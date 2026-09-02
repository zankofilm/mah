# -*- coding: utf-8 -*-
"""Dashboard module for sending messages to members of each block."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QTabWidget, QComboBox, QLineEdit, QTextEdit, QCheckBox,
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QProgressBar, QFrame, QSplitter, QSizePolicy, QLayout
)

from access_control import has_permission
from icon_manager import get_icon
from jalali_utils import to_persian_digits, convert_dates_in_text
from database_messaging import is_valid_mobile
from message_system import BlockMessagingService, MessageSender, MessageAPISettings


_SCOPE_ITEMS = [
    ("همه اعضای دارای شماره معتبر", "all"),
    ("معتمدین بلوک‌ها", "trusted"),
    ("اعضای شورای بلوک", "council"),
    ("اعضای کمیته‌های شش‌گانه", "committees"),
    ("اعضای شورای اجتماعی", "social"),
]
_PROVIDER_ITEMS = [
    ("حالت آزمایشی — بدون ارسال واقعی", "demo"),
    ("SMS.ir", "sms_ir"),
    ("API عمومی JSON", "generic_json"),
]
_PROVIDER_TITLES = {value: title for title, value in _PROVIDER_ITEMS}
_SCOPE_TITLES = {value: title for title, value in _SCOPE_ITEMS}


class MessagingWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db, current_user=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = current_user or db.get_current_user() or {}
        self.service = BlockMessagingService(db)
        self.recipients = []
        self.setWindowTitle("ارسال پیام به اعضای بلوک‌ها")
        self.resize(1420, 880)
        self.setMinimumSize(900, 540)
        self.setLayoutDirection(Qt.RightToLeft)
        self._build_ui()
        self._load_settings()
        self._load_zones()
        self.refresh_history()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(10)

        top = QHBoxLayout()
        back = QPushButton("بازگشت به داشبورد")
        back.setIcon(get_icon("back", "navy"))
        back.clicked.connect(self.back_requested.emit)
        title_box = QVBoxLayout()
        title = QLabel("ماژول ارسال پیام به اعضای هر بلوک")
        title.setStyleSheet("font-size:20px;font-weight:900;color:#17345f")
        subtitle = QLabel("انتخاب گیرندگان، ارسال گروهی، تنظیم سرویس پیامک و ثبت کامل سوابق تحویل")
        subtitle.setStyleSheet("color:#64748b")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addWidget(back)
        top.addStretch()
        top.addLayout(title_box)
        root.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.setMinimumSize(0, 0)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        root.addWidget(self.tabs, 1)
        self._build_send_tab()
        self._build_settings_tab()
        self._build_history_tab()

    def _build_send_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 12, 8, 8)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        recipient_panel = QFrame()
        recipient_panel.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #dbe4ee;border-radius:10px}")
        recipient_layout = QVBoxLayout(recipient_panel)
        recipient_layout.setContentsMargins(12, 12, 12, 12)
        filters = QGridLayout()
        self.zone_combo = QComboBox()
        self.scope_combo = QComboBox()
        for title, value in _SCOPE_ITEMS:
            self.scope_combo.addItem(title, value)
        self.zone_combo.currentIndexChanged.connect(self.refresh_recipients)
        self.scope_combo.currentIndexChanged.connect(self.refresh_recipients)
        filters.addWidget(QLabel("بلوک:"), 0, 0)
        filters.addWidget(self.zone_combo, 0, 1)
        filters.addWidget(QLabel("گروه گیرندگان:"), 1, 0)
        filters.addWidget(self.scope_combo, 1, 1)
        recipient_layout.addLayout(filters)

        selection = QHBoxLayout()
        select_all = QPushButton("انتخاب همه")
        clear_all = QPushButton("لغو انتخاب")
        refresh = QPushButton("تازه‌سازی اعضا")
        select_all.clicked.connect(lambda: self._set_all_checked(True))
        clear_all.clicked.connect(lambda: self._set_all_checked(False))
        refresh.clicked.connect(self.refresh_recipients)
        selection.addWidget(select_all)
        selection.addWidget(clear_all)
        selection.addStretch()
        selection.addWidget(refresh)
        recipient_layout.addLayout(selection)

        self.recipient_table = QTableWidget(0, 4)
        self.recipient_table.setHorizontalHeaderLabels(["انتخاب", "نام", "شماره همراه", "سمت / گروه"])
        self.recipient_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.recipient_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.recipient_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.recipient_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.recipient_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.recipient_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.recipient_table.itemChanged.connect(lambda _item: self._update_recipient_summary())
        recipient_layout.addWidget(self.recipient_table, 1)
        self.recipient_summary = QLabel("گیرنده‌ای انتخاب نشده است.")
        self.recipient_summary.setStyleSheet("font-weight:700;color:#17345f")
        recipient_layout.addWidget(self.recipient_summary)

        compose_panel = QFrame()
        compose_panel.setStyleSheet("QFrame{background:#ffffff;border:1px solid #dbe4ee;border-radius:10px}")
        compose_layout = QVBoxLayout(compose_panel)
        compose_layout.setContentsMargins(14, 14, 14, 14)
        form = QFormLayout()
        self.message_title = QLineEdit()
        self.message_title.setPlaceholderText("مثال: اطلاعیه جلسه شورای بلوک")
        self.priority_combo = QComboBox()
        self.priority_combo.addItem("عادی", "normal")
        self.priority_combo.addItem("مهم", "high")
        self.priority_combo.addItem("فوری", "urgent")
        self.message_body = QTextEdit()
        self.message_body.setPlaceholderText("متن پیام را وارد کنید…")
        self.message_body.setMinimumHeight(260)
        self.message_body.textChanged.connect(self._update_character_count)
        form.addRow("عنوان پیام:", self.message_title)
        form.addRow("اولویت:", self.priority_combo)
        form.addRow("متن پیام:", self.message_body)
        compose_layout.addLayout(form)
        self.char_count = QLabel("۰ نویسه")
        self.char_count.setAlignment(Qt.AlignLeft)
        self.char_count.setStyleSheet("color:#64748b")
        compose_layout.addWidget(self.char_count)

        self.provider_status = QLabel()
        self.provider_status.setWordWrap(True)
        self.provider_status.setStyleSheet("padding:10px;background:#eef4fb;border-radius:8px;color:#17345f;font-weight:700")
        compose_layout.addWidget(self.provider_status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        compose_layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        preview = QPushButton("پیش‌نمایش")
        preview.setIcon(get_icon("info", "navy"))
        preview.clicked.connect(self.preview_message)
        self.send_button = QPushButton("ارسال پیام به افراد انتخاب‌شده")
        self.send_button.setIcon(get_icon("mail", "white"))
        self.send_button.setStyleSheet("padding:10px 18px;background:#17345f;color:white;font-weight:800;border-radius:7px")
        self.send_button.clicked.connect(self.send_messages)
        buttons.addWidget(preview)
        buttons.addStretch()
        buttons.addWidget(self.send_button)
        compose_layout.addLayout(buttons)
        compose_layout.addStretch()

        splitter.addWidget(recipient_panel)
        splitter.addWidget(compose_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([760, 600])
        layout.addWidget(splitter, 1)
        self.tabs.addTab(tab, "ارسال پیام")

    def _build_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        card = QFrame()
        card.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #dbe4ee;border-radius:10px;padding:12px}")
        form = QFormLayout(card)
        self.settings_enabled = QCheckBox("سامانه ارسال پیام فعال باشد")
        self.provider_combo = QComboBox()
        for title, value in _PROVIDER_ITEMS:
            self.provider_combo.addItem(title, value)
        self.provider_combo.currentIndexChanged.connect(self._toggle_provider_fields)
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("https://sms-provider.example/api/send")
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        self.api_key.setPlaceholderText("کلید API")
        self.sender_id = QLineEdit()
        self.sender_id.setPlaceholderText("شماره یا شناسه خط ارسال‌کننده")
        self.timeout = QSpinBox()
        self.timeout.setRange(3, 120)
        self.timeout.setSuffix(" ثانیه")
        self.test_mobile = QLineEdit()
        self.test_mobile.setPlaceholderText("09xxxxxxxxx")
        form.addRow("وضعیت:", self.settings_enabled)
        form.addRow("ارائه‌دهنده:", self.provider_combo)
        form.addRow("آدرس API:", self.api_url)
        form.addRow("کلید API:", self.api_key)
        form.addRow("شناسه فرستنده:", self.sender_id)
        form.addRow("مهلت پاسخ:", self.timeout)
        form.addRow("شماره تست:", self.test_mobile)
        layout.addWidget(card)

        note = QLabel(
            "در حالت آزمایشی، همه مراحل انتخاب، ثبت سوابق و گزارش نتیجه اجرا می‌شود اما پیام واقعی ارسال نمی‌شود. "
            "برای ارسال واقعی، اطلاعات سرویس پیامک سازمان را در حالت API عمومی JSON وارد کنید."
        )
        note.setWordWrap(True)
        note.setStyleSheet("padding:12px;background:#fff7e6;border:1px solid #f5d38c;border-radius:8px;color:#7c4a03")
        layout.addWidget(note)

        row = QHBoxLayout()
        self.save_settings_btn = QPushButton("ذخیره تنظیمات")
        self.save_settings_btn.clicked.connect(self.save_settings)
        self.test_settings_btn = QPushButton("ارسال پیام تست")
        self.test_settings_btn.clicked.connect(self.test_provider)
        row.addStretch()
        row.addWidget(self.test_settings_btn)
        row.addWidget(self.save_settings_btn)
        layout.addLayout(row)
        layout.addStretch()

        is_admin = (self.current_user.get("role") == "admin")
        if not is_admin:
            for widget in (self.settings_enabled, self.provider_combo, self.api_url, self.api_key,
                           self.sender_id, self.timeout, self.test_mobile, self.save_settings_btn,
                           self.test_settings_btn):
                widget.setEnabled(False)
            note.setText("تنظیمات API فقط توسط مدیر سامانه قابل تغییر است. کاربران مجاز می‌توانند از بخش ارسال پیام استفاده کنند.")
        self.tabs.addTab(tab, "تنظیمات API")

    def _build_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        actions = QHBoxLayout()
        retry = QPushButton("ارسال مجدد ناموفق‌ها")
        retry.clicked.connect(self.retry_selected_campaign)
        pause = QPushButton("توقف عملیات")
        pause.clicked.connect(self.pause_selected_campaign)
        resume = QPushButton("ادامه عملیات")
        resume.clicked.connect(self.resume_selected_campaign)
        refresh = QPushButton("تازه‌سازی سوابق")
        refresh.clicked.connect(self.refresh_history)
        actions.addWidget(retry)
        actions.addWidget(pause)
        actions.addWidget(resume)
        actions.addStretch()
        actions.addWidget(refresh)
        layout.addLayout(actions)

        splitter = QSplitter(Qt.Vertical)
        self.history_table = QTableWidget(0, 10)
        self.history_table.setHorizontalHeaderLabels([
            "شناسه", "تاریخ", "بلوک", "عنوان", "ارائه‌دهنده", "کل", "موفق", "ناموفق", "وضعیت", "ایجادکننده"
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.itemSelectionChanged.connect(self._load_selected_deliveries)

        self.delivery_table = QTableWidget(0, 8)
        self.delivery_table.setHorizontalHeaderLabels(["گیرنده", "شماره", "وضعیت", "تلاش", "تحویل", "شناسه سرویس", "زمان ارسال", "خطا / پاسخ"])
        self.delivery_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.delivery_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.history_table)
        splitter.addWidget(self.delivery_table)
        splitter.setSizes([420, 260])
        layout.addWidget(splitter, 1)
        self.tabs.addTab(tab, "سوابق ارسال")

    def _load_zones(self):
        current = self.zone_combo.currentData()
        self.zone_combo.blockSignals(True)
        self.zone_combo.clear()
        for zone in self.db.get_zones():
            self.zone_combo.addItem(zone.get("name") or f"بلوک {zone['id']}", zone["id"])
        if current is not None:
            index = self.zone_combo.findData(current)
            if index >= 0:
                self.zone_combo.setCurrentIndex(index)
        self.zone_combo.blockSignals(False)
        self.refresh_recipients()

    def refresh_recipients(self):
        zone_id = self.zone_combo.currentData()
        scope = self.scope_combo.currentData() or "all"
        self.recipients = self.service.get_recipients(zone_id, scope) if zone_id is not None else []
        self.recipient_table.setRowCount(0)
        for recipient in self.recipients:
            row = self.recipient_table.rowCount()
            self.recipient_table.insertRow(row)
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            check_item.setCheckState(Qt.Checked)
            check_item.setData(Qt.UserRole, recipient)
            self.recipient_table.setItem(row, 0, check_item)
            self.recipient_table.setItem(row, 1, QTableWidgetItem(recipient.get("name") or "بدون نام"))
            self.recipient_table.setItem(row, 2, QTableWidgetItem(recipient.get("mobile") or ""))
            self.recipient_table.setItem(row, 3, QTableWidgetItem(recipient.get("group") or ""))
        self._update_recipient_summary()

    def _set_all_checked(self, checked):
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.recipient_table.rowCount()):
            item = self.recipient_table.item(row, 0)
            if item:
                item.setCheckState(state)
        self._update_recipient_summary()

    def _selected_recipients(self):
        selected = []
        for row in range(self.recipient_table.rowCount()):
            item = self.recipient_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected

    def _update_recipient_summary(self):
        total = self.recipient_table.rowCount()
        selected = len(self._selected_recipients())
        self.recipient_summary.setText(
            f"{to_persian_digits(selected)} نفر انتخاب‌شده از {to_persian_digits(total)} شماره معتبر"
        )

    def _update_character_count(self):
        count = len(self.message_body.toPlainText())
        segments = max(1, (count + 69) // 70) if count else 0
        self.char_count.setText(f"{to_persian_digits(count)} نویسه — حدود {to_persian_digits(segments)} بخش پیامک")

    def preview_message(self):
        selected = self._selected_recipients()
        title = self.message_title.text().strip()
        body = self.message_body.toPlainText().strip()
        if not selected or not body:
            QMessageBox.warning(self, "پیش‌نمایش ناقص", "حداقل یک گیرنده و متن پیام لازم است.")
            return
        preview = f"{title}\n{body}".strip()
        QMessageBox.information(
            self, "پیش‌نمایش پیام",
            f"بلوک: {self.zone_combo.currentText()}\n"
            f"گیرندگان: {to_persian_digits(len(selected))} نفر\n"
            f"گروه: {self.scope_combo.currentText()}\n\n{preview}"
        )

    def send_messages(self):
        selected = self._selected_recipients()
        title = self.message_title.text().strip()
        body = self.message_body.toPlainText().strip()
        if not selected:
            QMessageBox.warning(self, "بدون گیرنده", "حداقل یک گیرنده را انتخاب کنید.")
            return
        if not body:
            QMessageBox.warning(self, "متن خالی", "متن پیام را وارد کنید.")
            return
        settings = self.service.get_settings()
        try:
            settings.validate()
        except Exception as exc:
            QMessageBox.warning(self, "تنظیمات ارسال", str(exc))
            return
        mode_note = "حالت آزمایشی و بدون ارسال واقعی" if settings.provider == "demo" else "ارسال واقعی از طریق API"
        answer = QMessageBox.question(
            self, "تأیید ارسال",
            f"پیام برای {to_persian_digits(len(selected))} نفر از بلوک «{self.zone_combo.currentText()}» ارسال شود؟\n"
            f"روش: {mode_note}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self.send_button.setEnabled(False)
        self.progress.setValue(0)

        def progress(index, total, recipient, result):
            self.progress.setMaximum(max(1, total))
            self.progress.setValue(index)
            status = "موفق" if result.get("success") else "ناموفق"
            self.progress.setFormat(f"{to_persian_digits(index)} از {to_persian_digits(total)} — {status}")
            QApplication.processEvents()

        try:
            summary = self.service.send_to_recipients(
                self.zone_combo.currentData(), title, body, selected,
                scope=self.scope_combo.currentData() or "all",
                priority=self.priority_combo.currentData() or "normal",
                progress_callback=progress,
            )
            QMessageBox.information(
                self, "نتیجه ارسال",
                f"عملیات ثبت شد.\n"
                f"کل: {to_persian_digits(summary['total'])}\n"
                f"موفق: {to_persian_digits(summary['success'])}\n"
                f"ناموفق: {to_persian_digits(summary['failed'])}\n"
                f"وضعیت: {summary['status']}"
            )
            self.refresh_history()
        except Exception as exc:
            QMessageBox.critical(self, "خطا در ارسال پیام", str(exc))
        finally:
            self.send_button.setEnabled(True)

    def _load_settings(self):
        settings = self.db.get_message_api_settings()
        self.settings_enabled.setChecked(bool(settings.get("enabled")))
        index = self.provider_combo.findData(settings.get("provider") or "demo")
        self.provider_combo.setCurrentIndex(index if index >= 0 else 0)
        self.api_url.setText(settings.get("api_url") or "")
        self.api_key.setText(settings.get("api_key") or "")
        self.sender_id.setText(settings.get("sender_id") or "")
        self.timeout.setValue(int(settings.get("timeout_seconds") or 15))
        self._toggle_provider_fields()
        self._update_provider_status()

    def _toggle_provider_fields(self):
        real = self.provider_combo.currentData() == "generic_json"
        for widget in (self.api_url, self.api_key, self.sender_id):
            widget.setEnabled(real and self.current_user.get("role") == "admin")

    def _update_provider_status(self):
        settings = self.db.get_message_api_settings()
        provider = settings.get("provider") or "demo"
        state = "فعال" if settings.get("enabled") else "غیرفعال"
        self.provider_status.setText(f"وضعیت سرویس: {state} — {_PROVIDER_TITLES.get(provider, provider)}")

    def save_settings(self):
        if self.current_user.get("role") != "admin":
            QMessageBox.warning(self, "عدم دسترسی", "فقط مدیر سامانه می‌تواند تنظیمات API را تغییر دهد.")
            return
        provider = self.provider_combo.currentData() or "demo"
        if self.settings_enabled.isChecked() and provider in {"generic_json", "sms_ir"}:
            if not self.api_url.text().strip() or not self.api_key.text().strip():
                QMessageBox.warning(self, "تنظیمات ناقص", "برای ارسال واقعی، آدرس و کلید API الزامی است.")
                return
        self.db.set_message_api_settings(
            self.settings_enabled.isChecked(), provider, self.api_url.text(), self.api_key.text(),
            self.sender_id.text(), self.timeout.value(),
        )
        self._update_provider_status()
        QMessageBox.information(self, "ذخیره شد", "تنظیمات سرویس پیام با موفقیت ذخیره شد.")

    def test_provider(self):
        if self.current_user.get("role") != "admin":
            return
        mobile = self.test_mobile.text().strip()
        if not is_valid_mobile(mobile):
            QMessageBox.warning(self, "شماره نامعتبر", "یک شماره همراه معتبر مانند 09123456789 وارد کنید.")
            return
        settings = MessageAPISettings(
            provider=self.provider_combo.currentData() or "demo",
            api_url=self.api_url.text().strip(), api_key=self.api_key.text().strip(),
            sender_id=self.sender_id.text().strip(), enabled=self.settings_enabled.isChecked(),
            timeout_seconds=self.timeout.value(),
        )
        try:
            result = MessageSender(settings).send(mobile, "پیام تست سامانه مدیریت محلات جوانرود")
            QMessageBox.information(self, "آزمون موفق", f"نتیجه: {result.get('response') or 'ارسال انجام شد.'}")
        except Exception as exc:
            QMessageBox.critical(self, "آزمون ناموفق", str(exc))

    def _selected_campaign_id(self):
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "انتخاب عملیات", "یک عملیات ارسال را از جدول انتخاب کنید.")
            return None
        item = self.history_table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def retry_selected_campaign(self):
        campaign_id = self._selected_campaign_id()
        if not campaign_id:
            return
        answer = QMessageBox.question(
            self, "ارسال مجدد", "پیام‌های ناموفق این عملیات دوباره ارسال شوند؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.progress.setValue(0)
        def progress(index, total, recipient, result):
            self.progress.setMaximum(max(1, total))
            self.progress.setValue(index)
            QApplication.processEvents()
        try:
            summary = self.service.retry_campaign(campaign_id, progress_callback=progress)
            QMessageBox.information(
                self, "نتیجه ارسال مجدد",
                f"موفق: {to_persian_digits(summary['success'])} — ناموفق: {to_persian_digits(summary['failed'])}"
            )
            self.refresh_history()
        except Exception as exc:
            QMessageBox.warning(self, "ارسال مجدد", str(exc))

    def pause_selected_campaign(self):
        campaign_id = self._selected_campaign_id()
        if campaign_id:
            self.service.pause_campaign(campaign_id)
            self.refresh_history()

    def resume_selected_campaign(self):
        campaign_id = self._selected_campaign_id()
        if campaign_id:
            self.service.resume_campaign(campaign_id)
            self.refresh_history()

    def refresh_history(self):
        campaigns = self.db.get_message_campaigns()
        self.history_table.setRowCount(0)
        for campaign in campaigns:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            values = [
                campaign.get("id"), convert_dates_in_text(campaign.get("created_at") or ""),
                campaign.get("zone_name") or "—", campaign.get("title") or "بدون عنوان",
                _PROVIDER_TITLES.get(campaign.get("provider"), campaign.get("provider") or ""),
                campaign.get("total_count") or 0, campaign.get("success_count") or 0,
                campaign.get("failed_count") or 0, campaign.get("status") or "",
                campaign.get("created_by_name") or "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(to_persian_digits(str(value)) if col in {0, 5, 6, 7} else str(value))
                if col == 0:
                    item.setData(Qt.UserRole, campaign.get("id"))
                self.history_table.setItem(row, col, item)
        self.delivery_table.setRowCount(0)

    def _load_selected_deliveries(self):
        row = self.history_table.currentRow()
        if row < 0:
            return
        item = self.history_table.item(row, 0)
        campaign_id = item.data(Qt.UserRole) if item else None
        if not campaign_id:
            return
        deliveries = self.db.get_message_deliveries(campaign_id)
        self.delivery_table.setRowCount(0)
        for delivery in deliveries:
            row = self.delivery_table.rowCount()
            self.delivery_table.insertRow(row)
            detail = delivery.get("error_text") or delivery.get("response_text") or ""
            values = [delivery.get("recipient_name") or "—", delivery.get("mobile") or "",
                      delivery.get("status") or "", to_persian_digits(delivery.get("attempt_count") or 0),
                      delivery.get("delivery_status") or "نامشخص", delivery.get("provider_message_id") or "—",
                      convert_dates_in_text(delivery.get("sent_at") or "—"), detail]
            for col, value in enumerate(values):
                self.delivery_table.setItem(row, col, QTableWidgetItem(str(value)))
