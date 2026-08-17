#!/usr/bin/env python3
"""Variable-density radial-staggered candidate generation and selection."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree


SITE_RADIUS = 350.0
EXCLUSION_RADIUS = 100.0


@dataclass(frozen=True)
class RadialDesign:
    tower_x: float
    tower_y: float
    width: float
    height: float
    center_z: float
    clearance: float
    zone_boundaries: tuple[float, float]
    radial_factors: tuple[float, float, float]
    tangential_factors: tuple[float, float, float]
    phase: float = 0.0
    radial_offset_fraction: float = 0.10

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def minimum_spacing(self) -> float:
        return self.width + 5.0

    @property
    def safe_spacing(self) -> float:
        return self.minimum_spacing + self.clearance


def optical_priority(
    design: RadialDesign,
    xy: np.ndarray,
    states: list[tuple[int, float, float, np.ndarray, float]],
) -> np.ndarray:
    """Return a no-shadow annual optical score used only for conflict ordering."""
    centers = np.column_stack([xy, np.full(len(xy), design.center_z)])
    receiver = np.array([design.tower_x, design.tower_y, 80.0])
    target = receiver - centers
    distance = np.linalg.norm(target, axis=1)
    target /= distance[:, None]
    eta_at = 0.99321 - 0.0001176 * distance + 1.97e-8 * distance**2
    solar_radius = math.radians(0.266)
    blur = 0.70 * distance * math.tan(solar_radius)
    eta_trunc = np.minimum(1.0, 7.0 / (design.width + 2.0 * blur)) * np.minimum(
        1.0, 8.0 / (design.height + 2.0 * blur)
    )
    score = np.zeros(len(xy), dtype=float)
    dni_sum = 0.0
    for _, _, _, sun, dni in states:
        normals = target + sun
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        eta_cos = normals @ sun
        score += dni * 0.92 * eta_cos * eta_at * eta_trunc
        dni_sum += dni
    return score / max(dni_sum, 1.0e-12)


def generate_candidates(
    design: RadialDesign,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate four-ring staggered groups with safe count transitions."""
    max_radius = SITE_RADIUS + math.hypot(design.tower_x, design.tower_y)
    bounds = (EXCLUSION_RADIUS, *design.zone_boundaries, max_radius + design.safe_spacing)
    radius = EXCLUSION_RADIUS + design.clearance + design.radial_offset_fraction * design.safe_spacing
    ring_index = 0
    group_index = 0
    points: list[np.ndarray] = []
    zones: list[np.ndarray] = []
    rings: list[np.ndarray] = []
    while radius <= max_radius + 1.0e-9:
        zone = min(2, int(radius >= bounds[1]) + int(radius >= bounds[2]))
        tangential = design.tangential_factors[zone] * design.safe_spacing
        chord_limit = int(math.floor(math.pi / math.asin(min(1.0, design.safe_spacing / (2.0 * radius)))))
        desired_count = max(6, min(chord_limit, int(math.floor(2.0 * math.pi * radius / tangential))))
        angle_step = 2.0 * math.pi / desired_count
        group_phase = design.phase + (group_index % 2) * angle_step / 4.0
        internal_spacing = max(math.sqrt(3.0) / 2.0, design.radial_factors[zone]) * design.safe_spacing
        last_radius = radius
        for local_ring in range(4):
            ring_radius = radius + local_ring * internal_spacing
            if ring_radius > max_radius + 1.0e-9:
                break
            offset = group_phase + (math.pi / desired_count if local_ring % 2 else 0.0)
            angles = offset + angle_step * np.arange(desired_count)
            ring_xy = np.column_stack(
                [
                    design.tower_x + ring_radius * np.cos(angles),
                    design.tower_y + ring_radius * np.sin(angles),
                ]
            )
            site_mask = np.hypot(ring_xy[:, 0], ring_xy[:, 1]) <= SITE_RADIUS + 1.0e-9
            ring_xy = ring_xy[site_mask]
            if len(ring_xy):
                points.append(ring_xy)
                zones.append(np.full(len(ring_xy), zone, dtype=int))
                rings.append(np.full(len(ring_xy), ring_index, dtype=int))
            last_radius = ring_radius
            ring_index += 1
        radius = last_radius + max(1.0, design.radial_factors[zone]) * design.safe_spacing
        group_index += 1
    if not points:
        return np.empty((0, 2)), np.empty(0, dtype=int), np.empty(0, dtype=int)
    return np.vstack(points), np.concatenate(zones), np.concatenate(rings)


def weighted_spacing_selection(
    xy: np.ndarray,
    weights: np.ndarray,
    minimum_distance: float,
) -> np.ndarray:
    """Greedy weighted independent-set selection using a spatial hash."""
    if len(xy) == 0:
        return np.empty(0, dtype=int)
    cell_size = minimum_distance
    order = np.lexsort((np.arange(len(xy)), -weights))
    buckets: dict[tuple[int, int], list[int]] = {}
    accepted: list[int] = []
    threshold_sq = (minimum_distance - 1.0e-9) ** 2
    for index in order:
        point = xy[index]
        cell = tuple(np.floor(point / cell_size).astype(int))
        conflict = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in buckets.get((cell[0] + dx, cell[1] + dy), []):
                    if float(np.sum((xy[other] - point) ** 2)) < threshold_sq:
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                break
        if not conflict:
            accepted.append(int(index))
            buckets.setdefault(cell, []).append(int(index))
    return np.asarray(accepted, dtype=int)


def generate_layout(
    design: RadialDesign,
    states: list[tuple[int, float, float, np.ndarray, float]],
    return_stages: bool = False,
):
    candidates, zones, rings = generate_candidates(design)
    weights = optical_priority(design, candidates, states)
    selected = weighted_spacing_selection(candidates, weights, design.safe_spacing)
    order = np.lexsort((candidates[selected, 0], candidates[selected, 1]))
    selected = selected[order]
    if return_stages:
        return {
            "candidates": candidates,
            "candidate_zones": zones,
            "candidate_rings": rings,
            "candidate_weights": weights,
            "selected_indices": selected,
            "xy": candidates[selected],
            "zones": zones[selected],
            "rings": rings[selected],
        }
    return candidates[selected]


def geometry_checks(design: RadialDesign, xy: np.ndarray) -> dict[str, float | int | bool]:
    if len(xy) >= 2:
        distances, _ = cKDTree(xy).query(xy, k=2)
        nearest = float(np.min(distances[:, 1]))
    else:
        nearest = float("nan")
    site_radius = float(np.max(np.hypot(xy[:, 0], xy[:, 1]))) if len(xy) else float("nan")
    tower_radius = (
        float(np.min(np.hypot(xy[:, 0] - design.tower_x, xy[:, 1] - design.tower_y)))
        if len(xy)
        else float("nan")
    )
    return {
        "mirror_count": int(len(xy)),
        "minimum_center_distance_m": nearest,
        "required_problem_distance_m": design.minimum_spacing,
        "configured_safe_distance_m": design.safe_spacing,
        "spacing_constraint_satisfied": bool(nearest + 1.0e-7 >= design.safe_spacing),
        "maximum_site_radius_m": site_radius,
        "site_constraint_satisfied": bool(site_radius <= SITE_RADIUS + 1.0e-7),
        "minimum_tower_distance_m": tower_radius,
        "tower_exclusion_satisfied": bool(tower_radius >= EXCLUSION_RADIUS - 1.0e-7),
    }


def local_coordinate_improvement(
    design: RadialDesign,
    xy: np.ndarray,
    mirror_scores: np.ndarray,
    states: list[tuple[int, float, float, np.ndarray, float]],
    maximum_mirrors: int = 80,
) -> tuple[np.ndarray, int]:
    """Move a few low-score mirrors into nearby feasible positions."""
    result = np.array(xy, copy=True)
    order = np.argsort(mirror_scores)[:maximum_mirrors]
    accepted_moves = 0
    offsets = (-1.0, -0.5, 0.5, 1.0)
    for index in order:
        current = result[index]
        relative = current - np.array([design.tower_x, design.tower_y])
        radius = float(np.linalg.norm(relative))
        if radius <= 1.0e-9:
            continue
        radial = relative / radius
        tangential = np.array([-radial[1], radial[0]])
        candidate_points = [current]
        for delta in offsets:
            candidate_points.append(current + delta * radial)
            candidate_points.append(current + delta * tangential)
        candidate_array = np.asarray(candidate_points)
        valid = []
        others = np.delete(result, index, axis=0)
        tree = cKDTree(others)
        for candidate in candidate_array:
            site_ok = np.hypot(candidate[0], candidate[1]) <= SITE_RADIUS
            tower_ok = np.hypot(candidate[0] - design.tower_x, candidate[1] - design.tower_y) >= EXCLUSION_RADIUS
            spacing_ok = tree.query(candidate, k=1)[0] + 1.0e-9 >= design.safe_spacing
            if site_ok and tower_ok and spacing_ok:
                valid.append(candidate)
        if len(valid) <= 1:
            continue
        valid_array = np.asarray(valid)
        scores = optical_priority(design, valid_array, states)
        best = int(np.argmax(scores))
        current_score = float(optical_priority(design, current[None, :], states)[0])
        if scores[best] > current_score + 1.0e-7 and np.linalg.norm(valid_array[best] - current) > 1.0e-9:
            result[index] = valid_array[best]
            accepted_moves += 1
    return result, accepted_moves
