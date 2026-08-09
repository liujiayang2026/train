from __future__ import annotations

import csv
import html
import math
from pathlib import Path

import numpy as np
import pandas as pd


SEED = 20220805
PSEUDOCOUNT = 0.10
N_PERMUTATIONS = 5000

TYPE_HIGH_K = "高钾"
TYPE_LEAD_BARIUM = "铅钡"

COMPONENTS = [
    "SiO2", "Na2O", "K2O", "CaO", "MgO", "Al2O3", "Fe2O3",
    "CuO", "PbO", "BaO", "P2O5", "SrO", "SnO2", "SO2",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_directories(root: Path) -> dict[str, Path]:
    q4 = root / "question-4"
    dirs = {
        "code": q4 / "code",
        "docs": q4 / "docs",
        "processed": q4 / "data" / "processed",
        "results": q4 / "results",
        "figures": q4 / "figures",
        "qa": q4 / "qa",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def clr_transform(values: np.ndarray, pseudocount: float = PSEUDOCOUNT) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    row_sums = values.sum(axis=1, keepdims=True)
    closed = np.divide(values, row_sums, out=np.zeros_like(values), where=row_sums > 0) * 100.0
    logs = np.log(closed + pseudocount)
    return logs - logs.mean(axis=1, keepdims=True)


def correlation_matrix(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    centered = values - values.mean(axis=0, keepdims=True)
    denom = np.sqrt((centered**2).sum(axis=0))
    denom = np.where(denom > 1e-12, denom, np.nan)
    corr = centered.T @ centered / np.outer(denom, denom)
    corr = np.nan_to_num(corr, nan=0.0)
    np.fill_diagonal(corr, 1.0)
    return np.clip(corr, -1.0, 1.0)


def matrix_to_frame(matrix: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(matrix, index=COMPONENTS, columns=COMPONENTS).reset_index(names="component")


def long_correlations(matrix: np.ndarray, glass_type: str, group: pd.DataFrame) -> pd.DataFrame:
    zero_rates = {
        component: float((group[component] <= 1e-12).mean())
        for component in COMPONENTS
    }
    rows = []
    for i, a in enumerate(COMPONENTS):
        for j in range(i + 1, len(COMPONENTS)):
            b = COMPONENTS[j]
            max_zero_rate = max(zero_rates[a], zero_rates[b])
            rows.append({
                "glass_type": glass_type,
                "component_a": a,
                "component_b": b,
                "correlation": float(matrix[i, j]),
                "abs_correlation": abs(float(matrix[i, j])),
                "zero_rate_a": zero_rates[a],
                "zero_rate_b": zero_rates[b],
                "max_zero_rate": max_zero_rate,
                "reliable_pair": max_zero_rate <= 0.75,
            })
    return pd.DataFrame(rows)


def bh_adjust(p_values: np.ndarray) -> np.ndarray:
    p_values = np.asarray(p_values, dtype=float)
    n = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(n, dtype=float)
    running = 1.0
    for rank, idx in enumerate(order[::-1], start=1):
        original_rank = n - rank + 1
        running = min(running, p_values[idx] * n / original_rank)
        adjusted[idx] = running
    return np.clip(adjusted, 0.0, 1.0)


def upper_triangle_values(matrix: np.ndarray) -> np.ndarray:
    idx = np.triu_indices_from(matrix, k=1)
    return matrix[idx]


def frobenius_upper_difference(matrix_a: np.ndarray, matrix_b: np.ndarray) -> float:
    diff = upper_triangle_values(matrix_a - matrix_b)
    return float(np.sqrt(np.sum(diff**2)))


def permutation_difference_tests(
    data: pd.DataFrame,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    high = data[data["glass_type"] == TYPE_HIGH_K]
    lead = data[data["glass_type"] == TYPE_LEAD_BARIUM]
    all_clr = clr_transform(data[COMPONENTS].to_numpy(), PSEUDOCOUNT)
    labels = data["glass_type"].to_numpy()
    n_high = len(high)

    high_corr = correlation_matrix(clr_transform(high[COMPONENTS].to_numpy(), PSEUDOCOUNT))
    lead_corr = correlation_matrix(clr_transform(lead[COMPONENTS].to_numpy(), PSEUDOCOUNT))
    zero_rates = {}
    for glass_type, group in [(TYPE_HIGH_K, high), (TYPE_LEAD_BARIUM, lead)]:
        zero_rates[glass_type] = {
            component: float((group[component] <= 1e-12).mean())
            for component in COMPONENTS
        }
    observed_global = frobenius_upper_difference(high_corr, lead_corr)

    observed_pair_diffs = []
    pair_names = []
    for i, a in enumerate(COMPONENTS):
        for j in range(i + 1, len(COMPONENTS)):
            pair_names.append((a, COMPONENTS[j]))
            observed_pair_diffs.append(float(high_corr[i, j] - lead_corr[i, j]))
    observed_pair_diffs_array = np.array(observed_pair_diffs)
    pair_exceed = np.zeros(len(observed_pair_diffs_array), dtype=int)
    global_exceed = 0
    global_values = []

    indices = np.arange(len(data))
    for _ in range(N_PERMUTATIONS):
        high_idx = rng.choice(indices, size=n_high, replace=False)
        high_mask = np.zeros(len(data), dtype=bool)
        high_mask[high_idx] = True
        perm_high_corr = correlation_matrix(all_clr[high_mask])
        perm_lead_corr = correlation_matrix(all_clr[~high_mask])
        perm_global = frobenius_upper_difference(perm_high_corr, perm_lead_corr)
        global_values.append(perm_global)
        if perm_global >= observed_global - 1e-12:
            global_exceed += 1
        perm_diffs = []
        for i in range(len(COMPONENTS)):
            for j in range(i + 1, len(COMPONENTS)):
                perm_diffs.append(float(perm_high_corr[i, j] - perm_lead_corr[i, j]))
        pair_exceed += np.abs(np.array(perm_diffs)) >= np.abs(observed_pair_diffs_array) - 1e-12

    pair_p = (pair_exceed + 1) / (N_PERMUTATIONS + 1)
    pair_q = bh_adjust(pair_p)
    differential_rows = []
    for idx, (a, b) in enumerate(pair_names):
        i = COMPONENTS.index(a)
        j = COMPONENTS.index(b)
        differential_rows.append({
            "component_a": a,
            "component_b": b,
            "high_k_correlation": float(high_corr[i, j]),
            "lead_barium_correlation": float(lead_corr[i, j]),
            "correlation_difference_high_minus_lead": observed_pair_diffs[idx],
            "high_k_max_zero_rate": max(zero_rates[TYPE_HIGH_K][a], zero_rates[TYPE_HIGH_K][b]),
            "lead_barium_max_zero_rate": max(zero_rates[TYPE_LEAD_BARIUM][a], zero_rates[TYPE_LEAD_BARIUM][b]),
            "reliable_in_both_types": (
                max(zero_rates[TYPE_HIGH_K][a], zero_rates[TYPE_HIGH_K][b]) <= 0.75
                and max(zero_rates[TYPE_LEAD_BARIUM][a], zero_rates[TYPE_LEAD_BARIUM][b]) <= 0.75
            ),
            "permutation_p": pair_p[idx],
            "bh_q": pair_q[idx],
        })

    global_frame = pd.DataFrame([{
        "observed_frobenius_upper_difference": observed_global,
        "permutation_p": (global_exceed + 1) / (N_PERMUTATIONS + 1),
        "permutation_mean": float(np.mean(global_values)),
        "permutation_p95": float(np.quantile(global_values, 0.95)),
        "n_permutations": N_PERMUTATIONS,
        "n_high_k": int(n_high),
        "n_lead_barium": int((labels == TYPE_LEAD_BARIUM).sum()),
    }])
    return pd.DataFrame(differential_rows), global_frame


def raw_corrected_sensitivity(corrected: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for glass_type in [TYPE_HIGH_K, TYPE_LEAD_BARIUM]:
        corrected_group = corrected[corrected["glass_type"] == glass_type].sort_values("artifact_id")
        raw_group = raw[raw["glass_type"] == glass_type].sort_values("artifact_id")
        common = sorted(set(corrected_group["artifact_id"]) & set(raw_group["artifact_id"]))
        corrected_group = corrected_group[corrected_group["artifact_id"].isin(common)].sort_values("artifact_id")
        raw_group = raw_group[raw_group["artifact_id"].isin(common)].sort_values("artifact_id")
        c_corr = correlation_matrix(clr_transform(corrected_group[COMPONENTS].to_numpy(), PSEUDOCOUNT))
        r_corr = correlation_matrix(clr_transform(raw_group[COMPONENTS].to_numpy(), PSEUDOCOUNT))
        rows.append({
            "glass_type": glass_type,
            "common_artifacts": len(common),
            "frobenius_upper_difference_raw_vs_corrected": frobenius_upper_difference(c_corr, r_corr),
            "mean_abs_pairwise_difference": float(np.mean(np.abs(upper_triangle_values(c_corr - r_corr)))),
            "max_abs_pairwise_difference": float(np.max(np.abs(upper_triangle_values(c_corr - r_corr)))),
        })
    return pd.DataFrame(rows)


def summarize_components(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for glass_type, group in data.groupby("glass_type"):
        clr = clr_transform(group[COMPONENTS].to_numpy(), PSEUDOCOUNT)
        corr = correlation_matrix(clr)
        mean_abs = np.mean(np.abs(corr - np.eye(len(COMPONENTS))), axis=1)
        for idx, component in enumerate(COMPONENTS):
            rows.append({
                "glass_type": glass_type,
                "component": component,
                "mean": group[component].mean(),
                "median": group[component].median(),
                "zero_rate": float((group[component] <= 1e-12).mean()),
                "mean_abs_correlation_to_others": float((np.sum(np.abs(corr[idx])) - 1.0) / (len(COMPONENTS) - 1)),
                "clr_variance": float(np.var(clr[:, idx], ddof=1)),
            })
    return pd.DataFrame(rows)


def heat_color(value: float, max_abs: float = 1.0) -> str:
    value = max(-max_abs, min(max_abs, value)) / max_abs
    if value >= 0:
        t = value
        r = int(255 * (1 - t) + 178 * t)
        g = int(255 * (1 - t) + 69 * t)
        b = int(255 * (1 - t) + 69 * t)
    else:
        t = -value
        r = int(255 * (1 - t) + 47 * t)
        g = int(255 * (1 - t) + 111 * t)
        b = int(255 * (1 - t) + 159 * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def svg_heatmap(path: Path, matrix: np.ndarray, title: str, max_abs: float = 1.0) -> None:
    cell = 34
    left = 92
    top = 70
    width = left + cell * len(COMPONENTS) + 180
    height = top + cell * len(COMPONENTS) + 130
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" font-weight="700">{html.escape(title)}</text>',
    ]
    for i, comp in enumerate(COMPONENTS):
        x = left + i * cell + cell / 2
        y = top - 10
        elements.append(f'<text x="{x:.1f}" y="{y}" text-anchor="end" transform="rotate(-55 {x:.1f} {y})" font-family="Arial, sans-serif" font-size="10">{comp}</text>')
        elements.append(f'<text x="{left-8}" y="{top+i*cell+cell/2+4:.1f}" text-anchor="end" font-family="Arial, sans-serif" font-size="10">{comp}</text>')
    for i in range(len(COMPONENTS)):
        for j in range(len(COMPONENTS)):
            x = left + j * cell
            y = top + i * cell
            color = heat_color(float(matrix[i, j]), max_abs)
            elements.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{color}" stroke="#ffffff" stroke-width="1"/>')
            if i != j:
                elements.append(f'<text x="{x+cell/2:.1f}" y="{y+cell/2+3:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="8" fill="#111827">{matrix[i,j]:.2f}</text>')
    legend_x = left + cell * len(COMPONENTS) + 40
    legend_y = top + 20
    elements.append(f'<text x="{legend_x}" y="{legend_y-12}" font-family="Arial, sans-serif" font-size="12" font-weight="700">Correlation</text>')
    for k, value in enumerate(np.linspace(max_abs, -max_abs, 9)):
        y = legend_y + k * 22
        elements.append(f'<rect x="{legend_x}" y="{y}" width="22" height="18" fill="{heat_color(float(value), max_abs)}" stroke="#e5e7eb"/>')
        elements.append(f'<text x="{legend_x+30}" y="{y+13}" font-family="Arial, sans-serif" font-size="10">{value:.1f}</text>')
    elements.append("</svg>")
    path.write_text("\n".join(elements), encoding="utf-8-sig")


def write_summary(
    path: Path,
    long_corr: pd.DataFrame,
    differential: pd.DataFrame,
    global_diff: pd.DataFrame,
    sensitivity: pd.DataFrame,
) -> None:
    lines = [
        "# 问题四结果摘要",
        "",
        "## 全局结构差异",
        "",
    ]
    g = global_diff.iloc[0]
    lines.append(
        f"- 高钾与铅钡 CLR 相关矩阵的上三角 Frobenius 差异为 "
        f"{g['observed_frobenius_upper_difference']:.3f}，置换检验 p={g['permutation_p']:.4f}。"
    )
    lines += ["", "## 各类型可靠强相关成分对", ""]
    for glass_type in [TYPE_HIGH_K, TYPE_LEAD_BARIUM]:
        reliable = long_corr[
            (long_corr["glass_type"] == glass_type)
            & (long_corr["reliable_pair"])
        ]
        top = reliable.sort_values("abs_correlation", ascending=False).head(8)
        lines.append(f"### {glass_type}")
        for _, row in top.iterrows():
            lines.append(
                f"- {row['component_a']}--{row['component_b']}: r={row['correlation']:.3f}, "
                f"最大零值率={row['max_zero_rate']:.2f}."
            )
        lines.append("")
    lines += ["## 类型间差异最大的可靠相关关系", ""]
    top_diff = differential[differential["reliable_in_both_types"]].sort_values("bh_q").head(10)
    for _, row in top_diff.iterrows():
        lines.append(
            f"- {row['component_a']}--{row['component_b']}: "
            f"高钾 r={row['high_k_correlation']:.3f}, 铅钡 r={row['lead_barium_correlation']:.3f}, "
            f"差值={row['correlation_difference_high_minus_lead']:.3f}, q={row['bh_q']:.4f}."
        )
    lines += [
        "",
        "说明：完整相关矩阵仍保留全部 14 种成分；正文优先解释零值率较低的可靠成分对。"
        "涉及 SnO2、SrO、SO2 等高零值率成分的强相关可作为特殊样本线索，不宜过度解释。",
    ]
    lines += ["", "## 风化修正敏感性", ""]
    for _, row in sensitivity.iterrows():
        lines.append(
            f"- {row['glass_type']}: 原始与风化修正相关矩阵差异="
            f"{row['frobenius_upper_difference_raw_vs_corrected']:.3f}，"
            f"平均成分对差异={row['mean_abs_pairwise_difference']:.3f}。"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def main() -> None:
    rng = np.random.default_rng(SEED)
    root = project_root()
    dirs = ensure_directories(root)
    corrected_path = root / "question-2" / "data" / "processed" / "corrected-artifact-compositions.csv"
    raw_path = root / "question-2" / "data" / "processed" / "raw-artifact-compositions.csv"
    corrected = pd.read_csv(corrected_path, encoding="utf-8-sig")
    raw = pd.read_csv(raw_path, encoding="utf-8-sig")

    write_csv(corrected, dirs["processed"] / "analysis-artifact-compositions.csv")

    matrices = {}
    long_frames = []
    for glass_type in [TYPE_HIGH_K, TYPE_LEAD_BARIUM]:
        group = corrected[corrected["glass_type"] == glass_type]
        matrix = correlation_matrix(clr_transform(group[COMPONENTS].to_numpy(), PSEUDOCOUNT))
        matrices[glass_type] = matrix
        write_csv(matrix_to_frame(matrix), dirs["results"] / f"clr-correlation-{glass_type}.csv")
        long_frames.append(long_correlations(matrix, glass_type, group))
        svg_heatmap(dirs["figures"] / f"clr-correlation-heatmap-{glass_type}.svg", matrix, f"{glass_type} CLR component correlations")

    long_corr = pd.concat(long_frames, ignore_index=True)
    top_corr = long_corr.sort_values(["glass_type", "abs_correlation"], ascending=[True, False]).groupby("glass_type").head(20)
    reliable_top_corr = (
        long_corr[long_corr["reliable_pair"]]
        .sort_values(["glass_type", "abs_correlation"], ascending=[True, False])
        .groupby("glass_type")
        .head(20)
    )
    differential, global_diff = permutation_difference_tests(corrected, rng)
    sensitivity = raw_corrected_sensitivity(corrected, raw)
    component_summary = summarize_components(corrected)

    diff_matrix = matrices[TYPE_HIGH_K] - matrices[TYPE_LEAD_BARIUM]
    svg_heatmap(
        dirs["figures"] / "clr-correlation-difference-heatmap.svg",
        diff_matrix,
        "CLR correlation difference: high-K minus lead-barium",
        max_abs=max(1.0, float(np.max(np.abs(diff_matrix)))),
    )

    write_csv(long_corr, dirs["results"] / "clr-correlations-long.csv")
    write_csv(top_corr, dirs["results"] / "top-component-associations.csv")
    write_csv(reliable_top_corr, dirs["results"] / "top-reliable-component-associations.csv")
    write_csv(differential.sort_values("bh_q"), dirs["results"] / "differential-correlations.csv")
    write_csv(global_diff, dirs["results"] / "global-correlation-difference.csv")
    write_csv(sensitivity, dirs["results"] / "raw-vs-corrected-correlation-sensitivity.csv")
    write_csv(component_summary, dirs["results"] / "component-correlation-summary.csv")

    write_summary(
        dirs["docs"] / "question-4-results-summary.md",
        long_corr,
        differential,
        global_diff,
        sensitivity,
    )

    print("Question 4 analysis complete.")
    print(f"Corrected artifacts: {len(corrected)}")
    print(f"Results: {dirs['results']}")
    print(f"Figures: {dirs['figures']}")


if __name__ == "__main__":
    main()
