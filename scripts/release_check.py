# -*- coding: utf-8 -*-
"""Deterministic release gate for local and CI builds."""
from __future__ import annotations
import compileall
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "admin_source"
CLIENT = ROOT / "client_source"


def run(command, cwd=ROOT):
    print("+", " ".join(map(str, command)))
    subprocess.run(command, cwd=cwd, check=True)


def main():
    if not compileall.compile_dir(str(ADMIN), quiet=1) or not compileall.compile_dir(str(CLIENT), quiet=1):
        raise SystemExit("Python compilation failed")
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ADMIN, env=env, check=True)
    run([sys.executable, "windows_release_check.py"], cwd=ADMIN)
    run([sys.executable, "windows_release_check.py"], cwd=CLIENT)
    print("Release gate passed.")


if __name__ == "__main__":
    main()
