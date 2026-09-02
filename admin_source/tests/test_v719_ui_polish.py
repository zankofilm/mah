from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_typography_is_applied_before_stylesheet():
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "apply_application_typography(app)" in app_source
    assert app_source.index("apply_application_typography(app)") < app_source.index("app.setStyleSheet(MAIN_STYLESHEET)")


def test_committee_icon_family_and_cards_exist():
    source = (ROOT / "committees_module.py").read_text(encoding="utf-8")
    assert "class CommitteeCard(QFrame)" in source
    expected = ("infrastructure", "health", "sport", "security", "support", "culture")
    for name in expected:
        assert (ROOT / "assets" / "icons" / f"{name}_navy.svg").exists()
        assert (ROOT / "assets" / "icons" / f"{name}_white.svg").exists()
        assert f'"{name}"' in source
