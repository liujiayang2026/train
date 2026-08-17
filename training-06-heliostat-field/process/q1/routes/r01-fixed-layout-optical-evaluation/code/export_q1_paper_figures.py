#!/usr/bin/env python3
"""Regenerate the adopted Q1 figures and export header-free paper versions."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

import draw_physical_ray_geometry as physical
import draw_q1_narrative_figures as narrative
import draw_q1_narrative_flow_split as split


PAPER_WHITE = "#FFFFFF"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalized_crop(source: Path, output: Path, bounds: tuple[float, float, float, float]) -> dict[str, object]:
    with Image.open(source) as image:
        width, height = image.size
        left, top, right, bottom = bounds
        box = (
            round(width * left),
            round(height * top),
            round(width * right),
            round(height * bottom),
        )
        cropped = image.crop(box).convert("RGB")
        cropped = ImageOps.expand(cropped, border=18, fill="white")
        output.parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output, format="PNG", dpi=(300, 300), optimize=True)
        output_size = list(cropped.size)
    return {
        "source_size_px": [width, height],
        "crop_box_px": list(box),
        "output_size_px": output_size,
        "source_sha256": sha256(source),
        "output_sha256": sha256(output),
    }


def configure_paper_backgrounds() -> None:
    physical.COLORS["paper"] = PAPER_WHITE
    narrative.PALETTE["paper"] = PAPER_WHITE
    split.PALETTE["paper"] = PAPER_WHITE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--monthly-results", required=True, type=Path)
    parser.add_argument("--annual-results", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    args = parser.parse_args()

    configure_paper_backgrounds()
    output_dir = args.run_dir / "figures"
    validation_dir = args.run_dir / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="q1-paper-figures-") as temp_name:
        temp = Path(temp_name)
        evaluator = split.load_evaluator()
        centers = evaluator.read_centers(args.input)

        split.draw_scene_inputs(centers, temp / "scene-inputs.png")
        split.draw_optical_chain(temp / "per-mirror-optical-chain.png")
        split.draw_aggregation_map(temp / "aggregation-to-tables.png")

        context = narrative.build_context(args.input)
        narrative.draw_field_to_neighbor(context, temp / "fig02-field-to-neighbor-scale.png")
        narrative.draw_shadow_blocking_physical(temp / "fig03-shadow-vs-blocking-physical.png")
        narrative.draw_real_sampling(context, temp / "fig04-real-joint-sampling.png")
        narrative.draw_monthly_story(
            args.monthly_results,
            args.annual_results,
            temp / "fig05-monthly-results-story.png",
        )
        narrative.write_validation(context, temp / "narrative-checks.json")

        physical.build_figure(
            temp / "fig01-physical-ray-geometry.png",
            temp / "physical-checks.json",
            paper_mode=True,
        )

        profiles = {
            "scene-inputs-paper.png": ("scene-inputs.png", (0.03, 0.17, 0.97, 0.93)),
            "per-mirror-optical-chain-paper.png": (
                "per-mirror-optical-chain.png",
                (0.03, 0.17, 0.97, 0.93),
            ),
            "aggregation-to-tables-paper.png": (
                "aggregation-to-tables.png",
                (0.03, 0.17, 0.97, 0.93),
            ),
            "field-to-neighbor-scale-paper.png": (
                "fig02-field-to-neighbor-scale.png",
                (0.03, 0.13, 0.97, 0.925),
            ),
            "shadow-vs-blocking-paper.png": (
                "fig03-shadow-vs-blocking-physical.png",
                (0.03, 0.13, 0.97, 0.94),
            ),
            "real-joint-sampling-paper.png": (
                "fig04-real-joint-sampling.png",
                (0.03, 0.13, 0.97, 0.95),
            ),
            "monthly-performance-paper.png": (
                "fig05-monthly-results-story.png",
                (0.03, 0.18, 0.97, 0.93),
            ),
            "physical-ray-geometry-paper.png": (
                "fig01-physical-ray-geometry.png",
                (0.03, 0.02, 0.97, 0.96),
            ),
        }

        image_checks = {}
        for output_name, (source_name, bounds) in profiles.items():
            image_checks[output_name] = normalized_crop(
                temp / source_name,
                output_dir / output_name,
                bounds,
            )

        checks = {
            "paper_background": PAPER_WHITE,
            "review_headers_removed": True,
            "power_symbol_in_aggregation": "P_field",
            "heliostat_count": len(centers),
            "monthly_result_rows": len(narrative.read_csv_rows(args.monthly_results)),
            "narrative_geometry_checks": json.loads((temp / "narrative-checks.json").read_text(encoding="utf-8")),
            "physical_geometry_checks": json.loads((temp / "physical-checks.json").read_text(encoding="utf-8")),
            "images": image_checks,
            "code_sha256": {
                path.name: sha256(path)
                for path in [
                    Path(__file__),
                    Path(split.__file__),
                    Path(narrative.__file__),
                    Path(physical.__file__),
                ]
            },
        }
        (validation_dir / "paper-figure-checks.json").write_text(
            json.dumps(checks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
