# -*- coding: utf-8 -*-
"""
پنجره «تنظیمات سیستم»:
  - تغییر نام کاربری و رمز عبور ادمین
  - بکاپ‌گیری کامل از دیتابیس
  - بازگرداندن بکاپ
  - ریست کامل سیستم (پاک کردن همه داده‌های عملیاتی)
  - آپلود هدر سفارشی (تصویر دلخواه کاربر به‌جای هدر رسمی متنی)

عملیات حساس (ریست سیستم و بازگرداندن بکاپ) نیازمند وارد کردن مجدد
رمز عبور ادمین است.
"""

import os
import shutil
import tempfile
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QMessageBox, QGroupBox, QFileDialog, QInputDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QCheckBox, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap

from header_widget import build_official_header, HEADER_HEIGHT
from jalali_utils import convert_dates_in_text
from access_control import available_roles, role_title
from ui_scroll import scroll_page


class SystemSettingsWindow(QWidget):
    """پنجره یکپارچه تنظیمات سیستم شامل چند زیر-تب."""
    back_requested = pyqtSignal()
    header_changed = pyqtSignal()  # وقتی هدر سفارشی تغییر کند، سایر پنجره‌ها باید بازسازی شوند
    restart_required = pyqtSignal()  # پس از ریست سیستم یا بازگردانی بکاپ

    def __init__(self, db, current_user=None, initial_tab=None):
        super().__init__()
        self.db = db
        self.current_user = current_user or db.get_current_user() or {}
        self.is_admin = self.current_user.get("role") == "admin"
        self.setWindowTitle("تنظیمات حساب و سیستم")
        self.resize(1300, 850)
        self._build_ui()
        if initial_tab:
            self._jump_to_tab(initial_tab)

    def _jump_to_tab(self, tab_title):
        for i in range(self.sub_tabs.count()):
            if self.sub_tabs.tabText(i) == tab_title:
                self.sub_tabs.setCurrentIndex(i)
                return

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header_widget = build_official_header(app_subtitle="تنظیمات سیستم", db=self.db)
        outer.addWidget(self.header_widget)

        body = QVBoxLayout()
        body.setContentsMargins(30, 20, 30, 20)

        back_btn = QPushButton("‹ بازگشت به داشبورد")
        back_btn.setFixedWidth(180)
        back_btn.clicked.connect(self.back_requested.emit)
        body.addWidget(back_btn)
        body.addSpacing(12)

        self.sub_tabs = QTabWidget()
        self.sub_tabs.addTab(scroll_page(self._build_credentials_tab(), min_height=560), "حساب کاربری")
        if self.is_admin:
            self.sub_tabs.addTab(scroll_page(self._build_users_tab(), min_height=760), "کاربران و دسترسی‌ها")
            self.sub_tabs.addTab(scroll_page(self._build_backup_tab(), min_height=650), "بکاپ‌گیری و بازگردانی")
            self.sub_tabs.addTab(scroll_page(self._build_reset_tab(), min_height=520), "ریست سیستم")
            self.sub_tabs.addTab(scroll_page(self._build_header_tab(), min_height=560), "هدر سفارشی")
            self.sub_tabs.addTab(scroll_page(self._build_signature_documents_tab(), min_height=650), "امضا و اسناد")
            self.sub_tabs.addTab(scroll_page(self._build_ai_triage_tab(), min_height=520), "هوش مصنوعی")
            self.sub_tabs.addTab(scroll_page(self._build_audit_tab(), min_height=680), "سابقه فعالیت")
        body.addWidget(self.sub_tabs)

        outer.addLayout(body)

    def _refresh_header(self):
        """پس از تغییر هدر سفارشی، هدر بالای همین پنجره را دوباره می‌سازد."""
        new_header = build_official_header(app_subtitle="تنظیمات سیستم", db=self.db)
        layout = self.layout()
        layout.replaceWidget(self.header_widget, new_header)
        self.header_widget.deleteLater()
        self.header_widget = new_header
        self.header_changed.emit()

    # ==================== تب ۱: نام کاربری و رمز عبور ====================
    def _build_credentials_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        group = QGroupBox("تنظیمات حساب کاربری فعلی")
        form = QFormLayout(group)
        form.setSpacing(14)

        self.current_username_label = QLabel(self.current_user.get("username", ""))
        form.addRow("نام کاربری فعلی:", self.current_username_label)
        form.addRow("نقش:", QLabel(role_title(self.current_user.get("role"))))

        self.account_full_name_input = QLineEdit(self.current_user.get("full_name", ""))
        form.addRow("نام و نام خانوادگی:", self.account_full_name_input)

        self.account_mobile_input = QLineEdit(self.current_user.get("mobile", "") or "")
        form.addRow("شماره تماس:", self.account_mobile_input)

        self.new_username_input = QLineEdit(self.current_user.get("username", ""))
        form.addRow("نام کاربری:", self.new_username_input)

        self.current_password_input = QLineEdit()
        self.current_password_input.setEchoMode(QLineEdit.Password)
        self.current_password_input.setPlaceholderText("برای تأیید تغییرات وارد کنید")
        form.addRow("رمز عبور فعلی:", self.current_password_input)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        self.new_password_input.setPlaceholderText("در صورت عدم تغییر، خالی بگذارید")
        form.addRow("رمز عبور جدید:", self.new_password_input)

        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        form.addRow("تکرار رمز جدید:", self.confirm_password_input)

        save_btn = QPushButton("ذخیره تغییرات حساب")
        save_btn.setProperty("success", True)
        save_btn.clicked.connect(self._on_save_credentials)
        form.addRow(save_btn)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _on_save_credentials(self):
        user_id = self.current_user.get("id")
        current_password = self.current_password_input.text()
        if not user_id or not self.db.verify_user_password(user_id, current_password):
            QMessageBox.warning(self, "تأیید ناموفق", "رمز عبور فعلی صحیح نیست.")
            return
        username = self.new_username_input.text().strip()
        full_name = self.account_full_name_input.text().strip()
        mobile = self.account_mobile_input.text().strip()
        new_password = self.new_password_input.text()
        confirm = self.confirm_password_input.text()
        if not username or not full_name:
            QMessageBox.warning(self, "اطلاعات ناقص", "نام کاربری و نام کامل الزامی است.")
            return
        if new_password:
            if len(new_password) < 8:
                QMessageBox.warning(self, "رمز ضعیف", "رمز عبور باید حداقل ۱۰ کاراکتر باشد.")
                return
            if new_password != confirm:
                QMessageBox.warning(self, "عدم تطابق", "رمز عبور جدید و تکرار آن یکسان نیستند.")
                return
        try:
            updated = self.db.update_user(user_id, username=username, full_name=full_name, mobile=mobile)
            if new_password:
                self.db.set_user_password(user_id, new_password, must_change_password=False)
            self.current_user.update(updated)
            self.db.set_current_user(self.current_user)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))
            return
        self.current_username_label.setText(username)
        self.current_password_input.clear()
        self.new_password_input.clear()
        self.confirm_password_input.clear()
        QMessageBox.information(self, "موفق", "اطلاعات حساب با موفقیت ذخیره شد.")

    # ==================== مدیریت کاربران ====================
    def _build_users_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        form_group = QGroupBox("ایجاد یا ویرایش حساب کاربری")
        form = QFormLayout(form_group)
        self.user_edit_id = None
        self.user_username_input = QLineEdit()
        self.user_full_name_input = QLineEdit()
        self.user_mobile_input = QLineEdit()
        self.user_role_combo = QComboBox()
        for key, title in available_roles():
            self.user_role_combo.addItem(title, key)
        self.user_password_input = QLineEdit()
        self.user_password_input.setEchoMode(QLineEdit.Password)
        self.user_password_input.setPlaceholderText("برای کاربر جدید الزامی؛ حداقل ۱۰ کاراکتر")
        self.user_active_check = QCheckBox("حساب فعال باشد")
        self.user_active_check.setChecked(True)
        self.user_force_change_check = QCheckBox("در ورود بعدی تغییر رمز الزامی باشد")
        self.user_force_change_check.setChecked(True)
        form.addRow("نام کاربری:", self.user_username_input)
        form.addRow("نام کامل:", self.user_full_name_input)
        form.addRow("شماره تماس:", self.user_mobile_input)
        form.addRow("نقش:", self.user_role_combo)
        form.addRow("رمز موقت:", self.user_password_input)
        form.addRow("وضعیت:", self.user_active_check)
        form.addRow("امنیت:", self.user_force_change_check)

        buttons = QHBoxLayout()
        save_btn = QPushButton("ثبت کاربر جدید")
        save_btn.setProperty("success", True)
        save_btn.clicked.connect(self._save_user)
        buttons.addWidget(save_btn)
        update_btn = QPushButton("ذخیره ویرایش")
        update_btn.clicked.connect(self._update_selected_user)
        buttons.addWidget(update_btn)
        reset_btn = QPushButton("تغییر رمز انتخاب‌شده")
        reset_btn.clicked.connect(self._reset_selected_user_password)
        buttons.addWidget(reset_btn)
        deactivate_btn = QPushButton("غیرفعال‌کردن حساب")
        deactivate_btn.setProperty("danger", True)
        deactivate_btn.clicked.connect(self._deactivate_selected_user)
        buttons.addWidget(deactivate_btn)
        clear_btn = QPushButton("پاک‌کردن فرم")
        clear_btn.clicked.connect(self._clear_user_form)
        buttons.addWidget(clear_btn)
        form.addRow(buttons)
        layout.addWidget(form_group)

        self.users_table = QTableWidget(0, 7)
        self.users_table.setHorizontalHeaderLabels(["شناسه", "نام کاربری", "نام کامل", "نقش", "تماس", "وضعیت", "آخرین ورود"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.itemSelectionChanged.connect(self._load_selected_user)
        layout.addWidget(self.users_table, 1)
        self._refresh_users_table()
        return tab

    def _refresh_users_table(self):
        if not hasattr(self, "users_table"):
            return
        users = self.db.list_users(include_inactive=True)
        self.users_table.setRowCount(len(users))
        for row, user in enumerate(users):
            values = [user["id"], user["username"], user["full_name"], role_title(user["role"]),
                      user.get("mobile") or "", "فعال" if user.get("is_active") else "غیرفعال",
                      user.get("last_login_at") or "—"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(convert_dates_in_text(str(value)))
                if col == 0:
                    item.setData(Qt.UserRole, user["id"])
                self.users_table.setItem(row, col, item)

    def _selected_user_id(self):
        row = self.users_table.currentRow() if hasattr(self, "users_table") else -1
        if row < 0:
            return None
        item = self.users_table.item(row, 0)
        return int(item.data(Qt.UserRole) or item.text()) if item else None

    def _load_selected_user(self):
        user_id = self._selected_user_id()
        if not user_id:
            return
        user = self.db.get_user(user_id)
        if not user:
            return
        self.user_edit_id = user_id
        self.user_username_input.setText(user.get("username") or "")
        self.user_full_name_input.setText(user.get("full_name") or "")
        self.user_mobile_input.setText(user.get("mobile") or "")
        index = self.user_role_combo.findData(user.get("role"))
        if index >= 0:
            self.user_role_combo.setCurrentIndex(index)
        self.user_active_check.setChecked(bool(user.get("is_active")))
        self.user_force_change_check.setChecked(bool(user.get("must_change_password")))
        self.user_password_input.clear()

    def _clear_user_form(self):
        self.user_edit_id = None
        self.user_username_input.clear()
        self.user_full_name_input.clear()
        self.user_mobile_input.clear()
        self.user_password_input.clear()
        self.user_role_combo.setCurrentIndex(0)
        self.user_active_check.setChecked(True)
        self.user_force_change_check.setChecked(True)
        if hasattr(self, "users_table"):
            self.users_table.clearSelection()

    def _save_user(self):
        try:
            self.db.create_user(
                self.user_username_input.text(), self.user_full_name_input.text(),
                self.user_password_input.text(), self.user_role_combo.currentData(),
                self.user_mobile_input.text().strip(), self.user_active_check.isChecked(),
                self.user_force_change_check.isChecked(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "ثبت انجام نشد", str(exc))
            return
        self._clear_user_form()
        self._refresh_users_table()
        QMessageBox.information(self, "موفق", "حساب کاربری ایجاد شد.")

    def _update_selected_user(self):
        user_id = self.user_edit_id or self._selected_user_id()
        if not user_id:
            QMessageBox.information(self, "انتخاب کاربر", "ابتدا یک کاربر را انتخاب کنید.")
            return
        try:
            self.db.update_user(
                user_id, username=self.user_username_input.text(),
                full_name=self.user_full_name_input.text(), mobile=self.user_mobile_input.text().strip(),
                role=self.user_role_combo.currentData(), is_active=self.user_active_check.isChecked(),
                must_change_password=self.user_force_change_check.isChecked(),
            )
            if self.user_password_input.text():
                self.db.set_user_password(user_id, self.user_password_input.text(),
                                          must_change_password=self.user_force_change_check.isChecked())
        except Exception as exc:
            QMessageBox.warning(self, "ویرایش انجام نشد", str(exc))
            return
        self._refresh_users_table()
        QMessageBox.information(self, "موفق", "اطلاعات کاربر به‌روزرسانی شد.")

    def _reset_selected_user_password(self):
        user_id = self._selected_user_id()
        if not user_id:
            QMessageBox.information(self, "انتخاب کاربر", "ابتدا یک کاربر را انتخاب کنید.")
            return
        password, ok = QInputDialog.getText(self, "رمز موقت جدید", "رمز موقت قوی حداقل ۱۰ کاراکتری:", QLineEdit.Password)
        if not ok:
            return
        try:
            self.db.set_user_password(user_id, password, must_change_password=True)
        except Exception as exc:
            QMessageBox.warning(self, "تغییر رمز انجام نشد", str(exc))
            return
        QMessageBox.information(self, "موفق", "رمز موقت ثبت شد و کاربر در ورود بعدی باید آن را تغییر دهد.")

    def _deactivate_selected_user(self):
        user_id = self._selected_user_id()
        if not user_id:
            QMessageBox.information(self, "انتخاب کاربر", "ابتدا یک کاربر را انتخاب کنید.")
            return
        try:
            self.db.deactivate_user(user_id)
        except Exception as exc:
            QMessageBox.warning(self, "غیرفعال‌سازی انجام نشد", str(exc))
            return
        self._refresh_users_table()

    # ==================== تب ۲: بکاپ‌گیری و بازگردانی ====================
    def _build_backup_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        backup_group = QGroupBox("بکاپ‌گیری کامل از سامانه")
        backup_layout = QVBoxLayout(backup_group)
        backup_info = QLabel(
            "نسخه کامل دیتابیس شامل بلوک‌ها، نقشه‌ها، پرونده‌های محله، کاربران، درخواست‌ها و گزارش‌های مدیریتی ذخیره می‌شود. "
            "سامانه در شروع هر روز نیز یک بکاپ خودکار سالم نگهداری می‌کند."
        )
        backup_info.setWordWrap(True)
        backup_layout.addWidget(backup_info)
        self.backup_health_label = QLabel()
        self.backup_health_label.setWordWrap(True)
        backup_layout.addWidget(self.backup_health_label)

        backup_buttons = QHBoxLayout()
        backup_btn = QPushButton("تهیه بکاپ کامل در مسیر دلخواه")
        backup_btn.setProperty("success", True)
        backup_btn.clicked.connect(self._on_backup_clicked)
        backup_buttons.addWidget(backup_btn)

        encrypted_btn = QPushButton("تهیه بکاپ رمزگذاری‌شده")
        encrypted_btn.clicked.connect(self._on_encrypted_backup_clicked)
        backup_buttons.addWidget(encrypted_btn)

        daily_btn = QPushButton("ایجاد بکاپ خودکار امروز")
        daily_btn.clicked.connect(self._on_daily_backup_clicked)
        backup_buttons.addWidget(daily_btn)
        backup_layout.addLayout(backup_buttons)
        layout.addWidget(backup_group)

        restore_group = QGroupBox("بازگردانی از فایل بکاپ")
        restore_layout = QVBoxLayout(restore_group)
        restore_info = QLabel(
            "با بازگردانی بکاپ، اطلاعات فعلی با محتوای فایل انتخابی جایگزین می‌شود. "
            "قبل از جایگزینی، سامانه یک نسخه ایمنی خودکار تهیه و سلامت فایل را کنترل می‌کند."
        )
        restore_info.setWordWrap(True)
        restore_info.setStyleSheet("color: #a4262c;")
        restore_layout.addWidget(restore_info)
        restore_btn = QPushButton("انتخاب فایل بکاپ و بازگردانی")
        restore_btn.setProperty("danger", True)
        restore_btn.clicked.connect(self._on_restore_clicked)
        restore_layout.addWidget(restore_btn)
        layout.addWidget(restore_group)

        registry_group = QGroupBox("تاریخچه و سلامت بکاپ‌ها")
        registry_layout = QVBoxLayout(registry_group)
        registry_buttons = QHBoxLayout()
        refresh_btn = QPushButton("بروزرسانی فهرست")
        refresh_btn.clicked.connect(self._refresh_backup_registry)
        registry_buttons.addWidget(refresh_btn)
        validate_btn = QPushButton("بررسی سلامت فایل انتخاب‌شده")
        validate_btn.clicked.connect(self._validate_selected_backup)
        registry_buttons.addWidget(validate_btn)
        restore_test_btn = QPushButton("آزمون بازیابی آخرین بکاپ")
        restore_test_btn.clicked.connect(self._test_latest_backup_restore)
        registry_buttons.addWidget(restore_test_btn)
        registry_buttons.addStretch()
        registry_layout.addLayout(registry_buttons)

        self.backup_registry_table = QTableWidget(0, 7)
        self.backup_registry_table.setHorizontalHeaderLabels(
            ["زمان", "نوع", "علت", "حجم", "وضعیت", "مسیر", "SHA-256"]
        )
        self.backup_registry_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.backup_registry_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.backup_registry_table.setSelectionBehavior(QTableWidget.SelectRows)
        registry_layout.addWidget(self.backup_registry_table)
        layout.addWidget(registry_group, 1)
        self._refresh_backup_registry()
        return tab

    def _on_backup_clicked(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"javanrood_backup_{timestamp}.db"
        default_path = os.path.join(os.path.expanduser("~"), default_name)

        save_path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره فایل بکاپ", default_path, "Database Backup (*.db)"
        )
        if not save_path:
            return

        try:
            self.db.create_backup(save_path)
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"تهیه بکاپ با خطا مواجه شد:\n{e}")
            return

        QMessageBox.information(self, "موفق", f"بکاپ معتبر SQLite با موفقیت در مسیر زیر ذخیره شد:\n{save_path}")

    def _on_encrypted_backup_clicked(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = os.path.join(os.path.expanduser("~"), f"javanrood_secure_{timestamp}.jrbak")
        save_path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره بکاپ رمزگذاری‌شده", default_path, "Javanrood Encrypted Backup (*.jrbak)"
        )
        if not save_path:
            return
        password, ok = QInputDialog.getText(
            self, "رمز بکاپ", "یک رمز قوی و مستقل برای فایل بکاپ وارد کنید:", QLineEdit.Password
        )
        if not ok:
            return
        confirm, ok = QInputDialog.getText(
            self, "تکرار رمز بکاپ", "رمز بکاپ را دوباره وارد کنید:", QLineEdit.Password
        )
        if not ok or password != confirm:
            QMessageBox.warning(self, "عدم تطابق", "رمز بکاپ و تکرار آن یکسان نیستند.")
            return
        try:
            self.db.create_encrypted_backup(save_path, password)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", str(exc))
            return
        self._refresh_backup_registry()
        QMessageBox.information(self, "بکاپ امن", f"بکاپ رمزگذاری‌شده ایجاد شد:\n{save_path}")

    def _on_daily_backup_clicked(self):
        try:
            path = self.db.ensure_daily_backup(keep=14)
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"بکاپ خودکار ایجاد نشد:\n{exc}")
            return
        self._refresh_backup_registry()
        QMessageBox.information(self, "بکاپ روزانه", f"نسخه روزانه سامانه آماده است:\n{path or 'قبلاً ایجاد شده است.'}")

    def _refresh_backup_registry(self):
        if not hasattr(self, "backup_registry_table"):
            return
        rows = self.db.list_registered_backups(limit=100)
        try:
            health = self.db.backup_health_status()
            age = health.get("age_hours")
            age_text = "" if age is None else f" — عمر آخرین بکاپ: {age:.1f} ساعت"
            self.backup_health_label.setText(f"وضعیت بکاپ: {health.get('status')}{age_text}")
            self.backup_health_label.setStyleSheet(
                "padding:8px;border-radius:7px;background:#ecfdf3;color:#176b3a" if health.get("healthy")
                else "padding:8px;border-radius:7px;background:#fff7e6;color:#8a4b00"
            )
        except Exception:
            self.backup_health_label.setText("وضعیت بکاپ قابل بررسی نیست.")
        self.backup_registry_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            size_mb = float(item.get("file_size") or 0) / (1024 * 1024)
            values = [
                item.get("created_at") or "",
                "خودکار" if item.get("backup_type") == "automatic" else ("رمزگذاری‌شده" if item.get("backup_type") == "encrypted" else "دستی"),
                item.get("reason") or "—",
                f"{size_mb:.2f} MB",
                item.get("validation_status") or "نامشخص",
                item.get("file_path") or "",
                item.get("checksum") or "",
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value)))
                if col == 0:
                    cell.setData(Qt.UserRole, item.get("file_path"))
                self.backup_registry_table.setItem(row_index, col, cell)

    def _test_latest_backup_restore(self):
        ok, message = self.db.test_latest_backup_restore()
        if ok:
            QMessageBox.information(self, "آزمون بازیابی", message)
        else:
            QMessageBox.warning(self, "آزمون بازیابی", message)

    def _validate_selected_backup(self):
        row = self.backup_registry_table.currentRow() if hasattr(self, "backup_registry_table") else -1
        if row < 0:
            QMessageBox.information(self, "انتخاب بکاپ", "ابتدا یک ردیف بکاپ را انتخاب کنید.")
            return
        item = self.backup_registry_table.item(row, 0)
        path = item.data(Qt.UserRole) if item else None
        valid, message = self.db.validate_database_file(path)
        if valid:
            QMessageBox.information(self, "بکاپ سالم", "ساختار SQLite و جدول‌های اصلی فایل سالم هستند.")
        else:
            QMessageBox.critical(self, "بکاپ نامعتبر", message)

    def _on_restore_clicked(self):
        open_path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل بکاپ", os.path.expanduser("~"), "Backup Files (*.db *.jrbak)"
        )
        if not open_path:
            return

        decrypted_temp = None
        source_path = open_path
        if open_path.lower().endswith(".jrbak"):
            backup_password, ok = QInputDialog.getText(
                self, "رمز فایل بکاپ", "رمز فایل بکاپ رمزگذاری‌شده را وارد کنید:", QLineEdit.Password
            )
            if not ok:
                return
            fd, decrypted_temp = tempfile.mkstemp(prefix="javanrood_decrypted_", suffix=".db")
            os.close(fd)
            try:
                self.db.decrypt_backup_to_database(open_path, decrypted_temp, backup_password)
                source_path = decrypted_temp
            except Exception as exc:
                try:
                    os.remove(decrypted_temp)
                except OSError:
                    pass
                QMessageBox.critical(self, "فایل بکاپ نامعتبر", str(exc))
                return
        valid_backup, validation_message = self.db.validate_database_file(source_path)
        if not valid_backup:
            if decrypted_temp:
                try:
                    os.remove(decrypted_temp)
                except OSError:
                    pass
            QMessageBox.critical(self, "فایل بکاپ نامعتبر", validation_message)
            return

        password, ok = QInputDialog.getText(
            self, "تأیید هویت", "برای بازگردانی بکاپ، رمز عبور ادمین را وارد کنید:",
            QLineEdit.Password
        )
        if not ok:
            return
        if not self.db.verify_user_password(self.current_user.get("id"), password):
            QMessageBox.critical(self, "خطا", "رمز عبور اشتباه است. عملیات لغو شد.")
            return

        reply = QMessageBox.question(
            self, "تأیید نهایی",
            "با ادامه این عملیات، تمام اطلاعات فعلی سامانه با اطلاعات فایل بکاپ جایگزین می‌شود "
            "و این کار قابل بازگشت نیست. آیا مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        safety_backup = None
        restore_temp = None
        db_path = self.db.db_path
        database_closed = False
        try:
            safety_backup = self.db.create_automatic_backup("pre_restore")
            restore_temp = db_path + ".restore_tmp"
            if os.path.exists(restore_temp):
                os.remove(restore_temp)
            shutil.copyfile(source_path, restore_temp)
            valid_temp, temp_message = self.db.validate_database_file(restore_temp)
            if not valid_temp:
                raise RuntimeError(temp_message)

            self.db.checkpoint()
            self.db.close()
            database_closed = True
            for suffix in ("-wal", "-shm"):
                side_file = db_path + suffix
                if os.path.exists(side_file):
                    os.remove(side_file)
            os.replace(restore_temp, db_path)
            restore_temp = None
        except Exception as e:
            if restore_temp and os.path.exists(restore_temp):
                try:
                    os.remove(restore_temp)
                except OSError:
                    pass
            recovered = False
            if database_closed and safety_backup and os.path.exists(safety_backup):
                try:
                    shutil.copyfile(safety_backup, db_path)
                    recovered = True
                except Exception:
                    recovered = False
            recovery_text = "دیتابیس قبلی بازیابی شد." if recovered else "دیتابیس اصلی تغییر نکرده است."
            QMessageBox.critical(
                self, "خطا",
                f"بازگردانی بکاپ با خطا مواجه شد:\n{e}\n\n"
                f"نسخه ایمنی فعلی: {safety_backup or 'ایجاد نشد'}\n{recovery_text}"
            )
            if decrypted_temp and os.path.exists(decrypted_temp):
                try:
                    os.remove(decrypted_temp)
                except OSError:
                    pass
            if database_closed:
                self.restart_required.emit()
            return

        if decrypted_temp and os.path.exists(decrypted_temp):
            try:
                os.remove(decrypted_temp)
            except OSError:
                pass
        QMessageBox.information(
            self, "موفق",
            "بکاپ با موفقیت بازگردانی شد. برنامه اکنون به‌صورت خودکار بازنشانی می‌شود.\n\n"
            f"نسخه ایمنی قبل از بازگردانی:\n{safety_backup}"
        )
        self.restart_required.emit()

    # ==================== تب ۳: ریست سیستم ====================
    def _build_reset_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        group = QGroupBox("ریست کامل سیستم")
        group_layout = QVBoxLayout(group)

        warn = QLabel(
            "⚠ با ریست سیستم، تمام داده‌های عملیاتی زیر برای همیشه حذف می‌شوند:\n"
            "محدوده شهر، تمام مناطق/بلوک‌ها، خیابان‌ها، اماکن، تایل‌های نقشه آفلاین، "
            "اعضای شورای محلات، محل جلسات، درخواست‌ها و اقدامات.\n\n"
            "نام‌کاربری/رمز عبور ادمین و هدر سفارشی حذف نخواهند شد.\n"
            "پیشنهاد می‌شود پیش از ریست، حتماً یک بکاپ کامل تهیه کنید."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #a4262c; background: #fdecec; padding: 10px; border-radius: 6px;")
        group_layout.addWidget(warn)

        self.reset_stats_label = QLabel("")
        self.reset_stats_label.setWordWrap(True)
        group_layout.addWidget(self.reset_stats_label)
        self._update_reset_stats()

        reset_btn = QPushButton("🗑️ ریست کامل سیستم")
        reset_btn.setProperty("danger", True)
        reset_btn.clicked.connect(self._on_reset_clicked)
        group_layout.addWidget(reset_btn)

        layout.addWidget(group)
        layout.addStretch()
        return tab

    def _update_reset_stats(self):
        stats = self.db.get_system_stats()
        text = (
            f"وضعیت فعلی داده‌ها — مناطق: {stats['zones_count']} | "
            f"خیابان‌ها: {stats['streets_count']} | اماکن: {stats['places_count']} | "
            f"تایل‌های آفلاین: {stats['tiles_count']} | اعضای شورا: {stats['members_count']} | "
            f"درخواست‌ها: {stats['requests_count']} | اقدامات: {stats['actions_count']}"
        )
        self.reset_stats_label.setText(text)

    def _on_reset_clicked(self):
        password, ok = QInputDialog.getText(
            self, "تأیید هویت", "برای ریست کامل سیستم، رمز عبور ادمین را وارد کنید:",
            QLineEdit.Password
        )
        if not ok:
            return
        if not self.db.verify_user_password(self.current_user.get("id"), password):
            QMessageBox.critical(self, "خطا", "رمز عبور اشتباه است. عملیات لغو شد.")
            return

        reply = QMessageBox.question(
            self, "تأیید نهایی ریست سیستم",
            "آیا کاملاً مطمئن هستید که می‌خواهید تمام داده‌های سامانه را برای همیشه حذف کنید؟\n"
            "این عملیات قابل بازگشت نیست.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            safety_backup = self.db.create_automatic_backup("pre_reset")
            self.db.reset_all_data()
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"ریست سیستم انجام نشد:\n{e}")
            return
        self._update_reset_stats()
        QMessageBox.information(
            self, "انجام شد",
            "سیستم با موفقیت ریست شد و تمام داده‌های عملیاتی حذف گردید.\n"
            "برنامه اکنون بازنشانی می‌شود.\n\n"
            f"نسخه ایمنی قبل از ریست:\n{safety_backup}"
        )
        self.restart_required.emit()

    # ==================== تب ۴: هدر سفارشی ====================
    def _build_header_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        info = QLabel(
            f"می‌توانید یک تصویر دلخواه (لوگو یا بنر) به‌عنوان هدر برنامه بارگذاری کنید. "
            f"این تصویر جایگزین هدر متنی رسمی خواهد شد.\n\n"
            f"اندازه هدر در برنامه ثابت است: ارتفاع {HEADER_HEIGHT} پیکسل (عرض به‌صورت خودکار و با حفظ نسبت تصویر تنظیم می‌شود). "
            f"برای بهترین کیفیت، تصویری با ارتفاع حدود {HEADER_HEIGHT * 3} پیکسل یا بیشتر و فرمت PNG یا JPG آماده کنید."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        preview_group = QGroupBox("پیش‌نمایش هدر فعلی")
        preview_layout = QVBoxLayout(preview_group)
        self.header_preview_label = QLabel()
        self.header_preview_label.setAlignment(Qt.AlignCenter)
        self.header_preview_label.setMinimumHeight(HEADER_HEIGHT + 10)
        self.header_preview_label.setStyleSheet("background: #0b1f3a; border-radius: 6px;")
        preview_layout.addWidget(self.header_preview_label)
        layout.addWidget(preview_group)
        self._update_header_preview()

        btn_row = QHBoxLayout()
        upload_btn = QPushButton("📤 بارگذاری تصویر هدر سفارشی")
        upload_btn.setProperty("success", True)
        upload_btn.clicked.connect(self._on_upload_header_clicked)
        btn_row.addWidget(upload_btn)

        clear_btn = QPushButton("بازگشت به هدر رسمی پیش‌فرض")
        clear_btn.clicked.connect(self._on_clear_header_clicked)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        return tab

    def _build_ai_triage_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        info = QLabel(
            "پیشنهاد خودکار دسته‌بندی و فوریت برای درخواست‌های مردمی، بر اساس متن شرح "
            "درخواست، همیشه از یک موتور کلیدواژه‌ای آفلاین (بدون نیاز به اینترنت) فعال است.\n\n"
            "در صورت تمایل به دقت بالاتر، می‌توانید یک سرویس هوش مصنوعی خارجی (مطابق با "
            "قالب API استاندارد گفتگو) متصل کنید. اگر اتصال اینترنت در لحظه برقرار نباشد یا "
            "خطایی رخ دهد، برنامه به‌طور خودکار و بی‌صدا به همان موتور آفلاین برمی‌گردد."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        group = QGroupBox("اتصال اختیاری به سرویس هوش مصنوعی")
        form = QFormLayout(group)
        form.setSpacing(10)

        self.ai_enabled_check = QCheckBox("فعال‌سازی اتصال به سرویس هوش مصنوعی خارجی")
        form.addRow("", self.ai_enabled_check)

        self.ai_api_url_input = QLineEdit()
        self.ai_api_url_input.setPlaceholderText("https://api.example.com/v1/chat/completions")
        form.addRow("آدرس سرویس (API URL):", self.ai_api_url_input)

        self.ai_api_key_input = QLineEdit()
        self.ai_api_key_input.setEchoMode(QLineEdit.Password)
        self.ai_api_key_input.setPlaceholderText("کلید API")
        form.addRow("کلید API:", self.ai_api_key_input)

        layout.addWidget(group)

        privacy_note = QLabel(
            "توجه: در صورت فعال‌بودن این اتصال، فقط متن آزاد «شرح درخواست» برای پیشنهاد "
            "دسته‌بندی به سرویس خارجی ارسال می‌شود. نام شهروند، شماره تماس و مختصات مکانی "
            "هرگز ارسال نمی‌شوند."
        )
        privacy_note.setWordWrap(True)
        privacy_note.setStyleSheet("color:#666; font-size:12px;")
        layout.addWidget(privacy_note)

        save_btn = QPushButton("ذخیره تنظیمات هوش مصنوعی")
        save_btn.setProperty("success", True)
        save_btn.clicked.connect(self._on_save_ai_triage_settings)
        layout.addWidget(save_btn)

        layout.addStretch()
        self._load_ai_triage_settings()
        return tab

    def _load_ai_triage_settings(self):
        settings = self.db.get_smart_triage_settings()
        self.ai_enabled_check.setChecked(settings["enabled"])
        self.ai_api_url_input.setText(settings["api_url"])
        self.ai_api_key_input.setText(settings["api_key"])

    def _on_save_ai_triage_settings(self):
        enabled = self.ai_enabled_check.isChecked()
        api_url = self.ai_api_url_input.text().strip()
        api_key = self.ai_api_key_input.text().strip()
        if enabled and (not api_url or not api_key):
            QMessageBox.warning(
                self, "خطا",
                "برای فعال‌سازی اتصال هوش مصنوعی، آدرس سرویس و کلید API هر دو الزامی هستند."
            )
            return
        self.db.set_smart_triage_settings(enabled, api_url, api_key)
        QMessageBox.information(self, "ذخیره شد", "تنظیمات هوش مصنوعی ذخیره شد.")

    def _update_header_preview(self):
        custom_path = self.db.get_custom_header_image()
        if custom_path and os.path.exists(custom_path):
            pixmap = QPixmap(custom_path)
            if not pixmap.isNull():
                scaled = pixmap.scaledToHeight(HEADER_HEIGHT, Qt.SmoothTransformation)
                self.header_preview_label.setPixmap(scaled)
                return
        self.header_preview_label.setPixmap(QPixmap())
        self.header_preview_label.setText("در حال حاضر هدر رسمی پیش‌فرض (متنی) فعال است.")
        self.header_preview_label.setStyleSheet(
            "background: #0b1f3a; color: #c9a227; border-radius: 6px; font-weight: bold;"
        )

    def _on_upload_header_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب تصویر هدر", os.path.expanduser("~"),
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return

        # کپی تصویر به داخل پوشه داده‌های برنامه تا در صورت جابه‌جایی/حذف فایل اصلی، هدر خراب نشود
        headers_dir = os.path.join(os.path.dirname(self.db.db_path), "custom_headers")
        os.makedirs(headers_dir, exist_ok=True)
        ext = os.path.splitext(file_path)[1]
        dest_path = os.path.join(headers_dir, f"header{ext}")

        try:
            shutil.copyfile(file_path, dest_path)
        except Exception as e:
            QMessageBox.critical(self, "خطا", f"کپی تصویر با خطا مواجه شد:\n{e}")
            return

        self.db.set_custom_header_image(dest_path)
        self._update_header_preview()
        self._refresh_header()
        QMessageBox.information(self, "موفق", "هدر سفارشی با موفقیت اعمال شد.")

    def _on_clear_header_clicked(self):
        self.db.clear_custom_header_image()
        self._update_header_preview()
        self._refresh_header()
        QMessageBox.information(self, "بازگردانی شد", "هدر رسمی پیش‌فرض بازگردانده شد.")

    # ==================== امضا و اسناد رسمی ====================
    def _build_signature_documents_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        info = QLabel(
            "امضای اسکن‌شده و مشخصات امضاکننده در خروجی‌های رسمی Word و PDF استفاده می‌شوند. "
            "QR هر سند دارای کد اعتبارسنجی یکتا است. تصویر امضا در پوشه داده‌های برنامه کپی می‌شود."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        settings = self.db.get_official_signature()
        group = QGroupBox("تنظیمات امضا و اعتبارسنجی سند")
        form = QFormLayout(group)
        self.signer_name_input = QLineEdit(settings.get("signer_name") or "")
        self.signer_title_input = QLineEdit(settings.get("signer_title") or "")
        self.verification_url_input = QLineEdit(settings.get("verification_base_url") or "")
        self.verification_url_input.setPlaceholderText("اختیاری؛ مثال: https://example.ir/verify")
        form.addRow("نام و نام خانوادگی امضاکننده:", self.signer_name_input)
        form.addRow("سمت امضاکننده:", self.signer_title_input)
        form.addRow("نشانی پایه اعتبارسنجی QR:", self.verification_url_input)

        self.signature_preview = QLabel()
        self.signature_preview.setAlignment(Qt.AlignCenter)
        self.signature_preview.setMinimumHeight(150)
        self.signature_preview.setStyleSheet("background:white; border:1px solid #d7dbe3; border-radius:8px;")
        form.addRow("پیش‌نمایش امضا:", self.signature_preview)
        layout.addWidget(group)

        row = QHBoxLayout()
        upload = QPushButton("بارگذاری امضای اسکن‌شده")
        upload.setProperty("success", True)
        upload.clicked.connect(self._upload_official_signature)
        row.addWidget(upload)
        save = QPushButton("ذخیره مشخصات")
        save.clicked.connect(self._save_official_signature_settings)
        row.addWidget(save)
        clear = QPushButton("حذف تصویر امضا")
        clear.setProperty("danger", True)
        clear.clicked.connect(self._clear_official_signature)
        row.addWidget(clear)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        self._update_signature_preview()
        return tab

    def _update_signature_preview(self):
        if not hasattr(self, "signature_preview"):
            return
        settings = self.db.get_official_signature()
        path = settings.get("image_path") or ""
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.signature_preview.setPixmap(
                    pixmap.scaled(360, 130, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return
        self.signature_preview.setPixmap(QPixmap())
        self.signature_preview.setText("تصویر امضا بارگذاری نشده است.")

    def _upload_official_signature(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب تصویر امضا", os.path.expanduser("~"),
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if not file_path:
            return
        signatures_dir = os.path.join(os.path.dirname(self.db.db_path), "official_signatures")
        os.makedirs(signatures_dir, exist_ok=True)
        ext = os.path.splitext(file_path)[1].lower() or ".png"
        destination = os.path.join(signatures_dir, f"official_signature{ext}")
        try:
            shutil.copyfile(file_path, destination)
            self.db.set_official_signature(
                destination, self.signer_name_input.text().strip(),
                self.signer_title_input.text().strip(), self.verification_url_input.text().strip()
            )
        except Exception as exc:
            QMessageBox.critical(self, "خطا", f"ذخیره تصویر امضا انجام نشد:\n{exc}")
            return
        self._update_signature_preview()
        QMessageBox.information(self, "ثبت شد", "تصویر امضا با موفقیت ذخیره شد.")

    def _save_official_signature_settings(self):
        current = self.db.get_official_signature()
        self.db.set_official_signature(
            current.get("image_path") or "", self.signer_name_input.text().strip(),
            self.signer_title_input.text().strip(), self.verification_url_input.text().strip()
        )
        QMessageBox.information(self, "ذخیره شد", "مشخصات امضاکننده و اعتبارسنجی QR ذخیره شد.")

    def _clear_official_signature(self):
        current = self.db.get_official_signature()
        path = current.get("image_path") or ""
        self.db.set_official_signature(
            "", self.signer_name_input.text().strip(), self.signer_title_input.text().strip(),
            self.verification_url_input.text().strip()
        )
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        self._update_signature_preview()
        QMessageBox.information(self, "حذف شد", "تصویر امضا حذف شد؛ نام و سمت امضاکننده حفظ شدند.")

    # ==================== تب ۵: سابقه فعالیت ====================
    def _build_audit_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "تاریخچه حسابرسی شامل کاربر انجام‌دهنده، بلوک مرتبط، عملیات و جزئیات تغییر است. "
            "این اطلاعات برای پیگیری اداری و تشخیص تغییرات ناخواسته نگهداری می‌شود."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        filters = QHBoxLayout()
        self.audit_user_filter = QLineEdit()
        self.audit_user_filter.setPlaceholderText("فیلتر نام کاربری")
        self.audit_user_filter.returnPressed.connect(self._refresh_audit_table)
        filters.addWidget(self.audit_user_filter)

        self.audit_zone_filter = QComboBox()
        self.audit_zone_filter.addItem("همه بلوک‌ها", None)
        for zone in self.db.get_zones():
            self.audit_zone_filter.addItem(zone.get("name") or str(zone.get("id")), zone.get("id"))
        filters.addWidget(self.audit_zone_filter)

        self.audit_action_filter = QComboBox()
        self.audit_action_filter.addItem("همه عملیات", None)
        for key, title in [
            ("create", "ایجاد بلوک"), ("update", "ویرایش بلوک"), ("delete", "حذف بلوک"),
            ("user_created", "ایجاد کاربر"), ("user_updated", "ویرایش کاربر"),
            ("password_changed", "تغییر رمز"), ("login_success", "ورود موفق"),
            ("login_failed", "ورود ناموفق"), ("logout", "خروج"),
            ("backup_created", "ایجاد بکاپ"),
        ]:
            self.audit_action_filter.addItem(title, key)
        filters.addWidget(self.audit_action_filter)

        refresh_btn = QPushButton("بروزرسانی سابقه")
        refresh_btn.clicked.connect(self._refresh_audit_table)
        filters.addWidget(refresh_btn)
        layout.addLayout(filters)

        self.audit_table = QTableWidget()
        self.audit_table.setColumnCount(8)
        self.audit_table.setHorizontalHeaderLabels(
            ["زمان", "کاربر", "عملیات", "نوع", "شناسه", "بلوک", "جزئیات", "قبل / بعد"]
        )
        self.audit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.audit_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.audit_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.audit_table)
        self._refresh_audit_table()
        return tab

    def _refresh_audit_table(self):
        if not hasattr(self, "audit_table"):
            return
        username = self.audit_user_filter.text().strip() if hasattr(self, "audit_user_filter") else None
        zone_id = self.audit_zone_filter.currentData() if hasattr(self, "audit_zone_filter") else None
        action = self.audit_action_filter.currentData() if hasattr(self, "audit_action_filter") else None
        logs = self.db.get_audit_logs(limit=500, username=username or None, zone_id=zone_id, action=action)
        labels = {
            "create": "ایجاد", "update": "ویرایش", "delete": "حذف",
            "replace_osm_data": "بروزرسانی OSM بلوک",
            "replace_city_osm_data": "بروزرسانی OSM شهر",
            "credentials_changed": "تغییر حساب",
            "backup_created": "ایجاد بکاپ",
            "meeting_place_changed": "تغییر محل جلسه",
            "user_created": "ایجاد کاربر", "user_updated": "ویرایش کاربر",
            "password_changed": "تغییر رمز", "login_success": "ورود موفق",
            "login_failed": "ورود ناموفق", "logout": "خروج از حساب",
        }
        zone_names = {z.get("id"): z.get("name") for z in self.db.get_zones()}
        self.audit_table.setRowCount(len(logs))
        for row, item in enumerate(logs):
            before_after = ""
            if item.get("before_json") or item.get("after_json"):
                before_after = f"قبل: {item.get('before_json') or '—'} | بعد: {item.get('after_json') or '—'}"
            values = [
                item.get("created_at") or "",
                item.get("actor_username") or "system",
                labels.get(item.get("action"), item.get("action") or ""),
                item.get("entity_type") or "",
                item.get("entity_id") or "",
                zone_names.get(item.get("zone_id"), item.get("zone_id") or "—"),
                item.get("details") or "",
                before_after,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(convert_dates_in_text(str(value)))
                cell.setToolTip(str(value))
                self.audit_table.setItem(row, col, cell)

# نگهداری نام قدیمی برای سازگاری با کدهایی که ممکن است SettingsWindow را import کرده باشند
SettingsWindow = SystemSettingsWindow
