# -*- coding: utf-8 -*-
"""سامانه یکپارچه آیکون، اندازه‌ها و پرداخت نهایی رابط کاربری."""

import os
import re
from functools import lru_cache
from PyQt5.QtCore import QSize, QObject, QEvent, QTimer, Qt
from PyQt5.QtGui import QIcon, QPalette
from PyQt5.QtWidgets import (
    QAbstractButton, QTabWidget, QTableView, QAbstractItemView,
    QHeaderView, QLineEdit, QComboBox, QTextEdit, QPlainTextEdit,
    QAbstractSpinBox, QFormLayout, QWidget,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(BASE_DIR, "assets", "icons")

ICON_SIZE_COMPACT = 15
ICON_SIZE_NORMAL = 17
ICON_SIZE_TAB = 18
ICON_SIZE_HEADER = 20
ICON_SIZE_CARD = 24
ICON_SIZE_NAV = 26
ICON_SIZE_HERO = 30


def _qobject_is_alive(obj):
    """بررسی ایمن معتبر بودن wrapper پایتون و شیء C++ متناظر در PyQt5."""
    if obj is None:
        return False
    try:
        # thread() در QObject وجود دارد و در صورت حذف شدن شیء C++، RuntimeError می‌دهد.
        obj.thread()
        return True
    except (RuntimeError, ReferenceError):
        return False
    except Exception:
        # برای سازگاری با اشیای سفارشی، خطاهای غیرمرتبط مانع ادامه کار نشوند.
        return True


def _safe_invoke(callback, target):
    """اجرای callback فقط برای QObject زنده؛ خطای deleted wrapper را بی‌صدا مهار می‌کند."""
    if not _qobject_is_alive(target):
        return
    try:
        callback(target)
    except (RuntimeError, ReferenceError):
        return



@lru_cache(maxsize=512)
def get_icon(name, tone="navy"):
    """دریافت آیکون حرفه‌ای با کش داخلی و fallback کنترل‌شده."""
    candidates = (
        os.path.join(ICON_DIR, f"{name}_{tone}.svg"),
        os.path.join(ICON_DIR, f"{name}_navy.svg"),
    )
    for path in candidates:
        if os.path.exists(path):
            return QIcon(path)
    return QIcon()


def set_button_style(button, icon_name=None, role=None, tooltip=None,
                     icon_size=ICON_SIZE_NORMAL, compact=False):
    """آیکون، نقش رنگی و اندازه استاندارد را روی یک دکمه اعمال می‌کند."""
    if icon_name:
        tone = "white" if role in {"primary", "success", "danger"} else "navy"
        button.setIcon(get_icon(icon_name, tone))
        button.setIconSize(QSize(icon_size if not compact else ICON_SIZE_COMPACT,
                                 icon_size if not compact else ICON_SIZE_COMPACT))
    if role:
        button.setProperty("uiRole", role)
    button.setProperty("compact", bool(compact))
    button.setProperty("uiIconName", icon_name or "")
    button.setCursor(Qt.PointingHandCursor)
    if tooltip:
        button.setToolTip(tooltip)
    button.style().unpolish(button)
    button.style().polish(button)
    button.update()
    return button


BUTTON_RULES = [
    # فعل‌های عملیاتی باید پیش از واژه‌های عمومی مانند «عضو» بررسی شوند.
    (r"حذف", "delete", "danger"),
    (r"ویرایش|تغییر نام", "edit", "secondary"),
    (r"ثبت عضو جدید|افزودن عضو|عضو جدید", "user_plus", "success"),
    (r"ثبت جلسه", "calendar", "success"),
    (r"ثبت مصوبه", "resolution", "success"),
    (r"افزودن|ثبت .*جدید|ثبت اقدام", "plus", "success"),
    (r"ذخیره|تأیید", "save", "primary"),
    (r"ورود", "check", "primary"),
    (r"جستجو|استعلام", "search", "secondary"),
    (r"بازگشت", "back", "ghost"),
    (r"خروج", "logout", "danger"),
    (r"ریست", "refresh", "danger"),
    (r"انصراف|بستن", "close", "ghost"),
    (r"دانلود|خروجی بسته|GeoJSON", "download", "primary"),
    (r"بارگذاری|ورود بسته", "upload", "secondary"),
    (r"بکاپ", "database", "secondary"),
    (r"بازگردانی", "restore", "secondary"),
    (r"اتصال", "link", "secondary"),
    (r"کمیته", "committee", "secondary"),
    (r"عضو|نماینده", "users", "secondary"),
    (r"بروزرسانی|بازسازی|بازبینی|تازه", "refresh", "secondary"),
    (r"مکاتبه|نامه|کارتابل|ارجاع", "mail", "secondary"),
    (r"تصمیم", "check", "secondary"),
    (r"قرارداد|پیمانکار|صورت.?وضعیت|پرداخت", "report", "secondary"),
    (r"رضایت|نظرسنجی|مشارکت", "users", "secondary"),
    (r"قالب|سند Word|سند", "file", "secondary"),
    (r"تقویم|رویداد|اعلان", "calendar", "secondary"),
    (r"گزارش", "report", "primary"),
    (r"پاورپوینت", "presentation", "secondary"),
    (r"اکسل", "sheet", "secondary"),
    (r"PDF", "pdf", "secondary"),
    (r"مسجد", "mosque", "secondary"),
    (r"مکان", "pin", "secondary"),
    (r"خیابان|کوچه|معبر", "road", "secondary"),
    (r"آفلاین", "offline", "secondary"),
    (r"آنلاین", "globe", "secondary"),
    (r"نقشه|محدوده|بلوک", "map", "secondary"),
    (r"نمایش|مشاهده|پیش.?نمایش", "eye", "secondary"),
    (r"برآورد", "info", "secondary"),
]


def _clean_text(text):
    text = (text or "").replace("\n", " ")
    text = re.sub(r"[🗺️👥⚙️📋✅📊🛠️🏙️📥➕🕌🖼↻💾📂🗑️📤🔎⚠️]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _polish_button(button):
    if button.property("skipAutoPolish"):
        return
    text = _clean_text(button.text())
    if text and text != button.text():
        button.setText(text)
    if button.property("dashboardIcon"):
        return
    if button.property("danger"):
        set_button_style(button, "delete", "danger")
        return
    if button.property("success"):
        icon_name = "plus" if re.search(r"افزودن|ثبت", text) else "check"
        set_button_style(button, icon_name, "success")
        return
    for pattern, icon_name, role in BUTTON_RULES:
        if re.search(pattern, text):
            set_button_style(button, icon_name, role)
            return
    set_button_style(button, None, "secondary")


def polish_buttons(root):
    if not _qobject_is_alive(root):
        return
    try:
        buttons = list(root.findChildren(QAbstractButton))
    except (RuntimeError, ReferenceError):
        return
    for button in buttons:
        _safe_invoke(_polish_button, button)


TAB_RULES = [
    (r"مشخصات", "info"),
    (r"اعضا|شورا|کاربران|دسترسی", "users"),
    (r"جلسات", "calendar"),
    (r"مصوبات", "resolution"),
    (r"مسائل|نیازها", "warning"),
    (r"اقدامات", "check"),
    (r"محدوده|بلوک", "map"),
    (r"نقشه کلی|نقشه شهر", "city"),
    (r"خیابان|کوچه|معبر", "road"),
    (r"اماکن|مکان", "pin"),
    (r"مساجد|مسجد", "mosque"),
    (r"آفلاین", "offline"),
    (r"اولویت|درخواست", "list"),
    (r"جمعیت|خانوار", "users"),
    (r"بودجه|هزینه|کنترل مدیریتی", "report"),
    (r"هشدار|سررسید", "warning"),
    (r"دستگاه", "users"),
    (r"عملکرد|کنترل کیفیت", "check"),
    (r"پرونده جامع", "home"),
    (r"مکاتبه|نامه|کارتابل|ارجاع", "mail"),
    (r"تأیید|تصمیم", "check"),
    (r"تقویم|اعلان|پایش اجرایی", "calendar"),
    (r"برنامه عملیاتی|پروژه|گانت|ریسک|کنترل تغییر", "report"),
    (r"قرارداد|پیمانکار|صورت.?وضعیت|پرداخت", "report"),
    (r"رضایت|نظرسنجی|مشارکت", "users"),
    (r"قالب|اسناد تولید", "file"),
    (r"گزارش", "report"),
    (r"تنظیمات", "settings"),
    (r"سابقه|فعالیت|حسابرسی", "refresh"),
    (r"عملیات میدانی|بازدید", "pin"),
    (r"همگام‌سازی", "offline"),
    (r"تحلیل عملیاتی", "report"),
]


def polish_tabs(root):
    if not _qobject_is_alive(root):
        return
    try:
        tab_widgets = list(root.findChildren(QTabWidget))
    except (RuntimeError, ReferenceError):
        return
    for tabs in tab_widgets:
        if not _qobject_is_alive(tabs):
            continue
        try:
            tabs.setIconSize(QSize(ICON_SIZE_TAB, ICON_SIZE_TAB))
            tabs.setDocumentMode(True)
            tabs.tabBar().setExpanding(True)
            tabs.tabBar().setUsesScrollButtons(True)
            tabs.tabBar().setProperty("cleanTabs", True)
            for index in range(tabs.count()):
                title = tabs.tabText(index)
                for pattern, icon_name in TAB_RULES:
                    if re.search(pattern, title):
                        tabs.setTabIcon(index, get_icon(icon_name, "navy"))
                        break
        except (RuntimeError, ReferenceError):
            continue


def polish_tables(root):
    if not _qobject_is_alive(root):
        return
    try:
        tables = list(root.findChildren(QTableView))
    except (RuntimeError, ReferenceError):
        return
    for table in tables:
        if not _qobject_is_alive(table):
            continue
        try:
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectRows)
            table.setSelectionMode(QAbstractItemView.SingleSelection)
            table.setShowGrid(False)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(38)
            header = table.horizontalHeader()
            header.setMinimumHeight(38)
            header.setDefaultAlignment(Qt.AlignCenter)
            header.setStretchLastSection(True)
        except (RuntimeError, ReferenceError):
            continue


def _is_light_input_surface(widget):
    """تشخیص ورودی‌های واقعاً روشن؛ مخصوصاً دیالوگ‌های بومی macOS/Windows."""
    try:
        window = widget.window()
        if window and (window.inherits("QInputDialog") or window.inherits("QFileDialog")):
            return True
        base = widget.palette().color(QPalette.Base)
        luminance = (0.2126 * base.red()) + (0.7152 * base.green()) + (0.0722 * base.blue())
        return luminance >= 180
    except (RuntimeError, ReferenceError, AttributeError):
        return False


def _polish_input(widget):
    if not _qobject_is_alive(widget):
        return
    try:
        widget.setProperty("cleanInput", True)
        light_surface = _is_light_input_surface(widget)
        if widget.property("lightInputSurface") != light_surface:
            widget.setProperty("lightInputSurface", light_surface)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
    except (RuntimeError, ReferenceError):
        return


def polish_inputs(root):
    if not _qobject_is_alive(root):
        return
    input_types = (QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QAbstractSpinBox)
    for widget_type in input_types:
        try:
            widgets = list(root.findChildren(widget_type))
        except (RuntimeError, ReferenceError):
            return
        for widget in widgets:
            _safe_invoke(_polish_input, widget)



def polish_forms(root):
    if not _qobject_is_alive(root):
        return
    try:
        forms = list(root.findChildren(QFormLayout))
    except (RuntimeError, ReferenceError):
        return
    for form in forms:
        if not _qobject_is_alive(form):
            continue
        try:
            form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.setFormAlignment(Qt.AlignTop)
            form.setHorizontalSpacing(16)
            form.setVerticalSpacing(10)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        except (RuntimeError, ReferenceError):
            continue


def polish_widget_tree(root):
    if not _qobject_is_alive(root):
        return
    for callback in (polish_buttons, polish_tabs, polish_tables, polish_inputs, polish_forms):
        _safe_invoke(callback, root)
    if not _qobject_is_alive(root):
        return
    try:
        root.setWindowIcon(get_icon("map", "navy"))
    except (RuntimeError, ReferenceError, AttributeError):
        pass


class UiPolishFilter(QObject):
    """یکدست‌سازی خودکار پنجره‌ها، دیالوگ‌ها و عناصر پویا."""
    def eventFilter(self, obj, event):
        try:
            # فقط پنجره‌های سطح بالا نیاز به پرداخت کامل دارند. پردازش QLabel/QFrameهای
            # موقت باعث زمان‌بندی روی اشیایی می‌شد که پیش از اجرای QTimer حذف می‌شدند.
            if (
                event.type() == QEvent.Show
                and isinstance(obj, QWidget)
                and obj.isWindow()
            ):
                QTimer.singleShot(0, lambda target=obj: _safe_invoke(polish_widget_tree, target))
            elif event.type() == QEvent.ChildAdded:
                child = event.child()
                if isinstance(child, QAbstractButton):
                    QTimer.singleShot(0, lambda target=child: _safe_invoke(_polish_button, target))
                elif isinstance(child, (QLineEdit, QComboBox, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
                    QTimer.singleShot(0, lambda target=child: _safe_invoke(_polish_input, target))
        except (RuntimeError, ReferenceError):
            pass
        except Exception:
            pass
        return False
