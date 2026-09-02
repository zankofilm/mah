# -*- coding: utf-8 -*-
"""Database persistence for block messaging and delivery history."""
from __future__ import annotations

import re
import hashlib
import json
from datetime import datetime, timedelta


_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_mobile(value):
    text = str(value or "").translate(_FA_DIGITS).strip()
    text = re.sub(r"[^0-9+]", "", text)
    if text.startswith("+98"):
        text = "0" + text[3:]
    elif text.startswith("0098"):
        text = "0" + text[4:]
    elif text.startswith("98") and len(text) == 12:
        text = "0" + text[2:]
    elif text.startswith("9") and len(text) == 10:
        text = "0" + text
    return text


def is_valid_mobile(value):
    return bool(re.fullmatch(r"09\d{9}", normalize_mobile(value)))


class MessagingMixin:
    def _create_message_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS message_api_settings (
                id INTEGER PRIMARY KEY CHECK (id=1),
                enabled INTEGER DEFAULT 1,
                provider TEXT DEFAULT 'demo',
                api_url TEXT DEFAULT '',
                api_key TEXT DEFAULT '',
                sender_id TEXT DEFAULT '',
                timeout_seconds INTEGER DEFAULT 15,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO message_api_settings
            (id, enabled, provider, api_url, api_key, sender_id, timeout_seconds)
            VALUES (1, 1, 'demo', '', '', '', 15)
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS message_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                recipient_scope TEXT DEFAULT 'all',
                priority TEXT DEFAULT 'normal',
                provider TEXT,
                total_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'در حال ارسال',
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS message_deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                recipient_name TEXT,
                mobile TEXT NOT NULL,
                source_type TEXT,
                source_id INTEGER,
                status TEXT DEFAULT 'در انتظار',
                provider_message_id TEXT,
                response_text TEXT,
                error_text TEXT,
                sent_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (campaign_id) REFERENCES message_campaigns(id) ON DELETE CASCADE
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_message_campaign_zone ON message_campaigns(zone_id, created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_message_delivery_campaign ON message_deliveries(campaign_id, status)")
        for table, column, definition in [
            ("message_campaigns", "idempotency_key", "TEXT"),
            ("message_campaigns", "paused_at", "TEXT"),
            ("message_campaigns", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("message_deliveries", "attempt_count", "INTEGER DEFAULT 0"),
            ("message_deliveries", "next_attempt_at", "TEXT"),
            ("message_deliveries", "delivery_status", "TEXT DEFAULT 'نامشخص'"),
            ("message_deliveries", "delivered_at", "TEXT"),
            ("message_deliveries", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ]:
            try:
                self._ensure_column(table, column, definition)
            except Exception:
                pass
        cur.execute("CREATE INDEX IF NOT EXISTS idx_message_delivery_retry ON message_deliveries(status,next_attempt_at)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_message_campaign_idempotency ON message_campaigns(idempotency_key) WHERE idempotency_key IS NOT NULL")
        self.conn.commit()

    def get_message_api_settings(self):
        row = self.conn.execute(
            "SELECT enabled, provider, api_url, api_key, sender_id, timeout_seconds, updated_at "
            "FROM message_api_settings WHERE id=1"
        ).fetchone()
        if not row:
            return {
                "enabled": True, "provider": "demo", "api_url": "", "api_key": "",
                "sender_id": "", "timeout_seconds": 15, "updated_at": "",
            }
        return {
            "enabled": bool(row[0]), "provider": row[1] or "demo", "api_url": row[2] or "",
            "api_key": self.decrypt_secret(row[3]) if row[3] else "", "sender_id": row[4] or "",
            "timeout_seconds": int(row[5] or 15), "updated_at": row[6] or "",
        }

    def set_message_api_settings(self, enabled, provider="demo", api_url="", api_key="", sender_id="", timeout_seconds=15):
        self.require_permission("system_settings")
        provider = (provider or "demo").strip()
        timeout_seconds = max(3, min(int(timeout_seconds or 15), 120))
        self.conn.execute(
            """
            INSERT INTO message_api_settings
            (id, enabled, provider, api_url, api_key, sender_id, timeout_seconds, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                enabled=excluded.enabled, provider=excluded.provider, api_url=excluded.api_url,
                api_key=excluded.api_key, sender_id=excluded.sender_id,
                timeout_seconds=excluded.timeout_seconds, updated_at=CURRENT_TIMESTAMP
            """,
            (1 if enabled else 0, provider, (api_url or "").strip(), self.encrypt_secret((api_key or "").strip()),
             (sender_id or "").strip(), timeout_seconds),
        )
        self.conn.commit()
        try:
            self.log_action("message_api_settings_updated", "message_settings", 1, {"provider": provider, "enabled": bool(enabled)})
        except Exception:
            pass

    def get_message_recipients(self, zone_id, scope="all"):
        zone_id = int(zone_id)
        scope = scope or "all"
        recipients = []

        if scope in {"all", "trusted"}:
            rows = self.conn.execute(
                """SELECT id, TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')), mobile,
                          COALESCE(position, 'معتمد بلوک')
                   FROM council_members WHERE zone_id=? AND COALESCE(member_group, '')='معتمد'
                     AND TRIM(COALESCE(mobile,''))<>''""",
                (zone_id,),
            ).fetchall()
            recipients.extend({"source_type": "trusted", "source_id": r[0], "name": r[1].strip(),
                               "mobile": r[2], "group": r[3] or "معتمد بلوک"} for r in rows)

        if scope in {"all", "council"}:
            rows = self.conn.execute(
                """SELECT id, TRIM(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')), mobile,
                          COALESCE(position, member_group, 'عضو شورای بلوک')
                   FROM council_members WHERE zone_id=? AND TRIM(COALESCE(mobile,''))<>''""",
                (zone_id,),
            ).fetchall()
            recipients.extend({"source_type": "council", "source_id": r[0], "name": r[1].strip(),
                               "mobile": r[2], "group": r[3] or "عضو شورای بلوک"} for r in rows)

        if scope in {"all", "committees"}:
            rows = self.conn.execute(
                """SELECT m.id, m.person_name, m.mobile,
                          COALESCE(c.title, 'عضو کمیته') || ' — ' || COALESCE(m.member_role, 'عضو')
                   FROM committee_members m
                   JOIN neighborhood_committees c ON c.id=m.committee_id
                   WHERE c.zone_id=? AND COALESCE(m.status,'فعال')='فعال'
                     AND TRIM(COALESCE(m.mobile,''))<>''""",
                (zone_id,),
            ).fetchall()
            recipients.extend({"source_type": "committee", "source_id": r[0], "name": r[1].strip(),
                               "mobile": r[2], "group": r[3] or "عضو کمیته"} for r in rows)

        if scope in {"all", "social"}:
            rows = self.conn.execute(
                """SELECT id, full_name, mobile, COALESCE(role_title, 'عضو شورای اجتماعی')
                   FROM social_council_members
                   WHERE zone_id=? AND COALESCE(status,'فعال')='فعال'
                     AND TRIM(COALESCE(mobile,''))<>''""",
                (zone_id,),
            ).fetchall()
            recipients.extend({"source_type": "social", "source_id": r[0], "name": r[1].strip(),
                               "mobile": r[2], "group": r[3] or "عضو شورای اجتماعی"} for r in rows)

        # یک شماره فقط یک بار نمایش داده می‌شود؛ منبع نخست حفظ می‌شود.
        unique = {}
        for item in recipients:
            mobile = normalize_mobile(item.get("mobile"))
            if not is_valid_mobile(mobile):
                continue
            item = dict(item)
            item["mobile"] = mobile
            unique.setdefault(mobile, item)
        return sorted(unique.values(), key=lambda x: (x.get("group") or "", x.get("name") or ""))

    def create_message_campaign(self, zone_id, title, body, recipient_scope, priority, provider, recipients):
        self.require_permission("messaging")
        actor = self.get_current_user() or {}
        normalized_mobiles = sorted({normalize_mobile(item.get("mobile")) for item in recipients if item.get("mobile")})
        raw_key = json.dumps({
            "zone": int(zone_id), "title": (title or "").strip(), "body": (body or "").strip(),
            "scope": recipient_scope or "all", "provider": provider or "demo", "mobiles": normalized_mobiles,
        }, ensure_ascii=False, sort_keys=True)
        # کلید پنج‌دقیقه‌ای از ثبت دوباره یک عملیات یکسان در اثر دوبار کلیک جلوگیری می‌کند.
        time_bucket = datetime.now().strftime("%Y%m%d%H") + str(datetime.now().minute // 5)
        idempotency_key = hashlib.sha256((time_bucket + raw_key).encode("utf-8")).hexdigest()
        existing = self.conn.execute(
            "SELECT id,status FROM message_campaigns WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if existing:
            raise ValueError(f"این عملیات ارسال قبلاً ثبت شده است (شناسه {existing[0]}، وضعیت {existing[1]}).")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO message_campaigns
               (zone_id, title, body, recipient_scope, priority, provider, total_count, created_by, idempotency_key, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'در انتظار', CURRENT_TIMESTAMP)""",
            (int(zone_id), (title or "").strip(), (body or "").strip(), recipient_scope or "all",
             priority or "normal", provider or "demo", len(recipients), actor.get("id"), idempotency_key),
        )
        campaign_id = cur.lastrowid
        for recipient in recipients:
            cur.execute(
                """INSERT INTO message_deliveries
                   (campaign_id, recipient_name, mobile, source_type, source_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (campaign_id, recipient.get("name"), normalize_mobile(recipient.get("mobile")),
                 recipient.get("source_type"), recipient.get("source_id")),
            )
        self.conn.commit()
        try:
            self.log_action("message_campaign_created", "message_campaign", campaign_id,
                            {"zone_id": zone_id, "recipients": len(recipients)}, zone_id=zone_id)
        except Exception:
            pass
        return campaign_id

    def record_message_delivery(self, campaign_id, mobile, success, provider_message_id="", response_text="", error_text=""):
        status = "ارسال‌شده" if success else "ناموفق"
        next_attempt = None if success else (datetime.now() + timedelta(minutes=2)).isoformat(timespec="seconds")
        self.conn.execute(
            """UPDATE message_deliveries
               SET status=?, provider_message_id=?, response_text=?, error_text=?, sent_at=?,
                   attempt_count=COALESCE(attempt_count,0)+1, next_attempt_at=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=(SELECT id FROM message_deliveries
                         WHERE campaign_id=? AND mobile=? AND status IN ('در انتظار','ناموفق','در حال ارسال') ORDER BY id LIMIT 1)""",
            (status, str(provider_message_id or ""), str(response_text or "")[:2000],
             str(error_text or "")[:2000], datetime.now().isoformat(timespec="seconds"), next_attempt,
             int(campaign_id), normalize_mobile(mobile)),
        )
        self.conn.commit()

    def finish_message_campaign(self, campaign_id):
        row = self.conn.execute(
            """SELECT COUNT(*),
                      SUM(CASE WHEN status='ارسال‌شده' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN status='ناموفق' THEN 1 ELSE 0 END)
               FROM message_deliveries WHERE campaign_id=?""",
            (int(campaign_id),),
        ).fetchone()
        total, success, failed = int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
        pending = max(0, total - success - failed)
        if pending:
            status = "در انتظار ادامه"
        elif total and success == total:
            status = "تکمیل‌شده"
        elif success:
            status = "تکمیل با خطا"
        else:
            status = "ناموفق"
        self.conn.execute(
            """UPDATE message_campaigns SET total_count=?, success_count=?, failed_count=?,
                      status=?, completed_at=CURRENT_TIMESTAMP WHERE id=?""",
            (total, success, failed, status, int(campaign_id)),
        )
        self.conn.commit()
        return {"total": total, "success": success, "failed": failed, "status": status}

    def pause_message_campaign(self, campaign_id):
        self.conn.execute(
            "UPDATE message_campaigns SET status='متوقف‌شده',paused_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(campaign_id),),
        )
        self.conn.execute(
            "UPDATE message_deliveries SET status='متوقف' WHERE campaign_id=? AND status='در انتظار'",
            (int(campaign_id),),
        )
        self.conn.commit()
        self.log_action("message_campaign_paused", "message_campaign", campaign_id)
        return True

    def resume_message_campaign(self, campaign_id):
        self.conn.execute(
            "UPDATE message_campaigns SET status='در انتظار ادامه',paused_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(campaign_id),),
        )
        self.conn.execute(
            "UPDATE message_deliveries SET status='در انتظار',next_attempt_at=NULL WHERE campaign_id=? AND status='متوقف'",
            (int(campaign_id),),
        )
        self.conn.commit()
        self.log_action("message_campaign_resumed", "message_campaign", campaign_id)
        return True

    def retry_failed_message_deliveries(self, campaign_id, max_attempts=3):
        cur = self.conn.execute(
            """UPDATE message_deliveries SET status='در انتظار',next_attempt_at=NULL,error_text='',updated_at=CURRENT_TIMESTAMP
               WHERE campaign_id=? AND status='ناموفق' AND COALESCE(attempt_count,0)<?""",
            (int(campaign_id), int(max_attempts)),
        )
        self.conn.execute(
            "UPDATE message_campaigns SET status='در انتظار ادامه',completed_at=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(campaign_id),),
        )
        self.conn.commit()
        self.log_action("message_delivery_retry_scheduled", "message_campaign", campaign_id, {"count": cur.rowcount})
        return int(cur.rowcount or 0)

    def get_pending_message_deliveries(self, campaign_id, limit=500):
        rows = self.conn.execute(
            """SELECT id,campaign_id,recipient_name,mobile,status,attempt_count,next_attempt_at
               FROM message_deliveries WHERE campaign_id=? AND status='در انتظار'
               ORDER BY id LIMIT ?""", (int(campaign_id), int(limit))
        ).fetchall()
        keys = ["id","campaign_id","recipient_name","mobile","status","attempt_count","next_attempt_at"]
        return [dict(zip(keys,row)) for row in rows]

    def update_delivery_receipt(self, provider_message_id, delivered, response_text=""):
        status = "تحویل‌شده" if delivered else "تحویل‌ناموفق"
        delivered_at = datetime.now().isoformat(timespec="seconds") if delivered else None
        cur = self.conn.execute(
            """UPDATE message_deliveries SET delivery_status=?,delivered_at=?,response_text=?,updated_at=CURRENT_TIMESTAMP
               WHERE provider_message_id=?""",
            (status, delivered_at, str(response_text or "")[:2000], str(provider_message_id or "")),
        )
        self.conn.commit()
        return int(cur.rowcount or 0)

    def get_message_campaign(self, campaign_id):
        row = self.conn.execute(
            """SELECT id,zone_id,title,body,recipient_scope,priority,provider,total_count,success_count,
                      failed_count,status,created_at,completed_at,created_by
               FROM message_campaigns WHERE id=?""", (int(campaign_id),)
        ).fetchone()
        if not row:
            return None
        keys = ["id","zone_id","title","body","recipient_scope","priority","provider","total_count",
                "success_count","failed_count","status","created_at","completed_at","created_by"]
        return dict(zip(keys,row))

    def is_message_campaign_paused(self, campaign_id):
        row = self.conn.execute("SELECT status FROM message_campaigns WHERE id=?", (int(campaign_id),)).fetchone()
        return bool(row and row[0] == "متوقف‌شده")

    def get_message_campaigns(self, limit=500):
        rows = self.conn.execute(
            """SELECT c.id, c.zone_id, z.name, c.title, c.body, c.recipient_scope, c.priority,
                      c.provider, c.total_count, c.success_count, c.failed_count, c.status,
                      c.created_at, c.completed_at, COALESCE(u.full_name, u.username, '')
               FROM message_campaigns c
               LEFT JOIN zones z ON z.id=c.zone_id
               LEFT JOIN app_users u ON u.id=c.created_by
               ORDER BY c.id DESC LIMIT ?""",
            (int(limit),),
        ).fetchall()
        keys = ["id", "zone_id", "zone_name", "title", "body", "recipient_scope", "priority",
                "provider", "total_count", "success_count", "failed_count", "status",
                "created_at", "completed_at", "created_by_name"]
        return [dict(zip(keys, row)) for row in rows]

    def get_message_deliveries(self, campaign_id):
        rows = self.conn.execute(
            """SELECT id, campaign_id, recipient_name, mobile, source_type, source_id, status,
                      provider_message_id, response_text, error_text, sent_at, created_at,
                      COALESCE(attempt_count,0),next_attempt_at,COALESCE(delivery_status,'نامشخص'),delivered_at
               FROM message_deliveries WHERE campaign_id=? ORDER BY id""",
            (int(campaign_id),),
        ).fetchall()
        keys = ["id", "campaign_id", "recipient_name", "mobile", "source_type", "source_id", "status",
                "provider_message_id", "response_text", "error_text", "sent_at", "created_at",
                "attempt_count", "next_attempt_at", "delivery_status", "delivered_at"]
        return [dict(zip(keys, row)) for row in rows]
