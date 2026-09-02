# -*- coding: utf-8 -*-
"""هسته مدیریت محله‌محور: پرونده بلوک، خانوار، مسائل، اقدامات، جلسات و مصوبات."""

from PyQt5.QtCore import Qt, pyqtSignal, QDate, QTime
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QTabWidget, QGroupBox, QSpinBox, QDoubleSpinBox, QTextEdit, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QScrollArea, QSplitter,
    QDateEdit, QTimeEdit, QFrame, QAbstractItemView, QDialog, QDialogButtonBox
)

from header_widget import build_official_header
import zone_action_plan
from jalali_widgets import JalaliDateEdit
from jalali_utils import format_jalali, convert_dates_in_text, iso_to_jalali, jalali_to_iso, today_jalali
QDateEdit = JalaliDateEdit
from icon_manager import get_icon, set_button_style
from management_monitoring import ManagementMonitoringWidget
from operations_participation import OperationsParticipationWidget
from ui_scroll import scroll_page


def _scroll(widget, min_height=0, min_width=0):
    return scroll_page(widget, min_height=min_height, min_width=min_width)


def _table(headers, stretch_columns=()):
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    for idx in range(len(headers)):
        table.horizontalHeader().setSectionResizeMode(idx, QHeaderView.Stretch if idx in stretch_columns else QHeaderView.ResizeToContents)
    return table


def _date_value(edit):
    return edit.date().toString("yyyy-MM-dd")


class AgencyComboBox(QComboBox):
    """فهرست دستگاه‌های فعال با امکان ورود دستی و سازگاری با API قبلی QLineEdit."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

    def set_agencies(self, names):
        current = self.currentText()
        super().clear()
        self.addItem("")
        self.addItems(sorted({str(name).strip() for name in names if str(name).strip()}))
        self.setEditText(current)

    def text(self):
        return self.currentText()

    def setText(self, value):
        self.setEditText(value or "")

    def clear(self):
        self.setEditText("")


class ActionPlanResultDialog(QDialog):
    """نمایش برنامه عملیاتی تولیدشده برای یک بلوک، با امکان کپی متن.
    این برنامه پیش از این در دیتابیس ذخیره شده؛ این دیالوگ فقط نمایش‌دهنده است."""

    def __init__(self, parent, plan_text, engine):
        super().__init__(parent)
        self.setWindowTitle("برنامه عملیاتی بلوک")
        self.resize(680, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        engine_label = "سرویس هوش مصنوعی متصل‌شده" if engine == "api" else "موتور قانون‌محور آفلاین"
        info = QLabel(f"این برنامه با استفاده از «{engine_label}» تولید و در پرونده این بلوک ذخیره شد.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#555;")
        layout.addWidget(info)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setPlainText(plan_text)
        layout.addWidget(self.text_area, 1)

        buttons = QHBoxLayout()
        copy_btn = QPushButton("کپی متن")
        copy_btn.clicked.connect(self._copy_text)
        buttons.addWidget(copy_btn)
        buttons.addStretch()
        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    def _copy_text(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.text_area.toPlainText())


class NeighborhoodManagementWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.current_zone_id = None
        self.current_issue_id = None
        self.current_action_id = None
        self.current_meeting_id = None
        self.current_resolution_id = None
        self.setWindowTitle("مدیریت محله‌محور — پرونده جامع بلوک")
        self.resize(1420, 920)
        self._build_ui()
        self.refresh_zone_list()

    # ---------------- UI shell ----------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(build_official_header("مدیریت محله‌محور و پیگیری عملیات", self.db))

        toolbar = QFrame()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(18, 8, 18, 8)
        back = QPushButton("بازگشت به داشبورد")
        back.clicked.connect(self.back_requested.emit)
        set_button_style(back, "back", "ghost")
        toolbar_layout.addWidget(back)
        toolbar_layout.addSpacing(15)
        toolbar_layout.addWidget(QLabel("بلوک / محله:"))
        self.zone_combo = QComboBox()
        self.zone_combo.setMinimumWidth(290)
        self.zone_combo.currentIndexChanged.connect(self._zone_changed)
        toolbar_layout.addWidget(self.zone_combo)
        refresh = QPushButton("بروزرسانی اطلاعات")
        refresh.clicked.connect(self.refresh_all)
        set_button_style(refresh, "refresh", "secondary")
        toolbar_layout.addWidget(refresh)
        toolbar_layout.addStretch()
        self.completeness_label = QLabel("وضعیت پرونده: —")
        self.completeness_label.setStyleSheet("font-weight:800; color:#13294b;")
        toolbar_layout.addWidget(self.completeness_label)
        root.addWidget(toolbar)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._build_overview_tab()
        self._build_profile_tab()
        self._build_issues_tab()
        self._build_actions_tab()
        self._build_meetings_tab()
        self.management_monitoring = ManagementMonitoringWidget(self.db)
        self.management_monitoring.data_changed.connect(self._management_data_changed)
        self.tabs.addTab(self.management_monitoring, get_icon("report", "navy"), "کنترل مدیریتی")

        self.operations_participation = OperationsParticipationWidget(self.db)
        self.operations_participation.data_changed.connect(self._operations_data_changed)
        self.tabs.addTab(self.operations_participation, get_icon("pin", "navy"), "عملیات و مشارکت")

    # ---------------- zone handling ----------------
    def refresh_zone_list(self):
        selected = self.current_zone_id
        self.zone_combo.blockSignals(True)
        self.zone_combo.clear()
        zones = self.db.get_zones()
        for zone in zones:
            self.zone_combo.addItem(zone["name"], zone["id"])
        self.zone_combo.blockSignals(False)
        if not zones:
            self.current_zone_id = None
            self.zone_combo.addItem("ابتدا یک بلوک در بخش بلوک‌بندی ایجاد کنید", None)
            self.refresh_all()
            return
        index = 0
        if selected is not None:
            for i in range(self.zone_combo.count()):
                if self.zone_combo.itemData(i) == selected:
                    index = i
                    break
        self.zone_combo.setCurrentIndex(index)
        self.current_zone_id = self.zone_combo.currentData()
        self.refresh_all()

    def open_zone(self, zone_id):
        """انتخاب مستقیم یک بلوک مشخص و نمایش تب پرونده جامع آن؛ برای ورود
        از بیرون (مثلاً از پنجره مقایسه بلوک‌های شهر با دوبار کلیک)."""
        self.current_zone_id = zone_id
        self.refresh_zone_list()
        self.tabs.setCurrentIndex(0)  # تب «پرونده جامع بلوک» همیشه اول است

    def _zone_changed(self):
        self.current_zone_id = self.zone_combo.currentData()
        self.current_issue_id = self.current_action_id = None
        self.current_meeting_id = self.current_resolution_id = None
        self.refresh_all()

    def _require_zone(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "بلوک انتخاب نشده", "ابتدا یک بلوک/محله را انتخاب کنید.")
            return False
        return True

    def refresh_all(self):
        enabled = self.current_zone_id is not None
        self.tabs.setEnabled(enabled)
        if not enabled:
            self.completeness_label.setText("وضعیت پرونده: بدون بلوک")
            return
        self._refresh_agency_combos()
        self._refresh_overview()
        self._load_profile()
        self._refresh_issues()
        self._refresh_actions()
        self._refresh_meetings()
        self._refresh_resolutions()
        self._refresh_link_combos()
        if hasattr(self, "management_monitoring"):
            self.management_monitoring.set_zone(self.current_zone_id)
        if hasattr(self, "operations_participation"):
            self.operations_participation.set_zone(self.current_zone_id)

    def _operations_data_changed(self):
        self._refresh_overview()
        self._refresh_issues()
        self._refresh_link_combos()
        if hasattr(self, "management_monitoring"):
            self.management_monitoring.set_zone(self.current_zone_id)

    def _management_data_changed(self):
        self._refresh_agency_combos()
        if self.current_zone_id is not None:
            self._refresh_overview()

    def _refresh_agency_combos(self):
        names = [item["name"] for item in self.db.get_management_agencies(active_only=True)]
        for field_name in ("issue_office", "action_office", "action_partner", "resolution_office"):
            field = getattr(self, field_name, None)
            if field is not None and hasattr(field, "set_agencies"):
                field.set_agencies(names)

    # ---------------- Overview ----------------
    def _build_overview_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        image_group = QGroupBox("نمای گرافیکی بلوک")
        image_layout = QVBoxLayout(image_group)
        self.snapshot_label = QLabel("تصویر بلوک موجود نیست")
        self.snapshot_label.setAlignment(Qt.AlignCenter)
        self.snapshot_label.setMinimumSize(520, 380)
        self.snapshot_label.setStyleSheet("background:white; border:1px solid #cfd7e3; border-radius:10px;")
        image_layout.addWidget(self.snapshot_label)
        splitter.addWidget(image_group)

        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(8, 0, 0, 0)
        self.summary_cards = {}
        cards_grid = QGridLayout()
        specs = [
            ("households", "خانوار تأییدشده", "home"),
            ("population", "جمعیت تخمینی", "users"),
            ("issues", "مسائل باز", "warning"),
            ("critical", "مسائل فوری/بحرانی", "warning"),
            ("actions", "اقدامات فعال", "check"),
            ("resolutions", "مصوبات باز", "list"),
            ("visits", "بازدیدهای میدانی", "pin"),
            ("citizen", "درخواست مردمی باز", "users"),
        ]
        for i, (key, title, icon) in enumerate(specs):
            card = QFrame()
            card.setObjectName("StatCard")
            cl = QHBoxLayout(card)
            icon_label = QLabel()
            icon_label.setPixmap(get_icon(icon, "gold").pixmap(34, 34))
            cl.addWidget(icon_label)
            tc = QVBoxLayout()
            value = QLabel("۰")
            value.setStyleSheet("font-size:25px; font-weight:900; color:#13294b;")
            tc.addWidget(value)
            tc.addWidget(QLabel(title))
            cl.addLayout(tc)
            self.summary_cards[key] = value
            cards_grid.addWidget(card, i // 2, i % 2)
        info_layout.addLayout(cards_grid)

        detail_group = QGroupBox("خلاصه پرونده بلوک")
        detail_layout = QVBoxLayout(detail_group)
        self.overview_text = QTextEdit()
        self.overview_text.setReadOnly(True)
        detail_layout.addWidget(self.overview_text)

        plan_btn = QPushButton("💡 تولید برنامه عملیاتی هوشمند برای این بلوک")
        plan_btn.setToolTip(
            "بر اساس مسائل، درخواست‌های مردمی و اقدامات جاری این بلوک، یک برنامه "
            "عملیاتی پیشنهادی می‌سازد. این خروجی صرفاً کمکی است و تصمیم نهایی با "
            "کارشناس/مدیر بلوک است."
        )
        plan_btn.clicked.connect(self._on_generate_action_plan)
        detail_layout.addWidget(plan_btn)

        info_layout.addWidget(detail_group, 1)
        splitter.addWidget(info_widget)
        splitter.setSizes([760, 560])
        self.tabs.addTab(_scroll(page, min_height=760), get_icon("home", "navy"), "پرونده جامع بلوک")

    def _refresh_overview(self):
        zone = self.db.get_zone(self.current_zone_id)
        summary = self.db.get_neighborhood_summary(self.current_zone_id)
        profile = summary["profile"]
        values = {
            "households": profile.get("approved_households", 0),
            "population": profile.get("estimated_population", 0),
            "issues": summary.get("issues_open", 0),
            "critical": summary.get("issues_critical", 0),
            "actions": summary.get("actions_active", 0),
            "resolutions": summary.get("resolutions_pending", 0),
            "visits": summary.get("field_visits_total", 0),
            "citizen": summary.get("citizen_requests_open", 0),
        }
        trans = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
        for key, value in values.items():
            self.summary_cards[key].setText(str(value).translate(trans))

        snapshot = self.db.get_zone_snapshot(self.current_zone_id)
        if snapshot and snapshot.get("png_data"):
            pix = QPixmap()
            pix.loadFromData(snapshot["png_data"])
            self.snapshot_label.setPixmap(pix.scaled(self.snapshot_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.snapshot_label.setText("نمای گرافیکی بلوک هنوز ساخته نشده است")

        meeting = self.db.get_zone_meeting_place(self.current_zone_id)
        streets = self.db.get_streets(self.current_zone_id)
        places = self.db.get_places_with_mosques(self.current_zone_id)
        mosques = self.db.get_mosques(zone_id=self.current_zone_id)
        members = self.db.get_council_members(self.current_zone_id)
        area_ha = (zone.get("area_m2") or 0) / 10000
        lines = [
            f"نام بلوک: {zone.get('name')}",
            f"وضعیت داده مکانی: {zone.get('status', '—')}",
            f"مساحت: {area_ha:.2f} هکتار | محیط: {(zone.get('perimeter_m') or 0):.0f} متر",
            f"معابر ثبت‌شده: {len(streets)} | اماکن: {len(places)} | مساجد: {len(mosques)}",
            f"اعضای شورای محله: {len(members)}",
            f"محل جلسه: {(meeting or {}).get('place_name', 'ثبت نشده')}",
            "",
            f"روش برآورد خانوار: {profile.get('estimation_method') or 'ثبت نشده'}",
            f"سطح اطمینان: {profile.get('confidence_level') or '—'}",
            f"جلسات ثبت‌شده: {summary.get('meetings_total', 0)}",
            f"اقدامات تکمیل‌شده: {summary.get('actions_completed', 0)}",
            f"بازدیدهای میدانی: {summary.get('field_visits_total', 0)} | نیازمند پیگیری: {summary.get('field_followups', 0)}",
            f"درخواست‌های مردمی: {summary.get('citizen_requests_total', 0)} | باز: {summary.get('citizen_requests_open', 0)}",
        ]
        self.overview_text.setPlainText("\n".join(lines))
        score_parts = [bool(profile.get("approved_households")), bool(streets), bool(mosques), bool(meeting), bool(members)]
        completeness = int(sum(score_parts) / len(score_parts) * 100)
        self.completeness_label.setText(f"تکمیل پرونده: {completeness}٪")

    def _on_generate_action_plan(self):
        if self.current_zone_id is None:
            QMessageBox.warning(self, "خطا", "ابتدا یک بلوک را انتخاب کنید.")
            return
        context = self.db.get_zone_action_plan_context(self.current_zone_id)
        if not context:
            QMessageBox.warning(self, "خطا", "اطلاعات این بلوک یافت نشد.")
            return

        ai_settings = self.db.get_smart_triage_settings()
        api_url = ai_settings["api_url"] if ai_settings["enabled"] else ""
        api_key = ai_settings["api_key"] if ai_settings["enabled"] else ""

        plan_text, engine = zone_action_plan.generate(context, api_url=api_url, api_key=api_key)
        self.db.save_zone_action_plan(self.current_zone_id, engine, plan_text)

        dialog = ActionPlanResultDialog(self, plan_text, engine)
        dialog.exec_()

    # ---------------- Population/profile ----------------
    def _build_profile_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 18)
        group = QGroupBox("جمعیت، خانوار و شاخص‌های اجتماعی")
        form = QGridLayout(group)
        self.profile_fields = {}
        numeric_specs = [
            ("residential_buildings", "ساختمان مسکونی"), ("residential_units", "واحد مسکونی"),
            ("occupied_units", "واحد دارای سکنه"), ("vacant_units", "واحد خالی"),
            ("estimated_households", "خانوار محاسبه‌شده"), ("field_households", "خانوار ثبت میدانی"),
            ("approved_households", "خانوار نهایی تأییدشده"), ("estimated_population", "جمعیت تخمینی"),
            ("elderly_count", "سالمندان"), ("children_count", "کودکان"),
            ("disabled_count", "افراد دارای معلولیت"), ("vulnerable_households", "خانوار نیازمند حمایت"),
            ("female_headed_households", "زنان سرپرست خانوار"),
        ]
        for idx, (key, title) in enumerate(numeric_specs):
            spin = QSpinBox()
            spin.setRange(0, 1000000)
            self.profile_fields[key] = spin
            row, col = divmod(idx, 2)
            form.addWidget(QLabel(title + ":"), row, col * 2)
            form.addWidget(spin, row, col * 2 + 1)

        row = (len(numeric_specs) + 1) // 2
        self.avg_household_size = QDoubleSpinBox()
        self.avg_household_size.setRange(0, 20)
        self.avg_household_size.setDecimals(2)
        self.avg_household_size.setValue(3.3)
        form.addWidget(QLabel("میانگین بعد خانوار:"), row, 0)
        form.addWidget(self.avg_household_size, row, 1)
        self.estimation_method = QComboBox()
        self.estimation_method.addItems(["شمارش میدانی", "اطلاعات شهرداری", "انشعابات خدماتی", "اطلاعات شورای محله", "تخمین GIS", "روش ترکیبی"])
        form.addWidget(QLabel("روش برآورد:"), row, 2)
        form.addWidget(self.estimation_method, row, 3)

        row += 1
        self.confidence_level = QComboBox()
        self.confidence_level.addItems(["زیاد", "متوسط", "کم"])
        form.addWidget(QLabel("سطح اطمینان:"), row, 0)
        form.addWidget(self.confidence_level, row, 1)
        self.profile_updated = QLabel("آخرین بروزرسانی: —")
        form.addWidget(self.profile_updated, row, 2, 1, 2)

        row += 1
        self.profile_notes = QTextEdit()
        self.profile_notes.setPlaceholderText("توضیح روش شمارش، منبع آمار، مغایرت‌ها و نکات بازبینی...")
        self.profile_notes.setMaximumHeight(110)
        form.addWidget(QLabel("یادداشت:"), row, 0)
        form.addWidget(self.profile_notes, row, 1, 1, 3)
        layout.addWidget(group)

        actions = QHBoxLayout()
        calc = QPushButton("محاسبه پیشنهادی خانوار و جمعیت")
        calc.clicked.connect(self._calculate_profile)
        set_button_style(calc, "info", "secondary")
        actions.addWidget(calc)
        save = QPushButton("ذخیره پرونده جمعیتی")
        save.clicked.connect(self._save_profile)
        set_button_style(save, "save", "primary")
        actions.addWidget(save)
        actions.addStretch()
        layout.addLayout(actions)

        note = QLabel("عدد نهایی تأییدشده مبنای گزارش‌های مدیریتی است. محاسبه پیشنهادی فقط یک ابزار کمکی است و باید توسط مسئول محله بازبینی شود.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#5b6472; padding:10px;")
        layout.addWidget(note)
        layout.addStretch()
        self.tabs.addTab(_scroll(content, min_height=700), get_icon("users", "navy"), "جمعیت و خانوار")

    def _calculate_profile(self):
        occupied = self.profile_fields["occupied_units"].value()
        residential_units = self.profile_fields["residential_units"].value()
        estimated = occupied if occupied else int(residential_units * 0.9)
        self.profile_fields["estimated_households"].setValue(estimated)
        if self.profile_fields["approved_households"].value() == 0:
            field = self.profile_fields["field_households"].value()
            self.profile_fields["approved_households"].setValue(field or estimated)
        approved = self.profile_fields["approved_households"].value()
        self.profile_fields["estimated_population"].setValue(round(approved * self.avg_household_size.value()))

    def _load_profile(self):
        profile = self.db.get_zone_profile(self.current_zone_id)
        for key, widget in self.profile_fields.items():
            widget.setValue(int(profile.get(key) or 0))
        self.avg_household_size.setValue(float(profile.get("average_household_size") or 3.3))
        method = profile.get("estimation_method") or "روش ترکیبی"
        idx = self.estimation_method.findText(method)
        self.estimation_method.setCurrentIndex(idx if idx >= 0 else 0)
        confidence = profile.get("confidence_level") or "متوسط"
        idx = self.confidence_level.findText(confidence)
        self.confidence_level.setCurrentIndex(idx if idx >= 0 else 1)
        self.profile_notes.setPlainText(profile.get("notes") or "")
        self.profile_updated.setText("آخرین بروزرسانی: " + (format_jalali(profile.get("updated_at")) or "—"))

    def _save_profile(self):
        if not self._require_zone():
            return
        data = {key: widget.value() for key, widget in self.profile_fields.items()}
        data.update({
            "average_household_size": self.avg_household_size.value(),
            "estimation_method": self.estimation_method.currentText(),
            "confidence_level": self.confidence_level.currentText(),
            "notes": self.profile_notes.toPlainText().strip(),
        })
        self.db.save_zone_profile(self.current_zone_id, **data)
        self.refresh_all()
        QMessageBox.information(self, "ذخیره شد", "پرونده جمعیتی بلوک با موفقیت ذخیره شد.")

    # ---------------- Issues ----------------
    def _build_issues_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter, 1)

        form_box = QGroupBox("ثبت یا ویرایش مسئله و نیاز محله")
        form = QGridLayout(form_box)
        self.issue_title = QLineEdit()
        self.issue_category = QComboBox(); self.issue_category.addItems(self.db.ISSUE_CATEGORIES)
        self.issue_description = QTextEdit(); self.issue_description.setMaximumHeight(85)
        self.issue_office = AgencyComboBox()
        self.issue_urgency = QSpinBox(); self.issue_urgency.setRange(1, 5); self.issue_urgency.setValue(3)
        self.issue_severity = QSpinBox(); self.issue_severity.setRange(1, 5); self.issue_severity.setValue(3)
        self.issue_safety = QSpinBox(); self.issue_safety.setRange(1, 5); self.issue_safety.setValue(1)
        self.issue_households = QSpinBox(); self.issue_households.setRange(0, 1000000)
        self.issue_status = QComboBox(); self.issue_status.addItems(self.db.ISSUE_STATUSES)
        self.issue_source = QLineEdit(); self.issue_source.setPlaceholderText("شورای محله، بازدید میدانی، درخواست مردمی...")
        self.issue_location = QLineEdit(); self.issue_location.setPlaceholderText("نام خیابان/کوچه یا نشانی")
        self.issue_due = QDateEdit(QDate.currentDate()); self.issue_due.setCalendarPopup(True)
        form.addWidget(QLabel("عنوان:*"), 0, 0); form.addWidget(self.issue_title, 0, 1)
        form.addWidget(QLabel("دسته:"), 0, 2); form.addWidget(self.issue_category, 0, 3)
        form.addWidget(QLabel("شرح:"), 1, 0); form.addWidget(self.issue_description, 1, 1, 1, 3)
        form.addWidget(QLabel("دستگاه مرتبط:"), 2, 0); form.addWidget(self.issue_office, 2, 1)
        form.addWidget(QLabel("موقعیت:"), 2, 2); form.addWidget(self.issue_location, 2, 3)
        form.addWidget(QLabel("فوریت ۱ تا ۵:"), 3, 0); form.addWidget(self.issue_urgency, 3, 1)
        form.addWidget(QLabel("شدت ۱ تا ۵:"), 3, 2); form.addWidget(self.issue_severity, 3, 3)
        form.addWidget(QLabel("ریسک ایمنی:"), 4, 0); form.addWidget(self.issue_safety, 4, 1)
        form.addWidget(QLabel("خانوار تحت تأثیر:"), 4, 2); form.addWidget(self.issue_households, 4, 3)
        form.addWidget(QLabel("وضعیت:"), 5, 0); form.addWidget(self.issue_status, 5, 1)
        form.addWidget(QLabel("منبع گزارش:"), 5, 2); form.addWidget(self.issue_source, 5, 3)
        form.addWidget(QLabel("مهلت پیگیری:"), 6, 0); form.addWidget(self.issue_due, 6, 1)
        btns = QHBoxLayout()
        save = QPushButton("ثبت مسئله جدید"); save.clicked.connect(self._save_issue); set_button_style(save, "plus", "success")
        update = QPushButton("ویرایش مسئله انتخاب‌شده"); update.clicked.connect(self._update_issue); set_button_style(update, "edit", "secondary")
        clear = QPushButton("پاک‌کردن فرم"); clear.clicked.connect(self._clear_issue_form); set_button_style(clear, "refresh", "ghost")
        btns.addWidget(save); btns.addWidget(update); btns.addWidget(clear); btns.addStretch()
        form.addLayout(btns, 6, 2, 1, 2)
        splitter.addWidget(form_box)

        table_box = QGroupBox("فهرست مسائل بر اساس امتیاز اولویت")
        table_layout = QVBoxLayout(table_box)
        self.issues_table = _table(["شناسه", "عنوان", "دسته", "امتیاز", "سطح", "وضعیت", "دستگاه", "خانوار"], (1, 6))
        self.issues_table.itemSelectionChanged.connect(self._issue_selected)
        table_layout.addWidget(self.issues_table)
        row = QHBoxLayout()
        convert = QPushButton("تبدیل مسئله به اقدام"); convert.clicked.connect(self._convert_issue_to_action); set_button_style(convert, "check", "primary")
        delete = QPushButton("حذف مسئله"); delete.clicked.connect(self._delete_issue); set_button_style(delete, "delete", "danger")
        row.addWidget(convert); row.addWidget(delete); row.addStretch()
        table_layout.addLayout(row)
        splitter.addWidget(table_box)
        splitter.setSizes([360, 420])
        self.tabs.addTab(_scroll(page, min_height=780), get_icon("warning", "navy"), "مسائل و نیازها")

    def _issue_payload(self):
        return dict(
            title=self.issue_title.text().strip(), category=self.issue_category.currentText(),
            description=self.issue_description.toPlainText().strip(), related_office=self.issue_office.text().strip(),
            urgency=self.issue_urgency.value(), severity=self.issue_severity.value(),
            affected_households=self.issue_households.value(), safety_risk=self.issue_safety.value(),
            status=self.issue_status.currentText(), source=self.issue_source.text().strip() or "ثبت سامانه",
            location_text=self.issue_location.text().strip(), due_date=_date_value(self.issue_due),
        )

    def _save_issue(self):
        if not self._require_zone(): return
        data = self._issue_payload()
        if not data["title"]:
            QMessageBox.warning(self, "عنوان الزامی", "عنوان مسئله را وارد کنید."); return
        self.db.add_neighborhood_issue(self.current_zone_id, **data)
        self._clear_issue_form(); self.refresh_all()

    def _update_issue(self):
        if not self.current_issue_id:
            QMessageBox.warning(self, "انتخاب مسئله", "یک مسئله را از جدول انتخاب کنید."); return
        data = self._issue_payload()
        if not data["title"]: return
        self.db.update_neighborhood_issue(self.current_issue_id, **data)
        self.refresh_all()

    def _delete_issue(self):
        if not self.current_issue_id:
            QMessageBox.warning(self, "انتخاب مسئله", "یک مسئله را انتخاب کنید."); return
        if QMessageBox.question(self, "حذف مسئله", "مسئله انتخاب‌شده حذف شود؟", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_neighborhood_issue(self.current_issue_id)
            self._clear_issue_form(); self.refresh_all()

    def _clear_issue_form(self):
        self.current_issue_id = None
        self.issue_title.clear(); self.issue_description.clear(); self.issue_office.clear(); self.issue_location.clear(); self.issue_source.clear()
        self.issue_category.setCurrentIndex(0); self.issue_urgency.setValue(3); self.issue_severity.setValue(3); self.issue_safety.setValue(1); self.issue_households.setValue(0)
        self.issue_status.setCurrentIndex(0); self.issue_due.setDate(QDate.currentDate())
        self.issues_table.clearSelection()

    def _refresh_issues(self):
        self._issues = self.db.get_neighborhood_issues(self.current_zone_id)
        self.issues_table.setRowCount(len(self._issues))
        for row, item in enumerate(self._issues):
            vals = [item["id"], item["title"], item["category"], item["priority_score"], item["priority_level"], item["status"], item["related_office"] or "—", item["affected_households"]]
            for col, val in enumerate(vals):
                self.issues_table.setItem(row, col, QTableWidgetItem(convert_dates_in_text(str(val))))

    def _issue_selected(self):
        row = self.issues_table.currentRow()
        if row < 0 or row >= len(getattr(self, "_issues", [])): return
        issue = self._issues[row]; self.current_issue_id = issue["id"]
        self.issue_title.setText(issue["title"]); self.issue_description.setPlainText(issue["description"] or "")
        self.issue_office.setText(issue["related_office"] or ""); self.issue_location.setText(issue["location_text"] or ""); self.issue_source.setText(issue["source"] or "")
        for combo, text in [(self.issue_category, issue["category"]), (self.issue_status, issue["status"])]:
            idx = combo.findText(text); combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.issue_urgency.setValue(issue["urgency"]); self.issue_severity.setValue(issue["severity"]); self.issue_safety.setValue(issue["safety_risk"]); self.issue_households.setValue(issue["affected_households"])
        if issue.get("due_date"): self.issue_due.setDate(QDate.fromString(issue["due_date"], "yyyy-MM-dd"))

    def _convert_issue_to_action(self):
        if not self.current_issue_id:
            QMessageBox.warning(self, "انتخاب مسئله", "ابتدا یک مسئله را انتخاب کنید."); return
        issue = self.db.get_neighborhood_issue(self.current_issue_id)
        self.tabs.setCurrentIndex(3)
        self.action_title.setText("اقدام برای: " + issue["title"])
        self.action_description.setPlainText(issue["description"] or "")
        self.action_office.setText(issue["related_office"] or "")
        idx = self.action_issue_combo.findData(issue["id"])
        self.action_issue_combo.setCurrentIndex(idx if idx >= 0 else 0)

    # ---------------- Actions ----------------
    def _build_actions_tab(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(16, 14, 16, 14)
        splitter = QSplitter(Qt.Vertical); layout.addWidget(splitter, 1)
        box = QGroupBox("برنامه‌ریزی و پایش اقدام اجرایی"); form = QGridLayout(box)
        self.action_issue_combo = QComboBox(); self.action_title = QLineEdit(); self.action_description = QTextEdit(); self.action_description.setMaximumHeight(72)
        self.action_person = QLineEdit(); self.action_office = AgencyComboBox(); self.action_partner = AgencyComboBox()
        self.action_start = QDateEdit(QDate.currentDate()); self.action_start.setCalendarPopup(True)
        self.action_end = QDateEdit(QDate.currentDate().addDays(30)); self.action_end.setCalendarPopup(True)
        self.action_progress = QSpinBox(); self.action_progress.setRange(0, 100); self.action_progress.setSuffix("٪")
        self.action_estimated_cost = QDoubleSpinBox(); self.action_estimated_cost.setRange(0, 1e15); self.action_estimated_cost.setDecimals(0); self.action_estimated_cost.setSuffix(" ریال")
        self.action_actual_cost = QDoubleSpinBox(); self.action_actual_cost.setRange(0, 1e15); self.action_actual_cost.setDecimals(0); self.action_actual_cost.setSuffix(" ریال")
        self.action_funding = QLineEdit(); self.action_contractor = QLineEdit(); self.action_status = QComboBox(); self.action_status.addItems(self.db.ACTION_STATUSES)
        self.action_obstacles = QTextEdit(); self.action_obstacles.setMaximumHeight(55); self.action_result = QTextEdit(); self.action_result.setMaximumHeight(55)
        fields = [
            ("مسئله مرتبط:", self.action_issue_combo, 0, 0), ("عنوان اقدام:*", self.action_title, 0, 2),
            ("شرح:", self.action_description, 1, 0, 1, 4), ("مسئول اجرا:", self.action_person, 2, 0), ("دستگاه مسئول:", self.action_office, 2, 2),
            ("دستگاه همکار:", self.action_partner, 3, 0), ("پیمانکار/مجری:", self.action_contractor, 3, 2),
            ("شروع:", self.action_start, 4, 0), ("پایان برنامه:", self.action_end, 4, 2),
            ("درصد پیشرفت:", self.action_progress, 5, 0), ("وضعیت:", self.action_status, 5, 2),
            ("هزینه برآوردی:", self.action_estimated_cost, 6, 0), ("هزینه واقعی:", self.action_actual_cost, 6, 2),
            ("منبع اعتبار:", self.action_funding, 7, 0), ("موانع:", self.action_obstacles, 8, 0, 1, 4), ("نتیجه:", self.action_result, 9, 0, 1, 4),
        ]
        for spec in fields:
            label, widget, row, col, *span = spec; form.addWidget(QLabel(label), row, col); form.addWidget(widget, row, col + 1, *(span or [1, 1]))
        btns = QHBoxLayout();
        add = QPushButton("ثبت اقدام جدید"); add.clicked.connect(self._save_action); set_button_style(add, "plus", "success")
        upd = QPushButton("ویرایش اقدام انتخاب‌شده"); upd.clicked.connect(self._update_action); set_button_style(upd, "edit", "secondary")
        clear = QPushButton("پاک‌کردن فرم"); clear.clicked.connect(self._clear_action_form); set_button_style(clear, "refresh", "ghost")
        btns.addWidget(add); btns.addWidget(upd); btns.addWidget(clear); btns.addStretch(); form.addLayout(btns, 10, 0, 1, 4)
        splitter.addWidget(box)
        table_box = QGroupBox("اقدامات بلوک"); tl = QVBoxLayout(table_box)
        self.actions_table = _table(["شناسه", "عنوان", "مسئله", "مسئول", "وضعیت", "پیشرفت", "پایان", "هزینه واقعی"], (1, 2, 3))
        self.actions_table.itemSelectionChanged.connect(self._action_selected); tl.addWidget(self.actions_table)
        delete = QPushButton("حذف اقدام"); delete.clicked.connect(self._delete_action); set_button_style(delete, "delete", "danger")
        row = QHBoxLayout(); row.addWidget(delete); row.addStretch(); tl.addLayout(row)
        splitter.addWidget(table_box); splitter.setSizes([430, 350])
        self.tabs.addTab(_scroll(page, min_height=800), get_icon("check", "navy"), "اقدامات اجرایی")

    def _action_payload(self):
        return dict(issue_id=self.action_issue_combo.currentData(), title=self.action_title.text().strip(),
                    description=self.action_description.toPlainText().strip(), responsible_person=self.action_person.text().strip(),
                    responsible_office=self.action_office.text().strip(), partner_office=self.action_partner.text().strip(),
                    planned_start=_date_value(self.action_start), planned_end=_date_value(self.action_end),
                    progress_percent=self.action_progress.value(), estimated_cost=self.action_estimated_cost.value(),
                    actual_cost=self.action_actual_cost.value(), funding_source=self.action_funding.text().strip(),
                    contractor=self.action_contractor.text().strip(), status=self.action_status.currentText(),
                    obstacles=self.action_obstacles.toPlainText().strip(), result_summary=self.action_result.toPlainText().strip())

    def _save_action(self):
        if not self._require_zone(): return
        data = self._action_payload()
        if not data["title"]: QMessageBox.warning(self, "عنوان الزامی", "عنوان اقدام را وارد کنید."); return
        self.db.add_neighborhood_action(self.current_zone_id, **data); self._clear_action_form(); self.refresh_all()

    def _update_action(self):
        if not self.current_action_id: QMessageBox.warning(self, "انتخاب اقدام", "یک اقدام را انتخاب کنید."); return
        self.db.update_neighborhood_action(self.current_action_id, **self._action_payload()); self.refresh_all()

    def _delete_action(self):
        if not self.current_action_id: return
        if QMessageBox.question(self, "حذف اقدام", "اقدام انتخاب‌شده حذف شود؟", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.db.delete_neighborhood_action(self.current_action_id); self._clear_action_form(); self.refresh_all()

    def _clear_action_form(self):
        self.current_action_id = None; self.action_title.clear(); self.action_description.clear(); self.action_person.clear(); self.action_office.clear(); self.action_partner.clear(); self.action_funding.clear(); self.action_contractor.clear(); self.action_obstacles.clear(); self.action_result.clear(); self.action_progress.setValue(0); self.action_estimated_cost.setValue(0); self.action_actual_cost.setValue(0); self.action_status.setCurrentIndex(0); self.action_issue_combo.setCurrentIndex(0); self.actions_table.clearSelection()

    def _refresh_actions(self):
        self._actions = self.db.get_neighborhood_actions(self.current_zone_id); self.actions_table.setRowCount(len(self._actions))
        for row, a in enumerate(self._actions):
            vals = [a["id"], a["title"], a.get("issue_title") or "—", a["responsible_person"] or a["responsible_office"] or "—", a["status"], f"{a['progress_percent']}٪", a["planned_end"] or "—", f"{a['actual_cost']:,.0f}"]
            for col, val in enumerate(vals): self.actions_table.setItem(row, col, QTableWidgetItem(convert_dates_in_text(str(val))))

    def _action_selected(self):
        row = self.actions_table.currentRow()
        if row < 0 or row >= len(getattr(self, "_actions", [])): return
        a = self._actions[row]; self.current_action_id = a["id"]
        idx = self.action_issue_combo.findData(a["issue_id"]); self.action_issue_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.action_title.setText(a["title"]); self.action_description.setPlainText(a["description"] or ""); self.action_person.setText(a["responsible_person"] or ""); self.action_office.setText(a["responsible_office"] or ""); self.action_partner.setText(a["partner_office"] or ""); self.action_funding.setText(a["funding_source"] or ""); self.action_contractor.setText(a["contractor"] or ""); self.action_obstacles.setPlainText(a["obstacles"] or ""); self.action_result.setPlainText(a["result_summary"] or ""); self.action_progress.setValue(a["progress_percent"] or 0); self.action_estimated_cost.setValue(float(a["estimated_cost"] or 0)); self.action_actual_cost.setValue(float(a["actual_cost"] or 0))
        for edit, value in [(self.action_start, a["planned_start"]), (self.action_end, a["planned_end"])]:
            if value: edit.setDate(QDate.fromString(value, "yyyy-MM-dd"))
        idx = self.action_status.findText(a["status"]); self.action_status.setCurrentIndex(idx if idx >= 0 else 0)

    # ---------------- Meetings and resolutions ----------------
    def _build_meetings_tab(self):
        nested = QTabWidget()
        # meeting page
        meeting_page = QWidget(); ml = QVBoxLayout(meeting_page); ml.setContentsMargins(16, 14, 16, 14)
        box = QGroupBox("ثبت جلسه شورای محله"); form = QGridLayout(box)
        self.meeting_title = QLineEdit(); self.meeting_date = QDateEdit(QDate.currentDate()); self.meeting_date.setCalendarPopup(True); self.meeting_time = QTimeEdit(QTime.currentTime()); self.meeting_place = QLineEdit(); self.meeting_agenda = QTextEdit(); self.meeting_attendees = QTextEdit(); self.meeting_absentees = QTextEdit(); self.meeting_minutes = QTextEdit(); self.meeting_status = QComboBox(); self.meeting_status.addItems(["برنامه‌ریزی‌شده", "برگزارشده", "لغوشده"])
        for w in (self.meeting_agenda, self.meeting_attendees, self.meeting_absentees): w.setMaximumHeight(60)
        self.meeting_minutes.setMaximumHeight(85)
        form.addWidget(QLabel("عنوان جلسه:*"),0,0); form.addWidget(self.meeting_title,0,1); form.addWidget(QLabel("وضعیت:"),0,2); form.addWidget(self.meeting_status,0,3)
        form.addWidget(QLabel("تاریخ:"),1,0); form.addWidget(self.meeting_date,1,1); form.addWidget(QLabel("ساعت:"),1,2); form.addWidget(self.meeting_time,1,3)
        form.addWidget(QLabel("محل جلسه:"),2,0); form.addWidget(self.meeting_place,2,1,1,3)
        form.addWidget(QLabel("دستور جلسه:"),3,0); form.addWidget(self.meeting_agenda,3,1,1,3)
        form.addWidget(QLabel("حاضرین:"),4,0); form.addWidget(self.meeting_attendees,4,1); form.addWidget(QLabel("غایبین:"),4,2); form.addWidget(self.meeting_absentees,4,3)
        form.addWidget(QLabel("صورت‌جلسه:"),5,0); form.addWidget(self.meeting_minutes,5,1,1,3)
        btns=QHBoxLayout(); add=QPushButton("ثبت جلسه جدید"); add.clicked.connect(self._save_meeting); set_button_style(add,"plus","success"); upd=QPushButton("ویرایش جلسه"); upd.clicked.connect(self._update_meeting); set_button_style(upd,"edit","secondary"); clear=QPushButton("پاک‌کردن فرم"); clear.clicked.connect(self._clear_meeting_form); set_button_style(clear,"refresh","ghost"); btns.addWidget(add); btns.addWidget(upd); btns.addWidget(clear); btns.addStretch(); form.addLayout(btns,6,0,1,4)
        ml.addWidget(box)
        self.meetings_table = _table(["شناسه", "عنوان", "تاریخ", "ساعت", "محل", "وضعیت", "مصوبات"], (1,4)); self.meetings_table.itemSelectionChanged.connect(self._meeting_selected); ml.addWidget(self.meetings_table,1)
        row=QHBoxLayout(); delete=QPushButton("حذف جلسه"); delete.clicked.connect(self._delete_meeting); set_button_style(delete,"delete","danger"); row.addWidget(delete); row.addStretch(); ml.addLayout(row)
        nested.addTab(_scroll(meeting_page, min_height=760), get_icon("users","navy"), "جلسات")

        # resolution page
        resolution_page=QWidget(); rl=QVBoxLayout(resolution_page); rl.setContentsMargins(16,14,16,14)
        rbox=QGroupBox("ثبت مصوبه و تعیین مسئول پیگیری"); rf=QGridLayout(rbox)
        self.resolution_meeting=QComboBox(); self.resolution_title=QLineEdit(); self.resolution_description=QTextEdit(); self.resolution_description.setMaximumHeight(75); self.resolution_office=AgencyComboBox(); self.resolution_person=QLineEdit(); self.resolution_due=QDateEdit(QDate.currentDate().addDays(14)); self.resolution_due.setCalendarPopup(True); self.resolution_status=QComboBox(); self.resolution_status.addItems(self.db.RESOLUTION_STATUSES); self.resolution_issue=QComboBox(); self.resolution_action=QComboBox()
        rf.addWidget(QLabel("جلسه:*"),0,0); rf.addWidget(self.resolution_meeting,0,1); rf.addWidget(QLabel("عنوان مصوبه:*"),0,2); rf.addWidget(self.resolution_title,0,3)
        rf.addWidget(QLabel("شرح:"),1,0); rf.addWidget(self.resolution_description,1,1,1,3)
        rf.addWidget(QLabel("دستگاه مسئول:"),2,0); rf.addWidget(self.resolution_office,2,1); rf.addWidget(QLabel("شخص مسئول:"),2,2); rf.addWidget(self.resolution_person,2,3)
        rf.addWidget(QLabel("مهلت:"),3,0); rf.addWidget(self.resolution_due,3,1); rf.addWidget(QLabel("وضعیت:"),3,2); rf.addWidget(self.resolution_status,3,3)
        rf.addWidget(QLabel("مسئله مرتبط:"),4,0); rf.addWidget(self.resolution_issue,4,1); rf.addWidget(QLabel("اقدام مرتبط:"),4,2); rf.addWidget(self.resolution_action,4,3)
        rbtn=QHBoxLayout(); add=QPushButton("ثبت مصوبه جدید"); add.clicked.connect(self._save_resolution); set_button_style(add,"plus","success"); upd=QPushButton("ویرایش مصوبه"); upd.clicked.connect(self._update_resolution); set_button_style(upd,"edit","secondary"); clear=QPushButton("پاک‌کردن فرم"); clear.clicked.connect(self._clear_resolution_form); set_button_style(clear,"refresh","ghost"); rbtn.addWidget(add); rbtn.addWidget(upd); rbtn.addWidget(clear); rbtn.addStretch(); rf.addLayout(rbtn,5,0,1,4)
        rl.addWidget(rbox)
        self.resolutions_table=_table(["شناسه","جلسه","عنوان","مسئول","مهلت","وضعیت","مسئله/اقدام"],(1,2,3,6)); self.resolutions_table.itemSelectionChanged.connect(self._resolution_selected); rl.addWidget(self.resolutions_table,1)
        row=QHBoxLayout(); delete=QPushButton("حذف مصوبه"); delete.clicked.connect(self._delete_resolution); set_button_style(delete,"delete","danger"); row.addWidget(delete); row.addStretch(); rl.addLayout(row)
        # حذف آیکون مستقل «مصوبات و پیگیری»؛ اطلاعات مصوبات همچنان در صورتجلسات/دیتابیس حفظ می‌شود.
        self.tabs.addTab(nested, get_icon("users","navy"), "جلسات و مصوبات")

    def _meeting_payload(self):
        return dict(title=self.meeting_title.text().strip(), meeting_date=_date_value(self.meeting_date), start_time=self.meeting_time.time().toString("HH:mm"), place_name=self.meeting_place.text().strip(), agenda=self.meeting_agenda.toPlainText().strip(), attendees=self.meeting_attendees.toPlainText().strip(), absentees=self.meeting_absentees.toPlainText().strip(), minutes_text=self.meeting_minutes.toPlainText().strip(), status=self.meeting_status.currentText())
    def _save_meeting(self):
        if not self._require_zone(): return
        d=self._meeting_payload()
        if not d["title"]: QMessageBox.warning(self,"عنوان الزامی","عنوان جلسه را وارد کنید."); return
        self.db.add_neighborhood_meeting(self.current_zone_id,**d); self._clear_meeting_form(); self.refresh_all()
    def _update_meeting(self):
        if not self.current_meeting_id: QMessageBox.warning(self,"انتخاب جلسه","یک جلسه را انتخاب کنید."); return
        self.db.update_neighborhood_meeting(self.current_meeting_id,**self._meeting_payload()); self.refresh_all()
    def _delete_meeting(self):
        if self.current_meeting_id and QMessageBox.question(self,"حذف جلسه","جلسه و تمام مصوبات آن حذف شود؟",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            self.db.delete_neighborhood_meeting(self.current_meeting_id); self._clear_meeting_form(); self.refresh_all()
    def _clear_meeting_form(self):
        self.current_meeting_id=None; self.meeting_title.clear(); self.meeting_place.clear(); self.meeting_agenda.clear(); self.meeting_attendees.clear(); self.meeting_absentees.clear(); self.meeting_minutes.clear(); self.meeting_date.setDate(QDate.currentDate()); self.meeting_time.setTime(QTime.currentTime()); self.meeting_status.setCurrentIndex(0); self.meetings_table.clearSelection()
    def _refresh_meetings(self):
        self._meetings=self.db.get_neighborhood_meetings(self.current_zone_id); resolutions=self.db.get_neighborhood_resolutions(zone_id=self.current_zone_id); counts={m["id"]:0 for m in self._meetings}
        for r in resolutions: counts[r["meeting_id"]]=counts.get(r["meeting_id"],0)+1
        self.meetings_table.setRowCount(len(self._meetings))
        for row,m in enumerate(self._meetings):
            vals=[m["id"],m["title"],m["meeting_date"] or "—",m["start_time"] or "—",m["place_name"] or "—",m["status"],counts.get(m["id"],0)]
            for col,val in enumerate(vals): self.meetings_table.setItem(row,col,QTableWidgetItem(convert_dates_in_text(str(val))))
    def _meeting_selected(self):
        row=self.meetings_table.currentRow()
        if row<0 or row>=len(getattr(self,"_meetings",[])): return
        m=self._meetings[row]; self.current_meeting_id=m["id"]; self.meeting_title.setText(m["title"]); self.meeting_place.setText(m["place_name"] or ""); self.meeting_agenda.setPlainText(m["agenda"] or ""); self.meeting_attendees.setPlainText(m["attendees"] or ""); self.meeting_absentees.setPlainText(m["absentees"] or ""); self.meeting_minutes.setPlainText(m["minutes_text"] or "")
        if m["meeting_date"]: self.meeting_date.setDate(QDate.fromString(m["meeting_date"],"yyyy-MM-dd"))
        if m["start_time"]: self.meeting_time.setTime(QTime.fromString(m["start_time"],"HH:mm"))
        idx=self.meeting_status.findText(m["status"]); self.meeting_status.setCurrentIndex(idx if idx>=0 else 0)

    def _resolution_payload(self):
        return dict(meeting_id=self.resolution_meeting.currentData(), title=self.resolution_title.text().strip(), description=self.resolution_description.toPlainText().strip(), responsible_office=self.resolution_office.text().strip(), responsible_person=self.resolution_person.text().strip(), due_date=_date_value(self.resolution_due), status=self.resolution_status.currentText(), linked_issue_id=self.resolution_issue.currentData(), linked_action_id=self.resolution_action.currentData())
    def _save_resolution(self):
        if not self._require_zone(): return
        d=self._resolution_payload()
        if not d["meeting_id"] or not d["title"]: QMessageBox.warning(self,"اطلاعات ناقص","جلسه و عنوان مصوبه الزامی است."); return
        meeting_id=d.pop("meeting_id"); self.db.add_neighborhood_resolution(meeting_id,self.current_zone_id,**d); self._clear_resolution_form(); self.refresh_all()
    def _update_resolution(self):
        if not self.current_resolution_id: QMessageBox.warning(self,"انتخاب مصوبه","یک مصوبه را انتخاب کنید."); return
        d=self._resolution_payload(); d.pop("meeting_id",None); self.db.update_neighborhood_resolution(self.current_resolution_id,**d); self.refresh_all()
    def _delete_resolution(self):
        if self.current_resolution_id and QMessageBox.question(self,"حذف مصوبه","مصوبه انتخاب‌شده حذف شود؟",QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            self.db.delete_neighborhood_resolution(self.current_resolution_id); self._clear_resolution_form(); self.refresh_all()
    def _clear_resolution_form(self):
        self.current_resolution_id=None; self.resolution_title.clear(); self.resolution_description.clear(); self.resolution_office.clear(); self.resolution_person.clear(); self.resolution_due.setDate(QDate.currentDate().addDays(14)); self.resolution_status.setCurrentIndex(0); self.resolution_meeting.setCurrentIndex(0); self.resolution_issue.setCurrentIndex(0); self.resolution_action.setCurrentIndex(0); self.resolutions_table.clearSelection()
    def _refresh_resolutions(self):
        self._resolutions=self.db.get_neighborhood_resolutions(zone_id=self.current_zone_id); self.resolutions_table.setRowCount(len(self._resolutions))
        for row,r in enumerate(self._resolutions):
            linked=[]
            if r["linked_issue_id"]: linked.append(f"مسئله {r['linked_issue_id']}")
            if r["linked_action_id"]: linked.append(f"اقدام {r['linked_action_id']}")
            vals=[r["id"],r["meeting_title"],r["title"],r["responsible_person"] or r["responsible_office"] or "—",r["due_date"] or "—",r["status"]," / ".join(linked) or "—"]
            for col,val in enumerate(vals): self.resolutions_table.setItem(row,col,QTableWidgetItem(convert_dates_in_text(str(val))))
    def _resolution_selected(self):
        row=self.resolutions_table.currentRow()
        if row<0 or row>=len(getattr(self,"_resolutions",[])): return
        r=self._resolutions[row]; self.current_resolution_id=r["id"]
        for combo,value in [(self.resolution_meeting,r["meeting_id"]),(self.resolution_issue,r["linked_issue_id"]),(self.resolution_action,r["linked_action_id"])]:
            idx=combo.findData(value); combo.setCurrentIndex(idx if idx>=0 else 0)
        self.resolution_title.setText(r["title"]); self.resolution_description.setPlainText(r["description"] or ""); self.resolution_office.setText(r["responsible_office"] or ""); self.resolution_person.setText(r["responsible_person"] or "")
        if r["due_date"]: self.resolution_due.setDate(QDate.fromString(r["due_date"],"yyyy-MM-dd"))
        idx=self.resolution_status.findText(r["status"]); self.resolution_status.setCurrentIndex(idx if idx>=0 else 0)

    def _refresh_link_combos(self):
        def fill(combo, rows, label_key, include_none=True):
            current=combo.currentData(); combo.blockSignals(True); combo.clear()
            if include_none: combo.addItem("بدون ارتباط",None)
            for row in rows: combo.addItem(f"{row['id']} — {row[label_key]}",row["id"])
            idx=combo.findData(current); combo.setCurrentIndex(idx if idx>=0 else 0); combo.blockSignals(False)
        issues=self.db.get_neighborhood_issues(self.current_zone_id); actions=self.db.get_neighborhood_actions(self.current_zone_id); meetings=self.db.get_neighborhood_meetings(self.current_zone_id)
        fill(self.action_issue_combo,issues,"title",True); fill(self.resolution_issue,issues,"title",True); fill(self.resolution_action,actions,"title",True); fill(self.resolution_meeting,meetings,"title",False)
