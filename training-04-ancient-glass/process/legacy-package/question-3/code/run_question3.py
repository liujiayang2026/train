from __future__ import annotations

import csv
import html
import math
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


PSEUDOCOUNT = 0.10
COMPONENTS = [
    "SiO2", "Na2O", "K2O", "CaO", "MgO", "Al2O3", "Fe2O3",
    "CuO", "PbO", "BaO", "P2O5", "SrO", "SnO2", "SO2",
]
TYPE_HIGH_K = "高钾"
TYPE_LEAD_BARIUM = "铅钡"
HIGH_K_FEATURES = ["SiO2", "K2O", "CaO", "MgO", "Al2O3", "Fe2O3", "CuO"]
LEAD_BARIUM_FEATURES = ["SiO2", "PbO", "BaO", "P2O5", "SrO", "CuO"]
MAJOR_FEATURES = ["SiO2", "K2O", "CaO", "Al2O3", "PbO", "BaO"]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_directories(root: Path) -> dict[str, Path]:
    q3 = root / "question-3"
    dirs = {
        "code": q3 / "code",
        "docs": q3 / "docs",
        "processed": q3 / "data" / "processed",
        "results": q3 / "results",
        "figures": q3 / "figures",
        "qa": q3 / "qa",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def find_source_workbook(root: Path) -> Path:
    candidates = [
        path for path in root.rglob("*.xlsx")
        if not path.name.startswith("~$")
        and "question-1" not in path.parts
        and "question-2" not in path.parts
        and "question-3" not in path.parts
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one source workbook, found {candidates}")
    return candidates[0]


def read_unknown_samples(path: Path) -> pd.DataFrame:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = list(workbook.worksheets[2].iter_rows(values_only=True))
    records = []
    for row in rows[1:]:
        record = {
            "artifact_id": str(row[0]),
            "surface_weathering": str(row[1]),
        }
        for component, value in zip(COMPONENTS, row[2:]):
            record[component] = 0.0 if value is None else float(value)
        records.append(record)
    frame = pd.DataFrame(records)
    frame["component_sum"] = frame[COMPONENTS].sum(axis=1)
    frame["is_valid"] = frame["component_sum"].between(85.0, 105.0)
    return close_compositions(frame, COMPONENTS)


def close_compositions(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    sums = result[columns].sum(axis=1).replace(0, np.nan)
    result[columns] = result[columns].div(sums, axis=0).fillna(0.0) * 100.0
    result["closed_sum"] = result[columns].sum(axis=1)
    return result


def clr_transform(values: np.ndarray, pseudocount: float = PSEUDOCOUNT) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    row_sums = values.sum(axis=1, keepdims=True)
    closed = np.divide(values, row_sums, out=np.zeros_like(values), where=row_sums > 0) * 100.0
    logs = np.log(closed + pseudocount)
    return logs - logs.mean(axis=1, keepdims=True)


def inverse_clr(values: np.ndarray) -> np.ndarray:
    exp_values = np.exp(values)
    return exp_values / exp_values.sum(axis=1, keepdims=True) * 100.0


def standardize_with_reference(values: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    center = reference.mean(axis=0)
    scale = reference.std(axis=0, ddof=0)
    scale = np.where(scale > 1e-12, scale, 1.0)
    return (values - center) / scale, (reference - center) / scale


def log_ratio_pbba_to_k(frame: pd.DataFrame, pseudocount: float = PSEUDOCOUNT) -> np.ndarray:
    return np.log(
        (frame["PbO"].to_numpy() + frame["BaO"].to_numpy() + pseudocount)
        / (frame["K2O"].to_numpy() + pseudocount)
    )


def nearest_centroid_type(
    unknown: pd.DataFrame,
    training: pd.DataFrame,
    pseudocount: float = PSEUDOCOUNT,
) -> tuple[np.ndarray, np.ndarray]:
    x = clr_transform(unknown[MAJOR_FEATURES].to_numpy(), pseudocount)
    ref = clr_transform(training[MAJOR_FEATURES].to_numpy(), pseudocount)
    xz, refz = standardize_with_reference(x, ref)
    centroids = {
        glass_type: refz[training["glass_type"].to_numpy() == glass_type].mean(axis=0)
        for glass_type in sorted(training["glass_type"].unique())
    }
    predictions = []
    margins = []
    for row in xz:
        distances = {
            glass_type: float(((row - centroid) ** 2).sum())
            for glass_type, centroid in centroids.items()
        }
        ordered = sorted(distances.items(), key=lambda item: item[1])
        predictions.append(ordered[0][0])
        margins.append(ordered[1][1] - ordered[0][1] if len(ordered) > 1 else np.nan)
    return np.array(predictions, dtype=object), np.array(margins, dtype=float)


def nearest_subclass(
    row: pd.Series,
    centers: pd.DataFrame,
    training: pd.DataFrame,
    glass_type: str,
    pseudocount: float = PSEUDOCOUNT,
) -> dict[str, object]:
    features = HIGH_K_FEATURES if glass_type == TYPE_HIGH_K else LEAD_BARIUM_FEATURES
    type_training = training[training["glass_type"] == glass_type]
    type_centers = centers[centers["glass_type"] == glass_type].copy()
    x = clr_transform(row[features].to_numpy(dtype=float).reshape(1, -1), pseudocount)
    center_values = clr_transform(type_centers[features].to_numpy(dtype=float), pseudocount)
    xz, cz = standardize_with_reference(x, clr_transform(type_training[features].to_numpy(dtype=float), pseudocount))
    center_z, _ = standardize_with_reference(center_values, clr_transform(type_training[features].to_numpy(dtype=float), pseudocount))
    distances = ((xz[0][None, :] - center_z) ** 2).sum(axis=1)
    order = np.argsort(distances)
    best = type_centers.iloc[int(order[0])]
    second_distance = float(distances[order[1]]) if len(order) > 1 else np.nan
    return {
        "subclass_id": best["subclass_id"],
        "subclass_name": best["subclass_name"],
        "subclass_distance": float(distances[order[0]]),
        "subclass_margin": second_distance - float(distances[order[0]]) if len(order) > 1 else np.nan,
    }


def apply_type_weathering_correction(
    row: pd.Series,
    effects: pd.DataFrame,
    candidate_type: str,
    pseudocount: float = PSEUDOCOUNT,
) -> dict[str, float]:
    values = row[COMPONENTS].to_numpy(dtype=float).reshape(1, -1)
    y = clr_transform(values, pseudocount)
    effect_row = (
        effects[effects["glass_type"] == candidate_type]
        .set_index("component")
        .loc[COMPONENTS, "clr_weathering_effect"]
        .to_numpy(dtype=float)
        .reshape(1, -1)
    )
    corrected = inverse_clr(y - effect_row)[0]
    return {component: float(value) for component, value in zip(COMPONENTS, corrected)}


def classify_frame(
    frame: pd.DataFrame,
    training: pd.DataFrame,
    centers: pd.DataFrame,
    threshold: float,
    pseudocount: float = PSEUDOCOUNT,
) -> pd.DataFrame:
    result = frame.copy()
    ratio = log_ratio_pbba_to_k(result, pseudocount)
    result["log_ratio_pbba_to_k"] = ratio
    result["threshold_type"] = np.where(ratio >= threshold, TYPE_LEAD_BARIUM, TYPE_HIGH_K)
    centroid_type, centroid_margin = nearest_centroid_type(result, training, pseudocount)
    result["centroid_type"] = centroid_type
    result["centroid_margin"] = centroid_margin
    result["final_type"] = np.where(
        result["threshold_type"] == result["centroid_type"],
        result["threshold_type"],
        result["threshold_type"],
    )
    result["type_agreement"] = result["threshold_type"] == result["centroid_type"]
    subclass_records = []
    for _, row in result.iterrows():
        subclass_records.append(nearest_subclass(row, centers, training, row["final_type"], pseudocount))
    subclass_frame = pd.DataFrame(subclass_records)
    return pd.concat([result.reset_index(drop=True), subclass_frame], axis=1)


def build_type_conditional_candidates(
    unknown: pd.DataFrame,
    effects: pd.DataFrame,
    training: pd.DataFrame,
    centers: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    rows = []
    for _, row in unknown.iterrows():
        candidate_types = [TYPE_HIGH_K, TYPE_LEAD_BARIUM] if row["surface_weathering"] == "风化" else ["raw_unweathered"]
        for candidate in candidate_types:
            base = {
                "artifact_id": row["artifact_id"],
                "surface_weathering": row["surface_weathering"],
                "candidate_correction": candidate,
            }
            if candidate == "raw_unweathered":
                values = {component: float(row[component]) for component in COMPONENTS}
            else:
                values = apply_type_weathering_correction(row, effects, candidate, PSEUDOCOUNT)
            candidate_frame = pd.DataFrame([{**base, **values}])
            classified = classify_frame(candidate_frame, training, centers, threshold, PSEUDOCOUNT)
            rows.append(classified.iloc[0].to_dict())
    return pd.DataFrame(rows)


def type_sensitivity(
    unknown: pd.DataFrame,
    training: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    rows = []
    for pseudocount in [0.05, 0.10, 0.50]:
        training_ratio = log_ratio_pbba_to_k(training, pseudocount)
        training_labels = training["glass_type"].to_numpy()
        sorted_values = np.sort(training_ratio)
        candidates = [sorted_values[0] - 1e-9]
        candidates += [
            float((sorted_values[idx] + sorted_values[idx + 1]) / 2.0)
            for idx in range(len(sorted_values) - 1)
        ]
        candidates.append(sorted_values[-1] + 1e-9)
        best_threshold = threshold
        best_score = (-1.0, -1.0)
        for candidate in candidates:
            pred = np.where(training_ratio >= candidate, TYPE_LEAD_BARIUM, TYPE_HIGH_K)
            tp = ((pred == TYPE_LEAD_BARIUM) & (training_labels == TYPE_LEAD_BARIUM)).sum()
            tn = ((pred == TYPE_HIGH_K) & (training_labels == TYPE_HIGH_K)).sum()
            fp = ((pred == TYPE_LEAD_BARIUM) & (training_labels == TYPE_HIGH_K)).sum()
            fn = ((pred == TYPE_HIGH_K) & (training_labels == TYPE_LEAD_BARIUM)).sum()
            sensitivity = tp / max(1, tp + fn)
            specificity = tn / max(1, tn + fp)
            accuracy = (pred == training_labels).mean()
            score = (sensitivity + specificity - 1.0, accuracy)
            if score > best_score:
                best_score = score
                best_threshold = float(candidate)
        ratio = log_ratio_pbba_to_k(unknown, pseudocount)
        threshold_type = np.where(ratio >= best_threshold, TYPE_LEAD_BARIUM, TYPE_HIGH_K)
        centroid_type, _ = nearest_centroid_type(unknown, training, pseudocount)
        for artifact_id, t1, t2 in zip(unknown["artifact_id"], threshold_type, centroid_type):
            rows.append({
                "artifact_id": artifact_id,
                "pseudocount": pseudocount,
                "threshold": best_threshold,
                "threshold_type": t1,
                "centroid_type": t2,
                "agreement": t1 == t2,
            })
    return pd.DataFrame(rows)


def final_decision(raw: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in raw.iterrows():
        artifact_id = row["artifact_id"]
        related = candidates[candidates["artifact_id"] == artifact_id]
        candidate_match = related[related["candidate_correction"] == row["final_type"]]
        if row["surface_weathering"] == "风化" and not candidate_match.empty:
            chosen = candidate_match.iloc[0]
            basis = "type-conditional weathering correction agrees with raw type"
        elif row["surface_weathering"] == "风化":
            chosen = related.iloc[0]
            basis = "raw type retained; conditional correction inconsistent"
        else:
            chosen = row
            basis = "unweathered raw composition"

        stable_type = bool((related["final_type"] == row["final_type"]).all()) if len(related) > 1 else True
        raw_subclass = str(row["subclass_id"])
        chosen_subclass = str(chosen["subclass_id"])
        subclass_stable = raw_subclass == chosen_subclass
        confidence = "高" if bool(row["type_agreement"]) and stable_type else "中"
        rows.append({
            "artifact_id": artifact_id,
            "surface_weathering": row["surface_weathering"],
            "raw_threshold_type": row["threshold_type"],
            "raw_centroid_type": row["centroid_type"],
            "final_type": row["final_type"],
            "final_subclass_id": chosen["subclass_id"],
            "final_subclass_name": chosen["subclass_name"],
            "log_ratio_pbba_to_k": row["log_ratio_pbba_to_k"],
            "type_agreement": bool(row["type_agreement"]),
            "type_stable_under_candidate_correction": stable_type,
            "raw_subclass_id": raw_subclass,
            "subclass_stable_after_weathering_correction": subclass_stable,
            "confidence": confidence,
            "decision_basis": basis,
        })
    return pd.DataFrame(rows)


def pca_coordinates_for_unknown(training: pd.DataFrame, decisions: pd.DataFrame, unknown_raw: pd.DataFrame) -> pd.DataFrame:
    all_values = pd.concat([
        training[["artifact_id", "glass_type", *MAJOR_FEATURES]].assign(source="known"),
        unknown_raw.merge(decisions[["artifact_id", "final_type"]], on="artifact_id")[
            ["artifact_id", "final_type", *MAJOR_FEATURES]
        ].rename(columns={"final_type": "glass_type"}).assign(source="unknown"),
    ], ignore_index=True)
    clr = clr_transform(all_values[MAJOR_FEATURES].to_numpy(), PSEUDOCOUNT)
    centered = clr - clr.mean(axis=0)
    _, singular_values, vt = np.linalg.svd(centered, full_matrices=False)
    coords = centered @ vt[:2].T
    explained = singular_values**2 / np.sum(singular_values**2)
    all_values["pca1"] = coords[:, 0]
    all_values["pca2"] = coords[:, 1]
    all_values["pca1_explained"] = explained[0]
    all_values["pca2_explained"] = explained[1]
    return all_values[["artifact_id", "glass_type", "source", "pca1", "pca2", "pca1_explained", "pca2_explained"]]


def svg_unknown_major(path: Path, points: pd.DataFrame) -> None:
    width, height = 760, 520
    margin_left, margin_right, margin_top, margin_bottom = 70, 160, 55, 70
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    x = points["pca1"].to_numpy(float)
    y = points["pca2"].to_numpy(float)
    x_min, x_max = float(x.min()), float(x.max())
    y_min, y_max = float(y.min()), float(y.max())
    x_pad = 0.08 * (x_max - x_min or 1.0)
    y_pad = 0.08 * (y_max - y_min or 1.0)
    x_min -= x_pad
    x_max += x_pad
    y_min -= y_pad
    y_max += y_pad

    def sx(value: float) -> float:
        return margin_left + (value - x_min) / (x_max - x_min) * plot_w

    def sy(value: float) -> float:
        return margin_top + (y_max - value) / (y_max - y_min) * plot_h

    colors = {TYPE_HIGH_K: "#2f6f9f", TYPE_LEAD_BARIUM: "#c66b2b"}
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="28" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="700">Unknown artifacts in major-type PCA space</text>',
        f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{margin_left+plot_w}" y2="{margin_top+plot_h}" stroke="#222" stroke-width="1"/>',
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#222" stroke-width="1"/>',
    ]
    for _, row in points.iterrows():
        cx = sx(float(row["pca1"]))
        cy = sy(float(row["pca2"]))
        color = colors[row["glass_type"]]
        if row["source"] == "unknown":
            elements.append(f'<rect x="{cx-6:.1f}" y="{cy-6:.1f}" width="12" height="12" fill="{color}" stroke="#111827" stroke-width="1.4"/>')
            elements.append(f'<text x="{cx+9:.1f}" y="{cy+4:.1f}" font-family="Arial, sans-serif" font-size="11" font-weight="700">{html.escape(str(row["artifact_id"]))}</text>')
        else:
            elements.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.2" fill="{color}" opacity="0.45"/>')
    x_label = f'PC1 ({points["pca1_explained"].iloc[0]*100:.1f}%)'
    y_label = f'PC2 ({points["pca2_explained"].iloc[0]*100:.1f}%)'
    elements.append(f'<text x="{margin_left+plot_w/2}" y="{height-25}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">{x_label}</text>')
    elements.append(f'<text transform="translate(22 {margin_top+plot_h/2}) rotate(-90)" text-anchor="middle" font-family="Arial, sans-serif" font-size="13">{y_label}</text>')
    legend_x = margin_left + plot_w + 28
    elements.append(f'<circle cx="{legend_x}" cy="72" r="5" fill="{colors[TYPE_HIGH_K]}" opacity="0.8"/><text x="{legend_x+14}" y="76" font-family="Arial, sans-serif" font-size="12">High-K</text>')
    elements.append(f'<circle cx="{legend_x}" cy="96" r="5" fill="{colors[TYPE_LEAD_BARIUM]}" opacity="0.8"/><text x="{legend_x+14}" y="100" font-family="Arial, sans-serif" font-size="12">Lead-Ba</text>')
    elements.append(f'<rect x="{legend_x-5}" y="116" width="10" height="10" fill="#555"/><text x="{legend_x+14}" y="126" font-family="Arial, sans-serif" font-size="12">Unknown</text>')
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8-sig")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def write_summary(path: Path, decisions: pd.DataFrame, sensitivity: pd.DataFrame) -> None:
    lines = [
        "# 问题三结果摘要",
        "",
        "## 最终鉴别结果",
        "",
    ]
    for _, row in decisions.iterrows():
        lines.append(
            f"- {row['artifact_id']}：{row['final_type']}，"
            f"{row['final_subclass_id']} {row['final_subclass_name']}, "
            f"置信度={row['confidence']}，"
            f"大类稳定={row['type_stable_under_candidate_correction']}。"
        )
    lines += [
        "",
        "## 敏感性",
        "",
    ]
    for artifact_id, group in sensitivity.groupby("artifact_id"):
        pairs = [
            f"eps={row.pseudocount}: 阈值={row.threshold_type}, 中心={row.centroid_type}"
            for row in group.itertuples(index=False)
        ]
        lines.append(f"- {artifact_id}: " + "; ".join(pairs) + ".")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def main() -> None:
    root = project_root()
    dirs = ensure_directories(root)
    workbook = find_source_workbook(root)
    unknown = read_unknown_samples(workbook)
    training = pd.read_csv(root / "question-2" / "data" / "processed" / "corrected-artifact-compositions.csv", encoding="utf-8-sig")
    centers = pd.read_csv(root / "question-2" / "results" / "subclass-centers.csv", encoding="utf-8-sig")
    major_summary = pd.read_csv(root / "question-2" / "results" / "major-type-classification-summary.csv", encoding="utf-8-sig")
    effects = pd.read_csv(root / "question-1" / "results" / "weathering-clr-effects.csv", encoding="utf-8-sig")
    threshold = float(major_summary.loc[major_summary["model"] == "log_ratio_threshold_in_sample", "threshold"].iloc[0])

    raw_classification = classify_frame(unknown, training, centers, threshold, PSEUDOCOUNT)
    conditional = build_type_conditional_candidates(unknown, effects, training, centers, threshold)
    decisions = final_decision(raw_classification, conditional)
    sensitivity = type_sensitivity(unknown, training, threshold)
    pca_points = pca_coordinates_for_unknown(training, decisions, unknown)

    write_csv(unknown, dirs["processed"] / "unknown-artifact-compositions.csv")
    write_csv(raw_classification, dirs["results"] / "unknown-raw-classification.csv")
    write_csv(conditional, dirs["results"] / "type-conditional-weathering-classification.csv")
    write_csv(decisions, dirs["results"] / "unknown-final-identification.csv")
    write_csv(sensitivity, dirs["results"] / "unknown-type-sensitivity.csv")
    write_csv(pca_points, dirs["results"] / "unknown-major-pca-coordinates.csv")
    svg_unknown_major(dirs["figures"] / "unknown-major-pca.svg", pca_points)
    write_summary(dirs["docs"] / "question-3-results-summary.md", decisions, sensitivity)

    print("Question 3 analysis complete.")
    print(f"Unknown artifacts: {len(unknown)}")
    print(f"Results: {dirs['results']}")
    print(f"Figures: {dirs['figures']}")


if __name__ == "__main__":
    main()
