import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


YEARS = [2020, 2021, 2022]
MAIN_CHANNEL = (2005.0, 2040.0)
COLORS = {2020: "#2878B5", 2021: "#D55E5E", 2022: "#009E73"}


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
    raw["日期"] = pd.to_datetime(raw["日期"], errors="coerce").ffill()
    for column in ["起点距离(m)", "水位(m)", "水深(m)", "测点水深(m)", "测点水流速(m/s)", "测点含沙量(kg/m3)"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw["垂线距离(m)"] = raw.groupby("日期")["起点距离(m)"].ffill()
    raw["垂线总水深(m)"] = raw.groupby(["日期", "垂线距离(m)"], dropna=False)["水深(m)"].transform(first_valid)
    raw["断面水位(m)"] = raw.groupby("日期")["水位(m)"].transform(first_valid)

    velocity_points = raw.dropna(subset=["日期", "垂线距离(m)", "测点水流速(m/s)"]).copy()
    verticals = velocity_points.groupby(["日期", "垂线距离(m)"], as_index=False).agg(
        垂线平均流速_mps=("测点水流速(m/s)", "mean"),
        垂线流速中位数_mps=("测点水流速(m/s)", "median"),
        流速测点数=("测点水流速(m/s)", "size"),
        总水深_m=("垂线总水深(m)", "first"),
        最浅测点_m=("测点水深(m)", "min"),
        最深测点_m=("测点水深(m)", "max"),
    )

    bed_rows = raw.dropna(subset=["日期", "起点距离(m)", "断面水位(m)", "水深(m)"]).copy()
    bed_rows["河底高程(m)"] = bed_rows["断面水位(m)"] - bed_rows["水深(m)"]
    bed_stations = bed_rows.groupby(["日期", "起点距离(m)"], as_index=False).agg(
        {"断面水位(m)": "first", "水深(m)": "mean", "河底高程(m)": "mean"}
    )
    bed_profiles = {
        date: frame.sort_values("起点距离(m)").reset_index(drop=True)
        for date, frame in bed_stations.groupby("日期", sort=True)
    }
    return raw, velocity_points, verticals, bed_profiles


def representative_widths(x):
    x = np.asarray(x, dtype=float)
    widths = np.empty(len(x), dtype=float)
    if len(x) == 1:
        widths[0] = np.nan
        return widths
    widths[0] = (x[1] - x[0]) / 2
    widths[-1] = (x[-1] - x[-2]) / 2
    if len(x) > 2:
        widths[1:-1] = (x[2:] - x[:-2]) / 2
    return widths


def summarize_sections(verticals):
    rows = []
    for date, frame in verticals.groupby("日期", sort=True):
        frame = frame.sort_values("垂线距离(m)").copy()
        usable = frame.dropna(subset=["垂线平均流速_mps", "总水深_m"]).query("总水深_m > 0").copy()
        usable["代表宽度_m"] = representative_widths(usable["垂线距离(m)"].to_numpy())
        usable["面积权重_m2"] = usable["总水深_m"] * usable["代表宽度_m"]
        area_velocity = np.average(usable["垂线平均流速_mps"], weights=usable["面积权重_m2"]) if len(usable) >= 2 else np.nan
        main = frame[frame["垂线距离(m)"].between(*MAIN_CHANNEL)]
        rows.append(
            {
                "date": date,
                "year": date.year,
                "month": date.month,
                "vertical_count": len(frame),
                "velocity_point_count": int(frame["流速测点数"].sum()),
                "simple_mean_velocity_mps": frame["垂线平均流速_mps"].mean(),
                "median_vertical_velocity_mps": frame["垂线平均流速_mps"].median(),
                "area_weighted_velocity_mps": area_velocity,
                "weighted_area_proxy_m2": usable["面积权重_m2"].sum(),
                "main_channel_vertical_count": len(main),
                "main_channel_mean_velocity_mps": main["垂线平均流速_mps"].mean() if len(main) else np.nan,
                "main_channel_min_distance_m": main["垂线距离(m)"].min() if len(main) else np.nan,
                "main_channel_max_distance_m": main["垂线距离(m)"].max() if len(main) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def read_attachment1_daily(path):
    rows = []
    workbook = pd.ExcelFile(path)
    for sheet in workbook.sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet)
        raw.columns = [str(column).strip() for column in raw.columns]
        if not {"年", "月", "日", "流量(m3/s)", "含沙量(kg/m3)"}.issubset(raw.columns):
            continue
        raw[["年", "月", "日"]] = raw[["年", "月", "日"]].ffill()
        raw["date"] = pd.to_datetime(dict(year=raw["年"], month=raw["月"], day=raw["日"]), errors="coerce")
        raw["流量(m3/s)"] = pd.to_numeric(raw["流量(m3/s)"], errors="coerce")
        raw["含沙量(kg/m3)"] = pd.to_numeric(raw["含沙量(kg/m3)"], errors="coerce")
        rows.append(raw[["date", "流量(m3/s)", "含沙量(kg/m3)"]])
    data = pd.concat(rows, ignore_index=True).dropna(subset=["date"])
    return data.groupby("date", as_index=False).agg(
        daily_mean_discharge_m3s=("流量(m3/s)", "mean"),
        daily_max_discharge_m3s=("流量(m3/s)", "max"),
        daily_mean_sediment_kgm3=("含沙量(kg/m3)", "mean"),
        daily_max_sediment_kgm3=("含沙量(kg/m3)", "max"),
    )


def pchip_bed_change(bed_profiles, step=5.0):
    rows = []
    for year in YEARS:
        july_dates = sorted(date for date in bed_profiles if date.year == year and date.month == 7)
        start, end = july_dates[0], july_dates[-1]
        first, last = bed_profiles[start], bed_profiles[end]
        lower = max(MAIN_CHANNEL[0], first["起点距离(m)"].min(), last["起点距离(m)"].min())
        upper = min(MAIN_CHANNEL[1], first["起点距离(m)"].max(), last["起点距离(m)"].max())
        grid = np.arange(np.ceil(lower / step) * step, upper + 1e-9, step)
        start_fit = PchipInterpolator(first["起点距离(m)"], first["河底高程(m)"], extrapolate=False)(grid)
        end_fit = PchipInterpolator(last["起点距离(m)"], last["河底高程(m)"], extrapolate=False)(grid)
        delta = end_fit - start_fit
        rows.append(
            {
                "year": year,
                "july_start_date": start,
                "july_end_date": end,
                "main_channel_mean_bed_change_m": delta.mean(),
                "main_channel_net_section_change_m2": np.trapz(delta, grid),
                "main_channel_max_erosion_m": max(0.0, -delta.min()),
                "main_channel_max_deposition_m": max(0.0, delta.max()),
            }
        )
    return pd.DataFrame(rows)


def build_comparisons(section_summary, bed_change):
    rows = []
    for year in YEARS:
        year_data = section_summary[section_summary.year == year].sort_values("date")
        april = year_data[year_data.month == 4].iloc[0]
        july = year_data[year_data.month == 7]
        first, last = july.iloc[0], july.iloc[-1]
        rows.append(
            {
                "year": year,
                "april_date": april.date,
                "july_first_date": first.date,
                "july_last_date": last.date,
                "april_area_velocity_mps": april.area_weighted_velocity_mps,
                "july_first_area_velocity_mps": first.area_weighted_velocity_mps,
                "july_last_area_velocity_mps": last.area_weighted_velocity_mps,
                "april_to_july_last_change_mps": last.area_weighted_velocity_mps - april.area_weighted_velocity_mps,
                "april_to_july_last_change_pct": 100 * (last.area_weighted_velocity_mps / april.area_weighted_velocity_mps - 1),
                "july_first_to_last_change_mps": last.area_weighted_velocity_mps - first.area_weighted_velocity_mps,
                "july_first_to_last_change_pct": 100 * (last.area_weighted_velocity_mps / first.area_weighted_velocity_mps - 1),
                "april_main_velocity_mps": april.main_channel_mean_velocity_mps,
                "july_first_main_velocity_mps": first.main_channel_mean_velocity_mps,
                "july_last_main_velocity_mps": last.main_channel_mean_velocity_mps,
                "main_july_first_to_last_change_mps": last.main_channel_mean_velocity_mps - first.main_channel_mean_velocity_mps,
                "main_july_first_to_last_change_pct": 100 * (last.main_channel_mean_velocity_mps / first.main_channel_mean_velocity_mps - 1),
            }
        )
    return pd.DataFrame(rows).merge(bed_change, on="year", how="left")


def save_velocity_timeline(summary, output):
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharey=True)
    for ax, year in zip(axes, YEARS):
        frame = summary[(summary.year == year) & (summary.month.isin([4, 7]))]
        ax.plot(frame.date, frame.area_weighted_velocity_mps, color=COLORS[year], marker="o", lw=2, label="断面面积加权流速")
        ax.plot(frame.date, frame.simple_mean_velocity_mps, color="#555555", marker="s", ls="--", lw=1.2, label="垂线算术平均")
        july_indices = frame.index[frame.month.eq(7)].tolist()
        label_indices = {frame.index[0], july_indices[0], july_indices[-1]}
        for index, row in frame.iterrows():
            if index not in label_indices:
                continue
            ax.annotate(f"{row.area_weighted_velocity_mps:.2f}", (row.date, row.area_weighted_velocity_mps), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
        ax.set(title=f"{year}年4月基线与7月流速测次", ylabel="流速（m/s）")
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=7))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax.legend(frameon=False, ncol=2, fontsize=9)
    axes[-1].set_xlabel("日期")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_velocity_profiles(verticals, output):
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, sharey=True)
    for ax, year in zip(axes, YEARS):
        dates = sorted(date for date in verticals["日期"].unique() if pd.Timestamp(date).year == year and pd.Timestamp(date).month in [4, 7])
        colors = plt.cm.viridis(np.linspace(0.05, 0.95, len(dates)))
        for date, color in zip(dates, colors):
            frame = verticals[verticals["日期"] == date].sort_values("垂线距离(m)")
            style = "--" if pd.Timestamp(date).month == 4 else "-"
            ax.plot(frame["垂线距离(m)"], frame["垂线平均流速_mps"], marker="o", ms=3.5, lw=1.4, ls=style, color=color, label=pd.Timestamp(date).strftime("%m-%d"))
        ax.axvspan(*MAIN_CHANNEL, color="#F2A104", alpha=0.13, label="主槽2005—2040 m")
        ax.set(title=f"{year}年垂线平均流速横向分布", ylabel="流速（m/s）")
        ax.legend(frameon=False, ncol=min(5, len(dates) + 1), fontsize=8)
    axes[-1].set_xlabel("起点距离（m）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_change_summary(comparison, output):
    x = np.arange(len(comparison))
    width = 0.34
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    axes[0].bar(x - width / 2, comparison.april_to_july_last_change_pct, width, color="#2878B5", label="4月→7月末")
    axes[0].bar(x + width / 2, comparison.july_first_to_last_change_pct, width, color="#D55E5E", label="7月首→末")
    axes[0].axhline(0, color="#333333", lw=0.8)
    axes[0].set_xticks(x, comparison.year.astype(str))
    axes[0].set(title="断面面积加权流速变化", xlabel="年份", ylabel="变化率（%）")
    axes[0].legend(frameon=False)
    colors = ["#D55E5E" if value >= 0 else "#2878B5" for value in comparison.main_channel_mean_bed_change_m]
    axes[1].bar(x, comparison.main_channel_mean_bed_change_m, color=colors)
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].set_xticks(x, comparison.year.astype(str))
    axes[1].set(title="主槽2005—2040 m的7月河床变化", xlabel="年份", ylabel="平均高程变化（m）")
    fig.suptitle("流速增强与主槽冲淤并非简单一一对应", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_discharge_alignment(summary_with_flow, output):
    frame = summary_with_flow[summary_with_flow.year.isin([2020, 2021]) & summary_with_flow.month.eq(7)].copy()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8))
    for ax, year in zip(axes, [2020, 2021]):
        subset = frame[frame.year == year].sort_values("date")
        ax2 = ax.twinx()
        first = ax.plot(subset.date, subset.area_weighted_velocity_mps, marker="o", color="#2878B5", lw=2, label="断面面积加权流速")
        second = ax2.plot(subset.date, subset.daily_mean_discharge_m3s, marker="s", color="#D55E5E", lw=1.7, label="附件1日平均流量")
        ax.set(title=f"{year}年7月流速与流量测次对齐", ylabel="流速（m/s）")
        ax2.set_ylabel("流量（m³/s）")
        ax.set_xticks(subset.date)
        ax.set_xticklabels(subset.date.dt.strftime("%m-%d"), rotation=45, ha="right")
        ax.legend(first + second, [line.get_label() for line in first + second], frameon=False, fontsize=9, loc="best")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachment1", required=True)
    parser.add_argument("--attachment3", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    for folder in ["results", "figures", "validation", "logs"]:
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    configure_plotting()
    raw, velocity_points, verticals, bed_profiles = read_attachment3(args.attachment3)
    daily = read_attachment1_daily(args.attachment1)
    section_summary = summarize_sections(verticals)
    summary_with_flow = section_summary.merge(daily, on="date", how="left")
    bed_change = pchip_bed_change(bed_profiles)
    comparison = build_comparisons(section_summary, bed_change)

    velocity_points.to_csv(run_dir / "results" / "velocity_points.csv", index=False, encoding="utf-8-sig")
    verticals.to_csv(run_dir / "results" / "vertical_mean_velocity.csv", index=False, encoding="utf-8-sig")
    summary_with_flow.to_csv(run_dir / "results" / "survey_velocity_summary.csv", index=False, encoding="utf-8-sig")
    comparison.to_csv(run_dir / "results" / "velocity_bed_comparison.csv", index=False, encoding="utf-8-sig")
    bed_change.to_csv(run_dir / "results" / "main_channel_bed_change.csv", index=False, encoding="utf-8-sig")

    save_velocity_timeline(section_summary, run_dir / "figures" / "april_july_velocity_timeline.png")
    save_velocity_profiles(verticals, run_dir / "figures" / "velocity_cross_section_profiles.png")
    save_change_summary(comparison, run_dir / "figures" / "velocity_and_bed_change_summary.png")
    save_discharge_alignment(summary_with_flow, run_dir / "figures" / "velocity_discharge_alignment.png")

    july = section_summary[section_summary.year.isin(YEARS) & section_summary.month.eq(7)]
    checks = pd.DataFrame(
        [
            {"check": "velocity_survey_count", "value": len(section_summary), "passed": len(section_summary) == 19},
            {"check": "july_year_count", "value": july.year.nunique(), "passed": july.year.nunique() == 3},
            {"check": "finite_area_velocity", "value": int(np.isfinite(section_summary.area_weighted_velocity_mps).sum()), "passed": bool(np.isfinite(section_summary.area_weighted_velocity_mps).all())},
            {"check": "vertical_point_patterns", "value": verticals.流速测点数.isin([1, 2, 5]).mean(), "passed": bool(verticals.流速测点数.isin([1, 2, 5]).all())},
            {"check": "main_channel_has_observations", "value": int(july.main_channel_vertical_count.sum()), "passed": bool((july.main_channel_vertical_count >= 1).all())},
            {"check": "attachment1_alignment_2020_2021", "value": int(summary_with_flow.daily_mean_discharge_m3s.notna().sum()), "passed": bool(summary_with_flow[summary_with_flow.year.isin([2020, 2021])].daily_mean_discharge_m3s.notna().all())},
        ]
    )
    checks.to_csv(run_dir / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")
    (run_dir / "logs" / "run_summary.txt").write_text(
        f"velocity_surveys={len(section_summary)}\nverticals={len(verticals)}\nvelocity_points={len(velocity_points)}\nfigures=4\nquality_checks={int(checks.passed.sum())}/{len(checks)}\n",
        encoding="utf-8",
    )
    if not checks.passed.all():
        raise RuntimeError("Quality checks failed")


if __name__ == "__main__":
    main()
