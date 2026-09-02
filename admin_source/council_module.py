# -*- coding: utf-8 -*-
"""
ماژول اعضای شورای محلات:
- انتخاب بلوک/منطقه از لیست مناطق ثبت‌شده
- نمایش نقشه آن منطقه با قابلیت زوم
- نمایش اماکن دولتی/مساجد آن منطقه و انتخاب یکی به‌عنوان محل برگزاری جلسات (با ثبت آدرس دقیق)
- دکمه نمایش جدول کامل خیابان‌ها و کوچه‌های بلوک
- فرم ثبت/ویرایش/حذف اعضای شورای محلات
"""

import os
from runtime_paths import get_temp_dir
from urllib.parse import unquote
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QGroupBox, QFormLayout, QLineEdit, QRadioButton, QButtonGroup,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QDialogButtonBox, QTextEdit, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from header_widget import build_official_header
from map_html import build_zone_meeting_map_html
from database import Database
from place_types import get_place_role_label
from ui_scroll import scroll_page


class DebugWebPage(QWebEnginePage):
    """چاپ خطاهای جاوااسکریپت در ترمینال برای عیب‌یابی."""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS Console - Council Map] {message} (line {lineNumber})")


class StreetsTableDialog(QDialog):
    """دیالوگ نمایش جدول خیابان‌ها و کوچه‌های یک بلوک/منطقه خاص."""
    def __init__(self, db, zone_id, zone_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.zone_id = zone_id
        self.setWindowTitle(f"خیابان‌ها و کوچه‌های منطقه: {zone_name}")
        self.resize(800, 600)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("جستجو در نام خیابان/کوچه ...")
        self.search_input.textChanged.connect(self._filter_table)
        search_row.addWidget(QLabel("جستجو:"))
        search_row.addWidget(self.search_input)
        layout.addLayout(search_row)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["نام", "نوع معبر"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.count_label = QLabel("")
        layout.addWidget(self.count_label)

        self._all_streets = self.db.get_streets(zone_id=self.zone_id)
        self._populate_table(self._all_streets)

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _populate_table(self, streets):
        self.table.setRowCount(len(streets))
        for row, s in enumerate(streets):
            self.table.setItem(row, 0, QTableWidgetItem(s["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(s["highway_type"] or ""))
        self.count_label.setText(f"تعداد: {len(streets)}")

    def _filter_table(self, text):
        text = text.strip()
        if not text:
            self._populate_table(self._all_streets)
            return
        filtered = [s for s in self._all_streets if text in s["name"]]
        self._populate_table(filtered)


class MemberFormDialog(QDialog):
    """دیالوگ ثبت یا ویرایش اطلاعات یک عضو شورای محلات."""
    GROUPS = Database.COUNCIL_GROUPS

    def __init__(self, parent=None, member=None):
        super().__init__(parent)
        self.member = member  # اگر None باشد یعنی حالت "افزودن عضو جدید"
        self.setWindowTitle("ویرایش عضو" if member else "افزودن عضو جدید")
        self.resize(450, 500)
        self._build_ui()
        if member:
            self._fill_from_member(member)

    def _build_ui(self):
        shell = QVBoxLayout(self)
        shell.setContentsMargins(10, 10, 10, 10)
        shell.setSpacing(8)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)

        self.first_name_input = QLineEdit()
        form.addRow("نام:", self.first_name_input)

        self.last_name_input = QLineEdit()
        form.addRow("نام خانوادگی:", self.last_name_input)

        self.national_code_input = QLineEdit()
        self.national_code_input.setPlaceholderText("کد ملی ۱۰ رقمی")
        form.addRow("کد ملی:", self.national_code_input)

        self.education_input = QLineEdit()
        self.education_input.setPlaceholderText("مثلاً: دیپلم، کارشناسی، کارشناسی ارشد")
        form.addRow("تحصیلات:", self.education_input)

        self.mobile_input = QLineEdit()
        self.mobile_input.setPlaceholderText("09xxxxxxxxx")
        form.addRow("شماره موبایل:", self.mobile_input)

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("مثلاً: رئیس شورا، عضو، منشی")
        form.addRow("سمت:", self.position_input)

        layout.addLayout(form)

        group_box = QGroupBox("دسته‌بندی عضو (فقط یک مورد قابل انتخاب)")
        group_layout = QVBoxLayout(group_box)
        self.group_radio_buttons = QButtonGroup(self)
        for i, group_name in enumerate(self.GROUPS):
            rb = QRadioButton(group_name)
            self.group_radio_buttons.addButton(rb, i)
            group_layout.addWidget(rb)
        if self.group_radio_buttons.buttons():
            self.group_radio_buttons.buttons()[0].setChecked(True)
        layout.addWidget(group_box)
        layout.addStretch(1)

        scroll = scroll_page(body, min_height=620)
        shell.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        shell.addWidget(buttons, 0)

    def _fill_from_member(self, member):
        self.first_name_input.setText(member["first_name"])
        self.last_name_input.setText(member["last_name"])
        self.national_code_input.setText(member["national_code"] or "")
        self.education_input.setText(member["education"] or "")
        self.mobile_input.setText(member["mobile"] or "")
        self.position_input.setText(member["position"] or "")
        for btn in self.group_radio_buttons.buttons():
            if btn.text() == member["member_group"]:
                btn.setChecked(True)
                break

    def _on_save(self):
        if not self.first_name_input.text().strip() or not self.last_name_input.text().strip():
            QMessageBox.warning(self, "خطا", "نام و نام خانوادگی الزامی است.")
            return
        self.accept()

    def get_data(self):
        selected_btn = self.group_radio_buttons.checkedButton()
        member_group = selected_btn.text() if selected_btn else ""
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "national_code": self.national_code_input.text().strip(),
            "education": self.education_input.text().strip(),
            "mobile": self.mobile_input.text().strip(),
            "member_group": member_group,
            "position": self.position_input.text().strip(),
        }


class MosqueImamDialog(QDialog):
    """دیالوگ ثبت یا ویرایش امام جماعت یک مسجد؛ نتیجه به‌طور خودکار به‌عنوان
    معتمد همان بلوک با سمت «امام جماعت [نام مسجد]» در شورای محلات ثبت می‌شود."""

    def __init__(self, parent=None, mosque_name="", imam=None):
        super().__init__(parent)
        self.imam = imam  # اگر None باشد یعنی ثبت اولیه؛ در غیر این صورت ویرایش
        self.setWindowTitle("ثبت امام جماعت مسجد" if not imam else "ویرایش امام جماعت مسجد")
        self.resize(400, 260)
        self._build_ui(mosque_name)
        if imam:
            self._fill_from_imam(imam)

    def _build_ui(self, mosque_name):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info = QLabel(
            f"«{mosque_name}» به‌عنوان محل جلسات این بلوک انتخاب شد.\n"
            "لطفاً مشخصات امام جماعت این مسجد را ثبت کنید؛ این شخص به‌طور خودکار "
            "به‌عنوان معتمد این بلوک در شورای محلات ثبت خواهد شد."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        self.first_name_input = QLineEdit()
        form.addRow("نام:", self.first_name_input)

        self.last_name_input = QLineEdit()
        form.addRow("نام خانوادگی:", self.last_name_input)

        self.mobile_input = QLineEdit()
        self.mobile_input.setPlaceholderText("09xxxxxxxxx")
        form.addRow("شماره موبایل:", self.mobile_input)

        position_label = QLabel(f"امام جماعت {mosque_name}")
        position_label.setStyleSheet("color:#555;")
        form.addRow("سمت:", position_label)

        layout.addLayout(form)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill_from_imam(self, imam):
        self.first_name_input.setText(imam.get("first_name") or "")
        self.last_name_input.setText(imam.get("last_name") or "")
        self.mobile_input.setText(imam.get("mobile") or "")

    def _on_save(self):
        if not self.first_name_input.text().strip() or not self.last_name_input.text().strip():
            QMessageBox.warning(self, "خطا", "نام و نام خانوادگی امام جماعت الزامی است.")
            return
        self.accept()

    def get_data(self):
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "mobile": self.mobile_input.text().strip(),
        }


class FacilityManagerDialog(QDialog):
    """دیالوگ عمومی ثبت یا ویرایش مسؤول یک مدرسه/مرکز بهداشتی؛ نتیجه به‌طور
    خودکار به‌عنوان معتمد همان بلوک با سمت مشخص در شورای محلات ثبت می‌شود."""

    def __init__(self, parent=None, facility_name="", role_label="مسؤول", manager=None):
        super().__init__(parent)
        self.manager = manager  # اگر None باشد یعنی ثبت اولیه؛ در غیر این صورت ویرایش
        self.role_label = role_label
        self.setWindowTitle(f"ثبت {role_label}" if not manager else f"ویرایش {role_label}")
        self.resize(400, 260)
        self._build_ui(facility_name)
        if manager:
            self._fill_from_manager(manager)

    def _build_ui(self, facility_name):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info = QLabel(
            f"«{facility_name}» به‌عنوان محل جلسات این بلوک انتخاب شد.\n"
            f"لطفاً مشخصات {self.role_label} این مکان را ثبت کنید؛ این شخص به‌طور خودکار "
            "به‌عنوان معتمد این بلوک در شورای محلات ثبت خواهد شد."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        self.first_name_input = QLineEdit()
        form.addRow("نام:", self.first_name_input)

        self.last_name_input = QLineEdit()
        form.addRow("نام خانوادگی:", self.last_name_input)

        self.mobile_input = QLineEdit()
        self.mobile_input.setPlaceholderText("09xxxxxxxxx")
        form.addRow("شماره موبایل:", self.mobile_input)

        position_label = QLabel(f"{self.role_label} {facility_name}")
        position_label.setStyleSheet("color:#555;")
        form.addRow("سمت:", position_label)

        layout.addLayout(form)
        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _fill_from_manager(self, manager):
        self.first_name_input.setText(manager.get("first_name") or "")
        self.last_name_input.setText(manager.get("last_name") or "")
        self.mobile_input.setText(manager.get("mobile") or "")

    def _on_save(self):
        if not self.first_name_input.text().strip() or not self.last_name_input.text().strip():
            QMessageBox.warning(self, "خطا", f"نام و نام خانوادگی {self.role_label} الزامی است.")
            return
        self.accept()

    def get_data(self):
        return {
            "first_name": self.first_name_input.text().strip(),
            "last_name": self.last_name_input.text().strip(),
            "mobile": self.mobile_input.text().strip(),
        }


class CouncilModuleWindow(QWidget):
    """پنجره اصلی ماژول اعضای شورای محلات."""
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_zone_id = None
        self.setWindowTitle("ثبت اطلاعات اعضای شورای بلوک")
        self.resize(1300, 900)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = build_official_header(app_subtitle="ثبت اطلاعات اعضای شورای بلوک", db=self.db)
        outer.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(24, 16, 24, 16)
        body.setSpacing(14)

        # نوار بالا: بازگشت + انتخاب منطقه
        top_row = QHBoxLayout()
        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_requested.emit)
        top_row.addWidget(back_btn)

        top_row.addSpacing(20)
        top_row.addWidget(QLabel("بلوک موردنظر برای ثبت اعضای شورا:"))
        self.zone_combo = QComboBox()
        self.zone_combo.setMinimumWidth(260)
        self.zone_combo.currentIndexChanged.connect(self._on_zone_changed)
        top_row.addWidget(self.zone_combo)
        top_row.addStretch()
        body.addLayout(top_row)

        self.selected_zone_notice = QLabel("ابتدا بلوک را انتخاب کنید؛ اعضای ثبت‌شده فقط به همان بلوک متصل می‌شوند.")
        self.selected_zone_notice.setObjectName("CouncilZoneNotice")
        self.selected_zone_notice.setWordWrap(True)
        body.addWidget(self.selected_zone_notice)

        # نقشه منطقه
        map_group = QGroupBox("نقشه بلوک انتخاب‌شده")
        map_layout = QVBoxLayout(map_group)
        self.map_webview = QWebEngineView()
        self.map_webview.setMinimumHeight(320)
        self.map_page = DebugWebPage(self.map_webview)
        self.map_webview.setPage(self.map_page)
        self.map_webview.titleChanged.connect(self._on_map_title_changed)
        map_layout.addWidget(self.map_webview)
        body.addWidget(map_group)

        # انتخاب محل جلسات
        meeting_group = QGroupBox("محل برگزاری جلسات شورا (روی نقشه، مکان مورد نظر را کلیک و انتخاب کنید)")
        meeting_layout = QFormLayout(meeting_group)
        self.meeting_place_label = QLabel("هنوز مکانی انتخاب نشده است.")
        meeting_layout.addRow("مکان انتخاب‌شده:", self.meeting_place_label)

        self.meeting_address_input = QLineEdit()
        self.meeting_address_input.setPlaceholderText("آدرس دقیق محل برگزاری جلسات را وارد کنید")
        meeting_layout.addRow("آدرس دقیق:", self.meeting_address_input)

        save_address_btn = QPushButton("ذخیره آدرس دقیق")
        save_address_btn.setProperty("success", True)
        save_address_btn.clicked.connect(self._on_save_meeting_address)
        meeting_layout.addRow(save_address_btn)

        body.addWidget(meeting_group)

        # دکمه نمایش خیابان‌ها
        streets_btn = QPushButton("نمایش آدرس و خیابان‌های این بلوک")
        streets_btn.clicked.connect(self._on_show_streets)
        body.addWidget(streets_btn)

        # فرم و جدول اعضا
        members_group = QGroupBox("ثبت و مدیریت اعضای شورای بلوک انتخاب‌شده")
        self.members_group = members_group
        members_layout = QVBoxLayout(members_group)

        member_btn_row = QHBoxLayout()
        add_member_btn = QPushButton("➕ ثبت عضو جدید برای این بلوک")
        add_member_btn.setProperty("success", True)
        add_member_btn.clicked.connect(self._on_add_member)
        member_btn_row.addWidget(add_member_btn)

        edit_member_btn = QPushButton("ویرایش عضو انتخاب‌شده")
        edit_member_btn.clicked.connect(self._on_edit_member)
        member_btn_row.addWidget(edit_member_btn)

        delete_member_btn = QPushButton("حذف عضو انتخاب‌شده")
        delete_member_btn.setProperty("danger", True)
        delete_member_btn.clicked.connect(self._on_delete_member)
        member_btn_row.addWidget(delete_member_btn)
        member_btn_row.addStretch()
        members_layout.addLayout(member_btn_row)

        self.members_table = QTableWidget()
        self.members_table.setColumnCount(7)
        self.members_table.setHorizontalHeaderLabels([
            "نام", "نام خانوادگی", "کد ملی", "تحصیلات", "موبایل", "دسته", "سمت"
        ])
        self.members_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.members_table.setSelectionBehavior(QTableWidget.SelectRows)
        members_layout.addWidget(self.members_table)

        self.members_count_label = QLabel("تعداد اعضای ثبت‌شده برای این بلوک: 0")
        members_layout.addWidget(self.members_count_label)

        body.addWidget(members_group)

        # کل محتوای صفحه (نقشه، محل جلسات، فرم اعضا، جدول) داخل یک ناحیه قابل اسکرول
        # قرار می‌گیرد تا در صفحه‌نمایش‌های کوچک‌تر، بخش‌های پایینی (مثل فرم و جدول
        # اعضا) از دید کاربر خارج و غیرقابل‌دسترس نشوند.
        scroll_content = QWidget()
        scroll_content.setLayout(body)

        scroll_area = QScrollArea()
        self.scroll_area = scroll_area
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content)
        scroll_area.setFrameShape(QScrollArea.NoFrame)

        outer.addWidget(scroll_area)

        self.refresh_zone_list()

    # ---------------- مدیریت انتخاب منطقه ----------------
    def refresh_zone_list(self):
        self.zone_combo.blockSignals(True)
        self.zone_combo.clear()
        zones = self.db.get_zones()
        if not zones:
            self.zone_combo.addItem("ابتدا در بخش «بلوک‌بندی» یک منطقه بسازید", None)
        else:
            for z in zones:
                self.zone_combo.addItem(z["name"], z["id"])
        self.zone_combo.blockSignals(False)
        if zones:
            self.current_zone_id = zones[0]["id"]
            self._load_zone_data(self.current_zone_id)

    def _on_zone_changed(self, index):
        zone_id = self.zone_combo.currentData()
        if zone_id is None:
            return
        self.current_zone_id = zone_id
        self._load_zone_data(zone_id)

    def _load_zone_data(self, zone_id):
        zone = self.db.get_zone(zone_id)
        if not zone:
            return
        if hasattr(self, "selected_zone_notice"):
            self.selected_zone_notice.setText(
                f"اعضای جدید برای بلوک «{zone['name']}» ثبت می‌شوند. برای بلوک دیگر، انتخاب بالا را تغییر دهید."
            )

        # اماکن OSM، مساجد مرجع، مدارس و مراکز بهداشتی داخل همین بلوک برای انتخاب محل جلسات
        all_places = self.db.get_places(zone_id=zone_id)
        mosques = self.db.get_mosques(zone_id=zone_id)
        schools = self.db.get_schools(zone_id=zone_id)
        health_centers = self.db.get_health_centers(zone_id=zone_id)

        meeting_place = self.db.get_zone_meeting_place(zone_id)
        selected_type = meeting_place.get("source_type") if meeting_place else None
        selected_id = meeting_place.get("source_id") if meeting_place else None

        html = build_zone_meeting_map_html(
            zone, all_places, offline=False, mosques=mosques,
            schools=schools, health_centers=health_centers,
            selected_source_type=selected_type, selected_source_id=selected_id,
            allow_selection=True,
        )
        temp_path = self._write_temp_html(html)
        self.map_webview.setUrl(QUrl.fromLocalFile(temp_path))

        if meeting_place:
            self.meeting_place_label.setText(meeting_place["place_name"] or "—")
            self.meeting_address_input.setText(meeting_place["exact_address"] or "")
        else:
            self.meeting_place_label.setText("هنوز مکانی انتخاب نشده است.")
            self.meeting_address_input.clear()

        self._pending_selected_place = None
        self.refresh_members_table()

    def _write_temp_html(self, html_content):
        temp_dir = get_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        path = os.path.join(temp_dir, "council_map.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return path

    # ---------------- انتخاب محل جلسات از طریق نقشه ----------------
    def _on_map_title_changed(self, title):
        """دریافت انتخاب محل جلسه از نقشه؛ سازگار با پیام قدیمی و نسخه جدید."""
        if title.startswith("SELECT_SOURCE:"):
            parts = title.split(":", 2)
            if len(parts) != 3:
                return
            source_type, source_id = parts[1], unquote(parts[2])
            if source_type == "place":
                try:
                    self._handle_place_selected(int(source_id))
                except ValueError:
                    return
            elif source_type == "mosque":
                self._handle_mosque_selected(source_id)
            elif source_type in ("school", "health_center"):
                self._handle_facility_selected(source_type, source_id)
            return

        if title.startswith("SELECT_PLACE:"):
            try:
                place_id = int(title.split(":", 1)[1])
            except (IndexError, ValueError):
                return
            self._handle_place_selected(place_id)

    def _handle_place_selected(self, place_id):
        if self.current_zone_id is None:
            return
        places = self.db.get_places(zone_id=self.current_zone_id)
        selected = next((p for p in places if p["id"] == place_id), None)
        if not selected:
            return

        self.meeting_place_label.setText(selected["name"])
        # آدرس OSM (در صورت وجود) را به‌عنوان پیش‌فرض در فیلد آدرس دقیق قرار می‌دهیم
        if selected.get("address") and not self.meeting_address_input.text().strip():
            self.meeting_address_input.setText(selected["address"])

        self.db.set_zone_meeting_place(
            self.current_zone_id, selected["id"], selected["name"],
            self.meeting_address_input.text().strip(), selected["lat"], selected["lon"],
            source_type="place", source_id=str(selected["id"]),
        )
        # بازخوانی نقشه تا نشانگر انتخاب‌شده برجسته شود
        self._load_zone_data(self.current_zone_id)

        role_label = selected.get("manager_role") or get_place_role_label(selected.get("subtype"))
        existing_manager = self.db.get_place_manager(selected["id"])
        if existing_manager:
            QMessageBox.information(
                self, "ثبت شد",
                f"«{selected['name']}» به‌عنوان محل جلسات این بلوک ثبت شد.\n"
                f"{existing_manager.get('role_label') or role_label} این مکان پیش‌تر ثبت شده است: "
                f"{existing_manager['first_name']} {existing_manager['last_name']}"
            )
            return

        QMessageBox.information(self, "ثبت شد", f"«{selected['name']}» به‌عنوان محل جلسات این بلوک ثبت شد.")
        self._prompt_place_manager_registration(selected, role_label)

    def _prompt_place_manager_registration(self, place, role_label):
        """برای هر نوع مکان عمومی، مسئول را ثبت و به‌عنوان معتمد بلوک ذخیره می‌کند."""
        dialog = FacilityManagerDialog(
            self, facility_name=place["name"], role_label=role_label or "مسئول مکان"
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            self.db.register_place_manager(
                place["id"], self.current_zone_id,
                data["first_name"], data["last_name"], data["mobile"],
                role_label=role_label,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "خطا", str(exc))
            return
        self.refresh_members_table()
        self._load_zone_data(self.current_zone_id)
        QMessageBox.information(
            self, "ثبت شد",
            f"{data['first_name']} {data['last_name']} به‌عنوان {role_label} «{place['name']}» "
            "و معتمد این بلوک در شورای محله ثبت شد."
        )

    def _handle_mosque_selected(self, mosque_id):
        if self.current_zone_id is None:
            return
        mosques = self.db.get_mosques(zone_id=self.current_zone_id)
        selected = next((m for m in mosques if str(m["id"]) == str(mosque_id)), None)
        if not selected:
            return
        self.meeting_place_label.setText(selected["name"])
        self.db.set_zone_meeting_place(
            self.current_zone_id, None, selected["name"],
            self.meeting_address_input.text().strip(), selected["lat"], selected["lon"],
            source_type="mosque", source_id=str(selected["id"]),
        )
        self._load_zone_data(self.current_zone_id)

        existing_imam = self.db.get_mosque_imam(selected["id"])
        if existing_imam:
            QMessageBox.information(
                self, "ثبت شد",
                f"«{selected['name']}» به‌عنوان محل جلسات این بلوک ثبت شد.\n"
                f"امام جماعت این مسجد پیش‌تر ثبت شده است: "
                f"{existing_imam['first_name']} {existing_imam['last_name']}"
            )
            return

        QMessageBox.information(
            self, "ثبت شد", f"«{selected['name']}» به‌عنوان محل جلسات این بلوک ثبت شد."
        )
        self._prompt_mosque_imam_registration(selected)

    def _prompt_mosque_imam_registration(self, mosque):
        """پس از انتخاب یک مسجد به‌عنوان محل جلسات، در صورتی که امام جماعت آن
        هنوز ثبت نشده باشد، فرم ثبت امام جماعت را باز می‌کند تا او به‌طور
        خودکار به‌عنوان معتمد همین بلوک در شورای محلات ذخیره شود."""
        dialog = MosqueImamDialog(self, mosque_name=mosque["name"])
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            self.db.register_mosque_imam(
                mosque["id"], self.current_zone_id,
                data["first_name"], data["last_name"], data["mobile"],
            )
        except ValueError as exc:
            QMessageBox.warning(self, "خطا", str(exc))
            return
        self.refresh_members_table()
        QMessageBox.information(
            self, "ثبت شد",
            f"{data['first_name']} {data['last_name']} به‌عنوان امام جماعت «{mosque['name']}» "
            "و معتمد این بلوک در شورای محلات ثبت شد."
        )

    # ---------------- انتخاب مدرسه/مرکز بهداشتی به‌عنوان محل جلسات ----------------
    _FACILITY_UI_CONFIG = {
        "school": {
            "getter": "get_schools", "manager_getter": "get_school_manager",
            "register": "register_school_manager", "role_label": "مدیر مدرسه",
        },
        "health_center": {
            "getter": "get_health_centers", "manager_getter": "get_health_center_manager",
            "register": "register_health_center_manager", "role_label": "مسؤول مرکز بهداشتی",
        },
    }

    def _handle_facility_selected(self, source_type, facility_id):
        if self.current_zone_id is None:
            return
        cfg = self._FACILITY_UI_CONFIG[source_type]
        facilities = getattr(self.db, cfg["getter"])(zone_id=self.current_zone_id)
        selected = next((f for f in facilities if str(f["id"]) == str(facility_id)), None)
        if not selected:
            return
        self.meeting_place_label.setText(selected["name"])
        self.db.set_zone_meeting_place(
            self.current_zone_id, None, selected["name"],
            self.meeting_address_input.text().strip(), selected["lat"], selected["lon"],
            source_type=source_type, source_id=str(selected["id"]),
        )
        self._load_zone_data(self.current_zone_id)

        existing_manager = getattr(self.db, cfg["manager_getter"])(selected["id"])
        if existing_manager:
            QMessageBox.information(
                self, "ثبت شد",
                f"«{selected['name']}» به‌عنوان محل جلسات این بلوک ثبت شد.\n"
                f"{cfg['role_label']} این مکان پیش‌تر ثبت شده است: "
                f"{existing_manager['first_name']} {existing_manager['last_name']}"
            )
            return

        QMessageBox.information(
            self, "ثبت شد", f"«{selected['name']}» به‌عنوان محل جلسات این بلوک ثبت شد."
        )
        self._prompt_facility_manager_registration(source_type, selected)

    def _prompt_facility_manager_registration(self, source_type, facility):
        """پس از انتخاب یک مدرسه/مرکز بهداشتی به‌عنوان محل جلسات، در صورتی که
        مسؤول آن هنوز ثبت نشده باشد، فرم ثبت مسؤول را باز می‌کند تا او به‌طور
        خودکار به‌عنوان معتمد همین بلوک در شورای محلات ذخیره شود."""
        cfg = self._FACILITY_UI_CONFIG[source_type]
        dialog = FacilityManagerDialog(self, facility_name=facility["name"], role_label=cfg["role_label"])
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            getattr(self.db, cfg["register"])(
                facility["id"], self.current_zone_id,
                data["first_name"], data["last_name"], data["mobile"],
            )
        except ValueError as exc:
            QMessageBox.warning(self, "خطا", str(exc))
            return
        self.refresh_members_table()
        QMessageBox.information(
            self, "ثبت شد",
            f"{data['first_name']} {data['last_name']} به‌عنوان {cfg['role_label']} «{facility['name']}» "
            "و معتمد این بلوک در شورای محلات ثبت شد."
        )

    def _on_save_meeting_address(self):
        if self.current_zone_id is None:
            return
        meeting_place = self.db.get_zone_meeting_place(self.current_zone_id)
        if not meeting_place:
            QMessageBox.warning(self, "خطا", "ابتدا یک مکان را روی نقشه انتخاب کنید.")
            return
        self.db.set_zone_meeting_place(
            self.current_zone_id, meeting_place["place_id"], meeting_place["place_name"],
            self.meeting_address_input.text().strip(), meeting_place["lat"], meeting_place["lon"],
            source_type=meeting_place.get("source_type") or "place",
            source_id=meeting_place.get("source_id"),
        )
        QMessageBox.information(self, "ذخیره شد", "آدرس دقیق محل جلسات ذخیره شد.")

    # ---------------- نمایش خیابان‌های بلوک ----------------
    def _on_show_streets(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک بلوک/منطقه انتخاب کنید.")
            return
        zone = self.db.get_zone(self.current_zone_id)
        dialog = StreetsTableDialog(self.db, self.current_zone_id, zone["name"], parent=self)
        dialog.exec_()

    def focus_member_registration(self):
        """هنگام ورود از داشبورد، بخش ثبت اعضای بلوک را مستقیم در دید قرار می‌دهد."""
        def _focus():
            if hasattr(self, "scroll_area") and hasattr(self, "members_group"):
                self.scroll_area.ensureWidgetVisible(self.members_group, 20, 20)
        QTimer.singleShot(120, _focus)

    # ---------------- مدیریت اعضای شورا ----------------
    def refresh_members_table(self):
        if self.current_zone_id is None:
            self.members_table.setRowCount(0)
            self.members_count_label.setText("تعداد اعضای ثبت‌شده برای این بلوک: 0")
            return
        members = self.db.get_council_members(zone_id=self.current_zone_id)
        # امامان جماعت مساجد همیشه در ابتدای فهرست نمایش داده می‌شوند و با رنگ سبز مشخص می‌شوند
        is_imam = lambda m: bool((m.get("position") or "").startswith("امام جماعت"))
        members = sorted(members, key=lambda m: 0 if is_imam(m) else 1)
        self._current_members = members
        self.members_table.setRowCount(len(members))
        imam_color = QColor("#d4edda")  # سبز ملایم برای برجسته‌سازی ردیف امام جماعت
        for row, m in enumerate(members):
            values = [
                m["first_name"], m["last_name"], m["national_code"] or "",
                m["education"] or "", m["mobile"] or "", m["member_group"] or "", m["position"] or "",
            ]
            highlight = is_imam(m)
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if highlight:
                    item.setBackground(imam_color)
                self.members_table.setItem(row, col, item)
        self.members_count_label.setText(f"تعداد اعضای ثبت‌شده برای این بلوک: {len(members)}")

    def _get_selected_member(self):
        row = self.members_table.currentRow()
        if row < 0 or not hasattr(self, "_current_members") or row >= len(self._current_members):
            return None
        return self._current_members[row]

    def _on_add_member(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک بلوک/منطقه انتخاب کنید.")
            return
        dialog = MemberFormDialog(parent=self)
        zone = self.db.get_zone(self.current_zone_id)
        if zone:
            dialog.setWindowTitle(f"ثبت عضو شورای بلوک: {zone['name']}")
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            try:
                self.db.add_council_member(
                    self.current_zone_id, data["first_name"], data["last_name"],
                    data["national_code"], data["education"], data["mobile"],
                    data["member_group"], data["position"]
                )
            except ValueError as exc:
                QMessageBox.warning(self, "عدم امکان ثبت", str(exc))
                return
            self.refresh_members_table()

    def _on_edit_member(self):
        member = self._get_selected_member()
        if not member:
            QMessageBox.warning(self, "خطا", "ابتدا یک عضو را از جدول انتخاب کنید.")
            return
        dialog = MemberFormDialog(parent=self, member=member)
        zone = self.db.get_zone(self.current_zone_id)
        if zone:
            dialog.setWindowTitle(f"ویرایش عضو شورای بلوک: {zone['name']}")
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            self.db.update_council_member(
                member["id"], data["first_name"], data["last_name"],
                data["national_code"], data["education"], data["mobile"],
                data["member_group"], data["position"]
            )
            self.refresh_members_table()

    def _on_delete_member(self):
        member = self._get_selected_member()
        if not member:
            QMessageBox.warning(self, "خطا", "ابتدا یک عضو را از جدول انتخاب کنید.")
            return
        reply = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف «{member['first_name']} {member['last_name']}» مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_council_member(member["id"])
            self.refresh_members_table()
