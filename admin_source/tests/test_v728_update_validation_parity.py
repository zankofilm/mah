# -*- coding: utf-8 -*-
"""
رگرسیون‌تست v7.2.8 (بخش دوم):
با مقایسه سیستماتیک تمام متدهای add_*/create_* دارای قانون اعتبارسنجی
با متد update_* متناظرشان، ۵ حفره مشابه پیدا شد — هرکدام موردی که در
مسیر «افزودن» رد می‌شد اما در مسیر «ویرایش» به دیتابیس راه می‌یافت:
  1) update_project_milestone   - عنوان خالی
  2) update_project_indicator   - عنوان خالی
  3) update_project_risk        - عنوان خالی
  4) update_execution_case      - عنوان خالی
  5) update_contract_payment    - پایان دوره قبل از شروع دوره
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


class UpdateValidationParityTests(unittest.TestCase):
    """هر متد update_* باید همان قوانین اعتبارسنجی متد add_*/create_* هم‌نامش را رعایت کند."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "منطقه تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )
        self.project_id = self.db.add_project("پروژه آزمایشی", zone_id=self.zone_id)

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_milestone_update_rejects_empty_title(self):
        milestone_id = self.db.add_project_milestone(self.project_id, "نقطه اول")
        with self.assertRaises(ValueError):
            self.db.update_project_milestone(milestone_id, title="   ")
        # ولی یک عنوان معتبر باید بدون خطا پذیرفته شود
        self.db.update_project_milestone(milestone_id, title="نقطه اصلاح‌شده")
        row = self.db.get_project_milestone(milestone_id)
        self.assertEqual(row["title"], "نقطه اصلاح‌شده")

    def test_indicator_update_rejects_empty_title(self):
        indicator_id = self.db.add_project_indicator("شاخص اول", project_id=self.project_id)
        with self.assertRaises(ValueError):
            self.db.update_project_indicator(indicator_id, title="")
        self.db.update_project_indicator(indicator_id, title="شاخص اصلاح‌شده")
        row = self.db.get_project_indicator(indicator_id)
        self.assertEqual(row["title"], "شاخص اصلاح‌شده")

    def test_risk_update_rejects_empty_title(self):
        risk_id = self.db.add_project_risk("ریسک اول", project_id=self.project_id)
        with self.assertRaises(ValueError):
            self.db.update_project_risk(risk_id, title="   ")
        self.db.update_project_risk(risk_id, title="ریسک اصلاح‌شده")
        row = self.db.get_project_risk(risk_id)
        self.assertEqual(row["title"], "ریسک اصلاح‌شده")

    def test_execution_case_update_rejects_empty_title(self):
        case_id = self.db.add_execution_case("پرونده اول", zone_id=self.zone_id)
        with self.assertRaises(ValueError):
            self.db.update_execution_case(case_id, title="")
        self.db.update_execution_case(case_id, title="پرونده اصلاح‌شده")
        row = self.db.get_execution_case(case_id)
        self.assertEqual(row["title"], "پرونده اصلاح‌شده")

    def test_contract_payment_update_rejects_period_end_before_start(self):
        contractor_id = self.db.add_contractor("پیمانکار تست")
        contract_id = self.db.add_contract(
            "C-1", "قرارداد تست", contractor_id, project_id=self.project_id
        )
        payment_id = self.db.add_contract_payment(
            contract_id, period_from="1405-01-01", period_to="1405-02-01"
        )
        with self.assertRaises(ValueError):
            self.db.update_contract_payment(
                payment_id, period_from="1405-05-01", period_to="1405-01-01"
            )
        # ولی یک بازه معتبر باید بدون خطا پذیرفته شود
        self.db.update_contract_payment(
            payment_id, period_from="1405-01-01", period_to="1405-03-01"
        )
        row = self.db.get_contract_payment(payment_id)
        self.assertEqual(row["period_to"], "1405-03-01")


if __name__ == "__main__":
    unittest.main()
