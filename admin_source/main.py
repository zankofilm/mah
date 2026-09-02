# -*- coding: utf-8 -*-
"""
نرم‌افزار نقشه شهر جوانرود
- نمایش نقشه آنلاین و رسم محدوده شهر
- دریافت خیابان‌ها، کوچه‌ها و اماکن از OpenStreetMap
- ذخیره همه اطلاعات (نقشه، خیابان‌ها، اماکن) در دیتابیس محلی برای استفاده آفلاین
"""

import sys
import os
from runtime_paths import get_temp_dir

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QTableWidget, QTableWidgetItem,
    QMessageBox, QProgressBar, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout, QHeaderView,
    QLineEdit, QListWidget, QListWidgetItem, QInputDialog, QComboBox, QAbstractItemView,
    QDialog, QDialogButtonBox, QFileDialog, QToolButton, QScrollArea, QSizePolicy, QSplitter, QFrame, QLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QUrl
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from database import Database
from osm_fetcher import fetch_osm_data
from place_types import supported_place_labels
from place_type_widgets import PlaceTypeComboBox
from tile_downloader import download_tiles_for_bbox, estimate_tile_count, RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE
from tile_server import leaflet_vendor_files_available
from asset_manager import ensure_leaflet_assets
from map_html import (
    build_draw_mode_html, build_view_mode_html,
    build_zone_draw_html, build_all_zones_view_html,
    build_place_editor_html
)
from header_widget import build_official_header
from jalali_utils import format_jalali, convert_dates_in_text
from geometry_utils import polygon_metrics, polygons_overlap, validate_polygon
from zone_snapshot_service import (
    refresh_zone_snapshot, export_zone_snapshot_png, export_zone_snapshot_svg
)


# ------------------- صفحه وب سفارشی برای نمایش خطاهای جاوااسکریپت (دیباگ) -------------------

class DebugWebPage(QWebEnginePage):
    """این کلاس خطاها و پیام‌های console.log جاوااسکریپت را در ترمینال پایتون چاپ می‌کند
    تا در صورت سفید ماندن نقشه، بتوان علت را فهمید."""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS Console] {message} (line {lineNumber}, source: {sourceID})")




class CollapsibleSection(QWidget):
    """بخش تاشونده ساده برای کم‌کردن شلوغی رابط."""
    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.clicked.connect(self._on_toggled)
        self.toggle_button.setStyleSheet("QToolButton { font-weight: bold; padding: 6px 4px; text-align: right; }")

        self.content = QWidget()
        self.content.setVisible(expanded)
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(4)
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content)

    def setContentLayout(self, layout):
        self.content.setLayout(layout)

    def _on_toggled(self, checked):
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content.setVisible(checked)


class ManualPlaceDialog(QDialog):
    """
    دیالوگ افزودن دستی یک مکان (مسجد/مدرسه/...) که در OpenStreetMap ثبت نشده است.
    شامل نقشه‌ای که با کلیک روی آن، مختصات انتخاب می‌شود، و فرم نام + نوع مکان.
    """
    def __init__(self, db, zone, temp_html_writer, parent=None):
        super().__init__(parent)
        self.db = db
        self.zone = zone
        self._write_temp_html = temp_html_writer
        self.selected_lat = None
        self.selected_lon = None
        self.setWindowTitle(f"افزودن مکان دستی — منطقه: {zone['name']}")
        self.resize(900, 700)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "روی نقشه کلیک کنید تا مختصات مکان جدید انتخاب شود، یا مختصات دقیق را "
            "مستقیماً در فیلدهای زیر وارد کنید؛ سپس نام و نوع مکان را مشخص کنید."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.map_webview = QWebEngineView()
        self.map_page = DebugWebPage(self.map_webview)
        self.map_webview.setPage(self.map_page)
        self.map_webview.titleChanged.connect(self._on_map_title_changed)
        layout.addWidget(self.map_webview, stretch=1)

        places = self.db.get_places(zone_id=self.zone["id"])
        html = build_place_editor_html(self.zone, places, offline=False)
        temp_path = self._write_temp_html(html, "manual_place_editor.html")
        self.map_webview.setUrl(QUrl.fromLocalFile(temp_path))

        form = QFormLayout()

        coords_row = QHBoxLayout()
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setDecimals(6)
        self.lat_input.setRange(-90.0, 90.0)
        self.lat_input.setSingleStep(0.0001)
        self.lat_input.valueChanged.connect(self._on_manual_coords_changed)
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setDecimals(6)
        self.lon_input.setRange(-180.0, 180.0)
        self.lon_input.setSingleStep(0.0001)
        self.lon_input.valueChanged.connect(self._on_manual_coords_changed)
        coords_row.addWidget(QLabel("عرض جغرافیایی:"))
        coords_row.addWidget(self.lat_input)
        coords_row.addWidget(QLabel("طول جغرافیایی:"))
        coords_row.addWidget(self.lon_input)
        form.addRow("مختصات دقیق (اختیاری):", coords_row)

        self.coords_label = QLabel("هنوز مختصاتی انتخاب نشده است.")
        form.addRow("مختصات انتخاب‌شده:", self.coords_label)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("نام مکان را وارد کنید (مثلاً: مسجد امام حسین)")
        form.addRow("نام مکان:", self.name_input)

        type_container = QWidget()
        type_layout = QHBoxLayout(type_container)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.setSpacing(6)

        # با کلیک روی تمام سطح باکس، فهرست باز می‌شود؛ اسکرول بسته، مقدار را تغییر نمی‌دهد.
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

    def _on_manual_coords_changed(self):
        # وارد کردن دستی مختصات، معادل کلیک روی نقشه است؛ هر دو مسیر باید نتیجه یکسان بدهند
        if self.lat_input.value() == 0.0 and self.lon_input.value() == 0.0:
            return
        self.selected_lat = self.lat_input.value()
        self.selected_lon = self.lon_input.value()
        self.coords_label.setText(f"عرض: {self.selected_lat:.6f} — طول: {self.selected_lon:.6f}")

    def _on_map_title_changed(self, title):
        if title.startswith("NEW_PLACE_COORDS:"):
            try:
                coords_part = title.split(":", 1)[1]
                lat_str, lon_str = coords_part.split(",")
                self.selected_lat = float(lat_str)
                self.selected_lon = float(lon_str)
                self.coords_label.setText(f"عرض: {self.selected_lat:.6f} — طول: {self.selected_lon:.6f}")
                # هماهنگ‌سازی فیلدهای عددی با نقطه کلیک‌شده روی نقشه
                self.lat_input.blockSignals(True)
                self.lon_input.blockSignals(True)
                self.lat_input.setValue(self.selected_lat)
                self.lon_input.setValue(self.selected_lon)
                self.lat_input.blockSignals(False)
                self.lon_input.blockSignals(False)
            except (IndexError, ValueError):
                pass

    def _on_save(self):
        if self.selected_lat is None or self.selected_lon is None:
            QMessageBox.warning(self, "خطا", "لطفاً ابتدا روی نقشه کلیک کنید تا مختصات مکان انتخاب شود.")
            return
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "خطا", "لطفاً نام مکان را وارد کنید.")
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "subtype": self.type_combo.currentText(),
            "lat": self.selected_lat,
            "lon": self.selected_lon,
            "address": self.address_input.text().strip(),
        }


# ------------------- Worker Threads (تا رابط کاربری قفل نشود) -------------------

class FetchOSMThread(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(dict, object)  # result, zone_id
    failed = pyqtSignal(str)

    def __init__(self, boundary_points, zone_id=None):
        super().__init__()
        self.boundary_points = boundary_points
        self.zone_id = zone_id

    def run(self):
        try:
            result = fetch_osm_data(self.boundary_points, progress_callback=self.progress.emit)
            self.finished_ok.emit(result, self.zone_id)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadTilesThread(QThread):
    progress = pyqtSignal(int, int, int, int, int)  # done, total, downloaded, skipped, failed
    finished_ok = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, db_path, min_lat, min_lon, max_lat, max_lon, zoom_levels):
        super().__init__()
        self.db_path = db_path
        self.min_lat, self.min_lon = min_lat, min_lon
        self.max_lat, self.max_lon = max_lat, max_lon
        self.zoom_levels = zoom_levels

    def run(self):
        try:
            # اتصال SQLite باید در همان Thread ای ساخته شود که در آن استفاده می‌شود؛
            # پس یک اتصال کاملاً مستقل و جدید به همان فایل دیتابیس می‌سازیم.
            thread_db = Database(self.db_path)
            result = download_tiles_for_bbox(
                thread_db, self.min_lat, self.min_lon, self.max_lat, self.max_lon,
                zoom_levels=self.zoom_levels,
                progress_callback=self.progress.emit,
                should_cancel=self.isInterruptionRequested
            )
            thread_db.close()
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class PrepareOfflineAssetsThread(QThread):
    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(dict)

    def run(self):
        result = ensure_leaflet_assets(progress_callback=self.progress.emit)
        self.finished_ok.emit(result)


# ------------------------------- پنجره اصلی -------------------------------

class MainWindow(QMainWindow):
    back_to_dashboard = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.setWindowTitle("بلوک‌بندی و محله‌بندی — سامانه جامع مدیریت محلات و بلوک‌های شهرستان جوانرود")
        self.resize(1300, 850)
        self.setMinimumSize(900, 540)

        self.db = db
        self._legacy_tile_cleanup_count = self._migrate_to_vector_offline_map()
        self.boundary_points = self.db.get_boundary()  # از دیتابیس بارگذاری می‌شود

        central = QWidget()
        central_layout = QVBoxLayout(central)
        # QTabWidget اندازه حداقل همه تب‌ها را با هم محاسبه می‌کند؛ در نمایشگرهای
        # 1366×768 این موضوع ارتفاعی بزرگ‌تر از فضای کاری ویندوز ایجاد می‌کرد.
        central_layout.setSizeConstraint(QLayout.SetNoConstraint)
        central.setMinimumSize(0, 0)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        header = build_official_header(app_subtitle="بلوک‌بندی و محله‌بندی شهر", db=self.db)
        central_layout.addWidget(header)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(12, 8, 12, 0)
        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_to_dashboard.emit)
        top_bar.addWidget(back_btn)
        top_bar.addStretch()
        central_layout.addLayout(top_bar)

        self.tabs = QTabWidget()
        self.tabs.setMinimumSize(0, 0)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        central_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self._build_draw_tab()
        self._build_zones_tab()
        self._build_view_tab()
        self._build_all_zones_view_tab()
        self._build_streets_tab()
        self._build_places_tab()
        self._build_mosques_tab()
        self._build_offline_tab()

        self.statusBar().showMessage("آماده")

    def _migrate_to_vector_offline_map(self):
        """نشانگر سازگاری را ثبت می‌کند؛ تایل‌های دانلودشده هرگز حذف نمی‌شوند."""
        marker = "offline_vector_map_v1"
        try:
            if self.db.get_meta(marker, "0") == "1":
                return 0
            self.db.set_meta(marker, "1")
            return 0
        except Exception:
            return 0

    def _write_temp_html(self, html_content, filename):
        """نوشتن HTML در یک فایل واقعی روی دیسک تا از مشکلات cross-origin
        هنگام لود اسکریپت‌های خارجی (مثل SDK نشان) در QWebEngineView جلوگیری شود."""
        temp_dir = get_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return path

    def _get_mosques_with_zone_names(self):
        """فهرست ثابت مساجد را با نام بلوک‌های مرتبط برای نمایش روی نقشه برمی‌گرداند."""
        result = []
        for mosque in self.db.get_mosques():
            item = dict(mosque)
            item["zones"] = [z["name"] for z in self.db.get_mosque_zone_names(mosque["id"])]
            result.append(item)
        return result

    # ---------------- تب ۲: مناطق/بلوک‌ها ----------------
    def _build_zones_tab(self):
        tab = QWidget()
        root_layout = QVBoxLayout(tab)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(8)

        top_hint = QLabel("برای رسم دقیق‌تر، از حالت «تمرکز روی نقشه» استفاده کنید تا پنل‌های کناری مخفی شوند.")
        top_hint.setWordWrap(True)
        root_layout.addWidget(top_hint)

        self.zones_splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(self.zones_splitter, stretch=1)

        # --- پنل نقشه و ابزارهای سریع ---
        map_panel = QWidget()
        map_layout = QVBoxLayout(map_panel)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(6)

        quick_bar = QHBoxLayout()
        self.compact_draw_info = QLabel("نقشه رسم بلوک")
        quick_bar.addWidget(self.compact_draw_info)
        quick_bar.addStretch()

        self.focus_mode_btn = QPushButton("🗺️ تمرکز روی نقشه")
        self.focus_mode_btn.setCheckable(True)
        self.focus_mode_btn.clicked.connect(self.toggle_zones_side_panel)
        quick_bar.addWidget(self.focus_mode_btn)

        redraw_btn = QPushButton("آنلاین")
        redraw_btn.clicked.connect(lambda: self._refresh_zone_draw_map(offline=False))
        quick_bar.addWidget(redraw_btn)

        offline_draw_btn = QPushButton("آفلاین")
        offline_draw_btn.clicked.connect(lambda: self._refresh_zone_draw_map(offline=True))
        quick_bar.addWidget(offline_draw_btn)

        save_zone_btn = QPushButton("ذخیره بلوک")
        save_zone_btn.setProperty("success", True)
        save_zone_btn.clicked.connect(self.on_save_new_zone)
        quick_bar.addWidget(save_zone_btn)
        map_layout.addLayout(quick_bar)

        self.zone_draw_webview = QWebEngineView()
        self.zone_draw_page = DebugWebPage(self.zone_draw_webview)
        self.zone_draw_webview.setPage(self.zone_draw_page)
        map_layout.addWidget(self.zone_draw_webview, stretch=1)
        self._refresh_zone_draw_map(offline=False)

        self.zone_draw_status = QLabel("")
        self.zone_draw_status.setStyleSheet("color:#666;")
        map_layout.addWidget(self.zone_draw_status)

        # --- پنل کناری فشرده ---
        self.zones_side_panel = QFrame()
        self.zones_side_panel.setFrameShape(QFrame.StyledPanel)
        self.zones_side_panel.setMinimumWidth(300)
        self.zones_side_panel.setMaximumWidth(380)
        side_outer = QVBoxLayout(self.zones_side_panel)
        side_outer.setContentsMargins(0, 0, 0, 0)

        side_scroll = QScrollArea()
        side_scroll.setWidgetResizable(True)
        side_scroll.setFrameShape(QFrame.NoFrame)
        side_outer.addWidget(side_scroll)

        side_content = QWidget()
        side_scroll.setWidget(side_content)
        right_col = QVBoxLayout(side_content)
        right_col.setContentsMargins(6, 6, 6, 6)
        right_col.setSpacing(8)

        # خلاصه مساحت محدوده شهر و بلوک‌ها
        area_section = CollapsibleSection("خلاصه مساحت", expanded=True)
        area_layout = QVBoxLayout()
        area_layout.setContentsMargins(0, 0, 0, 0)
        self.area_summary_label = QLabel()
        self.area_summary_label.setWordWrap(True)
        self.area_summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        area_layout.addWidget(self.area_summary_label)
        recalculate_area_btn = QPushButton("بازمحاسبه مساحت‌ها")
        recalculate_area_btn.clicked.connect(self.on_recalculate_area_metrics)
        area_layout.addWidget(recalculate_area_btn)
        area_section.setContentLayout(area_layout)
        right_col.addWidget(area_section)

        # بخش عملیات بلوک انتخابی
        zone_actions_section = CollapsibleSection("منطقه/بلوک انتخابی", expanded=True)
        zone_actions_layout = QVBoxLayout()
        zone_actions_layout.setContentsMargins(0, 0, 0, 0)

        fetch_zone_btn = QPushButton("دریافت معابر و اماکن از OSM (نیازمند اینترنت)")
        fetch_zone_btn.clicked.connect(self.on_fetch_zone_osm_data)
        zone_actions_layout.addWidget(fetch_zone_btn)

        view_offline_zone_btn = QPushButton("نمایش نقشه آفلاین بلوک")
        view_offline_zone_btn.clicked.connect(self.on_view_zone_offline_map)
        zone_actions_layout.addWidget(view_offline_zone_btn)

        add_manual_place_btn = QPushButton("افزودن مکان دستی")
        add_manual_place_btn.setProperty("success", True)
        add_manual_place_btn.clicked.connect(self.on_add_manual_place)
        zone_actions_layout.addWidget(add_manual_place_btn)

        sync_mosques_btn = QPushButton("بازبینی مساجد داخل بلوک")
        sync_mosques_btn.clicked.connect(self.on_sync_zone_mosques)
        zone_actions_layout.addWidget(sync_mosques_btn)

        snapshot_btn = QPushButton("نمای گرافیکی ذخیره‌شده")
        snapshot_btn.clicked.connect(self.on_preview_zone_snapshot)
        zone_actions_layout.addWidget(snapshot_btn)

        rebuild_snapshot_btn = QPushButton("بازسازی تصویر گرافیکی")
        rebuild_snapshot_btn.clicked.connect(self.on_rebuild_zone_snapshot)
        zone_actions_layout.addWidget(rebuild_snapshot_btn)

        rename_btn = QPushButton("تغییر نام")
        rename_btn.clicked.connect(self.on_rename_zone)
        zone_actions_layout.addWidget(rename_btn)

        delete_zone_btn = QPushButton("حذف بلوک")
        delete_zone_btn.clicked.connect(self.on_delete_zone)
        zone_actions_layout.addWidget(delete_zone_btn)

        self.zone_info_label = QLabel("منطقه‌ای انتخاب نشده است.")
        self.zone_info_label.setWordWrap(True)
        zone_actions_layout.addWidget(self.zone_info_label)

        self.zone_auto_tile_progress = QProgressBar()
        self.zone_auto_tile_progress.setVisible(False)
        zone_actions_layout.addWidget(self.zone_auto_tile_progress)

        zone_actions_section.setContentLayout(zone_actions_layout)
        right_col.addWidget(zone_actions_section)

        # بخش بلوک‌های ثبت‌شده
        zones_list_section = CollapsibleSection("بلوک‌ها", expanded=True)
        zones_list_layout = QVBoxLayout()
        zones_list_layout.setContentsMargins(0, 0, 0, 0)

        self.zones_list = QListWidget()
        self.zones_list.itemSelectionChanged.connect(self._on_zone_selection_changed)
        zones_list_layout.addWidget(self.zones_list)

        focus_selected_btn = QPushButton("نمایش روی نقشه")
        focus_selected_btn.clicked.connect(self.on_focus_selected_zone)
        zones_list_layout.addWidget(focus_selected_btn)

        zones_list_section.setContentLayout(zones_list_layout)
        right_col.addWidget(zones_list_section)

        # بخش نقشه آفلاین
        offline_section = CollapsibleSection("نقشه آفلاین شهر", expanded=False)
        offline_layout = QVBoxLayout()
        offline_layout.setContentsMargins(0, 0, 0, 0)

        offline_info = QLabel(
            "نقشه آفلاین از مرز بلوک‌ها، معابر و اماکن ذخیره‌شده در دیتابیس ساخته می‌شود و هیچ درخواست تایل اینترنتی ندارد."
        )
        offline_info.setWordWrap(True)
        offline_layout.addWidget(offline_info)

        prepare_engine_btn = QPushButton("آماده‌سازی موتور آفلاین")
        prepare_engine_btn.clicked.connect(self.on_prepare_offline_assets)
        offline_layout.addWidget(prepare_engine_btn)

        self.offline_engine_status = QLabel(
            "موتور آفلاین آماده است." if leaflet_vendor_files_available() else "موتور آفلاین کامل نشده است."
        )
        self.offline_engine_status.setWordWrap(True)
        offline_layout.addWidget(self.offline_engine_status)

        self.zones_zoom_min_spin = QSpinBox()
        self.zones_zoom_min_spin.setRange(1, 19)
        self.zones_zoom_min_spin.setValue(12)
        self.zones_zoom_min_spin.setVisible(False)
        self.zones_zoom_max_spin = QSpinBox()
        self.zones_zoom_max_spin.setRange(1, 19)
        self.zones_zoom_max_spin.setValue(18)
        self.zones_zoom_max_spin.setVisible(False)

        prepare_vector_btn = QPushButton("پاک‌سازی کش خراب و آماده‌سازی نقشه آفلاین")
        prepare_vector_btn.setProperty("success", True)
        prepare_vector_btn.clicked.connect(self.on_prepare_vector_offline_map)
        offline_layout.addWidget(prepare_vector_btn)

        self.zones_estimate_label = QLabel("حالت آفلاین داخلی فعال است؛ دانلود تایل لازم نیست.")
        self.zones_estimate_label.setWordWrap(True)
        offline_layout.addWidget(self.zones_estimate_label)

        self.zones_download_progress = QProgressBar()
        self.zones_download_progress.setVisible(False)
        offline_layout.addWidget(self.zones_download_progress)

        self.zones_download_status = QLabel("")
        self.zones_download_status.setWordWrap(True)
        offline_layout.addWidget(self.zones_download_status)

        offline_section.setContentLayout(offline_layout)
        right_col.addWidget(offline_section)
        right_col.addStretch()

        self.zones_splitter.addWidget(map_panel)
        self.zones_splitter.addWidget(self.zones_side_panel)
        self.zones_splitter.setStretchFactor(0, 5)
        self.zones_splitter.setStretchFactor(1, 2)
        self.zones_splitter.setSizes([1100, 330])

        self.tabs.addTab(tab, "۲. مناطق/بلوک‌ها")
        self.refresh_zones_list()
        self._refresh_area_summary_labels()

    @staticmethod
    def _format_area_value(area_m2):
        area_m2 = float(area_m2 or 0.0)
        return f"{area_m2 / 10000.0:,.2f} هکتار ({area_m2:,.0f} مترمربع)"

    def _refresh_area_summary_labels(self):
        summary = self.db.get_area_summary()
        city_ready = summary["city_area_m2"] > 0
        city_text = self._format_area_value(summary["city_area_m2"]) if city_ready else "ثبت نشده"
        block_text = self._format_area_value(summary["block_area_m2"])
        difference_text = self._format_area_value(abs(summary["difference_m2"]))
        difference_title = "مساحت باقیمانده" if summary["difference_m2"] >= 0 else "مازاد بلوک‌ها نسبت به شهر"
        coverage_text = f"{summary['coverage_percent']:.2f}٪" if city_ready else "—"
        summary_text = (
            f"مساحت محدوده شهر: {city_text}\n"
            f"مجموع {summary['zone_count']} بلوک: {block_text}\n"
            f"درصد پوشش بلوک‌ها: {coverage_text}\n"
            f"{difference_title}: {difference_text}"
        )
        if hasattr(self, "area_summary_label"):
            self.area_summary_label.setText(summary_text)
        if hasattr(self, "city_area_summary_label"):
            self.city_area_summary_label.setText(summary_text)

    def on_recalculate_area_metrics(self):
        updated = self.db.recalculate_all_zone_metrics()
        self.refresh_zones_list()
        self._refresh_area_summary_labels()
        self.refresh_all_zones_view()
        QMessageBox.information(
            self, "بازمحاسبه انجام شد",
            f"مساحت و محیط {updated} بلوک از روی نقاط مرزی دوباره محاسبه شد."
        )

    def toggle_zones_side_panel(self):
        visible = self.zones_side_panel.isVisible()
        self.zones_side_panel.setVisible(not visible)
        if visible:
            self.focus_mode_btn.setText("↩ بازگشت پنل‌ها")
            self.zone_draw_status.setText((self.zone_draw_status.text() + " — حالت تمرکز روی نقشه فعال است.").strip(" —"))
            self.zones_splitter.setSizes([1, 0])
        else:
            self.focus_mode_btn.setText("🗺️ تمرکز روی نقشه")
            self.zones_splitter.setSizes([1100, 330])

    def on_focus_selected_zone(self):
        row = self.zones_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "انتخاب بلوک", "ابتدا یک بلوک را از فهرست انتخاب کنید.")
            return
        zone = self.db.get_zones()[row]
        self._refresh_zone_draw_map(offline=False)
        self.zone_draw_status.setText(f"برای بررسی دقیق، بلوک «{zone['name']}» را از روی نقشه ببینید.")

    def _refresh_zone_draw_map(self, offline=False):
        if offline:
            if not leaflet_vendor_files_available():
                QMessageBox.warning(
                    self, "موتور آفلاین آماده نیست",
                    "ابتدا دکمه «آماده‌سازی موتور نقشه آفلاین» را بزنید و در حالت آنلاین فایل‌های لازم را دریافت کنید."
                )
                return
        zones = self.db.get_zones()
        html = build_zone_draw_html(
            existing_zones=zones, boundary_points=self.boundary_points,
            mosques=self.db.get_mosques(), places=self.db.get_places(), schools=self.db.get_schools(),
            health_centers=self.db.get_health_centers(), offline=offline
        )
        path = self._write_temp_html(html, "zone_draw_offline.html" if offline else "zone_draw_online.html")
        self.zone_draw_webview.setUrl(QUrl.fromLocalFile(path))
        if hasattr(self, "zone_draw_status"):
            self.zone_draw_status.setText("نقشه رسم آفلاین فعال است." if offline else "نقشه رسم آنلاین فعال است.")
        if hasattr(self, "compact_draw_info"):
            self.compact_draw_info.setText("نقشه رسم بلوک — آفلاین" if offline else "نقشه رسم بلوک — آنلاین")

    def on_prepare_vector_offline_map(self):
        try:
            self.db.set_meta("offline_vector_map_v1", "1")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"پاک‌سازی کش قدیمی انجام نشد:\n{exc}")
            return
        if hasattr(self, "tile_count_label"):
            self._update_tile_count_label()
        if hasattr(self, "zones_download_status"):
            self.zones_download_status.setText(
                "نقشه آفلاین آماده است؛ تایل‌ها و اطلاعات قبلی حفظ شدند."
            )
        QMessageBox.information(
            self, "نقشه آفلاین آماده شد",
            f"نقشه آفلاین داخلی فعال شد.\n{removed} تایل قدیمی یا مسدود پاک شد.\n"
            "مرزها، معابر و اماکن ذخیره‌شده بدون اینترنت نمایش داده می‌شوند."
        )

    def on_prepare_offline_assets(self):
        self.offline_engine_status.setText("در حال دریافت فایل‌های موتور نقشه آفلاین ...")
        self.prepare_assets_thread = PrepareOfflineAssetsThread()
        self.prepare_assets_thread.progress.connect(self.offline_engine_status.setText)
        self.prepare_assets_thread.finished_ok.connect(self._on_offline_assets_ready)
        self.prepare_assets_thread.start()

    def _on_offline_assets_ready(self, result):
        if result.get("ok"):
            self.offline_engine_status.setText("✅ موتور نقشه آفلاین آماده است.")
            QMessageBox.information(self, "آماده شد", "فایل‌های Leaflet برای اجرای کامل نقشه آفلاین ذخیره شدند.")
        else:
            failed = "، ".join(result.get("failed", []))
            self.offline_engine_status.setText("⚠ دریافت بعضی فایل‌ها ناموفق بود: " + failed)
            QMessageBox.warning(self, "دانلود ناقص", "دریافت فایل‌های زیر ناموفق بود:\n" + failed)
            QMessageBox.warning(self, "دانلود ناقص", "دریافت فایل‌های زیر ناموفق بود:\n" + failed)

    def on_save_new_zone(self):
        self.zone_draw_webview.page().runJavaScript("getPoints();", self._handle_new_zone_points)

    def _handle_new_zone_points(self, points_json_str):
        import json
        try:
            points = json.loads(points_json_str)
        except Exception:
            points = []

        if len(points) < 3:
            QMessageBox.warning(self, "خطا", "حداقل ۳ نقطه برای تشکیل منطقه لازم است.")
            return

        name, ok = QInputDialog.getText(self, "نام منطقه", "یک نام برای این منطقه/بلوک وارد کنید:")
        if not ok or not name.strip():
            QMessageBox.information(self, "لغو شد", "ذخیره منطقه لغو شد (نامی وارد نشد).")
            return

        boundary_points = [(p[0], p[1]) for p in points]
        valid, validation_message = validate_polygon(boundary_points)
        if not valid:
            QMessageBox.warning(self, "محدوده نامعتبر", validation_message)
            return

        overlapping = [
            z["name"] for z in self.db.get_zones()
            if polygons_overlap(boundary_points, z.get("boundary_points", []))
        ]
        if overlapping:
            reply = QMessageBox.question(
                self, "هم‌پوشانی بلوک‌ها",
                "محدوده جدید با بلوک‌های زیر هم‌پوشانی دارد:\n" + "، ".join(overlapping) +
                "\n\nثبت بلوک هم‌پوشان ممکن است خیابان‌ها و مساجد را به چند بلوک منتسب کند. ادامه می‌دهید؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        zone_id = self.db.create_zone(name.strip(), boundary_points)
        zone = self.db.get_zone(zone_id)
        mosque_count = len(self.db.get_mosques(zone_id=zone_id))

        area_m2 = float(zone.get("area_m2") or 0.0)
        self.zone_draw_status.setText(
            f"منطقه «{name}» با {len(points)} نقطه، مساحت {area_m2 / 10000.0:,.2f} هکتار "
            f"و {mosque_count} مسجد داخل محدوده ذخیره شد."
        )
        QMessageBox.information(
            self, "موفق",
            f"منطقه «{name}» ذخیره شد.\nرنگ اختصاصی: {zone['color']}\n"
            f"مساحت: {area_m2 / 10000.0:,.2f} هکتار\nمساجد داخل بلوک: {mosque_count}"
        )

        self.refresh_zones_list()
        self._refresh_area_summary_labels()
        self._refresh_zone_draw_map(offline=False)
        self.refresh_all_zones_view()
        self._reload_zone_combos()
        if hasattr(self, "mosques_table"):
            self.refresh_mosques_table()
        if hasattr(self, "places_table"):
            self.refresh_places_table()

    def refresh_zones_list(self):
        self.zones_list.clear()
        zones = self.db.get_zones()
        for z in zones:
            area_ha = (z.get("area_m2", 0) or 0) / 10000
            item = QListWidgetItem(
                f"  {z['name']}  [{z.get('status', 'ناقص')}]  (مساحت: {area_ha:.2f} هکتار، "
                f"خیابان: {z['street_count']}، مکان: {z['place_count']}، مسجد: {z['mosque_count']})"
            )
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(z["color"]))
            item.setIcon(QIcon(pixmap))
            item.setData(Qt.UserRole, z["id"])
            self.zones_list.addItem(item)

    def _get_selected_zone_id(self):
        items = self.zones_list.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)

    def _on_zone_selection_changed(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            self.zone_info_label.setText("منطقه‌ای انتخاب نشده است.")
            return
        zone = self.db.get_zone(zone_id)
        streets = self.db.get_streets(zone_id=zone_id)
        places = self.db.get_places(zone_id=zone_id)
        mosques = self.db.get_mosques(zone_id=zone_id)
        mosque_names = "، ".join(m["name"] for m in mosques) if mosques else "—"
        self.zone_info_label.setText(
            f"نام: {zone['name']}\nوضعیت تکمیل: {zone.get('status', 'ناقص')}\nرنگ: {zone['color']}\nنقاط مرزی: {len(zone['boundary_points'])}\n"
            f"مساحت: {(zone.get('area_m2', 0) or 0) / 10000:.2f} هکتار | محیط: {zone.get('perimeter_m', 0) or 0:.0f} متر\n"
            f"خیابان/کوچه ذخیره‌شده: {len(streets)}\nاماکن ذخیره‌شده: {len(places)}\n"
            f"مساجد داخل بلوک: {len(mosques)}\n{mosque_names}"
        )
        # هماهنگ‌سازی کمبوباکس فیلتر منطقه در تب‌های جدول و آفلاین (در صورت وجود)
        if hasattr(self, "streets_zone_filter"):
            self._sync_zone_combo(self.streets_zone_filter, zone_id)
        if hasattr(self, "places_zone_filter"):
            self._sync_zone_combo(self.places_zone_filter, zone_id)
        if hasattr(self, "offline_zone_combo"):
            self._sync_zone_combo(self.offline_zone_combo, zone_id)

    def _sync_zone_combo(self, combo, zone_id):
        idx = combo.findData(zone_id)
        if idx >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def on_view_zone_offline_map(self):
        """
        نمایش نقشه آفلاین مخصوص بلوک انتخاب‌شده (نه محدوده کلی شهر) در یک پنجره جدا.
        این جدا از تب «۲. نمایش نقشه» است چون آن تب همیشه محدوده کلی شهر را نشان
        می‌دهد و اگر فقط تایل‌های یک بلوک کوچک دانلود شده باشند، بقیه نقشه خالی/محو
        دیده می‌شود.
        """
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return

        zone = self.db.get_zone(zone_id)
        if not zone or len(zone["boundary_points"]) < 3:
            QMessageBox.warning(self, "خطا", "محدوده این منطقه معتبر نیست.")
            return


        if not leaflet_vendor_files_available():
            QMessageBox.warning(
                self, "فایل‌های Leaflet یافت نشد",
                "برای نمایش نقشه آفلاین، فایل‌های leaflet.js و leaflet.css باید در پوشه "
                "vendor/leaflet قرار داشته باشند. راهنمای دانلود در vendor/leaflet/README.md "
                "موجود است. بدون این فایل‌ها، نقشه آفلاین نمایش داده نخواهد شد."
            )
            return

        streets = self.db.get_streets(zone_id=zone_id)
        places = self.db.get_places(zone_id=zone_id)
        mosques = self.db.get_mosques(zone_id=zone_id)
        for mosque in mosques:
            mosque["zones"] = [zone["name"]]
        html = build_view_mode_html(
            zone["boundary_points"], streets, places, mosques=mosques, offline=True,
            schools=self.db.get_schools(zone_id=zone_id),
            health_centers=self.db.get_health_centers(zone_id=zone_id),
        )
        path = self._write_temp_html(html, f"zone_offline_view_{zone_id}.html")

        dialog = QDialog(self)
        dialog.setWindowTitle(f"نقشه آفلاین بلوک: {zone['name']}")
        dialog.resize(1000, 750)
        layout = QVBoxLayout(dialog)

        info_label = QLabel(
            f"نقشه آفلاین «{zone['name']}» — {len(streets)} خیابان/کوچه، {len(places)} مکان و {len(mosques)} مسجد"
        )
        layout.addWidget(info_label)

        webview = QWebEngineView()
        webview.setPage(DebugWebPage(webview))
        webview.setUrl(QUrl.fromLocalFile(path))
        layout.addWidget(webview)

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.exec_()

    def on_sync_zone_mosques(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        zone = self.db.get_zone(zone_id)
        count = self.db.sync_zone_mosques(zone_id, zone["boundary_points"])
        self.refresh_zones_list()
        self._on_zone_selection_changed()
        self.refresh_all_zones_view()
        if hasattr(self, "mosques_table"):
            self.refresh_mosques_table()
        if hasattr(self, "places_table"):
            self.refresh_places_table()
        QMessageBox.information(
            self, "همگام‌سازی انجام شد",
            f"برای بلوک «{zone['name']}» تعداد {count} مسجد بر اساس مختصات واقعی داخل چندضلعی ثبت شد."
        )

    def on_rebuild_zone_snapshot(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        try:
            snapshot = refresh_zone_snapshot(self.db, zone_id, force=True)
            QMessageBox.information(
                self, "تصویر بلوک ساخته شد",
                f"نمای گرافیکی بلوک با موفقیت در دیتابیس ذخیره شد.\n"
                f"نسخه: {snapshot.get('version', 1)}\n"
                f"زمان تولید: {format_jalali(snapshot.get('generated_at')) or '—'}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"ساخت تصویر گرافیکی بلوک ممکن نشد:\n{exc}")

    def on_preview_zone_snapshot(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        try:
            snapshot = refresh_zone_snapshot(self.db, zone_id, force=False)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"نمای گرافیکی بلوک آماده نشد:\n{exc}")
            return
        png_data = snapshot.get("png_data") if snapshot else None
        if not png_data:
            QMessageBox.warning(self, "خطا", "تصویر ذخیره‌شده‌ای برای این بلوک وجود ندارد.")
            return

        zone = self.db.get_zone(zone_id)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"نمای گرافیکی بلوک — {zone['name']}")
        dialog.resize(1000, 760)
        layout = QVBoxLayout(dialog)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap()
        pixmap.loadFromData(png_data, "PNG")
        image_label.setPixmap(pixmap.scaled(940, 650, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(image_label, stretch=1)

        meta = QLabel(
            f"نسخه {snapshot.get('version', 1)} — تولید: {format_jalali(snapshot.get('generated_at')) or '—'} — "
            "این تصویر داخل دیتابیس ذخیره شده و در گزارش‌ها استفاده می‌شود."
        )
        meta.setWordWrap(True)
        layout.addWidget(meta)

        actions = QHBoxLayout()
        save_png_btn = QPushButton("ذخیره PNG")
        save_svg_btn = QPushButton("ذخیره SVG")
        rebuild_btn = QPushButton("بازسازی")
        close_btn = QPushButton("بستن")
        actions.addWidget(save_png_btn)
        actions.addWidget(save_svg_btn)
        actions.addWidget(rebuild_btn)
        actions.addStretch()
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        def save_png():
            path, _ = QFileDialog.getSaveFileName(dialog, "ذخیره تصویر بلوک", f"{zone['name']}.png", "PNG (*.png)")
            if path and export_zone_snapshot_png(self.db, zone_id, path):
                QMessageBox.information(dialog, "ذخیره شد", f"تصویر در مسیر زیر ذخیره شد:\n{path}")

        def save_svg():
            path, _ = QFileDialog.getSaveFileName(dialog, "ذخیره نمای برداری بلوک", f"{zone['name']}.svg", "SVG (*.svg)")
            if path and export_zone_snapshot_svg(self.db, zone_id, path):
                QMessageBox.information(dialog, "ذخیره شد", f"فایل برداری در مسیر زیر ذخیره شد:\n{path}")

        def rebuild():
            try:
                updated = refresh_zone_snapshot(self.db, zone_id, force=True)
                updated_pixmap = QPixmap()
                updated_pixmap.loadFromData(updated["png_data"], "PNG")
                image_label.setPixmap(updated_pixmap.scaled(940, 650, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                meta.setText(
                    f"نسخه {updated.get('version', 1)} — تولید: {format_jalali(updated.get('generated_at')) or '—'} — "
                    "تصویر جدید در دیتابیس ذخیره شد."
                )
            except Exception as exc:
                QMessageBox.critical(dialog, "خطا", str(exc))

        save_png_btn.clicked.connect(save_png)
        save_svg_btn.clicked.connect(save_svg)
        rebuild_btn.clicked.connect(rebuild)
        close_btn.clicked.connect(dialog.accept)
        dialog.exec_()

    def on_rename_zone(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        zone = self.db.get_zone(zone_id)
        new_name, ok = QInputDialog.getText(self, "تغییر نام منطقه", "نام جدید:", text=zone["name"])
        if ok and new_name.strip():
            self.db.update_zone(zone_id, name=new_name.strip())
            self.refresh_zones_list()
            self._refresh_zone_draw_map(offline=False)
            self.refresh_all_zones_view()
            if hasattr(self, "mosques_table"):
                self.refresh_mosques_table()
            if hasattr(self, "places_table"):
                self.refresh_places_table()

    def on_delete_zone(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        zone = self.db.get_zone(zone_id)
        reply = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف منطقه «{zone['name']}» و تمام خیابان‌ها/اماکن مرتبط با آن مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_zone(zone_id)
            self.refresh_zones_list()
            self._refresh_area_summary_labels()
            self._refresh_zone_draw_map(offline=False)
            self.refresh_all_zones_view()
            self.refresh_streets_table()
            self.refresh_places_table()
            self._reload_zone_combos()
            if hasattr(self, "mosques_table"):
                self.refresh_mosques_table()

    def on_fetch_zone_osm_data(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        zone = self.db.get_zone(zone_id)
        boundary_points = zone["boundary_points"]

        if len(boundary_points) < 3:
            QMessageBox.warning(self, "خطا", "محدوده این منطقه معتبر نیست.")
            return

        self.zone_info_label.setText(f"در حال دریافت اطلاعات منطقه «{zone['name']}» از OpenStreetMap ...")
        self.fetch_zone_thread = FetchOSMThread(boundary_points, zone_id=zone_id)
        self.fetch_zone_thread.progress.connect(lambda msg: self.zone_info_label.setText(msg))
        self.fetch_zone_thread.finished_ok.connect(self.on_zone_osm_data_ready)
        self.fetch_zone_thread.failed.connect(self.on_osm_data_failed)
        self.fetch_zone_thread.start()

    def on_zone_osm_data_ready(self, result, zone_id):
        streets = result.get("streets", [])
        places = result.get("places", [])
        streets_ok = result.get("streets_ok", True)
        places_ok = result.get("places_ok", True)
        errors = result.get("errors", {})
        unmatched_tags = result.get("unmatched_tags", [])
        government_tag_samples = result.get("government_tag_samples", [])
        dropped_no_coords = result.get("dropped_no_coords", [])

        self.db.replace_osm_data(
            zone_id, streets=streets, places=places,
            replace_streets=streets_ok, replace_places=places_ok
        )

        zone = self.db.get_zone(zone_id)
        message_parts = [f"نتیجه دریافت اطلاعات برای منطقه «{zone['name']}»:"]
        if streets_ok:
            street_stats = result.get("street_stats", {})
            message_parts.append(f"✅ {len(streets)} قطعه خیابان/کوچه داخل مرز بلوک ذخیره شد.")
            if street_stats:
                message_parts.append(
                    f"   مسیر خام: {street_stats.get('raw_ways', 0)} | بدون نام: {street_stats.get('unnamed_ways', 0)} | "
                    f"خارج از محدوده: {street_stats.get('outside_ways', 0)}"
                )
        else:
            message_parts.append("⚠ دریافت خیابان‌ها ناموفق بود؛ اطلاعات قبلی خیابان‌ها حفظ شد.")
        if places_ok:
            place_stats = result.get("place_stats", {})
            message_parts.append(f"✅ {len(places)} مکان داخل مرز بلوک ذخیره شد.")
            if place_stats and place_stats.get("outside"):
                message_parts.append(f"   {place_stats.get('outside')} مکانِ خارج از چندضلعی کنار گذاشته شد.")
        else:
            message_parts.append("⚠ دریافت اماکن ناموفق بود؛ اطلاعات قبلی اماکن حفظ شد.")
        if errors:
            message_parts.append("⚠ بخشی از سرویس آنلاین OSM پاسخ نداد؛ داده‌های قبلی همان بخش حفظ شد.")
        message = "\n".join(message_parts)
        if unmatched_tags:
            sample = "، ".join(unmatched_tags[:15])
            message += (
                f"\n\nاطلاعات عیب‌یابی: عناصر دیگری با این برچسب‌ها در محدوده یافت شدند "
                f"که در دسته‌بندی‌های فعلی برنامه نیستند:\n{sample}"
                + ("\n(و موارد بیشتر...)" if len(unmatched_tags) > 15 else "")
            )
        if dropped_no_coords:
            sample = "\n".join(dropped_no_coords[:10])
            message += (
                f"\n\n⚠ {len(dropped_no_coords)} مکان با تگ درست شناسایی شدند اما مختصات "
                f"قابل‌استفاده نداشتند (نادیده گرفته شدند):\n{sample}"
            )
        if government_tag_samples:
            message += "\n\nنمونه تگ‌های کامل مواردی که «اداره دولتی» تشخیص داده شدند:\n"
            for i, sample_tags in enumerate(government_tag_samples, start=1):
                message += f"{i}. {sample_tags}\n"
        message += "\n\nنقشه آفلاین داخلی از همین داده‌های ذخیره‌شده ساخته می‌شود و دانلود تایل لازم نیست."
        QMessageBox.information(self, "موفق", message)

        self.refresh_zones_list()
        self._on_zone_selection_changed()
        self.refresh_streets_table()
        self.refresh_places_table()
        self.refresh_all_zones_view()

        self.zone_info_label.setText(
            f"✅ داده‌های بلوک «{zone['name']}» ذخیره شد؛ نقشه آفلاین داخلی آماده نمایش است."
        )

    def _auto_download_zone_tiles(self, zone_id, zone_name, zoom_min=12, zoom_max=18):
        zone = self.db.get_zone(zone_id)
        if not zone or len(zone["boundary_points"]) < 3:
            return

        points = zone["boundary_points"]
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        min_lat, min_lon, max_lat, max_lon = min(lats), min(lons), max(lats), max(lons)
        zoom_levels = range(zoom_min, zoom_max + 1)

        self.zone_info_label.setText(
            f"در حال دانلود خودکار تایل‌های نقشه برای منطقه «{zone_name}» ..."
        )
        self.zone_auto_tile_progress.setVisible(True)
        self.zone_auto_tile_progress.setValue(0)

        self.auto_tile_download_thread = DownloadTilesThread(
            self.db.db_path, min_lat, min_lon, max_lat, max_lon, zoom_levels
        )
        self.auto_tile_download_thread.progress.connect(
            self._on_auto_zone_tiles_progress
        )
        self.auto_tile_download_thread.finished_ok.connect(
            lambda result: self._on_auto_zone_tiles_finished(zone_id, zone_name, result)
        )
        self.auto_tile_download_thread.failed.connect(
            lambda err: self._on_auto_zone_tiles_failed(zone_name, err)
        )
        self.auto_tile_download_thread.start()

    def _on_auto_zone_tiles_progress(self, done, total, downloaded, skipped, failed):
        pct = int((done / total) * 100) if total else 0
        self.zone_auto_tile_progress.setValue(pct)
        self.zone_info_label.setText(
            f"در حال دانلود نقشه آفلاین: {done}/{total} تایل (دانلود‌شده: {downloaded}) — لطفاً صبر کنید ..."
        )

    def _on_auto_zone_tiles_failed(self, zone_name, err):
        self.zone_auto_tile_progress.setVisible(False)
        self.zone_info_label.setText(
            f"⚠ دانلود خودکار تایل‌های نقشه برای «{zone_name}» ناموفق بود: {err}"
        )

    def _on_auto_zone_tiles_finished(self, zone_id, zone_name, result):
        self.zone_auto_tile_progress.setValue(100)
        self.zone_info_label.setText(
            f"✅ نقشه بلوک «{zone_name}» برای استفاده آفلاین کامل ذخیره شد "
            f"({result['downloaded']} تایل جدید دانلود شد، {result['skipped']} تایل از قبل موجود بود)."
        )
        if hasattr(self, "tile_count_label"):
            self._update_tile_count_label()
        QMessageBox.information(
            self, "نقشه آفلاین این بلوک آماده شد",
            f"دانلود خودکار تصویر نقشه برای بلوک «{zone_name}» به پایان رسید.\n"
            f"({result['downloaded']} تایل جدید دانلود شد، {result['skipped']} تایل از قبل موجود بود)\n\n"
            f"اکنون خیابان‌ها، اماکن و تصویر نقشه این بلوک به‌طور کامل برای استفاده آفلاین ذخیره شده‌اند."
        )
        self.zone_auto_tile_progress.setVisible(False)

    def on_add_manual_place(self):
        zone_id = self._get_selected_zone_id()
        if zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک منطقه را از لیست انتخاب کنید.")
            return
        zone = self.db.get_zone(zone_id)

        dialog = ManualPlaceDialog(self.db, zone, self._write_temp_html, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            # همه اماکن دستی در جدول واحد places ذخیره می‌شوند تا بدون استثنا در
            # تمام نقشه‌ها دیده شوند و ثبت مسئول عمومی برایشان فعال باشد.
            self.db.save_place(
                osm_id=None, name=data["name"], category="manual", subtype=data["subtype"],
                lat=data["lat"], lon=data["lon"], address=data["address"], zone_id=zone_id,
            )
            QMessageBox.information(
                self, "ذخیره شد",
                f"مکان «{data['name']}» با آیکون اختصاصی به بلوک «{zone['name']}» اضافه شد.\n"
                "این مکان در تمام نقشه‌های سامانه قابل مشاهده است و در صورت انتخاب به‌عنوان محل جلسه، "
                "فرم ثبت مسئول آن باز می‌شود."
            )

            self.refresh_zones_list()
            self._on_zone_selection_changed()
            self.refresh_places_table()
            self.refresh_all_zones_view()
            # نقشه کامل و نقشه رسم بلوک نیز بلافاصله تازه‌سازی شوند.
            try:
                self.refresh_view_map(offline=False)
            except Exception:
                pass
            try:
                self._refresh_zone_draw_map(offline=False)
            except Exception:
                pass

    def _reload_zone_combos(self):
        """پرکردن مجدد کمبوباکس‌های انتخاب منطقه در تب‌های دیگر پس از تغییرات."""
        zones = self.db.get_zones()
        for combo_attr in ("streets_zone_filter", "places_zone_filter", "offline_zone_combo"):
            if hasattr(self, combo_attr):
                combo = getattr(self, combo_attr)
                combo.blockSignals(True)
                combo.clear()
                combo.addItem("همه مناطق", None)
                for z in zones:
                    combo.addItem(z["name"], z["id"])
                combo.blockSignals(False)

    # ---------------- تب ۴: نقشه کلی همه مناطق ----------------
    def _build_all_zones_view_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        btn_row = QHBoxLayout()
        refresh_online_btn = QPushButton("بروزرسانی نقشه کلی (آنلاین)")
        refresh_online_btn.clicked.connect(lambda: self.refresh_all_zones_view(offline=False))
        btn_row.addWidget(refresh_online_btn)

        refresh_offline_btn = QPushButton("نمایش نقشه کلی آفلاین")
        refresh_offline_btn.clicked.connect(lambda: self.refresh_all_zones_view(offline=True))
        btn_row.addWidget(refresh_offline_btn)
        layout.addLayout(btn_row)

        self.all_zones_webview = QWebEngineView()
        self.all_zones_page = DebugWebPage(self.all_zones_webview)
        self.all_zones_webview.setPage(self.all_zones_page)
        layout.addWidget(self.all_zones_webview)

        self.tabs.addTab(tab, "۴. نقشه کلی مناطق")
        self.refresh_all_zones_view()

    def refresh_all_zones_view(self, offline=False):
        if offline and not leaflet_vendor_files_available():
            QMessageBox.warning(
                self, "فایل‌های Leaflet یافت نشد",
                "برای نمایش نقشه آفلاین، فایل‌های leaflet.js و leaflet.css باید در پوشه "
                "vendor/leaflet قرار داشته باشند. راهنمای دانلود در vendor/leaflet/README.md "
                "موجود است."
            )
            return
        zones = self.db.get_zones()
        full_zones = []
        for z in zones:
            full_zones.append({
                "id": z.get("id"),
                "name": z["name"],
                "color": z["color"],
                "status": z.get("status") or "ناقص",
                "area_m2": z.get("area_m2") or 0,
                "boundary_points": z["boundary_points"],
                "streets": self.db.get_streets(zone_id=z["id"]),
                "places": self.db.get_places(zone_id=z["id"]),
                "mosques": self.db.get_mosques(zone_id=z["id"]),
            })
        html = build_all_zones_view_html(
            full_zones, boundary_points=self.boundary_points, offline=offline,
            mosques=self._get_mosques_with_zone_names(),
            schools=self.db.get_schools(), health_centers=self.db.get_health_centers(),
        )
        path = self._write_temp_html(html, "all_zones_view.html")
        self.all_zones_webview.setUrl(QUrl.fromLocalFile(path))

    # ---------------- تب ۱: رسم محدوده ----------------
    def _build_draw_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel("روی نقشه کلیک کنید تا نقاط مرزی محدوده شهر جوانرود را مشخص کنید. سپس روی «ذخیره محدوده» بزنید.")
        layout.addWidget(info)

        self.draw_webview = QWebEngineView()
        self.draw_page = DebugWebPage(self.draw_webview)
        self.draw_webview.setPage(self.draw_page)
        self._draw_html_path = self._write_temp_html(build_draw_mode_html(), "draw_mode.html")
        self.draw_webview.setUrl(QUrl.fromLocalFile(self._draw_html_path))
        layout.addWidget(self.draw_webview)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("ذخیره محدوده در دیتابیس")
        save_btn.clicked.connect(self.on_save_boundary)
        btn_row.addWidget(save_btn)

        fetch_btn = QPushButton("دریافت خیابان‌ها و اماکن از OpenStreetMap")
        fetch_btn.clicked.connect(self.on_fetch_osm_data)
        btn_row.addWidget(fetch_btn)

        layout.addLayout(btn_row)

        self.draw_status = QLabel("")
        layout.addWidget(self.draw_status)

        self.city_area_summary_label = QLabel()
        self.city_area_summary_label.setWordWrap(True)
        self.city_area_summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.city_area_summary_label)
        self._refresh_area_summary_labels()

        self.tabs.addTab(tab, "۱. رسم محدوده")

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

        boundary_points = [(p[0], p[1]) for p in points]
        valid, validation_message = validate_polygon(boundary_points, minimum_area_m2=100.0)
        if not valid:
            QMessageBox.warning(self, "محدوده نامعتبر", validation_message.replace("بلوک", "محدوده شهر"))
            return

        self.boundary_points = boundary_points
        self.db.save_boundary(self.boundary_points)
        area_m2, perimeter_m = polygon_metrics(self.boundary_points)
        self.draw_status.setText(
            f"محدوده با {len(points)} نقطه ذخیره شد — مساحت: {area_m2 / 10000.0:,.2f} هکتار"
        )
        self._refresh_area_summary_labels()
        QMessageBox.information(
            self, "موفق",
            f"محدوده شهر با {len(points)} نقطه ذخیره شد.\n"
            f"مساحت: {area_m2 / 10000.0:,.2f} هکتار\n"
            f"محیط: {perimeter_m:,.0f} متر"
        )

    def on_fetch_osm_data(self):
        if not self.boundary_points or len(self.boundary_points) < 3:
            QMessageBox.warning(self, "خطا", "ابتدا محدوده شهر را رسم و ذخیره کنید.")
            return

        self.draw_status.setText("در حال دریافت اطلاعات از OpenStreetMap ...")
        self.fetch_thread = FetchOSMThread(self.boundary_points, zone_id=None)
        self.fetch_thread.progress.connect(lambda msg: self.draw_status.setText(msg))
        self.fetch_thread.finished_ok.connect(self.on_osm_data_ready)
        self.fetch_thread.failed.connect(self.on_osm_data_failed)
        self.fetch_thread.start()

    def on_osm_data_ready(self, result, zone_id):
        # این متد فقط برای دریافت خیابان‌ها/اماکن «کل محدوده شهر» (بدون منطقه) استفاده می‌شود
        streets = result.get("streets", [])
        places = result.get("places", [])
        streets_ok = result.get("streets_ok", True)
        places_ok = result.get("places_ok", True)
        errors = result.get("errors", {})

        self.db.replace_osm_data(
            None, streets=streets, places=places,
            replace_streets=streets_ok, replace_places=places_ok
        )

        status_parts = []
        status_parts.append(f"خیابان‌ها: {len(streets)} ذخیره شد" if streets_ok else "خیابان‌ها: خطا، داده قبلی حفظ شد")
        status_parts.append(f"اماکن: {len(places)} ذخیره شد" if places_ok else "اماکن: خطا، داده قبلی حفظ شد")
        message = " — ".join(status_parts)
        if errors:
            message += "\n⚠ بخشی از سرویس آنلاین پاسخ نداد؛ داده‌های قبلی حفظ شد."
        self.draw_status.setText(message)
        QMessageBox.information(self, "نتیجه دریافت", message)

        self.refresh_streets_table()
        self.refresh_places_table()
        self.refresh_view_map()

    def on_osm_data_failed(self, error_msg):
        self.draw_status.setText("سرویس آنلاین OSM در دسترس نبود؛ اطلاعات قبلی حفظ شد.")
        QMessageBox.warning(
            self, "عدم دسترسی به سرویس آنلاین",
            "ارتباط با سرویس OpenStreetMap/Overpass برقرار نشد.\n"
            "اطلاعات قبلی حذف نشده است. برای ادامه آفلاین از داده‌های ذخیره‌شده استفاده کنید "
            "و دریافت آنلاین را بعداً با اینترنت پایدار دوباره انجام دهید."
        )

    # ---------------- تب ۲: نمایش نقشه کامل ----------------
    def _build_view_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("بروزرسانی نقشه (آنلاین)")
        refresh_btn.clicked.connect(lambda: self.refresh_view_map(offline=False))
        btn_row.addWidget(refresh_btn)

        offline_btn = QPushButton("نمایش نقشه آفلاین (از دیتابیس)")
        offline_btn.clicked.connect(lambda: self.refresh_view_map(offline=True))
        btn_row.addWidget(offline_btn)

        layout.addLayout(btn_row)

        self.view_webview = QWebEngineView()
        self.view_page = DebugWebPage(self.view_webview)
        self.view_webview.setPage(self.view_page)
        layout.addWidget(self.view_webview)

        self.tabs.addTab(tab, "۲. نمایش نقشه")

    def refresh_view_map(self, offline=False):
        if offline and not leaflet_vendor_files_available():
            QMessageBox.warning(
                self, "فایل‌های Leaflet یافت نشد",
                "برای نمایش نقشه آفلاین، فایل‌های leaflet.js و leaflet.css باید در پوشه "
                "vendor/leaflet قرار داشته باشند. راهنمای دانلود در vendor/leaflet/README.md "
                "موجود است."
            )
            return
        streets = self.db.get_streets()
        places = self.db.get_places()
        mosques = self._get_mosques_with_zone_names()
        html = build_view_mode_html(
            self.boundary_points, streets, places, mosques=mosques, offline=offline,
            schools=self.db.get_schools(), health_centers=self.db.get_health_centers(),
        )
        path = self._write_temp_html(html, "view_mode.html")
        self.view_webview.setUrl(QUrl.fromLocalFile(path))

    # ---------------- تب ۵: جدول خیابان‌ها و کوچه‌ها ----------------
    def _build_streets_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("منطقه:"))
        self.streets_zone_filter = QComboBox()
        self.streets_zone_filter.addItem("همه مناطق", None)
        for z in self.db.get_zones():
            self.streets_zone_filter.addItem(z["name"], z["id"])
        self.streets_zone_filter.currentIndexChanged.connect(lambda _: self.refresh_streets_table())
        top_row.addWidget(self.streets_zone_filter)

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
        edit_street_btn = QPushButton("ویرایش ردیف انتخاب‌شده")
        edit_street_btn.clicked.connect(self.on_edit_street)
        action_row.addWidget(edit_street_btn)

        delete_street_btn = QPushButton("حذف ردیف انتخاب‌شده")
        delete_street_btn.setProperty("danger", True)
        delete_street_btn.clicked.connect(self.on_delete_street)
        action_row.addWidget(delete_street_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.streets_table = QTableWidget()
        self.streets_table.setColumnCount(4)
        self.streets_table.setHorizontalHeaderLabels(["نام", "نوع معبر", "تعداد نقاط مسیر", "منطقه"])
        self.streets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.streets_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.streets_table)

        self.streets_count_label = QLabel("تعداد: 0")
        layout.addWidget(self.streets_count_label)

        self.tabs.addTab(tab, "۵. خیابان‌ها و کوچه‌ها")
        self.refresh_streets_table()

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
            self.db.update_street(street["id"], name=new_name.strip())
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
            self.db.delete_street(street["id"])
            self.refresh_streets_table()

    def refresh_streets_table(self):
        zone_id = self.streets_zone_filter.currentData() if hasattr(self, "streets_zone_filter") else None
        self._all_streets = self.db.get_streets(zone_id=zone_id)
        self._zone_names_by_id = {z["id"]: z["name"] for z in self.db.get_zones()}
        self._populate_streets_table(self._all_streets)

    def _populate_streets_table(self, streets):
        self.streets_table.setRowCount(len(streets))
        for row, s in enumerate(streets):
            zone_name = self._zone_names_by_id.get(s.get("zone_id"), "—") if hasattr(self, "_zone_names_by_id") else "—"
            name_item = QTableWidgetItem(s["name"])
            name_item.setData(Qt.UserRole, s["id"])
            self.streets_table.setItem(row, 0, name_item)
            self.streets_table.setItem(row, 1, QTableWidgetItem(s["highway_type"] or ""))
            self.streets_table.setItem(row, 2, QTableWidgetItem(str(len(s["geometry"]))))
            self.streets_table.setItem(row, 3, QTableWidgetItem(zone_name))
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

    # ---------------- تب ۶: جدول اماکن ----------------
    def _build_places_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("منطقه:"))
        self.places_zone_filter = QComboBox()
        self.places_zone_filter.addItem("همه مناطق", None)
        for z in self.db.get_zones():
            self.places_zone_filter.addItem(z["name"], z["id"])
        self.places_zone_filter.currentIndexChanged.connect(lambda _: self.refresh_places_table())
        top_row.addWidget(self.places_zone_filter)

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
        edit_place_btn = QPushButton("ویرایش ردیف انتخاب‌شده")
        edit_place_btn.clicked.connect(self.on_edit_place)
        action_row.addWidget(edit_place_btn)

        delete_place_btn = QPushButton("حذف ردیف انتخاب‌شده")
        delete_place_btn.setProperty("danger", True)
        delete_place_btn.clicked.connect(self.on_delete_place)
        action_row.addWidget(delete_place_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.places_table = QTableWidget()
        self.places_table.setColumnCount(6)
        self.places_table.setHorizontalHeaderLabels(["نام", "دسته", "زیر‌دسته", "عرض جغرافیایی", "طول جغرافیایی", "منطقه"])
        self.places_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.places_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.places_table)

        self.places_count_label = QLabel("تعداد: 0")
        layout.addWidget(self.places_count_label)

        self.tabs.addTab(tab, "۶. اماکن (مدارس، ادارات و ...)")
        self.refresh_places_table()

    def on_edit_place(self):
        row = self.places_table.currentRow()
        item = self.places_table.item(row, 0) if row >= 0 else None
        place_id = item.data(Qt.UserRole) if item else None
        place = next((pl for pl in self._all_places if pl["id"] == place_id), None)
        if place is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        if place.get("record_type") == "mosque":
            QMessageBox.information(
                self, "مسجد مرجع",
                "این ردیف از فهرست مرجع مساجد و ارتباط خودکار مسجد–بلوک نمایش داده می‌شود. "
                "برای اصلاح اطلاعات آن از بخش «مساجد» استفاده کنید."
            )
            return
        new_name, ok = QInputDialog.getText(self, "ویرایش نام مکان", "نام جدید:", text=place["name"])
        if ok and new_name.strip():
            self.db.update_place(place["id"], name=new_name.strip())
            self.refresh_places_table()

    def on_delete_place(self):
        row = self.places_table.currentRow()
        item = self.places_table.item(row, 0) if row >= 0 else None
        place_id = item.data(Qt.UserRole) if item else None
        place = next((pl for pl in self._all_places if pl["id"] == place_id), None)
        if place is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        if place.get("record_type") == "mosque":
            QMessageBox.information(
                self, "مسجد مرجع",
                "مسجد مرجع از جدول اماکن حذف نمی‌شود. عضویت آن در بلوک بر اساس مختصات و مرز بلوک "
                "محاسبه می‌شود؛ در صورت نیاز مرز بلوک یا مختصات مسجد را بازبینی کنید."
            )
            return
        reply = QMessageBox.question(
            self, "تأیید حذف", f"آیا از حذف «{place['name']}» مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_place(place["id"])
            self.refresh_places_table()

    def refresh_places_table(self):
        """نمایش یکپارچه اماکن OSM/دستی و مساجد مرجع داخل بلوک انتخابی."""
        zone_id = self.places_zone_filter.currentData() if hasattr(self, "places_zone_filter") else None
        self._zone_names_by_id_places = {z["id"]: z["name"] for z in self.db.get_zones()}
        self._all_places = self.db.get_places_with_mosques(zone_id=zone_id)
        self._populate_places_table(self._all_places)

    def _populate_places_table(self, places):
        self.places_table.setRowCount(len(places))
        mosque_count = 0
        for row, place in enumerate(places):
            zone_name = place.get("zone_name") or (
                self._zone_names_by_id_places.get(place.get("zone_id"), "—")
                if hasattr(self, "_zone_names_by_id_places") else "—"
            )
            name_item = QTableWidgetItem(place["name"])
            name_item.setData(Qt.UserRole, place["id"])
            name_item.setData(Qt.UserRole + 1, place.get("record_type", "place"))
            if place.get("record_type") == "mosque":
                mosque_count += 1
                name_item.setToolTip("مسجد مرجع شناسایی‌شده داخل این بلوک")
                name_item.setBackground(QColor("#e8f5e9"))
            self.places_table.setItem(row, 0, name_item)
            self.places_table.setItem(row, 1, QTableWidgetItem(place["category"] or ""))
            self.places_table.setItem(row, 2, QTableWidgetItem(place["subtype"] or ""))
            self.places_table.setItem(row, 3, QTableWidgetItem(str(place["lat"])))
            self.places_table.setItem(row, 4, QTableWidgetItem(str(place["lon"])))
            self.places_table.setItem(row, 5, QTableWidgetItem(zone_name))
        other_count = len(places) - mosque_count
        self.places_count_label.setText(
            f"تعداد کل: {len(places)}  |  سایر اماکن: {other_count}  |  مساجد: {mosque_count}"
        )

    def filter_places_table(self, text):
        if not hasattr(self, "_all_places"):
            return
        text = text.strip()
        if not text:
            self._populate_places_table(self._all_places)
            return
        filtered = [
            place for place in self._all_places
            if text in place.get("name", "")
            or text in place.get("category", "")
            or text in place.get("subtype", "")
        ]
        self._populate_places_table(filtered)

    # ---------------- تب ۷: دانلود نقشه آفلاین (تایل‌ها) ----------------
    # ---------------- تب مساجد ثابت جوانرود ----------------
    def _build_mosques_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left = QVBoxLayout()
        title = QLabel("۲۴ مسجد منحصربه‌فرد جوانرود — نشانگرهای سبز روی نقشه ثابت هستند")
        title.setWordWrap(True)
        left.addWidget(title)
        self.mosques_webview = QWebEngineView()
        self.mosques_page = DebugWebPage(self.mosques_webview)
        self.mosques_webview.setPage(self.mosques_page)
        left.addWidget(self.mosques_webview)
        layout.addLayout(left, stretch=3)

        right = QVBoxLayout()
        self.mosque_search = QLineEdit()
        self.mosque_search.setPlaceholderText("جستجوی نام مسجد یا نام قبلی...")
        self.mosque_search.textChanged.connect(self.filter_mosques_table)
        right.addWidget(self.mosque_search)

        refresh_btn = QPushButton("بروزرسانی ارتباط مساجد با همه بلوک‌ها")
        refresh_btn.clicked.connect(self.on_sync_all_mosques)
        right.addWidget(refresh_btn)

        self.mosques_table = QTableWidget()
        self.mosques_table.setColumnCount(4)
        self.mosques_table.setHorizontalHeaderLabels(["نام مسجد", "عرض", "طول", "بلوک مرتبط"])
        self.mosques_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.mosques_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.mosques_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.mosques_table.itemSelectionChanged.connect(self._on_mosque_selected)
        right.addWidget(self.mosques_table)

        self.mosques_count_label = QLabel("")
        right.addWidget(self.mosques_count_label)
        layout.addLayout(right, stretch=2)

        self.tabs.addTab(tab, "مساجد")
        self.refresh_mosques_table()

    def refresh_mosques_table(self):
        self._all_mosques = self._get_mosques_with_zone_names()
        self._populate_mosques_table(self._all_mosques)
        html = build_view_mode_html(
            self.boundary_points, streets=[], places=[], mosques=self._all_mosques, offline=False
        )
        path = self._write_temp_html(html, "mosques_view.html")
        self.mosques_webview.setUrl(QUrl.fromLocalFile(path))

    def _populate_mosques_table(self, mosques):
        self._visible_mosques = list(mosques)
        self.mosques_table.setRowCount(len(mosques))
        for row, mosque in enumerate(mosques):
            name_item = QTableWidgetItem(mosque["name"])
            name_item.setData(Qt.UserRole, mosque["id"])
            self.mosques_table.setItem(row, 0, name_item)
            self.mosques_table.setItem(row, 1, QTableWidgetItem(f"{mosque['lat']:.7f}"))
            self.mosques_table.setItem(row, 2, QTableWidgetItem(f"{mosque['lon']:.7f}"))
            zone_text = "، ".join(mosque.get("zones", [])) or "—"
            self.mosques_table.setItem(row, 3, QTableWidgetItem(zone_text))
        self.mosques_count_label.setText(f"تعداد نمایش‌داده‌شده: {len(mosques)} از ۲۴")

    def filter_mosques_table(self, text):
        query = (text or "").strip().casefold()
        if not query:
            self._populate_mosques_table(self._all_mosques)
            return
        filtered = []
        for mosque in self._all_mosques:
            haystack = " ".join([mosque["name"], *mosque.get("aliases", []), *mosque.get("zones", [])]).casefold()
            if query in haystack:
                filtered.append(mosque)
        self._populate_mosques_table(filtered)

    def _on_mosque_selected(self):
        row = self.mosques_table.currentRow()
        if row < 0:
            return
        item = self.mosques_table.item(row, 0)
        if not item:
            return
        import json as _json
        mosque_id = item.data(Qt.UserRole)
        self.mosques_webview.page().runJavaScript(f"focusMosque({_json.dumps(mosque_id)});")

    def on_sync_all_mosques(self):
        self.db.sync_all_zone_mosques()
        self.refresh_zones_list()
        self.refresh_mosques_table()
        self.refresh_all_zones_view()
        QMessageBox.information(self, "انجام شد", "ارتباط ۲۴ مسجد با تمام بلوک‌ها دوباره محاسبه و ذخیره شد.")

    def _build_offline_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        group = QGroupBox("نقشه آفلاین داخلی — بدون وابستگی به سرور تایل")
        group_layout = QVBoxLayout(group)

        info = QLabel(
            "در نسخه جدید، حالت آفلاین از مرز شهر و بلوک‌ها، معابر، اماکن، مساجد، مدارس و مراکز "
            "ثبت‌شده در دیتابیس استفاده می‌کند. هیچ تایل اینترنتی دریافت نمی‌شود؛ بنابراین خطای "
            "403 و محدودیت سرور OpenStreetMap در حالت آفلاین تکرار نخواهد شد."
        )
        info.setWordWrap(True)
        group_layout.addWidget(info)

        self.recommended_estimate_label = QLabel(
            "برای دریافت معابر و اماکن جدید، فقط دکمه OSM در تب بلوک‌ها نیازمند اینترنت است. "
            "پس از ذخیره، نمایش نقشه کاملاً آفلاین خواهد بود."
        )
        self.recommended_estimate_label.setWordWrap(True)
        group_layout.addWidget(self.recommended_estimate_label)

        prepare_btn = QPushButton("پاک‌سازی تایل‌های خراب و فعال‌سازی نقشه آفلاین داخلی")
        prepare_btn.setProperty("success", True)
        prepare_btn.clicked.connect(self.on_prepare_vector_offline_map)
        group_layout.addWidget(prepare_btn)

        layout.addWidget(group)

        self.download_progress = QProgressBar()
        self.download_progress.setVisible(False)
        layout.addWidget(self.download_progress)

        self.download_status = QLabel("")
        self.download_status.setWordWrap(True)
        if self._legacy_tile_cleanup_count:
            self.download_status.setText(
                f"در اولین اجرای این نسخه، {self._legacy_tile_cleanup_count} تایل قدیمی/مسدود خودکار پاک شد."
            )
        layout.addWidget(self.download_status)

        self.tile_count_label = QLabel("")
        layout.addWidget(self.tile_count_label)
        self._update_tile_count_label()

        self.offline_zone_combo = QComboBox()
        self.offline_zone_combo.addItem("کل محدوده شهر", None)
        for z in self.db.get_zones():
            self.offline_zone_combo.addItem(z["name"], z["id"])
        self.offline_zone_combo.setVisible(False)
        self.zoom_min_spin = QSpinBox(); self.zoom_min_spin.setRange(1, 19); self.zoom_min_spin.setValue(12); self.zoom_min_spin.setVisible(False)
        self.zoom_max_spin = QSpinBox(); self.zoom_max_spin.setRange(1, 19); self.zoom_max_spin.setValue(18); self.zoom_max_spin.setVisible(False)
        self.estimate_label = QLabel("حالت آفلاین داخلی فعال است.")
        layout.addWidget(self.estimate_label)

        layout.addStretch()
        self.tabs.addTab(tab, "۷. نقشه آفلاین")

    def on_estimate_full_city_download(self, silent=False):
        """برآورد حجم/تعداد تایل برای دانلود کامل و حرفه‌ای (کل شهر، زوم ۱۰-۱۹)."""
        bbox = self._get_city_wide_bbox_for_zones_tab()
        if not bbox:
            if not silent:
                QMessageBox.warning(
                    self, "خطا",
                    "ابتدا باید محدوده کلی شهر را در تب «۱. رسم محدوده» رسم و ذخیره کنید."
                )
            return None
        min_lat, min_lon, max_lat, max_lon = bbox
        count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE)
        approx_mb = count * 15 / 1024
        # سرعت واقعی دانلود به اینترنت کاربر بستگی دارد؛ این فقط یک تخمین محافظه‌کارانه
        # بر اساس آهنگ متوسط مشاهده‌شده در این ماژول (حدود ۸ تا ۱۰ تایل بر ثانیه) است.
        approx_minutes = max(1, round(count / 8 / 60))
        text = (
            f"تعداد تایل: {count:,} — حجم تقریبی: {approx_mb:.0f} مگابایت — "
            f"زمان تقریبی (بسته به سرعت اینترنت): حدود {approx_minutes} دقیقه"
        )
        self.recommended_estimate_label.setText(text)
        return {"count": count, "approx_mb": approx_mb, "bbox": bbox}

    def on_download_full_city_map(self):
        """دانلود کامل و حرفه‌ای نقشه شهر با یک کلیک: کل محدوده شهر، زوم ۱۰ تا ۱۹
        (نمای کلی تا جزئی‌ترین سطح خیابان)، بدون نیاز کاربر به هیچ تنظیم دستی."""
        estimate = self.on_estimate_full_city_download(silent=False)
        if not estimate:
            return

        confirm = QMessageBox.question(
            self, "تأیید دانلود کامل نقشه شهر",
            f"{self.recommended_estimate_label.text()}\n\n"
            "این دانلود ممکن است چند دقیقه طول بکشد. توصیه می‌شود از یک اتصال اینترنت "
            "پایدار استفاده کنید و در حین دانلود از بستن برنامه خودداری کنید.\n\n"
            "آیا ادامه می‌دهید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if confirm != QMessageBox.Yes:
            return

        min_lat, min_lon, max_lat, max_lon = estimate["bbox"]
        self.full_city_download_thread = DownloadTilesThread(
            self.db.db_path, min_lat, min_lon, max_lat, max_lon, RECOMMENDED_FULL_DOWNLOAD_ZOOM_RANGE
        )
        self._full_city_download_total = estimate["count"]
        self.full_city_download_thread.progress.connect(self.on_full_city_download_progress)
        self.full_city_download_thread.finished_ok.connect(self.on_full_city_download_finished)
        self.full_city_download_thread.failed.connect(self.on_full_city_download_failed)
        self.full_city_download_thread.start()
        self.download_status.setText("در حال دانلود کامل نقشه شهر... لطفاً صبر کنید.")
        self.download_progress.setValue(0)

    def on_full_city_download_progress(self, done, total, downloaded, skipped, failed):
        pct = int((done / total) * 100) if total else 0
        self.download_progress.setValue(pct)
        self.download_status.setText(
            f"پیشرفت: {done:,} از {total:,} تایل ({pct}٪) — "
            f"دانلود‌شده: {downloaded:,}، از قبل موجود: {skipped:,}، ناموفق: {failed:,}"
        )

    def on_full_city_download_finished(self, result):
        self.download_progress.setValue(100)
        self._update_tile_count_label()
        if result.get("failed", 0) > 0:
            self.download_status.setText(
                f"دانلود پایان یافت. دانلود‌شده: {result['downloaded']:,}، از قبل موجود: {result['skipped']:,}، "
                f"ناموفق: {result['failed']:,} (این تعداد را می‌توانید دوباره اجرا کنید تا کامل شود)."
            )
        else:
            self.download_status.setText(
                f"دانلود کامل با موفقیت به پایان رسید. دانلود‌شده: {result['downloaded']:,}، "
                f"از قبل موجود: {result['skipped']:,}."
            )
        QMessageBox.information(
            self, "پایان دانلود",
            "دانلود کامل نقشه شهر به پایان رسید. اکنون می‌توانید بدون هیچ اتصال اینترنتی، "
            "نقشه را با تمام جزئیات (تا سطح خیابان و کوچه) در حالت آفلاین مشاهده کنید."
        )

    def on_full_city_download_failed(self, error_msg):
        self.download_status.setText("دانلود با خطا متوقف شد.")
        QMessageBox.critical(
            self, "خطا در دانلود",
            f"دانلود کامل نقشه شهر با خطا مواجه شد:\n{error_msg}\n\n"
            "می‌توانید دوباره تلاش کنید؛ تایل‌های قبلاً دانلود‌شده مجدد بارگیری نمی‌شوند."
        )

    def _get_bbox(self):
        """بر اساس گزینه انتخاب‌شده (کل شهر یا یک منطقه خاص) کادر جغرافیایی را برمی‌گرداند."""
        zone_id = self.offline_zone_combo.currentData() if hasattr(self, "offline_zone_combo") else None
        if zone_id is not None:
            zone = self.db.get_zone(zone_id)
            points = zone["boundary_points"] if zone else []
        else:
            points = self.boundary_points

        if not points or len(points) < 3:
            return None
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        return min(lats), min(lons), max(lats), max(lons)

    def on_estimate_tiles(self):
        bbox = self._get_bbox()
        if not bbox:
            QMessageBox.warning(self, "خطا", "ابتدا محدوده شهر را رسم و ذخیره کنید.")
            return
        min_lat, min_lon, max_lat, max_lon = bbox
        zoom_levels = range(self.zoom_min_spin.value(), self.zoom_max_spin.value() + 1)
        count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, zoom_levels)
        approx_mb = count * 15 / 1024  # برآورد تقریبی ۱۵ کیلوبایت هر تایل
        self.estimate_label.setText(f"{count} تایل (حدود {approx_mb:.1f} مگابایت)")

    def on_download_tiles(self):
        bbox = self._get_bbox()
        if not bbox:
            QMessageBox.warning(self, "خطا", "ابتدا محدوده شهر را رسم و ذخیره کنید.")
            return
        min_lat, min_lon, max_lat, max_lon = bbox
        zoom_levels = range(self.zoom_min_spin.value(), self.zoom_max_spin.value() + 1)

        self.download_thread = DownloadTilesThread(self.db.db_path, min_lat, min_lon, max_lat, max_lon, zoom_levels)
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.finished_ok.connect(self.on_download_finished)
        self.download_thread.failed.connect(self.on_download_failed)
        self.download_thread.start()
        self.download_status.setText("دانلود شروع شد ...")

    def on_download_progress(self, done, total, downloaded, skipped, failed):
        pct = int((done / total) * 100) if total else 0
        self.download_progress.setValue(pct)
        self.download_status.setText(
            f"پیشرفت: {done}/{total} — دانلود‌شده: {downloaded}، موجود قبلی: {skipped}، ناموفق: {failed}"
        )

    def on_download_finished(self, result):
        self.download_status.setText(
            f"پایان دانلود. دانلود‌شده: {result['downloaded']}، موجود قبلی: {result['skipped']}، ناموفق: {result['failed']}"
        )
        self._update_tile_count_label()
        QMessageBox.information(self, "پایان دانلود", "دانلود نقشه آفلاین به پایان رسید.")

    def on_download_failed(self, error_msg):
        QMessageBox.critical(self, "خطا", f"دانلود ناموفق بود:\n{error_msg}")

    def _update_tile_count_label(self):
        count = self.db.count_tiles()
        self.tile_count_label.setText(
            f"تایل قدیمی باقی‌مانده: {count} — نقشه آفلاین داخلی برای نمایش به تایل نیاز ندارد."
        )

    # ---------------- دانلود کامل نقشه شهر (دسترسی سریع از تب مناطق/بلوک‌ها) ----------------
    def _get_city_wide_bbox_for_zones_tab(self):
        """محدوده کلی شهر (همان که در تب ۱ رسم شده) را برمی‌گرداند."""
        if not self.boundary_points or len(self.boundary_points) < 3:
            return None
        lats = [p[0] for p in self.boundary_points]
        lons = [p[1] for p in self.boundary_points]
        return min(lats), min(lons), max(lats), max(lons)

    def on_estimate_city_wide_tiles(self):
        bbox = self._get_city_wide_bbox_for_zones_tab()
        if not bbox:
            QMessageBox.warning(
                self, "خطا",
                "ابتدا باید محدوده کلی شهر را در تب «۱. رسم محدوده» رسم و ذخیره کنید."
            )
            return
        min_lat, min_lon, max_lat, max_lon = bbox
        zoom_levels = range(self.zones_zoom_min_spin.value(), self.zones_zoom_max_spin.value() + 1)
        count = estimate_tile_count(min_lat, min_lon, max_lat, max_lon, zoom_levels)
        approx_mb = count * 15 / 1024
        self.zones_estimate_label.setText(f"{count} تایل (حدود {approx_mb:.1f} مگابایت)")

    def on_download_city_wide_tiles(self):
        bbox = self._get_city_wide_bbox_for_zones_tab()
        if not bbox:
            QMessageBox.warning(
                self, "خطا",
                "ابتدا باید محدوده کلی شهر را در تب «۱. رسم محدوده» رسم و ذخیره کنید."
            )
            return
        min_lat, min_lon, max_lat, max_lon = bbox
        zoom_levels = range(self.zones_zoom_min_spin.value(), self.zones_zoom_max_spin.value() + 1)

        self.city_wide_download_thread = DownloadTilesThread(
            self.db.db_path, min_lat, min_lon, max_lat, max_lon, zoom_levels
        )
        self.city_wide_download_thread.progress.connect(self.on_city_wide_download_progress)
        self.city_wide_download_thread.finished_ok.connect(self.on_city_wide_download_finished)
        self.city_wide_download_thread.failed.connect(self.on_city_wide_download_failed)
        self.city_wide_download_thread.start()
        self.zones_download_status.setText("دانلود نقشه کامل شهر شروع شد ...")

    def on_city_wide_download_progress(self, done, total, downloaded, skipped, failed):
        pct = int((done / total) * 100) if total else 0
        self.zones_download_progress.setValue(pct)
        self.zones_download_status.setText(
            f"پیشرفت: {done}/{total} — دانلود‌شده: {downloaded}، موجود قبلی: {skipped}، ناموفق: {failed}"
        )

    def on_city_wide_download_finished(self, result):
        self.zones_download_status.setText(
            f"پایان دانلود. دانلود‌شده: {result['downloaded']}، موجود قبلی: {result['skipped']}، ناموفق: {result['failed']}"
        )
        # هم‌زمان لیبل تعداد تایل در تب «۷. دانلود نقشه آفلاین» را هم به‌روزرسانی می‌کنیم
        if hasattr(self, "tile_count_label"):
            self._update_tile_count_label()
        QMessageBox.information(
            self, "پایان دانلود",
            "دانلود کامل نقشه شهر به پایان رسید. اکنون می‌توانید بدون اینترنت هم نقشه را با زوم "
            "بالا ببینید (از تب «۲. نمایش نقشه» گزینه «نمایش نقشه آفلاین» را بزنید)."
        )

    def on_city_wide_download_failed(self, error_msg):
        QMessageBox.critical(self, "خطا", f"دانلود نقشه کامل شهر ناموفق بود:\n{error_msg}")

    # توجه: closeEvent دیگر db را نمی‌بندد، چون در معماری جدید دیتابیس
    # بین چند پنجره (بلوک‌بندی، شورای محلات، تنظیمات) مشترک است و توسط
    # فایل app.py (نقطه ورود اصلی برنامه) مدیریت و بسته می‌شود.
