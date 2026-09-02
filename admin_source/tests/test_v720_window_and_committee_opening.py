from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_primary_pages_share_maximized_window_policy():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def _show_primary_window" in source
    assert "window.showMaximized()" in source
    for attr in (
        "dashboard_window", "reports_window", "committees_window",
        "council_window", "blocking_window", "neighborhood_management_window",
    ):
        assert f"self._show_primary_window(self.{attr})" in source


def test_committee_page_opens_first_available_committee_automatically():
    source = (ROOT / "committees_module.py").read_text(encoding="utf-8")
    assert "def _open_default_committee" in source
    assert "QTimer.singleShot(0, lambda: self._open_default_committee())" in source
    assert "card.set_empty()" in source
    assert 'QLabel("هنوز کمیته‌ای باز نشده است")' not in source
    assert "self.db.ensure_zone_committees(self.zone_id)" in source
