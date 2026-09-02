# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.8:
هنگام انتخاب یک مسجد به‌عنوان محل برگزاری جلسات یک بلوک، امام جماعت آن
مسجد ثبت می‌شود و به‌طور خودکار به‌عنوان معتمد همان بلوک (member_group=
"معتمد"، position="امام جماعت <نام مسجد>") در جدول council_members ذخیره
می‌شود. این تست‌ها مسیر کامل را — از ثبت اولیه تا نمایش در نقشه — پوشش
می‌دهند.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from map_html import (
    build_view_mode_html, build_zone_meeting_map_html,
    build_zone_draw_html, build_all_zones_view_html,
)


class MosqueImamRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "منطقه تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )
        # فهرست مرجع مساجد به‌طور پیش‌فرض seed می‌شود؛ یکی را به این بلوک متصل می‌کنیم
        all_mosques = self.db.get_mosques()
        self.assertTrue(all_mosques, "فهرست مرجع مساجد باید از پیش seed شده باشد")
        self.mosque_id = all_mosques[0]["id"]
        self.mosque_name = all_mosques[0]["name"]
        self.db.conn.execute(
            "INSERT INTO zone_mosques (zone_id, mosque_id) VALUES (?, ?)",
            (self.zone_id, self.mosque_id),
        )
        self.db.conn.commit()

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_register_creates_trusted_council_member_with_correct_position(self):
        member_id = self.db.register_mosque_imam(
            self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233"
        )
        member = self.db.get_council_member(member_id)
        self.assertEqual(member["member_group"], "معتمد")
        self.assertEqual(member["position"], f"امام جماعت {self.mosque_name}")
        self.assertEqual(member["zone_id"], self.zone_id)
        self.assertEqual((member["first_name"], member["last_name"]), ("سید علی", "حسینی"))

        # عضو تازه‌ساخته باید در فهرست اعضای همان بلوک هم دیده شود
        zone_members = self.db.get_council_members(zone_id=self.zone_id)
        self.assertTrue(any(m["id"] == member_id for m in zone_members))

    def test_register_rejects_missing_name(self):
        with self.assertRaises(ValueError):
            self.db.register_mosque_imam(self.mosque_id, self.zone_id, "", "حسینی")

    def test_register_twice_for_same_mosque_is_rejected(self):
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی")
        with self.assertRaises(ValueError):
            self.db.register_mosque_imam(self.mosque_id, self.zone_id, "شخص دیگر", "دیگری")

    def test_update_imam_also_updates_the_linked_council_member(self):
        member_id = self.db.register_mosque_imam(
            self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233"
        )
        self.db.update_mosque_imam(self.mosque_id, "سید علی", "حسینی‌نژاد", "09121112244")

        imam = self.db.get_mosque_imam(self.mosque_id)
        self.assertEqual(imam["last_name"], "حسینی‌نژاد")
        self.assertEqual(imam["mobile"], "09121112244")

        member = self.db.get_council_member(member_id)
        self.assertEqual(member["last_name"], "حسینی‌نژاد")
        self.assertEqual(member["mobile"], "09121112244")
        # سمت و دسته‌بندی معتمد باید حفظ شود
        self.assertEqual(member["member_group"], "معتمد")
        self.assertEqual(member["position"], f"امام جماعت {self.mosque_name}")

    def test_update_without_prior_registration_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.update_mosque_imam(self.mosque_id, "کسی", "دیگر")

    def test_get_mosques_reports_imam_label_and_mobile(self):
        mosques_before = self.db.get_mosques(zone_id=self.zone_id)
        self.assertEqual(mosques_before[0]["imam_label"], "")
        self.assertEqual(mosques_before[0]["imam_mobile"], "")

        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233")

        mosques_after = self.db.get_mosques(zone_id=self.zone_id)
        mosque = next(m for m in mosques_after if m["id"] == self.mosque_id)
        self.assertEqual(mosque["imam_label"], "سید علی حسینی")
        self.assertEqual(mosque["imam_mobile"], "09121112233")

    def test_imam_phone_appears_in_general_zone_map_popup(self):
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233")
        mosques = self.db.get_mosques(zone_id=self.zone_id)
        html = build_view_mode_html([(0, 0), (0, 1), (1, 1), (1, 0)], mosques=mosques)
        self.assertIn("09121112233", html)

    def test_imam_phone_appears_in_meeting_place_selector_map_popup(self):
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233")
        mosques = self.db.get_mosques(zone_id=self.zone_id)
        zone = self.db.get_zone(self.zone_id)
        html = build_zone_meeting_map_html(zone, places=[], mosques=mosques)
        self.assertIn("09121112233", html)

    def test_imam_member_sorts_first_regardless_of_registration_order(self):
        """امام جماعت باید همیشه ابتدای فهرست UI باشد، حتی اگر بعد از سایر
        اعضا ثبت شده باشد (منطق مرتب‌سازی در council_module.py)."""
        self.db.add_council_member(
            self.zone_id, "رضا", "احمدی", "1112223334", "دیپلم", "0912", "نخبه", "عضو عادی"
        )
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی")

        members = self.db.get_council_members(zone_id=self.zone_id)
        is_imam = lambda m: bool((m.get("position") or "").startswith("امام جماعت"))
        sorted_members = sorted(members, key=lambda m: 0 if is_imam(m) else 1)

        self.assertTrue(is_imam(sorted_members[0]))
        self.assertEqual(sorted_members[0]["first_name"], "سید علی")

    def test_imam_info_appears_in_zone_draw_map(self):
        """نقشه رسم منطقه جدید نیز باید نام و تلفن امام جماعت را نشان دهد."""
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233")
        mosques = self.db.get_mosques()
        html = build_zone_draw_html(mosques=mosques)
        self.assertIn("سید علی حسینی", html)
        self.assertIn("09121112233", html)

    def test_imam_info_appears_in_all_zones_overview_map(self):
        """نقشه کلی همه بلوک‌ها نیز باید نام و تلفن امام جماعت را نشان دهد."""
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی", "09121112233")
        mosques = self.db.get_mosques()
        html = build_all_zones_view_html([], mosques=mosques)
        self.assertIn("سید علی حسینی", html)
        self.assertIn("09121112233", html)

    def test_mosque_without_imam_has_empty_imam_fields_in_map_data(self):
        """اگر امامی ثبت نشده باشد، داده تزریق‌شده به نقشه باید imamLabel/imamMobile خالی داشته باشد
        (نه اینکه رشته «امام جماعت» به‌اشتباه در HTML دیده شود؛ آن رشته بخشی از قالب جاوااسکریپت
        است و صرفاً هنگام اجرا در مرورگر، در صورت خالی‌بودن imamLabel، نمایش داده نمی‌شود)."""
        mosques = self.db.get_mosques(zone_id=self.zone_id)
        self.assertEqual(mosques[0]["imam_label"], "")
        self.assertEqual(mosques[0]["imam_mobile"], "")
        zone = self.db.get_zone(self.zone_id)
        for html in (
            build_view_mode_html([(0, 0), (0, 1), (1, 1), (1, 0)], mosques=mosques),
            build_zone_meeting_map_html(zone, places=[], mosques=mosques),
            build_zone_draw_html(mosques=mosques),
            build_all_zones_view_html([], mosques=mosques),
        ):
            self.assertIn('"imamLabel": ""', html)

    def test_imam_name_appears_in_general_zone_map_popup(self):
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی")
        mosques = self.db.get_mosques(zone_id=self.zone_id)
        html = build_view_mode_html([(0, 0), (0, 1), (1, 1), (1, 0)], mosques=mosques)
        self.assertIn("سید علی حسینی", html)
        self.assertIn("امام جماعت", html)

    def test_imam_name_appears_in_meeting_place_selector_map_popup(self):
        self.db.register_mosque_imam(self.mosque_id, self.zone_id, "سید علی", "حسینی")
        mosques = self.db.get_mosques(zone_id=self.zone_id)
        zone = self.db.get_zone(self.zone_id)
        html = build_zone_meeting_map_html(zone, places=[], mosques=mosques)
        self.assertIn("سید علی حسینی", html)

    def test_deleting_linked_council_member_keeps_imam_record_but_clears_link(self):
        member_id = self.db.register_mosque_imam(
            self.mosque_id, self.zone_id, "سید علی", "حسینی"
        )
        self.db.delete_council_member(member_id)
        imam = self.db.get_mosque_imam(self.mosque_id)
        self.assertIsNotNone(imam, "رکورد امام جماعت باید پس از حذف عضو شورا باقی بماند")
        self.assertIsNone(imam["council_member_id"])


if __name__ == "__main__":
    unittest.main()
