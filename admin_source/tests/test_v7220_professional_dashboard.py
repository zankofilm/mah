from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def test_release_version_and_dashboard_components():
    assert 'APP_VERSION = "7.6.20"' in (ROOT / 'version.py').read_text(encoding='utf-8')
    source = (ROOT / 'dashboard_window.py').read_text(encoding='utf-8')
    for token in (
        'DashboardSidebar', 'PanelCard', 'DonutChartWidget',
        'MetricCard', 'PanelIcon', 'DashboardFooter',
    ):
        assert token in source


def test_professional_typography_profile():
    source = (ROOT / 'ui_typography.py').read_text(encoding='utf-8')
    for family in ('Vazirmatn', 'Estedad', 'Peyda', 'Dana', 'IRANYekanX', 'IRANSansX'):
        assert family in source
    assert 'addApplicationFont' in source
    assert 'uiTypographyProfile' in source


def test_icon_family_is_consistent():
    icon_dir = ROOT / 'assets' / 'icons'
    manifest = json.loads((icon_dir / 'ICON_STYLE_v7_2_20.json').read_text(encoding='utf-8'))
    assert manifest['profile'] == 'professional-line-v2'
    assert manifest['filesUpdated'] == 294
    assert manifest['strokeWidth'] == 1.8
    assert sum(manifest['counts'].values()) == 294
