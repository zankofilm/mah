# -*- coding: utf-8 -*-
"""جداول و عملیات دیتابیس ماژول برآورد جمعیت بلوک‌ها."""
from __future__ import annotations

import json
import os
from datetime import datetime

from population_engine import estimate_population


class PopulationEstimationMixin:
    def _create_population_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS population_source_values (
                zone_id INTEGER NOT NULL,
                source_code TEXT NOT NULL,
                source_title TEXT NOT NULL,
                source_year INTEGER,
                population_value REAL DEFAULT 0,
                cell_count INTEGER DEFAULT 0,
                source_file TEXT,
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (zone_id, source_code),
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS population_zone_inputs (
                zone_id INTEGER PRIMARY KEY,
                occupancy_rate REAL DEFAULT 0.90,
                active_meters INTEGER DEFAULT 0,
                adjustment INTEGER DEFAULT 0,
                notes TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS population_estimates (
                zone_id INTEGER PRIMARY KEY,
                worldpop_population REAL DEFAULT 0,
                ghsl_population REAL DEFAULT 0,
                housing_population INTEGER DEFAULT 0,
                meter_population INTEGER DEFAULT 0,
                final_population INTEGER DEFAULT 0,
                minimum_population INTEGER DEFAULT 0,
                maximum_population INTEGER DEFAULT 0,
                households INTEGER DEFAULT 0,
                density_per_km2 REAL DEFAULT 0,
                confidence TEXT DEFAULT 'فاقد داده',
                source_count INTEGER DEFAULT 0,
                method_summary TEXT,
                source_details TEXT,
                calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zone_id) REFERENCES zones(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_population_source_code ON population_source_values(source_code)")
        self.conn.commit()

    def save_population_source_values(self, source_code, source_title, source_year, source_file, values):
        source_code = str(source_code or "").strip().lower()
        if source_code not in {"worldpop", "ghsl"}:
            raise ValueError("منبع جمعیتی نامعتبر است.")
        with self.conn:
            for zone_id, item in (values or {}).items():
                self.conn.execute(
                    """INSERT INTO population_source_values
                       (zone_id, source_code, source_title, source_year, population_value, cell_count, source_file, imported_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(zone_id, source_code) DO UPDATE SET
                         source_title=excluded.source_title, source_year=excluded.source_year,
                         population_value=excluded.population_value, cell_count=excluded.cell_count,
                         source_file=excluded.source_file, imported_at=CURRENT_TIMESTAMP""",
                    (int(zone_id), source_code, source_title, int(source_year or 0) or None,
                     max(0.0, float(item.get("value") or 0)), max(0, int(item.get("cell_count") or 0)),
                     os.path.abspath(source_file) if source_file else ""),
                )
        self.log_action("population_source_import", "population", None, {
            "source": source_code, "year": source_year, "zones": len(values or {}),
        })

    def get_population_source_values(self, zone_id):
        rows = self.conn.execute(
            """SELECT source_code, source_title, source_year, population_value, cell_count, source_file, imported_at
               FROM population_source_values WHERE zone_id=?""", (int(zone_id),)
        ).fetchall()
        return {
            row[0]: {
                "source_code": row[0], "source_title": row[1], "source_year": row[2],
                "population_value": row[3] or 0, "cell_count": row[4] or 0,
                "source_file": row[5] or "", "imported_at": row[6],
            } for row in rows
        }

    def get_population_source_status(self):
        rows = self.conn.execute(
            """SELECT source_code, MAX(source_title), MAX(source_year), MAX(imported_at),
                      COUNT(*), SUM(population_value), SUM(cell_count)
               FROM population_source_values GROUP BY source_code ORDER BY source_code"""
        ).fetchall()
        return [
            {"source_code": r[0], "source_title": r[1], "source_year": r[2], "imported_at": r[3],
             "zones_count": r[4] or 0, "total_population": r[5] or 0, "cell_count": r[6] or 0}
            for r in rows
        ]

    def save_population_zone_inputs(self, zone_id, *, residential_buildings=0, residential_units=0,
                                    occupied_units=0, occupancy_rate=0.90, household_size=3.3,
                                    active_meters=0, adjustment=0, notes=""):
        zone_id = int(zone_id)
        residential_buildings = max(0, int(residential_buildings or 0))
        residential_units = max(0, int(residential_units or 0))
        occupied_units = max(0, int(occupied_units or 0))
        household_size = max(0.1, float(household_size or 3.3))
        occupancy_rate = min(1.0, max(0.0, float(occupancy_rate or 0)))
        active_meters = max(0, int(active_meters or 0))
        adjustment = int(adjustment or 0)
        with self.conn:
            self.conn.execute(
                """INSERT INTO zone_profiles
                   (zone_id, residential_buildings, residential_units, occupied_units,
                    average_household_size, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(zone_id) DO UPDATE SET
                     residential_buildings=excluded.residential_buildings,
                     residential_units=excluded.residential_units,
                     occupied_units=excluded.occupied_units,
                     average_household_size=excluded.average_household_size,
                     updated_at=CURRENT_TIMESTAMP""",
                (zone_id, residential_buildings, residential_units, occupied_units, household_size),
            )
            self.conn.execute(
                """INSERT INTO population_zone_inputs
                   (zone_id, occupancy_rate, active_meters, adjustment, notes, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(zone_id) DO UPDATE SET
                     occupancy_rate=excluded.occupancy_rate, active_meters=excluded.active_meters,
                     adjustment=excluded.adjustment, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
                (zone_id, occupancy_rate, active_meters, adjustment, str(notes or "").strip()),
            )
        return self.get_population_zone_inputs(zone_id)

    def get_population_zone_inputs(self, zone_id):
        profile = self.get_zone_profile(int(zone_id))
        row = self.conn.execute(
            "SELECT occupancy_rate, active_meters, adjustment, notes, updated_at FROM population_zone_inputs WHERE zone_id=?",
            (int(zone_id),),
        ).fetchone()
        return {
            "zone_id": int(zone_id),
            "residential_buildings": profile.get("residential_buildings") or 0,
            "residential_units": profile.get("residential_units") or 0,
            "occupied_units": profile.get("occupied_units") or 0,
            "household_size": profile.get("average_household_size") or 3.3,
            "occupancy_rate": row[0] if row else 0.90,
            "active_meters": row[1] if row else 0,
            "adjustment": row[2] if row else 0,
            "notes": row[3] if row else "",
            "updated_at": row[4] if row else profile.get("updated_at"),
        }

    def calculate_population_estimate(self, zone_id):
        zone = self.get_zone(int(zone_id))
        if not zone:
            raise ValueError("بلوک انتخاب‌شده پیدا نشد.")
        inputs = self.get_population_zone_inputs(zone_id)
        sources = self.get_population_source_values(zone_id)
        result = estimate_population(
            worldpop=(sources.get("worldpop") or {}).get("population_value", 0),
            ghsl=(sources.get("ghsl") or {}).get("population_value", 0),
            residential_units=inputs["residential_units"],
            occupied_units=inputs["occupied_units"],
            occupancy_rate=inputs["occupancy_rate"],
            household_size=inputs["household_size"],
            active_meters=inputs["active_meters"],
            adjustment=inputs["adjustment"],
            area_m2=zone.get("area_m2") or 0,
        )
        with self.conn:
            self.conn.execute(
                """INSERT INTO population_estimates
                   (zone_id, worldpop_population, ghsl_population, housing_population, meter_population,
                    final_population, minimum_population, maximum_population, households,
                    density_per_km2, confidence, source_count, method_summary, source_details, calculated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(zone_id) DO UPDATE SET
                     worldpop_population=excluded.worldpop_population,
                     ghsl_population=excluded.ghsl_population,
                     housing_population=excluded.housing_population,
                     meter_population=excluded.meter_population,
                     final_population=excluded.final_population,
                     minimum_population=excluded.minimum_population,
                     maximum_population=excluded.maximum_population,
                     households=excluded.households,
                     density_per_km2=excluded.density_per_km2,
                     confidence=excluded.confidence,
                     source_count=excluded.source_count,
                     method_summary=excluded.method_summary,
                     source_details=excluded.source_details,
                     calculated_at=CURRENT_TIMESTAMP""",
                (int(zone_id),
                 (sources.get("worldpop") or {}).get("population_value", 0),
                 (sources.get("ghsl") or {}).get("population_value", 0),
                 result.housing_population, result.meter_population,
                 result.final_population, result.minimum_population, result.maximum_population,
                 result.households, result.density_per_km2, result.confidence, result.source_count,
                 result.method_summary, json.dumps(result.source_values, ensure_ascii=False)),
            )
            self.conn.execute(
                """INSERT INTO zone_profiles
                   (zone_id, estimated_households, estimated_population, estimation_method, confidence_level, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(zone_id) DO UPDATE SET
                     estimated_households=excluded.estimated_households,
                     estimated_population=excluded.estimated_population,
                     estimation_method=excluded.estimation_method,
                     confidence_level=excluded.confidence_level,
                     updated_at=CURRENT_TIMESTAMP""",
                (int(zone_id), result.households, result.final_population, result.method_summary, result.confidence),
            )
        self.log_action("population_estimated", "zone", int(zone_id), {
            "population": result.final_population, "confidence": result.confidence,
            "source_count": result.source_count,
        })
        return self.get_population_estimate(zone_id)

    def calculate_all_population_estimates(self):
        return [self.calculate_population_estimate(zone["id"]) for zone in self.get_zones()]

    def get_population_estimate(self, zone_id):
        row = self.conn.execute(
            """SELECT zone_id, worldpop_population, ghsl_population, housing_population, meter_population,
                      final_population, minimum_population, maximum_population, households,
                      density_per_km2, confidence, source_count, method_summary, source_details, calculated_at
               FROM population_estimates WHERE zone_id=?""", (int(zone_id),)
        ).fetchone()
        keys = ["zone_id", "worldpop_population", "ghsl_population", "housing_population", "meter_population",
                "final_population", "minimum_population", "maximum_population", "households",
                "density_per_km2", "confidence", "source_count", "method_summary", "source_details", "calculated_at"]
        return dict(zip(keys, row)) if row else None

    def get_population_estimates(self):
        rows = self.conn.execute(
            """SELECT z.id, z.name, z.area_m2,
                      COALESCE(e.worldpop_population,0), COALESCE(e.ghsl_population,0),
                      COALESCE(e.housing_population,0), COALESCE(e.meter_population,0),
                      COALESCE(e.final_population,0), COALESCE(e.minimum_population,0),
                      COALESCE(e.maximum_population,0), COALESCE(e.households,0),
                      COALESCE(e.density_per_km2,0), COALESCE(e.confidence,'فاقد داده'),
                      COALESCE(e.source_count,0), e.method_summary, e.calculated_at
               FROM zones z LEFT JOIN population_estimates e ON e.zone_id=z.id
               ORDER BY z.created_at ASC"""
        ).fetchall()
        keys = ["zone_id", "zone_name", "area_m2", "worldpop_population", "ghsl_population",
                "housing_population", "meter_population", "final_population", "minimum_population",
                "maximum_population", "households", "density_per_km2", "confidence", "source_count",
                "method_summary", "calculated_at"]
        return [dict(zip(keys, row)) for row in rows]
