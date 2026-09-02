# -*- coding: utf-8 -*-
"""پیش‌نمایش HTML گزارش کامل بلوک با ترتیب یکسان با خروجی PDF."""

import base64
import html
import os
from jalali_utils import convert_dates_in_text
from committee_report_utils import get_zone_committee_report_data, member_display_role


def _image_to_base64(image_path):
    if not image_path or not os.path.exists(image_path):
        return None
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _snapshot_to_base64(db, zone_id, image_path=None):
    snapshot = db.get_zone_snapshot(zone_id) if hasattr(db, "get_zone_snapshot") else None
    if snapshot and snapshot.get("png_data"):
        return base64.b64encode(snapshot["png_data"]).decode("utf-8"), snapshot
    return _image_to_base64(image_path), snapshot


def _e(value):
    return html.escape(convert_dates_in_text(str(value if value not in (None, "") else "—")))


def _table(headers, rows):
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def build_block_full_report_preview_html(db, zone_id, map_image_path=None):
    zone = db.get_zone(zone_id)
    if not zone:
        return "<h1>منطقه یافت نشد</h1>"

    meeting_place = db.get_zone_meeting_place(zone_id)
    streets = db.get_streets(zone_id=zone_id)
    places = db.get_places(zone_id=zone_id)
    mosques = db.get_mosques(zone_id=zone_id)
    members = db.get_council_members(zone_id=zone_id)
    requests = db.get_priority_requests(zone_id=zone_id)
    profile = db.get_zone_profile(zone_id)
    issues = db.get_neighborhood_issues(zone_id)
    neighborhood_actions = db.get_neighborhood_actions(zone_id)
    meetings = db.get_neighborhood_meetings(zone_id)
    resolutions = db.get_neighborhood_resolutions(zone_id=zone_id)
    budgets = db.get_neighborhood_budgets(zone_id)
    budget_summary = db.get_budget_summary(zone_id)
    performance = db.get_zone_performance(zone_id)
    management_alerts = db.get_management_alerts(zone_id)
    quality_issues = db.get_quality_issues(zone_id)
    field_visits = db.get_field_visits(zone_id)
    citizen_requests = db.get_citizen_requests(zone_id)
    operational_analysis = db.get_zone_operational_analysis(zone_id)
    correspondence_letters = db.get_correspondence_letters(zone_id=zone_id)
    committees = get_zone_committee_report_data(db, zone_id)

    map_b64, snapshot_meta = _snapshot_to_base64(db, zone_id, map_image_path)
    if map_b64:
        version_text = ""
        if snapshot_meta:
            version_text = (
                f'<div class="snapshot-meta">نسخه تصویر: {_e(snapshot_meta.get("version", 1))} — '
                f'تولید: {_e(snapshot_meta.get("generated_at") or "—")}</div>'
            )
        map_html = (
            f'<div class="map-frame"><img class="block-map" '
            f'src="data:image/png;base64,{map_b64}" alt="نمای گرافیکی بلوک" /></div>{version_text}'
        )
    else:
        map_html = '<p class="empty-note">نمای گرافیکی بلوک هنوز تولید نشده است.</p>'

    summary_html = _table(
        ["شاخص", "مقدار"],
        [
            ["نام بلوک", zone.get("name")],
            ["وضعیت تکمیل", zone.get("status")],
            ["مساحت", f"{(zone.get('area_m2', 0) or 0)/10000:.2f} هکتار"],
            ["محیط", f"{zone.get('perimeter_m', 0) or 0:.0f} متر"],
            ["تعداد نقاط مرزی", len(zone.get("boundary_points", []))],
            ["تعداد خیابان و کوچه", len(streets)],
            ["تعداد سایر اماکن", len(places)],
            ["تعداد مساجد", len(mosques)],
            ["تعداد کمیته‌های تخصصی", len(committees)],
            ["اعضای فعال کمیته‌ها", sum(len(c.get("active_members") or []) for c in committees)],
            ["مصوبات باز کمیته‌ها", sum(1 for c in committees for r in (c.get("resolutions") or []) if r.get("status") not in ("انجام‌شده", "لغوشده"))],
            ["بازدیدهای میدانی", len(field_visits)],
            ["درخواست‌های مردمی", len(citizen_requests)],
            ["مکاتبات اداری مرتبط", len(correspondence_letters)],
            ["سطح ریسک عملیاتی", operational_analysis.get("risk_level")],
            ["تاریخ ایجاد", zone.get("created_at")],
            ["آخرین بروزرسانی", zone.get("updated_at")],
        ],
    )

    profile_html = _table(
        ["شاخص", "مقدار"],
        [
            ["ساختمان مسکونی", profile.get("residential_buildings", 0)],
            ["واحد مسکونی", profile.get("residential_units", 0)],
            ["واحد دارای سکنه", profile.get("occupied_units", 0)],
            ["خانوار محاسبه‌شده", profile.get("estimated_households", 0)],
            ["خانوار ثبت میدانی", profile.get("field_households", 0)],
            ["خانوار نهایی تأییدشده", profile.get("approved_households", 0)],
            ["جمعیت تخمینی", profile.get("estimated_population", 0)],
            ["روش برآورد", profile.get("estimation_method")],
            ["سطح اطمینان", profile.get("confidence_level")],
        ],
    )

    if meeting_place:
        meeting_html = _table(
            ["فیلد", "مقدار"],
            [
                ["نام مکان", meeting_place.get("place_name")],
                ["آدرس دقیق", meeting_place.get("exact_address")],
            ],
        )
    else:
        meeting_html = '<p class="empty-note">هنوز محل جلسه‌ای برای این بلوک ثبت نشده است.</p>'

    streets_html = (
        _table(
            ["ردیف", "نام معبر", "نوع"],
            [[i, street.get("name") or "معبر بدون نام", street.get("highway_type") or "—"]
             for i, street in enumerate(streets, start=1)],
        )
        if streets else '<p class="empty-note">معبری برای این بلوک ثبت نشده است.</p>'
    )

    places_html = (
        _table(
            ["ردیف", "نام مکان", "دسته", "نوع"],
            [[i, place.get("name"), place.get("category"), place.get("subtype")]
             for i, place in enumerate(places, start=1)],
        )
        if places else '<p class="empty-note">مکان دیگری برای این بلوک ثبت نشده است.</p>'
    )

    mosques_html = (
        _table(
            ["ردیف", "نام مسجد", "عرض", "طول"],
            [[i, mosque.get("name"), f"{mosque.get('lat'):.6f}", f"{mosque.get('lon'):.6f}"]
             for i, mosque in enumerate(mosques, start=1)],
        )
        if mosques else '<p class="empty-note">مسجدی داخل این بلوک ثبت نشده است.</p>'
    )

    members_html = (
        _table(
            ["نام و نام‌خانوادگی", "دسته", "سمت", "شماره تماس"],
            [[f"{m['first_name']} {m['last_name']}", m.get("member_group"), m.get("position"), m.get("mobile")]
             for m in members],
        )
        if members else '<p class="empty-note">عضوی برای این بلوک ثبت نشده است.</p>'
    )

    committee_sections = []
    if committees:
        committee_sections.append(_table(
            ["ردیف", "کمیته", "رئیس", "دبیر", "اعضا", "جلسات", "مصوبات باز", "وضعیت"],
            [[i, c.get("title"), c.get("chair_name"), c.get("secretary_name"),
              len(c.get("active_members") or []), len(c.get("meetings") or []),
              sum(1 for r in c.get("resolutions") or [] if r.get("status") not in ("انجام‌شده", "لغوشده")),
              c.get("status")] for i, c in enumerate(committees, start=1)],
        ))
        for committee in committees:
            profile_table = _table(
                ["مشخصه", "مقدار"],
                [["رئیس", committee.get("chair_name")], ["دبیر", committee.get("secretary_name")],
                 ["شماره حکم", committee.get("decree_no")], ["تاریخ حکم", committee.get("decree_date")],
                 ["دوره فعالیت", f"{committee.get('start_date') or '—'} تا {committee.get('end_date') or '—'}"],
                 ["دستگاه‌های پیشنهادی", committee.get("recommended_agencies")], ["وضعیت", committee.get("status")]],
            )
            members = committee.get("members") or []
            members_table = _table(
                ["نام عضو", "کد ملی", "سمت", "نوع عضویت", "اداره/دستگاه", "موبایل", "وضعیت"],
                [[m.get("person_name"), m.get("national_code"), member_display_role(m), m.get("member_type"),
                  m.get("agency_name"), m.get("mobile"), m.get("status")] for m in members],
            ) if members else '<p class="empty-note">فاقد عضو ثبت‌شده است.</p>'
            meetings = committee.get("meetings") or []
            meetings_table = _table(
                ["عنوان جلسه", "تاریخ", "ساعت", "محل", "وضعیت"],
                [[m.get("title"), m.get("meeting_date"), m.get("start_time"), m.get("place_name"), m.get("status")] for m in meetings],
            ) if meetings else '<p class="empty-note">جلسه‌ای ثبت نشده است.</p>'
            resolutions = committee.get("resolutions") or []
            resolutions_table = _table(
                ["عنوان مصوبه", "مسئول", "دستگاه", "مهلت", "وضعیت"],
                [[r.get("title"), r.get("responsible_person"), r.get("responsible_agency"), r.get("due_date"), r.get("status")] for r in resolutions],
            ) if resolutions else '<p class="empty-note">مصوبه‌ای ثبت نشده است.</p>'
            links = [["مسئله", x.get("title"), x.get("related_office"), x.get("status")] for x in committee.get("issues") or []]
            links += [["اقدام", x.get("title"), x.get("responsible_office"), x.get("status")] for x in committee.get("actions") or []]
            links_table = _table(["نوع", "عنوان", "دستگاه", "وضعیت"], links) if links else '<p class="empty-note">مسئله یا اقدامی متصل نشده است.</p>'
            committee_sections.append(
                f'<div class="committee-card"><h3>{_e(committee.get("title"))}</h3>'
                f'{profile_table}<h4>اعضا و سمت‌ها</h4>{members_table}'
                f'<h4>جلسات</h4>{meetings_table}<h4>مصوبات</h4>{resolutions_table}'
                f'<h4>مسائل و اقدامات مرتبط</h4>{links_table}</div>'
            )
        committees_html = "".join(committee_sections)
    else:
        committees_html = '<p class="empty-note">کمیته‌ای برای این بلوک ثبت نشده است.</p>'

    letters_html = (
        _table(
            ["شماره", "نوع", "موضوع", "فرستنده", "گیرنده", "مهلت", "وضعیت", "پیوست"],
            [[l.get("letter_number"), l.get("direction"), l.get("subject"), l.get("sender"),
              l.get("recipient"), l.get("due_date"), l.get("status"), l.get("attachment_count")]
             for l in correspondence_letters],
        ) if correspondence_letters else '<p class="empty-note">مکاتبه‌ای برای این بلوک ثبت نشده است.</p>'
    )

    visits_html = (
        _table(
            ["تاریخ", "کارشناس", "نوع", "موقعیت", "خانوار", "پیگیری", "وضعیت"],
            [[v.get("visit_date"), v.get("officer_name"), v.get("visit_type"), v.get("location_text"),
              v.get("households_count"), "بله" if v.get("followup_required") else "خیر", v.get("status")]
             for v in field_visits],
        ) if field_visits else '<p class="empty-note">بازدید میدانی ثبت نشده است.</p>'
    )

    citizen_html = (
        _table(
            ["کد رهگیری", "عنوان", "دسته", "فوریت", "دستگاه", "وضعیت", "مسئله مرتبط"],
            [[r.get("tracking_code"), r.get("title"), r.get("category"), r.get("urgency"),
              r.get("assigned_office"), r.get("status"), r.get("linked_issue_id")]
             for r in citizen_requests],
        ) if citizen_requests else '<p class="empty-note">درخواست مردمی ثبت نشده است.</p>'
    )

    operational_html = _table(
        ["شاخص", "مقدار"],
        [["امتیاز ریسک", operational_analysis.get("risk_score")],
         ["سطح ریسک", operational_analysis.get("risk_level")],
         ["درخواست باز", operational_analysis.get("open_requests")],
         ["درخواست فوری", operational_analysis.get("urgent_requests")],
         ["مسئله فوری/بحرانی", operational_analysis.get("critical_issues")],
         ["اقدام معوق", operational_analysis.get("overdue_actions")],
         ["شکاف خدماتی", operational_analysis.get("service_gap_count")],
         ["تراکم مسئله/هکتار", operational_analysis.get("issue_density_per_ha")],
         ["تراکم درخواست/هکتار", operational_analysis.get("request_density_per_ha")]]
    )

    issues_html = (
        _table(
            ["ردیف", "عنوان", "دسته", "امتیاز", "سطح", "وضعیت", "دستگاه"],
            [[i, issue.get("title"), issue.get("category"), issue.get("priority_score"),
              issue.get("priority_level"), issue.get("status"), issue.get("related_office")]
             for i, issue in enumerate(issues, start=1)],
        ) if issues else '<p class="empty-note">مسئله‌ای برای این بلوک ثبت نشده است.</p>'
    )

    actions_html = (
        _table(
            ["ردیف", "عنوان اقدام", "مسئول", "وضعیت", "پیشرفت", "پایان برنامه"],
            [[i, action.get("title"), action.get("responsible_office") or action.get("responsible_person"),
              action.get("status"), f"{action.get('progress_percent') or 0}٪", action.get("planned_end")]
             for i, action in enumerate(neighborhood_actions, start=1)],
        ) if neighborhood_actions else '<p class="empty-note">اقدام اجرایی ثبت نشده است.</p>'
    )

    meetings_html = (
        _table(
            ["ردیف", "عنوان", "تاریخ", "ساعت", "محل", "وضعیت"],
            [[i, meeting.get("title"), meeting.get("meeting_date"), meeting.get("start_time"),
              meeting.get("place_name"), meeting.get("status")]
             for i, meeting in enumerate(meetings, start=1)],
        ) if meetings else '<p class="empty-note">جلسه‌ای ثبت نشده است.</p>'
    )

    resolutions_html = (
        _table(
            ["ردیف", "عنوان مصوبه", "مسئول", "مهلت", "وضعیت"],
            [[i, resolution.get("title"), resolution.get("responsible_office") or resolution.get("responsible_person"),
              resolution.get("due_date"), resolution.get("status")]
             for i, resolution in enumerate(resolutions, start=1)],
        ) if resolutions else '<p class="empty-note">مصوبه‌ای ثبت نشده است.</p>'
    )

    budget_html = _table(
        ["شاخص", "مقدار"],
        [["اعتبار مصوب", f"{budget_summary.get('approved', 0):,.0f} ریال"],
         ["تخصیص‌یافته", f"{budget_summary.get('allocated', 0):,.0f} ریال"],
         ["هزینه‌شده", f"{budget_summary.get('spent', 0):,.0f} ریال"],
         ["مانده", f"{budget_summary.get('remaining', 0):,.0f} ریال"],
         ["درصد مصرف", f"{budget_summary.get('utilization_percent', 0):.1f}٪"]]
    )
    if budgets:
        budget_html += _table(
            ["ردیف", "عنوان", "منبع", "تخصیص", "هزینه", "وضعیت"],
            [[i, b.get("title"), b.get("funding_source"), f"{b.get('allocated_amount') or 0:,.0f}",
              f"{b.get('spent_amount') or 0:,.0f}", b.get("status")] for i, b in enumerate(budgets, start=1)]
        )

    performance_html = _table(
        ["شاخص", "مقدار"],
        [["امتیاز کل", f"{performance.get('total_score', 0):.1f} از ۱۰۰"],
         ["سطح عملکرد", performance.get("level")],
         ["تکمیل اطلاعات", f"{performance.get('completeness', 0):.1f}٪"],
         ["حل مسائل", f"{performance.get('issue_resolution', 0):.1f}٪"],
         ["تکمیل اقدامات", f"{performance.get('action_completion', 0):.1f}٪"],
         ["تحقق مصوبات", f"{performance.get('resolution_completion', 0):.1f}٪"],
         ["رعایت زمان‌بندی", f"{performance.get('timeliness', 0):.1f}٪"],
         ["کنترل مالی", f"{performance.get('financial_control', 0):.1f}٪"],
         ["پاسخ‌گویی و مشارکت", f"{performance.get('participation_response', 0):.1f}٪"]]
    )
    alerts_html = (
        _table(["سطح", "دسته", "عنوان", "توضیح", "مهلت"],
               [[a.get("severity"), a.get("category"), a.get("title"), a.get("detail"), a.get("due_date")]
                for a in management_alerts])
        if management_alerts else '<p class="empty-note">هشدار بازی وجود ندارد.</p>'
    )
    quality_html = (
        _table(["شدت", "دسته", "شرح مغایرت"],
               [[q.get("severity"), q.get("category"), q.get("message")] for q in quality_issues])
        if quality_issues else '<p class="empty-note">مغایرتی در پرونده شناسایی نشد.</p>'
    )

    return f"""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8" />
<title>پیش‌نمایش گزارش بلوک {_e(zone['name'])}</title>
<style>
  @page {{ size: A4 portrait; margin: 12mm 15mm 15mm; }}
  body {{ font-family: Tahoma, 'Vazirmatn', sans-serif; direction: rtl; background:#f4f5f7; color:#1c2530; margin:0; padding:24px; }}
  .report-container {{ max-width:900px; margin:0 auto; background:#fff; padding:32px; border-radius:8px; box-shadow:0 2px 10px rgba(0,0,0,.1); }}
  .header {{ text-align:center; border-bottom:3px solid #c9a227; padding-bottom:16px; margin-bottom:16px; }}
  .header h1 {{ color:#0b1f3a; margin:0 0 6px; font-size:22px; }}
  .header p {{ color:#5b6472; margin:0; font-size:13px; }}
  h2.section-title {{ color:#13294b; border-right:4px solid #c9a227; padding-right:10px; margin:22px 0 10px; font-size:16px; page-break-after:avoid; }}
  h4 {{ color:#13294b; margin:14px 0 6px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom:10px; page-break-inside:auto; }}
  tr {{ page-break-inside:avoid; }}
  th, td {{ border:1px solid #d7dbe3; padding:8px 10px; text-align:right; font-size:13px; }}
  th {{ background:#13294b; color:#fff; }}
  tbody tr:nth-child(even) {{ background:#f0f2f6; }}
  .map-frame {{ width:100%; height:125mm; display:flex; align-items:center; justify-content:center; overflow:hidden; border:1px solid #d7dbe3; border-radius:6px; background:#fff; page-break-inside:avoid; }}
  .block-map {{ max-width:100%; max-height:125mm; width:auto; height:auto; object-fit:contain; }}
  .empty-note {{ color:#5b6472; font-style:italic; background:#f0f2f6; padding:10px; border-radius:6px; }}
  .snapshot-meta {{ color:#5b6472; font-size:11px; margin-top:6px; text-align:center; }}
  .committee-card {{ border:1px solid #d7dbe3; border-radius:8px; padding:12px; margin:14px 0; page-break-inside:auto; }}
  .committee-card h3 {{ color:#13294b; margin:0 0 10px; border-bottom:2px solid #c9a227; padding-bottom:6px; }}
  @media print {{ body {{ background:#fff; padding:0; }} .report-container {{ box-shadow:none; max-width:100%; padding:0; }} }}
</style>
</head>
<body>
<div class="report-container">
  <div class="header">
    <h1>گزارش کامل بلوک: {_e(zone['name'])}</h1>
    <p>فرمانداری شهرستان جوانرود — سامانه جامع مدیریت محلات و بلوک‌های شهرستان جوانرود</p>
  </div>

  <h2 class="section-title">نمای گرافیکی بلوک</h2>
  {map_html}

  <h2 class="section-title">مشخصات پایه بلوک</h2>
  {summary_html}

  <h2 class="section-title">جمعیت و خانوار</h2>
  {profile_html}

  <h2 class="section-title">محل برگزاری جلسات</h2>
  {meeting_html}

  <h2 class="section-title">خیابان‌ها و کوچه‌ها</h2>
  {streets_html}

  <h2 class="section-title">سایر اماکن داخل بلوک</h2>
  {places_html}

  <h2 class="section-title">مساجد داخل بلوک</h2>
  {mosques_html}

  <h2 class="section-title">معتمدین و اعضای شورا</h2>
  {members_html}

  <h2 class="section-title">کمیته‌های شش‌گانه، اعضا و سمت‌ها</h2>
  {committees_html}

  <h2 class="section-title">مکاتبات اداری مرتبط</h2>
  {letters_html}

  <h2 class="section-title">بازدیدها و برداشت‌های میدانی</h2>
  {visits_html}

  <h2 class="section-title">درخواست‌ها و گزارش‌های مردمی</h2>
  {citizen_html}

  <h2 class="section-title">تحلیل عملیاتی بلوک</h2>
  {operational_html}

  <h2 class="section-title">مسائل و نیازهای محله</h2>
  {issues_html}

  <h2 class="section-title">اقدامات اجرایی</h2>
  {actions_html}

  <h2 class="section-title">جلسات شورای محله</h2>
  {meetings_html}

  <h2 class="section-title">مصوبات و پیگیری‌ها</h2>
  {resolutions_html}

  <h2 class="section-title">بودجه و هزینه</h2>
  {budget_html}

  <h2 class="section-title">ارزیابی عملکرد</h2>
  {performance_html}

  <h2 class="section-title">هشدارهای باز</h2>
  {alerts_html}

  <h2 class="section-title">کنترل کیفیت و مغایرت‌ها</h2>
  {quality_html}
</div>
</body>
</html>
"""
