# -*- coding: utf-8 -*-
"""تنظیمات اختصاصی اجرای نسخه ویندوز."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_USER_MODEL_ID = "JavanroodGovernorate.NeighborhoodManagement.7.2"


def configure_windows_process() -> None:
    """شناسه برنامه و تنظیمات سازگار با ویندوز را پیش از ساخت QApplication اعمال می‌کند."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


def windows_data_directory() -> Path:
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(root) / "JavanroodNeighborhoodManagement"


def is_supported_windows() -> bool:
    if os.name != "nt":
        return False
    try:
        return sys.getwindowsversion().major >= 10
    except Exception:
        return True
