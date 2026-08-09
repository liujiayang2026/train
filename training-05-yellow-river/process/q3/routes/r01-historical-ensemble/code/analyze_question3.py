from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[2]
BASE_SCRIPT = PROJECT_DIR / "question-3" / "code" / "stl_base_question3.py"
Q3_OPT_DIR = PROJECT_DIR / "question-3"
DATA_DIR = Q3_OPT_DIR / "data" / "processed"
RESULTS_DIR = Q3_OPT_DIR / "results"
DOCS_DIR = Q3_OPT_DIR / "docs"
FIGURES_DIR = Q3_OPT_DIR / "figures"
QA_DIR = Q3_OPT_DIR / "qa"
MODELS_DIR = Q3_OPT_DIR / "models"
SECONDS_PER_DAY = 24 * 3600
SCENARIOS = ["low", "normal", "high"]
TARGETS = [
    ("mean_flow_m3s", "flow"),
    ("mean_sediment_flux_kg_s", "sediment_flux"),
]


def load_base_module():
    spec = importlib.util.spec_from_file_location("question3_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import base question-3 script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


q3_base = load_base_module()


def metric_row(target: str, model: str, heldout_year: int | str, true: np.ndarray, pred: np.ndarray) -> dict[str, object]:
    true_log = np.log1p(true)
    pred_log = np.log1p(pred)
    denom = np.sum((true_log - true_log.mean()) ** 2)
    return {
        "target": target,
        "model": model,
        "heldout_year": heldout_year,
        "rmse_log": float(np.sqrt(np.mean((true_log - pred_log) ** 2))),
        "mae_log": float(np.mean(np.abs(true_log - pred_log))),
        "r2_log": float(1 - np.sum((true_log - pred_log) ** 2) / denom) if denom > 0 else np.nan,
        "rmse_original": float(np.sqrt(np.mean((true - pred) ** 2))),
        "mae_original": float(np.mean(np.abs(true - pred))),
    }


def fold_predictions(df: pd.DataFrame, target_col: str) -> list[dict[str, object]]:
    folds = []
    for year in [2018, 2019, 2020, 2021]:
        train = df[df["date"].dt.year < year].copy()
        test = df[df["date"].dt.year == year].copy()
        if len(train) < 365 or test.empty:
            continue
        future_dates = pd.DatetimeIndex(test["date"])
        template = q3_base.seasonal_template_forecast(train, future_dates, target_col, "normal")
        stl = q3_base.stl_combination_forecast(train, future_dates, target_col, "normal")
        folds.append(
            {
                "year": year,
                "true": test[target_col].to_numpy(dtype=float),
                "template": template,
                "stl": stl,
            }
        )
    return folds


def select_template_weight(folds: list[dict[str, object]], target_col: str) -> tuple[float, pd.DataFrame]:
    rows = []
    for weight in np.linspace(0, 1, 21):
        fold_errors = []
        for fold in folds:
            true = np.asarray(fold["true"], dtype=float)
            template = np.asarray(fold["template"], dtype=float)
            stl = np.asarray(fold["stl"], dtype=float)
            pred = weight * template + (1 - weight) * stl
            fold_errors.append(float(np.sqrt(np.mean((np.log1p(true) - np.log1p(pred)) ** 2))))
        rows.append(
            {
                "target": target_col,
                "template_weight": float(weight),
                "stl_weight": float(1 - weight),
                "mean_rmse_log": float(np.mean(fold_errors)),
            }
        )
    weights = pd.DataFrame(rows)
    best = weights.sort_values(["mean_rmse_log", "template_weight"], ascending=[True, False]).iloc[0]
    return float(best["template_weight"]), weights


def validate_optimized(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    validation_rows = []
    weight_rows = []
    for target_col, _ in TARGETS:
        folds = fold_predictions(df, target_col)
        template_weight, weight_grid = select_template_weight(folds, target_col)
        weight_rows.append(weight_grid)
        for fold in folds:
            year = int(fold["year"])
            true = np.asarray(fold["true"], dtype=float)
            template = np.asarray(fold["template"], dtype=float)
            stl = np.asarray(fold["stl"], dtype=float)
            optimized = template_weight * template + (1 - template_weight) * stl
            validation_rows.append(metric_row(target_col, "seasonal_template", year, true, template))
            validation_rows.append(metric_row(target_col, "stl_residual", year, true, stl))
            validation_rows.append(metric_row(target_col, "cv_weighted_ensemble", year, true, optimized))
    detail = pd.DataFrame(validation_rows)
    summary = (
        detail.groupby(["target", "model"], as_index=False)
        .agg(
            rmse_log=("rmse_log", "mean"),
            mae_log=("mae_log", "mean"),
            r2_log=("r2_log", "mean"),
            rmse_original=("rmse_original", "mean"),
            mae_original=("mae_original", "mean"),
        )
    )
    summary.insert(2, "heldout_year", "mean")
    validation = pd.concat([detail, summary], ignore_index=True)
    return validation, pd.concat(weight_rows, ignore_index=True)


def selected_weights(weight_grid: pd.DataFrame) -> dict[str, float]:
    out: dict[str, float] = {}
    for target, group in weight_grid.groupby("target"):
        best = group.sort_values(["mean_rmse_log", "template_weight"], ascending=[True, False]).iloc[0]
        out[str(target)] = float(best["template_weight"])
    return out


def monthly_quantile_bounds(train: pd.DataFrame, target_col: str, dates: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    work = train[["date", target_col]].copy()
    work["month"] = work["date"].dt.month
    values = work[target_col].to_numpy(dtype=float)
    q10 = float(np.quantile(values, 0.10))
    q95 = float(np.quantile(values, 0.95))
    lower_map = work.groupby("month")[target_col].quantile(0.10).to_dict()
    upper_map = work.groupby("month")[target_col].quantile(0.95).to_dict()
    lower = np.asarray([float(lower_map.get(int(date.month), q10)) for date in dates], dtype=float)
    upper = np.asarray([float(upper_map.get(int(date.month), q95)) for date in dates], dtype=float)
    return lower, upper


def order_and_bound_scenarios(
    train: pd.DataFrame,
    target_col: str,
    future_dates: pd.DatetimeIndex,
    low: np.ndarray,
    normal: np.ndarray,
    high: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    monthly_low, monthly_high = monthly_quantile_bounds(train, target_col, future_dates)
    if target_col == "mean_flow_m3s":
        high_cap = np.maximum(normal * 1.35, monthly_high * 1.25)
        low_floor = monthly_low * 0.75
    else:
        high_cap = np.maximum(normal * 1.80, monthly_high * 1.60)
        low_floor = monthly_low * 0.65
    low = np.maximum(low, low_floor)
    low = np.minimum(low, normal * 0.96)
    high = np.maximum(high, normal * 1.06)
    high = np.minimum(high, high_cap)
    return low.clip(min=0), normal.clip(min=0), high.clip(min=0)


def combined_forecast(df: pd.DataFrame, weights: dict[str, float]) -> pd.DataFrame:
    future_dates = pd.date_range("2022-01-01", "2023-12-31", freq="D")
    forecasts = pd.DataFrame({"date": future_dates})
    for target_col, stem in TARGETS:
        weight = weights[target_col]
        scenario_preds: dict[str, np.ndarray] = {}
        for scenario in SCENARIOS:
            template = q3_base.seasonal_template_forecast(df, future_dates, target_col, scenario)
            stl = q3_base.stl_combination_forecast(df, future_dates, target_col, scenario)
            scenario_preds[scenario] = weight * template + (1 - weight) * stl
        low, normal, high = order_and_bound_scenarios(
            df,
            target_col,
            future_dates,
            scenario_preds["low"],
            scenario_preds["normal"],
            scenario_preds["high"],
        )
        for scenario, values in [("low", low), ("normal", normal), ("high", high)]:
            if stem == "flow":
                forecasts[f"{scenario}_pred_mean_flow_m3s"] = values
            else:
                forecasts[f"{scenario}_pred_mean_sediment_flux_kg_s"] = values
    for scenario in SCENARIOS:
        forecasts[f"{scenario}_pred_water_volume_m3"] = forecasts[f"{scenario}_pred_mean_flow_m3s"] * SECONDS_PER_DAY
        forecasts[f"{scenario}_pred_sediment_mass_kg"] = forecasts[f"{scenario}_pred_mean_sediment_flux_kg_s"] * SECONDS_PER_DAY
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


def dataframe_to_markdown(df: pd.DataFrame, floatfmt: str = ".5g") -> str:
    return q3_base.dataframe_to_markdown(df, floatfmt=floatfmt)


def write_report(
    validation: pd.DataFrame,
    weight_grid: pd.DataFrame,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    plan: pd.DataFrame,
    monthly_counts: pd.DataFrame,
) -> None:
    validation_mean = validation[validation["heldout_year"].eq("mean")].sort_values(["target", "rmse_log"])
    best_weights = (
        weight_grid.sort_values(["target", "mean_rmse_log"])
        .groupby("target", as_index=False)
        .first()[["target", "template_weight", "stl_weight", "mean_rmse_log"]]
    )
    high_risk = plan.sort_values("risk_score", ascending=False).head(20).sort_values("date")
    lines = [
        "# 问题三优化组合预测版本",
        "",
        "本版本已写入标准 `question-3` 文件夹，作为问题三当前主模型使用。模型把近期加权季节模板和 STL 趋势残差模型进行组合，组合权重由 2018-2021 年留一年交叉验证自动确定。",
        "",
        "## 模型形式",
        "",
        "对每个预测对象分别建立组合预测：",
        "",
        "`y_hat = w * y_template + (1 - w) * y_stl`",
        "",
        "其中 `w` 为近期加权季节模板权重，`1-w` 为 STL 趋势残差模型权重。水量和输沙通量分别选择权重，避免用同一个权重强行描述不同波动过程。",
        "",
        "## 权重选择",
        "",
        dataframe_to_markdown(best_weights, floatfmt=".5g"),
        "",
        "## 留一年验证比较",
        "",
        dataframe_to_markdown(validation_mean, floatfmt=".5g"),
        "",
        "## 年度预测",
        "",
        dataframe_to_markdown(annual, floatfmt=".5g"),
        "",
        "## 月度预测图",
        "",
        "![optimized forecast](../figures/forecast-monthly-flux.png)",
        "",
        dataframe_to_markdown(monthly, floatfmt=".5g"),
        "",
        "## 采样方案",
        "",
        "采样方案仍以平水情景为基础，综合预测沙通量、偏丰情景通量、通量变化率、汛期/峰值期指标和历史突变月份风险。优化版保留原来的采样逻辑，以便不同模型之间结果可比。",
        "",
        "![optimized sampling](../figures/sampling-monthly-counts.png)",
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
        "## 结论",
        "",
        "1. 优化模型继承了 STL 模型的趋势解释能力，同时利用近期加权季节模板降低验证误差。",
        "2. 权重由交叉验证确定，避免主观指定模型比例。",
        "3. 偏丰情景加入同月份历史分位数约束，减少短样本外推导致的极端值。",
        "4. 本版本比随机森林更适合作为问题三主模型；随机森林可作为机器学习对照模型保留。",
        "",
    ]
    (DOCS_DIR / "question3-analysis.md").write_text("\n".join(lines), encoding="utf-8")


def write_readme() -> None:
    lines = [
        "# question 3 optimized ensemble forecast",
        "",
        "本文件夹是问题三当前采用的主模型版本：STL 趋势残差模型与近期加权季节模板模型的交叉验证加权组合。",
        "",
        "## How to Run",
        "",
        "```powershell",
        "python .\\code\\analyze_question3.py",
        "```",
        "",
        "## Main Outputs",
        "",
        "- `code/analyze_question3.py`: 当前优化组合模型的标准运行入口。",
        "- `code/stl_base_question3.py`: 原 STL/季节模板基础函数，供当前入口复用。",
        "- `data/processed/predicted_daily_flux_2022_2023.csv`: 2022-2023 年逐日预测序列。",
        "- `results/forecast_annual_flux_2022_2023.csv`: 年度预测结果。",
        "- `results/forecast_monthly_flux_2022_2023.csv`: 月度预测结果。",
        "- `results/sampling_plan_2022_2023.csv`: 逐日采样计划。",
        "- `results/sampling_monthly_counts_2022_2023.csv`: 月度采样次数汇总。",
        "- `results/sampling_schedule_2022_2023.csv`: 具体到日期和小时的采样明细。",
        "- `results/sampling_schedule_monthly_counts_2022_2023.csv`: 按实际采样时次统计的月度次数。",
        "- `qa/forecast_validation.csv`: 基模型与组合模型留一年验证比较。",
        "- `qa/weight_selection.csv`: 组合权重网格搜索结果。",
        "- `qa/model_settings.csv`: 最终模型设置。",
        "- `figures/forecast-monthly-flux.png`: 月度水沙预测图。",
        "- `figures/sampling-monthly-counts.png`: 月度采样次数图。",
        "- `docs/question3-method.md`: 完整方法与解题过程。",
        "- `docs/question3-analysis.md`: 运行结果、验证和采样方案。",
        "- `docs/sampling-schedule-detail.md`: 按年月展开的逐次采样日期和时刻清单。",
        "",
    ]
    (Q3_OPT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_sampling_schedule_detail(schedule: pd.DataFrame) -> None:
    lines = [
        "# 问题三逐次采样时刻明细",
        "",
        "本表将采样方案细化到每一次采样的具体日期和时刻。常规采样日一天一次，高风险采样日一天三次。",
        "",
    ]
    level_name = {
        "base_regular": "常规采样",
        "flood_regular": "汛期常规采样",
        "high": "高风险加密采样",
    }
    level_reason = {
        "base_regular": "枯水期或非汛期，水沙变化较弱，固定上午采样",
        "flood_regular": "汛期常规监测，早间掌握当天水沙状态",
        "high": "高风险日早中晚跟踪，捕捉日内涨落变化",
    }
    work = schedule.sort_values("sample_datetime").copy()
    for year, year_group in work.groupby("year", sort=True):
        lines.extend([f"## {int(year)} 年", ""])
        for month, month_group in year_group.groupby("month", sort=True):
            lines.extend(
                [
                    f"### {int(month)} 月（{len(month_group)} 次）",
                    "",
                    "| 序号 | 采样日期 | 采样时刻 | 采样等级 | 定性说明 |",
                    "| ---: | --- | --- | --- | --- |",
                ]
            )
            for idx, (_, row) in enumerate(month_group.iterrows(), start=1):
                level = str(row["sampling_level"])
                lines.append(
                    f"| {idx} | {row['date']} | {row['sample_time']} | "
                    f"{level_name.get(level, level)} | {level_reason.get(level, '')} |"
                )
            lines.append("")
    (DOCS_DIR / "sampling-schedule-detail.md").write_text("\n".join(lines), encoding="utf-8")


def expand_sampling_schedule(plan: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for _, row in plan.iterrows():
        date = pd.Timestamp(row["date"])
        if row["sampling_level"] == "high":
            times = ["08:00", "14:00", "20:00"]
            reason = "high-risk flood/sediment process, three-point tracking"
        elif row["sampling_level"] == "flood_regular":
            times = ["08:00"]
            reason = "flood-season regular morning sample"
        else:
            times = ["09:00"]
            reason = "base-period regular sample"
        for sample_time in times:
            rows.append(
                {
                    "sample_datetime": f"{date.strftime('%Y-%m-%d')} {sample_time}",
                    "date": date.strftime("%Y-%m-%d"),
                    "year": int(row["year"]),
                    "month": int(row["month"]),
                    "sample_time": sample_time,
                    "sampling_level": row["sampling_level"],
                    "risk_score": row["risk_score"],
                    "pred_mean_flow_m3s": row["pred_mean_flow_m3s"],
                    "pred_mean_sediment_flux_kg_s": row["pred_mean_sediment_flux_kg_s"],
                    "change_strength": row["change_strength"],
                    "reason": reason,
                }
            )
    schedule = pd.DataFrame(rows)
    monthly = (
        schedule.groupby(["year", "month"], as_index=False)
        .agg(
            sample_times=("sample_datetime", "size"),
            high_risk_sample_times=("sampling_level", lambda s: int((s == "high").sum())),
        )
        .sort_values(["year", "month"])
    )
    return schedule, monthly


def main() -> None:
    for directory in [DATA_DIR, RESULTS_DIR, DOCS_DIR, FIGURES_DIR, QA_DIR, MODELS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
    daily = q3_base.load_daily_flux()
    validation, weight_grid = validate_optimized(daily)
    weights = selected_weights(weight_grid)
    forecasts = combined_forecast(daily, weights)
    monthly_scenarios, annual_scenarios = q3_base.aggregate_scenarios(forecasts)
    monthly = monthly_scenarios[monthly_scenarios["scenario"] == "normal"].drop(columns=["scenario"]).reset_index(drop=True)
    plan, monthly_counts = q3_base.build_sampling_plan(forecasts)
    schedule, schedule_monthly_counts = expand_sampling_schedule(plan)
    model_settings = pd.DataFrame(
        [
            {
                "model": "cv_weighted_stl_template_ensemble",
                "target": target,
                "template_weight": weights[target],
                "stl_weight": 1 - weights[target],
                "weight_selection": "grid search from 0 to 1 by leave-one-year mean log RMSE",
                "scenario_constraint": "same-month historical quantile cap for high scenario",
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
    weight_grid.to_csv(QA_DIR / "weight_selection.csv", index=False, encoding="utf-8-sig")
    model_settings.to_csv(QA_DIR / "model_settings.csv", index=False, encoding="utf-8-sig")
    q3_base.save_forecast_figure(monthly, FIGURES_DIR / "forecast-monthly-flux.png")
    q3_base.save_sampling_figure(monthly_counts, FIGURES_DIR / "sampling-monthly-counts.png")
    write_report(validation, weight_grid, annual_scenarios, monthly, plan, monthly_counts)
    write_readme()
    write_sampling_schedule_detail(schedule)

    print("Selected weights:")
    print(model_settings.to_string(index=False))
    print("\nValidation mean:")
    print(validation[validation["heldout_year"].eq("mean")].sort_values(["target", "rmse_log"]).to_string(index=False))
    print("\nAnnual forecast:")
    print(annual_scenarios.to_string(index=False))
    print("\nSampling counts by year:")
    print(plan.groupby("year").size().rename("samples").reset_index().to_string(index=False))


if __name__ == "__main__":
    main()

