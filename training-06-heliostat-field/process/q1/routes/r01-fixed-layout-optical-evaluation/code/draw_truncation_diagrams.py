from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle


COLORS = {
    "bg": "#F7F8FA",
    "ink": "#202630",
    "muted": "#667085",
    "grid": "#D5D9E0",
    "mirror": "#258B7C",
    "mirror_fill": "#CDE9E3",
    "ray": "#3178B8",
    "ray_fill": "#C9E1F5",
    "hit": "#4F9561",
    "hit_fill": "#D7ECD9",
    "miss": "#C84855",
    "miss_fill": "#F6C9CE",
    "blocked": "#7C5AA6",
    "receiver": "#697386",
    "receiver_fill": "#D9DDE3",
    "solar": "#E9B949",
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


def add_arrow(ax, start, end, color, width=2.2, style="-", zorder=7) -> None:
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


def setup_side_axis(ax, title: str) -> None:
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=16, pad=10)
    ax.plot([0.35, 9.65], [0.58, 0.58], color=COLORS["grid"], linewidth=2)


def draw_mirror_segment(ax, p1, p2) -> None:
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=COLORS["mirror"], linewidth=13, solid_capstyle="butt", zorder=5)
    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=COLORS["mirror_fill"], linewidth=7, solid_capstyle="butt", zorder=6)


def draw_receiver_side(ax, x=8.55, bottom=3.65, top=5.35) -> None:
    ax.add_patch(
        Rectangle(
            (x - 0.16, bottom),
            0.32,
            top - bottom,
            facecolor=COLORS["receiver_fill"],
            edgecolor=COLORS["receiver"],
            linewidth=2.3,
            zorder=8,
        )
    )
    ax.scatter([x], [(bottom + top) / 2], s=36, color=COLORS["receiver"], zorder=9)
    ax.text(x, top + 0.34, "集热器侧面", ha="center", fontsize=11)


def draw_wrong_focus(ax) -> None:
    setup_side_axis(ax, "A  错误理解：让每个镜面点都瞄准集热器中心")
    p1 = np.array([1.15, 1.16])
    p2 = np.array([3.05, 1.58])
    center = 0.5 * (p1 + p2)
    receiver_center = np.array([8.55, 4.50])
    draw_mirror_segment(ax, p1, p2)
    draw_receiver_side(ax)

    for frac in np.linspace(0.05, 0.95, 6):
        p = p1 + frac * (p2 - p1)
        ax.plot([p[0], receiver_center[0]], [p[1], receiver_center[1]], color=COLORS["miss"], linewidth=1.7, alpha=0.80)
        ax.scatter(*p, s=22, color=COLORS["mirror"], zorder=9)
    add_arrow(ax, center, receiver_center, COLORS["miss"], 2.6)
    ax.text(4.15, 3.88, "所有射线被强行汇聚到 R", color=COLORS["miss"], fontsize=11, rotation=24)
    ax.text(0.78, 6.15, r"$\mathbf{d}(\mathbf{P})=(\mathbf{R}-\mathbf{P})/\|\mathbf{R}-\mathbf{P}\|$", fontsize=13)
    ax.text(0.78, 5.60, "这相当于把平面镜错误地当成聚焦镜", fontsize=11, color=COLORS["muted"])
    ax.text(center[0], 0.72, "平面定日镜", ha="center", fontsize=11)
    ax.text(0.70, 0.18, "结果：几乎所有光线都被算作命中，截断效率会被高估。", fontsize=11, color=COLORS["miss"])


def draw_parallel_bundle(ax) -> None:
    setup_side_axis(ax, "B  正确理解：中心太阳光经平面镜后保持平行")
    p1 = np.array([1.15, 1.16])
    p2 = np.array([3.05, 1.58])
    center = 0.5 * (p1 + p2)
    receiver_center = np.array([8.55, 4.50])
    draw_mirror_segment(ax, p1, p2)
    draw_receiver_side(ax)

    direction = receiver_center - center
    slope = direction[1] / direction[0]
    central_endpoints = []
    for frac in np.linspace(0.05, 0.95, 6):
        p = p1 + frac * (p2 - p1)
        y_end = p[1] + slope * (receiver_center[0] - p[0])
        central_endpoints.append(y_end)
        color = COLORS["hit"] if 3.65 <= y_end <= 5.35 else COLORS["miss"]
        ax.plot([p[0], receiver_center[0]], [p[1], y_end], color=color, linewidth=1.8, alpha=0.88)
        ax.scatter(*p, s=22, color=COLORS["mirror"], zorder=9)

    base_low = min(central_endpoints) - 0.82
    base_high = max(central_endpoints) + 0.82
    ax.fill_between(
        [center[0], receiver_center[0]],
        [center[1], base_low],
        [center[1], base_high],
        color=COLORS["ray_fill"],
        alpha=0.42,
        zorder=1,
    )
    ax.plot([center[0], receiver_center[0]], [center[1], base_low], color=COLORS["ray"], linewidth=1.6, linestyle="--")
    ax.plot([center[0], receiver_center[0]], [center[1], base_high], color=COLORS["ray"], linewidth=1.6, linestyle="--")
    add_arrow(ax, center, center + 0.64 * direction, COLORS["ray"], 2.7)

    ax.plot([8.87, 8.87], [base_low, 3.65], color=COLORS["miss"], linewidth=7, solid_capstyle="butt")
    ax.plot([8.87, 8.87], [3.65, 5.35], color=COLORS["hit"], linewidth=7, solid_capstyle="butt")
    ax.plot([8.87, 8.87], [5.35, base_high], color=COLORS["miss"], linewidth=7, solid_capstyle="butt")
    ax.text(9.12, 4.50, "命中", color=COLORS["hit"], fontsize=10, va="center")
    ax.text(9.12, base_high - 0.18, "溢出", color=COLORS["miss"], fontsize=10, va="center")
    ax.text(9.12, base_low + 0.18, "溢出", color=COLORS["miss"], fontsize=10, va="center")
    ax.text(0.78, 6.15, r"中心方向：$\mathbf{d}_r(\mathbf{P})=\mathbf{t}_i$", fontsize=13)
    ax.text(0.78, 5.60, r"太阳锥束使光斑再扩展：$\Delta r\approx d_{HR}\tan\theta_\odot$", fontsize=11, color=COLORS["ray"])
    ax.text(center[0], 0.72, "平面定日镜", ha="center", fontsize=11)
    ax.text(0.70, 0.18, "绿色部分落在有限接收面上；红色溢出部分形成截断损失（角度已夸张）。", fontsize=11)


def draw_footprint(output_dir: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.8, 7.4), constrained_layout=True)
    fig.suptitle("平面镜为什么仍然会产生截断损失", fontsize=21)
    draw_wrong_focus(axes[0])
    draw_parallel_bundle(axes[1])
    fig.savefig(output_dir / "fig01-flat-mirror-footprint-overflow.png", dpi=180, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def draw_cylinder_intersection(output_dir: Path) -> None:
    fig = plt.figure(figsize=(15.6, 8.4), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.38, 0.92])
    ax = fig.add_subplot(grid[0, 0], projection="3d")
    eq = fig.add_subplot(grid[0, 1])
    fig.suptitle("反射射线与圆柱集热器侧面的相交判定", fontsize=21)

    radius = 3.5
    theta = np.linspace(0, 2 * np.pi, 80)
    z = np.linspace(76, 84, 30)
    theta_grid, z_grid = np.meshgrid(theta, z)
    x_grid = radius * np.cos(theta_grid)
    y_grid = radius * np.sin(theta_grid)
    ax.plot_surface(
        x_grid,
        y_grid,
        z_grid,
        color=COLORS["receiver_fill"],
        edgecolor="none",
        alpha=0.48,
        shade=False,
    )
    for level in [76, 84]:
        ax.plot(radius * np.cos(theta), radius * np.sin(theta), np.full_like(theta, level), color=COLORS["receiver"], linewidth=2)

    p = np.array([15.0, -18.0, 68.0])
    q_hit = np.array([2.05, -math.sqrt(radius**2 - 2.05**2), 80.0])
    q_high = np.array([0.0, 0.0, 87.2])
    for target, color, label in [
        (q_hit, COLORS["hit"], "命中：交点高度在 76–84 m"),
        (q_high, COLORS["miss"], "未命中：穿过无限圆柱时已高于 84 m"),
    ]:
        direction = target - p
        end = p + 1.08 * direction
        ax.plot([p[0], end[0]], [p[1], end[1]], [p[2], end[2]], color=color, linewidth=3)
        ax.scatter(*target, s=54, color=color, depthshade=False)
        mid = p + 0.63 * direction
        ax.text(*mid, label, color=color, fontsize=10)
    ax.scatter(*p, s=52, color=COLORS["ray"], depthshade=False)
    ax.text(*(p + [0.5, 0.3, 0.3]), "$P$", fontsize=12)
    ax.text(0, 0, 85.1, "圆柱侧面\n$r_R=3.5$ m", ha="center", fontsize=11)
    ax.set_xlim(-6, 17)
    ax.set_ylim(-20, 7)
    ax.set_zlim(66, 89)
    ax.set_box_aspect((1.0, 1.1, 0.9))
    ax.view_init(elev=23, azim=-55)
    ax.set_xlabel("$x-x_R$ / m")
    ax.set_ylabel("$y-y_R$ / m")
    ax.set_zlabel("$z$ / m")
    ax.grid(True, color=COLORS["grid"], linewidth=0.7)
    ax.set_title("几何视图", fontsize=16, pad=12)

    eq.axis("off")
    eq.set_title("计算顺序", loc="left", fontsize=16, pad=12)
    rows = [
        (0.92, "1. 反射射线", r"$\mathbf{X}(\lambda)=\mathbf{P}+\lambda\mathbf{d}_r$"),
        (0.73, "2. 代入圆柱侧面", r"$(x-x_R)^2+(y-y_R)^2=r_R^2$"),
        (0.54, "3. 得到一元二次方程", r"$A\lambda^2+B\lambda+C=0$" + "\n" + r"$\Delta=B^2-4AC$"),
        (0.31, "4. 取最小正根", r"$\lambda_*=\min\{\lambda_\pm:\lambda_\pm>\varepsilon\}$"),
        (0.13, "5. 检查有限高度", r"$76\leq p_z+\lambda_*d_z\leq84$"),
    ]
    for y, head, formula in rows:
        eq.text(0.02, y, head, transform=eq.transAxes, fontsize=12, color=COLORS["muted"], va="top")
        eq.text(0.02, y - 0.065, formula, transform=eq.transAxes, fontsize=15, va="top")
    eq.text(
        0.02,
        0.015,
        r"推荐口径：只计算圆柱外侧壁，并要求 $\mathbf{d}_r\cdot\mathbf{n}_R<0$。",
        transform=eq.transAxes,
        fontsize=11,
        color=COLORS["ray"],
    )
    fig.savefig(output_dir / "fig02-ray-cylinder-intersection.png", dpi=180, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def scatter_grid(ax, states, colors, title, subtitle) -> None:
    coords = [(col, 9 - row) for row in range(10) for col in range(10)]
    for idx, (x, y) in enumerate(coords):
        ax.scatter(x, y, s=78, color=colors[states[idx]], edgecolor="none")
    ax.set_xlim(-0.8, 9.8)
    ax.set_ylim(-0.8, 9.8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=16, pad=10)
    ax.text(4.5, -0.72, subtitle, ha="center", fontsize=11, color=COLORS["muted"])


def draw_conditional_efficiency(output_dir: Path) -> None:
    fig = plt.figure(figsize=(15.8, 7.4), constrained_layout=True)
    grid = fig.add_gridspec(1, 3, width_ratios=[1.0, 1.0, 1.15])
    all_ax = fig.add_subplot(grid[0, 0])
    clear_ax = fig.add_subplot(grid[0, 1])
    formula_ax = fig.add_subplot(grid[0, 2])
    fig.suptitle("截断效率是阴影遮挡之后的条件效率", fontsize=21)

    first_states = np.array([1] * 15 + [0] * 85)
    first_states = first_states[np.argsort((np.arange(100) * 37) % 101)]
    scatter_grid(
        all_ax,
        first_states,
        {0: COLORS["ray"], 1: COLORS["blocked"]},
        "第一步：全部入射样本 100 条\n" + r"$\eta_{sb}=85/100=0.85$",
        "紫色 15 条被阴影或邻镜遮挡",
    )

    second_states = np.array([1] * 15 + [2] * 68 + [3] * 17)
    second_states = second_states[np.argsort((np.arange(100) * 43) % 103)]
    scatter_grid(
        clear_ax,
        second_states,
        {1: "#E3E5E9", 2: COLORS["hit"], 3: COLORS["miss"]},
        "第二步：只看剩余的 85 条\n" + r"$\eta_{trunc}=68/85=0.80$",
        "绿色 68 条命中；红色 17 条从接收面外溢出",
    )

    formula_ax.axis("off")
    formula_ax.set_title("分母为什么不是 100？", loc="left", fontsize=16, pad=12)
    formula_ax.text(0.02, 0.84, "截断效率只在幸存射线中统计", transform=formula_ax.transAxes, fontsize=12, color=COLORS["muted"])
    formula_ax.text(
        0.02,
        0.71,
        r"$\eta_{trunc,i}=\dfrac{N_{hit}}{N_{clear}}=\dfrac{68}{85}=0.80$",
        transform=formula_ax.transAxes,
        fontsize=18,
    )
    formula_ax.text(0.02, 0.54, "与阴影遮挡效率相乘后", transform=formula_ax.transAxes, fontsize=12, color=COLORS["muted"])
    formula_ax.text(
        0.02,
        0.41,
        r"$\eta_{sb,i}\eta_{trunc,i}$",
        transform=formula_ax.transAxes,
        fontsize=18,
        color=COLORS["ray"],
    )
    formula_ax.text(
        0.02,
        0.30,
        r"$=\dfrac{85}{100}\times\dfrac{68}{85}=\dfrac{68}{100}=0.68$",
        transform=formula_ax.transAxes,
        fontsize=17,
        color=COLORS["ray"],
    )
    formula_ax.text(
        0.02,
        0.15,
        "阴影遮挡损失只在第一步扣除一次。\n截断效率只回答：幸存反射光中有多少击中集热器。",
        transform=formula_ax.transAxes,
        fontsize=12,
        linespacing=1.7,
    )
    formula_ax.text(
        0.02,
        0.035,
        "图中 100、85、68 为说明口径的示意数字，不是附件镜场结果。",
        transform=formula_ax.transAxes,
        fontsize=10.5,
        color=COLORS["muted"],
    )
    fig.savefig(output_dir / "fig03-conditional-truncation-efficiency.png", dpi=180, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw mathematical diagrams for receiver truncation efficiency.")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_style()
    draw_footprint(args.output_dir)
    draw_cylinder_intersection(args.output_dir)
    draw_conditional_efficiency(args.output_dir)


if __name__ == "__main__":
    main()
