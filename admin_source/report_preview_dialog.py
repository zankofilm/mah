# -*- coding: utf-8 -*-
"""دیالوگ پایدار پیش‌نمایش گزارش‌ها.

پیش‌نمایش داخل برنامه همیشه به‌صورت HTML نمایش داده می‌شود؛ چون نمایش مستقیم
PDF در QWebEngineView روی بعضی نسخه‌های ویندوز/QtWebEngine سفید می‌ماند.
برای گزارش PDF، فایل PDF واقعی نیز از قبل تولید می‌شود و با دکمه جداگانه
می‌توان آن را در PDF Reader سیستم باز کرد.
"""

import os
from runtime_paths import get_temp_dir
import subprocess
import sys
import tempfile

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
    QProgressBar
)
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings


class DebugWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS Console - Report Preview] {message} (line {lineNumber})")


class ReportPreviewDialog(QDialog):
    """نمایش HTML گزارش و تأیید تولید فایل نهایی.

    preview_source:
      - رشته HTML کامل، یا
      - مسیر یک فایل HTML محلی.

    exact_preview_path:
      مسیر PDF واقعی موقت؛ فقط برای بازکردن در PDF Reader سیستم استفاده می‌شود.
    """

    def __init__(
        self,
        fmt,
        preview_source,
        final_generator_fn,
        final_output_path,
        parent=None,
        exact_preview_path=None,
    ):
        super().__init__(parent)
        self.fmt = fmt
        self.final_generator_fn = final_generator_fn
        self.final_output_path = final_output_path
        self.exact_preview_path = exact_preview_path
        self.confirmed = False
        self._temp_html_path = None

        self.setWindowTitle("پیش‌نمایش گزارش")
        self.setMinimumSize(860, 620)
        self._resize_to_screen()
        self._build_ui(preview_source)

    def _resize_to_screen(self):
        screen = self.screen()
        if not screen:
            self.resize(1000, 760)
            return
        available = screen.availableGeometry()
        width = min(1200, max(860, int(available.width() * 0.90)))
        height = min(900, max(620, int(available.height() * 0.90)))
        self.resize(width, height)

    def _build_ui(self, preview_source):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        info = QLabel(
            "این پیش‌نمایش گزارش شماست. محتوا را بررسی کنید و سپس "
            "«تأیید و ذخیره فایل نهایی» را بزنید."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setMaximumHeight(5)
        layout.addWidget(self.loading_bar)

        self.preview_status = QLabel("در حال بارگذاری پیش‌نمایش…")
        self.preview_status.setStyleSheet("color:#5b6472;")
        layout.addWidget(self.preview_status)

        self.webview = QWebEngineView()
        self.page = DebugWebPage(self.webview)
        self.webview.setPage(self.page)
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        self.webview.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.webview, stretch=1)

        html_path = self._prepare_html_file(preview_source)
        self.webview.setUrl(QUrl.fromLocalFile(html_path))

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("انصراف")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        if self.exact_preview_path and os.path.exists(self.exact_preview_path):
            exact_btn = QPushButton("🔎 باز کردن PDF واقعی")
            exact_btn.clicked.connect(self._open_exact_preview)
            btn_row.addWidget(exact_btn)

        retry_btn = QPushButton("↻ بارگذاری مجدد")
        retry_btn.clicked.connect(self.webview.reload)
        btn_row.addWidget(retry_btn)

        btn_row.addStretch()

        confirm_btn = QPushButton("✅ تأیید و ذخیره فایل نهایی")
        confirm_btn.setProperty("success", True)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)

        layout.addLayout(btn_row)

    def _prepare_html_file(self, preview_source):
        if isinstance(preview_source, str) and os.path.isfile(preview_source):
            if preview_source.lower().endswith(('.html', '.htm')):
                return os.path.abspath(preview_source)

        html_content = preview_source if isinstance(preview_source, str) else str(preview_source)
        if "<html" not in html_content.lower():
            html_content = (
                '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">'
                '<style>body{font-family:Tahoma;direction:rtl;padding:24px}</style></head>'
                f'<body>{html_content}</body></html>'
            )

        temp_dir = get_temp_dir()
        os.makedirs(temp_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix="report_preview_", suffix=".html", dir=temp_dir)
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        self._temp_html_path = path
        return os.path.abspath(path)

    def _on_load_finished(self, ok):
        self.loading_bar.setVisible(False)
        if ok:
            self.preview_status.setText("پیش‌نمایش آماده است.")
            self.preview_status.setStyleSheet("color:#2e7d32;")
        else:
            self.preview_status.setText(
                "بارگذاری پیش‌نمایش داخل برنامه ناموفق بود. دکمه «بارگذاری مجدد» را بزنید؛ "
                "برای PDF می‌توانید از «باز کردن PDF واقعی» استفاده کنید."
            )
            self.preview_status.setStyleSheet("color:#a4262c;")

    def _open_exact_preview(self):
        if not self.exact_preview_path or not os.path.exists(self.exact_preview_path):
            QMessageBox.warning(self, "فایل موجود نیست", "فایل PDF موقت پیدا نشد.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(self.exact_preview_path))):
            QMessageBox.warning(
                self,
                "بازکردن فایل ناموفق بود",
                f"PDF Reader ویندوز نتوانست فایل را باز کند:\n{self.exact_preview_path}",
            )

    def _on_confirm(self):
        try:
            self.final_generator_fn()
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"ذخیره فایل نهایی با خطا مواجه شد:\n{e}")
            return
        self.confirmed = True
        self.accept()

    def closeEvent(self, event):
        # حذف فایل HTML موقت پس از بسته‌شدن پنجره؛ PDF موقت توسط برنامه قابل بازاستفاده است.
        try:
            if self._temp_html_path and os.path.exists(self._temp_html_path):
                os.remove(self._temp_html_path)
        except OSError:
            pass
        super().closeEvent(event)


def make_temp_pdf_path(suffix="preview"):
    """مسیر PDF موقت برای اعتبارسنجی و بازکردن در PDF Reader سیستم."""
    temp_dir = get_temp_dir()
    os.makedirs(temp_dir, exist_ok=True)
    return os.path.join(temp_dir, f"report_preview_{suffix}.pdf")
