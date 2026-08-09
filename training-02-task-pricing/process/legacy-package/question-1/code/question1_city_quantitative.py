"""Final quantitative cause review for Question 1.

External evidence is kept at the city level:
- 2017 resident population and administrative-area population density;
- 2017 Amap peak congestion delay index.

Task-level inference uses only variables observed or constructed from the
competition attachments, plus city fixed effects. This avoids treating a city
index repeated across hundreds of tasks as hundreds of independent external
observations.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MplPolygon
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from question1_external_quantitative import (
    TRAFFIC_DATA,
    assign_city,
    fit_logistic,
    geometry_rings,
    make_effect_plot,
    make_traffic_map,
    model_coefficients,
    spatial_cross_validation,
)


RAW_DIR = QUESTION_DIR / "data" / "raw"
RESULTS_DIR = QUESTION_DIR / "results"
FIGURES_DIR = QUESTION_DIR / "figures"
DOCS_DIR = QUESTION_DIR / "docs"

BASE_INDICATORS = RESULTS_DIR / "question1-spatial-indicators.csv"
BOUNDARY_JSON = RAW_DIR / "guangdong-prefecture-boundaries.json"
CITY_POPULATION_CSV = RAW_DIR / "city-population-2017.csv"


def prepare_data():
    tasks = pd.read_csv(BASE_INDICATORS)
    population = pd.read_csv(CITY_POPULATION_CSV)
    with BOUNDARY_JSON.open("r", encoding="utf-8") as handle:
        features = json.load(handle)["features"]

    assignments = [
        assign_city(float(lon), float(lat), features)
        for lon, lat in zip(tasks["longitude"], tasks["latitude"])
    ]
    tasks["city"] = [item[0] for item in assignments]
    tasks["city_assignment_method"] = [item[1] for item in assignments]
    population_density = population.set_index("city")["population_density_per_km2"].to_dict()
    tasks["population_density_per_km2"] = tasks["city"].map(population_density)
    tasks["congestion_index_2017"] = tasks["city"].map(
        {city: item["congestion_index_2017"] for city, item in TRAFFIC_DATA.items()}
    )
    tasks["traffic_index_type"] = tasks["city"].map(
        {city: item["index_type"] for city, item in TRAFFIC_DATA.items()}
    )
    tasks["log_members_2km"] = np.log1p(tasks["members_2km"])
    tasks["log_tasks_2km"] = np.log1p(tasks["tasks_2km"])
    tasks["log_competition"] = np.log1p(tasks["competition_index"])
    return tasks, population, features


def build_city_summary(tasks):
    summary = tasks.groupby("city").agg(
        tasks=("completed", "size"),
        completed=("completed", "sum"),
        completion_rate=("completed", "mean"),
        average_price=("price", "mean"),
        average_members_2km=("members_2km", "mean"),
        average_tasks_2km=("tasks_2km", "mean"),
        average_competition_index=("competition_index", "mean"),
        population_density_per_km2=("population_density_per_km2", "first"),
        congestion_index_2017=("congestion_index_2017", "first"),
        traffic_index_type=("traffic_index_type", "first"),
    ).reset_index()
    summary["traffic_source"] = summary["city"].map(
        {city: item["source"] for city, item in TRAFFIC_DATA.items()}
    )
    return summary.sort_values("tasks", ascending=False)


def build_city_correlations(summary):
    usable = summary.dropna(subset=[
        "completion_rate",
        "population_density_per_km2",
        "congestion_index_2017",
    ])
    rows = []
    for variable in ["population_density_per_km2", "congestion_index_2017"]:
        rho, p_value = spearmanr(usable[variable], usable["completion_rate"])
        rows.append({
            "variable": variable,
            "cities_n": len(usable),
            "spearman_rho_with_completion_rate": rho,
            "p_value_exploratory": p_value,
            "interpretation": "descriptive only; too few independent cities for causal inference",
        })
    return pd.DataFrame(rows)


def add_city_dummies(tasks):
    frequent = tasks["city"].value_counts()
    modeled_cities = sorted(frequent[frequent >= 20].index.tolist())
    reference_city = tasks["city"].value_counts().index[0]
    predictors = []
    for city in modeled_cities:
        if city == reference_city:
            continue
        column = f"city_{city}"
        tasks[column] = (tasks["city"] == city).astype(float)
        predictors.append(column)
    return predictors, reference_city


def make_population_map(tasks, population, features, city_summary):
    fig, ax = plt.subplots(figsize=(12.0, 8.5), dpi=180)
    extent = (
        tasks["longitude"].min() - 0.08,
        tasks["longitude"].max() + 0.08,
        tasks["latitude"].min() - 0.07,
        tasks["latitude"].max() + 0.07,
    )
    density_lookup = population.set_index("city")["population_density_per_km2"].to_dict()
    summary_lookup = city_summary.set_index("city").to_dict("index")
    color_values = np.log1p(population["population_density_per_km2"])
    norm_values = Normalize(
        vmin=float(color_values.quantile(0.02)),
        vmax=float(color_values.quantile(0.98)),
    )
    cmap = plt.get_cmap("YlOrRd")
    for feature in features:
        city = feature["properties"]["name"]
        density = density_lookup.get(city)
        fill = "#E5E7EB" if density is None else cmap(norm_values(math.log1p(density)))
        visible = False
        for ring in geometry_rings(feature["geometry"]):
            arr = np.asarray(ring)
            if (
                arr[:, 0].max() < extent[0]
                or arr[:, 0].min() > extent[1]
                or arr[:, 1].max() < extent[2]
                or arr[:, 1].min() > extent[3]
            ):
                continue
            visible = True
            ax.add_patch(MplPolygon(
                arr,
                closed=True,
                facecolor=fill,
                edgecolor="white",
                linewidth=0.8,
                alpha=0.88,
                zorder=1,
            ))
        if visible and density is not None and city in summary_lookup:
            center = feature["properties"].get("centroid") or feature["properties"].get("center")
            stats = summary_lookup[city]
            ax.text(
                center[0],
                center[1],
                f"{city[:-1]}\n{density:,.0f} 人/km²\n完成率 {stats['completion_rate']:.1%}",
                ha="center",
                va="center",
                fontsize=8.3,
                weight="bold",
                color="#111827",
                bbox={"facecolor": "white", "alpha": 0.72, "edgecolor": "none", "pad": 2},
                zorder=5,
            )

    completed = tasks["completed"] == 1
    failed = ~completed
    ax.scatter(
        tasks.loc[completed, "longitude"],
        tasks.loc[completed, "latitude"],
        s=11,
        c="#2563EB",
        alpha=0.55,
        linewidths=0,
        zorder=3,
    )
    ax.scatter(
        tasks.loc[failed, "longitude"],
        tasks.loc[failed, "latitude"],
        s=23,
        c="#111827",
        marker="X",
        alpha=0.82,
        linewidths=0,
        zorder=4,
    )
    scalar = plt.cm.ScalarMappable(norm=norm_values, cmap=cmap)
    colorbar = fig.colorbar(scalar, ax=ax, fraction=0.033, pad=0.018)
    ticks = colorbar.get_ticks()
    colorbar.set_ticks(ticks)
    colorbar.set_ticklabels([f"{math.expm1(value):,.0f}" for value in ticks])
    colorbar.set_label("2017 年常住人口密度（人/km²）")
    ax.legend(handles=[
        Line2D([0], [0], marker="o", linestyle="", markerfacecolor="#2563EB", markeredgecolor="none", label="已完成"),
        Line2D([0], [0], marker="X", linestyle="", markerfacecolor="#111827", markeredgecolor="none", label="未完成"),
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
        "人口数据：各市 2017 年统计公报；密度按常住人口/行政区面积计算",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.3,
        color="#475569",
        bbox={"facecolor": "white", "alpha": 0.82, "edgecolor": "none", "pad": 3},
    )
    fig.tight_layout()
    fig.savefig(
        FIGURES_DIR / "question1-external-population-map.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(fig)


def write_source_notes():
    content = """# External data sources for Question 1

## Population

The file `data/raw/city-population-2017.csv` records 2017 resident population,
administrative area, calculated population density, and the source URL for each
city. Shenzhen, Guangzhou, and Dongguan use city-government or statistics-bureau
bulletins. Foshan uses the bulletin reproduced with attribution to the Foshan
Statistics Bureau.

## Traffic

The local file `data/raw/amap-2017-traffic-report.pdf` is the Amap 2017 annual
traffic report. Guangzhou (1.892) and Shenzhen (1.751) are transcribed from the
large-city ranking. Dongguan (1.622) is reported by a local article quoting the
same annual report. Foshan and Huizhou are marked `derived`: their 2016 annual
index is multiplied by the 2017 year-on-year change shown by Amap.

The congestion delay index is congested travel time divided by free-flow travel
time. Values are annual city-level indicators, not road-level speeds.

## Boundaries and interpretation

Guangdong prefecture boundaries come from:
https://geo.datav.aliyun.com/areas_v3/bound/440000_full.json

Population and congestion are city-level evidence. Repeating a city value for
hundreds of tasks does not create hundreds of independent observations.
Therefore, external indicators are used for city comparison and mapping.
Task-level regression uses attachment-derived price, member supply, task density,
price competition, and city fixed effects. Results are associations, not causal
effects.
"""
    (DOCS_DIR / "external-data-sources.md").write_text(content, encoding="utf-8")


def write_analysis_notes(summary, correlations, coefficients, metrics, reference_city):
    core_cities = ["深圳市", "广州市", "东莞市", "佛山市"]
    rows = []
    for city in core_cities:
        match = summary[summary["city"] == city]
        if match.empty:
            continue
        item = match.iloc[0]
        traffic = "无完整年度值" if pd.isna(item["congestion_index_2017"]) else f"{item['congestion_index_2017']:.3f}"
        rows.append(
            f"{city}：任务 {int(item['tasks'])} 个，完成率 {item['completion_rate']:.2%}，"
            f"人口密度 {item['population_density_per_km2']:.0f} 人/km²，拥堵指数 {traffic}，"
            f"平均标价 {item['average_price']:.2f} 元，2 km 内平均会员 {item['average_members_2km']:.2f} 人，"
            f"平均竞争指数 {item['average_competition_index']:.2f}。"
        )

    correlation_text = "\n".join(
        f"{item.variable} 与城市完成率的 Spearman 相关系数为 "
        f"{item.spearman_rho_with_completion_rate:.3f}（完整城市仅 {int(item.cities_n)} 个，"
        f"只作描述）。"
        for item in correlations.itertuples(index=False)
    )
    baseline = metrics[metrics["model"] == "platform-baseline"].iloc[0]
    adjusted = metrics[metrics["model"] == "city-adjusted"].iloc[0]
    shenzhen_effect = coefficients[
        (coefficients["model"] == "city-adjusted")
        & (coefficients["variable"] == "city_深圳市")
    ]
    if shenzhen_effect.empty:
        residual_text = "深圳任务数未达到城市固定效应入模阈值。"
    else:
        item = shenzhen_effect.iloc[0]
        residual_text = (
            f"深圳城市项 OR={item['odds_ratio_per_sd']:.3f}，95% CI "
            f"[{item['odds_ratio_ci_low']:.3f}, {item['odds_ratio_ci_high']:.3f}]，"
            f"p={item['p_value_wald']:.4f}。这是控制内部指标后的剩余区域差异，"
            f"不能直接命名为交通效应。"
        )

    content = f"""2017 CUMCM B 题“拍照赚钱”
问题一定量原因复核：人口密度、交通拥堵与平台内部因素

一、为什么需要重做

旧分析由“深圳未完成任务多”直接推断“深圳交通拥堵、停车困难”，缺少外部数据，也没有控制任务价格、会员供给和局部竞争。本次使用 2017 年城市人口统计、高德年度拥堵指数和附件任务数据建立两层证据。

二、城市级外部证据

{chr(10).join(rows)}

深圳人口密度明显高，但人口密度同时可能增加潜在会员供给，不能预设为负面因素。更关键的是，深圳 2017 年高峰拥堵延时指数 1.751，低于广州的 1.892；高德报告还将深圳列入年度拥堵缓解幅度较大的城市。因此，“深圳比广州更堵，所以未完成更多”与 2017 年城市级证据不一致。

城市级描述性相关：

{correlation_text}

由于拥有完整交通指标的城市很少，以上相关不作显著性或因果解释。

三、任务级 Logistic 模型

基准模型使用任务价格、2 km 内会员数、2 km 内任务数和局部价格竞争强度。城市调整模型在此基础上加入任务所属城市虚拟变量，参考城市为 {reference_city}。

基准模型：AUC={baseline['auc']:.3f}，Brier={baseline['brier']:.3f}，Log Loss={baseline['log_loss']:.3f}。
城市调整模型：AUC={adjusted['auc']:.3f}，Brier={adjusted['brier']:.3f}，Log Loss={adjusted['log_loss']:.3f}。

{residual_text}

四、可以成立的结论

1. 深圳确实存在显著的任务失败聚集，但城市人口密度和年度拥堵数据不能单独解释这种聚集。
2. 深圳并非样本城市中 2017 年最拥堵的城市，原来的“深圳交通拥堵导致失败”应删除或降为待检验假设。
3. 当前数据支持程度更高的原因是低价、会员供给与任务数量不匹配、相邻任务价格竞争，以及城市固定效应表示的未观测区域差异。
4. 人口密度高并不等于有效会员供给高。应优先使用附件二直接计算的会员数量、预订限额和信誉供给。
5. 若要证明交通原因，必须取得任务发布时间对应的道路速度、拥堵延时或停车可达性数据；城市年度平均指数只能用于反证和背景校验。

五、论文表述

建议写为：“外部数据复核表明，深圳任务失败聚集不能简单归因于城市总体交通拥堵。2017 年深圳高峰拥堵延时指数低于广州，但任务完成率仍明显偏低。控制任务价格、会员供给和局部竞争后仍存在城市剩余效应，说明平台内部供需结构和未观测的局部执行成本共同作用；交通拥堵仅作为需要更细道路数据验证的候选因素。”
"""
    (DOCS_DIR / "quantitative-cause-analysis.txt").write_text(content, encoding="utf-8")


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    tasks, population, features = prepare_data()
    summary = build_city_summary(tasks)
    correlations = build_city_correlations(summary)
    city_predictors, reference_city = add_city_dummies(tasks)
    platform_predictors = [
        "price",
        "log_members_2km",
        "log_tasks_2km",
        "log_competition",
    ]
    adjusted_predictors = [*platform_predictors, *city_predictors]
    baseline = fit_logistic(tasks, platform_predictors)
    adjusted = fit_logistic(tasks, adjusted_predictors)

    labels = {
        "price": "任务价格",
        "log_members_2km": "2 km会员供给（log）",
        "log_tasks_2km": "2 km任务密度（log）",
        "log_competition": "局部价格竞争（log）",
    }
    labels.update({column: column.removeprefix("city_") + "城市项" for column in city_predictors})
    coefficients = pd.DataFrame([
        *model_coefficients("platform-baseline", baseline, labels),
        *model_coefficients("city-adjusted", adjusted, labels),
    ])
    metrics = pd.DataFrame([
        {
            "model": "platform-baseline",
            "n": len(baseline["data"]),
            "predictors": len(platform_predictors),
            "log_likelihood": baseline["log_likelihood"],
            **baseline["metrics"],
        },
        {
            "model": "city-adjusted",
            "n": len(adjusted["data"]),
            "predictors": len(adjusted_predictors),
            "log_likelihood": adjusted["log_likelihood"],
            **adjusted["metrics"],
        },
    ])
    cross_validation = spatial_cross_validation(tasks, adjusted_predictors)

    tasks.to_csv(RESULTS_DIR / "question1-external-spatial-indicators.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(RESULTS_DIR / "question1-city-external-summary.csv", index=False, encoding="utf-8-sig")
    correlations.to_csv(RESULTS_DIR / "question1-city-external-correlations.csv", index=False, encoding="utf-8-sig")
    coefficients.to_csv(RESULTS_DIR / "question1-quantitative-model-coefficients.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(RESULTS_DIR / "question1-quantitative-model-metrics.csv", index=False, encoding="utf-8-sig")
    cross_validation.to_csv(RESULTS_DIR / "question1-quantitative-spatial-cv.csv", index=False, encoding="utf-8-sig")

    make_population_map(tasks, population, features, summary)
    make_traffic_map(tasks, features, summary)
    make_effect_plot(coefficients)
    write_source_notes()
    write_analysis_notes(summary, correlations, coefficients, metrics, reference_city)

    print(summary.to_string(index=False))
    print(metrics.to_string(index=False))
    print(coefficients[coefficients["model"] == "city-adjusted"].to_string(index=False))


if __name__ == "__main__":
    main()
