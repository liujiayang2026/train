from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Polygon, Rectangle


COLORS = {
    "bg": "#F7F8FA",
    "ink": "#202630",
    "muted": "#667085",
    "grid": "#D5D9E0",
    "solar": "#E9B949",
    "solar_fill": "#FFF1B8",
    "mirror": "#258B7C",
    "mirror_fill": "#CDE9E3",
    "beam": "#3178B8",
    "beam_fill": "#C9E1F5",
    "hit": "#4F9561",
    "miss": "#C84855",
    "receiver": "#697386",
    "receiver_fill": "#D9DDE3",
    "normal": "#7C5AA6",
}


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": COLORS["bg"],
            "axes.facecolor": COLORS["bg"],
            "text.color": COLORS["ink"],
            "axes.titlecolor": COLORS["ink"],
        }
    )


def arrow(ax, start, end, color, width=2.2, style="-", zorder=8) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=width,
            linestyle=style,
            color=color,
            shrinkA=0,
            shrinkB=0,
            zorder=zorder,
        )
    )


def thick_mirror(ax, center, angle_deg, length=1.8) -> tuple[np.ndarray, np.ndarray]:
    angle = math.radians(angle_deg)
    tangent = np.array([math.cos(angle), math.sin(angle)])
    p1 = np.asarray(center) - 0.5 * length * tangent
    p2 = np.asarray(center) + 0.5 * length * tangent
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=COLORS["mirror"], linewidth=14, solid_capstyle="butt", zorder=7)
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=COLORS["mirror_fill"], linewidth=8, solid_capstyle="butt", zorder=8)
    return p1, p2


def draw_side_view(ax) -> None:
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("A  侧视图：判断是否从集热器上方或下方溢出", loc="left", fontsize=16, pad=10)
    ax.plot([0.25, 11.75], [0.52, 0.52], color=COLORS["grid"], linewidth=2)

    sun = np.array([1.25, 6.85])
    mirror_center = np.array([3.20, 1.35])
    receiver_x = 10.25
    receiver_bottom = 4.00
    receiver_top = 6.22
    receiver_center = np.array([receiver_x, 5.11])

    ax.add_patch(Circle(sun, 0.34, facecolor=COLORS["solar"], edgecolor=COLORS["ink"], linewidth=1.6, zorder=9))
    ax.text(sun[0], 7.37, "太阳圆盘", ha="center", fontsize=10.5)
    mirror_p1, mirror_p2 = thick_mirror(ax, mirror_center, 16, 1.95)
    ax.text(mirror_center[0], 0.73, "6 m × 6 m 平面定日镜", ha="center", fontsize=10.5)

    incoming = np.vstack([sun + [-0.23, 0.10], sun + [0.25, -0.12], mirror_p2, mirror_p1])
    ax.add_patch(Polygon(incoming, closed=True, facecolor=COLORS["solar_fill"], edgecolor="none", alpha=0.70, zorder=1))
    ax.plot([sun[0] - 0.23, mirror_p1[0]], [sun[1] + 0.10, mirror_p1[1]], color=COLORS["solar"], linewidth=1.7)
    ax.plot([sun[0] + 0.25, mirror_p2[0]], [sun[1] - 0.12, mirror_p2[1]], color=COLORS["solar"], linewidth=1.7)
    arrow(ax, (1.85, 5.75), (2.55, 3.72), COLORS["solar"], 2.3)
    ax.text(1.70, 4.63, "入射锥束", color=COLORS["solar"], fontsize=10.5, rotation=-69)

    beam_low = 3.38
    beam_high = 6.82
    reflected_envelope = np.array(
        [
            mirror_p1,
            mirror_p2,
            [receiver_x, beam_high],
            [receiver_x, beam_low],
        ]
    )
    ax.add_patch(Polygon(reflected_envelope, closed=True, facecolor=COLORS["beam_fill"], edgecolor="none", alpha=0.55, zorder=2))
    ax.plot([mirror_p1[0], receiver_x], [mirror_p1[1], beam_low], color=COLORS["beam"], linewidth=1.7, linestyle="--")
    ax.plot([mirror_p2[0], receiver_x], [mirror_p2[1], beam_high], color=COLORS["beam"], linewidth=1.7, linestyle="--")

    ray_ends = np.linspace(beam_low, beam_high, 9)
    starts = np.linspace(0.06, 0.94, 9)
    hit_points = []
    for frac, y_end in zip(starts, ray_ends):
        p = mirror_p1 + frac * (mirror_p2 - mirror_p1)
        hit = receiver_bottom <= y_end <= receiver_top
        color = COLORS["hit"] if hit else COLORS["miss"]
        ax.plot([p[0], receiver_x], [p[1], y_end], color=color, linewidth=2.0, alpha=0.92, zorder=5)
        if hit:
            hit_points.append((receiver_x, y_end))
        else:
            ax.scatter([receiver_x], [y_end], s=38, marker="x", color=COLORS["miss"], linewidths=2, zorder=10)

    ax.add_patch(
        Rectangle(
            (receiver_x - 0.23, receiver_bottom),
            0.46,
            receiver_top - receiver_bottom,
            facecolor=COLORS["receiver_fill"],
            edgecolor=COLORS["receiver"],
            linewidth=2.3,
            zorder=8,
        )
    )
    ax.add_patch(Ellipse((receiver_x, receiver_top), 0.70, 0.22, facecolor=COLORS["receiver_fill"], edgecolor=COLORS["receiver"], linewidth=2.0, zorder=9))
    ax.add_patch(Ellipse((receiver_x, receiver_bottom), 0.70, 0.22, facecolor=COLORS["receiver_fill"], edgecolor=COLORS["receiver"], linewidth=2.0, zorder=9))
    if hit_points:
        ax.scatter([x for x, _ in hit_points], [y for _, y in hit_points], s=38, color=COLORS["hit"], edgecolor="white", linewidth=0.6, zorder=10)
    ax.scatter(*receiver_center, s=42, color=COLORS["receiver"], zorder=10)
    ax.text(receiver_x, 7.32, "圆柱集热器", ha="center", fontsize=11)
    ax.text(receiver_x + 0.47, 5.11, "高 8 m", va="center", fontsize=10, color=COLORS["muted"])
    ax.text(receiver_x + 0.48, 6.72, "上方溢出", color=COLORS["miss"], fontsize=10)
    ax.text(receiver_x + 0.48, 3.35, "下方溢出", color=COLORS["miss"], fontsize=10)

    central_direction = receiver_center - mirror_center
    arrow(ax, mirror_center, mirror_center + 0.63 * central_direction, COLORS["beam"], 3.0)
    ax.text(5.95, 3.30, r"中心反射方向 $\mathbf{t}_i$", color=COLORS["beam"], fontsize=11, rotation=30)
    normal_end = mirror_center + np.array([-0.38, 1.42])
    arrow(ax, mirror_center, normal_end, COLORS["normal"], 2.2, "--")
    ax.text(normal_end[0] - 0.18, normal_end[1] + 0.18, r"$\mathbf{n}_i$", color=COLORS["normal"], fontsize=11)
    ax.text(5.10, 6.90, "蓝色包络：镜面尺寸与太阳角共同形成的反射光束", fontsize=10.5, color=COLORS["beam"])


def first_circle_hit(p: np.ndarray, d: np.ndarray, center: np.ndarray, radius: float) -> np.ndarray | None:
    rel = p - center
    a = float(np.dot(d, d))
    b = 2.0 * float(np.dot(rel, d))
    c = float(np.dot(rel, rel) - radius**2)
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    roots = [(-b - math.sqrt(disc)) / (2 * a), (-b + math.sqrt(disc)) / (2 * a)]
    positive = [value for value in roots if value > 1e-9]
    if not positive:
        return None
    return p + min(positive) * d


def draw_top_view(ax) -> None:
    ax.set_xlim(0, 12)
    ax.set_ylim(-4.3, 4.3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("B  俯视图：判断是否从圆柱左右两侧掠过", loc="left", fontsize=16, pad=10)

    mirror_center = np.array([2.10, 0.0])
    receiver_center = np.array([9.25, 0.0])
    radius = 1.72
    mirror_p1, mirror_p2 = thick_mirror(ax, mirror_center, 82, 1.85)
    ax.text(1.18, -1.58, "定日镜在水平面内的投影", fontsize=10.5)

    envelope = np.array(
        [
            mirror_p1,
            mirror_p2,
            [11.45, 3.05],
            [11.45, -3.05],
        ]
    )
    ax.add_patch(Polygon(envelope, closed=True, facecolor=COLORS["beam_fill"], edgecolor="none", alpha=0.52, zorder=1))
    ax.plot([mirror_p1[0], 11.45], [mirror_p1[1], -3.05], color=COLORS["beam"], linewidth=1.7, linestyle="--")
    ax.plot([mirror_p2[0], 11.45], [mirror_p2[1], 3.05], color=COLORS["beam"], linewidth=1.7, linestyle="--")

    starts = np.linspace(-0.76, 0.76, 9)
    target_y = np.linspace(-2.58, 2.58, 9)
    for start_offset, y_target in zip(starts, target_y):
        p = mirror_center + np.array([0.0, start_offset])
        d = np.array([9.35, y_target - start_offset])
        hit = first_circle_hit(p, d, receiver_center, radius)
        if hit is None:
            end = p + 1.02 * d
            ax.plot([p[0], end[0]], [p[1], end[1]], color=COLORS["miss"], linewidth=2.0, alpha=0.92, zorder=4)
            ax.scatter([end[0]], [end[1]], s=36, marker="x", color=COLORS["miss"], linewidths=2, zorder=9)
        else:
            ax.plot([p[0], hit[0]], [p[1], hit[1]], color=COLORS["hit"], linewidth=2.0, alpha=0.92, zorder=4)
            ax.scatter([hit[0]], [hit[1]], s=34, color=COLORS["hit"], edgecolor="white", linewidth=0.5, zorder=9)

    ax.add_patch(Circle(receiver_center, radius, facecolor=COLORS["receiver_fill"], edgecolor=COLORS["receiver"], linewidth=2.6, alpha=0.92, zorder=7))
    ax.scatter(*receiver_center, s=42, color=COLORS["receiver"], zorder=9)
    ax.text(receiver_center[0], 2.23, "圆柱集热器水平截面", ha="center", fontsize=11)
    ax.text(receiver_center[0], -2.28, r"半径 $r_R=3.5$ m", ha="center", fontsize=10.5, color=COLORS["muted"])

    center_start = mirror_center
    center_direction = receiver_center - center_start
    q = first_circle_hit(center_start, center_direction, receiver_center, radius)
    if q is not None:
        arrow(ax, center_start, q, COLORS["beam"], 3.0)
        outward = (q - receiver_center) / radius
        arrow(ax, q, q + 1.05 * outward, COLORS["normal"], 2.2)
        ax.text(q[0] - 0.18, q[1] + 0.28, "$Q$", fontsize=11)
        ax.text(q[0] - 1.25, q[1] + 0.52, r"$\mathbf{n}_R$", color=COLORS["normal"], fontsize=11)
        ax.text(4.72, 0.34, r"$\mathbf{X}(\lambda)=\mathbf{P}+\lambda\mathbf{d}_r$", color=COLORS["beam"], fontsize=11)
    ax.text(8.50, 3.42, "红色：没有与圆周相交，形成横向截断损失", color=COLORS["miss"], fontsize=10.5, ha="center")
    ax.text(8.68, -3.72, r"命中外侧壁还应满足 $\mathbf{d}_r\cdot\mathbf{n}_R<0$", color=COLORS["normal"], fontsize=10.5, ha="center")


def draw_process(output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16.0, 7.8), constrained_layout=True)
    fig.suptitle("反射光束从定日镜传播到圆柱集热器", fontsize=21)
    draw_side_view(axes[0])
    draw_top_view(axes[1])
    fig.text(
        0.50,
        0.012,
        r"$\mathbf{d}_r=-\mathbf{s}_q+2(\mathbf{s}_q\cdot\mathbf{n}_i)\mathbf{n}_i$"
        + "        "
        + r"$(x-x_R)^2+(y-y_R)^2=r_R^2$"
        + "        "
        + r"$76\leq z(\lambda_*)\leq84$"
        + "        "
        + r"$\eta_{trunc}=N_{hit}/N_{clear}$",
        ha="center",
        fontsize=13,
        color=COLORS["ink"],
    )
    fig.savefig(output_dir / "fig01-reflected-bundle-to-cylinder-process.png", dpi=190, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw the reflected solar bundle travelling from a heliostat to a cylindrical receiver.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_style()
    draw_process(args.output_dir)


if __name__ == "__main__":
    main()
