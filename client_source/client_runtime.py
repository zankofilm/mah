# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

APP_FOLDER = "JavanroodCommitteeClient"


def base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir():
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
        path = Path(root) / APP_FOLDER
    else:
        path = Path.home() / ".local" / "share" / APP_FOLDER
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_path(*parts):
    return str(base_dir().joinpath("assets", *parts))
