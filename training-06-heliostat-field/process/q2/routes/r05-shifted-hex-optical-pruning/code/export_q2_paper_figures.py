#!/usr/bin/env python3
"""Export the adopted Q2 result as a traceable paper-figure suite."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree


HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
sys.path.insert(0, str(ROUTES / "r01-common-size-field-optimization" / "code"))
from q2_model import all_states  # noqa: E402


COLORS = {
    "ink": "#263238",
    "green": "#2A7F62",
    "green_light": "#8FC6A8",
    "blue": "#2E6F9E",
    "orange": "#D97706",
    "red": "#B42318",
    "gold": "#B58A24",
    "gray": "#9AA5AB",
    "light": "#E8ECEE",
    "white": "#FFFFFF",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r05-run", required=True, type=Path)
    parser.add_argument("--spatial-run", required=True, type=Path)
    parser.add_argument("--robust-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 11,
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "axes.edgecolor": COLORS["ink"],
            "axes.linewidth": 0.9,
            "figure.facecolor": COLORS["white"],
            "axes.facecolor": COLORS["white"],
            "savefig.facecolor": COLORS["white"],
            "savefig.dpi": 300,
        }
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_figure(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    with Image.open(path) as image:
        image.convert("RGB").save(path, format="PNG", dpi=(300, 300), optimize=True)


def draw_layout_and_spacing(xy: np.ndarray, design: dict, output: Path) -> None:
    tower = np.array([float(design["tower_x"]), float(design["tower_y"])])
    spacing = float(design["width"]) + 5.0 + float(design["clearance"])
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 6.1), constrained_layout=True)

    ax = axes[0]
    ax.scatter(xy[:, 0], xy[:, 1], s=4.2, color=COLORS["green"], linewidths=0, label="定日镜中心")
    ax.add_patch(plt.Circle((0, 0), 350, fill=False, color=COLORS["ink"], linewidth=1.4, label="场地边界（350 m）"))
    ax.add_patch(
        plt.Circle(
            tower,
            100,
            fill=False,
            color=COLORS["red"],
            linestyle="--",
            linewidth=1.4,
            label="塔周禁建区（100 m）",
        )
    )
    ax.scatter([tower[0]], [tower[1]], marker="^", s=90, color=COLORS["orange"], edgecolor="white", linewidth=0.6, zorder=5, label="集热塔")
    ax.annotate("塔位 (0, -60)", tower, xytext=(12, -26), textcoords="offset points", color=COLORS["ink"], fontsize=10)
    ax.set(xlabel="东向坐标 x / m", ylabel="北向坐标 y / m", title="(a) 最终镜场与几何边界")
    ax.set_aspect("equal")
    ax.set_xlim(-370, 370)
    ax.set_ylim(-370, 370)
    ax.grid(True, color=COLORS["light"], linewidth=0.7)
    ax.legend(loc="upper right", frameon=True, framealpha=0.96, fontsize=9)

    local_center_id = int(np.argmin(np.sum((xy - np.array([0.0, 80.0])) ** 2, axis=1)))
    tree = cKDTree(xy)
    _, neighbor_ids = tree.query(xy[local_center_id], k=7)
    center = xy[local_center_id]
    local_mask = np.linalg.norm(xy - center, axis=1) <= 34.0
    ax = axes[1]
    ax.scatter(xy[local_mask, 0], xy[local_mask, 1], s=42, color=COLORS["green_light"], edgecolor=COLORS["green"], linewidth=0.6)
    ax.scatter([center[0]], [center[1]], s=75, color=COLORS["orange"], edgecolor="white", linewidth=0.7, zorder=5)
    for neighbor_id in neighbor_ids[1:]:
        neighbor = xy[int(neighbor_id)]
        ax.plot([center[0], neighbor[0]], [center[1], neighbor[1]], color=COLORS["blue"], linewidth=1.1)
    label_neighbor = xy[int(neighbor_ids[1])]
    midpoint = 0.5 * (center + label_neighbor)
    ax.annotate(
        f"中心距 {spacing:.2f} m",
        xy=midpoint,
        xytext=(18, 16),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "color": COLORS["ink"], "linewidth": 0.9},
        fontsize=10,
    )
    ax.text(
        0.03,
        0.04,
        "单镜 6.3 m × 6.3 m\n相邻行错开半个中心距\n镜面数 3168，总面积 125737.92 m²",
        transform=ax.transAxes,
        va="bottom",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": COLORS["gray"], "alpha": 0.96},
    )
    ax.set(xlabel="东向坐标 x / m", ylabel="北向坐标 y / m", title="(b) 局部六角错列单元")
    ax.set_aspect("equal")
    ax.set_xlim(center[0] - 34, center[0] + 34)
    ax.set_ylim(center[1] - 34, center[1] + 34)
    ax.grid(True, color=COLORS["light"], linewidth=0.7)
    save_figure(fig, output)


def draw_candidate_selection(initial: list[dict[str, str]], pruning: list[dict[str, str]], annual: dict, output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.4, 5.2), constrained_layout=True)
    powers = np.asarray([float(row["annual_field_power_mw"]) for row in initial])
    units = np.asarray([float(row["annual_unit_area_power_kw_m2"]) for row in initial])
    feasible = powers >= 60.0
    axes[0].scatter(powers[~feasible], units[~feasible], s=54, color=COLORS["gray"], label="64光线未达60 MW")
    axes[0].scatter(powers[feasible], units[feasible], s=58, color=COLORS["green"], label="64光线可行候选")
    selected = next(row for row in initial if row["id"] == "target-29")
    selected_power = float(selected["annual_field_power_mw"])
    selected_unit = float(selected["annual_unit_area_power_kw_m2"])
    axes[0].scatter([selected_power], [selected_unit], marker="*", s=180, color=COLORS["orange"], edgecolor=COLORS["ink"], linewidth=0.5, zorder=5, label="入选候选（64光线）")
    axes[0].axvline(60.0, color=COLORS["red"], linestyle="--", linewidth=1.3, label="60 MW约束")
    axes[0].annotate(f"入选：{selected_power:.3f} MW\n{selected_unit:.4f} kW/m²", (selected_power, selected_unit), xytext=(8, 9), textcoords="offset points", fontsize=9)
    axes[0].set(xlabel="年平均输出功率 / MW", ylabel="单位面积年平均功率 / (kW/m²)", title="(a) 64光线候选筛选")
    axes[0].grid(True, color=COLORS["light"], linewidth=0.7)
    axes[0].legend(fontsize=8.5, frameon=True)

    removed = np.asarray([int(row["removed"]) for row in pruning])
    prune_power = np.asarray([float(row["annual_field_power_mw"]) for row in pruning])
    prune_unit = np.asarray([float(row["annual_unit_area_power_kw_m2"]) for row in pruning])
    ax = axes[1]
    ax.plot(removed, prune_power, marker="o", color=COLORS["blue"], linewidth=1.8, label="64光线功率")
    ax.axhline(60.0, color=COLORS["red"], linestyle="--", linewidth=1.3, label="60 MW约束")
    ax.set(xlabel="删除低贡献镜面数 / 面", ylabel="年平均输出功率 / MW", title="(b) 删镜收益与功率约束")
    ax.set_xticks(removed)
    ax.grid(True, color=COLORS["light"], linewidth=0.7)
    max_power_index = int(np.argmax(prune_power))
    min_power_index = int(np.argmin(prune_power))
    for index, (x, y, value) in enumerate(zip(removed, prune_power, prune_unit)):
        if index == max_power_index:
            offset = -18
        elif index == min_power_index:
            offset = 11
        else:
            offset = 11 if index % 2 else -18
        ax.annotate(f"{value:.4f}", (x, y), xytext=(0, offset), textcoords="offset points", ha="center", color=COLORS["orange"], fontsize=9)
    ax.text(0.03, 0.06, "橙色数值：单位面积功率 / (kW/m²)", transform=ax.transAxes, color=COLORS["orange"], fontsize=9)
    ax.legend(loc="upper right", fontsize=8.5)
    save_figure(fig, output)


def draw_monthly_performance(monthly: list[dict[str, str]], annual: dict, output: Path) -> None:
    months = np.asarray([int(float(row["month"])) for row in monthly])
    fig, axes = plt.subplots(2, 1, figsize=(10.8, 7.5), constrained_layout=True, sharex=True)
    series = [
        ("avg_cosine_efficiency", "余弦效率", COLORS["blue"]),
        ("avg_shadow_blocking_efficiency", "阴影遮挡效率", COLORS["green"]),
        ("avg_truncation_efficiency", "截断效率", COLORS["gold"]),
        ("avg_optical_efficiency", "总光学效率", COLORS["red"]),
    ]
    for key, label, color in series:
        axes[0].plot(months, [float(row[key]) for row in monthly], marker="o", markersize=4.5, linewidth=1.7, color=color, label=label)
    axes[0].set(ylabel="效率", title="(a) 月均光学效率")
    axes[0].set_ylim(0.40, 1.00)
    axes[0].grid(True, color=COLORS["light"], linewidth=0.7)
    axes[0].legend(ncol=4, loc="lower center", fontsize=9, frameon=True)

    power = np.asarray([float(row["field_power_mw"]) for row in monthly])
    unit = np.asarray([float(row["unit_area_power_kw_m2"]) for row in monthly])
    bars = axes[1].bar(months, power, width=0.62, color=COLORS["green"], alpha=0.88, label="月均输出功率")
    axes[1].axhline(float(annual["field_power_mw"]), color=COLORS["blue"], linestyle="--", linewidth=1.2, label=f"年均 {float(annual['field_power_mw']):.3f} MW")
    axes[1].set(xlabel="月份", ylabel="输出功率 / MW", title="(b) 月均功率及单位面积功率")
    axes[1].set_xticks(months)
    axes[1].grid(axis="y", color=COLORS["light"], linewidth=0.7)
    ax2 = axes[1].twinx()
    line = ax2.plot(months, unit, marker="D", markersize=4, color=COLORS["orange"], linewidth=1.5, label="单位面积功率")[0]
    ax2.set_ylabel("单位面积功率 / (kW/m²)")
    axes[1].legend([bars, line, axes[1].lines[0]], ["月均输出功率", "单位面积功率", f"年均 {float(annual['field_power_mw']):.3f} MW"], ncol=3, loc="upper center", fontsize=9)
    save_figure(fig, output)


def draw_spatial_power(mirror_rows: list[dict[str, str]], design: dict, output: Path) -> None:
    x = np.asarray([float(row["x_m"]) for row in mirror_rows])
    y = np.asarray([float(row["y_m"]) for row in mirror_rows])
    values = np.asarray([float(row["annual_unit_area_power_kw_m2"]) for row in mirror_rows])
    tower = (float(design["tower_x"]), float(design["tower_y"]))
    fig, ax = plt.subplots(figsize=(8.9, 7.4), constrained_layout=True)
    scatter = ax.scatter(x, y, c=values, cmap="RdYlGn", vmin=float(np.min(values)), vmax=float(np.max(values)), s=9.0, linewidths=0)
    ax.add_patch(plt.Circle((0, 0), 350, fill=False, color=COLORS["ink"], linewidth=1.4, label="场地边界（350 m）"))
    ax.add_patch(plt.Circle(tower, 100, fill=False, color=COLORS["gray"], linestyle="--", linewidth=1.3, label="塔周禁建区（100 m）"))
    ax.scatter([tower[0]], [tower[1]], marker="^", s=95, color=COLORS["ink"], edgecolor="white", linewidth=0.6, label="集热塔")
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.025, shrink=0.88)
    colorbar.set_label("单位面积年平均功率 / (kW/m²)")
    ax.set(xlabel="东向坐标 x / m", ylabel="北向坐标 y / m", title="逐镜单位面积年平均功率空间分布（256光线）")
    ax.set_aspect("equal")
    ax.set_xlim(-370, 370)
    ax.set_ylim(-370, 370)
    ax.grid(True, color=COLORS["light"], linewidth=0.55)
    ax.legend(loc="lower left", fontsize=9, frameon=True, framealpha=0.95)
    save_figure(fig, output)


def draw_convergence(rows: list[dict[str, str]], output: Path) -> None:
    samples = np.asarray([int(row["samples"]) for row in rows])
    power = np.asarray([float(row["field_power_mw"]) for row in rows])
    optical = np.asarray([float(row["avg_optical_efficiency"]) for row in rows])
    truncation = np.asarray([float(row["avg_truncation_efficiency"]) for row in rows])
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 4.9), constrained_layout=True)
    axes[0].plot(samples, power, marker="o", markersize=6, color=COLORS["green"], linewidth=1.8)
    axes[0].axhline(60.0, color=COLORS["red"], linestyle="--", linewidth=1.3, label="60 MW约束")
    for x, y in zip(samples, power):
        axes[0].annotate(f"{y:.3f}", (x, y), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)
    axes[0].set(xlabel="每镜每时点联合光线数", ylabel="年平均输出功率 / MW", title="(a) 功率收敛")
    axes[0].set_xscale("log", base=2)
    axes[0].set_xticks(samples, labels=[str(value) for value in samples])
    axes[0].set_ylim(min(59.9, float(np.min(power)) - 0.08), float(np.max(power)) + 0.15)
    axes[0].grid(True, color=COLORS["light"], linewidth=0.7)
    axes[0].legend(fontsize=9)

    axes[1].plot(samples, optical, marker="o", color=COLORS["blue"], linewidth=1.8, label="总光学效率")
    axes[1].plot(samples, truncation, marker="s", color=COLORS["orange"], linewidth=1.8, label="截断效率")
    axes[1].set(xlabel="每镜每时点联合光线数", ylabel="效率", title="(b) 关键效率收敛")
    axes[1].set_xscale("log", base=2)
    axes[1].set_xticks(samples, labels=[str(value) for value in samples])
    axes[1].grid(True, color=COLORS["light"], linewidth=0.7)
    axes[1].legend(fontsize=9)
    save_figure(fig, output)


def draw_robustness(seed_rows: list[dict[str, str]], summary: dict, output: Path) -> None:
    labels = [row["seed"] for row in seed_rows]
    powers = np.asarray([float(row["field_power_mw"]) for row in seed_rows])
    mean = float(summary["mean_power_mw"])
    lcb = float(summary["lcb_power_mw"])
    std = float(summary["std_power_mw"])
    fig, ax = plt.subplots(figsize=(10.3, 5.5), constrained_layout=True)
    bars = ax.bar(labels, powers, color=[COLORS["green"], COLORS["blue"], COLORS["gold"]], width=0.58, edgecolor="white", linewidth=0.8)
    ax.axhline(60.0, color=COLORS["red"], linestyle="--", linewidth=1.4, label="功率约束 60 MW")
    ax.axhline(mean, color=COLORS["ink"], linewidth=1.3, label=f"三种子均值 {mean:.3f} MW")
    ax.axhline(lcb, color=COLORS["orange"], linestyle=":", linewidth=1.6, label=f"保守下界 {lcb:.3f} MW")
    for bar, value in zip(bars, powers):
        ax.text(bar.get_x() + bar.get_width() / 2.0, value + 0.012, f"{value:.3f}", ha="center", va="bottom", fontsize=10)
    ax.text(
        0.98,
        0.95,
        f"样本标准差：{std:.3f} MW\n最小种子余量：{float(np.min(powers)) - 60.0:.3f} MW\n下界余量：{lcb - 60.0:.3f} MW",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": COLORS["gray"], "alpha": 0.96},
    )
    ax.set(xlabel="Sobol扰码种子", ylabel="年平均输出功率 / MW", title="256光线多扰码稳定性验证")
    ax.set_ylim(59.95, max(60.64, float(np.max(powers)) + 0.08))
    ax.grid(axis="y", color=COLORS["light"], linewidth=0.7)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.42), fontsize=9, frameon=True, framealpha=1.0)
    save_figure(fig, output)


def minimum_operating_edge_height(xy: np.ndarray, design: dict) -> dict[str, float | int]:
    center_z = float(design["center_z"])
    height = float(design["height"])
    centers = np.column_stack([xy, np.full(len(xy), center_z)])
    receiver = np.array([float(design["tower_x"]), float(design["tower_y"]), 80.0])
    best = {"height_m": float("inf"), "month": 0, "solar_time": 0.0, "mirror_id": 0}
    for month, solar_time, _, sun, _ in all_states():
        target = receiver - centers
        target /= np.linalg.norm(target, axis=1)[:, None]
        normals = target + sun
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        vertical_axis_z = np.linalg.norm(normals[:, :2], axis=1)
        lower = center_z - 0.5 * height * vertical_axis_z
        index = int(np.argmin(lower))
        if lower[index] < best["height_m"]:
            best = {
                "height_m": float(lower[index]),
                "month": int(month),
                "solar_time": float(solar_time),
                "mirror_id": index + 1,
            }
    return best


def image_metadata(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        corners = [rgb.getpixel((0, 0)), rgb.getpixel((rgb.width - 1, 0)), rgb.getpixel((0, rgb.height - 1)), rgb.getpixel((rgb.width - 1, rgb.height - 1))]
        return {
            "size_px": [rgb.width, rgb.height],
            "dpi": [float(value) for value in image.info.get("dpi", (0.0, 0.0))],
            "mode": image.mode,
            "white_corner_count": sum(all(channel >= 248 for channel in pixel) for pixel in corners),
            "sha256": sha256(path),
        }


def main() -> None:
    args = parse_args()
    configure_style()
    figures = args.output / "figures"
    results = args.output / "results"
    validation = args.output / "validation"
    for folder in (figures, results, validation, args.output / "logs"):
        folder.mkdir(parents=True, exist_ok=True)

    design_path = args.r05_run / "results" / "design.json"
    positions_path = args.r05_run / "results" / "final_positions.csv"
    monthly_path = args.r05_run / "results" / "monthly_metrics.csv"
    annual_path = args.r05_run / "results" / "annual_metrics.csv"
    convergence_path = args.r05_run / "results" / "ray_convergence.csv"
    initial_path = args.r05_run / "results" / "initial64_candidates.csv"
    pruning_path = args.r05_run / "results" / "pruning_candidates.csv"
    mirror_path = args.spatial_run / "results" / "mirror_power.csv"
    seed_path = args.robust_run / "results" / "seed_metrics.csv"
    robust_summary_path = args.robust_run / "results" / "summary.json"

    design = read_json(design_path)
    positions = read_csv(positions_path)
    xy = np.asarray([[float(row["x_m"]), float(row["y_m"])] for row in positions])
    monthly = read_csv(monthly_path)
    annual = read_csv(annual_path)[0]
    convergence = read_csv(convergence_path)
    initial = read_csv(initial_path)
    pruning = read_csv(pruning_path)
    mirror_rows = read_csv(mirror_path)
    seed_rows = read_csv(seed_path)
    robust_summary = read_json(robust_summary_path)

    outputs = {
        "layout-and-spacing-paper.png": lambda path: draw_layout_and_spacing(xy, design, path),
        "candidate-selection-paper.png": lambda path: draw_candidate_selection(initial, pruning, annual, path),
        "monthly-performance-paper.png": lambda path: draw_monthly_performance(monthly, annual, path),
        "spatial-power-paper.png": lambda path: draw_spatial_power(mirror_rows, design, path),
        "ray-convergence-paper.png": lambda path: draw_convergence(convergence, path),
        "robustness-paper.png": lambda path: draw_robustness(seed_rows, robust_summary, path),
    }
    for name, drawer in outputs.items():
        drawer(figures / name)

    mirror_power_sum_mw = sum(float(row["annual_avg_power_kw"]) for row in mirror_rows) / 1000.0
    edge = minimum_operating_edge_height(xy, design)
    checks = {
        "paper_background": COLORS["white"],
        "figure_count": len(outputs),
        "mirror_count": len(xy),
        "monthly_rows": len(monthly),
        "robust_seed_count": len(seed_rows),
        "official_power_mw": float(annual["field_power_mw"]),
        "official_unit_area_power_kw_m2": float(annual["unit_area_power_kw_m2"]),
        "mirror_power_sum_mw": mirror_power_sum_mw,
        "power_conservation_error_mw": mirror_power_sum_mw - float(annual["field_power_mw"]),
        "minimum_operating_edge": edge,
        "static_vertical_envelope_clearance_m": float(design["center_z"]) - 0.5 * float(design["height"]),
        "robust_mean_power_mw": float(robust_summary["mean_power_mw"]),
        "robust_minimum_seed_power_mw": float(robust_summary["minimum_seed_power_mw"]),
        "robust_lcb_power_mw": float(robust_summary["lcb_power_mw"]),
        "all_seed_power_constraint_satisfied": bool(robust_summary["all_seed_power_constraint_satisfied"]),
        "lcb_power_constraint_satisfied": bool(robust_summary["lcb_power_constraint_satisfied"]),
        "input_sha256": {path.name: sha256(path) for path in [design_path, positions_path, monthly_path, annual_path, convergence_path, initial_path, pruning_path, mirror_path, seed_path, robust_summary_path]},
        "images": {name: image_metadata(figures / name) for name in outputs},
        "code_sha256": sha256(Path(__file__)),
    }
    (validation / "paper-figure-checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    usage = """# Q2 论文图使用说明

| 图文件 | 建议位置 | 主要用途 | 数据口径 |
|---|---|---|---|
| `layout-and-spacing-paper.png` | 模型建立/方案描述 | 说明塔位、场界、禁建区和六角错列间距 | r05 正式镜位 |
| `candidate-selection-paper.png` | 求解算法 | 说明多精度候选筛选与不删镜决策 | 64 光线筛选 + 256 光线正式复核 |
| `monthly-performance-paper.png` | 结果分析 | 解释季节变化、效率与功率关系 | r05 seed 202308，256 光线 |
| `spatial-power-paper.png` | 结果分析 | 解释逐镜功率的空间非均匀性 | r05 seed 202308，256 光线 |
| `ray-convergence-paper.png` | 稳定性分析 | 展示 32/64/128/256 光线收敛 | 相同 Sobol 扰码种子 |
| `robustness-paper.png` | 稳定性分析 | 展示三个 256 光线扰码种子及保守下界 | r08 对 r05 的复核 |

探索路线 r07、旧 r03/r05 柱图和未标注安全线的旧删镜图不进入 Q2 最终论文图组。
"""
    (results / "paper-figure-usage.md").write_text(usage, encoding="utf-8")

    summary = f"""# Q2 论文结果与稳定性摘要

- 采用方案：r05 平移六角密排；塔位 `(0, -60) m`；镜面 `6.3 m × 6.3 m`；安装高度 `3.15 m`；3168 面镜。
- 正式结果：年平均输出功率 `{float(annual['field_power_mw']):.5f} MW`；单位面积年平均功率 `{float(annual['unit_area_power_kw_m2']):.6f} kW/m²`。
- 三种子稳定性：均值 `{float(robust_summary['mean_power_mw']):.5f} MW`；最小值 `{float(robust_summary['minimum_seed_power_mw']):.5f} MW`；`mean-2sd={float(robust_summary['lcb_power_mw']):.5f} MW`。
- 地面关系：题定 60 时点实际最低边缘高度 `{float(edge['height_m']):.4f} m`；完全竖直极限姿态的理论净空为 `{float(design['center_z']) - 0.5 * float(design['height']):.4f} m`。因此不穿地，但工程安全余量有限。
- 论文措辞：称为“当前已搜索路线中的最优稳健可行方案”，不声称已证明全局最优。
"""
    (results / "paper-result-summary.md").write_text(summary, encoding="utf-8")


if __name__ == "__main__":
    main()
