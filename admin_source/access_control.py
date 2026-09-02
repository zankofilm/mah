# -*- coding: utf-8 -*-
"""تعریف نقش‌ها و مجوزهای سامانه مدیریت محله‌محور."""

ROLE_DEFINITIONS = {
    "admin": {
        "title": "مدیر سامانه",
        "permissions": {"*"},
        "description": "دسترسی کامل به همه بخش‌ها، کاربران، بکاپ و تنظیمات حساس.",
    },
    "manager": {
        "title": "مدیر محله‌محور",
        "permissions": {
            "dashboard", "neighborhood", "blocking", "council", "priority",
            "actions", "reports", "city_map", "correspondence", "approvals", "monitoring", "project_control", "contracts", "governance", "operations_center", "messaging", "population", "global_search", "account",
        },
        "description": "مدیریت پرونده بلوک‌ها، مسائل، اقدامات، جلسات و گزارش‌ها.",
    },
    "gis": {
        "title": "کارشناس GIS",
        "permissions": {"dashboard", "blocking", "city_map", "reports", "monitoring", "project_control", "contracts", "operations_center", "population", "global_search", "account"},
        "description": "بلوک‌بندی، نقشه، معابر، اماکن و خروجی‌های مکانی.",
    },
    "field": {
        "title": "کارشناس میدانی",
        "permissions": {"dashboard", "neighborhood", "council", "priority", "correspondence", "approvals", "monitoring", "project_control", "contracts", "operations_center", "messaging", "global_search", "account"},
        "description": "بازدید میدانی، درخواست‌های مردمی و تکمیل پرونده محله.",
    },
    "reporter": {
        "title": "کارشناس گزارش",
        "permissions": {"dashboard", "reports", "correspondence", "approvals", "monitoring", "project_control", "contracts", "operations_center", "population", "global_search", "account"},
        "description": "مشاهده اطلاعات و تولید گزارش‌های رسمی.",
    },
    "viewer": {
        "title": "مشاهده‌گر",
        "permissions": {"dashboard", "reports", "correspondence", "approvals", "monitoring", "project_control", "contracts", "operations_center", "population", "global_search", "account"},
        "description": "دسترسی فقط‌خواندنی به گزارش‌ها و جستجو.",
    },
}


def role_title(role):
    return ROLE_DEFINITIONS.get(role, {}).get("title", role or "نامشخص")


def role_description(role):
    return ROLE_DEFINITIONS.get(role, {}).get("description", "")


def has_permission(role, permission):
    permissions = ROLE_DEFINITIONS.get(role, {}).get("permissions", set())
    return "*" in permissions or permission in permissions


def available_roles():
    return [(key, value["title"]) for key, value in ROLE_DEFINITIONS.items()]
