"""Solve CUMCM 2016 Problem A, Question 1 with a planar static model."""

from __future__ import annotations

import csv
import math
from pathlib import Path

G = 9.81
RHO = 1025.0
WATER_DEPTH = 18.0

BUOY_MASS = 1000.0
BUOY_RADIUS = 1.0
BUOY_HEIGHT = 2.0

PIPE_COUNT = 4
PIPE_LENGTH = 1.0
PIPE_DIAMETER = 0.05
PIPE_MASS = 10.0

BARREL_LENGTH = 1.0
BARREL_DIAMETER = 0.30
BARREL_MASS = 100.0

BALL_MASS = 1200.0

CHAIN_LENGTH = 22.05
CHAIN_MASS_PER_M = 7.0


def effective_weight(mass: float, diameter: float, length: float) -> float:
    """Submerged weight of a sealed cylindrical member."""
    displaced_volume = math.pi * diameter**2 * length / 4.0
    return mass * G - RHO * G * displaced_volume


PIPE_WEIGHT = effective_weight(PIPE_MASS, PIPE_DIAMETER, PIPE_LENGTH)
BARREL_WEIGHT = effective_weight(BARREL_MASS, BARREL_DIAMETER, BARREL_LENGTH)
BALL_WEIGHT = BALL_MASS * G  # Problem gives no ball volume; buoyancy is neglected.
CHAIN_WEIGHT_PER_M = CHAIN_MASS_PER_M * G  # Chain volume is not supplied.
BUOY_AREA = math.pi * BUOY_RADIUS**2


def bisect_root(function, lower: float, upper: float, tolerance: float = 1e-11) -> float:
    """Find a bracketed scalar root without third-party dependencies."""
    f_lower = function(lower)
    f_upper = function(upper)
    if f_lower == 0.0:
        return lower
    if f_upper == 0.0:
        return upper
    if f_lower * f_upper > 0.0:
        raise ValueError("Root is not bracketed")
    for _ in range(200):
        middle = 0.5 * (lower + upper)
        f_middle = function(middle)
        if abs(f_middle) < tolerance or upper - lower < tolerance:
            return middle
        if f_lower * f_middle <= 0.0:
            upper = middle
        else:
            lower = middle
            f_lower = f_middle
    return 0.5 * (lower + upper)


def member_state(horizontal_tension: float, chain_top_vertical: float):
    """Return member angles and the vertical load exerted on the buoy."""
    lower = chain_top_vertical + BALL_WEIGHT

    upper = lower + BARREL_WEIGHT
    barrel_angle = math.atan2(2.0 * horizontal_tension, lower + upper)
    lower = upper

    pipe_angles_bottom_up = []
    for _ in range(PIPE_COUNT):
        upper = lower + PIPE_WEIGHT
        angle = math.atan2(2.0 * horizontal_tension, lower + upper)
        pipe_angles_bottom_up.append(angle)
        lower = upper

    return barrel_angle, list(reversed(pipe_angles_bottom_up)), lower


def buoy_state(wind_speed: float, chain_top_vertical: float):
    """Compute draft, horizontal tension, and member angles for a chain load."""
    # Draft depends only on the total vertical load; upright buoy is assumed.
    _, _, buoy_vertical_load = member_state(0.0, chain_top_vertical)
    draft = (BUOY_MASS * G + buoy_vertical_load) / (RHO * G * BUOY_AREA)
    exposed_area = 2.0 * BUOY_RADIUS * (BUOY_HEIGHT - draft)
    horizontal_tension = 0.625 * exposed_area * wind_speed**2
    barrel_angle, pipe_angles, buoy_vertical_load = member_state(
        horizontal_tension, chain_top_vertical
    )
    return draft, horizontal_tension, barrel_angle, pipe_angles, buoy_vertical_load


def member_geometry(barrel_angle: float, pipe_angles: list[float]):
    vertical = BARREL_LENGTH * math.cos(barrel_angle)
    horizontal = BARREL_LENGTH * math.sin(barrel_angle)
    for angle in pipe_angles:
        vertical += PIPE_LENGTH * math.cos(angle)
        horizontal += PIPE_LENGTH * math.sin(angle)
    return horizontal, vertical


def suspended_chain_geometry(horizontal_tension: float, bottom_vertical: float):
    """Geometry of the full 22.05 m chain for prescribed bottom tension."""
    top_vertical = bottom_vertical + CHAIN_WEIGHT_PER_M * CHAIN_LENGTH
    x = horizontal_tension / CHAIN_WEIGHT_PER_M * (
        math.asinh(top_vertical / horizontal_tension)
        - math.asinh(bottom_vertical / horizontal_tension)
    )
    y = (
        math.hypot(horizontal_tension, top_vertical)
        - math.hypot(horizontal_tension, bottom_vertical)
    ) / CHAIN_WEIGHT_PER_M
    return x, y, top_vertical


def solve_partly_grounded(wind_speed: float):
    """Try a chain with a horizontal tangent at the lift-off point."""

    def residual(suspended_length: float) -> float:
        chain_top_vertical = CHAIN_WEIGHT_PER_M * suspended_length
        draft, h_tension, barrel_angle, pipe_angles, _ = buoy_state(
            wind_speed, chain_top_vertical
        )
        chain_y = (
            math.hypot(h_tension, chain_top_vertical) - h_tension
        ) / CHAIN_WEIGHT_PER_M
        _, members_y = member_geometry(barrel_angle, pipe_angles)
        return chain_y + members_y - (WATER_DEPTH - draft)

    suspended_length = bisect_root(residual, 1e-8, 60.0)
    if suspended_length > CHAIN_LENGTH + 1e-8:
        return None

    chain_top_vertical = CHAIN_WEIGHT_PER_M * suspended_length
    draft, h_tension, barrel_angle, pipe_angles, buoy_vertical_load = buoy_state(
        wind_speed, chain_top_vertical
    )
    chain_x = h_tension / CHAIN_WEIGHT_PER_M * math.asinh(
        chain_top_vertical / h_tension
    )
    chain_y = (
        math.hypot(h_tension, chain_top_vertical) - h_tension
    ) / CHAIN_WEIGHT_PER_M
    members_x, members_y = member_geometry(barrel_angle, pipe_angles)
    grounded_length = CHAIN_LENGTH - suspended_length
    excursion = grounded_length + chain_x + members_x
    return {
        "wind_speed_m_s": wind_speed,
        "chain_state": "partly grounded",
        "draft_m": draft,
        "horizontal_tension_n": h_tension,
        "chain_top_vertical_n": chain_top_vertical,
        "anchor_vertical_n": 0.0,
        "anchor_angle_deg": 0.0,
        "suspended_chain_m": suspended_length,
        "grounded_chain_m": grounded_length,
        "chain_horizontal_span_m": grounded_length + chain_x,
        "chain_suspended_horizontal_m": chain_x,
        "chain_vertical_rise_m": chain_y,
        "member_horizontal_span_m": members_x,
        "member_vertical_span_m": members_y,
        "excursion_radius_m": excursion,
        "excursion_area_m2": math.pi * excursion**2,
        "barrel_angle_deg": math.degrees(barrel_angle),
        "pipe_angles_deg": [math.degrees(a) for a in pipe_angles],
        "buoy_vertical_load_n": buoy_vertical_load,
    }


def solve_fully_suspended(wind_speed: float):
    """Solve a chain fully clear of the seabed."""

    def residual(bottom_vertical: float) -> float:
        chain_x, chain_y, chain_top_vertical = suspended_chain_geometry(
            buoy_state(wind_speed, bottom_vertical + CHAIN_WEIGHT_PER_M * CHAIN_LENGTH)[1],
            bottom_vertical,
        )
        draft, _, barrel_angle, pipe_angles, _ = buoy_state(
            wind_speed, chain_top_vertical
        )
        _, members_y = member_geometry(barrel_angle, pipe_angles)
        return chain_y + members_y - (WATER_DEPTH - draft)

    # The residual is negative at the transition and increases with bottom tension.
    lower = 0.0
    upper = 1.0
    while residual(upper) < 0.0:
        upper *= 2.0
        if upper > 1e7:
            raise RuntimeError("Unable to bracket the fully suspended solution")
    bottom_vertical = bisect_root(residual, lower, upper)

    # Iterate once consistently because H depends on draft, hence on top vertical load.
    chain_top_vertical = bottom_vertical + CHAIN_WEIGHT_PER_M * CHAIN_LENGTH
    draft, h_tension, barrel_angle, pipe_angles, buoy_vertical_load = buoy_state(
        wind_speed, chain_top_vertical
    )
    chain_x, chain_y, chain_top_vertical = suspended_chain_geometry(
        h_tension, bottom_vertical
    )
    members_x, members_y = member_geometry(barrel_angle, pipe_angles)
    excursion = chain_x + members_x
    return {
        "wind_speed_m_s": wind_speed,
        "chain_state": "fully suspended",
        "draft_m": draft,
        "horizontal_tension_n": h_tension,
        "chain_top_vertical_n": chain_top_vertical,
        "anchor_vertical_n": bottom_vertical,
        "anchor_angle_deg": math.degrees(math.atan2(bottom_vertical, h_tension)),
        "suspended_chain_m": CHAIN_LENGTH,
        "grounded_chain_m": 0.0,
        "chain_horizontal_span_m": chain_x,
        "chain_suspended_horizontal_m": chain_x,
        "chain_vertical_rise_m": chain_y,
        "member_horizontal_span_m": members_x,
        "member_vertical_span_m": members_y,
        "excursion_radius_m": excursion,
        "excursion_area_m2": math.pi * excursion**2,
        "barrel_angle_deg": math.degrees(barrel_angle),
        "pipe_angles_deg": [math.degrees(a) for a in pipe_angles],
        "buoy_vertical_load_n": buoy_vertical_load,
    }


def solve(wind_speed: float):
    grounded = solve_partly_grounded(wind_speed)
    return grounded if grounded is not None else solve_fully_suspended(wind_speed)


def chain_profile(result: dict, points: int = 101):
    """Generate anchor-based coordinates for plotting the chain."""
    h_tension = result["horizontal_tension_n"]
    q = CHAIN_WEIGHT_PER_M
    rows = []
    if result["chain_state"] == "partly grounded":
        grounded = result["grounded_chain_m"]
        rows.append((result["wind_speed_m_s"], 0.0, 0.0))
        for i in range(points):
            s = result["suspended_chain_m"] * i / (points - 1)
            x = grounded + h_tension / q * math.asinh(q * s / h_tension)
            y = h_tension / q * (math.sqrt(1.0 + (q * s / h_tension) ** 2) - 1.0)
            rows.append((result["wind_speed_m_s"], x, y))
    else:
        bottom_vertical = result["anchor_vertical_n"]
        for i in range(points):
            s = CHAIN_LENGTH * i / (points - 1)
            vertical = bottom_vertical + q * s
            x = h_tension / q * (
                math.asinh(vertical / h_tension)
                - math.asinh(bottom_vertical / h_tension)
            )
            y = (
                math.hypot(h_tension, vertical)
                - math.hypot(h_tension, bottom_vertical)
            ) / q
            rows.append((result["wind_speed_m_s"], x, y))
    return rows


def main() -> None:
    results = [solve(12.0), solve(24.0)]
    for result in results:
        vertical_closure = (
            result["draft_m"]
            + result["chain_vertical_rise_m"]
            + result["member_vertical_span_m"]
        )
        if abs(vertical_closure - WATER_DEPTH) > 1e-8:
            raise AssertionError("Water-depth closure check failed")
        if not 0.0 < result["draft_m"] < BUOY_HEIGHT:
            raise AssertionError("Buoy draft is physically invalid")
        if result["suspended_chain_m"] > CHAIN_LENGTH + 1e-8:
            raise AssertionError("Suspended chain exceeds total chain length")
    output_dir = Path(__file__).resolve().parents[1] / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "question-1-summary.csv"
    fields = [
        "wind_speed_m_s", "chain_state", "draft_m", "horizontal_tension_n",
        "chain_top_vertical_n", "anchor_vertical_n", "anchor_angle_deg",
        "suspended_chain_m", "grounded_chain_m", "chain_horizontal_span_m",
        "chain_vertical_rise_m", "member_horizontal_span_m",
        "member_vertical_span_m", "excursion_radius_m", "excursion_area_m2",
        "barrel_angle_deg", "pipe_1_angle_deg", "pipe_2_angle_deg",
        "pipe_3_angle_deg", "pipe_4_angle_deg", "buoy_vertical_load_n",
    ]
    with summary_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = {key: result.get(key) for key in fields}
            for i, angle in enumerate(result["pipe_angles_deg"], start=1):
                row[f"pipe_{i}_angle_deg"] = angle
            writer.writerow(row)

    profile_path = output_dir / "chain-profiles.csv"
    with profile_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["wind_speed_m_s", "x_from_anchor_m", "height_above_seabed_m"])
        for result in results:
            writer.writerows(chain_profile(result))

    for result in results:
        print(result)


if __name__ == "__main__":
    main()
