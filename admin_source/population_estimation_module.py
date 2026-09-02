# -*- coding: utf-8 -*-
"""رابط حرفه‌ای برآورد جمعیت بلوک‌ها بدون سرشماری خانه‌به‌خانه."""
from __future__ import annotations

import csv
import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QFileDialog, QFrame, QSplitter, QTextEdit, QProgressBar, QSizePolicy, QLayout,
)

from access_control import has_permission
from icon_manager import get_icon
from jalali_utils import to_persian_digits, convert_dates_in_text
from population_engine import aggregate_population_file


def _fa(value):
    if value in (None, ""):
        return "—"
    if isinstance(value, float):
        text = f"{value:,.1f}"
    else:
        text = f"{int(value):,}"
    return to_persian_digits(text)


class PopulationEstimationWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db, current_user=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = current_user or db.get_current_user() or {}
        self.can_write = self.current_user.get("role") in {"admin", "manager", "gis"}
        self.selected_zone_id = None
        self.setWindowTitle("برآورد جمعیت بلوک‌ها")
        self.resize(1500, 900)
        self.setMinimumSize(940, 560)
        self.setLayoutDirection(Qt.RightToLeft)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSizeConstraint(QLayout.SetNoConstraint)
        root.setContentsMargins(16, 12, 16, 16)
        root.setSpacing(12)

        top = QHBoxLayout()
        back = QPushButton("بازگشت به داشبورد")
        back.setIcon(get_icon("back", "navy"))
        back.clicked.connect(self.back_requested.emit)
        top.addWidget(back)
        top.addStretch()
        title_box = QVBoxLayout()
        title = QLabel("برآورد هوشمند جمعیت هر بلوک")
        title.setStyleSheet("font-size:21px;font-weight:900;color:#17345f")
        subtitle = QLabel("ترکیب داده‌های WorldPop، GHSL، واحدهای مسکونی و کنتورهای فعال همراه با بازه عدم‌قطعیت")
        subtitle.setStyleSheet("color:#64748b")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        root.addLayout(top)

        source_card = QFrame()
        source_card.setObjectName("PopulationSourceCard")
        source_card.setStyleSheet(
            "QFrame#PopulationSourceCard{background:#f8fafc;border:1px solid #dbe4ee;border-radius:12px}"
        )
        source_layout = QGridLayout(source_card)
        source_layout.setContentsMargins(14, 12, 14, 12)
        source_layout.setHorizontalSpacing(9)
        source_layout.setVerticalSpacing(8)
        self.source_combo = QComboBox()
        self.source_combo.addItem("WorldPop", "worldpop")
        self.source_combo.addItem("GHSL", "ghsl")
        self.source_year = QSpinBox()
        self.source_year.setRange(2000, 2035)
        self.source_year.setValue(2025)
        self.value_field = QLineEdit()
        self.value_field.setPlaceholderText("اختیاری؛ مثال: population")
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("CSV، GeoJSON یا GeoTIFF جمعیتی را انتخاب کنید")
        browse = QPushButton("انتخاب فایل")
        browse.setIcon(get_icon("folder", "navy"))
        browse.clicked.connect(self.choose_file)
        self.import_button = QPushButton("محاسبه و ثبت منبع")
        self.import_button.setIcon(get_icon("map", "white"))
        self.import_button.setStyleSheet("background:#17345f;color:white;font-weight:800;padding:9px 14px;border-radius:7px")
        self.import_button.clicked.connect(self.import_source)
        self.import_button.setEnabled(self.can_write)
        source_layout.addWidget(QLabel("منبع:"), 0, 0)
        source_layout.addWidget(self.source_combo, 0, 1)
        source_layout.addWidget(QLabel("سال داده:"), 0, 2)
        source_layout.addWidget(self.source_year, 0, 3)
        source_layout.addWidget(QLabel("ستون جمعیت:"), 0, 4)
        source_layout.addWidget(self.value_field, 0, 5)
        source_layout.addWidget(self.file_path, 1, 0, 1, 5)
        source_layout.addWidget(browse, 1, 5)
        source_layout.addWidget(self.import_button, 1, 6)
        self.source_status = QLabel("هنوز منبع مکانی وارد نشده است.")
        self.source_status.setWordWrap(True)
        self.source_status.setStyleSheet("color:#42526b;font-weight:700")
        source_layout.addWidget(self.source_status, 2, 0, 1, 7)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        source_layout.addWidget(self.progress, 3, 0, 1, 7)
        source_layout.setColumnStretch(0, 0)
        source_layout.setColumnStretch(1, 1)
        source_layout.setColumnStretch(5, 1)
        root.addWidget(source_card)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        table_panel = QFrame()
        table_panel.setStyleSheet("QFrame{background:#fff;border:1px solid #dbe4ee;border-radius:11px}")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_top = QHBoxLayout()
        table_top.addWidget(QLabel("نتیجه بلوک‌ها"))
        table_top.addStretch()
        calculate_all = QPushButton("محاسبه همه بلوک‌ها")
        calculate_all.setIcon(get_icon("refresh", "navy"))
        calculate_all.clicked.connect(self.calculate_all)
        calculate_all.setEnabled(self.can_write)
        export = QPushButton("خروجی CSV")
        export.setIcon(get_icon("report", "navy"))
        export.clicked.connect(self.export_csv)
        refresh = QPushButton("تازه‌سازی")
        refresh.setIcon(get_icon("refresh", "navy"))
        refresh.clicked.connect(self.refresh_all)
        table_top.addWidget(calculate_all)
        table_top.addWidget(export)
        table_top.addWidget(refresh)
        table_layout.addLayout(table_top)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "بلوک", "WorldPop", "GHSL", "واحد مسکونی", "کنتور", "جمعیت نهایی",
            "بازه برآورد", "خانوار", "تراکم/km²", "اطمینان",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 10):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.load_selected_zone)
        table_layout.addWidget(self.table, 1)
        self.summary_label = QLabel("جمعیت کل برآوردشده: —")
        self.summary_label.setStyleSheet("font-weight:900;color:#17345f;padding:7px")
        table_layout.addWidget(self.summary_label)

        input_panel = QFrame()
        input_panel.setMinimumWidth(360)
        input_panel.setMaximumWidth(470)
        input_panel.setStyleSheet("QFrame{background:#f8fafc;border:1px solid #dbe4ee;border-radius:11px}")
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(14, 14, 14, 14)
        self.zone_title = QLabel("یک بلوک را انتخاب کنید")
        self.zone_title.setStyleSheet("font-size:17px;font-weight:900;color:#17345f")
        input_layout.addWidget(self.zone_title)
        hint = QLabel("اطلاعات موجود در پرونده بلوک به‌صورت خودکار خوانده می‌شود. مقادیر قابل اصلاح هستند.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b")
        input_layout.addWidget(hint)

        form = QFormLayout()
        self.buildings = QSpinBox(); self.buildings.setRange(0, 1_000_000)
        self.units = QSpinBox(); self.units.setRange(0, 1_000_000)
        self.occupied_units = QSpinBox(); self.occupied_units.setRange(0, 1_000_000)
        self.occupancy_rate = QDoubleSpinBox(); self.occupancy_rate.setRange(0, 100); self.occupancy_rate.setDecimals(1); self.occupancy_rate.setSuffix("٪")
        self.household_size = QDoubleSpinBox(); self.household_size.setRange(0.1, 20); self.household_size.setDecimals(2)
        self.active_meters = QSpinBox(); self.active_meters.setRange(0, 1_000_000)
        self.adjustment = QSpinBox(); self.adjustment.setRange(-1_000_000, 1_000_000)
        self.adjustment.setToolTip("اصلاح محدود مدیریتی برای خطاهای شناخته‌شده؛ مقدار و دلیل آن در سوابق باقی می‌ماند.")
        self.notes = QTextEdit(); self.notes.setMaximumHeight(90); self.notes.setPlaceholderText("منبع تعداد واحدها، دلیل اصلاح یا توضیح کارشناسی")
        form.addRow("ساختمان مسکونی:", self.buildings)
        form.addRow("کل واحد مسکونی:", self.units)
        form.addRow("واحد اشغال‌شده:", self.occupied_units)
        form.addRow("نرخ سکونت:", self.occupancy_rate)
        form.addRow("بعد خانوار:", self.household_size)
        form.addRow("کنتور فعال مسکونی:", self.active_meters)
        form.addRow("اصلاح کارشناسی (نفر):", self.adjustment)
        form.addRow("یادداشت:", self.notes)
        input_layout.addLayout(form)

        self.selected_sources = QLabel("WorldPop: —\nGHSL: —")
        self.selected_sources.setStyleSheet("background:#eef4fb;color:#17345f;padding:10px;border-radius:8px;font-weight:700")
        input_layout.addWidget(self.selected_sources)
        actions = QHBoxLayout()
        self.save_button = QPushButton("ذخیره ورودی‌ها")
        self.save_button.setIcon(get_icon("save", "navy"))
        self.save_button.clicked.connect(self.save_inputs)
        self.calculate_button = QPushButton("محاسبه بلوک")
        self.calculate_button.setIcon(get_icon("check", "white"))
        self.calculate_button.setStyleSheet("background:#17345f;color:white;font-weight:800;padding:9px;border-radius:7px")
        self.calculate_button.clicked.connect(self.calculate_selected)
        for button in (self.save_button, self.calculate_button):
            button.setEnabled(False)
        actions.addWidget(self.save_button)
        actions.addWidget(self.calculate_button)
        input_layout.addLayout(actions)
        self.result_detail = QLabel("پس از محاسبه، روش و درجه اطمینان اینجا نمایش داده می‌شود.")
        self.result_detail.setWordWrap(True)
        self.result_detail.setStyleSheet("color:#42526b;padding-top:8px")
        input_layout.addWidget(self.result_detail)
        input_layout.addStretch()

        splitter.addWidget(table_panel)
        splitter.addWidget(input_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([1020, 400])
        root.addWidget(splitter, 1)

        if not self.can_write:
            self.source_status.setText("حساب فعلی فقط مجاز به مشاهده و خروجی گرفتن از برآوردها است.")

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب داده جمعیتی", "",
            "داده جمعیتی (*.csv *.tsv *.txt *.geojson *.json *.tif *.tiff);;همه فایل‌ها (*.*)",
        )
        if path:
            self.file_path.setText(path)

    def import_source(self):
        path = self.file_path.text().strip()
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "فایل نامعتبر", "ابتدا فایل جمعیتی معتبر را انتخاب کنید.")
            return
        zones = self.db.get_zones()
        if not zones:
            QMessageBox.warning(self, "فاقد بلوک", "ابتدا مرز بلوک‌ها را در بخش بلوک‌بندی ثبت کنید.")
            return
        source_code = self.source_combo.currentData()
        source_title = self.source_combo.currentText()
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.import_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            values = aggregate_population_file(path, zones, self.value_field.text().strip() or None)
            self.db.save_population_source_values(
                source_code, source_title, self.source_year.value(), path, values,
            )
            self.db.calculate_all_population_estimates()
            matched = sum(1 for item in values.values() if item.get("cell_count", 0) > 0)
            QMessageBox.information(
                self, "ثبت منبع جمعیتی",
                f"داده {source_title} برای {to_persian_digits(str(matched))} بلوک محاسبه و ثبت شد.",
            )
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "خطا در پردازش داده", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.setVisible(False)
            self.import_button.setEnabled(self.can_write)

    def refresh_all(self):
        previous = self.selected_zone_id
        estimates = self.db.get_population_estimates()
        self.table.setRowCount(len(estimates))
        total = 0
        selected_row = -1
        for row, item in enumerate(estimates):
            total += int(item.get("final_population") or 0)
            values = [
                item.get("zone_name"), _fa(item.get("worldpop_population")), _fa(item.get("ghsl_population")),
                _fa(item.get("housing_population")), _fa(item.get("meter_population")),
                _fa(item.get("final_population")),
                f"{_fa(item.get('minimum_population'))} تا {_fa(item.get('maximum_population'))}",
                _fa(item.get("households")), _fa(item.get("density_per_km2")), item.get("confidence") or "فاقد داده",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignCenter if col else Qt.AlignRight | Qt.AlignVCenter)
                if col == 0:
                    cell.setData(Qt.UserRole, int(item["zone_id"]))
                self.table.setItem(row, col, cell)
            if previous == item.get("zone_id"):
                selected_row = row
        self.summary_label.setText(f"جمعیت کل برآوردشده بلوک‌ها: {_fa(total)} نفر")
        self._refresh_source_status()
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        elif estimates:
            self.table.selectRow(0)

    def _refresh_source_status(self):
        statuses = {item["source_code"]: item for item in self.db.get_population_source_status()}
        parts = []
        for code, title in (("worldpop", "WorldPop"), ("ghsl", "GHSL")):
            item = statuses.get(code)
            if item:
                parts.append(
                    f"{title} {to_persian_digits(str(item.get('source_year') or ''))}: "
                    f"{_fa(item.get('zones_count'))} بلوک، {_fa(item.get('cell_count'))} سلول"
                )
            else:
                parts.append(f"{title}: وارد نشده")
        self.source_status.setText(" | ".join(parts))

    def load_selected_zone(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        zone_id = self.table.item(rows[0].row(), 0).data(Qt.UserRole)
        self.selected_zone_id = int(zone_id)
        zone = self.db.get_zone(zone_id)
        inputs = self.db.get_population_zone_inputs(zone_id)
        sources = self.db.get_population_source_values(zone_id)
        estimate = self.db.get_population_estimate(zone_id)
        self.zone_title.setText(zone.get("name") or "بلوک")
        self.buildings.setValue(int(inputs.get("residential_buildings") or 0))
        self.units.setValue(int(inputs.get("residential_units") or 0))
        self.occupied_units.setValue(int(inputs.get("occupied_units") or 0))
        self.occupancy_rate.setValue(float(inputs.get("occupancy_rate") or 0.90) * 100)
        self.household_size.setValue(float(inputs.get("household_size") or 3.3))
        self.active_meters.setValue(int(inputs.get("active_meters") or 0))
        self.adjustment.setValue(int(inputs.get("adjustment") or 0))
        self.notes.setPlainText(inputs.get("notes") or "")
        wp = (sources.get("worldpop") or {}).get("population_value", 0)
        gh = (sources.get("ghsl") or {}).get("population_value", 0)
        self.selected_sources.setText(f"WorldPop: {_fa(wp)} نفر\nGHSL: {_fa(gh)} نفر")
        if estimate:
            self.result_detail.setText(
                f"جمعیت نهایی: {_fa(estimate.get('final_population'))} نفر | "
                f"بازه: {_fa(estimate.get('minimum_population'))} تا {_fa(estimate.get('maximum_population'))} | "
                f"اطمینان: {estimate.get('confidence')}\n{estimate.get('method_summary') or ''}"
            )
        else:
            self.result_detail.setText("برای این بلوک هنوز محاسبه‌ای ثبت نشده است.")
        self.save_button.setEnabled(self.can_write)
        self.calculate_button.setEnabled(self.can_write)

    def save_inputs(self, show_message=True):
        if not self.selected_zone_id:
            return False
        self.db.save_population_zone_inputs(
            self.selected_zone_id,
            residential_buildings=self.buildings.value(),
            residential_units=self.units.value(),
            occupied_units=self.occupied_units.value(),
            occupancy_rate=self.occupancy_rate.value() / 100.0,
            household_size=self.household_size.value(),
            active_meters=self.active_meters.value(),
            adjustment=self.adjustment.value(),
            notes=self.notes.toPlainText(),
        )
        if show_message:
            QMessageBox.information(self, "ذخیره شد", "ورودی‌های برآورد جمعیت بلوک ذخیره شد.")
        return True

    def calculate_selected(self):
        if not self.selected_zone_id:
            return
        try:
            self.save_inputs(show_message=False)
            self.db.calculate_population_estimate(self.selected_zone_id)
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "خطای محاسبه", str(exc))

    def calculate_all(self):
        if not self.can_write:
            return
        answer = QMessageBox.question(
            self, "محاسبه همه بلوک‌ها",
            "برآورد همه بلوک‌ها با آخرین منابع و ورودی‌های ثبت‌شده دوباره محاسبه شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if self.selected_zone_id:
                self.save_inputs(show_message=False)
            self.db.calculate_all_population_estimates()
            self.refresh_all()
            QMessageBox.information(self, "پایان محاسبه", "برآورد جمعیت همه بلوک‌ها به‌روزرسانی شد.")
        except Exception as exc:
            QMessageBox.critical(self, "خطای محاسبه", str(exc))
        finally:
            QApplication.restoreOverrideCursor()

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش جمعیت", "population_estimates.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            rows = self.db.get_population_estimates()
            with open(path, "w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow([
                    "نام بلوک", "مساحت مترمربع", "WorldPop", "GHSL", "برآورد مسکونی", "برآورد کنتور",
                    "جمعیت نهایی", "حداقل", "حداکثر", "خانوار", "تراکم نفر در کیلومترمربع",
                    "سطح اطمینان", "تعداد منابع", "روش", "تاریخ محاسبه",
                ])
                for row in rows:
                    writer.writerow([
                        row.get("zone_name"), row.get("area_m2"), row.get("worldpop_population"),
                        row.get("ghsl_population"), row.get("housing_population"), row.get("meter_population"),
                        row.get("final_population"), row.get("minimum_population"), row.get("maximum_population"),
                        row.get("households"), row.get("density_per_km2"), row.get("confidence"),
                        row.get("source_count"), row.get("method_summary"), row.get("calculated_at"),
                    ])
            QMessageBox.information(self, "خروجی آماده شد", "فایل CSV برآورد جمعیت ذخیره شد.")
        except Exception as exc:
            QMessageBox.critical(self, "خطای خروجی", str(exc))
