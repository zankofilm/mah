from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")

def test_version_767():
    assert 'APP_VERSION = "7.6.20"' in read("version.py")

def test_sidebar_is_two_column_scrollable_and_icons_smaller():
    source = read("dashboard_window.py")
    assert 'self._layout_sidebar_navigation(2)' in source
    assert 'setObjectName("DashboardSidebarScroll")' in source
    assert 'button.setIconSize(QSize(18, 18))' in source
    assert 'Qt.ToolButtonTextUnderIcon' in source

def test_flag_has_no_adjacent_badge_and_no_emblem_fallback():
    source = read("header_widget.py")
    assert 'self.badge_label = None' in source
    assert 'pix = QPixmap(EMBLEM_PATH)' not in source
    assert 'pix = QPixmap(FLAG_PATH)' in source

def test_dashboard_map_is_full_width_scrollable_and_complete():
    source = read("dashboard_window.py")
    assert 'setObjectName("DashboardMapScroll")' in source
    assert 'setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)' in source
    assert 'setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)' in source
    assert 'self.dashboard_grid.addWidget(self.map_panel, 0, 0, 1, 2)' in source
    assert '"status": zone.get("status") or "ناقص"' in source
    assert '"area_m2": zone.get("area_m2") or 0' in source
