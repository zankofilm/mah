# -*- coding: utf-8 -*-
"""جستجوی سراسری در تمام پرونده‌های سامانه."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from icon_manager import get_icon
from jalali_utils import convert_dates_in_text


TYPE_LABELS = {
    "zone": "بلوک",
    "street": "معبر",
    "place": "مکان",
    "mosque": "مسجد",
    "council_member": "عضو شورا",
    "issue": "مسئله",
    "action": "اقدام",
    "citizen_request": "درخواست مردمی",
    "agency": "دستگاه",
    "social_council_member": "عضو شورای اجتماعی",
    "social_issue": "مسئله اجتماعی",
    "social_meeting": "جلسه شورای اجتماعی",
    "social_resolution": "مصوبه اجتماعی",
    "social_action_plan": "برنامه اقدام اجتماعی",
    "letter": "نامه اداری",
}


class GlobalSearchDialog(QDialog):
    result_activated = pyqtSignal(object)

    def __init__(self, db, parent=None, initial_query=""):
        super().__init__(parent)
        self.db = db
        self.initial_query = (initial_query or "").strip()
        self.results = []
        self.setWindowTitle("جستجوی سراسری سامانه")
        self.resize(950, 620)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("جستجو در بلوک‌ها، اماکن، شورای محله، شورای اجتماعی، مسائل، مصوبات و مکاتبات اداری")
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:700; color:#13294b;")
        layout.addWidget(title)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("حداقل دو حرف وارد کنید؛ نام، کد رهگیری، تلفن یا دستگاه مسئول...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.run_search)
        self.search_input.textChanged.connect(self._schedule_search)
        search_row.addWidget(self.search_input, 1)
        search_btn = QPushButton("جستجو")
        search_btn.setIcon(get_icon("search", "navy"))
        search_btn.clicked.connect(self.run_search)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        self.status_label = QLabel("برای شروع جستجو، عبارت موردنظر را وارد کنید.")
        self.status_label.setStyleSheet("color:#647184;")
        layout.addWidget(self.status_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["نوع", "عنوان", "شرح", "شناسه بلوک"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._activate_selected)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        open_btn = QPushButton("باز کردن بخش مرتبط")
        open_btn.setIcon(get_icon("eye", "navy"))
        open_btn.clicked.connect(self._activate_selected)
        bottom.addWidget(open_btn)
        close_btn = QPushButton("بستن")
        close_btn.clicked.connect(self.reject)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.run_search)
        if self.initial_query:
            self.search_input.setText(self.initial_query)
            QTimer.singleShot(0, self.run_search)
        self.search_input.setFocus()

    def _schedule_search(self, text):
        if len(text.strip()) >= 2:
            self.timer.start()
        else:
            self.timer.stop()
            self.results = []
            self.table.setRowCount(0)
            self.status_label.setText("حداقل دو حرف وارد کنید.")

    def run_search(self):
        query = self.search_input.text().strip()
        if len(query) < 2:
            return
        try:
            self.results = self.db.global_search(query, limit=150)
        except Exception as exc:
            self.status_label.setText(f"جستجو انجام نشد: {exc}")
            return
        self.table.setRowCount(len(self.results))
        for row_index, item in enumerate(self.results):
            values = [
                TYPE_LABELS.get(item.get("entity_type"), item.get("entity_type") or ""),
                item.get("title") or "",
                item.get("subtitle") or "",
                item.get("zone_id") if item.get("zone_id") is not None else "—",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value)))
                if column in (0, 3):
                    cell.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, column, cell)
        self.status_label.setText(f"{len(self.results)} نتیجه پیدا شد.")
        if self.results:
            self.table.selectRow(0)

    def _activate_selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.results):
            return
        self.result_activated.emit(dict(self.results[row]))
        self.accept()
