# -*- coding: utf-8 -*-
"""Central person registry, identity normalization and propagation."""
import re


class PeopleRegistryMixin:
    # ---------------- پرونده مشترک اشخاص ----------------
    @staticmethod
    def normalize_national_code(value):
        """کد ملی را به ده رقم لاتین استاندارد تبدیل می‌کند."""
        if value is None:
            return ""
        trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        return re.sub(r"\D", "", str(value).translate(trans))

    @classmethod
    def validate_national_code(cls, value, checksum=True):
        code = cls.normalize_national_code(value)
        if len(code) != 10:
            return False
        if len(set(code)) == 1:
            return False
        if not checksum:
            return True
        try:
            total = sum(int(code[i]) * (10 - i) for i in range(9))
            remainder = total % 11
            check = int(code[9])
            return check == (remainder if remainder < 2 else 11 - remainder)
        except Exception:
            return False

    @staticmethod
    def _split_person_name(full_name):
        parts = [part for part in str(full_name or "").strip().split() if part]
        if not parts:
            return "", ""
        if len(parts) == 1:
            return parts[0], ""
        return parts[0], " ".join(parts[1:])

    def get_person(self, person_id):
        row = self.conn.execute(
            """SELECT id,national_code,first_name,last_name,full_name,education,mobile,address,notes,
                      created_at,updated_at FROM people_registry WHERE id=?""", (person_id,)
        ).fetchone()
        if not row:
            return None
        keys = ["id","national_code","first_name","last_name","full_name","education","mobile","address","notes","created_at","updated_at"]
        return dict(zip(keys, row))

    def find_person_by_national_code(self, national_code):
        """جستجو در پرونده اشخاص و در صورت نیاز بازیابی از اعضای قدیمی شورا/کمیته."""
        code = self.normalize_national_code(national_code)
        if not code:
            return None
        row = self.conn.execute(
            """SELECT id,national_code,first_name,last_name,full_name,education,mobile,address,notes,
                      created_at,updated_at FROM people_registry WHERE national_code=? AND COALESCE(is_deleted,0)=0""", (code,)
        ).fetchone()
        if row:
            keys = ["id","national_code","first_name","last_name","full_name","education","mobile","address","notes","created_at","updated_at"]
            person = dict(zip(keys, row))
            person["source"] = "people_registry"
            return person

        # سازگاری با اطلاعاتی که پیش از نسخه ۷.۱.۱۴ ثبت شده‌اند.
        council_rows = self.conn.execute(
            "SELECT id,first_name,last_name,national_code,education,mobile FROM council_members WHERE national_code IS NOT NULL"
        ).fetchall()
        for member_id, first_name, last_name, raw_code, education, mobile in council_rows:
            if self.normalize_national_code(raw_code) == code:
                person_id = self.upsert_person(code, first_name=first_name, last_name=last_name,
                                               education=education, mobile=mobile, propagate=False)
                self.conn.execute("UPDATE council_members SET person_id=?, national_code=? WHERE id=?",
                                  (person_id, code, member_id))
                self.conn.commit()
                person = self.get_person(person_id)
                person["source"] = "council_members"
                return person

        committee_rows = self.conn.execute(
            "SELECT id,person_name,national_code,mobile FROM committee_members WHERE national_code IS NOT NULL"
        ).fetchall()
        for member_id, person_name, raw_code, mobile in committee_rows:
            if self.normalize_national_code(raw_code) == code:
                first_name, last_name = self._split_person_name(person_name)
                person_id = self.upsert_person(code, first_name=first_name, last_name=last_name,
                                               full_name=person_name, mobile=mobile, propagate=False)
                self.conn.execute("UPDATE committee_members SET person_id=?, national_code=? WHERE id=?",
                                  (person_id, code, member_id))
                self.conn.commit()
                person = self.get_person(person_id)
                person["source"] = "committee_members"
                return person
        return None

    def upsert_person(self, national_code, first_name="", last_name="", full_name="",
                      education="", mobile="", address="", notes="", propagate=True):
        code = self.normalize_national_code(national_code)
        if len(code) != 10:
            raise ValueError("کد ملی باید دقیقاً ۱۰ رقم باشد.")
        mobile = self.normalize_mobile_number(mobile) if mobile else ""
        mobile_valid = (not mobile) or self.validate_mobile_number(mobile)
        quality_status = "تأییدشده" if self.validate_national_code(code, checksum=True) and mobile_valid else "نیازمند بازبینی"
        first_name = str(first_name or "").strip()
        last_name = str(last_name or "").strip()
        full_name = str(full_name or "").strip()
        if not full_name:
            full_name = " ".join(part for part in (first_name, last_name) if part).strip()
        if full_name and not first_name and not last_name:
            first_name, last_name = self._split_person_name(full_name)

        current = self.conn.execute(
            "SELECT id,first_name,last_name,full_name,education,mobile,address,notes FROM people_registry WHERE national_code=? AND COALESCE(is_deleted,0)=0",
            (code,),
        ).fetchone()
        if current:
            person_id = current[0]
            merged = {
                "first_name": first_name or current[1] or "",
                "last_name": last_name or current[2] or "",
                "full_name": full_name or current[3] or "",
                "education": str(education or "").strip() or current[4] or "",
                "mobile": str(mobile or "").strip() or current[5] or "",
                "address": str(address or "").strip() or current[6] or "",
                "notes": str(notes or "").strip() or current[7] or "",
            }
            self.conn.execute(
                """UPDATE people_registry SET first_name=?,last_name=?,full_name=?,education=?,mobile=?,
                          address=?,notes=?,data_quality_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (merged["first_name"], merged["last_name"], merged["full_name"], merged["education"],
                 merged["mobile"], merged["address"], merged["notes"], quality_status, person_id),
            )
        else:
            cur = self.conn.execute(
                """INSERT INTO people_registry
                   (national_code,first_name,last_name,full_name,education,mobile,address,notes,data_quality_status)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (code, first_name, last_name, full_name, str(education or "").strip(),
                 mobile, str(address or "").strip(), str(notes or "").strip(), quality_status),
            )
            person_id = cur.lastrowid

        if propagate:
            person = self.get_person(person_id)
            combined = person.get("full_name") or " ".join(
                part for part in (person.get("first_name"), person.get("last_name")) if part
            )
            self.conn.execute(
                """UPDATE council_members SET first_name=?,last_name=?,national_code=?,education=?,mobile=?
                   WHERE person_id=?""",
                (person.get("first_name") or "", person.get("last_name") or "", code,
                 person.get("education") or "", person.get("mobile") or "", person_id),
            )
            self.conn.execute(
                """UPDATE committee_members SET person_name=?,national_code=?,mobile=?,updated_at=CURRENT_TIMESTAMP
                   WHERE person_id=?""",
                (combined, code, person.get("mobile") or "", person_id),
            )
        self.conn.commit()
        return person_id

    def _migrate_people_registry(self):
        """پرونده مشترک را از اعضای قدیمی شورا و کمیته بدون حذف داده می‌سازد."""
        try:
            for row in self.conn.execute(
                "SELECT id,first_name,last_name,national_code,education,mobile FROM council_members"
            ).fetchall():
                member_id, first_name, last_name, code, education, mobile = row
                normalized = self.normalize_national_code(code)
                if not normalized:
                    continue
                person_id = self.upsert_person(normalized, first_name=first_name, last_name=last_name,
                                               education=education, mobile=mobile, propagate=False)
                self.conn.execute("UPDATE council_members SET person_id=?,national_code=? WHERE id=?",
                                  (person_id, normalized, member_id))
            for row in self.conn.execute(
                "SELECT id,person_name,national_code,mobile FROM committee_members"
            ).fetchall():
                member_id, full_name, code, mobile = row
                normalized = self.normalize_national_code(code)
                if not normalized:
                    continue
                first_name, last_name = self._split_person_name(full_name)
                person_id = self.upsert_person(normalized, first_name=first_name, last_name=last_name,
                                               full_name=full_name, mobile=mobile, propagate=False)
                self.conn.execute("UPDATE committee_members SET person_id=?,national_code=? WHERE id=?",
                                  (person_id, normalized, member_id))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

