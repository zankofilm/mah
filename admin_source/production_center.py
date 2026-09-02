# -*- coding: utf-8 -*-
"""مرکز سلامت، بازیابی بحران و پشتیبانی نسخه عملیاتی."""
from __future__ import annotations

import os
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QGroupBox,
    QProgressBar, QCheckBox,
)

from header_widget import build_official_header
from ui_scroll import scroll_page
from jalali_utils import convert_dates_in_text, format_jalali
from runtime_paths import get_data_dir, get_support_dir
from production_health import (
    run_health_checks, overall_health, recovery_drill, mirror_latest_backup,
    create_support_bundle, cleanup_runtime_files,
)


class ProductionCenterWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db, previous_unclean=False):
        super().__init__()
        self.db = db
        self.previous_unclean = previous_unclean
        self.setWindowTitle("مرکز سلامت و بازیابی سامانه")
        self.resize(1250, 820)
        self._build_ui()
        self.refresh_health()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(build_official_header("مرکز سلامت، پشتیبانی و بازیابی بحران", self.db))

        body_widget = QWidget()
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(26, 18, 26, 24)
        body.setSpacing(12)

        top = QHBoxLayout()
        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.clicked.connect(self.back_requested.emit)
        top.addWidget(back_btn)
        top.addStretch()
        data_btn = QPushButton("بازکردن پوشه داده‌ها")
        data_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(get_data_dir())))
        top.addWidget(data_btn)
        body.addLayout(top)

        self.unclean_label = QLabel()
        self.unclean_label.setWordWrap(True)
        self.unclean_label.setVisible(self.previous_unclean)
        self.unclean_label.setText(
            "⚠ برنامه در اجرای قبلی به‌صورت عادی بسته نشده است. ابتدا کنترل سلامت و سپس آزمون بازیابی را اجرا کنید."
        )
        self.unclean_label.setStyleSheet("background:#fff3cd; color:#7a5500; border:1px solid #e0bd63; padding:10px; border-radius:7px;")
        body.addWidget(self.unclean_label)

        status_group = QGroupBox("وضعیت کلی سامانه")
        status_layout = QVBoxLayout(status_group)
        status_row = QHBoxLayout()
        self.overall_label = QLabel("در حال بررسی...")
        self.overall_label.setStyleSheet("font-size:17px; font-weight:800;")
        status_row.addWidget(self.overall_label)
        status_row.addStretch()
        refresh_btn = QPushButton("اجرای مجدد کنترل سلامت")
        refresh_btn.clicked.connect(self.refresh_health)
        status_row.addWidget(refresh_btn)
        status_layout.addLayout(status_row)
        self.health_progress = QProgressBar()
        self.health_progress.setRange(0, 100)
        self.health_progress.setValue(0)
        status_layout.addWidget(self.health_progress)
        body.addWidget(status_group)

        self.health_table = QTableWidget(0, 4)
        self.health_table.setHorizontalHeaderLabels(["کنترل", "وضعیت", "نتیجه", "جزئیات"])
        self.health_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.health_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.health_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.health_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.health_table.setEditTriggers(QTableWidget.NoEditTriggers)
        body.addWidget(self.health_table, 1)

        actions = QGroupBox("عملیات بازیابی و پشتیبانی")
        actions_layout = QVBoxLayout(actions)
        row1 = QHBoxLayout()
        backup_btn = QPushButton("ساخت بکاپ فوری سالم")
        backup_btn.setProperty("success", True)
        backup_btn.clicked.connect(self.create_backup)
        row1.addWidget(backup_btn)
        drill_btn = QPushButton("آزمون واقعی بازیابی")
        drill_btn.clicked.connect(self.run_recovery_drill)
        row1.addWidget(drill_btn)
        mirror_btn = QPushButton("کپی آخرین بکاپ در مسیر دوم")
        mirror_btn.clicked.connect(self.mirror_backup)
        row1.addWidget(mirror_btn)
        cleanup_btn = QPushButton("پاکسازی فایل‌های موقت قدیمی")
        cleanup_btn.clicked.connect(self.cleanup_files)
        row1.addWidget(cleanup_btn)
        actions_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.include_database_check = QCheckBox("دیتابیس نیز داخل بسته پشتیبانی قرار گیرد")
        self.include_database_check.setToolTip("این گزینه ممکن است اطلاعات محرمانه را وارد بسته کند؛ فقط برای تحویل امن به پشتیبان فعال شود.")
        row2.addWidget(self.include_database_check)
        row2.addStretch()
        support_btn = QPushButton("ساخت بسته پشتیبانی")
        support_btn.clicked.connect(self.build_support_bundle)
        row2.addWidget(support_btn)
        actions_layout.addLayout(row2)
        body.addWidget(actions)

        outer.addWidget(scroll_page(body_widget, min_height=720), 1)

    def refresh_health(self):
        try:
            self.health_progress.setValue(15)
            checks = run_health_checks(self.db)
            self.health_progress.setValue(100)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"کنترل سلامت اجرا نشد:\n{exc}")
            return
        self.checks = checks
        self.health_table.setRowCount(len(checks))
        labels = {"ok": "سالم", "warning": "هشدار", "error": "خطا"}
        colors = {"ok": QColor("#d8f3dc"), "warning": QColor("#fff3cd"), "error": QColor("#f8d7da")}
        for r, item in enumerate(checks):
            details = item.get("details") or {}
            values = [item.get("name"), labels.get(item.get("status"), item.get("status")), item.get("message"),
                      " | ".join(f"{k}: {v}" for k, v in details.items())]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value or "")))
                cell.setBackground(colors.get(item.get("status"), QColor("white")))
                self.health_table.setItem(r, c, cell)
        overall = overall_health(checks)
        if overall == "ok":
            self.overall_label.setText("وضعیت کلی: سالم و آماده بهره‌برداری")
            self.overall_label.setStyleSheet("font-size:17px; font-weight:800; color:#256029;")
        elif overall == "warning":
            self.overall_label.setText("وضعیت کلی: قابل استفاده، دارای هشدار")
            self.overall_label.setStyleSheet("font-size:17px; font-weight:800; color:#8a6200;")
        else:
            self.overall_label.setText("وضعیت کلی: نیازمند اقدام فوری")
            self.overall_label.setStyleSheet("font-size:17px; font-weight:800; color:#a4262c;")

    def create_backup(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره بکاپ فوری", f"javanrood_backup_{datetime.now():%Y%m%d_%H%M%S}.db", "SQLite Database (*.db)"
        )
        if not path:
            return
        try:
            self.db.create_backup(path, backup_type="manual", reason="مرکز سلامت نسخه ۷")
            QMessageBox.information(self, "موفق", f"بکاپ سالم ساخته شد:\n{path}")
            self.refresh_health()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def run_recovery_drill(self):
        folder = QFileDialog.getExistingDirectory(self, "پوشه آزمون بازیابی")
        if not folder:
            return
        try:
            result = recovery_drill(self.db, folder)
        except Exception as exc:
            QMessageBox.critical(self, "آزمون ناموفق", str(exc))
            return
        if result["passed"]:
            QMessageBox.information(self, "آزمون موفق", f"بکاپ ساخته و بدون جایگزینی دیتابیس اصلی بازیابی آزمایشی شد.\n{result['backup_path']}")
        else:
            QMessageBox.warning(self, "مغایرت", "آزمون بازیابی با مغایرت شمارش رکوردها پایان یافت.")
        self.refresh_health()

    def mirror_backup(self):
        folder = QFileDialog.getExistingDirectory(self, "انتخاب مسیر دوم بکاپ")
        if not folder:
            return
        try:
            path = mirror_latest_backup(self.db, folder)
            QMessageBox.information(self, "موفق", f"نسخه دوم بکاپ با کنترل هش ذخیره شد:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def build_support_bundle(self):
        default = os.path.join(get_support_dir(), f"support_{datetime.now():%Y%m%d_%H%M%S}.zip")
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره بسته پشتیبانی", default, "ZIP (*.zip)")
        if not path:
            return
        if self.include_database_check.isChecked():
            reply = QMessageBox.warning(
                self, "اطلاعات محرمانه",
                "دیتابیس می‌تواند شامل اطلاعات شهروندان، مکاتبات و شماره تماس باشد. بسته را فقط از مسیر امن تحویل دهید. ادامه می‌دهید؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
        try:
            output = create_support_bundle(self.db, path, include_database=self.include_database_check.isChecked())
            QMessageBox.information(self, "بسته آماده شد", output)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def cleanup_files(self):
        removed = cleanup_runtime_files(days=14)
        QMessageBox.information(self, "پاکسازی", f"{len(removed)} فایل موقت قدیمی حذف شد.")
