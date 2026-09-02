# -*- coding: utf-8 -*-
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from map_html import (
    build_all_zones_view_html,
    build_place_editor_html,
    build_view_mode_html,
    build_zone_draw_html,
    build_zone_meeting_map_html,
)
from tile_downloader import download_tiles_for_bbox


POINTS = [(34.80, 46.48), (34.82, 46.48), (34.82, 46.50)]
ZONE = {"id": 1, "name": "آزمایشی", "color": "#123456", "boundary_points": POINTS}


def _assert_true_offline(html):
    assert "OfflineGridLayer" in html
    assert "/tile/" not in html
    assert "tile.openstreetmap.org" not in html


def test_all_offline_maps_have_no_network_tile_dependency():
    htmls = [
        build_zone_draw_html(boundary_points=POINTS, offline=True),
        build_all_zones_view_html([ZONE], boundary_points=POINTS, offline=True),
        build_place_editor_html(ZONE, [], offline=True),
        build_zone_meeting_map_html(ZONE, [], offline=True),
        build_view_mode_html(POINTS, streets=[{"name": "معبر", "geometry": POINTS}], offline=True),
    ]
    for html in htmls:
        _assert_true_offline(html)


def test_legacy_tile_cache_can_be_removed_without_touching_database():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    db = Database(path)
    try:
        db.save_tile(1, 2, 3, b"blocked")
        assert db.clear_tiles() == 1
        assert db.count_tiles() == 0
    finally:
        db.conn.close()
        if os.path.exists(path):
            os.remove(path)


def test_bulk_public_osm_tile_download_is_disabled():
    try:
        download_tiles_for_bbox(None, 0, 0, 1, 1)
    except RuntimeError as exc:
        assert "غیرفعال" in str(exc)
    else:
        raise AssertionError("bulk tile download must be disabled")
