# -*- coding: utf-8 -*-
"""
پنجره ورود (Login) برنامه.
احراز هویت بر اساس جدول admin_settings در دیتابیس انجام می‌شود.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QLineEdit, QPushButton, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal

from theme import LOGIN_STYLESHEET
from header_widget import SoftwareHeader


class LoginWindow(QWidget):
    """پنجره ورود. با ورود موفق، سیگنال login_successful ارسال می‌شود."""
    login_successful = pyqtSignal(object)

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("ورود به سامانه — فرمانداری شهرستان جوانرود")
        self.setObjectName("LoginRoot")
        self.resize(1100, 700)
        self.setStyleSheet(LOGIN_STYLESHEET)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # همان هدر رسمی تمام صفحات؛ در حالت ورود بدون ابزارهای حساب کاربری
        self.header = SoftwareHeader(
            current_user={},
            unread_count=0,
            subtitle="نسخه ادمین | داشبورد مدیریتی",
            show_tools=False,
            login_mode=True,
        )
        outer.addWidget(self.header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 24, 24, 24)
        body_layout.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("LoginCard")
        card.setFixedWidth(458)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 32, 36, 32)
        card_layout.setSpacing(10)

        # کارت ورود؛ اطلاعات سازمانی در هدر مشترک نمایش داده می‌شود
        title = QLabel("ورود به سامانه")
        title.setObjectName("LoginTitle")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("برای ورود، نام کاربری و رمز عبور خود را وارد کنید")
        subtitle.setObjectName("LoginSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)
        credentials_path = ""
        try:
            credentials_path = self.db.get_initial_credentials_path()
        except Exception:
            credentials_path = ""
        if credentials_path:
            notice = QLabel("رمز اولیه امن در فایل زیر ثبت شده است:\n" + credentials_path)
            notice = QLabel("رمز اولیه امن در فایل زیر ثبت شده است:\n" + credentials_path)
            notice.setWordWrap(True)
            notice.setTextInteractionFlags(Qt.TextSelectableByMouse)
            notice.setStyleSheet("padding:10px;background:#0a2141;border:1px solid #d1a84c;border-radius:10px;color:#e8edf8")
            card_layout.addWidget(notice)
        card_layout.addSpacing(14)

        self.username_input = QLineEdit()
        self.username_input.setObjectName("LoginInput")
        self.username_input.setPlaceholderText("نام کاربری")
        card_layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setObjectName("LoginInput")
        self.password_input.setPlaceholderText("رمز عبور")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.on_login_clicked)
        card_layout.addWidget(self.password_input)

        self.error_label = QLabel("")
        self.error_label.setObjectName("LoginError")
        self.error_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.error_label)

        login_btn = QPushButton("ورود")
        login_btn.setObjectName("LoginButton")
        login_btn.clicked.connect(self.on_login_clicked)
        card_layout.addWidget(login_btn)

        body_layout.addWidget(card, alignment=Qt.AlignCenter)
        outer.addWidget(body, 1)

    def on_login_clicked(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.error_label.setText("لطفاً نام کاربری و رمز عبور را وارد کنید.")
            return

        user = self.db.authenticate_user(username, password)
        if user:
            self.error_label.setText("")
            if user.get("must_change_password"):
                QMessageBox.warning(
                    self, "تغییر رمز عبور ضروری است",
                    "رمز عبور این حساب موقت است. پس از ورود، از بخش تنظیمات حساب یک رمز اختصاصی و قوی تعیین کنید."
                )
            self.login_successful.emit(user)
        else:
            self.error_label.setText("نام کاربری یا رمز عبور اشتباه است، حساب غیرفعال است یا موقتاً قفل شده است.")
            self.password_input.clear()
            self.password_input.setFocus()
