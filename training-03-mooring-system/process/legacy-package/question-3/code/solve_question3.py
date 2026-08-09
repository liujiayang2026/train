"""Robust design search for CUMCM 2016 Problem A, Question 3."""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path


G = 9.81
RHO = 1025.0
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

PIPE_WEIGHT = PIPE_MASS * G - RHO * G * math.pi * PIPE_DIAMETER**2 / 4
BARREL_WEIGHT = BARREL_MASS * G - RHO * G * math.pi * BARREL_DIAMETER**2 / 4
BUOY_DENOMINATOR = RHO * G * math.pi * BUOY_RADIUS**2

CHAIN_TYPES = {
    "I": (0.078, 3.2),
    "II": (0.105, 7.0),
    "III": (0.120, 12.5),
    "IV": (0.150, 19.5),
    "V": (0.180, 28.12),
}


@dataclass(frozen=True)
class Design:
    chain_type: str
    links: int
    ballast_mass: float

    @property
    def chain_length(self) -> float:
        return self.links * CHAIN_TYPES[self.chain_type][0]

    @property
    def chain_mass_per_m(self) -> float:
        return CHAIN_TYPES[self.chain_type][1]


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def scale(a, factor):
    return (a[0] * factor, a[1] * factor)


def norm(a):
    return math.hypot(a[0], a[1])


def unit(a):
    length = norm(a)
    return (1.0, 0.0) if length < 1e-14 else (a[0] / length, a[1] / length)


def bisect(function, lower, upper, tolerance=1e-9):
    f_lower = function(lower)
    f_upper = function(upper)
    if f_lower * f_upper > 0:
        raise ValueError("Root not bracketed")
    for _ in range(150):
        middle = (lower + upper) / 2
        f_middle = function(middle)
        if abs(f_middle) < 1e-10 or upper - lower < tolerance:
            return middle
        if f_lower * f_middle <= 0:
            upper = middle
        else:
            lower = middle
            f_lower = f_middle
    return (lower + upper) / 2


def member_states(v_top_chain, ballast_mass, draft, wind_speed, current_speed, phi):
    """Solve 3-D horizontal force recursion and member directions by fixed point."""
    wind_dir = (1.0, 0.0)
    current_dir = (math.cos(phi), math.sin(phi))
    wind_force = 0.625 * (2 * (BUOY_HEIGHT - draft)) * wind_speed**2
    buoy_current = 374 * (2 * draft) * current_speed**2
    horizontal = add(scale(wind_dir, wind_force), scale(current_dir, buoy_current))

    # Vertical tensions, ordered from top pipe to barrel.
    barrel_lower_v = v_top_chain + ballast_mass * G
    barrel_upper_v = barrel_lower_v + BARREL_WEIGHT
    pipe_bounds_bottom_up = []
    lower_v = barrel_upper_v
    for _ in range(PIPE_COUNT):
        upper_v = lower_v + PIPE_WEIGHT
        pipe_bounds_bottom_up.append((lower_v, upper_v))
        lower_v = upper_v
    vertical_bounds = list(reversed(pipe_bounds_bottom_up)) + [(barrel_lower_v, barrel_upper_v)]
    dimensions = [(PIPE_DIAMETER, PIPE_LENGTH)] * PIPE_COUNT + [(BARREL_DIAMETER, BARREL_LENGTH)]

    directions = [unit(horizontal)] * 5
    angles = [0.0] * 5
    lower_vectors = []
    for _ in range(100):
        current_horizontal = horizontal
        new_directions = []
        new_angles = []
        new_lower_vectors = []
        for index, ((v_lower, v_upper), (diameter, length)) in enumerate(zip(vertical_bounds, dimensions)):
            old_angle = angles[index]
            old_direction = directions[index]
            # u dot current direction for a cylinder inclined from vertical.
            axis_dot_flow = math.sin(old_angle) * (
                old_direction[0] * current_dir[0] + old_direction[1] * current_dir[1]
            )
            projected_area = diameter * length * math.sqrt(max(0.0, 1.0 - axis_dot_flow**2))
            current_force = 374 * projected_area * current_speed**2
            next_horizontal = add(current_horizontal, scale(current_dir, current_force))
            moment_vector = add(current_horizontal, next_horizontal)
            direction = unit(moment_vector)
            angle = math.atan2(norm(moment_vector), v_lower + v_upper)
            new_directions.append(direction)
            new_angles.append(angle)
            new_lower_vectors.append(next_horizontal)
            current_horizontal = next_horizontal
        change = max(abs(a - b) for a, b in zip(new_angles, angles))
        directions, angles, lower_vectors = new_directions, new_angles, new_lower_vectors
        if change < 1e-12:
            break

    return {
        "wind_force": wind_force,
        "buoy_current_force": buoy_current,
        "chain_horizontal_vector": lower_vectors[-1],
        "angles": angles,
        "directions": directions,
        "vertical_bounds": vertical_bounds,
    }


def equilibrium(design: Design, depth: float, wind_speed: float, current_speed: float, phi: float):
    q = design.chain_mass_per_m * G
    length = design.chain_length

    def state_from_chain(vertical_top):
        buoy_vertical_load = vertical_top + design.ballast_mass * G + BARREL_WEIGHT + PIPE_COUNT * PIPE_WEIGHT
        draft = (BUOY_MASS * G + buoy_vertical_load) / BUOY_DENOMINATOR
        if not 0 < draft < BUOY_HEIGHT:
            raise ValueError("Invalid draft")
        members = member_states(vertical_top, design.ballast_mass, draft, wind_speed, current_speed, phi)
        return draft, members

    def chain_geometry(horizontal, bottom_vertical, chain_length):
        if horizontal < 1e-10:
            return 0.0, chain_length
        top_vertical = bottom_vertical + q * chain_length
        x = horizontal / q * (math.asinh(top_vertical / horizontal) - math.asinh(bottom_vertical / horizontal))
        y = (math.hypot(horizontal, top_vertical) - math.hypot(horizontal, bottom_vertical)) / q
        return x, y

    def member_geometry(members):
        horizontal = (0.0, 0.0)
        vertical = 0.0
        for angle, direction in zip(members["angles"], members["directions"]):
            horizontal = add(horizontal, scale(direction, math.sin(angle)))
            vertical += math.cos(angle)
        return horizontal, vertical

    def grounded_residual(suspended_length):
        vertical_top = q * suspended_length
        draft, members = state_from_chain(vertical_top)
        horizontal_chain = norm(members["chain_horizontal_vector"])
        _, chain_y = chain_geometry(horizontal_chain, 0.0, suspended_length)
        _, member_y = member_geometry(members)
        return draft + chain_y + member_y - depth

    max_test = grounded_residual(length)
    if max_test >= 0:
        suspended = bisect(grounded_residual, 1e-9, length)
        bottom_vertical = 0.0
        chain_state = "partly grounded"
    else:
        suspended = length

        def full_residual(bottom):
            vertical_top = bottom + q * length
            draft, members = state_from_chain(vertical_top)
            horizontal_chain = norm(members["chain_horizontal_vector"])
            _, chain_y = chain_geometry(horizontal_chain, bottom, length)
            _, member_y = member_geometry(members)
            return draft + chain_y + member_y - depth

        upper = 1.0
        while full_residual(upper) < 0:
            upper *= 2
            if upper > 1e7:
                raise ValueError("Cannot bracket full-chain state")
        bottom_vertical = bisect(full_residual, 0.0, upper)
        chain_state = "fully suspended"

    vertical_top = bottom_vertical + q * suspended
    draft, members = state_from_chain(vertical_top)
    chain_vector = members["chain_horizontal_vector"]
    horizontal_chain = norm(chain_vector)
    chain_x, chain_y = chain_geometry(horizontal_chain, bottom_vertical, suspended)
    chain_direction = unit(chain_vector)
    member_xy, member_y = member_geometry(members)
    grounded = length - suspended
    # Grounded chain is taken in the chain-tension direction.
    total_xy = add(scale(chain_direction, grounded + chain_x), member_xy)
    excursion = norm(total_xy)
    anchor_angle = math.degrees(math.atan2(bottom_vertical, horizontal_chain)) if horizontal_chain > 0 else 0.0
    closure = draft + chain_y + member_y
    return {
        "depth_m": depth,
        "wind_speed_m_s": wind_speed,
        "current_speed_m_s": current_speed,
        "wind_current_angle_deg": math.degrees(phi),
        "draft_m": draft,
        "barrel_angle_deg": math.degrees(members["angles"][-1]),
        "pipe_1_angle_deg": math.degrees(members["angles"][0]),
        "pipe_2_angle_deg": math.degrees(members["angles"][1]),
        "pipe_3_angle_deg": math.degrees(members["angles"][2]),
        "pipe_4_angle_deg": math.degrees(members["angles"][3]),
        "anchor_angle_deg": anchor_angle,
        "excursion_radius_m": excursion,
        "chain_state": chain_state,
        "suspended_chain_m": suspended,
        "grounded_chain_m": grounded,
        "chain_horizontal_span_m": grounded + chain_x,
        "chain_vertical_rise_m": chain_y,
        "chain_horizontal_tension_n": horizontal_chain,
        "anchor_vertical_tension_n": bottom_vertical,
        "wind_force_n": members["wind_force"],
        "buoy_current_force_n": members["buoy_current_force"],
        "closure_error_m": closure - depth,
    }


def worst_screen(design):
    results = [equilibrium(design, depth, 36.0, 1.5, 0.0) for depth in (16.0, 20.0)]
    return results


def minimum_ballast(chain_type, links, lower=200.0, upper=4000.0):
    def feasible(mass):
        design = Design(chain_type, links, mass)
        try:
            results = worst_screen(design)
        except ValueError:
            return False
        return all(r["barrel_angle_deg"] <= 5.0 and r["anchor_angle_deg"] <= 16.0 for r in results)

    if not feasible(upper):
        return None
    if feasible(lower):
        return lower
    for _ in range(45):
        middle = (lower + upper) / 2
        if feasible(middle):
            upper = middle
        else:
            lower = middle
    return upper


def scenario_grid(design):
    rows = []
    for depth in (16.0, 18.0, 20.0):
        for wind in (12.0, 24.0, 36.0):
            for current in (0.0, 0.5, 1.0, 1.5):
                for angle in (0.0, 45.0, 90.0, 135.0, 180.0):
                    rows.append(equilibrium(design, depth, wind, current, math.radians(angle)))
    return rows


def main():
    out = Path(__file__).resolve().parents[1] / "results"
    out.mkdir(parents=True, exist_ok=True)

    candidates = []
    # Search practical lengths from 18 to 32 m, in whole-link increments; use a
    # coarse 0.5 m band for screening to keep the mixed search reproducible.
    for chain_type, (link_length, _) in CHAIN_TYPES.items():
        min_links = math.ceil(18.0 / link_length)
        max_links = math.floor(32.0 / link_length)
        step = max(1, round(0.5 / link_length))
        for links in range(min_links, max_links + 1, step):
            mass = minimum_ballast(chain_type, links)
            if mass is None:
                continue
            for extra_ballast in (0.0, 200.0, 400.0):
                design = Design(chain_type, links, mass + extra_ballast)
                try:
                    screen = worst_screen(design)
                except ValueError:
                    continue
                candidates.append({
                    "chain_type": chain_type,
                    "links": links,
                    "chain_length_m": design.chain_length,
                    "ballast_mass_kg": design.ballast_mass,
                    "ballast_above_minimum_kg": extra_ballast,
                    "worst_draft_m": max(r["draft_m"] for r in screen),
                    "worst_excursion_m": max(r["excursion_radius_m"] for r in screen),
                    "worst_barrel_angle_deg": max(r["barrel_angle_deg"] for r in screen),
                    "worst_anchor_angle_deg": max(r["anchor_angle_deg"] for r in screen),
                })

    if not candidates:
        raise RuntimeError("No feasible designs found")

    # Pareto filter on draft, excursion and barrel angle.
    objectives = ("worst_draft_m", "worst_excursion_m", "worst_barrel_angle_deg")
    pareto = []
    for candidate in candidates:
        dominated = False
        for other in candidates:
            if other is candidate:
                continue
            no_worse = all(other[key] <= candidate[key] for key in objectives)
            strictly_better = any(other[key] < candidate[key] for key in objectives)
            if no_worse and strictly_better:
                dominated = True
                break
        if not dominated:
            pareto.append(candidate)

    mins = {key: min(c[key] for c in pareto) for key in objectives}
    maxs = {key: max(c[key] for c in pareto) for key in objectives}
    for candidate in pareto:
        normalized = []
        for key in objectives:
            span = maxs[key] - mins[key]
            normalized.append(0.0 if span == 0 else (candidate[key] - mins[key]) / span)
        candidate["ideal_distance"] = math.sqrt(sum(value**2 for value in normalized))
    selected = min(pareto, key=lambda c: c["ideal_distance"])
    recommended_mass = math.ceil(selected["ballast_mass_kg"] / 50.0) * 50.0
    selected_design = Design(selected["chain_type"], int(selected["links"]), recommended_mass)
    scenarios = scenario_grid(selected_design)

    with (out / "design-candidates.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=candidates[0].keys())
        writer.writeheader(); writer.writerows(candidates)
    with (out / "pareto-designs.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=pareto[0].keys())
        writer.writeheader(); writer.writerows(pareto)
    with (out / "selected-design-scenarios.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=scenarios[0].keys())
        writer.writeheader(); writer.writerows(scenarios)

    design_summary = {
        "chain_type": selected_design.chain_type,
        "links": selected_design.links,
        "chain_length_m": selected_design.chain_length,
        "pareto_ballast_mass_kg": selected["ballast_mass_kg"],
        "recommended_ballast_mass_kg": selected_design.ballast_mass,
        "worst_draft_m": max(r["draft_m"] for r in scenarios),
        "worst_excursion_m": max(r["excursion_radius_m"] for r in scenarios),
        "worst_barrel_angle_deg": max(r["barrel_angle_deg"] for r in scenarios),
        "worst_anchor_angle_deg": max(r["anchor_angle_deg"] for r in scenarios),
    }
    with (out / "selected-design-summary.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=design_summary.keys())
        writer.writeheader(); writer.writerow(design_summary)

    print("candidate_count", len(candidates))
    print("pareto_count", len(pareto))
    print("selected", selected)
    print("recommended", design_summary)
    for metric in ("draft_m", "excursion_radius_m", "barrel_angle_deg", "anchor_angle_deg"):
        worst = max(scenarios, key=lambda r: r[metric])
        print("worst", metric, worst[metric], {k: worst[k] for k in ("depth_m", "wind_speed_m_s", "current_speed_m_s", "wind_current_angle_deg")})


if __name__ == "__main__":
    main()
