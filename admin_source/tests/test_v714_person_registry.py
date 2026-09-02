import os
import tempfile
import unittest

from database import Database


class PersonRegistryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "app.db"))
        self.zone_id = self.db.create_zone(
            "بلوک اشخاص",
            [(34.0, 46.0), (34.0, 46.1), (34.1, 46.1)],
        )
        self.committee_id = self.db.get_zone_committees(self.zone_id)[0]["id"]

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_lookup_council_member_and_reuse_in_committee(self):
        code = "1234567891"
        council_id = self.db.add_council_member(
            self.zone_id,
            "علی",
            "احمدی",
            code,
            "کارشناسی",
            "09120000000",
            "معتمد",
            "عضو شورا",
        )
        person = self.db.find_person_by_national_code(code)
        self.assertIsNotNone(person)
        self.assertEqual(person["first_name"], "علی")
        self.assertEqual(person["last_name"], "احمدی")

        committee_member_id = self.db.add_committee_member(
            self.committee_id,
            "علی احمدی",
            person_id=person["id"],
            national_code=code,
            mobile="09120000000",
            education="کارشناسی",
            member_type="عضو شورای محله",
            member_role="عضو",
            status="فعال",
        )
        committee_member = self.db.get_committee_member(committee_member_id)
        council_member = self.db.get_council_members(self.zone_id)[0]
        self.assertEqual(committee_member["person_id"], council_member["person_id"])
        self.assertEqual(committee_member["education"], "کارشناسی")
        self.assertEqual(council_member["id"], council_id)

        self.db.upsert_person(
            code,
            first_name="علی",
            last_name="احمدی",
            education="کارشناسی ارشد",
            mobile="09121111111",
        )
        self.assertEqual(self.db.get_council_members(self.zone_id)[0]["mobile"], "09121111111")
        self.assertEqual(self.db.get_committee_member(committee_member_id)["mobile"], "09121111111")
        self.assertEqual(self.db.get_committee_member(committee_member_id)["education"], "کارشناسی ارشد")

    def test_new_person_and_duplicate_membership_prevention(self):
        code = "0000000019"
        person_id = self.db.upsert_person(
            code,
            first_name="مریم",
            last_name="کریمی",
            education="دیپلم",
            mobile="09123333333",
        )
        member_id = self.db.add_committee_member(
            self.committee_id,
            "مریم کریمی",
            person_id=person_id,
            national_code=code,
            mobile="09123333333",
            education="دیپلم",
            status="فعال",
        )
        self.assertEqual(self.db.get_committee_member(member_id)["person_id"], person_id)
        with self.assertRaises(ValueError):
            self.db.add_committee_member(
                self.committee_id,
                "مریم کریمی",
                person_id=person_id,
                national_code=code,
                status="فعال",
            )

    def test_persian_digits_are_normalized(self):
        person_id = self.db.upsert_person(
            "۱۲۳۴۵۶۷۸۹۱",
            first_name="رضا",
            last_name="محمدی",
        )
        person = self.db.get_person(person_id)
        self.assertEqual(person["national_code"], "1234567891")
        self.assertEqual(self.db.find_person_by_national_code("۱۲۳۴۵۶۷۸۹۱")["id"], person_id)


if __name__ == "__main__":
    unittest.main()
