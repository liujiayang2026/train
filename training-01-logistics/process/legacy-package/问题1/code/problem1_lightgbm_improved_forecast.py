from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from problem1_lightgbm_forecast import (
    BASE_DIR,
    RESULT_DIR,
    TARGET_EDGES,
    add_basic_features,
    add_history_features,
    add_static_features,
    build_panel,
    build_training_frame,
    feature_columns,
    load_data,
    make_encoders,
)


def train_binary_model(train_feat: pd.DataFrame) -> lgb.Booster:
    features = feature_columns()
    train_feat = train_feat.copy()
    train_feat[features] = train_feat[features].fillna(0)
    y = (train_feat["货量"] > 0).astype(int)

    valid_start = train_feat["日期"].max() - pd.Timedelta(days=61)
    train_idx = train_feat["日期"] < valid_start
    valid_idx = ~train_idx

    dtrain = lgb.Dataset(
        train_feat.loc[train_idx, features],
        label=y.loc[train_idx],
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        free_raw_data=False,
    )
    dvalid = lgb.Dataset(
        train_feat.loc[valid_idx, features],
        label=y.loc[valid_idx],
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        reference=dtrain,
        free_raw_data=False,
    )
    params = {
        "objective": "binary",
        "metric": ["binary_logloss", "auc"],
        "learning_rate": 0.05,
        "num_leaves": 96,
        "min_data_in_leaf": 100,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "lambda_l2": 0.3,
        "verbosity": -1,
        "seed": 2026,
        "num_threads": 0,
    }
    return lgb.train(
        params,
        dtrain,
        valid_sets=[dvalid],
        num_boost_round=800,
        callbacks=[lgb.early_stopping(60), lgb.log_evaluation(100)],
    )


def train_amount_model(train_feat: pd.DataFrame) -> lgb.Booster:
    features = feature_columns()
    positive = train_feat[train_feat["货量"] > 0].copy()
    positive[features] = positive[features].fillna(0)

    valid_start = positive["日期"].max() - pd.Timedelta(days=61)
    train_idx = positive["日期"] < valid_start
    valid_idx = ~train_idx

    dtrain = lgb.Dataset(
        positive.loc[train_idx, features],
        label=np.log1p(positive.loc[train_idx, "货量"]),
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        free_raw_data=False,
    )
    dvalid = lgb.Dataset(
        positive.loc[valid_idx, features],
        label=np.log1p(positive.loc[valid_idx, "货量"]),
        categorical_feature=["edge_id", "origin_id", "dest_id", "month", "dow"],
        reference=dtrain,
        free_raw_data=False,
    )
    params = {
        "objective": "regression_l1",
        "metric": ["l1", "rmse"],
        "learning_rate": 0.045,
        "num_leaves": 96,
        "min_data_in_leaf": 60,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "lambda_l1": 0.05,
        "lambda_l2": 0.2,
        "verbosity": -1,
        "seed": 2027,
        "num_threads": 0,
    }
    return lgb.train(
        params,
        dtrain,
        valid_sets=[dvalid],
        num_boost_round=1000,
        callbacks=[lgb.early_stopping(70), lgb.log_evaluation(100)],
    )


def make_future_rows(edges: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    out = edges.copy()
    out["日期"] = date
    out["货量"] = np.nan
    return out[["场地1", "场地2", "edge", "日期", "货量"]]


def recent_floor(future_feat: pd.DataFrame, working: pd.DataFrame) -> np.ndarray:
    recent_start = working["日期"].max() - pd.Timedelta(days=55)
    recent = working[working["日期"] >= recent_start].copy()
    recent["dow"] = recent["日期"].dt.dayofweek

    edge_recent = recent.groupby("edge")["货量"].agg(recent_mean="mean", recent_nonzero=lambda s: (s > 0).mean())
    dow_recent = recent.groupby(["edge", "dow"])["货量"].mean().rename("recent_dow_mean")
    feat = future_feat[["edge", "dow"]].join(edge_recent, on="edge").join(dow_recent, on=["edge", "dow"])
    feat = feat.fillna(0)
    floor = np.where(
        (feat["recent_nonzero"].to_numpy() >= 0.45) & (feat["recent_mean"].to_numpy() >= 5),
        0.60 * np.maximum(feat["recent_dow_mean"].to_numpy(), feat["recent_mean"].to_numpy()),
        0.0,
    )
    return floor


def apply_total_calibration(
    future_feat: pd.DataFrame,
    pred: np.ndarray,
    calibration_factor: float | None,
) -> np.ndarray:
    if calibration_factor is None:
        return pred
    pred_sum = pred.sum()
    if pred_sum <= 0:
        return pred
    factor = float(np.clip(calibration_factor, 0.85, 1.35))
    return pred * factor


def forecast_recursive_improved(
    binary_model: lgb.Booster,
    amount_model: lgb.Booster,
    history_panel: pd.DataFrame,
    encoders: dict[str, dict[str, int]],
    start: str,
    end: str,
    calibration_factor: float | None = None,
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

        prob_nonzero = binary_model.predict(future_feat[features], num_iteration=binary_model.best_iteration)
        amount = np.expm1(amount_model.predict(future_feat[features], num_iteration=amount_model.best_iteration))
        raw = np.maximum(prob_nonzero * amount, 0)

        floor = recent_floor(future_feat, working)
        raw = np.maximum(raw, floor)
        raw = apply_total_calibration(future_feat, raw, calibration_factor)

        caps = future_feat["edge_max"].to_numpy()
        pred = np.minimum(raw, np.where(caps > 0, caps * 1.2, raw))
        future_feat["预测货量"] = np.rint(np.maximum(pred, 0)).astype(int)
        preds.append(future_feat[["场地1", "场地2", "edge", "日期", "预测货量"]])

        append_rows = future_feat[["场地1", "场地2", "edge", "日期"]].copy()
        append_rows["货量"] = future_feat["预测货量"].astype(float).to_numpy()
        working = pd.concat([working, append_rows], ignore_index=True)

    return pd.concat(preds, ignore_index=True)


def metrics_frame(pred: pd.DataFrame, actual_panel: pd.DataFrame) -> pd.DataFrame:
    merged = pred.merge(actual_panel[["edge", "日期", "货量"]], on=["edge", "日期"], how="left")
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

    print("\n训练两阶段回测模型: 2021 -> 预测2022年1月")
    train_2021 = build_training_frame(panel, encoders, "2021-12-31")
    binary_2021 = train_binary_model(train_2021)
    amount_2021 = train_amount_model(train_2021)
    hist_2021 = panel[panel["日期"] <= "2021-12-31"].copy()
    raw_2022 = forecast_recursive_improved(binary_2021, amount_2021, hist_2021, encoders, "2022-01-01", "2022-01-31")
    actual_2022 = panel[(panel["日期"] >= "2022-01-01") & (panel["日期"] <= "2022-01-31")]
    raw_metrics = metrics_frame(raw_2022, actual_2022)
    calibration_factor = raw_metrics["total_actual"].iloc[0] / max(1, raw_metrics["total_pred"].iloc[0])
    calibrated_2022 = raw_2022.copy()
    calibrated_2022["预测货量"] = np.rint(calibrated_2022["预测货量"] * np.clip(calibration_factor, 0.85, 1.35)).astype(int)
    calibrated_metrics = metrics_frame(calibrated_2022, actual_2022)

    metrics = pd.concat(
        [
            raw_metrics.assign(model="two_stage_raw"),
            calibrated_metrics.assign(model="two_stage_total_calibrated"),
        ],
        ignore_index=True,
    )
    cols = ["model", "MAE", "RMSE", "sMAPE", "total_actual", "total_pred"]
    metrics = metrics[cols]
    metrics.to_csv(RESULT_DIR / "problem1_lightgbm_improved_validation_metrics.csv", index=False, encoding="utf-8-sig")
    print("改进模型回测指标:")
    print(metrics.round(4).to_string(index=False))
    print("最终总量校准系数:", round(float(calibration_factor), 4))

    print("\n训练最终两阶段模型: 2021-2022 -> 预测2023年1月")
    train_full = build_training_frame(panel, encoders, "2022-12-31")
    binary_full = train_binary_model(train_full)
    amount_full = train_amount_model(train_full)
    pred_2023 = forecast_recursive_improved(
        binary_full,
        amount_full,
        panel,
        encoders,
        "2023-01-01",
        "2023-01-31",
        calibration_factor=float(calibration_factor),
    )
    save_outputs(pred_2023, "problem1_lightgbm_improved_2023_01_forecast")

    daily_total = pred_2023.groupby("日期")["预测货量"].sum().reset_index()
    target = pred_2023[pred_2023[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)]
    print("\n2023年1月预测总量:")
    print(daily_total.to_string(index=False))
    print("\n三条指定线路预测:")
    print(target.sort_values(["edge", "日期"]).to_string(index=False))
    print("\n输出目录:", RESULT_DIR)


if __name__ == "__main__":
    main()
