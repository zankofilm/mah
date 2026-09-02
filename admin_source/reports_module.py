# -*- coding: utf-8 -*-
"""
ماژول گزارش‌گیری: تولید گزارش‌های مختلف بر اساس داده‌های سامانه،
با خروجی PDF و Excel.
"""

import os
from runtime_paths import get_reports_dir, get_temp_dir
import subprocess
import sys
import tempfile
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QRadioButton,
    QButtonGroup
)
from PyQt5.QtCore import pyqtSignal

from header_widget import build_official_header
from ui_scroll import scroll_page
from report_generator import (
    generate_overview_report_pdf, generate_overview_report_excel,
    generate_zone_full_report_pdf, generate_zone_full_report_excel,
    generate_members_report_pdf, generate_members_report_excel,
    generate_requests_report_pdf, generate_requests_report_excel,
    generate_actions_report_pdf, generate_actions_report_excel,
    generate_block_full_report_pdf, generate_block_full_report_excel,
    generate_overview_report_pptx, generate_zone_full_report_pptx,
    generate_members_report_pptx, generate_requests_report_pptx,
    generate_actions_report_pptx, generate_block_full_report_pptx,
    generate_block_public_report_pdf,
    generate_correspondence_report_pdf, generate_correspondence_report_excel,
    generate_correspondence_report_pptx, fonts_missing,
)
from report_preview_html import (
    build_overview_report_preview_html, build_members_report_preview_html,
    build_requests_report_preview_html, build_actions_report_preview_html,
    build_zone_full_report_preview_html, build_correspondence_report_preview_html,
)
from block_report_preview import build_block_full_report_preview_html
from block_public_report_preview import build_block_public_report_preview_html
from map_screenshot import capture_zone_map_screenshot
from zone_snapshot_service import export_zone_snapshot_png
from report_preview_dialog import ReportPreviewDialog, make_temp_pdf_path
from project_control_reports import (
    export_project_control_pdf, export_project_control_excel,
    export_project_control_powerpoint, build_project_control_preview_html,
)
from contracts_satisfaction_reports import (
    export_contract_management_pdf, export_contract_management_excel,
    export_contract_management_powerpoint, build_contract_management_preview_html,
)

REPORTS_OUTPUT_DIR = get_reports_dir()


REPORT_DEFINITIONS = [
    {
        "key": "overview",
        "title": "گزارش کلی وضعیت سامانه",
        "description": "آمار خلاصه کل سامانه: تعداد مناطق، خیابان‌ها، اماکن، اعضا و درخواست‌ها.",
        "needs_zone": False,
    },
    {
        "key": "block_full",
        "title": "⭐ گزارش کامل بلوک (نقشه + جلسات + معتمدین + مشکلات + اقدامات)",
        "description": (
            "گزارش جامع یک بلوک شامل: تصویر نقشه بلوک، محل برگزاری جلسات، نام و شماره تماس "
            "معتمدین، مشکلات بلوک به ترتیب اولویت، و کارهای انجام‌شده."
        ),
        "needs_zone": True,
    },
    {
        "key": "block_public",
        "title": "گزارش عمومی A4 بلوک (نقشه + اعضای معتمد)",
        "description": (
            "خروجی عمومی و تک‌صفحه‌ای A4؛ یک‌چهارم بالای صفحه برای نقشه بلوک و ادامه صفحه "
            "برای جدول معتمدین شامل ردیف، نام و نام خانوادگی، کد ملی، شماره تماس و سمت."
        ),
        "needs_zone": True,
    },
    {
        "key": "zone_full",
        "title": "گزارش کامل یک منطقه/بلوک",
        "description": "نمای گرافیکی ذخیره‌شده بلوک همراه خیابان‌ها، اماکن، اعضا، محل جلسات و درخواست‌ها.",
        "needs_zone": True,
    },
    {
        "key": "members",
        "title": "گزارش اعضای شورای محلات",
        "description": "لیست اعضای شورا برای همه مناطق یا یک منطقه خاص.",
        "needs_zone": "optional",
    },
    {
        "key": "requests",
        "title": "گزارش درخواست‌ها و مشکلات اولویت‌بندی‌شده",
        "description": "لیست درخواست‌ها و مشکلات ثبت‌شده برای همه مناطق یا یک منطقه خاص.",
        "needs_zone": "optional",
    },
    {
        "key": "actions",
        "title": "گزارش اقدامات انجام‌شده",
        "description": "تاریخچه کامل اقدامات پیگیری‌شده برای درخواست‌های همه مناطق یا یک منطقه خاص.",
        "needs_zone": "optional",
    },
    {
        "key": "project_control",
        "title": "گزارش برنامه عملیاتی و کنترل پروژه",
        "description": "داشبورد سبد پروژه، پیشرفت، بودجه، گانت، شاخص‌ها، ریسک‌ها و تغییرات.",
        "needs_zone": "optional",
    },
    {
        "key": "contracts_satisfaction",
        "title": "گزارش قراردادها، پیمانکاران و رضایت مردمی",
        "description": "قرارداد، صورت‌وضعیت، پرداخت، ارزیابی پیمانکار، رضایت مردم و مشارکت محلی.",
        "needs_zone": "optional",
    },
    {
        "key": "correspondence",
        "title": "گزارش مکاتبات و کارتابل اداری",
        "description": "دفتر نامه‌های وارده، صادره و داخلی به‌همراه ارجاعات، مهلت‌ها و وضعیت پیگیری.",
        "needs_zone": "optional",
    },
]

REPORT_GENERATORS = {
    ("overview", "pdf"): lambda db, path, zone_id, map_img=None: generate_overview_report_pdf(db, path),
    ("overview", "excel"): lambda db, path, zone_id, map_img=None: generate_overview_report_excel(db, path),
    ("block_full", "pdf"): lambda db, path, zone_id, map_img=None: generate_block_full_report_pdf(db, zone_id, path, map_image_path=map_img),
    ("block_public", "pdf"): lambda db, path, zone_id, map_img=None: generate_block_public_report_pdf(db, zone_id, path, map_image_path=map_img),
    ("block_full", "excel"): lambda db, path, zone_id, map_img=None: generate_block_full_report_excel(db, zone_id, path, map_image_path=map_img),
    ("zone_full", "pdf"): lambda db, path, zone_id, map_img=None: generate_zone_full_report_pdf(db, zone_id, path),
    ("zone_full", "excel"): lambda db, path, zone_id, map_img=None: generate_zone_full_report_excel(db, zone_id, path),
    ("members", "pdf"): lambda db, path, zone_id, map_img=None: generate_members_report_pdf(db, path, zone_id=zone_id),
    ("members", "excel"): lambda db, path, zone_id, map_img=None: generate_members_report_excel(db, path, zone_id=zone_id),
    ("requests", "pdf"): lambda db, path, zone_id, map_img=None: generate_requests_report_pdf(db, path, zone_id=zone_id),
    ("requests", "excel"): lambda db, path, zone_id, map_img=None: generate_requests_report_excel(db, path, zone_id=zone_id),
    ("actions", "pdf"): lambda db, path, zone_id, map_img=None: generate_actions_report_pdf(db, path, zone_id=zone_id),
    ("actions", "excel"): lambda db, path, zone_id, map_img=None: generate_actions_report_excel(db, path, zone_id=zone_id),
    ("correspondence", "pdf"): lambda db, path, zone_id, map_img=None: generate_correspondence_report_pdf(db, path, zone_id=zone_id),
    ("correspondence", "excel"): lambda db, path, zone_id, map_img=None: generate_correspondence_report_excel(db, path, zone_id=zone_id),
    ("project_control", "pdf"): lambda db, path, zone_id, map_img=None: export_project_control_pdf(db, path, zone_id=zone_id),
    ("project_control", "excel"): lambda db, path, zone_id, map_img=None: export_project_control_excel(db, path, zone_id=zone_id),
    ("project_control", "pptx"): lambda db, path, zone_id, map_img=None: export_project_control_powerpoint(db, path, zone_id=zone_id),
    ("contracts_satisfaction", "pdf"): lambda db, path, zone_id, map_img=None: export_contract_management_pdf(db, path, zone_id=zone_id),
    ("contracts_satisfaction", "excel"): lambda db, path, zone_id, map_img=None: export_contract_management_excel(db, path, zone_id=zone_id),
    ("contracts_satisfaction", "pptx"): lambda db, path, zone_id, map_img=None: export_contract_management_powerpoint(db, path, zone_id=zone_id),
    ("overview", "pptx"): lambda db, path, zone_id, map_img=None: generate_overview_report_pptx(db, path),
    ("block_full", "pptx"): lambda db, path, zone_id, map_img=None: generate_block_full_report_pptx(db, zone_id, path, map_image_path=map_img),
    ("zone_full", "pptx"): lambda db, path, zone_id, map_img=None: generate_zone_full_report_pptx(db, zone_id, path),
    ("members", "pptx"): lambda db, path, zone_id, map_img=None: generate_members_report_pptx(db, path, zone_id=zone_id),
    ("requests", "pptx"): lambda db, path, zone_id, map_img=None: generate_requests_report_pptx(db, path, zone_id=zone_id),
    ("actions", "pptx"): lambda db, path, zone_id, map_img=None: generate_actions_report_pptx(db, path, zone_id=zone_id),
    ("correspondence", "pptx"): lambda db, path, zone_id, map_img=None: generate_correspondence_report_pptx(db, path, zone_id=zone_id),
}

# توابع پیش‌نمایش HTML برای گزارش‌های عمومی (غیر از block_full که پیش‌نمایش
# اختصاصی خودش را با تصویر نقشه در block_report_preview.py دارد)
REPORT_HTML_PREVIEWS = {
    "overview": lambda db, zone_id: build_overview_report_preview_html(db),
    "zone_full": lambda db, zone_id: build_zone_full_report_preview_html(db, zone_id),
    "members": lambda db, zone_id: build_members_report_preview_html(db, zone_id=zone_id),
    "requests": lambda db, zone_id: build_requests_report_preview_html(db, zone_id=zone_id),
    "actions": lambda db, zone_id: build_actions_report_preview_html(db, zone_id=zone_id),
    "correspondence": lambda db, zone_id: build_correspondence_report_preview_html(db, zone_id=zone_id),
    "project_control": lambda db, zone_id: build_project_control_preview_html(db, zone_id=zone_id),
    "contracts_satisfaction": lambda db, zone_id: build_contract_management_preview_html(db, zone_id=zone_id),
}


class ReportsModuleWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("گزارش‌گیری")
        self.resize(1100, 750)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = build_official_header(app_subtitle="گزارش‌گیری", db=self.db)
        outer.addWidget(header)

        body_widget = QWidget()
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(30, 20, 30, 20)
        body.setSpacing(16)

        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_requested.emit)
        body.addWidget(back_btn)

        if fonts_missing():
            warn = QLabel(
                "⚠ فونت فارسی Vazirmatn در پوشه fonts یافت نشد. متن فارسی در PDF ممکن است به‌درستی نمایش داده نشود. "
                "به فایل README برای راهنمای نصب فونت مراجعه کنید. (فایل Excel از این موضوع تأثیر نمی‌پذیرد.)"
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #a4262c; background: #fdecec; padding: 8px; border-radius: 6px;")
            body.addWidget(warn)

        select_group = QGroupBox("انتخاب نوع گزارش")
        form = QFormLayout(select_group)

        self.report_combo = QComboBox()
        for rd in REPORT_DEFINITIONS:
            self.report_combo.addItem(rd["title"], rd["key"])
        self.report_combo.currentIndexChanged.connect(self._on_report_type_changed)
        form.addRow("نوع گزارش:", self.report_combo)

        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("color: #5b6472;")
        form.addRow(self.description_label)

        self.zone_row_label = QLabel("منطقه:")
        self.zone_combo = QComboBox()
        self._reload_zones()
        form.addRow(self.zone_row_label, self.zone_combo)

        format_row = QHBoxLayout()
        self.format_group = QButtonGroup(self)
        self.pdf_radio = QRadioButton("PDF")
        self.pdf_radio.setChecked(True)
        self.excel_radio = QRadioButton("Excel")
        self.pptx_radio = QRadioButton("PowerPoint")
        self.format_group.addButton(self.pdf_radio)
        self.format_group.addButton(self.excel_radio)
        self.format_group.addButton(self.pptx_radio)
        format_row.addWidget(self.pdf_radio)
        format_row.addWidget(self.excel_radio)
        format_row.addWidget(self.pptx_radio)
        format_row.addStretch()
        form.addRow("فرمت خروجی:", format_row)

        body.addWidget(select_group)

        generate_btn = QPushButton("📄 تولید و ذخیره گزارش")
        generate_btn.setProperty("success", True)
        generate_btn.clicked.connect(self._on_generate_clicked)
        body.addWidget(generate_btn)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        body.addWidget(self.status_label)

        body.addStretch()
        outer.addWidget(scroll_page(body_widget, min_height=560), 1)

        self._on_report_type_changed(0)

    def _reload_zones(self):
        self.zone_combo.clear()
        zones = self.db.get_zones()
        self.zone_combo.addItem("همه مناطق", None)
        for z in zones:
            self.zone_combo.addItem(z["name"], z["id"])

    def refresh(self):
        """برای فراخوانی از app.py هنگام بازگشت به این ماژول، تا لیست مناطق به‌روز باشد."""
        self._reload_zones()

    def _on_report_type_changed(self, index):
        key = self.report_combo.currentData()
        rd = next(r for r in REPORT_DEFINITIONS if r["key"] == key)
        self.description_label.setText(rd["description"])

        # گزارش عمومی بلوک فقط PDF است؛ چون چیدمان ثابت A4 دارد.
        pdf_only = key == "block_public"
        self.excel_radio.setEnabled(not pdf_only)
        self.pptx_radio.setEnabled(not pdf_only)
        if pdf_only:
            self.pdf_radio.setChecked(True)

        needs_zone = rd["needs_zone"]
        if needs_zone is False:
            self.zone_row_label.setVisible(False)
            self.zone_combo.setVisible(False)
        else:
            self.zone_row_label.setVisible(True)
            self.zone_combo.setVisible(True)
            if needs_zone is True:
                # حذف گزینه "همه مناطق" برای گزارش‌هایی که حتماً به یک منطقه نیاز دارند
                if self.zone_combo.itemData(0) is None:
                    self.zone_combo.removeItem(0)
            else:
                if self.zone_combo.count() == 0 or self.zone_combo.itemData(0) is not None:
                    self._reload_zones()

    def _on_generate_clicked(self):
        key = self.report_combo.currentData()
        rd = next(r for r in REPORT_DEFINITIONS if r["key"] == key)
        if self.pdf_radio.isChecked():
            fmt = "pdf"
        elif self.excel_radio.isChecked():
            fmt = "excel"
        else:
            fmt = "pptx"
        zone_id = self.zone_combo.currentData() if self.zone_combo.isVisible() else None

        if rd["needs_zone"] is True and zone_id is None:
            QMessageBox.warning(self, "خطا", "لطفاً یک منطقه را انتخاب کنید.")
            return

        zones = self.db.get_zones()
        if rd["needs_zone"] is True and not zones:
            QMessageBox.warning(self, "خطا", "ابتدا در بخش «بلوک‌بندی» یک منطقه بسازید.")
            return

        os.makedirs(REPORTS_OUTPUT_DIR, exist_ok=True)
        ext = "pdf" if fmt == "pdf" else ("xlsx" if fmt == "excel" else "pptx")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"{key}_{timestamp}.{ext}"
        default_path = os.path.join(REPORTS_OUTPUT_DIR, default_filename)

        if fmt == "pdf":
            filter_str = "PDF Files (*.pdf)"
        elif fmt == "excel":
            filter_str = "Excel Files (*.xlsx)"
        else:
            filter_str = "PowerPoint Files (*.pptx)"
        save_path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش", default_path, filter_str)
        if not save_path:
            return

        # استخراج نمای گرافیکی ذخیره‌شده بلوک (فقط برای گزارش «کامل بلوک» لازم است)
        map_image_path = None
        if key in ("block_full", "block_public"):
            self.status_label.setText("در حال آماده‌سازی نمای گرافیکی ذخیره‌شده بلوک ...")
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()
            temp_map_dir = get_temp_dir()
            os.makedirs(temp_map_dir, exist_ok=True)
            candidate_png_path = os.path.join(temp_map_dir, f"report_map_zone_{zone_id}.png")
            try:
                success = export_zone_snapshot_png(self.db, zone_id, candidate_png_path, force_refresh=False)
                # سازگاری اضطراری با دیتابیس‌های بسیار قدیمی؛ در صورت شکست موتور گرافیکی،
                # روش اسکرین‌شات قبلی آخرین راه نجات است.
                if not success:
                    success = capture_zone_map_screenshot(self.db, zone_id, candidate_png_path)
                map_image_path = candidate_png_path if success else None
                if not success:
                    QMessageBox.warning(
                        self, "هشدار",
                        "تهیه نمای گرافیکی بلوک ممکن نشد. "
                        "گزارش بدون تصویر نقشه ساخته می‌شود."
                    )
            except Exception as e:
                QMessageBox.warning(
                    self, "هشدار",
                    f"تهیه تصویر نقشه با خطا مواجه شد و گزارش بدون تصویر نقشه ساخته می‌شود:\n{e}"
                )
                map_image_path = None

        # ساخت پیش‌نمایش پایدار HTML؛ برای PDF، فایل واقعی نیز جداگانه تولید و اعتبارسنجی می‌شود.
        exact_preview_path = None
        try:
            if fmt == "pdf":
                exact_preview_path = make_temp_pdf_path(suffix=key)
                generator_fn = REPORT_GENERATORS[(key, fmt)]
                generator_fn(self.db, exact_preview_path, zone_id, map_image_path)
                if not os.path.exists(exact_preview_path) or os.path.getsize(exact_preview_path) < 100:
                    raise RuntimeError("فایل PDF موقت به‌درستی ساخته نشد.")

            if key == "block_full":
                preview_source = build_block_full_report_preview_html(self.db, zone_id, map_image_path)
            elif key == "block_public":
                preview_source = build_block_public_report_preview_html(self.db, zone_id, map_image_path)
            elif key in REPORT_HTML_PREVIEWS:
                preview_source = REPORT_HTML_PREVIEWS[key](self.db, zone_id)
            else:
                preview_source = "<h1>پیش‌نمایش برای این گزارش در دسترس نیست.</h1>"
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"آماده‌سازی پیش‌نمایش گزارش با خطا مواجه شد:\n{e}")
            return

        def _final_generate():
            generator_fn = REPORT_GENERATORS[(key, fmt)]
            generator_fn(self.db, save_path, zone_id, map_image_path)

        dialog = ReportPreviewDialog(
            fmt=fmt,
            preview_source=preview_source,
            final_generator_fn=_final_generate,
            final_output_path=save_path,
            parent=self,
            exact_preview_path=exact_preview_path,
        )
        dialog.exec_()

        if not dialog.confirmed:
            self.status_label.setText("خروجی گزارش لغو شد (پیش‌نمایش تأیید نشد).")
            return

        self.status_label.setText(f"گزارش با موفقیت ذخیره شد:\n{save_path}")
        reply = QMessageBox.question(
            self, "گزارش آماده شد",
            f"گزارش با موفقیت در مسیر زیر ذخیره شد:\n{save_path}\n\nآیا می‌خواهید اکنون باز شود؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._open_file(save_path)

    def _open_file(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self, "خطا", f"باز کردن فایل ممکن نشد:\n{e}\nمسیر فایل: {path}")
