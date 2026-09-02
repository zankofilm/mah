# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "committee_minutes_module.py").read_text(encoding="utf-8")


def test_resolution_editor_matches_client_style_contract():
    assert 'setObjectName("ResolutionsEditorTable")' in SOURCE
    assert '"ردیف", "شرح مصوبات", "اداره پیگیری‌کننده", "مهلت انجام", "حذف"' in SOURCE
    assert 'setObjectName("ResolutionDescriptionInput")' in SOURCE
    assert 'setObjectName("ResolutionAgencyInput")' in SOURCE
    assert 'setObjectName("ResolutionDueDateInput")' in SOURCE
    assert 'self.due.button.setVisible(False)' in SOURCE
    assert 'QPushButton("×")' in SOURCE
    assert '＋ افزودن ردیف مصوبه' in SOURCE


def test_pdf_is_opened_after_generation():
    assert "QDesktopServices" in SOURCE
    assert "QUrl.fromLocalFile(os.path.abspath(path))" in SOURCE
    generation_pos = SOURCE.index("generate_committee_minutes_pdf(")
    open_pos = SOURCE.rindex("QDesktopServices.openUrl")
    assert open_pos > generation_pos
