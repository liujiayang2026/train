from __future__ import annotations

import argparse
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROUTE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parents[5]
RUNS_DIR = ROUTE_DIR / "runs"
DEFAULT_Q1_SERIES = (
    PACKAGE_DIR
    / "process"
    / "q1"
    / "routes"
    / "r01-log-linear-sediment"
    / "runs"
    / "run-20260809-2032-time-block-bootstrap"
    / "results"
    / "data"
    / "cleaned_hydro_timeseries.csv"
)
DEFAULT_Q2_DAILY = (
    PACKAGE_DIR
    / "process"
    / "q2"
    / "routes"
    / "r01-interpolated-daily-pattern"
    / "runs"
    / "run-20260809-2036-time-block-q1"
    / "results"
    / "data"
    / "processed"
    / "daily_flux_series.csv"
)
DEFAULT_Q2_EVENTS = (
    PACKAGE_DIR
    / "process"
    / "q2"
    / "routes"
    / "r01-interpolated-daily-pattern"
    / "runs"
    / "run-20260809-2036-time-block-q1"
    / "results"
    / "tables"
    / "abrupt_change_events.csv"
)
TARGETS = [
    ("water_volume_1e8_m3", "月水量（亿m³）", "water"),
    ("sediment_mass_1e4_t", "月输沙量（万吨）", "sediment"),
]
REGIME_START_YEAR = 2018
MODEL_SELECTION_YEARS = (2019, 2020)
HOLDOUT_TEST_YEARS = (2021,)
SECOND_YEAR_INTERVAL_INFLATION = 1.25


def trapezoid_integral(values: np.ndarray, coordinates: np.ndarray) -> float:
    integrate = getattr(np, "trapezoid", None)
    if integrate is None:
        integrate = np.trapz
    return float(integrate(values, coordinates))


@dataclass(frozen=True)
class Candidate:
    name: str
    alpha: float | None = None

    @property
    def label(self) -> str:
        if self.alpha is None:
            return self.name
        return f"{self.name}_alpha_{self.alpha:g}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_input(path: Path) -> Path:
    resolved = path if path.is_absolute() else Path.cwd() / path
    resolved = resolved.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing required input: {resolved}")
    return resolved


def report_input_path(path: Path) -> str:
    """Return a stable package-relative label when possible."""
    try:
        return path.resolve().relative_to(PACKAGE_DIR.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def prepare_run_dir(path: Path) -> Path:
    run_dir = path if path.is_absolute() else ROUTE_DIR / path
    run_dir = run_dir.resolve()
    expected_parent = RUNS_DIR.resolve()
    if run_dir.parent != expected_parent:
        raise ValueError(f"Run directory must be a direct child of {expected_parent}")
    if not run_dir.name.startswith("run-"):
        raise ValueError("Run directory basename must start with 'run-'.")
    if not (run_dir / "run.md").is_file():
        raise FileNotFoundError("Create run.md before execution so the run has an owner.")
    occupied = sorted(item for item in run_dir.iterdir() if item.name != "run.md")
    if occupied:
        raise FileExistsError(
            "Refusing to overwrite generated evidence in an existing run: "
            + ", ".join(str(item) for item in occupied)
        )
    for name in ("results", "figures", "validation", "logs"):
        (run_dir / name).mkdir(parents=True, exist_ok=False)
    return run_dir


def load_observations(q1_series: Path) -> pd.DataFrame:
    data = pd.read_csv(q1_series, parse_dates=["datetime"])
    needed = ["datetime", "flow_m3s", "sediment_flux_kg_s"]
    missing = [column for column in needed if column not in data.columns]
    if missing:
        raise ValueError(f"Missing observation columns: {missing}")
    data = data[needed].dropna().sort_values("datetime").drop_duplicates("datetime")
    data = data[
        data["datetime"].between(
            pd.Timestamp("2016-01-01"),
            pd.Timestamp("2022-01-01"),
            inclusive="left",
        )
    ].reset_index(drop=True)
    if data.empty:
        raise ValueError("No observations in 2016-2021")
    return data


def monthly_trapezoid_totals(observations: pd.DataFrame) -> pd.DataFrame:
    epoch = pd.Timestamp("1970-01-01")
    time_seconds = (observations["datetime"] - epoch).dt.total_seconds().to_numpy(dtype=float)
    flow = observations["flow_m3s"].to_numpy(dtype=float)
    sediment_flux = observations["sediment_flux_kg_s"].to_numpy(dtype=float)
    rows = []
    for start in pd.date_range("2016-01-01", "2021-12-01", freq="MS"):
        end = start + pd.offsets.MonthBegin(1)
        start_seconds = float((start - epoch).total_seconds())
        end_seconds = float((end - epoch).total_seconds())
        inside = (time_seconds > start_seconds) & (time_seconds < end_seconds)
        interval_times = np.r_[start_seconds, time_seconds[inside], end_seconds]
        flow_values = np.r_[
            np.interp(start_seconds, time_seconds, flow),
            flow[inside],
            np.interp(end_seconds, time_seconds, flow),
        ]
        sediment_values = np.r_[
            np.interp(start_seconds, time_seconds, sediment_flux),
            sediment_flux[inside],
            np.interp(end_seconds, time_seconds, sediment_flux),
        ]
        duration_seconds = end_seconds - start_seconds
        water_volume_m3 = trapezoid_integral(flow_values, interval_times)
        sediment_mass_kg = trapezoid_integral(sediment_values, interval_times)
        gaps = np.diff(interval_times) / 3600.0
        rows.append(
            {
                "date": start,
                "year": int(start.year),
                "month": int(start.month),
                "days": int((end - start).days),
                "observation_count": int(inside.sum()),
                "max_gap_hours": float(gaps.max()),
                "water_volume_m3": water_volume_m3,
                "sediment_mass_kg": sediment_mass_kg,
                "water_volume_1e8_m3": water_volume_m3 / 1e8,
                "sediment_mass_1e4_t": sediment_mass_kg / 1e7,
                "mean_flow_m3s": water_volume_m3 / duration_seconds,
                "mean_sediment_flux_kg_s": sediment_mass_kg / duration_seconds,
            }
        )
    monthly = pd.DataFrame(rows)
    if len(monthly) != 72:
        raise AssertionError(f"Expected 72 months, got {len(monthly)}")
    return monthly


def integration_consistency(monthly: pd.DataFrame, q2_daily: Path) -> pd.DataFrame:
    if not q2_daily.exists():
        return pd.DataFrame(
            [{"target": "q2_daily_reference", "median_abs_pct": np.nan, "max_abs_pct": np.nan}]
        )
    daily = pd.read_csv(q2_daily, parse_dates=["date"])
    reference = (
        daily.set_index("date")[["water_volume_1e8_m3", "sediment_mass_1e4_t"]]
        .resample("MS")
        .sum()
    )
    direct = monthly.set_index("date")[["water_volume_1e8_m3", "sediment_mass_1e4_t"]]
    rows = []
    for target, _, _ in TARGETS:
        relative = (direct[target] - reference[target]) / reference[target]
        rows.append(
            {
                "target": target,
                "median_abs_pct": float(relative.abs().median() * 100),
                "p95_abs_pct": float(relative.abs().quantile(0.95) * 100),
                "max_abs_pct": float(relative.abs().max() * 100),
            }
        )
    return pd.DataFrame(rows)


def ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    design = np.column_stack([np.ones(len(z)), z])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return coef, mean, scale


def ridge_predict(
    x: np.ndarray,
    model: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> np.ndarray:
    coef, mean, scale = model
    z = (x - mean) / scale
    return np.column_stack([np.ones(len(z)), z]) @ coef


def calendar_features(dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    index = pd.DatetimeIndex(dates)
    trend = (index.year.to_numpy(dtype=float) - 2016) + (index.month.to_numpy(dtype=float) - 0.5) / 12
    post = (index >= pd.Timestamp("2018-01-01")).astype(float)
    post_trend = np.maximum(0.0, trend - 2.0)
    month = index.month.to_numpy(dtype=float)
    columns = [trend, post, post_trend]
    for harmonic in (1, 2, 3):
        angle = 2 * np.pi * harmonic * (month - 0.5) / 12.0
        columns.extend([np.sin(angle), np.cos(angle)])
    columns.extend(
        [
            ((month >= 6) & (month <= 10)).astype(float),
            ((month >= 7) & (month <= 10)).astype(float),
        ]
    )
    return np.column_stack(columns)


def annual_log_slope(train: pd.DataFrame, target: str, clip: float) -> float:
    annual = train.groupby("year", as_index=False)[target].sum().tail(4)
    if len(annual) < 2:
        return 0.0
    x = annual["year"].to_numpy(dtype=float)
    y = np.log1p(annual[target].to_numpy(dtype=float))
    slope = float(np.polyfit(x - x.min(), y, 1)[0])
    return float(np.clip(slope, -clip, clip))


def seasonal_naive_forecast(train: pd.DataFrame, dates: pd.DatetimeIndex, target: str) -> np.ndarray:
    latest_year = int(train["year"].max())
    latest = train[train["year"].eq(latest_year)].sort_values("month")
    month_map = latest.set_index("month")[target].to_dict()
    fallback = train.groupby("month")[target].median().to_dict()
    clip = 0.08 if target.startswith("water") else 0.12
    slope = annual_log_slope(train, target, clip)
    values = []
    for date in dates:
        base = float(month_map.get(int(date.month), fallback[int(date.month)]))
        values.append(base * math.exp(slope * (int(date.year) - latest_year)))
    return np.asarray(values, dtype=float)


def regime_climatology_forecast(train: pd.DataFrame, dates: pd.DatetimeIndex, target: str) -> np.ndarray:
    regime = train[train["year"] >= 2018].copy()
    if regime.empty:
        regime = train.copy()
    max_year = int(regime["year"].max())
    clip = 0.08 if target.startswith("water") else 0.12
    slope = annual_log_slope(regime, target, clip)
    month_levels = {}
    for month, group in regime.groupby("month"):
        weights = np.exp(-0.55 * (max_year - group["year"].to_numpy(dtype=float)))
        month_levels[int(month)] = float(
            np.expm1(np.average(np.log1p(group[target].to_numpy(dtype=float)), weights=weights))
        )
    return np.asarray(
        [
            month_levels[int(date.month)] * math.exp(slope * (int(date.year) - max_year))
            for date in dates
        ],
        dtype=float,
    )


def fourier_forecast(
    train: pd.DataFrame,
    dates: pd.DatetimeIndex,
    target: str,
    alpha: float,
) -> np.ndarray:
    x_train = calendar_features(train["date"])
    y_train = np.log1p(train[target].to_numpy(dtype=float))
    model = ridge_fit(x_train, y_train, alpha)
    pred_log = ridge_predict(calendar_features(dates), model)
    return np.expm1(pred_log).clip(min=0)


def lag_features_from_history(date: pd.Timestamp, values: list[float]) -> list[float]:
    calendar = calendar_features(pd.DatetimeIndex([date]))[0].tolist()
    lags = [values[-1], values[-2], values[-3], values[-6], values[-12]]
    rolling = [float(np.mean(values[-3:])), float(np.mean(values[-12:]))]
    return calendar + lags + rolling


def lag_ridge_forecast(
    train: pd.DataFrame,
    dates: pd.DatetimeIndex,
    target: str,
    alpha: float,
) -> np.ndarray:
    work = train.sort_values("date").reset_index(drop=True)
    logs = np.log1p(work[target].to_numpy(dtype=float)).tolist()
    rows = []
    response = []
    for index in range(12, len(work)):
        history = logs[:index]
        rows.append(lag_features_from_history(pd.Timestamp(work.loc[index, "date"]), history))
        response.append(logs[index])
    if len(rows) < 12:
        return fourier_forecast(train, dates, target, max(alpha, 0.1))
    model = ridge_fit(np.asarray(rows, dtype=float), np.asarray(response, dtype=float), alpha)
    values = logs.copy()
    predictions = []
    for date in dates:
        features = np.asarray([lag_features_from_history(pd.Timestamp(date), values)], dtype=float)
        pred_log = float(ridge_predict(features, model)[0])
        predictions.append(max(0.0, float(np.expm1(pred_log))))
        values.append(pred_log)
    return np.asarray(predictions, dtype=float)


def candidate_forecast(
    candidate: Candidate,
    train: pd.DataFrame,
    dates: pd.DatetimeIndex,
    target: str,
) -> np.ndarray:
    if candidate.name == "seasonal_naive":
        return seasonal_naive_forecast(train, dates, target)
    if candidate.name == "regime_climatology":
        return regime_climatology_forecast(train, dates, target)
    if candidate.name == "fourier_ridge":
        return fourier_forecast(train, dates, target, float(candidate.alpha))
    if candidate.name == "lag_ridge":
        return lag_ridge_forecast(train, dates, target, float(candidate.alpha))
    raise ValueError(f"Unknown candidate: {candidate}")


def candidates() -> list[Candidate]:
    out = [Candidate("seasonal_naive"), Candidate("regime_climatology")]
    out.extend(Candidate("fourier_ridge", alpha) for alpha in (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0))
    out.extend(Candidate("lag_ridge", alpha) for alpha in (0.1, 0.3, 1.0, 3.0, 10.0, 30.0))
    return out


def metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual_log = np.log1p(actual)
    predicted_log = np.log1p(predicted)
    residual = actual_log - predicted_log
    denominator = float(np.sum((actual_log - actual_log.mean()) ** 2))
    return {
        "rmse_log": float(np.sqrt(np.mean(residual**2))),
        "mae_log": float(np.mean(np.abs(residual))),
        "r2_log": float(1 - np.sum(residual**2) / denominator) if denominator else np.nan,
        "wape": float(np.sum(np.abs(actual - predicted)) / np.sum(np.abs(actual))),
    }


def compare_models(monthly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Candidate]]:
    rows = []
    selected = {}
    model_grid = candidates()
    for target, _, _ in TARGETS:
        for candidate in model_grid:
            for year in MODEL_SELECTION_YEARS:
                train = monthly[
                    monthly["year"].between(REGIME_START_YEAR, year - 1)
                ].copy()
                test = monthly[monthly["year"] == year].copy()
                predicted = candidate_forecast(candidate, train, pd.DatetimeIndex(test["date"]), target)
                rows.append(
                    {
                        "target": target,
                        "model": candidate.name,
                        "alpha": candidate.alpha,
                        "model_label": candidate.label,
                        "heldout_year": year,
                        **metrics(test[target].to_numpy(dtype=float), predicted),
                    }
                )
        detail = pd.DataFrame([row for row in rows if row["target"] == target])
        summary = (
            detail.groupby(["target", "model", "alpha", "model_label"], dropna=False, as_index=False)
            .agg(
                rmse_log=("rmse_log", "mean"),
                mae_log=("mae_log", "mean"),
                r2_log=("r2_log", "mean"),
                wape=("wape", "mean"),
            )
            .sort_values(["rmse_log", "mae_log", "model_label"])
        )
        best = summary.iloc[0]
        selected[target] = Candidate(
            str(best["model"]),
            None if pd.isna(best["alpha"]) else float(best["alpha"]),
        )
    detail_all = pd.DataFrame(rows)
    summary_all = (
        detail_all.groupby(["target", "model", "alpha", "model_label"], dropna=False, as_index=False)
        .agg(
            heldout_years=("heldout_year", "nunique"),
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            wape=("wape", "mean"),
        )
    )
    return pd.concat([detail_all, summary_all.assign(heldout_year="mean")], ignore_index=True), selected


def historical_backtest(
    monthly: pd.DataFrame,
    selected: dict[str, Candidate],
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    rows = []
    residuals = {}
    for target, _, _ in TARGETS:
        target_residuals = []
        candidate = selected[target]
        for year in MODEL_SELECTION_YEARS + HOLDOUT_TEST_YEARS:
            train = monthly[
                monthly["year"].between(REGIME_START_YEAR, year - 1)
            ].copy()
            test = monthly[monthly["year"] == year].copy()
            predicted = candidate_forecast(candidate, train, pd.DatetimeIndex(test["date"]), target)
            actual = test[target].to_numpy(dtype=float)
            target_residuals.extend((np.log1p(actual) - np.log1p(predicted)).tolist())
            for date, actual_value, predicted_value in zip(test["date"], actual, predicted):
                rows.append(
                    {
                        "date": date,
                        "year": year,
                        "target": target,
                        "model_label": candidate.label,
                        "evaluation_scope": (
                            "final_holdout_test"
                            if year in HOLDOUT_TEST_YEARS
                            else "model_selection_backtest"
                        ),
                        "actual": float(actual_value),
                        "predicted": float(predicted_value),
                    }
                )
        residuals[target] = np.asarray(target_residuals, dtype=float)
    return pd.DataFrame(rows), residuals


def empirical_radius(residuals: np.ndarray, coverage: float) -> float:
    absolute = np.abs(residuals)
    if absolute.size == 0:
        raise ValueError("Cannot calibrate an interval without backtest residuals")
    return float(np.quantile(absolute, coverage, method="linear"))


def add_backtest_intervals(
    backtest: pd.DataFrame,
    residuals: dict[str, np.ndarray],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = backtest.copy()
    coverage_rows = []
    for target, _, _ in TARGETS:
        radius80 = empirical_radius(residuals[target], 0.80)
        radius95 = empirical_radius(residuals[target], 0.95)
        mask = work["target"].eq(target)
        center = np.log1p(work.loc[mask, "predicted"].to_numpy(dtype=float))
        work.loc[mask, "lower80"] = np.expm1(center - radius80).clip(min=0)
        work.loc[mask, "upper80"] = np.expm1(center + radius80)
        work.loc[mask, "lower95"] = np.expm1(center - radius95).clip(min=0)
        work.loc[mask, "upper95"] = np.expm1(center + radius95)
        regular = work.loc[mask]
        for level in (80, 95):
            covered = regular["actual"].between(regular[f"lower{level}"], regular[f"upper{level}"])
            coverage_rows.append(
                {
                    "target": target,
                    "nominal_coverage": level / 100,
                    "empirical_coverage": float(covered.mean()),
                    "log_radius": radius80 if level == 80 else radius95,
                    "calibration_months": len(regular),
                }
            )
    return work, pd.DataFrame(coverage_rows)


def forecast_months(
    monthly: pd.DataFrame,
    selected: dict[str, Candidate],
    residuals: dict[str, np.ndarray],
) -> pd.DataFrame:
    dates = pd.date_range("2022-01-01", "2023-12-01", freq="MS")
    output = pd.DataFrame({"date": dates, "year": dates.year, "month": dates.month})
    model_monthly = monthly[monthly["year"] >= REGIME_START_YEAR].copy()
    for target, _, _ in TARGETS:
        predicted = candidate_forecast(selected[target], model_monthly, dates, target)
        radius80 = empirical_radius(residuals[target], 0.80)
        radius95 = empirical_radius(residuals[target], 0.95)
        center = np.log1p(predicted)
        inflation = np.where(dates.year == 2023, SECOND_YEAR_INTERVAL_INFLATION, 1.0)
        output[target] = predicted
        output[f"{target}_lower80"] = np.expm1(center - radius80 * inflation).clip(min=0)
        output[f"{target}_upper80"] = np.expm1(center + radius80 * inflation)
        output[f"{target}_lower95"] = np.expm1(center - radius95 * inflation).clip(min=0)
        output[f"{target}_upper95"] = np.expm1(center + radius95 * inflation)
        output[f"{target}_model"] = selected[target].label
    return output


def annual_forecast(monthly_forecast: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in monthly_forecast.columns if column.startswith(("water_", "sediment_"))]
    aggregations = {column: "sum" for column in columns if not column.endswith("_model")}
    annual = monthly_forecast.groupby("year", as_index=False).agg(aggregations)
    annual["water_model"] = monthly_forecast["water_volume_1e8_m3_model"].iloc[0]
    annual["sediment_model"] = monthly_forecast["sediment_mass_1e4_t_model"].iloc[0]
    return annual


def build_quality_checks(
    monthly: pd.DataFrame,
    forecast: pd.DataFrame,
    annual: pd.DataFrame,
    schedule: pd.DataFrame,
    consistency: pd.DataFrame,
) -> pd.DataFrame:
    checks = []

    def add(name: str, passed: bool, value: str, requirement: str) -> None:
        checks.append(
            {
                "check": name,
                "passed": bool(passed),
                "value": value,
                "requirement": requirement,
            }
        )

    expected_dates = pd.date_range("2016-01-01", "2021-12-01", freq="MS")
    add("monthly_observation_count", len(monthly) == 72, str(len(monthly)), "exactly 72")
    modeling_months = int(monthly["year"].ge(REGIME_START_YEAR).sum())
    add("post_break_modeling_count", modeling_months == 48, str(modeling_months), "exactly 48 months from 2018-01 through 2021-12")
    add(
        "monthly_calendar_complete",
        pd.DatetimeIndex(monthly["date"]).equals(expected_dates),
        f"{monthly['date'].min().date()} to {monthly['date'].max().date()}",
        "continuous 2016-01 through 2021-12",
    )
    target_columns = [target for target, _, _ in TARGETS]
    positive = bool((monthly[target_columns] > 0).all().all() and (forecast[target_columns] > 0).all().all())
    add("positive_totals", positive, str(positive), "all observed and forecast totals > 0")

    nested = True
    for target in target_columns:
        nested &= bool(
            (
                (forecast[f"{target}_lower95"] <= forecast[f"{target}_lower80"])
                & (forecast[f"{target}_lower80"] <= forecast[target])
                & (forecast[target] <= forecast[f"{target}_upper80"])
                & (forecast[f"{target}_upper80"] <= forecast[f"{target}_upper95"])
            ).all()
        )
    add("forecast_interval_nesting", nested, str(nested), "lower95 <= lower80 <= point <= upper80 <= upper95")

    wider = True
    for target in target_columns:
        by_year = {}
        for year in (2022, 2023):
            frame = forecast[forecast["year"].eq(year)]
            by_year[year] = (
                np.log1p(frame[f"{target}_upper95"].to_numpy(dtype=float))
                - np.log1p(frame[f"{target}_lower95"].to_numpy(dtype=float))
            )
        wider &= bool(np.all(by_year[2023] > by_year[2022]))
    add("second_year_intervals_wider", wider, str(wider), "every 2023 log interval wider than matching 2022 month")

    annual_matches = True
    for target in target_columns:
        expected = forecast.groupby("year")[target].sum().to_numpy(dtype=float)
        actual = annual[target].to_numpy(dtype=float)
        annual_matches &= bool(np.allclose(actual, expected, rtol=1e-12, atol=1e-9))
    add("annual_point_totals_match", annual_matches, str(annual_matches), "annual points equal sums of monthly points")

    forbidden = [column for column in schedule.columns if any(word in column.lower() for word in ("water", "sediment", "flux"))]
    add("schedule_has_no_daily_flux", not forbidden, ", ".join(forbidden) if forbidden else "none", "sampling dates/times only")
    max_difference = float(consistency["max_abs_pct"].max())
    add("integration_reference_difference", max_difference <= 1.0, f"{max_difference:.6f}%", "maximum difference <= 1%")
    return pd.DataFrame(checks)


def minmax(values: pd.Series) -> pd.Series:
    low = float(values.min())
    high = float(values.max())
    if high == low:
        return pd.Series(np.zeros(len(values)), index=values.index)
    return (values - low) / (high - low)


def abrupt_month_risk(q2_events: Path) -> dict[int, float]:
    if not q2_events.exists():
        return {month: 0.0 for month in range(1, 13)}
    events = pd.read_csv(q2_events, parse_dates=["date"])
    counts = events["date"].dt.month.value_counts()
    maximum = max(1, int(counts.max()))
    return {month: float(counts.get(month, 0) / maximum) for month in range(1, 13)}


def sampling_strategy(
    monthly_forecast: pd.DataFrame, q2_events: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategy = monthly_forecast[["date", "year", "month"]].copy()
    upper = monthly_forecast["sediment_mass_1e4_t_upper95"]
    point = monthly_forecast["sediment_mass_1e4_t"]
    relative_width = (
        monthly_forecast["sediment_mass_1e4_t_upper95"]
        - monthly_forecast["sediment_mass_1e4_t_lower95"]
    ) / np.maximum(point, 1e-9)
    strategy["pred_sediment_mass_1e4_t"] = point
    strategy["upper95_sediment_mass_1e4_t"] = upper
    strategy["relative_interval_width"] = relative_width
    strategy["historical_abrupt_month_risk"] = strategy["month"].map(
        abrupt_month_risk(q2_events)
    )
    strategy["is_flood"] = strategy["month"].between(6, 10).astype(float)
    strategy["is_peak_window"] = strategy["month"].between(7, 10).astype(float)
    strategy["risk_score"] = (
        0.45 * minmax(np.log1p(upper))
        + 0.20 * minmax(relative_width)
        + 0.20 * strategy["is_flood"]
        + 0.10 * strategy["is_peak_window"]
        + 0.05 * strategy["historical_abrupt_month_risk"]
    )
    high_threshold = float(strategy["risk_score"].quantile(0.70))
    strategy["risk_level"] = np.where(
        strategy["risk_score"] >= high_threshold,
        "high",
        np.where(strategy["month"].between(4, 11), "medium", "low"),
    )
    settings = {
        "high": (2, ["08:00", "14:00", "20:00"], "汛期或高不确定月份，两日一次并进行日内三时段跟踪"),
        "medium": (5, ["08:00", "20:00"], "过渡月份，五日一次并覆盖早晚变化"),
        "low": (10, ["09:00"], "低风险月份，十日一次常规监测"),
    }
    schedule_rows = []
    sample_counts = []
    for _, row in strategy.iterrows():
        start = pd.Timestamp(row["date"])
        end = start + pd.offsets.MonthBegin(1)
        interval_days, times, reason = settings[str(row["risk_level"])]
        dates = pd.date_range(start, end - pd.Timedelta(days=1), freq=f"{interval_days}D")
        for date in dates:
            for sample_time in times:
                schedule_rows.append(
                    {
                        "sample_datetime": f"{date.strftime('%Y-%m-%d')} {sample_time}",
                        "date": date.strftime("%Y-%m-%d"),
                        "year": int(row["year"]),
                        "month": int(row["month"]),
                        "sample_time": sample_time,
                        "risk_level": row["risk_level"],
                        "monthly_risk_score": float(row["risk_score"]),
                        "reason": reason,
                    }
                )
        sample_counts.append(len(dates) * len(times))
    strategy["recommended_sample_times"] = sample_counts
    return strategy, pd.DataFrame(schedule_rows)


def get_font(size: int, bold: bool = False):
    paths = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for path in paths:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def draw_series_panel(
    draw: ImageDraw.ImageDraw,
    title: str,
    rect: tuple[int, int, int, int],
    actual: pd.DataFrame,
    predicted: pd.DataFrame,
    actual_col: str,
    predicted_col: str,
    lower_col: str,
    upper_col: str,
    full_start: pd.Timestamp,
    full_end: pd.Timestamp,
    inner_lower_col: str | None = None,
    inner_upper_col: str | None = None,
) -> None:
    left, top, right, bottom = rect
    label_font = get_font(20, True)
    tick_font = get_font(14)
    values = np.r_[actual[actual_col].to_numpy(dtype=float), predicted[upper_col].to_numpy(dtype=float)]
    ymax = float(np.nanmax(values)) * 1.08
    draw.text((left, top - 40), title, font=label_font, fill=(31, 41, 55, 255))
    for tick in range(6):
        value = ymax * tick / 5
        y = bottom - value / ymax * (bottom - top)
        draw.line((left, y, right, y), fill=(225, 229, 235, 255), width=1)
        draw.text((left - 78, y - 8), f"{value:.0f}", font=tick_font, fill=(95, 104, 118, 255))
    draw.line((left, top, left, bottom), fill=(55, 65, 81, 255), width=2)
    draw.line((left, bottom, right, bottom), fill=(55, 65, 81, 255), width=2)
    total_days = max(1, (full_end - full_start).days)

    def xy(date: pd.Timestamp, value: float) -> tuple[float, float]:
        x = left + (date - full_start).days / total_days * (right - left)
        y = bottom - value / ymax * (bottom - top)
        return x, y

    for year in range(full_start.year, full_end.year + 1):
        date = pd.Timestamp(f"{year}-01-01")
        if full_start <= date <= full_end:
            x, _ = xy(date, 0)
            draw.line((x, bottom, x, bottom + 7), fill=(55, 65, 81, 255), width=1)
            draw.text((x - 18, bottom + 13), str(year), font=tick_font, fill=(55, 65, 81, 255))
    x_values = [xy(pd.Timestamp(date), 0)[0] for date in predicted["date"]]
    lower_values = [xy(pd.Timestamp(date), float(value))[1] for date, value in zip(predicted["date"], predicted[lower_col])]
    upper_values = [xy(pd.Timestamp(date), float(value))[1] for date, value in zip(predicted["date"], predicted[upper_col])]
    if x_values:
        band = list(zip(x_values, upper_values)) + list(zip(x_values[::-1], lower_values[::-1]))
        draw.polygon(band, fill=(239, 68, 68, 30))
    if inner_lower_col and inner_upper_col and x_values:
        inner_lower = [
            xy(pd.Timestamp(date), float(value))[1]
            for date, value in zip(predicted["date"], predicted[inner_lower_col])
        ]
        inner_upper = [
            xy(pd.Timestamp(date), float(value))[1]
            for date, value in zip(predicted["date"], predicted[inner_upper_col])
        ]
        inner_band = list(zip(x_values, inner_upper)) + list(zip(x_values[::-1], inner_lower[::-1]))
        draw.polygon(inner_band, fill=(239, 68, 68, 58))
    actual_points = [xy(pd.Timestamp(date), float(value)) for date, value in zip(actual["date"], actual[actual_col])]
    predicted_points = [
        xy(pd.Timestamp(date), float(value)) for date, value in zip(predicted["date"], predicted[predicted_col])
    ]
    if len(actual_points) > 1:
        draw.line(actual_points, fill=(31, 41, 55, 255), width=4)
    if len(predicted_points) > 1:
        draw.line(predicted_points, fill=(220, 38, 38, 255), width=4)

    legend_font = get_font(13)
    legend_y = top - 33
    legend_x = right - 450
    draw.line((legend_x, legend_y + 8, legend_x + 28, legend_y + 8), fill=(31, 41, 55, 255), width=3)
    draw.text((legend_x + 34, legend_y), "实际", font=legend_font, fill=(55, 65, 81, 255))
    draw.line((legend_x + 90, legend_y + 8, legend_x + 118, legend_y + 8), fill=(220, 38, 38, 255), width=3)
    draw.text((legend_x + 124, legend_y), "预测", font=legend_font, fill=(55, 65, 81, 255))
    draw.rectangle((legend_x + 185, legend_y + 1, legend_x + 211, legend_y + 15), fill=(239, 68, 68, 58))
    draw.text((legend_x + 218, legend_y), "80%", font=legend_font, fill=(55, 65, 81, 255))
    draw.rectangle((legend_x + 282, legend_y + 1, legend_x + 308, legend_y + 15), fill=(239, 68, 68, 30))
    draw.text((legend_x + 315, legend_y), "95%", font=legend_font, fill=(55, 65, 81, 255))


def save_backtest_figure(monthly: pd.DataFrame, backtest: pd.DataFrame, path: Path) -> None:
    width, height = 1640, 940
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    title = "历史对照：2019-2020选模回测与2021预测模型层条件留出"
    font = get_font(30, True)
    box = draw.textbbox((0, 0), title, font=font)
    draw.text(((width - box[2] + box[0]) / 2, 24), title, font=font, fill=(25, 34, 48, 255))
    history = monthly[monthly["year"] >= REGIME_START_YEAR].copy()
    for index, (target, label, _) in enumerate(TARGETS):
        panel = backtest[backtest["target"].eq(target)].sort_values("date")
        top = 125 if index == 0 else 595
        draw_series_panel(
            draw,
            label,
            (115, top, 1570, top + 300),
            history,
            panel,
            target,
            "predicted",
            "lower95",
            "upper95",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2021-12-01"),
            "lower80",
            "upper80",
        )
    image.save(path)


def save_forecast_figure(monthly: pd.DataFrame, forecast: pd.DataFrame, path: Path) -> None:
    width, height = 1640, 940
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    title = "月水量与月输沙量：历史积分及2022-2023预测区间"
    font = get_font(30, True)
    box = draw.textbbox((0, 0), title, font=font)
    draw.text(((width - box[2] + box[0]) / 2, 24), title, font=font, fill=(25, 34, 48, 255))
    history = monthly[monthly["year"] >= 2018].copy()
    boundary_font = get_font(16, True)
    boundary_label = "2022预测起点"
    for index, (target, label, _) in enumerate(TARGETS):
        top = 125 if index == 0 else 595
        draw_series_panel(
            draw,
            label,
            (115, top, 1570, top + 300),
            history,
            forecast,
            target,
            target,
            f"{target}_lower95",
            f"{target}_upper95",
            pd.Timestamp("2018-01-01"),
            pd.Timestamp("2023-12-01"),
            f"{target}_lower80",
            f"{target}_upper80",
        )
        boundary = 115 + (pd.Timestamp("2022-01-01") - pd.Timestamp("2018-01-01")).days / (
            pd.Timestamp("2023-12-01") - pd.Timestamp("2018-01-01")
        ).days * (1570 - 115)
        y = top
        while y < top + 300:
            draw.line((boundary, y, boundary, min(y + 10, top + 300)), fill=(37, 99, 235, 220), width=3)
            y += 18
        label_box = draw.textbbox((0, 0), boundary_label, font=boundary_font)
        label_width = label_box[2] - label_box[0]
        label_height = label_box[3] - label_box[1]
        draw.rounded_rectangle(
            (boundary + 7, top + 7, boundary + 17 + label_width, top + 17 + label_height),
            radius=4,
            fill=(255, 255, 255, 220),
        )
        draw.text(
            (boundary + 12, top + 10),
            boundary_label,
            font=boundary_font,
            fill=(37, 99, 235, 255),
        )
    image.save(path)


def save_sampling_figure(strategy: pd.DataFrame, path: Path) -> None:
    width, height = 1500, 650
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(29, True)
    tick_font = get_font(14)
    axis_font = get_font(18, True)
    legend_font = get_font(16)
    title = "2022—2023 月度建议采样时次"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    draw.text(
        ((width - title_box[2] + title_box[0]) / 2, 20),
        title,
        font=title_font,
        fill=(25, 34, 48),
    )
    left, top, right, bottom = 100, 100, 1440, 560
    axis_label = "采样时次数"
    axis_box = draw.textbbox((0, 0), axis_label, font=axis_font)
    axis_layer = Image.new(
        "RGBA",
        (axis_box[2] - axis_box[0] + 12, axis_box[3] - axis_box[1] + 12),
        (255, 255, 255, 0),
    )
    axis_draw = ImageDraw.Draw(axis_layer)
    axis_draw.text((6, 4), axis_label, font=axis_font, fill=(55, 65, 81, 255))
    axis_layer = axis_layer.rotate(90, expand=True)
    image.paste(
        axis_layer,
        (10, int((top + bottom - axis_layer.height) / 2)),
        axis_layer,
    )
    values = strategy["recommended_sample_times"].to_numpy(dtype=float)
    ymax = float(values.max()) * 1.15
    for tick in range(6):
        value = ymax * tick / 5
        y = bottom - value / ymax * (bottom - top)
        draw.line((left, y, right, y), fill=(225, 229, 235), width=1)
        draw.text((left - 48, y - 8), f"{value:.0f}", font=tick_font, fill=(95, 104, 118))
    group_width = (right - left) / len(values)
    colors = {"high": (220, 38, 38), "medium": (234, 136, 36), "low": (37, 99, 235)}
    legend_items = (("high", "高风险"), ("medium", "中风险"), ("low", "低风险"))
    legend_x, legend_y = 1035, 69
    for legend_index, (risk_level, risk_label) in enumerate(legend_items):
        x = legend_x + legend_index * 125
        draw.rectangle((x, legend_y, x + 20, legend_y + 14), fill=colors[risk_level])
        draw.text((x + 27, legend_y - 3), risk_label, font=legend_font, fill=(55, 65, 81))
    for index, row in strategy.reset_index(drop=True).iterrows():
        height = float(row["recommended_sample_times"]) / ymax * (bottom - top)
        x0 = left + index * group_width + group_width * 0.17
        x1 = left + (index + 1) * group_width - group_width * 0.17
        draw.rectangle((x0, bottom - height, x1, bottom), fill=colors[str(row["risk_level"])])
        if index % 2 == 0:
            label = f"{int(row['year'])}-{int(row['month']):02d}"
            draw.text((x0 - 8, bottom + 15), label, font=tick_font, fill=(55, 65, 81))
    image.save(path)


def dataframe_to_markdown(data: pd.DataFrame) -> str:
    frame = data.copy()
    for column in frame.select_dtypes(include=["float"]).columns:
        frame[column] = frame[column].map(lambda value: "" if pd.isna(value) else f"{value:.5g}")
    headers = list(frame.columns)
    widths = [max(len(str(header)), *(len(str(value)) for value in frame[header])) for header in headers]
    lines = [
        "| " + " | ".join(str(header).ljust(width) for header, width in zip(headers, widths)) + " |",
        "| " + " | ".join("-" * width for width in widths) + " |",
    ]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(str(row[header]).ljust(width) for header, width in zip(headers, widths)) + " |")
    return "\n".join(lines)


def write_summary(
    run_dir: Path,
    selected: dict[str, Candidate],
    comparison: pd.DataFrame,
    coverage: pd.DataFrame,
    annual: pd.DataFrame,
    strategy: pd.DataFrame,
    quality: pd.DataFrame,
) -> None:
    selected_rows = []
    for target, _, _ in TARGETS:
        mean_row = comparison[
            comparison["target"].eq(target)
            & comparison["model_label"].eq(selected[target].label)
            & comparison["heldout_year"].eq("mean")
        ].iloc[0]
        selected_rows.append(
            {
                "target": target,
                "selected_model": selected[target].label,
                "validation_rmse_log": mean_row["rmse_log"],
                "validation_r2_log": mean_row["r2_log"],
                "validation_wape": mean_row["wape"],
            }
        )
    lines = [
        "# Run summary",
        "",
        "## Selected monthly models",
        "",
        dataframe_to_markdown(pd.DataFrame(selected_rows)),
        "",
        "## Interval calibration",
        "",
        dataframe_to_markdown(coverage),
        "",
        "## Annual forecast",
        "",
        dataframe_to_markdown(annual),
        "",
        "## Quality checks",
        "",
        dataframe_to_markdown(quality),
        "",
        "## Sampling intensity",
        "",
        dataframe_to_markdown(
            strategy[["year", "month", "risk_level", "risk_score", "recommended_sample_times"]]
        ),
        "",
        "The daily output is a sampling schedule only. No future daily water or sediment flux series is produced.",
        "",
    ]
    (run_dir / "results" / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--q1-series", type=Path, default=DEFAULT_Q1_SERIES)
    parser.add_argument("--q2-daily", type=Path, default=DEFAULT_Q2_DAILY)
    parser.add_argument("--q2-events", type=Path, default=DEFAULT_Q2_EVENTS)
    args = parser.parse_args()
    q1_series = resolve_input(args.q1_series)
    q2_daily = resolve_input(args.q2_daily)
    q2_events = resolve_input(args.q2_events)
    run_dir = prepare_run_dir(Path(args.run_dir))

    observations = load_observations(q1_series)
    monthly = monthly_trapezoid_totals(observations)
    consistency = integration_consistency(monthly, q2_daily)
    comparison, selected = compare_models(monthly)
    backtest, residuals = historical_backtest(monthly, selected)
    backtest, coverage = add_backtest_intervals(backtest, residuals)
    forecast = forecast_months(monthly, selected, residuals)
    annual = annual_forecast(forecast)
    strategy, schedule = sampling_strategy(forecast, q2_events)
    quality = build_quality_checks(monthly, forecast, annual, schedule, consistency)

    monthly.to_csv(run_dir / "results" / "monthly_observed_totals.csv", index=False, encoding="utf-8-sig")
    forecast.to_csv(run_dir / "results" / "monthly_forecast_2022_2023.csv", index=False, encoding="utf-8-sig")
    annual.to_csv(run_dir / "results" / "annual_forecast_2022_2023.csv", index=False, encoding="utf-8-sig")
    strategy.to_csv(run_dir / "results" / "monthly_sampling_strategy.csv", index=False, encoding="utf-8-sig")
    schedule.to_csv(run_dir / "results" / "sampling_schedule_2022_2023.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(run_dir / "validation" / "model_comparison.csv", index=False, encoding="utf-8-sig")
    backtest.to_csv(run_dir / "validation" / "backtest_predictions.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(run_dir / "validation" / "interval_coverage.csv", index=False, encoding="utf-8-sig")
    consistency.to_csv(run_dir / "validation" / "integration_consistency.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(run_dir / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")

    save_backtest_figure(monthly, backtest, run_dir / "figures" / "historical_backtest.png")
    save_forecast_figure(monthly, forecast, run_dir / "figures" / "monthly_forecast_intervals.png")
    save_sampling_figure(strategy, run_dir / "figures" / "sampling_intensity.png")
    write_summary(run_dir, selected, comparison, coverage, annual, strategy, quality)

    selected_text = ", ".join(f"{target}={candidate.label}" for target, candidate in selected.items())
    log_lines = [
        f"observations={len(observations)}",
        f"monthly_rows={len(monthly)}",
        f"modeling_months={int(monthly['year'].ge(REGIME_START_YEAR).sum())}",
        f"model_selection_years={','.join(str(year) for year in MODEL_SELECTION_YEARS)}",
        f"holdout_test_years={','.join(str(year) for year in HOLDOUT_TEST_YEARS)}",
        f"selected_models={selected_text}",
        f"sampling_times={len(schedule)}",
        f"max_integration_difference_pct={consistency['max_abs_pct'].max():.6f}",
        f"quality_checks_passed={int(quality['passed'].sum())}/{len(quality)}",
        f"q1_series={report_input_path(q1_series)}",
        f"q1_series_sha256={sha256_file(q1_series)}",
        f"q2_daily={report_input_path(q2_daily)}",
        f"q2_daily_sha256={sha256_file(q2_daily)}",
        f"q2_events={report_input_path(q2_events)}",
        f"q2_events_sha256={sha256_file(q2_events)}",
    ]
    (run_dir / "logs" / "run_summary.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n".join(log_lines))
    print("\nAnnual forecast:")
    print(annual.to_string(index=False))
    print("\nInterval coverage:")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
