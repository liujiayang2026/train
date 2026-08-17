#!/usr/bin/env python3
"""High-precision multi-seed validation of an existing shifted-hex design."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
sys.path.insert(0, str(ROUTES / "r01-common-size-field-optimization" / "code"))
sys.path.insert(0, str(ROUTES / "r05-shifted-hex-optical-pruning" / "code"))

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field  # noqa: E402
from shifted_hex_model import ShiftedHexDesign, geometry_checks  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--design-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--seeds", type=int, nargs="+", default=[202308, 202309, 202310])
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_design(raw: dict) -> ShiftedHexDesign:
    return ShiftedHexDesign(
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


def ray_design(design: ShiftedHexDesign) -> Design:
    spacing = design.spacing
    return Design(
        design.tower_x,
        design.tower_y,
        design.width,
        design.height,
        design.center_z,
        100.0,
        math.sqrt(3.0) * spacing / 2.0 - (design.width + 5.0),
        spacing - (design.width + 5.0),
        520.0,
        design.rotation,
    )


def main() -> None:
    args = parse_args()
    for folder in ("results", "figures", "validation", "logs"):
        (args.output / folder).mkdir(parents=True, exist_ok=True)

    raw = json.loads((args.design_run / "results" / "design.json").read_text(encoding="utf-8"))
    position_rows = read_csv(args.design_run / "results" / "final_positions.csv")
    xy = np.asarray([[float(row["x_m"]), float(row["y_m"])] for row in position_rows])
    design = make_design(raw)
    optical_design = ray_design(design)

    seed_rows = []
    for seed in args.seeds:
        time_rows, _ = evaluate_field(
            optical_design,
            xy,
            args.samples,
            seed,
            args.neighbor_radius,
            states=all_states(),
        )
        _, annual = aggregate_time_rows(time_rows, design.area * len(xy))
        seed_rows.append({"seed": seed, "samples": args.samples, **annual})
        write_csv(args.output / "results" / f"time_metrics_seed_{seed}.csv", time_rows)

    powers = np.asarray([row["field_power_mw"] for row in seed_rows], dtype=float)
    units = np.asarray([row["unit_area_power_kw_m2"] for row in seed_rows], dtype=float)
    mean_power = float(np.mean(powers))
    std_power = float(np.std(powers, ddof=1)) if len(powers) > 1 else 0.0
    summary = {
        "source_design_run": str(args.design_run),
        "samples_per_mirror_time": args.samples,
        "seeds": args.seeds,
        "mirror_count": len(xy),
        "total_area_m2": design.area * len(xy),
        "mean_power_mw": mean_power,
        "std_power_mw": std_power,
        "lcb_power_mw": mean_power - 2.0 * std_power,
        "minimum_seed_power_mw": float(np.min(powers)),
        "maximum_seed_power_mw": float(np.max(powers)),
        "mean_unit_area_power_kw_m2": float(np.mean(units)),
        "all_seed_power_constraint_satisfied": bool(np.all(powers >= 60.0)),
        "lcb_power_constraint_satisfied": bool(mean_power - 2.0 * std_power >= 60.0),
    }
    write_csv(args.output / "results" / "seed_metrics.csv", seed_rows)
    write_json(args.output / "results" / "summary.json", summary)

    checks = {
        **geometry_checks(design, xy),
        "installation_height_m": design.center_z,
        "installation_height_constraint_satisfied": bool(2.0 <= design.center_z <= 6.0),
        "mirror_dimensions_constraint_satisfied": bool(2.0 <= design.height <= design.width <= 8.0),
        **{key: summary[key] for key in ("all_seed_power_constraint_satisfied", "lcb_power_constraint_satisfied")},
    }
    write_json(args.output / "validation" / "checks.json", checks)
    write_json(
        args.output / "validation" / "code_hashes.json",
        {
            "validate_existing_design.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "q2_model.py": hashlib.sha256((ROUTES / "r01-common-size-field-optimization" / "code" / "q2_model.py").read_bytes()).hexdigest(),
        },
    )

    fig, ax = plt.subplots(figsize=(7.2, 4.6), constrained_layout=True)
    ax.bar([str(seed) for seed in args.seeds], powers, color="#2a7f62", width=0.58)
    ax.axhline(60.0, color="#b42318", linestyle="--", linewidth=1.3, label="60 MW constraint")
    ax.set(xlabel="Sobol scramble seed", ylabel="Annual average power / MW", title=f"{args.samples}-ray robustness validation")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(frameon=False)
    fig.savefig(args.output / "figures" / "seed-power-validation.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()
