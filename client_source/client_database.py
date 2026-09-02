# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from client_exchange_core import build_client_package, content_hash, utc_now_iso
from client_runtime import data_dir


class ClientDatabase:
    def __init__(self, license_store):
        self.license_store = license_store
        self.path = data_dir() / "client_records.db"
        self.conn = sqlite3.connect(str(self.path))
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create()

    def _create(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS client_records (
                record_uuid TEXT PRIMARY KEY,
                record_type TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1,
                base_hash TEXT,
                content_hash TEXT NOT NULL,
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                exported_revision INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_client_records_type ON client_records(record_type,updated_at)")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS client_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_uuid TEXT NOT NULL UNIQUE,
                file_path TEXT,
                report_period TEXT,
                record_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def _encrypt(self, record_uuid: str, revision: int, data: Dict[str, Any]):
        nonce = secrets.token_bytes(12)
        aad = f"{record_uuid}|{revision}".encode("ascii")
        clear = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return nonce, AESGCM(self.license_store.data_key()).encrypt(nonce, clear, aad)

    def _decrypt(self, record_uuid: str, revision: int, nonce: bytes, ciphertext: bytes):
        aad = f"{record_uuid}|{revision}".encode("ascii")
        clear = AESGCM(self.license_store.data_key()).decrypt(nonce, ciphertext, aad)
        return json.loads(clear.decode("utf-8"))

    def save_record(self, record_type: str, data: Dict[str, Any], record_uuid: Optional[str] = None) -> str:
        if record_type not in {"member", "meeting", "issue", "resolution", "action"}:
            raise ValueError("نوع رکورد معتبر نیست.")
        now = utc_now_iso()
        if record_uuid:
            row = self.conn.execute(
                "SELECT revision,content_hash,created_at FROM client_records WHERE record_uuid=?", (record_uuid,)
            ).fetchone()
        else:
            row = None
        if row:
            revision = int(row[0]) + 1
            base_hash = row[1]
            created_at = row[2]
        else:
            record_uuid = str(uuid.uuid4())
            revision = 1
            base_hash = None
            created_at = now
        c_hash = content_hash(data)
        nonce, cipher = self._encrypt(record_uuid, revision, data)
        self.conn.execute(
            """INSERT INTO client_records(record_uuid,record_type,revision,base_hash,content_hash,nonce,ciphertext,created_at,updated_at,exported_revision)
               VALUES (?,?,?,?,?,?,?,?,?,0)
               ON CONFLICT(record_uuid) DO UPDATE SET record_type=excluded.record_type,revision=excluded.revision,
                 base_hash=excluded.base_hash,content_hash=excluded.content_hash,nonce=excluded.nonce,
                 ciphertext=excluded.ciphertext,updated_at=excluded.updated_at""",
            (record_uuid, record_type, revision, base_hash, c_hash, nonce, cipher, created_at, now),
        )
        self.conn.commit()
        return record_uuid

    def get_record(self, record_uuid: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """SELECT record_uuid,record_type,revision,base_hash,content_hash,nonce,ciphertext,created_at,updated_at,exported_revision
               FROM client_records WHERE record_uuid=?""", (record_uuid,)
        ).fetchone()
        if not row:
            return None
        data = self._decrypt(row[0], int(row[2]), row[5], row[6])
        return {
            "record_uuid": row[0], "record_type": row[1], "revision": int(row[2]),
            "base_hash": row[3], "content_hash": row[4], "data": data,
            "created_at": row[7], "updated_at": row[8], "exported_revision": int(row[9] or 0),
        }

    def list_records(self, record_type: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT record_uuid FROM client_records"
        params = []
        if record_type:
            sql += " WHERE record_type=?"; params.append(record_type)
        sql += " ORDER BY updated_at DESC"
        return [self.get_record(r[0]) for r in self.conn.execute(sql, params).fetchall()]

    def pending_records(self, include_all=False) -> List[Dict[str, Any]]:
        rows = self.list_records()
        if include_all:
            return rows
        return [r for r in rows if int(r["revision"]) > int(r["exported_revision"])]

    def export_package(self, output_path: str, report_period: str, include_all=False) -> Dict[str, Any]:
        valid = self.license_store.validate(update_clock=True)
        if valid["status"] != "valid":
            raise ValueError(valid["message"])
        license_item = valid["license"]
        records = self.pending_records(include_all=include_all)
        if not records:
            raise ValueError("رکورد جدید یا اصلاح‌شده‌ای برای خروجی وجود ندارد.")
        payload = {
            "license_id": license_item["license_id"],
            "device_id": license_item["device_id"],
            "responsible_full_name": license_item["responsible_full_name"],
            "zone_id": license_item["zone_id"], "zone_name": license_item["zone_name"],
            "committee_code": license_item["committee_code"], "committee_title": license_item["committee_title"],
            "report_period": report_period.strip() or "بدون دوره",
            "client_version": "1.0.0",
            "records": [
                {"record_uuid": r["record_uuid"], "record_type": r["record_type"], "revision": r["revision"],
                 "base_hash": r["base_hash"], "content_hash": r["content_hash"],
                 "created_at": r["created_at"], "updated_at": r["updated_at"], "data": r["data"]}
                for r in records
            ],
        }
        envelope = build_client_package(
            output_path, payload, self.license_store.key_store,
            self.license_store.load()["admin_exchange_public"] if self.license_store.load().get("admin_exchange_public") else json.loads(self.license_store.trust_path.read_text(encoding="utf-8"))["exchange_public"],
        )
        package_uuid = envelope["package_id"]
        self.conn.execute(
            "INSERT INTO client_exports(package_uuid,file_path,report_period,record_count) VALUES (?,?,?,?)",
            (package_uuid, output_path, report_period, len(records)),
        )
        for r in records:
            self.conn.execute(
                "UPDATE client_records SET exported_revision=? WHERE record_uuid=?",
                (r["revision"], r["record_uuid"]),
            )
        self.conn.commit()
        return {"package_uuid": package_uuid, "record_count": len(records), "path": output_path}

    def close(self):
        try: self.conn.close()
        except Exception: pass
