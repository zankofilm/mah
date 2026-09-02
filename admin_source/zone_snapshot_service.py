# -*- coding: utf-8 -*-
"""تولید و نگهداری نمای گرافیکی ثابت هر بلوک برای دیتابیس و گزارش‌ها."""

from __future__ import annotations

import hashlib
import html
import io
import json
import math
import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

from place_types import get_place_type_meta
from pdf_text_utils import shape_fa
from jalali_utils import now_jalali

Point = Tuple[float, float]

PRIMARY_HIGHWAYS = {"motorway", "trunk", "primary", "secondary", "tertiary"}
ALLEY_HIGHWAYS = {"service", "living_street", "track", "path", "footway", "pedestrian", "steps", "cycleway"}


def _font_path() -> str | None:
    candidates = [
        os.path.join(os.path.dirname(__file__), "fonts", "Vazirmatn-Regular.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        r"C:\Windows\Fonts\tahoma.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


def _font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend([
            os.path.join(os.path.dirname(__file__), "fonts", "Vazirmatn-Bold.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            r"C:\Windows\Fonts\tahomabd.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ])
    regular = _font_path()
    if regular:
        candidates.append(regular)
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(value: str, default=(30, 136, 229)):
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def _all_points(render_data: Dict[str, Any]) -> List[Point]:
    points: List[Point] = []
    points.extend(render_data.get("boundary") or [])
    for street in render_data.get("streets") or []:
        points.extend(street.get("geometry") or [])
    for key in ("mosques", "places"):
        for item in render_data.get(key) or []:
            if item.get("lat") is not None and item.get("lon") is not None:
                points.append((float(item["lat"]), float(item["lon"])))
    meeting = render_data.get("meeting_place")
    if meeting and meeting.get("lat") is not None and meeting.get("lon") is not None:
        points.append((float(meeting["lat"]), float(meeting["lon"])))
    return points


def _projection(points: Sequence[Point], width: int, height: int, margins=(70, 115, 70, 90)):
    left, top, right, bottom = margins
    if not points:
        return lambda lat, lon: (width / 2, height / 2), {"min_lat": 0, "max_lat": 0, "min_lon": 0, "max_lon": 0}
    lats = [float(p[0]) for p in points]
    lons = [float(p[1]) for p in points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat0 = (min_lat + max_lat) / 2.0
    mx = 111320.0 * max(0.2, math.cos(math.radians(lat0)))
    my = 110540.0
    span_x = max((max_lon - min_lon) * mx, 1.0)
    span_y = max((max_lat - min_lat) * my, 1.0)
    usable_w = max(1.0, width - left - right)
    usable_h = max(1.0, height - top - bottom)
    scale = min(usable_w / span_x, usable_h / span_y)
    drawn_w, drawn_h = span_x * scale, span_y * scale
    ox = left + (usable_w - drawn_w) / 2.0
    oy = top + (usable_h - drawn_h) / 2.0

    def project(lat, lon):
        x = ox + (float(lon) - min_lon) * mx * scale
        y = oy + (max_lat - float(lat)) * my * scale
        return (x, y)

    return project, {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon}


def build_zone_render_data(db, zone_id: int) -> Dict[str, Any]:
    zone = db.get_zone(zone_id)
    if not zone:
        raise ValueError("بلوک یافت نشد")
    streets = db.get_streets(zone_id=zone_id)
    places = db.get_places(zone_id=zone_id)
    mosques = db.get_mosques(zone_id=zone_id)
    meeting = db.get_zone_meeting_place(zone_id)
    alley_count = sum(1 for s in streets if (s.get("highway_type") or "") in ALLEY_HIGHWAYS)
    return {
        "zone": {
            "id": zone["id"], "name": zone["name"], "color": zone["color"],
            "area_m2": zone.get("area_m2", 0) or 0,
            "perimeter_m": zone.get("perimeter_m", 0) or 0,
            "updated_at": zone.get("updated_at") or zone.get("created_at"),
        },
        "boundary": [(float(p[0]), float(p[1])) for p in (zone.get("boundary_points") or [])],
        "streets": streets,
        "places": places,
        "mosques": mosques,
        "meeting_place": meeting,
        "stats": {
            "streets": len(streets) - alley_count,
            "alleys": alley_count,
            "places": len(places),
            "mosques": len(mosques),
        },
    }


def content_hash(render_data: Dict[str, Any]) -> str:
    canonical = json.dumps(render_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _draw_centered(draw, xy, text, font, fill):
    text = shape_fa(text)
    box = draw.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.text((xy[0] - w / 2, xy[1] - h / 2), text, font=font, fill=fill)


def generate_png(render_data: Dict[str, Any], width=1200, height=900) -> bytes:
    image = Image.new("RGB", (width, height), "#f7f9fc")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = _font(31, bold=True)
    subtitle_font = _font(18)
    label_font = _font(15)
    small_font = _font(13)
    icon_font = _font(17, bold=True)

    zone = render_data["zone"]
    zone_rgb = _hex_to_rgb(zone.get("color"))
    draw.rectangle((0, 0, width, 82), fill="#13294b")
    draw.text((width - 45, 18), shape_fa(f"نمای گرافیکی بلوک: {zone['name']}"), font=title_font, fill="white", anchor="ra")
    generated = now_jalali()
    draw.text((width - 45, 56), shape_fa(f"تولید: {generated}"), font=small_font, fill="#dce5f2", anchor="ra")

    points = _all_points(render_data)
    project, bbox = _projection(points, width, height)
    boundary = [project(lat, lon) for lat, lon in render_data.get("boundary") or []]
    if len(boundary) >= 3:
        draw.polygon(boundary, fill=(*zone_rgb, 38), outline=(*zone_rgb, 255))
        draw.line(boundary + [boundary[0]], fill=(*zone_rgb, 255), width=7, joint="curve")

    # معابر: کوچه نازک، خیابان اصلی ضخیم‌تر
    for street in render_data.get("streets") or []:
        geom = [project(p[0], p[1]) for p in street.get("geometry") or [] if len(p) >= 2]
        if len(geom) < 2:
            continue
        highway = street.get("highway_type") or ""
        if highway in PRIMARY_HIGHWAYS:
            color, line_w = (42, 83, 132, 245), 7
        elif highway in ALLEY_HIGHWAYS:
            color, line_w = (157, 116, 62, 210), 3
        else:
            color, line_w = (93, 111, 128, 225), 5
        draw.line(geom, fill=color, width=line_w, joint="curve")

    # برچسب محدود معابر برای جلوگیری از شلوغی
    used_names = set()
    labeled = 0
    for street in render_data.get("streets") or []:
        name = (street.get("name") or "").strip()
        geom = street.get("geometry") or []
        if not name or name in used_names or name.startswith("(") or len(geom) < 2 or labeled >= 18:
            continue
        used_names.add(name)
        mid = geom[len(geom) // 2]
        x, y = project(mid[0], mid[1])
        display = shape_fa(name[:32])
        box = draw.textbbox((0, 0), display, font=small_font)
        tw, th = box[2] - box[0], box[3] - box[1]
        draw.rounded_rectangle((x - tw / 2 - 4, y - th / 2 - 2, x + tw / 2 + 4, y + th / 2 + 2), 4, fill=(255, 255, 255, 190))
        draw.text((x, y), display, font=small_font, fill="#263238", anchor="mm")
        labeled += 1

    # اماکن عمومی با نشان اختصاصی نوع مکان
    place_palette = ["#1565c0", "#6a1b9a", "#00897b", "#ef6c00", "#455a64", "#ad1457"]
    for index, place in enumerate(render_data.get("places") or []):
        if place.get("lat") is None or place.get("lon") is None:
            continue
        x, y = project(place["lat"], place["lon"])
        meta = get_place_type_meta(place.get("subtype"))
        color = place_palette[abs(hash(meta["label"])) % len(place_palette)]
        draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=color, outline="white", width=2)
        code = (meta["label"] or "مکان")[0]
        _draw_centered(draw, (x, y), code, small_font, "white")
        if index < 14:
            name = shape_fa((place.get("name") or meta["label"])[:24])
            draw.text((x + 13, y), name, font=small_font, fill="#263238", anchor="lm")

    # مساجد
    for mosque in render_data.get("mosques") or []:
        x, y = project(mosque["lat"], mosque["lon"])
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill="#1b8a5a", outline="white", width=3)
        _draw_centered(draw, (x, y - 1), "م", icon_font, "white")
        name = mosque.get("name") or "مسجد"
        display = shape_fa(name)
        box = draw.textbbox((0, 0), display, font=small_font)
        tw, th = box[2] - box[0], box[3] - box[1]
        draw.rounded_rectangle((x - tw / 2 - 4, y + 14, x + tw / 2 + 4, y + 18 + th), 3, fill=(255, 255, 255, 210))
        draw.text((x, y + 16), display, font=small_font, fill="#145a3b", anchor="ma")

    # محل جلسه
    meeting = render_data.get("meeting_place")
    if meeting and meeting.get("lat") is not None and meeting.get("lon") is not None:
        x, y = project(meeting["lat"], meeting["lon"])
        draw.polygon([(x, y - 15), (x + 15, y), (x, y + 15), (x - 15, y)], fill="#d32f2f", outline="white")
        _draw_centered(draw, (x, y), "ج", icon_font, "white")
        draw.text((x + 20, y), shape_fa(meeting.get("place_name") or "محل جلسه"), font=label_font, fill="#8b1d1d", anchor="lm")

    # شمال‌نما
    draw.polygon([(65, 125), (52, 158), (65, 151), (78, 158)], fill="#13294b")
    _draw_centered(draw, (65, 110), "N", _font(18, True), "#13294b")

    # کادر آمار و راهنما
    stats = render_data.get("stats") or {}
    footer_y = height - 72
    draw.rectangle((0, footer_y, width, height), fill="#ffffff")
    draw.line((0, footer_y, width, footer_y), fill="#d7dbe3", width=2)
    summary = (
        f"خیابان: {stats.get('streets', 0)}    کوچه: {stats.get('alleys', 0)}    "
        f"مسجد: {stats.get('mosques', 0)}    مکان: {stats.get('places', 0)}    "
        f"مساحت: {(zone.get('area_m2', 0) or 0)/10000:.2f} هکتار"
    )
    draw.text((width - 35, footer_y + 20), shape_fa(summary), font=subtitle_font, fill="#263238", anchor="ra")

    # راهنمای رنگ
    lx = 35
    legend = [
        ("مرز بلوک", zone_rgb), ("خیابان", (42, 83, 132)), ("کوچه", (157, 116, 62)),
        ("مسجد", (27, 138, 90)), ("محل جلسه", (211, 47, 47)),
    ]
    for title, color in legend:
        draw.rectangle((lx, footer_y + 23, lx + 18, footer_y + 41), fill=color)
        draw.text((lx + 24, footer_y + 20), shape_fa(title), font=small_font, fill="#455a64")
        lx += 115

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def generate_thumbnail(png_data: bytes, width=400, height=300) -> bytes:
    image = Image.open(io.BytesIO(png_data)).convert("RGB")
    image.thumbnail((width, height), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def generate_svg(render_data: Dict[str, Any], width=1200, height=900) -> str:
    zone = render_data["zone"]
    points = _all_points(render_data)
    project, _ = _projection(points, width, height)
    zone_color = zone.get("color") or "#1e88e5"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f9fc"/>',
        '<rect width="100%" height="82" fill="#13294b"/>',
        f'<text x="{width-45}" y="48" text-anchor="end" direction="rtl" font-family="Tahoma,DejaVu Sans" font-size="31" font-weight="bold" fill="white">{html.escape("نمای گرافیکی بلوک: " + zone["name"])}</text>',
    ]
    boundary = [project(p[0], p[1]) for p in render_data.get("boundary") or []]
    if len(boundary) >= 3:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in boundary)
        parts.append(f'<polygon points="{pts}" fill="{zone_color}" fill-opacity="0.15" stroke="{zone_color}" stroke-width="7"/>')
    for street in render_data.get("streets") or []:
        geom = [project(p[0], p[1]) for p in street.get("geometry") or [] if len(p) >= 2]
        if len(geom) < 2:
            continue
        highway = street.get("highway_type") or ""
        if highway in PRIMARY_HIGHWAYS:
            color, line_w = "#2a5384", 7
        elif highway in ALLEY_HIGHWAYS:
            color, line_w = "#9d743e", 3
        else:
            color, line_w = "#5d6f80", 5
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in geom)
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{line_w}" stroke-linecap="round" stroke-linejoin="round"/>')
    place_palette = ["#1565c0", "#6a1b9a", "#00897b", "#ef6c00", "#455a64", "#ad1457"]
    for place in render_data.get("places") or []:
        if place.get("lat") is None or place.get("lon") is None:
            continue
        x, y = project(place["lat"], place["lon"])
        meta = get_place_type_meta(place.get("subtype"))
        color = place_palette[abs(hash(meta["label"])) % len(place_palette)]
        icon = html.escape(meta.get("icon") or "📍")
        name = html.escape(place.get("name") or meta["label"])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{color}" stroke="white" stroke-width="2"><title>{name}</title></circle>')
        parts.append(f'<text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-family="Segoe UI Emoji,Apple Color Emoji,Tahoma" font-size="13" fill="white">{icon}</text>')

    for mosque in render_data.get("mosques") or []:
        x, y = project(mosque["lat"], mosque["lon"])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="#1b8a5a" stroke="white" stroke-width="3"/>')
        parts.append(f'<text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-family="Tahoma,DejaVu Sans" font-size="15" font-weight="bold" fill="white">م</text>')
    meeting = render_data.get("meeting_place")
    if meeting and meeting.get("lat") is not None and meeting.get("lon") is not None:
        x, y = project(meeting["lat"], meeting["lon"])
        pts = f"{x:.1f},{y-15:.1f} {x+15:.1f},{y:.1f} {x:.1f},{y+15:.1f} {x-15:.1f},{y:.1f}"
        parts.append(f'<polygon points="{pts}" fill="#d32f2f" stroke="white" stroke-width="2"/>')
    stats = render_data.get("stats") or {}
    footer_y = height - 72
    summary = f"خیابان: {stats.get('streets',0)} | کوچه: {stats.get('alleys',0)} | مسجد: {stats.get('mosques',0)} | مکان: {stats.get('places',0)} | مساحت: {(zone.get('area_m2',0) or 0)/10000:.2f} هکتار"
    parts.extend([
        f'<rect x="0" y="{footer_y}" width="{width}" height="72" fill="white" stroke="#d7dbe3"/>',
        f'<text x="{width-35}" y="{footer_y+42}" text-anchor="end" direction="rtl" font-family="Tahoma,DejaVu Sans" font-size="18" fill="#263238">{html.escape(summary)}</text>',
        '</svg>',
    ])
    return "".join(parts)


def refresh_zone_snapshot(db, zone_id: int, force: bool = False) -> Dict[str, Any]:
    render_data = build_zone_render_data(db, zone_id)
    current_hash = content_hash(render_data)
    existing = db.get_zone_snapshot(zone_id)
    if existing and not force and existing.get("content_hash") == current_hash and existing.get("render_status") == "ready":
        return existing
    try:
        svg_text = generate_svg(render_data)
        png_data = generate_png(render_data)
        thumb_data = generate_thumbnail(png_data)
        db.save_zone_snapshot(
            zone_id=zone_id,
            svg_text=svg_text,
            png_data=png_data,
            thumbnail_data=thumb_data,
            content_hash=current_hash,
            width=1200,
            height=900,
            render_status="ready",
            error_message=None,
        )
        return db.get_zone_snapshot(zone_id)
    except Exception as exc:
        db.save_zone_snapshot(
            zone_id=zone_id,
            svg_text=None,
            png_data=None,
            thumbnail_data=None,
            content_hash=current_hash,
            width=1200,
            height=900,
            render_status="error",
            error_message=str(exc),
        )
        raise


def export_zone_snapshot_png(db, zone_id: int, output_path: str, force_refresh: bool = False) -> bool:
    snapshot = refresh_zone_snapshot(db, zone_id, force=force_refresh)
    data = snapshot.get("png_data") if snapshot else None
    if not data:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_path = output_path + ".tmp"
    with open(temp_path, "wb") as f:
        f.write(data)
    os.replace(temp_path, output_path)
    return True


def export_zone_snapshot_svg(db, zone_id: int, output_path: str, force_refresh: bool = False) -> bool:
    snapshot = refresh_zone_snapshot(db, zone_id, force=force_refresh)
    data = snapshot.get("svg_text") if snapshot else None
    if not data:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    temp_path = output_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(temp_path, output_path)
    return True
