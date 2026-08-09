from io import BytesIO
from math import atan, cos, log, pi, radians, sinh, tan
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image
from scipy.spatial import cKDTree


PROJECT = Path(r"D:\jianmo\project 2\B")
OUT = PROJECT / "question-1"
ZOOM = 9


def lonlat_to_tile(lon, lat, zoom):
    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = radians(lat)
    y = (1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / pi) / 2.0 * n
    return x, y


def tile_to_lonlat(x, y, zoom):
    n = 2**zoom
    return x / n * 360.0 - 180.0, np.degrees(atan(sinh(pi * (1 - 2 * y / n))))


def get_tile(url):
    req = Request(url, headers={"User-Agent": "CUMCM academic map rendering/1.0"})
    with urlopen(req, timeout=30) as response:
        return Image.open(BytesIO(response.read())).convert("RGBA")


tasks = pd.read_csv(PROJECT / ".analysis" / "tasks.csv")
members = pd.read_excel(next(PROJECT.glob("*.xlsx")))
lat = tasks.iloc[:, 1].astype(float).to_numpy()
lon = tasks.iloc[:, 2].astype(float).to_numpy()
price = tasks.iloc[:, 3].astype(float).to_numpy()
done = tasks.iloc[:, 4].astype(int).to_numpy()

member_coords = members.iloc[:, 1].astype(str).str.extract(
    r"([0-9.]+)\s+([0-9.]+)"
).astype(float)
member_lat = member_coords.iloc[:, 0].to_numpy()
member_lon = member_coords.iloc[:, 1].to_numpy()

# Local planar approximation in kilometres, sufficient for the study extent.
lat0 = float(np.mean(lat))
task_xy = np.column_stack((lon * 111.0 * np.cos(np.radians(lat0)), lat * 111.0))
member_xy = np.column_stack(
    (member_lon * 111.0 * np.cos(np.radians(lat0)), member_lat * 111.0)
)
task_tree = cKDTree(task_xy)
member_tree = cKDTree(member_xy)
members_2km = np.array([len(x) for x in member_tree.query_ball_point(task_xy, 2.0)])
task_neighbors = task_tree.query_ball_point(task_xy, 2.0)
tasks_2km = np.array([max(0, len(x) - 1) for x in task_neighbors])
competition = np.array([
    sum(np.exp((price[k] - price[i]) / 5.0) for k in neighbors if k != i)
    for i, neighbors in enumerate(task_neighbors)
])

west, east = lon.min() - 0.10, lon.max() + 0.10
south, north = lat.min() - 0.08, lat.max() + 0.08
x0f, y0f = lonlat_to_tile(west, north, ZOOM)
x1f, y1f = lonlat_to_tile(east, south, ZOOM)
x0, y0 = int(np.floor(x0f)), int(np.floor(y0f))
x1, y1 = int(np.floor(x1f)), int(np.floor(y1f))
canvas = Image.new("RGBA", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))

imagery = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
labels_url = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/"
    "Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
)
for tx in range(x0, x1 + 1):
    for ty in range(y0, y1 + 1):
        base = get_tile(imagery.format(z=ZOOM, y=ty, x=tx))
        try:
            overlay = get_tile(labels_url.format(z=ZOOM, y=ty, x=tx))
            base = Image.alpha_composite(base, overlay)
        except URLError:
            pass
        canvas.paste(base, ((tx - x0) * 256, (ty - y0) * 256))

map_west, map_north = tile_to_lonlat(x0, y0, ZOOM)
map_east, map_south = tile_to_lonlat(x1 + 1, y1 + 1, ZOOM)

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"
]
plt.rcParams["axes.unicode_minus"] = False


def base_axes(title):
    fig, ax = plt.subplots(figsize=(11.5, 8.6), dpi=170)
    ax.imshow(
        canvas, extent=[map_west, map_east, map_south, map_north],
        origin="upper", interpolation="bilinear"
    )
    ax.set(xlim=(west, east), ylim=(south, north), xlabel="经度", ylabel="纬度")
    ax.set_title(title, fontsize=16, pad=10)
    return fig, ax


def finish(fig, path):
    fig.text(
        0.995, 0.006,
        "底图：Esri World Imagery；边界与地名：Esri、HERE、Garmin 等",
        ha="right", va="bottom", fontsize=6.5, color="#404040"
    )
    fig.tight_layout(rect=[0, 0.022, 1, 1])
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_status_groups(ax, group, colors, group_labels, sizes=None):
    sizes = np.full(len(done), 32.0) if sizes is None else sizes
    for idx, color in enumerate(colors):
        completed = (group == idx) & (done == 1)
        failed = (group == idx) & (done == 0)
        ax.scatter(
            lon[completed], lat[completed], s=sizes[completed], marker="o",
            c=color, edgecolors="#172033", linewidths=0.5, alpha=0.90, zorder=3
        )
        ax.scatter(
            lon[failed], lat[failed], s=sizes[failed] * 1.15, marker="X",
            c=color, edgecolors="#172033", linewidths=0.65, alpha=0.98, zorder=4
        )
    category_handles = [
        Line2D([0], [0], marker="o", linestyle="", markersize=7,
               markerfacecolor=color, markeredgecolor="#172033", label=label)
        for color, label in zip(colors, group_labels)
    ]
    status_handles = [
        Line2D([0], [0], marker="o", linestyle="", markersize=7,
               markerfacecolor="#B8C0CC", markeredgecolor="#172033", label="已完成"),
        Line2D([0], [0], marker="X", linestyle="", markersize=7,
               markerfacecolor="#B8C0CC", markeredgecolor="#172033", label="未完成"),
    ]
    return category_handles, status_handles


# Cause 1: low price.
price_group = np.clip(np.digitize(price, [65, 70, 75, 80, 86]) - 1, 0, 3)
fig, ax = base_axes("原因一：低价任务与未完成状态空间重叠")
h1, hs = plot_status_groups(
    ax, price_group,
    ["#4E7CE2", "#23C985", "#FFD447", "#F25C54"],
    ["65–69.5元", "70–74.5元", "75–79.5元", "80–85元"]
)
leg = ax.legend(handles=h1, title="任务标价", loc="lower left", framealpha=0.90)
ax.add_artist(leg)
ax.legend(handles=hs, title="执行状态", loc="lower right", framealpha=0.90)
finish(fig, OUT / "cause-1-low-price-map.png")

# Cause 2: registered-member supply is not effective supply.
supply_group = np.select(
    [members_2km <= 2, members_2km <= 5, members_2km <= 10],
    [0, 1, 2], default=3
)
fig, ax = base_axes("原因二：周边会员数量与任务完成状态")
h2, hs = plot_status_groups(
    ax, supply_group,
    ["#F3E55B", "#56C7B2", "#4788D8", "#6848A8"],
    ["0–2人", "3–5人", "6–10人", "11人及以上"]
)
leg = ax.legend(handles=h2, title="2 km内会员数", loc="lower left", framealpha=0.90)
ax.add_artist(leg)
ax.legend(handles=hs, title="执行状态", loc="lower right", framealpha=0.90)
finish(fig, OUT / "cause-2-effective-supply-map.png")

# Cause 3: regional effects, represented by local failure-rate hexagons.
fig, ax = base_axes("原因三：局部未完成率揭示区域执行成本差异")
hb = ax.hexbin(
    lon, lat, C=1 - done, reduce_C_function=np.mean, gridsize=24,
    mincnt=3, cmap="YlOrRd", vmin=0, vmax=1, alpha=0.78,
    linewidths=0.45, edgecolors="#313131", zorder=3
)
ax.scatter(lon, lat, s=7, c="#172033", alpha=0.28, linewidths=0, zorder=4)
cb = fig.colorbar(hb, ax=ax, fraction=0.033, pad=0.018)
cb.set_label("局部未完成率")
finish(fig, OUT / "cause-3-regional-effect-map.png")

# Cause 4: local competition from neighbouring tasks and relative prices.
finite_q = np.quantile(competition, [0.25, 0.50, 0.75])
competition_group = np.digitize(competition, finite_q)
size = 24 + 5.5 * np.sqrt(tasks_2km + 1)
fig, ax = base_axes("原因四：局部任务竞争强度与未完成状态")
h4, hs = plot_status_groups(
    ax, competition_group,
    ["#F3E55B", "#69C6A5", "#3E89C9", "#5B3A9B"],
    ["低竞争", "中低竞争", "中高竞争", "高竞争"], sizes=size
)
leg = ax.legend(handles=h4, title="2 km局部竞争强度", loc="lower left", framealpha=0.90)
ax.add_artist(leg)
ax.legend(handles=hs, title="执行状态", loc="lower right", framealpha=0.90)
finish(fig, OUT / "cause-4-local-competition-map.png")

# Compact statistics used in the written analysis.
def grouped_stats(values, labels):
    frame = pd.DataFrame({"group": values, "done": done, "price": price})
    result = frame.groupby("group").agg(
        tasks=("done", "size"), completion_rate=("done", "mean"),
        average_price=("price", "mean")
    )
    result.index = labels
    return result

print("PRICE")
print(grouped_stats(price_group, ["65-69.5", "70-74.5", "75-79.5", "80-85"]).round(3))
print("SUPPLY")
print(grouped_stats(supply_group, ["0-2", "3-5", "6-10", "11+"]).round(3))
print("COMPETITION")
print(grouped_stats(competition_group, ["low", "mid-low", "mid-high", "high"]).round(3))
for path in sorted(OUT.glob("cause-*-map.png")):
    print(path.name, path.stat().st_size)
