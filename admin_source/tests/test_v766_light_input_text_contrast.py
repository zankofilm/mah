# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_release_version_is_766():
    assert 'APP_VERSION = "7.6.20"' in read("version.py")


def test_light_input_styles_force_black_text_on_white_background():
    theme = read("theme.py")
    marker = "نسخه 7.6.6 — تضمین کنتراست متن"
    assert marker in theme
    tail = theme[theme.index(marker):]
    assert "QInputDialog QLineEdit" in tail
    assert 'QLineEdit[lightInputSurface="true"]' in tail
    assert "background: #ffffff;" in tail
    assert "color: #111111;" in tail


def test_runtime_polisher_detects_native_light_inputs():
    source = read("icon_manager.py")
    assert "def _is_light_input_surface" in source
    assert 'window.inherits("QInputDialog")' in source
    assert 'widget.setProperty("lightInputSurface", light_surface)' in source
    assert "QAbstractSpinBox" in source
    assert "QPlainTextEdit" in source
