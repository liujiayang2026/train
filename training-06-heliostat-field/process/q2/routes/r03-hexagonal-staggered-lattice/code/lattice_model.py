#!/usr/bin/env python3
"""Analytic hexagonal staggered lattice for heliostat centers."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree


@dataclass(frozen=True)
class LatticeDesign:
    tower_x: float
    tower_y: float
    width: float
    height: float
    center_z: float
    clearance: float
    phase: float

    @property
    def spacing(self) -> float:
        return self.width + 5.0 + self.clearance

    @property
    def area(self) -> float:
        return self.width * self.height


def generate_lattice(design: LatticeDesign, return_raw: bool = False):
    spacing = design.spacing
    row_spacing = math.sqrt(3.0) * spacing / 2.0
    extent = 350.0 + math.hypot(design.tower_x, design.tower_y) + spacing
    row_limit = int(math.ceil(extent / row_spacing))
    column_limit = int(math.ceil(extent / spacing))
    parts = []
    for row in range(-row_limit, row_limit + 1):
        columns = np.arange(-column_limit, column_limit + 1)
        x = columns * spacing + (0.5 * spacing if row % 2 else 0.0)
        y = np.full_like(x, row * row_spacing, dtype=float)
        parts.append(np.column_stack([x, y]))
    local = np.vstack(parts)
    cosine = math.cos(design.phase)
    sine = math.sin(design.phase)
    rotation = np.array([[cosine, -sine], [sine, cosine]])
    raw = local @ rotation.T + np.array([design.tower_x, design.tower_y])
    site = np.hypot(raw[:, 0], raw[:, 1]) <= 350.0 + 1.0e-8
    exclusion = np.hypot(raw[:, 0] - design.tower_x, raw[:, 1] - design.tower_y) >= 100.0 - 1.0e-8
    accepted = raw[site & exclusion]
    return (raw, accepted) if return_raw else accepted


def lattice_checks(design: LatticeDesign, xy: np.ndarray) -> dict[str, float | int | bool]:
    distances, _ = cKDTree(xy).query(xy, k=2)
    nearest = float(np.min(distances[:, 1]))
    max_site = float(np.max(np.hypot(xy[:, 0], xy[:, 1])))
    min_tower = float(np.min(np.hypot(xy[:, 0] - design.tower_x, xy[:, 1] - design.tower_y)))
    return {
        "mirror_count": len(xy),
        "minimum_center_distance_m": nearest,
        "required_minimum_center_distance_m": design.width + 5.0,
        "spacing_constraint_satisfied": nearest + 1.0e-7 >= design.width + 5.0,
        "maximum_site_radius_m": max_site,
        "minimum_tower_distance_m": min_tower,
        "site_constraint_satisfied": max_site <= 350.0 + 1.0e-7,
        "tower_exclusion_satisfied": min_tower >= 100.0 - 1.0e-7,
    }
