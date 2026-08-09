from __future__ import annotations

from pathlib import Path

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ============================================================
# 1. 基本路径与全局参数
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "原始资料" / "附件1：物流网络历史货量数据.xlsx"

PROBLEM1_DIR = BASE_DIR / "问题1"
RESULT_FINAL_DIR = PROBLEM1_DIR / "results" / "final"
RESULT_EXPERIMENT_DIR = PROBLEM1_DIR / "results" / "experiments"
FIGURE_DIR = PROBLEM1_DIR / "paper_source" / "figures"

SPRING_FESTIVAL = {
    2021: pd.Timestamp("2021-02-12"),
    2022: pd.Timestamp("2022-02-01"),
    2023: pd.Timestamp("2023-01-22"),
}

TARGET_EDGES = [("DC14", "DC10"), ("DC20", "DC35"), ("DC25", "DC62")]
LAGS = [1, 2, 3, 7, 14, 28, 365]
ROLL_WINDOWS = [7, 14, 28, 56]


# ============================================================
# 2. 数据读取与完整线路-日期面板构造
# ============================================================

def load_data() -> pd.DataFrame:
    """读取附件1历史货量数据，并生成线路标识 edge。"""
    df = pd.read_excel(DATA_PATH)
    df["日期"] = pd.to_datetime(df["日期"])
    df["edge"] = df["场地1"].astype(str) + "->" + df["场地2"].astype(str)
    return df


def build_panel(df: pd.DataFrame) -> pd.DataFrame:
    """构造 线路 x 日期 完整面板，缺失的线路-日期货量记为 0。"""
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
    """将线路、起点、终点转成 LightGBM 可使用的类别编号。"""
    sites = sorted(set(panel["场地1"].unique()).union(set(panel["场地2"].unique())))
    return {
        "edge": {v: i for i, v in enumerate(sorted(panel["edge"].unique()))},
        "site": {v: i for i, v in enumerate(sites)},
    }


# ============================================================
# 3. 特征工程：日期特征、春节特征、滞后项、滚动统计量
# ============================================================

def spring_delta(date: pd.Timestamp) -> int:
    """计算日期距离当年春节的天数。"""
    return int((date - SPRING_FESTIVAL[int(date.year)]).days)


def add_basic_features(frame: pd.DataFrame, encoders: dict[str, dict[str, int]]) -> pd.DataFrame:
    """加入线路编码、场地编码、日历特征和春节相对日期特征。"""
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
    """加入各线路的历史滞后项和滚动统计量，预测当天不会使用当天真实值。"""
    out = panel.sort_values(["edge", "日期"]).copy()
    grouped = out.groupby("edge", sort=False)["货量"]

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
    """加入线路、起点、终点的历史静态统计特征。"""
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


def feature_columns() -> list[str]:
    """模型最终使用的全部特征列。"""
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
    """按给定截止日期构造训练样本。"""
    train_panel = panel[panel["日期"] <= pd.Timestamp(train_end)].copy()
    feat = add_history_features(train_panel)
    feat = add_basic_features(feat, encoders)
    feat = add_static_features(feat, train_panel)
    feat = feat[feat["日期"] >= feat["日期"].min() + pd.Timedelta(days=28)].copy()
    return feat


# ============================================================
# 4. LightGBM 模型训练与回测评价
# ============================================================

def train_model(train_feat: pd.DataFrame) -> lgb.Booster:
    """训练全局 LightGBM 模型，目标变量为 log(1 + 货量)。"""
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

    return lgb.train(
        params,
        dtrain,
        valid_sets=[dvalid],
        num_boost_round=1200,
        callbacks=[lgb.early_stopping(80), lgb.log_evaluation(100)],
    )


def metrics_frame(pred: pd.DataFrame, actual_panel: pd.DataFrame) -> pd.DataFrame:
    """计算 MAE、RMSE、sMAPE 和总量误差。"""
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


# ============================================================
# 5. 递推预测 2023 年 1 月全网络货量
# ============================================================

def make_future_rows(edges: pd.DataFrame, date: pd.Timestamp) -> pd.DataFrame:
    """生成某一天所有线路的待预测行。"""
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
    """逐日递推预测；前一天预测值会进入下一天的滞后特征。"""
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

        edge_caps = future_feat["edge_max"].to_numpy()
        pred = np.minimum(pred, np.where(edge_caps > 0, edge_caps * 1.2, pred))

        future_feat["预测货量"] = np.rint(pred).astype(int)
        preds.append(future_feat[["场地1", "场地2", "edge", "日期", "预测货量"]])

        append_rows = future_feat[["场地1", "场地2", "edge", "日期"]].copy()
        append_rows["货量"] = future_feat["预测货量"].astype(float).to_numpy()
        working = pd.concat([working, append_rows], ignore_index=True)

    return pd.concat(preds, ignore_index=True)


# ============================================================
# 6. 春节窗口总量校准
# ============================================================

def spring_relative_window_total(history: pd.DataFrame, year: int, low: int = -21, high: int = 9) -> int:
    """统计历史年份春节相对窗口内的全网络总货量。"""
    daily = history.groupby("日期")["货量"].sum().reset_index()
    start = SPRING_FESTIVAL[year] + pd.Timedelta(days=low)
    end = SPRING_FESTIVAL[year] + pd.Timedelta(days=high)
    return int(daily[daily["日期"].between(start, end)]["货量"].sum())


def calibrate_total(history: pd.DataFrame, pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """用 2021、2022 年春节相对窗口加权总量修正 2023 年 1 月预测总量。"""
    total_2021 = spring_relative_window_total(history, 2021)
    total_2022 = spring_relative_window_total(history, 2022)

    target_total = 0.35 * total_2021 + 0.65 * total_2022
    raw_total = float(pred["预测货量"].sum())
    calibration_factor = target_total / raw_total

    final = pred.copy()
    final["原LightGBM预测货量"] = final["预测货量"].astype(int)
    final["预测货量"] = np.rint(final["预测货量"] * calibration_factor).astype(int)

    diff = int(round(target_total)) - int(final["预测货量"].sum())
    if diff != 0:
        idx = final["预测货量"].idxmax()
        final.loc[idx, "预测货量"] += diff

    summary = pd.DataFrame(
        [
            {
                "history_2021_spring_window_total": total_2021,
                "history_2022_spring_window_total": total_2022,
                "target_total_weighted_035_065": int(round(target_total)),
                "raw_lightgbm_total": int(raw_total),
                "calibration_factor": calibration_factor,
                "final_total": int(final["预测货量"].sum()),
            }
        ]
    )
    return final, summary


# ============================================================
# 7. 结果导出：最终 CSV 与回测 CSV
# ============================================================

def save_experiment_outputs(raw_forecast: pd.DataFrame, metrics: pd.DataFrame) -> None:
    """保存未校准 LightGBM 预测结果和回测指标，作为实验对比材料。"""
    RESULT_EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)

    raw_forecast.to_csv(
        RESULT_EXPERIMENT_DIR / "problem1_lightgbm_2023_01_forecast_all_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )
    target = raw_forecast[raw_forecast[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)].copy()
    target.to_csv(
        RESULT_EXPERIMENT_DIR / "problem1_lightgbm_2023_01_forecast_target_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )
    daily = raw_forecast.groupby("日期")["预测货量"].sum().reset_index()
    daily.to_csv(
        RESULT_EXPERIMENT_DIR / "problem1_lightgbm_2023_01_forecast_daily_total.csv",
        index=False,
        encoding="utf-8-sig",
    )
    metrics.to_csv(
        RESULT_EXPERIMENT_DIR / "problem1_lightgbm_validation_metrics.csv",
        index=False,
        encoding="utf-8-sig",
    )


def save_final_outputs(final: pd.DataFrame, summary: pd.DataFrame) -> None:
    """保存最终校准后的全线路、指定线路、每日总量和校准摘要。"""
    RESULT_FINAL_DIR.mkdir(parents=True, exist_ok=True)

    all_edges = final[["场地1", "场地2", "edge", "日期", "预测货量", "原LightGBM预测货量"]].copy()
    all_edges.to_csv(
        RESULT_FINAL_DIR / "problem1_final_2023_01_forecast_all_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )

    target = all_edges[all_edges[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)].copy()
    target.to_csv(
        RESULT_FINAL_DIR / "problem1_final_2023_01_forecast_target_edges.csv",
        index=False,
        encoding="utf-8-sig",
    )

    daily = all_edges.groupby("日期", as_index=False).agg(
        预测货量=("预测货量", "sum"),
        原LightGBM预测货量=("原LightGBM预测货量", "sum"),
    )
    daily.to_csv(
        RESULT_FINAL_DIR / "problem1_final_2023_01_forecast_daily_total.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary.to_csv(
        RESULT_FINAL_DIR / "problem1_final_calibration_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


# ============================================================
# 8. 可视化：指定线路预测图
# ============================================================

def setup_chinese_font() -> None:
    """设置中文字体，保证图片标题和坐标轴能正常显示中文。"""
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def plot_target_edges(final: pd.DataFrame) -> None:
    """绘制三条指定线路的每日预测货量折线图。"""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    setup_chinese_font()

    target = final[final[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)].copy()

    fig, ax = plt.subplots(figsize=(10, 5.8))
    for edge, group in target.groupby("edge"):
        group = group.sort_values("日期")
        ax.plot(group["日期"], group["预测货量"], marker="o", linewidth=2, markersize=3.5, label=edge)

    ax.set_title("问题一三条指定线路 2023 年 1 月每日预测货量")
    ax.set_xlabel("日期")
    ax.set_ylabel("预测货量")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "target_edges.png", dpi=220)
    plt.close(fig)


def plot_dc20_dc35(final: pd.DataFrame) -> None:
    """单独绘制 DC20->DC35 线路，避免小货量线路在合图中被压扁。"""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    setup_chinese_font()

    one = final[(final["场地1"] == "DC20") & (final["场地2"] == "DC35")].sort_values("日期").copy()

    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.plot(one["日期"], one["预测货量"], marker="o", linewidth=2.2, markersize=4, color="#2f7ed8")
    ax.set_title("DC20->DC35 线路 2023 年 1 月每日预测货量")
    ax.set_xlabel("日期")
    ax.set_ylabel("预测货量")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "dc20_dc35_daily.png", dpi=220)
    plt.close(fig)


def save_visualizations(final: pd.DataFrame) -> None:
    """生成论文中保留的两张可视化图片。"""
    plot_target_edges(final)
    plot_dc20_dc35(final)


# ============================================================
# 9. 主流程：一键完成问题一最终建模、预测、校准、制图
# ============================================================

def main() -> None:
    df = load_data()
    panel = build_panel(df)
    encoders = make_encoders(panel)

    print(f"完整面板：{len(panel)} 行，{panel['edge'].nunique()} 条线路")

    print("\n[1/5] 回测：用 2021 年训练，预测 2022 年 1 月")
    train_2021 = build_training_frame(panel, encoders, "2021-12-31")
    model_2021 = train_model(train_2021)
    hist_2021 = panel[panel["日期"] <= "2021-12-31"].copy()
    pred_2022_jan = forecast_recursive(model_2021, hist_2021, encoders, "2022-01-01", "2022-01-31")
    actual_2022_jan = panel[(panel["日期"] >= "2022-01-01") & (panel["日期"] <= "2022-01-31")]
    metrics = metrics_frame(pred_2022_jan, actual_2022_jan)
    print(metrics.round(4).to_string(index=False))

    print("\n[2/5] 最终模型：用 2021-2022 年训练，预测 2023 年 1 月")
    train_full = build_training_frame(panel, encoders, "2022-12-31")
    model_full = train_model(train_full)
    raw_forecast = forecast_recursive(model_full, panel, encoders, "2023-01-01", "2023-01-31")

    print("\n[3/5] 春节窗口总量校准")
    final, summary = calibrate_total(df, raw_forecast)
    print(summary.round(6).to_string(index=False))

    print("\n[4/5] 保存 CSV 结果")
    save_experiment_outputs(raw_forecast, metrics)
    save_final_outputs(final, summary)

    print("\n[5/5] 生成可视化图片")
    save_visualizations(final)

    target = final[final[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)]
    target_total = target.groupby("edge")["预测货量"].sum().reset_index()

    print("\n三条指定线路 2023 年 1 月预测总量：")
    print(target_total.to_string(index=False))
    print(f"\n最终结果目录：{RESULT_FINAL_DIR}")
    print(f"对比实验目录：{RESULT_EXPERIMENT_DIR}")
    print(f"可视化目录：{FIGURE_DIR}")


if __name__ == "__main__":
    main()
