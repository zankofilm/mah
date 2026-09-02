# -*- coding: utf-8 -*-
"""
Offline Map Builder v7.6.17
ایجاد محدوده نقشه آفلاین توسط کاربر.
این ماژول محدوده انتخابی را ذخیره می‌کند تا در مراحل بعدی
داده‌های نقشه بدون وابستگی به اینترنت بارگذاری شوند.
"""

import os, json, sqlite3, datetime

class OfflineMapStore:
    def __init__(self, db_path):
        self.db_path=db_path
        self._init()

    def _init(self):
        con=sqlite3.connect(self.db_path)
        con.execute("""CREATE TABLE IF NOT EXISTS offline_map_area(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            polygon TEXT,
            created_at TEXT
        )""")
        con.commit()
        con.close()

    def save_area(self, name, polygon):
        con=sqlite3.connect(self.db_path)
        con.execute(
            "INSERT INTO offline_map_area(name,polygon,created_at) VALUES(?,?,?)",
            (name,json.dumps(polygon,ensure_ascii=False),
             datetime.datetime.now().isoformat())
        )
        con.commit()
        con.close()

    def get_areas(self):
        con=sqlite3.connect(self.db_path)
        rows=con.execute("SELECT id,name,polygon FROM offline_map_area").fetchall()
        con.close()
        return rows
