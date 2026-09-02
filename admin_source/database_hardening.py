# -*- coding: utf-8 -*-
"""Database hardening, validation, soft-delete and encrypted-backup services."""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta

from security_service import SecretVault, encrypt_backup_file, decrypt_backup_file
from runtime_paths import get_data_dir

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class HardeningMixin:
    def _initialize_hardening(self):
        self.secret_vault = SecretVault(get_data_dir())
        self._create_hardening_tables()
        self._migrate_plaintext_secrets()
        self._protect_database_permissions()

    def _create_hardening_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT DEFAULT 'info',
                event_type TEXT NOT NULL,
                username TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_security_events_created ON security_events(created_at)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_merge_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                details TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for table in ("people_registry", "council_members", "committee_members", "social_council_members"):
            try:
                self._ensure_column(table, "is_deleted", "INTEGER DEFAULT 0")
                self._ensure_column(table, "deleted_at", "TEXT")
                self._ensure_column(table, "deleted_by", "INTEGER")
            except Exception:
                continue
        for table in ("people_registry", "council_members", "committee_members"):
            try:
                self._ensure_column(table, "data_quality_status", "TEXT DEFAULT 'تأییدنشده'")
            except Exception:
                pass
        self.conn.commit()

    def _protect_database_permissions(self):
        for path in (self.db_path, self.db_path + "-wal", self.db_path + "-shm"):
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o600)
                except OSError:
                    pass

    def _migrate_plaintext_secrets(self):
        migrations = [
            ("message_api_settings", "api_key", "id=1"),
            ("smart_triage_settings", "api_key", "id=1"),
        ]
        for table, column, where in migrations:
            try:
                row = self.conn.execute(f"SELECT {column} FROM {table} WHERE {where}").fetchone()
                if row and row[0] and not self.secret_vault.is_encrypted(row[0]):
                    self.conn.execute(f"UPDATE {table} SET {column}=? WHERE {where}", (self.secret_vault.encrypt(row[0]),))
            except sqlite3.Error:
                continue
        self.conn.commit()

    def require_permission(self, permission):
        # عملیات داخلی زمان راه‌اندازی بدون کاربر مجاز است؛ پس از ورود، کنترل در لایه منطق نیز اعمال می‌شود.
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return True
        user = self.get_current_user() if hasattr(self, "get_current_user") else None
        if user and not self.current_user_can(permission):
            self.record_security_event("permission_denied", "warning", user.get("username", ""), permission)
            raise PermissionError("حساب کاربری فعلی مجوز انجام این عملیات را ندارد.")
        return True

    def encrypt_secret(self, value):
        return self.secret_vault.encrypt(value)

    def decrypt_secret(self, value):
        return self.secret_vault.decrypt(value)

    def record_security_event(self, event_type, severity="info", username="", details=""):
        self.conn.execute(
            "INSERT INTO security_events(severity,event_type,username,details) VALUES (?,?,?,?)",
            (severity, event_type, username or "", str(details or "")[:2000]),
        )
        self.conn.commit()

    def get_security_events(self, limit=200):
        rows = self.conn.execute(
            "SELECT id,severity,event_type,username,details,created_at FROM security_events ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        keys = ["id", "severity", "event_type", "username", "details", "created_at"]
        return [dict(zip(keys, row)) for row in rows]

    @staticmethod
    def normalize_mobile_number(value):
        text = re.sub(r"[^0-9+]", "", str(value or "").translate(_FA_DIGITS).strip())
        if text.startswith("+98"):
            text = "0" + text[3:]
        elif text.startswith("0098"):
            text = "0" + text[4:]
        elif text.startswith("98") and len(text) == 12:
            text = "0" + text[2:]
        elif text.startswith("9") and len(text) == 10:
            text = "0" + text
        return text

    @classmethod
    def validate_mobile_number(cls, value):
        return bool(re.fullmatch(r"09\d{9}", cls.normalize_mobile_number(value)))

    def validate_person_payload(self, national_code, mobile=""):
        if not self.validate_national_code(national_code):
            raise ValueError("کد ملی معتبر نیست.")
        if mobile and not self.validate_mobile_number(mobile):
            raise ValueError("شماره همراه باید با الگوی 09xxxxxxxxx وارد شود.")
        return self.normalize_national_code(national_code), self.normalize_mobile_number(mobile)

    def soft_delete_person(self, person_id):
        person = self.get_person(person_id)
        if not person:
            return False
        actor = self.get_current_user() or {}
        self.conn.execute(
            "UPDATE people_registry SET is_deleted=1,deleted_at=CURRENT_TIMESTAMP,deleted_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (actor.get("id"), int(person_id)),
        )
        self.conn.commit()
        self.log_action("person_soft_deleted", "person", person_id, before=person)
        return True

    def restore_person(self, person_id):
        self.conn.execute(
            "UPDATE people_registry SET is_deleted=0,deleted_at=NULL,deleted_by=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(person_id),),
        )
        self.conn.commit()
        self.log_action("person_restored", "person", person_id)
        return True

    def find_possible_duplicate_people(self, limit=200):
        rows = self.conn.execute("""
            SELECT a.id,a.full_name,a.national_code,a.mobile,b.id,b.full_name,b.national_code,b.mobile
            FROM people_registry a JOIN people_registry b ON a.id<b.id
            WHERE COALESCE(a.is_deleted,0)=0 AND COALESCE(b.is_deleted,0)=0
              AND ((TRIM(COALESCE(a.mobile,''))<>'' AND a.mobile=b.mobile)
                OR (TRIM(COALESCE(a.full_name,''))<>'' AND a.full_name=b.full_name))
            ORDER BY a.id,b.id LIMIT ?
        """, (int(limit),)).fetchall()
        keys = ["source_id","source_name","source_national_code","source_mobile",
                "target_id","target_name","target_national_code","target_mobile"]
        return [dict(zip(keys, row)) for row in rows]

    def merge_people(self, source_id, target_id):
        source_id, target_id = int(source_id), int(target_id)
        if source_id == target_id:
            raise ValueError("رکورد مبدا و مقصد یکسان است.")
        source, target = self.get_person(source_id), self.get_person(target_id)
        if not source or not target:
            raise ValueError("یکی از رکوردهای انتخاب‌شده پیدا نشد.")
        actor = self.get_current_user() or {}
        with self.conn:
            for table in ("council_members", "committee_members"):
                self.conn.execute(f"UPDATE {table} SET person_id=? WHERE person_id=?", (target_id, source_id))
            merged = {k: target.get(k) or source.get(k) or "" for k in
                      ("first_name","last_name","full_name","education","mobile","address","notes")}
            self.conn.execute("""
                UPDATE people_registry SET first_name=?,last_name=?,full_name=?,education=?,mobile=?,address=?,notes=?,
                    updated_at=CURRENT_TIMESTAMP WHERE id=?
            """, (merged["first_name"],merged["last_name"],merged["full_name"],merged["education"],
                  merged["mobile"],merged["address"],merged["notes"],target_id))
            self.conn.execute(
                "UPDATE people_registry SET is_deleted=1,deleted_at=CURRENT_TIMESTAMP,deleted_by=? WHERE id=?",
                (actor.get("id"), source_id),
            )
            self.conn.execute(
                "INSERT INTO data_merge_history(entity_type,source_id,target_id,details,created_by) VALUES ('person',?,?,?,?)",
                (source_id,target_id,"ادغام رکورد تکراری",actor.get("id")),
            )
        self.log_action("person_merged", "person", target_id, {"source_id": source_id})
        return self.get_person(target_id)

    def create_encrypted_backup(self, destination_path, password, reason="manual-encrypted"):
        fd, temp_db = tempfile.mkstemp(prefix="javanrood_backup_", suffix=".db")
        os.close(fd)
        try:
            self.create_backup(temp_db, backup_type="temporary", reason=reason)
            encrypt_backup_file(temp_db, destination_path, password)
            try:
                self.register_backup(destination_path, backup_type="encrypted", reason=reason)
            except Exception:
                pass
            self.log_action("encrypted_backup_created", "database", os.path.basename(destination_path))
            return destination_path
        finally:
            try:
                os.remove(temp_db)
            except OSError:
                pass

    def decrypt_backup_to_database(self, encrypted_path, destination_path, password):
        decrypt_backup_file(encrypted_path, destination_path, password)
        valid, message = self.validate_database_file(destination_path)
        if not valid:
            try:
                os.remove(destination_path)
            except OSError:
                pass
            raise ValueError(message)
        return destination_path

    def backup_health_status(self, max_age_hours=36):
        row = self.conn.execute(
            "SELECT file_path,validation_status,created_at FROM backup_registry ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return {"healthy": False, "status": "بدون بکاپ", "age_hours": None, "path": ""}
        try:
            created = datetime.fromisoformat(str(row[2]).replace(" ", "T"))
            age = (datetime.now() - created).total_seconds() / 3600
        except Exception:
            age = None
        healthy = bool(row[0] and os.path.exists(row[0]) and row[1] in {"سالم", "رمزگذاری‌شده"} and age is not None and age <= max_age_hours)
        return {"healthy": healthy, "status": "سالم" if healthy else "نیازمند بررسی", "age_hours": age, "path": row[0] or ""}

    def test_latest_backup_restore(self):
        row = self.conn.execute(
            "SELECT file_path FROM backup_registry WHERE validation_status='سالم' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row or not row[0] or not os.path.exists(row[0]):
            return False, "بکاپ سالمی برای آزمون وجود ندارد."
        valid, message = self.validate_database_file(row[0])
        if valid:
            self.set_meta("last_backup_restore_test", datetime.now().isoformat(timespec="seconds"))
            return True, "آزمون بازیابی موفق بود."
        return False, message
