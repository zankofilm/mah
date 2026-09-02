# -*- coding: utf-8 -*-
"""تقویم مدیریتی، اعلان‌های داخل برنامه و گزارش دوره‌ای نسخه ۶.۶."""

from datetime import datetime, timedelta

from PyQt5.QtCore import Qt, pyqtSignal, QDate, QTime
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QLineEdit, QTextEdit,
    QMessageBox, QFileDialog, QCalendarWidget, QSplitter, QDateEdit, QTimeEdit,
    QCheckBox, QSpinBox, QGroupBox, QTextBrowser, QFrame
)

from header_widget import build_official_header
from jalali_widgets import JalaliDateEdit, JalaliCalendarWidget
from jalali_utils import format_jalali, convert_dates_in_text, iso_to_jalali, jalali_to_iso, today_jalali
QDateEdit = JalaliDateEdit
from icon_manager import set_button_style


SEVERITY_COLORS = {
    "بحرانی": QColor("#ffd7d7"),
    "فوری": QColor("#ffe5c2"),
    "مهم": QColor("#fff5c4"),
    "اطلاع": QColor("#eaf2ff"),
}


def _table(headers, stretch=()):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    for index in range(len(headers)):
        table.horizontalHeader().setSectionResizeMode(
            index, QHeaderView.Stretch if index in stretch else QHeaderView.ResizeToContents
        )
    return table


def _qdate(value=None):
    if value:
        parsed = QDate.fromString(str(value)[:10], "yyyy-MM-dd")
        if parsed.isValid():
            return parsed
    return QDate.currentDate()


class CalendarEventDialog(QDialog):
    def __init__(self, db, event=None, selected_date=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.event = event or {}
        self.setWindowTitle("رویداد تقویم مدیریتی")
        self.resize(620, 600)
        layout = QVBoxLayout(self)
        info = QLabel("رویداد، جلسه، بازدید یا پیگیری برنامه‌ریزی‌شده را ثبت کنید.")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.title = QLineEdit(self.event.get("title") or "")
        self.zone = QComboBox(); self.zone.addItem("بدون بلوک مشخص", None)
        for zone in db.get_zones():
            self.zone.addItem(zone["name"], zone["id"])
        if self.event.get("zone_id") is not None:
            pos = self.zone.findData(self.event.get("zone_id"))
            if pos >= 0: self.zone.setCurrentIndex(pos)

        self.category = QComboBox(); self.category.addItems(db.CALENDAR_EVENT_CATEGORIES)
        self.category.setCurrentText(self.event.get("category") or "جلسه")
        initial_date = self.event.get("start_date") or selected_date or datetime.now().strftime("%Y-%m-%d")
        self.start_date = QDateEdit(_qdate(initial_date)); self.start_date.setCalendarPopup(True); self.start_date.setDisplayFormat("yyyy/MM/dd")
        self.end_date = QDateEdit(_qdate(self.event.get("end_date") or initial_date)); self.end_date.setCalendarPopup(True); self.end_date.setDisplayFormat("yyyy/MM/dd")
        self.all_day = QCheckBox("رویداد تمام‌روز است"); self.all_day.setChecked(bool(self.event.get("all_day", True)))
        self.start_time = QTimeEdit(QTime.fromString(self.event.get("start_time") or "08:00", "HH:mm")); self.start_time.setDisplayFormat("HH:mm")
        self.start_time.setEnabled(not self.all_day.isChecked())
        self.all_day.toggled.connect(lambda checked: self.start_time.setEnabled(not checked))

        self.responsible_user = QComboBox(); self.responsible_user.addItem("بدون کاربر مشخص", None)
        for user in db.list_users(include_inactive=False):
            self.responsible_user.addItem(f"{user['full_name']} — {user['username']}", user["id"])
        if self.event.get("responsible_user_id") is not None:
            pos = self.responsible_user.findData(self.event.get("responsible_user_id"))
            if pos >= 0: self.responsible_user.setCurrentIndex(pos)
        self.responsible_person = QLineEdit(self.event.get("responsible_person") or "")
        self.location = QLineEdit(self.event.get("location") or "")
        self.status = QComboBox(); self.status.addItems(db.CALENDAR_EVENT_STATUSES)
        self.status.setCurrentText(self.event.get("status") or "برنامه‌ریزی‌شده")
        self.priority = QComboBox(); self.priority.addItems(db.CALENDAR_PRIORITIES)
        self.priority.setCurrentText(self.event.get("priority") or "عادی")
        self.reminder_days = QSpinBox(); self.reminder_days.setRange(0, 365); self.reminder_days.setValue(int(self.event.get("reminder_days") or 2))
        self.description = QTextEdit(self.event.get("description") or ""); self.description.setMinimumHeight(120)

        form.addRow("عنوان:", self.title)
        form.addRow("بلوک:", self.zone)
        form.addRow("دسته‌بندی:", self.category)
        form.addRow("تاریخ شروع:", self.start_date)
        form.addRow("تاریخ پایان:", self.end_date)
        form.addRow("زمان:", self.start_time)
        form.addRow("", self.all_day)
        form.addRow("کاربر مسئول:", self.responsible_user)
        form.addRow("نام مسئول خارج از سامانه:", self.responsible_person)
        form.addRow("محل:", self.location)
        form.addRow("وضعیت:", self.status)
        form.addRow("اولویت:", self.priority)
        form.addRow("یادآوری چند روز قبل:", self.reminder_days)
        form.addRow("توضیحات:", self.description)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره رویداد")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "عنوان رویداد الزامی است.")
            return
        if self.end_date.date() < self.start_date.date():
            QMessageBox.warning(self, "تاریخ نامعتبر", "تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
            return
        self.accept()

    def values(self):
        return {
            "title": self.title.text().strip(),
            "zone_id": self.zone.currentData(),
            "category": self.category.currentText(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "start_time": None if self.all_day.isChecked() else self.start_time.time().toString("HH:mm"),
            "all_day": self.all_day.isChecked(),
            "responsible_user_id": self.responsible_user.currentData(),
            "responsible_person": self.responsible_person.text().strip(),
            "location": self.location.text().strip(),
            "description": self.description.toPlainText().strip(),
            "status": self.status.currentText(),
            "priority": self.priority.currentText(),
            "reminder_days": self.reminder_days.value(),
        }


from management_calendar_reports import export_management_brief_excel, export_management_brief_pdf


class ManagementCalendarWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_user = db.get_current_user() or {}
        self.can_edit_calendar = self.current_user.get("role") in {"admin", "manager", "field"}
        self.calendar_rows = []
        self.notification_rows = []
        self.setWindowTitle("پایش اجرایی، اعلان‌ها و تقویم مدیریتی")
        self.resize(1320, 850)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(build_official_header("پایش اجرایی و تقویم مدیریتی", self.db))

        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        title = QLabel("تقویم سررسیدها، اعلان‌های داخلی و گزارش دوره‌ای")
        title.setStyleSheet("font-size:16px; font-weight:800; color:#13294b;")
        toolbar_layout.addWidget(title)
        toolbar_layout.addStretch()
        refresh_btn = QPushButton("بروزرسانی اعلان‌ها")
        set_button_style(refresh_btn, "refresh", "secondary")
        refresh_btn.clicked.connect(self.refresh_all)
        toolbar_layout.addWidget(refresh_btn)
        back_btn = QPushButton("بازگشت به داشبورد")
        set_button_style(back_btn, "back", "ghost")
        back_btn.clicked.connect(self.back_requested.emit)
        toolbar_layout.addWidget(back_btn)
        root.addWidget(toolbar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_calendar_tab()
        self._build_notifications_tab()
        self._build_brief_tab()

    def _build_calendar_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("بلوک:"))
        self.calendar_zone = QComboBox(); self.calendar_zone.addItem("همه بلوک‌ها", None)
        for zone in self.db.get_zones(): self.calendar_zone.addItem(zone["name"], zone["id"])
        self.calendar_zone.currentIndexChanged.connect(self.refresh_calendar)
        filter_row.addWidget(self.calendar_zone)
        filter_row.addStretch()
        add_btn = QPushButton("ثبت رویداد جدید"); add_btn.clicked.connect(self.add_event)
        edit_btn = QPushButton("ویرایش رویداد"); edit_btn.clicked.connect(self.edit_event)
        delete_btn = QPushButton("حذف رویداد"); delete_btn.setProperty("danger", True); delete_btn.clicked.connect(self.delete_event)
        for button in (add_btn, edit_btn, delete_btn):
            button.setEnabled(self.can_edit_calendar)
            if not self.can_edit_calendar:
                button.setToolTip("نقش فعلی فقط اجازه مشاهده تقویم را دارد.")
        filter_row.addWidget(add_btn); filter_row.addWidget(edit_btn); filter_row.addWidget(delete_btn)
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Horizontal)
        self.calendar = JalaliCalendarWidget(); self.calendar.setGridVisible(True)
        self.calendar.selectionChanged.connect(self.refresh_calendar)
        splitter.addWidget(self.calendar)
        self.calendar_table = _table(["زمان", "نوع", "عنوان", "بلوک", "مسئول", "اولویت", "وضعیت", "منبع"], stretch=(2,))
        self.calendar_table.doubleClicked.connect(lambda _index: self.edit_event())
        splitter.addWidget(self.calendar_table)
        splitter.setSizes([420, 850])
        layout.addWidget(splitter, 1)
        self.calendar_status = QLabel("")
        layout.addWidget(self.calendar_status)
        self.tabs.addTab(tab, "تقویم و سررسیدها")

    def _build_notifications_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab)
        row = QHBoxLayout()
        self.unread_only = QCheckBox("فقط خوانده‌نشده‌ها"); self.unread_only.toggled.connect(self.refresh_notifications)
        row.addWidget(self.unread_only); row.addStretch()
        read_btn = QPushButton("علامت‌گذاری به‌عنوان خوانده‌شده"); read_btn.clicked.connect(self.mark_notification_read)
        all_read_btn = QPushButton("خواندن همه"); all_read_btn.clicked.connect(self.mark_all_read)
        dismiss_btn = QPushButton("بستن اعلان"); dismiss_btn.clicked.connect(self.dismiss_notification)
        row.addWidget(read_btn); row.addWidget(all_read_btn); row.addWidget(dismiss_btn)
        layout.addLayout(row)
        self.notifications_table = _table(["شدت", "عنوان", "پیام", "بلوک", "سررسید", "وضعیت"], stretch=(1,2))
        layout.addWidget(self.notifications_table, 1)
        self.notification_status = QLabel("")
        layout.addWidget(self.notification_status)
        self.tabs.addTab(tab, "اعلان‌های داخل برنامه")

    def _build_brief_tab(self):
        tab = QWidget(); layout = QVBoxLayout(tab)
        controls = QGroupBox("بازه گزارش")
        row = QHBoxLayout(controls)
        today = QDate.currentDate()
        self.brief_from = QDateEdit(today.addDays(-7)); self.brief_from.setCalendarPopup(True); self.brief_from.setDisplayFormat("yyyy/MM/dd")
        self.brief_to = QDateEdit(today); self.brief_to.setCalendarPopup(True); self.brief_to.setDisplayFormat("yyyy/MM/dd")
        self.brief_zone = QComboBox(); self.brief_zone.addItem("همه بلوک‌ها", None)
        for zone in self.db.get_zones(): self.brief_zone.addItem(zone["name"], zone["id"])
        row.addWidget(QLabel("از:")); row.addWidget(self.brief_from)
        row.addWidget(QLabel("تا:")); row.addWidget(self.brief_to)
        row.addWidget(QLabel("بلوک:")); row.addWidget(self.brief_zone)
        build_btn = QPushButton("تهیه گزارش"); build_btn.clicked.connect(self.refresh_brief)
        pdf_btn = QPushButton("خروجی PDF"); pdf_btn.clicked.connect(self.export_brief_pdf)
        excel_btn = QPushButton("خروجی Excel"); excel_btn.clicked.connect(self.export_brief_excel)
        row.addWidget(build_btn); row.addWidget(pdf_btn); row.addWidget(excel_btn); row.addStretch()
        layout.addWidget(controls)
        self.brief_view = QTextBrowser()
        layout.addWidget(self.brief_view, 1)
        self.brief_table = _table(["تاریخ", "دسته", "عنوان", "بلوک", "مسئول", "اولویت", "وضعیت"], stretch=(2,))
        self.brief_table.setMaximumHeight(300)
        layout.addWidget(self.brief_table)
        self.tabs.addTab(tab, "گزارش هفتگی و ماهانه")

    def refresh_all(self):
        try:
            self.db.refresh_in_app_notifications(days_ahead=7)
        except Exception as exc:
            QMessageBox.warning(self, "خطای اعلان", str(exc))
        self.refresh_calendar()
        self.refresh_notifications()
        self.refresh_brief()

    def refresh_calendar(self):
        date_value = self.calendar.selectedDate().toString("yyyy-MM-dd")
        self.calendar_rows = self.db.get_deadline_calendar_items(
            date_value, date_value, zone_id=self.calendar_zone.currentData(), include_closed=True
        )
        self.calendar_table.setRowCount(len(self.calendar_rows))
        for row, item in enumerate(self.calendar_rows):
            values = [item.get("time") or "تمام‌روز", item.get("category"), item.get("title"),
                      item.get("zone_name"), item.get("responsible"), item.get("priority"),
                      item.get("status"), "ثبت دستی" if item.get("is_manual") else "سامانه"]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value or "—")))
                if item.get("is_overdue"): cell.setBackground(QColor("#ffd7d7"))
                self.calendar_table.setItem(row, col, cell)
        self.calendar_status.setText(f"{len(self.calendar_rows)} مورد در تاریخ {iso_to_jalali(date_value)}")

    def _selected_calendar_row(self):
        row = self.calendar_table.currentRow()
        return self.calendar_rows[row] if 0 <= row < len(self.calendar_rows) else None

    def add_event(self):
        if not self.can_edit_calendar:
            QMessageBox.warning(self, "عدم دسترسی", "نقش فعلی اجازه ثبت رویداد را ندارد.")
            return
        dlg = CalendarEventDialog(self.db, selected_date=self.calendar.selectedDate().toString("yyyy-MM-dd"), parent=self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.db.add_management_calendar_event(**dlg.values())
                self.refresh_all()
            except Exception as exc:
                QMessageBox.critical(self, "خطا", str(exc))

    def edit_event(self):
        if not self.can_edit_calendar:
            return
        item = self._selected_calendar_row()
        if not item:
            QMessageBox.information(self, "انتخاب رویداد", "ابتدا یک ردیف را انتخاب کنید.")
            return
        if item.get("source_type") != "calendar_event":
            QMessageBox.information(self, "رویداد سیستمی", "این ردیف از اطلاعات عملیاتی سامانه تولید شده و از ماژول اصلی خودش ویرایش می‌شود.")
            return
        event = self.db.get_management_calendar_event(item["source_id"])
        dlg = CalendarEventDialog(self.db, event=event, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            try:
                self.db.update_management_calendar_event(event["id"], **dlg.values())
                self.refresh_all()
            except Exception as exc:
                QMessageBox.critical(self, "خطا", str(exc))

    def delete_event(self):
        if not self.can_edit_calendar:
            return
        item = self._selected_calendar_row()
        if not item or item.get("source_type") != "calendar_event":
            QMessageBox.information(self, "انتخاب رویداد", "فقط رویدادهای دستی تقویم قابل حذف هستند.")
            return
        if QMessageBox.question(self, "حذف رویداد", "رویداد انتخاب‌شده حذف شود؟",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_management_calendar_event(item["source_id"])
            self.refresh_all()

    def refresh_notifications(self):
        user_id = self.current_user.get("id")
        self.notification_rows = self.db.get_in_app_notifications(
            user_id=user_id, unread_only=self.unread_only.isChecked()
        )
        self.notifications_table.setRowCount(len(self.notification_rows))
        unread = 0
        for row, item in enumerate(self.notification_rows):
            if not item.get("is_read"): unread += 1
            values = [item.get("severity"), item.get("title"), item.get("message"),
                      item.get("zone_name"), item.get("due_date"), "خوانده‌شده" if item.get("is_read") else "جدید"]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value or "—")))
                cell.setBackground(SEVERITY_COLORS.get(item.get("severity"), QColor("#ffffff")))
                if not item.get("is_read"):
                    font = cell.font(); font.setBold(True); cell.setFont(font)
                self.notifications_table.setItem(row, col, cell)
        self.notification_status.setText(f"{len(self.notification_rows)} اعلان — {unread} خوانده‌نشده")

    def _selected_notification(self):
        row = self.notifications_table.currentRow()
        return self.notification_rows[row] if 0 <= row < len(self.notification_rows) else None

    def mark_notification_read(self):
        item = self._selected_notification()
        if item:
            self.db.mark_notification_read(item["id"], True)
            self.refresh_notifications()

    def mark_all_read(self):
        self.db.mark_all_notifications_read(self.current_user.get("id"))
        self.refresh_notifications()

    def dismiss_notification(self):
        item = self._selected_notification()
        if item:
            self.db.dismiss_notification(item["id"])
            self.refresh_notifications()

    def _brief_dates(self):
        return self.brief_from.date().toString("yyyy-MM-dd"), self.brief_to.date().toString("yyyy-MM-dd")

    def refresh_brief(self):
        try:
            date_from, date_to = self._brief_dates()
            brief = self.db.get_management_period_brief(date_from, date_to, self.brief_zone.currentData())
        except Exception as exc:
            self.brief_view.setText(str(exc)); return
        html = f"""
        <div dir='rtl' style='font-family:Tahoma; line-height:1.9'>
          <h2 style='color:#13294b'>گزارش پایش اجرایی</h2>
          <p><b>دوره:</b> {iso_to_jalali(brief['date_from'])} تا {iso_to_jalali(brief['date_to'])}</p>
          <table cellspacing='0' cellpadding='8' style='border-collapse:collapse; width:100%'>
            <tr><td>مسائل ثبت‌شده</td><td><b>{brief['issues_created']}</b></td><td>اقدامات تکمیل‌شده</td><td><b>{brief['actions_completed']}</b></td></tr>
            <tr><td>جلسات برگزارشده</td><td><b>{brief['meetings_held']}</b></td><td>بازدید میدانی</td><td><b>{brief['field_visits']}</b></td></tr>
            <tr><td>درخواست مردمی</td><td><b>{brief['citizen_requests']}</b></td><td>نامه ثبت‌شده</td><td><b>{brief['letters_registered']}</b></td></tr>
            <tr><td>رویداد تقویم</td><td><b>{brief['calendar_events']}</b></td><td>سررسید معوق</td><td><b style='color:#a4262c'>{brief['overdue_deadlines']}</b></td></tr>
            <tr><td>مبلغ هزینه‌شده</td><td colspan='3'><b>{brief['spent_amount']:,.0f}</b></td></tr>
          </table>
        </div>"""
        self.brief_view.setHtml(html)
        self.brief_table.setRowCount(len(brief["deadlines"]))
        for row, item in enumerate(brief["deadlines"]):
            values = [item["date"], item["category"], item["title"], item["zone_name"],
                      item["responsible"], item["priority"], item["status"]]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value or "—")))
                if item.get("is_overdue"): cell.setBackground(QColor("#ffd7d7"))
                self.brief_table.setItem(row, col, cell)

    def export_brief_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش PDF", "گزارش_پایش_اجرایی.pdf", "PDF (*.pdf)")
        if not path: return
        try:
            export_management_brief_pdf(self.db, *self._brief_dates(), path, self.brief_zone.currentData())
            QMessageBox.information(self, "گزارش آماده شد", "فایل PDF با موفقیت ذخیره شد.")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def export_brief_excel(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش Excel", "گزارش_پایش_اجرایی.xlsx", "Excel (*.xlsx)")
        if not path: return
        try:
            export_management_brief_excel(self.db, *self._brief_dates(), path, self.brief_zone.currentData())
            QMessageBox.information(self, "گزارش آماده شد", "فایل Excel با موفقیت ذخیره شد.")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))
