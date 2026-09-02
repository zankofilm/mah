# -*- coding: utf-8 -*-
"""
تست بازآرایی (refactor) database.py به چند Mixin مستقل — بدون تغییر
منطق، فقط جابه‌جایی محل کد برای کاهش حجم فایل اصلی (از ~۸۹۰۰ خط):

- database_council_facilities.py: شورای محلات، امام جماعت/مدارس/
  مراکز بهداشتی، تنظیمات هوش مصنوعی، درخواست‌های اولویت‌بندی.
- database_projects_contracts.py: کنترل پروژه، قراردادها/پیمانکاران.

این تست‌ها دو چیز را می‌سنجند:
۱) کلاس Database هنوز همان API عمومی سابق را دارد (چه از طریق instance
   چه به‌صورت class attribute مستقیم، مثل Database.COUNCIL_GROUPS که
   council_module.py مستقیماً از آن استفاده می‌کند).
۲) مسیر تولید خودکار کد پروژه (_next_project_code) که در حین این
   بازآرایی یک باگ import فراموش‌شده (datetime) در آن پیدا و رفع شد،
   اکنون پوشش تست دارد تا در آینده دوباره بی‌صدا نشکند.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


class DatabaseMixinSplitIntegrityTests(unittest.TestCase):
    """اطمینان از این‌که attributeها و متدهای هر دو Mixin از طریق کلاس
    اصلی Database (بدون نیاز به import مستقیم فایل‌های Mixin) در دسترسند."""

    def test_class_level_constants_accessible_without_instantiation(self):
        # از database_council_facilities.py
        self.assertIn("معتمد", Database.COUNCIL_GROUPS)
        # از database_projects_contracts.py
        self.assertIn("در حال اجرا", Database.PROJECT_STATUSES)
        self.assertIn("فعال", Database.CONTRACT_STATUSES)

    def test_methods_from_both_mixins_work_on_same_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(os.path.join(tmp, "javanrood.db"))
            zone_id = db.create_zone("بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)])

            # متد از CouncilFacilitiesMixin
            member_id = db.add_council_member(
                zone_id, "علی", "رضایی", "1234567890", "دیپلم", "0912", "معتمد", "رئیس"
            )
            self.assertIsNotNone(db.get_council_member(member_id))

            # متد از ProjectContractsMixin، روی همان instance و همان self.conn
            project_id = db.add_project("پروژه تست", zone_id=zone_id)
            self.assertIsNotNone(project_id)
            contractor_id = db.add_contractor("پیمانکار تست")
            contract_id = db.add_contract("C-1", "قرارداد تست", contractor_id, project_id=project_id)
            self.assertIsNotNone(contract_id)
            db.conn.close()


class ProjectAutoCodeGenerationTests(unittest.TestCase):
    """پوشش مسیر _next_project_code — جایی که در حین استخراج Mixin،
    import ماژول datetime به‌اشتباه از قلم افتاده بود و NameError می‌داد.
    هیچ تست قبلی پروژه این مسیر را پوشش نمی‌داد."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "javanrood.db"))
        self.zone_id = self.db.create_zone(
            "بلوک تست", [(0, 0), (0, 1), (1, 1), (1, 0)]
        )

    def tearDown(self):
        self.db.conn.close()
        self.tmp.cleanup()

    def test_project_without_explicit_code_gets_auto_generated_code(self):
        project_id = self.db.add_project("پروژه بدون کد دستی", zone_id=self.zone_id)
        project = self.db.get_project(project_id)
        self.assertTrue(project["project_code"])
        self.assertTrue(project["project_code"].startswith("PRJ-"))

    def test_multiple_auto_generated_codes_are_unique(self):
        id1 = self.db.add_project("پروژه اول", zone_id=self.zone_id)
        id2 = self.db.add_project("پروژه دوم", zone_id=self.zone_id)
        code1 = self.db.get_project(id1)["project_code"]
        code2 = self.db.get_project(id2)["project_code"]
        self.assertNotEqual(code1, code2)

    def test_explicit_project_code_is_preserved(self):
        project_id = self.db.add_project(
            "پروژه با کد دستی", project_code="CUSTOM-001", zone_id=self.zone_id
        )
        project = self.db.get_project(project_id)
        self.assertEqual(project["project_code"], "CUSTOM-001")


if __name__ == "__main__":
    unittest.main()
