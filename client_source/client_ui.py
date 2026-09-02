# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget, QHeaderView
)

from client_database import ClientDatabase
from client_exchange_core import ExchangeError, build_activation_request, normalize_national_code
from client_license_store import LicenseStore
from icon_manager import get_icon
from jalali_utils import iso_to_jalali, jalali_to_iso, to_persian_digits
from theme import MAIN_STYLESHEET
from ui_typography import apply_application_typography
from responsive_ui import ResponsiveUiFilter
from version import APP_NAME, APP_VERSION

COMMITTEES = [
    ("infrastructure", "عمران، خدمات محلی و محیط‌زیست", "infrastructure"),
    ("health", "بهداشت و سلامت", "health"),
    ("sports", "نشاط و ورزش", "sport"),
    ("security", "امنیت عمومی و آسیب‌های اجتماعی", "security"),
    ("support", "خدمات حمایتی و معیشتی", "support"),
    ("culture", "امور فرهنگی، آموزشی و دینی", "culture"),
]

RECORD_TITLES = {
    "member": "اعضای کمیته",
    "meeting": "جلسات",
    "issue": "مسائل و درخواست‌ها",
    "resolution": "مصوبات",
    "action": "اقدامات اجرایی",
}

SOCIAL_CATEGORIES = [
    "اعتیاد", "بیکاری و معیشت", "ترک تحصیل", "خشونت خانوادگی",
    "کودکان و نوجوانان", "سالمندان", "زنان سرپرست خانوار",
    "سلامت روان", "افراد دارای معلولیت", "امنیت محله",
    "مشارکت اجتماعی", "مهاجرت و حاشیه‌نشینی", "سایر",
]


CLIENT_BASE_DIR = Path(__file__).resolve().parent
CLIENT_EMBLEM_PATH = CLIENT_BASE_DIR / "assets" / "official_emblem.png"
CLIENT_FLAG_PATH = CLIENT_BASE_DIR / "assets" / "approved_flag.png"


def _tinted_pixmap(path: Path, size: int, color: str = "#e2bb62") -> QPixmap:
    pix = QPixmap(str(path))
    if pix.isNull():
        return pix
    pix = pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    result = QPixmap(pix.size())
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.drawPixmap(0, 0, pix)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), QColor(color))
    painter.end()
    return result


def _build_client_official_panel() -> QFrame:
    panel = QFrame()
    panel.setStyleSheet("background: transparent; border: none; border-right: 1px solid rgba(216,177,91,0.62);")
    panel.setFixedWidth(248)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(2)
    layout.addStretch(1)

    emblem = QLabel()
    emblem.setAlignment(Qt.AlignCenter)
    emblem.setPixmap(_tinted_pixmap(CLIENT_EMBLEM_PATH, 44))
    layout.addWidget(emblem, 0, Qt.AlignHCenter)

    for text_value, color, size, weight in [
        ("وزارت کشور", "#f5d98f", 13, 800),
        ("استانداری کرمانشاه", "#f5d98f", 13, 800),
        ("فرمانداری شهرستان جوانرود", "#ffffff", 14, 900),
    ]:
        lbl = QLabel(text_value)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"background: transparent; color:{color}; font-size:{size}px; font-weight:{weight};")
        layout.addWidget(lbl)
    layout.addStretch(1)
    return panel


def _build_client_title_panel(title_text: str, subtitle_text: str = "") -> QFrame:
    panel = QFrame()
    panel.setStyleSheet("background: transparent; border: none;")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(16, 8, 16, 8)
    layout.setSpacing(4)
    layout.addStretch(1)
    title = QLabel(title_text)
    title.setObjectName("SoftwareHeaderTitle")
    title.setAlignment(Qt.AlignCenter)
    title.setWordWrap(True)
    layout.addWidget(title)
    if subtitle_text:
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("SoftwareHeaderSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
    layout.addStretch(1)
    return panel


def _build_client_official_header(title_text: str, subtitle_text: str = "", left_widget: Optional[QWidget] = None) -> QFrame:
    header = QFrame()
    header.setObjectName("SoftwareHeader")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(14)

    left = QFrame()
    left.setStyleSheet("background: transparent; border: none;")
    left_layout = QVBoxLayout(left)
    left_layout.setContentsMargins(0, 0, 0, 0)
    if left_widget is not None:
        left_layout.addStretch(1)
        left_layout.addWidget(left_widget)
        left_layout.addStretch(1)
    else:
        left_layout.addStretch(1)
    layout.addWidget(left, 1)
    layout.addWidget(_build_client_title_panel(title_text, subtitle_text), 2)
    layout.addWidget(_build_client_official_panel())
    return header


def _button(text: str, icon: str = "", role: str = "") -> QPushButton:
    btn = QPushButton(text)
    if icon:
        btn.setIcon(get_icon(icon, "white" if role in {"primary", "success", "danger"} else "navy"))
    if role:
        btn.setProperty("uiRole", role)
    return btn


def _message(parent, title: str, text: str, error: bool = False):
    if error:
        QMessageBox.critical(parent, title, text)
    else:
        QMessageBox.information(parent, title, text)


def _jalali_today() -> str:
    return iso_to_jalali(date.today().isoformat(), persian_digits=True)


def _iso_from_input(text: str, required: bool = False) -> Optional[str]:
    return jalali_to_iso(text, required=required)


class ActivationWindow(QMainWindow):
    activated = pyqtSignal()

    def __init__(self, store: LicenseStore):
        super().__init__()
        self.store = store
        self.setWindowTitle(f"فعال‌سازی {APP_NAME}")
        self.resize(820, 620)
        self._build()
        self.refresh_status()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        hero = _build_client_official_header(APP_NAME, "فعال‌سازی وابسته به دستگاه و مجوز زمان‌دار")
        layout.addWidget(hero)

        self.status_box = QLabel()
        self.status_box.setWordWrap(True)
        self.status_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_box.setStyleSheet("padding:12px;background:#eef4fb;border:1px solid #ccd9e8;border-radius:9px;font-weight:700")
        layout.addWidget(self.status_box)

        tabs = QTabWidget()
        tabs.addTab(self._request_tab(), "ساخت درخواست فعال‌سازی")
        tabs.addTab(self._install_tab(), "فعال‌سازی یا تمدید")
        layout.addWidget(tabs, 1)

    def _request_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        text = QLabel(
            "برای اولین فعال‌سازی، کد ملی خود را وارد کنید و فایل درخواست با پسوند .jrr بسازید. "
            "این فایل را به مدیر سامانه تحویل دهید تا فایل فعال‌سازی مخصوص همین دستگاه صادر شود."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        form = QFormLayout()
        self.request_national_code = QLineEdit()
        self.request_national_code.setMaxLength(10)
        self.request_national_code.setPlaceholderText("کد ملی ۱۰ رقمی")
        form.addRow("کد ملی کاربر:", self.request_national_code)
        layout.addLayout(form)
        btn = _button("ساخت فایل درخواست .jrr", "download", "primary")
        btn.clicked.connect(self.create_request)
        layout.addWidget(btn)
        layout.addStretch()
        return tab

    def _install_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        text = QLabel(
            "فایل .jra دریافتی از مدیر را انتخاب و کد ملی همان کاربر را وارد کنید. "
            "فایل فقط روی دستگاهی که درخواست را ساخته قابل نصب است."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        form = QFormLayout()
        row = QHBoxLayout()
        self.activation_path = QLineEdit()
        self.activation_path.setReadOnly(True)
        choose = _button("انتخاب فایل", "file")
        choose.clicked.connect(self.choose_activation)
        row.addWidget(self.activation_path, 1)
        row.addWidget(choose)
        form.addRow("فایل فعال‌سازی:", row)
        self.activation_national_code = QLineEdit()
        self.activation_national_code.setMaxLength(10)
        self.activation_national_code.setPlaceholderText("کد ملی ۱۰ رقمی")
        form.addRow("کد ملی کاربر:", self.activation_national_code)
        layout.addLayout(form)
        install = _button("نصب فایل فعال‌سازی یا تمدید", "check", "success")
        install.clicked.connect(self.install_activation)
        layout.addWidget(install)
        layout.addStretch()
        return tab

    def refresh_status(self):
        try:
            result = self.store.validate(update_clock=False)
        except Exception as exc:
            self.status_box.setText(f"وضعیت مجوز محلی قابل خواندن نیست: {exc}")
            return
        lic = result.get("license") or {}
        if result["status"] == "not_activated":
            self.status_box.setText("این دستگاه هنوز فعال نشده است.")
            return
        expiry = iso_to_jalali(lic.get("valid_until"))
        self.status_box.setText(
            f"مسئول: {lic.get('responsible_full_name','')}\n"
            f"بلوک: {lic.get('zone_name','')} | کمیته: {lic.get('committee_title','')}\n"
            f"پایان اعتبار: {expiry} | وضعیت: {result.get('message','')}"
        )

    def create_request(self):
        try:
            code = normalize_national_code(self.request_national_code.text())
            path, _ = QFileDialog.getSaveFileName(self, "ذخیره درخواست فعال‌سازی", "client_activation_request.jrr", "درخواست فعال‌سازی (*.jrr)")
            if not path:
                return
            if not path.lower().endswith(".jrr"):
                path += ".jrr"
            build_activation_request(path, code, self.store.key_store, APP_VERSION)
            _message(self, "درخواست ساخته شد", "فایل درخواست فعال‌سازی با موفقیت ساخته شد. آن را به مدیر سامانه تحویل دهید.")
        except Exception as exc:
            _message(self, "خطا", str(exc), True)

    def choose_activation(self):
        path, _ = QFileDialog.getOpenFileName(self, "انتخاب فایل فعال‌سازی", "", "فایل فعال‌سازی (*.jra);;همه فایل‌ها (*.*)")
        if path:
            self.activation_path.setText(path)

    def install_activation(self):
        try:
            path = self.activation_path.text().strip()
            if not path:
                raise ExchangeError("فایل فعال‌سازی انتخاب نشده است.")
            payload = self.store.install(path, self.activation_national_code.text())
            expiry = iso_to_jalali(payload.get("valid_until"))
            _message(self, "فعال‌سازی موفق", f"کلاینت برای {payload.get('responsible_full_name')} فعال شد.\nپایان اعتبار: {expiry}")
            self.refresh_status()
            self.activated.emit()
        except Exception as exc:
            _message(self, "فعال‌سازی ناموفق", str(exc), True)


class LoginWindow(QMainWindow):
    logged_in = pyqtSignal(dict)
    activation_requested = pyqtSignal()

    def __init__(self, store: LicenseStore):
        super().__init__()
        self.store = store
        self.setWindowTitle(f"ورود به {APP_NAME}")
        self.resize(640, 520)
        self._build()
        self.refresh()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(44, 32, 44, 32)
        hero = _build_client_official_header(APP_NAME, "ورود امن به سامانه")
        layout.addWidget(hero)

        self.license_info = QLabel()
        self.license_info.setWordWrap(True)
        self.license_info.setStyleSheet("padding:12px;background:#eef4fb;border-radius:9px;font-weight:700")
        layout.addWidget(self.license_info)

        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.returnPressed.connect(self.login)
        form.addRow("نام کاربری:", self.username)
        form.addRow("رمز عبور:", self.password)
        layout.addLayout(form)
        login_btn = _button("ورود", "login", "primary")
        login_btn.clicked.connect(self.login)
        layout.addWidget(login_btn)
        renewal_btn = _button("واردکردن فایل فعال‌سازی یا تمدید", "upload")
        renewal_btn.clicked.connect(self.activation_requested.emit)
        layout.addWidget(renewal_btn)
        layout.addStretch()

    def refresh(self):
        result = self.store.validate(update_clock=False)
        lic = result.get("license") or {}
        self.username.setText(str(lic.get("username") or ""))
        expiry = iso_to_jalali(lic.get("valid_until"))
        remaining = result.get("remaining_days")
        remain_text = f" | {to_persian_digits(remaining)} روز باقی‌مانده" if remaining is not None else ""
        self.license_info.setText(
            f"مسئول: {lic.get('responsible_full_name','')}\n"
            f"بلوک: {lic.get('zone_name','')}\n"
            f"دسترسی: {lic.get('committee_title','')}\n"
            f"پایان اعتبار: {expiry}{remain_text}\n"
            f"وضعیت: {result.get('message','')}"
        )

    def login(self):
        result = self.store.validate(update_clock=True)
        if result["status"] != "valid":
            _message(self, "ورود غیرممکن", result["message"], True)
            return
        if not self.store.authenticate(self.username.text(), self.password.text()):
            _message(self, "ورود ناموفق", "نام کاربری یا رمز عبور صحیح نیست.", True)
            return
        self.logged_in.emit(result["license"])


FIELD_SCHEMAS: Dict[str, List[Dict[str, Any]]] = {
    "member": [
        {"key":"full_name", "label":"نام و نام خانوادگی*", "type":"line", "required":True},
        {"key":"national_code", "label":"کد ملی", "type":"line"},
        {"key":"mobile", "label":"شماره همراه", "type":"line"},
        {"key":"role", "label":"سمت در کمیته", "type":"line"},
        {"key":"member_type", "label":"نوع عضو", "type":"combo", "options":["عضو مردمی","نماینده دستگاه","معتمد محله","مسئول مکان"]},
        {"key":"agency", "label":"دستگاه یا نهاد", "type":"line"},
        {"key":"status", "label":"وضعیت", "type":"combo", "options":["فعال","غیرفعال"]},
        {"key":"notes", "label":"توضیحات", "type":"text"},
    ],
    "meeting": [
        {"key":"title", "label":"عنوان جلسه*", "type":"line", "required":True},
        {"key":"meeting_date", "label":"تاریخ جلسه (شمسی)", "type":"date"},
        {"key":"start_time", "label":"ساعت شروع", "type":"line"},
        {"key":"place_name", "label":"محل جلسه", "type":"line"},
        {"key":"agenda", "label":"دستور جلسه", "type":"text"},
        {"key":"attendees", "label":"حاضرین", "type":"text"},
        {"key":"minutes_text", "label":"صورت‌جلسه", "type":"text"},
        {"key":"status", "label":"وضعیت", "type":"combo", "options":["برنامه‌ریزی‌شده","برگزار شد","لغو شد"]},
    ],
    "issue": [
        {"key":"title", "label":"عنوان مسئله*", "type":"line", "required":True},
        {"key":"category", "label":"دسته‌بندی", "type":"editable_combo", "options":SOCIAL_CATEGORIES},
        {"key":"description", "label":"شرح مسئله", "type":"text"},
        {"key":"related_office", "label":"دستگاه مرتبط", "type":"line"},
        {"key":"urgency", "label":"فوریت از ۱ تا ۵", "type":"spin", "min":1, "max":5, "default":3},
        {"key":"severity", "label":"شدت از ۱ تا ۵", "type":"spin", "min":1, "max":5, "default":3},
        {"key":"affected_households", "label":"خانوارهای درگیر", "type":"spin", "min":0, "max":100000, "default":0},
        {"key":"safety_risk", "label":"ریسک ایمنی از ۰ تا ۵", "type":"spin", "min":0, "max":5, "default":1},
        {"key":"status", "label":"وضعیت", "type":"combo", "options":["ثبت اولیه","در حال بررسی","در حال پیگیری","مختومه"]},
        {"key":"location_text", "label":"محل یا نشانی", "type":"line"},
        {"key":"due_date", "label":"مهلت پیگیری (شمسی)", "type":"date"},
    ],
    "resolution": [
        {"key":"title", "label":"عنوان مصوبه*", "type":"line", "required":True},
        {"key":"description", "label":"شرح مصوبه", "type":"text"},
        {"key":"responsible_agency", "label":"دستگاه مسئول", "type":"line"},
        {"key":"responsible_person", "label":"مسئول پیگیری", "type":"line"},
        {"key":"due_date", "label":"مهلت انجام (شمسی)", "type":"date"},
        {"key":"status", "label":"وضعیت", "type":"combo", "options":["در انتظار اقدام","در حال انجام","انجام شد","متوقف"]},
    ],
    "action": [
        {"key":"title", "label":"عنوان اقدام*", "type":"line", "required":True},
        {"key":"description", "label":"شرح اقدام", "type":"text"},
        {"key":"responsible_person", "label":"مسئول اجرا", "type":"line"},
        {"key":"responsible_office", "label":"دستگاه مسئول", "type":"line"},
        {"key":"planned_start", "label":"شروع برنامه (شمسی)", "type":"date"},
        {"key":"planned_end", "label":"پایان برنامه (شمسی)", "type":"date"},
        {"key":"progress_percent", "label":"درصد پیشرفت", "type":"spin", "min":0, "max":100, "default":0},
        {"key":"status", "label":"وضعیت", "type":"combo", "options":["برنامه‌ریزی‌شده","در حال اجرا","تکمیل‌شده","متوقف","عقب‌افتاده"]},
        {"key":"obstacles", "label":"موانع", "type":"text"},
        {"key":"result_summary", "label":"نتیجه", "type":"text"},
    ],
}


class RecordDialog(QDialog):
    def __init__(self, record_type: str, data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.record_type = record_type
        self.original = data or {}
        self.widgets: Dict[str, QWidget] = {}
        self.setWindowTitle(f"ثبت یا ویرایش {RECORD_TITLES[record_type]}")
        self.resize(720, 760)
        root = QVBoxLayout(self)
        host = QWidget()
        form = QFormLayout(host)
        form.setLabelAlignment(Qt.AlignRight)
        for field in FIELD_SCHEMAS[record_type]:
            widget = self._make_widget(field)
            self.widgets[field["key"]] = widget
            form.addRow(field["label"] + ":", widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        root.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self._validate_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _make_widget(self, field: Dict[str, Any]):
        key = field["key"]
        value = self.original.get(key)
        kind = field["type"]
        if kind == "text":
            w = QTextEdit()
            w.setMinimumHeight(90)
            w.setPlainText(str(value or ""))
            return w
        if kind in {"combo", "editable_combo"}:
            w = QComboBox()
            w.addItems(field.get("options") or [])
            if kind == "editable_combo":
                w.setEditable(True)
                w.setInsertPolicy(QComboBox.InsertAtTop)
            if value:
                idx = w.findText(str(value))
                if idx < 0 and kind == "editable_combo":
                    w.insertItem(0, str(value)); idx = 0
                if idx >= 0:
                    w.setCurrentIndex(idx)
            return w
        if kind == "spin":
            w = QSpinBox()
            w.setRange(int(field.get("min", 0)), int(field.get("max", 100)))
            w.setValue(int(value if value is not None else field.get("default", 0)))
            return w
        w = QLineEdit()
        if kind == "date":
            if value:
                w.setText(iso_to_jalali(value))
            else:
                w.setPlaceholderText("۱۴۰۵/۰۵/۰۱")
        else:
            w.setText(str(value or ""))
        return w

    def _validate_accept(self):
        try:
            values = self.values()
            for field in FIELD_SCHEMAS[self.record_type]:
                if field.get("required") and not str(values.get(field["key"]) or "").strip():
                    raise ValueError(f"فیلد «{field['label']}» الزامی است.")
            if self.record_type == "member" and values.get("national_code"):
                normalize_national_code(values["national_code"])
            self.accept()
        except Exception as exc:
            _message(self, "اطلاعات ناقص", str(exc), True)

    def values(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        fields = {x["key"]: x for x in FIELD_SCHEMAS[self.record_type]}
        for key, widget in self.widgets.items():
            kind = fields[key]["type"]
            if isinstance(widget, QTextEdit):
                value: Any = widget.toPlainText().strip()
            elif isinstance(widget, QComboBox):
                value = widget.currentText().strip()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            else:
                value = widget.text().strip()
            if kind == "date":
                value = _iso_from_input(value, required=False) if value else None
            result[key] = value
        return result


class RecordPage(QWidget):
    def __init__(self, db: ClientDatabase, record_type: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.record_type = record_type
        self.records: List[Dict[str, Any]] = []
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        add = _button("ثبت جدید", "plus", "primary")
        add.clicked.connect(self.add_record)
        edit = _button("ویرایش انتخابی", "edit")
        edit.clicked.connect(self.edit_record)
        refresh = _button("تازه‌سازی", "refresh")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(add)
        actions.addWidget(edit)
        actions.addStretch()
        actions.addWidget(refresh)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["عنوان", "وضعیت", "بازبینی", "آخرین تغییر", "شناسه"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_record)
        layout.addWidget(self.table, 1)

    def _summary(self, item: Dict[str, Any]):
        data = item.get("data") or {}
        title = data.get("title") or data.get("full_name") or "بدون عنوان"
        status = data.get("status") or data.get("role") or ""
        return title, status

    def refresh(self):
        self.records = self.db.list_records(self.record_type)
        self.table.setRowCount(0)
        for item in self.records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            title, status = self._summary(item)
            values = [title, status, item["revision"], item["updated_at"], item["record_uuid"]]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value or ""))
                if col == 0:
                    cell.setData(Qt.UserRole, item["record_uuid"])
                self.table.setItem(row, col, cell)

    def selected_uuid(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def add_record(self):
        dlg = RecordDialog(self.record_type, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            self.db.save_record(self.record_type, dlg.values())
            self.refresh()
        except Exception as exc:
            _message(self, "خطا در ذخیره", str(exc), True)

    def edit_record(self, *_):
        record_uuid = self.selected_uuid()
        if not record_uuid:
            _message(self, "انتخاب رکورد", "ابتدا یک ردیف را انتخاب کنید.", True)
            return
        item = self.db.get_record(record_uuid)
        if not item:
            _message(self, "خطا", "رکورد انتخاب‌شده پیدا نشد.", True)
            return
        dlg = RecordDialog(self.record_type, item.get("data") or {}, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        try:
            self.db.save_record(self.record_type, dlg.values(), record_uuid=record_uuid)
            self.refresh()
        except Exception as exc:
            _message(self, "خطا در ویرایش", str(exc), True)


class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ساخت فایل رمزنگاری‌شده کلاینت")
        layout = QFormLayout(self)
        self.period = QLineEdit()
        self.period.setPlaceholderText("مثلاً مرداد ۱۴۰۵")
        self.include_all = QComboBox()
        self.include_all.addItem("فقط رکوردهای جدید و اصلاح‌شده", False)
        self.include_all.addItem("همه رکوردها", True)
        layout.addRow("دوره گزارش:", self.period)
        layout.addRow("محدوده خروجی:", self.include_all)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("انتخاب مسیر و ساخت فایل")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class ClientMainWindow(QMainWindow):
    logout_requested = pyqtSignal()
    activation_requested = pyqtSignal()

    def __init__(self, store: LicenseStore, license_item: Dict[str, Any]):
        super().__init__()
        self.store = store
        self.license = license_item
        self.db = ClientDatabase(store)
        self.setWindowTitle(APP_NAME)
        self.resize(1380, 860)
        self._build()

    def closeEvent(self, event):
        self.db.close()
        super().closeEvent(event)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        user_panel = QWidget()
        user_layout = QHBoxLayout(user_panel)
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(10)
        logout = _button("خروج", "logout")
        logout.clicked.connect(self.logout_requested.emit)
        user = QLabel(
            f"{self.license.get('responsible_full_name')}\n"
            f"{self.license.get('role_title')} | {self.license.get('zone_name')}"
        )
        user.setObjectName("HeaderUserName")
        user.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        user_layout.addWidget(logout)
        user_layout.addWidget(user)
        user_layout.addStretch(1)
        header = _build_client_official_header(APP_NAME, "کلاینت کمیته‌های محلات", user_panel)
        layout.addWidget(header)

        valid = self.store.validate(update_clock=False)
        expiry = iso_to_jalali(self.license.get("valid_until"))
        remain = to_persian_digits(valid.get("remaining_days", ""))
        info = QLabel(
            f"دسترسی فعال: فقط کمیته «{self.license.get('committee_title')}» در بلوک «{self.license.get('zone_name')}» | "
            f"پایان اعتبار: {expiry} | روزهای باقی‌مانده: {remain}"
        )
        info.setStyleSheet("padding:10px;background:#eef4fb;border:1px solid #ccd9e8;border-radius:8px;font-weight:700")
        layout.addWidget(info)

        committee_box = QGroupBox("پنل‌های کمیته")
        grid = QGridLayout(committee_box)
        allowed_code = self.license.get("committee_code")
        for i, (code, title_text, icon_name) in enumerate(COMMITTEES):
            btn = QPushButton(title_text)
            btn.setMinimumHeight(68)
            btn.setIcon(get_icon(icon_name, "navy" if code == allowed_code else "muted"))
            btn.setEnabled(code == allowed_code)
            if code == allowed_code:
                btn.setProperty("uiRole", "primary")
                btn.setToolTip("پنل مجاز شما")
            else:
                btn.setToolTip("این پنل در مجوز شما فعال نیست")
            grid.addWidget(btn, i // 3, i % 3)
        layout.addWidget(committee_box)

        top_actions = QHBoxLayout()
        export = _button("خروجی رمزنگاری‌شده برای ادمین", "upload", "success")
        export.clicked.connect(self.export_data)
        renewal = _button("ورود فایل تمدید", "security")
        renewal.clicked.connect(self.activation_requested.emit)
        top_actions.addWidget(export)
        top_actions.addWidget(renewal)
        top_actions.addStretch()
        layout.addLayout(top_actions)

        self.tabs = QTabWidget()
        for rtype in ("member", "meeting", "issue", "resolution", "action"):
            self.tabs.addTab(RecordPage(self.db, rtype, self), RECORD_TITLES[rtype])
        layout.addWidget(self.tabs, 1)

    def export_data(self):
        valid = self.store.validate(update_clock=True)
        if valid["status"] != "valid":
            _message(self, "خروجی غیرممکن", valid["message"], True)
            return
        dlg = ExportDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل کلاینت", "committee_report.jrcx", "فایل کلاینت رمزنگاری‌شده (*.jrcx)")
        if not path:
            return
        if not path.lower().endswith(".jrcx"):
            path += ".jrcx"
        try:
            result = self.db.export_package(path, dlg.period.text(), bool(dlg.include_all.currentData()))
            _message(self, "خروجی ساخته شد", f"فایل رمزنگاری‌شده ساخته شد.\nتعداد رکوردها: {to_persian_digits(result['record_count'])}")
        except Exception as exc:
            _message(self, "خطا در خروجی", str(exc), True)


class ClientApplicationController:
    def __init__(self, app: QApplication):
        self.app = app
        self.store = LicenseStore()
        self.activation_window: Optional[ActivationWindow] = None
        self.login_window: Optional[LoginWindow] = None
        self.main_window: Optional[ClientMainWindow] = None

    def start(self):
        result = self.store.validate(update_clock=False)
        if result["status"] == "not_activated":
            self.show_activation()
        else:
            self.show_login()

    def show_activation(self):
        if self.activation_window is None:
            self.activation_window = ActivationWindow(self.store)
            self.activation_window.activated.connect(self._after_activation)
        self.activation_window.refresh_status()
        self.activation_window.show()
        self.activation_window.raise_()
        if self.login_window:
            self.login_window.hide()
        if self.main_window:
            self.main_window.hide()

    def _after_activation(self):
        self.show_login()

    def show_login(self):
        if self.login_window is None:
            self.login_window = LoginWindow(self.store)
            self.login_window.logged_in.connect(self.show_main)
            self.login_window.activation_requested.connect(self.show_activation)
        self.login_window.refresh()
        self.login_window.show()
        self.login_window.raise_()
        if self.activation_window:
            self.activation_window.hide()
        if self.main_window:
            self.main_window.hide()

    def show_main(self, license_item: Dict[str, Any]):
        if self.main_window:
            self.main_window.close()
        self.main_window = ClientMainWindow(self.store, license_item)
        self.main_window.logout_requested.connect(self.show_login)
        self.main_window.activation_requested.connect(self.show_activation)
        self.main_window.show()
        if self.login_window:
            self.login_window.hide()
        if self.activation_window:
            self.activation_window.hide()


def configure_application(app: QApplication):
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet(MAIN_STYLESHEET)
    apply_application_typography(app)
    app.responsive_ui_filter = ResponsiveUiFilter(app)
    app.installEventFilter(app.responsive_ui_filter)
    icon = Path(__file__).resolve().parent / "assets" / "javanrood_app.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))


__all__ = ["ClientApplicationController", "configure_application"]
