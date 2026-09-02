# -*- coding: utf-8 -*-
import io
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from database import Database
from committee_minutes_pdf import generate_committee_minutes_pdf


ROOT = Path(__file__).resolve().parents[1]


class CommitteeMinutesAdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "app.db"))
        cur = self.db.conn.cursor()
        cur.execute(
            "INSERT INTO zones(name,color,boundary_points,area_m2,perimeter_m,status) VALUES (?,?,?,?,?,?)",
            ("بلوک صورتجلسه", "#224466", "[]", 10000, 400, "کامل"),
        )
        self.zone_id = cur.lastrowid
        self.db.conn.commit()
        self.committee = self.db.ensure_zone_committees(self.zone_id)[0]
        self.committee_id = self.committee["id"]

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schema_meeting_bundle_and_signatures(self):
        columns = [row[1] for row in self.db.conn.execute("PRAGMA table_info(committee_meetings)")]
        self.assertIn("meeting_number", columns)
        tables = {row[0] for row in self.db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("committee_meeting_signatures", tables)

        member_id = self.db.add_committee_member(
            self.committee_id, "عضو آزمایشی", member_role="دبیر کمیته",
            member_type="نماینده اداره", status="فعال",
        )
        meeting_id = self.db.add_committee_meeting(
            self.committee_id, self.zone_id, "صورتجلسه شماره ۱",
            meeting_number="1", meeting_date="2026-07-30", start_time="10:30",
            minutes_text="شرح مذاکرات", status="برگزارش‌شده",
        )
        self.db.save_committee_meeting_resolutions(
            meeting_id, self.committee_id, self.zone_id,
            [{"description": "شرح مصوبه", "responsible_agency": "شهرداری", "due_date": "2026-08-10"}],
        )
        self.db.save_committee_meeting_signature(meeting_id, member_id, b"png-data")

        meeting = self.db.get_committee_meeting(meeting_id)
        self.assertEqual(meeting["meeting_number"], "1")
        self.assertEqual(len(self.db.get_committee_meeting_resolutions(meeting_id)), 1)
        self.assertEqual(self.db.get_committee_meeting_signatures(meeting_id)[0]["signature_png"], b"png-data")

    def test_meeting_number_starts_at_one_and_continues(self):
        self.assertEqual(self.db.next_committee_meeting_number(self.committee_id), "1")
        self.db.add_committee_meeting(
            self.committee_id, self.zone_id, "صورتجلسه شماره ۱", meeting_number="۱"
        )
        self.assertEqual(self.db.next_committee_meeting_number(self.committee_id), "2")
        self.db.add_committee_meeting(
            self.committee_id, self.zone_id, "صورتجلسه شماره ۲", meeting_number="٢"
        )
        self.assertEqual(self.db.next_committee_meeting_number(self.committee_id), "3")

    def test_pdf_is_non_empty_and_contains_two_independent_pages(self):
        member_id = self.db.add_committee_member(
            self.committee_id, "علی محمدی", member_role="رئیس کمیته",
            member_type="عضو", is_chair=True, status="فعال",
        )
        meeting_id = self.db.add_committee_meeting(
            self.committee_id, self.zone_id, "صورتجلسه شماره ۲",
            meeting_number="2", meeting_date="2026-07-30", start_time="11:00",
            minutes_text="شرح کامل مذاکرات جلسه", status="برگزارش‌شده",
        )
        self.db.save_committee_meeting_resolutions(
            meeting_id, self.committee_id, self.zone_id,
            [{"description": "پیگیری روشنایی معابر", "responsible_agency": "شهرداری", "due_date": "2026-08-12"}],
        )
        image = Image.new("RGB", (900, 300), "white")
        draw = ImageDraw.Draw(image)
        draw.line([(80, 190), (250, 70), (430, 190), (720, 100)], fill="black", width=10)
        data = io.BytesIO(); image.save(data, format="PNG")
        self.db.save_committee_meeting_signature(meeting_id, member_id, data.getvalue())

        output = os.path.join(self.tmp.name, "minutes.pdf")
        signatures = {x["member_id"]: x["signature_png"] for x in self.db.get_committee_meeting_signatures(meeting_id)}
        generate_committee_minutes_pdf(
            output, self.db.get_committee(self.committee_id), self.db.get_committee_meeting(meeting_id),
            self.db.get_committee_meeting_resolutions(meeting_id), self.db.get_committee_members(self.committee_id),
            signatures, include_minutes=True, include_signatures=True,
        )
        raw = Path(output).read_bytes()
        self.assertTrue(raw.startswith(b"%PDF"))
        self.assertGreater(len(raw), 5000)
        # reportlab writes one /Type /Page object for each independent A4 page.
        self.assertGreaterEqual(raw.count(b"/Type /Page"), 2)

    def test_admin_ui_integration_and_version(self):
        version = (ROOT / "version.py").read_text(encoding="utf-8")
        committees = (ROOT / "committees_module.py").read_text(encoding="utf-8")
        ui = (ROOT / "committee_minutes_module.py").read_text(encoding="utf-8")
        self.assertIn('APP_VERSION = "7.6.13"', version)
        self.assertIn("صورتجلسه A4 جدید", committees)
        self.assertIn("بازکردن صورتجلسه انتخاب‌شده", committees)
        self.assertIn("class SignaturePad", ui)
        self.assertIn("انتخاب تاریخ جلسه", ui)
        self.assertIn("انتخاب ساعت جلسه", ui)
        self.assertIn("PDF کامل دو برگ", ui)


if __name__ == "__main__":
    unittest.main()
