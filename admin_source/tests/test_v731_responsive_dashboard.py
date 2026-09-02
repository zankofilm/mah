# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT.parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_release_version_and_design_system_are_present():
    assert 'APP_VERSION = "7.6.20"' in read("version.py")
    design = read("design_system.py")
    for token in (
        'PROFILE_COMPACT = "compact"',
        'PROFILE_COMFORTABLE = "comfortable"',
        'PROFILE_SPACIOUS = "spacious"',
        "COMPACT_MAX_WIDTH",
        "SPACIOUS_MIN_WIDTH",
        "UiMetrics",
        "metrics_for_width",
    ):
        assert token in design


def test_dashboard_reflows_without_hiding_information():
    source = read("dashboard_window.py")
    for token in (
        "apply_responsive_profile",
        "metric_columns = 1",
        "self.dashboard_grid.addWidget(self.map_panel, 0, 0)",
        "self.dashboard_grid.addWidget(self.activity_panel, 1, 0)",
        "Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextUnderIcon",
        "self.sidebar.setFixedWidth",
        "self.header.set_responsive_profile",
    ):
        assert token in source
    assert "QSplitter(Qt.Horizontal)" not in source


def test_application_wide_dpi_typography_and_icons_are_enabled():
    app = read("app.py")
    responsive = read("responsive_ui.py")
    typography = read("ui_typography.py")
    assert "Qt.AA_EnableHighDpiScaling" in app
    assert "Qt.AA_UseHighDpiPixmaps" in app
    assert "ResponsiveUiFilter" in app
    assert "app.installEventFilter(app.responsive_ui_filter)" in app
    for token in (
        "QAbstractButton", "QTableView", "QTabWidget",
        "setMinimumHeight", "setIconSize", "table_row_height",
    ):
        assert token in responsive
    assert "professional-fa-responsive" in typography


def test_header_has_compact_medium_and_spacious_profiles():
    source = read("header_widget.py")
    assert "def set_responsive_profile" in source
    assert "self.official_panel.setFixedWidth" in source
    assert "self.action_panel.setFixedWidth" in source
    assert "self.flag_widget.setVisible" in source


def test_client_uses_same_responsive_runtime():
    client = BUNDLE / "client_source"
    assert (client / "design_system.py").exists()
    assert (client / "responsive_ui.py").exists()
    main = (client / "main.py").read_text(encoding="utf-8")
    ui = (client / "client_ui.py").read_text(encoding="utf-8")
    assert "Qt.AA_EnableHighDpiScaling" in main
    assert "ResponsiveUiFilter" in ui
    assert "app.installEventFilter(app.responsive_ui_filter)" in ui


def test_windows_release_files_target_731():
    assert "7.6.20" in read("build_windows.bat")
    assert "7.6.20.0" in read("windows_version_info.txt")
    assert "7.6.20" in read("windows_release_check.py")
    workflow = (BUNDLE / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
    assert "v7.6.20" in workflow
