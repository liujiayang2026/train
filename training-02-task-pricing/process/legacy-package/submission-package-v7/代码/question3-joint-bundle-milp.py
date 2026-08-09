"""Joint single-task and bundled-task pricing MILP for Question 3.

Each task can either be released as a single task with a newly selected price,
or be covered by one selected bundled package. This corrects the previous
incremental bundle model where non-bundled task prices were fixed at the
Question 2 practical MILP prices.
"""

from __future__ import annotations

import importlib.util
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
BUNDLE_CANDIDATES = QUESTION / "results" / "optimized-bundle-candidates.csv"
PREVIOUS_BUNDLE_COMPARISON = QUESTION / "results" / "optimized-bundle-comparison.csv"
RESULTS_DIR = QUESTION / "results"
FIGURES_DIR = QUESTION / "figures"

MAX_PRICE_CHANGE = 8.0
BUDGET_RELAXATIONS = [0.00, 0.01, 0.02]


def load_q2_model():
    spec = importlib.util.spec_from_file_location("baseline_pricing", Q2_CODE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_single_options(model, data, feature_data, coef, means, scales):
    original_price = data["price"]
    task_count = len(original_price)
    rows = []

    for task_index, old_price in enumerate(original_price):
        low = max(model.PRICE_MIN, old_price - MAX_PRICE_CHANGE)
        high = min(model.PRICE_MAX, old_price + MAX_PRICE_CHANGE)
        prices = np.arange(low, high + model.PRICE_STEP / 2, model.PRICE_STEP)
        probabilities = []
        for price in prices:
            probability = model.predict(
                np.full(task_count, price), feature_data, coef, means, scales
            )[task_index]
            probabilities.append(float(probability))
        for price, probability in zip(prices, probabilities):
            rows.append(
                {
                    "option_type": "single",
                    "task_id": data["task_id"][task_index],
                    "task_ids": data["task_id"][task_index],
                    "task_count": 1,
                    "price": float(price),
                    "expected_completions": float(probability),
                    "expected_payout": float(price * probability),
                    "single_probability": float(probability),
                }
            )
    return pd.DataFrame(rows)


def build_bundle_options(bundle_candidates):
    frame = bundle_candidates.copy()
    return pd.DataFrame(
        {
            "option_type": "bundle",
            "task_id": "",
            "task_ids": frame["task_ids"],
            "task_count": frame["task_count"].astype(int),
            "price": frame["total_reward"].astype(float),
            "expected_completions": frame["expected_completions"].astype(float),
            "expected_payout": frame["expected_payout"].astype(float),
            "single_probability": np.nan,
            "region": frame.get("region", np.nan),
            "route_length_km": frame.get("route_length_km", np.nan),
            "compactness": frame.get("compactness", np.nan),
            "price_multiplier": frame.get("price_multiplier", np.nan),
            "bundle_probability": frame.get("bundle_probability", np.nan),
        }
    )


def solve_joint_milp(task_ids, options, budget_limit):
    task_index = {task_id: idx for idx, task_id in enumerate(task_ids)}
    option_count = len(options)

    row_indexes = []
    col_indexes = []
    values = []
    lower_bounds = []
    upper_bounds = []

    # Every task must be covered exactly once, either by one single-task price
    # option or by one selected bundle option containing the task.
    for task_id, row in task_index.items():
        covered_columns = []
        for option_idx, task_key in enumerate(options["task_ids"]):
            if task_id in str(task_key).split(";"):
                covered_columns.append(option_idx)
        row_indexes.extend([len(lower_bounds)] * len(covered_columns))
        col_indexes.extend(covered_columns)
        values.extend([1.0] * len(covered_columns))
        lower_bounds.append(1.0)
        upper_bounds.append(1.0)

    # Global expected-payout budget.
    row_indexes.extend([len(lower_bounds)] * option_count)
    col_indexes.extend(range(option_count))
    values.extend(options["expected_payout"].to_numpy(float))
    lower_bounds.append(-np.inf)
    upper_bounds.append(float(budget_limit))

    matrix = coo_matrix(
        (values, (row_indexes, col_indexes)),
        shape=(len(lower_bounds), option_count),
    ).tocsr()
    constraint = LinearConstraint(
        matrix, np.array(lower_bounds), np.array(upper_bounds)
    )
    objective = -options["expected_completions"].to_numpy(float)
    result = milp(
        c=objective,
        integrality=np.ones(option_count, dtype=int),
        bounds=Bounds(np.zeros(option_count), np.ones(option_count)),
        constraints=constraint,
        options={"time_limit": 240, "mip_rel_gap": 1e-6, "presolve": True},
    )
    if result.x is None:
        raise RuntimeError(f"Joint MILP failed: {result.message}")
    selected = options.loc[result.x > 0.5].copy()
    return selected, result


def expand_selected_tasks(selected, task_data, label):
    rows = []
    for _, option in selected.iterrows():
        task_ids = str(option["task_ids"]).split(";")
        if option["option_type"] == "single":
            task_id = task_ids[0]
            rows.append(
                {
                    "scheme": label,
                    "task_id": task_id,
                    "release_type": "single",
                    "selected_price": option["price"],
                    "selected_probability": option["single_probability"],
                    "package_task_count": 1,
                    "package_task_ids": task_id,
                }
            )
        else:
            probability_per_task = option["bundle_probability"]
            average_price = option["price"] / option["task_count"]
            for task_id in task_ids:
                rows.append(
                    {
                        "scheme": label,
                        "task_id": task_id,
                        "release_type": "bundle",
                        "selected_price": average_price,
                        "selected_probability": probability_per_task,
                        "package_task_count": option["task_count"],
                        "package_task_ids": option["task_ids"],
                    }
                )
    selected_frame = pd.DataFrame(rows)
    return task_data[["task_id", "region", "original_price", "practical_milp_price", "practical_milp_probability"]].merge(
        selected_frame, on="task_id", how="left"
    )


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    model = load_q2_model()
    data = model.parse_data()
    feature_data = model.make_features(data)
    coef, means, scales, original_probability = model.fit_model(data, feature_data)

    task_data = pd.read_csv(Q2_RESULTS)
    comparison = pd.read_csv(Q2_COMPARISON)
    practical = comparison.loc[comparison["scheme"] == "practical-milp"].iloc[0]
    practical_budget = float(practical["expected_payout"])

    if not BUNDLE_CANDIDATES.exists():
        raise FileNotFoundError(
            f"Missing {BUNDLE_CANDIDATES}. Run optimized-bundle-milp.py first."
        )
    bundle_candidates = pd.read_csv(BUNDLE_CANDIDATES)

    single_options = build_single_options(model, data, feature_data, coef, means, scales)
    bundle_options = build_bundle_options(bundle_candidates)
    options = pd.concat([single_options, bundle_options], ignore_index=True)
    options.to_csv(
        RESULTS_DIR / "joint-bundle-all-options.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary_rows = [
        {
            "scheme": "question2-practical-milp",
            "budget_relaxation": 0.0,
            "packages": 0,
            "bundled_tasks": 0,
            "single_tasks": len(task_data),
            "expected_payout": practical_budget,
            "expected_completions": float(practical["expected_completions"]),
            "expected_completion_rate": float(practical["expected_completion_rate"]),
            "completion_gain_vs_q2": 0.0,
            "payout_change_vs_q2": 0.0,
            "mip_gap": np.nan,
            "message": "baseline",
        }
    ]
    selected_option_frames = []
    selected_task_frames = []

    for relaxation in BUDGET_RELAXATIONS:
        budget_limit = practical_budget * (1 + relaxation)
        selected, result = solve_joint_milp(data["task_id"], options, budget_limit)
        label = f"joint-bundle-{int(relaxation * 100)}pct-extra"
        selected = selected.copy()
        selected["scheme"] = label
        selected["budget_relaxation"] = relaxation
        selected_option_frames.append(selected)

        selected_task = expand_selected_tasks(selected, task_data, label)
        selected_task_frames.append(selected_task)

        bundle_selected = selected[selected["option_type"] == "bundle"]
        bundled_tasks = sorted(
            {task for key in bundle_selected["task_ids"] for task in str(key).split(";")}
        )
        expected_payout = float(selected["expected_payout"].sum())
        expected_completions = float(selected["expected_completions"].sum())
        summary_rows.append(
            {
                "scheme": label,
                "budget_relaxation": relaxation,
                "packages": len(bundle_selected),
                "bundled_tasks": len(bundled_tasks),
                "single_tasks": int((selected["option_type"] == "single").sum()),
                "expected_payout": expected_payout,
                "expected_completions": expected_completions,
                "expected_completion_rate": expected_completions / len(task_data),
                "completion_gain_vs_q2": expected_completions - float(practical["expected_completions"]),
                "payout_change_vs_q2": expected_payout - practical_budget,
                "mip_gap": result.mip_gap,
                "message": result.message,
            }
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(
        RESULTS_DIR / "joint-bundle-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.concat(selected_option_frames, ignore_index=True).to_csv(
        RESULTS_DIR / "joint-bundle-selected-options.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.concat(selected_task_frames, ignore_index=True).to_csv(
        RESULTS_DIR / "joint-bundle-task-prices.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # Compact comparison table against the previous incremental bundle model.
    comparison_rows = [summary.iloc[0].to_dict()]
    if PREVIOUS_BUNDLE_COMPARISON.exists():
        previous = pd.read_csv(PREVIOUS_BUNDLE_COMPARISON)
        for _, row in previous.iterrows():
            if str(row["scheme"]).startswith("optimized-bundle"):
                comparison_rows.append(
                    {
                        "scheme": "previous-" + row["scheme"],
                        "budget_relaxation": row.get("budget_relaxation", np.nan),
                        "packages": row["packages"],
                        "bundled_tasks": row["bundled_tasks"],
                        "single_tasks": np.nan,
                        "expected_payout": row["expected_payout"],
                        "expected_completions": row["expected_completions"],
                        "expected_completion_rate": row["expected_completion_rate"],
                        "completion_gain_vs_q2": row["completion_gain_vs_q2"],
                        "payout_change_vs_q2": row["payout_change_vs_q2"],
                        "mip_gap": row.get("mip_gap", np.nan),
                        "message": "previous incremental bundle model",
                    }
                )
    comparison_rows.extend(summary.iloc[1:].to_dict("records"))
    pd.DataFrame(comparison_rows).to_csv(
        RESULTS_DIR / "joint-vs-previous-bundle-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    region_rows = []
    for task_frame in selected_task_frames:
        label = task_frame["scheme"].iloc[0]
        for region, group in task_frame.groupby("region"):
            region_rows.append(
                {
                    "scheme": label,
                    "region": region,
                    "tasks": len(group),
                    "bundled_tasks": int((group["release_type"] == "bundle").sum()),
                    "average_selected_price": group["selected_price"].mean(),
                    "average_selected_probability": group["selected_probability"].mean(),
                }
            )
    pd.DataFrame(region_rows).to_csv(
        RESULTS_DIR / "joint-bundle-regional-summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), dpi=180)
    labels = ["二问", "联合0%", "联合1%", "联合2%"]
    values = summary["expected_completion_rate"].to_numpy() * 100
    axes[0].bar(labels, values, color=["#4E79A7", "#59A14F", "#F28E2B", "#B07AA1"])
    axes[0].set(ylabel="预测完成率/%", title="联合优化后的总体完成率")
    gains = summary.loc[1:, "completion_gain_vs_q2"].to_numpy()
    axes[1].bar(labels[1:], gains, color=["#59A14F", "#F28E2B", "#B07AA1"])
    axes[1].set(ylabel="较二问增加预计完成任务", title="联合优化增益")
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "joint-bundle-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    print(summary.round(6).to_string(index=False))
    print(f"single_options={len(single_options)} bundle_options={len(bundle_options)} all_options={len(options)}")


if __name__ == "__main__":
    main()
