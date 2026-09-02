"""
Javanrood v7.6.18 Smart Backup + Offline Map foundation.
Keeps operational DB separate from offline map data and supports versioned backups.
"""
import json, shutil, sqlite3, zipfile
from pathlib import Path
from datetime import datetime

SCHEMA_VERSION = "7.6.18"

class SmartBackupManager:
    def __init__(self, base_dir):
        self.base = Path(base_dir)
        self.map_dir = self.base / "map_data"
        self.backup_dir = self.base / "backup"

    def backup(self, output_zip):
        self.backup_dir.mkdir(exist_ok=True)
        manifest = {
            "app_version": SCHEMA_VERSION,
            "created": datetime.now().isoformat(),
            "components": ["main_db", "offline_map", "settings"]
        }
        (self.backup_dir / "version.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for p in self.base.rglob("*"):
                if p.is_file() and ("map_data" in p.parts or p.name in ["version.json", "settings.json"] or p.suffix==".db"):
                    z.write(p, p.relative_to(self.base))

    def restore(self, backup_zip):
        with zipfile.ZipFile(backup_zip) as z:
            z.extractall(self.base)
        return True


def init_map_database(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS map_meta(id INTEGER PRIMARY KEY, area_name TEXT, polygon TEXT, version TEXT);
    CREATE TABLE IF NOT EXISTS roads(id INTEGER PRIMARY KEY, name TEXT, geometry TEXT);
    CREATE TABLE IF NOT EXISTS streets(id INTEGER PRIMARY KEY, name TEXT, geometry TEXT);
    CREATE TABLE IF NOT EXISTS pois(id INTEGER PRIMARY KEY, name TEXT, type TEXT, geometry TEXT);
    """)
    con.commit(); con.close()
