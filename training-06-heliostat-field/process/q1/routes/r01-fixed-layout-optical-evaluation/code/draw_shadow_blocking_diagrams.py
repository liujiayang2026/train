from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


COLORS = {
    "bg": "#F7F8FA",
    "ink": "#202630",
    "muted": "#667085",
    "grid": "#D5D9E0",
    "solar": "#E9B949",
    "solar_fill": "#FFF1B8",
    "shadow": "#C84855",
    "shadow_fill": "#F6C9CE",
    "block": "#D97941",
    "block_fill": "#F8D7C4",
    "ray": "#3178B8",
    "ray_fill": "#C9E1F5",
    "mirror": "#2C8C7B",
    "mirror_fill": "#CDE9E3",
    "clear": "#5A9B68",
    "clear_fill": "#D7ECD9",
    "overlap": "#7C5AA6",
    "receiver": "#6B7280",
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


def add_arrow(ax, start, end, color, width=2.2, style="-") -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=15,
            linewidth=width,
            linestyle=style,
            color=color,
            shrinkA=0,
            shrinkB=0,
            zorder=7,
        )
    )


def mirror_segment(center, angle_deg, length=1.8):
    angle = math.radians(angle_deg)
    tangent = np.array([math.cos(angle), math.sin(angle)])
    p1 = np.asarray(center) - 0.5 * length * tangent
    p2 = np.asarray(center) + 0.5 * length * tangent
    return p1, p2


def draw_mirror(ax, center, angle_deg, label, edge=None, fill=None, length=1.8):
    edge = edge or COLORS["mirror"]
    fill = fill or COLORS["mirror_fill"]
    p1, p2 = mirror_segment(center, angle_deg, length)
    tangent = (p2 - p1) / np.linalg.norm(p2 - p1)
    normal = np.array([-tangent[1], tangent[0]])
    thickness = 0.11
    poly = np.vstack(
        [
            p1 - thickness * normal,
            p2 - thickness * normal,
            p2 + thickness * normal,
            p1 + thickness * normal,
        ]
    )
    ax.add_patch(Polygon(poly, closed=True, facecolor=fill, edgecolor=edge, linewidth=2.2, zorder=6))
    ax.text(center[0], center[1] - 0.48, label, ha="center", va="top", fontsize=11, color=COLORS["ink"])
    return p1, p2


def setup_2d_axis(ax, title):
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.5)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=16, fontweight="normal", pad=12)
    ax.plot([0.25, 9.75], [0.55, 0.55], color=COLORS["grid"], linewidth=2, zorder=1)


def draw_shadow_panel(ax):
    setup_2d_axis(ax, "A  阴影：入射光到镜面前被截断")
    sun = np.array([1.15, 5.45])
    blocker = np.array([4.55, 3.45])
    target = np.array([7.75, 1.55])

    ax.add_patch(Circle(sun, 0.36, facecolor=COLORS["solar"], edgecolor=COLORS["ink"], linewidth=1.5, zorder=8))
    ax.text(sun[0], sun[1] + 0.58, "太阳圆盘", ha="center", fontsize=11)

    b1, b2 = mirror_segment(blocker, 12, 1.85)
    t1, t2 = mirror_segment(target, 13, 2.2)
    cone = np.vstack([sun + [-0.28, 0.16], sun + [0.30, -0.18], t2, t1])
    ax.add_patch(Polygon(cone, closed=True, facecolor=COLORS["solar_fill"], edgecolor="none", alpha=0.7, zorder=2))
    ax.plot([sun[0] - 0.28, t1[0]], [sun[1] + 0.16, t1[1]], color=COLORS["solar"], linewidth=1.8)
    ax.plot([sun[0] + 0.30, t2[0]], [sun[1] - 0.18, t2[1]], color=COLORS["solar"], linewidth=1.8)
    add_arrow(ax, (2.0, 4.92), (3.1, 4.25), COLORS["solar"], 2.3)

    # The projected region behind the blocker is the geometric shadow corridor.
    shadow_poly = np.vstack([b1, b2, t2, target + [-0.18, -0.04]])
    ax.add_patch(Polygon(shadow_poly, closed=True, facecolor=COLORS["shadow_fill"], edgecolor="none", alpha=0.88, zorder=3))
    draw_mirror(ax, blocker, 12, "遮光镜 $j$", edge=COLORS["block"], fill=COLORS["block_fill"], length=1.85)
    draw_mirror(ax, target, 13, "待评价镜 $i$", length=2.2)

    p = target + np.array([0.05, 0.08])
    add_arrow(ax, p, p + np.array([-1.55, 0.92]), COLORS["shadow"], 2.4, "--")
    ax.scatter(*p, s=44, color=COLORS["shadow"], zorder=9)
    ax.text(p[0] - 1.9, p[1] + 1.04, r"反向追踪：$\mathbf{P}+\lambda\mathbf{s}$", fontsize=11, color=COLORS["shadow"])
    ax.text(5.65, 3.05, "阴影区", fontsize=11, color=COLORS["shadow"], rotation=-28)
    ax.text(0.55, 0.12, r"判定：沿 $+\mathbf{s}$ 遇到其他镜面 $\Rightarrow$ 该采样点未被太阳照亮", fontsize=11)


def draw_blocking_panel(ax):
    setup_2d_axis(ax, "B  遮挡：反射光到集热器前被截断")
    target = np.array([2.0, 1.48])
    blocker = np.array([5.35, 3.0])
    receiver = np.array([8.9, 5.05])
    sun = np.array([0.65, 5.6])

    ax.add_patch(Circle(sun, 0.30, facecolor=COLORS["solar"], edgecolor=COLORS["ink"], linewidth=1.5, zorder=8))
    ax.text(sun[0] + 0.48, sun[1] + 0.20, "太阳圆盘", fontsize=10)
    incoming = np.vstack([sun + [-0.12, 0.1], sun + [0.22, -0.12], target + [0.65, 0.1], target + [-0.65, -0.1]])
    ax.add_patch(Polygon(incoming, closed=True, facecolor=COLORS["solar_fill"], edgecolor="none", alpha=0.62, zorder=2))
    add_arrow(ax, (0.95, 4.9), (1.65, 2.35), COLORS["solar"], 2.2)

    rcone = np.vstack([target + [-0.7, -0.08], target + [0.72, 0.10], receiver + [0.0, 0.48], receiver + [0.0, -0.48]])
    ax.add_patch(Polygon(rcone, closed=True, facecolor=COLORS["ray_fill"], edgecolor="none", alpha=0.74, zorder=2))
    ax.plot([target[0] - 0.7, receiver[0]], [target[1] - 0.08, receiver[1] - 0.48], color=COLORS["ray"], linewidth=1.8)
    ax.plot([target[0] + 0.72, receiver[0]], [target[1] + 0.10, receiver[1] + 0.48], color=COLORS["ray"], linewidth=1.8)

    draw_mirror(ax, target, 14, "待评价镜 $i$", length=2.1)
    draw_mirror(ax, blocker, 29, "挡光镜 $j$", edge=COLORS["block"], fill=COLORS["block_fill"], length=1.75)

    ax.add_patch(Rectangle((8.72, 4.25), 0.36, 1.58, facecolor="#E1E4E8", edgecolor=COLORS["receiver"], linewidth=2, zorder=6))
    ax.add_patch(Rectangle((8.47, 4.70), 0.86, 0.78, facecolor="#D7DBE0", edgecolor=COLORS["receiver"], linewidth=2.2, zorder=7))
    ax.text(8.9, 6.05, "集热器", ha="center", fontsize=11)

    p = target + np.array([0.05, 0.08])
    add_arrow(ax, p, p + np.array([2.15, 1.02]), COLORS["ray"], 2.6)
    ax.scatter(*p, s=44, color=COLORS["ray"], zorder=9)
    ax.text(2.72, 2.85, r"正向追踪：$\mathbf{P}+\lambda\mathbf{t}_i$", fontsize=11, color=COLORS["ray"])
    ax.text(5.85, 3.72, "被挡住的反射锥束", fontsize=11, color=COLORS["block"], rotation=25)
    ax.text(0.55, 0.12, r"判定：沿 $+\mathbf{t}_i$ 在到达集热器前遇到其他镜面 $\Rightarrow$ 该采样点被遮挡", fontsize=11)


def draw_paths(output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 7.1), constrained_layout=True)
    fig.suptitle("阴影与遮挡是两条不同的光路", fontsize=21, fontweight="normal")
    draw_shadow_panel(axes[0])
    draw_blocking_panel(axes[1])
    fig.savefig(output_dir / "fig01-shadow-vs-blocking-paths.png", dpi=180, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def draw_intersection(output_dir: Path) -> None:
    fig = plt.figure(figsize=(15.5, 8.2), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.45, 0.9])
    ax = fig.add_subplot(grid[0, 0], projection="3d")
    eq = fig.add_subplot(grid[0, 1])
    fig.suptitle("射线与另一面定日镜的相交判定", fontsize=21, fontweight="normal")

    mj = np.array([2.9, 1.7, 2.2])
    uj = np.array([0.84, 0.36, 0.0])
    uj = uj / np.linalg.norm(uj)
    nj = np.array([-0.28, 0.66, 0.70])
    nj = nj / np.linalg.norm(nj)
    vj = np.cross(nj, uj)
    vj = vj / np.linalg.norm(vj)
    half = 1.55
    corners = np.array([mj - half * uj - half * vj, mj + half * uj - half * vj, mj + half * uj + half * vj, mj - half * uj + half * vj])
    plane = Poly3DCollection(
        [corners],
        facecolors=COLORS["mirror_fill"],
        edgecolors=COLORS["mirror"],
        linewidths=2.2,
        alpha=0.82,
    )
    ax.add_collection3d(plane)

    q = mj + 0.42 * uj - 0.28 * vj
    p = np.array([-0.3, -0.15, 0.45])
    d = q - p
    d = d / np.linalg.norm(d)
    end = q + 1.75 * d
    ax.plot([p[0], end[0]], [p[1], end[1]], [p[2], end[2]], color=COLORS["ray"], linewidth=3)
    ax.quiver(*(q - 0.95 * d), *(0.9 * d), color=COLORS["ray"], arrow_length_ratio=0.18, linewidth=2.3)
    ax.scatter(*p, s=54, color=COLORS["shadow"], depthshade=False)
    ax.scatter(*q, s=62, color=COLORS["overlap"], depthshade=False)
    ax.scatter(*mj, s=48, color=COLORS["mirror"], depthshade=False)
    ax.quiver(*mj, *(1.1 * uj), color=COLORS["clear"], arrow_length_ratio=0.18, linewidth=2.2)
    ax.quiver(*mj, *(1.1 * vj), color=COLORS["block"], arrow_length_ratio=0.18, linewidth=2.2)
    ax.quiver(*mj, *(1.25 * nj), color=COLORS["overlap"], arrow_length_ratio=0.18, linewidth=2.2)
    ax.text(*(p + [-0.18, -0.15, 0.05]), "$P$", fontsize=12)
    ax.text(*(q + [0.08, 0.08, 0.08]), "$Q$", fontsize=12)
    ax.text(*(mj + [-0.28, -0.25, -0.18]), "$M_j$", fontsize=12)
    ax.text(*(mj + 1.18 * uj), "$u_j$", color=COLORS["clear"], fontsize=12)
    ax.text(*(mj + 1.18 * vj), "$v_j$", color=COLORS["block"], fontsize=12)
    ax.text(*(mj + 1.32 * nj), "$n_j$", color=COLORS["overlap"], fontsize=12)
    ax.text(*(p + 1.3 * d), r"$\mathbf{d}$", color=COLORS["ray"], fontsize=12)
    ax.set_xlim(-0.8, 5.2)
    ax.set_ylim(-0.8, 4.6)
    ax.set_zlim(0, 5.2)
    ax.set_box_aspect((1.1, 1.0, 0.9))
    ax.view_init(elev=23, azim=-58)
    ax.set_xlabel("$x$")
    ax.set_ylabel("$y$")
    ax.set_zlabel("$z$")
    ax.grid(True, color=COLORS["grid"], linewidth=0.7)
    ax.set_title("几何关系", fontsize=16, pad=12)

    eq.axis("off")
    eq.set_title("计算顺序", loc="left", fontsize=16, pad=12)
    equations = [
        (0.95, "1. 射线", r"$\mathbf{X}(\lambda)=\mathbf{P}+\lambda\mathbf{d}$"),
        (0.72, "2. 与镜面平面求交", r"$\lambda=\dfrac{\mathbf{n}_j\cdot(\mathbf{M}_j-\mathbf{P})}{\mathbf{n}_j\cdot\mathbf{d}}$"),
        (0.43, "3. 转到镜面局部坐标", r"$a=(\mathbf{Q}-\mathbf{M}_j)\cdot\mathbf{u}_j$" + "\n" + r"$b=(\mathbf{Q}-\mathbf{M}_j)\cdot\mathbf{v}_j$"),
        (0.16, "4. 判断是否落在 6 m × 6 m 镜内", r"$|a|\leq3,\quad |b|\leq3,\quad \lambda>\varepsilon$"),
    ]
    for y, head, formula in equations:
        eq.text(0.02, y, head, transform=eq.transAxes, fontsize=12, color=COLORS["muted"], va="top")
        eq.text(0.02, y - 0.08, formula, transform=eq.transAxes, fontsize=16, color=COLORS["ink"], va="top")
    eq.text(0.02, 0.01, r"阴影取 $\mathbf{d}=\mathbf{s}$；遮挡取 $\mathbf{d}=\mathbf{t}_i$。", transform=eq.transAxes, fontsize=12, color=COLORS["ray"])
    fig.savefig(output_dir / "fig02-ray-plane-intersection.png", dpi=180, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def draw_sampling(output_dir: Path) -> None:
    n = 20
    coords = np.linspace(-3 + 3 / n, 3 - 3 / n, n)
    x, z = np.meshgrid(coords, coords)
    shadow = ((x + 1.05) / 2.05) ** 2 + ((z - 0.55) / 1.60) ** 2 <= 1
    blocked = ((x - 1.00) / 1.72) ** 2 + ((z + 0.65) / 1.72) ** 2 <= 1
    classes = np.zeros_like(x, dtype=int)
    classes[shadow] = 1
    classes[blocked] = 2
    classes[shadow & blocked] = 3
    clear = int(np.count_nonzero(classes == 0))
    total = n * n

    color_table = np.array(
        [
            [0.843, 0.925, 0.851, 1.0],
            [0.965, 0.788, 0.808, 1.0],
            [0.973, 0.843, 0.769, 1.0],
            [0.486, 0.353, 0.651, 1.0],
        ]
    )

    fig, (ax, note) = plt.subplots(1, 2, figsize=(14.8, 8.2), gridspec_kw={"width_ratios": [1.2, 0.85]}, constrained_layout=True)
    fig.suptitle("从采样点统计阴影遮挡效率", fontsize=21, fontweight="normal")
    ax.imshow(color_table[classes], origin="lower", extent=[-3, 3, -3, 3], interpolation="nearest")
    for edge in np.linspace(-3, 3, n + 1):
        ax.plot([-3, 3], [edge, edge], color="white", alpha=0.55, linewidth=0.45)
        ax.plot([edge, edge], [-3, 3], color="white", alpha=0.55, linewidth=0.45)
    ax.add_patch(Rectangle((-3, -3), 6, 6, facecolor="none", edgecolor=COLORS["mirror"], linewidth=2.6))
    ax.set_xlabel(r"镜面宽度方向 $\xi$ / m", fontsize=12)
    ax.set_ylabel(r"镜面高度方向 $\zeta$ / m", fontsize=12)
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
    ax.set_yticks([-3, -2, -1, 0, 1, 2, 3])
    ax.set_aspect("equal")
    ax.set_title("20 × 20 分层网格示意", fontsize=16, pad=12)

    legend = [
        (COLORS["clear_fill"], COLORS["clear"], "有效点：两条光路均畅通"),
        (COLORS["shadow_fill"], COLORS["shadow"], "阴影点：入射光路被挡"),
        (COLORS["block_fill"], COLORS["block"], "遮挡点：反射光路被挡"),
        (COLORS["overlap"], COLORS["overlap"], "重叠点：两种损失同时发生"),
    ]
    for idx, (face, edge, text) in enumerate(legend):
        y = 0.87 - idx * 0.11
        note.add_patch(Rectangle((0.02, y), 0.055, 0.055, transform=note.transAxes, facecolor=face, edgecolor=edge, linewidth=1.5))
        note.text(0.10, y + 0.027, text, transform=note.transAxes, va="center", fontsize=12)
    note.text(0.02, 0.36, r"$I_p=1$：采样点既不在阴影集合 $S_i$ 中，" + "\n" + r"也不在遮挡集合 $B_i$ 中。", transform=note.transAxes, fontsize=13, linespacing=1.6)
    note.text(0.02, 0.20, rf"$\eta_{{sb,i}}=\dfrac{{N_{{clear}}}}{{N_p}}=\dfrac{{{clear}}}{{{total}}}={clear / total:.3f}$", transform=note.transAxes, fontsize=18, color=COLORS["ink"])
    note.text(0.02, 0.08, r"等价于：$\eta_{sb,i}=1-\dfrac{A(S_i\cup B_i)}{A_i}$", transform=note.transAxes, fontsize=14, color=COLORS["ray"])
    note.text(0.02, 0.015, "紫色重叠区只扣除一次；图中数值仅用于说明统计方法。", transform=note.transAxes, fontsize=11, color=COLORS["muted"])
    note.axis("off")
    fig.savefig(output_dir / "fig03-sampling-and-union-efficiency.png", dpi=180, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw mathematical diagrams for heliostat shadow and blocking efficiency.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_style()
    draw_paths(args.output_dir)
    draw_intersection(args.output_dir)
    draw_sampling(args.output_dir)


if __name__ == "__main__":
    main()
