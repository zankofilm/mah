# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ManualPlaceTypeDropdownTests(unittest.TestCase):
    def test_reusable_combo_opens_on_click_and_blocks_closed_wheel(self):
        source = (ROOT / "place_type_widgets.py").read_text(encoding="utf-8")
        self.assertIn("class PlaceTypeComboBox", source)
        self.assertIn("def mousePressEvent", source)
        self.assertIn("self.showPopup()", source)
        self.assertIn("def wheelEvent", source)
        self.assertIn("event.ignore()", source)
        self.assertIn("def add_custom_type", source)

    def test_zone_manual_place_dialog_uses_fixed_selector(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("self.type_combo = PlaceTypeComboBox()", source)
        self.assertIn('self.type_open_button.setText("▼")', source)
        self.assertIn('self.type_add_button.setText("+")', source)
        self.assertNotIn('self.type_combo.lineEdit().setPlaceholderText("نوع مکان را انتخاب یا وارد کنید")', source)

    def test_city_manual_place_dialog_uses_fixed_selector(self):
        source = (ROOT / "city_wide_map_module.py").read_text(encoding="utf-8")
        self.assertIn("self.type_combo = PlaceTypeComboBox()", source)
        self.assertIn("self.type_combo.showPopup", source)
        self.assertIn("self.type_combo.add_custom_type", source)


if __name__ == "__main__":
    unittest.main()
