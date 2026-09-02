# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
from pathlib import Path

import client_database
import client_license_store
from client_exchange_core import (
    AdminKeyStore, DecryptionError, b64e, build_activation_file,
    build_activation_request, open_client_package, password_hash,
    read_activation_request, validate_package_payload,
)


class ClientSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_license_data_dir = client_license_store.data_dir
        self.old_db_data_dir = client_database.data_dir
        client_license_store.data_dir = lambda: self.root / "client_data"
        client_database.data_dir = lambda: self.root / "client_data"
        self.store = client_license_store.LicenseStore()
        self.admin_keys = AdminKeyStore(str(self.root / "admin_keys"))

    def tearDown(self):
        client_license_store.data_dir = self.old_license_data_dir
        client_database.data_dir = self.old_db_data_dir
        self.tmp.cleanup()

    def _activation(self, valid_from="2026-01-01", valid_until="2027-01-01"):
        payload = {
            "license_id": "11111111-1111-4111-8111-111111111111",
            "responsible_first_name": "علی",
            "responsible_last_name": "رضایی",
            "responsible_full_name": "علی رضایی",
            "username": "ali",
            "password_hash": password_hash("Password123"),
            "zone_id": 12,
            "zone_name": "بلوک ۱۲",
            "committee_code": "sports",
            "committee_title": "نشاط و ورزش",
            "role_title": "مسئول کمیته نشاط و ورزش",
            "permissions": ["committee.read", "committee.write", "committee.export"],
            "device_id": self.store.key_store.device_id,
            "client_sign_public": b64e(self.store.key_store.signing_public_raw()),
            "valid_from": valid_from,
            "valid_until": valid_until,
            "warning_days": 7,
            "allow_renewal": True,
            "status": "فعال",
        }
        path = self.root / "activation.jra"
        build_activation_file(str(path), payload, "1234567890", self.admin_keys)
        return path

    def test_request_is_signed_and_bound_to_device(self):
        path = self.root / "request.jrr"
        build_activation_request(str(path), "1234567890", self.store.key_store)
        data = read_activation_request(str(path))
        self.assertEqual(data["device_id"], self.store.key_store.device_id)
        self.assertEqual(data["client_version"], "1.0.0")

    def test_activation_requires_matching_national_code_and_login(self):
        path = self._activation()
        with self.assertRaises(DecryptionError):
            self.store.install(str(path), "0000000000")
        state = self.store.install(str(path), "1234567890")
        self.assertEqual(state["committee_code"], "sports")
        self.assertTrue(self.store.authenticate("ali", "Password123"))
        self.assertFalse(self.store.authenticate("ali", "wrong-password"))

    def test_local_records_and_export_are_encrypted(self):
        self.store.install(str(self._activation()), "1234567890")
        db = client_database.ClientDatabase(self.store)
        record_id = db.save_record("issue", {
            "title": "کمبود فضای ورزشی",
            "category": "نشاط و ورزش",
            "urgency": 4,
            "severity": 3,
            "affected_households": 40,
            "safety_risk": 1,
        })
        self.assertEqual(db.get_record(record_id)["data"]["title"], "کمبود فضای ورزشی")
        package = self.root / "report.jrcx"
        result = db.export_package(str(package), "مرداد ۱۴۰۵")
        self.assertEqual(result["record_count"], 1)
        self.assertNotIn("کمبود فضای ورزشی", package.read_text(encoding="utf-8"))
        payload = open_client_package(
            str(package), self.admin_keys, b64e(self.store.key_store.signing_public_raw())
        )
        validate_package_payload(payload)
        self.assertEqual(payload["zone_id"], 12)
        self.assertEqual(payload["committee_code"], "sports")
        self.assertEqual(payload["records"][0]["data"]["title"], "کمبود فضای ورزشی")
        db.close()

    def test_expired_license_blocks_access_without_deleting_state(self):
        path = self._activation(valid_from="2020-01-01", valid_until="2020-12-31")
        self.store.install(str(path), "1234567890")
        result = self.store.validate(update_clock=False)
        self.assertEqual(result["status"], "expired")
        self.assertIsNotNone(self.store.load())

    def test_clock_rollback_is_detected(self):
        self.store.install(str(self._activation()), "1234567890")
        state = self.store.load()
        state["last_seen_utc"] = "2099-01-01T00:00:00Z"
        self.store._write_state(state)
        self.assertEqual(self.store.validate(update_clock=False)["status"], "clock_rollback")


if __name__ == "__main__":
    unittest.main()
