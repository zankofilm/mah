# -*- coding: utf-8 -*-
"""برنامه عملیاتی، سبد پروژه، گانت، ریسک و کنترل تغییرات نسخه ۶.۷."""

from datetime import datetime, date

from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QLineEdit, QTextEdit,
    QMessageBox, QFileDialog, QDateEdit, QDoubleSpinBox, QSpinBox, QGroupBox,
    QFrame, QGridLayout, QSplitter, QProgressBar, QInputDialog, QCheckBox,
    QCompleter, QSizePolicy
)

from header_widget import build_official_header
from jalali_widgets import JalaliDateEdit
from jalali_utils import format_jalali, convert_dates_in_text, iso_to_jalali, jalali_to_iso, today_jalali
QDateEdit = JalaliDateEdit
from icon_manager import set_button_style
from project_control_reports import (
    export_project_control_excel, export_project_control_pdf,
    export_project_control_powerpoint,
)


def _table(headers, stretch=()):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    for i in range(len(headers)):
        table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch if i in stretch else QHeaderView.ResizeToContents)
    return table


def _date_text(value):
    return iso_to_jalali(value)


def _set_date(edit, value, fallback=None):
    qdate = QDate.fromString(_date_text(value), "yyyy-MM-dd")
    edit.setDate(qdate if qdate.isValid() else (fallback or QDate.currentDate()))


def _date_edit(value=None, fallback=None):
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat("yyyy/MM/dd")
    _set_date(edit, value, fallback)
    return edit


def _money_spin(value=0):
    spin = QDoubleSpinBox()
    spin.setRange(0, 999999999999999.0)
    spin.setDecimals(0)
    spin.setGroupSeparatorShown(True)
    spin.setValue(float(value or 0))
    return spin


def _percent_spin(value=0):
    spin = QDoubleSpinBox()
    spin.setRange(0, 100)
    spin.setDecimals(1)
    spin.setSuffix(" ٪")
    spin.setValue(float(value or 0))
    return spin




DEFAULT_AGENCIES = [
    "فرمانداری شهرستان جوانرود",
    "شهرداری جوانرود",
    "اداره آب و فاضلاب",
    "اداره برق",
    "اداره گاز",
    "اداره مخابرات",
    "آموزش و پرورش",
    "شبکه بهداشت و درمان",
    "اداره بهزیستی",
    "اداره راه و شهرسازی",
    "نیروی انتظامی",
    "بخشداری مرکزی",
]


class AgencyInput(QWidget):
    """ورودی دستگاه مسئول با تایپ آزاد، پیشنهاد خودکار و ثبت سریع دستگاه جدید."""
    def __init__(self, db, value="", parent=None):
        super().__init__(parent)
        self.db = db
        self.edit = QLineEdit(str(value or ""))
        self.edit.setPlaceholderText("نام دستگاه را تایپ یا از پیشنهادها انتخاب کنید")
        self.edit.setClearButtonEnabled(True)
        self.edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.add_button = QPushButton("+")
        self.add_button.setToolTip("ثبت دستگاه جدید در دفتر دستگاه‌ها")
        self.add_button.setFixedWidth(38)
        self.add_button.clicked.connect(self._add_agency)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.add_button)
        self.refresh_suggestions()

    def _agency_names(self):
        names = list(DEFAULT_AGENCIES)
        try:
            names.extend(a.get("name", "") for a in self.db.get_management_agencies(active_only=False))
        except Exception:
            pass
        clean = []
        seen = set()
        for name in names:
            name = str(name or "").strip()
            key = name.casefold()
            if name and key not in seen:
                seen.add(key)
                clean.append(name)
        return sorted(clean)

    def refresh_suggestions(self):
        completer = QCompleter(self._agency_names(), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.edit.setCompleter(completer)
        self.completer = completer

    def _add_agency(self):
        current = self.text()
        name, ok = QInputDialog.getText(
            self, "ثبت دستگاه جدید", "نام دستگاه مسئول:", QLineEdit.Normal, current
        )
        name = str(name or "").strip()
        if not ok or not name:
            return
        try:
            saved_names = {
                str(item.get("name") or "").strip().casefold()
                for item in self.db.get_management_agencies(active_only=False)
            }
        except Exception:
            saved_names = set()
        if name.casefold() not in saved_names:
            try:
                self.db.add_management_agency(name=name)
            except Exception as exc:
                QMessageBox.warning(self, "ثبت دستگاه", f"ثبت دستگاه انجام نشد:\n{exc}")
                return
        self.refresh_suggestions()
        self.setText(name)

    def text(self):
        return self.edit.text().strip()

    def setText(self, value):
        self.edit.setText(str(value or ""))


class ProgramDialog(QDialog):
    def __init__(self, db, item=None, parent=None):
        super().__init__(parent)
        self.db = db; self.item = item or {}
        self.setWindowTitle("برنامه عملیاتی سالانه")
        self.resize(690, 650)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.year = QLineEdit(self.item.get("fiscal_year") or today_jalali(False)[:4])
        self.title = QLineEdit(self.item.get("title") or "")
        self.goal = QTextEdit(self.item.get("strategic_goal") or ""); self.goal.setMaximumHeight(80)
        self.zone = QComboBox(); self.zone.addItem("کل شهر / بدون بلوک خاص", None)
        for zone in db.get_zones(): self.zone.addItem(zone["name"], zone["id"])
        if self.item.get("zone_id") is not None:
            idx = self.zone.findData(self.item.get("zone_id")); self.zone.setCurrentIndex(max(0, idx))
        self.agency = AgencyInput(db, self.item.get("responsible_agency") or "")
        self.manager = QLineEdit(self.item.get("program_manager") or "")
        self.start = _date_edit(self.item.get("start_date"), QDate.currentDate())
        self.end = _date_edit(self.item.get("end_date"), QDate.currentDate().addYears(1))
        self.budget = _money_spin(self.item.get("approved_budget"))
        self.weight = QDoubleSpinBox(); self.weight.setRange(0.1, 100); self.weight.setValue(float(self.item.get("weight") or 1))
        self.progress = _percent_spin(self.item.get("progress_percent"))
        self.status = QComboBox(); self.status.addItems(db.PROGRAM_STATUSES); self.status.setCurrentText(self.item.get("status") or "پیش‌نویس")
        self.description = QTextEdit(self.item.get("description") or ""); self.description.setMinimumHeight(100)
        form.addRow("سال مالی:", self.year); form.addRow("عنوان برنامه:", self.title)
        form.addRow("هدف راهبردی:", self.goal); form.addRow("بلوک:", self.zone)
        form.addRow("دستگاه مسئول:", self.agency); form.addRow("مدیر برنامه:", self.manager)
        form.addRow("تاریخ شروع:", self.start); form.addRow("تاریخ پایان:", self.end)
        form.addRow("بودجه مصوب:", self.budget); form.addRow("وزن برنامه:", self.weight)
        form.addRow("پیشرفت:", self.progress); form.addRow("وضعیت:", self.status)
        form.addRow("توضیحات:", self.description); layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره برنامه"); buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def validate(self):
        if not self.year.text().strip() or not self.title.text().strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "سال مالی و عنوان برنامه الزامی است."); return
        if self.end.date() < self.start.date():
            QMessageBox.warning(self, "تاریخ نامعتبر", "تاریخ پایان قبل از تاریخ شروع است."); return
        self.accept()

    def values(self):
        return dict(fiscal_year=self.year.text().strip(), title=self.title.text().strip(),
                    strategic_goal=self.goal.toPlainText().strip(), zone_id=self.zone.currentData(),
                    responsible_agency=self.agency.text(), program_manager=self.manager.text().strip(),
                    start_date=self.start.date().toString("yyyy-MM-dd"), end_date=self.end.date().toString("yyyy-MM-dd"),
                    approved_budget=self.budget.value(), weight=self.weight.value(), progress_percent=self.progress.value(),
                    status=self.status.currentText(), description=self.description.toPlainText().strip())


class ProjectDialog(QDialog):
    def __init__(self, db, item=None, preselected_program=None, parent=None):
        super().__init__(parent)
        self.db=db; self.item=item or {}
        self.setWindowTitle("پروژه اجرایی")
        self.resize(720, 720)
        layout=QVBoxLayout(self); form=QFormLayout()
        self.program=QComboBox(); self.program.addItem("بدون برنامه بالادستی",None)
        for p in db.get_annual_programs(): self.program.addItem(f"{p['fiscal_year']} — {p['title']}",p['id'])
        target=self.item.get("program_id") if item else preselected_program
        if target is not None:
            idx=self.program.findData(target); self.program.setCurrentIndex(max(0,idx))
        self.zone=QComboBox(); self.zone.addItem("بدون بلوک خاص",None)
        for z in db.get_zones(): self.zone.addItem(z["name"],z["id"])
        if self.item.get("zone_id") is not None:
            idx=self.zone.findData(self.item.get("zone_id")); self.zone.setCurrentIndex(max(0,idx))
        self.code=QLineEdit(self.item.get("project_code") or ""); self.code.setPlaceholderText("خالی بماند تا خودکار تولید شود")
        self.title=QLineEdit(self.item.get("title") or "")
        self.agency=AgencyInput(db, self.item.get("responsible_agency") or "")
        self.manager=QLineEdit(self.item.get("project_manager") or "")
        self.start=_date_edit(self.item.get("start_date"),QDate.currentDate())
        self.end=_date_edit(self.item.get("end_date"),QDate.currentDate().addMonths(3))
        self.actual_start=_date_edit(self.item.get("actual_start_date"),QDate.currentDate())
        self.actual_start_enabled=QCheckBox("شروع واقعی ثبت شود"); self.actual_start_enabled.setChecked(bool(self.item.get("actual_start_date")))
        self.actual_start.setEnabled(self.actual_start_enabled.isChecked()); self.actual_start_enabled.toggled.connect(self.actual_start.setEnabled)
        self.planned_budget=_money_spin(self.item.get("planned_budget")); self.actual_cost=_money_spin(self.item.get("actual_cost"))
        self.planned_progress=_percent_spin(self.item.get("planned_progress")); self.actual_progress=_percent_spin(self.item.get("actual_progress"))
        self.priority=QComboBox(); self.priority.addItems(db.PROJECT_PRIORITIES); self.priority.setCurrentText(self.item.get("priority") or "عادی")
        self.status=QComboBox(); self.status.addItems(db.PROJECT_STATUSES); self.status.setCurrentText(self.item.get("status") or "برنامه‌ریزی‌شده")
        self.description=QTextEdit(self.item.get("description") or ""); self.description.setMinimumHeight(110)
        form.addRow("برنامه بالادستی:",self.program); form.addRow("بلوک:",self.zone); form.addRow("کد پروژه:",self.code)
        form.addRow("عنوان پروژه:",self.title); form.addRow("دستگاه مسئول:",self.agency); form.addRow("مدیر پروژه:",self.manager)
        form.addRow("شروع برنامه‌ای:",self.start); form.addRow("پایان برنامه‌ای:",self.end); form.addRow("",self.actual_start_enabled)
        form.addRow("شروع واقعی:",self.actual_start); form.addRow("بودجه برنامه‌ای:",self.planned_budget); form.addRow("هزینه واقعی:",self.actual_cost)
        form.addRow("پیشرفت برنامه‌ای:",self.planned_progress); form.addRow("پیشرفت واقعی:",self.actual_progress)
        form.addRow("اولویت:",self.priority); form.addRow("وضعیت:",self.status); form.addRow("توضیحات:",self.description)
        layout.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ذخیره پروژه"); buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        buttons.accepted.connect(self.validate); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def validate(self):
        if not self.title.text().strip(): QMessageBox.warning(self,"اطلاعات ناقص","عنوان پروژه الزامی است."); return
        if self.end.date()<self.start.date(): QMessageBox.warning(self,"تاریخ نامعتبر","پایان پروژه قبل از شروع است."); return
        self.accept()

    def values(self):
        return dict(program_id=self.program.currentData(),zone_id=self.zone.currentData(),project_code=self.code.text().strip() or None,
                    title=self.title.text().strip(),responsible_agency=self.agency.text(),project_manager=self.manager.text().strip(),
                    start_date=self.start.date().toString("yyyy-MM-dd"),end_date=self.end.date().toString("yyyy-MM-dd"),
                    actual_start_date=self.actual_start.date().toString("yyyy-MM-dd") if self.actual_start_enabled.isChecked() else None,
                    planned_budget=self.planned_budget.value(),actual_cost=self.actual_cost.value(),planned_progress=self.planned_progress.value(),
                    actual_progress=self.actual_progress.value(),priority=self.priority.currentText(),status=self.status.currentText(),
                    description=self.description.toPlainText().strip())


class MilestoneDialog(QDialog):
    def __init__(self, db, projects, item=None, parent=None):
        super().__init__(parent); self.db=db; self.item=item or {}
        self.setWindowTitle("نقطه عطف پروژه"); layout=QVBoxLayout(self); form=QFormLayout()
        self.project=QComboBox()
        for p in projects: self.project.addItem(f"{p['project_code']} — {p['title']}",p['id'])
        if self.item.get("project_id") is not None:
            idx=self.project.findData(self.item.get("project_id")); self.project.setCurrentIndex(max(0,idx))
        self.title=QLineEdit(self.item.get("title") or ""); self.due=_date_edit(self.item.get("due_date"),QDate.currentDate().addDays(30))
        self.weight=QDoubleSpinBox(); self.weight.setRange(0.1,100); self.weight.setValue(float(self.item.get("weight") or 1))
        self.status=QComboBox(); self.status.addItems(db.MILESTONE_STATUSES); self.status.setCurrentText(self.item.get("status") or "در انتظار")
        self.notes=QTextEdit(self.item.get("notes") or ""); self.notes.setMinimumHeight(100)
        form.addRow("پروژه:",self.project); form.addRow("عنوان:",self.title); form.addRow("سررسید:",self.due)
        form.addRow("وزن:",self.weight); form.addRow("وضعیت:",self.status); form.addRow("توضیحات:",self.notes); layout.addLayout(form)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.validate); b.rejected.connect(self.reject); layout.addWidget(b)
    def validate(self):
        if not self.title.text().strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "عنوان نقطه عطف الزامی است."); return
        self.accept()
    def values(self):
        status=self.status.currentText(); completed=date.today().isoformat() if status=="تکمیل‌شده" else self.item.get("completed_date")
        return dict(project_id=self.project.currentData(),title=self.title.text().strip(),due_date=self.due.date().toString("yyyy-MM-dd"),
                    completed_date=completed,weight=self.weight.value(),status=status,notes=self.notes.toPlainText().strip())


class ProgressDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent); self.project=project
        self.setWindowTitle(f"گزارش پیشرفت — {project['title']}"); self.resize(620,560)
        layout=QVBoxLayout(self); form=QFormLayout()
        self.report_date=_date_edit(None,QDate.currentDate()); self.planned=_percent_spin(project.get("planned_progress")); self.actual=_percent_spin(project.get("actual_progress")); self.cost=_money_spin(project.get("actual_cost"))
        self.summary=QTextEdit(); self.obstacles=QTextEdit(); self.next_steps=QTextEdit()
        form.addRow("تاریخ گزارش:",self.report_date); form.addRow("پیشرفت برنامه‌ای:",self.planned); form.addRow("پیشرفت واقعی:",self.actual)
        form.addRow("هزینه تجمعی:",self.cost); form.addRow("خلاصه وضعیت:",self.summary); form.addRow("موانع:",self.obstacles); form.addRow("گام بعدی:",self.next_steps)
        layout.addLayout(form); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); layout.addWidget(b)
    def values(self):
        return dict(report_date=self.report_date.date().toString("yyyy-MM-dd"),planned_progress=self.planned.value(),actual_progress=self.actual.value(),actual_cost=self.cost.value(),summary=self.summary.toPlainText().strip(),obstacles=self.obstacles.toPlainText().strip(),next_steps=self.next_steps.toPlainText().strip())


class IndicatorDialog(QDialog):
    def __init__(self, db, programs, projects, item=None, parent=None):
        super().__init__(parent); self.db=db; self.item=item or {}; self.setWindowTitle("شاخص عملکرد")
        layout=QVBoxLayout(self); form=QFormLayout()
        self.entity=QComboBox(); self.entity.addItem("— انتخاب برنامه یا پروژه —",(None,None))
        for p in programs:self.entity.addItem(f"برنامه: {p['title']}",(p['id'],None))
        for p in projects:self.entity.addItem(f"پروژه: {p['project_code']} — {p['title']}",(None,p['id']))
        target=(self.item.get("program_id"),self.item.get("project_id")); idx=self.entity.findData(target)
        if idx>=0:self.entity.setCurrentIndex(idx)
        self.title=QLineEdit(self.item.get("title") or ""); self.unit=QLineEdit(self.item.get("unit") or "")
        self.baseline=QDoubleSpinBox(); self.baseline.setRange(-999999999,999999999); self.baseline.setValue(float(self.item.get("baseline_value") or 0))
        self.target=QDoubleSpinBox(); self.target.setRange(-999999999,999999999); self.target.setValue(float(self.item.get("target_value") or 0))
        self.actual=QDoubleSpinBox(); self.actual.setRange(-999999999,999999999); self.actual.setValue(float(self.item.get("actual_value") or 0))
        self.direction=QComboBox(); self.direction.addItems(["افزایشی","کاهشی"]); self.direction.setCurrentText(self.item.get("direction") or "افزایشی")
        self.weight=QDoubleSpinBox(); self.weight.setRange(0.1,100); self.weight.setValue(float(self.item.get("weight") or 1))
        self.measurement=_date_edit(self.item.get("measurement_date"),QDate.currentDate()); self.notes=QTextEdit(self.item.get("notes") or "")
        for label,widget in [("اتصال:",self.entity),("عنوان:",self.title),("واحد:",self.unit),("مقدار مبنا:",self.baseline),("مقدار هدف:",self.target),("عملکرد واقعی:",self.actual),("جهت مطلوب:",self.direction),("وزن:",self.weight),("تاریخ اندازه‌گیری:",self.measurement),("یادداشت:",self.notes)]:form.addRow(label,widget)
        layout.addLayout(form); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.validate); b.rejected.connect(self.reject); layout.addWidget(b)
    def validate(self):
        if self.entity.currentIndex()==0 or not self.title.text().strip(): QMessageBox.warning(self,"اطلاعات ناقص","اتصال و عنوان شاخص الزامی است."); return
        self.accept()
    def values(self):
        program_id,project_id=self.entity.currentData()
        return dict(program_id=program_id,project_id=project_id,title=self.title.text().strip(),unit=self.unit.text().strip(),baseline_value=self.baseline.value(),target_value=self.target.value(),actual_value=self.actual.value(),direction=self.direction.currentText(),weight=self.weight.value(),measurement_date=self.measurement.date().toString("yyyy-MM-dd"),notes=self.notes.toPlainText().strip())


class RiskDialog(QDialog):
    def __init__(self, db, programs, projects, item=None, parent=None):
        super().__init__(parent); self.db=db; self.item=item or {}; self.setWindowTitle("ریسک پروژه")
        self.resize(650,600); layout=QVBoxLayout(self); form=QFormLayout()
        self.entity=QComboBox(); self.entity.addItem("ریسک عمومی سبد",(None,None))
        for p in programs:self.entity.addItem(f"برنامه: {p['title']}",(p['id'],None))
        for p in projects:self.entity.addItem(f"پروژه: {p['project_code']} — {p['title']}",(None,p['id']))
        idx=self.entity.findData((self.item.get("program_id"),self.item.get("project_id")))
        if idx>=0:self.entity.setCurrentIndex(idx)
        self.title=QLineEdit(self.item.get("title") or ""); self.category=QComboBox(); self.category.addItems(db.RISK_CATEGORIES); self.category.setCurrentText(self.item.get("category") or "اجرایی")
        self.probability=QSpinBox(); self.probability.setRange(1,5); self.probability.setValue(int(self.item.get("probability") or 1))
        self.impact=QSpinBox(); self.impact.setRange(1,5); self.impact.setValue(int(self.item.get("impact") or 1))
        self.owner=QLineEdit(self.item.get("owner") or ""); self.mitigation=QTextEdit(self.item.get("mitigation") or ""); self.contingency=QTextEdit(self.item.get("contingency") or "")
        self.review=_date_edit(self.item.get("review_date"),QDate.currentDate().addDays(30)); self.status=QComboBox(); self.status.addItems(db.RISK_STATUSES); self.status.setCurrentText(self.item.get("status") or "باز")
        for label,w in [("اتصال:",self.entity),("عنوان ریسک:",self.title),("دسته:",self.category),("احتمال ۱ تا ۵:",self.probability),("اثر ۱ تا ۵:",self.impact),("مالک ریسک:",self.owner),("اقدام پیشگیرانه:",self.mitigation),("برنامه واکنش:",self.contingency),("تاریخ بازبینی:",self.review),("وضعیت:",self.status)]:form.addRow(label,w)
        layout.addLayout(form); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.validate); b.rejected.connect(self.reject); layout.addWidget(b)
    def validate(self):
        if not self.title.text().strip(): QMessageBox.warning(self,"اطلاعات ناقص","عنوان ریسک الزامی است."); return
        self.accept()
    def values(self):
        program_id,project_id=self.entity.currentData()
        return dict(program_id=program_id,project_id=project_id,title=self.title.text().strip(),category=self.category.currentText(),probability=self.probability.value(),impact=self.impact.value(),owner=self.owner.text().strip(),mitigation=self.mitigation.toPlainText().strip(),contingency=self.contingency.toPlainText().strip(),review_date=self.review.date().toString("yyyy-MM-dd"),status=self.status.currentText())


class ChangeDialog(QDialog):
    FIELD_OPTIONS = [
        ("بدون اعمال خودکار",None),("تاریخ پایان","end_date"),("تاریخ شروع","start_date"),
        ("بودجه","planned_budget"),("مدیر/مسئول","project_manager"),("دستگاه مسئول","responsible_agency"),
        ("شرح","description"),("اولویت","priority")
    ]
    def __init__(self, db, programs, projects, item=None, parent=None):
        super().__init__(parent); self.db=db; self.item=item or {}; self.setWindowTitle("درخواست تغییر")
        self.resize(650,650); layout=QVBoxLayout(self); form=QFormLayout()
        self.entity=QComboBox()
        for p in programs:self.entity.addItem(f"برنامه: {p['title']}",(p['id'],None))
        for p in projects:self.entity.addItem(f"پروژه: {p['project_code']} — {p['title']}",(None,p['id']))
        idx=self.entity.findData((self.item.get("program_id"),self.item.get("project_id")))
        if idx>=0:self.entity.setCurrentIndex(idx)
        self.title=QLineEdit(self.item.get("title") or ""); self.change_type=QComboBox(); self.change_type.addItems(db.CHANGE_TYPES); self.change_type.setCurrentText(self.item.get("change_type") or "دامنه")
        self.target_field=QComboBox()
        for title,value in self.FIELD_OPTIONS:self.target_field.addItem(title,value)
        if self.item.get("target_field") is not None:
            idx=self.target_field.findData(self.item.get("target_field")); self.target_field.setCurrentIndex(max(0,idx))
        self.reason=QTextEdit(self.item.get("reason") or ""); self.requested_by=QLineEdit(self.item.get("requested_by") or "")
        self.request_date=_date_edit(self.item.get("request_date"),QDate.currentDate()); self.impact_days=QSpinBox(); self.impact_days.setRange(-3650,3650); self.impact_days.setValue(int(self.item.get("impact_days") or 0))
        self.impact_cost=_money_spin(self.item.get("impact_cost")); self.old_value=QLineEdit(self.item.get("old_value") or ""); self.new_value=QLineEdit(self.item.get("new_value") or "")
        for label,w in [("برنامه/پروژه:",self.entity),("عنوان:",self.title),("نوع تغییر:",self.change_type),("فیلد قابل اعمال:",self.target_field),("دلیل:",self.reason),("درخواست‌کننده:",self.requested_by),("تاریخ درخواست:",self.request_date),("اثر زمانی - روز:",self.impact_days),("اثر هزینه:",self.impact_cost),("مقدار قبلی:",self.old_value),("مقدار جدید:",self.new_value)]:form.addRow(label,w)
        layout.addLayout(form); b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.validate); b.rejected.connect(self.reject); layout.addWidget(b)
    def validate(self):
        if not self.title.text().strip(): QMessageBox.warning(self,"اطلاعات ناقص","عنوان تغییر الزامی است."); return
        self.accept()
    def values(self):
        program_id,project_id=self.entity.currentData()
        return dict(program_id=program_id,project_id=project_id,title=self.title.text().strip(),change_type=self.change_type.currentText(),target_field=self.target_field.currentData(),reason=self.reason.toPlainText().strip(),requested_by=self.requested_by.text().strip(),request_date=self.request_date.date().toString("yyyy-MM-dd"),impact_days=self.impact_days.value(),impact_cost=self.impact_cost.value(),old_value=self.old_value.text().strip(),new_value=self.new_value.text().strip())


class ProjectControlWindow(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db):
        super().__init__(); self.db=db; self.current_user=db.get_current_user() or {}
        role=self.current_user.get("role"); self.can_manage=role in {"admin","manager"}; self.can_update=role in {"admin","manager","field"}
        self.program_rows=[]; self.project_rows=[]; self.milestone_rows=[]; self.indicator_rows=[]; self.risk_rows=[]; self.change_rows=[]; self.alert_rows=[]
        self.setWindowTitle("برنامه عملیاتی و کنترل پروژه"); self.resize(1440,900)
        self._build_ui(); self.refresh_all()

    def _build_ui(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.addWidget(build_official_header("برنامه عملیاتی و کنترل پروژه",self.db))
        toolbar=QFrame(); row=QHBoxLayout(toolbar); title=QLabel("برنامه سالانه، سبد پروژه، گانت، ریسک و کنترل تغییرات"); title.setStyleSheet("font-size:16px;font-weight:800;color:#13294b;")
        row.addWidget(title); row.addStretch(); refresh=QPushButton("بروزرسانی"); set_button_style(refresh,"refresh","secondary"); refresh.clicked.connect(self.refresh_all); row.addWidget(refresh)
        back=QPushButton("بازگشت به داشبورد"); set_button_style(back,"back","ghost"); back.clicked.connect(self.back_requested.emit); row.addWidget(back); root.addWidget(toolbar)
        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)
        self._build_overview_tab(); self._build_programs_tab(); self._build_projects_tab(); self._build_gantt_tab(); self._build_milestones_indicators_tab(); self._build_risks_tab(); self._build_changes_tab(); self._build_reports_tab()

    def _build_overview_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); self.summary_grid=QGridLayout(); self.summary_labels={}
        specs=[("programs_count","برنامه‌ها"),("projects_count","پروژه‌ها"),("active_projects","پروژه فعال"),("overdue_projects","پروژه معوق"),("average_progress","میانگین پیشرفت"),("indicator_achievement","تحقق شاخص"),("planned_budget","بودجه برنامه‌ای"),("actual_cost","هزینه واقعی"),("high_risks","ریسک بالا"),("pending_changes","تغییر در انتظار"),("alerts_count","هشدار باز")]
        for idx,(key,label) in enumerate(specs):
            card=QFrame(); card.setObjectName("StatCard"); c=QVBoxLayout(card); value=QLabel("۰"); value.setStyleSheet("font-size:24px;font-weight:800;color:#13294b;"); caption=QLabel(label); caption.setStyleSheet("color:#647184;"); c.addWidget(value); c.addWidget(caption); self.summary_labels[key]=value; self.summary_grid.addWidget(card,idx//4,idx%4)
        layout.addLayout(self.summary_grid)
        self.alert_table=_table(["شدت","نوع","عنوان","بلوک","سررسید","پیام"],stretch=(2,5)); layout.addWidget(QLabel("هشدارهای کنترل پروژه")); layout.addWidget(self.alert_table,1)
        self.tabs.addTab(tab,"نمای مدیریتی")

    def _build_programs_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); row=QHBoxLayout()
        self.year_filter=QLineEdit(); self.year_filter.setPlaceholderText("سال مالی؛ خالی = همه"); self.year_filter.setMaximumWidth(160); self.year_filter.returnPressed.connect(self.refresh_programs)
        row.addWidget(QLabel("سال مالی:")); row.addWidget(self.year_filter); row.addStretch()
        for text,slot,danger in [("ثبت برنامه جدید",self.add_program,False),("ویرایش برنامه",self.edit_program,False),("حذف برنامه",self.delete_program,True)]:
            b=QPushButton(text); b.clicked.connect(slot); b.setEnabled(self.can_manage); b.setProperty("danger",danger); row.addWidget(b)
        layout.addLayout(row); self.program_table=_table(["سال","عنوان","هدف راهبردی","بلوک","دستگاه","مدیر","شروع","پایان","بودجه","پیشرفت","وضعیت","پروژه"],stretch=(1,2)); self.program_table.doubleClicked.connect(lambda _i:self.edit_program()); layout.addWidget(self.program_table,1)
        self.tabs.addTab(tab,"برنامه عملیاتی")

    def _build_projects_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); row=QHBoxLayout()
        self.project_program_filter=QComboBox(); self.project_program_filter.currentIndexChanged.connect(self.refresh_projects); row.addWidget(QLabel("برنامه:")); row.addWidget(self.project_program_filter)
        self.project_search=QLineEdit(); self.project_search.setPlaceholderText("جستجو کد، عنوان، مدیر یا دستگاه"); self.project_search.returnPressed.connect(self.refresh_projects); row.addWidget(self.project_search); row.addStretch()
        actions=[("ثبت پروژه",self.add_project,self.can_manage,False),("ویرایش",self.edit_project,self.can_manage,False),("گزارش پیشرفت",self.add_progress,self.can_update,False),("حذف",self.delete_project,self.can_manage,True)]
        for text,slot,enabled,danger in actions:
            b=QPushButton(text); b.clicked.connect(slot); b.setEnabled(enabled); b.setProperty("danger",danger); row.addWidget(b)
        layout.addLayout(row); self.project_table=_table(["کد","عنوان","برنامه","بلوک","دستگاه","مدیر","شروع","پایان","بودجه","هزینه","برنامه٪","واقعی٪","انحراف","ریسک","اولویت","وضعیت"],stretch=(1,2)); self.project_table.doubleClicked.connect(lambda _i:self.edit_project()); layout.addWidget(self.project_table,1)
        self.tabs.addTab(tab,"پروژه‌ها")

    def _build_gantt_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); row=QHBoxLayout()
        self.gantt_from=_date_edit(None,QDate.currentDate().addMonths(-2)); self.gantt_to=_date_edit(None,QDate.currentDate().addMonths(10)); row.addWidget(QLabel("از:")); row.addWidget(self.gantt_from); row.addWidget(QLabel("تا:")); row.addWidget(self.gantt_to)
        b=QPushButton("ساخت گانت"); b.clicked.connect(self.refresh_gantt); row.addWidget(b); row.addStretch(); layout.addLayout(row)
        self.gantt_table=QTableWidget(); self.gantt_table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.gantt_table.setAlternatingRowColors(True); layout.addWidget(self.gantt_table,1); self.tabs.addTab(tab,"نمودار گانت")

    def _build_milestones_indicators_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); split=QSplitter(Qt.Vertical)
        top=QWidget(); tl=QVBoxLayout(top); row=QHBoxLayout(); row.addWidget(QLabel("نقاط عطف")); row.addStretch()
        for text,slot,danger in [("ثبت نقطه عطف",self.add_milestone,False),("ویرایش",self.edit_milestone,False),("حذف",self.delete_milestone,True)]:
            b=QPushButton(text); b.clicked.connect(slot); b.setEnabled(self.can_manage); b.setProperty("danger",danger); row.addWidget(b)
        tl.addLayout(row); self.milestone_table=_table(["کد پروژه","پروژه","عنوان","بلوک","سررسید","تکمیل","وزن","وضعیت","معوق"],stretch=(1,2)); tl.addWidget(self.milestone_table); split.addWidget(top)
        bottom=QWidget(); bl=QVBoxLayout(bottom); row=QHBoxLayout(); row.addWidget(QLabel("شاخص‌های هدف و تحقق")); row.addStretch()
        for text,slot,danger in [("ثبت شاخص",self.add_indicator,False),("ویرایش",self.edit_indicator,False),("حذف",self.delete_indicator,True)]:
            b=QPushButton(text); b.clicked.connect(slot); b.setEnabled(self.can_manage); b.setProperty("danger",danger); row.addWidget(b)
        bl.addLayout(row); self.indicator_table=_table(["برنامه","پروژه","شاخص","واحد","مبنا","هدف","واقعی","جهت","تحقق٪","تاریخ"],stretch=(2,)); bl.addWidget(self.indicator_table); split.addWidget(bottom); split.setSizes([350,350]); layout.addWidget(split,1); self.tabs.addTab(tab,"نقاط عطف و شاخص‌ها")

    def _build_risks_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); row=QHBoxLayout(); row.addStretch()
        for text,slot,danger in [("ثبت ریسک",self.add_risk,False),("ویرایش",self.edit_risk,False),("حذف",self.delete_risk,True)]:
            b=QPushButton(text); b.clicked.connect(slot); b.setEnabled(self.can_manage); b.setProperty("danger",danger); row.addWidget(b)
        layout.addLayout(row); self.risk_table=_table(["برنامه","پروژه","بلوک","عنوان","دسته","احتمال","اثر","امتیاز","سطح","مالک","بازبینی","وضعیت"],stretch=(3,)); layout.addWidget(self.risk_table,1); self.tabs.addTab(tab,"دفتر ریسک")

    def _build_changes_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); row=QHBoxLayout(); row.addStretch()
        actions=[("ثبت درخواست تغییر",self.add_change,self.can_update,False),("تأیید",lambda:self.review_change("تأییدشده"),self.can_manage,False),("رد",lambda:self.review_change("ردشده"),self.can_manage,False),("تأیید و اعمال",lambda:self.review_change("تأییدشده",True),self.can_manage,False),("حذف",self.delete_change,self.can_manage,True)]
        for text,slot,enabled,danger in actions:
            b=QPushButton(text); b.clicked.connect(slot); b.setEnabled(enabled); b.setProperty("danger",danger); row.addWidget(b)
        layout.addLayout(row); self.change_table=_table(["برنامه","پروژه","عنوان","نوع","فیلد","درخواست‌کننده","تاریخ","روز","اثر هزینه","قبل","بعد","وضعیت","بررسی‌کننده"],stretch=(2,)); layout.addWidget(self.change_table,1); self.tabs.addTab(tab,"کنترل تغییرات")

    def _build_reports_tab(self):
        tab=QWidget(); layout=QVBoxLayout(tab); box=QGroupBox("گزارش سبد پروژه"); row=QHBoxLayout(box)
        self.report_year=QLineEdit(); self.report_year.setPlaceholderText("سال مالی؛ خالی = همه"); row.addWidget(QLabel("سال مالی:")); row.addWidget(self.report_year)
        for text,slot in [("خروجی PDF",self.export_pdf),("خروجی Excel",self.export_excel),("خروجی PowerPoint",self.export_pptx)]:
            b=QPushButton(text); b.clicked.connect(slot); row.addWidget(b)
        row.addStretch(); layout.addWidget(box); self.report_hint=QLabel("گزارش شامل داشبورد، پروژه‌ها، شاخص‌ها، ریسک‌ها، تغییرات، هشدارها و گانت است."); self.report_hint.setWordWrap(True); layout.addWidget(self.report_hint); layout.addStretch(); self.tabs.addTab(tab,"گزارش‌ها")

    def refresh_all(self):
        self._refresh_program_filters(); self.refresh_programs(); self.refresh_projects(); self.refresh_milestones(); self.refresh_indicators(); self.refresh_risks(); self.refresh_changes(); self.refresh_overview(); self.refresh_gantt()

    def _refresh_program_filters(self):
        current=self.project_program_filter.currentData() if self.project_program_filter.count() else None
        self.project_program_filter.blockSignals(True); self.project_program_filter.clear(); self.project_program_filter.addItem("همه برنامه‌ها",None)
        for p in self.db.get_annual_programs(): self.project_program_filter.addItem(f"{p['fiscal_year']} — {p['title']}",p['id'])
        idx=self.project_program_filter.findData(current); self.project_program_filter.setCurrentIndex(max(0,idx)); self.project_program_filter.blockSignals(False)

    def refresh_overview(self):
        summary=self.db.get_project_control_summary(fiscal_year=self.year_filter.text().strip() or None)
        for key,label in self.summary_labels.items():
            value=summary.get(key,0)
            if key in {"planned_budget","actual_cost"}: text=f"{float(value):,.0f}"
            elif key in {"average_progress","indicator_achievement"}: text=f"{float(value):.1f}٪"
            else:text=str(value)
            label.setText(text)
        self.alert_rows=self.db.get_project_control_alerts(fiscal_year=self.year_filter.text().strip() or None)
        self.alert_table.setRowCount(len(self.alert_rows)); colors={"بحرانی":"#ffd7d7","فوری":"#ffe5c2","مهم":"#fff5c4"}
        for r,a in enumerate(self.alert_rows):
            vals=[a.get("severity"),a.get("type"),a.get("title"),a.get("zone_name"),a.get("due_date"),a.get("message")]
            for c,v in enumerate(vals):
                cell=QTableWidgetItem(convert_dates_in_text(str(v or "—"))); cell.setBackground(QColor(colors.get(a.get("severity"),"#ffffff"))); self.alert_table.setItem(r,c,cell)

    def refresh_programs(self):
        self.program_rows=self.db.get_annual_programs(fiscal_year=self.year_filter.text().strip() or None)
        self.program_table.setRowCount(len(self.program_rows))
        for r,p in enumerate(self.program_rows):
            vals=[p.get("fiscal_year"),p.get("title"),p.get("strategic_goal"),p.get("zone_name"),p.get("responsible_agency"),p.get("program_manager"),format_jalali(p.get("start_date")),format_jalali(p.get("end_date")),f"{float(p.get('approved_budget') or 0):,.0f}",f"{float(p.get('progress_percent') or 0):.1f}٪",p.get("status"),p.get("project_count")]
            for c,v in enumerate(vals):self.program_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(v or "—"))))

    def refresh_projects(self):
        self.project_rows=self.db.get_projects(program_id=self.project_program_filter.currentData(),query=self.project_search.text().strip() or None)
        self.project_table.setRowCount(len(self.project_rows))
        for r,p in enumerate(self.project_rows):
            vals=[p.get("project_code"),p.get("title"),p.get("program_title"),p.get("zone_name"),p.get("responsible_agency"),p.get("project_manager"),format_jalali(p.get("start_date")),format_jalali(p.get("end_date")),f"{float(p.get('planned_budget') or 0):,.0f}",f"{float(p.get('actual_cost') or 0):,.0f}",f"{float(p.get('planned_progress') or 0):.1f}",f"{float(p.get('actual_progress') or 0):.1f}",f"{float(p.get('progress_variance') or 0):+.1f}",p.get("open_risk_count"),p.get("priority"),p.get("status")]
            for c,v in enumerate(vals):
                cell=QTableWidgetItem(convert_dates_in_text(str(v or "—")));
                if p.get("is_overdue"):cell.setBackground(QColor("#ffd7d7"))
                elif float(p.get("progress_variance") or 0)<-10:cell.setBackground(QColor("#fff5c4"))
                self.project_table.setItem(r,c,cell)

    def refresh_milestones(self):
        self.milestone_rows=self.db.get_project_milestones(); self.milestone_table.setRowCount(len(self.milestone_rows))
        for r,m in enumerate(self.milestone_rows):
            vals=[m.get("project_code"),m.get("project_title"),m.get("title"),m.get("zone_name"),format_jalali(m.get("due_date")),format_jalali(m.get("completed_date")),m.get("weight"),m.get("status"),"بله" if m.get("is_overdue") else "خیر"]
            for c,v in enumerate(vals):
                cell=QTableWidgetItem(convert_dates_in_text(str(v or "—")));
                if m.get("is_overdue"):cell.setBackground(QColor("#ffd7d7"))
                self.milestone_table.setItem(r,c,cell)

    def refresh_indicators(self):
        self.indicator_rows=self.db.get_project_indicators(); self.indicator_table.setRowCount(len(self.indicator_rows))
        for r,i in enumerate(self.indicator_rows):
            vals=[i.get("program_title"),i.get("project_title"),i.get("title"),i.get("unit"),i.get("baseline_value"),i.get("target_value"),i.get("actual_value"),i.get("direction"),f"{float(i.get('achievement_percent') or 0):.1f}",format_jalali(i.get("measurement_date"))]
            for c,v in enumerate(vals):self.indicator_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(v or "—"))))

    def refresh_risks(self):
        self.risk_rows=self.db.get_project_risks(); self.risk_table.setRowCount(len(self.risk_rows)); colors={"بحرانی":"#ffd7d7","زیاد":"#ffe5c2","متوسط":"#fff5c4","کم":"#e9f7ef"}
        for r,i in enumerate(self.risk_rows):
            vals=[i.get("program_title"),i.get("project_title"),i.get("zone_name"),i.get("title"),i.get("category"),i.get("probability"),i.get("impact"),i.get("risk_score"),i.get("risk_level"),i.get("owner"),format_jalali(i.get("review_date")),i.get("status")]
            for c,v in enumerate(vals):cell=QTableWidgetItem(convert_dates_in_text(str(v or "—"))); cell.setBackground(QColor(colors.get(i.get("risk_level"),"#fff"))); self.risk_table.setItem(r,c,cell)

    def refresh_changes(self):
        self.change_rows=self.db.get_project_change_requests(); self.change_table.setRowCount(len(self.change_rows))
        for r,i in enumerate(self.change_rows):
            vals=[i.get("program_title"),i.get("project_title"),i.get("title"),i.get("change_type"),i.get("target_field"),i.get("requested_by"),format_jalali(i.get("request_date")),i.get("impact_days"),f"{float(i.get('impact_cost') or 0):,.0f}",i.get("old_value"),i.get("new_value"),i.get("status"),i.get("reviewed_by_name")]
            for c,v in enumerate(vals):self.change_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(v or "—"))))

    def refresh_gantt(self):
        start=self.gantt_from.date(); end=self.gantt_to.date()
        if end<start:return
        months=[]; cursor=QDate(start.year(),start.month(),1)
        while cursor<=end and len(months)<24:
            months.append(cursor); cursor=cursor.addMonths(1)
        headers=["کد","عنوان","شروع","پایان","پیشرفت"]+[m.toString("yyyy-MM") for m in months]
        data=self.db.get_project_gantt_data(start.toString("yyyy-MM-dd"),end.toString("yyyy-MM-dd"))
        self.gantt_table.clear(); self.gantt_table.setColumnCount(len(headers)); self.gantt_table.setHorizontalHeaderLabels(headers); self.gantt_table.setRowCount(len(data)); self.gantt_table.verticalHeader().setVisible(False)
        self.gantt_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.gantt_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for r,item in enumerate(data):
            base=[item.get("code"),("↳ " if item.get("kind")=="milestone" else "")+str(item.get("title") or ""),format_jalali(item.get("start_date")),format_jalali(item.get("end_date")),f"{float(item.get('progress') or 0):.0f}٪"]
            for c,v in enumerate(base):self.gantt_table.setItem(r,c,QTableWidgetItem(convert_dates_in_text(str(v or "—"))))
            try:s=QDate.fromString(item.get("start_date") or "","yyyy-MM-dd"); e=QDate.fromString(item.get("end_date") or "","yyyy-MM-dd")
            except Exception:s=e=QDate()
            for idx,m in enumerate(months,5):
                cell=QTableWidgetItem("")
                month_end=m.addMonths(1).addDays(-1)
                if s.isValid() and e.isValid() and not (e<m or s>month_end):cell.setBackground(QColor("#c9a227" if item.get("kind")=="project" else "#4b78a8"))
                self.gantt_table.setItem(r,idx,cell)

    def _selected(self,table,rows):
        r=table.currentRow(); return rows[r] if 0<=r<len(rows) else None
    def add_program(self):
        d=ProgramDialog(self.db,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.add_annual_program(**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def edit_program(self):
        item=self._selected(self.program_table,self.program_rows)
        if not item:QMessageBox.information(self,"انتخاب","ابتدا یک برنامه را انتخاب کنید.");return
        d=ProgramDialog(self.db,item,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.update_annual_program(item["id"],**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def delete_program(self):
        item=self._selected(self.program_table,self.program_rows)
        if item and QMessageBox.question(self,"حذف","برنامه حذف شود؟ پروژه‌های آن حذف نمی‌شوند و فقط اتصالشان برداشته می‌شود.",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.db.delete_annual_program(item["id"]);self.refresh_all()
    def add_project(self):
        d=ProjectDialog(self.db,preselected_program=self.project_program_filter.currentData(),parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.add_project(**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def edit_project(self):
        item=self._selected(self.project_table,self.project_rows)
        if not item:QMessageBox.information(self,"انتخاب","ابتدا پروژه را انتخاب کنید.");return
        d=ProjectDialog(self.db,item,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.update_project(item["id"],**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def add_progress(self):
        item=self._selected(self.project_table,self.project_rows)
        if not item:QMessageBox.information(self,"انتخاب","ابتدا پروژه را انتخاب کنید.");return
        d=ProgressDialog(item,self)
        if d.exec_()==QDialog.Accepted:
            try:self.db.add_project_progress_update(item["id"],**d.values());self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def delete_project(self):
        item=self._selected(self.project_table,self.project_rows)
        if item and QMessageBox.question(self,"حذف پروژه","پروژه و تمام نقاط عطف، شاخص‌ها، ریسک‌ها و تغییرات وابسته حذف شوند؟",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.db.delete_project(item["id"]);self.refresh_all()
    def add_milestone(self):
        projects=self.db.get_projects();
        if not projects:QMessageBox.warning(self,"بدون پروژه","ابتدا یک پروژه ثبت کنید.");return
        d=MilestoneDialog(self.db,projects,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:
                self.db.add_project_milestone(**d.values()); self.refresh_all()
            except Exception as e:
                QMessageBox.critical(self,"خطا",str(e))
    def edit_milestone(self):
        item=self._selected(self.milestone_table,self.milestone_rows)
        if not item:return
        d=MilestoneDialog(self.db,self.db.get_projects(),item,self)
        if d.exec_()==QDialog.Accepted:
            try:
                vals=d.values(); vals.pop("project_id",None); self.db.update_project_milestone(item["id"],**vals); self.refresh_all()
            except Exception as e:
                QMessageBox.critical(self,"خطا",str(e))
    def delete_milestone(self):
        item=self._selected(self.milestone_table,self.milestone_rows)
        if item and QMessageBox.question(self,"حذف","نقطه عطف حذف شود؟",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.db.delete_project_milestone(item["id"]);self.refresh_all()
    def add_indicator(self):
        d=IndicatorDialog(self.db,self.db.get_annual_programs(),self.db.get_projects(),parent=self)
        if d.exec_()==QDialog.Accepted:
            try: self.db.add_project_indicator(**d.values()); self.refresh_all()
            except Exception as e: QMessageBox.critical(self,"خطا",str(e))
    def edit_indicator(self):
        item=self._selected(self.indicator_table,self.indicator_rows)
        if not item:return
        d=IndicatorDialog(self.db,self.db.get_annual_programs(),self.db.get_projects(),item,self)
        if d.exec_()==QDialog.Accepted:
            try: self.db.update_project_indicator(item["id"],**d.values()); self.refresh_all()
            except Exception as e: QMessageBox.critical(self,"خطا",str(e))
    def delete_indicator(self):
        item=self._selected(self.indicator_table,self.indicator_rows)
        if item and QMessageBox.question(self,"حذف","شاخص حذف شود؟",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.db.delete_project_indicator(item["id"]);self.refresh_all()
    def add_risk(self):
        d=RiskDialog(self.db,self.db.get_annual_programs(),self.db.get_projects(),parent=self)
        if d.exec_()==QDialog.Accepted:
            try: self.db.add_project_risk(**d.values()); self.refresh_all()
            except Exception as e: QMessageBox.critical(self,"خطا",str(e))
    def edit_risk(self):
        item=self._selected(self.risk_table,self.risk_rows)
        if not item:return
        d=RiskDialog(self.db,self.db.get_annual_programs(),self.db.get_projects(),item,self)
        if d.exec_()==QDialog.Accepted:
            try: self.db.update_project_risk(item["id"],**d.values()); self.refresh_all()
            except Exception as e: QMessageBox.critical(self,"خطا",str(e))
    def delete_risk(self):
        item=self._selected(self.risk_table,self.risk_rows)
        if item and QMessageBox.question(self,"حذف","ریسک حذف شود؟",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.db.delete_project_risk(item["id"]);self.refresh_all()
    def add_change(self):
        if not self.db.get_annual_programs() and not self.db.get_projects():QMessageBox.warning(self,"اطلاعات ناقص","ابتدا برنامه یا پروژه ثبت کنید.");return
        d=ChangeDialog(self.db,self.db.get_annual_programs(),self.db.get_projects(),parent=self)
        if d.exec_()==QDialog.Accepted:
            try: self.db.add_project_change_request(**d.values()); self.refresh_all()
            except Exception as e: QMessageBox.critical(self,"خطا",str(e))
    def review_change(self,status,apply=False):
        item=self._selected(self.change_table,self.change_rows)
        if not item:QMessageBox.information(self,"انتخاب","ابتدا درخواست تغییر را انتخاب کنید.");return
        note,ok=QInputDialog.getMultiLineText(self,"نظر بررسی","توضیح تصمیم:",item.get("review_note") or "")
        if ok:
            try:self.db.review_project_change_request(item["id"],status,note,apply_change=apply);self.refresh_all()
            except Exception as e:QMessageBox.critical(self,"خطا",str(e))
    def delete_change(self):
        item=self._selected(self.change_table,self.change_rows)
        if item and QMessageBox.question(self,"حذف","درخواست تغییر حذف شود؟",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:self.db.delete_project_change_request(item["id"]);self.refresh_all()
    def _report_path(self,caption,extension):
        return QFileDialog.getSaveFileName(self,caption,f"project_control_{datetime.now().strftime('%Y%m%d')}.{extension}",f"*.{extension}")[0]
    def export_pdf(self):
        path=self._report_path("ذخیره PDF","pdf")
        if path:
            try: export_project_control_pdf(self.db,path,self.report_year.text().strip() or None); QMessageBox.information(self,"انجام شد",f"گزارش ذخیره شد:\n{path}")
            except Exception as e: QMessageBox.critical(self,"خطا در گزارش",str(e))
    def export_excel(self):
        path=self._report_path("ذخیره Excel","xlsx")
        if path:
            try: export_project_control_excel(self.db,path,self.report_year.text().strip() or None); QMessageBox.information(self,"انجام شد",f"گزارش ذخیره شد:\n{path}")
            except Exception as e: QMessageBox.critical(self,"خطا در گزارش",str(e))
    def export_pptx(self):
        path=self._report_path("ذخیره PowerPoint","pptx")
        if path:
            try: export_project_control_powerpoint(self.db,path,self.report_year.text().strip() or None); QMessageBox.information(self,"انجام شد",f"گزارش ذخیره شد:\n{path}")
            except Exception as e: QMessageBox.critical(self,"خطا در گزارش",str(e))
