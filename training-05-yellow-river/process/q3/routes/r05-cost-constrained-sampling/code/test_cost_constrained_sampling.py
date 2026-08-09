from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd


CODE_DIR = Path(__file__).resolve().parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import cost_constrained_sampling as model


class CostConstrainedSamplingTests(unittest.TestCase):
    def test_prepare_run_dir_requires_direct_child_with_only_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            route_dir = Path(temporary) / "route"
            runs_dir = route_dir / "runs"
            valid = runs_dir / "run-20260809-0000-test"
            valid.mkdir(parents=True)
            (valid / "run.md").write_text("# Run record\n", encoding="utf-8")
            with patch.object(model, "ROUTE_DIR", route_dir):
                resolved = model.prepare_run_dir(Path("runs") / valid.name)
            self.assertEqual(resolved, valid.resolve())
            self.assertTrue((valid / "validation").is_dir())

            extra = runs_dir / "run-20260809-0001-extra"
            extra.mkdir()
            (extra / "run.md").write_text("# Run record\n", encoding="utf-8")
            (extra / "unexpected.txt").write_text("no\n", encoding="utf-8")
            with patch.object(model, "ROUTE_DIR", route_dir):
                with self.assertRaises(FileExistsError):
                    model.prepare_run_dir(Path("runs") / extra.name)

            nested = runs_dir / "nested" / "run-20260809-0002-nested"
            nested.mkdir(parents=True)
            (nested / "run.md").write_text("# Run record\n", encoding="utf-8")
            with patch.object(model, "ROUTE_DIR", route_dir):
                with self.assertRaises(ValueError):
                    model.prepare_run_dir(nested)

    def test_replay_daily_trigger_adds_next_day_sample(self) -> None:
        dates = pd.date_range("2020-01-01", periods=31, freq="D")
        daily = pd.DataFrame(
            {
                "date": dates,
                "year": 2020,
                "month": 1,
                "water_volume_1e8_m3": [1.0, *([10.0] * 30)],
                "sediment_mass_1e4_t": [1.0] * 31,
            }
        )
        events = pd.DataFrame(
            {"date": [dates[1]], "year": [2020], "month": [1]}
        )
        replay = model.replay_month(
            daily,
            events,
            year=2020,
            month=1,
            interval=14,
            trigger_threshold=0.5,
            scales={target: 1.0 for target in model.TARGETS},
        )
        sampled = replay.reconstruction.loc[replay.reconstruction["sampled"], "date"]
        self.assertIn(dates[2], set(sampled))
        self.assertIn(dates[3], set(sampled))
        self.assertEqual(replay.metrics["trigger_visits"], 2.0)

    def test_month_end_trigger_carries_followups_into_next_month(self) -> None:
        dates = pd.date_range("2020-01-28", "2020-02-29", freq="D")
        water = np.ones(len(dates))
        water[dates >= pd.Timestamp("2020-01-31")] = 10.0
        daily = pd.DataFrame(
            {
                "date": dates,
                "year": dates.year,
                "month": dates.month,
                "water_volume_1e8_m3": water,
                "sediment_mass_1e4_t": np.ones(len(dates)),
            }
        )
        events = pd.DataFrame(columns=["date", "year", "month"])
        replay = model.replay_month(
            daily,
            events,
            year=2020,
            month=2,
            interval=14,
            trigger_threshold=99.0,
            previous_trigger_threshold=0.5,
            scales={target: 1.0 for target in model.TARGETS},
        )
        reconstruction = replay.reconstruction.set_index("date")
        self.assertTrue(reconstruction.at[pd.Timestamp("2020-02-01"), "sampled"])
        self.assertTrue(reconstruction.at[pd.Timestamp("2020-02-02"), "sampled"])
        self.assertTrue(
            reconstruction.at[
                pd.Timestamp("2020-02-01"), "cross_month_trigger_action"
            ]
        )
        self.assertTrue(
            reconstruction.at[
                pd.Timestamp("2020-02-02"), "cross_month_trigger_visit"
            ]
        )
        self.assertEqual(replay.metrics["cross_month_trigger_actions"], 2.0)
        self.assertEqual(replay.metrics["cross_month_trigger_visits"], 1.0)

    def test_month_start_change_uses_previous_day_with_current_threshold(self) -> None:
        dates = pd.date_range("2020-01-29", "2020-02-29", freq="D")
        water = np.ones(len(dates))
        water[dates >= pd.Timestamp("2020-02-01")] = 10.0
        daily = pd.DataFrame(
            {
                "date": dates,
                "year": dates.year,
                "month": dates.month,
                "water_volume_1e8_m3": water,
                "sediment_mass_1e4_t": np.ones(len(dates)),
            }
        )
        events = pd.DataFrame(columns=["date", "year", "month"])
        replay = model.replay_month(
            daily,
            events,
            year=2020,
            month=2,
            interval=14,
            trigger_threshold=0.5,
            previous_trigger_threshold=99.0,
            scales={target: 1.0 for target in model.TARGETS},
        )
        sampled = set(
            replay.reconstruction.loc[replay.reconstruction["sampled"], "date"]
        )
        self.assertIn(pd.Timestamp("2020-02-02"), sampled)
        self.assertIn(pd.Timestamp("2020-02-03"), sampled)
        self.assertEqual(replay.metrics["calendar_boundary_comparisons"], 1.0)

    def test_month_end_event_can_be_captured_by_next_month_sample(self) -> None:
        dates = pd.date_range("2021-01-01", "2021-12-31", freq="D")
        daily = pd.DataFrame(
            {
                "date": dates,
                "year": dates.year,
                "month": dates.month,
                "water_volume_1e8_m3": np.ones(len(dates)),
                "sediment_mass_1e4_t": np.ones(len(dates)),
            }
        )
        events = pd.DataFrame(
            {
                "date": [pd.Timestamp("2021-08-31")],
                "year": [2021],
                "month": [8],
            }
        )
        for interval in (7, 14):
            with self.subTest(interval=interval):
                policy = {
                    month: (interval, None, 1) for month in range(1, 13)
                }
                replay = model.evaluate_monthly_policy(
                    daily,
                    events,
                    years=(2021,),
                    scales={target: 1.0 for target in model.TARGETS},
                    policy=policy,
                )
                sampled = set(
                    replay.reconstruction.loc[
                        replay.reconstruction["sampled"], "date"
                    ]
                )
                self.assertIn(pd.Timestamp("2021-09-01"), sampled)
                self.assertTrue(bool(replay.event_records.iloc[0]["captured"]))
                self.assertEqual(replay.metrics["event_capture_rate"], 1.0)

    def test_year_end_event_can_be_captured_by_next_year_sample(self) -> None:
        dates = pd.date_range("2020-01-01", "2021-12-31", freq="D")
        daily = pd.DataFrame(
            {
                "date": dates,
                "year": dates.year,
                "month": dates.month,
                "water_volume_1e8_m3": np.ones(len(dates)),
                "sediment_mass_1e4_t": np.ones(len(dates)),
            }
        )
        events = pd.DataFrame(
            {
                "date": [pd.Timestamp("2020-12-31")],
                "year": [2020],
                "month": [12],
            }
        )
        policy = {month: (14, None, 1) for month in range(1, 13)}
        replay = model.evaluate_monthly_policy(
            daily,
            events,
            years=(2020, 2021),
            scales={target: 1.0 for target in model.TARGETS},
            policy=policy,
        )
        self.assertTrue(bool(replay.event_records.iloc[0]["captured"]))
        self.assertEqual(replay.metrics["event_capture_rate"], 1.0)

    def test_event_stability_weighting_and_small_sample_bounds(self) -> None:
        dates = pd.to_datetime(["2019-01-05", "2021-02-06"])
        events = pd.DataFrame(
            {
                "date": dates,
                "year": [2019, 2021],
                "month": [1, 2],
                "main_direction": ["flow_rise", "sediment_fall"],
                "abrupt_score": [3.1, 4.2],
            }
        )
        stability = pd.DataFrame(
            {
                "baseline_event_date": dates,
                "main_direction": ["flow_rise", "sediment_fall"],
                "baseline_score": [3.1, 4.2],
                "matched_parameter_combinations": [1, 4],
                "total_parameter_combinations": [4, 4],
                "match_rate_within_7d": [0.25, 1.0],
            }
        )
        captures = pd.DataFrame(
            {
                "date": dates,
                "year": [2019, 2021],
                "month": [1, 2],
                "captured": [False, True],
                "split": [model.CALIBRATION_SPLIT, model.CONDITIONAL_HOLDOUT_SPLIT],
            }
        )
        details, summary = model.event_stability_validation(events, stability, captures)
        combined = summary.set_index("split").loc["combined_2018_2021_descriptive"]
        self.assertEqual(len(details), 2)
        self.assertAlmostEqual(combined["stability_weighted_capture_rate"], 0.8)
        self.assertTrue(combined["small_sample_caution"])
        self.assertLess(combined["raw_clopper_pearson_95_lower"], 0.5)
        self.assertGreater(combined["raw_clopper_pearson_95_upper"], 0.5)

    def test_dynamic_trigger_ablation_requires_same_base_signature(self) -> None:
        rows = []
        for split in (model.CALIBRATION_SPLIT, model.CONDITIONAL_HOLDOUT_SPLIT):
            for policy, cost, trigger in (
                ("optimized_dynamic", 100.0, True),
                ("optimized_base_only_ablation", 80.0, False),
            ):
                rows.append(
                    {
                        "split": split,
                        "policy": policy,
                        "dynamic_trigger_enabled": trigger,
                        "base_interval_signature": "01:14|02:14",
                        "annual_cost_units": cost,
                        "annual_visits": cost / 5,
                        "water_wape": 0.08,
                        "sediment_wape": 0.20,
                        "event_capture_rate": 0.80,
                    }
                )
        ablation = model.dynamic_trigger_ablation(pd.DataFrame(rows))
        self.assertEqual(len(ablation), 4)
        base = ablation[ablation["policy"] == "optimized_base_only_ablation"]
        self.assertTrue(np.allclose(base["delta_vs_dynamic_annual_cost_units"], -20.0))

    def test_cost_sensitivity_reports_each_weight_for_each_period(self) -> None:
        monthly = pd.DataFrame(
            {
                "year": [2022, 2023],
                "expected_total_visits": [10.0, 12.0],
            }
        )
        old = pd.DataFrame(
            {
                "year": [2022, 2022, 2023, 2023],
                "sample_date": pd.to_datetime(
                    ["2022-01-01", "2022-01-01", "2023-01-01", "2023-01-02"]
                ),
                "sample_datetime": pd.to_datetime(
                    [
                        "2022-01-01 09:00",
                        "2022-01-01 18:00",
                        "2023-01-01 09:00",
                        "2023-01-02 09:00",
                    ]
                ),
            }
        )
        sensitivity = model.cost_coefficient_sensitivity(monthly, old)
        self.assertEqual(len(sensitivity), len(model.COST_SCENARIOS) * 3)
        self.assertEqual(
            set(sensitivity["scenario"]), {scenario[0] for scenario in model.COST_SCENARIOS}
        )
        self.assertTrue(
            np.isfinite(sensitivity["expected_cost_reduction_vs_old_pct"]).all()
        )


if __name__ == "__main__":
    unittest.main()
