# -*- coding: utf-8 -*-
"""مدیریت کمیته‌های شش‌گانه شورای پیشرفت محله برای هر بلوک."""

from PyQt5.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QTextEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QDialog, QDialogButtonBox,
    QCheckBox, QGroupBox, QSplitter, QFrame, QScrollArea
)

from header_widget import build_official_header
from jalali_widgets import JalaliDateEdit
from jalali_utils import iso_to_jalali, to_persian_digits
from ui_scroll import scroll_page
from icon_manager import get_icon, set_button_style
from committee_minutes_module import CommitteeMinutesDialog, JalaliPickerField, TimePickerField


def _display_date(value):
    return iso_to_jalali(value) if value else "—"


def _selected_id(table):
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    return item.data(Qt.UserRole) if item else None


COMMITTEE_CARD_ICONS = (
    "infrastructure",
    "health",
    "sport",
    "security",
    "support",
    "culture",
)


class CommitteeMetric(QFrame):
    """شاخص کوچک و یکدست داخل کارت کمیته."""

    def __init__(self, icon_name, label, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setObjectName("CommitteeMetric")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(32)
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(6)
        self.icon = QLabel()
        self.icon.setObjectName("CommitteeMetricIcon")
        self.icon.setFixedSize(16, 16)
        self.icon.setAlignment(Qt.AlignCenter)
        self.text = QLabel(label)
        self.text.setObjectName("CommitteeMetricText")
        self.text.setAlignment(Qt.AlignCenter)
        row.addWidget(self.icon)
        row.addWidget(self.text, 1)

    def set_text(self, text):
        self.text.setText(text)

    def set_tone(self, tone):
        self.icon.setPixmap(get_icon(self.icon_name, tone).pixmap(14, 14))


class CommitteeCard(QFrame):
    """کارت انتخاب کمیته با چیدمان ثابت، آیکون واضح و شاخص‌های هم‌اندازه."""

    clicked = pyqtSignal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.committee_id = None
        self.icon_name = COMMITTEE_CARD_ICONS[index]
        self._selected = False
        self._status = "فعال"
        self.setObjectName("CommitteeCard")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(142)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLayoutDirection(Qt.RightToLeft)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 13)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(11)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("CommitteeCardIcon")
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(42, 42)
        header.addWidget(self.icon_label, 0, Qt.AlignVCenter)

        self.title_label = QLabel("در حال بارگذاری...")
        self.title_label.setObjectName("CommitteeCardTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.title_label.setMinimumHeight(42)
        header.addWidget(self.title_label, 1)

        self.status_label = QLabel("فعال")
        self.status_label.setObjectName("CommitteeCardStatus")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumWidth(58)
        self.status_label.setMaximumHeight(30)
        header.addWidget(self.status_label, 0, Qt.AlignVCenter)
        root.addLayout(header)

        stats = QHBoxLayout()
        stats.setSpacing(8)
        self.members_metric = CommitteeMetric("users", "اعضا: ۰")
        self.meetings_metric = CommitteeMetric("calendar", "جلسات: ۰")
        self.resolutions_metric = CommitteeMetric("resolution", "مصوبات باز: ۰")
        stats.addWidget(self.members_metric, 1)
        stats.addWidget(self.meetings_metric, 1)
        stats.addWidget(self.resolutions_metric, 1)
        root.addLayout(stats)
        self._apply_visuals()

    def set_data(self, item, index=None):
        if index is not None:
            self.index = index
            self.icon_name = COMMITTEE_CARD_ICONS[index]
        self.committee_id = int(item["id"])
        self._status = item.get("status") or "فعال"
        self.title_label.setText(f"{to_persian_digits(self.index + 1)}. {item['title']}")
        self.status_label.setText(self._status)
        self.members_metric.set_text(f"اعضا: {to_persian_digits(item.get('members_count') or 0)}")
        self.meetings_metric.set_text(f"جلسات: {to_persian_digits(item.get('meetings_count') or 0)}")
        self.resolutions_metric.set_text(f"مصوبات باز: {to_persian_digits(item.get('pending_resolutions') or 0)}")
        self.setEnabled(True)
        self.setToolTip(f"بازکردن پرونده {item['title']}")
        self._apply_visuals()

    def set_empty(self):
        self.committee_id = None
        self._selected = False
        self._status = "نامشخص"
        self.title_label.setText(f"{to_persian_digits(self.index + 1)}. کمیته ایجاد نشده است")
        self.status_label.setText("نامشخص")
        self.members_metric.set_text("اعضا: ۰")
        self.meetings_metric.set_text("جلسات: ۰")
        self.resolutions_metric.set_text("مصوبات باز: ۰")
        self.setEnabled(False)
        self._apply_visuals()

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._apply_visuals()

    def _apply_visuals(self):
        if not self.isEnabled():
            background, border, title, muted, metric_bg, metric_border = (
                "#f3f5f8", "#d7dee7", "#8a96a6", "#9ba6b4", "#edf1f5", "#e0e5eb"
            )
            icon_tone = "muted"
        elif self._selected:
            background, border, title, muted, metric_bg, metric_border = (
                "#102f5c", "#c99b39", "#ffffff", "#dbe8f8", "rgba(255,255,255,0.09)", "rgba(255,255,255,0.14)"
            )
            icon_tone = "white"
        else:
            background, border, title, muted, metric_bg, metric_border = (
                "#ffffff", "#d6e0eb", "#17345f", "#667487", "#f5f8fb", "#e5ebf2"
            )
            icon_tone = "navy"

        self.setStyleSheet(f"""
            QFrame#CommitteeCard {{
                background: {background};
                border: {'2px' if self._selected else '1px'} solid {border};
                border-radius: 12px;
            }}
            QFrame#CommitteeCard:hover {{
                border-color: {'#ddb957' if self._selected else '#91a7c1'};
            }}
            QLabel#CommitteeCardTitle {{
                background: transparent;
                border: none;
                color: {title};
                font-size: 13px;
                font-weight: 700;
                padding: 0;
            }}
            QLabel#CommitteeCardIcon {{
                background: {'rgba(255,255,255,0.10)' if self._selected else '#eef3f9'};
                border: {'1px solid rgba(255,255,255,0.14)' if self._selected else '1px solid #dfe7f0'};
                border-radius: 10px;
            }}
            QFrame#CommitteeMetric {{
                background: {metric_bg};
                border: 1px solid {metric_border};
                border-radius: 7px;
            }}
            QLabel#CommitteeMetricIcon {{ background: transparent; border: none; }}
            QLabel#CommitteeMetricText {{
                background: transparent;
                border: none;
                color: {muted};
                font-size: 10px;
                font-weight: 600;
                padding: 0;
            }}
        """)
        self.icon_label.setPixmap(get_icon(self.icon_name, icon_tone).pixmap(23, 23))
        for metric in (self.members_metric, self.meetings_metric, self.resolutions_metric):
            metric.set_tone(icon_tone if self._selected else ("muted" if not self.isEnabled() else "navy"))

        if self._selected:
            status_css = "background:#c99b39;color:#102a50;border:none;border-radius:7px;padding:4px 9px;font-size:10px;font-weight:700;"
        elif self._status == "فعال":
            status_css = "background:#e8f5ed;color:#1f6b3d;border:1px solid #bfdfca;border-radius:7px;padding:4px 9px;font-size:10px;font-weight:700;"
        elif self._status == "تعلیق":
            status_css = "background:#fff5da;color:#925f00;border:1px solid #ead496;border-radius:7px;padding:4px 9px;font-size:10px;font-weight:700;"
        else:
            status_css = "background:#fbeaec;color:#9b2f38;border:1px solid #e5b8bd;border-radius:7px;padding:4px 9px;font-size:10px;font-weight:700;"
        self.status_label.setStyleSheet(status_css)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.isEnabled() and self.committee_id:
            self.clicked.emit(self.committee_id)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space) and self.isEnabled() and self.committee_id:
            self.clicked.emit(self.committee_id)
            event.accept()
            return
        super().keyPressEvent(event)


class CommitteeMemberDialog(QDialog):
    """ثبت عضویت کمیته با استعلام اولیه کد ملی از پرونده مشترک اشخاص."""
    def __init__(self, db, item=None, committee_id=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.item = item or {}
        self.committee_id = committee_id or self.item.get("committee_id")
        self.person_id = self.item.get("person_id")
        self.lookup_completed = bool(self.person_id or self.item.get("national_code"))
        self.last_lookup_code = self.db.normalize_national_code(self.item.get("national_code")) if self.lookup_completed else ""
        self.setWindowTitle("ثبت عضو کمیته")
        self.resize(650, 760)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(10, 10, 10, 10)
        shell.setSpacing(8)

        form_host = QWidget()
        form = QFormLayout(form_host)

        # گام نخست: کد ملی و بازیابی پرونده شخص
        code_wrap = QWidget()
        code_row = QHBoxLayout(code_wrap)
        code_row.setContentsMargins(0, 0, 0, 0)
        code_row.setSpacing(8)
        self.national_code = QLineEdit(self.item.get("national_code") or "")
        self.national_code.setPlaceholderText("کد ملی ۱۰ رقمی")
        self.national_code.setMaxLength(10)
        self.lookup_btn = QPushButton("جستجو در اطلاعات اشخاص")
        self.lookup_btn.clicked.connect(self.lookup_person)
        code_row.addWidget(self.national_code, 1)
        code_row.addWidget(self.lookup_btn)
        form.addRow("۱. کد ملی*:", code_wrap)

        self.lookup_status = QLabel("ابتدا کد ملی را وارد و دکمه جستجو را بزنید.")
        self.lookup_status.setWordWrap(True)
        self.lookup_status.setStyleSheet("padding:8px; border-radius:7px; background:#eef3f9; color:#334155;")
        form.addRow("وضعیت استعلام:", self.lookup_status)

        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.mobile = QLineEdit(self.item.get("mobile") or "")
        self.education = QLineEdit(self.item.get("education") or "")
        self.first_name.setPlaceholderText("نام")
        self.last_name.setPlaceholderText("نام خانوادگی")
        self.mobile.setPlaceholderText("09xxxxxxxxx")
        self.education.setPlaceholderText("مثلاً کارشناسی")

        # مقدار اولیه برای ویرایش رکورد موجود
        if self.person_id:
            person = self.db.get_person(self.person_id) or {}
            self.first_name.setText(person.get("first_name") or "")
            self.last_name.setText(person.get("last_name") or "")
            self.mobile.setText(person.get("mobile") or self.item.get("mobile") or "")
            self.education.setText(person.get("education") or self.item.get("education") or "")
            self.lookup_status.setText("پرونده هویتی این عضو از پایگاه اشخاص فراخوانی شد.")
            self.lookup_status.setStyleSheet("padding:8px; border-radius:7px; background:#e8f6ec; color:#166534;")
        elif self.item.get("person_name"):
            first, last = self.db._split_person_name(self.item.get("person_name"))
            self.first_name.setText(first)
            self.last_name.setText(last)

        form.addRow("نام*:", self.first_name)
        form.addRow("نام خانوادگی*:", self.last_name)
        form.addRow("شماره همراه:", self.mobile)
        form.addRow("تحصیلات:", self.education)

        self.role = QLineEdit(self.item.get("member_role") or "عضو")
        self.member_type = QComboBox()
        self.member_type.addItems(["عضو مردمی", "نماینده دستگاه", "عضو شورای محله", "متخصص", "نماینده بانوان", "نماینده جوانان", "نماینده سمن یا گروه جهادی", "نماینده مسجد یا بسیج"])
        if self.item.get("member_type"):
            self.member_type.setCurrentText(self.item["member_type"])

        self.agency = QComboBox(); self.agency.setEditable(True)
        self.agency.addItem("بدون دستگاه", None)
        known_names = set()
        for agency in self.db.get_management_agencies(active_only=True):
            self.agency.addItem(agency["name"], agency["id"]); known_names.add(agency["name"])
        if self.committee_id:
            committee = self.db.get_committee(self.committee_id) or {}
            for suggested in (committee.get("recommended_agencies") or "").replace("،", ",").split(","):
                suggested = suggested.strip()
                if suggested and suggested not in known_names:
                    self.agency.addItem(suggested, None); known_names.add(suggested)
        if self.item.get("agency_id"):
            idx = self.agency.findData(self.item["agency_id"])
            if idx >= 0: self.agency.setCurrentIndex(idx)
        elif self.item.get("agency_name"):
            self.agency.setEditText(self.item["agency_name"])

        self.is_chair = QCheckBox("رئیس کمیته")
        self.is_secretary = QCheckBox("دبیر کمیته")
        self.is_chair.setChecked(bool(self.item.get("is_chair")))
        self.is_secretary.setChecked(bool(self.item.get("is_secretary")))
        flags = QHBoxLayout(); flags.addWidget(self.is_chair); flags.addWidget(self.is_secretary); flags.addStretch()

        self.decree_no = QLineEdit(self.item.get("decree_no") or "")
        self.decree_date = JalaliDateEdit(self.item.get("decree_date"));
        self.start_date = JalaliDateEdit(self.item.get("start_date"));
        self.end_date = JalaliDateEdit(self.item.get("end_date"));
        for widget, key in ((self.decree_date,"decree_date"),(self.start_date,"start_date"),(self.end_date,"end_date")):
            if not self.item.get(key): widget.clear()
        self.status = QComboBox(); self.status.addItems(["فعال", "غیرفعال", "پایان عضویت", "تعلیق"])
        self.status.setCurrentText(self.item.get("status") or "فعال")
        self.notes = QTextEdit(self.item.get("notes") or ""); self.notes.setMinimumHeight(85)

        form.addRow("۲. نقش/سمت در کمیته:", self.role)
        form.addRow("نوع عضویت:", self.member_type)
        form.addRow("دستگاه/نهاد:", self.agency)
        form.addRow("مسئولیت ویژه:", flags)
        form.addRow("شماره حکم:", self.decree_no)
        form.addRow("تاریخ حکم:", self.decree_date)
        form.addRow("شروع عضویت:", self.start_date)
        form.addRow("پایان عضویت:", self.end_date)
        form.addRow("وضعیت:", self.status)
        form.addRow("توضیحات:", self.notes)

        self.national_code.returnPressed.connect(self.lookup_person)
        self.national_code.editingFinished.connect(self._auto_lookup_if_ready)

        scroll = scroll_page(form_host, min_height=820)
        shell.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("ثبت عضویت")
        buttons.accepted.connect(self._validate); buttons.rejected.connect(self.reject)
        shell.addWidget(buttons, 0)

    def _auto_lookup_if_ready(self):
        code = self.db.normalize_national_code(self.national_code.text())
        if len(code) == 10 and code != self.db.normalize_national_code(self.item.get("national_code")):
            self.lookup_person(silent=True)

    def lookup_person(self, silent=False):
        code = self.db.normalize_national_code(self.national_code.text())
        self.national_code.setText(code)
        if len(code) != 10:
            if not silent:
                QMessageBox.warning(self, "کد ملی نامعتبر", "کد ملی باید دقیقاً ۱۰ رقم باشد.")
            return False
        if not self.db.validate_national_code(code):
            if not silent:
                answer = QMessageBox.question(
                    self, "کنترل کد ملی",
                    "ساختار کنترلی کد ملی معتبر نیست. آیا با مسئولیت کاربر ادامه داده شود؟",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return False
        person = self.db.find_person_by_national_code(code)
        self.lookup_completed = True
        self.last_lookup_code = code
        if person:
            self.person_id = person.get("id")
            self.first_name.setText(person.get("first_name") or "")
            self.last_name.setText(person.get("last_name") or "")
            self.mobile.setText(person.get("mobile") or "")
            self.education.setText(person.get("education") or "")
            source_title = "فهرست اعضای شورای محله" if person.get("source") == "council_members" else "پایگاه اشخاص سامانه"
            self.lookup_status.setText(f"مشخصات این فرد از {source_title} فراخوانی شد. نقش و دستگاه کمیته را تکمیل کنید.")
            self.lookup_status.setStyleSheet("padding:8px; border-radius:7px; background:#e8f6ec; color:#166534;")
        else:
            self.person_id = None
            if not self.item:
                self.first_name.clear(); self.last_name.clear(); self.mobile.clear(); self.education.clear()
            self.lookup_status.setText("این کد ملی در سامانه وجود ندارد؛ مشخصات فرد جدید را وارد کنید. با ذخیره، پرونده شخص ساخته می‌شود.")
            self.lookup_status.setStyleSheet("padding:8px; border-radius:7px; background:#fff7df; color:#92400e;")
        return True

    def _date(self, widget):
        if not widget.text().strip(): return None
        try: return widget.isoDate()
        except Exception: raise ValueError("یکی از تاریخ‌ها معتبر نیست.")

    def _validate(self):
        code = self.db.normalize_national_code(self.national_code.text())
        if len(code) != 10:
            QMessageBox.warning(self, "اطلاعات ناقص", "ورود کد ملی ۱۰ رقمی الزامی است."); return
        if not self.lookup_completed or code != self.last_lookup_code:
            if not self.lookup_person():
                return
        if not self.first_name.text().strip() or not self.last_name.text().strip():
            QMessageBox.warning(self, "اطلاعات ناقص", "نام و نام خانوادگی الزامی است."); return
        try:
            self._date(self.decree_date); self._date(self.start_date); self._date(self.end_date)
        except ValueError as exc:
            QMessageBox.warning(self, "تاریخ نامعتبر", str(exc)); return
        self.accept()

    def values(self):
        code = self.db.normalize_national_code(self.national_code.text())
        first_name = self.first_name.text().strip()
        last_name = self.last_name.text().strip()
        person_name = f"{first_name} {last_name}".strip()
        self.person_id = self.db.upsert_person(
            code,
            first_name=first_name,
            last_name=last_name,
            full_name=person_name,
            mobile=self.mobile.text().strip(),
            education=self.education.text().strip(),
        )
        agency_name = self.agency.currentText().strip()
        agency_id = self.agency.currentData()
        if agency_name and agency_name != "بدون دستگاه" and agency_id is None:
            existing = next((x for x in self.db.get_management_agencies(active_only=False) if x["name"] == agency_name), None)
            if existing:
                agency_id = existing["id"]
            else:
                try: agency_id = self.db.add_management_agency(agency_name, category="دستگاه همکار کمیته")
                except Exception: agency_id = None
        return {
            "person_id": self.person_id, "person_name": person_name,
            "first_name": first_name, "last_name": last_name,
            "national_code": code, "mobile": self.mobile.text().strip(),
            "education": self.education.text().strip(), "member_role": self.role.text().strip(),
            "member_type": self.member_type.currentText(), "agency_id": agency_id,
            "agency_name": "" if agency_name == "بدون دستگاه" else agency_name,
            "is_chair": self.is_chair.isChecked(), "is_secretary": self.is_secretary.isChecked(),
            "decree_no": self.decree_no.text().strip(), "decree_date": self._date(self.decree_date),
            "start_date": self._date(self.start_date), "end_date": self._date(self.end_date),
            "status": self.status.currentText(), "notes": self.notes.toPlainText().strip(),
        }


class CommitteeMeetingDialog(QDialog):
    def __init__(self, item=None, parent=None):
        super().__init__(parent); self.item=item or {}; self.setWindowTitle("ثبت جلسه کمیته"); self.resize(640,620)
        form=QFormLayout(self)
        self.title=QLineEdit(self.item.get("title") or "جلسه کمیته")
        self.date=JalaliPickerField(self.item.get("meeting_date"), dialog_title="انتخاب تاریخ جلسه")
        self.time=TimePickerField(self.item.get("start_time"))
        self.place=QLineEdit(self.item.get("place_name") or "")
        self.agenda=QTextEdit(self.item.get("agenda") or "")
        self.attendees=QTextEdit(self.item.get("attendees") or "")
        self.minutes=QTextEdit(self.item.get("minutes_text") or "")
        self.status=QComboBox(); self.status.addItems(["برنامه‌ریزی‌شده","برگزارش‌شده","لغوشده"]); self.status.setCurrentText(self.item.get("status") or "برنامه‌ریزی‌شده")
        for label,w in [("عنوان*:",self.title),("تاریخ:",self.date),("ساعت:",self.time),("محل:",self.place),("دستور جلسه:",self.agenda),("حاضرین:",self.attendees),("صورت‌جلسه:",self.minutes),("وضعیت:",self.status)]: form.addRow(label,w)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def values(self):
        return {"title":self.title.text().strip(),"meeting_date":self.date.isoDate() if self.date.text().strip() else None,"start_time":self.time.text().strip(),"place_name":self.place.text().strip(),"agenda":self.agenda.toPlainText().strip(),"attendees":self.attendees.toPlainText().strip(),"minutes_text":self.minutes.toPlainText().strip(),"status":self.status.currentText()}


class CommitteeResolutionDialog(QDialog):
    def __init__(self, db, committee_id, zone_id, parent=None):
        super().__init__(parent); self.db=db; self.committee_id=committee_id; self.zone_id=zone_id
        self.setWindowTitle("ثبت مصوبه کمیته"); self.resize(650,650); form=QFormLayout(self)
        self.meeting=QComboBox(); self.meeting.addItem("بدون جلسه مشخص",None)
        for x in db.get_committee_meetings(committee_id): self.meeting.addItem(f"{_display_date(x['meeting_date'])} — {x['title']}",x['id'])
        self.title=QLineEdit(); self.description=QTextEdit()
        self.agency=QComboBox(); self.agency.setEditable(True); self.agency.addItem("",None)
        for x in db.get_management_agencies(True): self.agency.addItem(x["name"],x["id"])
        self.person=QLineEdit(); self.due=JalaliPickerField(allow_empty=True, dialog_title="انتخاب مهلت اجرا")
        self.status=QComboBox(); self.status.addItems(["در انتظار اقدام","در حال اجرا","انجام‌شده","لغوشده"])
        self.issue=QComboBox(); self.issue.addItem("بدون اتصال",None)
        for x in db.get_neighborhood_issues(zone_id): self.issue.addItem(x["title"],x["id"])
        self.action=QComboBox(); self.action.addItem("بدون اتصال",None)
        for x in db.get_neighborhood_actions(zone_id): self.action.addItem(x["title"],x["id"])
        for label,w in [("جلسه:",self.meeting),("عنوان مصوبه*:",self.title),("شرح:",self.description),("دستگاه مسئول:",self.agency),("مسئول پیگیری:",self.person),("مهلت اجرا:",self.due),("وضعیت:",self.status),("مسئله مرتبط:",self.issue),("اقدام مرتبط:",self.action)]: form.addRow(label,w)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def values(self):
        return {"meeting_id":self.meeting.currentData(),"title":self.title.text().strip(),"description":self.description.toPlainText().strip(),"responsible_agency":self.agency.currentText().strip(),"responsible_person":self.person.text().strip(),"due_date":self.due.isoDate() if self.due.text().strip() else None,"status":self.status.currentText(),"linked_issue_id":self.issue.currentData(),"linked_action_id":self.action.currentData()}


class CountySteeringMemberDialog(QDialog):
    def __init__(self, item, parent=None):
        super().__init__(parent); self.item=item; self.setWindowTitle("ثبت عضو کمیته حمایت و راهبری شهرستان"); self.resize(560,470)
        form=QFormLayout(self)
        role=QLabel(f"{item['role_title']} — {item.get('agency_name') or ''}"); role.setWordWrap(True); role.setStyleSheet("font-weight:800;color:#13294b;")
        self.person=QLineEdit(item.get("person_name") or ""); self.mobile=QLineEdit(item.get("mobile") or ""); self.decree=QLineEdit(item.get("decree_no") or "")
        self.date=JalaliDateEdit(item.get("decree_date"));
        if not item.get("decree_date"): self.date.clear()
        self.status=QComboBox(); self.status.addItems(["فعال","غیرفعال","تعلیق"]); self.status.setCurrentText(item.get("status") or "فعال")
        self.notes=QTextEdit(item.get("notes") or "")
        for label,w in [("جایگاه:",role),("نام و نام خانوادگی:",self.person),("شماره همراه:",self.mobile),("شماره حکم:",self.decree),("تاریخ حکم:",self.date),("وضعیت:",self.status),("توضیحات:",self.notes)]: form.addRow(label,w)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def values(self):
        return {"person_name":self.person.text().strip(),"mobile":self.mobile.text().strip(),"decree_no":self.decree.text().strip(),"decree_date":self.date.isoDate() if self.date.text().strip() else None,"status":self.status.currentText(),"notes":self.notes.toPlainText().strip()}


class CountySteeringDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent); self.db=db; self.setWindowTitle("کمیته حمایت و راهبری شهرستان"); self.resize(980,600)
        root=QVBoxLayout(self)
        info=QLabel("ترکیب ثابت شهرستان: فرماندار (مسئول)، شهردار (دبیر)، رئیس تبلیغات اسلامی، فرمانده ناحیه مقاومت بسیج و دو نماینده تشکل‌های مردمی")
        info.setWordWrap(True); info.setStyleSheet("font-weight:800;color:#13294b;padding:8px;"); root.addWidget(info)
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(["جایگاه","دستگاه/نهاد","نام فرد","موبایل","شماره حکم","تاریخ حکم","وضعیت"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); root.addWidget(self.table)
        bar=QHBoxLayout(); edit=QPushButton("ثبت/ویرایش فرد انتخاب‌شده"); edit.clicked.connect(self.edit_member); close=QPushButton("بستن"); close.clicked.connect(self.accept); bar.addWidget(edit); bar.addStretch(); bar.addWidget(close); root.addLayout(bar); self.refresh()
    def refresh(self):
        self.table.setRowCount(0)
        for r,x in enumerate(self.db.get_county_steering_members()):
            self.table.insertRow(r); vals=[x["role_title"],x.get("agency_name") or "—",x.get("person_name") or "ثبت نشده",x.get("mobile") or "—",x.get("decree_no") or "—",_display_date(x.get("decree_date")),x["status"]]
            for c,v in enumerate(vals): self.table.setItem(r,c,QTableWidgetItem(str(v)))
            self.table.item(r,0).setData(Qt.UserRole,x["id"])
    def edit_member(self):
        mid=_selected_id(self.table)
        if not mid: QMessageBox.information(self,"انتخاب","یک جایگاه را انتخاب کنید."); return
        item=next(x for x in self.db.get_county_steering_members() if x["id"]==mid)
        d=CountySteeringMemberDialog(item,self)
        if d.exec_()==QDialog.Accepted: self.db.update_county_steering_member(mid,**d.values()); self.refresh()


class NeighborhoodCommitteesWindow(QWidget):
    back_requested=pyqtSignal()
    def __init__(self, db):
        super().__init__(); self.db=db; self.zone_id=None; self.committee_id=None
        self.setWindowTitle("کمیته‌های شش‌گانه محله‌محور"); self.resize(1460,900); self._build(); self.refresh_zones()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(build_official_header("مدیریت کمیته‌های شش‌گانه هر بلوک", self.db))
        body=QWidget(); layout=QVBoxLayout(body); layout.setContentsMargins(20,14,20,20); layout.setSpacing(12)

        top=QHBoxLayout()
        top.setSpacing(10)
        back=set_button_style(QPushButton("بازگشت به داشبورد"), "back", "ghost")
        back.clicked.connect(self.back_requested.emit); top.addWidget(back)
        county=set_button_style(QPushButton("کمیته حمایت و راهبری شهرستان"), "committee", "secondary")
        county.clicked.connect(self.open_county_steering); top.addWidget(county)
        zone_label=QLabel("بلوک/محله")
        zone_label.setProperty("muted", True)
        top.addWidget(zone_label)
        self.zone_combo=QComboBox(); self.zone_combo.setMinimumWidth(300); self.zone_combo.currentIndexChanged.connect(self._zone_changed); top.addWidget(self.zone_combo)
        top.addStretch()
        self.summary=QLabel(); self.summary.setObjectName("CommitteeSummary"); self.summary.setProperty("sectionTitle", True); top.addWidget(self.summary)
        layout.addLayout(top)

        committees_box=QGroupBox("کمیته‌های شش‌گانه بلوک انتخاب‌شده")
        cards_grid=QGridLayout(committees_box); cards_grid.setContentsMargins(12,18,12,12); cards_grid.setHorizontalSpacing(10); cards_grid.setVerticalSpacing(10)
        self.committee_cards=[]
        for index in range(6):
            card=CommitteeCard(index)
            card.set_empty()
            card.clicked.connect(self._select_committee)
            self.committee_cards.append(card)
            cards_grid.addWidget(card, index//2, index%2)
            cards_grid.setColumnStretch(index%2, 1)
        layout.addWidget(committees_box)

        current_panel=QFrame()
        current_panel.setObjectName("CommitteeCurrentPanel")
        current_panel.setStyleSheet("QFrame#CommitteeCurrentPanel{background:#ffffff;border:1px solid #d9e1eb;border-radius:10px;}")
        current_bar=QHBoxLayout(current_panel)
        current_bar.setContentsMargins(14,9,14,9)
        label=QLabel("کمیته بازشده")
        label.setProperty("muted", True)
        current_bar.addWidget(label)
        self.committee_title=QLabel("در حال آماده‌سازی کمیته‌های بلوک...")
        self.committee_title.setProperty("sectionTitle", True)
        current_bar.addWidget(self.committee_title)
        current_bar.addStretch()
        self.current_status=QLabel("—")
        self.current_status.setAlignment(Qt.AlignCenter)
        self.current_status.setMinimumWidth(110)
        current_bar.addWidget(self.current_status)
        layout.addWidget(current_panel)

        self.tabs=QTabWidget(); self.tabs.setEnabled(False); self.tabs.setIconSize(QSize(17,17)); self.tabs.setDocumentMode(True)
        self._build_profile_tab(); self._build_members_tab(); self._build_meetings_tab(); self._build_links_tab()
        layout.addWidget(self.tabs,1)
        root.addWidget(scroll_page(body, min_height=860), 1)

    def _build_profile_tab(self):
        page=QWidget(); form=QFormLayout(page)
        self.recommended=QTextEdit(); self.recommended.setReadOnly(True); self.recommended.setMaximumHeight(80)
        self.chair=QLineEdit(); self.chair_mobile=QLineEdit(); self.secretary=QLineEdit(); self.secretary_mobile=QLineEdit(); self.decree_no=QLineEdit()
        self.decree_date=JalaliDateEdit(); self.start_date=JalaliDateEdit(); self.end_date=JalaliDateEdit();
        for w in (self.decree_date,self.start_date,self.end_date): w.clear()
        self.committee_status=QComboBox(); self.committee_status.addItems(["فعال","غیرفعال","تعلیق"])
        self.notes=QTextEdit(); self.notes.setMinimumHeight(100)
        for label,w in [("دستگاه‌های پیشنهادی:",self.recommended),("رئیس کمیته:",self.chair),("تلفن رئیس:",self.chair_mobile),("دبیر کمیته:",self.secretary),("تلفن دبیر:",self.secretary_mobile),("شماره حکم:",self.decree_no),("تاریخ حکم:",self.decree_date),("شروع دوره:",self.start_date),("پایان دوره:",self.end_date),("وضعیت:",self.committee_status),("توضیحات:",self.notes)]: form.addRow(label,w)
        save=set_button_style(QPushButton("ذخیره مشخصات کمیته"), "save", "primary"); save.clicked.connect(self.save_profile); form.addRow(save)
        self.tabs.addTab(scroll_page(page,min_height=640), get_icon("info", "navy"), "مشخصات کمیته")

    def _build_members_tab(self):
        page=QWidget(); l=QVBoxLayout(page); bar=QHBoxLayout()
        for text,slot in [("ثبت عضو جدید",self.add_member),("ویرایش عضو",self.edit_member),("حذف عضو",self.delete_member)]: b=QPushButton(text); b.clicked.connect(slot); bar.addWidget(b)
        bar.addStretch(); l.addLayout(bar)
        self.members=QTableWidget(0,10); self.members.setHorizontalHeaderLabels(["نام","کد ملی","تحصیلات","نوع عضویت","سمت","دستگاه","موبایل","رئیس","دبیر","وضعیت"]); self.members.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.members.setSelectionBehavior(QAbstractItemView.SelectRows); self.members.setEditTriggers(QAbstractItemView.NoEditTriggers); l.addWidget(self.members)
        self.tabs.addTab(scroll_page(page, min_height=520), get_icon("users", "navy"), "اعضا و نمایندگان ادارات")

    def _build_meetings_tab(self):
        page=QWidget(); l=QVBoxLayout(page)
        bar=QHBoxLayout()
        new_minutes=QPushButton("صورتجلسه A4 جدید"); new_minutes.clicked.connect(self.new_minutes_a4)
        open_minutes=QPushButton("بازکردن صورتجلسه انتخاب‌شده"); open_minutes.clicked.connect(self.open_selected_minutes_a4)
        open_minutes.setStyleSheet("background:#c99b39;color:#102f5c;font-weight:900;border-radius:7px;padding:7px 12px;")
        add=QPushButton("ثبت جلسه ساده"); add.clicked.connect(self.add_meeting)
        delete=QPushButton("حذف جلسه"); delete.clicked.connect(self.delete_meeting)
        addres=QPushButton("ثبت مصوبه جداگانه"); addres.clicked.connect(self.add_resolution)
        for button in (new_minutes,open_minutes,add,delete,addres): bar.addWidget(button)
        bar.addStretch(); l.addLayout(bar)
        info=QLabel("برای تنظیم یک برگ A4 کامل شامل شماره، تاریخ و ساعت انتخابی، شرح مذاکرات، جدول مصوبات، برگ مستقل اعضا و امضای لمسی از دکمه‌های صورتجلسه A4 استفاده کنید.")
        info.setWordWrap(True); info.setStyleSheet("background:#eef5fb;color:#17345f;border:1px solid #cddce9;border-radius:7px;padding:8px;font-weight:700;"); l.addWidget(info)
        meetings_title=QLabel("جلسات کمیته"); meetings_title.setProperty("sectionTitle", True); l.addWidget(meetings_title); self.meetings=QTableWidget(0,6); self.meetings.setHorizontalHeaderLabels(["عنوان","تاریخ","ساعت","محل","وضعیت","دستور جلسه"]); self.meetings.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.meetings.setSelectionBehavior(QAbstractItemView.SelectRows); self.meetings.setEditTriggers(QAbstractItemView.NoEditTriggers); self.meetings.doubleClicked.connect(lambda _index: self.open_selected_minutes_a4()); l.addWidget(self.meetings)
        resolutions_title=QLabel("مصوبات کمیته"); resolutions_title.setProperty("sectionTitle", True); l.addWidget(resolutions_title); self.resolutions=QTableWidget(0,6); self.resolutions.setHorizontalHeaderLabels(["عنوان","دستگاه مسئول","مسئول","مهلت","وضعیت","اتصال"]); self.resolutions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.resolutions.setSelectionBehavior(QAbstractItemView.SelectRows); self.resolutions.setEditTriggers(QAbstractItemView.NoEditTriggers); l.addWidget(self.resolutions)
        statusbar=QHBoxLayout(); done=QPushButton("علامت‌گذاری مصوبه به‌عنوان انجام‌شده"); done.clicked.connect(self.complete_resolution); deleter=QPushButton("حذف مصوبه"); deleter.clicked.connect(self.delete_resolution); statusbar.addWidget(done); statusbar.addWidget(deleter); statusbar.addStretch(); l.addLayout(statusbar)
        self.tabs.addTab(scroll_page(page, min_height=620), get_icon("calendar", "navy"), "جلسات و مصوبات")

    def _build_links_tab(self):
        page=QWidget(); l=QVBoxLayout(page)
        issue_box=QGroupBox("مسائل ارجاع‌شده به کمیته"); il=QVBoxLayout(issue_box); row=QHBoxLayout(); self.issue_combo=QComboBox(); row.addWidget(self.issue_combo,1); add=QPushButton("اتصال مسئله"); add.clicked.connect(self.link_issue); rem=QPushButton("حذف اتصال"); rem.clicked.connect(self.unlink_issue); row.addWidget(add); row.addWidget(rem); il.addLayout(row); self.issues=QTableWidget(0,5); self.issues.setHorizontalHeaderLabels(["عنوان","دسته","اولویت","وضعیت","دستگاه مرتبط"]); self.issues.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.issues.setSelectionBehavior(QAbstractItemView.SelectRows); il.addWidget(self.issues); l.addWidget(issue_box)
        action_box=QGroupBox("اقدامات اجرایی کمیته"); al=QVBoxLayout(action_box); row2=QHBoxLayout(); self.action_combo=QComboBox(); row2.addWidget(self.action_combo,1); add2=QPushButton("اتصال اقدام"); add2.clicked.connect(self.link_action); rem2=QPushButton("حذف اتصال"); rem2.clicked.connect(self.unlink_action); row2.addWidget(add2); row2.addWidget(rem2); al.addLayout(row2); self.actions=QTableWidget(0,5); self.actions.setHorizontalHeaderLabels(["عنوان","دستگاه مسئول","پیشرفت","وضعیت","پایان برنامه‌ای"]); self.actions.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.actions.setSelectionBehavior(QAbstractItemView.SelectRows); al.addWidget(self.actions); l.addWidget(action_box)
        self.tabs.addTab(scroll_page(page, min_height=620), get_icon("link", "navy"), "مسائل و اقدامات مرتبط")

    def open_county_steering(self):
        CountySteeringDialog(self.db, self).exec_()

    def refresh_zones(self):
        previous_zone_id = self.zone_id
        self.zone_combo.blockSignals(True)
        self.zone_combo.clear()
        zones = self.db.get_zones()
        for zone in zones:
            self.zone_combo.addItem(zone["name"], zone["id"])

        target_index = -1
        if zones:
            for index, zone in enumerate(zones):
                if previous_zone_id and int(zone["id"]) == int(previous_zone_id):
                    target_index = index
                    break
            if target_index < 0:
                target_index = 0
            self.zone_combo.setCurrentIndex(target_index)
        self.zone_combo.blockSignals(False)

        if target_index >= 0:
            # اجرای صریح پس از تکمیل ساخت ComboBox؛ به سیگنال currentIndexChanged وابسته نیست.
            self._zone_changed(target_index)
            QTimer.singleShot(0, lambda: self._open_default_committee())
        else:
            self.zone_id = None
            self.committee_id = None
            self.refresh_committees()
            self.refresh_link_choices()

    def _zone_changed(self, _index):
        self.zone_id = self.zone_combo.currentData()
        self.committee_id = None
        self.refresh_committees()
        self.refresh_link_choices()

    def _open_default_committee(self):
        """اولین کمیته معتبر را پس از نمایش صفحه به‌طور قطعی باز می‌کند."""
        if self.committee_id:
            self._select_committee(self.committee_id)
            return
        first_id = next((card.committee_id for card in self.committee_cards if card.committee_id), None)
        self._select_committee(first_id)

    def refresh_committees(self):
        data = []
        if self.zone_id:
            # علاوه بر بازیابی، وجود دقیق شش کمیته برای بلوک تضمین می‌شود.
            data = self.db.ensure_zone_committees(self.zone_id)
        total_members = sum(int(item.get("members_count") or 0) for item in data)
        if self.zone_id:
            zone_name = self.zone_combo.currentText().strip() or "بلوک انتخاب‌شده"
            self.summary.setText(
                f"{zone_name} | ۶ کمیته تخصصی | {to_persian_digits(total_members)} عضو فعال"
            )
        else:
            self.summary.setText("ابتدا یک بلوک در سامانه ثبت کنید")

        by_index=list(data[:6])
        for index,card in enumerate(self.committee_cards):
            if index < len(by_index):
                card.set_data(by_index[index], index)
            else:
                card.set_empty()

        valid_ids = [item["id"] for item in data]
        selected = self.committee_id if self.committee_id in valid_ids else (valid_ids[0] if valid_ids else None)
        self._select_committee(selected)

    def _select_committee(self, committee_id):
        if not committee_id:
            self.committee_id = None
            if self.zone_id:
                self.committee_title.setText("کمیته‌های این بلوک آماده نشده‌اند؛ صفحه را بازخوانی کنید")
            else:
                self.committee_title.setText("هیچ بلوکی برای نمایش کمیته‌ها ثبت نشده است")
            self.current_status.setText("نامشخص")
            self.current_status.setStyleSheet("background:#f1f5f9;color:#64748b;border:1px solid #cbd5e1;border-radius:9px;padding:7px;font-weight:900;")
            self.tabs.setEnabled(False)
            for card in self.committee_cards: card.set_selected(False)
            return

        self.committee_id=int(committee_id)
        item=self.db.get_committee(self.committee_id)
        if not item:
            self.tabs.setEnabled(False)
            return
        for card in self.committee_cards:
            card.set_selected(card.committee_id == self.committee_id)
        self.committee_title.setText(item["title"])
        status=item.get("status") or "فعال"
        self.current_status.setText(f"وضعیت: {status}")
        if status == "فعال":
            css="background:#e8f6ec;color:#166534;border:1px solid #9ed5ad;border-radius:9px;padding:7px;font-weight:900;"
        elif status == "تعلیق":
            css="background:#fff7df;color:#92400e;border:1px solid #efd087;border-radius:9px;padding:7px;font-weight:900;"
        else:
            css="background:#fef0f0;color:#991b1b;border:1px solid #efb1b1;border-radius:9px;padding:7px;font-weight:900;"
        self.current_status.setStyleSheet(css)
        self.tabs.setEnabled(True)
        self._load_profile(item)
        self.refresh_members(); self.refresh_meetings(); self.refresh_resolutions(); self.refresh_links()

    def _committee_changed(self):
        """سازگاری با فراخوانی‌های قدیمی؛ کمیته انتخاب‌شده را باز می‌کند."""
        self._select_committee(self.committee_id)

    def _load_profile(self,x):
        self.recommended.setPlainText(x.get("recommended_agencies") or "")
        self.chair.setText(x.get("chair_name") or ""); self.chair_mobile.setText(x.get("chair_mobile") or ""); self.secretary.setText(x.get("secretary_name") or ""); self.secretary_mobile.setText(x.get("secretary_mobile") or ""); self.decree_no.setText(x.get("decree_no") or "")
        for w,key in ((self.decree_date,"decree_date"),(self.start_date,"start_date"),(self.end_date,"end_date")):
            w.setText(iso_to_jalali(x.get(key)) if x.get(key) else "")
        self.committee_status.setCurrentText(x.get("status") or "فعال"); self.notes.setPlainText(x.get("notes") or "")

    def _date(self,w): return w.isoDate() if w.text().strip() else None
    def save_profile(self):
        if not self.committee_id:return
        try:self.db.update_committee(self.committee_id,chair_name=self.chair.text().strip(),chair_mobile=self.chair_mobile.text().strip(),secretary_name=self.secretary.text().strip(),secretary_mobile=self.secretary_mobile.text().strip(),decree_no=self.decree_no.text().strip(),decree_date=self._date(self.decree_date),start_date=self._date(self.start_date),end_date=self._date(self.end_date),status=self.committee_status.currentText(),notes=self.notes.toPlainText().strip()); QMessageBox.information(self,"ذخیره شد","مشخصات کمیته ذخیره شد."); self.refresh_committees()
        except Exception as exc: QMessageBox.critical(self,"خطا",str(exc))

    def refresh_members(self):
        self.members.setRowCount(0)
        if not self.committee_id:return
        for r,x in enumerate(self.db.get_committee_members(self.committee_id)):
            self.members.insertRow(r); vals=[x["person_name"],x.get("national_code") or "—",x.get("education") or "—",x["member_type"],x["member_role"],x.get("agency_name") or "—",x.get("mobile") or "—","بله" if x["is_chair"] else "خیر","بله" if x["is_secretary"] else "خیر",x["status"]]
            for c,v in enumerate(vals): self.members.setItem(r,c,QTableWidgetItem(str(v)))
            self.members.item(r,0).setData(Qt.UserRole,x["id"])
    def add_member(self):
        if not self.committee_id:return
        d=CommitteeMemberDialog(self.db,committee_id=self.committee_id,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:
                vals=d.values(); name=vals.pop("person_name")
                self.db.add_committee_member(self.committee_id,name,**vals)
                self.refresh_members(); self.refresh_committees()
            except Exception as exc:
                QMessageBox.critical(self,"خطا در ثبت عضو",str(exc))
    def edit_member(self):
        mid=_selected_id(self.members)
        if not mid: QMessageBox.information(self,"انتخاب عضو","یک عضو را انتخاب کنید."); return
        item=self.db.get_committee_member(mid); d=CommitteeMemberDialog(self.db,item,committee_id=self.committee_id,parent=self)
        if d.exec_()==QDialog.Accepted:
            try:
                self.db.update_committee_member(mid,**d.values())
                self.refresh_members(); self.refresh_committees()
            except Exception as exc:
                QMessageBox.critical(self,"خطا در ویرایش عضو",str(exc))
    def delete_member(self):
        mid=_selected_id(self.members)
        if mid and QMessageBox.question(self,"حذف عضو","عضو انتخاب‌شده حذف شود؟")==QMessageBox.Yes:self.db.delete_committee_member(mid); self.refresh_members(); self.refresh_committees()

    def refresh_meetings(self):
        self.meetings.setRowCount(0)
        if not self.committee_id:return
        for r,x in enumerate(self.db.get_committee_meetings(self.committee_id)):
            self.meetings.insertRow(r); vals=[x["title"],_display_date(x["meeting_date"]),x.get("start_time") or "—",x.get("place_name") or "—",x["status"],x.get("agenda") or "—"]
            for c,v in enumerate(vals): self.meetings.setItem(r,c,QTableWidgetItem(str(v)))
            self.meetings.item(r,0).setData(Qt.UserRole,x["id"])
    def new_minutes_a4(self):
        if not self.committee_id:
            return
        dialog=CommitteeMinutesDialog(self.db,self.committee_id,self.zone_id,parent=self)
        dialog.saved.connect(lambda _mid: (self.refresh_meetings(),self.refresh_resolutions(),self.refresh_committees()))
        dialog.exec_()
        self.refresh_meetings(); self.refresh_resolutions(); self.refresh_committees()

    def open_selected_minutes_a4(self):
        if not self.committee_id:
            return
        meeting_id=_selected_id(self.meetings)
        if not meeting_id:
            QMessageBox.information(self,"انتخاب جلسه","یک جلسه را از جدول انتخاب کنید یا «صورتجلسه A4 جدید» را بزنید.")
            return
        dialog=CommitteeMinutesDialog(self.db,self.committee_id,self.zone_id,meeting_id=meeting_id,parent=self)
        dialog.saved.connect(lambda _mid: (self.refresh_meetings(),self.refresh_resolutions(),self.refresh_committees()))
        dialog.exec_()
        self.refresh_meetings(); self.refresh_resolutions(); self.refresh_committees()

    def add_meeting(self):
        if not self.committee_id:return
        d=CommitteeMeetingDialog(parent=self)
        if d.exec_()==QDialog.Accepted:
            vals=d.values(); title=vals.pop("title"); self.db.add_committee_meeting(self.committee_id,self.zone_id,title,**vals); self.refresh_meetings(); self.refresh_committees()
    def delete_meeting(self):
        mid=_selected_id(self.meetings)
        if mid and QMessageBox.question(self,"حذف جلسه","جلسه حذف شود؟")==QMessageBox.Yes:self.db.delete_committee_meeting(mid); self.refresh_meetings(); self.refresh_resolutions(); self.refresh_committees()

    def refresh_resolutions(self):
        self.resolutions.setRowCount(0)
        if not self.committee_id:return
        for r,x in enumerate(self.db.get_committee_resolutions(self.committee_id)):
            self.resolutions.insertRow(r); link="مسئله" if x.get("linked_issue_id") else ("اقدام" if x.get("linked_action_id") else "—"); vals=[x["title"],x.get("responsible_agency") or "—",x.get("responsible_person") or "—",_display_date(x.get("due_date")),x["status"],link]
            for c,v in enumerate(vals): self.resolutions.setItem(r,c,QTableWidgetItem(str(v)))
            self.resolutions.item(r,0).setData(Qt.UserRole,x["id"])
    def add_resolution(self):
        if not self.committee_id:return
        d=CommitteeResolutionDialog(self.db,self.committee_id,self.zone_id,self)
        if d.exec_()==QDialog.Accepted:
            vals=d.values(); title=vals.pop("title"); self.db.add_committee_resolution(self.committee_id,self.zone_id,title,**vals); self.refresh_resolutions(); self.refresh_committees()
    def complete_resolution(self):
        rid=_selected_id(self.resolutions)
        if rid:self.db.update_committee_resolution_status(rid,"انجام‌شده"); self.refresh_resolutions(); self.refresh_committees()
    def delete_resolution(self):
        rid=_selected_id(self.resolutions)
        if rid and QMessageBox.question(self,"حذف مصوبه","مصوبه حذف شود؟")==QMessageBox.Yes:self.db.delete_committee_resolution(rid); self.refresh_resolutions(); self.refresh_committees()

    def refresh_link_choices(self):
        self.issue_combo.clear(); self.action_combo.clear()
        if not self.zone_id:return
        for x in self.db.get_neighborhood_issues(self.zone_id): self.issue_combo.addItem(f"{x['title']} — {x['status']}",x["id"])
        for x in self.db.get_neighborhood_actions(self.zone_id): self.action_combo.addItem(f"{x['title']} — {x['status']}",x["id"])
    def refresh_links(self):
        self.issues.setRowCount(0); self.actions.setRowCount(0)
        if not self.committee_id:return
        for r,x in enumerate(self.db.get_committee_issues(self.committee_id)):
            self.issues.insertRow(r); vals=[x["title"],x["category"],x["priority_level"],x["status"],x.get("related_office") or "—"]
            for c,v in enumerate(vals):self.issues.setItem(r,c,QTableWidgetItem(str(v)))
            self.issues.item(r,0).setData(Qt.UserRole,x["id"])
        for r,x in enumerate(self.db.get_committee_actions(self.committee_id)):
            self.actions.insertRow(r); vals=[x["title"],x.get("responsible_office") or "—",f"{to_persian_digits(x.get('progress_percent') or 0)}٪",x["status"],_display_date(x.get("planned_end"))]
            for c,v in enumerate(vals):self.actions.setItem(r,c,QTableWidgetItem(str(v)))
            self.actions.item(r,0).setData(Qt.UserRole,x["id"])
    def link_issue(self):
        if self.committee_id and self.issue_combo.currentData():self.db.link_committee_issue(self.committee_id,self.issue_combo.currentData()); self.refresh_links()
    def unlink_issue(self):
        iid=_selected_id(self.issues)
        if iid:self.db.unlink_committee_issue(self.committee_id,iid); self.refresh_links()
    def link_action(self):
        if self.committee_id and self.action_combo.currentData():self.db.link_committee_action(self.committee_id,self.action_combo.currentData()); self.refresh_links()
    def unlink_action(self):
        aid=_selected_id(self.actions)
        if aid:self.db.unlink_committee_action(self.committee_id,aid); self.refresh_links()
