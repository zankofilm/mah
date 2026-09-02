# -*- coding: utf-8 -*-
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "icon_manager.py"


class DeletedQObjectGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE_PATH.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_source_is_valid_python(self):
        self.assertIsInstance(self.tree, ast.Module)

    def test_alive_guard_and_safe_callback_exist(self):
        self.assertIn("def _qobject_is_alive", self.source)
        self.assertIn("def _safe_invoke", self.source)
        self.assertIn("except (RuntimeError, ReferenceError)", self.source)

    def test_show_filter_only_polishes_top_level_widgets(self):
        self.assertIn("isinstance(obj, QWidget)", self.source)
        self.assertIn("obj.isWindow()", self.source)
        self.assertNotIn('QTimer.singleShot(0, lambda target=obj: polish_widget_tree(target))', self.source)

    def test_delayed_callbacks_use_safe_invoke(self):
        self.assertIn("_safe_invoke(polish_widget_tree, target)", self.source)
        self.assertIn("_safe_invoke(_polish_button, target)", self.source)

    def test_each_tree_stage_is_guarded(self):
        self.assertIn("_safe_invoke(callback, root)", self.source)
        for function_name in (
            "polish_buttons", "polish_tabs", "polish_tables", "polish_inputs", "polish_forms"
        ):
            self.assertIn(f"def {function_name}(root):", self.source)


if __name__ == "__main__":
    unittest.main()
