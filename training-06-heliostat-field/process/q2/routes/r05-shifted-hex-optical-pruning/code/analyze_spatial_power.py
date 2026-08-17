#!/usr/bin/env python3
"""Recompute per-mirror annual power and summarize it by polar site zones."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Wedge
import numpy as np


HERE = Path(__file__).resolve()
ROUTES = HERE.parents[2]
sys.path.insert(0, str(ROUTES / "r01-common-size-field-optimization" / "code"))

from q2_model import Design, all_states, evaluate_field


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-run", required=True, type=Path)
    parser.add_argument("--output-run", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--seed", type=int, default=202308)
    parser.add_argument("--neighbor-radius", type=float, default=70.0)
    parser.add_argument("--radial-bins", type=int, default=5)
    parser.add_argument("--sector-count", type=int, default=12)
    return parser.parse_args()


def make_logger(output_run: Path) -> logging.Logger:
    logger = logging.getLogger("spatial-power-zones")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(output_run / "logs" / "run.log", encoding="utf-8"),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compass_direction(angle_deg: float) -> str:
    names = ["东", "东北", "北", "西北", "西", "西南", "南", "东南"]
    return names[int(((angle_deg + 22.5) % 360.0) // 45.0)]


def reconstruct_design(raw: dict) -> Design:
    width = float(raw["width"])
    clearance = float(raw["clearance"])
    spacing = width + 5.0 + clearance
    return Design(
        float(raw["tower_x"]),
        float(raw["tower_y"]),
        width,
        float(raw["height"]),
        float(raw["center_z"]),
        100.0,
        math.sqrt(3.0) * spacing / 2.0 - (width + 5.0),
        spacing - (width + 5.0),
        520.0,
        float(raw["rotation"]),
    )


def exact_per_mirror_power(
    design: Design,
    xy: np.ndarray,
    samples: int,
    seed: int,
    neighbor_radius: float,
    logger: logging.Logger,
) -> np.ndarray:
    states = all_states()
    annual_power_kw = np.zeros(len(xy), dtype=float)
    for index, state in enumerate(states, start=1):
        _, mirror_metrics = evaluate_field(
            design,
            xy,
            samples,
            seed,
            neighbor_radius,
            states=[state],
            store_per_mirror=True,
        )
        dni = float(state[4])
        annual_power_kw += dni * design.area * mirror_metrics[:, 0] / len(states)
        if index % 5 == 0 or index == len(states):
            logger.info("Per-mirror power completed state %d/%d", index, len(states))
    return annual_power_kw


def build_zone_rows(
    xy: np.ndarray,
    mirror_power_kw: np.ndarray,
    mirror_area_m2: float,
    radial_bins: int,
    sector_count: int,
) -> tuple[list[dict], np.ndarray, np.ndarray, float]:
    radial_edges = np.linspace(0.0, 350.0, radial_bins + 1)
    sector_width = 360.0 / sector_count
    radius = np.hypot(xy[:, 0], xy[:, 1])
    angle = (np.degrees(np.arctan2(xy[:, 1], xy[:, 0])) + 360.0) % 360.0
    radial_index = np.clip(np.digitize(radius, radial_edges, right=False) - 1, 0, radial_bins - 1)
    sector_index = np.clip((angle / sector_width).astype(int), 0, sector_count - 1)
    average_values = []
    for ring in range(radial_bins):
        for sector in range(sector_count):
            mask = (radial_index == ring) & (sector_index == sector)
            if int(np.sum(mask)) >= 10:
                average_values.append(float(np.mean(mirror_power_kw[mask])))
    low_threshold = float(np.quantile(average_values, 0.25))
    field_average = float(np.mean(mirror_power_kw))
    field_total = float(np.sum(mirror_power_kw))
    rows = []
    for ring in range(radial_bins):
        for sector in range(sector_count):
            mask = (radial_index == ring) & (sector_index == sector)
            count = int(np.sum(mask))
            total = float(np.sum(mirror_power_kw[mask]))
            average = float(np.mean(mirror_power_kw[mask])) if count else float("nan")
            center_angle = (sector + 0.5) * sector_width
            rows.append(
                {
                    "zone_id": f"R{ring + 1}-S{sector + 1:02d}",
                    "radial_inner_m": float(radial_edges[ring]),
                    "radial_outer_m": float(radial_edges[ring + 1]),
                    "azimuth_start_deg": float(sector * sector_width),
                    "azimuth_end_deg": float((sector + 1) * sector_width),
                    "direction": compass_direction(center_angle),
                    "mirror_count": count,
                    "total_power_kw": total,
                    "avg_power_per_mirror_kw": average,
                    "avg_unit_area_power_kw_m2": average / mirror_area_m2 if count else float("nan"),
                    "field_power_share_pct": 100.0 * total / field_total,
                    "relative_to_field_avg_pct": 100.0 * average / field_average if count else float("nan"),
                    "is_low_power_zone": bool(count >= 10 and average <= low_threshold),
                }
            )
    return rows, radial_index, sector_index, low_threshold


def draw_site_context(ax, design: Design) -> None:
    ax.add_patch(plt.Circle((0, 0), 350, fill=False, color="#202020", linewidth=1.2))
    ax.add_patch(
        plt.Circle(
            (design.tower_x, design.tower_y),
            100,
            fill=False,
            color="#545454",
            linestyle="--",
            linewidth=0.9,
        )
    )
    ax.scatter([design.tower_x], [design.tower_y], marker="^", s=65, color="#111111", zorder=6)
    ax.set_aspect("equal")
    ax.set_xlim(-370, 370)
    ax.set_ylim(-370, 370)
    ax.set_xlabel("东向 x / m")
    ax.set_ylabel("北向 y / m")


def make_figures(
    output_run: Path,
    design: Design,
    xy: np.ndarray,
    mirror_power_kw: np.ndarray,
    zone_rows: list[dict],
    radial_bins: int,
    sector_count: int,
    low_threshold: float,
) -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 10,
        }
    )
    unit_power = mirror_power_kw / design.area
    norm = colors.Normalize(vmin=float(np.quantile(unit_power, 0.02)), vmax=float(np.quantile(unit_power, 0.98)))

    fig, ax = plt.subplots(figsize=(8.4, 7.2), constrained_layout=True)
    scatter = ax.scatter(xy[:, 0], xy[:, 1], c=unit_power, cmap="RdYlGn", norm=norm, s=10, linewidths=0)
    draw_site_context(ax, design)
    ax.set_title("逐镜年平均单位面积功率分布（256 光线）")
    colorbar = fig.colorbar(scatter, ax=ax, shrink=0.82)
    colorbar.set_label("单位镜面面积功率 / (kW/m²)")
    fig.savefig(output_run / "figures" / "fig01-mirror-power-map.png", dpi=220)
    plt.close(fig)

    occupied = [row for row in zone_rows if row["mirror_count"] > 0]
    zone_values = np.asarray([row["avg_unit_area_power_kw_m2"] for row in occupied])
    zone_norm = colors.Normalize(vmin=float(np.min(zone_values)), vmax=float(np.max(zone_values)))
    cmap = plt.get_cmap("RdYlGn")
    fig, ax = plt.subplots(figsize=(8.7, 7.5), constrained_layout=True)
    for row in zone_rows:
        value = row["avg_unit_area_power_kw_m2"]
        facecolor = "#eeeeee" if row["mirror_count"] == 0 else cmap(zone_norm(value))
        edgecolor = "#b42318" if row["is_low_power_zone"] else "white"
        linewidth = 1.8 if row["is_low_power_zone"] else 0.65
        wedge = Wedge(
            (0, 0),
            row["radial_outer_m"],
            row["azimuth_start_deg"],
            row["azimuth_end_deg"],
            width=row["radial_outer_m"] - row["radial_inner_m"],
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
        )
        ax.add_patch(wedge)
        if row["mirror_count"] > 0 and row["radial_inner_m"] >= 70.0:
            radius = 0.5 * (row["radial_inner_m"] + row["radial_outer_m"])
            angle = math.radians(0.5 * (row["azimuth_start_deg"] + row["azimuth_end_deg"]))
            ax.text(
                radius * math.cos(angle),
                radius * math.sin(angle),
                f"{row['avg_unit_area_power_kw_m2']:.3f}",
                ha="center",
                va="center",
                fontsize=6.4,
                color="#111111",
            )
    draw_site_context(ax, design)
    ax.set_title("60 分区平均单位面积功率（红框为后 25% 低功率区）")
    scalar = plt.cm.ScalarMappable(norm=zone_norm, cmap=cmap)
    scalar.set_array([])
    colorbar = fig.colorbar(scalar, ax=ax, shrink=0.82)
    colorbar.set_label("分区平均单位面积功率 / (kW/m²)")
    fig.savefig(output_run / "figures" / "fig02-zone-power-heatmap.png", dpi=220)
    plt.close(fig)

    low_rows = sorted(
        [row for row in zone_rows if row["is_low_power_zone"]],
        key=lambda row: row["avg_power_per_mirror_kw"],
    )
    fig, (map_ax, bar_ax) = plt.subplots(1, 2, figsize=(13.2, 6.2), constrained_layout=True)
    for row in zone_rows:
        is_low = row["is_low_power_zone"]
        facecolor = "#d95f4f" if is_low else "#e4e7e5"
        map_ax.add_patch(
            Wedge(
                (0, 0),
                row["radial_outer_m"],
                row["azimuth_start_deg"],
                row["azimuth_end_deg"],
                width=row["radial_outer_m"] - row["radial_inner_m"],
                facecolor=facecolor,
                edgecolor="white",
                linewidth=0.7,
            )
        )
    map_ax.scatter(xy[:, 0], xy[:, 1], s=1.8, color="#222222", alpha=0.45)
    draw_site_context(map_ax, design)
    map_ax.set_title("低功率分区空间位置")
    labels = [f"{row['zone_id']} {row['direction']}" for row in low_rows]
    values = [row["avg_unit_area_power_kw_m2"] for row in low_rows]
    positions = np.arange(len(low_rows))
    bar_ax.barh(positions, values, color="#d95f4f")
    bar_ax.set_yticks(positions, labels)
    bar_ax.invert_yaxis()
    bar_ax.axvline(float(np.mean(unit_power)), color="#222222", linestyle="--", linewidth=1.2, label="全场平均")
    bar_ax.axvline(low_threshold / design.area, color="#b42318", linestyle=":", linewidth=1.2, label="后25%阈值")
    bar_ax.set_xlabel("分区平均单位面积功率 / (kW/m²)")
    bar_ax.set_title("相对低功率区域排序")
    bar_ax.grid(True, axis="x", linewidth=0.5, alpha=0.5)
    bar_ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0)
    fig.savefig(output_run / "figures" / "fig03-low-power-zones.png", dpi=220)
    plt.close(fig)


def write_summary(
    output_run: Path,
    zone_rows: list[dict],
    mirror_power_kw: np.ndarray,
    design: Design,
    low_threshold: float,
) -> None:
    low_rows = sorted(
        [row for row in zone_rows if row["is_low_power_zone"]],
        key=lambda row: row["avg_power_per_mirror_kw"],
    )
    lines = [
        "# 镜场空间功率分区分析",
        "",
        "- 场地圆按 5 个 70 m 环带和 12 个 30° 扇区划分，共 60 区。",
        "- 方位角从东向逆时针计算：0° 为东、90° 为北、180° 为西、270° 为南。",
        "- 每面镜功率为 60 个时点、256 条锥形太阳光线计算得到的 DNI 加权年平均热功率。",
        "- 低功率区定义为镜数不少于 10 且区域单镜平均功率位于全部有效分区后 25%。",
        "",
        "## 全场核对",
        "",
        f"- 逐镜功率之和：{np.sum(mirror_power_kw) / 1000.0:.9f} MW",
        f"- 全场平均单镜功率：{np.mean(mirror_power_kw):.6f} kW",
        f"- 全场单位面积功率：{np.mean(mirror_power_kw) / design.area:.9f} kW/m²",
        f"- 低功率分区阈值：{low_threshold / design.area:.6f} kW/m²",
        "",
        "## 相对低功率区域",
        "",
        "| 排名 | 分区 | 半径范围 (m) | 方位角范围 | 方向 | 镜数 | 平均功率 (kW/面) | 单位面积功率 (kW/m²) | 相对全场平均 |",
        "|---:|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for index, row in enumerate(low_rows, start=1):
        lines.append(
            f"| {index} | {row['zone_id']} | {row['radial_inner_m']:.0f}-{row['radial_outer_m']:.0f} | "
            f"{row['azimuth_start_deg']:.0f}°-{row['azimuth_end_deg']:.0f}° | {row['direction']} | "
            f"{row['mirror_count']} | {row['avg_power_per_mirror_kw']:.4f} | "
            f"{row['avg_unit_area_power_kw_m2']:.4f} | {row['relative_to_field_avg_pct']:.1f}% |"
        )
    (output_run / "results" / "spatial_power_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    for folder in ("results", "figures", "validation", "logs"):
        (args.output_run / folder).mkdir(parents=True, exist_ok=True)
    logger = make_logger(args.output_run)
    raw_design = json.loads((args.input_run / "results" / "design.json").read_text(encoding="utf-8"))
    design = reconstruct_design(raw_design)
    positions = read_csv(args.input_run / "results" / "final_positions.csv")
    xy = np.asarray([[float(row["x_m"]), float(row["y_m"])] for row in positions])
    mirror_power_kw = exact_per_mirror_power(
        design,
        xy,
        args.samples,
        args.seed,
        args.neighbor_radius,
        logger,
    )
    zone_rows, radial_index, sector_index, low_threshold = build_zone_rows(
        xy,
        mirror_power_kw,
        design.area,
        args.radial_bins,
        args.sector_count,
    )
    mirror_rows = []
    for index, (point, power, ring, sector) in enumerate(
        zip(xy, mirror_power_kw, radial_index, sector_index), start=1
    ):
        mirror_rows.append(
            {
                "mirror_id": index,
                "x_m": float(point[0]),
                "y_m": float(point[1]),
                "annual_avg_power_kw": float(power),
                "annual_unit_area_power_kw_m2": float(power / design.area),
                "zone_id": f"R{int(ring) + 1}-S{int(sector) + 1:02d}",
            }
        )
    write_csv(args.output_run / "results" / "mirror_power.csv", mirror_rows)
    write_csv(args.output_run / "results" / "zone_metrics.csv", zone_rows)
    write_csv(
        args.output_run / "results" / "low_power_zones.csv",
        [row for row in zone_rows if row["is_low_power_zone"]],
    )
    make_figures(
        args.output_run,
        design,
        xy,
        mirror_power_kw,
        zone_rows,
        args.radial_bins,
        args.sector_count,
        low_threshold,
    )
    write_summary(args.output_run, zone_rows, mirror_power_kw, design, low_threshold)
    official_power_mw = float(raw_design["field_power_mw"])
    recomputed_power_mw = float(np.sum(mirror_power_kw) / 1000.0)
    checks = {
        "samples": args.samples,
        "mirror_count": len(xy),
        "radial_bins": args.radial_bins,
        "sector_count": args.sector_count,
        "zone_count": len(zone_rows),
        "occupied_zone_count": sum(row["mirror_count"] > 0 for row in zone_rows),
        "low_power_zone_count": sum(row["is_low_power_zone"] for row in zone_rows),
        "official_field_power_mw": official_power_mw,
        "recomputed_sum_of_mirror_power_mw": recomputed_power_mw,
        "absolute_power_difference_mw": abs(recomputed_power_mw - official_power_mw),
        "relative_power_difference": abs(recomputed_power_mw - official_power_mw) / official_power_mw,
        "zone_mirror_count_sum": sum(int(row["mirror_count"]) for row in zone_rows),
        "zone_power_sum_kw": sum(float(row["total_power_kw"]) for row in zone_rows),
        "power_conservation_passed": abs(recomputed_power_mw - official_power_mw) <= 1.0e-9,
    }
    (args.output_run / "validation" / "checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    hashes = {
        HERE.name: hashlib.sha256(HERE.read_bytes()).hexdigest(),
        "q2_model.py": hashlib.sha256((ROUTES / "r01-common-size-field-optimization" / "code" / "q2_model.py").read_bytes()).hexdigest(),
    }
    (args.output_run / "validation" / "code_hashes.json").write_text(
        json.dumps(hashes, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Spatial power analysis completed: %s", json.dumps(checks, ensure_ascii=False))


if __name__ == "__main__":
    main()
