from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ============================================================
# 1. Paths and global settings
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "paper_skill_materials" / "raw_data" / "history_volume_data.xlsx"
OLD_FORECAST_PATH = BASE_DIR / "paper_skill_materials" / "q1" / "results" / "final_forecast_all_edges.csv"

OUT_DIR = BASE_DIR / "q1_revised"
CODE_DIR = OUT_DIR / "code"
RESULT_DIR = OUT_DIR / "results"
FIGURE_DIR = OUT_DIR / "figures"

SPRING_FESTIVAL = {
    2021: pd.Timestamp("2021-02-12"),
    2022: pd.Timestamp("2022-02-01"),
    2023: pd.Timestamp("2023-01-22"),
}

TARGET_EDGES = [("DC14", "DC10"), ("DC20", "DC35"), ("DC25", "DC62")]
LAGS = [1, 2, 3, 7, 14, 28, 365]
ROLL_WINDOWS = [7, 14, 28, 56]


# ============================================================
# 2. Data loading and complete panel construction
# ============================================================

def load_history() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH)
    df = df.rename(columns={df.columns[0]: "origin", df.columns[1]: "dest", df.columns[2]: "date", df.columns[3]: "volume"})
    df["date"] = pd.to_datetime(df["date"])
    df["origin"] = df["origin"].astype(str)
    df["dest"] = df["dest"].astype(str)
    df["volume"] = df["volume"].astype(float)
    df["edge"] = df["origin"] + "->" + df["dest"]
    return df[["origin", "dest", "edge", "date", "volume"]]


def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    edges = df[["origin", "dest", "edge"]].drop_duplicates().sort_values("edge")
    dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    index = pd.MultiIndex.from_product([edges["edge"], dates], names=["edge", "date"])

    panel = (
        df.set_index(["edge", "date"])["volume"]
        .reindex(index, fill_value=0)
        .rename("volume")
        .reset_index()
        .merge(edges, on="edge", how="left")
    )
    panel = panel[["origin", "dest", "edge", "date", "volume"]]
    return panel.sort_values(["edge", "date"]).reset_index(drop=True)


def make_encoders(panel: pd.DataFrame) -> dict[str, dict[str, int]]:
    sites = sorted(set(panel["origin"]).union(panel["dest"]))
    return {
        "edge": {v: i for i, v in enumerate(sorted(panel["edge"].unique()))},
        "site": {v: i for i, v in enumerate(sites)},
    }


# ============================================================
# 3. Anomaly detection and historical correction
# ============================================================

def detect_long_shutdown_edges(panel: pd.DataFrame) -> tuple[pd.DataFrame, set[str], set[str]]:
    yearly_edge = (
        panel.assign(year=panel["date"].dt.year)
        .groupby(["edge", "year"])["volume"]
        .sum()
        .unstack("year")
        .fillna(0)
    )
    yearly_edge["ratio_2022_2021"] = yearly_edge.get(2022, 0) / (yearly_edge.get(2021, 0) + 1e-9)
    long_edges = yearly_edge[(yearly_edge.get(2021, 0) >= 500_000) & (yearly_edge["ratio_2022_2021"] < 0.05)].copy()
    long_edge_set = set(long_edges.index)

    site_rows = pd.concat(
        [
            panel[["date", "origin", "volume"]].rename(columns={"origin": "site"}),
            panel[["date", "dest", "volume"]].rename(columns={"dest": "site"}),
        ],
        ignore_index=True,
    )
    yearly_site = (
        site_rows.assign(year=site_rows["date"].dt.year)
        .groupby(["site", "year"])["volume"]
        .sum()
        .unstack("year")
        .fillna(0)
    )
    yearly_site["ratio_2022_2021"] = yearly_site.get(2022, 0) / (yearly_site.get(2021, 0) + 1e-9)
    long_sites = yearly_site[(yearly_site.get(2021, 0) >= 1_000_000) & (yearly_site["ratio_2022_2021"] < 0.05)].copy()
    long_site_set = set(long_sites.index)

    report = long_edges.reset_index().rename(columns={2021: "volume_2021", 2022: "volume_2022"})
    report["origin"] = report["edge"].str.split("->").str[0]
    report["dest"] = report["edge"].str.split("->").str[1]
    report["reason"] = "long_shutdown_edge"
    return report[["edge", "origin", "dest", "volume_2021", "volume_2022", "ratio_2022_2021", "reason"]], long_edge_set, long_site_set


def detect_short_month_anomalies(panel: pd.DataFrame) -> pd.DataFrame:
    monthly = (
        panel.assign(month=panel["date"].dt.to_period("M").dt.to_timestamp())
        .groupby(["month", "edge"], as_index=False)["volume"]
        .sum()
    )
    wide = monthly.pivot(index="month", columns="edge", values="volume").fillna(0).sort_index()
    rows: list[dict] = []
    dates = list(wide.index)

    for edge in wide.columns:
        series = wide[edge]
        for idx in range(2, len(series) - 2):
            current = float(series.iloc[idx])
            previous = float(series.iloc[idx - 1])
            next_value = float(series.iloc[idx + 1])
            baseline = float(np.median([series.iloc[idx - 2], series.iloc[idx - 1], series.iloc[idx + 1], series.iloc[idx + 2]]))
            if baseline >= 50_000 and current <= 0.15 * baseline and previous >= 0.35 * baseline and next_value >= 0.35 * baseline:
                rows.append(
                    {
                        "edge": edge,
                        "month": dates[idx],
                        "current_volume": current,
                        "local_baseline": baseline,
                        "current_to_baseline": current / baseline if baseline else 0,
                        "reason": "short_month_drop",
                    }
                )

    return pd.DataFrame(rows)


def replacement_values_for_month(panel: pd.DataFrame, edge: str, month: pd.Timestamp, baseline_total: float) -> pd.Series:
    dates = pd.date_range(month, month + pd.offsets.MonthEnd(0), freq="D")
    prev_month = month - pd.DateOffset(months=1)
    next_month = month + pd.DateOffset(months=1)
    edge_series = panel[panel["edge"] == edge].set_index("date")["volume"]

    values = []
    for date in dates:
        candidates = []
        for ref_month in [prev_month, next_month]:
            last_day = (ref_month + pd.offsets.MonthEnd(0)).day
            ref_day = min(date.day, last_day)
            ref_date = pd.Timestamp(year=ref_month.year, month=ref_month.month, day=ref_day)
            if ref_date in edge_series.index:
                candidates.append(float(edge_series.loc[ref_date]))
        values.append(float(np.mean(candidates)) if candidates else 0.0)

    replacement = pd.Series(values, index=dates)
    if replacement.sum() <= 0:
        replacement[:] = baseline_total / len(replacement)
    else:
        replacement *= baseline_total / replacement.sum()
    return replacement


def correct_short_months(panel: pd.DataFrame, short_anomalies: pd.DataFrame) -> pd.DataFrame:
    corrected = panel.copy()
    corrected["is_corrected_short_anomaly"] = False

    for _, row in short_anomalies.iterrows():
        edge = row["edge"]
        month = pd.Timestamp(row["month"])
        replacement = replacement_values_for_month(corrected, edge, month, float(row["local_baseline"]))
        mask = (corrected["edge"] == edge) & (corrected["date"].isin(replacement.index))
        corrected.loc[mask, "volume"] = corrected.loc[mask, "date"].map(replacement).to_numpy()
        corrected.loc[mask, "is_corrected_short_anomaly"] = True

    return corrected


def spring_delta(date: pd.Timestamp) -> int:
    return int((date - SPRING_FESTIVAL[int(date.year)]).days)


def spring_date(year: int, delta: int) -> pd.Timestamp:
    return SPRING_FESTIVAL[year] + pd.Timedelta(days=int(delta))


def stable_spring_growth_factor(panel: pd.DataFrame, excluded_edges: set[str]) -> float:
    def total_for_year(year: int) -> float:
        start = spring_date(year, -21)
        end = spring_date(year, 9)
        mask = panel["date"].between(start, end) & ~panel["edge"].isin(excluded_edges)
        return float(panel.loc[mask, "volume"].sum())

    total_2021 = total_for_year(2021)
    total_2022 = total_for_year(2022)
    factor = total_2022 / total_2021 if total_2021 > 0 else 1.0
    return float(np.clip(factor, 0.8, 1.3))


def long_shutdown_source_date(date: pd.Timestamp) -> pd.Timestamp:
    if abs(spring_delta(date)) <= 60:
        return spring_date(2021, spring_delta(date))
    return date - pd.DateOffset(years=1)


def correct_long_shutdown_history(panel: pd.DataFrame, original_panel: pd.DataFrame, long_edges: set[str], factor: float) -> pd.DataFrame:
    corrected = panel.copy()
    corrected["is_corrected_long_shutdown"] = False
    history_lookup = original_panel.set_index(["edge", "date"])["volume"]

    mask_2022 = corrected["edge"].isin(long_edges) & (corrected["date"].dt.year == 2022)
    for idx, row in corrected.loc[mask_2022].iterrows():
        source_date = long_shutdown_source_date(pd.Timestamp(row["date"]))
        base_value = float(history_lookup.get((row["edge"], source_date), 0.0))
        corrected.loc[idx, "volume"] = base_value * factor
        corrected.loc[idx, "is_corrected_long_shutdown"] = True

    return corrected


def correct_long_shutdown_forecast(forecast: pd.DataFrame, panel: pd.DataFrame, long_edges: set[str], factor: float) -> pd.DataFrame:
    corrected = forecast.copy()
    history_lookup = panel.set_index(["edge", "date"])["volume"]

    mask = corrected["edge"].isin(long_edges)
    corrected["is_long_shutdown_corrected"] = False
    for idx, row in corrected.loc[mask].iterrows():
        delta = spring_delta(pd.Timestamp(row["date"]))
        source_date = spring_date(2021, delta)
        base_value = float(history_lookup.get((row["edge"], source_date), 0.0))
        corrected.loc[idx, "forecast_volume"] = round(base_value * factor)
        corrected.loc[idx, "is_long_shutdown_corrected"] = True

    return corrected


# ============================================================
# 4. Feature engineering
# ============================================================

def add_basic_features(frame: pd.DataFrame, encoders: dict[str, dict[str, int]]) -> pd.DataFrame:
    out = frame.copy()
    dt = out["date"]

    out["edge_id"] = out["edge"].map(encoders["edge"]).astype("int32")
    out["origin_id"] = out["origin"].map(encoders["site"]).astype("int16")
    out["dest_id"] = out["dest"].map(encoders["site"]).astype("int16")

    out["month"] = dt.dt.month.astype("int8")
    out["day"] = dt.dt.day.astype("int8")
    out["dow"] = dt.dt.dayofweek.astype("int8")
    out["week"] = dt.dt.isocalendar().week.astype("int8")
    out["dayofyear"] = dt.dt.dayofyear.astype("int16")
    out["is_weekend"] = (out["dow"] >= 5).astype("int8")
    out["is_month_start"] = dt.dt.is_month_start.astype("int8")
    out["is_month_end"] = dt.dt.is_month_end.astype("int8")

    out["spring_delta"] = dt.map(spring_delta).astype("int16")
    out["abs_spring_delta"] = out["spring_delta"].abs().astype("int16")
    out["is_spring_window"] = out["spring_delta"].between(-15, 10).astype("int8")
    out["is_before_spring"] = out["spring_delta"].between(-20, -1).astype("int8")
    out["is_after_spring"] = out["spring_delta"].between(0, 15).astype("int8")
    return out


def add_history_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["edge", "date"]).copy()
    grouped = out.groupby("edge", sort=False)["volume"]

    for lag in LAGS:
        out[f"lag_{lag}"] = grouped.shift(lag)

    shifted = grouped.shift(1)
    for window in ROLL_WINDOWS:
        rolling = shifted.groupby(out["edge"], sort=False).rolling(window, min_periods=1)
        out[f"roll_mean_{window}"] = rolling.mean().reset_index(level=0, drop=True)
        out[f"roll_max_{window}"] = rolling.max().reset_index(level=0, drop=True)

    out["nonzero_last_28"] = (
        (shifted > 0)
        .astype(float)
        .groupby(out["edge"], sort=False)
        .rolling(28, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    return out


def add_static_features(frame: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    edge_stats = history.groupby("edge")["volume"].agg(
        edge_mean="mean",
        edge_median="median",
        edge_max="max",
        edge_nonzero_ratio=lambda s: float((s > 0).mean()),
    )
    origin_stats = history.groupby("origin")["volume"].agg(origin_mean="mean", origin_max="max")
    dest_stats = history.groupby("dest")["volume"].agg(dest_mean="mean", dest_max="max")

    out = out.merge(edge_stats, on="edge", how="left")
    out = out.merge(origin_stats, on="origin", how="left")
    out = out.merge(dest_stats, on="dest", how="left")
    fill_cols = [
        "edge_mean",
        "edge_median",
        "edge_max",
        "edge_nonzero_ratio",
        "origin_mean",
        "origin_max",
        "dest_mean",
        "dest_max",
    ]
    out[fill_cols] = out[fill_cols].fillna(0)
    return out


def feature_columns() -> list[str]:
    cols = [
        "edge_id",
        "origin_id",
        "dest_id",
        "month",
        "day",
        "dow",
        "week",
        "dayofyear",
        "is_weekend",
        "is_month_start",
        "is_month_end",
        "spring_delta",
        "abs_spring_delta",
        "is_spring_window",
        "is_before_spring",
        "is_after_spring",
        "edge_mean",
        "edge_median",
        "edge_max",
        "edge_nonzero_ratio",
        "origin_mean",
        "origin_max",
        "dest_mean",
        "dest_max",
        "nonzero_last_28",
    ]
    cols.extend([f"lag_{lag}" for lag in LAGS])
    for window in ROLL_WINDOWS:
        cols.append(f"roll_mean_{window}")
        cols.append(f"roll_max_{window}")
    return cols


def build_training_frame(panel: pd.DataFrame, encoders: dict[str, dict[str, int]], train_end: str) -> pd.DataFrame:
    train_panel = panel[panel["date"] <= pd.Timestamp(train_end)].copy()
    feat = add_history_features(train_panel)
    feat = add_basic_features(feat, encoders)
    feat = add_static_features(feat, train_panel)
    feat = feat[feat["date"] >= feat["date"].min() + pd.Timedelta(days=28)].copy()
    return feat


# ============================================================
# 5. LightGBM training and recursive forecast
# ============================================================

def train_model(train_feat: pd.DataFrame) -> lgb.Booster:
    features = feature_columns()
    train_feat = train_feat.copy()
    train_feat[features] = train_feat[features].fillna(0)

    valid_start = train_feat["date"].max() - pd.Timedelta(days=61)
    train_idx = train_feat["date"] < valid_start
    valid_idx = ~train_idx

    dtrain = lgb.Dataset(
        train_feat.loc[train_idx, features],
        label=np.log1p(train_feat.loc[train_idx, "volume"]),
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        free_raw_data=False,
    )
    dvalid = lgb.Dataset(
        train_feat.loc[valid_idx, features],
        label=np.log1p(train_feat.loc[valid_idx, "volume"]),
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        reference=dtrain,
        free_raw_data=False,
    )
    params = {
        "objective": "regression_l1",
        "metric": ["l1", "rmse"],
        "learning_rate": 0.045,
        "num_leaves": 96,
        "min_data_in_leaf": 80,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "lambda_l1": 0.05,
        "lambda_l2": 0.2,
        "verbosity": -1,
        "seed": 2026,
        "num_threads": 0,
    }
    return lgb.train(
        params,
        dtrain,
        valid_sets=[dvalid],
        num_boost_round=1000,
        callbacks=[lgb.early_stopping(80), lgb.log_evaluation(100)],
    )


def make_future_rows(edges: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    out = edges.copy()
    out["date"] = date
    out["volume"] = np.nan
    return out[["origin", "dest", "edge", "date", "volume"]]


def forecast_recursive(
    model: lgb.Booster,
    history_panel: pd.DataFrame,
    encoders: dict[str, dict[str, int]],
    start: str,
    end: str,
) -> pd.DataFrame:
    features = feature_columns()
    edges = history_panel[["origin", "dest", "edge"]].drop_duplicates().sort_values("edge")
    working = history_panel.copy()
    preds = []

    for date in pd.date_range(start, end, freq="D"):
        one_day = make_future_rows(edges, date)
        temp = pd.concat([working, one_day], ignore_index=True)
        temp_feat = add_history_features(temp)
        future_feat = temp_feat[temp_feat["date"] == date].copy()
        future_feat = add_basic_features(future_feat, encoders)
        future_feat = add_static_features(future_feat, working)
        future_feat[features] = future_feat[features].fillna(0)

        pred = np.expm1(model.predict(future_feat[features], num_iteration=model.best_iteration))
        pred = np.maximum(pred, 0)
        edge_caps = future_feat["edge_max"].to_numpy()
        pred = np.minimum(pred, np.where(edge_caps > 0, edge_caps * 1.2, pred))

        future_feat["forecast_volume"] = np.rint(pred).astype(int)
        preds.append(future_feat[["origin", "dest", "edge", "date", "forecast_volume"]])

        append_rows = future_feat[["origin", "dest", "edge", "date"]].copy()
        append_rows["volume"] = future_feat["forecast_volume"].astype(float).to_numpy()
        working = pd.concat([working, append_rows], ignore_index=True)

    return pd.concat(preds, ignore_index=True)


# ============================================================
# 6. Calibration, comparison and exports
# ============================================================

def spring_window_total(panel: pd.DataFrame, year: int, low: int = -21, high: int = 9) -> int:
    start = spring_date(year, low)
    end = spring_date(year, high)
    return int(round(panel[panel["date"].between(start, end)]["volume"].sum()))


def calibrate_total(corrected_panel: pd.DataFrame, pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    total_2021 = spring_window_total(corrected_panel, 2021)
    total_2022 = spring_window_total(corrected_panel, 2022)
    target_total = 0.35 * total_2021 + 0.65 * total_2022
    raw_total = float(pred["forecast_volume"].sum())
    calibration_factor = target_total / raw_total if raw_total > 0 else 1.0

    final = pred.copy()
    final["raw_forecast_volume"] = final["forecast_volume"].astype(int)
    final["forecast_volume"] = np.rint(final["forecast_volume"] * calibration_factor).astype(int)
    diff = int(round(target_total)) - int(final["forecast_volume"].sum())
    if diff != 0:
        idx = final["forecast_volume"].idxmax()
        final.loc[idx, "forecast_volume"] += diff

    summary = pd.DataFrame(
        [
            {
                "corrected_2021_spring_window_total": total_2021,
                "corrected_2022_spring_window_total": total_2022,
                "target_total_weighted_035_065": int(round(target_total)),
                "raw_revised_total": int(raw_total),
                "calibration_factor": calibration_factor,
                "final_revised_total": int(final["forecast_volume"].sum()),
            }
        ]
    )
    return final, summary


def load_old_forecast() -> pd.DataFrame:
    old = pd.read_csv(OLD_FORECAST_PATH)
    old = old.rename(
        columns={
            "场地1": "origin",
            "场地2": "dest",
            "日期": "date",
            "预测货量": "old_forecast_volume",
            "原LightGBM预测货量": "old_raw_forecast_volume",
        }
    )
    old["date"] = pd.to_datetime(old["date"])
    old["edge"] = old["origin"].astype(str) + "->" + old["dest"].astype(str)
    return old[["origin", "dest", "edge", "date", "old_forecast_volume", "old_raw_forecast_volume"]]


def compare_with_old(final: pd.DataFrame, long_sites: set[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    old = load_old_forecast()
    merged = old.merge(
        final[["origin", "dest", "edge", "date", "forecast_volume", "raw_forecast_volume", "is_long_shutdown_corrected"]],
        on=["origin", "dest", "edge", "date"],
        how="inner",
    )
    merged["diff"] = merged["forecast_volume"] - merged["old_forecast_volume"]

    daily = merged.groupby("date", as_index=False).agg(
        old_total=("old_forecast_volume", "sum"),
        revised_total=("forecast_volume", "sum"),
        difference=("diff", "sum"),
    )

    target = (
        merged[merged[["origin", "dest"]].apply(tuple, axis=1).isin(TARGET_EDGES)]
        .groupby("edge", as_index=False)
        .agg(old_total=("old_forecast_volume", "sum"), revised_total=("forecast_volume", "sum"), difference=("diff", "sum"))
    )

    important_sites = sorted(set(long_sites).union({"DC9", "DC3", "DC5", "DC27"}))
    site_rows = []
    for site in important_sites:
        m = merged[(merged["origin"] == site) | (merged["dest"] == site)]
        site_rows.append(
            {
                "site": site,
                "old_total": int(m["old_forecast_volume"].sum()),
                "revised_total": int(m["forecast_volume"].sum()),
                "difference": int(m["diff"].sum()),
                "corrected_edge_count": int(m[m["is_long_shutdown_corrected"]]["edge"].nunique()),
            }
        )
    site_compare = pd.DataFrame(site_rows).sort_values("difference", ascending=False)

    edge_compare = (
        merged.groupby(["edge", "origin", "dest"], as_index=False)
        .agg(old_total=("old_forecast_volume", "sum"), revised_total=("forecast_volume", "sum"), difference=("diff", "sum"))
    )
    edge_compare["abs_difference"] = edge_compare["difference"].abs()
    edge_compare = edge_compare.sort_values("abs_difference", ascending=False)
    return daily, target, site_compare, edge_compare


def export_final(final: pd.DataFrame, summary: pd.DataFrame) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    final.to_csv(RESULT_DIR / "revised_forecast_all_edges.csv", index=False, encoding="utf-8-sig")
    final.groupby("date", as_index=False).agg(
        forecast_volume=("forecast_volume", "sum"),
        raw_forecast_volume=("raw_forecast_volume", "sum"),
    ).to_csv(RESULT_DIR / "revised_forecast_daily_total.csv", index=False, encoding="utf-8-sig")
    final[final[["origin", "dest"]].apply(tuple, axis=1).isin(TARGET_EDGES)].to_csv(
        RESULT_DIR / "revised_forecast_target_edges.csv", index=False, encoding="utf-8-sig"
    )
    summary.to_csv(RESULT_DIR / "revised_calibration_summary.csv", index=False, encoding="utf-8-sig")


def export_comparisons(
    short_anomalies: pd.DataFrame,
    long_report: pd.DataFrame,
    daily: pd.DataFrame,
    target: pd.DataFrame,
    site_compare: pd.DataFrame,
    edge_compare: pd.DataFrame,
) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    short_anomalies.to_csv(RESULT_DIR / "detected_short_month_anomalies.csv", index=False, encoding="utf-8-sig")
    long_report.to_csv(RESULT_DIR / "detected_long_shutdown_edges.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(RESULT_DIR / "comparison_daily_total.csv", index=False, encoding="utf-8-sig")
    target.to_csv(RESULT_DIR / "comparison_target_edges.csv", index=False, encoding="utf-8-sig")
    site_compare.to_csv(RESULT_DIR / "comparison_key_sites.csv", index=False, encoding="utf-8-sig")
    edge_compare.to_csv(RESULT_DIR / "comparison_edge_total_top_changes.csv", index=False, encoding="utf-8-sig")


# ============================================================
# 7. Visualization
# ============================================================

def setup_font() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def plot_comparisons(daily: pd.DataFrame, site_compare: pd.DataFrame) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    setup_font()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(daily["date"], daily["old_total"], label="Before correction", linewidth=2)
    ax.plot(daily["date"], daily["revised_total"], label="After correction", linewidth=2)
    ax.set_title("Question 1 Daily Forecast Total: Before vs After Correction")
    ax.set_xlabel("Date")
    ax.set_ylabel("Forecast volume")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "daily_total_before_after.png", dpi=220)
    plt.close(fig)

    top = site_compare.head(8).sort_values("revised_total")
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(top))
    width = 0.38
    ax.bar(x - width / 2, top["old_total"], width, label="Before correction")
    ax.bar(x + width / 2, top["revised_total"], width, label="After correction")
    ax.set_xticks(x)
    ax.set_xticklabels(top["site"])
    ax.set_title("Key Site Forecast Total: Before vs After Correction")
    ax.set_xlabel("Site")
    ax.set_ylabel("Forecast volume")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "key_sites_before_after.png", dpi=220)
    plt.close(fig)


# ============================================================
# 8. Main workflow
# ============================================================

def main() -> None:
    print("[1/7] Load history and build complete panel")
    history = load_history()
    panel = build_panel(history)
    encoders = make_encoders(panel)
    print(f"Panel rows: {len(panel)}, edges: {panel['edge'].nunique()}, dates: {panel['date'].nunique()}")

    print("[2/7] Detect short-month and long-shutdown anomalies")
    long_report, long_edges, long_sites = detect_long_shutdown_edges(panel)
    short_anomalies = detect_short_month_anomalies(panel)
    print(f"Short-month anomalies: {len(short_anomalies)}")
    print(f"Long-shutdown edges: {len(long_edges)}, sites: {', '.join(sorted(long_sites))}")

    print("[3/7] Correct short-month historical anomalies")
    corrected_panel = correct_short_months(panel, short_anomalies)
    growth_factor = stable_spring_growth_factor(corrected_panel, long_edges)
    corrected_panel = correct_long_shutdown_history(corrected_panel, panel, long_edges, growth_factor)
    print(f"Stable spring-window growth factor for long-shutdown edges: {growth_factor:.6f}")

    print("[4/7] Train LightGBM on corrected history")
    train_full = build_training_frame(corrected_panel, encoders, "2022-12-31")
    model_full = train_model(train_full)

    print("[5/7] Forecast 2023-01 recursively and correct long-shutdown edges")
    raw_forecast = forecast_recursive(model_full, corrected_panel, encoders, "2023-01-01", "2023-01-31")
    raw_forecast = correct_long_shutdown_forecast(raw_forecast, panel, long_edges, growth_factor)

    print("[6/7] Calibrate total volume using corrected spring windows")
    final, summary = calibrate_total(corrected_panel, raw_forecast)
    print(summary.round(6).to_string(index=False))

    print("[7/7] Export comparisons")
    export_final(final, summary)
    daily, target, site_compare, edge_compare = compare_with_old(final, long_sites)
    export_comparisons(short_anomalies, long_report, daily, target, site_compare, edge_compare)
    plot_comparisons(daily, site_compare)

    print("\nTarget edge comparison:")
    print(target.to_string(index=False))
    print("\nKey site comparison:")
    print(site_compare.to_string(index=False))
    print("\nTop changed edges:")
    print(edge_compare.head(15).to_string(index=False))
    print(f"\nOutput directory: {RESULT_DIR}")


if __name__ == "__main__":
    main()

