import os
import tempfile
import unittest

from database import Database


class OperationsCenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "app.db"))
        self.zone_id = self.db.create_zone("بلوک عملیات", [(34.0, 46.0), (34.0, 46.1), (34.1, 46.1)])
        self.committee_id = self.db.get_zone_committees(self.zone_id)[0]["id"]

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_resolution_action_assignment_dossier_and_performance(self):
        meeting = self.db.add_committee_meeting(self.committee_id, self.zone_id, "جلسه اجرا")
        resolution = self.db.add_committee_resolution(
            self.committee_id, self.zone_id, "اصلاح روشنایی",
            meeting_id=meeting, responsible_agency="شهرداری جوانرود",
            responsible_person="مسئول خدمات", due_date="2026-08-01",
        )
        action = self.db.add_neighborhood_action(
            self.zone_id, "تعویض چراغ‌ها", responsible_office="شهرداری جوانرود",
            responsible_person="مسئول خدمات", status="در حال اجرا", progress_percent=25,
            planned_end="2026-08-02",
        )
        self.db.sync_execution_cases()
        cases = self.db.get_execution_cases(zone_id=self.zone_id)
        self.assertEqual(len(cases), 2)
        res_case = next(x for x in cases if x["source_type"] == "committee_resolution")
        act_case = next(x for x in cases if x["source_type"] == "neighborhood_action")
        self.assertEqual(res_case["source_id"], resolution)
        self.assertEqual(act_case["source_id"], action)

        self.db.add_execution_update(act_case["id"], note="عملیات آغاز شد", progress_percent=55, status="در حال اجرا")
        self.assertEqual(self.db.get_execution_case(act_case["id"])["progress_percent"], 55)
        assignment = self.db.add_execution_assignment(
            act_case["id"], assigned_to_name="کارشناس فنی", assigned_to_agency="شهرداری جوانرود",
            instruction="بازدید و گزارش", due_date="2026-07-30", priority="مهم",
        )
        self.db.update_execution_assignment(assignment, mark_viewed=True, status="دیده‌شده")
        self.db.update_execution_assignment(assignment, response_text="بازدید انجام شد", status="پاسخ‌داده‌شده")
        self.assertEqual(self.db.get_execution_assignments(case_id=act_case["id"])[0]["status"], "پاسخ‌داده‌شده")

        source = os.path.join(self.tmp.name, "evidence.txt")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write("evidence")
        self.db.archive_document_attachment("execution_case", act_case["id"], source, "مستند بازدید")
        self.assertEqual(len(self.db.get_document_attachments("execution_case", act_case["id"])), 1)

        dossier = self.db.get_zone_dossier(self.zone_id)
        self.assertEqual(dossier["zone"]["name"], "بلوک عملیات")
        self.assertEqual(len(dossier["committees"]), 6)
        self.assertGreaterEqual(dossier["execution_stats"]["total"], 2)
        agencies = self.db.get_execution_agency_performance()
        self.assertTrue(any(x["agency"] == "شهرداری جوانرود" for x in agencies))
        zones = self.db.get_execution_zone_performance()
        self.assertTrue(any(x["zone_id"] == self.zone_id for x in zones))

    def test_manual_case_and_completion(self):
        case_id = self.db.add_execution_case(
            "رفع آب‌گرفتگی", zone_id=self.zone_id, committee_id=self.committee_id,
            responsible_agency="آب و فاضلاب", due_date="2026-08-10", priority="فوری",
        )
        self.db.update_execution_case(case_id, status="تکمیل‌شده", final_result="رفع شد")
        case = self.db.get_execution_case(case_id)
        self.assertEqual(case["progress_percent"], 100)
        self.assertEqual(case["status"], "تکمیل‌شده")
        self.assertTrue(case["completed_date"])


if __name__ == "__main__":
    unittest.main()
