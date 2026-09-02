# -*- coding: utf-8 -*-
"""Application-wide responsive font, icon and control sizing."""

from __future__ import annotations

from PyQt5.QtCore import QObject, QEvent, QTimer, QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget, QAbstractButton, QLineEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QDateEdit, QDateTimeEdit, QTableView, QTreeView,
    QListView, QTabWidget, QTextEdit, QPlainTextEdit,
)

from design_system import metrics_for_width, scaled
from ui_typography import make_ui_font


def _alive(obj):
    try:
        obj.thread()
        return True
    except Exception:
        return False


def _logical_dpi(window):
    try:
        screen = window.screen()
        return screen.logicalDotsPerInch() if screen is not None else 96.0
    except Exception:
        return 96.0


def apply_responsive_metrics(window):
    """Apply one coherent density profile to a top-level window and its children."""
    if not _alive(window) or not isinstance(window, QWidget):
        return
    try:
        width = window.width()
        if window.isMaximized() and window.screen() is not None:
            width = window.screen().availableGeometry().width()
    except Exception:
        width = window.width()

    metrics = metrics_for_width(width)
    dpi = _logical_dpi(window)
    old_profile = window.property("responsiveProfile")
    window.setProperty("responsiveProfile", metrics.profile)
    window.setProperty("uiDensity", metrics.profile)
    window.setProperty("uiDpi", round(dpi, 1))
    window.setFont(make_ui_font(metrics.base_font_pt, QFont.Normal))

    for button in window.findChildren(QAbstractButton):
        try:
            if not button.property("allowSmallControl"):
                button.setMinimumHeight(scaled(metrics.control_height, dpi))
            if not button.icon().isNull():
                if button.property("dashboardNav"):
                    size = metrics.icon_large
                elif button.property("headerTool"):
                    size = metrics.icon_normal
                elif button.property("compact"):
                    size = metrics.icon_small
                else:
                    size = metrics.icon_normal
                button.setIconSize(QSize(scaled(size, dpi), scaled(size, dpi)))
                if not button.toolTip() and button.text().strip():
                    button.setToolTip(button.text().replace("\n", " ").strip())
        except Exception:
            continue

    input_types = (
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
        QDateEdit, QDateTimeEdit,
    )
    for widget_type in input_types:
        for widget in window.findChildren(widget_type):
            try:
                widget.setMinimumHeight(scaled(metrics.control_height, dpi))
            except Exception:
                pass

    for widget_type in (QTextEdit, QPlainTextEdit):
        for widget in window.findChildren(widget_type):
            try:
                widget.setFont(make_ui_font(metrics.base_font_pt, QFont.Normal))
            except Exception:
                pass

    for view_type in (QTableView, QTreeView, QListView):
        for view in window.findChildren(view_type):
            try:
                if hasattr(view, "verticalHeader"):
                    view.verticalHeader().setDefaultSectionSize(scaled(metrics.table_row_height, dpi))
                view.setIconSize(QSize(scaled(metrics.icon_normal, dpi), scaled(metrics.icon_normal, dpi)))
            except Exception:
                pass

    for tabs in window.findChildren(QTabWidget):
        try:
            tabs.setIconSize(QSize(scaled(metrics.icon_normal, dpi), scaled(metrics.icon_normal, dpi)))
            tabs.tabBar().setUsesScrollButtons(True)
            tabs.tabBar().setExpanding(metrics.profile != "compact")
        except Exception:
            pass

    try:
        if old_profile != metrics.profile:
            window.style().unpolish(window)
            window.style().polish(window)
        custom = getattr(window, "apply_responsive_profile", None)
        if callable(custom):
            custom(metrics.profile, metrics)
    except Exception:
        pass


class ResponsiveUiFilter(QObject):
    """Debounced application event filter for resolution and DPI changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending = set()

    def _schedule(self, window):
        if not _alive(window):
            return
        key = id(window)
        if key in self._pending:
            return
        self._pending.add(key)

        def run(target=window, token=key):
            self._pending.discard(token)
            if _alive(target):
                apply_responsive_metrics(target)

        QTimer.singleShot(35, run)

    def eventFilter(self, obj, event):
        try:
            if isinstance(obj, QWidget):
                window = obj.window()
                if event.type() in (
                    QEvent.Show, QEvent.Resize, QEvent.WindowStateChange,
                ):
                    if window is obj or event.type() in (QEvent.Show, QEvent.Resize):
                        self._schedule(window)
                # ScreenChangeInternal is not available on every PyQt build.
                screen_change = getattr(QEvent, "ScreenChangeInternal", None)
                if screen_change is not None and event.type() == screen_change:
                    self._schedule(window)
        except Exception:
            pass
        return False
