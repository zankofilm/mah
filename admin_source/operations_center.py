# -*- coding: utf-8 -*-
"""مرکز عملیات: پیگیری مصوبات، کارتابل، پرونده بلوک، اسناد و ارزیابی عملکرد."""
from __future__ import annotations

import csv
import html
import os
from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QTextBrowser, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QFileDialog, QTabWidget,
    QGroupBox, QFormLayout, QSplitter, QFrame, QCheckBox, QInputDialog,
)

from header_widget import build_official_header
from ui_scroll import scroll_page
from jalali_widgets import JalaliDateEdit
from jalali_utils import format_jalali, to_persian_digits
from runtime_paths import get_data_dir
from icon_manager import get_icon


CLOSED = {"تکمیل‌شده", "مختومه", "لغوشده"}
STATUSES = ["جدید", "در حال بررسی", "مصوب", "ارجاع‌شده", "در حال اجرا", "متوقف", "معوق", "تکمیل‌شده", "مختومه", "لغوشده"]
PRIORITIES = ["عادی", "مهم", "فوری", "بحرانی"]


def _item(value, align=Qt.AlignCenter):
    cell = QTableWidgetItem(str(value if value not in (None, "") else "—"))
    cell.setTextAlignment(align)
    return cell


def _status_color(status):
    if status in CLOSED:
        return "#256029"
    if status in {"معوق", "متوقف"}:
        return "#a4262c"
    if status in {"در حال اجرا", "ارجاع‌شده"}:
        return "#9a6700"
    return "#164f8c"


class StatCard(QFrame):
    def __init__(self, title, icon="report", parent=None):
        super().__init__(parent)
        self.setObjectName("OperationsStatCard")
        self.setStyleSheet("QFrame#OperationsStatCard{background:white;border:1px solid #d8dee8;border-radius:12px;}")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 12, 14, 12)
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_icon(icon, "navy").pixmap(28, 28))
        row.addWidget(icon_lbl)
        col = QVBoxLayout()
        self.value = QLabel("۰")
        self.value.setStyleSheet("font-size:22px;font-weight:900;color:#13294b;")
        self.value.setAlignment(Qt.AlignCenter)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("color:#5b6472;font-weight:700;")
        title_lbl.setAlignment(Qt.AlignCenter)
        col.addWidget(self.value)
        col.addWidget(title_lbl)
        row.addLayout(col, 1)

    def set_value(self, value):
        self.value.setText(to_persian_digits(value or 0))


class OperationsCenterWindow(QWidget):
    back_requested = pyqtSignal()
    open_production_center_requested = pyqtSignal()

    def __init__(self, db, current_user=None):
        super().__init__()
        self.db = db
        self.current_user = current_user or db.get_current_user() or {}
        self.selected_case_id = None
        self.setWindowTitle("مرکز عملیات و پیگیری محله‌محور")
        self.resize(1480, 900)
        self.setLayoutDirection(Qt.RightToLeft)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(build_official_header("مرکز عملیات، کارتابل و ارزیابی عملکرد", self.db))

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 14, 22, 22)
        layout.setSpacing(10)
        top = QHBoxLayout()
        back = QPushButton("‹ بازگشت به داشبورد")
        back.setIcon(get_icon("back", "navy"))
        back.clicked.connect(self.back_requested.emit)
        top.addWidget(back)
        top.addStretch()
        refresh = QPushButton("تازه‌سازی همه بخش‌ها")
        refresh.setIcon(get_icon("refresh", "navy"))
        refresh.clicked.connect(self.refresh_all)
        top.addWidget(refresh)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_overview_tab(), get_icon("home", "navy"), "نمای مدیریتی")
        self.tabs.addTab(self._build_tracking_tab(), get_icon("check", "navy"), "پیگیری مصوبات و اقدامات")
        self.tabs.addTab(self._build_inbox_tab(), get_icon("mail", "navy"), "کارتابل و ارجاع")
        self.tabs.addTab(self._build_dossier_tab(), get_icon("city", "navy"), "پرونده جامع بلوک")
        self.tabs.addTab(self._build_documents_tab(), get_icon("attachment", "navy"), "اسناد و پیوست‌ها")
        self.tabs.addTab(self._build_performance_tab(), get_icon("report", "navy"), "عملکرد ادارات و بلوک‌ها")
        self.tabs.addTab(self._build_backup_tab(), get_icon("database", "navy"), "پایداری و استقرار")
        layout.addWidget(self.tabs, 1)
        root.addWidget(body, 1)

    def _build_overview_tab(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        cards = QGridLayout()
        specs = [
            ("total", "کل پرونده‌ها", "list"),
            ("open", "پرونده‌های باز", "report"),
            ("overdue", "پرونده‌های معوق", "warning"),
            ("due_soon", "سررسید هفت روز آینده", "calendar"),
            ("open_assignments", "ارجاعات باز", "mail"),
            ("average_progress", "میانگین پیشرفت", "check"),
        ]
        self.overview_cards = {}
        for i, (key, title, icon) in enumerate(specs):
            card = StatCard(title, icon)
            self.overview_cards[key] = card
            cards.addWidget(card, i // 3, i % 3)
        lay.addLayout(cards)
        note = QLabel("چرخه استاندارد: ثبت مسئله ← بررسی کمیته ← تصویب ← ارجاع به دستگاه ← اقدام ← ثبت نتیجه ← مختومه")
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("background:#eef4fb;border:1px solid #cddbeb;border-radius:10px;padding:14px;font-weight:800;color:#13294b;")
        lay.addWidget(note)
        self.overdue_table = self._table(["شناسه", "بلوک", "عنوان", "دستگاه مسئول", "مهلت", "پیشرفت", "وضعیت"])
        lay.addWidget(QLabel("پرونده‌های نیازمند اقدام فوری"))
        lay.addWidget(self.overdue_table, 1)
        return page

    def _build_tracking_tab(self):
        page = QWidget()
        root = QVBoxLayout(page)
        filters = QHBoxLayout()
        self.case_zone_filter = QComboBox(); self.case_zone_filter.currentIndexChanged.connect(self.refresh_cases)
        self.case_status_filter = QComboBox(); self.case_status_filter.addItem("همه وضعیت‌ها", None)
        for s in STATUSES: self.case_status_filter.addItem(s, s)
        self.case_status_filter.currentIndexChanged.connect(self.refresh_cases)
        self.case_query = QLineEdit(); self.case_query.setPlaceholderText("جستجو در عنوان، دستگاه یا مسئول...")
        self.case_query.returnPressed.connect(self.refresh_cases)
        sync = QPushButton("همگام‌سازی مصوبات و اقدامات قبلی"); sync.clicked.connect(self.sync_cases)
        filters.addWidget(QLabel("بلوک:")); filters.addWidget(self.case_zone_filter)
        filters.addWidget(QLabel("وضعیت:")); filters.addWidget(self.case_status_filter)
        filters.addWidget(self.case_query, 1); filters.addWidget(sync)
        root.addLayout(filters)

        splitter = QSplitter(Qt.Horizontal)
        self.case_table = self._table(["شناسه", "بلوک", "کمیته", "عنوان", "دستگاه", "مسئول", "مهلت", "٪", "وضعیت"])
        self.case_table.itemSelectionChanged.connect(self.load_selected_case)
        splitter.addWidget(self.case_table)

        form_box = QGroupBox("ثبت یا ویرایش پرونده پیگیری")
        form = QFormLayout(form_box)
        self.case_title = QLineEdit()
        self.case_description = QTextEdit(); self.case_description.setFixedHeight(72)
        self.case_zone = QComboBox(); self.case_zone.currentIndexChanged.connect(self.refresh_committee_combo)
        self.case_committee = QComboBox()
        self.case_agency = QComboBox(); self.case_agency.setEditable(True)
        self.case_person = QLineEdit()
        self.case_priority = QComboBox(); self.case_priority.addItems(PRIORITIES)
        self.case_status = QComboBox(); self.case_status.addItems(STATUSES)
        self.case_due = JalaliDateEdit(); self.case_progress = QSpinBox(); self.case_progress.setRange(0, 100); self.case_progress.setSuffix("٪")
        self.case_delay = QLineEdit(); self.case_result = QTextEdit(); self.case_result.setFixedHeight(64)
        form.addRow("عنوان:", self.case_title); form.addRow("شرح:", self.case_description)
        form.addRow("بلوک:", self.case_zone); form.addRow("کمیته:", self.case_committee)
        form.addRow("دستگاه مسئول:", self.case_agency); form.addRow("مسئول پیگیری:", self.case_person)
        form.addRow("اولویت:", self.case_priority); form.addRow("وضعیت:", self.case_status)
        form.addRow("مهلت اجرا:", self.case_due); form.addRow("درصد پیشرفت:", self.case_progress)
        form.addRow("علت تأخیر:", self.case_delay); form.addRow("نتیجه نهایی:", self.case_result)
        buttons = QHBoxLayout()
        new_btn = QPushButton("پرونده جدید"); new_btn.clicked.connect(self.clear_case_form)
        save_btn = QPushButton("ذخیره پرونده"); save_btn.setProperty("uiRole", "primary"); save_btn.clicked.connect(self.save_case)
        update_btn = QPushButton("ثبت گزارش پیشرفت"); update_btn.clicked.connect(self.add_progress_update)
        complete_btn = QPushButton("تکمیل پرونده"); complete_btn.setProperty("uiRole", "success"); complete_btn.clicked.connect(self.complete_case)
        buttons.addWidget(new_btn); buttons.addWidget(save_btn); buttons.addWidget(update_btn); buttons.addWidget(complete_btn)
        form.addRow(buttons)
        splitter.addWidget(form_box)
        splitter.setSizes([930, 470])
        root.addWidget(splitter, 1)
        return page

    def _build_inbox_tab(self):
        page = QWidget(); root = QVBoxLayout(page)
        create = QGroupBox("ارجاع پرونده")
        grid = QGridLayout(create)
        self.assign_case = QComboBox(); self.assign_user = QComboBox(); self.assign_agency = QComboBox(); self.assign_agency.setEditable(True)
        self.assign_instruction = QLineEdit(); self.assign_due = JalaliDateEdit(); self.assign_priority = QComboBox(); self.assign_priority.addItems(PRIORITIES)
        send = QPushButton("ارسال به کارتابل"); send.setProperty("uiRole", "primary"); send.clicked.connect(self.create_assignment)
        grid.addWidget(QLabel("پرونده:"),0,0); grid.addWidget(self.assign_case,0,1,1,3)
        grid.addWidget(QLabel("کاربر:"),1,0); grid.addWidget(self.assign_user,1,1)
        grid.addWidget(QLabel("دستگاه:"),1,2); grid.addWidget(self.assign_agency,1,3)
        grid.addWidget(QLabel("دستور:"),2,0); grid.addWidget(self.assign_instruction,2,1,1,3)
        grid.addWidget(QLabel("مهلت:"),3,0); grid.addWidget(self.assign_due,3,1)
        grid.addWidget(QLabel("اولویت:"),3,2); grid.addWidget(self.assign_priority,3,3)
        grid.addWidget(send,4,3)
        root.addWidget(create)
        toolbar = QHBoxLayout()
        self.only_my_assignments = QCheckBox("فقط کارتابل من")
        self.only_my_assignments.setChecked(True)
        self.only_my_assignments.stateChanged.connect(self.refresh_assignments)
        toolbar.addWidget(self.only_my_assignments); toolbar.addStretch()
        viewed = QPushButton("علامت‌گذاری به‌عنوان دیده‌شده"); viewed.clicked.connect(self.mark_assignment_viewed)
        respond = QPushButton("ثبت پاسخ و بستن ارجاع"); respond.setProperty("uiRole", "success"); respond.clicked.connect(self.respond_assignment)
        toolbar.addWidget(viewed); toolbar.addWidget(respond)
        root.addLayout(toolbar)
        self.assignment_table = self._table(["شناسه", "پرونده", "بلوک", "گیرنده", "دستگاه", "دستور", "مهلت", "اولویت", "وضعیت"])
        root.addWidget(self.assignment_table, 1)
        return page

    def _build_dossier_tab(self):
        page = QWidget(); root = QVBoxLayout(page)
        top=QHBoxLayout(); self.dossier_zone=QComboBox(); self.dossier_zone.currentIndexChanged.connect(self.refresh_dossier)
        export_html=QPushButton("خروجی HTML پرونده"); export_html.clicked.connect(self.export_dossier_html)
        export_csv=QPushButton("خروجی CSV خلاصه"); export_csv.clicked.connect(self.export_dossier_csv)
        top.addWidget(QLabel("بلوک:")); top.addWidget(self.dossier_zone); top.addStretch(); top.addWidget(export_csv); top.addWidget(export_html)
        root.addLayout(top)
        self.dossier_view=QTextBrowser(); self.dossier_view.setOpenExternalLinks(True)
        root.addWidget(self.dossier_view,1)
        return page

    def _build_documents_tab(self):
        page=QWidget(); root=QVBoxLayout(page)
        top=QHBoxLayout(); self.document_case=QComboBox(); self.document_description=QLineEdit(); self.document_description.setPlaceholderText("توضیح سند")
        add=QPushButton("افزودن فایل به پرونده"); add.clicked.connect(self.add_attachment)
        open_btn=QPushButton("بازکردن فایل"); open_btn.clicked.connect(self.open_attachment)
        delete_btn=QPushButton("حذف فایل"); delete_btn.setProperty("uiRole","danger"); delete_btn.clicked.connect(self.delete_attachment)
        top.addWidget(QLabel("پرونده:")); top.addWidget(self.document_case,1); top.addWidget(self.document_description,1); top.addWidget(add); top.addWidget(open_btn); top.addWidget(delete_btn)
        root.addLayout(top)
        self.attachment_table=self._table(["شناسه","نوع پرونده","شماره پرونده","نام فایل","نوع","حجم","توضیح","ثبت‌کننده","تاریخ"])
        root.addWidget(self.attachment_table,1)
        return page

    def _build_performance_tab(self):
        page=QWidget(); root=QVBoxLayout(page)
        splitter=QSplitter(Qt.Horizontal)
        agency=QGroupBox("عملکرد دستگاه‌ها"); al=QVBoxLayout(agency)
        self.agency_perf_table=self._table(["رتبه","دستگاه","کل","تکمیل","معوق","میانگین پیشرفت"]); al.addWidget(self.agency_perf_table)
        zone=QGroupBox("عملکرد بلوک‌ها"); zl=QVBoxLayout(zone)
        self.zone_perf_table=self._table(["رتبه","بلوک","کل","تکمیل","معوق","میانگین پیشرفت"]); zl.addWidget(self.zone_perf_table)
        splitter.addWidget(agency); splitter.addWidget(zone); splitter.setSizes([700,700])
        root.addWidget(splitter,1)
        return page

    def _build_backup_tab(self):
        page=QWidget(); root=QVBoxLayout(page)
        info=QLabel("پیش از هر ارتقا، سامانه بکاپ مهاجرتی می‌سازد. بکاپ روزانه نیز هنگام شروع برنامه کنترل می‌شود. نسخه نصب ویندوز از build_windows.bat و فایل Inno Setup داخل پوشه installer ساخته می‌شود.")
        info.setWordWrap(True); info.setStyleSheet("background:#eef4fb;border:1px solid #cddbeb;border-radius:10px;padding:14px;")
        root.addWidget(info)
        actions=QHBoxLayout()
        backup=QPushButton("ساخت بکاپ فوری"); backup.setProperty("uiRole","success"); backup.clicked.connect(self.create_backup)
        folder=QPushButton("بازکردن پوشه داده و بکاپ"); folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(get_data_dir())))
        health=QPushButton("ورود به مرکز سلامت و بازیابی"); health.clicked.connect(self.open_production_center_requested.emit)
        guide=QPushButton("بازکردن راهنمای ساخت نسخه ویندوز"); guide.clicked.connect(self.open_build_guide)
        actions.addWidget(backup); actions.addWidget(folder); actions.addWidget(health); actions.addWidget(guide)
        root.addLayout(actions)
        self.backup_table=self._table(["شناسه","مسیر","نوع","علت","حجم","وضعیت","تاریخ"])
        root.addWidget(self.backup_table,1)
        return page

    @staticmethod
    def _table(headers):
        table=QTableWidget(0,len(headers)); table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectRows); table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers); table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        if headers: table.horizontalHeader().setSectionResizeMode(min(len(headers)-1,3), QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        return table

    def _load_zones(self):
        zones=self.db.get_zones()
        for combo in (self.case_zone_filter,self.case_zone,self.dossier_zone):
            current=combo.currentData(); combo.blockSignals(True); combo.clear()
            if combo is self.case_zone_filter: combo.addItem("همه بلوک‌ها",None)
            for z in zones: combo.addItem(z.get("name") or f"بلوک {z.get('id')}",z.get("id"))
            idx=combo.findData(current); combo.setCurrentIndex(idx if idx>=0 else (1 if combo is self.case_zone_filter and combo.count()>1 else 0)); combo.blockSignals(False)
        self.refresh_committee_combo()

    def _load_agencies_users(self):
        agencies=[a.get("name") for a in self.db.get_management_agencies(active_only=True)]
        for combo in (self.case_agency,self.assign_agency):
            current=combo.currentText(); combo.clear(); combo.addItems([a for a in agencies if a]); combo.setEditText(current)
        self.assign_user.clear(); self.assign_user.addItem("بدون کاربر مشخص",None)
        for user in self.db.list_users(include_inactive=False): self.assign_user.addItem(user.get("full_name") or user.get("username"),user.get("id"))

    def refresh_committee_combo(self):
        zone_id=self.case_zone.currentData() if hasattr(self,"case_zone") else None
        if not hasattr(self,"case_committee"): return
        self.case_committee.clear(); self.case_committee.addItem("بدون کمیته",None)
        if zone_id:
            for c in self.db.get_zone_committees(zone_id): self.case_committee.addItem(c.get("title"),c.get("id"))

    def refresh_all(self):
        self.db.sync_execution_cases()
        self._load_zones(); self._load_agencies_users(); self.refresh_overview(); self.refresh_cases(); self.refresh_case_selectors(); self.refresh_assignments(); self.refresh_dossier(); self.refresh_attachments(); self.refresh_performance(); self.refresh_backups()

    def refresh_overview(self):
        stats=self.db.get_execution_dashboard_stats()
        for key,card in self.overview_cards.items():
            value=stats.get(key,0); card.set_value(f"{value}٪" if key=="average_progress" else value)
        cases=[c for c in self.db.get_execution_cases(open_only=True) if c.get("due_date") and c.get("due_date")<datetime.now().strftime("%Y-%m-%d")]
        self.overdue_table.setRowCount(len(cases))
        for r,c in enumerate(cases):
            vals=[c["id"],c.get("zone_name"),c.get("title"),c.get("responsible_agency"),format_jalali(c.get("due_date")),f"{c.get('progress_percent',0)}٪",c.get("status")]
            for col,v in enumerate(vals): self.overdue_table.setItem(r,col,_item(v))

    def refresh_cases(self):
        zone=self.case_zone_filter.currentData() if hasattr(self,"case_zone_filter") else None
        status=self.case_status_filter.currentData() if hasattr(self,"case_status_filter") else None
        query=self.case_query.text().strip() if hasattr(self,"case_query") else None
        cases=self.db.get_execution_cases(zone_id=zone,status=status,query=query)
        self._cases_cache=cases; self.case_table.setRowCount(len(cases))
        for r,c in enumerate(cases):
            vals=[c["id"],c.get("zone_name"),c.get("committee_title"),c.get("title"),c.get("responsible_agency"),c.get("responsible_person"),format_jalali(c.get("due_date")),f"{c.get('progress_percent',0)}٪",c.get("status")]
            for col,v in enumerate(vals): self.case_table.setItem(r,col,_item(v,Qt.AlignRight|Qt.AlignVCenter if col in (3,4,5) else Qt.AlignCenter))

    def refresh_case_selectors(self):
        cases=self.db.get_execution_cases(limit=3000)
        for combo in (self.assign_case,self.document_case):
            current=combo.currentData(); combo.blockSignals(True); combo.clear()
            for c in cases: combo.addItem(f"#{c['id']} — {c.get('title')}",c['id'])
            idx=combo.findData(current); combo.setCurrentIndex(idx if idx>=0 else 0); combo.blockSignals(False)

    def sync_cases(self):
        self.db.sync_execution_cases(); self.refresh_all(); QMessageBox.information(self,"همگام‌سازی","مصوبات و اقدامات قبلی بدون تکرار وارد مرکز پیگیری شدند.")

    def clear_case_form(self):
        self.selected_case_id=None; self.case_title.clear(); self.case_description.clear(); self.case_person.clear(); self.case_delay.clear(); self.case_result.clear(); self.case_progress.setValue(0); self.case_status.setCurrentText("جدید")

    def load_selected_case(self):
        row=self.case_table.currentRow()
        if row<0 or row>=len(getattr(self,"_cases_cache",[])): return
        c=self._cases_cache[row]; self.selected_case_id=c["id"]
        self.case_title.setText(c.get("title") or ""); self.case_description.setPlainText(c.get("description") or "")
        idx=self.case_zone.findData(c.get("zone_id")); self.case_zone.setCurrentIndex(idx if idx>=0 else 0); self.refresh_committee_combo()
        idx=self.case_committee.findData(c.get("committee_id")); self.case_committee.setCurrentIndex(idx if idx>=0 else 0)
        self.case_agency.setEditText(c.get("responsible_agency") or ""); self.case_person.setText(c.get("responsible_person") or "")
        self.case_priority.setCurrentText(c.get("priority") or "عادی"); self.case_status.setCurrentText(c.get("status") or "جدید")
        if c.get("due_date"): self.case_due.setText(format_jalali(c.get("due_date")))
        self.case_progress.setValue(int(c.get("progress_percent") or 0)); self.case_delay.setText(c.get("delay_reason") or ""); self.case_result.setPlainText(c.get("final_result") or "")

    def save_case(self):
        try: due=self.case_due.isoDate()
        except Exception: due=None
        data=dict(zone_id=self.case_zone.currentData(),committee_id=self.case_committee.currentData(),description=self.case_description.toPlainText().strip(),responsible_agency=self.case_agency.currentText().strip(),responsible_person=self.case_person.text().strip(),priority=self.case_priority.currentText(),status=self.case_status.currentText(),due_date=due,progress_percent=self.case_progress.value(),delay_reason=self.case_delay.text().strip(),final_result=self.case_result.toPlainText().strip())
        try:
            if self.selected_case_id: self.db.update_execution_case(self.selected_case_id,title=self.case_title.text().strip(),**data)
            else: self.selected_case_id=self.db.add_execution_case(self.case_title.text().strip(),**data)
            self.refresh_all(); QMessageBox.information(self,"موفق","پرونده پیگیری ذخیره شد.")
        except Exception as exc: QMessageBox.critical(self,"خطا",str(exc))

    def add_progress_update(self):
        if not self.selected_case_id: QMessageBox.warning(self,"انتخاب پرونده","ابتدا یک پرونده را انتخاب کنید."); return
        note,ok=QInputDialog.getMultiLineText(self,"گزارش پیشرفت","شرح اقدام یا نتیجه جدید:")
        if not ok: return
        self.db.add_execution_update(self.selected_case_id,note=note,progress_percent=self.case_progress.value(),status=self.case_status.currentText())
        self.refresh_all(); QMessageBox.information(self,"ثبت شد","گزارش پیشرفت و وضعیت پرونده به‌روزرسانی شد.")

    def complete_case(self):
        if not self.selected_case_id: return
        result=self.case_result.toPlainText().strip()
        if not result:
            result,ok=QInputDialog.getMultiLineText(self,"نتیجه نهایی","نتیجه نهایی اجرا را ثبت کنید:")
            if not ok: return
        self.db.update_execution_case(self.selected_case_id,status="تکمیل‌شده",progress_percent=100,final_result=result)
        self.refresh_all()

    def create_assignment(self):
        case_id=self.assign_case.currentData()
        if not case_id: QMessageBox.warning(self,"پرونده","پرونده‌ای برای ارجاع وجود ندارد."); return
        try: due=self.assign_due.isoDate()
        except Exception: due=None
        try:
            self.db.add_execution_assignment(case_id,assigned_to_user_id=self.assign_user.currentData(),assigned_to_name=self.assign_user.currentText() if self.assign_user.currentData() else "",assigned_to_agency=self.assign_agency.currentText().strip(),instruction=self.assign_instruction.text().strip(),due_date=due,priority=self.assign_priority.currentText())
            self.assign_instruction.clear(); self.refresh_all(); QMessageBox.information(self,"ارجاع شد","پرونده در کارتابل گیرنده ثبت شد.")
        except Exception as exc: QMessageBox.critical(self,"خطا",str(exc))

    def refresh_assignments(self):
        user_id=self.current_user.get("id") if self.only_my_assignments.isChecked() else None
        assignments=self.db.get_execution_assignments(assigned_to_user_id=user_id)
        self._assign_cache=assignments; self.assignment_table.setRowCount(len(assignments))
        for r,a in enumerate(assignments):
            vals=[a["id"],a.get("case_title"),a.get("zone_name"),a.get("assigned_to_name"),a.get("assigned_to_agency"),a.get("instruction"),format_jalali(a.get("due_date")),a.get("priority"),a.get("status")]
            for c,v in enumerate(vals): self.assignment_table.setItem(r,c,_item(v,Qt.AlignRight|Qt.AlignVCenter if c in (1,3,4,5) else Qt.AlignCenter))

    def _selected_assignment(self):
        row=self.assignment_table.currentRow(); return self._assign_cache[row] if row>=0 and row<len(getattr(self,"_assign_cache",[])) else None

    def mark_assignment_viewed(self):
        a=self._selected_assignment()
        if a: self.db.update_execution_assignment(a["id"],mark_viewed=True,status="دیده‌شده" if a.get("status")=="ارجاع‌شده" else a.get("status")); self.refresh_assignments()

    def respond_assignment(self):
        a=self._selected_assignment()
        if not a: return
        response,ok=QInputDialog.getMultiLineText(self,"پاسخ ارجاع","پاسخ یا گزارش انجام کار:",a.get("response_text") or "")
        if not ok: return
        self.db.update_execution_assignment(a["id"],status="پاسخ‌داده‌شده",response_text=response,mark_viewed=True); self.refresh_all()

    def refresh_dossier(self):
        if not hasattr(self,"dossier_view"): return
        zone_id=self.dossier_zone.currentData()
        if not zone_id: self.dossier_view.setHtml("<p dir='rtl'>هیچ بلوکی ثبت نشده است.</p>"); return
        try: data=self.db.get_zone_dossier(zone_id); self._dossier_data=data
        except Exception as exc: self.dossier_view.setHtml(f"<p dir='rtl'>{html.escape(str(exc))}</p>"); return
        z=data["zone"]; profile=data["profile"]; stats=data["execution_stats"]
        sections=[f"<h1>{html.escape(z.get('name') or '')}</h1>",
                  f"<p><b>خانوار مصوب:</b> {profile.get('approved_households',0)} &nbsp; <b>جمعیت تخمینی:</b> {profile.get('estimated_population',0)}</p>",
                  f"<p><b>پرونده‌های اجرایی:</b> {stats['total']} &nbsp; <b>باز:</b> {stats['open']} &nbsp; <b>معوق:</b> {stats['overdue']} &nbsp; <b>میانگین پیشرفت:</b> {stats['average_progress']}٪</p>",
                  f"<h2>شورای محله ({len(data['council_members'])} عضو)</h2>"]
        sections.append("<ul>"+"".join(f"<li>{html.escape((m.get('first_name') or '')+' '+(m.get('last_name') or ''))} — {html.escape(m.get('position') or '')}</li>" for m in data['council_members'])+"</ul>")
        sections.append("<h2>کمیته‌های شش‌گانه</h2>")
        for item in data["committees"]:
            c=item["committee"]; sections.append(f"<h3>{html.escape(c.get('title') or '')}</h3><p>اعضا: {len(item['members'])} | جلسات: {len(item['meetings'])} | مصوبات: {len(item['resolutions'])}</p>")
            if item["members"]: sections.append("<ul>"+"".join(f"<li>{html.escape(m.get('person_name') or '')} — {html.escape(m.get('member_role') or '')} — {html.escape(m.get('agency_name') or '')}</li>" for m in item['members'])+"</ul>")
        sections.append(f"<h2>مسائل و اقدامات</h2><p>مسائل: {len(data['issues'])} | اقدامات: {len(data['actions'])} | پروژه‌ها: {len(data['projects'])} | درخواست‌های مردمی: {len(data['citizen_requests'])} | مکاتبات: {len(data['letters'])}</p>")
        sections.append("<h2>پرونده‌های پیگیری</h2><table border='1' cellspacing='0' cellpadding='6' width='100%'><tr><th>عنوان</th><th>دستگاه</th><th>مهلت</th><th>پیشرفت</th><th>وضعیت</th></tr>"+"".join(f"<tr><td>{html.escape(c.get('title') or '')}</td><td>{html.escape(c.get('responsible_agency') or '')}</td><td>{html.escape(format_jalali(c.get('due_date')))}</td><td>{c.get('progress_percent',0)}٪</td><td>{html.escape(c.get('status') or '')}</td></tr>" for c in data['execution_cases'])+"</table>")
        style="<style>body{direction:rtl;font-family:Tahoma;line-height:1.8;color:#1c2530;padding:18px}h1,h2,h3{color:#13294b}table{border-collapse:collapse}th{background:#e9eef5}</style>"
        self._dossier_html="<html><head>"+style+"</head><body>"+"".join(sections)+"</body></html>"
        self.dossier_view.setHtml(self._dossier_html)

    def export_dossier_html(self):
        if not getattr(self,"_dossier_html",None): return
        path,_=QFileDialog.getSaveFileName(self,"ذخیره پرونده جامع بلوک","block_dossier.html","HTML (*.html)")
        if path:
            with open(path,"w",encoding="utf-8") as f: f.write(self._dossier_html)
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def export_dossier_csv(self):
        data=getattr(self,"_dossier_data",None)
        if not data: return
        path,_=QFileDialog.getSaveFileName(self,"خروجی خلاصه بلوک","block_dossier.csv","CSV (*.csv)")
        if not path: return
        with open(path,"w",encoding="utf-8-sig",newline="") as f:
            w=csv.writer(f); w.writerow(["بخش","شاخص","مقدار"])
            w.writerow(["بلوک","نام",data['zone'].get('name')]); w.writerow(["جمعیت","خانوار",data['profile'].get('approved_households',0)]); w.writerow(["جمعیت","جمعیت تخمینی",data['profile'].get('estimated_population',0)])
            w.writerow(["ساختار","اعضای شورا",len(data['council_members'])]); w.writerow(["ساختار","کمیته‌ها",len(data['committees'])]); w.writerow(["عملیات","پرونده‌های باز",data['execution_stats']['open']]); w.writerow(["عملیات","پرونده‌های معوق",data['execution_stats']['overdue']])

    def refresh_attachments(self):
        if not hasattr(self,"attachment_table"): return
        case_id=self.document_case.currentData()
        rows=self.db.get_document_attachments("execution_case",case_id) if case_id else []
        self._attachment_cache=rows; self.attachment_table.setRowCount(len(rows))
        for r,a in enumerate(rows):
            vals=[a['id'],a['parent_type'],a['parent_id'],a['original_name'],a['mime_type'],f"{round((a.get('file_size') or 0)/1024,1)} KB",a.get('description'),a.get('created_by_name'),format_jalali(a.get('created_at'))]
            for c,v in enumerate(vals): self.attachment_table.setItem(r,c,_item(v,Qt.AlignRight|Qt.AlignVCenter if c in (3,6,7) else Qt.AlignCenter))

    def add_attachment(self):
        case_id=self.document_case.currentData()
        if not case_id: return
        path,_=QFileDialog.getOpenFileName(self,"انتخاب سند یا تصویر")
        if not path: return
        try: self.db.archive_document_attachment("execution_case",case_id,path,self.document_description.text().strip()); self.document_description.clear(); self.refresh_attachments()
        except Exception as exc: QMessageBox.critical(self,"خطا",str(exc))

    def _selected_attachment(self):
        row=self.attachment_table.currentRow(); return self._attachment_cache[row] if row>=0 and row<len(getattr(self,"_attachment_cache",[])) else None

    def open_attachment(self):
        a=self._selected_attachment()
        if a and os.path.exists(a.get('stored_path') or ''): QDesktopServices.openUrl(QUrl.fromLocalFile(a['stored_path']))

    def delete_attachment(self):
        a=self._selected_attachment()
        if a and QMessageBox.question(self,"حذف سند","فایل و رکورد پیوست حذف شود؟")==QMessageBox.Yes: self.db.delete_document_attachment(a['id']); self.refresh_attachments()

    def refresh_performance(self):
        agencies=self.db.get_execution_agency_performance(); self.agency_perf_table.setRowCount(len(agencies))
        for r,a in enumerate(agencies):
            vals=[r+1,a['agency'],a['total'],a['completed'],a['overdue'],f"{a['average_progress']}٪"]
            for c,v in enumerate(vals): self.agency_perf_table.setItem(r,c,_item(v,Qt.AlignRight|Qt.AlignVCenter if c==1 else Qt.AlignCenter))
        zones=self.db.get_execution_zone_performance(); self.zone_perf_table.setRowCount(len(zones))
        for r,z in enumerate(zones):
            vals=[r+1,z['zone_name'],z['total'],z['completed'],z['overdue'],f"{z['average_progress']}٪"]
            for c,v in enumerate(vals): self.zone_perf_table.setItem(r,c,_item(v,Qt.AlignRight|Qt.AlignVCenter if c==1 else Qt.AlignCenter))

    def create_backup(self):
        try: path=self.db.create_automatic_backup(reason="operations_center",keep=20); QMessageBox.information(self,"بکاپ ساخته شد",path); self.refresh_backups()
        except Exception as exc: QMessageBox.critical(self,"خطا",str(exc))

    def refresh_backups(self):
        rows=self.db.conn.execute("SELECT id,file_path,backup_type,reason,file_size,validation_status,created_at FROM backup_registry ORDER BY id DESC LIMIT 200").fetchall()
        self.backup_table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            vals=[row[0],row[1],row[2],row[3],f"{round((row[4] or 0)/1024/1024,2)} MB",row[5],format_jalali(row[6])]
            for c,v in enumerate(vals): self.backup_table.setItem(r,c,_item(v,Qt.AlignRight|Qt.AlignVCenter if c in (1,3) else Qt.AlignCenter))

    def open_build_guide(self):
        path=os.path.join(os.path.dirname(__file__),"docs","INSTALL_WINDOWS.md")
        if os.path.exists(path): QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        else: QMessageBox.information(self,"راهنما","فایل build_windows.bat را اجرا و سپس فایل installer/JavanroodSetup.iss را با Inno Setup کامپایل کنید.")
