"""Optimized bundled-task pricing model for Question 3.

This version improves on the first greedy bundle simulation by:
1. generating many overlapping candidate bundles;
2. assigning each bundle several price multipliers;
3. selecting bundles under a global expected-payout budget with MILP;
4. comparing against Question 2 practical MILP and the first bundle simulation.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack


QUESTION = Path(__file__).resolve().parents[1]
PROJECT = QUESTION.parent
Q2_RESULTS = PROJECT / "question-2" / "results" / "milp-pricing-results.csv"
Q2_COMPARISON = PROJECT / "question-2" / "results" / "milp-comparison.csv"
FIRST_COMPARISON = QUESTION / "results" / "bundle-comparison.csv"
RESULTS_DIR = QUESTION / "results"
FIGURES_DIR = QUESTION / "figures"

LOW_PROBABILITY_THRESHOLD = 0.50
BOUNDARY_CHANGE = 8.0
BUNDLE_RADIUS_KM = 1.0
MAX_BUNDLE_SIZE = 5
MAX_NEIGHBORS = 8
MAX_CANDIDATES_PER_TASK = 80
PRICE_MULTIPLIERS = np.array([0.90, 0.95, 1.00, 1.05, 1.10])
BUDGET_RELAXATIONS = [0.00, 0.01, 0.02]


def logit(probability):
    probability = np.clip(probability, 1e-6, 1 - 1e-6)
    return np.log(probability / (1 - probability))


def sigmoid(value):
    return 1 / (1 + np.exp(-value))


def coordinates_km(frame):
    latitude = frame["latitude"].to_numpy(float)
    longitude = frame["longitude"].to_numpy(float)
    latitude_center = np.mean(latitude)
    return np.column_stack(
        (
            longitude * 111.0 * np.cos(np.radians(latitude_center)),
            latitude * 111.0,
        )
    )


def distance_matrix(points):
    diff = points[:, None, :] - points[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def mst_length(distances):
    count = distances.shape[0]
    if count <= 1:
        return 0.0
    selected = np.zeros(count, dtype=bool)
    selected[0] = True
    total = 0.0
    for _ in range(count - 1):
        best_distance = np.inf
        best_index = -1
        for index in np.flatnonzero(selected):
            candidates = np.flatnonzero(~selected)
            candidate_distances = distances[index, candidates]
            position = int(np.argmin(candidate_distances))
            if candidate_distances[position] < best_distance:
                best_distance = float(candidate_distances[position])
                best_index = int(candidates[position])
        selected[best_index] = True
        total += best_distance
    return total


def estimate_probability(package, local_distances, average_reward):
    old_prob = package["original_probability"].to_numpy(float)
    new_prob = package["practical_milp_probability"].to_numpy(float)
    old_price = package["original_price"].to_numpy(float)
    new_price = package["practical_milp_price"].to_numpy(float)

    base_average_reward = float(np.mean(new_price))
    mean_logit = float(np.mean(logit(new_prob)))
    price_changes = new_price - old_price
    valid = np.abs(price_changes) > 1e-6
    if np.any(valid):
        slopes = (logit(new_prob[valid]) - logit(old_prob[valid])) / price_changes[valid]
        slope = float(np.clip(np.mean(slopes), 0.02, 0.20))
    else:
        slope = 0.08

    task_count = len(package)
    route_length = mst_length(local_distances)
    average_edge = route_length / max(task_count - 1, 1)
    compactness = max(0.0, 1.0 - average_edge / BUNDLE_RADIUS_KM)

    # Slightly stronger route-sharing benefit than the first simulation, because
    # the optimized model can reject weak packages through MILP instead of being
    # forced to accept every locally greedy package.
    route_bonus = (
        0.42 * np.log(task_count)
        + 0.55 * compactness
        - 0.07 * (task_count - 1)
        - 0.10 * max(0.0, route_length - BUNDLE_RADIUS_KM)
    )
    utility = mean_logit + slope * (average_reward - base_average_reward)
    return float(sigmoid(utility + route_bonus)), route_length, compactness


def generate_candidate_bundles(candidates):
    candidates = candidates.copy().reset_index(drop=True)
    points = coordinates_km(candidates)
    distances = distance_matrix(points)
    task_to_index = dict(zip(candidates["task_id"], candidates.index))
    seen = set()
    rows = []

    for seed in candidates.index:
        same_region = candidates["region"] == candidates.loc[seed, "region"]
        nearby = [
            int(index)
            for index in np.flatnonzero(same_region.to_numpy())
            if index != seed and distances[seed, index] <= BUNDLE_RADIUS_KM
        ]
        nearby.sort(key=lambda index: distances[seed, index])
        nearby = nearby[:MAX_NEIGHBORS]
        local_candidates = [seed] + nearby
        generated_for_seed = 0

        for size in range(2, min(MAX_BUNDLE_SIZE, len(local_candidates)) + 1):
            for combo_tail in combinations(nearby, size - 1):
                combo = tuple(sorted((seed,) + combo_tail))
                if combo in seen:
                    continue
                seen.add(combo)
                package = candidates.loc[list(combo)].copy()
                local_distances = distances[np.ix_(combo, combo)]
                route_length = mst_length(local_distances)
                average_edge = route_length / max(size - 1, 1)
                max_pair_distance = float(local_distances.max())
                if max_pair_distance > BUNDLE_RADIUS_KM * 1.25:
                    continue
                if average_edge > 0.85:
                    continue

                baseline_probability = package["practical_milp_probability"].to_numpy(float)
                baseline_price = package["practical_milp_price"].to_numpy(float)
                baseline_completions = float(np.sum(baseline_probability))
                baseline_payout = float(np.sum(baseline_price * baseline_probability))
                base_average_reward = float(np.mean(baseline_price))

                best_gain = -np.inf
                best_rows = []
                for multiplier in PRICE_MULTIPLIERS:
                    average_reward = base_average_reward * float(multiplier)
                    probability, route_length, compactness = estimate_probability(
                        package, local_distances, average_reward
                    )
                    expected_completions = size * probability
                    expected_payout = size * average_reward * probability
                    gain = expected_completions - baseline_completions
                    best_gain = max(best_gain, gain)
                    best_rows.append(
                        {
                            "candidate_id": f"candidate-{len(rows) + len(best_rows) + 1:05d}",
                            "task_ids": ";".join(package["task_id"].astype(str)),
                            "region": int(package["region"].mode().iloc[0]),
                            "task_count": size,
                            "route_length_km": route_length,
                            "compactness": compactness,
                            "price_multiplier": float(multiplier),
                            "average_reward": average_reward,
                            "total_reward": size * average_reward,
                            "bundle_probability": probability,
                            "expected_completions": expected_completions,
                            "expected_payout": expected_payout,
                            "baseline_completions": baseline_completions,
                            "baseline_expected_payout": baseline_payout,
                            "completion_gain": gain,
                            "payout_change": expected_payout - baseline_payout,
                        }
                    )

                # Keep only packages that can plausibly improve completions.
                if best_gain >= 0.03:
                    rows.extend(best_rows)
                    generated_for_seed += 1
                if generated_for_seed >= MAX_CANDIDATES_PER_TASK:
                    break
            if generated_for_seed >= MAX_CANDIDATES_PER_TASK:
                break

    return pd.DataFrame(rows), task_to_index


def solve_bundle_milp(task_data, candidate_options, budget_relaxation):
    total_tasks = len(task_data)
    task_index = {task_id: idx for idx, task_id in enumerate(task_data["task_id"])}
    baseline_completions = float(task_data["practical_milp_probability"].sum())
    baseline_payout = float(
        (task_data["practical_milp_price"] * task_data["practical_milp_probability"]).sum()
    )
    budget_limit = baseline_payout * (1 + budget_relaxation)

    package_keys = candidate_options["task_ids"].to_numpy(str)
    option_count = len(candidate_options)
    rows = []
    cols = []
    values = []
    lower = []
    upper = []

    # A task can be covered by at most one selected package option. Tasks not
    # covered by a selected package remain in the Question 2 single-task scheme.
    for task_id, row_index in task_index.items():
        option_indexes = [
            option_idx
            for option_idx, key in enumerate(package_keys)
            if task_id in key.split(";")
        ]
        if not option_indexes:
            continue
        rows.extend([len(lower)] * len(option_indexes))
        cols.extend(option_indexes)
        values.extend([1.0] * len(option_indexes))
        lower.append(0.0)
        upper.append(1.0)

    # Options with the same exact task set are mutually exclusive price choices.
    for _, group in candidate_options.groupby("task_ids"):
        option_indexes = group.index.to_numpy(int)
        rows.extend([len(lower)] * len(option_indexes))
        cols.extend(option_indexes)
        values.extend([1.0] * len(option_indexes))
        lower.append(0.0)
        upper.append(1.0)

    payout_change = candidate_options["payout_change"].to_numpy(float)
    rows.extend([len(lower)] * option_count)
    cols.extend(range(option_count))
    values.extend(payout_change)
    lower.append(-np.inf)
    upper.append(budget_limit - baseline_payout)

    matrix = coo_matrix((values, (rows, cols)), shape=(len(lower), option_count)).tocsr()
    constraint = LinearConstraint(matrix, np.array(lower), np.array(upper))
    objective = -candidate_options["completion_gain"].to_numpy(float)
    result = milp(
        c=objective,
        integrality=np.ones(option_count, dtype=int),
        bounds=Bounds(np.zeros(option_count), np.ones(option_count)),
        constraints=constraint,
        options={"time_limit": 120, "mip_rel_gap": 1e-6, "presolve": True},
    )
    if result.x is None:
        raise RuntimeError(f"MILP failed: {result.message}")

    selected = candidate_options.loc[result.x > 0.5].copy()
    completion_gain = float(selected["completion_gain"].sum())
    payout_change = float(selected["payout_change"].sum())
    bundled_tasks = sorted({task for key in selected["task_ids"] for task in key.split(";")})
    return {
        "selected": selected,
        "message": result.message,
        "mip_gap": result.mip_gap,
        "budget_relaxation": budget_relaxation,
        "packages": len(selected),
        "bundled_tasks": len(bundled_tasks),
        "expected_payout": baseline_payout + payout_change,
        "expected_completions": baseline_completions + completion_gain,
        "expected_completion_rate": (baseline_completions + completion_gain) / total_tasks,
        "completion_gain_vs_q2": completion_gain,
        "payout_change_vs_q2": payout_change,
    }


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    task_data = pd.read_csv(Q2_RESULTS)
    comparison = pd.read_csv(Q2_COMPARISON)
    practical = comparison.loc[comparison["scheme"] == "practical-milp"].iloc[0]
    candidate_mask = (
        (task_data["practical_milp_probability"] < LOW_PROBABILITY_THRESHOLD)
        & (task_data["practical_price_change"].abs() >= BOUNDARY_CHANGE)
    )
    candidates = task_data.loc[candidate_mask].copy()

    candidate_options, _ = generate_candidate_bundles(candidates)
    candidate_options.to_csv(
        RESULTS_DIR / "optimized-bundle-candidates.csv",
        index=False,
        encoding="utf-8-sig",
    )

    solve_rows = [
        {
            "scheme": "question2-practical-milp",
            "budget_relaxation": 0.0,
            "packages": 0,
            "bundled_tasks": 0,
            "expected_payout": float(practical["expected_payout"]),
            "expected_completions": float(practical["expected_completions"]),
            "expected_completion_rate": float(practical["expected_completion_rate"]),
            "completion_gain_vs_q2": 0.0,
            "payout_change_vs_q2": 0.0,
            "mip_gap": np.nan,
        }
    ]
    selected_frames = []
    for relaxation in BUDGET_RELAXATIONS:
        solution = solve_bundle_milp(task_data, candidate_options, relaxation)
        selected = solution.pop("selected")
        selected["budget_relaxation"] = relaxation
        selected_frames.append(selected)
        solve_rows.append({"scheme": f"optimized-bundle-{int(relaxation*100)}pct-extra", **solution})

    summary = pd.DataFrame(solve_rows)
    summary.to_csv(
        RESULTS_DIR / "optimized-bundle-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    selected_all = pd.concat(selected_frames, ignore_index=True)
    selected_all.to_csv(
        RESULTS_DIR / "optimized-bundle-selected-packages.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if FIRST_COMPARISON.exists():
        first = pd.read_csv(FIRST_COMPARISON)
        first.to_csv(
            RESULTS_DIR / "first-bundle-comparison-copy.csv",
            index=False,
            encoding="utf-8-sig",
        )

    region_rows = []
    for (relaxation, region), group in selected_all.groupby(["budget_relaxation", "region"]):
        region_rows.append(
            {
                "budget_relaxation": relaxation,
                "region": region,
                "packages": len(group),
                "bundled_tasks": len({task for key in group["task_ids"] for task in key.split(";")}),
                "completion_gain": group["completion_gain"].sum(),
                "payout_change": group["payout_change"].sum(),
            }
        )
    pd.DataFrame(region_rows).to_csv(
        RESULTS_DIR / "optimized-bundle-regional-summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), dpi=180)
    labels = summary["scheme"].str.replace("optimized-bundle-", "打包").str.replace("question2-practical-milp", "二问")
    axes[0].bar(labels, summary["expected_completion_rate"] * 100, color="#4E79A7")
    axes[0].set(ylabel="预测完成率/%", title="优化打包总体完成率")
    axes[0].tick_params(axis="x", rotation=18)
    axes[1].bar(labels[1:], summary.loc[1:, "completion_gain_vs_q2"], color="#59A14F")
    axes[1].set(ylabel="较二问增加预计完成任务", title="优化打包增益")
    axes[1].tick_params(axis="x", rotation=18)
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "optimized-bundle-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    print(summary.round(6).to_string(index=False))
    print(f"candidate_options={len(candidate_options)}")
    print(selected_all.groupby("budget_relaxation").size().to_string())


if __name__ == "__main__":
    main()
