"""Validate the continuous catenary solution with a discrete 210-link model."""

from __future__ import annotations

import csv
import importlib.util
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("q1_continuous", HERE / "solve_question1.py")
MODEL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODEL)

LINK_LENGTH = 0.105
LINK_COUNT = 210


def discrete_suspended_geometry(horizontal_tension: float, suspended_length: float):
    """Sum short-link projections using midpoint vertical tension per link."""
    remaining = suspended_length
    lower_vertical = 0.0
    x_total = 0.0
    y_total = 0.0
    segments = []

    while remaining > 1e-14:
        ds = min(LINK_LENGTH, remaining)
        upper_vertical = lower_vertical + MODEL.CHAIN_WEIGHT_PER_M * ds
        mean_vertical = 0.5 * (lower_vertical + upper_vertical)
        tension_norm = math.hypot(horizontal_tension, mean_vertical)
        dx = ds * horizontal_tension / tension_norm
        dy = ds * mean_vertical / tension_norm
        x_total += dx
        y_total += dy
        segments.append((ds, dx, dy, lower_vertical, upper_vertical))
        lower_vertical = upper_vertical
        remaining -= ds

    return x_total, y_total, lower_vertical, segments


def solve_discrete(wind_speed: float):
    """Solve the partly grounded equilibrium using discrete chain elements."""

    def residual(suspended_length: float) -> float:
        chain_top_vertical = MODEL.CHAIN_WEIGHT_PER_M * suspended_length
        draft, horizontal_tension, barrel_angle, pipe_angles, _ = MODEL.buoy_state(
            wind_speed, chain_top_vertical
        )
        _, chain_y, _, _ = discrete_suspended_geometry(
            horizontal_tension, suspended_length
        )
        _, members_y = MODEL.member_geometry(barrel_angle, pipe_angles)
        return draft + chain_y + members_y - MODEL.WATER_DEPTH

    suspended_length = MODEL.bisect_root(residual, 1e-10, MODEL.CHAIN_LENGTH)
    chain_top_vertical = MODEL.CHAIN_WEIGHT_PER_M * suspended_length
    draft, horizontal_tension, barrel_angle, pipe_angles, buoy_vertical_load = (
        MODEL.buoy_state(wind_speed, chain_top_vertical)
    )
    chain_suspended_x, chain_y, _, segments = discrete_suspended_geometry(
        horizontal_tension, suspended_length
    )
    members_x, members_y = MODEL.member_geometry(barrel_angle, pipe_angles)
    grounded_length = MODEL.CHAIN_LENGTH - suspended_length
    chain_x = grounded_length + chain_suspended_x
    excursion = chain_x + members_x

    if abs(draft + chain_y + members_y - MODEL.WATER_DEPTH) > 1e-8:
        raise AssertionError("Discrete water-depth closure failed")

    return {
        "wind_speed_m_s": wind_speed,
        "draft_m": draft,
        "horizontal_tension_n": horizontal_tension,
        "suspended_chain_m": suspended_length,
        "grounded_chain_m": grounded_length,
        "chain_horizontal_span_m": chain_x,
        "chain_vertical_rise_m": chain_y,
        "excursion_radius_m": excursion,
        "barrel_angle_deg": math.degrees(barrel_angle),
        "pipe_angles_deg": [math.degrees(angle) for angle in pipe_angles],
        "buoy_vertical_load_n": buoy_vertical_load,
        "discrete_elements": len(segments),
    }


def relative_error(discrete: float, continuous: float) -> float:
    return abs(discrete - continuous) / abs(continuous) * 100.0


def main() -> None:
    output_dir = HERE.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison_rows = []

    scalar_metrics = [
        "draft_m",
        "horizontal_tension_n",
        "suspended_chain_m",
        "grounded_chain_m",
        "chain_horizontal_span_m",
        "chain_vertical_rise_m",
        "excursion_radius_m",
        "barrel_angle_deg",
    ]

    for wind_speed in (12.0, 24.0):
        continuous = MODEL.solve(wind_speed)
        discrete = solve_discrete(wind_speed)
        for metric in scalar_metrics:
            comparison_rows.append(
                {
                    "wind_speed_m_s": wind_speed,
                    "metric": metric,
                    "continuous": continuous[metric],
                    "discrete": discrete[metric],
                    "absolute_difference": abs(discrete[metric] - continuous[metric]),
                    "relative_error_percent": relative_error(
                        discrete[metric], continuous[metric]
                    ),
                }
            )
        for index, (continuous_angle, discrete_angle) in enumerate(
            zip(continuous["pipe_angles_deg"], discrete["pipe_angles_deg"]), start=1
        ):
            comparison_rows.append(
                {
                    "wind_speed_m_s": wind_speed,
                    "metric": f"pipe_{index}_angle_deg",
                    "continuous": continuous_angle,
                    "discrete": discrete_angle,
                    "absolute_difference": abs(discrete_angle - continuous_angle),
                    "relative_error_percent": relative_error(discrete_angle, continuous_angle),
                }
            )

    path = output_dir / "continuous-discrete-validation.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=comparison_rows[0].keys())
        writer.writeheader()
        writer.writerows(comparison_rows)

    for row in comparison_rows:
        print(
            f"v={row['wind_speed_m_s']:g}, {row['metric']}: "
            f"continuous={row['continuous']:.9f}, discrete={row['discrete']:.9f}, "
            f"error={row['relative_error_percent']:.6f}%"
        )


if __name__ == "__main__":
    main()
