# -*- coding: utf-8 -*-
"""داشبورد رسمی و حرفه‌ای سامانه مدیریت محلات و بلوک‌های شهرستان جوانرود."""

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QGridLayout,
    QToolButton, QFrame, QSizePolicy, QScrollArea, QMenu, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QGraphicsDropShadowEffect,
    QLayout, QMessageBox, QShortcut,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QUrl, QTimer, QRectF
from PyQt5.QtGui import QKeySequence, QPainter, QColor, QPen

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover
    QWebEngineView = None

from theme import DASHBOARD_STYLESHEET
from version import APP_VERSION
from icon_manager import get_icon
from design_system import (
    PROFILE_COMPACT, PROFILE_COMFORTABLE, PROFILE_SPACIOUS,
    metrics_for_width,
)
from access_control import has_permission, role_title
from global_search_dialog import GlobalSearchDialog
from map_html import build_all_zones_view_html
from runtime_paths import get_data_dir
from header_widget import SoftwareHeader
from jalali_utils import now_jalali, format_jalali, to_persian_digits, convert_dates_in_text


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBLEM_PATH = os.path.join(BASE_DIR, "assets", "official_emblem.png")


def _fa_number(value):
    return str(value if value not in (None, "") else 0).translate(
        str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    )


def _shadow(widget, blur=20, y=4, opacity=32):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(8, 28, 58, opacity))
    widget.setGraphicsEffect(effect)


class DashboardHeader(SoftwareHeader):
    def __init__(self, current_user, unread_count=0, parent=None):
        super().__init__(
            current_user=current_user,
            unread_count=unread_count,
            subtitle="نسخه ادمین | داشبورد مدیریتی",
            show_tools=True,
            search_mode=True,
            parent=parent,
        )


class MetricCard(QFrame):
    """کارت آماری مطابق طرح تأییدشده، با آیکون رنگی و متن خوانا."""

    def __init__(self, title, icon_name, accent="blue", unit="", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setProperty("accent", accent)
        self.setMinimumHeight(122)
        self.unit = unit
        _shadow(self, 18, 4, 28)

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 16, 16, 16)
        row.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel("۰")
        self.value_label.setObjectName("MetricValue")
        self.note_label = QLabel(unit or "به‌روزرسانی از پایگاه داده")
        self.note_label.setObjectName("MetricChange")
        text.addWidget(self.title_label)
        text.addWidget(self.value_label)
        text.addWidget(self.note_label)
        text.addStretch(1)
        row.addLayout(text, 1)

        icon_wrap = QFrame()
        icon_wrap.setObjectName("MetricIcon")
        icon_wrap.setProperty("accent", accent)
        icon_wrap.setFixedSize(58, 58)
        icon_layout = QVBoxLayout(icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon = QLabel()
        icon.setPixmap(get_icon(icon_name, "white").pixmap(29, 29))
        icon.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon)
        row.addWidget(icon_wrap)

    def set_value(self, value, note=None):
        self.value_label.setText(_fa_number(value))
        if note is not None:
            self.note_label.setText(note)

    def apply_density(self, profile):
        compact = profile == PROFILE_COMPACT
        spacious = profile == PROFILE_SPACIOUS
        self.setMinimumHeight(104 if compact else (132 if spacious else 118))
        icon_size = 48 if compact else (64 if spacious else 56)
        icon_wrap = self.findChild(QFrame, "MetricIcon")
        if icon_wrap is not None:
            icon_wrap.setFixedSize(icon_size, icon_size)
        self.setProperty("compact", compact)
        self.style().unpolish(self)
        self.style().polish(self)


class PanelCard(QFrame):
    """پنل سفید با عنوان، آیکون و اقدام اختیاری."""

    def __init__(self, title, icon_name=None, action_text=None, action_slot=None, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardPanel")
        _shadow(self, 18, 4, 24)
        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(14, 12, 14, 14)
        self.layout_main.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(8)
        if icon_name:
            icon_wrap = QFrame()
            icon_wrap.setObjectName("PanelIcon")
            icon_wrap.setFixedSize(34, 34)
            il = QVBoxLayout(icon_wrap)
            il.setContentsMargins(0, 0, 0, 0)
            icon = QLabel()
            icon.setPixmap(get_icon(icon_name, "navy").pixmap(18, 18))
            icon.setAlignment(Qt.AlignCenter)
            il.addWidget(icon)
            header.addWidget(icon_wrap)
        title_label = QLabel(title)
        title_label.setObjectName("PanelTitle")
        header.addWidget(title_label)
        header.addStretch(1)
        if action_text:
            action = QPushButton(action_text)
            action.setObjectName("PanelAction")
            action.setProperty("skipAutoPolish", True)
            if action_slot:
                action.clicked.connect(action_slot)
            header.addWidget(action)
        self.layout_main.addLayout(header)

        divider = QFrame()
        divider.setObjectName("PanelDivider")
        divider.setFixedHeight(1)
        self.layout_main.addWidget(divider)

    def add_widget(self, widget, stretch=0):
        self.layout_main.addWidget(widget, stretch)

    def add_layout(self, layout, stretch=0):
        self.layout_main.addLayout(layout, stretch)


class DonutChartWidget(QWidget):
    """نمودار حلقه‌ای سبک و بدون وابستگی خارجی."""

    COLORS = ["#25a55f", "#3478e5", "#f2aa16", "#ef4444"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [0, 0, 0, 0]
        self.setMinimumSize(170, 170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_values(self, values):
        values = [max(0, int(v or 0)) for v in list(values)[:4]]
        self.values = values + [0] * (4 - len(values))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = max(90, min(self.width(), self.height()) - 20)
        rect = QRectF(
            (self.width() - side) / 2 + 14,
            (self.height() - side) / 2 + 14,
            side - 28,
            side - 28,
        )
        pen_width = max(16, int(side * 0.13))
        total = sum(self.values)
        if total <= 0:
            painter.setPen(QPen(QColor("#e5ebf2"), pen_width, Qt.SolidLine, Qt.FlatCap))
            painter.drawArc(rect, 0, 360 * 16)
        else:
            start = 90 * 16
            for value, color in zip(self.values, self.COLORS):
                if value <= 0:
                    continue
                span = -int((value / total) * 360 * 16)
                painter.setPen(QPen(QColor(color), pen_width, Qt.SolidLine, Qt.FlatCap))
                painter.drawArc(rect, start, span)
                start += span
        painter.setPen(QColor("#173a68"))
        painter.drawText(rect, Qt.AlignCenter, _fa_number(total))
        painter.end()


class DashboardWindow(QWidget):
    open_blocking_module = pyqtSignal()
    open_council_module = pyqtSignal()
    open_committees_module = pyqtSignal()
    open_social_council_module = pyqtSignal()
    open_priority_module = pyqtSignal()
    open_actions_module = pyqtSignal()
    open_settings_module = pyqtSignal()
    open_reports_module = pyqtSignal()
    open_system_settings_module = pyqtSignal()
    open_ai_settings_module = pyqtSignal()
    open_city_comparison_module = pyqtSignal()
    open_city_wide_map_module = pyqtSignal()
    open_neighborhood_management_module = pyqtSignal()
    open_correspondence_module = pyqtSignal()
    open_approval_templates_module = pyqtSignal()
    open_management_calendar_module = pyqtSignal()
    open_project_control_module = pyqtSignal()
    open_contracts_satisfaction_module = pyqtSignal()
    open_data_governance_module = pyqtSignal()
    open_production_center_module = pyqtSignal()
    open_operations_center_module = pyqtSignal()
    open_client_management_module = pyqtSignal()
    open_messaging_module = pyqtSignal()
    open_population_estimation_module = pyqtSignal()
    logout_requested = pyqtSignal()
    search_result_activated = pyqtSignal(object)

    def __init__(self, db, current_user=None):
        super().__init__()
        self.db = db
        self.current_user = current_user or db.get_current_user() or {}
        self.setWindowTitle("داشبورد — سامانه جامع مدیریت محلات و بلوک‌های شهرستان جوانرود")
        self.setObjectName("DashboardRoot")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1480, 920)
        self.setMinimumSize(960, 540)
        self.setStyleSheet(DASHBOARD_STYLESHEET)
        self.metric_cards = {}
        self._responsive_profile = None
        self._responsive_update_pending = False
        self._build_ui()
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.search_shortcut.activated.connect(self.open_global_search)
        self.refresh_stats()

    def _allowed(self, permission):
        return has_permission(self.current_user.get("role"), permission)

    def _sidebar_button(self, title, icon_name, signal, permission, active=False):
        button = QToolButton()
        button.setProperty("sidebarNav", True)
        button.setProperty("active", active)
        button.setProperty("fullText", title)
        grid_text = {
            "محلات و بلوک‌ها": "محلات و\nبلوک‌ها",
            "نقشه بلوک‌ها": "نقشه\nبلوک‌ها",
            "اعضای معتمد": "اعضای\nمعتمد",
            "کاربران و دسترسی‌ها": "کاربران و\nدسترسی‌ها",
        }.get(title, title)
        button.setProperty("gridText", grid_text)
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setText(grid_text)
        button.setIcon(get_icon(icon_name, "gold" if not active else "white"))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(title)
        button.setCursor(Qt.PointingHandCursor)
        button.setMinimumHeight(62)
        button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        allowed = self._allowed(permission)
        button.setEnabled(allowed)
        if allowed:
            if active:
                button.clicked.connect(self.refresh_stats)
            else:
                button.clicked.connect(signal.emit)
        else:
            button.setToolTip("حساب فعلی مجوز ورود به این بخش را ندارد.")
        return button

    def _add_more_action(self, menu, title, icon_name, signal, permission):
        action = menu.addAction(get_icon(icon_name, "navy"), title)
        allowed = self._allowed(permission)
        action.setEnabled(allowed)
        if allowed:
            action.triggered.connect(lambda checked=False, target=signal: target.emit())
        return action

    def _layout_sidebar_navigation(self, columns=2):
        columns = max(1, int(columns or 1))
        while self.sidebar_nav_grid.count():
            self.sidebar_nav_grid.takeAt(0)
        for index, button in enumerate(self.sidebar_buttons):
            self.sidebar_nav_grid.addWidget(button, index // columns, index % columns)
        for column in range(2):
            self.sidebar_nav_grid.setColumnStretch(column, 1 if column < columns else 0)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("DashboardSidebar")
        sidebar.setLayoutDirection(Qt.RightToLeft)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(10)

        self.sidebar_title = QLabel("داشبورد مدیریتی")
        self.sidebar_title.setObjectName("SidebarTitle")
        self.sidebar_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.sidebar_title)

        user_card = QFrame()
        user_card.setObjectName("SidebarUserCard")
        ucl = QHBoxLayout(user_card)
        ucl.setContentsMargins(12, 10, 12, 10)
        ucl.setSpacing(10)
        avatar = QLabel()
        avatar.setObjectName("SidebarUserAvatar")
        avatar.setPixmap(get_icon("user", "gold").pixmap(30, 30))
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(42, 42)
        info = QVBoxLayout()
        info.setSpacing(2)
        user_name = QLabel(self.current_user.get("full_name") or "ادمین سیستم")
        user_name.setObjectName("SidebarUserName")
        user_role = QLabel(role_title(self.current_user.get("role")) or "مدیر ارشد سیستم")
        user_role.setObjectName("SidebarUserRole")
        info.addWidget(user_name)
        info.addWidget(user_role)
        ucl.addWidget(avatar)
        ucl.addLayout(info, 1)
        layout.addWidget(user_card)

        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("DashboardSidebarScroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QFrame.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        nav_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        nav_host = QWidget()
        nav_host.setObjectName("DashboardSidebarNavHost")
        nav_layout = QVBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        self.sidebar_buttons = []
        self.sidebar_nav_grid = QGridLayout()
        self.sidebar_nav_grid.setContentsMargins(0, 0, 0, 0)
        self.sidebar_nav_grid.setHorizontalSpacing(7)
        self.sidebar_nav_grid.setVerticalSpacing(7)
        primary = [
            ("داشبورد", "home", self.open_neighborhood_management_module, "neighborhood", True),
            ("محلات و بلوک‌ها", "city", self.open_blocking_module, "blocking", False),
            ("نقشه بلوک‌ها", "map", self.open_blocking_module, "blocking", False),
            ("گزارش‌ها", "report", self.open_reports_module, "reports", False),
            ("پیام‌ها", "mail", self.open_messaging_module, "messaging", False),
            ("اعضای معتمد", "users", self.open_council_module, "council", False),
            ("کاربران و دسترسی‌ها", "users", self.open_client_management_module, "client_management", False),
            ("تنظیمات", "settings", self.open_system_settings_module, "system_settings", False),
        ]
        for spec in primary:
            btn = self._sidebar_button(*spec)
            self.sidebar_buttons.append(btn)
        self._layout_sidebar_navigation(2)
        nav_layout.addLayout(self.sidebar_nav_grid)

        more_button = QToolButton()
        more_button.setObjectName("SidebarMore")
        more_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        more_button.setText("ماژول‌های بیشتر")
        more_button.setIcon(get_icon("list", "gold"))
        more_button.setIconSize(QSize(23, 23))
        more_button.setPopupMode(QToolButton.InstantPopup)
        more_menu = QMenu(more_button)
        self._add_more_action(more_menu, "مرکز عملیات", "support", self.open_operations_center_module, "operations_center")
        self._add_more_action(more_menu, "مکاتبات اداری", "mail", self.open_correspondence_module, "correspondence")
        self._add_more_action(more_menu, "برآورد جمعیت", "users", self.open_population_estimation_module, "population")
        self._add_more_action(more_menu, "کنترل پروژه", "presentation", self.open_project_control_module, "project_control")
        self._add_more_action(more_menu, "کمیته‌های شش‌گانه", "committee", self.open_committees_module, "council")
        self._add_more_action(more_menu, "شورای اجتماعی", "culture", self.open_social_council_module, "council")
        self._add_more_action(more_menu, "مدیریت کلاینت‌ها", "security", self.open_client_management_module, "client_management")
        self._add_more_action(more_menu, "مقایسه بلوک‌ها", "report", self.open_city_comparison_module, "neighborhood")
        self._add_more_action(more_menu, "تقویم مدیریتی", "calendar", self.open_management_calendar_module, "calendar")
        more_button.setMenu(more_menu)
        self.sidebar_more_button = more_button
        nav_layout.addWidget(more_button)
        nav_layout.addStretch(1)
        nav_scroll.setWidget(nav_host)
        self.sidebar_nav_scroll = nav_scroll
        self.sidebar_nav_host = nav_host
        layout.addWidget(nav_scroll, 1)

        identity = QFrame()
        identity.setObjectName("SidebarIdentity")
        il = QVBoxLayout(identity)
        il.setContentsMargins(10, 12, 10, 12)
        il.setSpacing(4)
        emblem = QLabel()
        emblem.setPixmap(get_icon("city", "success").pixmap(44, 44))
        emblem.setAlignment(Qt.AlignCenter)
        self.sidebar_identity_emblem = emblem
        self.sidebar_identity_title = QLabel("فرمانداری شهرستان جوانرود")
        self.sidebar_identity_title.setObjectName("SidebarIdentityTitle")
        self.sidebar_identity_title.setAlignment(Qt.AlignCenter)
        self.sidebar_identity_version = QLabel(f"نسخه {to_persian_digits(APP_VERSION)}  •  سامانه محله‌محور")
        self.sidebar_identity_version.setObjectName("SidebarIdentityVersion")
        self.sidebar_identity_version.setAlignment(Qt.AlignCenter)
        il.addWidget(emblem)
        il.addWidget(self.sidebar_identity_title)
        il.addWidget(self.sidebar_identity_version)
        layout.addWidget(identity)
        self.sidebar_identity = identity

        logout = QPushButton("خروج امن")
        logout.setObjectName("SidebarLogout")
        logout.setIcon(get_icon("logout", "white"))
        logout.clicked.connect(self.logout_requested.emit)
        layout.addWidget(logout)
        self.sidebar_logout = logout
        return sidebar

    def _build_map_panel(self):
        panel = PanelCard(
            "نقشه بلوک‌ها",
            "map",
            "مشاهده نقشه کامل",
            self.open_blocking_module.emit,
        )
        map_scroll = QScrollArea()
        map_scroll.setObjectName("DashboardMapScroll")
        map_scroll.setWidgetResizable(True)
        map_scroll.setFrameShape(QFrame.NoFrame)
        map_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        map_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        map_scroll.setMinimumHeight(520)

        map_host = QWidget()
        map_host.setObjectName("DashboardMapHost")
        map_host.setMinimumSize(1080, 500)
        body = QHBoxLayout(map_host)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        legend = QFrame()
        legend.setObjectName("MapLegend")
        ll = QVBoxLayout(legend)
        ll.setContentsMargins(12, 14, 12, 14)
        ll.setSpacing(12)
        for title, color in [
            ("فعال", "#25a55f"),
            ("در حال بررسی", "#3478e5"),
            ("نیاز به پیگیری", "#f2aa16"),
            ("غیرفعال", "#ef4444"),
        ]:
            row = QHBoxLayout()
            label = QLabel(title)
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; background:transparent; border:none; font-size:15px;")
            row.addWidget(label)
            row.addStretch(1)
            row.addWidget(dot)
            ll.addLayout(row)
        ll.addStretch(1)
        legend.setMinimumWidth(165)
        legend.setMaximumWidth(210)
        self.map_legend = legend
        body.addWidget(legend)

        if QWebEngineView is not None:
            self.map_view = QWebEngineView()
            self.map_view.setMinimumSize(850, 470)
            self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.map_view.setFocusPolicy(Qt.StrongFocus)
            self.map_view.setMouseTracking(True)
            self.map_view.setHtml('''<html><body dir="rtl" style="margin:0;background:#071a32;color:#d9e6f8;font-family:Vazirmatn,Segoe UI,Tahoma;height:100vh;display:flex;align-items:center;justify-content:center;"><div style="width:100%;height:100%;position:relative;background:radial-gradient(circle at 20% 20%,#10305b 0,#081b34 45%,#061426 100%);overflow:hidden;"><div style="position:absolute;inset:20px;border:2px solid #e1bd66;border-radius:30px;clip-path:polygon(18% 8%,48% 5%,76% 14%,84% 35%,82% 69%,64% 88%,41% 84%,22% 63%,10% 34%);background:linear-gradient(135deg, rgba(62,103,163,.22), rgba(20,40,78,.35));"></div><div style="position:absolute;right:33%;top:22%;color:#fff;font-weight:800">محله مرکزی</div><div style="position:absolute;right:20%;top:46%;color:#fff;font-weight:800">محله آزادی</div><div style="position:absolute;right:52%;top:50%;color:#fff;font-weight:800">محله مدارس</div><div style="position:absolute;right:28%;top:68%;color:#fff;font-weight:800">محله کردستان</div><div style="position:absolute;right:46%;top:68%;color:#fff;font-weight:800">محله انقلاب</div><div style="position:absolute;left:18px;bottom:18px;background:#0a2141;border:1px solid #d6ac53;color:#f2cf7a;padding:8px 14px;border-radius:12px;font-weight:700">مشاهده نقشه کامل</div></div></body></html>''')
            body.addWidget(self.map_view, 1)
        else:
            self.map_view = None
            placeholder = QLabel("برای نمایش نقشه تعاملی، PyQtWebEngine باید نصب باشد.\nنقشه پس از نصب این افزونه در همین بخش نمایش داده می‌شود.")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setMinimumSize(850, 470)
            body.addWidget(placeholder, 1)
        map_scroll.setWidget(map_host)
        panel.add_widget(map_scroll, 1)
        self.map_scroll = map_scroll
        self.map_host = map_host
        self.map_panel = panel
        return panel

    def _build_activity_panel(self):
        panel = PanelCard(
            "آخرین فعالیت‌ها",
            "warning",
            "مشاهده همه",
            self.open_management_calendar_module.emit,
        )
        self.activity_layout = QVBoxLayout()
        self.activity_layout.setSpacing(7)
        panel.add_layout(self.activity_layout)
        panel.add_widget(QWidget(), 1)
        self.activity_panel = panel
        return panel

    def _build_reports_panel(self):
        panel = PanelCard(
            "گزارش‌های کلیدی",
            "report",
            "مشاهده همه گزارش‌ها",
            self.open_reports_module.emit,
        )
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        cards = [
            ("گزارش‌های مالی", "5", "گزارش", "database", "gold"),
            ("گزارش‌های عمرانی", "9", "گزارش", "presentation", "orange"),
            ("گزارش‌های خدمات شهری", "12", "گزارش", "city", "blue"),
            ("گزارش‌های جمعیتی", "7", "گزارش", "users", "teal"),
        ]
        self.report_summary_cards = []
        self.report_summary_value_labels = []
        for idx, (title, value, subtitle, icon_name, accent) in enumerate(cards):
            card = QFrame()
            card.setObjectName("MiniStat")
            card.setProperty("accent", accent)
            card.setMinimumHeight(154)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(10)

            top = QHBoxLayout()
            top.setSpacing(10)
            icon_wrap = QFrame()
            icon_wrap.setObjectName("MiniStatIcon")
            icon_wrap.setProperty("accent", accent)
            icon_wrap.setFixedSize(54, 54)
            iw = QVBoxLayout(icon_wrap)
            iw.setContentsMargins(0, 0, 0, 0)
            icon = QLabel()
            icon.setAlignment(Qt.AlignCenter)
            icon.setPixmap(get_icon(icon_name, "gold" if accent in ("gold", "orange") else "white").pixmap(26, 26))
            iw.addWidget(icon)
            top.addWidget(icon_wrap)
            top.addStretch(1)
            title_lbl = QLabel(title)
            title_lbl.setObjectName("MiniStatTitle")
            title_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            top.addWidget(title_lbl)
            card_layout.addLayout(top)

            value_lbl = QLabel(_fa_number(value))
            value_lbl.setObjectName("MiniStatValue")
            value_lbl.setAlignment(Qt.AlignCenter)
            subtitle_lbl = QLabel(subtitle)
            subtitle_lbl.setObjectName("MiniStatTitle")
            subtitle_lbl.setAlignment(Qt.AlignCenter)
            link = QPushButton("مشاهده")
            link.setObjectName("MiniStatLink")
            link.setProperty("panelLink", True)
            link.clicked.connect(self.open_reports_module.emit)

            card_layout.addWidget(value_lbl)
            card_layout.addWidget(subtitle_lbl)
            card_layout.addStretch(1)
            card_layout.addWidget(link, 0, Qt.AlignRight)
            grid.addWidget(card, 0, idx)
            self.report_summary_cards.append(card)
            self.report_summary_value_labels.append(value_lbl)

        panel.add_layout(grid, 1)
        self.reports_panel = panel
        return panel

    def _build_status_panel(self):
        panel = PanelCard("نمودار وضعیت بلوک‌ها", "report")
        row = QHBoxLayout()
        row.setSpacing(10)
        chart = DonutChartWidget()
        row.addWidget(chart, 1)
        legend = QVBoxLayout()
        legend.setSpacing(12)
        self.status_legend_labels = []
        for title, color in [
            ("فعال", "#25a55f"),
            ("در حال بررسی", "#3478e5"),
            ("نیاز به پیگیری", "#f2aa16"),
            ("غیرفعال", "#ef4444"),
        ]:
            line = QHBoxLayout()
            label = QLabel(title)
            value = QLabel("۰")
            value.setObjectName("StatusLegendValue")
            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; background:transparent; border:none;")
            line.addWidget(label)
            line.addStretch(1)
            line.addWidget(value)
            line.addWidget(dot)
            legend.addLayout(line)
            self.status_legend_labels.append(value)
        legend.addStretch(1)
        row.addLayout(legend, 1)
        panel.add_layout(row, 1)
        self.donut_chart = chart
        self.status_panel = panel
        return panel

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        try:
            unread = int(self.db.get_system_stats().get("unread_notifications_count", 0))
        except Exception:
            unread = 0
        self.header = DashboardHeader(self.current_user, unread)
        self.header.settings_requested.connect(self.open_system_settings_module.emit)
        self.header.notifications_requested.connect(self.open_management_calendar_module.emit)
        self.header.search_requested.connect(self.open_global_search)
        self.header.logout_requested.connect(self.logout_requested.emit)
        root.addWidget(self.header)

        shell = QWidget()
        shell.setObjectName("DashboardShell")
        shell.setLayoutDirection(Qt.LeftToRight)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.sidebar = self._build_sidebar()
        self.sidebar.setFixedWidth(252)
        shell_layout.addWidget(self.sidebar)

        content_scroll = QScrollArea()
        content_scroll.setObjectName("DashboardScroll")
        content_scroll.setWidgetResizable(True)
        content_scroll.setFrameShape(QFrame.NoFrame)
        content_scroll.setMinimumSize(0, 0)
        content_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_widget = QWidget()
        content_widget.setObjectName("DashboardContent")
        content_widget.setLayoutDirection(Qt.RightToLeft)
        content = QVBoxLayout(content_widget)
        content.setContentsMargins(18, 18, 18, 18)
        content.setSpacing(14)
        self.content_layout = content

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)
        self.metrics_layout = metrics
        self.metric_widgets = []
        metric_specs = [
            ("zones_count", "تعداد محلات", "home", "gold", "محله فعال"),
            ("blocks_count", "تعداد بلوک‌ها", "city", "orange", "بلوک ثبت‌شده"),
            ("estimated_population", "ساکنان تحت پوشش", "users", "purple", "نفر"),
            ("unread_notifications_count", "سرعت بروزرسانی", "check", "green", "اطلاعات بروز"),
        ]
        for index, (key, title, icon, accent, unit) in enumerate(metric_specs):
            card = MetricCard(title, icon, accent, unit)
            self.metric_cards[key] = card
            self.metric_widgets.append(card)
            metrics.addWidget(card, 0, index)
        content.addLayout(metrics)

        dashboard_grid = QGridLayout()
        dashboard_grid.setContentsMargins(0, 0, 0, 0)
        dashboard_grid.setHorizontalSpacing(12)
        dashboard_grid.setVerticalSpacing(12)
        self.dashboard_grid = dashboard_grid
        self.map_panel = self._build_map_panel()
        self.activity_panel = self._build_activity_panel()
        self.reports_panel = self._build_reports_panel()
        self.status_panel = self._build_status_panel()
        dashboard_grid.addWidget(self.map_panel, 0, 0, 1, 2)
        dashboard_grid.addWidget(self.activity_panel, 1, 0)
        dashboard_grid.addWidget(self.status_panel, 1, 1)
        dashboard_grid.addWidget(self.reports_panel, 2, 0, 1, 2)
        dashboard_grid.setColumnStretch(0, 2)
        dashboard_grid.setColumnStretch(1, 1)
        dashboard_grid.setRowStretch(0, 4)
        dashboard_grid.setRowStretch(1, 2)
        dashboard_grid.setRowStretch(2, 2)
        content.addLayout(dashboard_grid, 1)

        content_scroll.setWidget(content_widget)
        shell_layout.addWidget(content_scroll, 1)
        self.content_scroll = content_scroll
        self.content_widget = content_widget
        root.addWidget(shell, 1)

        footer = QFrame()
        footer.setObjectName("DashboardFooter")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(18, 5, 18, 5)
        rights = QLabel("تمامی حقوق محفوظ است.")
        rights.setObjectName("FooterRights")
        fl.addWidget(rights)
        fl.addStretch(1)
        self.footer_status = QLabel("پایگاه داده متصل است")
        self.footer_status.setObjectName("FooterStatus")
        fl.addWidget(self.footer_status)
        self.footer_update_label = QLabel("آخرین بروزرسانی: —")
        self.footer_update_label.setObjectName("FooterUpdate")
        fl.addWidget(self.footer_update_label)
        root.addWidget(footer)
        self.footer = footer

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._responsive_update_pending:
            self._responsive_update_pending = True
            QTimer.singleShot(40, self._apply_responsive_from_window)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_responsive_from_window)

    def _apply_responsive_from_window(self):
        self._responsive_update_pending = False
        metrics = metrics_for_width(self.width())
        self.apply_responsive_profile(metrics.profile, metrics)

    @staticmethod
    def _take_all(layout):
        while layout.count():
            layout.takeAt(0)

    def apply_responsive_profile(self, profile, metrics=None):
        metrics = metrics or metrics_for_width(self.width())
        self._responsive_profile = profile
        self.setProperty("responsiveProfile", profile)
        compact = profile == PROFILE_COMPACT
        spacious = profile == PROFILE_SPACIOUS

        sidebar_width = 88 if compact else (272 if spacious else 232)
        self.sidebar.setFixedWidth(sidebar_width)
        self.sidebar_title.setVisible(not compact)
        self.sidebar_identity_title.setVisible(not compact)
        self.sidebar_identity_version.setVisible(not compact)
        self.sidebar_logout.setText("" if compact else "خروج امن")
        self.sidebar_logout.setToolTip("خروج امن")
        self.sidebar_more_button.setText("" if compact else "ماژول‌های بیشتر")
        self._layout_sidebar_navigation(1 if compact else 2)
        for button in self.sidebar_buttons:
            button.setToolButtonStyle(Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextUnderIcon)
            button.setText("" if compact else button.property("gridText"))
            button.setMinimumHeight(48 if compact else (68 if spacious else 62))
            icon_size = 19 if compact else (20 if spacious else 18)
            button.setIconSize(QSize(icon_size, icon_size))

        margin = 10 if compact else (22 if spacious else 16)
        self.content_layout.setContentsMargins(margin, margin, margin, margin)
        self.content_layout.setSpacing(10 if compact else 14)

        self._take_all(self.metrics_layout)
        metric_columns = 1 if self.width() < 760 else (2 if compact else 5)
        for index, card in enumerate(self.metric_widgets):
            card.apply_density(profile)
            self.metrics_layout.addWidget(card, index // metric_columns, index % metric_columns)
        for col in range(5):
            self.metrics_layout.setColumnStretch(col, 1 if col < metric_columns else 0)

        self._take_all(self.dashboard_grid)
        if compact:
            self.dashboard_grid.addWidget(self.map_panel, 0, 0)
            self.dashboard_grid.addWidget(self.activity_panel, 1, 0)
            self.dashboard_grid.addWidget(self.status_panel, 2, 0)
            self.dashboard_grid.addWidget(self.reports_panel, 3, 0)
            self.dashboard_grid.setColumnStretch(0, 1)
            self.map_legend.setVisible(True)
        else:
            self.dashboard_grid.addWidget(self.map_panel, 0, 0, 1, 2)
            self.dashboard_grid.addWidget(self.activity_panel, 1, 0)
            self.dashboard_grid.addWidget(self.status_panel, 1, 1)
            self.dashboard_grid.addWidget(self.reports_panel, 2, 0, 1, 2)
            self.dashboard_grid.setColumnStretch(0, 2)
            self.dashboard_grid.setColumnStretch(1, 1)
            self.map_legend.setVisible(True)

        map_width = 920 if compact else (1280 if spacious else 1080)
        map_height = 470 if compact else (590 if spacious else 520)
        self.map_host.setMinimumSize(map_width, map_height)
        self.map_scroll.setMinimumHeight(430 if compact else (610 if spacious else 540))
        if self.map_view is not None:
            self.map_view.setMinimumSize(max(700, map_width - 220), map_height - 30)
        if hasattr(self.header, "set_responsive_profile"):
            self.header.set_responsive_profile(profile)

        self.style().unpolish(self)
        self.style().polish(self)
        self.updateGeometry()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                DashboardWindow._clear_layout(child_layout)

    def _activity_item(self, title, subtitle="", icon_name="info", severity="normal"):
        frame = QFrame()
        frame.setObjectName("ActivityItem")
        frame.setProperty("severity", severity)
        row = QHBoxLayout(frame)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(9)
        text = QVBoxLayout()
        text.setSpacing(2)
        title_label = QLabel(convert_dates_in_text(title or "بدون عنوان"))
        title_label.setObjectName("ActivityTitle")
        subtitle_label = QLabel(convert_dates_in_text(subtitle or ""))
        subtitle_label.setObjectName("ActivitySubtitle")
        text.addWidget(title_label)
        text.addWidget(subtitle_label)
        row.addLayout(text, 1)
        icon_box = QFrame()
        icon_box.setObjectName("ActivityIcon")
        icon_box.setProperty("severity", severity)
        icon_box.setFixedSize(38, 38)
        il = QVBoxLayout(icon_box)
        il.setContentsMargins(0, 0, 0, 0)
        icon = QLabel()
        icon.setPixmap(get_icon(icon_name, "navy").pixmap(20, 20))
        icon.setAlignment(Qt.AlignCenter)
        il.addWidget(icon)
        row.addWidget(icon_box)
        return frame

    def refresh_map(self):
        if self.map_view is None:
            return
        try:
            zones = self.db.get_zones()
            boundary = self.db.get_boundary() or []
            if not zones and not boundary:
                self.map_view.setHtml('''<html><body dir="rtl" style="margin:0;background:#071a32;color:#d9e6f8;font-family:Vazirmatn,Segoe UI,Tahoma;height:100vh;display:flex;align-items:center;justify-content:center;"><div style="width:100%;height:100%;position:relative;background:radial-gradient(circle at 20% 20%,#10305b 0,#081b34 45%,#061426 100%);overflow:hidden;"><div style="position:absolute;inset:20px;border:2px solid #e1bd66;border-radius:30px;clip-path:polygon(18% 8%,48% 5%,76% 14%,84% 35%,82% 69%,64% 88%,41% 84%,22% 63%,10% 34%);background:linear-gradient(135deg, rgba(62,103,163,.22), rgba(20,40,78,.35));"></div><div style="position:absolute;right:33%;top:22%;color:#fff;font-weight:800">محله مرکزی</div><div style="position:absolute;right:20%;top:46%;color:#fff;font-weight:800">محله آزادی</div><div style="position:absolute;right:52%;top:50%;color:#fff;font-weight:800">محله مدارس</div><div style="position:absolute;right:28%;top:68%;color:#fff;font-weight:800">محله کردستان</div><div style="position:absolute;right:46%;top:68%;color:#fff;font-weight:800">محله انقلاب</div><div style="position:absolute;left:18px;bottom:18px;background:#0a2141;border:1px solid #d6ac53;color:#f2cf7a;padding:8px 14px;border-radius:12px;font-weight:700">مشاهده نقشه کامل</div></div></body></html>''')
                return
            full_zones = []
            for zone in zones:
                full_zones.append({
                    "id": zone.get("id"),
                    "name": zone["name"],
                    "color": zone["color"],
                    "status": zone.get("status") or "ناقص",
                    "area_m2": zone.get("area_m2") or 0,
                    "boundary_points": zone.get("boundary_points", []),
                    "streets": self.db.get_streets(zone_id=zone["id"]),
                    "places": self.db.get_places(zone_id=zone["id"]),
                    "mosques": self.db.get_mosques(zone_id=zone["id"]),
                })
            mosques = []
            for mosque in self.db.get_mosques():
                item = dict(mosque)
                item["zones"] = [z["name"] for z in self.db.get_mosque_zone_names(mosque["id"])]
                mosques.append(item)
            html = build_all_zones_view_html(
                full_zones,
                boundary_points=boundary,
                offline=False,
                mosques=mosques,
                schools=self.db.get_schools(),
                health_centers=self.db.get_health_centers(),
            )
            path = os.path.join(get_data_dir(), "dashboard_map.html")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(html)
            self.map_view.setUrl(QUrl.fromLocalFile(path))
        except Exception as exc:
            self.map_view.setHtml(
                f"<html><body dir='rtl' style=\"font-family:Vazirmatn,'Segoe UI',Tahoma;padding:30px\">"
                f"<h3>نمایش نقشه موقتاً ممکن نیست</h3><p>{str(exc)}</p></body></html>"
            )

    def _fill_reports_table(self):
        try:
            documents = self.db.get_generated_documents(limit=5000)
        except Exception:
            documents = []

        # داشبورد مصوب 7.6 از کارت‌های خلاصه استفاده می‌کند و جدول قدیمی
        # reports_table در آن وجود ندارد. این شاخه برای سازگاری با پوسته‌های
        # قدیمی نگه داشته شده است و نباید در شروع برنامه خطا ایجاد کند.
        reports_table = getattr(self, "reports_table", None)
        if reports_table is not None:
            reports_table.setRowCount(len(documents))
            for row, item in enumerate(documents):
                values = [
                    f"GR-{int(item.get('id') or 0):06d}",
                    item.get("title") or item.get("template_name") or "گزارش بدون عنوان",
                    item.get("zone_name") or "—",
                    item.get("created_by_name") or "سامانه",
                    format_jalali(item.get("created_at") or ""),
                    "ثبت‌شده",
                ]
                for col, value in enumerate(values):
                    cell = QTableWidgetItem(convert_dates_in_text(str(value)))
                    cell.setTextAlignment(Qt.AlignCenter)
                    if col == 5:
                        cell.setForeground(QColor("#23815a"))
                    reports_table.setItem(row, col, cell)
            if not documents:
                reports_table.setRowCount(1)
                cell = QTableWidgetItem("هنوز گزارشی ثبت نشده است")
                cell.setTextAlignment(Qt.AlignCenter)
                reports_table.setItem(0, 1, cell)
            return

        value_labels = getattr(self, "report_summary_value_labels", [])
        if not value_labels:
            return

        keyword_groups = (
            ("مالی", "بودجه", "درآمد", "هزینه", "قرارداد"),
            ("عمرانی", "پروژه", "ساخت", "زیرساخت", "آبادانی"),
            ("خدمات شهری", "خدمات", "پسماند", "نظافت", "فضای سبز"),
            ("جمعیت", "جمعیتی", "ساکن", "خانوار", "نفوس"),
        )
        counts = [0] * len(keyword_groups)
        for item in documents:
            searchable = " ".join(str(item.get(key) or "") for key in ("title", "template_name", "related_entity_type"))
            for index, keywords in enumerate(keyword_groups):
                if any(keyword in searchable for keyword in keywords):
                    counts[index] += 1
                    break
        for label, count in zip(value_labels, counts):
            label.setText(_fa_number(count))

    def _update_block_status(self, stats):
        total = max(0, int(stats.get("zones_count", 0) or 0))
        needs_streets = max(0, int(stats.get("zones_without_streets", 0) or 0))
        needs_meeting = max(0, int(stats.get("zones_without_meeting_place", 0) or 0))
        review = min(total, needs_meeting)
        follow = min(max(total - review, 0), needs_streets)
        active = max(total - review - follow, 0)
        inactive = 0
        values = [active, review, follow, inactive]
        self.donut_chart.set_values(values)
        for label, value in zip(self.status_legend_labels, values):
            percent = round((value / total) * 100) if total else 0
            label.setText(f"{_fa_number(value)} ({_fa_number(percent)}٪)")

    def refresh_stats(self):
        try:
            stats = self.db.get_system_stats()
        except Exception:
            stats = {}

        for key, card in self.metric_cards.items():
            card.set_value(stats.get(key, 0))

        self._clear_layout(self.activity_layout)
        activities = []
        try:
            for action in self.db.get_neighborhood_actions()[:3]:
                status = action.get("status") or "ثبت‌شده"
                severity = "success" if status in ("تکمیل‌شده", "انجام‌شده") else (
                    "warning" if status == "در حال اجرا" else "normal"
                )
                activities.append((
                    action.get("title") or "اقدام اجرایی جدید",
                    action.get("responsible_office") or action.get("responsible_person") or status,
                    "check",
                    severity,
                ))
        except Exception:
            pass
        try:
            user_id = self.current_user.get("id")
            for item in self.db.get_in_app_notifications(user_id=user_id, limit=3):
                severity = "critical" if item.get("severity") in ("بحرانی", "فوری") else (
                    "warning" if item.get("severity") == "مهم" else "normal"
                )
                activities.append((
                    item.get("title") or "اعلان جدید",
                    format_jalali(item.get("due_date") or item.get("created_at") or ""),
                    "warning",
                    severity,
                ))
        except Exception:
            pass
        if not activities:
            activities.append(("فعالیت جدیدی ثبت نشده است", "سامانه آماده دریافت اطلاعات است", "info", "normal"))
        for title, subtitle, icon_name, severity in activities[:5]:
            self.activity_layout.addWidget(self._activity_item(title, subtitle, icon_name, severity))
        self.activity_layout.addStretch(1)

        self._fill_reports_table()
        self._update_block_status(stats)
        self.footer_update_label.setText("آخرین بروزرسانی: " + now_jalali())
        try:
            health = self.db.database_health()
            backup = self.db.backup_health_status()
            db_text = "پایگاه داده سالم" if health.get("integrity_ok") and not health.get("foreign_key_errors") else "نیازمند بررسی دیتابیس"
            backup_text = "بکاپ به‌روز" if backup.get("healthy") else "بکاپ نیازمند بررسی"
            self.footer_status.setText(f"{db_text} — {backup_text}")
            self.footer_status.setToolTip(backup.get("path") or "")
        except Exception:
            self.footer_status.setText("وضعیت سامانه در دسترس نیست")
        self.refresh_map()

    def show_quick_start(self):
        lines = [
            "۱) محدوده شهر و بلوک‌ها را ثبت کنید.",
            "۲) اعضای شورای هر بلوک و شماره‌های تماس را تکمیل کنید.",
            "۳) مسائل، درخواست‌ها و اقدامات اجرایی را ثبت و پیگیری کنید.",
            "۴) قبل از ارسال گروهی، پیش‌نمایش پیام را کنترل کنید.",
            "۵) از بخش تنظیمات، سلامت بکاپ و آزمون بازیابی را بررسی کنید.",
            "۶) گزارش‌های رسمی را از ماژول گزارش‌گیری تولید کنید.",
        ]
        QMessageBox.information(self, "راهنمای شروع سریع", "\n".join(lines))

    def open_global_search(self):
        if not has_permission(self.current_user.get("role"), "global_search"):
            return
        dialog = GlobalSearchDialog(self.db, self, initial_query="")
        dialog.result_activated.connect(self.search_result_activated.emit)
        dialog.exec_()
