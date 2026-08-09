# Integrated code for Problem 3. Run this file from the project root or any working directory.



# ============================================================
# Part A: MILP scheme used for dynamic line adjustment
# Source: q3_revised\code\problem3_dc9_dynamic_milp.py
# ============================================================

from pathlib import Path

import pandas as pd
import pulp


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "paper_skill_materials" / "raw_data" / "history_volume_data.xlsx"
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
RESULT_DIR = BASE_DIR / "q3_revised" / "results"
FIGURE_DIR = BASE_DIR / "q3_revised" / "figures"

CLOSED_SITE = "DC9"
ALLOWANCE = 2
SOLVER_TIME_LIMIT = 120
SCHEME_NAME = f"new_first_min_changed_plus_{ALLOWANCE}"
OUTPUT_PREFIX = "problem3_dc9_dynamic_new_first"


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

    pred = pd.read_csv(PRED_PATH)
    pred["date"] = pd.to_datetime(pred["date"])
    pred["origin"] = pred["origin"].astype(str)
    pred["dest"] = pred["dest"].astype(str)
    pred["forecast_volume"] = pred["forecast_volume"].round().astype(int)
    pred["edge"] = pred["origin"] + "->" + pred["dest"]
    return history, pred[["origin", "dest", "edge", "date", "forecast_volume"]]


def build_capacities(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, list[str]]:
    edge_cap = (
        history.groupby(["origin", "dest"], as_index=False)["volume"]
        .max()
        .rename(columns={"volume": "edge_capacity"})
    )
    edge_cap["edge_capacity"] = edge_cap["edge_capacity"].round().astype(int)
    max_existing_edge_capacity = int(edge_cap["edge_capacity"].max())

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
    site_cap["site_capacity"] = site_cap["site_capacity"].round().astype(int)

    sites = sorted(set(history["origin"]).union(history["dest"]))
    return edge_cap, site_cap, max_existing_edge_capacity, sites


def baseline_capacity_anomalies(
    pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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


def prepare_day(
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[tuple[str, str], int], dict[tuple[str, str], int], dict[str, int], dict[str, int]]:
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

    site_base_load: dict[str, int] = {site: 0 for site in site_capacity}
    for _, row in base.iterrows():
        src, dst, volume = row["origin"], row["dest"], int(row["forecast_volume"])
        site_base_load[src] = site_base_load.get(src, 0) + volume
        site_base_load[dst] = site_base_load.get(dst, 0) + volume

    return affected, edge_base, edge_capacity, site_base_load, site_capacity


def build_demands_and_candidates(
    affected: pd.DataFrame,
    edge_base: dict[tuple[str, str], int],
    existing_edge_capacity: dict[tuple[str, str], int],
    sites: list[str],
    new_edge_capacity: int,
) -> tuple[list[dict], list[tuple[int, tuple[str, str]]], dict[tuple[str, str], int], dict[tuple[str, str], bool]]:
    demand_rows: list[dict] = []
    alloc_pairs: list[tuple[int, tuple[str, str]]] = []
    candidate_capacity: dict[tuple[str, str], int] = {}
    is_new_edge: dict[tuple[str, str], bool] = {}

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
            candidates = [(src, site) for site in sites if site not in {CLOSED_SITE, src}]
        else:
            candidates = [(site, dst) for site in sites if site not in {CLOSED_SITE, dst}]

        for edge in candidates:
            if edge in existing_edge_capacity:
                capacity = existing_edge_capacity[edge]
                is_new = False
            else:
                capacity = new_edge_capacity
                is_new = True
            if capacity - edge_base.get(edge, 0) <= 0:
                continue
            candidate_capacity[edge] = capacity
            is_new_edge[edge] = is_new
            alloc_pairs.append((ridx, edge))

    return demand_rows, alloc_pairs, candidate_capacity, is_new_edge


def build_problem(
    name: str,
    demand_rows: list[dict],
    alloc_pairs: list[tuple[int, tuple[str, str]]],
    edge_base: dict[tuple[str, str], int],
    edge_capacity: dict[tuple[str, str], int],
    site_base_load: dict[str, int],
    site_capacity: dict[str, int],
    objective: str,
    is_new_edge: dict[tuple[str, str], bool],
    fixed_unserved: int | None = None,
    existing_changed_limit: int | None = None,
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
    existing_changed_count = pulp.lpSum(
        y[edge] for edge in candidate_edges if not is_new_edge.get(edge, False)
    )

    if fixed_unserved is not None:
        prob += total_unserved <= fixed_unserved, "fixed_min_unserved"
    if existing_changed_limit is not None:
        prob += existing_changed_count <= existing_changed_limit, "existing_changed_limit"
    if changed_limit is not None:
        prob += changed_count <= changed_limit, "changed_limit"

    if objective == "unserved":
        prob += total_unserved
    elif objective == "existing_changed":
        prob += existing_changed_count
    elif objective == "changed":
        prob += changed_count
    elif objective == "load":
        prob += max_load
    else:
        raise ValueError(objective)

    return prob, x, u, y, max_load


def solve_one_day(
    date: pd.Timestamp,
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
    sites: list[str],
    max_existing_edge_capacity: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    affected, edge_base, edge_capacity_existing, site_base_load, site_capacity = prepare_day(day_pred, edge_cap, site_cap)
    existing_edge_capacity = {
        (row["origin"], row["dest"]): int(row["edge_capacity"])
        for _, row in edge_cap.iterrows()
        if row["origin"] != CLOSED_SITE and row["dest"] != CLOSED_SITE
    }
    demand_rows, alloc_pairs, candidate_capacity, is_new_edge = build_demands_and_candidates(
        affected,
        edge_base,
        existing_edge_capacity,
        sites,
        max_existing_edge_capacity,
    )
    edge_capacity = {**edge_capacity_existing, **candidate_capacity}

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=SOLVER_TIME_LIMIT)
    date_text = date.strftime("%Y%m%d")

    prob1, _, u1, _, _ = build_problem(
        f"dc9_{date_text}_stage1_unserved",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="unserved",
        is_new_edge=is_new_edge,
    )
    status1 = prob1.solve(solver)
    min_unserved = int(round(sum(pulp.value(v) or 0 for v in u1.values())))

    prob2, _, _, y2, _ = build_problem(
        f"dc9_{date_text}_stage2_existing_changed",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="existing_changed",
        is_new_edge=is_new_edge,
        fixed_unserved=min_unserved,
    )
    status2 = prob2.solve(solver)
    min_existing_changed = int(
        round(sum((pulp.value(var) or 0) for edge, var in y2.items() if not is_new_edge.get(edge, False)))
    )

    prob3, _, _, y3, _ = build_problem(
        f"dc9_{date_text}_stage3_changed",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="changed",
        is_new_edge=is_new_edge,
        fixed_unserved=min_unserved,
        existing_changed_limit=min_existing_changed,
    )
    status3 = prob3.solve(solver)
    min_changed = int(round(sum(pulp.value(v) or 0 for v in y3.values())))

    changed_limit = min_changed + ALLOWANCE
    prob4, x4, u4, y4, l4 = build_problem(
        f"dc9_{date_text}_stage4_load",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="load",
        is_new_edge=is_new_edge,
        fixed_unserved=min_unserved,
        existing_changed_limit=min_existing_changed,
        changed_limit=changed_limit,
    )
    status4 = prob4.solve(solver)

    added_by_edge: dict[tuple[str, str], int] = {}
    allocation_records = []
    for (rid, edge), var in x4.items():
        volume = int(round(pulp.value(var) or 0))
        if volume <= 0:
            continue
        demand = demand_rows[rid]
        added_by_edge[edge] = added_by_edge.get(edge, 0) + volume
        allocation_records.append(
            {
                "scheme": SCHEME_NAME,
                "date": date,
                "original_edge": demand["original_edge"],
                "demand_type": demand["demand_type"],
                "alternative_origin": edge[0],
                "alternative_dest": edge[1],
                "alternative_edge": f"{edge[0]}->{edge[1]}",
                "is_new_opened_line": bool(is_new_edge.get(edge, False)),
                "allocated_volume": volume,
                "unserved_volume": 0,
            }
        )

    for rid, var in u4.items():
        volume = int(round(pulp.value(var) or 0))
        if volume <= 0:
            continue
        demand = demand_rows[rid]
        allocation_records.append(
            {
                "scheme": SCHEME_NAME,
                "date": date,
                "original_edge": demand["original_edge"],
                "demand_type": demand["demand_type"],
                "alternative_origin": "",
                "alternative_dest": "",
                "alternative_edge": "",
                "is_new_opened_line": False,
                "allocated_volume": 0,
                "unserved_volume": volume,
            }
        )

    adjusted_records = []
    all_edges = sorted(set(edge_base) | set(added_by_edge))
    for edge in all_edges:
        base_volume = edge_base.get(edge, 0)
        added = added_by_edge.get(edge, 0)
        cap = edge_capacity[edge]
        adjusted = base_volume + added
        adjusted_records.append(
            {
                "scheme": SCHEME_NAME,
                "origin": edge[0],
                "dest": edge[1],
                "edge": f"{edge[0]}->{edge[1]}",
                "date": date,
                "base_forecast_volume": base_volume,
                "added_volume": added,
                "adjusted_volume": adjusted,
                "edge_capacity": cap,
                "is_new_opened_line": bool(is_new_edge.get(edge, False)),
                "line_load_rate": adjusted / cap if cap > 0 else 0.0,
            }
        )

    closed_records = []
    for _, row in affected.iterrows():
        closed_records.append(
            {
                "scheme": SCHEME_NAME,
                "date": date,
                "change_type": "close_line",
                "edge": row["edge"],
                "origin": row["origin"],
                "dest": row["dest"],
                "volume_before": int(row["forecast_volume"]),
                "volume_after": 0,
                "capacity": int(row["edge_capacity"]),
                "is_new_opened_line": False,
            }
        )
    for edge, added in sorted(added_by_edge.items()):
        if not is_new_edge.get(edge, False):
            continue
        closed_records.append(
            {
                "scheme": SCHEME_NAME,
                "date": date,
                "change_type": "open_line",
                "edge": f"{edge[0]}->{edge[1]}",
                "origin": edge[0],
                "dest": edge[1],
                "volume_before": 0,
                "volume_after": added,
                "capacity": edge_capacity[edge],
                "is_new_opened_line": True,
            }
        )

    allocation_df = pd.DataFrame(allocation_records)
    adjusted_df = pd.DataFrame(adjusted_records)
    line_changes_df = pd.DataFrame(closed_records)

    positive_load = adjusted_df[adjusted_df["edge_capacity"] > 0]["line_load_rate"]
    changed_edges = int((adjusted_df["added_volume"] > 0).sum())
    new_opened = int(adjusted_df[(adjusted_df["added_volume"] > 0) & (adjusted_df["is_new_opened_line"])].shape[0])
    existing_changed = changed_edges - new_opened
    unserved_total = int(round(sum(pulp.value(v) or 0 for v in u4.values())))

    metric = {
        "scheme": SCHEME_NAME,
        "date": date,
        "stage1_status": pulp.LpStatus[status1],
        "stage2_status": pulp.LpStatus[status2],
        "stage3_status": pulp.LpStatus[status3],
        "stage4_status": pulp.LpStatus[status4],
        "changed_allowance": ALLOWANCE,
        "minimum_unserved_volume": min_unserved,
        "minimum_existing_changed_lines": min_existing_changed,
        "minimum_changed_lines": min_changed,
        "allowed_changed_lines": changed_limit,
        "actual_changed_lines": changed_edges,
        "existing_changed_lines": existing_changed,
        "new_opened_lines": new_opened,
        "closed_positive_lines": int(affected[["origin", "dest"]].drop_duplicates().shape[0]),
        "affected_volume": int(affected["forecast_volume"].sum()),
        "unserved_volume": unserved_total,
        "max_line_load_rate": float(positive_load.max()) if len(positive_load) else 0.0,
        "model_max_line_load_rate": float(pulp.value(l4) or 0),
        "average_line_load_rate": float(positive_load.mean()) if len(positive_load) else 0.0,
        "line_load_std": float(positive_load.std(ddof=0)) if len(positive_load) else 0.0,
        "candidate_line_count": len(set(edge for _, edge in alloc_pairs)),
        "new_candidate_line_count": int(sum(1 for edge in set(edge for _, edge in alloc_pairs) if is_new_edge.get(edge, False))),
        "affected_positive_line_count": int(affected[["origin", "dest"]].drop_duplicates().shape[0]),
    }
    return allocation_df, adjusted_df, line_changes_df, metric


def verify_allocation(pred: pd.DataFrame, allocation_df: pd.DataFrame) -> pd.DataFrame:
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


def build_post_shutdown_workload(adjusted_df: pd.DataFrame, line_changes_df: pd.DataFrame) -> pd.DataFrame:
    active = adjusted_df[
        [
            "scheme",
            "date",
            "origin",
            "dest",
            "edge",
            "base_forecast_volume",
            "adjusted_volume",
            "edge_capacity",
            "is_new_opened_line",
            "line_load_rate",
        ]
    ].copy()
    active["line_status_after_shutdown"] = active["is_new_opened_line"].map(
        {True: "new_opened", False: "active_existing"}
    )
    active = active.rename(
        columns={
            "base_forecast_volume": "volume_before_shutdown",
            "adjusted_volume": "volume_after_shutdown",
        }
    )

    closed = line_changes_df[line_changes_df["change_type"] == "close_line"][
        ["scheme", "date", "origin", "dest", "edge", "volume_before", "volume_after", "capacity"]
    ].copy()
    closed = closed.rename(
        columns={
            "volume_before": "volume_before_shutdown",
            "volume_after": "volume_after_shutdown",
            "capacity": "edge_capacity",
        }
    )
    closed["is_new_opened_line"] = False
    closed["line_load_rate"] = 0.0
    closed["line_status_after_shutdown"] = "closed_due_to_dc9"

    columns = [
        "scheme",
        "date",
        "origin",
        "dest",
        "edge",
        "line_status_after_shutdown",
        "volume_before_shutdown",
        "volume_after_shutdown",
        "edge_capacity",
        "line_load_rate",
        "is_new_opened_line",
    ]
    return pd.concat([active[columns], closed[columns]], ignore_index=True, sort=False)


def create_visualizations(metrics_df: pd.DataFrame, workload_df: pd.DataFrame, line_changes_df: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    metrics = metrics_df.copy()
    metrics["date"] = pd.to_datetime(metrics["date"])

    plt.style.use("default")

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(metrics["date"], metrics["affected_volume"], marker="o", label="affected volume", color="#1f77b4")
    ax1.plot(metrics["date"], metrics["unserved_volume"], marker="o", label="unserved volume", color="#d62728")
    ax1.set_ylabel("Volume")
    ax2 = ax1.twinx()
    ax2.plot(metrics["date"], metrics["new_opened_lines"], marker="s", label="new opened lines", color="#2ca02c")
    ax2.plot(metrics["date"], metrics["existing_changed_lines"], marker="s", label="existing changed lines", color="#ff7f0e")
    ax2.set_ylabel("Line count")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left", ncol=2)
    ax1.set_title("DC9 new-first daily allocation metrics")
    ax1.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_daily_metrics.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(metrics["date"], metrics["max_line_load_rate"], marker="o", color="#9467bd", label="max load rate")
    ax.plot(metrics["date"], metrics["average_line_load_rate"], marker="o", color="#8c564b", label="average load rate")
    ax.axhline(1.0, color="#d62728", linewidth=1, linestyle="--", label="capacity limit")
    ax.set_title("Post-shutdown line load rate by day")
    ax.set_ylabel("Load rate")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_daily_load_rate.png", dpi=180)
    plt.close(fig)

    active_load = workload_df[
        (workload_df["volume_after_shutdown"] > 0)
        & (workload_df["edge_capacity"] > 0)
        & (workload_df["line_status_after_shutdown"] != "closed_due_to_dc9")
    ]["line_load_rate"]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(active_load, bins=40, color="#4c78a8", edgecolor="white")
    ax.axvline(1.0, color="#d62728", linewidth=1, linestyle="--", label="capacity limit")
    ax.set_title("Post-shutdown active line load-rate distribution")
    ax.set_xlabel("Load rate")
    ax.set_ylabel("Line-day count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_load_rate_distribution.png", dpi=180)
    plt.close(fig)

    opened = line_changes_df[line_changes_df["change_type"] == "open_line"].copy()
    top_opened = opened.groupby("edge", as_index=False)["volume_after"].sum().sort_values("volume_after", ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_opened["edge"][::-1], top_opened["volume_after"][::-1], color="#59a14f")
    ax.set_title("Top opened lines by allocated volume")
    ax.set_xlabel("Allocated volume")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_top_opened_lines.png", dpi=180)
    plt.close(fig)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    history, pred = load_inputs()
    edge_cap, site_cap, max_existing_edge_capacity, sites = build_capacities(history)
    edge_over, site_over = baseline_capacity_anomalies(pred, edge_cap, site_cap)
    edge_over.to_csv(RESULT_DIR / "baseline_edge_capacity_anomalies.csv", index=False, encoding="utf-8-sig")
    site_over.to_csv(RESULT_DIR / "baseline_site_capacity_anomalies.csv", index=False, encoding="utf-8-sig")

    all_allocations: list[pd.DataFrame] = []
    all_adjusted: list[pd.DataFrame] = []
    all_line_changes: list[pd.DataFrame] = []
    all_metrics: list[dict] = []

    for date, day_pred in pred.groupby("date", sort=True):
        print(f"Solve {date.date()} ...", flush=True)
        allocation_df, adjusted_df, line_changes_df, metric = solve_one_day(
            date,
            day_pred.copy(),
            edge_cap,
            site_cap,
            sites,
            max_existing_edge_capacity,
        )
        all_allocations.append(allocation_df)
        all_adjusted.append(adjusted_df)
        all_line_changes.append(line_changes_df)
        all_metrics.append(metric)
        print(
            f"  unserved={metric['unserved_volume']}, changed={metric['actual_changed_lines']}, "
            f"new_opened={metric['new_opened_lines']}, max_load={metric['max_line_load_rate']:.4f}, "
            f"status={metric['stage4_status']}",
            flush=True,
        )

    allocation_df = pd.concat(all_allocations, ignore_index=True, sort=False)
    adjusted_df = pd.concat(all_adjusted, ignore_index=True, sort=False)
    line_changes_df = pd.concat(all_line_changes, ignore_index=True, sort=False)
    metrics_df = pd.DataFrame(all_metrics)
    workload_df = build_post_shutdown_workload(adjusted_df, line_changes_df)
    verification_df = verify_allocation(pred, allocation_df)
    create_visualizations(metrics_df, workload_df, line_changes_df)

    allocation_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_allocation_detail.csv", index=False, encoding="utf-8-sig")
    adjusted_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_adjusted_line_volume.csv", index=False, encoding="utf-8-sig")
    workload_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_post_shutdown_line_workload.csv", index=False, encoding="utf-8-sig")
    line_changes_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_daily_line_changes.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_daily_metrics.csv", index=False, encoding="utf-8-sig")
    verification_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_allocation_verification.csv", index=False, encoding="utf-8-sig")

    summary = (
        metrics_df.groupby("scheme", as_index=False)
        .agg(
            day_count=("date", "nunique"),
            affected_total_volume=("affected_volume", "sum"),
            unserved_total_volume=("unserved_volume", "sum"),
            average_daily_changed_lines=("actual_changed_lines", "mean"),
            max_daily_changed_lines=("actual_changed_lines", "max"),
            average_daily_new_opened_lines=("new_opened_lines", "mean"),
            max_daily_new_opened_lines=("new_opened_lines", "max"),
            average_daily_existing_changed_lines=("existing_changed_lines", "mean"),
            max_line_load_rate=("max_line_load_rate", "max"),
            average_line_load_rate=("average_line_load_rate", "mean"),
            average_load_std=("line_load_std", "mean"),
            optimal_days=("stage4_status", lambda s: int((s == "Optimal").sum())),
        )
        .sort_values("scheme")
    )
    summary["new_edge_capacity"] = max_existing_edge_capacity
    summary["baseline_edge_capacity_anomaly_rows"] = len(edge_over)
    summary["baseline_site_capacity_anomaly_rows"] = len(site_over)
    summary.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_summary.csv", index=False, encoding="utf-8-sig")

    print("\nSummary:")
    print(summary.round(6).to_string(index=False))
    print("\nAllocation verification:")
    print(verification_df.to_string(index=False))
    print(f"\nOutput directory: {RESULT_DIR}")


if __name__ == "__main__":
    main()



# ============================================================
# Part B: Pareto-style balance scan for new and existing lines
# Source: q3_revised\code\problem3_dc9_pareto_milp.py
# ============================================================

from pathlib import Path
import math

import pandas as pd
import pulp


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "paper_skill_materials" / "raw_data" / "history_volume_data.xlsx"
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
RESULT_DIR = BASE_DIR / "q3_revised" / "results"
FIGURE_DIR = BASE_DIR / "q3_revised" / "figures"

CLOSED_SITE = "DC9"
ALLOWANCE = 2
SOLVER_TIME_LIMIT = 60
OUTPUT_PREFIX = "problem3_dc9_pareto"
SCAN_ALLOWANCES = [2, 4]
SCAN_NEW_CAP_FRACTIONS = [0.75]


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

    pred = pd.read_csv(PRED_PATH)
    pred["date"] = pd.to_datetime(pred["date"])
    pred["origin"] = pred["origin"].astype(str)
    pred["dest"] = pred["dest"].astype(str)
    pred["forecast_volume"] = pred["forecast_volume"].round().astype(int)
    pred["edge"] = pred["origin"] + "->" + pred["dest"]
    return history, pred[["origin", "dest", "edge", "date", "forecast_volume"]]


def build_capacities(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, list[str]]:
    edge_cap = (
        history.groupby(["origin", "dest"], as_index=False)["volume"]
        .max()
        .rename(columns={"volume": "edge_capacity"})
    )
    edge_cap["edge_capacity"] = edge_cap["edge_capacity"].round().astype(int)
    max_existing_edge_capacity = int(edge_cap["edge_capacity"].max())

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
    site_cap["site_capacity"] = site_cap["site_capacity"].round().astype(int)

    sites = sorted(set(history["origin"]).union(history["dest"]))
    return edge_cap, site_cap, max_existing_edge_capacity, sites


def baseline_capacity_anomalies(
    pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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


def prepare_day(
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[tuple[str, str], int], dict[tuple[str, str], int], dict[str, int], dict[str, int]]:
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

    site_base_load: dict[str, int] = {site: 0 for site in site_capacity}
    for _, row in base.iterrows():
        src, dst, volume = row["origin"], row["dest"], int(row["forecast_volume"])
        site_base_load[src] = site_base_load.get(src, 0) + volume
        site_base_load[dst] = site_base_load.get(dst, 0) + volume

    return affected, edge_base, edge_capacity, site_base_load, site_capacity


def build_demands_and_candidates(
    affected: pd.DataFrame,
    edge_base: dict[tuple[str, str], int],
    existing_edge_capacity: dict[tuple[str, str], int],
    sites: list[str],
    new_edge_capacity: int,
) -> tuple[list[dict], list[tuple[int, tuple[str, str]]], dict[tuple[str, str], int], dict[tuple[str, str], bool]]:
    demand_rows: list[dict] = []
    alloc_pairs: list[tuple[int, tuple[str, str]]] = []
    candidate_capacity: dict[tuple[str, str], int] = {}
    is_new_edge: dict[tuple[str, str], bool] = {}

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
            candidates = [(src, site) for site in sites if site not in {CLOSED_SITE, src}]
        else:
            candidates = [(site, dst) for site in sites if site not in {CLOSED_SITE, dst}]

        for edge in candidates:
            if edge in existing_edge_capacity:
                capacity = existing_edge_capacity[edge]
                is_new = False
            else:
                capacity = new_edge_capacity
                is_new = True
            if capacity - edge_base.get(edge, 0) <= 0:
                continue
            candidate_capacity[edge] = capacity
            is_new_edge[edge] = is_new
            alloc_pairs.append((ridx, edge))

    return demand_rows, alloc_pairs, candidate_capacity, is_new_edge


def build_problem(
    name: str,
    demand_rows: list[dict],
    alloc_pairs: list[tuple[int, tuple[str, str]]],
    edge_base: dict[tuple[str, str], int],
    edge_capacity: dict[tuple[str, str], int],
    site_base_load: dict[str, int],
    site_capacity: dict[str, int],
    objective: str,
    is_new_edge: dict[tuple[str, str], bool],
    fixed_unserved: int | None = None,
    existing_changed_limit: int | None = None,
    new_changed_limit: int | None = None,
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
        (rid, edge): pulp.LpVariable(f"x_{rid}_{edge[0]}_{edge[1]}", lowBound=0)
        for rid, edge in alloc_pairs
    }
    u = {rid: pulp.LpVariable(f"u_{rid}", lowBound=0) for rid in demand_ids}
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
        # Balance only lines actually used by the adjustment. This avoids unrelated
        # baseline overload rows dominating the routing decision.
        prob += base_volume + added <= cap * max_load + cap * (1 - y[edge]), f"candidate_load_{edge[0]}_{edge[1]}"

    # Non-candidate baseline lines are still included in exported network workload,
    # but not in the adjustment objective.

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
    existing_changed_count = pulp.lpSum(
        y[edge] for edge in candidate_edges if not is_new_edge.get(edge, False)
    )
    new_changed_count = pulp.lpSum(
        y[edge] for edge in candidate_edges if is_new_edge.get(edge, False)
    )

    if fixed_unserved is not None:
        prob += total_unserved <= fixed_unserved, "fixed_min_unserved"
    if existing_changed_limit is not None:
        prob += existing_changed_count <= existing_changed_limit, "existing_changed_limit"
    if new_changed_limit is not None:
        prob += new_changed_count <= new_changed_limit, "new_changed_limit"
    if changed_limit is not None:
        prob += changed_count <= changed_limit, "changed_limit"

    if objective == "unserved":
        prob += total_unserved
    elif objective == "existing_changed":
        prob += existing_changed_count
    elif objective == "changed":
        prob += changed_count
    elif objective == "load":
        prob += max_load
    else:
        raise ValueError(objective)

    return prob, x, u, y, max_load


def solve_one_day(
    date: pd.Timestamp,
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
    sites: list[str],
    max_existing_edge_capacity: int,
    changed_allowance: int,
    new_cap_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    affected, edge_base, edge_capacity_existing, site_base_load, site_capacity = prepare_day(day_pred, edge_cap, site_cap)
    existing_edge_capacity = {
        (row["origin"], row["dest"]): int(row["edge_capacity"])
        for _, row in edge_cap.iterrows()
        if row["origin"] != CLOSED_SITE and row["dest"] != CLOSED_SITE
    }
    demand_rows, alloc_pairs, candidate_capacity, is_new_edge = build_demands_and_candidates(
        affected,
        edge_base,
        existing_edge_capacity,
        sites,
        max_existing_edge_capacity,
    )
    edge_capacity = {**edge_capacity_existing, **candidate_capacity}

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=SOLVER_TIME_LIMIT)
    date_text = date.strftime("%Y%m%d")
    new_cap_pct = int(round(new_cap_fraction * 100))
    scheme_name = f"pareto_a{changed_allowance}_newcap{new_cap_pct}"

    prob1, _, u1, _, _ = build_problem(
        f"dc9_{date_text}_stage1_unserved",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="unserved",
        is_new_edge=is_new_edge,
    )
    status1 = prob1.solve(solver)
    min_unserved = int(round(sum(pulp.value(v) or 0 for v in u1.values())))

    prob2, _, _, y2, _ = build_problem(
        f"dc9_{date_text}_stage2_changed",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="changed",
        is_new_edge=is_new_edge,
        fixed_unserved=min_unserved,
    )
    status2 = prob2.solve(solver)
    min_changed = int(round(sum(pulp.value(v) or 0 for v in y2.values())))

    changed_limit = min_changed + changed_allowance
    new_changed_limit = max(1, math.ceil(changed_limit * new_cap_fraction))
    prob3, x3, u3, y3, l3 = build_problem(
        f"dc9_{date_text}_stage3_load_a{changed_allowance}_n{new_cap_pct}",
        demand_rows,
        alloc_pairs,
        edge_base,
        edge_capacity,
        site_base_load,
        site_capacity,
        objective="load",
        is_new_edge=is_new_edge,
        fixed_unserved=min_unserved,
        new_changed_limit=new_changed_limit,
        changed_limit=changed_limit,
    )
    status3 = prob3.solve(solver)

    added_by_edge: dict[tuple[str, str], int] = {}
    allocation_records = []
    for (rid, edge), var in x3.items():
        volume = int(round(pulp.value(var) or 0))
        if volume <= 0:
            continue
        demand = demand_rows[rid]
        added_by_edge[edge] = added_by_edge.get(edge, 0) + volume
        allocation_records.append(
            {
                "scheme": scheme_name,
                "date": date,
                "original_edge": demand["original_edge"],
                "demand_type": demand["demand_type"],
                "alternative_origin": edge[0],
                "alternative_dest": edge[1],
                "alternative_edge": f"{edge[0]}->{edge[1]}",
                "is_new_opened_line": bool(is_new_edge.get(edge, False)),
                "allocated_volume": volume,
                "unserved_volume": 0,
            }
        )

    for rid, var in u3.items():
        volume = int(round(pulp.value(var) or 0))
        if volume <= 0:
            continue
        demand = demand_rows[rid]
        allocation_records.append(
            {
                "scheme": scheme_name,
                "date": date,
                "original_edge": demand["original_edge"],
                "demand_type": demand["demand_type"],
                "alternative_origin": "",
                "alternative_dest": "",
                "alternative_edge": "",
                "is_new_opened_line": False,
                "allocated_volume": 0,
                "unserved_volume": volume,
            }
        )

    adjusted_records = []
    all_edges = sorted(set(edge_base) | set(added_by_edge))
    for edge in all_edges:
        base_volume = edge_base.get(edge, 0)
        added = added_by_edge.get(edge, 0)
        cap = edge_capacity[edge]
        adjusted = base_volume + added
        adjusted_records.append(
            {
                "scheme": scheme_name,
                "origin": edge[0],
                "dest": edge[1],
                "edge": f"{edge[0]}->{edge[1]}",
                "date": date,
                "base_forecast_volume": base_volume,
                "added_volume": added,
                "adjusted_volume": adjusted,
                "edge_capacity": cap,
                "is_new_opened_line": bool(is_new_edge.get(edge, False)),
                "line_load_rate": adjusted / cap if cap > 0 else 0.0,
            }
        )

    closed_records = []
    for _, row in affected.iterrows():
        closed_records.append(
            {
                "scheme": scheme_name,
                "date": date,
                "change_type": "close_line",
                "edge": row["edge"],
                "origin": row["origin"],
                "dest": row["dest"],
                "volume_before": int(row["forecast_volume"]),
                "volume_after": 0,
                "capacity": int(row["edge_capacity"]),
                "is_new_opened_line": False,
            }
        )
    for edge, added in sorted(added_by_edge.items()):
        if not is_new_edge.get(edge, False):
            continue
        closed_records.append(
            {
                "scheme": scheme_name,
                "date": date,
                "change_type": "open_line",
                "edge": f"{edge[0]}->{edge[1]}",
                "origin": edge[0],
                "dest": edge[1],
                "volume_before": 0,
                "volume_after": added,
                "capacity": edge_capacity[edge],
                "is_new_opened_line": True,
            }
        )

    allocation_df = pd.DataFrame(allocation_records)
    adjusted_df = pd.DataFrame(adjusted_records)
    line_changes_df = pd.DataFrame(closed_records)

    positive_load = adjusted_df[adjusted_df["edge_capacity"] > 0]["line_load_rate"]
    changed_edges = int((adjusted_df["added_volume"] > 0).sum())
    new_opened = int(adjusted_df[(adjusted_df["added_volume"] > 0) & (adjusted_df["is_new_opened_line"])].shape[0])
    existing_changed = changed_edges - new_opened
    unserved_total = int(round(sum(pulp.value(v) or 0 for v in u3.values())))

    metric = {
        "scheme": scheme_name,
        "date": date,
        "stage1_status": pulp.LpStatus[status1],
        "stage2_status": pulp.LpStatus[status2],
        "stage3_status": pulp.LpStatus[status3],
        "changed_allowance": changed_allowance,
        "new_cap_fraction": new_cap_fraction,
        "minimum_unserved_volume": min_unserved,
        "minimum_changed_lines": min_changed,
        "allowed_changed_lines": changed_limit,
        "allowed_new_opened_lines": new_changed_limit,
        "actual_changed_lines": changed_edges,
        "existing_changed_lines": existing_changed,
        "new_opened_lines": new_opened,
        "closed_positive_lines": int(affected[["origin", "dest"]].drop_duplicates().shape[0]),
        "affected_volume": int(affected["forecast_volume"].sum()),
        "unserved_volume": unserved_total,
        "max_line_load_rate": float(positive_load.max()) if len(positive_load) else 0.0,
        "model_candidate_max_line_load_rate": float(pulp.value(l3) or 0),
        "average_line_load_rate": float(positive_load.mean()) if len(positive_load) else 0.0,
        "line_load_std": float(positive_load.std(ddof=0)) if len(positive_load) else 0.0,
        "candidate_line_count": len(set(edge for _, edge in alloc_pairs)),
        "new_candidate_line_count": int(sum(1 for edge in set(edge for _, edge in alloc_pairs) if is_new_edge.get(edge, False))),
        "affected_positive_line_count": int(affected[["origin", "dest"]].drop_duplicates().shape[0]),
    }
    return allocation_df, adjusted_df, line_changes_df, metric


def verify_allocation(pred: pd.DataFrame, allocation_df: pd.DataFrame) -> pd.DataFrame:
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


def build_post_shutdown_workload(adjusted_df: pd.DataFrame, line_changes_df: pd.DataFrame) -> pd.DataFrame:
    active = adjusted_df[
        [
            "scheme",
            "date",
            "origin",
            "dest",
            "edge",
            "base_forecast_volume",
            "adjusted_volume",
            "edge_capacity",
            "is_new_opened_line",
            "line_load_rate",
        ]
    ].copy()
    active["line_status_after_shutdown"] = active["is_new_opened_line"].map(
        {True: "new_opened", False: "active_existing"}
    )
    active = active.rename(
        columns={
            "base_forecast_volume": "volume_before_shutdown",
            "adjusted_volume": "volume_after_shutdown",
        }
    )

    closed = line_changes_df[line_changes_df["change_type"] == "close_line"][
        ["scheme", "date", "origin", "dest", "edge", "volume_before", "volume_after", "capacity"]
    ].copy()
    closed = closed.rename(
        columns={
            "volume_before": "volume_before_shutdown",
            "volume_after": "volume_after_shutdown",
            "capacity": "edge_capacity",
        }
    )
    closed["is_new_opened_line"] = False
    closed["line_load_rate"] = 0.0
    closed["line_status_after_shutdown"] = "closed_due_to_dc9"

    columns = [
        "scheme",
        "date",
        "origin",
        "dest",
        "edge",
        "line_status_after_shutdown",
        "volume_before_shutdown",
        "volume_after_shutdown",
        "edge_capacity",
        "line_load_rate",
        "is_new_opened_line",
    ]
    return pd.concat([active[columns], closed[columns]], ignore_index=True, sort=False)


def create_visualizations(metrics_df: pd.DataFrame, workload_df: pd.DataFrame, line_changes_df: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    metrics = metrics_df.copy()
    metrics["date"] = pd.to_datetime(metrics["date"])

    plt.style.use("default")

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(metrics["date"], metrics["affected_volume"], marker="o", label="affected volume", color="#1f77b4")
    ax1.plot(metrics["date"], metrics["unserved_volume"], marker="o", label="unserved volume", color="#d62728")
    ax1.set_ylabel("Volume")
    ax2 = ax1.twinx()
    ax2.plot(metrics["date"], metrics["new_opened_lines"], marker="s", label="new opened lines", color="#2ca02c")
    ax2.plot(metrics["date"], metrics["existing_changed_lines"], marker="s", label="existing changed lines", color="#ff7f0e")
    ax2.set_ylabel("Line count")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left", ncol=2)
    ax1.set_title("DC9 new-first daily allocation metrics")
    ax1.grid(True, alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_daily_metrics.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(metrics["date"], metrics["max_line_load_rate"], marker="o", color="#9467bd", label="max load rate")
    ax.plot(metrics["date"], metrics["average_line_load_rate"], marker="o", color="#8c564b", label="average load rate")
    ax.axhline(1.0, color="#d62728", linewidth=1, linestyle="--", label="capacity limit")
    ax.set_title("Post-shutdown line load rate by day")
    ax.set_ylabel("Load rate")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_daily_load_rate.png", dpi=180)
    plt.close(fig)

    active_load = workload_df[
        (workload_df["volume_after_shutdown"] > 0)
        & (workload_df["edge_capacity"] > 0)
        & (workload_df["line_status_after_shutdown"] != "closed_due_to_dc9")
    ]["line_load_rate"]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(active_load, bins=40, color="#4c78a8", edgecolor="white")
    ax.axvline(1.0, color="#d62728", linewidth=1, linestyle="--", label="capacity limit")
    ax.set_title("Post-shutdown active line load-rate distribution")
    ax.set_xlabel("Load rate")
    ax.set_ylabel("Line-day count")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_load_rate_distribution.png", dpi=180)
    plt.close(fig)

    opened = line_changes_df[line_changes_df["change_type"] == "open_line"].copy()
    top_opened = opened.groupby("edge", as_index=False)["volume_after"].sum().sort_values("volume_after", ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top_opened["edge"][::-1], top_opened["volume_after"][::-1], color="#59a14f")
    ax.set_title("Top opened lines by allocated volume")
    ax.set_xlabel("Allocated volume")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_top_opened_lines.png", dpi=180)
    plt.close(fig)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    history, pred = load_inputs()
    edge_cap, site_cap, max_existing_edge_capacity, sites = build_capacities(history)
    edge_over, site_over = baseline_capacity_anomalies(pred, edge_cap, site_cap)
    edge_over.to_csv(RESULT_DIR / "baseline_edge_capacity_anomalies.csv", index=False, encoding="utf-8-sig")
    site_over.to_csv(RESULT_DIR / "baseline_site_capacity_anomalies.csv", index=False, encoding="utf-8-sig")

    day_groups = [(date, day.copy()) for date, day in pred.groupby("date", sort=True)]
    scan_metrics: list[dict] = []

    for allowance in SCAN_ALLOWANCES:
        for new_cap_fraction in SCAN_NEW_CAP_FRACTIONS:
            print(f"\nScan allowance={allowance}, new_cap_fraction={new_cap_fraction:.2f}", flush=True)
            for date, day_pred in day_groups:
                _, _, _, metric = solve_one_day(
                    date,
                    day_pred.copy(),
                    edge_cap,
                    site_cap,
                    sites,
                    max_existing_edge_capacity,
                    allowance,
                    new_cap_fraction,
                )
                scan_metrics.append(metric)
                print(
                    f"  {date.date()} unserved={metric['unserved_volume']}, "
                    f"changed={metric['actual_changed_lines']}, new={metric['new_opened_lines']}, "
                    f"candidate_load={metric['model_candidate_max_line_load_rate']:.4f}, "
                    f"status={metric['stage3_status']}",
                    flush=True,
                )

    scan_df = pd.DataFrame(scan_metrics)
    scan_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_daily_scan.csv", index=False, encoding="utf-8-sig")

    summary = (
        scan_df.groupby("scheme", as_index=False)
        .agg(
            day_count=("date", "nunique"),
            changed_allowance=("changed_allowance", "first"),
            new_cap_fraction=("new_cap_fraction", "first"),
            affected_total_volume=("affected_volume", "sum"),
            unserved_total_volume=("unserved_volume", "sum"),
            average_daily_changed_lines=("actual_changed_lines", "mean"),
            max_daily_changed_lines=("actual_changed_lines", "max"),
            average_daily_new_opened_lines=("new_opened_lines", "mean"),
            max_daily_new_opened_lines=("new_opened_lines", "max"),
            average_daily_existing_changed_lines=("existing_changed_lines", "mean"),
            max_candidate_line_load_rate=("model_candidate_max_line_load_rate", "max"),
            max_line_load_rate=("max_line_load_rate", "max"),
            average_line_load_rate=("average_line_load_rate", "mean"),
            average_load_std=("line_load_std", "mean"),
            optimal_days=("stage3_status", lambda s: int((s == "Optimal").sum())),
        )
        .sort_values("scheme")
    )
    summary["new_opened_share"] = summary["average_daily_new_opened_lines"] / summary["average_daily_changed_lines"]
    summary["new_edge_capacity"] = max_existing_edge_capacity
    summary["baseline_edge_capacity_anomaly_rows"] = len(edge_over)
    summary["baseline_site_capacity_anomaly_rows"] = len(site_over)

    valid = summary[
        (summary["optimal_days"] == summary["day_count"])
        & (summary["unserved_total_volume"] == summary["unserved_total_volume"].min())
    ].copy()
    min_avg_changed = valid["average_daily_changed_lines"].min()
    valid = valid[valid["average_daily_changed_lines"] <= min_avg_changed + 3].copy()
    balanced = valid[(valid["new_opened_share"] >= 0.45) & (valid["new_opened_share"] <= 0.80)].copy()
    if balanced.empty:
        balanced = valid.copy()

    def normalize(series: pd.Series) -> pd.Series:
        span = series.max() - series.min()
        if span == 0:
            return pd.Series(0.0, index=series.index)
        return (series - series.min()) / span

    balanced["recommend_score"] = (
        normalize(balanced["max_candidate_line_load_rate"])
        + 0.35 * normalize(balanced["average_daily_changed_lines"])
        + 0.15 * (balanced["new_opened_share"] - 0.60).abs()
    )
    recommended = balanced.sort_values(
        ["recommend_score", "max_candidate_line_load_rate", "average_daily_changed_lines"]
    ).iloc[0]
    summary["recommended"] = summary["scheme"] == recommended["scheme"]
    summary.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_summary.csv", index=False, encoding="utf-8-sig")

    rec_allowance = int(recommended["changed_allowance"])
    rec_new_cap_fraction = float(recommended["new_cap_fraction"])
    print(
        f"\nRecommended scheme: {recommended['scheme']} "
        f"(allowance={rec_allowance}, new_cap_fraction={rec_new_cap_fraction:.2f})",
        flush=True,
    )

    all_allocations: list[pd.DataFrame] = []
    all_adjusted: list[pd.DataFrame] = []
    all_line_changes: list[pd.DataFrame] = []
    all_metrics: list[dict] = []
    for date, day_pred in day_groups:
        allocation_df, adjusted_df, line_changes_df, metric = solve_one_day(
            date,
            day_pred.copy(),
            edge_cap,
            site_cap,
            sites,
            max_existing_edge_capacity,
            rec_allowance,
            rec_new_cap_fraction,
        )
        all_allocations.append(allocation_df)
        all_adjusted.append(adjusted_df)
        all_line_changes.append(line_changes_df)
        all_metrics.append(metric)

    allocation_df = pd.concat(all_allocations, ignore_index=True, sort=False)
    adjusted_df = pd.concat(all_adjusted, ignore_index=True, sort=False)
    line_changes_df = pd.concat(all_line_changes, ignore_index=True, sort=False)
    metrics_df = pd.DataFrame(all_metrics)
    workload_df = build_post_shutdown_workload(adjusted_df, line_changes_df)
    verification_df = verify_allocation(pred, allocation_df)
    create_visualizations(metrics_df, workload_df, line_changes_df)

    allocation_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_recommended_allocation_detail.csv", index=False, encoding="utf-8-sig")
    adjusted_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_recommended_adjusted_line_volume.csv", index=False, encoding="utf-8-sig")
    workload_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_recommended_post_shutdown_line_workload.csv", index=False, encoding="utf-8-sig")
    line_changes_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_recommended_daily_line_changes.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_recommended_daily_metrics.csv", index=False, encoding="utf-8-sig")
    verification_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_recommended_allocation_verification.csv", index=False, encoding="utf-8-sig")

    print("\nSummary:")
    print(summary.round(6).to_string(index=False))
    print("\nAllocation verification:")
    print(verification_df.to_string(index=False))
    print(f"\nOutput directory: {RESULT_DIR}")


if __name__ == "__main__":
    main()



# ============================================================
# Part C: fast flow heuristic balance scheme
# Source: q3_revised\code\problem3_dc9_flow_heuristic.py
# ============================================================

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "paper_skill_materials" / "raw_data" / "history_volume_data.xlsx"
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
RESULT_DIR = BASE_DIR / "q3_revised" / "results"
FIGURE_DIR = BASE_DIR / "q3_revised" / "figures"

CLOSED_SITE = "DC9"
OUTPUT_PREFIX = "problem3_dc9_flow_heuristic"
TARGET_NEW_SHARES = [0.40, 0.55, 0.70]
LINES_PER_DEMAND_CHOICES = [1, 2]
RHO_SLACKS = [0.15, 0.30, 0.45, 0.60]
EPS = 1e-6


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

    pred = pd.read_csv(PRED_PATH)
    pred["date"] = pd.to_datetime(pred["date"])
    pred["origin"] = pred["origin"].astype(str)
    pred["dest"] = pred["dest"].astype(str)
    pred["forecast_volume"] = pred["forecast_volume"].round().astype(float)
    pred["edge"] = pred["origin"] + "->" + pred["dest"]
    return history, pred[["origin", "dest", "edge", "date", "forecast_volume"]]


def build_capacities(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, list[str]]:
    edge_cap = (
        history.groupby(["origin", "dest"], as_index=False)["volume"]
        .max()
        .rename(columns={"volume": "edge_capacity"})
    )
    edge_cap["edge_capacity"] = edge_cap["edge_capacity"].round().astype(float)
    max_edge_capacity = int(edge_cap["edge_capacity"].max())

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
    site_cap["site_capacity"] = site_cap["site_capacity"].round().astype(float)
    sites = sorted(set(history["origin"]).union(history["dest"]))
    return edge_cap, site_cap, max_edge_capacity, sites


def prepare_day(
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
    sites: list[str],
    new_edge_capacity: int,
) -> dict:
    day = day_pred.merge(edge_cap, on=["origin", "dest"], how="left")
    day["edge_capacity"] = day["edge_capacity"].fillna(0.0)

    affected = day[((day["origin"] == CLOSED_SITE) | (day["dest"] == CLOSED_SITE)) & (day["forecast_volume"] > 0)].copy()
    base = day[(day["origin"] != CLOSED_SITE) & (day["dest"] != CLOSED_SITE)].copy()

    edge_base = {(r.origin, r.dest): float(r.forecast_volume) for r in base.itertuples()}
    existing_edge_capacity = {
        (r.origin, r.dest): float(r.edge_capacity)
        for r in edge_cap.itertuples()
        if r.origin != CLOSED_SITE and r.dest != CLOSED_SITE
    }
    edge_capacity = {(r.origin, r.dest): float(r.edge_capacity) for r in base.itertuples()}
    site_capacity = {
        r.site: float(r.site_capacity)
        for r in site_cap[site_cap["site"] != CLOSED_SITE].itertuples()
    }
    site_base_load = {site: 0.0 for site in site_capacity}
    for r in base.itertuples():
        volume = float(r.forecast_volume)
        site_base_load[r.origin] = site_base_load.get(r.origin, 0.0) + volume
        site_base_load[r.dest] = site_base_load.get(r.dest, 0.0) + volume
    site_spare = {site: max(site_capacity[site] - site_base_load.get(site, 0.0), 0.0) for site in site_capacity}

    demands: list[dict] = []
    pairs: list[tuple[int, tuple[str, str]]] = []
    candidate_capacity: dict[tuple[str, str], float] = {}
    is_new_edge: dict[tuple[str, str], bool] = {}

    for rid, row in enumerate(affected.itertuples()):
        src, dst = row.origin, row.dest
        demands.append(
            {
                "demand_id": rid,
                "origin": src,
                "dest": dst,
                "original_edge": f"{src}->{dst}",
                "demand_type": "outbound_from_closed_site" if src == CLOSED_SITE else "inbound_to_closed_site",
                "demand_volume": float(row.forecast_volume),
            }
        )
        if dst == CLOSED_SITE:
            candidates = [(src, site) for site in sites if site not in {CLOSED_SITE, src}]
        else:
            candidates = [(site, dst) for site in sites if site not in {CLOSED_SITE, dst}]

        for edge in candidates:
            if edge in existing_edge_capacity:
                capacity = existing_edge_capacity[edge]
                is_new = False
            else:
                capacity = float(new_edge_capacity)
                is_new = True
            if capacity - edge_base.get(edge, 0.0) <= EPS:
                continue
            candidate_capacity[edge] = capacity
            is_new_edge[edge] = is_new
            edge_capacity[edge] = capacity
            pairs.append((rid, edge))

    return {
        "affected": affected,
        "base": base,
        "demands": demands,
        "pairs": pairs,
        "edge_base": edge_base,
        "edge_capacity": edge_capacity,
        "candidate_capacity": candidate_capacity,
        "is_new_edge": is_new_edge,
        "site_spare": site_spare,
        "site_base_load": site_base_load,
        "site_capacity": site_capacity,
    }


def edge_available_capacity(edge: tuple[str, str], edge_base: dict, edge_capacity: dict, rho: float | None) -> float:
    cap = edge_capacity[edge]
    base = edge_base.get(edge, 0.0)
    if rho is None:
        return max(cap - base, 0.0)
    return max(min(cap - base, rho * cap - base), 0.0)


def solve_flow_lp(
    day_data: dict,
    selected_edges: set[tuple[str, str]] | None = None,
    rho: float | None = None,
    return_solution: bool = False,
) -> tuple[float, dict[tuple[int, tuple[str, str]], float], str]:
    demands = day_data["demands"]
    pairs_all = day_data["pairs"]
    edge_base = day_data["edge_base"]
    edge_capacity = day_data["edge_capacity"]
    site_spare = day_data["site_spare"]

    if selected_edges is None:
        selected_edges = {edge for _, edge in pairs_all}

    pairs = [
        (rid, edge)
        for rid, edge in pairs_all
        if edge in selected_edges and edge_available_capacity(edge, edge_base, edge_capacity, rho) > EPS
    ]
    if not pairs:
        return 0.0, {}, "empty"

    demand_amount = {row["demand_id"]: row["demand_volume"] for row in demands}
    demand_ids = sorted(demand_amount)
    candidate_edges = sorted({edge for _, edge in pairs})
    sites = sorted(site_spare)

    demand_row = {rid: idx for idx, rid in enumerate(demand_ids)}
    edge_row = {edge: len(demand_ids) + idx for idx, edge in enumerate(candidate_edges)}
    site_row = {site: len(demand_ids) + len(candidate_edges) + idx for idx, site in enumerate(sites)}
    n_rows = len(demand_ids) + len(candidate_edges) + len(sites)
    n_cols = len(pairs)

    a_ub = lil_matrix((n_rows, n_cols), dtype=float)
    b_ub = np.zeros(n_rows, dtype=float)
    for rid, amount in demand_amount.items():
        b_ub[demand_row[rid]] = amount
    for edge in candidate_edges:
        b_ub[edge_row[edge]] = edge_available_capacity(edge, edge_base, edge_capacity, rho)
    for site in sites:
        b_ub[site_row[site]] = site_spare[site]

    for col, (rid, edge) in enumerate(pairs):
        a_ub[demand_row[rid], col] = 1.0
        a_ub[edge_row[edge], col] = 1.0
        a_ub[site_row[edge[0]], col] = 1.0
        a_ub[site_row[edge[1]], col] = 1.0

    c = -np.ones(n_cols, dtype=float)
    res = linprog(c, A_ub=a_ub.tocsr(), b_ub=b_ub, bounds=(0, None), method="highs")
    if not res.success:
        return 0.0, {}, res.message

    served = float(-res.fun)
    if not return_solution:
        return served, {}, "optimal"
    solution = {
        pair: float(value)
        for pair, value in zip(pairs, res.x)
        if value > 1e-5
    }
    return served, solution, "optimal"


def find_min_rho(day_data: dict, target_served: float, selected_edges: set[tuple[str, str]] | None = None) -> float:
    lo, hi = 0.0, 1.25
    for _ in range(20):
        mid = (lo + hi) / 2
        served, _, _ = solve_flow_lp(day_data, selected_edges=selected_edges, rho=mid)
        if served + 1e-4 >= target_served:
            hi = mid
        else:
            lo = mid
    return hi


def select_edges_for_day(day_data: dict, target_served: float, rho: float) -> tuple[set[tuple[str, str]], dict]:
    demands = day_data["demands"]
    pairs = day_data["pairs"]
    edge_base = day_data["edge_base"]
    edge_capacity = day_data["edge_capacity"]
    is_new_edge = day_data["is_new_edge"]

    by_demand: dict[int, list[tuple[str, str]]] = {row["demand_id"]: [] for row in demands}
    for rid, edge in pairs:
        if edge_available_capacity(edge, edge_base, edge_capacity, rho) > EPS:
            by_demand[rid].append(edge)

    best: tuple[float, set[tuple[str, str]], dict] | None = None
    for target_share in TARGET_NEW_SHARES:
        for lines_per_demand in LINES_PER_DEMAND_CHOICES:
            selected: set[tuple[str, str]] = set()
            for rid, edges in by_demand.items():
                new_edges = [edge for edge in edges if is_new_edge.get(edge, False)]
                old_edges = [edge for edge in edges if not is_new_edge.get(edge, False)]
                key = lambda edge: edge_available_capacity(edge, edge_base, edge_capacity, rho)
                new_edges.sort(key=key, reverse=True)
                old_edges.sort(key=key, reverse=True)
                new_count = int(round(lines_per_demand * target_share))
                old_count = lines_per_demand - new_count
                chosen = new_edges[:new_count] + old_edges[:old_count]
                if len(chosen) < lines_per_demand:
                    pool = [edge for edge in new_edges + old_edges if edge not in chosen]
                    chosen += pool[: lines_per_demand - len(chosen)]
                selected.update(chosen)

            served, solution, status = solve_flow_lp(day_data, selected_edges=selected, rho=rho, return_solution=True)
            if served + 1e-4 < target_served:
                continue

            selected = prune_edges(day_data, selected, target_served, rho, solution)
            served, solution, _ = solve_flow_lp(day_data, selected_edges=selected, rho=rho, return_solution=True)
            used_edges = {edge for (_, edge), volume in solution.items() if volume > 1e-5}
            if not used_edges:
                continue
            new_count_used = sum(1 for edge in used_edges if is_new_edge.get(edge, False))
            changed_count = len(used_edges)
            new_share = new_count_used / changed_count
            score = rho + 0.045 * changed_count + 0.08 * abs(new_share - 0.55)
            meta = {
                "target_new_share": target_share,
                "lines_per_demand": lines_per_demand,
                "changed_count": changed_count,
                "new_opened_count": new_count_used,
                "existing_changed_count": changed_count - new_count_used,
                "new_opened_share": new_share,
                "served": served,
            }
            if best is None or score < best[0]:
                best = (score, used_edges, meta)

    if best is None:
        served, solution, _ = solve_flow_lp(day_data, rho=rho, return_solution=True)
        used_edges = {edge for (_, edge), volume in solution.items() if volume > 1e-5}
        new_count_used = sum(1 for edge in used_edges if is_new_edge.get(edge, False))
        meta = {
            "target_new_share": -1,
            "lines_per_demand": -1,
            "changed_count": len(used_edges),
            "new_opened_count": new_count_used,
            "existing_changed_count": len(used_edges) - new_count_used,
            "new_opened_share": new_count_used / len(used_edges) if used_edges else 0.0,
            "served": served,
        }
        return used_edges, meta
    return best[1], best[2]


def prune_edges(
    day_data: dict,
    selected: set[tuple[str, str]],
    target_served: float,
    rho: float,
    solution: dict[tuple[int, tuple[str, str]], float],
) -> set[tuple[str, str]]:
    used_volume: dict[tuple[str, str], float] = {}
    for (_, edge), volume in solution.items():
        used_volume[edge] = used_volume.get(edge, 0.0) + volume

    current = set(selected)
    for edge, _ in sorted(used_volume.items(), key=lambda item: item[1]):
        trial = current - {edge}
        served, _, _ = solve_flow_lp(day_data, selected_edges=trial, rho=rho)
        if served + 1e-4 >= target_served:
            current = trial
    return current


def solve_one_day(
    date: pd.Timestamp,
    day_pred: pd.DataFrame,
    edge_cap: pd.DataFrame,
    site_cap: pd.DataFrame,
    sites: list[str],
    new_edge_capacity: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    day_data = prepare_day(day_pred, edge_cap, site_cap, sites, new_edge_capacity)
    affected = day_data["affected"]
    total_demand = float(sum(row["demand_volume"] for row in day_data["demands"]))
    served_without_rho, _, _ = solve_flow_lp(day_data, rho=None)
    min_unserved = max(total_demand - served_without_rho, 0.0)
    target_served = total_demand - min_unserved

    min_rho_all = find_min_rho(day_data, target_served)
    best_day: tuple[float, float, set[tuple[str, str]], dict] | None = None
    for slack in RHO_SLACKS:
        rho = min(1.25, min_rho_all + slack)
        selected_edges, meta = select_edges_for_day(day_data, target_served, rho)
        final_rho = find_min_rho(day_data, target_served, selected_edges=selected_edges)
        score = final_rho + 0.045 * meta["changed_count"] + 0.08 * abs(meta["new_opened_share"] - 0.55)
        if best_day is None or score < best_day[0]:
            best_day = (score, final_rho, selected_edges, meta)

    assert best_day is not None
    _, final_rho, selected_edges, selection_meta = best_day
    served, solution, status = solve_flow_lp(day_data, selected_edges=selected_edges, rho=final_rho, return_solution=True)

    demands = day_data["demands"]
    edge_base = day_data["edge_base"]
    edge_capacity = day_data["edge_capacity"]
    is_new_edge = day_data["is_new_edge"]

    demand_served = {row["demand_id"]: 0.0 for row in demands}
    added_by_edge: dict[tuple[str, str], float] = {}
    allocation_records = []
    for (rid, edge), volume in solution.items():
        if volume <= 1e-5:
            continue
        demand = demands[rid]
        demand_served[rid] += volume
        added_by_edge[edge] = added_by_edge.get(edge, 0.0) + volume
        allocation_records.append(
            {
                "scheme": "flow_heuristic_balanced",
                "date": date,
                "original_edge": demand["original_edge"],
                "demand_type": demand["demand_type"],
                "alternative_origin": edge[0],
                "alternative_dest": edge[1],
                "alternative_edge": f"{edge[0]}->{edge[1]}",
                "is_new_opened_line": bool(is_new_edge.get(edge, False)),
                "allocated_volume": volume,
                "unserved_volume": 0.0,
            }
        )

    for demand in demands:
        unserved = max(demand["demand_volume"] - demand_served[demand["demand_id"]], 0.0)
        if unserved > 1e-5:
            allocation_records.append(
                {
                    "scheme": "flow_heuristic_balanced",
                    "date": date,
                    "original_edge": demand["original_edge"],
                    "demand_type": demand["demand_type"],
                    "alternative_origin": "",
                    "alternative_dest": "",
                    "alternative_edge": "",
                    "is_new_opened_line": False,
                    "allocated_volume": 0.0,
                    "unserved_volume": unserved,
                }
            )

    adjusted_records = []
    for edge in sorted(set(edge_base) | set(added_by_edge)):
        base_volume = edge_base.get(edge, 0.0)
        added = added_by_edge.get(edge, 0.0)
        cap = edge_capacity[edge]
        adjusted = base_volume + added
        adjusted_records.append(
            {
                "scheme": "flow_heuristic_balanced",
                "origin": edge[0],
                "dest": edge[1],
                "edge": f"{edge[0]}->{edge[1]}",
                "date": date,
                "base_forecast_volume": base_volume,
                "added_volume": added,
                "adjusted_volume": adjusted,
                "edge_capacity": cap,
                "is_new_opened_line": bool(is_new_edge.get(edge, False)),
                "line_load_rate": adjusted / cap if cap > 0 else 0.0,
            }
        )

    line_changes = []
    for row in affected.itertuples():
        line_changes.append(
            {
                "scheme": "flow_heuristic_balanced",
                "date": date,
                "change_type": "close_line",
                "edge": row.edge,
                "origin": row.origin,
                "dest": row.dest,
                "volume_before": float(row.forecast_volume),
                "volume_after": 0.0,
                "capacity": float(row.edge_capacity),
                "is_new_opened_line": False,
            }
        )
    for edge, added in sorted(added_by_edge.items()):
        if not is_new_edge.get(edge, False):
            continue
        line_changes.append(
            {
                "scheme": "flow_heuristic_balanced",
                "date": date,
                "change_type": "open_line",
                "edge": f"{edge[0]}->{edge[1]}",
                "origin": edge[0],
                "dest": edge[1],
                "volume_before": 0.0,
                "volume_after": added,
                "capacity": edge_capacity[edge],
                "is_new_opened_line": True,
            }
        )

    allocation_df = pd.DataFrame(allocation_records)
    adjusted_df = pd.DataFrame(adjusted_records)
    line_changes_df = pd.DataFrame(line_changes)
    changed_edges = {edge for edge, added in added_by_edge.items() if added > 1e-5}
    new_opened = sum(1 for edge in changed_edges if is_new_edge.get(edge, False))
    candidate_load = adjusted_df[adjusted_df["added_volume"] > 1e-5]["line_load_rate"]
    active_load = adjusted_df[adjusted_df["edge_capacity"] > 0]["line_load_rate"]
    metric = {
        "scheme": "flow_heuristic_balanced",
        "date": date,
        "status": status,
        "affected_volume": total_demand,
        "served_volume": served,
        "unserved_volume": max(total_demand - served, 0.0),
        "minimum_unserved_volume": min_unserved,
        "min_rho_with_all_candidates": min_rho_all,
        "selected_candidate_max_load_rate": final_rho,
        "actual_changed_lines": len(changed_edges),
        "new_opened_lines": new_opened,
        "existing_changed_lines": len(changed_edges) - new_opened,
        "new_opened_share": new_opened / len(changed_edges) if changed_edges else 0.0,
        "closed_positive_lines": int(affected[["origin", "dest"]].drop_duplicates().shape[0]),
        "max_candidate_line_load_rate": float(candidate_load.max()) if len(candidate_load) else 0.0,
        "max_line_load_rate": float(active_load.max()) if len(active_load) else 0.0,
        "average_line_load_rate": float(active_load.mean()) if len(active_load) else 0.0,
        "line_load_std": float(active_load.std(ddof=0)) if len(active_load) else 0.0,
        **selection_meta,
    }
    return allocation_df, adjusted_df, line_changes_df, metric


def build_workload(adjusted_df: pd.DataFrame, line_changes_df: pd.DataFrame) -> pd.DataFrame:
    active = adjusted_df[
        [
            "scheme",
            "date",
            "origin",
            "dest",
            "edge",
            "base_forecast_volume",
            "adjusted_volume",
            "edge_capacity",
            "is_new_opened_line",
            "line_load_rate",
        ]
    ].copy()
    active["line_status_after_shutdown"] = active["is_new_opened_line"].map(
        {True: "new_opened", False: "active_existing"}
    )
    active = active.rename(
        columns={
            "base_forecast_volume": "volume_before_shutdown",
            "adjusted_volume": "volume_after_shutdown",
        }
    )
    closed = line_changes_df[line_changes_df["change_type"] == "close_line"][
        ["scheme", "date", "origin", "dest", "edge", "volume_before", "volume_after", "capacity"]
    ].copy()
    closed = closed.rename(
        columns={
            "volume_before": "volume_before_shutdown",
            "volume_after": "volume_after_shutdown",
            "capacity": "edge_capacity",
        }
    )
    closed["is_new_opened_line"] = False
    closed["line_load_rate"] = 0.0
    closed["line_status_after_shutdown"] = "closed_due_to_dc9"
    columns = [
        "scheme",
        "date",
        "origin",
        "dest",
        "edge",
        "line_status_after_shutdown",
        "volume_before_shutdown",
        "volume_after_shutdown",
        "edge_capacity",
        "line_load_rate",
        "is_new_opened_line",
    ]
    return pd.concat([active[columns], closed[columns]], ignore_index=True, sort=False)


def create_figures(metrics: pd.DataFrame, workload: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    metrics = metrics.copy()
    metrics["date"] = pd.to_datetime(metrics["date"])

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.plot(metrics["date"], metrics["selected_candidate_max_load_rate"], marker="o", label="selected candidate max load", color="#4c78a8")
    ax1.plot(metrics["date"], metrics["min_rho_with_all_candidates"], marker="o", label="all-candidate min load", color="#72b7b2")
    ax1.set_ylabel("Load rate")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(metrics["date"], metrics["actual_changed_lines"], marker="s", color="#f58518", label="changed lines")
    ax2.plot(metrics["date"], metrics["new_opened_lines"], marker="s", color="#54a24b", label="new opened lines")
    ax2.set_ylabel("Line count")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left", ncol=2)
    ax1.set_title("DC9 flow heuristic: load and line changes")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_daily_balance.png", dpi=180)
    plt.close(fig)

    active = workload[
        (workload["volume_after_shutdown"] > 0)
        & (workload["line_status_after_shutdown"] != "closed_due_to_dc9")
    ]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(active["line_load_rate"], bins=40, color="#4c78a8", edgecolor="white")
    ax.axvline(1.0, color="#d62728", linestyle="--", linewidth=1)
    ax.set_title("Post-shutdown line load-rate distribution")
    ax.set_xlabel("Load rate")
    ax.set_ylabel("Line-day count")
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / f"{OUTPUT_PREFIX}_load_distribution.png", dpi=180)
    plt.close(fig)


def verify_allocation(pred: pd.DataFrame, allocation_df: pd.DataFrame) -> pd.DataFrame:
    affected = pred[((pred["origin"] == CLOSED_SITE) | (pred["dest"] == CLOSED_SITE)) & (pred["forecast_volume"] > 0)].copy()
    served = allocation_df[allocation_df["allocated_volume"] > 0]
    unserved = allocation_df[allocation_df["unserved_volume"] > 0]
    return pd.DataFrame(
        [
            {
                "closed_site": CLOSED_SITE,
                "inbound_total": float(affected[affected["dest"] == CLOSED_SITE]["forecast_volume"].sum()),
                "inbound_served": float(served[served["demand_type"] == "inbound_to_closed_site"]["allocated_volume"].sum()),
                "inbound_unserved": float(unserved[unserved["demand_type"] == "inbound_to_closed_site"]["unserved_volume"].sum()),
                "outbound_total": float(affected[affected["origin"] == CLOSED_SITE]["forecast_volume"].sum()),
                "outbound_served": float(served[served["demand_type"] == "outbound_from_closed_site"]["allocated_volume"].sum()),
                "outbound_unserved": float(unserved[unserved["demand_type"] == "outbound_from_closed_site"]["unserved_volume"].sum()),
            }
        ]
    )


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    history, pred = load_inputs()
    edge_cap, site_cap, new_edge_capacity, sites = build_capacities(history)

    allocations: list[pd.DataFrame] = []
    adjusted: list[pd.DataFrame] = []
    changes: list[pd.DataFrame] = []
    metrics: list[dict] = []
    for date, day_pred in pred.groupby("date", sort=True):
        print(f"Solve {date.date()} ...", flush=True)
        allocation_df, adjusted_df, line_changes_df, metric = solve_one_day(
            date,
            day_pred.copy(),
            edge_cap,
            site_cap,
            sites,
            new_edge_capacity,
        )
        allocations.append(allocation_df)
        adjusted.append(adjusted_df)
        changes.append(line_changes_df)
        metrics.append(metric)
        print(
            f"  unserved={metric['unserved_volume']:.0f}, changed={metric['actual_changed_lines']}, "
            f"new={metric['new_opened_lines']}, load={metric['selected_candidate_max_load_rate']:.4f}",
            flush=True,
        )

    allocation_df = pd.concat(allocations, ignore_index=True, sort=False)
    adjusted_df = pd.concat(adjusted, ignore_index=True, sort=False)
    changes_df = pd.concat(changes, ignore_index=True, sort=False)
    metrics_df = pd.DataFrame(metrics)
    workload_df = build_workload(adjusted_df, changes_df)
    verification_df = verify_allocation(pred, allocation_df)

    allocation_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_allocation_detail.csv", index=False, encoding="utf-8-sig")
    adjusted_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_adjusted_line_volume.csv", index=False, encoding="utf-8-sig")
    changes_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_daily_line_changes.csv", index=False, encoding="utf-8-sig")
    workload_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_post_shutdown_line_workload.csv", index=False, encoding="utf-8-sig")
    metrics_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_daily_metrics.csv", index=False, encoding="utf-8-sig")
    verification_df.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_allocation_verification.csv", index=False, encoding="utf-8-sig")

    summary = (
        metrics_df.groupby("scheme", as_index=False)
        .agg(
            day_count=("date", "nunique"),
            affected_total_volume=("affected_volume", "sum"),
            unserved_total_volume=("unserved_volume", "sum"),
            average_daily_changed_lines=("actual_changed_lines", "mean"),
            max_daily_changed_lines=("actual_changed_lines", "max"),
            average_daily_new_opened_lines=("new_opened_lines", "mean"),
            average_daily_existing_changed_lines=("existing_changed_lines", "mean"),
            average_new_opened_share=("new_opened_share", "mean"),
            max_selected_candidate_load_rate=("selected_candidate_max_load_rate", "max"),
            average_selected_candidate_load_rate=("selected_candidate_max_load_rate", "mean"),
            max_line_load_rate=("max_line_load_rate", "max"),
            average_line_load_rate=("average_line_load_rate", "mean"),
        )
    )
    summary["new_edge_capacity"] = new_edge_capacity
    summary.to_csv(RESULT_DIR / f"{OUTPUT_PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    create_figures(metrics_df, workload_df)

    print("\nSummary:")
    print(summary.round(6).to_string(index=False))
    print("\nVerification:")
    print(verification_df.round(6).to_string(index=False))


if __name__ == "__main__":
    main()

