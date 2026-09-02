# -*- coding: utf-8 -*-
"""کارتابل مکاتبات، بایگانی اسناد و پیگیری ارجاعات اداری."""

import os
from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog, QDialogButtonBox, QAbstractItemView, QSplitter,
    QFrame, QTabWidget, QGroupBox
)

from header_widget import build_official_header
from jalali_widgets import JalaliDateEdit
from jalali_utils import convert_dates_in_text, format_jalali
from icon_manager import get_icon, set_button_style
from document_service import generate_correspondence_letter_document


def _make_table(headers, stretch=()):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    for index in range(len(headers)):
        mode = QHeaderView.Stretch if index in stretch else QHeaderView.ResizeToContents
        table.horizontalHeader().setSectionResizeMode(index, mode)
    return table


class LetterDialog(QDialog):
    def __init__(self, db, letter=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.letter = letter or {}
        self.setWindowTitle("ثبت مکاتبه اداری" if not letter else "ویرایش مکاتبه اداری")
        self.resize(650, 650)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.number = QLineEdit(self.letter.get("letter_number") or "")
        self.direction = QComboBox(); self.direction.addItems(db.LETTER_DIRECTIONS)
        self.direction.setCurrentText(self.letter.get("direction") or "وارده")
        self.subject = QLineEdit(self.letter.get("subject") or "")
        self.sender = QLineEdit(self.letter.get("sender") or "")
        self.recipient = QLineEdit(self.letter.get("recipient") or "")
        self.letter_date = JalaliDateEdit(self.letter.get("letter_date"));
        if not self.letter.get("letter_date"): self.letter_date.clear()
        self.received_date = JalaliDateEdit(self.letter.get("received_date"));
        if not self.letter.get("received_date"): self.received_date.clear()
        self.due_date = JalaliDateEdit(self.letter.get("due_date"));
        if not self.letter.get("due_date"): self.due_date.clear()
        self.zone = QComboBox(); self.zone.addItem("بدون بلوک مشخص", None)
        for item in db.get_zones():
            self.zone.addItem(item["name"], item["id"])
        if self.letter.get("zone_id") is not None:
            index = self.zone.findData(self.letter.get("zone_id"))
            if index >= 0: self.zone.setCurrentIndex(index)
        self.status = QComboBox(); self.status.addItems(db.LETTER_STATUSES)
        self.status.setCurrentText(self.letter.get("status") or "ثبت‌شده")
        self.priority = QComboBox(); self.priority.addItems(db.PRIORITY_LEVELS)
        self.priority.setCurrentText(self.letter.get("priority") or "عادی")
        self.confidentiality = QComboBox(); self.confidentiality.addItems(db.CONFIDENTIALITY_LEVELS)
        self.confidentiality.setCurrentText(self.letter.get("confidentiality") or "عادی")
        self.description = QTextEdit(self.letter.get("description") or "")
        self.description.setMinimumHeight(120)

        form.addRow("شماره نامه*:", self.number)
        form.addRow("نوع مکاتبه*:", self.direction)
        form.addRow("موضوع*:", self.subject)
        form.addRow("فرستنده:", self.sender)
        form.addRow("گیرنده:", self.recipient)
        form.addRow("تاریخ نامه:", self.letter_date)
        form.addRow("تاریخ دریافت/ارسال:", self.received_date)
        form.addRow("مهلت پاسخ:", self.due_date)
        form.addRow("بلوک مرتبط:", self.zone)
        form.addRow("وضعیت:", self.status)
        form.addRow("اولویت:", self.priority)
        form.addRow("طبقه‌بندی:", self.confidentiality)
        form.addRow("شرح و توضیحات:", self.description)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره مکاتبه")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self):
        if not self.number.text().strip() or not self.subject.text().strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "شماره و موضوع نامه الزامی هستند.")
            return
        self.accept()

    def values(self):
        return {
            "letter_number": self.number.text().strip(),
            "direction": self.direction.currentText(),
            "subject": self.subject.text().strip(),
            "sender": self.sender.text().strip(),
            "recipient": self.recipient.text().strip(),
            "letter_date": self.letter_date.isoDate() if self.letter_date.text().strip() else None,
            "received_date": self.received_date.isoDate() if self.received_date.text().strip() else None,
            "due_date": self.due_date.isoDate() if self.due_date.text().strip() else None,
            "zone_id": self.zone.currentData(),
            "status": self.status.currentText(),
            "priority": self.priority.currentText(),
            "confidentiality": self.confidentiality.currentText(),
            "description": self.description.toPlainText().strip(),
        }


class AssignmentDialog(QDialog):
    def __init__(self, db, letter, parent=None):
        super().__init__(parent)
        self.db = db
        self.letter = letter
        self.setWindowTitle(f"ارجاع نامه {letter.get('letter_number','')}")
        self.resize(560, 430)
        layout = QVBoxLayout(self)
        info = QLabel(f"<b>{letter.get('subject','')}</b>")
        info.setWordWrap(True)
        layout.addWidget(info)
        form = QFormLayout()
        self.user = QComboBox(); self.user.addItem("گیرنده خارج از کاربران سامانه", None)
        for user in db.list_users(active_only=True):
            self.user.addItem(f"{user['full_name']} — {user['username']}", user["id"])
        self.external_name = QLineEdit()
        self.external_name.setPlaceholderText("نام واحد، مسئول یا دستگاه بیرونی")
        self.instruction = QTextEdit(); self.instruction.setMinimumHeight(110)
        self.due_date = JalaliDateEdit(); self.due_date.clear()
        self.priority = QComboBox(); self.priority.addItems(db.PRIORITY_LEVELS)
        form.addRow("کاربر سامانه:", self.user)
        form.addRow("یا گیرنده بیرونی:", self.external_name)
        form.addRow("دستور اقدام:", self.instruction)
        form.addRow("مهلت انجام:", self.due_date)
        form.addRow("اولویت:", self.priority)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ثبت ارجاع")
        buttons.accepted.connect(self._validate); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self):
        if self.user.currentData() is None and not self.external_name.text().strip():
            QMessageBox.warning(self, "گیرنده مشخص نیست", "یک کاربر یا گیرنده بیرونی انتخاب کنید.")
            return
        self.accept()

    def values(self):
        return {
            "assigned_to_user_id": self.user.currentData(),
            "assigned_to_name": self.external_name.text().strip(),
            "instruction": self.instruction.toPlainText().strip(),
            "due_date": self.due_date.isoDate() if self.due_date.text().strip() else None,
            "priority": self.priority.currentText(),
        }


class AssignmentUpdateDialog(QDialog):
    def __init__(self, db, assignment, parent=None):
        super().__init__(parent)
        self.db = db
        self.assignment = assignment
        self.setWindowTitle("ثبت پاسخ و وضعیت ارجاع")
        self.resize(560, 430)
        layout = QVBoxLayout(self)
        info = QLabel(f"نامه {assignment.get('letter_number','')} — {assignment.get('subject','')}")
        info.setWordWrap(True); layout.addWidget(info)
        form = QFormLayout()
        self.status = QComboBox(); self.status.addItems(db.WORKFLOW_STATUSES)
        self.status.setCurrentText(assignment.get("status") or "ارجاع‌شده")
        self.due_date = JalaliDateEdit(assignment.get("due_date"));
        if not assignment.get("due_date"): self.due_date.clear()
        self.priority = QComboBox(); self.priority.addItems(db.PRIORITY_LEVELS)
        self.priority.setCurrentText(assignment.get("priority") or "عادی")
        self.response = QTextEdit(assignment.get("response_text") or ""); self.response.setMinimumHeight(140)
        form.addRow("وضعیت:", self.status)
        form.addRow("مهلت:", self.due_date)
        form.addRow("اولویت:", self.priority)
        form.addRow("پاسخ / نتیجه اقدام:", self.response)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره پیگیری")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {
            "status": self.status.currentText(),
            "due_date": self.due_date.isoDate() if self.due_date.text().strip() else None,
            "priority": self.priority.currentText(),
            "response_text": self.response.toPlainText().strip(),
        }


class CorrespondenceWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_user = db.get_current_user() or {}
        self.can_manage = self.current_user.get("role") in {"admin", "manager"}
        self.can_respond = self.current_user.get("role") in {"admin", "manager", "field"}
        self.letters = []
        self.assignments = []
        self.notifications = []
        self.attachments = []
        self.setWindowTitle("کارتابل مکاتبات و بایگانی اداری")
        self.resize(1450, 900)
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(build_official_header("کارتابل مکاتبات، بایگانی و پیگیری اداری", self.db))
        toolbar = QFrame(); bar = QHBoxLayout(toolbar); bar.setContentsMargins(18, 8, 18, 8)
        back = QPushButton("بازگشت به داشبورد"); set_button_style(back, "back", "ghost")
        back.clicked.connect(self.back_requested.emit); bar.addWidget(back)
        bar.addSpacing(12)
        new_btn = QPushButton("ثبت نامه جدید"); set_button_style(new_btn, "plus", "success")
        new_btn.clicked.connect(self.new_letter); new_btn.setEnabled(self.can_manage); bar.addWidget(new_btn)
        refresh_btn = QPushButton("بروزرسانی"); set_button_style(refresh_btn, "refresh", "secondary")
        refresh_btn.clicked.connect(self.refresh); bar.addWidget(refresh_btn)
        archive_btn = QPushButton("خروجی بایگانی ZIP"); set_button_style(archive_btn, "download", "primary")
        archive_btn.clicked.connect(self.export_archive); bar.addWidget(archive_btn)
        bar.addStretch()
        self.summary = QLabel("—"); self.summary.setStyleSheet("font-weight:800; color:#13294b;")
        bar.addWidget(self.summary); root.addWidget(toolbar)

        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._build_letters_tab(); self._build_assignments_tab(); self._build_notifications_tab()

    def _build_letters_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(14, 14, 14, 14)
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("شماره نامه، موضوع، فرستنده یا گیرنده...")
        self.search.returnPressed.connect(self.refresh_letters); filters.addWidget(self.search, 1)
        self.zone_filter = QComboBox(); self.zone_filter.addItem("همه بلوک‌ها", None)
        for zone in self.db.get_zones(): self.zone_filter.addItem(zone["name"], zone["id"])
        self.zone_filter.currentIndexChanged.connect(self.refresh_letters); filters.addWidget(self.zone_filter)
        self.direction_filter = QComboBox(); self.direction_filter.addItem("همه انواع", None)
        self.direction_filter.addItems(self.db.LETTER_DIRECTIONS); self.direction_filter.currentIndexChanged.connect(self.refresh_letters)
        filters.addWidget(self.direction_filter)
        self.status_filter = QComboBox(); self.status_filter.addItem("همه وضعیت‌ها", None)
        self.status_filter.addItems(self.db.LETTER_STATUSES); self.status_filter.currentIndexChanged.connect(self.refresh_letters)
        filters.addWidget(self.status_filter)
        find_btn = QPushButton("جستجو"); find_btn.clicked.connect(self.refresh_letters); filters.addWidget(find_btn)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Vertical); layout.addWidget(splitter, 1)
        upper = QWidget(); upper_layout = QVBoxLayout(upper); upper_layout.setContentsMargins(0,0,0,0)
        self.letters_table = _make_table(
            ["شناسه", "شماره", "نوع", "موضوع", "فرستنده", "گیرنده", "بلوک", "مهلت", "وضعیت", "اولویت", "پیوست", "ارجاع باز"],
            stretch=(3,4,5)
        )
        self.letters_table.itemSelectionChanged.connect(self.refresh_attachments)
        self.letters_table.doubleClicked.connect(self.edit_letter)
        upper_layout.addWidget(self.letters_table)
        actions = QHBoxLayout()
        for text, slot, enabled in [
            ("ویرایش نامه", self.edit_letter, self.can_manage),
            ("ارجاع نامه", self.assign_letter, self.can_manage),
            ("افزودن پیوست", self.add_attachment, self.can_manage),
            ("خروجی Word", lambda: self.export_selected_letter("docx"), True),
            ("خروجی PDF", lambda: self.export_selected_letter("pdf"), True),
            ("حذف نامه", self.delete_letter, self.can_manage),
        ]:
            btn = QPushButton(text); btn.clicked.connect(slot); btn.setEnabled(enabled); actions.addWidget(btn)
        actions.addStretch(); upper_layout.addLayout(actions); splitter.addWidget(upper)

        attach_group = QGroupBox("پیوست‌های نامه انتخاب‌شده")
        attach_layout = QVBoxLayout(attach_group)
        self.attachments_table = _make_table(["شناسه", "نام فایل", "نوع", "حجم", "ثبت‌کننده", "تاریخ"], stretch=(1,))
        self.attachments_table.doubleClicked.connect(self.open_attachment)
        attach_layout.addWidget(self.attachments_table)
        attach_actions = QHBoxLayout()
        open_btn = QPushButton("باز کردن فایل"); open_btn.clicked.connect(self.open_attachment); attach_actions.addWidget(open_btn)
        del_btn = QPushButton("حذف پیوست"); del_btn.clicked.connect(self.delete_attachment); del_btn.setEnabled(self.can_manage); attach_actions.addWidget(del_btn)
        attach_actions.addStretch(); attach_layout.addLayout(attach_actions)
        splitter.addWidget(attach_group); splitter.setSizes([600, 230])
        self.tabs.addTab(page, get_icon("report", "navy"), "دفتر مکاتبات")

    def _build_assignments_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(14,14,14,14)
        top = QHBoxLayout()
        self.assignment_scope = QComboBox(); self.assignment_scope.addItem("همه ارجاعات", "all")
        self.assignment_scope.addItem("کارتابل من", "mine")
        self.assignment_scope.currentIndexChanged.connect(self.refresh_assignments); top.addWidget(self.assignment_scope)
        self.assignment_status = QComboBox(); self.assignment_status.addItem("همه وضعیت‌ها", None)
        self.assignment_status.addItems(self.db.WORKFLOW_STATUSES)
        self.assignment_status.currentIndexChanged.connect(self.refresh_assignments); top.addWidget(self.assignment_status)
        top.addStretch(); layout.addLayout(top)
        self.assignments_table = _make_table(
            ["شناسه", "شماره نامه", "موضوع", "بلوک", "ارجاع به", "دستور", "مهلت", "اولویت", "وضعیت", "پاسخ"],
            stretch=(2,5,9)
        )
        self.assignments_table.doubleClicked.connect(self.update_assignment)
        layout.addWidget(self.assignments_table, 1)
        actions = QHBoxLayout()
        update_btn = QPushButton("ثبت پاسخ / تغییر وضعیت"); update_btn.clicked.connect(self.update_assignment)
        update_btn.setEnabled(self.can_respond); actions.addWidget(update_btn); actions.addStretch(); layout.addLayout(actions)
        self.tabs.addTab(page, get_icon("list", "navy"), "کارتابل ارجاعات")

    def _build_notifications_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(14,14,14,14)
        info = QLabel("اعلان‌ها بر اساس مهلت پاسخ نامه و مهلت ارجاعات، به‌صورت خودکار ایجاد می‌شوند.")
        info.setWordWrap(True); layout.addWidget(info)
        self.notifications_table = _make_table(
            ["شدت", "نوع", "عنوان", "شرح", "بلوک", "سررسید", "روز باقی‌مانده"], stretch=(2,3)
        )
        layout.addWidget(self.notifications_table, 1)
        actions = QHBoxLayout()
        ack = QPushButton("ثبت رسیدگی به اعلان"); ack.clicked.connect(self.ack_notification); ack.setEnabled(self.can_respond)
        actions.addWidget(ack); actions.addStretch(); layout.addLayout(actions)
        self.tabs.addTab(page, get_icon("warning", "navy"), "هشدارها و سررسیدها")

    def _selected_letter(self):
        row = self.letters_table.currentRow()
        return self.letters[row] if 0 <= row < len(self.letters) else None

    def _selected_assignment(self):
        row = self.assignments_table.currentRow()
        return self.assignments[row] if 0 <= row < len(self.assignments) else None

    def export_selected_letter(self, extension):
        letter = self._selected_letter()
        if not letter:
            QMessageBox.information(self, "انتخاب نامه", "ابتدا یک نامه را انتخاب کنید.")
            return
        suffix = ".pdf" if extension == "pdf" else ".docx"
        filter_text = "PDF (*.pdf)" if extension == "pdf" else "Word (*.docx)"
        safe_number = str(letter.get("letter_number") or letter.get("id")).replace("/", "-").replace("\\", "-")
        default_name = f"letter_{safe_number}{suffix}"
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره نامه رسمی", default_name, filter_text)
        if not path:
            return
        if not path.lower().endswith(suffix):
            path += suffix
        try:
            result = generate_correspondence_letter_document(self.db, letter["id"], path)
            QMessageBox.information(
                self, "خروجی آماده شد",
                f"فایل ذخیره شد:\n{result['path']}\n\nکد اعتبارسنجی QR: {result['verification_token']}"
            )
        except Exception as exc:
            QMessageBox.warning(self, "خطا", str(exc))

    def refresh(self):
        self.refresh_letters(); self.refresh_assignments(); self.refresh_notifications()
        stats = self.db.get_correspondence_stats()
        self.summary.setText(
            f"کل نامه‌ها: {stats['letters_total']} | ارجاع باز: {stats['open_assignments']} | هشدار: {stats['administrative_alerts']}"
        )

    def refresh_letters(self):
        if not hasattr(self, "letters_table"): return
        self.letters = self.db.get_correspondence_letters(
            zone_id=self.zone_filter.currentData(), direction=self.direction_filter.currentData(),
            status=self.status_filter.currentData(), query=self.search.text().strip() or None,
        )
        self.letters_table.setRowCount(len(self.letters))
        for r, item in enumerate(self.letters):
            values = [item["id"], item["letter_number"], item["direction"], item["subject"], item["sender"],
                      item["recipient"], item["zone_name"] or "—", item["due_date"] or "—", item["status"],
                      item["priority"], item["attachment_count"], item["open_assignment_count"]]
            for c, value in enumerate(values):
                self.letters_table.setItem(r, c, QTableWidgetItem(convert_dates_in_text(str(value or ""))))
        if self.letters: self.letters_table.selectRow(0)
        else: self.attachments_table.setRowCount(0)

    def refresh_attachments(self):
        letter = self._selected_letter()
        self.attachments = self.db.get_document_attachments("letter", letter["id"]) if letter else []
        self.attachments_table.setRowCount(len(self.attachments))
        for r, item in enumerate(self.attachments):
            size_kb = round((item.get("file_size") or 0) / 1024, 1)
            values = [item["id"], item["original_name"], item["mime_type"], f"{size_kb} KB",
                      item.get("created_by_name") or "سیستم", item["created_at"]]
            for c, value in enumerate(values): self.attachments_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(value or ""))))
        if self.attachments: self.attachments_table.selectRow(0)

    def refresh_assignments(self):
        if not hasattr(self, "assignments_table"): return
        assignee = self.current_user.get("id") if self.assignment_scope.currentData() == "mine" else None
        self.assignments = self.db.get_workflow_assignments(
            assigned_to_user_id=assignee, status=self.assignment_status.currentData()
        )
        self.assignments_table.setRowCount(len(self.assignments))
        for r, item in enumerate(self.assignments):
            values = [item["id"], item["letter_number"], item["subject"], item["zone_name"] or "—",
                      item["assigned_to_name"], item["instruction"], item["due_date"] or "—", item["priority"],
                      item["status"], item["response_text"] or ""]
            for c, value in enumerate(values): self.assignments_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(value or ""))))
        if self.assignments: self.assignments_table.selectRow(0)

    def refresh_notifications(self):
        if not hasattr(self, "notifications_table"): return
        self.notifications = self.db.get_administrative_notifications()
        zone_names = {z["id"]: z["name"] for z in self.db.get_zones()}
        self.notifications_table.setRowCount(len(self.notifications))
        for r, item in enumerate(self.notifications):
            values = [item["severity"], item["type"], item["title"], item["message"],
                      zone_names.get(item.get("zone_id"), "—"), item["due_date"], item["days_remaining"]]
            for c, value in enumerate(values): self.notifications_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(value or ""))))
        if self.notifications: self.notifications_table.selectRow(0)

    def new_letter(self):
        dialog = LetterDialog(self.db, parent=self)
        if dialog.exec_() != QDialog.Accepted: return
        try:
            self.db.add_correspondence_letter(**dialog.values()); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def edit_letter(self):
        item = self._selected_letter()
        if not item or not self.can_manage: return
        full = self.db.get_correspondence_letter(item["id"])
        dialog = LetterDialog(self.db, full, self)
        if dialog.exec_() != QDialog.Accepted: return
        try:
            self.db.update_correspondence_letter(item["id"], **dialog.values()); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def delete_letter(self):
        item = self._selected_letter()
        if not item or not self.can_manage: return
        if QMessageBox.question(self, "حذف نامه", "نامه و همه ارجاعات و پیوست‌های آن حذف شوند؟",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        self.db.delete_correspondence_letter(item["id"]); self.refresh()

    def assign_letter(self):
        item = self._selected_letter()
        if not item or not self.can_manage: return
        dialog = AssignmentDialog(self.db, item, self)
        if dialog.exec_() != QDialog.Accepted: return
        try:
            self.db.add_workflow_assignment(item["id"], **dialog.values()); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def add_attachment(self):
        item = self._selected_letter()
        if not item or not self.can_manage: return
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل پیوست")
        if not path: return
        try:
            self.db.archive_document_attachment("letter", item["id"], path); self.refresh_attachments(); self.refresh_letters()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def open_attachment(self):
        row = self.attachments_table.currentRow()
        if row < 0 or row >= len(self.attachments): return
        path = self.attachments[row].get("stored_path")
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "فایل پیدا نشد", "فایل بایگانی‌شده در مسیر ثبت‌شده وجود ندارد.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def delete_attachment(self):
        row = self.attachments_table.currentRow()
        if row < 0 or row >= len(self.attachments) or not self.can_manage: return
        if QMessageBox.question(self, "حذف پیوست", "فایل بایگانی‌شده حذف شود؟",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
        self.db.delete_document_attachment(self.attachments[row]["id"]); self.refresh_attachments(); self.refresh_letters()

    def update_assignment(self):
        item = self._selected_assignment()
        if not item or not self.can_respond: return
        dialog = AssignmentUpdateDialog(self.db, item, self)
        if dialog.exec_() != QDialog.Accepted: return
        try:
            self.db.update_workflow_assignment(item["id"], **dialog.values()); self.refresh()
        except Exception as exc: QMessageBox.critical(self, "خطا", str(exc))

    def export_archive(self):
        zone_id = self.zone_filter.currentData() if hasattr(self, "zone_filter") else None
        default_name = "correspondence_archive.zip" if zone_id is None else f"correspondence_zone_{zone_id}.zip"
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره بایگانی مکاتبات", default_name, "ZIP Files (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            result = self.db.export_correspondence_archive(path, zone_id=zone_id)
            QMessageBox.information(
                self, "بایگانی ساخته شد",
                f"{result['letters']} نامه و {result['files']} فایل پیوست در بسته ذخیره شد."
            )
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def ack_notification(self):
        row = self.notifications_table.currentRow()
        if row < 0 or row >= len(self.notifications) or not self.can_respond: return
        self.db.acknowledge_administrative_notification(self.notifications[row]["key"])
        self.refresh_notifications(); self.refresh()
