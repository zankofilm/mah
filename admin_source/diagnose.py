# -*- coding: utf-8 -*-
"""ابزار خط فرمان تشخیص و بازیابی؛ مستقل از رابط PyQt."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

from database import Database
from production_health import (
    create_support_bundle, overall_health, recovery_drill, run_health_checks,
)
from runtime_paths import get_support_dir, migrate_legacy_runtime_data


def main():
    parser = argparse.ArgumentParser(description="Javanrood system diagnostics")
    parser.add_argument("--support", action="store_true", help="create support ZIP")
    parser.add_argument("--include-database", action="store_true", help="include database in support ZIP")
    parser.add_argument("--recovery-drill", metavar="DIR", help="run recovery drill in directory")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args()

    migrate_legacy_runtime_data()
    db = Database()
    try:
        try:
            db.ensure_daily_backup(keep=14)
        except Exception:
            pass
        checks = run_health_checks(db)
        payload = {"overall": overall_health(checks), "checks": checks}
        if args.recovery_drill:
            payload["recovery_drill"] = recovery_drill(db, args.recovery_drill)
        if args.support:
            output = os.path.join(get_support_dir(), f"support_cli_{datetime.now():%Y%m%d_%H%M%S}.zip")
            payload["support_bundle"] = create_support_bundle(db, output, args.include_database)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        else:
            print("Overall:", payload["overall"])
            for item in checks:
                print(f"[{item['status'].upper()}] {item['name']}: {item['message']}")
            if payload.get("recovery_drill"):
                print("Recovery drill:", "PASSED" if payload["recovery_drill"]["passed"] else "FAILED")
            if payload.get("support_bundle"):
                print("Support bundle:", payload["support_bundle"])
        return 0 if payload["overall"] != "error" else 2
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
