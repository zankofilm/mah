# -*- coding: utf-8 -*-
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED = [
    "main.py", "client_ui.py", "client_database.py", "client_license_store.py",
    "client_exchange_core.py", "client.spec", "requirements.txt",
    "assets/javanrood_app.ico", "assets/javanrood_app.png",
]

def main():
    missing = [x for x in REQUIRED if not (ROOT / x).exists()]
    if missing:
        raise SystemExit("Missing: " + ", ".join(missing))
    leaked = [p for p in ROOT.rglob("*") if p.is_file() and (p.suffix.lower() == ".pem" or p.name.endswith("secret.bin"))]
    if leaked:
        raise SystemExit("Private key material must not be shipped: " + ", ".join(str(p.relative_to(ROOT)) for p in leaked))
    for path in ROOT.rglob("*.py"):
        if any(x in path.parts for x in (".venv-build", "build", "dist", "release")):
            continue
        ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    print("[OK] Client source and Windows build configuration are internally consistent.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
