# -*- coding: utf-8 -*-
"""کنترل سلامت، بازیابی بحران و بسته پشتیبانی نسخه عملیاتی."""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from runtime_paths import (
    get_data_dir, get_logs_dir, get_support_dir, get_temp_dir,
    ensure_runtime_dirs, resource_dir,
)
from version import APP_NAME, APP_VERSION


class RuntimeSessionGuard:
    """تشخیص بسته‌شدن غیرعادی برنامه بدون ذخیره داده حساس."""
    def __init__(self):
        ensure_runtime_dirs()
        self.path = Path(get_data_dir()) / "runtime_session.json"
        self.previous_unclean = False
        self.previous = {}

    def begin(self):
        if self.path.exists():
            try:
                self.previous = json.loads(self.path.read_text(encoding="utf-8"))
                self.previous_unclean = self.previous.get("status") == "running"
            except Exception:
                self.previous_unclean = True
        payload = {
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "pid": os.getpid(),
            "app_version": APP_VERSION,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.previous_unclean

    def mark_clean(self):
        try:
            payload = {
                "status": "clean",
                "closed_at": datetime.now().isoformat(timespec="seconds"),
                "pid": os.getpid(),
                "app_version": APP_VERSION,
            }
            self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass


def _check(name, status, message, details=None):
    return {
        "name": name,
        "status": status,  # ok / warning / error
        "message": message,
        "details": details or {},
    }


def _latest_backup(db):
    rows = db.list_registered_backups(limit=100)
    for row in rows:
        path = row.get("file_path")
        if path and os.path.exists(path) and row.get("validation_status") == "سالم":
            return row
    return None


def run_health_checks(db):
    """کنترل‌های بدون تغییر داده؛ مناسب اجرا در شروع یا مرکز پشتیبانی."""
    ensure_runtime_dirs()
    checks = []
    data_dir = Path(get_data_dir())

    # نوشتن‌پذیری مسیر داده
    try:
        probe = data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append(_check("مسیر داده", "ok", "مسیر داده قابل نوشتن است.", {"path": str(data_dir)}))
    except Exception as exc:
        checks.append(_check("مسیر داده", "error", "مسیر داده قابل نوشتن نیست.", {"error": str(exc), "path": str(data_dir)}))

    # سلامت SQLite و کلید خارجی
    try:
        health = db.database_health()
        status = "ok" if health["integrity_ok"] and health["quick_ok"] and health["foreign_key_errors"] == 0 else "error"
        checks.append(_check(
            "دیتابیس", status,
            "ساختار دیتابیس سالم است." if status == "ok" else "دیتابیس یا روابط آن نیازمند بررسی است.",
            health,
        ))
    except Exception as exc:
        checks.append(_check("دیتابیس", "error", "بررسی سلامت دیتابیس ناموفق بود.", {"error": str(exc)}))

    # فضای دیسک
    try:
        usage = shutil.disk_usage(data_dir)
        free_mb = usage.free // (1024 * 1024)
        status = "ok" if free_mb >= 1024 else ("warning" if free_mb >= 250 else "error")
        checks.append(_check("فضای ذخیره‌سازی", status, f"فضای آزاد: {free_mb:,} مگابایت", {"free_bytes": usage.free}))
    except Exception as exc:
        checks.append(_check("فضای ذخیره‌سازی", "warning", "فضای دیسک قابل اندازه‌گیری نبود.", {"error": str(exc)}))

    # تازگی بکاپ
    try:
        backup = _latest_backup(db)
        if not backup:
            checks.append(_check("بکاپ", "error", "هیچ بکاپ سالم ثبت‌شده‌ای یافت نشد."))
        else:
            created = datetime.fromisoformat(str(backup["created_at"]).replace("Z", "+00:00"))
            age = datetime.now() - created.replace(tzinfo=None)
            status = "ok" if age <= timedelta(days=2) else ("warning" if age <= timedelta(days=7) else "error")
            checks.append(_check("بکاپ", status, f"آخرین بکاپ سالم مربوط به {age.days} روز قبل است.", {"path": backup["file_path"]}))
    except Exception as exc:
        checks.append(_check("بکاپ", "warning", "وضعیت بکاپ قابل بررسی نبود.", {"error": str(exc)}))

    # فایل‌های Leaflet
    try:
        from asset_manager import leaflet_assets_available
        available = leaflet_assets_available()
        checks.append(_check("موتور نقشه آفلاین", "ok" if available else "warning",
                             "فایل‌های آفلاین آماده‌اند." if available else "بعضی فایل‌های Leaflet موجود نیستند."))
    except Exception as exc:
        checks.append(_check("موتور نقشه آفلاین", "warning", "بررسی موتور آفلاین ناموفق بود.", {"error": str(exc)}))

    # پیوست‌های گمشده
    try:
        rows = db.conn.execute("SELECT stored_path FROM document_attachments").fetchall()
        missing = sum(1 for row in rows if row[0] and not os.path.exists(row[0]))
        checks.append(_check("پیوست‌ها", "ok" if missing == 0 else "warning",
                             "تمام پیوست‌ها در دسترس‌اند." if missing == 0 else f"{missing} پیوست در دیسک یافت نشد.",
                             {"missing": missing, "total": len(rows)}))
    except Exception as exc:
        checks.append(_check("پیوست‌ها", "warning", "بررسی پیوست‌ها ناموفق بود.", {"error": str(exc)}))

    # نسخه ساختار
    schema_version = db.get_schema_version()
    checks.append(_check("نسخه ساختار", "ok" if schema_version >= 700 else "warning",
                         f"نسخه ساختار دیتابیس: {schema_version}"))
    return checks


def overall_health(checks):
    statuses = {item.get("status") for item in checks}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def cleanup_runtime_files(days=14):
    cutoff = datetime.now().timestamp() - max(1, int(days)) * 86400
    removed = []
    for root in (Path(get_temp_dir()), Path(get_support_dir())):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                try:
                    path.unlink()
                    removed.append(str(path))
                except OSError:
                    pass
    return removed


def recovery_drill(db, destination_dir=None):
    """بکاپ می‌سازد و بدون جایگزینی دیتابیس اصلی، قابلیت بازیابی را آزمایش می‌کند."""
    destination_dir = Path(destination_dir or tempfile.mkdtemp(prefix="javanrood_recovery_"))
    destination_dir.mkdir(parents=True, exist_ok=True)
    backup_path = destination_dir / f"recovery_drill_{datetime.now():%Y%m%d_%H%M%S}.db"
    db.create_backup(str(backup_path), backup_type="recovery-test", reason="آزمون بازیابی")
    valid, message = db.validate_database_file(str(backup_path))
    if not valid:
        raise RuntimeError(message)

    source_counts = {}
    restored_counts = {}
    tables = ["zones", "streets", "places", "app_users", "neighborhood_issues", "project_portfolio"]
    test_conn = sqlite3.connect(str(backup_path))
    try:
        for table in tables:
            try:
                source_counts[table] = int(db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                restored_counts[table] = int(test_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                continue
        integrity = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        test_conn.close()
    passed = integrity == "ok" and source_counts == restored_counts
    return {
        "passed": passed,
        "backup_path": str(backup_path),
        "integrity": integrity,
        "source_counts": source_counts,
        "restored_counts": restored_counts,
    }


def mirror_latest_backup(db, destination_dir):
    """آخرین بکاپ سالم را به مسیر دوم کپی و هش آن را کنترل می‌کند."""
    backup = _latest_backup(db)
    if not backup:
        raise RuntimeError("بکاپ سالمی برای انتقال وجود ندارد.")
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    src = Path(backup["file_path"])
    dst = destination / src.name
    shutil.copy2(src, dst)
    if db._file_sha256(str(src)) != db._file_sha256(str(dst)):
        dst.unlink(missing_ok=True)
        raise RuntimeError("کنترل صحت نسخه دوم بکاپ ناموفق بود.")
    return str(dst)


def create_support_bundle(db, output_path=None, include_database=False):
    """بسته تشخیص مشکل بدون رمز و اطلاعات شخصی؛ دیتابیس فقط با درخواست صریح افزوده می‌شود."""
    ensure_runtime_dirs()
    output_path = output_path or str(Path(get_support_dir()) / f"support_{datetime.now():%Y%m%d_%H%M%S}.zip")
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    checks = run_health_checks(db)
    stats = db.get_system_stats()
    safe_stats = {k: v for k, v in stats.items() if isinstance(v, (int, float, str, bool))}
    environment = {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "schema_version": db.get_schema_version(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "os": platform.platform(),
        "python": sys.version,
        "frozen": bool(getattr(sys, "frozen", False)),
        "data_dir": get_data_dir(),
        "resource_dir": str(resource_dir()),
    }
    manifest = {
        "contains_database": bool(include_database),
        "privacy_note": "این بسته به‌طور پیش‌فرض فاقد رمز عبور، متن مکاتبات و مشخصات شهروندان است.",
        "health": overall_health(checks),
    }

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.writestr("environment.json", json.dumps(environment, ensure_ascii=False, indent=2))
        zf.writestr("health.json", json.dumps(checks, ensure_ascii=False, indent=2, default=str))
        zf.writestr("system_stats.json", json.dumps(safe_stats, ensure_ascii=False, indent=2, default=str))
        zf.writestr("migration_history.json", json.dumps(db.get_migration_history(), ensure_ascii=False, indent=2, default=str))
        log_dir = Path(get_logs_dir())
        for log in sorted(log_dir.glob("app.log*")):
            if log.is_file():
                zf.write(log, f"logs/{log.name}")
        if include_database:
            with tempfile.TemporaryDirectory() as temp:
                db_copy = Path(temp) / "javanrood_support.db"
                db.create_backup(str(db_copy), backup_type="support", reason="بسته پشتیبانی")
                zf.write(db_copy, "database/javanrood.db")
    return output_path
