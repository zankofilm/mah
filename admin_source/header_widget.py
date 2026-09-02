# -*- coding: utf-8 -*-
"""هدر رسمی، حرفه‌ای و واکنش‌گرای سامانه جوانرود."""

import os

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QToolButton, QWidget,
    QBoxLayout,
)
from PyQt5.QtGui import (
    QPixmap, QPainter, QColor, QLinearGradient, QPen, QPainterPath,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRectF

from icon_manager import get_icon
from access_control import role_title
from jalali_utils import today_jalali, to_persian_digits
from design_system import PROFILE_COMPACT, PROFILE_COMFORTABLE, PROFILE_SPACIOUS

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBLEM_PATH = os.path.join(BASE_DIR, "assets", "official_emblem.png")
FLAG_PATH = os.path.join(BASE_DIR, "assets", "approved_flag.png")
HEADER_HEIGHT = 132

HEADER_FRAME_STYLE = """
QFrame#SoftwareHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #06162f, stop:0.46 #092a59, stop:1 #071b3b);
    border: none;
    border-bottom: 2px solid #d1a84c;
}
"""
TRANSPARENT = "background: transparent; border: none;"


def _tinted_pixmap(path, size, color="#ffffff"):
    pix = QPixmap(path)
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


def _label(text, css, align=Qt.AlignCenter, wrap=False):
    lbl = QLabel(text)
    lbl.setAlignment(align)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(TRANSPARENT + css)
    lbl.setAttribute(Qt.WA_TranslucentBackground, True)
    return lbl


class IranFlagWidget(QLabel):
    """پرچم تصویری تأییدشده؛ در صورت نبود فایل، با تصویر خالی جایگزین نمی‌شود."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(112, 60)
        self.setAlignment(Qt.AlignCenter)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setToolTip("پرچم جمهوری اسلامی ایران")
        self._refresh_pixmap()

    def _refresh_pixmap(self):
        pix = QPixmap(FLAG_PATH)
        if not pix.isNull():
            pix = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.setPixmap(pix)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_pixmap()


class SoftwareHeader(QFrame):
    settings_requested = pyqtSignal()
    notifications_requested = pyqtSignal()
    logout_requested = pyqtSignal()
    search_requested = pyqtSignal()

    def __init__(self, current_user=None, unread_count=0, subtitle="", db=None,
                 show_tools=True, login_mode=False, search_mode=False, parent=None):
        super().__init__(parent)
        if current_user is None and db is not None:
            try:
                current_user = db.get_current_user() or {}
            except Exception:
                current_user = {}

        self.current_user = current_user or {}
        self.subtitle = subtitle or "نسخه ادمین | داشبورد مدیریتی"
        self.show_tools = bool(show_tools)
        self.login_mode = bool(login_mode)
        self.search_mode = bool(search_mode)
        self.tool_buttons = []
        self._responsive_profile = None

        self.setObjectName("SoftwareHeader")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(HEADER_FRAME_STYLE)
        self.setFixedHeight(HEADER_HEIGHT)
        self._build(unread_count)

    def paintEvent(self, event):
        """تزئینات ظریف هدر پس از رسم پس‌زمینه استاندارد Qt."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # هاله نرم سمت راست
        glow = QLinearGradient(self.width() * 0.58, 0, self.width(), 0)
        glow.setColorAt(0.0, QColor(255, 255, 255, 0))
        glow.setColorAt(0.74, QColor(57, 118, 196, 22))
        glow.setColorAt(1.0, QColor(92, 151, 226, 38))
        painter.fillRect(self.rect(), glow)

        # خطوط موجی طلایی و آبی مشابه هدر تأییدشده
        gold_path = QPainterPath()
        gold_path.moveTo(self.width() * 0.33, self.height() - 5)
        gold_path.cubicTo(
            self.width() * 0.43, self.height() - 12,
            self.width() * 0.43, 20,
            self.width() * 0.55, 7,
        )
        painter.setPen(QPen(QColor(216, 177, 91, 150), 1.2))
        painter.drawPath(gold_path)

        blue_path = QPainterPath()
        blue_path.moveTo(self.width() * 0.28, self.height() - 2)
        blue_path.cubicTo(
            self.width() * 0.39, self.height() - 18,
            self.width() * 0.39, 10,
            self.width() * 0.50, 0,
        )
        painter.setPen(QPen(QColor(124, 179, 241, 110), 1.0))
        painter.drawPath(blue_path)
        painter.end()

    def _header_tool(self, title, icon, slot, badge=None):
        btn = QToolButton()
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setIcon(get_icon(icon, "white"))
        btn.setIconSize(QSize(21, 21))
        badge_text = to_persian_digits(badge) if badge else ""
        btn.setText(f"{title}\n{badge_text}" if badge_text else title)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedSize(56, 56)
        btn.setStyleSheet("""
            QToolButton {
                color: #ffffff;
                background: transparent;
                border: 1px solid transparent;
                border-radius: 10px;
                padding: 2px;
                font-weight: 700;
                font-size: 9.5px;
            }
            QToolButton:hover {
                background-color: rgba(255,255,255,0.11);
                border-color: rgba(216,177,91,0.55);
            }
            QToolButton:pressed { background-color: rgba(255,255,255,0.17); }
        """)
        btn.clicked.connect(slot)
        btn.setProperty("headerTool", True)
        btn.setToolTip(title if not badge else f"{title}: {badge_text}")
        self.tool_buttons.append(btn)
        return btn

    def _refresh_official_emblem(self, size):
        size = int(size)
        self.official_emblem.setFixedSize(size + 8, size + 8)
        self.official_emblem.setPixmap(_tinted_pixmap(EMBLEM_PATH, size, "#e2bb62"))

    def _build_official_panel(self):
        panel = QFrame()
        panel.setObjectName("OfficialIdentityPanel")
        panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setStyleSheet("""
            QFrame#OfficialIdentityPanel {
                background: transparent;
                border: none;
                border-right: 1px solid rgba(216,177,91,0.62);
            }
        """)
        panel.setFixedWidth(332)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        emblem = QLabel()
        emblem.setAlignment(Qt.AlignCenter)
        emblem.setStyleSheet(TRANSPARENT)
        self.official_emblem = emblem
        self._refresh_official_emblem(52)
        layout.addStretch(1)
        layout.addWidget(emblem, 0, Qt.AlignHCenter)

        self.ministry_label = _label(
            "وزارت کشور",
            "color:#f5d98f; font-size:14px; font-weight:800;",
            Qt.AlignCenter,
        )
        self.province_label = _label(
            "استانداری کرمانشاه",
            "color:#f5d98f; font-size:14px; font-weight:800;",
            Qt.AlignCenter,
        )
        self.governorate_label = _label(
            "فرمانداری شهرستان جوانرود",
            "color:#ffffff; font-size:15px; font-weight:900;",
            Qt.AlignCenter,
        )
        layout.addWidget(self.ministry_label)
        layout.addWidget(self.province_label)
        layout.addWidget(self.governorate_label)
        layout.addStretch(1)
        return panel

    def _build_center_panel(self):
        panel = QFrame()
        panel.setObjectName("HeaderTitlePanel")
        panel.setAttribute(Qt.WA_TranslucentBackground, True)
        panel.setStyleSheet("QFrame#HeaderTitlePanel { background: transparent; border: none; }")
        panel.setMinimumWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 9, 18, 7)
        layout.setSpacing(3)
        layout.addStretch(1)

        self.title_label = _label(
            "سامانه جامع مدیریت محلات و بلوک‌های شهرستان جوانرود",
            "color:#f2c35f; font-size:23px; font-weight:900;",
            Qt.AlignCenter,
            True,
        )
        self.subtitle_label = _label(
            self.subtitle,
            "color:#dce9fb; font-size:12px; font-weight:700;",
            Qt.AlignCenter,
            True,
        )
        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)

        line = QFrame()
        line.setFixedHeight(2)
        line.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0, "
            "stop:0 transparent, stop:0.20 #d9b15a, stop:0.80 #d9b15a, stop:1 transparent); border:none;"
        )
        layout.addWidget(line)
        layout.addStretch(1)
        return panel

    def _build_action_panel(self, unread_count):
        panel = QFrame()
        panel.setObjectName("HeaderActionPanel")
        panel.setAttribute(Qt.WA_TranslucentBackground, True)
        panel.setStyleSheet("QFrame#HeaderActionPanel { background: transparent; border: none; }")
        panel.setFixedWidth(410)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 8, 10, 8)
        layout.setSpacing(10)

        tools_col = QHBoxLayout()
        tools_col.setSpacing(6)
        if self.search_mode:
            tools_col.addWidget(self._header_tool("جستجو", "search", self.search_requested.emit))
        tools_col.addWidget(self._header_tool("اعلان‌ها", "warning", self.notifications_requested.emit, unread_count))
        tools_col.addWidget(self._header_tool("تنظیمات", "settings", self.settings_requested.emit))
        tools_col.addWidget(self._header_tool("خروج", "logout", self.logout_requested.emit))
        layout.addLayout(tools_col)

        user_col = QVBoxLayout()
        user_col.setSpacing(1)
        self.user_name_label = _label(
            "ورود امن به سامانه" if self.login_mode else (self.current_user.get("full_name") or "ادمین سیستم"),
            "color:#ffffff; font-size:12px; font-weight:800;",
            Qt.AlignLeft | Qt.AlignVCenter,
        )
        self.user_role_label = _label(
            "احراز هویت کاربران" if self.login_mode else (role_title(self.current_user.get("role")) or "مدیر ارشد سیستم"),
            "color:#cfe0f7; font-size:9px; font-weight:600;",
            Qt.AlignLeft | Qt.AlignVCenter,
        )
        self.user_date_label = _label(
            today_jalali(),
            "color:#92b8e7; font-size:9px;",
            Qt.AlignLeft | Qt.AlignVCenter,
        )
        user_col.addStretch(1)
        user_col.addWidget(self.user_name_label)
        user_col.addWidget(self.user_role_label)
        user_col.addWidget(self.user_date_label)
        user_col.addStretch(1)
        layout.addLayout(user_col, 1)

        flag = IranFlagWidget()
        self.flag_widget = flag
        layout.addWidget(flag)

        # نشان تکراری کنار پرچم حذف شده است؛ پرچم تأییدشده به‌تنهایی نمایش داده می‌شود.
        self.badge_label = None
        return panel

    def _build(self, unread_count):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        row_wrap = QWidget()
        row_wrap.setObjectName("SoftwareHeaderContent")
        row_wrap.setAttribute(Qt.WA_TranslucentBackground, True)
        row_wrap.setStyleSheet("QWidget#SoftwareHeaderContent { background: transparent; border: none; }")
        row = QHBoxLayout(row_wrap)
        row.setDirection(QBoxLayout.LeftToRight)
        row.setContentsMargins(14, 8, 14, 8)
        row.setSpacing(14)

        self.official_panel = self._build_official_panel()
        self.center_panel = self._build_center_panel()
        self.action_panel = self._build_action_panel(unread_count)

        row.addWidget(self.action_panel)
        row.addWidget(self.center_panel, 1)
        row.addWidget(self.official_panel)
        self.header_row_layout = row
        outer.addWidget(row_wrap)

    def set_responsive_profile(self, profile):
        """هدر در 1366×768 تا 4K بدون بریدگی باقی می‌ماند."""
        if self._responsive_profile == profile:
            return
        self._responsive_profile = profile
        compact = profile == PROFILE_COMPACT
        spacious = profile == PROFILE_SPACIOUS

        self.setFixedHeight(112 if compact else (142 if spacious else 128))
        self.action_panel.setFixedWidth(245 if compact else (450 if spacious else 395))
        self.official_panel.setFixedWidth(220 if compact else (360 if spacious else 320))
        self.center_panel.setMinimumWidth(270 if compact else (580 if spacious else 450))

        self.title_label.setStyleSheet(
            TRANSPARENT + f"color:#f2c35f; font-size:{17 if compact else (25 if spacious else 22)}px; font-weight:900;"
        )
        self.subtitle_label.setStyleSheet(
            TRANSPARENT + f"color:#dce9fb; font-size:{9 if compact else (13 if spacious else 11)}px; font-weight:700;"
        )

        self.ministry_label.setStyleSheet(
            TRANSPARENT + f"color:#f5d98f; font-size:{10 if compact else (15 if spacious else 13)}px; font-weight:800;"
        )
        self.province_label.setStyleSheet(
            TRANSPARENT + f"color:#f5d98f; font-size:{10 if compact else (15 if spacious else 13)}px; font-weight:800;"
        )
        self.governorate_label.setStyleSheet(
            TRANSPARENT + f"color:#ffffff; font-size:{11 if compact else (16 if spacious else 14)}px; font-weight:900;"
        )
        self._refresh_official_emblem(38 if compact else (58 if spacious else 48))

        self.user_name_label.setVisible(not compact)
        self.user_role_label.setVisible(not compact)
        self.user_date_label.setVisible(not compact)
        if self.badge_label is not None:
            self.badge_label.setVisible(not compact)
        self.flag_widget.setVisible(True)
        self.flag_widget.setFixedSize(74 if compact else (106 if spacious else 92), 46 if compact else (66 if spacious else 58))

        for button in self.tool_buttons:
            if compact:
                button.setToolButtonStyle(Qt.ToolButtonIconOnly)
                button.setFixedSize(38, 38)
                button.setIconSize(QSize(18, 18))
            else:
                button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                button.setFixedSize(60 if spacious else 54, 60 if spacious else 54)
                button.setIconSize(QSize(22 if spacious else 20, 22 if spacious else 20))
        self.updateGeometry()


def build_official_header(app_subtitle="نسخه ادمین | داشبورد مدیریتی", db=None):
    unread = 0
    current = None
    if db is not None:
        try:
            current = db.get_current_user() or {}
            unread = len(db.get_in_app_notifications(user_id=current.get("id"), unread_only=True))
        except Exception:
            unread = 0
    return SoftwareHeader(
        current_user=current,
        db=db,
        unread_count=unread,
        subtitle=app_subtitle,
        show_tools=True,
    )
