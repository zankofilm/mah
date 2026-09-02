# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from PIL import Image as PILImage

from report_generator import generate_block_public_report_pdf, _trusted_members_for_public_report


class FakeDb:
    def get_zone(self, zone_id):
        return {"id": zone_id, "name": "بلوک آزمایشی"}

    def get_council_members(self, zone_id=None):
        return [
            {"first_name": "علی", "last_name": "احمدی", "national_code": "1234567890", "mobile": "09121234567", "member_group": "معتمد", "position": "معتمد محله"},
            {"first_name": "مریم", "last_name": "محمدی", "national_code": "0987654321", "mobile": "09129876543", "member_group": "نخبه", "position": "عضو شورا"},
            {"first_name": "رضا", "last_name": "کریمی", "national_code": "1111111111", "mobile": "09350000000", "member_group": "معتمد", "position": "امام جماعت مسجد"},
        ]

    def get_zone_snapshot(self, zone_id):
        return None


class PublicBlockReportTest(unittest.TestCase):
    def test_filters_trusted_members_and_generates_pdf(self):
        db = FakeDb()
        trusted = _trusted_members_for_public_report(db, 1)
        self.assertEqual(len(trusted), 2)
        with tempfile.TemporaryDirectory() as tmp:
            image_path = os.path.join(tmp, "map.png")
            PILImage.new("RGB", (1000, 600), "white").save(image_path)
            pdf_path = os.path.join(tmp, "report.pdf")
            generate_block_public_report_pdf(db, 1, pdf_path, map_image_path=image_path)
            self.assertTrue(os.path.exists(pdf_path))
            self.assertGreater(os.path.getsize(pdf_path), 1000)
            with open(pdf_path, "rb") as handle:
                self.assertEqual(handle.read(4), b"%PDF")


if __name__ == "__main__":
    unittest.main()
