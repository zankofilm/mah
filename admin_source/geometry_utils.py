# -*- coding: utf-8 -*-
"""توابع هندسی بدون وابستگی خارجی برای عملیات GIS سبک برنامه."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Iterable, List, Sequence, Tuple

Point = Tuple[float, float]  # (lat, lon)
EPS = 1e-10
EARTH_RADIUS_M = 6371008.8
WGS84_A_M = 6378137.0
WGS84_FLATTENING = 1.0 / 298.257223563
WGS84_E2 = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)


def normalize_polygon(points: Iterable[Sequence[float]]) -> List[Point]:
    """مختصات را به فهرست معتبر (lat, lon) تبدیل و نقاط تکراری متوالی را حذف می‌کند."""
    result: List[Point] = []
    for point in points or []:
        if point is None or len(point) < 2:
            continue
        lat, lon = float(point[0]), float(point[1])
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        current = (lat, lon)
        if not result or not points_equal(result[-1], current):
            result.append(current)
    if len(result) > 1 and points_equal(result[0], result[-1]):
        result.pop()
    return result


def points_equal(a: Point, b: Point, eps: float = EPS) -> bool:
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def point_on_segment(point: Point, a: Point, b: Point, eps: float = 1e-9) -> bool:
    """بررسی می‌کند نقطه روی پاره‌خط قرار دارد؛ مختصات کوچک شهری برای این دقت مناسب است."""
    py, px = point
    ay, ax = a
    by, bx = b
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    return (
        min(ax, bx) - eps <= px <= max(ax, bx) + eps
        and min(ay, by) - eps <= py <= max(ay, by) + eps
    )


def point_in_polygon(lat: float, lon: float, polygon: Iterable[Sequence[float]], include_boundary: bool = True) -> bool:
    """آزمون ray-casting برای قرارگیری نقطه داخل چندضلعی؛ نقاط مرزی نیز داخل محسوب می‌شوند."""
    poly = normalize_polygon(polygon)
    if len(poly) < 3:
        return False
    point = (float(lat), float(lon))
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        a = poly[j]
        b = poly[i]
        if include_boundary and point_on_segment(point, a, b):
            return True
        yi, xi = b
        yj, xj = a
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or EPS) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _segment_intersection_t(a: Point, b: Point, c: Point, d: Point) -> float | None:
    """پارامتر t محل تقاطع AB و CD را روی AB برمی‌گرداند؛ تقاطع هم‌خط نادیده گرفته می‌شود."""
    ay, ax = a
    by, bx = b
    cy, cx = c
    dy, dx = d
    r_x, r_y = bx - ax, by - ay
    s_x, s_y = dx - cx, dy - cy
    denom = r_x * s_y - r_y * s_x
    qmp_x, qmp_y = cx - ax, cy - ay
    if abs(denom) <= EPS:
        return None
    t = (qmp_x * s_y - qmp_y * s_x) / denom
    u = (qmp_x * r_y - qmp_y * r_x) / denom
    if -EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS:
        return max(0.0, min(1.0, t))
    return None


def _interpolate(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def clip_polyline_to_polygon(polyline: Iterable[Sequence[float]], polygon: Iterable[Sequence[float]]) -> List[List[Point]]:
    """
    یک خط چندبخشی را دقیقاً به داخل چندضلعی محدود می‌کند.

    خروجی ممکن است چند قطعه مستقل باشد؛ مثلاً وقتی خیابان چند بار از بلوک خارج و وارد می‌شود.
    """
    line = normalize_polygon(polyline)
    poly = normalize_polygon(polygon)
    if len(line) < 2 or len(poly) < 3:
        return []

    fragments: List[List[Point]] = []
    current: List[Point] = []
    edges = list(zip(poly, poly[1:] + poly[:1]))

    def append_point(target: List[Point], p: Point) -> None:
        if not target or not points_equal(target[-1], p, eps=1e-9):
            target.append(p)

    for idx in range(len(line) - 1):
        a, b = line[idx], line[idx + 1]
        if points_equal(a, b):
            continue
        ts = [0.0, 1.0]
        for c, d in edges:
            t = _segment_intersection_t(a, b, c, d)
            if t is not None:
                ts.append(t)
        ts = sorted(set(round(t, 12) for t in ts))

        segment_had_inside = False
        for start_t, end_t in zip(ts, ts[1:]):
            if end_t - start_t <= EPS:
                continue
            mid = _interpolate(a, b, (start_t + end_t) / 2.0)
            if point_in_polygon(mid[0], mid[1], poly, include_boundary=True):
                p1 = _interpolate(a, b, start_t)
                p2 = _interpolate(a, b, end_t)
                append_point(current, p1)
                append_point(current, p2)
                segment_had_inside = True
            elif current:
                if len(current) >= 2:
                    fragments.append(current)
                current = []

        if not segment_had_inside and current:
            if len(current) >= 2:
                fragments.append(current)
            current = []

    if current and len(current) >= 2:
        fragments.append(current)

    cleaned: List[List[Point]] = []
    for fragment in fragments:
        deduped: List[Point] = []
        for p in fragment:
            append_point(deduped, p)
        if len(deduped) >= 2 and polyline_length_m(deduped) > 0.2:
            cleaned.append(deduped)
    return cleaned


def haversine_distance_m(a: Point, b: Point) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def polyline_length_m(points: Iterable[Sequence[float]]) -> float:
    pts = normalize_polygon(points)
    return sum(haversine_distance_m(a, b) for a, b in zip(pts, pts[1:]))


def polygon_metrics(points: Iterable[Sequence[float]]) -> Tuple[float, float]:
    """
    مساحت مترمربع و محیط متر را برای چندضلعی‌های شهری محاسبه می‌کند.

    مختصات ابتدا نسبت به مرکز هندسه به صفحه محلی منتقل می‌شوند. این کار از
    تفریق اعداد بسیار بزرگ در فرمول shoelace جلوگیری می‌کند و دقت محاسبه
    مساحت بلوک‌ها و محدوده شهر را پایدار نگه می‌دارد.
    """
    poly = normalize_polygon(points)
    if len(poly) < 3:
        return 0.0, 0.0

    lat0 = math.radians(math.fsum(p[0] for p in poly) / len(poly))
    lon0 = math.radians(math.fsum(p[1] for p in poly) / len(poly))
    sin_lat0 = math.sin(lat0)
    cos_lat0 = math.cos(lat0)
    curvature = math.sqrt(1.0 - WGS84_E2 * sin_lat0 * sin_lat0)
    prime_vertical_radius = WGS84_A_M / curvature
    meridional_radius = WGS84_A_M * (1.0 - WGS84_E2) / (curvature ** 3)

    def wrapped_delta_lon(lon_rad: float) -> float:
        return (lon_rad - lon0 + math.pi) % (2.0 * math.pi) - math.pi

    xy = []
    for lat, lon in poly:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        xy.append((
            prime_vertical_radius * cos_lat0 * wrapped_delta_lon(lon_rad),
            meridional_radius * (lat_rad - lat0),
        ))

    cross_terms = [
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1])
    ]
    area_m2 = abs(math.fsum(cross_terms)) / 2.0
    def ellipsoid_segment_length_m(a: Point, b: Point) -> float:
        lat1, lon1 = map(math.radians, a)
        lat2, lon2 = map(math.radians, b)
        mean_lat = (lat1 + lat2) / 2.0
        sin_mean = math.sin(mean_lat)
        segment_curvature = math.sqrt(1.0 - WGS84_E2 * sin_mean * sin_mean)
        segment_prime_vertical = WGS84_A_M / segment_curvature
        segment_meridional = WGS84_A_M * (1.0 - WGS84_E2) / (segment_curvature ** 3)
        delta_lon = (lon2 - lon1 + math.pi) % (2.0 * math.pi) - math.pi
        dx = segment_prime_vertical * math.cos(mean_lat) * delta_lon
        dy = segment_meridional * (lat2 - lat1)
        return math.hypot(dx, dy)

    perimeter_m = math.fsum(
        ellipsoid_segment_length_m(a, b) for a, b in zip(poly, poly[1:] + poly[:1])
    )
    return area_m2, perimeter_m


def geometry_hash(points: Iterable[Sequence[float]]) -> str:
    normalized = [[round(float(p[0]), 7), round(float(p[1]), 7)] for p in points or []]
    payload = json.dumps(normalized, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _orientation(a: Point, b: Point, c: Point) -> float:
    """علامت ضرب برداری در صفحه lon/lat."""
    return (b[1] - a[1]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[1] - a[1])


def _proper_segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    """تقاطع واقعی دو پاره‌خط؛ تماس صرف در رأس مشترک را هم‌پوشانی محسوب نمی‌کند."""
    if points_equal(a, c) or points_equal(a, d) or points_equal(b, c) or points_equal(b, d):
        return False
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    return ((o1 > EPS and o2 < -EPS) or (o1 < -EPS and o2 > EPS)) and (
        (o3 > EPS and o4 < -EPS) or (o3 < -EPS and o4 > EPS)
    )


def polygon_self_intersects(points: Iterable[Sequence[float]]) -> bool:
    poly = normalize_polygon(points)
    if len(poly) < 4:
        return False
    edges = list(zip(poly, poly[1:] + poly[:1]))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i:
                continue
            # یال‌های مجاور و یال اول/آخر یک رأس مشترک دارند و بررسی نمی‌شوند.
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if _proper_segments_intersect(a, b, c, d):
                return True
    return False


def polygons_overlap(first: Iterable[Sequence[float]], second: Iterable[Sequence[float]]) -> bool:
    """هم‌پوشانی ناحیه‌ای دو چندضلعی؛ تماس مرزی به‌تنهایی هم‌پوشانی نیست."""
    a_poly = normalize_polygon(first)
    b_poly = normalize_polygon(second)
    if len(a_poly) < 3 or len(b_poly) < 3:
        return False
    a_edges = list(zip(a_poly, a_poly[1:] + a_poly[:1]))
    b_edges = list(zip(b_poly, b_poly[1:] + b_poly[:1]))
    if any(_proper_segments_intersect(a, b, c, d) for a, b in a_edges for c, d in b_edges):
        return True
    # رأس کاملاً داخلی (نه روی مرز) نشان‌دهنده هم‌پوشانی یا محاط‌شدن است.
    for p in a_poly:
        if point_in_polygon(p[0], p[1], b_poly, include_boundary=False):
            return True
    for p in b_poly:
        if point_in_polygon(p[0], p[1], a_poly, include_boundary=False):
            return True
    return False


def validate_polygon(points: Iterable[Sequence[float]], minimum_area_m2: float = 10.0) -> Tuple[bool, str]:
    poly = normalize_polygon(points)
    if len(poly) < 3:
        return False, "حداقل سه نقطه غیرتکراری لازم است."
    if polygon_self_intersects(poly):
        return False, "مرز رسم‌شده خودمتقاطع است؛ خطوط مرز نباید یکدیگر را قطع کنند."
    area, _ = polygon_metrics(poly)
    if area < minimum_area_m2:
        return False, "مساحت بلوک بسیار کوچک یا صفر است."
    return True, "ok"
