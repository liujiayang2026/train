from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[2]
Q3_DIR = PROJECT_DIR / "question-3"
BASE_SCRIPT = Q3_DIR / "code" / "stl_base_question3.py"
LEGACY_SCRIPT = Q3_DIR / "code" / "analyze_question3.py"
DATA_DIR = Q3_DIR / "data" / "processed"
RESULTS_DIR = Q3_DIR / "results"
DOCS_DIR = Q3_DIR / "docs"
FIGURES_DIR = Q3_DIR / "figures"
QA_DIR = Q3_DIR / "qa"
SECONDS_PER_DAY = 86400
TARGETS = [
    ("mean_flow_m3s", "flow"),
    ("mean_sediment_flux_kg_s", "sediment_flux"),
]
SCENARIOS = ["low", "normal", "high"]
CV_YEARS = [2019, 2020, 2021]
RIDGE_ALPHA = 0.10
RECENT_SHAPE_WEIGHT = 0.60


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


q3_base = load_module("question3_base_regime", BASE_SCRIPT)
q3_legacy = load_module("question3_legacy_helpers", LEGACY_SCRIPT)


def monthly_series(daily: pd.DataFrame) -> pd.DataFrame:
    return (
        daily.set_index("date")[[target for target, _ in TARGETS]]
        .resample("MS")
        .mean()
        .reset_index()
    )


def detect_change_year(daily: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    annual = (
        daily.assign(year=daily["date"].dt.year)
        .groupby("year", as_index=False)
        .agg(
            mean_flow_m3s=("mean_flow_m3s", "mean"),
            mean_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "mean"),
        )
    )
    scores = []
    for idx in range(1, len(annual)):
        before = annual.iloc[:idx]
        after = annual.iloc[idx:]
        if len(after) < 2:
            continue
        score = 0.0
        for target, _ in TARGETS:
            before_level = float(np.log1p(before[target]).mean())
            after_level = float(np.log1p(after[target]).mean())
            score += abs(after_level - before_level)
        scores.append((int(annual.iloc[idx]["year"]), score))
    change_year = max(scores, key=lambda item: item[1])[0]
    for target, _ in TARGETS:
        annual[f"{target}_year_ratio"] = annual[target] / annual[target].shift(1)
    annual["selected_regime_start"] = annual["year"].eq(change_year)
    return change_year, annual


def month_design(dates: pd.Series | pd.DatetimeIndex, origin_year: int) -> np.ndarray:
    index = pd.DatetimeIndex(dates)
    month = index.month.to_numpy(dtype=float)
    trend = index.year.to_numpy(dtype=float) - origin_year + (month - 0.5) / 12.0
    columns = [np.ones(len(index)), trend]
    for harmonic in (1, 2, 3):
        angle = 2 * np.pi * harmonic * (month - 0.5) / 12.0
        columns.extend([np.sin(angle), np.cos(angle)])
    return np.column_stack(columns)


def fit_fourier_ridge(train_monthly: pd.DataFrame, target: str, change_year: int) -> dict[str, object]:
    regime = train_monthly[train_monthly["date"].dt.year >= change_year].copy()
    if len(regime) < 12:
        regime = train_monthly.copy()
    origin_year = int(regime["date"].dt.year.min())
    x = month_design(regime["date"], origin_year)
    y = np.log1p(regime[target].to_numpy(dtype=float))
    penalty = np.eye(x.shape[1]) * RIDGE_ALPHA
    penalty[0, 0] = 0.0
    penalty[1, 1] = RIDGE_ALPHA * 0.20
    coef = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    return {"origin_year": origin_year, "coef": coef}


def predict_fourier_ridge(model: dict[str, object], dates: pd.Series | pd.DatetimeIndex) -> np.ndarray:
    x = month_design(dates, int(model["origin_year"]))
    pred_log = x @ np.asarray(model["coef"], dtype=float)
    return np.expm1(pred_log).clip(min=0)


def legacy_weight(target: str) -> float:
    return 1.0 if target == "mean_flow_m3s" else 0.75


def legacy_daily_prediction(
    train: pd.DataFrame,
    future_dates: pd.DatetimeIndex,
    target: str,
    scenario: str = "normal",
) -> np.ndarray:
    weight = legacy_weight(target)
    template = q3_base.seasonal_template_forecast(train, future_dates, target, scenario)
    stl = q3_base.stl_combination_forecast(train, future_dates, target, scenario)
    return weight * template + (1.0 - weight) * stl


def aggregate_daily_mean(dates: pd.DatetimeIndex, values: np.ndarray) -> pd.Series:
    frame = pd.DataFrame({"date": dates, "value": values}).set_index("date")
    return frame["value"].resample("MS").mean()


def error_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual_log = np.log1p(actual)
    predicted_log = np.log1p(predicted)
    residual = actual_log - predicted_log
    denominator = float(np.sum((actual_log - actual_log.mean()) ** 2))
    return {
        "rmse_log": float(np.sqrt(np.mean(residual**2))),
        "mae_log": float(np.mean(np.abs(residual))),
        "r2_log": float(1.0 - np.sum(residual**2) / denominator) if denominator > 0 else np.nan,
        "wape": float(np.sum(np.abs(actual - predicted)) / np.sum(np.abs(actual))),
    }


def build_cv_components(
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    target: str,
    change_year: int,
) -> list[dict[str, object]]:
    folds = []
    for year in CV_YEARS:
        train_daily = daily[daily["date"].dt.year < year].copy()
        test_daily = daily[daily["date"].dt.year == year].copy()
        train_monthly = monthly[monthly["date"].dt.year < year].copy()
        test_monthly = monthly[monthly["date"].dt.year == year].copy()
        if test_monthly.empty:
            continue
        dates = pd.DatetimeIndex(test_daily["date"])
        legacy_daily = legacy_daily_prediction(train_daily, dates, target)
        legacy_monthly = aggregate_daily_mean(dates, legacy_daily).to_numpy(dtype=float)
        model = fit_fourier_ridge(train_monthly, target, change_year)
        fourier_monthly = predict_fourier_ridge(model, test_monthly["date"])
        folds.append(
            {
                "year": year,
                "dates": pd.DatetimeIndex(test_monthly["date"]),
                "actual": test_monthly[target].to_numpy(dtype=float),
                "legacy": legacy_monthly,
                "fourier": fourier_monthly,
            }
        )
    return folds


def select_hybrid_weight(folds: list[dict[str, object]], target: str) -> tuple[float, pd.DataFrame]:
    rows = []
    for weight in np.linspace(0.0, 1.0, 21):
        fold_rmse = []
        for fold in folds:
            pred = weight * np.asarray(fold["fourier"]) + (1.0 - weight) * np.asarray(fold["legacy"])
            fold_rmse.append(error_metrics(np.asarray(fold["actual"]), pred)["rmse_log"])
        rows.append(
            {
                "target": target,
                "fourier_weight": float(weight),
                "legacy_weight": float(1.0 - weight),
                "mean_monthly_rmse_log": float(np.mean(fold_rmse)),
            }
        )
    grid = pd.DataFrame(rows)
    best = grid.sort_values(["mean_monthly_rmse_log", "fourier_weight"]).iloc[0]
    return float(best["fourier_weight"]), grid


def validate_model(
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    change_year: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float], dict[str, tuple[float, float]]]:
    metric_rows = []
    prediction_rows = []
    grids = []
    selected_weights: dict[str, float] = {}
    interval_factors: dict[str, tuple[float, float]] = {}
    for target, _ in TARGETS:
        folds = build_cv_components(daily, monthly, target, change_year)
        weight, grid = select_hybrid_weight(folds, target)
        selected_weights[target] = weight
        grids.append(grid)
        residuals = []
        for fold in folds:
            actual = np.asarray(fold["actual"], dtype=float)
            legacy = np.asarray(fold["legacy"], dtype=float)
            fourier = np.asarray(fold["fourier"], dtype=float)
            hybrid = weight * fourier + (1.0 - weight) * legacy
            residuals.extend((np.log1p(actual) - np.log1p(hybrid)).tolist())
            for model_name, predicted in [
                ("legacy_daily_ensemble", legacy),
                ("regime_fourier_ridge", fourier),
                ("regime_hybrid", hybrid),
            ]:
                metric_rows.append(
                    {
                        "target": target,
                        "model": model_name,
                        "heldout_year": int(fold["year"]),
                        **error_metrics(actual, predicted),
                    }
                )
            for date, actual_value, legacy_value, fourier_value, hybrid_value in zip(
                fold["dates"], actual, legacy, fourier, hybrid
            ):
                prediction_rows.append(
                    {
                        "date": pd.Timestamp(date),
                        "year": int(fold["year"]),
                        "target": target,
                        "actual": float(actual_value),
                        "legacy_predicted": float(legacy_value),
                        "fourier_predicted": float(fourier_value),
                        "hybrid_predicted": float(hybrid_value),
                    }
                )
        low_residual, high_residual = np.quantile(np.asarray(residuals), [0.10, 0.90])
        low_factor = min(0.90, float(np.exp(low_residual)))
        high_factor = max(1.10, float(np.exp(high_residual)))
        interval_factors[target] = (low_factor, high_factor)
    detail = pd.DataFrame(metric_rows)
    summary = (
        detail.groupby(["target", "model"], as_index=False)
        .agg(
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            wape=("wape", "mean"),
        )
    )
    summary.insert(2, "heldout_year", "mean")
    validation = pd.concat([detail, summary], ignore_index=True)
    predictions = pd.DataFrame(prediction_rows)
    for target, (low_factor, high_factor) in interval_factors.items():
        mask = predictions["target"].eq(target)
        predictions.loc[mask, "lower_80"] = predictions.loc[mask, "hybrid_predicted"] * low_factor
        predictions.loc[mask, "upper_80"] = predictions.loc[mask, "hybrid_predicted"] * high_factor
    return validation, predictions, pd.concat(grids, ignore_index=True), selected_weights, interval_factors


def build_historical_backtest(
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    change_year: int,
    weights: dict[str, float],
    interval_factors: dict[str, tuple[float, float]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_rows = []
    metric_rows = []
    for target, _ in TARGETS:
        for year in (2018, 2019, 2020, 2021):
            train_daily = daily[daily["date"].dt.year < year].copy()
            test_daily = daily[daily["date"].dt.year == year].copy()
            train_monthly = monthly[monthly["date"].dt.year < year].copy()
            test_monthly = monthly[monthly["date"].dt.year == year].copy()
            dates = pd.DatetimeIndex(test_daily["date"])
            legacy_daily = legacy_daily_prediction(train_daily, dates, target)
            legacy_monthly = aggregate_daily_mean(dates, legacy_daily).to_numpy(dtype=float)
            fourier_model = fit_fourier_ridge(train_monthly, target, change_year)
            fourier_monthly = predict_fourier_ridge(fourier_model, test_monthly["date"])
            fourier_weight = weights[target]
            hybrid = fourier_weight * fourier_monthly + (1.0 - fourier_weight) * legacy_monthly
            actual = test_monthly[target].to_numpy(dtype=float)
            low_factor, high_factor = interval_factors[target]
            metrics = error_metrics(actual, hybrid)
            metric_rows.append(
                {
                    "target": target,
                    "heldout_year": year,
                    "train_end": year - 1,
                    "evaluation_scope": "structural_break_stress_test" if year == 2018 else "rolling_origin",
                    **metrics,
                }
            )
            for date, actual_value, predicted_value in zip(test_monthly["date"], actual, hybrid):
                prediction_rows.append(
                    {
                        "date": pd.Timestamp(date),
                        "year": year,
                        "target": target,
                        "train_end": year - 1,
                        "actual": float(actual_value),
                        "hybrid_predicted": float(predicted_value),
                        "lower_80": float(predicted_value * low_factor),
                        "upper_80": float(predicted_value * high_factor),
                    }
                )
    return pd.DataFrame(prediction_rows), pd.DataFrame(metric_rows)


def calibrate_daily_to_monthly(
    dates: pd.DatetimeIndex,
    daily_values: np.ndarray,
    monthly_dates: pd.DatetimeIndex,
    monthly_means: np.ndarray,
) -> np.ndarray:
    daily_frame = pd.DataFrame({"date": dates, "value": daily_values})
    month_key = daily_frame["date"].dt.to_period("M").dt.to_timestamp()
    current_means = daily_frame.assign(month=month_key).groupby("month")["value"].mean()
    target_means = pd.Series(monthly_means, index=monthly_dates)
    scale = month_key.map(target_means / current_means).to_numpy(dtype=float)
    return np.maximum(0.0, daily_values * scale)


def apply_recent_regime_shape(
    history_monthly: pd.DataFrame,
    target: str,
    future_months: pd.DatetimeIndex,
    baseline_monthly: np.ndarray,
    recent_weight: float = RECENT_SHAPE_WEIGHT,
) -> np.ndarray:
    latest_year = int(history_monthly["date"].dt.year.max())
    recent = (
        history_monthly[history_monthly["date"].dt.year.eq(latest_year)]
        .sort_values("date")[target]
        .to_numpy(dtype=float)
    )
    if len(recent) != 12:
        return baseline_monthly.copy()
    recent_shape = recent / recent.mean()
    corrected = np.zeros_like(baseline_monthly, dtype=float)
    future_years = future_months.year.to_numpy(dtype=int)
    for year in np.unique(future_years):
        mask = future_years == year
        baseline = baseline_monthly[mask]
        month_days = future_months[mask].days_in_month.to_numpy(dtype=float)
        baseline_shape = baseline / baseline.mean()
        mixed_shape = np.exp(
            (1.0 - recent_weight) * np.log(np.maximum(baseline_shape, 1e-9))
            + recent_weight * np.log(np.maximum(recent_shape, 1e-9))
        )
        baseline_weighted_mean = float(np.average(baseline, weights=month_days))
        mixed_weighted_mean = float(np.average(mixed_shape, weights=month_days))
        corrected[mask] = mixed_shape / mixed_weighted_mean * baseline_weighted_mean
    return corrected


def recent_shape_sensitivity(
    history_monthly: pd.DataFrame,
    baseline_by_target: dict[str, np.ndarray],
    future_months: pd.DatetimeIndex,
) -> pd.DataFrame:
    rows = []
    for target, _ in TARGETS:
        for weight in (0.40, 0.60, 0.80):
            values = apply_recent_regime_shape(
                history_monthly,
                target,
                future_months,
                baseline_by_target[target],
                recent_weight=weight,
            )
            for year in np.unique(future_months.year):
                mask = future_months.year == year
                year_values = values[mask]
                flood_values = year_values[5:10]
                rows.append(
                    {
                        "target": target,
                        "recent_shape_weight": weight,
                        "year": int(year),
                        "annual_monthly_mean": float(year_values.mean()),
                        "peak_month": int(np.argmax(year_values) + 1),
                        "flood_season_trough_month": int(np.argmin(flood_values) + 6),
                        "august_value": float(year_values[7]),
                        "october_value": float(year_values[9]),
                    }
                )
    return pd.DataFrame(rows)


def forecast_daily(
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    change_year: int,
    weights: dict[str, float],
    interval_factors: dict[str, tuple[float, float]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    future_dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    future_months = pd.date_range("2022-01-01", "2023-12-01", freq="MS")
    forecasts = pd.DataFrame({"date": future_dates})
    baseline_by_target: dict[str, np.ndarray] = {}
    for target, stem in TARGETS:
        legacy_normal = legacy_daily_prediction(daily, future_dates, target, "normal")
        legacy_monthly = aggregate_daily_mean(future_dates, legacy_normal).to_numpy(dtype=float)
        model = fit_fourier_ridge(monthly, target, change_year)
        fourier_monthly = predict_fourier_ridge(model, future_months)
        weight = weights[target]
        hybrid_monthly = weight * fourier_monthly + (1.0 - weight) * legacy_monthly
        baseline_by_target[target] = hybrid_monthly.copy()
        adaptive_monthly = apply_recent_regime_shape(
            monthly,
            target,
            future_months,
            hybrid_monthly,
        )
        normal = calibrate_daily_to_monthly(
            future_dates,
            legacy_normal,
            future_months,
            adaptive_monthly,
        )
        low_factor, high_factor = interval_factors[target]
        low = normal * low_factor
        high = normal * high_factor
        column = "mean_flow_m3s" if stem == "flow" else "mean_sediment_flux_kg_s"
        forecasts[f"low_pred_{column}"] = low
        forecasts[f"normal_pred_{column}"] = normal
        forecasts[f"high_pred_{column}"] = high
    for scenario in SCENARIOS:
        forecasts[f"{scenario}_pred_water_volume_m3"] = (
            forecasts[f"{scenario}_pred_mean_flow_m3s"] * SECONDS_PER_DAY
        )
        forecasts[f"{scenario}_pred_sediment_mass_kg"] = (
            forecasts[f"{scenario}_pred_mean_sediment_flux_kg_s"] * SECONDS_PER_DAY
        )
        forecasts[f"{scenario}_pred_water_volume_1e8_m3"] = (
            forecasts[f"{scenario}_pred_water_volume_m3"] / 1e8
        )
        forecasts[f"{scenario}_pred_sediment_mass_1e4_t"] = (
            forecasts[f"{scenario}_pred_sediment_mass_kg"] / 1e7
        )
    forecasts["pred_mean_flow_m3s"] = forecasts["normal_pred_mean_flow_m3s"]
    forecasts["pred_mean_sediment_flux_kg_s"] = forecasts["normal_pred_mean_sediment_flux_kg_s"]
    forecasts["pred_water_volume_m3"] = forecasts["normal_pred_water_volume_m3"]
    forecasts["pred_sediment_mass_kg"] = forecasts["normal_pred_sediment_mass_kg"]
    forecasts["pred_water_volume_1e8_m3"] = forecasts["normal_pred_water_volume_1e8_m3"]
    forecasts["pred_sediment_mass_1e4_t"] = forecasts["normal_pred_sediment_mass_1e4_t"]
    forecasts["year"] = forecasts["date"].dt.year
    forecasts["month"] = forecasts["date"].dt.month
    sensitivity = recent_shape_sensitivity(monthly, baseline_by_target, future_months)
    return forecasts, sensitivity


def build_history_forecast_comparison(
    history_monthly: pd.DataFrame,
    monthly_scenarios: pd.DataFrame,
) -> pd.DataFrame:
    history = history_monthly.copy()
    history["period"] = "historical"
    history = history.rename(
        columns={
            "mean_flow_m3s": "actual_mean_flow_m3s",
            "mean_sediment_flux_kg_s": "actual_mean_sediment_flux_kg_s",
        }
    )
    history = history[
        ["date", "period", "actual_mean_flow_m3s", "actual_mean_sediment_flux_kg_s"]
    ]
    forecast = None
    for scenario in SCENARIOS:
        part = monthly_scenarios[monthly_scenarios["scenario"].eq(scenario)].copy()
        part["date"] = pd.to_datetime(
            dict(year=part["year"].astype(int), month=part["month"].astype(int), day=1)
        )
        part = part[
            ["date", "pred_mean_flow_m3s", "pred_mean_sediment_flux_kg_s"]
        ].rename(
            columns={
                "pred_mean_flow_m3s": f"{scenario}_pred_mean_flow_m3s",
                "pred_mean_sediment_flux_kg_s": f"{scenario}_pred_mean_sediment_flux_kg_s",
            }
        )
        forecast = part if forecast is None else forecast.merge(part, on="date", how="outer")
    if forecast is None:
        raise RuntimeError("No forecast scenarios were produced")
    forecast["period"] = "forecast"
    return pd.concat([history, forecast], ignore_index=True, sort=False).sort_values("date")


def get_font(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def save_validation_figure(
    predictions: pd.DataFrame,
    path: Path,
    title: str = "变点混合模型：月尺度滚动验证（2019-2021）",
) -> None:
    width, height = 1600, 920
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = get_font(30, True)
    label_font = get_font(19, True)
    tick_font = get_font(14)
    title_box = draw.textbbox((0, 0), title, font=title_font)
    title_width = title_box[2] - title_box[0]
    draw.text(((width - title_width) / 2, 24), title, font=title_font, fill=(25, 34, 48, 255))
    panels = [
        ("mean_flow_m3s", "月均流量 Q（m³/s）", (110, 120, 1540, 425)),
        ("mean_sediment_flux_kg_s", "月均输沙通量 F（kg/s）", (110, 565, 1540, 870)),
    ]
    for target, title, rect in panels:
        panel = predictions[predictions["target"].eq(target)].sort_values("date").reset_index(drop=True)
        left, top, right, bottom = rect
        ymax = float(panel[["actual", "upper_80"]].to_numpy().max()) * 1.08
        draw.text((left, top - 40), title, font=label_font, fill=(31, 41, 55, 255))
        for tick in range(6):
            value = ymax * tick / 5
            y = bottom - value / ymax * (bottom - top)
            draw.line((left, y, right, y), fill=(225, 229, 235, 255), width=1)
            text_value = f"{value / 10000:.1f}万" if value >= 10000 else f"{value:.0f}"
            draw.text((left - 72, y - 8), text_value, font=tick_font, fill=(95, 104, 118, 255))
        draw.line((left, top, left, bottom), fill=(55, 65, 81, 255), width=2)
        draw.line((left, bottom, right, bottom), fill=(55, 65, 81, 255), width=2)
        count = len(panel)
        xs = np.linspace(left, right, count)
        lower = bottom - panel["lower_80"].to_numpy() / ymax * (bottom - top)
        upper = bottom - panel["upper_80"].to_numpy() / ymax * (bottom - top)
        band = list(zip(xs, upper)) + list(zip(xs[::-1], lower[::-1]))
        draw.polygon(band, fill=(239, 68, 68, 35))
        for column, color, line_width in [
            ("actual", (31, 41, 55, 255), 4),
            ("hybrid_predicted", (220, 38, 38, 255), 4),
        ]:
            ys = bottom - panel[column].to_numpy() / ymax * (bottom - top)
            draw.line(list(zip(xs, ys)), fill=color, width=line_width)
        for idx, row in panel.iterrows():
            if int(row["date"].month) == 1:
                x = xs[idx]
                draw.line((x, bottom, x, bottom + 7), fill=(55, 65, 81, 255), width=1)
                draw.text((x - 18, bottom + 13), str(int(row["year"])), font=tick_font, fill=(55, 65, 81, 255))
        legend_x = right - 490
        draw.line((legend_x, top + 14, legend_x + 34, top + 14), fill=(31, 41, 55, 255), width=4)
        draw.text((legend_x + 44, top + 3), "实际月均值", font=tick_font, fill=(55, 65, 81, 255))
        draw.line((legend_x + 145, top + 14, legend_x + 179, top + 14), fill=(220, 38, 38, 255), width=4)
        draw.text((legend_x + 189, top + 3), "滚动预测", font=tick_font, fill=(55, 65, 81, 255))
        draw.rectangle((legend_x + 288, top + 5, legend_x + 322, top + 23), fill=(239, 68, 68, 45))
        draw.text((legend_x + 332, top + 3), "80%经验区间", font=tick_font, fill=(55, 65, 81, 255))
    image.save(path)


def save_history_forecast_figure(comparison: pd.DataFrame, path: Path) -> None:
    width, height = 1680, 980
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = get_font(31, True)
    label_font = get_font(20, True)
    tick_font = get_font(14)
    draw.text((455, 24), "2016-2021 历史水沙过程与 2022-2023 预测对照", font=title_font, fill=(25, 34, 48, 255))
    panels = [
        (
            "月均流量 Q（m³/s）",
            "actual_mean_flow_m3s",
            "low_pred_mean_flow_m3s",
            "normal_pred_mean_flow_m3s",
            "high_pred_mean_flow_m3s",
            (120, 125, 1610, 450),
        ),
        (
            "月均输沙通量 F（kg/s）",
            "actual_mean_sediment_flux_kg_s",
            "low_pred_mean_sediment_flux_kg_s",
            "normal_pred_mean_sediment_flux_kg_s",
            "high_pred_mean_sediment_flux_kg_s",
            (120, 610, 1610, 935),
        ),
    ]
    dates = pd.DatetimeIndex(comparison["date"])
    min_date = pd.Timestamp(dates.min())
    max_date = pd.Timestamp(dates.max())
    total_days = max(1, (max_date - min_date).days)
    for title, actual_col, low_col, normal_col, high_col, rect in panels:
        left, top, right, bottom = rect
        historical = comparison[comparison["period"].eq("historical")].dropna(subset=[actual_col])
        forecast = comparison[comparison["period"].eq("forecast")].dropna(subset=[normal_col])
        ymax = max(float(historical[actual_col].max()), float(forecast[high_col].max())) * 1.08
        draw.text((left, top - 42), title, font=label_font, fill=(31, 41, 55, 255))
        for tick in range(6):
            value = ymax * tick / 5
            y = bottom - value / ymax * (bottom - top)
            draw.line((left, y, right, y), fill=(225, 229, 235, 255), width=1)
            text_value = f"{value / 10000:.1f}万" if value >= 10000 else f"{value:.0f}"
            draw.text((left - 78, y - 8), text_value, font=tick_font, fill=(95, 104, 118, 255))
        draw.line((left, top, left, bottom), fill=(55, 65, 81, 255), width=2)
        draw.line((left, bottom, right, bottom), fill=(55, 65, 81, 255), width=2)

        def x_position(date: pd.Timestamp) -> float:
            return left + (date - min_date).days / total_days * (right - left)

        def y_position(value: float) -> float:
            return bottom - value / ymax * (bottom - top)

        for year in range(min_date.year, max_date.year + 1):
            date = pd.Timestamp(f"{year}-01-01")
            if min_date <= date <= max_date:
                x = x_position(date)
                draw.line((x, bottom, x, bottom + 7), fill=(55, 65, 81, 255), width=1)
                draw.text((x - 18, bottom + 13), str(year), font=tick_font, fill=(55, 65, 81, 255))

        forecast_x = [x_position(pd.Timestamp(date)) for date in forecast["date"]]
        lower_y = [y_position(float(value)) for value in forecast[low_col]]
        upper_y = [y_position(float(value)) for value in forecast[high_col]]
        band = list(zip(forecast_x, upper_y)) + list(zip(forecast_x[::-1], lower_y[::-1]))
        draw.polygon(band, fill=(239, 68, 68, 38))
        actual_points = [
            (x_position(pd.Timestamp(date)), y_position(float(value)))
            for date, value in zip(historical["date"], historical[actual_col])
        ]
        forecast_points = [
            (x_position(pd.Timestamp(date)), y_position(float(value)))
            for date, value in zip(forecast["date"], forecast[normal_col])
        ]
        draw.line(actual_points, fill=(31, 41, 55, 255), width=4)
        draw.line(forecast_points, fill=(220, 38, 38, 255), width=4)
        boundary = x_position(pd.Timestamp("2022-01-01"))
        dash_y = top
        while dash_y < bottom:
            draw.line((boundary, dash_y, boundary, min(dash_y + 10, bottom)), fill=(37, 99, 235, 210), width=3)
            dash_y += 18
        draw.text((boundary + 10, top + 32), "预测起点", font=tick_font, fill=(37, 99, 235, 255))
        legend_x = right - 520
        draw.line((legend_x, top + 14, legend_x + 34, top + 14), fill=(31, 41, 55, 255), width=4)
        draw.text((legend_x + 44, top + 3), "历史值", font=tick_font, fill=(55, 65, 81, 255))
        draw.line((legend_x + 130, top + 14, legend_x + 164, top + 14), fill=(220, 38, 38, 255), width=4)
        draw.text((legend_x + 174, top + 3), "近期状态修正预测", font=tick_font, fill=(55, 65, 81, 255))
        draw.rectangle((legend_x + 345, top + 5, legend_x + 379, top + 23), fill=(239, 68, 68, 45))
        draw.text((legend_x + 389, top + 3), "经验情景区间", font=tick_font, fill=(55, 65, 81, 255))
    image.save(path)


def markdown_table(df: pd.DataFrame) -> str:
    return q3_base.dataframe_to_markdown(df, floatfmt=".5g")


def write_report(
    change_year: int,
    validation: pd.DataFrame,
    weights: dict[str, float],
    intervals: dict[str, tuple[float, float]],
    annual: pd.DataFrame,
) -> None:
    mean_validation = validation[validation["heldout_year"].eq("mean")].copy()
    comparison_rows = []
    for target, _ in TARGETS:
        target_rows = mean_validation[mean_validation["target"].eq(target)].set_index("model")
        legacy_row = target_rows.loc["legacy_daily_ensemble"]
        hybrid_row = target_rows.loc["regime_hybrid"]
        comparison_rows.append(
            {
                "target": target,
                "legacy_rmse_log": legacy_row["rmse_log"],
                "hybrid_rmse_log": hybrid_row["rmse_log"],
                "rmse_reduction_pct": 100.0 * (legacy_row["rmse_log"] - hybrid_row["rmse_log"]) / legacy_row["rmse_log"],
                "legacy_wape": legacy_row["wape"],
                "hybrid_wape": hybrid_row["wape"],
            }
        )
    comparison = pd.DataFrame(comparison_rows)
    settings = pd.DataFrame(
        [
            {
                "target": target,
                "regime_start": change_year,
                "fourier_weight": weights[target],
                "legacy_weight": 1.0 - weights[target],
                "low_factor": intervals[target][0],
                "high_factor": intervals[target][1],
            }
            for target, _ in TARGETS
        ]
    )
    normal_annual = annual[annual["scenario"].eq("normal")].copy()
    lines = [
        "# 问题三：变点感知的月-日两尺度混合预测",
        "",
        "## 改进结论",
        "",
        f"年均水沙序列在 {change_year} 年出现明显状态跃迁，因此不再把 2016-2017 低水沙状态与跃迁后的年份等权拟合。模型以月尺度预测未来趋势，再把月均值分配到日尺度，用于采样计划。",
        "",
        "逐日洪峰的准确日期受调度和降雨影响，无法仅凭日期变量提前两年确定。因此正式精度评价采用月尺度滚动外推；逐日结果表示季节风险形状，不解释为精确洪峰预报。",
        "",
        "## 模型结构",
        "",
        "1. 用年均对数水沙水平识别结构变点。",
        "2. 在变点后数据上拟合带三阶 Fourier 季节项的岭回归。",
        "3. 将 Fourier 月模型与原 STL/季节模板模型组合，权重由 2019-2021 留一年验证选择。",
        "4. 用验证残差的 10% 和 90% 分位数构造经验情景区间。",
        "5. 保留原模型日内季节形状，并逐月缩放到混合模型预测的月均值。",
        f"6. 最终外推使用最新状态自适应修正：基准季节形状权重 {1 - RECENT_SHAPE_WEIGHT:.0%}，2021 年型权重 {RECENT_SHAPE_WEIGHT:.0%}；每个预测年的年度均值保持不变。",
        "",
        "## 参数",
        "",
        markdown_table(settings),
        "",
        "## 月尺度滚动验证",
        "",
        markdown_table(mean_validation.sort_values(["target", "rmse_log"])),
        "",
        "相对上一版模型的直接改进为：",
        "",
        markdown_table(comparison),
        "",
        "![validation](../figures/regime-hybrid-monthly-validation.png)",
        "",
        "完整的 2018-2021 严格时间外推对照如下。每一年只使用该年以前的数据；2018 年是结构突变压力测试。",
        "",
        "![2018-2021 backtest](../figures/historical-backtest-2018-2021.png)",
        "",
        "2018 年只用 2016-2017 年数据无法预见制度性跃迁，因此将其视为结构突变压力测试，不与 2019-2021 常规滚动预测平均。这个处理避免用一个先验不可知的突变夸大模型日常外推误差。",
        "",
        "## 2022-2023 平水情景预测",
        "",
        markdown_table(normal_annual),
        "",
        "完整偏枯、平水、偏丰结果见 `results/forecast_annual_flux_2022_2023.csv`。",
        "",
        "## 历史与预测连续对照",
        "",
        "![history forecast comparison](../figures/history-vs-forecast-monthly.png)",
        "",
        "近期状态修正保留了 2021 年 8 月低谷和 10-11 月秋季高值特征，避免最终预测继续把 8 月机械设置为唯一洪峰。该修正反映最新观测状态，但不作为 2019-2021 交叉验证最优参数；其权重敏感性见 `qa/recent_regime_sensitivity.csv`。",
        "",
        "## 论文表述边界",
        "",
        "模型能较稳定地给出月度水沙趋势、汛期风险窗口和年度总量；不能保证两年前精确命中某一天的洪峰。采样方案因此采用汛期固定加密与高风险窗口加密，并建议获得新监测值后按月滚动更新。",
        "",
    ]
    (DOCS_DIR / "question3-analysis.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    for directory in [DATA_DIR, RESULTS_DIR, DOCS_DIR, FIGURES_DIR, QA_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    daily = q3_base.load_daily_flux()
    monthly = monthly_series(daily)
    change_year, change_table = detect_change_year(daily)
    validation, validation_predictions, weight_grid, weights, intervals = validate_model(
        daily, monthly, change_year
    )
    historical_backtest, historical_backtest_metrics = build_historical_backtest(
        daily, monthly, change_year, weights, intervals
    )
    forecasts, recent_sensitivity = forecast_daily(daily, monthly, change_year, weights, intervals)
    monthly_scenarios, annual_scenarios = q3_base.aggregate_scenarios(forecasts)
    monthly_normal = monthly_scenarios[monthly_scenarios["scenario"].eq("normal")].drop(
        columns=["scenario"]
    )
    plan, monthly_counts = q3_base.build_sampling_plan(forecasts)
    schedule, schedule_monthly_counts = q3_legacy.expand_sampling_schedule(plan)
    comparison = build_history_forecast_comparison(monthly, monthly_scenarios)

    settings = pd.DataFrame(
        [
            {
                "model": "regime_fourier_stl_hybrid",
                "target": target,
                "regime_start": change_year,
                "ridge_alpha": RIDGE_ALPHA,
                "fourier_weight": weights[target],
                "legacy_weight": 1.0 - weights[target],
                "low_factor": intervals[target][0],
                "high_factor": intervals[target][1],
                "recent_shape_weight": RECENT_SHAPE_WEIGHT,
                "recent_shape_source_year": int(monthly["date"].dt.year.max()),
                "validation_scale": "monthly rolling-origin",
            }
            for target, _ in TARGETS
        ]
    )
    forecasts.to_csv(DATA_DIR / "predicted_daily_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly_scenarios.to_csv(RESULTS_DIR / "forecast_monthly_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    annual_scenarios.to_csv(RESULTS_DIR / "forecast_annual_flux_2022_2023.csv", index=False, encoding="utf-8-sig")
    plan.to_csv(RESULTS_DIR / "sampling_plan_2022_2023.csv", index=False, encoding="utf-8-sig")
    monthly_counts.to_csv(RESULTS_DIR / "sampling_monthly_counts_2022_2023.csv", index=False, encoding="utf-8-sig")
    schedule.to_csv(RESULTS_DIR / "sampling_schedule_2022_2023.csv", index=False, encoding="utf-8-sig")
    schedule_monthly_counts.to_csv(
        RESULTS_DIR / "sampling_schedule_monthly_counts_2022_2023.csv", index=False, encoding="utf-8-sig"
    )
    validation.to_csv(QA_DIR / "forecast_validation.csv", index=False, encoding="utf-8-sig")
    validation_predictions.to_csv(
        QA_DIR / "monthly_validation_actual_vs_predicted.csv", index=False, encoding="utf-8-sig"
    )
    historical_backtest.to_csv(
        QA_DIR / "historical_backtest_2018_2021.csv", index=False, encoding="utf-8-sig"
    )
    historical_backtest_metrics.to_csv(
        QA_DIR / "historical_backtest_metrics_2018_2021.csv", index=False, encoding="utf-8-sig"
    )
    weight_grid.to_csv(QA_DIR / "weight_selection.csv", index=False, encoding="utf-8-sig")
    change_table.to_csv(QA_DIR / "structural_change_detection.csv", index=False, encoding="utf-8-sig")
    recent_sensitivity.to_csv(QA_DIR / "recent_regime_sensitivity.csv", index=False, encoding="utf-8-sig")
    settings.to_csv(QA_DIR / "model_settings.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(
        RESULTS_DIR / "history_forecast_monthly_comparison.csv", index=False, encoding="utf-8-sig"
    )

    q3_base.save_forecast_figure(monthly_normal, FIGURES_DIR / "forecast-monthly-flux.png")
    q3_base.save_sampling_figure(monthly_counts, FIGURES_DIR / "sampling-monthly-counts.png")
    save_validation_figure(validation_predictions, FIGURES_DIR / "regime-hybrid-monthly-validation.png")
    save_validation_figure(
        historical_backtest,
        FIGURES_DIR / "historical-backtest-2018-2021.png",
        title="模型历史回测：实际值与预测值对照（2018-2021）",
    )
    save_history_forecast_figure(comparison, FIGURES_DIR / "history-vs-forecast-monthly.png")
    q3_legacy.write_sampling_schedule_detail(schedule)
    write_report(change_year, validation, weights, intervals, annual_scenarios)

    print(f"Detected regime start: {change_year}")
    print("\nModel settings:")
    print(settings.to_string(index=False))
    print("\nMean monthly rolling validation:")
    print(validation[validation["heldout_year"].eq("mean")].sort_values(["target", "rmse_log"]).to_string(index=False))
    print("\nAnnual forecasts:")
    print(annual_scenarios.to_string(index=False))


if __name__ == "__main__":
    main()
