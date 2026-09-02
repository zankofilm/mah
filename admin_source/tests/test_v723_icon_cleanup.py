from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committee_icons_have_consistent_vector_language():
    names = ("infrastructure", "health", "sport", "security", "support", "culture")
    tones = ("navy", "white", "gold", "success", "danger", "muted")
    for name in names:
        for tone in tones:
            path = ROOT / "assets" / "icons" / f"{name}_{tone}.svg"
            text = path.read_text(encoding="utf-8")
            assert 'viewBox="0 0 24 24"' in text
            assert 'stroke-width="1.8"' in text
            assert 'stroke-linecap="round"' in text


def test_member_action_icons_are_semantically_distinct():
    source = (ROOT / "icon_manager.py").read_text(encoding="utf-8")
    assert 'r"ثبت عضو جدید|افزودن عضو|عضو جدید", "user_plus", "success"' in source
    assert source.index('r"ویرایش|تغییر نام"') < source.index('r"عضو|نماینده"')
    for tone in ("navy", "white", "success"):
        assert (ROOT / "assets" / "icons" / f"user_plus_{tone}.svg").exists()


def test_committee_cards_use_two_column_clean_layout():
    source = (ROOT / "committees_module.py").read_text(encoding="utf-8")
    assert "class CommitteeMetric(QFrame)" in source
    assert "index//2, index%2" in source
    assert 'CommitteeMetric("users"' in source
    assert 'CommitteeMetric("calendar"' in source
    assert 'CommitteeMetric("resolution"' in source


def test_flat_button_and_tab_style_is_present():
    source = (ROOT / "theme.py").read_text(encoding="utf-8")
    assert "QPushButton, QToolButton" in source
    button_section = source.split("/* ---------------- دکمه‌ها ---------------- */", 1)[1].split("/* ---------------- جزئیات تعاملی ---------------- */", 1)[0]
    assert "qlineargradient" not in button_section
    assert "border-bottom: 3px solid {COLOR_GOLD};" in source
