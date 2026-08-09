from __future__ import annotations

from pathlib import Path

import pandas as pd
import pulp


# ============================================================
# 1. 基本路径与参数
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "原始资料" / "附件1：物流网络历史货量数据.xlsx"
PRED_PATH = BASE_DIR / "问题1" / "results" / "final" / "problem1_final_2023_01_forecast_all_edges.csv"

PROBLEM2_DIR = BASE_DIR / "问题2"
RESULT_DIR = PROBLEM2_DIR / "results"

CLOSED_SITE = "DC5"
SOLVER_TIME_LIMIT = 120
EPS = 1e-6


# ============================================================
# 2. 数据读取与能力上限计算
# ============================================================

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """读取历史货量和问题一最终预测结果。"""
    history = pd.read_excel(DATA_PATH)
    pred = pd.read_csv(PRED_PATH)
    history["日期"] = pd.to_datetime(history["日期"])
    pred["日期"] = pd.to_datetime(pred["日期"])
    return history, pred


def build_capacities(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """线路能力为历史日最大货量，场地能力为历史每日进出总处理量最大值。"""
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
# 3. 每日候选分流网络构造
# ============================================================

def prepare_day_data(
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], float], dict[str, float]]:
    """合并能力上限，分离 DC5 受影响线路和关停后的基础网络。"""
    day = day_pred.merge(edge_cap, on=["场地1", "场地2"], how="left")
    day["线路能力"] = day["线路能力"].fillna(0)

    affected = day[((day["场地1"] == CLOSED_SITE) | (day["场地2"] == CLOSED_SITE)) & (day["预测货量"] > 0)].copy()
    base = day[(day["场地1"] != CLOSED_SITE) & (day["场地2"] != CLOSED_SITE)].copy()

    base_edge = {
        (row["场地1"], row["场地2"]): float(row["预测货量"])
        for _, row in base.iterrows()
    }
    site_capacity = {
        row["场地"]: float(row["场地能力"])
        for _, row in site_cap[site_cap["场地"] != CLOSED_SITE].iterrows()
    }
    return day, affected, base_edge, site_capacity


def base_site_load(base: pd.DataFrame) -> dict[str, float]:
    """计算关停 DC5 后，不含 DC5 线路的基础场地处理量。"""
    loads: dict[str, float] = {}
    for _, row in base.iterrows():
        src, dst, volume = row["场地1"], row["场地2"], float(row["预测货量"])
        loads[src] = loads.get(src, 0.0) + volume
        loads[dst] = loads.get(dst, 0.0) + volume
    return loads


def build_candidate_pairs(
    affected: pd.DataFrame,
    base: pd.DataFrame,
) -> tuple[list[dict], list[tuple[int, tuple[str, str]]], dict[tuple[str, str], float]]:
    """
    为每一条 DC5 相关线路构造替代线路。
    i->DC5 的货量分配到已有 i->k；DC5->j 的货量分配到已有 k->j。
    """
    edge_capacity = {
        (row["场地1"], row["场地2"]): float(row["线路能力"])
        for _, row in base.iterrows()
    }
    edge_base = {
        (row["场地1"], row["场地2"]): float(row["预测货量"])
        for _, row in base.iterrows()
    }

    demand_rows: list[dict] = []
    alloc_pairs: list[tuple[int, tuple[str, str]]] = []

    for ridx, (_, row) in enumerate(affected.iterrows()):
        src, dst = row["场地1"], row["场地2"]
        demand = float(row["预测货量"])
        demand_rows.append({"需求编号": ridx, "原线路": f"{src}->{dst}", "起点": src, "终点": dst, "需求量": demand})

        if dst == CLOSED_SITE:
            candidates = [
                edge for edge in edge_capacity
                if edge[0] == src and edge[1] != CLOSED_SITE and edge_capacity[edge] - edge_base.get(edge, 0.0) > EPS
            ]
        else:
            candidates = [
                edge for edge in edge_capacity
                if edge[1] == dst and edge[0] != CLOSED_SITE and edge_capacity[edge] - edge_base.get(edge, 0.0) > EPS
            ]

        for edge in candidates:
            alloc_pairs.append((ridx, edge))

    return demand_rows, alloc_pairs, edge_capacity


# ============================================================
# 4. PuLP 分层 MILP 求解
# ============================================================

def build_problem(
    date_text: str,
    demand_rows: list[dict],
    alloc_pairs: list[tuple[int, tuple[str, str]]],
    edge_capacity: dict[tuple[str, str], float],
    edge_base: dict[tuple[str, str], float],
    site_capacity: dict[str, float],
    site_base_load: dict[str, float],
    fixed_unserved: float | None = None,
    fixed_changed_count: int | None = None,
    objective: str = "unserved",
) -> tuple[pulp.LpProblem, dict, dict, dict, pulp.LpVariable]:
    """建立某一天的 MILP。objective 可取 unserved、changed、load。"""
    prob = pulp.LpProblem(f"problem2_dc5_{date_text}_{objective}", pulp.LpMinimize)

    demand_ids = [row["需求编号"] for row in demand_rows]
    demand_amount = {row["需求编号"]: float(row["需求量"]) for row in demand_rows}
    candidate_edges = sorted(set(edge for _, edge in alloc_pairs))
    pairs_by_demand: dict[int, list[tuple[str, str]]] = {rid: [] for rid in demand_ids}
    pairs_by_edge: dict[tuple[str, str], list[int]] = {edge: [] for edge in candidate_edges}

    for rid, edge in alloc_pairs:
        pairs_by_demand[rid].append(edge)
        pairs_by_edge[edge].append(rid)

    x = {
        (rid, edge): pulp.LpVariable(f"x_{rid}_{edge[0]}_{edge[1]}", lowBound=0)
        for rid, edge in alloc_pairs
    }
    u = {
        rid: pulp.LpVariable(f"u_{rid}", lowBound=0)
        for rid in demand_ids
    }
    y = {
        edge: pulp.LpVariable(f"y_{edge[0]}_{edge[1]}", cat="Binary")
        for edge in candidate_edges
    }
    max_load = pulp.LpVariable("max_load_rate", lowBound=0)

    # 每条受影响线路的货量：要么被分流，要么计入未正常流转。
    for rid in demand_ids:
        prob += (
            pulp.lpSum(x[(rid, edge)] for edge in pairs_by_demand[rid]) + u[rid] == demand_amount[rid],
            f"demand_balance_{rid}",
        )

    # 线路容量、是否变化变量、最大负荷率约束。
    for edge in candidate_edges:
        added = pulp.lpSum(x[(rid, edge)] for rid in pairs_by_edge[edge])
        base_volume = edge_base.get(edge, 0.0)
        cap = edge_capacity[edge]
        prob += base_volume + added <= cap, f"edge_capacity_{edge[0]}_{edge[1]}"
        prob += added <= max(cap - base_volume, 0.0) * y[edge], f"edge_change_link_{edge[0]}_{edge[1]}"
        prob += base_volume + added <= cap * max_load, f"edge_load_rate_{edge[0]}_{edge[1]}"

    # 场地处理能力约束：线路上新增货量会同时增加起点和终点处理量。
    for site, cap in site_capacity.items():
        added_terms = []
        for rid, edge in alloc_pairs:
            if edge[0] == site or edge[1] == site:
                added_terms.append(x[(rid, edge)])
        prob += site_base_load.get(site, 0.0) + pulp.lpSum(added_terms) <= cap, f"site_capacity_{site}"

    total_unserved = pulp.lpSum(u.values())
    changed_count = pulp.lpSum(y.values())

    if fixed_unserved is not None:
        prob += total_unserved <= fixed_unserved + 1e-4, "fixed_unserved"
    if fixed_changed_count is not None:
        prob += changed_count <= fixed_changed_count, "fixed_changed_count"

    if objective == "unserved":
        prob += total_unserved
    elif objective == "changed":
        prob += changed_count
    elif objective == "load":
        prob += max_load
    else:
        raise ValueError(f"unknown objective: {objective}")

    return prob, x, u, y, max_load


def solve_one_day(
    date: pd.Timestamp,
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """对单日依次求解三层目标，并返回分流明细、调整后线路货量和指标。"""
    day, affected, _, site_capacity = prepare_day_data(day_pred, edge_cap, site_cap)
    base = day[(day["场地1"] != CLOSED_SITE) & (day["场地2"] != CLOSED_SITE)].copy()
    site_load = base_site_load(base)

    demand_rows, alloc_pairs, edge_capacity = build_candidate_pairs(affected, base)
    edge_base = {
        (row["场地1"], row["场地2"]): float(row["预测货量"])
        for _, row in base.iterrows()
    }

    date_text = date.strftime("%Y%m%d")
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=SOLVER_TIME_LIMIT)

    # 第一层：最小化未正常流转货量。
    prob1, _, u1, _, _ = build_problem(
        date_text, demand_rows, alloc_pairs, edge_capacity, edge_base, site_capacity, site_load, objective="unserved"
    )
    status1 = prob1.solve(solver)
    best_unserved = float(sum(pulp.value(var) or 0.0 for var in u1.values()))

    # 第二层：固定最小未流转货量，最小化变化线路数。
    prob2, _, _, y2, _ = build_problem(
        date_text,
        demand_rows,
        alloc_pairs,
        edge_capacity,
        edge_base,
        site_capacity,
        site_load,
        fixed_unserved=best_unserved,
        objective="changed",
    )
    status2 = prob2.solve(solver)
    best_changed = int(round(sum(pulp.value(var) or 0.0 for var in y2.values())))

    # 第三层：固定前两层结果，最小化最大负荷率。
    prob3, x3, u3, y3, l3 = build_problem(
        date_text,
        demand_rows,
        alloc_pairs,
        edge_capacity,
        edge_base,
        site_capacity,
        site_load,
        fixed_unserved=best_unserved,
        fixed_changed_count=best_changed,
        objective="load",
    )
    status3 = prob3.solve(solver)

    allocation_records = []
    added_by_edge: dict[tuple[str, str], float] = {}
    for (rid, edge), var in x3.items():
        volume = float(pulp.value(var) or 0.0)
        if volume > 1e-4:
            original = demand_rows[rid]["原线路"]
            allocation_records.append(
                {
                    "日期": date,
                    "原线路": original,
                    "替代场地1": edge[0],
                    "替代场地2": edge[1],
                    "替代线路": f"{edge[0]}->{edge[1]}",
                    "分流货量": volume,
                }
            )
            added_by_edge[edge] = added_by_edge.get(edge, 0.0) + volume

    unserved_records = []
    for rid, var in u3.items():
        volume = float(pulp.value(var) or 0.0)
        if volume > 1e-4:
            unserved_records.append(
                {
                    "日期": date,
                    "原线路": demand_rows[rid]["原线路"],
                    "未正常流转货量": volume,
                }
            )

    adjusted = base[["场地1", "场地2", "edge", "日期", "预测货量", "线路能力"]].copy()
    adjusted["分流增加货量"] = adjusted[["场地1", "场地2"]].apply(
        lambda s: added_by_edge.get((s["场地1"], s["场地2"]), 0.0), axis=1
    )
    adjusted["调整后货量"] = adjusted["预测货量"] + adjusted["分流增加货量"]
    adjusted["线路负荷率"] = adjusted.apply(
        lambda row: row["调整后货量"] / row["线路能力"] if row["线路能力"] > 0 else 0.0,
        axis=1,
    )

    changed_edges = int((adjusted["分流增加货量"] > 1e-4).sum())
    total_unserved = float(sum(pulp.value(var) or 0.0 for var in u3.values()))
    affected_volume = float(affected["预测货量"].sum())
    max_load = float(pulp.value(l3) or adjusted["线路负荷率"].max())

    positive_load = adjusted[adjusted["线路能力"] > 0]["线路负荷率"]
    metrics = {
        "日期": date,
        "第一阶段状态": pulp.LpStatus[status1],
        "第二阶段状态": pulp.LpStatus[status2],
        "第三阶段状态": pulp.LpStatus[status3],
        "受影响货量": affected_volume,
        "未正常流转货量": total_unserved,
        "变化线路数": changed_edges,
        "最大线路负荷率": max_load,
        "平均线路负荷率": float(positive_load.mean()),
        "负荷率标准差": float(positive_load.std(ddof=0)),
        "候选分流线路数": len(set(edge for _, edge in alloc_pairs)),
        "DC5相关线路数": int(affected[["场地1", "场地2"]].drop_duplicates().shape[0]),
    }

    allocation_df = pd.DataFrame(allocation_records)
    unserved_df = pd.DataFrame(unserved_records)
    if not unserved_df.empty:
        allocation_df = pd.concat([allocation_df, unserved_df], ignore_index=True, sort=False)

    return allocation_df, adjusted, metrics


# ============================================================
# 5. 主流程：循环 31 天并导出结果
# ============================================================

def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    history, pred = load_inputs()
    edge_cap, site_cap = build_capacities(history)

    all_allocations = []
    all_adjusted = []
    daily_metrics = []

    for date, day_pred in pred.groupby("日期", sort=True):
        print(f"求解 {date.date()} ...", flush=True)
        allocation, adjusted, metrics = solve_one_day(date, day_pred.copy(), edge_cap, site_cap)
        all_allocations.append(allocation)
        all_adjusted.append(adjusted)
        daily_metrics.append(metrics)
        print(
            f"  未流转={metrics['未正常流转货量']:.0f}, "
            f"变化线路={metrics['变化线路数']}, "
            f"最大负荷率={metrics['最大线路负荷率']:.4f}",
            flush=True,
        )

    allocation_df = pd.concat(all_allocations, ignore_index=True, sort=False)
    adjusted_df = pd.concat(all_adjusted, ignore_index=True, sort=False)
    metrics_df = pd.DataFrame(daily_metrics)

    allocation_df.to_csv(RESULT_DIR / "problem2_dc5_allocation_detail.csv", index=False, encoding="utf-8-sig")
    adjusted_df.to_csv(RESULT_DIR / "problem2_dc5_adjusted_line_volume.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(RESULT_DIR / "problem2_dc5_daily_metrics.csv", index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "日期数": metrics_df["日期"].nunique(),
                "受影响总货量": metrics_df["受影响货量"].sum(),
                "未正常流转总货量": metrics_df["未正常流转货量"].sum(),
                "平均每日变化线路数": metrics_df["变化线路数"].mean(),
                "最大每日变化线路数": metrics_df["变化线路数"].max(),
                "最大线路负荷率": metrics_df["最大线路负荷率"].max(),
                "平均线路负荷率": metrics_df["平均线路负荷率"].mean(),
            }
        ]
    )
    summary.to_csv(RESULT_DIR / "problem2_dc5_summary.csv", index=False, encoding="utf-8-sig")

    print("\n问题二 DC5 关停分流汇总：")
    print(summary.round(6).to_string(index=False))
    print(f"\n输出目录：{RESULT_DIR}")


if __name__ == "__main__":
    main()
