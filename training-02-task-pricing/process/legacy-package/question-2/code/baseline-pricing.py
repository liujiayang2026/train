"""Baseline pricing model for CUMCM 2017 Problem B, Question 2.

Method
------
1. Build spatial supply/demand features from task and member coordinates.
2. Fit an L2-regularized logistic completion model.
3. Constrain the standardized price coefficient to be non-negative.
4. For each task, choose the lowest 0.5-yuan price in [65, 85] whose
   predicted completion probability reaches TARGET_PROBABILITY.
5. If the target is unreachable at 85 yuan, use 85 yuan.

Outputs
-------
results/pricing-results.csv
docs/model-summary.txt
figures/pricing-comparison.png
"""

import heapq
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans2
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.special import expit
from scipy.stats import rankdata


QUESTION = Path(__file__).resolve().parents[1]
PROJECT = QUESTION.parent
TASK_CSV = PROJECT / ".analysis" / "tasks.csv"
MEMBER_XLSX = next(PROJECT.glob("*.xlsx"))
DOCS_DIR = QUESTION / "docs"
FIGURES_DIR = QUESTION / "figures"
RESULTS_DIR = QUESTION / "results"

TARGET_PROBABILITY = 0.75
IMPROVED_COST_INCREASE_LIMIT = 0.05
IMPROVED_MAX_PRICE_CHANGE = 5.0
PRICE_MIN = 65.0
PRICE_MAX = 85.0
PRICE_STEP = 0.5
NEIGHBOR_RADIUS_KM = 2.0
REGION_COUNT = 5
L2_PENALTY = 0.8
RANDOM_SEED = 2026


def parse_data():
    tasks = pd.read_csv(TASK_CSV)
    members = pd.read_excel(MEMBER_XLSX)

    task_id = tasks.iloc[:, 0].astype(str).to_numpy()
    task_lat = tasks.iloc[:, 1].astype(float).to_numpy()
    task_lon = tasks.iloc[:, 2].astype(float).to_numpy()
    original_price = tasks.iloc[:, 3].astype(float).to_numpy()
    completed = tasks.iloc[:, 4].astype(int).to_numpy()

    member_coords = members.iloc[:, 1].astype(str).str.extract(
        r"([0-9.]+)\s+([0-9.]+)"
    ).astype(float)
    member_lat = member_coords.iloc[:, 0].to_numpy()
    member_lon = member_coords.iloc[:, 1].to_numpy()
    member_quota = members.iloc[:, 2].astype(float).to_numpy()
    member_credit = members.iloc[:, 4].astype(float).to_numpy()

    return {
        "tasks": tasks,
        "task_id": task_id,
        "lat": task_lat,
        "lon": task_lon,
        "price": original_price,
        "completed": completed,
        "member_lat": member_lat,
        "member_lon": member_lon,
        "member_quota": member_quota,
        "member_credit": member_credit,
    }


def make_features(data):
    lat = data["lat"]
    lon = data["lon"]
    member_lat = data["member_lat"]
    member_lon = data["member_lon"]
    latitude_center = float(np.mean(lat))

    # Local equirectangular approximation in kilometres.
    task_xy = np.column_stack(
        (lon * 111.0 * np.cos(np.radians(latitude_center)), lat * 111.0)
    )
    member_xy = np.column_stack(
        (
            member_lon * 111.0 * np.cos(np.radians(latitude_center)),
            member_lat * 111.0,
        )
    )

    task_tree = cKDTree(task_xy)
    member_tree = cKDTree(member_xy)

    nearest_member_km = member_tree.query(task_xy, k=1)[0]
    member_neighbors = member_tree.query_ball_point(
        task_xy, NEIGHBOR_RADIUS_KM
    )
    task_neighbors = task_tree.query_ball_point(task_xy, NEIGHBOR_RADIUS_KM)

    members_2km = np.array([len(indexes) for indexes in member_neighbors])
    tasks_2km = np.array([max(0, len(indexes) - 1) for indexes in task_neighbors])
    quota_2km = np.array(
        [data["member_quota"][indexes].sum() for indexes in member_neighbors]
    )
    credit_2km = np.array(
        [data["member_credit"][indexes].sum() for indexes in member_neighbors]
    )

    # Spatial regions absorb broad unobserved geographic differences.
    standardized_xy = (task_xy - task_xy.mean(axis=0)) / task_xy.std(axis=0)
    _, region = kmeans2(
        standardized_xy, REGION_COUNT, minit="++", seed=RANDOM_SEED
    )
    region_dummies = np.column_stack(
        [(region == index).astype(float) for index in range(1, REGION_COUNT)]
    )

    fixed_continuous = np.column_stack(
        (
            np.minimum(nearest_member_km, 10.0),
            np.log1p(members_2km),
            np.log1p(tasks_2km),
            np.log1p(quota_2km),
            np.log1p(credit_2km),
        )
    )
    fixed_names = [
        "nearest_member_km",
        "log_members_2km",
        "log_tasks_2km",
        "log_quota_2km",
        "log_credit_2km",
    ]
    region_names = [f"region_{index}" for index in range(1, REGION_COUNT)]

    return {
        "fixed_continuous": fixed_continuous,
        "region_dummies": region_dummies,
        "feature_names": ["price"] + fixed_names + region_names,
        "nearest_member_km": nearest_member_km,
        "members_2km": members_2km,
        "tasks_2km": tasks_2km,
        "quota_2km": quota_2km,
        "credit_2km": credit_2km,
        "region": region,
    }


def build_design(price, feature_data, means, scales):
    raw_continuous = np.column_stack(
        (price, feature_data["fixed_continuous"])
    )
    standardized = (raw_continuous - means) / scales
    return np.column_stack(
        (
            np.ones(len(price)),
            standardized,
            feature_data["region_dummies"],
        )
    )


def fit_model(data, feature_data):
    y = data["completed"]
    raw_continuous = np.column_stack(
        (data["price"], feature_data["fixed_continuous"])
    )
    means = raw_continuous.mean(axis=0)
    scales = raw_continuous.std(axis=0)
    scales[scales == 0] = 1.0
    design = build_design(data["price"], feature_data, means, scales)

    def objective(coef):
        probability = expit(design @ coef)
        negative_log_likelihood = -np.sum(
            y * np.log(probability + 1e-12)
            + (1 - y) * np.log(1 - probability + 1e-12)
        )
        penalty = L2_PENALTY * np.sum(coef[1:] ** 2)
        return negative_log_likelihood + penalty

    # coef[1] is the standardized price coefficient.
    bounds = [(None, None), (0.0, None)] + [
        (None, None)
    ] * (design.shape[1] - 2)
    result = minimize(
        objective,
        np.zeros(design.shape[1]),
        method="L-BFGS-B",
        bounds=bounds,
    )
    if not result.success:
        raise RuntimeError(f"Model fitting failed: {result.message}")

    original_probability = expit(design @ result.x)
    return result.x, means, scales, original_probability


def predict(price, feature_data, coef, means, scales):
    design = build_design(price, feature_data, means, scales)
    return expit(design @ coef)


def auc_score(y, probability):
    positive = y == 1
    negative = y == 0
    ranks = rankdata(probability)
    n_positive = positive.sum()
    n_negative = negative.sum()
    rank_sum = ranks[positive].sum()
    return (
        rank_sum - n_positive * (n_positive + 1) / 2
    ) / (n_positive * n_negative)


def choose_new_prices(feature_data, coef, means, scales):
    candidates = np.arange(
        PRICE_MIN, PRICE_MAX + PRICE_STEP / 2, PRICE_STEP
    )
    all_probabilities = np.column_stack(
        [
            predict(
                np.full(len(feature_data["region"]), candidate),
                feature_data,
                coef,
                means,
                scales,
            )
            for candidate in candidates
        ]
    )

    reaches_target = all_probabilities >= TARGET_PROBABILITY
    first_index = np.argmax(reaches_target, axis=1)
    unreachable = ~reaches_target.any(axis=1)
    first_index[unreachable] = len(candidates) - 1

    new_price = candidates[first_index]
    new_probability = all_probabilities[
        np.arange(len(new_price)), first_index
    ]
    return new_price, new_probability, unreachable


def choose_improved_prices(
    original_price,
    original_probability,
    feature_data,
    coef,
    means,
    scales,
    cost_increase_limit=IMPROVED_COST_INCREASE_LIMIT,
    max_price_change=IMPROVED_MAX_PRICE_CHANGE,
):
    """Allocate price increments by probability gain per expected-cost gain.

    Each task may move at most +/- 5 yuan from its original price. The expected
    payout may increase by at most 5% relative to the original modeled payout.
    """
    candidates = np.arange(
        PRICE_MIN, PRICE_MAX + PRICE_STEP / 2, PRICE_STEP
    )
    probability_matrix = np.column_stack(
        [
            predict(
                np.full(len(original_price), candidate),
                feature_data,
                coef,
                means,
                scales,
            )
            for candidate in candidates
        ]
    )
    expected_cost_matrix = probability_matrix * candidates[np.newaxis, :]

    lower_price = np.maximum(PRICE_MIN, original_price - max_price_change)
    upper_price = np.minimum(PRICE_MAX, original_price + max_price_change)
    lower_index = np.rint((lower_price - PRICE_MIN) / PRICE_STEP).astype(int)
    upper_index = np.rint((upper_price - PRICE_MIN) / PRICE_STEP).astype(int)
    current_index = lower_index.copy()

    row_index = np.arange(len(original_price))
    current_cost = float(
        expected_cost_matrix[row_index, current_index].sum()
    )
    original_expected_cost = float(
        np.sum(original_price * original_probability)
    )
    cost_limit = original_expected_cost * (
        1.0 + cost_increase_limit
    )

    # Heap entries: (-gain/cost, task index, expected current index).
    heap = []

    def push_next(task_index):
        index = current_index[task_index]
        if index >= upper_index[task_index]:
            return
        next_index = index + 1
        probability_gain = (
            probability_matrix[task_index, next_index]
            - probability_matrix[task_index, index]
        )
        cost_gain = (
            expected_cost_matrix[task_index, next_index]
            - expected_cost_matrix[task_index, index]
        )
        if probability_gain <= 0 or cost_gain <= 0:
            return
        efficiency = probability_gain / cost_gain
        heapq.heappush(
            heap,
            (-efficiency, task_index, index),
        )

    for task_index in range(len(original_price)):
        push_next(task_index)

    accepted_steps = 0
    while heap:
        _, task_index, expected_index = heapq.heappop(heap)
        if current_index[task_index] != expected_index:
            continue
        next_index = expected_index + 1
        cost_gain = (
            expected_cost_matrix[task_index, next_index]
            - expected_cost_matrix[task_index, expected_index]
        )
        if current_cost + cost_gain <= cost_limit + 1e-9:
            current_index[task_index] = next_index
            current_cost += float(cost_gain)
            accepted_steps += 1
            push_next(task_index)

    improved_price = candidates[current_index]
    improved_probability = probability_matrix[row_index, current_index]
    return (
        improved_price,
        improved_probability,
        cost_limit,
        current_cost,
        accepted_steps,
    )


def save_results(
    data,
    feature_data,
    original_probability,
    new_price,
    new_probability,
    unreachable,
):
    output = pd.DataFrame(
        {
            "task_id": data["task_id"],
            "latitude": data["lat"],
            "longitude": data["lon"],
            "actual_completed": data["completed"],
            "original_price": data["price"],
            "new_price": new_price,
            "price_change": new_price - data["price"],
            "predicted_probability_original": original_probability,
            "predicted_probability_new": new_probability,
            "probability_change": new_probability - original_probability,
            "target_unreachable_at_85": unreachable.astype(int),
            "nearest_member_km": feature_data["nearest_member_km"],
            "members_2km": feature_data["members_2km"],
            "tasks_2km": feature_data["tasks_2km"],
            "region": feature_data["region"],
        }
    )
    output.to_csv(
        RESULTS_DIR / "pricing-results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return output


def save_improved_results(
    baseline_output,
    improved_price,
    improved_probability,
):
    output = baseline_output.copy()
    output = output.rename(
        columns={
            "new_price": "threshold_price",
            "price_change": "threshold_price_change",
            "predicted_probability_new": "threshold_probability",
            "probability_change": "threshold_probability_change",
        }
    )
    output["improved_price"] = improved_price
    output["improved_price_change"] = (
        improved_price - output["original_price"].to_numpy()
    )
    output["improved_probability"] = improved_probability
    output["improved_probability_change"] = (
        improved_probability
        - output["predicted_probability_original"].to_numpy()
    )
    output.to_csv(
        RESULTS_DIR / "improved-pricing-results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return output


def make_comparison_figure(output):
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), dpi=180)

    axes[0].hist(
        output["original_price"],
        bins=np.arange(64.75, 85.76, 0.5),
        alpha=0.68,
        label="原价格",
        color="#4E79A7",
    )
    axes[0].hist(
        output["new_price"],
        bins=np.arange(64.75, 85.76, 0.5),
        alpha=0.58,
        label="新价格",
        color="#F28E2B",
    )
    axes[0].set(xlabel="任务价格/元", ylabel="任务数", title="新旧价格分布")
    axes[0].legend()

    axes[1].scatter(
        output["original_price"],
        output["new_price"],
        c=output["probability_change"],
        cmap="viridis",
        s=18,
        alpha=0.72,
        edgecolors="none",
    )
    axes[1].plot([65, 85], [65, 85], "--", color="#444444", linewidth=1)
    axes[1].set(
        xlim=(64.5, 85.5),
        ylim=(64.5, 85.5),
        xlabel="原价格/元",
        ylabel="新价格/元",
        title="逐任务价格调整",
    )

    axes[2].hist(
        output["predicted_probability_original"],
        bins=np.linspace(0, 1, 21),
        alpha=0.68,
        label="原方案",
        color="#4E79A7",
    )
    axes[2].hist(
        output["predicted_probability_new"],
        bins=np.linspace(0, 1, 21),
        alpha=0.58,
        label="新方案",
        color="#59A14F",
    )
    axes[2].axvline(
        TARGET_PROBABILITY,
        linestyle="--",
        color="#D62728",
        linewidth=1,
        label="目标概率",
    )
    axes[2].set(
        xlabel="预测完成概率",
        ylabel="任务数",
        title="预测完成概率分布",
    )
    axes[2].legend()

    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "pricing-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def make_improved_comparison_figure(output):
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"
    ]
    plt.rcParams["axes.unicode_minus"] = False

    original_probability = output["predicted_probability_original"].to_numpy()
    threshold_probability = output["threshold_probability"].to_numpy()
    improved_probability = output["improved_probability"].to_numpy()
    original_price = output["original_price"].to_numpy()
    threshold_price = output["threshold_price"].to_numpy()
    improved_price = output["improved_price"].to_numpy()

    names = ["原方案", "75%阈值方案", "改进方案"]
    completion_rates = [
        original_probability.mean(),
        threshold_probability.mean(),
        improved_probability.mean(),
    ]
    expected_costs = [
        np.sum(original_price * original_probability),
        np.sum(threshold_price * threshold_probability),
        np.sum(improved_price * improved_probability),
    ]
    average_prices = [
        original_price.mean(),
        threshold_price.mean(),
        improved_price.mean(),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), dpi=180)
    colors = ["#4E79A7", "#E15759", "#59A14F"]

    bars = axes[0].bar(names, completion_rates, color=colors)
    axes[0].set(
        ylim=(0, 0.85),
        ylabel="预测完成率",
        title="预测完成率对比",
    )
    for bar, value in zip(bars, completion_rates):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.012,
            f"{value:.1%}",
            ha="center",
        )

    bars = axes[1].bar(names, expected_costs, color=colors)
    axes[1].set(ylabel="预计支付金额/元", title="预计支付金额对比")
    for bar, value in zip(bars, expected_costs):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            value + 450,
            f"{value:,.0f}",
            ha="center",
        )

    bins = np.arange(64.75, 85.76, 0.5)
    axes[2].hist(
        original_price, bins=bins, alpha=0.55, color=colors[0], label="原方案"
    )
    axes[2].hist(
        threshold_price, bins=bins, alpha=0.45, color=colors[1],
        label="75%阈值方案"
    )
    axes[2].hist(
        improved_price, bins=bins, alpha=0.55, color=colors[2], label="改进方案"
    )
    axes[2].set(
        xlabel="任务价格/元",
        ylabel="任务数",
        title="价格分布对比",
    )
    axes[2].legend()

    fig.suptitle(
        "原方案、统一阈值方案与改进方案对比"
        f"（改进方案平均价格 {average_prices[2]:.2f} 元）",
        fontsize=14,
    )
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "improved-pricing-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def write_improved_summary(
    output,
    cost_limit,
    improved_cost,
    accepted_steps,
):
    y = output["actual_completed"].to_numpy()
    original_price = output["original_price"].to_numpy()
    threshold_price = output["threshold_price"].to_numpy()
    improved_price = output["improved_price"].to_numpy()
    original_probability = output["predicted_probability_original"].to_numpy()
    threshold_probability = output["threshold_probability"].to_numpy()
    improved_probability = output["improved_probability"].to_numpy()

    def scheme_line(name, price, probability):
        expected_cost = np.sum(price * probability)
        return [
            f"{name}:",
            f"  average price = {price.mean():.3f}",
            f"  posted total = {price.sum():.2f}",
            f"  expected payout = {expected_cost:.2f}",
            f"  expected completions = {probability.sum():.2f}",
            f"  expected completion rate = {probability.mean():.4f}",
        ]

    lines = [
        "Question 2 improved pricing comparison",
        "=" * 46,
        f"Tasks: {len(output)}",
        f"Observed historical completion rate: {y.mean():.4f}",
        "",
    ]
    lines += scheme_line("Original scheme", original_price, original_probability)
    lines.append("")
    lines += scheme_line(
        "Uniform 75% threshold scheme",
        threshold_price,
        threshold_probability,
    )
    lines.append("")
    lines += scheme_line(
        "Improved marginal-efficiency scheme",
        improved_price,
        improved_probability,
    )
    lines += [
        "",
        f"Improved expected-cost limit: {cost_limit:.2f}",
        f"Improved expected cost used: {improved_cost:.2f}",
        f"Accepted 0.5-yuan increments: {accepted_steps}",
        f"Maximum absolute price change: {IMPROVED_MAX_PRICE_CHANGE:.2f}",
        f"Expected-cost increase limit: {IMPROVED_COST_INCREASE_LIMIT:.1%}",
        "",
        f"Improved tasks with price increase: {(improved_price>original_price).sum()}",
        f"Improved tasks with price decrease: {(improved_price<original_price).sum()}",
        f"Improved tasks with unchanged price: {(improved_price==original_price).sum()}",
        f"Improved tasks priced at 65: {(improved_price==65).sum()}",
        f"Improved tasks priced at 85: {(improved_price==85).sum()}",
        "",
        "Differences versus original:",
        f"  expected completion increase = {(improved_probability-original_probability).sum():.2f}",
        f"  completion-rate increase = {(improved_probability.mean()-original_probability.mean()):.4f}",
        f"  expected-payout increase = {np.sum(improved_price*improved_probability)-np.sum(original_price*original_probability):.2f}",
        "",
        "Differences versus uniform 75% threshold scheme:",
        f"  expected completions = {improved_probability.sum()-threshold_probability.sum():.2f}",
        f"  expected payout = {np.sum(improved_price*improved_probability)-np.sum(threshold_price*threshold_probability):.2f}",
        f"  average price = {improved_price.mean()-threshold_price.mean():.3f}",
    ]
    (DOCS_DIR / "improved-model-summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def write_summary(data, output, coef, feature_names):
    y = data["completed"]
    old_probability = output["predicted_probability_original"].to_numpy()
    new_probability = output["predicted_probability_new"].to_numpy()
    old_price = output["original_price"].to_numpy()
    new_price = output["new_price"].to_numpy()

    old_posted = old_price.sum()
    new_posted = new_price.sum()
    actual_historical_payout = np.sum(old_price * y)
    old_expected_payout = np.sum(old_price * old_probability)
    new_expected_payout = np.sum(new_price * new_probability)

    lines = [
        "Question 2 baseline pricing result",
        "=" * 42,
        f"Tasks: {len(output)}",
        f"Observed historical completion rate: {y.mean():.4f}",
        f"Model AUC on training data: {auc_score(y, old_probability):.4f}",
        f"Model Brier score on training data: {np.mean((y-old_probability)**2):.4f}",
        f"Standardized price coefficient: {coef[1]:.6f}",
        "",
        f"Target completion probability: {TARGET_PROBABILITY:.2f}",
        f"Original average price: {old_price.mean():.3f}",
        f"New average price: {new_price.mean():.3f}",
        f"Original posted total: {old_posted:.2f}",
        f"New posted total: {new_posted:.2f}",
        f"Historical actual payout: {actual_historical_payout:.2f}",
        f"Original expected payout: {old_expected_payout:.2f}",
        f"New expected payout: {new_expected_payout:.2f}",
        "",
        f"Original expected completions: {old_probability.sum():.2f}",
        f"New expected completions: {new_probability.sum():.2f}",
        f"Original expected completion rate: {old_probability.mean():.4f}",
        f"New expected completion rate: {new_probability.mean():.4f}",
        f"Expected completion increase: {(new_probability-old_probability).sum():.2f}",
        "",
        f"Tasks with price increase: {(new_price>old_price).sum()}",
        f"Tasks with price decrease: {(new_price<old_price).sum()}",
        f"Tasks with unchanged price: {(new_price==old_price).sum()}",
        f"Tasks unable to reach target at 85: {output['target_unreachable_at_85'].sum()}",
        f"Tasks predicted to reach target under new scheme: {(new_probability>=TARGET_PROBABILITY).sum()}",
        "",
        "Model coefficients (standardized continuous variables):",
    ]
    coefficient_names = ["intercept"] + feature_names
    lines.extend(
        f"{name}: {value:.6f}"
        for name, value in zip(coefficient_names, coef)
    )
    (DOCS_DIR / "model-summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main():
    for output_dir in (DOCS_DIR, FIGURES_DIR, RESULTS_DIR):
        output_dir.mkdir(parents=True, exist_ok=True)
    data = parse_data()
    feature_data = make_features(data)
    coef, means, scales, original_probability = fit_model(data, feature_data)
    new_price, new_probability, unreachable = choose_new_prices(
        feature_data, coef, means, scales
    )
    output = save_results(
        data,
        feature_data,
        original_probability,
        new_price,
        new_probability,
        unreachable,
    )
    make_comparison_figure(output)
    write_summary(data, output, coef, feature_data["feature_names"])
    (
        improved_price,
        improved_probability,
        cost_limit,
        improved_cost,
        accepted_steps,
    ) = choose_improved_prices(
        data["price"],
        original_probability,
        feature_data,
        coef,
        means,
        scales,
    )
    improved_output = save_improved_results(
        output,
        improved_price,
        improved_probability,
    )
    make_improved_comparison_figure(improved_output)
    write_improved_summary(
        improved_output,
        cost_limit,
        improved_cost,
        accepted_steps,
    )
    print(
        (DOCS_DIR / "improved-model-summary.txt").read_text(encoding="utf-8")
    )


if __name__ == "__main__":
    main()
