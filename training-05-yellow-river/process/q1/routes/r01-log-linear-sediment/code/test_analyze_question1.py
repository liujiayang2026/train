from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import analyze_question1 as q1


def synthetic_observed() -> pd.DataFrame:
    rows = []
    for year in q1.YEARS:
        start = datetime(year, 1, 1)
        for offset_hours in (0, 6, 12, 18, 24, 30, 36, 42):
            rows.append(
                {
                    "datetime": start + timedelta(hours=offset_hours),
                    "year": year,
                    "sediment_obs_kgm3": 1.0 + (year - 2016),
                }
            )
    return pd.DataFrame(rows).sort_values("datetime").reset_index(drop=True)


class ParsingTests(unittest.TestCase):
    def test_legal_numeric_text_is_parsed(self) -> None:
        self.assertEqual(q1._as_finite_float(" 43.27 "), 43.27)
        self.assertEqual(q1._as_finite_float(np.float64(43.28)), 43.28)
        self.assertTrue(np.isnan(q1._as_finite_float("not-a-number")))
        self.assertTrue(np.isnan(q1._as_finite_float("NaN")))

    def test_text_water_level_is_used_by_workbook_loader(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "numeric-text-water-level.xlsx"
            workbook = q1.openpyxl.Workbook()
            for index, year in enumerate(q1.YEARS):
                sheet = workbook.active if index == 0 else workbook.create_sheet()
                sheet.title = str(year)
                sheet.append(["year", "month", "day", "time", "water", "flow", "sediment"])
                sheet.append([year, 1, 1, "00:00", "43.27", "100", "1.2"])
            workbook.save(workbook_path)
            loaded = q1.load_hydro_data(workbook_path)
            self.assertTrue(loaded["water_level_m"].eq(43.27).all())
            self.assertTrue(loaded["flow_m3s"].eq(100.0).all())


class RunLocationTests(unittest.TestCase):
    def test_direct_child_with_only_run_record_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs = Path(temp_dir) / "runs"
            run_dir = runs / "run-20260809-2100-test"
            run_dir.mkdir(parents=True)
            (run_dir / "run.md").write_text("# Run record\n", encoding="utf-8")
            with patch.object(q1, "RUNS_DIR", runs):
                q1.validate_output_location(run_dir.resolve())

    def test_nested_run_directory_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs = Path(temp_dir) / "runs"
            nested = runs / "holder" / "run-20260809-2100-test"
            nested.mkdir(parents=True)
            with patch.object(q1, "RUNS_DIR", runs):
                with self.assertRaises(ValueError):
                    q1.validate_output_location(nested.resolve())

    def test_any_existing_generated_evidence_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs = Path(temp_dir) / "runs"
            run_dir = runs / "run-20260809-2100-test"
            (run_dir / "logs").mkdir(parents=True)
            with patch.object(q1, "RUNS_DIR", runs):
                with self.assertRaises(FileExistsError):
                    q1.validate_output_location(run_dir.resolve())

    def test_external_input_path_has_a_report_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            external = (Path(temp_dir) / "external.xlsx").resolve()
            self.assertEqual(q1.report_input_path(external), str(external))


class MovingTimeBlockTests(unittest.TestCase):
    def test_block_pool_is_chronological_and_never_crosses_year(self) -> None:
        observed = synthetic_observed()
        pools = q1.build_moving_time_block_pool(observed, 24)
        for year, blocks in pools.items():
            for positions in blocks:
                part = observed.iloc[positions]
                self.assertTrue(part["year"].eq(year).all())
                self.assertTrue(part["datetime"].is_monotonic_increasing)
                elapsed = part["datetime"].max() - part["datetime"].min()
                self.assertLess(elapsed, pd.Timedelta(hours=24))

    def test_residual_blocks_are_sampled_from_the_same_year(self) -> None:
        observed = synthetic_observed()
        pools = q1.build_moving_time_block_pool(observed, 24)
        residuals = observed["year"].to_numpy(dtype=float) - 2000.0
        target_rows = []
        for year in q1.YEARS:
            target_rows.append(
                {
                    "datetime": datetime(year, 1, 1, 3),
                    "year": year,
                    "sediment_obs_kgm3": np.nan,
                }
            )
        target = pd.DataFrame(target_rows)
        plan = q1.build_residual_time_block_plan(target, observed, pools, 24)
        sampled = q1.sample_missing_residual_time_path(
            plan,
            residuals,
            np.random.default_rng(7),
        )
        np.testing.assert_allclose(sampled, target["year"].to_numpy(dtype=float) - 2000.0)

    def test_cached_integration_weights_match_reference_integrator(self) -> None:
        rows = []
        for year in q1.YEARS:
            start = datetime(year, 1, 1)
            rows.extend(
                [
                    {"datetime": start, "year": year, "value": 1.0},
                    {"datetime": start + timedelta(days=120), "year": year, "value": 2.0},
                    {"datetime": start + timedelta(days=300), "year": year, "value": 4.0},
                ]
            )
        frame = pd.DataFrame(rows)
        plan = q1.build_annual_integration_plan(frame)
        values = frame["value"].to_numpy(dtype=float)
        for year in q1.YEARS:
            positions, weights = plan[year]
            cached = float(np.dot(values[positions], weights))
            part = frame[frame["year"] == year]
            reference = q1.integrate_on_year_grid(
                part["datetime"], part["value"].to_numpy(dtype=float), year
            )
            self.assertAlmostEqual(cached, reference, places=5)

    def test_required_sensitivity_cannot_be_omitted(self) -> None:
        self.assertEqual(q1.validate_block_hours(72, [24, 72, 168]), [24, 72, 168])
        with self.assertRaises(ValueError):
            q1.validate_block_hours(72, [24, 72])


if __name__ == "__main__":
    unittest.main()
