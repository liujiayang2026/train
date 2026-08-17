#!/usr/bin/env python3
"""Screen representative common-size layouts with the real cone-ray evaluator."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field, generate_layout, validation_states


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
    parser.add_argument("--neighbor-radius", type=float, default=65.0)
    args = parser.parse_args()
    for folder in ["results", "validation", "logs", "figures"]:
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    designs = []
    for tower_y in (-100.0, -140.0):
        for width in (5.4, 5.8, 6.2, 6.6, 7.0, 7.4, 7.8):
            designs.append(Design(0.0, tower_y, width, width, max(3.0, width / 2.0), 100.0, 0.0, 0.0, 520.0, 0.0))
    for width in (6.0, 7.0, 8.0):
        designs.append(Design(0.0, -140.0, width, width, max(3.0, width / 2.0), 100.0, 1.5, 1.5, 520.0, 0.0))
    reduced_rows = []
    for index, design in enumerate(designs, start=1):
        xy = generate_layout(design)
        rows, _ = evaluate_field(
            design,
            xy,
            samples=args.samples,
            seed=args.seed + index,
            neighbor_radius=args.neighbor_radius,
            states=validation_states(),
        )
        _, annual = aggregate_time_rows(rows, design.area * len(xy))
        reduced_rows.append(
            {
                "design_id": index,
                "tower_y_m": design.tower_y,
                "width_m": design.width,
                "height_m": design.height,
                "clearance_m": design.radial_clearance,
                "mirror_count": len(xy),
                "total_area_m2": design.area * len(xy),
                **annual,
            }
        )
        print(f"reduced {index}/{len(designs)} W={design.width:.1f} y={design.tower_y:.0f} c={design.radial_clearance:.1f} P={annual['field_power_mw']:.3f}", flush=True)
    write_csv(args.output / "results" / "reduced_ray_screen.csv", reduced_rows)
    best_ids = [int(row["design_id"]) for row in sorted(reduced_rows, key=lambda row: row["field_power_mw"], reverse=True)[:5]]
    full_rows = []
    for rank, design_id in enumerate(best_ids, start=1):
        design = designs[design_id - 1]
        xy = generate_layout(design)
        rows, _ = evaluate_field(
            design,
            xy,
            samples=args.samples,
            seed=args.seed,
            neighbor_radius=args.neighbor_radius,
            states=all_states(),
        )
        _, annual = aggregate_time_rows(rows, design.area * len(xy))
        full_rows.append(
            {
                "rank": rank,
                "design_id": design_id,
                "tower_y_m": design.tower_y,
                "width_m": design.width,
                "height_m": design.height,
                "clearance_m": design.radial_clearance,
                "mirror_count": len(xy),
                "total_area_m2": design.area * len(xy),
                **annual,
            }
        )
        print(f"full {rank}/5 id={design_id} P={annual['field_power_mw']:.3f} unit={annual['unit_area_power_kw_m2']:.4f}", flush=True)
    write_csv(args.output / "results" / "full_year_ray_screen.csv", full_rows)


if __name__ == "__main__":
    main()
