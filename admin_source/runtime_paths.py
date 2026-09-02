# -*- coding: utf-8 -*-
"""مسیرهای خواندنی/نوشتنی سامانه برای حالت توسعه، پرتابل و نصب‌شده ویندوز."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_DATA_FOLDER = "JavanroodNeighborhoodManagement"
SOURCE_DIR = Path(__file__).resolve().parent


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """مسیر منابع فقط‌خواندنی بسته PyInstaller یا سورس."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base).resolve() if base else SOURCE_DIR


def executable_dir() -> Path:
    return Path(sys.executable).resolve().parent if is_frozen() else SOURCE_DIR


def _default_data_dir() -> Path:
    override = os.environ.get("JAVANROOD_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    portable = os.environ.get("JAVANROOD_PORTABLE", "").strip().lower() in {"1", "true", "yes", "on"}
    if portable or not is_frozen():
        return SOURCE_DIR / "data"

    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / APP_DATA_FOLDER
    xdg = os.environ.get("XDG_DATA_HOME")
    return Path(xdg).expanduser() / APP_DATA_FOLDER if xdg else Path.home() / ".local" / "share" / APP_DATA_FOLDER


DATA_DIR = _default_data_dir()


def ensure_runtime_dirs() -> Path:
    for name in ("logs", "reports", "automatic_backups", "attachments", "temp", "support", "vendor"):
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def get_data_dir() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR)


def get_persistent_security_dir() -> str:
    """مسیر پایدار کلیدهای امنیتی؛ مستقل از محل استخراج یا جابه‌جایی سورس."""
    override = os.environ.get("JAVANROOD_SECURITY_DIR")
    if override:
        path = Path(override).expanduser().resolve()
    elif os.environ.get("JAVANROOD_PORTABLE", "").strip().lower() in {"1", "true", "yes", "on"}:
        path = DATA_DIR / "security"
    elif os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        path = Path(root) / APP_DATA_FOLDER / "security"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_DATA_FOLDER / "security"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
        path = base / APP_DATA_FOLDER / "security"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_client_exchange_key_dir() -> str:
    """کلید ادمین را یک‌بار از مسیر قدیمی مهاجرت و سپس در مسیر پایدار نگهداری می‌کند."""
    destination = Path(get_persistent_security_dir()) / "client_exchange"
    legacy = Path(get_data_dir()) / "security" / "client_exchange"
    if not destination.exists() and legacy.exists():
        shutil.copytree(legacy, destination, dirs_exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    return str(destination)


def get_database_path() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR / "javanrood.db")


def get_logs_dir() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR / "logs")


def get_reports_dir() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR / "reports")


def get_temp_dir() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR / "temp")


def get_support_dir() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR / "support")


def get_runtime_vendor_dir() -> str:
    ensure_runtime_dirs()
    return str(DATA_DIR / "vendor" / "leaflet")


def migrate_legacy_runtime_data() -> list[str]:
    """در نصب‌شده، داده‌های پرتابل کنار برنامه را فقط در نبود مقصد جدید منتقل می‌کند."""
    ensure_runtime_dirs()
    copied: list[str] = []
    if not is_frozen():
        return copied

    candidates = [executable_dir() / "data", resource_dir() / "data"]
    for legacy in candidates:
        if not legacy.exists() or legacy.resolve() == DATA_DIR.resolve():
            continue
        for rel in ("javanrood.db", "javanrood.db-wal", "javanrood.db-shm"):
            src, dst = legacy / rel, DATA_DIR / rel
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)
                copied.append(str(dst))
        for folder in ("attachments", "automatic_backups"):
            src_dir, dst_dir = legacy / folder, DATA_DIR / folder
            if src_dir.exists() and not any(dst_dir.iterdir()):
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
                copied.append(str(dst_dir))
        if copied:
            break
    return copied
