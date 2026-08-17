#!/usr/bin/env python3
"""Re-render the seven final figures from a completed numerical run."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
R01_CODE = HERE.parents[2] / "r01-common-size-field-optimization" / "code"
sys.path.insert(0, str(R01_CODE))

from optimize_common_size import configure_plots, plot_final_field, plot_monthly_convergence, plot_q1_q2_comparison, read_csv_row
from q2_model import Design
from lattice_model import LatticeDesign
from optimize_hex_lattice import plot_convergence_accuracy, plot_filtering, plot_parameter_diagram, plot_pareto


def read_rows(path: Path) -> list[dict[str, float]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--q1-annual", required=True, type=Path)
    args = parser.parse_args()
    (args.output / "figures").mkdir(parents=True, exist_ok=True)
    (args.output / "validation").mkdir(parents=True, exist_ok=True)
    (args.output / "results").mkdir(parents=True, exist_ok=True)
    (args.output / "logs").mkdir(parents=True, exist_ok=True)
    configure_plots()
    results = args.source_run / "results"
    design_data = json.loads((results / "design.json").read_text(encoding="utf-8"))
    design = LatticeDesign(
        design_data["tower_x"],
        design_data["tower_y"],
        design_data["width"],
        design_data["height"],
        design_data["center_z"],
        design_data["clearance"],
        design_data["phase"],
    )
    base_design = Design(design.tower_x, design.tower_y, design.width, design.height, design.center_z, 100.0, 0.0, design.clearance, 520.0, design.phase)
    positions = read_rows(results / "heliostat_positions.csv")
    xy = np.array([[row["x_m"], row["y_m"]] for row in positions])
    mirror_rows = read_rows(results / "mirror_annual_metrics.csv")
    mirror = np.array(
        [
            [
                row["annual_optical_efficiency"],
                row["annual_cosine_efficiency"],
                row["annual_atmospheric_efficiency"],
                row["annual_shadow_blocking_efficiency"],
                row["annual_truncation_efficiency"],
            ]
            for row in mirror_rows
        ]
    )
    annual = read_csv_row(results / "annual_metrics.csv")
    monthly = read_rows(results / "monthly_metrics.csv")
    ray = read_rows(results / "ray_sample_convergence.csv")
    optimization = read_rows(results / "optimization_samples.csv")
    convergence = read_rows(results / "optimization_convergence.csv")
    cv = read_rows(results / "surrogate_loocv.csv")
    q1 = read_csv_row(args.q1_annual)
    plot_parameter_diagram(args.output, design, xy)
    plot_filtering(args.output, design)
    plot_pareto(args.output, optimization, design.area * len(xy), annual["unit_area_power_kw_m2"])
    quality = plot_convergence_accuracy(args.output, convergence, cv)
    plot_final_field(args.output, base_design, xy, mirror)
    plot_q1_q2_comparison(args.output, q1, annual)
    plot_monthly_convergence(args.output, monthly, ray)
    (args.output / "validation" / "image-check.json").write_text(
        json.dumps({**quality, "figure_count": len(list((args.output / "figures").glob("*.png")))}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
