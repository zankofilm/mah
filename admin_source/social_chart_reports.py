# -*- coding: utf-8 -*-
"""Pure aggregation helpers for Social Council bar-chart reports."""

from __future__ import annotations

from collections import Counter, defaultdict
import re

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
CLOSED_STATUSES = {"مختومه", "انجام‌شده", "لغوشده", "تکمیل‌شده"}
ANSWERED_REFERRAL_STATUSES = {"پاسخ‌داده‌شده", "مختومه"}
ACTIVE_ACTION_STATUSES = {"برنامه‌ریزی‌شده", "در حال اجرا"}

CHART_TYPES = [
    ("issues_by_category", "آسیب‌های اجتماعی بر اساس دسته‌بندی"),
    ("blocks_comparison", "مقایسه عملکرد بلوک‌ها"),
    ("committees_performance", "عملکرد کمیته‌های شش‌گانه"),
    ("resolutions_status", "وضعیت مصوبات شورای اجتماعی"),
    ("actions_status", "وضعیت برنامه‌های عملیاتی"),
]


def normalize_date(value) -> str:
    """Return a comparable YYYY-MM-DD-like key from ISO/Jalali text."""
    text = str(value or "").strip().translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)
    if not text:
        return ""
    text = text.replace("/", "-").replace(".", "-")
    match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if not match:
        return text[:10]
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"


def row_in_date_range(row, date_from="", date_to="", keys=("created_at",)) -> bool:
    start, end = normalize_date(date_from), normalize_date(date_to)
    if not start and not end:
        return True
    value = ""
    for key in keys:
        value = normalize_date((row or {}).get(key))
        if value:
            break
    if not value:
        return False
    return (not start or value >= start) and (not end or value <= end)


def filter_rows(rows, status="", date_from="", date_to="", date_keys=("created_at",)):
    status = str(status or "").strip()
    return [
        row for row in rows
        if (not status or row.get("status") == status)
        and row_in_date_range(row, date_from, date_to, date_keys)
    ]


def _ordered_counter(counter: Counter):
    return sorted(counter.items(), key=lambda item: (-item[1], str(item[0])))


def issues_by_category_payload(issues, subtitle=""):
    counts = Counter((row.get("category") or "سایر") for row in issues)
    ordered = _ordered_counter(counts)
    return {
        "title": "آسیب‌های اجتماعی بر اساس دسته‌بندی",
        "subtitle": subtitle,
        "categories": [name for name, _ in ordered],
        "series": [{"label": "تعداد پرونده", "values": [count for _, count in ordered]}],
        "headers": ["دسته‌بندی", "تعداد پرونده"],
        "rows": [[name, count] for name, count in ordered],
    }


def blocks_comparison_payload(blocks, subtitle="", exact_status=False):
    data = []
    for block in blocks:
        issues = list(block.get("issues") or [])
        resolutions = list(block.get("resolutions") or [])
        actions = list(block.get("actions") or [])
        issue_count = len(issues) if exact_status else sum(1 for row in issues if row.get("status") not in CLOSED_STATUSES)
        critical = sum(1 for row in issues if row.get("urgency") in {"فوری", "بحرانی"} and (exact_status or row.get("status") not in CLOSED_STATUSES))
        resolution_count = len(resolutions) if exact_status else sum(1 for row in resolutions if row.get("status") not in CLOSED_STATUSES)
        action_count = len(actions) if exact_status else sum(1 for row in actions if row.get("status") in ACTIVE_ACTION_STATUSES)
        data.append((block.get("zone_name") or "بدون نام", issue_count, critical, resolution_count, action_count))
    data.sort(key=lambda row: (-(row[1] + row[2] + row[3] + row[4]), row[0]))
    issue_label = "مسائل فیلترشده" if exact_status else "مسائل باز"
    resolution_label = "مصوبات فیلترشده" if exact_status else "مصوبات باز"
    action_label = "اقدامات فیلترشده" if exact_status else "اقدامات فعال"
    return {
        "title": "مقایسه عملکرد بلوک‌ها",
        "subtitle": subtitle,
        "categories": [row[0] for row in data],
        "series": [
            {"label": issue_label, "values": [row[1] for row in data]},
            {"label": "مسائل فوری/بحرانی", "values": [row[2] for row in data]},
            {"label": resolution_label, "values": [row[3] for row in data]},
            {"label": action_label, "values": [row[4] for row in data]},
        ],
        "headers": ["بلوک", issue_label, "فوری/بحرانی", resolution_label, action_label],
        "rows": [list(row) for row in data],
    }


def committees_performance_payload(referrals, committee_titles=None, subtitle=""):
    stats = defaultdict(lambda: [0, 0, 0])
    for row in referrals:
        title = row.get("committee_title") or "کمیته نامشخص"
        stats[title][0] += 1
        if row.get("status") in ANSWERED_REFERRAL_STATUSES:
            stats[title][1] += 1
        else:
            stats[title][2] += 1
    titles = list(dict.fromkeys(committee_titles or []))
    for title in stats:
        if title not in titles:
            titles.append(title)
    titles.sort(key=lambda title: (-stats[title][0], title))
    return {
        "title": "عملکرد کمیته‌های شش‌گانه",
        "subtitle": subtitle,
        "categories": titles,
        "series": [
            {"label": "کل ارجاعات", "values": [stats[t][0] for t in titles]},
            {"label": "پاسخ‌داده‌شده", "values": [stats[t][1] for t in titles]},
            {"label": "باز/در حال بررسی", "values": [stats[t][2] for t in titles]},
        ],
        "headers": ["کمیته", "کل ارجاعات", "پاسخ‌داده‌شده", "باز/در حال بررسی"],
        "rows": [[t, *stats[t]] for t in titles],
    }


def resolutions_status_payload(resolutions, subtitle=""):
    counts = Counter((row.get("status") or "نامشخص") for row in resolutions)
    preferred = ["در انتظار اقدام", "در حال پیگیری", "انجام‌شده", "لغوشده"]
    statuses = [s for s in preferred if s in counts] + [s for s, _ in _ordered_counter(counts) if s not in preferred]
    return {
        "title": "وضعیت مصوبات شورای اجتماعی",
        "subtitle": subtitle,
        "categories": statuses,
        "series": [{"label": "تعداد مصوبه", "values": [counts[s] for s in statuses]}],
        "headers": ["وضعیت", "تعداد مصوبه"],
        "rows": [[s, counts[s]] for s in statuses],
    }


def actions_status_payload(actions, subtitle=""):
    grouped = defaultdict(list)
    for row in actions:
        grouped[row.get("status") or "نامشخص"].append(int(row.get("progress_percent") or 0))
    preferred = ["برنامه‌ریزی‌شده", "در حال اجرا", "متوقف", "تکمیل‌شده", "لغوشده"]
    statuses = [s for s in preferred if s in grouped] + sorted(s for s in grouped if s not in preferred)
    counts = [len(grouped[s]) for s in statuses]
    averages = [round(sum(grouped[s]) / len(grouped[s]), 1) if grouped[s] else 0 for s in statuses]
    overall = round(sum(int(row.get("progress_percent") or 0) for row in actions) / len(actions), 1) if actions else 0
    detail = f"میانگین پیشرفت کل: {overall}٪"
    subtitle = f"{subtitle} | {detail}" if subtitle else detail
    return {
        "title": "وضعیت برنامه‌های عملیاتی",
        "subtitle": subtitle,
        "categories": statuses,
        "series": [{"label": "تعداد برنامه", "values": counts}],
        "headers": ["وضعیت", "تعداد برنامه", "میانگین پیشرفت"],
        "rows": [[s, counts[i], f"{averages[i]}٪"] for i, s in enumerate(statuses)],
    }
