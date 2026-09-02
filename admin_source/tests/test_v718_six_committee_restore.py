import os
import tempfile
import unittest

from database import Database


class SixCommitteeRestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "app.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_zone_has_exactly_six_committees_in_fixed_order(self):
        db = Database(self.path)
        zone_id = db.create_zone("بلوک شش کمیته", [(34,46),(34,46.1),(34.1,46.1)])
        rows = db.get_zone_committees(zone_id)
        self.assertEqual([r["committee_code"] for r in rows], [
            "infrastructure", "health", "sports", "security", "support", "culture"
        ])
        self.assertEqual(len(rows), 6)
        db.close()

    def test_strategic_committee_data_is_preserved_during_restore(self):
        db = Database(self.path)
        zone_id = db.create_zone("بلوک مهاجرت", [(34,46),(34,46.1),(34.1,46.1)])
        committees = db.get_zone_committees(zone_id)
        for row in committees:
            db.conn.execute("DELETE FROM neighborhood_committees WHERE id=?", (row["id"],))
        cur = db.conn.execute(
            """INSERT INTO neighborhood_committees
               (zone_id, committee_code, title, recommended_agencies, chair_name, status)
               VALUES (?, 'strategic', 'کمیته راهبردی محله', 'فرمانداری', 'رئیس قبلی', 'فعال')""",
            (zone_id,),
        )
        strategic_id = cur.lastrowid
        db.conn.execute(
            """INSERT INTO committee_members
               (committee_id, person_name, member_role, member_type, status)
               VALUES (?, 'عضو قبلی', 'عضو', 'عضو مردمی', 'فعال')""",
            (strategic_id,),
        )
        db.conn.execute("PRAGMA user_version=716")
        db.conn.commit(); db.close()

        upgraded = Database(self.path)
        rows = upgraded.get_zone_committees(zone_id)
        self.assertEqual(len(rows), 6)
        self.assertFalse(any(r["committee_code"] == "strategic" for r in rows))
        infrastructure = rows[0]
        self.assertEqual(infrastructure["chair_name"], "رئیس قبلی")
        members = upgraded.get_committee_members(infrastructure["id"])
        self.assertTrue(any(m["person_name"] == "عضو قبلی" for m in members))
        upgraded.close()


if __name__ == "__main__":
    unittest.main()
