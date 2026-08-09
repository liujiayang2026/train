from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter


OUT_DIR = Path(__file__).resolve().parent / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FONT = font_manager.FontProperties(fname=r"C:\Windows\Fonts\msyh.ttc")
BOLD_FONT = font_manager.FontProperties(fname=r"C:\Windows\Fonts\msyhbd.ttc")

plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 160

BAR_COLOR = "#2f6f73"
ACCENT = "#c46a36"
GRID_COLOR = "#d8ddd9"
TEXT_COLOR = "#1f2933"


def thousands(x, pos=None):
    return f"{int(x):,}"


def score_fmt(x, pos=None):
    return f"{x:.2f}"


def style_axis(ax):
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID_COLOR, linewidth=0.8)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color("#87938d")
    ax.tick_params(axis="both", colors=TEXT_COLOR, labelsize=9)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontproperties(FONT)


def save_table7():
    volume_items = [
        ("DC5 相关受影响总货量", 3214028),
        ("入 DC5 货量", 3161350),
        ("出 DC5 货量", 52678),
        ("正常分流货量", 3190249),
        ("未正常流转货量", 23779),
    ]
    line_items = [
        ("平均每日变化线路数", 44.741935),
        ("最大每日变化线路数", 65),
    ]

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(11.2, 4.9),
        gridspec_kw={"width_ratios": [3.4, 1.6]},
        constrained_layout=True,
    )

    labels = [x[0] for x in volume_items][::-1]
    values = [x[1] for x in volume_items][::-1]
    axes[0].barh(labels, values, color=BAR_COLOR, height=0.56)
    axes[0].set_title("货量指标（件）", fontproperties=BOLD_FONT, fontsize=12, color=TEXT_COLOR, pad=8)
    axes[0].xaxis.set_major_formatter(FuncFormatter(thousands))
    axes[0].set_xlim(0, max(values) * 1.18)
    for y, v in enumerate(values):
        axes[0].text(
            v + max(values) * 0.018,
            y,
            f"{v:,}",
            va="center",
            ha="left",
            fontsize=8.5,
            color=TEXT_COLOR,
            fontproperties=FONT,
        )
    style_axis(axes[0])

    labels2 = [x[0] for x in line_items][::-1]
    values2 = [x[1] for x in line_items][::-1]
    axes[1].barh(labels2, values2, color=ACCENT, height=0.48)
    axes[1].set_title("线路变化指标（条/日）", fontproperties=BOLD_FONT, fontsize=12, color=TEXT_COLOR, pad=8)
    axes[1].set_xlim(0, max(values2) * 1.35)
    for y, v in enumerate(values2):
        label = f"{v:.6f}" if abs(v - round(v)) > 1e-9 else f"{int(v)}"
        axes[1].text(
            v + max(values2) * 0.035,
            y,
            label,
            va="center",
            ha="left",
            fontsize=8.5,
            color=TEXT_COLOR,
            fontproperties=FONT,
        )
    style_axis(axes[1])

    fig.suptitle("问题二 DC5 关停分流结果", fontproperties=BOLD_FONT, fontsize=14, color=TEXT_COLOR)
    fig.savefig(OUT_DIR / "table7_dc5_diversion_bar.png", bbox_inches="tight", dpi=220)
    plt.close(fig)


def save_rank_bar_chart(filename, title, data, color, highlight_color, xlim, figsize):
    labels = [f"{i}. {name}" for i, (name, _) in enumerate(data, 1)][::-1]
    values = [v for _, v in data][::-1]
    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)
    colors = [color] * len(values)
    for i in range(len(colors) - 5, len(colors)):
        colors[i] = highlight_color
    ax.barh(labels, values, color=colors, height=0.56)
    ax.set_title(title, fontproperties=BOLD_FONT, fontsize=14, color=TEXT_COLOR, pad=10)
    ax.set_xlabel("重要性得分", fontproperties=FONT, fontsize=10, color=TEXT_COLOR)
    ax.set_xlim(*xlim)
    ax.xaxis.set_major_formatter(FuncFormatter(score_fmt))
    style_axis(ax)
    for y, v in enumerate(values):
        ax.text(
            v + (xlim[1] - xlim[0]) * 0.012,
            y,
            f"{v:.6f}",
            va="center",
            ha="left",
            fontsize=8.2,
            color=TEXT_COLOR,
            fontproperties=FONT,
        )
    fig.savefig(OUT_DIR / filename, bbox_inches="tight", dpi=220)
    plt.close(fig)


def save_table13():
    site_data = [
        ("DC14", 0.924691),
        ("DC9", 0.916512),
        ("DC10", 0.897685),
        ("DC3", 0.891975),
        ("DC4", 0.887654),
        ("DC8", 0.881481),
        ("DC5", 0.875926),
        ("DC62", 0.870833),
        ("DC25", 0.816204),
        ("DC23", 0.814198),
        ("DC36", 0.805864),
        ("DC22", 0.783488),
        ("DC51", 0.775000),
        ("DC17", 0.767747),
        ("DC20", 0.759259),
    ]
    save_rank_bar_chart(
        "table13_site_importance_bar.png",
        "问题四场地重要性前十五名",
        site_data,
        "#98b8a7",
        BAR_COLOR,
        (0.72, 0.95),
        (8.9, 6.4),
    )


def save_table14():
    edge_data = [
        ("DC14->DC9", 0.982257),
        ("DC25->DC9", 0.971556),
        ("DC14->DC3", 0.969209),
        ("DC9->DC3", 0.963179),
        ("DC9->DC14", 0.961439),
        ("DC51->DC9", 0.960665),
        ("DC9->DC5", 0.949416),
        ("DC14->DC8", 0.949011),
        ("DC62->DC8", 0.947569),
        ("DC10->DC3", 0.944733),
        ("DC15->DC9", 0.943923),
        ("DC36->DC3", 0.941492),
        ("DC44->DC9", 0.939871),
        ("DC10->DC4", 0.938870),
        ("DC23->DC3", 0.937297),
        ("DC14->DC62", 0.936499),
        ("DC25->DC3", 0.933997),
        ("DC14->DC10", 0.933222),
        ("DC8->DC14", 0.931542),
        ("DC23->DC4", 0.930207),
    ]
    save_rank_bar_chart(
        "table14_edge_importance_bar.png",
        "问题四线路重要性前二十名",
        edge_data,
        "#a7b7c8",
        "#375f8b",
        (0.925, 0.99),
        (9.2, 7.4),
    )


if __name__ == "__main__":
    save_table7()
    save_table13()
    save_table14()
    for path in sorted(OUT_DIR.glob("table*_bar.png")):
        print(f"{path.name}: {path.stat().st_size} bytes")
