# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_version_768():
    assert 'APP_VERSION = "7.6.20"' in read("version.py")


def test_dashboard_map_has_visible_zoom_in_and_zoom_out_controls():
    source = read("map_html.py")
    for token in (
        "zoomControl: false",
        "L.control.zoom",
        "position: 'topright'",
        "zoomInTitle: 'بزرگ‌نمایی'",
        "zoomOutTitle: 'کوچک‌نمایی'",
        "map.scrollWheelZoom.enable()",
        "map.doubleClickZoom.enable()",
        "map.boxZoom.enable()",
        "map.keyboard.enable()",
        "map.touchZoom.enable()",
    ):
        assert token in source


def test_dashboard_web_map_is_focusable_for_mouse_and_trackpad():
    source = read("dashboard_window.py")
    assert "self.map_view.setFocusPolicy(Qt.StrongFocus)" in source
    assert "self.map_view.setMouseTracking(True)" in source


def test_zoom_controls_do_not_overlap_left_zone_panel():
    source = read("map_html.py")
    assert "#zone-panel" in source and "left:12px" in source
    assert ".leaflet-top.leaflet-right" in source
