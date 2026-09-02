# -*- coding: utf-8 -*-
"""رابط حکمرانی داده، حل تعارض و انتشار عمومی — نسخه ۶.۹."""

import json
import os
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QComboBox, QSpinBox, QCheckBox, QTextEdit, QLineEdit, QFileDialog,
    QGroupBox, QFormLayout
)
from header_widget import build_official_header
from jalali_utils import convert_dates_in_text, format_jalali
from icon_manager import set_button_style
from public_portal_service import generate_public_portal


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.setSelectionMode(QTableWidget.SingleSelection)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setAlternatingRowColors(True)
    return table


class DataGovernanceWindow(QMainWindow):
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("حکمرانی داده و همگام‌سازی — سامانه مدیریت محلات جوانرود")
        self.resize(1280, 820)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(build_official_header("حکمرانی داده، حل تعارض و انتشار عمومی", self.db))

        top = QHBoxLayout(); top.setContentsMargins(18, 8, 18, 4)
        title = QLabel("مرکز کنترل کیفیت، محرمانگی و تبادل داده")
        title.setStyleSheet("font-size:16px;font-weight:800;color:#13294b")
        top.addWidget(title); top.addStretch()
        back = QPushButton("بازگشت به داشبورد"); set_button_style(back, "back", "secondary")
        back.clicked.connect(self.back_requested.emit); top.addWidget(back)
        root.addLayout(top)

        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._build_conflicts_tab(); self._build_data_quality_tab(); self._build_policies_tab(); self._build_records_tab(); self._build_portal_tab()

    def _build_conflicts_tab(self):
        page = QWidget(); lay = QVBoxLayout(page)
        info = QLabel("وقتی یک رکورد روی دو دستگاه از یک نسخه مشترک به‌صورت متفاوت ویرایش شود، سامانه آن را خودکار متوقف و برای تصمیم مدیر نمایش می‌دهد.")
        info.setWordWrap(True); lay.addWidget(info)
        self.conflicts_table = _table(["نوع", "شناسه", "بلوک", "نسخه محلی", "نسخه ورودی", "دستگاه", "وضعیت", "زمان"])
        lay.addWidget(self.conflicts_table, 1)
        row = QHBoxLayout()
        local = QPushButton("نگهداری نسخه محلی"); set_button_style(local, "check", "secondary")
        incoming = QPushButton("جایگزینی با نسخه ورودی"); set_button_style(incoming, "download", "primary")
        details = QPushButton("مقایسه جزئیات"); set_button_style(details, "search", "secondary")
        local.clicked.connect(lambda: self._resolve_conflict("نسخه محلی"))
        incoming.clicked.connect(lambda: self._resolve_conflict("نسخه ورودی"))
        details.clicked.connect(self._show_conflict_details)
        row.addWidget(local); row.addWidget(incoming); row.addWidget(details); row.addStretch(); lay.addLayout(row)
        self.tabs.addTab(page, "تعارض‌های همگام‌سازی")

    def _build_data_quality_tab(self):
        page = QWidget(); lay = QVBoxLayout(page)
        info = QLabel(
            "رکوردهای احتمالی تکراری بر اساس شماره همراه یا نام یکسان نمایش داده می‌شوند. "
            "ادغام، ارتباط اعضای شورا و کمیته‌ها را به رکورد مقصد منتقل و رکورد مبدا را به‌صورت نرم حذف می‌کند."
        )
        info.setWordWrap(True); lay.addWidget(info)
        self.duplicate_people_table = _table([
            "شناسه مبدا", "نام مبدا", "کد ملی مبدا", "همراه مبدا",
            "شناسه مقصد", "نام مقصد", "کد ملی مقصد", "همراه مقصد"
        ])
        lay.addWidget(self.duplicate_people_table, 1)
        row = QHBoxLayout()
        refresh = QPushButton("بررسی دوباره"); set_button_style(refresh, "refresh", "secondary")
        refresh.clicked.connect(self._refresh_duplicate_people)
        merge = QPushButton("ادغام مبدا در مقصد"); set_button_style(merge, "check", "primary")
        merge.clicked.connect(self._merge_selected_people)
        row.addWidget(refresh); row.addWidget(merge); row.addStretch(); lay.addLayout(row)
        self.tabs.addTab(page, "کیفیت و رکوردهای تکراری")

    def _build_policies_tab(self):
        page = QWidget(); lay = QHBoxLayout(page)
        self.policies_table = _table(["نوع داده", "عنوان", "طبقه‌بندی", "نگهداری/روز", "تأیید", "انتشار", "داده شخصی"])
        self.policies_table.itemSelectionChanged.connect(self._load_policy)
        lay.addWidget(self.policies_table, 2)
        form_box = QGroupBox("ویرایش خط‌مشی")
        form = QFormLayout(form_box)
        self.policy_entity = QLineEdit(); self.policy_entity.setReadOnly(True)
        self.policy_title = QLineEdit()
        self.policy_class = QComboBox(); self.policy_class.addItems(["عمومی", "داخلی", "محرمانه", "خیلی محرمانه"])
        self.policy_retention = QSpinBox(); self.policy_retention.setRange(0, 36500)
        self.policy_approval = QCheckBox("نیازمند تأیید")
        self.policy_public = QCheckBox("اجازه انتشار عمومی")
        self.policy_personal = QCheckBox("حاوی داده شخصی")
        self.policy_notes = QTextEdit(); self.policy_notes.setMaximumHeight(110)
        for label, w in [("کد نوع داده", self.policy_entity), ("عنوان", self.policy_title), ("طبقه‌بندی", self.policy_class),
                         ("مدت نگهداری", self.policy_retention), ("تأیید", self.policy_approval),
                         ("انتشار", self.policy_public), ("حریم خصوصی", self.policy_personal), ("یادداشت", self.policy_notes)]:
            form.addRow(label, w)
        save = QPushButton("ذخیره خط‌مشی"); set_button_style(save, "save", "primary"); save.clicked.connect(self._save_policy)
        form.addRow(save); lay.addWidget(form_box, 1)
        self.tabs.addTab(page, "خط‌مشی داده")

    def _build_records_tab(self):
        page = QWidget(); lay = QVBoxLayout(page)
        top = QHBoxLayout()
        self.record_type = QComboBox(); self.record_type.addItems(["project", "field_visit", "citizen_request", "contract", "letter", "satisfaction_survey"])
        self.record_uid = QLineEdit(); self.record_uid.setPlaceholderText("شناسه عددی یا UID رکورد")
        self.record_zone = QComboBox(); self.record_zone.addItem("بدون بلوک", None)
        for z in self.db.get_zones(): self.record_zone.addItem(z["name"], z["id"])
        self.record_class = QComboBox(); self.record_class.addItems(["عمومی", "داخلی", "محرمانه", "خیلی محرمانه"])
        self.record_status = QComboBox(); self.record_status.addItems(["پیش‌نویس", "نیازمند بازبینی", "تأییدشده", "منقضی‌شده", "آرشیوشده"])
        self.record_public = QCheckBox("قابل انتشار")
        for label, w in [("نوع", self.record_type), ("شناسه", self.record_uid), ("بلوک", self.record_zone), ("طبقه‌بندی", self.record_class), ("وضعیت", self.record_status)]:
            top.addWidget(QLabel(label)); top.addWidget(w)
        top.addWidget(self.record_public)
        add = QPushButton("ثبت/بروزرسانی"); set_button_style(add, "save", "primary"); add.clicked.connect(self._save_record_governance)
        top.addWidget(add); lay.addLayout(top)
        self.records_table = _table(["نوع", "شناسه", "بلوک", "طبقه‌بندی", "وضعیت", "عمومی", "مالک", "آخرین تغییر"])
        lay.addWidget(self.records_table, 1)
        row = QHBoxLayout()
        approve = QPushButton("تأیید رکورد"); set_button_style(approve, "check", "success"); approve.clicked.connect(lambda: self._approve_record(True))
        reject = QPushButton("نیازمند بازبینی"); set_button_style(reject, "warning", "secondary"); reject.clicked.connect(lambda: self._approve_record(False))
        row.addWidget(approve); row.addWidget(reject); row.addStretch(); lay.addLayout(row)
        self.tabs.addTab(page, "چرخه عمر و انتشار")

    def _build_portal_tab(self):
        page = QWidget(); lay = QVBoxLayout(page)
        note = QLabel("درگاه عمومی فقط آمار تجمیعی و پروژه‌هایی را نمایش می‌دهد که صریحاً «قابل انتشار» و «تأییدشده» باشند. نام، تلفن، متن نامه و داده محرمانه هرگز وارد خروجی نمی‌شود.")
        note.setWordWrap(True); note.setStyleSheet("background:#fff8dc;border-right:5px solid #c9a227;padding:12px")
        lay.addWidget(note)
        row = QHBoxLayout()
        export = QPushButton("ساخت درگاه عمومی آفلاین"); set_button_style(export, "report", "primary"); export.clicked.connect(self._export_portal)
        retention = QPushButton("بررسی سررسید نگهداری داده"); set_button_style(retention, "warning", "secondary"); retention.clicked.connect(self._show_retention_alerts)
        row.addWidget(export); row.addWidget(retention); row.addStretch(); lay.addLayout(row)
        self.portal_status = QLabel("هنوز خروجی عمومی ساخته نشده است."); self.portal_status.setWordWrap(True); lay.addWidget(self.portal_status)
        self.publications_table = _table(["عنوان", "مسیر", "بلوک", "پروژه", "درخواست تجمیعی", "تاریخ", "وضعیت"])
        lay.addWidget(self.publications_table, 1)
        self.tabs.addTab(page, "درگاه عمومی و نگهداری")

    def _selected_id(self, table):
        row = table.currentRow()
        if row < 0 or not table.item(row, 0): return None
        return table.item(row, 0).data(Qt.UserRole)

    def refresh_all(self):
        self._refresh_conflicts(); self._refresh_duplicate_people(); self._refresh_policies(); self._refresh_records(); self._refresh_publications()

    def _refresh_duplicate_people(self):
        if not hasattr(self, "duplicate_people_table"):
            return
        rows = self.db.find_possible_duplicate_people()
        self.duplicate_people_table.setRowCount(len(rows))
        for r, item in enumerate(rows):
            values = [item.get("source_id"), item.get("source_name"), item.get("source_national_code"), item.get("source_mobile"),
                      item.get("target_id"), item.get("target_name"), item.get("target_national_code"), item.get("target_mobile")]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(str(value or "—"))
                if c == 0:
                    cell.setData(Qt.UserRole, (item.get("source_id"), item.get("target_id")))
                self.duplicate_people_table.setItem(r, c, cell)

    def _merge_selected_people(self):
        row = self.duplicate_people_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "انتخاب رکورد", "ابتدا یک جفت رکورد را انتخاب کنید.")
            return
        pair = self.duplicate_people_table.item(row, 0).data(Qt.UserRole)
        if not pair:
            return
        if QMessageBox.question(
            self, "تأیید ادغام", "رکورد مبدا در رکورد مقصد ادغام و به‌صورت نرم حذف شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            self.db.merge_people(pair[0], pair[1])
        except Exception as exc:
            QMessageBox.critical(self, "خطا در ادغام", str(exc))
            return
        self._refresh_duplicate_people()
        QMessageBox.information(self, "ادغام انجام شد", "ارتباط‌ها منتقل و سابقه ادغام ثبت شد.")

    def _refresh_conflicts(self):
        rows = self.db.get_sync_conflicts()
        self.conflicts_table.setRowCount(len(rows))
        for r, x in enumerate(rows):
            zone = self.db.get_zone(x.get("zone_id")) if x.get("zone_id") else None
            vals = [x.get("entity_type"), x.get("entity_uid"), (zone or {}).get("name") or "—",
                    x.get("local_version"), x.get("incoming_version"), x.get("source_device") or "—",
                    x.get("status"), x.get("created_at")]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(convert_dates_in_text(str(v or "—")))
                if c == 0: item.setData(Qt.UserRole, x["id"])
                self.conflicts_table.setItem(r, c, item)

    def _resolve_conflict(self, choice):
        cid = self._selected_id(self.conflicts_table)
        if not cid: QMessageBox.information(self, "انتخاب تعارض", "ابتدا یک تعارض را انتخاب کنید."); return
        if QMessageBox.question(self, "تصمیم تعارض", f"تصمیم «{choice}» اعمال شود؟") != QMessageBox.Yes: return
        self.db.resolve_sync_conflict(cid, choice); self.refresh_all()

    def _show_conflict_details(self):
        cid = self._selected_id(self.conflicts_table)
        item = next((x for x in self.db.get_sync_conflicts() if x["id"] == cid), None)
        if not item: return
        text = "نسخه محلی:\n" + json.dumps(item.get("local_payload") or {}, ensure_ascii=False, indent=2)
        text += "\n\nنسخه ورودی:\n" + json.dumps(item.get("incoming_payload") or {}, ensure_ascii=False, indent=2)
        box = QMessageBox(self); box.setWindowTitle("مقایسه تعارض"); box.setText("جزئیات دو نسخه"); box.setDetailedText(text); box.exec_()

    def _refresh_policies(self):
        rows = self.db.get_governance_policies(); self.policies_table.setRowCount(len(rows))
        for r, x in enumerate(rows):
            vals = [x["entity_type"], x["title"], x["classification"], x["retention_days"],
                    "بله" if x["requires_approval"] else "خیر", "بله" if x["public_allowed"] else "خیر",
                    "بله" if x["contains_personal_data"] else "خیر"]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(convert_dates_in_text(str(v)));
                if c == 0: item.setData(Qt.UserRole, x["entity_type"])
                self.policies_table.setItem(r, c, item)

    def _load_policy(self):
        row = self.policies_table.currentRow()
        if row < 0: return
        entity = self.policies_table.item(row, 0).data(Qt.UserRole)
        x = next((p for p in self.db.get_governance_policies() if p["entity_type"] == entity), None)
        if not x: return
        self.policy_entity.setText(x["entity_type"]); self.policy_title.setText(x["title"])
        self.policy_class.setCurrentText(x["classification"]); self.policy_retention.setValue(int(x["retention_days"] or 0))
        self.policy_approval.setChecked(bool(x["requires_approval"])); self.policy_public.setChecked(bool(x["public_allowed"]))
        self.policy_personal.setChecked(bool(x["contains_personal_data"])); self.policy_notes.setPlainText(x.get("notes") or "")

    def _save_policy(self):
        entity = self.policy_entity.text().strip()
        if not entity: QMessageBox.information(self, "انتخاب خط‌مشی", "یک خط‌مشی را انتخاب کنید."); return
        if self.policy_personal.isChecked() and self.policy_public.isChecked():
            QMessageBox.warning(self, "مغایرت حریم خصوصی", "داده شخصی نمی‌تواند مستقیماً عمومی شود."); return
        self.db.update_governance_policy(entity, title=self.policy_title.text(), classification=self.policy_class.currentText(),
            retention_days=self.policy_retention.value(), requires_approval=self.policy_approval.isChecked(),
            public_allowed=self.policy_public.isChecked(), contains_personal_data=self.policy_personal.isChecked(),
            notes=self.policy_notes.toPlainText())
        self.refresh_all()

    def _save_record_governance(self):
        uid = self.record_uid.text().strip()
        if not uid: QMessageBox.warning(self, "اطلاعات ناقص", "شناسه رکورد را وارد کنید."); return
        if self.record_public.isChecked() and self.record_class.currentText() in ("محرمانه", "خیلی محرمانه"):
            QMessageBox.warning(self, "مغایرت انتشار", "رکورد محرمانه قابل انتشار عمومی نیست."); return
        user = self.db.get_current_user() or {}
        self.db.set_record_governance(self.record_type.currentText(), uid, zone_id=self.record_zone.currentData(),
            classification=self.record_class.currentText(), lifecycle_status=self.record_status.currentText(),
            data_owner=user.get("full_name") or user.get("username") or "", is_public=self.record_public.isChecked())
        self.record_uid.clear(); self.refresh_all()

    def _refresh_records(self):
        rows = self.db.list_record_governance(); self.records_table.setRowCount(len(rows))
        for r, x in enumerate(rows):
            zone = self.db.get_zone(x.get("zone_id")) if x.get("zone_id") else None
            vals = [x["entity_type"], x["entity_uid"], (zone or {}).get("name") or "—", x["classification"],
                    x["lifecycle_status"], "بله" if x["is_public"] else "خیر", x.get("data_owner") or "—", x.get("updated_at")]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(convert_dates_in_text(str(v or "—")))
                if c == 0: item.setData(Qt.UserRole, x["id"])
                self.records_table.setItem(r, c, item)

    def _approve_record(self, approve):
        gid = self._selected_id(self.records_table)
        if not gid: QMessageBox.information(self, "انتخاب رکورد", "یک رکورد را انتخاب کنید."); return
        self.db.approve_record_governance(gid, approve); self.refresh_all()

    def _export_portal(self):
        directory = QFileDialog.getExistingDirectory(self, "انتخاب پوشه خروجی درگاه عمومی")
        if not directory: return
        try:
            result = generate_public_portal(self.db, os.path.join(directory, "javanrood_public_portal"))
            self.portal_status.setText(f"خروجی ساخته شد: {result['html_path']}")
            QMessageBox.information(self, "درگاه عمومی", "خروجی عمومی با موفقیت ساخته شد. فایل index.html را باز کنید.")
            self.refresh_all()
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))

    def _show_retention_alerts(self):
        rows = self.db.get_retention_alerts(30)
        if not rows: QMessageBox.information(self, "نگهداری داده", "هیچ رکوردی در ۳۰ روز آینده منقضی نمی‌شود."); return
        text = "\n".join(f"{x['entity_type']} / {x['entity_uid']} — {x['days_remaining']} روز" for x in rows[:100])
        QMessageBox.warning(self, "سررسید نگهداری داده", text)

    def _refresh_publications(self):
        rows = self.db.get_publications(); self.publications_table.setRowCount(len(rows))
        for r, x in enumerate(rows):
            vals = [x["title"], x["output_path"], x["zones_count"], x["projects_count"], x["requests_count"], x["generated_at"], x["status"]]
            for c, v in enumerate(vals): self.publications_table.setItem(r, c, QTableWidgetItem(convert_dates_in_text(str(v or "—"))))
