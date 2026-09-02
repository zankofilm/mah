import os, tempfile, unittest, sqlite3, json
from database import Database

class CommitteeStructureTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Database(os.path.join(self.tmp.name,'app.db'))
        self.zone_id=self.db.create_zone('بلوک کمیته',[(34.0,46.0),(34.0,46.1),(34.1,46.1)])
    def tearDown(self):
        self.db.close(); self.tmp.cleanup()
    def test_full_committee_cycle(self):
        committees=self.db.get_zone_committees(self.zone_id)
        self.assertEqual(len(committees),6)
        cid=committees[0]['id']
        member=self.db.add_committee_member(cid,'کارشناس شهرداری',member_type='نماینده دستگاه',agency_name='شهرداری جوانرود',is_chair=True,status='فعال')
        self.assertEqual(self.db.get_committee_member(member)['person_name'],'کارشناس شهرداری')
        issue=self.db.add_neighborhood_issue(self.zone_id,'آسفالت معبر',category='عمران')
        action=self.db.add_neighborhood_action(self.zone_id,'اصلاح آسفالت',issue_id=issue,status='در حال اجرا')
        self.db.link_committee_issue(cid,issue); self.db.link_committee_action(cid,action)
        self.assertEqual(len(self.db.get_committee_issues(cid)),1)
        self.assertEqual(len(self.db.get_committee_actions(cid)),1)
        meeting=self.db.add_committee_meeting(cid,self.zone_id,'جلسه عمران',meeting_date='2026-07-20')
        resolution=self.db.add_committee_resolution(cid,self.zone_id,'پیگیری آسفالت',meeting_id=meeting,linked_issue_id=issue,linked_action_id=action)
        self.assertEqual(len(self.db.get_committee_resolutions(cid)),1)
        self.db.update_committee_resolution_status(resolution,'انجام‌شده')
        self.assertEqual(self.db.get_committee_resolutions(cid)[0]['status'],'انجام‌شده')
        self.db.delete_zone(self.zone_id)
        self.assertEqual(self.db.conn.execute('SELECT COUNT(*) FROM neighborhood_committees WHERE zone_id=?',(self.zone_id,)).fetchone()[0],0)
    def test_upgrade_existing_zone_and_search(self):
        path=os.path.join(self.tmp.name,'legacy.db')
        legacy=Database(path)
        zid=legacy.create_zone('بلوک قدیمی',[(34,46),(34,46.1),(34.1,46.1)])
        legacy.conn.execute('DROP TABLE committee_meeting_signatures')
        legacy.conn.execute('DROP TABLE committee_action_links')
        legacy.conn.execute('DROP TABLE committee_issue_links')
        legacy.conn.execute('DROP TABLE committee_resolutions')
        legacy.conn.execute('DROP TABLE committee_meetings')
        legacy.conn.execute('DROP TABLE committee_members')
        legacy.conn.execute('DROP TABLE neighborhood_committees')
        legacy.conn.execute('DROP TABLE county_steering_members')
        legacy.conn.execute('PRAGMA user_version=700')
        legacy.conn.commit(); legacy.close()
        upgraded=Database(path)
        committees=upgraded.get_zone_committees(zid)
        self.assertEqual(len(committees),6)
        results=upgraded.global_search('بهداشت')
        self.assertTrue(any(x['entity_type']=='committee' for x in results))
        upgraded.close()

    def test_county_steering_defaults(self):
        members=self.db.get_county_steering_members()
        self.assertEqual(len(members),6)
        governor=members[0]
        self.db.update_county_steering_member(governor['id'],person_name='فرماندار نمونه',mobile='09120000000')
        self.assertEqual(self.db.get_county_steering_members()[0]['person_name'],'فرماندار نمونه')

if __name__=='__main__': unittest.main()
