#!/usr/bin/env python3
"""Close-packed staggered-ring geometry for the second Q2 route."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree


SITE_RADIUS = 350.0
EXCLUSION_RADIUS = 100.0


@dataclass(frozen=True)
class HexDesign:
    tower_x: float
    tower_y: float
    width: float
    height: float
    center_z: float
    first_radius: float
    radial_ratio: float
    tangential_clearance: float
    max_radius: float
    phase: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def minimum_spacing(self) -> float:
        return self.width + 5.0

    @property
    def radial_spacing(self) -> float:
        return self.radial_ratio * self.minimum_spacing

    @property
    def tangential_spacing(self) -> float:
        return self.minimum_spacing + self.tangential_clearance


def _greedy_distance_filter(points: np.ndarray, minimum_spacing: float) -> np.ndarray:
    cell_size = minimum_spacing
    buckets: dict[tuple[int, int], list[int]] = {}
    accepted: list[np.ndarray] = []
    threshold2 = (minimum_spacing - 1.0e-8) ** 2
    for point in points:
        cell = (math.floor(point[0] / cell_size), math.floor(point[1] / cell_size))
        conflict = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for index in buckets.get((cell[0] + dx, cell[1] + dy), []):
                    delta = accepted[index] - point
                    if float(delta @ delta) < threshold2:
                        conflict = True
                        break
                if conflict:
                    break
            if conflict:
                break
        if not conflict:
            index = len(accepted)
            accepted.append(point)
            buckets.setdefault(cell, []).append(index)
    return np.asarray(accepted, dtype=float)


def generate_hex_layout(design: HexDesign, return_raw: bool = False):
    radii = np.arange(
        max(EXCLUSION_RADIUS, design.first_radius),
        design.max_radius + 0.5 * design.radial_spacing,
        design.radial_spacing,
    )
    rings = []
    for k, radius in enumerate(radii):
        pair_radius = radii[2 * (k // 2)]
        ratio = np.clip(design.tangential_spacing / (2.0 * pair_radius), 0.0, 1.0)
        count = max(3, int(math.floor(math.pi / math.asin(ratio))))
        offset = design.phase + (math.pi / count if k % 2 else 0.0)
        angles = offset + 2.0 * math.pi * np.arange(count) / count
        rings.append(
            np.column_stack(
                [
                    design.tower_x + radius * np.cos(angles),
                    design.tower_y + radius * np.sin(angles),
                ]
            )
        )
    raw = np.vstack(rings)
    tower_distance = np.hypot(raw[:, 0] - design.tower_x, raw[:, 1] - design.tower_y)
    site_distance = np.hypot(raw[:, 0], raw[:, 1])
    bounded = raw[(tower_distance >= EXCLUSION_RADIUS - 1.0e-8) & (site_distance <= SITE_RADIUS + 1.0e-8)]
    accepted = _greedy_distance_filter(bounded, design.minimum_spacing)
    if return_raw:
        return raw, bounded, accepted
    return accepted


def hex_layout_checks(design: HexDesign, xy: np.ndarray) -> dict[str, float | bool | int]:
    distances, _ = cKDTree(xy).query(xy, k=2)
    nearest = float(np.min(distances[:, 1]))
    return {
        "mirror_count": len(xy),
        "minimum_center_distance_m": nearest,
        "required_minimum_center_distance_m": design.minimum_spacing,
        "spacing_constraint_satisfied": nearest + 1.0e-7 >= design.minimum_spacing,
        "maximum_site_radius_m": float(np.max(np.hypot(xy[:, 0], xy[:, 1]))),
        "minimum_tower_distance_m": float(np.min(np.hypot(xy[:, 0] - design.tower_x, xy[:, 1] - design.tower_y))),
    }
