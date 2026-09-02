# -*- coding: utf-8 -*-
"""
ماژول اولویت‌بندی مشکلات و درخواست‌ها + ماژول اقدامات انجام‌شده.
هر دو صفحه ساختار مشترکی دارند (انتخاب منطقه، نقشه، دکمه‌های لیست خیابان/اعضا، جدول)
اما صفحه «اقدامات انجام‌شده» علاوه بر آن، امکان ثبت اقدام پیگیری برای هر درخواست را دارد.
"""

import os
from runtime_paths import get_temp_dir
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QGroupBox, QFormLayout, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDialog,
    QDialogButtonBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from header_widget import build_official_header
from jalali_utils import convert_dates_in_text
from map_html import build_zone_meeting_map_html


class DebugWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS Console - Priority Map] {message} (line {lineNumber})")


class StreetsListDialog(QDialog):
    """دیالوگ نمایش لیست خیابان‌ها و کوچه‌های یک منطقه."""
    def __init__(self, db, zone_id, zone_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.zone_id = zone_id
        self.setWindowTitle(f"خیابان‌ها و کوچه‌های منطقه: {zone_name}")
        self.resize(700, 550)
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


class MembersListDialog(QDialog):
    """دیالوگ نمایش لیست اعضای شورای محلات یک منطقه."""
    def __init__(self, db, zone_id, zone_name, parent=None):
        super().__init__(parent)
        self.db = db
        self.zone_id = zone_id
        self.setWindowTitle(f"اعضای شورای محلات منطقه: {zone_name}")
        self.resize(800, 500)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "نام", "نام خانوادگی", "کد ملی", "تحصیلات", "موبایل", "دسته", "سمت"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        members = self.db.get_council_members(zone_id=self.zone_id)
        self.table.setRowCount(len(members))
        for row, m in enumerate(members):
            self.table.setItem(row, 0, QTableWidgetItem(m["first_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(m["last_name"]))
            self.table.setItem(row, 2, QTableWidgetItem(m["national_code"] or ""))
            self.table.setItem(row, 3, QTableWidgetItem(m["education"] or ""))
            self.table.setItem(row, 4, QTableWidgetItem(m["mobile"] or ""))
            self.table.setItem(row, 5, QTableWidgetItem(m["member_group"] or ""))
            self.table.setItem(row, 6, QTableWidgetItem(m["position"] or ""))

        self.count_label = QLabel(f"تعداد اعضا: {len(members)}")
        layout.addWidget(self.count_label)

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class ActionsDialog(QDialog):
    """دیالوگ نمایش و ثبت اقدامات انجام‌شده برای یک درخواست خاص."""
    def __init__(self, db, request_id, request_description, parent=None):
        super().__init__(parent)
        self.db = db
        self.request_id = request_id
        self.setWindowTitle("اقدامات انجام‌شده")
        self.resize(650, 500)
        self._build_ui(request_description)

    def _build_ui(self, request_description):
        layout = QVBoxLayout(self)

        desc_label = QLabel(f"درخواست/مشکل: {request_description}")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(desc_label)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["تاریخ ثبت", "شرح اقدام انجام‌شده"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.table)
        self._refresh_table()

        new_action_group = QGroupBox("ثبت اقدام جدید")
        form = QFormLayout(new_action_group)
        self.new_action_input = QTextEdit()
        self.new_action_input.setFixedHeight(80)
        self.new_action_input.setPlaceholderText("شرح اقدام انجام‌شده برای این درخواست را وارد کنید ...")
        form.addRow("شرح اقدام:", self.new_action_input)

        add_btn = QPushButton("➕ ثبت اقدام جدید")
        add_btn.setProperty("success", True)
        add_btn.clicked.connect(self._on_add_action)
        form.addRow(add_btn)
        layout.addWidget(new_action_group)

        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _refresh_table(self):
        actions = self.db.get_request_actions(self.request_id)
        self.table.setRowCount(len(actions))
        for row, a in enumerate(actions):
            self.table.setItem(row, 0, QTableWidgetItem(format_jalali(a["created_at"])))
            self.table.setItem(row, 1, QTableWidgetItem(a["action_description"]))

    def _on_add_action(self):
        text = self.new_action_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "خطا", "لطفاً شرح اقدام را وارد کنید.")
            return
        self.db.add_request_action(self.request_id, text)
        self.new_action_input.clear()
        self._refresh_table()


class BasePriorityWindow(QWidget):
    """
    کلاس پایه مشترک بین صفحه «اولویت‌بندی مشکلات» و «اقدامات انجام‌شده».
    show_actions_column کنترل می‌کند که آیا ستون/دکمه «اقدامات» در جدول نمایش داده شود یا نه.
    """
    back_requested = pyqtSignal()

    def __init__(self, db, title, subtitle, show_actions_column=False):
        super().__init__()
        self.db = db
        self.current_zone_id = None
        self.show_actions_column = show_actions_column
        self.setWindowTitle(title)
        self.resize(1300, 900)
        self._build_ui(subtitle)

    def _build_ui(self, subtitle):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = build_official_header(app_subtitle=subtitle, db=self.db)
        outer.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(24, 16, 24, 16)
        body.setSpacing(14)

        top_row = QHBoxLayout()
        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_requested.emit)
        top_row.addWidget(back_btn)

        top_row.addSpacing(20)
        top_row.addWidget(QLabel("بلوک / محله:"))
        self.zone_combo = QComboBox()
        self.zone_combo.setMinimumWidth(260)
        self.zone_combo.currentIndexChanged.connect(self._on_zone_changed)
        top_row.addWidget(self.zone_combo)
        top_row.addStretch()
        body.addLayout(top_row)

        # نقشه منطقه
        map_group = QGroupBox("نقشه بلوک انتخاب‌شده")
        map_layout = QVBoxLayout(map_group)
        self.map_webview = QWebEngineView()
        self.map_webview.setMinimumHeight(280)
        self.map_page = DebugWebPage(self.map_webview)
        self.map_webview.setPage(self.map_page)
        map_layout.addWidget(self.map_webview)
        body.addWidget(map_group)

        # دکمه‌های لیست خیابان و اعضا
        list_btn_row = QHBoxLayout()
        streets_btn = QPushButton("لیست خیابان‌های این منطقه")
        streets_btn.clicked.connect(self._on_show_streets)
        list_btn_row.addWidget(streets_btn)

        members_btn = QPushButton("لیست اعضای شورای محله")
        members_btn.clicked.connect(self._on_show_members)
        list_btn_row.addWidget(members_btn)
        list_btn_row.addStretch()
        body.addLayout(list_btn_row)

        # فرم ثبت درخواست/مشکل (فقط در صفحه اولویت‌بندی نمایش داده می‌شود؛
        # صفحه اقدامات انجام‌شده فقط جدول را نشان می‌دهد و امکان افزودن اقدام دارد)
        if not self.show_actions_column:
            form_group = QGroupBox("ثبت درخواست و مشکلات بر اساس اولویت")
            form_layout = QFormLayout(form_group)

            self.description_input = QTextEdit()
            self.description_input.setFixedHeight(90)
            self.description_input.setPlaceholderText(
                "شرح درخواست و مشکلات بر اساس اولویت را بنویسید ..."
            )
            form_layout.addRow("شرح درخواست/مشکل:", self.description_input)

            self.office_input = QLineEdit()
            self.office_input.setPlaceholderText("مثلاً: شهرداری جوانرود، اداره برق، آبفا و ...")
            form_layout.addRow("اداره مرتبط:", self.office_input)

            save_btn = QPushButton("ذخیره")
            save_btn.setProperty("success", True)
            save_btn.clicked.connect(self._on_save_request)
            form_layout.addRow(save_btn)

            body.addWidget(form_group)

        # جدول درخواست‌ها
        table_group = QGroupBox("لیست درخواست‌ها و مشکلات ثبت‌شده")
        table_layout = QVBoxLayout(table_group)

        column_count = 5 if self.show_actions_column else 4
        self.requests_table = QTableWidget()
        self.requests_table.setColumnCount(column_count)
        headers = ["ردیف", "نام منطقه", "درخواست و مشکلات بر اساس اولویت", "اداره مرتبط"]
        if self.show_actions_column:
            headers.append("اقدامات")
        self.requests_table.setHorizontalHeaderLabels(headers)
        self.requests_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.requests_table.setSelectionBehavior(QTableWidget.SelectRows)
        table_layout.addWidget(self.requests_table)

        action_row = QHBoxLayout()
        if not self.show_actions_column:
            edit_btn = QPushButton("ویرایش ردیف انتخاب‌شده")
            edit_btn.clicked.connect(self._on_edit_request)
            action_row.addWidget(edit_btn)

            delete_btn = QPushButton("حذف ردیف انتخاب‌شده")
            delete_btn.setProperty("danger", True)
            delete_btn.clicked.connect(self._on_delete_request)
            action_row.addWidget(delete_btn)
        action_row.addStretch()
        table_layout.addLayout(action_row)

        body.addWidget(table_group)

        # کل محتوای صفحه داخل یک ناحیه قابل اسکرول قرار می‌گیرد تا در صفحه‌نمایش‌های
        # کوچک‌تر، بخش‌های پایینی (فرم ثبت درخواست یا جدول) از دید خارج نشوند.
        scroll_content = QWidget()
        scroll_content.setLayout(body)

        scroll_area = QScrollArea()
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

        places = self.db.get_places(zone_id=zone_id)
        mosques = self.db.get_mosques(zone_id=zone_id)
        html = build_zone_meeting_map_html(
            zone, places, offline=False, mosques=mosques, allow_selection=False
        )
        temp_path = self._write_temp_html(html)
        self.map_webview.setUrl(QUrl.fromLocalFile(temp_path))

        self.refresh_requests_table()

    def _write_temp_html(self, html_content):
        temp_dir = get_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        # نام فایل بر اساس نوع صفحه متفاوت است تا با نقشه ماژول شورا تداخل نکند
        fname = "priority_map.html" if not self.show_actions_column else "actions_map.html"
        path = os.path.join(temp_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return path

    # ---------------- دیالوگ‌های لیست خیابان و اعضا ----------------
    def _on_show_streets(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک بلوک/منطقه انتخاب کنید.")
            return
        zone = self.db.get_zone(self.current_zone_id)
        dialog = StreetsListDialog(self.db, self.current_zone_id, zone["name"], parent=self)
        dialog.exec_()

    def _on_show_members(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک بلوک/منطقه انتخاب کنید.")
            return
        zone = self.db.get_zone(self.current_zone_id)
        dialog = MembersListDialog(self.db, self.current_zone_id, zone["name"], parent=self)
        dialog.exec_()

    # ---------------- ثبت/ویرایش/حذف درخواست (فقط صفحه اولویت‌بندی) ----------------
    def _on_save_request(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک بلوک/منطقه انتخاب کنید.")
            return
        description = self.description_input.toPlainText().strip()
        office = self.office_input.text().strip()
        if not description:
            QMessageBox.warning(self, "خطا", "لطفاً شرح درخواست/مشکل را وارد کنید.")
            return
        self.db.add_priority_request(self.current_zone_id, description, office)
        self.description_input.clear()
        self.office_input.clear()
        self.refresh_requests_table()

    def _on_edit_request(self):
        row = self.requests_table.currentRow()
        if row < 0 or not hasattr(self, "_current_requests") or row >= len(self._current_requests):
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        req = self._current_requests[row]

        dialog = QDialog(self)
        dialog.setWindowTitle("ویرایش درخواست")
        dialog.resize(450, 300)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        desc_edit = QTextEdit()
        desc_edit.setPlainText(req["description"])
        desc_edit.setFixedHeight(90)
        form.addRow("شرح درخواست/مشکل:", desc_edit)

        office_edit = QLineEdit()
        office_edit.setText(req["related_office"] or "")
        form.addRow("اداره مرتبط:", office_edit)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted:
            new_desc = desc_edit.toPlainText().strip()
            new_office = office_edit.text().strip()
            if new_desc:
                self.db.update_priority_request(req["id"], description=new_desc, related_office=new_office)
                self.refresh_requests_table()

    def _on_delete_request(self):
        row = self.requests_table.currentRow()
        if row < 0 or not hasattr(self, "_current_requests") or row >= len(self._current_requests):
            QMessageBox.warning(self, "خطا", "ابتدا یک ردیف را از جدول انتخاب کنید.")
            return
        req = self._current_requests[row]
        reply = QMessageBox.question(
            self, "تأیید حذف",
            f"آیا از حذف این درخواست مطمئن هستید؟\n\n{req['description'][:80]}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.db.delete_priority_request(req["id"])
            self.refresh_requests_table()

    # ---------------- جدول درخواست‌ها ----------------
    def refresh_requests_table(self):
        if self.current_zone_id is None:
            self.requests_table.setRowCount(0)
            return
        zone = self.db.get_zone(self.current_zone_id)
        zone_name = zone["name"] if zone else "—"
        self._current_requests = self.db.get_priority_requests(zone_id=self.current_zone_id)

        self.requests_table.setRowCount(len(self._current_requests))
        for row, r in enumerate(self._current_requests):
            self.requests_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.requests_table.setItem(row, 1, QTableWidgetItem(zone_name))
            self.requests_table.setItem(row, 2, QTableWidgetItem(r["description"]))
            self.requests_table.setItem(row, 3, QTableWidgetItem(r["related_office"] or ""))

            if self.show_actions_column:
                btn = QPushButton(f"اقدامات ({r['action_count']}) / ثبت اقدام جدید")
                btn.clicked.connect(lambda _, req_id=r["id"], desc=r["description"]: self._on_open_actions(req_id, desc))
                self.requests_table.setCellWidget(row, 4, btn)

    def _on_open_actions(self, request_id, description):
        dialog = ActionsDialog(self.db, request_id, description, parent=self)
        dialog.exec_()
        self.refresh_requests_table()


class PriorityRequestsWindow(BasePriorityWindow):
    """صفحه «اولویت‌بندی مشکلات و درخواست‌ها»."""
    def __init__(self, db):
        super().__init__(
            db,
            title="اولویت‌بندی مشکلات و درخواست‌ها",
            subtitle="اولویت‌بندی مشکلات و درخواست‌ها",
            show_actions_column=False
        )


class CompletedActionsWindow(BasePriorityWindow):
    """صفحه «اقدامات انجام‌شده» — همان لیست درخواست‌ها به‌همراه امکان ثبت اقدام پیگیری."""
    def __init__(self, db):
        super().__init__(
            db,
            title="اقدامات انجام‌شده",
            subtitle="اقدامات انجام‌شده",
            show_actions_column=True
        )
