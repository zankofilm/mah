# -*- coding: utf-8 -*-
"""تایپوگرافی حرفه‌ای و سازگار با فارسی در Windows و macOS.

هیچ فونتی همراه برنامه توزیع نمی‌شود. در صورت وجود فونت‌های مجاز در پوشه
``fonts`` یا نصب بودن آن‌ها روی سیستم، بهترین گزینه به‌صورت خودکار انتخاب می‌شود.
"""

from __future__ import annotations

import os
from pathlib import Path

from PyQt5.QtGui import QFont, QFontDatabase

from design_system import PROFILES, PROFILE_COMFORTABLE

BASE_DIR = Path(__file__).resolve().parent
LOCAL_FONT_DIR = BASE_DIR / "fonts"

# ترتیب بر اساس خوانایی در رابط کاربری، پشتیبانی از ارقام فارسی و کیفیت نمایش در Windows.
PREFERRED_PERSIAN_FONTS = (
    "Vazirmatn FD",
    "Vazirmatn",
    "Estedad",
    "Peyda",
    "Dana FaNum",
    "Dana",
    "Yekan Bakh FaNum",
    "Yekan Bakh",
    "IRANYekanXFaNum",
    "IRANYekanX",
    "IRANSansXFaNum",
    "IRANSansX",
    "Shabnam",
    "Sahel",
    "Samim",
    "Segoe UI",
    "Tahoma",
)

_REGISTERED_LOCAL_FONTS = False
_CACHED_FAMILY = None


def _register_local_fonts():
    """فونت‌های قانونیِ افزوده‌شده توسط مدیر سامانه را در زمان اجرا ثبت می‌کند."""
    global _REGISTERED_LOCAL_FONTS
    if _REGISTERED_LOCAL_FONTS:
        return
    _REGISTERED_LOCAL_FONTS = True
    if not LOCAL_FONT_DIR.is_dir():
        return
    for path in sorted(LOCAL_FONT_DIR.iterdir()):
        if path.suffix.lower() not in {".ttf", ".otf", ".ttc"}:
            continue
        try:
            QFontDatabase.addApplicationFont(os.fspath(path))
        except Exception:
            # خرابی یک فایل فونت نباید مانع اجرای برنامه شود.
            continue


def resolve_ui_font_family():
    """بهترین فونت فارسی موجود را با fallback مطمئن انتخاب می‌کند."""
    global _CACHED_FAMILY
    if _CACHED_FAMILY:
        return _CACHED_FAMILY

    _register_local_fonts()
    try:
        installed = {name.casefold(): name for name in QFontDatabase().families()}
    except Exception:
        installed = {}

    for candidate in PREFERRED_PERSIAN_FONTS:
        match = installed.get(candidate.casefold())
        if match:
            _CACHED_FAMILY = match
            return match

    _CACHED_FAMILY = "Tahoma"
    return _CACHED_FAMILY


def make_ui_font(point_size=10.5, weight=QFont.Normal):
    """ساخت فونت استاندارد برای اجزای اختصاصی رابط."""
    font = QFont(resolve_ui_font_family())
    font.setPointSizeF(float(point_size))
    font.setWeight(weight)
    font.setKerning(True)
    font.setStyleStrategy(QFont.PreferAntialias)
    try:
        font.setHintingPreference(QFont.PreferFullHinting)
    except Exception:
        pass
    return font


def apply_application_typography(app):
    """فونت پایه برنامه را روی تمام پنجره‌ها و دیالوگ‌ها اعمال می‌کند."""
    family = resolve_ui_font_family()
    default_metrics = PROFILES[PROFILE_COMFORTABLE]
    font = make_ui_font(default_metrics.base_font_pt, QFont.Normal)
    app.setFont(font)
    app.setProperty("uiFontFamily", family)
    app.setProperty("uiFontBasePointSize", default_metrics.base_font_pt)
    app.setProperty("uiTypographyProfile", "professional-fa-responsive")
    return family
