from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
HISTORY_PATH = BASE_DIR / "paper_skill_materials" / "raw_data" / "history_volume_data.xlsx"
PRED_PATH = BASE_DIR / "q1_revised" / "results" / "revised_forecast_all_edges.csv"
RESULT_DIR = BASE_DIR / "q4_analysis" / "results"

HIGH_LOAD_THRESHOLD = 0.8
EPS = 1e-9


def pct_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    return series.rank(pct=True, ascending=ascending, method="average").fillna(0.0)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    history = pd.read_excel(HISTORY_PATH)
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
    pred["forecast_volume"] = pred["forecast_volume"].astype(float)
    pred["edge"] = pred["origin"] + "->" + pred["dest"]
    return history, pred


def build_site_importance(history: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    sites = sorted(set(history["origin"]).union(history["dest"]))

    hist_site_rows = pd.concat(
        [
            history[["date", "origin", "volume"]].rename(columns={"origin": "site", "volume": "site_volume"}),
            history[["date", "dest", "volume"]].rename(columns={"dest": "site", "volume": "site_volume"}),
        ],
        ignore_index=True,
    )
    hist_daily = hist_site_rows.groupby(["date", "site"], as_index=False)["site_volume"].sum()
    site_capacity = hist_daily.groupby("site", as_index=False)["site_volume"].max().rename(
        columns={"site_volume": "site_capacity"}
    )
    hist_total = hist_daily.groupby("site", as_index=False)["site_volume"].sum().rename(
        columns={"site_volume": "historical_total_throughput"}
    )

    pred_site_rows = pd.concat(
        [
            pred[["date", "origin", "forecast_volume"]].rename(columns={"origin": "site", "forecast_volume": "site_volume"}),
            pred[["date", "dest", "forecast_volume"]].rename(columns={"dest": "site", "forecast_volume": "site_volume"}),
        ],
        ignore_index=True,
    )
    pred_daily = pred_site_rows.groupby(["date", "site"], as_index=False)["site_volume"].sum()
    pred_stats = (
        pred_daily.groupby("site")["site_volume"]
        .agg(
            forecast_total_throughput="sum",
            forecast_daily_mean="mean",
            forecast_daily_max="max",
            forecast_daily_std=lambda s: s.std(ddof=0),
        )
        .reset_index()
    )

    in_degree = history.groupby("dest")["origin"].nunique().rename("in_degree")
    out_degree = history.groupby("origin")["dest"].nunique().rename("out_degree")
    degree = (
        pd.DataFrame({"site": sites})
        .merge(in_degree, left_on="site", right_index=True, how="left")
        .merge(out_degree, left_on="site", right_index=True, how="left")
        .fillna(0)
    )
    degree["total_degree"] = degree["in_degree"] + degree["out_degree"]

    site = (
        pd.DataFrame({"site": sites})
        .merge(hist_total, on="site", how="left")
        .merge(site_capacity, on="site", how="left")
        .merge(pred_stats, on="site", how="left")
        .merge(degree, on="site", how="left")
        .fillna(0)
    )
    site["forecast_max_load_rate"] = site["forecast_daily_max"] / (site["site_capacity"] + EPS)
    pred_daily = pred_daily.merge(site[["site", "site_capacity"]], on="site", how="left")
    pred_daily["load_rate"] = pred_daily["site_volume"] / (pred_daily["site_capacity"] + EPS)
    high_load = (
        pred_daily.assign(high_load=lambda df: df["load_rate"] >= HIGH_LOAD_THRESHOLD)
        .groupby("site", as_index=False)["high_load"]
        .mean()
        .rename(columns={"high_load": "high_load_day_ratio"})
    )
    site = site.merge(high_load, on="site", how="left").fillna({"high_load_day_ratio": 0})
    site["forecast_throughput_cv"] = site["forecast_daily_std"] / (site["forecast_daily_mean"] + EPS)
    site["direct_shutdown_affected_volume"] = site["forecast_total_throughput"]

    site["volume_score"] = 0.75 * pct_rank(site["forecast_total_throughput"]) + 0.25 * pct_rank(site["historical_total_throughput"])
    site["structure_score"] = pct_rank(site["total_degree"])
    site["volatility_score"] = pct_rank(site["forecast_throughput_cv"])
    site["failure_impact_score"] = pct_rank(site["direct_shutdown_affected_volume"])
    site["importance_score"] = (
        0.35 * site["volume_score"]
        + 0.25 * site["structure_score"]
        + 0.15 * site["volatility_score"]
        + 0.25 * site["failure_impact_score"]
    )
    return site.sort_values("importance_score", ascending=False).reset_index(drop=True)


def build_edge_importance(history: pd.DataFrame, pred: pd.DataFrame, site_importance: pd.DataFrame) -> pd.DataFrame:
    edge_capacity = (
        history.groupby(["origin", "dest", "edge"], as_index=False)["volume"]
        .max()
        .rename(columns={"volume": "edge_capacity"})
    )
    hist_total = (
        history.groupby(["origin", "dest", "edge"], as_index=False)["volume"]
        .sum()
        .rename(columns={"volume": "historical_total_volume"})
    )
    pred_stats = (
        pred.groupby(["origin", "dest", "edge"])["forecast_volume"]
        .agg(
            forecast_total_volume="sum",
            forecast_daily_mean="mean",
            forecast_daily_max="max",
            forecast_daily_std=lambda s: s.std(ddof=0),
        )
        .reset_index()
    )
    edge = (
        pred_stats.merge(hist_total, on=["origin", "dest", "edge"], how="left")
        .merge(edge_capacity, on=["origin", "dest", "edge"], how="left")
        .fillna(0)
    )
    edge["forecast_max_load_rate"] = edge["forecast_daily_max"] / (edge["edge_capacity"] + EPS)
    edge["forecast_volume_cv"] = edge["forecast_daily_std"] / (edge["forecast_daily_mean"] + EPS)

    pred_daily = pred.merge(edge[["edge", "edge_capacity"]], on="edge", how="left")
    pred_daily["load_rate"] = pred_daily["forecast_volume"] / (pred_daily["edge_capacity"] + EPS)
    high_load = (
        pred_daily.assign(high_load=lambda df: df["load_rate"] >= HIGH_LOAD_THRESHOLD)
        .groupby("edge", as_index=False)["high_load"]
        .mean()
        .rename(columns={"high_load": "high_load_day_ratio"})
    )
    edge = edge.merge(high_load, on="edge", how="left").fillna({"high_load_day_ratio": 0})

    cap_by_origin = edge_capacity.groupby("origin")["edge_capacity"].sum().rename("origin_total_capacity")
    cap_by_dest = edge_capacity.groupby("dest")["edge_capacity"].sum().rename("dest_total_capacity")
    edge = edge.merge(cap_by_origin, on="origin", how="left").merge(cap_by_dest, on="dest", how="left")
    edge["same_origin_alternative_capacity"] = edge["origin_total_capacity"] - edge["edge_capacity"]
    edge["same_dest_alternative_capacity"] = edge["dest_total_capacity"] - edge["edge_capacity"]
    edge["alternative_capacity_ratio"] = (
        edge["same_origin_alternative_capacity"] + edge["same_dest_alternative_capacity"]
    ) / (edge["edge_capacity"] + EPS)

    site_score = site_importance.set_index("site")["importance_score"]
    edge["origin_site_importance"] = edge["origin"].map(site_score).fillna(0)
    edge["dest_site_importance"] = edge["dest"].map(site_score).fillna(0)
    edge["endpoint_importance_score"] = 0.5 * edge["origin_site_importance"] + 0.5 * edge["dest_site_importance"]

    edge["volume_score"] = 0.75 * pct_rank(edge["forecast_total_volume"]) + 0.25 * pct_rank(edge["historical_total_volume"])
    edge["connection_score"] = pct_rank(edge["endpoint_importance_score"])
    edge["volatility_score"] = pct_rank(edge["forecast_volume_cv"])
    edge["substitution_risk_score"] = pct_rank(-edge["alternative_capacity_ratio"])
    edge["importance_score"] = (
        0.35 * edge["volume_score"]
        + 0.25 * edge["connection_score"]
        + 0.15 * edge["volatility_score"]
        + 0.25 * edge["substitution_risk_score"]
    )
    return edge.sort_values("importance_score", ascending=False).reset_index(drop=True)


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    history, pred = load_inputs()
    site = build_site_importance(history, pred)
    edge = build_edge_importance(history, pred, site)

    site.to_csv(RESULT_DIR / "problem4_site_core_importance.csv", index=False, encoding="utf-8-sig")
    edge.to_csv(RESULT_DIR / "problem4_edge_core_importance.csv", index=False, encoding="utf-8-sig")
    site.head(20).to_csv(RESULT_DIR / "problem4_site_core_importance_top20.csv", index=False, encoding="utf-8-sig")
    edge.head(30).to_csv(RESULT_DIR / "problem4_edge_core_importance_top30.csv", index=False, encoding="utf-8-sig")

    print("Top sites:")
    print(
        site[
            [
                "site",
                "importance_score",
                "forecast_total_throughput",
                "historical_total_throughput",
                "total_degree",
                "forecast_max_load_rate",
                "high_load_day_ratio",
                "forecast_throughput_cv",
            ]
        ]
        .head(15)
        .round(6)
        .to_string(index=False)
    )
    print("\nTop edges:")
    print(
        edge[
            [
                "edge",
                "importance_score",
                "forecast_total_volume",
                "historical_total_volume",
                "endpoint_importance_score",
                "forecast_max_load_rate",
                "high_load_day_ratio",
                "forecast_volume_cv",
                "alternative_capacity_ratio",
            ]
        ]
        .head(20)
        .round(6)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
