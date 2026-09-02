# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.8: پیشنهاد هوشمند دسته‌بندی و فوریت درخواست‌های مردمی
(smart_triage.py) — موتور کلیدواژه‌ای آفلاین به‌عنوان پیش‌فرض همیشه‌فعال،
و امکان اتصال اختیاری به یک سرویس هوش مصنوعی خارجی با بازگشت بی‌صدا
(silent fallback) به حالت آفلاین در هر نوع خطا یا نبود اتصال.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
import smart_triage


class OfflineKeywordEngineTests(unittest.TestCase):
    def test_lighting_complaint_is_categorized_correctly(self):
        result = smart_triage.suggest_offline("چراغ‌های خیابان چند شب است روشن نمی‌شود")
        self.assertEqual(result["category"], "روشنایی")
        self.assertEqual(result["engine"], "keyword")

    def test_critical_safety_phrase_forces_max_urgency(self):
        result = smart_triage.suggest_offline("لوله آب ترکیده و خطر برق‌گرفتگی وجود دارد")
        self.assertEqual(result["urgency"], 5)

    def test_low_urgency_phrase_lowers_score(self):
        result = smart_triage.suggest_offline("درخت پارک نیاز به هرس دارد، عجله‌ای نیست")
        self.assertEqual(result["urgency"], 2)

    def test_unrelated_text_falls_back_to_other_category(self):
        result = smart_triage.suggest_offline("سلام وقت بخیر")
        self.assertEqual(result["category"], "سایر")
        self.assertLess(result["confidence"], 0.3)

    def test_empty_text_returns_safe_default_without_error(self):
        result = smart_triage.suggest_offline("")
        self.assertEqual(result["category"], "سایر")
        self.assertEqual(result["urgency"], 3)

    def test_suggested_category_is_always_a_valid_official_category(self):
        samples = [
            "زباله‌ها جمع نمی‌شود", "آب‌گرفتگی کوچه", "درگیری در محل",
            "بیکاری جوانان منطقه", "کمبود معلم در مدرسه", "چیز عجیب و نامرتبط xyz",
        ]
        for text in samples:
            result = smart_triage.suggest_offline(text)
            self.assertIn(result["category"], Database.ISSUE_CATEGORIES)


class ApiEngineFallbackTests(unittest.TestCase):
    """موتور API هرگز نباید کاربر را با خطای شبکه/کلید نامعتبر متوقف کند؛
    در هر شرایط غیرعادی باید بی‌صدا None برگرداند تا suggest() به آفلاین برگردد."""

    def test_missing_api_key_returns_none_immediately(self):
        result = smart_triage.suggest_via_api(
            "متن تست", "https://example.com/v1/chat", "", Database.ISSUE_CATEGORIES
        )
        self.assertIsNone(result)

    def test_missing_api_url_returns_none_immediately(self):
        result = smart_triage.suggest_via_api(
            "متن تست", "", "fake-key", Database.ISSUE_CATEGORIES
        )
        self.assertIsNone(result)

    def test_unreachable_network_falls_back_to_none(self):
        # دامنه نامعتبر عمداً برای شبیه‌سازی نبود اتصال اینترنت
        result = smart_triage.suggest_via_api(
            "چراغ خیابان خراب است",
            "https://invalid-nonexistent-domain-xyz123.test/v1/chat",
            "fake-key", Database.ISSUE_CATEGORIES, timeout=2,
        )
        self.assertIsNone(result)

    def test_suggest_falls_back_to_offline_when_api_configured_but_unreachable(self):
        result = smart_triage.suggest(
            "چراغ خیابان خراب است", Database.ISSUE_CATEGORIES,
            api_url="https://invalid-nonexistent-domain-xyz123.test/v1/chat",
            api_key="fake-key",
        )
        self.assertEqual(result["engine"], "keyword")
        self.assertEqual(result["category"], "روشنایی")

    def test_suggest_without_any_api_config_uses_offline_directly(self):
        result = smart_triage.suggest("چراغ خیابان خراب است", Database.ISSUE_CATEGORIES)
        self.assertEqual(result["engine"], "keyword")

    def test_suggest_uses_api_result_when_available(self):
        fake_result = {
            "category": "روشنایی", "urgency": 4, "confidence": 0.9,
            "matched_keywords": [], "engine": "api",
        }
        with patch("smart_triage.suggest_via_api", return_value=fake_result):
            result = smart_triage.suggest(
                "چراغ خیابان خراب است", Database.ISSUE_CATEGORIES,
                api_url="https://api.example.com/v1/chat", api_key="real-key",
            )
        self.assertEqual(result["engine"], "api")
        self.assertEqual(result["urgency"], 4)

    def test_api_response_with_invalid_category_is_normalized_to_other(self):
        """اگر سرویس خارجی دسته‌بندی نامعتبری برگرداند، به «سایر» اصلاح می‌شود
        تا هرگز دسته‌بندی خارج از فهرست رسمی پروژه در دیتابیس ثبت نشود."""
        fake_response_content = '{"category": "یک دسته ساختگی نامعتبر", "urgency": 3}'

        class FakeResponse:
            status_code = 200
            def json(self):
                return {"choices": [{"message": {"content": fake_response_content}}]}

        with patch("smart_triage.requests.post", return_value=FakeResponse()):
            result = smart_triage.suggest_via_api(
                "متن تست", "https://api.example.com/v1/chat", "real-key",
                Database.ISSUE_CATEGORIES,
            )
        self.assertEqual(result["category"], "سایر")


class SmartTriageSettingsPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_default_settings_are_disabled_and_empty(self):
        settings = self.db.get_smart_triage_settings()
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["api_url"], "")
        self.assertEqual(settings["api_key"], "")

    def test_save_and_reload_settings(self):
        self.db.set_smart_triage_settings(True, "https://api.example.com/v1/chat", "sk-abc123")
        settings = self.db.get_smart_triage_settings()
        self.assertTrue(settings["enabled"])
        self.assertEqual(settings["api_url"], "https://api.example.com/v1/chat")
        self.assertEqual(settings["api_key"], "sk-abc123")

    def test_disabling_clears_stored_credentials(self):
        self.db.set_smart_triage_settings(True, "https://api.example.com/v1/chat", "sk-abc123")
        self.db.set_smart_triage_settings(False)
        settings = self.db.get_smart_triage_settings()
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["api_url"], "")
        self.assertEqual(settings["api_key"], "")


if __name__ == "__main__":
    unittest.main()
