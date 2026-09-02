# -*- coding: utf-8 -*-
"""ویجت‌های ورودی و تقویم شمسی با ذخیره داخلی میلادی."""

from datetime import date
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QRegularExpressionValidator
from PyQt5.QtCore import QRegularExpression
from PyQt5.QtWidgets import (
    QLineEdit, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView
)

from jalali_utils import (
    iso_to_jalali, jalali_to_iso, gregorian_to_jalali, jalali_to_gregorian,
    to_latin_digits, to_persian_digits, today_jalali
)


class JalaliDateEdit(QLineEdit):
    """جایگزین سبک QDateEdit؛ نمایش شمسی و خروجی QDate میلادی برای سازگاری کد قدیمی."""
    dateChanged = pyqtSignal(QDate)

    def __init__(self, value=None, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setPlaceholderText("۱۴۰۵/۰۴/۲۹")
        self.setToolTip("تاریخ را به‌صورت شمسی وارد کنید؛ نمونه: ۱۴۰۵/۰۴/۲۹")
        self.setClearButtonEnabled(True)
        self.setValidator(QRegularExpressionValidator(QRegularExpression(r"[۰-۹0-9]{0,4}/?[۰-۹0-9]{0,2}/?[۰-۹0-9]{0,2}"), self))
        if isinstance(value, QDate):
            self.setDate(value)
        elif value:
            self.setText(iso_to_jalali(value))
        else:
            self.setText(today_jalali())
        self.editingFinished.connect(self._normalize)

    def setCalendarPopup(self, _enabled):
        pass

    def setDisplayFormat(self, _fmt):
        pass

    def setDate(self, qdate):
        if isinstance(qdate, QDate) and qdate.isValid():
            self.setText(iso_to_jalali(qdate.toString("yyyy-MM-dd")))
            self.dateChanged.emit(qdate)

    def date(self):
        try:
            iso = jalali_to_iso(self.text(), required=True)
            return QDate.fromString(iso, "yyyy-MM-dd")
        except Exception:
            return QDate()

    def isoDate(self):
        return jalali_to_iso(self.text(), required=True)

    def _normalize(self):
        try:
            iso = self.isoDate()
            self.setText(iso_to_jalali(iso))
            self.setStyleSheet("")
            self.dateChanged.emit(QDate.fromString(iso, "yyyy-MM-dd"))
        except Exception:
            self.setStyleSheet("border:1px solid #a4262c; background:#fff5f5;")


class JalaliCalendarWidget(QWidget):
    """تقویم ماهانه شمسی با API حداقلی مشابه QCalendarWidget."""
    selectionChanged = pyqtSignal()
    clicked = pyqtSignal(QDate)

    MONTH_NAMES = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
    WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]

    def __init__(self, parent=None):
        super().__init__(parent)
        gy, gm, gd = date.today().year, date.today().month, date.today().day
        self.jy, self.jm, self.jd = gregorian_to_jalali(gy, gm, gd)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        nav = QHBoxLayout()
        prev_btn = QPushButton("ماه قبل")
        next_btn = QPushButton("ماه بعد")
        self.title = QLabel()
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-weight:800; font-size:15px;")
        prev_btn.clicked.connect(lambda: self._move_month(-1))
        next_btn.clicked.connect(lambda: self._move_month(1))
        nav.addWidget(prev_btn); nav.addWidget(self.title, 1); nav.addWidget(next_btn)
        root.addLayout(nav)
        self.table = QTableWidget(6, 7)
        self.table.setHorizontalHeaderLabels(self.WEEKDAYS)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.cellClicked.connect(self._cell_clicked)
        root.addWidget(self.table)
        self._refresh()

    def setGridVisible(self, _visible):
        pass

    def selectedDate(self):
        gy, gm, gd = jalali_to_gregorian(self.jy, self.jm, self.jd)
        return QDate(gy, gm, gd)

    def setSelectedDate(self, qdate):
        if qdate and qdate.isValid():
            self.jy, self.jm, self.jd = gregorian_to_jalali(qdate.year(), qdate.month(), qdate.day())
            self._refresh()
            self.selectionChanged.emit()

    def _month_days(self, jy, jm):
        if jm <= 6: return 31
        if jm <= 11: return 30
        # اختلاف اول فروردین سال بعد و اول اسفند
        gy1, gm1, gd1 = jalali_to_gregorian(jy, 12, 1)
        gy2, gm2, gd2 = jalali_to_gregorian(jy + 1, 1, 1)
        return (date(gy2, gm2, gd2) - date(gy1, gm1, gd1)).days

    def _first_weekday(self):
        gy, gm, gd = jalali_to_gregorian(self.jy, self.jm, 1)
        # Python Monday=0. در تقویم ما شنبه=0
        return (date(gy, gm, gd).weekday() + 2) % 7

    def _refresh(self):
        self.title.setText(f"{self.MONTH_NAMES[self.jm-1]} {to_persian_digits(self.jy)}")
        self.table.clearContents()
        first = self._first_weekday()
        days = self._month_days(self.jy, self.jm)
        for day in range(1, days + 1):
            idx = first + day - 1
            row, col = divmod(idx, 7)
            item = QTableWidgetItem(to_persian_digits(day))
            item.setTextAlignment(Qt.AlignCenter)
            item.setData(Qt.UserRole, day)
            if day == self.jd:
                item.setBackground(Qt.lightGray)
            self.table.setItem(row, col, item)

    def _cell_clicked(self, row, col):
        item = self.table.item(row, col)
        if not item or item.data(Qt.UserRole) is None:
            return
        self.jd = int(item.data(Qt.UserRole))
        self._refresh()
        qdate = self.selectedDate()
        self.selectionChanged.emit()
        self.clicked.emit(qdate)

    def _move_month(self, delta):
        total = self.jy * 12 + (self.jm - 1) + delta
        self.jy, rem = divmod(total, 12)
        self.jm = rem + 1
        self.jd = min(self.jd, self._month_days(self.jy, self.jm))
        self._refresh()
        self.selectionChanged.emit()


class JalaliDisplayFilter(QObject):
    """تبدیل تاریخ‌های میلادی باقی‌مانده در QLabelها هنگام نمایش پنجره."""
    def eventFilter(self, obj, event):
        try:
            from PyQt5.QtWidgets import QLabel
            from jalali_utils import convert_dates_in_text
            if isinstance(obj, QLabel) and event.type() in (QEvent.Show, QEvent.Polish, QEvent.LayoutRequest):
                current = obj.text()
                converted = convert_dates_in_text(current)
                if converted != current:
                    obj.setText(converted)
        except Exception:
            pass
        return False
