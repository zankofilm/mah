# -*- coding: utf-8 -*-
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_dashboard_and_controller_are_connected():
    dashboard = (ROOT / "dashboard_window.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    database = (ROOT / "database.py").read_text(encoding="utf-8")
    assert "open_client_management_module" in dashboard
    assert "ClientManagementWindow" in app
    assert "show_client_management_module" in app
    assert "ClientExchangeMixin" in database
    assert "_create_client_exchange_tables" in database


def test_private_admin_keys_are_not_shipped():
    leaked = [
        p for p in (ROOT / "data").rglob("*")
        if p.is_file() and (p.suffix.lower() == ".pem" or p.name.endswith("secret.bin"))
    ]
    assert leaked == []


def test_client_dependencies_are_in_release_requirements():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "cryptography" in req
    assert "argon2-cffi" in req
