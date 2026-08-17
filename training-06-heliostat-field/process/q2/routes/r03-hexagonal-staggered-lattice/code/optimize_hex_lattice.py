#!/usr/bin/env python3
"""Surrogate-assisted NSGA-II and final ray validation for Q2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.optimize import differential_evolution

if not hasattr(np, "row_stack"):
    np.row_stack = np.vstack

HERE = Path(__file__).resolve()
R01_CODE = HERE.parents[2] / "r01-common-size-field-optimization" / "code"
sys.path.insert(0, str(R01_CODE))

from optimize_common_size import (
    configure_plots,
    plot_final_field,
    plot_monthly_convergence,
    plot_q1_q2_comparison,
    read_csv_row,
    write_csv,
    write_tables,
)
from q2_model import Design, aggregate_time_rows, all_states, evaluate_field
from lattice_model import LatticeDesign, generate_lattice, lattice_checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--screen-run", required=True, type=Path)
    parser.add_argument("--q1-annual", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--population", type=int, default=56)
    parser.add_argument("--generations", type=int, default=40)
    parser.add_argument("--final-samples", type=int, default=256)
    return parser.parse_args()


def setup_logging(output: Path) -> logging.Logger:
    logger = logging.getLogger("q2-hex-final")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in [logging.StreamHandler(), logging.FileHandler(output / "logs" / "run.log", encoding="utf-8")]:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def ray_design(design: LatticeDesign) -> Design:
    return Design(
        design.tower_x,
        design.tower_y,
        design.width,
        design.height,
        design.center_z,
        100.0,
        0.0,
        design.clearance,
        520.0,
        design.phase,
    )


def evaluate_annual(design: LatticeDesign, samples: int, seed: int, store: bool = False, logger=None):
    xy = generate_lattice(design)
    rows, mirror = evaluate_field(
        ray_design(design),
        xy,
        samples=samples,
        seed=seed,
        neighbor_radius=70.0,
        states=all_states(),
        store_per_mirror=store,
        logger=logger,
    )
    monthly, annual = aggregate_time_rows(rows, design.area * len(xy))
    return xy, rows, monthly, annual, mirror


def load_existing_training(screen_run: Path) -> list[dict[str, float]]:
    path = screen_run / "results" / "full_year_hex_screen.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output = []
    for row in rows:
        output.append(
            {
                "source": "screen",
                "tower_y_m": float(row["tower_y_m"]),
                "width_m": float(row["width_m"]),
                "height_m": float(row["height_m"]),
                "mirror_count": float(row["mirror_count"]),
                "total_area_m2": float(row["total_area_m2"]),
                "field_power_mw": float(row["field_power_mw"]),
                "unit_area_power_kw_m2": float(row["unit_area_power_kw_m2"]),
            }
        )
    return output


def targeted_training(seed: int, logger: logging.Logger) -> list[dict[str, float]]:
    rows = []
    total = 12
    index = 0
    for tower_y in (-60.0, -80.0, -100.0):
        for height in (6.25, 6.35, 6.45, 6.55):
            index += 1
            design = LatticeDesign(0.0, tower_y, 6.8, height, max(3.2, height / 2.0), 0.0, 0.0)
            xy, _, _, annual, _ = evaluate_annual(design, 16, seed)
            rows.append(
                {
                    "source": "targeted",
                    "tower_y_m": tower_y,
                    "width_m": 6.8,
                    "height_m": height,
                    "mirror_count": float(len(xy)),
                    "total_area_m2": design.area * len(xy),
                    "field_power_mw": annual["field_power_mw"],
                    "unit_area_power_kw_m2": annual["unit_area_power_kw_m2"],
                }
            )
            logger.info(
                "Targeted training %d/%d y=%.0f H=%.2f P=%.3f unit=%.4f",
                index,
                total,
                tower_y,
                height,
                annual["field_power_mw"],
                annual["unit_area_power_kw_m2"],
            )
    return rows


class Surrogate:
    def __init__(self, training: list[dict[str, float]]):
        self.lower = np.array([-120.0, 6.0, 5.8])
        self.upper = np.array([-40.0, 8.0, 8.0])
        x = np.array([[row["tower_y_m"], row["width_m"], row["height_m"]] for row in training])
        y = np.array([[row["field_power_mw"], row["unit_area_power_kw_m2"]] for row in training])
        self.x = (x - self.lower) / (self.upper - self.lower)
        self.y = y
        self.model = RBFInterpolator(self.x, y, kernel="thin_plate_spline", smoothing=0.20, degree=1)

    def predict(self, values: np.ndarray) -> np.ndarray:
        scaled = (np.atleast_2d(values) - self.lower) / (self.upper - self.lower)
        return self.model(scaled)

    def loocv(self) -> list[dict[str, float]]:
        rows = []
        for index in range(len(self.x)):
            keep = np.arange(len(self.x)) != index
            model = RBFInterpolator(
                self.x[keep], self.y[keep], kernel="thin_plate_spline", smoothing=0.20, degree=1
            )
            prediction = model(self.x[index : index + 1])[0]
            rows.append(
                {
                    "sample": float(index + 1),
                    "actual_power_mw": float(self.y[index, 0]),
                    "predicted_power_mw": float(prediction[0]),
                    "actual_unit_area_power_kw_m2": float(self.y[index, 1]),
                    "predicted_unit_area_power_kw_m2": float(prediction[1]),
                }
            )
        return rows


def optimize_surrogate(surrogate: Surrogate, population: int, generations: int, seed: int):
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.core.callback import Callback
    from pymoo.core.problem import ElementwiseProblem
    from pymoo.optimize import minimize

    records: list[dict[str, float]] = []
    convergence: list[dict[str, float]] = []

    class Problem(ElementwiseProblem):
        def __init__(self):
            super().__init__(n_var=3, n_obj=2, n_ieq_constr=2, xl=np.array([-110.0, 6.3, 5.9]), xu=np.array([-45.0, 7.3, 7.3]))

        def _evaluate(self, x, out, *args, **kwargs):
            prediction = surrogate.predict(x)[0]
            design = LatticeDesign(0.0, x[0], x[1], x[2], max(3.1, x[2] / 2.0), 0.0, 0.0)
            count = len(generate_lattice(design))
            area = design.area * count
            out["F"] = [-prediction[1], area / 100000.0]
            out["G"] = [60.30 - prediction[0], x[2] - x[1]]
            records.append(
                {
                    "tower_y_m": float(x[0]),
                    "width_m": float(x[1]),
                    "height_m": float(x[2]),
                    "mirror_count": float(count),
                    "total_area_m2": float(area),
                    "predicted_power_mw": float(prediction[0]),
                    "predicted_unit_area_power_kw_m2": float(prediction[1]),
                }
            )

    class History(Callback):
        def notify(self, algorithm):
            f = np.asarray(algorithm.pop.get("F"), dtype=float)
            g = np.asarray(algorithm.pop.get("G"), dtype=float)
            feasible = np.all(g <= 0, axis=1)
            convergence.append(
                {
                    "generation": float(algorithm.n_gen),
                    "feasible_count": float(np.sum(feasible)),
                    "best_unit_area_power_kw_m2": float(np.max(-f[feasible, 0])) if np.any(feasible) else float(np.max(-f[:, 0])),
                }
            )

    anchors = np.array(
        [
            [-60.0, 6.8, 6.4],
            [-80.0, 6.8, 6.4],
            [-100.0, 6.8, 6.4],
            [-60.0, 6.8, 6.8],
            [-80.0, 7.2, 7.2],
        ]
    )
    rng = np.random.default_rng(seed)
    random_values = np.column_stack(
        [rng.uniform(-110, -45, population), rng.uniform(6.3, 7.3, population), rng.uniform(5.9, 7.3, population)]
    )
    random_values[:, 2] = np.minimum(random_values[:, 2], random_values[:, 1])
    random_values[: len(anchors)] = anchors
    callback = History()
    result = minimize(
        Problem(),
        NSGA2(pop_size=population, sampling=random_values, eliminate_duplicates=True),
        ("n_gen", generations),
        seed=seed,
        callback=callback,
        verbose=True,
    )
    feasible = [row for row in records if row["predicted_power_mw"] >= 60.30 and row["height_m"] <= row["width_m"]]
    if not feasible:
        raise RuntimeError("Surrogate NSGA-II produced no feasible candidate.")
    chosen = max(feasible, key=lambda row: row["predicted_unit_area_power_kw_m2"])
    x0 = np.array([chosen["tower_y_m"], chosen["width_m"], chosen["height_m"]])

    def objective(x):
        prediction = surrogate.predict(x)[0]
        penalty = 5.0 * max(0.0, 60.4 - prediction[0]) ** 2 + 20.0 * max(0.0, x[2] - x[1]) ** 2
        return -prediction[1] + penalty

    bounds = [(max(-110, x0[0] - 10), min(-45, x0[0] + 10)), (max(6.3, x0[1] - 0.25), min(7.3, x0[1] + 0.25)), (max(5.9, x0[2] - 0.25), min(7.3, x0[2] + 0.25))]
    refined = differential_evolution(objective, bounds, seed=seed + 9, maxiter=10, popsize=6, x0=x0, polish=True)
    x = refined.x if refined.x[2] <= refined.x[1] else x0
    return LatticeDesign(0.0, float(x[0]), float(x[1]), float(x[2]), max(3.1, float(x[2]) / 2.0), 0.0, 0.0), records, convergence


def candidate_verification(nsga: LatticeDesign, training: list[dict[str, float]], seed: int, logger: logging.Logger):
    feasible_training = sorted(
        [row for row in training if row["field_power_mw"] >= 60.25 and row["height_m"] <= row["width_m"]],
        key=lambda row: row["unit_area_power_kw_m2"],
        reverse=True,
    )[:3]
    candidates = [nsga]
    for row in feasible_training:
        candidates.append(
            LatticeDesign(0.0, row["tower_y_m"], row["width_m"], row["height_m"], max(3.1, row["height_m"] / 2.0), 0.0, 0.0)
        )
    verified = []
    seen = set()
    for design in candidates:
        key = tuple(round(value, 5) for value in [design.tower_y, design.width, design.height])
        if key in seen:
            continue
        seen.add(key)
        xy, _, _, annual, _ = evaluate_annual(design, 32, seed)
        verified.append((design, xy, annual))
        logger.info("Candidate verify y=%.2f W=%.3f H=%.3f P=%.3f unit=%.4f", design.tower_y, design.width, design.height, annual["field_power_mw"], annual["unit_area_power_kw_m2"])
    feasible = [item for item in verified if item[2]["field_power_mw"] >= 60.45]
    if not feasible:
        best = max(verified, key=lambda item: item[2]["field_power_mw"])
        design = best[0]
        for _ in range(6):
            design = replace(design, height=min(design.width, design.height + 0.06), center_z=max(3.1, min(design.width, design.height + 0.06) / 2.0))
            xy, _, _, annual, _ = evaluate_annual(design, 32, seed)
            verified.append((design, xy, annual))
            if annual["field_power_mw"] >= 60.45:
                feasible.append((design, xy, annual))
                break
    if not feasible:
        raise RuntimeError("No 32-ray candidate has a sufficient power margin.")
    return max(feasible, key=lambda item: item[2]["unit_area_power_kw_m2"]), verified


def plot_parameter_diagram(output: Path, design: LatticeDesign, xy: np.ndarray) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4), constrained_layout=True)
    axes[0].scatter(xy[:, 0], xy[:, 1], s=2, color="#3b8c6e", alpha=0.7)
    axes[0].add_patch(plt.Circle((0, 0), 350, fill=False, color="#263238"))
    axes[0].add_patch(plt.Circle((design.tower_x, design.tower_y), 100, fill=False, color="#c43c39", linestyle="--"))
    axes[0].scatter([design.tower_x], [design.tower_y], marker="^", s=85, color="#c46a1a")
    axes[0].set_aspect("equal")
    axes[0].set_title("A  场区、塔位与六角交错点阵")
    axes[0].set_xlabel("x / m")
    axes[0].set_ylabel("y / m")
    axes[0].grid(True)
    d = design.spacing
    points = np.array([[0, 0], [d, 0], [d / 2, math.sqrt(3) * d / 2], [1.5 * d, math.sqrt(3) * d / 2]])
    axes[1].scatter(points[:, 0], points[:, 1], s=180, color="#3b8c6e")
    for a, b in [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3)]:
        axes[1].plot(points[[a, b], 0], points[[a, b], 1], color="#82909a", linewidth=1.2)
    axes[1].annotate("", xy=points[1], xytext=points[0], arrowprops=dict(arrowstyle="<->", color="#2f6f9f"))
    axes[1].text(d / 2, -0.08 * d, f"d = W + 5 = {d:.2f} m", ha="center")
    axes[1].annotate("", xy=(1.7 * d, math.sqrt(3) * d / 2), xytext=(1.7 * d, 0), arrowprops=dict(arrowstyle="<->", color="#74559a"))
    axes[1].text(1.75 * d, math.sqrt(3) * d / 4, "√3 d / 2", va="center")
    axes[1].set_xlim(-0.25 * d, 2.1 * d)
    axes[1].set_ylim(-0.25 * d, 1.2 * d)
    axes[1].set_aspect("equal")
    axes[1].set_title("B  单元参数与奇偶行半步错位")
    axes[1].axis("off")
    fig.suptitle("六角交错定日镜场参数化布局", fontsize=16)
    fig.savefig(output / "figures" / "fig01-hexagonal-layout-parameters.png", dpi=190)
    plt.close(fig)


def plot_filtering(output: Path, design: LatticeDesign) -> None:
    raw, accepted = generate_lattice(design, return_raw=True)
    near = raw[(np.abs(raw[:, 0]) <= 390) & (np.abs(raw[:, 1]) <= 390)]
    site = near[np.hypot(near[:, 0], near[:, 1]) <= 350]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    for ax, points, title, color in [
        (axes[0], near, "A  无限点阵候选", "#7d99af"),
        (axes[1], site, "B  场区边界裁剪", "#c46a1a"),
        (axes[2], accepted, "C  禁建区裁剪后最终镜位", "#3b8c6e"),
    ]:
        ax.scatter(points[:, 0], points[:, 1], s=2, color=color, alpha=0.7)
        ax.add_patch(plt.Circle((0, 0), 350, fill=False, color="#263238"))
        ax.add_patch(plt.Circle((design.tower_x, design.tower_y), 100, fill=False, color="#c43c39", linestyle="--"))
        ax.set_aspect("equal")
        ax.set_xlim(-400, 400)
        ax.set_ylim(-400, 400)
        ax.set_title(title)
        ax.set_xlabel("x / m")
        ax.set_ylabel("y / m")
        ax.grid(True, linewidth=0.5)
    fig.suptitle("布局生成与几何约束筛选", fontsize=16)
    fig.savefig(output / "figures" / "fig02-layout-generation-and-filtering.png", dpi=190)
    plt.close(fig)


def plot_pareto(output: Path, records: list[dict[str, float]], final_area: float, final_unit: float) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 6), constrained_layout=True)
    area = np.array([r["total_area_m2"] for r in records]) / 1000
    unit = np.array([r["predicted_unit_area_power_kw_m2"] for r in records])
    power = np.array([r["predicted_power_mw"] for r in records])
    feasible = power >= 60.3
    ax.scatter(area[~feasible], unit[~feasible], s=9, color="#bcc2c7", alpha=0.35, label="代理不可行")
    mark = ax.scatter(area[feasible], unit[feasible], c=power[feasible], cmap="viridis", s=16, alpha=0.65, label="代理可行")
    ax.scatter([final_area / 1000], [final_unit], marker="*", s=230, color="#c43c39", edgecolor="white", label="最终光线复算方案", zorder=5)
    ax.set_title("NSGA-II 面积-单位功率 Pareto 分布")
    ax.set_xlabel("总镜面面积 / 10^3 m2")
    ax.set_ylabel("单位面积年平均功率 / (kW/m2)")
    ax.grid(True)
    ax.legend(frameon=False)
    fig.colorbar(mark, ax=ax, label="代理年平均功率 / MW")
    fig.savefig(output / "figures" / "fig03-nsga2-pareto-front.png", dpi=190)
    plt.close(fig)


def plot_convergence_accuracy(output: Path, convergence: list[dict[str, float]], cv: list[dict[str, float]]) -> dict[str, float]:
    actual = np.array([r["actual_power_mw"] for r in cv])
    predicted = np.array([r["predicted_power_mw"] for r in cv])
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    denominator = float(np.sum((actual - np.mean(actual)) ** 2))
    r2 = 1 - float(np.sum((actual - predicted) ** 2)) / denominator if denominator else 1.0
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    axes[0].plot([r["generation"] for r in convergence], [r["best_unit_area_power_kw_m2"] for r in convergence], color="#2f6f9f", linewidth=2)
    axes[0].set_title("A  NSGA-II 收敛")
    axes[0].set_xlabel("代数")
    axes[0].set_ylabel("当代最优代理单位功率 / (kW/m2)")
    axes[0].grid(True)
    low = min(actual.min(), predicted.min()) - 0.5
    high = max(actual.max(), predicted.max()) + 0.5
    axes[1].plot([low, high], [low, high], linestyle="--", color="#626b72")
    axes[1].scatter(actual, predicted, color="#c46a1a", s=42)
    axes[1].set_xlim(low, high)
    axes[1].set_ylim(low, high)
    axes[1].set_aspect("equal", adjustable="box")
    axes[1].set_title(f"B  RBF 留一法验证（RMSE={rmse:.2f} MW）")
    axes[1].set_xlabel("真实 16 光线功率 / MW")
    axes[1].set_ylabel("留一预测功率 / MW")
    axes[1].grid(True)
    fig.savefig(output / "figures" / "fig04-convergence-and-surrogate-accuracy.png", dpi=190)
    plt.close(fig)
    return {"surrogate_power_rmse_mw": rmse, "surrogate_power_r2": r2}


def main() -> None:
    args = parse_args()
    for folder in ["results", "figures", "validation", "logs"]:
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    configure_plots()
    logger = setup_logging(args.output)
    training = load_existing_training(args.screen_run)
    training.extend(targeted_training(args.seed, logger))
    write_csv(args.output / "results" / "surrogate_training.csv", training)
    surrogate = Surrogate(training)
    cv_rows = surrogate.loocv()
    write_csv(args.output / "results" / "surrogate_loocv.csv", cv_rows)
    nsga_design, optimization_records, convergence = optimize_surrogate(
        surrogate, args.population, args.generations, args.seed
    )
    logger.info("NSGA candidate %s", asdict(nsga_design))
    (selected_design, selected_xy, _), verified = candidate_verification(nsga_design, training, args.seed, logger)
    write_csv(
        args.output / "results" / "candidate_verification.csv",
        [
            {
                **asdict(design),
                "mirror_count": len(xy),
                "total_area_m2": design.area * len(xy),
                **annual,
            }
            for design, xy, annual in verified
        ],
    )
    ray_convergence = []
    final_rows = final_monthly = final_annual = final_mirror = None
    final_xy = selected_xy
    for samples in sorted(set([32, 64, 128, args.final_samples])):
        final_xy, rows, monthly, annual, mirror = evaluate_annual(
            selected_design, samples, args.seed, store=samples == args.final_samples, logger=logger
        )
        ray_convergence.append(
            {
                "samples": float(samples),
                "field_power_mw": annual["field_power_mw"],
                "unit_area_power_kw_m2": annual["unit_area_power_kw_m2"],
                "avg_optical_efficiency": annual["avg_optical_efficiency"],
            }
        )
        if samples == args.final_samples:
            final_rows, final_monthly, final_annual, final_mirror = rows, monthly, annual, mirror
    if final_annual is None or final_mirror is None or final_annual["field_power_mw"] < 60.0:
        raise RuntimeError(f"Final 256-ray design is infeasible: {None if final_annual is None else final_annual['field_power_mw']}")
    q1 = read_csv_row(args.q1_annual)
    checks = lattice_checks(selected_design, final_xy)
    accuracy = plot_convergence_accuracy(args.output, convergence, cv_rows)
    annual_output = {
        **final_annual,
        "mirror_count": len(final_xy),
        "mirror_width_m": selected_design.width,
        "mirror_height_m": selected_design.height,
        "mirror_center_z_m": selected_design.center_z,
        "tower_x_m": selected_design.tower_x,
        "tower_y_m": selected_design.tower_y,
        "samples_per_mirror_time": args.final_samples,
        "seed": args.seed,
        "neighbor_radius_m": 70.0,
    }
    position_rows = [
        {"mirror_id": i, "x_m": float(p[0]), "y_m": float(p[1]), "z_m": selected_design.center_z}
        for i, p in enumerate(final_xy, 1)
    ]
    monthly_rows = [{k: (int(v) if k == "month" else v) for k, v in row.items()} for row in final_monthly]
    time_rows = [{k: (int(v) if k == "month" else v) for k, v in row.items()} for row in final_rows]
    mirror_rows = [
        {
            "mirror_id": i,
            "x_m": float(p[0]),
            "y_m": float(p[1]),
            "annual_optical_efficiency": float(m[0]),
            "annual_cosine_efficiency": float(m[1]),
            "annual_atmospheric_efficiency": float(m[2]),
            "annual_shadow_blocking_efficiency": float(m[3]),
            "annual_truncation_efficiency": float(m[4]),
        }
        for i, (p, m) in enumerate(zip(final_xy, final_mirror), 1)
    ]
    write_csv(args.output / "results" / "optimization_samples.csv", optimization_records)
    write_csv(args.output / "results" / "optimization_convergence.csv", convergence)
    write_csv(args.output / "results" / "ray_sample_convergence.csv", ray_convergence)
    write_csv(args.output / "results" / "heliostat_positions.csv", position_rows)
    write_csv(args.output / "results" / "time_metrics.csv", time_rows)
    write_csv(args.output / "results" / "monthly_metrics.csv", monthly_rows)
    write_csv(args.output / "results" / "annual_metrics.csv", [annual_output])
    write_csv(args.output / "results" / "mirror_annual_metrics.csv", mirror_rows)
    (args.output / "results" / "design.json").write_text(json.dumps({**asdict(selected_design), **annual_output}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "results" / "result2-data.json").write_text(
        json.dumps(
            {
                "tower_x": selected_design.tower_x,
                "tower_y": selected_design.tower_y,
                "width": selected_design.width,
                "height": selected_design.height,
                "center_z": selected_design.center_z,
                "positions": [[i, float(p[0]), float(p[1])] for i, p in enumerate(final_xy, 1)],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    write_tables(args.output, ray_design(selected_design), monthly_rows, annual_output, len(final_xy))
    plot_parameter_diagram(args.output, selected_design, final_xy)
    plot_filtering(args.output, selected_design)
    plot_pareto(args.output, optimization_records, selected_design.area * len(final_xy), annual_output["unit_area_power_kw_m2"])
    plot_final_field(args.output, ray_design(selected_design), final_xy, final_mirror)
    plot_q1_q2_comparison(args.output, q1, annual_output)
    plot_monthly_convergence(args.output, monthly_rows, ray_convergence)
    validation = {
        **checks,
        **accuracy,
        "annual_power_constraint_satisfied": annual_output["field_power_mw"] >= 60.0,
        "annual_power_mw": annual_output["field_power_mw"],
        "unit_area_power_kw_m2": annual_output["unit_area_power_kw_m2"],
        "ray_128_to_256_absolute_change_kw_m2": abs(ray_convergence[-1]["unit_area_power_kw_m2"] - ray_convergence[-2]["unit_area_power_kw_m2"]),
        "maximum_required_neighbor_radius_m": max(row["required_neighbor_radius_m"] for row in final_rows),
        "configured_neighbor_radius_m": 70.0,
        "figure_count": len(list((args.output / "figures").glob("*.png"))),
        "optimization_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "lattice_code_sha256": hashlib.sha256((Path(__file__).parent / "lattice_model.py").read_bytes()).hexdigest(),
    }
    (args.output / "validation" / "checks.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("FINAL %s", json.dumps({**asdict(selected_design), **annual_output}, ensure_ascii=False))


if __name__ == "__main__":
    main()
