#!/usr/bin/env python3
"""Ray-screen close-packed staggered layouts for feasibility."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
R01_CODE = HERE.parents[2] / "r01-common-size-field-optimization" / "code"
sys.path.insert(0, str(R01_CODE))

from q2_model import Design, aggregate_time_rows, all_states, evaluate_field, validation_states
from hex_layout_model import HexDesign, generate_hex_layout, hex_layout_checks


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def base_design(design: HexDesign) -> Design:
    return Design(
        design.tower_x,
        design.tower_y,
        design.width,
        design.height,
        design.center_z,
        design.first_radius,
        0.0,
        design.tangential_clearance,
        design.max_radius,
        design.phase,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=16)
    parser.add_argument("--seed", type=int, default=202308)
    args = parser.parse_args()
    for folder in ["results", "validation", "figures", "logs"]:
        (args.output / folder).mkdir(parents=True, exist_ok=True)
    designs = []
    for tower_y in (-80.0, -100.0, -120.0):
        for width in (6.2, 6.6, 7.0, 7.4, 7.8):
            for ratio in (0.82, 0.8660254, 0.92):
                designs.append(HexDesign(0.0, tower_y, width, width, max(3.0, width / 2.0), 100.0, ratio, 0.0, 520.0, 0.0))
    reduced = []
    for index, design in enumerate(designs, start=1):
        xy = generate_hex_layout(design)
        rows, _ = evaluate_field(
            base_design(design), xy, args.samples, args.seed + index, neighbor_radius=65.0, states=validation_states()
        )
        _, annual = aggregate_time_rows(rows, design.area * len(xy))
        reduced.append(
            {
                "design_id": index,
                "tower_y_m": design.tower_y,
                "width_m": design.width,
                "radial_ratio": design.radial_ratio,
                "mirror_count": len(xy),
                "total_area_m2": design.area * len(xy),
                **annual,
                **{f"check_{k}": v for k, v in hex_layout_checks(design, xy).items() if k != "mirror_count"},
            }
        )
        print(f"reduced {index}/{len(designs)} W={design.width:.1f} y={design.tower_y:.0f} ratio={design.radial_ratio:.3f} N={len(xy)} P={annual['field_power_mw']:.3f}", flush=True)
    write_csv(args.output / "results" / "reduced_close_packed_screen.csv", reduced)
    top_ids = [int(row["design_id"]) for row in sorted(reduced, key=lambda row: row["field_power_mw"], reverse=True)[:6]]
    full = []
    for rank, design_id in enumerate(top_ids, start=1):
        design = designs[design_id - 1]
        xy = generate_hex_layout(design)
        rows, _ = evaluate_field(
            base_design(design), xy, args.samples, args.seed, neighbor_radius=65.0, states=all_states()
        )
        _, annual = aggregate_time_rows(rows, design.area * len(xy))
        full.append(
            {
                "rank": rank,
                "design_id": design_id,
                "tower_y_m": design.tower_y,
                "width_m": design.width,
                "radial_ratio": design.radial_ratio,
                "mirror_count": len(xy),
                "total_area_m2": design.area * len(xy),
                **annual,
            }
        )
        print(f"full {rank}/6 id={design_id} P={annual['field_power_mw']:.3f} unit={annual['unit_area_power_kw_m2']:.4f}", flush=True)
    write_csv(args.output / "results" / "full_year_close_packed_screen.csv", full)


if __name__ == "__main__":
    main()
