# -*- coding: utf-8 -*-
import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from client_exchange_core import AdminKeyStore, ClientKeyStore, build_activation_request, build_client_package, content_hash
from database import Database


class ClientMinutesExchangeTests(unittest.TestCase):
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
            committee_code="infrastructure", role_title="مسئول کمیته زیرساخت",
            valid_from="2026-01-01", valid_until="2027-01-01",
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    @staticmethod
    def _signature_data_url():
        image = Image.new("RGBA", (600, 180), "white")
        draw = ImageDraw.Draw(image)
        draw.line([(40, 120), (160, 50), (260, 130), (420, 60), (560, 110)], fill="black", width=8)
        output = io.BytesIO()
        image.save(output, "PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    def test_minutes_resolutions_members_and_signatures_are_imported_together(self):
        member_uuid = "11111111-1111-4111-8111-111111111111"
        meeting_uuid = "22222222-2222-4222-8222-222222222222"
        resolution_uuid = "33333333-3333-4333-8333-333333333333"
        member_data = {"full_name": "علی محمدی", "role": "رئیس کمیته", "member_type": "عضو اداری", "status": "فعال"}
        meeting_data = {
            "title": "صورتجلسه شماره ۱۲", "meeting_number": "12", "meeting_date": "2026-07-30",
            "start_time": "10:30", "discussion_notes": "شرح مذاکرات آزمایشی", "minutes_text": "شرح مذاکرات آزمایشی",
            "status": "برگزار شد", "resolution_uuids": [resolution_uuid],
            "member_signatures": [{
                "member_uuid": member_uuid, "full_name": "علی محمدی", "role": "رئیس کمیته",
                "member_type": "عضو اداری", "signature_data": self._signature_data_url(),
                "signed_at": "2026-07-30T14:00:00Z",
            }],
        }
        resolution_data = {
            "title": "اصلاح روشنایی", "description": "شهرداری روشنایی را اصلاح کند.",
            "responsible_agency": "شهرداری", "due_date": "2026-08-10", "status": "در انتظار اقدام",
            "meeting_uuid": meeting_uuid, "meeting_number": "12", "row_order": 1,
        }

        def record(uuid_value, record_type, data):
            return {
                "record_uuid": uuid_value, "record_type": record_type, "revision": 1, "base_hash": None,
                "content_hash": content_hash(data), "created_at": "2026-07-30T13:00:00Z",
                "updated_at": "2026-07-30T13:00:00Z", "data": data,
            }

        payload = {
            "license_id": self.license["license_id"], "device_id": self.client_keys.device_id,
            "responsible_full_name": "علی رضایی", "zone_id": self.zone_id, "zone_name": "بلوک آزمایشی",
            "committee_code": "infrastructure", "committee_title": "کمیته زیرساخت و خدمات شهری",
            "report_period": "مرداد ۱۴۰۵", "created_at": "2026-07-30T14:10:00Z", "client_version": "pwa-1.0.5",
            "records": [record(resolution_uuid, "resolution", resolution_data), record(meeting_uuid, "meeting", meeting_data), record(member_uuid, "member", member_data)],
        }
        package_path = self.root / "minutes.jrcx"
        build_client_package(str(package_path), payload, self.client_keys, self.admin_keys.trust_bundle()["exchange_public"])
        preview = self.db.preview_client_package(str(package_path))
        result = self.db.apply_client_package(preview)
        self.assertEqual(result["accepted"], 3)

        meeting = self.db.conn.execute(
            "SELECT id,meeting_number,minutes_text,start_time FROM committee_meetings WHERE meeting_number='12'"
        ).fetchone()
        self.assertIsNotNone(meeting)
        self.assertEqual(meeting[1], "12")
        self.assertEqual(meeting[2], "شرح مذاکرات آزمایشی")
        self.assertEqual(meeting[3], "10:30")
        resolution = self.db.conn.execute(
            "SELECT meeting_id,responsible_agency FROM committee_resolutions WHERE title='اصلاح روشنایی'"
        ).fetchone()
        self.assertEqual(resolution[0], meeting[0])
        self.assertEqual(resolution[1], "شهرداری")
        signature = self.db.conn.execute(
            "SELECT signature_png FROM committee_meeting_signatures WHERE meeting_id=?", (meeting[0],)
        ).fetchone()
        self.assertTrue(signature[0].startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
