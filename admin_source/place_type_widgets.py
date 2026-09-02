# -*- coding: utf-8 -*-
"""ویجت استاندارد انتخاب نوع مکان برای تمام فرم‌های افزودن مکان دستی."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QInputDialog

from place_types import supported_place_labels


class PlaceTypeComboBox(QComboBox):
    """فهرست نوع مکان که با کلیک باز می‌شود و با چرخ موس ناخواسته تغییر نمی‌کند."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(supported_place_labels())
        # حالت غیرقابل‌ویرایش باعث می‌شود کلیک روی تمام سطح باکس، فهرست را باز کند.
        # افزودن نوع سفارشی از دکمه + کنار فیلد انجام می‌شود.
        self.setEditable(False)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(16)
        self.setMinimumContentsLength(24)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setFocusPolicy(Qt.StrongFocus)
        self.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setToolTip("برای بازکردن فهرست، روی باکس کلیک کنید. برای نوع جدید از دکمه + استفاده کنید.")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setFocus(Qt.MouseFocusReason)
            self.showPopup()
            event.accept()
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        # تغییر تصادفی نوع مکان با اسکرول صفحه جلوگیری می‌شود.
        # پیمایش با چرخ موس فقط زمانی فعال است که فهرست واقعاً باز باشد.
        if self.view().isVisible():
            super().wheelEvent(event)
        else:
            event.ignore()

    def add_custom_type(self, parent=None):
        text, ok = QInputDialog.getText(
            parent or self.window(),
            "افزودن نوع مکان",
            "عنوان نوع مکان جدید را وارد کنید:",
        )
        value = (text or "").strip()
        if not ok or not value:
            return False
        index = self.findText(value, Qt.MatchFixedString)
        if index < 0:
            self.addItem(value)
            index = self.count() - 1
        self.setCurrentIndex(index)
        return True
