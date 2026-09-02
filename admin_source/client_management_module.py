# -*- coding: utf-8 -*-
"""مدیریت کلاینت‌های آفلاین: درخواست دستگاه، صدور/تمدید مجوز و ورود بسته‌ها."""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
    QDialog, QDialogButtonBox, QLineEdit, QComboBox, QSpinBox, QCheckBox, QTextEdit,
    QAbstractItemView, QScrollArea, QFrame
)

from header_widget import build_official_header
from jalali_widgets import JalaliDateEdit
from jalali_utils import iso_to_jalali, to_persian_digits
from icon_manager import get_icon, set_button_style


def _selected_id(table):
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    return item.data(Qt.UserRole) if item else None


def _mask_code(code):
    text = str(code or "")
    return text[:3] + "****" + text[-3:] if len(text) == 10 else text


class LicenseIssueDialog(QDialog):
    def __init__(self, db, request_id, parent=None):
        super().__init__(parent)
        self.db = db
        self.request_id = request_id
        self.setWindowTitle("صدور فایل فعال‌سازی کلاینت")
        self.resize(650, 760)
        root = QVBoxLayout(self)
        host = QWidget()
        form = QFormLayout(host)
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.national_code = QLineEdit(); self.national_code.setMaxLength(10)
        self.username = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("حداقل ۸ نویسه؛ فقط هنگام صدور نمایش داده می‌شود")
        self.zone = QComboBox()
        for z in self.db.get_zones():
            self.zone.addItem(z["name"], z["id"])
        self.committee = QComboBox()
        self.zone.currentIndexChanged.connect(self._reload_committees)
        self.role_title = QLineEdit()
        self.valid_from = JalaliDateEdit(date.today().isoformat())
        self.valid_until = JalaliDateEdit((date.today() + timedelta(days=365)).isoformat())
        self.warning_days = QSpinBox(); self.warning_days.setRange(0, 90); self.warning_days.setValue(7)
        self.allow_renewal = QCheckBox("تمدید مجوز توسط ادمین مجاز باشد"); self.allow_renewal.setChecked(True)
        form.addRow("نام مسئول*:", self.first_name)
        form.addRow("نام خانوادگی*:", self.last_name)
        form.addRow("کد ملی*:", self.national_code)
        form.addRow("نام کاربری*:", self.username)
        form.addRow("رمز عبور اولیه*:", self.password)
        form.addRow("بلوک مجاز*:", self.zone)
        form.addRow("کمیته مجاز*:", self.committee)
        form.addRow("عنوان مسئولیت:", self.role_title)
        form.addRow("شروع اعتبار:", self.valid_from)
        form.addRow("پایان اعتبار:", self.valid_until)
        form.addRow("هشدار پیش از انقضا (روز):", self.warning_days)
        form.addRow("تمدید:", self.allow_renewal)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(host)
        root.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("صدور فایل فعال‌سازی")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._reload_committees()

    def _reload_committees(self):
        self.committee.clear()
        zid = self.zone.currentData()
        if zid is None:
            return
        for c in self.db.get_zone_committees(zid):
            self.committee.addItem(c["title"], c["committee_code"])
        if self.committee.currentText():
            self.role_title.setText(f"مسئول کمیته {self.committee.currentText()}")

    def values(self):
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "national_code": self.national_code.text().strip(),
            "username": self.username.text().strip(),
            "initial_password": self.password.text(),
            "zone_id": self.zone.currentData(),
            "committee_code": self.committee.currentData(),
            "role_title": self.role_title.text().strip(),
            "valid_from": self.valid_from.isoDate(),
            "valid_until": self.valid_until.isoDate(),
            "warning_days": self.warning_days.value(),
            "allow_renewal": self.allow_renewal.isChecked(),
        }


class RenewalDialog(QDialog):
    def __init__(self, license_item, parent=None):
        super().__init__(parent)
        self.item = license_item
        self.setWindowTitle("تمدید اعتبار کلاینت")
        layout = QFormLayout(self)
        self.national_code = QLineEdit(); self.national_code.setMaxLength(10)
        self.valid_from = JalaliDateEdit(date.today().isoformat())
        current_end = license_item.get("valid_until") or date.today().isoformat()
        try:
            base = date.fromisoformat(current_end)
        except Exception:
            base = date.today()
        self.valid_until = JalaliDateEdit((max(base, date.today()) + timedelta(days=365)).isoformat())
        self.warning_days = QSpinBox(); self.warning_days.setRange(0, 90); self.warning_days.setValue(int(license_item.get("warning_days") or 7))
        layout.addRow("مسئول:", QLabel(license_item.get("responsible_full_name") or ""))
        layout.addRow("بلوک و کمیته:", QLabel(f"{license_item.get('zone_name')} — {license_item.get('committee_title')}"))
        layout.addRow("کد ملی برای رمزنگاری*:", self.national_code)
        layout.addRow("شروع اعتبار جدید:", self.valid_from)
        layout.addRow("پایان اعتبار جدید:", self.valid_until)
        layout.addRow("هشدار پیش از انقضا:", self.warning_days)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("صدور فایل تمدید")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class LicenseEditDialog(QDialog):
    """ویرایش امن مشخصات فعال‌سازی و صدور فایل جایگزین برای همان مجوز."""

    def __init__(self, db, license_item, parent=None):
        super().__init__(parent)
        self.db = db
        self.item = license_item
        self.setWindowTitle("اصلاح فعال‌سازی کلاینت")
        self.resize(650, 780)
        root = QVBoxLayout(self)
        host = QWidget()
        form = QFormLayout(host)

        self.first_name = QLineEdit(str(license_item.get("responsible_first_name") or ""))
        self.last_name = QLineEdit(str(license_item.get("responsible_last_name") or ""))
        self.national_code = QLineEdit(str(license_item.get("national_code") or ""))
        self.national_code.setMaxLength(10)
        self.username = QLineEdit(str(license_item.get("username") or ""))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("برای حفظ رمز فعلی خالی بگذارید")

        self.zone = QComboBox()
        for z in self.db.get_zones():
            self.zone.addItem(z["name"], z["id"])
        self.committee = QComboBox()
        self.role_title = QLineEdit(str(license_item.get("role_title") or ""))
        self.valid_from = JalaliDateEdit(license_item.get("valid_from") or date.today().isoformat())
        self.valid_until = JalaliDateEdit(license_item.get("valid_until") or (date.today() + timedelta(days=365)).isoformat())
        self.warning_days = QSpinBox()
        self.warning_days.setRange(0, 90)
        self.warning_days.setValue(int(license_item.get("warning_days") or 0))
        self.allow_renewal = QCheckBox("تمدید مجوز توسط ادمین مجاز باشد")
        self.allow_renewal.setChecked(bool(license_item.get("allow_renewal")))
        self.status = QComboBox()
        self.status.addItems(["فعال", "تعلیق", "لغوشده", "منقضی"])
        status_index = self.status.findText(str(license_item.get("status") or "فعال"))
        if status_index >= 0:
            self.status.setCurrentIndex(status_index)

        form.addRow("نام مسئول*:", self.first_name)
        form.addRow("نام خانوادگی*:", self.last_name)
        form.addRow("کد ملی*:", self.national_code)
        form.addRow("نام کاربری*:", self.username)
        form.addRow("رمز عبور جدید:", self.password)
        form.addRow("بلوک مجاز*:", self.zone)
        form.addRow("کمیته مجاز*:", self.committee)
        form.addRow("عنوان مسئولیت:", self.role_title)
        form.addRow("شروع اعتبار:", self.valid_from)
        form.addRow("پایان اعتبار:", self.valid_until)
        form.addRow("هشدار پیش از انقضا (روز):", self.warning_days)
        form.addRow("تمدید:", self.allow_renewal)
        form.addRow("وضعیت:", self.status)

        self.zone.currentIndexChanged.connect(self._reload_committees)
        zone_index = self.zone.findData(license_item.get("zone_id"))
        if zone_index >= 0:
            self.zone.setCurrentIndex(zone_index)
        self._reload_committees(license_item.get("committee_code"))

        note = QLabel("پس از ذخیره، یک فایل فعال‌سازی جایگزین ساخته می‌شود و باید روی همان کلاینت نصب شود.")
        note.setWordWrap(True)
        note.setStyleSheet("padding:8px;background:#fff7df;border:1px solid #e3c36a;border-radius:7px")
        root.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره و ساخت فایل اصلاح‌شده")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _reload_committees(self, preferred_code=None):
        current_code = preferred_code if isinstance(preferred_code, str) else self.committee.currentData()
        self.committee.clear()
        zid = self.zone.currentData()
        if zid is None:
            return
        for c in self.db.get_zone_committees(zid):
            self.committee.addItem(c["title"], c["committee_code"])
        if current_code:
            idx = self.committee.findData(current_code)
            if idx >= 0:
                self.committee.setCurrentIndex(idx)

    def values(self):
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "national_code": self.national_code.text().strip(),
            "username": self.username.text().strip(),
            "new_password": self.password.text(),
            "zone_id": self.zone.currentData(),
            "committee_code": self.committee.currentData(),
            "role_title": self.role_title.text().strip(),
            "valid_from": self.valid_from.isoDate(),
            "valid_until": self.valid_until.isoDate(),
            "warning_days": self.warning_days.value(),
            "allow_renewal": self.allow_renewal.isChecked(),
            "status": self.status.currentText(),
        }


class ClientImportPreviewDialog(QDialog):
    def __init__(self, preview, parent=None):
        super().__init__(parent)
        self.preview = preview
        self.decision_widgets = {}
        self.setWindowTitle("بررسی و تأیید فایل کلاینت")
        self.resize(1100, 720)
        root = QVBoxLayout(self)
        info = QLabel(
            f"مسئول: {preview['responsible_name']}    |    بلوک: {preview['zone_name']}    |    "
            f"کمیته: {preview['committee_title']}\n"
            f"دوره گزارش: {preview['report_period']}    |    تاریخ ساخت فایل: {preview['client_created_at']}"
        )
        info.setWordWrap(True); info.setStyleSheet("font-weight:700;padding:10px;background:#eef4fb;border-radius:8px")
        root.addWidget(info)
        c = preview["counts"]
        counts = QLabel(
            f"جدید: {to_persian_digits(c['new'])}    اصلاح‌شده: {to_persian_digits(c['changed'])}    "
            f"تکراری: {to_persian_digits(c['duplicate'])}    تعارض: {to_persian_digits(c['conflict'])}"
        )
        root.addWidget(counts)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["وضعیت", "نوع", "عنوان", "جزئیات تعارض", "بازبینی", "تاریخ تغییر", "تصمیم", "شناسه"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root.addWidget(self.table, 1)
        labels = {"new":"جدید", "changed":"اصلاح‌شده", "duplicate":"تکراری", "conflict":"دارای تعارض"}
        types = {"member":"عضو", "meeting":"جلسه", "issue":"مسئله", "resolution":"مصوبه", "action":"اقدام"}
        for record in preview["records"]:
            row = self.table.rowCount(); self.table.insertRow(row)
            data = record.get("data") or {}
            title = data.get("title") or data.get("full_name") or data.get("person_name") or "بدون عنوان"
            number_conflict = record.get("meeting_number_conflict") or {}
            conflict_text = ""
            if number_conflict:
                existing_number = number_conflict.get("incoming_number") or "—"
                existing_title = number_conflict.get("existing_title") or "جلسه موجود"
                existing_date = number_conflict.get("existing_date") or "بدون تاریخ"
                if number_conflict.get("kind") == "mapped_number_collision":
                    assigned = number_conflict.get("mapped_number") or "—"
                    conflict_text = (
                        f"شماره {existing_number} متعلق به «{existing_title}» ({existing_date}) است؛ "
                        f"این رکورد قبلاً با شماره {assigned} ثبت شده است."
                    )
                else:
                    conflict_text = f"شماره {existing_number} قبلاً برای «{existing_title}» ({existing_date}) ثبت شده است."
            values = [
                labels.get(record["classification"], record["classification"]),
                types.get(record["record_type"], record["record_type"]),
                title, conflict_text, record.get("revision"), record.get("updated_at") or "", "", record["record_uuid"]
            ]
            for col, value in enumerate(values):
                if col == 6:
                    continue
                item = QTableWidgetItem(str(value))
                if col == 3 and value:
                    item.setToolTip(str(value))
                self.table.setItem(row, col, item)
            decision = QComboBox()
            if record["classification"] == "duplicate":
                decision.addItem("رد خودکار (تکراری)", "reject"); decision.setEnabled(False)
            elif number_conflict.get("kind") == "existing_number":
                decision.addItem("نیازمند تعیین تکلیف", "")
                decision.addItem("ادغام اطلاعات با جلسه موجود", "merge_existing")
                decision.addItem("ثبت با شماره جدید خودکار", "renumber")
                decision.addItem("رد این صورتجلسه", "reject")
            elif number_conflict.get("kind") == "mapped_number_collision":
                decision.addItem("نیازمند تعیین تکلیف", "")
                decision.addItem("حفظ شماره اختصاص‌یافته قبلی", "keep_assigned")
                decision.addItem("رد این تغییر", "reject")
            elif record["classification"] == "new":
                decision.addItem("تأیید", "accept"); decision.addItem("رد", "reject")
            else:
                decision.addItem("نیازمند تصمیم", "")
                decision.addItem("تأیید تغییر", "accept")
                decision.addItem("رد تغییر", "reject")
            self.table.setCellWidget(row, 6, decision)
            self.decision_widgets[record["record_uuid"]] = decision
        warning = QLabel(
            "قاعده یکتایی: در هر کمیته، هر شماره جلسه فقط یک‌بار مجاز است. "
            "در تعارض شماره، ورود تا انتخاب «ادغام»، «شماره جدید» یا «رد» متوقف می‌ماند."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("padding:8px;background:#fff7df;border:1px solid #e3c36a;border-radius:7px")
        root.addWidget(warning)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("اعمال موارد تأییدشده")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._accept_checked); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept_checked(self):
        for record in self.preview["records"]:
            if record["classification"] in {"changed", "conflict"} and not self.decision_widgets[record["record_uuid"]].currentData():
                QMessageBox.warning(self, "تصمیم ناقص", "برای همه رکوردهای اصلاح‌شده یا دارای تعارض، یک تصمیم مشخص انتخاب کنید.")
                return
        self.accept()

    def decisions(self):
        return {rid: combo.currentData() or "reject" for rid, combo in self.decision_widgets.items()}


class ClientManagementWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("مدیریت کلاینت‌های آفلاین")
        self.resize(1380, 860)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 16)
        top = QHBoxLayout()
        back = QPushButton("بازگشت به داشبورد"); back.setIcon(get_icon("back", "navy")); back.clicked.connect(self.back_requested.emit)
        title = QLabel("مدیریت کلاینت‌های آفلاین، مجوزهای زمان‌دار و تبادل امن فایل")
        title.setStyleSheet("font-size:18px;font-weight:800;color:#17345f")
        top.addWidget(back); top.addStretch(); top.addWidget(title)
        root.addLayout(top)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._build_requests_tab(); self._build_import_tab(); self._build_history_tab()

    def _build_requests_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab)
        actions = QHBoxLayout()
        import_btn = QPushButton("ورود درخواست فعال‌سازی (.jrr)"); import_btn.setIcon(get_icon("upload", "navy")); import_btn.clicked.connect(self.import_request)
        issue_btn = QPushButton("صدور فایل فعال‌سازی"); issue_btn.setIcon(get_icon("security", "navy")); issue_btn.clicked.connect(self.issue_license)
        renew_btn = QPushButton("تمدید مجوز انتخابی"); renew_btn.clicked.connect(self.renew_license)
        edit_btn = QPushButton("اصلاح فعال‌سازی انتخابی"); edit_btn.clicked.connect(self.edit_license)
        set_button_style(edit_btn, "edit", "secondary")
        delete_btn = QPushButton("حذف فعال‌سازی انتخابی"); delete_btn.clicked.connect(self.delete_license)
        set_button_style(delete_btn, "delete", "danger")
        self.license_status = QComboBox()
        self.license_status.addItems(["فعال", "تعلیق", "لغوشده", "منقضی"])
        status_btn = QPushButton("اعمال وضعیت مجوز")
        status_btn.clicked.connect(self.change_license_status)
        refresh = QPushButton("تازه‌سازی"); refresh.clicked.connect(self.refresh_all)
        actions.addWidget(import_btn); actions.addWidget(issue_btn); actions.addWidget(renew_btn)
        actions.addWidget(edit_btn); actions.addWidget(delete_btn)
        actions.addWidget(self.license_status); actions.addWidget(status_btn)
        actions.addStretch(); actions.addWidget(refresh)
        layout.addLayout(actions)
        splitter = QHBoxLayout()
        self.requests_table = QTableWidget(0, 7)
        self.requests_table.setHorizontalHeaderLabels(["شناسه", "وضعیت", "دستگاه", "نسخه کلاینت", "تاریخ درخواست", "تاریخ ورود", "هش فایل"])
        self.requests_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.requests_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.requests_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.licenses_table = QTableWidget(0, 10)
        self.licenses_table.setHorizontalHeaderLabels(["شناسه", "مسئول", "کد ملی", "بلوک", "کمیته", "نام کاربری", "شروع", "انقضا", "وضعیت", "دستگاه"])
        self.licenses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.licenses_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.licenses_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.licenses_table.doubleClicked.connect(self.edit_license)
        layout.addWidget(QLabel("درخواست‌های دستگاه")); layout.addWidget(self.requests_table, 1)
        layout.addWidget(QLabel("مجوزهای صادرشده")); layout.addWidget(self.licenses_table, 1)
        self.tabs.addTab(tab, "مجوزها و فعال‌سازی")

    def _build_import_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab)
        box = QFrame(); box.setStyleSheet("QFrame{background:#f6f9fc;border:1px solid #d7e1ec;border-radius:10px;padding:12px}")
        form = QVBoxLayout(box)
        text = QLabel("فایل خروجی رمزنگاری‌شده کلاینت را انتخاب کنید. سامانه پیش از ورود، امضا، مجوز، بلوک، کمیته، تکراری‌بودن و تعارض رکوردها را کنترل می‌کند.")
        text.setWordWrap(True); form.addWidget(text)
        row = QHBoxLayout(); self.package_path = QLineEdit(); self.package_path.setReadOnly(True)
        choose = QPushButton("انتخاب فایل .jrcx"); choose.clicked.connect(self.choose_package)
        check = QPushButton("بررسی و ورود"); check.clicked.connect(self.preview_and_import)
        row.addWidget(self.package_path, 1); row.addWidget(choose); row.addWidget(check); form.addLayout(row)
        layout.addWidget(box); layout.addStretch()
        self.tabs.addTab(tab, "ورود فایل کلاینت")

    def _build_history_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab)
        self.history_table = QTableWidget(0, 13)
        self.history_table.setHorizontalHeaderLabels(["شناسه بسته", "مسئول", "بلوک", "کمیته", "دوره", "تاریخ کلاینت", "تاریخ ورود", "وضعیت", "جدید", "اصلاح", "تکراری", "تعارض", "پذیرفته"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        layout.addWidget(self.history_table)
        self.tabs.addTab(tab, "سوابق ورود")

    def refresh_all(self):
        requests = self.db.list_client_activation_requests(False)
        self.requests_table.setRowCount(0)
        for r in requests:
            row = self.requests_table.rowCount(); self.requests_table.insertRow(row)
            vals = [r["id"], r["status"], r["device_id"][:12] + "…", r.get("client_version") or "", r.get("request_created_at") or "", r.get("imported_at") or "", r["source_file_hash"][:12] + "…"]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(str(val));
                if col == 0: item.setData(Qt.UserRole, r["id"])
                self.requests_table.setItem(row, col, item)
        licenses = self.db.list_client_licenses(True)
        self.licenses_table.setRowCount(0)
        for lic in licenses:
            row = self.licenses_table.rowCount(); self.licenses_table.insertRow(row)
            vals = [lic["id"], lic["responsible_full_name"], _mask_code(lic["national_code"]), lic["zone_name"], lic["committee_title"], lic["username"], iso_to_jalali(lic["valid_from"]), iso_to_jalali(lic["valid_until"]), lic["status"], lic["device_id"][:12] + "…"]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(str(val));
                if col == 0: item.setData(Qt.UserRole, lic["license_uuid"])
                self.licenses_table.setItem(row, col, item)
        imports = self.db.list_client_imports()
        self.history_table.setRowCount(0)
        for x in imports:
            row = self.history_table.rowCount(); self.history_table.insertRow(row)
            vals = [x["package_uuid"][:12] + "…", x["responsible_name"], x["zone_name"], x["committee_title"], x["report_period"], x["client_created_at"], x["imported_at"], x["status"], x["new_count"], x["changed_count"], x["duplicate_count"], x["conflict_count"], x["accepted_count"]]
            for col, val in enumerate(vals): self.history_table.setItem(row, col, QTableWidgetItem(str(val or "")))

    def import_request(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب درخواست فعال‌سازی", "", "درخواست کلاینت (*.jrr);;همه فایل‌ها (*.*)")
        if not path: return
        try:
            data = self.db.import_client_activation_request(path)
            QMessageBox.information(self, "درخواست ثبت شد", f"درخواست دستگاه با شناسه {data['request_id']} ثبت شد.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def issue_license(self):
        request_id = _selected_id(self.requests_table)
        if request_id is None:
            QMessageBox.warning(self, "انتخاب درخواست", "ابتدا یک درخواست دستگاه را انتخاب کنید."); return
        dlg = LicenseIssueDialog(self.db, request_id, self)
        if dlg.exec_() != QDialog.Accepted: return
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل فعال‌سازی", "client_activation.jra", "فایل فعال‌سازی (*.jra)")
        if not path: return
        if not path.lower().endswith(".jra"): path += ".jra"
        try:
            payload = self.db.create_client_license(request_id, path, **dlg.values())
            QMessageBox.information(self, "مجوز صادر شد", f"فایل فعال‌سازی برای {payload['responsible_full_name']} ساخته شد.\nرمز عبور اولیه را فقط از مسیر امن به کاربر اعلام کنید.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "خطا در صدور مجوز", str(exc))

    def renew_license(self):
        license_uuid = _selected_id(self.licenses_table)
        if not license_uuid:
            QMessageBox.warning(self, "انتخاب مجوز", "ابتدا یک مجوز را انتخاب کنید."); return
        lic = self.db.get_client_license(license_uuid)
        dlg = RenewalDialog(lic, self)
        if dlg.exec_() != QDialog.Accepted: return
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل تمدید", "client_renewal.jra", "فایل تمدید (*.jra)")
        if not path: return
        if not path.lower().endswith(".jra"): path += ".jra"
        try:
            self.db.issue_client_renewal(license_uuid, path, dlg.national_code.text(), dlg.valid_from.isoDate(), dlg.valid_until.isoDate(), dlg.warning_days.value())
            QMessageBox.information(self, "تمدید صادر شد", "فایل تمدید با موفقیت ساخته شد.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def edit_license(self, *_args):
        license_uuid = _selected_id(self.licenses_table)
        if not license_uuid:
            QMessageBox.warning(self, "انتخاب فعال‌سازی", "ابتدا یک فعال‌سازی را انتخاب کنید.")
            return
        lic = self.db.get_client_license_details(license_uuid)
        if not lic:
            QMessageBox.warning(self, "فعال‌سازی نامعتبر", "رکورد فعال‌سازی انتخاب‌شده پیدا نشد.")
            self.refresh_all()
            return
        dlg = LicenseEditDialog(self.db, lic, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل فعال‌سازی اصلاح‌شده", "client_activation_updated.jra",
            "فایل فعال‌سازی (*.jra)"
        )
        if not path:
            return
        if not path.lower().endswith(".jra"):
            path += ".jra"
        try:
            payload = self.db.update_client_license(license_uuid, path, **dlg.values())
            self.refresh_all()
            QMessageBox.information(
                self, "فعال‌سازی اصلاح شد",
                f"مشخصات فعال‌سازی «{payload['responsible_full_name']}» اصلاح شد.\n"
                "فایل جدید را روی همان کلاینت نصب کنید."
            )
        except Exception as exc:
            QMessageBox.critical(self, "خطا در اصلاح فعال‌سازی", str(exc))

    def delete_license(self):
        license_uuid = _selected_id(self.licenses_table)
        if not license_uuid:
            QMessageBox.warning(self, "انتخاب فعال‌سازی", "ابتدا یک فعال‌سازی را انتخاب کنید.")
            return
        lic = self.db.get_client_license(license_uuid)
        if not lic:
            QMessageBox.warning(self, "فعال‌سازی نامعتبر", "رکورد فعال‌سازی انتخاب‌شده پیدا نشد.")
            self.refresh_all()
            return
        confirm = QMessageBox.warning(
            self, "حذف فعال‌سازی",
            f"فعال‌سازی «{lic.get('responsible_full_name') or lic.get('username')}» حذف شود؟\n\n"
            "سوابق فایل‌های واردشده و اطلاعات اصلی سامانه حذف نمی‌شوند. "
            "کلاینت مربوطه دیگر امکان ارسال فایل جدید با این مجوز را نخواهد داشت.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db.delete_client_license(license_uuid)
            self.refresh_all()
            QMessageBox.information(self, "حذف انجام شد", "فعال‌سازی انتخاب‌شده حذف شد.")
        except Exception as exc:
            QMessageBox.critical(self, "خطا در حذف فعال‌سازی", str(exc))

    def change_license_status(self):
        license_uuid = _selected_id(self.licenses_table)
        if not license_uuid:
            QMessageBox.warning(self, "انتخاب مجوز", "ابتدا یک مجوز را انتخاب کنید.")
            return
        status = self.license_status.currentText()
        confirm = QMessageBox.question(
            self, "تغییر وضعیت مجوز",
            f"وضعیت مجوز انتخاب‌شده به «{status}» تغییر کند؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db.set_client_license_status(license_uuid, status)
            self.refresh_all()
            QMessageBox.information(self, "وضعیت بروزرسانی شد", f"وضعیت مجوز به «{status}» تغییر یافت.")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def choose_package(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب خروجی کلاینت", "", "فایل کلاینت (*.jrcx *.jrcx.json);;همه فایل‌ها (*.*)")
        if path: self.package_path.setText(path)

    def preview_and_import(self):
        path = self.package_path.text().strip()
        if not path:
            QMessageBox.warning(self, "انتخاب فایل", "ابتدا فایل خروجی کلاینت را انتخاب کنید."); return
        try:
            preview = self.db.preview_client_package(path)
            c = preview["counts"]
            intro = (
                f"فایل مربوط به بلوک «{preview['zone_name']}»، کمیته «{preview['committee_title']}» و مسئول «{preview['responsible_name']}» است.\n"
                f"دوره: {preview['report_period']} | جدید: {c['new']} | اصلاح‌شده: {c['changed']} | تکراری: {c['duplicate']} | تعارض: {c['conflict']}"
            )
            QMessageBox.information(self, "شناسایی فایل", intro)
            dlg = ClientImportPreviewDialog(preview, self)
            if dlg.exec_() != QDialog.Accepted: return
            result = self.db.apply_client_package(preview, dlg.decisions())
            QMessageBox.information(self, "ورود انجام شد", f"{result['accepted']} رکورد پذیرفته و {result['rejected']} رکورد رد شد. اطلاعات در همان بلوک و کمیته بروزرسانی شد.")
            self.package_path.clear(); self.refresh_all(); self.tabs.setCurrentIndex(2)
        except Exception as exc:
            QMessageBox.critical(self, "فایل پذیرفته نشد", str(exc))
