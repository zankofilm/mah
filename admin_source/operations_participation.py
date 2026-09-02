# -*- coding: utf-8 -*-
"""عملیات میدانی، مشارکت مردمی، تبادل آفلاین و تحلیل عملیاتی نسخه ۶.۲."""

from PyQt5.QtCore import Qt, pyqtSignal, QDate, QTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QTabWidget, QGroupBox, QSpinBox, QDoubleSpinBox, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QDateEdit, QTimeEdit,
    QCheckBox, QFileDialog, QAbstractItemView, QFrame
)

from icon_manager import get_icon, set_button_style
from ui_scroll import scroll_page
from jalali_utils import convert_dates_in_text
import smart_triage


def _table(headers, stretch_columns=()):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    for idx in range(len(headers)):
        mode = QHeaderView.Stretch if idx in stretch_columns else QHeaderView.ResizeToContents
        table.horizontalHeader().setSectionResizeMode(idx, mode)
    return table


def _float_value(widget):
    value = widget.value()
    return None if abs(value) < 0.0000001 else value


class OperationsParticipationWidget(QWidget):
    """ویجت یکپارچه عملیات میدانی و درخواست‌های مردمی برای یک بلوک."""

    data_changed = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.zone_id = None
        self.current_visit_id = None
        self.current_request_id = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self._build_field_tab()
        self._build_requests_tab()
        self._build_sync_tab()
        self._build_analysis_tab()

    def set_zone(self, zone_id):
        self.zone_id = zone_id
        self.current_visit_id = None
        self.current_request_id = None
        self.refresh_all()

    def refresh_all(self):
        enabled = self.zone_id is not None
        self.tabs.setEnabled(enabled)
        if not enabled:
            return
        self._refresh_agencies()
        self._refresh_visits()
        self._refresh_requests()
        self._refresh_sync()
        self._refresh_analysis()

    def _refresh_agencies(self):
        names = [x["name"] for x in self.db.get_management_agencies(active_only=True)]
        current = self.request_office.currentText()
        self.request_office.clear()
        self.request_office.addItem("")
        self.request_office.addItems(names)
        self.request_office.setEditText(current)

    # ---------------- Field visits ----------------
    def _build_field_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form_group = QGroupBox("ثبت بازدید و برداشت میدانی")
        grid = QGridLayout(form_group)

        self.visit_date = QDateEdit(QDate.currentDate())
        self.visit_date.setCalendarPopup(True)
        self.visit_date.setDisplayFormat("yyyy/MM/dd")
        self.visit_time = QTimeEdit(QTime.currentTime())
        self.visit_time.setDisplayFormat("HH:mm")
        self.visit_officer = QLineEdit()
        self.visit_type = QComboBox()
        self.visit_type.addItems(self.db.FIELD_VISIT_TYPES)
        self.visit_location = QLineEdit()
        self.visit_lat = QDoubleSpinBox(); self.visit_lat.setRange(-90, 90); self.visit_lat.setDecimals(6)
        self.visit_lon = QDoubleSpinBox(); self.visit_lon.setRange(-180, 180); self.visit_lon.setDecimals(6)
        self.visit_buildings = QSpinBox(); self.visit_buildings.setRange(0, 100000)
        self.visit_households = QSpinBox(); self.visit_households.setRange(0, 100000)
        self.visit_followup = QCheckBox("نیازمند پیگیری")
        self.visit_status = QComboBox(); self.visit_status.addItems(self.db.FIELD_VISIT_STATUSES)
        self.visit_observation = QTextEdit(); self.visit_observation.setMaximumHeight(75)
        self.visit_action = QTextEdit(); self.visit_action.setMaximumHeight(65)

        fields = [
            ("تاریخ", self.visit_date), ("ساعت", self.visit_time),
            ("نام کارشناس", self.visit_officer), ("نوع بازدید", self.visit_type),
            ("موقعیت/نشانی", self.visit_location), ("وضعیت", self.visit_status),
            ("عرض جغرافیایی", self.visit_lat), ("طول جغرافیایی", self.visit_lon),
            ("ساختمان شمارش‌شده", self.visit_buildings), ("خانوار شمارش‌شده", self.visit_households),
        ]
        for i, (label, widget) in enumerate(fields):
            col = 0 if i < 5 else 2
            row = i if i < 5 else i - 5
            grid.addWidget(QLabel(label), row, col)
            grid.addWidget(widget, row, col + 1)
        grid.addWidget(self.visit_followup, 5, 0, 1, 2)
        grid.addWidget(QLabel("مشاهدات"), 6, 0)
        grid.addWidget(self.visit_observation, 6, 1, 1, 3)
        grid.addWidget(QLabel("اقدام فوری"), 7, 0)
        grid.addWidget(self.visit_action, 7, 1, 1, 3)

        buttons = QHBoxLayout()
        save = QPushButton("ذخیره بازدید")
        save.clicked.connect(self._save_visit)
        set_button_style(save, "save", "primary")
        clear = QPushButton("فرم جدید")
        clear.clicked.connect(self._clear_visit_form)
        set_button_style(clear, "plus", "secondary")
        delete = QPushButton("حذف بازدید")
        delete.clicked.connect(self._delete_visit)
        set_button_style(delete, "delete", "danger")
        buttons.addWidget(save); buttons.addWidget(clear); buttons.addWidget(delete); buttons.addStretch()
        grid.addLayout(buttons, 8, 0, 1, 4)
        layout.addWidget(form_group)

        self.visits_table = _table(
            ["تاریخ", "کارشناس", "نوع", "موقعیت", "خانوار", "پیگیری", "وضعیت"],
            stretch_columns=(2, 3),
        )
        self.visits_table.itemSelectionChanged.connect(self._load_selected_visit)
        layout.addWidget(self.visits_table, 1)
        self.tabs.addTab(scroll_page(page, min_height=820), get_icon("pin", "navy"), "عملیات میدانی")

    def _visit_form_data(self):
        return dict(
            visit_date=self.visit_date.date().toString("yyyy-MM-dd"),
            start_time=self.visit_time.time().toString("HH:mm"),
            officer_name=self.visit_officer.text(), visit_type=self.visit_type.currentText(),
            location_text=self.visit_location.text(), lat=_float_value(self.visit_lat), lon=_float_value(self.visit_lon),
            buildings_count=self.visit_buildings.value(), households_count=self.visit_households.value(),
            observation=self.visit_observation.toPlainText(), immediate_action=self.visit_action.toPlainText(),
            followup_required=self.visit_followup.isChecked(), status=self.visit_status.currentText(),
        )

    def _save_visit(self):
        if not self.zone_id:
            return
        data = self._visit_form_data()
        if not data["officer_name"].strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "نام کارشناس بازدید را وارد کنید.")
            return
        if self.current_visit_id:
            self.db.update_field_visit(self.current_visit_id, **data)
        else:
            self.db.add_field_visit(self.zone_id, **data)
        self._clear_visit_form()
        self.refresh_all()
        self.data_changed.emit()

    def _clear_visit_form(self):
        self.current_visit_id = None
        self.visit_date.setDate(QDate.currentDate()); self.visit_time.setTime(QTime.currentTime())
        self.visit_officer.clear(); self.visit_type.setCurrentIndex(0); self.visit_location.clear()
        self.visit_lat.setValue(0); self.visit_lon.setValue(0); self.visit_buildings.setValue(0)
        self.visit_households.setValue(0); self.visit_observation.clear(); self.visit_action.clear()
        self.visit_followup.setChecked(False); self.visit_status.setCurrentIndex(0)
        self.visits_table.clearSelection()

    def _refresh_visits(self):
        rows = self.db.get_field_visits(self.zone_id)
        self.visits_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = [format_jalali(item.get("visit_date")) or "—", item.get("officer_name") or "—",
                      item.get("visit_type") or "—", item.get("location_text") or "—",
                      str(item.get("households_count") or 0), "بله" if item.get("followup_required") else "خیر",
                      item.get("status") or "—"]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if c == 0:
                    cell.setData(Qt.UserRole, item["id"])
                self.visits_table.setItem(r, c, cell)

    def _load_selected_visit(self):
        row = self.visits_table.currentRow()
        if row < 0:
            return
        visit_id = self.visits_table.item(row, 0).data(Qt.UserRole)
        item = self.db.get_field_visit(visit_id)
        if not item:
            return
        self.current_visit_id = visit_id
        if item.get("visit_date"):
            self.visit_date.setDate(QDate.fromString(item["visit_date"], "yyyy-MM-dd"))
        if item.get("start_time"):
            self.visit_time.setTime(QTime.fromString(item["start_time"], "HH:mm"))
        self.visit_officer.setText(item.get("officer_name") or "")
        self.visit_type.setCurrentText(item.get("visit_type") or "بازدید عمومی")
        self.visit_location.setText(item.get("location_text") or "")
        self.visit_lat.setValue(item.get("lat") or 0); self.visit_lon.setValue(item.get("lon") or 0)
        self.visit_buildings.setValue(item.get("buildings_count") or 0)
        self.visit_households.setValue(item.get("households_count") or 0)
        self.visit_observation.setPlainText(item.get("observation") or "")
        self.visit_action.setPlainText(item.get("immediate_action") or "")
        self.visit_followup.setChecked(bool(item.get("followup_required")))
        self.visit_status.setCurrentText(item.get("status") or "ثبت‌شده")

    def _delete_visit(self):
        if not self.current_visit_id:
            QMessageBox.information(self, "انتخاب بازدید", "ابتدا یک بازدید را انتخاب کنید.")
            return
        if QMessageBox.question(self, "حذف بازدید", "بازدید انتخاب‌شده حذف شود؟") != QMessageBox.Yes:
            return
        self.db.delete_field_visit(self.current_visit_id)
        self._clear_visit_form(); self.refresh_all(); self.data_changed.emit()

    # ---------------- Citizen requests ----------------
    def _build_requests_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        group = QGroupBox("ثبت درخواست یا گزارش مردمی")
        grid = QGridLayout(group)
        self.request_anonymous = QCheckBox("ثبت ناشناس")
        self.request_anonymous.toggled.connect(self._toggle_anonymous)
        self.request_consent = QCheckBox("اجازه تماس برای پیگیری"); self.request_consent.setChecked(True)
        self.request_name = QLineEdit(); self.request_mobile = QLineEdit()
        self.request_category = QComboBox(); self.request_category.addItems(self.db.ISSUE_CATEGORIES)
        self.request_title = QLineEdit(); self.request_description = QTextEdit(); self.request_description.setMaximumHeight(75)
        self.request_location = QLineEdit()
        self.request_lat = QDoubleSpinBox(); self.request_lat.setRange(-90, 90); self.request_lat.setDecimals(6)
        self.request_lon = QDoubleSpinBox(); self.request_lon.setRange(-180, 180); self.request_lon.setDecimals(6)
        self.request_urgency = QSpinBox(); self.request_urgency.setRange(1, 5); self.request_urgency.setValue(3)
        self.request_status = QComboBox(); self.request_status.addItems(self.db.CITIZEN_REQUEST_STATUSES)
        self.request_office = QComboBox(); self.request_office.setEditable(True)
        self.request_source = QComboBox(); self.request_source.addItems(["ثبت حضوری", "تماس تلفنی", "پیام‌رسان", "فرم میدانی", "نامه اداری"])

        fields = [
            ("نام شهروند", self.request_name), ("شماره تماس", self.request_mobile),
            ("دسته‌بندی", self.request_category), ("عنوان", self.request_title),
            ("موقعیت/نشانی", self.request_location), ("فوریت ۱ تا ۵", self.request_urgency),
            ("وضعیت", self.request_status), ("دستگاه مسئول", self.request_office),
            ("منبع دریافت", self.request_source), ("عرض جغرافیایی", self.request_lat),
            ("طول جغرافیایی", self.request_lon),
        ]
        for i, (label, widget) in enumerate(fields):
            col = 0 if i < 6 else 2
            row = i if i < 6 else i - 6
            grid.addWidget(QLabel(label), row, col); grid.addWidget(widget, row, col + 1)
        grid.addWidget(self.request_anonymous, 6, 0, 1, 2)
        grid.addWidget(self.request_consent, 6, 2, 1, 2)
        description_header = QHBoxLayout()
        description_header.addWidget(QLabel("شرح درخواست"))
        description_header.addStretch()
        suggest_btn = QPushButton("💡 پیشنهاد هوشمند دسته‌بندی و فوریت")
        suggest_btn.setToolTip(
            "بر اساس متن شرح درخواست، دسته‌بندی و میزان فوریت پیشنهادی را تعیین می‌کند.\n"
            "این پیشنهاد صرفاً کمکی است؛ تصمیم نهایی همیشه با کارمند ثبت‌کننده است."
        )
        suggest_btn.clicked.connect(self._on_suggest_category_urgency)
        description_header.addWidget(suggest_btn)
        grid.addLayout(description_header, 7, 0, 1, 4)
        grid.addWidget(self.request_description, 8, 0, 1, 4)
        buttons = QHBoxLayout()
        save = QPushButton("ذخیره درخواست مردمی"); save.clicked.connect(self._save_request); set_button_style(save, "save", "primary")
        clear = QPushButton("فرم جدید"); clear.clicked.connect(self._clear_request_form); set_button_style(clear, "plus", "secondary")
        convert = QPushButton("تبدیل به مسئله محله"); convert.clicked.connect(self._convert_request); set_button_style(convert, "warning", "success")
        delete = QPushButton("حذف درخواست"); delete.clicked.connect(self._delete_request); set_button_style(delete, "delete", "danger")
        buttons.addWidget(save); buttons.addWidget(clear); buttons.addWidget(convert); buttons.addWidget(delete); buttons.addStretch()
        grid.addLayout(buttons, 9, 0, 1, 4)
        layout.addWidget(group)

        self.requests_table = _table(
            ["کد رهگیری", "عنوان", "دسته", "فوریت", "دستگاه", "وضعیت", "مسئله مرتبط"],
            stretch_columns=(1, 4),
        )
        self.requests_table.itemSelectionChanged.connect(self._load_selected_request)
        layout.addWidget(self.requests_table, 1)
        self.tabs.addTab(scroll_page(page, min_height=860), get_icon("users", "navy"), "درخواست‌های مردمی")

    def _toggle_anonymous(self, checked):
        self.request_name.setEnabled(not checked)
        self.request_mobile.setEnabled(not checked)
        if checked:
            self.request_name.clear(); self.request_mobile.clear(); self.request_consent.setChecked(False)

    def _on_suggest_category_urgency(self):
        text = self.request_description.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self, "متن خالی است",
                "برای دریافت پیشنهاد، ابتدا شرح درخواست را وارد کنید."
            )
            return
        ai_settings = self.db.get_smart_triage_settings()
        api_url = ai_settings["api_url"] if ai_settings["enabled"] else ""
        api_key = ai_settings["api_key"] if ai_settings["enabled"] else ""
        result = smart_triage.suggest(text, self.db.ISSUE_CATEGORIES, api_url=api_url, api_key=api_key)

        self.request_category.setCurrentText(result["category"])
        self.request_urgency.setValue(result["urgency"])

        engine_label = "سرویس هوش مصنوعی متصل‌شده" if result["engine"] == "api" else "موتور کلیدواژه‌ای آفلاین"
        message = f"پیشنهاد بر اساس {engine_label}:\nدسته‌بندی: {result['category']}\nفوریت: {result['urgency']} از ۵"
        if result["matched_keywords"]:
            message += f"\nکلیدواژه‌های یافت‌شده: {'، '.join(result['matched_keywords'])}"
        message += "\n\nاین فقط یک پیشنهاد است؛ در صورت نیاز آن را اصلاح کنید."
        QMessageBox.information(self, "پیشنهاد هوشمند", message)

    def _request_form_data(self):
        return dict(
            title=self.request_title.text(), category=self.request_category.currentText(),
            description=self.request_description.toPlainText(), citizen_name=self.request_name.text(),
            mobile=self.request_mobile.text(), is_anonymous=self.request_anonymous.isChecked(),
            consent_contact=self.request_consent.isChecked(), location_text=self.request_location.text(),
            lat=_float_value(self.request_lat), lon=_float_value(self.request_lon),
            urgency=self.request_urgency.value(), status=self.request_status.currentText(),
            assigned_office=self.request_office.currentText(), source=self.request_source.currentText(),
        )

    def _save_request(self):
        if not self.zone_id:
            return
        data = self._request_form_data()
        if not data["title"].strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "عنوان درخواست را وارد کنید.")
            return
        if self.current_request_id:
            self.db.update_citizen_request(self.current_request_id, **data)
        else:
            request_id = self.db.add_citizen_request(self.zone_id, **data)
            code = self.db.get_citizen_request(request_id)["tracking_code"]
            QMessageBox.information(self, "درخواست ثبت شد", f"کد رهگیری درخواست: {code}")
        self._clear_request_form(); self.refresh_all(); self.data_changed.emit()

    def _clear_request_form(self):
        self.current_request_id = None
        self.request_anonymous.setChecked(False); self.request_consent.setChecked(True)
        self.request_name.clear(); self.request_mobile.clear(); self.request_category.setCurrentIndex(0)
        self.request_title.clear(); self.request_description.clear(); self.request_location.clear()
        self.request_lat.setValue(0); self.request_lon.setValue(0); self.request_urgency.setValue(3)
        self.request_status.setCurrentIndex(0); self.request_office.setEditText(""); self.request_source.setCurrentIndex(0)
        self.requests_table.clearSelection()

    def _refresh_requests(self):
        rows = self.db.get_citizen_requests(self.zone_id)
        self.requests_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = [item.get("tracking_code") or "—", item.get("title") or "—", item.get("category") or "—",
                      str(item.get("urgency") or 0), item.get("assigned_office") or "—", item.get("status") or "—",
                      str(item.get("linked_issue_id") or "—")]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if c == 0:
                    cell.setData(Qt.UserRole, item["id"])
                self.requests_table.setItem(r, c, cell)

    def _load_selected_request(self):
        row = self.requests_table.currentRow()
        if row < 0:
            return
        request_id = self.requests_table.item(row, 0).data(Qt.UserRole)
        item = self.db.get_citizen_request(request_id)
        if not item:
            return
        self.current_request_id = request_id
        self.request_anonymous.setChecked(bool(item.get("is_anonymous")))
        self.request_consent.setChecked(bool(item.get("consent_contact")))
        self.request_name.setText(item.get("citizen_name") or ""); self.request_mobile.setText(item.get("mobile") or "")
        self.request_category.setCurrentText(item.get("category") or "سایر"); self.request_title.setText(item.get("title") or "")
        self.request_description.setPlainText(item.get("description") or "")
        self.request_location.setText(item.get("location_text") or "")
        self.request_lat.setValue(item.get("lat") or 0); self.request_lon.setValue(item.get("lon") or 0)
        self.request_urgency.setValue(item.get("urgency") or 3); self.request_status.setCurrentText(item.get("status") or "دریافت‌شده")
        self.request_office.setEditText(item.get("assigned_office") or ""); self.request_source.setCurrentText(item.get("source") or "ثبت حضوری")

    def _convert_request(self):
        if not self.current_request_id:
            QMessageBox.information(self, "انتخاب درخواست", "ابتدا یک درخواست مردمی را انتخاب کنید.")
            return
        issue_id = self.db.convert_citizen_request_to_issue(self.current_request_id)
        QMessageBox.information(self, "تبدیل انجام شد", f"درخواست به مسئله شماره {issue_id} متصل شد.")
        self.refresh_all(); self.data_changed.emit()

    def _delete_request(self):
        if not self.current_request_id:
            QMessageBox.information(self, "انتخاب درخواست", "ابتدا یک درخواست را انتخاب کنید.")
            return
        if QMessageBox.question(self, "حذف درخواست", "درخواست انتخاب‌شده حذف شود؟") != QMessageBox.Yes:
            return
        self.db.delete_citizen_request(self.current_request_id)
        self._clear_request_form(); self.refresh_all(); self.data_changed.emit()

    # ---------------- Offline exchange ----------------
    def _build_sync_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        info = QLabel(
            "ثبت‌های میدانی و درخواست‌های مردمی بدون اینترنت در دیتابیس محلی ذخیره می‌شوند. "
            "برای انتقال به رایانه دیگر، بسته تبادل JSON بسازید و در مقصد وارد کنید. "
            "این فایل ممکن است شامل اطلاعات تماس شهروندان باشد و باید محرمانه نگهداری شود."
        )
        info.setWordWrap(True); layout.addWidget(info)
        bar = QHBoxLayout()
        export = QPushButton("خروجی بسته تبادل"); export.clicked.connect(self._export_sync); set_button_style(export, "download", "primary")
        import_btn = QPushButton("ورود بسته تبادل"); import_btn.clicked.connect(self._import_sync); set_button_style(import_btn, "upload", "secondary")
        refresh = QPushButton("بروزرسانی صف"); refresh.clicked.connect(self._refresh_sync); set_button_style(refresh, "refresh", "secondary")
        bar.addWidget(export); bar.addWidget(import_btn); bar.addWidget(refresh); bar.addStretch()
        layout.addLayout(bar)
        self.sync_status = QLabel("—"); layout.addWidget(self.sync_status)
        self.sync_table = _table(["نوع رکورد", "عملیات", "وضعیت", "زمان صف", "خطا"], stretch_columns=(0, 4))
        layout.addWidget(self.sync_table, 1)
        self.tabs.addTab(scroll_page(page, min_height=700), get_icon("offline", "navy"), "همگام‌سازی آفلاین")

    def _refresh_sync(self):
        rows = self.db.get_sync_queue()
        self.sync_table.setRowCount(len(rows))
        labels = {"field_visit": "بازدید میدانی", "citizen_request": "درخواست مردمی"}
        pending = 0
        for r, item in enumerate(rows):
            if item.get("status") == "در انتظار انتقال": pending += 1
            values = [labels.get(item.get("entity_type"), item.get("entity_type") or "—"),
                      item.get("operation") or "—", item.get("status") or "—",
                      item.get("queued_at") or "—", item.get("last_error") or "—"]
            for c, value in enumerate(values): self.sync_table.setItem(r, c, QTableWidgetItem(convert_dates_in_text(str(value))))
        self.sync_status.setText(f"تعداد کل تغییرات: {len(rows)} — در انتظار انتقال: {pending}")

    def _export_sync(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره بسته تبادل", "javanrood_sync.json", "JSON (*.json)")
        if not path: return
        result = self.db.export_sync_package(path, zone_id=self.zone_id)
        QMessageBox.information(
            self, "بسته ساخته شد",
            f"{result['count']} رکورد نهایی در بسته ذخیره شد. "
            f"{result.get('compacted_from', result['count'])} تغییر صف‌شده پردازش شد.\n"
            "فایل را به‌دلیل احتمال وجود اطلاعات تماس، محرمانه نگهداری کنید."
        )
        self._refresh_sync(); self.data_changed.emit()

    def _import_sync(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب بسته تبادل", "", "JSON (*.json)")
        if not path: return
        try:
            counts = self.db.import_sync_package(path)
        except Exception as exc:
            QMessageBox.critical(self, "ورود ناموفق", str(exc)); return
        QMessageBox.information(
            self, "ورود بسته انجام شد",
            f"جدید: {counts.get('inserted', 0)}\nبروزرسانی: {counts.get('updated', 0)}\n"
            f"حذف: {counts.get('deleted', 0)}\nبلوک ناموجود: {counts.get('zone_missing', 0)}\n"
            f"خطای رکورد: {counts.get('errors', 0)}",
        )
        self.refresh_all(); self.data_changed.emit()

    # ---------------- Analysis ----------------
    def _build_analysis_tab(self):
        page = QWidget(); layout = QVBoxLayout(page)
        cards = QGridLayout(); self.analysis_labels = {}
        specs = [
            ("risk_score", "امتیاز ریسک"), ("risk_level", "سطح ریسک"),
            ("field_visits", "بازدید میدانی"), ("open_requests", "درخواست باز"),
            ("critical_issues", "مسئله فوری/بحرانی"), ("service_gap_count", "شکاف خدماتی"),
            ("issue_density_per_ha", "تراکم مسئله/هکتار"), ("request_density_per_ha", "تراکم درخواست/هکتار"),
        ]
        for i, (key, title) in enumerate(specs):
            card = QFrame(); card.setObjectName("StatCard"); cl = QVBoxLayout(card)
            value = QLabel("—"); value.setAlignment(Qt.AlignCenter); value.setStyleSheet("font-size:22px; font-weight:900; color:#13294b;")
            label = QLabel(title); label.setAlignment(Qt.AlignCenter)
            cl.addWidget(value); cl.addWidget(label); cards.addWidget(card, i // 4, i % 4)
            self.analysis_labels[key] = value
        layout.addLayout(cards)
        bar = QHBoxLayout()
        export = QPushButton("خروجی GeoJSON تحلیل عملیاتی"); export.clicked.connect(self._export_geojson); set_button_style(export, "map", "primary")
        refresh = QPushButton("محاسبه مجدد"); refresh.clicked.connect(self._refresh_analysis); set_button_style(refresh, "refresh", "secondary")
        bar.addWidget(export); bar.addWidget(refresh); bar.addStretch(); layout.addLayout(bar)
        self.city_analysis_table = _table(
            ["بلوک", "ریسک", "امتیاز", "درخواست باز", "مسئله بحرانی", "اقدام معوق", "شکاف خدماتی"],
            stretch_columns=(0,),
        )
        layout.addWidget(self.city_analysis_table, 1)
        self.tabs.addTab(scroll_page(page, min_height=650), get_icon("report", "navy"), "تحلیل عملیاتی")

    def _refresh_analysis(self):
        if not self.zone_id: return
        current = self.db.get_zone_operational_analysis(self.zone_id)
        for key, label in self.analysis_labels.items(): label.setText(str(current.get(key, "—")))
        rows = self.db.get_city_operational_analysis()
        self.city_analysis_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = [item.get("zone_name"), item.get("risk_level"), item.get("risk_score"),
                      item.get("open_requests"), item.get("critical_issues"), item.get("overdue_actions"),
                      item.get("service_gap_count")]
            for c, value in enumerate(values): self.city_analysis_table.setItem(r, c, QTableWidgetItem(convert_dates_in_text(str(value))))

    def _export_geojson(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره تحلیل مکانی", "neighborhood_operations.geojson", "GeoJSON (*.geojson)")
        if not path: return
        self.db.export_operational_geojson(path)
        QMessageBox.information(self, "خروجی ساخته شد", "فایل GeoJSON تحلیل عملیاتی ذخیره شد.")
