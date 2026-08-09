from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
SITE_IMPORTANCE_PATH = BASE_DIR / "q4_analysis" / "results" / "problem4_site_core_importance.csv"
EDGE_IMPORTANCE_PATH = BASE_DIR / "q4_analysis" / "results" / "problem4_edge_core_importance.csv"
RESULT_DIR = BASE_DIR / "q4_analysis" / "results"

NEW_SITE = "DC_NEW"
NEW_SITE_CAPACITY = 800_000
NEW_EDGE_CAPACITY_UPPER = 505_833
MONTE_CARLO_RUNS = 200
RANDOM_SEED = 20260721


def round_up_1000(value: float) -> int:
    return int(np.ceil(value / 1000.0) * 1000)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pred = pd.read_csv(PRED_PATH)
    pred["date"] = pd.to_datetime(pred["date"])
    pred["forecast_volume"] = pred["forecast_volume"].astype(float)
    pred["edge"] = pred["origin"].astype(str) + "->" + pred["dest"].astype(str)
    site = pd.read_csv(SITE_IMPORTANCE_PATH)
    edge = pd.read_csv(EDGE_IMPORTANCE_PATH)
    return pred, site, edge


def choose_connected_sites(site: pd.DataFrame, edge: pd.DataFrame) -> pd.DataFrame:
    core_sites = site.head(8)["site"].tolist()
    core_set = set(core_sites)

    key_neighbors: list[str] = []
    for row in edge.head(30).itertuples():
        if row.origin in core_set and row.dest not in core_set:
            key_neighbors.append(row.dest)
        if row.dest in core_set and row.origin not in core_set:
            key_neighbors.append(row.origin)

    pressure_sites = site.sort_values(
        ["forecast_max_load_rate", "forecast_total_throughput"], ascending=False
    ).head(6)["site"].tolist()

    selected: list[str] = []
    for group in [core_sites, key_neighbors, pressure_sites]:
        for site_name in group:
            if site_name not in selected:
                selected.append(site_name)
            if len(selected) >= 14:
                break
        if len(selected) >= 14:
            break

    selected_df = site[site["site"].isin(selected)].copy()
    selected_df["selection_order"] = selected_df["site"].map({s: i + 1 for i, s in enumerate(selected)})
    selected_df["selection_reason"] = selected_df["site"].apply(
        lambda s: "core_importance"
        if s in core_sites
        else ("high_failure_neighbor" if s in key_neighbors else "pressure_buffer")
    )
    return selected_df.sort_values("selection_order")


def add_site_roles(selected_sites: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    inbound = pred.groupby("dest")["forecast_volume"].sum().rename("forecast_inbound")
    outbound = pred.groupby("origin")["forecast_volume"].sum().rename("forecast_outbound")
    selected = selected_sites.merge(inbound, left_on="site", right_index=True, how="left")
    selected = selected.merge(outbound, left_on="site", right_index=True, how="left").fillna(0)
    selected["forecast_total_io"] = selected["forecast_inbound"] + selected["forecast_outbound"]
    selected["inbound_share"] = selected["forecast_inbound"] / (selected["forecast_total_io"] + 1e-9)
    selected["outbound_share"] = selected["forecast_outbound"] / (selected["forecast_total_io"] + 1e-9)

    def role(row: pd.Series) -> str:
        if row["outbound_share"] >= 0.60:
            return "source"
        if row["inbound_share"] >= 0.60:
            return "sink"
        return "transit"

    selected["site_role"] = selected.apply(role, axis=1)
    return selected


def line_capacity_for_site(site_row: pd.Series) -> int:
    base_capacity = max(100_000, 0.55 * float(site_row["forecast_daily_max"]))
    return min(NEW_EDGE_CAPACITY_UPPER, round_up_1000(base_capacity))


def design_new_lines(selected_sites: pd.DataFrame, pred: pd.DataFrame, edge_importance: pd.DataFrame) -> pd.DataFrame:
    records = []
    site_info = selected_sites.set_index("site")

    def add_line(site_name: str, origin: str, dest: str, direction: str, reason: str) -> None:
        if site_name not in site_info.index:
            return
        row = site_info.loc[site_name]
        edge_name = f"{origin}->{dest}"
        if any(record["edge"] == edge_name for record in records):
            existing = next(record for record in records if record["edge"] == edge_name)
            if reason not in existing["selection_reason"].split("+"):
                existing["selection_reason"] = existing["selection_reason"] + "+" + reason
            return
        records.append(
            {
                "origin": origin,
                "dest": dest,
                "edge": edge_name,
                "connected_existing_site": site_name,
                "direction_type": direction,
                "new_line_capacity": line_capacity_for_site(row),
                "site_importance_score": row.importance_score,
                "site_forecast_daily_max": row.forecast_daily_max,
                "site_forecast_total": row.forecast_total_throughput,
                "site_role": row.site_role,
                "inbound_share": row.inbound_share,
                "outbound_share": row.outbound_share,
                "selection_reason": reason,
            }
        )

    for row in selected_sites.itertuples():
        if row.site_role == "source":
            directions = [(row.site, NEW_SITE, "to_new_site", row.selection_reason)]
        elif row.site_role == "sink":
            directions = [(NEW_SITE, row.site, "from_new_site", row.selection_reason)]
        else:
            directions = [
                (row.site, NEW_SITE, "to_new_site", row.selection_reason),
                (NEW_SITE, row.site, "from_new_site", row.selection_reason),
            ]

        for origin, dest, direction, reason in directions:
            add_line(row.site, origin, dest, direction, reason)

    overload_edges = edge_importance[edge_importance["forecast_max_load_rate"] > 1.0].copy()
    for row in overload_edges.itertuples():
        if row.origin in site_info.index:
            add_line(row.origin, row.origin, NEW_SITE, "to_new_site", "overload_path")
        if row.dest in site_info.index:
            add_line(row.dest, NEW_SITE, row.dest, "from_new_site", "overload_path")

    return pd.DataFrame(records)


def apply_new_site_diversion(
    pred: pd.DataFrame,
    edge_importance: pd.DataFrame,
    new_lines: pd.DataFrame,
    multiplier: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = pred.copy()
    if multiplier is not None:
        work["forecast_volume"] = work["forecast_volume"] * multiplier

    cap_map = {
        row.edge: float(row.new_line_capacity)
        for row in new_lines.itertuples()
    }
    selected_sites = set(new_lines["connected_existing_site"])
    important_edge_set = set(edge_importance.head(80)["edge"])

    adjusted_rows = []
    new_line_load: dict[tuple[pd.Timestamp, str], float] = {}
    new_site_daily_load: dict[pd.Timestamp, float] = {}

    for row in work.itertuples():
        volume = float(row.forecast_volume)
        diverted = 0.0
        if (
            row.origin in selected_sites
            and row.dest in selected_sites
            and row.edge in important_edge_set
            and volume > 0
        ):
            edge1 = f"{row.origin}->{NEW_SITE}"
            edge2 = f"{NEW_SITE}->{row.dest}"
            if edge1 in cap_map and edge2 in cap_map:
                spare1 = cap_map[edge1] - new_line_load.get((row.date, edge1), 0.0)
                spare2 = cap_map[edge2] - new_line_load.get((row.date, edge2), 0.0)
                site_spare = NEW_SITE_CAPACITY - new_site_daily_load.get(row.date, 0.0)
                planned = 0.20 * volume
                diverted = max(min(planned, spare1, spare2, site_spare / 2.0), 0.0)
                if diverted > 0:
                    new_line_load[(row.date, edge1)] = new_line_load.get((row.date, edge1), 0.0) + diverted
                    new_line_load[(row.date, edge2)] = new_line_load.get((row.date, edge2), 0.0) + diverted
                    new_site_daily_load[row.date] = new_site_daily_load.get(row.date, 0.0) + 2.0 * diverted

        adjusted_rows.append(
            {
                "date": row.date,
                "origin": row.origin,
                "dest": row.dest,
                "edge": row.edge,
                "base_volume": volume,
                "diverted_to_new_site": diverted,
                "adjusted_volume": volume - diverted,
                "line_type": "existing",
            }
        )

    for (date, edge_name), volume in new_line_load.items():
        origin, dest = edge_name.split("->")
        adjusted_rows.append(
            {
                "date": date,
                "origin": origin,
                "dest": dest,
                "edge": edge_name,
                "base_volume": 0.0,
                "diverted_to_new_site": 0.0,
                "adjusted_volume": volume,
                "line_type": "new",
            }
        )

    site_load_df = pd.DataFrame(
        [
            {"date": date, "site": NEW_SITE, "new_site_load": load, "new_site_capacity": NEW_SITE_CAPACITY}
            for date, load in new_site_daily_load.items()
        ]
    )
    return pd.DataFrame(adjusted_rows), site_load_df


def robustness_metrics(adjusted: pd.DataFrame, edge_importance: pd.DataFrame, new_lines: pd.DataFrame) -> dict:
    cap_existing = edge_importance.set_index("edge")["edge_capacity"].to_dict()
    cap_new = new_lines.set_index("edge")["new_line_capacity"].to_dict()
    capacity = {**cap_existing, **cap_new}

    active = adjusted[adjusted["adjusted_volume"] > 0].copy()
    active["capacity"] = active["edge"].map(capacity)
    active = active[active["capacity"].notna() & (active["capacity"] > 0)].copy()
    active["load_rate"] = active["adjusted_volume"] / active["capacity"]
    overload = active[active["load_rate"] > 1.0]
    return {
        "edge_overload_rows": int(len(overload)),
        "edge_overload_total_amount": float((overload["adjusted_volume"] - overload["capacity"]).sum()),
        "edge_load_rate_std": float(active["load_rate"].std(ddof=0)),
        "edge_load_rate_cv": float(active["load_rate"].std(ddof=0) / (active["load_rate"].mean() + 1e-9)),
        "active_edge_day_rows": int(len(active)),
    }


def run_robustness(pred: pd.DataFrame, edge: pd.DataFrame, new_lines: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    records = []
    base_adjusted = pred.rename(columns={"forecast_volume": "adjusted_volume"}).copy()
    base_adjusted["base_volume"] = base_adjusted["adjusted_volume"]
    base_adjusted["diverted_to_new_site"] = 0.0
    base_adjusted["line_type"] = "existing"

    for scenario, sigma in [("base", 0.0), ("random_10pct", 0.10), ("random_15pct", 0.15)]:
        runs = 1 if sigma == 0 else MONTE_CARLO_RUNS
        for run in range(runs):
            if sigma == 0:
                multiplier = None
                before = base_adjusted
            else:
                multiplier = np.clip(rng.normal(1.0, sigma, len(pred)), 0.70, 1.35)
                before = base_adjusted.copy()
                before["adjusted_volume"] = pred["forecast_volume"].to_numpy() * multiplier

            after, new_site_load = apply_new_site_diversion(pred, edge, new_lines, multiplier=multiplier)
            before_metric = robustness_metrics(before, edge, new_lines)
            after_metric = robustness_metrics(after, edge, new_lines)
            records.append(
                {
                    "scenario": scenario,
                    "run": run,
                    "before_edge_overload_rows": before_metric["edge_overload_rows"],
                    "after_edge_overload_rows": after_metric["edge_overload_rows"],
                    "before_edge_overload_total_amount": before_metric["edge_overload_total_amount"],
                    "after_edge_overload_total_amount": after_metric["edge_overload_total_amount"],
                    "before_edge_load_rate_std": before_metric["edge_load_rate_std"],
                    "after_edge_load_rate_std": after_metric["edge_load_rate_std"],
                    "before_edge_load_rate_cv": before_metric["edge_load_rate_cv"],
                    "after_edge_load_rate_cv": after_metric["edge_load_rate_cv"],
                    "new_site_max_load": float(new_site_load["new_site_load"].max()) if len(new_site_load) else 0.0,
                    "new_site_capacity": NEW_SITE_CAPACITY,
                    "new_site_max_load_rate": float(new_site_load["new_site_load"].max() / NEW_SITE_CAPACITY) if len(new_site_load) else 0.0,
                }
            )
    return pd.DataFrame(records)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    pred, site, edge = load_inputs()
    selected_sites = choose_connected_sites(site, edge)
    selected_sites = add_site_roles(selected_sites, pred)
    new_lines = design_new_lines(selected_sites, pred, edge)
    adjusted, new_site_load = apply_new_site_diversion(pred, edge, new_lines)
    robustness = run_robustness(pred, edge, new_lines)
    robustness_summary = (
        robustness.groupby("scenario", as_index=False)
        .agg(
            runs=("run", "count"),
            before_edge_overload_rows=("before_edge_overload_rows", "mean"),
            after_edge_overload_rows=("after_edge_overload_rows", "mean"),
            before_edge_overload_total_amount=("before_edge_overload_total_amount", "mean"),
            after_edge_overload_total_amount=("after_edge_overload_total_amount", "mean"),
            before_edge_load_rate_std=("before_edge_load_rate_std", "mean"),
            after_edge_load_rate_std=("after_edge_load_rate_std", "mean"),
            before_edge_load_rate_cv=("before_edge_load_rate_cv", "mean"),
            after_edge_load_rate_cv=("after_edge_load_rate_cv", "mean"),
            new_site_max_load=("new_site_max_load", "mean"),
            new_site_max_load_rate=("new_site_max_load_rate", "mean"),
        )
    )

    selected_sites.to_csv(RESULT_DIR / "problem4_new_site_connected_sites.csv", index=False, encoding="utf-8-sig")
    new_lines.to_csv(RESULT_DIR / "problem4_new_site_lines.csv", index=False, encoding="utf-8-sig")
    adjusted.to_csv(RESULT_DIR / "problem4_new_site_adjusted_forecast_lines.csv", index=False, encoding="utf-8-sig")
    new_site_load.to_csv(RESULT_DIR / "problem4_new_site_daily_load.csv", index=False, encoding="utf-8-sig")
    robustness.to_csv(RESULT_DIR / "problem4_new_site_robustness_runs.csv", index=False, encoding="utf-8-sig")
    robustness_summary.to_csv(RESULT_DIR / "problem4_new_site_robustness_summary.csv", index=False, encoding="utf-8-sig")

    print("Connected sites:")
    print(
        selected_sites[
            [
                "selection_order",
                "site",
                "importance_score",
                "forecast_daily_max",
                "inbound_share",
                "outbound_share",
                "site_role",
                "selection_reason",
            ]
        ]
        .round(6)
        .to_string(index=False)
    )
    print("\nNew lines:")
    print(new_lines[["edge", "new_line_capacity", "selection_reason"]].to_string(index=False))
    print("\nRobustness summary:")
    print(robustness_summary.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
