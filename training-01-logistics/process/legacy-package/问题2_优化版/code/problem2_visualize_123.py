from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd


# ============================================================
# 1. 路径与画图基础设置
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
RESULT_DIR = BASE_DIR / "问题2_优化版" / "results"
FIGURE_DIR = BASE_DIR / "问题2_优化版" / "figures"

DAILY_METRICS_PATH = RESULT_DIR / "problem2_dc5_integer_tradeoff_daily_metrics.csv"

SCHEME_LABELS = {
    "min_changed_plus_0": "最少变化(+0)",
    "min_changed_plus_2": "放宽2条(+2)",
    "min_changed_plus_5": "放宽5条(+5)",
}

SCHEME_COLORS = {
    "min_changed_plus_0": "#d55e00",
    "min_changed_plus_2": "#0072b2",
    "min_changed_plus_5": "#009e73",
}


matplotlib.use("Agg")


def setup_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120


def load_metrics() -> pd.DataFrame:
    df = pd.read_csv(DAILY_METRICS_PATH)
    df["日期"] = pd.to_datetime(df["日期"], format="mixed")
    df["方案名称"] = df["方案"].map(SCHEME_LABELS)
    df["是否异常"] = (
        (df["第一阶段状态"] != "Optimal")
        | (df["第二阶段状态"] != "Optimal")
        | (df["第三阶段状态"] != "Optimal")
        | (df["实际变化线路数"] > df["允许变化线路数"])
    )
    return df


# ============================================================
# 2. 可视化 1：三方案总体指标对比
# ============================================================

def plot_scheme_summary(df: pd.DataFrame) -> None:
    summary = (
        df.groupby("方案", as_index=False)
        .agg(
            平均变化线路数=("实际变化线路数", "mean"),
            最大变化线路数=("实际变化线路数", "max"),
            最大线路负荷率=("最大线路负荷率", "max"),
            平均线路负荷率=("平均线路负荷率", "mean"),
            异常天数=("是否异常", "sum"),
        )
        .sort_values("方案")
    )
    summary["方案名称"] = summary["方案"].map(SCHEME_LABELS)

    metrics = [
        ("平均变化线路数", "平均变化线路数"),
        ("最大变化线路数", "最大变化线路数"),
        ("最大线路负荷率", "最大线路负荷率"),
        ("平均线路负荷率", "平均线路负荷率"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    axes = axes.ravel()

    colors = [SCHEME_COLORS[s] for s in summary["方案"]]
    for ax, (col, title) in zip(axes, metrics):
        bars = ax.bar(summary["方案名称"], summary[col], color=colors, width=0.58)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=0)

        for bar, value in zip(bars, summary[col]):
            label = f"{value:.3f}" if "负荷率" in col else f"{value:.2f}"
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), label, ha="center", va="bottom", fontsize=9)

    abnormal = summary[summary["异常天数"] > 0]
    if not abnormal.empty:
        fig.text(
            0.5,
            0.01,
            "注：最少变化(+0) 方案存在 1 天第三阶段未正常求解，正式推荐采用放宽2条(+2)方案。",
            ha="center",
            fontsize=10,
            color="#8a4b08",
        )

    fig.suptitle("问题二 DC5 关停后三种分流方案指标对比", fontsize=15)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(FIGURE_DIR / "problem2_scheme_summary_compare.png", dpi=220)
    plt.close(fig)


# ============================================================
# 3. 可视化 2：每日变化线路数折线图
# ============================================================

def plot_daily_changed_lines(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))

    for scheme, group in df.groupby("方案", sort=True):
        group = group.sort_values("日期")
        ax.plot(
            group["日期"],
            group["实际变化线路数"],
            marker="o",
            linewidth=2,
            markersize=4,
            color=SCHEME_COLORS[scheme],
            label=SCHEME_LABELS[scheme],
        )

    abnormal = df[df["是否异常"]]
    if not abnormal.empty:
        ax.scatter(
            abnormal["日期"],
            abnormal["实际变化线路数"],
            s=90,
            facecolors="none",
            edgecolors="#b00020",
            linewidths=2,
            label="异常点",
            zorder=5,
        )

    ax.set_title("问题二三种方案每日变化线路数")
    ax.set_xlabel("日期")
    ax.set_ylabel("变化线路数")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=9)
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "problem2_daily_changed_lines.png", dpi=220)
    plt.close(fig)


# ============================================================
# 4. 可视化 3：每日最大线路负荷率折线图
# ============================================================

def plot_daily_max_load(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))

    for scheme, group in df.groupby("方案", sort=True):
        group = group.sort_values("日期")
        ax.plot(
            group["日期"],
            group["最大线路负荷率"],
            marker="o",
            linewidth=2,
            markersize=4,
            color=SCHEME_COLORS[scheme],
            label=SCHEME_LABELS[scheme],
        )

    abnormal = df[df["是否异常"]]
    if not abnormal.empty:
        ax.scatter(
            abnormal["日期"],
            abnormal["最大线路负荷率"],
            s=90,
            facecolors="none",
            edgecolors="#b00020",
            linewidths=2,
            label="异常点",
            zorder=5,
        )

    ax.set_title("问题二三种方案每日最大线路负荷率")
    ax.set_xlabel("日期")
    ax.set_ylabel("最大线路负荷率")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=9)
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    fig.savefig(FIGURE_DIR / "problem2_daily_max_load_rate.png", dpi=220)
    plt.close(fig)


# ============================================================
# 5. 主流程
# ============================================================

def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    metrics = load_metrics()
    plot_scheme_summary(metrics)
    plot_daily_changed_lines(metrics)
    plot_daily_max_load(metrics)

    print(f"可视化图片已输出到：{FIGURE_DIR}")


if __name__ == "__main__":
    main()
