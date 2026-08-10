import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import colormaps, font_manager
import numpy as np
import pandas as pd


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


def read_surveys(path):
    raw = pd.read_excel(path, header=None)
    surveys = {}
    rows = []
    for col in range(0, raw.shape[1], 2):
        date = pd.to_datetime(raw.iat[0, col], errors="coerce")
        if pd.isna(date):
            continue
        frame = pd.DataFrame(
            {
                "distance_m": pd.to_numeric(raw.iloc[2:, col], errors="coerce"),
                "bed_elevation_m": pd.to_numeric(raw.iloc[2:, col + 1], errors="coerce"),
            }
        ).dropna()
        frame = frame.groupby("distance_m", as_index=False)["bed_elevation_m"].mean()
        frame = frame.sort_values("distance_m").reset_index(drop=True)
        surveys[date] = frame
        rows.append(frame.assign(survey_date=date))
    return surveys, pd.concat(rows, ignore_index=True)


def interpolate_common(surveys, step):
    lower = max(frame.distance_m.min() for frame in surveys.values())
    upper = min(frame.distance_m.max() for frame in surveys.values())
    grid = np.arange(np.ceil(lower / step) * step, upper + 1e-9, step)
    values = []
    for date, frame in surveys.items():
        values.append(np.interp(grid, frame.distance_m, frame.bed_elevation_m))
    return grid, np.asarray(values), lower, upper


def save_overview(surveys, output):
    colors = colormaps["viridis"](np.linspace(0.05, 0.95, len(surveys)))
    fig, ax = plt.subplots(figsize=(14, 7.5))
    for (date, frame), color in zip(surveys.items(), colors):
        ax.plot(frame.distance_m, frame.bed_elevation_m, color=color, lw=1.7, label=date.strftime("%Y-%m-%d"))
        ax.scatter(frame.distance_m, frame.bed_elevation_m, color=color, s=6, alpha=0.35)
    ax.set(title="附件2：历次河床横断面原始测点总览", xlabel="距固定岸边起点的距离（m）", ylabel="河底高程（m，1985国家高程基准）")
    ax.legend(ncol=3, fontsize=9, frameon=False)
    ax.grid(axis="x", alpha=0.12)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_facets(surveys, output):
    fig, axes = plt.subplots(3, 3, figsize=(15, 11), sharex=False, sharey=True)
    colors = colormaps["viridis"](np.linspace(0.05, 0.95, len(surveys)))
    for ax, ((date, frame), color) in zip(axes.flat, zip(surveys.items(), colors)):
        ax.plot(frame.distance_m, frame.bed_elevation_m, color=color, lw=1.5)
        ax.scatter(frame.distance_m, frame.bed_elevation_m, color=color, s=8, alpha=0.55)
        ax.set_title(date.strftime("%Y-%m-%d"), fontsize=11)
        ax.set_xlabel("起点距离（m）")
        ax.set_ylabel("河底高程（m）")
    fig.suptitle("附件2：9期河床断面分面图（保留各期实际覆盖范围）", fontsize=16, y=1.01)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_common_overlay(surveys, grid, matrix, output):
    colors = colormaps["viridis"](np.linspace(0.05, 0.95, len(surveys)))
    fig, ax = plt.subplots(figsize=(14, 7.5))
    for (date, _), values, color in zip(surveys.items(), matrix, colors):
        ax.plot(grid, values, color=color, lw=1.7, label=date.strftime("%Y-%m-%d"))
    ax.set(title="共同覆盖区河床断面对比（线性插值，仅用于探索性可视化）", xlabel="距固定岸边起点的距离（m）", ylabel="河底高程（m）")
    ax.legend(ncol=3, fontsize=9, frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_heatmap(surveys, grid, matrix, output):
    labels = [date.strftime("%Y-%m-%d") for date in surveys]
    fig, ax = plt.subplots(figsize=(14, 6.8))
    image = ax.imshow(matrix, aspect="auto", cmap="terrain", extent=[grid.min(), grid.max(), len(labels) - 0.5, -0.5])
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set(title="共同覆盖区河底高程的时间—距离分布", xlabel="距固定岸边起点的距离（m）", ylabel="断面测量日期")
    ax.grid(False)
    colorbar = fig.colorbar(image, ax=ax, pad=0.015)
    colorbar.set_label("河底高程（m）")
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_changes(surveys, grid, matrix, output):
    dates = list(surveys)
    fig, axes = plt.subplots(4, 2, figsize=(15, 12), sharex=True, sharey=True)
    for index, ax in enumerate(axes.flat):
        delta = matrix[index + 1] - matrix[index]
        ax.axhline(0, color="#3D4653", lw=0.8)
        ax.plot(grid, delta, color="#3D4653", lw=0.8)
        ax.fill_between(grid, 0, delta, where=delta >= 0, color="#D55E5E", alpha=0.72, label="淤积（后期更高）")
        ax.fill_between(grid, 0, delta, where=delta < 0, color="#2878B5", alpha=0.72, label="冲刷（后期更低）")
        ax.set_title(f"{dates[index]:%Y-%m-%d} → {dates[index + 1]:%Y-%m-%d}", fontsize=10)
        ax.set_ylabel("高程变化（m）")
    for ax in axes[-1]:
        ax.set_xlabel("起点距离（m）")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.002), ncol=2, frameon=False)
    fig.suptitle("相邻测次共同覆盖区河床高程变化", fontsize=16, y=0.995)
    fig.tight_layout(rect=(0, 0.035, 1, 0.965))
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--grid-step-m", type=float, default=5.0)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    figures = run_dir / "figures"
    results = run_dir / "results"
    validation = run_dir / "validation"
    logs = run_dir / "logs"
    for folder in [figures, results, validation, logs]:
        folder.mkdir(parents=True, exist_ok=True)

    configure_plotting()
    surveys, long_data = read_surveys(args.input)
    grid, matrix, lower, upper = interpolate_common(surveys, args.grid_step_m)
    dates = list(surveys)

    long_data[["survey_date", "distance_m", "bed_elevation_m"]].to_csv(results / "attachment2_long.csv", index=False, encoding="utf-8-sig")
    common = pd.DataFrame(matrix.T, columns=[date.strftime("%Y-%m-%d") for date in dates])
    common.insert(0, "distance_m", grid)
    common.to_csv(results / "attachment2_common_grid.csv", index=False, encoding="utf-8-sig")

    summary = []
    for date, frame, values in zip(dates, surveys.values(), matrix):
        summary.append(
            {
                "survey_date": date.date(),
                "raw_points": len(frame),
                "raw_min_distance_m": frame.distance_m.min(),
                "raw_max_distance_m": frame.distance_m.max(),
                "raw_min_bed_elevation_m": frame.bed_elevation_m.min(),
                "raw_max_bed_elevation_m": frame.bed_elevation_m.max(),
                "common_mean_bed_elevation_m": values.mean(),
                "common_min_bed_elevation_m": values.min(),
                "common_thalweg_distance_m": grid[np.argmin(values)],
            }
        )
    pd.DataFrame(summary).to_csv(results / "survey_summary.csv", index=False, encoding="utf-8-sig")

    changes = []
    for index in range(len(dates) - 1):
        delta = matrix[index + 1] - matrix[index]
        changes.append(
            {
                "start_date": dates[index].date(),
                "end_date": dates[index + 1].date(),
                "days": (dates[index + 1] - dates[index]).days,
                "mean_elevation_change_m": delta.mean(),
                "signed_section_change_m2": np.trapz(delta, grid),
                "deposition_area_m2": np.trapz(np.maximum(delta, 0), grid),
                "erosion_area_m2": np.trapz(np.maximum(-delta, 0), grid),
            }
        )
    pd.DataFrame(changes).to_csv(results / "consecutive_change_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        [
            {
                "survey_count": len(surveys),
                "common_lower_m": lower,
                "common_upper_m": upper,
                "grid_step_m": args.grid_step_m,
                "common_grid_points": len(grid),
                "all_surveys_strictly_increasing_distance": all(frame.distance_m.is_monotonic_increasing for frame in surveys.values()),
                "all_common_values_finite": bool(np.isfinite(matrix).all()),
            }
        ]
    ).to_csv(validation / "visualization_checks.csv", index=False, encoding="utf-8-sig")

    save_overview(surveys, figures / "attachment2_all_cross_sections.png")
    save_facets(surveys, figures / "attachment2_cross_section_facets.png")
    save_common_overlay(surveys, grid, matrix, figures / "attachment2_common_domain_overlay.png")
    save_heatmap(surveys, grid, matrix, figures / "attachment2_bed_elevation_heatmap.png")
    save_changes(surveys, grid, matrix, figures / "attachment2_consecutive_bed_changes.png")
    (logs / "run_summary.txt").write_text(
        f"survey_count={len(surveys)}\ncommon_domain_m={lower:.3f},{upper:.3f}\ngrid_step_m={args.grid_step_m:.3f}\nfigures=5\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
