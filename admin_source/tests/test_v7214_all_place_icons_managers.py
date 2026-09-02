# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from place_types import supported_place_labels, get_place_icon, get_place_role_label
from map_html import (
    build_view_mode_html, build_zone_meeting_map_html,
    build_zone_draw_html, build_all_zones_view_html, build_place_editor_html,
)


class GenericPlaceManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.db"))
        self.zone_id = self.db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_every_supported_place_type_has_icon_and_role(self):
        labels = supported_place_labels()
        self.assertGreaterEqual(len(labels), 20)
        for label in labels:
            with self.subTest(label=label):
                self.assertTrue(get_place_icon(label))
                self.assertTrue(get_place_role_label(label))

    def test_register_bank_manager_creates_trusted_member(self):
        place_id = self.db.save_place(None, "بانک محله", "manual", "بانک", 0.5, 0.5, zone_id=self.zone_id)
        member_id = self.db.register_place_manager(place_id, self.zone_id, "علی", "احمدی", "0912")
        member = self.db.get_council_member(member_id)
        self.assertEqual(member["member_group"], "معتمد")
        self.assertEqual(member["position"], "رئیس شعبه بانک محله")
        place = self.db.get_place(place_id)
        self.assertEqual(place["manager_label"], "علی احمدی")
        self.assertEqual(place["manager_mobile"], "0912")

    def test_register_each_type_uses_specific_role(self):
        samples = [
            ("بیمارستان", "رئیس بیمارستان"),
            ("داروخانه", "مسئول داروخانه"),
            ("کلانتری/پلیس", "فرمانده کلانتری"),
            ("آتش‌نشانی", "مسئول ایستگاه آتش‌نشانی"),
            ("اداره دولتی", "رئیس اداره"),
        ]
        for index, (subtype, role) in enumerate(samples):
            place_id = self.db.save_place(None, f"مکان {index}", "manual", subtype, 0.2 + index * .01, 0.3, zone_id=self.zone_id)
            member_id = self.db.register_place_manager(place_id, self.zone_id, "نام", f"خانوادگی{index}")
            self.assertTrue(self.db.get_council_member(member_id)["position"].startswith(role))

    def test_duplicate_manager_is_rejected(self):
        place_id = self.db.save_place(None, "اداره تست", "manual", "اداره دولتی", 0.5, 0.5, zone_id=self.zone_id)
        self.db.register_place_manager(place_id, self.zone_id, "علی", "احمدی")
        with self.assertRaises(ValueError):
            self.db.register_place_manager(place_id, self.zone_id, "رضا", "کریمی")

    def test_manual_place_survives_osm_refresh(self):
        place_id = self.db.save_place(None, "مکان دستی", "manual", "بانک", 0.5, 0.5, zone_id=self.zone_id)
        self.db.replace_osm_data(
            self.zone_id,
            streets=[],
            places=[{"osm_id": 123, "name": "مکان OSM", "category": "amenity", "subtype": "داروخانه", "lat": .4, "lon": .4}],
            replace_streets=False,
            replace_places=True,
        )
        ids = {p["id"] for p in self.db.get_places(zone_id=self.zone_id)}
        self.assertIn(place_id, ids)

    def test_managed_osm_place_survives_osm_refresh_without_duplicate(self):
        place_id = self.db.save_place(777, "بانک OSM", "amenity", "بانک", 0.5, 0.5, zone_id=self.zone_id)
        self.db.register_place_manager(place_id, self.zone_id, "علی", "احمدی")
        self.db.replace_osm_data(
            self.zone_id, streets=[], replace_streets=False, replace_places=True,
            places=[{"osm_id": 777, "name": "بانک OSM", "category": "amenity", "subtype": "بانک", "lat": .5, "lon": .5}],
        )
        matches = [p for p in self.db.get_places(zone_id=self.zone_id) if p.get("osm_id") == 777]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["manager_label"], "علی احمدی")

    def test_place_icons_and_manager_appear_in_all_maps(self):
        place_id = self.db.save_place(None, "بانک مرکزی تست", "manual", "بانک", 0.5, 0.5, zone_id=self.zone_id)
        self.db.register_place_manager(place_id, self.zone_id, "علی", "احمدی", "0912")
        place = self.db.get_place(place_id)
        zone = self.db.get_zone(self.zone_id)
        pages = [
            build_view_mode_html(zone["boundary_points"], places=[place]),
            build_zone_meeting_map_html(zone, places=[place]),
            build_zone_draw_html(places=[place]),
            build_all_zones_view_html([{
                "name": zone["name"], "color": zone["color"], "boundary_points": zone["boundary_points"],
                "streets": [], "places": [place], "mosques": [],
            }]),
            build_place_editor_html(zone, [place]),
        ]
        for html in pages:
            self.assertIn("بانک مرکزی تست", html)
            self.assertIn("🏦", html)
            self.assertIn("علی احمدی", html)
            self.assertIn("0912", html)


if __name__ == "__main__":
    unittest.main()
