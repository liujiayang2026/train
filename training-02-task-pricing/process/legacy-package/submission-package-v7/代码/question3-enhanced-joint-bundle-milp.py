"""Enhanced joint bundle MILP for Question 3.

Enhancements over joint-bundle-milp.py:
1. Candidate bundles use low-probability boundary tasks as cores, but may
   include nearby ride-along tasks with moderate completion probabilities.
2. Bundle price candidates use a finer and wider multiplier grid.
"""

from __future__ import annotations

import importlib.util
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


QUESTION = Path(__file__).resolve().parents[1]
PROJECT = QUESTION.parent
Q2_CODE = PROJECT / "question-2" / "code" / "baseline-pricing.py"
Q2_RESULTS = PROJECT / "question-2" / "results" / "milp-pricing-results.csv"
Q2_COMPARISON = PROJECT / "question-2" / "results" / "milp-comparison.csv"
CURRENT_JOINT = QUESTION / "results" / "joint-bundle-comparison.csv"
RESULTS_DIR = QUESTION / "results"
FIGURES_DIR = QUESTION / "figures"

CORE_PROBABILITY_THRESHOLD = 0.50
RIDE_ALONG_PROBABILITY_THRESHOLD = 0.75
BOUNDARY_CHANGE = 8.0
BUNDLE_RADIUS_KM = 1.0
MAX_BUNDLE_SIZE = 5
MAX_NEIGHBORS = 10
MAX_CANDIDATES_PER_CORE = 120
PRICE_MULTIPLIERS = np.array([0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15])
MAX_PRICE_CHANGE = 8.0
BUDGET_RELAXATIONS = [0.00, 0.01, 0.02]


def load_q2_model():
    spec = importlib.util.spec_from_file_location("baseline_pricing", Q2_CODE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def estimate_bundle_probability(package, local_distances, average_reward):
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
    core_share = float(
        np.mean(
            (package["practical_milp_probability"] < CORE_PROBABILITY_THRESHOLD)
            & (package["practical_price_change"].abs() >= BOUNDARY_CHANGE)
        )
    )

    # Ride-along packages can contain easier tasks, so add a small anchoring
    # benefit when a bundle mixes hard core tasks with moderate-probability
    # nearby tasks, while still penalizing overly diffuse routes.
    ride_along_bonus = 0.12 * (1.0 - core_share)
    route_bonus = (
        0.42 * np.log(task_count)
        + 0.55 * compactness
        + ride_along_bonus
        - 0.07 * (task_count - 1)
        - 0.10 * max(0.0, route_length - BUNDLE_RADIUS_KM)
    )
    utility = mean_logit + slope * (average_reward - base_average_reward)
    return float(sigmoid(utility + route_bonus)), route_length, compactness, core_share


def generate_enhanced_bundle_options(task_data):
    task_data = task_data.copy().reset_index(drop=True)
    points = coordinates_km(task_data)
    distances = distance_matrix(points)
    core_mask = (
        (task_data["practical_milp_probability"] < CORE_PROBABILITY_THRESHOLD)
        & (task_data["practical_price_change"].abs() >= BOUNDARY_CHANGE)
    )
    ride_mask = task_data["practical_milp_probability"] < RIDE_ALONG_PROBABILITY_THRESHOLD
    seen = set()
    rows = []

    for core_index in np.flatnonzero(core_mask.to_numpy()):
        same_region = task_data["region"] == task_data.loc[core_index, "region"]
        nearby = [
            int(index)
            for index in np.flatnonzero((same_region & ride_mask).to_numpy())
            if index != core_index and distances[core_index, index] <= BUNDLE_RADIUS_KM
        ]
        nearby.sort(
            key=lambda index: (
                distances[core_index, index],
                task_data.loc[index, "practical_milp_probability"],
            )
        )
        nearby = nearby[:MAX_NEIGHBORS]
        generated = 0
        for size in range(2, min(MAX_BUNDLE_SIZE, len(nearby) + 1) + 1):
            for tail in combinations(nearby, size - 1):
                combo = tuple(sorted((core_index,) + tail))
                if combo in seen:
                    continue
                seen.add(combo)
                package = task_data.loc[list(combo)].copy()
                if not (
                    (package["practical_milp_probability"] < CORE_PROBABILITY_THRESHOLD)
                    & (package["practical_price_change"].abs() >= BOUNDARY_CHANGE)
                ).any():
                    continue
                local_distances = distances[np.ix_(combo, combo)]
                route_length = mst_length(local_distances)
                average_edge = route_length / max(size - 1, 1)
                max_pair_distance = float(local_distances.max())
                if max_pair_distance > BUNDLE_RADIUS_KM * 1.30:
                    continue
                if average_edge > 0.90:
                    continue

                baseline_probability = package["practical_milp_probability"].to_numpy(float)
                baseline_price = package["practical_milp_price"].to_numpy(float)
                baseline_completions = float(np.sum(baseline_probability))
                baseline_payout = float(np.sum(baseline_price * baseline_probability))
                base_average_reward = float(np.mean(baseline_price))
                best_gain = -np.inf
                option_rows = []

                for multiplier in PRICE_MULTIPLIERS:
                    average_reward = base_average_reward * float(multiplier)
                    probability, route_length, compactness, core_share = estimate_bundle_probability(
                        package, local_distances, average_reward
                    )
                    expected_completions = size * probability
                    expected_payout = size * average_reward * probability
                    gain = expected_completions - baseline_completions
                    best_gain = max(best_gain, gain)
                    option_rows.append(
                        {
                            "task_ids": ";".join(package["task_id"].astype(str)),
                            "region": int(package["region"].mode().iloc[0]),
                            "task_count": size,
                            "core_tasks": int(
                                (
                                    (package["practical_milp_probability"] < CORE_PROBABILITY_THRESHOLD)
                                    & (package["practical_price_change"].abs() >= BOUNDARY_CHANGE)
                                ).sum()
                            ),
                            "ride_along_tasks": int(size - (
                                (package["practical_milp_probability"] < CORE_PROBABILITY_THRESHOLD)
                                & (package["practical_price_change"].abs() >= BOUNDARY_CHANGE)
                            ).sum()),
                            "core_share": core_share,
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
                if best_gain >= 0.03:
                    rows.extend(option_rows)
                    generated += 1
                if generated >= MAX_CANDIDATES_PER_CORE:
                    break
            if generated >= MAX_CANDIDATES_PER_CORE:
                break

    options = pd.DataFrame(rows).drop_duplicates(["task_ids", "price_multiplier"])
    options.insert(0, "candidate_id", [f"enhanced-{i+1:05d}" for i in range(len(options))])
    return options


def build_single_options(model, data, feature_data, coef, means, scales):
    original_price = data["price"]
    task_count = len(original_price)
    rows = []
    for task_index, old_price in enumerate(original_price):
        low = max(model.PRICE_MIN, old_price - MAX_PRICE_CHANGE)
        high = min(model.PRICE_MAX, old_price + MAX_PRICE_CHANGE)
        prices = np.arange(low, high + model.PRICE_STEP / 2, model.PRICE_STEP)
        for price in prices:
            probability = float(
                model.predict(
                    np.full(task_count, price), feature_data, coef, means, scales
                )[task_index]
            )
            rows.append(
                {
                    "option_type": "single",
                    "task_ids": data["task_id"][task_index],
                    "task_count": 1,
                    "price": float(price),
                    "expected_completions": probability,
                    "expected_payout": float(price * probability),
                    "single_probability": probability,
                    "region": int(feature_data["region"][task_index]),
                }
            )
    return pd.DataFrame(rows)


def build_bundle_options(enhanced_candidates):
    return pd.DataFrame(
        {
            "option_type": "bundle",
            "task_ids": enhanced_candidates["task_ids"],
            "task_count": enhanced_candidates["task_count"].astype(int),
            "price": enhanced_candidates["total_reward"].astype(float),
            "expected_completions": enhanced_candidates["expected_completions"].astype(float),
            "expected_payout": enhanced_candidates["expected_payout"].astype(float),
            "single_probability": np.nan,
            "region": enhanced_candidates["region"],
            "route_length_km": enhanced_candidates["route_length_km"],
            "compactness": enhanced_candidates["compactness"],
            "price_multiplier": enhanced_candidates["price_multiplier"],
            "bundle_probability": enhanced_candidates["bundle_probability"],
            "core_tasks": enhanced_candidates["core_tasks"],
            "ride_along_tasks": enhanced_candidates["ride_along_tasks"],
        }
    )


def solve_joint_milp(task_ids, options, budget_limit):
    task_index = {task_id: idx for idx, task_id in enumerate(task_ids)}
    option_count = len(options)
    row_indexes = []
    col_indexes = []
    values = []
    lower = []
    upper = []

    option_task_lists = [str(key).split(";") for key in options["task_ids"]]
    memberships = {task_id: [] for task_id in task_ids}
    for option_index, task_list in enumerate(option_task_lists):
        for task_id in task_list:
            if task_id in memberships:
                memberships[task_id].append(option_index)

    for task_id in task_ids:
        columns = memberships[task_id]
        row_indexes.extend([len(lower)] * len(columns))
        col_indexes.extend(columns)
        values.extend([1.0] * len(columns))
        lower.append(1.0)
        upper.append(1.0)

    row_indexes.extend([len(lower)] * option_count)
    col_indexes.extend(range(option_count))
    values.extend(options["expected_payout"].to_numpy(float))
    lower.append(-np.inf)
    upper.append(float(budget_limit))

    matrix = coo_matrix((values, (row_indexes, col_indexes)), shape=(len(lower), option_count)).tocsr()
    constraint = LinearConstraint(matrix, np.array(lower), np.array(upper))
    result = milp(
        c=-options["expected_completions"].to_numpy(float),
        integrality=np.ones(option_count, dtype=int),
        bounds=Bounds(np.zeros(option_count), np.ones(option_count)),
        constraints=constraint,
        options={"time_limit": 300, "mip_rel_gap": 1e-6, "presolve": True},
    )
    if result.x is None:
        raise RuntimeError(f"MILP failed: {result.message}")
    return options.loc[result.x > 0.5].copy(), result


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    model = load_q2_model()
    data = model.parse_data()
    feature_data = model.make_features(data)
    coef, means, scales, _ = model.fit_model(data, feature_data)
    task_data = pd.read_csv(Q2_RESULTS)
    comparison = pd.read_csv(Q2_COMPARISON)
    practical = comparison.loc[comparison["scheme"] == "practical-milp"].iloc[0]
    budget = float(practical["expected_payout"])

    enhanced_candidates = generate_enhanced_bundle_options(task_data)
    enhanced_candidates.to_csv(
        RESULTS_DIR / "enhanced-bundle-candidates.csv", index=False, encoding="utf-8-sig"
    )
    single_options = build_single_options(model, data, feature_data, coef, means, scales)
    bundle_options = build_bundle_options(enhanced_candidates)
    options = pd.concat([single_options, bundle_options], ignore_index=True)
    options.to_csv(
        RESULTS_DIR / "enhanced-joint-all-options.csv", index=False, encoding="utf-8-sig"
    )

    rows = [
        {
            "scheme": "question2-practical-milp",
            "budget_relaxation": 0.0,
            "packages": 0,
            "bundled_tasks": 0,
            "single_tasks": len(task_data),
            "ride_along_tasks": 0,
            "expected_payout": budget,
            "expected_completions": float(practical["expected_completions"]),
            "expected_completion_rate": float(practical["expected_completion_rate"]),
            "completion_gain_vs_q2": 0.0,
            "payout_change_vs_q2": 0.0,
            "mip_gap": np.nan,
            "message": "baseline",
        }
    ]
    selected_frames = []
    for relaxation in BUDGET_RELAXATIONS:
        selected, result = solve_joint_milp(data["task_id"], options, budget * (1 + relaxation))
        bundle_selected = selected[selected["option_type"] == "bundle"].copy()
        task_set = sorted({task for key in bundle_selected["task_ids"] for task in str(key).split(";")})
        selected["scheme"] = f"enhanced-joint-{int(relaxation*100)}pct-extra"
        selected["budget_relaxation"] = relaxation
        selected_frames.append(selected)
        expected_payout = float(selected["expected_payout"].sum())
        expected_completions = float(selected["expected_completions"].sum())
        rows.append(
            {
                "scheme": f"enhanced-joint-{int(relaxation*100)}pct-extra",
                "budget_relaxation": relaxation,
                "packages": len(bundle_selected),
                "bundled_tasks": len(task_set),
                "single_tasks": int((selected["option_type"] == "single").sum()),
                "ride_along_tasks": int(bundle_selected.get("ride_along_tasks", pd.Series(dtype=float)).sum()),
                "expected_payout": expected_payout,
                "expected_completions": expected_completions,
                "expected_completion_rate": expected_completions / len(task_data),
                "completion_gain_vs_q2": expected_completions - float(practical["expected_completions"]),
                "payout_change_vs_q2": expected_payout - budget,
                "mip_gap": result.mip_gap,
                "message": result.message,
            }
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(
        RESULTS_DIR / "enhanced-joint-bundle-comparison.csv", index=False, encoding="utf-8-sig"
    )
    selected_all = pd.concat(selected_frames, ignore_index=True)
    selected_all.to_csv(
        RESULTS_DIR / "enhanced-joint-selected-options.csv", index=False, encoding="utf-8-sig"
    )

    existing_rows = []
    if CURRENT_JOINT.exists():
        current = pd.read_csv(CURRENT_JOINT)
        for _, row in current.iterrows():
            existing_rows.append({"model": "current-joint", **row.to_dict()})
    for _, row in summary.iterrows():
        existing_rows.append({"model": "enhanced-joint", **row.to_dict()})
    pd.DataFrame(existing_rows).to_csv(
        RESULTS_DIR / "enhanced-vs-current-joint-comparison.csv", index=False, encoding="utf-8-sig"
    )

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), dpi=180)
    labels = ["二问", "增强0%", "增强1%", "增强2%"]
    axes[0].bar(labels, summary["expected_completion_rate"] * 100, color="#4E79A7")
    axes[0].set(ylabel="预测完成率/%", title="增强联合优化完成率")
    axes[1].bar(labels[1:], summary.loc[1:, "completion_gain_vs_q2"], color="#59A14F")
    axes[1].set(ylabel="较二问增加预计完成任务", title="增强候选包增益")
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "enhanced-joint-bundle-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    print(summary.round(6).to_string(index=False))
    print(f"enhanced_bundle_options={len(bundle_options)} single_options={len(single_options)} all_options={len(options)}")


if __name__ == "__main__":
    main()
