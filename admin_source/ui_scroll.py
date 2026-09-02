# -*- coding: utf-8 -*-
"""ابزار مشترک برای ساخت صفحات اسکرول‌پذیر در رابط کاربری."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QScrollArea, QFrame, QSizePolicy


def scroll_page(widget, min_height=0, min_width=0, object_name="PageScrollArea"):
    """
    یک صفحه را داخل QScrollArea استاندارد قرار می‌دهد.

    هدر و نوار ابزار پنجره ثابت می‌مانند و فقط محتوای اصلی اسکرول می‌شود.
    حداقل ارتفاع برای فرم‌های بلند باعث می‌شود روی نمایشگرهای کوچک نوار اسکرول
    به‌صورت خودکار ظاهر شود، بدون آنکه در نمایشگرهای بزرگ فضای خالی ایجاد کند.
    """
    if min_height:
        widget.setMinimumHeight(int(min_height))
    if min_width:
        widget.setMinimumWidth(int(min_width))
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)

    area = QScrollArea()
    area.setObjectName(object_name)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    area.setAlignment(Qt.AlignTop | Qt.AlignRight)
    area.setWidget(widget)
    area.viewport().setAutoFillBackground(False)
    return area
