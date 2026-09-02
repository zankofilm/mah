# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.10: مقایسه و رتبه‌بندی همه بلوک‌های شهر بر اساس
امتیاز ریسک شفاف (Database.get_all_zones_comparison)، برای این‌که مدیر
ارشد بدون باز کردن جداگانه هر بلوک، بدترین بلوک‌ها را سریع پیدا کند.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


class ZoneComparisonRankingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_empty_project_returns_empty_list_without_error(self):
        result = self.db.get_all_zones_comparison()
        self.assertEqual(result, [])

    def test_zone_with_no_issues_has_zero_risk_score(self):
        self.db.create_zone("بلوک آرام", [(0, 0), (0, 1), (1, 1), (1, 0)])
        result = self.db.get_all_zones_comparison()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["risk_score"], 0)

    def test_zone_with_critical_issues_ranks_above_calmer_zone(self):
        calm_zone = self.db.create_zone("بلوک آرام", [(0, 0), (0, 1), (1, 1), (1, 0)])
        critical_zone = self.db.create_zone("بلوک بحرانی", [(2, 2), (2, 3), (3, 3), (3, 2)])

        self.db.add_neighborhood_issue(
            critical_zone, "آب‌گرفتگی شدید", "آب و فاضلاب",
            urgency=5, severity=5, affected_households=50, safety_risk=5,
        )

        result = self.db.get_all_zones_comparison()
        # مرتب‌سازی باید بدترین را اول بگذارد
        self.assertEqual(result[0]["zone_id"], critical_zone)
        self.assertEqual(result[-1]["zone_id"], calm_zone)
        self.assertGreater(result[0]["risk_score"], result[-1]["risk_score"])

    def test_critical_issue_contributes_to_both_critical_and_open_weight(self):
        """این تست همان انتخاب طراحی عمدی را قفل می‌کند: یک مسئله بحرانی هم
        در وزن issues_critical و هم در وزن issues_open حساب می‌شود، چون
        هم «باز» است هم «بحرانی» — نه یک باگ حساب مضاعف."""
        zone_id = self.db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])
        self.db.add_neighborhood_issue(
            zone_id, "مسئله بحرانی", "زیرساخت",
            urgency=5, severity=5, affected_households=10, safety_risk=5,
        )
        result = self.db.get_all_zones_comparison()
        expected_score = (
            1 * Database.ZONE_RISK_WEIGHTS["issues_critical"]
            + 1 * Database.ZONE_RISK_WEIGHTS["issues_open"]
        )
        self.assertEqual(result[0]["risk_score"], expected_score)

    def test_closed_issues_do_not_affect_risk_score(self):
        zone_id = self.db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])
        issue_id = self.db.add_neighborhood_issue(
            zone_id, "مسئله حل‌شده", "زیرساخت", urgency=5, severity=5,
        )
        self.db.update_neighborhood_issue(issue_id, status="مختومه")

        result = self.db.get_all_zones_comparison()
        self.assertEqual(result[0]["risk_score"], 0)

    def test_open_citizen_requests_increase_risk_score(self):
        zone_id = self.db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])
        self.db.add_citizen_request(zone_id, "درخواست باز", category="پسماند", urgency=2)

        result = self.db.get_all_zones_comparison()
        self.assertEqual(result[0]["risk_score"], Database.ZONE_RISK_WEIGHTS["citizen_requests_open"])

    def test_answered_citizen_requests_do_not_increase_risk_score(self):
        zone_id = self.db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])
        request_id = self.db.add_citizen_request(zone_id, "درخواست پاسخ‌داده‌شده", category="پسماند", urgency=2)
        self.db.update_citizen_request(request_id, status="پاسخ‌داده‌شده")

        result = self.db.get_all_zones_comparison()
        self.assertEqual(result[0]["risk_score"], 0)

    def test_result_includes_all_zones_even_with_identical_scores(self):
        self.db.create_zone("بلوک یک", [(0, 0), (0, 1), (1, 1), (1, 0)])
        self.db.create_zone("بلوک دو", [(2, 2), (2, 3), (3, 3), (3, 2)])
        result = self.db.get_all_zones_comparison()
        self.assertEqual(len(result), 2)
        names = {item["zone_name"] for item in result}
        self.assertEqual(names, {"بلوک یک", "بلوک دو"})

    def test_result_reports_population_from_profile(self):
        zone_id = self.db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])
        self.db.save_zone_profile(zone_id, estimated_population=1200)
        result = self.db.get_all_zones_comparison()
        self.assertEqual(result[0]["estimated_population"], 1200)


if __name__ == "__main__":
    unittest.main()
