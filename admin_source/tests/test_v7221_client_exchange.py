# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from client_exchange_core import (
    AdminKeyStore, ClientKeyStore, b64e, build_activation_request,
    build_client_package, content_hash,
)
from database import Database


class AdminClientExchangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = Database(str(self.root / "admin.db"))
        self.admin_keys = AdminKeyStore(str(self.root / "admin_keys"))
        self.db._client_key_store = lambda: self.admin_keys
        self.zone_id = self.db.create_zone(
            "بلوک آزمایشی",
            [[34.0000, 46.0000], [34.0000, 46.0100], [34.0100, 46.0100]],
        )
        self.client_keys = ClientKeyStore(str(self.root / "client_keys"))
        request_path = self.root / "request.jrr"
        build_activation_request(str(request_path), "1234567890", self.client_keys)
        request = self.db.import_client_activation_request(str(request_path))
        activation_path = self.root / "activation.jra"
        self.license = self.db.create_client_license(
            request["id"], str(activation_path),
            first_name="علی", last_name="رضایی", national_code="1234567890",
            username="ali", initial_password="Password123", zone_id=self.zone_id,
            committee_code="sports", role_title="مسئول کمیته نشاط و ورزش",
            valid_from="2026-01-01", valid_until="2027-01-01",
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _package(self, path: Path, revision=1, base_hash=None, description="نسخه اول"):
        data = {
            "title": "مصوبه توسعه ورزش محله",
            "description": description,
            "responsible_agency": "اداره ورزش و جوانان",
            "status": "در انتظار اقدام",
        }
        record = {
            "record_uuid": "22222222-2222-4222-8222-222222222222",
            "record_type": "resolution",
            "revision": revision,
            "base_hash": base_hash,
            "content_hash": content_hash(data),
            "created_at": "2026-07-25T08:00:00Z",
            "updated_at": "2026-07-25T08:00:00Z",
            "data": data,
        }
        payload = {
            "license_id": self.license["license_id"],
            "device_id": self.client_keys.device_id,
            "responsible_full_name": "علی رضایی",
            "zone_id": self.zone_id,
            "zone_name": "بلوک آزمایشی",
            "committee_code": "sports",
            "committee_title": "نشاط و ورزش",
            "report_period": "مرداد ۱۴۰۵",
            "created_at": "2026-07-25T08:00:00Z",
            "client_version": "1.0.0",
            "records": [record],
        }
        build_client_package(
            str(path), payload, self.client_keys,
            self.admin_keys.trust_bundle()["exchange_public"],
        )
        return record

    def test_new_duplicate_and_changed_record_workflow(self):
        first_path = self.root / "first.jrcx"
        first = self._package(first_path)
        preview = self.db.preview_client_package(str(first_path))
        self.assertEqual(preview["counts"]["new"], 1)
        result = self.db.apply_client_package(preview, {first["record_uuid"]: "accept"})
        self.assertEqual(result["accepted"], 1)
        with self.assertRaisesRegex(ValueError, "قبلاً"):
            self.db.preview_client_package(str(first_path))

        second_path = self.root / "second.jrcx"
        second = self._package(
            second_path, revision=2, base_hash=first["content_hash"], description="نسخه اصلاح‌شده"
        )
        changed = self.db.preview_client_package(str(second_path))
        self.assertEqual(changed["counts"]["changed"], 1)
        self.db.apply_client_package(changed, {second["record_uuid"]: "accept"})
        row = self.db.conn.execute(
            "SELECT description FROM committee_resolutions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self.assertEqual(row[0], "نسخه اصلاح‌شده")

    def test_scope_is_reported_from_admin_license(self):
        path = self.root / "scope.jrcx"
        self._package(path)
        preview = self.db.preview_client_package(str(path))
        self.assertEqual(preview["zone_name"], "بلوک آزمایشی")
        self.assertEqual(preview["committee_title"], "نشاط و ورزش")
        self.assertEqual(preview["responsible_name"], "علی رضایی")


if __name__ == "__main__":
    unittest.main()
