# -*- coding: utf-8 -*-
"""کنترل‌های پیش از ساخت نسخه رسمی ویندوز."""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    ROOT / "app.py",
    ROOT / "version.py",
    ROOT / "javanrood.spec",
    ROOT / "windows_version_info.txt",
    ROOT / "assets" / "javanrood_app.ico",
    ROOT / "installer" / "JavanroodSetup.iss",
]
FORBIDDEN_TOKENS = ("PLACEHOLDER", "TODO_RELEASE_BLOCKER", "NotImplementedError")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    raise SystemExit(1)


def main() -> int:
    if os.name != "nt":
        print("[INFO] Static validation is running outside Windows; EXE generation still must run on Windows.")

    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.exists()]
    if missing:
        fail("Required Windows release files are missing: " + ", ".join(missing))

    leaked_private_keys = [
        path for path in (ROOT / "data").rglob("*")
        if path.is_file() and (path.suffix.lower() == ".pem" or path.name.endswith("secret.bin"))
    ]
    if leaked_private_keys:
        fail("Private client-exchange keys must not be shipped in source: " + ", ".join(
            str(path.relative_to(ROOT)) for path in leaked_private_keys
        ))

    version_ns: dict[str, object] = {}
    exec((ROOT / "version.py").read_text(encoding="utf-8"), version_ns)
    version = str(version_ns.get("APP_VERSION", ""))
    if version != "7.6.20":
        fail(f"APP_VERSION must be 7.6.20, found {version!r}")

    bad: list[str] = []
    for path in ROOT.rglob("*.py"):
        if any(part in {".venv-build", "build", "dist", "release"} for part in path.parts):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            fail(f"Syntax error in {path.relative_to(ROOT)}: {exc}")
        for token in FORBIDDEN_TOKENS:
            if token in source and path.name != "windows_release_check.py":
                bad.append(f"{path.relative_to(ROOT)} contains {token}")
    if bad:
        fail("; ".join(bad))

    installer = (ROOT / "installer" / "JavanroodSetup.iss").read_text(encoding="utf-8")
    required_installer_fragments = [
        "PrivilegesRequired=lowest",
        "preinstall_backups",
        "JavanroodNeighborhoodManagement_Setup_",
        "SetupIconFile=",
    ]
    for fragment in required_installer_fragments:
        if fragment not in installer:
            fail(f"Installer safety fragment is missing: {fragment}")

    spec = (ROOT / "javanrood.spec").read_text(encoding="utf-8")
    if "windows_version_info.txt" not in spec or "javanrood_app.ico" not in spec:
        fail("PyInstaller spec does not include Windows icon/version metadata")

    print("[OK] Windows release package is internally consistent.")
    print(f"[OK] Version: {version}")
    print("[OK] Installer preserves user data and creates a pre-install backup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
