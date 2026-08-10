import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


SEASONAL_WINDOWS = {
    2020: (pd.Timestamp("2020-04-17"), pd.Timestamp("2020-07-29")),
    2021: (pd.Timestamp("2021-04-16"), pd.Timestamp("2021-07-22")),
    2022: (pd.Timestamp("2022-04-18"), pd.Timestamp("2022-07-23")),
}
COLORS = {"pre": "#2878B5", "post": "#D55E5E", "erosion": "#2878B5", "deposition": "#D55E5E"}
CORE_DOMAIN = (1725.0, 2050.0)


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


def read_attachment1(path):
    rows = []
    workbook = pd.ExcelFile(path)
    for sheet in workbook.sheet_names:
        raw = pd.read_excel(path, sheet_name=sheet)
        raw.columns = [str(column).strip() for column in raw.columns]
        required = ["年", "月", "日", "流量(m3/s)", "含沙量(kg/m3)"]
        if not set(required).issubset(raw.columns):
            continue
        raw[["年", "月", "日"]] = raw[["年", "月", "日"]].ffill()
        raw["日期"] = pd.to_datetime(dict(year=raw["年"], month=raw["月"], day=raw["日"]), errors="coerce")
        raw["流量(m3/s)"] = pd.to_numeric(raw["流量(m3/s)"], errors="coerce")
        raw["含沙量(kg/m3)"] = pd.to_numeric(raw["含沙量(kg/m3)"], errors="coerce")
        rows.append(raw[["日期", "流量(m3/s)", "含沙量(kg/m3)"]])
    data = pd.concat(rows, ignore_index=True).dropna(subset=["日期"])
    return data.groupby("日期", as_index=False).agg(
        平均流量_m3s=("流量(m3/s)", "mean"),
        最大流量_m3s=("流量(m3/s)", "max"),
        平均含沙量_kgm3=("含沙量(kg/m3)", "mean"),
        最大含沙量_kgm3=("含沙量(kg/m3)", "max"),
        含沙观测数=("含沙量(kg/m3)", "count"),
    )


def read_attachment3(path):
    raw = pd.read_excel(path)
    raw["日期"] = pd.to_datetime(raw["日期"], errors="coerce").ffill()
    for column in ["起点距离(m)", "水位(m)", "水深(m)"]:
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw["水位(m)"] = raw.groupby("日期")["水位(m)"].transform(
        lambda values: values.dropna().iloc[0] if values.notna().any() else np.nan
    )
    stations = raw.dropna(subset=["日期", "起点距离(m)", "水位(m)", "水深(m)"]).copy()
    stations["河底高程(m)"] = stations["水位(m)"] - stations["水深(m)"]
    stations = stations.groupby(["日期", "起点距离(m)"], as_index=False).agg(
        {"水位(m)": "first", "水深(m)": "mean", "河底高程(m)": "mean"}
    )
    profiles = {
        date: frame.sort_values("起点距离(m)").reset_index(drop=True)
        for date, frame in stations.groupby("日期", sort=True)
    }
    return stations.sort_values(["日期", "起点距离(m)"]), profiles


def read_attachment2(path):
    raw = pd.read_excel(path, header=None)
    surveys = {}
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
        surveys[date] = frame.groupby("distance_m", as_index=False)["bed_elevation_m"].mean().sort_values("distance_m")
    return surveys


def pchip_profile(frame, grid, distance_column="起点距离(m)", elevation_column="河底高程(m)"):
    x = frame[distance_column].to_numpy(float)
    z = frame[elevation_column].to_numpy(float)
    return PchipInterpolator(x, z, extrapolate=False)(grid)


def compare_windows(profiles, windows, step, window_name):
    grid_rows, summary_rows = [], []
    for year, (pre_date, post_date) in windows.items():
        pre, post = profiles[pre_date], profiles[post_date]
        lower = max(pre["起点距离(m)"].min(), post["起点距离(m)"].min())
        upper = min(pre["起点距离(m)"].max(), post["起点距离(m)"].max())
        grid = np.arange(np.ceil(lower / step) * step, upper + 1e-9, step)
        pre_fit = pchip_profile(pre, grid)
        post_fit = pchip_profile(post, grid)
        delta = post_fit - pre_fit
        threshold = np.quantile(np.abs(delta), 0.75)
        for x, before, after, change in zip(grid, pre_fit, post_fit, delta):
            grid_rows.append(
                {
                    "window": window_name,
                    "year": year,
                    "pre_date": pre_date.date(),
                    "post_date": post_date.date(),
                    "distance_m": x,
                    "pre_bed_elevation_m": before,
                    "post_bed_elevation_m": after,
                    "elevation_change_m": change,
                    "is_top_quartile_change": abs(change) >= threshold,
                }
            )
        summary_rows.append(
            {
                "window": window_name,
                "year": year,
                "pre_date": pre_date.date(),
                "post_date": post_date.date(),
                "days": (post_date - pre_date).days,
                "lower_distance_m": grid.min(),
                "upper_distance_m": grid.max(),
                "net_section_change_m2": np.trapz(delta, grid),
                "erosion_area_m2": np.trapz(np.maximum(-delta, 0), grid),
                "deposition_area_m2": np.trapz(np.maximum(delta, 0), grid),
                "mean_change_m": delta.mean(),
                "max_erosion_m": -delta.min(),
                "max_erosion_distance_m": grid[np.argmin(delta)],
                "max_deposition_m": delta.max(),
                "max_deposition_distance_m": grid[np.argmax(delta)],
            }
        )
    return pd.DataFrame(grid_rows), pd.DataFrame(summary_rows)


def summarize_domains(grid_data):
    rows = []
    for (window, year), frame in grid_data.groupby(["window", "year"], sort=False):
        for domain, lower, upper in [
            ("full_common", frame.distance_m.min(), frame.distance_m.max()),
            ("interior_1725_2050", CORE_DOMAIN[0], CORE_DOMAIN[1]),
        ]:
            subset = frame[(frame.distance_m >= lower) & (frame.distance_m <= upper)]
            x = subset.distance_m.to_numpy(float)
            delta = subset.elevation_change_m.to_numpy(float)
            erosion_index = np.flatnonzero(delta < 0)
            deposition_index = np.flatnonzero(delta > 0)
            deepest = erosion_index[np.argmin(delta[erosion_index])] if len(erosion_index) else None
            highest = deposition_index[np.argmax(delta[deposition_index])] if len(deposition_index) else None
            rows.append(
                {
                    "window": window,
                    "year": year,
                    "domain": domain,
                    "pre_date": subset.pre_date.iloc[0],
                    "post_date": subset.post_date.iloc[0],
                    "lower_distance_m": x.min(),
                    "upper_distance_m": x.max(),
                    "net_section_change_m2": np.trapz(delta, x),
                    "erosion_area_m2": np.trapz(np.maximum(-delta, 0), x),
                    "deposition_area_m2": np.trapz(np.maximum(delta, 0), x),
                    "mean_change_m": delta.mean(),
                    "max_erosion_m": -delta[deepest] if deepest is not None else 0.0,
                    "max_erosion_distance_m": x[deepest] if deepest is not None else np.nan,
                    "max_deposition_m": delta[highest] if highest is not None else 0.0,
                    "max_deposition_distance_m": x[highest] if highest is not None else np.nan,
                }
            )
    return pd.DataFrame(rows)


def july_windows(profiles):
    result = {}
    for year in SEASONAL_WINDOWS:
        dates = sorted(date for date in profiles if date.year == year and date.month == 7)
        result[year] = (dates[0], dates[-1])
    return result


def attachment2_context(surveys, step):
    pre_date, post_date = pd.Timestamp("2019-04-13"), pd.Timestamp("2019-10-15")
    pre, post = surveys[pre_date], surveys[post_date]
    lower = max(pre.distance_m.min(), post.distance_m.min())
    upper = min(pre.distance_m.max(), post.distance_m.max())
    grid = np.arange(np.ceil(lower / step) * step, upper + 1e-9, step)
    pre_fit = pchip_profile(pre, grid, "distance_m", "bed_elevation_m")
    post_fit = pchip_profile(post, grid, "distance_m", "bed_elevation_m")
    return pd.DataFrame(
        {
            "pre_date": pre_date.date(),
            "post_date": post_date.date(),
            "distance_m": grid,
            "pre_bed_elevation_m": pre_fit,
            "post_bed_elevation_m": post_fit,
            "elevation_change_m": post_fit - pre_fit,
        }
    )


def save_pre_post_profiles(profiles, seasonal_grid, output):
    fig, axes = plt.subplots(3, 2, figsize=(15, 11), gridspec_kw={"width_ratios": [1.15, 1]})
    for row, year in enumerate(sorted(SEASONAL_WINDOWS)):
        pre_date, post_date = SEASONAL_WINDOWS[year]
        ax_profile, ax_change = axes[row]
        for date, role, marker in [(pre_date, "pre", "o"), (post_date, "post", "s")]:
            frame = profiles[date]
            ax_profile.scatter(frame["起点距离(m)"], frame["河底高程(m)"], s=20, alpha=0.55, marker=marker, color=COLORS[role])
            curve = seasonal_grid[seasonal_grid.year == year]
            values = curve["pre_bed_elevation_m"] if role == "pre" else curve["post_bed_elevation_m"]
            ax_profile.plot(curve.distance_m, values, lw=2, color=COLORS[role], label=f"{date:%Y-%m-%d}")
        curve = seasonal_grid[seasonal_grid.year == year]
        ax_change.axhline(0, color="#333333", lw=0.8)
        ax_change.plot(curve.distance_m, curve.elevation_change_m, color="#4C4C4C", lw=1.5)
        ax_change.fill_between(curve.distance_m, 0, curve.elevation_change_m, where=curve.elevation_change_m < 0, color=COLORS["erosion"], alpha=0.7, label="冲刷")
        ax_change.fill_between(curve.distance_m, 0, curve.elevation_change_m, where=curve.elevation_change_m >= 0, color=COLORS["deposition"], alpha=0.7, label="淤积")
        for axis in [ax_profile, ax_change]:
            axis.axvline(CORE_DOMAIN[0], color="#F2A104", ls=":", lw=1)
            axis.axvline(CORE_DOMAIN[1], color="#F2A104", ls=":", lw=1)
        ax_profile.set(title=f"{year}年前后河床断面（PCHIP）", ylabel="河底高程（m）")
        ax_change.set(title=f"{year}年前后高程变化", ylabel="后期−前期（m）")
        ax_profile.legend(frameon=False, ncol=2, fontsize=9)
        ax_change.legend(frameon=False, ncol=2, fontsize=9)
    for ax in axes[-1]:
        ax.set_xlabel("起点距离（m）")
    fig.suptitle("2020—2022年6—7月水沙过程前后河床变化", fontsize=16)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_heatmap(grid_data, output):
    years = sorted(grid_data.year.unique())
    lower, upper = CORE_DOMAIN
    grid = np.arange(lower, upper + 1e-9, 5.0)
    matrix = []
    for year in years:
        curve = grid_data[grid_data.year == year]
        matrix.append(np.interp(grid, curve.distance_m, curve.elevation_change_m))
    matrix = np.asarray(matrix)
    vmax = max(np.quantile(np.abs(matrix), 0.98), 0.1)
    fig, ax = plt.subplots(figsize=(13, 5.2))
    image = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax, extent=[grid.min(), grid.max(), len(years) - 0.5, -0.5])
    ax.set_yticks(range(len(years)), labels=years)
    ax.set(title="4月基线至7月末内部稳健区河底高程变化（PCHIP）", xlabel="起点距离（m）", ylabel="年份")
    ax.grid(False)
    bar = fig.colorbar(image, ax=ax, pad=0.015)
    bar.set_label("高程变化（m）：蓝色冲刷，红色淤积")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_effect_summary(summary, output):
    core = summary[summary.domain == "interior_1725_2050"]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6.3), sharey=True)
    specifications = [
        ("april_to_late_july", "4月基线 → 7月末"),
        ("july_first_to_last", "7月首测 → 7月末测"),
    ]
    for ax, (window, title) in zip(axes, specifications):
        frame = core[core.window == window].sort_values("year")
        x = np.arange(len(frame))
        ax.bar(x, frame.deposition_area_m2, color=COLORS["deposition"], alpha=0.82, label="淤积面积")
        ax.bar(x, -frame.erosion_area_m2, color=COLORS["erosion"], alpha=0.82, label="冲刷面积")
        ax.scatter(x, frame.net_section_change_m2, color="#222222", marker="D", s=45, zorder=3, label="净变化")
        for index, net in enumerate(frame.net_section_change_m2):
            offset = 7 if net >= 0 else -12
            ax.annotate(f"{net:+.1f}", (index, net), xytext=(0, offset), textcoords="offset points", ha="center", fontsize=10)
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_xticks(x, frame.year.astype(str))
        ax.set(title=title, xlabel="年份")
    axes[0].set_ylabel("断面面积变化（m²）")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 0.98))
    fig.suptitle("内部稳健区1725—2050 m的冲淤效果（PCHIP）", fontsize=16, y=1.03)
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_hydrology(daily, profiles, output):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8.5), sharex=False)
    for ax, year in zip(axes, [2020, 2021]):
        frame = daily[(daily.日期 >= f"{year}-06-01") & (daily.日期 <= f"{year}-07-31")]
        ax2 = ax.twinx()
        line1 = ax.plot(frame.日期, frame.平均流量_m3s, color="#2878B5", lw=2, label="日平均流量")
        line2 = ax2.plot(frame.日期, frame.平均含沙量_kgm3, color="#D55E5E", lw=1.8, label="日平均含沙量")
        july_dates = sorted(date for date in profiles if date.year == year and date.month == 7)
        for date in july_dates:
            ax.axvline(date, color="#555555", ls="--", lw=0.7, alpha=0.55)
            ax.text(date, 0.98, date.strftime("%m/%d"), transform=ax.get_xaxis_transform(), rotation=90, va="top", ha="right", fontsize=8, color="#555555")
        ax.set(title=f"{year}年6—7月水沙过程与附件3测次", ylabel="流量（m³/s）")
        ax2.set_ylabel("含沙量（kg/m³）")
        ax.legend(line1 + line2, [item.get_label() for item in line1 + line2], frameon=False, loc="upper left")
    axes[-1].set_xlabel("日期")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_attachment2_context(context, output):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8.5), sharex=True)
    axes[0].plot(context.distance_m, context.pre_bed_elevation_m, color=COLORS["pre"], lw=1.8, label="2019-04-13")
    axes[0].plot(context.distance_m, context.post_bed_elevation_m, color=COLORS["post"], lw=1.8, label="2019-10-15")
    axes[0].axvspan(1675, 2075, color="#F2A104", alpha=0.13, label="附件3主要覆盖区")
    axes[0].set(title="附件2全断面背景：2019年6—7月前后最近测次（间隔含8—10月变化）", ylabel="河底高程（m）")
    axes[0].legend(frameon=False, ncol=3)
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].plot(context.distance_m, context.elevation_change_m, color="#4C4C4C", lw=1)
    axes[1].fill_between(context.distance_m, 0, context.elevation_change_m, where=context.elevation_change_m < 0, color=COLORS["erosion"], alpha=0.7)
    axes[1].fill_between(context.distance_m, 0, context.elevation_change_m, where=context.elevation_change_m >= 0, color=COLORS["deposition"], alpha=0.7)
    axes[1].axvspan(1675, 2075, color="#F2A104", alpha=0.13)
    axes[1].set(xlabel="起点距离（m）", ylabel="后期−前期（m）", title="2019-04-13 → 2019-10-15全断面变化（PCHIP）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachment1", required=True)
    parser.add_argument("--attachment2", required=True)
    parser.add_argument("--attachment3", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--grid-step-m", type=float, default=5.0)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    for folder in ["results", "figures", "validation", "logs"]:
        (run_dir / folder).mkdir(parents=True, exist_ok=True)
    configure_plotting()
    daily = read_attachment1(args.attachment1)
    stations, profiles = read_attachment3(args.attachment3)
    attachment2 = read_attachment2(args.attachment2)

    seasonal_grid, _ = compare_windows(profiles, SEASONAL_WINDOWS, args.grid_step_m, "april_to_late_july")
    inner_grid, _ = compare_windows(profiles, july_windows(profiles), args.grid_step_m, "july_first_to_last")
    all_grid = pd.concat([seasonal_grid, inner_grid], ignore_index=True)
    all_summary = summarize_domains(all_grid)
    context = attachment2_context(attachment2, args.grid_step_m)

    daily.to_csv(run_dir / "results" / "attachment1_daily_hydrosediment.csv", index=False, encoding="utf-8-sig")
    stations.to_csv(run_dir / "results" / "attachment3_bed_stations.csv", index=False, encoding="utf-8-sig")
    all_grid.to_csv(run_dir / "results" / "pchip_pre_post_grid.csv", index=False, encoding="utf-8-sig")
    all_summary.to_csv(run_dir / "results" / "pchip_effect_summary.csv", index=False, encoding="utf-8-sig")
    context.to_csv(run_dir / "results" / "attachment2_2019_context.csv", index=False, encoding="utf-8-sig")

    save_pre_post_profiles(profiles, seasonal_grid, run_dir / "figures" / "annual_pre_post_profiles_pchip.png")
    save_heatmap(seasonal_grid, run_dir / "figures" / "annual_effect_heatmap_pchip.png")
    save_effect_summary(all_summary, run_dir / "figures" / "annual_effect_summary_pchip.png")
    save_hydrology(daily, profiles, run_dir / "figures" / "hydro_sediment_and_surveys.png")
    save_attachment2_context(context, run_dir / "figures" / "attachment2_full_section_context.png")

    expected_dates = {date for window in SEASONAL_WINDOWS.values() for date in window}
    checks = pd.DataFrame(
        [
            {"check": "three_seasonal_windows", "value": seasonal_grid.year.nunique(), "passed": seasonal_grid.year.nunique() == 3},
            {"check": "required_attachment3_dates", "value": len(expected_dates.intersection(profiles)), "passed": expected_dates.issubset(profiles)},
            {"check": "all_changes_finite", "value": int(np.isfinite(all_grid.elevation_change_m).sum()), "passed": bool(np.isfinite(all_grid.elevation_change_m).all())},
            {"check": "grid_step_5m", "value": args.grid_step_m, "passed": args.grid_step_m == 5.0},
            {"check": "attachment1_has_2020_2021", "value": int(daily.日期.dt.year.isin([2020, 2021]).sum()), "passed": set([2020, 2021]).issubset(set(daily.日期.dt.year))},
            {"check": "attachment2_context_pair", "value": len(context), "passed": len(context) > 0},
        ]
    )
    checks.to_csv(run_dir / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")
    (run_dir / "logs" / "run_summary.txt").write_text(
        f"seasonal_windows={seasonal_grid.year.nunique()}\ninner_july_windows={inner_grid.year.nunique()}\nsummary_domains={all_summary.domain.nunique()}\nfigures=5\nquality_checks={int(checks.passed.sum())}/{len(checks)}\n",
        encoding="utf-8",
    )
    if not checks.passed.all():
        raise RuntimeError("Quality checks failed")


if __name__ == "__main__":
    main()
