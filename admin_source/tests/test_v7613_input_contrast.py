from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _v7613_block():
    source = (ROOT / "theme.py").read_text(encoding="utf-8")
    marker = "# نسخه 7.6.13 — اصلاح قطعی کنتراست تمام فیلدهای ورودی در پنل ادمین"
    assert marker in source
    return source.split(marker, 1)[1]


def test_all_input_classes_have_light_surface_and_dark_text():
    block = _v7613_block()
    for selector in (
        "QLineEdit", "QTextEdit", "QPlainTextEdit", "QComboBox",
        "QAbstractSpinBox", "QSpinBox", "QDoubleSpinBox", "QDateEdit",
        "QDateTimeEdit", "QTimeEdit", "QKeySequenceEdit",
    ):
        assert selector in block
    assert "background: #ffffff;" in block
    assert "color: #111827;" in block
    assert "placeholder-text-color" not in block


def test_override_is_applied_to_all_application_stylesheets():
    block = _v7613_block()
    assert "MAIN_STYLESHEET += _ADMIN_LIGHT_INPUTS_QSS" in block
    assert "LOGIN_STYLESHEET += _ADMIN_LIGHT_INPUTS_QSS" in block
    assert "DASHBOARD_STYLESHEET += _ADMIN_LIGHT_INPUTS_QSS" in block


def test_native_palette_guard_exists():
    source = (ROOT / "icon_manager.py").read_text(encoding="utf-8")
    assert "def _apply_light_input_palette" in source
    assert 'QColor("#ffffff")' in source
    assert 'QColor("#111827")' in source
    assert "PaletteChange" in source or "_apply_light_input_palette" in source
    assert 'widget.setProperty("lightInputSurface", True)' in source
