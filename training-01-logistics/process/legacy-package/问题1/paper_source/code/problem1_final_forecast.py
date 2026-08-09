from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[3]
DATA_PATH = BASE_DIR / "原始资料" / "附件1：物流网络历史货量数据.xlsx"
RESULT_DIR = BASE_DIR / "问题1" / "results" / "final"
LIGHTGBM_PRED_PATH = BASE_DIR / "问题1" / "results" / "experiments" / "problem1_lightgbm_2023_01_forecast_all_edges.csv"

SPRING_FESTIVAL = {
    2021: pd.Timestamp("2021-02-12"),
    2022: pd.Timestamp("2022-02-01"),
    2023: pd.Timestamp("2023-01-22"),
}

TARGET_EDGES = [("DC14", "DC10"), ("DC20", "DC35"), ("DC25", "DC62")]


def load_history() -> pd.DataFrame:
    df = pd.read_excel(DATA_PATH)
    df["日期"] = pd.to_datetime(df["日期"])
    df["edge"] = df["场地1"].astype(str) + "->" + df["场地2"].astype(str)
    return df


def load_lightgbm_prediction() -> pd.DataFrame:
    pred = pd.read_csv(LIGHTGBM_PRED_PATH)
    pred["日期"] = pd.to_datetime(pred["日期"])
    return pred


def spring_relative_window_total(history: pd.DataFrame, year: int, low: int = -21, high: int = 9) -> int:
    daily = history.groupby("日期")["货量"].sum().reset_index()
    start = SPRING_FESTIVAL[year] + pd.Timedelta(days=low)
    end = SPRING_FESTIVAL[year] + pd.Timedelta(days=high)
    return int(daily[daily["日期"].between(start, end)]["货量"].sum())


def calibrate_total(history: pd.DataFrame, pred: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    total_2021 = spring_relative_window_total(history, 2021)
    total_2022 = spring_relative_window_total(history, 2022)

    # 2023年1月正好对应春节前21天到春节后9天。用更近的2022年赋予更高权重，
    # 既体现业务规模增长，又避免直接外推导致预测过高。
    target_total = 0.35 * total_2021 + 0.65 * total_2022
    raw_total = float(pred["预测货量"].sum())
    calibration_factor = target_total / raw_total

    final = pred.copy()
    final["原LightGBM预测货量"] = final["预测货量"].astype(int)
    final["预测货量"] = np.rint(final["预测货量"] * calibration_factor).astype(int)

    # 四舍五入会造成少量总量偏差，把差额补到预测量最大的线路-日期上，保证总量一致。
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


def save_outputs(final: pd.DataFrame, summary: pd.DataFrame) -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    all_edges = final[["场地1", "场地2", "edge", "日期", "预测货量", "原LightGBM预测货量"]].copy()
    all_edges.to_csv(RESULT_DIR / "problem1_final_2023_01_forecast_all_edges.csv", index=False, encoding="utf-8-sig")

    target = all_edges[all_edges[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)].copy()
    target.to_csv(RESULT_DIR / "problem1_final_2023_01_forecast_target_edges.csv", index=False, encoding="utf-8-sig")

    daily = all_edges.groupby("日期", as_index=False).agg(
        预测货量=("预测货量", "sum"),
        原LightGBM预测货量=("原LightGBM预测货量", "sum"),
    )
    daily.to_csv(RESULT_DIR / "problem1_final_2023_01_forecast_daily_total.csv", index=False, encoding="utf-8-sig")

    summary.to_csv(RESULT_DIR / "problem1_final_calibration_summary.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    history = load_history()
    pred = load_lightgbm_prediction()
    final, summary = calibrate_total(history, pred)
    save_outputs(final, summary)

    daily = final.groupby("日期")["预测货量"].sum().reset_index()
    target = final[final[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)]

    print("最终校准摘要:")
    print(summary.round(6).to_string(index=False))
    print("\n最终每日总货量:")
    print(daily.to_string(index=False))
    print("\n最终三条指定线路预测:")
    print(target[["场地1", "场地2", "edge", "日期", "预测货量", "原LightGBM预测货量"]].sort_values(["edge", "日期"]).to_string(index=False))
    print("\n输出目录:", RESULT_DIR)


if __name__ == "__main__":
    main()
