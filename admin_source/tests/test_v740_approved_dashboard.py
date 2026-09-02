# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT.parent


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_version_and_official_identity():
    assert 'APP_VERSION = "7.6.20"' in read("version.py")
    header = read("header_widget.py")
    for token in (
        "سامانه جامع مدیریت محلات و بلوک‌های شهرستان جوانرود",
        "وزارت کشور",
        "استانداری کرمانشاه",
        "فرمانداری شهرستان جوانرود",
        "IranFlagWidget",
        "search_mode",
    ):
        assert token in header


def test_approved_dashboard_is_implemented_as_widgets():
    source = read("dashboard_window.py")
    for token in (
        'setObjectName("DashboardSidebar")',
        '"نقشه بلوک‌ها"',
        '"اعضای معتمد"',
        '"پیام‌ها"',
        '"تعداد بلوک‌ها"',
        '"ساکنان تحت پوشش"',
        '"آخرین فعالیت‌ها"',
        '"گزارش‌های کلیدی"',
        'DonutChartWidget',
        'PanelCard',
        'apply_responsive_profile',
    ):
        assert token in source
    assert "background-image" not in source


def test_windows_release_targets_740():
    assert "7.6.20" in read("build_windows.bat")
    assert "7.6.20.0" in read("windows_version_info.txt")
    assert 'version != "7.6.20"' in read("windows_release_check.py")
    workflow = (BUNDLE / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
    assert "v7.6.20" in workflow


def test_reference_mockup_is_packaged():
    assert (ROOT / "docs" / "DASHBOARD_REFERENCE_v7_4_0.png").exists()
