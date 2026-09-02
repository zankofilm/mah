# -*- coding: utf-8 -*-
"""
Mixin مربوط به شورای محلات، امام جماعت/مدارس/مراکز بهداشتی (معتمدین
خودکار بلوک)، تنظیمات پیشنهاد هوشمند، و درخواست‌های اولویت‌بندی.

این فایل بخشی جدا از database.py است که صرفاً برای کاهش حجم آن فایل
(که به بیش از ۸۸۰۰ خط رسیده بود) استخراج شده؛ هیچ تغییری در منطق ایجاد
نشده — کلاس Database از این Mixin ارث‌بری می‌کند و تمام متدها دقیقاً
مثل قبل از طریق self.method() در دسترس‌اند. self.conn (اتصال SQLite
مشترک) توسط Database.__init__ ساخته می‌شود؛ این Mixin به آن متکی است
اما خودش چیزی مقداردهی اولیه نمی‌کند.
"""

from place_types import get_place_role_label


class CouncilFacilitiesMixin:
    # ---------------- Council Members (اعضای شورای محلات) ----------------
    COUNCIL_GROUPS = ["معتمد", "نخبه", "جوان", "ورزشکار", "اداری", "دانشجو", "دانش‌آموز"]

    def add_council_member(self, zone_id, first_name, last_name, national_code,
                            education, mobile, member_group, position):
        code = self.normalize_national_code(national_code)
        if code:
            existing = self.conn.execute(
                "SELECT first_name, last_name FROM council_members WHERE national_code=?",
                (code,)
            ).fetchone()
            if existing:
                raise ValueError(
                    f"این کد ملی قبلاً برای شخص دیگری ثبت شده است: {existing[0]} {existing[1]}"
                )
        person_id = None
        if code:
            person_id = self.upsert_person(code, first_name=first_name, last_name=last_name,
                                           education=education, mobile=mobile)
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO council_members
               (zone_id, person_id, first_name, last_name, national_code, education, mobile, member_group, position)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (zone_id, person_id, first_name, last_name, code, education, mobile, member_group, position)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_council_member(self, member_id, first_name, last_name, national_code,
                               education, mobile, member_group, position):
        code = self.normalize_national_code(national_code)
        if code:
            existing = self.conn.execute(
                "SELECT first_name, last_name FROM council_members WHERE national_code=? AND id<>?",
                (code, member_id)
            ).fetchone()
            if existing:
                raise ValueError(
                    f"این کد ملی قبلاً برای شخص دیگری ثبت شده است: {existing[0]} {existing[1]}"
                )
        person_id = None
        if code:
            person_id = self.upsert_person(code, first_name=first_name, last_name=last_name,
                                           education=education, mobile=mobile)
        cur = self.conn.cursor()
        cur.execute(
            """UPDATE council_members SET
               person_id=?, first_name=?, last_name=?, national_code=?, education=?,
               mobile=?, member_group=?, position=?
               WHERE id=?""",
            (person_id, first_name, last_name, code, education, mobile, member_group, position, member_id)
        )
        self.conn.commit()

    def delete_council_member(self, member_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM council_members WHERE id=?", (member_id,))
        self.conn.commit()

    def get_council_members(self, zone_id=None):
        cur = self.conn.cursor()
        sql = (
            "SELECT id, zone_id, person_id, first_name, last_name, national_code, education, mobile, member_group, position "
            "FROM council_members"
        )
        if zone_id is not None:
            cur.execute(sql + " WHERE zone_id=? ORDER BY created_at ASC", (zone_id,))
        else:
            cur.execute(sql + " ORDER BY created_at ASC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0], "zone_id": r[1], "person_id": r[2], "first_name": r[3], "last_name": r[4],
                "national_code": r[5], "education": r[6], "mobile": r[7],
                "member_group": r[8], "position": r[9]
            })
        return result

    def get_council_member(self, member_id):
        cur = self.conn.execute(
            "SELECT id, zone_id, person_id, first_name, last_name, national_code, education, mobile, member_group, position "
            "FROM council_members WHERE id=?",
            (member_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0], "zone_id": row[1], "person_id": row[2], "first_name": row[3], "last_name": row[4],
            "national_code": row[5], "education": row[6], "mobile": row[7],
            "member_group": row[8], "position": row[9]
        }

    # ---------------- امام جماعت مسجد (ثبت خودکار به‌عنوان معتمد بلوک) ----------------
    def get_mosque_imam(self, mosque_id):
        """اطلاعات امام جماعت ثبت‌شده برای یک مسجد؛ اگر ثبت نشده باشد None برمی‌گرداند."""
        row = self.conn.execute(
            """SELECT mosque_id, zone_id, council_member_id, first_name, last_name, mobile,
                      created_at, updated_at
               FROM mosque_imams WHERE mosque_id=?""",
            (str(mosque_id),)
        ).fetchone()
        if not row:
            return None
        keys = ["mosque_id", "zone_id", "council_member_id", "first_name", "last_name",
                "mobile", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def register_mosque_imam(self, mosque_id, zone_id, first_name, last_name, mobile=""):
        """ثبت امام جماعت یک مسجد و افزودن خودکار او به‌عنوان معتمد همان بلوک.

        اگر این مسجد پیش‌تر امام ثبت‌شده‌ای داشته باشد، خطا می‌دهد؛
        برای تغییر امام موجود باید update_mosque_imam استفاده شود.
        """
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        mobile = (mobile or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی امام جماعت الزامی است.")
        if self.get_mosque_imam(mosque_id):
            raise ValueError("برای این مسجد پیش‌تر امام جماعتی ثبت شده است.")
        mosque = self.conn.execute("SELECT name FROM mosques WHERE id=?", (str(mosque_id),)).fetchone()
        mosque_name = mosque[0] if mosque else "مسجد"

        council_member_id = self.add_council_member(
            zone_id, first_name, last_name, national_code="",
            education="", mobile=mobile, member_group="معتمد",
            position=f"امام جماعت {mosque_name}",
        )
        self.conn.execute(
            """INSERT INTO mosque_imams (mosque_id, zone_id, council_member_id, first_name, last_name, mobile)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(mosque_id), zone_id, council_member_id, first_name, last_name, mobile)
        )
        self.conn.commit()
        return council_member_id

    def update_mosque_imam(self, mosque_id, first_name, last_name, mobile=""):
        """به‌روزرسانی مشخصات امام جماعت یک مسجد، همراه با به‌روزرسانی رکورد معتمد متناظر در شورا."""
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        mobile = (mobile or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی امام جماعت الزامی است.")
        current = self.get_mosque_imam(mosque_id)
        if not current:
            raise ValueError("امام جماعتی برای این مسجد ثبت نشده است.")
        self.conn.execute(
            """UPDATE mosque_imams SET first_name=?, last_name=?, mobile=?, updated_at=CURRENT_TIMESTAMP
               WHERE mosque_id=?""",
            (first_name, last_name, mobile, str(mosque_id))
        )
        self.conn.commit()
        if current.get("council_member_id") and self.get_council_member(current["council_member_id"]):
            member = self.get_council_member(current["council_member_id"])
            self.update_council_member(
                current["council_member_id"], first_name, last_name,
                national_code=member.get("national_code") or "",
                education=member.get("education") or "", mobile=mobile,
                member_group="معتمد", position=member.get("position"),
            )
        return True

    # ---------------- مسئول عمومی همه اماکن (ثبت خودکار به‌عنوان معتمد بلوک) ----------------
    def get_place_manager(self, place_id):
        row = self.conn.execute(
            """SELECT place_id, zone_id, council_member_id, role_label, first_name, last_name, mobile,
                      created_at, updated_at
               FROM place_managers WHERE place_id=?""",
            (int(place_id),),
        ).fetchone()
        if not row:
            return None
        keys = ["place_id", "zone_id", "council_member_id", "role_label", "first_name",
                "last_name", "mobile", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def register_place_manager(self, place_id, zone_id, first_name, last_name, mobile="", role_label=None):
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        mobile = (mobile or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی مسئول مکان الزامی است.")
        if self.get_place_manager(place_id):
            raise ValueError("برای این مکان پیش‌تر مسئولی ثبت شده است.")
        place = self.get_place(place_id) if hasattr(self, "get_place") else None
        if not place:
            raise ValueError("مکان انتخاب‌شده پیدا نشد.")
        role_label = (role_label or get_place_role_label(place.get("subtype"))).strip() or "مسئول مکان"
        council_member_id = self.add_council_member(
            zone_id, first_name, last_name, national_code="", education="", mobile=mobile,
            member_group="معتمد", position=f"{role_label} {place['name']}",
        )
        self.conn.execute(
            """INSERT INTO place_managers
               (place_id, zone_id, council_member_id, role_label, first_name, last_name, mobile)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (int(place_id), zone_id, council_member_id, role_label, first_name, last_name, mobile),
        )
        self.conn.commit()
        return council_member_id

    def update_place_manager(self, place_id, first_name, last_name, mobile="", role_label=None):
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        mobile = (mobile or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی مسئول مکان الزامی است.")
        current = self.get_place_manager(place_id)
        if not current:
            raise ValueError("مسئولی برای این مکان ثبت نشده است.")
        place = self.get_place(place_id) if hasattr(self, "get_place") else None
        role_label = (role_label or current.get("role_label") or get_place_role_label((place or {}).get("subtype"))).strip()
        self.conn.execute(
            """UPDATE place_managers SET first_name=?, last_name=?, mobile=?, role_label=?,
                      updated_at=CURRENT_TIMESTAMP WHERE place_id=?""",
            (first_name, last_name, mobile, role_label, int(place_id)),
        )
        self.conn.commit()
        member_id = current.get("council_member_id")
        member = self.get_council_member(member_id) if member_id else None
        if member:
            self.update_council_member(
                member_id, first_name, last_name, member.get("national_code") or "",
                member.get("education") or "", mobile, "معتمد",
                f"{role_label} {(place or {}).get('name') or 'مکان'}",
            )
        return True

    # ---------------- مدارس و مراکز بهداشتی (ثبت دستی توسط کاربر با مختصات دقیق) ----------------
    # پیاده‌سازی مشترک برای دو نوع مکان (مدرسه، مرکز بهداشتی)؛ هر دو رفتاری کاملاً مشابه
    # مسجد دارند: ثبت مکان با مختصات، سپس ثبت مسؤول که خودکار به‌عنوان معتمد بلوک
    # در شورای محلات ذخیره می‌شود.
    _FACILITY_CONFIG = {
        "school": {
            "table": "schools", "managers_table": "school_managers", "fk": "school_id",
            "role_label": "مدیر مدرسه",
        },
        "health_center": {
            "table": "health_centers", "managers_table": "health_center_managers", "fk": "health_center_id",
            "role_label": "مسؤول مرکز بهداشتی",
        },
    }

    def _add_facility(self, kind, zone_id, name, lat, lon):
        name = (name or "").strip()
        if not name:
            raise ValueError("نام الزامی است.")
        cfg = self._FACILITY_CONFIG[kind]
        cur = self.conn.execute(
            f"INSERT INTO {cfg['table']} (zone_id, name, lat, lon) VALUES (?, ?, ?, ?)",
            (zone_id, name, lat, lon)
        )
        self.conn.commit()
        return cur.lastrowid

    def _get_facilities(self, kind, zone_id=None):
        cfg = self._FACILITY_CONFIG[kind]
        if zone_id is None:
            rows = self.conn.execute(
                f"""SELECT f.id, f.zone_id, f.name, f.lat, f.lon, m.first_name, m.last_name, m.mobile
                    FROM {cfg['table']} f LEFT JOIN {cfg['managers_table']} m ON m.{cfg['fk']}=f.id
                    ORDER BY f.name COLLATE NOCASE"""
            ).fetchall()
        else:
            rows = self.conn.execute(
                f"""SELECT f.id, f.zone_id, f.name, f.lat, f.lon, m.first_name, m.last_name, m.mobile
                    FROM {cfg['table']} f LEFT JOIN {cfg['managers_table']} m ON m.{cfg['fk']}=f.id
                    WHERE f.zone_id=? ORDER BY f.name COLLATE NOCASE""",
                (zone_id,)
            ).fetchall()
        result = []
        for r in rows:
            manager_label = f"{r[5]} {r[6]}".strip() if r[5] else ""
            result.append({
                "id": r[0], "zone_id": r[1], "name": r[2], "lat": r[3], "lon": r[4],
                "manager_label": manager_label, "manager_mobile": (r[7] or "") if r[5] else "",
            })
        return result

    def _get_facility(self, kind, facility_id):
        cfg = self._FACILITY_CONFIG[kind]
        row = self.conn.execute(
            f"SELECT id, zone_id, name, lat, lon FROM {cfg['table']} WHERE id=?", (facility_id,)
        ).fetchone()
        if not row:
            return None
        return {"id": row[0], "zone_id": row[1], "name": row[2], "lat": row[3], "lon": row[4]}

    def _update_facility(self, kind, facility_id, name=None, lat=None, lon=None):
        current = self._get_facility(kind, facility_id)
        if not current:
            return False
        cfg = self._FACILITY_CONFIG[kind]
        new_name = (name if name is not None else current["name"]).strip()
        if not new_name:
            raise ValueError("نام الزامی است.")
        new_lat = lat if lat is not None else current["lat"]
        new_lon = lon if lon is not None else current["lon"]
        self.conn.execute(
            f"UPDATE {cfg['table']} SET name=?, lat=?, lon=? WHERE id=?",
            (new_name, new_lat, new_lon, facility_id)
        )
        self.conn.commit()
        return True

    def _delete_facility(self, kind, facility_id):
        cfg = self._FACILITY_CONFIG[kind]
        self.conn.execute(f"DELETE FROM {cfg['table']} WHERE id=?", (facility_id,))
        self.conn.commit()
        return True

    def _get_facility_manager(self, kind, facility_id):
        cfg = self._FACILITY_CONFIG[kind]
        row = self.conn.execute(
            f"""SELECT {cfg['fk']}, zone_id, council_member_id, first_name, last_name, mobile,
                       created_at, updated_at
                FROM {cfg['managers_table']} WHERE {cfg['fk']}=?""",
            (facility_id,)
        ).fetchone()
        if not row:
            return None
        keys = [cfg['fk'], "zone_id", "council_member_id", "first_name", "last_name",
                "mobile", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def _register_facility_manager(self, kind, facility_id, zone_id, first_name, last_name, mobile=""):
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        mobile = (mobile or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی مسؤول الزامی است.")
        if self._get_facility_manager(kind, facility_id):
            raise ValueError("برای این مکان پیش‌تر مسؤولی ثبت شده است.")
        cfg = self._FACILITY_CONFIG[kind]
        facility = self._get_facility(kind, facility_id)
        facility_name = facility["name"] if facility else cfg["role_label"]

        council_member_id = self.add_council_member(
            zone_id, first_name, last_name, national_code="",
            education="", mobile=mobile, member_group="معتمد",
            position=f"{cfg['role_label']} {facility_name}",
        )
        self.conn.execute(
            f"""INSERT INTO {cfg['managers_table']}
                ({cfg['fk']}, zone_id, council_member_id, first_name, last_name, mobile)
                VALUES (?, ?, ?, ?, ?, ?)""",
            (facility_id, zone_id, council_member_id, first_name, last_name, mobile)
        )
        self.conn.commit()
        return council_member_id

    def _update_facility_manager(self, kind, facility_id, first_name, last_name, mobile=""):
        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        mobile = (mobile or "").strip()
        if not first_name or not last_name:
            raise ValueError("نام و نام خانوادگی مسؤول الزامی است.")
        cfg = self._FACILITY_CONFIG[kind]
        current = self._get_facility_manager(kind, facility_id)
        if not current:
            raise ValueError("مسؤولی برای این مکان ثبت نشده است.")
        self.conn.execute(
            f"""UPDATE {cfg['managers_table']} SET first_name=?, last_name=?, mobile=?,
                updated_at=CURRENT_TIMESTAMP WHERE {cfg['fk']}=?""",
            (first_name, last_name, mobile, facility_id)
        )
        self.conn.commit()
        if current.get("council_member_id") and self.get_council_member(current["council_member_id"]):
            member = self.get_council_member(current["council_member_id"])
            self.update_council_member(
                current["council_member_id"], first_name, last_name,
                national_code=member.get("national_code") or "",
                education=member.get("education") or "", mobile=mobile,
                member_group="معتمد", position=member.get("position"),
            )
        return True

    # --- API عمومی: مدارس ---
    def add_school(self, zone_id, name, lat, lon):
        return self._add_facility("school", zone_id, name, lat, lon)

    def get_schools(self, zone_id=None):
        return self._get_facilities("school", zone_id)

    def get_school(self, school_id):
        return self._get_facility("school", school_id)

    def update_school(self, school_id, name=None, lat=None, lon=None):
        return self._update_facility("school", school_id, name, lat, lon)

    def delete_school(self, school_id):
        return self._delete_facility("school", school_id)

    def get_school_manager(self, school_id):
        return self._get_facility_manager("school", school_id)

    def register_school_manager(self, school_id, zone_id, first_name, last_name, mobile=""):
        return self._register_facility_manager("school", school_id, zone_id, first_name, last_name, mobile)

    def update_school_manager(self, school_id, first_name, last_name, mobile=""):
        return self._update_facility_manager("school", school_id, first_name, last_name, mobile)

    # --- API عمومی: مراکز بهداشتی ---
    def add_health_center(self, zone_id, name, lat, lon):
        return self._add_facility("health_center", zone_id, name, lat, lon)

    def get_health_centers(self, zone_id=None):
        return self._get_facilities("health_center", zone_id)

    def get_health_center(self, health_center_id):
        return self._get_facility("health_center", health_center_id)

    def update_health_center(self, health_center_id, name=None, lat=None, lon=None):
        return self._update_facility("health_center", health_center_id, name, lat, lon)

    def delete_health_center(self, health_center_id):
        return self._delete_facility("health_center", health_center_id)

    def get_health_center_manager(self, health_center_id):
        return self._get_facility_manager("health_center", health_center_id)

    def register_health_center_manager(self, health_center_id, zone_id, first_name, last_name, mobile=""):
        return self._register_facility_manager("health_center", health_center_id, zone_id, first_name, last_name, mobile)

    def update_health_center_manager(self, health_center_id, first_name, last_name, mobile=""):
        return self._update_facility_manager("health_center", health_center_id, first_name, last_name, mobile)

    # ---------------- تنظیمات پیشنهاد هوشمند (smart_triage) ----------------
    def get_smart_triage_settings(self):
        row = self.conn.execute(
            "SELECT enabled, api_url, api_key FROM smart_triage_settings WHERE id=1"
        ).fetchone()
        if not row:
            return {"enabled": False, "api_url": "", "api_key": ""}
        return {"enabled": bool(row[0]), "api_url": row[1] or "", "api_key": self.decrypt_secret(row[2]) if row[2] else ""}

    def set_smart_triage_settings(self, enabled, api_url="", api_key=""):
        self.require_permission("system_settings")
        self.conn.execute(
            """INSERT INTO smart_triage_settings (id, enabled, api_url, api_key, updated_at)
               VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET
                   enabled=excluded.enabled, api_url=excluded.api_url,
                   api_key=excluded.api_key, updated_at=CURRENT_TIMESTAMP""",
            (1 if enabled else 0, (api_url or "").strip(), self.encrypt_secret((api_key or "").strip()))
        )
        self.conn.commit()
        return True

    # ---------------- Priority Requests (اولویت‌بندی مشکلات و درخواست‌ها) ----------------
    def add_priority_request(self, zone_id, description, related_office):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO priority_requests (zone_id, description, related_office) VALUES (?, ?, ?)",
            (zone_id, description, related_office)
        )
        self.conn.commit()
        request_id = cur.lastrowid
        title = (description[:67] + "...") if len(description) > 70 else description
        self.conn.execute(
            """INSERT OR IGNORE INTO neighborhood_issues
               (zone_id, legacy_request_id, title, category, description, related_office, urgency, severity,
                safety_risk, priority_score, priority_level, status, source, updated_at)
               VALUES (?, ?, ?, 'سایر', ?, ?, 3, 3, 1, 42, 'مهم', 'در حال بررسی',
                       'ثبت از ماژول درخواست‌های قدیمی', CURRENT_TIMESTAMP)""",
            (zone_id, request_id, title, description, related_office)
        )
        self.conn.commit()
        return request_id

    def update_priority_request(self, request_id, description=None, related_office=None, status=None):
        cur = self.conn.cursor()
        if description is not None:
            cur.execute("UPDATE priority_requests SET description=? WHERE id=?", (description, request_id))
        if related_office is not None:
            cur.execute("UPDATE priority_requests SET related_office=? WHERE id=?", (related_office, request_id))
        if status is not None:
            cur.execute("UPDATE priority_requests SET status=? WHERE id=?", (status, request_id))
        legacy = cur.execute("SELECT description, related_office, status FROM priority_requests WHERE id=?", (request_id,)).fetchone()
        if legacy:
            title = (legacy[0][:67] + "...") if len(legacy[0]) > 70 else legacy[0]
            cur.execute(
                "UPDATE neighborhood_issues SET title=?, description=?, related_office=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE legacy_request_id=?",
                (title, legacy[0], legacy[1], legacy[2], request_id)
            )
        self.conn.commit()

    def delete_priority_request(self, request_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM neighborhood_issues WHERE legacy_request_id=?", (request_id,))
        cur.execute("DELETE FROM request_actions WHERE request_id=?", (request_id,))
        cur.execute("DELETE FROM priority_requests WHERE id=?", (request_id,))
        self.conn.commit()

    def get_priority_requests(self, zone_id=None):
        cur = self.conn.cursor()
        if zone_id is not None:
            cur.execute(
                "SELECT id, zone_id, description, related_office, status, created_at "
                "FROM priority_requests WHERE zone_id=? ORDER BY created_at ASC", (zone_id,)
            )
        else:
            cur.execute(
                "SELECT id, zone_id, description, related_office, status, created_at "
                "FROM priority_requests ORDER BY created_at ASC"
            )
        rows = cur.fetchall()
        result = []
        for r in rows:
            action_count = self.conn.execute(
                "SELECT COUNT(*) FROM request_actions WHERE request_id=?", (r[0],)
            ).fetchone()[0]
            result.append({
                "id": r[0], "zone_id": r[1], "description": r[2],
                "related_office": r[3], "status": r[4], "created_at": r[5],
                "action_count": action_count
            })
        return result

    def get_priority_request(self, request_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, zone_id, description, related_office, status, created_at "
            "FROM priority_requests WHERE id=?", (request_id,)
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0], "zone_id": r[1], "description": r[2],
            "related_office": r[3], "status": r[4], "created_at": r[5]
        }

    # ---------------- Request Actions (اقدامات انجام‌شده روی هر درخواست) ----------------
    def add_request_action(self, request_id, action_description):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO request_actions (request_id, action_description) VALUES (?, ?)",
            (request_id, action_description)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_request_action(self, action_id, action_description):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE request_actions SET action_description=? WHERE id=?",
            (action_description, action_id)
        )
        self.conn.commit()

    def delete_request_action(self, action_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM request_actions WHERE id=?", (action_id,))
        self.conn.commit()

    def get_request_actions(self, request_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, request_id, action_description, created_at "
            "FROM request_actions WHERE request_id=? ORDER BY created_at ASC", (request_id,)
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "request_id": r[1], "action_description": r[2], "created_at": r[3]}
            for r in rows
        ]
