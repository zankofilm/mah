# -*- coding: utf-8 -*-
import csv
import os
import tempfile
import unittest
from pathlib import Path

from database import Database, SCHEMA_VERSION
from population_engine import aggregate_population_file, estimate_population


ROOT = Path(__file__).resolve().parents[1]


class V732PopulationEstimationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.db"))
        self.zone_id = self.db.create_zone(
            "بلوک نمونه",
            [(34.8000, 46.4800), (34.8000, 46.4900), (34.8100, 46.4900), (34.8100, 46.4800)],
        )

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_weighted_estimate_has_range_density_and_confidence(self):
        result = estimate_population(
            worldpop=1000, ghsl=1100, residential_units=300, occupancy_rate=0.9,
            household_size=3.5, active_meters=280, area_m2=500000,
        )
        self.assertGreater(result.final_population, 0)
        self.assertLess(result.minimum_population, result.final_population)
        self.assertGreater(result.maximum_population, result.final_population)
        self.assertEqual(result.source_count, 4)
        self.assertEqual(result.confidence, "زیاد")
        self.assertGreater(result.density_per_km2, 0)

    def test_csv_cells_are_aggregated_inside_zone(self):
        path = os.path.join(self.tmp.name, "worldpop.csv")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["lat", "lon", "population"])
            writer.writerow([34.805, 46.485, 120])
            writer.writerow([34.806, 46.486, 80])
            writer.writerow([35.0, 47.0, 900])
        values = aggregate_population_file(path, self.db.get_zones())
        self.assertEqual(values[self.zone_id]["value"], 200)
        self.assertEqual(values[self.zone_id]["cell_count"], 2)

    def test_database_persists_sources_inputs_and_final_estimate(self):
        self.db.save_population_source_values(
            "worldpop", "WorldPop", 2025, "worldpop.csv",
            {self.zone_id: {"value": 1000, "cell_count": 50}},
        )
        self.db.save_population_source_values(
            "ghsl", "GHSL", 2025, "ghsl.csv",
            {self.zone_id: {"value": 1100, "cell_count": 45}},
        )
        self.db.save_population_zone_inputs(
            self.zone_id, residential_buildings=100, residential_units=300,
            occupancy_rate=0.9, household_size=3.5, active_meters=280,
        )
        estimate = self.db.calculate_population_estimate(self.zone_id)
        self.assertGreater(estimate["final_population"], 0)
        self.assertEqual(estimate["source_count"], 4)
        profile = self.db.get_zone_profile(self.zone_id)
        self.assertEqual(profile["estimated_population"], estimate["final_population"])
        self.assertEqual(self.db.get_system_stats()["estimated_population"], estimate["final_population"])

    def test_release_integration_tokens(self):
        self.assertEqual(SCHEMA_VERSION, 7630)
        self.assertIn('APP_VERSION = "7.6.20"', (ROOT / "version.py").read_text(encoding="utf-8"))
        dashboard = (ROOT / "dashboard_window.py").read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("open_population_estimation_module", dashboard)
        self.assertIn("برآورد جمعیت", dashboard)
        self.assertIn("PopulationEstimationWindow", app)
        self.assertTrue((ROOT / "population_estimation_module.py").exists())
        self.assertTrue((ROOT / "population_engine.py").exists())


if __name__ == "__main__":
    unittest.main()
