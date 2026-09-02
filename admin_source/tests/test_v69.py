# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from pathlib import Path

from database import Database
from public_portal_service import generate_public_portal


class GovernanceAndSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db1 = Database(os.path.join(self.tmp.name, "device1.db"))
        self.db2 = Database(os.path.join(self.tmp.name, "device2.db"))
        self.zone_points = [(34.80, 46.49), (34.80, 46.50), (34.81, 46.50), (34.81, 46.49)]
        self.z1 = self.db1.create_zone("بلوک تعارض", self.zone_points)
        self.z2 = self.db2.create_zone("بلوک تعارض", self.zone_points)

    def tearDown(self):
        self.db1.close(); self.db2.close(); self.tmp.cleanup()

    def test_conflict_detection_and_incoming_resolution(self):
        visit_id = self.db1.add_field_visit(self.z1, officer_name="کارشناس", observation="نسخه پایه")
        first_package = os.path.join(self.tmp.name, "first.json")
        self.db1.export_sync_package(first_package)
        counts = self.db2.import_sync_package(first_package)
        self.assertEqual(counts["inserted"], 1)
        remote = self.db2.get_field_visits(self.z2)[0]

        self.db1.update_field_visit(visit_id, observation="ویرایش دستگاه اول")
        self.db2.update_field_visit(remote["id"], observation="ویرایش دستگاه دوم")
        second_package = os.path.join(self.tmp.name, "second.json")
        self.db1.export_sync_package(second_package)
        counts = self.db2.import_sync_package(second_package)
        self.assertEqual(counts["conflicted"], 1)
        conflicts = self.db2.get_sync_conflicts("در انتظار تصمیم")
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(self.db2.get_field_visit(remote["id"])["observation"], "ویرایش دستگاه دوم")

        self.db2.resolve_sync_conflict(conflicts[0]["id"], "نسخه ورودی")
        self.assertEqual(self.db2.get_field_visit(remote["id"])["observation"], "ویرایش دستگاه اول")
        self.assertEqual(len(self.db2.get_sync_conflicts("در انتظار تصمیم")), 0)

    def test_governance_and_public_portal_redacts_personal_data(self):
        admin = self.db1.authenticate_user("admin", "admin123")
        self.assertIsNotNone(admin)
        self.db1.set_current_user(admin)
        self.db1.save_zone_profile(self.z1, approved_households=75, estimated_population=260)
        self.db1.add_citizen_request(
            self.z1, "درخواست روشنایی", citizen_name="نام محرمانه", mobile="09120000000",
            category="روشنایی", status="مختومه"
        )
        program_id = self.db1.add_annual_program("1405", "برنامه روشنایی", zone_id=self.z1, status="مصوب")
        project_id = self.db1.add_project(
            "نصب چراغ محله", program_id=program_id, zone_id=self.z1,
            actual_progress=55, status="در حال اجرا"
        )
        governance = self.db1.set_record_governance(
            "project", project_id, zone_id=self.z1, classification="عمومی",
            lifecycle_status="تأییدشده", is_public=True, data_owner="مدیر پروژه"
        )
        self.db1.approve_record_governance(governance["id"], True)

        output = generate_public_portal(self.db1, os.path.join(self.tmp.name, "portal"))
        self.assertTrue(os.path.exists(output["html_path"]))
        html = Path(output["html_path"]).read_text(encoding="utf-8")
        data_text = Path(output["data_path"]).read_text(encoding="utf-8")
        self.assertIn("نصب چراغ محله", html)
        self.assertNotIn("نام محرمانه", html + data_text)
        self.assertNotIn("09120000000", html + data_text)
        data = json.loads(data_text)
        self.assertEqual(data["summary"]["published_projects"], 1)
        self.assertEqual(data["zones"][0]["approved_households"], 75)
        self.assertEqual(len(self.db1.get_publications()), 1)

    def test_confidential_record_cannot_be_public(self):
        item = self.db1.set_record_governance(
            "citizen_request", "CR-TEST", zone_id=self.z1,
            classification="محرمانه", lifecycle_status="تأییدشده", is_public=True
        )
        self.assertFalse(bool(item["is_public"]))
        policies = {x["entity_type"]: x for x in self.db1.get_governance_policies()}
        self.assertTrue(policies["citizen_request"]["contains_personal_data"])


if __name__ == "__main__":
    unittest.main()
