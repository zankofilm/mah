# -*- coding: utf-8 -*-
"""
Mixin مربوط به کنترل پروژه (برنامه‌های سالانه، پروژه‌ها، نقاط عطف،
شاخص‌ها، ریسک‌ها، درخواست‌های تغییر) و مدیریت قراردادها (پیمانکاران،
قراردادها، پرداخت‌ها، رضایت‌سنجی، مشارکت مردمی).

این فایل بخشی جدا از database.py است که صرفاً برای کاهش حجم آن فایل
استخراج شده؛ هیچ تغییری در منطق ایجاد نشده — کلاس Database از این
Mixin (در کنار سایر Mixin ها) ارث‌بری می‌کند و تمام متدها دقیقاً مثل
قبل از طریق self.method() در دسترس‌اند. self.conn (اتصال SQLite
مشترک) توسط Database.__init__ ساخته می‌شود؛ این Mixin به آن متکی است
اما خودش چیزی مقداردهی اولیه نمی‌کند.
"""


from datetime import datetime, timedelta


class ProjectContractsMixin:
    # ---------------- Project Control v6.7 ----------------
    PROGRAM_STATUSES = ["پیش‌نویس", "مصوب", "در حال اجرا", "متوقف", "تکمیل‌شده", "مختومه"]
    PROJECT_STATUSES = ["برنامه‌ریزی‌شده", "در حال اجرا", "متوقف", "تکمیل‌شده", "لغوشده"]
    PROJECT_PRIORITIES = ["کم", "عادی", "مهم", "فوری", "بحرانی"]
    MILESTONE_STATUSES = ["در انتظار", "در حال انجام", "تکمیل‌شده", "لغوشده"]
    RISK_CATEGORIES = ["مالی", "زمانی", "اجرایی", "حقوقی", "اجتماعی", "فنی", "تأمین", "امنیتی", "سایر"]
    RISK_STATUSES = ["باز", "در حال کنترل", "محقق‌شده", "بسته‌شده"]
    CHANGE_TYPES = ["دامنه", "زمان", "بودجه", "مسئول", "شاخص", "فنی", "سایر"]
    CHANGE_STATUSES = ["در انتظار بررسی", "تأییدشده", "ردشده", "اعمال‌شده", "لغوشده"]

    @staticmethod
    def calculate_risk_level(probability, impact):
        probability = max(1, min(5, int(probability or 1)))
        impact = max(1, min(5, int(impact or 1)))
        score = probability * impact
        if score >= 20:
            level = "بحرانی"
        elif score >= 12:
            level = "زیاد"
        elif score >= 6:
            level = "متوسط"
        else:
            level = "کم"
        return score, level

    @staticmethod
    def calculate_indicator_achievement(baseline, target, actual, direction="افزایشی"):
        baseline = float(baseline or 0)
        target = float(target or 0)
        actual = float(actual or 0)
        if direction == "کاهشی":
            denominator = baseline - target
            if denominator <= 0:
                return 100.0 if actual <= target else 0.0
            value = ((baseline - actual) / denominator) * 100.0
        else:
            denominator = target - baseline
            if denominator <= 0:
                return 100.0 if actual >= target else 0.0
            value = ((actual - baseline) / denominator) * 100.0
        return max(0.0, min(200.0, round(value, 2)))

    def add_annual_program(self, fiscal_year, title, strategic_goal="", zone_id=None,
                           responsible_agency="", program_manager="", start_date=None,
                           end_date=None, approved_budget=0, weight=1, progress_percent=0,
                           status="پیش‌نویس", description=""):
        if not str(fiscal_year or "").strip() or not str(title or "").strip():
            raise ValueError("سال مالی و عنوان برنامه الزامی است.")
        if start_date and end_date and str(end_date) < str(start_date):
            raise ValueError("تاریخ پایان برنامه نمی‌تواند قبل از تاریخ شروع باشد.")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO annual_operational_programs
               (fiscal_year,title,strategic_goal,zone_id,responsible_agency,program_manager,
                start_date,end_date,approved_budget,weight,progress_percent,status,description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (str(fiscal_year).strip(), str(title).strip(), strategic_goal or "", zone_id,
             responsible_agency or "", program_manager or "", start_date, end_date,
             float(approved_budget or 0), float(weight or 1), float(progress_percent or 0),
             status or "پیش‌نویس", description or ""),
        )
        program_id = cur.lastrowid
        self.conn.commit()
        self.log_action("create", "annual_program", program_id,
                        {"title": title, "fiscal_year": fiscal_year, "zone_id": zone_id}, zone_id=zone_id)
        return program_id

    def get_annual_program(self, program_id):
        row = self.conn.execute(
            """SELECT p.*, z.name AS zone_name
               FROM annual_operational_programs p LEFT JOIN zones z ON z.id=p.zone_id
               WHERE p.id=?""", (int(program_id),)
        ).fetchone()
        if not row:
            return None
        keys = [c[0] for c in self.conn.execute(
            """SELECT p.*, z.name AS zone_name
               FROM annual_operational_programs p LEFT JOIN zones z ON z.id=p.zone_id LIMIT 0"""
        ).description]
        return dict(zip(keys, row))

    def get_annual_programs(self, fiscal_year=None, zone_id=None, status=None):
        clauses, params = [], []
        if fiscal_year:
            clauses.append("p.fiscal_year=?"); params.append(str(fiscal_year))
        if zone_id is not None:
            clauses.append("p.zone_id=?"); params.append(int(zone_id))
        if status:
            clauses.append("p.status=?"); params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        sql = """SELECT p.*, z.name AS zone_name,
                    (SELECT COUNT(*) FROM project_portfolio pr WHERE pr.program_id=p.id) AS project_count,
                    (SELECT COALESCE(SUM(pr.planned_budget),0) FROM project_portfolio pr WHERE pr.program_id=p.id) AS projects_budget,
                    (SELECT COALESCE(SUM(pr.actual_cost),0) FROM project_portfolio pr WHERE pr.program_id=p.id) AS projects_cost
                 FROM annual_operational_programs p LEFT JOIN zones z ON z.id=p.zone_id""" + where + \
              " ORDER BY p.fiscal_year DESC, p.id DESC"
        cur = self.conn.execute(sql, params)
        keys = [c[0] for c in cur.description]
        return [dict(zip(keys, row)) for row in cur.fetchall()]

    def update_annual_program(self, program_id, **changes):
        before = self.get_annual_program(program_id)
        if not before:
            raise ValueError("برنامه پیدا نشد.")
        allowed = {"fiscal_year", "title", "strategic_goal", "zone_id", "responsible_agency",
                   "program_manager", "start_date", "end_date", "approved_budget", "weight",
                   "progress_percent", "status", "description"}
        values = {k: v for k, v in changes.items() if k in allowed}
        if not values:
            return False
        start = values.get("start_date", before.get("start_date"))
        end = values.get("end_date", before.get("end_date"))
        if start and end and str(end) < str(start):
            raise ValueError("تاریخ پایان برنامه نمی‌تواند قبل از تاریخ شروع باشد.")
        values["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = "UPDATE annual_operational_programs SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?"
        self.conn.execute(sql, list(values.values()) + [int(program_id)])
        self.conn.commit()
        after = self.get_annual_program(program_id)
        self.log_action("update", "annual_program", program_id, {"title": after.get("title")},
                        zone_id=after.get("zone_id"), before=before, after=after)
        return True

    def delete_annual_program(self, program_id):
        before = self.get_annual_program(program_id)
        if not before:
            return False
        self.conn.execute("DELETE FROM annual_operational_programs WHERE id=?", (int(program_id),))
        self.conn.commit()
        self.log_action("delete", "annual_program", program_id, {"title": before.get("title")},
                        zone_id=before.get("zone_id"), before=before)
        return True

    def _next_project_code(self):
        prefix = datetime.now().strftime("PRJ-%Y")
        row = self.conn.execute(
            "SELECT project_code FROM project_portfolio WHERE project_code LIKE ? ORDER BY id DESC LIMIT 1",
            (prefix + "-%",)
        ).fetchone()
        number = 1
        if row and row[0]:
            try:
                number = int(str(row[0]).rsplit("-", 1)[-1]) + 1
            except Exception:
                number = 1
        return f"{prefix}-{number:04d}"

    def add_project(self, title, program_id=None, zone_id=None, project_code=None,
                    responsible_agency="", project_manager="", start_date=None, end_date=None,
                    actual_start_date=None, actual_end_date=None, planned_budget=0, actual_cost=0,
                    planned_progress=0, actual_progress=0, priority="عادی",
                    status="برنامه‌ریزی‌شده", description=""):
        if not str(title or "").strip():
            raise ValueError("عنوان پروژه الزامی است.")
        if start_date and end_date and str(end_date) < str(start_date):
            raise ValueError("تاریخ پایان پروژه نمی‌تواند قبل از تاریخ شروع باشد.")
        code = str(project_code or "").strip() or self._next_project_code()
        try:
            cur = self.conn.cursor()
            cur.execute(
                """INSERT INTO project_portfolio
                   (program_id,zone_id,project_code,title,responsible_agency,project_manager,
                    start_date,end_date,actual_start_date,actual_end_date,planned_budget,actual_cost,
                    planned_progress,actual_progress,priority,status,description)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (program_id, zone_id, code, str(title).strip(), responsible_agency or "",
                 project_manager or "", start_date, end_date, actual_start_date, actual_end_date,
                 float(planned_budget or 0), float(actual_cost or 0), float(planned_progress or 0),
                 float(actual_progress or 0), priority or "عادی", status or "برنامه‌ریزی‌شده",
                 description or ""),
            )
        except sqlite3.IntegrityError as exc:
            if "project_code" in str(exc):
                raise ValueError("کد پروژه تکراری است.") from exc
            raise
        project_id = cur.lastrowid
        self.conn.commit()
        self.log_action("create", "project", project_id, {"title": title, "code": code, "zone_id": zone_id}, zone_id=zone_id)
        self._recalculate_program_progress(program_id)
        return project_id

    def get_project(self, project_id):
        cur = self.conn.execute(
            """SELECT pr.*, p.title AS program_title, p.fiscal_year, z.name AS zone_name
               FROM project_portfolio pr
               LEFT JOIN annual_operational_programs p ON p.id=pr.program_id
               LEFT JOIN zones z ON z.id=pr.zone_id WHERE pr.id=?""", (int(project_id),)
        )
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None

    def get_projects(self, program_id=None, zone_id=None, status=None, query=None):
        clauses, params = [], []
        if program_id is not None:
            clauses.append("pr.program_id=?"); params.append(int(program_id))
        if zone_id is not None:
            clauses.append("pr.zone_id=?"); params.append(int(zone_id))
        if status:
            clauses.append("pr.status=?"); params.append(status)
        if query:
            clauses.append("(pr.title LIKE ? OR pr.project_code LIKE ? OR pr.project_manager LIKE ? OR pr.responsible_agency LIKE ?)")
            q = f"%{query}%"; params.extend([q, q, q, q])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cur = self.conn.execute(
            """SELECT pr.*, p.title AS program_title, p.fiscal_year, z.name AS zone_name,
                      (SELECT COUNT(*) FROM project_milestones m WHERE m.project_id=pr.id) AS milestone_count,
                      (SELECT COUNT(*) FROM project_risks r WHERE r.project_id=pr.id AND r.status NOT IN ('بسته‌شده')) AS open_risk_count
               FROM project_portfolio pr
               LEFT JOIN annual_operational_programs p ON p.id=pr.program_id
               LEFT JOIN zones z ON z.id=pr.zone_id""" + where + " ORDER BY pr.id DESC", params
        )
        keys = [c[0] for c in cur.description]
        rows = [dict(zip(keys, row)) for row in cur.fetchall()]
        today = datetime.now().strftime("%Y-%m-%d")
        for item in rows:
            item["is_overdue"] = bool(item.get("end_date") and item["end_date"] < today and item.get("status") not in ("تکمیل‌شده", "لغوشده"))
            item["progress_variance"] = round(float(item.get("actual_progress") or 0) - float(item.get("planned_progress") or 0), 2)
            item["cost_variance"] = round(float(item.get("actual_cost") or 0) - float(item.get("planned_budget") or 0), 2)
        return rows

    def update_project(self, project_id, **changes):
        before = self.get_project(project_id)
        if not before:
            raise ValueError("پروژه پیدا نشد.")
        allowed = {"program_id", "zone_id", "project_code", "title", "responsible_agency",
                   "project_manager", "start_date", "end_date", "actual_start_date", "actual_end_date",
                   "planned_budget", "actual_cost", "planned_progress", "actual_progress", "priority",
                   "status", "description"}
        values = {k: v for k, v in changes.items() if k in allowed}
        if not values:
            return False
        start = values.get("start_date", before.get("start_date"))
        end = values.get("end_date", before.get("end_date"))
        if start and end and str(end) < str(start):
            raise ValueError("تاریخ پایان پروژه نمی‌تواند قبل از تاریخ شروع باشد.")
        values["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.conn.execute("UPDATE project_portfolio SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
                              list(values.values()) + [int(project_id)])
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            if "project_code" in str(exc):
                raise ValueError("کد پروژه تکراری است.") from exc
            raise
        after = self.get_project(project_id)
        self.log_action("update", "project", project_id, {"title": after.get("title")},
                        zone_id=after.get("zone_id"), before=before, after=after)
        self._recalculate_program_progress(before.get("program_id"))
        if after.get("program_id") != before.get("program_id"):
            self._recalculate_program_progress(after.get("program_id"))
        return True

    def delete_project(self, project_id):
        before = self.get_project(project_id)
        if not before:
            return False
        self.conn.execute("DELETE FROM project_portfolio WHERE id=?", (int(project_id),))
        self.conn.commit()
        self.log_action("delete", "project", project_id, {"title": before.get("title")},
                        zone_id=before.get("zone_id"), before=before)
        self._recalculate_program_progress(before.get("program_id"))
        return True

    def _recalculate_program_progress(self, program_id):
        if program_id is None:
            return
        row = self.conn.execute(
            """SELECT COALESCE(SUM(CASE WHEN planned_budget>0 THEN actual_progress*planned_budget ELSE actual_progress END),0),
                      COALESCE(SUM(CASE WHEN planned_budget>0 THEN planned_budget ELSE 1 END),0)
               FROM project_portfolio WHERE program_id=? AND status<>'لغوشده'""", (int(program_id),)
        ).fetchone()
        progress = (float(row[0]) / float(row[1])) if row and row[1] else 0
        self.conn.execute("UPDATE annual_operational_programs SET progress_percent=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          (round(progress, 2), int(program_id)))
        self.conn.commit()

    def add_project_milestone(self, project_id, title, due_date=None, completed_date=None,
                              weight=1, status="در انتظار", notes=""):
        if not self.get_project(project_id):
            raise ValueError("پروژه پیدا نشد.")
        if not str(title or "").strip():
            raise ValueError("عنوان نقطه عطف الزامی است.")
        cur = self.conn.cursor()
        cur.execute("""INSERT INTO project_milestones
                       (project_id,title,due_date,completed_date,weight,status,notes)
                       VALUES (?,?,?,?,?,?,?)""",
                    (int(project_id), str(title).strip(), due_date, completed_date, float(weight or 1), status, notes or ""))
        milestone_id = cur.lastrowid
        self.conn.commit()
        project = self.get_project(project_id)
        self.log_action("create", "project_milestone", milestone_id, {"title": title, "project_id": project_id}, zone_id=project.get("zone_id"))
        return milestone_id

    def get_project_milestone(self, milestone_id):
        cur = self.conn.execute(
            """SELECT m.*, pr.title AS project_title, pr.zone_id, z.name AS zone_name
               FROM project_milestones m JOIN project_portfolio pr ON pr.id=m.project_id
               LEFT JOIN zones z ON z.id=pr.zone_id WHERE m.id=?""", (int(milestone_id),)
        )
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None

    def get_project_milestones(self, project_id=None, status=None):
        clauses, params = [], []
        if project_id is not None:
            clauses.append("m.project_id=?"); params.append(int(project_id))
        if status:
            clauses.append("m.status=?"); params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cur = self.conn.execute(
            """SELECT m.*, pr.title AS project_title, pr.project_code, pr.zone_id, z.name AS zone_name
               FROM project_milestones m JOIN project_portfolio pr ON pr.id=m.project_id
               LEFT JOIN zones z ON z.id=pr.zone_id""" + where + " ORDER BY COALESCE(m.due_date,'9999-12-31'), m.id", params
        )
        keys = [c[0] for c in cur.description]
        today = datetime.now().strftime("%Y-%m-%d")
        rows = [dict(zip(keys, row)) for row in cur.fetchall()]
        for row in rows:
            row["is_overdue"] = bool(row.get("due_date") and row["due_date"] < today and row.get("status") not in ("تکمیل‌شده", "لغوشده"))
        return rows

    def update_project_milestone(self, milestone_id, **changes):
        before = self.get_project_milestone(milestone_id)
        if not before:
            raise ValueError("نقطه عطف پیدا نشد.")
        allowed = {"title", "due_date", "completed_date", "weight", "status", "notes"}
        values = {k: v for k, v in changes.items() if k in allowed}
        if not values:
            return False
        if "title" in values and not str(values["title"] or "").strip():
            raise ValueError("عنوان نقطه عطف الزامی است.")
        values["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute("UPDATE project_milestones SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
                          list(values.values()) + [int(milestone_id)])
        self.conn.commit()
        after = self.get_project_milestone(milestone_id)
        self.log_action("update", "project_milestone", milestone_id, {"title": after.get("title")},
                        zone_id=after.get("zone_id"), before=before, after=after)
        return True

    def delete_project_milestone(self, milestone_id):
        before = self.get_project_milestone(milestone_id)
        if not before:
            return False
        self.conn.execute("DELETE FROM project_milestones WHERE id=?", (int(milestone_id),))
        self.conn.commit()
        self.log_action("delete", "project_milestone", milestone_id, {"title": before.get("title")},
                        zone_id=before.get("zone_id"), before=before)
        return True

    def add_project_progress_update(self, project_id, report_date, planned_progress=0,
                                    actual_progress=0, actual_cost=0, summary="", obstacles="", next_steps=""):
        if not self.get_project(project_id):
            raise ValueError("پروژه پیدا نشد.")
        self.conn.execute(
            """INSERT INTO project_progress_updates
               (project_id,report_date,planned_progress,actual_progress,actual_cost,summary,obstacles,next_steps)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(project_id,report_date) DO UPDATE SET
                 planned_progress=excluded.planned_progress, actual_progress=excluded.actual_progress,
                 actual_cost=excluded.actual_cost, summary=excluded.summary,
                 obstacles=excluded.obstacles, next_steps=excluded.next_steps""",
            (int(project_id), str(report_date)[:10], float(planned_progress or 0), float(actual_progress or 0),
             float(actual_cost or 0), summary or "", obstacles or "", next_steps or ""),
        )
        self.conn.execute(
            """UPDATE project_portfolio SET planned_progress=?, actual_progress=?, actual_cost=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (float(planned_progress or 0), float(actual_progress or 0), float(actual_cost or 0), int(project_id)),
        )
        self.conn.commit()
        project = self.get_project(project_id)
        self._recalculate_program_progress(project.get("program_id"))
        self.log_action("progress_update", "project", project_id,
                        {"report_date": report_date, "actual_progress": actual_progress, "actual_cost": actual_cost}, zone_id=project.get("zone_id"))
        return True

    def get_project_progress_updates(self, project_id):
        cur = self.conn.execute("SELECT * FROM project_progress_updates WHERE project_id=? ORDER BY report_date, id", (int(project_id),))
        keys = [c[0] for c in cur.description]
        return [dict(zip(keys, row)) for row in cur.fetchall()]

    def add_project_indicator(self, title, program_id=None, project_id=None, unit="",
                              baseline_value=0, target_value=0, actual_value=0,
                              direction="افزایشی", weight=1, measurement_date=None, notes=""):
        if program_id is None and project_id is None:
            raise ValueError("شاخص باید به برنامه یا پروژه متصل باشد.")
        if not str(title or "").strip():
            raise ValueError("عنوان شاخص الزامی است.")
        cur = self.conn.cursor()
        cur.execute("""INSERT INTO project_indicators
                       (program_id,project_id,title,unit,baseline_value,target_value,actual_value,
                        direction,weight,measurement_date,notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (program_id, project_id, str(title).strip(), unit or "", float(baseline_value or 0),
                     float(target_value or 0), float(actual_value or 0), direction or "افزایشی",
                     float(weight or 1), measurement_date, notes or ""))
        indicator_id = cur.lastrowid
        self.conn.commit()
        project = self.get_project(project_id) if project_id else None
        program = self.get_annual_program(program_id) if program_id else None
        self.log_action("create", "project_indicator", indicator_id, {"title": title},
                        zone_id=(project or program or {}).get("zone_id"))
        return indicator_id

    def get_project_indicator(self, indicator_id):
        cur = self.conn.execute(
            """SELECT i.*, p.title AS program_title, pr.title AS project_title,
                      COALESCE(pr.zone_id,p.zone_id) AS zone_id, z.name AS zone_name
               FROM project_indicators i
               LEFT JOIN annual_operational_programs p ON p.id=i.program_id
               LEFT JOIN project_portfolio pr ON pr.id=i.project_id
               LEFT JOIN zones z ON z.id=COALESCE(pr.zone_id,p.zone_id)
               WHERE i.id=?""", (int(indicator_id),)
        )
        row = cur.fetchone()
        if not row: return None
        item = dict(zip([c[0] for c in cur.description], row))
        item["achievement_percent"] = self.calculate_indicator_achievement(
            item.get("baseline_value"), item.get("target_value"), item.get("actual_value"), item.get("direction"))
        return item

    def get_project_indicators(self, program_id=None, project_id=None):
        clauses, params = [], []
        if program_id is not None:
            clauses.append("i.program_id=?"); params.append(int(program_id))
        if project_id is not None:
            clauses.append("i.project_id=?"); params.append(int(project_id))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cur = self.conn.execute(
            """SELECT i.*, p.title AS program_title, pr.title AS project_title,
                      COALESCE(pr.zone_id,p.zone_id) AS zone_id, z.name AS zone_name
               FROM project_indicators i
               LEFT JOIN annual_operational_programs p ON p.id=i.program_id
               LEFT JOIN project_portfolio pr ON pr.id=i.project_id
               LEFT JOIN zones z ON z.id=COALESCE(pr.zone_id,p.zone_id)""" + where + " ORDER BY i.id DESC", params
        )
        keys = [c[0] for c in cur.description]
        rows = [dict(zip(keys, row)) for row in cur.fetchall()]
        for item in rows:
            item["achievement_percent"] = self.calculate_indicator_achievement(
                item.get("baseline_value"), item.get("target_value"), item.get("actual_value"), item.get("direction"))
        return rows

    def update_project_indicator(self, indicator_id, **changes):
        before = self.get_project_indicator(indicator_id)
        if not before: raise ValueError("شاخص پیدا نشد.")
        allowed = {"program_id", "project_id", "title", "unit", "baseline_value", "target_value",
                   "actual_value", "direction", "weight", "measurement_date", "notes"}
        values = {k:v for k,v in changes.items() if k in allowed}
        if not values: return False
        if values.get("program_id", before.get("program_id")) is None and values.get("project_id", before.get("project_id")) is None:
            raise ValueError("شاخص باید به برنامه یا پروژه متصل باشد.")
        if "title" in values and not str(values["title"] or "").strip():
            raise ValueError("عنوان شاخص الزامی است.")
        values["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute("UPDATE project_indicators SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
                          list(values.values()) + [int(indicator_id)])
        self.conn.commit()
        after = self.get_project_indicator(indicator_id)
        self.log_action("update", "project_indicator", indicator_id, {"title": after.get("title")},
                        zone_id=after.get("zone_id"), before=before, after=after)
        return True

    def delete_project_indicator(self, indicator_id):
        before = self.get_project_indicator(indicator_id)
        if not before: return False
        self.conn.execute("DELETE FROM project_indicators WHERE id=?", (int(indicator_id),))
        self.conn.commit()
        self.log_action("delete", "project_indicator", indicator_id, {"title": before.get("title")},
                        zone_id=before.get("zone_id"), before=before)
        return True

    def add_project_risk(self, title, program_id=None, project_id=None, zone_id=None,
                         category="اجرایی", probability=1, impact=1, owner="", mitigation="",
                         contingency="", review_date=None, status="باز"):
        if not str(title or "").strip(): raise ValueError("عنوان ریسک الزامی است.")
        score, level = self.calculate_risk_level(probability, impact)
        if zone_id is None:
            entity = self.get_project(project_id) if project_id else self.get_annual_program(program_id) if program_id else None
            zone_id = (entity or {}).get("zone_id")
        cur = self.conn.cursor()
        cur.execute("""INSERT INTO project_risks
                       (program_id,project_id,zone_id,title,category,probability,impact,risk_score,risk_level,
                        owner,mitigation,contingency,review_date,status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (program_id, project_id, zone_id, str(title).strip(), category or "اجرایی",
                     int(probability or 1), int(impact or 1), score, level, owner or "", mitigation or "",
                     contingency or "", review_date, status or "باز"))
        risk_id = cur.lastrowid
        self.conn.commit()
        self.log_action("create", "project_risk", risk_id, {"title": title, "risk_score": score}, zone_id=zone_id)
        return risk_id

    def get_project_risk(self, risk_id):
        cur = self.conn.execute(
            """SELECT r.*, p.title AS program_title, pr.title AS project_title, z.name AS zone_name
               FROM project_risks r
               LEFT JOIN annual_operational_programs p ON p.id=r.program_id
               LEFT JOIN project_portfolio pr ON pr.id=r.project_id
               LEFT JOIN zones z ON z.id=r.zone_id WHERE r.id=?""", (int(risk_id),)
        )
        row = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], row)) if row else None

    def get_project_risks(self, program_id=None, project_id=None, zone_id=None, open_only=False):
        clauses, params = [], []
        if program_id is not None: clauses.append("r.program_id=?"); params.append(int(program_id))
        if project_id is not None: clauses.append("r.project_id=?"); params.append(int(project_id))
        if zone_id is not None: clauses.append("r.zone_id=?"); params.append(int(zone_id))
        if open_only: clauses.append("r.status NOT IN ('بسته‌شده')")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        cur = self.conn.execute(
            """SELECT r.*, p.title AS program_title, pr.title AS project_title, z.name AS zone_name
               FROM project_risks r
               LEFT JOIN annual_operational_programs p ON p.id=r.program_id
               LEFT JOIN project_portfolio pr ON pr.id=r.project_id
               LEFT JOIN zones z ON z.id=r.zone_id""" + where + " ORDER BY r.risk_score DESC, r.id DESC", params
        )
        keys=[c[0] for c in cur.description]
        return [dict(zip(keys,row)) for row in cur.fetchall()]

    def update_project_risk(self, risk_id, **changes):
        before=self.get_project_risk(risk_id)
        if not before: raise ValueError("ریسک پیدا نشد.")
        allowed={"program_id","project_id","zone_id","title","category","probability","impact","owner",
                 "mitigation","contingency","review_date","status"}
        values={k:v for k,v in changes.items() if k in allowed}
        if not values: return False
        if "title" in values and not str(values["title"] or "").strip():
            raise ValueError("عنوان ریسک الزامی است.")
        probability=values.get("probability",before.get("probability")); impact=values.get("impact",before.get("impact"))
        score,level=self.calculate_risk_level(probability,impact)
        values["risk_score"]=score; values["risk_level"]=level
        values["updated_at"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute("UPDATE project_risks SET "+",".join(f"{k}=?" for k in values)+" WHERE id=?",
                          list(values.values())+[int(risk_id)])
        self.conn.commit()
        after=self.get_project_risk(risk_id)
        self.log_action("update","project_risk",risk_id,{"title":after.get("title"),"risk_score":score},
                        zone_id=after.get("zone_id"),before=before,after=after)
        return True

    def delete_project_risk(self, risk_id):
        before=self.get_project_risk(risk_id)
        if not before:return False
        self.conn.execute("DELETE FROM project_risks WHERE id=?",(int(risk_id),)); self.conn.commit()
        self.log_action("delete","project_risk",risk_id,{"title":before.get("title")},zone_id=before.get("zone_id"),before=before)
        return True

    def add_project_change_request(self, title, program_id=None, project_id=None, change_type="دامنه",
                                   target_field=None, reason="", requested_by="", request_date=None,
                                   impact_days=0, impact_cost=0, old_value="", new_value="",
                                   status="در انتظار بررسی", review_note=""):
        if program_id is None and project_id is None: raise ValueError("درخواست تغییر باید به برنامه یا پروژه متصل باشد.")
        if not str(title or "").strip(): raise ValueError("عنوان درخواست تغییر الزامی است.")
        cur=self.conn.cursor()
        cur.execute("""INSERT INTO project_change_requests
                       (program_id,project_id,title,change_type,target_field,reason,requested_by,request_date,
                        impact_days,impact_cost,old_value,new_value,status,review_note)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (program_id,project_id,str(title).strip(),change_type or "دامنه",target_field,reason or "",
                     requested_by or "",request_date or datetime.now().strftime("%Y-%m-%d"),int(impact_days or 0),
                     float(impact_cost or 0),str(old_value or ""),str(new_value or ""),status or "در انتظار بررسی",review_note or ""))
        change_id=cur.lastrowid; self.conn.commit()
        entity=self.get_project(project_id) if project_id else self.get_annual_program(program_id)
        self.log_action("create","project_change",change_id,{"title":title,"change_type":change_type},zone_id=(entity or {}).get("zone_id"))
        return change_id

    def get_project_change_request(self, change_id):
        cur=self.conn.execute("""SELECT c.*, p.title AS program_title, pr.title AS project_title,
                      COALESCE(pr.zone_id,p.zone_id) AS zone_id, z.name AS zone_name, u.full_name AS reviewed_by_name
               FROM project_change_requests c
               LEFT JOIN annual_operational_programs p ON p.id=c.program_id
               LEFT JOIN project_portfolio pr ON pr.id=c.project_id
               LEFT JOIN zones z ON z.id=COALESCE(pr.zone_id,p.zone_id)
               LEFT JOIN app_users u ON u.id=c.reviewed_by WHERE c.id=?""",(int(change_id),))
        row=cur.fetchone(); return dict(zip([c[0] for c in cur.description],row)) if row else None

    def get_project_change_requests(self, program_id=None, project_id=None, status=None):
        clauses=[];params=[]
        if program_id is not None:clauses.append("c.program_id=?");params.append(int(program_id))
        if project_id is not None:clauses.append("c.project_id=?");params.append(int(project_id))
        if status:clauses.append("c.status=?");params.append(status)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        cur=self.conn.execute("""SELECT c.*, p.title AS program_title, pr.title AS project_title,
                      COALESCE(pr.zone_id,p.zone_id) AS zone_id, z.name AS zone_name, u.full_name AS reviewed_by_name
               FROM project_change_requests c
               LEFT JOIN annual_operational_programs p ON p.id=c.program_id
               LEFT JOIN project_portfolio pr ON pr.id=c.project_id
               LEFT JOIN zones z ON z.id=COALESCE(pr.zone_id,p.zone_id)
               LEFT JOIN app_users u ON u.id=c.reviewed_by"""+where+" ORDER BY c.id DESC",params)
        keys=[c[0] for c in cur.description];return [dict(zip(keys,row)) for row in cur.fetchall()]

    def review_project_change_request(self, change_id, status, review_note="", apply_change=False):
        if status not in ("تأییدشده","ردشده","لغوشده","اعمال‌شده"):
            raise ValueError("وضعیت بررسی نامعتبر است.")
        before=self.get_project_change_request(change_id)
        if not before:raise ValueError("درخواست تغییر پیدا نشد.")
        user_id=(self.current_user or {}).get("id")
        reviewed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        final_status=status
        if apply_change and status in ("تأییدشده","اعمال‌شده"):
            field=before.get("target_field")
            new_value=before.get("new_value")
            project_fields={"end_date","start_date","planned_budget","project_manager","responsible_agency","description","priority"}
            program_fields={"end_date","start_date","approved_budget","program_manager","responsible_agency","description","status"}
            if before.get("project_id") and field in project_fields:
                value=float(new_value) if field=="planned_budget" else new_value
                self.update_project(before["project_id"],**{field:value})
                final_status="اعمال‌شده"
            elif before.get("program_id"):
                program_field_map = {"planned_budget": "approved_budget", "project_manager": "program_manager"}
                mapped_field = program_field_map.get(field, field)
                if mapped_field in program_fields:
                    value=float(new_value) if mapped_field=="approved_budget" else new_value
                    self.update_annual_program(before["program_id"],**{mapped_field:value})
                    final_status="اعمال‌شده"
        self.conn.execute("""UPDATE project_change_requests SET status=?,review_note=?,reviewed_by=?,reviewed_at=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                          (final_status,review_note or "",user_id,reviewed_at,int(change_id)))
        self.conn.commit()
        after=self.get_project_change_request(change_id)
        self.log_action("review","project_change",change_id,{"status":final_status},zone_id=after.get("zone_id"),before=before,after=after)
        return after

    def delete_project_change_request(self, change_id):
        before=self.get_project_change_request(change_id)
        if not before:return False
        self.conn.execute("DELETE FROM project_change_requests WHERE id=?",(int(change_id),));self.conn.commit()
        self.log_action("delete","project_change",change_id,{"title":before.get("title")},zone_id=before.get("zone_id"),before=before)
        return True

    def get_project_control_alerts(self, fiscal_year=None, zone_id=None, days_ahead=7):
        today=datetime.now().date(); threshold=today+timedelta(days=int(days_ahead or 7)); alerts=[]
        for row in self.conn.execute(
            """SELECT m.id,m.zone_id,z.name,c.title || ' — ' || m.title,m.meeting_date,m.status,
                      m.start_time,m.place_name
               FROM committee_meetings m
               JOIN neighborhood_committees c ON c.id=m.committee_id
               LEFT JOIN zones z ON z.id=m.zone_id
               WHERE m.meeting_date IS NOT NULL AND m.meeting_date<>''"""
        ).fetchall():
            add_item("committee_meeting", row[0], row[1], row[2], row[3], "جلسه کمیته محله", row[4], row[5],
                     "عادی", "", None, row[6], row[7], 1, False)

        for row in self.conn.execute(
            """SELECT r.id,r.zone_id,z.name,c.title || ' — ' || r.title,r.due_date,r.status,
                      r.responsible_person,r.responsible_agency
               FROM committee_resolutions r
               JOIN neighborhood_committees c ON c.id=r.committee_id
               LEFT JOIN zones z ON z.id=r.zone_id
               WHERE r.due_date IS NOT NULL AND r.due_date<>''"""
        ).fetchall():
            if include_closed or row[5] not in {"انجام‌شده", "لغوشده"}:
                add_item("committee_resolution", row[0], row[1], row[2], row[3], "مصوبه کمیته محله",
                         row[4], row[5], "مهم", row[6] or row[7] or "")

        for project in self.get_projects(zone_id=zone_id):
            if fiscal_year and str(project.get("fiscal_year") or "")!=str(fiscal_year):continue
            end=self._date_object(project.get("end_date"))
            actual=float(project.get("actual_progress") or 0); planned=float(project.get("planned_progress") or 0)
            if end and end<today and project.get("status") not in ("تکمیل‌شده","لغوشده"):
                alerts.append({"key":f"project_overdue:{project['id']}","severity":"بحرانی","type":"پروژه معوق","title":project["title"],"zone_name":project.get("zone_name"),"due_date":project.get("end_date"),"message":"پروژه از تاریخ پایان برنامه‌ریزی‌شده عبور کرده است."})
            elif end and today<=end<=threshold and project.get("status") not in ("تکمیل‌شده","لغوشده"):
                alerts.append({"key":f"project_due:{project['id']}","severity":"فوری","type":"سررسید پروژه","title":project["title"],"zone_name":project.get("zone_name"),"due_date":project.get("end_date"),"message":"پروژه به تاریخ پایان نزدیک است."})
            if actual+10<planned and project.get("status") not in ("تکمیل‌شده","لغوشده"):
                alerts.append({"key":f"project_lag:{project['id']}","severity":"مهم","type":"انحراف پیشرفت","title":project["title"],"zone_name":project.get("zone_name"),"due_date":project.get("end_date"),"message":f"پیشرفت واقعی {actual:.0f}٪ در برابر برنامه {planned:.0f}٪ است."})
            if float(project.get("planned_budget") or 0)>0 and float(project.get("actual_cost") or 0)>float(project.get("planned_budget") or 0):
                alerts.append({"key":f"project_overrun:{project['id']}","severity":"بحرانی","type":"اضافه‌هزینه","title":project["title"],"zone_name":project.get("zone_name"),"due_date":project.get("end_date"),"message":"هزینه واقعی از بودجه برنامه‌ریزی‌شده بیشتر است."})
        for milestone in self.get_project_milestones():
            if zone_id is not None and milestone.get("zone_id")!=int(zone_id):continue
            due=self._date_object(milestone.get("due_date"))
            if due and due<today and milestone.get("status") not in ("تکمیل‌شده","لغوشده"):
                alerts.append({"key":f"milestone_overdue:{milestone['id']}","severity":"بحرانی","type":"نقطه عطف معوق","title":milestone["title"],"zone_name":milestone.get("zone_name"),"due_date":milestone.get("due_date"),"message":f"نقطه عطف پروژه {milestone.get('project_title')} معوق است."})
        for risk in self.get_project_risks(zone_id=zone_id,open_only=True):
            if int(risk.get("risk_score") or 0)>=12:
                alerts.append({"key":f"risk_high:{risk['id']}","severity":"بحرانی" if int(risk.get("risk_score") or 0)>=20 else "فوری","type":"ریسک بالا","title":risk["title"],"zone_name":risk.get("zone_name"),"due_date":risk.get("review_date"),"message":f"امتیاز ریسک {risk.get('risk_score')} از ۲۵ است."})
        for change in self.get_project_change_requests(status="در انتظار بررسی"):
            if zone_id is not None and change.get("zone_id")!=int(zone_id):continue
            alerts.append({"key":f"change_pending:{change['id']}","severity":"مهم","type":"تغییر در انتظار","title":change["title"],"zone_name":change.get("zone_name"),"due_date":change.get("request_date"),"message":"درخواست تغییر هنوز بررسی نشده است."})
        order={"بحرانی":0,"فوری":1,"مهم":2,"اطلاع":3}
        return sorted(alerts,key=lambda x:(order.get(x.get("severity"),9),x.get("due_date") or "9999-12-31",x.get("title") or ""))

    def get_project_control_summary(self, fiscal_year=None, zone_id=None):
        programs=self.get_annual_programs(fiscal_year=fiscal_year,zone_id=zone_id)
        projects=[]
        for program in programs:
            projects.extend(self.get_projects(program_id=program["id"],zone_id=zone_id))
        if not fiscal_year:
            projects=self.get_projects(zone_id=zone_id)
        project_ids={p["id"] for p in projects}
        risks=[r for r in self.get_project_risks(zone_id=zone_id,open_only=True) if not project_ids or r.get("project_id") in project_ids or r.get("project_id") is None]
        changes=[c for c in self.get_project_change_requests(status="در انتظار بررسی") if zone_id is None or c.get("zone_id")==int(zone_id)]
        indicators=self.get_project_indicators()
        if project_ids:
            indicators=[i for i in indicators if i.get("project_id") in project_ids or i.get("program_id") in {p["id"] for p in programs}]
        weighted=sum(float(i.get("achievement_percent") or 0)*float(i.get("weight") or 1) for i in indicators)
        total_weight=sum(float(i.get("weight") or 1) for i in indicators)
        today=datetime.now().strftime("%Y-%m-%d")
        planned_budget=sum(float(p.get("planned_budget") or 0) for p in projects)
        actual_cost=sum(float(p.get("actual_cost") or 0) for p in projects)
        avg_progress=(sum(float(p.get("actual_progress") or 0) for p in projects)/len(projects)) if projects else 0
        return {
            "programs_count":len(programs),"projects_count":len(projects),
            "active_projects":sum(1 for p in projects if p.get("status")=="در حال اجرا"),
            "completed_projects":sum(1 for p in projects if p.get("status")=="تکمیل‌شده"),
            "overdue_projects":sum(1 for p in projects if p.get("end_date") and p["end_date"]<today and p.get("status") not in ("تکمیل‌شده","لغوشده")),
            "planned_budget":round(planned_budget,2),"actual_cost":round(actual_cost,2),
            "cost_variance":round(actual_cost-planned_budget,2),"average_progress":round(avg_progress,2),
            "high_risks":sum(1 for r in risks if int(r.get("risk_score") or 0)>=12),
            "critical_risks":sum(1 for r in risks if int(r.get("risk_score") or 0)>=20),
            "pending_changes":len(changes),"indicator_achievement":round(weighted/total_weight,2) if total_weight else 0,
            "alerts_count":len(self.get_project_control_alerts(fiscal_year=fiscal_year,zone_id=zone_id)),
        }

    def get_project_gantt_data(self, date_from=None, date_to=None, program_id=None, zone_id=None):
        projects=self.get_projects(program_id=program_id,zone_id=zone_id)
        result=[]
        for p in projects:
            if date_from and p.get("end_date") and p["end_date"]<date_from:continue
            if date_to and p.get("start_date") and p["start_date"]>date_to:continue
            result.append({"kind":"project","id":p["id"],"parent_id":None,"code":p.get("project_code"),"title":p.get("title"),
                           "program_title":p.get("program_title"),"zone_name":p.get("zone_name"),"start_date":p.get("start_date"),
                           "end_date":p.get("end_date"),"progress":float(p.get("actual_progress") or 0),"status":p.get("status"),"priority":p.get("priority")})
            for m in self.get_project_milestones(project_id=p["id"]):
                if date_from and m.get("due_date") and m["due_date"]<date_from:continue
                if date_to and m.get("due_date") and m["due_date"]>date_to:continue
                result.append({"kind":"milestone","id":m["id"],"parent_id":p["id"],"code":"", "title":m.get("title"),
                               "program_title":p.get("program_title"),"zone_name":p.get("zone_name"),"start_date":m.get("due_date"),
                               "end_date":m.get("due_date"),"progress":100 if m.get("status")=="تکمیل‌شده" else 0,
                               "status":m.get("status"),"priority":p.get("priority")})
        return result

    # ---------------- Contracts, Contractors & Satisfaction v6.8 ----------------
    CONTRACTOR_STATUSES = ["فعال", "تعلیق", "غیرفعال", "ممنوع‌المعامله"]
    CONTRACT_STATUSES = ["پیش‌نویس", "فعال", "متوقف", "تحویل موقت", "تسویه", "مختومه", "فسخ‌شده"]
    PAYMENT_TYPES = ["پیش‌پرداخت", "صورت‌وضعیت", "تعدیل", "کسور", "تسویه نهایی", "سایر"]
    PAYMENT_STATUSES = ["ثبت اولیه", "در انتظار تأیید", "تأییدشده", "پرداخت جزئی", "پرداخت‌شده", "ردشده"]
    PARTICIPATION_TYPES = ["داوطلبانه", "کمک نقدی", "کمک غیرنقدی", "خیرین", "گروه مردمی", "مسئولیت اجتماعی", "سایر"]

    @staticmethod
    def calculate_contractor_score(quality, schedule, safety, cooperation, documentation):
        values = [max(0.0, min(5.0, float(v or 0))) for v in
                  (quality, schedule, safety, cooperation, documentation)]
        # کیفیت و زمان‌بندی وزن بیشتر دارند.
        score = (values[0] * 0.30 + values[1] * 0.25 + values[2] * 0.20 +
                 values[3] * 0.15 + values[4] * 0.10) * 20.0
        return round(score, 2)

    @staticmethod
    def calculate_satisfaction_percent(quality, speed, communication, overall):
        values = [max(0.0, min(5.0, float(v or 0))) for v in
                  (quality, speed, communication, overall)]
        return round((sum(values) / 4.0) * 20.0, 2)

    def add_contractor(self, name, national_id="", registration_no="", manager_name="",
                       phone="", email="", address="", specialty="", status="فعال", notes=""):
        if not str(name or "").strip():
            raise ValueError("نام پیمانکار الزامی است.")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO contractors
               (name,national_id,registration_no,manager_name,phone,email,address,specialty,status,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (str(name).strip(), national_id or "", registration_no or "", manager_name or "",
             phone or "", email or "", address or "", specialty or "", status or "فعال", notes or ""),
        )
        contractor_id = cur.lastrowid
        self.conn.commit()
        self.log_action("create", "contractor", contractor_id, {"name": name})
        return contractor_id

    def update_contractor(self, contractor_id, **values):
        before = self.get_contractor(contractor_id)
        if not before:
            raise ValueError("پیمانکار پیدا نشد.")
        allowed = ["name", "national_id", "registration_no", "manager_name", "phone", "email",
                   "address", "specialty", "status", "notes"]
        fields, params = [], []
        for key in allowed:
            if key in values:
                fields.append(f"{key}=?"); params.append(values[key])
        if not fields:
            return before
        params.append(int(contractor_id))
        self.conn.execute(f"UPDATE contractors SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", params)
        self.conn.commit()
        after = self.get_contractor(contractor_id)
        self.log_action("update", "contractor", contractor_id, {"name": after.get("name")}, before=before, after=after)
        return after

    def get_contractor(self, contractor_id):
        row = self.conn.execute(
            """SELECT id,name,national_id,registration_no,manager_name,phone,email,address,specialty,
                      status,average_score,notes,created_at,updated_at
               FROM contractors WHERE id=?""", (int(contractor_id),)
        ).fetchone()
        keys = ["id","name","national_id","registration_no","manager_name","phone","email","address",
                "specialty","status","average_score","notes","created_at","updated_at"]
        return dict(zip(keys, row)) if row else None

    def get_contractors(self, status=None, query=None):
        clauses, params = [], []
        if status:
            clauses.append("status=?"); params.append(status)
        if query:
            clauses.append("(name LIKE ? OR national_id LIKE ? OR manager_name LIKE ? OR specialty LIKE ?)")
            like = f"%{query}%"; params.extend([like, like, like, like])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(
            """SELECT c.id,c.name,c.national_id,c.registration_no,c.manager_name,c.phone,c.email,c.address,
                      c.specialty,c.status,c.average_score,c.notes,c.created_at,c.updated_at,
                      COUNT(pc.id),COALESCE(SUM(CASE WHEN pc.status='فعال' THEN 1 ELSE 0 END),0)
               FROM contractors c LEFT JOIN project_contracts pc ON pc.contractor_id=c.id""" + where +
            " GROUP BY c.id ORDER BY CASE c.status WHEN 'فعال' THEN 0 ELSE 1 END, c.name", params
        ).fetchall()
        keys = ["id","name","national_id","registration_no","manager_name","phone","email","address",
                "specialty","status","average_score","notes","created_at","updated_at","contracts_count","active_contracts"]
        return [dict(zip(keys, row)) for row in rows]

    def delete_contractor(self, contractor_id):
        before = self.get_contractor(contractor_id)
        if not before:
            return False
        if self.conn.execute("SELECT COUNT(*) FROM project_contracts WHERE contractor_id=?", (int(contractor_id),)).fetchone()[0]:
            raise ValueError("پیمانکار دارای قرارداد است و قابل حذف نیست؛ ابتدا وضعیت آن را غیرفعال کنید.")
        self.conn.execute("DELETE FROM contractors WHERE id=?", (int(contractor_id),)); self.conn.commit()
        self.log_action("delete", "contractor", contractor_id, {"name": before.get("name")}, before=before)
        return True

    def add_contract(self, contract_no, title, contractor_id, project_id=None, action_id=None,
                     contract_date=None, start_date=None, end_date=None, amount=0,
                     guarantee_amount=0, retention_percent=0, advance_percent=0,
                     status="پیش‌نویس", description=""):
        if not str(contract_no or "").strip() or not str(title or "").strip():
            raise ValueError("شماره و عنوان قرارداد الزامی است.")
        if project_id is None and action_id is None:
            raise ValueError("قرارداد باید به یک پروژه یا اقدام متصل شود.")
        if start_date and end_date and str(end_date) < str(start_date):
            raise ValueError("تاریخ پایان قرارداد قبل از شروع است.")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO project_contracts
               (project_id,action_id,contractor_id,contract_no,title,contract_date,start_date,end_date,
                amount,guarantee_amount,retention_percent,advance_percent,status,description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (project_id, action_id, int(contractor_id), str(contract_no).strip(), str(title).strip(),
             contract_date, start_date, end_date, float(amount or 0), float(guarantee_amount or 0),
             float(retention_percent or 0), float(advance_percent or 0), status or "پیش‌نویس", description or ""),
        )
        contract_id = cur.lastrowid; self.conn.commit()
        item = self.get_contract(contract_id)
        self.log_action("create", "contract", contract_id, {"contract_no": contract_no, "title": title}, zone_id=item.get("zone_id"))
        return contract_id

    def update_contract(self, contract_id, **values):
        before = self.get_contract(contract_id)
        if not before: raise ValueError("قرارداد پیدا نشد.")
        allowed = ["project_id","action_id","contractor_id","contract_no","title","contract_date","start_date",
                   "end_date","amount","guarantee_amount","retention_percent","advance_percent","status",
                   "temporary_delivery_date","final_delivery_date","description"]
        fields, params = [], []
        for key in allowed:
            if key in values:
                fields.append(f"{key}=?"); params.append(values[key])
        if not fields: return before
        project_id = values.get("project_id", before.get("project_id")); action_id = values.get("action_id", before.get("action_id"))
        if project_id is None and action_id is None: raise ValueError("قرارداد باید به پروژه یا اقدام متصل بماند.")
        start = values.get("start_date", before.get("start_date")); end = values.get("end_date", before.get("end_date"))
        if start and end and str(end) < str(start): raise ValueError("تاریخ پایان قرارداد قبل از شروع است.")
        params.append(int(contract_id)); self.conn.execute(f"UPDATE project_contracts SET {', '.join(fields)}, updated_at=CURRENT_TIMESTAMP WHERE id=?", params); self.conn.commit()
        after = self.get_contract(contract_id)
        self.log_action("update", "contract", contract_id, {"contract_no": after.get("contract_no")}, zone_id=after.get("zone_id"), before=before, after=after)
        return after

    def _contract_select(self):
        return """SELECT c.id,c.project_id,c.action_id,c.contractor_id,c.contract_no,c.title,c.contract_date,
                         c.start_date,c.end_date,c.amount,c.guarantee_amount,c.retention_percent,c.advance_percent,
                         c.status,c.temporary_delivery_date,c.final_delivery_date,c.description,c.created_at,c.updated_at,
                         k.name,p.project_code,p.title,a.title,COALESCE(p.zone_id,a.zone_id),z.name,
                         COALESCE((SELECT SUM(cp.approved_amount) FROM contract_payments cp WHERE cp.contract_id=c.id),0),
                         COALESCE((SELECT SUM(cp.paid_amount) FROM contract_payments cp WHERE cp.contract_id=c.id),0),
                         COALESCE((SELECT AVG(e.total_score) FROM contractor_evaluations e WHERE e.contract_id=c.id),0)
                  FROM project_contracts c
                  JOIN contractors k ON k.id=c.contractor_id
                  LEFT JOIN project_portfolio p ON p.id=c.project_id
                  LEFT JOIN neighborhood_actions a ON a.id=c.action_id
                  LEFT JOIN zones z ON z.id=COALESCE(p.zone_id,a.zone_id)"""

    def get_contract(self, contract_id):
        row = self.conn.execute(self._contract_select() + " WHERE c.id=?", (int(contract_id),)).fetchone()
        keys = ["id","project_id","action_id","contractor_id","contract_no","title","contract_date","start_date",
                "end_date","amount","guarantee_amount","retention_percent","advance_percent","status",
                "temporary_delivery_date","final_delivery_date","description","created_at","updated_at",
                "contractor_name","project_code","project_title","action_title","zone_id","zone_name",
                "approved_total","paid_total","evaluation_score"]
        if not row: return None
        item = dict(zip(keys,row)); item["remaining_amount"] = round(float(item["amount"] or 0)-float(item["paid_total"] or 0),2)
        item["payment_percent"] = round((float(item["paid_total"] or 0)/float(item["amount"] or 1))*100,2) if float(item["amount"] or 0)>0 else 0
        return item

    def get_contracts(self, project_id=None, action_id=None, contractor_id=None, zone_id=None, status=None, query=None):
        clauses, params = [], []
        for field, value in (("c.project_id",project_id),("c.action_id",action_id),("c.contractor_id",contractor_id),("c.status",status)):
            if value is not None:
                clauses.append(f"{field}=?"); params.append(value)
        if zone_id is not None:
            clauses.append("COALESCE(p.zone_id,a.zone_id)=?"); params.append(int(zone_id))
        if query:
            clauses.append("(c.contract_no LIKE ? OR c.title LIKE ? OR k.name LIKE ?)"); like=f"%{query}%"; params.extend([like,like,like])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(self._contract_select()+where+" ORDER BY COALESCE(c.end_date,'9999-12-31'),c.id DESC",params).fetchall()
        keys = ["id","project_id","action_id","contractor_id","contract_no","title","contract_date","start_date",
                "end_date","amount","guarantee_amount","retention_percent","advance_percent","status",
                "temporary_delivery_date","final_delivery_date","description","created_at","updated_at",
                "contractor_name","project_code","project_title","action_title","zone_id","zone_name",
                "approved_total","paid_total","evaluation_score"]
        result=[]
        for row in rows:
            item=dict(zip(keys,row)); item["remaining_amount"]=round(float(item["amount"] or 0)-float(item["paid_total"] or 0),2)
            item["payment_percent"]=round((float(item["paid_total"] or 0)/float(item["amount"] or 1))*100,2) if float(item["amount"] or 0)>0 else 0
            result.append(item)
        return result

    def delete_contract(self, contract_id):
        before=self.get_contract(contract_id)
        if not before:return False
        self.conn.execute("DELETE FROM project_contracts WHERE id=?",(int(contract_id),));self.conn.commit()
        self._refresh_contractor_average(before["contractor_id"])
        self.log_action("delete","contract",contract_id,{"contract_no":before.get("contract_no")},zone_id=before.get("zone_id"),before=before)
        return True

    def add_contract_payment(self, contract_id, payment_type="صورت‌وضعیت", statement_no=None,
                             period_from=None, period_to=None, gross_amount=0, deductions=0,
                             approved_amount=0, paid_amount=0, invoice_date=None, approval_date=None,
                             payment_date=None, status="ثبت اولیه", notes=""):
        gross=float(gross_amount or 0); deductions=float(deductions or 0); net=max(0.0,gross-deductions)
        if period_from and period_to and str(period_to)<str(period_from): raise ValueError("پایان دوره قبل از شروع است.")
        cur=self.conn.cursor();cur.execute(
            """INSERT INTO contract_payments
               (contract_id,payment_type,statement_no,period_from,period_to,gross_amount,deductions,net_amount,
                approved_amount,paid_amount,invoice_date,approval_date,payment_date,status,notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(contract_id),payment_type or "صورت‌وضعیت",statement_no,period_from,period_to,gross,deductions,net,
             float(approved_amount or 0),float(paid_amount or 0),invoice_date,approval_date,payment_date,status or "ثبت اولیه",notes or ""))
        pid=cur.lastrowid;self.conn.commit();contract=self.get_contract(contract_id)
        self.log_action("create","contract_payment",pid,{"contract_id":contract_id,"statement_no":statement_no},zone_id=(contract or {}).get("zone_id"))
        return pid

    def update_contract_payment(self, payment_id, **values):
        before=self.get_contract_payment(payment_id)
        if not before:raise ValueError("پرداخت پیدا نشد.")
        allowed=["payment_type","statement_no","period_from","period_to","gross_amount","deductions","approved_amount","paid_amount","invoice_date","approval_date","payment_date","status","notes"]
        data=dict(before);data.update(values);gross=float(data.get("gross_amount") or 0);ded=float(data.get("deductions") or 0);data["net_amount"]=max(0.0,gross-ded)
        period_from=data.get("period_from");period_to=data.get("period_to")
        if period_from and period_to and str(period_to)<str(period_from):
            raise ValueError("پایان دوره قبل از شروع است.")
        fields=[];params=[]
        for key in allowed+["net_amount"]:
            if key in values or key=="net_amount":fields.append(f"{key}=?");params.append(data.get(key))
        params.append(int(payment_id));self.conn.execute(f"UPDATE contract_payments SET {', '.join(fields)},updated_at=CURRENT_TIMESTAMP WHERE id=?",params);self.conn.commit()
        after=self.get_contract_payment(payment_id);contract=self.get_contract(after["contract_id"])
        self.log_action("update","contract_payment",payment_id,{"statement_no":after.get("statement_no")},zone_id=(contract or {}).get("zone_id"),before=before,after=after)
        return after

    def get_contract_payment(self, payment_id):
        row=self.conn.execute(
            """SELECT cp.id,cp.contract_id,cp.payment_type,cp.statement_no,cp.period_from,cp.period_to,
                      cp.gross_amount,cp.deductions,cp.net_amount,cp.approved_amount,cp.paid_amount,
                      cp.invoice_date,cp.approval_date,cp.payment_date,cp.status,cp.notes,cp.created_at,cp.updated_at,
                      c.contract_no,c.title,k.name,COALESCE(p.zone_id,a.zone_id),z.name
               FROM contract_payments cp JOIN project_contracts c ON c.id=cp.contract_id
               JOIN contractors k ON k.id=c.contractor_id LEFT JOIN project_portfolio p ON p.id=c.project_id
               LEFT JOIN neighborhood_actions a ON a.id=c.action_id LEFT JOIN zones z ON z.id=COALESCE(p.zone_id,a.zone_id)
               WHERE cp.id=?""",(int(payment_id),)).fetchone()
        keys=["id","contract_id","payment_type","statement_no","period_from","period_to","gross_amount","deductions","net_amount","approved_amount","paid_amount","invoice_date","approval_date","payment_date","status","notes","created_at","updated_at","contract_no","contract_title","contractor_name","zone_id","zone_name"]
        return dict(zip(keys,row)) if row else None

    def get_contract_payments(self, contract_id=None, status=None):
        clauses=[];params=[]
        if contract_id is not None:clauses.append("cp.contract_id=?");params.append(int(contract_id))
        if status:clauses.append("cp.status=?");params.append(status)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        rows=self.conn.execute(
            """SELECT cp.id,cp.contract_id,cp.payment_type,cp.statement_no,cp.period_from,cp.period_to,
                      cp.gross_amount,cp.deductions,cp.net_amount,cp.approved_amount,cp.paid_amount,
                      cp.invoice_date,cp.approval_date,cp.payment_date,cp.status,cp.notes,cp.created_at,cp.updated_at,
                      c.contract_no,c.title,k.name,COALESCE(p.zone_id,a.zone_id),z.name
               FROM contract_payments cp JOIN project_contracts c ON c.id=cp.contract_id
               JOIN contractors k ON k.id=c.contractor_id LEFT JOIN project_portfolio p ON p.id=c.project_id
               LEFT JOIN neighborhood_actions a ON a.id=c.action_id LEFT JOIN zones z ON z.id=COALESCE(p.zone_id,a.zone_id)"""+where+
            " ORDER BY COALESCE(cp.payment_date,cp.approval_date,cp.invoice_date,'9999-12-31') DESC,cp.id DESC",params).fetchall()
        keys=["id","contract_id","payment_type","statement_no","period_from","period_to","gross_amount","deductions","net_amount","approved_amount","paid_amount","invoice_date","approval_date","payment_date","status","notes","created_at","updated_at","contract_no","contract_title","contractor_name","zone_id","zone_name"]
        return [dict(zip(keys,row)) for row in rows]

    def delete_contract_payment(self, payment_id):
        before=self.get_contract_payment(payment_id)
        if not before:return False
        self.conn.execute("DELETE FROM contract_payments WHERE id=?",(int(payment_id),));self.conn.commit()
        self.log_action("delete","contract_payment",payment_id,{"statement_no":before.get("statement_no")},zone_id=before.get("zone_id"),before=before);return True

    def _refresh_contractor_average(self, contractor_id):
        score=float(self.conn.execute(
            """SELECT COALESCE(AVG(e.total_score),0) FROM contractor_evaluations e
               JOIN project_contracts c ON c.id=e.contract_id WHERE c.contractor_id=?""",(int(contractor_id),)).fetchone()[0] or 0)
        self.conn.execute("UPDATE contractors SET average_score=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(round(score,2),int(contractor_id)));self.conn.commit()
        return round(score,2)

    def add_contractor_evaluation(self, contract_id, evaluation_date, quality_score=0, schedule_score=0,
                                  safety_score=0, cooperation_score=0, documentation_score=0,
                                  evaluator="", notes=""):
        total=self.calculate_contractor_score(quality_score,schedule_score,safety_score,cooperation_score,documentation_score)
        cur=self.conn.cursor();cur.execute(
            """INSERT INTO contractor_evaluations
               (contract_id,evaluation_date,quality_score,schedule_score,safety_score,cooperation_score,
                documentation_score,total_score,evaluator,notes) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (int(contract_id),evaluation_date,float(quality_score or 0),float(schedule_score or 0),float(safety_score or 0),
             float(cooperation_score or 0),float(documentation_score or 0),total,evaluator or "",notes or ""))
        eid=cur.lastrowid;self.conn.commit();contract=self.get_contract(contract_id);self._refresh_contractor_average(contract["contractor_id"])
        self.log_action("create","contractor_evaluation",eid,{"contract_id":contract_id,"score":total},zone_id=contract.get("zone_id"));return eid

    def get_contractor_evaluations(self, contract_id=None, contractor_id=None):
        clauses=[];params=[]
        if contract_id is not None:clauses.append("e.contract_id=?");params.append(int(contract_id))
        if contractor_id is not None:clauses.append("c.contractor_id=?");params.append(int(contractor_id))
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        rows=self.conn.execute(
            """SELECT e.id,e.contract_id,e.evaluation_date,e.quality_score,e.schedule_score,e.safety_score,
                      e.cooperation_score,e.documentation_score,e.total_score,e.evaluator,e.notes,e.created_at,
                      c.contract_no,c.title,k.id,k.name,COALESCE(p.zone_id,a.zone_id),z.name
               FROM contractor_evaluations e JOIN project_contracts c ON c.id=e.contract_id
               JOIN contractors k ON k.id=c.contractor_id LEFT JOIN project_portfolio p ON p.id=c.project_id
               LEFT JOIN neighborhood_actions a ON a.id=c.action_id LEFT JOIN zones z ON z.id=COALESCE(p.zone_id,a.zone_id)"""+where+
            " ORDER BY e.evaluation_date DESC,e.id DESC",params).fetchall()
        keys=["id","contract_id","evaluation_date","quality_score","schedule_score","safety_score","cooperation_score","documentation_score","total_score","evaluator","notes","created_at","contract_no","contract_title","contractor_id","contractor_name","zone_id","zone_name"]
        return [dict(zip(keys,row)) for row in rows]

    def delete_contractor_evaluation(self, evaluation_id):
        row=self.conn.execute("SELECT contract_id FROM contractor_evaluations WHERE id=?",(int(evaluation_id),)).fetchone()
        if not row:return False
        contract=self.get_contract(row[0]);self.conn.execute("DELETE FROM contractor_evaluations WHERE id=?",(int(evaluation_id),));self.conn.commit();self._refresh_contractor_average(contract["contractor_id"])
        self.log_action("delete","contractor_evaluation",evaluation_id,{"contract_id":row[0]},zone_id=contract.get("zone_id"));return True

    def add_satisfaction_survey(self, survey_date, zone_id=None, project_id=None, action_id=None,
                                citizen_request_id=None, respondents=1, problem_resolved_percent=0,
                                quality_score=0, speed_score=0, communication_score=0, overall_score=0,
                                reopen_recommended=False, recorded_by="", comments=""):
        if all(x is None for x in (zone_id,project_id,action_id,citizen_request_id)):
            raise ValueError("نظرسنجی باید به بلوک، پروژه، اقدام یا درخواست مردمی متصل شود.")
        if zone_id is None:
            if project_id is not None:
                row=self.conn.execute("SELECT zone_id FROM project_portfolio WHERE id=?",(int(project_id),)).fetchone();zone_id=row[0] if row else None
            elif action_id is not None:
                row=self.conn.execute("SELECT zone_id FROM neighborhood_actions WHERE id=?",(int(action_id),)).fetchone();zone_id=row[0] if row else None
            elif citizen_request_id is not None:
                row=self.conn.execute("SELECT zone_id FROM citizen_requests WHERE id=?",(int(citizen_request_id),)).fetchone();zone_id=row[0] if row else None
        satisfaction=self.calculate_satisfaction_percent(quality_score,speed_score,communication_score,overall_score)
        cur=self.conn.cursor();cur.execute(
            """INSERT INTO satisfaction_surveys
               (zone_id,project_id,action_id,citizen_request_id,survey_date,respondents,problem_resolved_percent,
                quality_score,speed_score,communication_score,overall_score,satisfaction_percent,
                reopen_recommended,recorded_by,comments) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (zone_id,project_id,action_id,citizen_request_id,survey_date,max(1,int(respondents or 1)),
             max(0,min(100,float(problem_resolved_percent or 0))),float(quality_score or 0),float(speed_score or 0),
             float(communication_score or 0),float(overall_score or 0),satisfaction,1 if reopen_recommended else 0,
             recorded_by or "",comments or ""))
        sid=cur.lastrowid;self.conn.commit();self.log_action("create","satisfaction_survey",sid,{"satisfaction":satisfaction},zone_id=zone_id);return sid

    def get_satisfaction_surveys(self, zone_id=None, project_id=None, action_id=None):
        clauses=[];params=[]
        for field,value in (("s.zone_id",zone_id),("s.project_id",project_id),("s.action_id",action_id)):
            if value is not None:clauses.append(f"{field}=?");params.append(int(value))
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        rows=self.conn.execute(
            """SELECT s.id,s.zone_id,s.project_id,s.action_id,s.citizen_request_id,s.survey_date,s.respondents,
                      s.problem_resolved_percent,s.quality_score,s.speed_score,s.communication_score,s.overall_score,
                      s.satisfaction_percent,s.reopen_recommended,s.recorded_by,s.comments,s.created_at,s.updated_at,
                      z.name,p.project_code,p.title,a.title,cr.tracking_code
               FROM satisfaction_surveys s LEFT JOIN zones z ON z.id=s.zone_id
               LEFT JOIN project_portfolio p ON p.id=s.project_id LEFT JOIN neighborhood_actions a ON a.id=s.action_id
               LEFT JOIN citizen_requests cr ON cr.id=s.citizen_request_id"""+where+
            " ORDER BY s.survey_date DESC,s.id DESC",params).fetchall()
        keys=["id","zone_id","project_id","action_id","citizen_request_id","survey_date","respondents","problem_resolved_percent","quality_score","speed_score","communication_score","overall_score","satisfaction_percent","reopen_recommended","recorded_by","comments","created_at","updated_at","zone_name","project_code","project_title","action_title","tracking_code"]
        result=[]
        for row in rows:
            item=dict(zip(keys,row));item["reopen_recommended"]=bool(item["reopen_recommended"]);result.append(item)
        return result

    def delete_satisfaction_survey(self, survey_id):
        row=self.conn.execute("SELECT zone_id FROM satisfaction_surveys WHERE id=?",(int(survey_id),)).fetchone()
        if not row:return False
        self.conn.execute("DELETE FROM satisfaction_surveys WHERE id=?",(int(survey_id),));self.conn.commit();self.log_action("delete","satisfaction_survey",survey_id,{},zone_id=row[0]);return True

    def add_community_participation(self, zone_id, title, participation_type="داوطلبانه", project_id=None,
                                    action_id=None, organization_name="", contact_person="", phone="",
                                    volunteers_count=0, cash_value=0, noncash_value=0, start_date=None,
                                    end_date=None, status="فعال", description=""):
        if not str(title or "").strip():raise ValueError("عنوان مشارکت الزامی است.")
        cur=self.conn.cursor();cur.execute(
            """INSERT INTO community_participations
               (zone_id,project_id,action_id,title,participation_type,organization_name,contact_person,phone,
                volunteers_count,cash_value,noncash_value,start_date,end_date,status,description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(zone_id),project_id,action_id,str(title).strip(),participation_type or "داوطلبانه",organization_name or "",
             contact_person or "",phone or "",max(0,int(volunteers_count or 0)),float(cash_value or 0),float(noncash_value or 0),
             start_date,end_date,status or "فعال",description or ""))
        pid=cur.lastrowid;self.conn.commit();self.log_action("create","community_participation",pid,{"title":title},zone_id=zone_id);return pid

    def get_community_participations(self, zone_id=None, status=None):
        clauses=[];params=[]
        if zone_id is not None:clauses.append("cp.zone_id=?");params.append(int(zone_id))
        if status:clauses.append("cp.status=?");params.append(status)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        rows=self.conn.execute(
            """SELECT cp.id,cp.zone_id,cp.project_id,cp.action_id,cp.title,cp.participation_type,
                      cp.organization_name,cp.contact_person,cp.phone,cp.volunteers_count,cp.cash_value,
                      cp.noncash_value,cp.start_date,cp.end_date,cp.status,cp.description,cp.created_at,cp.updated_at,
                      z.name,p.project_code,p.title,a.title
               FROM community_participations cp JOIN zones z ON z.id=cp.zone_id
               LEFT JOIN project_portfolio p ON p.id=cp.project_id LEFT JOIN neighborhood_actions a ON a.id=cp.action_id"""+where+
            " ORDER BY cp.id DESC",params).fetchall()
        keys=["id","zone_id","project_id","action_id","title","participation_type","organization_name","contact_person","phone","volunteers_count","cash_value","noncash_value","start_date","end_date","status","description","created_at","updated_at","zone_name","project_code","project_title","action_title"]
        return [dict(zip(keys,row)) for row in rows]

    def delete_community_participation(self, participation_id):
        row=self.conn.execute("SELECT zone_id,title FROM community_participations WHERE id=?",(int(participation_id),)).fetchone()
        if not row:return False
        self.conn.execute("DELETE FROM community_participations WHERE id=?",(int(participation_id),));self.conn.commit();self.log_action("delete","community_participation",participation_id,{"title":row[1]},zone_id=row[0]);return True

    def get_contract_management_alerts(self, zone_id=None, days_ahead=14):
        today=datetime.now().date();threshold=today+timedelta(days=int(days_ahead or 14));alerts=[]
        for c in self.get_contracts(zone_id=zone_id):
            end=self._date_object(c.get("end_date"))
            if end and c.get("status") not in ("مختومه","تسویه","فسخ‌شده"):
                if end<today:alerts.append({"key":f"contract_overdue:{c['id']}","severity":"بحرانی","type":"قرارداد معوق","title":c["title"],"zone_name":c.get("zone_name"),"due_date":c.get("end_date"),"message":f"قرارداد {c.get('contract_no')} از تاریخ پایان عبور کرده است."})
                elif end<=threshold:alerts.append({"key":f"contract_due:{c['id']}","severity":"مهم","type":"پایان قرارداد","title":c["title"],"zone_name":c.get("zone_name"),"due_date":c.get("end_date"),"message":"قرارداد به پایان دوره نزدیک است."})
            if float(c.get("paid_total") or 0)>float(c.get("amount") or 0)>0:
                alerts.append({"key":f"contract_overpay:{c['id']}","severity":"بحرانی","type":"پرداخت بیش از مبلغ قرارداد","title":c["title"],"zone_name":c.get("zone_name"),"due_date":None,"message":"مجموع پرداخت از مبلغ قرارداد بیشتر است."})
        for p in self.get_contract_payments():
            if zone_id is not None and p.get("zone_id")!=int(zone_id):continue
            if p.get("status") in ("تأییدشده","پرداخت جزئی") and float(p.get("approved_amount") or 0)>float(p.get("paid_amount") or 0):
                alerts.append({"key":f"payment_pending:{p['id']}","severity":"فوری","type":"مطالبه پرداخت‌نشده","title":f"{p.get('contract_no')} / {p.get('statement_no') or p.get('payment_type')}","zone_name":p.get("zone_name"),"due_date":p.get("approval_date"),"message":"مبلغ تأییدشده هنوز کامل پرداخت نشده است."})
        for s in self.get_satisfaction_surveys(zone_id=zone_id):
            if float(s.get("satisfaction_percent") or 0)<50 or s.get("reopen_recommended"):
                alerts.append({"key":f"satisfaction_low:{s['id']}","severity":"فوری","type":"رضایت پایین","title":s.get("project_title") or s.get("action_title") or s.get("zone_name") or "نظرسنجی","zone_name":s.get("zone_name"),"due_date":s.get("survey_date"),"message":f"رضایت ثبت‌شده {float(s.get('satisfaction_percent') or 0):.0f}٪ است و نیاز به بازبینی دارد."})
        order={"بحرانی":0,"فوری":1,"مهم":2,"اطلاع":3};return sorted(alerts,key=lambda x:(order.get(x.get("severity"),9),x.get("due_date") or "9999-12-31"))

    def get_contract_management_summary(self, zone_id=None):
        contracts=self.get_contracts(zone_id=zone_id);payments=[]
        contract_ids={c["id"] for c in contracts}
        for p in self.get_contract_payments():
            if p["contract_id"] in contract_ids:payments.append(p)
        surveys=self.get_satisfaction_surveys(zone_id=zone_id)
        parts=self.get_community_participations(zone_id=zone_id)
        amount=sum(float(c.get("amount") or 0) for c in contracts);paid=sum(float(p.get("paid_amount") or 0) for p in payments)
        approved=sum(float(p.get("approved_amount") or 0) for p in payments)
        weighted_satisfaction=sum(float(s.get("satisfaction_percent") or 0)*max(1,int(s.get("respondents") or 1)) for s in surveys)
        respondents=sum(max(1,int(s.get("respondents") or 1)) for s in surveys)
        contractors={c.get("contractor_id") for c in contracts}
        return {"contractors_count":len(contractors),"contracts_count":len(contracts),
                "active_contracts":sum(1 for c in contracts if c.get("status")=="فعال"),
                "contract_amount":round(amount,2),"approved_payments":round(approved,2),"paid_amount":round(paid,2),
                "remaining_amount":round(amount-paid,2),"payment_percent":round(paid/amount*100,2) if amount else 0,
                "average_satisfaction":round(weighted_satisfaction/respondents,2) if respondents else 0,
                "survey_respondents":respondents,"low_satisfaction_count":sum(1 for s in surveys if float(s.get("satisfaction_percent") or 0)<50),
                "participations_count":len(parts),"volunteers_count":sum(int(x.get("volunteers_count") or 0) for x in parts),
                "community_value":round(sum(float(x.get("cash_value") or 0)+float(x.get("noncash_value") or 0) for x in parts),2),
                "alerts_count":len(self.get_contract_management_alerts(zone_id=zone_id))}

    def global_search(self, query, limit=100):
        """جستجوی یکپارچه در بلوک، معبر، مکان، مسجد، شورا و پرونده‌های مدیریتی."""
        term = (query or "").strip()
        if len(term) < 2:
            return []
        like = f"%{term}%"
        results = []

        def add_rows(sql, params, entity_type, title_index=1, subtitle_builder=None):
            for row in self.conn.execute(sql, params).fetchall():
                if len(results) >= int(limit):
                    break
                subtitle = subtitle_builder(row) if subtitle_builder else ""
                results.append({
                    "entity_type": entity_type, "entity_id": row[0], "title": row[title_index] or "",
                    "subtitle": subtitle, "zone_id": row[-1] if isinstance(row[-1], int) else None,
                })

        add_rows("SELECT id, name, id FROM zones WHERE name LIKE ? ORDER BY name LIMIT ?",
                 (like, limit), "zone", subtitle_builder=lambda r: "بلوک / منطقه")
        add_rows("SELECT id, name, highway_type, zone_id FROM streets WHERE name LIKE ? ORDER BY name LIMIT ?",
                 (like, limit), "street", subtitle_builder=lambda r: f"معبر — {r[2] or 'نوع نامشخص'}")
        add_rows("SELECT id, name, category, zone_id FROM places WHERE name LIKE ? OR address LIKE ? ORDER BY name LIMIT ?",
                 (like, like, limit), "place", subtitle_builder=lambda r: f"مکان — {r[2] or 'سایر'}")
        for row in self.conn.execute(
            """SELECT m.id, m.name, GROUP_CONCAT(z.name, '، '), MIN(z.id)
               FROM mosques m LEFT JOIN zone_mosques zm ON zm.mosque_id=m.id
               LEFT JOIN zones z ON z.id=zm.zone_id
               WHERE m.name LIKE ? OR m.aliases LIKE ? GROUP BY m.id LIMIT ?""",
            (like, like, limit),
        ).fetchall():
            results.append({"entity_type": "mosque", "entity_id": row[0], "title": row[1],
                            "subtitle": "مسجد" + (f" — {row[2]}" if row[2] else ""), "zone_id": row[3]})
        add_rows("""SELECT id, first_name || ' ' || last_name, position, zone_id FROM council_members
                    WHERE first_name LIKE ? OR last_name LIKE ? OR mobile LIKE ? OR national_code LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "council_member",
                 subtitle_builder=lambda r: f"عضو شورای محله — {r[2] or 'عضو'}")
        add_rows("""SELECT c.id, c.title, z.name, c.zone_id FROM neighborhood_committees c
                    JOIN zones z ON z.id=c.zone_id
                    WHERE c.title LIKE ? OR c.chair_name LIKE ? OR c.secretary_name LIKE ? OR c.recommended_agencies LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "committee",
                 subtitle_builder=lambda r: f"کمیته محله‌محور — {r[2] or ''}")
        add_rows("""SELECT m.id, m.person_name, c.title, c.zone_id FROM committee_members m
                    JOIN neighborhood_committees c ON c.id=m.committee_id
                    WHERE m.person_name LIKE ? OR m.mobile LIKE ? OR m.agency_name LIKE ? OR m.member_role LIKE ? OR m.national_code LIKE ? LIMIT ?""",
                 (like, like, like, like, like, limit), "committee_member",
                 subtitle_builder=lambda r: f"عضو کمیته — {r[2] or ''}")
        add_rows("""SELECT id, title, category, zone_id FROM neighborhood_issues
                    WHERE title LIKE ? OR description LIKE ? OR related_office LIKE ? LIMIT ?""",
                 (like, like, like, limit), "issue", subtitle_builder=lambda r: f"مسئله — {r[2] or 'سایر'}")
        add_rows("""SELECT id, title, status, zone_id FROM neighborhood_actions
                    WHERE title LIKE ? OR description LIKE ? OR responsible_office LIKE ? LIMIT ?""",
                 (like, like, like, limit), "action", subtitle_builder=lambda r: f"اقدام — {r[2] or ''}")
        add_rows("""SELECT id, full_name, role_title, zone_id FROM social_council_members
                    WHERE full_name LIKE ? OR national_code LIKE ? OR mobile LIKE ? OR role_title LIKE ? OR agency_name LIKE ? LIMIT ?""",
                 (like, like, like, like, like, limit), "social_council_member",
                 subtitle_builder=lambda r: f"عضو شورای اجتماعی — {r[2] or ''}")
        social_role = (self.current_user or {}).get("role")
        social_conf_clause = "" if social_role == "admin" else (" AND confidentiality<>'فقط مدیر سیستم'" if social_role == "manager" else " AND confidentiality IN ('عمومی','داخلی')")
        add_rows(f"""SELECT id, title, category || ' / ' || urgency, zone_id FROM social_issues
                    WHERE (title LIKE ? OR description LIKE ? OR responsible_agency LIKE ?) {social_conf_clause} LIMIT ?""",
                 (like, like, like, limit), "social_issue", subtitle_builder=lambda r: f"مسئله اجتماعی — {r[2] or ''}")
        add_rows("""SELECT id, title, meeting_date, zone_id FROM social_council_meetings
                    WHERE title LIKE ? OR agenda LIKE ? OR place_name LIKE ? OR minutes_text LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "social_meeting",
                 subtitle_builder=lambda r: f"جلسه شورای اجتماعی — {r[2] or ''}")
        add_rows("""SELECT id, title, status, zone_id FROM social_resolutions
                    WHERE title LIKE ? OR description LIKE ? OR responsible_agency LIKE ? OR responsible_person LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "social_resolution",
                 subtitle_builder=lambda r: f"مصوبه شورای اجتماعی — {r[2] or ''}")
        add_rows("""SELECT id, title, status, zone_id FROM social_action_plans
                    WHERE title LIKE ? OR action_description LIKE ? OR responsible_agency LIKE ? OR responsible_person LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "social_action_plan",
                 subtitle_builder=lambda r: f"برنامه اقدام اجتماعی — {r[2] or ''}")
        add_rows("""SELECT id, title, status, zone_id FROM execution_cases
                    WHERE title LIKE ? OR description LIKE ? OR responsible_agency LIKE ? OR responsible_person LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "execution_case",
                 subtitle_builder=lambda r: f"پرونده پیگیری — {r[2] or ''}")
        add_rows("""SELECT id, title, status, zone_id FROM citizen_requests
                    WHERE title LIKE ? OR description LIKE ? OR tracking_code LIKE ? OR mobile LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "citizen_request",
                 subtitle_builder=lambda r: f"درخواست مردمی — {r[2] or ''}")
        add_rows("""SELECT id, name, category, NULL FROM management_agencies
                    WHERE name LIKE ? OR contact_person LIKE ? OR phone LIKE ? LIMIT ?""",
                 (like, like, like, limit), "agency", subtitle_builder=lambda r: f"دستگاه — {r[2] or ''}")
        add_rows("""SELECT id, letter_number || ' — ' || subject, direction, zone_id
                    FROM correspondence_letters
                    WHERE letter_number LIKE ? OR subject LIKE ? OR sender LIKE ? OR recipient LIKE ? OR description LIKE ?
                    LIMIT ?""",
                 (like, like, like, like, like, limit), "letter",
                 subtitle_builder=lambda r: f"نامه {r[2] or ''}")
        add_rows("""SELECT id, title, status, zone_id FROM approval_requests
                    WHERE title LIKE ? OR notes LIKE ? OR entity_type LIKE ? LIMIT ?""",
                 (like, like, like, limit), "approval",
                 subtitle_builder=lambda r: f"گردش تأیید — {r[2] or ''}")
        add_rows("""SELECT id, name, template_type, NULL FROM document_templates
                    WHERE name LIKE ? OR subject_template LIKE ? OR body_template LIKE ? LIMIT ?""",
                 (like, like, like, limit), "document_template",
                 subtitle_builder=lambda r: f"قالب اداری — {r[2] or ''}")
        add_rows("""SELECT id, title, related_entity_type, zone_id FROM generated_documents
                    WHERE title LIKE ? OR content LIKE ? LIMIT ?""",
                 (like, like, limit), "generated_document",
                 subtitle_builder=lambda r: f"سند تولیدشده — {r[2] or 'بدون ارتباط'}")
        add_rows("""SELECT id, title, fiscal_year, zone_id FROM annual_operational_programs
                    WHERE title LIKE ? OR strategic_goal LIKE ? OR responsible_agency LIKE ? OR program_manager LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "annual_program",
                 subtitle_builder=lambda r: f"برنامه عملیاتی — سال {r[2] or '—'}")
        add_rows("""SELECT id, project_code || ' — ' || title, status, zone_id FROM project_portfolio
                    WHERE title LIKE ? OR project_code LIKE ? OR responsible_agency LIKE ? OR project_manager LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "project",
                 subtitle_builder=lambda r: f"پروژه — {r[2] or ''}")
        add_rows("""SELECT m.id, m.title, pr.title, pr.zone_id FROM project_milestones m
                    JOIN project_portfolio pr ON pr.id=m.project_id
                    WHERE m.title LIKE ? OR m.notes LIKE ? OR pr.title LIKE ? LIMIT ?""",
                 (like, like, like, limit), "project_milestone",
                 subtitle_builder=lambda r: f"نقطه عطف — {r[2] or ''}")
        add_rows("""SELECT i.id, i.title, COALESCE(pr.title,p.title), COALESCE(pr.zone_id,p.zone_id)
                    FROM project_indicators i
                    LEFT JOIN project_portfolio pr ON pr.id=i.project_id
                    LEFT JOIN annual_operational_programs p ON p.id=i.program_id
                    WHERE i.title LIKE ? OR i.notes LIKE ? OR i.unit LIKE ? LIMIT ?""",
                 (like, like, like, limit), "project_indicator",
                 subtitle_builder=lambda r: f"شاخص پروژه — {r[2] or ''}")
        add_rows("""SELECT r.id, r.title, r.risk_level, r.zone_id FROM project_risks r
                    WHERE r.title LIKE ? OR r.owner LIKE ? OR r.mitigation LIKE ? LIMIT ?""",
                 (like, like, like, limit), "project_risk",
                 subtitle_builder=lambda r: f"ریسک پروژه — {r[2] or ''}")
        add_rows("""SELECT c.id, c.title, c.status, COALESCE(pr.zone_id,p.zone_id)
                    FROM project_change_requests c
                    LEFT JOIN project_portfolio pr ON pr.id=c.project_id
                    LEFT JOIN annual_operational_programs p ON p.id=c.program_id
                    WHERE c.title LIKE ? OR c.reason LIKE ? OR c.requested_by LIKE ? LIMIT ?""",
                 (like, like, like, limit), "project_change",
                 subtitle_builder=lambda r: f"درخواست تغییر — {r[2] or ''}")
        add_rows("""SELECT c.id, c.contract_no || ' — ' || c.title, k.name, COALESCE(p.zone_id,a.zone_id)
                    FROM project_contracts c JOIN contractors k ON k.id=c.contractor_id
                    LEFT JOIN project_portfolio p ON p.id=c.project_id
                    LEFT JOIN neighborhood_actions a ON a.id=c.action_id
                    WHERE c.contract_no LIKE ? OR c.title LIKE ? OR k.name LIKE ? LIMIT ?""",
                 (like, like, like, limit), "contract",
                 subtitle_builder=lambda r: f"قرارداد — {r[2] or ''}")
        add_rows("""SELECT id, name, specialty, NULL FROM contractors
                    WHERE name LIKE ? OR manager_name LIKE ? OR national_id LIKE ? OR specialty LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "contractor",
                 subtitle_builder=lambda r: f"پیمانکار — {r[2] or ''}")
        add_rows("""SELECT s.id, COALESCE(p.title,a.title,z.name), s.satisfaction_percent, s.zone_id
                    FROM satisfaction_surveys s LEFT JOIN zones z ON z.id=s.zone_id
                    LEFT JOIN project_portfolio p ON p.id=s.project_id LEFT JOIN neighborhood_actions a ON a.id=s.action_id
                    WHERE s.comments LIKE ? OR p.title LIKE ? OR a.title LIKE ? OR z.name LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "satisfaction_survey",
                 subtitle_builder=lambda r: f"رضایت مردمی — {float(r[2] or 0):.0f}٪")
        add_rows("""SELECT cp.id, cp.title, cp.participation_type, cp.zone_id
                    FROM community_participations cp
                    WHERE cp.title LIKE ? OR cp.organization_name LIKE ? OR cp.contact_person LIKE ? OR cp.description LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "community_participation",
                 subtitle_builder=lambda r: f"مشارکت مردمی — {r[2] or ''}")
        add_rows("""SELECT id, entity_type || ' / ' || entity_uid, lifecycle_status, zone_id
                    FROM record_governance
                    WHERE entity_type LIKE ? OR entity_uid LIKE ? OR data_owner LIKE ? OR notes LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "governance_record",
                 subtitle_builder=lambda r: f"حکمرانی داده — {r[2] or ''}")
        add_rows("""SELECT id, entity_type || ' / ' || entity_uid, status, zone_id
                    FROM sync_conflicts
                    WHERE entity_type LIKE ? OR entity_uid LIKE ? OR source_device LIKE ? LIMIT ?""",
                 (like, like, like, limit), "sync_conflict",
                 subtitle_builder=lambda r: f"تعارض همگام‌سازی — {r[2] or ''}")
        add_rows("""SELECT id, title, status, NULL FROM public_portal_publications
                    WHERE title LIKE ? OR output_path LIKE ? LIMIT ?""",
                 (like, like, limit), "publication",
                 subtitle_builder=lambda r: f"انتشار عمومی — {r[2] or ''}")
        add_rows("""SELECT id, title, start_date, zone_id FROM management_calendar_events
                    WHERE title LIKE ? OR description LIKE ? OR responsible_person LIKE ? OR location LIKE ? LIMIT ?""",
                 (like, like, like, like, limit), "calendar_event",
                 subtitle_builder=lambda r: f"رویداد تقویم — {r[2] or ''}")
        return results[:int(limit)]

