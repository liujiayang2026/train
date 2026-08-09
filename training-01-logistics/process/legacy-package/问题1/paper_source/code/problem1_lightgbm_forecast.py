from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = BASE_DIR / "原始资料" / "附件1：物流网络历史货量数据.xlsx"
RESULT_DIR = BASE_DIR / "问题1" / "results" / "experiments"

SPRING_FESTIVAL = {
    2021: pd.Timestamp("2021-02-12"),
    2022: pd.Timestamp("2022-02-01"),
    2023: pd.Timestamp("2023-01-22"),
}

TARGET_EDGES = [("DC14", "DC10"), ("DC20", "DC35"), ("DC25", "DC62")]
LAGS = [1, 2, 3, 7, 14, 28, 365]
ROLL_WINDOWS = [7, 14, 28, 56]


def load_data() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH)
    df["日期"] = pd.to_datetime(df["日期"])
    df["edge"] = df["场地1"].astype(str) + "->" + df["场地2"].astype(str)
    return df


def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    edges = df[["场地1", "场地2", "edge"]].drop_duplicates().sort_values("edge")
    dates = pd.date_range(df["日期"].min(), df["日期"].max(), freq="D")
    index = pd.MultiIndex.from_product([edges["edge"], dates], names=["edge", "日期"])
    panel = (
        df.set_index(["edge", "日期"])["货量"]
        .reindex(index, fill_value=0)
        .rename("货量")
        .reset_index()
        .merge(edges, on="edge", how="left")
    )
    return panel[["场地1", "场地2", "edge", "日期", "货量"]].sort_values(["edge", "日期"]).reset_index(drop=True)


def make_encoders(panel: pd.DataFrame) -> dict[str, dict[str, int]]:
    return {
        "edge": {v: i for i, v in enumerate(sorted(panel["edge"].unique()))},
        "site": {
            v: i
            for i, v in enumerate(
                sorted(set(panel["场地1"].unique()).union(set(panel["场地2"].unique())))
            )
        },
    }


def spring_delta(date: pd.Timestamp) -> int:
    return int((date - SPRING_FESTIVAL[int(date.year)]).days)


def add_basic_features(frame: pd.DataFrame, encoders: dict[str, dict[str, int]]) -> pd.DataFrame:
    out = frame.copy()
    dt = out["日期"]
    out["edge_id"] = out["edge"].map(encoders["edge"]).astype("int32")
    out["origin_id"] = out["场地1"].map(encoders["site"]).astype("int16")
    out["dest_id"] = out["场地2"].map(encoders["site"]).astype("int16")
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
    out = panel.sort_values(["edge", "日期"]).copy()
    grouped = out.groupby("edge", sort=False)["货量"]
    for lag in LAGS:
        out[f"lag_{lag}"] = grouped.shift(lag)
    shifted = grouped.shift(1)
    for window in ROLL_WINDOWS:
        out[f"roll_mean_{window}"] = shifted.groupby(out["edge"], sort=False).rolling(window, min_periods=1).mean().reset_index(level=0, drop=True)
        out[f"roll_max_{window}"] = shifted.groupby(out["edge"], sort=False).rolling(window, min_periods=1).max().reset_index(level=0, drop=True)
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
    edge_stats = history.groupby("edge")["货量"].agg(
        edge_mean="mean",
        edge_median="median",
        edge_max="max",
        edge_nonzero_ratio=lambda s: float((s > 0).mean()),
    )
    origin_stats = history.groupby("场地1")["货量"].agg(origin_mean="mean", origin_max="max")
    dest_stats = history.groupby("场地2")["货量"].agg(dest_mean="mean", dest_max="max")

    out = out.merge(edge_stats, on="edge", how="left")
    out = out.merge(origin_stats, on="场地1", how="left")
    out = out.merge(dest_stats, on="场地2", how="left")
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


def build_training_frame(panel: pd.DataFrame, encoders: dict[str, dict[str, int]], train_end: str) -> pd.DataFrame:
    train_panel = panel[panel["日期"] <= pd.Timestamp(train_end)].copy()
    feat = add_history_features(train_panel)
    feat = add_basic_features(feat, encoders)
    feat = add_static_features(feat, train_panel)
    feat = feat[feat["日期"] >= feat["日期"].min() + pd.Timedelta(days=28)].copy()
    return feat


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


def train_model(train_feat: pd.DataFrame) -> lgb.Booster:
    features = feature_columns()
    train_feat = train_feat.copy()
    train_feat[features] = train_feat[features].fillna(0)

    valid_start = train_feat["日期"].max() - pd.Timedelta(days=61)
    train_idx = train_feat["日期"] < valid_start
    valid_idx = ~train_idx

    dtrain = lgb.Dataset(
        train_feat.loc[train_idx, features],
        label=np.log1p(train_feat.loc[train_idx, "货量"]),
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        free_raw_data=False,
    )
    dvalid = lgb.Dataset(
        train_feat.loc[valid_idx, features],
        label=np.log1p(train_feat.loc[valid_idx, "货量"]),
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
    model = lgb.train(
        params,
        dtrain,
        valid_sets=[dvalid],
        num_boost_round=1200,
        callbacks=[lgb.early_stopping(80), lgb.log_evaluation(100)],
    )
    return model


def make_future_rows(edges: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    out = edges.copy()
    out["日期"] = date
    out["货量"] = np.nan
    return out[["场地1", "场地2", "edge", "日期", "货量"]]


def forecast_recursive(
    model: lgb.Booster,
    history_panel: pd.DataFrame,
    encoders: dict[str, dict[str, int]],
    start: str,
    end: str,
) -> pd.DataFrame:
    features = feature_columns()
    edges = history_panel[["场地1", "场地2", "edge"]].drop_duplicates().sort_values("edge")
    working = history_panel.copy()
    preds = []

    for date in pd.date_range(start, end, freq="D"):
        one_day = make_future_rows(edges, date)
        temp = pd.concat([working, one_day], ignore_index=True)
        temp_feat = add_history_features(temp)
        future_feat = temp_feat[temp_feat["日期"] == date].copy()
        future_feat = add_basic_features(future_feat, encoders)
        future_feat = add_static_features(future_feat, working)
        future_feat[features] = future_feat[features].fillna(0)
        pred = np.expm1(model.predict(future_feat[features], num_iteration=model.best_iteration))
        pred = np.maximum(pred, 0)
        caps = future_feat["edge_max"].to_numpy()
        pred = np.minimum(pred, np.where(caps > 0, caps * 1.2, pred))
        future_feat["预测货量"] = np.rint(pred).astype(int)
        preds.append(future_feat[["场地1", "场地2", "edge", "日期", "预测货量"]])

        append_rows = future_feat[["场地1", "场地2", "edge", "日期"]].copy()
        append_rows["货量"] = future_feat["预测货量"].astype(float).to_numpy()
        working = pd.concat([working, append_rows], ignore_index=True)

    return pd.concat(preds, ignore_index=True)


def metrics_frame(pred: pd.DataFrame, actual_panel: pd.DataFrame) -> pd.DataFrame:
    actual = actual_panel[["edge", "日期", "货量"]]
    merged = pred.merge(actual, on=["edge", "日期"], how="left")
    merged["abs_err"] = (merged["预测货量"] - merged["货量"]).abs()
    merged["sq_err"] = (merged["预测货量"] - merged["货量"]) ** 2
    merged["smape_part"] = np.where(
        merged["预测货量"] + merged["货量"] > 0,
        2 * merged["abs_err"] / (merged["预测货量"] + merged["货量"]),
        0.0,
    )
    return pd.DataFrame(
        [
            {
                "MAE": merged["abs_err"].mean(),
                "RMSE": float(np.sqrt(merged["sq_err"].mean())),
                "sMAPE": merged["smape_part"].mean(),
                "total_actual": int(merged["货量"].sum()),
                "total_pred": int(merged["预测货量"].sum()),
            }
        ]
    )


def save_outputs(forecast: pd.DataFrame, prefix: str) -> None:
    forecast.to_csv(RESULT_DIR / f"{prefix}_all_edges.csv", index=False, encoding="utf-8-sig")
    target = forecast[forecast[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)].copy()
    target.to_csv(RESULT_DIR / f"{prefix}_target_edges.csv", index=False, encoding="utf-8-sig")
    daily = forecast.groupby("日期")["预测货量"].sum().reset_index()
    daily.to_csv(RESULT_DIR / f"{prefix}_daily_total.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    panel = build_panel(df)
    encoders = make_encoders(panel)
    print("完整面板:", len(panel), "行,", panel["edge"].nunique(), "条线路")

    print("\n训练回测模型: 2021 -> 预测2022年1月")
    train_2021 = build_training_frame(panel, encoders, "2021-12-31")
    model_2021 = train_model(train_2021)
    hist_2021 = panel[panel["日期"] <= "2021-12-31"].copy()
    pred_2022_jan = forecast_recursive(model_2021, hist_2021, encoders, "2022-01-01", "2022-01-31")
    actual_2022_jan = panel[(panel["日期"] >= "2022-01-01") & (panel["日期"] <= "2022-01-31")]
    metrics = metrics_frame(pred_2022_jan, actual_2022_jan)
    metrics.to_csv(RESULT_DIR / "problem1_lightgbm_validation_metrics.csv", index=False, encoding="utf-8-sig")
    print("LightGBM回测指标:")
    print(metrics.round(4).to_string(index=False))

    print("\n训练最终模型: 2021-2022 -> 预测2023年1月")
    train_full = build_training_frame(panel, encoders, "2022-12-31")
    model_full = train_model(train_full)
    pred_2023_jan = forecast_recursive(model_full, panel, encoders, "2023-01-01", "2023-01-31")
    save_outputs(pred_2023_jan, "problem1_lightgbm_2023_01_forecast")

    daily_total = pred_2023_jan.groupby("日期")["预测货量"].sum().reset_index()
    target = pred_2023_jan[pred_2023_jan[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)]

    print("\n2023年1月预测总量:")
    print(daily_total.to_string(index=False))
    print("\n三条指定线路预测:")
    print(target.sort_values(["edge", "日期"]).to_string(index=False))
    print("\n输出目录:", RESULT_DIR)


if __name__ == "__main__":
    main()
