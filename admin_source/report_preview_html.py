# -*- coding: utf-8 -*-
"""
تولید HTML پیش‌نمایش برای گزارش‌های عمومی سامانه (کلی وضعیت، اعضا، درخواست‌ها، اقدامات)
جهت نمایش در QWebEngineView قبل از خروجی نهایی فایل. برخلاف گزارش «کامل بلوک»
(که در block_report_preview.py پیاده‌سازی شده)، این گزارش‌ها معمولاً فقط جدول‌های
ساده هستند و نیازی به تصویر نقشه ندارند.
"""

import base64
from jalali_utils import convert_dates_in_text
from committee_report_utils import get_zone_committee_report_data, member_display_role

REPORT_PREVIEW_STYLE = """
<style>
  body {
    font-family: Tahoma, 'Vazirmatn', sans-serif;
    direction: rtl;
    background: #f4f5f7;
    color: #1c2530;
    margin: 0;
    padding: 24px;
  }
  .report-container {
    max-width: 900px;
    margin: 0 auto;
    background: white;
    padding: 32px;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  }
  .header {
    text-align: center;
    border-bottom: 3px solid #c9a227;
    padding-bottom: 16px;
    margin-bottom: 24px;
  }
  .header h1 {
    color: #0b1f3a;
    margin: 0 0 6px 0;
    font-size: 22px;
  }
  .header p {
    color: #5b6472;
    margin: 0;
    font-size: 13px;
  }
  h2.section-title {
    color: #13294b;
    border-right: 4px solid #c9a227;
    padding-right: 10px;
    margin-top: 28px;
    margin-bottom: 12px;
    font-size: 16px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10px;
  }
  th, td {
    border: 1px solid #d7dbe3;
    padding: 8px 10px;
    text-align: right;
    font-size: 13px;
  }
  th {
    background: #13294b;
    color: white;
  }
  tbody tr:nth-child(even) {
    background: #f0f2f6;
  }
  .committee-card {
    border: 1px solid #d7dbe3;
    border-radius: 8px;
    padding: 12px;
    margin: 14px 0;
  }
  .committee-card h3 {
    color: #13294b;
    margin: 0 0 10px;
    border-bottom: 2px solid #c9a227;
    padding-bottom: 6px;
  }
  .empty-note {
    color: #5b6472;
    font-style: italic;
    background: #f0f2f6;
    padding: 10px;
    border-radius: 6px;
  }
  @media print {
    body { background: white; padding: 0; }
    .report-container { box-shadow: none; max-width: 100%; }
  }
</style>
"""


def _table_or_empty(headers, rows, empty_message):
    headers = [convert_dates_in_text(x) for x in headers]
    rows = [[convert_dates_in_text(x) for x in row] for row in rows]
    if not rows:
        return f'<p class="empty-note">{empty_message}</p>'
    header_html = "".join(f"<th>{h}</th>" for h in headers)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"""
    <table>
      <thead><tr>{header_html}</tr></thead>
      <tbody>{body_html}</tbody>
    </table>
    """


def _wrap_report_html(title, body_html):
    title = convert_dates_in_text(title)
    body_html = convert_dates_in_text(body_html)
    return f"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8" />
<title>{title}</title>
{REPORT_PREVIEW_STYLE}
</head>
<body>
  <div class="report-container">
    <div class="header">
      <h1>{title}</h1>
      <p>فرمانداری شهرستان جوانرود — سامانه جامع مدیریت محلات و بلوک‌های شهرستان جوانرود</p>
    </div>
    {body_html}
  </div>
</body>
</html>
"""


def build_overview_report_preview_html(db):
    zones = db.get_zones()
    all_streets = db.get_streets()
    all_places = db.get_places()
    all_members = db.get_council_members()
    all_requests = db.get_priority_requests()
    all_committees = [c for z in zones for c in get_zone_committee_report_data(db, z["id"])]
    total_actions = sum(r["action_count"] for r in all_requests)

    stats_rows = [
        ["تعداد مناطق/بلوک‌ها", str(len(zones))],
        ["تعداد خیابان‌ها و کوچه‌ها", str(len(all_streets))],
        ["تعداد اماکن", str(len(all_places))],
        ["تعداد اعضای شورا", str(len(all_members))],
        ["تعداد کمیته‌های تخصصی", str(len(all_committees))],
        ["تعداد اعضای فعال کمیته‌ها", str(sum(len(c.get("active_members") or []) for c in all_committees))],
        ["مصوبات باز کمیته‌ها", str(sum(1 for c in all_committees for r in (c.get("resolutions") or []) if r.get("status") not in ("انجام‌شده", "لغوشده")))],
        ["تعداد درخواست‌ها", str(len(all_requests))],
        ["مجموع اقدامات پیگیری", str(total_actions)],
    ]

    zone_rows = []
    for z in zones:
        zone_rows.append([
            z["name"],
            str(len(db.get_streets(zone_id=z["id"]))),
            str(len(db.get_places(zone_id=z["id"]))),
            str(len(db.get_council_members(zone_id=z["id"]))),
            str(len(db.get_priority_requests(zone_id=z["id"]))),
        ])

    body = f"""
    <h2 class="section-title">خلاصه وضعیت</h2>
    {_table_or_empty(["شاخص", "مقدار"], stats_rows, "داده‌ای موجود نیست.")}

    <h2 class="section-title">جزئیات هر منطقه</h2>
    {_table_or_empty(
        ["نام منطقه", "تعداد خیابان", "تعداد مکان", "تعداد اعضا", "تعداد درخواست"],
        zone_rows, "هنوز منطقه‌ای ثبت نشده است."
    )}
    """
    return _wrap_report_html("گزارش کلی وضعیت سامانه", body)


def build_members_report_preview_html(db, zone_id=None):
    members = db.get_council_members(zone_id=zone_id)
    zones_by_id = {z["id"]: z["name"] for z in db.get_zones()}

    title = "گزارش اعضای شورای محلات"
    if zone_id is not None:
        zone = db.get_zone(zone_id)
        if zone:
            title += f" — منطقه: {zone['name']}"

    headers = ["نام", "نام خانوادگی", "کد ملی", "تحصیلات", "موبایل", "دسته", "سمت"]
    if zone_id is None:
        headers.append("منطقه")

    rows = []
    for m in members:
        row = [m["first_name"], m["last_name"], m["national_code"] or "—",
               m["education"] or "—", m["mobile"] or "—", m["member_group"] or "—", m["position"] or "—"]
        if zone_id is None:
            row.append(zones_by_id.get(m["zone_id"], "—"))
        rows.append(row)

    body = f"""
    <h2 class="section-title">لیست اعضا (تعداد: {len(members)})</h2>
    {_table_or_empty(headers, rows, "هیچ عضوی ثبت نشده است.")}
    """
    return _wrap_report_html(title, body)


def build_requests_report_preview_html(db, zone_id=None):
    requests = db.get_priority_requests(zone_id=zone_id)
    zones_by_id = {z["id"]: z["name"] for z in db.get_zones()}

    title = "گزارش درخواست‌ها و مشکلات اولویت‌بندی‌شده"
    if zone_id is not None:
        zone = db.get_zone(zone_id)
        if zone:
            title += f" — منطقه: {zone['name']}"

    rows = []
    for i, r in enumerate(requests, start=1):
        rows.append([
            str(i), zones_by_id.get(r["zone_id"], "—"), r["description"],
            r["related_office"] or "—", str(r["action_count"])
        ])

    body = f"""
    <h2 class="section-title">لیست درخواست‌ها (تعداد: {len(requests)})</h2>
    {_table_or_empty(
        ["ردیف", "منطقه", "شرح درخواست/مشکل", "اداره مرتبط", "تعداد اقدام"],
        rows, "درخواستی ثبت نشده است."
    )}
    """
    return _wrap_report_html(title, body)


def build_actions_report_preview_html(db, zone_id=None):
    requests = db.get_priority_requests(zone_id=zone_id)
    zones_by_id = {z["id"]: z["name"] for z in db.get_zones()}

    title = "گزارش اقدامات انجام‌شده"
    if zone_id is not None:
        zone = db.get_zone(zone_id)
        if zone:
            title += f" — منطقه: {zone['name']}"

    sections = []
    any_found = False
    for r in requests:
        actions = db.get_request_actions(r["id"])
        if not actions:
            continue
        any_found = True
        rows = [[a["created_at"], a["action_description"]] for a in actions]
        header_text = f"{zones_by_id.get(r['zone_id'], '—')} — {r['description']}"
        sections.append(f"""
        <h3 style="color:#13294b; margin-top:18px;">{header_text}</h3>
        {_table_or_empty(["تاریخ", "شرح اقدام"], rows, "")}
        """)

    body_inner = "".join(sections) if any_found else '<p class="empty-note">هیچ اقدامی ثبت نشده است.</p>'
    body = f"""
    <h2 class="section-title">تاریخچه اقدامات</h2>
    {body_inner}
    """
    return _wrap_report_html(title, body)


def build_zone_full_report_preview_html(db, zone_id):
    """پیش‌نمایش گزارش کامل منطقه با تصویر در ابتدا و همه مشخصات به ترتیب."""
    zone = db.get_zone(zone_id)
    if not zone:
        return "<h1>منطقه یافت نشد</h1>"

    meeting_place = db.get_zone_meeting_place(zone_id)
    streets = db.get_streets(zone_id=zone_id)
    places = db.get_places(zone_id=zone_id)
    mosques = db.get_mosques(zone_id=zone_id)
    members = db.get_council_members(zone_id=zone_id)
    requests = db.get_priority_requests(zone_id=zone_id)
    field_visits = db.get_field_visits(zone_id)
    citizen_requests = db.get_citizen_requests(zone_id)
    operational_analysis = db.get_zone_operational_analysis(zone_id)
    correspondence_letters = db.get_correspondence_letters(zone_id=zone_id)
    committees = get_zone_committee_report_data(db, zone_id)

    snapshot = None
    try:
        from zone_snapshot_service import refresh_zone_snapshot
        snapshot = refresh_zone_snapshot(db, zone_id, force=False)
    except Exception:
        snapshot = db.get_zone_snapshot(zone_id) if hasattr(db, "get_zone_snapshot") else None
    if snapshot and snapshot.get("png_data"):
        map_b64 = base64.b64encode(snapshot["png_data"]).decode("utf-8")
        snapshot_html = (
            f'<h2 class="section-title">نمای گرافیکی بلوک</h2>'
            f'<div style="width:100%;height:125mm;display:flex;align-items:center;justify-content:center;overflow:hidden;page-break-inside:avoid">'
            f'<img style="max-width:100%;max-height:125mm;object-fit:contain;border:1px solid #d7dbe3;border-radius:6px" '
            f'src="data:image/png;base64,{map_b64}" alt="نمای بلوک" /></div>'
        )
    else:
        snapshot_html = '<h2 class="section-title">نمای گرافیکی بلوک</h2><p class="empty-note">تصویر بلوک در دسترس نیست.</p>'

    summary_rows = [
        ["نام بلوک", zone.get("name") or "—"],
        ["وضعیت تکمیل", zone.get("status") or "—"],
        ["مساحت", f"{(zone.get('area_m2', 0) or 0)/10000:.2f} هکتار"],
        ["محیط", f"{zone.get('perimeter_m', 0) or 0:.0f} متر"],
        ["تعداد نقاط مرزی", str(len(zone.get("boundary_points", [])))],
        ["تعداد خیابان و کوچه", str(len(streets))],
        ["تعداد سایر اماکن", str(len(places))],
        ["تعداد مساجد", str(len(mosques))],
        ["تعداد کمیته‌های تخصصی", str(len(committees))],
        ["اعضای فعال کمیته‌ها", str(sum(len(c.get("active_members") or []) for c in committees))],
        ["مصوبات باز کمیته‌ها", str(sum(1 for c in committees for r in (c.get("resolutions") or []) if r.get("status") not in ("انجام‌شده", "لغوشده")))],
        ["بازدیدهای میدانی", str(len(field_visits))],
        ["درخواست‌های مردمی", str(len(citizen_requests))],
        ["مکاتبات اداری مرتبط", str(len(correspondence_letters))],
        ["سطح ریسک عملیاتی", operational_analysis.get("risk_level") or "—"],
    ]

    meeting_rows = []
    if meeting_place:
        meeting_rows = [
            ["نام مکان", meeting_place["place_name"] or "—"],
            ["آدرس دقیق", meeting_place["exact_address"] or "—"],
        ]

    committee_sections = []
    if committees:
        committee_sections.append(_table_or_empty(
            ["ردیف", "کمیته", "رئیس", "دبیر", "اعضا", "جلسات", "مصوبات باز", "وضعیت"],
            [[i, c.get("title") or "—", c.get("chair_name") or "—", c.get("secretary_name") or "—",
              len(c.get("active_members") or []), len(c.get("meetings") or []),
              sum(1 for r in c.get("resolutions") or [] if r.get("status") not in ("انجام‌شده", "لغوشده")),
              c.get("status") or "—"] for i, c in enumerate(committees, start=1)],
            "کمیته‌ای ثبت نشده است."
        ))
        for committee in committees:
            members_rows = [[m.get("person_name") or "—", m.get("national_code") or "—",
                             member_display_role(m), m.get("member_type") or "—",
                             m.get("agency_name") or "—", m.get("mobile") or "—",
                             m.get("status") or "—"] for m in committee.get("members") or []]
            meetings_rows = [[m.get("title") or "—", m.get("meeting_date") or "—",
                              m.get("start_time") or "—", m.get("place_name") or "—",
                              m.get("status") or "—"] for m in committee.get("meetings") or []]
            resolutions_rows = [[r.get("title") or "—", r.get("responsible_person") or "—",
                                 r.get("responsible_agency") or "—", r.get("due_date") or "—",
                                 r.get("status") or "—"] for r in committee.get("resolutions") or []]
            links_rows = [["مسئله", x.get("title") or "—", x.get("related_office") or "—", x.get("status") or "—"] for x in committee.get("issues") or []]
            links_rows += [["اقدام", x.get("title") or "—", x.get("responsible_office") or "—", x.get("status") or "—"] for x in committee.get("actions") or []]
            committee_sections.append(f"""
            <div class="committee-card">
              <h3>{committee.get('title') or 'کمیته'}</h3>
              {_table_or_empty(["مشخصه", "مقدار"], [
                  ["رئیس", committee.get("chair_name") or "—"],
                  ["دبیر", committee.get("secretary_name") or "—"],
                  ["شماره حکم", committee.get("decree_no") or "—"],
                  ["تاریخ حکم", committee.get("decree_date") or "—"],
                  ["دوره فعالیت", f"{committee.get('start_date') or '—'} تا {committee.get('end_date') or '—'}"],
                  ["دستگاه‌های پیشنهادی", committee.get("recommended_agencies") or "—"],
                  ["وضعیت", committee.get("status") or "—"],
              ], "")}
              <h4>اعضا و سمت‌ها</h4>
              {_table_or_empty(["نام عضو", "کد ملی", "سمت", "نوع عضویت", "اداره/دستگاه", "موبایل", "وضعیت"], members_rows, "فاقد عضو ثبت‌شده است.")}
              <h4>جلسات</h4>
              {_table_or_empty(["عنوان", "تاریخ", "ساعت", "محل", "وضعیت"], meetings_rows, "جلسه‌ای ثبت نشده است.")}
              <h4>مصوبات</h4>
              {_table_or_empty(["عنوان", "مسئول", "دستگاه", "مهلت", "وضعیت"], resolutions_rows, "مصوبه‌ای ثبت نشده است.")}
              <h4>مسائل و اقدامات مرتبط</h4>
              {_table_or_empty(["نوع", "عنوان", "دستگاه", "وضعیت"], links_rows, "مورد مرتبطی ثبت نشده است.")}
            </div>
            """)
        committees_html = "".join(committee_sections)
    else:
        committees_html = '<p class="empty-note">کمیته‌ای برای این بلوک ثبت نشده است.</p>'

    body = f"""
    {snapshot_html}

    <h2 class="section-title">مشخصات پایه بلوک</h2>
    {_table_or_empty(["شاخص", "مقدار"], summary_rows, "مشخصات پایه در دسترس نیست.")}

    <h2 class="section-title">محل برگزاری جلسات</h2>
    {_table_or_empty(["فیلد", "مقدار"], meeting_rows, "هنوز محل جلسه‌ای ثبت نشده است.")}

    <h2 class="section-title">خیابان‌ها و کوچه‌ها (تعداد: {len(streets)})</h2>
    {_table_or_empty(["نام", "نوع معبر"], [[s["name"], s["highway_type"] or "—"] for s in streets], "خیابانی ثبت نشده است.")}

    <h2 class="section-title">سایر اماکن (تعداد: {len(places)})</h2>
    {_table_or_empty(["نام", "دسته", "نوع"], [[p["name"], p["category"] or "—", p["subtype"] or "—"] for p in places], "مکانی ثبت نشده است.")}

    <h2 class="section-title">مساجد داخل بلوک (تعداد: {len(mosques)})</h2>
    {_table_or_empty(["نام مسجد", "عرض", "طول"], [[m["name"], f"{m['lat']:.6f}", f"{m['lon']:.6f}"] for m in mosques], "مسجدی ثبت نشده است.")}

    <h2 class="section-title">اعضای شورای محلات (تعداد: {len(members)})</h2>
    {_table_or_empty(
        ["نام و نام خانوادگی", "دسته", "سمت", "موبایل"],
        [[f"{m['first_name']} {m['last_name']}", m["member_group"] or "—", m["position"] or "—", m["mobile"] or "—"] for m in members],
        "عضوی ثبت نشده است."
    )}

    <h2 class="section-title">کمیته‌های شش‌گانه، اعضا و سمت‌ها</h2>
    {committees_html}

    <h2 class="section-title">مکاتبات اداری مرتبط (تعداد: {len(correspondence_letters)})</h2>
    {_table_or_empty(
        ["شماره", "نوع", "موضوع", "فرستنده", "گیرنده", "مهلت", "وضعیت", "پیوست"],
        [[l.get("letter_number") or "—", l.get("direction") or "—", l.get("subject") or "—",
          l.get("sender") or "—", l.get("recipient") or "—", l.get("due_date") or "—",
          l.get("status") or "—", str(l.get("attachment_count") or 0)] for l in correspondence_letters],
        "مکاتبه‌ای برای این بلوک ثبت نشده است."
    )}

    <h2 class="section-title">بازدیدهای میدانی (تعداد: {len(field_visits)})</h2>
    {_table_or_empty(
        ["تاریخ", "کارشناس", "نوع", "موقعیت", "خانوار", "پیگیری", "وضعیت"],
        [[v.get("visit_date") or "—", v.get("officer_name") or "—", v.get("visit_type") or "—",
          v.get("location_text") or "—", str(v.get("households_count") or 0),
          "بله" if v.get("followup_required") else "خیر", v.get("status") or "—"] for v in field_visits],
        "بازدید میدانی ثبت نشده است."
    )}

    <h2 class="section-title">درخواست‌های مردمی (تعداد: {len(citizen_requests)})</h2>
    {_table_or_empty(
        ["کد رهگیری", "عنوان", "دسته", "فوریت", "دستگاه", "وضعیت"],
        [[r.get("tracking_code") or "—", r.get("title") or "—", r.get("category") or "—",
          str(r.get("urgency") or 0), r.get("assigned_office") or "—", r.get("status") or "—"]
         for r in citizen_requests],
        "درخواست مردمی ثبت نشده است."
    )}

    <h2 class="section-title">تحلیل عملیاتی بلوک</h2>
    {_table_or_empty(
        ["شاخص", "مقدار"],
        [["امتیاز ریسک", str(operational_analysis.get("risk_score", 0))],
         ["سطح ریسک", operational_analysis.get("risk_level") or "—"],
         ["درخواست باز", str(operational_analysis.get("open_requests", 0))],
         ["مسئله بحرانی", str(operational_analysis.get("critical_issues", 0))],
         ["اقدام معوق", str(operational_analysis.get("overdue_actions", 0))],
         ["شکاف خدماتی", str(operational_analysis.get("service_gap_count", 0))]],
        "تحلیل در دسترس نیست."
    )}

    <h2 class="section-title">درخواست‌ها و مشکلات (تعداد: {len(requests)})</h2>
    {_table_or_empty(
        ["شرح درخواست/مشکل", "اداره مرتبط", "تعداد اقدام"],
        [[r["description"], r["related_office"] or "—", str(r["action_count"])] for r in requests],
        "درخواستی ثبت نشده است."
    )}
    """
    return _wrap_report_html(f"گزارش کامل منطقه: {zone['name']}", body)



def build_correspondence_report_preview_html(db, zone_id=None):
    letters = db.get_correspondence_letters(zone_id=zone_id, limit=10000)
    assignments = []
    for letter in letters:
        assignments.extend(db.get_workflow_assignments(letter_id=letter["id"], limit=1000))
    title = "گزارش مکاتبات اداری"
    if zone_id is not None:
        zone = db.get_zone(zone_id)
        title += f" — {zone.get('name') if zone else zone_id}"
    body = f"""
    <h2 class="section-title">دفتر مکاتبات (تعداد: {len(letters)})</h2>
    {_table_or_empty(
        ["شماره", "نوع", "موضوع", "بلوک", "فرستنده", "گیرنده", "مهلت", "وضعیت", "اولویت"],
        [[l.get("letter_number") or "—", l.get("direction") or "—", l.get("subject") or "—",
          l.get("zone_name") or "—", l.get("sender") or "—", l.get("recipient") or "—",
          l.get("due_date") or "—", l.get("status") or "—", l.get("priority") or "—"] for l in letters],
        "مکاتبه‌ای ثبت نشده است."
    )}
    <h2 class="section-title">ارجاعات و پیگیری‌ها (تعداد: {len(assignments)})</h2>
    {_table_or_empty(
        ["شماره نامه", "موضوع", "ارجاع به", "دستور", "مهلت", "اولویت", "وضعیت", "پاسخ"],
        [[a.get("letter_number") or "—", a.get("subject") or "—", a.get("assigned_to_name") or "—",
          a.get("instruction") or "—", a.get("due_date") or "—", a.get("priority") or "—",
          a.get("status") or "—", a.get("response_text") or "—"] for a in assignments],
        "ارجاعی ثبت نشده است."
    )}
    """
    return _wrap_report_html(title, body)
