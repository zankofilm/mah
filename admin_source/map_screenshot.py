# -*- coding: utf-8 -*-
"""
ابزار کمکی برای گرفتن اسکرین‌شات (تصویر PNG) از نقشه آفلاین یک بلوک،
جهت استفاده در گزارش‌های PDF.

از یک QWebEngineView مخفی استفاده می‌شود: نقشه در آن لود می‌شود، صبر می‌کنیم
تا رندر کامل شود (شامل بارگذاری تایل‌ها)، سپس با grab() از آن عکس گرفته می‌شود.
"""

import os
from runtime_paths import get_temp_dir
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QUrl, QTimer, QEventLoop
from PyQt5.QtWebEngineWidgets import QWebEngineView

from map_html import build_view_mode_html


def _write_temp_html(html_content, filename):
    temp_dir = get_temp_dir()
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return path


def capture_zone_map_screenshot(db, zone_id, output_png_path, width=900, height=600, tile_wait_ms=2500):
    """
    یک اسکرین‌شات PNG از نقشه آفلاین یک بلوک/منطقه می‌گیرد و در output_png_path ذخیره می‌کند.
    این تابع باید از UI thread اصلی (نه از QThread جدا) فراخوانی شود، چون رندر
    واقعی QWebEngineView نیاز به event loop دارد.

    خروجی: True در صورت موفقیت، False در صورت شکست (مثلاً نبود محدوده یا تایل).
    """
    zone = db.get_zone(zone_id)
    if not zone or len(zone.get("boundary_points", [])) < 3:
        return False

    streets = db.get_streets(zone_id=zone_id)
    places = db.get_places(zone_id=zone_id)
    mosques = db.get_mosques(zone_id=zone_id)

    html = build_view_mode_html(
        zone["boundary_points"], streets, places, mosques=mosques, offline=True
    )
    html_path = _write_temp_html(html, f"report_map_zone_{zone_id}.html")

    # ویجت مخفی برای رندر نقشه (باید اندازه واقعی داشته باشد تا grab() تصویر خالی ندهد)
    view = QWebEngineView()
    view.resize(width, height)
    view.setAttribute(0x00000080)  # Qt.WA_DontShowOnScreen -- رندر بدون نمایش واقعی روی صفحه
    view.show()  # لازم است show شود تا رندر داخلی انجام گیرد، حتی اگر روی صفحه دیده نشود

    loop = QEventLoop()
    success_holder = {"loaded": False}

    def _on_load_finished(ok):
        success_holder["loaded"] = ok
        # کمی صبر اضافه برای اطمینان از بارگذاری کامل تایل‌های تصویری قبل از خروج از event loop
        QTimer.singleShot(tile_wait_ms, loop.quit)

    view.loadFinished.connect(_on_load_finished)
    view.setUrl(QUrl.fromLocalFile(html_path))

    # اجرای event loop محلی تا لود کامل شود (حداکثر با یک تایم‌اوت ایمنی)
    QTimer.singleShot(15000, loop.quit)  # ایمنی: حداکثر ۱۵ ثانیه صبر شود
    loop.exec_()

    if not success_holder["loaded"]:
        view.close()
        view.deleteLater()
        return False

    try:
        pixmap = view.grab()
        pixmap.save(output_png_path, "PNG")
        result = os.path.exists(output_png_path) and os.path.getsize(output_png_path) > 0
    except Exception:
        result = False
    finally:
        view.close()
        view.deleteLater()

    return result
