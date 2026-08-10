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
HORIZON_YEARS = 10
INTERVALS = [
    ("g1", pd.Timestamp("2016-10-20"), pd.Timestamp("2017-05-11")),
    ("g2", pd.Timestamp("2018-09-13"), pd.Timestamp("2019-04-13")),
    ("g3", pd.Timestamp("2019-10-15"), pd.Timestamp("2020-03-19")),
    ("g4", pd.Timestamp("2020-03-19"), pd.Timestamp("2021-03-14")),
]
SCENARIOS = {
    "raw_interval": [1.0, 1.5, 2.0, 3.0],
    "annualized": [2.5, 3.0, 4.0, 5.0],
}
CENTRAL_MODEL = "annualized"
CENTRAL_SHIFT = 3.0


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


def gm11(sequence, shift, horizon):
    sequence = np.asarray(sequence, dtype=float)
    shifted = sequence + shift
    if np.any(shifted <= 0):
        raise ValueError("GM(1,1) requires a strictly positive shifted sequence")
    accumulated = np.cumsum(shifted)
    background = 0.5 * (accumulated[1:] + accumulated[:-1])
    design = np.column_stack([-background, np.ones(len(background))])
    a, b = np.linalg.lstsq(design, shifted[1:], rcond=None)[0]
    total = len(sequence) + horizon
    response = np.empty(total, dtype=float)
    if abs(a) < 1e-12:
        response = shifted[0] + b * np.arange(total)
    else:
        k = np.arange(total, dtype=float)
        response = (shifted[0] - b / a) * np.exp(-a * k) + b / a
    restored_shifted = np.empty(total, dtype=float)
    restored_shifted[0] = response[0]
    restored_shifted[1:] = np.diff(response)
    restored = restored_shifted - shift
    lower = np.exp(-2.0 / (len(sequence) + 1))
    upper = np.exp(2.0 / (len(sequence) + 1))
    ratios = shifted[:-1] / shifted[1:]
    return {
        "a": float(a),
        "b": float(b),
        "fitted": restored[: len(sequence)],
        "future": restored[len(sequence) :],
        "level_ratio_pass": bool(np.all((ratios > lower) & (ratios < upper))),
    }


def build_inputs(profiles2, grid):
    raw_columns = []
    interval_rows = []
    for label, start, end in INTERVALS:
        days = int((end - start).days)
        delta = fit_profile(profiles2[end], grid) - fit_profile(profiles2[start], grid)
        raw_columns.append(delta)
        for x, value in zip(grid, delta):
            interval_rows.append(
                {
                    "interval": label,
                    "start_date": start.date(),
                    "end_date": end.date(),
                    "days": days,
                    "distance_m": x,
                    "raw_change_m": value,
                    "annualized_change_m_per_year": value * 365.25 / days,
                }
            )
    raw = np.column_stack(raw_columns)
    days = np.array([(end - start).days for _, start, end in INTERVALS], dtype=float)
    annualized = raw * 365.25 / days
    return {"raw_interval": raw, "annualized": annualized}, pd.DataFrame(interval_rows)


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
        "maximum_change_m": float(values.max()),
        "dominant_outcome": outcome,
    }


def run_scenario(model_name, inputs, shift, base, grid):
    if np.any(inputs + shift <= 0):
        return None, {
            "model": model_name,
            "shift": shift,
            "status": "invalid_nonpositive_shifted_input",
            "minimum_shifted_input": float(np.min(inputs + shift)),
        }, None
    forecasts = []
    fitted = []
    a_values = []
    ratio_pass = []
    for sequence in inputs:
        result = gm11(sequence, shift, HORIZON_YEARS)
        forecasts.append(result["future"])
        fitted.append(result["fitted"])
        a_values.append(result["a"])
        ratio_pass.append(result["level_ratio_pass"])
    forecasts = np.asarray(forecasts)
    fitted = np.asarray(fitted)
    a_values = np.asarray(a_values)
    cumulative_change = forecasts.sum(axis=1)
    final = base + cumulative_change
    grid_rows = []
    annual_rows = []
    for i, x in enumerate(grid):
        grid_rows.append(
            {
                "model": model_name,
                "shift": shift,
                "distance_m": x,
                "base_bed_elevation_m": base[i],
                "forecast_2033_bed_elevation_m": final[i],
                "ten_year_change_m": cumulative_change[i],
                "development_coefficient_a": a_values[i],
                "abs_a_lt_0_3": abs(a_values[i]) < 0.3,
                "level_ratio_pass": ratio_pass[i],
                "in_sample_mae": float(np.mean(np.abs(fitted[i] - inputs[i]))),
            }
        )
        running = 0.0
        annual_rows.append(
            {
                "model": model_name,
                "shift": shift,
                "year": 2023,
                "distance_m": x,
                "annual_change_m": 0.0,
                "cumulative_change_m": 0.0,
                "bed_elevation_m": base[i],
            }
        )
        for year_index, annual_change in enumerate(forecasts[i], start=1):
            running += annual_change
            annual_rows.append(
                {
                    "model": model_name,
                    "shift": shift,
                    "year": 2023 + year_index,
                    "distance_m": x,
                    "annual_change_m": annual_change,
                    "cumulative_change_m": running,
                    "bed_elevation_m": base[i] + running,
                }
            )
    historical_scale = np.maximum(np.max(np.abs(inputs), axis=1) * HORIZON_YEARS, 1e-9)
    diagnostics = {
        "model": model_name,
        "shift": shift,
        "status": "completed",
        "minimum_shifted_input": float(np.min(inputs + shift)),
        "level_ratio_pass_fraction": float(np.mean(ratio_pass)),
        "abs_a_lt_0_3_fraction": float(np.mean(np.abs(a_values) < 0.3)),
        "median_abs_a": float(np.median(np.abs(a_values))),
        "maximum_abs_a": float(np.max(np.abs(a_values))),
        "mean_in_sample_mae": float(np.mean(np.abs(fitted - inputs))),
        "median_forecast_to_historical_scale_ratio": float(
            np.median(np.abs(cumulative_change) / historical_scale)
        ),
        "maximum_abs_ten_year_change_m": float(np.max(np.abs(cumulative_change))),
    }
    return pd.DataFrame(grid_rows), diagnostics, pd.DataFrame(annual_rows)


def hindcast_fourth(model_name, inputs, shift, grid):
    if np.any(inputs[:, :3] + shift <= 0):
        return {
            "model": model_name,
            "shift": shift,
            "status": "invalid_nonpositive_shifted_input",
        }, None
    predicted = []
    for sequence in inputs[:, :3]:
        predicted.append(gm11(sequence, shift, 1)["future"][0])
    predicted = np.asarray(predicted)
    actual = inputs[:, 3]
    error = predicted - actual
    rows = pd.DataFrame(
        {
            "model": model_name,
            "shift": shift,
            "distance_m": grid,
            "actual_fourth_change": actual,
            "predicted_fourth_change": predicted,
            "prediction_error": error,
        }
    )
    summary = {
        "model": model_name,
        "shift": shift,
        "status": "completed",
        "rmse_m": float(np.sqrt(np.mean(error**2))),
        "mae_m": float(np.mean(np.abs(error))),
        "actual_net_section_change_m2": integrate(actual, grid),
        "predicted_net_section_change_m2": integrate(predicted, grid),
        "net_section_error_m2": integrate(error, grid),
        "point_direction_agreement": float(np.mean(np.sign(actual) == np.sign(predicted))),
    }
    return summary, rows


def save_input_figure(intervals, output):
    fig, ax = plt.subplots(figsize=(12, 6.5))
    labels = {
        "g1": "2016-10-20→2017-05-11",
        "g2": "2018-09-13→2019-04-13",
        "g3": "2019-10-15→2020-03-19",
        "g4": "2020-03-19→2021-03-14",
    }
    for label, frame in intervals.groupby("interval"):
        ax.plot(
            frame.distance_m,
            frame.annualized_change_m_per_year,
            lw=1.8,
            label=labels[label],
        )
    ax.axhline(0, color="#333333", lw=0.8)
    ax.axvspan(*MAIN_CHANNEL, color="#F2A104", alpha=0.12, label="主槽2005—2040 m")
    ax.set(
        title="GM(1,1)输入：四段年化河底高程变化",
        xlabel="起点距离（m）",
        ylabel="年化高程变化（m/年）",
    )
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_forecast_figure(grid_results, output):
    central = grid_results[
        (grid_results.model == CENTRAL_MODEL) & (grid_results["shift"] == CENTRAL_SHIFT)
    ]
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 8.5), sharex=True)
    axes[0].plot(
        central.distance_m,
        central.base_bed_elevation_m,
        lw=2.2,
        label="2023-02-26基准",
    )
    axes[0].plot(
        central.distance_m,
        central.forecast_2033_bed_elevation_m,
        lw=2.2,
        label="2033 GM(1,1)预测",
    )
    axes[0].set(title="年化GM(1,1)中心情景", ylabel="河底高程（m）")
    axes[0].legend(frameon=False)
    values = central.ten_year_change_m.to_numpy()
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].fill_between(
        central.distance_m, 0, values, where=values >= 0, color="#D55E5E", alpha=0.75, label="淤积"
    )
    axes[1].fill_between(
        central.distance_m, 0, values, where=values < 0, color="#2878B5", alpha=0.75, label="冲刷"
    )
    axes[1].set(xlabel="起点距离（m）", ylabel="2033−2023（m）")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_sensitivity_figure(summary, output):
    frame = summary[summary.domain.str.startswith("strict_common_")].copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    for model, group in frame.groupby("model"):
        ax.plot(group["shift"], group.net_section_change_m2, marker="o", lw=2, label=model)
    ax.axhline(0, color="#333333", lw=0.8)
    ax.set(
        title="GM(1,1)平移常数敏感性",
        xlabel="平移常数",
        ylabel="十年净断面变化（m²）",
    )
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_analysis(path, summary, diagnostics, hindcast):
    central = summary[
        (summary.model == CENTRAL_MODEL)
        & (summary["shift"] == CENTRAL_SHIFT)
        & summary.domain.str.startswith("strict_common_")
    ].iloc[0]
    central_diag = diagnostics[
        (diagnostics.model == CENTRAL_MODEL) & (diagnostics["shift"] == CENTRAL_SHIFT)
    ].iloc[0]
    central_val = hindcast[
        (hindcast.model == CENTRAL_MODEL) & (hindcast["shift"] == CENTRAL_SHIFT)
    ].iloc[0]
    annual_core = summary[
        (summary.model == "annualized") & summary.domain.str.startswith("strict_common_")
    ].sort_values("shift")
    raw_core = summary[
        (summary.model == "raw_interval") & summary.domain.str.startswith("strict_common_")
    ].sort_values("shift")
    lines = [
        "# GM(1,1)无调水调沙十年预测",
        "",
        "## 中心结果",
        "",
        f"年化修正GM(1,1)取平移常数3 m/年，在{central.lower_distance_m:.0f}—{central.upper_distance_m:.0f} m共同区预测十年平均高程变化{central.mean_change_m:+.2f} m，净断面变化{central.net_section_change_m2:+.1f} m²，正变化网格占比{central.positive_grid_fraction:.1%}，判定为 `{central.dominant_outcome}`。",
        "",
        "## 稳定性诊断",
        "",
        f"中心情景只有{central_diag.abs_a_lt_0_3_fraction:.1%}的坐标满足|a|<0.3的中长期适用经验条件，级比检验通过率为{central_diag.level_ratio_pass_fraction:.1%}；最大局部十年变化达到{central_diag.maximum_abs_ten_year_change_m:.1f} m。",
        f"用前三项预测第四项的回测RMSE为{central_val.rmse_m:.3f} m/年，MAE为{central_val.mae_m:.3f} m/年，逐点方向一致率为{central_val.point_direction_agreement:.1%}；实际与预测净断面变化分别为{central_val.actual_net_section_change_m2:+.1f}和{central_val.predicted_net_section_change_m2:+.1f} m²。",
        "",
        "## 平移常数敏感性",
        "",
        "年化模型各可行情景的净断面变化为："
        + "；".join(
            f"c={row.shift:g}: {row.net_section_change_m2:+.1f} m²"
            for row in annual_core.itertuples()
        )
        + "。",
        "原文式未年化模型各可行情景的净断面变化为："
        + "；".join(
            f"c={row.shift:g}: {row.net_section_change_m2:+.1f} m²"
            for row in raw_core.itertuples()
        )
        + "。固定c=1因部分坐标平移后仍非正而不能覆盖完整断面。",
        "",
        "## 结论",
        "",
        "GM(1,1)的可行情景总体给出净淤积方向，与恒定自然速率模型的净冲刷方向相反；因此冲淤结论明显依赖预测模型。与此同时，十年幅度远超历史变化尺度且对平移常数高度敏感，说明该4项序列不满足可靠长期灰色外推的条件。GM结果可以作为论文中的敏感性/对照结果，但不宜直接把逐点2033高程作为可信主预测。",
        "",
        "第四输入段2020-03-19至2021-03-14跨过6—7月，天然汛期和调水调沙贡献无法分离，这也是该路线不能被解释为纯自然演变预测的重要限制。",
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
    input_sets, interval_frame = build_inputs(profiles2, grid)

    grid_frames = []
    annual_frames = []
    diagnostic_rows = []
    hindcast_rows = []
    hindcast_grid_frames = []
    summary_rows = []
    for model_name, shifts in SCENARIOS.items():
        for shift in shifts:
            grid_result, diagnostic, annual = run_scenario(
                model_name, input_sets[model_name], shift, base, grid
            )
            diagnostic_rows.append(diagnostic)
            hindcast_summary, hindcast_grid = hindcast_fourth(
                model_name, input_sets[model_name], shift, grid
            )
            hindcast_rows.append(hindcast_summary)
            if hindcast_grid is not None:
                hindcast_grid_frames.append(hindcast_grid)
            if grid_result is None:
                continue
            grid_frames.append(grid_result)
            annual_frames.append(annual)
            change = grid_result.ten_year_change_m.to_numpy()
            for domain_name, bounds in [
                (f"strict_common_{int(grid.min())}_{int(grid.max())}", (grid.min(), grid.max())),
                ("main_channel_2005_2040", MAIN_CHANNEL),
            ]:
                summary_rows.append(
                    {
                        "model": model_name,
                        "shift": shift,
                        "domain": domain_name,
                        "base_date": BASE_DATE.date(),
                        "target_date": TARGET_DATE.date(),
                        **domain_metrics(change, grid, *bounds),
                    }
                )

    grid_results = pd.concat(grid_frames, ignore_index=True)
    annual_results = pd.concat(annual_frames, ignore_index=True)
    diagnostics = pd.DataFrame(diagnostic_rows)
    hindcast_summary = pd.DataFrame(hindcast_rows)
    hindcast_grid = pd.concat(hindcast_grid_frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows)

    interval_frame.to_csv(
        output / "results" / "gm11_input_intervals.csv", index=False, encoding="utf-8-sig"
    )
    grid_results.to_csv(
        output / "results" / "gm11_forecast_2033_grid.csv", index=False, encoding="utf-8-sig"
    )
    annual_results.to_csv(
        output / "results" / "gm11_annual_forecast_grid.csv", index=False, encoding="utf-8-sig"
    )
    summary.to_csv(
        output / "results" / "gm11_forecast_summary.csv", index=False, encoding="utf-8-sig"
    )
    attachment1.to_csv(
        output / "results" / "attachment1_water_context.csv", index=False, encoding="utf-8-sig"
    )
    diagnostics.to_csv(
        output / "validation" / "gm11_diagnostics.csv", index=False, encoding="utf-8-sig"
    )
    hindcast_summary.to_csv(
        output / "validation" / "gm11_hindcast_summary.csv", index=False, encoding="utf-8-sig"
    )
    hindcast_grid.to_csv(
        output / "validation" / "gm11_hindcast_grid.csv", index=False, encoding="utf-8-sig"
    )

    save_input_figure(interval_frame, output / "figures" / "gm11_input_profiles.png")
    save_forecast_figure(grid_results, output / "figures" / "gm11_forecast_2023_2033.png")
    save_sensitivity_figure(summary, output / "figures" / "gm11_shift_sensitivity.png")
    write_analysis(output / "results" / "analysis.md", summary, diagnostics, hindcast_summary)

    central = summary[
        (summary.model == CENTRAL_MODEL)
        & (summary["shift"] == CENTRAL_SHIFT)
        & summary.domain.str.startswith("strict_common_")
    ].iloc[0]
    checks = pd.DataFrame(
        [
            {"check": "strict_grid_is_1820_2050", "passed": grid.min() == 1820 and grid.max() == 2050, "value": f"{grid.min():.0f}-{grid.max():.0f}"},
            {"check": "four_input_intervals", "passed": len(INTERVALS) == 4, "value": len(INTERVALS)},
            {"check": "interval_days_match", "passed": [int((b-a).days) for _, a, b in INTERVALS] == [203, 212, 156, 360], "value": "203,212,156,360"},
            {"check": "central_scenario_completed", "passed": len(central) > 0, "value": CENTRAL_SHIFT},
            {"check": "paper_shift_one_flagged_invalid", "passed": diagnostics[(diagnostics.model == "raw_interval") & (diagnostics["shift"] == 1.0)].status.iloc[0] == "invalid_nonpositive_shifted_input", "value": diagnostics[(diagnostics.model == "raw_interval") & (diagnostics["shift"] == 1.0)].minimum_shifted_input.iloc[0]},
            {"check": "three_attachments_used", "passed": len(attachment1) == 6 and len(interval_frame) > 0 and len(base) > 0, "value": "a1_context,a2_model,a3_base"},
            {"check": "all_numeric_outputs_finite", "passed": np.isfinite(grid_results.select_dtypes(include=[np.number])).all().all(), "value": len(grid_results)},
        ]
    )
    checks.to_csv(output / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")
    log = [
        f"Quality checks passed: {int(checks.passed.sum())}/{len(checks)}",
        f"Central net section change: {central.net_section_change_m2:+.4f} m2",
        f"Central mean elevation change: {central.mean_change_m:+.4f} m",
        f"Central dominant outcome: {central.dominant_outcome}",
    ]
    (output / "logs" / "run_summary.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    if not checks.passed.all():
        raise RuntimeError("One or more quality checks failed")


if __name__ == "__main__":
    main()
