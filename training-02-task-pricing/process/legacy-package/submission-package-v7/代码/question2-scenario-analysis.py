"""Compare completion-rate scenarios for the improved pricing method."""

import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


QUESTION = Path(__file__).resolve().parents[1]
CODE_DIR = QUESTION / "code"
FIGURES_DIR = QUESTION / "figures"
RESULTS_DIR = QUESTION / "results"
MODEL_PATH = CODE_DIR / "baseline-pricing.py"

spec = importlib.util.spec_from_file_location("baseline_pricing", MODEL_PATH)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    data = model.parse_data()
    feature_data = model.make_features(data)
    coef, means, scales, original_probability = model.fit_model(
        data, feature_data
    )
    original_price = data["price"]
    original_expected_cost = float(
        np.sum(original_price * original_probability)
    )

    scenario_settings = [
        ("cost-neutral", 0.00, 5.0),
        ("balanced-5", 0.05, 5.0),
        ("enhanced-10", 0.10, 5.0),
        ("enhanced-15", 0.15, 5.0),
        ("wide-10", 0.10, 8.0),
        ("wide-15", 0.15, 8.0),
        ("completion-first-20", 0.20, 10.0),
    ]

    rows = []
    task_output = pd.DataFrame(
        {
            "task_id": data["task_id"],
            "original_price": original_price,
            "original_probability": original_probability,
        }
    )

    for name, cost_limit, max_change in scenario_settings:
        (
            price,
            probability,
            allowed_cost,
            used_cost,
            accepted_steps,
        ) = model.choose_improved_prices(
            original_price,
            original_probability,
            feature_data,
            coef,
            means,
            scales,
            cost_increase_limit=cost_limit,
            max_price_change=max_change,
        )
        rows.append(
            {
                "scenario": name,
                "cost_limit_increase": cost_limit,
                "max_price_change": max_change,
                "average_price": price.mean(),
                "posted_total": price.sum(),
                "expected_payout": used_cost,
                "actual_cost_increase": used_cost / original_expected_cost - 1,
                "expected_completions": probability.sum(),
                "expected_completion_rate": probability.mean(),
                "completion_increase": probability.sum()
                - original_probability.sum(),
                "price_increase_tasks": int((price > original_price).sum()),
                "price_decrease_tasks": int((price < original_price).sum()),
                "unchanged_tasks": int((price == original_price).sum()),
                "tasks_at_65": int((price == 65).sum()),
                "tasks_at_85": int((price == 85).sum()),
                "accepted_half_yuan_steps": accepted_steps,
                "allowed_expected_payout": allowed_cost,
            }
        )
        task_output[f"{name}_price"] = price
        task_output[f"{name}_probability"] = probability

    summary = pd.DataFrame(rows)
    summary.to_csv(
        RESULTS_DIR / "completion-scenarios.csv",
        index=False,
        encoding="utf-8-sig",
    )
    task_output.to_csv(
        RESULTS_DIR / "completion-scenario-task-results.csv",
        index=False,
        encoding="utf-8-sig",
    )
    recommended = pd.DataFrame(
        {
            "task_id": task_output["task_id"],
            "original_price": task_output["original_price"],
            "recommended_price": task_output["wide-15_price"],
            "price_change": (
                task_output["wide-15_price"] - task_output["original_price"]
            ),
            "original_probability": task_output["original_probability"],
            "recommended_probability": task_output["wide-15_probability"],
            "probability_change": (
                task_output["wide-15_probability"]
                - task_output["original_probability"]
            ),
        }
    )
    recommended.to_csv(
        RESULTS_DIR / "recommended-pricing-results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"
    ]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9.5, 6.2), dpi=180)
    x = summary["actual_cost_increase"].to_numpy() * 100
    y = summary["expected_completion_rate"].to_numpy() * 100
    size = 45 + 10 * summary["max_price_change"].to_numpy()
    scatter = ax.scatter(
        x,
        y,
        s=size,
        c=summary["max_price_change"],
        cmap="viridis",
        edgecolors="#24303F",
        linewidths=0.8,
        zorder=3,
    )
    ax.plot(x[:4], y[:4], color="#4E79A7", linewidth=1.4, alpha=0.7)
    for _, row in summary.iterrows():
        ax.annotate(
            row["scenario"],
            (
                row["actual_cost_increase"] * 100,
                row["expected_completion_rate"] * 100,
            ),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8.5,
        )
    ax.axhline(
        original_probability.mean() * 100,
        linestyle="--",
        linewidth=1,
        color="#777777",
        label="原方案预测完成率",
    )
    ax.set(
        xlabel="预计支付金额增幅/%",
        ylabel="预测完成率/%",
        title="不同预算与调价幅度下的预测完成率",
    )
    ax.grid(alpha=0.25)
    colorbar = fig.colorbar(scatter, ax=ax, pad=0.02)
    colorbar.set_label("单任务最大调价幅度/元")
    ax.legend()
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "completion-scenarios.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    print(
        summary[
            [
                "scenario",
                "actual_cost_increase",
                "max_price_change",
                "average_price",
                "expected_payout",
                "expected_completions",
                "expected_completion_rate",
                "tasks_at_65",
                "tasks_at_85",
            ]
        ].round(4).to_string(index=False)
    )


if __name__ == "__main__":
    main()
