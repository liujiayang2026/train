from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.stats import beta, norm


ROUTE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parents[5]
DEFAULT_R04_RUN = (
    PACKAGE_DIR
    / "process"
    / "q3"
    / "routes"
    / "r04-monthly-flux-forecast"
    / "runs"
    / "run-20260809-2103-figure-label-clarity"
)
DEFAULT_R04_FORECAST = DEFAULT_R04_RUN / "results" / "monthly_forecast_2022_2023.csv"
DEFAULT_R04_STRATEGY = DEFAULT_R04_RUN / "results" / "monthly_sampling_strategy.csv"
DEFAULT_R04_OLD_SCHEDULE = DEFAULT_R04_RUN / "results" / "sampling_schedule_2022_2023.csv"
DEFAULT_Q2_RUN = (
    PACKAGE_DIR
    / "process"
    / "q2"
    / "routes"
    / "r01-interpolated-daily-pattern"
    / "runs"
    / "run-20260809-2036-time-block-q1"
)
DEFAULT_Q2_DAILY = (
    DEFAULT_Q2_RUN / "results" / "data" / "processed" / "daily_flux_series.csv"
)
DEFAULT_Q2_EVENTS = DEFAULT_Q2_RUN / "results" / "tables" / "abrupt_change_events.csv"
DEFAULT_Q2_EVENT_STABILITY = DEFAULT_Q2_RUN / "validation" / "abrupt_event_stability.csv"

CALIBRATION_YEARS = (2018, 2019, 2020)
CONDITIONAL_HOLDOUT_YEARS = (2021,)
CALIBRATION_SPLIT = "calibration_2018_2020"
CONDITIONAL_HOLDOUT_SPLIT = "strategy_conditional_holdout_2021"
INTERVALS = (3, 5, 7, 10, 14)
TRIGGER_THRESHOLDS = (1.0, 1.5, 2.0, 2.5)
TRIGGER_FOLLOWUP_DAYS = 2
EVENT_TOLERANCE_DAYS = 1
VISIT_COST = 4.0
ASSAY_COST = 1.0
PRE_SPECIFIED_WATER_WAPE = 0.10
PRE_SPECIFIED_SEDIMENT_WAPE = 0.25
PRE_SPECIFIED_EVENT_CAPTURE = 0.80
TARGETS = ("water_volume_1e8_m3", "sediment_mass_1e4_t")
RISK_RANK = {"low": 0, "medium": 1, "high": 2}
RISK_MAX_GAP = {"low": 14, "medium": 10, "high": 5}
COST_SCENARIOS = (
    ("assay_heavy", 1.0, 4.0),
    ("balanced", 1.0, 1.0),
    ("visit_light", 2.0, 1.0),
    ("pre_specified", VISIT_COST, ASSAY_COST),
    ("visit_heavy", 8.0, 1.0),
)


@dataclass(frozen=True)
class ReplayResult:
    metrics: dict[str, float]
    reconstruction: pd.DataFrame
    event_records: pd.DataFrame


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def csv_source_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        next(reader, None)
        return sum(1 for _ in reader)


def prepare_run_dir(run_dir: Path) -> Path:
    candidate = run_dir if run_dir.is_absolute() else ROUTE_DIR / run_dir
    resolved = candidate.resolve()
    runs_dir = (ROUTE_DIR / "runs").resolve()
    if resolved.parent != runs_dir:
        raise ValueError(f"run-dir must be a direct child of {runs_dir}")
    if not resolved.is_dir():
        raise FileNotFoundError("Create the run directory and run.md before executing the model")
    entries = list(resolved.iterdir())
    if len(entries) != 1 or entries[0].name != "run.md" or not entries[0].is_file():
        raise FileExistsError(
            "A new run directory may contain only its pre-created run.md before execution"
        )
    for name in ("results", "figures", "validation", "logs"):
        folder = resolved / name
        folder.mkdir(parents=True, exist_ok=True)
    return resolved


def load_inputs(
    q2_daily_path: Path,
    q2_events_path: Path,
    q2_event_stability_path: Path,
    r04_forecast_path: Path,
    r04_strategy_path: Path,
    r04_old_schedule_path: Path,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    required = [
        q2_daily_path,
        q2_events_path,
        q2_event_stability_path,
        r04_forecast_path,
        r04_strategy_path,
        r04_old_schedule_path,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing inputs:\n" + "\n".join(missing))

    daily = pd.read_csv(q2_daily_path, parse_dates=["date"])
    needed_daily = ["date", *TARGETS, "year", "month"]
    absent = [column for column in needed_daily if column not in daily.columns]
    if absent:
        raise ValueError(f"Daily proxy missing columns: {absent}")
    daily = daily[needed_daily].copy()
    daily = daily[daily["year"].between(2018, 2021)].sort_values("date").reset_index(drop=True)
    expected = pd.date_range("2018-01-01", "2021-12-31", freq="D")
    if not pd.DatetimeIndex(daily["date"]).equals(expected):
        raise AssertionError("Historical proxy must be a complete daily calendar for 2018-2021")
    if not (daily[list(TARGETS)] > 0).all().all():
        raise AssertionError("Historical proxy targets must be positive")

    events = pd.read_csv(q2_events_path, parse_dates=["date"])
    needed_events = ["date", "year", "month", "main_direction"]
    absent_events = [column for column in needed_events if column not in events.columns]
    if absent_events:
        raise ValueError(f"Abrupt-event table missing columns: {absent_events}")
    events = events[events["year"].between(2018, 2021)].copy()
    if events["date"].duplicated().any():
        raise AssertionError("Abrupt-event dates must be unique")

    stability = pd.read_csv(q2_event_stability_path, parse_dates=["baseline_event_date"])
    needed_stability = [
        "baseline_event_date",
        "main_direction",
        "baseline_score",
        "matched_parameter_combinations",
        "total_parameter_combinations",
        "match_rate_within_7d",
    ]
    absent_stability = [column for column in needed_stability if column not in stability.columns]
    if absent_stability:
        raise ValueError(f"Abrupt-event stability table missing columns: {absent_stability}")
    stability = stability[
        stability["baseline_event_date"].dt.year.between(2018, 2021)
    ].copy()
    if stability["baseline_event_date"].duplicated().any():
        raise AssertionError("Abrupt-event stability dates must be unique")
    if not stability["match_rate_within_7d"].between(0.0, 1.0).all():
        raise AssertionError("Abrupt-event stability match rates must be in [0, 1]")
    recomputed_rate = (
        stability["matched_parameter_combinations"]
        / stability["total_parameter_combinations"]
    )
    if not np.allclose(recomputed_rate, stability["match_rate_within_7d"], atol=1e-12):
        raise AssertionError("Abrupt-event stability counts and match rates disagree")

    forecast = pd.read_csv(r04_forecast_path, parse_dates=["date"])
    strategy = pd.read_csv(r04_strategy_path, parse_dates=["date"])
    old_schedule = pd.read_csv(
        r04_old_schedule_path, parse_dates=["sample_datetime", "date"]
    )
    if old_schedule.empty:
        raise AssertionError("r04 old sampling schedule must be non-empty")
    if old_schedule["sample_datetime"].duplicated().any():
        raise AssertionError("r04 old sampling schedule datetimes must be unique")
    if not old_schedule["sample_datetime"].dt.normalize().equals(
        old_schedule["date"].dt.normalize()
    ):
        raise AssertionError("r04 old sampling datetimes and calendar dates disagree")
    old_schedule["sample_date"] = old_schedule["date"].dt.normalize()
    if len(forecast) != 24 or len(strategy) != 24:
        raise AssertionError("r04 forecast and risk strategy must each contain 24 months")
    expected_months = {(year, month) for year in (2022, 2023) for month in range(1, 13)}
    if set(zip(forecast["year"], forecast["month"])) != expected_months:
        raise AssertionError("r04 forecast must cover 2022-2023")
    if set(zip(strategy["year"], strategy["month"])) != expected_months:
        raise AssertionError("r04 risk strategy must cover 2022-2023")
    if set(old_schedule["sample_datetime"].dt.year) != {2022, 2023}:
        raise AssertionError("r04 old sampling schedule must cover 2022-2023")
    return daily, events, stability, forecast, strategy, old_schedule


def change_scales(daily: pd.DataFrame) -> dict[str, float]:
    calibration = daily[daily["year"].isin(CALIBRATION_YEARS)]
    scales: dict[str, float] = {}
    for target in TARGETS:
        values = np.log1p(calibration[target].to_numpy(dtype=float))
        changes = np.abs(np.diff(values))
        scale = float(np.quantile(changes, 0.90))
        if not np.isfinite(scale) or scale <= 0:
            raise AssertionError(f"Invalid change scale for {target}: {scale}")
        scales[target] = scale
    return scales


def conservative_risk_map(strategy: pd.DataFrame) -> dict[int, str]:
    risk: dict[int, str] = {}
    for month, group in strategy.groupby("month"):
        levels = group["risk_level"].astype(str).tolist()
        risk[int(month)] = max(levels, key=lambda item: RISK_RANK[item])
    if set(risk) != set(range(1, 13)):
        raise AssertionError("Risk strategy must cover all calendar months")
    return risk


def base_dates(year: int, month: int, interval: int) -> list[pd.Timestamp]:
    start = pd.Timestamp(year=year, month=month, day=1)
    end = start + pd.offsets.MonthBegin(1)
    return list(pd.date_range(start, end, freq=f"{interval}D", inclusive="left"))


def replay_month(
    daily: pd.DataFrame,
    month_events: pd.DataFrame,
    year: int,
    month: int,
    interval: int,
    trigger_threshold: float | None,
    scales: dict[str, float],
    assays_per_visit: int = 1,
    previous_trigger_threshold: float | None = None,
) -> ReplayResult:
    month_start = pd.Timestamp(year=year, month=month, day=1)
    month_end = month_start + pd.offsets.MonthBegin(1)
    month_data = daily[
        (daily["date"] >= month_start) & (daily["date"] < month_end)
    ].copy()
    expected_dates = pd.date_range(month_start, month_end, freq="D", inclusive="left")
    if not pd.DatetimeIndex(month_data["date"]).equals(expected_dates):
        raise AssertionError(f"Incomplete daily calendar for {year}-{month:02d}")
    indexed = month_data.set_index("date")
    bases = base_dates(year, month, interval)
    triggered: set[pd.Timestamp] = set()
    trigger_sources: dict[pd.Timestamp, set[pd.Timestamp]] = {}
    month_start_comparison = 0

    if trigger_threshold is not None or previous_trigger_threshold is not None:
        # A trigger on either of the previous month's last two days can create
        # an action in this month.  Include one additional day so the first of
        # those two source dates still has a genuine previous-day comparison.
        context_start = month_start - pd.Timedelta(days=3)
        context = daily[
            (daily["date"] >= context_start) & (daily["date"] < month_end)
        ].copy()
        context_indexed = context.set_index("date")
        monitoring_dates = list(pd.DatetimeIndex(context["date"]))
        for previous, current in zip(monitoring_dates[:-1], monitoring_dates[1:]):
            if current < month_start - pd.Timedelta(days=2):
                continue
            threshold = (
                previous_trigger_threshold if current < month_start else trigger_threshold
            )
            if threshold is None:
                continue
            if current == month_start:
                month_start_comparison = 1
            scores = []
            for target in TARGETS:
                previous_value = float(context_indexed.at[previous, target])
                current_value = float(context_indexed.at[current, target])
                daily_change = abs(math.log1p(current_value) - math.log1p(previous_value))
                scores.append(daily_change / scales[target])
            if max(scores) >= threshold:
                for offset in range(1, TRIGGER_FOLLOWUP_DAYS + 1):
                    followup = current + pd.Timedelta(days=offset)
                    if month_start <= followup < month_end:
                        triggered.add(followup)
                        trigger_sources.setdefault(followup, set()).add(current)

    sampled_dates = sorted(set(bases) | triggered)
    base_set = set(bases)
    incoming_actions = {
        date
        for date, sources in trigger_sources.items()
        if any(source < month_start for source in sources)
    }
    incoming_visits = incoming_actions - base_set
    positions = (month_data["date"] - month_data["date"].iloc[0]).dt.days.to_numpy(dtype=float)
    sample_positions = np.array(
        [(date - month_data["date"].iloc[0]).days for date in sampled_dates], dtype=float
    )
    reconstruction = month_data[["date", "year", "month", *TARGETS]].copy()
    reconstruction["sampled"] = reconstruction["date"].isin(sampled_dates)
    reconstruction["base_sample"] = reconstruction["date"].isin(bases)
    reconstruction["trigger_sample"] = reconstruction["date"].isin(triggered - base_set)
    reconstruction["cross_month_trigger_action"] = reconstruction["date"].isin(
        incoming_actions
    )
    reconstruction["cross_month_trigger_visit"] = reconstruction["date"].isin(
        incoming_visits
    )
    reconstruction["month_start_change_evaluated"] = False
    if month_start_comparison:
        reconstruction.loc[
            reconstruction["date"] == month_start, "month_start_change_evaluated"
        ] = True

    metrics: dict[str, float] = {
        "visits": float(len(sampled_dates)),
        "base_visits": float(len(bases)),
        "trigger_visits": float(len(set(sampled_dates) - base_set)),
        "assays": float(len(sampled_dates) * assays_per_visit),
        "cost_units": float(len(sampled_dates) * (VISIT_COST + assays_per_visit * ASSAY_COST)),
        "max_gap_days": 0.0,
        "calendar_boundary_comparisons": float(month_start_comparison),
        "cross_month_trigger_actions": float(len(incoming_actions)),
        "cross_month_trigger_visits": float(len(incoming_visits)),
    }
    month_length = len(month_data)
    boundary_positions = np.r_[sample_positions, month_length - 1]
    metrics["max_gap_days"] = float(np.diff(np.unique(boundary_positions)).max(initial=0.0))

    for target in TARGETS:
        actual = month_data[target].to_numpy(dtype=float)
        sample_values = indexed.loc[sampled_dates, target].to_numpy(dtype=float)
        predicted = np.interp(positions, sample_positions, sample_values)
        reconstruction[f"reconstructed_{target}"] = predicted
        metrics[f"{target}_abs_error"] = float(np.abs(actual - predicted).sum())
        metrics[f"{target}_total"] = float(actual.sum())

    event_dates = pd.DatetimeIndex(month_events["date"])
    captured_flags = []
    for event_date in event_dates:
        captured = any(
            abs((sample_date - event_date).days) <= EVENT_TOLERANCE_DAYS
            for sample_date in sampled_dates
        )
        captured_flags.append(captured)
    event_records = pd.DataFrame(
        {
            "date": event_dates,
            "year": year,
            "month": month,
            "captured": captured_flags,
        }
    )
    metrics["event_count"] = float(len(event_dates))
    metrics["events_captured"] = float(sum(captured_flags))
    return ReplayResult(metrics, reconstruction, event_records)


def option_performance(
    daily: pd.DataFrame,
    events: pd.DataFrame,
    scales: dict[str, float],
    risk_map: dict[int, str],
) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in range(1, 13):
        for interval in INTERVALS:
            if interval > RISK_MAX_GAP[risk_map[month]]:
                continue
            for threshold in TRIGGER_THRESHOLDS:
                for previous_threshold in TRIGGER_THRESHOLDS:
                    totals: dict[str, float] = {}
                    for year in CALIBRATION_YEARS:
                        month_events = events[
                            (events["year"] == year) & (events["month"] == month)
                        ]
                        replay = replay_month(
                            daily,
                            month_events,
                            year,
                            month,
                            interval,
                            threshold,
                            scales,
                            previous_trigger_threshold=previous_threshold,
                        )
                        for key, value in replay.metrics.items():
                            totals[key] = totals.get(key, 0.0) + value
                    row: dict[str, float | int | str] = {
                        "month": month,
                        "risk_level": risk_map[month],
                        "previous_trigger_threshold": previous_threshold,
                        "base_interval_days": interval,
                        "trigger_threshold": threshold,
                        "calibration_years": len(CALIBRATION_YEARS),
                    }
                    averaged_metrics = {
                        "visits",
                        "base_visits",
                        "trigger_visits",
                        "assays",
                        "cost_units",
                        "calendar_boundary_comparisons",
                        "cross_month_trigger_actions",
                        "cross_month_trigger_visits",
                    }
                    for key, value in totals.items():
                        row[key] = (
                            value / len(CALIBRATION_YEARS)
                            if key in averaged_metrics
                            else value
                        )
                    row["trigger_rate"] = float(
                        totals["trigger_visits"] / totals["base_visits"]
                    )
                    row["water_wape"] = float(
                        totals["water_volume_1e8_m3_abs_error"]
                        / totals["water_volume_1e8_m3_total"]
                    )
                    row["sediment_wape"] = float(
                        totals["sediment_mass_1e4_t_abs_error"]
                        / totals["sediment_mass_1e4_t_total"]
                    )
                    row["event_capture_rate"] = (
                        float(totals["events_captured"] / totals["event_count"])
                        if totals["event_count"]
                        else np.nan
                    )
                    rows.append(row)
    return pd.DataFrame(rows)


def policy_metrics(selected: pd.DataFrame) -> dict[str, float | str]:
    water_error = float(selected["water_volume_1e8_m3_abs_error"].sum())
    water_total = float(selected["water_volume_1e8_m3_total"].sum())
    sediment_error = float(selected["sediment_mass_1e4_t_abs_error"].sum())
    sediment_total = float(selected["sediment_mass_1e4_t_total"].sum())
    event_count = float(selected["event_count"].sum())
    captured = float(selected["events_captured"].sum())
    signature = "|".join(
        f"{int(row.month):02d}:{int(row.base_interval_days)}@{float(row.trigger_threshold):g}"
        for row in selected.sort_values("month").itertuples()
    )
    return {
        "annual_cost_units": float(selected["cost_units"].sum()),
        "annual_visits": float(selected["visits"].sum()),
        "water_wape": water_error / water_total,
        "sediment_wape": sediment_error / sediment_total,
        "event_capture_rate": captured / event_count if event_count else 1.0,
        "policy_signature": signature,
    }


def solve_policy(
    options: pd.DataFrame,
    water_limit: float,
    sediment_limit: float,
    event_capture_min: float,
) -> tuple[pd.DataFrame | None, dict[str, float | str]]:
    frame = options.reset_index(drop=True)
    n = len(frame)
    constraints: list[np.ndarray] = []
    lower: list[float] = []
    upper: list[float] = []
    for month in range(1, 13):
        row = (frame["month"].to_numpy() == month).astype(float)
        constraints.append(row)
        lower.append(1.0)
        upper.append(1.0)
    for month in range(1, 13):
        previous_month = 12 if month == 1 else month - 1
        for threshold in TRIGGER_THRESHOLDS:
            incoming_previous_threshold = (
                (frame["month"].to_numpy() == month)
                & np.isclose(
                    frame["previous_trigger_threshold"].to_numpy(dtype=float),
                    threshold,
                )
            ).astype(float)
            selected_previous_month_threshold = (
                (frame["month"].to_numpy() == previous_month)
                & np.isclose(
                    frame["trigger_threshold"].to_numpy(dtype=float), threshold
                )
            ).astype(float)
            constraints.append(
                incoming_previous_threshold - selected_previous_month_threshold
            )
            lower.append(0.0)
            upper.append(0.0)

    water_total = float(
        frame.groupby("month")["water_volume_1e8_m3_total"].first().sum()
    )
    sediment_total = float(
        frame.groupby("month")["sediment_mass_1e4_t_total"].first().sum()
    )
    event_total = float(frame.groupby("month")["event_count"].first().sum())
    constraints.append(frame["water_volume_1e8_m3_abs_error"].to_numpy(dtype=float))
    lower.append(-np.inf)
    upper.append(water_limit * water_total)
    constraints.append(frame["sediment_mass_1e4_t_abs_error"].to_numpy(dtype=float))
    lower.append(-np.inf)
    upper.append(sediment_limit * sediment_total)
    constraints.append(-frame["events_captured"].to_numpy(dtype=float))
    lower.append(-np.inf)
    upper.append(-event_capture_min * event_total)

    # Cost is primary.  The tiny normalized terms only make equal-cost MILP
    # optima deterministic by preferring lower reconstruction error and more
    # captured events; a one-unit cost difference always dominates them.
    objective = frame["cost_units"].to_numpy(dtype=float).copy()
    objective += 1e-6 * (
        frame["water_volume_1e8_m3_abs_error"].to_numpy(dtype=float) / water_total
        + frame["sediment_mass_1e4_t_abs_error"].to_numpy(dtype=float) / sediment_total
        - frame["events_captured"].to_numpy(dtype=float) / max(event_total, 1.0)
    )
    result = milp(
        c=objective,
        integrality=np.ones(n, dtype=int),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(np.vstack(constraints), np.array(lower), np.array(upper)),
        options={"time_limit": 30.0},
    )
    if not result.success or result.x is None:
        return None, {"solver_status": str(result.message)}
    selected = frame.loc[result.x > 0.5].copy().sort_values("month")
    if len(selected) != 12:
        raise AssertionError(f"MILP selected {len(selected)} monthly options, expected 12")
    selected_lookup = selected.set_index("month")
    for month in range(1, 13):
        previous_month = 12 if month == 1 else month - 1
        incoming = float(selected_lookup.loc[month, "previous_trigger_threshold"])
        outgoing = float(selected_lookup.loc[previous_month, "trigger_threshold"])
        if not math.isclose(incoming, outgoing, rel_tol=0.0, abs_tol=1e-12):
            raise AssertionError(
                f"Inconsistent threshold transition {previous_month:02d}->{month:02d}: "
                f"{outgoing} != {incoming}"
            )
    metrics = policy_metrics(selected)
    metrics["solver_status"] = str(result.message)
    return selected, metrics


def epsilon_constraint_analysis(options: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, float | str | bool]] = []
    solutions: dict[str, dict[str, float | str]] = {}
    for water_limit in (0.08, 0.10, 0.12, 0.15, 0.20):
        for sediment_limit in (0.18, 0.22, 0.25, 0.30, 0.35):
            for capture_min in (0.60, 0.70, 0.80, 0.90, 1.00):
                selected, metrics = solve_policy(options, water_limit, sediment_limit, capture_min)
                row: dict[str, float | str | bool] = {
                    "water_wape_limit": water_limit,
                    "sediment_wape_limit": sediment_limit,
                    "event_capture_min": capture_min,
                    "feasible": selected is not None,
                    "solver_status": metrics["solver_status"],
                }
                if selected is not None:
                    row.update(metrics)
                    signature = str(metrics["policy_signature"])
                    if signature not in solutions:
                        solutions[signature] = dict(metrics)
                rows.append(row)

    sensitivity = pd.DataFrame(rows)
    unique = pd.DataFrame(list(solutions.values()))
    if unique.empty:
        raise RuntimeError("No feasible policy found in threshold sensitivity grid")
    dominated = np.zeros(len(unique), dtype=bool)
    for i, candidate in unique.iterrows():
        for j, challenger in unique.iterrows():
            if i == j:
                continue
            weak = (
                challenger["annual_cost_units"] <= candidate["annual_cost_units"]
                and challenger["water_wape"] <= candidate["water_wape"]
                and challenger["sediment_wape"] <= candidate["sediment_wape"]
                and challenger["event_capture_rate"] >= candidate["event_capture_rate"]
            )
            strict = (
                challenger["annual_cost_units"] < candidate["annual_cost_units"]
                or challenger["water_wape"] < candidate["water_wape"]
                or challenger["sediment_wape"] < candidate["sediment_wape"]
                or challenger["event_capture_rate"] > candidate["event_capture_rate"]
            )
            if weak and strict:
                dominated[i] = True
                break
    unique["epsilon_grid_nondominated"] = ~dominated
    approx_nondominated = unique[unique["epsilon_grid_nondominated"]].sort_values(
        ["annual_cost_units", "sediment_wape", "water_wape"]
    )
    return sensitivity, approx_nondominated


def aggregate_replays(replays: list[ReplayResult], years_count: int) -> ReplayResult:
    totals: dict[str, float] = {}
    for replay in replays:
        for key, value in replay.metrics.items():
            totals[key] = totals.get(key, 0.0) + value
    metrics = {
        "annual_cost_units": totals["cost_units"] / years_count,
        "annual_visits": totals["visits"] / years_count,
        "annual_assays": totals["assays"] / years_count,
        "water_wape": totals["water_volume_1e8_m3_abs_error"]
        / totals["water_volume_1e8_m3_total"],
        "sediment_wape": totals["sediment_mass_1e4_t_abs_error"]
        / totals["sediment_mass_1e4_t_total"],
        "event_capture_rate": totals["events_captured"] / totals["event_count"]
        if totals["event_count"]
        else 1.0,
        "events_captured": totals["events_captured"],
        "event_count": totals["event_count"],
        "max_gap_days": max(replay.metrics["max_gap_days"] for replay in replays),
        "calendar_boundary_comparisons": totals["calendar_boundary_comparisons"],
        "cross_month_trigger_actions": totals["cross_month_trigger_actions"],
        "cross_month_trigger_visits": totals["cross_month_trigger_visits"],
    }
    reconstruction = pd.concat([item.reconstruction for item in replays], ignore_index=True)
    event_records = pd.concat([item.event_records for item in replays], ignore_index=True)
    return ReplayResult(metrics, reconstruction, event_records)


def score_events_on_global_calendar(
    events: pd.DataFrame,
    reconstruction: pd.DataFrame,
) -> pd.DataFrame:
    """Score event capture against the merged calendar, not a month-local subset."""
    event_records = events[["date", "year", "month"]].copy().sort_values("date")
    sampled_dates = pd.DatetimeIndex(
        reconstruction.loc[reconstruction["sampled"], "date"].drop_duplicates()
    )
    captured_flags: list[bool] = []
    for event_date in pd.DatetimeIndex(event_records["date"]):
        captured_flags.append(
            bool(
                len(sampled_dates)
                and np.any(
                    np.abs((sampled_dates - event_date).days)
                    <= EVENT_TOLERANCE_DAYS
                )
            )
        )
    event_records["captured"] = captured_flags
    return event_records.reset_index(drop=True)


def evaluate_monthly_policy(
    daily: pd.DataFrame,
    events: pd.DataFrame,
    years: tuple[int, ...],
    scales: dict[str, float],
    policy: dict[int, tuple[int, float | None, int]],
) -> ReplayResult:
    replays: list[ReplayResult] = []
    for year in years:
        for month in range(1, 13):
            interval, threshold, assays = policy[month]
            month_events = events[(events["year"] == year) & (events["month"] == month)]
            previous_month = 12 if month == 1 else month - 1
            previous_threshold = policy[previous_month][1]
            replays.append(
                replay_month(
                    daily,
                    month_events,
                    year,
                    month,
                    interval,
                    threshold,
                    scales,
                    assays,
                    previous_threshold,
                )
            )
    aggregated = aggregate_replays(replays, len(years))
    split_events = events[events["year"].isin(years)].copy()
    event_records = score_events_on_global_calendar(
        split_events,
        aggregated.reconstruction,
    )
    metrics = dict(aggregated.metrics)
    metrics["events_captured"] = float(event_records["captured"].sum())
    metrics["event_count"] = float(len(event_records))
    metrics["event_capture_rate"] = (
        metrics["events_captured"] / metrics["event_count"]
        if metrics["event_count"]
        else 1.0
    )
    return ReplayResult(metrics, aggregated.reconstruction, event_records)


def replay_baselines(
    daily: pd.DataFrame,
    events: pd.DataFrame,
    scales: dict[str, float],
    selected: pd.DataFrame,
    risk_map: dict[int, str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    optimized_policy = {
        int(row.month): (int(row.base_interval_days), float(row.trigger_threshold), 1)
        for row in selected.itertuples()
    }
    base_only_ablation = {
        month: (settings[0], None, settings[2])
        for month, settings in optimized_policy.items()
    }
    old_settings = {"low": (10, None, 1), "medium": (5, None, 2), "high": (2, None, 3)}
    policies: dict[str, dict[int, tuple[int, float | None, int]]] = {
        "optimized_dynamic": optimized_policy,
        "optimized_base_only_ablation": base_only_ablation,
        "old_r04_heuristic": {month: old_settings[risk_map[month]] for month in range(1, 13)},
    }
    for interval in INTERVALS:
        policies[f"uniform_{interval}d"] = {
            month: (interval, None, 1) for month in range(1, 13)
        }

    rows: list[dict[str, float | str | bool]] = []
    selected_holdout: ReplayResult | None = None
    selected_calibration: ReplayResult | None = None
    selected_event_frames: list[pd.DataFrame] = []
    calibration_results: dict[str, ReplayResult] = {}
    for split, years in (
        (CALIBRATION_SPLIT, CALIBRATION_YEARS),
        (CONDITIONAL_HOLDOUT_SPLIT, CONDITIONAL_HOLDOUT_YEARS),
    ):
        for name, policy in policies.items():
            replay = evaluate_monthly_policy(daily, events, years, scales, policy)
            base_signature = "|".join(
                f"{month:02d}:{policy[month][0]}" for month in range(1, 13)
            )
            if split == CALIBRATION_SPLIT:
                calibration_results[name] = replay
            if name == "optimized_dynamic" and split == CALIBRATION_SPLIT:
                selected_calibration = replay
            if name == "optimized_dynamic" and split == CONDITIONAL_HOLDOUT_SPLIT:
                selected_holdout = replay
            if name == "optimized_dynamic":
                selected_event_frames.append(replay.event_records.assign(split=split))
            rows.append(
                {
                    "split": split,
                    "policy": name,
                    "risk_assignment": (
                        "conservative_calendar_month_max_across_r04_2022_2023"
                        if name == "old_r04_heuristic"
                        else "not_applicable"
                    ),
                    "dynamic_trigger_enabled": any(
                        settings[1] is not None for settings in policy.values()
                    ),
                    "base_interval_signature": base_signature,
                    **replay.metrics,
                }
            )

    if selected_holdout is None or selected_calibration is None:
        raise AssertionError("Selected policy replay was not generated")
    optimized_cost = calibration_results["optimized_dynamic"].metrics["annual_cost_units"]
    uniform_names = [name for name in policies if name.startswith("uniform_")]
    matched_name = min(
        uniform_names,
        key=lambda name: abs(calibration_results[name].metrics["annual_cost_units"] - optimized_cost),
    )
    metrics = pd.DataFrame(rows)
    metrics["cost_matched_reference"] = metrics["policy"].eq(matched_name)
    selected_events = pd.concat(selected_event_frames, ignore_index=True)
    return (
        metrics,
        selected_holdout.reconstruction,
        selected_holdout.event_records,
        selected_events,
    )


def dynamic_trigger_ablation(baseline_metrics: pd.DataFrame) -> pd.DataFrame:
    policies = ["optimized_dynamic", "optimized_base_only_ablation"]
    subset = baseline_metrics[baseline_metrics["policy"].isin(policies)].copy()
    rows: list[dict[str, object]] = []
    metric_columns = [
        "annual_cost_units",
        "annual_visits",
        "water_wape",
        "sediment_wape",
        "event_capture_rate",
    ]
    for split, group in subset.groupby("split", sort=False):
        if set(group["policy"]) != set(policies):
            raise AssertionError(f"Dynamic-trigger ablation incomplete for {split}")
        dynamic = group.set_index("policy").loc["optimized_dynamic"]
        signatures = set(group["base_interval_signature"])
        if len(signatures) != 1:
            raise AssertionError("Dynamic ablation must preserve the optimized base intervals")
        for row in group.itertuples(index=False):
            output = row._asdict()
            for metric in metric_columns:
                output[f"delta_vs_dynamic_{metric}"] = float(getattr(row, metric)) - float(
                    dynamic[metric]
                )
            rows.append(output)
    return pd.DataFrame(rows)


def clopper_pearson_interval(captured: int, total: int, alpha: float = 0.05) -> tuple[float, float]:
    if total <= 0 or captured < 0 or captured > total:
        return np.nan, np.nan
    lower = 0.0 if captured == 0 else float(beta.ppf(alpha / 2, captured, total - captured + 1))
    upper = 1.0 if captured == total else float(
        beta.ppf(1 - alpha / 2, captured + 1, total - captured)
    )
    return lower, upper


def weighted_wilson_interval(
    weighted_rate: float, effective_count: float, alpha: float = 0.05
) -> tuple[float, float]:
    if not np.isfinite(weighted_rate) or effective_count <= 0:
        return np.nan, np.nan
    z = float(norm.ppf(1 - alpha / 2))
    denominator = 1.0 + z**2 / effective_count
    center = (weighted_rate + z**2 / (2 * effective_count)) / denominator
    radius = (
        z
        * math.sqrt(
            weighted_rate * (1 - weighted_rate) / effective_count
            + z**2 / (4 * effective_count**2)
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def event_stability_validation(
    events: pd.DataFrame,
    stability: pd.DataFrame,
    selected_event_records: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_columns = ["date", "year", "month", "main_direction"]
    if "abrupt_score" in events.columns:
        event_columns.append("abrupt_score")
    reference = events[event_columns].copy()
    captures = selected_event_records[["date", "split", "captured"]].copy()
    if captures["date"].duplicated().any():
        raise AssertionError("Selected-policy event replay must have one record per event date")
    details = reference.merge(captures, on="date", how="left", validate="one_to_one")
    if details[["split", "captured"]].isna().any().any():
        raise AssertionError("Selected-policy replay did not score every q2 abrupt event")

    stability_renamed = stability.rename(
        columns={
            "baseline_event_date": "date",
            "main_direction": "stability_main_direction",
            "baseline_score": "stability_baseline_score",
            "matched_parameter_combinations": "stability_matched_combinations",
            "total_parameter_combinations": "stability_total_combinations",
            "match_rate_within_7d": "stability_match_rate_within_7d",
        }
    )
    details = details.merge(stability_renamed, on="date", how="left", validate="one_to_one")
    details["exact_stability_date_match"] = details["stability_match_rate_within_7d"].notna()
    details["direction_matches_stability"] = (
        details["main_direction"] == details["stability_main_direction"]
    ) & details["exact_stability_date_match"]
    details["stability_weight"] = details["stability_match_rate_within_7d"]
    details["weighted_capture_contribution"] = (
        details["captured"].astype(float) * details["stability_weight"]
    )

    summary_rows: list[dict[str, object]] = []

    def summarize(split: str, frame: pd.DataFrame, evidence_role: str) -> None:
        total = len(frame)
        captured = int(frame["captured"].sum())
        lower, upper = clopper_pearson_interval(captured, total)
        matched = frame[frame["exact_stability_date_match"]].copy()
        weights = matched["stability_weight"].to_numpy(dtype=float)
        weight_sum = float(weights.sum())
        weighted_captured = float(matched["weighted_capture_contribution"].sum())
        weighted_rate = weighted_captured / weight_sum if weight_sum > 0 else np.nan
        weight_square_sum = float(np.square(weights).sum())
        effective_count = weight_sum**2 / weight_square_sum if weight_square_sum > 0 else 0.0
        weighted_lower, weighted_upper = weighted_wilson_interval(
            weighted_rate, effective_count
        )
        summary_rows.append(
            {
                "split": split,
                "evidence_role": evidence_role,
                "event_count": total,
                "captured_events": captured,
                "raw_capture_rate": captured / total if total else np.nan,
                "raw_clopper_pearson_95_lower": lower,
                "raw_clopper_pearson_95_upper": upper,
                "exact_stability_matches": len(matched),
                "exact_stability_match_rate": len(matched) / total if total else np.nan,
                "direction_matches": int(frame["direction_matches_stability"].sum()),
                "stability_weight_sum": weight_sum,
                "stability_weighted_captured": weighted_captured,
                "stability_weighted_capture_rate": weighted_rate,
                "weighted_effective_event_count": effective_count,
                "weighted_wilson_approx_95_lower": weighted_lower,
                "weighted_wilson_approx_95_upper": weighted_upper,
                "small_sample_caution": total < 30,
                "boundary_note": (
                    "Event count is small; the exact raw interval and weighted effective "
                    "count are descriptive uncertainty bounds, not proof of future coverage."
                ),
            }
        )

    for split, frame in details.groupby("split", sort=False):
        role = (
            "optimization_and_calibration"
            if split == CALIBRATION_SPLIT
            else "strategy_level_conditional_holdout_only"
        )
        summarize(str(split), frame, role)
    summarize(
        "combined_2018_2021_descriptive",
        details,
        "descriptive_only_not_for_model_selection",
    )
    return details.sort_values("date").reset_index(drop=True), pd.DataFrame(summary_rows)


def future_plan(
    selected: pd.DataFrame,
    forecast: pd.DataFrame,
    strategy: pd.DataFrame,
    old_schedule: pd.DataFrame,
    risk_map: dict[int, str],
    scales: dict[str, float],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    policy = selected.set_index("month")
    strategy_lookup = strategy.set_index(["year", "month"])
    forecast_lookup = forecast.set_index(["year", "month"])
    schedule_rows: list[dict[str, object]] = []
    monthly_rows: list[dict[str, object]] = []
    for year in (2022, 2023):
        for month in range(1, 13):
            option = policy.loc[month]
            interval = int(option["base_interval_days"])
            threshold = float(option["trigger_threshold"])
            dates = base_dates(year, month, interval)
            strategy_row = strategy_lookup.loc[(year, month)]
            forecast_row = forecast_lookup.loc[(year, month)]
            for date in dates:
                schedule_rows.append(
                    {
                        "sample_datetime": date + pd.Timedelta(hours=9),
                        "sample_date": date,
                        "year": year,
                        "month": month,
                        "sample_type": "base_daily_composite",
                        "r04_risk_level": strategy_row["risk_level"],
                        "conservative_risk_level": risk_map[month],
                        "base_interval_days": interval,
                        "trigger_threshold": threshold,
                        "trigger_rule": (
                            "At 09:00 evaluate same-time Q and rapid C proxies; "
                            "D>=threshold adds one sample on each of the next 2 days"
                        ),
                    }
                )
            base_visits = len(dates)
            expected_trigger_visits = base_visits * float(option["trigger_rate"])
            days_in_month = int((pd.Timestamp(year, month, 1) + pd.offsets.MonthBegin(1) - pd.Timestamp(year, month, 1)).days)
            expected_trigger_visits = min(
                expected_trigger_visits, days_in_month - base_visits
            )
            max_trigger_visits = days_in_month - base_visits
            monthly_rows.append(
                {
                    "date": pd.Timestamp(year, month, 1),
                    "year": year,
                    "month": month,
                    "pred_water_volume_1e8_m3": forecast_row["water_volume_1e8_m3"],
                    "pred_sediment_mass_1e4_t": forecast_row["sediment_mass_1e4_t"],
                    "r04_risk_score": strategy_row["risk_score"],
                    "r04_risk_level": strategy_row["risk_level"],
                    "conservative_risk_level": risk_map[month],
                    "base_interval_days": interval,
                    "trigger_threshold": threshold,
                    "base_visits": base_visits,
                    "expected_trigger_visits": expected_trigger_visits,
                    "expected_total_visits": base_visits + expected_trigger_visits,
                    "base_cost_units": base_visits * (VISIT_COST + ASSAY_COST),
                    "expected_cost_units": (base_visits + expected_trigger_visits) * (VISIT_COST + ASSAY_COST),
                    "worst_case_reserved_visits": base_visits + max_trigger_visits,
                    "worst_case_cost_units": (base_visits + max_trigger_visits) * (VISIT_COST + ASSAY_COST),
                }
            )

    schedule = pd.DataFrame(schedule_rows)
    monthly = pd.DataFrame(monthly_rows)
    protocol = monthly[
        [
            "year", "month", "r04_risk_level", "conservative_risk_level",
            "base_interval_days", "trigger_threshold", "base_visits",
            "expected_trigger_visits", "worst_case_reserved_visits",
        ]
    ].copy()
    protocol["evaluation_time_local"] = "daily 09:00 Asia/Shanghai"
    protocol["calendar_continuity"] = (
        "Carry the previous 09:00 reading and pending next-two-calendar-day follow-ups "
        "across month and year boundaries; never reset at month start."
    )
    protocol["rapid_signal_access_assumption"] = (
        "Q and rapid C come from the existing station/remote sensor feed with no incremental "
        "field visit; if manual attendance is required, add that daily cost and re-optimize."
    )
    protocol["q90_water_log_change"] = scales["water_volume_1e8_m3"]
    protocol["q90_sediment_log_change"] = scales["sediment_mass_1e4_t"]
    protocol["water_same_time_proxy"] = (
        "W*=0.000864*Q, Q in m3/s; daily-equivalent units of 1e8 m3"
    )
    protocol["sediment_same_time_proxy"] = (
        "S*=0.00864*Q*C, C rapid turbidity/sediment proxy in kg/m3; "
        "daily-equivalent units of 1e4 t"
    )
    protocol["trigger_score"] = (
        "D=max(abs(diff(log1p(W*)))/q90_water, "
        "abs(diff(log1p(S*)))/q90_sediment) using only current/prior 09:00 readings"
    )
    protocol["historical_to_field_mapping"] = (
        "q90 values come from adjacent historical daily-total proxies; W* and S* use the "
        "same stored units at one fixed clock time, so no future daily total is used. "
        "Prospective same-time data are required to recalibrate this approximation."
    )
    protocol["laboratory_result_deadline"] = (
        "Formal assay result returned before 09:00 Asia/Shanghai on the next calendar day"
    )
    protocol["missing_sediment_fallback"] = (
        "If rapid C or the prior formal sediment result is unavailable by 09:00, do not wait: "
        "use the water component abs(diff(log1p(W*)))/q90_water alone and trigger at the "
        "same monthly threshold."
    )
    protocol["action"] = (
        "threshold reached: sample on each of the next 2 calendar days at 09:00; "
        "merge duplicate dates"
    )

    old = old_schedule.copy()
    old_counts = old.groupby("year").agg(
        old_visits=("sample_date", "nunique"), old_assays=("sample_datetime", "size")
    )
    old_counts["old_cost_units"] = old_counts["old_visits"] * VISIT_COST + old_counts["old_assays"] * ASSAY_COST
    summary_rows: list[dict[str, object]] = []
    for year in (2022, 2023):
        group = monthly[monthly["year"] == year]
        optimized_base = float(group["base_cost_units"].sum())
        optimized_expected = float(group["expected_cost_units"].sum())
        optimized_worst = float(group["worst_case_cost_units"].sum())
        old_cost = float(old_counts.loc[year, "old_cost_units"])
        summary_rows.append(
            {
                "year": year,
                "optimized_base_cost_units": optimized_base,
                "optimized_expected_cost_units": optimized_expected,
                "optimized_worst_case_cost_units": optimized_worst,
                "old_r04_cost_units": old_cost,
                "expected_cost_reduction_vs_old_pct": 100 * (old_cost - optimized_expected) / old_cost,
                "optimized_base_visits": int(group["base_visits"].sum()),
                "optimized_expected_visits": float(group["expected_total_visits"].sum()),
                "old_r04_visits": int(old_counts.loc[year, "old_visits"]),
                "old_r04_assays": int(old_counts.loc[year, "old_assays"]),
            }
        )
    total = pd.DataFrame(summary_rows).sum(numeric_only=True)
    old_cost_total = float(total["old_r04_cost_units"])
    expected_total = float(total["optimized_expected_cost_units"])
    summary_rows.append(
        {
            "year": "2022-2023 total",
            "optimized_base_cost_units": total["optimized_base_cost_units"],
            "optimized_expected_cost_units": expected_total,
            "optimized_worst_case_cost_units": total["optimized_worst_case_cost_units"],
            "old_r04_cost_units": old_cost_total,
            "expected_cost_reduction_vs_old_pct": 100 * (old_cost_total - expected_total) / old_cost_total,
            "optimized_base_visits": total["optimized_base_visits"],
            "optimized_expected_visits": total["optimized_expected_visits"],
            "old_r04_visits": total["old_r04_visits"],
            "old_r04_assays": total["old_r04_assays"],
        }
    )
    return schedule, monthly, protocol, pd.DataFrame(summary_rows)


def cost_coefficient_sensitivity(
    monthly_plan: pd.DataFrame, old_schedule: pd.DataFrame
) -> pd.DataFrame:
    old_counts = old_schedule.groupby("year").agg(
        old_visits=("sample_date", "nunique"), old_assays=("sample_datetime", "size")
    )
    rows: list[dict[str, object]] = []
    for scenario, visit_cost, assay_cost in COST_SCENARIOS:
        yearly_rows: list[dict[str, object]] = []
        for year in (2022, 2023):
            plan = monthly_plan[monthly_plan["year"] == year]
            optimized_visits = float(plan["expected_total_visits"].sum())
            optimized_assays = optimized_visits
            old_visits = float(old_counts.loc[year, "old_visits"])
            old_assays = float(old_counts.loc[year, "old_assays"])
            optimized_cost = optimized_visits * visit_cost + optimized_assays * assay_cost
            old_cost = old_visits * visit_cost + old_assays * assay_cost
            yearly_rows.append(
                {
                    "scenario": scenario,
                    "year": str(year),
                    "visit_cost_weight": visit_cost,
                    "assay_cost_weight": assay_cost,
                    "optimized_expected_visits": optimized_visits,
                    "optimized_expected_assays": optimized_assays,
                    "old_r04_visits": old_visits,
                    "old_r04_assays": old_assays,
                    "optimized_expected_cost": optimized_cost,
                    "old_r04_cost": old_cost,
                    "expected_cost_reduction_vs_old_pct": 100
                    * (old_cost - optimized_cost)
                    / old_cost,
                }
            )
        rows.extend(yearly_rows)
        totals = pd.DataFrame(yearly_rows).sum(numeric_only=True)
        optimized_total = float(totals["optimized_expected_cost"])
        old_total = float(totals["old_r04_cost"])
        rows.append(
            {
                "scenario": scenario,
                "year": "2022-2023 total",
                "visit_cost_weight": visit_cost,
                "assay_cost_weight": assay_cost,
                "optimized_expected_visits": totals["optimized_expected_visits"],
                "optimized_expected_assays": totals["optimized_expected_assays"],
                "old_r04_visits": totals["old_r04_visits"],
                "old_r04_assays": totals["old_r04_assays"],
                "optimized_expected_cost": optimized_total,
                "old_r04_cost": old_total,
                "expected_cost_reduction_vs_old_pct": 100
                * (old_total - optimized_total)
                / old_total,
            }
        )
    return pd.DataFrame(rows)


def quality_checks(
    selected: pd.DataFrame,
    selected_metrics: dict[str, float | str],
    approx_nondominated: pd.DataFrame,
    future_schedule: pd.DataFrame,
    monthly_plan: pd.DataFrame,
    protocol: pd.DataFrame,
    baseline_metrics: pd.DataFrame,
    ablation: pd.DataFrame,
    event_stability_summary: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    strategy: pd.DataFrame,
    old_schedule: pd.DataFrame,
    risk_map: dict[int, str],
    daily: pd.DataFrame,
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []

    def add(name: str, passed: bool, observed: object, expected: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "observed": observed, "expected": expected})

    add("one_policy_per_month", len(selected) == 12 and selected["month"].nunique() == 12, len(selected), 12)
    selected_lookup = selected.set_index("month")
    transition_ok = all(
        math.isclose(
            float(selected_lookup.loc[month, "previous_trigger_threshold"]),
            float(selected_lookup.loc[12 if month == 1 else month - 1, "trigger_threshold"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        for month in range(1, 13)
    )
    add(
        "continuous_calendar_threshold_transitions_consistent",
        transition_ok,
        transition_ok,
        True,
    )
    add("calibration_water_constraint", float(selected_metrics["water_wape"]) <= PRE_SPECIFIED_WATER_WAPE + 1e-9, selected_metrics["water_wape"], f"<= {PRE_SPECIFIED_WATER_WAPE}")
    add("calibration_sediment_constraint", float(selected_metrics["sediment_wape"]) <= PRE_SPECIFIED_SEDIMENT_WAPE + 1e-9, selected_metrics["sediment_wape"], f"<= {PRE_SPECIFIED_SEDIMENT_WAPE}")
    add("calibration_event_constraint", float(selected_metrics["event_capture_rate"]) + 1e-9 >= PRE_SPECIFIED_EVENT_CAPTURE, selected_metrics["event_capture_rate"], f">= {PRE_SPECIFIED_EVENT_CAPTURE}")
    gap_ok = all(
        int(row.base_interval_days) <= RISK_MAX_GAP[risk_map[int(row.month)]]
        for row in selected.itertuples()
    )
    add("risk_specific_gap_constraints", gap_ok, gap_ok, True)
    add("selected_in_epsilon_grid_approx_nondominated_set", str(selected_metrics["policy_signature"]) in set(approx_nondominated["policy_signature"]), str(selected_metrics["policy_signature"]), "present in grid-based epsilon-constraint approximate non-dominated set")
    add("future_months_complete", len(monthly_plan) == 24 and monthly_plan[["year", "month"]].drop_duplicates().shape[0] == 24, len(monthly_plan), 24)
    add("future_schedule_unique", not future_schedule["sample_datetime"].duplicated().any(), int(future_schedule["sample_datetime"].duplicated().sum()), 0)
    add("future_schedule_years", set(future_schedule["year"]) == {2022, 2023}, sorted(future_schedule["year"].unique()), [2022, 2023])
    cost_bounds_ok = (
        (monthly_plan["base_cost_units"] <= monthly_plan["expected_cost_units"])
        & (monthly_plan["expected_cost_units"] <= monthly_plan["worst_case_cost_units"])
    ).all()
    add("future_cost_bounds_ordered", cost_bounds_ok, cost_bounds_ok, True)
    add("r04_strategy_complete", len(strategy) == 24, len(strategy), 24)
    add("old_schedule_nonempty", not old_schedule.empty, len(old_schedule), "> 0")
    add("old_schedule_unique_datetimes", not old_schedule["sample_datetime"].duplicated().any(), int(old_schedule["sample_datetime"].duplicated().sum()), 0)
    add("old_schedule_year_coverage", set(old_schedule["sample_datetime"].dt.year) == {2022, 2023}, sorted(old_schedule["sample_datetime"].dt.year.unique()), [2022, 2023])
    splits = set(baseline_metrics["split"])
    expected_splits = {CALIBRATION_SPLIT, CONDITIONAL_HOLDOUT_SPLIT}
    add("strategy_conditional_holdout_reported_separately", splits == expected_splits, sorted(splits), sorted(expected_splits))
    dynamic_rows = baseline_metrics[
        baseline_metrics["policy"] == "optimized_dynamic"
    ].set_index("split")
    calibration_dynamic = dynamic_rows.loc[CALIBRATION_SPLIT]
    optimizer_replay_pairs = {
        "annual_cost_units": (
            float(selected_metrics["annual_cost_units"]),
            float(calibration_dynamic["annual_cost_units"]),
        ),
        "annual_visits": (
            float(selected_metrics["annual_visits"]),
            float(calibration_dynamic["annual_visits"]),
        ),
        "water_wape": (
            float(selected_metrics["water_wape"]),
            float(calibration_dynamic["water_wape"]),
        ),
        "sediment_wape": (
            float(selected_metrics["sediment_wape"]),
            float(calibration_dynamic["sediment_wape"]),
        ),
        "event_capture_rate": (
            float(selected_metrics["event_capture_rate"]),
            float(calibration_dynamic["event_capture_rate"]),
        ),
    }
    optimizer_replay_ok = all(
        math.isclose(optimized, replayed, rel_tol=1e-10, abs_tol=1e-10)
        for optimized, replayed in optimizer_replay_pairs.values()
    )
    add(
        "continuous_calendar_optimizer_matches_full_replay",
        optimizer_replay_ok,
        optimizer_replay_pairs,
        "optimizer and full replay agree",
    )
    available_dates = set(pd.DatetimeIndex(daily["date"]))

    def expected_boundary_comparisons(years: tuple[int, ...]) -> int:
        return sum(
            (pd.Timestamp(year=year, month=month, day=1) - pd.Timedelta(days=1))
            in available_dates
            for year in years
            for month in range(1, 13)
        )

    observed_boundaries = {
        CALIBRATION_SPLIT: int(
            dynamic_rows.loc[CALIBRATION_SPLIT, "calendar_boundary_comparisons"]
        ),
        CONDITIONAL_HOLDOUT_SPLIT: int(
            dynamic_rows.loc[
                CONDITIONAL_HOLDOUT_SPLIT, "calendar_boundary_comparisons"
            ]
        ),
    }
    expected_boundaries = {
        CALIBRATION_SPLIT: expected_boundary_comparisons(CALIBRATION_YEARS),
        CONDITIONAL_HOLDOUT_SPLIT: expected_boundary_comparisons(
            CONDITIONAL_HOLDOUT_YEARS
        ),
    }
    add(
        "continuous_calendar_month_start_comparisons_complete",
        observed_boundaries == expected_boundaries,
        observed_boundaries,
        expected_boundaries,
    )
    cross_month_accounting_ok = (
        dynamic_rows["cross_month_trigger_actions"].ge(0).all()
        and dynamic_rows["cross_month_trigger_visits"].ge(0).all()
        and (
            dynamic_rows["cross_month_trigger_actions"]
            >= dynamic_rows["cross_month_trigger_visits"]
        ).all()
    )
    add(
        "continuous_calendar_cross_month_actions_accounted",
        cross_month_accounting_ok,
        dynamic_rows[
            ["cross_month_trigger_actions", "cross_month_trigger_visits"]
        ].to_dict("index"),
        "actions >= incremental visits >= 0",
    )
    ablation_pairs = ablation.groupby("split")["policy"].nunique()
    add("dynamic_trigger_ablation_complete", len(ablation) == 4 and (ablation_pairs == 2).all(), len(ablation), "2 policies x 2 splits")
    signature_counts = ablation.groupby("split")["base_interval_signature"].nunique()
    add("dynamic_trigger_ablation_same_base_intervals", (signature_counts == 1).all(), signature_counts.to_dict(), "one shared base signature per split")
    stability_splits = set(event_stability_summary["split"])
    expected_stability_splits = {
        CALIBRATION_SPLIT,
        CONDITIONAL_HOLDOUT_SPLIT,
        "combined_2018_2021_descriptive",
    }
    add("event_stability_splits_complete", stability_splits == expected_stability_splits, sorted(stability_splits), sorted(expected_stability_splits))
    exact_match_min = float(event_stability_summary["exact_stability_match_rate"].min())
    add("event_stability_exact_date_match", exact_match_min == 1.0, exact_match_min, 1.0)
    direction_ok = (
        event_stability_summary["direction_matches"]
        == event_stability_summary["exact_stability_matches"]
    ).all()
    add("event_stability_direction_match", direction_ok, direction_ok, True)
    q90_ok = (
        len(protocol) == 24
        and protocol["q90_water_log_change"].gt(0).all()
        and protocol["q90_sediment_log_change"].gt(0).all()
        and protocol["q90_water_log_change"].nunique() == 1
        and protocol["q90_sediment_log_change"].nunique() == 1
    )
    add("operational_protocol_reports_q90", q90_ok, q90_ok, True)
    fallback_ok = protocol["missing_sediment_fallback"].str.contains("water component", regex=False).all()
    add("operational_protocol_has_flow_fallback", fallback_ok, fallback_ok, True)
    calendar_protocol_ok = protocol["calendar_continuity"].str.contains(
        "never reset at month start", regex=False
    ).all()
    add(
        "operational_protocol_is_calendar_continuous",
        calendar_protocol_ok,
        calendar_protocol_ok,
        True,
    )
    expected_sensitivity_rows = len(COST_SCENARIOS) * 3
    sensitivity_ok = (
        len(cost_sensitivity) == expected_sensitivity_rows
        and np.isfinite(cost_sensitivity["expected_cost_reduction_vs_old_pct"]).all()
    )
    add("cost_coefficient_sensitivity_complete", sensitivity_ok, len(cost_sensitivity), expected_sensitivity_rows)
    return pd.DataFrame(checks)


def save_epsilon_constraint_figure(
    approx_nondominated: pd.DataFrame,
    selected_metrics: dict[str, float | str],
    path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(8.5, 5.4))
    scatter = ax.scatter(
        approx_nondominated["annual_cost_units"],
        approx_nondominated["sediment_wape"] * 100,
        c=approx_nondominated["event_capture_rate"] * 100,
        s=90,
        cmap="viridis",
        alpha=0.85,
        edgecolor="white",
    )
    ax.scatter(
        [selected_metrics["annual_cost_units"]],
        [float(selected_metrics["sediment_wape"]) * 100],
        marker="*",
        s=260,
        color="#d62728",
        edgecolor="black",
        label="Pre-specified-constraint solution",
        zorder=5,
    )
    ax.set_xlabel("Calibration annual resource cost (units)")
    ax.set_ylabel("Sediment proxy reconstruction WAPE (%)")
    ax.set_title("Grid-based epsilon-constraint approximate non-dominated set")
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("Abrupt-event capture (%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_baseline_figure(
    metrics: pd.DataFrame,
    event_stability_summary: pd.DataFrame,
    path: Path,
) -> None:
    conditional_holdout = metrics[metrics["split"] == CONDITIONAL_HOLDOUT_SPLIT].copy()
    conditional_holdout = conditional_holdout.sort_values("annual_cost_units")
    labels = conditional_holdout["policy"].map(
        lambda policy: (
            "old r04 heuristic\n(conservative risk)"
            if policy == "old_r04_heuristic"
            else str(policy).replace("_", " ")
        )
    )
    x = np.arange(len(conditional_holdout))
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    axes[0].bar(x, conditional_holdout["annual_cost_units"], color="#4c78a8")
    axes[0].set_ylabel("Resource cost (units)")
    axes[0].set_title("2021 strategy-level conditional holdout")
    width = 0.25
    axes[1].bar(x - width, conditional_holdout["water_wape"] * 100, width, label="Water WAPE")
    axes[1].bar(x, conditional_holdout["sediment_wape"] * 100, width, label="Sediment WAPE")
    axes[1].bar(x + width, conditional_holdout["event_capture_rate"] * 100, width, label="Event capture")
    axes[1].set_ylabel("Percent")
    axes[1].set_xticks(x, labels, rotation=25, ha="right")
    axes[1].legend(ncol=3)
    holdout_events = event_stability_summary[
        event_stability_summary["split"] == CONDITIONAL_HOLDOUT_SPLIT
    ].iloc[0]
    event_note = (
        f"events n={int(holdout_events['event_count'])}; dynamic "
        f"{int(holdout_events['captured_events'])}/{int(holdout_events['event_count'])}, "
        "exact 95% CI "
        f"{float(holdout_events['raw_clopper_pearson_95_lower']):.1%}–"
        f"{float(holdout_events['raw_clopper_pearson_95_upper']):.0%}"
    )
    fig.text(0.5, 0.012, event_note, ha="center", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def save_future_figure(monthly: pd.DataFrame, path: Path) -> None:
    labels = monthly["date"].dt.strftime("%Y-%m")
    x = np.arange(len(monthly))
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.bar(x, monthly["base_visits"], label="Base visits", color="#4c78a8")
    ax.bar(
        x,
        monthly["expected_trigger_visits"],
        bottom=monthly["base_visits"],
        label="Expected trigger visits (historical-rate estimate)",
        color="#f58518",
    )
    ax.set_ylabel("Visits")
    ax.set_title("2022-2023 cost-constrained monitoring intensity", pad=52)
    ax.set_xticks(x, labels, rotation=60, ha="right")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=2)
    fig.text(
        0.5,
        0.012,
        "Expected trigger visits may be fractional; they are expected counts, not pre-scheduled visit dates.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=180)
    plt.close(fig)


def markdown_table(frame: pd.DataFrame, columns: list[str], decimals: int = 3) -> list[str]:
    data = frame[columns].copy()
    for column in data.select_dtypes(include=["number"]).columns:
        data[column] = data[column].map(lambda value: f"{value:.{decimals}f}")
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in data.astype(str).itertuples(index=False, name=None):
        lines.append("| " + " | ".join(row) + " |")
    return lines


def write_summary(
    run_dir: Path,
    selected: pd.DataFrame,
    selected_metrics: dict[str, float | str],
    baseline_metrics: pd.DataFrame,
    ablation: pd.DataFrame,
    event_stability_summary: pd.DataFrame,
    cost_summary: pd.DataFrame,
    cost_sensitivity: pd.DataFrame,
    scales: dict[str, float],
    quality: pd.DataFrame,
) -> None:
    conditional_holdout = baseline_metrics[
        baseline_metrics["split"] == CONDITIONAL_HOLDOUT_SPLIT
    ].copy()
    sensitivity_totals = cost_sensitivity[
        cost_sensitivity["year"] == "2022-2023 total"
    ].copy()
    boundary_accounting = baseline_metrics[
        baseline_metrics["policy"].isin(
            ["optimized_dynamic", "optimized_base_only_ablation"]
        )
    ].copy()
    lines = [
        "# Cost-constrained sampling run summary",
        "",
        "This run optimizes monitoring timing only. It consumes the explicitly supplied r04 "
        "forecast/risk products and does not refit the forecast model.",
        "Adjacent calendar months are coupled in the MILP through threshold-transition "
        "variables, so month-start comparisons and follow-up visits crossing month/year "
        "boundaries are included before policy selection.",
        "",
        "## Pre-specified constraints",
        "",
        f"- Calibration water proxy WAPE <= {PRE_SPECIFIED_WATER_WAPE:.0%}",
        f"- Calibration sediment proxy WAPE <= {PRE_SPECIFIED_SEDIMENT_WAPE:.0%}",
        f"- Calibration abrupt-event capture >= {PRE_SPECIFIED_EVENT_CAPTURE:.0%}",
        "- Base gap caps: high 5 days, medium 10 days, low 14 days",
        "",
        "## Selected monthly policy",
        "",
        *markdown_table(selected, ["month", "risk_level", "previous_trigger_threshold", "base_interval_days", "trigger_threshold", "cost_units", "water_wape", "sediment_wape", "event_capture_rate"]),
        "",
        "## Calibration aggregate",
        "",
        f"- Annual expected cost: {float(selected_metrics['annual_cost_units']):.2f} resource units",
        f"- Water proxy WAPE: {float(selected_metrics['water_wape']):.2%}",
        f"- Sediment proxy WAPE: {float(selected_metrics['sediment_wape']):.2%}",
        f"- Abrupt-event capture: {float(selected_metrics['event_capture_rate']):.2%}",
        "",
        "## 2021 strategy-level conditional holdout and baselines",
        "",
        *markdown_table(conditional_holdout, ["policy", "annual_cost_units", "annual_visits", "water_wape", "sediment_wape", "event_capture_rate", "max_gap_days"]),
        "",
        "This is conditional only at the r05 strategy layer: 2021 is excluded from r05 "
        "policy/threshold selection, but the supplied q1 completion and r04 risk products may "
        "contain information from the full historical span. It is not an end-to-end "
        "leakage-free holdout.",
        "The old-r04 historical baseline uses the conservative maximum risk assigned to "
        "each calendar month across the supplied 2022 and 2023 r04 strategy. Its replay "
        "cost is therefore not the same quantity as the actual two-year average old-r04 "
        "schedule cost used in the future cost comparison.",
        "",
        "## Dynamic-trigger ablation (same base intervals)",
        "",
        *markdown_table(ablation, ["split", "policy", "annual_cost_units", "water_wape", "sediment_wape", "event_capture_rate", "delta_vs_dynamic_annual_cost_units"]),
        "",
        "## Continuous-calendar boundary accounting",
        "",
        *markdown_table(boundary_accounting, ["split", "policy", "calendar_boundary_comparisons", "cross_month_trigger_actions", "cross_month_trigger_visits"]),
        "",
        "## Abrupt-event stability evidence",
        "",
        *markdown_table(event_stability_summary, ["split", "event_count", "captured_events", "raw_capture_rate", "raw_clopper_pearson_95_lower", "raw_clopper_pearson_95_upper", "stability_weighted_capture_rate", "weighted_effective_event_count"]),
        "",
        "Event counts are small. Exact raw binomial intervals and weighted effective counts "
        "are reported as uncertainty boundaries, not as proof of future capture performance.",
        "",
        "## Operational dynamic protocol",
        "",
        f"- Historical q90 water log-change scale: {scales['water_volume_1e8_m3']:.9f}",
        f"- Historical q90 sediment log-change scale: {scales['sediment_mass_1e4_t']:.9f}",
        "- At daily 09:00 Asia/Shanghai, use only observations available by that time: "
        "W*=0.000864*Q and S*=0.00864*Q*C, where Q is instantaneous flow (m3/s) and C is "
        "the rapid turbidity/sediment proxy (kg/m3). Compare consecutive 09:00 log1p changes.",
        "- The daily rapid trigger assumes Q and C are available from an existing automatic/"
        "remote station feed without an extra field visit. If 09:00 readings require manual "
        "attendance, that daily cost must be added and the optimization rerun.",
        "- Formal assay results must return before next-day 09:00. If rapid C or the prior "
        "formal sediment result is late, use the flow component alone at the same threshold "
        "without waiting. A trigger adds samples on each of the next two calendar days, "
        "including across month and year boundaries.",
        "- Historical daily-total q90 scales are mapped to same-unit daily-equivalent "
        "instantaneous proxies; prospective fixed-time observations are still needed for "
        "recalibration, and no future daily total is assumed known.",
        "",
        "## Future cost comparison",
        "",
        *markdown_table(cost_summary, ["year", "optimized_base_cost_units", "optimized_expected_cost_units", "optimized_worst_case_cost_units", "old_r04_cost_units", "expected_cost_reduction_vs_old_pct"]),
        "",
        "## Cost-coefficient sensitivity",
        "",
        *markdown_table(sensitivity_totals, ["scenario", "visit_cost_weight", "assay_cost_weight", "optimized_expected_cost", "old_r04_cost", "expected_cost_reduction_vs_old_pct"]),
        "",
        "## Evidence boundary",
        "",
        "The historical daily series is a proxy derived from q1 completion and q2 "
        "interpolation. Intraday benefits of the old 2/3-sample visits cannot be scored from "
        "daily data, so they are charged as cost but are not credited with invented accuracy. "
        "All candidate r05 options use one assay per visit, so changing cost coefficients does "
        "not change their within-r05 ranking; it changes the savings comparison against the "
        "multi-assay r04 schedule. This candidate run is not a human adoption decision.",
        "",
        f"Quality checks passed: {int(quality['passed'].sum())}/{len(quality)}.",
    ]
    (run_dir / "results" / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def path_for_record(path: Path) -> str:
    try:
        return path.relative_to(PACKAGE_DIR).as_posix()
    except ValueError:
        return str(path)


def write_manifest(
    run_dir: Path,
    input_paths: dict[str, Path],
    source_rows: dict[str, int],
    rows_used: dict[str, int],
    scales: dict[str, float],
    output_files: list[str],
) -> None:
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "script": str(Path(__file__).resolve()),
        "script_sha256": sha256(Path(__file__).resolve()),
        "inputs": {
            name: {
                "path": path_for_record(path),
                "sha256": sha256(path),
                "source_rows": source_rows[name],
                "rows_used": rows_used[name],
            }
            for name, path in input_paths.items()
        },
        "calibration_years": list(CALIBRATION_YEARS),
        "strategy_conditional_holdout_years": list(CONDITIONAL_HOLDOUT_YEARS),
        "strategy_conditional_holdout_boundary": (
            "2021 is excluded from r05 policy selection only; supplied q1/r04 upstream "
            "products can contain full-span information, so this is not end-to-end "
            "leakage-free validation."
        ),
        "pre_specified_constraints": {
            "water_wape_max": PRE_SPECIFIED_WATER_WAPE,
            "sediment_wape_max": PRE_SPECIFIED_SEDIMENT_WAPE,
            "event_capture_min": PRE_SPECIFIED_EVENT_CAPTURE,
            "event_tolerance_days": EVENT_TOLERANCE_DAYS,
        },
        "dynamic_protocol": {
            "evaluation_time": "daily 09:00 Asia/Shanghai",
            "rapid_signal_access_assumption": (
                "existing automatic/remote station feed; manual daily attendance would "
                "require re-costing and re-optimization"
            ),
            "q90_water_log_change": scales["water_volume_1e8_m3"],
            "q90_sediment_log_change": scales["sediment_mass_1e4_t"],
            "water_same_time_proxy": "W*=0.000864*Q",
            "sediment_same_time_proxy": "S*=0.00864*Q*C",
            "followup_days": TRIGGER_FOLLOWUP_DAYS,
            "calendar_continuity": (
                "consecutive readings and next-two-calendar-day follow-ups continue "
                "across month and year boundaries"
            ),
            "formal_assay_deadline": "before next-day 09:00 Asia/Shanghai",
            "missing_sediment_fallback": "use flow component alone at the same threshold",
        },
        "cost_scenarios": [
            {
                "name": name,
                "visit_cost_weight": visit_cost,
                "assay_cost_weight": assay_cost,
            }
            for name, visit_cost, assay_cost in COST_SCENARIOS
        ],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "outputs": output_files,
    }
    (run_dir / "validation" / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cost-constrained adaptive monitoring design")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--q2-daily", type=Path, default=DEFAULT_Q2_DAILY)
    parser.add_argument("--q2-events", type=Path, default=DEFAULT_Q2_EVENTS)
    parser.add_argument(
        "--q2-event-stability", type=Path, default=DEFAULT_Q2_EVENT_STABILITY
    )
    parser.add_argument("--r04-forecast", type=Path, default=DEFAULT_R04_FORECAST)
    parser.add_argument("--r04-strategy", type=Path, default=DEFAULT_R04_STRATEGY)
    parser.add_argument(
        "--r04-old-schedule", type=Path, default=DEFAULT_R04_OLD_SCHEDULE
    )
    args = parser.parse_args()
    run_dir = prepare_run_dir(Path(args.run_dir))

    input_paths = {
        "q2_daily": args.q2_daily.resolve(),
        "q2_events": args.q2_events.resolve(),
        "q2_event_stability": args.q2_event_stability.resolve(),
        "r04_forecast": args.r04_forecast.resolve(),
        "r04_strategy": args.r04_strategy.resolve(),
        "r04_old_schedule": args.r04_old_schedule.resolve(),
    }
    source_rows = {
        name: csv_source_rows(path) for name, path in input_paths.items()
    }
    daily, events, stability, forecast, strategy, old_schedule = load_inputs(
        input_paths["q2_daily"],
        input_paths["q2_events"],
        input_paths["q2_event_stability"],
        input_paths["r04_forecast"],
        input_paths["r04_strategy"],
        input_paths["r04_old_schedule"],
    )
    scales = change_scales(daily)
    risk_map = conservative_risk_map(strategy)
    options = option_performance(daily, events, scales, risk_map)
    selected, selected_metrics = solve_policy(
        options,
        PRE_SPECIFIED_WATER_WAPE,
        PRE_SPECIFIED_SEDIMENT_WAPE,
        PRE_SPECIFIED_EVENT_CAPTURE,
    )
    if selected is None:
        raise RuntimeError(
            f"Pre-specified optimization infeasible: {selected_metrics['solver_status']}"
        )
    epsilon_grid, approx_nondominated = epsilon_constraint_analysis(options)
    (
        baseline_metrics,
        conditional_holdout_reconstruction,
        conditional_holdout_events,
        selected_event_records,
    ) = replay_baselines(
        daily, events, scales, selected, risk_map
    )
    ablation = dynamic_trigger_ablation(baseline_metrics)
    event_stability_details, event_stability_summary = event_stability_validation(
        events, stability, selected_event_records
    )
    schedule, monthly, protocol, cost_summary = future_plan(
        selected, forecast, strategy, old_schedule, risk_map, scales
    )
    cost_sensitivity = cost_coefficient_sensitivity(monthly, old_schedule)
    quality = quality_checks(
        selected,
        selected_metrics,
        approx_nondominated,
        schedule,
        monthly,
        protocol,
        baseline_metrics,
        ablation,
        event_stability_summary,
        cost_sensitivity,
        strategy,
        old_schedule,
        risk_map,
        daily,
    )
    if not quality["passed"].all():
        failed = quality.loc[~quality["passed"], "check"].tolist()
        raise AssertionError(f"Quality checks failed before output: {failed}")

    selected_output = selected[
        [
            "month", "risk_level", "previous_trigger_threshold",
            "base_interval_days", "trigger_threshold",
            "trigger_rate", "visits", "base_visits", "trigger_visits", "cost_units",
            "water_wape", "sediment_wape", "event_capture_rate",
            "calendar_boundary_comparisons", "cross_month_trigger_actions",
            "cross_month_trigger_visits",
        ]
    ].copy()
    selected_output["policy_signature"] = selected_metrics["policy_signature"]
    selected_output.to_csv(run_dir / "results" / "selected_monthly_policy.csv", index=False, encoding="utf-8-sig")
    schedule.to_csv(run_dir / "results" / "sampling_plan_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(run_dir / "results" / "monthly_plan_2022_2023.csv", index=False, encoding="utf-8-sig")
    protocol.to_csv(run_dir / "results" / "conditional_trigger_protocol_2022_2023.csv", index=False, encoding="utf-8-sig")
    cost_summary.to_csv(run_dir / "results" / "cost_summary_2022_2023.csv", index=False, encoding="utf-8-sig")

    options.to_csv(run_dir / "validation" / "candidate_option_performance.csv", index=False, encoding="utf-8-sig")
    epsilon_grid.to_csv(run_dir / "validation" / "epsilon_constraint_grid.csv", index=False, encoding="utf-8-sig")
    approx_nondominated.to_csv(run_dir / "validation" / "epsilon_constraint_approx_nondominated_set.csv", index=False, encoding="utf-8-sig")
    baseline_metrics.to_csv(run_dir / "validation" / "historical_replay_metrics.csv", index=False, encoding="utf-8-sig")
    boundary_accounting = baseline_metrics[
        baseline_metrics["policy"].isin(
            ["optimized_dynamic", "optimized_base_only_ablation"]
        )
    ][
        [
            "split", "policy", "calendar_boundary_comparisons",
            "cross_month_trigger_actions", "cross_month_trigger_visits",
        ]
    ].copy()
    boundary_accounting.to_csv(
        run_dir / "validation" / "calendar_boundary_accounting.csv",
        index=False,
        encoding="utf-8-sig",
    )
    ablation.to_csv(run_dir / "validation" / "dynamic_trigger_ablation.csv", index=False, encoding="utf-8-sig")
    conditional_holdout_reconstruction.to_csv(run_dir / "validation" / "strategy_conditional_holdout_2021_daily_reconstruction.csv", index=False, encoding="utf-8-sig")
    conditional_holdout_events.to_csv(run_dir / "validation" / "strategy_conditional_holdout_2021_event_capture.csv", index=False, encoding="utf-8-sig")
    event_stability_details.to_csv(run_dir / "validation" / "event_stability_capture_details.csv", index=False, encoding="utf-8-sig")
    event_stability_summary.to_csv(run_dir / "validation" / "event_stability_weighted_capture.csv", index=False, encoding="utf-8-sig")
    cost_sensitivity.to_csv(run_dir / "validation" / "cost_coefficient_sensitivity.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(run_dir / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")

    save_epsilon_constraint_figure(approx_nondominated, selected_metrics, run_dir / "figures" / "epsilon_constraint_approx_front.png")
    save_baseline_figure(
        baseline_metrics,
        event_stability_summary,
        run_dir / "figures" / "strategy_conditional_holdout_baseline_comparison.png",
    )
    save_future_figure(monthly, run_dir / "figures" / "sampling_calendar_2022_2023.png")
    write_summary(
        run_dir,
        selected,
        selected_metrics,
        baseline_metrics,
        ablation,
        event_stability_summary,
        cost_summary,
        cost_sensitivity,
        scales,
        quality,
    )

    log_lines = [
        "status=yes",
        f"solver_status={selected_metrics['solver_status']}",
        f"calibration_water_wape={float(selected_metrics['water_wape']):.8f}",
        f"calibration_sediment_wape={float(selected_metrics['sediment_wape']):.8f}",
        f"calibration_event_capture={float(selected_metrics['event_capture_rate']):.8f}",
        f"calibration_annual_cost_units={float(selected_metrics['annual_cost_units']):.4f}",
        f"q90_water_log_change={scales['water_volume_1e8_m3']:.9f}",
        f"q90_sediment_log_change={scales['sediment_mass_1e4_t']:.9f}",
        f"future_base_samples={len(schedule)}",
        f"epsilon_grid_approx_nondominated_policies={len(approx_nondominated)}",
        f"quality_checks_passed={int(quality['passed'].sum())}/{len(quality)}",
        f"code_sha256={sha256(Path(__file__))}",
    ]
    for name, path in input_paths.items():
        log_lines.append(f"input_sha256 {name} {path_for_record(path)}={sha256(path)}")
    (run_dir / "logs" / "run_summary.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    output_files = sorted(
        path.relative_to(run_dir).as_posix()
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "run.md"
    )
    output_files.append("validation/run_manifest.json")
    output_files = sorted(set(output_files))
    rows_used = {
        "q2_daily": len(daily),
        "q2_events": len(events),
        "q2_event_stability": len(stability),
        "r04_forecast": len(forecast),
        "r04_strategy": len(strategy),
        "r04_old_schedule": len(old_schedule),
    }
    write_manifest(
        run_dir,
        input_paths,
        source_rows,
        rows_used,
        scales,
        output_files,
    )


if __name__ == "__main__":
    main()
