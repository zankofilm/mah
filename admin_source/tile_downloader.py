# -*- coding: utf-8 -*-
"""
دانلود تایل‌های نقشه (OpenStreetMap Standard Tiles) برای یک محدوده جغرافیایی
در چند سطح زوم، جهت استفاده آفلاین با کیفیت بالا.
"""

import math
import time
import requests

TILE_SERVERS = [
    "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
]

# محدوده زوم توصیه‌شده برای دانلود «کامل و حرفه‌ای» یک‌باره: از نمای کلی شهر (۱۰)
# تا جزئی‌ترین سطح خیابان/کوچه که OpenStreetMap raster tiles پشتیبانی می‌کند (۱۹).
RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE = range(10, 20)

HEADERS = {
    "User-Agent": "JavanroodMapApp/4.0 (municipal offline map tool)"
}


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def get_tile_range(min_lat, min_lon, max_lat, max_lon, zoom):
    x1, y1 = deg2num(max_lat, min_lon, zoom)
    x2, y2 = deg2num(min_lat, max_lon, zoom)
    x_min, x_max = min(x1, x2), max(x1, x2)
    y_min, y_max = min(y1, y2), max(y1, y2)
    return x_min, x_max, y_min, y_max


def download_tiles_for_bbox(db, min_lat, min_lon, max_lat, max_lon,
                             zoom_levels=range(12, 18),
                             progress_callback=None, delay=0.05,
                             should_cancel=None, batch_size=25):
    """دانلود و ذخیره تایل‌های OSM برای استفاده آفلاین."""
    return _legacy_download_tiles_for_bbox(
        db, min_lat, min_lon, max_lat, max_lon, zoom_levels,
        progress_callback, delay, should_cancel, batch_size
    )


def _legacy_download_tiles_for_bbox(db, min_lat, min_lon, max_lat, max_lon,
                                    zoom_levels=range(12, 18),
                                    progress_callback=None, delay=0.05,
                                    should_cancel=None, batch_size=25):
    """پیاده‌سازی قدیمی فقط برای مرجع؛ از رابط برنامه فراخوانی نمی‌شود."""
    all_tiles = []
    for z in zoom_levels:
        x_min, x_max, y_min, y_max = get_tile_range(min_lat, min_lon, max_lat, max_lon, z)
        for x in range(x_min, x_max + 1):
            for y in range(y_min, y_max + 1):
                all_tiles.append((z, x, y))

    total = len(all_tiles)
    existing = db.get_all_tile_keys() if hasattr(db, "get_all_tile_keys") else set()
    downloaded = skipped = failed = 0
    pending = []
    session = requests.Session()
    session.headers.update(HEADERS)

    def flush():
        nonlocal pending
        if pending:
            if hasattr(db, "save_tiles_bulk"):
                db.save_tiles_bulk(pending)
            else:
                for z, x, y, content in pending:
                    db.save_tile(z, x, y, content)
            pending = []

    for i, (z, x, y) in enumerate(all_tiles):
        if should_cancel and should_cancel():
            flush()
            return {
                "downloaded": downloaded, "skipped": skipped, "failed": failed,
                "total": total, "cancelled": True,
            }
        key = (z, x, y)
        if key in existing:
            skipped += 1
        else:
            success = False
            # چند زیردامنه OSM برای توزیع عادلانه درخواست‌ها؛ حداکثر دو تلاش
            for attempt in range(2):
                url = TILE_SERVERS[(i + attempt) % len(TILE_SERVERS)].format(z=z, x=x, y=y)
                try:
                    response = session.get(url, timeout=(8, 20))
                    if response.status_code == 200 and response.content:
                        pending.append((z, x, y, response.content))
                        existing.add(key)
                        downloaded += 1
                        success = True
                        if len(pending) >= batch_size:
                            flush()
                        break
                    if response.status_code == 429:
                        time.sleep(2 + attempt * 2)
                except Exception:
                    if attempt == 0:
                        time.sleep(0.5)
            if not success:
                failed += 1
            if delay:
                time.sleep(delay)

        if progress_callback and (i % 10 == 0 or i == total - 1):
            progress_callback(i + 1, total, downloaded, skipped, failed)

    flush()
    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "total": total,
        "cancelled": False,
    }


def estimate_tile_count(min_lat, min_lon, max_lat, max_lon, zoom_levels=range(12, 18)):
    count = 0
    for z in zoom_levels:
        x_min, x_max, y_min, y_max = get_tile_range(min_lat, min_lon, max_lat, max_lon, z)
        count += (x_max - x_min + 1) * (y_max - y_min + 1)
    return count
