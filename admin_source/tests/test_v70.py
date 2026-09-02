# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from database import Database, SCHEMA_VERSION
from production_health import (
    RuntimeSessionGuard, create_support_bundle, mirror_latest_backup,
    recovery_drill, run_health_checks,
)


class ProductionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "production.db"))
        self.zone_id = self.db.create_zone(
            "بلوک تولید", [(34.80, 46.49), (34.80, 46.50), (34.81, 46.50), (34.81, 46.49)]
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_schema_health_recovery_and_support_bundle(self):
        self.assertEqual(self.db.get_schema_version(), SCHEMA_VERSION)
        self.assertTrue(any(x["version"] == SCHEMA_VERSION for x in self.db.get_migration_history()))
        health = self.db.database_health()
        self.assertTrue(health["integrity_ok"])
        self.assertEqual(health["foreign_key_errors"], 0)

        backup = os.path.join(self.tmp.name, "daily.db")
        self.db.create_backup(backup, backup_type="automatic", reason="daily")
        checks = run_health_checks(self.db)
        self.assertTrue(any(x["name"] == "دیتابیس" and x["status"] == "ok" for x in checks))
        self.assertTrue(any(x["name"] == "بکاپ" and x["status"] == "ok" for x in checks))

        drill = recovery_drill(self.db, os.path.join(self.tmp.name, "drill"))
        self.assertTrue(drill["passed"])
        self.assertEqual(drill["source_counts"], drill["restored_counts"])

        bundle = os.path.join(self.tmp.name, "support.zip")
        create_support_bundle(self.db, bundle, include_database=False)
        with zipfile.ZipFile(bundle) as zf:
            names = set(zf.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("health.json", names)
            self.assertNotIn("database/javanrood.db", names)
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
            self.assertFalse(manifest["contains_database"])

    def test_backup_mirror_checksum_and_session_guard(self):
        source = os.path.join(self.tmp.name, "source.db")
        self.db.create_backup(source, backup_type="manual", reason="mirror test")
        mirrored = mirror_latest_backup(self.db, os.path.join(self.tmp.name, "secondary"))
        self.assertTrue(os.path.exists(mirrored))
        self.assertEqual(self.db._file_sha256(source), self.db._file_sha256(mirrored))

        session_dir = Path(self.tmp.name) / "session"
        session_dir.mkdir()
        with patch("production_health.ensure_runtime_dirs", lambda: session_dir), \
             patch("production_health.get_data_dir", lambda: str(session_dir)):
            first = RuntimeSessionGuard()
            self.assertFalse(first.begin())
            second = RuntimeSessionGuard()
            self.assertTrue(second.begin())
            second.mark_clean()
            third = RuntimeSessionGuard()
            self.assertFalse(third.begin())
            third.mark_clean()


if __name__ == "__main__":
    unittest.main()
