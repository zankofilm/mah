# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.8: خلاصه برنامه عملیاتی هوشمند اکنون به‌طور خودکار در
گزارش PDF کامل بلوک (generate_block_full_report_pdf) درج می‌شود — نه فقط
در دیالوگ جداگانه‌ای که کاربر باید جدا باز کند.

قواعد:
- اگر برنامه‌ای از قبل برای بلوک ذخیره شده باشد (کاربر دستی تولید کرده)،
  همان در گزارش استفاده می‌شود.
- اگر برنامه‌ای ذخیره نشده باشد، یک نسخه آفلاین سریع (بدون فراخوان شبکه)
  فقط برای نمایش در گزارش ساخته می‌شود؛ این نسخه موقت به‌عنوان یک رکورد
  رسمی در zone_action_plans ذخیره نمی‌شود.
- ساخت گزارش هرگز نباید به این بخش وابسته به‌طور کامل شکست بخورد؛ در صورت
  خطای غیرمنتظره باید پیام جای‌گزین نشان دهد و باقی گزارش ادامه یابد.

بررسی محتوای واقعی متن داخل PDF به علت reshaping حروف فارسی در ابزارهای
استخراج متن قابل‌اعتماد نیست؛ به همین دلیل این تست‌ها مستقیماً از منطق
درج (نه از parse کردن فایل PDF باینری) تأیید می‌گیرند.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
import report_generator
import zone_action_plan


class ReportActionPlanIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "بلوک تست گزارش", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )
        self.output_path = os.path.join(self.tmp.name, "report.pdf")

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_report_uses_previously_saved_plan_without_regenerating(self):
        """اگر کاربر قبلاً برنامه تولید کرده، گزارش باید همان متن ذخیره‌شده
        را نمایش دهد، نه یک نسخه تازه بسازد."""
        self.db.save_zone_action_plan(self.zone_id, "keyword", "متن برنامه ذخیره‌شده قبلی")

        with patch("zone_action_plan.generate_offline") as mock_generate:
            report_generator.generate_block_full_report_pdf(self.db, self.zone_id, self.output_path)
            mock_generate.assert_not_called()

        self.assertTrue(os.path.exists(self.output_path))
        self.assertGreater(os.path.getsize(self.output_path), 0)

    def test_report_generates_offline_plan_when_none_saved(self):
        """اگر هیچ برنامه‌ای ذخیره نشده باشد، گزارش باید بلادرنگ و آفلاین
        (بدون فراخوان API) یک نسخه بسازد."""
        self.db.add_neighborhood_issue(
            self.zone_id, "آب‌گرفتگی شدید", "آب و فاضلاب",
            urgency=5, severity=5, affected_households=50, safety_risk=5,
        )

        with patch("zone_action_plan.generate_via_api") as mock_api:
            report_generator.generate_block_full_report_pdf(self.db, self.zone_id, self.output_path)
            mock_api.assert_not_called()

        self.assertTrue(os.path.exists(self.output_path))

    def test_ephemeral_offline_plan_is_not_persisted_as_official_record(self):
        """برنامه‌ای که فقط برای نمایش در گزارش موقتاً ساخته می‌شود، نباید
        به‌عنوان یک رکورد رسمی «تولیدشده توسط کاربر» در تاریخچه ثبت شود."""
        report_generator.generate_block_full_report_pdf(self.db, self.zone_id, self.output_path)
        self.assertEqual(self.db.get_zone_action_plans(self.zone_id), [])

    def test_report_generation_survives_action_plan_failure(self):
        """اگر بخش برنامه عملیاتی به هر دلیلی خطا بدهد، کل گزارش نباید
        متوقف شود — باید پیام جای‌گزین نشان دهد و ادامه یابد."""
        with patch("zone_action_plan.generate_offline", side_effect=RuntimeError("خطای فرضی")):
            # نباید استثنا به بیرون درز کند
            report_generator.generate_block_full_report_pdf(self.db, self.zone_id, self.output_path)
        self.assertTrue(os.path.exists(self.output_path))
        self.assertGreater(os.path.getsize(self.output_path), 0)

    def test_report_with_no_issues_still_generates_successfully(self):
        """بلوک بدون هیچ مسئله یا درخواستی هم باید گزارش کامل و بدون خطا بسازد."""
        report_generator.generate_block_full_report_pdf(self.db, self.zone_id, self.output_path)
        self.assertTrue(os.path.exists(self.output_path))


if __name__ == "__main__":
    unittest.main()
