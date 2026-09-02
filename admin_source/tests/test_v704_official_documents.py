# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from PIL import Image, ImageDraw

from database import Database
from document_service import generate_correspondence_letter_document


class OfficialDocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "app.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_word_pdf_qr_signature_and_automatic_letter_fields(self):
        signature = os.path.join(self.tmp.name, "signature.png")
        img = Image.new("RGBA", (500, 150), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)
        draw.line([(20, 100), (130, 55), (250, 105), (390, 45), (475, 90)], fill=(30, 50, 150, 255), width=5)
        img.save(signature)
        self.db.set_official_signature(signature, "مدیر آزمون", "فرماندار", "https://example.ir/verify")
        zone_id = self.db.create_zone("بلوک آزمون سند", [
            (34.79, 46.48), (34.79, 46.49), (34.80, 46.49), (34.80, 46.48),
        ])
        letter_id = self.db.add_correspondence_letter(
            letter_number="1405/100", direction="صادره", subject="موضوع آزمایشی",
            zone_id=zone_id, sender="فرمانداری", recipient="اداره مقصد",
            letter_date="1405/04/21", description="متن رسمی آزمایشی نامه.",
        )
        docx_path = os.path.join(self.tmp.name, "letter.docx")
        pdf_path = os.path.join(self.tmp.name, "letter.pdf")
        docx_result = generate_correspondence_letter_document(self.db, letter_id, docx_path)
        pdf_result = generate_correspondence_letter_document(self.db, letter_id, pdf_path)
        self.assertTrue(os.path.isfile(docx_path))
        self.assertTrue(os.path.isfile(pdf_path))
        self.assertGreater(os.path.getsize(docx_path), 5000)
        self.assertGreater(os.path.getsize(pdf_path), 5000)
        self.assertEqual(docx_result["verification_token"], pdf_result["verification_token"])
        self.assertTrue(docx_result["verification_payload"].startswith("https://example.ir/verify/"))
        context = self.db.build_document_context(zone_id=zone_id, letter_id=letter_id)
        self.assertEqual(context["letter_number"], "1405/100")
        self.assertEqual(context["letter_date"], "1405/04/21")
        self.assertEqual(context["recipient"], "اداره مقصد")
        self.assertEqual(context["subject"], "موضوع آزمایشی")
        saved = self.db.get_generated_documents(limit=10)
        self.assertEqual(len(saved), 2)
        self.assertTrue(all(docx_result["verification_token"] in item["content"] for item in saved))


if __name__ == "__main__":
    unittest.main()
