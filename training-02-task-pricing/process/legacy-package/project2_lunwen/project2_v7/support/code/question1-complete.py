"""Question 1 complete analysis script.

Outputs:
- figures/question1-*.png
- results/question1-*.csv

The script reads the shared cleaned task table in `.analysis/tasks.csv` and the
member workbook in the project folder, builds the spatial indicators used in the
paper, writes grouped statistics, and renders the four cause maps.
"""

from __future__ import annotations

import sys
from io import BytesIO
from math import atan, cos, log, pi, radians, sinh, tan
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

QUESTION_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = QUESTION_DIR.parent
SHARED_PACKAGES = PROJECT_DIR / "shared" / "python-packages"
if SHARED_PACKAGES.exists():
    sys.path.insert(0, str(SHARED_PACKAGES))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image
from scipy.spatial import cKDTree

TASK_CSV = PROJECT_DIR / ".analysis" / "tasks.csv"
MEMBER_XLSX = next(
    path for path in PROJECT_DIR.glob("*.xlsx") if not path.name.startswith("~$")
)
FIGURES_DIR = QUESTION_DIR / "figures"
RESULTS_DIR = QUESTION_DIR / "results"
ZOOM = 9
NEIGHBOR_RADIUS_KM = 2.0
USE_ONLINE_BASEMAP = False


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


def build_blank_canvas(west, east, south, north):
    width = 1400
    height = int(width * (north - south) / max(east - west, 1e-6))
    return Image.new("RGBA", (width, max(height, 900)), "#EEF2F5")


def load_map_canvas(lon, lat):
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
    if not USE_ONLINE_BASEMAP:
        canvas = build_blank_canvas(west, east, south, north)
        return canvas, west, east, south, north, west, east, south, north
    try:
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
    except Exception:
        canvas = build_blank_canvas(west, east, south, north)
        map_west, map_east, map_south, map_north = west, east, south, north
    return canvas, west, east, south, north, map_west, map_east, map_south, map_north


def grouped_stats(values, labels, done, price):
    frame = pd.DataFrame({"group": values, "done": done, "price": price})
    result = frame.groupby("group").agg(
        tasks=("done", "size"),
        completed=("done", "sum"),
        completion_rate=("done", "mean"),
        average_price=("price", "mean"),
    )
    result.index = labels
    return result.reset_index(names="group")


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    tasks = pd.read_csv(TASK_CSV)
    members = pd.read_excel(MEMBER_XLSX)
    task_id = tasks.iloc[:, 0].astype(str).to_numpy()
    lat = tasks.iloc[:, 1].astype(float).to_numpy()
    lon = tasks.iloc[:, 2].astype(float).to_numpy()
    price = tasks.iloc[:, 3].astype(float).to_numpy()
    done = tasks.iloc[:, 4].astype(int).to_numpy()

    member_coords = members.iloc[:, 1].astype(str).str.extract(r"([0-9.]+)\s+([0-9.]+)").astype(float)
    member_lat = member_coords.iloc[:, 0].to_numpy()
    member_lon = member_coords.iloc[:, 1].to_numpy()

    lat0 = float(np.mean(lat))
    task_xy = np.column_stack((lon * 111.0 * np.cos(np.radians(lat0)), lat * 111.0))
    member_xy = np.column_stack((member_lon * 111.0 * np.cos(np.radians(lat0)), member_lat * 111.0))
    task_tree = cKDTree(task_xy)
    member_tree = cKDTree(member_xy)
    members_2km = np.array([len(x) for x in member_tree.query_ball_point(task_xy, NEIGHBOR_RADIUS_KM)])
    task_neighbors = task_tree.query_ball_point(task_xy, NEIGHBOR_RADIUS_KM)
    tasks_2km = np.array([max(0, len(x) - 1) for x in task_neighbors])
    competition = np.array([
        sum(np.exp((price[k] - price[i]) / 5.0) for k in neighbors if k != i)
        for i, neighbors in enumerate(task_neighbors)
    ])

    indicators = pd.DataFrame({
        "task_id": task_id,
        "latitude": lat,
        "longitude": lon,
        "price": price,
        "completed": done,
        "members_2km": members_2km,
        "tasks_2km": tasks_2km,
        "competition_index": competition,
    })
    indicators.to_csv(RESULTS_DIR / "question1-spatial-indicators.csv", index=False, encoding="utf-8-sig")

    price_group = np.clip(np.digitize(price, [65, 70, 75, 80, 86]) - 1, 0, 3)
    supply_group = np.select([members_2km <= 2, members_2km <= 5, members_2km <= 10], [0, 1, 2], default=3)
    finite_q = np.quantile(competition, [0.25, 0.50, 0.75])
    competition_group = np.digitize(competition, finite_q)

    grouped_stats(price_group, ["65-69.5", "70-74.5", "75-79.5", "80-85"], done, price).to_csv(
        RESULTS_DIR / "question1-price-group-stats.csv", index=False, encoding="utf-8-sig"
    )
    grouped_stats(supply_group, ["0-2", "3-5", "6-10", "11+"], done, price).to_csv(
        RESULTS_DIR / "question1-supply-group-stats.csv", index=False, encoding="utf-8-sig"
    )
    grouped_stats(competition_group, ["low", "mid-low", "mid-high", "high"], done, price).to_csv(
        RESULTS_DIR / "question1-competition-group-stats.csv", index=False, encoding="utf-8-sig"
    )

    canvas, west, east, south, north, map_west, map_east, map_south, map_north = load_map_canvas(lon, lat)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    def base_axes(title):
        fig, ax = plt.subplots(figsize=(11.5, 8.6), dpi=170)
        ax.imshow(canvas, extent=[map_west, map_east, map_south, map_north], origin="upper", interpolation="bilinear")
        ax.set(xlim=(west, east), ylim=(south, north), xlabel="经度", ylabel="纬度")
        ax.set_title(title, fontsize=16, pad=10)
        return fig, ax

    def finish(fig, filename):
        fig.tight_layout(rect=[0, 0.022, 1, 1])
        fig.savefig(FIGURES_DIR / filename, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close(fig)

    def plot_status_groups(ax, group, colors, labels, sizes=None):
        sizes = np.full(len(done), 32.0) if sizes is None else sizes
        for idx, color in enumerate(colors):
            completed = (group == idx) & (done == 1)
            failed = (group == idx) & (done == 0)
            ax.scatter(lon[completed], lat[completed], s=sizes[completed], marker="o", c=color, edgecolors="#172033", linewidths=0.5, alpha=0.90, zorder=3)
            ax.scatter(lon[failed], lat[failed], s=sizes[failed] * 1.15, marker="X", c=color, edgecolors="#172033", linewidths=0.65, alpha=0.98, zorder=4)
        category_handles = [Line2D([0], [0], marker="o", linestyle="", markersize=7, markerfacecolor=color, markeredgecolor="#172033", label=label) for color, label in zip(colors, labels)]
        status_handles = [
            Line2D([0], [0], marker="o", linestyle="", markersize=7, markerfacecolor="#B8C0CC", markeredgecolor="#172033", label="已完成"),
            Line2D([0], [0], marker="X", linestyle="", markersize=7, markerfacecolor="#B8C0CC", markeredgecolor="#172033", label="未完成"),
        ]
        return category_handles, status_handles

    fig, ax = base_axes("原因一：低价任务与未完成状态空间重叠")
    h, hs = plot_status_groups(ax, price_group, ["#4E7CE2", "#23C985", "#FFD447", "#F25C54"], ["65-69.5元", "70-74.5元", "75-79.5元", "80-85元"])
    leg = ax.legend(handles=h, title="任务标价", loc="lower left", framealpha=0.90)
    ax.add_artist(leg)
    ax.legend(handles=hs, title="执行状态", loc="lower right", framealpha=0.90)
    finish(fig, "question1-cause-1-low-price-map.png")

    fig, ax = base_axes("原因二：周边会员数量与任务完成状态")
    h, hs = plot_status_groups(ax, supply_group, ["#F3E55B", "#56C7B2", "#4788D8", "#6848A8"], ["0-2人", "3-5人", "6-10人", "11人及以上"])
    leg = ax.legend(handles=h, title="2 km内会员数", loc="lower left", framealpha=0.90)
    ax.add_artist(leg)
    ax.legend(handles=hs, title="执行状态", loc="lower right", framealpha=0.90)
    finish(fig, "question1-cause-2-effective-supply-map.png")

    fig, ax = base_axes("区域未完成率差异：具体机制仍需外部数据检验")
    hb = ax.hexbin(lon, lat, C=1 - done, reduce_C_function=np.mean, gridsize=24, mincnt=3, cmap="YlOrRd", vmin=0, vmax=1, alpha=0.78, linewidths=0.45, edgecolors="#313131", zorder=3)
    ax.scatter(lon, lat, s=7, c="#172033", alpha=0.28, linewidths=0, zorder=4)
    cb = fig.colorbar(hb, ax=ax, fraction=0.033, pad=0.018)
    cb.set_label("局部未完成率")
    finish(fig, "question1-cause-3-regional-effect-map.png")

    size = 24 + 5.5 * np.sqrt(tasks_2km + 1)
    fig, ax = base_axes("原因四：局部任务竞争强度与未完成状态")
    h, hs = plot_status_groups(ax, competition_group, ["#F3E55B", "#69C6A5", "#3E89C9", "#5B3A9B"], ["低竞争", "中低竞争", "中高竞争", "高竞争"], sizes=size)
    leg = ax.legend(handles=h, title="2 km局部竞争强度", loc="lower left", framealpha=0.90)
    ax.add_artist(leg)
    ax.legend(handles=hs, title="执行状态", loc="lower right", framealpha=0.90)
    finish(fig, "question1-cause-4-local-competition-map.png")

    print("Question 1 complete.")
    print(f"Outputs: {RESULTS_DIR} and {FIGURES_DIR}")


if __name__ == "__main__":
    main()
