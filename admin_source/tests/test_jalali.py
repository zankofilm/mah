# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from database import Database
from jalali_utils import iso_to_jalali, jalali_to_iso, format_jalali, convert_dates_in_text


class JalaliDateTests(unittest.TestCase):
    def test_conversion_round_trip(self):
        self.assertEqual(iso_to_jalali("2026-07-20", persian_digits=False), "1405/04/29")
        self.assertEqual(jalali_to_iso("۱۴۰۵/۰۴/۲۹"), "2026-07-20")
        self.assertEqual(format_jalali("2026-07-20 12:34"), "۱۴۰۵/۰۴/۲۹ ۱۲:۳۴")
        self.assertIn("۱۴۰۵/۰۴/۲۹", convert_dates_in_text("تاریخ: 2026-07-20"))

    def test_database_accepts_jalali_and_keeps_iso(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(os.path.join(tmp, "test.db"))
            event_id = db.add_management_calendar_event(
                title="آزمون تاریخ شمسی",
                start_date="۱۴۰۵/۰۴/۲۹",
                end_date="۱۴۰۵/۰۵/۰۱",
            )
            event = db.get_management_calendar_event(event_id)
            self.assertEqual(event["start_date"], "2026-07-20")
            self.assertEqual(event["end_date"], "2026-07-23")
            db.close()


if __name__ == "__main__":
    unittest.main()
