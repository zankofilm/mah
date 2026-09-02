# -*- coding: utf-8 -*-
"""Regression coverage for dashboard startup role title resolution."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_imports_role_title_explicitly():
    tree = ast.parse((ROOT / "dashboard_window.py").read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "access_control"
        for alias in node.names
    }
    assert "role_title" in imported


def test_role_title_resolves_admin_title():
    from access_control import role_title

    assert role_title("admin") == "مدیر سامانه"
