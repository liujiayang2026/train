from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


SCRIPT_PATH = Path(__file__).resolve()
ROUTE_DIR = SCRIPT_PATH.parents[1]
RUNS_DIR = ROUTE_DIR / "runs"
START = pd.Timestamp("2016-01-01 00:00:00")
END = pd.Timestamp("2022-01-01 00:00:00")
SECONDS_PER_DAY = 24 * 3600
BASELINE_METHOD = "linear_flux_direct"
INTERPOLATION_METHODS = (
    "linear_flux_direct",
    "linear_components_product",
    "previous_flux_direct",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reproduce the Q2 daily water/sediment-pattern route in a new canonical run."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Q1 cleaned_hydro_timeseries.csv used as the explicit upstream input.",
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="A pre-recorded, unused run-* directory under this route's runs/ directory.",
    )
    parser.add_argument("--event-window", type=int, default=7)
    parser.add_argument("--event-threshold", type=float, default=3.0)
    parser.add_argument("--event-gap-days", type=int, default=20)
    parser.add_argument("--event-top-n", type=int, default=15)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_run_dir(run_dir: Path) -> dict[str, Path]:
    run_dir = run_dir.resolve()
    expected_parent = RUNS_DIR.resolve()
    if run_dir.parent != expected_parent:
        raise ValueError(f"--run-dir must be a direct child of {expected_parent}")
    if not run_dir.name.startswith("run-"):
        raise ValueError("--run-dir name must start with 'run-'.")
    if not (run_dir / "run.md").is_file():
        raise FileNotFoundError("Create run.md before execution so the run has an owner and provenance record.")
    occupied = sorted((item for item in run_dir.iterdir() if item.name != "run.md"), key=lambda item: item.name)
    if occupied:
        raise FileExistsError(
            "Refusing to overwrite an existing run; only the pre-recorded run.md may exist before execution: "
            + ", ".join(str(item) for item in occupied)
        )

    paths = {
        "run": run_dir,
        "data": run_dir / "results" / "data" / "processed",
        "tables": run_dir / "results" / "tables",
        "reports": run_dir / "results" / "reports",
        "figures": run_dir / "figures",
        "validation": run_dir / "validation",
        "logs": run_dir / "logs",
    }
    for key, path in paths.items():
        if key == "run":
            continue
        path.mkdir(parents=True, exist_ok=False)
    return paths


def load_question1_series(path: Path) -> pd.DataFrame:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing required Q1 cleaned series: {path}")
    df = pd.read_csv(path, parse_dates=["datetime"])
    needed = ["datetime", "flow_m3s", "sediment_used_kgm3", "sediment_flux_kg_s"]
    missing = [column for column in needed if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in Q1 output: {missing}")
    optional = [column for column in ["sediment_obs_kgm3", "sediment_filled_flag"] if column in df.columns]
    df = df[needed + optional].copy()
    df = df.sort_values("datetime").drop_duplicates("datetime", keep="last")
    df = df[(df["datetime"] >= START) & (df["datetime"] < END)].reset_index(drop=True)
    if df.empty:
        raise ValueError("Q1 input has no rows in 2016-2021.")
    for column in needed[1:]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if df[needed].isna().any().any():
        counts = df[needed].isna().sum()
        raise ValueError(f"Q1 required fields contain missing values:\n{counts[counts > 0]}")
    if (df[["flow_m3s", "sediment_used_kgm3", "sediment_flux_kg_s"]] < 0).any().any():
        raise ValueError("Q1 required physical quantities must be non-negative.")
    return df


def build_daily_series(df: pd.DataFrame, method: str) -> pd.DataFrame:
    if method not in INTERPOLATION_METHODS:
        raise ValueError(f"Unknown interpolation method: {method}")
    indexed = df.set_index("datetime").sort_index()
    target_hours = pd.date_range(START, END, freq="1h", inclusive="left")
    expanded = indexed.reindex(indexed.index.union(target_hours)).sort_index()
    columns = ["flow_m3s", "sediment_used_kgm3", "sediment_flux_kg_s"]

    if method in {"linear_flux_direct", "linear_components_product"}:
        expanded[columns] = expanded[columns].interpolate(method="time", limit_direction="both")
    elif method == "previous_flux_direct":
        expanded[columns] = expanded[columns].ffill().bfill()

    if method == "linear_components_product":
        expanded["sediment_flux_kg_s"] = expanded["flow_m3s"] * expanded["sediment_used_kgm3"]

    hourly = expanded.loc[target_hours, columns]
    daily = hourly.resample("D").mean()
    daily.index.name = "date"
    daily = daily.rename(
        columns={
            "flow_m3s": "mean_flow_m3s",
            "sediment_used_kgm3": "mean_sediment_kgm3",
            "sediment_flux_kg_s": "mean_sediment_flux_kg_s",
        }
    )
    daily["water_volume_m3"] = daily["mean_flow_m3s"] * SECONDS_PER_DAY
    daily["sediment_mass_kg"] = daily["mean_sediment_flux_kg_s"] * SECONDS_PER_DAY
    daily["water_volume_1e8_m3"] = daily["water_volume_m3"] / 1e8
    daily["sediment_mass_1e4_t"] = daily["sediment_mass_kg"] / 1e7
    daily["year"] = daily.index.year
    daily["month"] = daily.index.month
    daily["day_of_year"] = daily.index.dayofyear
    return daily.reset_index()


def validate_daily_series(daily: pd.DataFrame) -> None:
    expected_days = len(pd.date_range(START, END, freq="D", inclusive="left"))
    if len(daily) != expected_days:
        raise ValueError(f"Expected {expected_days} daily rows, got {len(daily)}.")
    if daily["date"].duplicated().any() or not daily["date"].is_monotonic_increasing:
        raise ValueError("Daily dates must be unique and increasing.")
    numeric = [
        "mean_flow_m3s",
        "mean_sediment_kgm3",
        "mean_sediment_flux_kg_s",
        "water_volume_m3",
        "sediment_mass_kg",
    ]
    if not np.isfinite(daily[numeric].to_numpy(dtype=float)).all():
        raise ValueError("Daily series contains non-finite physical values.")
    if (daily[numeric] < 0).any().any():
        raise ValueError("Daily series contains negative physical values.")


def seasonal_summary(daily: pd.DataFrame) -> pd.DataFrame:
    total_water = daily["water_volume_m3"].sum()
    total_sediment = daily["sediment_mass_kg"].sum()
    monthly = (
        daily.groupby("month", as_index=False)
        .agg(
            days=("date", "size"),
            mean_flow_m3s=("mean_flow_m3s", "mean"),
            mean_sediment_kgm3=("mean_sediment_kgm3", "mean"),
            mean_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "mean"),
            water_volume_1e8_m3=("water_volume_1e8_m3", "sum"),
            sediment_mass_1e4_t=("sediment_mass_1e4_t", "sum"),
        )
    )
    monthly["water_share"] = monthly["water_volume_1e8_m3"] * 1e8 / total_water
    monthly["sediment_share"] = monthly["sediment_mass_1e4_t"] * 1e7 / total_sediment
    monthly["sediment_to_water_share_ratio"] = monthly["sediment_share"] / monthly["water_share"]
    return monthly


def annual_summary(daily: pd.DataFrame) -> pd.DataFrame:
    annual = (
        daily.groupby("year", as_index=False)
        .agg(
            days=("date", "size"),
            water_volume_1e8_m3=("water_volume_1e8_m3", "sum"),
            sediment_mass_1e4_t=("sediment_mass_1e4_t", "sum"),
            mean_flow_m3s=("mean_flow_m3s", "mean"),
            mean_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "mean"),
            max_daily_flow_m3s=("mean_flow_m3s", "max"),
            max_daily_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "max"),
        )
    )
    annual["water_yoy_change"] = annual["water_volume_1e8_m3"].pct_change()
    annual["sediment_yoy_change"] = annual["sediment_mass_1e4_t"].pct_change()
    return annual


def high_flux_concentration(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month_set, label in [([6, 7], "jun_jul"), ([6, 7, 8, 9, 10], "jun_oct"), ([7], "jul")]:
        part = daily[daily["month"].isin(month_set)]
        rows.append(
            {
                "period": label,
                "days": int(len(part)),
                "water_share": float(part["water_volume_m3"].sum() / daily["water_volume_m3"].sum()),
                "sediment_share": float(part["sediment_mass_kg"].sum() / daily["sediment_mass_kg"].sum()),
                "mean_flow_m3s": float(part["mean_flow_m3s"].mean()),
                "mean_sediment_flux_kg_s": float(part["mean_sediment_flux_kg_s"].mean()),
            }
        )
    return pd.DataFrame(rows)


def abrupt_candidates(daily: pd.DataFrame, window: int) -> pd.DataFrame:
    if window < 2:
        raise ValueError("Abrupt-change window must be at least 2 days.")
    data = daily.sort_values("date").copy()
    data["log_flow"] = np.log1p(data["mean_flow_m3s"])
    data["log_sediment_flux"] = np.log1p(data["mean_sediment_flux_kg_s"])
    for source, prefix in [("log_flow", "flow"), ("log_sediment_flux", "sediment")]:
        before = data[source].shift(1).rolling(window).mean()
        after = data[source].rolling(window).mean().shift(-window + 1)
        contrast = after - before
        scale = contrast.std(skipna=True)
        if not np.isfinite(scale) or scale == 0:
            scale = 1.0
        data[f"{prefix}_contrast_z"] = contrast / scale
    data["abrupt_score"] = np.maximum(data["flow_contrast_z"].abs(), data["sediment_contrast_z"].abs())
    data["main_direction"] = np.where(
        data["sediment_contrast_z"].abs() >= data["flow_contrast_z"].abs(),
        np.where(data["sediment_contrast_z"] >= 0, "sediment_rise", "sediment_fall"),
        np.where(data["flow_contrast_z"] >= 0, "flow_rise", "flow_fall"),
    )
    columns = [
        "date",
        "year",
        "month",
        "mean_flow_m3s",
        "mean_sediment_kgm3",
        "mean_sediment_flux_kg_s",
        "flow_contrast_z",
        "sediment_contrast_z",
        "abrupt_score",
        "main_direction",
    ]
    return data.dropna(subset=["abrupt_score"])[columns].copy()


def select_events(
    candidates: pd.DataFrame,
    threshold: float,
    min_gap_days: int,
    top_n: int,
) -> pd.DataFrame:
    eligible = candidates[candidates["abrupt_score"] >= threshold]
    selected: list[pd.Series] = []
    used_dates: list[pd.Timestamp] = []
    for _, row in eligible.sort_values("abrupt_score", ascending=False).iterrows():
        date = pd.Timestamp(row["date"])
        if all(abs((date - used_date).days) >= min_gap_days for used_date in used_dates):
            selected.append(row)
            used_dates.append(date)
        if len(selected) >= top_n:
            break
    if not selected:
        return eligible.head(0).copy()
    return pd.DataFrame(selected).sort_values("date").reset_index(drop=True)


def abrupt_change_events(
    daily: pd.DataFrame,
    window: int,
    threshold: float,
    min_gap_days: int,
    top_n: int,
) -> pd.DataFrame:
    return select_events(abrupt_candidates(daily, window), threshold, min_gap_days, top_n)


def matching_fraction(source_dates: pd.Series, target_dates: pd.Series, tolerance_days: int = 7) -> float:
    source = [pd.Timestamp(value) for value in source_dates]
    target = [pd.Timestamp(value) for value in target_dates]
    if not source:
        return 1.0 if not target else 0.0
    if not target:
        return 0.0
    matched = sum(any(abs((date - other).days) <= tolerance_days for other in target) for date in source)
    return matched / len(source)


def periodogram(series: pd.Series, name: str) -> pd.DataFrame:
    y = np.log1p(series.to_numpy(dtype=float))
    y = pd.Series(y).interpolate(limit_direction="both").to_numpy()
    x = np.arange(len(y), dtype=float)
    coef = np.polyfit(x, y, deg=1)
    detrended = y - np.polyval(coef, x)
    detrended = detrended - detrended.mean()
    spectrum = np.fft.rfft(detrended * np.hanning(len(detrended)))
    frequency = np.fft.rfftfreq(len(detrended), d=1.0)
    power = np.abs(spectrum) ** 2
    valid = frequency > 0
    periods = 1 / frequency[valid]
    power = power[valid]
    band = (periods >= 20) & (periods <= 800)
    periods = periods[band]
    power = power[band]
    total_power = power.sum()
    table = pd.DataFrame(
        {
            "series": name,
            "period_days": periods,
            "period_months": periods / 30.4375,
            "relative_power": power / total_power if total_power else np.nan,
        }
    )
    return table.sort_values("relative_power", ascending=False).head(10).reset_index(drop=True)


def dominant_period_metrics(series: pd.Series) -> dict[str, float | bool]:
    peaks = periodogram(series, "series")
    dominant = peaks.iloc[0]
    annual = peaks[(peaks["period_days"] >= 300) & (peaks["period_days"] <= 450)]
    annual_peak = annual.iloc[0] if not annual.empty else None
    return {
        "dominant_period_days": float(dominant["period_days"]),
        "dominant_relative_power": float(dominant["relative_power"]),
        "annual_band_peak_days": float(annual_peak["period_days"]) if annual_peak is not None else np.nan,
        "annual_band_peak_relative_power": float(annual_peak["relative_power"]) if annual_peak is not None else np.nan,
        "dominant_is_annual_scale": bool(300 <= float(dominant["period_days"]) <= 450),
    }


def autocorrelation_lags(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column, name in [
        ("mean_flow_m3s", "water_flux"),
        ("mean_sediment_flux_kg_s", "sediment_flux"),
    ]:
        y = np.log1p(daily[column].to_numpy(dtype=float))
        y = y - np.nanmean(y)
        for lag in [7, 15, 30, 60, 90, 120, 180, 365]:
            corr = np.corrcoef(y[:-lag], y[lag:])[0, 1]
            rows.append({"series": name, "lag_days": lag, "autocorrelation": float(corr)})
    return pd.DataFrame(rows)


def input_quality_summary(source: pd.DataFrame) -> pd.DataFrame:
    gaps = source["datetime"].diff().dt.total_seconds().dropna() / 3600
    rows = [
        ("input_rows", len(source), "rows", "Unique Q1 timestamps in 2016-2021"),
        ("start_time", source["datetime"].min().isoformat(), "datetime", "First upstream timestamp"),
        ("end_time", source["datetime"].max().isoformat(), "datetime", "Last upstream timestamp"),
        ("median_gap_hours", float(gaps.median()), "hours", "Median interval between upstream rows"),
        ("max_gap_hours", float(gaps.max()), "hours", "Maximum interval between upstream rows"),
    ]
    if "sediment_filled_flag" in source.columns:
        filled = source["sediment_filled_flag"].astype(str).str.lower().isin(["true", "1"])
        rows.append(
            (
                "q1_model_filled_sediment_share",
                float(filled.mean()),
                "fraction",
                "Share of upstream timestamps whose sediment concentration came from the Q1 model",
            )
        )
    if "sediment_obs_kgm3" in source.columns:
        rows.append(
            (
                "q1_observed_sediment_share",
                float(source["sediment_obs_kgm3"].notna().mean()),
                "fraction",
                "Share of upstream timestamps with observed sediment concentration",
            )
        )
    return pd.DataFrame(rows, columns=["metric", "value", "unit", "interpretation"])


def interpolation_sensitivity(
    daily_by_method: dict[str, pd.DataFrame],
    baseline_events: pd.DataFrame,
    event_parameters: dict[str, float | int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline = daily_by_method[BASELINE_METHOD]
    baseline_monthly = seasonal_summary(baseline)
    baseline_water = baseline["water_volume_m3"].sum()
    baseline_sediment = baseline["sediment_mass_kg"].sum()
    summary_rows = []
    annual_rows = []
    monthly_rows = []
    overlap_rows = []

    for method, daily in daily_by_method.items():
        monthly = seasonal_summary(daily)
        concentration = high_flux_concentration(daily).set_index("period")
        water_total = daily["water_volume_m3"].sum()
        sediment_total = daily["sediment_mass_kg"].sum()
        water_share_delta = (monthly["water_share"] - baseline_monthly["water_share"]).abs() * 100
        sediment_share_delta = (monthly["sediment_share"] - baseline_monthly["sediment_share"]).abs() * 100
        summary_rows.append(
            {
                "method": method,
                "water_total_1e8_m3": water_total / 1e8,
                "sediment_total_1e4_t": sediment_total / 1e7,
                "water_total_relative_difference": water_total / baseline_water - 1,
                "sediment_total_relative_difference": sediment_total / baseline_sediment - 1,
                "max_monthly_water_share_difference_pp": float(water_share_delta.max()),
                "max_monthly_sediment_share_difference_pp": float(sediment_share_delta.max()),
                "jun_oct_water_share": float(concentration.loc["jun_oct", "water_share"]),
                "jun_oct_sediment_share": float(concentration.loc["jun_oct", "sediment_share"]),
                "peak_water_month": int(monthly.loc[monthly["water_share"].idxmax(), "month"]),
                "peak_sediment_month": int(monthly.loc[monthly["sediment_share"].idxmax(), "month"]),
            }
        )
        annual = annual_summary(daily).copy()
        annual.insert(0, "method", method)
        annual_rows.append(annual)
        monthly_table = monthly.copy()
        monthly_table.insert(0, "method", method)
        monthly_rows.append(monthly_table)

        events = abrupt_change_events(
            daily,
            int(event_parameters["window"]),
            float(event_parameters["threshold"]),
            int(event_parameters["min_gap_days"]),
            int(event_parameters["top_n"]),
        )
        overlap_rows.append(
            {
                "method": method,
                "event_count": len(events),
                "baseline_event_coverage_within_7d": matching_fraction(
                    baseline_events["date"], events["date"], 7
                ),
                "candidate_event_match_within_7d": matching_fraction(
                    events["date"], baseline_events["date"], 7
                ),
            }
        )
    return (
        pd.DataFrame(summary_rows),
        pd.concat(annual_rows, ignore_index=True),
        pd.concat(monthly_rows, ignore_index=True),
        pd.DataFrame(overlap_rows),
    )


def abrupt_parameter_sensitivity(
    daily: pd.DataFrame,
    baseline_events: pd.DataFrame,
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    combinations: list[tuple[str, pd.DataFrame]] = []
    for window, threshold, gap_days in product([3, 7, 14], [2.5, 3.0, 3.5], [10, 20, 30]):
        events = abrupt_change_events(daily, window, threshold, gap_days, top_n)
        combination = f"w{window}_z{threshold:g}_g{gap_days}"
        combinations.append((combination, events))
        rows.append(
            {
                "combination": combination,
                "window_days": window,
                "threshold": threshold,
                "min_gap_days": gap_days,
                "event_count": len(events),
                "jun_sep_event_share": float(events["month"].isin([6, 7, 8, 9]).mean()) if len(events) else np.nan,
                "baseline_event_coverage_within_7d": matching_fraction(
                    baseline_events["date"], events["date"], 7
                ),
                "candidate_event_match_within_7d": matching_fraction(
                    events["date"], baseline_events["date"], 7
                ),
            }
        )

    stability_rows = []
    for _, event in baseline_events.iterrows():
        date = pd.Timestamp(event["date"])
        matches = 0
        for _, candidate_events in combinations:
            if any(abs((date - pd.Timestamp(other)).days) <= 7 for other in candidate_events["date"]):
                matches += 1
        stability_rows.append(
            {
                "baseline_event_date": date,
                "main_direction": event["main_direction"],
                "baseline_score": event["abrupt_score"],
                "matched_parameter_combinations": matches,
                "total_parameter_combinations": len(combinations),
                "match_rate_within_7d": matches / len(combinations),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(stability_rows)


def periodicity_robustness(daily_by_method: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    spans = [
        ("full_2016_2021", pd.Timestamp("2016-01-01"), pd.Timestamp("2022-01-01")),
        ("early_2016_2020", pd.Timestamp("2016-01-01"), pd.Timestamp("2021-01-01")),
        ("late_2017_2021", pd.Timestamp("2017-01-01"), pd.Timestamp("2022-01-01")),
    ]
    for method, daily in daily_by_method.items():
        method_spans = spans if method == BASELINE_METHOD else spans[:1]
        for span, start, end in method_spans:
            part = daily[(daily["date"] >= start) & (daily["date"] < end)]
            for column, series_name in [
                ("mean_flow_m3s", "water_flux"),
                ("mean_sediment_flux_kg_s", "sediment_flux"),
            ]:
                rows.append(
                    {
                        "interpolation_method": method,
                        "time_span": span,
                        "series": series_name,
                        "days": len(part),
                        **dominant_period_metrics(part[column]),
                    }
                )
    return pd.DataFrame(rows)


def yearly_seasonality(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in daily.groupby("year"):
        monthly = group.groupby("month", as_index=False).agg(
            water_volume_m3=("water_volume_m3", "sum"),
            sediment_mass_kg=("sediment_mass_kg", "sum"),
        )
        flood = monthly[monthly["month"].isin([6, 7, 8, 9, 10])]
        rows.append(
            {
                "year": int(year),
                "jun_oct_water_share": float(flood["water_volume_m3"].sum() / monthly["water_volume_m3"].sum()),
                "jun_oct_sediment_share": float(
                    flood["sediment_mass_kg"].sum() / monthly["sediment_mass_kg"].sum()
                ),
                "peak_water_month": int(monthly.loc[monthly["water_volume_m3"].idxmax(), "month"]),
                "peak_sediment_month": int(monthly.loc[monthly["sediment_mass_kg"].idxmax(), "month"]),
            }
        )
    return pd.DataFrame(rows)


def dataframe_to_markdown(df: pd.DataFrame, floatfmt: str = ".4g") -> str:
    headers = list(df.columns)
    body: list[list[str]] = []
    for _, row in df.iterrows():
        values = []
        for value in row:
            if isinstance(value, pd.Timestamp):
                values.append(value.strftime("%Y-%m-%d"))
            elif isinstance(value, (float, np.floating)):
                values.append(format(float(value), floatfmt))
            else:
                values.append(str(value))
        body.append(values)
    widths = [
        max(len(str(header)), *(len(row[index]) for row in body)) if body else len(str(header))
        for index, header in enumerate(headers)
    ]
    lines = [
        "| " + " | ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)) + " |",
        "| " + " | ".join("-" * widths[index] for index in range(len(headers))) + " |",
    ]
    lines.extend(
        "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"
        for row in body
    )
    return "\n".join(lines)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_centered_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], label: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (xy[0] - (bbox[2] - bbox[0]) / 2, xy[1] - (bbox[3] - bbox[1]) / 2),
        label,
        font=font,
        fill=fill,
    )


def save_chart(
    path: Path,
    labels: list[str],
    series: list[tuple[str, list[float], tuple[int, int, int]]],
    title: str,
    ylabel: str,
    kind: str,
    width: int = 1200,
    height: int = 720,
) -> None:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(28, bold=True)
    axis_font = get_font(16)
    tick_font = get_font(14)
    legend_font = get_font(16)
    left, right, top, bottom = 115, 45, 82, 105
    plot_width = width - left - right
    plot_height = height - top - bottom
    y_max = max(max(values) for _, values, _ in series) * 1.15
    y_max = y_max if y_max > 0 else 1.0
    draw_centered_text(draw, (width / 2, 36), title, title_font, (31, 41, 55))
    draw.text((left, top - 30), ylabel, font=axis_font, fill=(55, 65, 81))
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_height - value / y_max * plot_height
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((10, y - 8), f"{value:.1f}", font=tick_font, fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_height), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_height, width - right, top + plot_height), fill=(55, 65, 81), width=2)
    step = plot_width / len(labels)
    for index, label in enumerate(labels):
        center = left + (index + 0.5) * step
        draw_centered_text(draw, (center, top + plot_height + 28), label, tick_font, (55, 65, 81))
    if kind == "bar":
        gap = 7
        bar_width = min(34, (step - 22) / len(series) - gap)
        for index in range(len(labels)):
            center = left + (index + 0.5) * step
            start_x = center - (len(series) * bar_width + (len(series) - 1) * gap) / 2
            for series_index, (_, values, color) in enumerate(series):
                value = values[index]
                bar_height = value / y_max * plot_height
                x = start_x + series_index * (bar_width + gap)
                y = top + plot_height - bar_height
                draw.rounded_rectangle((x, y, x + bar_width, top + plot_height), radius=3, fill=color)
    elif kind == "line":
        for _, values, color in series:
            points = []
            for index, value in enumerate(values):
                x = left + (index + 0.5) * step
                y = top + plot_height - value / y_max * plot_height
                points.append((x, y))
            draw.line(points, fill=color, width=4, joint="curve")
            for x, y in points:
                draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
    else:
        raise ValueError(f"Unknown chart kind: {kind}")
    legend_x = left
    legend_y = height - 45
    for name, _, color in series:
        draw.rounded_rectangle((legend_x, legend_y - 12, legend_x + 18, legend_y + 6), radius=3, fill=color)
        draw.text((legend_x + 27, legend_y - 14), name, font=legend_font, fill=(55, 65, 81))
        legend_x += 330
    image.save(path)


def write_seasonal_figures(monthly: pd.DataFrame, figure_dir: Path) -> dict[str, Path]:
    labels = [str(int(month)) for month in monthly["month"]]
    water_share = (monthly["water_share"] * 100).tolist()
    sediment_share = (monthly["sediment_share"] * 100).tolist()
    flow = monthly["mean_flow_m3s"].tolist()
    sediment_flux = monthly["mean_sediment_flux_kg_s"].tolist()
    paths = {
        "share": figure_dir / "monthly-water-sediment-share.png",
        "normalized": figure_dir / "monthly-normalized-flux.png",
        "flow": figure_dir / "monthly-mean-flow.png",
        "sediment": figure_dir / "monthly-mean-sediment-flux.png",
    }
    save_chart(
        paths["share"],
        labels,
        [("water volume share", water_share, (37, 99, 235)), ("sediment mass share", sediment_share, (220, 38, 38))],
        "Monthly Water and Sediment Contribution",
        "share (%)",
        "bar",
    )
    save_chart(
        paths["normalized"],
        labels,
        [
            ("mean flow index", (monthly["mean_flow_m3s"] / monthly["mean_flow_m3s"].max() * 100).tolist(), (37, 99, 235)),
            ("mean sediment-flux index", (monthly["mean_sediment_flux_kg_s"] / monthly["mean_sediment_flux_kg_s"].max() * 100).tolist(), (220, 38, 38)),
        ],
        "Monthly Normalized Water-Sediment Pattern",
        "index (each series max = 100)",
        "line",
    )
    save_chart(paths["flow"], labels, [("mean flow", flow, (37, 99, 235))], "Monthly Mean Flow", "flow (m^3/s)", "bar")
    save_chart(
        paths["sediment"],
        labels,
        [("mean sediment flux", sediment_flux, (220, 38, 38))],
        "Monthly Mean Sediment Flux",
        "sediment flux (kg/s)",
        "bar",
    )
    return paths


def write_report(
    path: Path,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    concentration: pd.DataFrame,
    events: pd.DataFrame,
    periods: pd.DataFrame,
    acf: pd.DataFrame,
    interpolation_summary: pd.DataFrame,
    abrupt_sensitivity: pd.DataFrame,
    event_stability: pd.DataFrame,
    periodicity_checks: pd.DataFrame,
    yearly_checks: pd.DataFrame,
    quality: pd.DataFrame,
) -> None:
    filled_row = quality[quality["metric"] == "q1_model_filled_sediment_share"]
    filled_share = float(filled_row.iloc[0]["value"]) if not filled_row.empty else np.nan
    parameter_coverage = float(abrupt_sensitivity["baseline_event_coverage_within_7d"].median())
    periodicity_rate = float(periodicity_checks["dominant_is_annual_scale"].mean())
    max_sediment_difference = float(
        interpolation_summary["sediment_total_relative_difference"].abs().max()
    )
    lines = [
        "# 问题二 canonical run 分析摘要",
        "",
        "本运行以问题一清洗序列为显式上游输入。基准口径是在逐小时时间轴上分别线性插值流量、含沙量和已计算的沙通量，再聚合为日均量；以下判断只描述该处理口径下的数据特征，不作水库调度或调水调沙等因果归因。",
        "",
        f"上游时刻中模型补全含沙量占比为 {filled_share:.2%}。因此，沙通量及其突变结果同时继承问题一模型误差，不能等同于全部实测结论。",
        "",
        "## 年际结果",
        "",
        dataframe_to_markdown(annual, ".5g"),
        "",
        "2018—2021 年的基准口径年度水量和排沙量高于 2016—2017 年；这里的差异是描述性结果，未进行独立的结构突变显著性检验。",
        "",
        "## 季节性结果",
        "",
        dataframe_to_markdown(monthly, ".5g"),
        "",
        dataframe_to_markdown(concentration, ".5g"),
        "",
        "![月份水量与排沙量占比](../../figures/monthly-water-sediment-share.png)",
        "",
        "![月份归一化水沙过程](../../figures/monthly-normalized-flux.png)",
        "",
        "![月份平均流量](../../figures/monthly-mean-flow.png)",
        "",
        "![月份平均沙通量](../../figures/monthly-mean-sediment-flux.png)",
        "",
        "绝对流量和绝对沙通量分别绘图，避免在同一纵轴混用 `m^3/s` 与 `kg/s`。逐年汛期占比和峰值月份见 `validation/seasonality_by_year.csv`；总样本月度集中不能自动推出每一年完全相同。",
        "",
        "## 突变候选",
        "",
        "基准参数为前后各 7 日窗口、得分阈值 3.0、事件最小间隔 20 日、最多 15 个事件。阈值先筛选候选，再按得分去除相邻事件。",
        "",
        dataframe_to_markdown(events, ".5g"),
        "",
        f"27 组窗口/阈值/间隔组合对基准事件的 7 日邻域覆盖率中位数为 {parameter_coverage:.1%}。这说明事件日期会随参数变化；正文应优先引用 `abrupt_event_stability.csv` 中匹配率较高的事件，并将其称为算法识别的候选突变，而非已知原因事件。",
        "",
        "## 周期性结果",
        "",
        dataframe_to_markdown(periods.groupby("series").head(5).reset_index(drop=True), ".5g"),
        "",
        dataframe_to_markdown(acf[acf["lag_days"].isin([30, 90, 180, 365])], ".5g"),
        "",
        f"不同插值口径及前后五年子区间的频谱检查中，主峰落在 300—450 日年尺度带的比例为 {periodicity_rate:.1%}。由于完整样本只有 6 年，结论应表述为“存在较强年尺度周期证据”，不宜表述为已证明长期稳定周期；次级频谱峰也不作确定性物理解释。",
        "",
        "## 稳健性边界",
        "",
        dataframe_to_markdown(interpolation_summary, ".5g"),
        "",
        f"三个插值口径相对基准的六年总排沙量最大绝对差异为 {max_sediment_difference:.2%}。插值稳健性只检验本题从不等间隔序列到小时/日尺度的处理选择，不包含问题一含沙量模型的不确定性传播。",
        "",
        "逐年季节性：",
        "",
        dataframe_to_markdown(yearly_checks, ".5g"),
        "",
        "## 可用于后续写作的保守结论",
        "",
        "1. 在基准插值口径下，六年水量和排沙量具有明显的月份集中现象，6—10 月占比较高。",
        "2. 7 日窗口算法在汛期附近识别出若干高分突变候选，但日期和数量受窗口、阈值、事件间隔影响。",
        "3. 完整序列与两段五年子样本均应结合 `periodicity_robustness.csv` 解读；六年数据支持年尺度成分，不足以证明长期稳定性。",
        "4. 沙通量结论依赖问题一大量模型补全值，应与输入覆盖率和插值敏感性结果同时报告。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    input_path = args.input.resolve()
    paths = prepare_run_dir(args.run_dir)
    source = load_question1_series(input_path)
    daily_by_method = {method: build_daily_series(source, method) for method in INTERPOLATION_METHODS}
    for daily in daily_by_method.values():
        validate_daily_series(daily)
    daily = daily_by_method[BASELINE_METHOD]

    event_parameters = {
        "window": args.event_window,
        "threshold": args.event_threshold,
        "min_gap_days": args.event_gap_days,
        "top_n": args.event_top_n,
    }
    annual = annual_summary(daily)
    monthly = seasonal_summary(daily)
    concentration = high_flux_concentration(daily)
    events = abrupt_change_events(daily, **event_parameters)
    periods = pd.concat(
        [
            periodogram(daily["mean_flow_m3s"], "water_flux"),
            periodogram(daily["mean_sediment_flux_kg_s"], "sediment_flux"),
        ],
        ignore_index=True,
    )
    acf = autocorrelation_lags(daily)
    quality = input_quality_summary(source)
    interpolation_summary, interpolation_annual, interpolation_monthly, interpolation_events = (
        interpolation_sensitivity(daily_by_method, events, event_parameters)
    )
    abrupt_sensitivity, event_stability = abrupt_parameter_sensitivity(daily, events, args.event_top_n)
    periodicity_checks = periodicity_robustness(daily_by_method)
    yearly_checks = yearly_seasonality(daily)

    write_csv(daily, paths["data"] / "daily_flux_series.csv")
    write_csv(annual, paths["tables"] / "annual_flux_pattern.csv")
    write_csv(monthly, paths["tables"] / "monthly_flux_summary.csv")
    write_csv(concentration, paths["tables"] / "flood_season_concentration.csv")
    write_csv(events, paths["tables"] / "abrupt_change_events.csv")
    write_csv(periods, paths["tables"] / "periodicity_summary.csv")
    write_csv(acf, paths["tables"] / "autocorrelation_lags.csv")
    write_csv(quality, paths["validation"] / "input_quality_summary.csv")
    write_csv(interpolation_summary, paths["validation"] / "interpolation_sensitivity_summary.csv")
    write_csv(interpolation_annual, paths["validation"] / "interpolation_sensitivity_annual.csv")
    write_csv(interpolation_monthly, paths["validation"] / "interpolation_sensitivity_monthly.csv")
    write_csv(interpolation_events, paths["validation"] / "interpolation_event_overlap.csv")
    write_csv(abrupt_sensitivity, paths["validation"] / "abrupt_parameter_sensitivity.csv")
    write_csv(event_stability, paths["validation"] / "abrupt_event_stability.csv")
    write_csv(periodicity_checks, paths["validation"] / "periodicity_robustness.csv")
    write_csv(yearly_checks, paths["validation"] / "seasonality_by_year.csv")
    write_seasonal_figures(monthly, paths["figures"])
    write_report(
        paths["reports"] / "question2-analysis.md",
        annual,
        monthly,
        concentration,
        events,
        periods,
        acf,
        interpolation_summary,
        abrupt_sensitivity,
        event_stability,
        periodicity_checks,
        yearly_checks,
        quality,
    )

    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "script": str(SCRIPT_PATH),
        "script_sha256": sha256_file(SCRIPT_PATH),
        "input": str(input_path),
        "input_sha256": sha256_file(input_path),
        "input_rows": len(source),
        "baseline_interpolation_method": BASELINE_METHOD,
        "interpolation_sensitivity_methods": list(INTERPOLATION_METHODS),
        "event_parameters": event_parameters,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pillow": Image.__version__ if hasattr(Image, "__version__") else "unknown",
        "daily_rows": len(daily),
        "baseline_event_count": len(events),
    }
    (paths["validation"] / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log_lines = [
        f"completed_at={manifest['generated_at']}",
        f"input={input_path}",
        f"input_sha256={manifest['input_sha256']}",
        f"script_sha256={manifest['script_sha256']}",
        f"daily_rows={len(daily)}",
        f"baseline_event_count={len(events)}",
        f"outputs={paths['run']}",
    ]
    (paths["logs"] / "execution.log").write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(f"Daily rows: {len(daily)}")
    print(f"Baseline abrupt events: {len(events)}")
    print("Interpolation sensitivity:")
    print(interpolation_summary.to_string(index=False))
    print("Periodicity robustness:")
    print(periodicity_checks.to_string(index=False))


if __name__ == "__main__":
    main()
