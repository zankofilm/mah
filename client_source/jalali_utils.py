# -*- coding: utf-8 -*-
"""ابزارهای تاریخ شمسی برای نمایش سراسری نرم‌افزار.

قاعده سامانه:
- تاریخ‌ها در دیتابیس همچنان به‌صورت ISO میلادی ذخیره می‌شوند تا مرتب‌سازی، محاسبات
  و سازگاری نسخه‌های قبلی حفظ شود.
- تمام تاریخ‌های قابل مشاهده و قابل ورود برای کاربر به‌صورت شمسی نمایش داده می‌شوند.
"""

import re
from datetime import date, datetime

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
LATIN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def to_persian_digits(value):
    return str(value if value is not None else "").translate(PERSIAN_DIGITS)


def to_latin_digits(value):
    return str(value if value is not None else "").translate(LATIN_DIGITS)


def _div(a, b):
    return a // b


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + _div(gy2 + 3, 4) - _div(gy2 + 99, 100) + _div(gy2 + 399, 400) + gd + g_d_m[gm - 1]
    jy = -1595 + 33 * _div(days, 12053)
    days %= 12053
    jy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        jy += _div(days - 1, 365)
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + _div(days, 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + _div(days - 186, 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy += 1595
    days = -355668 + 365 * jy + _div(jy, 33) * 8 + _div((jy % 33) + 3, 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += (jm - 7) * 30 + 186
    gy = 400 * _div(days, 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * _div(days, 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * _div(days, 1461)
    days %= 1461
    if days > 365:
        gy += _div(days - 1, 365)
        days = (days - 1) % 365
    gd = days + 1
    leap = gy % 4 == 0 and (gy % 100 != 0 or gy % 400 == 0)
    month_days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    for length in month_days:
        if gd <= length:
            break
        gd -= length
        gm += 1
    return gy, gm, gd


def _parts(value):
    text = to_latin_digits(value).strip().replace(".", "/").replace("-", "/")
    m = re.match(r"^\s*(\d{4})/(\d{1,2})/(\d{1,2})", text)
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def jalali_to_iso(value, required=False):
    """تاریخ شمسی یا میلادی را به YYYY-MM-DD میلادی تبدیل می‌کند."""
    if value is None or str(value).strip() == "":
        if required:
            raise ValueError("تاریخ الزامی است.")
        return None
    parts = _parts(value)
    if not parts:
        raise ValueError("فرمت تاریخ باید به شکل ۱۴۰۵/۰۴/۲۹ باشد.")
    y, m, d = parts
    if y >= 1700:  # ورودی میلادی قدیمی یا داده قبلی
        gy, gm, gd = y, m, d
    else:
        gy, gm, gd = jalali_to_gregorian(y, m, d)
    try:
        date(gy, gm, gd)
    except ValueError as exc:
        raise ValueError("تاریخ واردشده معتبر نیست.") from exc
    return f"{gy:04d}-{gm:02d}-{gd:02d}"


def iso_to_jalali(value, persian_digits=True, separator="/"):
    if value is None or str(value).strip() == "":
        return ""
    text = to_latin_digits(value).strip()
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if not m:
        return str(value)
    y, mo, d = (int(x) for x in m.groups())
    try:
        if y < 1700:
            jy, jm, jd = y, mo, d
        else:
            date(y, mo, d)
            jy, jm, jd = gregorian_to_jalali(y, mo, d)
    except ValueError:
        return str(value)
    out = f"{jy:04d}{separator}{jm:02d}{separator}{jd:02d}"
    return to_persian_digits(out) if persian_digits else out


def format_jalali(value, include_time=True, persian_digits=True):
    """تاریخ یا تاریخ‌زمان ISO را برای نمایش شمسی می‌کند."""
    if value is None or str(value).strip() == "":
        return ""
    text = str(value).strip()
    converted = iso_to_jalali(text, persian_digits=False)
    if converted == text and not re.match(r"^\d{4}[-/.]\d", to_latin_digits(text)):
        return text
    time_part = ""
    if include_time:
        m = re.search(r"[ T](\d{1,2}:\d{2}(?::\d{2})?)", to_latin_digits(text))
        if m:
            time_part = " " + m.group(1)
    out = converted + time_part
    return to_persian_digits(out) if persian_digits else out


_DATE_RE = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T](\d{1,2}:\d{2}(?::\d{2})?))?")


def convert_dates_in_text(value, persian_digits=True):
    """تمام تاریخ‌های میلادی موجود در متن را به شمسی تبدیل می‌کند."""
    if value is None:
        return ""
    text = str(value)

    def repl(match):
        raw = match.group(0)
        return format_jalali(raw, include_time=True, persian_digits=persian_digits)

    return _DATE_RE.sub(repl, text)


def today_jalali(persian_digits=True):
    return iso_to_jalali(date.today().isoformat(), persian_digits=persian_digits)


def now_jalali(persian_digits=True, with_seconds=False):
    fmt = "%H:%M:%S" if with_seconds else "%H:%M"
    value = f"{today_jalali(False)} {datetime.now().strftime(fmt)}"
    return to_persian_digits(value) if persian_digits else value


def jalali_year():
    return int(today_jalali(False)[:4])


def install_openpyxl_jalali_patch():
    """تبدیل خودکار تاریخ‌های متنی هنگام تولید فایل Excel."""
    try:
        from openpyxl.worksheet.worksheet import Worksheet
    except Exception:
        return False
    if getattr(Worksheet, "_jalali_append_patched", False):
        return True
    original = Worksheet.append

    def append(self, iterable):
        if isinstance(iterable, dict):
            iterable = {k: convert_dates_in_text(v) if isinstance(v, str) else v for k, v in iterable.items()}
        else:
            try:
                iterable = [convert_dates_in_text(v) if isinstance(v, str) else v for v in iterable]
            except TypeError:
                pass
        return original(self, iterable)

    Worksheet.append = append
    Worksheet._jalali_append_patched = True
    return True


def install_pptx_jalali_patch():
    """تبدیل خودکار تاریخ‌های متنی در پاراگراف‌ها و کادرهای PowerPoint."""
    try:
        from pptx.text.text import _Paragraph, TextFrame
    except Exception:
        return False
    if getattr(_Paragraph, "_jalali_text_patched", False):
        return True
    p_prop = _Paragraph.text
    tf_prop = TextFrame.text

    def p_set(self, value):
        return p_prop.fset(self, convert_dates_in_text(value))

    def tf_set(self, value):
        return tf_prop.fset(self, convert_dates_in_text(value))

    _Paragraph.text = property(p_prop.fget, p_set, p_prop.fdel, p_prop.__doc__)
    TextFrame.text = property(tf_prop.fget, tf_set, tf_prop.fdel, tf_prop.__doc__)
    _Paragraph._jalali_text_patched = True
    return True
