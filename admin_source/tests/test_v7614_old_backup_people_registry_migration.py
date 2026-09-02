# -*- coding: utf-8 -*-
import os
import sqlite3
import tempfile
import unittest

from database import Database


class OldBackupPeopleRegistryMigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "legacy_backup.db")

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except OSError:
                pass
        self.tmp.cleanup()

    def _prepare_legacy_backup(self, minimal_registry=False):
        db = Database(self.db_path)
        db.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("PRAGMA legacy_alter_table=ON")
        conn.execute("DROP INDEX IF EXISTS uq_people_registry_national_code")
        conn.execute("DROP INDEX IF EXISTS idx_people_registry_name")
        conn.execute("ALTER TABLE people_registry RENAME TO people_registry_current")
        if minimal_registry:
            conn.execute(
                """CREATE TABLE people_registry (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       national_code TEXT,
                       first_name TEXT,
                       last_name TEXT
                   )"""
            )
        else:
            conn.execute(
                """CREATE TABLE people_registry (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       national_code TEXT NOT NULL UNIQUE,
                       first_name TEXT,
                       last_name TEXT,
                       full_name TEXT,
                       education TEXT,
                       mobile TEXT,
                       address TEXT,
                       notes TEXT,
                       created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                       updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                   )"""
            )
        conn.execute("DROP TABLE people_registry_current")
        conn.execute(
            "INSERT INTO zones(name,color,boundary_points) VALUES('بلوک بکاپ','#000000','[]')"
        )
        zone_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO council_members
               (zone_id,first_name,last_name,national_code,education,mobile)
               VALUES(?,?,?,?,?,?)""",
            (zone_id, "علی", "احمدی", "0013546789", "دیپلم", "09120000000"),
        )
        conn.commit()
        conn.close()

    def test_backup_without_hardening_columns_is_upgraded_before_person_migration(self):
        self._prepare_legacy_backup(minimal_registry=False)
        db = Database(self.db_path)
        try:
            columns = {row[1] for row in db.conn.execute("PRAGMA table_info(people_registry)")}
            self.assertTrue(
                {"is_deleted", "deleted_at", "deleted_by", "data_quality_status"}.issubset(columns)
            )
            person = db.conn.execute(
                "SELECT id,national_code,first_name,last_name,is_deleted "
                "FROM people_registry WHERE national_code='0013546789'"
            ).fetchone()
            self.assertIsNotNone(person)
            member = db.conn.execute(
                "SELECT person_id FROM council_members WHERE national_code='0013546789'"
            ).fetchone()
            self.assertEqual(member[0], person[0])
        finally:
            db.close()

    def test_minimal_legacy_registry_gets_all_fields_needed_by_upsert(self):
        self._prepare_legacy_backup(minimal_registry=True)
        db = Database(self.db_path)
        try:
            columns = {row[1] for row in db.conn.execute("PRAGMA table_info(people_registry)")}
            self.assertTrue(
                {
                    "full_name", "education", "mobile", "address", "notes",
                    "created_at", "updated_at", "is_deleted", "data_quality_status",
                }.issubset(columns)
            )
            person = db.conn.execute(
                "SELECT full_name,education,mobile FROM people_registry "
                "WHERE national_code='0013546789'"
            ).fetchone()
            self.assertEqual(person, ("علی احمدی", "دیپلم", "09120000000"))
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
