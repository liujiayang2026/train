#!/usr/bin/env python3
"""Run a reproducible three-zone radial-layout experiment for question 2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
R01_CODE = ROUTES / "r01-common-size-field-optimization" / "code"
sys.path.insert(0, str(R01_CODE))

from q2_model import (
    Design,
    aggregate_time_rows,
    all_states,
    evaluate_field,
    proxy_metrics_from_xy,
    validation_states,
)
from variable_density_radial import (
    RadialDesign,
    generate_layout,
    geometry_checks,
    local_coordinate_improvement,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--r03-run", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--proxy-keep", type=int, default=8)
    parser.add_argument("--screen-keep", type=int, default=3)
    parser.add_argument("--screen-samples", type=int, default=16)
    parser.add_argument("--verify-samples", type=int, default=32)
    parser.add_argument("--final-samples", type=int, default=128)
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    return parser.parse_args()


def setup_logger(output: Path) -> logging.Logger:
    logger = logging.getLogger("q2-radial-experiment")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in [
        logging.StreamHandler(),
        logging.FileHandler(output / "logs" / "run.log", encoding="utf-8"),
    ]:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def ray_design(design: RadialDesign) -> Design:
    mean_radial = float(np.mean(design.radial_factors)) * design.safe_spacing
    mean_tangential = float(np.mean(design.tangential_factors)) * design.safe_spacing
    return Design(
        design.tower_x,
        design.tower_y,
        design.width,
        design.height,
        design.center_z,
        100.0,
        mean_radial - design.minimum_spacing,
        mean_tangential - design.minimum_spacing,
        520.0,
        design.phase,
    )


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv_row(path: Path) -> dict[str, float]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    return {key: float(value) for key, value in row.items() if value not in (None, "")}


def evaluate(
    design: RadialDesign,
    xy: np.ndarray,
    samples: int,
    seed: int,
    neighbor_radius: float,
    states=None,
    store: bool = False,
    logger=None,
):
    rows, mirror = evaluate_field(
        ray_design(design),
        xy,
        samples=samples,
        seed=seed,
        neighbor_radius=neighbor_radius,
        states=states,
        store_per_mirror=store,
        logger=logger,
    )
    monthly, annual = aggregate_time_rows(rows, design.area * len(xy))
    return rows, monthly, annual, mirror


def candidate_designs() -> list[RadialDesign]:
    patterns = [
        ((0.87, 0.90, 0.94), (1.00, 1.03, 1.07)),
        ((0.89, 0.93, 0.98), (1.00, 1.02, 1.05)),
        ((0.92, 0.97, 1.03), (1.00, 1.02, 1.04)),
    ]
    sizes = [(6.2, 5.9), (6.3, 5.9), (6.4, 6.0), (6.5, 6.1), (6.6, 6.2), (6.8, 6.35)]
    designs = []
    for tower_y in (-45.0, -60.0, -75.0):
        for width, height in sizes:
            for radial, tangential in patterns:
                designs.append(
                    RadialDesign(
                        0.0,
                        tower_y,
                        width,
                        height,
                        max(3.1, height / 2.0),
                        0.08,
                        (190.0, 285.0),
                        radial,
                        tangential,
                        0.0,
                    )
                )
    return designs


def design_fields(design: RadialDesign) -> dict:
    return {
        "tower_x_m": design.tower_x,
        "tower_y_m": design.tower_y,
        "width_m": design.width,
        "height_m": design.height,
        "center_z_m": design.center_z,
        "clearance_m": design.clearance,
        "zone_boundary_1_m": design.zone_boundaries[0],
        "zone_boundary_2_m": design.zone_boundaries[1],
        "radial_factors": "/".join(f"{v:.3f}" for v in design.radial_factors),
        "tangential_factors": "/".join(f"{v:.3f}" for v in design.tangential_factors),
    }


def proxy_screen(designs: list[RadialDesign], reference_factor: float, logger: logging.Logger):
    rows = []
    states = all_states()
    for index, design in enumerate(designs, start=1):
        stages = generate_layout(design, states, return_stages=True)
        xy = stages["xy"]
        metrics = proxy_metrics_from_xy(ray_design(design), xy, calibration_factor=reference_factor)
        rows.append(
            {
                "design_id": index,
                **design_fields(design),
                "candidate_count": len(stages["candidates"]),
                "mirror_count": len(xy),
                "total_area_m2": design.area * len(xy),
                **{f"proxy_{key}": value for key, value in metrics.items() if key not in ("mirror_count", "total_area_m2")},
                "design": design,
                "xy": xy,
            }
        )
    logger.info("Proxy screening completed for %d designs", len(rows))
    return rows


def choose_proxy_rows(rows: list[dict], count: int) -> list[dict]:
    feasible = [row for row in rows if row["proxy_field_power_mw"] >= 59.0]
    ranked = sorted(feasible, key=lambda row: row["proxy_unit_area_power_kw_m2"], reverse=True)
    power_ranked = sorted(rows, key=lambda row: row["proxy_field_power_mw"], reverse=True)
    chosen = []
    seen = set()
    for row in ranked + power_ranked:
        key = row["design_id"]
        if key not in seen:
            chosen.append(row)
            seen.add(key)
        if len(chosen) >= count:
            break
    return chosen


def reduced_screen(
    rows: list[dict],
    baseline_reduced: float,
    baseline_full: float,
    args: argparse.Namespace,
    logger: logging.Logger,
):
    output = []
    scale = baseline_full / baseline_reduced
    for index, row in enumerate(rows, start=1):
        _, _, annual, _ = evaluate(
            row["design"],
            row["xy"],
            args.screen_samples,
            args.seed,
            args.neighbor_radius,
            states=validation_states(),
        )
        result = {
            **{key: value for key, value in row.items() if key not in ("design", "xy")},
            **{f"screen_{key}": value for key, value in annual.items()},
            "estimated_full_power_mw": annual["field_power_mw"] * scale,
            "design": row["design"],
            "xy": row["xy"],
        }
        output.append(result)
        logger.info(
            "Reduced screen %d/%d id=%d N=%d P_est=%.3f unit=%.4f",
            index,
            len(rows),
            row["design_id"],
            len(row["xy"]),
            result["estimated_full_power_mw"],
            annual["unit_area_power_kw_m2"],
        )
    return output


def choose_screen_rows(rows: list[dict], count: int) -> list[dict]:
    feasible = [row for row in rows if row["estimated_full_power_mw"] >= 60.2]
    ranked = sorted(feasible, key=lambda row: row["screen_unit_area_power_kw_m2"], reverse=True)
    power_ranked = sorted(rows, key=lambda row: row["estimated_full_power_mw"], reverse=True)
    chosen = []
    seen = set()
    for row in ranked + power_ranked:
        if row["design_id"] not in seen:
            chosen.append(row)
            seen.add(row["design_id"])
        if len(chosen) >= count:
            break
    return chosen


def full_verification(rows: list[dict], args: argparse.Namespace, logger: logging.Logger):
    verified = []
    for index, row in enumerate(rows, start=1):
        _, _, annual, mirror = evaluate(
            row["design"],
            row["xy"],
            args.verify_samples,
            args.seed,
            args.neighbor_radius,
            states=all_states(),
            store=True,
            logger=logger,
        )
        verified.append({**row, "full_annual": annual, "mirror_metrics": mirror})
        logger.info(
            "Full verify %d/%d id=%d P=%.3f unit=%.4f",
            index,
            len(rows),
            row["design_id"],
            annual["field_power_mw"],
            annual["unit_area_power_kw_m2"],
        )
    return verified


def select_verified(rows: list[dict]) -> dict:
    feasible = [row for row in rows if row["full_annual"]["field_power_mw"] >= 60.35]
    if feasible:
        return max(feasible, key=lambda row: row["full_annual"]["unit_area_power_kw_m2"])
    return max(rows, key=lambda row: row["full_annual"]["field_power_mw"])


def iterative_pruning(selected: dict, args: argparse.Namespace, logger: logging.Logger):
    design = selected["design"]
    current_xy = np.array(selected["xy"], copy=True)
    _, _, reduced_annual, mirror = evaluate(
        design,
        current_xy,
        args.screen_samples,
        args.seed,
        args.neighbor_radius,
        states=validation_states(),
        store=True,
    )
    full_power = selected["full_annual"]["field_power_mw"]
    reduced_to_full = full_power / reduced_annual["field_power_mw"]
    target_reduced = 60.45 / reduced_to_full
    history = [
        {
            "iteration": 0,
            "mirror_count": len(current_xy),
            "estimated_full_power_mw": reduced_annual["field_power_mw"] * reduced_to_full,
            "screen_unit_area_power_kw_m2": reduced_annual["unit_area_power_kw_m2"],
            "removed": 0,
            "accepted": True,
        }
    ]
    snapshots = [(np.array(current_xy, copy=True), history[-1])]
    for iteration in range(1, 13):
        batch = max(2, int(math.ceil(len(current_xy) * (0.008 if iteration <= 5 else 0.003))))
        scores = mirror[:, 0]
        remove = np.argsort(scores)[:batch]
        candidate_xy = np.delete(current_xy, remove, axis=0)
        _, _, candidate_annual, candidate_mirror = evaluate(
            design,
            candidate_xy,
            args.screen_samples,
            args.seed,
            args.neighbor_radius,
            states=validation_states(),
            store=True,
        )
        estimated = candidate_annual["field_power_mw"] * reduced_to_full
        accepted = estimated >= 60.45 and candidate_annual["unit_area_power_kw_m2"] > reduced_annual["unit_area_power_kw_m2"]
        history.append(
            {
                "iteration": iteration,
                "mirror_count": len(candidate_xy),
                "estimated_full_power_mw": estimated,
                "screen_unit_area_power_kw_m2": candidate_annual["unit_area_power_kw_m2"],
                "removed": batch,
                "accepted": accepted,
            }
        )
        logger.info(
            "Prune %d remove=%d P_est=%.3f unit=%.4f accepted=%s",
            iteration,
            batch,
            estimated,
            candidate_annual["unit_area_power_kw_m2"],
            accepted,
        )
        if not accepted:
            break
        current_xy = candidate_xy
        reduced_annual = candidate_annual
        mirror = candidate_mirror
        snapshots.append((np.array(current_xy, copy=True), history[-1]))
    return snapshots, history, mirror


def verify_snapshots(
    design: RadialDesign,
    snapshots,
    args: argparse.Namespace,
    logger: logging.Logger,
):
    candidates = snapshots[-3:] if len(snapshots) >= 3 else snapshots
    verified = []
    for index, (xy, metadata) in enumerate(candidates, start=1):
        _, _, annual, mirror = evaluate(
            design,
            xy,
            max(64, args.verify_samples),
            args.seed,
            args.neighbor_radius,
            states=all_states(),
            store=True,
            logger=logger,
        )
        verified.append((xy, metadata, annual, mirror))
        logger.info(
            "Pruned snapshot %d/%d N=%d P=%.3f unit=%.4f",
            index,
            len(candidates),
            len(xy),
            annual["field_power_mw"],
            annual["unit_area_power_kw_m2"],
        )
    feasible = [item for item in verified if item[2]["field_power_mw"] >= 60.20]
    return max(feasible or verified, key=lambda item: item[2]["unit_area_power_kw_m2"])


def plot_results(output: Path, design: RadialDesign, before_xy: np.ndarray, final_xy: np.ndarray, proxy_rows, prune_history, r03, final):
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.6), constrained_layout=True)
    for ax, xy, title in [(axes[0], before_xy, "A  分区径向初始场"), (axes[1], final_xy, "B  删镜与局部优化后")]:
        radius = np.hypot(xy[:, 0] - design.tower_x, xy[:, 1] - design.tower_y)
        scatter = ax.scatter(xy[:, 0], xy[:, 1], c=radius, s=3, cmap="viridis")
        ax.add_patch(plt.Circle((0, 0), 350, fill=False, color="#333333"))
        ax.add_patch(plt.Circle((design.tower_x, design.tower_y), 100, fill=False, linestyle="--", color="#c43c39"))
        for boundary in design.zone_boundaries:
            ax.add_patch(plt.Circle((design.tower_x, design.tower_y), boundary, fill=False, linestyle=":", color="#707b83"))
        ax.scatter([design.tower_x], [design.tower_y], marker="^", s=70, color="#c46a1a")
        ax.set_aspect("equal")
        ax.set_xlim(-370, 370)
        ax.set_ylim(-370, 370)
        ax.set_title(title)
        ax.set_xlabel("x / m")
        ax.set_ylabel("y / m")
        ax.grid(True, linewidth=0.4)
    fig.colorbar(scatter, ax=axes, label="到塔距离 / m", shrink=0.82)
    fig.savefig(output / "figures" / "fig01-radial-layout-before-after.png", dpi=190)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.8, 5.6), constrained_layout=True)
    power = [row["proxy_field_power_mw"] for row in proxy_rows]
    unit = [row["proxy_unit_area_power_kw_m2"] for row in proxy_rows]
    area = np.asarray([row["total_area_m2"] for row in proxy_rows]) / 1000.0
    mark = ax.scatter(power, unit, c=area, cmap="plasma", s=30, alpha=0.75)
    ax.axvline(60, color="#c43c39", linestyle="--")
    ax.set_xlabel("校准代理年平均功率 / MW")
    ax.set_ylabel("校准代理单位面积功率 / (kW/m2)")
    ax.set_title("三分区参数组合初筛")
    ax.grid(True)
    fig.colorbar(mark, ax=ax, label="总镜面面积 / 10^3 m2")
    fig.savefig(output / "figures" / "fig02-proxy-screen.png", dpi=190)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), constrained_layout=True)
    accepted = [row for row in prune_history if row["accepted"]]
    axes[0].plot([row["mirror_count"] for row in accepted], [row["estimated_full_power_mw"] for row in accepted], marker="o")
    axes[0].axhline(60.45, color="#c43c39", linestyle="--")
    axes[0].set_xlabel("镜面数量")
    axes[0].set_ylabel("估计完整年平均功率 / MW")
    axes[0].set_title("A  低贡献镜面筛除")
    axes[0].grid(True)
    labels = ["r03 六角", "r04 径向"]
    axes[1].bar(labels, [r03["unit_area_power_kw_m2"], final["unit_area_power_kw_m2"]], color=["#7d99af", "#3b8c6e"])
    axes[1].set_ylabel("单位面积年平均功率 / (kW/m2)")
    axes[1].set_title("B  正式复算结果比较")
    axes[1].grid(True, axis="y")
    fig.savefig(output / "figures" / "fig03-pruning-and-comparison.png", dpi=190)
    plt.close(fig)


def serializable_proxy_rows(rows: list[dict]) -> list[dict]:
    return [{key: value for key, value in row.items() if key not in ("design", "xy")} for row in rows]


def main() -> None:
    args = parse_args()
    for folder in ("results", "figures", "validation", "logs"):
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    logger = setup_logger(args.output)
    r03_annual = read_csv_row(args.r03_run / "results" / "annual_metrics.csv")
    r03_xy = np.genfromtxt(args.r03_run / "results" / "heliostat_positions.csv", delimiter=",", names=True, encoding="utf-8-sig")
    baseline_xy = np.column_stack([r03_xy["x_m"], r03_xy["y_m"]])
    baseline_design = Design(0.0, -60.0, 6.8, 6.35, 3.175, 100.0, -1.578, 0.0, 520.0, 0.0)
    baseline_proxy = proxy_metrics_from_xy(baseline_design, baseline_xy)
    calibration = r03_annual["unit_area_power_kw_m2"] / baseline_proxy["unit_area_power_kw_m2"]
    _, _, baseline_reduced_annual, _ = evaluate(
        RadialDesign(0.0, -60.0, 6.8, 6.35, 3.175, 0.0, (190, 285), (0.866, 0.9, 0.94), (1, 1.03, 1.07)),
        baseline_xy,
        args.screen_samples,
        args.seed,
        args.neighbor_radius,
        states=validation_states(),
    )
    logger.info("Proxy calibration factor %.6f", calibration)

    designs = candidate_designs()
    proxy_rows = proxy_screen(designs, calibration, logger)
    write_csv(args.output / "results" / "proxy_screen.csv", serializable_proxy_rows(proxy_rows))
    proxy_chosen = choose_proxy_rows(proxy_rows, args.proxy_keep)
    screen_rows = reduced_screen(
        proxy_chosen,
        baseline_reduced_annual["field_power_mw"],
        r03_annual["field_power_mw"],
        args,
        logger,
    )
    write_csv(args.output / "results" / "ray_screen.csv", serializable_proxy_rows(screen_rows))
    full_rows = full_verification(choose_screen_rows(screen_rows, args.screen_keep), args, logger)
    write_csv(
        args.output / "results" / "candidate_verification.csv",
        [
            {
                **{key: value for key, value in row.items() if key not in ("design", "xy", "full_annual", "mirror_metrics")},
                **{f"full_{key}": value for key, value in row["full_annual"].items()},
            }
            for row in full_rows
        ],
    )
    selected = select_verified(full_rows)
    snapshots, pruning_history, _ = iterative_pruning(selected, args, logger)
    write_csv(args.output / "results" / "pruning_history.csv", pruning_history)
    pruned_xy, _, pruned_annual, pruned_mirror = verify_snapshots(selected["design"], snapshots, args, logger)

    local_xy, move_count = local_coordinate_improvement(
        selected["design"], pruned_xy, pruned_mirror[:, 0], all_states(), maximum_mirrors=80
    )
    _, _, local_check_annual, _ = evaluate(
        selected["design"], local_xy, max(64, args.verify_samples), args.seed, args.neighbor_radius, states=all_states()
    )
    if local_check_annual["field_power_mw"] >= 60.20 and local_check_annual["unit_area_power_kw_m2"] > pruned_annual["unit_area_power_kw_m2"]:
        final_xy = local_xy
        local_accepted = True
    else:
        final_xy = pruned_xy
        local_accepted = False
    logger.info("Local moves proposed=%d accepted_as_field=%s", move_count, local_accepted)

    convergence = []
    final_rows = final_monthly = final_annual = final_mirror = None
    for samples in sorted(set([32, 64, args.final_samples])):
        rows, monthly, annual, mirror = evaluate(
            selected["design"],
            final_xy,
            samples,
            args.seed,
            args.neighbor_radius,
            states=all_states(),
            store=samples == args.final_samples,
            logger=logger,
        )
        convergence.append({"samples": samples, **annual})
        if samples == args.final_samples:
            final_rows, final_monthly, final_annual, final_mirror = rows, monthly, annual, mirror
    assert final_annual is not None and final_mirror is not None
    checks = geometry_checks(selected["design"], final_xy)
    checks.update(
        {
            "annual_power_constraint_satisfied": final_annual["field_power_mw"] >= 60.0,
            "annual_power_mw": final_annual["field_power_mw"],
            "unit_area_power_kw_m2": final_annual["unit_area_power_kw_m2"],
            "local_move_count": move_count,
            "local_field_accepted": local_accepted,
            "final_samples": args.final_samples,
        }
    )
    position_rows = [
        {"mirror_id": index, "x_m": point[0], "y_m": point[1], "z_m": selected["design"].center_z}
        for index, point in enumerate(final_xy, start=1)
    ]
    write_csv(args.output / "results" / "final_positions.csv", position_rows)
    write_csv(args.output / "results" / "ray_convergence.csv", convergence)
    write_csv(args.output / "results" / "monthly_metrics.csv", final_monthly)
    write_csv(args.output / "results" / "time_metrics.csv", final_rows)
    write_csv(
        args.output / "results" / "mirror_annual_metrics.csv",
        [
            {
                "mirror_id": index,
                "x_m": point[0],
                "y_m": point[1],
                "annual_optical_efficiency": metrics[0],
                "annual_cosine_efficiency": metrics[1],
                "annual_atmospheric_efficiency": metrics[2],
                "annual_shadow_blocking_efficiency": metrics[3],
                "annual_truncation_efficiency": metrics[4],
            }
            for index, (point, metrics) in enumerate(zip(final_xy, final_mirror), start=1)
        ],
    )
    final_result = {
        **design_fields(selected["design"]),
        "mirror_count": len(final_xy),
        "total_area_m2": selected["design"].area * len(final_xy),
        **final_annual,
        "local_move_count": move_count,
        "local_field_accepted": local_accepted,
    }
    write_csv(args.output / "results" / "annual_metrics.csv", [final_result])
    (args.output / "results" / "design.json").write_text(
        json.dumps({**asdict(selected["design"]), **final_result}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output / "validation" / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    plot_results(
        args.output,
        selected["design"],
        selected["xy"],
        final_xy,
        proxy_rows,
        pruning_history,
        r03_annual,
        final_annual,
    )
    code_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [HERE, HERE.with_name("variable_density_radial.py")]
    }
    (args.output / "validation" / "code_hashes.json").write_text(
        json.dumps(code_hashes, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("FINAL %s", json.dumps(final_result, ensure_ascii=False))


if __name__ == "__main__":
    main()
