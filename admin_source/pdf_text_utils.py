# -*- coding: utf-8 -*-
"""
ابزار کمکی برای نمایش صحیح متن فارسی در گزارش‌های PDF.
متن فارسی/عربی برای نمایش درست در reportlab باید:
  1) حروف به‌هم متصل شوند (reshape)
  2) ترتیب راست‌به‌چپ اعمال شود (bidi)
در صورت نبود کتابخانه‌های arabic_reshaper و python-bidi،
متن خام (بدون شکل‌دهی) برگردانده می‌شود تا برنامه از کار نیفتد؛
در این حالت فقط نمایش گرافیکی متن فارسی در PDF درست نخواهد بود.
"""

from jalali_utils import convert_dates_in_text

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _SHAPING_AVAILABLE = True
except ImportError:
    _SHAPING_AVAILABLE = False


def shape_fa(text):
    """متن فارسی را برای نمایش صحیح در PDF آماده می‌کند."""
    if not text:
        return ""
    text = convert_dates_in_text(str(text))
    if not _SHAPING_AVAILABLE:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


def shaping_available():
    return _SHAPING_AVAILABLE
