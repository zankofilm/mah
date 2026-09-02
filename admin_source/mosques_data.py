# -*- coding: utf-8 -*-
"""فهرست مرجع مساجد جوانرود و ابزارهای هندسی مرتبط با بلوک‌بندی."""

import math

# دو جفت رکورد بسیار نزدیک ادغام شده‌اند:
# 1) مسجد حضرت رسول(ص) + مسجد محمد رسول‌الله
# 2) مسجد جامع + مسجد جامع جدید
MOSQUES = [
    {"id": "mosque-001", "name": "مسجد حضرت رسول(ص)", "lat": 34.8018430, "lon": 46.5042190,
     "aliases": ["مسجد محمد رسول الله", "مسجد محمد رسول‌الله"]},
    {"id": "mosque-002", "name": "مسجد جامع", "lat": 34.8023070, "lon": 46.4897476,
     "aliases": ["مسجد جامع جدید"]},
    {"id": "mosque-003", "name": "مسجد قبا", "lat": 34.8094813, "lon": 46.4983859, "aliases": []},
    {"id": "mosque-004", "name": "مسجد سیدالشهدا حمزه", "lat": 34.8075119, "lon": 46.5006376, "aliases": []},
    {"id": "mosque-005", "name": "مسجد یکتا", "lat": 34.8056047, "lon": 46.4964591, "aliases": []},
    {"id": "mosque-006", "name": "مسجد حضرت ابراهیم", "lat": 34.8121261, "lon": 46.5025554, "aliases": []},
    {"id": "mosque-007", "name": "مسجد صلاح الدین ایوبی کوردی", "lat": 34.8063009, "lon": 46.5019562, "aliases": []},
    {"id": "mosque-008", "name": "مسجد شهدای احد", "lat": 34.8135000, "lon": 46.4945000, "aliases": []},
    {"id": "mosque-009", "name": "مسجد خاتم الانبیا", "lat": 34.8086282, "lon": 46.4906336, "aliases": []},
    {"id": "mosque-010", "name": "مسجد امام محمد شافعی", "lat": 34.8071870, "lon": 46.4907443, "aliases": []},
    {"id": "mosque-011", "name": "مسجد نور", "lat": 34.8026213, "lon": 46.4938445, "aliases": []},
    {"id": "mosque-012", "name": "مسجد دارالاحسان", "lat": 34.8047447, "lon": 46.4908054, "aliases": []},
    {"id": "mosque-013", "name": "مسجد پیر خدری", "lat": 34.8079009, "lon": 46.4886532, "aliases": []},
    {"id": "mosque-014", "name": "مسجد جامع قدیم", "lat": 34.8035585, "lon": 46.4910932, "aliases": []},
    {"id": "mosque-015", "name": "مسجد آل محمد", "lat": 34.8046824, "lon": 46.4884080, "aliases": []},
    {"id": "mosque-016", "name": "مسجد دارالصفا", "lat": 34.8006258, "lon": 46.4932351, "aliases": []},
    {"id": "mosque-017", "name": "مسجد حاج حسن قبادی", "lat": 34.7995000, "lon": 46.4963000, "aliases": []},
    {"id": "mosque-018", "name": "نمازخانه مسکن مهر مولوی", "lat": 34.8081937, "lon": 46.4858138, "aliases": []},
    {"id": "mosque-019", "name": "مسجد قادری", "lat": 34.8036529, "lon": 46.4870586, "aliases": []},
    {"id": "mosque-020", "name": "مسجد نبی اکرم", "lat": 34.8015710, "lon": 46.4881057, "aliases": []},
    {"id": "mosque-021", "name": "مسجد حاج سید صفاالدین هاشمی", "lat": 34.8050354, "lon": 46.4837500, "aliases": []},
    {"id": "mosque-022", "name": "مسجد حضرت محمد", "lat": 34.8004371, "lon": 46.4872163, "aliases": []},
    {"id": "mosque-023", "name": "مسجد نبی الله", "lat": 34.7979456, "lon": 46.4858680, "aliases": []},
    {"id": "mosque-024", "name": "مسجد خلفای راشدین", "lat": 34.8057936, "lon": 46.4940866, "aliases": []},
]


def _point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon, tolerance=1e-10):
    """بررسی قرار داشتن نقطه روی ضلع چندضلعی؛ نقاط مرزی داخل محسوب می‌شوند."""
    cross = (lon - a_lon) * (b_lat - a_lat) - (lat - a_lat) * (b_lon - a_lon)
    if abs(cross) > tolerance:
        return False
    return (
        min(a_lat, b_lat) - tolerance <= lat <= max(a_lat, b_lat) + tolerance
        and min(a_lon, b_lon) - tolerance <= lon <= max(a_lon, b_lon) + tolerance
    )


def point_in_polygon(lat, lon, polygon):
    """Ray-casting دقیق برای تشخیص قرارگیری نقطه داخل چندضلعی [(lat, lon), ...]."""
    if not polygon or len(polygon) < 3:
        return False

    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        a_lat, a_lon = polygon[j]
        b_lat, b_lon = polygon[i]

        if _point_on_segment(lat, lon, a_lat, a_lon, b_lat, b_lon):
            return True

        intersects = ((b_lat > lat) != (a_lat > lat))
        if intersects:
            denom = (a_lat - b_lat)
            if abs(denom) > 1e-15:
                intersect_lon = (a_lon - b_lon) * (lat - b_lat) / denom + b_lon
                if lon < intersect_lon:
                    inside = not inside
        j = i
    return inside


def distance_meters(lat1, lon1, lat2, lon2):
    """فاصله تقریبی دو نقطه بر حسب متر (Haversine)، برای تست و کنترل داده."""
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
