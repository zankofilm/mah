# -*- coding: utf-8 -*-
"""مقایسه و رتبه‌بندی وضعیت تمام بلوک‌های شهر بر اساس امتیاز ریسک شفاف.

این ماژول به مدیر ارشد/فرماندار کمک می‌کند بدون باز کردن جداگانه پرونده
هر بلوک، ببیند کدام بلوک‌ها بیشترین مسائل بحرانی، درخواست باز، یا
پرونده معوق دارند — و مستقیماً به پرونده جامع همان بلوک برود.
"""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView
)

from header_widget import build_official_header
from icon_manager import get_icon, set_button_style


class CityComparisonWindow(QWidget):
    """پنجره مقایسه همه بلوک‌های شهر با رتبه‌بندی بر اساس امتیاز ریسک."""

    back_requested = pyqtSignal()
    open_zone_requested = pyqtSignal(int)  # zone_id انتخاب‌شده برای ورود به پرونده جامع

    RISK_COLOR_HIGH = QColor("#f8d7da")     # قرمز ملایم
    RISK_COLOR_MEDIUM = QColor("#fff3cd")   # زرد ملایم
    RISK_COLOR_LOW = QColor("#d4edda")      # سبز ملایم

    def __init__(self, db, current_user=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = current_user or db.get_current_user() or {}
        self._rows_data = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = build_official_header(app_subtitle="مقایسه و رتبه‌بندی بلوک‌ها", db=self.db)
        layout.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(24, 18, 24, 18)
        body.setSpacing(12)

        top_row = QHBoxLayout()
        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_requested.emit)
        top_row.addWidget(back_btn)
        top_row.addStretch()
        refresh_btn = QPushButton("تازه‌سازی")
        set_button_style(refresh_btn, "refresh", "secondary")
        refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(refresh_btn)
        body.addLayout(top_row)

        info = QLabel(
            "بلوک‌ها بر اساس «امتیاز ریسک» مرتب شده‌اند: مسائل بحرانی، مسائل باز، "
            "درخواست‌های مردمی باز، و پرونده‌های پیگیری معوق، هرکدام با وزن مشخص در این "
            "امتیاز سهیم‌اند. رنگ هر ردیف صرفاً برای مشاهده سریع‌تر است؛ اعداد ستون‌ها "
            "منبع واقعی تصمیم‌گیری‌اند."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#555;")
        body.addWidget(info)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "رتبه", "نام بلوک", "امتیاز ریسک", "مسائل بحرانی", "مسائل باز",
            "درخواست‌های باز", "پرونده معوق", "اقدام در جریان",
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        body.addWidget(self.table, 1)

        hint = QLabel("برای ورود به پرونده جامع یک بلوک، روی ردیف آن دوبار کلیک کنید.")
        hint.setStyleSheet("color:#777; font-size:12px;")
        body.addWidget(hint)

        layout.addLayout(body)

    def refresh(self):
        try:
            self._rows_data = self.db.get_all_zones_comparison()
        except Exception as exc:
            QMessageBox.warning(self, "خطا", f"دریافت اطلاعات مقایسه بلوک‌ها با خطا مواجه شد:\n{exc}")
            self._rows_data = []

        self.table.setRowCount(len(self._rows_data))
        for row_idx, item in enumerate(self._rows_data):
            values = [
                str(row_idx + 1),
                item["zone_name"],
                str(item["risk_score"]),
                str(item["issues_critical"]),
                str(item["issues_open"]),
                str(item["citizen_requests_open"]),
                str(item["overdue_execution_cases"]),
                str(item["actions_active"]),
            ]
            color = self._risk_color(item["risk_score"])
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setTextAlignment(Qt.AlignCenter)
                if color:
                    cell.setBackground(color)
                self.table.setItem(row_idx, col, cell)

        if not self._rows_data:
            self.table.setRowCount(1)
            empty_item = QTableWidgetItem("هنوز هیچ بلوکی ثبت نشده است.")
            empty_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(0, 1, empty_item)

    def _risk_color(self, score):
        if score >= 20:
            return self.RISK_COLOR_HIGH
        if score >= 5:
            return self.RISK_COLOR_MEDIUM
        return self.RISK_COLOR_LOW

    def _on_row_double_clicked(self, row, _column):
        if row < 0 or row >= len(self._rows_data):
            return
        zone_id = self._rows_data[row]["zone_id"]
        self.open_zone_requested.emit(zone_id)
