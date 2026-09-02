# -*- coding: utf-8 -*-
"""
موتور تولید «برنامه عملیاتی بلوک» بر اساس مشکلات و درخواست‌های ثبت‌شده
یک بلوک. هدف: کمک به کارشناس بلوک برای تدوین سریع یک برنامه اقدام
مستند، نه جای‌گزینی تصمیم انسانی.

مثل smart_triage.py، دو حالت دارد:
  1) موتور قانون‌محور آفلاین (پیش‌فرض، همیشه فعال، بدون نیاز به اینترنت):
     مسائل و درخواست‌ها را بر اساس امتیاز اولویت موجود در دیتابیس
     (calculate_issue_priority، از قبل شفاف و قابل بازتولید) دسته‌بندی و
     مرتب می‌کند، و یک برنامه ساختارمند متنی می‌سازد: اولویت‌ها، دستگاه
     مسؤول پیشنهادی (از فهرست دستگاه‌های فعال ثبت‌شده)، و اقدامات در
     جریان که نباید تکرار شوند.
  2) اتصال اختیاری به سرویس هوش مصنوعی خارجی برای تولید یک برنامه
     روایت‌گونه‌تر و با استدلال عمیق‌تر روی همان داده. در صورت هر نوع
     خطا (نبود اینترنت، کلید نامعتبر و ...) به‌طور کاملاً بی‌صدا به موتور
     آفلاین بازمی‌گردد.

نکته حریم خصوصی: تنها عنوان/دسته/شرح مسائل و درخواست‌ها (بدون نام
شهروندان، شماره تماس، یا مختصات دقیق) به سرویس خارجی ارسال می‌شود.
"""
from __future__ import annotations

import json
import re

try:
    import requests
except ImportError:
    requests = None


# ---------------------------------------------------------------------------
# حالت ۱: موتور قانون‌محور آفلاین
# ---------------------------------------------------------------------------

def _format_issue_line(issue):
    parts = [f"- «{issue['title']}»"]
    if issue.get("category"):
        parts.append(f"(دسته: {issue['category']})")
    if issue.get("priority_level"):
        parts.append(f"— اولویت: {issue['priority_level']}")
    if issue.get("affected_households"):
        parts.append(f"— خانوار متأثر: {issue['affected_households']}")
    if issue.get("related_office"):
        parts.append(f"— دستگاه مرتبط ثبت‌شده: {issue['related_office']}")
    return " ".join(parts)


def _format_request_line(request):
    parts = [f"- «{request.get('title') or request.get('description', '')[:40]}»"]
    if request.get("category"):
        parts.append(f"(دسته: {request['category']})")
    urgency = request.get("urgency")
    if urgency:
        parts.append(f"— فوریت اعلامی شهروند: {urgency} از ۵")
    return " ".join(parts)


def _suggest_agency_for_category(category, agencies):
    """جستجوی ساده در حوزه خدمت دستگاه‌های فعال بر اساس دسته مسئله؛
    اگر هیچ تطابقی نبود، None برمی‌گرداند تا برنامه صادقانه بگوید
    «دستگاه مسؤول نیاز به تعیین دارد» به‌جای حدس نادرست."""
    if not category:
        return None
    for agency in agencies:
        scope = (agency.get("service_scope") or "") + " " + (agency.get("category") or "")
        if category in scope:
            return agency["name"]
    return None


def generate_offline(context):
    """تولید برنامه عملیاتی صرفاً بر اساس قوانین شفاف؛ بدون اینترنت.

    context: خروجی Database.get_zone_action_plan_context(zone_id)
    خروجی: متن فارسی ساختارمند (رشته)
    """
    zone_name = context["zone"]["name"]
    profile = context.get("profile") or {}
    issues = sorted(
        context.get("open_issues") or [],
        key=lambda x: x.get("priority_score") or 0, reverse=True
    )
    requests_ = context.get("open_requests") or []
    active_actions = context.get("active_actions") or []
    agencies = context.get("agencies") or []

    critical = [i for i in issues if i.get("priority_level") in ("بحرانی", "فوری")]
    important = [i for i in issues if i.get("priority_level") == "مهم"]
    normal = [i for i in issues if i.get("priority_level") not in ("بحرانی", "فوری", "مهم")]

    lines = [f"برنامه عملیاتی بلوک «{zone_name}»", "=" * 40, ""]

    lines.append("۱) وضعیت کلی")
    lines.append(f"- مسائل باز ثبت‌شده: {len(issues)} مورد (بحرانی/فوری: {len(critical)}، مهم: {len(important)}، سایر: {len(normal)})")
    lines.append(f"- درخواست‌های مردمی باز: {len(requests_)} مورد")
    lines.append(f"- اقدامات در جریان: {len(active_actions)} مورد")
    if profile.get("estimated_population"):
        lines.append(f"- جمعیت تخمینی بلوک: {profile['estimated_population']} نفر")
    if profile.get("vulnerable_households"):
        lines.append(f"- خانوارهای آسیب‌پذیر ثبت‌شده: {profile['vulnerable_households']}")
    lines.append("")

    if critical:
        lines.append("۲) اولویت فوری — نیازمند اقدام در کوتاه‌ترین زمان")
        for issue in critical:
            lines.append(_format_issue_line(issue))
            agency = _suggest_agency_for_category(issue.get("category"), agencies)
            if agency:
                lines.append(f"    ← دستگاه پیشنهادی برای پیگیری: {agency}")
            else:
                lines.append("    ← دستگاه مسؤول هنوز تعیین نشده؛ نیاز به تخصیص دارد.")
        lines.append("")

    if important:
        lines.append("۳) اولویت مهم — برنامه‌ریزی در بازه میان‌مدت")
        for issue in important:
            lines.append(_format_issue_line(issue))
            agency = _suggest_agency_for_category(issue.get("category"), agencies)
            if agency:
                lines.append(f"    ← دستگاه پیشنهادی برای پیگیری: {agency}")
        lines.append("")

    if normal:
        lines.append(f"۴) سایر مسائل ثبت‌شده ({len(normal)} مورد، اولویت پایین‌تر)")
        for issue in normal[:5]:
            lines.append(_format_issue_line(issue))
        if len(normal) > 5:
            lines.append(f"    و {len(normal) - 5} مورد دیگر...")
        lines.append("")

    if requests_:
        lines.append("۵) درخواست‌های مردمی باز")
        for req in requests_[:8]:
            lines.append(_format_request_line(req))
        if len(requests_) > 8:
            lines.append(f"    و {len(requests_) - 8} مورد دیگر...")
        lines.append("")

    if active_actions:
        lines.append("۶) اقدامات در حال انجام (برای پیشگیری از دوباره‌کاری)")
        for action in active_actions:
            resp = action.get("responsible_office") or action.get("responsible_person") or "—"
            lines.append(f"- «{action['title']}» — مسؤول: {resp} — وضعیت: {action['status']}")
        lines.append("")

    if not issues and not requests_:
        lines.append("در حال حاضر هیچ مسئله یا درخواست بازی برای این بلوک ثبت نشده است.")

    lines.append("—" * 20)
    lines.append(
        "این برنامه بر اساس داده‌های ثبت‌شده در سامانه و قواعد اولویت‌بندی شفاف "
        "تولید شده است؛ تصمیم نهایی و تخصیص منابع بر عهده کارشناس/مدیر بلوک است."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# حالت ۲: تولید برنامه توسط سرویس هوش مصنوعی خارجی (اختیاری)
# ---------------------------------------------------------------------------

def _build_api_prompt(context):
    zone_name = context["zone"]["name"]
    profile = context.get("profile") or {}
    issues = context.get("open_issues") or []
    requests_ = context.get("open_requests") or []
    active_actions = context.get("active_actions") or []
    agencies = [a["name"] for a in (context.get("agencies") or [])]

    # فقط فیلدهای غیرحساس (بدون نام شهروند، تلفن، مختصات دقیق)
    issues_brief = [
        {"title": i["title"], "category": i["category"], "priority": i["priority_level"],
         "description": (i.get("description") or "")[:200]}
        for i in issues
    ]
    requests_brief = [
        {"title": r.get("title") or "", "category": r.get("category") or "",
         "urgency": r.get("urgency"), "description": (r.get("description") or "")[:200]}
        for r in requests_
    ]
    actions_brief = [
        {"title": a["title"], "status": a["status"], "responsible": a.get("responsible_office") or ""}
        for a in active_actions
    ]

    payload = {
        "zone_name": zone_name,
        "estimated_population": profile.get("estimated_population"),
        "vulnerable_households": profile.get("vulnerable_households"),
        "open_issues": issues_brief,
        "open_citizen_requests": requests_brief,
        "actions_in_progress": actions_brief,
        "available_agencies": agencies,
    }
    return (
        "تو یک مشاور مدیریت شهری هستی. بر اساس اطلاعات JSON زیر مربوط به یک بلوک "
        "شهری، یک «برنامه عملیاتی» به زبان فارسی رسمی و ساختارمند بنویس. برنامه باید "
        "شامل این بخش‌ها باشد: ۱) خلاصه وضعیت، ۲) اولویت‌های فوری با دستگاه مسؤول "
        "پیشنهادی از فهرست available_agencies (در صورت تطابق)، ۳) اولویت‌های میان‌مدت، "
        "۴) هشدار درباره اقدامات تکراری با آنچه در actions_in_progress موجود است. "
        "متن را کوتاه، عملی و بدون سرفصل انگلیسی بنویس.\n\n"
        f"داده:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def generate_via_api(context, api_url, api_key, timeout=20):
    """تلاش برای تولید برنامه عملیاتی با یک سرویس هوش مصنوعی خارجی.
    در هر نوع خطا None برمی‌گرداند تا فراخوان به موتور آفلاین برگردد."""
    if not api_url or not api_key or requests is None:
        return None
    try:
        prompt = _build_api_prompt(context)
        response = requests.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1200,
            },
            timeout=timeout,
        )
        if response.status_code != 200:
            return None
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        content = re.sub(r"^```(text)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
        return content if content else None
    except Exception:
        return None


def generate(context, api_url: str = "", api_key: str = ""):
    """نقطه ورود اصلی: اگر تنظیمات API معتبر باشد ابتدا آن را امتحان می‌کند؛
    در غیر این صورت (یا شکست بی‌صدا) به موتور قانون‌محور آفلاین برمی‌گردد.
    همیشه یک تاپل (متن_برنامه, نام_موتور) برمی‌گرداند، هرگز None."""
    if api_url and api_key:
        result = generate_via_api(context, api_url, api_key)
        if result:
            return result, "api"
    return generate_offline(context), "keyword"
