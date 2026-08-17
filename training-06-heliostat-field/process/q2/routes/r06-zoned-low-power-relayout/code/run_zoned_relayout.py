#!/usr/bin/env python3
"""Generate and evaluate local triangular-lattice replacements in low-power zones."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree


HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
sys.path.insert(0, str(ROUTES / "r01-common-size-field-optimization" / "code"))
sys.path.insert(0, str(ROUTES / "r05-shifted-hex-optical-pruning" / "code"))

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field, validation_states
from shifted_hex_model import geometry_checks, ShiftedHexDesign


@dataclass(frozen=True)
class RelayoutParameters:
    margin_m: float
    rotation_deg: float
    phase_1: float
    phase_2: float

    @property
    def candidate_id(self) -> str:
        return (
            f"m{self.margin_m:.2f}-r{self.rotation_deg:.1f}"
            f"-p{self.phase_1:.2f}-{self.phase_2:.2f}"
        )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-run", required=True, type=Path)
    parser.add_argument("--spatial-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("geometry", "full"), default="geometry")
    parser.add_argument(
        "--strategy",
        choices=("global", "zoned", "zoned-absolute"),
        default="zoned-absolute",
    )
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    return parser.parse_args()


def logger_for(output: Path) -> logging.Logger:
    for folder in ("results", "figures", "validation", "logs"):
        (output / folder).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("zoned-low-power-relayout")
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
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_inputs(baseline_run: Path, spatial_run: Path):
    raw_design = json.loads((baseline_run / "results" / "design.json").read_text(encoding="utf-8"))
    position_rows = read_csv(baseline_run / "results" / "final_positions.csv")
    xy = np.asarray([[float(row["x_m"]), float(row["y_m"])] for row in position_rows])
    low_zone_rows = read_csv(spatial_run / "results" / "low_power_zones.csv")
    low_zones = {row["zone_id"] for row in low_zone_rows}
    mirror_power_rows = read_csv(spatial_run / "results" / "mirror_power.csv")
    mirror_power_kw = np.asarray([float(row["annual_avg_power_kw"]) for row in mirror_power_rows])
    return raw_design, xy, low_zones, mirror_power_kw


def design_objects(raw: dict):
    width = float(raw["width"])
    height = float(raw["height"])
    clearance = float(raw["clearance"])
    spacing = width + 5.0 + clearance
    shifted = ShiftedHexDesign(
        float(raw["tower_x"]),
        float(raw["tower_y"]),
        width,
        height,
        float(raw["center_z"]),
        clearance,
        float(raw["rotation"]),
        float(raw["offset_u"]),
        float(raw["offset_v"]),
    )
    ray = Design(
        shifted.tower_x,
        shifted.tower_y,
        width,
        height,
        shifted.center_z,
        100.0,
        math.sqrt(3.0) * spacing / 2.0 - (width + 5.0),
        spacing - (width + 5.0),
        520.0,
        shifted.rotation,
    )
    return shifted, ray


def point_zone_indices(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    radius = np.hypot(points[:, 0], points[:, 1])
    angle = (np.degrees(np.arctan2(points[:, 1], points[:, 0])) + 360.0) % 360.0
    ring = np.clip((radius / 70.0).astype(int), 0, 4)
    sector = np.clip((angle / 30.0).astype(int), 0, 11)
    zone_ids = np.asarray([f"R{r + 1}-S{s + 1:02d}" for r, s in zip(ring, sector)])
    return radius, angle, ring, sector, zone_ids


def core_mask(points: np.ndarray, low_zones: set[str], margin_m: float) -> np.ndarray:
    radius, angle, ring, sector, zone_ids = point_zone_indices(points)
    selected = np.isin(zone_ids, list(low_zones))
    radial_inner = ring * 70.0
    radial_outer = (ring + 1) * 70.0
    radial_clearance = np.minimum(radius - radial_inner, radial_outer - radius)
    angle_start = sector * 30.0
    delta_start = np.radians(angle - angle_start)
    delta_end = np.radians(angle_start + 30.0 - angle)
    angular_clearance = radius * np.minimum(np.sin(delta_start), np.sin(delta_end))
    return selected & (radial_clearance >= margin_m) & (angular_clearance >= margin_m)


def zone_center_angle(zone_id: str) -> float:
    sector = int(zone_id.split("-S")[1]) - 1
    return (sector + 0.5) * 30.0


def triangular_lattice(design: ShiftedHexDesign, params: RelayoutParameters) -> np.ndarray:
    spacing = design.spacing
    angle = math.radians(params.rotation_deg)
    b1 = spacing * np.asarray([math.cos(angle), math.sin(angle)])
    b2 = spacing * np.asarray([math.cos(angle + math.pi / 3.0), math.sin(angle + math.pi / 3.0)])
    origin = np.asarray([design.tower_x, design.tower_y]) + params.phase_1 * b1 + params.phase_2 * b2
    limit = 55
    indices = np.arange(-limit, limit + 1)
    ii, jj = np.meshgrid(indices, indices, indexing="ij")
    return origin + ii.reshape(-1, 1) * b1 + jj.reshape(-1, 1) * b2


def replace_core(
    baseline_xy: np.ndarray,
    design: ShiftedHexDesign,
    low_zones: set[str],
    params: RelayoutParameters,
) -> tuple[np.ndarray, dict]:
    removed_mask = core_mask(baseline_xy, low_zones, params.margin_m)
    fixed = baseline_xy[~removed_mask]
    lattice = triangular_lattice(design, params)
    candidate_mask = core_mask(lattice, low_zones, params.margin_m)
    candidates = lattice[candidate_mask]
    site_ok = np.hypot(candidates[:, 0], candidates[:, 1]) <= 350.0 + 1.0e-9
    tower_ok = (
        np.hypot(candidates[:, 0] - design.tower_x, candidates[:, 1] - design.tower_y)
        >= 100.0 - 1.0e-9
    )
    candidates = candidates[site_ok & tower_ok]
    if len(candidates):
        distance_to_fixed = cKDTree(fixed).query(candidates, k=1)[0]
        candidates = candidates[distance_to_fixed >= design.spacing - 1.0e-7]
    combined = np.vstack([fixed, candidates])
    combined = combined[np.lexsort((combined[:, 0], combined[:, 1]))]
    checks = geometry_checks(design, combined)
    metadata = {
        "candidate_id": params.candidate_id,
        "margin_m": params.margin_m,
        "rotation_deg": params.rotation_deg,
        "phase_1": params.phase_1,
        "phase_2": params.phase_2,
        "baseline_core_count": int(np.sum(removed_mask)),
        "replacement_count": int(len(candidates)),
        "mirror_count": int(len(combined)),
        "mirror_delta": int(len(combined) - len(baseline_xy)),
        **checks,
    }
    return combined, metadata


def replace_cores_independently(
    baseline_xy: np.ndarray,
    design: ShiftedHexDesign,
    low_zones: set[str],
    margin_m: float,
    orientation_offset_deg: float,
    orientation_mode: str = "radial",
) -> tuple[np.ndarray, dict]:
    removed_mask = core_mask(baseline_xy, low_zones, margin_m)
    fixed = baseline_xy[~removed_mask]
    replacement_parts = []
    choices = {}
    phases = np.arange(0.0, 1.0, 0.125)
    fixed_tree = cKDTree(fixed)
    for zone_id in sorted(low_zones):
        best = None
        if orientation_mode == "radial":
            rotation_deg = (zone_center_angle(zone_id) + orientation_offset_deg) % 60.0
        else:
            rotation_deg = orientation_offset_deg % 60.0
        for phase_1 in phases:
            for phase_2 in phases:
                params = RelayoutParameters(margin_m, rotation_deg, float(phase_1), float(phase_2))
                lattice = triangular_lattice(design, params)
                candidates = lattice[core_mask(lattice, {zone_id}, margin_m)]
                site_ok = np.hypot(candidates[:, 0], candidates[:, 1]) <= 350.0 + 1.0e-9
                tower_ok = (
                    np.hypot(candidates[:, 0] - design.tower_x, candidates[:, 1] - design.tower_y)
                    >= 100.0 - 1.0e-9
                )
                candidates = candidates[site_ok & tower_ok]
                if len(candidates):
                    candidates = candidates[
                        fixed_tree.query(candidates, k=1)[0] >= design.spacing - 1.0e-7
                    ]
                score = (len(candidates), -float(phase_1 + phase_2))
                if best is None or score > best[0]:
                    best = (score, candidates, float(phase_1), float(phase_2))
        replacement_parts.append(best[1])
        choices[zone_id] = {
            "rotation_deg": rotation_deg,
            "phase_1": best[2],
            "phase_2": best[3],
            "replacement_count": len(best[1]),
            "baseline_core_count": int(np.sum(core_mask(baseline_xy, {zone_id}, margin_m))),
        }
    replacements = np.vstack(replacement_parts) if replacement_parts else np.empty((0, 2))
    combined = np.vstack([fixed, replacements])
    combined = combined[np.lexsort((combined[:, 0], combined[:, 1]))]
    checks = geometry_checks(design, combined)
    metadata = {
        "candidate_id": f"{orientation_mode}-m{margin_m:.2f}-o{orientation_offset_deg:.1f}",
        "margin_m": margin_m,
        "rotation_deg": orientation_offset_deg,
        "phase_1": "per-zone",
        "phase_2": "per-zone",
        "baseline_core_count": int(np.sum(removed_mask)),
        "replacement_count": int(len(replacements)),
        "mirror_count": int(len(combined)),
        "mirror_delta": int(len(combined) - len(baseline_xy)),
        "zone_choices": json.dumps(choices, ensure_ascii=False, sort_keys=True),
        **checks,
    }
    return combined, metadata


def parameter_grid() -> list[RelayoutParameters]:
    margins = (11.35, 17.025, 22.70)
    rotations = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0)
    phases = (0.0, 0.25, 0.5, 0.75)
    return [
        RelayoutParameters(margin, rotation, phase_1, phase_2)
        for margin in margins
        for rotation in rotations
        for phase_1 in phases
        for phase_2 in phases
    ]


def zoned_parameter_grid() -> list[tuple[float, float]]:
    return [
        (margin, offset)
        for margin in (11.35, 17.025, 22.70)
        for offset in np.arange(0.0, 60.0, 5.0)
    ]


def absolute_parameter_grid() -> list[tuple[float, float]]:
    return [
        (margin, rotation)
        for margin in (11.35, 17.025, 22.70)
        for rotation in (0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0)
    ]


def geometry_candidates(baseline_xy, design, low_zones, logger, strategy="zoned"):
    candidates = []
    seen = set()
    if strategy == "global":
        grid = parameter_grid()
    elif strategy == "zoned":
        grid = zoned_parameter_grid()
    else:
        grid = absolute_parameter_grid()
    for index, specification in enumerate(grid, start=1):
        if strategy == "global":
            params = specification
            xy, metadata = replace_core(baseline_xy, design, low_zones, params)
        else:
            margin, offset = specification
            params = RelayoutParameters(margin, offset, 0.0, 0.0)
            xy, metadata = replace_cores_independently(
                baseline_xy,
                design,
                low_zones,
                margin,
                offset,
                "radial" if strategy == "zoned" else "absolute",
            )
        digest = hashlib.sha256(np.round(xy, 8).tobytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        candidates.append({"params": params, "xy": xy, "metadata": metadata, "hash": digest})
        if index % 6 == 0:
            logger.info("Geometry candidate %d/%d", index, len(grid))
    return candidates


def evaluate_layout(ray_design, xy, samples, seed, radius, states=None, store=False, logger=None):
    rows, mirror = evaluate_field(
        ray_design,
        xy,
        samples,
        seed,
        radius,
        states=states,
        store_per_mirror=store,
        logger=logger,
    )
    monthly, annual = aggregate_time_rows(rows, ray_design.area * len(xy))
    return rows, monthly, annual, mirror


def select_geometry(candidates, count=16):
    nonbaseline = candidates
    grouped = {}
    for item in nonbaseline:
        key = (item["params"].margin_m, item["params"].rotation_deg)
        grouped.setdefault(key, []).append(item)
    representatives = []
    for values in grouped.values():
        representatives.extend(sorted(values, key=lambda item: item["metadata"]["mirror_count"], reverse=True)[:2])
    return sorted(representatives, key=lambda item: item["metadata"]["mirror_count"], reverse=True)[:count]


def pruning_controls(baseline_xy, shifted_design, mirror_power_kw):
    order = np.argsort(mirror_power_kw)
    controls = []
    for removed in (0, 5, 10, 15, 20, 25, 30):
        xy = np.delete(baseline_xy, order[:removed], axis=0) if removed else np.array(baseline_xy, copy=True)
        checks = geometry_checks(shifted_design, xy)
        metadata = {
            "candidate_id": f"prune-{removed}",
            "margin_m": 0.0,
            "rotation_deg": 0.0,
            "phase_1": "baseline",
            "phase_2": "baseline",
            "baseline_core_count": removed,
            "replacement_count": 0,
            "mirror_count": len(xy),
            "mirror_delta": -removed,
            **checks,
        }
        controls.append(
            {
                "params": RelayoutParameters(0.0, 0.0, 0.0, 0.0),
                "xy": xy,
                "metadata": metadata,
                "hash": hashlib.sha256(np.round(xy, 8).tobytes()).hexdigest(),
            }
        )
    return controls


def serial_geometry(candidates):
    keys = (
        "candidate_id",
        "margin_m",
        "rotation_deg",
        "phase_1",
        "phase_2",
        "baseline_core_count",
        "replacement_count",
        "mirror_count",
        "mirror_delta",
        "minimum_center_distance_m",
        "maximum_site_radius_m",
        "minimum_tower_distance_m",
        "spacing_constraint_satisfied",
        "site_constraint_satisfied",
        "tower_exclusion_satisfied",
    )
    return [{key: item["metadata"][key] for key in keys} for item in candidates]


def make_geometry_plot(output: Path, rows: list[dict]) -> None:
    plt.rcParams.update({"font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"], "axes.unicode_minus": False})
    fig, ax = plt.subplots(figsize=(8.4, 5.5), constrained_layout=True)
    scatter = ax.scatter(
        [row["rotation_deg"] for row in rows],
        [row["mirror_count"] for row in rows],
        c=[row["margin_m"] for row in rows],
        cmap="viridis",
        s=24,
        alpha=0.75,
    )
    ax.axhline(3168, color="#b42318", linestyle="--", linewidth=1.1, label="r05 镜数")
    ax.set_xlabel("局部点阵旋转角 / °")
    ax.set_ylabel("重排后镜数")
    ax.set_title("低功率区局部重排几何预筛")
    ax.grid(True, linewidth=0.5, alpha=0.5)
    ax.legend()
    colorbar = fig.colorbar(scatter, ax=ax)
    colorbar.set_label("过渡带宽度 / m")
    fig.savefig(output / "figures" / "fig01-geometry-candidate-counts.png", dpi=210)
    plt.close(fig)


def geometry_mode(args, baseline_xy, shifted_design, low_zones, logger):
    candidates = geometry_candidates(
        baseline_xy, shifted_design, low_zones, logger, args.strategy
    )
    rows = serial_geometry(candidates)
    write_csv(args.output / "results" / "geometry_candidates.csv", rows)
    selected = select_geometry(candidates)
    write_csv(args.output / "results" / "selected_for_ray_screen.csv", serial_geometry(selected))
    make_geometry_plot(args.output, rows)
    counts = np.asarray([row["mirror_count"] for row in rows])
    summary = {
        "strategy": args.strategy,
        "parameter_combinations": (
            len(parameter_grid())
            if args.strategy == "global"
            else len(zoned_parameter_grid())
            if args.strategy == "zoned"
            else len(absolute_parameter_grid())
        ),
        "unique_candidates": len(candidates),
        "selected_for_ray_screen": len(selected),
        "baseline_mirror_count": len(baseline_xy),
        "maximum_candidate_mirror_count": int(np.max(counts)),
        "median_candidate_mirror_count": float(np.median(counts)),
        "minimum_candidate_mirror_count": int(np.min(counts)),
        "candidates_with_at_least_3150_mirrors": int(np.sum(counts >= 3150)),
        "all_geometry_constraints_passed": bool(
            all(
                row["spacing_constraint_satisfied"]
                and row["site_constraint_satisfied"]
                and row["tower_exclusion_satisfied"]
                for row in rows
            )
        ),
    }
    (args.output / "validation" / "checks.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("GEOMETRY %s", json.dumps(summary, ensure_ascii=False))


def full_mode(
    args,
    raw_design,
    baseline_xy,
    shifted_design,
    ray_design,
    low_zones,
    mirror_power_kw,
    logger,
):
    candidates = geometry_candidates(
        baseline_xy, shifted_design, low_zones, logger, args.strategy
    )
    candidates.extend(pruning_controls(baseline_xy, shifted_design, mirror_power_kw))
    selected = []
    seen = set()
    for item in candidates:
        if item["hash"] not in seen:
            selected.append(item)
            seen.add(item["hash"])
    baseline_screen = evaluate_layout(
        ray_design, baseline_xy, 16, args.seed, args.neighbor_radius, validation_states()
    )[2]
    screen_rows = []
    evaluated = []
    for index, item in enumerate(selected, start=1):
        annual = evaluate_layout(
            ray_design, item["xy"], 16, args.seed, args.neighbor_radius, validation_states()
        )[2]
        estimate = float(raw_design["field_power_mw"]) + annual["field_power_mw"] - baseline_screen["field_power_mw"]
        estimated_unit = estimate * 1000.0 / (ray_design.area * len(item["xy"]))
        row = {
            **item["metadata"],
            **{f"screen_{key}": value for key, value in annual.items()},
            "estimated_full_power_mw": estimate,
            "estimated_full_unit_area_power_kw_m2": estimated_unit,
        }
        screen_rows.append(row)
        evaluated.append(
            {
                **item,
                "screen": annual,
                "estimated_full_power_mw": estimate,
                "estimated_full_unit_area_power_kw_m2": estimated_unit,
            }
        )
        logger.info(
            "Screen16 %d/%d %s N=%d est=%.3f unit=%.4f",
            index,
            len(selected),
            item["metadata"]["candidate_id"],
            len(item["xy"]),
            estimate,
            estimated_unit,
        )
    write_csv(args.output / "results" / "screen16_candidates.csv", screen_rows)
    rough_feasible = [item for item in evaluated if item["estimated_full_power_mw"] >= 59.70]
    ranked_unit = sorted(
        rough_feasible or evaluated,
        key=lambda item: item["estimated_full_unit_area_power_kw_m2"],
        reverse=True,
    )[:8]
    ranked_power = sorted(evaluated, key=lambda item: item["estimated_full_power_mw"], reverse=True)[:2]
    top = []
    seen = set()
    for item in ranked_unit + ranked_power:
        if item["hash"] not in seen:
            top.append(item)
            seen.add(item["hash"])
    full64 = []
    for index, item in enumerate(top, start=1):
        annual = evaluate_layout(ray_design, item["xy"], 64, args.seed, args.neighbor_radius, logger=logger)[2]
        full64.append({**item, "annual64": annual})
        logger.info("Full64 %d/%d %s P=%.3f unit=%.4f", index, len(top), item["metadata"]["candidate_id"], annual["field_power_mw"], annual["unit_area_power_kw_m2"])
    write_csv(
        args.output / "results" / "full64_candidates.csv",
        [{**item["metadata"], **{f"annual64_{key}": value for key, value in item["annual64"].items()}} for item in full64],
    )
    viable64 = [item for item in full64 if item["annual64"]["field_power_mw"] >= 59.70]
    top128 = sorted(viable64 or full64, key=lambda item: item["annual64"]["unit_area_power_kw_m2"], reverse=True)[:4]
    refined = []
    for index, item in enumerate(top128, start=1):
        annual = evaluate_layout(ray_design, item["xy"], 128, args.seed, args.neighbor_radius, logger=logger)[2]
        refined.append({**item, "annual128": annual})
        logger.info("Full128 %d/%d %s P=%.3f unit=%.4f", index, len(top128), item["metadata"]["candidate_id"], annual["field_power_mw"], annual["unit_area_power_kw_m2"])
    write_csv(
        args.output / "results" / "full128_candidates.csv",
        [{**item["metadata"], **{f"annual128_{key}": value for key, value in item["annual128"].items()}} for item in refined],
    )
    viable128 = [item for item in refined if item["annual128"]["field_power_mw"] >= 59.90]
    final_items = sorted(
        viable128 or refined,
        key=lambda item: item["annual128"]["unit_area_power_kw_m2"],
        reverse=True,
    )[:3]
    baseline_control = next(item for item in candidates if item["metadata"]["candidate_id"] == "prune-0")
    if all(item["hash"] != baseline_control["hash"] for item in final_items):
        final_items.append(baseline_control)
    final_evaluations = []
    for index, item in enumerate(final_items, start=1):
        rows, monthly, annual, mirror = evaluate_layout(
            ray_design,
            item["xy"],
            args.samples,
            args.seed,
            args.neighbor_radius,
            store=True,
            logger=logger,
        )
        final_evaluations.append(
            {**item, "rows256": rows, "monthly256": monthly, "annual256": annual, "mirror256": mirror}
        )
        logger.info(
            "Full256 %d/%d %s P=%.3f unit=%.4f",
            index,
            len(final_items),
            item["metadata"]["candidate_id"],
            annual["field_power_mw"],
            annual["unit_area_power_kw_m2"],
        )
    write_csv(
        args.output / "results" / "full256_candidates.csv",
        [
            {**item["metadata"], **{f"annual256_{key}": value for key, value in item["annual256"].items()}}
            for item in final_evaluations
        ],
    )
    feasible256 = [item for item in final_evaluations if item["annual256"]["field_power_mw"] >= 60.0]
    chosen = max(feasible256, key=lambda item: item["annual256"]["unit_area_power_kw_m2"])
    rows = chosen["rows256"]
    monthly = chosen["monthly256"]
    annual256 = chosen["annual256"]
    mirror = chosen["mirror256"]
    result = {
        **chosen["metadata"],
        **annual256,
        "baseline_power_mw": float(raw_design["field_power_mw"]),
        "baseline_unit_area_power_kw_m2": float(raw_design["unit_area_power_kw_m2"]),
        "power_change_pct": 100.0 * (annual256["field_power_mw"] / float(raw_design["field_power_mw"]) - 1.0),
        "unit_area_change_pct": 100.0 * (annual256["unit_area_power_kw_m2"] / float(raw_design["unit_area_power_kw_m2"]) - 1.0),
    }
    write_csv(args.output / "results" / "annual_metrics.csv", [result])
    write_csv(args.output / "results" / "monthly_metrics.csv", monthly)
    write_csv(args.output / "results" / "time_metrics.csv", rows)
    write_csv(
        args.output / "results" / "final_positions.csv",
        [{"mirror_id": index, "x_m": point[0], "y_m": point[1], "z_m": shifted_design.center_z} for index, point in enumerate(chosen["xy"], start=1)],
    )
    write_csv(
        args.output / "results" / "mirror_annual_metrics.csv",
        [
            {
                "mirror_id": index,
                "x_m": point[0],
                "y_m": point[1],
                "annual_optical_efficiency": values[0],
                "annual_cosine_efficiency": values[1],
                "annual_atmospheric_efficiency": values[2],
                "annual_shadow_blocking_efficiency": values[3],
                "annual_truncation_efficiency": values[4],
            }
            for index, (point, values) in enumerate(zip(chosen["xy"], mirror), start=1)
        ],
    )
    checks = geometry_checks(shifted_design, chosen["xy"])
    checks.update(
        {
            "annual_power_constraint_satisfied": annual256["field_power_mw"] >= 60.0,
            "internal_safety_line_satisfied": annual256["field_power_mw"] >= 60.10,
            "unit_area_improved_over_r05": annual256["unit_area_power_kw_m2"] > float(raw_design["unit_area_power_kw_m2"]),
            "final_samples": args.samples,
        }
    )
    (args.output / "validation" / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.6), constrained_layout=True)
    axes[0].scatter(baseline_xy[:, 0], baseline_xy[:, 1], s=2, color="#bfc5c2", label="r05")
    axes[0].scatter(chosen["xy"][:, 0], chosen["xy"][:, 1], s=2, color="#267a5b", label="r06")
    axes[0].set_aspect("equal")
    axes[0].set_title("局部重排前后镜位")
    axes[0].set_xlabel("x / m")
    axes[0].set_ylabel("y / m")
    axes[0].legend(markerscale=4)
    axes[1].bar(
        ["r05", "r06"],
        [float(raw_design["unit_area_power_kw_m2"]), annual256["unit_area_power_kw_m2"]],
        color=["#899ca6", "#267a5b"],
    )
    axes[1].set_ylabel("单位面积功率 / (kW/m²)")
    axes[1].set_title("256 光线正式结果")
    axes[1].grid(True, axis="y", linewidth=0.5)
    fig.savefig(args.output / "figures" / "fig02-r05-r06-comparison.png", dpi=210)
    plt.close(fig)
    logger.info("FINAL %s", json.dumps(result, ensure_ascii=False))


def main():
    args = parse_args()
    logger = logger_for(args.output)
    raw_design, baseline_xy, low_zones, mirror_power_kw = load_inputs(
        args.baseline_run, args.spatial_run
    )
    shifted_design, ray_design = design_objects(raw_design)
    if args.mode == "geometry":
        geometry_mode(args, baseline_xy, shifted_design, low_zones, logger)
    else:
        full_mode(
            args,
            raw_design,
            baseline_xy,
            shifted_design,
            ray_design,
            low_zones,
            mirror_power_kw,
            logger,
        )
    hashes = {
        HERE.name: hashlib.sha256(HERE.read_bytes()).hexdigest(),
        "q2_model.py": hashlib.sha256((ROUTES / "r01-common-size-field-optimization" / "code" / "q2_model.py").read_bytes()).hexdigest(),
        "shifted_hex_model.py": hashlib.sha256((ROUTES / "r05-shifted-hex-optical-pruning" / "code" / "shifted_hex_model.py").read_bytes()).hexdigest(),
    }
    (args.output / "validation" / "code_hashes.json").write_text(
        json.dumps(hashes, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
