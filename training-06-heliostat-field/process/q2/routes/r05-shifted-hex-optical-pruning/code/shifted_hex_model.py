#!/usr/bin/env python3
"""Shifted and rotated hexagonal heliostat lattice."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class ShiftedHexDesign:
    tower_x: float
    tower_y: float
    width: float
    height: float
    center_z: float
    clearance: float
    rotation: float
    offset_u: float
    offset_v: float

    @property
    def spacing(self) -> float:
        return self.width + 5.0 + self.clearance

    @property
    def area(self) -> float:
        return self.width * self.height


def generate_layout(design: ShiftedHexDesign) -> np.ndarray:
    d = design.spacing
    row_spacing = math.sqrt(3.0) * d / 2.0
    extent = 350.0 + math.hypot(design.tower_x, design.tower_y) + 2.0 * d
    row_limit = int(math.ceil(extent / row_spacing)) + 2
    column_limit = int(math.ceil(extent / d)) + 2
    parts = []
    for row in range(-row_limit, row_limit + 1):
        columns = np.arange(-column_limit, column_limit + 1)
        x = columns * d + (0.5 * d if row % 2 else 0.0) + design.offset_u * d
        y = np.full_like(x, (row + design.offset_v) * row_spacing, dtype=float)
        parts.append(np.column_stack([x, y]))
    local = np.vstack(parts)
    cosine = math.cos(design.rotation)
    sine = math.sin(design.rotation)
    rotation = np.array([[cosine, -sine], [sine, cosine]])
    raw = local @ rotation.T + np.array([design.tower_x, design.tower_y])
    site = np.hypot(raw[:, 0], raw[:, 1]) <= 350.0 + 1.0e-9
    exclusion = np.hypot(raw[:, 0] - design.tower_x, raw[:, 1] - design.tower_y) >= 100.0 - 1.0e-9
    accepted = raw[site & exclusion]
    return accepted[np.lexsort((accepted[:, 0], accepted[:, 1]))]


def geometry_checks(design: ShiftedHexDesign, xy: np.ndarray) -> dict[str, float | int | bool]:
    distances, _ = cKDTree(xy).query(xy, k=2)
    nearest = float(np.min(distances[:, 1]))
    max_site = float(np.max(np.hypot(xy[:, 0], xy[:, 1])))
    min_tower = float(np.min(np.hypot(xy[:, 0] - design.tower_x, xy[:, 1] - design.tower_y)))
    return {
        "mirror_count": int(len(xy)),
        "minimum_center_distance_m": nearest,
        "required_problem_distance_m": design.width + 5.0,
        "configured_safe_distance_m": design.spacing,
        "spacing_constraint_satisfied": bool(nearest + 1.0e-7 >= design.spacing),
        "maximum_site_radius_m": max_site,
        "site_constraint_satisfied": bool(max_site <= 350.0 + 1.0e-7),
        "minimum_tower_distance_m": min_tower,
        "tower_exclusion_satisfied": bool(min_tower >= 100.0 - 1.0e-7),
    }


def no_shadow_priority(design: ShiftedHexDesign, xy: np.ndarray, states) -> np.ndarray:
    centers = np.column_stack([xy, np.full(len(xy), design.center_z)])
    receiver = np.array([design.tower_x, design.tower_y, 80.0])
    target = receiver - centers
    distance = np.linalg.norm(target, axis=1)
    target /= distance[:, None]
    eta_at = 0.99321 - 0.0001176 * distance + 1.97e-8 * distance**2
    blur = 0.70 * distance * math.tan(math.radians(0.266))
    eta_trunc = np.minimum(1.0, 7.0 / (design.width + 2.0 * blur)) * np.minimum(
        1.0, 8.0 / (design.height + 2.0 * blur)
    )
    score = np.zeros(len(xy))
    for _, _, _, sun, dni in states:
        normals = target + sun
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        score += dni * 0.92 * (normals @ sun) * eta_at * eta_trunc
    return score / len(states)


def local_improvement(design: ShiftedHexDesign, xy: np.ndarray, mirror_scores: np.ndarray, states, limit: int = 60):
    result = np.array(xy, copy=True)
    moves = 0
    for index in np.argsort(mirror_scores)[:limit]:
        current = result[index]
        relative = current - np.array([design.tower_x, design.tower_y])
        radius = float(np.linalg.norm(relative))
        if radius <= 1.0e-9:
            continue
        radial = relative / radius
        tangential = np.array([-radial[1], radial[0]])
        proposals = [current]
        for delta in (-1.0, -0.5, 0.5, 1.0):
            proposals.extend([current + delta * radial, current + delta * tangential])
        others = np.delete(result, index, axis=0)
        tree = cKDTree(others)
        feasible = []
        for point in proposals:
            if np.hypot(point[0], point[1]) > 350.0:
                continue
            if np.hypot(point[0] - design.tower_x, point[1] - design.tower_y) < 100.0:
                continue
            if tree.query(point, k=1)[0] + 1.0e-9 < design.spacing:
                continue
            feasible.append(point)
        if len(feasible) <= 1:
            continue
        feasible = np.asarray(feasible)
        scores = no_shadow_priority(design, feasible, states)
        best = int(np.argmax(scores))
        current_score = float(no_shadow_priority(design, current[None, :], states)[0])
        if scores[best] > current_score + 1.0e-7 and np.linalg.norm(feasible[best] - current) > 1.0e-9:
            result[index] = feasible[best]
            moves += 1
    return result, moves
