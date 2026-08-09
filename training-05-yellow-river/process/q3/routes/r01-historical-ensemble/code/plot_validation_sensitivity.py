from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[2]
SCRIPT_PATH = PROJECT_DIR / "question-3" / "code" / "analyze_question3.py"
FIGURES_DIR = PROJECT_DIR / "question-3" / "figures"
QA_DIR = PROJECT_DIR / "question-3" / "qa"


def load_q3_module():
    spec = importlib.util.spec_from_file_location("question3_active", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


q3 = load_q3_module()
q3_base = q3.q3_base


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


def nice_number(value: float) -> str:
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    if value >= 1000:
        return f"{value:.0f}"
    if value >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}"


def weighted_prediction(
    train: pd.DataFrame,
    future_dates: pd.DatetimeIndex,
    target_col: str,
    template_weight: float,
) -> np.ndarray:
    template = q3_base.seasonal_template_forecast(train, future_dates, target_col, "normal")
    stl = q3_base.stl_combination_forecast(train, future_dates, target_col, "normal")
    return template_weight * template + (1 - template_weight) * stl


def make_fold_predictions(
    daily: pd.DataFrame,
    target_col: str,
    years: list[int],
    exclude_early: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = []
    weight_rows = []
    for year in years:
        train = daily[daily["date"].dt.year < year].copy()
        if exclude_early:
            train = train[train["date"].dt.year >= 2018].copy()
        test = daily[daily["date"].dt.year == year].copy()
        if len(train) < 365 or test.empty:
            continue
        future_dates = pd.DatetimeIndex(test["date"])
        template = q3_base.seasonal_template_forecast(train, future_dates, target_col, "normal")
        stl = q3_base.stl_combination_forecast(train, future_dates, target_col, "normal")
        weight_rows.append(
            {
                "year": year,
                "true": test[target_col].to_numpy(dtype=float),
                "template": template,
                "stl": stl,
            }
        )
    if not weight_rows:
        return pd.DataFrame(), pd.DataFrame()

    grid = []
    for weight in np.linspace(0, 1, 21):
        errors = []
        for row in weight_rows:
            true = row["true"]
            pred = weight * row["template"] + (1 - weight) * row["stl"]
            errors.append(float(np.sqrt(np.mean((np.log1p(true) - np.log1p(pred)) ** 2))))
        grid.append(
            {
                "target": target_col,
                "data_scope": "exclude_2016_2017" if exclude_early else "all_available",
                "template_weight": float(weight),
                "stl_weight": float(1 - weight),
                "mean_rmse_log": float(np.mean(errors)),
            }
        )
    grid_df = pd.DataFrame(grid)
    best = grid_df.sort_values(["mean_rmse_log", "template_weight"], ascending=[True, False]).iloc[0]
    weight = float(best["template_weight"])
    for row in weight_rows:
        true = row["true"]
        pred = weight * row["template"] + (1 - weight) * row["stl"]
        year = int(row["year"])
        dates = daily[daily["date"].dt.year == year]["date"].to_list()
        for date, actual, predicted in zip(dates, true, pred):
            records.append(
                {
                    "date": pd.Timestamp(date),
                    "year": year,
                    "target": target_col,
                    "data_scope": "exclude_2016_2017" if exclude_early else "all_available",
                    "actual": float(actual),
                    "predicted": float(predicted),
                    "template_weight": weight,
                    "stl_weight": 1 - weight,
                }
            )
    return pd.DataFrame(records), grid_df


def make_current_validation_predictions(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    validation, weight_grid = q3.validate_optimized(daily)
    weights = q3.selected_weights(weight_grid)
    for target_col in ["mean_flow_m3s", "mean_sediment_flux_kg_s"]:
        for year in [2018, 2019, 2020, 2021]:
            train = daily[daily["date"].dt.year < year].copy()
            test = daily[daily["date"].dt.year == year].copy()
            if len(train) < 365 or test.empty:
                continue
            pred = weighted_prediction(train, pd.DatetimeIndex(test["date"]), target_col, weights[target_col])
            for date, actual, predicted in zip(test["date"], test[target_col], pred):
                rows.append(
                    {
                        "date": pd.Timestamp(date),
                        "year": year,
                        "target": target_col,
                        "actual": float(actual),
                        "predicted": float(predicted),
                    }
                )
    return pd.DataFrame(rows)


def make_points(
    dates: pd.Series,
    values: pd.Series,
    rect: tuple[int, int, int, int],
    ymax: float,
    min_date: pd.Timestamp,
    max_date: pd.Timestamp,
) -> list[tuple[float, float]]:
    left, top, right, bottom = rect
    total_days = max(1, (max_date - min_date).days)
    out = []
    for date, value in zip(dates, values):
        x = left + (pd.Timestamp(date) - min_date).days / total_days * (right - left)
        y = bottom - max(0.0, min(float(value), ymax)) / ymax * (bottom - top)
        out.append((x, y))
    return out


def draw_panel(
    draw: ImageDraw.ImageDraw,
    df: pd.DataFrame,
    rect: tuple[int, int, int, int],
    title: str,
    unit: str,
    series: list[tuple[str, str, tuple[int, int, int], int]],
) -> None:
    left, top, right, bottom = rect
    title_font = get_font(24, bold=True)
    label_font = get_font(15)
    tick_font = get_font(13)
    min_date = pd.Timestamp(df["date"].min())
    max_date = pd.Timestamp(df["date"].max())
    ymax = max(float(df[col].max()) for _, col, _, _ in series) * 1.08
    if ymax <= 0:
        ymax = 1.0

    draw.text((left, top - 42), title, font=title_font, fill=(31, 41, 55))
    draw.text((left, top - 16), unit, font=label_font, fill=(75, 85, 99))

    for tick in range(6):
        value = ymax * tick / 5
        y = bottom - value / ymax * (bottom - top)
        draw.line((left, y, right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 74, y - 8), nice_number(value), font=tick_font, fill=(107, 114, 128))

    draw.line((left, top, left, bottom), fill=(55, 65, 81), width=2)
    draw.line((left, bottom, right, bottom), fill=(55, 65, 81), width=2)
    for year in range(min_date.year, max_date.year + 1):
        date = pd.Timestamp(f"{year}-01-01")
        if min_date <= date <= max_date:
            x = left + (date - min_date).days / max(1, (max_date - min_date).days) * (right - left)
            draw.line((x, bottom, x, bottom + 7), fill=(55, 65, 81), width=1)
            draw_centered(draw, (x, bottom + 24), str(year), tick_font, (55, 65, 81))

    legend_x = right - 520
    legend_y = top + 8
    for idx, (label, col, color, width) in enumerate(series):
        y = legend_y + idx * 24
        draw.line((legend_x, y, legend_x + 32, y), fill=color, width=width)
        draw.text((legend_x + 42, y - 10), label, font=label_font, fill=(55, 65, 81))
        points = make_points(df["date"], df[col], rect, ymax, min_date, max_date)
        if len(points) > 1:
            draw.line(points, fill=color, width=width)


def save_current_validation_figure(preds: pd.DataFrame, path: Path) -> None:
    width, height = 1600, 960
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(30, bold=True)
    draw_centered(draw, (width / 2, 42), "组合模型留一年验证：实际值与预测值对比", title_font, (17, 24, 39))
    panels = [
        ("mean_flow_m3s", "水流量 Q", "单位：m³/s", (120, 120, 1540, 440)),
        ("mean_sediment_flux_kg_s", "沙通量 F", "单位：kg/s", (120, 585, 1540, 905)),
    ]
    for target, title, unit, rect in panels:
        panel = preds[preds["target"] == target].copy()
        panel["actual_roll15"] = panel["actual"].rolling(15, min_periods=1, center=True).mean()
        panel["predicted_roll15"] = panel["predicted"].rolling(15, min_periods=1, center=True).mean()
        draw_panel(
            draw,
            panel,
            rect,
            title,
            unit,
            [
                ("实际值(15日平滑)", "actual_roll15", (31, 41, 55), 3),
                ("组合预测(15日平滑)", "predicted_roll15", (220, 38, 38), 3),
            ],
        )
    image.save(path)


def save_sensitivity_figure(sensitivity_preds: pd.DataFrame, path: Path) -> None:
    width, height = 1600, 960
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(30, bold=True)
    draw_centered(draw, (width / 2, 42), "2016-2017低水沙年份敏感性：实际值与预测值对比", title_font, (17, 24, 39))
    panels = [
        ("mean_flow_m3s", "水流量 Q（2019-2021验证）", "单位：m³/s", (120, 120, 1540, 440)),
        ("mean_sediment_flux_kg_s", "沙通量 F（2019-2021验证）", "单位：kg/s", (120, 585, 1540, 905)),
    ]
    for target, title, unit, rect in panels:
        full = sensitivity_preds[(sensitivity_preds["target"] == target) & (sensitivity_preds["data_scope"] == "all_available")].copy()
        late = sensitivity_preds[(sensitivity_preds["target"] == target) & (sensitivity_preds["data_scope"] == "exclude_2016_2017")].copy()
        panel = full[["date", "actual", "predicted"]].rename(columns={"predicted": "pred_all"})
        panel = panel.merge(late[["date", "predicted"]].rename(columns={"predicted": "pred_late"}), on="date", how="left")
        for col in ["actual", "pred_all", "pred_late"]:
            panel[f"{col}_roll15"] = panel[col].rolling(15, min_periods=1, center=True).mean()
        draw_panel(
            draw,
            panel,
            rect,
            title,
            unit,
            [
                ("实际值(15日平滑)", "actual_roll15", (31, 41, 55), 3),
                ("保留2016-2017预测", "pred_all_roll15", (37, 99, 235), 3),
                ("排除2016-2017预测", "pred_late_roll15", (22, 163, 74), 3),
            ],
        )
    image.save(path)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)
    daily = q3_base.load_daily_flux()

    current_preds = make_current_validation_predictions(daily)
    current_preds.to_csv(QA_DIR / "validation_actual_vs_predicted.csv", index=False, encoding="utf-8-sig")
    save_current_validation_figure(
        current_preds,
        FIGURES_DIR / "validation-actual-vs-predicted-2018-2021.png",
    )

    sensitivity_frames = []
    grid_frames = []
    for target in ["mean_flow_m3s", "mean_sediment_flux_kg_s"]:
        for exclude_early in [False, True]:
            preds, grid = make_fold_predictions(daily, target, [2019, 2020, 2021], exclude_early)
            sensitivity_frames.append(preds)
            grid_frames.append(grid)
    sensitivity_preds = pd.concat(sensitivity_frames, ignore_index=True)
    sensitivity_grid = pd.concat(grid_frames, ignore_index=True)
    sensitivity_preds.to_csv(QA_DIR / "early_year_sensitivity_predictions.csv", index=False, encoding="utf-8-sig")
    sensitivity_grid.to_csv(QA_DIR / "early_year_weight_sensitivity.csv", index=False, encoding="utf-8-sig")
    save_sensitivity_figure(
        sensitivity_preds,
        FIGURES_DIR / "early-year-sensitivity-actual-vs-predicted-2019-2021.png",
    )

    summary = (
        sensitivity_grid.sort_values(["target", "data_scope", "mean_rmse_log"])
        .groupby(["target", "data_scope"], as_index=False)
        .first()
    )
    summary.to_csv(QA_DIR / "early_year_weight_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
