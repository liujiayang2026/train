#!/usr/bin/env python3
"""Split the dense Q1 overview into three single-purpose paper figures."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

from draw_physical_ray_geometry import CJK, CJK_BOLD, COLORS, MONO, arrow, direction, text, unit


PALETTE = {
    **COLORS,
    "shadow": "#C65366",
    "block": "#D47A35",
    "overlap": "#7856A1",
    "neutral": "#818892",
}


def load_evaluator():
    path = Path(__file__).with_name("evaluate_fixed_layout.py")
    spec = importlib.util.spec_from_file_location("q1_evaluator_split", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def new_figure():
    return plt.figure(figsize=(16, 9), dpi=180, facecolor=PALETTE["paper"])


def add_header(figure, title_value: str, subtitle: str, marker: str):
    figure.text(0.06, 0.925, title_value, fontproperties=CJK_BOLD, fontsize=22, color=PALETTE["ink"], va="top")
    figure.text(0.06, 0.875, subtitle, fontproperties=CJK, fontsize=11, color=PALETTE["muted"], va="top")
    figure.text(0.95, 0.925, marker, fontproperties=MONO, fontsize=9, color=PALETTE["muted"], ha="right", va="top")


def panel(ax, xy, width, height, face="#FAFAF7", radius=0.03):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        facecolor=face,
        edgecolor=PALETTE["hairline"],
        linewidth=1.0,
    )
    ax.add_patch(patch)
    return patch


def draw_scene_inputs(centers: np.ndarray, output: Path):
    figure = new_figure()
    add_header(
        figure,
        "评价对象与输入：60 个太阳状态作用于固定镜场",
        "题目给定镜场坐标和镜面尺寸；逐月只改变太阳位置与 DNI，不改变镜场布局",
        "INPUT / A",
    )
    grid = figure.add_gridspec(1, 2, left=0.06, right=0.95, top=0.80, bottom=0.10, width_ratios=[0.38, 0.62], wspace=0.10)
    schedule = figure.add_subplot(grid[0, 0])
    field = figure.add_subplot(grid[0, 1])

    schedule.set_xlim(0, 1)
    schedule.set_ylim(0, 1)
    schedule.axis("off")
    text(schedule, 0.02, 0.96, "A  时间与辐照输入", size=13, bold=True, va="top")
    schedule.add_patch(Circle((0.20, 0.71), 0.09, facecolor=PALETTE["solar"], edgecolor="none"))
    for angle in np.linspace(0, 360, 12, endpoint=False):
        ray = direction(float(angle))
        schedule.plot(
            [0.20 + 0.11 * ray[0], 0.20 + 0.15 * ray[0]],
            [0.71 + 0.11 * ray[1], 0.71 + 0.15 * ray[1]],
            color=PALETTE["solar"],
            linewidth=1.4,
        )
    text(schedule, 0.37, 0.76, "太阳位置", size=12, bold=True)
    text(schedule, 0.37, 0.69, "DNI", size=10.5, color=PALETTE["solar"], bold=True)

    months = np.arange(1, 13)
    month_x = np.linspace(0.07, 0.93, 12)
    schedule.plot([0.07, 0.93], [0.48, 0.48], color=PALETTE["hairline"], linewidth=1.1)
    schedule.scatter(month_x, np.full(12, 0.48), s=24, facecolor=PALETTE["paper"], edgecolor=PALETTE["ray"], linewidth=1.2, zorder=3)
    for month, x in zip(months, month_x):
        schedule.text(x, 0.42, str(month), fontproperties=MONO, fontsize=7.5, color=PALETTE["muted"], ha="center")
    text(schedule, 0.07, 0.55, "每月 21 日", size=10, color=PALETTE["muted"])

    times = ["9:00", "10:30", "12:00", "13:30", "15:00"]
    time_x = np.linspace(0.10, 0.90, 5)
    for x, label in zip(time_x, times):
        schedule.add_patch(Circle((x, 0.25), 0.029, facecolor=PALETTE["solar"], edgecolor="none"))
        schedule.text(x, 0.17, label, fontproperties=MONO, fontsize=8.3, color=PALETTE["ink"], ha="center")
    arrow(schedule, (0.10, 0.25), (0.90, 0.25), PALETTE["hairline"], width=1.2, mutation=8, zorder=1)
    text(schedule, 0.07, 0.06, "12 个月 × 5 个时刻 = 60 个评价状态", size=10.5, color=PALETTE["ink"], bold=True)

    field.set_aspect("equal")
    field.set_facecolor(PALETTE["paper"])
    field.spines[:].set_visible(False)
    field.tick_params(length=0, labelsize=8, colors=PALETTE["muted"])
    xy = centers[:, :2]
    field.scatter(xy[:, 0], xy[:, 1], s=4.2, color=PALETTE["ray"], alpha=0.72, linewidths=0)
    field.add_patch(Circle((0, 0), 350, fill=False, edgecolor=PALETTE["hit"], linewidth=1.5))
    field.add_patch(Circle((0, 0), 100, facecolor="#E9D8D4", edgecolor=PALETTE["miss"], linewidth=1.0, alpha=0.72))
    field.scatter(0, 0, s=44, color=PALETTE["receiver"], zorder=5)
    field.set_xlim(-370, 370)
    field.set_ylim(-370, 370)
    field.set_xticks([-300, 0, 300])
    field.set_yticks([-300, 0, 300])
    text(field, -355, 345, "B  固定镜场几何", size=13, bold=True)
    text(field, 0, -30, "吸收塔", size=8.5, color=PALETTE["receiver"], ha="center")
    text(field, 235, 327, "1745 面定日镜", size=10.5, color=PALETTE["ray"], bold=True, ha="center")
    text(field, 250, -335, "中心距 100-350 m", size=9.5, color=PALETTE["muted"], ha="center")

    figure.text(0.50, 0.045, "输入图：只定义评价对象与时空范围，不展示算法或计算结果", fontproperties=CJK, fontsize=10, color=PALETTE["muted"], ha="center")
    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def draw_reflection_icon(ax, origin):
    center = np.asarray(origin, dtype=float)
    sun = unit(np.array([-0.30, 0.954]))
    receiver_direction = unit(np.array([0.82, 0.57]))
    normal = unit(sun + receiver_direction)
    tangent = np.array([-normal[1], normal[0]])
    mirror_a = center - 0.11 * tangent
    mirror_b = center + 0.11 * tangent
    ax.plot([mirror_a[0], mirror_b[0]], [mirror_a[1], mirror_b[1]], color=PALETTE["mirror"], linewidth=8, solid_capstyle="round", zorder=6)
    ax.plot([mirror_a[0], mirror_b[0]], [mirror_a[1], mirror_b[1]], color=PALETTE["panel"], linewidth=2.5, solid_capstyle="round", zorder=7)
    arrow(ax, center + 0.20 * sun, center, PALETTE["solar"], width=2.1, mutation=10)
    arrow(ax, center, center + 0.16 * receiver_direction, PALETTE["ray"], width=2.1, mutation=10)
    ax.plot([center[0], center[0] + 0.12 * normal[0]], [center[1], center[1] + 0.12 * normal[1]], color=PALETTE["neutral"], linewidth=1.1, linestyle=(0, (3, 3)))
    return sun, receiver_direction, normal


def draw_optical_chain(output: Path):
    figure = new_figure()
    add_header(
        figure,
        "逐镜光学评价链：定向、判定、相乘",
        "每个时刻对每面镜独立计算；射线判定使用同一联合样本，损失不会重复扣除",
        "METHOD / B",
    )
    ax = figure.add_axes([0.055, 0.10, 0.90, 0.70])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    blocks = [(0.02, 0.12, 0.27, 0.76), (0.365, 0.12, 0.27, 0.76), (0.71, 0.12, 0.27, 0.76)]
    for left, bottom, width, height in blocks:
        panel(ax, (left, bottom), width, height)
    arrow(ax, (0.30, 0.50), (0.35, 0.50), PALETTE["hairline"], width=1.5, mutation=9)
    arrow(ax, (0.645, 0.50), (0.695, 0.50), PALETTE["hairline"], width=1.5, mutation=9)

    text(ax, 0.055, 0.82, "01  逐镜定向", size=13, bold=True)
    sun, receiver_direction, normal = draw_reflection_icon(ax, (0.145, 0.54))
    text(ax, 0.055, 0.28, "n_i 取太阳方向与\n接收器方向的角平分线", size=10.5, color=PALETTE["muted"], va="top")
    ax.text(0.055, 0.18, r"$\eta_{cos}=\mathbf{n}_i\cdot\mathbf{s}$", fontsize=14, color=PALETTE["ink"])

    text(ax, 0.40, 0.82, "02  联合射线判定", size=13, bold=True)
    x0, y0 = 0.405, 0.67
    steps = [
        ("入射段", "邻镜求交", PALETTE["shadow"]),
        ("反射段", "邻镜求交", PALETTE["block"]),
        ("接收器", "命中判定", PALETTE["hit"]),
    ]
    for index, (title_value, note, color) in enumerate(steps):
        y = y0 - index * 0.18
        ax.add_patch(Circle((x0 + 0.025, y), 0.024, facecolor=color, edgecolor="none"))
        text(ax, x0 + 0.065, y + 0.012, title_value, size=10.5, bold=True, va="center")
        text(ax, x0 + 0.065, y - 0.035, note, size=8.8, color=PALETTE["muted"], va="center")
        if index < len(steps) - 1:
            arrow(ax, (x0 + 0.025, y - 0.035), (x0 + 0.025, y - 0.125), PALETTE["hairline"], width=1.1, mutation=7)
    text(ax, 0.40, 0.18, "阴影、遮挡取并集；\n截断只在畅通射线中统计", size=10.2, color=PALETTE["muted"], va="top")

    text(ax, 0.745, 0.82, "03  五项效率相乘", size=13, bold=True)
    factor_labels = [r"$\eta_{cos}$", r"$\eta_{sb}$", r"$\eta_{at}$", r"$\eta_{trunc}$", r"$\eta_{ref}$"]
    factor_colors = [PALETTE["ray"], PALETTE["overlap"], PALETTE["neutral"], PALETTE["hit"], PALETTE["block"]]
    factor_x = np.linspace(0.755, 0.94, 5)
    for index, (x, label, color) in enumerate(zip(factor_x, factor_labels, factor_colors)):
        ax.add_patch(Rectangle((x - 0.017, 0.52), 0.034, 0.13, facecolor=color, edgecolor="none", alpha=0.92))
        ax.text(x, 0.47, label, fontsize=11, color=PALETTE["ink"], ha="center")
        if index < 4:
            ax.text(x + 0.023, 0.575, r"$\times$", fontsize=10, color=PALETTE["muted"], ha="center")
    ax.text(0.745, 0.32, r"$\eta_{opt}=\eta_{cos}\eta_{sb}\eta_{at}\eta_{trunc}\eta_{ref}$", fontsize=15, color=PALETTE["ink"])
    text(ax, 0.745, 0.20, "逐镜相乘，不把五项效率\n先分别平均后再相乘", size=10.2, color=PALETTE["muted"], va="top")

    reflection = -sun + 2.0 * np.dot(sun, normal) * normal
    error = float(np.linalg.norm(reflection - receiver_direction))
    figure.text(0.50, 0.045, f"方法图：方向由反射定律计算（方向误差 {error:.1e}），图中不包含结果数值", fontproperties=CJK, fontsize=10, color=PALETTE["muted"], ha="center")
    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)
    return error


def draw_aggregation_map(output: Path):
    figure = new_figure()
    add_header(
        figure,
        "汇总口径：先逐时求和，再形成月表与年表",
        "单镜效率先进入同一时刻的镜场功率；月均和年均均从逐时结果继续汇总",
        "AGGREGATION / C",
    )
    ax = figure.add_axes([0.055, 0.10, 0.90, 0.70])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    text(ax, 0.03, 0.91, "1745 面镜", size=12.5, bold=True)
    angles = np.linspace(0, 7 * math.pi, 100)
    radii = np.linspace(0.02, 0.17, 100)
    x = 0.115 + radii * np.cos(angles)
    y = 0.55 + radii * np.sin(angles)
    ax.scatter(x, y, s=11, color=PALETTE["ray"], alpha=0.78, linewidths=0)
    ax.add_patch(Circle((0.115, 0.55), 0.017, facecolor=PALETTE["receiver"], edgecolor="none"))
    text(ax, 0.115, 0.28, "同一时刻 t", size=10, color=PALETTE["muted"], ha="center")

    arrow(ax, (0.25, 0.55), (0.34, 0.55), PALETTE["hairline"], width=1.6, mutation=10)
    panel(ax, (0.35, 0.38), 0.25, 0.34, face="#EEEDEA", radius=0.025)
    text(ax, 0.475, 0.66, "逐时镜场功率", size=12.5, bold=True, ha="center")
    ax.text(
        0.475,
        0.53,
        r"$P_{\mathrm{field}}(t)=\mathrm{DNI}(t)\sum_i A_i\eta_i(t)$",
        fontsize=15,
        color=PALETTE["ink"],
        ha="center",
    )
    text(ax, 0.475, 0.43, "先对镜面求和", size=9.5, color=PALETTE["muted"], ha="center")

    arrow(ax, (0.61, 0.55), (0.69, 0.55), PALETTE["hairline"], width=1.6, mutation=10)
    grid_x = np.linspace(0.71, 0.84, 12)
    grid_y = np.linspace(0.39, 0.69, 5)
    for gx in grid_x:
        ax.scatter(np.full(5, gx), grid_y, s=18, color=PALETTE["solar"], linewidths=0)
    text(ax, 0.775, 0.78, "60 个逐时结果", size=11.5, bold=True, ha="center")
    text(ax, 0.775, 0.30, "12 月 × 5 时刻", size=9.5, color=PALETTE["muted"], ha="center")

    arrow(ax, (0.86, 0.61), (0.91, 0.69), PALETTE["hairline"], width=1.3, mutation=8)
    arrow(ax, (0.86, 0.49), (0.91, 0.40), PALETTE["hairline"], width=1.3, mutation=8)
    ax.add_patch(Rectangle((0.91, 0.59), 0.075, 0.20, facecolor=PALETTE["panel"], edgecolor=PALETTE["ray"], linewidth=1.4))
    for offset in range(1, 5):
        ax.plot([0.918, 0.977], [0.59 + offset * 0.034, 0.59 + offset * 0.034], color=PALETTE["hairline"], linewidth=0.8)
    ax.add_patch(Rectangle((0.91, 0.28), 0.075, 0.16, facecolor=PALETTE["panel"], edgecolor=PALETTE["hit"], linewidth=1.4))
    for offset in range(1, 4):
        ax.plot([0.918, 0.977], [0.28 + offset * 0.034, 0.28 + offset * 0.034], color=PALETTE["hairline"], linewidth=0.8)
    text(ax, 0.947, 0.83, "表 1", size=10.5, bold=True, ha="center")
    text(ax, 0.947, 0.54, "月均 / 12 行", size=8.5, color=PALETTE["ray"], ha="center")
    text(ax, 0.947, 0.48, "表 2", size=10.5, bold=True, ha="center")
    text(ax, 0.947, 0.23, "年均 / 1 行", size=8.5, color=PALETTE["hit"], ha="center")

    figure.text(0.50, 0.045, "口径图：用于解释表 1 / 表 2 的数据来源；实际数值应使用正式结果表或月度结果图", fontproperties=CJK, fontsize=10, color=PALETTE["muted"], ha="center")
    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def write_checks(centers, monthly, annual, reflection_error, path: Path):
    checks = {
        "mirror_count": int(len(centers)),
        "monthly_row_count": int(len(monthly)),
        "evaluation_time_count": int(len(monthly) * 5),
        "annual_row_count": 1,
        "annual_avg_optical_efficiency": float(annual["avg_optical_efficiency"]),
        "annual_field_power_mw": float(annual["field_power_mw"]),
        "annual_unit_area_power_kw_m2": float(annual["unit_area_power_kw_m2"]),
        "schematic_reflection_direction_error": reflection_error,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--monthly-results", required=True, type=Path)
    parser.add_argument("--annual-results", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()

    evaluator = load_evaluator()
    centers = evaluator.read_centers(args.input)
    monthly = read_csv_rows(args.monthly_results)
    annual_rows = read_csv_rows(args.annual_results)
    if len(monthly) != 12 or len(annual_rows) != 1:
        raise ValueError("Expected 12 monthly rows and one annual row")

    figure_dir = args.run_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    draw_scene_inputs(centers, figure_dir / "scene-inputs.png")
    reflection_error = draw_optical_chain(figure_dir / "per-mirror-optical-chain.png")
    draw_aggregation_map(figure_dir / "aggregation-to-tables.png")
    write_checks(centers, monthly, annual_rows[0], reflection_error, args.run_dir / "validation" / "checks.json")


if __name__ == "__main__":
    main()
