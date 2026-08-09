"""Optimized bundled pricing for Question 4.

Improvements over question4_complete.py:
1. Effective member supply weights quota, credit, and distance.
2. Package radius and maximum size adapt to local density and pressure.
3. A global set-partitioning MILP replaces greedy package selection.
4. Every selected package is assigned to a member and consumes that member's
   booking quota.

The original bundled result is retained and used as the fair-cost benchmark.
"""

from __future__ import annotations

import importlib.util
import sys
from itertools import combinations
from pathlib import Path

QUESTION_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = QUESTION_DIR.parent
SHARED_PACKAGES = PROJECT_DIR / "shared" / "python-packages"
if SHARED_PACKAGES.exists():
    sys.path.insert(0, str(SHARED_PACKAGES))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix
from scipy.spatial import cKDTree
from scipy.special import expit, logit
from scipy.stats import rankdata


Q4_CODE = QUESTION_DIR / "code" / "question4_complete.py"
BASELINE_COMPARISON = (
    QUESTION_DIR / "results" / "question4-scheme-comparison.csv"
)
BASELINE_TASK_RESULTS = (
    QUESTION_DIR / "results" / "question4-task-pricing.csv"
)
RESULTS_DIR = QUESTION_DIR / "results"
DOCS_DIR = QUESTION_DIR / "docs"
FIGURES_DIR = QUESTION_DIR / "figures"

PRICE_MIN = 65.0
PRICE_MAX = 85.0
PRICE_STEP = 0.5
TARGET_PROBABILITY = 0.75
SUPPLY_RADIUS_KM = 2.0
SUPPLY_DISTANCE_SCALE_KM = 1.5
PRESSURE_LOGIT_PENALTY = 0.65
MAX_NEIGHBORS = 6
MAX_CANDIDATES_PER_CORE = 12
MEMBER_OPTIONS_PER_PACKAGE = 40
MAX_ASSIGNMENT_DISTANCE_KM = 20.0
MIP_TIME_LIMIT_SECONDS = 90
MIP_REL_GAP = 0.005
RANDOM_SEED = 2026


def load_q4_module():
    spec = importlib.util.spec_from_file_location("question4_complete", Q4_CODE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def effective_member_weights(member_quota, member_credit):
    positive_quota = member_quota[member_quota > 0]
    quota_median = float(np.median(positive_quota))
    quota_weight = np.sqrt(np.maximum(member_quota, 0.0) / quota_median)
    quota_weight = np.clip(quota_weight, 0.35, 3.0)

    # Percentile ranks prevent a handful of very large credit values from
    # dominating the supply calculation.
    credit_percentile = rankdata(member_credit, method="average") / len(
        member_credit
    )
    credit_weight = 0.5 + credit_percentile
    combined = quota_weight * credit_weight
    return combined / np.mean(combined)


def calculate_effective_supply(task_xy, member_xy, member_weight):
    tree = cKDTree(member_xy)
    neighbor_lists = tree.query_ball_point(task_xy, SUPPLY_RADIUS_KM)
    supply = np.zeros(len(task_xy), dtype=float)
    for index, neighbors in enumerate(neighbor_lists):
        if not neighbors:
            continue
        neighbors = np.asarray(neighbors, dtype=int)
        distances = np.linalg.norm(
            member_xy[neighbors] - task_xy[index], axis=1
        )
        distance_weight = np.exp(-distances / SUPPLY_DISTANCE_SCALE_KM)
        supply[index] = np.sum(member_weight[neighbors] * distance_weight)
    return supply


def build_effective_pressure(
    q4, historical_data, historical_features, new_features
):
    member_weight = effective_member_weights(
        historical_data["member_quota"], historical_data["member_credit"]
    )
    latitude_center = float(
        np.mean(
            np.concatenate(
                (
                    historical_data["lat"],
                    new_features["xy"][:, 1] / 111.0,
                )
            )
        )
    )
    historical_xy = q4.coordinates_km(
        historical_data["lat"], historical_data["lon"], latitude_center
    )
    member_xy = q4.coordinates_km(
        historical_data["member_lat"],
        historical_data["member_lon"],
        latitude_center,
    )

    # Rebuild the new task/member coordinates with one shared projection.
    new_lat = new_features["xy"][:, 1] / 111.0
    # The old x projection used nearly the same center. Recover longitude from
    # the original feature projection only for compatibility; the caller
    # immediately replaces this with exact new coordinates below.
    old_center = float(np.mean(new_lat))
    new_lon = new_features["xy"][:, 0] / (
        111.0 * np.cos(np.radians(old_center))
    )
    new_xy = q4.coordinates_km(new_lat, new_lon, latitude_center)

    historical_supply = calculate_effective_supply(
        historical_xy, member_xy, member_weight
    )
    new_supply = calculate_effective_supply(new_xy, member_xy, member_weight)
    historical_pressure = (
        historical_features["tasks_2km"] + 1
    ) / (historical_supply + 1)
    pressure_reference = float(np.percentile(historical_pressure, 95))
    new_pressure = (new_features["tasks_2km"] + 1) / (new_supply + 1)
    new_penalty = PRESSURE_LOGIT_PENALTY * np.maximum(
        0.0,
        np.log(np.maximum(new_pressure, 1e-9) / pressure_reference),
    )
    return {
        "member_weight": member_weight,
        "member_xy": member_xy,
        "historical_supply": historical_supply,
        "new_supply": new_supply,
        "historical_pressure": historical_pressure,
        "pressure_reference": pressure_reference,
        "new_pressure": new_pressure,
        "new_penalty": new_penalty,
    }


def build_base_price_logits(
    model, features, coefficient, means, scales
):
    price_grid = np.arange(
        PRICE_MIN, PRICE_MAX + PRICE_STEP / 2, PRICE_STEP
    )
    logits = []
    for price in price_grid:
        base_probability = model.predict(
            np.full(len(features["region"]), price),
            features,
            coefficient,
            means,
            scales,
        )
        logits.append(
            logit(np.clip(base_probability, 1e-6, 1 - 1e-6))
            - features["congestion_penalty"]
        )
    return price_grid, np.column_stack(logits)


def adaptive_rules(tasks_2km, effective_supply, effective_pressure):
    density_q25, density_q50 = np.percentile(tasks_2km, [25, 50])
    supply_q50 = float(np.percentile(effective_supply, 50))
    pressure_q75 = float(np.percentile(effective_pressure, 75))

    max_size = np.full(len(tasks_2km), 4, dtype=int)
    radius = np.full(len(tasks_2km), 0.40, dtype=float)

    high_pressure = effective_pressure >= pressure_q75
    dense_supported = (tasks_2km >= density_q50) & (
        effective_supply >= supply_q50
    )
    sparse = tasks_2km <= density_q25

    max_size[high_pressure] = 3
    radius[high_pressure] = 0.25
    max_size[dense_supported & ~high_pressure] = 5
    radius[dense_supported & ~high_pressure] = 0.35
    max_size[sparse] = 2
    radius[sparse] = 0.55

    return max_size, radius


def package_bonus(size, spread_km, allowed_radius_km):
    if size <= 1:
        return 0.0, 1.0
    compactness = max(
        0.0, 1.0 - spread_km / max(allowed_radius_km, 1e-6)
    )
    bonus = (
        0.38 * np.log(size)
        + 0.12 * compactness
        - 0.025 * (size - 1) ** 2
    )
    return float(max(0.0, bonus)), compactness


def evaluate_candidate(indexes, xy, max_size, radius, price_grid, base_logits):
    indexes = tuple(sorted(indexes))
    size = len(indexes)
    allowed_radius = float(np.min(radius[list(indexes)]))
    if size > int(np.min(max_size[list(indexes)])):
        return None

    points = xy[list(indexes)]
    centroid = points.mean(axis=0)
    spread = float(np.max(np.linalg.norm(points - centroid, axis=1)))
    pairwise = np.linalg.norm(
        points[:, None, :] - points[None, :, :], axis=2
    )
    if size > 1 and float(pairwise.max()) > allowed_radius * 1.25:
        return None

    bonus, compactness = package_bonus(
        size, spread, allowed_radius
    )
    local_logits = base_logits[list(indexes)] + bonus
    probabilities = expit(local_logits)
    reaches = probabilities >= TARGET_PROBABILITY
    first = np.argmax(reaches, axis=1)
    unreachable = ~reaches.any(axis=1)
    first[unreachable] = len(price_grid) - 1
    task_prices = price_grid[first]
    task_probabilities = probabilities[np.arange(size), first]

    return {
        "tasks": indexes,
        "task_count": size,
        "centroid_x": float(centroid[0]),
        "centroid_y": float(centroid[1]),
        "spread_km": spread,
        "allowed_radius_km": allowed_radius,
        "compactness": compactness,
        "bundle_logit_bonus": bonus,
        "task_prices": task_prices,
        "task_probabilities": task_probabilities,
        "posted_total": float(np.sum(task_prices)),
        "expected_payout": float(np.sum(task_prices * task_probabilities)),
        "expected_completions": float(np.sum(task_probabilities)),
        "target_reached_tasks": int(
            np.sum(task_probabilities >= TARGET_PROBABILITY)
        ),
        "unreachable_at_85_tasks": int(np.sum(unreachable)),
    }


def generate_candidates(
    new_tasks, xy, max_size, radius, price_grid, base_logits
):
    tree = cKDTree(xy)
    exact_key = list(
        zip(
            new_tasks["latitude"].round(6),
            new_tasks["longitude"].round(6),
        )
    )
    exact_map = {}
    for index, key in enumerate(exact_key):
        exact_map.setdefault(key, []).append(index)

    candidate_map = {}

    def add_candidate(indexes):
        key = tuple(sorted(set(int(i) for i in indexes)))
        if not key or key in candidate_map:
            return
        evaluated = evaluate_candidate(
            key, xy, max_size, radius, price_grid, base_logits
        )
        if evaluated is not None:
            candidate_map[key] = evaluated

    for index in range(len(new_tasks)):
        add_candidate((index,))

    for core in range(len(new_tasks)):
        neighbors = tree.query_ball_point(xy[core], float(radius[core]))
        neighbors = [
            int(index) for index in neighbors if int(index) != core
        ]
        neighbors.sort(key=lambda index: np.linalg.norm(xy[index] - xy[core]))
        neighbors = neighbors[:MAX_NEIGHBORS]
        local = [core] + neighbors

        proposals = []
        for neighbor in neighbors:
            proposals.append((core, neighbor))
        for size in range(3, min(int(max_size[core]), len(local)) + 1):
            proposals.append(tuple(local[:size]))
        top = neighbors[:4]
        for size in range(2, min(int(max_size[core]), len(top) + 1) + 1):
            for tail in combinations(top, size - 1):
                proposals.append((core,) + tail)

        exact_group = exact_map[exact_key[core]]
        if len(exact_group) > 1:
            exact_neighbors = [
                index for index in exact_group if index != core
            ][: MAX_NEIGHBORS]
            for size in range(
                2, min(5, len(exact_neighbors) + 1) + 1
            ):
                proposals.append((core,) + tuple(exact_neighbors[: size - 1]))

        scored = []
        for proposal in proposals:
            key = tuple(sorted(set(proposal)))
            if len(key) < 2:
                continue
            points = xy[list(key)]
            spread = float(
                np.max(
                    np.linalg.norm(points - points.mean(axis=0), axis=1)
                )
            )
            score = len(key) - spread / max(float(radius[core]), 1e-6)
            scored.append((score, key))
        scored.sort(reverse=True)
        seen_local = set()
        accepted = 0
        for _, key in scored:
            if key in seen_local:
                continue
            seen_local.add(key)
            before = len(candidate_map)
            add_candidate(key)
            if len(candidate_map) > before:
                accepted += 1
            if accepted >= MAX_CANDIDATES_PER_CORE:
                break

    candidates = list(candidate_map.values())
    for candidate_id, candidate in enumerate(candidates, start=1):
        candidate["candidate_id"] = candidate_id
    return candidates


def candidate_member_options(
    candidates,
    member_xy,
    member_weight,
):
    member_tree = cKDTree(member_xy)
    variable_rows = []
    for candidate_index, candidate in enumerate(candidates):
        centroid = np.array(
            [candidate["centroid_x"], candidate["centroid_y"]]
        )
        k = min(40, len(member_xy))
        distances, members = member_tree.query(centroid, k=k)
        distances = np.atleast_1d(distances)
        members = np.atleast_1d(members).astype(int)
        score = member_weight[members] * np.exp(
            -distances / SUPPLY_DISTANCE_SCALE_KM
        )
        order = np.argsort(-score)
        chosen = []
        for position in order:
            member = int(members[position])
            distance = float(distances[position])
            if (
                distance <= MAX_ASSIGNMENT_DISTANCE_KM
                or not chosen
            ):
                chosen.append((member, distance, float(score[position])))
            if len(chosen) >= MEMBER_OPTIONS_PER_PACKAGE:
                break

        for member, distance, assignment_score in chosen:
            variable_rows.append(
                {
                    "candidate_index": candidate_index,
                    "member_index": member,
                    "member_distance_km": distance,
                    "assignment_score": assignment_score,
                }
            )
    return variable_rows


def solve_milp(
    candidates,
    variable_rows,
    task_count,
    member_quota,
    expected_payout_budget,
    objective_mode="completion",
):
    variable_count = len(variable_rows)
    member_count = len(member_quota)
    budget_row = task_count + member_count
    row_indexes = []
    col_indexes = []
    values = []

    for variable_index, option in enumerate(variable_rows):
        candidate = candidates[option["candidate_index"]]
        for task in candidate["tasks"]:
            row_indexes.append(int(task))
            col_indexes.append(variable_index)
            values.append(1.0)
        row_indexes.append(task_count + option["member_index"])
        col_indexes.append(variable_index)
        values.append(float(candidate["task_count"]))
        row_indexes.append(budget_row)
        col_indexes.append(variable_index)
        values.append(float(candidate["expected_payout"]))

    matrix = coo_matrix(
        (values, (row_indexes, col_indexes)),
        shape=(budget_row + 1, variable_count),
    ).tocsr()
    lower = np.full(budget_row + 1, -np.inf)
    upper = np.full(budget_row + 1, np.inf)
    lower[:task_count] = 1.0
    upper[:task_count] = 1.0
    upper[task_count : task_count + member_count] = member_quota
    if expected_payout_budget is not None:
        upper[budget_row] = expected_payout_budget

    objective = np.zeros(variable_count)
    for index, option in enumerate(variable_rows):
        candidate = candidates[option["candidate_index"]]
        if objective_mode == "cost":
            objective[index] = (
                candidate["expected_payout"]
                + 1e-5 * option["member_distance_km"]
            )
        else:
            objective[index] = (
                -candidate["expected_completions"]
                + 1e-6 * candidate["expected_payout"]
                + 1e-5 * option["member_distance_km"]
            )

    result = milp(
        c=objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(np.zeros(variable_count), np.ones(variable_count)),
        constraints=LinearConstraint(matrix, lower, upper),
        options={
            "time_limit": MIP_TIME_LIMIT_SECONDS,
            "mip_rel_gap": MIP_REL_GAP,
            "presolve": True,
        },
    )
    if result.x is None:
        raise RuntimeError(f"MILP failed: {result.message}")
    selected_variables = np.flatnonzero(result.x > 0.5)
    return result, selected_variables


def solve_package_selection(candidates, task_count, expected_payout_budget):
    """Select a disjoint package cover before assigning packages to members."""
    variable_count = len(candidates)
    budget_row = task_count
    row_indexes = []
    col_indexes = []
    values = []
    for candidate_index, candidate in enumerate(candidates):
        for task in candidate["tasks"]:
            row_indexes.append(int(task))
            col_indexes.append(candidate_index)
            values.append(1.0)
        row_indexes.append(budget_row)
        col_indexes.append(candidate_index)
        values.append(float(candidate["expected_payout"]))

    matrix = coo_matrix(
        (values, (row_indexes, col_indexes)),
        shape=(task_count + 1, variable_count),
    ).tocsr()
    lower = np.full(task_count + 1, -np.inf)
    upper = np.full(task_count + 1, np.inf)
    lower[:task_count] = 1.0
    upper[:task_count] = 1.0
    upper[budget_row] = expected_payout_budget
    objective = np.array(
        [
            -candidate["expected_completions"]
            + 1e-6 * candidate["expected_payout"]
            for candidate in candidates
        ]
    )
    result = milp(
        c=objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(np.zeros(variable_count), np.ones(variable_count)),
        constraints=LinearConstraint(matrix, lower, upper),
        options={
            "time_limit": 60,
            "mip_rel_gap": MIP_REL_GAP,
            "presolve": True,
        },
    )
    if result.x is None:
        raise RuntimeError(
            f"Package-selection MILP failed: {result.message}"
        )
    return result, np.flatnonzero(result.x > 0.5)


def solve_member_assignment(candidates, variable_rows, member_quota):
    """Assign each already-selected package to one member under quota."""
    package_count = len(candidates)
    member_count = len(member_quota)
    variable_count = len(variable_rows)
    row_indexes = []
    col_indexes = []
    values = []
    for variable_index, option in enumerate(variable_rows):
        candidate_index = option["candidate_index"]
        candidate = candidates[candidate_index]
        row_indexes.append(candidate_index)
        col_indexes.append(variable_index)
        values.append(1.0)
        row_indexes.append(package_count + option["member_index"])
        col_indexes.append(variable_index)
        values.append(float(candidate["task_count"]))

    matrix = coo_matrix(
        (values, (row_indexes, col_indexes)),
        shape=(package_count + member_count, variable_count),
    ).tocsr()
    lower = np.full(package_count + member_count, -np.inf)
    upper = np.full(package_count + member_count, np.inf)
    lower[:package_count] = 1.0
    upper[:package_count] = 1.0
    upper[package_count:] = member_quota
    objective = np.array(
        [
            option["member_distance_km"]
            - 0.01 * np.log1p(option["assignment_score"])
            for option in variable_rows
        ]
    )
    result = milp(
        c=objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(np.zeros(variable_count), np.ones(variable_count)),
        constraints=LinearConstraint(matrix, lower, upper),
        options={
            "time_limit": 45,
            "mip_rel_gap": MIP_REL_GAP,
            "presolve": True,
        },
    )
    if result.x is None:
        raise RuntimeError(
            f"Member-assignment MILP failed: {result.message}"
        )
    return result, np.flatnonzero(result.x > 0.5)


def build_outputs(
    q4,
    new_tasks,
    features,
    supply_data,
    max_size,
    radius,
    candidates,
    variable_rows,
    selected_variables,
    historical_data,
    result,
):
    task_rows = [None] * len(new_tasks)
    package_rows = []
    member_usage = np.zeros(len(historical_data["member_quota"]))

    for package_number, variable_index in enumerate(
        selected_variables, start=1
    ):
        option = variable_rows[variable_index]
        candidate = candidates[option["candidate_index"]]
        package_id = f"OP{package_number:04d}"
        member_index = option["member_index"]
        member_usage[member_index] += candidate["task_count"]
        task_ids = [
            new_tasks.loc[index, "task_id"] for index in candidate["tasks"]
        ]
        package_rows.append(
            {
                "package_id": package_id,
                "task_count": candidate["task_count"],
                "task_ids": ";".join(task_ids),
                "assigned_member_index": member_index,
                "assigned_member_id": str(
                    historical_data["members"].iloc[member_index, 0]
                ),
                "member_distance_km": option["member_distance_km"],
                "member_quota": historical_data["member_quota"][
                    member_index
                ],
                "spread_km": candidate["spread_km"],
                "allowed_radius_km": candidate["allowed_radius_km"],
                "compactness": candidate["compactness"],
                "bundle_logit_bonus": candidate["bundle_logit_bonus"],
                "average_price": float(
                    np.mean(candidate["task_prices"])
                ),
                "total_reward": candidate["posted_total"],
                "expected_payout": candidate["expected_payout"],
                "expected_completions": candidate["expected_completions"],
                "average_probability": candidate[
                    "expected_completions"
                ]
                / candidate["task_count"],
            }
        )
        for local_index, task_index in enumerate(candidate["tasks"]):
            task_rows[task_index] = {
                "task_id": new_tasks.loc[task_index, "task_id"],
                "latitude": new_tasks.loc[task_index, "latitude"],
                "longitude": new_tasks.loc[task_index, "longitude"],
                "city": new_tasks.loc[task_index, "city"],
                "package_id": package_id,
                "package_size": candidate["task_count"],
                "assigned_member_id": str(
                    historical_data["members"].iloc[member_index, 0]
                ),
                "assigned_member_distance_km": option[
                    "member_distance_km"
                ],
                "nearest_member_km": features["nearest_member_km"][
                    task_index
                ],
                "tasks_2km": features["tasks_2km"][task_index],
                "members_2km": features["members_2km"][task_index],
                "effective_member_supply": supply_data["new_supply"][
                    task_index
                ],
                "effective_pressure": supply_data["new_pressure"][
                    task_index
                ],
                "adaptive_max_package_size": max_size[task_index],
                "adaptive_radius_km": radius[task_index],
                "bundle_logit_bonus": candidate["bundle_logit_bonus"],
                "optimized_price": candidate["task_prices"][
                    local_index
                ],
                "optimized_probability": candidate[
                    "task_probabilities"
                ][local_index],
                "target_reached": candidate["task_probabilities"][
                    local_index
                ]
                >= TARGET_PROBABILITY,
                "unreachable_at_85": (
                    candidate["task_prices"][local_index] == PRICE_MAX
                    and candidate["task_probabilities"][local_index]
                    < TARGET_PROBABILITY
                ),
            }

    task_results = pd.DataFrame(task_rows)
    package_results = pd.DataFrame(package_rows)
    used_member_indexes = np.flatnonzero(member_usage > 0)
    member_results = pd.DataFrame(
        {
            "member_index": used_member_indexes,
            "member_id": [
                str(historical_data["members"].iloc[index, 0])
                for index in used_member_indexes
            ],
            "quota": historical_data["member_quota"][
                used_member_indexes
            ],
            "assigned_tasks": member_usage[used_member_indexes],
        }
    )
    member_results["capacity_utilization"] = (
        member_results["assigned_tasks"] / member_results["quota"]
    )

    summary = {
        "scheme": "optimized-bundled-pricing",
        "average_price": float(task_results["optimized_price"].mean()),
        "posted_total": float(task_results["optimized_price"].sum()),
        "expected_payout": float(
            np.sum(
                task_results["optimized_price"]
                * task_results["optimized_probability"]
            )
        ),
        "expected_completions": float(
            task_results["optimized_probability"].sum()
        ),
        "expected_completion_rate": float(
            task_results["optimized_probability"].mean()
        ),
        "target_reached_tasks": int(task_results["target_reached"].sum()),
        "unreachable_at_85_tasks": int(
            task_results["unreachable_at_85"].sum()
        ),
        "tasks_at_65": int(
            np.sum(task_results["optimized_price"] == PRICE_MIN)
        ),
        "tasks_at_85": int(
            np.sum(task_results["optimized_price"] == PRICE_MAX)
        ),
        "bundled_tasks": int(
            np.sum(task_results["package_size"] > 1)
        ),
        "packages": int(np.sum(package_results["task_count"] > 1)),
        "total_packages": len(package_results),
        "assigned_members": len(member_results),
        "maximum_member_utilization": float(
            member_results["capacity_utilization"].max()
        ),
        "mip_gap": float(result.mip_gap)
        if result.mip_gap is not None
        else np.nan,
        "solver_message": result.message,
    }
    return task_results, package_results, member_results, summary


def save_comparison_figure(comparison):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.4))
    labels = ["Original bundle", "Optimized bundle"]
    colors = ["#64748B", "#0F766E"]
    completion = comparison["expected_completion_rate"].to_numpy() * 100
    price = comparison["average_price"].to_numpy()
    axes[0].bar(labels, completion, color=colors)
    axes[0].set_ylabel("Expected completion rate (%)")
    axes[0].set_ylim(0, max(80, completion.max() + 5))
    axes[0].set_title("Completion effect")
    axes[1].bar(labels, price, color=colors)
    axes[1].set_ylabel("Average price (yuan/task)")
    axes[1].set_ylim(0, max(90, price.max() + 5))
    axes[1].set_title("Price comparison")
    for axis, values, suffix in [
        (axes[0], completion, "%"),
        (axes[1], price, ""),
    ]:
        for index, value in enumerate(values):
            axis.text(
                index,
                value + 0.8,
                f"{value:.2f}{suffix}",
                ha="center",
            )
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "optimized-bundle-comparison.png", dpi=180
    )
    plt.close(fig)


def reevaluate_original_packages(new_tasks, base_logits):
    """Evaluate the old greedy package structure with the updated model."""
    old = pd.read_csv(BASELINE_TASK_RESULTS).set_index("task_id")
    old = old.loc[new_tasks["task_id"]].reset_index()
    updated_bonus = np.zeros(len(old))
    for _, group in old.groupby("package_id"):
        indexes = group.index.to_numpy()
        size = len(indexes)
        spread = float(group["package_spread_km"].max())
        bonus, _ = package_bonus(size, spread, 0.35)
        updated_bonus[indexes] = bonus
    price = old["bundled_price"].to_numpy(float)
    price_index = np.rint((price - PRICE_MIN) / PRICE_STEP).astype(int)
    price_index = np.clip(price_index, 0, base_logits.shape[1] - 1)
    probability = expit(
        base_logits[np.arange(len(old)), price_index] + updated_bonus
    )
    probability_at_85 = expit(base_logits[:, -1] + updated_bonus)
    package_size = old["package_size"].to_numpy(int)
    return {
        "scheme": "original-bundle-updated-model",
        "average_price": float(np.mean(price)),
        "posted_total": float(np.sum(price)),
        "expected_payout": float(np.sum(price * probability)),
        "expected_completions": float(np.sum(probability)),
        "expected_completion_rate": float(np.mean(probability)),
        "target_reached_tasks": int(np.sum(probability >= TARGET_PROBABILITY)),
        "unreachable_at_85_tasks": int(
            np.sum(probability_at_85 < TARGET_PROBABILITY)
        ),
        "tasks_at_65": int(np.sum(price == PRICE_MIN)),
        "tasks_at_85": int(np.sum(price == PRICE_MAX)),
        "bundled_tasks": int(np.sum(package_size > 1)),
        "packages": int(
            old.loc[old["package_size"] > 1, "package_id"].nunique()
        ),
        "total_packages": int(old["package_id"].nunique()),
        "assigned_members": np.nan,
        "maximum_member_utilization": np.nan,
        "mip_gap": np.nan,
        "solver_message": "re-evaluated with effective supply model",
    }


def main():
    np.random.seed(RANDOM_SEED)
    q4 = load_q4_module()
    model = q4.load_q2_model()
    model.MEMBER_XLSX = next(
        path
        for path in PROJECT_DIR.glob("*.xlsx")
        if not path.name.startswith("~$")
    )
    historical_data = model.parse_data()
    # Keep the raw member frame for assignment output.
    historical_data["members"] = pd.read_excel(model.MEMBER_XLSX)
    historical_features = model.make_features(historical_data)
    coefficient, means, scales, _ = model.fit_model(
        historical_data, historical_features
    )
    new_tasks = q4.load_new_tasks()
    new_features = q4.build_new_features(
        model, historical_data, historical_features, new_tasks
    )

    # Recompute exact shared-projection coordinates to avoid depending on the
    # projection stored in the earlier script.
    latitude_center = float(
        np.mean(
            np.concatenate(
                (
                    historical_data["lat"],
                    new_tasks["latitude"].to_numpy(float),
                )
            )
        )
    )
    new_xy = q4.coordinates_km(
        new_tasks["latitude"].to_numpy(float),
        new_tasks["longitude"].to_numpy(float),
        latitude_center,
    )
    member_xy = q4.coordinates_km(
        historical_data["member_lat"],
        historical_data["member_lon"],
        latitude_center,
    )
    historical_xy = q4.coordinates_km(
        historical_data["lat"],
        historical_data["lon"],
        latitude_center,
    )
    member_weight = effective_member_weights(
        historical_data["member_quota"],
        historical_data["member_credit"],
    )
    historical_supply = calculate_effective_supply(
        historical_xy, member_xy, member_weight
    )
    new_supply = calculate_effective_supply(
        new_xy, member_xy, member_weight
    )
    historical_pressure = (
        historical_features["tasks_2km"] + 1
    ) / (historical_supply + 1)
    pressure_reference = float(
        np.percentile(historical_pressure, 95)
    )
    new_pressure = (new_features["tasks_2km"] + 1) / (new_supply + 1)
    new_penalty = PRESSURE_LOGIT_PENALTY * np.maximum(
        0.0, np.log(np.maximum(new_pressure, 1e-9) / pressure_reference)
    )
    supply_data = {
        "member_weight": member_weight,
        "member_xy": member_xy,
        "historical_supply": historical_supply,
        "new_supply": new_supply,
        "historical_pressure": historical_pressure,
        "pressure_reference": pressure_reference,
        "new_pressure": new_pressure,
        "new_penalty": new_penalty,
    }
    new_features["pressure"] = new_pressure
    new_features["pressure_reference"] = pressure_reference
    new_features["congestion_penalty"] = new_penalty
    new_features["xy"] = new_xy

    max_size, radius = adaptive_rules(
        new_features["tasks_2km"], new_supply, new_pressure
    )
    price_grid, base_logits = build_base_price_logits(
        model, new_features, coefficient, means, scales
    )
    candidates = generate_candidates(
        new_tasks,
        new_xy,
        max_size,
        radius,
        price_grid,
        base_logits,
    )
    baseline = pd.read_csv(BASELINE_COMPARISON)
    baseline_bundle = baseline.loc[
        baseline["scheme"] == "bundled-pricing"
    ].iloc[0]
    original_expected_payout_budget = float(
        baseline_bundle["expected_payout"]
    )
    expected_payout_budget = original_expected_payout_budget
    package_result, selected_candidate_indexes = solve_package_selection(
        candidates,
        len(new_tasks),
        expected_payout_budget,
    )
    selected_candidates = [
        candidates[index] for index in selected_candidate_indexes
    ]
    variable_rows = candidate_member_options(
        selected_candidates, member_xy, member_weight
    )
    assignment_result, selected_variables = solve_member_assignment(
        selected_candidates,
        variable_rows,
        historical_data["member_quota"],
    )

    new_tasks["city"] = q4.assign_cities(new_tasks)
    (
        task_results,
        package_results,
        member_results,
        optimized_summary,
    ) = build_outputs(
        q4,
        new_tasks,
        new_features,
        supply_data,
        max_size,
        radius,
        selected_candidates,
        variable_rows,
        selected_variables,
        historical_data,
        package_result,
    )

    baseline_row = {
        "scheme": "original-bundled-pricing",
        "average_price": float(baseline_bundle["average_price"]),
        "posted_total": float(baseline_bundle["posted_total"]),
        "expected_payout": float(baseline_bundle["expected_payout"]),
        "expected_completions": float(
            baseline_bundle["expected_completions"]
        ),
        "expected_completion_rate": float(
            baseline_bundle["expected_completion_rate"]
        ),
        "target_reached_tasks": int(
            baseline_bundle["target_reached_tasks"]
        ),
        "unreachable_at_85_tasks": int(
            baseline_bundle["unreachable_at_85_tasks"]
        ),
        "tasks_at_65": int(baseline_bundle["tasks_at_65"]),
        "tasks_at_85": int(baseline_bundle["tasks_at_85"]),
        "bundled_tasks": int(baseline_bundle["bundled_tasks"]),
        "packages": int(baseline_bundle["packages"]),
        "total_packages": np.nan,
        "assigned_members": np.nan,
        "maximum_member_utilization": np.nan,
        "mip_gap": np.nan,
        "solver_message": "baseline",
    }
    updated_baseline_row = reevaluate_original_packages(
        new_tasks, base_logits
    )
    comparison = pd.DataFrame(
        [baseline_row, updated_baseline_row, optimized_summary]
    )
    numeric_columns = [
        "average_price",
        "posted_total",
        "expected_payout",
        "expected_completions",
        "expected_completion_rate",
        "target_reached_tasks",
        "unreachable_at_85_tasks",
        "tasks_at_65",
        "tasks_at_85",
        "bundled_tasks",
        "packages",
    ]
    delta = {
        "scheme": "optimized-minus-original",
        **{
            column: comparison.loc[2, column] - comparison.loc[1, column]
            for column in numeric_columns
        },
        "total_packages": np.nan,
        "assigned_members": np.nan,
        "maximum_member_utilization": np.nan,
        "mip_gap": optimized_summary["mip_gap"],
        "solver_message": "difference",
    }
    comparison = pd.concat(
        [comparison, pd.DataFrame([delta])], ignore_index=True
    )

    city_summary = (
        task_results.groupby("city", as_index=False)
        .agg(
            tasks=("task_id", "count"),
            average_price=("optimized_price", "mean"),
            expected_completion_rate=("optimized_probability", "mean"),
            median_effective_supply=("effective_member_supply", "median"),
            median_effective_pressure=("effective_pressure", "median"),
            average_package_size=("package_size", "mean"),
            target_reached_share=("target_reached", "mean"),
        )
        .sort_values("tasks", ascending=False)
    )

    task_results.to_csv(
        RESULTS_DIR / "optimized-bundle-task-pricing.csv",
        index=False,
        encoding="utf-8-sig",
    )
    package_results.to_csv(
        RESULTS_DIR / "optimized-bundle-packages.csv",
        index=False,
        encoding="utf-8-sig",
    )
    member_results.to_csv(
        RESULTS_DIR / "optimized-member-capacity.csv",
        index=False,
        encoding="utf-8-sig",
    )
    city_summary.to_csv(
        RESULTS_DIR / "optimized-bundle-city-summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    comparison.to_csv(
        RESULTS_DIR / "optimized-vs-original-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    save_comparison_figure(comparison.iloc[[1, 2]])

    summary_text = f"""Question 4 optimized bundle run
================================
Tasks: {len(new_tasks)}
Candidate packages: {len(candidates)}
MILP variables with member assignments: {len(variable_rows)}
Historical effective-pressure P95: {pressure_reference:.6f}
New effective-pressure median: {np.median(new_pressure):.6f}
Original and optimization expected-payout budget: {expected_payout_budget:.6f}
Package solver status: {package_result.message}
Package MIP gap: {package_result.mip_gap}
Assignment solver status: {assignment_result.message}
Assignment MIP gap: {assignment_result.mip_gap}

{comparison.to_string(index=False)}

Capacity checks
---------------
Assigned members: {len(member_results)}
Maximum member capacity utilization: {member_results['capacity_utilization'].max():.6f}
Members over quota: {int(np.sum(member_results['capacity_utilization'] > 1 + 1e-9))}
Selected packages: {len(package_results)}
Selected multi-task packages: {int(np.sum(package_results['task_count'] > 1))}
Maximum package size: {int(package_results['task_count'].max())}
"""
    (DOCS_DIR / "optimized-run-summary.txt").write_text(
        summary_text, encoding="utf-8"
    )
    print(summary_text)


if __name__ == "__main__":
    main()
