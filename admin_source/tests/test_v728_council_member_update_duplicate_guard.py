# -*- coding: utf-8 -*-
"""
رگرسیون‌تست v7.2.8:
add_council_member از ثبت کد ملی تکراری جلوگیری می‌کرد، اما همین محافظت
در update_council_member وجود نداشت و می‌شد با ویرایش یک عضو، کد ملی او
را به کد ملی عضو دیگری تغییر داد. این تست تضمین می‌کند این حفره دیگر باز نشود.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


class CouncilMemberUpdateDuplicateGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "javanrood.db")
        self.db = Database(self.path)
        self.zone_id = self.db.create_zone(
            "منطقه تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )
        self.member_a = self.db.add_council_member(
            self.zone_id, "علی", "رضایی", "1234567890",
            "دیپلم", "09121234567", "شورا", "رئیس"
        )
        self.member_b = self.db.add_council_member(
            self.zone_id, "حسن", "محمدی", "0987654321",
            "دیپلم", "09121234568", "شورا", "نایب رئیس"
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_update_rejects_national_code_used_by_another_member(self):
        with self.assertRaises(ValueError):
            self.db.update_council_member(
                self.member_b, "حسن", "محمدی", "1234567890",
                "دیپلم", "09121234568", "شورا", "نایب رئیس"
            )
        codes = [
            row[0] for row in self.db.conn.execute(
                "SELECT national_code FROM council_members ORDER BY id"
            ).fetchall()
        ]
        self.assertEqual(codes, ["1234567890", "0987654321"])

    def test_update_allows_member_to_keep_own_national_code(self):
        self.db.update_council_member(
            self.member_a, "علی", "رضایی‌زاده", "1234567890",
            "لیسانس", "09121234567", "شورا", "رئیس"
        )
        row = self.db.conn.execute(
            "SELECT last_name, national_code FROM council_members WHERE id=?",
            (self.member_a,)
        ).fetchone()
        self.assertEqual(row, ("رضایی‌زاده", "1234567890"))

    def test_update_allows_new_unique_national_code(self):
        self.db.update_council_member(
            self.member_b, "حسن", "محمدی", "1111111111",
            "دیپلم", "09121234568", "شورا", "نایب رئیس"
        )
        row = self.db.conn.execute(
            "SELECT national_code FROM council_members WHERE id=?",
            (self.member_b,)
        ).fetchone()
        self.assertEqual(row[0], "1111111111")


if __name__ == "__main__":
    unittest.main()
