#!/usr/bin/env python3
"""Draw a cohesive, physically grounded narrative figure suite for question 1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle, Wedge
from scipy.spatial import cKDTree

from draw_physical_ray_geometry import CJK, CJK_BOLD, COLORS, MONO, arrow, direction, text, unit


MIRROR_ID = 1660
DAY_OFFSET = 306
SOLAR_TIME = 9.0
SAMPLES = 512
SEED = 202308
NEIGHBOR_RADIUS = 45.0
SOLAR_RADIUS = math.radians(0.266)

PALETTE = {
    **COLORS,
    "shadow": "#C65366",
    "shadow_fill": "#F2CBD2",
    "block": "#D47A35",
    "block_fill": "#F3D4BA",
    "overlap": "#7856A1",
    "clear_miss": "#B7473C",
    "tower": "#555C65",
}


@dataclass
class Context:
    centers: np.ndarray
    selected: int
    neighbors: np.ndarray
    dominant_neighbor: int
    sun: np.ndarray
    dni: float
    target: np.ndarray
    normals: np.ndarray
    axes_u: np.ndarray
    axes_v: np.ndarray
    uv: np.ndarray
    xi: np.ndarray
    zeta: np.ndarray
    points: np.ndarray
    disk_directions: np.ndarray
    reflected: np.ndarray
    shadow_hits: np.ndarray
    block_hits: np.ndarray
    receiver_hit: np.ndarray
    categories: np.ndarray


def load_evaluator():
    path = Path(__file__).with_name("evaluate_fixed_layout.py")
    spec = importlib.util.spec_from_file_location("q1_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def hit_matrix(points, directions, candidate_ids, centers, normals, axes_u, axes_v, eps):
    c = centers[candidate_ids]
    n = normals[candidate_ids]
    u = axes_u[candidate_ids]
    v = axes_v[candidate_ids]
    denominator = directions @ n.T
    numerator = np.sum(c * n, axis=1)[None, :] - points @ n.T
    valid = np.abs(denominator) > eps
    lam = np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=valid)
    valid &= lam > 1.0e-7
    local_u = points @ u.T + lam * (directions @ u.T) - np.sum(c * u, axis=1)[None, :]
    local_v = points @ v.T + lam * (directions @ v.T) - np.sum(c * v, axis=1)[None, :]
    valid &= np.abs(local_u) <= 3.0 + 1.0e-8
    valid &= np.abs(local_v) <= 3.0 + 1.0e-8
    return valid


def build_context(input_path: Path) -> Context:
    evaluator = load_evaluator()
    centers = evaluator.read_centers(input_path)
    _, sun, dni = evaluator.solar_state(DAY_OFFSET, SOLAR_TIME)
    target, _, normals, axes_u, axes_v = evaluator.mirror_frames(centers, sun)
    uv = evaluator.sobol_samples(SAMPLES, SEED)
    disk_directions = evaluator.solar_disk_directions(sun, uv)
    xi = 6.0 * (uv[:, 0] - 0.5)
    zeta = 6.0 * (uv[:, 1] - 0.5)

    selected = MIRROR_ID - 1
    tree = cKDTree(centers[:, :2])
    neighbors = np.asarray(
        [index for index in tree.query_ball_point(centers[selected, :2], NEIGHBOR_RADIUS) if index != selected],
        dtype=int,
    )
    points = centers[selected] + xi[:, None] * axes_u[selected] + zeta[:, None] * axes_v[selected]
    reflected = -disk_directions + 2.0 * (disk_directions @ normals[selected])[:, None] * normals[selected]
    reflected /= np.linalg.norm(reflected, axis=1)[:, None]
    shadow_hits = hit_matrix(
        points, disk_directions, neighbors, centers, normals, axes_u, axes_v, evaluator.EPS
    )
    block_hits = hit_matrix(
        points, reflected, neighbors, centers, normals, axes_u, axes_v, evaluator.EPS
    )
    receiver_hit = evaluator.ray_hits_receiver(points, reflected)

    shadow = np.any(shadow_hits, axis=1)
    blocked = np.any(block_hits, axis=1)
    clear = ~(shadow | blocked)
    categories = np.full(SAMPLES, 0, dtype=int)
    categories[shadow & ~blocked] = 1
    categories[blocked & ~shadow] = 2
    categories[shadow & blocked] = 3
    categories[clear & ~receiver_hit] = 4

    combined_hits = np.sum(shadow_hits | block_hits, axis=0)
    dominant_neighbor = int(neighbors[int(np.argmax(combined_hits))])
    return Context(
        centers=centers,
        selected=selected,
        neighbors=neighbors,
        dominant_neighbor=dominant_neighbor,
        sun=sun,
        dni=dni,
        target=target,
        normals=normals,
        axes_u=axes_u,
        axes_v=axes_v,
        uv=uv,
        xi=xi,
        zeta=zeta,
        points=points,
        disk_directions=disk_directions,
        reflected=reflected,
        shadow_hits=shadow_hits,
        block_hits=block_hits,
        receiver_hit=receiver_hit,
        categories=categories,
    )


def new_figure():
    return plt.figure(figsize=(16, 9), dpi=180, facecolor=PALETTE["paper"])


def add_header(figure, title_value: str, subtitle: str, marker: str):
    figure.text(0.055, 0.945, title_value, fontproperties=CJK_BOLD, fontsize=23, color=PALETTE["ink"], va="top")
    figure.text(0.055, 0.905, subtitle, fontproperties=CJK, fontsize=11.5, color=PALETTE["muted"], va="top")
    figure.text(0.96, 0.942, marker, fontproperties=MONO, fontsize=9, color=PALETTE["muted"], ha="right", va="top")


def rounded_panel(ax, xy, width, height, face=None, edge=None, radius=0.08, linewidth=1.0):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle=f"round,pad=0.015,rounding_size={radius}",
        facecolor=face or PALETTE["panel"],
        edgecolor=edge or PALETTE["hairline"],
        linewidth=linewidth,
    )
    ax.add_patch(patch)
    return patch


def draw_workflow_icon(ax, index, center):
    x, y = center
    if index == 0:
        ax.add_patch(Circle((x - 0.12, y + 0.1), 0.12, facecolor=PALETTE["solar"], edgecolor="none"))
        for hour_angle in (-55, -20, 15, 50):
            ray = direction(hour_angle)
            ax.plot([x - 0.12, x - 0.12 + 0.18 * ray[0]], [y + 0.1, y + 0.1 + 0.18 * ray[1]], color=PALETTE["solar"], linewidth=1.4)
        ax.text(x + 0.18, y - 0.03, "60", fontproperties=MONO, fontsize=25, color=PALETTE["ink"], ha="center")
    elif index == 1:
        angles = np.linspace(0, 2 * math.pi, 34, endpoint=False)
        radii = np.linspace(0.18, 0.36, 34)
        ax.scatter(x + radii * np.cos(angles), y + radii * np.sin(angles), s=5, color=PALETTE["ray"])
        ax.add_patch(Circle((x, y), 0.05, facecolor=PALETTE["tower"], edgecolor="none"))
    elif index == 2:
        ax.plot([x - 0.28, x + 0.15], [y - 0.1, y - 0.18], color=PALETTE["mirror"], linewidth=6, solid_capstyle="round")
        arrow(ax, (x - 0.10, y + 0.22), (x - 0.02, y - 0.11), PALETTE["solar"], width=1.6, mutation=7)
        arrow(ax, (x - 0.02, y - 0.11), (x + 0.28, y + 0.12), PALETTE["ray"], width=1.6, mutation=7)
    elif index == 3:
        grid = np.arange(5)
        xx, yy = np.meshgrid(grid, grid)
        colors = [PALETTE["hit"], PALETTE["shadow"], PALETTE["block"], PALETTE["overlap"]]
        for row, col in zip(xx.ravel(), yy.ravel()):
            ax.scatter(x - 0.25 + row * 0.1, y - 0.2 + col * 0.1, s=12, color=colors[(row + 2 * col) % 4])
    elif index == 4:
        factors = [PALETTE["shadow"], PALETTE["ray"], PALETTE["muted"], PALETTE["block"], PALETTE["hit"]]
        for offset, color in enumerate(factors):
            ax.add_patch(Rectangle((x - 0.31 + offset * 0.13, y - 0.08), 0.09, 0.18, facecolor=color, edgecolor="none", alpha=0.9))
    else:
        heights = [0.18, 0.3, 0.42, 0.26, 0.48]
        for offset, height in enumerate(heights):
            ax.add_patch(Rectangle((x - 0.3 + offset * 0.13, y - 0.22), 0.08, height, facecolor=PALETTE["ray"], edgecolor="none", alpha=0.85))
        ax.plot([x - 0.32, x + 0.28], [y - 0.22, y - 0.22], color=PALETTE["ink"], linewidth=0.8)


def draw_narrative_flow(output: Path):
    figure = new_figure()
    add_header(
        figure,
        "问题一：把 53,606,400 条射线汇总成两张结果表",
        "固定镜场不是优化题；核心任务是逐时、逐镜评估每一份太阳能最终去了哪里",
        "NARRATIVE / 01",
    )
    ax = figure.add_axes([0.045, 0.10, 0.91, 0.72])
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 1)
    ax.axis("off")
    stages = [
        ("01", "太阳与 DNI", "12 个月 × 5 时刻"),
        ("02", "1745 面定日镜", "固定坐标与尺寸"),
        ("03", "逐镜定向", "法向与余弦效率"),
        ("04", "联合射线", "阴影·遮挡·截断"),
        ("05", "五项效率", "逐镜相乘，不乘平均值"),
        ("06", "逐时汇总", "功率求和后再平均"),
    ]
    for index, (number, title_value, note) in enumerate(stages):
        left = index + 0.08
        rounded_panel(ax, (left, 0.22), 0.76, 0.56, face=PALETTE["panel"], radius=0.035)
        ax.text(left + 0.07, 0.70, number, fontproperties=MONO, fontsize=9, color=PALETTE["muted"], va="center")
        text(ax, left + 0.07, 0.34, title_value, size=11.2, bold=True)
        text(ax, left + 0.07, 0.28, note, size=8.2, color=PALETTE["muted"])
        draw_workflow_icon(ax, index, (left + 0.38, 0.53))
        if index < len(stages) - 1:
            arrow(ax, (left + 0.80, 0.50), (left + 1.02, 0.50), PALETTE["hairline"], width=1.4, mutation=8, zorder=2)
    ax.plot([0.15, 5.85], [0.12, 0.12], color=PALETTE["hairline"], linewidth=0.8)
    ax.text(0.15, 0.06, "INPUT", fontproperties=MONO, fontsize=8, color=PALETTE["muted"])
    ax.text(5.85, 0.06, "TABLE 1 / TABLE 2", fontproperties=MONO, fontsize=8, color=PALETTE["muted"], ha="right")
    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def draw_field_to_neighbor(context: Context, output: Path):
    figure = new_figure()
    add_header(
        figure,
        "从全镜场缩放到一面镜的候选邻域",
        "全场用于功率求和；局部 45 m 邻域用于判断哪些镜面可能截断入射或反射光路",
        "SCALE / 02",
    )
    grid = figure.add_gridspec(1, 2, left=0.06, right=0.95, top=0.82, bottom=0.10, width_ratios=[1.02, 0.98], wspace=0.16)
    field = figure.add_subplot(grid[0, 0])
    local = figure.add_subplot(grid[0, 1])

    for axis in (field, local):
        axis.set_aspect("equal")
        axis.set_facecolor(PALETTE["paper"])
        axis.spines[:].set_visible(False)
        axis.tick_params(labelsize=8, colors=PALETTE["muted"], length=0)

    xy = context.centers[:, :2]
    field.scatter(xy[:, 0], xy[:, 1], s=3.4, color=PALETTE["ray"], alpha=0.65, linewidths=0)
    field.add_patch(Circle((0, 0), 350, fill=False, edgecolor=PALETTE["hit"], linewidth=1.4))
    field.add_patch(Circle((0, 0), 100, facecolor="#E7D5D1", edgecolor=PALETTE["miss"], linewidth=1.0, alpha=0.65))
    selected_xy = xy[context.selected]
    field.scatter(*selected_xy, s=60, facecolor=PALETTE["miss"], edgecolor=PALETTE["paper"], linewidth=1.5, zorder=5)
    field.plot([0, selected_xy[0]], [0, selected_xy[1]], color=PALETTE["hairline"], linewidth=0.9, linestyle=(0, (4, 4)))
    field.scatter(0, 0, s=38, color=PALETTE["tower"], zorder=5)
    field.set_xlim(-370, 370)
    field.set_ylim(-370, 370)
    field.set_xticks([-300, 0, 300])
    field.set_yticks([-300, 0, 300])
    text(field, -355, 340, "A  全场 / 1745 面", size=12.5, bold=True)
    text(field, selected_xy[0] - 20, selected_xy[1] + 28, "#1660", size=9, color=PALETTE["miss"], ha="center")
    text(field, 0, -32, "吸收塔", size=8.5, color=PALETTE["tower"], ha="center")

    local_xy = xy[context.neighbors]
    local.scatter(local_xy[:, 0], local_xy[:, 1], s=30, facecolor=PALETTE["panel"], edgecolor=PALETTE["ray"], linewidth=1.2)
    local.add_patch(Circle(selected_xy, NEIGHBOR_RADIUS, facecolor=PALETTE["ray_fill"], edgecolor=PALETTE["ray"], linewidth=1.2, alpha=0.22))
    dominant_xy = xy[context.dominant_neighbor]
    local.scatter(*dominant_xy, s=88, facecolor=PALETTE["block"], edgecolor=PALETTE["paper"], linewidth=1.4, zorder=6)
    local.scatter(*selected_xy, s=90, facecolor=PALETTE["miss"], edgecolor=PALETTE["paper"], linewidth=1.5, zorder=7)
    local.plot([selected_xy[0], dominant_xy[0]], [selected_xy[1], dominant_xy[1]], color=PALETTE["overlap"], linewidth=2.0, alpha=0.8)

    sun_xy = unit(context.sun[:2])
    tower_xy = unit(-selected_xy)
    arrow(local, selected_xy, selected_xy + 31 * sun_xy, PALETTE["solar"], width=2.0, mutation=10, zorder=8)
    arrow(local, selected_xy, selected_xy + 31 * tower_xy, PALETTE["ray"], width=2.0, mutation=10, zorder=8)
    radius = 53
    local.set_xlim(selected_xy[0] - radius, selected_xy[0] + radius)
    local.set_ylim(selected_xy[1] - radius, selected_xy[1] + radius)
    local.set_xticks([])
    local.set_yticks([])
    text(local, selected_xy[0] - 50, selected_xy[1] + 48, "B  45 m 邻域 / 15 面候选镜", size=12.5, bold=True)
    text(local, selected_xy[0] - 4, selected_xy[1] - 7, "#1660", size=9, color=PALETTE["miss"], ha="center")
    text(local, dominant_xy[0] + 8, dominant_xy[1] + 7, "#1529\n主导损失镜", size=8.5, color=PALETTE["block"], ha="center")
    text(local, *(selected_xy + 35 * sun_xy), "太阳方向 s", size=8.5, color=PALETTE["solar"], ha="center")
    text(local, *(selected_xy + 35 * tower_xy), "接收器方向 t_i", size=8.5, color=PALETTE["ray"], ha="center")

    figure.text(0.50, 0.055, "全场坐标  →  45 m 保守候选集  →  用方向向量对每条射线做镜面求交", fontproperties=CJK, fontsize=10.5, color=PALETTE["muted"], ha="center")
    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def mirror_frame_2d(center, sun, receiver, length=1.8):
    target = unit(receiver - center)
    normal = unit(sun + target)
    tangent = np.array([-normal[1], normal[0]])
    return center - 0.5 * length * tangent, center + 0.5 * length * tangent, normal, tangent, target


def draw_mirror_2d(ax, center, sun, receiver, color, label, length=1.8):
    p1, p2, normal, tangent, target = mirror_frame_2d(center, sun, receiver, length)
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=color, linewidth=8, solid_capstyle="round", zorder=7)
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=PALETTE["panel"], linewidth=2.6, solid_capstyle="round", zorder=8)
    text(ax, center[0], center[1] - 0.55, label, size=9, color=color, ha="center")
    return normal, tangent, target


def setup_path_axis(ax, title_value):
    ax.set_xlim(-1.2, 9.8)
    ax.set_ylim(-1.1, 6.6)
    ax.set_aspect("equal")
    ax.axis("off")
    text(ax, -1.0, 6.25, title_value, size=13, bold=True)
    ax.plot([-1, 9.4], [-0.55, -0.55], color=PALETTE["hairline"], linewidth=0.8)


def draw_shadow_blocking_physical(output: Path):
    figure = new_figure()
    add_header(
        figure,
        "阴影与遮挡：损失发生在两条不同的光路",
        "所有镜面姿态由同一个太阳方向和各自的接收器方向计算；示意角度与交点可复算",
        "PATHS / 03",
    )
    grid = figure.add_gridspec(1, 2, left=0.05, right=0.96, top=0.82, bottom=0.08, wspace=0.09)
    left = figure.add_subplot(grid[0, 0])
    right = figure.add_subplot(grid[0, 1])
    receiver = np.array([8.6, 4.7])
    sun = direction(118.0)
    target = np.array([1.0, 0.65])

    setup_path_axis(left, "A  阴影 / 阳光尚未到达待评价镜")
    shadow_blocker = target + 3.0 * sun
    _, target_tangent, _ = draw_mirror_2d(left, target, sun, receiver, PALETTE["mirror"], "待评价镜 i", 2.0)
    draw_mirror_2d(left, shadow_blocker, sun, receiver, PALETTE["block"], "遮光镜 j", 1.7)
    p = target + 0.15 * target_tangent
    upstream = p + 5.0 * sun
    arrow(left, upstream, shadow_blocker + 0.08 * sun, PALETTE["solar"], width=2.4, mutation=11, zorder=4)
    left.plot([shadow_blocker[0], p[0]], [shadow_blocker[1], p[1]], color=PALETTE["shadow"], linewidth=2.0, linestyle=(0, (5, 4)), zorder=3)
    left.add_patch(Polygon(np.vstack([shadow_blocker + [-0.7, 0.18], shadow_blocker + [0.65, -0.18], target + [0.85, 0.12], target + [-0.7, -0.12]]), closed=True, facecolor=PALETTE["shadow_fill"], edgecolor="none", alpha=0.5, zorder=1))
    left.scatter(*p, s=38, color=PALETTE["shadow"], zorder=9)
    text(left, 1.55, 2.15, "未到达的延长线", size=8.5, color=PALETTE["shadow"], ha="center")
    left.text(2.25, 2.82, r"$P+\lambda s_q$", fontsize=12, color=PALETTE["shadow"], fontweight="bold")
    text(left, -0.85, -0.9, "从 P 朝太阳回溯，先遇到镜 j  →  该样本处于阴影", size=9.5, color=PALETTE["muted"])

    setup_path_axis(right, "B  遮挡 / 反射光尚未到达接收器")
    normal, target_tangent, target_direction = draw_mirror_2d(right, target, sun, receiver, PALETTE["mirror"], "待评价镜 i", 2.0)
    block_center = target + 3.8 * target_direction
    draw_mirror_2d(right, block_center, sun, receiver, PALETTE["block"], "挡光镜 k", 1.7)
    p = target
    incoming_start = p + 3.4 * sun
    arrow(right, incoming_start, p, PALETTE["solar"], width=2.0, mutation=10, zorder=4)
    arrow(right, p, block_center - 0.1 * target_direction, PALETTE["ray"], width=2.7, mutation=11, zorder=5)
    right.plot([block_center[0], receiver[0]], [block_center[1], receiver[1]], color=PALETTE["miss"], linewidth=2.0, linestyle=(0, (5, 4)), zorder=3)
    right.add_patch(Rectangle((8.35, 3.8), 0.5, 1.8, facecolor="#DFE3E3", edgecolor=PALETTE["tower"], linewidth=1.4, zorder=6))
    text(right, 8.6, 5.9, "集热器", size=9, color=PALETTE["tower"], ha="center")
    right.text(2.55, 2.12, r"$P+\lambda d_{r,i,q}$", fontsize=12, color=PALETTE["ray"], fontweight="bold")
    text(right, 6.75, 3.76, "被截断的延长线", size=8.5, color=PALETTE["miss"], ha="center")
    text(right, -0.85, -0.9, "从 P 沿反射方向前进，先遇到镜 k  →  该样本被遮挡", size=9.5, color=PALETTE["muted"])

    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def category_counts(categories):
    return {
        "clear_hit": int(np.sum(categories == 0)),
        "shadow_only": int(np.sum(categories == 1)),
        "block_only": int(np.sum(categories == 2)),
        "overlap": int(np.sum(categories == 3)),
        "clear_miss": int(np.sum(categories == 4)),
    }


def draw_real_sampling(context: Context, output: Path):
    figure = new_figure()
    add_header(
        figure,
        "一面真实定日镜的 512 条联合射线如何变成效率",
        "1 月 21 日 9:00 · 镜 #1660 · 坐标 (-175.626, 287.774, 4.000) m · Sobol seed 202308",
        "SAMPLES / 04",
    )
    grid = figure.add_gridspec(1, 2, left=0.07, right=0.95, top=0.82, bottom=0.09, width_ratios=[1.08, 0.92], wspace=0.16)
    scatter = figure.add_subplot(grid[0, 0])
    stats = figure.add_subplot(grid[0, 1])
    scatter.set_facecolor(PALETTE["paper"])
    scatter.set_aspect("equal")
    scatter.set_xlim(-3.3, 3.3)
    scatter.set_ylim(-3.75, 3.3)
    scatter.spines[:].set_visible(False)
    scatter.set_xticks([-3, 0, 3])
    scatter.set_yticks([-3, 0, 3])
    scatter.tick_params(length=0, labelsize=8, colors=PALETTE["muted"])
    scatter.add_patch(Rectangle((-3, -3), 6, 6, facecolor=PALETTE["panel"], edgecolor=PALETTE["mirror"], linewidth=1.8))

    labels = {
        0: (PALETTE["hit"], "畅通且命中 287"),
        1: (PALETTE["shadow"], "仅阴影 71"),
        2: (PALETTE["block"], "仅遮挡 58"),
        3: (PALETTE["overlap"], "阴影与遮挡重叠 85"),
        4: (PALETTE["clear_miss"], "畅通但溢出 11"),
    }
    for category, (color, label) in labels.items():
        selected = context.categories == category
        scatter.scatter(context.xi[selected], context.zeta[selected], s=18 if category != 0 else 13, color=color, alpha=0.88, linewidths=0, label=label)
    text(scatter, -3.25, 3.18, "A  镜面局部坐标中的真实样本", size=12.5, bold=True)
    scatter.set_xlabel("镜面宽度方向 ξ / m", fontproperties=CJK, fontsize=9, color=PALETTE["muted"])
    scatter.set_ylabel("镜面高度方向 ζ / m", fontproperties=CJK, fontsize=9, color=PALETTE["muted"])
    scatter.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 0.012),
        frameon=False,
        prop=CJK.copy(),
        fontsize=7.8,
        ncol=3,
        markerscale=0.9,
        columnspacing=1.2,
        handletextpad=0.45,
    )

    stats.set_xlim(0, 1)
    stats.set_ylim(0, 1)
    stats.axis("off")
    counts = category_counts(context.categories)
    clear = counts["clear_hit"] + counts["clear_miss"]
    lost = counts["shadow_only"] + counts["block_only"] + counts["overlap"]
    eta_sb = clear / SAMPLES
    eta_trunc = counts["clear_hit"] / clear

    text(stats, 0.02, 0.94, "B  两层分母，损失只扣一次", size=12.5, bold=True)
    rounded_panel(stats, (0.02, 0.69), 0.96, 0.17, face="#EEEDEA", radius=0.025)
    stats.text(0.08, 0.78, "512", fontproperties=MONO, fontsize=27, color=PALETTE["ink"], va="center")
    text(stats, 0.24, 0.79, "全部联合射线", size=10, color=PALETTE["muted"], va="center")
    arrow(stats, (0.44, 0.77), (0.61, 0.77), PALETTE["hairline"], width=1.3, mutation=8)
    text(stats, 0.67, 0.80, f"畅通 {clear}", size=11, color=PALETTE["hit"], bold=True)
    text(stats, 0.67, 0.73, f"阴影/遮挡并集 {lost}", size=9.5, color=PALETTE["overlap"])

    stats.add_patch(Rectangle((0.03, 0.59), eta_sb * 0.94, 0.035, facecolor=PALETTE["hit"], edgecolor="none"))
    stats.add_patch(Rectangle((0.03 + eta_sb * 0.94, 0.59), (1 - eta_sb) * 0.94, 0.035, facecolor=PALETTE["overlap"], edgecolor="none"))
    stats.text(0.03, 0.52, rf"$\eta_{{sb}} = {clear}/512 = {eta_sb:.4f}$", fontsize=15, color=PALETTE["ink"])

    rounded_panel(stats, (0.02, 0.26), 0.96, 0.18, face="#EEEDEA", radius=0.025)
    text(stats, 0.08, 0.36, f"在 {clear} 条畅通射线中", size=10, color=PALETTE["muted"])
    text(stats, 0.08, 0.29, f"命中 {counts['clear_hit']}   /   溢出 {counts['clear_miss']}", size=12, color=PALETTE["ink"], bold=True)
    stats.text(0.03, 0.15, rf"$\eta_{{trunc}} = {counts['clear_hit']}/{clear} = {eta_trunc:.4f}$", fontsize=15, color=PALETTE["ink"])
    stats.text(0.03, 0.055, rf"$\eta_{{sb}}\eta_{{trunc}} = {counts['clear_hit']}/512 = {counts['clear_hit']/SAMPLES:.4f}$", fontsize=14, color=PALETTE["ray"])
    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def read_csv_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def draw_monthly_story(monthly_path: Path, annual_path: Path, output: Path):
    monthly = read_csv_rows(monthly_path)
    annual = read_csv_rows(annual_path)[0]
    months = np.asarray([int(row["month"]) for row in monthly])
    optical = np.asarray([float(row["avg_optical_efficiency"]) for row in monthly])
    cosine = np.asarray([float(row["avg_cosine_efficiency"]) for row in monthly])
    shadow = np.asarray([float(row["avg_shadow_blocking_efficiency"]) for row in monthly])
    trunc = np.asarray([float(row["avg_truncation_efficiency"]) for row in monthly])
    unit_power = np.asarray([float(row["unit_area_power_kw_m2"]) for row in monthly])

    figure = new_figure()
    add_header(
        figure,
        "季节改变太阳位置，最终改变镜场效率与单位面积功率",
        "每个月先平均当天 5 个评价时刻；年均再对全部 60 个时刻等权平均",
        "RESULTS / 05",
    )
    grid = figure.add_gridspec(2, 1, left=0.07, right=0.94, top=0.73, bottom=0.11, height_ratios=[0.58, 0.42], hspace=0.12)
    efficiency_ax = figure.add_subplot(grid[0])
    power_ax = figure.add_subplot(grid[1], sharex=efficiency_ax)
    for axis in (efficiency_ax, power_ax):
        axis.set_facecolor(PALETTE["paper"])
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.grid(axis="y", color=PALETTE["hairline"], linewidth=0.7, alpha=0.65)
        axis.tick_params(length=0, colors=PALETTE["muted"], labelsize=8)

    efficiency_ax.plot(months, optical, color=PALETTE["ray"], linewidth=3.0, marker="o", markersize=4.5, label="总光学效率")
    efficiency_ax.plot(months, cosine, color="#5B7E9A", linewidth=1.6, marker="o", markersize=3, label="余弦效率")
    efficiency_ax.plot(months, shadow, color=PALETTE["block"], linewidth=1.6, marker="o", markersize=3, label="阴影遮挡效率")
    efficiency_ax.plot(months, trunc, color=PALETTE["hit"], linewidth=1.6, marker="o", markersize=3, label="截断效率")
    efficiency_ax.set_ylim(0.48, 0.98)
    efficiency_ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9])
    efficiency_ax.set_ylabel("效率", fontproperties=CJK, fontsize=9, color=PALETTE["muted"])
    efficiency_ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=4, frameon=False, prop=CJK.copy(), fontsize=8)
    efficiency_ax.tick_params(labelbottom=False)

    bar_colors = [PALETTE["solar"] if value >= np.median(unit_power) else "#D8D4CA" for value in unit_power]
    power_ax.bar(months, unit_power, width=0.62, color=bar_colors, edgecolor="none")
    power_ax.plot(months, unit_power, color=PALETTE["solar"], linewidth=1.5, marker="o", markersize=3)
    power_ax.set_ylim(0.40, 0.68)
    power_ax.set_yticks([0.45, 0.55, 0.65])
    power_ax.set_xticks(months)
    power_ax.set_xticklabels([f"{month}月" for month in months], fontproperties=CJK, fontsize=8)
    power_ax.set_ylabel("kW/m²", fontproperties=MONO, fontsize=8, color=PALETTE["muted"])
    text(power_ax, 1, unit_power[0] + 0.018, f"{unit_power[0]:.3f}", size=8, color=PALETTE["muted"], ha="center")
    text(power_ax, 6, unit_power[5] + 0.018, f"{unit_power[5]:.3f}", size=8, color=PALETTE["solar"], ha="center", bold=True)
    text(power_ax, 12, unit_power[-1] + 0.018, f"{unit_power[-1]:.3f}", size=8, color=PALETTE["muted"], ha="center")

    metrics = [
        ("年平均光学效率", float(annual["avg_optical_efficiency"]), ""),
        ("年平均输出热功率", float(annual["field_power_mw"]), " MW"),
        ("单位面积年平均功率", float(annual["unit_area_power_kw_m2"]), " kW/m²"),
    ]
    for index, (label, value, suffix) in enumerate(metrics):
        x = 0.58 + index * 0.13
        figure.text(x, 0.875, label, fontproperties=CJK, fontsize=8.3, color=PALETTE["muted"], ha="left")
        figure.text(x, 0.842, f"{value:.4f}{suffix}", fontproperties=MONO, fontsize=11.5, color=PALETTE["ink"], ha="left")

    figure.savefig(output, facecolor=PALETTE["paper"])
    plt.close(figure)


def write_validation(context: Context, path: Path):
    counts = category_counts(context.categories)
    dominant_position = int(np.where(context.neighbors == context.dominant_neighbor)[0][0])
    schematic_sun = direction(118.0)
    schematic_target = np.array([1.0, 0.65])
    schematic_receiver = np.array([8.6, 4.7])
    receiver_direction = unit(schematic_receiver - schematic_target)
    schematic_normal = unit(schematic_sun + receiver_direction)
    incident_direction = -schematic_sun
    reflected_direction = incident_direction - 2.0 * np.dot(incident_direction, schematic_normal) * schematic_normal
    shadow_blocker = schematic_target + 3.0 * schematic_sun
    shadow_offset = shadow_blocker - schematic_target
    checks = {
        "representative_month": 1,
        "representative_solar_time": SOLAR_TIME,
        "representative_mirror_id": MIRROR_ID,
        "representative_mirror_center": context.centers[context.selected].tolist(),
        "neighbor_radius_m": NEIGHBOR_RADIUS,
        "neighbor_count": len(context.neighbors),
        "dominant_neighbor_id": context.dominant_neighbor + 1,
        "dominant_neighbor_union_hit_count": int(np.sum(context.shadow_hits[:, dominant_position] | context.block_hits[:, dominant_position])),
        "sample_count": SAMPLES,
        "category_counts": counts,
        "category_count_sum": int(sum(counts.values())),
        "shadow_blocking_efficiency": (counts["clear_hit"] + counts["clear_miss"]) / SAMPLES,
        "conditional_truncation_efficiency": counts["clear_hit"] / (counts["clear_hit"] + counts["clear_miss"]),
        "joint_clear_receiver_hit_fraction": counts["clear_hit"] / SAMPLES,
        "schematic_reflection_direction_error": float(np.linalg.norm(reflected_direction - receiver_direction)),
        "schematic_shadow_collinearity_error": float(abs(schematic_sun[0] * shadow_offset[1] - schematic_sun[1] * shadow_offset[0])),
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
    figure_dir = args.run_dir / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    context = build_context(args.input)
    draw_narrative_flow(figure_dir / "fig01-q1-narrative-flow.png")
    draw_field_to_neighbor(context, figure_dir / "fig02-field-to-neighbor-scale.png")
    draw_shadow_blocking_physical(figure_dir / "fig03-shadow-vs-blocking-physical.png")
    draw_real_sampling(context, figure_dir / "fig04-real-joint-sampling.png")
    draw_monthly_story(args.monthly_results, args.annual_results, figure_dir / "fig05-monthly-results-story.png")
    write_validation(context, args.run_dir / "validation" / "geometry-checks.json")


if __name__ == "__main__":
    main()
