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
WINDOWS = {
    2016: ("attachment2", "2016-06-08", "attachment2", "2016-10-20", "B"),
    2017: ("attachment2", "2017-05-11", "attachment2", "2017-09-05", "B"),
    2018: ("attachment3", "2018-04-04", "attachment2", "2018-09-13", "C"),
    2019: ("attachment2", "2019-04-13", "attachment2", "2019-10-15", "B"),
    2020: ("attachment3", "2020-04-17", "attachment3", "2020-07-29", "A"),
    2021: ("attachment3", "2021-04-16", "attachment3", "2021-07-22", "A"),
    2022: ("attachment3", "2022-04-18", "attachment3", "2022-07-23", "A*"),
}
JULY_WINDOWS = {
    2020: ("2020-07-10", "2020-07-29"),
    2021: ("2021-07-07", "2021-07-22"),
    2022: ("2022-07-07", "2022-07-23"),
}


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


def read_attachment1(path):
    rows = []
    for sheet in pd.ExcelFile(path).sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet)
        raw.columns = [str(column).strip() for column in raw.columns]
        required = {"年", "月", "日", "流量(m3/s)", "含沙量(kg/m3)"}
        if not required.issubset(raw.columns):
            continue
        raw[["年", "月", "日"]] = raw[["年", "月", "日"]].ffill()
        raw["date"] = pd.to_datetime(
            dict(year=raw["年"], month=raw["月"], day=raw["日"]), errors="coerce"
        )
        raw["discharge_m3s"] = pd.to_numeric(raw["流量(m3/s)"], errors="coerce")
        raw["sediment_kgm3"] = pd.to_numeric(raw["含沙量(kg/m3)"], errors="coerce")
        rows.append(raw[["date", "discharge_m3s", "sediment_kgm3"]])
    data = pd.concat(rows, ignore_index=True).dropna(subset=["date"])
    return data.groupby("date", as_index=False).agg(
        daily_mean_discharge_m3s=("discharge_m3s", "mean"),
        daily_max_discharge_m3s=("discharge_m3s", "max"),
        discharge_observations=("discharge_m3s", "count"),
        daily_mean_sediment_kgm3=("sediment_kgm3", "mean"),
        sediment_observations=("sediment_kgm3", "count"),
    )


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
    numeric = ["起点距离(m)", "水位(m)", "水深(m)", "测点水深(m)", "测点水流速(m/s)"]
    for column in numeric:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw["vertical_distance_m"] = raw.groupby("date")["起点距离(m)"].ffill()
    raw["vertical_depth_m"] = raw.groupby(["date", "vertical_distance_m"], dropna=False)["水深(m)"].transform(first_valid)
    raw["section_stage_m"] = raw.groupby("date")["水位(m)"].transform(first_valid)

    bed = raw.dropna(subset=["date", "起点距离(m)", "section_stage_m", "水深(m)"]).copy()
    bed["bed_elevation_m"] = bed["section_stage_m"] - bed["水深(m)"]
    bed = bed.groupby(["date", "起点距离(m)"], as_index=False).agg(bed_elevation_m=("bed_elevation_m", "mean"))
    profiles = {
        date: frame.rename(columns={"起点距离(m)": "distance_m"}).sort_values("distance_m")
        for date, frame in bed.groupby("date")
    }

    points = raw.dropna(subset=["date", "vertical_distance_m", "测点水流速(m/s)"]).copy()
    verticals = points.groupby(["date", "vertical_distance_m"], as_index=False).agg(
        mean_velocity_mps=("测点水流速(m/s)", "mean"),
        total_depth_m=("vertical_depth_m", "first"),
        velocity_points=("测点水流速(m/s)", "size"),
    )
    return profiles, verticals


def fit_profile(frame, grid, method="pchip"):
    x = frame["distance_m"].to_numpy(float)
    z = frame["bed_elevation_m"].to_numpy(float)
    if method == "pchip":
        return PchipInterpolator(x, z, extrapolate=False)(grid)
    if method == "linear":
        return np.interp(grid, x, z)
    raise ValueError(method)


def common_grid(first, second, domain=None):
    lower = max(first.distance_m.min(), second.distance_m.min())
    upper = min(first.distance_m.max(), second.distance_m.max())
    if domain is not None:
        lower, upper = max(lower, domain[0]), min(upper, domain[1])
    start = np.ceil(lower / STEP_M) * STEP_M
    stop = np.floor(upper / STEP_M) * STEP_M
    if stop <= start:
        return np.array([])
    return np.arange(start, stop + STEP_M / 2, STEP_M)


def calibration_metrics(a2, a3):
    date2, date3 = pd.Timestamp("2019-04-13"), pd.Timestamp("2019-04-17")
    first, second = a2[date2], a3[date3]
    grid = common_grid(first, second)
    z2, z3 = fit_profile(first, grid), fit_profile(second, grid)
    error = z3 - z2
    offset = float(error.mean())
    corrected = error - offset
    summary = pd.DataFrame(
        [{
            "attachment2_date": date2.date(),
            "attachment3_date": date3.date(),
            "lower_distance_m": grid.min(),
            "upper_distance_m": grid.max(),
            "grid_points": len(grid),
            "mean_bias_a3_minus_a2_m": offset,
            "raw_rmse_m": np.sqrt(np.mean(error ** 2)),
            "bias_corrected_rmse_m": np.sqrt(np.mean(corrected ** 2)),
            "raw_median_absolute_error_m": np.median(np.abs(error)),
            "bias_corrected_median_absolute_error_m": np.median(np.abs(corrected)),
            "raw_integrated_difference_m2": np.trapz(error, grid),
            "bias_corrected_integrated_difference_m2": np.trapz(corrected, grid),
            "passes_1m_rmse_rule": np.sqrt(np.mean(corrected ** 2)) <= 1.0,
        }]
    )
    detail = pd.DataFrame({
        "distance_m": grid,
        "attachment2_bed_m": z2,
        "attachment3_bed_m": z3,
        "raw_difference_m": error,
        "bias_corrected_difference_m": corrected,
    })
    return offset, summary, detail


def profile_metrics(grid, pre, post):
    delta = post - pre
    return {
        "lower_distance_m": grid.min(),
        "upper_distance_m": grid.max(),
        "grid_points": len(grid),
        "net_section_change_m2": np.trapz(delta, grid),
        "erosion_area_m2": np.trapz(np.maximum(-delta, 0), grid),
        "deposition_area_m2": np.trapz(np.maximum(delta, 0), grid),
        "mean_bed_change_m": delta.mean(),
        "max_erosion_m": max(0.0, -delta.min()),
        "max_erosion_distance_m": grid[np.argmin(delta)],
        "max_deposition_m": max(0.0, delta.max()),
        "max_deposition_distance_m": grid[np.argmax(delta)],
        "conveyance_area_change_proxy_m2": -np.trapz(delta, grid),
    }


def evaluate_bed_windows(a2, a3, cross_offset):
    profile_sets = {"attachment2": a2, "attachment3": a3}
    summary_rows, detail_rows, sensitivity_rows = [], [], []
    for year, (pre_source, pre_text, post_source, post_text, grade) in WINDOWS.items():
        pre_date, post_date = pd.Timestamp(pre_text), pd.Timestamp(post_text)
        pre_frame = profile_sets[pre_source][pre_date]
        post_frame = profile_sets[post_source][post_date]
        for domain_name, domain in [("full_common", None), ("interior_1725_2050", CORE_DOMAIN), ("main_channel_2005_2040", MAIN_CHANNEL)]:
            grid = common_grid(pre_frame, post_frame, domain)
            if not len(grid):
                continue
            values = {}
            for method in ["pchip", "linear"]:
                pre = fit_profile(pre_frame, grid, method)
                post = fit_profile(post_frame, grid, method)
                if year == 2018:
                    pre = pre - cross_offset
                values[method] = (pre, post)
                metrics = profile_metrics(grid, pre, post)
                sensitivity_rows.append({"year": year, "domain": domain_name, "method": method, **metrics})
            pre, post = values["pchip"]
            metrics = profile_metrics(grid, pre, post)
            summary_rows.append({
                "year": year,
                "evidence_grade": grade,
                "pre_source": pre_source,
                "post_source": post_source,
                "pre_date": pre_date.date(),
                "post_date": post_date.date(),
                "window_days": (post_date - pre_date).days,
                "domain": domain_name,
                "cross_attachment_bias_correction_m": cross_offset if year == 2018 else 0.0,
                **metrics,
            })
            for x, before, after in zip(grid, pre, post):
                detail_rows.append({
                    "year": year, "evidence_grade": grade, "domain": domain_name,
                    "pre_date": pre_date.date(), "post_date": post_date.date(),
                    "distance_m": x, "pre_bed_elevation_m": before,
                    "post_bed_elevation_m": after, "bed_change_m": after - before,
                })
    summary = pd.DataFrame(summary_rows)
    sensitivity = pd.DataFrame(sensitivity_rows)
    pivot = sensitivity.pivot_table(index=["year", "domain"], columns="method", values="net_section_change_m2").reset_index()
    pivot["pchip_minus_linear_net_m2"] = pivot["pchip"] - pivot["linear"]
    pivot["same_net_direction"] = np.sign(pivot["pchip"]) == np.sign(pivot["linear"])
    return summary, pd.DataFrame(detail_rows), sensitivity, pivot


def evaluate_july_windows(a3):
    rows = []
    for year, (pre_text, post_text) in JULY_WINDOWS.items():
        pre_date, post_date = pd.Timestamp(pre_text), pd.Timestamp(post_text)
        pre_frame, post_frame = a3[pre_date], a3[post_date]
        for domain_name, domain in [("full_common", None), ("interior_1725_2050", CORE_DOMAIN), ("main_channel_2005_2040", MAIN_CHANNEL)]:
            grid = common_grid(pre_frame, post_frame, domain)
            pre, post = fit_profile(pre_frame, grid), fit_profile(post_frame, grid)
            rows.append({
                "year": year, "evidence_grade": "A" if year < 2022 else "A*",
                "pre_date": pre_date.date(), "post_date": post_date.date(),
                "window_days": (post_date - pre_date).days, "domain": domain_name,
                **profile_metrics(grid, pre, post),
            })
    return pd.DataFrame(rows)


def longest_missing_run(mask):
    longest = current = 0
    for missing in mask:
        current = current + 1 if missing else 0
        longest = max(longest, current)
    return longest


def summarize_hydrosediment(daily):
    rows, processed = [], []
    for year in range(2016, 2022):
        calendar = pd.DataFrame({"date": pd.date_range(f"{year}-06-01", f"{year}-07-31", freq="D")})
        frame = calendar.merge(daily[daily.date.dt.year == year], on="date", how="left")
        observed = frame["daily_mean_sediment_kgm3"].notna()
        frame["sediment_interpolated_kgm3"] = frame["daily_mean_sediment_kgm3"].interpolate(
            method="linear", limit_area="inside"
        )
        valid = frame["daily_mean_discharge_m3s"].notna() & frame["sediment_interpolated_kgm3"].notna()
        observed_mass = 86400 * (frame.loc[observed, "daily_mean_discharge_m3s"] * frame.loc[observed, "daily_mean_sediment_kgm3"]).sum()
        interpolated_mass = 86400 * (frame.loc[valid, "daily_mean_discharge_m3s"] * frame.loc[valid, "sediment_interpolated_kgm3"]).sum()
        water = 86400 * frame["daily_mean_discharge_m3s"].sum()
        rows.append({
            "year": year,
            "window_days": len(frame),
            "discharge_observed_days": frame["daily_mean_discharge_m3s"].notna().sum(),
            "mean_discharge_m3s": frame["daily_mean_discharge_m3s"].mean(),
            "peak_daily_discharge_m3s": frame["daily_max_discharge_m3s"].max(),
            "cumulative_water_billion_m3": water / 1e9,
            "sediment_observed_days": observed.sum(),
            "sediment_observed_day_coverage": observed.mean(),
            "subdaily_sediment_sampling_fraction": frame["sediment_observations"].sum() / frame["discharge_observations"].sum(),
            "sediment_interpolated_day_coverage": valid.mean(),
            "longest_sediment_missing_run_days": longest_missing_run(~observed.to_numpy()),
            "observed_day_sediment_mass_million_t": observed_mass / 1e9,
            "interpolated_sediment_mass_million_t": interpolated_mass / 1e9,
            "interpolated_unit_water_sediment_kgm3": interpolated_mass / water if water > 0 else np.nan,
        })
        frame["year"] = year
        processed.append(frame)
    result = pd.DataFrame(rows)
    result["sediment_process_class"] = pd.qcut(
        result["interpolated_sediment_mass_million_t"], 3, labels=["相对弱", "中等", "相对强"]
    ).astype(str)
    return result, pd.concat(processed, ignore_index=True)


def representative_widths(x):
    x = np.asarray(x, dtype=float)
    widths = np.empty(len(x))
    widths[0], widths[-1] = (x[1] - x[0]) / 2, (x[-1] - x[-2]) / 2
    if len(x) > 2:
        widths[1:-1] = (x[2:] - x[:-2]) / 2
    return widths


def summarize_velocity(verticals):
    rows = []
    for date, frame in verticals.groupby("date"):
        frame = frame.dropna(subset=["mean_velocity_mps", "total_depth_m"]).query("total_depth_m > 0").sort_values("vertical_distance_m").copy()
        if len(frame) < 2:
            continue
        frame["width_m"] = representative_widths(frame["vertical_distance_m"])
        weights = frame["width_m"] * frame["total_depth_m"]
        rows.append({
            "date": date, "year": date.year, "month": date.month,
            "vertical_count": len(frame), "velocity_point_count": int(frame.velocity_points.sum()),
            "area_weighted_velocity_mps": np.average(frame.mean_velocity_mps, weights=weights),
        })
    sections = pd.DataFrame(rows).sort_values("date")
    comparisons = []
    for year in [2020, 2021, 2022]:
        frame = sections[sections.year == year]
        april = frame[frame.month == 4].iloc[0]
        july = frame[frame.month == 7].sort_values("date")
        first, last = july.iloc[0], july.iloc[-1]
        comparisons.append({
            "year": year, "april_date": april.date.date(), "july_first_date": first.date.date(), "july_last_date": last.date.date(),
            "april_velocity_mps": april.area_weighted_velocity_mps,
            "july_first_velocity_mps": first.area_weighted_velocity_mps,
            "july_last_velocity_mps": last.area_weighted_velocity_mps,
            "april_to_july_last_change_pct": 100 * (last.area_weighted_velocity_mps / april.area_weighted_velocity_mps - 1),
            "july_first_to_last_change_pct": 100 * (last.area_weighted_velocity_mps / first.area_weighted_velocity_mps - 1),
        })
    return sections, pd.DataFrame(comparisons)


def build_target_matrix(bed, july_bed, hydro, velocity, calibration):
    core = bed[bed.domain == "interior_1725_2050"].set_index("year")
    july_core = july_bed[july_bed.domain == "interior_1725_2050"].set_index("year")
    hydro = hydro.set_index("year")
    velocity = velocity.set_index("year")
    rows = []
    for year in range(2016, 2024):
        if year == 2023:
            rows.append({
                "year": year, "evidence_grade": "不可评价", "hydrodynamic_evidence": "缺少6—7月后断面测次",
                "sediment_process": "附件1无数据", "local_bed_response": "不可评价", "local_goal_judgement": "不可评价",
                "limitation": "附件3仅有2023-02-26测次",
            })
            continue
        row = core.loc[year]
        net = row.net_section_change_m2
        if year in velocity.index:
            velocity_change = velocity.loc[year, "april_to_july_last_change_pct"]
            dynamic = f"4月→7月末面积加权流速{velocity_change:+.1f}%：水动力明确增强" if velocity_change > 0 else f"4月→7月末面积加权流速{velocity_change:+.1f}%"
        elif year in hydro.index:
            dynamic = f"6—7月平均流量{hydro.loc[year, 'mean_discharge_m3s']:.0f} m³/s、峰值{hydro.loc[year, 'peak_daily_discharge_m3s']:.0f} m³/s；缺流速前后对照"
        else:
            dynamic = "附件1无数据"
        if year in hydro.index:
            sediment = (f"{hydro.loc[year, 'sediment_process_class']}；日均估计累计过沙{hydro.loc[year, 'interpolated_sediment_mass_million_t']:.2f} Mt"
                        f"（逐日覆盖{hydro.loc[year, 'sediment_observed_day_coverage']:.0%}，日内记录采样率{hydro.loc[year, 'subdaily_sediment_sampling_fraction']:.0%}）")
        else:
            sediment = "附件1无数据，过沙过程不可观测"
        bed_text = f"宽窗口净{'冲刷' if net < 0 else '淤积'} {abs(net):.1f} m²"
        if str(row.evidence_grade).startswith("A"):
            july_net = july_core.loc[year, "net_section_change_m2"]
            bed_text = (f"4月→7月末净{'冲刷' if net < 0 else '淤积'} {abs(net):.1f} m²；"
                        f"7月首→末净{'冲刷' if july_net < 0 else '淤积'} {abs(july_net):.1f} m²")
            if net < 0 and july_net < 0:
                judgement = "该断面两个观测窗口内均形成净冲刷"
            elif net >= 0 and july_net < 0:
                judgement = "7月高频观测期内形成净冲刷，但4月至7月累计仍为净淤积"
            else:
                judgement = "该断面观测窗口内未形成净冲刷，表现为净淤积"
        else:
            judgement = f"宽窗口阶段性净{'冲刷' if net < 0 else '淤积'}；不能单独归因于工程"
        limitation = "同源精细前后测次" if row.evidence_grade in ["A", "A*"] else "宽时间窗，含季节混杂"
        if year == 2018:
            passed = bool(calibration.iloc[0].passes_1m_rmse_rule)
            bed_text = f"1965—2050 m共同区净{'冲刷' if net < 0 else '淤积'} {abs(net):.1f} m²"
            limitation = f"仅覆盖内部稳健区中的1965—2050 m；跨附件偏差校准；校准后RMSE={calibration.iloc[0].bias_corrected_rmse_m:.2f} m；{'通过' if passed else '未通过'}1 m规则"
            if not passed:
                judgement = "仅定性参考，不据数值判定工程达成"
        if year == 2022:
            limitation += "；附件1缺失"
        rows.append({
            "year": year, "evidence_grade": row.evidence_grade, "hydrodynamic_evidence": dynamic,
            "sediment_process": sediment, "local_bed_response": bed_text,
            "local_goal_judgement": judgement, "limitation": limitation,
        })
    return pd.DataFrame(rows)


def save_calibration_figure(detail, output):
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(detail.distance_m, detail.attachment2_bed_m, lw=2, label="附件2：2019-04-13")
    axes[0].plot(detail.distance_m, detail.attachment3_bed_m, lw=2, label="附件3：2019-04-17")
    axes[0].set(ylabel="河底高程（m）", title="跨附件近同期断面对齐校验")
    axes[0].legend(frameon=False)
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].plot(detail.distance_m, detail.raw_difference_m, label="原始差值")
    axes[1].plot(detail.distance_m, detail.bias_corrected_difference_m, label="去均值偏差后")
    axes[1].set(xlabel="起点距离（m）", ylabel="附件3−附件2（m）")
    axes[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_bed_figure(detail, output):
    data = detail[detail.domain == "interior_1725_2050"]
    years = sorted(data.year.unique())
    fig, axes = plt.subplots(4, 2, figsize=(14, 13), sharex=True)
    for ax, year in zip(axes.flat, years):
        frame = data[data.year == year]
        ax.axhline(0, color="#333333", lw=0.8)
        ax.fill_between(frame.distance_m, 0, frame.bed_change_m, where=frame.bed_change_m < 0, color="#2878B5", alpha=0.75, label="冲刷")
        ax.fill_between(frame.distance_m, 0, frame.bed_change_m, where=frame.bed_change_m >= 0, color="#D55E5E", alpha=0.75, label="淤积")
        ax.set(title=f"{year}年（{frame.evidence_grade.iloc[0]}级）", ylabel="后−前（m）")
    axes.flat[-1].axis("off")
    for ax in axes[-1, :1]:
        ax.set_xlabel("起点距离（m）")
    fig.suptitle("2016—2022年含调水调沙季的本断面河床变化（PCHIP）", fontsize=16, y=0.995)
    fig.text(0.5, 0.973, "蓝色为冲刷，红色为淤积；2018年严格共同覆盖仅1965—2050 m", ha="center", fontsize=10, color="#555555")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_summary_figure(bed, july_bed, hydro, velocity, output):
    core = bed[bed.domain == "interior_1725_2050"].sort_values("year")
    july_core = july_bed[july_bed.domain == "interior_1725_2050"].sort_values("year")
    fig, axes = plt.subplots(3, 1, figsize=(12, 12))
    colors = ["#2878B5" if value < 0 else "#D55E5E" for value in core.net_section_change_m2]
    axes[0].bar(core.year, core.net_section_change_m2, color=colors)
    axes[0].scatter(july_core.year, july_core.net_section_change_m2, color="#222222", marker="D", s=50, zorder=3, label="7月首测→末测（A级年份）")
    axes[0].axhline(0, color="#333333", lw=0.8)
    axes[0].set(title="严格共同覆盖区净断面变化（负值为冲刷；2018仅1965—2050 m）", ylabel="净变化（m²）")
    axes[0].legend(frameon=False)
    axes[1].bar(hydro.year, hydro.interpolated_sediment_mass_million_t, color="#C68E17")
    axes[1].set(title="附件1：6—7月日均估计累计过沙量", ylabel="百万吨（Mt）")
    axes[2].bar(velocity.year, velocity.april_to_july_last_change_pct, color="#009E73")
    axes[2].axhline(0, color="#333333", lw=0.8)
    axes[2].set(title="附件3：4月到7月末断面面积加权流速变化", xlabel="年份", ylabel="变化率（%）")
    fig.suptitle("单测站可观测的调水调沙目标指标", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def write_analysis(path, calibration, bed, july_bed, hydro, velocity, matrix, sensitivity):
    core = bed[bed.domain == "interior_1725_2050"].sort_values("year")
    july_core = july_bed[july_bed.domain == "interior_1725_2050"].set_index("year")
    lines = [
        "# 2016—2023年调水调沙实际效果的分级评价", "",
        "## 跨附件校验", "",
        f"2019年近同期断面去除平均高程偏差后RMSE为{calibration.iloc[0].bias_corrected_rmse_m:.3f} m，"
        f"1 m规则判定为{'通过' if calibration.iloc[0].passes_1m_rmse_rule else '未通过'}。"
        "因此2018年仅按C级跨附件证据解释，并同时保留其校准限制。", "",
        "## 本断面河床结果", "",
    ]
    for row in core.itertuples():
        extra = ""
        if row.year in july_core.index:
            event = july_core.loc[row.year]
            extra = f"；7月首末测次净变化{event.net_section_change_m2:+.1f} m²"
        if row.year == 2018:
            extra += "；该数值仅对应1965—2050 m共同覆盖区，不能与其余年份按面积大小直接比较"
        lines.append(f"- {row.year}年（{row.evidence_grade}级，{row.pre_date}→{row.post_date}）：内部稳健区净变化{row.net_section_change_m2:+.1f} m²，"
                     f"表现为{'冲刷' if row.net_section_change_m2 < 0 else '淤积'}；过流面积代理变化{row.conveyance_area_change_proxy_m2:+.1f} m²{extra}。")
    lines += ["", "PCHIP与分段线性在7个年度内部稳健区的净冲淤方向一致率为"
              f"{sensitivity[sensitivity.domain == 'interior_1725_2050'].same_net_direction.mean():.0%}。", "",
              "## 水沙和流速", ""]
    for row in hydro.itertuples():
        lines.append(f"- {row.year}年6—7月：平均流量{row.mean_discharge_m3s:.0f} m³/s，峰值{row.peak_daily_discharge_m3s:.0f} m³/s，"
                     f"日均估计累计过沙量{row.interpolated_sediment_mass_million_t:.2f} Mt，含沙逐日覆盖率{row.sediment_observed_day_coverage:.1%}，"
                     f"含沙量相对流量记录的日内采样率{row.subdaily_sediment_sampling_fraction:.1%}。")
    for row in velocity.itertuples():
        lines.append(f"- {row.year}年4月→7月末面积加权流速变化{row.april_to_july_last_change_pct:+.1f}%。")
    lines += ["", "## 评价结论", "",
              "国家调水调沙目标是多目标体系。本题单测站能够确认2020—2022年水动力均明显增强，但本断面减淤响应不稳定。"
              "其中2022年7月高频观测期内出现强冲刷，但尚未逆转4月至7月的累计淤积；"
              "对B/C级年份只能说明含调水调沙季在内的阶段性净冲淤，不能把宽窗口全部归因于工程。"
              "2023年缺少6—7月后测次，不能评价。该结论不代表水库排沙、全河段减淤、输沙入海或河口生态补水的总体成效。", "",
              "逐年目标达成与证据限制见 `target_achievement_matrix.csv`。"]
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

    daily = read_attachment1(args.attachment1)
    a2 = read_attachment2(args.attachment2)
    a3, verticals = read_attachment3(args.attachment3)
    offset, calibration, calibration_detail = calibration_metrics(a2, a3)
    bed, bed_detail, all_methods, sensitivity = evaluate_bed_windows(a2, a3, offset)
    july_bed = evaluate_july_windows(a3)
    hydro, hydro_daily = summarize_hydrosediment(daily)
    velocity_sections, velocity = summarize_velocity(verticals)
    matrix = build_target_matrix(bed, july_bed, hydro, velocity, calibration)

    results = output / "results"
    validation = output / "validation"
    calibration.to_csv(validation / "cross_attachment_calibration_summary.csv", index=False, encoding="utf-8-sig")
    calibration_detail.to_csv(validation / "cross_attachment_calibration_grid.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(validation / "pchip_linear_sensitivity.csv", index=False, encoding="utf-8-sig")
    all_methods.to_csv(validation / "all_method_domain_metrics.csv", index=False, encoding="utf-8-sig")
    bed.to_csv(results / "multiyear_bed_effect_summary.csv", index=False, encoding="utf-8-sig")
    july_bed.to_csv(results / "july_event_bed_effect_summary.csv", index=False, encoding="utf-8-sig")
    bed_detail.to_csv(results / "multiyear_bed_change_grid.csv", index=False, encoding="utf-8-sig")
    hydro.to_csv(results / "june_july_hydrosediment_summary.csv", index=False, encoding="utf-8-sig")
    hydro_daily.to_csv(results / "june_july_hydrosediment_daily.csv", index=False, encoding="utf-8-sig")
    velocity_sections.to_csv(results / "attachment3_velocity_sections.csv", index=False, encoding="utf-8-sig")
    velocity.to_csv(results / "april_july_velocity_comparison.csv", index=False, encoding="utf-8-sig")
    matrix.to_csv(results / "target_achievement_matrix.csv", index=False, encoding="utf-8-sig")
    write_analysis(results / "analysis.md", calibration, bed, july_bed, hydro, velocity, matrix, sensitivity)

    save_calibration_figure(calibration_detail, output / "figures" / "cross_attachment_calibration.png")
    save_bed_figure(bed_detail, output / "figures" / "multiyear_bed_change.png")
    save_summary_figure(bed, july_bed, hydro, velocity, output / "figures" / "multiyear_effect_summary.png")

    checks = pd.DataFrame([
        {"check": "seven_bed_years_present", "passed": bed.year.nunique() == 7, "value": bed.year.nunique()},
        {"check": "three_velocity_years_present", "passed": velocity.year.nunique() == 3, "value": velocity.year.nunique()},
        {"check": "three_july_event_years_present", "passed": july_bed.year.nunique() == 3, "value": july_bed.year.nunique()},
        {"check": "six_hydrosediment_years_present", "passed": hydro.year.nunique() == 6, "value": hydro.year.nunique()},
        {"check": "no_pchip_spatial_extrapolation", "passed": bed_detail[["pre_bed_elevation_m", "post_bed_elevation_m"]].notna().all().all(), "value": "strict common domains"},
        {"check": "pchip_linear_direction_agreement_core", "passed": sensitivity[sensitivity.domain == "interior_1725_2050"].same_net_direction.all(), "value": sensitivity[sensitivity.domain == "interior_1725_2050"].same_net_direction.mean()},
        {"check": "target_matrix_has_2016_2023", "passed": matrix.year.tolist() == list(range(2016, 2024)), "value": len(matrix)},
    ])
    checks.to_csv(validation / "quality_checks.csv", index=False, encoding="utf-8-sig")
    summary = [
        f"Cross-attachment corrected RMSE: {calibration.iloc[0].bias_corrected_rmse_m:.4f} m",
        f"Core PCHIP-linear direction agreement: {sensitivity[sensitivity.domain == 'interior_1725_2050'].same_net_direction.mean():.1%}",
        f"Quality checks passed: {checks.passed.sum()}/{len(checks)}",
    ]
    (output / "logs" / "run_summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    if not checks.passed.all():
        raise RuntimeError("One or more quality checks failed")


if __name__ == "__main__":
    main()
