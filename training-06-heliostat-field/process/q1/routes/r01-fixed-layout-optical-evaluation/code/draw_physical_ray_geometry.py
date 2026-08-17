#!/usr/bin/env python3
"""Draw a physically derived heliostat ray-cone overview."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.patches import Arc, FancyArrowPatch, Polygon, Rectangle


SOLAR_HALF_ANGLE = math.radians(0.266)
MIRROR_SIZE = 6.0
MIRROR_CENTER = np.array([0.0, 4.0])
RECEIVER_CENTER = np.array([340.0, 80.0])
RECEIVER_Z_MIN = 76.0
RECEIVER_Z_MAX = 84.0

COLORS = {
    "paper": "#F4F3EF",
    "ink": "#20242A",
    "muted": "#69717C",
    "hairline": "#CDD1D4",
    "panel": "#FAFAF7",
    "solar": "#E5AA25",
    "solar_fill": "#F7D778",
    "ray": "#276E9B",
    "ray_fill": "#BBD9E8",
    "hit": "#31825C",
    "miss": "#C84A3D",
    "mirror": "#17766B",
    "receiver": "#474E57",
}


def unit(vector: np.ndarray) -> np.ndarray:
    return vector / np.linalg.norm(vector)


def direction(angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    return np.array([math.cos(angle), math.sin(angle)])


def reflect_sun_direction(sun_direction: np.ndarray, normal: np.ndarray) -> np.ndarray:
    reflected = -sun_direction + 2.0 * np.dot(sun_direction, normal) * normal
    return unit(reflected)


def font_path(name: str) -> Path | None:
    candidates = [
        Path(r"C:\Windows\Fonts") / name,
        Path(r"C:\Users\32417\.agents\skills\canvas-design\canvas-fonts") / name,
    ]
    return next((path for path in candidates if path.exists()), None)


def font_properties(name: str, size: float):
    path = font_path(name)
    if path is not None:
        return font_manager.FontProperties(fname=path, size=size)
    return font_manager.FontProperties(size=size)


CJK = font_properties("msyh.ttc", 11)
CJK_BOLD = font_properties("msyhbd.ttc", 11)
LATIN = font_properties("InstrumentSans-Regular.ttf", 11)
MONO = font_properties("DMMono-Regular.ttf", 10)


def text(ax, x: float, y: float, value: str, *, size=11, color=None, bold=False, **kwargs):
    base = CJK_BOLD if bold else CJK
    prop = base.copy()
    prop.set_size(size)
    return ax.text(x, y, value, fontproperties=prop, color=color or COLORS["ink"], **kwargs)


def arrow(ax, start, end, color, width=1.8, mutation=11, zorder=5, alpha=1.0):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=mutation,
        linewidth=width,
        color=color,
        shrinkA=0,
        shrinkB=0,
        zorder=zorder,
        alpha=alpha,
    )
    ax.add_patch(patch)
    return patch


def convex_hull(points: np.ndarray) -> np.ndarray:
    unique = sorted({(float(x), float(y)) for x, y in points})
    if len(unique) <= 1:
        return np.asarray(unique)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return np.asarray(lower[:-1] + upper[:-1])


def setup_geometry():
    target = unit(RECEIVER_CENTER - MIRROR_CENTER)
    sun = direction(80.0)
    normal = unit(sun + target)
    tangent = np.array([-normal[1], normal[0]])
    return sun, target, normal, tangent


def draw_direction_inset(ax, sun, target, normal, tangent):
    ax.set_xlim(-1.4, 4.3)
    ax.set_ylim(-0.8, 3.25)
    ax.set_aspect("equal")
    ax.axis("off")
    text(ax, -1.28, 3.02, "01  单点反射", size=14, bold=True)
    text(ax, -1.28, 2.68, "从采样点 P 反向观察太阳圆盘", size=10, color=COLORS["muted"])

    point = np.array([0.0, 0.0])
    draw_angle = math.radians(8.0)
    center_angle = math.atan2(sun[1], sun[0])
    sun_edges = [direction(math.degrees(center_angle - draw_angle)), direction(math.degrees(center_angle + draw_angle))]
    reflected_edges = [reflect_sun_direction(edge, normal) for edge in sun_edges]

    incoming_ends = [point + 2.8 * edge for edge in sun_edges]
    reflected_ends = [point + 3.6 * edge for edge in reflected_edges]
    ax.add_patch(
        Polygon(
            np.vstack([incoming_ends[0], incoming_ends[1], point]),
            closed=True,
            facecolor=COLORS["solar_fill"],
            edgecolor="none",
            alpha=0.42,
            zorder=1,
        )
    )
    ax.add_patch(
        Polygon(
            np.vstack([point, reflected_ends[0], reflected_ends[1]]),
            closed=True,
            facecolor=COLORS["ray_fill"],
            edgecolor="none",
            alpha=0.5,
            zorder=1,
        )
    )
    for endpoint in incoming_ends:
        arrow(ax, endpoint, point, COLORS["solar"], width=1.4, mutation=8, zorder=3)
    arrow(ax, point + 3.05 * sun, point, COLORS["solar"], width=2.3, mutation=10, zorder=4)
    for endpoint in reflected_ends:
        arrow(ax, point, endpoint, COLORS["ray"], width=1.4, mutation=8, zorder=3)
    arrow(ax, point, point + 3.85 * target, COLORS["ray"], width=2.3, mutation=10, zorder=4)

    mirror_a = point - 1.05 * tangent
    mirror_b = point + 1.05 * tangent
    ax.plot([mirror_a[0], mirror_b[0]], [mirror_a[1], mirror_b[1]], color=COLORS["mirror"], linewidth=7, solid_capstyle="round", zorder=6)
    ax.plot([mirror_a[0], mirror_b[0]], [mirror_a[1], mirror_b[1]], color=COLORS["panel"], linewidth=2.2, solid_capstyle="round", zorder=7)
    ax.plot([point[0], point[0] + 1.35 * normal[0]], [point[1], point[1] + 1.35 * normal[1]], color=COLORS["muted"], linewidth=1.3, linestyle=(0, (3, 3)), zorder=5)
    ax.scatter(*point, s=38, color=COLORS["ink"], zorder=8)

    arc_in = Arc(point, 1.0, 1.0, angle=0, theta1=72, theta2=88, color=COLORS["solar"], linewidth=1.4)
    reflected_angles = sorted(math.degrees(math.atan2(v[1], v[0])) for v in reflected_edges)
    arc_out = Arc(point, 1.35, 1.35, angle=0, theta1=reflected_angles[0], theta2=reflected_angles[1], color=COLORS["ray"], linewidth=1.4)
    ax.add_patch(arc_in)
    ax.add_patch(arc_out)

    text(ax, -0.18, -0.42, "P", size=11, bold=True)
    text(ax, 0.62, 1.37, "n", size=10, color=COLORS["muted"])
    text(ax, -0.72, 1.86, "入射方向锥", size=10, color=COLORS["solar"])
    text(ax, 2.22, 0.75, "反射方向锥", size=10, color=COLORS["ray"])
    text(ax, -1.22, -0.68, "共同顶点：P", size=8.5, color=COLORS["muted"])
    text(ax, 0.92, -0.68, "θ⊙ = 0.266°（角度已放大）", size=9.5, color=COLORS["ink"])


def draw_fact_panel(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    text(ax, 0.02, 0.90, "物理约束", size=14, bold=True)
    facts = [
        ("反射 / REFLECTION", "中心光严格满足入射角 = 反射角"),
        ("方向锥 / CONE", "反射保持太阳方向锥的半角"),
        ("平面镜 / FLAT", "不同镜面点的中心反射线彼此平行"),
        ("接收器 / RECEIVER", "中心 80 m；有效侧壁 76–84 m"),
    ]
    for index, (tag, value) in enumerate(facts):
        y = 0.70 - index * 0.17
        ax.plot([0.02, 0.97], [y - 0.045, y - 0.045], color=COLORS["hairline"], linewidth=0.8)
        text(ax, 0.02, y + 0.035, tag, size=8.5, color=COLORS["muted"], va="center")
        text(ax, 0.28, y + 0.035, value, size=9.5, va="center")
    legend = [(COLORS["solar"], "入射"), (COLORS["ray"], "中心反射"), (COLORS["hit"], "命中"), (COLORS["miss"], "溢出")]
    for index, (color, label) in enumerate(legend):
        x = 0.03 + index * 0.23
        ax.plot([x, x + 0.055], [0.06, 0.06], color=color, linewidth=3.2, solid_capstyle="round")
        text(ax, x + 0.07, 0.06, label, size=8.5, color=COLORS["muted"], va="center")


def draw_main_geometry(ax, sun, target, normal, tangent):
    ax.set_xlim(-30, 370)
    ax.set_ylim(-6, 100)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    text(ax, -28, 97, "02  有限平面镜到有限接收器", size=14, bold=True)
    text(ax, -28, 91, "光束先由镜面尺寸与太阳角生成，再与接收器求交", size=10, color=COLORS["muted"])

    ax.plot([-25, 365], [0, 0], color=COLORS["hairline"], linewidth=1.2, zorder=0)
    mirror_offsets = np.linspace(-MIRROR_SIZE / 2, MIRROR_SIZE / 2, 7)
    mirror_points = np.array([MIRROR_CENTER + offset * tangent for offset in mirror_offsets])
    solar_angles = [80.0 - math.degrees(SOLAR_HALF_ANGLE), 80.0, 80.0 + math.degrees(SOLAR_HALF_ANGLE)]
    sun_directions = [direction(value) for value in solar_angles]
    reflected_directions = [reflect_sun_direction(value, normal) for value in sun_directions]

    endpoints = []
    rays = []
    for point in mirror_points:
        for ray_direction in reflected_directions:
            lam = (RECEIVER_CENTER[0] - point[0]) / ray_direction[0]
            endpoint = point + lam * ray_direction
            endpoints.append(endpoint)
            rays.append((point, endpoint, RECEIVER_Z_MIN <= endpoint[1] <= RECEIVER_Z_MAX))

    hull = convex_hull(np.vstack([mirror_points, np.asarray(endpoints)]))
    ax.add_patch(Polygon(hull, closed=True, facecolor=COLORS["ray_fill"], edgecolor="none", alpha=0.28, zorder=1))

    for point in mirror_points[::2]:
        start = point + 23.0 * sun
        arrow(ax, start, point, COLORS["solar"], width=1.05, mutation=6, zorder=3, alpha=0.68)

    for point, endpoint, hit in rays:
        color = COLORS["hit"] if hit else COLORS["miss"]
        ax.plot([point[0], endpoint[0]], [point[1], endpoint[1]], color=color, linewidth=0.9, alpha=0.34, zorder=2)

    arrow(ax, MIRROR_CENTER, RECEIVER_CENTER, COLORS["ray"], width=2.2, mutation=9, zorder=5)
    arrow(ax, MIRROR_CENTER + 18.0 * sun, MIRROR_CENTER, COLORS["solar"], width=2.2, mutation=9, zorder=5)

    mirror_a = MIRROR_CENTER - 0.5 * MIRROR_SIZE * tangent
    mirror_b = MIRROR_CENTER + 0.5 * MIRROR_SIZE * tangent
    ax.plot([mirror_a[0], mirror_b[0]], [mirror_a[1], mirror_b[1]], color=COLORS["mirror"], linewidth=5.5, solid_capstyle="round", zorder=7)
    ax.scatter(mirror_points[:, 0], mirror_points[:, 1], s=10, color=COLORS["panel"], edgecolor=COLORS["mirror"], linewidth=0.5, zorder=8)

    receiver_width = 5.0
    ax.add_patch(Rectangle((RECEIVER_CENTER[0] - receiver_width / 2, 0), receiver_width, RECEIVER_Z_MIN, facecolor="#D9D7D0", edgecolor="none", zorder=1))
    ax.add_patch(Rectangle((RECEIVER_CENTER[0] - receiver_width / 2, RECEIVER_Z_MIN), receiver_width, RECEIVER_Z_MAX - RECEIVER_Z_MIN, facecolor="#DFE3E3", edgecolor=COLORS["receiver"], linewidth=1.6, zorder=6))
    ax.scatter(*RECEIVER_CENTER, s=24, color=COLORS["receiver"], zorder=8)

    hit_endpoints = [end for _, end, hit in rays if hit]
    miss_endpoints = [end for _, end, hit in rays if not hit]
    if hit_endpoints:
        hit_array = np.asarray(hit_endpoints)
        ax.scatter(hit_array[:, 0], hit_array[:, 1], s=14, color=COLORS["hit"], zorder=9)
    if miss_endpoints:
        miss_array = np.asarray(miss_endpoints)
        ax.scatter(miss_array[:, 0], miss_array[:, 1], s=18, marker="x", linewidth=1.2, color=COLORS["miss"], zorder=9)

    ax.annotate("", xy=(358, 80), xytext=(358, 0), arrowprops={"arrowstyle": "<->", "color": COLORS["receiver"], "linewidth": 1.2})
    text(ax, 361, 40, "集热器中心 80 m", size=9.5, color=COLORS["receiver"], rotation=90, ha="center", va="center")
    ax.plot([334, 350], [RECEIVER_Z_MIN, RECEIVER_Z_MIN], color=COLORS["receiver"], linewidth=0.8, linestyle=(0, (3, 2)))
    ax.plot([334, 350], [RECEIVER_Z_MAX, RECEIVER_Z_MAX], color=COLORS["receiver"], linewidth=0.8, linestyle=(0, (3, 2)))
    text(ax, 329, 90, "圆柱有效侧壁\n76–84 m", size=9, color=COLORS["receiver"], ha="right")

    ax.plot([-12, -12], [0, MIRROR_CENTER[1]], color=COLORS["mirror"], linewidth=1.0)
    ax.plot([-14, -10], [0, 0], color=COLORS["mirror"], linewidth=1.0)
    ax.plot([-14, -10], [MIRROR_CENTER[1], MIRROR_CENTER[1]], color=COLORS["mirror"], linewidth=1.0)
    text(ax, -16, 2, "镜心 4 m", size=8.5, color=COLORS["mirror"], ha="right", va="center")
    text(ax, -1, -4.7, "6 m 平面镜", size=9, color=COLORS["mirror"], ha="center")
    text(ax, 14, 23, "入射光（近似平行）", size=9, color=COLORS["solar"])
    text(ax, 145, 49, "中心反射线  M → R", size=9, color=COLORS["ray"], rotation=12.6)
    text(ax, 237, 88, "绿色：命中侧壁", size=8.5, color=COLORS["hit"])
    text(ax, 237, 83, "红色：从上/下方溢出", size=8.5, color=COLORS["miss"])

    return rays, reflected_directions


def build_figure(output: Path, validation_path: Path, *, paper_mode: bool = False) -> None:
    sun, target, normal, tangent = setup_geometry()
    figure = plt.figure(figsize=(16, 9), dpi=180, facecolor=COLORS["paper"])
    grid_top = 0.96 if paper_mode else 0.88
    grid = figure.add_gridspec(2, 2, height_ratios=[0.42, 0.58], width_ratios=[0.57, 0.43], left=0.055, right=0.96, top=grid_top, bottom=0.065, hspace=0.14, wspace=0.11)
    inset = figure.add_subplot(grid[0, 0])
    facts = figure.add_subplot(grid[0, 1])
    main = figure.add_subplot(grid[1, :])

    if not paper_mode:
        figure.text(0.055, 0.945, "从太阳方向锥到圆柱接收器", fontproperties=CJK_BOLD, fontsize=24, color=COLORS["ink"], va="top")
        figure.text(0.055, 0.905, "方向锥在反射中保持半角；平面镜不会把所有光线聚焦到一点", fontproperties=CJK, fontsize=11.5, color=COLORS["muted"], va="top")
        figure.text(0.96, 0.942, "HELIOSTAT / Q1", fontproperties=MONO, fontsize=9, color=COLORS["muted"], ha="right", va="top")

    draw_direction_inset(inset, sun, target, normal, tangent)
    draw_fact_panel(facts)
    rays, reflected_directions = draw_main_geometry(main, sun, target, normal, tangent)

    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, facecolor=COLORS["paper"], bbox_inches=None)
    plt.close(figure)

    center_reflection_error = float(np.linalg.norm(reflect_sun_direction(sun, normal) - target))
    boundary_errors = []
    for sun_ray, reflected_ray in zip(
        [direction(80.0 - math.degrees(SOLAR_HALF_ANGLE)), direction(80.0 + math.degrees(SOLAR_HALF_ANGLE))],
        [reflected_directions[0], reflected_directions[2]],
    ):
        incoming_offset = math.acos(float(np.clip(np.dot(sun_ray, sun), -1.0, 1.0)))
        reflected_offset = math.acos(float(np.clip(np.dot(reflected_ray, target), -1.0, 1.0)))
        boundary_errors.append(abs(incoming_offset - reflected_offset))

    hit_count = sum(hit for _, _, hit in rays)
    checks = {
        "center_reflection_direction_error": center_reflection_error,
        "maximum_cone_half_angle_preservation_error_rad": max(boundary_errors),
        "solar_half_angle_deg": math.degrees(SOLAR_HALF_ANGLE),
        "mirror_size_m": MIRROR_SIZE,
        "mirror_center_height_m": float(MIRROR_CENTER[1]),
        "receiver_center_height_m": float(RECEIVER_CENTER[1]),
        "receiver_z_range_m": [RECEIVER_Z_MIN, RECEIVER_Z_MAX],
        "ray_count": len(rays),
        "receiver_hit_count": int(hit_count),
        "receiver_miss_count": int(len(rays) - hit_count),
        "paper_mode": paper_mode,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--paper-mode", action="store_true")
    args = parser.parse_args()
    build_figure(
        args.run_dir / "figures" / "fig01-physical-ray-geometry.png",
        args.run_dir / "validation" / "geometry-checks.json",
        paper_mode=args.paper_mode,
    )


if __name__ == "__main__":
    main()
