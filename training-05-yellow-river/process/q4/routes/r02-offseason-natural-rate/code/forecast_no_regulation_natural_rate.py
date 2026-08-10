import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


CORE_DOMAIN = (1725.0, 2050.0)
MAIN_CHANNEL = (2005.0, 2040.0)
STEP_M = 5.0
ESTIMATION_INTERVALS = [
    ("rate_1", pd.Timestamp("2020-07-29"), pd.Timestamp("2021-04-16")),
    ("rate_2", pd.Timestamp("2021-07-22"), pd.Timestamp("2022-04-18")),
]
VALIDATION_INTERVAL = (pd.Timestamp("2022-07-23"), pd.Timestamp("2023-02-26"))
BASE_DATE = pd.Timestamp("2023-02-26")
TARGET_DATE = pd.Timestamp("2033-02-26")
ATTACHMENT2_CONTEXT_INTERVALS = [
    (pd.Timestamp("2016-10-20"), pd.Timestamp("2017-05-11")),
    (pd.Timestamp("2019-10-15"), pd.Timestamp("2020-03-19")),
]


def configure_plotting():
    available = {font.name for font in font_manager.fontManager.ttflist}
    for name in ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "#F7F8FA"
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.2


def first_valid(values):
    valid = values.dropna()
    return valid.iloc[0] if len(valid) else np.nan


def read_attachment3(path):
    raw = pd.read_excel(path)
    raw["date"] = pd.to_datetime(raw["日期"], errors="coerce").ffill()
    for column in ["起点距离(m)", "水位(m)", "水深(m)"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw["stage_m"] = raw.groupby("date")["水位(m)"].transform(first_valid)
    bed = raw.dropna(subset=["date", "起点距离(m)", "stage_m", "水深(m)"]).copy()
    bed["bed_elevation_m"] = bed["stage_m"] - bed["水深(m)"]
    bed = bed.groupby(["date", "起点距离(m)"], as_index=False).agg(
        bed_elevation_m=("bed_elevation_m", "mean")
    )
    return {
        date: frame.rename(columns={"起点距离(m)": "distance_m"}).sort_values("distance_m")
        for date, frame in bed.groupby("date")
    }


def read_attachment2(path):
    raw = pd.read_excel(path, header=None)
    profiles = {}
    for column in range(0, raw.shape[1], 2):
        date = pd.to_datetime(raw.iat[0, column], errors="coerce")
        if pd.isna(date):
            continue
        frame = pd.DataFrame({
            "distance_m": pd.to_numeric(raw.iloc[2:, column], errors="coerce"),
            "bed_elevation_m": pd.to_numeric(raw.iloc[2:, column + 1], errors="coerce"),
        }).dropna()
        profiles[date] = frame.groupby("distance_m", as_index=False)["bed_elevation_m"].mean().sort_values("distance_m")
    return profiles


def read_attachment1_daily(path):
    rows = []
    for sheet in pd.ExcelFile(path).sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet)
        raw.columns = [str(column).strip() for column in raw.columns]
        raw[["年", "月", "日"]] = raw[["年", "月", "日"]].ffill()
        raw["date"] = pd.to_datetime(dict(year=raw["年"], month=raw["月"], day=raw["日"]), errors="coerce")
        raw["discharge_m3s"] = pd.to_numeric(raw["流量(m3/s)"], errors="coerce")
        rows.append(raw[["date", "discharge_m3s"]])
    data = pd.concat(rows, ignore_index=True).dropna(subset=["date"])
    return data.groupby("date", as_index=False).agg(
        daily_mean_discharge_m3s=("discharge_m3s", "mean"),
        daily_peak_discharge_m3s=("discharge_m3s", "max"),
    )


def fit_profile(frame, grid, method):
    x = frame["distance_m"].to_numpy(float)
    z = frame["bed_elevation_m"].to_numpy(float)
    if method == "pchip":
        return PchipInterpolator(x, z, extrapolate=False)(grid)
    if method == "linear":
        return np.interp(grid, x, z)
    raise ValueError(method)


def fixed_grid(profiles, dates, domain):
    lower = max([domain[0]] + [profiles[date].distance_m.min() for date in dates])
    upper = min([domain[1]] + [profiles[date].distance_m.max() for date in dates])
    start = np.ceil(lower / STEP_M) * STEP_M
    stop = np.floor(upper / STEP_M) * STEP_M
    return np.arange(start, stop + STEP_M / 2, STEP_M)


def integrate(values, grid):
    return float(np.trapz(values, grid))


def domain_summary(change, grid, lower, upper):
    mask = (grid >= lower) & (grid <= upper)
    x, delta = grid[mask], change[mask]
    return {
        "lower_distance_m": float(x.min()),
        "upper_distance_m": float(x.max()),
        "grid_points": int(len(x)),
        "mean_change_m": float(delta.mean()),
        "net_section_change_m2": integrate(delta, x),
        "deposition_area_m2": integrate(np.maximum(delta, 0), x),
        "erosion_area_m2": integrate(np.maximum(-delta, 0), x),
        "positive_grid_fraction": float(np.mean(delta > 0)),
        "negative_grid_fraction": float(np.mean(delta < 0)),
        "max_deposition_m": float(max(0.0, delta.max())),
        "max_deposition_distance_m": float(x[np.argmax(delta)]),
        "max_erosion_m": float(max(0.0, -delta.min())),
        "max_erosion_distance_m": float(x[np.argmin(delta)]),
    }


def forecast_from_attachment3(profiles, method):
    dates = sorted({date for _, start, end in ESTIMATION_INTERVALS for date in [start, end]} | set(VALIDATION_INTERVAL) | {BASE_DATE})
    grid = fixed_grid(profiles, dates, CORE_DOMAIN)
    fitted = {date: fit_profile(profiles[date], grid, method) for date in dates}

    rate_rows = []
    increments = {}
    rates = {}
    for label, start, end in ESTIMATION_INTERVALS:
        days = (end - start).days
        increment = fitted[end] - fitted[start]
        rate = increment / days
        increments[label] = increment
        rates[label] = rate
        for x, delta, daily_rate in zip(grid, increment, rate):
            rate_rows.append({
                "method": method, "rate_source": label, "start_date": start.date(), "end_date": end.date(),
                "days": days, "distance_m": x, "natural_increment_m": delta,
                "daily_natural_rate_m_per_day": daily_rate, "annualized_rate_m_per_year": daily_rate * 365.25,
            })

    total_days = sum((end - start).days for _, start, end in ESTIMATION_INTERVALS)
    pooled_rate = sum(increments.values()) / total_days
    for x, daily_rate in zip(grid, pooled_rate):
        rate_rows.append({
            "method": method, "rate_source": "pooled", "start_date": ESTIMATION_INTERVALS[0][1].date(),
            "end_date": ESTIMATION_INTERVALS[-1][2].date(), "days": total_days, "distance_m": x,
            "natural_increment_m": daily_rate * total_days, "daily_natural_rate_m_per_day": daily_rate,
            "annualized_rate_m_per_year": daily_rate * 365.25,
        })

    val_start, val_end = VALIDATION_INTERVAL
    val_days = (val_end - val_start).days
    actual_validation = fitted[val_end] - fitted[val_start]
    predicted_validation = pooled_rate * val_days
    validation_error = predicted_validation - actual_validation
    validation = pd.DataFrame({
        "method": method, "distance_m": grid, "actual_change_m": actual_validation,
        "predicted_change_m": predicted_validation, "prediction_error_m": validation_error,
        "actual_direction": np.sign(actual_validation), "predicted_direction": np.sign(predicted_validation),
    })
    validation_summary = pd.DataFrame([{
        "method": method, "start_date": val_start.date(), "end_date": val_end.date(), "days": val_days,
        "rmse_m": float(np.sqrt(np.mean(validation_error ** 2))),
        "mae_m": float(np.mean(np.abs(validation_error))), "mean_bias_m": float(validation_error.mean()),
        "actual_net_section_change_m2": integrate(actual_validation, grid),
        "predicted_net_section_change_m2": integrate(predicted_validation, grid),
        "net_section_error_m2": integrate(validation_error, grid),
        "point_direction_agreement": float(np.mean(np.sign(actual_validation) == np.sign(predicted_validation))),
    }])

    horizon_days = (TARGET_DATE - BASE_DATE).days
    base = fitted[BASE_DATE]
    central_change = pooled_rate * horizon_days
    scenario_1_change = rates["rate_1"] * horizon_days
    scenario_2_change = rates["rate_2"] * horizon_days
    central = base + central_change
    scenario_1 = base + scenario_1_change
    scenario_2 = base + scenario_2_change
    forecast = pd.DataFrame({
        "method": method, "distance_m": grid, "base_date": BASE_DATE.date(), "target_date": TARGET_DATE.date(),
        "horizon_days": horizon_days, "base_bed_elevation_m": base, "central_daily_rate_m": pooled_rate,
        "central_bed_elevation_m": central, "central_change_m": central_change,
        "scenario_1_bed_elevation_m": scenario_1, "scenario_2_bed_elevation_m": scenario_2,
        "sensitivity_lower_bed_elevation_m": np.minimum(scenario_1, scenario_2),
        "sensitivity_upper_bed_elevation_m": np.maximum(scenario_1, scenario_2),
    })

    annual_rows = []
    for year in range(BASE_DATE.year, TARGET_DATE.year + 1):
        date = BASE_DATE.replace(year=year)
        days = (date - BASE_DATE).days
        values = base + pooled_rate * days
        for x, z in zip(grid, values):
            annual_rows.append({"method": method, "date": date.date(), "elapsed_days": days, "distance_m": x, "bed_elevation_m": z})

    summary_rows = []
    strict_domain_name = f"strict_common_{int(grid.min())}_{int(grid.max())}"
    for domain_name, bounds in [(strict_domain_name, (grid.min(), grid.max())), ("main_channel_2005_2040", MAIN_CHANNEL)]:
        metrics = domain_summary(central_change, grid, *bounds)
        if metrics["net_section_change_m2"] > 0 and metrics["positive_grid_fraction"] > 0.5:
            outcome = "net_deposition_dominant"
        elif metrics["net_section_change_m2"] < 0 and metrics["negative_grid_fraction"] > 0.5:
            outcome = "net_erosion_dominant"
        else:
            outcome = "spatially_mixed"
        s1_metrics = domain_summary(scenario_1_change, grid, *bounds)
        s2_metrics = domain_summary(scenario_2_change, grid, *bounds)
        summary_rows.append({
            "method": method, "domain": domain_name, "base_date": BASE_DATE.date(), "target_date": TARGET_DATE.date(),
            "horizon_days": horizon_days, **metrics, "dominant_outcome": outcome,
            "scenario_1_net_change_m2": s1_metrics["net_section_change_m2"],
            "scenario_2_net_change_m2": s2_metrics["net_section_change_m2"],
            "scenario_net_direction_agreement": np.sign(s1_metrics["net_section_change_m2"]) == np.sign(s2_metrics["net_section_change_m2"]),
        })
    return (
        pd.DataFrame(rate_rows), validation, validation_summary, forecast,
        pd.DataFrame(annual_rows), pd.DataFrame(summary_rows), grid,
    )


def attachment2_context(profiles):
    dates = [date for interval in ATTACHMENT2_CONTEXT_INTERVALS for date in interval]
    grid = fixed_grid(profiles, dates, CORE_DOMAIN)
    rows = []
    for start, end in ATTACHMENT2_CONTEXT_INTERVALS:
        days = (end - start).days
        pre = fit_profile(profiles[start], grid, "pchip")
        post = fit_profile(profiles[end], grid, "pchip")
        change = post - pre
        metrics = domain_summary(change, grid, *CORE_DOMAIN)
        rows.append({
            "start_date": start.date(), "end_date": end.date(), "days": days,
            "mean_daily_change_m": metrics["mean_change_m"] / days,
            "annualized_mean_change_m": metrics["mean_change_m"] / days * 365.25,
            "net_section_change_m2": metrics["net_section_change_m2"],
            "annualized_net_section_change_m2": metrics["net_section_change_m2"] / days * 365.25,
            "positive_grid_fraction": metrics["positive_grid_fraction"],
        })
    return pd.DataFrame(rows)


def attachment1_context(daily):
    rows = []
    for year, frame in daily.groupby(daily.date.dt.year):
        june_july = frame[frame.date.dt.month.isin([6, 7])]
        outside = frame[~frame.date.dt.month.isin([6, 7])]
        annual_water = 86400 * frame.daily_mean_discharge_m3s.sum()
        jj_water = 86400 * june_july.daily_mean_discharge_m3s.sum()
        rows.append({
            "year": year, "june_july_mean_discharge_m3s": june_july.daily_mean_discharge_m3s.mean(),
            "outside_mean_discharge_m3s": outside.daily_mean_discharge_m3s.mean(),
            "june_july_vs_outside_ratio": june_july.daily_mean_discharge_m3s.mean() / outside.daily_mean_discharge_m3s.mean(),
            "june_july_peak_discharge_m3s": june_july.daily_peak_discharge_m3s.max(),
            "june_july_water_billion_m3": jj_water / 1e9, "june_july_annual_water_share": jj_water / annual_water,
            "role_in_forecast": "context_only_source_not_identifiable",
        })
    return pd.DataFrame(rows)


def save_rate_figure(rates, output):
    frame = rates[rates.method == "pchip"]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    styles = {"rate_1": ("#2878B5", "2020-07-29→2021-04-16"), "rate_2": ("#D55E5E", "2021-07-22→2022-04-18"), "pooled": ("#222222", "按天合并中心率")}
    for source, (color, label) in styles.items():
        subset = frame[frame.rate_source == source]
        width = 2.4 if source == "pooled" else 1.5
        ax.plot(subset.distance_m, subset.annualized_rate_m_per_year, color=color, lw=width, label=label)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.axvspan(*MAIN_CHANNEL, color="#F2A104", alpha=0.12, label="主槽2005—2040 m")
    ax.set(title="非调度期河床自然演变率（PCHIP）", xlabel="起点距离（m）", ylabel="年化高程变化（m/年）")
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_validation_figure(validation, output):
    frame = validation[validation.method == "pchip"]
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(frame.distance_m, frame.actual_change_m, lw=2, label="实际：2022-07-23→2023-02-26")
    axes[0].plot(frame.distance_m, frame.predicted_change_m, lw=2, label="由前两段自然率预测")
    axes[0].axhline(0, color="#333333", lw=0.8)
    axes[0].set(title="218天独立验证", ylabel="河底高程变化（m）")
    axes[0].legend(frameon=False)
    axes[1].plot(frame.distance_m, frame.prediction_error_m, color="#7B3294")
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].set(xlabel="起点距离（m）", ylabel="预测−实际（m）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_forecast_figure(forecast, summary, output):
    frame = forecast[forecast.method == "pchip"]
    core = summary[(summary.method == "pchip") & (summary.domain.str.startswith("strict_common_"))].iloc[0]
    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True)
    axes[0].plot(frame.distance_m, frame.base_bed_elevation_m, color="#2878B5", lw=2.2, label="2023-02-26基准")
    axes[0].fill_between(frame.distance_m, frame.sensitivity_lower_bed_elevation_m, frame.sensitivity_upper_bed_elevation_m, color="#F2A104", alpha=0.25, label="两段自然率敏感性包络")
    axes[0].plot(frame.distance_m, frame.central_bed_elevation_m, color="#D55E5E", lw=2.2, label="2033-02-26中心预测")
    axes[0].set(title="无调水调沙简化情景的河底高程", ylabel="河底高程（m）")
    axes[0].legend(frameon=False, ncol=3)
    change = frame.central_change_m.to_numpy()
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].fill_between(frame.distance_m, 0, change, where=change >= 0, color="#D55E5E", alpha=0.75, label="淤积")
    axes[1].fill_between(frame.distance_m, 0, change, where=change < 0, color="#2878B5", alpha=0.75, label="冲刷")
    axes[1].set(title=f"十年累计变化：净断面变化{core.net_section_change_m2:+.1f} m²，正变化网格占比{core.positive_grid_fraction:.1%}", xlabel="起点距离（m）", ylabel="2033−2023（m）")
    axes[1].legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_analysis(path, summary, validation, context2, context1, sensitivity):
    core = summary[(summary.method == "pchip") & (summary.domain.str.startswith("strict_common_"))].iloc[0]
    main = summary[(summary.method == "pchip") & (summary.domain == "main_channel_2005_2040")].iloc[0]
    val = validation[validation.method == "pchip"].iloc[0]
    lin = summary[(summary.method == "linear") & (summary.domain.str.startswith("strict_common_"))].iloc[0]
    outcome_text = {
        "net_deposition_dominant": "以净淤积为主",
        "net_erosion_dominant": "以净冲刷为主",
        "spatially_mixed": "空间混合且无明显主导方向",
    }[core.dominant_outcome]
    lines = [
        "# 无调水调沙10年河底高程预测", "",
        "## 模型口径", "",
        "由于6—7月下游测站水沙无法分离天然汛期、常规下泄和专门调水调沙贡献，本模型不进行来源拆分。"
        "以两段7月末至次年4月的非调度期变化估计日均自然演变率，并把该速率延伸到全年，包括6—7月；以2023-02-26为基准递推至2033-02-26。", "",
        "## 中心预测", "",
        f"- 严格共同区{core.lower_distance_m:.0f}—{core.upper_distance_m:.0f} m：平均高程变化{core.mean_change_m:+.3f} m，净断面变化{core.net_section_change_m2:+.1f} m²，"
        f"淤积面积{core.deposition_area_m2:.1f} m²，冲刷面积{core.erosion_area_m2:.1f} m²，正变化网格占比{core.positive_grid_fraction:.1%}。",
        f"- 按预设判定规则，中心预测{outcome_text}。",
        f"- 主槽2005—2040 m：平均高程变化{main.mean_change_m:+.3f} m，净断面变化{main.net_section_change_m2:+.1f} m²。", "",
        "## 敏感性", "",
        f"- 单独延续第一段自然率，内部区十年净变化{core.scenario_1_net_change_m2:+.1f} m²；单独延续第二段自然率为{core.scenario_2_net_change_m2:+.1f} m²。",
        f"- 两情景净方向{'一致' if core.scenario_net_direction_agreement else '不一致'}；线性插值中心预测净变化为{lin.net_section_change_m2:+.1f} m²，"
        f"与PCHIP净方向{'一致' if np.sign(lin.net_section_change_m2) == np.sign(core.net_section_change_m2) else '不一致'}。", "",
        "## 独立验证", "",
        f"2022-07-23→2023-02-26的218天验证RMSE为{val.rmse_m:.3f} m，MAE为{val.mae_m:.3f} m，"
        f"实际净断面变化{val.actual_net_section_change_m2:+.1f} m²，预测{val.predicted_net_section_change_m2:+.1f} m²，逐点方向一致率{val.point_direction_agreement:.1%}。", "",
        "## 三附件证据边界", "",
        f"附件1显示2016—2021年6—7月观测流量相对其他月份的年度比值范围为{context1.june_july_vs_outside_ratio.min():.2f}—{context1.june_july_vs_outside_ratio.max():.2f}，"
        "但来源不可分，故只作为模型简化的依据，不进入自然率估计。",
        "附件2的两段非6—7月变化仅作长期背景敏感性，不并入中心率；具体数值见 `attachment2_offseason_context.csv`。", "",
        "## 解释", "",
        ("中心结果为净淤积，在本简化模型内部支持无调度后河底总体抬高。" if core.dominant_outcome == "net_deposition_dominant" else
         "中心结果为净冲刷，与‘无调度后河底必然升高’的判断相反，因此本简化模型内部不支持该判断。"),
        f"但十年最大局部变化达到{max(core.max_deposition_m, core.max_erosion_m):.2f} m，且独立验证逐点方向一致率仅{val.point_direction_agreement:.1%}，"
        "说明线性长期外推的空间高程可信度较低；当前更适合引用净方向和敏感性，而不宜把每个坐标的2033数值当作精确预言。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachment1", required=True)
    parser.add_argument("--attachment2", required=True)
    parser.add_argument("--attachment3", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    for name in ["results", "figures", "validation", "logs"]:
        (output / name).mkdir(parents=True, exist_ok=True)
    configure_plotting()

    profiles3 = read_attachment3(args.attachment3)
    profiles2 = read_attachment2(args.attachment2)
    daily1 = read_attachment1_daily(args.attachment1)
    method_outputs = {}
    for method in ["pchip", "linear"]:
        method_outputs[method] = forecast_from_attachment3(profiles3, method)

    rates = pd.concat([method_outputs[m][0] for m in method_outputs], ignore_index=True)
    validation_grid = pd.concat([method_outputs[m][1] for m in method_outputs], ignore_index=True)
    validation_summary = pd.concat([method_outputs[m][2] for m in method_outputs], ignore_index=True)
    forecast = pd.concat([method_outputs[m][3] for m in method_outputs], ignore_index=True)
    annual = pd.concat([method_outputs[m][4] for m in method_outputs], ignore_index=True)
    summary = pd.concat([method_outputs[m][5] for m in method_outputs], ignore_index=True)
    context2 = attachment2_context(profiles2)
    context1 = attachment1_context(daily1)

    results = output / "results"
    validation = output / "validation"
    rates.to_csv(results / "natural_rate_grid.csv", index=False, encoding="utf-8-sig")
    forecast.to_csv(results / "forecast_2033_grid.csv", index=False, encoding="utf-8-sig")
    annual.to_csv(results / "annual_forecast_grid.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(results / "forecast_summary.csv", index=False, encoding="utf-8-sig")
    context1.to_csv(results / "attachment1_water_flux_context.csv", index=False, encoding="utf-8-sig")
    context2.to_csv(results / "attachment2_offseason_context.csv", index=False, encoding="utf-8-sig")
    validation_grid.to_csv(validation / "independent_validation_grid.csv", index=False, encoding="utf-8-sig")
    validation_summary.to_csv(validation / "independent_validation_summary.csv", index=False, encoding="utf-8-sig")

    save_rate_figure(rates, output / "figures" / "natural_rate_profiles.png")
    save_validation_figure(validation_grid, output / "figures" / "independent_validation.png")
    save_forecast_figure(forecast, summary, output / "figures" / "forecast_2023_2033.png")
    write_analysis(results / "analysis.md", summary, validation_summary, context2, context1, None)

    core = summary[summary.domain.str.startswith("strict_common_")]
    checks = pd.DataFrame([
        {"check": "estimation_days_are_261_and_270", "passed": [int((end-start).days) for _, start, end in ESTIMATION_INTERVALS] == [261, 270], "value": "261,270"},
        {"check": "validation_days_are_218", "passed": (VALIDATION_INTERVAL[1] - VALIDATION_INTERVAL[0]).days == 218, "value": 218},
        {"check": "forecast_days_are_3653", "passed": (TARGET_DATE - BASE_DATE).days == 3653, "value": (TARGET_DATE - BASE_DATE).days},
        {"check": "no_spatial_extrapolation_or_nan", "passed": forecast.select_dtypes(include=[np.number]).notna().all().all(), "value": "strict common core"},
        {"check": "both_estimation_intervals_present", "passed": set(rates.rate_source.unique()) == {"rate_1", "rate_2", "pooled"}, "value": rates.rate_source.nunique()},
        {"check": "pchip_linear_central_direction_agree", "passed": np.sign(core.iloc[0].net_section_change_m2) == np.sign(core.iloc[1].net_section_change_m2), "value": core.net_section_change_m2.tolist()},
        {"check": "three_attachments_used", "passed": len(context1) == 6 and len(context2) == 2 and len(forecast) > 0, "value": "a1_context,a2_context,a3_model"},
    ])
    checks.to_csv(validation / "quality_checks.csv", index=False, encoding="utf-8-sig")
    log_lines = [
        f"Quality checks passed: {checks.passed.sum()}/{len(checks)}",
        f"PCHIP core net change: {core[core.method == 'pchip'].iloc[0].net_section_change_m2:+.4f} m2",
        f"PCHIP core positive fraction: {core[core.method == 'pchip'].iloc[0].positive_grid_fraction:.4f}",
        f"PCHIP dominant outcome: {core[core.method == 'pchip'].iloc[0].dominant_outcome}",
    ]
    (output / "logs" / "run_summary.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    if not checks.passed.all():
        raise RuntimeError("One or more quality checks failed")


if __name__ == "__main__":
    main()
