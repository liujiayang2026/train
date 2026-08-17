import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


DOMAIN = (1725.0, 2050.0)
MAIN_CHANNEL = (2005.0, 2040.0)
STEP_M = 5.0
BASE_DATE = pd.Timestamp("2023-02-26")
TARGET_DATE = pd.Timestamp("2033-02-26")
HORIZON_YEARS = 10.0
TAU_VALUES = [5.0, 10.0, 20.0]
CENTRAL_TAU = 10.0
INTERVALS = [
    ("g1", pd.Timestamp("2016-10-20"), pd.Timestamp("2017-05-11")),
    ("g2", pd.Timestamp("2018-09-13"), pd.Timestamp("2019-04-13")),
    ("g3", pd.Timestamp("2019-10-15"), pd.Timestamp("2020-03-19")),
    ("g4", pd.Timestamp("2020-03-19"), pd.Timestamp("2021-03-14")),
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
    values = values.dropna()
    return values.iloc[0] if len(values) else np.nan


def read_attachment2(path):
    raw = pd.read_excel(path, header=None)
    profiles = {}
    for column in range(0, raw.shape[1], 2):
        date = pd.to_datetime(raw.iat[0, column], errors="coerce")
        if pd.isna(date):
            continue
        frame = pd.DataFrame(
            {
                "distance_m": pd.to_numeric(raw.iloc[2:, column], errors="coerce"),
                "bed_elevation_m": pd.to_numeric(raw.iloc[2:, column + 1], errors="coerce"),
            }
        ).dropna()
        profiles[date] = (
            frame.groupby("distance_m", as_index=False)["bed_elevation_m"]
            .mean()
            .sort_values("distance_m")
        )
    return profiles


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


def read_attachment1_context(path):
    rows = []
    for sheet in pd.ExcelFile(path).sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet)
        raw.columns = [str(column).strip() for column in raw.columns]
        raw[["年", "月", "日"]] = raw[["年", "月", "日"]].ffill()
        raw["date"] = pd.to_datetime(
            dict(year=raw["年"], month=raw["月"], day=raw["日"]), errors="coerce"
        )
        raw["discharge_m3s"] = pd.to_numeric(raw["流量(m3/s)"], errors="coerce")
        rows.append(raw[["date", "discharge_m3s"]])
    daily = pd.concat(rows, ignore_index=True).dropna(subset=["date", "discharge_m3s"])
    daily = daily.groupby("date", as_index=False).discharge_m3s.mean()
    result = []
    for year, frame in daily.groupby(daily.date.dt.year):
        jj = frame[frame.date.dt.month.isin([6, 7])]
        other = frame[~frame.date.dt.month.isin([6, 7])]
        result.append(
            {
                "year": int(year),
                "june_july_mean_discharge_m3s": float(jj.discharge_m3s.mean()),
                "outside_mean_discharge_m3s": float(other.discharge_m3s.mean()),
                "june_july_vs_outside_ratio": float(
                    jj.discharge_m3s.mean() / other.discharge_m3s.mean()
                ),
                "role": "context_only_source_not_identifiable",
            }
        )
    return pd.DataFrame(result)


def fit_profile(frame, grid):
    return PchipInterpolator(
        frame.distance_m.to_numpy(float),
        frame.bed_elevation_m.to_numpy(float),
        extrapolate=False,
    )(grid)


def strict_grid(profiles2, profiles3):
    dates = {date for _, start, end in INTERVALS for date in (start, end)}
    frames = [profiles2[date] for date in dates] + [profiles3[BASE_DATE]]
    lower = max([DOMAIN[0]] + [float(frame.distance_m.min()) for frame in frames])
    upper = min([DOMAIN[1]] + [float(frame.distance_m.max()) for frame in frames])
    start = np.ceil(lower / STEP_M) * STEP_M
    stop = np.floor(upper / STEP_M) * STEP_M
    return np.arange(start, stop + STEP_M / 2, STEP_M)


def integrate(values, grid):
    return float(np.trapz(values, grid))


def build_annualized_rates(profiles2, grid):
    rows = []
    rate_profiles = []
    for label, start, end in INTERVALS:
        days = int((end - start).days)
        change = fit_profile(profiles2[end], grid) - fit_profile(profiles2[start], grid)
        annualized = change * 365.25 / days
        rate_profiles.append(annualized)
        for x, raw_value, annual_value in zip(grid, change, annualized):
            rows.append(
                {
                    "interval": label,
                    "start_date": start.date(),
                    "end_date": end.date(),
                    "days": days,
                    "distance_m": x,
                    "raw_change_m": raw_value,
                    "annualized_change_m_per_year": annual_value,
                }
            )
    rates = np.asarray(rate_profiles)
    net_rates = np.asarray([integrate(profile, grid) for profile in rates])
    return rates, net_rates, pd.DataFrame(rows)


def zero_integral_template(rates, net_rates, grid):
    length = float(grid[-1] - grid[0])
    demeaned = rates - (net_rates / length)[:, None]
    template = np.median(demeaned, axis=0)
    template -= integrate(template, grid) / length
    return template


def scenario_net_rates(net_rates):
    positive = np.sort(net_rates[net_rates > 0])
    if len(positive) < 3:
        raise ValueError("At least three positive net-aggradation observations are required")
    return {
        "low": float(positive.min()),
        "central": float(np.median(positive)),
        "high": float(positive.max()),
    }


def cumulative_factor(years, tau):
    return float(tau * (1.0 - np.exp(-years / tau)))


def domain_metrics(change, grid, lower, upper):
    mask = (grid >= lower) & (grid <= upper)
    x = grid[mask]
    values = change[mask]
    net = integrate(values, x)
    positive = float(np.mean(values > 0))
    negative = float(np.mean(values < 0))
    if net > 0 and positive > 0.5:
        outcome = "net_deposition_dominant"
    elif net < 0 and negative > 0.5:
        outcome = "net_erosion_dominant"
    else:
        outcome = "spatially_mixed"
    return {
        "lower_distance_m": float(x.min()),
        "upper_distance_m": float(x.max()),
        "grid_points": int(len(x)),
        "mean_change_m": float(values.mean()),
        "net_section_change_m2": net,
        "deposition_area_m2": integrate(np.maximum(values, 0), x),
        "erosion_area_m2": integrate(np.maximum(-values, 0), x),
        "positive_grid_fraction": positive,
        "negative_grid_fraction": negative,
        "minimum_change_m": float(values.min()),
        "minimum_change_distance_m": float(x[np.argmin(values)]),
        "maximum_change_m": float(values.max()),
        "maximum_change_distance_m": float(x[np.argmax(values)]),
        "dominant_outcome": outcome,
    }


def run_scenarios(template, net_scenarios, base, grid):
    length = float(grid[-1] - grid[0])
    forecast_rows = []
    annual_rows = []
    summary_rows = []
    for level, net_rate in net_scenarios.items():
        initial_rate = template + net_rate / length
        for tau in TAU_VALUES:
            factor = cumulative_factor(HORIZON_YEARS, tau)
            change = initial_rate * factor
            forecast = base + change
            for x, z0, r0, delta, z10 in zip(grid, base, initial_rate, change, forecast):
                forecast_rows.append(
                    {
                        "scenario": level,
                        "tau_years": tau,
                        "distance_m": x,
                        "base_bed_elevation_m": z0,
                        "initial_change_rate_m_per_year": r0,
                        "ten_year_change_m": delta,
                        "forecast_2033_bed_elevation_m": z10,
                    }
                )
                for elapsed in range(0, 11):
                    elapsed_factor = cumulative_factor(float(elapsed), tau)
                    annual_rows.append(
                        {
                            "scenario": level,
                            "tau_years": tau,
                            "year": 2023 + elapsed,
                            "distance_m": x,
                            "cumulative_change_m": r0 * elapsed_factor,
                            "bed_elevation_m": z0 + r0 * elapsed_factor,
                        }
                    )
            for domain_name, bounds in [
                (f"strict_common_{int(grid.min())}_{int(grid.max())}", (grid.min(), grid.max())),
                ("main_channel_2005_2040", MAIN_CHANNEL),
            ]:
                summary_rows.append(
                    {
                        "scenario": level,
                        "initial_net_aggradation_rate_m2_per_year": net_rate,
                        "tau_years": tau,
                        "effective_linear_years": factor,
                        "domain": domain_name,
                        "base_date": BASE_DATE.date(),
                        "target_date": TARGET_DATE.date(),
                        **domain_metrics(change, grid, *bounds),
                    }
                )
    return (
        pd.DataFrame(forecast_rows),
        pd.DataFrame(annual_rows),
        pd.DataFrame(summary_rows),
    )


def validate_spatial_template(rates, net_rates, grid):
    rows = []
    grid_rows = []
    positive_indices = np.where(net_rates > 0)[0]
    length = float(grid[-1] - grid[0])
    for holdout in positive_indices:
        keep = np.asarray([i for i in range(len(rates)) if i != holdout])
        template = zero_integral_template(rates[keep], net_rates[keep], grid)
        predicted = template + net_rates[holdout] / length
        actual = rates[holdout]
        error = predicted - actual
        rows.append(
            {
                "holdout_interval": INTERVALS[holdout][0],
                "actual_net_rate_m2_per_year": net_rates[holdout],
                "predicted_net_rate_m2_per_year": integrate(predicted, grid),
                "rmse_m_per_year": float(np.sqrt(np.mean(error**2))),
                "mae_m_per_year": float(np.mean(np.abs(error))),
                "point_direction_agreement": float(
                    np.mean(np.sign(predicted) == np.sign(actual))
                ),
            }
        )
        for x, actual_value, predicted_value, error_value in zip(
            grid, actual, predicted, error
        ):
            grid_rows.append(
                {
                    "holdout_interval": INTERVALS[holdout][0],
                    "distance_m": x,
                    "actual_rate_m_per_year": actual_value,
                    "predicted_rate_m_per_year": predicted_value,
                    "error_m_per_year": error_value,
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(grid_rows)


def save_observed_rates_figure(intervals, net_rates, output):
    fig, axes = plt.subplots(2, 1, figsize=(12, 9))
    labels = {
        "g1": "2016-10-20→2017-05-11",
        "g2": "2018-09-13→2019-04-13",
        "g3": "2019-10-15→2020-03-19",
        "g4": "2020-03-19→2021-03-14",
    }
    for label, frame in intervals.groupby("interval"):
        axes[0].plot(
            frame.distance_m,
            frame.annualized_change_m_per_year,
            lw=1.8,
            label=labels[label],
        )
    axes[0].axhline(0, color="#333333", lw=0.8)
    axes[0].set(title="四段年化河床变化", ylabel="高程变化率（m/年）")
    axes[0].legend(frameon=False, ncol=2)
    colors = ["#D55E5E" if value > 0 else "#2878B5" for value in net_rates]
    axes[1].bar(["g1", "g2", "g3", "g4"], net_rates, color=colors)
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].set(
        xlabel="观测时段",
        ylabel="净断面年变化（m²/年）",
        title="净淤积率情景的数据来源",
    )
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_forecast_figure(forecast, output):
    central = forecast[
        (forecast.scenario == "central") & (forecast.tau_years == CENTRAL_TAU)
    ]
    low = forecast[(forecast.scenario == "low") & (forecast.tau_years == CENTRAL_TAU)]
    high = forecast[(forecast.scenario == "high") & (forecast.tau_years == CENTRAL_TAU)]
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 9), sharex=True)
    axes[0].plot(
        central.distance_m,
        central.base_bed_elevation_m,
        lw=2.2,
        label="2023-02-26基准",
    )
    axes[0].fill_between(
        central.distance_m,
        low.forecast_2033_bed_elevation_m,
        high.forecast_2033_bed_elevation_m,
        color="#F2A104",
        alpha=0.25,
        label="低—高净淤积情景",
    )
    axes[0].plot(
        central.distance_m,
        central.forecast_2033_bed_elevation_m,
        color="#D55E5E",
        lw=2.2,
        label="2033中心预测",
    )
    axes[0].set(title="有界趋稳净淤积模型", ylabel="河底高程（m）")
    axes[0].legend(frameon=False, ncol=3)
    values = central.ten_year_change_m.to_numpy()
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].fill_between(
        central.distance_m,
        0,
        values,
        where=values >= 0,
        color="#D55E5E",
        alpha=0.75,
        label="淤积",
    )
    axes[1].fill_between(
        central.distance_m,
        0,
        values,
        where=values < 0,
        color="#2878B5",
        alpha=0.75,
        label="局部冲刷",
    )
    axes[1].set(
        xlabel="起点距离（m）", ylabel="2033−2023（m）", title="中心情景十年累计变化"
    )
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_sensitivity_figure(summary, output):
    frame = summary[summary.domain.str.startswith("strict_common_")]
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = {"low": "#2878B5", "central": "#D55E5E", "high": "#F2A104"}
    for scenario, group in frame.groupby("scenario"):
        group = group.sort_values("tau_years")
        ax.plot(
            group.tau_years,
            group.net_section_change_m2,
            marker="o",
            lw=2,
            color=colors[scenario],
            label=scenario,
        )
    ax.set(
        title="净淤积率与形态调整时间常数敏感性",
        xlabel="时间常数τ（年）",
        ylabel="十年净断面变化（m²）",
    )
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_annual_growth_figure(annual, output):
    rows = []
    for (scenario, tau, year), frame in annual.groupby(
        ["scenario", "tau_years", "year"]
    ):
        frame = frame.sort_values("distance_m")
        rows.append(
            {
                "scenario": scenario,
                "tau_years": tau,
                "year": year,
                "net_section_change_m2": integrate(
                    frame.cumulative_change_m.to_numpy(),
                    frame.distance_m.to_numpy(),
                ),
                "mean_elevation_change_m": float(frame.cumulative_change_m.mean()),
            }
        )
    growth = pd.DataFrame(rows)
    fig, axes = plt.subplots(2, 1, figsize=(11, 9), sharex=True)
    colors = {"low": "#2878B5", "central": "#D55E5E", "high": "#F2A104"}
    labels = {"low": "低情景", "central": "中心情景", "high": "高情景"}
    for scenario in ["low", "central", "high"]:
        frame = growth[
            (growth.scenario == scenario) & (growth.tau_years == CENTRAL_TAU)
        ].sort_values("year")
        axes[0].plot(
            frame.year,
            frame.net_section_change_m2,
            marker="o",
            lw=2.2,
            color=colors[scenario],
            label=labels[scenario],
        )
    axes[0].set(
        title="不同净淤积率情景的逐年累计变化（τ=10年）",
        ylabel="累计净断面变化（m²）",
    )
    axes[0].legend(frameon=False, ncol=3)
    tau_colors = {5.0: "#2878B5", 10.0: "#D55E5E", 20.0: "#7B3294"}
    for tau in TAU_VALUES:
        frame = growth[
            (growth.scenario == "central") & (growth.tau_years == tau)
        ].sort_values("year")
        axes[1].plot(
            frame.year,
            frame.mean_elevation_change_m,
            marker="o",
            lw=2.2,
            color=tau_colors[tau],
            label=f"τ={tau:g}年",
        )
    axes[1].set(
        title="中心情景在不同趋稳速度下的逐年平均抬高",
        xlabel="年份",
        ylabel="断面平均高程变化（m）",
    )
    axes[1].legend(frameon=False, ncol=3)
    axes[1].set_xticks(range(2023, 2034))
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_analysis(path, summary, net_rates, template_validation):
    core = summary[
        (summary.scenario == "central")
        & (summary.tau_years == CENTRAL_TAU)
        & summary.domain.str.startswith("strict_common_")
    ].iloc[0]
    main = summary[
        (summary.scenario == "central")
        & (summary.tau_years == CENTRAL_TAU)
        & (summary.domain == "main_channel_2005_2040")
    ].iloc[0]
    central_tau = summary[
        (summary.tau_years == CENTRAL_TAU)
        & summary.domain.str.startswith("strict_common_")
    ].sort_values("initial_net_aggradation_rate_m2_per_year")
    central_rate = summary[
        (summary.scenario == "central")
        & summary.domain.str.startswith("strict_common_")
    ].sort_values("tau_years")
    lines = [
        "# 有界趋稳净淤积模型结果",
        "",
        "## 思路",
        "",
        "无调水调沙时的工程机理先验被写成“整个断面十年净变化为正”，而不是强迫每个坐标都抬高。附件2四段年化变化先分解为断面净变化和零积分局部形态；三个净淤积时段的净断面年变化构成低、中、高情景。河床变化速率按指数衰减，使累计变化随时间趋于上界。附件3提供2023基准断面，附件1只用于说明6—7月水量来源不可分。",
        "",
        "## 中心预测",
        "",
        f"三个正净变化样本为{', '.join(f'{value:+.1f}' for value in sorted(net_rates[net_rates > 0]))} m²/年；中心初始净淤积率取其中位数{core.initial_net_aggradation_rate_m2_per_year:.1f} m²/年，时间常数取10年。",
        f"1820—2050 m共同区十年净断面变化为{core.net_section_change_m2:+.1f} m²，平均河底高程变化{core.mean_change_m:+.3f} m，淤积面积{core.deposition_area_m2:.1f} m²、冲刷面积{core.erosion_area_m2:.1f} m²，正变化网格占比{core.positive_grid_fraction:.1%}。局部变化范围为{core.minimum_change_m:+.3f}至{core.maximum_change_m:+.3f} m。",
        f"主槽2005—2040 m净断面变化为{main.net_section_change_m2:+.1f} m²，平均变化{main.mean_change_m:+.3f} m。",
        "",
        "## 敏感性",
        "",
        "时间常数10年时，低—中—高净淤积情景的十年净断面变化为："
        + "；".join(
            f"{row.scenario} {row.net_section_change_m2:+.1f} m²"
            for row in central_tau.itertuples()
        )
        + "。",
        "中心净淤积率下，τ=5、10、20年对应："
        + "；".join(
            f"τ={row.tau_years:g}: {row.net_section_change_m2:+.1f} m²"
            for row in central_rate.itertuples()
        )
        + "。",
        "",
        "## 空间形态检验",
        "",
        f"对三个正净变化时段做留一法空间形态检验，平均RMSE为{template_validation.rmse_m_per_year.mean():.3f} m/年，平均MAE为{template_validation.mae_m_per_year.mean():.3f} m/年，平均逐点方向一致率为{template_validation.point_direction_agreement.mean():.1%}。该检验只评价局部形态分配，不验证无工程反事实的净淤积方向。",
        "",
        "## 解释",
        "",
        "中心情景预测断面总体抬高但保留少量局部冲刷，符合河段净淤积与主槽调整可以同时存在的水沙机理。与GM(1,1)相比，结果保持在米级且随时间趋稳，不发生指数爆炸。由于净淤积方向是工程机理约束、真实无工程样本不存在，论文应称其为条件反事实预测，并同时报告低—高情景，不能写成无条件精确预言。",
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
    for folder in ["results", "figures", "validation", "logs"]:
        (output / folder).mkdir(parents=True, exist_ok=True)
    configure_plotting()

    profiles2 = read_attachment2(args.attachment2)
    profiles3 = read_attachment3(args.attachment3)
    attachment1 = read_attachment1_context(args.attachment1)
    grid = strict_grid(profiles2, profiles3)
    base = fit_profile(profiles3[BASE_DATE], grid)
    rates, net_rates, intervals = build_annualized_rates(profiles2, grid)
    template = zero_integral_template(rates, net_rates, grid)
    net_scenarios = scenario_net_rates(net_rates)
    forecast, annual, summary = run_scenarios(template, net_scenarios, base, grid)
    template_validation, template_validation_grid = validate_spatial_template(
        rates, net_rates, grid
    )

    interval_summary = pd.DataFrame(
        [
            {
                "interval": label,
                "start_date": start.date(),
                "end_date": end.date(),
                "days": int((end - start).days),
                "annualized_net_section_change_m2_per_year": net_rates[index],
                "used_as_positive_aggradation_scenario": bool(net_rates[index] > 0),
            }
            for index, (label, start, end) in enumerate(INTERVALS)
        ]
    )
    template_frame = pd.DataFrame(
        {"distance_m": grid, "zero_integral_spatial_template_m_per_year": template}
    )
    results = output / "results"
    validation = output / "validation"
    intervals.to_csv(results / "annualized_input_profiles.csv", index=False, encoding="utf-8-sig")
    interval_summary.to_csv(results / "input_interval_summary.csv", index=False, encoding="utf-8-sig")
    template_frame.to_csv(results / "spatial_template.csv", index=False, encoding="utf-8-sig")
    forecast.to_csv(results / "bounded_forecast_2033_grid.csv", index=False, encoding="utf-8-sig")
    annual.to_csv(results / "bounded_annual_forecast_grid.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(results / "bounded_forecast_summary.csv", index=False, encoding="utf-8-sig")
    attachment1.to_csv(results / "attachment1_water_context.csv", index=False, encoding="utf-8-sig")
    template_validation.to_csv(validation / "spatial_template_loo_summary.csv", index=False, encoding="utf-8-sig")
    template_validation_grid.to_csv(validation / "spatial_template_loo_grid.csv", index=False, encoding="utf-8-sig")

    save_observed_rates_figure(intervals, net_rates, output / "figures" / "observed_annualized_rates.png")
    save_forecast_figure(forecast, output / "figures" / "bounded_forecast_2023_2033.png")
    save_sensitivity_figure(summary, output / "figures" / "bounded_sensitivity.png")
    save_annual_growth_figure(annual, output / "figures" / "bounded_annual_growth.png")
    write_analysis(results / "analysis.md", summary, net_rates, template_validation)

    central = summary[
        (summary.scenario == "central")
        & (summary.tau_years == CENTRAL_TAU)
        & summary.domain.str.startswith("strict_common_")
    ].iloc[0]
    length = grid[-1] - grid[0]
    expected_central_net = net_scenarios["central"] * cumulative_factor(
        HORIZON_YEARS, CENTRAL_TAU
    )
    checks = pd.DataFrame(
        [
            {"check": "strict_grid_is_1820_2050", "passed": grid.min() == 1820 and grid.max() == 2050, "value": f"{grid.min():.0f}-{grid.max():.0f}"},
            {"check": "four_input_intervals", "passed": len(INTERVALS) == 4, "value": len(INTERVALS)},
            {"check": "three_positive_net_observations", "passed": int(np.sum(net_rates > 0)) == 3, "value": int(np.sum(net_rates > 0))},
            {"check": "spatial_template_zero_integral", "passed": abs(integrate(template, grid)) < 1e-9, "value": integrate(template, grid)},
            {"check": "central_net_matches_closed_form", "passed": abs(central.net_section_change_m2 - expected_central_net) < 1e-8, "value": central.net_section_change_m2},
            {"check": "central_net_aggradation_positive", "passed": central.net_section_change_m2 > 0, "value": central.net_section_change_m2},
            {"check": "bounded_factor_less_than_linear_horizon", "passed": all(cumulative_factor(HORIZON_YEARS, tau) < HORIZON_YEARS for tau in TAU_VALUES), "value": ",".join(f"{cumulative_factor(HORIZON_YEARS,tau):.3f}" for tau in TAU_VALUES)},
            {"check": "all_numeric_outputs_finite", "passed": np.isfinite(forecast.select_dtypes(include=[np.number])).all().all(), "value": len(forecast)},
            {"check": "three_attachments_used", "passed": len(attachment1) == 6 and len(intervals) > 0 and len(base) > 0, "value": "a1_context,a2_model,a3_base"},
        ]
    )
    checks.to_csv(validation / "quality_checks.csv", index=False, encoding="utf-8-sig")
    log = [
        f"Quality checks passed: {int(checks.passed.sum())}/{len(checks)}",
        f"Domain length: {length:.1f} m",
        f"Central initial net aggradation rate: {net_scenarios['central']:+.4f} m2/year",
        f"Central net ten-year change: {central.net_section_change_m2:+.4f} m2",
        f"Central mean ten-year elevation change: {central.mean_change_m:+.4f} m",
        f"Central dominant outcome: {central.dominant_outcome}",
    ]
    (output / "logs" / "run_summary.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    if not checks.passed.all():
        raise RuntimeError("One or more quality checks failed")


if __name__ == "__main__":
    main()
