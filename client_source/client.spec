# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
datas = []
for folder in ("assets", "fonts"):
    path = root / folder
    if path.exists():
        datas.append((str(path), folder))

hiddenimports = collect_submodules("PyQt5") + collect_submodules("cryptography") + collect_submodules("argon2")

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="JavanroodCommitteeClient", debug=False, console=False,
    icon=str(root / "assets" / "javanrood_app.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="JavanroodCommitteeClient")
