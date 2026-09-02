# -*- coding: utf-8 -*-
"""تولید PDF ثابت صورتجلسه، مصوبات و برگ امضای اعضای کمیته."""

from __future__ import annotations

import io
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph, Image as RLImage
from reportlab.lib.styles import ParagraphStyle

from jalali_utils import iso_to_jalali, to_persian_digits
from committee_report_utils import member_display_role
from pdf_text_utils import shape_fa
import report_generator as _report_fonts

NAVY = colors.HexColor("#102f5c")
GOLD = colors.HexColor("#c99b39")
BORDER = colors.HexColor("#8b98a8")
LIGHT = colors.HexColor("#f4f7fa")


def _fa(value):
    return shape_fa(to_persian_digits(str(value or "—")))


def _truncate(text, limit):
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def _ensure_pdf_fonts():
    _report_fonts._ensure_fonts_registered()
    return _report_fonts.FONT_NAME, _report_fonts.FONT_NAME_BOLD


def _p(text, size=8, bold=False, align=2, leading=None, color=colors.black):
    regular, bold_name = _ensure_pdf_fonts()
    return Paragraph(
        _fa(text),
        ParagraphStyle(
            f"fa-{size}-{int(bold)}-{align}",
            fontName=bold_name if bold else regular,
            fontSize=size,
            leading=leading or size * 1.55,
            alignment=align,
            textColor=color,
        ),
    )

def _draw_flowable(c, flowable, x, y_top, width, available_height=1000 * mm):
    _w, height = flowable.wrap(width, available_height)
    flowable.drawOn(c, x, y_top - height)
    return y_top - height


def _base_table_style(font_size=8, header=False):
    regular, bold = _ensure_pdf_fonts()
    style = [
        ("FONTNAME", (0, 0), (-1, -1), regular),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.6, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [
            ("FONTNAME", (0, 0), (-1, 0), bold),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ]
    return style


def _draw_official_header(c, title, subtitle=None):
    page_width, page_height = A4
    x = 10 * mm
    width = page_width - 20 * mm
    y = page_height - 10 * mm
    header = Table(
        [[
            _p("وزارت کشور", 8, bold=True, align=1, color=NAVY),
            _p("استانداری کرمانشاه", 9, bold=True, align=1, color=NAVY),
            _p("فرمانداری شهرستان جوانرود", 11, bold=True, align=1, color=NAVY),
        ]],
        colWidths=[width / 3] * 3,
    )
    header.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1, GOLD),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#dce3eb")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    y = _draw_flowable(c, header, x, y, width)
    y -= 4 * mm
    y = _draw_flowable(c, _p(title, 14, bold=True, align=1, color=NAVY), x, y, width)
    if subtitle:
        y -= 1.5 * mm
        y = _draw_flowable(c, _p(subtitle, 9, bold=True, align=1, color=colors.HexColor("#4a5b70")), x, y, width)
    return y - 3 * mm


def _build_minutes_resolution_table(resolutions, width, max_height):
    if not resolutions:
        resolutions = [{"description": "—", "responsible_agency": "—", "due_date": None}]
    font_size = 8.0
    max_description = max(140, int(1700 / max(1, len(resolutions))))
    while True:
        rows = [[
            _p("مهلت انجام", font_size, bold=True, align=1, color=colors.white),
            _p("اداره پیگیری‌کننده", font_size, bold=True, align=1, color=colors.white),
            _p("شرح مصوبات", font_size, bold=True, align=1, color=colors.white),
            _p("ردیف", font_size, bold=True, align=1, color=colors.white),
        ]]
        for index, item in enumerate(resolutions, start=1):
            due = iso_to_jalali(item.get("due_date")) if item.get("due_date") else "—"
            rows.append([
                _p(due, font_size, align=1),
                _p(item.get("responsible_agency") or "—", font_size),
                _p(_truncate(item.get("description") or item.get("title") or "—", max_description), font_size),
                _p(index, font_size, align=1),
            ])
        table = Table(rows, colWidths=[30 * mm, 43 * mm, width - 91 * mm, 18 * mm], repeatRows=1)
        table.setStyle(TableStyle(_base_table_style(font_size, header=True) + [
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ]))
        _w, height = table.wrap(width, max_height)
        if height <= max_height or font_size <= 5.5:
            return table
        font_size -= 0.5
        max_description = max(80, int(max_description * 0.82))


def _draw_minutes_page(c, committee, meeting, resolutions):
    page_width, page_height = A4
    x = 10 * mm
    width = page_width - 20 * mm
    y = _draw_official_header(c, "صورتجلسه و مصوبات کمیته", committee.get("title") or "")

    number = meeting.get("meeting_number") or meeting.get("id") or "—"
    date_text = iso_to_jalali(meeting.get("meeting_date")) if meeting.get("meeting_date") else "—"
    time_text = meeting.get("start_time") or "—"
    count = len(resolutions)

    meta = Table([
        [
            _p(date_text, 9, align=1), _p("تاریخ جلسه", 8, bold=True, align=1),
            _p(time_text, 9, align=1), _p("ساعت جلسه", 8, bold=True, align=1),
            _p(number, 9, align=1), _p("شماره جلسه", 8, bold=True, align=1),
        ],
        [
            "", "", "", "",
            _p(count, 9, align=1), _p("تعداد مصوبات", 8, bold=True, align=1),
        ],
    ], colWidths=[32 * mm, 25 * mm, 27 * mm, 25 * mm, 32 * mm, 39 * mm])
    meta.setStyle(TableStyle(_base_table_style(8) + [
        ("BACKGROUND", (1, 0), (1, 0), LIGHT),
        ("BACKGROUND", (3, 0), (3, 0), LIGHT),
        ("BACKGROUND", (5, 0), (5, 1), LIGHT),
        ("SPAN", (0, 1), (3, 1)),
    ]))
    y = _draw_flowable(c, meta, x, y, width)
    y -= 3 * mm

    discussion = _truncate(meeting.get("minutes_text") or "—", 1800)
    discussion_para = _p(discussion, 8)
    _dw, discussion_height = discussion_para.wrap(width - 38 * mm, 55 * mm)
    discussion_row_height = min(55 * mm, max(35 * mm, discussion_height + 8 * mm))
    discussion_table = Table([
        [discussion_para, _p("شرح مذاکرات", 8, bold=True, align=1)]
    ], colWidths=[width - 30 * mm, 30 * mm], rowHeights=[discussion_row_height])
    discussion_table.setStyle(TableStyle(_base_table_style(8) + [
        ("BACKGROUND", (1, 0), (1, 0), LIGHT),
    ]))
    y = _draw_flowable(c, discussion_table, x, y, width)
    y -= 4 * mm
    y = _draw_flowable(c, _p("مصوبات", 11, bold=True, align=2, color=NAVY), x, y, width)
    y -= 2 * mm
    max_height = max(40 * mm, y - 14 * mm)
    table = _build_minutes_resolution_table(resolutions, width, max_height)
    _draw_flowable(c, table, x, y, width, max_height)
    c.setFont(_ensure_pdf_fonts()[0], 6.5)
    c.setFillColor(colors.HexColor("#64748b"))
    c.drawCentredString(page_width / 2, 7 * mm, _fa("فرمانداری شهرستان جوانرود - برگ مستقل صورتجلسه"))
    c.showPage()


def _signature_image(data, width=42 * mm, height=16 * mm):
    if not data:
        return _p("", 7, align=1)
    try:
        image = RLImage(io.BytesIO(bytes(data)), width=width, height=height)
        image.hAlign = "CENTER"
        return image
    except Exception:
        return _p("", 7, align=1)


def _draw_signature_pages(c, committee, meeting, members, signatures):
    page_width, page_height = A4
    x = 10 * mm
    width = page_width - 20 * mm
    chunks = [members[i:i + 8] for i in range(0, len(members), 8)] or [[]]
    for page_index, chunk in enumerate(chunks, start=1):
        y = _draw_official_header(c, "فهرست اعضای کمیته و محل امضا", committee.get("title") or "")
        number = meeting.get("meeting_number") or meeting.get("id") or "—"
        date_text = iso_to_jalali(meeting.get("meeting_date")) if meeting.get("meeting_date") else "—"
        meta_text = f"شماره جلسه: {number}     تاریخ جلسه: {date_text}"
        if len(chunks) > 1:
            meta_text += f"     صفحه {page_index} از {len(chunks)}"
        y = _draw_flowable(c, _p(meta_text, 9, bold=True, align=1, color=NAVY), x, y, width)
        y -= 3 * mm
        rows = [[
            _p("محل امضا", 8, bold=True, align=1, color=colors.white),
            _p("عضو", 8, bold=True, align=1, color=colors.white),
            _p("سمت", 8, bold=True, align=1, color=colors.white),
            _p("نام و نام خانوادگی", 8, bold=True, align=1, color=colors.white),
            _p("ردیف", 8, bold=True, align=1, color=colors.white),
        ]]
        for offset, member in enumerate(chunk, start=(page_index - 1) * 8 + 1):
            rows.append([
                _signature_image(signatures.get(member.get("id"))),
                _p(member.get("member_type") or "عضو", 8, align=1),
                _p(member_display_role(member), 8),
                _p(member.get("person_name") or "—", 8),
                _p(offset, 8, align=1),
            ])
        if not chunk:
            rows.append([_p("", 8), _p("—", 8), _p("—", 8), _p("عضوی ثبت نشده است", 8), _p("۱", 8, align=1)])
        table = Table(rows, colWidths=[48 * mm, 28 * mm, 38 * mm, 58 * mm, 18 * mm], repeatRows=1,
                      rowHeights=[10 * mm] + [23 * mm] * (len(rows) - 1))
        table.setStyle(TableStyle(_base_table_style(8, header=True) + [
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ]))
        _draw_flowable(c, table, x, y, width)
        c.setFont(_ensure_pdf_fonts()[0], 6.5)
        c.setFillColor(colors.HexColor("#64748b"))
        c.drawCentredString(page_width / 2, 7 * mm, _fa("فرمانداری شهرستان جوانرود - برگ مستقل فهرست اعضا و امضا"))
        c.showPage()


def generate_committee_minutes_pdf(output_path, committee, meeting, resolutions, members, signatures,
                                   include_minutes=True, include_signatures=True):
    """ساخت PDF ثابت؛ فرم و امضاها قبل از خروجی به محتوای ایستا تبدیل می‌شوند."""
    if not include_minutes and not include_signatures:
        raise ValueError("حداقل یکی از برگ‌های خروجی باید انتخاب شود.")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(output_path, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"صورتجلسه کمیته - {meeting.get('meeting_number') or meeting.get('id') or ''}")
    pdf.setAuthor("فرمانداری شهرستان جوانرود")
    if include_minutes:
        _draw_minutes_page(pdf, committee, meeting, resolutions)
    if include_signatures:
        _draw_signature_pages(pdf, committee, meeting, members, signatures)
    pdf.save()
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
        raise RuntimeError("فایل PDF ساخته نشد یا خروجی خالی است.")
    return output_path
