# -*- coding: utf-8 -*-
"""
ماژول «نقشه کامل شهر»:
- رسم محدوده کل شهر جوانرود (مستقل و بدون ارتباط با بلوک‌بندی)
- دانلود و ذخیره تمام خیابان‌ها و اماکن (مذهبی، مدارس، ادارات و...) آن محدوده از OSM
- نمایش نقشه کامل شهر با تمام جزئیات
- جدول‌های خیابان‌ها و اماکن با قابلیت ویرایش/حذف
- افزودن دستی مکان (برای مواردی که در OSM ثبت نشده‌اند)

این داده کاملاً مستقل از فرآیند بلوک‌بندی است و صرفاً به‌عنوان یک نقشه مرجع/کلی
برای مرور کاربر عمل می‌کند؛ بعداً هنگام تعریف هر بلوک/منطقه، همچنان داده آن
بلوک به‌طور مستقل از OSM دریافت می‌شود.
"""

import os
from runtime_paths import get_temp_dir
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit,
    QGroupBox, QFormLayout, QComboBox, QInputDialog, QScrollArea, QDialog,
    QDialogButtonBox, QToolButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from header_widget import build_official_header
from map_html import build_draw_mode_html, build_view_mode_html, build_place_editor_html
from osm_fetcher import fetch_osm_data
from place_types import supported_place_labels
from place_type_widgets import PlaceTypeComboBox


class DebugWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS Console - City-Wide Map] {message} (line {lineNumber})")


class FetchCityWideOSMThread(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, boundary_points):
        super().__init__()
        self.boundary_points = boundary_points

    def run(self):
        try:
            result = fetch_osm_data(self.boundary_points, progress_callback=self.progress.emit)
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class ManualPlaceDialog(QDialog):
    """دیالوگ افزودن دستی یک مکان (برای مواردی که در OSM ثبت نشده‌اند)."""
    TYPE_OPTIONS = supported_place_labels()

    def __init__(self, lat, lon, parent=None):
        super().__init__(parent)
        self.lat = lat
        self.lon = lon
        self.setWindowTitle("افزودن مکان دستی")
        self.resize(420, 260)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        coords_label = QLabel(f"مختصات انتخاب‌شده: {self.lat:.6f}, {self.lon:.6f}")
        form.addRow(coords_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("مثلاً: مسجد خلفای راشدین")
        form.addRow("نام مکان:", self.name_input)

        type_container = QWidget()
        type_layout = QHBoxLayout(type_container)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.setSpacing(6)

        self.type_combo = PlaceTypeComboBox()
        type_layout.addWidget(self.type_combo, 1)

        self.type_open_button = QToolButton()
        self.type_open_button.setText("▼")
        self.type_open_button.setToolTip("بازکردن فهرست انواع مکان")
        self.type_open_button.setFixedWidth(34)
        self.type_open_button.clicked.connect(self.type_combo.showPopup)
        type_layout.addWidget(self.type_open_button)

        self.type_add_button = QToolButton()
        self.type_add_button.setText("+")
        self.type_add_button.setToolTip("افزودن نوع مکان جدید")
        self.type_add_button.setFixedWidth(34)
        self.type_add_button.clicked.connect(lambda: self.type_combo.add_custom_type(self))
        type_layout.addWidget(self.type_add_button)

        form.addRow("نوع مکان:", type_container)

        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("آدرس (اختیاری)")
        form.addRow("آدرس:", self.address_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره مکان")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "خطا", "لطفاً نام مکان را وارد کنید.")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "subtype": self.type_combo.currentText(),
            "address": self.address_input.text().strip(),
        }


class CityWideMapWindow(QWidget):
    """پنجره اصلی ماژول «نقشه کامل شهر»."""
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.boundary_points = self.db.get_city_wide_boundary()
        self.setWindowTitle("نقشه کامل شهر جوانرود")
        self.resize(1300, 900)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = build_official_header(app_subtitle="نقشه کامل شهر", db=self.db)
        outer.addWidget(header)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(16, 10, 16, 0)
        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(back_btn)
        top_bar.addStretch()
        outer.addLayout(top_bar)

        info = QLabel(
            "این بخش برای رسم محدوده کامل شهر و دانلود یک‌جای تمام خیابان‌ها، مساجد، مدارس، ادارات "
            "و سایر اماکن است تا به‌عنوان یک نقشه مرجع/کلی برای مرور در دسترس باشد. این داده کاملاً "
            "مستقل از بلوک‌بندی است؛ برای هر بلوک همچنان داده به‌طور جدا از OSM دریافت می‌شود."
        )
        info.setWordWrap(True)
        info.setContentsMargins(16, 6, 16, 6)
        outer.addWidget(info)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        self._build_draw_tab()
        self._build_view_tab()
        self._build_streets_tab()
        self._build_places_tab()

    # ==================== تب ۱: رسم محدوده کل شهر ====================
    def _build_draw_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("روی نقشه کلیک کنید تا نقاط مرزی محدوده کامل شهر جوانرود را مشخص کنید (حداقل ۳ نقطه).")
        layout.addWidget(info)

        self.draw_webview = QWebEngineView()
        self.draw_page = DebugWebPage(self.draw_webview)
        self.draw_webview.setPage(self.draw_page)
        self._draw_html_path = self._write_temp_html(build_draw_mode_html(), "citywide_draw.html")
        self.draw_webview.setUrl(QUrl.fromLocalFile(self._draw_html_path))
        layout.addWidget(self.draw_webview)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("ذخیره محدوده کل شهر")
        save_btn.clicked.connect(self.on_save_boundary)
        btn_row.addWidget(save_btn)

        fetch_btn = QPushButton("📥 دانلود کامل خیابان‌ها و اماکن این محدوده از OpenStreetMap")
        fetch_btn.setProperty("success", True)
        fetch_btn.clicked.connect(self.on_fetch_city_wide_data)
        btn_row.addWidget(fetch_btn)
        layout.addLayout(btn_row)

        self.draw_status = QLabel("")
        self.draw_status.setWordWrap(True)
        layout.addWidget(self.draw_status)

        self.tabs.addTab(tab, "۱. رسم محدوده کل شهر")

    def _write_temp_html(self, html_content, filename):
        temp_dir = get_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return path

    def on_save_boundary(self):
        self.draw_webview.page().runJavaScript("getPoints();", self._handle_boundary_points)

    def _handle_boundary_points(self, points_json_str):
        import json
        try:
            points = json.loads(points_json_str)
        except Exception:
            points = []

        if len(points) < 3:
            QMessageBox.warning(self, "خطا", "حداقل ۳ نقطه برای تشکیل محدوده لازم است.")
            return

        self.boundary_points = [(p[0], p[1]) for p in points]
        self.db.save_city_wide_boundary(self.boundary_points)
        self.draw_status.setText(f"محدوده کل شهر با {len(points)} نقطه ذخیره شد.")
        QMessageBox.information(self, "موفق", f"محدوده کامل شهر با {len(points)} نقطه ذخیره شد.")

    def on_fetch_city_wide_data(self):
        if not self.boundary_points or len(self.boundary_points) < 3:
            QMessageBox.warning(self, "خطا", "ابتدا محدوده کل شهر را رسم و ذخیره کنید.")
            return

        self.draw_status.setText("در حال دانلود اطلاعات کامل شهر از OpenStreetMap ... (ممکن است چند دقیقه طول بکشد)")
        self.fetch_thread = FetchCityWideOSMThread(self.boundary_points)
        self.fetch_thread.progress.connect(lambda msg: self.draw_status.setText(msg))
        self.fetch_thread.finished_ok.connect(self.on_city_wide_data_ready)
        self.fetch_thread.failed.connect(self.on_fetch_failed)
        self.fetch_thread.start()

    def on_city_wide_data_ready(self, result):
        streets = result["streets"]
        places = result["places"]
        unmatched_tags = result.get("unmatched_tags", [])
        dropped_no_coords = result.get("dropped_no_coords", [])

        self.db.replace_city_wide_osm_data(
            streets=streets,
            places=places,
            replace_streets=result.get("streets_ok", True),
            replace_places=result.get("places_ok", True),
        )

        message = f"دانلود کامل شد: {len(streets)} خیابان/کوچه و {len(places)} مکان برای کل شهر ذخیره شد."
        if unmatched_tags:
            sample = "، ".join(unmatched_tags[:10])
            message += f"\n\nبرچسب‌های دیگری که در دسته‌بندی ما نبودند: {sample}"
        if dropped_no_coords:
            message += f"\n\n⚠ {len(dropped_no_coords)} مکان به‌دلیل نبود مختصات قابل‌استفاده نادیده گرفته شد."

        self.draw_status.setText(message)
        QMessageBox.information(self, "موفق", message)

        self.refresh_streets_table()
        self.refresh_places_table()
        self.refresh_view_map()

    def on_fetch_failed(self, error_msg):
        self.draw_status.setText("خطا در دانلود اطلاعات.")
        QMessageBox.critical(self, "خطا", f"دانلود اطلاعات از OpenStreetMap ناموفق بود:\n{error_msg}")

    # ==================== تب ۲: نمایش نقشه کامل ====================
    def _build_view_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        btn_row = QHBoxLayout()
        refresh_online_btn = QPushButton("بروزرسانی نقشه (آنلاین)")
        refresh_online_btn.clicked.connect(lambda: self.refresh_view_map(offline=False))
        btn_row.addWidget(refresh_online_btn)

        refresh_offline_btn = QPushButton("نمایش نقشه آفلاین (از دیتابیس)")
        refresh_offline_btn.clicked.connect(lambda: self.refresh_view_map(offline=True))
        btn_row.addWidget(refresh_offline_btn)

        add_manual_btn = QPushButton("➕ افزودن مکان دستی (مسجد/مدرسه/... که در OSM نیست)")
        add_manual_btn.setProperty("success", True)
        add_manual_btn.clicked.connect(self.on_add_manual_place)
        btn_row.addWidget(add_manual_btn)
        layout.addLayout(btn_row)

        self.view_webview = QWebEngineView()
        self.view_page = DebugWebPage(self.view_webview)
        self.view_webview.setPage(self.view_page)
        self.view_webview.titleChanged.connect(self._on_view_map_title_changed)
        layout.addWidget(self.view_webview)

        self.tabs.addTab(tab, "۲. نمایش نقشه کامل")
        self.refresh_view_map()

    def refresh_view_map(self, offline=False):
        streets = self.db.get_city_wide_streets()
        places = self.db.get_city_wide_places()
        mosques = self.db.get_mosques()
        html = build_view_mode_html(
            self.boundary_points, streets, places, mosques=mosques, offline=offline,
            schools=self.db.get_schools(), health_centers=self.db.get_health_centers(),
        )
        path = self._write_temp_html(html, "citywide_view.html")
        self.view_webview.setUrl(QUrl.fromLocalFile(path))

    def on_add_manual_place(self):
        # از کاربر می‌خواهیم روی نقشه کلیک کند؛ برای این منظور نقشه ادیتور مکان را نشان می‌دهیم
        places = self.db.get_city_wide_places()
        zone_like = {"name": "کل شهر", "color": "#13294b", "boundary_points": self.boundary_points}
        html = build_place_editor_html(zone_like, places, offline=False)
        path = self._write_temp_html(html, "citywide_place_editor.html")
        self.view_webview.setUrl(QUrl.fromLocalFile(path))
        QMessageBox.information(
            self, "افزودن مکان",
            "روی نقشه، دقیقاً روی محل مورد نظر کلیک کنید تا فرم افزودن مکان باز شود."
        )

    def _on_view_map_title_changed(self, title):
        if title.startswith("NEW_PLACE_COORDS:"):
            try:
                _, coords = title.split(":", 1)
                lat_str, lon_str = coords.split(",")
                lat, lon = float(lat_str), float(lon_str)
            except Exception:
                return
            dialog = ManualPlaceDialog(lat, lon, parent=self)
            if dialog.exec_() == QDialog.Accepted:
                data = dialog.get_data()
                self.db.add_manual_city_wide_place(data["name"], data["subtype"], lat, lon, data["address"])
                QMessageBox.information(self, "ذخیره شد", f"مکان «{data['name']}» با موفقیت اضافه شد.")
                self.refresh_places_table()
                self.refresh_view_map()

    # ==================== تب ۳: جدول خیابان‌ها ====================
    def _build_streets_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_row = QHBoxLayout()
        self.street_search = QLineEdit()
        self.street_search.setPlaceholderText("جستجو در نام خیابان/کوچه ...")
        self.street_search.textChanged.connect(self.filter_streets_table)
        top_row.addWidget(QLabel("جستجو:"))
        top_row.addWidget(self.street_search)

        refresh_btn = QPushButton("بروزرسانی جدول")
        refresh_btn.clicked.connect(self.refresh_streets_table)
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        action_row = QHBoxLayout()
        edit_btn = QPushButton("ویرایش ردیف انتخاب‌شده")
        edit_btn.clicked.connect(self.on_edit_street)
        action_row.addWidget(edit_btn)

        delete_btn = QPushButton("حذف ردیف انتخاب‌شده")
        delete_btn.setProperty("danger", True)
        delete_btn.clicked.connect(self.on_delete_street)
        action_row.addWidget(delete_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.streets_table = QTableWidget()
        self.streets_table.setColumnCount(2)
        self.streets_table.setHorizontalHeaderLabels(["نام", "نوع معبر"])
        self.streets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.streets_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.streets_table)

        self.streets_count_label = QLabel("تعداد: 0")
        layout.addWidget(self.streets_count_label)

        self.tabs.addTab(tab, "۳. خیابان‌های کل شهر")
        self.refresh_streets_table()

    def refresh_streets_table(self):
        self._all_streets = self.db.get_city_wide_streets()
        self._populate_streets_table(self._all_streets)

    def _populate_streets_table(self, streets):
        self.streets_table.setRowCount(len(streets))
        for row, s in enumerate(streets):
            name_item = QTableWidgetItem(s["name"])
            name_item.setData(Qt.UserRole, s["id"])
            self.streets_table.setItem(row, 0, name_item)
            self.streets_table.setItem(row, 1, QTableWidgetItem(s["highway_type"] or ""))
        self.streets_count_label.setText(f"تعداد: {len(streets)}")

    def filter_streets_table(self, text):
        if not hasattr(self, "_all_streets"):
            return
        text = text.strip()
        if not text:
            self._populate_streets_table(self._all_streets)
            return
        filtered = [s for s in self._all_streets if text in s["name"]]
        self._populate_streets_table(filtered)

    def on_edit_street(self):
        row = self.streets_table.currentRow()
        item = self.streets_table.item(row, 0) if row >= 0 else None
        street_id = item.data(Qt.UserRole) if item else None
        street = next((st for st in self._all_streets if st["id"] == street_id), None)
        if street is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        new_name, ok = QInputDialog.getText(self, "ویرایش نام خیابان/کوچه", "نام جدید:", text=street["name"])
        if ok and new_name.strip():
            self.db.update_city_wide_street(street["id"], name=new_name.strip())
            self.refresh_streets_table()

    def on_delete_street(self):
        row = self.streets_table.currentRow()
        item = self.streets_table.item(row, 0) if row >= 0 else None
        street_id = item.data(Qt.UserRole) if item else None
        street = next((st for st in self._all_streets if st["id"] == street_id), None)
        if street is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        reply = QMessageBox.question(
            self, "تأیید حذف", f"آیا از حذف «{street['name']}» مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_city_wide_street(street["id"])
            self.refresh_streets_table()

    # ==================== تب ۴: جدول اماکن ====================
    def _build_places_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_row = QHBoxLayout()
        self.place_search = QLineEdit()
        self.place_search.setPlaceholderText("جستجو در نام مکان ...")
        self.place_search.textChanged.connect(self.filter_places_table)
        top_row.addWidget(QLabel("جستجو:"))
        top_row.addWidget(self.place_search)

        refresh_btn = QPushButton("بروزرسانی جدول")
        refresh_btn.clicked.connect(self.refresh_places_table)
        top_row.addWidget(refresh_btn)
        layout.addLayout(top_row)

        action_row = QHBoxLayout()
        edit_btn = QPushButton("ویرایش ردیف انتخاب‌شده")
        edit_btn.clicked.connect(self.on_edit_place)
        action_row.addWidget(edit_btn)

        delete_btn = QPushButton("حذف ردیف انتخاب‌شده")
        delete_btn.setProperty("danger", True)
        delete_btn.clicked.connect(self.on_delete_place)
        action_row.addWidget(delete_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.places_table = QTableWidget()
        self.places_table.setColumnCount(4)
        self.places_table.setHorizontalHeaderLabels(["نام", "دسته", "زیر‌دسته", "منبع"])
        self.places_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.places_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.places_table)

        self.places_count_label = QLabel("تعداد: 0")
        layout.addWidget(self.places_count_label)

        self.tabs.addTab(tab, "۴. اماکن کل شهر")
        self.refresh_places_table()

    def refresh_places_table(self):
        self._all_places = self.db.get_city_wide_places()
        self._populate_places_table(self._all_places)

    def _populate_places_table(self, places):
        self.places_table.setRowCount(len(places))
        for row, p in enumerate(places):
            source = "دستی" if p["osm_id"] is None else "OpenStreetMap"
            name_item = QTableWidgetItem(p["name"])
            name_item.setData(Qt.UserRole, p["id"])
            self.places_table.setItem(row, 0, name_item)
            self.places_table.setItem(row, 1, QTableWidgetItem(p["category"] or ""))
            self.places_table.setItem(row, 2, QTableWidgetItem(p["subtype"] or ""))
            self.places_table.setItem(row, 3, QTableWidgetItem(source))
        self.places_count_label.setText(f"تعداد: {len(places)}")

    def filter_places_table(self, text):
        if not hasattr(self, "_all_places"):
            return
        text = text.strip()
        if not text:
            self._populate_places_table(self._all_places)
            return
        filtered = [p for p in self._all_places if text in p["name"]]
        self._populate_places_table(filtered)

    def on_edit_place(self):
        row = self.places_table.currentRow()
        item = self.places_table.item(row, 0) if row >= 0 else None
        place_id = item.data(Qt.UserRole) if item else None
        place = next((pl for pl in self._all_places if pl["id"] == place_id), None)
        if place is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        new_name, ok = QInputDialog.getText(self, "ویرایش نام مکان", "نام جدید:", text=place["name"])
        if ok and new_name.strip():
            self.db.update_city_wide_place(place["id"], name=new_name.strip())
            self.refresh_places_table()

    def on_delete_place(self):
        row = self.places_table.currentRow()
        item = self.places_table.item(row, 0) if row >= 0 else None
        place_id = item.data(Qt.UserRole) if item else None
        place = next((pl for pl in self._all_places if pl["id"] == place_id), None)
        if place is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        reply = QMessageBox.question(
            self, "تأیید حذف", f"آیا از حذف «{place['name']}» مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_city_wide_place(place["id"])
            self.refresh_places_table()
