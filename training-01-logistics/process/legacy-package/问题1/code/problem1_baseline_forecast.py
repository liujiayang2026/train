from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "原始资料" / "附件1：物流网络历史货量数据.xlsx"
RESULT_DIR = BASE_DIR / "问题1" / "results" / "experiments"

SPRING_FESTIVAL = {
    2021: pd.Timestamp("2021-02-12"),
    2022: pd.Timestamp("2022-02-01"),
    2023: pd.Timestamp("2023-01-22"),
}

TARGET_EDGES = [("DC14", "DC10"), ("DC20", "DC35"), ("DC25", "DC62")]


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
    return panel[["场地1", "场地2", "edge", "日期", "货量"]]


def add_date_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["year"] = out["日期"].dt.year
    out["month"] = out["日期"].dt.month
    out["day"] = out["日期"].dt.day
    out["dow"] = out["日期"].dt.dayofweek
    out["spring_delta"] = out["日期"].map(
        lambda d: (d - SPRING_FESTIVAL[int(d.year)]).days
        if int(d.year) in SPRING_FESTIVAL
        else np.nan
    )
    return out


def clipped_ratio(num: pd.Series, den: pd.Series, low: float = 0.35, high: float = 2.8) -> pd.Series:
    ratio = num / den.replace(0, np.nan)
    ratio = ratio.replace([np.inf, -np.inf], np.nan).fillna(1.0)
    return ratio.clip(low, high)


def prepare_lookup(panel: pd.DataFrame) -> dict[str, pd.DataFrame | pd.Series]:
    p = add_date_features(panel)

    # 春节相对日期画像：比如春节前7天、春节后3天。预测2023年1月时尤其重要。
    spring_edge = p[p["spring_delta"].between(-45, 20)].groupby(["edge", "spring_delta"])["货量"].mean()
    spring_global = p[p["spring_delta"].between(-45, 20)].groupby("spring_delta")["货量"].mean()

    # 去年同月同日画像。
    md_edge = p.groupby(["edge", "month", "day"])["货量"].mean()
    md_global = p.groupby(["month", "day"])["货量"].mean()

    # 最近8周同星期画像，反映临近趋势。
    recent_start = panel["日期"].max() - pd.Timedelta(days=55)
    recent = add_date_features(panel[panel["日期"] >= recent_start])
    recent_dow_edge = recent.groupby(["edge", "dow"])["货量"].mean()
    recent_dow_global = recent.groupby("dow")["货量"].mean()

    # 年度增长/收缩修正。缺少历史或极端线路用全局比例兜底。
    p["year"] = p["日期"].dt.year
    annual_edge = p.groupby(["edge", "year"])["货量"].sum().unstack(fill_value=0)
    annual_global = p.groupby("year")["货量"].sum()
    edge_trend = clipped_ratio(annual_edge.get(2022, 0), annual_edge.get(2021, 0))
    global_trend = float(clipped_ratio(pd.Series([annual_global.get(2022, 0)]), pd.Series([annual_global.get(2021, 0)])).iloc[0])

    # 线路容量来自题设：历史最大货量。
    edge_max = panel.groupby("edge")["货量"].max()

    return {
        "spring_edge": spring_edge,
        "spring_global": spring_global,
        "md_edge": md_edge,
        "md_global": md_global,
        "recent_dow_edge": recent_dow_edge,
        "recent_dow_global": recent_dow_global,
        "edge_trend": edge_trend,
        "global_trend": pd.Series({"global": global_trend}),
        "edge_max": edge_max,
    }


def lookup_component(
    edge: str,
    key_value: int,
    edge_table: pd.Series,
    global_table: pd.Series,
    extra_key: tuple[int, int] | None = None,
) -> float:
    if extra_key is None:
        edge_key = (edge, key_value)
        global_key = key_value
    else:
        edge_key = (edge, extra_key[0], extra_key[1])
        global_key = extra_key

    edge_value = edge_table.get(edge_key, np.nan)
    global_value = global_table.get(global_key, np.nan)

    if pd.notna(edge_value):
        return float(edge_value)
    if pd.notna(global_value):
        return float(global_value)
    return 0.0


def forecast_month(panel: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    lookups = prepare_lookup(panel)
    edges = panel[["场地1", "场地2", "edge"]].drop_duplicates().sort_values("edge")
    future_dates = pd.date_range(start, end, freq="D")
    future = pd.MultiIndex.from_product([edges["edge"], future_dates], names=["edge", "日期"]).to_frame(index=False)
    future = future.merge(edges, on="edge", how="left")
    future = add_date_features(future)

    trend = lookups["edge_trend"]
    global_trend = float(lookups["global_trend"].loc["global"])
    caps = lookups["edge_max"]

    preds: list[float] = []
    for row in future.itertuples(index=False):
        edge = row.edge
        date = row.日期
        spring_delta = int(row.spring_delta)
        dow = int(row.dow)
        month = int(row.month)
        day = int(row.day)

        spring_part = lookup_component(
            edge,
            spring_delta,
            lookups["spring_edge"],
            lookups["spring_global"],
        )
        md_part = lookup_component(
            edge,
            0,
            lookups["md_edge"],
            lookups["md_global"],
            extra_key=(month, day),
        )
        recent_part = lookup_component(
            edge,
            dow,
            lookups["recent_dow_edge"],
            lookups["recent_dow_global"],
        )

        edge_trend = float(trend.get(edge, global_trend))
        value = 0.50 * spring_part + 0.30 * md_part * edge_trend + 0.20 * recent_part

        # 预测服务后续优化模型，不能超过过离谱的历史能力；留15%弹性。
        cap = float(caps.get(edge, np.inf))
        if np.isfinite(cap) and cap > 0:
            value = min(value, cap * 1.15)
        preds.append(max(0.0, value))

    future["预测货量"] = np.rint(preds).astype(int)
    return future[["场地1", "场地2", "edge", "日期", "预测货量"]]


def validate_2022_january(panel: pd.DataFrame) -> pd.DataFrame:
    train = panel[panel["日期"] <= pd.Timestamp("2021-12-31")]
    pred = forecast_month(train, "2022-01-01", "2022-01-31")
    actual = panel[(panel["日期"] >= "2022-01-01") & (panel["日期"] <= "2022-01-31")]
    merged = pred.merge(actual[["edge", "日期", "货量"]], on=["edge", "日期"], how="left")
    merged["abs_err"] = (merged["预测货量"] - merged["货量"]).abs()
    merged["sq_err"] = (merged["预测货量"] - merged["货量"]) ** 2
    merged["smape_part"] = np.where(
        merged["预测货量"] + merged["货量"] > 0,
        2 * merged["abs_err"] / (merged["预测货量"] + merged["货量"]),
        0.0,
    )
    return merged


def main() -> None:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    panel = build_panel(df)

    validation = validate_2022_january(panel)
    metrics = pd.DataFrame(
        [
            {
                "MAE": validation["abs_err"].mean(),
                "RMSE": float(np.sqrt(validation["sq_err"].mean())),
                "sMAPE": validation["smape_part"].mean(),
                "total_actual": int(validation["货量"].sum()),
                "total_pred": int(validation["预测货量"].sum()),
            }
        ]
    )
    metrics.to_csv(RESULT_DIR / "problem1_baseline_validation_metrics.csv", index=False, encoding="utf-8-sig")

    forecast = forecast_month(panel, "2023-01-01", "2023-01-31")
    forecast.to_csv(RESULT_DIR / "problem1_all_edges_2023_01_forecast.csv", index=False, encoding="utf-8-sig")

    target = forecast[
        forecast[["场地1", "场地2"]].apply(tuple, axis=1).isin(TARGET_EDGES)
    ].copy()
    target.to_csv(RESULT_DIR / "problem1_target_edges_2023_01_forecast.csv", index=False, encoding="utf-8-sig")

    daily_total = forecast.groupby("日期")["预测货量"].sum().reset_index()
    daily_total.to_csv(RESULT_DIR / "problem1_daily_total_2023_01_forecast.csv", index=False, encoding="utf-8-sig")

    print("数据行数:", len(df))
    print("完整面板:", len(panel), "=", panel["edge"].nunique(), "条线路 x", panel["日期"].nunique(), "天")
    print("验证集 2022年1月:")
    print(metrics.round(4).to_string(index=False))
    print("\n2023年1月预测总量:")
    print(daily_total.to_string(index=False))
    print("\n三条指定线路预测:")
    print(target.sort_values(["edge", "日期"]).to_string(index=False))
    print("\n输出目录:", RESULT_DIR)


if __name__ == "__main__":
    main()
