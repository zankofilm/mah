# -*- coding: utf-8 -*-
"""جداول و منطق ادمین برای صدور مجوز کلاینت و ورود بسته‌های رمزنگاری‌شده."""
from __future__ import annotations

import json
import io
import base64
import binascii
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from client_exchange_core import (
    AdminKeyStore, ExchangeError, build_activation_file, national_code_hash,
    normalize_national_code, open_client_package, password_hash,
    read_activation_request, sha256_file, validate_package_payload, parse_utc,
)
from runtime_paths import get_data_dir, get_client_exchange_key_dir


COMMITTEE_TITLES = {
    "infrastructure": "عمران، خدمات محلی و محیط‌زیست",
    "health": "بهداشت و سلامت",
    "sports": "نشاط و ورزش",
    "security": "امنیت عمومی و آسیب‌های اجتماعی",
    "support": "خدمات حمایتی و معیشتی",
    "culture": "امور فرهنگی، آموزشی و دینی",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


_MEETING_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _normalize_meeting_number(value: Any) -> str:
    """Normalize Persian/Arabic digits and whitespace for safe uniqueness checks."""
    text = str(value or "").translate(_MEETING_DIGIT_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip()
    if text.isdigit():
        return str(int(text))
    return text.casefold()


class ClientExchangeMixin:
    """Mixin قابل افزودن به Database اصلی بدون شکستن نسخه‌های قبلی."""

    def _client_key_store(self) -> AdminKeyStore:
        return AdminKeyStore(get_client_exchange_key_dir())

    def _create_client_exchange_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_activation_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_uuid TEXT NOT NULL UNIQUE,
                device_id TEXT NOT NULL,
                national_code_hash TEXT NOT NULL,
                client_sign_public TEXT NOT NULL,
                client_version TEXT,
                request_created_at TEXT,
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                source_file_hash TEXT NOT NULL UNIQUE,
                raw_json TEXT NOT NULL,
                status TEXT DEFAULT 'در انتظار صدور'
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_requests_status ON client_activation_requests(status, imported_at)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_uuid TEXT NOT NULL UNIQUE,
                request_id INTEGER,
                responsible_first_name TEXT NOT NULL,
                responsible_last_name TEXT NOT NULL,
                national_code TEXT NOT NULL,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                zone_id INTEGER NOT NULL,
                zone_name TEXT NOT NULL,
                committee_code TEXT NOT NULL,
                committee_title TEXT NOT NULL,
                role_title TEXT NOT NULL,
                device_id TEXT NOT NULL,
                client_sign_public TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_until TEXT NOT NULL,
                warning_days INTEGER DEFAULT 7,
                allow_renewal INTEGER DEFAULT 1,
                status TEXT DEFAULT 'فعال',
                activation_issued_at TEXT,
                last_renewed_at TEXT,
                last_package_at TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES client_activation_requests(id) ON DELETE SET NULL,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE RESTRICT,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_licenses_scope ON client_licenses(zone_id, committee_code, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_licenses_expiry ON client_licenses(valid_until, status)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_import_packages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_uuid TEXT NOT NULL UNIQUE,
                source_file_hash TEXT NOT NULL UNIQUE,
                license_uuid TEXT NOT NULL,
                responsible_name TEXT,
                zone_id INTEGER,
                zone_name TEXT,
                committee_code TEXT,
                committee_title TEXT,
                report_period TEXT,
                client_created_at TEXT,
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                imported_by INTEGER,
                status TEXT NOT NULL,
                new_count INTEGER DEFAULT 0,
                changed_count INTEGER DEFAULT 0,
                duplicate_count INTEGER DEFAULT 0,
                conflict_count INTEGER DEFAULT 0,
                accepted_count INTEGER DEFAULT 0,
                rejected_count INTEGER DEFAULT 0,
                summary_json TEXT,
                FOREIGN KEY (imported_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_import_scope ON client_import_packages(zone_id, committee_code, imported_at)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_record_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                license_uuid TEXT NOT NULL,
                record_uuid TEXT NOT NULL,
                record_type TEXT NOT NULL,
                current_revision INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                admin_entity_type TEXT,
                admin_entity_id INTEGER,
                last_package_uuid TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(license_uuid, record_uuid)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_client_record_admin ON client_record_versions(admin_entity_type, admin_entity_id)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS client_import_record_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                package_uuid TEXT NOT NULL,
                license_uuid TEXT NOT NULL,
                record_uuid TEXT NOT NULL,
                record_type TEXT NOT NULL,
                incoming_revision INTEGER,
                incoming_hash TEXT,
                classification TEXT,
                decision TEXT,
                admin_entity_type TEXT,
                admin_entity_id INTEGER,
                details_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    # ---------- درخواست و مجوز ----------
    def import_client_activation_request(self, file_path: str) -> Dict[str, Any]:
        file_hash = sha256_file(file_path)
        existing = self.conn.execute(
            "SELECT id,request_uuid,status FROM client_activation_requests WHERE source_file_hash=?", (file_hash,)
        ).fetchone()
        if existing:
            raise ValueError("این فایل درخواست فعال‌سازی قبلاً وارد شده است.")
        data = read_activation_request(file_path)
        try:
            cur = self.conn.cursor()
            cur.execute(
                """INSERT INTO client_activation_requests
                   (request_uuid,device_id,national_code_hash,client_sign_public,client_version,
                    request_created_at,source_file_hash,raw_json,status)
                   VALUES (?,?,?,?,?,?,?,?, 'در انتظار صدور')""",
                (data["request_id"], data["device_id"], data["national_code_hash"],
                 data["client_sign_public"], data.get("client_version"), data.get("created_at"),
                 file_hash, _json(data)),
            )
            self.conn.commit()
            data["id"] = cur.lastrowid
            return data
        except sqlite3.IntegrityError as exc:
            raise ValueError("این درخواست فعال‌سازی قبلاً ثبت شده است.") from exc

    def list_client_activation_requests(self, pending_only=False) -> List[Dict[str, Any]]:
        sql = """SELECT id,request_uuid,device_id,national_code_hash,client_sign_public,client_version,
                        request_created_at,imported_at,source_file_hash,status
                 FROM client_activation_requests"""
        params: List[Any] = []
        if pending_only:
            sql += " WHERE status='در انتظار صدور'"
        sql += " ORDER BY id DESC"
        keys = ["id","request_uuid","device_id","national_code_hash","client_sign_public","client_version",
                "request_created_at","imported_at","source_file_hash","status"]
        return [dict(zip(keys, r)) for r in self.conn.execute(sql, params).fetchall()]

    def get_client_activation_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        return next((x for x in self.list_client_activation_requests(False) if x["id"] == int(request_id)), None)

    def create_client_license(self, request_id: int, output_path: str, *, first_name: str, last_name: str,
                              national_code: str, username: str, initial_password: str,
                              zone_id: int, committee_code: str, role_title: str,
                              valid_from: str, valid_until: str, warning_days: int = 7,
                              allow_renewal: bool = True) -> Dict[str, Any]:
        request = self.get_client_activation_request(request_id)
        if not request:
            raise ValueError("درخواست فعال‌سازی انتخاب‌شده وجود ندارد.")
        if request["status"] not in {"در انتظار صدور", "نیازمند صدور مجدد"}:
            raise ValueError("برای این درخواست قبلاً مجوز صادر شده است.")
        code = normalize_national_code(national_code)
        if national_code_hash(code) != request["national_code_hash"]:
            raise ValueError("کد ملی با کد واردشده هنگام ساخت درخواست کلاینت تطابق ندارد.")
        zone = next((z for z in self.get_zones() if int(z["id"]) == int(zone_id)), None)
        if not zone:
            raise ValueError("بلوک انتخاب‌شده معتبر نیست.")
        committee = next((c for c in self.get_zone_committees(zone_id) if c["committee_code"] == committee_code), None)
        if not committee:
            raise ValueError("کمیته انتخاب‌شده در بلوک وجود ندارد.")
        if not (first_name or "").strip() or not (last_name or "").strip():
            raise ValueError("نام و نام خانوادگی مسئول الزامی است.")
        if not (username or "").strip():
            raise ValueError("نام کاربری الزامی است.")
        start = datetime.fromisoformat(valid_from)
        end = datetime.fromisoformat(valid_until)
        if end <= start:
            raise ValueError("تاریخ انقضا باید بعد از تاریخ شروع باشد.")
        license_uuid = str(uuid.uuid4())
        encoded_password = password_hash(initial_password)
        current_user = self.get_current_user() or {}
        payload = {
            "license_id": license_uuid,
            "responsible_first_name": first_name.strip(),
            "responsible_last_name": last_name.strip(),
            "responsible_full_name": f"{first_name.strip()} {last_name.strip()}".strip(),
            "username": username.strip(),
            "password_hash": encoded_password,
            "zone_id": int(zone_id),
            "zone_name": zone["name"],
            "committee_code": committee_code,
            "committee_title": committee["title"],
            "role_title": role_title.strip() or f"مسئول کمیته {committee['title']}",
            "permissions": ["committee.read", "committee.write", "committee.export"],
            "device_id": request["device_id"],
            "client_sign_public": request["client_sign_public"],
            "valid_from": valid_from,
            "valid_until": valid_until,
            "warning_days": max(0, min(90, int(warning_days or 0))),
            "allow_renewal": bool(allow_renewal),
            "status": "فعال",
        }
        build_activation_file(output_path, payload, code, self._client_key_store(), kind="activation")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self.conn.execute(
                """INSERT INTO client_licenses
                   (license_uuid,request_id,responsible_first_name,responsible_last_name,national_code,
                    username,password_hash,zone_id,zone_name,committee_code,committee_title,role_title,
                    device_id,client_sign_public,valid_from,valid_until,warning_days,allow_renewal,status,
                    activation_issued_at,created_by)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'فعال', CURRENT_TIMESTAMP,?)""",
                (license_uuid, request_id, first_name.strip(), last_name.strip(), code, username.strip(),
                 encoded_password, int(zone_id), zone["name"], committee_code, committee["title"],
                 payload["role_title"], request["device_id"], request["client_sign_public"],
                 valid_from, valid_until, payload["warning_days"], int(bool(allow_renewal)), current_user.get("id")),
            )
            self.conn.execute("UPDATE client_activation_requests SET status='مجوز صادر شد' WHERE id=?", (request_id,))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            try:
                os.remove(output_path)
            except Exception:
                pass
            raise
        return payload

    def list_client_licenses(self, include_inactive=True) -> List[Dict[str, Any]]:
        sql = """SELECT id,license_uuid,request_id,responsible_first_name,responsible_last_name,national_code,
                        username,zone_id,zone_name,committee_code,committee_title,role_title,device_id,
                        valid_from,valid_until,warning_days,allow_renewal,status,activation_issued_at,
                        last_renewed_at,last_package_at,created_at,updated_at
                 FROM client_licenses"""
        if not include_inactive:
            sql += " WHERE status='فعال'"
        sql += " ORDER BY id DESC"
        keys = ["id","license_uuid","request_id","responsible_first_name","responsible_last_name","national_code",
                "username","zone_id","zone_name","committee_code","committee_title","role_title","device_id",
                "valid_from","valid_until","warning_days","allow_renewal","status","activation_issued_at",
                "last_renewed_at","last_package_at","created_at","updated_at"]
        rows = [dict(zip(keys, r)) for r in self.conn.execute(sql).fetchall()]
        for item in rows:
            item["responsible_full_name"] = f"{item['responsible_first_name']} {item['responsible_last_name']}".strip()
        return rows

    def get_client_license(self, license_uuid: str) -> Optional[Dict[str, Any]]:
        return next((x for x in self.list_client_licenses(True) if x["license_uuid"] == license_uuid), None)

    def get_client_license_details(self, license_uuid: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """SELECT id,license_uuid,request_id,responsible_first_name,responsible_last_name,national_code,
                      username,password_hash,zone_id,zone_name,committee_code,committee_title,role_title,
                      device_id,client_sign_public,valid_from,valid_until,warning_days,allow_renewal,status,
                      activation_issued_at,last_renewed_at,last_package_at,created_at,updated_at
               FROM client_licenses WHERE license_uuid=?""",
            (str(license_uuid),),
        ).fetchone()
        if not row:
            return None
        keys = [
            "id","license_uuid","request_id","responsible_first_name","responsible_last_name",
            "national_code","username","password_hash","zone_id","zone_name","committee_code",
            "committee_title","role_title","device_id","client_sign_public","valid_from",
            "valid_until","warning_days","allow_renewal","status","activation_issued_at",
            "last_renewed_at","last_package_at","created_at","updated_at",
        ]
        item = dict(zip(keys, row))
        item["responsible_full_name"] = f"{item['responsible_first_name']} {item['responsible_last_name']}".strip()
        return item

    def update_client_license(self, license_uuid: str, output_path: str, *, first_name: str,
                              last_name: str, national_code: str, username: str, new_password: str,
                              zone_id: int, committee_code: str, role_title: str, valid_from: str,
                              valid_until: str, warning_days: int = 7, allow_renewal: bool = True,
                              status: str = "فعال") -> Dict[str, Any]:
        existing = self.get_client_license_details(license_uuid)
        if not existing:
            raise ValueError("فعال‌سازی انتخاب‌شده وجود ندارد.")
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        username = (username or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی مسئول الزامی است.")
        if not username:
            raise ValueError("نام کاربری الزامی است.")
        code = normalize_national_code(national_code)
        zone = next((z for z in self.get_zones() if int(z["id"]) == int(zone_id)), None)
        if not zone:
            raise ValueError("بلوک انتخاب‌شده معتبر نیست.")
        committee = next((c for c in self.get_zone_committees(zone_id) if c["committee_code"] == committee_code), None)
        if not committee:
            raise ValueError("کمیته انتخاب‌شده در بلوک وجود ندارد.")
        if status not in {"فعال", "تعلیق", "لغوشده", "منقضی"}:
            raise ValueError("وضعیت مجوز معتبر نیست.")
        start = datetime.fromisoformat(valid_from)
        end = datetime.fromisoformat(valid_until)
        if end <= start:
            raise ValueError("تاریخ انقضا باید بعد از تاریخ شروع باشد.")
        if new_password and len(new_password) < 8:
            raise ValueError("رمز عبور جدید باید حداقل ۸ نویسه باشد.")
        encoded_password = password_hash(new_password) if new_password else existing["password_hash"]
        resolved_role = (role_title or "").strip() or f"مسئول کمیته {committee['title']}"
        safe_warning_days = max(0, min(90, int(warning_days or 0)))
        payload = {
            "license_id": existing["license_uuid"],
            "responsible_first_name": first_name,
            "responsible_last_name": last_name,
            "responsible_full_name": f"{first_name} {last_name}".strip(),
            "username": username,
            "password_hash": encoded_password,
            "zone_id": int(zone_id),
            "zone_name": zone["name"],
            "committee_code": committee_code,
            "committee_title": committee["title"],
            "role_title": resolved_role,
            "permissions": ["committee.read", "committee.write", "committee.export"],
            "device_id": existing["device_id"],
            "client_sign_public": existing["client_sign_public"],
            "valid_from": valid_from,
            "valid_until": valid_until,
            "warning_days": safe_warning_days,
            "allow_renewal": bool(allow_renewal),
            "status": status,
        }
        build_activation_file(output_path, payload, code, self._client_key_store(), kind="activation")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            cur = self.conn.execute(
                """UPDATE client_licenses SET
                       responsible_first_name=?,responsible_last_name=?,national_code=?,username=?,
                       password_hash=?,zone_id=?,zone_name=?,committee_code=?,committee_title=?,role_title=?,
                       valid_from=?,valid_until=?,warning_days=?,allow_renewal=?,status=?,updated_at=CURRENT_TIMESTAMP
                   WHERE license_uuid=?""",
                (first_name, last_name, code, username, encoded_password, int(zone_id), zone["name"],
                 committee_code, committee["title"], resolved_role, valid_from, valid_until,
                 safe_warning_days, int(bool(allow_renewal)), status, existing["license_uuid"]),
            )
            if cur.rowcount != 1:
                raise ValueError("فعال‌سازی هنگام ذخیره پیدا نشد.")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            try:
                os.remove(output_path)
            except Exception:
                pass
            raise
        return payload

    def delete_client_license(self, license_uuid: str) -> bool:
        existing = self.get_client_license_details(license_uuid)
        if not existing:
            raise ValueError("فعال‌سازی انتخاب‌شده وجود ندارد.")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            cur = self.conn.execute("DELETE FROM client_licenses WHERE license_uuid=?", (str(license_uuid),))
            if cur.rowcount != 1:
                raise ValueError("فعال‌سازی هنگام حذف پیدا نشد.")
            request_id = existing.get("request_id")
            if request_id is not None:
                remaining = self.conn.execute(
                    "SELECT COUNT(*) FROM client_licenses WHERE request_id=?", (int(request_id),)
                ).fetchone()[0]
                if int(remaining or 0) == 0:
                    self.conn.execute(
                        "UPDATE client_activation_requests SET status='نیازمند صدور مجدد' WHERE id=?",
                        (int(request_id),),
                    )
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            raise

    def issue_client_renewal(self, license_uuid: str, output_path: str, national_code: str,
                             valid_from: str, valid_until: str, warning_days: Optional[int] = None) -> Dict[str, Any]:
        license_item = self.get_client_license(license_uuid)
        if not license_item:
            raise ValueError("مجوز انتخاب‌شده وجود ندارد.")
        if not license_item["allow_renewal"]:
            raise ValueError("تمدید برای این مجوز غیرفعال شده است.")
        code = normalize_national_code(national_code)
        if code != license_item["national_code"]:
            raise ValueError("کد ملی با مجوز انتخاب‌شده تطابق ندارد.")
        start = datetime.fromisoformat(valid_from)
        end = datetime.fromisoformat(valid_until)
        if end <= start:
            raise ValueError("تاریخ انقضای جدید باید بعد از تاریخ شروع باشد.")
        payload = {
            "license_id": license_uuid,
            "responsible_first_name": license_item["responsible_first_name"],
            "responsible_last_name": license_item["responsible_last_name"],
            "responsible_full_name": license_item["responsible_full_name"],
            "username": license_item["username"],
            "zone_id": license_item["zone_id"], "zone_name": license_item["zone_name"],
            "committee_code": license_item["committee_code"], "committee_title": license_item["committee_title"],
            "role_title": license_item["role_title"], "device_id": license_item["device_id"],
            "valid_from": valid_from, "valid_until": valid_until,
            "warning_days": int(warning_days if warning_days is not None else license_item["warning_days"]),
            "allow_renewal": bool(license_item["allow_renewal"]), "status": "فعال",
        }
        build_activation_file(output_path, payload, code, self._client_key_store(), kind="renewal")
        self.conn.execute(
            """UPDATE client_licenses SET valid_from=?,valid_until=?,warning_days=?,status='فعال',
               last_renewed_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE license_uuid=?""",
            (valid_from, valid_until, payload["warning_days"], license_uuid),
        )
        self.conn.commit()
        return payload

    def set_client_license_status(self, license_uuid: str, status: str) -> bool:
        if status not in {"فعال", "تعلیق", "لغوشده", "منقضی"}:
            raise ValueError("وضعیت مجوز معتبر نیست.")
        cur = self.conn.execute(
            "UPDATE client_licenses SET status=?,updated_at=CURRENT_TIMESTAMP WHERE license_uuid=?",
            (status, license_uuid),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ---------- کنترل یکتایی شماره جلسه ----------
    def _find_committee_meeting_by_number(self, committee_id: int, meeting_number: Any, exclude_id=None):
        target = _normalize_meeting_number(meeting_number)
        if not target:
            return None
        rows = self.conn.execute(
            """SELECT id,title,meeting_number,meeting_date FROM committee_meetings
               WHERE committee_id=? ORDER BY id""",
            (int(committee_id),),
        ).fetchall()
        for row in rows:
            if exclude_id is not None and int(row[0]) == int(exclude_id):
                continue
            if _normalize_meeting_number(row[2]) == target:
                return {
                    "id": int(row[0]),
                    "title": row[1] or "",
                    "meeting_number": str(row[2] or ""),
                    "meeting_date": row[3] or "",
                }
        return None

    def _next_unique_committee_meeting_number(self, committee_id: int) -> str:
        rows = self.conn.execute(
            "SELECT meeting_number FROM committee_meetings WHERE committee_id=?",
            (int(committee_id),),
        ).fetchall()
        numeric = []
        for row in rows:
            value = _normalize_meeting_number(row[0])
            if value.isdigit() and int(value) > 0:
                numeric.append(int(value))
        return str((max(numeric) if numeric else 0) + 1)

    # ---------- پیش‌نمایش و ورود ----------
    def preview_client_package(self, file_path: str) -> Dict[str, Any]:
        file_hash = sha256_file(file_path)
        duplicate = self.conn.execute(
            "SELECT package_uuid,imported_at,status FROM client_import_packages WHERE source_file_hash=?", (file_hash,)
        ).fetchone()
        if duplicate:
            raise ValueError(f"این فایل قبلاً با شناسه {duplicate[0]} وارد شده است.")
        try:
            raw = json.loads(Path(file_path).read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError("فایل کلاینت قابل خواندن نیست.") from exc
        license_uuid = str(raw.get("license_id") or "")
        license_item = self.get_client_license(license_uuid)
        if not license_item:
            raise ValueError("مجوز این فایل در نسخه ادمین ثبت نشده است.")
        if license_item["status"] in {"لغوشده", "تعلیق"}:
            raise ValueError(f"مجوز کلاینت در وضعیت «{license_item['status']}» است و فایل پذیرفته نمی‌شود.")
        payload = open_client_package(
            file_path, self._client_key_store(), self._license_sign_public(license_uuid),
            package_secret=self._license_package_secret(license_uuid),
        )
        validate_package_payload(payload)
        if payload.get("device_id") != license_item["device_id"]:
            raise ValueError("شناسه دستگاه فایل با دستگاه مجاز تطابق ندارد.")
        if int(payload.get("zone_id") or -1) != int(license_item["zone_id"]):
            raise ValueError("بلوک فایل با محدوده مجوز تطابق ندارد.")
        if payload.get("committee_code") != license_item["committee_code"]:
            raise ValueError("کمیته فایل با محدوده مجوز تطابق ندارد.")
        try:
            package_time = parse_utc(payload.get("created_at"))
            valid_from = parse_utc(str(license_item["valid_from"]) + ("T00:00:00Z" if "T" not in str(license_item["valid_from"]) else ""))
            valid_until = parse_utc(str(license_item["valid_until"]) + ("T23:59:59Z" if "T" not in str(license_item["valid_until"]) else ""))
        except Exception as exc:
            raise ValueError("تاریخ بسته یا محدوده اعتبار مجوز معتبر نیست.") from exc
        if package_time < valid_from or package_time > valid_until:
            raise ValueError("این فایل خارج از بازه اعتبار مجوز کلاینت ساخته شده و پذیرفته نمی‌شود.")
        if len(payload.get("records") or []) > 10000:
            raise ValueError("تعداد رکوردهای فایل از سقف مجاز بیشتر است.")
        duplicate_id = self.conn.execute(
            "SELECT imported_at,status FROM client_import_packages WHERE package_uuid=?", (payload["package_id"],)
        ).fetchone()
        if duplicate_id:
            raise ValueError("شناسه این بسته قبلاً وارد شده و ورود دوباره مجاز نیست.")
        committee_id = self._committee_id(int(license_item["zone_id"]), license_item["committee_code"])

        # وجود دو صورتجلسه با یک شماره در خود فایل، نشانه بسته ناسالم است و کل ورود متوقف می‌شود.
        package_meeting_numbers = {}
        for raw_record in payload.get("records", []):
            if raw_record.get("record_type") != "meeting":
                continue
            number = _normalize_meeting_number((raw_record.get("data") or {}).get("meeting_number"))
            if not number:
                continue
            package_meeting_numbers.setdefault(number, []).append(str(raw_record.get("record_uuid") or ""))
        duplicated_in_package = [number for number, ids in package_meeting_numbers.items() if len(ids) > 1]
        if duplicated_in_package:
            joined = "، ".join(duplicated_in_package)
            raise ValueError(
                f"فایل کلاینت شامل چند صورتجلسه با شماره تکراری «{joined}» در همین کمیته است. "
                "ورود متوقف شد؛ ابتدا شماره‌ها در کلاینت اصلاح و خروجی جدید ساخته شود."
            )

        records = []
        counts = {"new": 0, "changed": 0, "duplicate": 0, "conflict": 0}
        for record in payload.get("records", []):
            old = self.conn.execute(
                """SELECT current_revision,content_hash,admin_entity_type,admin_entity_id,last_package_uuid
                   FROM client_record_versions WHERE license_uuid=? AND record_uuid=?""",
                (license_uuid, record["record_uuid"]),
            ).fetchone()
            if old is None:
                classification = "new"
            else:
                old_revision, old_hash = int(old[0]), old[1]
                incoming_revision = int(record["revision"])
                if record["content_hash"] == old_hash:
                    classification = "duplicate"
                elif incoming_revision > old_revision and (not record.get("base_hash") or record.get("base_hash") == old_hash):
                    classification = "changed"
                else:
                    classification = "conflict"

            item = dict(record)
            item["meeting_number_conflict"] = None
            if record.get("record_type") == "meeting" and classification != "duplicate":
                data = record.get("data") or {}
                incoming_number = _normalize_meeting_number(data.get("meeting_number"))
                mapped_id = int(old[3]) if old and old[2] == "committee_meeting" and old[3] is not None else None
                if incoming_number:
                    existing = self._find_committee_meeting_by_number(committee_id, incoming_number)
                    if existing and (mapped_id is None or int(existing["id"]) != int(mapped_id)):
                        mapped = None
                        if mapped_id is not None:
                            row = self.conn.execute(
                                "SELECT id,title,meeting_number,meeting_date FROM committee_meetings WHERE id=? AND committee_id=?",
                                (mapped_id, committee_id),
                            ).fetchone()
                            if row:
                                mapped = {
                                    "id": int(row[0]), "title": row[1] or "",
                                    "meeting_number": str(row[2] or ""), "meeting_date": row[3] or "",
                                }
                        item["meeting_number_conflict"] = {
                            "kind": "mapped_number_collision" if mapped else "existing_number",
                            "incoming_number": incoming_number,
                            "existing_meeting_id": existing["id"],
                            "existing_title": existing["title"],
                            "existing_date": existing["meeting_date"],
                            "mapped_meeting_id": mapped["id"] if mapped else None,
                            "mapped_number": mapped["meeting_number"] if mapped else None,
                            "mapped_title": mapped["title"] if mapped else None,
                        }
                        classification = "conflict"

            counts[classification] += 1
            item["classification"] = classification
            item["default_decision"] = "accept" if classification in {"new"} else "review" if classification in {"changed", "conflict"} else "reject"
            records.append(item)
        return {
            "file_path": file_path, "file_hash": file_hash, "payload": payload,
            "license": license_item, "records": records, "counts": counts,
            "responsible_name": license_item["responsible_full_name"],
            "zone_name": license_item["zone_name"], "committee_title": license_item["committee_title"],
            "report_period": payload.get("report_period") or "نامشخص",
            "client_created_at": payload.get("created_at"),
        }

    def _license_sign_public(self, license_uuid: str) -> str:
        row = self.conn.execute(
            "SELECT client_sign_public FROM client_licenses WHERE license_uuid=?", (license_uuid,)
        ).fetchone()
        if not row:
            raise ValueError("کلید امضای کلاینت برای مجوز پیدا نشد.")
        return row[0]

    def _license_package_secret(self, license_uuid: str) -> str:
        row = self.conn.execute(
            "SELECT password_hash FROM client_licenses WHERE license_uuid=?", (license_uuid,)
        ).fetchone()
        if not row or not row[0]:
            raise ValueError("کلید تبادل امن برای این مجوز در دیتابیس پیدا نشد.")
        return str(row[0])

    def _backup_before_client_import(self, package_uuid: str) -> str:
        backup_dir = os.path.join(os.path.dirname(self.db_path), "automatic_backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(backup_dir, f"before_client_import_{package_uuid[:8]}_{stamp}.db")
        target = sqlite3.connect(path)
        try:
            self.conn.backup(target)
            target.commit()
        finally:
            target.close()
        return path

    def apply_client_package(self, preview: Dict[str, Any], decisions: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        payload = preview["payload"]
        license_item = preview["license"]
        decisions = decisions or {}
        package_uuid = payload["package_id"]
        self._backup_before_client_import(package_uuid)
        accepted = rejected = 0
        results = []
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            type_priority = {"member": 1, "meeting": 2, "resolution": 3, "issue": 4, "action": 5}
            ordered_records = sorted(
                preview["records"],
                key=lambda item: (type_priority.get(item.get("record_type"), 99), str(item.get("created_at") or "")),
            )
            package_meeting_decisions = {
                item["record_uuid"]: decisions.get(item["record_uuid"], "accept" if item["classification"] == "new" else "reject")
                for item in ordered_records if item.get("record_type") == "meeting"
            }
            for record in ordered_records:
                classification = record["classification"]
                decision = decisions.get(record["record_uuid"])
                allowed_decisions = {"accept", "reject", "merge_existing", "renumber", "keep_assigned"}
                if decision not in allowed_decisions:
                    decision = "accept" if classification == "new" else "reject"
                if record.get("record_type") == "resolution" and decision != "reject":
                    meeting_uuid = str((record.get("data") or {}).get("meeting_uuid") or "")
                    parent_decision = package_meeting_decisions.get(meeting_uuid)
                    existing_parent = self._mapped_client_entity(
                        license_item["license_uuid"], meeting_uuid, "committee_meeting"
                    ) if meeting_uuid else None
                    if meeting_uuid and parent_decision == "reject" and not existing_parent:
                        decision = "reject"
                admin_type = admin_id = None
                details = {}
                if decision != "reject" and classification != "duplicate":
                    admin_type, admin_id, details = self._apply_client_record(license_item, record, decision)
                    self.conn.execute(
                        """INSERT INTO client_record_versions
                           (license_uuid,record_uuid,record_type,current_revision,content_hash,
                            admin_entity_type,admin_entity_id,last_package_uuid,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                           ON CONFLICT(license_uuid,record_uuid) DO UPDATE SET
                             record_type=excluded.record_type,current_revision=excluded.current_revision,
                             content_hash=excluded.content_hash,admin_entity_type=excluded.admin_entity_type,
                             admin_entity_id=excluded.admin_entity_id,last_package_uuid=excluded.last_package_uuid,
                             updated_at=CURRENT_TIMESTAMP""",
                        (license_item["license_uuid"], record["record_uuid"], record["record_type"],
                         int(record["revision"]), record["content_hash"], admin_type, admin_id, package_uuid),
                    )
                    accepted += 1
                else:
                    rejected += 1
                self.conn.execute(
                    """INSERT INTO client_import_record_log
                       (package_uuid,license_uuid,record_uuid,record_type,incoming_revision,incoming_hash,
                        classification,decision,admin_entity_type,admin_entity_id,details_json)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (package_uuid, license_item["license_uuid"], record["record_uuid"], record["record_type"],
                     int(record["revision"]), record["content_hash"], classification, decision,
                     admin_type, admin_id, _json(details)),
                )
                results.append({"record_uuid": record["record_uuid"], "decision": decision,
                                "admin_entity_type": admin_type, "admin_entity_id": admin_id})
            c = preview["counts"]
            status = "وارد شد" if accepted else "بدون رکورد پذیرفته‌شده"
            self.conn.execute(
                """INSERT INTO client_import_packages
                   (package_uuid,source_file_hash,license_uuid,responsible_name,zone_id,zone_name,
                    committee_code,committee_title,report_period,client_created_at,imported_by,status,
                    new_count,changed_count,duplicate_count,conflict_count,accepted_count,rejected_count,summary_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (package_uuid, preview["file_hash"], license_item["license_uuid"],
                 license_item["responsible_full_name"], license_item["zone_id"], license_item["zone_name"],
                 license_item["committee_code"], license_item["committee_title"], preview["report_period"],
                 preview["client_created_at"], (self.get_current_user() or {}).get("id"), status,
                 c["new"], c["changed"], c["duplicate"], c["conflict"], accepted, rejected,
                 _json({"results": results})),
            )
            self.conn.execute(
                "UPDATE client_licenses SET last_package_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE license_uuid=?",
                (license_item["license_uuid"],),
            )
            self.conn.commit()
            return {"package_uuid": package_uuid, "accepted": accepted, "rejected": rejected, "results": results}
        except Exception:
            self.conn.rollback()
            raise

    def _existing_record_mapping(self, license_uuid: str, record_uuid: str):
        return self.conn.execute(
            "SELECT admin_entity_type,admin_entity_id FROM client_record_versions WHERE license_uuid=? AND record_uuid=?",
            (license_uuid, record_uuid),
        ).fetchone()

    def _committee_id(self, zone_id: int, committee_code: str) -> int:
        row = self.conn.execute(
            "SELECT id FROM neighborhood_committees WHERE zone_id=? AND committee_code=?",
            (int(zone_id), committee_code),
        ).fetchone()
        if not row:
            self.ensure_zone_committees(zone_id, commit=False)
            row = self.conn.execute(
                "SELECT id FROM neighborhood_committees WHERE zone_id=? AND committee_code=?",
                (int(zone_id), committee_code),
            ).fetchone()
        if not row:
            raise ValueError("کمیته مقصد در دیتابیس ادمین پیدا نشد.")
        return int(row[0])

    def _apply_client_record(self, license_item: Dict[str, Any], record: Dict[str, Any], import_decision: str = "accept"):
        zone_id = int(license_item["zone_id"])
        committee_id = self._committee_id(zone_id, license_item["committee_code"])
        data = dict(record["data"])
        mapping = self._existing_record_mapping(license_item["license_uuid"], record["record_uuid"])
        mapped_type, mapped_id = (mapping or (None, None))
        rtype = record["record_type"]
        if rtype == "member":
            return self._apply_client_member(committee_id, data, mapped_id)
        if rtype == "meeting":
            return self._apply_client_meeting(
                license_item, committee_id, zone_id, data, mapped_id, import_decision, record
            )
        if rtype == "issue":
            return self._apply_client_issue(committee_id, zone_id, data, mapped_id)
        if rtype == "resolution":
            return self._apply_client_resolution(license_item, committee_id, zone_id, data, mapped_id)
        if rtype == "action":
            return self._apply_client_action(committee_id, zone_id, data, mapped_id)
        raise ValueError("نوع رکورد کلاینت پشتیبانی نمی‌شود.")

    def _apply_client_member(self, committee_id: int, data: Dict[str, Any], mapped_id):
        full_name = (data.get("full_name") or data.get("person_name") or "").strip()
        if not full_name:
            raise ValueError("نام عضو در فایل کلاینت خالی است.")
        code = ""
        if data.get("national_code"):
            code = self.normalize_national_code(data.get("national_code")) or ""
        person_id = None
        if code:
            person = self.get_person_by_national_code(code)
            first, last = self._split_person_name(full_name)
            if person:
                person_id = person["id"]
                self.conn.execute(
                    """UPDATE people_registry SET first_name=?,last_name=?,full_name=?,mobile=?,notes=COALESCE(notes,''),
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (first, last, full_name, data.get("mobile") or "", person_id),
                )
            else:
                cur = self.conn.execute(
                    """INSERT INTO people_registry(national_code,first_name,last_name,full_name,mobile,updated_at)
                       VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)""",
                    (code, first, last, full_name, data.get("mobile") or ""),
                )
                person_id = cur.lastrowid
        if not mapped_id and person_id:
            row = self.conn.execute(
                "SELECT id FROM committee_members WHERE committee_id=? AND person_id=?", (committee_id, person_id)
            ).fetchone()
            mapped_id = row[0] if row else None
        values = (
            person_id, full_name, code or None, data.get("mobile") or "", data.get("role") or data.get("member_role") or "عضو",
            data.get("member_type") or "عضو مردمی", data.get("agency") or data.get("agency_name") or "",
            data.get("status") or "فعال", data.get("notes") or "",
        )
        if mapped_id:
            self.conn.execute(
                """UPDATE committee_members SET person_id=?,person_name=?,national_code=?,mobile=?,member_role=?,
                   member_type=?,agency_name=?,status=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND committee_id=?""",
                values + (int(mapped_id), committee_id),
            )
            entity_id = int(mapped_id)
        else:
            cur = self.conn.execute(
                """INSERT INTO committee_members
                   (committee_id,person_id,person_name,national_code,mobile,member_role,member_type,agency_name,status,notes,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (committee_id,) + values,
            )
            entity_id = cur.lastrowid
        return "committee_member", entity_id, {"name": full_name}

    def _mapped_client_entity(self, license_uuid: str, record_uuid: str, expected_type: str):
        if not record_uuid:
            return None
        row = self.conn.execute(
            """SELECT admin_entity_id FROM client_record_versions
               WHERE license_uuid=? AND record_uuid=? AND admin_entity_type=?""",
            (license_uuid, str(record_uuid), expected_type),
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    @staticmethod
    def _decode_client_signature_png(value):
        if not value:
            return None
        text = str(value).strip()
        prefix = "data:image/png;base64,"
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
        try:
            raw = base64.b64decode(text, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("تصویر یکی از امضاهای صورتجلسه معتبر نیست.") from exc
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("حجم یکی از امضاهای صورتجلسه بیش از حد مجاز است.")
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("فرمت یکی از امضاهای صورتجلسه PNG نیست.")
        try:
            from PIL import Image
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                width, height = image.size
            if width < 1 or height < 1 or width > 4096 or height > 4096:
                raise ValueError("ابعاد یکی از امضاهای صورتجلسه معتبر نیست.")
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("فایل تصویری یکی از امضاهای صورتجلسه آسیب‌دیده است.") from exc
        return raw

    def _resolve_client_member_id(self, license_item, committee_id: int, signature_item):
        member_uuid = str((signature_item or {}).get("member_uuid") or "")
        member_id = self._mapped_client_entity(
            license_item["license_uuid"], member_uuid, "committee_member"
        )
        if member_id:
            row = self.conn.execute(
                "SELECT id FROM committee_members WHERE id=? AND committee_id=?",
                (member_id, committee_id),
            ).fetchone()
            if row:
                return member_id
        full_name = str((signature_item or {}).get("full_name") or "").strip()
        if full_name:
            row = self.conn.execute(
                """SELECT id FROM committee_members WHERE committee_id=? AND TRIM(person_name)=TRIM(?)
                   ORDER BY CASE WHEN status='فعال' THEN 0 ELSE 1 END, id LIMIT 1""",
                (committee_id, full_name),
            ).fetchone()
            if row:
                return int(row[0])
        return None

    def _sync_client_meeting_signatures(self, license_item, committee_id: int, meeting_id: int, data):
        if "member_signatures" not in data:
            return {"signature_count": 0, "signature_skipped": 0}
        signatures = data.get("member_signatures")
        if signatures is None:
            signatures = []
        if not isinstance(signatures, list):
            raise ValueError("ساختار امضاهای صورتجلسه معتبر نیست.")
        self.conn.execute("DELETE FROM committee_meeting_signatures WHERE meeting_id=?", (meeting_id,))
        saved = skipped = 0
        for item in signatures:
            if not isinstance(item, dict):
                skipped += 1
                continue
            member_id = self._resolve_client_member_id(license_item, committee_id, item)
            signature_png = self._decode_client_signature_png(item.get("signature_data"))
            if not member_id or not signature_png:
                skipped += 1
                continue
            self.conn.execute(
                """INSERT INTO committee_meeting_signatures
                   (meeting_id,member_id,signature_png,signed_at,updated_at)
                   VALUES (?,?,?,?,CURRENT_TIMESTAMP)
                   ON CONFLICT(meeting_id,member_id) DO UPDATE SET
                     signature_png=excluded.signature_png,signed_at=excluded.signed_at,
                     updated_at=CURRENT_TIMESTAMP""",
                (meeting_id, member_id, sqlite3.Binary(signature_png), item.get("signed_at")),
            )
            saved += 1
        return {"signature_count": saved, "signature_skipped": skipped}

    def _apply_client_meeting(
        self, license_item, committee_id, zone_id, data, mapped_id,
        import_decision="accept", record=None,
    ):
        record = record or {}
        conflict = record.get("meeting_number_conflict") or {}
        incoming_number = _normalize_meeting_number(data.get("meeting_number"))
        meeting_number = incoming_number

        if import_decision == "merge_existing":
            target_id = conflict.get("existing_meeting_id")
            if not target_id:
                raise ValueError("جلسه موجود برای ادغام پیدا نشد.")
            mapped_id = int(target_id)
        elif import_decision == "renumber":
            meeting_number = self._next_unique_committee_meeting_number(committee_id)
        elif import_decision == "keep_assigned":
            target_id = conflict.get("mapped_meeting_id") or mapped_id
            if not target_id:
                raise ValueError("جلسه قبلی این رکورد برای حفظ شماره پیدا نشد.")
            row = self.conn.execute(
                "SELECT meeting_number FROM committee_meetings WHERE id=? AND committee_id=?",
                (int(target_id), int(committee_id)),
            ).fetchone()
            if not row:
                raise ValueError("جلسه قبلی این رکورد در کمیته مقصد وجود ندارد.")
            mapped_id = int(target_id)
            meeting_number = _normalize_meeting_number(row[0])

        duplicate = self._find_committee_meeting_by_number(
            committee_id, meeting_number, exclude_id=mapped_id
        )
        if duplicate:
            raise ValueError(
                f"شماره جلسه «{meeting_number}» قبلاً برای «{duplicate['title']}» "
                "در همین کمیته ثبت شده است؛ ورود بدون تعیین تکلیف مجاز نیست."
            )

        raw_title = str(data.get("title") or "").strip()
        incoming_title_norm = _normalize_meeting_number(raw_title.replace("صورتجلسه شماره", "").strip())
        if (not raw_title) or (incoming_number and incoming_title_norm == incoming_number):
            title = f"صورتجلسه شماره {meeting_number}" if meeting_number else ""
        else:
            title = raw_title
        if not title:
            raise ValueError("عنوان جلسه خالی است.")

        minutes_text = data.get("discussion_notes") if data.get("discussion_notes") is not None else data.get("minutes_text")
        values = (
            title, meeting_number or None, data.get("meeting_date"), data.get("start_time"),
            data.get("place_name"), data.get("agenda"), data.get("attendees"), minutes_text or "",
            data.get("status") or "برگزار شد",
        )
        if mapped_id:
            self.conn.execute(
                """UPDATE committee_meetings SET title=?,meeting_number=?,meeting_date=?,start_time=?,place_name=?,
                   agenda=?,attendees=?,minutes_text=?,status=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND committee_id=?""",
                values + (int(mapped_id), committee_id),
            )
            entity_id = int(mapped_id)
        else:
            cur = self.conn.execute(
                """INSERT INTO committee_meetings
                   (committee_id,zone_id,title,meeting_number,meeting_date,start_time,place_name,agenda,attendees,
                    minutes_text,status,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (committee_id, zone_id) + values,
            )
            entity_id = cur.lastrowid
        signature_details = self._sync_client_meeting_signatures(
            license_item, committee_id, entity_id, data
        )
        return "committee_meeting", entity_id, {
            "title": title,
            "meeting_number": meeting_number,
            "incoming_meeting_number": incoming_number,
            "import_decision": import_decision,
            "date": data.get("meeting_date"),
            **signature_details,
        }

    def _apply_client_issue(self, committee_id, zone_id, data, mapped_id):
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("عنوان مسئله خالی است.")
        urgency = max(1, min(5, int(data.get("urgency") or 3)))
        severity = max(1, min(5, int(data.get("severity") or 3)))
        households = max(0, int(data.get("affected_households") or 0))
        safety = max(0, min(5, int(data.get("safety_risk") or 1)))
        score, level = self.calculate_issue_priority(urgency, severity, households, safety)
        values = (title, data.get("category") or "سایر", data.get("description") or "",
                  data.get("related_office") or "", urgency, severity, households, safety, score, level,
                  data.get("status") or "ثبت اولیه", "کلاینت کمیته", data.get("location_text") or "",
                  data.get("due_date"))
        if mapped_id:
            self.conn.execute(
                """UPDATE neighborhood_issues SET title=?,category=?,description=?,related_office=?,urgency=?,severity=?,
                   affected_households=?,safety_risk=?,priority_score=?,priority_level=?,status=?,source=?,location_text=?,
                   due_date=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND zone_id=?""",
                values + (int(mapped_id), zone_id),
            )
            entity_id = int(mapped_id)
        else:
            cur = self.conn.execute(
                """INSERT INTO neighborhood_issues
                   (zone_id,title,category,description,related_office,urgency,severity,affected_households,safety_risk,
                    priority_score,priority_level,status,source,location_text,due_date,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (zone_id,) + values,
            )
            entity_id = cur.lastrowid
        self.conn.execute(
            "INSERT OR IGNORE INTO committee_issue_links(committee_id,issue_id) VALUES (?,?)", (committee_id, entity_id)
        )
        return "issue", entity_id, {"title": title, "priority": level}

    def _apply_client_resolution(self, license_item, committee_id, zone_id, data, mapped_id):
        title = (data.get("title") or data.get("description") or "").strip()
        if not title:
            raise ValueError("عنوان مصوبه خالی است.")
        meeting_uuid = data.get("meeting_uuid")
        meeting_id = self._mapped_client_entity(
            license_item["license_uuid"], meeting_uuid, "committee_meeting"
        )
        if meeting_uuid and not meeting_id:
            raise ValueError("مصوبه به صورتجلسه‌ای متصل است که در ادمین پذیرفته یا ثبت نشده است.")
        values = (
            meeting_id, title, data.get("description") or "", data.get("responsible_agency") or "",
            data.get("responsible_person") or "", data.get("due_date"),
            data.get("status") or "در انتظار اقدام",
        )
        if mapped_id:
            self.conn.execute(
                """UPDATE committee_resolutions SET meeting_id=?,title=?,description=?,responsible_agency=?,
                   responsible_person=?,due_date=?,status=?,updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND committee_id=?""",
                values + (int(mapped_id), committee_id),
            )
            entity_id = int(mapped_id)
        else:
            cur = self.conn.execute(
                """INSERT INTO committee_resolutions
                   (meeting_id,committee_id,zone_id,title,description,responsible_agency,responsible_person,due_date,
                    status,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (meeting_id, committee_id, zone_id) + values[1:],
            )
            entity_id = cur.lastrowid
        return "committee_resolution", entity_id, {"title": title, "meeting_id": meeting_id}

    def _apply_client_action(self, committee_id, zone_id, data, mapped_id):
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("عنوان اقدام خالی است.")
        progress = max(0, min(100, int(data.get("progress_percent") or 0)))
        values = (title, data.get("description") or "", data.get("responsible_person") or "",
                  data.get("responsible_office") or "", data.get("planned_start"), data.get("planned_end"),
                  progress, data.get("status") or "برنامه‌ریزی‌شده", data.get("obstacles") or "",
                  data.get("result_summary") or "")
        if mapped_id:
            self.conn.execute(
                """UPDATE neighborhood_actions SET title=?,description=?,responsible_person=?,responsible_office=?,
                   planned_start=?,planned_end=?,progress_percent=?,status=?,obstacles=?,result_summary=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=? AND zone_id=?""",
                values + (int(mapped_id), zone_id),
            )
            entity_id = int(mapped_id)
        else:
            cur = self.conn.execute(
                """INSERT INTO neighborhood_actions
                   (zone_id,title,description,responsible_person,responsible_office,planned_start,planned_end,
                    progress_percent,status,obstacles,result_summary,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (zone_id,) + values,
            )
            entity_id = cur.lastrowid
        self.conn.execute(
            "INSERT OR IGNORE INTO committee_action_links(committee_id,action_id) VALUES (?,?)", (committee_id, entity_id)
        )
        return "action", entity_id, {"title": title, "progress": progress}

    def list_client_imports(self, limit=200) -> List[Dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT id,package_uuid,license_uuid,responsible_name,zone_name,committee_title,report_period,
                      client_created_at,imported_at,status,new_count,changed_count,duplicate_count,conflict_count,
                      accepted_count,rejected_count
               FROM client_import_packages ORDER BY id DESC LIMIT ?""", (int(limit),)
        ).fetchall()
        keys = ["id","package_uuid","license_uuid","responsible_name","zone_name","committee_title","report_period",
                "client_created_at","imported_at","status","new_count","changed_count","duplicate_count",
                "conflict_count","accepted_count","rejected_count"]
        return [dict(zip(keys, r)) for r in rows]
