#!/usr/bin/env python3
"""Robust outer-design search with optical contribution pruning for Q2."""

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
from scipy.stats import qmc


HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
sys.path.insert(0, str(ROUTES / "r01-common-size-field-optimization" / "code"))
sys.path.insert(0, str(ROUTES / "r05-shifted-hex-optical-pruning" / "code"))

from q2_model import (  # noqa: E402
    Design,
    aggregate_time_rows,
    all_states,
    evaluate_field,
    proxy_metrics_from_xy,
    validation_states,
)
from analyze_spatial_power import exact_per_mirror_power  # noqa: E402
from shifted_hex_model import (  # noqa: E402
    ShiftedHexDesign,
    generate_layout,
    geometry_checks,
)


BASELINE_RUN = (
    ROUTES
    / "r05-shifted-hex-optical-pruning"
    / "runs"
    / "run-20260817-1606-square-region-multifidelity"
)
GROUND_MARGIN_M = 0.10
SPACING_MARGIN_M = 0.05
SCREEN_POWER_FLOOR_MW = 59.4
SAFE_POWER_MW = 60.20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--designs", type=int, default=128)
    parser.add_argument("--screen-samples", type=int, default=16)
    parser.add_argument("--full-samples", type=int, default=64)
    parser.add_argument("--robust-samples", type=int, default=128)
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    return parser.parse_args()


def setup(output: Path) -> logging.Logger:
    for folder in ("results", "figures", "validation", "logs"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("robust-optical-density-search")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (
        logging.StreamHandler(),
        logging.FileHandler(output / "logs" / "run.log", encoding="utf-8"),
    ):
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ray_design(d: ShiftedHexDesign) -> Design:
    spacing = d.spacing
    return Design(
        d.tower_x,
        d.tower_y,
        d.width,
        d.height,
        d.center_z,
        100.0,
        math.sqrt(3.0) * spacing / 2.0 - (d.width + 5.0),
        spacing - (d.width + 5.0),
        520.0,
        d.rotation,
    )


def design_fields(d: ShiftedHexDesign) -> dict[str, float]:
    return {
        "tower_x_m": d.tower_x,
        "tower_y_m": d.tower_y,
        "width_m": d.width,
        "height_m": d.height,
        "center_z_m": d.center_z,
        "ground_clearance_m": d.center_z - d.height / 2.0,
        "spacing_clearance_m": d.clearance,
        "rotation_deg": math.degrees(d.rotation),
        "offset_u": d.offset_u,
        "offset_v": d.offset_v,
    }


def design_key(d: ShiftedHexDesign) -> tuple[float, ...]:
    return tuple(
        round(value, 6)
        for value in (
            d.tower_x,
            d.tower_y,
            d.width,
            d.height,
            d.center_z,
            d.rotation,
            d.offset_u,
            d.offset_v,
        )
    )


def candidate_designs(count: int, seed: int) -> list[ShiftedHexDesign]:
    anchors: list[ShiftedHexDesign] = []
    for tower_x, tower_y in (
        (0.0, -60.0),
        (-20.0, -60.0),
        (20.0, -60.0),
        (0.0, -40.0),
        (0.0, -80.0),
    ):
        for width, height in ((6.2, 6.2), (6.3, 6.3), (6.4, 6.2)):
            anchors.append(
                ShiftedHexDesign(
                    tower_x,
                    tower_y,
                    width,
                    height,
                    max(3.4, height / 2.0 + GROUND_MARGIN_M),
                    SPACING_MARGIN_M,
                    0.0,
                    0.0,
                    0.0,
                )
            )
    dimension = 8
    exponent = int(math.ceil(math.log2(max(1, count))))
    values = qmc.Sobol(d=dimension, scramble=True, seed=seed).random_base2(exponent)
    generated: list[ShiftedHexDesign] = []
    for row in values:
        width = 5.85 + 0.95 * row[2]
        height = max(2.0, width - 0.45 * row[3])
        lower_z = max(2.0, height / 2.0 + GROUND_MARGIN_M)
        center_z = lower_z + row[4] * (5.2 - lower_z)
        generated.append(
            ShiftedHexDesign(
                -45.0 + 90.0 * row[0],
                -95.0 + 70.0 * row[1],
                width,
                height,
                center_z,
                SPACING_MARGIN_M,
                row[5] * math.pi / 3.0,
                row[6],
                row[7],
            )
        )
    result: list[ShiftedHexDesign] = []
    seen = set()
    for design in anchors + generated:
        key = design_key(design)
        if key not in seen:
            result.append(design)
            seen.add(key)
        if len(result) >= count:
            break
    return result


def serial_row(row: dict) -> dict:
    return {
        key: value
        for key, value in row.items()
        if key not in {"design", "ray_design", "xy", "time_rows", "per_mirror_power_kw"}
    }


def select_unique(rows: list[dict], count: int, rankings: list[tuple[str, bool]]) -> list[dict]:
    selected: list[dict] = []
    seen = set()
    ranked_rows = [
        sorted(rows, key=lambda item: item[key], reverse=reverse)
        for key, reverse in rankings
    ]
    cursors = [0] * len(ranked_rows)
    while len(selected) < count:
        added = False
        for ranking_index, ranking in enumerate(ranked_rows):
            while cursors[ranking_index] < len(ranking):
                row = ranking[cursors[ranking_index]]
                cursors[ranking_index] += 1
                signature = (design_key(row["design"]), row.get("removed"))
                if signature in seen:
                    continue
                selected.append(row)
                seen.add(signature)
                added = True
                break
            if len(selected) >= count:
                return selected
        if not added:
            break
    return selected


def evaluate_rows(
    rows: list[dict],
    samples: int,
    seed: int,
    neighbor_radius: float,
    states,
    prefix: str,
    logger: logging.Logger,
    store_per_mirror: bool = False,
) -> list[dict]:
    output = []
    for index, row in enumerate(rows, start=1):
        time_rows, mirror = evaluate_field(
            row["ray_design"],
            row["xy"],
            samples,
            seed,
            neighbor_radius,
            states=states,
            store_per_mirror=store_per_mirror,
        )
        _, annual = aggregate_time_rows(time_rows, row["ray_design"].area * len(row["xy"]))
        item = {
            **row,
            **{f"{prefix}_{key}": value for key, value in annual.items()},
            "time_rows": time_rows,
        }
        if mirror is not None:
            item["mirror_optical_metrics"] = mirror
        output.append(item)
        logger.info(
            "%s %d/%d id=%s N=%d P=%.4f unit=%.6f",
            prefix,
            index,
            len(rows),
            row["design_id"],
            len(row["xy"]),
            annual["field_power_mw"],
            annual["unit_area_power_kw_m2"],
        )
    return output


def baseline_calibration(args: argparse.Namespace, logger: logging.Logger):
    raw = json.loads((BASELINE_RUN / "results" / "design.json").read_text(encoding="utf-8"))
    position_rows = read_csv(BASELINE_RUN / "results" / "final_positions.csv")
    xy = np.asarray([[float(row["x_m"]), float(row["y_m"])] for row in position_rows])
    shifted = ShiftedHexDesign(
        float(raw["tower_x"]),
        float(raw["tower_y"]),
        float(raw["width"]),
        float(raw["height"]),
        float(raw["center_z"]),
        float(raw["clearance"]),
        float(raw["rotation"]),
        float(raw["offset_u"]),
        float(raw["offset_v"]),
    )
    ray = ray_design(shifted)
    proxy = proxy_metrics_from_xy(ray, xy)
    proxy_factor = float(raw["unit_area_power_kw_m2"]) / proxy["unit_area_power_kw_m2"]
    validation_rows, _ = evaluate_field(
        ray,
        xy,
        args.screen_samples,
        args.seed,
        args.neighbor_radius,
        states=validation_states(),
    )
    _, validation_annual = aggregate_time_rows(validation_rows, ray.area * len(xy))
    validation_scale = float(raw["field_power_mw"]) / validation_annual["field_power_mw"]
    logger.info(
        "Baseline calibration proxy_factor=%.6f validation_scale=%.6f",
        proxy_factor,
        validation_scale,
    )
    return proxy_factor, validation_scale, raw


def prune_variants(
    base: dict,
    mirror_power_kw: np.ndarray,
) -> list[dict]:
    order = np.argsort(mirror_power_kw)
    base_power = float(base["full64_field_power_mw"])
    rows = []
    for removed in range(0, 81, 5):
        keep = order[removed:]
        xy = base["xy"][keep]
        estimated_power = base_power - float(np.sum(mirror_power_kw[order[:removed]])) / 1000.0
        estimated_unit = estimated_power * 1000.0 / (base["ray_design"].area * len(xy))
        rows.append(
            {
                **base,
                "design_id": f"{base['design_id']}-prune-{removed}",
                "xy": xy,
                "removed": removed,
                "estimated_pruned_power_mw": estimated_power,
                "estimated_pruned_unit_area_power_kw_m2": estimated_unit,
            }
        )
    return rows


def robust_evaluate(
    rows: list[dict], args: argparse.Namespace, logger: logging.Logger
) -> tuple[list[dict], list[dict]]:
    summaries = []
    seed_rows = []
    for row in rows:
        powers = []
        units = []
        for seed in (args.seed, args.seed + 1, args.seed + 2):
            time_rows, _ = evaluate_field(
                row["ray_design"],
                row["xy"],
                args.robust_samples,
                seed,
                args.neighbor_radius,
                states=all_states(),
            )
            _, annual = aggregate_time_rows(
                time_rows, row["ray_design"].area * len(row["xy"])
            )
            powers.append(annual["field_power_mw"])
            units.append(annual["unit_area_power_kw_m2"])
            seed_rows.append(
                {
                    "design_id": row["design_id"],
                    "seed": seed,
                    "samples": args.robust_samples,
                    "field_power_mw": annual["field_power_mw"],
                    "unit_area_power_kw_m2": annual["unit_area_power_kw_m2"],
                }
            )
        mean_power = float(np.mean(powers))
        std_power = float(np.std(powers, ddof=1))
        summary = {
            **row,
            "robust_mean_power_mw": mean_power,
            "robust_std_power_mw": std_power,
            "robust_lcb_power_mw": mean_power - 2.0 * std_power,
            "robust_mean_unit_area_power_kw_m2": float(np.mean(units)),
            "robust_min_power_mw": float(np.min(powers)),
            "robust_max_power_mw": float(np.max(powers)),
        }
        summaries.append(summary)
        logger.info(
            "ROBUST id=%s mean=%.4f std=%.4f lcb=%.4f unit=%.6f",
            row["design_id"],
            mean_power,
            std_power,
            summary["robust_lcb_power_mw"],
            summary["robust_mean_unit_area_power_kw_m2"],
        )
    return summaries, seed_rows


def plot_results(output: Path, proxy_rows: list[dict], full_rows: list[dict], robust_rows: list[dict], final: dict) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    scatter = ax.scatter(
        [row["proxy_field_power_mw"] for row in proxy_rows],
        [row["proxy_unit_area_power_kw_m2"] for row in proxy_rows],
        c=[row["center_z_m"] for row in proxy_rows],
        cmap="viridis",
        s=22,
        alpha=0.75,
    )
    ax.axvline(60.0, color="#b42318", linestyle="--", linewidth=1.2)
    ax.set(xlabel="Calibrated proxy power / MW", ylabel="Proxy unit-area power / (kW/m2)", title="Global design screening")
    ax.grid(True, alpha=0.35)
    fig.colorbar(scatter, ax=ax, label="Installation height / m")
    fig.savefig(output / "figures" / "fig01-global-screen.png", dpi=210)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    ax.scatter(
        [row["full64_field_power_mw"] for row in full_rows],
        [row["full64_unit_area_power_kw_m2"] for row in full_rows],
        s=60,
        color="#2a7f62",
    )
    ax.axvline(60.0, color="#b42318", linestyle="--", linewidth=1.2)
    ax.set(xlabel="64-ray annual power / MW", ylabel="Unit-area power / (kW/m2)", title="Full-year candidate verification")
    ax.grid(True, alpha=0.35)
    fig.savefig(output / "figures" / "fig02-full64-candidates.png", dpi=210)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.2), constrained_layout=True)
    xy = final["xy"]
    axes[0].scatter(xy[:, 0], xy[:, 1], s=2.0, color="#2a7f62")
    axes[0].add_patch(plt.Circle((0, 0), 350, fill=False, color="#222222"))
    d = final["design"]
    axes[0].add_patch(plt.Circle((d.tower_x, d.tower_y), 100, fill=False, color="#b42318", linestyle="--"))
    axes[0].scatter([d.tower_x], [d.tower_y], marker="^", s=70, color="#cc6b1a")
    axes[0].set_aspect("equal")
    axes[0].set(xlabel="x / m", ylabel="y / m", title="Selected variable-density field")
    axes[0].grid(True, alpha=0.3)
    labels = [row["design_id"].split("-prune-")[-1] for row in robust_rows]
    axes[1].errorbar(
        labels,
        [row["robust_mean_power_mw"] for row in robust_rows],
        yerr=[2.0 * row["robust_std_power_mw"] for row in robust_rows],
        fmt="o",
        color="#2a7f62",
        capsize=4,
    )
    axes[1].axhline(60.0, color="#b42318", linestyle="--")
    axes[1].set(xlabel="Removed mirrors", ylabel="Robust annual power / MW", title="Mean +/- 2 sample SD")
    axes[1].grid(True, alpha=0.3)
    fig.savefig(output / "figures" / "fig03-final-field-and-robustness.png", dpi=210)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    logger = setup(args.output)
    proxy_factor, validation_scale, baseline = baseline_calibration(args, logger)

    proxy_rows = []
    for index, shifted in enumerate(candidate_designs(args.designs, args.seed), start=1):
        xy = generate_layout(shifted)
        checks = geometry_checks(shifted, xy)
        ray = ray_design(shifted)
        proxy = proxy_metrics_from_xy(ray, xy, calibration_factor=proxy_factor)
        proxy_rows.append(
            {
                "design_id": f"d{index:03d}",
                **design_fields(shifted),
                **checks,
                **{f"proxy_{key}": value for key, value in proxy.items()},
                "design": shifted,
                "ray_design": ray,
                "xy": xy,
            }
        )
    write_csv(args.output / "results" / "proxy_candidates.csv", [serial_row(row) for row in proxy_rows])
    logger.info("Proxy screening complete designs=%d", len(proxy_rows))

    proxy_selected = select_unique(
        proxy_rows,
        24,
        [("proxy_field_power_mw", True), ("proxy_unit_area_power_kw_m2", True)],
    )
    screened = evaluate_rows(
        proxy_selected,
        args.screen_samples,
        args.seed,
        args.neighbor_radius,
        validation_states(),
        "screen16",
        logger,
    )
    for row in screened:
        row["estimated_full_power_mw"] = row["screen16_field_power_mw"] * validation_scale
        row["estimated_full_unit_area_power_kw_m2"] = (
            row["estimated_full_power_mw"] * 1000.0 / row["screen16_total_area_m2"]
        )
    write_csv(args.output / "results" / "screen16_candidates.csv", [serial_row(row) for row in screened])

    screen_pool = [row for row in screened if row["estimated_full_power_mw"] >= SCREEN_POWER_FLOOR_MW]
    full32_input = select_unique(
        screen_pool or screened,
        10,
        [("estimated_full_unit_area_power_kw_m2", True), ("estimated_full_power_mw", True)],
    )
    full32 = evaluate_rows(
        full32_input,
        32,
        args.seed,
        args.neighbor_radius,
        all_states(),
        "full32",
        logger,
    )
    write_csv(args.output / "results" / "full32_candidates.csv", [serial_row(row) for row in full32])

    full32_pool = [row for row in full32 if row["full32_field_power_mw"] >= 59.7]
    full64_input = select_unique(
        full32_pool or full32,
        5,
        [("full32_unit_area_power_kw_m2", True), ("full32_field_power_mw", True)],
    )
    full64 = evaluate_rows(
        full64_input,
        args.full_samples,
        args.seed,
        args.neighbor_radius,
        all_states(),
        "full64",
        logger,
    )
    write_csv(args.output / "results" / "full64_candidates.csv", [serial_row(row) for row in full64])

    safe = [row for row in full64 if row["full64_field_power_mw"] >= SAFE_POWER_MW]
    base = max(
        safe or full64,
        key=lambda row: (
            row["full64_unit_area_power_kw_m2"] if safe else row["full64_field_power_mw"]
        ),
    )
    logger.info("Selected pruning base %s", base["design_id"])
    mirror_power_kw = exact_per_mirror_power(
        base["ray_design"],
        base["xy"],
        args.full_samples,
        args.seed,
        args.neighbor_radius,
        logger,
    )
    variants = prune_variants(base, mirror_power_kw)
    promising = [row for row in variants if row["estimated_pruned_power_mw"] >= 59.85]
    prune_input = select_unique(
        promising or variants,
        5,
        [("estimated_pruned_unit_area_power_kw_m2", True), ("estimated_pruned_power_mw", True)],
    )
    prune64 = evaluate_rows(
        prune_input,
        args.full_samples,
        args.seed,
        args.neighbor_radius,
        all_states(),
        "prune64",
        logger,
    )
    write_csv(args.output / "results" / "prune64_candidates.csv", [serial_row(row) for row in prune64])

    robust_input = sorted(
        [row for row in prune64 if row["prune64_field_power_mw"] >= 59.90] or prune64,
        key=lambda row: row["prune64_unit_area_power_kw_m2"],
        reverse=True,
    )[:3]
    robust_rows, robust_seed_rows = robust_evaluate(robust_input, args, logger)
    write_csv(args.output / "results" / "robust_candidates.csv", [serial_row(row) for row in robust_rows])
    write_csv(args.output / "results" / "robust_seed_metrics.csv", robust_seed_rows)

    robust_feasible = [row for row in robust_rows if row["robust_lcb_power_mw"] >= 60.0]
    final = max(
        robust_feasible or robust_rows,
        key=lambda row: (
            row["robust_mean_unit_area_power_kw_m2"]
            if robust_feasible
            else row["robust_lcb_power_mw"]
        ),
    )
    final_time, _ = evaluate_field(
        final["ray_design"],
        final["xy"],
        args.robust_samples,
        args.seed,
        args.neighbor_radius,
        states=all_states(),
    )
    monthly, annual = aggregate_time_rows(
        final_time, final["ray_design"].area * len(final["xy"])
    )
    final_power_kw = exact_per_mirror_power(
        final["ray_design"],
        final["xy"],
        args.robust_samples,
        args.seed,
        args.neighbor_radius,
        logger,
    )

    write_csv(args.output / "results" / "time_metrics.csv", final_time)
    write_csv(args.output / "results" / "monthly_metrics.csv", monthly)
    write_csv(args.output / "results" / "annual_metrics.csv", [{**annual, "samples": args.robust_samples, "seed": args.seed}])
    write_csv(
        args.output / "results" / "final_positions.csv",
        [
            {"heliostat_id": index, "x_m": point[0], "y_m": point[1]}
            for index, point in enumerate(final["xy"], start=1)
        ],
    )
    write_csv(
        args.output / "results" / "mirror_annual_power.csv",
        [
            {
                "heliostat_id": index,
                "x_m": point[0],
                "y_m": point[1],
                "annual_avg_power_kw": power,
                "annual_unit_area_power_kw_m2": power / final["ray_design"].area,
            }
            for index, (point, power) in enumerate(zip(final["xy"], final_power_kw), start=1)
        ],
    )

    final_design = {
        **asdict(final["design"]),
        **design_fields(final["design"]),
        "mirror_count": len(final["xy"]),
        "removed": final.get("removed", 0),
        **annual,
        "robust_mean_power_mw": final["robust_mean_power_mw"],
        "robust_std_power_mw": final["robust_std_power_mw"],
        "robust_lcb_power_mw": final["robust_lcb_power_mw"],
        "robust_mean_unit_area_power_kw_m2": final["robust_mean_unit_area_power_kw_m2"],
    }
    write_json(args.output / "results" / "design.json", final_design)

    checks = {
        **geometry_checks(final["design"], final["xy"]),
        "tower_inside_site": bool(final["design"].tower_x**2 + final["design"].tower_y**2 <= 350.0**2),
        "mirror_dimensions_satisfied": bool(2.0 <= final["design"].height <= final["design"].width <= 8.0),
        "installation_height_range_satisfied": bool(2.0 <= final["design"].center_z <= 6.0),
        "ground_clearance_m": final["design"].center_z - final["design"].height / 2.0,
        "ground_clearance_satisfied": bool(final["design"].center_z - final["design"].height / 2.0 >= GROUND_MARGIN_M - 1.0e-9),
        "single_seed_power_constraint_satisfied": bool(annual["field_power_mw"] >= 60.0),
        "robust_power_constraint_satisfied": bool(final["robust_lcb_power_mw"] >= 60.0),
        "per_mirror_power_sum_mw": float(np.sum(final_power_kw) / 1000.0),
        "per_mirror_power_conservation_error_mw": float(np.sum(final_power_kw) / 1000.0 - annual["field_power_mw"]),
        "q1_replay_reference_power_mw": 35.294197282479594,
        "q1_replay_reference_unit_area_power_kw_m2": 0.561830583929952,
        "baseline_r05_power_mw": float(baseline["field_power_mw"]),
        "baseline_r05_unit_area_power_kw_m2": float(baseline["unit_area_power_kw_m2"]),
    }
    write_json(args.output / "validation" / "checks.json", checks)
    write_json(
        args.output / "validation" / "code_hashes.json",
        {
            "run_robust_density_search.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "q2_model.py": hashlib.sha256((ROUTES / "r01-common-size-field-optimization" / "code" / "q2_model.py").read_bytes()).hexdigest(),
            "shifted_hex_model.py": hashlib.sha256((ROUTES / "r05-shifted-hex-optical-pruning" / "code" / "shifted_hex_model.py").read_bytes()).hexdigest(),
        },
    )
    plot_results(args.output, proxy_rows, full64, robust_rows, final)
    logger.info("FINAL %s", json.dumps(final_design, ensure_ascii=False))


if __name__ == "__main__":
    main()
