from io import BytesIO
from math import atan, cos, exp, log, pi, radians, sinh, tan
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from PIL import Image


ROOT = Path(r"D:\jianmo\project 2\B")
OUT = ROOT / "问题一_历史任务空间分布图.png"
ZOOM = 9
PAD_LON = 0.10
PAD_LAT = 0.08


def lonlat_to_tile(lon, lat, zoom):
    n = 2**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = radians(lat)
    y = (1.0 - log(tan(lat_rad) + 1.0 / cos(lat_rad)) / pi) / 2.0 * n
    return x, y


def tile_to_lonlat(x, y, zoom):
    n = 2**zoom
    lon = x / n * 360.0 - 180.0
    lat = np.degrees(atan(sinh(pi * (1 - 2 * y / n))))
    return lon, lat


def get_tile(url):
    request = Request(url, headers={"User-Agent": "CUMCM academic map rendering/1.0"})
    with urlopen(request, timeout=30) as response:
        return Image.open(BytesIO(response.read())).convert("RGBA")


tasks = pd.read_csv(ROOT / ".analysis" / "tasks.csv")
lat = tasks.iloc[:, 1].astype(float).to_numpy()
lon = tasks.iloc[:, 2].astype(float).to_numpy()
price = tasks.iloc[:, 3].astype(float).to_numpy()
done = tasks.iloc[:, 4].astype(int).to_numpy()

west, east = lon.min() - PAD_LON, lon.max() + PAD_LON
south, north = lat.min() - PAD_LAT, lat.max() + PAD_LAT
x0f, y0f = lonlat_to_tile(west, north, ZOOM)
x1f, y1f = lonlat_to_tile(east, south, ZOOM)
x0, y0 = int(np.floor(x0f)), int(np.floor(y0f))
x1, y1 = int(np.floor(x1f)), int(np.floor(y1f))

canvas = Image.new("RGBA", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))

imagery = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
labels = (
    "https://services.arcgisonline.com/ArcGIS/rest/services/"
    "Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"
)

for tx in range(x0, x1 + 1):
    for ty in range(y0, y1 + 1):
        base = get_tile(imagery.format(z=ZOOM, y=ty, x=tx))
        try:
            overlay = get_tile(labels.format(z=ZOOM, y=ty, x=tx))
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

fig, ax = plt.subplots(figsize=(13.2, 10.0), dpi=180)
ax.imshow(
    canvas,
    extent=[map_west, map_east, map_south, map_north],
    origin="upper",
    interpolation="bilinear",
)

bins = np.array([65, 70, 75, 80, 86])
labels_text = ["65–69.5 元", "70–74.5 元", "75–79.5 元", "80–85 元"]
colors = ["#4E7CE2", "#24C96B", "#FFE04B", "#F15A4A"]
groups = np.clip(np.digitize(price, bins, right=False) - 1, 0, 3)

for group, color in enumerate(colors):
    mask_done = (groups == group) & (done == 1)
    mask_fail = (groups == group) & (done == 0)
    ax.scatter(
        lon[mask_done], lat[mask_done], s=34, marker="o",
        c=color, edgecolors="#172033", linewidths=0.55, alpha=0.92, zorder=3
    )
    ax.scatter(
        lon[mask_fail], lat[mask_fail], s=43, marker="X",
        c=color, edgecolors="#172033", linewidths=0.65, alpha=0.98, zorder=4
    )

ax.set_xlim(west, east)
ax.set_ylim(south, north)
ax.set_xlabel("经度")
ax.set_ylabel("纬度")
ax.set_title("历史任务价格与完成状态空间分布", pad=12, fontsize=16)
ax.grid(False)

price_legend = [
    Line2D([0], [0], marker="o", linestyle="", markersize=8,
           markerfacecolor=c, markeredgecolor="#172033", label=label)
    for c, label in zip(colors, labels_text)
]
status_legend = [
    Line2D([0], [0], marker="o", linestyle="", markersize=8,
           markerfacecolor="#B8C0CC", markeredgecolor="#172033", label="已完成"),
    Line2D([0], [0], marker="X", linestyle="", markersize=8,
           markerfacecolor="#B8C0CC", markeredgecolor="#172033", label="未完成"),
]
legend1 = ax.legend(
    handles=price_legend, title="任务标价", loc="lower left",
    frameon=True, framealpha=0.90, borderpad=0.8
)
ax.add_artist(legend1)
ax.legend(
    handles=status_legend, title="执行状态", loc="lower right",
    frameon=True, framealpha=0.90, borderpad=0.8
)

fig.text(
    0.995, 0.008,
    "底图：Esri World Imagery；边界与地名：Esri、HERE、Garmin 等",
    ha="right", va="bottom", fontsize=7, color="#404040"
)
fig.tight_layout(rect=[0, 0.025, 1, 1])
fig.savefig(OUT, dpi=300, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(OUT)
print(f"{OUT.stat().st_size} bytes; {len(tasks)} tasks; tiles={(x1-x0+1)}x{(y1-y0+1)}")
