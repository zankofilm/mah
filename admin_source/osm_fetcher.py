# -*- coding: utf-8 -*-
"""دریافت و پردازش داده‌های OpenStreetMap در محدوده دقیق چندضلعی."""

from __future__ import annotations

import json
import os
from runtime_paths import get_data_dir
import time
from typing import Dict, Iterable, List, Sequence

import requests

from geometry_utils import clip_polyline_to_polygon, normalize_polygon, point_in_polygon

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

REQUEST_HEADERS = {
    "User-Agent": "JavanroodMapApp/4.0 (desktop municipal GIS; contact: local administrator)",
    "Accept": "application/json,text/plain,*/*",
    "Content-Type": "application/x-www-form-urlencoded",
}

PLACE_QUERY_TAGS = [
    ("amenity", "school", "مدرسه"),
    ("amenity", "kindergarten", "مهدکودک"),
    ("amenity", "university", "دانشگاه"),
    ("amenity", "college", "آموزشکده"),
    ("amenity", "hospital", "بیمارستان"),
    ("amenity", "clinic", "درمانگاه"),
    ("amenity", "pharmacy", "داروخانه"),
    ("amenity", "police", "کلانتری/پلیس"),
    ("amenity", "fire_station", "آتش‌نشانی"),
    ("amenity", "townhall", "شهرداری/ساختمان دولتی"),
    ("amenity", "courthouse", "دادگاه"),
    ("amenity", "post_office", "اداره پست"),
    ("amenity", "bank", "بانک"),
    ("amenity", "place_of_worship", "مسجد/مکان مذهبی"),
    ("office", "government", "اداره دولتی"),
    ("landuse", "military", "نظامی"),
    ("amenity", "doctors", "مطب پزشک"),
    ("healthcare", "clinic", "درمانگاه (شبکه بهداشت)"),
    ("healthcare", "center", "مرکز بهداشت"),
    ("amenity", "social_facility", "خانه بهداشت/مرکز خدمات اجتماعی"),
    ("building", "mosque", "مسجد/مکان مذهبی"),
    ("amenity", "mosque", "مسجد/مکان مذهبی"),
    ("building", "school", "مدرسه"),
]


def _validate_boundary(points: Iterable[Sequence[float]]) -> List[tuple]:
    polygon = normalize_polygon(points)
    if len(polygon) < 3:
        raise ValueError("محدوده باید حداقل سه نقطه معتبر داشته باشد.")
    return polygon


def _polygon_to_overpass_poly(points):
    polygon = _validate_boundary(points)
    return " ".join(f"{lat:.8f} {lon:.8f}" for lat, lon in polygon)


def build_streets_query(boundary_points):
    poly = _polygon_to_overpass_poly(boundary_points)
    return f"""
    [out:json][timeout:120];
    way["highway"](poly:"{poly}");
    out body geom;
    """


def build_places_query(boundary_points):
    poly = _polygon_to_overpass_poly(boundary_points)
    place_queries = [f'nwr["{key}"="{value}"](poly:"{poly}");' for key, value, _ in PLACE_QUERY_TAGS]
    return f"""
    [out:json][timeout:150];
    (
      {''.join(place_queries)}
    );
    out body geom center;
    """


def build_overpass_query(boundary_points):
    """نسخه ترکیبی برای سازگاری با کدهای قدیمی."""
    poly = _polygon_to_overpass_poly(boundary_points)
    place_queries = []
    for key, value, _ in PLACE_QUERY_TAGS:
        place_queries.extend([
            f'node["{key}"="{value}"](poly:"{poly}");',
            f'way["{key}"="{value}"](poly:"{poly}");',
            f'relation["{key}"="{value}"](poly:"{poly}");',
        ])
    return f"""
    [out:json][timeout:180];
    (
      way["highway"](poly:"{poly}");
      {''.join(place_queries)}
    );
    out body geom center;
    """


def _run_overpass_query(query, progress_callback=None, label=""):
    """اجرای محدود و قابل‌فهم درخواست آنلاین؛ در نبود شبکه سریع متوقف می‌شود."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    transient_failures = 0

    for server_index, url in enumerate(OVERPASS_URLS[:4], start=1):
        try:
            if progress_callback:
                progress_callback(f"{label} اتصال به سرور {server_index}/4")
            response = session.post(url, data={"data": query}, timeout=(6, 90))
            if response.status_code == 429 or 500 <= response.status_code < 600:
                transient_failures += 1
                continue
            response.raise_for_status()
            data = response.json()
            if data.get("remark") and not data.get("elements"):
                transient_failures += 1
                continue
            if not isinstance(data.get("elements", []), list):
                transient_failures += 1
                continue
            if progress_callback:
                progress_callback(f"{label} پاسخ معتبر دریافت شد.")
            return data
        except requests.exceptions.ConnectionError as exc:
            text = str(exc).lower()
            if any(token in text for token in ("nameresolution", "failed to resolve", "getaddrinfo failed")):
                raise RuntimeError("اتصال اینترنت یا سامانه DNS در دسترس نیست.") from None
            transient_failures += 1
        except requests.exceptions.ConnectTimeout:
            transient_failures += 1
            if transient_failures >= 2:
                break
        except requests.exceptions.ReadTimeout:
            transient_failures += 1
        except Exception:
            transient_failures += 1

    raise RuntimeError(
        f"{label} سرویس آنلاین OpenStreetMap/Overpass در دسترس نیست؛ بعداً دوباره تلاش کنید."
    )


def _save_debug_json(filename: str, data: Dict) -> None:
    try:
        data_dir = get_data_dir()
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, filename), "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _localized_name(tags: Dict, fallback: str = "") -> str:
    for key in ("name:fa", "name:ckb", "name:ku", "name"):
        value = (tags.get(key) or "").strip()
        if value:
            return value
    return fallback


def _element_center(element: Dict):
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        return center.get("lat"), center.get("lon")
    geometry = element.get("geometry") or []
    valid = [(p.get("lat"), p.get("lon")) for p in geometry if p.get("lat") is not None and p.get("lon") is not None]
    if valid:
        return sum(p[0] for p in valid) / len(valid), sum(p[1] for p in valid) / len(valid)
    all_points = [
        (p.get("lat"), p.get("lon"))
        for member in element.get("members", [])
        for p in (member.get("geometry") or [])
        if p.get("lat") is not None and p.get("lon") is not None
    ]
    if all_points:
        return sum(p[0] for p in all_points) / len(all_points), sum(p[1] for p in all_points) / len(all_points)
    bounds = element.get("bounds") or {}
    if all(k in bounds for k in ("minlat", "maxlat", "minlon", "maxlon")):
        return (bounds["minlat"] + bounds["maxlat"]) / 2, (bounds["minlon"] + bounds["maxlon"]) / 2
    return None, None


def fetch_osm_data(boundary_points, progress_callback=None):
    """
    خیابان‌ها و اماکن را مستقل دریافت می‌کند و هندسه خیابان را دقیقاً به مرز بلوک برش می‌دهد.
    شکست یک بخش باعث حذف یا از دست رفتن نتیجه موفق بخش دیگر نمی‌شود.
    """
    polygon = _validate_boundary(boundary_points)
    streets, places = [], []
    streets_ok = places_ok = False
    errors = {}
    unmatched_tags = set()
    government_tag_samples = []
    dropped_no_coords = []
    street_stats = {
        "raw_ways": 0,
        "saved_fragments": 0,
        "unnamed_ways": 0,
        "outside_ways": 0,
        "invalid_ways": 0,
    }
    place_stats = {"raw_elements": 0, "saved": 0, "outside": 0, "no_coords": 0, "duplicates": 0}

    try:
        raw = _run_overpass_query(build_streets_query(polygon), progress_callback, "[خیابان‌ها]")
        _save_debug_json("last_streets_raw.json", raw)
        seen_fragments = set()
        for element in raw.get("elements", []):
            tags = element.get("tags") or {}
            if element.get("type") != "way" or not tags.get("highway"):
                continue
            street_stats["raw_ways"] += 1
            coordinates = [
                (float(p["lat"]), float(p["lon"]))
                for p in (element.get("geometry") or [])
                if p.get("lat") is not None and p.get("lon") is not None
            ]
            if len(coordinates) < 2:
                street_stats["invalid_ways"] += 1
                continue

            osm_id = element.get("id")
            name = _localized_name(tags)
            is_unnamed = not bool(name)
            if is_unnamed:
                street_stats["unnamed_ways"] += 1
                name = f"معبر بدون نام (OSM {osm_id})" if osm_id is not None else "معبر بدون نام"

            fragments = clip_polyline_to_polygon(coordinates, polygon)
            if not fragments:
                street_stats["outside_ways"] += 1
                continue
            for segment_index, fragment in enumerate(fragments):
                key = (osm_id, segment_index, tuple((round(a, 7), round(b, 7)) for a, b in fragment))
                if key in seen_fragments:
                    continue
                seen_fragments.add(key)
                streets.append({
                    "osm_id": osm_id,
                    "segment_index": segment_index,
                    "name": name,
                    "is_unnamed": int(is_unnamed),
                    "highway_type": tags.get("highway"),
                    "geometry": fragment,
                })
        street_stats["saved_fragments"] = len(streets)
        streets_ok = True
        if progress_callback:
            progress_callback(
                f"[خیابان‌ها] {street_stats['raw_ways']} مسیر خام بررسی و "
                f"{len(streets)} قطعه داخل محدوده آماده ذخیره شد؛ "
                f"{street_stats['unnamed_ways']} مسیر بدون نام بود."
            )
    except Exception as exc:
        errors["streets"] = str(exc)
        if progress_callback:
            progress_callback("⚠ دریافت خیابان‌ها ناموفق بود؛ داده قبلی حفظ می‌شود.")

    try:
        raw = _run_overpass_query(build_places_query(polygon), progress_callback, "[اماکن]")
        _save_debug_json("last_places_raw.json", raw)
        seen_places = set()
        place_stats["raw_elements"] = len(raw.get("elements", []))
        for element in raw.get("elements", []):
            tags = element.get("tags") or {}
            matched = next(((key, value, label) for key, value, label in PLACE_QUERY_TAGS if tags.get(key) == value), None)
            if not matched:
                for key in ("amenity", "building", "healthcare", "office", "shop"):
                    if tags.get(key):
                        unmatched_tags.add(f"{key}={tags[key]}")
                continue
            category, _value, label = matched
            if category == "office" and len(government_tag_samples) < 5:
                government_tag_samples.append(dict(tags))

            lat, lon = _element_center(element)
            if lat is None or lon is None:
                place_stats["no_coords"] += 1
                dropped_no_coords.append(f"{label} (id={element.get('id')}, name={tags.get('name', '?')})")
                continue
            lat, lon = float(lat), float(lon)
            if not point_in_polygon(lat, lon, polygon, include_boundary=True):
                place_stats["outside"] += 1
                continue

            key = (element.get("type"), element.get("id"), category, label)
            if key in seen_places:
                place_stats["duplicates"] += 1
                continue
            seen_places.add(key)
            address = " ".join(
                str(value).strip()
                for value in (tags.get("addr:street"), tags.get("addr:housenumber"))
                if value
            )
            places.append({
                "osm_id": element.get("id"),
                "name": _localized_name(tags, f"({label} بدون نام)"),
                "category": category,
                "subtype": label,
                "lat": lat,
                "lon": lon,
                "address": address,
            })
        place_stats["saved"] = len(places)
        places_ok = True
        if progress_callback:
            progress_callback(f"[اماکن] {len(places)} مکان داخل محدوده آماده ذخیره شد.")
    except Exception as exc:
        errors["places"] = str(exc)
        if progress_callback:
            progress_callback("⚠ دریافت اماکن ناموفق بود؛ داده قبلی حفظ می‌شود.")

    if not streets_ok and not places_ok:
        raise RuntimeError("دریافت خیابان‌ها و اماکن هر دو ناموفق بود.\n" + "\n".join(f"{k}: {v}" for k, v in errors.items()))

    return {
        "streets": streets,
        "places": places,
        "streets_ok": streets_ok,
        "places_ok": places_ok,
        "errors": errors,
        "unmatched_tags": sorted(unmatched_tags),
        "government_tag_samples": government_tag_samples,
        "dropped_no_coords": dropped_no_coords,
        "street_stats": street_stats,
        "place_stats": place_stats,
    }
