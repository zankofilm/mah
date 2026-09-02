# -*- coding: utf-8 -*-
"""پیش‌نمایش HTML گزارش عمومی A4 بلوک."""

import base64
import html
import os
from jalali_utils import convert_dates_in_text, now_jalali


def _e(value):
    return html.escape(convert_dates_in_text(str(value if value not in (None, "") else "—")))


def _map_base64(db, zone_id, image_path=None):
    snapshot = db.get_zone_snapshot(zone_id) if hasattr(db, "get_zone_snapshot") else None
    if snapshot and snapshot.get("png_data"):
        return base64.b64encode(snapshot["png_data"]).decode("ascii")
    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("ascii")
    return None


def build_block_public_report_preview_html(db, zone_id, map_image_path=None):
    zone = db.get_zone(zone_id)
    if not zone:
        return "<h1>منطقه یافت نشد</h1>"

    members = [
        member for member in db.get_council_members(zone_id=zone_id)
        if "معتمد" in str(member.get("member_group") or "")
    ]
    rows = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{_e(((member.get('first_name') or '') + ' ' + (member.get('last_name') or '')).strip())}</td>"
        f"<td>{_e(member.get('national_code'))}</td>"
        f"<td>{_e(member.get('mobile'))}</td>"
        f"<td>{_e(member.get('position'))}</td>"
        "</tr>"
        for index, member in enumerate(members, start=1)
    )
    if not rows:
        rows = '<tr><td colspan="5" class="empty">عضو معتمدی برای این بلوک ثبت نشده است.</td></tr>'

    map_b64 = _map_base64(db, zone_id, map_image_path)
    map_html = (
        f'<img src="data:image/png;base64,{map_b64}" alt="نقشه بلوک" />'
        if map_b64 else '<div class="empty-map">نمای نقشه بلوک هنوز تولید نشده است.</div>'
    )

    return f'''<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش عمومی بلوک</title>
<style>
@page {{ size:A4 portrait; margin:12mm; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#e9edf2; font-family:Tahoma,Vazirmatn,sans-serif; color:#1c2530; direction:rtl; }}
.page {{ width:210mm; min-height:297mm; margin:18px auto; background:#fff; padding:11mm 12mm; box-shadow:0 3px 18px #0002; }}
header {{ text-align:center; border-bottom:2px solid #c9a227; padding-bottom:5mm; }}
header .org {{ font-size:14px; font-weight:bold; color:#13294b; }}
header h1 {{ font-size:20px; color:#13294b; margin:3mm 0 1mm; }}
header .date {{ font-size:11px; color:#5b6472; text-align:right; }}
.map {{ height:62mm; margin-top:5mm; border:1px solid #cbd2dc; border-radius:7px; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
.map img {{ max-width:100%; max-height:100%; object-fit:contain; }}
.empty-map {{ color:#5b6472; }}
h2 {{ font-size:15px; color:#13294b; margin:6mm 0 3mm; border-right:4px solid #c9a227; padding-right:3mm; }}
table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
th,td {{ border:1px solid #d7dbe3; padding:2.4mm; text-align:center; font-size:11px; overflow-wrap:anywhere; }}
th {{ background:#13294b; color:#fff; }}
tbody tr:nth-child(even) {{ background:#f0f2f6; }}
th:nth-child(1),td:nth-child(1) {{ width:9%; }}
th:nth-child(2),td:nth-child(2) {{ width:34%; }}
th:nth-child(3),td:nth-child(3) {{ width:18%; }}
th:nth-child(4),td:nth-child(4) {{ width:18%; }}
th:nth-child(5),td:nth-child(5) {{ width:21%; }}
.empty {{ color:#5b6472; padding:8mm; }}
footer {{ text-align:center; color:#7a8491; font-size:9px; margin-top:5mm; }}
@media print {{ body {{ background:#fff; }} .page {{ margin:0; box-shadow:none; }} }}
</style>
</head>
<body>
<div class="page">
<header>
<div class="org">فرمانداری شهرستان جوانرود</div>
<h1>گزارش عمومی بلوک: {_e(zone.get('name'))}</h1>
<div class="date">تاریخ تهیه: {_e(now_jalali())}</div>
</header>
<section class="map">{map_html}</section>
<h2>جدول اعضای معتمد - تعداد: {len(members)}</h2>
<table>
<thead><tr><th>ردیف</th><th>نام و نام خانوادگی</th><th>کد ملی</th><th>شماره تماس</th><th>سمت</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<footer>سامانه مدیریت محلات جوانرود</footer>
</div>
</body>
</html>'''
