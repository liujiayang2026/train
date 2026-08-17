#!/usr/bin/env python3
"""Screen hexagonal-lattice designs with cone-ray tracing."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
R01_CODE = HERE.parents[2] / "r01-common-size-field-optimization" / "code"
sys.path.insert(0, str(R01_CODE))

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field, validation_states
from lattice_model import LatticeDesign, generate_lattice, lattice_checks


def ray_design(design: LatticeDesign) -> Design:
    return Design(design.tower_x, design.tower_y, design.width, design.height, design.center_z, 100.0, 0.0, design.clearance, 520.0, design.phase)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--seed", type=int, default=202308)
    args = parser.parse_args()
    for folder in ["results", "figures", "validation", "logs"]:
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    designs = []
    for tower_y in (-60.0, -80.0, -100.0, -120.0):
        for width in (6.0, 6.4, 6.8, 7.2, 7.6, 8.0):
            for height_offset in (0.0, -0.6):
                height = max(2.0, width + height_offset)
                designs.append(LatticeDesign(0.0, tower_y, width, height, max(3.0, height / 2.0), 0.0, 0.0))
    reduced = []
    for index, design in enumerate(designs, start=1):
        xy = generate_lattice(design)
        rows, _ = evaluate_field(ray_design(design), xy, args.samples, args.seed + index, 70.0, validation_states())
        _, annual = aggregate_time_rows(rows, design.area * len(xy))
        reduced.append({
            "design_id": index,
            "tower_y_m": design.tower_y,
            "width_m": design.width,
            "height_m": design.height,
            "mirror_count": len(xy),
            "total_area_m2": design.area * len(xy),
            **annual,
            **{f"check_{k}": v for k, v in lattice_checks(design, xy).items() if k != "mirror_count"},
        })
        print(f"reduced {index}/{len(designs)} W={design.width:.1f} H={design.height:.1f} y={design.tower_y:.0f} N={len(xy)} P={annual['field_power_mw']:.3f}", flush=True)
    write_csv(args.output / "results" / "reduced_hex_screen.csv", reduced)
    top_ids = [int(row["design_id"]) for row in sorted(reduced, key=lambda row: row["field_power_mw"], reverse=True)[:8]]
    full = []
    for rank, design_id in enumerate(top_ids, start=1):
        design = designs[design_id - 1]
        xy = generate_lattice(design)
        rows, _ = evaluate_field(ray_design(design), xy, args.samples, args.seed, 70.0, all_states())
        _, annual = aggregate_time_rows(rows, design.area * len(xy))
        full.append({
            "rank": rank,
            "design_id": design_id,
            "tower_y_m": design.tower_y,
            "width_m": design.width,
            "height_m": design.height,
            "mirror_count": len(xy),
            "total_area_m2": design.area * len(xy),
            **annual,
        })
        print(f"full {rank}/8 id={design_id} P={annual['field_power_mw']:.3f} unit={annual['unit_area_power_kw_m2']:.4f}", flush=True)
    write_csv(args.output / "results" / "full_year_hex_screen.csv", full)


if __name__ == "__main__":
    main()
