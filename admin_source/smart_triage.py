# -*- coding: utf-8 -*-
"""
موتور پیشنهاد هوشمند دسته‌بندی و فوریت برای متون فارسی مربوط به مسائل و
درخواست‌های شهروندی.

دو حالت کار می‌کند:
  1) حالت پیش‌فرض و همیشه‌فعال: تحلیل کلیدواژه‌ای آفلاین (بدون نیاز به
     اینترنت یا هیچ سرویس خارجی). این حالت تضمین می‌کند برنامه بدون
     اتصال شبکه هم قابلیت پیشنهاد را از دست ندهد — سازگار با معماری
     آفلاین‌محور بقیه پروژه.
  2) حالت اختیاری: در صورتی که کاربر کلید API یک سرویس هوش مصنوعی را در
     تنظیمات سیستم وارد کرده باشد و اتصال اینترنت برقرار باشد، پیشنهاد
     دقیق‌تری از طریق آن سرویس گرفته می‌شود. در غیر این صورت (نبود کلید،
     نبود اینترنت، یا خطای هر نوع) به‌طور خاموش (silent) به حالت ۱ برمی‌گردد
     — یعنی این قابلیت هرگز کاربر را با خطای شبکه معطل نمی‌کند.

نکته حریم خصوصی: این ماژول عمداً تنها متن آزاد شرح مسئله/درخواست را به
سرویس بیرونی می‌فرستد؛ نام شهروند، شماره موبایل، مختصات دقیق و سایر
اطلاعات هویتی هرگز به تابع ارسال به API پاس داده نمی‌شوند.
"""
from __future__ import annotations

import json
import re

try:
    import requests
except ImportError:  # requests از قبل در requirements.txt پروژه است
    requests = None


# ---------------------------------------------------------------------------
# حالت ۱: تحلیل کلیدواژه‌ای آفلاین
# ---------------------------------------------------------------------------

# هر دسته به چند کلیدواژه/عبارت پرتکرار در شکایات مردمی نگاشت شده است.
# ترتیب دسته‌ها اهمیتی ندارد؛ امتیاز بر اساس تعداد تطابق در متن محاسبه می‌شود.
CATEGORY_KEYWORDS = {
    "روشنایی": ["روشنایی", "چراغ", "لامپ", "تیر برق", "نور کافی نیست", "تاریک"],
    "آسفالت و معابر": ["آسفالت", "چاله", "دست‌انداز", "پیاده‌رو", "جدول", "خیابان خراب", "معبر"],
    "آب و فاضلاب": ["آب‌گرفتگی", "فاضلاب", "لوله", "نشت آب", "چاه فاضلاب", "آب آشامیدنی", "قطعی آب"],
    "پسماند": ["زباله", "پسماند", "سطل زباله", "بوی نامطبوع زباله", "جمع‌آوری زباله"],
    "فضای سبز": ["فضای سبز", "درخت", "پارک", "چمن", "آبیاری فضای سبز"],
    "امنیتی": ["دزدی", "سرقت", "درگیری", "مزاحمت", "ناامنی", "خشونت", "نزاع"],
    "بهداشت و درمان": ["بیماری", "آلودگی هوا", "بهداشت", "درمانگاه", "شیوع"],
    "آسیب‌های اجتماعی": ["اعتیاد", "معتاد", "کارتن‌خواب", "تکدی‌گری", "خرید و فروش مواد"],
    "عمرانی": ["ساخت‌وساز", "تخریب", "نوسازی", "بافت فرسوده", "پروژه عمرانی"],
    "خدمات شهری": ["شهرداری", "سرویس بهداشتی عمومی", "خدمات شهری"],
    "اجتماعی": ["نزاع خانوادگی", "اختلاف همسایگی", "مشکل اجتماعی"],
    "آموزشی": ["مدرسه", "کلاس درس", "آموزش‌وپرورش", "کمبود معلم"],
    "اشتغال": ["بیکاری", "اشتغال", "کارگاه تولیدی", "فرصت شغلی"],
    "فرهنگی": ["فرهنگسرا", "برنامه فرهنگی", "مسجد", "هیئت", "مراسم"],
}

# عبارات نشان‌دهنده فوریت بالا (۴ یا ۵ از ۵). اگر هیچ‌کدام یافت نشد، امتیاز
# پیش‌فرض میانه (۳) برگردانده می‌شود تا کارمند خودش تصمیم نهایی را بگیرد.
URGENCY_CRITICAL_PATTERNS = [
    "خطر جانی", "آتش‌سوزی", "آتش سوزی", "انفجار", "ریزش", "خطر ریزش",
    "برق‌گرفتگی", "برق گرفتگی", "غرق", "سقوط", "تصادف شدید", "جراحت",
]
URGENCY_HIGH_PATTERNS = [
    "فوری", "خطرناک", "خطر", "آسیب", "اضطراری", "سریع", "هرچه زودتر",
]
URGENCY_LOW_PATTERNS = [
    "هر زمان", "در فرصت مناسب", "مهم نیست", "عجله‌ای نیست", "غیرفوری",
]


def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def suggest_offline(text: str):
    """پیشنهاد دسته‌بندی و فوریت صرفاً بر اساس تطابق کلیدواژه؛ بدون اینترنت.

    خروجی: دیکشنری با کلیدهای category, urgency, confidence, matched_keywords, engine
    مقدار category همیشه یکی از database.Database.ISSUE_CATEGORIES است (یا "سایر").
    مقدار urgency عددی بین ۱ تا ۵ است.
    """
    normalized = _normalize(text)
    if not normalized:
        return {
            "category": "سایر", "urgency": 3, "confidence": 0.0,
            "matched_keywords": [], "engine": "keyword",
        }

    best_category, best_score, matched = "سایر", 0, []
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in normalized]
        if len(hits) > best_score:
            best_category, best_score, matched = category, len(hits), hits

    if any(p in normalized for p in URGENCY_CRITICAL_PATTERNS):
        urgency = 5
    elif any(p in normalized for p in URGENCY_HIGH_PATTERNS):
        urgency = 4
    elif any(p in normalized for p in URGENCY_LOW_PATTERNS):
        urgency = 2
    else:
        urgency = 3

    # اطمینان ساده و شفاف: هرچه کلیدواژه بیشتری تطابق داشته، اطمینان بیشتر
    confidence = min(1.0, 0.3 + 0.2 * best_score) if best_score else 0.15

    return {
        "category": best_category,
        "urgency": urgency,
        "confidence": round(confidence, 2),
        "matched_keywords": matched,
        "engine": "keyword",
    }


# ---------------------------------------------------------------------------
# حالت ۲: استعلام اختیاری از یک سرویس هوش مصنوعی خارجی
# ---------------------------------------------------------------------------

VALID_CATEGORIES_TOKEN = "{{CATEGORIES}}"

_API_PROMPT_TEMPLATE = (
    "متن زیر یک شکایت یا درخواست شهروندی به فارسی است. فقط یک خروجی JSON با "
    "دقیقاً همین دو کلید برگردان و هیچ توضیح دیگری اضافه نکن:\n"
    '{{"category": "<یکی از این گزینه‌ها دقیقاً>: ' + VALID_CATEGORIES_TOKEN + '", '
    '"urgency": <عدد صحیح بین ۱ تا ۵>}}\n\n'
    "متن شکایت:\n{text}"
)


def suggest_via_api(text: str, api_url: str, api_key: str, categories, timeout: int = 8):
    """تلاش برای گرفتن پیشنهاد دقیق‌تر از یک سرویس هوش مصنوعی خارجی.

    فقط متن آزاد شرح مسئله ارسال می‌شود؛ هیچ داده هویتی (نام، موبایل،
    مختصات) در این تابع دخیل نیست. در هرگونه خطا (نبود اینترنت، کلید
    نامعتبر، پاسخ غیرمنتظره) مقدار None برمی‌گرداند تا فراخوان به‌سادگی
    به پیشنهاد آفلاین برگردد؛ این تابع هرگز استثنا پرتاب نمی‌کند.
    """
    if not text or not text.strip() or not api_url or not api_key or requests is None:
        return None
    try:
        prompt = _API_PROMPT_TEMPLATE.format(text=text.strip()[:2000]) \
            .replace(VALID_CATEGORIES_TOKEN, "، ".join(categories))
        response = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 120,
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return None
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        content = re.sub(r"^```(json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        data = json.loads(content)
        category = data.get("category")
        urgency = int(data.get("urgency", 3))
        if category not in categories:
            category = "سایر"
        urgency = max(1, min(5, urgency))
        return {
            "category": category, "urgency": urgency,
            "confidence": 0.85, "matched_keywords": [], "engine": "api",
        }
    except Exception:
        return None


def suggest(text: str, categories, api_url: str = "", api_key: str = ""):
    """نقطه ورود اصلی: اگر تنظیمات API معتبر باشد، اول آن را امتحان می‌کند؛
    در غیر این صورت (یا در صورت شکست بی‌صدا) به موتور کلیدواژه‌ای آفلاین
    برمی‌گردد. این تابع همیشه یک پیشنهاد معتبر برمی‌گرداند، هرگز None."""
    if api_url and api_key:
        result = suggest_via_api(text, api_url, api_key, categories)
        if result is not None:
            return result
    return suggest_offline(text)
