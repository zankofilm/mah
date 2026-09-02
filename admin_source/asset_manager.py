# -*- coding: utf-8 -*-
"""مدیریت دارایی‌های محلی Leaflet برای نمایش واقعی نقشه در حالت آفلاین."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

import requests

from runtime_paths import get_runtime_vendor_dir, resource_dir

BASE_DIR = resource_dir()
VENDOR_DIR = Path(get_runtime_vendor_dir())
BUNDLED_VENDOR_DIR = BASE_DIR / "vendor" / "leaflet"

ASSETS = {
    "leaflet.js": [
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js",
    ],
    "leaflet.css": [
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css",
    ],
    "images/layers.png": [
        "https://unpkg.com/leaflet@1.9.4/dist/images/layers.png",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/layers.png",
    ],
    "images/layers-2x.png": [
        "https://unpkg.com/leaflet@1.9.4/dist/images/layers-2x.png",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/layers-2x.png",
    ],
    "images/marker-icon.png": [
        "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon.png",
    ],
    "images/marker-icon-2x.png": [
        "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon-2x.png",
    ],
    "images/marker-shadow.png": [
        "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
        "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-shadow.png",
    ],
}

MIN_SIZES = {
    "leaflet.js": 100_000,
    "leaflet.css": 10_000,
}


def _seed_bundled_assets():
    """منابع بسته‌شده را در مسیر نوشتنی کاربر کپی می‌کند."""
    if not BUNDLED_VENDOR_DIR.exists() or BUNDLED_VENDOR_DIR.resolve() == VENDOR_DIR.resolve():
        return
    for relative_path in ASSETS:
        src = BUNDLED_VENDOR_DIR / relative_path
        dst = VENDOR_DIR / relative_path
        if src.exists() and (not dst.exists() or dst.stat().st_size <= 0):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def leaflet_assets_available() -> bool:
    _seed_bundled_assets()
    for relative_path in ASSETS:
        path = VENDOR_DIR / relative_path
        if not path.exists() or path.stat().st_size <= 0:
            return False
        if relative_path in MIN_SIZES and path.stat().st_size < MIN_SIZES[relative_path]:
            return False
    return True


def ensure_leaflet_assets(progress_callback=None, timeout=25) -> dict:
    """دارایی‌های گمشده را از دو CDN معتبر دریافت می‌کند؛ شکست دانلود برنامه را متوقف نمی‌کند."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    _seed_bundled_assets()
    downloaded, existing, failed = [], [], []
    session = requests.Session()
    session.headers.update({"User-Agent": "JavanroodMapApp/4.0 asset bootstrap"})

    for relative_path, urls in ASSETS.items():
        destination = VENDOR_DIR / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        minimum = MIN_SIZES.get(relative_path, 1)
        if destination.exists() and destination.stat().st_size >= minimum:
            existing.append(relative_path)
            continue

        success = False
        for url in urls:
            try:
                if progress_callback:
                    progress_callback(f"دریافت فایل آفلاین {relative_path} ...")
                response = session.get(url, timeout=(10, timeout))
                response.raise_for_status()
                content = response.content
                if len(content) < minimum:
                    raise RuntimeError("حجم فایل دریافت‌شده معتبر نیست")
                temp_path = destination.with_suffix(destination.suffix + ".tmp")
                temp_path.write_bytes(content)
                os.replace(temp_path, destination)
                downloaded.append(relative_path)
                success = True
                break
            except Exception:
                continue
        if not success:
            failed.append(relative_path)

    return {
        "ok": not failed,
        "downloaded": downloaded,
        "existing": existing,
        "failed": failed,
    }
