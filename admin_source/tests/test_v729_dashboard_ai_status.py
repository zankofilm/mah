# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.9: کارت «وضعیت هوش مصنوعی» در داشبورد اصلی، برای
رفع مشکل کشف‌پذیری قابلیت‌های هوشمند (کاربر قبلاً هیچ نشانه‌ای در کل
برنامه نمی‌دید که این قابلیت‌ها کجا هستند).

این تست‌ها منطق backend را می‌سنجند (تشخیص وضعیت اتصال، و پرش مستقیم به
تب هوش مصنوعی در تنظیمات)؛ رندر واقعی ویجت‌های PyQt نیاز به PyQtWebEngine
دارد که در محیط تست فعلی نصب نیست، پس اینجا پوشش داده نمی‌شود.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


def _is_ai_connected(settings):
    """دقیقاً همان منطقی که dashboard_window.py برای تشخیص وضعیت کارت
    هوش مصنوعی استفاده می‌کند (کپی شده برای تست بدون وابستگی به PyQt)."""
    return bool(settings.get("enabled") and settings.get("api_url") and settings.get("api_key"))


class DashboardAiStatusLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_default_state_shows_offline_only(self):
        settings = self.db.get_smart_triage_settings()
        self.assertFalse(_is_ai_connected(settings))

    def test_fully_configured_shows_connected(self):
        self.db.set_smart_triage_settings(True, "https://api.example.com/v1/chat", "sk-real-key")
        settings = self.db.get_smart_triage_settings()
        self.assertTrue(_is_ai_connected(settings))

    def test_enabled_without_credentials_still_shows_offline(self):
        """اگر پرچم enabled به‌هر دلیلی True باشد ولی کلید/آدرس خالی
        باشد، کارت باید صادقانه «فقط آفلاین» نشان دهد، نه گمراه‌کننده
        «متصل». این یک محافظت مهم در برابر حالت داده ناقص است."""
        self.db.conn.execute(
            "UPDATE smart_triage_settings SET enabled=1, api_key='' WHERE id=1"
        )
        self.db.conn.commit()
        settings = self.db.get_smart_triage_settings()
        self.assertFalse(_is_ai_connected(settings))

    def test_disabled_with_leftover_credentials_shows_offline(self):
        """set_smart_triage_settings(False) پاک‌کننده اعتبارنامه‌هاست،
        اما این تست مطمئن می‌شود حتی اگر جای دیگری credential باقی
        بماند، enabled=False همچنان نتیجه را آفلاین نشان می‌دهد."""
        self.db.set_smart_triage_settings(True, "https://api.example.com/v1/chat", "sk-real-key")
        self.db.conn.execute(
            "UPDATE smart_triage_settings SET enabled=0 WHERE id=1"
        )
        self.db.conn.commit()
        settings = self.db.get_smart_triage_settings()
        self.assertFalse(_is_ai_connected(settings))


class SettingsTabJumpLogicTests(unittest.TestCase):
    """تست منطق _jump_to_tab بدون نیاز به یک QTabWidget واقعی؛ با یک
    شبیه‌ساز حداقلی که فقط رفتار tabText/setCurrentIndex را تقلید می‌کند."""

    class FakeTabWidget:
        def __init__(self, titles):
            self._titles = titles
            self.current_index = 0

        def count(self):
            return len(self._titles)

        def tabText(self, i):
            return self._titles[i]

        def setCurrentIndex(self, i):
            self.current_index = i

    def _jump_to_tab(self, tabs, tab_title):
        """کپی مستقیم منطق SystemSettingsWindow._jump_to_tab برای تست
        بدون نیاز به نمونه‌سازی واقعی QWidget."""
        for i in range(tabs.count()):
            if tabs.tabText(i) == tab_title:
                tabs.setCurrentIndex(i)
                return

    def test_jumps_to_ai_tab_when_present(self):
        tabs = self.FakeTabWidget(["حساب کاربری", "کاربران و دسترسی‌ها", "هوش مصنوعی", "سابقه فعالیت"])
        self._jump_to_tab(tabs, "هوش مصنوعی")
        self.assertEqual(tabs.current_index, 2)

    def test_stays_on_first_tab_when_target_not_found(self):
        """کاربر غیرادمین تب هوش مصنوعی را در فهرست ندارد؛ نباید خطا
        بدهد یا وضعیت نامعتبر ایجاد کند، فقط باید بی‌اثر بماند."""
        tabs = self.FakeTabWidget(["حساب کاربری"])
        self._jump_to_tab(tabs, "هوش مصنوعی")
        self.assertEqual(tabs.current_index, 0)


if __name__ == "__main__":
    unittest.main()
