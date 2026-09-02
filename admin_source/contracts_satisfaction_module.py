# -*- coding: utf-8 -*-
"""رابط قراردادها، پیمانکاران، پرداخت، رضایت و مشارکت مردمی — نسخه ۶.۸."""
from datetime import date
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QDialog,
    QDialogButtonBox, QLabel, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QLineEdit, QComboBox,
    QDoubleSpinBox, QSpinBox, QTextEdit, QCheckBox, QFileDialog, QFrame,
)
from header_widget import build_official_header
from jalali_widgets import JalaliDateEdit
from jalali_utils import convert_dates_in_text
from icon_manager import set_button_style
from contracts_satisfaction_reports import (
    export_contract_management_pdf, export_contract_management_excel,
    export_contract_management_powerpoint,
)


def _money_spin(value=0):
    w=QDoubleSpinBox();w.setRange(0,999_999_999_999_999);w.setDecimals(0);w.setGroupSeparatorShown(True);w.setValue(float(value or 0));return w

def _score_spin(value=0):
    w=QDoubleSpinBox();w.setRange(0,5);w.setDecimals(1);w.setSingleStep(.5);w.setValue(float(value or 0));return w

def _date_text(value=None):
    w=JalaliDateEdit(value)
    if not value: w.clear()
    return w

def _iso_date(widget):
    return widget.isoDate() if widget.text().strip() else None


class ContractorDialog(QDialog):
    def __init__(self, db, item=None, parent=None):
        super().__init__(parent);self.db=db;self.item=item or {};self.setWindowTitle("مشخصات پیمانکار");self.resize(600,600)
        lay=QVBoxLayout(self);form=QFormLayout()
        self.name=QLineEdit(self.item.get("name") or "");self.nid=QLineEdit(self.item.get("national_id") or "")
        self.reg=QLineEdit(self.item.get("registration_no") or "");self.manager=QLineEdit(self.item.get("manager_name") or "")
        self.phone=QLineEdit(self.item.get("phone") or "");self.email=QLineEdit(self.item.get("email") or "")
        self.specialty=QLineEdit(self.item.get("specialty") or "");self.address=QTextEdit(self.item.get("address") or "")
        self.status=QComboBox();self.status.addItems(db.CONTRACTOR_STATUSES);self.status.setCurrentText(self.item.get("status") or "فعال")
        self.notes=QTextEdit(self.item.get("notes") or "")
        for label,w in [("نام پیمانکار*:",self.name),("شناسه ملی:",self.nid),("شماره ثبت:",self.reg),("مدیرعامل/مسئول:",self.manager),("تلفن:",self.phone),("ایمیل:",self.email),("تخصص:",self.specialty),("نشانی:",self.address),("وضعیت:",self.status),("یادداشت:",self.notes)]:form.addRow(label,w)
        lay.addLayout(form);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.validate);b.rejected.connect(self.reject);lay.addWidget(b)
    def validate(self):
        if not self.name.text().strip():QMessageBox.warning(self,"اطلاعات ناقص","نام پیمانکار الزامی است.");return
        self.accept()
    def values(self):
        return dict(name=self.name.text().strip(),national_id=self.nid.text().strip(),registration_no=self.reg.text().strip(),manager_name=self.manager.text().strip(),phone=self.phone.text().strip(),email=self.email.text().strip(),specialty=self.specialty.text().strip(),address=self.address.toPlainText().strip(),status=self.status.currentText(),notes=self.notes.toPlainText().strip())


class ContractDialog(QDialog):
    def __init__(self, db, item=None, parent=None):
        super().__init__(parent);self.db=db;self.item=item or {};self.setWindowTitle("قرارداد");self.resize(650,700)
        lay=QVBoxLayout(self);form=QFormLayout()
        self.no=QLineEdit(self.item.get("contract_no") or "");self.title=QLineEdit(self.item.get("title") or "")
        self.contractor=QComboBox()
        for x in db.get_contractors():self.contractor.addItem(x["name"],x["id"])
        if self.item.get("contractor_id") is not None:self.contractor.setCurrentIndex(max(0,self.contractor.findData(self.item["contractor_id"])))
        self.link_type=QComboBox();self.link_type.addItems(["پروژه","اقدام"]);self.link=QComboBox();self.link_type.currentTextChanged.connect(self.refresh_links)
        if self.item.get("action_id"):self.link_type.setCurrentText("اقدام")
        self.refresh_links();target=self.item.get("action_id") or self.item.get("project_id");idx=self.link.findData(target);self.link.setCurrentIndex(max(0,idx))
        self.contract_date=_date_text(self.item.get("contract_date"));self.start=_date_text(self.item.get("start_date"));self.end=_date_text(self.item.get("end_date"))
        self.amount=_money_spin(self.item.get("amount"));self.guarantee=_money_spin(self.item.get("guarantee_amount"))
        self.retention=QDoubleSpinBox();self.retention.setRange(0,100);self.retention.setSuffix("٪");self.retention.setValue(float(self.item.get("retention_percent") or 0))
        self.advance=QDoubleSpinBox();self.advance.setRange(0,100);self.advance.setSuffix("٪");self.advance.setValue(float(self.item.get("advance_percent") or 0))
        self.status=QComboBox();self.status.addItems(db.CONTRACT_STATUSES);self.status.setCurrentText(self.item.get("status") or "پیش‌نویس")
        self.description=QTextEdit(self.item.get("description") or "")
        for label,w in [("شماره قرارداد*:",self.no),("عنوان*:",self.title),("پیمانکار*:",self.contractor),("نوع ارتباط:",self.link_type),("پروژه/اقدام*:",self.link),("تاریخ قرارداد:",self.contract_date),("شروع:",self.start),("پایان:",self.end),("مبلغ قرارداد:",self.amount),("ضمانت‌نامه:",self.guarantee),("حسن انجام کار:",self.retention),("پیش‌پرداخت:",self.advance),("وضعیت:",self.status),("شرح:",self.description)]:form.addRow(label,w)
        lay.addLayout(form);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.validate);b.rejected.connect(self.reject);lay.addWidget(b)
    def refresh_links(self):
        current=self.link.currentData() if self.link.count() else None;self.link.clear()
        if self.link_type.currentText()=="پروژه":
            for x in self.db.get_projects():self.link.addItem(f"{x.get('project_code')} — {x.get('title')}",x["id"])
        else:
            for x in self.db.get_neighborhood_actions():self.link.addItem(f"{x.get('zone_name') or ''} — {x.get('title')}",x["id"])
        idx=self.link.findData(current)
        if idx>=0:self.link.setCurrentIndex(idx)
    def validate(self):
        if not self.no.text().strip() or not self.title.text().strip() or self.contractor.currentData() is None or self.link.currentData() is None:
            QMessageBox.warning(self,"اطلاعات ناقص","شماره، عنوان، پیمانکار و پروژه/اقدام الزامی است.");return
        if self.start.text().strip() and self.end.text().strip() and self.end.date()<self.start.date():QMessageBox.warning(self,"تاریخ نامعتبر","پایان قرارداد قبل از شروع است.");return
        self.accept()
    def values(self):
        is_project=self.link_type.currentText()=="پروژه"
        return dict(contract_no=self.no.text().strip(),title=self.title.text().strip(),contractor_id=self.contractor.currentData(),project_id=self.link.currentData() if is_project else None,action_id=None if is_project else self.link.currentData(),contract_date=_iso_date(self.contract_date),start_date=_iso_date(self.start),end_date=_iso_date(self.end),amount=self.amount.value(),guarantee_amount=self.guarantee.value(),retention_percent=self.retention.value(),advance_percent=self.advance.value(),status=self.status.currentText(),description=self.description.toPlainText().strip())


class PaymentDialog(QDialog):
    def __init__(self, db, contracts, item=None, parent=None):
        super().__init__(parent);self.db=db;self.item=item or {};self.setWindowTitle("صورت‌وضعیت و پرداخت");self.resize(620,680)
        lay=QVBoxLayout(self);form=QFormLayout();self.contract=QComboBox()
        for x in contracts:self.contract.addItem(f"{x['contract_no']} — {x['title']}",x["id"])
        if self.item.get("contract_id"):self.contract.setCurrentIndex(max(0,self.contract.findData(self.item["contract_id"])))
        self.ptype=QComboBox();self.ptype.addItems(db.PAYMENT_TYPES);self.ptype.setCurrentText(self.item.get("payment_type") or "صورت‌وضعیت")
        self.statement=QLineEdit(self.item.get("statement_no") or "");self.pfrom=_date_text(self.item.get("period_from"));self.pto=_date_text(self.item.get("period_to"))
        self.gross=_money_spin(self.item.get("gross_amount"));self.deductions=_money_spin(self.item.get("deductions"));self.approved=_money_spin(self.item.get("approved_amount"));self.paid=_money_spin(self.item.get("paid_amount"))
        self.invoice=_date_text(self.item.get("invoice_date"));self.approval=_date_text(self.item.get("approval_date"));self.payment=_date_text(self.item.get("payment_date"))
        self.status=QComboBox();self.status.addItems(db.PAYMENT_STATUSES);self.status.setCurrentText(self.item.get("status") or "ثبت اولیه");self.notes=QTextEdit(self.item.get("notes") or "")
        for label,w in [("قرارداد:",self.contract),("نوع:",self.ptype),("شماره صورت‌وضعیت:",self.statement),("از تاریخ:",self.pfrom),("تا تاریخ:",self.pto),("مبلغ ناخالص:",self.gross),("کسور:",self.deductions),("مبلغ تأییدشده:",self.approved),("مبلغ پرداختی:",self.paid),("تاریخ ثبت:",self.invoice),("تاریخ تأیید:",self.approval),("تاریخ پرداخت:",self.payment),("وضعیت:",self.status),("یادداشت:",self.notes)]:form.addRow(label,w)
        lay.addLayout(form);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);lay.addWidget(b)
    def values(self):
        return dict(contract_id=self.contract.currentData(),payment_type=self.ptype.currentText(),statement_no=self.statement.text().strip() or None,period_from=_iso_date(self.pfrom),period_to=_iso_date(self.pto),gross_amount=self.gross.value(),deductions=self.deductions.value(),approved_amount=self.approved.value(),paid_amount=self.paid.value(),invoice_date=_iso_date(self.invoice),approval_date=_iso_date(self.approval),payment_date=_iso_date(self.payment),status=self.status.currentText(),notes=self.notes.toPlainText().strip())


class EvaluationDialog(QDialog):
    def __init__(self, db, contracts, parent=None):
        super().__init__(parent);self.setWindowTitle("ارزیابی پیمانکار");lay=QVBoxLayout(self);form=QFormLayout();self.contract=QComboBox()
        for x in contracts:self.contract.addItem(f"{x['contract_no']} — {x['contractor_name']}",x["id"])
        self.date=_date_text(date.today().isoformat());self.quality=_score_spin();self.schedule=_score_spin();self.safety=_score_spin();self.cooperation=_score_spin();self.documentation=_score_spin();self.evaluator=QLineEdit();self.notes=QTextEdit()
        for label,w in [("قرارداد:",self.contract),("تاریخ:",self.date),("کیفیت:",self.quality),("زمان‌بندی:",self.schedule),("ایمنی:",self.safety),("همکاری:",self.cooperation),("مستندات:",self.documentation),("ارزیاب:",self.evaluator),("یادداشت:",self.notes)]:form.addRow(label,w)
        lay.addLayout(form);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);lay.addWidget(b)
    def values(self):return dict(contract_id=self.contract.currentData(),evaluation_date=self.date.isoDate(),quality_score=self.quality.value(),schedule_score=self.schedule.value(),safety_score=self.safety.value(),cooperation_score=self.cooperation.value(),documentation_score=self.documentation.value(),evaluator=self.evaluator.text().strip(),notes=self.notes.toPlainText().strip())


class SatisfactionDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent);self.db=db;self.setWindowTitle("ثبت رضایت مردمی");self.resize(620,640);lay=QVBoxLayout(self);form=QFormLayout()
        self.zone=QComboBox();[self.zone.addItem(x["name"],x["id"]) for x in db.get_zones()]
        self.link_type=QComboBox();self.link_type.addItems(["فقط بلوک","پروژه","اقدام","درخواست مردمی"]);self.link=QComboBox();self.link_type.currentTextChanged.connect(self.refresh_links);self.refresh_links()
        self.date=_date_text(date.today().isoformat());self.respondents=QSpinBox();self.respondents.setRange(1,1_000_000);self.respondents.setValue(1)
        self.resolved=QDoubleSpinBox();self.resolved.setRange(0,100);self.resolved.setSuffix("٪")
        self.quality=_score_spin();self.speed=_score_spin();self.communication=_score_spin();self.overall=_score_spin();self.reopen=QCheckBox("نیاز به بازگشایی و اصلاح دارد");self.recorded=QLineEdit();self.comments=QTextEdit()
        for label,w in [("بلوک:",self.zone),("اتصال:",self.link_type),("رکورد مرتبط:",self.link),("تاریخ:",self.date),("تعداد پاسخ‌دهندگان:",self.respondents),("رفع واقعی مسئله:",self.resolved),("کیفیت:",self.quality),("سرعت:",self.speed),("پاسخ‌گویی:",self.communication),("رضایت کلی:",self.overall),("بازبینی:",self.reopen),("ثبت‌کننده:",self.recorded),("توضیحات:",self.comments)]:form.addRow(label,w)
        lay.addLayout(form);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);lay.addWidget(b)
    def refresh_links(self):
        self.link.clear();kind=self.link_type.currentText()
        if kind=="فقط بلوک":self.link.addItem("—",None)
        elif kind=="پروژه":[self.link.addItem(f"{x.get('project_code')} — {x.get('title')}",x["id"]) for x in self.db.get_projects()]
        elif kind=="اقدام":[self.link.addItem(x.get("title"),x["id"]) for x in self.db.get_neighborhood_actions()]
        else:[self.link.addItem(f"{x.get('tracking_code')} — {x.get('title')}",x["id"]) for x in self.db.get_citizen_requests()]
    def values(self):
        kind=self.link_type.currentText();rid=self.link.currentData()
        return dict(zone_id=self.zone.currentData(),project_id=rid if kind=="پروژه" else None,action_id=rid if kind=="اقدام" else None,citizen_request_id=rid if kind=="درخواست مردمی" else None,survey_date=self.date.isoDate(),respondents=self.respondents.value(),problem_resolved_percent=self.resolved.value(),quality_score=self.quality.value(),speed_score=self.speed.value(),communication_score=self.communication.value(),overall_score=self.overall.value(),reopen_recommended=self.reopen.isChecked(),recorded_by=self.recorded.text().strip(),comments=self.comments.toPlainText().strip())


class ParticipationDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent);self.db=db;self.setWindowTitle("مشارکت و ظرفیت محلی");self.resize(600,650);lay=QVBoxLayout(self);form=QFormLayout()
        self.zone=QComboBox();[self.zone.addItem(x["name"],x["id"]) for x in db.get_zones()];self.title=QLineEdit();self.ptype=QComboBox();self.ptype.addItems(db.PARTICIPATION_TYPES)
        self.org=QLineEdit();self.contact=QLineEdit();self.phone=QLineEdit();self.volunteers=QSpinBox();self.volunteers.setRange(0,1_000_000);self.cash=_money_spin();self.noncash=_money_spin();self.start=_date_text();self.end=_date_text();self.status=QComboBox();self.status.addItems(["فعال","تکمیل‌شده","متوقف","لغوشده"]);self.description=QTextEdit()
        for label,w in [("بلوک:",self.zone),("عنوان*:",self.title),("نوع:",self.ptype),("گروه/سازمان:",self.org),("فرد رابط:",self.contact),("تلفن:",self.phone),("تعداد داوطلب:",self.volunteers),("ارزش نقدی:",self.cash),("ارزش غیرنقدی:",self.noncash),("شروع:",self.start),("پایان:",self.end),("وضعیت:",self.status),("شرح:",self.description)]:form.addRow(label,w)
        lay.addLayout(form);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.validate);b.rejected.connect(self.reject);lay.addWidget(b)
    def validate(self):
        if not self.title.text().strip():QMessageBox.warning(self,"اطلاعات ناقص","عنوان مشارکت الزامی است.");return
        self.accept()
    def values(self):return dict(zone_id=self.zone.currentData(),title=self.title.text().strip(),participation_type=self.ptype.currentText(),organization_name=self.org.text().strip(),contact_person=self.contact.text().strip(),phone=self.phone.text().strip(),volunteers_count=self.volunteers.value(),cash_value=self.cash.value(),noncash_value=self.noncash.value(),start_date=_iso_date(self.start),end_date=_iso_date(self.end),status=self.status.currentText(),description=self.description.toPlainText().strip())


class ContractsSatisfactionWindow(QMainWindow):
    back_requested=pyqtSignal()
    def __init__(self, db):
        super().__init__();self.db=db;self.user=db.get_current_user() or {};self.can_manage=self.user.get("role") in ("admin","manager");self.can_field=self.can_manage or self.user.get("role")=="field"
        self.setWindowTitle("قراردادها، پیمانکاران و رضایت مردمی");self.resize(1400,880);self._build();self.refresh_all()
    def _build(self):
        central=QWidget();self.setCentralWidget(central);root=QVBoxLayout(central);root.setContentsMargins(0,0,0,0);root.addWidget(build_official_header("قرارداد، پیمانکار و رضایت مردمی",self.db))
        bar=QHBoxLayout();back=QPushButton("بازگشت به داشبورد");back.clicked.connect(self.back_requested.emit);bar.addWidget(back);bar.addStretch();self.summary=QLabel();self.summary.setStyleSheet("font-weight:700;color:#13294b;");bar.addWidget(self.summary)
        for label,kind in [("گزارش PDF","pdf"),("گزارش Excel","xlsx"),("گزارش PowerPoint","pptx")]:
            b=QPushButton(label);b.clicked.connect(lambda _,k=kind:self.export_report(k));bar.addWidget(b)
        root.addLayout(bar);self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        self.contractors=self._table(["نام","شناسه ملی","مدیر","تلفن","تخصص","وضعیت","امتیاز","قرارداد فعال"]);self.tabs.addTab(self._tab(self.contractors,[("افزودن پیمانکار",self.add_contractor),("ویرایش",self.edit_contractor),("حذف",self.delete_contractor)],self.can_manage),"پیمانکاران")
        self.contracts=self._table(["شماره","عنوان","پیمانکار","پروژه/اقدام","بلوک","شروع","پایان","مبلغ","پرداخت٪","امتیاز","وضعیت"]);self.tabs.addTab(self._tab(self.contracts,[("افزودن قرارداد",self.add_contract),("ویرایش",self.edit_contract),("حذف",self.delete_contract)],self.can_manage),"قراردادها")
        self.payments=self._table(["قرارداد","نوع","شماره","خالص","تأیید","پرداخت","تاریخ","وضعیت"]);self.tabs.addTab(self._tab(self.payments,[("ثبت صورت‌وضعیت/پرداخت",self.add_payment),("ویرایش",self.edit_payment),("حذف",self.delete_payment)],self.can_manage),"صورت‌وضعیت و پرداخت")
        self.evaluations=self._table(["قرارداد","پیمانکار","تاریخ","کیفیت","زمان","ایمنی","همکاری","مستندات","امتیاز","ارزیاب"]);self.tabs.addTab(self._tab(self.evaluations,[("ثبت ارزیابی",self.add_evaluation),("حذف",self.delete_evaluation)],self.can_manage),"ارزیابی پیمانکار")
        self.surveys=self._table(["بلوک","پروژه/اقدام","تاریخ","پاسخ‌دهنده","رفع مسئله٪","رضایت٪","بازگشایی","ثبت‌کننده"]);self.tabs.addTab(self._tab(self.surveys,[("ثبت نظرسنجی",self.add_survey),("حذف",self.delete_survey)],self.can_field),"رضایت مردمی")
        self.participations=self._table(["بلوک","عنوان","نوع","گروه","داوطلب","نقدی","غیرنقدی","وضعیت"]);self.tabs.addTab(self._tab(self.participations,[("ثبت مشارکت",self.add_participation),("حذف",self.delete_participation)],self.can_field),"مشارکت مردمی")
        self.alerts=self._table(["شدت","نوع","عنوان","بلوک","سررسید","پیام"]);self.tabs.addTab(self._tab(self.alerts,[],False),"هشدارها")
    def _table(self,headers):
        t=QTableWidget(0,len(headers));t.setHorizontalHeaderLabels(headers);t.setSelectionBehavior(QTableWidget.SelectRows);t.setEditTriggers(QTableWidget.NoEditTriggers);t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);return t
    def _tab(self,table,buttons,enabled):
        w=QWidget();lay=QVBoxLayout(w);row=QHBoxLayout()
        for text,slot in buttons:
            b=QPushButton(text);b.setEnabled(enabled);b.clicked.connect(slot);row.addWidget(b)
        row.addStretch();refresh=QPushButton("بروزرسانی");refresh.clicked.connect(self.refresh_all);row.addWidget(refresh);lay.addLayout(row);lay.addWidget(table);return w
    def _fill(self,table,rows,keys):
        table.setRowCount(len(rows))
        for r,item in enumerate(rows):
            table.setRowHeight(r,30);table.setVerticalHeaderItem(r,QTableWidgetItem(str(item.get("id"))))
            for c,key in enumerate(keys):
                value=key(item) if callable(key) else item.get(key);table.setItem(r,c,QTableWidgetItem("—" if value in (None,"") else convert_dates_in_text(str(value))))
    def _selected_id(self,table):
        row=table.currentRow()
        if row<0:return None
        item=table.verticalHeaderItem(row);return int(item.text()) if item else None
    def refresh_all(self):
        self.contractor_rows=self.db.get_contractors();self.contract_rows=self.db.get_contracts();self.payment_rows=self.db.get_contract_payments();self.evaluation_rows=self.db.get_contractor_evaluations();self.survey_rows=self.db.get_satisfaction_surveys();self.participation_rows=self.db.get_community_participations();self.alert_rows=self.db.get_contract_management_alerts();s=self.db.get_contract_management_summary()
        self.summary.setText(f"قرارداد: {s['contracts_count']} | فعال: {s['active_contracts']} | پرداخت: {s['payment_percent']:.0f}٪ | رضایت: {s['average_satisfaction']:.0f}٪ | هشدار: {s['alerts_count']}")
        self._fill(self.contractors,self.contractor_rows,["name","national_id","manager_name","phone","specialty","status",lambda x:f"{float(x.get('average_score') or 0):.1f}","active_contracts"])
        self._fill(self.contracts,self.contract_rows,["contract_no","title","contractor_name",lambda x:x.get("project_title") or x.get("action_title"),"zone_name","start_date","end_date",lambda x:f"{float(x.get('amount') or 0):,.0f}",lambda x:f"{float(x.get('payment_percent') or 0):.0f}٪",lambda x:f"{float(x.get('evaluation_score') or 0):.0f}","status"])
        self._fill(self.payments,self.payment_rows,["contract_no","payment_type","statement_no",lambda x:f"{float(x.get('net_amount') or 0):,.0f}",lambda x:f"{float(x.get('approved_amount') or 0):,.0f}",lambda x:f"{float(x.get('paid_amount') or 0):,.0f}","payment_date","status"])
        self._fill(self.evaluations,self.evaluation_rows,["contract_no","contractor_name","evaluation_date","quality_score","schedule_score","safety_score","cooperation_score","documentation_score",lambda x:f"{float(x.get('total_score') or 0):.1f}","evaluator"])
        self._fill(self.surveys,self.survey_rows,["zone_name",lambda x:x.get("project_title") or x.get("action_title") or x.get("tracking_code"),"survey_date","respondents",lambda x:f"{float(x.get('problem_resolved_percent') or 0):.0f}٪",lambda x:f"{float(x.get('satisfaction_percent') or 0):.0f}٪",lambda x:"بله" if x.get("reopen_recommended") else "خیر","recorded_by"])
        self._fill(self.participations,self.participation_rows,["zone_name","title","participation_type","organization_name","volunteers_count",lambda x:f"{float(x.get('cash_value') or 0):,.0f}",lambda x:f"{float(x.get('noncash_value') or 0):,.0f}","status"])
        self._fill(self.alerts,self.alert_rows,["severity","type","title","zone_name","due_date","message"])
    def add_contractor(self):
        d=ContractorDialog(self.db,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.add_contractor(**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def edit_contractor(self):
        i=self._selected_id(self.contractors)
        if not i:return
        d=ContractorDialog(self.db,self.db.get_contractor(i),self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.update_contractor(i,**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def delete_contractor(self):self._delete(self.contractors,self.db.delete_contractor,"پیمانکار")
    def add_contract(self):
        if not self.db.get_contractors():QMessageBox.warning(self,"نیاز به پیمانکار","ابتدا پیمانکار ثبت کنید.");return
        d=ContractDialog(self.db,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.add_contract(**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def edit_contract(self):
        i=self._selected_id(self.contracts)
        if not i:return
        d=ContractDialog(self.db,self.db.get_contract(i),self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.update_contract(i,**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def delete_contract(self):self._delete(self.contracts,self.db.delete_contract,"قرارداد")
    def add_payment(self):
        if not self.contract_rows:return
        d=PaymentDialog(self.db,self.contract_rows,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.add_contract_payment(**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def edit_payment(self):
        i=self._selected_id(self.payments)
        if not i:return
        item=self.db.get_contract_payment(i);d=PaymentDialog(self.db,self.contract_rows,item,self)
        if d.exec_()==QDialog.Accepted:
            try:v=d.values();v.pop("contract_id",None);self.db.update_contract_payment(i,**v);self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def delete_payment(self):self._delete(self.payments,self.db.delete_contract_payment,"پرداخت")
    def add_evaluation(self):
        if not self.contract_rows:return
        d=EvaluationDialog(self.db,self.contract_rows,self)
        if d.exec_()==QDialog.Accepted:self.db.add_contractor_evaluation(**d.values());self.refresh_all()
    def delete_evaluation(self):self._delete(self.evaluations,self.db.delete_contractor_evaluation,"ارزیابی")
    def add_survey(self):
        d=SatisfactionDialog(self.db,self)
        if d.exec_()==QDialog.Accepted:self.db.add_satisfaction_survey(**d.values());self.refresh_all()
    def delete_survey(self):self._delete(self.surveys,self.db.delete_satisfaction_survey,"نظرسنجی")
    def add_participation(self):
        d=ParticipationDialog(self.db,self)
        if d.exec_()==QDialog.Accepted:self.db.add_community_participation(**d.values());self.refresh_all()
    def delete_participation(self):self._delete(self.participations,self.db.delete_community_participation,"مشارکت")
    def _delete(self,table,func,label):
        i=self._selected_id(table)
        if not i:return
        if QMessageBox.question(self,"تأیید حذف",f"{label} انتخاب‌شده حذف شود؟",QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        try:func(i);self.refresh_all()
        except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def export_report(self,kind):
        filters={"pdf":"PDF (*.pdf)","xlsx":"Excel (*.xlsx)","pptx":"PowerPoint (*.pptx)"};path,_=QFileDialog.getSaveFileName(self,"ذخیره گزارش",f"contract_management.{kind}",filters[kind])
        if not path:return
        try:
            {"pdf":export_contract_management_pdf,"xlsx":export_contract_management_excel,"pptx":export_contract_management_powerpoint}[kind](self.db,path)
            QMessageBox.information(self,"گزارش آماده شد",path)
        except Exception as e:QMessageBox.critical(self,"خطا",str(e))
