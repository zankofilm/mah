# -*- coding: utf-8 -*-
"""تولید درگاه عمومی ایستا و بدون داده شخصی برای پروژه مدیریت محله‌محور."""

import json
import os
from datetime import datetime
from html import escape
from jalali_utils import now_jalali, convert_dates_in_text, format_jalali


def _safe_number(value, digits=0):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        number = 0.0
    return round(number, digits)


def build_public_dataset(db):
    zones = []
    for zone in db.get_zones():
        zid = zone["id"]
        profile = db.get_zone_profile(zid) or {}
        issues = db.get_neighborhood_issues(zid)
        actions = db.get_neighborhood_actions(zid)
        projects = db.get_projects(zone_id=zid)
        surveys = db.get_satisfaction_surveys(zone_id=zid)
        avg_satisfaction = (
            sum(float(x.get("satisfaction_percent") or 0) for x in surveys) / len(surveys)
            if surveys else 0
        )
        zones.append({
            "id": zid,
            "name": zone.get("name") or "بدون نام",
            "status": zone.get("status") or "نامشخص",
            "area_hectares": _safe_number((zone.get("area_m2") or 0) / 10000, 2),
            "approved_households": int(profile.get("approved_households") or 0),
            "estimated_population": int(profile.get("estimated_population") or 0),
            "open_issues": sum(1 for x in issues if x.get("status") not in ("مختومه", "انجام‌شده")),
            "active_actions": sum(1 for x in actions if x.get("status") not in ("تکمیل‌شده", "لغوشده")),
            "projects": len(projects),
            "average_satisfaction": _safe_number(avg_satisfaction, 1),
        })

    published_projects = []
    for project in db.get_projects():
        gov = db.get_record_governance("project", project["id"])
        if not gov or not gov.get("is_public") or gov.get("lifecycle_status") != "تأییدشده":
            continue
        zone = db.get_zone(project.get("zone_id")) if project.get("zone_id") else None
        published_projects.append({
            "code": project.get("project_code") or "—",
            "title": project.get("title") or "بدون عنوان",
            "zone": (zone or {}).get("name") or "کل شهر",
            "status": project.get("status") or "نامشخص",
            "progress_percent": _safe_number(project.get("progress_percent"), 1),
            "planned_start": project.get("planned_start") or "",
            "planned_end": project.get("planned_end") or "",
        })

    request_stats = {}
    for request in db.get_citizen_requests():
        category = request.get("category") or "سایر"
        item = request_stats.setdefault(category, {"category": category, "total": 0, "closed": 0})
        item["total"] += 1
        if request.get("status") in ("پاسخ‌داده‌شده", "مختومه"):
            item["closed"] += 1

    return {
        "portal_title": "درگاه عمومی مدیریت محلات جوانرود",
        "generated_at": now_jalali(with_seconds=True),
        "privacy_note": "این خروجی فقط شامل آمار تجمیعی و اطلاعات عمومی تأییدشده است و هیچ نام، شماره تماس یا مکاتبه محرمانه‌ای منتشر نمی‌کند.",
        "summary": {
            "zones": len(zones),
            "households": sum(x["approved_households"] for x in zones),
            "population": sum(x["estimated_population"] for x in zones),
            "open_issues": sum(x["open_issues"] for x in zones),
            "published_projects": len(published_projects),
        },
        "zones": zones,
        "projects": published_projects,
        "request_statistics": sorted(request_stats.values(), key=lambda x: (-x["total"], x["category"])),
    }


def _render_html(data):
    summary = data["summary"]
    zone_rows = "".join(
        f"<tr><td>{escape(z['name'])}</td><td>{z['approved_households']}</td><td>{z['estimated_population']}</td>"
        f"<td>{z['open_issues']}</td><td>{z['active_actions']}</td><td>{z['average_satisfaction']}٪</td></tr>"
        for z in data["zones"]
    ) or "<tr><td colspan='6'>هنوز اطلاعاتی منتشر نشده است.</td></tr>"
    project_cards = "".join(
        f"<article class='project'><h3>{escape(p['title'])}</h3><p>{escape(p['code'])} — {escape(p['zone'])}</p>"
        f"<div class='progress'><span style='width:{max(0,min(100,p['progress_percent']))}%'></span></div>"
        f"<small>{escape(p['status'])} — پیشرفت {p['progress_percent']}٪</small></article>"
        for p in data["projects"]
    ) or "<p class='empty'>هیچ پروژه‌ای برای انتشار عمومی تأیید نشده است.</p>"
    request_rows = "".join(
        f"<tr><td>{escape(x['category'])}</td><td>{x['total']}</td><td>{x['closed']}</td></tr>"
        for x in data["request_statistics"]
    ) or "<tr><td colspan='3'>داده‌ای ثبت نشده است.</td></tr>"
    return f"""<!doctype html>
<html lang='fa' dir='rtl'>
<head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{escape(data['portal_title'])}</title>
<style>
body{{margin:0;background:#f3f5f8;color:#172033;font-family:Tahoma,Arial,sans-serif;line-height:1.8}}
header{{background:linear-gradient(135deg,#0b1f3a,#1f3a63);color:white;padding:28px 6%;border-bottom:5px solid #c9a227}}
header h1{{margin:0;color:#f2d46b}} header p{{margin:4px 0 0;color:#d8e0ec}}
main{{max-width:1180px;margin:22px auto;padding:0 18px}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}}
.card,.section,.project{{background:white;border:1px solid #d9dfe8;border-radius:14px;box-shadow:0 8px 22px rgba(21,39,68,.08)}}
.card{{padding:18px;text-align:center}} .card b{{display:block;font-size:28px;color:#13294b}} .section{{padding:20px;margin-top:18px}}
table{{width:100%;border-collapse:collapse}} th{{background:#13294b;color:white}} th,td{{padding:9px;border:1px solid #dde2e9;text-align:center}}
.projects{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}} .project{{padding:16px}} .project h3{{margin:0 0 4px}}
.progress{{height:10px;background:#e6ebf2;border-radius:8px;overflow:hidden;margin:10px 0}} .progress span{{display:block;height:100%;background:#2b7a3d}}
.note{{background:#fff8dc;border-right:5px solid #c9a227;padding:12px 16px;border-radius:8px}} .empty{{color:#697386}}
footer{{text-align:center;padding:22px;color:#687386}}
</style></head>
<body><header><h1>{escape(data['portal_title'])}</h1><p>آخرین بروزرسانی: {escape(data['generated_at'])}</p></header>
<main><div class='note'>{escape(data['privacy_note'])}</div>
<section class='cards'>
<div class='card'><b>{summary['zones']}</b>بلوک</div><div class='card'><b>{summary['households']}</b>خانوار تأییدشده</div>
<div class='card'><b>{summary['population']}</b>جمعیت تخمینی</div><div class='card'><b>{summary['open_issues']}</b>مسئله باز</div>
<div class='card'><b>{summary['published_projects']}</b>پروژه عمومی</div></section>
<section class='section'><h2>وضعیت بلوک‌ها</h2><table><thead><tr><th>بلوک</th><th>خانوار</th><th>جمعیت</th><th>مسئله باز</th><th>اقدام فعال</th><th>رضایت</th></tr></thead><tbody>{zone_rows}</tbody></table></section>
<section class='section'><h2>پروژه‌های عمومی تأییدشده</h2><div class='projects'>{project_cards}</div></section>
<section class='section'><h2>آمار تجمیعی درخواست‌های مردمی</h2><table><thead><tr><th>دسته‌بندی</th><th>کل</th><th>پاسخ‌داده‌شده/مختومه</th></tr></thead><tbody>{request_rows}</tbody></table></section>
</main><footer>سامانه مدیریت محلات جوانرود — خروجی عمومی بدون اطلاعات شخصی</footer></body></html>"""


def generate_public_portal(db, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    data = build_public_dataset(db)
    data_path = os.path.join(output_dir, "data.json")
    html_path = os.path.join(output_dir, "index.html")
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(_render_html(data))
    db.register_publication(
        data["portal_title"], html_path,
        zones_count=data["summary"]["zones"],
        projects_count=data["summary"]["published_projects"],
        requests_count=sum(x["total"] for x in data["request_statistics"]),
    )
    return {"html_path": html_path, "data_path": data_path, "data": data}
