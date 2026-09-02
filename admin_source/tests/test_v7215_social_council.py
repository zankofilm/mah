import os
import tempfile
import unittest

from database import Database, SCHEMA_VERSION


class SocialCouncilTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.db"))
        self.zone_id = self.db.create_zone("بلوک آزمایشی", [(34.8, 46.5), (34.81, 46.51), (34.8, 46.52)], "#123456")
        self.db.ensure_social_council(self.zone_id)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schema_version_and_all_tables(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 7217)
        names = {x[0] for x in self.db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expected = {
            "social_councils", "social_council_members", "social_council_meetings",
            "social_issues", "social_issue_categories", "social_issue_committee_links", "social_resolutions", "social_action_plans",
        }
        self.assertTrue(expected.issubset(names))

    def test_council_is_created_without_removing_six_committees(self):
        self.assertIsNotNone(self.db.get_social_council(self.zone_id))
        self.assertEqual(len(self.db.get_zone_committees(self.zone_id)), 6)

    def test_existing_trustee_syncs_non_destructively(self):
        self.db.add_council_member(self.zone_id, "علی", "احمدی", "1234567891", "", "09120000000", "معتمد", "معتمد محله")
        manual_id = self.db.add_social_council_member(self.zone_id, "عضو دستی", role_title="کارشناس اجتماعی")
        self.db.sync_social_council_members(self.zone_id)
        members = self.db.get_social_council_members(self.zone_id)
        self.assertTrue(any(x["full_name"] == "علی احمدی" for x in members))
        self.assertTrue(any(x["id"] == manual_id for x in members))

    def test_issue_referral_resolution_and_action_workflow(self):
        issue = self.db.add_social_issue(
            self.zone_id, "ترک تحصیل نوجوانان", category="ترک تحصیل", urgency="فوری",
            target_group="نوجوانان", affected_people=5, confidentiality="محرمانه",
        )
        committees = self.db.get_zone_committees(self.zone_id)
        self.db.refer_social_issue(issue, committees[5]["id"], "بررسی فوری")
        meeting = self.db.add_social_meeting(self.zone_id, "جلسه بررسی ترک تحصیل")
        resolution = self.db.add_social_resolution(self.zone_id, "بازگشت دانش‌آموزان به تحصیل", meeting_id=meeting, issue_id=issue)
        action = self.db.add_social_action_plan(self.zone_id, "شناسایی و پیگیری خانواده‌ها", resolution_id=resolution, issue_id=issue, progress_percent=30, status="در حال اجرا")
        self.assertEqual(len(self.db.get_social_referrals(self.zone_id)), 1)
        self.assertEqual(self.db.get_social_resolution(resolution)["issue_id"], issue)
        self.assertEqual(self.db.get_social_action_plan(action)["progress_percent"], 30)
        dashboard = self.db.get_social_dashboard(self.zone_id)
        self.assertEqual(dashboard["critical_issues"], 1)
        self.assertEqual(dashboard["actions_active"], 1)
        self.assertEqual(dashboard["confidential_cases"], 1)

    def test_social_issue_mirrors_to_neighborhood_issue(self):
        issue_id = self.db.add_social_issue(self.zone_id, "آسیب اجتماعی", category="آسیب‌های اجتماعی")
        issue = self.db.get_social_issue(issue_id)
        self.assertIsNotNone(issue["linked_neighborhood_issue_id"])
        self.assertIsNotNone(self.db.get_neighborhood_issue(issue["linked_neighborhood_issue_id"]))

    def test_general_place_manager_is_auto_invited_to_meeting(self):
        place_id = self.db.save_place(None, "بانک محله", "amenity", "bank", 34.8, 46.5, "", zone_id=self.zone_id)
        self.db.register_place_manager(place_id, self.zone_id, "رضا", "مرادی", "09121111111")
        meeting_id = self.db.add_social_meeting(self.zone_id, "جلسه بانکی", place_id=place_id, place_name="بانک محله")
        meeting = self.db.get_social_meeting(meeting_id)
        self.assertIn("رضا مرادی", meeting["invitees"])

    def test_public_report_filter_hides_confidential(self):
        self.db.add_social_issue(self.zone_id, "مورد عمومی", confidentiality="عمومی")
        self.db.add_social_issue(self.zone_id, "مورد محرمانه", confidentiality="محرمانه")
        rows = self.db.get_social_issues(self.zone_id, include_confidential=False)
        self.assertEqual([x["title"] for x in rows], ["مورد عمومی"])

    def test_mosque_and_school_managers_are_auto_invited(self):
        mosque_id = "M-SOCIAL"
        self.db.conn.execute("INSERT INTO mosques(id,name,lat,lon) VALUES (?,?,?,?)", (mosque_id, "مسجد شورا", 34.8, 46.5))
        self.db.conn.execute("INSERT INTO zone_mosques(zone_id,mosque_id) VALUES (?,?)", (self.zone_id, mosque_id))
        self.db.conn.commit()
        self.db.register_mosque_imam(mosque_id, self.zone_id, "حسن", "محمدی", "09120000002")
        mid = self.db.add_social_meeting(self.zone_id, "جلسه مسجد", place_source="mosque", place_ref_id=mosque_id, place_name="مسجد شورا")
        self.assertIn("حسن محمدی", self.db.get_social_meeting(mid)["invitees"])

        school_id = self.db.add_school(self.zone_id, "مدرسه شورا", 34.8, 46.5)
        self.db.register_school_manager(school_id, self.zone_id, "مریم", "کریمی", "09120000003")
        sid = self.db.add_social_meeting(self.zone_id, "جلسه مدرسه", place_source="school", place_ref_id=school_id, place_name="مدرسه شورا")
        self.assertIn("مریم کریمی", self.db.get_social_meeting(sid)["invitees"])

    def test_social_entities_appear_in_global_search(self):
        self.db.add_social_council_member(self.zone_id, "کارشناس ویژه اجتماعی", role_title="کارشناس اجتماعی")
        self.db.add_social_issue(self.zone_id, "مسئله ویژه اجتماعی", confidentiality="داخلی")
        result_types = {x["entity_type"] for x in self.db.global_search("ویژه")}
        self.assertIn("social_council_member", result_types)
        self.assertIn("social_issue", result_types)

    def test_create_zone_automatically_creates_social_council(self):
        other = self.db.create_zone("بلوک دوم", [(34.82, 46.5), (34.83, 46.51), (34.82, 46.52)])
        self.assertIsNotNone(self.db.get_social_council(other))



if __name__ == "__main__":
    unittest.main()
