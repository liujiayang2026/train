"""Question 4 baseline run for the new project in Attachment 3.

The script transfers the Question 2 completion model to the new task
locations, but explicitly controls two distribution shifts:

1. The new-task density input is capped at the historical 95th percentile.
2. Local task/member pressure above the historical 95th percentile receives
   an out-of-distribution congestion penalty.

It compares a uniform 75-yuan release, individual pricing, and compact
bundled pricing.  All task-level prices stay within the observed 65--85 yuan
range to avoid unsupported price extrapolation.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

QUESTION_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = QUESTION_DIR.parent
SHARED_PACKAGES = PROJECT_DIR / "shared" / "python-packages"
if SHARED_PACKAGES.exists():
    sys.path.insert(0, str(SHARED_PACKAGES))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path as PlotPath
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.special import expit, logit


Q2_CODE = PROJECT_DIR / "question-2" / "code" / "baseline-pricing.py"
NEW_TASK_CSV = PROJECT_DIR / ".analysis" / "new_tasks.csv"
PREFECTURES_JSON = PROJECT_DIR / ".analysis" / "prefectures.json"
RESULTS_DIR = QUESTION_DIR / "results"
DOCS_DIR = QUESTION_DIR / "docs"
FIGURES_DIR = QUESTION_DIR / "figures"

PRICE_MIN = 65.0
PRICE_MAX = 85.0
PRICE_STEP = 0.5
UNIFORM_PRICE = 75.0
TARGET_PROBABILITY = 0.75
NEIGHBOR_RADIUS_KM = 2.0
PACKAGE_RADIUS_KM = 0.35
MAX_PACKAGE_SIZE = 5
PRESSURE_LOGIT_PENALTY = 0.65
BUNDLE_SIZE_BONUS = 0.38
BUNDLE_COMPACTNESS_BONUS = 0.12


def load_q2_model():
    spec = importlib.util.spec_from_file_location("baseline_pricing", Q2_CODE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def coordinates_km(latitude, longitude, latitude_center):
    return np.column_stack(
        (
            longitude * 111.0 * np.cos(np.radians(latitude_center)),
            latitude * 111.0,
        )
    )


def load_new_tasks():
    frame = pd.read_csv(NEW_TASK_CSV)
    frame = frame.dropna(how="all").copy()
    frame = frame.iloc[:, :3]
    frame.columns = ["task_id", "latitude", "longitude"]
    frame["task_id"] = frame["task_id"].astype(str)
    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame = frame.dropna(subset=["task_id", "latitude", "longitude"])
    return frame.reset_index(drop=True)


def build_new_features(model, historical_data, historical_features, new_tasks):
    latitude_center = float(
        np.mean(np.concatenate((historical_data["lat"], new_tasks["latitude"])))
    )
    historical_xy = coordinates_km(
        historical_data["lat"], historical_data["lon"], latitude_center
    )
    new_xy = coordinates_km(
        new_tasks["latitude"].to_numpy(float),
        new_tasks["longitude"].to_numpy(float),
        latitude_center,
    )
    member_xy = coordinates_km(
        historical_data["member_lat"],
        historical_data["member_lon"],
        latitude_center,
    )

    historical_tree = cKDTree(historical_xy)
    new_tree = cKDTree(new_xy)
    member_tree = cKDTree(member_xy)

    nearest_member_km = member_tree.query(new_xy, k=1)[0]
    member_neighbors = member_tree.query_ball_point(
        new_xy, NEIGHBOR_RADIUS_KM
    )
    task_neighbors = new_tree.query_ball_point(new_xy, NEIGHBOR_RADIUS_KM)
    members_2km = np.array([len(x) for x in member_neighbors], dtype=int)
    tasks_2km = np.array([max(0, len(x) - 1) for x in task_neighbors], dtype=int)
    quota_2km = np.array(
        [historical_data["member_quota"][x].sum() for x in member_neighbors]
    )
    credit_2km = np.array(
        [historical_data["member_credit"][x].sum() for x in member_neighbors]
    )

    # Transfer the broad regional effect from the nearest historical task.
    nearest_historical = historical_tree.query(new_xy, k=1)[1]
    region = historical_features["region"][nearest_historical]
    region_dummies = np.column_stack(
        [
            (region == index).astype(float)
            for index in range(1, model.REGION_COUNT)
        ]
    )

    historical_density_cap = float(
        np.percentile(historical_features["tasks_2km"], 95)
    )
    clipped_tasks_2km = np.minimum(tasks_2km, historical_density_cap)
    fixed_continuous = np.column_stack(
        (
            np.minimum(nearest_member_km, 10.0),
            np.log1p(members_2km),
            np.log1p(clipped_tasks_2km),
            np.log1p(quota_2km),
            np.log1p(credit_2km),
        )
    )

    historical_pressure = (
        historical_features["tasks_2km"] + 1
    ) / (historical_features["members_2km"] + 1)
    pressure_reference = float(np.percentile(historical_pressure, 95))
    pressure = (tasks_2km + 1) / (members_2km + 1)
    congestion_penalty = PRESSURE_LOGIT_PENALTY * np.maximum(
        0.0, np.log(np.maximum(pressure, 1e-9) / pressure_reference)
    )

    return {
        "fixed_continuous": fixed_continuous,
        "region_dummies": region_dummies,
        "region": region,
        "nearest_member_km": nearest_member_km,
        "members_2km": members_2km,
        "tasks_2km": tasks_2km,
        "quota_2km": quota_2km,
        "credit_2km": credit_2km,
        "pressure": pressure,
        "pressure_reference": pressure_reference,
        "congestion_penalty": congestion_penalty,
        "historical_density_cap": historical_density_cap,
        "xy": new_xy,
    }


def form_packages(new_tasks, xy):
    count = len(new_tasks)
    package_id = np.full(count, -1, dtype=int)
    package_number = 0

    # Exact-coordinate groups are handled first and split into executable
    # packages of at most MAX_PACKAGE_SIZE tasks.
    rounded = new_tasks[["latitude", "longitude"]].round(6)
    exact_groups = rounded.groupby(["latitude", "longitude"]).indices
    for indexes in exact_groups.values():
        indexes = list(indexes)
        if len(indexes) < 2:
            continue
        for start in range(0, len(indexes), MAX_PACKAGE_SIZE):
            block = indexes[start : start + MAX_PACKAGE_SIZE]
            package_id[block] = package_number
            package_number += 1

    # Remaining tasks are greedily grouped with nearby tasks. Dense tasks are
    # processed first so that compact local groups are not broken up early.
    tree = cKDTree(xy)
    neighbors = tree.query_ball_point(xy, PACKAGE_RADIUS_KM)
    order = np.argsort([-len(x) for x in neighbors])
    for core in order:
        if package_id[core] >= 0:
            continue
        candidates = [
            index for index in neighbors[core] if package_id[index] < 0
        ]
        candidates.sort(key=lambda index: np.linalg.norm(xy[index] - xy[core]))
        block = candidates[:MAX_PACKAGE_SIZE]
        if not block:
            block = [int(core)]
        package_id[block] = package_number
        package_number += 1

    package_size = np.zeros(count, dtype=int)
    package_spread = np.zeros(count, dtype=float)
    package_bonus = np.zeros(count, dtype=float)
    rows = []
    for current_id in range(package_number):
        indexes = np.flatnonzero(package_id == current_id)
        points = xy[indexes]
        centroid = points.mean(axis=0)
        spread = float(np.max(np.linalg.norm(points - centroid, axis=1)))
        size = len(indexes)
        compactness = max(0.0, 1.0 - spread / PACKAGE_RADIUS_KM)
        bonus = 0.0
        if size > 1:
            bonus = (
                BUNDLE_SIZE_BONUS * np.log(size)
                + BUNDLE_COMPACTNESS_BONUS * compactness
            )
        package_size[indexes] = size
        package_spread[indexes] = spread
        package_bonus[indexes] = bonus
        rows.append(
            {
                "package_id": f"P{current_id + 1:04d}",
                "task_count": size,
                "latitude": float(new_tasks.loc[indexes, "latitude"].mean()),
                "longitude": float(new_tasks.loc[indexes, "longitude"].mean()),
                "spread_km": spread,
                "compactness": compactness,
                "bundle_logit_bonus": bonus,
                "task_ids": ";".join(new_tasks.loc[indexes, "task_id"]),
            }
        )

    package_labels = np.array(
        [f"P{value + 1:04d}" for value in package_id], dtype=object
    )
    return (
        package_labels,
        package_size,
        package_spread,
        package_bonus,
        pd.DataFrame(rows),
    )


def adjusted_probability(
    model,
    price,
    features,
    coefficient,
    means,
    scales,
    bundle_bonus,
):
    base = model.predict(price, features, coefficient, means, scales)
    utility = (
        logit(np.clip(base, 1e-6, 1 - 1e-6))
        - features["congestion_penalty"]
        + bundle_bonus
    )
    return expit(utility)


def choose_prices(
    model,
    features,
    coefficient,
    means,
    scales,
    bundle_bonus,
):
    candidates = np.arange(
        PRICE_MIN, PRICE_MAX + PRICE_STEP / 2, PRICE_STEP
    )
    probabilities = np.column_stack(
        [
            adjusted_probability(
                model,
                np.full(len(features["region"]), candidate),
                features,
                coefficient,
                means,
                scales,
                bundle_bonus,
            )
            for candidate in candidates
        ]
    )
    reaches_target = probabilities >= TARGET_PROBABILITY
    first_index = np.argmax(reaches_target, axis=1)
    unreachable = ~reaches_target.any(axis=1)
    first_index[unreachable] = len(candidates) - 1
    chosen_price = candidates[first_index]
    chosen_probability = probabilities[
        np.arange(len(chosen_price)), first_index
    ]
    return chosen_price, chosen_probability, unreachable


def assign_cities(frame):
    points = frame[["longitude", "latitude"]].to_numpy(float)
    city = np.full(len(frame), "Other", dtype=object)
    wanted = {"Guangzhou", "Shenzhen", "Dongguan", "Foshan"}
    with open(PREFECTURES_JSON, "r", encoding="utf-8") as handle:
        geojson = json.load(handle)

    for feature in geojson["features"]:
        name = feature.get("properties", {}).get("name")
        if name not in wanted:
            continue
        geometry = feature["geometry"]
        polygons = (
            geometry["coordinates"]
            if geometry["type"] == "MultiPolygon"
            else [geometry["coordinates"]]
        )
        mask = np.zeros(len(frame), dtype=bool)
        for polygon in polygons:
            if not polygon:
                continue
            outer_ring = np.asarray(polygon[0], dtype=float)
            mask |= PlotPath(outer_ring).contains_points(points)
        city[mask] = name
    return city


def scheme_row(name, price, probability, unreachable, bundled_tasks=0, packages=0):
    return {
        "scheme": name,
        "average_price": float(np.mean(price)),
        "posted_total": float(np.sum(price)),
        "expected_payout": float(np.sum(price * probability)),
        "expected_completions": float(np.sum(probability)),
        "expected_completion_rate": float(np.mean(probability)),
        "target_reached_tasks": int(np.sum(probability >= TARGET_PROBABILITY)),
        "unreachable_at_85_tasks": int(np.sum(unreachable)),
        "tasks_at_65": int(np.sum(price == PRICE_MIN)),
        "tasks_at_85": int(np.sum(price == PRICE_MAX)),
        "bundled_tasks": int(bundled_tasks),
        "packages": int(packages),
    }


def save_figure(comparison, task_results):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    labels = ["Uniform 75", "Individual", "Bundled"]
    rates = comparison["expected_completion_rate"].to_numpy() * 100
    axes[0].bar(labels, rates, color=["#94A3B8", "#3B82F6", "#0F766E"])
    axes[0].set_ylabel("Expected completion rate (%)")
    axes[0].set_ylim(0, max(80, rates.max() + 5))
    axes[0].set_title("Attachment 3 scheme comparison")
    for index, value in enumerate(rates):
        axes[0].text(index, value + 0.8, f"{value:.1f}%", ha="center")

    bins = np.arange(PRICE_MIN - 0.25, PRICE_MAX + 0.75, 0.5)
    axes[1].hist(
        task_results["bundled_price"],
        bins=bins,
        color="#0F766E",
        alpha=0.85,
    )
    axes[1].set_xlabel("Recommended price (yuan/task)")
    axes[1].set_ylabel("Tasks")
    axes[1].set_title("Bundled-pricing distribution")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "question4-scheme-comparison.png", dpi=180)
    plt.close(fig)


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    model = load_q2_model()
    # Ignore Excel's temporary lock workbook when Attachment 2 is open.
    model.MEMBER_XLSX = next(
        path
        for path in PROJECT_DIR.glob("*.xlsx")
        if not path.name.startswith("~$")
    )
    historical_data = model.parse_data()
    historical_features = model.make_features(historical_data)
    coefficient, means, scales, historical_probability = model.fit_model(
        historical_data, historical_features
    )
    new_tasks = load_new_tasks()
    features = build_new_features(
        model, historical_data, historical_features, new_tasks
    )

    (
        package_id,
        package_size,
        package_spread,
        package_bonus,
        package_summary,
    ) = form_packages(new_tasks, features["xy"])

    uniform_price = np.full(len(new_tasks), UNIFORM_PRICE)
    uniform_probability = adjusted_probability(
        model,
        uniform_price,
        features,
        coefficient,
        means,
        scales,
        np.zeros(len(new_tasks)),
    )
    uniform_unreachable = np.zeros(len(new_tasks), dtype=bool)

    individual_price, individual_probability, individual_unreachable = (
        choose_prices(
            model,
            features,
            coefficient,
            means,
            scales,
            np.zeros(len(new_tasks)),
        )
    )
    bundled_price, bundled_probability, bundled_unreachable = choose_prices(
        model,
        features,
        coefficient,
        means,
        scales,
        package_bonus,
    )

    city = assign_cities(new_tasks)
    task_results = new_tasks.copy()
    task_results["city"] = city
    task_results["region"] = features["region"]
    task_results["nearest_member_km"] = features["nearest_member_km"]
    task_results["members_2km"] = features["members_2km"]
    task_results["tasks_2km"] = features["tasks_2km"]
    task_results["quota_2km"] = features["quota_2km"]
    task_results["task_member_pressure"] = features["pressure"]
    task_results["congestion_logit_penalty"] = features["congestion_penalty"]
    task_results["package_id"] = package_id
    task_results["package_size"] = package_size
    task_results["package_spread_km"] = package_spread
    task_results["bundle_logit_bonus"] = package_bonus
    task_results["uniform_price"] = uniform_price
    task_results["uniform_probability"] = uniform_probability
    task_results["individual_price"] = individual_price
    task_results["individual_probability"] = individual_probability
    task_results["bundled_price"] = bundled_price
    task_results["bundled_probability"] = bundled_probability
    task_results["target_reached"] = bundled_probability >= TARGET_PROBABILITY
    task_results["unreachable_at_85"] = bundled_unreachable

    comparison = pd.DataFrame(
        [
            scheme_row(
                "uniform-75-single",
                uniform_price,
                uniform_probability,
                uniform_unreachable,
            ),
            scheme_row(
                "individual-pricing",
                individual_price,
                individual_probability,
                individual_unreachable,
            ),
            scheme_row(
                "bundled-pricing",
                bundled_price,
                bundled_probability,
                bundled_unreachable,
                bundled_tasks=int(np.sum(package_size > 1)),
                packages=int(np.sum(package_summary["task_count"] > 1)),
            ),
        ]
    )

    city_summary = (
        task_results.groupby("city", as_index=False)
        .agg(
            tasks=("task_id", "count"),
            average_price=("bundled_price", "mean"),
            expected_completion_rate=("bundled_probability", "mean"),
            median_tasks_2km=("tasks_2km", "median"),
            median_members_2km=("members_2km", "median"),
            median_pressure=("task_member_pressure", "median"),
            bundled_share=("package_size", lambda x: float(np.mean(x > 1))),
            target_reached_share=("target_reached", "mean"),
        )
        .sort_values("tasks", ascending=False)
    )

    package_probability = (
        task_results.groupby("package_id", as_index=False)
        .agg(
            average_price=("bundled_price", "mean"),
            total_reward=("bundled_price", "sum"),
            average_probability=("bundled_probability", "mean"),
            expected_completions=("bundled_probability", "sum"),
        )
    )
    package_summary = package_summary.merge(
        package_probability, on="package_id", how="left"
    )

    task_results.to_csv(
        RESULTS_DIR / "question4-task-pricing.csv",
        index=False,
        encoding="utf-8-sig",
    )
    comparison.to_csv(
        RESULTS_DIR / "question4-scheme-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )
    city_summary.to_csv(
        RESULTS_DIR / "question4-city-summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    package_summary.to_csv(
        RESULTS_DIR / "question4-package-summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    save_figure(comparison, task_results)

    historical_auc = model.auc_score(
        historical_data["completed"], historical_probability
    )
    summary = f"""Question 4 baseline run
=======================
Valid new tasks: {len(new_tasks)}
Historical model training AUC: {historical_auc:.4f}
Historical observed completion rate: {np.mean(historical_data['completed']):.4f}
Historical 95th percentile task density (2 km): {features['historical_density_cap']:.2f}
Historical 95th percentile task/member pressure: {features['pressure_reference']:.4f}
New median task/member pressure: {np.median(features['pressure']):.4f}

Price range: {PRICE_MIN:.1f}--{PRICE_MAX:.1f} yuan
Target completion probability: {TARGET_PROBABILITY:.2f}
Congestion logit penalty coefficient: {PRESSURE_LOGIT_PENALTY:.2f}
Bundle radius: {PACKAGE_RADIUS_KM:.2f} km
Maximum tasks per package: {MAX_PACKAGE_SIZE}

{comparison.to_string(index=False)}

Interpretation note
-------------------
The predicted rates are model-based implementation estimates, not observed
outcomes.  Attachment 3 has no actual price or completion-status field.
The congestion and bundling corrections are scenario assumptions and should
be checked with a pilot release before full deployment.
"""
    (DOCS_DIR / "run-summary.txt").write_text(summary, encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
