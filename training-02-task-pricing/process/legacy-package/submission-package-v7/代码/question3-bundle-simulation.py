"""Initial bundled-task simulation for Question 3.

The script starts from the Question 2 practical MILP task-level results,
forms short-distance bundles among low-probability boundary tasks, and
compares bundled release with the single-task practical MILP baseline.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


QUESTION = Path(__file__).resolve().parents[1]
PROJECT = QUESTION.parent
Q2_RESULTS = PROJECT / "question-2" / "results" / "milp-pricing-results.csv"
Q2_COMPARISON = PROJECT / "question-2" / "results" / "milp-comparison.csv"
RESULTS_DIR = QUESTION / "results"
FIGURES_DIR = QUESTION / "figures"

LOW_PROBABILITY_THRESHOLD = 0.50
BOUNDARY_CHANGE = 8.0
BUNDLE_RADIUS_KM = 1.0
MIN_BUNDLE_SIZE = 2
MAX_BUNDLE_SIZE = 5


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
    task_count = distances.shape[0]
    if task_count <= 1:
        return 0.0

    selected = np.zeros(task_count, dtype=bool)
    selected[0] = True
    length = 0.0
    for _ in range(task_count - 1):
        best_distance = np.inf
        best_index = -1
        for i in np.flatnonzero(selected):
            candidates = np.flatnonzero(~selected)
            if len(candidates) == 0:
                break
            candidate_distances = distances[i, candidates]
            local_position = int(np.argmin(candidate_distances))
            if candidate_distances[local_position] < best_distance:
                best_distance = float(candidate_distances[local_position])
                best_index = int(candidates[local_position])
        selected[best_index] = True
        length += best_distance
    return length


def form_bundles(candidate_frame):
    candidate_frame = candidate_frame.copy().reset_index(drop=False)
    points = coordinates_km(candidate_frame)
    distances = distance_matrix(points)
    unassigned = set(candidate_frame.index)
    bundles = []

    ordering = candidate_frame.sort_values(
        ["region", "practical_milp_probability", "task_id"]
    ).index

    for seed in ordering:
        if seed not in unassigned:
            continue
        same_region = candidate_frame["region"] == candidate_frame.loc[seed, "region"]
        nearby = [
            index
            for index in unassigned
            if same_region.iloc[index] and distances[seed, index] <= BUNDLE_RADIUS_KM
        ]
        nearby.sort(
            key=lambda index: (
                distances[seed, index],
                candidate_frame.loc[index, "practical_milp_probability"],
            )
        )
        selected = nearby[:MAX_BUNDLE_SIZE]
        if len(selected) < MIN_BUNDLE_SIZE:
            continue
        for index in selected:
            unassigned.remove(index)
        bundles.append(selected)

    return candidate_frame, points, distances, bundles


def bundle_probability(package_frame, package_distances, average_reward):
    old_prob = package_frame["original_probability"].to_numpy(float)
    new_prob = package_frame["practical_milp_probability"].to_numpy(float)
    old_price = package_frame["original_price"].to_numpy(float)
    new_price = package_frame["practical_milp_price"].to_numpy(float)

    base_average_reward = float(np.mean(new_price))
    mean_logit = float(np.mean(logit(new_prob)))

    price_changes = new_price - old_price
    valid = np.abs(price_changes) > 1e-6
    if np.any(valid):
        price_slopes = (
            logit(new_prob[valid]) - logit(old_prob[valid])
        ) / price_changes[valid]
        price_slope = float(np.clip(np.mean(price_slopes), 0.02, 0.20))
    else:
        price_slope = 0.08

    member_count = len(package_frame)
    route_length = mst_length(package_distances)
    average_edge = route_length / max(member_count - 1, 1)
    compactness = max(0.0, 1.0 - average_edge / BUNDLE_RADIUS_KM)

    route_bonus = (
        0.35 * np.log(member_count)
        + 0.45 * compactness
        - 0.08 * (member_count - 1)
        - 0.12 * max(0.0, route_length - BUNDLE_RADIUS_KM)
    )
    utility = mean_logit + price_slope * (average_reward - base_average_reward)
    return float(sigmoid(utility + route_bonus)), route_length, compactness


def solve_cost_neutral_reward(package_frame, package_distances):
    baseline_cost = float(
        np.sum(
            package_frame["practical_milp_price"].to_numpy(float)
            * package_frame["practical_milp_probability"].to_numpy(float)
        )
    )
    task_count = len(package_frame)
    high = float(package_frame["practical_milp_price"].mean())
    low = 0.0
    route_length = 0.0
    compactness = 0.0

    for _ in range(70):
        mid = (low + high) / 2
        probability, route_length, compactness = bundle_probability(
            package_frame, package_distances, mid
        )
        expected_cost = mid * task_count * probability
        if expected_cost <= baseline_cost:
            low = mid
        else:
            high = mid

    reward = low
    probability, route_length, compactness = bundle_probability(
        package_frame, package_distances, reward
    )
    return reward, probability, route_length, compactness


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    task_data = pd.read_csv(Q2_RESULTS)
    comparison = pd.read_csv(Q2_COMPARISON)
    practical_summary = comparison.loc[
        comparison["scheme"] == "practical-milp"
    ].iloc[0]

    candidate_mask = (
        (task_data["practical_milp_probability"] < LOW_PROBABILITY_THRESHOLD)
        & (task_data["practical_price_change"].abs() >= BOUNDARY_CHANGE)
    )
    candidates = task_data.loc[candidate_mask].copy()
    candidates.to_csv(
        RESULTS_DIR / "bundle-candidate-tasks.csv",
        index=False,
        encoding="utf-8-sig",
    )

    candidate_frame, points, distances, bundles = form_bundles(candidates)
    package_rows = []
    bundled_task_ids = set()

    for package_number, indexes in enumerate(bundles, start=1):
        package_frame = candidate_frame.loc[indexes].copy()
        local_distances = distances[np.ix_(indexes, indexes)]
        same_reward = float(package_frame["practical_milp_price"].mean())
        same_probability, route_length, compactness = bundle_probability(
            package_frame, local_distances, same_reward
        )
        neutral_reward, neutral_probability, route_length, compactness = (
            solve_cost_neutral_reward(package_frame, local_distances)
        )

        baseline_probability = package_frame[
            "practical_milp_probability"
        ].to_numpy(float)
        baseline_price = package_frame["practical_milp_price"].to_numpy(float)
        baseline_completions = float(np.sum(baseline_probability))
        baseline_payout = float(np.sum(baseline_price * baseline_probability))
        task_count = len(package_frame)

        for task_id in package_frame["task_id"]:
            bundled_task_ids.add(task_id)

        package_rows.append(
            {
                "package_id": f"package-{package_number:03d}",
                "region": int(package_frame["region"].mode().iloc[0]),
                "task_count": task_count,
                "task_ids": ";".join(package_frame["task_id"].astype(str)),
                "baseline_completions": baseline_completions,
                "baseline_expected_payout": baseline_payout,
                "route_length_km": route_length,
                "compactness": compactness,
                "same_average_reward": same_reward,
                "same_reward_probability": same_probability,
                "same_reward_expected_completions": task_count
                * same_probability,
                "same_reward_expected_payout": same_reward
                * task_count
                * same_probability,
                "cost_neutral_average_reward": neutral_reward,
                "cost_neutral_total_reward": neutral_reward * task_count,
                "cost_neutral_probability": neutral_probability,
                "cost_neutral_expected_completions": task_count
                * neutral_probability,
                "cost_neutral_expected_payout": neutral_reward
                * task_count
                * neutral_probability,
            }
        )

    package_results = pd.DataFrame(package_rows)
    package_results.to_csv(
        RESULTS_DIR / "bundle-package-results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if len(package_results) == 0:
        raise RuntimeError("No bundles formed; adjust radius or candidate filters.")

    baseline_pack_completions = package_results["baseline_completions"].sum()
    baseline_pack_payout = package_results["baseline_expected_payout"].sum()
    neutral_pack_completions = package_results[
        "cost_neutral_expected_completions"
    ].sum()
    neutral_pack_payout = package_results["cost_neutral_expected_payout"].sum()
    same_pack_completions = package_results[
        "same_reward_expected_completions"
    ].sum()
    same_pack_payout = package_results["same_reward_expected_payout"].sum()

    total_tasks = len(task_data)
    baseline_total_completions = float(
        practical_summary["expected_completions"]
    )
    baseline_total_payout = float(practical_summary["expected_payout"])

    summary_rows = [
        {
            "scheme": "question2-practical-milp",
            "packages": 0,
            "bundled_tasks": 0,
            "expected_payout": baseline_total_payout,
            "expected_completions": baseline_total_completions,
            "expected_completion_rate": baseline_total_completions / total_tasks,
            "completion_gain_vs_q2": 0.0,
            "payout_change_vs_q2": 0.0,
        },
        {
            "scheme": "bundle-cost-neutral",
            "packages": len(package_results),
            "bundled_tasks": len(bundled_task_ids),
            "expected_payout": baseline_total_payout
            - baseline_pack_payout
            + neutral_pack_payout,
            "expected_completions": baseline_total_completions
            - baseline_pack_completions
            + neutral_pack_completions,
            "expected_completion_rate": (
                baseline_total_completions
                - baseline_pack_completions
                + neutral_pack_completions
            )
            / total_tasks,
            "completion_gain_vs_q2": neutral_pack_completions
            - baseline_pack_completions,
            "payout_change_vs_q2": neutral_pack_payout - baseline_pack_payout,
        },
        {
            "scheme": "bundle-same-average-reward",
            "packages": len(package_results),
            "bundled_tasks": len(bundled_task_ids),
            "expected_payout": baseline_total_payout
            - baseline_pack_payout
            + same_pack_payout,
            "expected_completions": baseline_total_completions
            - baseline_pack_completions
            + same_pack_completions,
            "expected_completion_rate": (
                baseline_total_completions
                - baseline_pack_completions
                + same_pack_completions
            )
            / total_tasks,
            "completion_gain_vs_q2": same_pack_completions
            - baseline_pack_completions,
            "payout_change_vs_q2": same_pack_payout - baseline_pack_payout,
        },
    ]
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(
        RESULTS_DIR / "bundle-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    region_rows = []
    for region, region_packages in package_results.groupby("region"):
        region_rows.append(
            {
                "region": region,
                "packages": len(region_packages),
                "bundled_tasks": int(region_packages["task_count"].sum()),
                "baseline_completions": region_packages[
                    "baseline_completions"
                ].sum(),
                "cost_neutral_completions": region_packages[
                    "cost_neutral_expected_completions"
                ].sum(),
                "same_reward_completions": region_packages[
                    "same_reward_expected_completions"
                ].sum(),
                "cost_neutral_gain": region_packages[
                    "cost_neutral_expected_completions"
                ].sum()
                - region_packages["baseline_completions"].sum(),
                "same_reward_gain": region_packages[
                    "same_reward_expected_completions"
                ].sum()
                - region_packages["baseline_completions"].sum(),
            }
        )
    pd.DataFrame(region_rows).to_csv(
        RESULTS_DIR / "bundle-regional-summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), dpi=180)
    labels = ["二问实用MILP", "成本中性打包", "同均价打包"]
    axes[0].bar(
        labels,
        summary["expected_completion_rate"] * 100,
        color=["#4E79A7", "#59A14F", "#F28E2B"],
    )
    axes[0].set(ylabel="预测完成率/%", title="整体预测完成率")
    axes[0].tick_params(axis="x", rotation=15)

    axes[1].hist(
        package_results["task_count"],
        bins=np.arange(1.5, MAX_BUNDLE_SIZE + 1.6, 1),
        color="#4E79A7",
        edgecolor="white",
    )
    axes[1].set(
        xlabel="包内任务数",
        ylabel="任务包数量",
        title="候选任务包大小分布",
    )
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "bundle-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    print(summary.round(6).to_string(index=False))
    print(
        package_results[
            [
                "package_id",
                "region",
                "task_count",
                "baseline_completions",
                "cost_neutral_expected_completions",
                "same_reward_expected_completions",
            ]
        ]
        .head(12)
        .round(4)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
