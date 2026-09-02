# -*- coding: utf-8 -*-
"""تنظیم صورتجلسه A4، مصوبات، امضای لمسی اعضای کمیته و خروجی PDF."""

from __future__ import annotations

import os

from PyQt5.QtCore import Qt, QBuffer, QByteArray, QIODevice, QPointF, QEvent, QTime, QUrl, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QPen, QColor, QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog, QTabWidget,
    QTimeEdit, QFrame, QCompleter
)

from jalali_widgets import JalaliDateEdit, JalaliCalendarWidget
from jalali_utils import iso_to_jalali, to_persian_digits, to_latin_digits
from committee_report_utils import member_display_role
from runtime_paths import get_reports_dir
from committee_minutes_pdf import generate_committee_minutes_pdf



def _safe_name(value):
    value = str(value or "").strip() or "بدون_شماره"
    for ch in '\\/:*?"<>|':
        value = value.replace(ch, "-")
    return value


class ClickableJalaliDateEdit(JalaliDateEdit):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class ClickableLineEdit(QLineEdit):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()


class JalaliPickerField(QWidget):
    """فیلد تاریخ شمسی آماده با بازشدن تقویم توسط کلیک."""

    def __init__(self, value=None, parent=None, allow_empty=False, dialog_title="انتخاب تاریخ"):
        super().__init__(parent)
        self.allow_empty = allow_empty
        self.dialog_title = dialog_title
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.edit = ClickableJalaliDateEdit(value)
        self.edit.setReadOnly(True)
        self.edit.setCursor(Qt.PointingHandCursor)
        self.edit.setToolTip("برای انتخاب تاریخ کلیک کنید")
        if allow_empty and not value:
            self.edit.clear()
        self.button = QPushButton("انتخاب")
        self.button.setFixedWidth(62)
        self.button.clicked.connect(self.open_picker)
        self.edit.clicked.connect(self.open_picker)
        row.addWidget(self.edit, 1)
        row.addWidget(self.button)

    def open_picker(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.dialog_title)
        dialog.resize(430, 380)
        layout = QVBoxLayout(dialog)
        calendar = JalaliCalendarWidget(dialog)
        qdate = self.edit.date()
        if qdate.isValid():
            calendar.setSelectedDate(qdate)
        layout.addWidget(calendar)
        if self.allow_empty:
            clear_button = QPushButton("پاک کردن تاریخ")
            clear_button.clicked.connect(lambda: (self.edit.clear(), dialog.reject()))
            layout.addWidget(clear_button)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        calendar.clicked.connect(lambda _d: dialog.accept())
        layout.addWidget(buttons)
        if dialog.exec_() == QDialog.Accepted:
            self.edit.setDate(calendar.selectedDate())

    def isoDate(self):
        if not self.edit.text().strip() and self.allow_empty:
            return None
        return self.edit.isoDate()

    def setIsoDate(self, value):
        if value:
            self.edit.setText(iso_to_jalali(value))
        elif self.allow_empty:
            self.edit.clear()

    def text(self):
        return self.edit.text().strip()


class TimePickerField(QWidget):
    """فیلد ساعت آماده که با کلیک، پنجره انتخاب ساعت را باز می‌کند."""

    def __init__(self, value=None, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.edit = ClickableLineEdit(self)
        self.edit.setReadOnly(True)
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.setText(self._normalize(value) or QTime.currentTime().toString("HH:mm"))
        self.edit.clicked.connect(self.open_picker)
        self.button = QPushButton("انتخاب")
        self.button.setFixedWidth(62)
        self.button.clicked.connect(self.open_picker)
        row.addWidget(self.edit, 1)
        row.addWidget(self.button)

    @staticmethod
    def _normalize(value):
        parsed = QTime.fromString(str(value or ""), "HH:mm")
        return parsed.toString("HH:mm") if parsed.isValid() else ""

    def open_picker(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("انتخاب ساعت جلسه")
        dialog.resize(320, 150)
        layout = QVBoxLayout(dialog)
        picker = QTimeEdit(dialog)
        picker.setDisplayFormat("HH:mm")
        picker.setAlignment(Qt.AlignCenter)
        picker.setMinimumHeight(45)
        current = QTime.fromString(self.edit.text(), "HH:mm")
        picker.setTime(current if current.isValid() else QTime.currentTime())
        layout.addWidget(picker)
        now_button = QPushButton("ساعت فعلی")
        now_button.clicked.connect(lambda: picker.setTime(QTime.currentTime()))
        layout.addWidget(now_button)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() == QDialog.Accepted:
            self.edit.setText(picker.time().toString("HH:mm"))

    def text(self):
        return self.edit.text().strip()

    def setText(self, value):
        normalized = self._normalize(value)
        if normalized:
            self.edit.setText(normalized)


class SignaturePad(QWidget):
    """صفحه امضا با پشتیبانی قلم، ماوس و لمس صفحه."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 82)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.setCursor(Qt.CrossCursor)
        self._image = QImage(900, 300, QImage.Format_ARGB32)
        self._image.fill(QColor("white"))
        self._last = None
        self._drawing = False
        self._has_ink = False

    def _map_point(self, pos):
        width = max(1, self.width())
        height = max(1, self.height())
        return QPointF(pos.x() * self._image.width() / width, pos.y() * self._image.height() / height)

    def _start(self, pos):
        self._drawing = True
        self._last = self._map_point(pos)

    def _move(self, pos):
        if not self._drawing or self._last is None:
            return
        point = self._map_point(pos)
        painter = QPainter(self._image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(QColor("#111111"), 8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(self._last, point)
        painter.end()
        self._last = point
        self._has_ink = True
        self.update()
        self.changed.emit()

    def _end(self):
        self._drawing = False
        self._last = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start(event.localPos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._move(event.localPos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._end()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def event(self, event):
        if event.type() in (QEvent.TouchBegin, QEvent.TouchUpdate, QEvent.TouchEnd):
            points = event.touchPoints()
            if points:
                point = points[0]
                if event.type() == QEvent.TouchBegin:
                    self._start(point.pos())
                elif event.type() == QEvent.TouchUpdate:
                    self._move(point.pos())
                else:
                    self._end()
            event.accept()
            return True
        return super().event(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.drawImage(self.rect(), self._image)
        painter.setPen(QPen(QColor("#9aa7b5"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def clear(self):
        self._image.fill(QColor("white"))
        self._has_ink = False
        self.update()
        self.changed.emit()

    def load_png(self, data):
        if not data:
            self.clear()
            return
        image = QImage.fromData(bytes(data), "PNG")
        if image.isNull():
            self.clear()
            return
        self._image.fill(QColor("white"))
        painter = QPainter(self._image)
        painter.drawImage(self._image.rect(), image)
        painter.end()
        self._has_ink = True
        self.update()

    def png_bytes(self):
        if not self._has_ink:
            return None
        array = QByteArray()
        buffer = QBuffer(array)
        buffer.open(QIODevice.WriteOnly)
        self._image.save(buffer, "PNG")
        buffer.close()
        return bytes(array)


class SignatureCell(QWidget):
    def __init__(self, signature=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.pad = SignaturePad(self)
        clear_button = QPushButton("پاک کردن امضا")
        clear_button.setMaximumHeight(25)
        clear_button.clicked.connect(self.pad.clear)
        layout.addWidget(self.pad)
        layout.addWidget(clear_button, 0, Qt.AlignLeft)
        if signature:
            self.pad.load_png(signature)


class ResolutionRow:
    """یک ردیف مصوبه با ظاهر همسان با فرم کلاینت."""

    def __init__(self, table, row, agencies, item=None, remove_callback=None):
        self.table = table
        self.row = row
        self.item = item or {}

        number_item = QTableWidgetItem(to_persian_digits(row + 1))
        number_item.setTextAlignment(Qt.AlignCenter)
        number_item.setData(Qt.UserRole, self.item.get("id"))
        number_item.setFlags(number_item.flags() & ~Qt.ItemIsEditable)
        table.setItem(row, 0, number_item)

        self.description = QTextEdit(self.item.get("description") or self.item.get("title") or "")
        self.description.setObjectName("ResolutionDescriptionInput")
        self.description.setAcceptRichText(False)
        self.description.setMinimumHeight(64)
        self.description.setMaximumHeight(88)
        self.description.setPlaceholderText("شرح مصوبه")
        table.setCellWidget(row, 1, self.description)

        # در کلاینت این بخش یک ورودی متنی ساده است. برای حفظ فهرست ادارات،
        # همان ظاهر با تکمیل خودکار ارائه می‌شود.
        self.agency = QLineEdit(self.item.get("responsible_agency") or "")
        self.agency.setObjectName("ResolutionAgencyInput")
        self.agency.setPlaceholderText("اداره پیگیری‌کننده")
        agency_names = [str(name).strip() for name in agencies if str(name or "").strip()]
        if agency_names:
            completer = QCompleter(agency_names, self.agency)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.agency.setCompleter(completer)
        table.setCellWidget(row, 2, self.agency)

        self.due = JalaliPickerField(
            self.item.get("due_date"), allow_empty=True, dialog_title="انتخاب مهلت انجام"
        )
        self.due.setObjectName("ResolutionDueDateField")
        self.due.edit.setObjectName("ResolutionDueDateInput")
        self.due.edit.setAlignment(Qt.AlignCenter)
        self.due.edit.setPlaceholderText("۱۴۰۵/۰۵/۱۵")
        # مانند کلاینت، کل فیلد تاریخ با لمس/کلیک باز می‌شود و دکمه جداگانه ندارد.
        self.due.button.setVisible(False)
        table.setCellWidget(row, 3, self.due)

        self.remove_button = QPushButton("×")
        self.remove_button.setObjectName("ResolutionRemoveButton")
        self.remove_button.setToolTip("حذف ردیف مصوبه")
        self.remove_button.setFixedSize(34, 34)
        if remove_callback:
            self.remove_button.clicked.connect(lambda: remove_callback(self))
        table.setCellWidget(row, 4, self.remove_button)
        table.setRowHeight(row, 76)

    def values(self):
        description = self.description.toPlainText().strip()
        title = description.splitlines()[0][:120].strip() if description else ""
        return {
            "id": self.item.get("id"),
            "title": title,
            "description": description,
            "responsible_agency": self.agency.text().strip(),
            "responsible_person": self.item.get("responsible_person"),
            "due_date": self.due.isoDate(),
            "status": self.item.get("status") or "در انتظار اقدام",
            "linked_issue_id": self.item.get("linked_issue_id"),
            "linked_action_id": self.item.get("linked_action_id"),
        }


class CommitteeMinutesDialog(QDialog):
    """ویرایشگر کامل صورتجلسه و دو برگ مستقل A4."""

    saved = pyqtSignal(int)

    def __init__(self, db, committee_id, zone_id, meeting_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.committee_id = int(committee_id)
        self.zone_id = int(zone_id)
        self.meeting_id = int(meeting_id) if meeting_id else None
        self.committee = self.db.get_committee(self.committee_id) or {}
        self._resolution_rows = []
        self._signature_cells = {}
        self.setWindowTitle("تنظیم صورتجلسه، مصوبات و امضای اعضای کمیته")
        self.resize(1180, 820)
        self.setLayoutDirection(Qt.RightToLeft)
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel(f"تنظیم صورتجلسه A4 - {self.committee.get('title') or 'کمیته'}")
        title.setStyleSheet("font-size:17px;font-weight:900;color:#102f5c;padding:6px;")
        root.addWidget(title)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_minutes_tab()
        self._build_signatures_tab()

        buttons = QHBoxLayout()
        self.save_button = QPushButton("ذخیره صورتجلسه و امضاها")
        self.save_button.clicked.connect(self.save_all)
        self.minutes_pdf_button = QPushButton("PDF برگ صورتجلسه")
        self.minutes_pdf_button.clicked.connect(lambda: self.export_pdf("minutes"))
        self.signatures_pdf_button = QPushButton("PDF برگ امضاها")
        self.signatures_pdf_button.clicked.connect(lambda: self.export_pdf("signatures"))
        self.combined_pdf_button = QPushButton("PDF کامل دو برگ")
        self.combined_pdf_button.clicked.connect(lambda: self.export_pdf("combined"))
        close_button = QPushButton("بستن")
        close_button.clicked.connect(self.accept)
        for button in (self.save_button, self.minutes_pdf_button, self.signatures_pdf_button, self.combined_pdf_button):
            button.setMinimumHeight(38)
        self.save_button.setStyleSheet("background:#102f5c;color:white;font-weight:800;border-radius:7px;padding:8px 16px;")
        self.combined_pdf_button.setStyleSheet("background:#c99b39;color:#102f5c;font-weight:900;border-radius:7px;padding:8px 16px;")
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.minutes_pdf_button)
        buttons.addWidget(self.signatures_pdf_button)
        buttons.addWidget(self.combined_pdf_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        root.addLayout(buttons)

    def _build_minutes_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)

        meta_frame = QFrame()
        meta_frame.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #d7e0ea;border-radius:8px;}")
        form = QFormLayout(meta_frame)
        form.setContentsMargins(12, 12, 12, 12)
        self.meeting_number = QLineEdit()
        self.meeting_number.setPlaceholderText("شماره خودکار")
        self.meeting_number.setAlignment(Qt.AlignCenter)
        self.meeting_number.setReadOnly(True)
        self.meeting_number.setToolTip("شماره جلسه به‌صورت خودکار تعیین می‌شود")
        self.meeting_date = JalaliPickerField(dialog_title="انتخاب تاریخ جلسه")
        self.meeting_time = TimePickerField()
        self.resolution_count = QLineEdit("۰")
        self.resolution_count.setReadOnly(True)
        self.resolution_count.setAlignment(Qt.AlignCenter)
        self.discussion = QTextEdit()
        self.discussion.setMinimumHeight(125)
        form.addRow("شماره جلسه:", self.meeting_number)
        form.addRow("تاریخ جلسه:", self.meeting_date)
        form.addRow("ساعت جلسه:", self.meeting_time)
        form.addRow("تعداد مصوبات:", self.resolution_count)
        form.addRow("شرح مذاکرات:", self.discussion)
        layout.addWidget(meta_frame)

        toolbar = QHBoxLayout()
        heading = QLabel("مصوبات")
        heading.setStyleSheet("font-size:15px;font-weight:900;color:#102f5c;")
        toolbar.addWidget(heading)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.resolutions_table = QTableWidget(0, 5)
        self.resolutions_table.setObjectName("ResolutionsEditorTable")
        self.resolutions_table.setLayoutDirection(Qt.RightToLeft)
        self.resolutions_table.setHorizontalHeaderLabels([
            "ردیف", "شرح مصوبات", "اداره پیگیری‌کننده", "مهلت انجام", "حذف"
        ])
        header = self.resolutions_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignCenter)
        header.setMinimumHeight(44)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.resolutions_table.setColumnWidth(0, 58)
        self.resolutions_table.setColumnWidth(2, 240)
        self.resolutions_table.setColumnWidth(3, 190)
        self.resolutions_table.setColumnWidth(4, 70)
        self.resolutions_table.verticalHeader().setVisible(False)
        self.resolutions_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.resolutions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.resolutions_table.setAlternatingRowColors(False)
        self.resolutions_table.setShowGrid(True)
        self.resolutions_table.setWordWrap(True)
        self.resolutions_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.resolutions_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.resolutions_table.setMinimumHeight(275)
        self.resolutions_table.setStyleSheet("""
            QTableWidget#ResolutionsEditorTable {
                background: #ffffff;
                color: #111111;
                border: 1px solid #cbd5e1;
                border-radius: 7px;
                gridline-color: #cbd5e1;
                selection-background-color: #ffffff;
            }
            QTableWidget#ResolutionsEditorTable::item {
                background: #ffffff;
                color: #111111;
                padding: 4px;
                border: 0;
            }
            QTableWidget#ResolutionsEditorTable QHeaderView::section {
                background: #123865;
                color: #ffffff;
                border: 0;
                border-left: 1px solid #d6b04d;
                padding: 8px 5px;
                font-weight: 800;
            }
            QTableWidget#ResolutionsEditorTable QTextEdit#ResolutionDescriptionInput,
            QTableWidget#ResolutionsEditorTable QLineEdit#ResolutionAgencyInput,
            QTableWidget#ResolutionsEditorTable QLineEdit#ResolutionDueDateInput {
                background: #ffffff;
                color: #111111;
                border: 0;
                border-radius: 0;
                padding: 7px;
                selection-background-color: #dbeafe;
                selection-color: #111111;
            }
            QTableWidget#ResolutionsEditorTable QTextEdit#ResolutionDescriptionInput:focus,
            QTableWidget#ResolutionsEditorTable QLineEdit#ResolutionAgencyInput:focus,
            QTableWidget#ResolutionsEditorTable QLineEdit#ResolutionDueDateInput:focus {
                border: 2px solid #c9a227;
            }
            QTableWidget#ResolutionsEditorTable QPushButton#ResolutionRemoveButton {
                background: #ffffff;
                color: #a4262c;
                border: 1px solid #efc4c7;
                border-radius: 17px;
                font-size: 20px;
                font-weight: 900;
                padding: 0;
            }
            QTableWidget#ResolutionsEditorTable QPushButton#ResolutionRemoveButton:hover {
                background: #fff1f2;
                border-color: #c9303a;
            }
        """)
        layout.addWidget(self.resolutions_table, 1)

        add_row_layout = QHBoxLayout()
        add_row_button = QPushButton("＋ افزودن ردیف مصوبه")
        add_row_button.setObjectName("AddResolutionRowButton")
        add_row_button.setMinimumHeight(36)
        add_row_button.setStyleSheet(
            "QPushButton{background:#1f9d55;color:white;border:0;border-radius:7px;"
            "padding:7px 15px;font-weight:800;}"
            "QPushButton:hover{background:#168347;}"
        )
        add_row_button.clicked.connect(lambda: self.add_resolution_row())
        add_row_layout.addWidget(add_row_button)
        add_row_layout.addStretch()
        layout.addLayout(add_row_layout)
        self.tabs.addTab(page, "صورتجلسه و مصوبات")

    def _build_signatures_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel("فهرست اعضا از دیتابیس همین کمیته خوانده می‌شود. امضا با لمس صفحه، قلم یا ماوس ثبت می‌شود.")
        note.setWordWrap(True)
        note.setStyleSheet("background:#eef5fb;color:#17345f;border:1px solid #cddce9;border-radius:7px;padding:9px;font-weight:700;")
        layout.addWidget(note)
        self.signature_table = QTableWidget(0, 5)
        self.signature_table.setLayoutDirection(Qt.RightToLeft)
        self.signature_table.setHorizontalHeaderLabels([
            "ردیف", "نام و نام خانوادگی", "سمت", "عضو", "محل امضا"
        ])
        self.signature_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.signature_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.signature_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.signature_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.signature_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.signature_table.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.signature_table, 1)
        self.tabs.addTab(page, "فهرست اعضا و امضا")

    def _load(self):
        meeting = self.db.get_committee_meeting(self.meeting_id) if self.meeting_id else None
        if meeting:
            number = meeting.get("meeting_number") or meeting.get("title") or ""
            number = str(number).replace("صورتجلسه شماره", "").replace("جلسه شماره", "").strip()
            self.meeting_number.setText(to_persian_digits(number))
            self.meeting_date.setIsoDate(meeting.get("meeting_date"))
            self.meeting_time.setText(meeting.get("start_time"))
            self.discussion.setPlainText(meeting.get("minutes_text") or "")
            resolutions = self.db.get_committee_meeting_resolutions(self.meeting_id)
        else:
            self.meeting_number.setText(to_persian_digits(self.db.next_committee_meeting_number(self.committee_id)))
            resolutions = []
        for item in resolutions:
            self.add_resolution_row(item)
        if not resolutions:
            self.add_resolution_row()
        self._load_signatures()
        self._update_resolution_count()

    def _load_signatures(self):
        members = self.db.get_committee_members(self.committee_id)
        members = [m for m in members if (m.get("status") or "فعال") == "فعال"] or members
        signatures = {}
        if self.meeting_id:
            signatures = {x["member_id"]: x.get("signature_png") for x in self.db.get_committee_meeting_signatures(self.meeting_id)}
        self.signature_table.setRowCount(0)
        self._signature_cells = {}
        for row, member in enumerate(members):
            self.signature_table.insertRow(row)
            self.signature_table.setRowHeight(row, 118)
            values = [
                to_persian_digits(row + 1),
                member.get("person_name") or "—",
                member_display_role(member),
                member.get("member_type") or "عضو",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignCenter if column in (0, 3) else Qt.AlignRight | Qt.AlignVCenter)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.signature_table.setItem(row, column, item)
            cell = SignatureCell(signatures.get(member["id"]))
            self.signature_table.setCellWidget(row, 4, cell)
            self._signature_cells[member["id"]] = cell

    def _agency_names(self):
        return [x.get("name") for x in self.db.get_management_agencies(active_only=False) if x.get("name")]

    def add_resolution_row(self, item=None):
        row = self.resolutions_table.rowCount()
        self.resolutions_table.insertRow(row)
        holder = ResolutionRow(self.resolutions_table, row, self._agency_names(), item, self.remove_resolution_row)
        holder.description.textChanged.connect(self._update_resolution_count)
        self._resolution_rows.append(holder)
        self._renumber_resolutions()

    def remove_resolution_row(self, holder):
        if holder not in self._resolution_rows:
            return
        row = self._resolution_rows.index(holder)
        self.resolutions_table.removeRow(row)
        self._resolution_rows.remove(holder)
        self._renumber_resolutions()

    def _renumber_resolutions(self):
        for row, holder in enumerate(self._resolution_rows):
            holder.row = row
            item = self.resolutions_table.item(row, 0)
            if item:
                item.setText(to_persian_digits(row + 1))
        self._update_resolution_count()

    def _valid_resolutions(self):
        return [item for item in (row.values() for row in self._resolution_rows) if item.get("description")]

    def _update_resolution_count(self):
        self.resolution_count.setText(to_persian_digits(len(self._valid_resolutions())))

    def _collect_signatures(self):
        return {member_id: cell.pad.png_bytes() for member_id, cell in self._signature_cells.items()}

    def save_all(self, quiet=False):
        try:
            if not self.meeting_id:
                number = self.db.next_committee_meeting_number(self.committee_id)
                self.meeting_number.setText(to_persian_digits(number))
            else:
                number = to_latin_digits(self.meeting_number.text()).strip()
            if not number:
                raise ValueError("شماره جلسه به‌صورت خودکار تعیین نشد.")
            meeting_date = self.meeting_date.isoDate()
            title = f"صورتجلسه شماره {number}"
            data = {
                "title": title,
                "meeting_number": number,
                "meeting_date": meeting_date,
                "start_time": self.meeting_time.text(),
                "place_name": "",
                "agenda": "",
                "attendees": "",
                "minutes_text": self.discussion.toPlainText().strip(),
                "status": "برگزارش‌شده",
            }
            if self.meeting_id:
                self.db.update_committee_meeting(self.meeting_id, **data)
            else:
                self.meeting_id = self.db.add_committee_meeting(
                    self.committee_id, self.zone_id, title, **{k: v for k, v in data.items() if k != "title"}
                )
            self.db.save_committee_meeting_resolutions(
                self.meeting_id, self.committee_id, self.zone_id, self._valid_resolutions()
            )
            self.db.save_committee_meeting_signatures(self.meeting_id, self._collect_signatures())
            self.saved.emit(self.meeting_id)
            self._update_resolution_count()
            if not quiet:
                QMessageBox.information(self, "ذخیره شد", "صورتجلسه، مصوبات و امضاها با موفقیت ذخیره شد.")
            return True
        except Exception as exc:
            QMessageBox.critical(self, "خطا در ذخیره", str(exc))
            return False

    def _pdf_data(self):
        meeting = self.db.get_committee_meeting(self.meeting_id)
        resolutions = self.db.get_committee_meeting_resolutions(self.meeting_id)
        members = self.db.get_committee_members(self.committee_id)
        members = [m for m in members if (m.get("status") or "فعال") == "فعال"] or members
        signatures = {x["member_id"]: x.get("signature_png") for x in self.db.get_committee_meeting_signatures(self.meeting_id)}
        return meeting, resolutions, members, signatures

    def export_pdf(self, mode):
        if not self.save_all(quiet=True):
            return
        meeting, resolutions, members, signatures = self._pdf_data()
        number = meeting.get("meeting_number") or meeting.get("id")
        suffix = {"minutes": "صورتجلسه", "signatures": "امضاها", "combined": "صورتجلسه_و_امضاها"}[mode]
        default_path = os.path.join(get_reports_dir(), f"{suffix}_{_safe_name(number)}.pdf")
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل PDF", default_path, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            generate_committee_minutes_pdf(
                path,
                self.committee,
                meeting,
                resolutions,
                members,
                signatures,
                include_minutes=mode in ("minutes", "combined"),
                include_signatures=mode in ("signatures", "combined"),
            )
            # پس از ذخیره، PDF بلافاصله با نمایشگر پیش‌فرض سیستم باز می‌شود.
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))
            if not opened:
                QMessageBox.warning(
                    self,
                    "PDF ذخیره شد",
                    f"فایل ذخیره شد اما نمایش خودکار آن توسط سیستم‌عامل انجام نشد:\n{path}",
                )
        except Exception as exc:
            QMessageBox.critical(self, "خطا در ساخت PDF", str(exc))
