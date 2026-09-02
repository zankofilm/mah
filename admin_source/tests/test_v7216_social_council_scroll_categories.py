import os
import tempfile
import unittest
from pathlib import Path

from database import Database, SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[1]


class SocialCouncilScrollCategoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schema_and_default_categories(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 7217)
        categories = self.db.get_social_issue_categories()
        self.assertIn("آسیب‌های اجتماعی", categories)
        self.assertIn("سایر", categories)

    def test_custom_category_is_persistent_and_not_duplicated(self):
        first = self.db.add_social_issue_category("کودکان کار")
        second = self.db.add_social_issue_category("  کودکان   کار  ")
        self.assertEqual(first, second)
        self.assertEqual(self.db.get_social_issue_categories().count("کودکان کار"), 1)

    def test_all_social_data_entry_dialogs_use_scroll_form(self):
        source = (ROOT / "social_council_module.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("form=_dialog_form(self)"), 6)
        self.assertIn("form = _dialog_form(self)", source)
        self.assertIn("QInputDialog.getText", source)
        self.assertIn("دسته‌بندی آسیب‌های اجتماعی", source)


if __name__ == "__main__":
    unittest.main()
