# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_client_has_activation_login_scope_and_export_ui():
    source = (ROOT / "client_ui.py").read_text(encoding="utf-8")
    for token in (
        "ActivationWindow", "LoginWindow", "ClientMainWindow", "build_activation_request",
        "allowed_code", "btn.setEnabled(code == allowed_code)", "export_package",
    ):
        assert token in source


def test_client_does_not_ship_private_keys_or_runtime_database():
    leaked = [
        p for p in ROOT.rglob("*")
        if p.is_file() and (p.suffix.lower() in {".pem", ".db", ".jra", ".jrr", ".jrcx"} or p.name.endswith("secret.bin"))
    ]
    assert leaked == []
