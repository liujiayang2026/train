"""Solve CUMCM 2016 Problem A, Question 2 by minimum-ballast search."""

from __future__ import annotations

import csv
import importlib.util
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
Q1_PATH = HERE.parents[1] / "question-1" / "code" / "solve_question1.py"
SPEC = importlib.util.spec_from_file_location("q1_model", Q1_PATH)
MODEL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODEL)

WIND_SPEED = 36.0
BARREL_LIMIT_DEG = 5.0
ANCHOR_LIMIT_DEG = 16.0


def solve_for_mass(ballast_mass_kg: float) -> dict:
    """Solve equilibrium after setting the independent ballast point load."""
    MODEL.BALL_WEIGHT = ballast_mass_kg * MODEL.G
    result = MODEL.solve(WIND_SPEED)
    result = dict(result)
    result["ballast_mass_kg"] = ballast_mass_kg
    result["barrel_margin_deg"] = BARREL_LIMIT_DEG - result["barrel_angle_deg"]
    result["anchor_margin_deg"] = ANCHOR_LIMIT_DEG - result["anchor_angle_deg"]
    result["feasible"] = (
        result["barrel_angle_deg"] <= BARREL_LIMIT_DEG
        and result["anchor_angle_deg"] <= ANCHOR_LIMIT_DEG
    )
    result["exposed_height_m"] = MODEL.BUOY_HEIGHT - result["draft_m"]
    result["wind_area_m2"] = 2.0 * MODEL.BUOY_RADIUS * result["exposed_height_m"]
    return result


def threshold_mass(metric: str, limit: float, lower: float, upper: float) -> float:
    """Find the smallest mass for which a monotonically decreasing metric meets a limit."""
    if solve_for_mass(lower)[metric] <= limit:
        return lower
    if solve_for_mass(upper)[metric] > limit:
        raise ValueError("Upper mass does not satisfy the requested constraint")
    for _ in range(100):
        middle = 0.5 * (lower + upper)
        if solve_for_mass(middle)[metric] <= limit:
            upper = middle
        else:
            lower = middle
        if upper - lower < 1e-9:
            break
    return upper


def flatten(result: dict) -> dict:
    row = {key: value for key, value in result.items() if key != "pipe_angles_deg"}
    for index, angle in enumerate(result["pipe_angles_deg"], start=1):
        row[f"pipe_{index}_angle_deg"] = angle
    return row


def main() -> None:
    output_dir = HERE.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    barrel_threshold = threshold_mass(
        "barrel_angle_deg", BARREL_LIMIT_DEG, 1200.0, 2500.0
    )
    anchor_threshold = threshold_mass(
        "anchor_angle_deg", ANCHOR_LIMIT_DEG, 1200.0, 2500.0
    )
    theoretical_optimum = max(barrel_threshold, anchor_threshold)

    cases = [
        solve_for_mass(1200.0),
        solve_for_mass(anchor_threshold),
        solve_for_mass(theoretical_optimum),
        solve_for_mass(1800.0),
    ]

    baseline, _, optimum, recommended = cases
    if baseline["chain_state"] != "fully suspended":
        raise AssertionError("The 36 m/s baseline must use the fully suspended chain model")
    if baseline["barrel_angle_deg"] <= BARREL_LIMIT_DEG:
        raise AssertionError("Baseline unexpectedly satisfies the barrel constraint")
    if baseline["anchor_angle_deg"] <= ANCHOR_LIMIT_DEG:
        raise AssertionError("Baseline unexpectedly satisfies the anchor constraint")
    if abs(optimum["barrel_angle_deg"] - BARREL_LIMIT_DEG) > 1e-8:
        raise AssertionError("Theoretical optimum is not on the active barrel constraint")
    if optimum["anchor_angle_deg"] > ANCHOR_LIMIT_DEG:
        raise AssertionError("Theoretical optimum violates the anchor constraint")
    if not recommended["feasible"]:
        raise AssertionError("Recommended 1800 kg design is not feasible")
    for result in cases:
        closure = (
            result["draft_m"]
            + result["chain_vertical_rise_m"]
            + result["member_vertical_span_m"]
        )
        if abs(closure - MODEL.WATER_DEPTH) > 1e-8:
            raise AssertionError("Water-depth closure failed")

    summary_path = output_dir / "question-2-summary.csv"
    rows = [flatten(case) for case in cases]
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    sensitivity_path = output_dir / "ballast-mass-sensitivity.csv"
    sensitivity_masses = list(range(1200, 2201, 50))
    with sensitivity_path.open("w", newline="", encoding="utf-8-sig") as handle:
        fields = [
            "ballast_mass_kg", "barrel_angle_deg", "anchor_angle_deg", "draft_m",
            "horizontal_tension_n", "excursion_radius_m", "chain_state", "feasible",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for mass in sensitivity_masses:
            result = solve_for_mass(float(mass))
            writer.writerow({field: result[field] for field in fields})

    print(f"anchor threshold mass = {anchor_threshold:.9f} kg")
    print(f"barrel threshold mass = {barrel_threshold:.9f} kg")
    print(f"theoretical optimum = {theoretical_optimum:.9f} kg")
    for case in cases:
        print(flatten(case))


if __name__ == "__main__":
    main()
