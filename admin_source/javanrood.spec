# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
datas = []
for folder in ("assets", "vendor", "fonts"):
    path = root / folder
    if path.exists():
        datas.append((str(path), folder))

hiddenimports = collect_submodules("PyQt5") + collect_submodules("cryptography") + collect_submodules("argon2") + collect_submodules("message_system") + [
    "arabic_reshaper", "bidi.algorithm", "PIL.Image", "reportlab.pdfbase.ttfonts",
    "openpyxl", "pptx", "docx", "qrcode",
]

icon_path = str(root / "assets" / "javanrood_app.ico")
version_path = str(root / "windows_version_info.txt")

a = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy.testing", "PySide2", "PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JavanroodNeighborhoodManagement",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=icon_path,
    version=version_path,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="JavanroodNeighborhoodManagement",
)
