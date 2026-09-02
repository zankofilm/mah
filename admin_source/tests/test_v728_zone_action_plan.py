# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.8: تولید «برنامه عملیاتی بلوک» بر اساس مشکلات،
درخواست‌های مردمی و اقدامات جاری ثبت‌شده برای یک بلوک (zone_action_plan.py
+ Database.get_zone_action_plan_context/save_zone_action_plan).

مثل smart_triage، دو موتور دارد: قانون‌محور آفلاین (همیشه فعال) و اتصال
اختیاری به سرویس هوش مصنوعی با بازگشت بی‌صدا در هر نوع خطا.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
import zone_action_plan


class ZoneActionPlanContextTests(unittest.TestCase):
    """تست تابع جمع‌آوری داده در database.py که ورودی موتور تولید برنامه است."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_context_includes_only_open_issues_and_requests(self):
        open_issue = self.db.add_neighborhood_issue(self.zone_id, "مسئله باز", "زیرساخت", urgency=4, severity=4)
        closed_issue = self.db.add_neighborhood_issue(self.zone_id, "مسئله بسته", "زیرساخت", urgency=2, severity=2)
        self.db.update_neighborhood_issue(closed_issue, status="مختومه")

        context = self.db.get_zone_action_plan_context(self.zone_id)
        issue_ids = [i["id"] for i in context["open_issues"]]
        self.assertIn(open_issue, issue_ids)
        self.assertNotIn(closed_issue, issue_ids)

    def test_context_includes_active_actions_for_deduplication(self):
        self.db.add_neighborhood_action(self.zone_id, "اقدام در جریان", status="در حال اجرا")
        self.db.add_neighborhood_action(self.zone_id, "اقدام تکمیل‌شده", status="تکمیل‌شده")

        context = self.db.get_zone_action_plan_context(self.zone_id)
        titles = [a["title"] for a in context["active_actions"]]
        self.assertIn("اقدام در جریان", titles)
        self.assertNotIn("اقدام تکمیل‌شده", titles)

    def test_context_includes_only_active_agencies(self):
        self.db.add_management_agency("دستگاه فعال", is_active=1)
        self.db.add_management_agency("دستگاه غیرفعال", is_active=0)

        context = self.db.get_zone_action_plan_context(self.zone_id)
        names = [a["name"] for a in context["agencies"]]
        self.assertIn("دستگاه فعال", names)
        self.assertNotIn("دستگاه غیرفعال", names)

    def test_context_for_nonexistent_zone_returns_none(self):
        context = self.db.get_zone_action_plan_context(999999)
        self.assertIsNone(context)


class OfflinePlanGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "بلوک نمونه", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_plan_mentions_zone_name(self):
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, engine = zone_action_plan.generate(context)
        self.assertIn("بلوک نمونه", plan_text)
        self.assertEqual(engine, "keyword")

    def test_critical_issue_appears_in_urgent_section(self):
        self.db.add_neighborhood_issue(
            self.zone_id, "آب‌گرفتگی شدید", "آب و فاضلاب",
            urgency=5, severity=5, affected_households=50, safety_risk=5,
        )
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, _ = zone_action_plan.generate(context)
        self.assertIn("اولویت فوری", plan_text)
        self.assertIn("آب‌گرفتگی شدید", plan_text)

    def test_matching_agency_is_suggested_for_critical_issue_category(self):
        self.db.add_neighborhood_issue(
            self.zone_id, "لوله ترکیده", "آب و فاضلاب",
            urgency=5, severity=5, affected_households=50, safety_risk=5,
        )
        self.db.add_management_agency(
            "شرکت آبفا", service_scope="آب و فاضلاب، لوله‌کشی"
        )
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, _ = zone_action_plan.generate(context)
        self.assertIn("شرکت آبفا", plan_text)

    def test_matching_agency_is_suggested_for_important_issue_category(self):
        """پیشنهاد دستگاه فقط منحصر به سطح فوری/بحرانی نیست؛ برای مسائل با
        اولویت «مهم» هم در صورت تطابق حوزه خدمت نمایش داده می‌شود."""
        self.db.add_neighborhood_issue(
            self.zone_id, "لوله ترکیده", "آب و فاضلاب", urgency=5, severity=5,
        )
        self.db.add_management_agency(
            "شرکت آبفا", service_scope="آب و فاضلاب، لوله‌کشی"
        )
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, _ = zone_action_plan.generate(context)
        self.assertIn("اولویت مهم", plan_text)
        self.assertIn("شرکت آبفا", plan_text)

    def test_no_agency_match_shows_honest_placeholder_not_a_guess(self):
        """اگر هیچ دستگاهی حوزه خدمت متناظر ندارد، موتور نباید دستگاه تصادفی
        حدس بزند؛ باید صادقانه بگوید نیاز به تعیین دارد."""
        self.db.add_neighborhood_issue(
            self.zone_id, "مسئله بدون دستگاه مرتبط", "فرهنگی",
            urgency=5, severity=5, affected_households=50, safety_risk=5,
        )
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, _ = zone_action_plan.generate(context)
        self.assertIn("تعیین نشده", plan_text)

    def test_active_actions_listed_to_prevent_duplicate_work(self):
        self.db.add_neighborhood_action(
            self.zone_id, "تعمیر لوله اصلی", responsible_office="آبفا", status="در حال اجرا"
        )
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, _ = zone_action_plan.generate(context)
        self.assertIn("تعمیر لوله اصلی", plan_text)
        self.assertIn("دوباره‌کاری", plan_text)

    def test_empty_zone_produces_valid_plan_without_error(self):
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, engine = zone_action_plan.generate(context)
        self.assertIsInstance(plan_text, str)
        self.assertGreater(len(plan_text), 0)
        self.assertEqual(engine, "keyword")


class ApiPlanGeneratorFallbackTests(unittest.TestCase):
    """موتور API هرگز نباید کاربر را متوقف کند؛ در هر خطا باید بی‌صدا
    None برگرداند تا generate() به موتور آفلاین برگردد."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "بلوک نمونه", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_missing_credentials_returns_none(self):
        context = self.db.get_zone_action_plan_context(self.zone_id)
        result = zone_action_plan.generate_via_api(context, "", "")
        self.assertIsNone(result)

    def test_unreachable_network_falls_back_to_offline(self):
        context = self.db.get_zone_action_plan_context(self.zone_id)
        plan_text, engine = zone_action_plan.generate(
            context,
            api_url="https://invalid-nonexistent-domain-xyz123.test/v1/chat",
            api_key="fake-key",
        )
        self.assertEqual(engine, "keyword")
        self.assertIn("بلوک نمونه", plan_text)

    def test_successful_api_response_is_used_as_is(self):
        context = self.db.get_zone_action_plan_context(self.zone_id)
        with patch("zone_action_plan.generate_via_api", return_value="متن تولیدشده توسط هوش مصنوعی"):
            plan_text, engine = zone_action_plan.generate(
                context, api_url="https://api.example.com/v1/chat", api_key="real-key"
            )
        self.assertEqual(engine, "api")
        self.assertEqual(plan_text, "متن تولیدشده توسط هوش مصنوعی")

    def test_empty_api_response_falls_back_to_offline(self):
        context = self.db.get_zone_action_plan_context(self.zone_id)
        with patch("zone_action_plan.generate_via_api", return_value=""):
            plan_text, engine = zone_action_plan.generate(
                context, api_url="https://api.example.com/v1/chat", api_key="real-key"
            )
        self.assertEqual(engine, "keyword")


class ZoneActionPlanPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_save_and_retrieve_latest_plan(self):
        self.db.save_zone_action_plan(self.zone_id, "keyword", "برنامه اول")
        self.db.save_zone_action_plan(self.zone_id, "keyword", "برنامه دوم (به‌روزتر)")

        latest = self.db.get_latest_zone_action_plan(self.zone_id)
        self.assertEqual(latest["content"], "برنامه دوم (به‌روزتر)")

        all_plans = self.db.get_zone_action_plans(self.zone_id)
        self.assertEqual(len(all_plans), 2)

    def test_no_plan_returns_none(self):
        self.assertIsNone(self.db.get_latest_zone_action_plan(self.zone_id))

    def test_deleting_zone_cascades_plans(self):
        self.db.save_zone_action_plan(self.zone_id, "keyword", "برنامه تست")
        self.db.delete_zone(self.zone_id)
        self.assertEqual(self.db.get_zone_action_plans(self.zone_id), [])


if __name__ == "__main__":
    unittest.main()
