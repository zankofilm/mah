# -*- coding: utf-8 -*-
"""
تم بصری رسمی/اداری برنامه با طراحی تخت، فاصله‌گذاری منظم و رنگ‌بندی
سرمه‌ای/طلایی. این ماژول یک استایل‌شیت واحد (QSS) برای کل برنامه فراهم می‌کند.
"""

# پالت رنگ رسمی
COLOR_NAVY_DARK = "#0b1f3a"      # سرمه‌ای تیره (پس‌زمینه هدر)
COLOR_NAVY = "#13294b"           # سرمه‌ای اصلی
COLOR_NAVY_LIGHT = "#1f3a63"     # سرمه‌ای روشن‌تر (هاور)
COLOR_GOLD = "#c9a227"           # طلایی رسمی (تاکید/خط جداکننده)
COLOR_GOLD_LIGHT = "#e0c34f"     # طلایی روشن‌تر (هاور دکمه‌ها)
COLOR_BG = "#f4f5f7"             # پس‌زمینه کلی روشن
COLOR_CARD_BG = "#ffffff"        # پس‌زمینه کارت‌ها/پنل‌ها
COLOR_TEXT_DARK = "#1c2530"      # رنگ متن اصلی
COLOR_TEXT_MUTED = "#5b6472"     # رنگ متن کم‌رنگ‌تر
COLOR_BORDER = "#d7dbe3"         # رنگ حاشیه‌ها
COLOR_DANGER = "#a4262c"         # قرمز رسمی (حذف/خطا)
COLOR_SUCCESS = "#256029"        # سبز رسمی (تأیید/موفقیت)
COLOR_PANEL_TOP = "#ffffff"      # گرادیان بالای کارت
COLOR_PANEL_BOTTOM = "#e9edf3"   # گرادیان پایین کارت
COLOR_SCROLL_TRACK = "#d9dee7"   # ترک اسکرول
COLOR_SCROLL_HANDLE = "#7d90ab"  # دسته اسکرول
COLOR_SCROLL_HANDLE_HOVER = "#5f7594"

FONT_FAMILY = "Vazirmatn, Estedad, Peyda, Dana, IRANSansX, Segoe UI, Tahoma, sans-serif"

MAIN_STYLESHEET = f"""
QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT_DARK};
    font-size: 13px;
}}

QMainWindow {{
    background-color: {COLOR_BG};
}}

/* ---------------- هدر رسمی محیط نرم‌افزار ---------------- */
#OfficialHeader, QFrame#SoftwareHeader {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #071e49, stop:0.52 #0b3978, stop:1 #082658);
    border: none;
    border-bottom: 3px solid {COLOR_GOLD};
}}
/*
تمام فرزندان متنی هدر باید شفاف باشند. قانون عمومی QWidget در macOS/Windows
در غیر این صورت برای QLabelها پس‌زمینه روشن می‌سازد و متن سفید را پنهان می‌کند.
*/
QFrame#SoftwareHeader QLabel,
QFrame#SoftwareHeader QAbstractButton,
#OfficialHeader QLabel,
#OfficialHeader QAbstractButton {{
    background-color: transparent;
    background: transparent;
    border: none;
}}
QFrame#SoftwareHeader > QFrame#HeaderCenterBox {{
    background-color: transparent;
    background: transparent;
    border: none;
}}
#OfficialHeaderOrgBox, #OfficialHeaderUserBox, QFrame#HeaderOrgBox, QFrame#HeaderUserBox {{
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.16);
    border-radius: 12px;
}}
#HeaderTitleMain {{
    color: white;
    font-size: 22px;
    font-weight: 900;
}}
#HeaderTitleSub {{
    color: #e6efff;
    font-size: 13px;
    font-weight: 700;
}}
#HeaderBottomLine {{
    color: #bcd1f0;
    font-size: 11px;
}}
#HeaderTitleOrg {{
    color: #eff5ff;
    font-size: 10px;
    font-weight: 600;
}}
#HeaderTitleSubOrg {{
    color: white;
    font-size: 12px;
    font-weight: 800;
}}
#HeaderUserName {{ color: white; font-size: 12px; font-weight: 800; }}
#HeaderUserRole {{ color: #cbdcf5; font-size: 10px; }}
#HeaderOnlineStatus {{ color: #7de39c; font-size: 10px; font-weight: 700; }}


QFrame#HeaderCenterBox {{ background: transparent; border: none; }}
QLabel#HeaderAvatar {{ background: rgba(255,255,255,0.12); border-radius: 29px; }}
QLabel#SoftwareHeaderTitle {{ color: white; font-size: 24px; font-weight: 900; }}
QLabel#SoftwareHeaderSubtitle {{ color: #d9e7ff; font-size: 12px; font-weight: 600; }}
QLabel#HeaderOrgSmall {{ color: #eff5ff; font-size: 11px; font-weight: 600; }}
QLabel#HeaderOrgMain {{ color: white; font-size: 13px; font-weight: 800; }}
QLabel#HeaderUserDate {{ color: #9fc0f2; font-size: 10px; }}
QFrame#HeaderGoldLine {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 transparent, stop:0.2 #d4ad55, stop:0.8 #d4ad55, stop:1 transparent);
    border: none;
}}
QToolButton[headerTool="true"] {{
    color: white; background: transparent; border: 1px solid transparent;
    border-radius: 12px; padding: 6px; font-weight: 700;
}}
QToolButton[headerTool="true"]:hover {{
    background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.22);
}}


/* محافظ نهایی هدر مشترک در تمام پنجره‌ها */
QFrame#SoftwareHeader QLabel#HeaderUserName,
QFrame#SoftwareHeader QLabel#HeaderUserRole,
QFrame#SoftwareHeader QLabel#HeaderUserDate,
QFrame#SoftwareHeader QLabel#SoftwareHeaderTitle,
QFrame#SoftwareHeader QLabel#SoftwareHeaderSubtitle,
QFrame#SoftwareHeader QLabel#HeaderOrgSmall,
QFrame#SoftwareHeader QLabel#HeaderOrgMain,
QFrame#SoftwareHeader QLabel#HeaderAvatar {{
    background: transparent;
    background-color: transparent;
    border: none;
}}
QFrame#SoftwareHeader QLabel#HeaderAvatar {{
    background: rgba(255,255,255,0.12);
    border-radius: 29px;
}}

/* ---------------- تب‌ها ---------------- */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    background: {COLOR_CARD_BG};
    border-radius: 8px;
    top: -1px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: #f3f6fa;
    color: #44546a;
    min-height: 25px;
    padding: 10px 16px;
    margin: 0 1px;
    border: 1px solid #e0e6ee;
    border-bottom: 2px solid transparent;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    font-weight: 650;
}}
QTabBar::tab:selected {{
    background: #ffffff;
    color: {COLOR_NAVY};
    border-color: #d6dee8;
    border-bottom: 3px solid {COLOR_GOLD};
}}
QTabBar::tab:hover:!selected {{
    background: #eaf0f7;
    color: {COLOR_NAVY};
}}
QTabBar::close-button {{
    subcontrol-position: left;
}}

/* ---------------- دکمه‌ها ---------------- */
QPushButton, QToolButton {{
    min-height: 34px;
    background: #ffffff;
    color: {COLOR_NAVY};
    border: 1px solid #c8d3df;
    border-radius: 8px;
    padding: 7px 13px;
    font-weight: 650;
}}
QPushButton:hover, QToolButton:hover {{
    background: #f5f8fb;
    border-color: #91a5bd;
}}
QPushButton:pressed, QToolButton:pressed {{
    background: #e9eff6;
    border-color: #7188a4;
}}
QPushButton:focus, QToolButton:focus {{
    border: 1px solid {COLOR_GOLD};
}}
QPushButton:disabled, QToolButton:disabled {{
    background: #f0f2f5;
    color: #9aa4b1;
    border-color: #dce2e8;
}}
QPushButton[compact="true"], QToolButton[compact="true"] {{
    min-height: 28px;
    padding: 4px 9px;
}}
QPushButton[uiRole="primary"], QToolButton[uiRole="primary"] {{
    background: {COLOR_NAVY};
    color: white;
    border: 1px solid {COLOR_NAVY};
}}
QPushButton[uiRole="primary"]:hover, QToolButton[uiRole="primary"]:hover {{
    background: {COLOR_NAVY_LIGHT};
    border-color: {COLOR_NAVY_LIGHT};
}}
QPushButton[uiRole="success"], QToolButton[uiRole="success"] {{
    background: #2f7a4d;
    color: white;
    border: 1px solid #2f7a4d;
}}
QPushButton[uiRole="success"]:hover, QToolButton[uiRole="success"]:hover {{
    background: #276a42;
    border-color: #276a42;
}}
QPushButton[uiRole="danger"], QToolButton[uiRole="danger"] {{
    background: #c9434d;
    color: white;
    border: 1px solid #c9434d;
}}
QPushButton[uiRole="danger"]:hover, QToolButton[uiRole="danger"]:hover {{
    background: #b63842;
    border-color: #b63842;
}}
QPushButton[uiRole="ghost"], QToolButton[uiRole="ghost"] {{
    background: transparent;
    color: {COLOR_NAVY};
    border: 1px solid transparent;
}}
QPushButton[uiRole="ghost"]:hover, QToolButton[uiRole="ghost"]:hover {{
    background: #e9eef5;
    border-color: #d5dde8;
}}
QPushButton[danger="true"] {{
    background: #c9434d;
    color: white;
}}
QPushButton[success="true"] {{
    background: #2f7a4d;
    color: white;
}}

/* ---------------- جزئیات تعاملی ---------------- */
QToolTip {{
    background-color: {COLOR_NAVY_DARK};
    color: white;
    border: 1px solid {COLOR_GOLD};
    border-radius: 5px;
    padding: 6px 9px;
}}
QMenu {{
    background: white;
    border: 1px solid {COLOR_BORDER};
    border-radius: 7px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 28px 7px 12px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: #eaf0f7;
    color: {COLOR_NAVY_DARK};
}}
QSplitter::handle {{
    background: #dfe5ec;
    width: 4px;
    height: 4px;
}}
QSplitter::handle:hover {{
    background: {COLOR_GOLD};
}}

/* ---------------- ورودی‌ها ---------------- */
QLineEdit, QComboBox, QSpinBox, QTextEdit {{
    background-color: white;
    border: 1px solid {COLOR_BORDER};
    border-radius: 5px;
    padding: 6px 8px;
    selection-background-color: {COLOR_GOLD_LIGHT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {COLOR_NAVY};
}}

QRadioButton, QCheckBox {{
    spacing: 6px;
}}

/* ---------------- جدول‌ها ---------------- */
QTableWidget {{
    background-color: white;
    alternate-background-color: #f0f2f6;
    gridline-color: {COLOR_BORDER};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}
QHeaderView::section {{
    background-color: {COLOR_NAVY};
    color: white;
    padding: 7px;
    border: none;
    font-weight: 600;
}}
QTableWidget::item:selected {{
    background-color: {COLOR_GOLD_LIGHT};
    color: {COLOR_TEXT_DARK};
}}

/* ---------------- لیست ---------------- */
QListWidget {{
    background-color: white;
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
}}
QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid #eef0f3;
}}
QListWidget::item:selected {{
    background-color: {COLOR_NAVY};
    color: white;
}}

/* ---------------- گروه‌باکس ---------------- */
QGroupBox {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    margin-top: 14px;
    font-weight: bold;
    padding-top: 10px;
    background: #ffffff;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    right: 12px;
    padding: 0 6px;
    color: {COLOR_NAVY};
}}

/* ---------------- نوار پیشرفت ---------------- */
QProgressBar {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    text-align: center;
    background: white;
}}
QProgressBar::chunk {{
    background-color: {COLOR_GOLD};
    border-radius: 5px;
}}


/* ---------------- اسکرول‌بار حرفه‌ای ---------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 16px;
    margin: 18px 3px 18px 3px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #93a4bc, stop:0.5 {COLOR_SCROLL_HANDLE}, stop:1 #4c6280);
    min-height: 34px;
    border-radius: 7px;
    border: 1px solid #e9edf4;
}}
QScrollBar::handle:vertical:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a6b5c9, stop:0.5 {COLOR_SCROLL_HANDLE_HOVER}, stop:1 #425872);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fdfefe, stop:1 #d7dee8);
    height: 15px;
    border-radius: 7px;
    border: 1px solid #bcc8d7;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: rgba(217, 222, 231, 0.55);
    border-radius: 7px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 16px;
    margin: 3px 18px 3px 18px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #93a4bc, stop:0.5 {COLOR_SCROLL_HANDLE}, stop:1 #4c6280);
    min-width: 34px;
    border-radius: 7px;
    border: 1px solid #e9edf4;
}}
QScrollBar::handle:horizontal:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #a6b5c9, stop:0.5 {COLOR_SCROLL_HANDLE_HOVER}, stop:1 #425872);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fdfefe, stop:1 #d7dee8);
    width: 15px;
    border-radius: 7px;
    border: 1px solid #bcc8d7;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: rgba(217, 222, 231, 0.55);
    border-radius: 7px;
}}
QAbstractScrollArea {{
    border-radius: 8px;
}}
QScrollArea#PageScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea#PageScrollArea QWidget#qt_scrollarea_viewport {{
    background: transparent;
}}

/* ---------------- نوار وضعیت ---------------- */
QStatusBar {{
    background-color: {COLOR_NAVY_DARK};
    color: white;
}}
"""


# پرداخت نهایی نسخه حرفه‌ای: رابط تخت، فاصله‌گذاری منظم و تایپوگرافی مبتنی بر QApplication
MAIN_STYLESHEET += f"""
/* ---------------- پرداخت حرفه‌ای سراسری ---------------- */
QWidget {{
    color: #182235;
}}

QPushButton, QToolButton {{
    min-height: 36px;
    background: #ffffff;
    color: #17345f;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 6px 13px;
    font-weight: 600;
}}
QPushButton:hover, QToolButton:hover {{
    background: #f5f8fc;
    border-color: #8ba2bf;
}}
QPushButton:pressed, QToolButton:pressed {{
    background: #e9eff7;
    border-color: #6d87a8;
    padding: 6px 13px;
}}
QPushButton:focus, QToolButton:focus {{
    border: 1px solid #315f9f;
}}
QPushButton[compact="true"], QToolButton[compact="true"] {{
    min-height: 30px;
    padding: 4px 9px;
    border-radius: 7px;
}}
QPushButton[uiRole="primary"], QToolButton[uiRole="primary"] {{
    background: #123b73;
    color: #ffffff;
    border-color: #123b73;
}}
QPushButton[uiRole="primary"]:hover, QToolButton[uiRole="primary"]:hover {{
    background: #194b8a;
    border-color: #194b8a;
}}
QPushButton[uiRole="success"], QToolButton[uiRole="success"] {{
    background: #237346;
    color: #ffffff;
    border-color: #237346;
}}
QPushButton[uiRole="success"]:hover, QToolButton[uiRole="success"]:hover {{
    background: #2a8652;
    border-color: #2a8652;
}}
QPushButton[uiRole="danger"], QToolButton[uiRole="danger"] {{
    background: #a9323a;
    color: #ffffff;
    border-color: #a9323a;
}}
QPushButton[uiRole="danger"]:hover, QToolButton[uiRole="danger"]:hover {{
    background: #bd3a43;
    border-color: #bd3a43;
}}
QPushButton[uiRole="ghost"], QToolButton[uiRole="ghost"] {{
    background: transparent;
    color: #17345f;
    border-color: transparent;
}}
QPushButton[uiRole="ghost"]:hover, QToolButton[uiRole="ghost"]:hover {{
    background: #edf3fa;
    border-color: #d7e1ed;
}}

QLineEdit, QComboBox, QSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {{
    min-height: 34px;
    background: #ffffff;
    color: #182235;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 5px 9px;
    selection-background-color: #c8d9ef;
}}
QTextEdit, QPlainTextEdit {{
    padding: 8px 10px;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDateEdit:hover,
QTextEdit:hover, QPlainTextEdit:hover {{
    border-color: #9aadc4;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus,
QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid #315f9f;
    background: #ffffff;
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox QAbstractItemView {{
    background: #ffffff;
    border: 1px solid #cbd5e1;
    selection-background-color: #e6eef8;
    selection-color: #17345f;
    outline: none;
    padding: 4px;
}}

QTabWidget::pane {{
    background: #ffffff;
    border: 1px solid #d9e1eb;
    border-radius: 10px;
    top: -1px;
}}
QTabBar::tab {{
    min-height: 38px;
    background: transparent;
    color: #5c6b7d;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 8px 16px;
    margin: 0 2px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: #ffffff;
    color: #123b73;
    border-bottom: 3px solid #c99b39;
}}
QTabBar::tab:hover:!selected {{
    background: #f1f5fa;
    color: #17345f;
}}

QTableView, QTableWidget {{
    background: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #d9e1eb;
    border-radius: 9px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: #dce9f8;
    selection-color: #13294b;
}}
QTableView::item, QTableWidget::item {{
    padding: 7px 9px;
    border-bottom: 1px solid #edf1f5;
}}
QTableView::item:hover, QTableWidget::item:hover {{
    background: #eef4fb;
}}
QHeaderView::section {{
    min-height: 38px;
    background: #17345f;
    color: #ffffff;
    border: none;
    border-left: 1px solid #294a76;
    padding: 7px 9px;
    font-weight: 600;
}}

QGroupBox {{
    background: #ffffff;
    border: 1px solid #d9e1eb;
    border-radius: 11px;
    margin-top: 16px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top right;
    right: 14px;
    padding: 0 8px;
    color: #17345f;
    background: #ffffff;
}}

QLabel[sectionTitle="true"] {{
    color: #13294b;
    font-size: 15px;
    font-weight: 700;
}}
QLabel[muted="true"] {{
    color: #6d7887;
}}
QFormLayout QLabel {{
    color: #344258;
}}
"""


LOGIN_STYLESHEET = f"""
QWidget#LoginRoot {{
    background-color: {COLOR_NAVY_DARK};
}}
QFrame#LoginCard {{
    background-color: {COLOR_CARD_BG};
    border-radius: 14px;
    border-top: 4px solid {COLOR_GOLD};
}}
QLabel#LoginTitle {{
    color: {COLOR_NAVY_DARK};
    font-size: 18px;
    font-weight: bold;
}}
QLabel#LoginSubtitle {{
    color: {COLOR_TEXT_MUTED};
    font-size: 12px;
}}
QLabel#LoginOrgLine {{
    color: #aab4c4;
    font-size: 12px;
}}
QLabel#LoginOrgMain {{
    color: {COLOR_GOLD};
    font-size: 22px;
    font-weight: bold;
}}
QLineEdit#LoginInput {{
    background-color: #f4f5f7;
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 13px;
}}
QLineEdit#LoginInput:focus {{
    border: 1px solid {COLOR_NAVY};
}}
QPushButton#LoginButton {{
    background-color: {COLOR_NAVY};
    color: white;
    border-radius: 8px;
    padding: 10px;
    font-weight: bold;
    font-size: 14px;
}}
QPushButton#LoginButton:hover {{
    background-color: {COLOR_GOLD};
    color: {COLOR_NAVY_DARK};
}}
QLabel#LoginError {{
    color: #ff6b6b;
    font-size: 12px;
}}
"""


DASHBOARD_STYLESHEET = f"""
QWidget#DashboardRoot {{
    background: #eef3f8;
    color: #17243a;
    font-size: 12px;
}}
QWidget#DashboardContent {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f5f8fc, stop:1 #edf2f7);
}}
QScrollArea#DashboardScroll,
QScrollArea#DashboardScroll QWidget#qt_scrollarea_viewport {{
    background: transparent;
    border: none;
}}
QWidget#DashboardRoot QLabel {{
    background: transparent;
    border: none;
}}

/* هدر اصلی */
QFrame#SoftwareHeader {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #06182f, stop:0.46 #0c3367, stop:1 #08244a);
    border: none;
    border-bottom: 3px solid #c49a3a;
}}
QFrame#SoftwareHeader QLabel,
QFrame#SoftwareHeader QAbstractButton {{
    background: transparent;
    background-color: transparent;
    border: none;
}}
QFrame#HeaderCenterBox {{ background: transparent; border: none; }}
QFrame#HeaderUserBox, QFrame#HeaderOrgBox {{
    background: rgba(255,255,255,0.075);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 15px;
}}
QLabel#HeaderAvatar {{
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 29px;
}}
QLabel#HeaderUserName {{ color: white; font-size: 14px; font-weight: 800; }}
QLabel#HeaderUserRole {{ color: #d6e4f8; font-size: 11px; }}
QLabel#HeaderUserDate {{ color: #a9c4e9; font-size: 10px; }}
QLabel#SoftwareHeaderTitle {{ color: white; font-size: 24px; font-weight: 900; }}
QLabel#SoftwareHeaderSubtitle {{ color: #d7e5f8; font-size: 12px; font-weight: 600; }}
QLabel#HeaderOrgSmall {{ color: #eaf2ff; font-size: 11px; font-weight: 600; }}
QLabel#HeaderOrgMain {{ color: white; font-size: 13px; font-weight: 800; }}
QFrame#HeaderGoldLine {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 transparent, stop:0.18 #d7b55f, stop:0.82 #d7b55f, stop:1 transparent);
    border: none;
}}
QToolButton[headerTool="true"] {{
    color: white;
    background: rgba(255,255,255,0.025);
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 7px;
    font-weight: 700;
}}
QToolButton[headerTool="true"]:hover {{
    background: rgba(255,255,255,0.12);
    border-color: rgba(255,255,255,0.22);
}}

/* نوار ماژول‌ها */
QFrame#DashboardNavBar {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f8fbff, stop:1 #eef4fb);
    border: none;
    border-bottom: 1px solid #d6e0eb;
}}
QScrollArea#DashboardNavScroll,
QScrollArea#DashboardNavScroll QWidget#qt_scrollarea_viewport,
QWidget#DashboardNavHost {{
    background: transparent;
    border: none;
}}
QToolButton[dashboardNav="true"] {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #f3f7fc);
    color: #16365f;
    border: 1px solid #d9e4ef;
    border-radius: 16px;
    padding: 9px 8px 8px 8px;
    font-size: 10.5px;
    font-weight: 800;
    text-align: center;
}}
QToolButton[dashboardNav="true"]:hover {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:1 #eaf2fb);
    border-color: #a7bfdc;
    color: #0d315f;
}}
QToolButton[dashboardNav="true"][active="true"] {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1b4f90, stop:0.82 #143c6f, stop:1 #102f58);
    color: #ffffff;
    border: 1px solid #c49a3a;
}}
QToolButton[dashboardNav="true"]:disabled {{
    background: #f4f7fa;
    color: #a2adba;
    border-color: #e8eef4;
}}

/* معرفی داشبورد */
QFrame#DashboardWelcome {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ffffff, stop:1 #eef5ff);
    border: 1px solid #d8e4f1;
    border-radius: 16px;
}}
QLabel#WelcomeTitle {{ color: #0d2f5b; font-size: 18px; font-weight: 900; }}
QLabel#WelcomeSubtitle {{ color: #66758a; font-size: 11px; font-weight: 550; }}
QLineEdit#DashboardSearch {{
    min-height: 38px;
    background: #ffffff;
    color: #1d2e45;
    border: 1px solid #c8d6e5;
    border-radius: 10px;
    padding: 5px 12px;
}}
QLineEdit#DashboardSearch:focus {{ border: 1px solid #2a67ab; }}
QPushButton#WelcomeRefresh {{
    min-height: 38px;
    background: #123b73;
    color: white;
    border: 1px solid #123b73;
    border-radius: 10px;
    padding: 5px 15px;
    font-weight: 750;
}}
QPushButton#WelcomeRefresh:hover {{ background: #194e8f; border-color: #194e8f; }}

/* شاخص‌های کلیدی */
QFrame#MetricCard {{
    background: #ffffff;
    border: 1px solid #dfe7f0;
    border-radius: 16px;
}}
QFrame#MetricAccent {{ border: none; }}
QFrame#MetricAccent[accent="blue"] {{ background: #2878d4; }}
QFrame#MetricAccent[accent="green"] {{ background: #2c9a63; }}
QFrame#MetricAccent[accent="orange"] {{ background: #e8952d; }}
QFrame#MetricAccent[accent="purple"] {{ background: #7655c9; }}
QLabel#MetricTitle {{ color: #4f6076; font-size: 12px; font-weight: 700; }}
QLabel#MetricValue {{ color: #0c2c56; font-size: 30px; font-weight: 900; }}
QLabel#MetricChange {{ color: #8491a2; font-size: 9px; }}
QFrame#MetricIcon {{ border-radius: 31px; border: none; }}
QFrame#MetricIcon[accent="blue"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3b8ce6, stop:1 #1e66bd); }}
QFrame#MetricIcon[accent="green"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #45ae77, stop:1 #23815a); }}
QFrame#MetricIcon[accent="orange"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #f1ad4f, stop:1 #d88018); }}
QFrame#MetricIcon[accent="purple"] {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #8e70d9, stop:1 #6444b4); }}

/* پنل‌ها */
QFrame#DashboardPanel {{
    background: #ffffff;
    border: 1px solid #dfe7f0;
    border-radius: 16px;
}}
QFrame#PanelIcon {{
    background: #edf4fc;
    border: 1px solid #d9e6f4;
    border-radius: 10px;
}}
QFrame#PanelDivider {{ background: #edf1f5; border: none; }}
QLabel#PanelTitle {{ color: #12345f; font-size: 14px; font-weight: 850; }}

QFrame#MiniStat {{
    background: #f7faff;
    border: 1px solid #e1e9f3;
    border-radius: 12px;
}}
QFrame#MiniStat:hover {{ background: #eef5fd; border-color: #c6d8ec; }}
QLabel#MiniStatValue {{ color: #113b6e; font-size: 20px; font-weight: 900; }}
QLabel#MiniStatTitle {{ color: #6f7d90; font-size: 9px; font-weight: 600; }}

QFrame#DashboardListItem, QFrame#ProjectListItem {{
    background: #fbfcfe;
    border: 1px solid #e5ebf2;
    border-radius: 11px;
}}
QFrame#DashboardListItem:hover, QFrame#ProjectListItem:hover {{
    background: #f1f6fd;
    border-color: #b9cde5;
}}
QLabel#ListTitle {{ color: #20334e; font-weight: 750; font-size: 11px; }}
QLabel#ListSubtitle {{ color: #7c8999; font-size: 9px; }}
QLabel#ListDot {{ color: #357dc5; }}
QLabel#ListDot[severity="success"] {{ color: #23815a; }}
QLabel#ListDot[severity="warning"] {{ color: #d7861d; }}
QLabel#ListDot[severity="critical"] {{ color: #c43d4b; }}
QLabel#StatusBadge {{
    padding: 3px 9px;
    border-radius: 9px;
    background: #e7f1ff;
    color: #2367b1;
    font-size: 9px;
    font-weight: 700;
}}
QLabel#StatusBadge[severity="success"] {{ background: #e6f5ed; color: #237a54; }}
QLabel#StatusBadge[severity="warning"] {{ background: #fff1dc; color: #a9630b; }}
QLabel#StatusBadge[severity="critical"] {{ background: #fde8ea; color: #ae303c; }}
QLabel#ProjectPercent {{ color: #1765b6; font-weight: 850; }}

QPushButton[panelLink="true"] {{
    min-height: 29px;
    background: #f4f8fd;
    color: #1b65ad;
    border: 1px solid #e1eaf4;
    border-radius: 8px;
    text-align: right;
    padding: 4px 10px;
    font-weight: 700;
}}
QPushButton[panelLink="true"]:hover {{
    background: #eaf2fb;
    color: #0c4d8d;
    border-color: #bed2e9;
}}

QLabel#SystemHealthy {{
    color: #207548;
    background: #e8f6ee;
    border: 1px solid #cde9d9;
    border-radius: 10px;
    padding: 9px;
    font-size: 12px;
    font-weight: 800;
}}
QLabel#SystemUpdate {{ color: #6e7b8d; font-size: 10px; }}
QFrame#VersionCard {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #123b73, stop:1 #071d3d);
    border: 1px solid #193f70;
    border-radius: 16px;
    min-height: 105px;
}}
QLabel#VersionTitle {{ color: #cbdcf1; font-size: 11px; }}
QLabel#VersionValue {{ color: white; font-size: 24px; font-weight: 900; }}
QLabel#FooterStatus {{ color: #23815a; font-weight: 750; }}

QSplitter#DashboardSplitter::handle {{ background: transparent; width: 10px; }}
QProgressBar {{ border: none; background: #e4eaf1; border-radius: 4px; }}
QProgressBar::chunk {{ background: #2d9363; border-radius: 4px; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 3px; }}
QScrollBar::handle:vertical {{ background: #9aa9bb; border-radius: 5px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: #6f8299; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 1px 4px; }}
QScrollBar::handle:horizontal {{ background: #a7b4c4; border-radius: 4px; min-width: 45px; }}
QScrollBar::handle:horizontal:hover {{ background: #788aa0; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QLabel#CouncilZoneNotice {{
    background: #eef5ff;
    color: #173a68;
    border: 1px solid #bfd1e5;
    border-radius: 9px;
    padding: 9px 12px;
    font-weight: 700;
}}
"""


# v7.3.1 - central responsive overrides.  These rules are intentionally appended
# after legacy module rules so point sizes and minimum controls remain readable
# on compact and high-density displays.
MAIN_STYLESHEET += """
QWidget[responsiveProfile="compact"] {
    font-size: 10pt;
}
QWidget[responsiveProfile="comfortable"] {
    font-size: 10.5pt;
}
QWidget[responsiveProfile="spacious"] {
    font-size: 11pt;
}
QWidget[responsiveProfile="compact"] QPushButton,
QWidget[responsiveProfile="compact"] QToolButton,
QWidget[responsiveProfile="compact"] QLineEdit,
QWidget[responsiveProfile="compact"] QComboBox,
QWidget[responsiveProfile="compact"] QSpinBox,
QWidget[responsiveProfile="compact"] QDateEdit {
    min-height: 34px;
    padding-top: 5px;
    padding-bottom: 5px;
}
QWidget[responsiveProfile="comfortable"] QPushButton,
QWidget[responsiveProfile="comfortable"] QToolButton,
QWidget[responsiveProfile="comfortable"] QLineEdit,
QWidget[responsiveProfile="comfortable"] QComboBox,
QWidget[responsiveProfile="comfortable"] QSpinBox,
QWidget[responsiveProfile="comfortable"] QDateEdit {
    min-height: 38px;
}
QWidget[responsiveProfile="spacious"] QPushButton,
QWidget[responsiveProfile="spacious"] QToolButton,
QWidget[responsiveProfile="spacious"] QLineEdit,
QWidget[responsiveProfile="spacious"] QComboBox,
QWidget[responsiveProfile="spacious"] QSpinBox,
QWidget[responsiveProfile="spacious"] QDateEdit {
    min-height: 42px;
}
QWidget[responsiveProfile="compact"] QTabBar::tab {
    min-height: 30px;
    padding: 7px 10px;
    font-size: 9.5pt;
}
QWidget[responsiveProfile="comfortable"] QTabBar::tab {
    min-height: 34px;
    padding: 8px 13px;
    font-size: 10pt;
}
QWidget[responsiveProfile="spacious"] QTabBar::tab {
    min-height: 38px;
    padding: 9px 16px;
    font-size: 10.5pt;
}
QWidget[responsiveProfile="compact"] QHeaderView::section,
QWidget[responsiveProfile="compact"] QTableView,
QWidget[responsiveProfile="compact"] QTreeView {
    font-size: 9.5pt;
}
QWidget[responsiveProfile="comfortable"] QHeaderView::section,
QWidget[responsiveProfile="comfortable"] QTableView,
QWidget[responsiveProfile="comfortable"] QTreeView {
    font-size: 10pt;
}
QWidget[responsiveProfile="spacious"] QHeaderView::section,
QWidget[responsiveProfile="spacious"] QTableView,
QWidget[responsiveProfile="spacious"] QTreeView {
    font-size: 10.5pt;
}
"""

DASHBOARD_STYLESHEET += """
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#WelcomeTitle {
    font-size: 15px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#WelcomeSubtitle {
    font-size: 10px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QToolButton[dashboardNav="true"] {
    font-size: 9.5px;
    padding: 6px 5px;
    border-radius: 13px;
}
QWidget#DashboardRoot[responsiveProfile="comfortable"] QToolButton[dashboardNav="true"] {
    font-size: 10.5px;
}
QWidget#DashboardRoot[responsiveProfile="spacious"] QToolButton[dashboardNav="true"] {
    font-size: 11.5px;
}
QFrame#MetricCard[compact="true"] QLabel#MetricValue {
    font-size: 25px;
}
QFrame#MetricCard[compact="true"] QLabel#MetricTitle {
    font-size: 11px;
}
QFrame#MetricCard[compact="true"] QLabel#MetricChange {
    font-size: 8px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#PanelTitle {
    font-size: 13px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#MiniStatValue {
    font-size: 18px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#MiniStatTitle {
    font-size: 9px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QPushButton[panelLink="true"] {
    min-height: 34px;
    font-size: 10px;
}
QWidget#DashboardRoot[responsiveProfile="spacious"] QLabel#PanelTitle {
    font-size: 15px;
}
QWidget#DashboardRoot[responsiveProfile="spacious"] QLabel#MetricValue {
    font-size: 34px;
}
"""

# نسخه 7.4.0 — بازطراحی کامل داشبورد مطابق طرح رسمی تأییدشده
DASHBOARD_STYLESHEET += """
QWidget#DashboardRoot {
    background: #eef3f8;
}
QWidget#DashboardShell,
QWidget#DashboardContent,
QScrollArea#DashboardScroll,
QScrollArea#DashboardScroll QWidget#qt_scrollarea_viewport {
    background: #eef3f8;
    border: none;
}

/* سایدبار رسمی تیره */
QFrame#DashboardSidebar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #092a59, stop:0.52 #08244a, stop:1 #06182f);
    border: none;
    border-right: 1px solid #c49a3a;
}
QLabel#SidebarTitle {
    color: #d9b15a;
    font-size: 12px;
    font-weight: 800;
    padding: 4px;
    background: transparent;
}
QToolButton[sidebarNav="true"] {
    background: rgba(255,255,255,0.025);
    color: #ffffff;
    border: 1px solid rgba(217,177,90,0.30);
    border-radius: 13px;
    padding: 10px 13px;
    font-size: 12px;
    font-weight: 800;
    text-align: right;
}
QToolButton[sidebarNav="true"]:hover {
    background: rgba(42,111,189,0.25);
    border-color: rgba(217,177,90,0.70);
}
QToolButton[sidebarNav="true"][active="true"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #174c8b, stop:1 #0f3768);
    color: #ffffff;
    border: 1px solid #d9b15a;
}
QToolButton[sidebarNav="true"]:disabled {
    color: rgba(255,255,255,0.36);
    border-color: rgba(255,255,255,0.08);
    background: rgba(255,255,255,0.01);
}
QToolButton#SidebarMore {
    background: rgba(255,255,255,0.03);
    color: #f2d17d;
    border: 1px dashed rgba(217,177,90,0.45);
    border-radius: 12px;
    min-height: 48px;
    padding: 8px 12px;
    font-weight: 800;
}
QToolButton#SidebarMore:hover {
    background: rgba(255,255,255,0.08);
    border-color: #d9b15a;
}
QMenu {
    background: #ffffff;
    color: #173a68;
    border: 1px solid #d9e3ee;
    border-radius: 10px;
    padding: 7px;
}
QMenu::item {
    min-height: 32px;
    padding: 6px 28px 6px 16px;
    border-radius: 7px;
}
QMenu::item:selected {
    background: #eaf2fb;
    color: #0c3367;
}
QFrame#SidebarIdentity {
    background: rgba(255,255,255,0.045);
    border: 1px solid rgba(217,177,90,0.38);
    border-radius: 14px;
}
QLabel#SidebarIdentityTitle {
    color: #ffffff;
    font-size: 12px;
    font-weight: 850;
    background: transparent;
}
QLabel#SidebarIdentityVersion {
    color: #a9c6e8;
    font-size: 9px;
    background: transparent;
}
QPushButton#SidebarLogout {
    background: #9f2f3b;
    color: #ffffff;
    border: 1px solid #c75b65;
    border-radius: 10px;
    min-height: 38px;
    font-weight: 800;
}
QPushButton#SidebarLogout:hover {
    background: #b73b48;
}

/* کارت‌های آماری */
QFrame#MetricCard {
    background: #ffffff;
    border: 1px solid #dbe4ee;
    border-radius: 15px;
}
QLabel#MetricTitle {
    color: #4e5f75;
    font-size: 11px;
    font-weight: 750;
}
QLabel#MetricValue {
    color: #0b2b55;
    font-size: 28px;
    font-weight: 900;
}
QLabel#MetricChange {
    color: #8a96a6;
    font-size: 9px;
}
QFrame#MetricIcon {
    border-radius: 29px;
    border: none;
}
QFrame#MetricIcon[accent="green"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #43bb79,stop:1 #218d5b);
}
QFrame#MetricIcon[accent="blue"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4b97ee,stop:1 #2269c3);
}
QFrame#MetricIcon[accent="orange"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #f5b34f,stop:1 #de861b);
}
QFrame#MetricIcon[accent="purple"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #9a7be8,stop:1 #6e4cc1);
}
QFrame#MetricIcon[accent="teal"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #42c7bc,stop:1 #169b92);
}

/* پنل‌های اصلی */
QFrame#DashboardPanel {
    background: #ffffff;
    border: 1px solid #dbe4ee;
    border-radius: 15px;
}
QFrame#PanelIcon {
    background: #edf4fc;
    border: 1px solid #d9e6f4;
    border-radius: 10px;
}
QLabel#PanelTitle {
    color: #12345f;
    font-size: 14px;
    font-weight: 850;
}
QFrame#PanelDivider {
    background: #edf1f5;
    border: none;
}
QPushButton#PanelAction {
    background: #eef5ff;
    color: #1f64ad;
    border: 1px solid #cdddf0;
    border-radius: 8px;
    min-height: 30px;
    padding: 3px 11px;
    font-size: 10px;
    font-weight: 750;
}
QPushButton#PanelAction:hover {
    background: #e1edfb;
    border-color: #9cb9da;
}
QFrame#MapLegend {
    background: #f8fbff;
    border: 1px solid #e0e8f1;
    border-radius: 10px;
    min-width: 128px;
    max-width: 160px;
}
QFrame#ActivityItem {
    background: #fbfdff;
    border: 1px solid #e5ebf2;
    border-radius: 10px;
}
QFrame#ActivityItem:hover {
    background: #f4f8fd;
    border-color: #cbd9e9;
}
QLabel#ActivityTitle {
    color: #24364c;
    font-size: 10px;
    font-weight: 750;
}
QLabel#ActivitySubtitle {
    color: #8793a2;
    font-size: 8.5px;
}
QFrame#ActivityIcon {
    background: #edf4fc;
    border: 1px solid #dbe8f5;
    border-radius: 10px;
}
QFrame#ActivityIcon[severity="success"] {
    background: #e8f8ef;
    border-color: #c5ead4;
}
QFrame#ActivityIcon[severity="warning"] {
    background: #fff5df;
    border-color: #f2ddac;
}
QFrame#ActivityIcon[severity="critical"] {
    background: #fdeced;
    border-color: #f1c6ca;
}
QTableWidget#RecentReportsTable {
    background: #ffffff;
    alternate-background-color: #f8fafc;
    color: #29394e;
    border: none;
    gridline-color: #e9eef4;
    selection-background-color: #eaf2fb;
    selection-color: #173a68;
    font-size: 9px;
}
QTableWidget#RecentReportsTable QHeaderView::section {
    background: #f2f6fb;
    color: #34475f;
    border: none;
    border-bottom: 1px solid #dbe4ee;
    padding: 7px;
    font-size: 9px;
    font-weight: 800;
}
QLabel#StatusLegendValue {
    color: #516176;
    font-size: 9px;
    font-weight: 750;
}

/* نوار پایانی */
QFrame#DashboardFooter {
    background: #071b3b;
    border: none;
    border-top: 1px solid #c49a3a;
    min-height: 34px;
}
QLabel#FooterRights,
QLabel#FooterStatus,
QLabel#FooterUpdate {
    color: #c8d8eb;
    background: transparent;
    font-size: 9px;
}
QLabel#FooterStatus {
    color: #8ed6ac;
    font-weight: 700;
}

QWidget#DashboardRoot[responsiveProfile="compact"] QToolButton[sidebarNav="true"] {
    padding: 8px;
    border-radius: 11px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#MetricValue {
    font-size: 24px;
}
QWidget#DashboardRoot[responsiveProfile="compact"] QLabel#PanelTitle {
    font-size: 12px;
}
"""


# نسخه 7.5.0 — اعمال تم حرفه‌ای تأییدشده در کل سورس
MAIN_STYLESHEET += """
/* ===== Global Premium Dark Theme ===== */
/* Font family is applied globally through QApplication.setFont().
   Avoid listing unavailable font aliases in QSS because Qt/macOS emits
   qt.qpa.fonts warnings and performs an expensive alias scan. */
QMainWindow, QDialog {
    background: #07172d;
}
QWidget[appSurface="true"],
QFrame, QGroupBox, QTabWidget::pane, QScrollArea, QAbstractScrollArea, QListView, QTreeView, QTableView, QTextEdit, QPlainTextEdit {
    background: #081b34;
    color: #eef4ff;
    border-color: #173a63;
}
QLabel {
    color: #eef4ff;
}
QGroupBox {
    border: 1px solid #12355f;
    border-radius: 14px;
    margin-top: 18px;
    padding: 16px 12px 12px 12px;
    background: #091e3a;
}
QGroupBox::title {
    color: #e8c36f;
    background: #091e3a;
    right: 14px;
    padding: 0 8px;
}
QTabBar::tab {
    background: #0a2141;
    color: #d9e7ff;
    border: 1px solid #173a63;
    border-bottom: 2px solid transparent;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    padding: 10px 16px;
    font-weight: 750;
}
QTabBar::tab:selected {
    background: #0e2c57;
    color: #ffffff;
    border-color: #235084;
    border-bottom: 2px solid #d8b15d;
}
QTabBar::tab:hover:!selected {
    background: #0d274d;
}
QPushButton, QToolButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #123968, stop:1 #0c2a52);
    color: #f4f8ff;
    border: 1px solid #235084;
    border-radius: 10px;
    padding: 7px 13px;
    font-weight: 750;
}
QPushButton:hover, QToolButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #18477f, stop:1 #12355f);
    border-color: #d5ab53;
}
QPushButton:pressed, QToolButton:pressed {
    background: #0b2547;
}
QPushButton[uiRole="primary"], QToolButton[uiRole="primary"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1a5fd0, stop:1 #1270ff);
    border: 1px solid #5aa1ff;
    color: white;
}
QPushButton[uiRole="success"], QToolButton[uiRole="success"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #17995a, stop:1 #1fbf6d);
    border: 1px solid #63d19d;
    color: white;
}
QPushButton[uiRole="danger"], QToolButton[uiRole="danger"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #942b3d, stop:1 #c64157);
    border: 1px solid #dd8090;
    color: white;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit, QDateTimeEdit, QTimeEdit {
    background: #07162d;
    color: #ffffff;
    border: 1px solid #1e4677;
    border-radius: 10px;
    padding: 8px 10px;
    selection-background-color: #1f70ff;
    selection-color: white;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus, QDateTimeEdit:focus, QTimeEdit:focus {
    border: 1px solid #d8b15d;
}
QComboBox QAbstractItemView {
    background: #081b34;
    color: #eef4ff;
    border: 1px solid #1e4677;
    selection-background-color: #123968;
}
QTableView, QTableWidget, QTreeView, QListView {
    background: #081b34;
    alternate-background-color: #0a2141;
    color: #eef4ff;
    border: 1px solid #173a63;
    border-radius: 12px;
    gridline-color: #12355f;
    selection-background-color: #0f3768;
    selection-color: #ffffff;
}
QHeaderView::section {
    min-height: 38px;
    background: #0c2a52;
    color: #f7e0a2;
    border: none;
    border-left: 1px solid #17416f;
    padding: 8px 10px;
    font-weight: 800;
}
QTableView::item, QTableWidget::item {
    padding: 8px 10px;
    border-bottom: 1px solid #0f2c53;
}
QMenu {
    background: #081b34;
    color: #eef4ff;
    border: 1px solid #1e4677;
}
QMenu::item:selected {
    background: #123968;
}
QStatusBar {
    background: #061426;
    color: #d5e3fa;
    border-top: 1px solid #173a63;
}
QScrollBar:vertical {
    background: transparent;
    width: 11px;
}
QScrollBar::handle:vertical {
    background: #1f4878;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #2b5d97;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
}
QScrollBar::handle:horizontal {
    background: #1f4878;
    border-radius: 5px;
    min-width: 45px;
}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
    border: none;
}
QLabel[sectionTitle="true"] {
    color: #f1cf7a;
    font-size: 15px;
    font-weight: 800;
}
QLabel[muted="true"] {
    color: #b7c7df;
}
"""

LOGIN_STYLESHEET += """
QWidget#LoginRoot {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #041123, stop:0.55 #081d39, stop:1 #0c2f57);
}
QFrame#LoginCard {
    background: rgba(7, 24, 47, 0.92);
    border: 1px solid #1c4676;
    border-top: 3px solid #d8b15d;
    border-radius: 18px;
}
QLabel#LoginTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 900;
}
QLabel#LoginSubtitle {
    color: #c9d8f0;
    font-size: 12px;
    font-weight: 600;
}
QLineEdit#LoginInput {
    background: #06162c;
    color: #ffffff;
    border: 1px solid #1e4677;
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 13px;
}
QLineEdit#LoginInput:focus {
    border: 1px solid #d8b15d;
}
QPushButton#LoginButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #155dd0, stop:1 #0e7bff);
    color: white;
    border: 1px solid #5aa1ff;
    border-radius: 12px;
    padding: 12px;
    font-weight: 800;
    font-size: 14px;
}
QPushButton#LoginButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1b69ea, stop:1 #2786ff);
}
QLabel#LoginError {
    color: #ff8894;
    font-size: 12px;
    font-weight: 700;
}
"""

DASHBOARD_STYLESHEET += """
/* ===== Approved Premium Dashboard Overrides ===== */
QWidget#DashboardRoot,
QWidget#DashboardShell,
QWidget#DashboardContent,
QScrollArea#DashboardScroll,
QScrollArea#DashboardScroll QWidget#qt_scrollarea_viewport {
    background: #07172d;
    color: #eef4ff;
}
QFrame#SoftwareHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #051225, stop:0.50 #0a2d56, stop:1 #06192f);
    border: none;
    border-bottom: 2px solid #d8b15d;
}
QFrame#DashboardSidebar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #06182f, stop:0.55 #071e3b, stop:1 #051225);
    border: none;
    border-left: 1px solid #173a63;
    border-right: 1px solid #173a63;
}
QLabel#SidebarTitle {
    color: #f2cf7a;
    font-size: 13px;
    font-weight: 900;
    padding: 6px 4px;
}
QToolButton[sidebarNav="true"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(9,33,66,0.96), stop:1 rgba(11,41,77,0.96));
    color: #ffffff;
    border: 1px solid #17416f;
    border-radius: 14px;
    padding: 11px 14px;
    font-size: 12px;
    font-weight: 850;
    text-align: right;
}
QToolButton[sidebarNav="true"]:hover {
    border-color: #d8b15d;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(15,53,102,0.98), stop:1 rgba(12,46,88,0.98));
}
QToolButton[sidebarNav="true"][active="true"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #1759b5, stop:1 #0f76ff);
    border: 1px solid #8bbcff;
    color: #ffffff;
}
QToolButton#SidebarMore {
    background: rgba(255,255,255,0.03);
    color: #f2d17d;
    border: 1px dashed rgba(217,177,90,0.52);
    border-radius: 13px;
}
QFrame#SidebarIdentity {
    background: #081b34;
    border: 1px solid #173a63;
    border-radius: 16px;
}
QLabel#SidebarIdentityTitle {
    color: #ffffff;
    font-size: 13px;
    font-weight: 850;
}
QLabel#SidebarIdentityVersion {
    color: #b9c9de;
    font-size: 11px;
}
QPushButton#SidebarLogout {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #8d1735, stop:1 #c23052);
    color: white;
    border: 1px solid #e17e95;
    border-radius: 12px;
    font-weight: 850;
}
QFrame#DashboardWelcome,
QFrame#MetricCard,
QFrame#DashboardPanel,
QFrame#DashboardListItem,
QFrame#ProjectListItem,
QFrame#MiniStat,
QFrame#VersionCard,
QFrame#MapLegend {
    background: #081b34;
    border: 1px solid #173a63;
    border-radius: 16px;
}
QFrame#DashboardWelcome {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #081b34, stop:1 #0b2446);
}
QLabel#WelcomeTitle,
QLabel#PanelTitle,
QLabel#MetricValue,
QLabel#ListTitle,
QLabel#VersionValue {
    color: #ffffff;
}
QLabel#WelcomeSubtitle,
QLabel#MetricTitle,
QLabel#MetricChange,
QLabel#ListSubtitle,
QLabel#VersionTitle,
QLabel#SystemUpdate,
QLabel#MiniStatTitle {
    color: #b8c7dc;
}
QLabel#MetricValue { font-size: 30px; font-weight: 900; }
QLabel#MetricTitle { font-size: 12px; font-weight: 700; }
QFrame#PanelIcon {
    background: #0b2547;
    border: 1px solid #17416f;
    border-radius: 12px;
}
QPushButton[panelLink="true"] {
    background: #0a2547;
    color: #7cb3ff;
    border: 1px solid #1d4675;
    border-radius: 9px;
    font-weight: 800;
}
QPushButton[panelLink="true"]:hover {
    background: #10305b;
    color: #ffffff;
    border-color: #d8b15d;
}
QLabel#StatusBadge {
    background: #0f3768;
    color: #cfe3ff;
    border: 1px solid #2f6297;
    border-radius: 9px;
    padding: 4px 10px;
    font-size: 9px;
    font-weight: 800;
}
QLabel#StatusBadge[severity="success"] { background: #0d3d2c; color: #9ff2c1; border-color: #1a8358; }
QLabel#StatusBadge[severity="warning"] { background: #4a3205; color: #ffd98a; border-color: #d18b13; }
QLabel#StatusBadge[severity="critical"] { background: #4a1120; color: #ffadb7; border-color: #bb314d; }
QLabel#SystemHealthy {
    color: #bff4d2;
    background: #0c3d2a;
    border: 1px solid #1a8358;
}
QLabel#FooterStatus {
    color: #89e3a9;
    font-weight: 800;
}
QTableView, QTableWidget {
    background: #081b34;
    color: #eef4ff;
    alternate-background-color: #0a2141;
    border: 1px solid #173a63;
    border-radius: 12px;
    gridline-color: #12355f;
}
QHeaderView::section {
    background: #0c2a52;
    color: #f7e0a2;
    border-left: 1px solid #17416f;
}
"""


# نسخه 7.5.1 — اصلاح واقعی هدر و داشبورد مطابق بازخورد کاربر
DASHBOARD_STYLESHEET += """
QFrame#HeaderActionPanel, QFrame#OfficialIdentityPanel, QFrame#HeaderTitlePanel {
    background: transparent;
    border: none;
}
QFrame#OfficialIdentityPanel {
    border-left: 1px solid rgba(216,177,91,0.62);
    border-right: none;
}
QFrame#DashboardFooter {
    background: #061426;
    border-top: 1px solid #173a63;
}
QLabel#FooterRights, QLabel#FooterUpdate {
    color: #b8c7dc;
    font-size: 10px;
}
QFrame#MapLegend {
    background: #0a2141;
    border: 1px solid #173a63;
}
QFrame#DashboardPanel {
    background: #081b34;
    border: 1px solid #173a63;
    border-radius: 16px;
}
QFrame#DashboardListItem, QFrame#ProjectListItem, QFrame#MiniStat {
    background: #0a2141;
    border: 1px solid #173a63;
}
QLabel#ListTitle, QLabel#MiniStatValue, QLabel#PanelTitle {
    color: #ffffff;
}
QLabel#ListSubtitle, QLabel#MiniStatTitle {
    color: #b8c7dc;
}
QToolButton[headerTool="true"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(216,177,91,0.20);
    border-radius: 12px;
    color: #ffffff;
}
QToolButton[headerTool="true"]:hover {
    background: rgba(255,255,255,0.09);
    border-color: rgba(216,177,91,0.58);
}
"""

LOGIN_STYLESHEET += """
QLabel {
    color: #ffffff;
}
"""


# نسخه 7.6.0 — اعمال قالب نهایی تأییدشده کاربر در کل برنامه
MAIN_STYLESHEET += """
/* Global font remains inherited from QApplication; no QSS font aliases. */
QMainWindow, QDialog { background: #07162d; }
QFrame, QGroupBox, QWidget[card="true"] {
    color: #eef4ff;
}
QPushButton, QToolButton {
    font-weight: 800;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateEdit {
    background: #081c36;
    color: #ffffff;
    border: 1px solid #1b4a82;
    border-radius: 10px;
    padding: 8px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {
    border-color: #d8b15d;
}
QTableView, QTableWidget, QTreeView, QListView {
    background: #081b34;
    color: #eef4ff;
    alternate-background-color: #0a2141;
    border: 1px solid #173a63;
    border-radius: 12px;
    gridline-color: #12355f;
}
QHeaderView::section {
    min-height: 38px;
    background: #0c2a52;
    color: #f7e0a2;
    border: none;
    border-left: 1px solid #17416f;
    padding: 8px 10px;
    font-weight: 800;
}
"""

LOGIN_STYLESHEET += """
QWidget#LoginRoot {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #051224, stop:0.55 #081d39, stop:1 #0b2d55);
}
QFrame#LoginCard {
    background: rgba(7, 24, 47, 0.95);
    border: 1px solid #1d4b83;
    border-top: 3px solid #d8b15d;
    border-radius: 18px;
}
QLabel#LoginTitle { color:#ffffff; font-size:22px; font-weight:900; }
QLabel#LoginSubtitle { color:#d3dff3; font-size:12px; font-weight:650; }
QPushButton#LoginButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1b63d2, stop:1 #0f7cff);
    color:#ffffff; border:1px solid #5ba2ff; border-radius:12px; padding:12px; font-size:14px;
}
QPushButton#LoginButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2372ee, stop:1 #248aff); }
"""

DASHBOARD_STYLESHEET += """
QWidget#DashboardRoot,
QWidget#DashboardShell,
QWidget#DashboardContent,
QScrollArea#DashboardScroll,
QScrollArea#DashboardScroll QWidget#qt_scrollarea_viewport {
    background: #07172d;
    color: #eef4ff;
}
QFrame#SoftwareHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #041224, stop:0.50 #072650, stop:1 #041224);
    border: none;
    border-bottom: 2px solid #d6ac53;
}
QFrame#DashboardSidebar {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #05162c, stop:0.55 #071b36, stop:1 #041121);
    border: 1px solid #14365f;
    border-radius: 18px;
}
QLabel#SidebarTitle {
    color:#f1cc73; font-size:13px; font-weight:900; padding:4px;
}
QFrame#SidebarUserCard {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(216,177,91,0.36);
    border-radius: 16px;
}
QLabel#SidebarUserAvatar {
    background: rgba(216,177,91,0.10);
    border: 1px solid rgba(216,177,91,0.45);
    border-radius: 21px;
}
QLabel#SidebarUserName {
    color:#ffffff; font-size:13px; font-weight:850;
}
QLabel#SidebarUserRole {
    color:#f0c96d; font-size:10px; font-weight:700;
}
QToolButton[sidebarNav="true"] {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(7,27,54,0.98), stop:1 rgba(9,33,66,0.98));
    color:#ffffff; border:1px solid #17416f; border-radius:15px; padding:12px 15px; font-size:12px; font-weight:850;
}
QToolButton[sidebarNav="true"]:hover {
    border-color:#d8b15d; background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 rgba(17,61,115,0.98), stop:1 rgba(10,45,88,0.98));
}
QToolButton[sidebarNav="true"][active="true"] {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1b5db8, stop:1 #0e78ff);
    color:#ffffff; border:1px solid #8fc0ff;
}
QToolButton#SidebarMore {
    background: rgba(255,255,255,0.02); color:#f2cf7a; border:1px dashed rgba(217,177,90,0.52); border-radius:14px;
}
QFrame#SidebarIdentity {
    background:#071a32; border:1px solid #173a63; border-radius:16px;
}
QLabel#SidebarIdentityTitle { color:#ffffff; font-size:13px; font-weight:850; }
QLabel#SidebarIdentityVersion { color:#b8c7dc; font-size:10px; }
QPushButton#SidebarLogout {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #922540, stop:1 #cc3559);
    color:white; border:1px solid #e6879a; border-radius:12px; font-weight:850;
}
QPushButton#SidebarLogout:hover {
    background:qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #aa2c4c, stop:1 #df4469);
}
QFrame#MetricCard,
QFrame#DashboardPanel,
QFrame#DashboardListItem,
QFrame#ProjectListItem,
QFrame#MiniStat,
QFrame#VersionCard,
QFrame#MapLegend {
    background: #081b34;
    border: 1px solid #173a63;
    border-radius: 18px;
}
QFrame#MetricCard { border-color:#1e4778; }
QFrame#MetricIcon {
    border-radius: 31px;
    border: 2px solid rgba(255,255,255,0.16);
    background: transparent;
}
QFrame#MetricIcon[accent="blue"] { background: rgba(51,122,225,0.18); border-color:#4f87df; }
QFrame#MetricIcon[accent="green"] { background: rgba(54,171,108,0.18); border-color:#3db579; }
QFrame#MetricIcon[accent="orange"] { background: rgba(238,162,54,0.18); border-color:#f0ad42; }
QFrame#MetricIcon[accent="purple"] { background: rgba(170,92,227,0.18); border-color:#bb7df2; }
QFrame#MetricIcon[accent="teal"] { background: rgba(62,199,195,0.18); border-color:#58ddd8; }
QLabel#MetricTitle { color:#d6e2f5; font-size:13px; font-weight:700; }
QLabel#MetricValue { color:#ffffff; font-size:24px; font-weight:900; }
QLabel#MetricChange { color:#52d68d; font-size:10px; font-weight:700; }
QFrame#DashboardPanel {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #081b34, stop:1 #0a2141);
}
QFrame#PanelIcon {
    background:#0d274c; border:1px solid #18497e; border-radius:12px;
}
QLabel#PanelTitle,
QLabel#ListTitle,
QLabel#WelcomeTitle,
QLabel#VersionValue { color:#ffffff; font-weight:850; }
QLabel#ListSubtitle,
QLabel#MiniStatTitle,
QLabel#VersionTitle,
QLabel#WelcomeSubtitle,
QLabel#SystemUpdate { color:#b8c7dc; }
QPushButton#PanelAction {
    background: rgba(216,177,91,0.10); color:#f3cf78; border:1px solid rgba(216,177,91,0.45); border-radius:9px; padding:6px 12px;
}
QPushButton#PanelAction:hover { background: rgba(216,177,91,0.18); }
QFrame#PanelDivider { background:#14365f; border:none; }
QLabel#StatusBadge {
    background:#0f3768; color:#d9e8ff; border:1px solid #2f6297; border-radius:9px; padding:4px 10px; font-size:9px; font-weight:800;
}
QFrame#DashboardFooter { background:#061426; border-top:1px solid #14365f; }
QLabel#FooterRights, QLabel#FooterUpdate { color:#b8c7dc; font-size:10px; }
"""


# نسخه 7.6.1 — پیاده‌سازی نزدیک‌تر به نمونه نهایی داشبورد
DASHBOARD_STYLESHEET += """
QLabel#SoftwareHeaderTitle { color:#f2c35f; font-size:25px; font-weight:900; }
QLabel#SoftwareHeaderSubtitle { color:#d8e1f1; font-size:13px; font-weight:700; }
QFrame#MetricCard {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #081b34, stop:1 #0b2140);
    border: 1px solid #1c4678;
    border-radius: 18px;
}
QFrame#MetricCard QLabel#MetricChange { color:#53d88e; }
QFrame#DashboardPanel {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #081b34, stop:1 #091f3c);
    border: 1px solid #1c4678;
    border-radius: 18px;
}
QFrame#MiniStat {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #081b34, stop:1 #0a2141);
    border: 1px solid #1e4778;
    border-radius: 18px;
}
QFrame#MiniStatIcon {
    background: rgba(255,255,255,0.03);
    border: 2px solid rgba(216,177,91,0.30);
    border-radius: 27px;
}
QFrame#MiniStatIcon[accent="blue"] { border-color:#4f87df; }
QFrame#MiniStatIcon[accent="teal"] { border-color:#58ddd8; }
QFrame#MiniStatIcon[accent="orange"] { border-color:#efab40; }
QFrame#MiniStatIcon[accent="gold"] { border-color:#d8b15d; }
QLabel#MiniStatValue { color:#ffffff; font-size:28px; font-weight:900; }
QLabel#MiniStatTitle { color:#d4deef; font-size:12px; font-weight:700; }
QPushButton#MiniStatLink {
    background: transparent;
    color:#f2cf7a;
    border:none;
    font-weight:800;
    padding:4px 0;
}
QPushButton#MiniStatLink:hover { color:#ffffff; }
"""


# نسخه 7.6.2 — هدر ۱:۱ نزدیک‌تر به نمونه تأییدشده
DASHBOARD_STYLESHEET += """
QFrame#SoftwareHeader {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #041224, stop:0.46 #08244b, stop:0.80 #0a3466, stop:1 #041224);
    border: none;
    border-bottom: 2px solid #d1a84c;
}
QFrame#OfficialIdentityPanel {
    border-right: 1px solid rgba(216,177,91,0.62);
}
QFrame#HeaderActionPanel QToolButton[headerTool="true"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(216,177,91,0.16);
    border-radius: 11px;
    color: #ffffff;
}
QFrame#HeaderActionPanel QToolButton[headerTool="true"]:hover {
    background: rgba(255,255,255,0.08);
    border-color: rgba(216,177,91,0.48);
}
QLabel#SoftwareHeaderTitle { color:#f2c35f; }
QLabel#SoftwareHeaderSubtitle { color:#dce9fb; }
"""


# نسخه 7.6.6 — تضمین کنتراست متن در ورودی‌های دارای پس‌زمینه سفید
MAIN_STYLESHEET += """
/* ورودی‌های روشن باید در همه سیستم‌عامل‌ها متن مشکی و خوانا داشته باشند. */
QInputDialog QLineEdit,
QInputDialog QTextEdit,
QInputDialog QPlainTextEdit,
QInputDialog QComboBox,
QInputDialog QSpinBox,
QInputDialog QDoubleSpinBox,
QFileDialog QLineEdit,
QFileDialog QComboBox,
QLineEdit[lightInputSurface="true"],
QTextEdit[lightInputSurface="true"],
QPlainTextEdit[lightInputSurface="true"],
QComboBox[lightInputSurface="true"],
QSpinBox[lightInputSurface="true"],
QDoubleSpinBox[lightInputSurface="true"],
QDateEdit[lightInputSurface="true"],
QDateTimeEdit[lightInputSurface="true"],
QTimeEdit[lightInputSurface="true"] {
    background: #ffffff;
    background-color: #ffffff;
    color: #111111;
    selection-background-color: #245fa8;
    selection-color: #ffffff;
    border: 1px solid #aeb9c7;
}
QLineEdit[lightInputSurface="true"]:disabled,
QTextEdit[lightInputSurface="true"]:disabled,
QPlainTextEdit[lightInputSurface="true"]:disabled,
QComboBox[lightInputSurface="true"]:disabled,
QSpinBox[lightInputSurface="true"]:disabled,
QDoubleSpinBox[lightInputSurface="true"]:disabled,
QDateEdit[lightInputSurface="true"]:disabled,
QDateTimeEdit[lightInputSurface="true"]:disabled,
QTimeEdit[lightInputSurface="true"]:disabled {
    background: #f1f3f5;
    color: #4b5563;
}
QInputDialog QComboBox QAbstractItemView,
QFileDialog QComboBox QAbstractItemView,
QComboBox[lightInputSurface="true"] QAbstractItemView {
    background: #ffffff;
    color: #111111;
    selection-background-color: #dce9f8;
    selection-color: #111111;
}
"""


# نسخه 7.6.7 — منوی دو ستونه و نقشه کامل اسکرول‌پذیر
DASHBOARD_STYLESHEET += """
QScrollArea#DashboardSidebarScroll,
QScrollArea#DashboardSidebarScroll QWidget#qt_scrollarea_viewport,
QWidget#DashboardSidebarNavHost,
QScrollArea#DashboardMapScroll,
QScrollArea#DashboardMapScroll QWidget#qt_scrollarea_viewport,
QWidget#DashboardMapHost {
    background: transparent;
    border: none;
}
QToolButton[sidebarNav="true"] {
    padding: 6px 5px;
    font-size: 10px;
    font-weight: 800;
    text-align: center;
    border-radius: 12px;
}
QToolButton#SidebarMore {
    min-height: 42px;
    padding: 7px 9px;
}
QScrollArea#DashboardMapScroll {
    border: 1px solid rgba(53, 103, 166, 0.52);
    border-radius: 14px;
}
QScrollArea#DashboardMapScroll QScrollBar:horizontal,
QScrollArea#DashboardMapScroll QScrollBar:vertical {
    background: #07182f;
}
"""

# نسخه 7.6.13 — اصلاح قطعی کنتراست تمام فیلدهای ورودی در پنل ادمین
# این قانون عمداً در انتهای فایل قرار گرفته تا تم تیره و تنظیمات بومی macOS/Windows
# نتوانند متن سفید را روی پس‌زمینه سفید نمایش دهند.
_ADMIN_LIGHT_INPUTS_QSS = """
QLineEdit,
QTextEdit,
QPlainTextEdit,
QComboBox,
QAbstractSpinBox,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QDateTimeEdit,
QTimeEdit,
QKeySequenceEdit,
QLineEdit#LoginInput,
QLineEdit#DashboardSearch {
    background: #ffffff;
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #9eabbc;
    border-radius: 9px;
    padding: 7px 10px;
    selection-background-color: #245fa8;
    selection-color: #ffffff;
}
QLineEdit:hover,
QTextEdit:hover,
QPlainTextEdit:hover,
QComboBox:hover,
QAbstractSpinBox:hover,
QSpinBox:hover,
QDoubleSpinBox:hover,
QDateEdit:hover,
QDateTimeEdit:hover,
QTimeEdit:hover,
QKeySequenceEdit:hover,
QLineEdit#LoginInput:hover,
QLineEdit#DashboardSearch:hover {
    border-color: #6f86a3;
}
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QAbstractSpinBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QDateTimeEdit:focus,
QTimeEdit:focus,
QKeySequenceEdit:focus,
QLineEdit#LoginInput:focus,
QLineEdit#DashboardSearch:focus {
    background: #ffffff;
    color: #0f172a;
    border: 2px solid #c99b39;
}
QLineEdit:read-only,
QTextEdit:read-only,
QPlainTextEdit:read-only,
QAbstractSpinBox:read-only {
    background: #f7f8fa;
    color: #273244;
}
QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled,
QComboBox:disabled,
QAbstractSpinBox:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QDateEdit:disabled,
QDateTimeEdit:disabled,
QTimeEdit:disabled,
QKeySequenceEdit:disabled {
    background: #edf0f3;
    color: #4b5563;
    border-color: #c8d0da;
}
QComboBox QAbstractItemView,
QComboBoxPrivateContainer QAbstractItemView,
QInputDialog QComboBox QAbstractItemView,
QFileDialog QComboBox QAbstractItemView {
    background: #ffffff;
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #9eabbc;
    selection-background-color: #dce9f8;
    selection-color: #111827;
    outline: none;
}
QComboBox::drop-down {
    background: #f3f6f9;
    border: none;
    border-right: 1px solid #d4dae2;
    width: 30px;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
"""

MAIN_STYLESHEET += _ADMIN_LIGHT_INPUTS_QSS
LOGIN_STYLESHEET += _ADMIN_LIGHT_INPUTS_QSS
DASHBOARD_STYLESHEET += _ADMIN_LIGHT_INPUTS_QSS

