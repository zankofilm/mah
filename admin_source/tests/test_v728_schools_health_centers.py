# -*- coding: utf-8 -*-
"""
تست ویژگی جدید v7.2.8: ثبت دستی مدارس و مراکز بهداشتی با مختصات دقیق،
مشابه مسجد — با قابلیت ثبت مدیر/مسؤول که به‌طور خودکار به‌عنوان معتمد
همان بلوک در شورای محلات ذخیره می‌شود، و نمایش آیکون تخصصی + مشخصات
مسؤول روی هر ۴ نقشه پروژه.

برخلاف مسجد (فهرست مرجع ثابت seed‌شده)، مدرسه و مرکز بهداشتی را خود
کاربر با مختصات دلخواه اضافه می‌کند؛ به همین دلیل add/update/delete هم
در این‌جا تست می‌شود، نه فقط ثبت مسؤول.
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


class FacilityCrudTestsMixin:
    """آزمون‌های مشترک CRUD برای مدرسه و مرکز بهداشتی؛ کلاس‌های فرزند فقط
    property های kind/add_fn/get_fn/... را مشخص می‌کنند تا کد تکرار نشود."""

    kind = None  # "school" یا "health_center"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "منطقه تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def _add(self, name, lat, lon):
        fn = getattr(self.db, f"add_{self.kind}")
        return fn(self.zone_id, name, lat, lon)

    def _get_all(self, zone_id=None):
        fn = getattr(self.db, f"get_{self.kind}s")
        return fn(zone_id=zone_id) if zone_id is not None else fn()

    def _get_one(self, facility_id):
        return getattr(self.db, f"get_{self.kind}")(facility_id)

    def _update(self, facility_id, **kwargs):
        return getattr(self.db, f"update_{self.kind}")(facility_id, **kwargs)

    def _delete(self, facility_id):
        return getattr(self.db, f"delete_{self.kind}")(facility_id)

    def _register_manager(self, facility_id, first_name, last_name, mobile=""):
        fn = getattr(self.db, f"register_{self.kind}_manager")
        return fn(facility_id, self.zone_id, first_name, last_name, mobile)

    def _get_manager(self, facility_id):
        return getattr(self.db, f"get_{self.kind}_manager")(facility_id)

    def _update_manager(self, facility_id, first_name, last_name, mobile=""):
        fn = getattr(self.db, f"update_{self.kind}_manager")
        return fn(facility_id, first_name, last_name, mobile)

    # --- تست‌های CRUD مکان ---
    def test_add_and_get_facility_with_exact_coordinates(self):
        facility_id = self._add("مکان تست", 34.812345, 46.495678)
        facility = self._get_one(facility_id)
        self.assertEqual(facility["name"], "مکان تست")
        self.assertEqual(facility["lat"], 34.812345)
        self.assertEqual(facility["lon"], 46.495678)

    def test_add_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            self._add("   ", 34.8, 46.5)

    def test_get_all_scoped_to_zone(self):
        self._add("مکان بلوک تست", 34.8, 46.5)
        other_zone_id = self.db.create_zone("بلوک دیگر", [(2, 2), (2, 3), (3, 3), (3, 2)])
        fn = getattr(self.db, f"add_{self.kind}")
        fn(other_zone_id, "مکان بلوک دیگر", 2.5, 2.5)

        this_zone_list = self._get_all(zone_id=self.zone_id)
        self.assertEqual(len(this_zone_list), 1)
        self.assertEqual(this_zone_list[0]["name"], "مکان بلوک تست")

        all_list = self._get_all()
        self.assertEqual(len(all_list), 2)

    def test_update_changes_name_and_coordinates(self):
        facility_id = self._add("نام قدیمی", 34.8, 46.5)
        self._update(facility_id, name="نام جدید", lat=35.0, lon=47.0)
        facility = self._get_one(facility_id)
        self.assertEqual(facility["name"], "نام جدید")
        self.assertEqual(facility["lat"], 35.0)
        self.assertEqual(facility["lon"], 47.0)

    def test_update_rejects_empty_name(self):
        facility_id = self._add("نام معتبر", 34.8, 46.5)
        with self.assertRaises(ValueError):
            self._update(facility_id, name="   ")

    def test_delete_removes_facility(self):
        facility_id = self._add("مکان حذف‌شونده", 34.8, 46.5)
        self._delete(facility_id)
        self.assertIsNone(self._get_one(facility_id))

    # --- تست‌های ثبت مدیر/مسؤول (الگوی معتمد بلوک) ---
    def test_register_manager_creates_trusted_council_member(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        member_id = self._register_manager(facility_id, "محمد", "احمدی", "09121234567")
        member = self.db.get_council_member(member_id)
        self.assertEqual(member["member_group"], "معتمد")
        self.assertIn("مکان تست", member["position"])
        self.assertEqual((member["first_name"], member["last_name"]), ("محمد", "احمدی"))

    def test_register_manager_rejects_missing_name(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        with self.assertRaises(ValueError):
            self._register_manager(facility_id, "", "احمدی")

    def test_registering_manager_twice_is_rejected(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        self._register_manager(facility_id, "محمد", "احمدی")
        with self.assertRaises(ValueError):
            self._register_manager(facility_id, "شخص دیگر", "دیگری")

    def test_update_manager_also_updates_linked_council_member(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        member_id = self._register_manager(facility_id, "محمد", "احمدی", "0912")
        self._update_manager(facility_id, "محمد", "احمدی‌نژاد", "0935")

        manager = self._get_manager(facility_id)
        self.assertEqual(manager["last_name"], "احمدی‌نژاد")
        self.assertEqual(manager["mobile"], "0935")

        member = self.db.get_council_member(member_id)
        self.assertEqual(member["last_name"], "احمدی‌نژاد")
        self.assertEqual(member["mobile"], "0935")
        self.assertEqual(member["member_group"], "معتمد")

    def test_update_manager_without_prior_registration_is_rejected(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        with self.assertRaises(ValueError):
            self._update_manager(facility_id, "کسی", "دیگر")

    def test_get_all_reports_manager_label_and_mobile(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        before = self._get_all(zone_id=self.zone_id)
        self.assertEqual(before[0]["manager_label"], "")
        self.assertEqual(before[0]["manager_mobile"], "")

        self._register_manager(facility_id, "محمد", "احمدی", "0912")

        after = self._get_all(zone_id=self.zone_id)
        facility = next(f for f in after if f["id"] == facility_id)
        self.assertEqual(facility["manager_label"], "محمد احمدی")
        self.assertEqual(facility["manager_mobile"], "0912")

    def test_deleting_facility_clears_manager_but_keeps_council_member(self):
        facility_id = self._add("مکان تست", 34.8, 46.5)
        member_id = self._register_manager(facility_id, "محمد", "احمدی")
        self._delete(facility_id)
        # عضو معتمد باید در شورا باقی بماند حتی اگر خودِ مکان حذف شود
        member = self.db.get_council_member(member_id)
        self.assertIsNotNone(member)
        self.assertEqual(member["first_name"], "محمد")


class SchoolTests(FacilityCrudTestsMixin, unittest.TestCase):
    kind = "school"


class HealthCenterTests(FacilityCrudTestsMixin, unittest.TestCase):
    kind = "health_center"


class FacilityMapDisplayTests(unittest.TestCase):
    """پوشش نمایش آیکون و مشخصات مسؤول مدرسه/مرکز بهداشتی روی هر ۴ نقشه پروژه."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "منطقه تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )
        self.school_id = self.db.add_school(self.zone_id, "دبستان تست", 0.5, 0.5)
        self.db.register_school_manager(self.school_id, self.zone_id, "محمد", "احمدی", "0912")
        self.hc_id = self.db.add_health_center(self.zone_id, "مرکز بهداشت تست", 0.6, 0.6)
        self.db.register_health_center_manager(self.hc_id, self.zone_id, "زهرا", "کریمی", "0935")

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_all_four_maps_show_school_icon_and_manager(self):
        schools = self.db.get_schools(zone_id=self.zone_id)
        health_centers = self.db.get_health_centers(zone_id=self.zone_id)
        zone = self.db.get_zone(self.zone_id)

        pages = {
            "view_mode": build_view_mode_html(
                [(0, 0), (0, 1), (1, 1), (1, 0)],
                schools=schools, health_centers=health_centers,
            ),
            "meeting_map": build_zone_meeting_map_html(
                zone, places=[], schools=schools, health_centers=health_centers,
            ),
            "zone_draw": build_zone_draw_html(schools=schools, health_centers=health_centers),
            "all_zones": build_all_zones_view_html([], schools=schools, health_centers=health_centers),
        }
        for page_name, html in pages.items():
            with self.subTest(page=page_name):
                self.assertIn("دبستان تست", html)
                self.assertIn("🏫", html)
                self.assertIn("محمد احمدی", html)
                self.assertIn("مرکز بهداشت تست", html)
                self.assertIn("🏥", html)
                self.assertIn("زهرا کریمی", html)

    def test_facility_without_manager_has_empty_manager_fields(self):
        empty_school_id = self.db.add_school(self.zone_id, "دبستان بدون مدیر", 0.7, 0.7)
        schools = self.db.get_schools(zone_id=self.zone_id)
        school = next(s for s in schools if s["id"] == empty_school_id)
        self.assertEqual(school["manager_label"], "")
        self.assertEqual(school["manager_mobile"], "")


if __name__ == "__main__":
    unittest.main()
