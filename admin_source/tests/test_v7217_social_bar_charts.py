# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

from database import SCHEMA_VERSION
from social_chart_reports import (
    CHART_TYPES,
    actions_status_payload,
    blocks_comparison_payload,
    committees_performance_payload,
    filter_rows,
    issues_by_category_payload,
    resolutions_status_payload,
)

ROOT = Path(__file__).resolve().parents[1]


class SocialBarChartReportTests(unittest.TestCase):
    def test_release_schema_and_five_chart_types(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 7217)
        self.assertEqual(len(CHART_TYPES), 5)
        self.assertEqual(
            {key for key, _ in CHART_TYPES},
            {
                "issues_by_category",
                "blocks_comparison",
                "committees_performance",
                "resolutions_status",
                "actions_status",
            },
        )

    def test_category_and_status_aggregation(self):
        issues = [
            {"category": "اعتیاد", "status": "ثبت اولیه"},
            {"category": "اعتیاد", "status": "در حال بررسی"},
            {"category": "ترک تحصیل", "status": "ثبت اولیه"},
        ]
        payload = issues_by_category_payload(issues)
        self.assertEqual(payload["categories"][0], "اعتیاد")
        self.assertEqual(payload["series"][0]["values"][0], 2)

        resolutions = [{"status": "در انتظار اقدام"}, {"status": "انجام‌شده"}, {"status": "در انتظار اقدام"}]
        resolution_payload = resolutions_status_payload(resolutions)
        self.assertEqual(resolution_payload["rows"][0], ["در انتظار اقدام", 2])

    def test_committee_and_block_grouped_series(self):
        referrals = [
            {"committee_title": "بهداشت و سلامت", "status": "پاسخ‌داده‌شده"},
            {"committee_title": "بهداشت و سلامت", "status": "در حال بررسی"},
        ]
        payload = committees_performance_payload(referrals, ["بهداشت و سلامت", "نشاط و ورزش"])
        row = next(row for row in payload["rows"] if row[0] == "بهداشت و سلامت")
        self.assertEqual(row[1:], [2, 1, 1])
        self.assertEqual(len(payload["series"]), 3)

        block_payload = blocks_comparison_payload([
            {
                "zone_name": "بلوک یک",
                "issues": [{"status": "ثبت اولیه", "urgency": "بحرانی"}],
                "resolutions": [{"status": "در انتظار اقدام"}],
                "actions": [{"status": "در حال اجرا"}],
            }
        ])
        self.assertEqual(block_payload["rows"][0], ["بلوک یک", 1, 1, 1, 1])
        self.assertEqual(len(block_payload["series"]), 4)

    def test_action_average_progress_and_date_filter(self):
        actions = [
            {"status": "در حال اجرا", "progress_percent": 20, "created_at": "2026-04-01"},
            {"status": "در حال اجرا", "progress_percent": 60, "created_at": "2026-05-01"},
            {"status": "تکمیل‌شده", "progress_percent": 100, "created_at": "2026-06-01"},
        ]
        filtered = filter_rows(actions, "در حال اجرا", "2026-04-15", "2026-05-31", ("created_at",))
        self.assertEqual(len(filtered), 1)
        payload = actions_status_payload(actions)
        running = next(row for row in payload["rows"] if row[0] == "در حال اجرا")
        self.assertEqual(running, ["در حال اجرا", 2, "40.0٪"])

    def test_ui_contains_filters_and_all_exports(self):
        source = (ROOT / "social_council_module.py").read_text(encoding="utf-8")
        self.assertIn("class BarChartWidget", source)
        self.assertIn("گزارش‌های نموداری", source)
        self.assertIn("self.chart_date_from", source)
        self.assertIn("self.chart_committee", source)
        self.assertIn("def export_chart_image", source)
        self.assertIn("def export_charts_word", source)
        self.assertIn("def export_charts_pdf", source)


if __name__ == "__main__":
    unittest.main()
