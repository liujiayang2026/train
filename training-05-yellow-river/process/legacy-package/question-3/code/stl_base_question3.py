from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[2]
Q2_DIR = PROJECT_DIR / "question-2"
DATA_DIR = PROJECT_DIR / "question-3" / "data" / "processed"
RESULTS_DIR = PROJECT_DIR / "question-3" / "results"
DOCS_DIR = PROJECT_DIR / "question-3" / "docs"
FIGURES_DIR = PROJECT_DIR / "question-3" / "figures"
QA_DIR = PROJECT_DIR / "question-3" / "qa"
MODELS_DIR = PROJECT_DIR / "question-3" / "models"
SECONDS_PER_DAY = 24 * 3600


@dataclass
class RidgeModel:
    target: str
    feature_names: list[str]
    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    alpha: float


def load_daily_flux() -> pd.DataFrame:
    candidates = [
        Q2_DIR / "data" / "processed" / "daily_flux_series.csv",
        Q2_DIR / "results" / "daily_flux_series.csv",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        expected = "\n".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"Missing question 2 daily series. Tried:\n{expected}")
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    needed = ["date", "mean_flow_m3s", "mean_sediment_flux_kg_s"]
    missing = [col for col in needed if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def date_features(date: pd.Timestamp) -> list[float]:
    year_start = pd.Timestamp(datetime(date.year, 1, 1))
    year_end = pd.Timestamp(datetime(date.year + 1, 1, 1))
    d = (date - year_start).total_seconds() / (year_end - year_start).total_seconds()
    trend = (date - pd.Timestamp("2016-01-01")).days / 365.25
    angle = 2 * np.pi * d
    month = date.month
    return [
        trend,
        trend**2,
        np.sin(angle),
        np.cos(angle),
        np.sin(2 * angle),
        np.cos(2 * angle),
        1.0 if 6 <= month <= 10 else 0.0,
        1.0 if 7 <= month <= 9 else 0.0,
        1.0 if month == 7 else 0.0,
    ]


def feature_names() -> list[str]:
    return [
        "trend_year",
        "trend_year_sq",
        "sin_annual",
        "cos_annual",
        "sin_semiannual",
        "cos_semiannual",
        "is_flood_jun_oct",
        "is_peak_jul_sep",
        "is_july",
        "lag_1",
        "lag_3",
        "lag_7",
        "roll7_mean",
        "roll7_std",
    ]


def make_supervised(df: pd.DataFrame, target_col: str) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, list[str]]:
    work = df[["date", target_col]].copy().sort_values("date").reset_index(drop=True)
    y_series = np.log1p(work[target_col].to_numpy(dtype=float))
    rows = []
    y = []
    meta = []
    for idx in range(7, len(work)):
        date = pd.Timestamp(work.loc[idx, "date"])
        history = y_series[:idx]
        lag_values = [
            history[-1],
            history[-3],
            history[-7],
            float(np.mean(history[-7:])),
            float(np.std(history[-7:])),
        ]
        rows.append(date_features(date) + lag_values)
        y.append(y_series[idx])
        meta.append({"date": date, "year": date.year})
    return np.asarray(rows, dtype=float), np.asarray(y, dtype=float), pd.DataFrame(meta), feature_names()


def fit_ridge(x: np.ndarray, y: np.ndarray, names: list[str], target: str, alpha: float = 3.0) -> RidgeModel:
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    design = np.column_stack([np.ones(len(z)), z])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return RidgeModel(target=target, feature_names=names, mean=mean, scale=scale, coef=coef, alpha=alpha)


def predict_model(model: RidgeModel, x: np.ndarray) -> np.ndarray:
    z = (x - model.mean) / model.scale
    design = np.column_stack([np.ones(len(z)), z])
    return design @ model.coef


def recursive_forecast(
    model: RidgeModel,
    history_dates: list[pd.Timestamp],
    history_y: list[float],
    future_dates: pd.DatetimeIndex,
) -> np.ndarray:
    predictions = []
    values = list(history_y)
    for date in future_dates:
        lag_values = [
            values[-1],
            values[-3],
            values[-7],
            float(np.mean(values[-7:])),
            float(np.std(values[-7:])),
        ]
        x = np.asarray([date_features(pd.Timestamp(date)) + lag_values], dtype=float)
        pred = float(predict_model(model, x)[0])
        predictions.append(pred)
        values.append(pred)
        history_dates.append(pd.Timestamp(date))
    return np.asarray(predictions)


def validate_recursive(df: pd.DataFrame, target_col: str, alpha: float = 3.0) -> pd.DataFrame:
    records = []
    for year in [2018, 2019, 2020, 2021]:
        train = df[df["date"].dt.year < year].copy()
        test = df[df["date"].dt.year == year].copy()
        if len(train) < 370 or test.empty:
            continue
        x_train, y_train, _, names = make_supervised(train, target_col)
        model = fit_ridge(x_train, y_train, names, target_col, alpha=alpha)
        history_y = np.log1p(train[target_col].to_numpy(dtype=float)).tolist()
        future_dates = pd.DatetimeIndex(test["date"])
        pred_log = recursive_forecast(model, list(train["date"]), history_y, future_dates)
        true_log = np.log1p(test[target_col].to_numpy(dtype=float))
        pred = np.expm1(pred_log)
        true = test[target_col].to_numpy(dtype=float)
        records.append(
            {
                "target": target_col,
                "heldout_year": year,
                "rmse_log": float(np.sqrt(np.mean((true_log - pred_log) ** 2))),
                "mae_log": float(np.mean(np.abs(true_log - pred_log))),
                "r2_log": float(1 - np.sum((true_log - pred_log) ** 2) / np.sum((true_log - true_log.mean()) ** 2)),
                "rmse_original": float(np.sqrt(np.mean((true - pred) ** 2))),
                "mae_original": float(np.mean(np.abs(true - pred))),
            }
        )
    summary = (
        pd.DataFrame(records)
        .groupby("target", as_index=False)
        .agg(
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            rmse_original=("rmse_original", "mean"),
            mae_original=("mae_original", "mean"),
        )
    )
    summary.insert(1, "heldout_year", "mean")
    return pd.concat([pd.DataFrame(records), summary], ignore_index=True)


def train_and_forecast(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    future_dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    forecasts = pd.DataFrame({"date": future_dates})
    model_rows = []
    for target_col, output_col in [
        ("mean_flow_m3s", "pred_mean_flow_m3s"),
        ("mean_sediment_flux_kg_s", "pred_mean_sediment_flux_kg_s"),
    ]:
        x, y, _, names = make_supervised(df, target_col)
        model = fit_ridge(x, y, names, target_col)
        history_y = np.log1p(df[target_col].to_numpy(dtype=float)).tolist()
        pred_log = recursive_forecast(model, list(df["date"]), history_y, future_dates)
        forecasts[output_col] = np.expm1(pred_log).clip(min=0)
        for name, coef, scale in zip(model.feature_names, model.coef[1:], model.scale):
            model_rows.append(
                {
                    "target": target_col,
                    "feature": name,
                    "standardized_coef": float(coef),
                    "raw_scale_coef_approx": float(coef / scale),
                }
            )
    forecasts["pred_water_volume_m3"] = forecasts["pred_mean_flow_m3s"] * SECONDS_PER_DAY
    forecasts["pred_sediment_mass_kg"] = forecasts["pred_mean_sediment_flux_kg_s"] * SECONDS_PER_DAY
    forecasts["pred_water_volume_1e8_m3"] = forecasts["pred_water_volume_m3"] / 1e8
    forecasts["pred_sediment_mass_1e4_t"] = forecasts["pred_sediment_mass_kg"] / 1e7
    forecasts["year"] = forecasts["date"].dt.year
    forecasts["month"] = forecasts["date"].dt.month
    return forecasts, pd.DataFrame(model_rows)


def aggregate_forecast(forecasts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = (
        forecasts.groupby(["year", "month"], as_index=False)
        .agg(
            pred_mean_flow_m3s=("pred_mean_flow_m3s", "mean"),
            pred_mean_sediment_flux_kg_s=("pred_mean_sediment_flux_kg_s", "mean"),
            pred_water_volume_1e8_m3=("pred_water_volume_1e8_m3", "sum"),
            pred_sediment_mass_1e4_t=("pred_sediment_mass_1e4_t", "sum"),
        )
        .sort_values(["year", "month"])
    )
    annual = (
        forecasts.groupby("year", as_index=False)
        .agg(
            pred_water_volume_1e8_m3=("pred_water_volume_1e8_m3", "sum"),
            pred_sediment_mass_1e4_t=("pred_sediment_mass_1e4_t", "sum"),
            pred_mean_flow_m3s=("pred_mean_flow_m3s", "mean"),
            pred_mean_sediment_flux_kg_s=("pred_mean_sediment_flux_kg_s", "mean"),
            max_pred_flow_m3s=("pred_mean_flow_m3s", "max"),
            max_pred_sediment_flux_kg_s=("pred_mean_sediment_flux_kg_s", "max"),
        )
        .sort_values("year")
    )
    return monthly, annual


def circular_doy_distance(a: np.ndarray, b: int, period: int = 366) -> np.ndarray:
    diff = np.abs(a - b)
    return np.minimum(diff, period - diff)


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values)
    values_sorted = values[order]
    weights_sorted = weights[order]
    cumulative = np.cumsum(weights_sorted)
    if cumulative[-1] <= 0:
        return float(np.mean(values))
    cutoff = quantile * cumulative[-1]
    return float(values_sorted[np.searchsorted(cumulative, cutoff, side="left")])


def annual_log_slope(train: pd.DataFrame, target_col: str) -> float:
    annual = (
        train.groupby(train["date"].dt.year)[target_col]
        .mean()
        .tail(4)
        .reset_index(name="value")
    )
    if len(annual) < 2:
        return 0.0
    x = annual["date"].to_numpy(dtype=float)
    y = np.log1p(annual["value"].to_numpy(dtype=float))
    slope = float(np.polyfit(x - x.min(), y, deg=1)[0])
    clip = 0.05 if target_col == "mean_flow_m3s" else 0.08
    return float(np.clip(slope, -clip, clip))


def recency_year_weights(years: np.ndarray, max_year: int) -> np.ndarray:
    distance = max_year - years
    weights = np.exp(-0.42 * distance)
    weights[years < 2018] *= 0.45
    return weights


def seasonal_template_forecast(
    train: pd.DataFrame,
    future_dates: pd.DatetimeIndex,
    target_col: str,
    scenario: str,
    window_days: int = 15,
) -> np.ndarray:
    history = train[["date", target_col]].copy().sort_values("date")
    history["doy"] = history["date"].dt.dayofyear
    history["year"] = history["date"].dt.year
    years = history["year"].to_numpy(dtype=int)
    values = history[target_col].to_numpy(dtype=float)
    doys = history["doy"].to_numpy(dtype=int)
    max_year = int(history["year"].max())
    slope = annual_log_slope(history, target_col)
    preds = []
    for date in future_dates:
        date = pd.Timestamp(date)
        dist = circular_doy_distance(doys, int(date.dayofyear))
        mask = dist <= window_days
        if not mask.any():
            mask = dist <= 31
        local_values = values[mask]
        local_years = years[mask]
        local_dist = dist[mask]
        kernel = np.exp(-0.5 * (local_dist / 7.5) ** 2)
        recency = recency_year_weights(local_years, max_year)
        weights = kernel * recency
        if scenario == "low":
            base = weighted_quantile(local_values, weights, 0.30)
            scenario_factor = 0.93
            trend_multiplier = 0.6
        elif scenario == "high":
            base = weighted_quantile(local_values, weights, 0.75)
            scenario_factor = 1.08
            trend_multiplier = 1.2
        else:
            base = float(np.average(local_values, weights=weights))
            scenario_factor = 1.0
            trend_multiplier = 1.0
        year_offset = date.year - max_year
        trend_factor = float(np.exp(slope * year_offset * trend_multiplier))
        preds.append(max(0.0, base * trend_factor * scenario_factor))
    return np.asarray(preds, dtype=float)


def template_validate(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    records = []
    for year in [2018, 2019, 2020, 2021]:
        train = df[df["date"].dt.year < year].copy()
        test = df[df["date"].dt.year == year].copy()
        if len(train) < 365 or test.empty:
            continue
        pred = seasonal_template_forecast(train, pd.DatetimeIndex(test["date"]), target_col, "normal")
        true = test[target_col].to_numpy(dtype=float)
        true_log = np.log1p(true)
        pred_log = np.log1p(pred)
        records.append(
            {
                "target": target_col,
                "heldout_year": year,
                "rmse_log": float(np.sqrt(np.mean((true_log - pred_log) ** 2))),
                "mae_log": float(np.mean(np.abs(true_log - pred_log))),
                "r2_log": float(1 - np.sum((true_log - pred_log) ** 2) / np.sum((true_log - true_log.mean()) ** 2)),
                "rmse_original": float(np.sqrt(np.mean((true - pred) ** 2))),
                "mae_original": float(np.mean(np.abs(true - pred))),
            }
        )
    detail = pd.DataFrame(records)
    summary = (
        detail.groupby("target", as_index=False)
        .agg(
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            rmse_original=("rmse_original", "mean"),
            mae_original=("mae_original", "mean"),
        )
    )
    summary.insert(1, "heldout_year", "mean")
    return pd.concat([detail, summary], ignore_index=True)


def template_train_and_forecast(df: pd.DataFrame) -> pd.DataFrame:
    future_dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    forecasts = pd.DataFrame({"date": future_dates})
    for scenario in ["low", "normal", "high"]:
        flow = seasonal_template_forecast(df, future_dates, "mean_flow_m3s", scenario)
        sediment_flux = seasonal_template_forecast(df, future_dates, "mean_sediment_flux_kg_s", scenario)
        forecasts[f"{scenario}_pred_mean_flow_m3s"] = flow
        forecasts[f"{scenario}_pred_mean_sediment_flux_kg_s"] = sediment_flux
        forecasts[f"{scenario}_pred_water_volume_m3"] = flow * SECONDS_PER_DAY
        forecasts[f"{scenario}_pred_sediment_mass_kg"] = sediment_flux * SECONDS_PER_DAY
        forecasts[f"{scenario}_pred_water_volume_1e8_m3"] = forecasts[f"{scenario}_pred_water_volume_m3"] / 1e8
        forecasts[f"{scenario}_pred_sediment_mass_1e4_t"] = forecasts[f"{scenario}_pred_sediment_mass_kg"] / 1e7
    forecasts["pred_mean_flow_m3s"] = forecasts["normal_pred_mean_flow_m3s"]
    forecasts["pred_mean_sediment_flux_kg_s"] = forecasts["normal_pred_mean_sediment_flux_kg_s"]
    forecasts["pred_water_volume_m3"] = forecasts["normal_pred_water_volume_m3"]
    forecasts["pred_sediment_mass_kg"] = forecasts["normal_pred_sediment_mass_kg"]
    forecasts["pred_water_volume_1e8_m3"] = forecasts["normal_pred_water_volume_1e8_m3"]
    forecasts["pred_sediment_mass_1e4_t"] = forecasts["normal_pred_sediment_mass_1e4_t"]
    forecasts["year"] = forecasts["date"].dt.year
    forecasts["month"] = forecasts["date"].dt.month
    return forecasts


def aggregate_scenarios(forecasts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows = []
    annual_rows = []
    for scenario in ["low", "normal", "high"]:
        monthly = (
            forecasts.groupby(["year", "month"], as_index=False)
            .agg(
                pred_mean_flow_m3s=(f"{scenario}_pred_mean_flow_m3s", "mean"),
                pred_mean_sediment_flux_kg_s=(f"{scenario}_pred_mean_sediment_flux_kg_s", "mean"),
                pred_water_volume_1e8_m3=(f"{scenario}_pred_water_volume_1e8_m3", "sum"),
                pred_sediment_mass_1e4_t=(f"{scenario}_pred_sediment_mass_1e4_t", "sum"),
            )
            .sort_values(["year", "month"])
        )
        monthly.insert(0, "scenario", scenario)
        monthly_rows.append(monthly)
        annual = (
            forecasts.groupby("year", as_index=False)
            .agg(
                pred_water_volume_1e8_m3=(f"{scenario}_pred_water_volume_1e8_m3", "sum"),
                pred_sediment_mass_1e4_t=(f"{scenario}_pred_sediment_mass_1e4_t", "sum"),
                pred_mean_flow_m3s=(f"{scenario}_pred_mean_flow_m3s", "mean"),
                pred_mean_sediment_flux_kg_s=(f"{scenario}_pred_mean_sediment_flux_kg_s", "mean"),
                max_pred_flow_m3s=(f"{scenario}_pred_mean_flow_m3s", "max"),
                max_pred_sediment_flux_kg_s=(f"{scenario}_pred_mean_sediment_flux_kg_s", "max"),
            )
            .sort_values("year")
        )
        annual.insert(0, "scenario", scenario)
        annual_rows.append(annual)
    return pd.concat(monthly_rows, ignore_index=True), pd.concat(annual_rows, ignore_index=True)


def fractional_year(dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    dt_index = pd.DatetimeIndex(dates)
    values = []
    for date in dt_index:
        start = pd.Timestamp(datetime(date.year, 1, 1))
        end = pd.Timestamp(datetime(date.year + 1, 1, 1))
        values.append(date.year + (date - start).total_seconds() / (end - start).total_seconds())
    return np.asarray(values, dtype=float)


def fit_stl_trend(history: pd.DataFrame, target_col: str) -> dict[str, float]:
    work = history[["date", target_col]].copy().sort_values("date")
    work["year"] = work["date"].dt.year
    annual = (
        work.groupby("year", as_index=False)
        .agg(mean_log=(target_col, lambda s: float(np.log1p(s).mean())))
        .tail(4)
    )
    if len(annual) < 2:
        slope = 0.0
        anchor_level = float(np.log1p(work[target_col]).mean())
    else:
        x = annual["year"].to_numpy(dtype=float) + 0.5
        y = annual["mean_log"].to_numpy(dtype=float)
        slope = float(np.polyfit(x - x.min(), y, deg=1)[0])
        clip = 0.05 if target_col == "mean_flow_m3s" else 0.08
        slope = float(np.clip(slope, -clip, clip))
        anchor_level = float(y[-1])
    return {"slope": slope, "anchor_level": anchor_level, "anchor_x": float(work["date"].dt.year.max()) + 0.5}


def stl_trend_values(dates: pd.Series | pd.DatetimeIndex, params: dict[str, float], multiplier: float = 1.0) -> np.ndarray:
    x = fractional_year(dates)
    return params["anchor_level"] + params["slope"] * multiplier * (x - params["anchor_x"])


def stl_combination_forecast(
    train: pd.DataFrame,
    future_dates: pd.DatetimeIndex,
    target_col: str,
    scenario: str,
    window_days: int = 15,
) -> np.ndarray:
    history = train[["date", target_col]].copy().sort_values("date")
    history["doy"] = history["date"].dt.dayofyear
    history["year"] = history["date"].dt.year
    y_log = np.log1p(history[target_col].to_numpy(dtype=float))
    params = fit_stl_trend(history, target_col)
    trend_hist = stl_trend_values(pd.DatetimeIndex(history["date"]), params)
    seasonal_resid = y_log - trend_hist
    doys = history["doy"].to_numpy(dtype=int)
    years = history["year"].to_numpy(dtype=int)
    max_year = int(history["year"].max())
    preds = []
    for date in future_dates:
        date = pd.Timestamp(date)
        dist = circular_doy_distance(doys, int(date.dayofyear))
        mask = dist <= window_days
        if not mask.any():
            mask = dist <= 31
        local_resid = seasonal_resid[mask]
        local_years = years[mask]
        local_dist = dist[mask]
        kernel = np.exp(-0.5 * (local_dist / 7.5) ** 2)
        recency = recency_year_weights(local_years, max_year)
        weights = kernel * recency
        if scenario == "low":
            seasonal = weighted_quantile(local_resid, weights, 0.30)
            trend_multiplier = 0.65
            scenario_shift = -0.04
        elif scenario == "high":
            seasonal = weighted_quantile(local_resid, weights, 0.75)
            trend_multiplier = 1.20
            scenario_shift = 0.05
        else:
            seasonal = float(np.average(local_resid, weights=weights))
            trend_multiplier = 1.0
            scenario_shift = 0.0
        pred_log = stl_trend_values(pd.DatetimeIndex([date]), params, trend_multiplier)[0] + seasonal + scenario_shift
        preds.append(max(0.0, float(np.expm1(pred_log))))
    return np.asarray(preds, dtype=float)


def stl_validate(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    records = []
    for year in [2018, 2019, 2020, 2021]:
        train = df[df["date"].dt.year < year].copy()
        test = df[df["date"].dt.year == year].copy()
        if len(train) < 365 or test.empty:
            continue
        pred = stl_combination_forecast(train, pd.DatetimeIndex(test["date"]), target_col, "normal")
        true = test[target_col].to_numpy(dtype=float)
        true_log = np.log1p(true)
        pred_log = np.log1p(pred)
        records.append(
            {
                "target": target_col,
                "heldout_year": year,
                "rmse_log": float(np.sqrt(np.mean((true_log - pred_log) ** 2))),
                "mae_log": float(np.mean(np.abs(true_log - pred_log))),
                "r2_log": float(1 - np.sum((true_log - pred_log) ** 2) / np.sum((true_log - true_log.mean()) ** 2)),
                "rmse_original": float(np.sqrt(np.mean((true - pred) ** 2))),
                "mae_original": float(np.mean(np.abs(true - pred))),
            }
        )
    detail = pd.DataFrame(records)
    summary = (
        detail.groupby("target", as_index=False)
        .agg(
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            rmse_original=("rmse_original", "mean"),
            mae_original=("mae_original", "mean"),
        )
    )
    summary.insert(1, "heldout_year", "mean")
    return pd.concat([detail, summary], ignore_index=True)


def stl_train_and_forecast(df: pd.DataFrame) -> pd.DataFrame:
    future_dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    forecasts = pd.DataFrame({"date": future_dates})
    for scenario in ["low", "normal", "high"]:
        flow = stl_combination_forecast(df, future_dates, "mean_flow_m3s", scenario)
        sediment_flux = stl_combination_forecast(df, future_dates, "mean_sediment_flux_kg_s", scenario)
        forecasts[f"{scenario}_pred_mean_flow_m3s"] = flow
        forecasts[f"{scenario}_pred_mean_sediment_flux_kg_s"] = sediment_flux
        forecasts[f"{scenario}_pred_water_volume_m3"] = flow * SECONDS_PER_DAY
        forecasts[f"{scenario}_pred_sediment_mass_kg"] = sediment_flux * SECONDS_PER_DAY
        forecasts[f"{scenario}_pred_water_volume_1e8_m3"] = forecasts[f"{scenario}_pred_water_volume_m3"] / 1e8
        forecasts[f"{scenario}_pred_sediment_mass_1e4_t"] = forecasts[f"{scenario}_pred_sediment_mass_kg"] / 1e7
    forecasts["pred_mean_flow_m3s"] = forecasts["normal_pred_mean_flow_m3s"]
    forecasts["pred_mean_sediment_flux_kg_s"] = forecasts["normal_pred_mean_sediment_flux_kg_s"]
    forecasts["pred_water_volume_m3"] = forecasts["normal_pred_water_volume_m3"]
    forecasts["pred_sediment_mass_kg"] = forecasts["normal_pred_sediment_mass_kg"]
    forecasts["pred_water_volume_1e8_m3"] = forecasts["normal_pred_water_volume_1e8_m3"]
    forecasts["pred_sediment_mass_1e4_t"] = forecasts["normal_pred_sediment_mass_1e4_t"]
    forecasts["year"] = forecasts["date"].dt.year
    forecasts["month"] = forecasts["date"].dt.month
    return forecasts


def historical_abrupt_month_risk() -> dict[int, float]:
    path = Q2_DIR / "qa" / "abrupt_change_events.csv"
    if not path.exists():
        return {month: 0.0 for month in range(1, 13)}
    events = pd.read_csv(path, parse_dates=["date"])
    counts = events["date"].dt.month.value_counts().to_dict()
    max_count = max(counts.values()) if counts else 1
    return {month: counts.get(month, 0) / max_count for month in range(1, 13)}


def minmax(values: pd.Series) -> pd.Series:
    lo = values.min()
    hi = values.max()
    if hi == lo:
        return pd.Series(np.zeros(len(values)), index=values.index)
    return (values - lo) / (hi - lo)


def build_sampling_plan(forecasts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = forecasts.copy()
    work["log_sediment_flux"] = np.log1p(work["pred_mean_sediment_flux_kg_s"])
    if "high_pred_mean_sediment_flux_kg_s" in work.columns:
        work["high_log_sediment_flux"] = np.log1p(work["high_pred_mean_sediment_flux_kg_s"])
    else:
        work["high_log_sediment_flux"] = work["log_sediment_flux"]
    work["change_strength"] = work["log_sediment_flux"].diff().abs().fillna(0)
    month_risk = historical_abrupt_month_risk()
    work["historical_abrupt_month_risk"] = work["month"].map(month_risk).astype(float)
    work["is_flood"] = work["month"].between(6, 10).astype(float)
    work["is_peak"] = work["month"].between(7, 9).astype(float)
    work["is_july"] = (work["month"] == 7).astype(float)
    work["risk_score"] = (
        0.35 * minmax(work["log_sediment_flux"])
        + 0.10 * minmax(work["high_log_sediment_flux"])
        + 0.25 * minmax(work["change_strength"])
        + 0.15 * work["is_peak"]
        + 0.10 * work["is_flood"]
        + 0.05 * work["historical_abrupt_month_risk"]
    )

    selected_dates: set[pd.Timestamp] = set()
    for _, row in work.iterrows():
        date = pd.Timestamp(row["date"])
        month = date.month
        if month <= 3:
            interval = 10
        elif month <= 5:
            interval = 5
        elif month <= 10:
            interval = 2
        else:
            interval = 7
        if (date.day - 1) % interval == 0:
            selected_dates.add(date)

    for year, group in work.groupby(work["date"].dt.year):
        top = group.sort_values("risk_score", ascending=False).head(20)
        for date in pd.DatetimeIndex(top["date"]):
            selected_dates.add(pd.Timestamp(date))
        peak_centers = group.sort_values("risk_score", ascending=False).head(6)["date"]
        for center in pd.DatetimeIndex(peak_centers):
            for offset in [-1, 0, 1]:
                candidate = pd.Timestamp(center) + pd.Timedelta(days=offset)
                if candidate.year == year:
                    selected_dates.add(candidate)

    plan = work[work["date"].isin(selected_dates)].copy().sort_values("date")
    plan["sampling_level"] = np.where(
        plan["risk_score"] >= work["risk_score"].quantile(0.90),
        "high",
        np.where(plan["month"].between(6, 10), "flood_regular", "base_regular"),
    )
    plan = plan[
        [
            "date",
            "year",
            "month",
            "sampling_level",
            "risk_score",
            "pred_mean_flow_m3s",
            "pred_mean_sediment_flux_kg_s",
            "change_strength",
        ]
    ]
    monthly_counts = (
        plan.groupby(["year", "month"], as_index=False)
        .agg(samples=("date", "size"), high_risk_samples=("sampling_level", lambda s: int((s == "high").sum())))
        .sort_values(["year", "month"])
    )
    return plan, monthly_counts


def get_font(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_centered(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (bbox[2] - bbox[0]) / 2, xy[1] - (bbox[3] - bbox[1]) / 2), text, font=font, fill=fill)


def save_forecast_figure(monthly: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 720
    left, right, top, bottom = 105, 45, 88, 110
    plot_w, plot_h = width - left - right, height - top - bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(28, bold=True)
    tick_font = get_font(14)
    axis_font = get_font(16)
    draw_centered(draw, (width / 2, 38), "Forecast Monthly Water and Sediment Flux", title_font, (31, 41, 55))
    draw.text((left, top - 32), "index (max=100)", font=axis_font, fill=(55, 65, 81))
    x_labels = [f"{int(y)}-{int(m):02d}" for y, m in zip(monthly["year"], monthly["month"])]
    water = (monthly["pred_water_volume_1e8_m3"] / monthly["pred_water_volume_1e8_m3"].max() * 100).tolist()
    sediment = (
        monthly["pred_sediment_mass_1e4_t"] / monthly["pred_sediment_mass_1e4_t"].max() * 100
    ).tolist()
    y_max = 115
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_h - value / y_max * plot_h
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 52, y - 8), f"{value:.0f}", font=tick_font, fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_h), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill=(55, 65, 81), width=2)
    step = plot_w / (len(x_labels) - 1)
    for i, label in enumerate(x_labels):
        if i % 2 == 0:
            draw_centered(draw, (left + i * step, top + plot_h + 28), label, tick_font, (55, 65, 81))
    for values, color in [(water, (37, 99, 235)), (sediment, (220, 38, 38))]:
        points = [(left + i * step, top + plot_h - value / y_max * plot_h) for i, value in enumerate(values)]
        draw.line(points, fill=color, width=4)
        for x, y in points:
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=color)
    legend_y = height - 48
    draw.line((left, legend_y, left + 32, legend_y), fill=(37, 99, 235), width=4)
    draw.text((left + 42, legend_y - 12), "monthly water volume", font=axis_font, fill=(55, 65, 81))
    draw.line((left + 270, legend_y, left + 302, legend_y), fill=(220, 38, 38), width=4)
    draw.text((left + 312, legend_y - 12), "monthly sediment mass", font=axis_font, fill=(55, 65, 81))
    image.save(path)


def save_sampling_figure(monthly_counts: pd.DataFrame, path: Path) -> None:
    width, height = 1280, 720
    left, right, top, bottom = 105, 45, 88, 110
    plot_w, plot_h = width - left - right, height - top - bottom
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(28, bold=True)
    tick_font = get_font(14)
    axis_font = get_font(16)
    draw_centered(draw, (width / 2, 38), "Recommended Monthly Sampling Counts", title_font, (31, 41, 55))
    draw.text((left, top - 32), "samples", font=axis_font, fill=(55, 65, 81))
    x_labels = [f"{int(y)}-{int(m):02d}" for y, m in zip(monthly_counts["year"], monthly_counts["month"])]
    values = monthly_counts["samples"].tolist()
    y_max = max(values) * 1.2
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_h - value / y_max * plot_h
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 52, y - 8), f"{value:.0f}", font=tick_font, fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_h), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill=(55, 65, 81), width=2)
    group_w = plot_w / len(values)
    bar_w = min(34, group_w * 0.62)
    for i, (label, value) in enumerate(zip(x_labels, values)):
        x = left + i * group_w + (group_w - bar_w) / 2
        h = value / y_max * plot_h
        y = top + plot_h - h
        color = (220, 38, 38) if "07" in label or "08" in label or "09" in label else (37, 99, 235)
        draw.rounded_rectangle((x, y, x + bar_w, top + plot_h), radius=3, fill=color)
        if i % 2 == 0:
            draw_centered(draw, (x + bar_w / 2, top + plot_h + 28), label, tick_font, (55, 65, 81))
    image.save(path)


def dataframe_to_markdown(df: pd.DataFrame, floatfmt: str = ".4g") -> str:
    headers = list(df.columns)
    body = []
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


def write_report(
    validation: pd.DataFrame,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    plan: pd.DataFrame,
    monthly_counts: pd.DataFrame,
) -> None:
    validation_mean = validation[validation["heldout_year"].eq("mean")]
    high_risk = plan.sort_values("risk_score", ascending=False).head(20).sort_values("date")
    lines = [
        "# 问题三第三版分析",
        "",
        "本版以问题二的日尺度水沙通量序列为基础，采用“STL 分解思想 + 近年加权季节残差 + 情景预测”的组合模型预测 2022-2023 年水沙通量。",
        "模型先将 `log(1+x)` 序列分解为趋势项、季节项和残差项：趋势项由近四年年均对数通量拟合，季节项由历史同季节前后 15 天残差按日期距离和年份远近加权得到。为反映不确定性，输出偏枯、平水、偏丰三种情景，采样方案以平水情景为基础，并参考偏丰情景高风险。",
        "",
        "## 递推验证",
        "",
        dataframe_to_markdown(validation_mean, floatfmt=".5g"),
        "",
        "## 年度预测",
        "",
        dataframe_to_markdown(annual, floatfmt=".5g"),
        "",
        "## 月度预测",
        "",
        "![forecast monthly flux](../figures/forecast-monthly-flux.png)",
        "",
        dataframe_to_markdown(monthly, floatfmt=".5g"),
        "",
        "## 采样方案",
        "",
        "采样权重综合考虑预测沙通量强度、预测变化率、汛期/峰值期指标和历史突变月份风险。基础规则为枯水期低频、入汛前和退水期中频、汛期高频，并在高风险日期附近加密。",
        "",
        "![sampling counts](../figures/sampling-monthly-counts.png)",
        "",
        dataframe_to_markdown(monthly_counts, floatfmt=".5g"),
        "",
        "高风险采样日期示例：",
        "",
        dataframe_to_markdown(
            high_risk[
                [
                    "date",
                    "sampling_level",
                    "risk_score",
                    "pred_mean_flow_m3s",
                    "pred_mean_sediment_flux_kg_s",
                    "change_strength",
                ]
            ],
            floatfmt=".5g",
        ),
        "",
        "## 初步结论",
        "",
        "1. 预测结果仍呈现显著年周期，6-10 月水沙通量明显偏高。",
        "2. 7-9 月为未来两年主要高风险输沙时段，应保持高频监测。",
        "3. 采样方案采用低风险期稀疏、汛期加密、高风险日期补充加密的策略，在控制总次数的同时覆盖主要变化过程。",
        "",
    ]
    (DOCS_DIR / "question3-analysis.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    for directory in [DATA_DIR, RESULTS_DIR, DOCS_DIR, FIGURES_DIR, QA_DIR, MODELS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    daily = load_daily_flux()
    validation = pd.concat(
        [
            stl_validate(daily, "mean_flow_m3s"),
            stl_validate(daily, "mean_sediment_flux_kg_s"),
        ],
        ignore_index=True,
    )
    forecasts = stl_train_and_forecast(daily)
    monthly_scenarios, annual_scenarios = aggregate_scenarios(forecasts)
    monthly = monthly_scenarios[monthly_scenarios["scenario"] == "normal"].drop(columns=["scenario"]).reset_index(drop=True)
    plan, monthly_counts = build_sampling_plan(forecasts)
    model_settings = pd.DataFrame(
        [
            {
                "model": "stl_recent_weighted_seasonal_residual",
                "window_days": 15,
                "normal": "trend plus weighted mean of recent seasonal residuals",
                "low": "trend plus weighted 30th percentile of seasonal residuals",
                "high": "trend plus weighted 75th percentile of seasonal residuals",
            }
        ]
    )

    forecasts.to_csv(DATA_DIR / "predicted_daily_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly_scenarios.to_csv(RESULTS_DIR / "forecast_monthly_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    annual_scenarios.to_csv(RESULTS_DIR / "forecast_annual_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    plan.to_csv(RESULTS_DIR / "sampling_plan_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly_counts.to_csv(RESULTS_DIR / "sampling_monthly_counts_2022_2023.csv", index=False, encoding="utf-8-sig")
    validation.to_csv(QA_DIR / "forecast_validation.csv", index=False, encoding="utf-8-sig")
    model_settings.to_csv(QA_DIR / "model_settings.csv", index=False, encoding="utf-8-sig")
    save_forecast_figure(monthly, FIGURES_DIR / "forecast-monthly-flux.png")
    save_sampling_figure(monthly_counts, FIGURES_DIR / "sampling-monthly-counts.png")
    write_report(validation, annual_scenarios, monthly, plan, monthly_counts)

    print("Validation mean:")
    print(validation[validation["heldout_year"].eq("mean")].to_string(index=False))
    print("\nAnnual forecast:")
    print(annual_scenarios.to_string(index=False))
    print("\nSampling counts by year:")
    print(plan.groupby("year").size().rename("samples").reset_index().to_string(index=False))
    print("\nTop sampling months:")
    print(monthly_counts.sort_values("samples", ascending=False).head(8).to_string(index=False))


if __name__ == "__main__":
    main()
