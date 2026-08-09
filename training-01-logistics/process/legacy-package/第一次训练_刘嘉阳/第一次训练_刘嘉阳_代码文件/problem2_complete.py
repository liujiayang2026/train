# Integrated code for Problem 2. Run this file after Problem 1 outputs are available.


# ============================================================
# Part 1: problem2_dc5_integer_tradeoff.py
# Source: 问题2_优化版\code\problem2_dc5_integer_tradeoff.py
# ============================================================

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pulp


# ============================================================
# 1. 路径与参数
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "原始资料" / "附件1：物流网络历史货量数据.xlsx"
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
RESULT_DIR = BASE_DIR / "问题2_优化版" / "results"

CLOSED_SITE = "DC5"
ALLOWANCES = [0, 2, 5]
SOLVER_TIME_LIMIT = 120
EPS = 1e-6


# ============================================================
# 2. 数据读取与能力上限
# ============================================================

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    history = pd.read_excel(DATA_PATH)
    pred = pd.read_csv(PRED_PATH)
    pred = pred.rename(
        columns={
            "origin": "场地1",
            "dest": "场地2",
            "date": "日期",
            "forecast_volume": "预测货量",
        }
    )
    history["日期"] = pd.to_datetime(history["日期"])
    pred["日期"] = pd.to_datetime(pred["日期"])
    return history, pred[["场地1", "场地2", "edge", "日期", "预测货量"]]


def build_capacities(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edge_cap = (
        history.groupby(["场地1", "场地2"], as_index=False)["货量"]
        .max()
        .rename(columns={"货量": "线路能力"})
    )

    out_daily = history.groupby(["日期", "场地1"])["货量"].sum().rename("out")
    in_daily = history.groupby(["日期", "场地2"])["货量"].sum().rename("in")
    site_daily = (
        pd.concat([out_daily, in_daily], axis=1)
        .fillna(0)
        .reset_index()
        .rename(columns={"level_1": "场地"})
    )
    site_daily["处理量"] = site_daily["out"] + site_daily["in"]
    site_cap = (
        site_daily.groupby("场地", as_index=False)["处理量"]
        .max()
        .rename(columns={"处理量": "场地能力"})
    )
    return edge_cap, site_cap


# ============================================================
# 3. 单日数据准备
# ============================================================

def prepare_day(
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict, dict, dict]:
    day = day_pred.merge(edge_cap, on=["场地1", "场地2"], how="left")
    day["线路能力"] = day["线路能力"].fillna(0).round().astype(int)
    day["预测货量"] = day["预测货量"].round().astype(int)

    affected = day[((day["场地1"] == CLOSED_SITE) | (day["场地2"] == CLOSED_SITE)) & (day["预测货量"] > 0)].copy()
    base = day[(day["场地1"] != CLOSED_SITE) & (day["场地2"] != CLOSED_SITE)].copy()

    edge_base = {
        (row["场地1"], row["场地2"]): int(row["预测货量"])
        for _, row in base.iterrows()
    }
    edge_capacity = {
        (row["场地1"], row["场地2"]): int(row["线路能力"])
        for _, row in base.iterrows()
    }
    site_capacity = {
        row["场地"]: int(round(row["场地能力"]))
        for _, row in site_cap[site_cap["场地"] != CLOSED_SITE].iterrows()
    }

    site_base_load: dict[str, int] = {}
    for _, row in base.iterrows():
        src, dst, volume = row["场地1"], row["场地2"], int(row["预测货量"])
        site_base_load[src] = site_base_load.get(src, 0) + volume
        site_base_load[dst] = site_base_load.get(dst, 0) + volume

    return day, affected, edge_base, edge_capacity, site_base_load, site_capacity


def build_demands_and_candidates(
    affected: pd.DataFrame,
    edge_base: dict[tuple[str, str], int],
    edge_capacity: dict[tuple[str, str], int],
) -> tuple[list[dict], list[tuple[int, tuple[str, str]]]]:
    demand_rows: list[dict] = []
    alloc_pairs: list[tuple[int, tuple[str, str]]] = []

    for ridx, (_, row) in enumerate(affected.iterrows()):
        src, dst = row["场地1"], row["场地2"]
        demand = int(row["预测货量"])
        demand_rows.append(
            {
                "需求编号": ridx,
                "原线路": f"{src}->{dst}",
                "起点": src,
                "终点": dst,
                "需求类型": "出DC5" if src == CLOSED_SITE else "入DC5",
                "需求量": demand,
            }
        )

        if dst == CLOSED_SITE:
            candidates = [
                edge for edge, cap in edge_capacity.items()
                if edge[0] == src and edge[1] != CLOSED_SITE and cap - edge_base.get(edge, 0) > 0
            ]
        else:
            candidates = [
                edge for edge, cap in edge_capacity.items()
                if edge[1] == dst and edge[0] != CLOSED_SITE and cap - edge_base.get(edge, 0) > 0
            ]

        for edge in candidates:
            alloc_pairs.append((ridx, edge))

    return demand_rows, alloc_pairs


# ============================================================
# 4. 建立 MILP
# ============================================================

def build_problem(
    name: str,
    demand_rows: list[dict],
    alloc_pairs: list[tuple[int, tuple[str, str]]],
    edge_base: dict[tuple[str, str], int],
    edge_capacity: dict[tuple[str, str], int],
    site_base_load: dict[str, int],
    site_capacity: dict[str, int],
    objective: str,
    fixed_unserved: int | None = None,
    changed_limit: int | None = None,
) -> tuple[pulp.LpProblem, dict, dict, dict, pulp.LpVariable]:
    prob = pulp.LpProblem(name, pulp.LpMinimize)

    demand_ids = [row["需求编号"] for row in demand_rows]
    demand_amount = {row["需求编号"]: int(row["需求量"]) for row in demand_rows}
    candidate_edges = sorted(set(edge for _, edge in alloc_pairs))

    pairs_by_demand = {rid: [] for rid in demand_ids}
    pairs_by_edge = {edge: [] for edge in candidate_edges}
    for rid, edge in alloc_pairs:
        pairs_by_demand[rid].append(edge)
        pairs_by_edge[edge].append(rid)

    x = {
        (rid, edge): pulp.LpVariable(f"x_{rid}_{edge[0]}_{edge[1]}", lowBound=0, cat="Integer")
        for rid, edge in alloc_pairs
    }
    u = {
        rid: pulp.LpVariable(f"u_{rid}", lowBound=0, cat="Integer")
        for rid in demand_ids
    }
    y = {
        edge: pulp.LpVariable(f"y_{edge[0]}_{edge[1]}", cat="Binary")
        for edge in candidate_edges
    }
    max_load = pulp.LpVariable("max_line_load_rate", lowBound=0)

    for rid in demand_ids:
        prob += (
            pulp.lpSum(x[(rid, edge)] for edge in pairs_by_demand[rid]) + u[rid] == demand_amount[rid],
            f"demand_balance_{rid}",
        )

    # 候选分流线路：容量、变化线路指示变量、全网最大负荷率。
    for edge in candidate_edges:
        added = pulp.lpSum(x[(rid, edge)] for rid in pairs_by_edge[edge])
        base_volume = edge_base.get(edge, 0)
        cap = edge_capacity[edge]
        spare = max(cap - base_volume, 0)
        prob += base_volume + added <= cap, f"edge_capacity_{edge[0]}_{edge[1]}"
        prob += added <= spare * y[edge], f"change_link_{edge[0]}_{edge[1]}"
        prob += base_volume + added <= cap * max_load, f"candidate_load_{edge[0]}_{edge[1]}"

    # 非候选线路也纳入最大负荷率，保证 L 是整个非 DC5 网络的最大线路负荷率。
    candidate_edge_set = set(candidate_edges)
    for edge, base_volume in edge_base.items():
        if edge not in candidate_edge_set:
            cap = edge_capacity.get(edge, 0)
            if cap > 0:
                prob += base_volume <= cap * max_load, f"base_load_{edge[0]}_{edge[1]}"

    # 场地处理能力约束。
    for site, cap in site_capacity.items():
        added_terms = [
            x[(rid, edge)]
            for rid, edge in alloc_pairs
            if edge[0] == site or edge[1] == site
        ]
        prob += site_base_load.get(site, 0) + pulp.lpSum(added_terms) <= cap, f"site_capacity_{site}"

    total_unserved = pulp.lpSum(u.values())
    changed_count = pulp.lpSum(y.values())

    if fixed_unserved is not None:
        prob += total_unserved <= fixed_unserved, "fixed_min_unserved"
    if changed_limit is not None:
        prob += changed_count <= changed_limit, "changed_limit"

    if objective == "unserved":
        prob += total_unserved
    elif objective == "changed":
        prob += changed_count
    elif objective == "load":
        prob += max_load
    else:
        raise ValueError(objective)

    return prob, x, u, y, max_load


# ============================================================
# 5. 单日三层求解与折中方案
# ============================================================

def solve_one_day(
    date: pd.Timestamp,
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], list[dict]]:
    _, affected, edge_base, edge_capacity, site_base_load, site_capacity = prepare_day(day_pred, edge_cap, site_cap)
    demand_rows, alloc_pairs = build_demands_and_candidates(affected, edge_base, edge_capacity)

    date_text = date.strftime("%Y%m%d")
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=SOLVER_TIME_LIMIT)

    prob1, _, u1, _, _ = build_problem(
        f"dc5_{date_text}_stage1_unserved",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="unserved",
    )
    status1 = prob1.solve(solver)
    min_unserved = int(round(sum(pulp.value(v) or 0 for v in u1.values())))

    prob2, _, _, y2, _ = build_problem(
        f"dc5_{date_text}_stage2_changed",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="changed",
        fixed_unserved=min_unserved,
    )
    status2 = prob2.solve(solver)
    min_changed = int(round(sum(pulp.value(v) or 0 for v in y2.values())))

    allocation_outputs: list[pd.DataFrame] = []
    adjusted_outputs: list[pd.DataFrame] = []
    metrics_outputs: list[dict] = []

    for allowance in ALLOWANCES:
        changed_limit = min_changed + allowance
        scheme = f"min_changed_plus_{allowance}"

        prob3, x3, u3, y3, l3 = build_problem(
            f"dc5_{date_text}_stage3_load_{allowance}",
            demand_rows,
            alloc_pairs,
            edge_base,
            edge_capacity,
            site_base_load,
            site_capacity,
            objective="load",
            fixed_unserved=min_unserved,
            changed_limit=changed_limit,
        )
        status3 = prob3.solve(solver)

        added_by_edge: dict[tuple[str, str], int] = {}
        allocation_records = []
        for (rid, edge), var in x3.items():
            volume = int(round(pulp.value(var) or 0))
            if volume > 0:
                demand = demand_rows[rid]
                added_by_edge[edge] = added_by_edge.get(edge, 0) + volume
                allocation_records.append(
                    {
                        "方案": scheme,
                        "日期": date,
                        "原线路": demand["原线路"],
                        "需求类型": demand["需求类型"],
                        "替代场地1": edge[0],
                        "替代场地2": edge[1],
                        "替代线路": f"{edge[0]}->{edge[1]}",
                        "分流货量": volume,
                    }
                )

        unserved_records = []
        for rid, var in u3.items():
            volume = int(round(pulp.value(var) or 0))
            if volume > 0:
                demand = demand_rows[rid]
                unserved_records.append(
                    {
                        "方案": scheme,
                        "日期": date,
                        "原线路": demand["原线路"],
                        "需求类型": demand["需求类型"],
                        "未正常流转货量": volume,
                    }
                )

        allocation_df = pd.DataFrame(allocation_records)
        if unserved_records:
            allocation_df = pd.concat([allocation_df, pd.DataFrame(unserved_records)], ignore_index=True, sort=False)

        adjusted_records = []
        for edge, base_volume in edge_base.items():
            cap = edge_capacity[edge]
            added = added_by_edge.get(edge, 0)
            adjusted = base_volume + added
            adjusted_records.append(
                {
                    "方案": scheme,
                    "场地1": edge[0],
                    "场地2": edge[1],
                    "edge": f"{edge[0]}->{edge[1]}",
                    "日期": date,
                    "原预测货量": base_volume,
                    "分流增加货量": added,
                    "调整后货量": adjusted,
                    "线路能力": cap,
                    "线路负荷率": adjusted / cap if cap > 0 else 0.0,
                }
            )
        adjusted_df = pd.DataFrame(adjusted_records)

        changed_edges = int((adjusted_df["分流增加货量"] > 0).sum())
        unserved_total = int(round(sum(pulp.value(v) or 0 for v in u3.values())))
        max_line_load = float(adjusted_df["线路负荷率"].max())
        positive_load = adjusted_df[adjusted_df["线路能力"] > 0]["线路负荷率"]

        metrics_outputs.append(
            {
                "方案": scheme,
                "日期": date,
                "第一阶段状态": pulp.LpStatus[status1],
                "第二阶段状态": pulp.LpStatus[status2],
                "第三阶段状态": pulp.LpStatus[status3],
                "变化线路放宽量": allowance,
                "最小未正常流转货量": min_unserved,
                "最小变化线路数": min_changed,
                "允许变化线路数": changed_limit,
                "实际变化线路数": changed_edges,
                "受影响货量": int(affected["预测货量"].sum()),
                "未正常流转货量": unserved_total,
                "最大线路负荷率": max_line_load,
                "模型最大线路负荷率": float(pulp.value(l3) or 0),
                "平均线路负荷率": float(positive_load.mean()),
                "负荷率标准差": float(positive_load.std(ddof=0)),
                "候选分流线路数": len(set(edge for _, edge in alloc_pairs)),
                "DC5相关线路数": int(affected[["场地1", "场地2"]].drop_duplicates().shape[0]),
            }
        )

        allocation_outputs.append(allocation_df)
        adjusted_outputs.append(adjusted_df)

    return allocation_outputs, adjusted_outputs, metrics_outputs


# ============================================================
# 6. 主程序
# ============================================================

def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    history, pred = load_inputs()
    edge_cap, site_cap = build_capacities(history)

    all_allocations: list[pd.DataFrame] = []
    all_adjusted: list[pd.DataFrame] = []
    all_metrics: list[dict] = []

    for date, day_pred in pred.groupby("日期", sort=True):
        print(f"求解 {date.date()} ...", flush=True)
        allocations, adjusted, metrics = solve_one_day(date, day_pred.copy(), edge_cap, site_cap)
        all_allocations.extend(allocations)
        all_adjusted.extend(adjusted)
        all_metrics.extend(metrics)
        for row in metrics:
            print(
                f"  {row['方案']}: 未流转={row['未正常流转货量']}, "
                f"变化线路={row['实际变化线路数']}, 最大负荷率={row['最大线路负荷率']:.4f}",
                flush=True,
            )

    allocation_df = pd.concat(all_allocations, ignore_index=True, sort=False)
    adjusted_df = pd.concat(all_adjusted, ignore_index=True, sort=False)
    metrics_df = pd.DataFrame(all_metrics)

    allocation_df.to_csv(RESULT_DIR / "problem2_dc5_integer_tradeoff_allocation_detail.csv", index=False, encoding="utf-8-sig")
    adjusted_df.to_csv(RESULT_DIR / "problem2_dc5_integer_tradeoff_adjusted_line_volume.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(RESULT_DIR / "problem2_dc5_integer_tradeoff_daily_metrics.csv", index=False, encoding="utf-8-sig")

    summary = (
        metrics_df.groupby("方案", as_index=False)
        .agg(
            日期数=("日期", "nunique"),
            受影响总货量=("受影响货量", "sum"),
            未正常流转总货量=("未正常流转货量", "sum"),
            平均每日变化线路数=("实际变化线路数", "mean"),
            最大每日变化线路数=("实际变化线路数", "max"),
            最大线路负荷率=("最大线路负荷率", "max"),
            平均线路负荷率=("平均线路负荷率", "mean"),
            平均负荷率标准差=("负荷率标准差", "mean"),
        )
        .sort_values("方案")
    )
    summary.to_csv(RESULT_DIR / "problem2_dc5_integer_tradeoff_summary.csv", index=False, encoding="utf-8-sig")

    print("\n优化版问题二汇总：")
    print(summary.round(6).to_string(index=False))
    print(f"\n输出目录：{RESULT_DIR}")


if __name__ == "__main__":
    main()


# ============================================================
# Part 2: problem2_visualize_123.py
# Source: 问题2_优化版\code\problem2_visualize_123.py
# ============================================================

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd


# ============================================================
# 1. 路径与画图基础设置
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
RESULT_DIR = BASE_DIR / "问题2_优化版" / "results"
FIGURE_DIR = BASE_DIR / "问题2_优化版" / "figures"

DAILY_METRICS_PATH = RESULT_DIR / "problem2_dc5_integer_tradeoff_daily_metrics.csv"

SCHEME_LABELS = {
    "min_changed_plus_0": "最少变化(+0)",
    "min_changed_plus_2": "放宽2条(+2)",
    "min_changed_plus_5": "放宽5条(+5)",
}

SCHEME_COLORS = {
    "min_changed_plus_0": "#d55e00",
    "min_changed_plus_2": "#0072b2",
    "min_changed_plus_5": "#009e73",
}


matplotlib.use("Agg")


def setup_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120


def load_metrics() -> pd.DataFrame:
    df = pd.read_csv(DAILY_METRICS_PATH)
    df["日期"] = pd.to_datetime(df["日期"], format="mixed")
    df["方案名称"] = df["方案"].map(SCHEME_LABELS)
    df["是否异常"] = (
        (df["第一阶段状态"] != "Optimal")
        | (df["第二阶段状态"] != "Optimal")
        | (df["第三阶段状态"] != "Optimal")
        | (df["实际变化线路数"] > df["允许变化线路数"])
    )
    return df


# ============================================================
# 2. 可视化 1：三方案总体指标对比
# ============================================================

def plot_scheme_summary(df: pd.DataFrame) -> None:
    summary = (
        df.groupby("方案", as_index=False)
        .agg(
            平均变化线路数=("实际变化线路数", "mean"),
            最大变化线路数=("实际变化线路数", "max"),
            最大线路负荷率=("最大线路负荷率", "max"),
            平均线路负荷率=("平均线路负荷率", "mean"),
            异常天数=("是否异常", "sum"),
        )
        .sort_values("方案")
    )
    summary["方案名称"] = summary["方案"].map(SCHEME_LABELS)

    metrics = [
        ("平均变化线路数", "平均变化线路数"),
        ("最大变化线路数", "最大变化线路数"),
        ("最大线路负荷率", "最大线路负荷率"),
        ("平均线路负荷率", "平均线路负荷率"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes = axes.ravel()

    colors = [SCHEME_COLORS[s] for s in summary["方案"]]
    for ax, (col, title) in zip(axes, metrics):
        bars = ax.bar(summary["方案名称"], summary[col], color=colors, width=0.58)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=0)

        for bar, value in zip(bars, summary[col]):
            label = f"{value:.3f}" if "负荷率" in col else f"{value:.2f}"
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), label, ha="center", va="bottom", fontsize=9)

    abnormal = summary[summary["异常天数"] > 0]
    if not abnormal.empty:
        fig.text(
            0.5,
            0.01,
            "注：最少变化(+0) 方案存在 1 天第三阶段未正常求解，正式推荐采用放宽2条(+2)方案。",
            ha="center",
            fontsize=10,
            color="#8a4b08",
        )

    fig.suptitle("问题二 DC5 关停后三种分流方案指标对比", fontsize=15)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIGURE_DIR / "problem2_scheme_summary_compare.png", dpi=220)
    plt.close(fig)


# ============================================================
# 3. 可视化 2：每日变化线路数折线图
# ============================================================

def plot_daily_changed_lines(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))

    for scheme, group in df.groupby("方案", sort=True):
        group = group.sort_values("日期")
        ax.plot(
            group["日期"],
            group["实际变化线路数"],
            marker="o",
            linewidth=2,
            markersize=4,
            color=SCHEME_COLORS[scheme],
            label=SCHEME_LABELS[scheme],
        )

    abnormal = df[df["是否异常"]]
    if not abnormal.empty:
        ax.scatter(
            abnormal["日期"],
            abnormal["实际变化线路数"],
            s=90,
            facecolors="none",
            edgecolors="#b00020",
            linewidths=2,
            label="异常点",
            zorder=5,
        )

    ax.set_title("问题二三种方案每日变化线路数")
    ax.set_xlabel("日期")
    ax.set_ylabel("变化线路数")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=9)
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "problem2_daily_changed_lines.png", dpi=220)
    plt.close(fig)


# ============================================================
# 4. 可视化 3：每日最大线路负荷率折线图
# ============================================================

def plot_daily_max_load(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))

    for scheme, group in df.groupby("方案", sort=True):
        group = group.sort_values("日期")
        ax.plot(
            group["日期"],
            group["最大线路负荷率"],
            marker="o",
            linewidth=2,
            markersize=4,
            color=SCHEME_COLORS[scheme],
            label=SCHEME_LABELS[scheme],
        )

    abnormal = df[df["是否异常"]]
    if not abnormal.empty:
        ax.scatter(
            abnormal["日期"],
            abnormal["最大线路负荷率"],
            s=90,
            facecolors="none",
            edgecolors="#b00020",
            linewidths=2,
            label="异常点",
            zorder=5,
        )

    ax.set_title("问题二三种方案每日最大线路负荷率")
    ax.set_xlabel("日期")
    ax.set_ylabel("最大线路负荷率")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=9)
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "problem2_daily_max_load_rate.png", dpi=220)
    plt.close(fig)


# ============================================================
# 5. 主流程
# ============================================================

def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    metrics = load_metrics()
    plot_scheme_summary(metrics)
    plot_daily_changed_lines(metrics)
    plot_daily_max_load(metrics)

    print(f"可视化图片已输出到：{FIGURE_DIR}")


if __name__ == "__main__":
    main()
