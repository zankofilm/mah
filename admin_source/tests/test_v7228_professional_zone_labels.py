# -*- coding: utf-8 -*-
"""Regression checks for v7.2.28 professional block labels."""

from map_html import build_all_zones_view_html, build_zone_draw_html


SAMPLE_ZONES = [
    {
        "id": 1,
        "name": "فرهنگیان",
        "color": "#1769aa",
        "status": "کامل",
        "area_m2": 125000,
        "boundary_points": [
            (34.8100, 46.4800),
            (34.8100, 46.4900),
            (34.8200, 46.4900),
            (34.8200, 46.4800),
        ],
        "streets": [],
        "places": [],
        "mosques": [],
    }
]


def test_zone_draw_map_has_zoom_aware_permanent_name_label():
    html = build_zone_draw_html(existing_zones=SAMPLE_ZONES)

    assert "zone-label-card" in html
    assert "updateExistingZoneLabels" in html
    assert "poly.getCenter()" in html
    assert "zoom < 13" in html
    assert "فرهنگیان" in html


def test_all_zones_map_has_search_selection_and_reset_controls():
    html = build_all_zones_view_html(SAMPLE_ZONES)

    assert 'id="zone-search"' in html
    assert "renderZoneList" in html
    assert "selectZone" in html
    assert "showAllZones" in html
    assert "activeZoneIndex" in html
    assert "map.fitBounds" in html
    assert "zonePopup" in html
    assert "۱۲۵۰۰۰" not in html  # input remains numeric JSON, UI formatting is performed in JS
    assert '"area_m2": 125000' in html
