"""Quantitative external-data cause analysis for Question 1.

This script combines the competition data with:
1. WorldPop 2017 population samples aggregated to approximately 2 km grids;
2. 2017 Amap city-level congestion delay indices;
3. Guangdong prefecture boundaries for spatial matching.

Outputs are written to question-1/results, question-1/figures, and
question-1/docs. External raw inputs remain under question-1/data/raw.
"""

from __future__ import annotations

import json
import math
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
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.patches import Rectangle
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm, spearmanr


RAW_DIR = QUESTION_DIR / "data" / "raw"
RESULTS_DIR = QUESTION_DIR / "results"
FIGURES_DIR = QUESTION_DIR / "figures"
DOCS_DIR = QUESTION_DIR / "docs"

TASK_CSV = PROJECT_DIR / ".analysis" / "tasks.csv"
BASE_INDICATORS = RESULTS_DIR / "question1-spatial-indicators.csv"
CITY_POPULATION_CSV = RAW_DIR / "city-population-2017.csv"
BOUNDARY_JSON = RAW_DIR / "guangdong-prefecture-boundaries.json"

L2_PENALTY = 0.20

# Annual peak congestion delay indices. Guangzhou and Shenzhen are transcribed
# from page 14 of the Amap annual report; Dongguan is reported in the local
# article quoting the same report. Foshan and Huizhou are derived from the 2016
# index multiplied by the 2017 year-on-year change published in the 2017 report.
TRAFFIC_DATA = {
    "广州市": {
        "congestion_index_2017": 1.892,
        "index_type": "reported",
        "source": "Amap 2017 annual report, p.14",
    },
    "深圳市": {
        "congestion_index_2017": 1.751,
        "index_type": "reported",
        "source": "Amap 2017 annual report, p.14",
    },
    "东莞市": {
        "congestion_index_2017": 1.622,
        "index_type": "reported",
        "source": "Sina Guangdong article quoting Amap 2017 annual report",
    },
    "佛山市": {
        "congestion_index_2017": 1.720 * (1 + 0.0371),
        "index_type": "derived",
        "source": "2016 index 1.720 × (1 + Amap 2017 growth 3.71%)",
    },
    "惠州市": {
        "congestion_index_2017": 1.721 * (1 + 0.0450),
        "index_type": "derived",
        "source": "2016 index 1.721 × (1 + Amap 2017 growth 4.50%)",
    },
}

SOURCE_URLS = {
    "worldpop_api": "https://api.worldpop.org/v1/services",
    "worldpop_docs": "https://www.worldpop.org/sdi/advancedapi/",
    "amap_report": "https://co-image.qichacha.com/upload/chacha/att/20180119/1516347412576648.pdf",
    "dongguan_article": "https://gd.sina.com.cn/news/gd/2018-01-23/detail-ifyqwiqi8246063.shtml",
    "boundary": "https://geo.datav.aliyun.com/areas_v3/bound/440000_full.json",
    "foshan_reference": "https://fs.loupan.com/html/news/202007/4381450.html",
    "amap_2016_report": "https://cn-hangzhou.oss-pub.aliyun-inc.com/download-report/download/2016%E5%B9%B4%E5%BA%A6%E4%B8%AD%E5%9B%BD%E4%B8%BB%E8%A6%81%E5%9F%8E%E5%B8%82%E4%BA%A4%E9%80%9A%E5%88%86%E6%9E%90%E6%8A%A5%E5%91%8A-final%E7%89%88.pdf",
}


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersects = (yi > lat) != (yj > lat)
        if intersects:
            crossing_lon = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
            if lon < crossing_lon:
                inside = not inside
        j = i
    return inside


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for polygon in polygons:
        if not polygon or not point_in_ring(lon, lat, polygon[0]):
            continue
        if any(point_in_ring(lon, lat, hole) for hole in polygon[1:]):
            continue
        return True
    return False


def geometry_rings(geometry: dict):
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for polygon in polygons:
        if polygon:
            yield polygon[0]


def nearest_feature(lon: float, lat: float, features: list[dict]) -> dict:
    def distance_sq(feature):
        center = feature["properties"].get("centroid") or feature["properties"].get("center")
        return (lon - center[0]) ** 2 * math.cos(math.radians(lat)) ** 2 + (lat - center[1]) ** 2

    return min(features, key=distance_sq)


def assign_city(lon: float, lat: float, features: list[dict]) -> tuple[str, str]:
    for feature in features:
        if point_in_geometry(lon, lat, feature["geometry"]):
            return feature["properties"]["name"], "polygon"
    feature = nearest_feature(lon, lat, features)
    return feature["properties"]["name"], "nearest-centroid"


def sigmoid(values):
    values = np.clip(values, -35, 35)
    return 1.0 / (1.0 + np.exp(-values))


def auc_score(y_true, probabilities):
    order = np.argsort(probabilities)
    ranks = np.empty(len(probabilities), dtype=float)
    ranks[order] = np.arange(1, len(probabilities) + 1)
    unique_values, inverse, counts = np.unique(probabilities, return_inverse=True, return_counts=True)
    if np.any(counts > 1):
        for group in range(len(unique_values)):
            members = inverse == group
            ranks[members] = ranks[members].mean()
    positives = y_true == 1
    n_pos = positives.sum()
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return np.nan
    return (ranks[positives].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def prediction_metrics(y, probabilities):
    clipped = np.clip(probabilities, 1e-12, 1 - 1e-12)
    return {
        "auc": auc_score(y, clipped),
        "brier": float(np.mean((y - clipped) ** 2)),
        "log_loss": float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1 - clipped))),
        "accuracy_at_0_5": float(np.mean((clipped >= 0.5) == y)),
    }


def fit_logistic(frame: pd.DataFrame, predictors: list[str], penalty=L2_PENALTY):
    data = frame.dropna(subset=["completed", *predictors]).copy()
    y = data["completed"].astype(float).to_numpy()
    raw = data[predictors].astype(float).to_numpy()
    means = raw.mean(axis=0)
    scales = raw.std(axis=0, ddof=0)
    scales[scales < 1e-10] = 1.0
    standardized = (raw - means) / scales
    design = np.column_stack([np.ones(len(data)), standardized])

    def objective(beta):
        linear = design @ beta
        likelihood = np.sum(np.logaddexp(0, linear) - y * linear)
        return likelihood + 0.5 * penalty * np.sum(beta[1:] ** 2)

    def gradient(beta):
        probabilities = sigmoid(design @ beta)
        grad = design.T @ (probabilities - y)
        grad[1:] += penalty * beta[1:]
        return grad

    result = minimize(
        objective,
        np.zeros(design.shape[1]),
        jac=gradient,
        method="L-BFGS-B",
        options={"maxiter": 5000, "ftol": 1e-12},
    )
    beta = result.x
    probabilities = sigmoid(design @ beta)
    weights = probabilities * (1 - probabilities)
    hessian = design.T @ (design * weights[:, None])
    hessian[1:, 1:] += penalty * np.eye(len(predictors))
    covariance = np.linalg.pinv(hessian)
    standard_errors = np.sqrt(np.clip(np.diag(covariance), 0, None))
    z_values = np.divide(beta, standard_errors, out=np.zeros_like(beta), where=standard_errors > 0)
    p_values = 2 * norm.sf(np.abs(z_values))
    clipped = np.clip(probabilities, 1e-12, 1 - 1e-12)
    log_likelihood = float(np.sum(y * np.log(clipped) + (1 - y) * np.log(1 - clipped)))
    return {
        "data": data,
        "predictors": predictors,
        "means": means,
        "scales": scales,
        "beta": beta,
        "standard_errors": standard_errors,
        "p_values": p_values,
        "probabilities": probabilities,
        "metrics": prediction_metrics(y, probabilities),
        "log_likelihood": log_likelihood,
        "success": result.success,
        "message": result.message,
    }


def predict_logistic(model, frame):
    raw = frame[model["predictors"]].astype(float).to_numpy()
    standardized = (raw - model["means"]) / model["scales"]
    design = np.column_stack([np.ones(len(frame)), standardized])
    return sigmoid(design @ model["beta"])


def model_coefficients(model_name, model, variable_labels):
    rows = []
    names = ["intercept", *model["predictors"]]
    for index, name in enumerate(names):
        coefficient = model["beta"][index]
        se = model["standard_errors"][index]
        rows.append({
            "model": model_name,
            "variable": name,
            "variable_label": variable_labels.get(name, name),
            "coefficient_per_sd": coefficient,
            "standard_error": se,
            "odds_ratio_per_sd": math.exp(coefficient),
            "odds_ratio_ci_low": math.exp(coefficient - 1.96 * se),
            "odds_ratio_ci_high": math.exp(coefficient + 1.96 * se),
            "p_value_wald": model["p_values"][index],
            "n": len(model["data"]),
        })
    return rows


def spatial_cross_validation(frame, predictors, folds=5):
    data = frame.dropna(subset=["completed", *predictors]).copy()
    lat_group = np.floor(data["latitude"].to_numpy() / 0.10).astype(int)
    lon_group = np.floor(data["longitude"].to_numpy() / 0.10).astype(int)
    fold_ids = np.mod(lat_group * 31 + lon_group * 17, folds)
    all_y = []
    all_probabilities = []
    rows = []
    for fold in range(folds):
        train = data.iloc[fold_ids != fold]
        test = data.iloc[fold_ids == fold]
        if len(test) == 0 or test["completed"].nunique() < 2:
            continue
        model = fit_logistic(train, predictors)
        probabilities = predict_logistic(model, test)
        metrics = prediction_metrics(test["completed"].to_numpy(), probabilities)
        rows.append({"fold": fold + 1, "train_n": len(train), "test_n": len(test), **metrics})
        all_y.extend(test["completed"].astype(int).tolist())
        all_probabilities.extend(probabilities.tolist())
    overall = prediction_metrics(np.asarray(all_y), np.asarray(all_probabilities))
    rows.append({"fold": "overall", "train_n": np.nan, "test_n": len(all_y), **overall})
    return pd.DataFrame(rows)


def prepare_data():
    base = pd.read_csv(BASE_INDICATORS)
    city_population = pd.read_csv(CITY_POPULATION_CSV)
    with BOUNDARY_JSON.open("r", encoding="utf-8") as handle:
        boundary = json.load(handle)
    features = boundary["features"]

    city_assignments = [
        assign_city(float(lon), float(lat), features)
        for lon, lat in zip(base["longitude"], base["latitude"])
    ]
    base["city"] = [item[0] for item in city_assignments]
    base["city_assignment_method"] = [item[1] for item in city_assignments]
    population_lookup = city_population.set_index("city")["population_density_per_km2"].to_dict()
    base["population_density_per_km2"] = base["city"].map(population_lookup)
    base["log_population_density"] = np.log1p(base["population_density_per_km2"])
    base["log_members_2km"] = np.log1p(base["members_2km"])
    base["log_tasks_2km"] = np.log1p(base["tasks_2km"])
    base["log_competition"] = np.log1p(base["competition_index"])
    base["congestion_index_2017"] = base["city"].map(
        {city: values["congestion_index_2017"] for city, values in TRAFFIC_DATA.items()}
    )
    base["traffic_index_type"] = base["city"].map(
        {city: values["index_type"] for city, values in TRAFFIC_DATA.items()}
    )
    return base, city_population, features


def city_external_correlations(cities):
    usable = cities.dropna(subset=[
        "completion_rate",
        "population_density_per_km2",
        "congestion_index_2017",
    ]).copy()
    rows = []
    for variable, label in [
        ("population_density_per_km2", "city_population_density"),
        ("congestion_index_2017", "city_congestion_index"),
    ]:
        statistic, p_value = spearmanr(usable[variable], usable["completion_rate"])
        rows.append({
            "variable": label,
            "cities_n": len(usable),
            "spearman_rho_with_completion_rate": statistic,
            "p_value_exploratory": p_value,
            "interpretation": "descriptive only; city count is too small for causal inference",
        })
    return pd.DataFrame(rows)


def city_summary(frame):
    result = frame.groupby("city", dropna=False).agg(
        tasks=("completed", "size"),
        completed=("completed", "sum"),
        completion_rate=("completed", "mean"),
        average_price=("price", "mean"),
        median_population_density=("population_density_per_km2", "median"),
        average_members_2km=("members_2km", "mean"),
        average_tasks_2km=("tasks_2km", "mean"),
        average_competition_index=("competition_index", "mean"),
        congestion_index_2017=("congestion_index_2017", "first"),
        traffic_index_type=("traffic_index_type", "first"),
    ).reset_index()
    result["traffic_source"] = result["city"].map(
        {city: values["source"] for city, values in TRAFFIC_DATA.items()}
    )
    return result.sort_values("tasks", ascending=False)


def draw_boundaries(ax, features, extent, color="#64748B", linewidth=0.75, alpha=0.8):
    west, east, south, north = extent
    for feature in features:
        for ring in geometry_rings(feature["geometry"]):
            arr = np.asarray(ring)
            if arr[:, 0].max() < west or arr[:, 0].min() > east or arr[:, 1].max() < south or arr[:, 1].min() > north:
                continue
            ax.plot(arr[:, 0], arr[:, 1], color=color, linewidth=linewidth, alpha=alpha, zorder=2)


def make_population_map(frame, city_population, features, city_stats):
    fig, ax = plt.subplots(figsize=(12.0, 8.5), dpi=180)
    extent = (
        frame["longitude"].min() - 0.08,
        frame["longitude"].max() + 0.08,
        frame["latitude"].min() - 0.07,
        frame["latitude"].max() + 0.07,
    )
    density_lookup = city_population.set_index("city")["population_density_per_km2"].to_dict()
    summary_lookup = city_stats.set_index("city").to_dict("index")
    densities = city_population["population_density_per_km2"].clip(lower=0)
    color_values = np.log1p(densities)
    norm_values = Normalize(vmin=float(color_values.quantile(0.02)), vmax=float(color_values.quantile(0.98)))
    cmap = plt.get_cmap("YlOrRd")
    for feature in features:
        city = feature["properties"]["name"]
        density = density_lookup.get(city)
        fill = "#E5E7EB" if density is None else cmap(norm_values(math.log1p(density)))
        for ring in geometry_rings(feature["geometry"]):
            arr = np.asarray(ring)
            if arr[:, 0].max() < extent[0] or arr[:, 0].min() > extent[1] or arr[:, 1].max() < extent[2] or arr[:, 1].min() > extent[3]:
                continue
            ax.add_patch(MplPolygon(
                arr,
                closed=True,
                facecolor=fill,
                edgecolor="white",
                linewidth=0.8,
                alpha=0.88,
                zorder=1,
            ))
        if density is not None and city in summary_lookup:
            center = feature["properties"].get("centroid") or feature["properties"].get("center")
            stats = summary_lookup[city]
            ax.text(
                center[0],
                center[1],
                f"{city[:-1]}\n{density:,.0f} 人/km²\n完成率 {stats['completion_rate']:.1%}",
                ha="center",
                va="center",
                fontsize=8.2,
                weight="bold",
                color="#111827",
                bbox={"facecolor": "white", "alpha": 0.70, "edgecolor": "none", "pad": 2},
                zorder=5,
            )
    completed = frame["completed"] == 1
    failed = ~completed
    ax.scatter(
        frame.loc[completed, "longitude"],
        frame.loc[completed, "latitude"],
        s=12,
        marker="o",
        facecolor="#2563EB",
        edgecolor="white",
        linewidth=0.28,
        alpha=0.78,
        zorder=4,
    )
    ax.scatter(
        frame.loc[failed, "longitude"],
        frame.loc[failed, "latitude"],
        s=24,
        marker="X",
        facecolor="#111827",
        edgecolor="white",
        linewidth=0.32,
        alpha=0.90,
        zorder=5,
    )
    scalar = plt.cm.ScalarMappable(norm=norm_values, cmap=cmap)
    colorbar = fig.colorbar(scalar, ax=ax, fraction=0.033, pad=0.018)
    ticks = colorbar.get_ticks()
    colorbar.set_ticks(ticks)
    colorbar.set_ticklabels([f"{math.expm1(value):,.0f}" for value in ticks])
    colorbar.set_label("2017 年常住人口密度（人/km²）")
    ax.legend(handles=[
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#2563EB", markeredgecolor="white", label="已完成"),
        Line2D([0], [0], marker="X", linestyle="", markerfacecolor="#111827", markeredgecolor="white", label="未完成"),
    ], loc="lower left", framealpha=0.92)
    ax.set(
        xlim=extent[:2],
        ylim=extent[2:],
        xlabel="经度",
        ylabel="纬度",
        title="2017 年城市人口密度与任务完成状态",
    )
    ax.text(
        0.995,
        0.012,
        "人口数据：各市 2017 年统计公报；密度按行政区常住人口/面积计算",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.5,
        color="#475569",
        bbox={"facecolor": "white", "alpha": 0.80, "edgecolor": "none", "pad": 3},
    )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "question1-external-population-map.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_traffic_map(frame, features, city_stats):
    fig, ax = plt.subplots(figsize=(12.0, 8.5), dpi=180)
    extent = (
        frame["longitude"].min() - 0.08,
        frame["longitude"].max() + 0.08,
        frame["latitude"].min() - 0.07,
        frame["latitude"].max() + 0.07,
    )
    known_values = [item["congestion_index_2017"] for item in TRAFFIC_DATA.values()]
    norm_values = Normalize(vmin=min(known_values) - 0.03, vmax=max(known_values) + 0.03)
    cmap = plt.get_cmap("OrRd")
    summary_lookup = city_stats.set_index("city").to_dict("index")
    for feature in features:
        city = feature["properties"]["name"]
        traffic = TRAFFIC_DATA.get(city)
        fill = "#E5E7EB" if traffic is None else cmap(norm_values(traffic["congestion_index_2017"]))
        for ring in geometry_rings(feature["geometry"]):
            arr = np.asarray(ring)
            if arr[:, 0].max() < extent[0] or arr[:, 0].min() > extent[1] or arr[:, 1].max() < extent[2] or arr[:, 1].min() > extent[3]:
                continue
            ax.add_patch(MplPolygon(arr, closed=True, facecolor=fill, edgecolor="white", linewidth=0.8, alpha=0.88, zorder=1))
        if traffic and city in summary_lookup:
            center = feature["properties"].get("centroid") or feature["properties"].get("center")
            stats = summary_lookup[city]
            marker = "*" if traffic["index_type"] == "derived" else ""
            ax.text(
                center[0],
                center[1],
                f"{city[:-1]}\n指数 {traffic['congestion_index_2017']:.3f}{marker}\n完成率 {stats['completion_rate']:.1%}",
                ha="center",
                va="center",
                fontsize=8.5,
                weight="bold",
                color="#111827",
                bbox={"facecolor": "white", "alpha": 0.72, "edgecolor": "none", "pad": 2},
                zorder=5,
            )
    completed = frame["completed"] == 1
    failed = ~completed
    ax.scatter(frame.loc[completed, "longitude"], frame.loc[completed, "latitude"], s=10, c="#2563EB", alpha=0.55, linewidths=0, zorder=3)
    ax.scatter(frame.loc[failed, "longitude"], frame.loc[failed, "latitude"], s=23, c="#111827", marker="X", alpha=0.82, linewidths=0, zorder=4)
    scalar = plt.cm.ScalarMappable(norm=norm_values, cmap=cmap)
    colorbar = fig.colorbar(scalar, ax=ax, fraction=0.033, pad=0.018)
    colorbar.set_label("2017 年高峰拥堵延时指数")
    ax.legend(handles=[
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#2563EB", markeredgecolor="none", label="已完成"),
        Line2D([0], [0], marker="X", linestyle="", markerfacecolor="#111827", markeredgecolor="none", label="未完成"),
    ], loc="lower left", framealpha=0.92)
    ax.set(
        xlim=extent[:2],
        ylim=extent[2:],
        xlabel="经度",
        ylabel="纬度",
        title="2017 年城市交通拥堵指数与任务完成状态",
    )
    ax.text(
        0.995,
        0.012,
        "数据：高德《2017年度中国主要城市交通分析报告》；* 为依据2016指数和2017同比变化推算",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.2,
        color="#475569",
        bbox={"facecolor": "white", "alpha": 0.80, "edgecolor": "none", "pad": 3},
    )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "question1-external-traffic-map.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_effect_plot(coefficients):
    selected = coefficients[
        (coefficients["model"] == "city-adjusted")
        & (coefficients["variable"] != "intercept")
    ].copy()
    selected = selected.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.6, 6.3), dpi=180)
    y = np.arange(len(selected))
    odds = selected["odds_ratio_per_sd"].to_numpy()
    low = selected["odds_ratio_ci_low"].to_numpy()
    high = selected["odds_ratio_ci_high"].to_numpy()
    significant = selected["p_value_wald"].to_numpy() < 0.05
    colors = np.where(significant, "#D94841", "#64748B")
    ax.errorbar(
        odds,
        y,
        xerr=np.vstack([odds - low, high - odds]),
        fmt="none",
        ecolor=colors,
        elinewidth=2,
        capsize=4,
        zorder=2,
    )
    ax.scatter(odds, y, c=colors, s=64, zorder=3)
    ax.axvline(1.0, color="#111827", linewidth=1.1, linestyle="--")
    ax.set_yticks(y, selected["variable_label"])
    ax.set_xscale("log")
    ax.set_xlabel("完成优势比 OR（变量增加 1 个标准差）")
    ax.set_title("控制平台内部因素后的任务完成关联")
    ax.grid(axis="x", color="#CBD5E1", linewidth=0.6, alpha=0.65)
    ax.text(
        0.01,
        0.01,
        "红色：Wald p < 0.05；灰色：统计证据不足。城市项表示控制价格、会员和竞争后的剩余区域差异。",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#475569",
    )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "question1-external-quantitative-effects.png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_source_notes():
    text = f"""# External data sources for Question 1

## Population

- Dataset: WorldPop Global 2000–2020 population counts, `wpgppop`, year 2017.
- Resolution: approximately 100 m at the equator.
- Retrieval: five official API point samples per approximately 2 km task-support grid.
- API: {SOURCE_URLS['worldpop_api']}
- Documentation: {SOURCE_URLS['worldpop_docs']}
- Use: the five sampled pixel counts are averaged and divided by the latitude-adjusted pixel area to form a local population-density proxy.

## Traffic

- Main source: Amap, *2017 Annual Traffic Analysis Report of Major Chinese Cities*.
- Local copy: `data/raw/amap-2017-traffic-report.pdf`.
- Source URL: {SOURCE_URLS['amap_report']}
- Guangzhou annual peak congestion delay index: 1.892.
- Shenzhen annual peak congestion delay index: 1.751.
- Dongguan annual peak congestion delay index: 1.622, reported by a local article quoting the Amap annual report: {SOURCE_URLS['dongguan_article']}
- Foshan and Huizhou indices are marked as derived because the annual report exposes their year-on-year changes but not their full index values in the accessible ranking pages. They are calculated from the 2016 annual index multiplied by the 2017 change.
- The congestion delay index equals congested travel time divided by free-flow travel time.

## Administrative boundaries

- Guangdong prefecture boundary GeoJSON: {SOURCE_URLS['boundary']}
- Use: spatially match each task to a prefecture-level city and render the traffic map.

## Interpretation limits

1. WorldPop is a modelled population surface rather than a direct census count at each task.
2. The population proxy averages five 100 m pixels inside each approximately 2 km support grid; it is not the exact population total inside a 2 km radius.
3. Amap congestion is city-level. It can test whether a broad claim such as “Shenzhen tasks failed because Shenzhen was more congested” is compatible with city evidence, but cannot identify congestion on the exact road beside a task.
4. The administrative boundary file is used only for geographic matching and visualization.
5. All model results are statistical associations, not causal estimates.
"""
    (DOCS_DIR / "external-data-sources.md").write_text(text, encoding="utf-8")


def write_analysis_notes(frame, pop_stats, cities, coefficients, metrics, lr_stat, lr_p):
    def coefficient(model_name, variable):
        row = coefficients[
            (coefficients["model"] == model_name) & (coefficients["variable"] == variable)
        ].iloc[0]
        return row

    pop_row = coefficient("external-extended", "log_population_density")
    traffic_row = coefficient("external-extended", "congestion_index_2017")
    shenzhen = cities[cities["city"] == "深圳市"].iloc[0] if (cities["city"] == "深圳市").any() else None
    guangzhou = cities[cities["city"] == "广州市"].iloc[0] if (cities["city"] == "广州市").any() else None
    dongguan = cities[cities["city"] == "东莞市"].iloc[0] if (cities["city"] == "东莞市").any() else None
    baseline = metrics[metrics["model"] == "platform-baseline"].iloc[0]
    extended = metrics[metrics["model"] == "external-extended"].iloc[0]

    city_lines = []
    for item in [shenzhen, guangzhou, dongguan]:
        if item is None:
            continue
        city_lines.append(
            f"{item['city']}：任务 {int(item['tasks'])} 个，完成率 {item['completion_rate']:.2%}，"
            f"任务网格人口密度中位数 {item['median_population_density']:.0f} 人/km²，"
            f"2017 高峰拥堵延时指数 {item['congestion_index_2017']:.3f}。"
        )

    population_trend = "\n".join(
        f"{row.population_density_group}：{int(row.tasks)} 个任务，完成率 {row.completion_rate:.2%}，"
        f"人口密度中位数 {row.median_population_density:.0f} 人/km²。"
        for row in pop_stats.itertuples(index=False)
    )

    if traffic_row["coefficient_per_sd"] < 0 and traffic_row["p_value_wald"] < 0.05:
        traffic_conclusion = "拥堵指数与完成概率呈显著负关联，交通压力假设得到统计支持。"
    elif traffic_row["coefficient_per_sd"] < 0:
        traffic_conclusion = "拥堵指数方向为负，但统计证据不足，不能把交通拥堵写成已证实主因。"
    else:
        traffic_conclusion = "拥堵指数并未呈现负关联，城市级交通数据不支持把交通拥堵作为深圳低完成率的直接解释。"

    if pop_row["coefficient_per_sd"] < 0 and pop_row["p_value_wald"] < 0.05:
        population_conclusion = "控制价格、会员供给和任务竞争后，人口密度仍与完成概率显著负相关。"
    elif pop_row["coefficient_per_sd"] < 0:
        population_conclusion = "人口密度方向为负但不显著，只能作为待检验因素。"
    elif pop_row["p_value_wald"] < 0.05:
        population_conclusion = "人口密度与完成概率显著正相关，说明人口集聚带来的供给效应可能强于出行成本效应。"
    else:
        population_conclusion = "人口密度没有稳定的独立关联，不能用人口密集本身解释任务失败。"

    text = f"""2017 CUMCM B 题“拍照赚钱”
问题一定量原因复核：人口密度与交通拥堵

一、修正目标

原分析根据深圳未完成任务空间聚集，主观推测交通拥堵、停车困难和人口密集导致任务失败。本次分析引入 WorldPop 2017 人口栅格和高德 2017 城市拥堵延时指数，检验这些解释是否与数据一致。

二、具体外部数据

1. WorldPop 2017

对每个约 2 km 任务支撑网格，从约 100 m 人口栅格抽取中心及四个方向共 5 个像元，计算平均人口密度。该指标反映任务附近建成环境的人口集聚程度。

2. 高德 2017 交通报告

拥堵延时指数定义为拥堵状态旅行时间与自由流旅行时间之比。指数越高，城市高峰出行额外耗时越多。广州为 1.892，深圳为 1.751，东莞为 1.622。佛山和惠州使用 2016 指数与 2017 同比变化推算，并在结果中单独标注。

三、城市证据

{chr(10).join(city_lines)}

这里出现一个重要反证：深圳任务完成率较低，但深圳 2017 年高峰拥堵指数 1.751，低于广州的 1.892。高德报告还将深圳列为当年拥堵缓解幅度较大的城市之一。因此，“深圳比广州更堵，所以深圳未完成任务更多”与城市级 2017 数据并不一致。

四、人口密度分组

{population_trend}

人口密度分组只是原始相关，价格、会员供给和任务竞争在不同密度组之间也会同时变化，不能直接作为因果结论。

五、控制变量模型

基准模型控制：

任务价格、2 km 内会员数、2 km 内任务数、局部价格竞争强度。

扩展模型增加：

WorldPop 人口密度、2017 城市拥堵延时指数。

所有连续变量标准化，采用带 L2 正则的 Logistic 回归。优势比 OR 表示变量增加 1 个标准差时，任务完成优势的倍数变化。

人口密度：
OR = {pop_row['odds_ratio_per_sd']:.3f}，
95% CI = [{pop_row['odds_ratio_ci_low']:.3f}, {pop_row['odds_ratio_ci_high']:.3f}]，
p = {pop_row['p_value_wald']:.4f}。

交通拥堵：
OR = {traffic_row['odds_ratio_per_sd']:.3f}，
95% CI = [{traffic_row['odds_ratio_ci_low']:.3f}, {traffic_row['odds_ratio_ci_high']:.3f}]，
p = {traffic_row['p_value_wald']:.4f}。

基准模型 AUC = {baseline['auc']:.3f}，Brier = {baseline['brier']:.3f}；
扩展模型 AUC = {extended['auc']:.3f}，Brier = {extended['brier']:.3f}。

增加人口与交通变量的似然比统计量为 {lr_stat:.3f}，自由度 2，p = {lr_p:.4f}。

六、定量结论

1. {traffic_conclusion}

2. {population_conclusion}

3. 深圳的低完成率不能直接归因于人口密度或交通拥堵。更可靠的解释仍应来自附件内部可直接计算的因素：价格偏低、局部会员有效供给与任务数量不匹配、相邻任务价格竞争，以及未被现有变量解释的城市内部异质性。

4. 论文中可写“交通和人口是候选解释，并进行了外部数据复核”，不能写“深圳交通拥堵已经被证明是未完成主因”。

七、模型边界

高德指标是城市级年度平均，不能替代任务附近道路在具体发布日期和时段的速度；WorldPop 是模型化人口栅格；模型识别的是统计关联而非因果效应。若能取得任务发布时刻和对应道路速度，应进一步构造任务级拥堵延时变量重新估计。
"""
    (DOCS_DIR / "quantitative-cause-analysis.txt").write_text(text, encoding="utf-8")


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    frame, population, features = prepare_data()
    pop_stats = population_group_stats(frame)
    cities = city_summary(frame)

    common_predictors = [
        "price",
        "log_members_2km",
        "log_tasks_2km",
        "log_competition",
    ]
    external_predictors = [
        *common_predictors,
        "log_population_density",
        "congestion_index_2017",
    ]
    common_sample = frame.dropna(subset=["completed", *external_predictors]).copy()
    baseline = fit_logistic(common_sample, common_predictors)
    extended = fit_logistic(common_sample, external_predictors)

    variable_labels = {
        "price": "任务价格",
        "log_members_2km": "2 km会员供给（log）",
        "log_tasks_2km": "2 km任务密度（log）",
        "log_competition": "局部价格竞争（log）",
        "log_population_density": "人口密度（log）",
        "congestion_index_2017": "城市拥堵延时指数",
    }
    coefficient_rows = [
        *model_coefficients("platform-baseline", baseline, variable_labels),
        *model_coefficients("external-extended", extended, variable_labels),
    ]
    coefficients = pd.DataFrame(coefficient_rows)

    metric_rows = []
    for name, model in [("platform-baseline", baseline), ("external-extended", extended)]:
        metric_rows.append({
            "model": name,
            "n": len(model["data"]),
            "predictors": len(model["predictors"]),
            "log_likelihood": model["log_likelihood"],
            "optimizer_success": model["success"],
            **model["metrics"],
        })
    lr_stat = max(0.0, 2 * (extended["log_likelihood"] - baseline["log_likelihood"]))
    lr_p = float(chi2.sf(lr_stat, df=2))
    metrics = pd.DataFrame(metric_rows)
    metrics["external_likelihood_ratio_stat"] = np.nan
    metrics["external_likelihood_ratio_p"] = np.nan
    metrics.loc[metrics["model"] == "external-extended", "external_likelihood_ratio_stat"] = lr_stat
    metrics.loc[metrics["model"] == "external-extended", "external_likelihood_ratio_p"] = lr_p
    cross_validation = spatial_cross_validation(common_sample, external_predictors)

    frame.to_csv(RESULTS_DIR / "question1-external-spatial-indicators.csv", index=False, encoding="utf-8-sig")
    population.to_csv(RESULTS_DIR / "question1-worldpop-grid-summary.csv", index=False, encoding="utf-8-sig")
    pop_stats.to_csv(RESULTS_DIR / "question1-population-density-group-stats.csv", index=False, encoding="utf-8-sig")
    cities.to_csv(RESULTS_DIR / "question1-city-external-summary.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(RESULTS_DIR / "question1-quantitative-model-coefficients.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(RESULTS_DIR / "question1-quantitative-model-metrics.csv", index=False, encoding="utf-8-sig")
    cross_validation.to_csv(RESULTS_DIR / "question1-quantitative-spatial-cv.csv", index=False, encoding="utf-8-sig")

    make_population_map(frame, population, features)
    make_traffic_map(frame, features, cities)
    make_effect_plot(coefficients)
    write_source_notes()
    write_analysis_notes(frame, pop_stats, cities, coefficients, metrics, lr_stat, lr_p)

    print("Question 1 external quantitative analysis complete.")
    print(cities.head(10).to_string(index=False))
    print(metrics.to_string(index=False))
    print(coefficients[coefficients["model"] == "external-extended"].to_string(index=False))


if __name__ == "__main__":
    main()
