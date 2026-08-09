"""Quantitative cause analysis for Question 1.

This script supplements the original descriptive maps with:

1. task-level spatial supply, competition, and relative-price indicators;
2. a penalized logistic model with city fixed effects;
3. bootstrap confidence intervals for adjusted odds ratios;
4. a city comparison that combines task outcomes with compact 2017
   population and 2017-Q2 traffic statistics.

The city-level external indicators are contextual evidence only. They are not
treated as task-level congestion observations and are not used to claim a
causal traffic effect.
"""

from __future__ import annotations

import json
import os
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
import numpy as np
import pandas as pd
from matplotlib.path import Path as MplPath
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.special import expit

TASK_CSV = PROJECT_DIR / ".analysis" / "tasks.csv"
PREFECTURES_JSON = PROJECT_DIR / ".analysis" / "prefectures.json"
MEMBER_XLSX = next(
    p for p in PROJECT_DIR.glob("*.xlsx") if not p.name.startswith("~$")
)
FIGURES_DIR = QUESTION_DIR / "figures"
RESULTS_DIR = QUESTION_DIR / "results"
PROCESSED_DIR = QUESTION_DIR / "data" / "processed"
DOCS_DIR = QUESTION_DIR / "docs"

RADIUS_KM = 2.0
RIDGE = 0.20
BOOTSTRAP_RUNS = 240
RNG = np.random.default_rng(20260726)


def polygon_paths(geometry):
    """Yield exterior polygon rings from GeoJSON Polygon/MultiPolygon."""
    if geometry["type"] == "Polygon":
        polygons = [geometry["coordinates"]]
    elif geometry["type"] == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return
    for polygon in polygons:
        exterior = np.asarray(polygon[0], dtype=float)
        holes = [np.asarray(ring, dtype=float) for ring in polygon[1:]]
        yield MplPath(exterior), [MplPath(hole) for hole in holes]


def assign_prefectures(lon, lat):
    points = np.column_stack([lon, lat])
    assigned = np.full(len(points), "其他", dtype=object)
    with PREFECTURES_JSON.open(encoding="utf-8") as handle:
        geo = json.load(handle)
    wanted = {"深圳市", "广州市", "佛山市", "东莞市", "惠州市", "中山市"}
    for feature in geo["features"]:
        name = feature["properties"].get("地名", "")
        if name not in wanted:
            continue
        inside = np.zeros(len(points), dtype=bool)
        for exterior, holes in polygon_paths(feature["geometry"]):
            part = exterior.contains_points(points, radius=1e-10)
            for hole in holes:
                part &= ~hole.contains_points(points, radius=1e-10)
            inside |= part
        assigned[inside] = name
    return assigned


def fit_logistic(x, y, ridge=RIDGE, beta0=None):
    """Fit a ridge logistic model; the intercept is not penalized."""
    n_features = x.shape[1]
    start = np.zeros(n_features) if beta0 is None else beta0.copy()
    penalty = np.ones(n_features)
    penalty[0] = 0.0

    def objective(beta):
        eta = x @ beta
        loss = np.logaddexp(0.0, eta).sum() - y @ eta
        return loss + 0.5 * ridge * np.sum(penalty * beta**2)

    def gradient(beta):
        p = expit(x @ beta)
        return x.T @ (p - y) + ridge * penalty * beta

    result = minimize(
        objective,
        start,
        jac=gradient,
        method="L-BFGS-B",
        options={"maxiter": 1000, "ftol": 1e-11, "gtol": 1e-8},
    )
    if not result.success:
        raise RuntimeError(result.message)
    return result.x


def auc_score(y, score):
    order = np.argsort(score)
    ranks = np.empty(len(score), dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    # Average tied ranks.
    _, inverse, counts = np.unique(score, return_inverse=True, return_counts=True)
    for group, count in enumerate(counts):
        if count > 1:
            idx = np.flatnonzero(inverse == group)
            ranks[idx] = ranks[idx].mean()
    n1 = y.sum()
    n0 = len(y) - n1
    return (ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def bootstrap_coefficients(x, y, fitted):
    draws = []
    for _ in range(BOOTSTRAP_RUNS):
        idx = RNG.integers(0, len(y), len(y))
        try:
            draws.append(fit_logistic(x[idx], y[idx], beta0=fitted))
        except RuntimeError:
            continue
    return np.asarray(draws)


def build_indicators():
    tasks = pd.read_csv(TASK_CSV)
    members = pd.read_excel(MEMBER_XLSX)

    task_id = tasks.iloc[:, 0].astype(str).to_numpy()
    lat = tasks.iloc[:, 1].astype(float).to_numpy()
    lon = tasks.iloc[:, 2].astype(float).to_numpy()
    price = tasks.iloc[:, 3].astype(float).to_numpy()
    completed = tasks.iloc[:, 4].astype(int).to_numpy()

    member_coords = (
        members.iloc[:, 1]
        .astype(str)
        .str.extract(r"([0-9.]+)\s+([0-9.]+)")
        .astype(float)
    )
    member_lat = member_coords.iloc[:, 0].to_numpy()
    member_lon = member_coords.iloc[:, 1].to_numpy()
    member_quota = members.iloc[:, 2].astype(float).to_numpy()
    member_credit = members.iloc[:, 4].astype(float).to_numpy()

    lat0 = float(np.mean(lat))
    lon_scale = 111.0 * np.cos(np.radians(lat0))
    task_xy = np.column_stack([lon * lon_scale, lat * 111.0])
    member_xy = np.column_stack([member_lon * lon_scale, member_lat * 111.0])
    task_tree = cKDTree(task_xy)
    member_tree = cKDTree(member_xy)
    nearest_member_km = member_tree.query(task_xy, k=1)[0]

    member_neighbors = member_tree.query_ball_point(task_xy, RADIUS_KM)
    task_neighbors = task_tree.query_ball_point(task_xy, RADIUS_KM)
    members_2km = np.array([len(v) for v in member_neighbors])
    tasks_2km = np.array([max(len(v) - 1, 0) for v in task_neighbors])
    quota_2km = np.array(
        [member_quota[idx].sum() if len(idx) else 0.0 for idx in member_neighbors]
    )
    credit_2km = np.array(
        [member_credit[idx].sum() if len(idx) else 0.0 for idx in member_neighbors]
    )
    avg_quota_2km = quota_2km / np.maximum(members_2km, 1)

    local_mean_price = np.array(
        [
            price[[k for k in neighbors if k != i]].mean()
            if len(neighbors) > 1
            else price[i]
            for i, neighbors in enumerate(task_neighbors)
        ]
    )
    higher_priced_share = np.array(
        [
            np.mean([price[k] > price[i] for k in neighbors if k != i])
            if len(neighbors) > 1
            else 0.0
            for i, neighbors in enumerate(task_neighbors)
        ]
    )

    frame = pd.DataFrame(
        {
            "task_id": task_id,
            "latitude": lat,
            "longitude": lon,
            "city": assign_prefectures(lon, lat),
            "price": price,
            "completed": completed,
            "nearest_member_km": nearest_member_km,
            "members_2km": members_2km,
            "tasks_2km": tasks_2km,
            "quota_2km": quota_2km,
            "credit_2km": credit_2km,
            "average_quota_2km": avg_quota_2km,
            "local_mean_price_2km": local_mean_price,
            "relative_price_2km": price - local_mean_price,
            "higher_priced_task_share_2km": higher_priced_share,
            "task_member_pressure": (tasks_2km + 1) / (members_2km + 1),
        }
    )
    return frame


def model_design(frame, add_city):
    continuous = pd.DataFrame(
        {
            "price_per_5_yuan": (frame["price"] - 65.0) / 5.0,
            "nearest_member_per_km": frame["nearest_member_km"],
            "members_2km_doubling": np.log2(frame["members_2km"] + 1.0),
            "tasks_2km_doubling": np.log2(frame["tasks_2km"] + 1.0),
            "average_quota_doubling": np.log2(frame["average_quota_2km"] + 1.0),
            "relative_price_per_5_yuan": frame["relative_price_2km"] / 5.0,
            "higher_priced_share_per_10pct": frame[
                "higher_priced_task_share_2km"
            ]
            * 10.0,
        }
    )
    design = pd.DataFrame({"intercept": np.ones(len(frame))})
    design = pd.concat([design, continuous.reset_index(drop=True)], axis=1)
    if add_city:
        cities = pd.get_dummies(frame["city"], prefix="city", dtype=float)
        # Dongguan is the best-performing major city and is used as reference.
        if "city_东莞市" in cities:
            cities = cities.drop(columns=["city_东莞市"])
        design = pd.concat([design, cities.reset_index(drop=True)], axis=1)
    return design


def write_effect_table(columns, beta, draws):
    labels = {
        "price_per_5_yuan": ("任务价格", "每增加5元"),
        "nearest_member_per_km": ("最近会员距离", "每增加1 km"),
        "members_2km_doubling": ("2 km会员数", "会员数翻倍"),
        "tasks_2km_doubling": ("2 km任务数", "任务数翻倍"),
        "average_quota_doubling": ("周边会员平均预订限额", "限额翻倍"),
        "relative_price_per_5_yuan": ("相对周边平均价格", "每高5元"),
        "higher_priced_share_per_10pct": ("周边更高价任务占比", "每增加10个百分点"),
    }
    rows = []
    for idx, name in enumerate(columns):
        if name == "intercept":
            continue
        ci = np.quantile(np.exp(draws[:, idx]), [0.025, 0.975])
        if name.startswith("city_"):
            variable = name.replace("city_", "") + "固定效应"
            unit = "相对东莞市"
            category = "区域残余效应"
        else:
            variable, unit = labels[name]
            category = "任务级因素"
        rows.append(
            {
                "variable": variable,
                "category": category,
                "effect_unit": unit,
                "coefficient": beta[idx],
                "adjusted_odds_ratio": np.exp(beta[idx]),
                "ci_2_5": ci[0],
                "ci_97_5": ci[1],
                "direction": (
                    "positive"
                    if ci[0] > 1
                    else "negative"
                    if ci[1] < 1
                    else "uncertain"
                ),
            }
        )
    return pd.DataFrame(rows)


def build_city_comparison(frame, baseline_probability):
    # Population figures are year-end 2017 official statistics. Areas are
    # administrative land areas; density is a citywide contextual indicator.
    external = pd.DataFrame(
        [
            ["深圳市", 1252.83, 1997.47, 1.783, 27.24],
            ["广州市", 1449.84, 7434.40, 1.883, 24.96],
            ["佛山市", 765.67, 3797.72, 1.793, 24.94],
            ["东莞市", 834.25, 2460.10, 1.598, 31.71],
        ],
        columns=[
            "city",
            "population_2017_10k",
            "area_km2",
            "q2_2017_peak_delay_index",
            "q2_2017_peak_speed_kmh",
        ],
    )
    external["population_density_2017_per_km2"] = (
        external["population_2017_10k"] * 10000 / external["area_km2"]
    )
    task_summary = (
        frame.assign(baseline_probability=baseline_probability)
        .groupby("city", as_index=False)
        .agg(
            tasks=("completed", "size"),
            completed=("completed", "sum"),
            observed_completion_rate=("completed", "mean"),
            internal_model_expected_rate=("baseline_probability", "mean"),
            average_price=("price", "mean"),
            average_members_2km=("members_2km", "mean"),
            average_tasks_2km=("tasks_2km", "mean"),
        )
    )
    task_summary["residual_completion_gap"] = (
        task_summary["observed_completion_rate"]
        - task_summary["internal_model_expected_rate"]
    )
    result = external.merge(task_summary, on="city", how="left")
    return result


def make_figures(effects, city):
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    task_effects = effects[effects["category"] == "任务级因素"].copy()
    task_effects = task_effects.iloc[::-1]
    ypos = np.arange(len(task_effects))
    center = task_effects["adjusted_odds_ratio"].to_numpy()
    low = task_effects["ci_2_5"].to_numpy()
    high = task_effects["ci_97_5"].to_numpy()
    fig, ax = plt.subplots(figsize=(10.2, 6.1), dpi=170)
    ax.errorbar(
        center,
        ypos,
        xerr=np.vstack([center - low, high - center]),
        fmt="o",
        color="#176B87",
        ecolor="#79A7A8",
        capsize=4,
        markersize=7,
    )
    ax.axvline(1.0, color="#C44536", linestyle="--", linewidth=1.3)
    ax.set_yticks(ypos, task_effects["variable"])
    ax.set_xlabel("调整后优势比 OR（95% Bootstrap区间）")
    ax.set_title("问题一：任务未完成因素的多变量定量检验")
    ax.grid(axis="x", alpha=0.20)
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "question1-quantitative-odds-ratios.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)

    city_plot = city.sort_values("q2_2017_peak_delay_index")
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 5.2), dpi=170)
    axes[0].scatter(
        city_plot["q2_2017_peak_delay_index"],
        city_plot["observed_completion_rate"] * 100,
        s=100,
        c="#D85B42",
        edgecolors="white",
        linewidths=1.2,
    )
    axes[1].scatter(
        city_plot["population_density_2017_per_km2"],
        city_plot["observed_completion_rate"] * 100,
        s=100,
        c="#2F7D8C",
        edgecolors="white",
        linewidths=1.2,
    )
    for _, row in city_plot.iterrows():
        for ax, xcol in [
            (axes[0], "q2_2017_peak_delay_index"),
            (axes[1], "population_density_2017_per_km2"),
        ]:
            ax.annotate(
                row["city"].replace("市", ""),
                (row[xcol], row["observed_completion_rate"] * 100),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=10,
            )
    axes[0].set(
        xlabel="2017 Q2 高峰拥堵延时指数",
        ylabel="任务完成率（%）",
        title="交通拥堵与任务完成率（城市级）",
    )
    axes[1].set(
        xlabel="2017 年常住人口密度（人/km²）",
        ylabel="任务完成率（%）",
        title="人口密度与任务完成率（城市级）",
    )
    for ax in axes:
        ax.grid(alpha=0.20)
    fig.suptitle("城市级外部证据：仅作相关性佐证（n=4）", fontsize=14)
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "question1-city-population-traffic-comparison.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def main():
    for directory in [FIGURES_DIR, RESULTS_DIR, PROCESSED_DIR, DOCS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

    frame = build_indicators()
    frame.to_csv(
        PROCESSED_DIR / "question1-cause-indicators.csv",
        index=False,
        encoding="utf-8-sig",
    )

    y = frame["completed"].to_numpy(dtype=float)
    base_design = model_design(frame, add_city=False)
    fixed_design = model_design(frame, add_city=True)
    base_x = base_design.to_numpy(dtype=float)
    fixed_x = fixed_design.to_numpy(dtype=float)
    base_beta = fit_logistic(base_x, y)
    fixed_beta = fit_logistic(fixed_x, y)
    base_probability = expit(base_x @ base_beta)
    fixed_probability = expit(fixed_x @ fixed_beta)
    draws = bootstrap_coefficients(fixed_x, y, fixed_beta)

    effects = write_effect_table(fixed_design.columns, fixed_beta, draws)
    effects.to_csv(
        RESULTS_DIR / "question1-logistic-effects.csv",
        index=False,
        encoding="utf-8-sig",
    )

    city = build_city_comparison(frame, base_probability)
    city.to_csv(
        RESULTS_DIR / "question1-city-population-traffic-comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    major = city.dropna(subset=["observed_completion_rate"]).copy()
    traffic_corr = major[
        ["q2_2017_peak_delay_index", "observed_completion_rate"]
    ].corr(method="spearman").iloc[0, 1]
    population_corr = major[
        ["population_density_2017_per_km2", "observed_completion_rate"]
    ].corr(method="spearman").iloc[0, 1]
    metrics = pd.DataFrame(
        [
            ["base_task_model_auc", auc_score(y, base_probability)],
            ["city_fixed_effect_model_auc", auc_score(y, fixed_probability)],
            ["base_task_model_brier", np.mean((base_probability - y) ** 2)],
            ["city_fixed_effect_model_brier", np.mean((fixed_probability - y) ** 2)],
            ["bootstrap_successful_runs", len(draws)],
            ["city_spearman_traffic_vs_completion", traffic_corr],
            ["city_spearman_population_density_vs_completion", population_corr],
        ],
        columns=["metric", "value"],
    )
    metrics.to_csv(
        RESULTS_DIR / "question1-quantitative-model-metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    make_figures(effects, city)
    print(metrics.to_string(index=False))
    print(city.to_string(index=False))
    print(effects.to_string(index=False))


if __name__ == "__main__":
    main()
