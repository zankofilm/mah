# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from database import Database
from message_system import BlockMessagingService


class V730HardeningReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "javanrood.db")
        self.db = Database(self.db_path)
        self.admin = self.db.authenticate_user("admin", "admin123")
        self.assertIsNotNone(self.admin)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_api_keys_are_encrypted_at_rest_and_decrypted_for_runtime(self):
        self.db.set_message_api_settings(True, "generic_json", "https://example.test/send", "TopSecretKey", "1000", 10)
        raw = self.db.conn.execute("SELECT api_key FROM message_api_settings WHERE id=1").fetchone()[0]
        self.assertTrue(raw.startswith("enc:v1:"))
        self.assertNotIn("TopSecretKey", raw)
        self.assertEqual(self.db.get_message_api_settings()["api_key"], "TopSecretKey")

        self.db.set_smart_triage_settings(True, "https://example.test/ai", "AI-Secret")
        raw_ai = self.db.conn.execute("SELECT api_key FROM smart_triage_settings WHERE id=1").fetchone()[0]
        self.assertTrue(raw_ai.startswith("enc:v1:"))
        self.assertEqual(self.db.get_smart_triage_settings()["api_key"], "AI-Secret")

    def test_encrypted_backup_round_trip_and_health(self):
        self.db.create_zone("بلوک امن", [(0, 0), (0, 1), (1, 1), (1, 0)])
        encrypted = os.path.join(self.tmp.name, "secure.jrbak")
        restored = os.path.join(self.tmp.name, "restored.db")
        self.db.create_encrypted_backup(encrypted, "SecureBackup#2026")
        self.assertTrue(os.path.exists(encrypted))
        self.assertNotEqual(open(encrypted, "rb").read(16), open(self.db_path, "rb").read(16))
        self.db.decrypt_backup_to_database(encrypted, restored, "SecureBackup#2026")
        valid, _ = self.db.validate_database_file(restored)
        self.assertTrue(valid)
        self.assertIn(self.db.backup_health_status()["status"], {"سالم", "نیازمند بررسی"})

    def test_message_idempotency_retry_and_delivery_receipt(self):
        zone_id = self.db.create_zone("بلوک پیام", [(0, 0), (0, 1), (1, 1), (1, 0)])
        self.db.set_message_api_settings(True, "demo", "", "", "", 10)
        service = BlockMessagingService(self.db)
        recipients = [{"name": "عضو اول", "mobile": "09120000000", "source_type": "manual", "source_id": 1}]
        summary = service.send_to_recipients(zone_id, "جلسه", "زمان جلسه اعلام شد", recipients)
        self.assertEqual(summary["success"], 1)
        with self.assertRaises(ValueError):
            service.send_to_recipients(zone_id, "جلسه", "زمان جلسه اعلام شد", recipients)
        delivery = self.db.get_message_deliveries(summary["campaign_id"])[0]
        self.assertGreaterEqual(delivery["attempt_count"], 1)
        self.assertEqual(self.db.update_delivery_receipt(delivery["provider_message_id"], True), 1)
        self.assertEqual(self.db.get_message_deliveries(summary["campaign_id"])[0]["delivery_status"], "تحویل‌شده")

    def test_soft_delete_duplicate_detection_and_merge_history(self):
        first = self.db.upsert_person("1234567890", full_name="علی رضایی", mobile="09121111111")
        second = self.db.upsert_person("1111111111", full_name="علی رضایی", mobile="09121111111")
        duplicates = self.db.find_possible_duplicate_people()
        self.assertTrue(any({x["source_id"], x["target_id"]} == {first, second} for x in duplicates))
        self.db.merge_people(first, second)
        deleted = self.db.conn.execute("SELECT is_deleted FROM people_registry WHERE id=?", (first,)).fetchone()[0]
        self.assertEqual(deleted, 1)
        self.assertEqual(self.db.conn.execute("SELECT COUNT(*) FROM data_merge_history").fetchone()[0], 1)

    def test_strong_password_policy_is_enforced(self):
        with self.assertRaises(ValueError):
            self.db.create_user("weakuser", "کاربر ضعیف", "1234567890", role="viewer")
        user_id = self.db.create_user("secureuser", "کاربر امن", "N0rmaL#Pass2026", role="viewer")
        self.assertTrue(user_id)


if __name__ == "__main__":
    unittest.main()
