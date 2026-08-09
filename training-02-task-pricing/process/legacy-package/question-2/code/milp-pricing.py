"""Exact and practical MILP pricing models for Question 2.

This script compares:
1. Original pricing.
2. Existing marginal-efficiency greedy pricing.
3. Exact multiple-choice knapsack MILP maximizing expected completions.
4. Practical MILP with price-change penalty and regional service floors.
"""

import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack


QUESTION = Path(__file__).resolve().parents[1]
CODE_DIR = QUESTION / "code"
DOCS_DIR = QUESTION / "docs"
FIGURES_DIR = QUESTION / "figures"
RESULTS_DIR = QUESTION / "results"
MODEL_PATH = CODE_DIR / "baseline-pricing.py"
EXPECTED_COST_INCREASE = 0.15
MAX_PRICE_CHANGE = 8.0
REGION_MAX_RATE_DROP = 0.01
PRICE_CHANGE_PENALTY = 0.015

spec = importlib.util.spec_from_file_location("baseline_pricing", MODEL_PATH)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def build_candidates(data, feature_data, coef, means, scales):
    original_price = data["price"]
    prices = []
    probabilities = []
    task_indexes = []
    changes = []

    for task_index, old_price in enumerate(original_price):
        low = max(model.PRICE_MIN, old_price - MAX_PRICE_CHANGE)
        high = min(model.PRICE_MAX, old_price + MAX_PRICE_CHANGE)
        candidate_prices = np.arange(
            low, high + model.PRICE_STEP / 2, model.PRICE_STEP
        )
        candidate_probabilities = np.array(
            [
                model.predict(
                    np.full(len(original_price), price),
                    feature_data,
                    coef,
                    means,
                    scales,
                )[task_index]
                for price in candidate_prices
            ]
        )
        prices.extend(candidate_prices)
        probabilities.extend(candidate_probabilities)
        task_indexes.extend([task_index] * len(candidate_prices))
        changes.extend(candidate_prices - old_price)

    return (
        np.asarray(prices),
        np.asarray(probabilities),
        np.asarray(task_indexes, dtype=int),
        np.asarray(changes),
    )


def solve_milp(
    name,
    prices,
    probabilities,
    task_indexes,
    changes,
    original_probability,
    original_price,
    regions,
    practical,
):
    task_count = len(original_price)
    variable_count = len(prices)
    expected_cost = prices * probabilities

    if practical:
        penalty = PRICE_CHANGE_PENALTY * (changes / MAX_PRICE_CHANGE) ** 2
    else:
        penalty = np.zeros(variable_count)
    objective = -probabilities + penalty

    # One candidate price must be selected for every task.
    equality = coo_matrix(
        (
            np.ones(variable_count),
            (task_indexes, np.arange(variable_count)),
        ),
        shape=(task_count, variable_count),
    ).tocsr()
    matrices = [equality]
    lower_bounds = [np.ones(task_count)]
    upper_bounds = [np.ones(task_count)]

    original_expected_cost = float(
        np.sum(original_price * original_probability)
    )
    cost_limit = original_expected_cost * (1 + EXPECTED_COST_INCREASE)
    cost_row = coo_matrix(
        (
            expected_cost,
            (np.zeros(variable_count, dtype=int), np.arange(variable_count)),
        ),
        shape=(1, variable_count),
    ).tocsr()
    matrices.append(cost_row)
    lower_bounds.append(np.array([-np.inf]))
    upper_bounds.append(np.array([cost_limit]))

    # Practical model: every region may lose at most one percentage point.
    if practical:
        for region in sorted(np.unique(regions)):
            region_tasks = regions == region
            region_variable_mask = region_tasks[task_indexes]
            columns = np.flatnonzero(region_variable_mask)
            values = probabilities[columns]
            row = coo_matrix(
                (
                    values,
                    (np.zeros(len(columns), dtype=int), columns),
                ),
                shape=(1, variable_count),
            ).tocsr()
            old_expected_completions = original_probability[
                region_tasks
            ].sum()
            region_floor = (
                old_expected_completions
                - REGION_MAX_RATE_DROP * region_tasks.sum()
            )
            matrices.append(row)
            lower_bounds.append(np.array([region_floor]))
            upper_bounds.append(np.array([np.inf]))

    matrix = vstack(matrices, format="csr")
    lower = np.concatenate(lower_bounds)
    upper = np.concatenate(upper_bounds)
    constraint = LinearConstraint(matrix, lower, upper)

    result = milp(
        c=objective,
        integrality=np.ones(variable_count, dtype=int),
        bounds=Bounds(
            np.zeros(variable_count),
            np.ones(variable_count),
        ),
        constraints=constraint,
        options={
            "time_limit": 120,
            "mip_rel_gap": 1e-6,
            "presolve": True,
        },
    )
    if result.x is None:
        raise RuntimeError(f"{name} failed: {result.message}")

    selected = result.x > 0.5
    selected_prices = np.empty(task_count)
    selected_probabilities = np.empty(task_count)
    for task_index in range(task_count):
        indexes = np.flatnonzero(selected & (task_indexes == task_index))
        if len(indexes) != 1:
            raise RuntimeError(
                f"{name}: task {task_index} selected {len(indexes)} prices"
            )
        variable = indexes[0]
        selected_prices[task_index] = prices[variable]
        selected_probabilities[task_index] = probabilities[variable]

    return {
        "name": name,
        "price": selected_prices,
        "probability": selected_probabilities,
        "expected_cost": float(
            np.sum(selected_prices * selected_probabilities)
        ),
        "cost_limit": cost_limit,
        "status": result.status,
        "message": result.message,
        "objective": result.fun,
        "mip_gap": getattr(result, "mip_gap", np.nan),
    }


def summarize_scheme(name, price, probability, old_price, old_probability):
    return {
        "scheme": name,
        "average_price": price.mean(),
        "posted_total": price.sum(),
        "expected_payout": np.sum(price * probability),
        "expected_cost_increase": (
            np.sum(price * probability)
            / np.sum(old_price * old_probability)
            - 1
        ),
        "expected_completions": probability.sum(),
        "expected_completion_rate": probability.mean(),
        "completion_increase": probability.sum() - old_probability.sum(),
        "price_increase_tasks": int((price > old_price).sum()),
        "price_decrease_tasks": int((price < old_price).sum()),
        "unchanged_tasks": int((price == old_price).sum()),
        "mean_absolute_change": np.mean(np.abs(price - old_price)),
        "boundary_change_tasks": int(
            (np.abs(price - old_price) >= MAX_PRICE_CHANGE - 1e-9).sum()
        ),
        "tasks_at_65": int((price == 65).sum()),
        "tasks_at_85": int((price == 85).sum()),
    }


def main():
    for output_dir in (DOCS_DIR, FIGURES_DIR, RESULTS_DIR):
        output_dir.mkdir(parents=True, exist_ok=True)
    data = model.parse_data()
    feature_data = model.make_features(data)
    coef, means, scales, original_probability = model.fit_model(
        data, feature_data
    )
    original_price = data["price"]

    greedy_price, greedy_probability, _, _, _ = model.choose_improved_prices(
        original_price,
        original_probability,
        feature_data,
        coef,
        means,
        scales,
        cost_increase_limit=EXPECTED_COST_INCREASE,
        max_price_change=MAX_PRICE_CHANGE,
    )

    prices, probabilities, task_indexes, changes = build_candidates(
        data, feature_data, coef, means, scales
    )
    exact = solve_milp(
        "exact-milp",
        prices,
        probabilities,
        task_indexes,
        changes,
        original_probability,
        original_price,
        feature_data["region"],
        practical=False,
    )
    practical = solve_milp(
        "practical-milp",
        prices,
        probabilities,
        task_indexes,
        changes,
        original_probability,
        original_price,
        feature_data["region"],
        practical=True,
    )

    rows = [
        summarize_scheme(
            "original",
            original_price,
            original_probability,
            original_price,
            original_probability,
        ),
        summarize_scheme(
            "greedy",
            greedy_price,
            greedy_probability,
            original_price,
            original_probability,
        ),
        summarize_scheme(
            "exact-milp",
            exact["price"],
            exact["probability"],
            original_price,
            original_probability,
        ),
        summarize_scheme(
            "practical-milp",
            practical["price"],
            practical["probability"],
            original_price,
            original_probability,
        ),
    ]
    summary = pd.DataFrame(rows)
    summary.to_csv(
        RESULTS_DIR / "milp-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    task_output = pd.DataFrame(
        {
            "task_id": data["task_id"],
            "latitude": data["lat"],
            "longitude": data["lon"],
            "region": feature_data["region"],
            "original_price": original_price,
            "original_probability": original_probability,
            "greedy_price": greedy_price,
            "greedy_probability": greedy_probability,
            "exact_milp_price": exact["price"],
            "exact_milp_probability": exact["probability"],
            "practical_milp_price": practical["price"],
            "practical_milp_probability": practical["probability"],
        }
    )
    task_output["practical_price_change"] = (
        task_output["practical_milp_price"] - task_output["original_price"]
    )
    task_output["practical_probability_change"] = (
        task_output["practical_milp_probability"]
        - task_output["original_probability"]
    )
    task_output.to_csv(
        RESULTS_DIR / "milp-pricing-results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Regional service comparison.
    regional_rows = []
    for region in sorted(np.unique(feature_data["region"])):
        mask = feature_data["region"] == region
        for name, price, probability in [
            ("original", original_price, original_probability),
            ("greedy", greedy_price, greedy_probability),
            ("practical-milp", practical["price"], practical["probability"]),
        ]:
            regional_rows.append(
                {
                    "region": region,
                    "scheme": name,
                    "tasks": int(mask.sum()),
                    "average_price": price[mask].mean(),
                    "expected_completion_rate": probability[mask].mean(),
                    "expected_payout": np.sum(price[mask] * probability[mask]),
                }
            )
    pd.DataFrame(regional_rows).to_csv(
        RESULTS_DIR / "milp-regional-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"
    ]
    plt.rcParams["axes.unicode_minus"] = False
    labels = ["原方案", "贪心方案", "精确MILP", "实用MILP"]
    colors = ["#4E79A7", "#59A14F", "#F28E2B", "#B07AA1"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.9), dpi=180)

    values = summary["expected_completion_rate"].to_numpy()
    bars = axes[0].bar(labels, values, color=colors)
    axes[0].set(ylabel="预测完成率", title="完成率对比", ylim=(0.60, 0.71))
    for bar, value in zip(bars, values):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.002,
            f"{value:.2%}",
            ha="center",
            fontsize=9,
        )

    values = summary["expected_payout"].to_numpy()
    bars = axes[1].bar(labels, values, color=colors)
    axes[1].set(ylabel="预计支付金额/元", title="预计成本对比")
    for bar, value in zip(bars, values):
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            value + 280,
            f"{value:,.0f}",
            ha="center",
            fontsize=9,
        )

    width = 0.25
    x = np.arange(3)
    axes[2].bar(
        x - width,
        [
            (np.abs(greedy_price - original_price) >= MAX_PRICE_CHANGE).sum(),
            (greedy_price == 65).sum(),
            (greedy_price == 85).sum(),
        ],
        width,
        label="贪心方案",
        color=colors[1],
    )
    axes[2].bar(
        x,
        [
            (np.abs(exact["price"] - original_price) >= MAX_PRICE_CHANGE).sum(),
            (exact["price"] == 65).sum(),
            (exact["price"] == 85).sum(),
        ],
        width,
        label="精确MILP",
        color=colors[2],
    )
    axes[2].bar(
        x + width,
        [
            (
                np.abs(practical["price"] - original_price)
                >= MAX_PRICE_CHANGE
            ).sum(),
            (practical["price"] == 65).sum(),
            (practical["price"] == 85).sum(),
        ],
        width,
        label="实用MILP",
        color=colors[3],
    )
    axes[2].set_xticks(x, ["达到±8元边界", "定价65元", "定价85元"])
    axes[2].set(ylabel="任务数", title="价格极端程度")
    axes[2].legend()

    fig.suptitle("贪心定价与多选择背包MILP方案对比", fontsize=14)
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "milp-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    lines = [
        "Question 2 MILP comparison",
        "=" * 40,
        summary.round(6).to_string(index=False),
        "",
        f"Exact MILP status: {exact['message']}",
        f"Exact MILP gap: {exact['mip_gap']}",
        f"Practical MILP status: {practical['message']}",
        f"Practical MILP gap: {practical['mip_gap']}",
        f"Practical price-change penalty: {PRICE_CHANGE_PENALTY}",
        f"Regional maximum rate drop: {REGION_MAX_RATE_DROP:.1%}",
    ]
    (DOCS_DIR / "milp-summary.txt").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    print(summary.round(6).to_string(index=False))
    print(exact["message"], exact["mip_gap"])
    print(practical["message"], practical["mip_gap"])


if __name__ == "__main__":
    main()
