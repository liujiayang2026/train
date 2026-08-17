#!/usr/bin/env python3
"""Optimize, ray-validate, and visualize the common-size heliostat field."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import shutil
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from scipy.optimize import differential_evolution

# pymoo 0.6.1.5 still uses the NumPy 1.x alias removed in NumPy 2.x.
if not hasattr(np, "row_stack"):
    np.row_stack = np.vstack

from q2_model import (
    Design,
    EXCLUSION_RADIUS,
    SITE_RADIUS,
    aggregate_time_rows,
    all_states,
    evaluate_field,
    generate_layout,
    layout_checks,
    proxy_calibration_factor,
    proxy_metrics_from_xy,
    read_scalar_csv,
    read_xy_workbook,
    validation_states,
)


VARIABLE_NAMES = [
    "tower_x",
    "tower_y",
    "width",
    "height",
    "center_z",
    "first_radius",
    "radial_clearance",
    "tangential_clearance",
    "max_radius",
    "phase",
]
LOWER = np.array([-60.0, -160.0, 4.5, 4.5, 3.0, 100.0, 0.0, 0.0, 360.0, 0.0])
UPPER = np.array([60.0, 60.0, 7.5, 7.5, 6.0, 125.0, 5.0, 5.0, 520.0, 2.0 * math.pi])
PROXY_CONSTRAINT_MW = 60.0
SELECTION_TARGET_MW = 60.4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--q1-input", required=True, type=Path)
    parser.add_argument("--q1-annual", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--population", type=int, default=56)
    parser.add_argument("--generations", type=int, default=36)
    parser.add_argument("--final-samples", type=int, default=256)
    parser.add_argument("--neighbor-radius", type=float, default=55.0)
    return parser.parse_args()


def setup_logging(output: Path) -> logging.Logger:
    logger = logging.getLogger("q2-optimization")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(output / "logs" / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv_row(path: Path) -> dict[str, float]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw = next(csv.DictReader(handle))
    return {key: float(value) for key, value in raw.items()}


def configure_plots() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial"],
            "axes.unicode_minus": False,
            "axes.edgecolor": "#4b5563",
            "axes.labelcolor": "#263238",
            "xtick.color": "#4b5563",
            "ytick.color": "#4b5563",
            "text.color": "#263238",
            "figure.facecolor": "#fafaf8",
            "axes.facecolor": "#ffffff",
            "grid.color": "#d7dde2",
            "grid.alpha": 0.55,
        }
    )


def initial_population(population: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    values = LOWER + rng.random((population, len(LOWER))) * (UPPER - LOWER)
    values[:, 3] = np.minimum(values[:, 3], values[:, 2])
    values[:, 4] = np.maximum(values[:, 4], values[:, 3] / 2.0)
    anchors = []
    for tower_y in (-100.0, -120.0, -140.0):
        for width in (5.6, 5.8, 6.0):
            anchors.append([0.0, tower_y, width, width, max(3.0, width / 2.0), 100.0, 0.0, 0.0, 500.0, 0.0])
    anchors_array = np.asarray(anchors[:population], dtype=float)
    values[: len(anchors_array)] = anchors_array
    return values


def make_problem(calibration: float, records: list[dict[str, float]], convergence: list[dict[str, float]]):
    from pymoo.core.callback import Callback
    from pymoo.core.problem import ElementwiseProblem

    cache: dict[tuple[float, ...], tuple[dict[str, float], np.ndarray]] = {}

    class FieldProblem(ElementwiseProblem):
        def __init__(self):
            super().__init__(n_var=10, n_obj=2, n_ieq_constr=4, xl=LOWER, xu=UPPER)

        def _evaluate(self, x, out, *args, **kwargs):
            key = tuple(np.round(x, 7))
            if key in cache:
                metrics, _ = cache[key]
            else:
                design = Design.from_array(x)
                xy = generate_layout(design)
                metrics = proxy_metrics_from_xy(design, xy, calibration)
                cache[key] = (metrics, xy)
                record = {name: float(value) for name, value in zip(VARIABLE_NAMES, x)}
                record.update(metrics)
                record["height_minus_width"] = design.height - design.width
                record["height_clearance"] = design.height / 2.0 - design.center_z
                record["tower_radius_m"] = math.hypot(design.tower_x, design.tower_y)
                records.append(record)
            out["F"] = [-metrics["unit_area_power_kw_m2"], metrics["total_area_m2"] / 100000.0]
            design = Design.from_array(x)
            out["G"] = [
                PROXY_CONSTRAINT_MW - metrics["field_power_mw"],
                design.height - design.width,
                design.height / 2.0 - design.center_z,
                math.hypot(design.tower_x, design.tower_y) - 180.0,
            ]

    class History(Callback):
        def notify(self, algorithm):
            f = np.asarray(algorithm.pop.get("F"), dtype=float)
            g = np.asarray(algorithm.pop.get("G"), dtype=float)
            feasible = np.all(g <= 0.0, axis=1)
            if np.any(feasible):
                unit = float(np.max(-f[feasible, 0]))
                area = float(np.min(f[feasible, 1]) * 100000.0)
            else:
                unit = float(np.max(-f[:, 0]))
                area = float(np.min(f[:, 1]) * 100000.0)
            convergence.append(
                {
                    "generation": float(algorithm.n_gen),
                    "feasible_count": float(np.sum(feasible)),
                    "best_unit_area_power_kw_m2": unit,
                    "minimum_area_m2": area,
                }
            )

    return FieldProblem(), History()


def design_constraints_ok(record: dict[str, float]) -> bool:
    return (
        record["height"] <= record["width"] + 1.0e-9
        and record["center_z"] + 1.0e-9 >= record["height"] / 2.0
        and record["tower_radius_m"] <= 180.0 + 1.0e-9
    )


def refine_design(seed_design: Design, calibration: float, seed: int, logger: logging.Logger) -> Design:
    center = seed_design.as_array()
    spans = np.array([8.0, 10.0, 0.35, 0.35, 0.35, 3.0, 0.8, 0.8, 15.0, 0.35])
    bounds = [(max(LOWER[i], center[i] - spans[i]), min(UPPER[i], center[i] + spans[i])) for i in range(10)]

    def objective(x: np.ndarray) -> float:
        design = Design.from_array(x)
        xy = generate_layout(design)
        metrics = proxy_metrics_from_xy(design, xy, calibration)
        penalty = 0.0
        penalty += 4.0 * max(0.0, SELECTION_TARGET_MW - metrics["field_power_mw"]) ** 2
        penalty += 20.0 * max(0.0, design.height - design.width) ** 2
        penalty += 20.0 * max(0.0, design.height / 2.0 - design.center_z) ** 2
        return -metrics["unit_area_power_kw_m2"] + penalty

    result = differential_evolution(
        objective,
        bounds,
        seed=seed + 41,
        maxiter=8,
        popsize=5,
        polish=True,
        workers=1,
        updating="immediate",
        x0=center,
        tol=2.0e-4,
    )
    logger.info("Differential-evolution refinement: success=%s objective=%.6f", result.success, result.fun)
    refined = Design.from_array(result.x)
    refined_metrics = proxy_metrics_from_xy(refined, generate_layout(refined), calibration)
    seed_metrics = proxy_metrics_from_xy(seed_design, generate_layout(seed_design), calibration)
    if (
        refined.height <= refined.width
        and refined.center_z >= refined.height / 2.0
        and refined_metrics["field_power_mw"] >= SELECTION_TARGET_MW
        and refined_metrics["unit_area_power_kw_m2"] >= seed_metrics["unit_area_power_kw_m2"]
    ):
        return refined
    return seed_design


def select_validation_designs(records: list[dict[str, float]], count: int = 6) -> list[Design]:
    feasible = [
        row
        for row in records
        if row["field_power_mw"] >= PROXY_CONSTRAINT_MW and design_constraints_ok(row)
    ]
    feasible.sort(key=lambda row: row["total_area_m2"])
    if not feasible:
        return []
    indices = np.unique(np.linspace(0, len(feasible) - 1, min(count, len(feasible))).astype(int))
    return [Design.from_array([feasible[i][name] for name in VARIABLE_NAMES]) for i in indices]


def reduced_ray_validation(
    designs: list[Design], calibration: float, seed: int, neighbor_radius: float, logger: logging.Logger
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    states = validation_states()
    for index, design in enumerate(designs, start=1):
        xy = generate_layout(design)
        proxy = proxy_metrics_from_xy(design, xy, calibration, states=states)
        ray_rows, _ = evaluate_field(
            design,
            xy,
            samples=16,
            seed=seed + 100 + index,
            neighbor_radius=neighbor_radius,
            states=states,
            store_per_mirror=False,
        )
        _, ray = aggregate_time_rows(ray_rows, design.area * len(xy))
        rows.append(
            {
                "candidate": float(index),
                "mirror_count": float(len(xy)),
                "total_area_m2": design.area * len(xy),
                "proxy_unit_area_power_kw_m2": proxy["unit_area_power_kw_m2"],
                "ray_unit_area_power_kw_m2": ray["unit_area_power_kw_m2"],
                "proxy_power_mw": proxy["field_power_mw"],
                "ray_power_mw": ray["field_power_mw"],
            }
        )
        logger.info("Reduced ray validation candidate %d/%d complete", index, len(designs))
    return rows


def ensure_power_margin(
    design: Design,
    samples: int,
    seed: int,
    neighbor_radius: float,
    logger: logging.Logger,
) -> tuple[Design, np.ndarray, list[dict[str, float]], dict[str, float]]:
    current = design
    for attempt in range(6):
        xy = generate_layout(current)
        rows, _ = evaluate_field(
            current,
            xy,
            samples=samples,
            seed=seed,
            neighbor_radius=neighbor_radius,
            states=all_states(),
            store_per_mirror=False,
            logger=logger,
        )
        _, annual = aggregate_time_rows(rows, current.area * len(xy))
        logger.info(
            "Power precheck attempt %d: N=%d area=%.1f m2 power=%.3f MW unit=%.5f kW/m2",
            attempt + 1,
            len(xy),
            current.area * len(xy),
            annual["field_power_mw"],
            annual["unit_area_power_kw_m2"],
        )
        if annual["field_power_mw"] >= 60.05:
            return current, xy, rows, annual
        current = replace(current, max_radius=min(540.0, current.max_radius + current.radial_spacing))
    raise RuntimeError("Unable to establish a ray-traced power margin above 60.05 MW.")


def plot_layout_stages(output: Path, design: Design) -> None:
    stages = generate_layout(design, return_stages=True)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), constrained_layout=True)
    panels = [
        (stages.raw, "A 生成全部交错环", "#3d7ea6"),
        (stages.after_exclusion, "B 施加塔周禁建区", "#d08b3e"),
        (stages.accepted, "C 场区裁剪后的可行布局", "#3b8c6e"),
    ]
    for ax, (points, title, color) in zip(axes, panels):
        ax.scatter(points[:, 0], points[:, 1], s=2.0, color=color, alpha=0.75, rasterized=True)
        site = plt.Circle((0, 0), SITE_RADIUS, fill=False, color="#263238", linewidth=1.2)
        exclusion = plt.Circle(
            (design.tower_x, design.tower_y),
            EXCLUSION_RADIUS,
            facecolor="#f4d7d3",
            edgecolor="#b64f47",
            linewidth=1.0,
            alpha=0.65,
        )
        ax.add_patch(site)
        ax.add_patch(exclusion)
        ax.scatter([design.tower_x], [design.tower_y], marker="^", s=80, color="#c46a1a", zorder=4)
        ax.set_title(title)
        ax.set_aspect("equal")
        ax.set_xlim(-440, 440)
        ax.set_ylim(-440, 440)
        ax.set_xlabel("x / m")
        ax.set_ylabel("y / m")
        ax.grid(True, linewidth=0.5)
    fig.suptitle("交错环形布局的生成与约束筛选", fontsize=16)
    fig.savefig(output / "figures" / "fig02-layout-generation-and-filtering.png", dpi=190)
    plt.close(fig)


def plot_pareto(output: Path, records: list[dict[str, float]], chosen: dict[str, float]) -> None:
    area = np.asarray([row["total_area_m2"] for row in records])
    unit = np.asarray([row["unit_area_power_kw_m2"] for row in records])
    power = np.asarray([row["field_power_mw"] for row in records])
    feasible = np.asarray([row["field_power_mw"] >= PROXY_CONSTRAINT_MW and design_constraints_ok(row) for row in records])
    fig, ax = plt.subplots(figsize=(9.5, 6.2), constrained_layout=True)
    ax.scatter(area[~feasible] / 1000.0, unit[~feasible], s=10, color="#b8bec4", alpha=0.38, label="不可行样本")
    scatter = ax.scatter(
        area[feasible] / 1000.0,
        unit[feasible],
        c=power[feasible],
        s=18,
        cmap="viridis",
        alpha=0.72,
        label="可行样本",
    )
    ax.scatter(
        chosen["total_area_m2"] / 1000.0,
        chosen["unit_area_power_kw_m2"],
        marker="*",
        s=220,
        color="#c43c39",
        edgecolor="white",
        linewidth=1.0,
        label="选定方案",
        zorder=5,
    )
    ax.set_title("NSGA-II 搜索得到的面积-单位功率 Pareto 分布")
    ax.set_xlabel("总镜面面积 / 10^3 m2")
    ax.set_ylabel("代理单位面积年平均功率 / (kW/m2)")
    ax.grid(True)
    ax.legend(frameon=False)
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("代理年平均功率 / MW")
    fig.savefig(output / "figures" / "fig03-nsga2-pareto-front.png", dpi=190)
    plt.close(fig)


def plot_convergence_accuracy(
    output: Path, convergence: list[dict[str, float]], surrogate_rows: list[dict[str, float]]
) -> dict[str, float]:
    x = np.asarray([row["proxy_unit_area_power_kw_m2"] for row in surrogate_rows])
    y = np.asarray([row["ray_unit_area_power_kw_m2"] for row in surrogate_rows])
    if len(x) >= 2:
        coefficient = np.polyfit(x, y, 1)
        predicted = np.polyval(coefficient, x)
        rmse = float(np.sqrt(np.mean((x - y) ** 2)))
        denominator = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - float(np.sum((y - predicted) ** 2)) / denominator if denominator > 0 else 1.0
    else:
        coefficient = np.array([1.0, 0.0])
        rmse = float("nan")
        r2 = float("nan")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.1), constrained_layout=True)
    generations = [row["generation"] for row in convergence]
    best = [row["best_unit_area_power_kw_m2"] for row in convergence]
    axes[0].plot(generations, best, color="#2f6f9f", linewidth=2.2)
    axes[0].scatter(generations, best, color="#2f6f9f", s=12)
    axes[0].set_title("A  优化收敛过程")
    axes[0].set_xlabel("迭代代数")
    axes[0].set_ylabel("当代最优单位面积功率 / (kW/m2)")
    axes[0].grid(True)
    low = min(float(np.min(x)), float(np.min(y))) - 0.01
    high = max(float(np.max(x)), float(np.max(y))) + 0.01
    axes[1].plot([low, high], [low, high], color="#626b72", linestyle="--", linewidth=1.4, label="理想一致线")
    axes[1].scatter(x, y, s=48, color="#c46a1a", edgecolor="white", linewidth=0.6)
    axes[1].set_xlim(low, high)
    axes[1].set_ylim(low, high)
    axes[1].set_aspect("equal", adjustable="box")
    axes[1].set_title(f"B  代理与低样本光线复算（RMSE={rmse:.3f}）")
    axes[1].set_xlabel("代理单位面积功率 / (kW/m2)")
    axes[1].set_ylabel("光线复算单位面积功率 / (kW/m2)")
    axes[1].grid(True)
    axes[1].legend(frameon=False)
    fig.savefig(output / "figures" / "fig04-convergence-and-surrogate-accuracy.png", dpi=190)
    plt.close(fig)
    return {"surrogate_rmse_kw_m2": rmse, "surrogate_linear_r2": r2}


def plot_final_field(output: Path, design: Design, xy: np.ndarray, mirror_metrics: np.ndarray) -> None:
    efficiency = mirror_metrics[:, 0]
    fig, ax = plt.subplots(figsize=(8.2, 7.1), constrained_layout=True)
    scatter = ax.scatter(
        xy[:, 0],
        xy[:, 1],
        c=efficiency,
        s=8,
        cmap="turbo",
        norm=Normalize(vmin=float(np.percentile(efficiency, 2)), vmax=float(np.percentile(efficiency, 98))),
        linewidths=0,
        rasterized=True,
    )
    ax.add_patch(plt.Circle((0, 0), SITE_RADIUS, fill=False, color="#263238", linewidth=1.3))
    ax.add_patch(
        plt.Circle(
            (design.tower_x, design.tower_y),
            EXCLUSION_RADIUS,
            fill=False,
            color="#c43c39",
            linestyle="--",
            linewidth=1.3,
        )
    )
    ax.scatter([design.tower_x], [design.tower_y], marker="^", color="black", s=100, label="吸收塔")
    ax.set_title("最终镜场布局与年平均光学效率空间分布")
    ax.set_xlabel("x / m（东）")
    ax.set_ylabel("y / m（北）")
    ax.set_aspect("equal")
    ax.grid(True, linewidth=0.5)
    ax.legend(frameon=False, loc="upper right")
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("单镜年平均光学效率")
    fig.savefig(output / "figures" / "fig05-final-field-spatial-efficiency.png", dpi=210)
    plt.close(fig)


def plot_q1_q2_comparison(output: Path, q1: dict[str, float], q2: dict[str, float]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.7), constrained_layout=True)
    labels = ["光学", "余弦", "阴影遮挡", "截断"]
    keys = [
        "avg_optical_efficiency",
        "avg_cosine_efficiency",
        "avg_shadow_blocking_efficiency",
        "avg_truncation_efficiency",
    ]
    positions = np.arange(len(keys))
    width = 0.36
    axes[0].bar(positions - width / 2, [q1[k] for k in keys], width, label="问题一", color="#7d99af")
    axes[0].bar(positions + width / 2, [q2[k] for k in keys], width, label="问题二", color="#3b8c6e")
    axes[0].set_xticks(positions, labels)
    axes[0].set_ylim(0.45, 1.0)
    axes[0].set_ylabel("年平均效率")
    axes[0].set_title("A  光学效率分量")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="y")
    axes[1].bar(["问题一", "问题二"], [q1["unit_area_power_kw_m2"], q2["unit_area_power_kw_m2"]], color=["#7d99af", "#3b8c6e"])
    axes[1].set_ylabel("kW/m2")
    axes[1].set_title("B  单位面积年平均功率")
    axes[1].grid(axis="y")
    axes[2].bar(["问题一", "问题二"], [q1["field_power_mw"], q2["field_power_mw"]], color=["#7d99af", "#3b8c6e"])
    axes[2].axhline(60.0, color="#c43c39", linestyle="--", linewidth=1.4, label="60 MW 约束")
    axes[2].set_ylabel("MW")
    axes[2].set_title("C  年平均输出功率")
    axes[2].grid(axis="y")
    axes[2].legend(frameon=False)
    fig.suptitle("问题一固定镜场与问题二优化镜场对比", fontsize=15)
    fig.savefig(output / "figures" / "fig06-q1-q2-comparison.png", dpi=190)
    plt.close(fig)


def plot_monthly_convergence(
    output: Path, monthly: list[dict[str, float]], ray_convergence: list[dict[str, float]]
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.1), constrained_layout=True)
    months = [int(row["month"]) for row in monthly]
    axes[0].plot(months, [row["avg_optical_efficiency"] for row in monthly], marker="o", color="#2f6f9f", label="平均光学效率")
    axes[0].plot(months, [row["avg_cosine_efficiency"] for row in monthly], marker="s", color="#74559a", label="平均余弦效率")
    axes[0].set_xlabel("月份")
    axes[0].set_ylabel("效率")
    axes[0].set_xticks(months)
    axes[0].set_title("A  最终方案月度性能")
    axes[0].grid(True)
    axes[0].legend(frameon=False, loc="lower center", ncol=2)
    secondary = axes[0].twinx()
    secondary.plot(months, [row["unit_area_power_kw_m2"] for row in monthly], color="#c46a1a", linewidth=2.0, label="单位面积功率")
    secondary.set_ylabel("单位面积功率 / (kW/m2)", color="#c46a1a")
    samples = [row["samples"] for row in ray_convergence]
    values = [row["unit_area_power_kw_m2"] for row in ray_convergence]
    axes[1].plot(samples, values, marker="o", linewidth=2.2, color="#3b8c6e")
    axes[1].axhline(values[-1], color="#626b72", linestyle="--", linewidth=1.2)
    axes[1].set_xscale("log", base=2)
    axes[1].set_xticks(samples, [str(int(value)) for value in samples])
    axes[1].set_xlabel("每镜每时点 Sobol 光线数")
    axes[1].set_ylabel("单位面积年平均功率 / (kW/m2)")
    axes[1].set_title("B  锥形光束采样收敛性")
    axes[1].grid(True)
    fig.savefig(output / "figures" / "fig07-monthly-performance-and-ray-convergence.png", dpi=190)
    plt.close(fig)


def write_tables(output: Path, design: Design, monthly: list[dict[str, float]], annual: dict[str, float], count: int) -> None:
    lines = [
        "# 问题二计算结果",
        "",
        "## 表 1  每月 21 日平均光学效率及输出功率",
        "",
        "| 日期 | 平均光学效率 | 平均余弦效率 | 平均阴影遮挡效率 | 平均截断效率 | 单位面积镜面平均输出热功率 (kW/m2) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in monthly:
        lines.append(
            f"| {int(row['month'])} 月 21 日 | {row['avg_optical_efficiency']:.4f} | {row['avg_cosine_efficiency']:.4f} | "
            f"{row['avg_shadow_blocking_efficiency']:.4f} | {row['avg_truncation_efficiency']:.4f} | {row['unit_area_power_kw_m2']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## 表 2  年平均光学效率及输出功率",
            "",
            "| 年平均光学效率 | 年平均余弦效率 | 年平均阴影遮挡效率 | 年平均截断效率 | 年平均输出热功率 (MW) | 单位面积镜面年平均输出热功率 (kW/m2) |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {annual['avg_optical_efficiency']:.4f} | {annual['avg_cosine_efficiency']:.4f} | {annual['avg_shadow_blocking_efficiency']:.4f} | {annual['avg_truncation_efficiency']:.4f} | {annual['field_power_mw']:.4f} | {annual['unit_area_power_kw_m2']:.4f} |",
            "",
            "## 表 3  设计参数",
            "",
            "| 吸收塔位置坐标 | 定日镜尺寸（宽 x 高） | 定日镜安装高度 (m) | 定日镜总面数 | 定日镜总面积 (m2) |",
            "|---|---:|---:|---:|---:|",
            f"| ({design.tower_x:.3f}, {design.tower_y:.3f}) | {design.width:.3f} x {design.height:.3f} | {design.center_z:.3f} | {count} | {design.area * count:.3f} |",
        ]
    )
    (output / "results" / "result_tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    for folder in ["results", "figures", "validation", "logs"]:
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    logger = setup_logging(args.output)
    configure_plots()
    q1_xy = read_xy_workbook(args.q1_input)
    q1_unit = read_scalar_csv(args.q1_annual, "unit_area_power_kw_m2")
    calibration = proxy_calibration_factor(q1_xy, q1_unit)
    logger.info("Proxy calibration factor %.8f based on Q1 unit power %.8f", calibration, q1_unit)

    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.optimize import minimize

    records: list[dict[str, float]] = []
    convergence: list[dict[str, float]] = []
    problem, callback = make_problem(calibration, records, convergence)
    algorithm = NSGA2(
        pop_size=args.population,
        sampling=initial_population(args.population, args.seed),
        eliminate_duplicates=True,
    )
    result = minimize(
        problem,
        algorithm,
        ("n_gen", args.generations),
        seed=args.seed,
        callback=callback,
        verbose=True,
        save_history=False,
    )
    logger.info("NSGA-II complete: %d evaluated records", len(records))
    feasible = [
        row
        for row in records
        if row["field_power_mw"] >= SELECTION_TARGET_MW and design_constraints_ok(row)
    ]
    if not feasible:
        feasible = [
            row
            for row in records
            if row["field_power_mw"] >= PROXY_CONSTRAINT_MW and design_constraints_ok(row)
        ]
    if not feasible:
        raise RuntimeError("NSGA-II did not produce a feasible design.")
    chosen_record = max(feasible, key=lambda row: row["unit_area_power_kw_m2"])
    chosen = Design.from_array([chosen_record[name] for name in VARIABLE_NAMES])
    chosen = refine_design(chosen, calibration, args.seed, logger)
    chosen_xy = generate_layout(chosen)
    chosen_proxy = proxy_metrics_from_xy(chosen, chosen_xy, calibration)
    logger.info("Chosen proxy design: %s", json.dumps({**asdict(chosen), **chosen_proxy}, ensure_ascii=False))

    validation_designs = select_validation_designs(records)
    validation_designs.append(chosen)
    surrogate_rows = reduced_ray_validation(
        validation_designs, calibration, args.seed, args.neighbor_radius, logger
    )

    final_design, final_xy, precheck_rows, precheck_annual = ensure_power_margin(
        chosen,
        samples=32,
        seed=args.seed,
        neighbor_radius=args.neighbor_radius,
        logger=logger,
    )
    convergence_samples = [32, 64, 128, args.final_samples]
    convergence_samples = sorted(set(convergence_samples))
    ray_convergence: list[dict[str, float]] = []
    final_rows: list[dict[str, float]] | None = None
    final_mirror_metrics: np.ndarray | None = None
    for samples in convergence_samples:
        if samples == 32 and final_design == chosen:
            rows = precheck_rows
            mirror_metrics = None
        else:
            rows, mirror_metrics = evaluate_field(
                final_design,
                final_xy,
                samples=samples,
                seed=args.seed,
                neighbor_radius=args.neighbor_radius,
                states=all_states(),
                store_per_mirror=samples == args.final_samples,
                logger=logger,
            )
        monthly_candidate, annual_candidate = aggregate_time_rows(
            rows, final_design.area * len(final_xy)
        )
        ray_convergence.append(
            {
                "samples": float(samples),
                "field_power_mw": annual_candidate["field_power_mw"],
                "unit_area_power_kw_m2": annual_candidate["unit_area_power_kw_m2"],
                "avg_optical_efficiency": annual_candidate["avg_optical_efficiency"],
            }
        )
        if samples == args.final_samples:
            final_rows = rows
            final_mirror_metrics = mirror_metrics
            final_monthly = monthly_candidate
            final_annual = annual_candidate
    if final_rows is None or final_mirror_metrics is None:
        raise RuntimeError("Final ray evaluation was not produced.")
    if final_annual["field_power_mw"] < 60.0:
        raise RuntimeError(
            f"Final high-fidelity power {final_annual['field_power_mw']:.4f} MW violates 60 MW."
        )

    final_proxy = proxy_metrics_from_xy(final_design, final_xy, calibration)
    final_record = {**asdict(final_design), **final_proxy}
    layout_validation = layout_checks(final_design, final_xy)
    q1_annual = read_csv_row(args.q1_annual)

    position_rows = [
        {"mirror_id": index, "x_m": float(point[0]), "y_m": float(point[1]), "z_m": final_design.center_z}
        for index, point in enumerate(final_xy, start=1)
    ]
    time_rows = [
        {key: (int(value) if key == "month" else value) for key, value in row.items()}
        for row in final_rows
    ]
    monthly_rows = [
        {key: (int(value) if key == "month" else value) for key, value in row.items()}
        for row in final_monthly
    ]
    annual_output = {
        **final_annual,
        "mirror_count": len(final_xy),
        "mirror_width_m": final_design.width,
        "mirror_height_m": final_design.height,
        "mirror_center_z_m": final_design.center_z,
        "tower_x_m": final_design.tower_x,
        "tower_y_m": final_design.tower_y,
        "samples_per_mirror_time": args.final_samples,
        "seed": args.seed,
        "neighbor_radius_m": args.neighbor_radius,
    }
    mirror_rows = []
    for index, (point, metrics) in enumerate(zip(final_xy, final_mirror_metrics), start=1):
        mirror_rows.append(
            {
                "mirror_id": index,
                "x_m": float(point[0]),
                "y_m": float(point[1]),
                "annual_optical_efficiency": float(metrics[0]),
                "annual_cosine_efficiency": float(metrics[1]),
                "annual_atmospheric_efficiency": float(metrics[2]),
                "annual_shadow_blocking_efficiency": float(metrics[3]),
                "annual_truncation_efficiency": float(metrics[4]),
            }
        )
    unique_records: dict[tuple[float, ...], dict[str, float]] = {}
    for row in records:
        key = tuple(round(row[name], 6) for name in VARIABLE_NAMES)
        unique_records[key] = row
    pareto_rows = list(unique_records.values())
    write_csv(args.output / "results" / "optimization_samples.csv", pareto_rows)
    write_csv(args.output / "results" / "optimization_convergence.csv", convergence)
    write_csv(args.output / "results" / "surrogate_validation.csv", surrogate_rows)
    write_csv(args.output / "results" / "ray_sample_convergence.csv", ray_convergence)
    write_csv(args.output / "results" / "heliostat_positions.csv", position_rows)
    write_csv(args.output / "results" / "time_metrics.csv", time_rows)
    write_csv(args.output / "results" / "monthly_metrics.csv", monthly_rows)
    write_csv(args.output / "results" / "annual_metrics.csv", [annual_output])
    write_csv(args.output / "results" / "mirror_annual_metrics.csv", mirror_rows)
    (args.output / "results" / "design.json").write_text(
        json.dumps({**asdict(final_design), **annual_output}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    workbook_data = {
        "tower_x": final_design.tower_x,
        "tower_y": final_design.tower_y,
        "width": final_design.width,
        "height": final_design.height,
        "center_z": final_design.center_z,
        "positions": [[index, float(x), float(y)] for index, (x, y) in enumerate(final_xy, start=1)],
    }
    (args.output / "results" / "result2-data.json").write_text(
        json.dumps(workbook_data, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_tables(args.output, final_design, monthly_rows, annual_output, len(final_xy))

    source_figure = (
        args.output.parent
        / "run-20260817-1312-staggered-ring-layout-final"
        / "figures"
        / "fig01-staggered-ring-layout-parameters.png"
    )
    if source_figure.exists():
        shutil.copy2(source_figure, args.output / "figures" / "fig01-staggered-ring-layout-parameters.png")
    plot_layout_stages(args.output, final_design)
    plot_pareto(args.output, pareto_rows, final_record)
    accuracy = plot_convergence_accuracy(args.output, convergence, surrogate_rows)
    plot_final_field(args.output, final_design, final_xy, final_mirror_metrics)
    plot_q1_q2_comparison(args.output, q1_annual, annual_output)
    plot_monthly_convergence(args.output, monthly_rows, ray_convergence)

    convergence_error = abs(ray_convergence[-1]["unit_area_power_kw_m2"] - ray_convergence[-2]["unit_area_power_kw_m2"])
    checks = {
        **layout_validation,
        **accuracy,
        "annual_power_constraint_satisfied": final_annual["field_power_mw"] >= 60.0,
        "annual_power_mw": final_annual["field_power_mw"],
        "unit_area_power_kw_m2": final_annual["unit_area_power_kw_m2"],
        "ray_128_to_256_absolute_change_kw_m2": convergence_error,
        "efficiencies_in_unit_interval": bool(
            all(
                0.0 <= row[key] <= 1.0
                for row in final_rows
                for key in [
                    "avg_optical_efficiency",
                    "avg_cosine_efficiency",
                    "avg_shadow_blocking_efficiency",
                    "avg_truncation_efficiency",
                ]
            )
        ),
        "maximum_required_neighbor_radius_m": max(row["required_neighbor_radius_m"] for row in final_rows),
        "configured_neighbor_radius_m": args.neighbor_radius,
        "figure_count": len(list((args.output / "figures").glob("*.png"))),
        "optimization_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "model_code_sha256": hashlib.sha256((Path(__file__).parent / "q2_model.py").read_bytes()).hexdigest(),
    }
    (args.output / "validation" / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Final design: %s", json.dumps({**asdict(final_design), **annual_output}, ensure_ascii=False))
    logger.info("Validation checks: %s", json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
