# -*- coding: utf-8 -*-
"""Persistence layer for the independent Social Council module."""

from datetime import datetime


SOCIAL_ISSUE_CATEGORIES = [
    "آسیب‌های اجتماعی", "اعتیاد", "کودکان و نوجوانان", "سالمندان",
    "زنان سرپرست خانوار", "بیکاری و معیشت", "ترک تحصیل",
    "خشونت خانوادگی", "امنیت محله", "سلامت روان",
    "افراد دارای معلولیت", "مشارکت اجتماعی", "مهاجرت و حاشیه‌نشینی", "سایر",
]
SOCIAL_TARGET_GROUPS = [
    "عموم ساکنان", "کودکان", "نوجوانان", "جوانان", "زنان", "سالمندان",
    "خانوارهای کم‌برخوردار", "افراد دارای معلولیت", "مهاجران", "سایر",
]
SOCIAL_CONFIDENTIALITY_LEVELS = ["عمومی", "داخلی", "محرمانه", "فقط مدیر سیستم"]


class SocialCouncilMixin:
    def _create_social_council_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_councils (
                zone_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                formation_date TEXT,
                chair_member_id INTEGER,
                secretary_member_id INTEGER,
                status TEXT DEFAULT 'فعال',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (chair_member_id) REFERENCES social_council_members(id) ON DELETE SET NULL,
                FOREIGN KEY (secretary_member_id) REFERENCES social_council_members(id) ON DELETE SET NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_council_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                person_id INTEGER,
                council_member_id INTEGER,
                full_name TEXT NOT NULL,
                national_code TEXT,
                mobile TEXT,
                role_title TEXT DEFAULT 'عضو شورای اجتماعی',
                representation_type TEXT DEFAULT 'عضو مردمی',
                committee_id INTEGER,
                agency_name TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'فعال',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (person_id) REFERENCES people_registry(id) ON DELETE SET NULL,
                FOREIGN KEY (council_member_id) REFERENCES council_members(id) ON DELETE SET NULL,
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_members_zone ON social_council_members(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_members_person ON social_council_members(person_id)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_council_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                meeting_date TEXT,
                start_time TEXT,
                place_id INTEGER,
                place_source TEXT DEFAULT 'place',
                place_ref_id INTEGER,
                place_name TEXT,
                agenda TEXT,
                attendees TEXT,
                absentees TEXT,
                invitees TEXT,
                minutes_text TEXT,
                attachment_path TEXT,
                status TEXT DEFAULT 'برنامه‌ریزی‌شده',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_meetings_zone_date ON social_council_meetings(zone_id, meeting_date)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                linked_neighborhood_issue_id INTEGER,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'سایر',
                urgency TEXT DEFAULT 'عادی',
                target_group TEXT DEFAULT 'عموم ساکنان',
                affected_people INTEGER DEFAULT 0,
                affected_households INTEGER DEFAULT 0,
                description TEXT,
                evidence TEXT,
                source TEXT DEFAULT 'ثبت شورای اجتماعی',
                responsible_agency TEXT,
                status TEXT DEFAULT 'ثبت اولیه',
                confidentiality TEXT DEFAULT 'داخلی',
                location_text TEXT,
                lat REAL,
                lon REAL,
                due_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_neighborhood_issue_id) REFERENCES neighborhood_issues(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_issues_zone_status ON social_issues(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_issues_confidentiality ON social_issues(confidentiality)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_issue_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL UNIQUE,
                is_system INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for category in SOCIAL_ISSUE_CATEGORIES:
            cur.execute(
                "INSERT OR IGNORE INTO social_issue_categories(title,is_system) VALUES (?,1)",
                (category,),
            )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_issue_committee_links (
                issue_id INTEGER NOT NULL,
                committee_id INTEGER NOT NULL,
                referral_date TEXT,
                referral_note TEXT,
                response_text TEXT,
                status TEXT DEFAULT 'ارجاع‌شده',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(issue_id, committee_id),
                FOREIGN KEY (issue_id) REFERENCES social_issues(id) ON DELETE CASCADE,
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_resolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                zone_id INTEGER NOT NULL,
                issue_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                responsible_agency TEXT,
                responsible_person TEXT,
                due_date TEXT,
                status TEXT DEFAULT 'در انتظار اقدام',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES social_council_meetings(id) ON DELETE SET NULL,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (issue_id) REFERENCES social_issues(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_resolutions_zone_status ON social_resolutions(zone_id, status)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS social_action_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                resolution_id INTEGER,
                issue_id INTEGER,
                title TEXT NOT NULL,
                action_description TEXT,
                responsible_person TEXT,
                responsible_agency TEXT,
                partner_agencies TEXT,
                required_resources TEXT,
                budget_amount REAL DEFAULT 0,
                funding_source TEXT,
                start_date TEXT,
                end_date TEXT,
                progress_percent INTEGER DEFAULT 0,
                status TEXT DEFAULT 'برنامه‌ریزی‌شده',
                delay_reason TEXT,
                final_result TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (resolution_id) REFERENCES social_resolutions(id) ON DELETE SET NULL,
                FOREIGN KEY (issue_id) REFERENCES social_issues(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_social_actions_zone_status ON social_action_plans(zone_id, status)")
        self.conn.commit()
        self._ensure_social_councils_for_all_zones()

    def _ensure_social_councils_for_all_zones(self):
        for zone in self.get_zones():
            self.ensure_social_council(zone["id"])

    def get_social_issue_categories(self):
        """Returns built-in and user-defined social-harm categories in stable order."""
        rows = self.conn.execute(
            "SELECT title FROM social_issue_categories ORDER BY is_system DESC, id"
        ).fetchall()
        return [row[0] for row in rows]

    def add_social_issue_category(self, title):
        """Adds a reusable custom category without duplicating existing values."""
        title = " ".join(str(title or "").split()).strip()
        if not title:
            raise ValueError("عنوان دسته‌بندی نمی‌تواند خالی باشد.")
        existing = self.conn.execute(
            "SELECT id FROM social_issue_categories WHERE TRIM(title)=?", (title,)
        ).fetchone()
        if existing:
            return int(existing[0])
        cur = self.conn.execute(
            "INSERT INTO social_issue_categories(title,is_system) VALUES (?,0)", (title,)
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def ensure_social_council(self, zone_id):
        zone = self.get_zone(zone_id)
        if not zone:
            return None
        self.conn.execute(
            "INSERT OR IGNORE INTO social_councils(zone_id,title,status) VALUES (?,?, 'فعال')",
            (int(zone_id), f"شورای اجتماعی {zone.get('name') or 'بلوک'}"),
        )
        self.conn.commit()
        self.sync_social_council_members(zone_id)
        return self.get_social_council(zone_id)

    def get_social_council(self, zone_id):
        row = self.conn.execute(
            """SELECT zone_id,title,formation_date,chair_member_id,secretary_member_id,status,notes,
                      created_at,updated_at FROM social_councils WHERE zone_id=?""", (int(zone_id),)
        ).fetchone()
        if not row:
            return None
        keys = ["zone_id","title","formation_date","chair_member_id","secretary_member_id","status","notes","created_at","updated_at"]
        return dict(zip(keys, row))

    def update_social_council(self, zone_id, **data):
        self.ensure_social_council(zone_id)
        fields = ["title","formation_date","chair_member_id","secretary_member_id","status","notes"]
        current = self.get_social_council(zone_id) or {}
        values = [data.get(field, current.get(field)) for field in fields]
        self.conn.execute(
            "UPDATE social_councils SET " + ",".join(f"{f}=?" for f in fields) + ",updated_at=CURRENT_TIMESTAMP WHERE zone_id=?",
            values + [int(zone_id)],
        )
        self.conn.commit()
        return True

    def sync_social_council_members(self, zone_id):
        """Non-destructively imports neighborhood trustees and six-committee representatives."""
        zone_id = int(zone_id)
        for member in self.get_council_members(zone_id=zone_id):
            full_name = f"{member.get('first_name') or ''} {member.get('last_name') or ''}".strip()
            if not full_name:
                continue
            exists = self.conn.execute(
                "SELECT id FROM social_council_members WHERE zone_id=? AND council_member_id=?",
                (zone_id, member.get("id")),
            ).fetchone()
            role = member.get("position") or "عضو شورای اجتماعی"
            if exists:
                self.conn.execute(
                    """UPDATE social_council_members SET full_name=?,national_code=?,mobile=?,role_title=?,
                       representation_type='معتمد/شورای محله',status='فعال',updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (full_name, member.get("national_code"), member.get("mobile"), role, exists[0]),
                )
            else:
                self.conn.execute(
                    """INSERT INTO social_council_members
                       (zone_id,person_id,council_member_id,full_name,national_code,mobile,role_title,representation_type,status)
                       VALUES (?,?,?,?,?,?,?,?, 'فعال')""",
                    (zone_id, member.get("person_id"), member.get("id"), full_name, member.get("national_code"),
                     member.get("mobile"), role, "معتمد/شورای محله"),
                )
        committees = self.get_zone_committees(zone_id, ensure=True)
        for committee in committees:
            representative = None
            members = self.get_committee_members(committee["id"])
            representative = next((m for m in members if m.get("is_chair")), None) or \
                             next((m for m in members if m.get("is_secretary")), None) or \
                             next((m for m in members if m.get("status") == "فعال"), None)
            name = (representative or {}).get("person_name") or committee.get("chair_name") or committee.get("secretary_name")
            if not name:
                continue
            existing = self.conn.execute(
                "SELECT id FROM social_council_members WHERE zone_id=? AND committee_id=? AND representation_type='نماینده کمیته'",
                (zone_id, committee["id"]),
            ).fetchone()
            values = (
                name,
                (representative or {}).get("national_code"),
                (representative or {}).get("mobile") or committee.get("chair_mobile") or committee.get("secretary_mobile"),
                f"نماینده {committee.get('title')}",
                (representative or {}).get("agency_name") or "",
            )
            if existing:
                self.conn.execute(
                    """UPDATE social_council_members SET full_name=?,national_code=?,mobile=?,role_title=?,agency_name=?,
                       status='فعال',updated_at=CURRENT_TIMESTAMP WHERE id=?""", values + (existing[0],)
                )
            else:
                self.conn.execute(
                    """INSERT INTO social_council_members
                       (zone_id,person_id,full_name,national_code,mobile,role_title,representation_type,committee_id,agency_name,status)
                       VALUES (?,?,?,?,?,?, 'نماینده کمیته',?,?, 'فعال')""",
                    (zone_id, (representative or {}).get("person_id"), values[0], values[1], values[2], values[3], committee["id"], values[4]),
                )
        self.conn.commit()

    def add_social_council_member(self, zone_id, full_name, national_code="", mobile="", role_title="عضو شورای اجتماعی",
                                  representation_type="عضو مردمی", committee_id=None, agency_name="", start_date=None,
                                  end_date=None, status="فعال", notes=""):
        full_name = (full_name or "").strip()
        if not full_name:
            raise ValueError("نام عضو الزامی است.")
        code = self.normalize_national_code(national_code)
        person_id = None
        if code:
            parts = full_name.split()
            person_id = self.upsert_person(code, first_name=parts[0], last_name=" ".join(parts[1:]), mobile=mobile)
            duplicate = self.conn.execute(
                "SELECT id FROM social_council_members WHERE zone_id=? AND national_code=? AND role_title=?",
                (int(zone_id), code, role_title),
            ).fetchone()
            if duplicate:
                raise ValueError("این شخص با همین نقش قبلاً در شورای اجتماعی ثبت شده است.")
        cur = self.conn.execute(
            """INSERT INTO social_council_members
               (zone_id,person_id,full_name,national_code,mobile,role_title,representation_type,committee_id,
                agency_name,start_date,end_date,status,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(zone_id), person_id, full_name, code, mobile, role_title, representation_type, committee_id,
             agency_name, start_date, end_date, status, notes),
        )
        self.conn.commit()
        self.log_action("social_council_member_added", "social_member", cur.lastrowid, {"zone_id": zone_id})
        return cur.lastrowid

    def update_social_council_member(self, member_id, **data):
        current = self.get_social_council_member(member_id)
        if not current:
            return False
        fields = ["full_name","national_code","mobile","role_title","representation_type","committee_id","agency_name","start_date","end_date","status","notes"]
        merged = {f: data.get(f, current.get(f)) for f in fields}
        merged["national_code"] = self.normalize_national_code(merged.get("national_code"))
        self.conn.execute(
            "UPDATE social_council_members SET " + ",".join(f"{f}=?" for f in fields) + ",updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [merged[f] for f in fields] + [int(member_id)],
        )
        self.conn.commit()
        return True

    def delete_social_council_member(self, member_id):
        self.conn.execute("DELETE FROM social_council_members WHERE id=?", (int(member_id),))
        self.conn.commit()

    def get_social_council_member(self, member_id):
        return next((x for x in self.get_social_council_members() if x["id"] == int(member_id)), None)

    def get_social_council_members(self, zone_id=None, active_only=False):
        sql = """SELECT m.id,m.zone_id,m.person_id,m.council_member_id,m.full_name,m.national_code,m.mobile,
                        m.role_title,m.representation_type,m.committee_id,m.agency_name,m.start_date,m.end_date,
                        m.status,m.notes,m.created_at,m.updated_at,c.title
                 FROM social_council_members m LEFT JOIN neighborhood_committees c ON c.id=m.committee_id"""
        clauses, params = [], []
        if zone_id is not None:
            clauses.append("m.zone_id=?"); params.append(int(zone_id))
        if active_only:
            clauses.append("m.status='فعال'")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE m.role_title WHEN 'رئیس شورا' THEN 0 WHEN 'دبیر شورا' THEN 1 ELSE 2 END,m.full_name"
        keys = ["id","zone_id","person_id","council_member_id","full_name","national_code","mobile","role_title",
                "representation_type","committee_id","agency_name","start_date","end_date","status","notes","created_at","updated_at","committee_title"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def _place_invitee(self, place_id=None, place_source="place", place_ref_id=None):
        source = (place_source or "place").strip()
        ref_id = place_ref_id if place_ref_id is not None else place_id
        if not ref_id:
            return ""
        manager = None
        role = "مسئول مکان"
        if source == "mosque":
            manager = self.get_mosque_imam(str(ref_id)) if hasattr(self, "get_mosque_imam") else None
            role = "امام جماعت"
        elif source == "school":
            manager = self.get_school_manager(int(ref_id)) if hasattr(self, "get_school_manager") else None
            role = "مدیر مدرسه"
        elif source == "health_center":
            manager = self.get_health_center_manager(int(ref_id)) if hasattr(self, "get_health_center_manager") else None
            role = "مسئول مرکز بهداشتی"
        else:
            manager = self.get_place_manager(int(ref_id)) if hasattr(self, "get_place_manager") else None
            role = (manager or {}).get("role_label") or role
        if manager:
            return f"{role}: {manager.get('first_name','')} {manager.get('last_name','')}".strip()
        return ""

    def add_social_meeting(self, zone_id, title, meeting_date=None, start_time=None, place_id=None,
                           place_source="place", place_ref_id=None, place_name="", agenda="", attendees="",
                           absentees="", invitees="", minutes_text="", attachment_path="",
                           status="برنامه‌ریزی‌شده"):
        ref_id = place_ref_id if place_ref_id is not None else place_id
        auto_invitee = self._place_invitee(place_id, place_source, ref_id)
        if auto_invitee and auto_invitee not in (invitees or ""):
            invitees = ((invitees or "").strip() + ("\n" if (invitees or "").strip() else "") + auto_invitee).strip()
        generic_place_id = int(ref_id) if place_source == "place" and ref_id else None
        cur = self.conn.execute(
            """INSERT INTO social_council_meetings
               (zone_id,title,meeting_date,start_time,place_id,place_source,place_ref_id,place_name,agenda,
                attendees,absentees,invitees,minutes_text,attachment_path,status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(zone_id), title, meeting_date, start_time, generic_place_id, place_source, ref_id,
             place_name, agenda, attendees, absentees, invitees, minutes_text, attachment_path, status),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_social_meeting(self, meeting_id, **data):
        current = self.get_social_meeting(meeting_id)
        if not current:
            return False
        fields = ["title","meeting_date","start_time","place_source","place_ref_id","place_name","agenda",
                  "attendees","absentees","invitees","minutes_text","attachment_path","status"]
        merged = {f: data.get(f, current.get(f)) for f in fields}
        auto_invitee = self._place_invitee(None, merged.get("place_source"), merged.get("place_ref_id"))
        if auto_invitee and auto_invitee not in (merged.get("invitees") or ""):
            merged["invitees"] = ((merged.get("invitees") or "").strip() + "\n" + auto_invitee).strip()
        generic_place_id = int(merged["place_ref_id"]) if merged.get("place_source") == "place" and merged.get("place_ref_id") else None
        assignments = [merged[f] for f in fields]
        self.conn.execute(
            "UPDATE social_council_meetings SET " + ",".join(f"{f}=?" for f in fields) +
            ",place_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", assignments + [generic_place_id, int(meeting_id)]
        )
        self.conn.commit()
        return True

    def delete_social_meeting(self, meeting_id):
        self.conn.execute("DELETE FROM social_council_meetings WHERE id=?", (int(meeting_id),))
        self.conn.commit()

    def get_social_meeting(self, meeting_id):
        return next((x for x in self.get_social_meetings() if x["id"] == int(meeting_id)), None)

    def get_social_meetings(self, zone_id=None):
        sql = """SELECT id,zone_id,title,meeting_date,start_time,place_id,place_source,place_ref_id,place_name,
                        agenda,attendees,absentees,invitees,minutes_text,attachment_path,status,created_at,updated_at
                 FROM social_council_meetings"""
        params=[]
        if zone_id is not None:
            sql += " WHERE zone_id=?"; params.append(int(zone_id))
        sql += " ORDER BY COALESCE(meeting_date,created_at) DESC,id DESC"
        keys=["id","zone_id","title","meeting_date","start_time","place_id","place_source","place_ref_id",
              "place_name","agenda","attendees","absentees","invitees","minutes_text","attachment_path",
              "status","created_at","updated_at"]
        return [dict(zip(keys,row)) for row in self.conn.execute(sql,params).fetchall()]

    def add_social_issue(self, zone_id, title, category="سایر", urgency="عادی", target_group="عموم ساکنان",
                         affected_people=0, affected_households=0, description="", evidence="", source="ثبت شورای اجتماعی",
                         responsible_agency="", status="ثبت اولیه", confidentiality="داخلی", location_text="", lat=None,
                         lon=None, due_date=None, mirror_to_neighborhood=True):
        linked_id = None
        if mirror_to_neighborhood:
            urgency_num = {"کم":1,"عادی":3,"زیاد":4,"فوری":5,"بحرانی":5}.get(urgency,3)
            linked_id = self.add_neighborhood_issue(
                zone_id, title, category=category, description=description, related_office=responsible_agency,
                urgency=urgency_num, severity=urgency_num, affected_households=affected_households,
                safety_risk=urgency_num, status=status, source=source, location_text=location_text,
                lat=lat, lon=lon, due_date=due_date,
            )
        cur = self.conn.execute(
            """INSERT INTO social_issues
               (zone_id,linked_neighborhood_issue_id,title,category,urgency,target_group,affected_people,
                affected_households,description,evidence,source,responsible_agency,status,confidentiality,
                location_text,lat,lon,due_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(zone_id), linked_id, title, category, urgency, target_group, int(affected_people or 0),
             int(affected_households or 0), description, evidence, source, responsible_agency, status,
             confidentiality, location_text, lat, lon, due_date),
        )
        self.conn.commit(); return cur.lastrowid

    def update_social_issue(self, issue_id, **data):
        current=self.get_social_issue(issue_id)
        if not current: return False
        fields=["title","category","urgency","target_group","affected_people","affected_households","description","evidence","source","responsible_agency","status","confidentiality","location_text","lat","lon","due_date"]
        merged={f:data.get(f,current.get(f)) for f in fields}
        self.conn.execute("UPDATE social_issues SET "+",".join(f"{f}=?" for f in fields)+",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [merged[f] for f in fields]+[int(issue_id)])
        linked=current.get("linked_neighborhood_issue_id")
        if linked:
            self.update_neighborhood_issue(linked, title=merged["title"], category=merged["category"],
                                           description=merged["description"], related_office=merged["responsible_agency"],
                                           affected_households=merged["affected_households"], status=merged["status"],
                                           location_text=merged["location_text"], lat=merged["lat"], lon=merged["lon"],
                                           due_date=merged["due_date"])
        self.conn.commit(); return True

    def delete_social_issue(self, issue_id):
        current=self.get_social_issue(issue_id)
        self.conn.execute("DELETE FROM social_issues WHERE id=?",(int(issue_id),)); self.conn.commit()
        if current and current.get("linked_neighborhood_issue_id"):
            try: self.delete_neighborhood_issue(current["linked_neighborhood_issue_id"])
            except Exception: pass

    def get_social_issue(self, issue_id):
        return next((x for x in self.get_social_issues() if x["id"]==int(issue_id)),None)

    def get_social_issues(self, zone_id=None, include_confidential=True):
        sql="""SELECT id,zone_id,linked_neighborhood_issue_id,title,category,urgency,target_group,affected_people,
                      affected_households,description,evidence,source,responsible_agency,status,confidentiality,
                      location_text,lat,lon,due_date,created_at,updated_at FROM social_issues"""
        clauses=[]; params=[]
        if zone_id is not None: clauses.append("zone_id=?"); params.append(int(zone_id))
        if not include_confidential: clauses.append("confidentiality IN ('عمومی','داخلی')")
        if clauses: sql += " WHERE "+" AND ".join(clauses)
        sql += " ORDER BY CASE urgency WHEN 'بحرانی' THEN 0 WHEN 'فوری' THEN 1 WHEN 'زیاد' THEN 2 ELSE 3 END,id DESC"
        keys=["id","zone_id","linked_neighborhood_issue_id","title","category","urgency","target_group","affected_people","affected_households","description","evidence","source","responsible_agency","status","confidentiality","location_text","lat","lon","due_date","created_at","updated_at"]
        return [dict(zip(keys,row)) for row in self.conn.execute(sql,params).fetchall()]

    def refer_social_issue(self, issue_id, committee_id, referral_note="", status="ارجاع‌شده"):
        self.conn.execute(
            """INSERT INTO social_issue_committee_links(issue_id,committee_id,referral_date,referral_note,status)
               VALUES (?,?,date('now'),?,?) ON CONFLICT(issue_id,committee_id) DO UPDATE SET
               referral_date=excluded.referral_date,referral_note=excluded.referral_note,status=excluded.status,
               updated_at=CURRENT_TIMESTAMP""", (int(issue_id),int(committee_id),referral_note,status)
        )
        issue=self.get_social_issue(issue_id)
        if issue and issue.get("linked_neighborhood_issue_id"):
            try: self.link_issue_to_committee(committee_id, issue["linked_neighborhood_issue_id"])
            except Exception: pass
        self.conn.commit(); return True

    def update_social_referral(self, issue_id, committee_id, response_text="", status="پاسخ‌داده‌شده"):
        self.conn.execute("UPDATE social_issue_committee_links SET response_text=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE issue_id=? AND committee_id=?",
                          (response_text,status,int(issue_id),int(committee_id))); self.conn.commit()

    def delete_social_referral(self, issue_id, committee_id):
        self.conn.execute("DELETE FROM social_issue_committee_links WHERE issue_id=? AND committee_id=?",(int(issue_id),int(committee_id))); self.conn.commit()

    def get_social_referrals(self, zone_id=None):
        sql="""SELECT l.issue_id,l.committee_id,l.referral_date,l.referral_note,l.response_text,l.status,l.updated_at,
                      i.title,i.urgency,i.confidentiality,c.title,z.name
               FROM social_issue_committee_links l JOIN social_issues i ON i.id=l.issue_id
               JOIN neighborhood_committees c ON c.id=l.committee_id JOIN zones z ON z.id=i.zone_id"""
        params=[]
        if zone_id is not None: sql += " WHERE i.zone_id=?"; params.append(int(zone_id))
        sql += " ORDER BY l.updated_at DESC"
        keys=["issue_id","committee_id","referral_date","referral_note","response_text","status","updated_at","issue_title","urgency","confidentiality","committee_title","zone_name"]
        return [dict(zip(keys,row)) for row in self.conn.execute(sql,params).fetchall()]

    def add_social_resolution(self, zone_id, title, meeting_id=None, issue_id=None, description="", responsible_agency="",
                              responsible_person="", due_date=None, status="در انتظار اقدام"):
        cur=self.conn.execute("""INSERT INTO social_resolutions(meeting_id,zone_id,issue_id,title,description,responsible_agency,
                               responsible_person,due_date,status) VALUES (?,?,?,?,?,?,?,?,?)""",
                              (meeting_id,int(zone_id),issue_id,title,description,responsible_agency,responsible_person,due_date,status))
        self.conn.commit(); return cur.lastrowid

    def update_social_resolution(self,resolution_id,**data):
        current=self.get_social_resolution(resolution_id)
        if not current:return False
        fields=["meeting_id","issue_id","title","description","responsible_agency","responsible_person","due_date","status"]
        merged={f:data.get(f,current.get(f)) for f in fields}
        self.conn.execute("UPDATE social_resolutions SET "+",".join(f"{f}=?" for f in fields)+",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [merged[f] for f in fields]+[int(resolution_id)]);self.conn.commit();return True

    def delete_social_resolution(self,resolution_id):
        self.conn.execute("DELETE FROM social_resolutions WHERE id=?",(int(resolution_id),));self.conn.commit()

    def get_social_resolution(self,resolution_id):
        return next((x for x in self.get_social_resolutions() if x["id"]==int(resolution_id)),None)

    def get_social_resolutions(self,zone_id=None):
        sql="""SELECT r.id,r.meeting_id,r.zone_id,r.issue_id,r.title,r.description,r.responsible_agency,
                      r.responsible_person,r.due_date,r.status,r.created_at,r.updated_at,m.title,i.title,i.confidentiality
               FROM social_resolutions r LEFT JOIN social_council_meetings m ON m.id=r.meeting_id
               LEFT JOIN social_issues i ON i.id=r.issue_id"""
        params=[]
        if zone_id is not None:sql+=" WHERE r.zone_id=?";params.append(int(zone_id))
        sql+=" ORDER BY CASE r.status WHEN 'در انتظار اقدام' THEN 0 WHEN 'در حال پیگیری' THEN 1 ELSE 2 END,r.id DESC"
        keys=["id","meeting_id","zone_id","issue_id","title","description","responsible_agency","responsible_person","due_date","status","created_at","updated_at","meeting_title","issue_title","issue_confidentiality"]
        return [dict(zip(keys,row)) for row in self.conn.execute(sql,params).fetchall()]

    def add_social_action_plan(self,zone_id,title,resolution_id=None,issue_id=None,action_description="",responsible_person="",
                               responsible_agency="",partner_agencies="",required_resources="",budget_amount=0,
                               funding_source="",start_date=None,end_date=None,progress_percent=0,status="برنامه‌ریزی‌شده",
                               delay_reason="",final_result=""):
        progress=max(0,min(100,int(progress_percent or 0)))
        cur=self.conn.execute("""INSERT INTO social_action_plans(zone_id,resolution_id,issue_id,title,action_description,
                              responsible_person,responsible_agency,partner_agencies,required_resources,budget_amount,
                              funding_source,start_date,end_date,progress_percent,status,delay_reason,final_result)
                              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                             (int(zone_id),resolution_id,issue_id,title,action_description,responsible_person,responsible_agency,
                              partner_agencies,required_resources,float(budget_amount or 0),funding_source,start_date,end_date,
                              progress,status,delay_reason,final_result))
        self.conn.commit();return cur.lastrowid

    def update_social_action_plan(self,action_id,**data):
        current=self.get_social_action_plan(action_id)
        if not current:return False
        fields=["resolution_id","issue_id","title","action_description","responsible_person","responsible_agency",
                "partner_agencies","required_resources","budget_amount","funding_source","start_date","end_date",
                "progress_percent","status","delay_reason","final_result"]
        merged={f:data.get(f,current.get(f)) for f in fields};merged["progress_percent"]=max(0,min(100,int(merged["progress_percent"] or 0)))
        self.conn.execute("UPDATE social_action_plans SET "+",".join(f"{f}=?" for f in fields)+",updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [merged[f] for f in fields]+[int(action_id)]);self.conn.commit();return True

    def delete_social_action_plan(self,action_id):
        self.conn.execute("DELETE FROM social_action_plans WHERE id=?",(int(action_id),));self.conn.commit()

    def get_social_action_plan(self,action_id):
        return next((x for x in self.get_social_action_plans() if x["id"]==int(action_id)),None)

    def get_social_action_plans(self,zone_id=None):
        sql="""SELECT a.id,a.zone_id,a.resolution_id,a.issue_id,a.title,a.action_description,a.responsible_person,
                      a.responsible_agency,a.partner_agencies,a.required_resources,a.budget_amount,a.funding_source,
                      a.start_date,a.end_date,a.progress_percent,a.status,a.delay_reason,a.final_result,a.created_at,
                      a.updated_at,r.title,i.title,i.confidentiality FROM social_action_plans a
               LEFT JOIN social_resolutions r ON r.id=a.resolution_id LEFT JOIN social_issues i ON i.id=a.issue_id"""
        params=[]
        if zone_id is not None:sql+=" WHERE a.zone_id=?";params.append(int(zone_id))
        sql+=" ORDER BY CASE a.status WHEN 'در حال اجرا' THEN 0 WHEN 'برنامه‌ریزی‌شده' THEN 1 ELSE 2 END,a.id DESC"
        keys=["id","zone_id","resolution_id","issue_id","title","action_description","responsible_person","responsible_agency","partner_agencies","required_resources","budget_amount","funding_source","start_date","end_date","progress_percent","status","delay_reason","final_result","created_at","updated_at","resolution_title","issue_title","issue_confidentiality"]
        return [dict(zip(keys,row)) for row in self.conn.execute(sql,params).fetchall()]

    def get_social_dashboard(self, zone_id):
        members=self.get_social_council_members(zone_id,active_only=True)
        meetings=self.get_social_meetings(zone_id)
        issues=self.get_social_issues(zone_id)
        referrals=self.get_social_referrals(zone_id)
        resolutions=self.get_social_resolutions(zone_id)
        actions=self.get_social_action_plans(zone_id)
        closed={"مختومه","انجام‌شده","لغوشده","تکمیل‌شده"}
        return {
            "members_count":len(members),"meetings_count":len(meetings),"issues_count":len(issues),
            "open_issues":sum(1 for x in issues if x.get("status") not in closed),
            "critical_issues":sum(1 for x in issues if x.get("urgency") in ("بحرانی","فوری") and x.get("status") not in closed),
            "referrals_open":sum(1 for x in referrals if x.get("status") not in ("مختومه","پاسخ‌داده‌شده")),
            "pending_resolutions":sum(1 for x in resolutions if x.get("status") not in closed),
            "actions_active":sum(1 for x in actions if x.get("status") in ("برنامه‌ریزی‌شده","در حال اجرا")),
            "average_progress":round(sum(int(x.get("progress_percent") or 0) for x in actions)/len(actions),1) if actions else 0,
            "confidential_cases":sum(1 for x in issues if x.get("confidentiality") in ("محرمانه","فقط مدیر سیستم")),
        }

    def get_social_city_summary(self):
        rows=[]
        for zone in self.get_zones():
            data=self.get_social_dashboard(zone["id"])
            data.update({"zone_id":zone["id"],"zone_name":zone.get("name")})
            rows.append(data)
        return rows
