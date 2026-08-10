import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


METHODS = ["linear", "pchip"]
COLORS = {"linear": "#4C4C4C", "pchip": "#0072B2"}


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


def read_bed_profiles(path):
    raw = pd.read_excel(path)
    raw["日期"] = pd.to_datetime(raw["日期"], errors="coerce").ffill()
    raw["起点距离(m)"] = pd.to_numeric(raw["起点距离(m)"], errors="coerce")
    raw["水位(m)"] = pd.to_numeric(raw["水位(m)"], errors="coerce")
    raw["水深(m)"] = pd.to_numeric(raw["水深(m)"], errors="coerce")
    raw["水位(m)"] = raw.groupby("日期")["水位(m)"].transform(lambda values: values.dropna().iloc[0] if values.notna().any() else np.nan)
    stations = raw.dropna(subset=["日期", "起点距离(m)", "水位(m)", "水深(m)"]).copy()
    stations["河底高程(m)"] = stations["水位(m)"] - stations["水深(m)"]
    stations = stations.groupby(["日期", "起点距离(m)"], as_index=False).agg({"水位(m)": "first", "水深(m)": "mean", "河底高程(m)": "mean"})
    profiles = {date: group.sort_values("起点距离(m)").reset_index(drop=True) for date, group in stations.groupby("日期", sort=True)}
    return stations.sort_values(["日期", "起点距离(m)"]), profiles


def predict(method, x, y, xp):
    if method == "linear":
        return np.interp(xp, x, y)
    return PchipInterpolator(x, y, extrapolate=False)(xp)


def blocked_folds(n, folds=5, block_size=3):
    interior = np.arange(1, n - 1)
    blocks = [interior[i : i + block_size] for i in range(0, len(interior), block_size)]
    return [np.concatenate(blocks[k::folds]) for k in range(folds) if blocks[k::folds]]


def cross_validate(profiles):
    rows = []
    for date, frame in profiles.items():
        x = frame["起点距离(m)"].to_numpy(float)
        y = frame["河底高程(m)"].to_numpy(float)
        for fold, test in enumerate(blocked_folds(len(x)), start=1):
            train = np.ones(len(x), dtype=bool)
            train[test] = False
            for method in METHODS:
                fitted = predict(method, x[train], y[train], x[test])
                for index, actual, estimate in zip(test, y[test], fitted):
                    rows.append({"survey_date": date.date(), "fold": fold, "method": method, "distance_m": x[index], "actual_m": actual, "predicted_m": estimate, "error_m": estimate - actual, "abs_error_m": abs(estimate - actual), "is_july": date.month == 7})
    predictions = pd.DataFrame(rows)

    def metrics(group):
        error = group.error_m.to_numpy()
        return pd.Series({"n": len(error), "rmse_m": np.sqrt(np.mean(error**2)), "mae_m": np.mean(np.abs(error)), "bias_m": np.mean(error), "max_abs_error_m": np.max(np.abs(error))})

    overall = predictions.groupby("method", sort=False).apply(metrics, include_groups=False).reset_index()
    july = predictions[predictions.is_july].groupby("method", sort=False).apply(metrics, include_groups=False).reset_index()
    by_date = predictions.groupby(["survey_date", "method"], sort=False).apply(metrics, include_groups=False).reset_index()
    return predictions, overall, july, by_date


def july_windows(profiles):
    windows = {}
    for year in [2020, 2021, 2022]:
        dates = sorted(date for date in profiles if date.year == year and date.month == 7)
        if len(dates) >= 2:
            windows[year] = (dates[0], dates[-1])
    return windows


def contiguous_intervals(grid, mask, values, method, year, scope):
    rows = []
    indices = np.flatnonzero(mask)
    if not len(indices):
        return rows
    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    for group in groups:
        segment = values[group]
        rows.append(
            {
                "scope": scope,
                "year": year,
                "method": method,
                "start_distance_m": grid[group[0]],
                "end_distance_m": grid[group[-1]],
                "width_m": grid[group[-1]] - grid[group[0]] + 5.0,
                "direction": "erosion" if np.mean(segment) < 0 else "deposition",
                "mean_change_m": np.mean(segment),
                "max_abs_change_m": np.max(np.abs(segment)),
            }
        )
    return rows


def calculate_changes(profiles, windows, step):
    fitted_rows = []
    change_rows = []
    summary_rows = []
    hotspot_rows = []
    year_grids = {}
    year_changes = {}
    for year, (start, end) in windows.items():
        first = profiles[start]
        last = profiles[end]
        lower = max(first["起点距离(m)"].min(), last["起点距离(m)"].min())
        upper = min(first["起点距离(m)"].max(), last["起点距离(m)"].max())
        grid = np.arange(np.ceil(lower / step) * step, upper + 1e-9, step)
        year_grids[year] = grid
        year_changes[year] = {}
        for method in METHODS:
            start_fit = predict(method, first["起点距离(m)"].to_numpy(float), first["河底高程(m)"].to_numpy(float), grid)
            end_fit = predict(method, last["起点距离(m)"].to_numpy(float), last["河底高程(m)"].to_numpy(float), grid)
            delta = end_fit - start_fit
            year_changes[year][method] = delta
            for date, values in [(start, start_fit), (end, end_fit)]:
                fitted_rows.extend({"year": year, "survey_date": date.date(), "method": method, "distance_m": x, "bed_elevation_m": z} for x, z in zip(grid, values))
            change_rows.extend({"year": year, "start_date": start.date(), "end_date": end.date(), "method": method, "distance_m": x, "elevation_change_m": dz} for x, dz in zip(grid, delta))
            summary_rows.append(
                {
                    "year": year,
                    "start_date": start.date(),
                    "end_date": end.date(),
                    "method": method,
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
        linear = year_changes[year]["linear"]
        pchip = year_changes[year]["pchip"]
        threshold_linear = np.quantile(np.abs(linear), 0.75)
        threshold_pchip = np.quantile(np.abs(pchip), 0.75)
        consensus = (np.abs(linear) >= threshold_linear) & (np.abs(pchip) >= threshold_pchip) & (np.sign(linear) == np.sign(pchip))
        consensus_values = (linear + pchip) / 2
        hotspot_rows.extend(contiguous_intervals(grid, consensus, consensus_values, "linear_pchip_consensus", year, "within_year_q75"))

    common_lower = max(grid.min() for grid in year_grids.values())
    common_upper = min(grid.max() for grid in year_grids.values())
    common_grid = np.arange(common_lower, common_upper + 1e-9, step)
    pooled = []
    for year in sorted(windows):
        grid = year_grids[year]
        pooled.append(np.interp(common_grid, grid, (year_changes[year]["linear"] + year_changes[year]["pchip"]) / 2))
    pooled = np.asarray(pooled)
    mean_abs = np.mean(np.abs(pooled), axis=0)
    threshold = np.quantile(mean_abs, 0.75)
    erosion_count = np.sum(pooled < 0, axis=0)
    deposition_count = np.sum(pooled > 0, axis=0)
    consistent = (mean_abs >= threshold) & ((erosion_count >= 2) | (deposition_count >= 2))
    mean_signed = pooled.mean(axis=0)
    hotspot_rows.extend(contiguous_intervals(common_grid, consistent, mean_signed, "linear_pchip_consensus", "2020-2022", "cross_year_q75_recurrence"))
    pooled_frame = pd.DataFrame({"distance_m": common_grid, "mean_signed_change_m": mean_signed, "mean_abs_change_m": mean_abs, "erosion_year_count": erosion_count, "deposition_year_count": deposition_count, "is_cross_year_hotspot": consistent})
    return pd.DataFrame(fitted_rows), pd.DataFrame(change_rows), pd.DataFrame(summary_rows), pd.DataFrame(hotspot_rows), pooled_frame


def save_profiles(profiles, windows, fitted, output):
    fig, axes = plt.subplots(3, 1, figsize=(13, 11), sharex=True, sharey=True)
    for ax, (year, (start, end)) in zip(axes, windows.items()):
        for date, color, marker in [(start, "#2878B5", "o"), (end, "#D55E5E", "s")]:
            raw = profiles[date]
            ax.scatter(raw["起点距离(m)"], raw["河底高程(m)"], s=22, color=color, marker=marker, alpha=0.65, label=f"{date:%Y-%m-%d}实测")
            curve = fitted[(fitted.year == year) & (fitted.survey_date == date.date()) & (fitted.method == "pchip")]
            ax.plot(curve.distance_m, curve.bed_elevation_m, color=color, lw=2, label=f"{date:%Y-%m-%d} PCHIP")
        ax.set_title(f"{year}年7月首末测次河床断面")
        ax.set_ylabel("河底高程（m）")
        ax.legend(ncol=2, frameon=False, fontsize=9)
    axes[-1].set_xlabel("起点距离（m）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_changes(changes, output):
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, sharey=True)
    for ax, year in zip(axes, sorted(changes.year.unique())):
        subset = changes[changes.year == year]
        for method in METHODS:
            curve = subset[subset.method == method]
            ax.plot(curve.distance_m, curve.elevation_change_m, color=COLORS[method], lw=1.8, label=method.upper())
        pchip = subset[subset.method == "pchip"]
        ax.fill_between(pchip.distance_m, 0, pchip.elevation_change_m, where=pchip.elevation_change_m < 0, color="#2878B5", alpha=0.18)
        ax.fill_between(pchip.distance_m, 0, pchip.elevation_change_m, where=pchip.elevation_change_m >= 0, color="#D55E5E", alpha=0.18)
        ax.axhline(0, color="#333333", lw=0.8)
        ax.set_title(f"{year}年7月首末测次净变化（负值为后期更低）")
        ax.set_ylabel("高程变化（m）")
        ax.legend(frameon=False)
    axes[-1].set_xlabel("起点距离（m）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_heatmap(changes, output):
    years = sorted(changes.year.unique())
    lower = max(changes.loc[changes.year == year, "distance_m"].min() for year in years)
    upper = min(changes.loc[changes.year == year, "distance_m"].max() for year in years)
    grid = np.arange(lower, upper + 1e-9, 5.0)
    matrix = []
    for year in years:
        curve = changes[(changes.year == year) & (changes.method == "pchip")]
        matrix.append(np.interp(grid, curve.distance_m, curve.elevation_change_m))
    matrix = np.asarray(matrix)
    vmax = max(np.quantile(np.abs(matrix), 0.98), 0.1)
    fig, ax = plt.subplots(figsize=(13, 5.2))
    image = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax, extent=[grid.min(), grid.max(), len(years) - 0.5, -0.5])
    ax.set_yticks(range(len(years)), labels=years)
    ax.set(title="2020—2022年7月首末测次河底高程净变化（PCHIP）", xlabel="起点距离（m）", ylabel="年份")
    ax.grid(False)
    colorbar = fig.colorbar(image, ax=ax, pad=0.015)
    colorbar.set_label("高程变化（m）：蓝色冲刷，红色淤积")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_pooled_hotspots(pooled, output):
    fig, ax = plt.subplots(figsize=(13, 6.3))
    ax.plot(pooled.distance_m, pooled.mean_abs_change_m, color="#6A3D9A", lw=2, label="三年平均绝对变化")
    mask = pooled.is_cross_year_hotspot.astype(bool)
    ax.fill_between(pooled.distance_m, 0, pooled.mean_abs_change_m, where=mask, color="#F2A104", alpha=0.45, label="跨年复现热点")
    ax.set(title="2020—2022年7月变化集中的横向位置", xlabel="起点距离（m）", ylabel="平均绝对高程变化（m）")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_cv(overall, july, output):
    labels = ["全部19期", "7月测次"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.5), sharey=True)
    for ax, frame, title in zip(axes, [overall, july], labels):
        x = np.arange(len(frame))
        ax.bar(x, frame.rmse_m, color=[COLORS[m] for m in frame.method])
        ax.set_xticks(x, [m.upper() for m in frame.method])
        ax.set_title(title)
        ax.set_ylabel("空间区块留出RMSE（m）")
        for i, value in enumerate(frame.rmse_m):
            ax.text(i, value + 0.01, f"{value:.3f}", ha="center")
    fig.suptitle("附件3线性与PCHIP空间重建验证")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--grid-step-m", type=float, default=5.0)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    for name in ["results", "figures", "validation", "logs"]:
        (run_dir / name).mkdir(parents=True, exist_ok=True)
    configure_plotting()
    stations, profiles = read_bed_profiles(args.input)
    windows = july_windows(profiles)
    predictions, overall, july, by_date = cross_validate(profiles)
    fitted, changes, summary, hotspots, pooled = calculate_changes(profiles, windows, args.grid_step_m)

    stations.to_csv(run_dir / "results" / "attachment3_bed_stations.csv", index=False, encoding="utf-8-sig")
    fitted.to_csv(run_dir / "results" / "july_fitted_profiles.csv", index=False, encoding="utf-8-sig")
    changes.to_csv(run_dir / "results" / "july_bed_change_grid.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(run_dir / "results" / "july_change_summary.csv", index=False, encoding="utf-8-sig")
    hotspots.to_csv(run_dir / "results" / "july_hotspot_intervals.csv", index=False, encoding="utf-8-sig")
    pooled.to_csv(run_dir / "results" / "cross_year_hotspot_grid.csv", index=False, encoding="utf-8-sig")
    predictions.to_csv(run_dir / "validation" / "attachment3_blocked_cv_predictions.csv", index=False, encoding="utf-8-sig")
    overall.to_csv(run_dir / "validation" / "attachment3_blocked_cv_summary.csv", index=False, encoding="utf-8-sig")
    july.to_csv(run_dir / "validation" / "attachment3_july_blocked_cv_summary.csv", index=False, encoding="utf-8-sig")
    by_date.to_csv(run_dir / "validation" / "attachment3_blocked_cv_by_survey.csv", index=False, encoding="utf-8-sig")

    save_profiles(profiles, windows, fitted, run_dir / "figures" / "july_first_last_profiles.png")
    save_changes(changes, run_dir / "figures" / "july_net_bed_change.png")
    save_heatmap(changes, run_dir / "figures" / "july_change_heatmap.png")
    save_pooled_hotspots(pooled, run_dir / "figures" / "cross_year_change_hotspots.png")
    save_cv(overall, july, run_dir / "figures" / "attachment3_method_cv.png")

    checks = pd.DataFrame(
        [
            {"check": "profile_count", "value": len(profiles), "passed": len(profiles) == 19},
            {"check": "july_year_count", "value": len(windows), "passed": len(windows) == 3},
            {"check": "grid_step_m", "value": args.grid_step_m, "passed": args.grid_step_m == 5.0},
            {"check": "finite_changes", "value": int(np.isfinite(changes.elevation_change_m).sum()), "passed": bool(np.isfinite(changes.elevation_change_m).all())},
            {"check": "both_methods", "value": changes.method.nunique(), "passed": changes.method.nunique() == 2},
        ]
    )
    checks.to_csv(run_dir / "validation" / "quality_checks.csv", index=False, encoding="utf-8-sig")
    (run_dir / "logs" / "run_summary.txt").write_text(f"profiles={len(profiles)}\njuly_windows={len(windows)}\ncv_predictions={len(predictions)}\nhotspot_intervals={len(hotspots)}\nquality_checks={int(checks.passed.sum())}/{len(checks)}\n", encoding="utf-8")
    if not checks.passed.all():
        raise RuntimeError("Quality checks failed")


if __name__ == "__main__":
    main()
