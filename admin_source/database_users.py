# -*- coding: utf-8 -*-
"""User accounts, authentication and role administration."""
import os
import sqlite3
from datetime import datetime, timedelta
from security_service import validate_password_policy


class UserSecurityMixin:
    # ---------------- Users, Roles and Security ----------------
    def _ensure_default_users(self):
        """انتقال غیرمخرب حساب مدیر قدیمی به جدول کاربران نسخه ۶.۳."""
        row = self.conn.execute(
            "SELECT username, password_hash, COALESCE(must_change_password,1) FROM admin_settings WHERE id=1"
        ).fetchone()
        if not row:
            return
        username, password_hash, must_change = row
        existing = self.conn.execute("SELECT id FROM app_users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
        if existing is None:
            self.conn.execute(
                """INSERT OR IGNORE INTO app_users
                   (username, full_name, password_hash, role, is_active, must_change_password)
                   VALUES (?, ?, ?, 'admin', 1, ?)""",
                (username, "مدیر سامانه", password_hash, int(bool(must_change))),
            )
            self.conn.commit()

    def authenticate_user(self, username, password):
        """ورود کاربران با قفل موقت پس از پنج تلاش ناموفق."""
        username = (username or "").strip()
        row = self.conn.execute(
            """SELECT id, username, full_name, password_hash, role, mobile, is_active,
                      must_change_password, failed_attempts, locked_until
               FROM app_users WHERE username=? COLLATE NOCASE""",
            (username,),
        ).fetchone()
        if not row or not row[6]:
            return None
        user_id, stored_username, full_name, password_hash, role, mobile, _, must_change, failed, locked_until = row
        if locked_until:
            try:
                if datetime.fromisoformat(locked_until) > datetime.now():
                    return None
            except Exception:
                pass
        if not self._verify_password(password, password_hash):
            failed = int(failed or 0) + 1
            lock_value = None
            if failed >= 5:
                lock_value = (datetime.now() + timedelta(minutes=15)).isoformat(timespec="seconds")
                failed = 0
            self.conn.execute(
                "UPDATE app_users SET failed_attempts=?, locked_until=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (failed, lock_value, user_id),
            )
            self.conn.commit()
            self.log_action("login_failed", "user", user_id, {"username": stored_username})
            try:
                self.record_security_event("login_failed", "warning", stored_username, "تلاش ناموفق برای ورود")
                if lock_value:
                    self.record_security_event("account_locked", "critical", stored_username, "قفل ۱۵ دقیقه‌ای پس از پنج تلاش ناموفق")
            except Exception:
                pass
            return None
        if not password_hash.startswith("pbkdf2_sha256$"):
            password_hash = self._hash_password(password)
            self.conn.execute("UPDATE app_users SET password_hash=? WHERE id=?", (password_hash, user_id))
        self.conn.execute(
            """UPDATE app_users SET failed_attempts=0, locked_until=NULL,
               last_login_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (user_id,),
        )
        self.conn.commit()
        user = {
            "id": user_id, "username": stored_username, "full_name": full_name,
            "role": role, "mobile": mobile, "must_change_password": bool(must_change),
        }
        self.set_current_user(user)
        self.log_action("login_success", "user", user_id, {"role": role})
        return user

    def list_users(self, include_inactive=True):
        sql = """SELECT id, username, full_name, role, mobile, is_active, must_change_password,
                        failed_attempts, locked_until, last_login_at, created_at, updated_at
                 FROM app_users"""
        if not include_inactive:
            sql += " WHERE is_active=1"
        sql += " ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, full_name"
        keys = ["id", "username", "full_name", "role", "mobile", "is_active",
                "must_change_password", "failed_attempts", "locked_until", "last_login_at",
                "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql).fetchall()]

    def get_user(self, user_id):
        for user in self.list_users(include_inactive=True):
            if user["id"] == int(user_id):
                return user
        return None

    def create_user(self, username, full_name, password, role="viewer", mobile=None,
                    is_active=True, must_change_password=True):
        self.require_permission("system_settings")
        from access_control import ROLE_DEFINITIONS
        username = (username or "").strip()
        full_name = (full_name or "").strip()
        if not username or not full_name:
            raise ValueError("نام کاربری و نام کامل الزامی است.")
        valid_password, password_message = validate_password_policy(password, username)
        if not valid_password:
            raise ValueError(password_message)
        if role not in ROLE_DEFINITIONS:
            raise ValueError("نقش کاربری معتبر نیست.")
        try:
            cur = self.conn.execute(
                """INSERT INTO app_users
                   (username, full_name, password_hash, role, mobile, is_active, must_change_password)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (username, full_name, self._hash_password(password), role, mobile,
                 int(bool(is_active)), int(bool(must_change_password))),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("این نام کاربری قبلاً ثبت شده است.") from exc
        user_id = cur.lastrowid
        self.log_action("user_created", "user", user_id, {"username": username, "role": role})
        return user_id

    def update_user(self, user_id, **fields):
        self.require_permission("system_settings")
        current = self.get_user(user_id)
        if not current:
            raise ValueError("کاربر پیدا نشد.")
        allowed = {"username", "full_name", "role", "mobile", "is_active", "must_change_password"}
        values = {k: v for k, v in fields.items() if k in allowed}
        if "username" in values:
            values["username"] = (values["username"] or "").strip()
            if not values["username"]:
                raise ValueError("نام کاربری خالی است.")
        if "full_name" in values:
            values["full_name"] = (values["full_name"] or "").strip()
            if not values["full_name"]:
                raise ValueError("نام کامل خالی است.")
        if "role" in values:
            from access_control import ROLE_DEFINITIONS
            if values["role"] not in ROLE_DEFINITIONS:
                raise ValueError("نقش کاربری معتبر نیست.")
        if "is_active" in values:
            values["is_active"] = int(bool(values["is_active"]))
        if "must_change_password" in values:
            values["must_change_password"] = int(bool(values["must_change_password"]))
        # جلوگیری از حذف یا تنزل آخرین مدیر فعال سامانه
        final_role = values.get("role", current.get("role"))
        final_active = values.get("is_active", current.get("is_active"))
        if current.get("role") == "admin" and (final_role != "admin" or not final_active):
            active_admins = self.conn.execute(
                "SELECT COUNT(*) FROM app_users WHERE role='admin' AND is_active=1"
            ).fetchone()[0]
            if active_admins <= 1:
                raise ValueError("آخرین مدیر فعال سامانه را نمی‌توان غیرفعال یا به نقش دیگری منتقل کرد.")
        if not values:
            return current
        sql = ", ".join(f"{key}=?" for key in values)
        try:
            self.conn.execute(
                f"UPDATE app_users SET {sql}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                list(values.values()) + [int(user_id)],
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("این نام کاربری قبلاً ثبت شده است.") from exc
        updated = self.get_user(user_id)
        self.log_action("user_updated", "user", user_id, before=current, after=updated)
        return updated

    def set_user_password(self, user_id, new_password, must_change_password=False):
        current = self.get_current_user() or {}
        if current.get("id") != int(user_id):
            self.require_permission("system_settings")
        user = self.get_user(user_id)
        valid_password, password_message = validate_password_policy(new_password, (user or {}).get("username", ""))
        if not valid_password:
            raise ValueError(password_message)
        if not user:
            raise ValueError("کاربر پیدا نشد.")
        self.conn.execute(
            """UPDATE app_users SET password_hash=?, must_change_password=?, failed_attempts=0,
               locked_until=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (self._hash_password(new_password), int(bool(must_change_password)), int(user_id)),
        )
        self.conn.commit()
        if user.get("role") == "admin":
            self.clear_initial_credentials_file()
        self.log_action("password_changed", "user", user_id)

    def verify_user_password(self, user_id, password):
        row = self.conn.execute("SELECT password_hash FROM app_users WHERE id=?", (int(user_id),)).fetchone()
        return bool(row and self._verify_password(password, row[0]))

    def deactivate_user(self, user_id):
        user = self.get_user(user_id)
        if not user:
            return False
        if user.get("role") == "admin":
            count = self.conn.execute("SELECT COUNT(*) FROM app_users WHERE role='admin' AND is_active=1").fetchone()[0]
            if count <= 1:
                raise ValueError("آخرین مدیر فعال سامانه را نمی‌توان غیرفعال کرد.")
        self.update_user(user_id, is_active=False)
        return True

