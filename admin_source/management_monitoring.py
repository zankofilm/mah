# -*- coding: utf-8 -*-
"""نسخه ۶.۱: بودجه، دستگاه‌ها، هشدارها، عملکرد و کنترل کیفیت."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QTabWidget, QGroupBox, QDoubleSpinBox, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox,
    QAbstractItemView, QFrame
)

from icon_manager import get_icon, set_button_style
from ui_scroll import scroll_page
from jalali_utils import convert_dates_in_text


def _table(headers, stretch_columns=()):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    for idx in range(len(headers)):
        table.horizontalHeader().setSectionResizeMode(
            idx, QHeaderView.Stretch if idx in stretch_columns else QHeaderView.ResizeToContents
        )
    return table


def _money(value):
    try:
        return f"{float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "۰"


class ManagementMonitoringWidget(QWidget):
    """پنل یکپارچه کنترل مدیریتی بلوک انتخابی."""
    data_changed = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.zone_id = None
        self.current_budget_id = None
        self.current_agency_id = None
        self.current_alert_key = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        self._build_budget_tab()
        self._build_agencies_tab()
        self._build_alerts_tab()
        self._build_quality_tab()

    def set_zone(self, zone_id):
        self.zone_id = zone_id
        self.refresh_all()

    def refresh_all(self):
        enabled = self.zone_id is not None
        self.tabs.setEnabled(enabled)
        if not enabled:
            return
        self._refresh_action_combo()
        self._refresh_budgets()
        self._refresh_agencies()
        self._refresh_alerts()
        self._refresh_quality()

    # ---------------- Budget ----------------
    def _build_budget_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)

        summary = QGroupBox("خلاصه بودجه بلوک")
        sg = QGridLayout(summary)
        self.budget_summary_labels = {}
        specs = [
            ("approved", "اعتبار مصوب"), ("allocated", "تخصیص‌یافته"),
            ("spent", "هزینه‌شده"), ("remaining", "مانده تخصیص"),
            ("absorption_percent", "درصد تخصیص"), ("utilization_percent", "درصد مصرف")
        ]
        for i, (key, title) in enumerate(specs):
            frame = QFrame()
            frame.setObjectName("StatCard")
            fl = QVBoxLayout(frame)
            value = QLabel("—")
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("font-size:20px; font-weight:900; color:#13294b;")
            caption = QLabel(title)
            caption.setAlignment(Qt.AlignCenter)
            fl.addWidget(value)
            fl.addWidget(caption)
            sg.addWidget(frame, i // 3, i % 3)
            self.budget_summary_labels[key] = value
        layout.addWidget(summary)

        form_box = QGroupBox("ثبت و ویرایش ردیف بودجه")
        form = QGridLayout(form_box)
        self.budget_action = QComboBox()
        self.budget_title = QLineEdit()
        self.budget_year = QLineEdit()
        self.budget_year.setPlaceholderText("مثلاً ۱۴۰۵")
        self.budget_source = QLineEdit()
        self.budget_approved = self._money_spin()
        self.budget_allocated = self._money_spin()
        self.budget_spent = self._money_spin()
        self.budget_status = QComboBox()
        self.budget_status.addItems(self.db.BUDGET_STATUSES)
        self.budget_doc = QLineEdit()
        self.budget_notes = QTextEdit()
        self.budget_notes.setMaximumHeight(65)

        fields = [
            ("اقدام مرتبط:", self.budget_action, 0, 0), ("عنوان ردیف:*", self.budget_title, 0, 2),
            ("سال مالی:", self.budget_year, 1, 0), ("منبع اعتبار:", self.budget_source, 1, 2),
            ("اعتبار مصوب:", self.budget_approved, 2, 0), ("مبلغ تخصیص:", self.budget_allocated, 2, 2),
            ("مبلغ هزینه‌شده:", self.budget_spent, 3, 0), ("وضعیت:", self.budget_status, 3, 2),
            ("شماره سند/ابلاغ:", self.budget_doc, 4, 0), ("یادداشت:", self.budget_notes, 5, 0, 1, 4),
        ]
        for item in fields:
            label, widget, row, col, *span = item
            form.addWidget(QLabel(label), row, col)
            form.addWidget(widget, row, col + 1, *(span or [1, 1]))
        buttons = QHBoxLayout()
        add = QPushButton("ثبت ردیف بودجه")
        add.clicked.connect(self._save_budget)
        set_button_style(add, "plus", "success")
        update = QPushButton("ویرایش ردیف انتخاب‌شده")
        update.clicked.connect(self._update_budget)
        set_button_style(update, "edit", "secondary")
        clear = QPushButton("پاک‌کردن فرم")
        clear.clicked.connect(self._clear_budget_form)
        set_button_style(clear, "refresh", "ghost")
        buttons.addWidget(add); buttons.addWidget(update); buttons.addWidget(clear); buttons.addStretch()
        form.addLayout(buttons, 6, 0, 1, 4)
        layout.addWidget(form_box)

        table_box = QGroupBox("ردیف‌های بودجه و هزینه")
        tl = QVBoxLayout(table_box)
        self.budget_table = _table(
            ["شناسه", "عنوان", "اقدام", "مصوب", "تخصیص", "هزینه", "مانده", "وضعیت", "سال"],
            (1, 2)
        )
        self.budget_table.itemSelectionChanged.connect(self._budget_selected)
        tl.addWidget(self.budget_table)
        row = QHBoxLayout()
        delete = QPushButton("حذف ردیف بودجه")
        delete.clicked.connect(self._delete_budget)
        set_button_style(delete, "delete", "danger")
        row.addWidget(delete); row.addStretch(); tl.addLayout(row)
        layout.addWidget(table_box, 1)
        self.tabs.addTab(scroll_page(page, min_height=820), get_icon("report", "navy"), "بودجه و هزینه")

    @staticmethod
    def _money_spin():
        spin = QDoubleSpinBox()
        spin.setRange(0, 10**16)
        spin.setDecimals(0)
        spin.setSingleStep(1000000)
        spin.setSuffix(" ریال")
        return spin

    def _budget_payload(self):
        return dict(
            action_id=self.budget_action.currentData(), title=self.budget_title.text().strip(),
            fiscal_year=self.budget_year.text().strip(), funding_source=self.budget_source.text().strip(),
            approved_amount=self.budget_approved.value(), allocated_amount=self.budget_allocated.value(),
            spent_amount=self.budget_spent.value(), status=self.budget_status.currentText(),
            document_reference=self.budget_doc.text().strip(), notes=self.budget_notes.toPlainText().strip()
        )

    def _save_budget(self):
        if self.zone_id is None:
            return
        payload = self._budget_payload()
        if not payload["title"]:
            QMessageBox.warning(self, "عنوان الزامی", "عنوان ردیف بودجه را وارد کنید.")
            return
        try:
            self.db.add_neighborhood_budget(self.zone_id, **payload)
            self._clear_budget_form(); self.refresh_all(); self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def _update_budget(self):
        if not self.current_budget_id:
            QMessageBox.warning(self, "انتخاب ردیف", "ابتدا یک ردیف بودجه را انتخاب کنید.")
            return
        try:
            self.db.update_neighborhood_budget(self.current_budget_id, **self._budget_payload())
            self.refresh_all(); self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def _delete_budget(self):
        if not self.current_budget_id:
            return
        if QMessageBox.question(self, "حذف بودجه", "ردیف انتخاب‌شده حذف شود؟", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_neighborhood_budget(self.current_budget_id)
            self._clear_budget_form(); self.refresh_all(); self.data_changed.emit()

    def _clear_budget_form(self):
        self.current_budget_id = None
        self.budget_action.setCurrentIndex(0)
        self.budget_title.clear(); self.budget_year.clear(); self.budget_source.clear()
        self.budget_approved.setValue(0); self.budget_allocated.setValue(0); self.budget_spent.setValue(0)
        self.budget_status.setCurrentIndex(0); self.budget_doc.clear(); self.budget_notes.clear()
        self.budget_table.clearSelection()

    def _refresh_action_combo(self):
        current = self.budget_action.currentData()
        self.budget_action.blockSignals(True)
        self.budget_action.clear()
        self.budget_action.addItem("بدون ارتباط با اقدام", None)
        if self.zone_id is not None:
            for action in self.db.get_neighborhood_actions(self.zone_id):
                self.budget_action.addItem(f"{action['id']} — {action['title']}", action["id"])
        idx = self.budget_action.findData(current)
        self.budget_action.setCurrentIndex(idx if idx >= 0 else 0)
        self.budget_action.blockSignals(False)

    def _refresh_budgets(self):
        if self.zone_id is None:
            return
        self._budgets = self.db.get_neighborhood_budgets(self.zone_id)
        self.budget_table.setRowCount(len(self._budgets))
        for row, item in enumerate(self._budgets):
            remaining = float(item.get("allocated_amount") or 0) - float(item.get("spent_amount") or 0)
            vals = [item["id"], item["title"], item.get("action_title") or "—",
                    _money(item.get("approved_amount")), _money(item.get("allocated_amount")),
                    _money(item.get("spent_amount")), _money(remaining), item.get("status") or "—",
                    item.get("fiscal_year") or "—"]
            for col, val in enumerate(vals):
                self.budget_table.setItem(row, col, QTableWidgetItem(convert_dates_in_text(str(val))))
        summary = self.db.get_budget_summary(self.zone_id)
        for key, label in self.budget_summary_labels.items():
            if key.endswith("percent"):
                label.setText(f"{summary[key]:.1f}٪")
            else:
                label.setText(_money(summary[key]) + " ریال")

    def _budget_selected(self):
        row = self.budget_table.currentRow()
        if row < 0 or row >= len(getattr(self, "_budgets", [])):
            return
        item = self._budgets[row]
        self.current_budget_id = item["id"]
        idx = self.budget_action.findData(item.get("action_id")); self.budget_action.setCurrentIndex(idx if idx >= 0 else 0)
        self.budget_title.setText(item.get("title") or "")
        self.budget_year.setText(item.get("fiscal_year") or "")
        self.budget_source.setText(item.get("funding_source") or "")
        self.budget_approved.setValue(float(item.get("approved_amount") or 0))
        self.budget_allocated.setValue(float(item.get("allocated_amount") or 0))
        self.budget_spent.setValue(float(item.get("spent_amount") or 0))
        idx = self.budget_status.findText(item.get("status") or ""); self.budget_status.setCurrentIndex(idx if idx >= 0 else 0)
        self.budget_doc.setText(item.get("document_reference") or "")
        self.budget_notes.setPlainText(item.get("notes") or "")

    # ---------------- Agencies ----------------
    def _build_agencies_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        form_box = QGroupBox("دفتر دستگاه‌ها و مسئولان")
        form = QGridLayout(form_box)
        self.agency_name = QLineEdit(); self.agency_category = QComboBox()
        self.agency_category.addItems(["دستگاه اجرایی", "نهاد حمایتی", "خدمات شهری", "زیرساخت", "فرهنگی و اجتماعی", "امنیتی", "سایر"])
        self.agency_contact = QLineEdit(); self.agency_phone = QLineEdit(); self.agency_email = QLineEdit()
        self.agency_address = QLineEdit(); self.agency_scope = QLineEdit(); self.agency_active = QCheckBox("فعال")
        self.agency_active.setChecked(True); self.agency_notes = QTextEdit(); self.agency_notes.setMaximumHeight(65)
        entries = [
            ("نام دستگاه:*", self.agency_name, 0, 0), ("دسته:", self.agency_category, 0, 2),
            ("نام مسئول:", self.agency_contact, 1, 0), ("تلفن:", self.agency_phone, 1, 2),
            ("ایمیل:", self.agency_email, 2, 0), ("آدرس:", self.agency_address, 2, 2),
            ("حوزه خدمت:", self.agency_scope, 3, 0), ("وضعیت:", self.agency_active, 3, 2),
            ("یادداشت:", self.agency_notes, 4, 0, 1, 4),
        ]
        for item in entries:
            label, widget, row, col, *span = item
            form.addWidget(QLabel(label), row, col); form.addWidget(widget, row, col + 1, *(span or [1, 1]))
        buttons = QHBoxLayout()
        add = QPushButton("ثبت دستگاه جدید"); add.clicked.connect(self._save_agency); set_button_style(add, "plus", "success")
        update = QPushButton("ویرایش دستگاه"); update.clicked.connect(self._update_agency); set_button_style(update, "edit", "secondary")
        clear = QPushButton("پاک‌کردن فرم"); clear.clicked.connect(self._clear_agency_form); set_button_style(clear, "refresh", "ghost")
        buttons.addWidget(add); buttons.addWidget(update); buttons.addWidget(clear); buttons.addStretch(); form.addLayout(buttons, 5, 0, 1, 4)
        layout.addWidget(form_box)

        self.agency_table = _table(["شناسه", "نام دستگاه", "دسته", "مسئول", "تلفن", "حوزه خدمت", "فعال", "ارجاعات", "تکمیل", "معوق"], (1, 3, 5))
        self.agency_table.itemSelectionChanged.connect(self._agency_selected)
        layout.addWidget(self.agency_table, 1)
        row = QHBoxLayout(); delete = QPushButton("حذف دستگاه"); delete.clicked.connect(self._delete_agency); set_button_style(delete, "delete", "danger")
        row.addWidget(delete); row.addStretch(); layout.addLayout(row)
        self.tabs.addTab(scroll_page(page, min_height=700), get_icon("users", "navy"), "دستگاه‌های مسئول")

    def _agency_payload(self):
        return dict(name=self.agency_name.text().strip(), category=self.agency_category.currentText(),
                    contact_person=self.agency_contact.text().strip(), phone=self.agency_phone.text().strip(),
                    email=self.agency_email.text().strip(), address=self.agency_address.text().strip(),
                    service_scope=self.agency_scope.text().strip(), is_active=self.agency_active.isChecked(),
                    notes=self.agency_notes.toPlainText().strip())

    def _save_agency(self):
        data = self._agency_payload()
        if not data["name"]:
            QMessageBox.warning(self, "نام الزامی", "نام دستگاه را وارد کنید."); return
        try:
            self.db.add_management_agency(**data); self._clear_agency_form(); self.refresh_all(); self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def _update_agency(self):
        if not self.current_agency_id:
            QMessageBox.warning(self, "انتخاب دستگاه", "ابتدا یک دستگاه را انتخاب کنید."); return
        try:
            self.db.update_management_agency(self.current_agency_id, **self._agency_payload()); self.refresh_all(); self.data_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def _delete_agency(self):
        if self.current_agency_id and QMessageBox.question(self, "حذف دستگاه", "دستگاه انتخاب‌شده حذف شود؟", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_management_agency(self.current_agency_id); self._clear_agency_form(); self.refresh_all(); self.data_changed.emit()

    def _clear_agency_form(self):
        self.current_agency_id = None
        self.agency_name.clear(); self.agency_category.setCurrentIndex(0); self.agency_contact.clear()
        self.agency_phone.clear(); self.agency_email.clear(); self.agency_address.clear(); self.agency_scope.clear()
        self.agency_active.setChecked(True); self.agency_notes.clear(); self.agency_table.clearSelection()

    def _refresh_agencies(self):
        self._agencies = self.db.get_agency_performance()
        self.agency_table.setRowCount(len(self._agencies))
        for row, item in enumerate(self._agencies):
            vals = [item["id"], item["name"], item.get("category") or "—", item.get("contact_person") or "—",
                    item.get("phone") or "—", item.get("service_scope") or "—", "بله" if item.get("is_active") else "خیر",
                    item.get("assigned", 0), f"{item.get('completion_percent', 0):.1f}٪", item.get("overdue", 0)]
            for col, val in enumerate(vals):
                self.agency_table.setItem(row, col, QTableWidgetItem(convert_dates_in_text(str(val))))

    def _agency_selected(self):
        row = self.agency_table.currentRow()
        if row < 0 or row >= len(getattr(self, "_agencies", [])):
            return
        item = self._agencies[row]; self.current_agency_id = item["id"]
        self.agency_name.setText(item.get("name") or "")
        idx = self.agency_category.findText(item.get("category") or ""); self.agency_category.setCurrentIndex(idx if idx >= 0 else 0)
        self.agency_contact.setText(item.get("contact_person") or ""); self.agency_phone.setText(item.get("phone") or "")
        self.agency_email.setText(item.get("email") or ""); self.agency_address.setText(item.get("address") or "")
        self.agency_scope.setText(item.get("service_scope") or ""); self.agency_active.setChecked(bool(item.get("is_active")))
        self.agency_notes.setPlainText(item.get("notes") or "")

    # ---------------- Alerts ----------------
    def _build_alerts_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        tools = QHBoxLayout()
        self.show_acknowledged = QCheckBox("نمایش هشدارهای رسیدگی‌شده")
        self.show_acknowledged.toggled.connect(self._refresh_alerts)
        tools.addWidget(self.show_acknowledged)
        refresh = QPushButton("بروزرسانی هشدارها"); refresh.clicked.connect(self._refresh_alerts); set_button_style(refresh, "refresh", "secondary")
        tools.addWidget(refresh); tools.addStretch(); layout.addLayout(tools)
        self.alerts_table = _table(["سطح", "دسته", "عنوان", "توضیح", "مهلت", "وضعیت"], (2, 3))
        self.alerts_table.itemSelectionChanged.connect(self._alert_selected)
        layout.addWidget(self.alerts_table, 1)
        row = QHBoxLayout()
        ack = QPushButton("علامت‌گذاری به‌عنوان رسیدگی‌شده"); ack.clicked.connect(self._ack_alert); set_button_style(ack, "check", "success")
        restore = QPushButton("بازگرداندن هشدار"); restore.clicked.connect(self._restore_alert); set_button_style(restore, "refresh", "secondary")
        row.addWidget(ack); row.addWidget(restore); row.addStretch(); layout.addLayout(row)
        self.tabs.addTab(scroll_page(page, min_height=620), get_icon("warning", "navy"), "هشدارها و سررسیدها")

    def _refresh_alerts(self):
        if self.zone_id is None:
            return
        self._alerts = self.db.get_management_alerts(self.zone_id, include_acknowledged=self.show_acknowledged.isChecked())
        self.alerts_table.setRowCount(len(self._alerts))
        for row, item in enumerate(self._alerts):
            vals = [item["severity"], item["category"], item["title"], item["detail"], item.get("due_date") or "—",
                    "رسیدگی‌شده" if item.get("acknowledged") else "باز"]
            for col, val in enumerate(vals):
                cell = QTableWidgetItem(convert_dates_in_text(str(val))); self.alerts_table.setItem(row, col, cell)

    def _alert_selected(self):
        row = self.alerts_table.currentRow()
        if row < 0 or row >= len(getattr(self, "_alerts", [])):
            self.current_alert_key = None; return
        self.current_alert_key = self._alerts[row]["key"]

    def _ack_alert(self):
        if not self.current_alert_key:
            QMessageBox.warning(self, "انتخاب هشدار", "ابتدا یک هشدار را انتخاب کنید."); return
        self.db.acknowledge_management_alert(self.current_alert_key)
        self.current_alert_key = None; self._refresh_alerts()

    def _restore_alert(self):
        if not self.current_alert_key:
            return
        self.db.restore_management_alert(self.current_alert_key)
        self.current_alert_key = None; self._refresh_alerts()

    # ---------------- Quality & performance ----------------
    def _build_quality_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(10, 10, 10, 10)
        perf = QGroupBox("امتیاز عملکرد بلوک")
        grid = QGridLayout(perf)
        self.performance_labels = {}
        specs = [
            ("total_score", "امتیاز کل"), ("completeness", "تکمیل اطلاعات"),
            ("issue_resolution", "حل مسائل"), ("action_completion", "تکمیل اقدامات"),
            ("resolution_completion", "تحقق مصوبات"), ("timeliness", "رعایت زمان‌بندی"),
            ("financial_control", "کنترل مالی"),
        ]
        for i, (key, title) in enumerate(specs):
            frame = QFrame(); fl = QVBoxLayout(frame)
            value = QLabel("—"); value.setAlignment(Qt.AlignCenter); value.setStyleSheet("font-size:20px; font-weight:900; color:#13294b;")
            cap = QLabel(title); cap.setAlignment(Qt.AlignCenter)
            fl.addWidget(value); fl.addWidget(cap); grid.addWidget(frame, i // 4, i % 4); self.performance_labels[key] = value
        self.performance_level = QLabel("وضعیت: —")
        self.performance_level.setAlignment(Qt.AlignCenter)
        self.performance_level.setStyleSheet("font-size:17px; font-weight:900; padding:8px;")
        grid.addWidget(self.performance_level, 2, 0, 1, 4)
        layout.addWidget(perf)

        quality_box = QGroupBox("مغایرت‌ها و نقص‌های پرونده")
        ql = QVBoxLayout(quality_box)
        self.quality_table = _table(["شدت", "دسته", "شرح مغایرت"], (2,))
        ql.addWidget(self.quality_table)
        layout.addWidget(quality_box, 1)
        self.tabs.addTab(scroll_page(page, min_height=680), get_icon("check", "navy"), "عملکرد و کنترل کیفیت")

    def _refresh_quality(self):
        if self.zone_id is None:
            return
        perf = self.db.get_zone_performance(self.zone_id)
        for key, label in self.performance_labels.items():
            label.setText(f"{perf.get(key, 0):.1f}٪" if key != "total_score" else f"{perf.get(key, 0):.1f} / ۱۰۰")
        self.performance_level.setText(f"ارزیابی نهایی: {perf.get('level', '—')}")
        quality = self.db.get_quality_issues(self.zone_id)
        self.quality_table.setRowCount(len(quality))
        for row, item in enumerate(quality):
            for col, val in enumerate([item["severity"], item["category"], item["message"]]):
                self.quality_table.setItem(row, col, QTableWidgetItem(convert_dates_in_text(str(val))))
