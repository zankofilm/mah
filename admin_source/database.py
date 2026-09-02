# -*- coding: utf-8 -*-
"""
ماژول مدیریت دیتابیس SQLite برای ذخیره:
- محدوده شهر (نقاط مرزی)
- خیابان‌ها و کوچه‌ها
- اماکن (مدارس، ادارات دولتی و ...)
- تایل‌های نقشه (برای استفاده آفلاین)
"""

import sqlite3
import json
import os
import hashlib
import hmac
import secrets
import uuid
import shutil
import mimetypes
import zipfile
import re
import math
from datetime import datetime, timedelta

from mosques_data import MOSQUES
from geometry_utils import geometry_hash, point_in_polygon, polygon_metrics
from runtime_paths import get_database_path
from jalali_utils import jalali_to_iso
from database_council_facilities import CouncilFacilitiesMixin
from database_social_council import SocialCouncilMixin
from database_projects_contracts import ProjectContractsMixin
from database_client_exchange import ClientExchangeMixin
from database_messaging import MessagingMixin
from database_hardening import HardeningMixin
from database_users import UserSecurityMixin
from database_backup_security import BackupSecurityMixin
from database_people import PeopleRegistryMixin
from database_population import PopulationEstimationMixin
from security_service import validate_password_policy, generate_strong_password, is_encrypted_backup_file

DB_PATH = get_database_path()
SCHEMA_VERSION = 7641


DEFAULT_NEIGHBORHOOD_COMMITTEES = [
    {"code": "infrastructure", "title": "عمران، خدمات محلی و محیط‌زیست", "recommended_agencies": "شهرداری جوانرود، آبفا، توزیع برق، شرکت گاز، مخابرات، راه و شهرسازی، راهداری، محیط‌زیست، نظام مهندسی"},
    {"code": "health", "title": "بهداشت و سلامت", "recommended_agencies": "شبکه بهداشت و درمان جوانرود، مرکز بهداشت، بیمارستان، هلال‌احمر، بهزیستی، اورژانس"},
    {"code": "sports", "title": "نشاط و ورزش", "recommended_agencies": "اداره ورزش و جوانان، شهرداری، آموزش‌وپرورش، بسیج، کانون‌های مساجد، سمن‌های جوانان"},
    {"code": "security", "title": "امنیت عمومی و آسیب‌های اجتماعی", "recommended_agencies": "فرماندهی انتظامی، کلانتری، بهزیستی و اورژانس اجتماعی، دادگستری، شورای هماهنگی مبارزه با مواد مخدر، بسیج، آموزش‌وپرورش"},
    {"code": "support", "title": "خدمات حمایتی و معیشتی", "recommended_agencies": "کمیته امداد، بهزیستی، تعاون کار و رفاه اجتماعی، فنی‌وحرفه‌ای، بنیاد مسکن، بسیج سازندگی، خیرین و گروه‌های جهادی"},
    {"code": "culture", "title": "امور فرهنگی، آموزشی و دینی", "recommended_agencies": "سازمان تبلیغات اسلامی، امام جماعت محله، آموزش‌وپرورش، فرهنگ و ارشاد اسلامی، اوقاف، کتابخانه‌های عمومی، بسیج و حوزه علمیه"},
]

_MEETING_NUMBER_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _normalize_committee_meeting_number(value):
    text = str(value or "").translate(_MEETING_NUMBER_DIGIT_TRANSLATION)
    text = re.sub(r"\s+", " ", text).strip()
    if text.isdigit():
        return str(int(text))
    return text.casefold()


DEFAULT_COMMITTEE_AGENCIES = [
    "شهرداری جوانرود", "آب و فاضلاب", "شرکت توزیع نیروی برق", "شرکت گاز", "مخابرات",
    "راه و شهرسازی", "راهداری و حمل‌ونقل جاده‌ای", "اداره حفاظت محیط‌زیست", "سازمان نظام مهندسی",
    "شبکه بهداشت و درمان جوانرود", "مرکز بهداشت", "بیمارستان", "جمعیت هلال‌احمر", "اداره بهزیستی", "اورژانس",
    "اداره ورزش و جوانان", "آموزش‌وپرورش", "ناحیه مقاومت بسیج", "کانون فرهنگی هنری مساجد",
    "فرماندهی انتظامی", "کلانتری", "اورژانس اجتماعی", "دادگستری", "شورای هماهنگی مبارزه با مواد مخدر",
    "کمیته امداد امام خمینی", "تعاون کار و رفاه اجتماعی", "فنی‌وحرفه‌ای", "بنیاد مسکن", "بسیج سازندگی",
    "سازمان تبلیغات اسلامی", "فرهنگ و ارشاد اسلامی", "اوقاف و امور خیریه", "کتابخانه‌های عمومی", "حوزه علمیه"
]


class Database(HardeningMixin, UserSecurityMixin, BackupSecurityMixin, PeopleRegistryMixin, PopulationEstimationMixin, MessagingMixin, ClientExchangeMixin, SocialCouncilMixin, CouncilFacilitiesMixin, ProjectContractsMixin):
    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.current_user = None
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout=5000;")
        migration_backup = self._prepare_upgrade_backup()
        try:
            self._create_tables()
            self._create_execution_tables()
            self._create_social_council_tables()
            self._create_client_exchange_tables()
            self._create_message_tables()
            self._create_population_tables()
            self._initialize_hardening()
            self._seed_county_steering_structure()
            self._restore_six_committee_structure()
            self._ensure_default_committees_for_all_zones()
            self.sync_execution_cases()
            self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            self.conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, description) VALUES (?, ?)",
                (SCHEMA_VERSION, "نسخه ۷.۶.۱۴ سازگاری بازیابی بکاپ‌های قدیمی و مهاجرت پرونده اشخاص"),
            )
            self.conn.commit()
        except Exception:
            try:
                self.conn.close()
            finally:
                if migration_backup and os.path.exists(migration_backup):
                    shutil.copy2(migration_backup, self.db_path)
            raise

    def _create_execution_tables(self):
        """ساخت جداول مرکز عملیات و گردش مصوبه تا اجرا."""
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS execution_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                committee_id INTEGER,
                source_type TEXT DEFAULT 'manual',
                source_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                responsible_agency TEXT,
                responsible_person TEXT,
                assigned_user_id INTEGER,
                priority TEXT DEFAULT 'عادی',
                status TEXT DEFAULT 'جدید',
                progress_percent INTEGER DEFAULT 0,
                decision_date TEXT,
                start_date TEXT,
                due_date TEXT,
                completed_date TEXT,
                delay_reason TEXT,
                final_result TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_source ON execution_cases(source_type, source_id) WHERE source_id IS NOT NULL")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_execution_status_due ON execution_cases(status, due_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_execution_zone ON execution_cases(zone_id, status)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS execution_case_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                update_date TEXT,
                progress_percent INTEGER DEFAULT 0,
                status TEXT,
                note TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES execution_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_execution_updates_case ON execution_case_updates(case_id, id)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS execution_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                assigned_to_user_id INTEGER,
                assigned_to_name TEXT,
                assigned_to_agency TEXT,
                assigned_by_user_id INTEGER,
                instruction TEXT,
                due_date TEXT,
                priority TEXT DEFAULT 'عادی',
                status TEXT DEFAULT 'ارجاع‌شده',
                viewed_at TEXT,
                response_text TEXT,
                completed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES execution_cases(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_to_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_by_user_id) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_execution_assignment_user ON execution_assignments(assigned_to_user_id, status, due_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_execution_assignment_case ON execution_assignments(case_id)")
        self.conn.commit()

    def _prepare_upgrade_backup(self):
        """پیش از ارتقای واقعی ساختار، یک نسخه قابل‌بازیابی می‌سازد."""
        try:
            current = int(self.conn.execute("PRAGMA user_version").fetchone()[0] or 0)
            tables = int(self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0] or 0)
            if current >= SCHEMA_VERSION or tables == 0:
                return None
            backup_dir = os.path.join(os.path.dirname(self.db_path), "automatic_backups")
            os.makedirs(backup_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            destination = os.path.join(backup_dir, f"pre_migration_v{SCHEMA_VERSION}_{stamp}.db")
            target = sqlite3.connect(destination)
            try:
                self.conn.backup(target)
                target.commit()
            finally:
                target.close()
            return destination
        except Exception:
            return None

    def _create_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT,
                applied_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول محدوده شهر (نقاط مرزی به ترتیب رسم) - محدوده کلی شهر
        cur.execute("""
            CREATE TABLE IF NOT EXISTS boundary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seq INTEGER NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول مناطق/بلوک‌ها (زیرمجموعه محدوده کلی شهر)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                boundary_points TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول خیابان‌ها و کوچه‌ها (هر ردیف متعلق به یک منطقه مشخص است)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS streets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                osm_id INTEGER,
                name TEXT,
                highway_type TEXT,
                geometry TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # جدول اماکن (مدارس، ادارات دولتی، بیمارستان و ...) - هر ردیف متعلق به یک منطقه مشخص
        cur.execute("""
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                osm_id INTEGER,
                name TEXT,
                category TEXT,
                subtype TEXT,
                lat REAL,
                lon REAL,
                address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # مسئول هر مکان عمومی؛ با انتخاب مکان به‌عنوان محل جلسه، شخص مسئول
        # به‌صورت خودکار به‌عنوان معتمد همان بلوک در شورای محله ثبت می‌شود.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS place_managers (
                place_id INTEGER PRIMARY KEY,
                zone_id INTEGER,
                council_member_id INTEGER,
                role_label TEXT NOT NULL DEFAULT 'مسئول مکان',
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                mobile TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (council_member_id) REFERENCES council_members(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_place_managers_zone ON place_managers(zone_id)")

        # فهرست مرجع و ثابت مساجد جوانرود (۲۴ مکان منحصربه‌فرد)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mosques (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                aliases TEXT DEFAULT '[]',
                source TEXT DEFAULT 'فهرست مرجع پروژه',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ارتباط چندبه‌چند مسجد و بلوک؛ عضویت بر اساس مختصات و چندضلعی بلوک محاسبه می‌شود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zone_mosques (
                zone_id INTEGER NOT NULL,
                mosque_id TEXT NOT NULL,
                assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_id, mosque_id),
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (mosque_id) REFERENCES mosques(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zone_mosques_zone ON zone_mosques(zone_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zone_mosques_mosque ON zone_mosques(mosque_id)")

        # امام جماعت ثبت‌شده برای هر مسجد مرجع؛ یک امام برای هر مسجد (در صورت تغییر، رکورد به‌روزرسانی می‌شود)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mosque_imams (
                mosque_id TEXT PRIMARY KEY,
                zone_id INTEGER,
                council_member_id INTEGER,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                mobile TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mosque_id) REFERENCES mosques(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (council_member_id) REFERENCES council_members(id) ON DELETE SET NULL
            )
        """)

        # مدارس؛ برخلاف مساجد (فهرست مرجع ثابت)، کاربر خودش با مختصات دقیق ثبت می‌کند
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_schools_zone ON schools(zone_id)")

        # مدیر/مسؤول ثبت‌شده برای هر مدرسه؛ مثل امام جماعت، به‌طور خودکار معتمد بلوک می‌شود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS school_managers (
                school_id INTEGER PRIMARY KEY,
                zone_id INTEGER,
                council_member_id INTEGER,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                mobile TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (council_member_id) REFERENCES council_members(id) ON DELETE SET NULL
            )
        """)

        # مراکز بهداشتی؛ همانند مدارس، کاربر خودش با مختصات دقیق ثبت می‌کند
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_health_centers_zone ON health_centers(zone_id)")

        # مسؤول ثبت‌شده برای هر مرکز بهداشتی؛ مثل امام جماعت، به‌طور خودکار معتمد بلوک می‌شود
        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_center_managers (
                health_center_id INTEGER PRIMARY KEY,
                zone_id INTEGER,
                council_member_id INTEGER,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                mobile TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (health_center_id) REFERENCES health_centers(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (council_member_id) REFERENCES council_members(id) ON DELETE SET NULL
            )
        """)

        # نمای گرافیکی ثابت هر بلوک برای پیش‌نمایش و گزارش‌ها
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zone_snapshots (
                zone_id INTEGER PRIMARY KEY,
                svg_text TEXT,
                png_data BLOB,
                thumbnail_data BLOB,
                content_hash TEXT,
                width INTEGER DEFAULT 1200,
                height INTEGER DEFAULT 900,
                render_status TEXT DEFAULT 'dirty',
                error_message TEXT,
                version INTEGER DEFAULT 1,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zone_snapshots_status ON zone_snapshots(render_status)")

        # جدول تایل‌های نقشه (برای حالت آفلاین) - می‌تواند مختص یک منطقه یا کل شهر باشد
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                z INTEGER NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                image_data BLOB NOT NULL,
                UNIQUE(z, x, y)
            )
        """)

        # متادیتای دانلود (آخرین وضعیت دانلود آفلاین)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # جدول تنظیمات ادمین (نام‌کاربری و رمز عبور هش‌شده)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # تنظیمات اختیاری اتصال به سرویس هوش مصنوعی برای پیشنهاد دسته‌بندی/فوریت
        # درخواست‌های مردمی (smart_triage.py). در صورت خالی‌بودن api_key، برنامه
        # همیشه از موتور کلیدواژه‌ای آفلاین استفاده می‌کند.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS smart_triage_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER DEFAULT 0,
                api_url TEXT DEFAULT '',
                api_key TEXT DEFAULT '',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # برنامه‌های عملیاتی تولیدشده برای هر بلوک (توسط zone_action_plan.py)؛
        # هر بار تولید مجدد، نسخه جدیدی ثبت می‌شود تا تاریخچه حفظ شود.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zone_action_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                engine TEXT NOT NULL,
                content TEXT NOT NULL,
                context_snapshot TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zone_action_plans_zone ON zone_action_plans(zone_id)")

        # کاربران و نقش‌های سامانه؛ جدول admin_settings برای سازگاری نسخه‌های قدیمی حفظ می‌شود.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                full_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                mobile TEXT,
                is_active INTEGER DEFAULT 1,
                must_change_password INTEGER DEFAULT 1,
                failed_attempts INTEGER DEFAULT 0,
                locked_until TEXT,
                last_login_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_app_users_role_active ON app_users(role, is_active)")

        # جدول محل برگزاری جلسات شورای هر منطقه (یک مکان انتخابی برای هر منطقه)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zone_meeting_places (
                zone_id INTEGER PRIMARY KEY,
                place_id INTEGER,
                place_name TEXT,
                exact_address TEXT,
                lat REAL,
                lon REAL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # پرونده هویتی مشترک اشخاص؛ یک شخص می‌تواند هم‌زمان عضو شورا و چند کمیته باشد.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS people_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                national_code TEXT NOT NULL UNIQUE,
                first_name TEXT,
                last_name TEXT,
                full_name TEXT,
                education TEXT,
                mobile TEXT,
                address TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # قبل از ساخت ایندکس‌ها و اجرای مهاجرت اشخاص، ساختار بکاپ‌های قدیمی را کامل کن.
        # در نسخه‌های قبلی ممکن است people_registry وجود داشته باشد اما ستون‌های حذف نرم،
        # کیفیت داده یا حتی برخی فیلدهای تکمیلی هنوز به آن اضافه نشده باشند.
        self._ensure_people_registry_compatibility_schema()
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_people_registry_national_code ON people_registry(national_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_people_registry_name ON people_registry(last_name, first_name)")

        # جدول اعضای شورای محلات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS council_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                person_id INTEGER,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                national_code TEXT,
                education TEXT,
                mobile TEXT,
                member_group TEXT,
                position TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (person_id) REFERENCES people_registry(id) ON DELETE SET NULL
            )
        """)

        # کمیته حمایت و راهبری شهرستان
        cur.execute("""
            CREATE TABLE IF NOT EXISTS county_steering_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_slot TEXT NOT NULL UNIQUE,
                role_title TEXT NOT NULL,
                agency_name TEXT,
                person_name TEXT,
                mobile TEXT,
                decree_no TEXT,
                decree_date TEXT,
                status TEXT DEFAULT 'فعال',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # کمیته‌های شش‌گانه شورای پیشرفت محله برای هر بلوک
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neighborhood_committees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                committee_code TEXT NOT NULL,
                title TEXT NOT NULL,
                recommended_agencies TEXT,
                chair_name TEXT,
                chair_mobile TEXT,
                secretary_name TEXT,
                secretary_mobile TEXT,
                decree_no TEXT,
                decree_date TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'فعال',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(zone_id, committee_code),
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                committee_id INTEGER NOT NULL,
                person_id INTEGER,
                person_name TEXT NOT NULL,
                national_code TEXT,
                mobile TEXT,
                member_role TEXT DEFAULT 'عضو',
                member_type TEXT DEFAULT 'عضو مردمی',
                agency_id INTEGER,
                agency_name TEXT,
                is_chair INTEGER DEFAULT 0,
                is_secretary INTEGER DEFAULT 0,
                decree_no TEXT,
                decree_date TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'فعال',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE CASCADE,
                FOREIGN KEY (person_id) REFERENCES people_registry(id) ON DELETE SET NULL,
                FOREIGN KEY (agency_id) REFERENCES management_agencies(id) ON DELETE SET NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                committee_id INTEGER NOT NULL,
                zone_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                meeting_number TEXT,
                meeting_date TEXT,
                start_time TEXT,
                place_name TEXT,
                agenda TEXT,
                attendees TEXT,
                minutes_text TEXT,
                status TEXT DEFAULT 'برنامه‌ریزی‌شده',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_resolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                committee_id INTEGER NOT NULL,
                zone_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                responsible_agency TEXT,
                responsible_person TEXT,
                due_date TEXT,
                status TEXT DEFAULT 'در انتظار اقدام',
                linked_issue_id INTEGER,
                linked_action_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES committee_meetings(id) ON DELETE SET NULL,
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_issue_id) REFERENCES neighborhood_issues(id) ON DELETE SET NULL,
                FOREIGN KEY (linked_action_id) REFERENCES neighborhood_actions(id) ON DELETE SET NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_issue_links (
                committee_id INTEGER NOT NULL,
                issue_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (committee_id, issue_id),
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE CASCADE,
                FOREIGN KEY (issue_id) REFERENCES neighborhood_issues(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_action_links (
                committee_id INTEGER NOT NULL,
                action_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (committee_id, action_id),
                FOREIGN KEY (committee_id) REFERENCES neighborhood_committees(id) ON DELETE CASCADE,
                FOREIGN KEY (action_id) REFERENCES neighborhood_actions(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_committees_zone ON neighborhood_committees(zone_id, committee_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_committee_members_committee ON committee_members(committee_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_committee_meetings_committee_date ON committee_meetings(committee_id, meeting_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_committee_resolutions_committee_status ON committee_resolutions(committee_id, status)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_meeting_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                signature_png BLOB,
                signed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(meeting_id, member_id),
                FOREIGN KEY (meeting_id) REFERENCES committee_meetings(id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES committee_members(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_committee_meeting_signatures_meeting ON committee_meeting_signatures(meeting_id, member_id)")

        # جدول درخواست‌ها و مشکلات اولویت‌بندی‌شده هر منطقه
        cur.execute("""
            CREATE TABLE IF NOT EXISTS priority_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                related_office TEXT,
                status TEXT DEFAULT 'در حال بررسی',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # جدول اقدامات انجام‌شده برای هر درخواست (یک درخواست می‌تواند چند اقدام پیگیری داشته باشد)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS request_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                action_description TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES priority_requests(id) ON DELETE CASCADE
            )
        """)

        # پرونده جمعیتی و اجتماعی هر بلوک
        cur.execute("""
            CREATE TABLE IF NOT EXISTS zone_profiles (
                zone_id INTEGER PRIMARY KEY,
                residential_buildings INTEGER DEFAULT 0,
                residential_units INTEGER DEFAULT 0,
                occupied_units INTEGER DEFAULT 0,
                vacant_units INTEGER DEFAULT 0,
                estimated_households INTEGER DEFAULT 0,
                field_households INTEGER DEFAULT 0,
                approved_households INTEGER DEFAULT 0,
                estimated_population INTEGER DEFAULT 0,
                average_household_size REAL DEFAULT 3.3,
                elderly_count INTEGER DEFAULT 0,
                children_count INTEGER DEFAULT 0,
                disabled_count INTEGER DEFAULT 0,
                vulnerable_households INTEGER DEFAULT 0,
                female_headed_households INTEGER DEFAULT 0,
                estimation_method TEXT,
                confidence_level TEXT DEFAULT 'متوسط',
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # پرونده مسائل و نیازهای محله
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neighborhood_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                legacy_request_id INTEGER UNIQUE,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'سایر',
                description TEXT,
                related_office TEXT,
                urgency INTEGER DEFAULT 3,
                severity INTEGER DEFAULT 3,
                affected_households INTEGER DEFAULT 0,
                safety_risk INTEGER DEFAULT 1,
                priority_score REAL DEFAULT 0,
                priority_level TEXT DEFAULT 'عادی',
                status TEXT DEFAULT 'ثبت اولیه',
                source TEXT DEFAULT 'ثبت سامانه',
                location_text TEXT,
                lat REAL,
                lon REAL,
                due_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # اقدامات اجرایی مرتبط با مسئله یا بلوک
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neighborhood_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                issue_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                responsible_person TEXT,
                responsible_office TEXT,
                partner_office TEXT,
                planned_start TEXT,
                planned_end TEXT,
                progress_percent INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0,
                actual_cost REAL DEFAULT 0,
                funding_source TEXT,
                contractor TEXT,
                status TEXT DEFAULT 'برنامه‌ریزی‌شده',
                obstacles TEXT,
                result_summary TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (issue_id) REFERENCES neighborhood_issues(id) ON DELETE SET NULL
            )
        """)

        # جلسات شورای محله
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neighborhood_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                meeting_date TEXT,
                start_time TEXT,
                place_name TEXT,
                agenda TEXT,
                attendees TEXT,
                absentees TEXT,
                minutes_text TEXT,
                status TEXT DEFAULT 'برگزارشده',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # مصوبات هر جلسه، با امکان اتصال به مسئله و اقدام
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neighborhood_resolutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                zone_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                responsible_office TEXT,
                responsible_person TEXT,
                due_date TEXT,
                status TEXT DEFAULT 'در انتظار اقدام',
                linked_issue_id INTEGER,
                linked_action_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES neighborhood_meetings(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_issue_id) REFERENCES neighborhood_issues(id) ON DELETE SET NULL,
                FOREIGN KEY (linked_action_id) REFERENCES neighborhood_actions(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_zone_profiles_updated ON zone_profiles(updated_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_zone_status ON neighborhood_issues(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_actions_zone_status ON neighborhood_actions(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_meetings_zone_date ON neighborhood_meetings(zone_id, meeting_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_resolutions_zone_status ON neighborhood_resolutions(zone_id, status)")

        # دفتر دستگاه‌ها و نهادهای همکار مدیریت محله‌محور
        cur.execute("""
            CREATE TABLE IF NOT EXISTS management_agencies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'دستگاه اجرایی',
                contact_person TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                service_scope TEXT,
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ردیف‌های بودجه، تخصیص و هزینه برای هر بلوک/اقدام
        cur.execute("""
            CREATE TABLE IF NOT EXISTS neighborhood_budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                action_id INTEGER,
                title TEXT NOT NULL,
                fiscal_year TEXT,
                funding_source TEXT,
                approved_amount REAL DEFAULT 0,
                allocated_amount REAL DEFAULT 0,
                spent_amount REAL DEFAULT 0,
                status TEXT DEFAULT 'پیشنهادی',
                document_reference TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (action_id) REFERENCES neighborhood_actions(id) ON DELETE SET NULL
            )
        """)

        # سوابق تأیید/رسیدگی به هشدارهای سیستمی
        cur.execute("""
            CREATE TABLE IF NOT EXISTS management_alert_acknowledgements (
                alert_key TEXT PRIMARY KEY,
                acknowledged_at TEXT DEFAULT CURRENT_TIMESTAMP,
                acknowledged_by TEXT,
                note TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_budget_zone_status ON neighborhood_budgets(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_budget_action ON neighborhood_budgets(action_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_agency_active ON management_agencies(is_active, name)")

        # بازدیدها و ثبت‌های میدانی؛ client_uid برای تبادل آفلاین بین دستگاه‌هاست.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS field_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_uid TEXT NOT NULL UNIQUE,
                zone_id INTEGER NOT NULL,
                visit_date TEXT,
                start_time TEXT,
                officer_name TEXT,
                visit_type TEXT DEFAULT 'بازدید عمومی',
                location_text TEXT,
                lat REAL,
                lon REAL,
                buildings_count INTEGER DEFAULT 0,
                households_count INTEGER DEFAULT 0,
                observation TEXT,
                immediate_action TEXT,
                followup_required INTEGER DEFAULT 0,
                status TEXT DEFAULT 'ثبت‌شده',
                source_device TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)

        # درخواست‌ها و گزارش‌های مردمی با کد رهگیری و امکان تبدیل به مسئله محله.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS citizen_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_uid TEXT NOT NULL UNIQUE,
                tracking_code TEXT NOT NULL UNIQUE,
                zone_id INTEGER NOT NULL,
                citizen_name TEXT,
                mobile TEXT,
                is_anonymous INTEGER DEFAULT 0,
                consent_contact INTEGER DEFAULT 1,
                category TEXT DEFAULT 'سایر',
                title TEXT NOT NULL,
                description TEXT,
                location_text TEXT,
                lat REAL,
                lon REAL,
                urgency INTEGER DEFAULT 3,
                status TEXT DEFAULT 'دریافت‌شده',
                assigned_office TEXT,
                linked_issue_id INTEGER,
                source TEXT DEFAULT 'ثبت حضوری',
                received_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_issue_id) REFERENCES neighborhood_issues(id) ON DELETE SET NULL
            )
        """)

        # صف تغییرات آفلاین؛ برای خروجی/ورودی بسته تبادل و همگام‌سازی آینده.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS offline_sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_uid TEXT NOT NULL,
                operation TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT DEFAULT 'در انتظار انتقال',
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT,
                queued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                synced_at TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_field_visits_zone_date ON field_visits(zone_id, visit_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_citizen_requests_zone_status ON citizen_requests(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_citizen_requests_tracking ON citizen_requests(tracking_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON offline_sync_queue(status, queued_at)")

        # ثبت وضعیت بکاپ‌های خودکار برای کنترل سلامت و نگهداری.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS backup_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                backup_type TEXT DEFAULT 'automatic',
                reason TEXT,
                file_size INTEGER DEFAULT 0,
                checksum TEXT,
                validation_status TEXT DEFAULT 'نامشخص',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_backup_registry_created ON backup_registry(created_at)")

        # مکاتبات اداری وارده، صادره و داخلی
        cur.execute("""
            CREATE TABLE IF NOT EXISTS correspondence_letters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                letter_number TEXT NOT NULL,
                direction TEXT NOT NULL DEFAULT 'وارده',
                subject TEXT NOT NULL,
                sender TEXT,
                recipient TEXT,
                letter_date TEXT,
                received_date TEXT,
                due_date TEXT,
                status TEXT DEFAULT 'ثبت‌شده',
                priority TEXT DEFAULT 'عادی',
                confidentiality TEXT DEFAULT 'عادی',
                related_entity_type TEXT,
                related_entity_id TEXT,
                description TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_correspondence_letter_number_direction ON correspondence_letters(letter_number, direction)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_correspondence_zone_status ON correspondence_letters(zone_id, status, due_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_correspondence_subject ON correspondence_letters(subject)")

        # پیوست‌های بایگانی‌شده؛ فایل‌ها در پوشه data/attachments نگهداری می‌شوند.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_type TEXT NOT NULL,
                parent_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT,
                file_size INTEGER DEFAULT 0,
                checksum TEXT,
                description TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_attachments_parent ON document_attachments(parent_type, parent_id)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_attachment_parent_checksum ON document_attachments(parent_type, parent_id, checksum) WHERE checksum IS NOT NULL")

        # ارجاعات و کارتابل پیگیری مکاتبات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS workflow_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                letter_id INTEGER NOT NULL,
                assigned_to_user_id INTEGER,
                assigned_to_name TEXT,
                assigned_by_user_id INTEGER,
                instruction TEXT,
                due_date TEXT,
                priority TEXT DEFAULT 'عادی',
                status TEXT DEFAULT 'ارجاع‌شده',
                response_text TEXT,
                completed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (letter_id) REFERENCES correspondence_letters(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_to_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
                FOREIGN KEY (assigned_by_user_id) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workflow_assignee_status ON workflow_assignments(assigned_to_user_id, status, due_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workflow_letter ON workflow_assignments(letter_id)")

        # ثبت مشاهده/رسیدگی اعلان‌های اداری پویا
        cur.execute("""
            CREATE TABLE IF NOT EXISTS administrative_notification_acknowledgements (
                notification_key TEXT PRIMARY KEY,
                acknowledged_by INTEGER,
                acknowledged_at TEXT DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                FOREIGN KEY (acknowledged_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)

        # گردش تأیید چندمرحله‌ای برای اقدامات، مصوبات، بودجه و مکاتبات
        cur.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                title TEXT NOT NULL,
                requested_by INTEGER,
                current_step INTEGER DEFAULT 1,
                total_steps INTEGER DEFAULT 1,
                status TEXT DEFAULT 'در انتظار تأیید',
                due_date TEXT,
                notes TEXT,
                completed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (requested_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_approval_status_step ON approval_requests(status, current_step, due_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_approval_entity ON approval_requests(entity_type, entity_id)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS approval_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                approval_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                approver_role TEXT,
                approver_user_id INTEGER,
                approver_name TEXT,
                status TEXT DEFAULT 'قفل‌شده',
                decision_comment TEXT,
                decided_by INTEGER,
                decided_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(approval_id, step_order),
                FOREIGN KEY (approval_id) REFERENCES approval_requests(id) ON DELETE CASCADE,
                FOREIGN KEY (approver_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
                FOREIGN KEY (decided_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_approval_steps_pending ON approval_steps(status, approver_role, approver_user_id)")

        # قالب‌های استاندارد نامه، صورت‌جلسه و گزارش اقدام
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                template_type TEXT NOT NULL,
                subject_template TEXT,
                body_template TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_document_template_name_type ON document_templates(name, template_type)")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS generated_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER,
                zone_id INTEGER,
                related_entity_type TEXT,
                related_entity_id TEXT,
                title TEXT NOT NULL,
                content TEXT,
                file_path TEXT,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES document_templates(id) ON DELETE SET NULL,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_generated_documents_zone ON generated_documents(zone_id, created_at)")

        # تقویم مدیریتی و رویدادهای دستی/برنامه‌ریزی‌شده نسخه ۶.۶
        cur.execute("""
            CREATE TABLE IF NOT EXISTS management_calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'جلسه',
                start_date TEXT NOT NULL,
                end_date TEXT,
                start_time TEXT,
                all_day INTEGER DEFAULT 1,
                responsible_user_id INTEGER,
                responsible_person TEXT,
                location TEXT,
                description TEXT,
                status TEXT DEFAULT 'برنامه‌ریزی‌شده',
                priority TEXT DEFAULT 'عادی',
                linked_entity_type TEXT,
                linked_entity_id TEXT,
                reminder_days INTEGER DEFAULT 2,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (responsible_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
                FOREIGN KEY (created_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_calendar_date ON management_calendar_events(start_date, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_calendar_zone ON management_calendar_events(zone_id, start_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_calendar_user ON management_calendar_events(responsible_user_id, start_date)")

        # اعلان‌های داخل برنامه؛ اعلان‌های خودکار با unique_key به‌روزرسانی می‌شوند.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS in_app_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                unique_key TEXT NOT NULL UNIQUE,
                user_id INTEGER,
                zone_id INTEGER,
                notification_type TEXT DEFAULT 'سررسید خودکار',
                title TEXT NOT NULL,
                message TEXT,
                severity TEXT DEFAULT 'اطلاع',
                source_type TEXT,
                source_id TEXT,
                due_date TEXT,
                is_read INTEGER DEFAULT 0,
                read_at TEXT,
                is_dismissed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES app_users(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON in_app_notifications(user_id, is_read, is_dismissed, due_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_notifications_due ON in_app_notifications(due_date, severity)")

        # برنامه عملیاتی سالانه و کنترل پروژه — نسخه ۶.۷
        cur.execute("""
            CREATE TABLE IF NOT EXISTS annual_operational_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fiscal_year TEXT NOT NULL,
                title TEXT NOT NULL,
                strategic_goal TEXT,
                zone_id INTEGER,
                responsible_agency TEXT,
                program_manager TEXT,
                start_date TEXT,
                end_date TEXT,
                approved_budget REAL DEFAULT 0,
                weight REAL DEFAULT 1,
                progress_percent REAL DEFAULT 0,
                status TEXT DEFAULT 'پیش‌نویس',
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_programs_year_status ON annual_operational_programs(fiscal_year, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_programs_zone ON annual_operational_programs(zone_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                zone_id INTEGER,
                project_code TEXT UNIQUE,
                title TEXT NOT NULL,
                responsible_agency TEXT,
                project_manager TEXT,
                start_date TEXT,
                end_date TEXT,
                actual_start_date TEXT,
                actual_end_date TEXT,
                planned_budget REAL DEFAULT 0,
                actual_cost REAL DEFAULT 0,
                planned_progress REAL DEFAULT 0,
                actual_progress REAL DEFAULT 0,
                priority TEXT DEFAULT 'عادی',
                status TEXT DEFAULT 'برنامه‌ریزی‌شده',
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (program_id) REFERENCES annual_operational_programs(id) ON DELETE SET NULL,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_program ON project_portfolio(program_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_zone ON project_portfolio(zone_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_dates ON project_portfolio(start_date, end_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT,
                completed_date TEXT,
                weight REAL DEFAULT 1,
                status TEXT DEFAULT 'در انتظار',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_milestones_project_due ON project_milestones(project_id, due_date, status)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_progress_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                report_date TEXT NOT NULL,
                planned_progress REAL DEFAULT 0,
                actual_progress REAL DEFAULT 0,
                actual_cost REAL DEFAULT 0,
                summary TEXT,
                obstacles TEXT,
                next_steps TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_project_update_date ON project_progress_updates(project_id, report_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_indicators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                project_id INTEGER,
                title TEXT NOT NULL,
                unit TEXT,
                baseline_value REAL DEFAULT 0,
                target_value REAL DEFAULT 0,
                actual_value REAL DEFAULT 0,
                direction TEXT DEFAULT 'افزایشی',
                weight REAL DEFAULT 1,
                measurement_date TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (program_id) REFERENCES annual_operational_programs(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE CASCADE,
                CHECK (program_id IS NOT NULL OR project_id IS NOT NULL)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_indicators_program_project ON project_indicators(program_id, project_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_risks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                project_id INTEGER,
                zone_id INTEGER,
                title TEXT NOT NULL,
                category TEXT DEFAULT 'اجرایی',
                probability INTEGER DEFAULT 1,
                impact INTEGER DEFAULT 1,
                risk_score INTEGER DEFAULT 1,
                risk_level TEXT DEFAULT 'کم',
                owner TEXT,
                mitigation TEXT,
                contingency TEXT,
                review_date TEXT,
                status TEXT DEFAULT 'باز',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (program_id) REFERENCES annual_operational_programs(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE CASCADE,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_risks_score_status ON project_risks(risk_score, status, review_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER,
                project_id INTEGER,
                title TEXT NOT NULL,
                change_type TEXT DEFAULT 'دامنه',
                target_field TEXT,
                reason TEXT,
                requested_by TEXT,
                request_date TEXT DEFAULT CURRENT_DATE,
                impact_days INTEGER DEFAULT 0,
                impact_cost REAL DEFAULT 0,
                old_value TEXT,
                new_value TEXT,
                status TEXT DEFAULT 'در انتظار بررسی',
                review_note TEXT,
                reviewed_by INTEGER,
                reviewed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (program_id) REFERENCES annual_operational_programs(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by) REFERENCES app_users(id) ON DELETE SET NULL,
                CHECK (program_id IS NOT NULL OR project_id IS NOT NULL)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_changes_status ON project_change_requests(status, request_date)")

        # قراردادها، پیمانکاران، پرداخت و رضایت مردمی — نسخه ۶.۸
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contractors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                national_id TEXT,
                registration_no TEXT,
                manager_name TEXT,
                phone TEXT,
                email TEXT,
                address TEXT,
                specialty TEXT,
                status TEXT DEFAULT 'فعال',
                average_score REAL DEFAULT 0,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contractors_status ON contractors(status, name)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS project_contracts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                action_id INTEGER,
                contractor_id INTEGER NOT NULL,
                contract_no TEXT NOT NULL UNIQUE COLLATE NOCASE,
                title TEXT NOT NULL,
                contract_date TEXT,
                start_date TEXT,
                end_date TEXT,
                amount REAL DEFAULT 0,
                guarantee_amount REAL DEFAULT 0,
                retention_percent REAL DEFAULT 0,
                advance_percent REAL DEFAULT 0,
                status TEXT DEFAULT 'پیش‌نویس',
                temporary_delivery_date TEXT,
                final_delivery_date TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE RESTRICT,
                FOREIGN KEY (action_id) REFERENCES neighborhood_actions(id) ON DELETE RESTRICT,
                FOREIGN KEY (contractor_id) REFERENCES contractors(id) ON DELETE RESTRICT,
                CHECK (project_id IS NOT NULL OR action_id IS NOT NULL)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contracts_project ON project_contracts(project_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contracts_action ON project_contracts(action_id, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_contracts_contractor ON project_contracts(contractor_id, status)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS contract_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                payment_type TEXT DEFAULT 'صورت‌وضعیت',
                statement_no TEXT,
                period_from TEXT,
                period_to TEXT,
                gross_amount REAL DEFAULT 0,
                deductions REAL DEFAULT 0,
                net_amount REAL DEFAULT 0,
                approved_amount REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0,
                invoice_date TEXT,
                approval_date TEXT,
                payment_date TEXT,
                status TEXT DEFAULT 'ثبت اولیه',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES project_contracts(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_contract_statement ON contract_payments(contract_id, payment_type, statement_no) WHERE statement_no IS NOT NULL AND statement_no<>''")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_payments_contract_status ON contract_payments(contract_id, status, payment_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS contractor_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id INTEGER NOT NULL,
                evaluation_date TEXT NOT NULL,
                quality_score REAL DEFAULT 0,
                schedule_score REAL DEFAULT 0,
                safety_score REAL DEFAULT 0,
                cooperation_score REAL DEFAULT 0,
                documentation_score REAL DEFAULT 0,
                total_score REAL DEFAULT 0,
                evaluator TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contract_id) REFERENCES project_contracts(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_contract_date ON contractor_evaluations(contract_id, evaluation_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS satisfaction_surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER,
                project_id INTEGER,
                action_id INTEGER,
                citizen_request_id INTEGER,
                survey_date TEXT NOT NULL,
                respondents INTEGER DEFAULT 1,
                problem_resolved_percent REAL DEFAULT 0,
                quality_score REAL DEFAULT 0,
                speed_score REAL DEFAULT 0,
                communication_score REAL DEFAULT 0,
                overall_score REAL DEFAULT 0,
                satisfaction_percent REAL DEFAULT 0,
                reopen_recommended INTEGER DEFAULT 0,
                recorded_by TEXT,
                comments TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE SET NULL,
                FOREIGN KEY (action_id) REFERENCES neighborhood_actions(id) ON DELETE SET NULL,
                FOREIGN KEY (citizen_request_id) REFERENCES citizen_requests(id) ON DELETE SET NULL,
                CHECK (zone_id IS NOT NULL OR project_id IS NOT NULL OR action_id IS NOT NULL OR citizen_request_id IS NOT NULL)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_satisfaction_zone_date ON satisfaction_surveys(zone_id, survey_date)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS community_participations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_id INTEGER NOT NULL,
                project_id INTEGER,
                action_id INTEGER,
                title TEXT NOT NULL,
                participation_type TEXT DEFAULT 'داوطلبانه',
                organization_name TEXT,
                contact_person TEXT,
                phone TEXT,
                volunteers_count INTEGER DEFAULT 0,
                cash_value REAL DEFAULT 0,
                noncash_value REAL DEFAULT 0,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'فعال',
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES project_portfolio(id) ON DELETE SET NULL,
                FOREIGN KEY (action_id) REFERENCES neighborhood_actions(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_participation_zone_status ON community_participations(zone_id, status)")

        # حکمرانی داده، نسخه‌بندی و حل تعارض همگام‌سازی — نسخه ۶.۹
        cur.execute("""
            CREATE TABLE IF NOT EXISTS data_governance_policies (
                entity_type TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                classification TEXT DEFAULT 'داخلی',
                retention_days INTEGER DEFAULT 1825,
                requires_approval INTEGER DEFAULT 0,
                public_allowed INTEGER DEFAULT 0,
                contains_personal_data INTEGER DEFAULT 0,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS record_governance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_uid TEXT NOT NULL,
                zone_id INTEGER,
                classification TEXT DEFAULT 'داخلی',
                lifecycle_status TEXT DEFAULT 'پیش‌نویس',
                data_owner TEXT,
                reviewer_user_id INTEGER,
                retention_until TEXT,
                is_public INTEGER DEFAULT 0,
                approved_at TEXT,
                approved_by INTEGER,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(entity_type, entity_uid),
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewer_user_id) REFERENCES app_users(id) ON DELETE SET NULL,
                FOREIGN KEY (approved_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_record_governance_zone ON record_governance(zone_id, lifecycle_status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_record_governance_public ON record_governance(is_public, classification)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_uid TEXT NOT NULL,
                zone_id INTEGER,
                local_version INTEGER DEFAULT 0,
                incoming_version INTEGER DEFAULT 0,
                base_version INTEGER DEFAULT 0,
                local_payload_json TEXT NOT NULL,
                incoming_payload_json TEXT NOT NULL,
                source_device TEXT,
                status TEXT DEFAULT 'در انتظار تصمیم',
                resolution TEXT,
                resolved_by INTEGER,
                resolved_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE SET NULL,
                FOREIGN KEY (resolved_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_conflicts_status ON sync_conflicts(status, created_at)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_open_sync_conflict ON sync_conflicts(entity_type, entity_uid) WHERE status='در انتظار تصمیم'")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS public_portal_publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                publication_uid TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                output_path TEXT NOT NULL,
                zones_count INTEGER DEFAULT 0,
                projects_count INTEGER DEFAULT 0,
                requests_count INTEGER DEFAULT 0,
                generated_by INTEGER,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                checksum TEXT,
                status TEXT DEFAULT 'منتشرشده',
                FOREIGN KEY (generated_by) REFERENCES app_users(id) ON DELETE SET NULL
            )
        """)

        # نسخه رکورد و دستگاه آخرین ویرایش برای تشخیص تعارض واقعی بین دستگاه‌ها
        for table in ("field_visits", "citizen_requests"):
            self._ensure_column(table, "record_version", "INTEGER DEFAULT 1")
            self._ensure_column(table, "last_modified_device", "TEXT")
            self._ensure_column(table, "data_classification", "TEXT DEFAULT 'داخلی'")
            self._ensure_column(table, "lifecycle_status", "TEXT DEFAULT 'تأییدشده'")

        self._seed_governance_policies(cur)

        # وضعیت تأیید روی موجودیت‌های اصلی، بدون تغییر وضعیت عملیاتی آن‌ها
        for table in ("neighborhood_actions", "neighborhood_resolutions", "neighborhood_budgets", "correspondence_letters"):
            self._ensure_column(table, "approval_status", "TEXT DEFAULT 'نیاز ندارد'")
            self._ensure_column(table, "approved_at", "TEXT")
            self._ensure_column(table, "approved_by", "INTEGER")

        self._seed_document_templates(cur)

        # محدوده مرجع «نقشه کامل شهر» (مستقل و بدون ارتباط با محدوده بلوک‌بندی یا مناطق)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS city_wide_boundary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seq INTEGER NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # خیابان‌های «نقشه کامل شهر» — کاملاً مجزا از جدول streets که مربوط به بلوک‌هاست
        cur.execute("""
            CREATE TABLE IF NOT EXISTS city_wide_streets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                osm_id INTEGER,
                name TEXT,
                highway_type TEXT,
                geometry TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # اماکن «نقشه کامل شهر» — کاملاً مجزا از جدول places که مربوط به بلوک‌هاست
        cur.execute("""
            CREATE TABLE IF NOT EXISTS city_wide_places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                osm_id INTEGER,
                name TEXT,
                category TEXT,
                subtype TEXT,
                lat REAL,
                lon REAL,
                address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ارتقای دیتابیس‌های قدیمی: افزودن ستون zone_id اگر وجود نداشته باشد
        self._ensure_column("streets", "zone_id", "INTEGER")
        self._ensure_column("places", "zone_id", "INTEGER")
        self._ensure_column("council_members", "person_id", "INTEGER")
        self._ensure_column("committee_members", "person_id", "INTEGER")
        self._upgrade_schema()
        # اکنون همه جداول عضو ساخته شده‌اند؛ ستون‌های لازم بکاپ‌های قدیمی را پیش از مهاجرت کامل کن.
        self._ensure_people_registry_compatibility_schema()
        self._migrate_people_registry()

        # انتقال غیرمخرب درخواست‌های نسخه‌های قبلی به پرونده مسائل محله
        cur.execute("""
            INSERT OR IGNORE INTO neighborhood_issues
                (zone_id, legacy_request_id, title, category, description, related_office,
                 urgency, severity, safety_risk, priority_score, priority_level, status, source, created_at, updated_at)
            SELECT zone_id, id,
                   CASE WHEN LENGTH(description) > 70 THEN SUBSTR(description, 1, 67) || '...' ELSE description END,
                   'سایر', description, related_office, 3, 3, 1, 42, 'مهم',
                   COALESCE(status, 'ثبت اولیه'), 'مهاجرت از درخواست‌های قدیمی', created_at, created_at
            FROM priority_requests
        """)

        self.conn.commit()

        # فهرست مرجع مساجد را درج/به‌روزرسانی و ارتباط آن‌ها با بلوک‌های موجود را بازسازی کن
        self._seed_mosques()
        self.sync_all_zone_mosques()

        # اگر تنظیمات ادمین هنوز وجود ندارد، مقدار پیش‌فرض بساز
        self._ensure_default_admin()
        self._ensure_default_users()

    def _refresh_zone_snapshot_safe(self, zone_id, force=False):
        """بازسازی تصویر بلوک؛ خطای رندر نباید عملیات اصلی ذخیره داده را خراب کند."""
        if zone_id is None:
            return False
        try:
            from zone_snapshot_service import refresh_zone_snapshot
            refresh_zone_snapshot(self, int(zone_id), force=force)
            return True
        except Exception as exc:
            try:
                self.mark_zone_snapshot_dirty(zone_id, error_message=str(exc), status="error")
            except Exception:
                pass
            return False

    def _ensure_people_registry_compatibility_schema(self):
        """تکمیل غیرمخرب ساختار اشخاص پیش از مهاجرت بکاپ‌های نسخه‌های قدیمی."""
        # ستون‌هایی که PeopleRegistryMixin هنگام مهاجرت و upsert به آن‌ها نیاز دارد.
        for column, col_type in [
            ("national_code", "TEXT"),
            ("first_name", "TEXT"),
            ("last_name", "TEXT"),
            ("full_name", "TEXT"),
            ("education", "TEXT"),
            ("mobile", "TEXT"),
            ("address", "TEXT"),
            ("notes", "TEXT"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
            ("is_deleted", "INTEGER DEFAULT 0"),
            ("deleted_at", "TEXT"),
            ("deleted_by", "INTEGER"),
            ("data_quality_status", "TEXT DEFAULT 'تأییدنشده'"),
        ]:
            self._ensure_column("people_registry", column, col_type)

        # جداول عضو نیز در بعضی بکاپ‌های قدیمی بخشی از ستون‌های اتصال به پرونده اشخاص را ندارند.
        for table, columns in {
            "council_members": [
                ("person_id", "INTEGER"),
                ("national_code", "TEXT"),
                ("education", "TEXT"),
                ("mobile", "TEXT"),
            ],
            "committee_members": [
                ("person_id", "INTEGER"),
                ("person_name", "TEXT"),
                ("national_code", "TEXT"),
                ("mobile", "TEXT"),
                ("updated_at", "TEXT"),
            ],
        }.items():
            table_exists = self.conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not table_exists:
                continue
            for column, col_type in columns:
                self._ensure_column(table, column, col_type)

        # ستون‌های تازه افزوده‌شده با ALTER TABLE ممکن است برای رکوردهای قبلی NULL باشند.
        self.conn.execute("UPDATE people_registry SET is_deleted=0 WHERE is_deleted IS NULL")
        self.conn.execute(
            "UPDATE people_registry SET data_quality_status='تأییدنشده' "
            "WHERE data_quality_status IS NULL OR TRIM(data_quality_status)=''"
        )
        self.conn.execute("UPDATE people_registry SET created_at=CURRENT_TIMESTAMP WHERE created_at IS NULL")
        self.conn.execute("UPDATE people_registry SET updated_at=CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        self.conn.commit()

    def _ensure_column(self, table, column, col_type):
        """اگر ستون در جدول موجود نباشد، آن را اضافه می‌کند (برای سازگاری با دیتابیس‌های قدیمی)."""
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        existing_cols = [row[1] for row in cur.fetchall()]
        if column not in existing_cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            self.conn.commit()


    def _upgrade_schema(self):
        """مهاجرت غیرمخرب دیتابیس‌های قدیمی به ساختار پایدار نسخه ۴."""
        for table, column, col_type in [
            ("zones", "status", "TEXT DEFAULT 'در حال تکمیل'"),
            ("zones", "area_m2", "REAL DEFAULT 0"),
            ("zones", "perimeter_m", "REAL DEFAULT 0"),
            ("zones", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("streets", "segment_index", "INTEGER DEFAULT 0"),
            ("streets", "is_unnamed", "INTEGER DEFAULT 0"),
            ("streets", "geometry_hash", "TEXT"),
            ("streets", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("places", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("city_wide_streets", "segment_index", "INTEGER DEFAULT 0"),
            ("city_wide_streets", "is_unnamed", "INTEGER DEFAULT 0"),
            ("city_wide_streets", "geometry_hash", "TEXT"),
            ("city_wide_streets", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("city_wide_places", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ("admin_settings", "must_change_password", "INTEGER DEFAULT 1"),
            ("zone_meeting_places", "source_type", "TEXT DEFAULT 'place'"),
            ("zone_meeting_places", "source_id", "TEXT"),
            ("committee_meetings", "meeting_number", "TEXT"),
        ]:
            self._ensure_column(table, column, col_type)

        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute(
            "UPDATE zone_meeting_places SET source_type=COALESCE(source_type, 'place'), "
            "source_id=COALESCE(source_id, CAST(place_id AS TEXT)) WHERE source_id IS NULL"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS committee_meeting_signatures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                signature_png BLOB,
                signed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(meeting_id, member_id),
                FOREIGN KEY (meeting_id) REFERENCES committee_meetings(id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES committee_members(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_committee_meeting_signatures_meeting ON committee_meeting_signatures(meeting_id, member_id)")

        # تکمیل هش هندسه و شاخص‌های هندسی رکوردهای قدیمی
        for table in ("streets", "city_wide_streets"):
            for row_id, geometry_text in cur.execute(
                f"SELECT id, geometry FROM {table} WHERE geometry_hash IS NULL OR geometry_hash=''"
            ).fetchall():
                try:
                    points = json.loads(geometry_text) if geometry_text else []
                    value = geometry_hash(points)
                except Exception:
                    value = geometry_hash([])
                cur.execute(f"UPDATE {table} SET geometry_hash=? WHERE id=?", (value, row_id))

        for zone_id, boundary_text in cur.execute("SELECT id, boundary_points FROM zones").fetchall():
            try:
                area_m2, perimeter_m = polygon_metrics(json.loads(boundary_text) if boundary_text else [])
            except Exception:
                area_m2, perimeter_m = 0.0, 0.0
            cur.execute(
                "UPDATE zones SET area_m2=?, perimeter_m=? WHERE id=?",
                (area_m2, perimeter_m, zone_id),
            )

        # حذف رکوردهای تکراری قدیمی پیش از ساخت قید یکتا
        cur.execute("""
            DELETE FROM streets
            WHERE osm_id IS NOT NULL AND id NOT IN (
                SELECT MIN(id) FROM streets WHERE osm_id IS NOT NULL
                GROUP BY COALESCE(zone_id, -1), osm_id, COALESCE(segment_index, 0)
            )
        """)
        cur.execute("""
            DELETE FROM city_wide_streets
            WHERE osm_id IS NOT NULL AND id NOT IN (
                SELECT MIN(id) FROM city_wide_streets WHERE osm_id IS NOT NULL
                GROUP BY osm_id, COALESCE(segment_index, 0)
            )
        """)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_streets_zone ON streets(zone_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_places_zone ON places(zone_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_streets_name ON streets(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_places_name ON places(name)")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_streets_osm_segment ON streets(COALESCE(zone_id,-1), osm_id, segment_index) WHERE osm_id IS NOT NULL")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_city_streets_osm_segment ON city_wide_streets(osm_id, segment_index) WHERE osm_id IS NOT NULL")
        for column, col_type in [
            ("actor_user_id", "INTEGER"),
            ("actor_username", "TEXT"),
            ("zone_id", "INTEGER"),
            ("before_json", "TEXT"),
            ("after_json", "TEXT"),
        ]:
            self._ensure_column("audit_logs", column, col_type)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_username, created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_zone ON audit_logs(zone_id, created_at)")
        self.conn.commit()

    def set_current_user(self, user):
        """ثبت کاربر فعال برای کنترل دسترسی و درج نام او در تاریخچه تغییرات."""
        self.current_user = dict(user) if user else None

    def get_current_user(self):
        return dict(self.current_user) if self.current_user else None

    def current_user_can(self, permission):
        from access_control import has_permission
        if not self.current_user:
            return False
        return has_permission(self.current_user.get("role"), permission)

    def log_action(self, action, entity_type=None, entity_id=None, details=None,
                   zone_id=None, before=None, after=None):
        """ثبت رویداد به‌همراه کاربر، بلوک و وضعیت قبل/بعد برای حسابرسی اداری."""
        try:
            details_text = json.dumps(details, ensure_ascii=False) if isinstance(details, (dict, list)) else (str(details) if details is not None else None)
            before_text = json.dumps(before, ensure_ascii=False, default=str) if before is not None else None
            after_text = json.dumps(after, ensure_ascii=False, default=str) if after is not None else None
            if zone_id is None and isinstance(details, dict) and details.get("zone_id") is not None:
                zone_id = details.get("zone_id")
            if zone_id is None and entity_type == "zone" and entity_id is not None:
                try:
                    zone_id = int(entity_id)
                except Exception:
                    zone_id = None
            actor_id = self.current_user.get("id") if self.current_user else None
            actor_username = self.current_user.get("username") if self.current_user else "system"
            self.conn.execute(
                """INSERT INTO audit_logs
                   (action, entity_type, entity_id, details, actor_user_id, actor_username, zone_id, before_json, after_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (action, entity_type, str(entity_id) if entity_id is not None else None, details_text,
                 actor_id, actor_username, zone_id, before_text, after_text),
            )
            self.conn.commit()
        except Exception:
            pass

    def get_audit_logs(self, limit=200, username=None, zone_id=None, action=None):
        clauses, params = [], []
        if username:
            clauses.append("actor_username LIKE ?")
            params.append(f"%{username}%")
        if zone_id is not None:
            clauses.append("zone_id=?")
            params.append(int(zone_id))
        if action:
            clauses.append("action=?")
            params.append(action)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        rows = self.conn.execute(
            "SELECT id, action, entity_type, entity_id, details, created_at, "
            "actor_user_id, actor_username, zone_id, before_json, after_json "
            f"FROM audit_logs{where} ORDER BY id DESC LIMIT ?", params,
        ).fetchall()
        keys = ["id", "action", "entity_type", "entity_id", "details", "created_at",
                "actor_user_id", "actor_username", "zone_id", "before_json", "after_json"]
        return [dict(zip(keys, row)) for row in rows]

    # ---------------- Approval Workflow & Document Templates v6.5 ----------------
    APPROVAL_STATUSES = ["در انتظار تأیید", "تأییدشده", "ردشده", "لغوشده"]
    APPROVAL_ENTITY_TYPES = {
        "action": {"table": "neighborhood_actions", "getter": "get_neighborhood_action", "title": "title"},
        "resolution": {"table": "neighborhood_resolutions", "getter": "get_neighborhood_resolution", "title": "title"},
        "budget": {"table": "neighborhood_budgets", "getter": "get_neighborhood_budget", "title": "title"},
        "letter": {"table": "correspondence_letters", "getter": "get_correspondence_letter", "title": "subject"},
    }
    DOCUMENT_TEMPLATE_TYPES = ["نامه اداری", "صورت‌جلسه", "گزارش اقدام", "اعلام پیگیری"]

    def _seed_governance_policies(self, cur=None):
        """خط‌مشی‌های پیش‌فرض نگهداری، محرمانگی و انتشار داده."""
        cur = cur or self.conn.cursor()
        defaults = [
            ("field_visit", "بازدید میدانی", "داخلی", 1825, 0, 0, 0, "اطلاعات عملیاتی بلوک"),
            ("citizen_request", "درخواست مردمی", "محرمانه", 1825, 1, 0, 1, "نام و تلفن شهروند نباید عمومی شود"),
            ("zone_profile", "پرونده جمعیت و خانوار", "داخلی", 3650, 1, 0, 0, "فقط آمار تجمیعی قابل انتشار است"),
            ("project", "پروژه اجرایی", "عمومی", 3650, 1, 1, 0, "عنوان، پیشرفت و بودجه تجمیعی قابل انتشار"),
            ("contract", "قرارداد", "داخلی", 3650, 1, 0, 0, "انتشار فقط پس از بررسی حقوقی"),
            ("letter", "مکاتبه اداری", "محرمانه", 3650, 1, 0, 1, "نامه‌ها به‌صورت پیش‌فرض عمومی نیستند"),
            ("satisfaction_survey", "رضایت مردمی", "داخلی", 1825, 0, 1, 0, "فقط نتیجه تجمیعی منتشر شود"),
        ]
        cur.executemany(
            """INSERT INTO data_governance_policies
               (entity_type,title,classification,retention_days,requires_approval,public_allowed,contains_personal_data,notes)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(entity_type) DO NOTHING""",
            defaults,
        )

    def _seed_document_templates(self, cur=None):
        cur = cur or self.conn.cursor()
        defaults = [
            (
                "نامه پیگیری دستگاه اجرایی", "نامه اداری",
                "پیگیری موضوع {subject} در محدوده {zone_name}",
                "با سلام و احترام\n\nپیرو بررسی‌های انجام‌شده در محدوده {zone_name}، موضوع «{subject}» جهت اقدام و اعلام نتیجه به آن دستگاه محترم ارجاع می‌شود. خواهشمند است نتیجه بررسی حداکثر تا تاریخ {due_date} به این فرمانداری اعلام گردد.\n\nمسئول پیگیری: {responsible_person}\nدستگاه مسئول: {responsible_office}\n\nبا احترام\n{user_full_name}",
            ),
            (
                "صورت‌جلسه شورای محله", "صورت‌جلسه",
                "صورت‌جلسه {meeting_title} — {zone_name}",
                "جلسه «{meeting_title}» در تاریخ {meeting_date} ساعت {meeting_time} در محل {meeting_place} برگزار شد.\n\nدستور جلسه:\n{agenda}\n\nحاضرین:\n{attendees}\n\nمصوبات و جمع‌بندی:\n{minutes_text}\n\nتنظیم‌کننده: {user_full_name}",
            ),
            (
                "گزارش پیشرفت اقدام", "گزارش اقدام",
                "گزارش پیشرفت {action_title}",
                "عنوان اقدام: {action_title}\nبلوک: {zone_name}\nدستگاه مسئول: {responsible_office}\nمسئول اجرا: {responsible_person}\nدرصد پیشرفت: {progress_percent}٪\nوضعیت: {action_status}\n\nشرح و نتیجه:\n{action_description}\n\nموانع:\n{obstacles}\n\nتاریخ تهیه گزارش: {date}",
            ),
            (
                "اعلام نتیجه درخواست مردمی", "اعلام پیگیری",
                "اعلام نتیجه پیگیری درخواست {tracking_code}",
                "شهروند گرامی،\n\nدرخواست شما با کد رهگیری {tracking_code} درباره «{subject}» در بلوک {zone_name} بررسی شد.\n\nنتیجه پیگیری:\n{result}\n\nوضعیت نهایی: {status}\nتاریخ: {date}",
            ),
        ]
        for name, template_type, subject_template, body_template in defaults:
            cur.execute(
                """INSERT OR IGNORE INTO document_templates
                   (name, template_type, subject_template, body_template, is_active)
                   VALUES (?, ?, ?, ?, 1)""",
                (name, template_type, subject_template, body_template),
            )

    def _get_approval_entity(self, entity_type, entity_id):
        config = self.APPROVAL_ENTITY_TYPES.get(entity_type)
        if not config:
            raise ValueError("نوع موجودیت برای گردش تأیید پشتیبانی نمی‌شود.")
        getter = getattr(self, config["getter"])
        entity = getter(int(entity_id))
        if not entity:
            raise ValueError("رکورد موردنظر برای تأیید پیدا نشد.")
        return entity

    def _set_entity_approval_status(self, entity_type, entity_id, status, approved_by=None):
        config = self.APPROVAL_ENTITY_TYPES.get(entity_type)
        if not config:
            return False
        table = config["table"]
        approved_at = "CURRENT_TIMESTAMP" if status == "تأییدشده" else "NULL"
        self.conn.execute(
            f"UPDATE {table} SET approval_status=?, approved_at={approved_at}, approved_by=? WHERE id=?",
            (status, approved_by if status == "تأییدشده" else None, int(entity_id)),
        )
        return True

    def create_approval_request(self, entity_type, entity_id, title=None, zone_id=None,
                                steps=None, due_date=None, notes=""):
        entity = self._get_approval_entity(entity_type, entity_id)
        existing = self.conn.execute(
            """SELECT id FROM approval_requests
               WHERE entity_type=? AND entity_id=? AND status='در انتظار تأیید'
               ORDER BY id DESC LIMIT 1""",
            (entity_type, str(entity_id)),
        ).fetchone()
        if existing:
            raise ValueError("برای این رکورد یک گردش تأیید فعال وجود دارد.")
        config = self.APPROVAL_ENTITY_TYPES[entity_type]
        title = (title or entity.get(config["title"]) or f"تأیید {entity_type}").strip()
        zone_id = zone_id if zone_id is not None else entity.get("zone_id")
        steps = list(steps or [
            {"approver_role": "manager", "approver_name": "مدیر محله‌محور"},
            {"approver_role": "admin", "approver_name": "مدیر سامانه"},
        ])
        cleaned_steps = []
        for step in steps:
            role = (step.get("approver_role") or "").strip() or None
            user_id = step.get("approver_user_id")
            name = (step.get("approver_name") or "").strip()
            if not role and not user_id and not name:
                continue
            cleaned_steps.append({"approver_role": role, "approver_user_id": user_id, "approver_name": name})
        if not cleaned_steps:
            raise ValueError("حداقل یک مرحله تأیید لازم است.")
        actor_id = self.current_user.get("id") if self.current_user else None
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO approval_requests
                   (zone_id, entity_type, entity_id, title, requested_by, current_step,
                    total_steps, status, due_date, notes)
                   VALUES (?, ?, ?, ?, ?, 1, ?, 'در انتظار تأیید', ?, ?)""",
                (zone_id, entity_type, str(entity_id), title, actor_id, len(cleaned_steps), due_date, notes),
            )
            approval_id = cur.lastrowid
            for index, step in enumerate(cleaned_steps, start=1):
                self.conn.execute(
                    """INSERT INTO approval_steps
                       (approval_id, step_order, approver_role, approver_user_id, approver_name, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (approval_id, index, step["approver_role"], step["approver_user_id"],
                     step["approver_name"], "در انتظار" if index == 1 else "قفل‌شده"),
                )
            self._set_entity_approval_status(entity_type, entity_id, "در انتظار تأیید")
        self.log_action(
            "approval_requested", "approval", approval_id,
            {"zone_id": zone_id, "entity_type": entity_type, "entity_id": entity_id, "steps": len(cleaned_steps)},
            zone_id=zone_id,
        )
        return approval_id

    def get_approval_request(self, approval_id):
        row = self.conn.execute(
            """SELECT a.id, a.zone_id, a.entity_type, a.entity_id, a.title, a.requested_by,
                      a.current_step, a.total_steps, a.status, a.due_date, a.notes,
                      a.completed_at, a.created_at, a.updated_at, z.name, u.full_name
               FROM approval_requests a
               LEFT JOIN zones z ON z.id=a.zone_id
               LEFT JOIN app_users u ON u.id=a.requested_by
               WHERE a.id=?""",
            (int(approval_id),),
        ).fetchone()
        if not row:
            return None
        keys = ["id", "zone_id", "entity_type", "entity_id", "title", "requested_by",
                "current_step", "total_steps", "status", "due_date", "notes",
                "completed_at", "created_at", "updated_at", "zone_name", "requested_by_name"]
        result = dict(zip(keys, row))
        result["steps"] = self.get_approval_steps(approval_id)
        return result

    def get_approval_steps(self, approval_id):
        rows = self.conn.execute(
            """SELECT s.id, s.approval_id, s.step_order, s.approver_role, s.approver_user_id,
                      s.approver_name, s.status, s.decision_comment, s.decided_by, s.decided_at,
                      s.created_at, u.full_name, du.full_name
               FROM approval_steps s
               LEFT JOIN app_users u ON u.id=s.approver_user_id
               LEFT JOIN app_users du ON du.id=s.decided_by
               WHERE s.approval_id=? ORDER BY s.step_order""",
            (int(approval_id),),
        ).fetchall()
        keys = ["id", "approval_id", "step_order", "approver_role", "approver_user_id",
                "approver_name", "status", "decision_comment", "decided_by", "decided_at",
                "created_at", "approver_user_name", "decided_by_name"]
        return [dict(zip(keys, row)) for row in rows]

    def get_approval_requests(self, status=None, zone_id=None, assigned_to_current=False, limit=1000):
        clauses, params = [], []
        if status:
            clauses.append("a.status=?")
            params.append(status)
        if zone_id is not None:
            clauses.append("a.zone_id=?")
            params.append(int(zone_id))
        if assigned_to_current:
            user = self.current_user or {}
            if not user:
                return []
            if user.get("role") != "admin":
                clauses.append(
                    "EXISTS (SELECT 1 FROM approval_steps s WHERE s.approval_id=a.id "
                    "AND s.step_order=a.current_step AND s.status='در انتظار' "
                    "AND (s.approver_user_id=? OR (s.approver_user_id IS NULL AND s.approver_role=?)))"
                )
                params.extend([user.get("id"), user.get("role")])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows = self.conn.execute(
            """SELECT a.id, a.zone_id, a.entity_type, a.entity_id, a.title,
                      a.current_step, a.total_steps, a.status, a.due_date, a.notes,
                      a.created_at, a.updated_at, z.name, u.full_name
               FROM approval_requests a
               LEFT JOIN zones z ON z.id=a.zone_id
               LEFT JOIN app_users u ON u.id=a.requested_by""" + where +
            " ORDER BY CASE a.status WHEN 'در انتظار تأیید' THEN 0 ELSE 1 END, "
            "COALESCE(a.due_date, '9999-12-31'), a.id DESC LIMIT ?",
            params,
        ).fetchall()
        keys = ["id", "zone_id", "entity_type", "entity_id", "title", "current_step",
                "total_steps", "status", "due_date", "notes", "created_at", "updated_at",
                "zone_name", "requested_by_name"]
        return [dict(zip(keys, row)) for row in rows]

    def current_user_can_decide_approval(self, approval_id):
        approval = self.get_approval_request(approval_id)
        user = self.current_user or {}
        if not approval or approval["status"] != "در انتظار تأیید" or not user:
            return False
        if user.get("role") == "admin":
            return True
        step = next((x for x in approval["steps"] if x["step_order"] == approval["current_step"]), None)
        if not step or step["status"] != "در انتظار":
            return False
        if step.get("approver_user_id") is not None:
            return int(step["approver_user_id"]) == int(user.get("id") or -1)
        return step.get("approver_role") == user.get("role")

    def decide_approval(self, approval_id, approved=True, comment=""):
        approval = self.get_approval_request(approval_id)
        if not approval or approval["status"] != "در انتظار تأیید":
            raise ValueError("گردش تأیید فعال پیدا نشد.")
        if not self.current_user_can_decide_approval(approval_id):
            raise PermissionError("کاربر فعلی مجوز تصمیم‌گیری در این مرحله را ندارد.")
        actor_id = self.current_user.get("id") if self.current_user else None
        current_order = int(approval["current_step"])
        step = next(x for x in approval["steps"] if x["step_order"] == current_order)
        decision = "تأییدشده" if approved else "ردشده"
        with self.conn:
            self.conn.execute(
                """UPDATE approval_steps SET status=?, decision_comment=?, decided_by=?,
                   decided_at=CURRENT_TIMESTAMP WHERE id=?""",
                (decision, comment, actor_id, step["id"]),
            )
            if not approved:
                self.conn.execute(
                    """UPDATE approval_requests SET status='ردشده', completed_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (approval_id,),
                )
                self._set_entity_approval_status(approval["entity_type"], approval["entity_id"], "ردشده")
                final_status = "ردشده"
            elif current_order >= int(approval["total_steps"]):
                self.conn.execute(
                    """UPDATE approval_requests SET status='تأییدشده', completed_at=CURRENT_TIMESTAMP,
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                    (approval_id,),
                )
                self._set_entity_approval_status(
                    approval["entity_type"], approval["entity_id"], "تأییدشده", actor_id
                )
                final_status = "تأییدشده"
            else:
                next_order = current_order + 1
                self.conn.execute(
                    "UPDATE approval_steps SET status='در انتظار' WHERE approval_id=? AND step_order=?",
                    (approval_id, next_order),
                )
                self.conn.execute(
                    "UPDATE approval_requests SET current_step=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (next_order, approval_id),
                )
                final_status = "در انتظار تأیید"
        self.log_action(
            "approval_decided", "approval", approval_id,
            {"approved": bool(approved), "comment": comment, "final_status": final_status},
            zone_id=approval.get("zone_id"),
        )
        return self.get_approval_request(approval_id)

    def cancel_approval(self, approval_id, note=""):
        approval = self.get_approval_request(approval_id)
        if not approval or approval["status"] != "در انتظار تأیید":
            return False
        role = (self.current_user or {}).get("role")
        actor_id = (self.current_user or {}).get("id")
        if role not in ("admin", "manager") and actor_id != approval.get("requested_by"):
            raise PermissionError("مجوز لغو این گردش تأیید وجود ندارد.")
        with self.conn:
            self.conn.execute(
                """UPDATE approval_requests SET status='لغوشده', notes=CASE WHEN ?='' THEN notes ELSE ? END,
                   completed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (note, note, approval_id),
            )
            self.conn.execute(
                "UPDATE approval_steps SET status='لغوشده' WHERE approval_id=? AND status IN ('در انتظار','قفل‌شده')",
                (approval_id,),
            )
            self._set_entity_approval_status(approval["entity_type"], approval["entity_id"], "نیاز ندارد")
        self.log_action("approval_cancelled", "approval", approval_id, {"note": note}, zone_id=approval.get("zone_id"))
        return True

    def get_approval_stats(self):
        cur = self.conn.cursor()
        today = datetime.now().date().isoformat()
        return {
            "approvals_total": cur.execute("SELECT COUNT(*) FROM approval_requests").fetchone()[0],
            "approvals_pending": cur.execute("SELECT COUNT(*) FROM approval_requests WHERE status='در انتظار تأیید'").fetchone()[0],
            "approvals_assigned_to_me": len(self.get_approval_requests(status="در انتظار تأیید", assigned_to_current=True)),
            "approvals_overdue": cur.execute(
                "SELECT COUNT(*) FROM approval_requests WHERE status='در انتظار تأیید' AND due_date IS NOT NULL AND due_date < ?",
                (today,),
            ).fetchone()[0],
        }

    def add_document_template(self, name, template_type, body_template, subject_template="", is_active=True):
        if template_type not in self.DOCUMENT_TEMPLATE_TYPES:
            raise ValueError("نوع قالب نامعتبر است.")
        actor_id = (self.current_user or {}).get("id")
        cur = self.conn.execute(
            """INSERT INTO document_templates
               (name, template_type, subject_template, body_template, is_active, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name.strip(), template_type, subject_template, body_template, 1 if is_active else 0, actor_id),
        )
        self.conn.commit()
        template_id = cur.lastrowid
        self.log_action("document_template_created", "template", template_id, {"name": name, "type": template_type})
        return template_id

    def update_document_template(self, template_id, **data):
        current = self.get_document_template(template_id)
        if not current:
            return False
        editable = ["name", "template_type", "subject_template", "body_template", "is_active"]
        merged = {key: data.get(key, current.get(key)) for key in editable}
        if merged["template_type"] not in self.DOCUMENT_TEMPLATE_TYPES:
            raise ValueError("نوع قالب نامعتبر است.")
        self.conn.execute(
            """UPDATE document_templates SET name=?, template_type=?, subject_template=?,
               body_template=?, is_active=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (merged["name"], merged["template_type"], merged["subject_template"], merged["body_template"],
             1 if merged["is_active"] else 0, template_id),
        )
        self.conn.commit()
        self.log_action("document_template_updated", "template", template_id, {"name": merged["name"]})
        return True

    def delete_document_template(self, template_id):
        self.conn.execute("DELETE FROM document_templates WHERE id=?", (int(template_id),))
        self.conn.commit()
        self.log_action("document_template_deleted", "template", template_id)

    def get_document_template(self, template_id):
        row = self.conn.execute(
            """SELECT id, name, template_type, subject_template, body_template, is_active,
                      created_by, created_at, updated_at FROM document_templates WHERE id=?""",
            (int(template_id),),
        ).fetchone()
        keys = ["id", "name", "template_type", "subject_template", "body_template", "is_active",
                "created_by", "created_at", "updated_at"]
        return dict(zip(keys, row)) if row else None

    def get_document_templates(self, template_type=None, active_only=False):
        clauses, params = [], []
        if template_type:
            clauses.append("template_type=?")
            params.append(template_type)
        if active_only:
            clauses.append("is_active=1")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(
            """SELECT id, name, template_type, subject_template, body_template, is_active,
                      created_by, created_at, updated_at FROM document_templates""" + where +
            " ORDER BY template_type, name",
            params,
        ).fetchall()
        keys = ["id", "name", "template_type", "subject_template", "body_template", "is_active",
                "created_by", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def build_document_context(self, zone_id=None, letter_id=None, meeting_id=None, action_id=None,
                               citizen_request_id=None, extra=None):
        user = self.current_user or {}
        context = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "user_full_name": user.get("full_name") or user.get("username") or "کاربر سامانه",
            "zone_name": "—", "subject": "—", "due_date": "—", "responsible_person": "—",
            "responsible_office": "—", "meeting_title": "—", "meeting_date": "—",
            "meeting_time": "—", "meeting_place": "—", "agenda": "—", "attendees": "—",
            "minutes_text": "—", "action_title": "—", "progress_percent": 0,
            "action_status": "—", "action_description": "—", "obstacles": "—",
            "tracking_code": "—", "result": "—", "status": "—",
            "letter_number": "—", "letter_date": "—", "sender": "—", "recipient": "—",
            "letter_description": "—", "attachment_text": "ندارد", "time": "—",
        }
        if zone_id is not None:
            zone = self.get_zone(zone_id)
            if zone:
                context["zone_name"] = zone.get("name") or "—"
        if letter_id is not None:
            letter = self.get_correspondence_letter(letter_id)
            if letter:
                context.update({
                    "subject": letter.get("subject") or "—",
                    "due_date": letter.get("due_date") or "—",
                    "letter_number": letter.get("letter_number") or "—",
                    "letter_date": letter.get("letter_date") or letter.get("received_date") or "—",
                    "date": letter.get("letter_date") or letter.get("received_date") or context["date"],
                    "sender": letter.get("sender") or "—",
                    "recipient": letter.get("recipient") or "—",
                    "letter_description": letter.get("description") or "—",
                    "result": letter.get("description") or context["result"],
                    "status": letter.get("status") or "—",
                    "attachment_text": str(letter.get("attachment_count") or 0) if letter.get("attachment_count") else "ندارد",
                })
                if zone_id is None and letter.get("zone_id"):
                    zone = self.get_zone(letter["zone_id"])
                    context["zone_name"] = zone.get("name") if zone else "—"
        if meeting_id is not None:
            meeting = self.get_neighborhood_meeting(meeting_id)
            if meeting:
                context.update({
                    "meeting_title": meeting.get("title") or "—",
                    "meeting_date": meeting.get("meeting_date") or "—",
                    "meeting_time": meeting.get("start_time") or "—",
                    "meeting_place": meeting.get("place_name") or "—",
                    "agenda": meeting.get("agenda") or "—",
                    "attendees": meeting.get("attendees") or "—",
                    "minutes_text": meeting.get("minutes_text") or "—",
                })
        if action_id is not None:
            action = self.get_neighborhood_action(action_id)
            if action:
                context.update({
                    "action_title": action.get("title") or "—",
                    "subject": action.get("title") or context["subject"],
                    "responsible_person": action.get("responsible_person") or "—",
                    "responsible_office": action.get("responsible_office") or "—",
                    "progress_percent": action.get("progress_percent") or 0,
                    "action_status": action.get("status") or "—",
                    "action_description": action.get("description") or action.get("result_summary") or "—",
                    "obstacles": action.get("obstacles") or "—",
                    "due_date": action.get("planned_end") or context["due_date"],
                })
        if citizen_request_id is not None:
            request = self.get_citizen_request(citizen_request_id)
            if request:
                context.update({
                    "tracking_code": request.get("tracking_code") or "—",
                    "subject": request.get("title") or "—",
                    "status": request.get("status") or "—",
                    "result": request.get("response_text") or request.get("description") or "—",
                    "responsible_office": request.get("assigned_office") or "—",
                })
        context.update(extra or {})
        return context

    def save_generated_document(self, template_id, title, content, file_path=None, zone_id=None,
                                related_entity_type=None, related_entity_id=None):
        actor_id = (self.current_user or {}).get("id")
        cur = self.conn.execute(
            """INSERT INTO generated_documents
               (template_id, zone_id, related_entity_type, related_entity_id, title,
                content, file_path, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (template_id, zone_id, related_entity_type, str(related_entity_id) if related_entity_id is not None else None,
             title, content, file_path, actor_id),
        )
        self.conn.commit()
        document_id = cur.lastrowid
        self.log_action("document_generated", "generated_document", document_id,
                        {"zone_id": zone_id, "title": title, "file_path": file_path}, zone_id=zone_id)
        return document_id

    def get_generated_documents(self, zone_id=None, limit=500):
        clauses, params = [], []
        if zone_id is not None:
            clauses.append("g.zone_id=?")
            params.append(int(zone_id))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows = self.conn.execute(
            """SELECT g.id, g.template_id, g.zone_id, g.related_entity_type, g.related_entity_id,
                      g.title, g.content, g.file_path, g.created_by, g.created_at,
                      t.name, z.name, u.full_name
               FROM generated_documents g
               LEFT JOIN document_templates t ON t.id=g.template_id
               LEFT JOIN zones z ON z.id=g.zone_id
               LEFT JOIN app_users u ON u.id=g.created_by""" + where +
            " ORDER BY g.id DESC LIMIT ?",
            params,
        ).fetchall()
        keys = ["id", "template_id", "zone_id", "related_entity_type", "related_entity_id",
                "title", "content", "file_path", "created_by", "created_at",
                "template_name", "zone_name", "created_by_name"]
        return [dict(zip(keys, row)) for row in rows]

    def get_zone_decision_rows(self):
        rows = []
        today = datetime.now().date().isoformat()
        for zone in self.get_zones():
            zid = zone["id"]
            performance = self.get_zone_performance(zid)
            issues = self.get_neighborhood_issues(zid)
            actions = self.get_neighborhood_actions(zid)
            resolutions = self.get_neighborhood_resolutions(zone_id=zid)
            citizen = self.get_citizen_requests(zid)
            budget = self.get_budget_summary(zid)
            pending_approvals = self.conn.execute(
                "SELECT COUNT(*) FROM approval_requests WHERE zone_id=? AND status='در انتظار تأیید'", (zid,)
            ).fetchone()[0]
            overdue_approvals = self.conn.execute(
                """SELECT COUNT(*) FROM approval_requests WHERE zone_id=? AND status='در انتظار تأیید'
                   AND due_date IS NOT NULL AND due_date < ?""", (zid, today)
            ).fetchone()[0]
            rows.append({
                "zone_id": zid,
                "zone_name": zone.get("name"),
                "score": performance.get("total_score", 0),
                "level": performance.get("level"),
                "households": self.get_zone_profile(zid).get("approved_households", 0),
                "open_issues": sum(1 for x in issues if x.get("status") not in ("مختومه", "انجام‌شده")),
                "critical_issues": sum(1 for x in issues if x.get("priority_level") in ("فوری", "بحرانی") and x.get("status") not in ("مختومه", "انجام‌شده")),
                "active_actions": sum(1 for x in actions if x.get("status") in ("در حال اجرا", "برنامه‌ریزی‌شده")),
                "overdue_actions": performance.get("overdue_actions", 0),
                "pending_resolutions": sum(1 for x in resolutions if x.get("status") not in ("انجام‌شده", "لغوشده")),
                "open_citizen_requests": sum(1 for x in citizen if x.get("status") not in ("پاسخ‌داده‌شده", "مختومه", "ردشده")),
                "budget_spent": budget.get("spent", 0),
                "budget_allocated": budget.get("allocated", 0),
                "budget_overruns": budget.get("overrun_count", 0),
                "pending_approvals": pending_approvals,
                "overdue_approvals": overdue_approvals,
            })
        return sorted(rows, key=lambda x: (x["score"], -x["critical_issues"], x["zone_name"] or ""))

    # ---------------- Zone Snapshots (نمای گرافیکی بلوک) ----------------
    def save_zone_snapshot(self, zone_id, svg_text, png_data, thumbnail_data,
                           content_hash, width=1200, height=900,
                           render_status="ready", error_message=None):
        self.conn.execute(
            """INSERT INTO zone_snapshots
               (zone_id, svg_text, png_data, thumbnail_data, content_hash, width, height,
                render_status, error_message, version, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
               ON CONFLICT(zone_id) DO UPDATE SET
                 svg_text=excluded.svg_text,
                 png_data=excluded.png_data,
                 thumbnail_data=excluded.thumbnail_data,
                 content_hash=excluded.content_hash,
                 width=excluded.width,
                 height=excluded.height,
                 render_status=excluded.render_status,
                 error_message=excluded.error_message,
                 version=zone_snapshots.version + 1,
                 generated_at=CURRENT_TIMESTAMP""",
            (zone_id, svg_text, png_data, thumbnail_data, content_hash, width, height,
             render_status, error_message),
        )
        self.conn.commit()

    def get_zone_snapshot(self, zone_id):
        row = self.conn.execute(
            """SELECT zone_id, svg_text, png_data, thumbnail_data, content_hash,
                      width, height, render_status, error_message, version, generated_at
               FROM zone_snapshots WHERE zone_id=?""",
            (zone_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "zone_id": row[0], "svg_text": row[1], "png_data": row[2],
            "thumbnail_data": row[3], "content_hash": row[4],
            "width": row[5] or 1200, "height": row[6] or 900,
            "render_status": row[7] or "dirty", "error_message": row[8],
            "version": row[9] or 1, "generated_at": row[10],
        }

    def mark_zone_snapshot_dirty(self, zone_id, error_message=None, status="dirty"):
        self.conn.execute(
            """INSERT INTO zone_snapshots (zone_id, render_status, error_message, generated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(zone_id) DO UPDATE SET
                 render_status=excluded.render_status,
                 error_message=excluded.error_message,
                 generated_at=CURRENT_TIMESTAMP""",
            (zone_id, status, error_message),
        )
        self.conn.commit()

    def delete_zone_snapshot(self, zone_id):
        self.conn.execute("DELETE FROM zone_snapshots WHERE zone_id=?", (zone_id,))
        self.conn.commit()

    # ---------------- Boundary ----------------
    def save_boundary(self, points):
        """points: لیستی از (lat, lon) به ترتیب رسم مرز"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM boundary")
        for i, (lat, lon) in enumerate(points):
            cur.execute(
                "INSERT INTO boundary (seq, lat, lon) VALUES (?, ?, ?)",
                (i, lat, lon)
            )
        self.conn.commit()

    def get_boundary(self):
        cur = self.conn.cursor()
        cur.execute("SELECT lat, lon FROM boundary ORDER BY seq ASC")
        return cur.fetchall()

    def recalculate_all_zone_metrics(self):
        """مساحت و محیط همه بلوک‌ها را از هندسه اصلی دوباره محاسبه و ذخیره می‌کند."""
        cur = self.conn.cursor()
        updated = 0
        for zone_id, boundary_text in cur.execute(
            "SELECT id, boundary_points FROM zones ORDER BY id"
        ).fetchall():
            try:
                points = json.loads(boundary_text) if boundary_text else []
                area_m2, perimeter_m = polygon_metrics(points)
            except Exception:
                area_m2, perimeter_m = 0.0, 0.0
            cur.execute(
                "UPDATE zones SET area_m2=?, perimeter_m=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (area_m2, perimeter_m, zone_id),
            )
            updated += 1
        self.conn.commit()
        return updated

    def get_area_summary(self):
        """خلاصه دقیق مساحت محدوده شهر و مجموع بلوک‌های ثبت‌شده را برمی‌گرداند."""
        city_points = self.get_boundary()
        city_area_m2, city_perimeter_m = polygon_metrics(city_points)

        zones = self.get_zones()
        block_area_m2 = math.fsum(float(z.get("area_m2") or 0.0) for z in zones)
        block_perimeter_m = math.fsum(float(z.get("perimeter_m") or 0.0) for z in zones)
        difference_m2 = city_area_m2 - block_area_m2
        coverage_percent = (block_area_m2 / city_area_m2 * 100.0) if city_area_m2 > 0 else 0.0

        return {
            "city_area_m2": city_area_m2,
            "city_area_ha": city_area_m2 / 10000.0,
            "city_perimeter_m": city_perimeter_m,
            "block_area_m2": block_area_m2,
            "block_area_ha": block_area_m2 / 10000.0,
            "block_perimeter_m": block_perimeter_m,
            "difference_m2": difference_m2,
            "difference_ha": difference_m2 / 10000.0,
            "coverage_percent": coverage_percent,
            "zone_count": len(zones),
        }

    # ---------------- Zones (مناطق/بلوک‌ها) ----------------

    # پالت رنگ‌های از پیش تعیین‌شده برای اختصاص خودکار و غیرتکراری به مناطق
    ZONE_COLOR_PALETTE = [
        "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
        "#dcbeff", "#9A6324", "#808000", "#ffd8b1", "#000075",
        "#a9a9a9", "#800000", "#aaffc3", "#808080", "#ffe119",
    ]

    def get_next_zone_color(self):
        """اولین رنگی از پالت که هنوز برای هیچ منطقه‌ای استفاده نشده را برمی‌گرداند."""
        cur = self.conn.cursor()
        cur.execute("SELECT color FROM zones")
        used_colors = {row[0] for row in cur.fetchall()}
        for color in self.ZONE_COLOR_PALETTE:
            if color not in used_colors:
                return color
        # اگر همه رنگ‌های پالت استفاده شده بودند، یک رنگ تصادفی بساز
        import random
        return "#%06x" % random.randint(0, 0xFFFFFF)

    def create_zone(self, name, boundary_points, color=None):
        """یک منطقه/بلوک جدید با نام و محدوده مشخص می‌سازد و رنگ غیرتکراری به آن اختصاص می‌دهد."""
        if color is None:
            color = self.get_next_zone_color()
        cur = self.conn.cursor()
        area_m2, perimeter_m = polygon_metrics(boundary_points)
        cur.execute(
            "INSERT INTO zones (name, color, boundary_points, area_m2, perimeter_m, status, updated_at) VALUES (?, ?, ?, ?, ?, 'ناقص', CURRENT_TIMESTAMP)",
            (name, color, json.dumps(boundary_points), area_m2, perimeter_m)
        )
        zone_id = cur.lastrowid
        self.conn.commit()
        self.sync_zone_mosques(zone_id, boundary_points, refresh_snapshot=True)
        self.ensure_zone_committees(zone_id)
        if hasattr(self, "ensure_social_council"):
            self.ensure_social_council(zone_id)
        self.log_action("create", "zone", zone_id, {"name": name, "area_m2": round(area_m2, 2)})
        return zone_id

    def update_zone(self, zone_id, name=None, boundary_points=None, color=None):
        cur = self.conn.cursor()
        if name is not None:
            cur.execute("UPDATE zones SET name=? WHERE id=?", (name, zone_id))
        if boundary_points is not None:
            area_m2, perimeter_m = polygon_metrics(boundary_points)
            cur.execute(
                "UPDATE zones SET boundary_points=?, area_m2=?, perimeter_m=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (json.dumps(boundary_points), area_m2, perimeter_m, zone_id)
            )
        if color is not None:
            cur.execute("UPDATE zones SET color=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (color, zone_id))
        if name is not None:
            cur.execute("UPDATE zones SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (zone_id,))
        self.conn.commit()
        if boundary_points is not None:
            self.sync_zone_mosques(zone_id, boundary_points, refresh_snapshot=True)
        elif name is not None or color is not None:
            self._refresh_zone_snapshot_safe(zone_id)
        self.log_action("update", "zone", zone_id, {"name": name, "boundary_changed": boundary_points is not None, "color": color})

    def delete_zone(self, zone_id):
        # حذف‌های عملیات میدانی و درخواست مردمی در صف تبادل ثبت می‌شوند تا مقصد نیز پاک‌سازی شود.
        if hasattr(self, "get_field_visits"):
            for item in list(self.get_field_visits(zone_id)):
                self.delete_field_visit(item["id"], queue_change=True)
        if hasattr(self, "get_citizen_requests"):
            for item in list(self.get_citizen_requests(zone_id)):
                self.delete_citizen_request(item["id"], queue_change=True)
        cur = self.conn.cursor()
        cur.execute("DELETE FROM zone_snapshots WHERE zone_id=?", (zone_id,))
        cur.execute("DELETE FROM zone_mosques WHERE zone_id=?", (zone_id,))
        cur.execute("DELETE FROM streets WHERE zone_id=?", (zone_id,))
        cur.execute("DELETE FROM places WHERE zone_id=? AND COALESCE(category, '')<>'manual'", (zone_id,))
        cur.execute("DELETE FROM zones WHERE id=?", (zone_id,))
        self.conn.commit()
        self.log_action("delete", "zone", zone_id)

    def get_zones(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, color, boundary_points, created_at, status, area_m2, perimeter_m, updated_at FROM zones ORDER BY created_at ASC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            zone_id = r[0]
            street_count = self.conn.execute("SELECT COUNT(*) FROM streets WHERE zone_id=?", (zone_id,)).fetchone()[0]
            place_count = self.conn.execute("SELECT COUNT(*) FROM places WHERE zone_id=?", (zone_id,)).fetchone()[0]
            mosque_count = self.conn.execute("SELECT COUNT(*) FROM zone_mosques WHERE zone_id=?", (zone_id,)).fetchone()[0]
            has_meeting = self.conn.execute("SELECT 1 FROM zone_meeting_places WHERE zone_id=?", (zone_id,)).fetchone() is not None
            computed_status = "ناقص" if street_count == 0 else ("کامل" if has_meeting else "در حال تکمیل")
            if computed_status != (r[5] or ""):
                self.conn.execute("UPDATE zones SET status=? WHERE id=?", (computed_status, zone_id))
            result.append({
                "id": zone_id,
                "name": r[1],
                "color": r[2],
                "boundary_points": json.loads(r[3]) if r[3] else [],
                "created_at": r[4],
                "street_count": street_count,
                "place_count": place_count,
                "mosque_count": mosque_count,
                "status": computed_status,
                "area_m2": r[6] or 0,
                "perimeter_m": r[7] or 0,
                "updated_at": r[8],
            })
        self.conn.commit()
        return result

    def get_zone(self, zone_id):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, color, boundary_points, created_at, status, area_m2, perimeter_m, updated_at FROM zones WHERE id=?", (zone_id,))
        r = cur.fetchone()
        if not r:
            return None
        street_count = self.conn.execute("SELECT COUNT(*) FROM streets WHERE zone_id=?", (zone_id,)).fetchone()[0]
        has_meeting = self.conn.execute("SELECT 1 FROM zone_meeting_places WHERE zone_id=?", (zone_id,)).fetchone() is not None
        computed_status = "ناقص" if street_count == 0 else ("کامل" if has_meeting else "در حال تکمیل")
        if computed_status != (r[5] or ""):
            self.conn.execute("UPDATE zones SET status=? WHERE id=?", (computed_status, zone_id))
            self.conn.commit()
        return {
            "id": r[0], "name": r[1], "color": r[2],
            "boundary_points": json.loads(r[3]) if r[3] else [],
            "created_at": r[4],
            "status": computed_status,
            "area_m2": r[6] or 0,
            "perimeter_m": r[7] or 0,
            "updated_at": r[8],
        }

    # ---------------- Mosques (فهرست مرجع و ارتباط با بلوک‌ها) ----------------
    def _seed_mosques(self):
        """فهرست ثابت ۲۴ مسجد را بدون ایجاد رکورد تکراری در دیتابیس درج/به‌روزرسانی می‌کند."""
        cur = self.conn.cursor()
        cur.executemany(
            """INSERT INTO mosques (id, name, lat, lon, aliases, source, updated_at)
               VALUES (?, ?, ?, ?, ?, 'فهرست مرجع پروژه', CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, lat=excluded.lat, lon=excluded.lon,
                 aliases=excluded.aliases, source=excluded.source, updated_at=CURRENT_TIMESTAMP""",
            [(m["id"], m["name"], m["lat"], m["lon"], json.dumps(m.get("aliases", []), ensure_ascii=False))
             for m in MOSQUES]
        )
        # هر رکورد قدیمی خارج از فهرست مرجع حذف می‌شود تا تعداد دقیقاً ۲۴ باقی بماند.
        placeholders = ",".join("?" for _ in MOSQUES)
        cur.execute(f"DELETE FROM mosques WHERE id NOT IN ({placeholders})", [m["id"] for m in MOSQUES])
        self.conn.commit()

    def get_mosques(self, zone_id=None):
        cur = self.conn.cursor()
        if zone_id is None:
            cur.execute(
                """SELECT m.id, m.name, m.lat, m.lon, m.aliases, m.source,
                          i.first_name, i.last_name, i.mobile
                   FROM mosques m LEFT JOIN mosque_imams i ON i.mosque_id=m.id
                   ORDER BY m.name COLLATE NOCASE"""
            )
        else:
            cur.execute(
                """SELECT m.id, m.name, m.lat, m.lon, m.aliases, m.source,
                          i.first_name, i.last_name, i.mobile
                   FROM mosques m
                   INNER JOIN zone_mosques zm ON zm.mosque_id=m.id
                   LEFT JOIN mosque_imams i ON i.mosque_id=m.id
                   WHERE zm.zone_id=?
                   ORDER BY m.name COLLATE NOCASE""",
                (zone_id,)
            )
        rows = cur.fetchall()
        result = []
        for r in rows:
            imam_label = f"{r[6]} {r[7]}".strip() if r[6] else ""
            result.append({
                "id": r[0], "name": r[1], "lat": r[2], "lon": r[3],
                "aliases": json.loads(r[4]) if r[4] else [], "source": r[5],
                "imam_label": imam_label,
                "imam_mobile": (r[8] or "") if r[6] else "",
            })
        return result

    def get_places_with_mosques(self, zone_id=None):
        """نمای یکپارچه اماکن و مساجد مرجع برای رابط کاربری.

        مسجدها در جدول places کپی نمی‌شوند؛ فقط به‌صورت رکورد نمایشی با record_type=mosque
        به نتیجه افزوده می‌شوند تا داده مرجع تکراری یا قابل حذف تصادفی نباشد.
        """
        zone_names = {z["id"]: z["name"] for z in self.get_zones()}
        result = []
        for place in self.get_places(zone_id=zone_id):
            item = dict(place)
            item["record_type"] = "place"
            item["zone_name"] = zone_names.get(item.get("zone_id"), "—")
            result.append(item)

        mosques = self.get_mosques(zone_id=zone_id) if zone_id is not None else self.get_mosques()
        for mosque in mosques:
            if zone_id is not None:
                related_zone_name = zone_names.get(zone_id, "—")
            else:
                related = self.get_mosque_zone_names(mosque["id"])
                related_zone_name = "، ".join(z["name"] for z in related) or "خارج از بلوک‌ها"
            result.append({
                "id": f"mosque:{mosque['id']}",
                "mosque_id": mosque["id"],
                "name": mosque["name"],
                "category": "مسجد",
                "subtype": "مسجد مرجع",
                "lat": mosque["lat"],
                "lon": mosque["lon"],
                "zone_id": zone_id,
                "zone_name": related_zone_name,
                "record_type": "mosque",
            })

        return sorted(result, key=lambda item: (item.get("record_type") != "mosque", item.get("name", "")))

    def get_mosque_zone_names(self, mosque_id):
        cur = self.conn.cursor()
        cur.execute(
            """SELECT z.id, z.name FROM zones z
               INNER JOIN zone_mosques zm ON zm.zone_id=z.id
               WHERE zm.mosque_id=? ORDER BY z.name""",
            (mosque_id,)
        )
        return [{"id": r[0], "name": r[1]} for r in cur.fetchall()]

    def sync_zone_mosques(self, zone_id, boundary_points=None, refresh_snapshot=True):
        """عضویت مسجدها در یک بلوک را بر پایه نقطه‌درچندضلعی، اتمیک بازسازی می‌کند."""
        if boundary_points is None:
            zone = self.get_zone(zone_id)
            boundary_points = zone["boundary_points"] if zone else []
        boundary_points = [(float(p[0]), float(p[1])) for p in (boundary_points or [])]
        selected_ids = [
            m["id"] for m in self.get_mosques()
            if point_in_polygon(float(m["lat"]), float(m["lon"]), boundary_points)
        ]
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            cur.execute("DELETE FROM zone_mosques WHERE zone_id=?", (zone_id,))
            cur.executemany(
                "INSERT INTO zone_mosques (zone_id, mosque_id) VALUES (?, ?)",
                [(zone_id, mosque_id) for mosque_id in selected_ids]
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        if refresh_snapshot:
            self._refresh_zone_snapshot_safe(zone_id)
        return len(selected_ids)

    def sync_all_zone_mosques(self):
        for zone in self.get_zones():
            self.sync_zone_mosques(zone["id"], zone["boundary_points"], refresh_snapshot=False)

    # ---------------- Streets ----------------
    def clear_streets(self, zone_id=None):
        if zone_id is not None:
            self.conn.execute("DELETE FROM streets WHERE zone_id=?", (zone_id,))
        else:
            self.conn.execute("DELETE FROM streets WHERE zone_id IS NULL")
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def save_street(self, osm_id, name, highway_type, geometry, zone_id=None, segment_index=0, is_unnamed=0):
        """geometry: لیست [(lat, lon), ...] که به صورت JSON ذخیره می‌شود"""
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO streets (zone_id, osm_id, segment_index, name, is_unnamed, highway_type, geometry, geometry_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (zone_id, osm_id, segment_index, name, int(bool(is_unnamed)), highway_type, json.dumps(geometry), geometry_hash(geometry))
        )
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def save_streets_bulk(self, streets, zone_id=None):
        """streets: لیستی از دیکشنری‌ها {osm_id, name, highway_type, geometry}"""
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO streets (zone_id, osm_id, segment_index, name, is_unnamed, highway_type, geometry, geometry_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [(zone_id, s.get("osm_id"), s.get("segment_index", 0), s.get("name"), int(bool(s.get("is_unnamed", 0))), s.get("highway_type"), json.dumps(s.get("geometry", [])), geometry_hash(s.get("geometry", []))) for s in streets]
        )
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def get_streets(self, zone_id=None):
        cur = self.conn.cursor()
        if zone_id is not None:
            cur.execute("SELECT id, zone_id, osm_id, segment_index, name, is_unnamed, highway_type, geometry FROM streets WHERE zone_id=? ORDER BY name ASC", (zone_id,))
        else:
            cur.execute("SELECT id, zone_id, osm_id, segment_index, name, is_unnamed, highway_type, geometry FROM streets ORDER BY name ASC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "zone_id": r[1],
                "osm_id": r[2],
                "segment_index": r[3] or 0,
                "name": r[4] or "(بدون نام)",
                "is_unnamed": bool(r[5]),
                "highway_type": r[6],
                "geometry": json.loads(r[7]) if r[7] else []
            })
        return result

    def update_street(self, street_id, name=None, highway_type=None):
        cur = self.conn.cursor()
        row = cur.execute("SELECT zone_id FROM streets WHERE id=?", (street_id,)).fetchone()
        zone_id = row[0] if row else None
        if name is not None:
            cur.execute("UPDATE streets SET name=? WHERE id=?", (name, street_id))
        if highway_type is not None:
            cur.execute("UPDATE streets SET highway_type=? WHERE id=?", (highway_type, street_id))
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def delete_street(self, street_id):
        cur = self.conn.cursor()
        row = cur.execute("SELECT zone_id FROM streets WHERE id=?", (street_id,)).fetchone()
        zone_id = row[0] if row else None
        cur.execute("DELETE FROM streets WHERE id=?", (street_id,))
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    # ---------------- Places ----------------
    def clear_places(self, zone_id=None):
        if zone_id is not None:
            self.conn.execute("DELETE FROM places WHERE zone_id=?", (zone_id,))
        else:
            self.conn.execute("DELETE FROM places WHERE zone_id IS NULL")
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def save_place(self, osm_id, name, category, subtype, lat, lon, address="", zone_id=None):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO places (zone_id, osm_id, name, category, subtype, lat, lon, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (zone_id, osm_id, name, category, subtype, lat, lon, address)
        )
        place_id = cur.lastrowid
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)
        return place_id

    def save_places_bulk(self, places, zone_id=None):
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT INTO places (zone_id, osm_id, name, category, subtype, lat, lon, address) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(zone_id, p["osm_id"], p["name"], p["category"], p["subtype"], p["lat"], p["lon"], p.get("address", "")) for p in places]
        )
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def get_places(self, category=None, zone_id=None):
        cur = self.conn.cursor()
        conditions = []
        params = []
        if category:
            conditions.append("category=?")
            params.append(category)
        if zone_id is not None:
            conditions.append("zone_id=?")
            params.append(zone_id)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur.execute(
            f"""SELECT p.id, p.zone_id, p.osm_id, p.name, p.category, p.subtype, p.lat, p.lon, p.address,
                       m.first_name, m.last_name, m.mobile, m.role_label, m.council_member_id
                FROM places p LEFT JOIN place_managers m ON m.place_id=p.id
                {where_clause.replace('category=?', 'p.category=?').replace('zone_id=?', 'p.zone_id=?')}
                ORDER BY p.category ASC, p.name ASC""",
            params
        )
        rows = cur.fetchall()
        result = []
        for r in rows:
            manager_label = f"{r[9] or ''} {r[10] or ''}".strip()
            result.append({
                "id": r[0], "zone_id": r[1], "osm_id": r[2], "name": r[3] or "(بدون نام)",
                "category": r[4], "subtype": r[5], "lat": r[6], "lon": r[7], "address": r[8],
                "manager_label": manager_label, "manager_mobile": r[11] or "",
                "manager_role": r[12] or "", "manager_council_member_id": r[13],
            })
        return result

    def get_place(self, place_id):
        places = self.get_places()
        return next((place for place in places if int(place["id"]) == int(place_id)), None)

    def update_place(self, place_id, name=None, category=None, subtype=None, address=None):
        cur = self.conn.cursor()
        row = cur.execute("SELECT zone_id FROM places WHERE id=?", (place_id,)).fetchone()
        zone_id = row[0] if row else None
        if name is not None:
            cur.execute("UPDATE places SET name=? WHERE id=?", (name, place_id))
        if category is not None:
            cur.execute("UPDATE places SET category=? WHERE id=?", (category, place_id))
        if subtype is not None:
            cur.execute("UPDATE places SET subtype=? WHERE id=?", (subtype, place_id))
        if address is not None:
            cur.execute("UPDATE places SET address=? WHERE id=?", (address, place_id))
        self.conn.commit()
        # عنوان معتمد وابسته به مکان نیز با نام/نوع جدید همگام می‌شود.
        manager = self.get_place_manager(place_id) if hasattr(self, "get_place_manager") else None
        if manager and manager.get("council_member_id"):
            place = self.get_place(place_id)
            role = manager.get("role_label") or "مسئول مکان"
            member = self.get_council_member(manager["council_member_id"])
            if place and member:
                self.update_council_member(
                    member["id"], member.get("first_name") or "", member.get("last_name") or "",
                    member.get("national_code") or "", member.get("education") or "",
                    member.get("mobile") or "", "معتمد", f"{role} {place['name']}",
                )
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def delete_place(self, place_id):
        cur = self.conn.cursor()
        row = cur.execute("SELECT zone_id FROM places WHERE id=?", (place_id,)).fetchone()
        zone_id = row[0] if row else None
        cur.execute("DELETE FROM places WHERE id=?", (place_id,))
        self.conn.commit()
        if zone_id is not None:
            self._refresh_zone_snapshot_safe(zone_id)

    def replace_osm_data(self, zone_id, streets=None, places=None, replace_streets=True, replace_places=True):
        """
        جایگزینی اتمیک داده‌های OSM. فقط بخش‌هایی که دریافتشان موفق بوده جایگزین می‌شوند؛
        در صورت خطا، کل تراکنش rollback شده و داده قبلی باقی می‌ماند.
        """
        streets = streets or []
        places = places or []
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            if replace_streets:
                if zone_id is None:
                    cur.execute("DELETE FROM streets WHERE zone_id IS NULL")
                else:
                    cur.execute("DELETE FROM streets WHERE zone_id=?", (zone_id,))
                cur.executemany(
                    "INSERT INTO streets (zone_id, osm_id, segment_index, name, is_unnamed, highway_type, geometry, geometry_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    [(zone_id, st.get("osm_id"), st.get("segment_index", 0), st.get("name"), int(bool(st.get("is_unnamed", 0))), st.get("highway_type"),
                      json.dumps(st.get("geometry", [])), geometry_hash(st.get("geometry", []))) for st in streets]
                )
            if replace_places:
                # اماکن دستی و هر مکان دارای مسئول ثبت‌شده حفظ می‌شوند تا معتمد مرتبط
                # و انتخاب محل جلسه در بروزرسانی بعدی OSM از بین نرود.
                if zone_id is None:
                    preserved_rows = cur.execute(
                        """SELECT p.osm_id FROM places p
                           WHERE p.zone_id IS NULL AND p.osm_id IS NOT NULL
                             AND EXISTS (SELECT 1 FROM place_managers m WHERE m.place_id=p.id)"""
                    ).fetchall()
                    cur.execute(
                        """DELETE FROM places WHERE zone_id IS NULL
                           AND COALESCE(category, '')<>'manual'
                           AND NOT EXISTS (SELECT 1 FROM place_managers m WHERE m.place_id=places.id)"""
                    )
                else:
                    preserved_rows = cur.execute(
                        """SELECT p.osm_id FROM places p
                           WHERE p.zone_id=? AND p.osm_id IS NOT NULL
                             AND EXISTS (SELECT 1 FROM place_managers m WHERE m.place_id=p.id)""",
                        (zone_id,),
                    ).fetchall()
                    cur.execute(
                        """DELETE FROM places WHERE zone_id=?
                           AND COALESCE(category, '')<>'manual'
                           AND NOT EXISTS (SELECT 1 FROM place_managers m WHERE m.place_id=places.id)""",
                        (zone_id,),
                    )
                preserved_osm_ids = {row[0] for row in preserved_rows}
                new_places = [pl for pl in places if pl.get("osm_id") not in preserved_osm_ids]
                cur.executemany(
                    "INSERT INTO places (zone_id, osm_id, name, category, subtype, lat, lon, address) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(zone_id, pl.get("osm_id"), pl.get("name"), pl.get("category"), pl.get("subtype"),
                      pl.get("lat"), pl.get("lon"), pl.get("address", "")) for pl in new_places]
                )
            self.conn.commit()
            self.log_action("replace_osm_data", "zone", zone_id, {"streets": len(streets) if replace_streets else None, "places": len(places) if replace_places else None})
            if zone_id is not None:
                self._refresh_zone_snapshot_safe(zone_id, force=True)
        except Exception:
            self.conn.rollback()
            raise

    # ---------------- Tiles (آفلاین) ----------------
    def save_tile(self, z, x, y, image_bytes):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO tiles (z, x, y, image_data) VALUES (?, ?, ?, ?)",
            (z, x, y, image_bytes)
        )
        self.conn.commit()

    def save_tiles_bulk(self, records):
        """ذخیره گروهی تایل‌ها در یک تراکنش برای سرعت و کاهش استهلاک دیسک."""
        if not records:
            return
        self.conn.executemany(
            "INSERT OR REPLACE INTO tiles (z, x, y, image_data) VALUES (?, ?, ?, ?)",
            records
        )
        self.conn.commit()

    def get_all_tile_keys(self):
        return {(int(r[0]), int(r[1]), int(r[2])) for r in self.conn.execute("SELECT z, x, y FROM tiles").fetchall()}

    def get_tile(self, z, x, y):
        cur = self.conn.cursor()
        cur.execute("SELECT image_data FROM tiles WHERE z=? AND x=? AND y=?", (z, x, y))
        row = cur.fetchone()
        return row[0] if row else None

    def count_tiles(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tiles")
        return cur.fetchone()[0]

    def clear_tiles(self):
        """پاک‌سازی کش قدیمی تایل‌ها؛ داده‌های اصلی نقشه، بلوک‌ها و اماکن دست‌نخورده می‌مانند."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tiles")
        count = int(cur.fetchone()[0] or 0)
        cur.execute("DELETE FROM tiles")
        self.conn.commit()
        return count

    def tile_exists(self, z, x, y):
        cur = self.conn.cursor()
        cur.execute("SELECT 1 FROM tiles WHERE z=? AND x=? AND y=?", (z, x, y))
        return cur.fetchone() is not None

    # ---------------- Metadata ----------------
    def set_meta(self, key, value):
        cur = self.conn.cursor()
        cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()

    def get_meta(self, key, default=None):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM metadata WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else default

    def create_backup(self, destination_path, backup_type="manual", reason=""):
        """ساخت بکاپ سازگار SQLite با API داخلی backup؛ مستقل از WAL و ایمن‌تر از کپی فایل."""
        if not destination_path:
            raise ValueError("مسیر بکاپ مشخص نشده است.")
        destination_path = os.path.abspath(destination_path)
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        if os.path.abspath(self.db_path) == destination_path:
            raise ValueError("مسیر بکاپ نمی‌تواند همان فایل دیتابیس اصلی باشد.")
        temp_path = destination_path + ".tmp"
        if os.path.exists(temp_path):
            os.remove(temp_path)
        target = None
        try:
            self.conn.commit()
            target = sqlite3.connect(temp_path)
            self.conn.backup(target)
            target.commit()
            target.close()
            target = None
            valid, message = self.validate_database_file(temp_path)
            if not valid:
                raise RuntimeError(message)
            os.replace(temp_path, destination_path)
            try:
                self.register_backup(destination_path, backup_type=backup_type, reason=reason)
            except Exception:
                pass
            self.log_action("backup_created", "database", os.path.basename(destination_path),
                            {"type": backup_type, "reason": reason})
            return destination_path
        finally:
            if target is not None:
                target.close()
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def create_automatic_backup(self, reason="safety", keep=10):
        """بکاپ نجات قبل از ریست/بازگردانی و نگهداری آخرین نسخه‌ها."""
        backup_dir = os.path.join(os.path.dirname(self.db_path), "automatic_backups")
        os.makedirs(backup_dir, exist_ok=True)
        safe_reason = "".join(ch for ch in str(reason) if ch.isalnum() or ch in ("-", "_")) or "safety"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(backup_dir, f"{safe_reason}_{timestamp}.db")
        self.create_backup(path, backup_type="automatic", reason=reason)
        files = sorted(
            (os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith(".db")),
            key=lambda item: os.path.getmtime(item), reverse=True,
        )
        for old_path in files[max(1, int(keep)):]:
            try:
                os.remove(old_path)
            except OSError:
                pass
        return path

    def checkpoint(self):
        """
        merge کردن کامل فایل WAL درون فایل اصلی دیتابیس.
        چون این برنامه در حالت journal_mode=WAL کار می‌کند، تغییرات اخیر ممکن است
        هنوز فقط در فایل کمکی <name>.db-wal نوشته شده باشند، نه در خود فایل اصلی .db.
        پیش از هرگونه کپی مستقیم فایل دیتابیس (مثلاً برای بکاپ‌گیری)، باید ابتدا
        این متد را صدا زد تا کپی حاصل، کامل و معتبر باشد.
        """
        self.conn.commit()
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

    def close(self):
        self.conn.close()

    # ---------------- City-Wide Map (نقشه کامل شهر - مستقل از بلوک‌بندی) ----------------
    def save_city_wide_boundary(self, points):
        """points: لیستی از (lat, lon) به ترتیب رسم مرز کل شهر"""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM city_wide_boundary")
        for i, (lat, lon) in enumerate(points):
            cur.execute(
                "INSERT INTO city_wide_boundary (seq, lat, lon) VALUES (?, ?, ?)",
                (i, lat, lon)
            )
        self.conn.commit()

    def get_city_wide_boundary(self):
        cur = self.conn.cursor()
        cur.execute("SELECT lat, lon FROM city_wide_boundary ORDER BY seq ASC")
        return cur.fetchall()

    def replace_city_wide_osm_data(self, streets=None, places=None, replace_streets=True, replace_places=True):
        """جایگزینی اتمیک داده‌های نقشه کامل شهر؛ بخش ناموفق دست‌نخورده می‌ماند."""
        streets = streets or []
        places = places or []
        cur = self.conn.cursor()
        try:
            cur.execute("BEGIN")
            if replace_streets:
                cur.execute("DELETE FROM city_wide_streets")
                cur.executemany(
                    "INSERT INTO city_wide_streets (osm_id, segment_index, name, is_unnamed, highway_type, geometry, geometry_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    [(s.get("osm_id"), s.get("segment_index", 0), s.get("name"), int(bool(s.get("is_unnamed", 0))), s.get("highway_type"), json.dumps(s.get("geometry", [])), geometry_hash(s.get("geometry", []))) for s in streets]
                )
            if replace_places:
                cur.execute("DELETE FROM city_wide_places")
                cur.executemany(
                    "INSERT INTO city_wide_places (osm_id, name, category, subtype, lat, lon, address, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                    [(p.get("osm_id"), p.get("name"), p.get("category"), p.get("subtype"), p.get("lat"), p.get("lon"), p.get("address", "")) for p in places]
                )
            self.conn.commit()
            self.log_action("replace_city_osm_data", "city", "javanrood", {"streets": len(streets) if replace_streets else None, "places": len(places) if replace_places else None})
        except Exception:
            self.conn.rollback()
            raise

    def clear_city_wide_streets(self):
        self.conn.execute("DELETE FROM city_wide_streets")
        self.conn.commit()

    def save_city_wide_streets_bulk(self, streets):
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT OR REPLACE INTO city_wide_streets (osm_id, segment_index, name, is_unnamed, highway_type, geometry, geometry_hash, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            [(s.get("osm_id"), s.get("segment_index", 0), s.get("name"), int(bool(s.get("is_unnamed", 0))), s.get("highway_type"), json.dumps(s.get("geometry", [])), geometry_hash(s.get("geometry", []))) for s in streets]
        )
        self.conn.commit()

    def get_city_wide_streets(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, osm_id, segment_index, name, is_unnamed, highway_type, geometry FROM city_wide_streets ORDER BY name ASC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0], "osm_id": r[1], "segment_index": r[2] or 0, "name": r[3] or "(بدون نام)",
                "is_unnamed": bool(r[4]), "highway_type": r[5], "geometry": json.loads(r[6]) if r[6] else []
            })
        return result

    def clear_city_wide_places(self):
        self.conn.execute("DELETE FROM city_wide_places")
        self.conn.commit()

    def save_city_wide_places_bulk(self, places):
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT INTO city_wide_places (osm_id, name, category, subtype, lat, lon, address) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(p["osm_id"], p["name"], p["category"], p["subtype"], p["lat"], p["lon"], p.get("address", "")) for p in places]
        )
        self.conn.commit()

    def get_city_wide_places(self, category=None):
        cur = self.conn.cursor()
        if category:
            cur.execute(
                "SELECT id, osm_id, name, category, subtype, lat, lon, address FROM city_wide_places "
                "WHERE category=? ORDER BY name ASC", (category,)
            )
        else:
            cur.execute(
                "SELECT id, osm_id, name, category, subtype, lat, lon, address FROM city_wide_places "
                "ORDER BY category ASC, name ASC"
            )
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0], "osm_id": r[1], "name": r[2] or "(بدون نام)",
                "category": r[3], "subtype": r[4], "lat": r[5], "lon": r[6], "address": r[7]
            })
        return result

    def update_city_wide_street(self, street_id, name=None, highway_type=None):
        cur = self.conn.cursor()
        if name is not None:
            cur.execute("UPDATE city_wide_streets SET name=? WHERE id=?", (name, street_id))
        if highway_type is not None:
            cur.execute("UPDATE city_wide_streets SET highway_type=? WHERE id=?", (highway_type, street_id))
        self.conn.commit()

    def delete_city_wide_street(self, street_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM city_wide_streets WHERE id=?", (street_id,))
        self.conn.commit()

    def update_city_wide_place(self, place_id, name=None, category=None, subtype=None, address=None):
        cur = self.conn.cursor()
        if name is not None:
            cur.execute("UPDATE city_wide_places SET name=? WHERE id=?", (name, place_id))
        if category is not None:
            cur.execute("UPDATE city_wide_places SET category=? WHERE id=?", (category, place_id))
        if subtype is not None:
            cur.execute("UPDATE city_wide_places SET subtype=? WHERE id=?", (subtype, place_id))
        if address is not None:
            cur.execute("UPDATE city_wide_places SET address=? WHERE id=?", (address, place_id))
        self.conn.commit()

    def delete_city_wide_place(self, place_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM city_wide_places WHERE id=?", (place_id,))
        self.conn.commit()

    def add_manual_city_wide_place(self, name, subtype, lat, lon, address=""):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO city_wide_places (osm_id, name, category, subtype, lat, lon, address) "
            "VALUES (NULL, ?, 'manual', ?, ?, ?, ?)",
            (name, subtype, lat, lon, address)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_city_wide_stats(self):
        return {
            "streets_count": self.conn.execute("SELECT COUNT(*) FROM city_wide_streets").fetchone()[0],
            "places_count": self.conn.execute("SELECT COUNT(*) FROM city_wide_places").fetchone()[0],
            "boundary_points": self.conn.execute("SELECT COUNT(*) FROM city_wide_boundary").fetchone()[0],
        }

    # ---------------- System Info / Stats (برای گزارش‌گیری و تنظیمات سیستم) ----------------
    def get_system_stats(self):
        """آمار کلی سیستم برای گزارش‌گیری و صفحه تنظیمات."""
        cur = self.conn.cursor()
        stats = {}
        stats["zones_count"] = cur.execute("SELECT COUNT(*) FROM zones").fetchone()[0]
        stats["streets_count"] = cur.execute("SELECT COUNT(*) FROM streets").fetchone()[0]
        stats["places_count"] = cur.execute("SELECT COUNT(*) FROM places").fetchone()[0]
        stats["mosques_count"] = cur.execute("SELECT COUNT(*) FROM mosques").fetchone()[0]
        stats["tiles_count"] = cur.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        stats["members_count"] = cur.execute("SELECT COUNT(*) FROM council_members").fetchone()[0]
        stats["county_steering_members_count"] = cur.execute("SELECT COUNT(*) FROM county_steering_members WHERE COALESCE(person_name,'')<>''").fetchone()[0]
        stats["committees_count"] = cur.execute("SELECT COUNT(*) FROM neighborhood_committees").fetchone()[0]
        stats["committee_members_count"] = cur.execute("SELECT COUNT(*) FROM committee_members WHERE status='فعال'").fetchone()[0]
        stats["pending_committee_resolutions"] = cur.execute("SELECT COUNT(*) FROM committee_resolutions WHERE status NOT IN ('انجام‌شده','لغوشده')").fetchone()[0]
        stats["social_councils_count"] = cur.execute("SELECT COUNT(*) FROM social_councils").fetchone()[0]
        stats["social_council_members_count"] = cur.execute("SELECT COUNT(*) FROM social_council_members WHERE status='فعال'").fetchone()[0]
        stats["open_social_issues_count"] = cur.execute("SELECT COUNT(*) FROM social_issues WHERE status NOT IN ('مختومه','انجام‌شده','لغوشده')").fetchone()[0]
        stats["pending_social_resolutions"] = cur.execute("SELECT COUNT(*) FROM social_resolutions WHERE status NOT IN ('انجام‌شده','لغوشده')").fetchone()[0]
        stats["requests_count"] = cur.execute("SELECT COUNT(*) FROM priority_requests").fetchone()[0]
        stats["open_requests_count"] = cur.execute(
            "SELECT COUNT(*) FROM priority_requests WHERE COALESCE(status, '') NOT IN ('تکمیل‌شده', 'مختومه', 'انجام‌شده')"
        ).fetchone()[0]
        stats["actions_count"] = cur.execute("SELECT COUNT(*) FROM request_actions").fetchone()[0]
        stats["meeting_places_count"] = cur.execute("SELECT COUNT(*) FROM zone_meeting_places").fetchone()[0]
        stats["zones_without_streets"] = cur.execute(
            "SELECT COUNT(*) FROM zones z WHERE NOT EXISTS (SELECT 1 FROM streets s WHERE s.zone_id=z.id)"
        ).fetchone()[0]
        stats["zones_without_meeting_place"] = cur.execute(
            "SELECT COUNT(*) FROM zones z WHERE NOT EXISTS (SELECT 1 FROM zone_meeting_places m WHERE m.zone_id=z.id)"
        ).fetchone()[0]
        stats["approved_households"] = cur.execute("SELECT COALESCE(SUM(approved_households),0) FROM zone_profiles").fetchone()[0]
        stats["estimated_population"] = cur.execute("SELECT COALESCE(SUM(estimated_population),0) FROM zone_profiles").fetchone()[0]
        stats["neighborhood_issues_count"] = cur.execute("SELECT COUNT(*) FROM neighborhood_issues").fetchone()[0]
        stats["critical_issues_count"] = cur.execute("SELECT COUNT(*) FROM neighborhood_issues WHERE priority_level IN ('بحرانی','فوری') AND status NOT IN ('مختومه','انجام‌شده')").fetchone()[0]
        stats["active_neighborhood_actions"] = cur.execute("SELECT COUNT(*) FROM neighborhood_actions WHERE status='در حال اجرا'").fetchone()[0]
        stats["pending_resolutions"] = cur.execute("SELECT COUNT(*) FROM neighborhood_resolutions WHERE status NOT IN ('انجام‌شده','لغوشده')").fetchone()[0]
        stats["agencies_count"] = cur.execute("SELECT COUNT(*) FROM management_agencies WHERE is_active=1").fetchone()[0]
        stats["budget_records_count"] = cur.execute("SELECT COUNT(*) FROM neighborhood_budgets").fetchone()[0]
        stats["budget_overruns_count"] = cur.execute(
            "SELECT COUNT(*) FROM neighborhood_budgets WHERE allocated_amount>0 AND spent_amount>allocated_amount"
        ).fetchone()[0]
        stats["management_alerts_count"] = len(self.get_management_alerts())
        stats["field_visits_count"] = cur.execute("SELECT COUNT(*) FROM field_visits").fetchone()[0]
        stats["citizen_requests_count"] = cur.execute("SELECT COUNT(*) FROM citizen_requests").fetchone()[0]
        stats["open_citizen_requests"] = cur.execute(
            "SELECT COUNT(*) FROM citizen_requests WHERE status NOT IN ('پاسخ‌داده‌شده','مختومه','ردشده')"
        ).fetchone()[0]
        stats["pending_sync_count"] = cur.execute(
            "SELECT COUNT(*) FROM offline_sync_queue WHERE status='در انتظار انتقال'"
        ).fetchone()[0]
        stats["active_users_count"] = cur.execute(
            "SELECT COUNT(*) FROM app_users WHERE is_active=1"
        ).fetchone()[0]
        stats["healthy_backups_count"] = cur.execute(
            "SELECT COUNT(*) FROM backup_registry WHERE validation_status='سالم'"
        ).fetchone()[0]
        correspondence = self.get_correspondence_stats()
        stats.update(correspondence)
        stats.update(self.get_approval_stats())
        stats["document_templates_count"] = cur.execute(
            "SELECT COUNT(*) FROM document_templates WHERE is_active=1"
        ).fetchone()[0]
        stats["generated_documents_count"] = cur.execute(
            "SELECT COUNT(*) FROM generated_documents"
        ).fetchone()[0]
        try:
            self.refresh_in_app_notifications(days_ahead=7)
        except Exception:
            pass
        current_user_id = (self.current_user or {}).get("id")
        stats["calendar_events_count"] = cur.execute(
            "SELECT COUNT(*) FROM management_calendar_events WHERE status NOT IN ('انجام‌شده','لغوشده')"
        ).fetchone()[0]
        if current_user_id is None:
            stats["unread_notifications_count"] = cur.execute(
                "SELECT COUNT(*) FROM in_app_notifications WHERE is_read=0 AND is_dismissed=0"
            ).fetchone()[0]
        else:
            stats["unread_notifications_count"] = cur.execute(
                """SELECT COUNT(*) FROM in_app_notifications
                   WHERE is_read=0 AND is_dismissed=0 AND (user_id IS NULL OR user_id=?)""",
                (int(current_user_id),),
            ).fetchone()[0]
        today = datetime.now().strftime("%Y-%m-%d")
        stats["overdue_deadlines_count"] = cur.execute(
            """SELECT COUNT(*) FROM in_app_notifications
               WHERE is_dismissed=0 AND due_date<? AND severity='بحرانی'""", (today,)
        ).fetchone()[0]
        project_summary = self.get_project_control_summary()
        stats["annual_programs_count"] = project_summary["programs_count"]
        stats["portfolio_projects_count"] = project_summary["projects_count"]
        stats["active_portfolio_projects"] = project_summary["active_projects"]
        stats["overdue_portfolio_projects"] = project_summary["overdue_projects"]
        stats["high_project_risks"] = project_summary["high_risks"]
        stats["pending_project_changes"] = project_summary["pending_changes"]
        contract_summary = self.get_contract_management_summary()
        stats["contractors_count"] = contract_summary["contractors_count"]
        stats["contracts_count"] = contract_summary["contracts_count"]
        stats["active_contracts"] = contract_summary["active_contracts"]
        stats["contract_alerts_count"] = contract_summary["alerts_count"]
        stats["average_satisfaction"] = contract_summary["average_satisfaction"]
        stats["community_participations_count"] = contract_summary["participations_count"]
        stats["sync_conflicts_pending"] = cur.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE status='در انتظار تصمیم'"
        ).fetchone()[0]
        stats["governance_records_count"] = cur.execute(
            "SELECT COUNT(*) FROM record_governance"
        ).fetchone()[0]
        stats["public_records_count"] = cur.execute(
            "SELECT COUNT(*) FROM record_governance WHERE is_public=1 AND lifecycle_status='تأییدشده'"
        ).fetchone()[0]
        stats["publications_count"] = cur.execute(
            "SELECT COUNT(*) FROM public_portal_publications WHERE status='منتشرشده'"
        ).fetchone()[0]
        stats["retention_alerts_count"] = len(self.get_retention_alerts(30))
        try:
            execution = self.get_execution_dashboard_stats()
            stats["execution_cases_count"] = execution["total"]
            stats["open_execution_cases"] = execution["open"]
            stats["overdue_execution_cases"] = execution["overdue"]
            stats["open_execution_assignments"] = execution["open_assignments"]
        except Exception:
            stats["execution_cases_count"] = stats["open_execution_cases"] = 0
            stats["overdue_execution_cases"] = stats["open_execution_assignments"] = 0
        return stats

    def reset_all_data(self):
        """
        پاک کردن کامل تمام داده‌های عملیاتی (محدوده، مناطق، خیابان‌ها، اماکن، تایل‌ها،
        اعضای شورا، درخواست‌ها، اقدامات، محل جلسات).
        حساب‌های کاربری، تاریخچه بکاپ و هدر سفارشی دست‌نخورده باقی می‌مانند.
        """
        cur = self.conn.cursor()
        tables_to_clear = [
            "public_portal_publications", "sync_conflicts", "record_governance",
            "community_participations", "satisfaction_surveys", "contractor_evaluations",
            "contract_payments", "project_contracts", "contractors",
            "project_change_requests", "project_risks", "project_indicators",
            "project_progress_updates", "project_milestones", "project_portfolio",
            "annual_operational_programs",
            "in_app_notifications", "management_calendar_events",
            "approval_steps", "approval_requests", "generated_documents",
            "administrative_notification_acknowledgements", "workflow_assignments",
            "document_attachments", "correspondence_letters",
            "offline_sync_queue", "citizen_requests", "field_visits",
            "management_alert_acknowledgements", "neighborhood_budgets", "management_agencies",
            "neighborhood_resolutions", "neighborhood_meetings", "neighborhood_actions",
            "neighborhood_issues", "zone_profiles",
            "request_actions", "priority_requests", "zone_meeting_places",
            "council_members", "zone_mosques", "places", "streets", "zones", "boundary",
            "city_wide_places", "city_wide_streets", "city_wide_boundary", "tiles", "audit_logs"
        ]
        for table in tables_to_clear:
            cur.execute(f"DELETE FROM {table}")
        self.conn.commit()
        # فشرده‌سازی فایل دیتابیس پس از حذف حجم زیاد داده (مخصوصاً تایل‌ها)
        cur.execute("VACUUM")
        self.conn.commit()

    # ---------------- Neighborhood Management v6 ----------------
    ISSUE_CATEGORIES = [
        "عمرانی", "خدمات شهری", "روشنایی", "آسفالت و معابر", "آب و فاضلاب",
        "پسماند", "فرهنگی", "اجتماعی", "آموزشی", "امنیتی", "بهداشت و درمان",
        "اشتغال", "فضای سبز", "آسیب‌های اجتماعی", "سایر"
    ]
    ISSUE_STATUSES = ["ثبت اولیه", "در حال بررسی", "تأییدشده", "ارجاع‌شده", "در حال اجرا", "مختومه"]
    ACTION_STATUSES = ["برنامه‌ریزی‌شده", "در حال اجرا", "متوقف‌شده", "تکمیل‌شده", "ارزیابی نتیجه"]
    RESOLUTION_STATUSES = ["در انتظار اقدام", "ارجاع‌شده", "در حال پیگیری", "انجام‌شده", "لغوشده"]

    @staticmethod
    def calculate_issue_priority(urgency, severity, affected_households=0, safety_risk=1):
        """امتیاز شفاف و قابل بازتولید برای اولویت مسئله (۰ تا ۱۰۰)."""
        urgency = max(1, min(5, int(urgency or 1)))
        severity = max(1, min(5, int(severity or 1)))
        safety_risk = max(1, min(5, int(safety_risk or 1)))
        affected = max(0, int(affected_households or 0))
        affected_score = min(25.0, affected / 4.0)
        score = urgency * 6 + severity * 6 + safety_risk * 3 + affected_score
        score = round(min(100.0, score), 1)
        if score >= 80:
            level = "بحرانی"
        elif score >= 65:
            level = "فوری"
        elif score >= 45:
            level = "مهم"
        elif score >= 25:
            level = "عادی"
        else:
            level = "کم‌اولویت"
        return score, level

    def save_zone_profile(self, zone_id, **data):
        allowed = [
            "residential_buildings", "residential_units", "occupied_units", "vacant_units",
            "estimated_households", "field_households", "approved_households", "estimated_population",
            "average_household_size", "elderly_count", "children_count", "disabled_count",
            "vulnerable_households", "female_headed_households", "estimation_method",
            "confidence_level", "notes"
        ]
        values = {key: data.get(key) for key in allowed}
        for key in allowed[:14]:
            if key == "average_household_size":
                values[key] = max(0.0, float(values[key] or 0))
            else:
                values[key] = max(0, int(values[key] or 0))
        columns = ", ".join(["zone_id"] + allowed)
        placeholders = ", ".join(["?"] * (len(allowed) + 1))
        updates = ", ".join(f"{c}=excluded.{c}" for c in allowed)
        self.conn.execute(
            f"INSERT INTO zone_profiles ({columns}, updated_at) VALUES ({placeholders}, CURRENT_TIMESTAMP) "
            f"ON CONFLICT(zone_id) DO UPDATE SET {updates}, updated_at=CURRENT_TIMESTAMP",
            [zone_id] + [values[c] for c in allowed],
        )
        self.conn.commit()
        self.log_action("zone_profile_saved", "zone", zone_id, {"approved_households": values["approved_households"]})
        return self.get_zone_profile(zone_id)

    def get_zone_profile(self, zone_id):
        row = self.conn.execute(
            """SELECT zone_id, residential_buildings, residential_units, occupied_units, vacant_units,
                      estimated_households, field_households, approved_households, estimated_population,
                      average_household_size, elderly_count, children_count, disabled_count,
                      vulnerable_households, female_headed_households, estimation_method,
                      confidence_level, notes, updated_at
               FROM zone_profiles WHERE zone_id=?""", (zone_id,)
        ).fetchone()
        keys = ["zone_id", "residential_buildings", "residential_units", "occupied_units", "vacant_units",
                "estimated_households", "field_households", "approved_households", "estimated_population",
                "average_household_size", "elderly_count", "children_count", "disabled_count",
                "vulnerable_households", "female_headed_households", "estimation_method",
                "confidence_level", "notes", "updated_at"]
        if row:
            return dict(zip(keys, row))
        return {
            "zone_id": zone_id, "residential_buildings": 0, "residential_units": 0,
            "occupied_units": 0, "vacant_units": 0, "estimated_households": 0,
            "field_households": 0, "approved_households": 0, "estimated_population": 0,
            "average_household_size": 3.3, "elderly_count": 0, "children_count": 0,
            "disabled_count": 0, "vulnerable_households": 0, "female_headed_households": 0,
            "estimation_method": "", "confidence_level": "متوسط", "notes": "", "updated_at": None,
        }

    def add_neighborhood_issue(self, zone_id, title, category="سایر", description="", related_office="",
                               urgency=3, severity=3, affected_households=0, safety_risk=1,
                               status="ثبت اولیه", source="ثبت سامانه", location_text="", lat=None, lon=None,
                               due_date=None):
        score, level = self.calculate_issue_priority(urgency, severity, affected_households, safety_risk)
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO neighborhood_issues
               (zone_id, title, category, description, related_office, urgency, severity,
                affected_households, safety_risk, priority_score, priority_level, status,
                source, location_text, lat, lon, due_date, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (zone_id, title, category, description, related_office, urgency, severity,
             affected_households, safety_risk, score, level, status, source, location_text, lat, lon, due_date)
        )
        self.conn.commit()
        issue_id = cur.lastrowid
        self.log_action("neighborhood_issue_added", "issue", issue_id, {"zone_id": zone_id, "priority": level})
        return issue_id

    def update_neighborhood_issue(self, issue_id, **data):
        current = self.get_neighborhood_issue(issue_id)
        if not current:
            return False
        editable = ["title", "category", "description", "related_office", "urgency", "severity",
                    "affected_households", "safety_risk", "status", "source", "location_text",
                    "lat", "lon", "due_date"]
        merged = {k: data.get(k, current.get(k)) for k in editable}
        score, level = self.calculate_issue_priority(
            merged["urgency"], merged["severity"], merged["affected_households"], merged["safety_risk"]
        )
        sets = ", ".join(f"{k}=?" for k in editable)
        self.conn.execute(
            f"UPDATE neighborhood_issues SET {sets}, priority_score=?, priority_level=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [merged[k] for k in editable] + [score, level, issue_id]
        )
        self.conn.commit()
        self.log_action("neighborhood_issue_updated", "issue", issue_id, {"priority": level})
        return True

    def delete_neighborhood_issue(self, issue_id):
        row = self.conn.execute("SELECT legacy_request_id FROM neighborhood_issues WHERE id=?", (issue_id,)).fetchone()
        legacy_request_id = row[0] if row else None
        self.conn.execute("DELETE FROM neighborhood_issues WHERE id=?", (issue_id,))
        if legacy_request_id is not None:
            self.conn.execute("DELETE FROM request_actions WHERE request_id=?", (legacy_request_id,))
            self.conn.execute("DELETE FROM priority_requests WHERE id=?", (legacy_request_id,))
        self.conn.commit()
        self.log_action("neighborhood_issue_deleted", "issue", issue_id, {"legacy_request_id": legacy_request_id})

    def get_neighborhood_issue(self, issue_id):
        rows = self.get_neighborhood_issues()
        return next((x for x in rows if x["id"] == issue_id), None)

    def get_neighborhood_issues(self, zone_id=None):
        sql = """SELECT id, zone_id, legacy_request_id, title, category, description, related_office,
                        urgency, severity, affected_households, safety_risk, priority_score,
                        priority_level, status, source, location_text, lat, lon, due_date,
                        created_at, updated_at
                 FROM neighborhood_issues"""
        params = []
        if zone_id is not None:
            sql += " WHERE zone_id=?"
            params.append(zone_id)
        sql += " ORDER BY priority_score DESC, id DESC"
        keys = ["id", "zone_id", "legacy_request_id", "title", "category", "description", "related_office",
                "urgency", "severity", "affected_households", "safety_risk", "priority_score",
                "priority_level", "status", "source", "location_text", "lat", "lon", "due_date",
                "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def add_neighborhood_action(self, zone_id, title, issue_id=None, description="", responsible_person="",
                                responsible_office="", partner_office="", planned_start=None, planned_end=None,
                                progress_percent=0, estimated_cost=0, actual_cost=0, funding_source="",
                                contractor="", status="برنامه‌ریزی‌شده", obstacles="", result_summary=""):
        progress_percent = max(0, min(100, int(progress_percent or 0)))
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO neighborhood_actions
               (zone_id, issue_id, title, description, responsible_person, responsible_office,
                partner_office, planned_start, planned_end, progress_percent, estimated_cost,
                actual_cost, funding_source, contractor, status, obstacles, result_summary, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (zone_id, issue_id, title, description, responsible_person, responsible_office,
             partner_office, planned_start, planned_end, progress_percent, float(estimated_cost or 0),
             float(actual_cost or 0), funding_source, contractor, status, obstacles, result_summary)
        )
        self.conn.commit()
        action_id = cur.lastrowid
        if issue_id:
            self.conn.execute("UPDATE neighborhood_issues SET status='در حال اجرا', updated_at=CURRENT_TIMESTAMP WHERE id=?", (issue_id,))
            self.conn.commit()
        self.log_action("neighborhood_action_added", "action", action_id, {"zone_id": zone_id, "issue_id": issue_id})
        return action_id

    def update_neighborhood_action(self, action_id, **data):
        current = self.get_neighborhood_action(action_id)
        if not current:
            return False
        editable = ["issue_id", "title", "description", "responsible_person", "responsible_office",
                    "partner_office", "planned_start", "planned_end", "progress_percent",
                    "estimated_cost", "actual_cost", "funding_source", "contractor", "status",
                    "obstacles", "result_summary"]
        merged = {k: data.get(k, current.get(k)) for k in editable}
        merged["progress_percent"] = max(0, min(100, int(merged["progress_percent"] or 0)))
        sets = ", ".join(f"{k}=?" for k in editable)
        self.conn.execute(
            f"UPDATE neighborhood_actions SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [merged[k] for k in editable] + [action_id]
        )
        if merged["status"] == "تکمیل‌شده" and merged.get("issue_id"):
            self.conn.execute("UPDATE neighborhood_issues SET status='مختومه', updated_at=CURRENT_TIMESTAMP WHERE id=?", (merged["issue_id"],))
        self.conn.commit()
        self.log_action("neighborhood_action_updated", "action", action_id, {"progress": merged["progress_percent"]})
        return True

    def delete_neighborhood_action(self, action_id):
        self.conn.execute("DELETE FROM neighborhood_actions WHERE id=?", (action_id,))
        self.conn.commit()
        self.log_action("neighborhood_action_deleted", "action", action_id)

    def get_neighborhood_action(self, action_id):
        return next((x for x in self.get_neighborhood_actions() if x["id"] == action_id), None)

    def get_neighborhood_actions(self, zone_id=None):
        sql = """SELECT a.id, a.zone_id, a.issue_id, a.title, a.description, a.responsible_person,
                        a.responsible_office, a.partner_office, a.planned_start, a.planned_end,
                        a.progress_percent, a.estimated_cost, a.actual_cost, a.funding_source,
                        a.contractor, a.status, a.obstacles, a.result_summary, a.created_at,
                        a.updated_at, a.approval_status, a.approved_at, a.approved_by, i.title
                 FROM neighborhood_actions a
                 LEFT JOIN neighborhood_issues i ON i.id=a.issue_id"""
        params = []
        if zone_id is not None:
            sql += " WHERE a.zone_id=?"
            params.append(zone_id)
        sql += " ORDER BY CASE a.status WHEN 'در حال اجرا' THEN 0 WHEN 'برنامه‌ریزی‌شده' THEN 1 ELSE 2 END, a.id DESC"
        keys = ["id", "zone_id", "issue_id", "title", "description", "responsible_person",
                "responsible_office", "partner_office", "planned_start", "planned_end",
                "progress_percent", "estimated_cost", "actual_cost", "funding_source",
                "contractor", "status", "obstacles", "result_summary", "created_at",
                "updated_at", "approval_status", "approved_at", "approved_by", "issue_title"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def add_neighborhood_meeting(self, zone_id, title, meeting_date=None, start_time=None, place_name="",
                                 agenda="", attendees="", absentees="", minutes_text="", status="برگزارشده"):
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO neighborhood_meetings
               (zone_id, title, meeting_date, start_time, place_name, agenda, attendees,
                absentees, minutes_text, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (zone_id, title, meeting_date, start_time, place_name, agenda, attendees, absentees, minutes_text, status)
        )
        self.conn.commit()
        meeting_id = cur.lastrowid
        self.log_action("neighborhood_meeting_added", "meeting", meeting_id, {"zone_id": zone_id})
        return meeting_id

    def update_neighborhood_meeting(self, meeting_id, **data):
        current = self.get_neighborhood_meeting(meeting_id)
        if not current:
            return False
        editable = ["title", "meeting_date", "start_time", "place_name", "agenda", "attendees",
                    "absentees", "minutes_text", "status"]
        merged = {k: data.get(k, current.get(k)) for k in editable}
        sets = ", ".join(f"{k}=?" for k in editable)
        self.conn.execute(f"UPDATE neighborhood_meetings SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [merged[k] for k in editable] + [meeting_id])
        self.conn.commit()
        self.log_action("neighborhood_meeting_updated", "meeting", meeting_id)
        return True

    def delete_neighborhood_meeting(self, meeting_id):
        self.conn.execute("DELETE FROM neighborhood_meetings WHERE id=?", (meeting_id,))
        self.conn.commit()
        self.log_action("neighborhood_meeting_deleted", "meeting", meeting_id)

    def get_neighborhood_meeting(self, meeting_id):
        return next((x for x in self.get_neighborhood_meetings() if x["id"] == meeting_id), None)

    def get_neighborhood_meetings(self, zone_id=None):
        sql = """SELECT id, zone_id, title, meeting_date, start_time, place_name, agenda,
                        attendees, absentees, minutes_text, status, created_at, updated_at
                 FROM neighborhood_meetings"""
        params = []
        if zone_id is not None:
            sql += " WHERE zone_id=?"
            params.append(zone_id)
        sql += " ORDER BY COALESCE(meeting_date, created_at) DESC, id DESC"
        keys = ["id", "zone_id", "title", "meeting_date", "start_time", "place_name", "agenda",
                "attendees", "absentees", "minutes_text", "status", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def add_neighborhood_resolution(self, meeting_id, zone_id, title, description="",
                                    responsible_office="", responsible_person="", due_date=None,
                                    status="در انتظار اقدام", linked_issue_id=None, linked_action_id=None):
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO neighborhood_resolutions
               (meeting_id, zone_id, title, description, responsible_office, responsible_person,
                due_date, status, linked_issue_id, linked_action_id, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (meeting_id, zone_id, title, description, responsible_office, responsible_person,
             due_date, status, linked_issue_id, linked_action_id)
        )
        self.conn.commit()
        resolution_id = cur.lastrowid
        self.log_action("neighborhood_resolution_added", "resolution", resolution_id, {"meeting_id": meeting_id})
        return resolution_id

    def update_neighborhood_resolution(self, resolution_id, **data):
        current = self.get_neighborhood_resolution(resolution_id)
        if not current:
            return False
        editable = ["title", "description", "responsible_office", "responsible_person", "due_date",
                    "status", "linked_issue_id", "linked_action_id"]
        merged = {k: data.get(k, current.get(k)) for k in editable}
        sets = ", ".join(f"{k}=?" for k in editable)
        self.conn.execute(f"UPDATE neighborhood_resolutions SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [merged[k] for k in editable] + [resolution_id])
        self.conn.commit()
        self.log_action("neighborhood_resolution_updated", "resolution", resolution_id)
        return True

    def delete_neighborhood_resolution(self, resolution_id):
        self.conn.execute("DELETE FROM neighborhood_resolutions WHERE id=?", (resolution_id,))
        self.conn.commit()
        self.log_action("neighborhood_resolution_deleted", "resolution", resolution_id)

    def get_neighborhood_resolution(self, resolution_id):
        return next((x for x in self.get_neighborhood_resolutions() if x["id"] == resolution_id), None)

    def get_neighborhood_resolutions(self, zone_id=None, meeting_id=None):
        sql = """SELECT r.id, r.meeting_id, r.zone_id, r.title, r.description, r.responsible_office,
                        r.responsible_person, r.due_date, r.status, r.linked_issue_id,
                        r.linked_action_id, r.created_at, r.updated_at,
                        r.approval_status, r.approved_at, r.approved_by, m.title
                 FROM neighborhood_resolutions r
                 JOIN neighborhood_meetings m ON m.id=r.meeting_id"""
        clauses, params = [], []
        if zone_id is not None:
            clauses.append("r.zone_id=?")
            params.append(zone_id)
        if meeting_id is not None:
            clauses.append("r.meeting_id=?")
            params.append(meeting_id)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE r.status WHEN 'در انتظار اقدام' THEN 0 WHEN 'در حال پیگیری' THEN 1 ELSE 2 END, r.id DESC"
        keys = ["id", "meeting_id", "zone_id", "title", "description", "responsible_office",
                "responsible_person", "due_date", "status", "linked_issue_id", "linked_action_id",
                "created_at", "updated_at", "approval_status", "approved_at", "approved_by", "meeting_title"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def get_neighborhood_summary(self, zone_id):
        profile = self.get_zone_profile(zone_id)
        issues = self.get_neighborhood_issues(zone_id)
        actions = self.get_neighborhood_actions(zone_id)
        meetings = self.get_neighborhood_meetings(zone_id)
        resolutions = self.get_neighborhood_resolutions(zone_id=zone_id)
        field_visits = self.get_field_visits(zone_id)
        citizen_requests = self.get_citizen_requests(zone_id)
        return {
            "profile": profile,
            "issues_total": len(issues),
            "issues_open": sum(1 for x in issues if x["status"] not in ("مختومه", "انجام‌شده")),
            "issues_critical": sum(1 for x in issues if x["priority_level"] in ("بحرانی", "فوری")),
            "actions_total": len(actions),
            "actions_active": sum(1 for x in actions if x["status"] == "در حال اجرا"),
            "actions_completed": sum(1 for x in actions if x["status"] == "تکمیل‌شده"),
            "meetings_total": len(meetings),
            "resolutions_pending": sum(1 for x in resolutions if x["status"] not in ("انجام‌شده", "لغوشده")),
            "field_visits_total": len(field_visits),
            "field_followups": sum(1 for x in field_visits if x.get("followup_required") and x.get("status") != "تکمیل‌شده"),
            "citizen_requests_total": len(citizen_requests),
            "citizen_requests_open": sum(1 for x in citizen_requests if x.get("status") not in ("پاسخ‌داده‌شده", "مختومه", "ردشده")),
        }

    # وزن‌های امتیاز ریسک بلوک؛ عمداً در یک محل ثابت نگه داشته شده تا در صورت
    # تغییر سیاست اولویت‌بندی شهر، فقط همین‌جا اصلاح شود، نه در چند فایل جدا.
    ZONE_RISK_WEIGHTS = {
        "issues_critical": 10,
        "issues_open": 3,
        "citizen_requests_open": 2,
        "overdue_execution_cases": 6,
        "field_followups": 2,
    }

    def get_all_zones_comparison(self):
        """خلاصه وضعیت و امتیاز ریسک برای تمام بلوک‌های شهر، برای مقایسه و
        رتبه‌بندی. امتیاز ریسک صرفاً بر اساس شمارش‌های شفاف و از پیش موجود
        محاسبه می‌شود (همان اعداد get_neighborhood_summary)، نه یک مدل
        پیچیده یا مبهم — تا نتیجه برای کارشناس بلوک قابل توضیح و اعتماد باشد.

        نکته طراحی عمدی: issues_critical زیرمجموعه issues_open است (یک
        مسئله بحرانی هم «باز» است هم «بحرانی»)، پس در جمع امتیاز هر دو وزن
        را می‌گیرد. این تکرار حساب نیست، بلکه یک انتخاب آگاهانه است تا
        بودن‌بحرانی صرفاً به بودن‌باز جایگزین نشود، بلکه رویش اضافه شود.
        """
        zones = self.get_zones()
        results = []
        for zone in zones:
            zone_id = zone["id"]
            summary = self.get_neighborhood_summary(zone_id)
            execution_stats = self.get_execution_dashboard_stats(zone_id)
            overdue_cases = execution_stats.get("overdue", 0)

            risk_score = (
                summary["issues_critical"] * self.ZONE_RISK_WEIGHTS["issues_critical"]
                + summary["issues_open"] * self.ZONE_RISK_WEIGHTS["issues_open"]
                + summary["citizen_requests_open"] * self.ZONE_RISK_WEIGHTS["citizen_requests_open"]
                + overdue_cases * self.ZONE_RISK_WEIGHTS["overdue_execution_cases"]
                + summary["field_followups"] * self.ZONE_RISK_WEIGHTS["field_followups"]
            )
            results.append({
                "zone_id": zone_id,
                "zone_name": zone["name"],
                "risk_score": risk_score,
                "issues_critical": summary["issues_critical"],
                "issues_open": summary["issues_open"],
                "citizen_requests_open": summary["citizen_requests_open"],
                "overdue_execution_cases": overdue_cases,
                "actions_active": summary["actions_active"],
                "estimated_population": (summary.get("profile") or {}).get("estimated_population") or 0,
            })
        results.sort(key=lambda x: x["risk_score"], reverse=True)
        return results

    def get_zone_action_plan_context(self, zone_id):
        """جمع‌آوری تمام داده‌های لازم برای تولید یک برنامه عملیاتی برای یک
        بلوک: مشکلات و درخواست‌های باز، اقدامات در جریان (تا پیشنهاد تکراری
        داده نشود)، دستگاه‌های اجرایی فعال، و جمعیت‌شناسی بلوک. خروجی این
        تابع مستقیماً به زون_اکشن_پلن.py (تولید برنامه) داده می‌شود."""
        zone = self.get_zone(zone_id)
        if not zone:
            return None
        profile = self.get_zone_profile(zone_id)
        issues = self.get_neighborhood_issues(zone_id)
        open_issues = [x for x in issues if x["status"] not in ("مختومه", "انجام‌شده")]
        requests = self.get_citizen_requests(zone_id)
        open_requests = [x for x in requests if x.get("status") not in ("پاسخ‌داده‌شده", "مختومه", "ردشده")]
        actions = self.get_neighborhood_actions(zone_id)
        active_actions = [x for x in actions if x["status"] in ("برنامه‌ریزی‌شده", "در حال اجرا")]
        agencies = self.get_management_agencies(active_only=True)
        council_members = self.get_council_members(zone_id=zone_id)

        return {
            "zone": {"id": zone_id, "name": zone["name"]},
            "profile": profile,
            "open_issues": open_issues,
            "open_requests": open_requests,
            "active_actions": active_actions,
            "agencies": agencies,
            "council_members": council_members,
        }

    def save_zone_action_plan(self, zone_id, engine, content, context_snapshot=None, created_by=None):
        cur = self.conn.execute(
            """INSERT INTO zone_action_plans (zone_id, engine, content, context_snapshot, created_by)
               VALUES (?, ?, ?, ?, ?)""",
            (zone_id, engine, content, context_snapshot, created_by)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_zone_action_plans(self, zone_id):
        rows = self.conn.execute(
            """SELECT id, zone_id, engine, content, created_by, created_at
               FROM zone_action_plans WHERE zone_id=? ORDER BY id DESC""",
            (zone_id,)
        ).fetchall()
        keys = ["id", "zone_id", "engine", "content", "created_by", "created_at"]
        return [dict(zip(keys, row)) for row in rows]

    def get_latest_zone_action_plan(self, zone_id):
        plans = self.get_zone_action_plans(zone_id)
        return plans[0] if plans else None

    # ---------------- مدیریت بودجه، دستگاه‌ها، هشدار و کیفیت ----------------
    BUDGET_STATUSES = ["پیشنهادی", "مصوب", "تخصیص‌یافته", "در حال هزینه", "تسویه‌شده", "متوقف"]

    def add_management_agency(self, name, category="دستگاه اجرایی", contact_person="", phone="",
                              email="", address="", service_scope="", is_active=1, notes=""):
        name = (name or "").strip()
        if not name:
            raise ValueError("نام دستگاه الزامی است")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO management_agencies
               (name, category, contact_person, phone, email, address, service_scope, is_active, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (name, category, contact_person, phone, email, address, service_scope, int(bool(is_active)), notes)
        )
        self.conn.commit()
        agency_id = cur.lastrowid
        self.log_action("management_agency_added", "agency", agency_id, {"name": name})
        return agency_id

    def update_management_agency(self, agency_id, **data):
        current = self.get_management_agency(agency_id)
        if not current:
            return False
        fields = ["name", "category", "contact_person", "phone", "email", "address",
                  "service_scope", "is_active", "notes"]
        values = {key: data.get(key, current.get(key)) for key in fields}
        values["name"] = (values["name"] or "").strip()
        if not values["name"]:
            raise ValueError("نام دستگاه الزامی است")
        values["is_active"] = int(bool(values["is_active"]))
        sets = ", ".join(f"{key}=?" for key in fields)
        self.conn.execute(
            f"UPDATE management_agencies SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [values[key] for key in fields] + [agency_id]
        )
        self.conn.commit()
        self.log_action("management_agency_updated", "agency", agency_id, {"name": values["name"]})
        return True

    def delete_management_agency(self, agency_id):
        self.conn.execute("DELETE FROM management_agencies WHERE id=?", (agency_id,))
        self.conn.commit()
        self.log_action("management_agency_deleted", "agency", agency_id)

    def get_management_agency(self, agency_id):
        return next((x for x in self.get_management_agencies(active_only=False) if x["id"] == agency_id), None)

    def get_management_agencies(self, active_only=True):
        sql = """SELECT id, name, category, contact_person, phone, email, address, service_scope,
                        is_active, notes, created_at, updated_at
                 FROM management_agencies"""
        params = []
        if active_only:
            sql += " WHERE is_active=1"
        sql += " ORDER BY name"
        keys = ["id", "name", "category", "contact_person", "phone", "email", "address",
                "service_scope", "is_active", "notes", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def add_neighborhood_budget(self, zone_id, title, action_id=None, fiscal_year="", funding_source="",
                                approved_amount=0, allocated_amount=0, spent_amount=0,
                                status="پیشنهادی", document_reference="", notes=""):
        title = (title or "").strip()
        if not title:
            raise ValueError("عنوان ردیف بودجه الزامی است")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO neighborhood_budgets
               (zone_id, action_id, title, fiscal_year, funding_source, approved_amount,
                allocated_amount, spent_amount, status, document_reference, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (zone_id, action_id, title, fiscal_year, funding_source,
             max(0, float(approved_amount or 0)), max(0, float(allocated_amount or 0)),
             max(0, float(spent_amount or 0)), status, document_reference, notes)
        )
        self.conn.commit()
        budget_id = cur.lastrowid
        self.log_action("neighborhood_budget_added", "budget", budget_id, {"zone_id": zone_id})
        return budget_id

    def update_neighborhood_budget(self, budget_id, **data):
        current = self.get_neighborhood_budget(budget_id)
        if not current:
            return False
        fields = ["action_id", "title", "fiscal_year", "funding_source", "approved_amount",
                  "allocated_amount", "spent_amount", "status", "document_reference", "notes"]
        values = {key: data.get(key, current.get(key)) for key in fields}
        values["title"] = (values["title"] or "").strip()
        if not values["title"]:
            raise ValueError("عنوان ردیف بودجه الزامی است")
        for key in ("approved_amount", "allocated_amount", "spent_amount"):
            values[key] = max(0, float(values[key] or 0))
        sets = ", ".join(f"{key}=?" for key in fields)
        self.conn.execute(
            f"UPDATE neighborhood_budgets SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [values[key] for key in fields] + [budget_id]
        )
        self.conn.commit()
        self.log_action("neighborhood_budget_updated", "budget", budget_id)
        return True

    def delete_neighborhood_budget(self, budget_id):
        self.conn.execute("DELETE FROM neighborhood_budgets WHERE id=?", (budget_id,))
        self.conn.commit()
        self.log_action("neighborhood_budget_deleted", "budget", budget_id)

    def get_neighborhood_budget(self, budget_id):
        return next((x for x in self.get_neighborhood_budgets() if x["id"] == budget_id), None)

    def get_neighborhood_budgets(self, zone_id=None):
        sql = """SELECT b.id, b.zone_id, b.action_id, b.title, b.fiscal_year, b.funding_source,
                        b.approved_amount, b.allocated_amount, b.spent_amount, b.status,
                        b.document_reference, b.notes, b.created_at, b.updated_at,
                        b.approval_status, b.approved_at, b.approved_by, a.title
                 FROM neighborhood_budgets b
                 LEFT JOIN neighborhood_actions a ON a.id=b.action_id"""
        params = []
        if zone_id is not None:
            sql += " WHERE b.zone_id=?"
            params.append(zone_id)
        sql += " ORDER BY b.id DESC"
        keys = ["id", "zone_id", "action_id", "title", "fiscal_year", "funding_source",
                "approved_amount", "allocated_amount", "spent_amount", "status",
                "document_reference", "notes", "created_at", "updated_at",
                "approval_status", "approved_at", "approved_by", "action_title"]
        return [dict(zip(keys, row)) for row in self.conn.execute(sql, params).fetchall()]

    def get_budget_summary(self, zone_id=None):
        budgets = self.get_neighborhood_budgets(zone_id)
        approved = sum(float(x.get("approved_amount") or 0) for x in budgets)
        allocated = sum(float(x.get("allocated_amount") or 0) for x in budgets)
        spent = sum(float(x.get("spent_amount") or 0) for x in budgets)
        utilization = round((spent / allocated * 100), 1) if allocated else 0.0
        absorption = round((allocated / approved * 100), 1) if approved else 0.0
        return {
            "count": len(budgets), "approved": approved, "allocated": allocated,
            "spent": spent, "remaining": max(0.0, allocated - spent),
            "utilization_percent": utilization, "absorption_percent": absorption,
            "overrun_count": sum(1 for x in budgets if float(x.get("spent_amount") or 0) > float(x.get("allocated_amount") or 0) and float(x.get("allocated_amount") or 0) > 0),
        }

    @staticmethod
    def _is_overdue(date_text):
        if not date_text:
            return False
        try:
            return datetime.strptime(str(date_text)[:10], "%Y-%m-%d").date() < datetime.now().date()
        except (ValueError, TypeError):
            return False

    def get_management_alerts(self, zone_id=None, include_acknowledged=False):
        alerts = []
        zones = [self.get_zone(zone_id)] if zone_id is not None else self.get_zones()
        zones = [z for z in zones if z]
        acknowledged = {row[0] for row in self.conn.execute("SELECT alert_key FROM management_alert_acknowledgements").fetchall()}

        def add(key, severity, category, title, detail, zid, entity_type="", entity_id=None, due_date=None):
            if not include_acknowledged and key in acknowledged:
                return
            alerts.append({"key": key, "severity": severity, "category": category, "title": title,
                           "detail": detail, "zone_id": zid, "entity_type": entity_type,
                           "entity_id": entity_id, "due_date": due_date,
                           "acknowledged": key in acknowledged})

        for zone in zones:
            zid, zname = zone["id"], zone["name"]
            profile = self.get_zone_profile(zid)
            if not profile.get("approved_households"):
                add(f"zone:{zid}:households", "هشدار", "نقص اطلاعات", f"خانوار بلوک «{zname}» تأیید نشده است", "آمار خانوار نهایی ثبت نشده است.", zid, "zone", zid)
            if not self.get_zone_meeting_place(zid):
                add(f"zone:{zid}:meeting_place", "اطلاع", "نقص اطلاعات", f"محل جلسه بلوک «{zname}» ثبت نشده است", "برای جلسات شورای محله یک محل ثابت تعیین کنید.", zid, "zone", zid)
            for issue in self.get_neighborhood_issues(zid):
                if issue.get("status") in ("مختومه", "انجام‌شده"):
                    continue
                if issue.get("priority_level") in ("بحرانی", "فوری"):
                    add(f"issue:{issue['id']}:critical", "بحرانی", "مسئله", issue["title"], f"اولویت {issue['priority_level']} و وضعیت {issue['status']}", zid, "issue", issue["id"], issue.get("due_date"))
                if self._is_overdue(issue.get("due_date")):
                    add(f"issue:{issue['id']}:overdue", "بحرانی", "سررسید", f"مهلت مسئله گذشته است: {issue['title']}", f"تاریخ سررسید: {issue.get('due_date')}", zid, "issue", issue["id"], issue.get("due_date"))
                if not issue.get("related_office"):
                    add(f"issue:{issue['id']}:office", "هشدار", "ارجاع", f"مسئله بدون دستگاه مسئول: {issue['title']}", "دستگاه مسئول تعیین نشده است.", zid, "issue", issue["id"])
            for action in self.get_neighborhood_actions(zid):
                if action.get("status") in ("تکمیل‌شده", "لغوشده"):
                    continue
                if self._is_overdue(action.get("planned_end")):
                    add(f"action:{action['id']}:overdue", "بحرانی", "پروژه", f"اقدام تأخیرخورده: {action['title']}", f"پیشرفت {action.get('progress_percent') or 0}٪؛ پایان برنامه: {action.get('planned_end')}", zid, "action", action["id"], action.get("planned_end"))
                if not action.get("responsible_office") and not action.get("responsible_person"):
                    add(f"action:{action['id']}:owner", "هشدار", "مسئولیت", f"اقدام بدون مسئول: {action['title']}", "مسئول یا دستگاه مجری تعیین نشده است.", zid, "action", action["id"])
            for resolution in self.get_neighborhood_resolutions(zone_id=zid):
                if resolution.get("status") in ("انجام‌شده", "لغوشده"):
                    continue
                if self._is_overdue(resolution.get("due_date")):
                    add(f"resolution:{resolution['id']}:overdue", "بحرانی", "مصوبه", f"مصوبه معوق: {resolution['title']}", f"مهلت: {resolution.get('due_date')}", zid, "resolution", resolution["id"], resolution.get("due_date"))
            for request in self.get_citizen_requests(zid):
                if request.get("status") in ("پاسخ‌داده‌شده", "مختومه", "ردشده"):
                    continue
                if int(request.get("urgency") or 0) >= 4:
                    add(f"citizen:{request['id']}:urgent", "بحرانی", "درخواست مردمی",
                        f"درخواست فوری: {request['title']}",
                        f"کد رهگیری: {request.get('tracking_code')} — وضعیت: {request.get('status')}",
                        zid, "citizen_request", request["id"])
                if not request.get("assigned_office"):
                    add(f"citizen:{request['id']}:office", "هشدار", "ارجاع مردمی",
                        f"درخواست بدون دستگاه مسئول: {request['title']}",
                        f"کد رهگیری: {request.get('tracking_code')}", zid, "citizen_request", request["id"])
            for visit in self.get_field_visits(zid):
                if visit.get("followup_required") and visit.get("status") != "تکمیل‌شده":
                    add(f"visit:{visit['id']}:followup", "هشدار", "بازدید میدانی",
                        f"بازدید نیازمند پیگیری: {visit.get('visit_type') or 'بازدید'}",
                        f"تاریخ: {visit.get('visit_date') or '—'} — کارشناس: {visit.get('officer_name') or '—'}",
                        zid, "field_visit", visit["id"])
            for budget in self.get_neighborhood_budgets(zid):
                allocated = float(budget.get("allocated_amount") or 0)
                spent = float(budget.get("spent_amount") or 0)
                if allocated and spent > allocated:
                    add(f"budget:{budget['id']}:overrun", "بحرانی", "بودجه", f"اضافه‌هزینه: {budget['title']}", f"هزینه {spent:,.0f} ریال از تخصیص {allocated:,.0f} ریال بیشتر است.", zid, "budget", budget["id"])
            for approval in self.get_approval_requests(status="در انتظار تأیید", zone_id=zid):
                if self._is_overdue(approval.get("due_date")):
                    add(f"approval:{approval['id']}:overdue", "بحرانی", "تأیید اداری",
                        f"گردش تأیید معوق: {approval['title']}",
                        f"مرحله {approval.get('current_step')} از {approval.get('total_steps')} — مهلت: {approval.get('due_date')}",
                        zid, "approval", approval["id"], approval.get("due_date"))
                else:
                    add(f"approval:{approval['id']}:pending", "اطلاع", "تأیید اداری",
                        f"در انتظار تأیید: {approval['title']}",
                        f"مرحله {approval.get('current_step')} از {approval.get('total_steps')}",
                        zid, "approval", approval["id"], approval.get("due_date"))
        order = {"بحرانی": 0, "هشدار": 1, "اطلاع": 2}
        return sorted(alerts, key=lambda x: (order.get(x["severity"], 9), x.get("due_date") or "9999"))

    def acknowledge_management_alert(self, alert_key, user="مدیر سامانه", note=""):
        self.conn.execute(
            """INSERT INTO management_alert_acknowledgements(alert_key, acknowledged_at, acknowledged_by, note)
               VALUES (?, CURRENT_TIMESTAMP, ?, ?)
               ON CONFLICT(alert_key) DO UPDATE SET acknowledged_at=CURRENT_TIMESTAMP,
                   acknowledged_by=excluded.acknowledged_by, note=excluded.note""",
            (alert_key, user, note)
        )
        self.conn.commit()

    def restore_management_alert(self, alert_key):
        self.conn.execute("DELETE FROM management_alert_acknowledgements WHERE alert_key=?", (alert_key,))
        self.conn.commit()

    def get_quality_issues(self, zone_id=None):
        issues = []
        zones = [self.get_zone(zone_id)] if zone_id is not None else self.get_zones()
        for zone in [z for z in zones if z]:
            zid, name = zone["id"], zone["name"]
            checks = [
                (not self.get_streets(zid), "داده مکانی", "بلوک فاقد معبر ثبت‌شده است", "زیاد"),
                (not self.get_mosques(zone_id=zid), "اماکن", "هیچ مسجدی داخل بلوک تشخیص داده نشده است", "متوسط"),
                (not self.get_council_members(zid), "شورای محله", "عضو یا معتمد محله ثبت نشده است", "زیاد"),
                (not self.get_zone_meeting_place(zid), "جلسات", "محل جلسه بلوک ثبت نشده است", "متوسط"),
                (not self.get_zone_profile(zid).get("approved_households"), "جمعیت", "خانوار تأییدشده ثبت نشده است", "زیاد"),
                (not self.db_snapshot_ready(zid), "گزارش", "تصویر گرافیکی بلوک آماده نیست", "متوسط"),
                (not self.get_field_visits(zid), "عملیات میدانی", "هیچ بازدید میدانی برای بلوک ثبت نشده است", "متوسط"),
            ]
            for failed, category, message, severity in checks:
                if failed:
                    issues.append({"zone_id": zid, "zone_name": name, "category": category,
                                   "message": message, "severity": severity})
            for item in self.get_neighborhood_issues(zid):
                if item.get("status") not in ("مختومه", "انجام‌شده") and not item.get("related_office"):
                    issues.append({"zone_id": zid, "zone_name": name, "category": "مسائل",
                                   "message": f"مسئله «{item['title']}» دستگاه مسئول ندارد", "severity": "زیاد"})
            for item in self.get_neighborhood_actions(zid):
                if item.get("status") not in ("تکمیل‌شده", "لغوشده") and not item.get("planned_end"):
                    issues.append({"zone_id": zid, "zone_name": name, "category": "اقدامات",
                                   "message": f"اقدام «{item['title']}» مهلت پایان ندارد", "severity": "متوسط"})
            for item in self.get_citizen_requests(zid):
                if item.get("status") not in ("پاسخ‌داده‌شده", "مختومه", "ردشده") and not item.get("assigned_office"):
                    issues.append({"zone_id": zid, "zone_name": name, "category": "درخواست مردمی",
                                   "message": f"درخواست «{item['tracking_code']}» دستگاه مسئول ندارد", "severity": "زیاد"})
        return issues

    def db_snapshot_ready(self, zone_id):
        snap = self.get_zone_snapshot(zone_id)
        return bool(snap and snap.get("render_status") == "ready" and snap.get("png_data"))

    def get_zone_performance(self, zone_id):
        profile = self.get_zone_profile(zone_id)
        issues = self.get_neighborhood_issues(zone_id)
        actions = self.get_neighborhood_actions(zone_id)
        resolutions = self.get_neighborhood_resolutions(zone_id=zone_id)
        citizen_requests = self.get_citizen_requests(zone_id)
        field_visits = self.get_field_visits(zone_id)
        budget = self.get_budget_summary(zone_id)
        completeness_checks = [
            bool(profile.get("approved_households")), bool(self.get_streets(zone_id)),
            bool(self.get_mosques(zone_id=zone_id)), bool(self.get_council_members(zone_id)),
            bool(self.get_zone_meeting_place(zone_id)), self.db_snapshot_ready(zone_id),
            bool(field_visits),
        ]
        completeness = sum(completeness_checks) / len(completeness_checks) * 100
        issue_rate = (sum(1 for x in issues if x.get("status") in ("مختومه", "انجام‌شده")) / len(issues) * 100) if issues else 100
        action_rate = (sum(1 for x in actions if x.get("status") == "تکمیل‌شده") / len(actions) * 100) if actions else 100
        resolution_rate = (sum(1 for x in resolutions if x.get("status") == "انجام‌شده") / len(resolutions) * 100) if resolutions else 100
        citizen_response = (sum(1 for x in citizen_requests if x.get("status") in ("پاسخ‌داده‌شده", "مختومه")) / len(citizen_requests) * 100) if citizen_requests else 100
        field_followups = [x for x in field_visits if x.get("followup_required")]
        field_followup_rate = (sum(1 for x in field_followups if x.get("status") == "تکمیل‌شده") / len(field_followups) * 100) if field_followups else 100
        participation = (citizen_response * 0.65 + field_followup_rate * 0.35)
        overdue = sum(1 for x in actions if x.get("status") not in ("تکمیل‌شده", "لغوشده") and self._is_overdue(x.get("planned_end")))
        timeliness = max(0, 100 - overdue * 20)
        financial = 100 if not budget["count"] else max(0, 100 - budget["overrun_count"] * 25)
        total = round(completeness * 0.20 + issue_rate * 0.17 + action_rate * 0.17 +
                      resolution_rate * 0.12 + timeliness * 0.10 + financial * 0.09 + participation * 0.15, 1)
        if total >= 85:
            level = "عالی"
        elif total >= 70:
            level = "خوب"
        elif total >= 50:
            level = "نیازمند بهبود"
        else:
            level = "بحرانی"
        return {"total_score": total, "level": level, "completeness": round(completeness, 1),
                "issue_resolution": round(issue_rate, 1), "action_completion": round(action_rate, 1),
                "resolution_completion": round(resolution_rate, 1), "timeliness": round(timeliness, 1),
                "financial_control": round(financial, 1), "participation_response": round(participation, 1),
                "citizen_response": round(citizen_response, 1), "field_followup_completion": round(field_followup_rate, 1),
                "overdue_actions": overdue, "budget": budget}

    def get_agency_performance(self):
        agencies = self.get_management_agencies(active_only=False)
        issues = self.get_neighborhood_issues()
        actions = self.get_neighborhood_actions()
        resolutions = self.get_neighborhood_resolutions()
        result = []
        for agency in agencies:
            name = agency["name"].strip()
            ai = [x for x in issues if (x.get("related_office") or "").strip() == name]
            aa = [x for x in actions if (x.get("responsible_office") or "").strip() == name]
            ar = [x for x in resolutions if (x.get("responsible_office") or "").strip() == name]
            assigned = len(ai) + len(aa) + len(ar)
            completed = sum(1 for x in ai if x.get("status") in ("مختومه", "انجام‌شده")) + \
                        sum(1 for x in aa if x.get("status") == "تکمیل‌شده") + \
                        sum(1 for x in ar if x.get("status") == "انجام‌شده")
            overdue = sum(1 for x in ai if x.get("status") not in ("مختومه", "انجام‌شده") and self._is_overdue(x.get("due_date"))) + \
                      sum(1 for x in aa if x.get("status") not in ("تکمیل‌شده", "لغوشده") and self._is_overdue(x.get("planned_end"))) + \
                      sum(1 for x in ar if x.get("status") not in ("انجام‌شده", "لغوشده") and self._is_overdue(x.get("due_date")))
            result.append({**agency, "assigned": assigned, "completed": completed, "overdue": overdue,
                           "completion_percent": round(completed / assigned * 100, 1) if assigned else 0.0})
        return sorted(result, key=lambda x: (-x["assigned"], x["name"]))

    # ---------------- Operations & Participation v6.2 ----------------
    FIELD_VISIT_TYPES = ["بازدید عمومی", "شمارش خانوار", "بررسی مشکل", "کنترل پروژه", "ارزیابی خدمات", "جلسه میدانی"]
    FIELD_VISIT_STATUSES = ["ثبت‌شده", "نیازمند پیگیری", "ارجاع‌شده", "تکمیل‌شده"]
    CITIZEN_REQUEST_STATUSES = ["دریافت‌شده", "در حال بررسی", "ارجاع‌شده", "در حال اقدام", "پاسخ‌داده‌شده", "مختومه", "ردشده"]

    @staticmethod
    def _new_client_uid(prefix):
        return f"{prefix}-{uuid.uuid4().hex}"

    @staticmethod
    def _sync_payload_hash(payload):
        ignored = {"id", "updated_at", "created_at", "_change_hash", "_base_version", "_record_version", "_source_device", "record_version", "last_modified_device", "zone_name"}
        clean = {k: v for k, v in dict(payload or {}).items() if k not in ignored}
        raw = json.dumps(clean, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get_or_create_device_id(self):
        row = self.conn.execute("SELECT value FROM metadata WHERE key='device_id'").fetchone()
        if row and row[0]:
            return row[0]
        device_id = f"DEV-{uuid.uuid4().hex[:12].upper()}"
        self.conn.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('device_id',?)", (device_id,))
        self.conn.commit()
        return device_id

    def _queue_offline_change(self, entity_type, entity_uid, operation, payload, base_version=None):
        """نسخه کامل رکورد را همراه مبنای نسخه برای تشخیص تعارض در صف می‌گذارد."""
        payload = dict(payload or {})
        if payload.get("zone_id") and not payload.get("zone_name"):
            zone = self.get_zone(payload.get("zone_id"))
            if zone:
                payload["zone_name"] = zone.get("name")
        version = int(payload.get("record_version") or payload.get("_record_version") or 1)
        payload["_record_version"] = version
        payload["_base_version"] = int(base_version if base_version is not None else max(0, version - 1))
        payload["_source_device"] = payload.get("last_modified_device") or payload.get("source_device") or self.get_or_create_device_id()
        payload["_change_hash"] = self._sync_payload_hash(payload)
        self.conn.execute(
            """INSERT INTO offline_sync_queue(entity_type, entity_uid, operation, payload_json)
               VALUES (?, ?, ?, ?)""",
            (entity_type, entity_uid, operation, json.dumps(payload, ensure_ascii=False, default=str)),
        )

    def add_field_visit(self, zone_id, visit_date=None, start_time=None, officer_name="",
                        visit_type="بازدید عمومی", location_text="", lat=None, lon=None,
                        buildings_count=0, households_count=0, observation="", immediate_action="",
                        followup_required=False, status="ثبت‌شده", source_device="سامانه اصلی",
                        client_uid=None, queue_change=True):
        client_uid = client_uid or self._new_client_uid("FV")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO field_visits
               (client_uid, zone_id, visit_date, start_time, officer_name, visit_type, location_text,
                lat, lon, buildings_count, households_count, observation, immediate_action,
                followup_required, status, source_device, record_version, last_modified_device)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (client_uid, zone_id, visit_date, start_time, officer_name.strip(), visit_type,
             location_text.strip(), lat, lon, max(0, int(buildings_count or 0)),
             max(0, int(households_count or 0)), observation.strip(), immediate_action.strip(),
             1 if followup_required else 0, status, source_device, source_device or self.get_or_create_device_id()),
        )
        visit_id = cur.lastrowid
        item = self.get_field_visit(visit_id)
        if queue_change:
            self._queue_offline_change("field_visit", client_uid, "upsert", item, base_version=0)
        self.conn.commit()
        self.log_action("field_visit_saved", "field_visit", visit_id, {"zone_id": zone_id, "status": status})
        return visit_id

    def update_field_visit(self, visit_id, queue_change=True, **changes):
        allowed = {"visit_date", "start_time", "officer_name", "visit_type", "location_text", "lat", "lon",
                   "buildings_count", "households_count", "observation", "immediate_action",
                   "followup_required", "status", "source_device"}
        clean = {k: v for k, v in changes.items() if k in allowed}
        if not clean:
            return self.get_field_visit(visit_id)
        for key in ("buildings_count", "households_count"):
            if key in clean:
                clean[key] = max(0, int(clean[key] or 0))
        if "followup_required" in clean:
            clean["followup_required"] = 1 if clean["followup_required"] else 0
        before = self.get_field_visit(visit_id)
        base_version = int((before or {}).get("record_version") or 1)
        sql = ", ".join(f"{key}=?" for key in clean)
        self.conn.execute(f"UPDATE field_visits SET {sql}, record_version=COALESCE(record_version,1)+1, last_modified_device=COALESCE(?,last_modified_device), updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [clean[key] for key in clean] + [clean.get("source_device") or self.get_or_create_device_id(), visit_id])
        item = self.get_field_visit(visit_id)
        if item and queue_change:
            self._queue_offline_change("field_visit", item["client_uid"], "upsert", item, base_version=base_version)
        self.conn.commit()
        return item

    def delete_field_visit(self, visit_id, queue_change=True):
        item = self.get_field_visit(visit_id)
        if not item:
            return False
        self.conn.execute("DELETE FROM field_visits WHERE id=?", (visit_id,))
        if queue_change:
            self._queue_offline_change("field_visit", item["client_uid"], "delete",
                                       {"client_uid": item["client_uid"], "zone_id": item.get("zone_id"),
                                        "record_version": int(item.get("record_version") or 1) + 1},
                                       base_version=int(item.get("record_version") or 1))
        self.conn.commit()
        return True

    def get_field_visit(self, visit_id):
        row = self.conn.execute("SELECT * FROM field_visits WHERE id=?", (visit_id,)).fetchone()
        if not row:
            return None
        keys = [d[0] for d in self.conn.execute("SELECT * FROM field_visits LIMIT 0").description]
        return dict(zip(keys, row))

    def get_field_visits(self, zone_id=None):
        sql = "SELECT * FROM field_visits"
        params = []
        if zone_id is not None:
            sql += " WHERE zone_id=?"
            params.append(zone_id)
        sql += " ORDER BY COALESCE(visit_date, created_at) DESC, id DESC"
        rows = self.conn.execute(sql, params).fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM field_visits LIMIT 0").description]
        return [dict(zip(keys, row)) for row in rows]

    def _next_tracking_code(self):
        today = datetime.now().strftime("%Y%m%d")
        for _ in range(20):
            code = f"JR-{today}-{secrets.token_hex(3).upper()}"
            if not self.conn.execute("SELECT 1 FROM citizen_requests WHERE tracking_code=?", (code,)).fetchone():
                return code
        return f"JR-{today}-{uuid.uuid4().hex[:10].upper()}"

    def add_citizen_request(self, zone_id, title, category="سایر", description="", citizen_name="",
                            mobile="", is_anonymous=False, consent_contact=True, location_text="",
                            lat=None, lon=None, urgency=3, status="دریافت‌شده", assigned_office="",
                            source="ثبت حضوری", received_at=None, client_uid=None, tracking_code=None,
                            queue_change=True, source_device=None):
        client_uid = client_uid or self._new_client_uid("CR")
        tracking_code = tracking_code or self._next_tracking_code()
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO citizen_requests
               (client_uid, tracking_code, zone_id, citizen_name, mobile, is_anonymous, consent_contact,
                category, title, description, location_text, lat, lon, urgency, status,
                assigned_office, source, received_at, record_version, last_modified_device)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), 1, ?)""",
            (client_uid, tracking_code, zone_id, citizen_name.strip(), mobile.strip(), 1 if is_anonymous else 0,
             1 if consent_contact else 0, category, title.strip(), description.strip(), location_text.strip(),
             lat, lon, max(1, min(5, int(urgency or 3))), status, assigned_office.strip(), source, received_at,
             source_device or self.get_or_create_device_id()),
        )
        request_id = cur.lastrowid
        item = self.get_citizen_request(request_id)
        if queue_change:
            self._queue_offline_change("citizen_request", client_uid, "upsert", item, base_version=0)
        self.conn.commit()
        self.log_action("citizen_request_saved", "citizen_request", request_id, {"tracking_code": tracking_code})
        return request_id

    def update_citizen_request(self, request_id, queue_change=True, **changes):
        allowed = {"citizen_name", "mobile", "is_anonymous", "consent_contact", "category", "title",
                   "description", "location_text", "lat", "lon", "urgency", "status", "assigned_office",
                   "linked_issue_id", "source", "received_at"}
        clean = {k: v for k, v in changes.items() if k in allowed}
        if not clean:
            return self.get_citizen_request(request_id)
        for key in ("is_anonymous", "consent_contact"):
            if key in clean:
                clean[key] = 1 if clean[key] else 0
        if "urgency" in clean:
            clean["urgency"] = max(1, min(5, int(clean["urgency"] or 3)))
        before = self.get_citizen_request(request_id)
        base_version = int((before or {}).get("record_version") or 1)
        sql = ", ".join(f"{key}=?" for key in clean)
        self.conn.execute(f"UPDATE citizen_requests SET {sql}, record_version=COALESCE(record_version,1)+1, last_modified_device=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                          [clean[key] for key in clean] + [self.get_or_create_device_id(), request_id])
        item = self.get_citizen_request(request_id)
        if item and queue_change:
            self._queue_offline_change("citizen_request", item["client_uid"], "upsert", item, base_version=base_version)
        self.conn.commit()
        return item

    def delete_citizen_request(self, request_id, queue_change=True):
        item = self.get_citizen_request(request_id)
        if not item:
            return False
        self.conn.execute("DELETE FROM citizen_requests WHERE id=?", (request_id,))
        if queue_change:
            self._queue_offline_change("citizen_request", item["client_uid"], "delete",
                                       {"client_uid": item["client_uid"], "zone_id": item.get("zone_id"),
                                        "record_version": int(item.get("record_version") or 1) + 1},
                                       base_version=int(item.get("record_version") or 1))
        self.conn.commit()
        return True

    def get_citizen_request(self, request_id):
        row = self.conn.execute("SELECT * FROM citizen_requests WHERE id=?", (request_id,)).fetchone()
        if not row:
            return None
        keys = [d[0] for d in self.conn.execute("SELECT * FROM citizen_requests LIMIT 0").description]
        return dict(zip(keys, row))

    def get_citizen_requests(self, zone_id=None, status=None):
        clauses, params = [], []
        if zone_id is not None:
            clauses.append("zone_id=?")
            params.append(zone_id)
        if status:
            clauses.append("status=?")
            params.append(status)
        sql = "SELECT * FROM citizen_requests"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY CASE urgency WHEN 5 THEN 0 WHEN 4 THEN 1 ELSE 2 END, received_at DESC, id DESC"
        rows = self.conn.execute(sql, params).fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM citizen_requests LIMIT 0").description]
        return [dict(zip(keys, row)) for row in rows]

    def convert_citizen_request_to_issue(self, request_id):
        request = self.get_citizen_request(request_id)
        if not request:
            raise ValueError("درخواست مردمی یافت نشد")
        if request.get("linked_issue_id"):
            return request["linked_issue_id"]
        issue_id = self.add_neighborhood_issue(
            request["zone_id"], request["title"], category=request.get("category") or "سایر",
            description=request.get("description") or "", related_office=request.get("assigned_office") or "",
            urgency=request.get("urgency") or 3, severity=request.get("urgency") or 3,
            affected_households=0, safety_risk=max(1, (request.get("urgency") or 3) - 1),
            status="ثبت اولیه", source=f"درخواست مردمی {request['tracking_code']}",
            location_text=request.get("location_text") or "", lat=request.get("lat"), lon=request.get("lon"),
        )
        self.update_citizen_request(request_id, linked_issue_id=issue_id, status="در حال بررسی")
        return issue_id

    def get_sync_queue(self, status=None):
        sql = "SELECT * FROM offline_sync_queue"
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY id DESC"
        rows = self.conn.execute(sql, params).fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM offline_sync_queue LIMIT 0").description]
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            try:
                item["payload"] = json.loads(item.get("payload_json") or "{}")
            except Exception:
                item["payload"] = {}
            result.append(item)
        return result

    def mark_sync_entries_transferred(self, entry_ids):
        ids = [int(x) for x in entry_ids if x is not None]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        self.conn.execute(
            f"UPDATE offline_sync_queue SET status='منتقل‌شده', synced_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
            ids,
        )
        self.conn.commit()
        return len(ids)

    def export_sync_package(self, output_path, zone_id=None):
        pending_entries = self.get_sync_queue(status="در انتظار انتقال")
        if zone_id is not None:
            pending_entries = [e for e in pending_entries if (e.get("payload") or {}).get("zone_id") == zone_id]

        # جدیدترین تغییر هر موجودیت کافی است؛ تاریخچه کامل در صف و لاگ باقی می‌ماند.
        latest_by_entity = {}
        for entry in pending_entries:
            key = (entry.get("entity_type"), entry.get("entity_uid"))
            if key not in latest_by_entity:
                latest_by_entity[key] = entry
        compact_entries = list(reversed(list(latest_by_entity.values())))

        package = {
            "format": "javanrood-neighborhood-sync",
            "version": 2,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source": "سامانه مدیریت محلات جوانرود",
            "source_device": self.get_or_create_device_id(),
            "entries": [{"entity_type": e["entity_type"], "entity_uid": e["entity_uid"],
                         "operation": e["operation"], "payload": e["payload"]} for e in compact_entries],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(package, f, ensure_ascii=False, indent=2)
        self.mark_sync_entries_transferred([e["id"] for e in pending_entries])
        return {"path": output_path, "count": len(compact_entries),
                "compacted_from": len(pending_entries), "version": 2,
                "source_device": package["source_device"]}

    def _resolve_import_zone_id(self, payload):
        zone_id = payload.get("zone_id")
        zone_name = (payload.get("zone_name") or "").strip()
        if zone_id:
            existing = self.get_zone(zone_id)
            if existing and (not zone_name or (existing.get("name") or "").strip() == zone_name):
                return zone_id
        if zone_name:
            row = self.conn.execute("SELECT id FROM zones WHERE TRIM(name)=? ORDER BY id LIMIT 1", (zone_name,)).fetchone()
            if row:
                return row[0]
        return None

    def _create_sync_conflict(self, entity_type, entity_uid, local_payload, incoming_payload, source_device=None):
        zone_id = self._resolve_import_zone_id(incoming_payload) or local_payload.get("zone_id")
        local_version = int(local_payload.get("record_version") or 1)
        incoming_version = int(incoming_payload.get("_record_version") or incoming_payload.get("record_version") or 1)
        base_version = int(incoming_payload.get("_base_version") or max(0, incoming_version - 1))
        self.conn.execute(
            """INSERT INTO sync_conflicts
               (entity_type,entity_uid,zone_id,local_version,incoming_version,base_version,
                local_payload_json,incoming_payload_json,source_device)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(entity_type,entity_uid) WHERE status='در انتظار تصمیم'
               DO UPDATE SET zone_id=excluded.zone_id, local_version=excluded.local_version,
                  incoming_version=excluded.incoming_version, base_version=excluded.base_version,
                  local_payload_json=excluded.local_payload_json,
                  incoming_payload_json=excluded.incoming_payload_json,
                  source_device=excluded.source_device, created_at=CURRENT_TIMESTAMP""",
            (entity_type, entity_uid, zone_id, local_version, incoming_version, base_version,
             json.dumps(local_payload, ensure_ascii=False, default=str),
             json.dumps(incoming_payload, ensure_ascii=False, default=str), source_device),
        )
        self.conn.commit()

    def _has_sync_conflict(self, local_payload, incoming_payload):
        if not local_payload:
            return False
        incoming_version = int(incoming_payload.get("_record_version") or incoming_payload.get("record_version") or 1)
        base_version = int(incoming_payload.get("_base_version") or max(0, incoming_version - 1))
        local_version = int(local_payload.get("record_version") or 1)
        if local_version <= base_version:
            return False
        return self._sync_payload_hash(local_payload) != self._sync_payload_hash(incoming_payload)

    def _apply_imported_field_visit(self, payload, operation):
        uid = payload.get("client_uid")
        if not uid:
            return "ignored"
        existing = self.conn.execute("SELECT id FROM field_visits WHERE client_uid=?", (uid,)).fetchone()
        if operation == "delete":
            if existing:
                self.delete_field_visit(existing[0], queue_change=False)
            return "deleted"
        resolved_zone_id = self._resolve_import_zone_id(payload)
        if not resolved_zone_id:
            return "zone_missing"
        keys = (
            "visit_date", "start_time", "officer_name", "visit_type", "location_text", "lat", "lon",
            "buildings_count", "households_count", "observation", "immediate_action", "followup_required",
            "status", "source_device", "data_classification", "lifecycle_status"
        )
        data = {k: payload.get(k) for k in keys}
        version = int(payload.get("_record_version") or payload.get("record_version") or 1)
        device = payload.get("_source_device") or payload.get("last_modified_device") or payload.get("source_device")
        if existing:
            assignments = ", ".join([f"{k}=?" for k in keys])
            self.conn.execute(
                f"UPDATE field_visits SET zone_id=?, {assignments}, record_version=?, last_modified_device=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [resolved_zone_id] + [data[k] for k in keys] + [version, device, existing[0]],
            )
            self.conn.commit()
            return "updated"
        visit_id = self.add_field_visit(
            resolved_zone_id, client_uid=uid, queue_change=False,
            visit_date=data["visit_date"], start_time=data["start_time"], officer_name=data["officer_name"] or "",
            visit_type=data["visit_type"] or "بازدید عمومی", location_text=data["location_text"] or "",
            lat=data["lat"], lon=data["lon"], buildings_count=data["buildings_count"] or 0,
            households_count=data["households_count"] or 0, observation=data["observation"] or "",
            immediate_action=data["immediate_action"] or "", followup_required=data["followup_required"],
            status=data["status"] or "ثبت‌شده", source_device=data["source_device"] or device or "سامانه اصلی",
        )
        self.conn.execute(
            "UPDATE field_visits SET record_version=?, last_modified_device=?, data_classification=COALESCE(?,data_classification), lifecycle_status=COALESCE(?,lifecycle_status) WHERE id=?",
            (version, device, data.get("data_classification"), data.get("lifecycle_status"), visit_id),
        )
        self.conn.commit()
        return "inserted"

    def _apply_imported_citizen_request(self, payload, operation):
        uid = payload.get("client_uid")
        if not uid:
            return "ignored"
        existing = self.conn.execute("SELECT id FROM citizen_requests WHERE client_uid=?", (uid,)).fetchone()
        if operation == "delete":
            if existing:
                self.delete_citizen_request(existing[0], queue_change=False)
            return "deleted"
        resolved_zone_id = self._resolve_import_zone_id(payload)
        if not resolved_zone_id:
            return "zone_missing"
        keys = (
            "citizen_name", "mobile", "is_anonymous", "consent_contact", "category", "title",
            "description", "location_text", "lat", "lon", "urgency", "status", "assigned_office",
            "linked_issue_id", "source", "received_at", "data_classification", "lifecycle_status"
        )
        data = {k: payload.get(k) for k in keys}
        if data.get("linked_issue_id") and not self.conn.execute(
            "SELECT 1 FROM neighborhood_issues WHERE id=?", (data.get("linked_issue_id"),)
        ).fetchone():
            data["linked_issue_id"] = None
        version = int(payload.get("_record_version") or payload.get("record_version") or 1)
        device = payload.get("_source_device") or payload.get("last_modified_device")
        if existing:
            assignments = ", ".join([f"{k}=?" for k in keys])
            self.conn.execute(
                f"UPDATE citizen_requests SET zone_id=?, {assignments}, record_version=?, last_modified_device=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                [resolved_zone_id] + [data[k] for k in keys] + [version, device, existing[0]],
            )
            self.conn.commit()
            return "updated"
        tracking_code = payload.get("tracking_code") or self._next_tracking_code()
        if self.conn.execute("SELECT 1 FROM citizen_requests WHERE tracking_code=?", (tracking_code,)).fetchone():
            tracking_code = self._next_tracking_code()
        request_id = self.add_citizen_request(
            resolved_zone_id, data["title"] or "درخواست واردشده", category=data["category"] or "سایر",
            description=data["description"] or "", citizen_name=data["citizen_name"] or "",
            mobile=data["mobile"] or "", is_anonymous=data["is_anonymous"], consent_contact=data["consent_contact"],
            location_text=data["location_text"] or "", lat=data["lat"], lon=data["lon"],
            urgency=data["urgency"] or 3, status=data["status"] or "دریافت‌شده",
            assigned_office=data["assigned_office"] or "", source=data["source"] or "بسته آفلاین",
            received_at=data["received_at"], client_uid=uid, tracking_code=tracking_code,
            queue_change=False, source_device=device,
        )
        self.conn.execute(
            "UPDATE citizen_requests SET linked_issue_id=?, record_version=?, last_modified_device=?, data_classification=COALESCE(?,data_classification), lifecycle_status=COALESCE(?,lifecycle_status) WHERE id=?",
            (data.get("linked_issue_id"), version, device, data.get("data_classification"), data.get("lifecycle_status"), request_id),
        )
        self.conn.commit()
        return "inserted"

    def _upsert_imported_field_visit(self, payload, operation, source_device=None, force=False):
        uid = payload.get("client_uid")
        existing = None
        if uid:
            row = self.conn.execute("SELECT id FROM field_visits WHERE client_uid=?", (uid,)).fetchone()
            existing = self.get_field_visit(row[0]) if row else None
        if not force and operation != "delete" and existing and self._has_sync_conflict(existing, payload):
            self._create_sync_conflict("field_visit", uid, existing, payload, source_device)
            return "conflicted"
        return self._apply_imported_field_visit(payload, operation)

    def _upsert_imported_citizen_request(self, payload, operation, source_device=None, force=False):
        uid = payload.get("client_uid")
        existing = None
        if uid:
            row = self.conn.execute("SELECT id FROM citizen_requests WHERE client_uid=?", (uid,)).fetchone()
            existing = self.get_citizen_request(row[0]) if row else None
        if not force and operation != "delete" and existing and self._has_sync_conflict(existing, payload):
            self._create_sync_conflict("citizen_request", uid, existing, payload, source_device)
            return "conflicted"
        return self._apply_imported_citizen_request(payload, operation)

    def import_sync_package(self, input_path):
        with open(input_path, "r", encoding="utf-8") as f:
            package = json.load(f)
        if not isinstance(package, dict) or package.get("format") != "javanrood-neighborhood-sync":
            raise ValueError("فرمت بسته تبادل معتبر نیست")
        package_version = int(package.get("version") or 0)
        if package_version not in (1, 2):
            raise ValueError("نسخه بسته تبادل پشتیبانی نمی‌شود")
        entries = package.get("entries")
        if not isinstance(entries, list):
            raise ValueError("ساختار رکوردهای بسته تبادل معتبر نیست")
        if len(entries) > 50000:
            raise ValueError("تعداد رکوردهای بسته تبادل بیش از حد مجاز است")
        source_device = package.get("source_device") or package.get("source")
        counts = {"inserted": 0, "updated": 0, "deleted": 0, "ignored": 0,
                  "zone_missing": 0, "conflicted": 0, "errors": 0}
        for entry in entries:
            try:
                if not isinstance(entry, dict):
                    counts["errors"] += 1
                    continue
                entity_type = entry.get("entity_type")
                payload = entry.get("payload") or {}
                operation = entry.get("operation") or "upsert"
                if not isinstance(payload, dict) or operation not in ("upsert", "delete"):
                    counts["errors"] += 1
                    continue
                if package_version == 1:
                    payload.setdefault("_record_version", payload.get("record_version") or 1)
                    payload.setdefault("_base_version", max(0, int(payload["_record_version"]) - 1))
                if entity_type == "field_visit":
                    result = self._upsert_imported_field_visit(payload, operation, source_device)
                elif entity_type == "citizen_request":
                    result = self._upsert_imported_citizen_request(payload, operation, source_device)
                else:
                    result = "ignored"
                counts[result] = counts.get(result, 0) + 1
            except Exception:
                counts["errors"] += 1
        return counts

    def get_sync_conflicts(self, status=None):
        sql = "SELECT * FROM sync_conflicts"
        params = []
        if status:
            sql += " WHERE status=?"
            params.append(status)
        sql += " ORDER BY CASE status WHEN 'در انتظار تصمیم' THEN 0 ELSE 1 END, created_at DESC, id DESC"
        rows = self.conn.execute(sql, params).fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM sync_conflicts LIMIT 0").description]
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            for key in ("local_payload_json", "incoming_payload_json"):
                try:
                    item[key.replace("_json", "")] = json.loads(item.get(key) or "{}")
                except Exception:
                    item[key.replace("_json", "")] = {}
            result.append(item)
        return result

    def resolve_sync_conflict(self, conflict_id, resolution, merged_payload=None):
        conflict = self.conn.execute("SELECT * FROM sync_conflicts WHERE id=?", (conflict_id,)).fetchone()
        if not conflict:
            raise ValueError("تعارض یافت نشد")
        keys = [d[0] for d in self.conn.execute("SELECT * FROM sync_conflicts LIMIT 0").description]
        item = dict(zip(keys, conflict))
        if item.get("status") != "در انتظار تصمیم":
            return False
        local_payload = json.loads(item.get("local_payload_json") or "{}")
        incoming_payload = json.loads(item.get("incoming_payload_json") or "{}")
        if resolution == "نسخه ورودی":
            payload = incoming_payload
        elif resolution == "ادغام دستی":
            payload = dict(local_payload)
            payload.update(dict(merged_payload or {}))
            payload["client_uid"] = item["entity_uid"]
            payload["_record_version"] = max(int(item.get("local_version") or 1), int(item.get("incoming_version") or 1)) + 1
            payload["_base_version"] = max(int(item.get("local_version") or 1), int(item.get("incoming_version") or 1))
        elif resolution == "نسخه محلی":
            payload = None
        else:
            raise ValueError("نوع تصمیم تعارض معتبر نیست")
        if payload is not None:
            if item["entity_type"] == "field_visit":
                self._upsert_imported_field_visit(payload, "upsert", item.get("source_device"), force=True)
            elif item["entity_type"] == "citizen_request":
                self._upsert_imported_citizen_request(payload, "upsert", item.get("source_device"), force=True)
        user_id = (self.current_user or {}).get("id")
        self.conn.execute(
            "UPDATE sync_conflicts SET status='حل‌شده', resolution=?, resolved_by=?, resolved_at=CURRENT_TIMESTAMP WHERE id=?",
            (resolution, user_id, conflict_id),
        )
        self.conn.commit()
        self.log_action("sync_conflict_resolved", item["entity_type"], item["entity_uid"],
                        {"resolution": resolution, "conflict_id": conflict_id})
        return True

    # ---------------- Data Governance & Public Portal v6.9 ----------------
    def get_governance_policies(self):
        rows = self.conn.execute("SELECT * FROM data_governance_policies ORDER BY title").fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM data_governance_policies LIMIT 0").description]
        return [dict(zip(keys, row)) for row in rows]

    def update_governance_policy(self, entity_type, **changes):
        allowed = {"title", "classification", "retention_days", "requires_approval", "public_allowed", "contains_personal_data", "notes"}
        clean = {k: v for k, v in changes.items() if k in allowed}
        if not clean:
            return False
        for key in ("requires_approval", "public_allowed", "contains_personal_data"):
            if key in clean:
                clean[key] = 1 if clean[key] else 0
        if "retention_days" in clean:
            clean["retention_days"] = max(0, int(clean["retention_days"] or 0))
        sql = ", ".join(f"{k}=?" for k in clean)
        self.conn.execute(f"UPDATE data_governance_policies SET {sql}, updated_at=CURRENT_TIMESTAMP WHERE entity_type=?",
                          [clean[k] for k in clean] + [entity_type])
        self.conn.commit()
        return True

    def set_record_governance(self, entity_type, entity_uid, zone_id=None, classification=None,
                              lifecycle_status="پیش‌نویس", data_owner="", reviewer_user_id=None,
                              retention_until=None, is_public=False, notes=""):
        policy = self.conn.execute("SELECT * FROM data_governance_policies WHERE entity_type=?", (entity_type,)).fetchone()
        if classification is None:
            classification = policy[2] if policy else "داخلی"
        if classification in ("محرمانه", "خیلی محرمانه"):
            is_public = False
        self.conn.execute(
            """INSERT INTO record_governance
               (entity_type,entity_uid,zone_id,classification,lifecycle_status,data_owner,reviewer_user_id,
                retention_until,is_public,notes,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
               ON CONFLICT(entity_type,entity_uid) DO UPDATE SET
                 zone_id=excluded.zone_id, classification=excluded.classification,
                 lifecycle_status=excluded.lifecycle_status, data_owner=excluded.data_owner,
                 reviewer_user_id=excluded.reviewer_user_id, retention_until=excluded.retention_until,
                 is_public=excluded.is_public, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
            (entity_type, str(entity_uid), zone_id, classification, lifecycle_status, data_owner.strip(),
             reviewer_user_id, retention_until, 1 if is_public else 0, notes.strip()),
        )
        self.conn.commit()
        return self.get_record_governance(entity_type, entity_uid)

    def get_record_governance(self, entity_type, entity_uid):
        row = self.conn.execute(
            "SELECT * FROM record_governance WHERE entity_type=? AND entity_uid=?",
            (entity_type, str(entity_uid)),
        ).fetchone()
        if not row:
            return None
        keys = [d[0] for d in self.conn.execute("SELECT * FROM record_governance LIMIT 0").description]
        return dict(zip(keys, row))

    def list_record_governance(self, zone_id=None, lifecycle_status=None):
        clauses, params = [], []
        if zone_id is not None:
            clauses.append("zone_id=?"); params.append(zone_id)
        if lifecycle_status:
            clauses.append("lifecycle_status=?"); params.append(lifecycle_status)
        sql = "SELECT * FROM record_governance"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC"
        rows = self.conn.execute(sql, params).fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM record_governance LIMIT 0").description]
        return [dict(zip(keys, row)) for row in rows]

    def approve_record_governance(self, governance_id, approve=True):
        user_id = (self.current_user or {}).get("id")
        status = "تأییدشده" if approve else "نیازمند بازبینی"
        self.conn.execute(
            "UPDATE record_governance SET lifecycle_status=?, approved_at=CURRENT_TIMESTAMP, approved_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, user_id, governance_id),
        )
        self.conn.commit()
        return True

    def get_retention_alerts(self, days_ahead=30):
        today = datetime.now().date()
        threshold = today + timedelta(days=max(0, int(days_ahead)))
        result = []
        for item in self.list_record_governance():
            value = item.get("retention_until")
            if not value:
                continue
            try:
                date_value = datetime.fromisoformat(str(value)[:10]).date()
            except Exception:
                continue
            if date_value <= threshold and item.get("lifecycle_status") != "آرشیوشده":
                item = dict(item)
                item["days_remaining"] = (date_value - today).days
                result.append(item)
        return sorted(result, key=lambda x: x["days_remaining"])

    def register_publication(self, title, output_path, zones_count=0, projects_count=0, requests_count=0):
        publication_uid = f"PUB-{uuid.uuid4().hex}"
        checksum = self._file_sha256(output_path) if os.path.isfile(output_path) else None
        cur = self.conn.execute(
            """INSERT INTO public_portal_publications
               (publication_uid,title,output_path,zones_count,projects_count,requests_count,generated_by,checksum)
               VALUES (?,?,?,?,?,?,?,?)""",
            (publication_uid, title, os.path.abspath(output_path), int(zones_count or 0),
             int(projects_count or 0), int(requests_count or 0),
             (self.current_user or {}).get("id"), checksum),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_publications(self):
        rows = self.conn.execute("SELECT * FROM public_portal_publications ORDER BY generated_at DESC, id DESC").fetchall()
        keys = [d[0] for d in self.conn.execute("SELECT * FROM public_portal_publications LIMIT 0").description]
        return [dict(zip(keys, row)) for row in rows]

    def get_zone_operational_analysis(self, zone_id):
        zone = self.get_zone(zone_id)
        if not zone:
            return {}
        issues = self.get_neighborhood_issues(zone_id)
        requests = self.get_citizen_requests(zone_id)
        visits = self.get_field_visits(zone_id)
        actions = self.get_neighborhood_actions(zone_id)
        places = self.get_places(zone_id=zone_id)
        area_ha = max(0.01, float(zone.get("area_m2") or 0) / 10000.0)
        open_requests = [x for x in requests if x.get("status") not in ("پاسخ‌داده‌شده", "مختومه", "ردشده")]
        urgent_requests = [x for x in open_requests if int(x.get("urgency") or 0) >= 4]
        critical_issues = [x for x in issues if x.get("priority_level") in ("بحرانی", "فوری") and x.get("status") != "مختومه"]
        overdue_actions = [x for x in actions if x.get("status") not in ("تکمیل‌شده", "لغوشده") and self._is_overdue(x.get("planned_end"))]
        service_categories = {x.get("category") for x in places if x.get("category")}
        service_gap_count = sum(1 for category in ("آموزشی", "درمانی", "فضای سبز", "خدماتی") if category not in service_categories)
        risk_score = min(100.0, round(
            len(critical_issues) * 12 + len(urgent_requests) * 7 + len(overdue_actions) * 9 +
            service_gap_count * 6 + (0 if visits else 8), 1
        ))
        if risk_score >= 70:
            risk_level = "بحرانی"
        elif risk_score >= 45:
            risk_level = "زیاد"
        elif risk_score >= 20:
            risk_level = "متوسط"
        else:
            risk_level = "کم"
        return {
            "zone_id": zone_id, "zone_name": zone["name"], "area_ha": round(area_ha, 2),
            "field_visits": len(visits), "citizen_requests": len(requests), "open_requests": len(open_requests),
            "urgent_requests": len(urgent_requests), "critical_issues": len(critical_issues),
            "overdue_actions": len(overdue_actions), "service_gap_count": service_gap_count,
            "issue_density_per_ha": round(len(issues) / area_ha, 2),
            "request_density_per_ha": round(len(requests) / area_ha, 2),
            "risk_score": risk_score, "risk_level": risk_level,
        }

    def get_city_operational_analysis(self):
        return sorted(
            [self.get_zone_operational_analysis(z["id"]) for z in self.get_zones()],
            key=lambda x: (-x.get("risk_score", 0), x.get("zone_name", "")),
        )

    def build_operational_geojson(self):
        features = []
        for zone in self.get_zones():
            analysis = self.get_zone_operational_analysis(zone["id"])
            coords = [[p[1], p[0]] for p in zone.get("boundary_points", [])]
            if coords and coords[0] != coords[-1]:
                coords.append(coords[0])
            features.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [coords]},
                             "properties": analysis})
        for request in self.get_citizen_requests():
            if request.get("lat") is not None and request.get("lon") is not None:
                features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [request["lon"], request["lat"]]},
                                 "properties": {"feature_type": "citizen_request", "tracking_code": request["tracking_code"],
                                                "title": request["title"], "status": request["status"], "urgency": request["urgency"]}})
        for visit in self.get_field_visits():
            if visit.get("lat") is not None and visit.get("lon") is not None:
                features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [visit["lon"], visit["lat"]]},
                                 "properties": {"feature_type": "field_visit", "visit_type": visit["visit_type"],
                                                "visit_date": visit["visit_date"], "status": visit["status"]}})
        return {"type": "FeatureCollection", "features": features}

    def export_operational_geojson(self, output_path):
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.build_operational_geojson(), f, ensure_ascii=False, indent=2)
        return output_path

    # ---------------- Custom Header (هدر سفارشی کاربر) ----------------
    def set_custom_header_image(self, image_path):
        self.set_meta("custom_header_image_path", image_path or "")

    def get_custom_header_image(self):
        return self.get_meta("custom_header_image_path", "")

    def clear_custom_header_image(self):
        self.set_meta("custom_header_image_path", "")

    def set_official_signature(self, image_path="", signer_name="", signer_title="", verification_base_url=""):
        self.set_meta("official_signature_image_path", image_path or "")
        self.set_meta("official_signer_name", signer_name or "")
        self.set_meta("official_signer_title", signer_title or "")
        self.set_meta("document_verification_base_url", verification_base_url or "")

    def get_official_signature(self):
        return {
            "image_path": self.get_meta("official_signature_image_path", ""),
            "signer_name": self.get_meta("official_signer_name", ""),
            "signer_title": self.get_meta("official_signer_title", ""),
            "verification_base_url": self.get_meta("document_verification_base_url", ""),
        }

    def clear_official_signature(self):
        self.set_official_signature("", "", "", self.get_meta("document_verification_base_url", ""))

    # ---------------- Correspondence & Administrative Workflow v6.4 ----------------
    LETTER_DIRECTIONS = ["وارده", "صادره", "داخلی"]
    LETTER_STATUSES = ["ثبت‌شده", "در حال بررسی", "ارجاع‌شده", "در انتظار پاسخ", "پاسخ‌داده‌شده", "مختومه"]
    WORKFLOW_STATUSES = ["ارجاع‌شده", "مشاهده‌شده", "در حال اقدام", "پاسخ‌داده‌شده", "مختومه"]
    PRIORITY_LEVELS = ["عادی", "مهم", "فوری", "بحرانی"]
    CONFIDENTIALITY_LEVELS = ["عادی", "محرمانه", "خیلی محرمانه"]

    def add_correspondence_letter(self, letter_number, direction, subject, zone_id=None,
                                  sender="", recipient="", letter_date=None, received_date=None,
                                  due_date=None, status="ثبت‌شده", priority="عادی",
                                  confidentiality="عادی", related_entity_type=None,
                                  related_entity_id=None, description=""):
        if not (letter_number or "").strip():
            raise ValueError("شماره نامه الزامی است.")
        if not (subject or "").strip():
            raise ValueError("موضوع نامه الزامی است.")
        if direction not in self.LETTER_DIRECTIONS:
            raise ValueError("نوع نامه معتبر نیست.")
        actor_id = self.current_user.get("id") if self.current_user else None
        try:
            cur = self.conn.execute(
                """INSERT INTO correspondence_letters
                   (zone_id, letter_number, direction, subject, sender, recipient,
                    letter_date, received_date, due_date, status, priority, confidentiality,
                    related_entity_type, related_entity_id, description, created_by, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (zone_id, letter_number.strip(), direction, subject.strip(), sender.strip(), recipient.strip(),
                 letter_date, received_date, due_date, status, priority, confidentiality,
                 related_entity_type, str(related_entity_id) if related_entity_id is not None else None,
                 description, actor_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("این شماره نامه برای همین نوع مکاتبه قبلاً ثبت شده است.") from exc
        letter_id = cur.lastrowid
        self.log_action("correspondence_created", "letter", letter_id,
                        {"number": letter_number, "direction": direction, "subject": subject}, zone_id=zone_id)
        return letter_id

    def update_correspondence_letter(self, letter_id, **data):
        allowed = {
            "zone_id", "letter_number", "direction", "subject", "sender", "recipient",
            "letter_date", "received_date", "due_date", "status", "priority", "confidentiality",
            "related_entity_type", "related_entity_id", "description"
        }
        current = self.get_correspondence_letter(letter_id)
        if not current:
            raise ValueError("نامه پیدا نشد.")
        values = {k: data[k] for k in data if k in allowed}
        if not values:
            return current
        if "letter_number" in values and not str(values["letter_number"]).strip():
            raise ValueError("شماره نامه الزامی است.")
        if "subject" in values and not str(values["subject"]).strip():
            raise ValueError("موضوع نامه الزامی است.")
        sql = ", ".join(f"{key}=?" for key in values)
        try:
            self.conn.execute(
                f"UPDATE correspondence_letters SET {sql}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                list(values.values()) + [int(letter_id)],
            )
            self.conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("شماره نامه تکراری است.") from exc
        updated = self.get_correspondence_letter(letter_id)
        self.log_action("correspondence_updated", "letter", letter_id,
                        zone_id=updated.get("zone_id"), before=current, after=updated)
        return updated

    def delete_correspondence_letter(self, letter_id):
        current = self.get_correspondence_letter(letter_id)
        if not current:
            return False
        attachments = self.get_document_attachments("letter", letter_id)
        self.conn.execute("DELETE FROM correspondence_letters WHERE id=?", (int(letter_id),))
        self.conn.commit()
        for item in attachments:
            try:
                if item.get("stored_path") and os.path.exists(item["stored_path"]):
                    os.remove(item["stored_path"])
            except Exception:
                pass
        self.log_action("correspondence_deleted", "letter", letter_id, zone_id=current.get("zone_id"), before=current)
        return True

    def get_correspondence_letter(self, letter_id):
        row = self.conn.execute(
            """SELECT l.id, l.zone_id, z.name, l.letter_number, l.direction, l.subject,
                      l.sender, l.recipient, l.letter_date, l.received_date, l.due_date,
                      l.status, l.priority, l.confidentiality, l.related_entity_type,
                      l.related_entity_id, l.description, l.created_by, u.full_name,
                      l.created_at, l.updated_at, l.approval_status, l.approved_at, l.approved_by
               FROM correspondence_letters l
               LEFT JOIN zones z ON z.id=l.zone_id
               LEFT JOIN app_users u ON u.id=l.created_by
               WHERE l.id=?""", (int(letter_id),)
        ).fetchone()
        if not row:
            return None
        keys = ["id", "zone_id", "zone_name", "letter_number", "direction", "subject",
                "sender", "recipient", "letter_date", "received_date", "due_date", "status",
                "priority", "confidentiality", "related_entity_type", "related_entity_id",
                "description", "created_by", "created_by_name", "created_at", "updated_at",
                "approval_status", "approved_at", "approved_by"]
        item = dict(zip(keys, row))
        item["attachment_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM document_attachments WHERE parent_type='letter' AND parent_id=?",
            (int(letter_id),),
        ).fetchone()[0]
        item["assignment_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM workflow_assignments WHERE letter_id=?", (int(letter_id),)
        ).fetchone()[0]
        return item

    def get_correspondence_letters(self, zone_id=None, direction=None, status=None, query=None, limit=1000):
        clauses, params = [], []
        if zone_id is not None:
            clauses.append("l.zone_id=?")
            params.append(int(zone_id))
        if direction:
            clauses.append("l.direction=?")
            params.append(direction)
        if status:
            clauses.append("l.status=?")
            params.append(status)
        if query:
            like = f"%{query.strip()}%"
            clauses.append("(l.letter_number LIKE ? OR l.subject LIKE ? OR l.sender LIKE ? OR l.recipient LIKE ? OR l.description LIKE ?)")
            params.extend([like] * 5)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows = self.conn.execute(
            """SELECT l.id, l.zone_id, z.name, l.letter_number, l.direction, l.subject,
                      l.sender, l.recipient, l.letter_date, l.received_date, l.due_date,
                      l.status, l.priority, l.confidentiality, l.created_at, l.approval_status,
                      (SELECT COUNT(*) FROM document_attachments a WHERE a.parent_type='letter' AND a.parent_id=l.id),
                      (SELECT COUNT(*) FROM workflow_assignments w WHERE w.letter_id=l.id AND w.status NOT IN ('پاسخ‌داده‌شده','مختومه'))
               FROM correspondence_letters l LEFT JOIN zones z ON z.id=l.zone_id""" + where +
            " ORDER BY COALESCE(l.received_date,l.letter_date,l.created_at) DESC, l.id DESC LIMIT ?", params
        ).fetchall()
        keys = ["id", "zone_id", "zone_name", "letter_number", "direction", "subject", "sender",
                "recipient", "letter_date", "received_date", "due_date", "status", "priority",
                "confidentiality", "created_at", "approval_status", "attachment_count", "open_assignment_count"]
        return [dict(zip(keys, row)) for row in rows]

    def archive_document_attachment(self, parent_type, parent_id, source_path, description=""):
        if not source_path or not os.path.isfile(source_path):
            raise ValueError("فایل انتخاب‌شده وجود ندارد.")
        parent_type = (parent_type or "").strip().lower()
        if parent_type not in {"letter", "issue", "action", "meeting", "resolution", "citizen_request", "field_visit", "execution_case", "execution_assignment", "committee_resolution", "project", "zone", "committee", "council_member", "committee_member"}:
            raise ValueError("نوع پرونده پیوست معتبر نیست.")
        checksum = self._file_sha256(source_path)
        existing = self.conn.execute(
            "SELECT id FROM document_attachments WHERE parent_type=? AND parent_id=? AND checksum=?",
            (parent_type, int(parent_id), checksum),
        ).fetchone()
        if existing:
            return existing[0]
        root = os.path.join(os.path.dirname(self.db_path), "attachments", parent_type, str(parent_id))
        os.makedirs(root, exist_ok=True)
        original = os.path.basename(source_path)
        safe_name = "".join(ch if ch.isalnum() or ch in "._-() []" else "_" for ch in original)
        stored = os.path.join(root, f"{uuid.uuid4().hex[:12]}_{safe_name}")
        shutil.copy2(source_path, stored)
        mime_type = mimetypes.guess_type(original)[0] or "application/octet-stream"
        actor_id = self.current_user.get("id") if self.current_user else None
        cur = self.conn.execute(
            """INSERT INTO document_attachments
               (parent_type, parent_id, original_name, stored_path, mime_type, file_size,
                checksum, description, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (parent_type, int(parent_id), original, os.path.abspath(stored), mime_type,
             os.path.getsize(stored), checksum, description, actor_id),
        )
        self.conn.commit()
        self.log_action("attachment_archived", "attachment", cur.lastrowid,
                        {"parent_type": parent_type, "parent_id": parent_id, "name": original})
        return cur.lastrowid

    def get_document_attachments(self, parent_type, parent_id):
        rows = self.conn.execute(
            """SELECT a.id, a.parent_type, a.parent_id, a.original_name, a.stored_path,
                      a.mime_type, a.file_size, a.checksum, a.description, a.created_by,
                      u.full_name, a.created_at
               FROM document_attachments a LEFT JOIN app_users u ON u.id=a.created_by
               WHERE a.parent_type=? AND a.parent_id=? ORDER BY a.id DESC""",
            (parent_type, int(parent_id)),
        ).fetchall()
        keys = ["id", "parent_type", "parent_id", "original_name", "stored_path", "mime_type",
                "file_size", "checksum", "description", "created_by", "created_by_name", "created_at"]
        return [dict(zip(keys, row)) for row in rows]

    def delete_document_attachment(self, attachment_id):
        row = self.conn.execute(
            "SELECT id, parent_type, parent_id, original_name, stored_path FROM document_attachments WHERE id=?",
            (int(attachment_id),),
        ).fetchone()
        if not row:
            return False
        self.conn.execute("DELETE FROM document_attachments WHERE id=?", (int(attachment_id),))
        self.conn.commit()
        try:
            if row[4] and os.path.exists(row[4]):
                os.remove(row[4])
        except Exception:
            pass
        self.log_action("attachment_deleted", "attachment", attachment_id,
                        {"parent_type": row[1], "parent_id": row[2], "name": row[3]})
        return True

    def add_workflow_assignment(self, letter_id, assigned_to_user_id=None, assigned_to_name="",
                                instruction="", due_date=None, priority="عادی"):
        if not self.get_correspondence_letter(letter_id):
            raise ValueError("نامه پیدا نشد.")
        actor_id = self.current_user.get("id") if self.current_user else None
        if assigned_to_user_id:
            user = self.get_user(assigned_to_user_id)
            if not user:
                raise ValueError("کاربر گیرنده ارجاع پیدا نشد.")
            assigned_to_name = user.get("full_name") or user.get("username")
        if not (assigned_to_name or "").strip():
            raise ValueError("گیرنده ارجاع الزامی است.")
        cur = self.conn.execute(
            """INSERT INTO workflow_assignments
               (letter_id, assigned_to_user_id, assigned_to_name, assigned_by_user_id,
                instruction, due_date, priority, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'ارجاع‌شده', CURRENT_TIMESTAMP)""",
            (int(letter_id), assigned_to_user_id, assigned_to_name.strip(), actor_id,
             instruction, due_date, priority),
        )
        self.conn.execute(
            "UPDATE correspondence_letters SET status='ارجاع‌شده', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(letter_id),),
        )
        self.conn.commit()
        letter = self.get_correspondence_letter(letter_id)
        self.log_action("workflow_assigned", "assignment", cur.lastrowid,
                        {"letter_id": letter_id, "assigned_to": assigned_to_name, "due_date": due_date},
                        zone_id=letter.get("zone_id") if letter else None)
        return cur.lastrowid

    def update_workflow_assignment(self, assignment_id, status=None, response_text=None,
                                   due_date=None, priority=None):
        current = self.get_workflow_assignment(assignment_id)
        if not current:
            raise ValueError("ارجاع پیدا نشد.")
        values = {}
        if status is not None:
            values["status"] = status
            if status in {"پاسخ‌داده‌شده", "مختومه"}:
                values["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if response_text is not None:
            values["response_text"] = response_text
        if due_date is not None:
            values["due_date"] = due_date
        if priority is not None:
            values["priority"] = priority
        if values:
            sql = ", ".join(f"{key}=?" for key in values)
            self.conn.execute(
                f"UPDATE workflow_assignments SET {sql}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                list(values.values()) + [int(assignment_id)],
            )
            if status in {"پاسخ‌داده‌شده", "مختومه"}:
                open_count = self.conn.execute(
                    "SELECT COUNT(*) FROM workflow_assignments WHERE letter_id=? AND status NOT IN ('پاسخ‌داده‌شده','مختومه')",
                    (current["letter_id"],),
                ).fetchone()[0]
                if open_count == 0:
                    self.conn.execute(
                        "UPDATE correspondence_letters SET status='پاسخ‌داده‌شده', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                        (current["letter_id"],),
                    )
            self.conn.commit()
        updated = self.get_workflow_assignment(assignment_id)
        self.log_action("workflow_updated", "assignment", assignment_id, before=current, after=updated)
        return updated

    def get_workflow_assignment(self, assignment_id):
        row = self.conn.execute(
            """SELECT w.id, w.letter_id, l.letter_number, l.subject, l.zone_id,
                      w.assigned_to_user_id, w.assigned_to_name, w.assigned_by_user_id,
                      byu.full_name, w.instruction, w.due_date, w.priority, w.status,
                      w.response_text, w.completed_at, w.created_at, w.updated_at
               FROM workflow_assignments w
               JOIN correspondence_letters l ON l.id=w.letter_id
               LEFT JOIN app_users byu ON byu.id=w.assigned_by_user_id
               WHERE w.id=?""", (int(assignment_id),)
        ).fetchone()
        if not row:
            return None
        keys = ["id", "letter_id", "letter_number", "subject", "zone_id", "assigned_to_user_id",
                "assigned_to_name", "assigned_by_user_id", "assigned_by_name", "instruction", "due_date",
                "priority", "status", "response_text", "completed_at", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def get_workflow_assignments(self, letter_id=None, assigned_to_user_id=None, status=None, limit=1000):
        clauses, params = [], []
        if letter_id is not None:
            clauses.append("w.letter_id=?")
            params.append(int(letter_id))
        if assigned_to_user_id is not None:
            clauses.append("w.assigned_to_user_id=?")
            params.append(int(assigned_to_user_id))
        if status:
            clauses.append("w.status=?")
            params.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows = self.conn.execute(
            """SELECT w.id, w.letter_id, l.letter_number, l.subject, l.zone_id,
                      z.name, w.assigned_to_user_id, w.assigned_to_name, w.instruction,
                      w.due_date, w.priority, w.status, w.response_text, w.completed_at,
                      w.created_at, w.updated_at
               FROM workflow_assignments w
               JOIN correspondence_letters l ON l.id=w.letter_id
               LEFT JOIN zones z ON z.id=l.zone_id""" + where +
            " ORDER BY CASE WHEN w.status IN ('پاسخ‌داده‌شده','مختومه') THEN 1 ELSE 0 END, COALESCE(w.due_date,'9999-12-31'), w.id DESC LIMIT ?",
            params,
        ).fetchall()
        keys = ["id", "letter_id", "letter_number", "subject", "zone_id", "zone_name",
                "assigned_to_user_id", "assigned_to_name", "instruction", "due_date", "priority",
                "status", "response_text", "completed_at", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def get_administrative_notifications(self, include_acknowledged=False, days_ahead=3):
        today = datetime.now().date()
        notifications = []
        closed = {"پاسخ‌داده‌شده", "مختومه"}
        for letter in self.get_correspondence_letters(limit=5000):
            if letter.get("status") in closed or not letter.get("due_date"):
                continue
            try:
                due = datetime.strptime(str(letter["due_date"])[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            delta = (due - today).days
            if delta <= days_ahead:
                notifications.append({
                    "key": f"letter:{letter['id']}:{letter['due_date']}",
                    "type": "نامه",
                    "entity_id": letter["id"],
                    "zone_id": letter.get("zone_id"),
                    "title": f"سررسید نامه {letter['letter_number']}",
                    "message": letter.get("subject") or "",
                    "due_date": letter.get("due_date"),
                    "severity": "بحرانی" if delta < 0 else ("فوری" if delta == 0 else "مهم"),
                    "days_remaining": delta,
                })
        for item in self.get_workflow_assignments(limit=5000):
            if item.get("status") in closed or not item.get("due_date"):
                continue
            try:
                due = datetime.strptime(str(item["due_date"])[:10], "%Y-%m-%d").date()
            except Exception:
                continue
            delta = (due - today).days
            if delta <= days_ahead:
                notifications.append({
                    "key": f"assignment:{item['id']}:{item['due_date']}",
                    "type": "ارجاع",
                    "entity_id": item["id"],
                    "zone_id": item.get("zone_id"),
                    "title": f"پیگیری ارجاع نامه {item['letter_number']}",
                    "message": item.get("assigned_to_name") or "",
                    "due_date": item.get("due_date"),
                    "severity": "بحرانی" if delta < 0 else ("فوری" if delta == 0 else "مهم"),
                    "days_remaining": delta,
                })
        if not include_acknowledged and notifications:
            keys = [item["key"] for item in notifications]
            placeholders = ",".join("?" for _ in keys)
            acked = {row[0] for row in self.conn.execute(
                f"SELECT notification_key FROM administrative_notification_acknowledgements WHERE notification_key IN ({placeholders})",
                keys,
            ).fetchall()}
            notifications = [item for item in notifications if item["key"] not in acked]
        severity_order = {"بحرانی": 0, "فوری": 1, "مهم": 2, "عادی": 3}
        return sorted(notifications, key=lambda x: (severity_order.get(x["severity"], 9), x.get("due_date") or ""))

    def acknowledge_administrative_notification(self, notification_key, note=""):
        actor_id = self.current_user.get("id") if self.current_user else None
        self.conn.execute(
            """INSERT INTO administrative_notification_acknowledgements
               (notification_key, acknowledged_by, acknowledged_at, note)
               VALUES (?, ?, CURRENT_TIMESTAMP, ?)
               ON CONFLICT(notification_key) DO UPDATE SET acknowledged_by=excluded.acknowledged_by,
                 acknowledged_at=CURRENT_TIMESTAMP, note=excluded.note""",
            (notification_key, actor_id, note),
        )
        self.conn.commit()
        self.log_action("administrative_notification_acknowledged", "notification", notification_key)

    def export_correspondence_archive(self, output_path, zone_id=None):
        """خروجی ZIP خودکفا شامل فهرست نامه‌ها، ارجاعات و نسخه فایل‌های پیوست."""
        if not output_path:
            raise ValueError("مسیر خروجی مشخص نشده است.")
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        letters = self.get_correspondence_letters(zone_id=zone_id, limit=100000)
        payload = {
            "format": "javanrood-correspondence-archive",
            "version": 1,
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "zone_id": zone_id,
            "letters": [],
        }
        copied_files = 0
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for letter_summary in letters:
                letter = self.get_correspondence_letter(letter_summary["id"]) or letter_summary
                assignments = self.get_workflow_assignments(letter_id=letter_summary["id"], limit=10000)
                attachments = self.get_document_attachments("letter", letter_summary["id"])
                attachment_meta = []
                for attachment in attachments:
                    stored = attachment.get("stored_path")
                    archive_name = None
                    if stored and os.path.isfile(stored):
                        archive_name = f"files/{letter_summary['id']}/{attachment['id']}_{attachment['original_name']}"
                        archive.write(stored, archive_name)
                        copied_files += 1
                    attachment_meta.append({
                        "id": attachment.get("id"),
                        "original_name": attachment.get("original_name"),
                        "mime_type": attachment.get("mime_type"),
                        "file_size": attachment.get("file_size"),
                        "checksum": attachment.get("checksum"),
                        "description": attachment.get("description"),
                        "archive_path": archive_name,
                    })
                payload["letters"].append({
                    "letter": letter,
                    "assignments": assignments,
                    "attachments": attachment_meta,
                })
            archive.writestr("correspondence.json", json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        self.log_action("correspondence_archive_exported", "archive", os.path.basename(output_path),
                        {"zone_id": zone_id, "letters": len(letters), "files": copied_files})
        return {"path": output_path, "letters": len(letters), "files": copied_files}

    def get_correspondence_stats(self):
        cur = self.conn.cursor()
        return {
            "letters_total": cur.execute("SELECT COUNT(*) FROM correspondence_letters").fetchone()[0],
            "letters_incoming": cur.execute("SELECT COUNT(*) FROM correspondence_letters WHERE direction='وارده'").fetchone()[0],
            "letters_outgoing": cur.execute("SELECT COUNT(*) FROM correspondence_letters WHERE direction='صادره'").fetchone()[0],
            "open_assignments": cur.execute("SELECT COUNT(*) FROM workflow_assignments WHERE status NOT IN ('پاسخ‌داده‌شده','مختومه')").fetchone()[0],
            "attachments_count": cur.execute("SELECT COUNT(*) FROM document_attachments").fetchone()[0],
            "administrative_alerts": len(self.get_administrative_notifications()),
        }

    # ---------------- Global Search ----------------
    # ---------------- Management Calendar & Notifications v6.6 ----------------
    CALENDAR_EVENT_CATEGORIES = ["جلسه", "بازدید میدانی", "پیگیری", "گزارش", "مکاتبه", "پروژه", "سایر"]
    CALENDAR_EVENT_STATUSES = ["برنامه‌ریزی‌شده", "در حال انجام", "انجام‌شده", "لغوشده"]
    CALENDAR_PRIORITIES = ["عادی", "مهم", "فوری", "بحرانی"]

    @staticmethod
    def _normalize_iso_date(value, required=False):
        """پذیرش تاریخ شمسی کاربر و نگهداری استاندارد میلادی در دیتابیس."""
        return jalali_to_iso(value, required=required)

    @staticmethod
    def _date_object(value):
        try:
            normalized = jalali_to_iso(value, required=True)
            return datetime.strptime(normalized, "%Y-%m-%d").date()
        except Exception:
            return None

    def add_management_calendar_event(self, title, start_date, zone_id=None, category="جلسه",
                                      end_date=None, start_time=None, all_day=True,
                                      responsible_user_id=None, responsible_person="", location="",
                                      description="", status="برنامه‌ریزی‌شده", priority="عادی",
                                      linked_entity_type=None, linked_entity_id=None, reminder_days=2):
        title = (title or "").strip()
        if not title:
            raise ValueError("عنوان رویداد الزامی است.")
        start_date = self._normalize_iso_date(start_date, required=True)
        end_date = self._normalize_iso_date(end_date) or start_date
        if end_date < start_date:
            raise ValueError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
        if category not in self.CALENDAR_EVENT_CATEGORIES:
            category = "سایر"
        if status not in self.CALENDAR_EVENT_STATUSES:
            status = "برنامه‌ریزی‌شده"
        if priority not in self.CALENDAR_PRIORITIES:
            priority = "عادی"
        reminder_days = max(0, min(365, int(reminder_days or 0)))
        actor_id = self.current_user.get("id") if self.current_user else None
        if responsible_user_id:
            user = self.get_user(responsible_user_id)
            if not user:
                raise ValueError("کاربر مسئول پیدا نشد.")
            responsible_person = user.get("full_name") or user.get("username")
        cur = self.conn.execute(
            """INSERT INTO management_calendar_events
               (zone_id, title, category, start_date, end_date, start_time, all_day,
                responsible_user_id, responsible_person, location, description, status,
                priority, linked_entity_type, linked_entity_id, reminder_days, created_by, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (zone_id, title, category, start_date, end_date, start_time, 1 if all_day else 0,
             responsible_user_id, responsible_person, location, description, status, priority,
             linked_entity_type, str(linked_entity_id) if linked_entity_id is not None else None,
             reminder_days, actor_id),
        )
        self.conn.commit()
        event_id = cur.lastrowid
        self.log_action("calendar_event_added", "calendar_event", event_id,
                        {"zone_id": zone_id, "date": start_date, "title": title}, zone_id=zone_id)
        return event_id

    def get_management_calendar_event(self, event_id):
        rows = self.get_management_calendar_events()
        return next((row for row in rows if row["id"] == int(event_id)), None)

    def get_management_calendar_events(self, date_from=None, date_to=None, zone_id=None,
                                       responsible_user_id=None, include_closed=True):
        clauses, params = [], []
        if date_from:
            clauses.append("e.end_date>=?")
            params.append(self._normalize_iso_date(date_from, required=True))
        if date_to:
            clauses.append("e.start_date<=?")
            params.append(self._normalize_iso_date(date_to, required=True))
        if zone_id is not None:
            clauses.append("e.zone_id=?")
            params.append(int(zone_id))
        if responsible_user_id is not None:
            clauses.append("e.responsible_user_id=?")
            params.append(int(responsible_user_id))
        if not include_closed:
            clauses.append("e.status NOT IN ('انجام‌شده','لغوشده')")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.conn.execute(
            """SELECT e.id, e.zone_id, z.name, e.title, e.category, e.start_date, e.end_date,
                      e.start_time, e.all_day, e.responsible_user_id, e.responsible_person,
                      u.full_name, e.location, e.description, e.status, e.priority,
                      e.linked_entity_type, e.linked_entity_id, e.reminder_days,
                      e.created_by, cu.full_name, e.created_at, e.updated_at
               FROM management_calendar_events e
               LEFT JOIN zones z ON z.id=e.zone_id
               LEFT JOIN app_users u ON u.id=e.responsible_user_id
               LEFT JOIN app_users cu ON cu.id=e.created_by""" + where +
            " ORDER BY e.start_date, COALESCE(e.start_time,'23:59'), e.id",
            params,
        ).fetchall()
        keys = ["id", "zone_id", "zone_name", "title", "category", "start_date", "end_date",
                "start_time", "all_day", "responsible_user_id", "responsible_person",
                "responsible_user_name", "location", "description", "status", "priority",
                "linked_entity_type", "linked_entity_id", "reminder_days", "created_by",
                "created_by_name", "created_at", "updated_at"]
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            item["all_day"] = bool(item["all_day"])
            item["responsible_display"] = item.get("responsible_user_name") or item.get("responsible_person") or "—"
            result.append(item)
        return result

    def update_management_calendar_event(self, event_id, **data):
        current = self.get_management_calendar_event(event_id)
        if not current:
            raise ValueError("رویداد پیدا نشد.")
        editable = ["zone_id", "title", "category", "start_date", "end_date", "start_time",
                    "all_day", "responsible_user_id", "responsible_person", "location",
                    "description", "status", "priority", "linked_entity_type",
                    "linked_entity_id", "reminder_days"]
        merged = {key: data.get(key, current.get(key)) for key in editable}
        merged["title"] = (merged.get("title") or "").strip()
        if not merged["title"]:
            raise ValueError("عنوان رویداد الزامی است.")
        merged["start_date"] = self._normalize_iso_date(merged.get("start_date"), required=True)
        merged["end_date"] = self._normalize_iso_date(merged.get("end_date")) or merged["start_date"]
        if merged["end_date"] < merged["start_date"]:
            raise ValueError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.")
        merged["all_day"] = 1 if merged.get("all_day") else 0
        merged["reminder_days"] = max(0, min(365, int(merged.get("reminder_days") or 0)))
        if merged.get("responsible_user_id"):
            user = self.get_user(merged["responsible_user_id"])
            if not user:
                raise ValueError("کاربر مسئول پیدا نشد.")
            merged["responsible_person"] = user.get("full_name") or user.get("username")
        sets = ", ".join(f"{key}=?" for key in editable)
        self.conn.execute(
            f"UPDATE management_calendar_events SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [merged[key] for key in editable] + [int(event_id)],
        )
        self.conn.commit()
        updated = self.get_management_calendar_event(event_id)
        self.log_action("calendar_event_updated", "calendar_event", event_id,
                        zone_id=updated.get("zone_id"), before=current, after=updated)
        return updated

    def delete_management_calendar_event(self, event_id):
        current = self.get_management_calendar_event(event_id)
        if not current:
            return False
        self.conn.execute("DELETE FROM management_calendar_events WHERE id=?", (int(event_id),))
        self.conn.commit()
        self.log_action("calendar_event_deleted", "calendar_event", event_id,
                        {"title": current.get("title")}, zone_id=current.get("zone_id"))
        return True

    def get_deadline_calendar_items(self, date_from=None, date_to=None, zone_id=None,
                                    user_id=None, include_closed=False):
        """تجمیع تمام مهلت‌ها و رویدادها در یک ساختار استاندارد تقویم."""
        start = self._date_object(date_from) if date_from else None
        end = self._date_object(date_to) if date_to else None
        today = datetime.now().date()
        items = []

        def add_item(source_type, source_id, zone, zone_name, title, category, date_value,
                     status, priority="عادی", responsible="", responsible_user_id=None,
                     time_value=None, location="", reminder_days=2, manual=False, message=""):
            due = self._date_object(date_value)
            if not due:
                return
            if start and due < start:
                return
            if end and due > end:
                return
            if zone_id is not None and int(zone or -1) != int(zone_id):
                return
            if user_id is not None and responsible_user_id not in (None, int(user_id)):
                return
            delta = (due - today).days
            items.append({
                "source_type": source_type, "source_id": source_id, "zone_id": zone,
                "zone_name": zone_name or "—", "title": title or "بدون عنوان",
                "category": category, "date": due.strftime("%Y-%m-%d"), "time": time_value,
                "status": status or "—", "priority": priority or "عادی",
                "responsible": responsible or "—", "responsible_user_id": responsible_user_id,
                "location": location or "", "reminder_days": int(reminder_days or 0),
                "is_manual": bool(manual), "is_overdue": delta < 0, "days_remaining": delta,
                "message": message or "",
            })

        closed_actions = {"تکمیل‌شده", "ارزیابی نتیجه"}
        for row in self.conn.execute(
            """SELECT a.id,a.zone_id,z.name,a.title,a.planned_end,a.status,a.responsible_person,
                      a.responsible_office,a.progress_percent
               FROM neighborhood_actions a LEFT JOIN zones z ON z.id=a.zone_id
               WHERE a.planned_end IS NOT NULL AND a.planned_end<>''"""
        ).fetchall():
            if include_closed or row[5] not in closed_actions:
                add_item("action", row[0], row[1], row[2], row[3], "اقدام اجرایی", row[4], row[5],
                         "مهم" if int(row[8] or 0) < 75 else "عادی", row[6] or row[7] or "",
                         message=f"پیشرفت: {int(row[8] or 0)}٪")

        for row in self.conn.execute(
            """SELECT i.id,i.zone_id,z.name,i.title,i.due_date,i.status,i.priority_level,i.related_office
               FROM neighborhood_issues i LEFT JOIN zones z ON z.id=i.zone_id
               WHERE i.due_date IS NOT NULL AND i.due_date<>''"""
        ).fetchall():
            if include_closed or row[5] not in {"مختومه", "انجام‌شده"}:
                add_item("issue", row[0], row[1], row[2], row[3], "مسئله محله", row[4], row[5], row[6], row[7])

        for row in self.conn.execute(
            """SELECT r.id,r.zone_id,z.name,r.title,r.due_date,r.status,r.responsible_person,r.responsible_office
               FROM neighborhood_resolutions r LEFT JOIN zones z ON z.id=r.zone_id
               WHERE r.due_date IS NOT NULL AND r.due_date<>''"""
        ).fetchall():
            if include_closed or row[5] not in {"انجام‌شده", "لغوشده"}:
                add_item("resolution", row[0], row[1], row[2], row[3], "مصوبه", row[4], row[5], "مهم", row[6] or row[7])

        for row in self.conn.execute(
            """SELECT l.id,l.zone_id,z.name,l.letter_number || ' — ' || l.subject,l.due_date,l.status,
                      l.priority,l.recipient
               FROM correspondence_letters l LEFT JOIN zones z ON z.id=l.zone_id
               WHERE l.due_date IS NOT NULL AND l.due_date<>''"""
        ).fetchall():
            if include_closed or row[5] not in {"پاسخ‌داده‌شده", "مختومه"}:
                add_item("letter", row[0], row[1], row[2], row[3], "نامه اداری", row[4], row[5], row[6], row[7])

        for row in self.conn.execute(
            """SELECT w.id,l.zone_id,z.name,'ارجاع ' || l.letter_number || ' — ' || l.subject,
                      w.due_date,w.status,w.priority,w.assigned_to_name,w.assigned_to_user_id
               FROM workflow_assignments w JOIN correspondence_letters l ON l.id=w.letter_id
               LEFT JOIN zones z ON z.id=l.zone_id
               WHERE w.due_date IS NOT NULL AND w.due_date<>''"""
        ).fetchall():
            if include_closed or row[5] not in {"پاسخ‌داده‌شده", "مختومه"}:
                add_item("assignment", row[0], row[1], row[2], row[3], "ارجاع اداری", row[4], row[5],
                         row[6], row[7], row[8])

        for row in self.conn.execute(
            """SELECT a.id,a.zone_id,z.name,a.title,a.due_date,a.status,
                      s.approver_user_id,COALESCE(u.full_name,s.approver_name,s.approver_role)
               FROM approval_requests a
               LEFT JOIN approval_steps s ON s.approval_id=a.id AND s.step_order=a.current_step
               LEFT JOIN app_users u ON u.id=s.approver_user_id
               LEFT JOIN zones z ON z.id=a.zone_id
               WHERE a.due_date IS NOT NULL AND a.due_date<>''"""
        ).fetchall():
            if include_closed or row[5] == "در انتظار تأیید":
                add_item("approval", row[0], row[1], row[2], row[3], "گردش تأیید", row[4], row[5],
                         "فوری", row[7], row[6])

        for row in self.conn.execute(
            """SELECT m.id,m.zone_id,z.name,m.title,m.meeting_date,m.status,m.start_time,m.place_name
               FROM neighborhood_meetings m LEFT JOIN zones z ON z.id=m.zone_id
               WHERE m.meeting_date IS NOT NULL AND m.meeting_date<>''"""
        ).fetchall():
            add_item("meeting", row[0], row[1], row[2], row[3], "جلسه", row[4], row[5],
                     "عادی", "", None, row[6], row[7], 1, False)

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
            if project.get("end_date") and (include_closed or project.get("status") not in {"تکمیل‌شده", "لغوشده"}):
                add_item("project", project["id"], project.get("zone_id"), project.get("zone_name"),
                         project.get("title"), "پروژه", project.get("end_date"), project.get("status"),
                         project.get("priority"), project.get("project_manager") or project.get("responsible_agency"),
                         message=f"پیشرفت واقعی: {float(project.get('actual_progress') or 0):.0f}٪")
        for milestone in self.get_project_milestones():
            if include_closed or milestone.get("status") not in {"تکمیل‌شده", "لغوشده"}:
                add_item("project_milestone", milestone["id"], milestone.get("zone_id"), milestone.get("zone_name"),
                         milestone.get("title"), "نقطه عطف پروژه", milestone.get("due_date"), milestone.get("status"),
                         "مهم", milestone.get("project_title") or "")
        for risk in self.get_project_risks(zone_id=zone_id, open_only=True):
            if risk.get("review_date"):
                priority = "بحرانی" if int(risk.get("risk_score") or 0) >= 20 else "فوری" if int(risk.get("risk_score") or 0) >= 12 else "مهم"
                add_item("project_risk", risk["id"], risk.get("zone_id"), risk.get("zone_name"),
                         risk.get("title"), "بازبینی ریسک", risk.get("review_date"), risk.get("status"),
                         priority, risk.get("owner") or "", message=f"امتیاز ریسک: {risk.get('risk_score')}")

        for contract in self.get_contracts(zone_id=zone_id):
            if contract.get("end_date") and (include_closed or contract.get("status") not in {"مختومه", "تسویه", "فسخ‌شده"}):
                add_item("contract", contract["id"], contract.get("zone_id"), contract.get("zone_name"),
                         f"{contract.get('contract_no')} — {contract.get('title')}", "قرارداد", contract.get("end_date"),
                         contract.get("status"), "مهم", contract.get("contractor_name") or "",
                         message=f"پرداخت: {float(contract.get('payment_percent') or 0):.0f}٪")

        for event in self.get_management_calendar_events(date_from, date_to, zone_id, include_closed=include_closed):
            if user_id is not None and event.get("responsible_user_id") not in (None, int(user_id)):
                continue
            add_item("calendar_event", event["id"], event.get("zone_id"), event.get("zone_name"),
                     event.get("title"), event.get("category"), event.get("start_date"),
                     event.get("status"), event.get("priority"), event.get("responsible_display"),
                     event.get("responsible_user_id"), event.get("start_time"), event.get("location"),
                     event.get("reminder_days"), True, event.get("description"))

        priority_rank = {"بحرانی": 0, "فوری": 1, "مهم": 2, "عادی": 3}
        items.sort(key=lambda x: (x["date"], x.get("time") or "23:59", priority_rank.get(x.get("priority"), 4), x["title"]))
        return items

    def refresh_in_app_notifications(self, reference_date=None, days_ahead=7):
        today = self._date_object(reference_date) if reference_date else datetime.now().date()
        if not today:
            today = datetime.now().date()
        items = self.get_deadline_calendar_items("1900-01-01", (today + timedelta(days=max(1, int(days_ahead)))).strftime("%Y-%m-%d"))
        active_keys = []
        for item in items:
            delta = (self._date_object(item["date"]) - today).days
            reminder_limit = item.get("reminder_days", days_ahead) if item.get("is_manual") else int(days_ahead)
            if delta > reminder_limit:
                continue
            if delta < 0:
                severity = "بحرانی"
                title_prefix = "تأخیر"
            elif delta == 0:
                severity = "فوری"
                title_prefix = "سررسید امروز"
            elif delta <= 2:
                severity = "مهم"
                title_prefix = "سررسید نزدیک"
            else:
                severity = "اطلاع"
                title_prefix = "یادآوری"
            assigned_user_id = item.get("responsible_user_id")
            if assigned_user_id is not None:
                target_user_ids = [int(assigned_user_id)]
            else:
                target_user_ids = [int(user["id"]) for user in self.list_users(include_inactive=False)] or [None]
            message = item.get("message") or f"بلوک: {item.get('zone_name') or '—'} — مسئول: {item.get('responsible') or '—'}"
            for target_user_id in target_user_ids:
                unique_key = (
                    f"deadline:{item['source_type']}:{item['source_id']}:{item['date']}:"
                    f"u{target_user_id if target_user_id is not None else 0}"
                )
                active_keys.append(unique_key)
                self.conn.execute(
                    """INSERT INTO in_app_notifications
                       (unique_key,user_id,zone_id,notification_type,title,message,severity,
                        source_type,source_id,due_date,is_read,is_dismissed,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,0,0,CURRENT_TIMESTAMP)
                       ON CONFLICT(unique_key) DO UPDATE SET
                         user_id=excluded.user_id, zone_id=excluded.zone_id, title=excluded.title,
                         message=excluded.message, severity=excluded.severity, due_date=excluded.due_date,
                         updated_at=CURRENT_TIMESTAMP""",
                    (unique_key, target_user_id, item.get("zone_id"), "سررسید خودکار",
                     f"{title_prefix}: {item['title']}", message, severity, item["source_type"],
                     str(item["source_id"]), item["date"]),
                )
        if active_keys:
            marks = ",".join("?" for _ in active_keys)
            self.conn.execute(
                f"UPDATE in_app_notifications SET is_dismissed=1, updated_at=CURRENT_TIMESTAMP "
                f"WHERE notification_type='سررسید خودکار' AND unique_key NOT IN ({marks})",
                active_keys,
            )
        else:
            self.conn.execute("UPDATE in_app_notifications SET is_dismissed=1 WHERE notification_type='سررسید خودکار'")
        self.conn.commit()
        return len(active_keys)

    def get_in_app_notifications(self, user_id=None, unread_only=False, include_dismissed=False, limit=500):
        clauses, params = [], []
        if user_id is not None:
            clauses.append("(n.user_id IS NULL OR n.user_id=?)")
            params.append(int(user_id))
        if unread_only:
            clauses.append("n.is_read=0")
        if not include_dismissed:
            clauses.append("n.is_dismissed=0")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows = self.conn.execute(
            """SELECT n.id,n.unique_key,n.user_id,n.zone_id,z.name,n.notification_type,n.title,
                      n.message,n.severity,n.source_type,n.source_id,n.due_date,n.is_read,
                      n.read_at,n.is_dismissed,n.created_at,n.updated_at
               FROM in_app_notifications n LEFT JOIN zones z ON z.id=n.zone_id""" + where +
            " ORDER BY CASE n.severity WHEN 'بحرانی' THEN 0 WHEN 'فوری' THEN 1 WHEN 'مهم' THEN 2 ELSE 3 END, "
            "COALESCE(n.due_date,'9999-12-31'), n.id DESC LIMIT ?",
            params,
        ).fetchall()
        keys = ["id", "unique_key", "user_id", "zone_id", "zone_name", "notification_type",
                "title", "message", "severity", "source_type", "source_id", "due_date",
                "is_read", "read_at", "is_dismissed", "created_at", "updated_at"]
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            item["is_read"] = bool(item["is_read"])
            item["is_dismissed"] = bool(item["is_dismissed"])
            result.append(item)
        return result

    def mark_notification_read(self, notification_id, is_read=True):
        self.conn.execute(
            "UPDATE in_app_notifications SET is_read=?, read_at=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (1 if is_read else 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_read else None, int(notification_id)),
        )
        self.conn.commit()

    def mark_all_notifications_read(self, user_id=None):
        if user_id is None:
            self.conn.execute(
                "UPDATE in_app_notifications SET is_read=1, read_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE is_dismissed=0"
            )
        else:
            self.conn.execute(
                """UPDATE in_app_notifications SET is_read=1, read_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                   WHERE is_dismissed=0 AND (user_id IS NULL OR user_id=?)""", (int(user_id),)
            )
        self.conn.commit()

    def dismiss_notification(self, notification_id):
        self.conn.execute(
            "UPDATE in_app_notifications SET is_dismissed=1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(notification_id),),
        )
        self.conn.commit()

    def get_management_period_brief(self, date_from, date_to, zone_id=None):
        date_from = self._normalize_iso_date(date_from, required=True)
        date_to = self._normalize_iso_date(date_to, required=True)
        if date_to < date_from:
            raise ValueError("تاریخ پایان قبل از تاریخ شروع است.")
        zone_clause = " AND zone_id=?" if zone_id is not None else ""
        zone_params = [int(zone_id)] if zone_id is not None else []

        def count(table, date_column, extra="", params=()):
            sql = f"SELECT COUNT(*) FROM {table} WHERE SUBSTR({date_column},1,10) BETWEEN ? AND ?{zone_clause}{extra}"
            return self.conn.execute(sql, [date_from, date_to] + zone_params + list(params)).fetchone()[0]

        summary = {
            "date_from": date_from, "date_to": date_to, "zone_id": zone_id,
            "issues_created": count("neighborhood_issues", "created_at"),
            "actions_created": count("neighborhood_actions", "created_at"),
            "actions_completed": count("neighborhood_actions", "updated_at", " AND status='تکمیل‌شده'"),
            "meetings_held": count("neighborhood_meetings", "meeting_date"),
            "field_visits": count("field_visits", "visit_date"),
            "citizen_requests": count("citizen_requests", "received_at"),
            "letters_registered": count("correspondence_letters", "created_at"),
            "approvals_completed": count("approval_requests", "completed_at", " AND status IN ('تأییدشده','ردشده')"),
            "calendar_events": count("management_calendar_events", "start_date"),
        }
        budget_sql = "SELECT COALESCE(SUM(spent_amount),0) FROM neighborhood_budgets WHERE SUBSTR(updated_at,1,10) BETWEEN ? AND ?"
        params = [date_from, date_to]
        if zone_id is not None:
            budget_sql += " AND zone_id=?"
            params.append(int(zone_id))
        summary["spent_amount"] = float(self.conn.execute(budget_sql, params).fetchone()[0] or 0)
        items = self.get_deadline_calendar_items(date_from, date_to, zone_id=zone_id)
        summary["deadlines_total"] = len(items)
        summary["overdue_deadlines"] = sum(1 for item in items if item.get("is_overdue"))
        summary["deadlines"] = items
        return summary

    # ---------------- Production / schema health ----------------
    def get_schema_version(self):
        try:
            return int(self.conn.execute("PRAGMA user_version").fetchone()[0] or 0)
        except Exception:
            return 0

    def get_migration_history(self):
        try:
            rows = self.conn.execute(
                "SELECT version, description, applied_at FROM schema_migrations ORDER BY version DESC"
            ).fetchall()
            return [{"version": r[0], "description": r[1], "applied_at": r[2]} for r in rows]
        except Exception:
            return []

    def database_health(self):
        integrity = self.conn.execute("PRAGMA integrity_check").fetchone()
        fk_rows = self.conn.execute("PRAGMA foreign_key_check").fetchall()
        quick = self.conn.execute("PRAGMA quick_check").fetchone()
        return {
            "integrity_ok": bool(integrity and integrity[0] == "ok"),
            "integrity_message": integrity[0] if integrity else "no result",
            "quick_ok": bool(quick and quick[0] == "ok"),
            "foreign_key_errors": len(fk_rows),
            "schema_version": self.get_schema_version(),
            "database_size": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
        }

    # ---------------- Zone Meeting Place (محل برگزاری جلسات شورا) ----------------
    def set_zone_meeting_place(self, zone_id, place_id, place_name, exact_address, lat, lon,
                               source_type="place", source_id=None):
        source_type = source_type or "place"
        if source_id is None:
            source_id = str(place_id) if place_id is not None else None
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO zone_meeting_places
               (zone_id, place_id, place_name, exact_address, lat, lon, source_type, source_id, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(zone_id) DO UPDATE SET
                 place_id=excluded.place_id,
                 place_name=excluded.place_name,
                 exact_address=excluded.exact_address,
                 lat=excluded.lat,
                 lon=excluded.lon,
                 source_type=excluded.source_type,
                 source_id=excluded.source_id,
                 updated_at=CURRENT_TIMESTAMP""",
            (zone_id, place_id, place_name, exact_address, lat, lon, source_type, source_id)
        )
        self.conn.commit()
        self.log_action(
            "meeting_place_changed", "zone", zone_id,
            {"name": place_name, "source_type": source_type, "source_id": source_id}
        )
        self._refresh_zone_snapshot_safe(zone_id, force=True)

    def get_zone_meeting_place(self, zone_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT place_id, place_name, exact_address, lat, lon, source_type, source_id "
            "FROM zone_meeting_places WHERE zone_id=?",
            (zone_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "place_id": row[0], "place_name": row[1], "exact_address": row[2],
            "lat": row[3], "lon": row[4], "source_type": row[5] or "place",
            "source_id": row[6] if row[6] is not None else (str(row[0]) if row[0] is not None else None),
        }

    # ---------------- کمیته‌های شش‌گانه محله‌محور ----------------
    def _seed_county_steering_structure(self):
        defaults = [
            ("governor", "مسئول کمیته", "فرمانداری شهرستان جوانرود"),
            ("mayor", "دبیر کمیته", "شهرداری جوانرود"),
            ("propagation", "عضو", "اداره تبلیغات اسلامی شهرستان"),
            ("basij", "عضو", "ناحیه مقاومت بسیج"),
            ("ngo_1", "نماینده تشکل مردمی اول", "تشکل‌های مردمی شهرستان"),
            ("ngo_2", "نماینده تشکل مردمی دوم", "تشکل‌های مردمی شهرستان"),
        ]
        for slot, role, agency in defaults:
            self.conn.execute(
                """INSERT OR IGNORE INTO county_steering_members
                   (member_slot, role_title, agency_name, status, updated_at)
                   VALUES (?, ?, ?, 'فعال', CURRENT_TIMESTAMP)""",
                (slot, role, agency),
            )
        self.conn.commit()

    def get_county_steering_members(self):
        rows = self.conn.execute(
            """SELECT id, member_slot, role_title, agency_name, person_name, mobile, decree_no,
                      decree_date, status, notes, created_at, updated_at
               FROM county_steering_members
               ORDER BY CASE member_slot WHEN 'governor' THEN 1 WHEN 'mayor' THEN 2
                        WHEN 'propagation' THEN 3 WHEN 'basij' THEN 4 WHEN 'ngo_1' THEN 5 ELSE 6 END"""
        ).fetchall()
        keys = ["id", "member_slot", "role_title", "agency_name", "person_name", "mobile", "decree_no",
                "decree_date", "status", "notes", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def update_county_steering_member(self, member_id, **data):
        current = next((x for x in self.get_county_steering_members() if x["id"] == member_id), None)
        if not current:
            return False
        fields = ["person_name", "mobile", "decree_no", "decree_date", "status", "notes"]
        values = [data.get(key, current.get(key)) for key in fields]
        self.conn.execute(
            "UPDATE county_steering_members SET " + ", ".join(f"{key}=?" for key in fields) +
            ", updated_at=CURRENT_TIMESTAMP WHERE id=?", values + [member_id])
        self.conn.commit()
        self.log_action("county_steering_member_updated", "county_steering_member", member_id,
                        {"role": current.get("role_title"), "person_name": values[0]})
        return True

    def _seed_committee_agencies(self):
        for name in DEFAULT_COMMITTEE_AGENCIES:
            self.conn.execute(
                """INSERT OR IGNORE INTO management_agencies
                   (name, category, service_scope, is_active, notes, updated_at)
                   VALUES (?, 'دستگاه همکار کمیته‌های محله‌محور', 'همکاری در کمیته‌های تخصصی محله', 1,
                           'افزوده‌شده از ساختار کمیته‌های شش‌گانه', CURRENT_TIMESTAMP)""",
                (name,),
            )
        self.conn.commit()

    def _restore_six_committee_structure(self):
        """ساختار تک‌کمیته‌ای نسخه‌های ۷.۱.۱۶ و ۷.۱.۱۷ را بدون حذف داده به شش کمیته بازمی‌گرداند.

        چون داده‌های ادغام‌شده در نسخه تک‌کمیته‌ای دیگر منشأ تخصصی قابل اتکا ندارند،
        پرونده کمیته راهبردی قبلی به کمیته عمران منتقل می‌شود و پنج کمیته دیگر ایجاد می‌شوند.
        """
        infrastructure = DEFAULT_NEIGHBORHOOD_COMMITTEES[0]
        zones = self.conn.execute("SELECT id FROM zones ORDER BY id").fetchall()
        for (zone_id,) in zones:
            strategic = self.conn.execute(
                """SELECT id, chair_name, chair_mobile, secretary_name, secretary_mobile,
                          decree_no, decree_date, start_date, end_date, status, notes
                   FROM neighborhood_committees
                   WHERE zone_id=? AND committee_code='strategic' LIMIT 1""",
                (zone_id,),
            ).fetchone()
            if not strategic:
                continue

            strategic_id = strategic[0]
            target = self.conn.execute(
                "SELECT id FROM neighborhood_committees WHERE zone_id=? AND committee_code='infrastructure' LIMIT 1",
                (zone_id,),
            ).fetchone()

            migration_note = "انتقال خودکار اطلاعات کمیته راهبردی نسخه قبلی به کمیته عمران در نسخه ۷.۱.۱۸"
            if target is None:
                existing_notes = (strategic[10] or "").strip()
                notes = migration_note if not existing_notes else existing_notes + "\n" + migration_note
                self.conn.execute(
                    """UPDATE neighborhood_committees
                       SET committee_code='infrastructure', title=?, recommended_agencies=?, notes=?,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (infrastructure["title"], infrastructure["recommended_agencies"], notes, strategic_id),
                )
                continue

            target_id = target[0]
            # انتقال وابستگی‌ها به رکورد کمیته عمران موجود
            self.conn.execute(
                "UPDATE committee_members SET committee_id=?, updated_at=CURRENT_TIMESTAMP WHERE committee_id=?",
                (target_id, strategic_id),
            )
            self.conn.execute(
                "UPDATE committee_meetings SET committee_id=?, updated_at=CURRENT_TIMESTAMP WHERE committee_id=?",
                (target_id, strategic_id),
            )
            self.conn.execute(
                "UPDATE committee_resolutions SET committee_id=?, updated_at=CURRENT_TIMESTAMP WHERE committee_id=?",
                (target_id, strategic_id),
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO committee_issue_links(committee_id, issue_id) "
                "SELECT ?, issue_id FROM committee_issue_links WHERE committee_id=?",
                (target_id, strategic_id),
            )
            self.conn.execute("DELETE FROM committee_issue_links WHERE committee_id=?", (strategic_id,))
            self.conn.execute(
                "INSERT OR IGNORE INTO committee_action_links(committee_id, action_id) "
                "SELECT ?, action_id FROM committee_action_links WHERE committee_id=?",
                (target_id, strategic_id),
            )
            self.conn.execute("DELETE FROM committee_action_links WHERE committee_id=?", (strategic_id,))

            current = self.conn.execute(
                """SELECT chair_name, chair_mobile, secretary_name, secretary_mobile, decree_no,
                          decree_date, start_date, end_date, status, notes
                   FROM neighborhood_committees WHERE id=?""",
                (target_id,),
            ).fetchone()
            merged = []
            for idx in range(9):
                merged.append(current[idx] or strategic[idx + 1])
            notes_parts = [part.strip() for part in (current[9], strategic[10], migration_note) if part and part.strip()]
            merged_notes = "\n".join(dict.fromkeys(notes_parts))
            self.conn.execute(
                """UPDATE neighborhood_committees
                   SET title=?, recommended_agencies=?, chair_name=?, chair_mobile=?, secretary_name=?,
                       secretary_mobile=?, decree_no=?, decree_date=?, start_date=?, end_date=?, status=?, notes=?,
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (infrastructure["title"], infrastructure["recommended_agencies"],
                 merged[0], merged[1], merged[2], merged[3], merged[4], merged[5], merged[6], merged[7],
                 merged[8] or "فعال", merged_notes, target_id),
            )
            self.conn.execute("DELETE FROM neighborhood_committees WHERE id=?", (strategic_id,))
        self.conn.commit()

    def _ensure_default_committees_for_all_zones(self):
        for (zone_id,) in self.conn.execute("SELECT id FROM zones").fetchall():
            self.ensure_zone_committees(zone_id, commit=False)
        self.conn.commit()

    def ensure_zone_committees(self, zone_id, commit=True):
        zone_id = int(zone_id)
        for item in DEFAULT_NEIGHBORHOOD_COMMITTEES:
            self.conn.execute(
                """INSERT OR IGNORE INTO neighborhood_committees
                   (zone_id, committee_code, title, recommended_agencies, status, updated_at)
                   VALUES (?, ?, ?, ?, 'فعال', CURRENT_TIMESTAMP)""",
                (zone_id, item["code"], item["title"], item["recommended_agencies"]),
            )
        if commit:
            self.conn.commit()
        return self.get_zone_committees(zone_id, ensure=False)

    def get_zone_committees(self, zone_id, ensure=True):
        if ensure:
            self.ensure_zone_committees(zone_id, commit=False)
        rows = self.conn.execute(
            """SELECT id, zone_id, committee_code, title, recommended_agencies, chair_name, chair_mobile,
                      secretary_name, secretary_mobile, decree_no, decree_date, start_date, end_date,
                      status, notes, created_at, updated_at
               FROM neighborhood_committees WHERE zone_id=?
               ORDER BY CASE committee_code
                   WHEN 'infrastructure' THEN 1
                   WHEN 'health' THEN 2
                   WHEN 'sports' THEN 3
                   WHEN 'security' THEN 4
                   WHEN 'support' THEN 5
                   WHEN 'culture' THEN 6
                   ELSE 99 END, id""",
            (zone_id,),
        ).fetchall()
        keys = ["id", "zone_id", "committee_code", "title", "recommended_agencies", "chair_name", "chair_mobile",
                "secretary_name", "secretary_mobile", "decree_no", "decree_date", "start_date", "end_date",
                "status", "notes", "created_at", "updated_at"]
        result = []
        for row in rows:
            item = dict(zip(keys, row))
            cid = item["id"]
            item["members_count"] = self.conn.execute(
                "SELECT COUNT(*) FROM committee_members WHERE committee_id=? AND status='فعال'", (cid,)
            ).fetchone()[0]
            item["meetings_count"] = self.conn.execute(
                "SELECT COUNT(*) FROM committee_meetings WHERE committee_id=?", (cid,)
            ).fetchone()[0]
            item["pending_resolutions"] = self.conn.execute(
                "SELECT COUNT(*) FROM committee_resolutions WHERE committee_id=? AND status NOT IN ('انجام‌شده','لغوشده')", (cid,)
            ).fetchone()[0]
            result.append(item)
        if ensure:
            self.conn.commit()
        return result

    def get_committee(self, committee_id):
        for zone in self.get_zones():
            item = next((x for x in self.get_zone_committees(zone["id"]) if x["id"] == committee_id), None)
            if item:
                return item
        return None

    def update_committee(self, committee_id, **data):
        current = self.get_committee(committee_id)
        if not current:
            return False
        fields = ["chair_name", "chair_mobile", "secretary_name", "secretary_mobile", "decree_no",
                  "decree_date", "start_date", "end_date", "status", "notes"]
        values = [data.get(key, current.get(key)) for key in fields]
        self.conn.execute(
            "UPDATE neighborhood_committees SET " + ", ".join(f"{key}=?" for key in fields) +
            ", updated_at=CURRENT_TIMESTAMP WHERE id=?",
            values + [committee_id],
        )
        self.conn.commit()
        self.log_action("committee_updated", "committee", committee_id, {"title": current.get("title")})
        return True

    def add_committee_member(self, committee_id, person_name, **data):
        person_name = (person_name or "").strip()
        if not person_name:
            raise ValueError("نام عضو الزامی است")
        national_code = self.normalize_national_code(data.get("national_code"))
        person_id = data.get("person_id")
        if national_code:
            first_name = data.get("first_name") or ""
            last_name = data.get("last_name") or ""
            if not first_name and not last_name:
                first_name, last_name = self._split_person_name(person_name)
            person_id = self.upsert_person(
                national_code,
                first_name=first_name,
                last_name=last_name,
                full_name=person_name,
                education=data.get("education") or "",
                mobile=data.get("mobile") or "",
            )
        if person_id:
            duplicate = self.conn.execute(
                "SELECT id FROM committee_members WHERE committee_id=? AND person_id=?",
                (committee_id, person_id),
            ).fetchone()
            if duplicate:
                raise ValueError("این شخص قبلاً در کمیته انتخابی ثبت شده است.")

        fields = ["national_code", "mobile", "member_role", "member_type", "agency_id", "agency_name",
                  "is_chair", "is_secretary", "decree_no", "decree_date", "start_date", "end_date", "status", "notes"]
        defaults = {"member_role": "عضو", "member_type": "عضو مردمی", "is_chair": 0, "is_secretary": 0, "status": "فعال"}
        values = [data.get(key, defaults.get(key)) for key in fields]
        values[0] = national_code
        values[6] = int(bool(values[6])); values[7] = int(bool(values[7]))
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO committee_members
               (committee_id, person_id, person_name, national_code, mobile, member_role, member_type, agency_id,
                agency_name, is_chair, is_secretary, decree_no, decree_date, start_date, end_date, status,
                notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            [committee_id, person_id, person_name] + values,
        )
        member_id = cur.lastrowid
        if values[6] or values[7]:
            updates = {}
            if values[6]: updates.update(chair_name=person_name, chair_mobile=data.get("mobile") or "")
            if values[7]: updates.update(secretary_name=person_name, secretary_mobile=data.get("mobile") or "")
            self.update_committee(committee_id, **updates)
        self.conn.commit()
        self.log_action("committee_member_added", "committee_member", member_id, {"committee_id": committee_id, "name": person_name})
        return member_id

    def update_committee_member(self, member_id, **data):
        current = self.get_committee_member(member_id)
        if not current:
            return False
        person_name = (data.get("person_name", current.get("person_name")) or "").strip()
        if not person_name:
            raise ValueError("نام عضو الزامی است")
        national_code = self.normalize_national_code(data.get("national_code", current.get("national_code")))
        person_id = data.get("person_id", current.get("person_id"))
        if national_code:
            first_name = data.get("first_name") or ""
            last_name = data.get("last_name") or ""
            if not first_name and not last_name:
                first_name, last_name = self._split_person_name(person_name)
            person_id = self.upsert_person(
                national_code,
                first_name=first_name,
                last_name=last_name,
                full_name=person_name,
                education=data.get("education") or current.get("education") or "",
                mobile=data.get("mobile", current.get("mobile")) or "",
            )
            duplicate = self.conn.execute(
                "SELECT id FROM committee_members WHERE committee_id=? AND person_id=? AND id<>?",
                (current["committee_id"], person_id, member_id),
            ).fetchone()
            if duplicate:
                raise ValueError("این شخص قبلاً در کمیته انتخابی ثبت شده است.")

        fields = ["person_id", "person_name", "national_code", "mobile", "member_role", "member_type", "agency_id", "agency_name",
                  "is_chair", "is_secretary", "decree_no", "decree_date", "start_date", "end_date", "status", "notes"]
        merged = dict(current)
        merged.update(data)
        merged.update({"person_id": person_id, "person_name": person_name, "national_code": national_code})
        values = [merged.get(key) for key in fields]
        values[8] = int(bool(values[8])); values[9] = int(bool(values[9]))
        self.conn.execute(
            "UPDATE committee_members SET " + ", ".join(f"{key}=?" for key in fields) +
            ", updated_at=CURRENT_TIMESTAMP WHERE id=?", values + [member_id])
        self.conn.commit()
        return True

    def delete_committee_member(self, member_id):
        self.conn.execute("DELETE FROM committee_members WHERE id=?", (member_id,))
        self.conn.commit()

    def get_committee_members(self, committee_id):
        rows = self.conn.execute(
            """SELECT m.id, m.committee_id, m.person_id, m.person_name, m.national_code, m.mobile,
                      COALESCE(p.education,''), m.member_role, m.member_type, m.agency_id, m.agency_name,
                      m.is_chair, m.is_secretary, m.decree_no, m.decree_date, m.start_date,
                      m.end_date, m.status, m.notes, m.created_at, m.updated_at
               FROM committee_members m
               LEFT JOIN people_registry p ON p.id=m.person_id
               WHERE m.committee_id=?
               ORDER BY m.is_chair DESC, m.is_secretary DESC, m.person_name""",
            (committee_id,),).fetchall()
        keys = ["id", "committee_id", "person_id", "person_name", "national_code", "mobile", "education",
                "member_role", "member_type", "agency_id", "agency_name", "is_chair", "is_secretary",
                "decree_no", "decree_date", "start_date", "end_date", "status", "notes", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def get_committee_member(self, member_id):
        row = self.conn.execute(
            "SELECT committee_id FROM committee_members WHERE id=?", (member_id,)).fetchone()
        if not row:
            return None
        return next((x for x in self.get_committee_members(row[0]) if x["id"] == member_id), None)

    def _duplicate_committee_meeting_number(self, committee_id, meeting_number, exclude_id=None):
        target = _normalize_committee_meeting_number(meeting_number)
        if not target:
            return None
        rows = self.conn.execute(
            "SELECT id,title,meeting_number FROM committee_meetings WHERE committee_id=?",
            (committee_id,),
        ).fetchall()
        for row in rows:
            if exclude_id is not None and int(row[0]) == int(exclude_id):
                continue
            if _normalize_committee_meeting_number(row[2]) == target:
                return {"id": int(row[0]), "title": row[1] or "", "meeting_number": row[2] or ""}
        return None

    def add_committee_meeting(self, committee_id, zone_id, title, **data):
        title = (title or "").strip()
        if not title: raise ValueError("عنوان جلسه الزامی است")
        meeting_number = _normalize_committee_meeting_number(data.get("meeting_number"))
        duplicate = self._duplicate_committee_meeting_number(committee_id, meeting_number)
        if duplicate:
            raise ValueError(
                f"شماره جلسه «{meeting_number}» قبلاً برای «{duplicate['title']}» در همین کمیته ثبت شده است."
            )
        data["meeting_number"] = meeting_number or None
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO committee_meetings
               (committee_id, zone_id, title, meeting_number, meeting_date, start_time, place_name, agenda, attendees,
                minutes_text, status, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (committee_id, zone_id, title, data.get("meeting_number"), data.get("meeting_date"), data.get("start_time"),
             data.get("place_name"), data.get("agenda"), data.get("attendees"), data.get("minutes_text"),
             data.get("status") or "برنامه‌ریزی‌شده"),)
        self.conn.commit(); return cur.lastrowid

    def update_committee_meeting(self, meeting_id, **data):
        current = self.get_committee_meeting(meeting_id)
        if not current:
            return False
        fields = ["title", "meeting_number", "meeting_date", "start_time", "place_name", "agenda", "attendees", "minutes_text", "status"]
        merged = dict(current)
        merged.update(data)
        title = (merged.get("title") or "").strip()
        if not title:
            raise ValueError("عنوان جلسه الزامی است")
        meeting_number = _normalize_committee_meeting_number(merged.get("meeting_number"))
        duplicate = self._duplicate_committee_meeting_number(
            current["committee_id"], meeting_number, exclude_id=meeting_id
        )
        if duplicate:
            raise ValueError(
                f"شماره جلسه «{meeting_number}» قبلاً برای «{duplicate['title']}» در همین کمیته ثبت شده است."
            )
        merged["meeting_number"] = meeting_number or None
        values = [title] + [merged.get(field) for field in fields[1:]]
        self.conn.execute(
            "UPDATE committee_meetings SET " + ", ".join(f"{field}=?" for field in fields) +
            ", updated_at=CURRENT_TIMESTAMP WHERE id=?", values + [meeting_id]
        )
        self.conn.commit()
        return True

    def get_committee_meetings(self, committee_id):
        rows = self.conn.execute(
            """SELECT id, committee_id, zone_id, title, meeting_number, meeting_date, start_time, place_name, agenda,
                      attendees, minutes_text, status, created_at, updated_at
               FROM committee_meetings WHERE committee_id=? ORDER BY COALESCE(meeting_date,'') DESC, id DESC""", (committee_id,)).fetchall()
        keys = ["id", "committee_id", "zone_id", "title", "meeting_number", "meeting_date", "start_time", "place_name", "agenda",
                "attendees", "minutes_text", "status", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def get_committee_meeting(self, meeting_id):
        row = self.conn.execute(
            """SELECT id, committee_id, zone_id, title, meeting_number, meeting_date, start_time, place_name, agenda,
                      attendees, minutes_text, status, created_at, updated_at
               FROM committee_meetings WHERE id=?""", (meeting_id,)
        ).fetchone()
        if not row:
            return None
        keys = ["id", "committee_id", "zone_id", "title", "meeting_number", "meeting_date", "start_time", "place_name", "agenda",
                "attendees", "minutes_text", "status", "created_at", "updated_at"]
        return dict(zip(keys, row))

    def next_committee_meeting_number(self, committee_id):
        rows = self.conn.execute(
            "SELECT meeting_number FROM committee_meetings WHERE committee_id=?", (committee_id,)
        ).fetchall()
        numeric = []
        for row in rows:
            value = _normalize_committee_meeting_number(row[0])
            if value.isdigit() and int(value) > 0:
                numeric.append(int(value))
        return str((max(numeric) if numeric else len(rows)) + 1)

    def delete_committee_meeting(self, meeting_id):
        self.conn.execute("DELETE FROM committee_meetings WHERE id=?", (meeting_id,)); self.conn.commit()

    def add_committee_resolution(self, committee_id, zone_id, title, **data):
        title = (title or "").strip()
        if not title: raise ValueError("عنوان مصوبه الزامی است")
        cur = self.conn.cursor()
        cur.execute(
            """INSERT INTO committee_resolutions
               (meeting_id, committee_id, zone_id, title, description, responsible_agency, responsible_person,
                due_date, status, linked_issue_id, linked_action_id, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (data.get("meeting_id"), committee_id, zone_id, title, data.get("description"), data.get("responsible_agency"),
             data.get("responsible_person"), data.get("due_date"), data.get("status") or "در انتظار اقدام",
             data.get("linked_issue_id"), data.get("linked_action_id")),)
        self.conn.commit(); return cur.lastrowid

    def get_committee_resolutions(self, committee_id):
        rows = self.conn.execute(
            """SELECT id, meeting_id, committee_id, zone_id, title, description, responsible_agency,
                      responsible_person, due_date, status, linked_issue_id, linked_action_id, created_at, updated_at
               FROM committee_resolutions WHERE committee_id=? ORDER BY id DESC""", (committee_id,)).fetchall()
        keys = ["id", "meeting_id", "committee_id", "zone_id", "title", "description", "responsible_agency",
                "responsible_person", "due_date", "status", "linked_issue_id", "linked_action_id", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def get_committee_meeting_resolutions(self, meeting_id):
        rows = self.conn.execute(
            """SELECT id, meeting_id, committee_id, zone_id, title, description, responsible_agency,
                      responsible_person, due_date, status, linked_issue_id, linked_action_id, created_at, updated_at
               FROM committee_resolutions WHERE meeting_id=? ORDER BY id""", (meeting_id,)
        ).fetchall()
        keys = ["id", "meeting_id", "committee_id", "zone_id", "title", "description", "responsible_agency",
                "responsible_person", "due_date", "status", "linked_issue_id", "linked_action_id", "created_at", "updated_at"]
        return [dict(zip(keys, row)) for row in rows]

    def save_committee_meeting_resolutions(self, meeting_id, committee_id, zone_id, resolutions):
        existing = {
            int(row[0]) for row in self.conn.execute(
                "SELECT id FROM committee_resolutions WHERE meeting_id=?", (meeting_id,)
            ).fetchall()
        }
        kept = set()
        cur = self.conn.cursor()
        for index, item in enumerate(resolutions or [], start=1):
            description = (item.get("description") or item.get("title") or "").strip()
            if not description:
                continue
            title = (item.get("title") or description.splitlines()[0][:120] or f"مصوبه {index}").strip()
            resolution_id = item.get("id")
            values = (
                title, description, item.get("responsible_agency"), item.get("responsible_person"),
                item.get("due_date"), item.get("status") or "در انتظار اقدام",
                item.get("linked_issue_id"), item.get("linked_action_id")
            )
            if resolution_id and int(resolution_id) in existing:
                cur.execute(
                    """UPDATE committee_resolutions SET title=?, description=?, responsible_agency=?, responsible_person=?,
                       due_date=?, status=?, linked_issue_id=?, linked_action_id=?, updated_at=CURRENT_TIMESTAMP
                       WHERE id=? AND meeting_id=?""",
                    values + (int(resolution_id), meeting_id),
                )
                kept.add(int(resolution_id))
            else:
                cur.execute(
                    """INSERT INTO committee_resolutions
                       (meeting_id, committee_id, zone_id, title, description, responsible_agency, responsible_person,
                        due_date, status, linked_issue_id, linked_action_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (meeting_id, committee_id, zone_id) + values,
                )
                kept.add(int(cur.lastrowid))
        for resolution_id in existing - kept:
            cur.execute("DELETE FROM committee_resolutions WHERE id=? AND meeting_id=?", (resolution_id, meeting_id))
        self.conn.commit()
        return True

    def update_committee_resolution_status(self, resolution_id, status):
        self.conn.execute("UPDATE committee_resolutions SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, resolution_id)); self.conn.commit()

    def delete_committee_resolution(self, resolution_id):
        self.conn.execute("DELETE FROM committee_resolutions WHERE id=?", (resolution_id,)); self.conn.commit()

    def get_committee_meeting_signatures(self, meeting_id):
        rows = self.conn.execute(
            """SELECT s.id, s.meeting_id, s.member_id, s.signature_png, s.signed_at,
                      m.person_name, m.member_role, m.member_type, m.is_chair, m.is_secretary, m.status
               FROM committee_meeting_signatures s
               JOIN committee_members m ON m.id=s.member_id
               WHERE s.meeting_id=? ORDER BY m.is_chair DESC, m.is_secretary DESC, m.person_name""",
            (meeting_id,),
        ).fetchall()
        keys = ["id", "meeting_id", "member_id", "signature_png", "signed_at", "person_name", "member_role",
                "member_type", "is_chair", "is_secretary", "status"]
        return [dict(zip(keys, row)) for row in rows]

    def save_committee_meeting_signature(self, meeting_id, member_id, signature_png):
        if signature_png:
            self.conn.execute(
                """INSERT INTO committee_meeting_signatures(meeting_id, member_id, signature_png, signed_at, updated_at)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                   ON CONFLICT(meeting_id, member_id) DO UPDATE SET
                       signature_png=excluded.signature_png, signed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP""",
                (meeting_id, member_id, sqlite3.Binary(signature_png)),
            )
        else:
            self.conn.execute(
                "DELETE FROM committee_meeting_signatures WHERE meeting_id=? AND member_id=?",
                (meeting_id, member_id),
            )
        self.conn.commit()
        return True

    def save_committee_meeting_signatures(self, meeting_id, signatures):
        cur = self.conn.cursor()
        for member_id, signature_png in (signatures or {}).items():
            if signature_png:
                cur.execute(
                    """INSERT INTO committee_meeting_signatures(meeting_id, member_id, signature_png, signed_at, updated_at)
                       VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                       ON CONFLICT(meeting_id, member_id) DO UPDATE SET
                           signature_png=excluded.signature_png, signed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP""",
                    (meeting_id, int(member_id), sqlite3.Binary(signature_png)),
                )
            else:
                cur.execute(
                    "DELETE FROM committee_meeting_signatures WHERE meeting_id=? AND member_id=?",
                    (meeting_id, int(member_id)),
                )
        self.conn.commit()
        return True

    def link_committee_issue(self, committee_id, issue_id):
        self.conn.execute("INSERT OR IGNORE INTO committee_issue_links(committee_id, issue_id) VALUES (?, ?)", (committee_id, issue_id)); self.conn.commit()

    def unlink_committee_issue(self, committee_id, issue_id):
        self.conn.execute("DELETE FROM committee_issue_links WHERE committee_id=? AND issue_id=?", (committee_id, issue_id)); self.conn.commit()

    def get_committee_issues(self, committee_id):
        rows = self.conn.execute(
            """SELECT i.id, i.title, i.category, i.priority_level, i.status, i.related_office
               FROM neighborhood_issues i JOIN committee_issue_links l ON l.issue_id=i.id
               WHERE l.committee_id=? ORDER BY i.id DESC""", (committee_id,)).fetchall()
        keys = ["id", "title", "category", "priority_level", "status", "related_office"]
        return [dict(zip(keys, row)) for row in rows]

    def link_committee_action(self, committee_id, action_id):
        self.conn.execute("INSERT OR IGNORE INTO committee_action_links(committee_id, action_id) VALUES (?, ?)", (committee_id, action_id)); self.conn.commit()

    def unlink_committee_action(self, committee_id, action_id):
        self.conn.execute("DELETE FROM committee_action_links WHERE committee_id=? AND action_id=?", (committee_id, action_id)); self.conn.commit()

    def get_committee_actions(self, committee_id):
        rows = self.conn.execute(
            """SELECT a.id, a.title, a.responsible_office, a.progress_percent, a.status, a.planned_end
               FROM neighborhood_actions a JOIN committee_action_links l ON l.action_id=a.id
               WHERE l.committee_id=? ORDER BY a.id DESC""", (committee_id,)).fetchall()
        keys = ["id", "title", "responsible_office", "progress_percent", "status", "planned_end"]
        return [dict(zip(keys, row)) for row in rows]

    # ---------------- مرکز عملیات و پیگیری ----------------
    EXECUTION_CLOSED_STATUSES = ("تکمیل‌شده", "مختومه", "لغوشده")

    def sync_execution_cases(self):
        """ورود غیرمخرب مصوبات کمیته و اقدامات قبلی به مرکز پیگیری."""
        actor_id = (self.current_user or {}).get("id")
        self.conn.execute("""
            INSERT OR IGNORE INTO execution_cases
            (zone_id, committee_id, source_type, source_id, title, description,
             responsible_agency, responsible_person, priority, status, progress_percent,
             decision_date, due_date, created_by, created_at, updated_at)
            SELECT r.zone_id, r.committee_id, 'committee_resolution', r.id, r.title,
                   r.description, r.responsible_agency, r.responsible_person, 'مهم',
                   CASE WHEN r.status IN ('انجام‌شده','لغوشده') THEN r.status ELSE 'مصوب' END,
                   CASE WHEN r.status='انجام‌شده' THEN 100 ELSE 0 END,
                   r.created_at, r.due_date, ?, r.created_at, r.updated_at
            FROM committee_resolutions r
        """, (actor_id,))
        self.conn.execute("""
            INSERT OR IGNORE INTO execution_cases
            (zone_id, source_type, source_id, title, description, responsible_agency,
             responsible_person, priority, status, progress_percent, start_date, due_date,
             created_by, created_at, updated_at)
            SELECT a.zone_id, 'neighborhood_action', a.id, a.title, a.description,
                   a.responsible_office, a.responsible_person, 'عادی', a.status,
                   COALESCE(a.progress_percent,0), a.planned_start, a.planned_end,
                   ?, a.created_at, a.updated_at
            FROM neighborhood_actions a
        """, (actor_id,))
        self.conn.commit()

    def add_execution_case(self, title, zone_id=None, committee_id=None, **data):
        title = (title or "").strip()
        if not title:
            raise ValueError("عنوان پرونده پیگیری الزامی است.")
        actor_id = (self.current_user or {}).get("id")
        progress = max(0, min(100, int(data.get("progress_percent") or 0)))
        status = data.get("status") or "جدید"
        completed_date = data.get("completed_date")
        if status in self.EXECUTION_CLOSED_STATUSES and not completed_date:
            completed_date = datetime.now().strftime("%Y-%m-%d")
        cur = self.conn.execute("""
            INSERT INTO execution_cases
            (zone_id, committee_id, source_type, source_id, title, description,
             responsible_agency, responsible_person, assigned_user_id, priority, status,
             progress_percent, decision_date, start_date, due_date, completed_date,
             delay_reason, final_result, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (zone_id, committee_id, data.get("source_type") or "manual", data.get("source_id"),
              title, data.get("description"), data.get("responsible_agency"),
              data.get("responsible_person"), data.get("assigned_user_id"),
              data.get("priority") or "عادی", status, progress, data.get("decision_date"),
              data.get("start_date"), data.get("due_date"), completed_date,
              data.get("delay_reason"), data.get("final_result"), actor_id))
        self.conn.commit()
        self.log_action("execution_case_created", "execution_case", cur.lastrowid, {"title": title})
        return cur.lastrowid

    def update_execution_case(self, case_id, **changes):
        current = self.get_execution_case(case_id)
        if not current:
            raise ValueError("پرونده پیگیری پیدا نشد.")
        allowed = {"zone_id", "committee_id", "title", "description", "responsible_agency",
                   "responsible_person", "assigned_user_id", "priority", "status",
                   "progress_percent", "decision_date", "start_date", "due_date",
                   "completed_date", "delay_reason", "final_result"}
        data = {k: v for k, v in changes.items() if k in allowed}
        if "title" in data and not str(data["title"] or "").strip():
            raise ValueError("عنوان پرونده پیگیری الزامی است.")
        if "progress_percent" in data:
            data["progress_percent"] = max(0, min(100, int(data["progress_percent"] or 0)))
        if data.get("status") in self.EXECUTION_CLOSED_STATUSES:
            data.setdefault("completed_date", datetime.now().strftime("%Y-%m-%d"))
            if data.get("status") == "تکمیل‌شده":
                data.setdefault("progress_percent", 100)
        if not data:
            return True
        sets = ", ".join(f"{k}=?" for k in data)
        self.conn.execute(f"UPDATE execution_cases SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?", list(data.values())+[int(case_id)])
        self.conn.commit()
        self.log_action("execution_case_updated", "execution_case", case_id, data)
        return True

    def get_execution_case(self, case_id):
        rows = self.get_execution_cases(case_id=case_id)
        return rows[0] if rows else None

    def get_execution_cases(self, zone_id=None, status=None, assigned_user_id=None, query=None, case_id=None, open_only=False, limit=2000):
        clauses=[]; params=[]
        if case_id is not None: clauses.append("c.id=?"); params.append(int(case_id))
        if zone_id is not None: clauses.append("c.zone_id=?"); params.append(int(zone_id))
        if status: clauses.append("c.status=?"); params.append(status)
        if assigned_user_id is not None: clauses.append("c.assigned_user_id=?"); params.append(int(assigned_user_id))
        if open_only: clauses.append("c.status NOT IN ('تکمیل‌شده','مختومه','لغوشده')")
        if query:
            like=f"%{query.strip()}%"; clauses.append("(c.title LIKE ? OR c.description LIKE ? OR c.responsible_agency LIKE ? OR c.responsible_person LIKE ?)"); params += [like]*4
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows=self.conn.execute("""SELECT c.id,c.zone_id,z.name,c.committee_id,n.title,c.source_type,c.source_id,
                    c.title,c.description,c.responsible_agency,c.responsible_person,c.assigned_user_id,
                    u.full_name,c.priority,c.status,c.progress_percent,c.decision_date,c.start_date,
                    c.due_date,c.completed_date,c.delay_reason,c.final_result,c.created_at,c.updated_at,
                    (SELECT COUNT(*) FROM execution_assignments a WHERE a.case_id=c.id AND a.status NOT IN ('پاسخ‌داده‌شده','مختومه')),
                    (SELECT COUNT(*) FROM document_attachments d WHERE d.parent_type='execution_case' AND d.parent_id=c.id)
               FROM execution_cases c LEFT JOIN zones z ON z.id=c.zone_id
               LEFT JOIN neighborhood_committees n ON n.id=c.committee_id
               LEFT JOIN app_users u ON u.id=c.assigned_user_id"""+where+
               " ORDER BY CASE WHEN c.status NOT IN ('تکمیل‌شده','مختومه','لغوشده') THEN 0 ELSE 1 END, COALESCE(c.due_date,'9999-12-31'), c.id DESC LIMIT ?", params).fetchall()
        keys=["id","zone_id","zone_name","committee_id","committee_title","source_type","source_id","title","description","responsible_agency","responsible_person","assigned_user_id","assigned_user_name","priority","status","progress_percent","decision_date","start_date","due_date","completed_date","delay_reason","final_result","created_at","updated_at","open_assignment_count","attachment_count"]
        return [dict(zip(keys,row)) for row in rows]

    def add_execution_update(self, case_id, note="", progress_percent=None, status=None, update_date=None):
        case=self.get_execution_case(case_id)
        if not case: raise ValueError("پرونده پیگیری پیدا نشد.")
        progress=case.get("progress_percent") if progress_percent is None else max(0,min(100,int(progress_percent)))
        status=status or case.get("status")
        actor_id=(self.current_user or {}).get("id")
        cur=self.conn.execute("""INSERT INTO execution_case_updates(case_id,update_date,progress_percent,status,note,created_by)
                                 VALUES(?,?,?,?,?,?)""", (int(case_id), update_date or datetime.now().strftime("%Y-%m-%d"), progress, status, note, actor_id))
        self.update_execution_case(case_id, progress_percent=progress, status=status)
        return cur.lastrowid

    def get_execution_updates(self, case_id):
        rows=self.conn.execute("""SELECT x.id,x.case_id,x.update_date,x.progress_percent,x.status,x.note,x.created_by,u.full_name,x.created_at
                                  FROM execution_case_updates x LEFT JOIN app_users u ON u.id=x.created_by
                                  WHERE x.case_id=? ORDER BY x.id DESC""", (int(case_id),)).fetchall()
        keys=["id","case_id","update_date","progress_percent","status","note","created_by","created_by_name","created_at"]
        return [dict(zip(keys,row)) for row in rows]

    def add_execution_assignment(self, case_id, assigned_to_user_id=None, assigned_to_name="", assigned_to_agency="", instruction="", due_date=None, priority="عادی"):
        if not self.get_execution_case(case_id): raise ValueError("پرونده پیگیری پیدا نشد.")
        actor_id=(self.current_user or {}).get("id")
        if assigned_to_user_id:
            user=self.get_user(assigned_to_user_id)
            if not user: raise ValueError("کاربر گیرنده پیدا نشد.")
            assigned_to_name=user.get("full_name") or user.get("username")
        if not (assigned_to_name or assigned_to_agency): raise ValueError("گیرنده یا دستگاه ارجاع الزامی است.")
        cur=self.conn.execute("""INSERT INTO execution_assignments
            (case_id,assigned_to_user_id,assigned_to_name,assigned_to_agency,assigned_by_user_id,instruction,due_date,priority,status,updated_at)
            VALUES(?,?,?,?,?,?,?,?, 'ارجاع‌شده', CURRENT_TIMESTAMP)""",
            (int(case_id),assigned_to_user_id,(assigned_to_name or '').strip(),(assigned_to_agency or '').strip(),actor_id,instruction,due_date,priority))
        if assigned_to_user_id:
            self.update_execution_case(case_id, assigned_user_id=assigned_to_user_id)
        self.conn.commit(); return cur.lastrowid

    def get_execution_assignments(self, case_id=None, assigned_to_user_id=None, status=None, open_only=False, limit=2000):
        clauses=[]; params=[]
        if case_id is not None: clauses.append("a.case_id=?"); params.append(int(case_id))
        if assigned_to_user_id is not None: clauses.append("a.assigned_to_user_id=?"); params.append(int(assigned_to_user_id))
        if status: clauses.append("a.status=?"); params.append(status)
        if open_only: clauses.append("a.status NOT IN ('پاسخ‌داده‌شده','مختومه')")
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        params.append(int(limit))
        rows=self.conn.execute("""SELECT a.id,a.case_id,c.title,c.zone_id,z.name,a.assigned_to_user_id,a.assigned_to_name,
                 a.assigned_to_agency,a.assigned_by_user_id,b.full_name,a.instruction,a.due_date,a.priority,a.status,
                 a.viewed_at,a.response_text,a.completed_at,a.created_at,a.updated_at
                 FROM execution_assignments a JOIN execution_cases c ON c.id=a.case_id
                 LEFT JOIN zones z ON z.id=c.zone_id LEFT JOIN app_users b ON b.id=a.assigned_by_user_id"""+where+
                 " ORDER BY CASE WHEN a.status NOT IN ('پاسخ‌داده‌شده','مختومه') THEN 0 ELSE 1 END, COALESCE(a.due_date,'9999-12-31'), a.id DESC LIMIT ?", params).fetchall()
        keys=["id","case_id","case_title","zone_id","zone_name","assigned_to_user_id","assigned_to_name","assigned_to_agency","assigned_by_user_id","assigned_by_name","instruction","due_date","priority","status","viewed_at","response_text","completed_at","created_at","updated_at"]
        return [dict(zip(keys,row)) for row in rows]

    def update_execution_assignment(self, assignment_id, status=None, response_text=None, mark_viewed=False):
        fields=[]; params=[]
        if status is not None: fields.append("status=?"); params.append(status)
        if response_text is not None: fields.append("response_text=?"); params.append(response_text)
        if mark_viewed: fields.append("viewed_at=COALESCE(viewed_at,CURRENT_TIMESTAMP)")
        if status in ("پاسخ‌داده‌شده","مختومه"): fields.append("completed_at=CURRENT_TIMESTAMP")
        if not fields: return True
        params.append(int(assignment_id))
        self.conn.execute("UPDATE execution_assignments SET "+", ".join(fields)+", updated_at=CURRENT_TIMESTAMP WHERE id=?", params)
        self.conn.commit(); return True

    def get_execution_dashboard_stats(self, zone_id=None):
        params=[]; where=""
        if zone_id is not None: where=" WHERE zone_id=?"; params=[int(zone_id)]
        rows=self.conn.execute("SELECT status,due_date,progress_percent FROM execution_cases"+where, params).fetchall()
        today=datetime.now().strftime("%Y-%m-%d")
        total=len(rows); closed=sum(1 for s,_,__ in rows if s in self.EXECUTION_CLOSED_STATUSES)
        overdue=sum(1 for s,d,__ in rows if s not in self.EXECUTION_CLOSED_STATUSES and d and d<today)
        due_soon=sum(1 for s,d,__ in rows if s not in self.EXECUTION_CLOSED_STATUSES and d and today<=d<=(datetime.now()+timedelta(days=7)).strftime("%Y-%m-%d"))
        avg=round(sum(int(p or 0) for _,__,p in rows)/total,1) if total else 0
        assignments=self.conn.execute("SELECT COUNT(*) FROM execution_assignments WHERE status NOT IN ('پاسخ‌داده‌شده','مختومه')").fetchone()[0]
        return {"total":total,"open":total-closed,"closed":closed,"overdue":overdue,"due_soon":due_soon,"average_progress":avg,"open_assignments":assignments}

    def get_zone_dossier(self, zone_id):
        zone=self.get_zone(zone_id)
        if not zone: raise ValueError("بلوک پیدا نشد.")
        committees=self.get_zone_committees(zone_id)
        return {"zone":zone,"profile":self.get_zone_profile(zone_id) or {},"council_members":self.get_council_members(zone_id),
                "committees":[{"committee":c,"members":self.get_committee_members(c["id"]),"meetings":self.get_committee_meetings(c["id"]),"resolutions":self.get_committee_resolutions(c["id"])} for c in committees],
                "issues":self.get_neighborhood_issues(zone_id),"actions":self.get_neighborhood_actions(zone_id),
                "projects":self.get_projects(zone_id=zone_id),"citizen_requests":self.get_citizen_requests(zone_id=zone_id),
                "letters":self.get_correspondence_letters(zone_id=zone_id),"budgets":self.get_neighborhood_budgets(zone_id=zone_id),
                "execution_cases":self.get_execution_cases(zone_id=zone_id),"execution_stats":self.get_execution_dashboard_stats(zone_id)}

    def get_execution_agency_performance(self):
        rows=self.conn.execute("""SELECT COALESCE(NULLIF(TRIM(responsible_agency),''),'بدون دستگاه') agency,
            COUNT(*) total,
            SUM(CASE WHEN status IN ('تکمیل‌شده','مختومه') THEN 1 ELSE 0 END) completed,
            SUM(CASE WHEN status NOT IN ('تکمیل‌شده','مختومه','لغوشده') AND due_date<date('now') THEN 1 ELSE 0 END) overdue,
            ROUND(AVG(COALESCE(progress_percent,0)),1) avg_progress
            FROM execution_cases GROUP BY agency ORDER BY completed DESC, avg_progress DESC, total DESC""").fetchall()
        keys=["agency","total","completed","overdue","average_progress"]
        return [dict(zip(keys,row)) for row in rows]

    def get_execution_zone_performance(self):
        rows=self.conn.execute("""SELECT z.id,z.name,COUNT(c.id) total,
            SUM(CASE WHEN c.status IN ('تکمیل‌شده','مختومه') THEN 1 ELSE 0 END) completed,
            SUM(CASE WHEN c.status NOT IN ('تکمیل‌شده','مختومه','لغوشده') AND c.due_date<date('now') THEN 1 ELSE 0 END) overdue,
            ROUND(COALESCE(AVG(c.progress_percent),0),1) avg_progress
            FROM zones z LEFT JOIN execution_cases c ON c.zone_id=z.id GROUP BY z.id,z.name
            ORDER BY avg_progress DESC, completed DESC, z.name""").fetchall()
        keys=["zone_id","zone_name","total","completed","overdue","average_progress"]
        return [dict(zip(keys,row)) for row in rows]

    def get_all_document_attachments(self, parent_type=None, limit=2000):
        params=[]; where=""
        if parent_type: where=" WHERE a.parent_type=?"; params.append(parent_type)
        params.append(int(limit))
        rows=self.conn.execute("""SELECT a.id,a.parent_type,a.parent_id,a.original_name,a.stored_path,a.mime_type,
            a.file_size,a.description,a.created_by,u.full_name,a.created_at
            FROM document_attachments a LEFT JOIN app_users u ON u.id=a.created_by"""+where+" ORDER BY a.id DESC LIMIT ?", params).fetchall()
        keys=["id","parent_type","parent_id","original_name","stored_path","mime_type","file_size","description","created_by","created_by_name","created_at"]
        return [dict(zip(keys,row)) for row in rows]

