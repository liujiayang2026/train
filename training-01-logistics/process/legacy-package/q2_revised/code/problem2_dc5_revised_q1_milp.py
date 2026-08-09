from __future__ import annotations

from pathlib import Path

import pandas as pd
import pulp


# ============================================================
# 1. Paths and parameters
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "paper_skill_materials" / "raw_data" / "history_volume_data.xlsx"
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
RESULT_DIR = BASE_DIR / "q2_revised" / "results"

CLOSED_SITE = "DC5"
ALLOWANCE = 2
SOLVER_TIME_LIMIT = 120
EPS = 1e-6


# ============================================================
# 2. Data and capacities
# ============================================================

def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    history = pd.read_excel(DATA_PATH)
    history = history.rename(
        columns={
            history.columns[0]: "origin",
            history.columns[1]: "dest",
            history.columns[2]: "date",
            history.columns[3]: "volume",
        }
    )
    history["date"] = pd.to_datetime(history["date"])
    history["origin"] = history["origin"].astype(str)
    history["dest"] = history["dest"].astype(str)
    history["volume"] = history["volume"].astype(float)
    history["edge"] = history["origin"] + "->" + history["dest"]

    pred = pd.read_csv(PRED_PATH)
    pred["date"] = pd.to_datetime(pred["date"])
    pred["origin"] = pred["origin"].astype(str)
    pred["dest"] = pred["dest"].astype(str)
    pred["forecast_volume"] = pred["forecast_volume"].round().astype(int)
    pred["edge"] = pred["origin"] + "->" + pred["dest"]
    return history, pred[["origin", "dest", "edge", "date", "forecast_volume"]]


def build_capacities(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edge_cap = (
        history.groupby(["origin", "dest"], as_index=False)["volume"]
        .max()
        .rename(columns={"volume": "edge_capacity"})
    )

    out_daily = history.groupby(["date", "origin"])["volume"].sum().rename("out")
    in_daily = history.groupby(["date", "dest"])["volume"].sum().rename("in")
    site_daily = pd.concat([out_daily, in_daily], axis=1).fillna(0).reset_index()
    site_daily = site_daily.rename(columns={"level_1": "site"})
    site_daily["site_load"] = site_daily["out"] + site_daily["in"]
    site_cap = (
        site_daily.groupby("site", as_index=False)["site_load"]
        .max()
        .rename(columns={"site_load": "site_capacity"})
    )
    return edge_cap, site_cap


def baseline_capacity_anomalies(pred: pd.DataFrame, edge_cap: pd.DataFrame, site_cap: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    edge_check = pred.merge(edge_cap, on=["origin", "dest"], how="left")
    edge_over = edge_check[edge_check["forecast_volume"] > edge_check["edge_capacity"]].copy()
    edge_over["over_amount"] = edge_over["forecast_volume"] - edge_over["edge_capacity"]
    edge_over["load_rate"] = edge_over["forecast_volume"] / edge_over["edge_capacity"]

    site_rows = pd.concat(
        [
            pred[["date", "origin", "forecast_volume"]].rename(columns={"origin": "site"}),
            pred[["date", "dest", "forecast_volume"]].rename(columns={"dest": "site"}),
        ],
        ignore_index=True,
    )
    site_load = site_rows.groupby(["date", "site"], as_index=False)["forecast_volume"].sum()
    site_check = site_load.merge(site_cap, on="site", how="left")
    site_over = site_check[site_check["forecast_volume"] > site_check["site_capacity"]].copy()
    site_over["over_amount"] = site_over["forecast_volume"] - site_over["site_capacity"]
    site_over["load_rate"] = site_over["forecast_volume"] / site_over["site_capacity"]
    return edge_over, site_over


# ============================================================
# 3. Daily data preparation
# ============================================================

def prepare_day(
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[str, str], int], dict[tuple[str, str], int], dict[str, int], dict[str, int]]:
    day = day_pred.merge(edge_cap, on=["origin", "dest"], how="left")
    day["edge_capacity"] = day["edge_capacity"].fillna(0).round().astype(int)
    day["forecast_volume"] = day["forecast_volume"].round().astype(int)

    affected = day[((day["origin"] == CLOSED_SITE) | (day["dest"] == CLOSED_SITE)) & (day["forecast_volume"] > 0)].copy()
    base = day[(day["origin"] != CLOSED_SITE) & (day["dest"] != CLOSED_SITE)].copy()

    edge_base = {
        (row["origin"], row["dest"]): int(row["forecast_volume"])
        for _, row in base.iterrows()
    }
    edge_capacity = {
        (row["origin"], row["dest"]): int(row["edge_capacity"])
        for _, row in base.iterrows()
    }
    site_capacity = {
        row["site"]: int(round(row["site_capacity"]))
        for _, row in site_cap[site_cap["site"] != CLOSED_SITE].iterrows()
    }

    site_base_load: dict[str, int] = {}
    for _, row in base.iterrows():
        src, dst, volume = row["origin"], row["dest"], int(row["forecast_volume"])
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
        src, dst = row["origin"], row["dest"]
        demand = int(row["forecast_volume"])
        demand_type = "outbound_from_closed_site" if src == CLOSED_SITE else "inbound_to_closed_site"
        demand_rows.append(
            {
                "demand_id": ridx,
                "original_edge": f"{src}->{dst}",
                "origin": src,
                "dest": dst,
                "demand_type": demand_type,
                "demand_volume": demand,
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
# 4. MILP model
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

    demand_ids = [row["demand_id"] for row in demand_rows]
    demand_amount = {row["demand_id"]: int(row["demand_volume"]) for row in demand_rows}
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
    u = {rid: pulp.LpVariable(f"u_{rid}", lowBound=0, cat="Integer") for rid in demand_ids}
    y = {edge: pulp.LpVariable(f"y_{edge[0]}_{edge[1]}", cat="Binary") for edge in candidate_edges}
    max_load = pulp.LpVariable("max_line_load_rate", lowBound=0)

    for rid in demand_ids:
        prob += (
            pulp.lpSum(x[(rid, edge)] for edge in pairs_by_demand[rid]) + u[rid] == demand_amount[rid],
            f"demand_balance_{rid}",
        )

    for edge in candidate_edges:
        added = pulp.lpSum(x[(rid, edge)] for rid in pairs_by_edge[edge])
        base_volume = edge_base.get(edge, 0)
        cap = edge_capacity[edge]
        spare = max(cap - base_volume, 0)
        prob += added <= spare, f"edge_spare_{edge[0]}_{edge[1]}"
        prob += added <= spare * y[edge], f"change_indicator_{edge[0]}_{edge[1]}"
        if cap > 0:
            prob += base_volume + added <= cap * max_load, f"candidate_load_{edge[0]}_{edge[1]}"

    candidate_edge_set = set(candidate_edges)
    for edge, base_volume in edge_base.items():
        if edge not in candidate_edge_set:
            cap = edge_capacity.get(edge, 0)
            if cap > 0:
                prob += base_volume <= cap * max_load, f"base_load_{edge[0]}_{edge[1]}"

    for site, cap in site_capacity.items():
        site_spare = max(cap - site_base_load.get(site, 0), 0)
        added_terms = [
            x[(rid, edge)]
            for rid, edge in alloc_pairs
            if edge[0] == site or edge[1] == site
        ]
        prob += pulp.lpSum(added_terms) <= site_spare, f"site_spare_{site}"

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
# 5. Daily three-stage solve
# ============================================================

def solve_one_day(
    date: pd.Timestamp,
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
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

    changed_limit = min_changed + ALLOWANCE
    prob3, x3, u3, y3, l3 = build_problem(
        f"dc5_{date_text}_stage3_load",
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
                    "scheme": f"min_changed_plus_{ALLOWANCE}",
                    "date": date,
                    "original_edge": demand["original_edge"],
                    "demand_type": demand["demand_type"],
                    "alternative_origin": edge[0],
                    "alternative_dest": edge[1],
                    "alternative_edge": f"{edge[0]}->{edge[1]}",
                    "allocated_volume": volume,
                    "unserved_volume": 0,
                }
            )

    for rid, var in u3.items():
        volume = int(round(pulp.value(var) or 0))
        if volume > 0:
            demand = demand_rows[rid]
            allocation_records.append(
                {
                    "scheme": f"min_changed_plus_{ALLOWANCE}",
                    "date": date,
                    "original_edge": demand["original_edge"],
                    "demand_type": demand["demand_type"],
                    "alternative_origin": "",
                    "alternative_dest": "",
                    "alternative_edge": "",
                    "allocated_volume": 0,
                    "unserved_volume": volume,
                }
            )

    adjusted_records = []
    for edge, base_volume in edge_base.items():
        cap = edge_capacity[edge]
        added = added_by_edge.get(edge, 0)
        adjusted = base_volume + added
        adjusted_records.append(
            {
                "scheme": f"min_changed_plus_{ALLOWANCE}",
                "origin": edge[0],
                "dest": edge[1],
                "edge": f"{edge[0]}->{edge[1]}",
                "date": date,
                "base_forecast_volume": base_volume,
                "added_volume": added,
                "adjusted_volume": adjusted,
                "edge_capacity": cap,
                "line_load_rate": adjusted / cap if cap > 0 else 0.0,
            }
        )

    allocation_df = pd.DataFrame(allocation_records)
    adjusted_df = pd.DataFrame(adjusted_records)
    changed_edges = int((adjusted_df["added_volume"] > 0).sum())
    unserved_total = int(round(sum(pulp.value(v) or 0 for v in u3.values())))
    positive_load = adjusted_df[adjusted_df["edge_capacity"] > 0]["line_load_rate"]

    metric = {
        "scheme": f"min_changed_plus_{ALLOWANCE}",
        "date": date,
        "stage1_status": pulp.LpStatus[status1],
        "stage2_status": pulp.LpStatus[status2],
        "stage3_status": pulp.LpStatus[status3],
        "changed_allowance": ALLOWANCE,
        "minimum_unserved_volume": min_unserved,
        "minimum_changed_lines": min_changed,
        "allowed_changed_lines": changed_limit,
        "actual_changed_lines": changed_edges,
        "affected_volume": int(affected["forecast_volume"].sum()),
        "unserved_volume": unserved_total,
        "max_line_load_rate": float(positive_load.max()) if len(positive_load) else 0.0,
        "model_max_line_load_rate": float(pulp.value(l3) or 0),
        "average_line_load_rate": float(positive_load.mean()) if len(positive_load) else 0.0,
        "line_load_std": float(positive_load.std(ddof=0)) if len(positive_load) else 0.0,
        "candidate_line_count": len(set(edge for _, edge in alloc_pairs)),
        "dc5_related_positive_line_count": int(affected[["origin", "dest"]].drop_duplicates().shape[0]),
    }
    return allocation_df, adjusted_df, metric


# ============================================================
# 6. Verification and exports
# ============================================================

def verify_dc5_allocation(pred: pd.DataFrame, allocation_df: pd.DataFrame) -> pd.DataFrame:
    affected = pred[((pred["origin"] == CLOSED_SITE) | (pred["dest"] == CLOSED_SITE)) & (pred["forecast_volume"] > 0)].copy()
    inbound_total = int(affected[affected["dest"] == CLOSED_SITE]["forecast_volume"].sum())
    outbound_total = int(affected[affected["origin"] == CLOSED_SITE]["forecast_volume"].sum())

    served = allocation_df[allocation_df["allocated_volume"] > 0].copy()
    unserved = allocation_df[allocation_df["unserved_volume"] > 0].copy()
    inbound_served = int(served[served["demand_type"] == "inbound_to_closed_site"]["allocated_volume"].sum())
    outbound_served = int(served[served["demand_type"] == "outbound_from_closed_site"]["allocated_volume"].sum())
    inbound_unserved = int(unserved[unserved["demand_type"] == "inbound_to_closed_site"]["unserved_volume"].sum())
    outbound_unserved = int(unserved[unserved["demand_type"] == "outbound_from_closed_site"]["unserved_volume"].sum())

    return pd.DataFrame(
        [
            {
                "closed_site": CLOSED_SITE,
                "inbound_total": inbound_total,
                "inbound_served": inbound_served,
                "inbound_unserved": inbound_unserved,
                "inbound_balance_error": inbound_total - inbound_served - inbound_unserved,
                "outbound_total": outbound_total,
                "outbound_served": outbound_served,
                "outbound_unserved": outbound_unserved,
                "outbound_balance_error": outbound_total - outbound_served - outbound_unserved,
            }
        ]
    )


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    history, pred = load_inputs()
    edge_cap, site_cap = build_capacities(history)
    edge_over, site_over = baseline_capacity_anomalies(pred, edge_cap, site_cap)
    edge_over.to_csv(RESULT_DIR / "baseline_edge_capacity_anomalies.csv", index=False, encoding="utf-8-sig")
    site_over.to_csv(RESULT_DIR / "baseline_site_capacity_anomalies.csv", index=False, encoding="utf-8-sig")

    all_allocations: list[pd.DataFrame] = []
    all_adjusted: list[pd.DataFrame] = []
    all_metrics: list[dict] = []

    for date, day_pred in pred.groupby("date", sort=True):
        print(f"Solve {date.date()} ...", flush=True)
        allocation_df, adjusted_df, metric = solve_one_day(date, day_pred.copy(), edge_cap, site_cap)
        all_allocations.append(allocation_df)
        all_adjusted.append(adjusted_df)
        all_metrics.append(metric)
        print(
            f"  unserved={metric['unserved_volume']}, changed={metric['actual_changed_lines']}, "
            f"max_load={metric['max_line_load_rate']:.4f}, status={metric['stage3_status']}",
            flush=True,
        )

    allocation_df = pd.concat(all_allocations, ignore_index=True, sort=False)
    adjusted_df = pd.concat(all_adjusted, ignore_index=True, sort=False)
    metrics_df = pd.DataFrame(all_metrics)
    verification_df = verify_dc5_allocation(pred, allocation_df)

    allocation_df.to_csv(RESULT_DIR / "problem2_revised_allocation_detail.csv", index=False, encoding="utf-8-sig")
    adjusted_df.to_csv(RESULT_DIR / "problem2_revised_adjusted_line_volume.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(RESULT_DIR / "problem2_revised_daily_metrics.csv", index=False, encoding="utf-8-sig")
    verification_df.to_csv(RESULT_DIR / "problem2_revised_dc5_allocation_verification.csv", index=False, encoding="utf-8-sig")

    summary = (
        metrics_df.groupby("scheme", as_index=False)
        .agg(
            day_count=("date", "nunique"),
            affected_total_volume=("affected_volume", "sum"),
            unserved_total_volume=("unserved_volume", "sum"),
            average_daily_changed_lines=("actual_changed_lines", "mean"),
            max_daily_changed_lines=("actual_changed_lines", "max"),
            max_line_load_rate=("max_line_load_rate", "max"),
            average_line_load_rate=("average_line_load_rate", "mean"),
            average_load_std=("line_load_std", "mean"),
            optimal_days=("stage3_status", lambda s: int((s == "Optimal").sum())),
        )
        .sort_values("scheme")
    )
    summary["baseline_edge_capacity_anomaly_rows"] = len(edge_over)
    summary["baseline_site_capacity_anomaly_rows"] = len(site_over)
    summary.to_csv(RESULT_DIR / "problem2_revised_summary.csv", index=False, encoding="utf-8-sig")

    print("\nSummary:")
    print(summary.round(6).to_string(index=False))
    print("\nDC5 allocation verification:")
    print(verification_df.to_string(index=False))
    print(f"\nOutput directory: {RESULT_DIR}")


if __name__ == "__main__":
    main()
