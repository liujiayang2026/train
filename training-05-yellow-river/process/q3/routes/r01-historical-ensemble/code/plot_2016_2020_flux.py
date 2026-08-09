from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_DIR / "question-2" / "data" / "processed" / "daily_flux_series.csv"
FIGURES_DIR = PROJECT_DIR / "question-3" / "figures"


def get_font(size: int, bold: bool = False):
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_centered(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (bbox[2] - bbox[0]) / 2, xy[1] - (bbox[3] - bbox[1]) / 2), text, font=font, fill=fill)


def nice_number(value: float) -> str:
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    if value >= 1000:
        return f"{value:.0f}"
    if value >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}"


def make_points(dates: pd.Series, values: pd.Series, rect: tuple[int, int, int, int], ymax: float) -> list[tuple[float, float]]:
    left, top, right, bottom = rect
    start = dates.min()
    end = dates.max()
    total_days = max(1, (end - start).days)
    points = []
    for date, value in zip(dates, values):
        x = left + (date - start).days / total_days * (right - left)
        y = bottom - max(0.0, min(float(value), ymax)) / ymax * (bottom - top)
        points.append((x, y))
    return points


def draw_panel(
    draw: ImageDraw.ImageDraw,
    df: pd.DataFrame,
    value_col: str,
    smooth_col: str,
    rect: tuple[int, int, int, int],
    title: str,
    unit: str,
    raw_color: tuple[int, int, int],
    smooth_color: tuple[int, int, int],
) -> None:
    left, top, right, bottom = rect
    title_font = get_font(24, bold=True)
    label_font = get_font(15)
    tick_font = get_font(13)
    ymax = max(float(df[value_col].max()), float(df[smooth_col].max())) * 1.08
    if ymax <= 0:
        ymax = 1.0

    draw.text((left, top - 42), title, font=title_font, fill=(31, 41, 55))
    draw.text((left, top - 16), unit, font=label_font, fill=(75, 85, 99))

    for tick in range(6):
        value = ymax * tick / 5
        y = bottom - value / ymax * (bottom - top)
        draw.line((left, y, right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 72, y - 8), nice_number(value), font=tick_font, fill=(107, 114, 128))

    draw.line((left, top, left, bottom), fill=(55, 65, 81), width=2)
    draw.line((left, bottom, right, bottom), fill=(55, 65, 81), width=2)

    for year in range(2016, 2021):
        date = pd.Timestamp(datetime(year, 1, 1))
        x = left + (date - df["date"].min()).days / max(1, (df["date"].max() - df["date"].min()).days) * (right - left)
        draw.line((x, bottom, x, bottom + 7), fill=(55, 65, 81), width=1)
        draw_centered(draw, (x, bottom + 24), str(year), tick_font, (55, 65, 81))

    raw_points = make_points(df["date"], df[value_col], rect, ymax)
    smooth_points = make_points(df["date"], df[smooth_col], rect, ymax)
    if len(raw_points) > 1:
        draw.line(raw_points, fill=raw_color, width=1)
    if len(smooth_points) > 1:
        draw.line(smooth_points, fill=smooth_color, width=4)

    legend_y = top + 8
    draw.line((right - 300, legend_y, right - 270, legend_y), fill=raw_color, width=2)
    draw.text((right - 262, legend_y - 10), "日值", font=label_font, fill=(75, 85, 99))
    draw.line((right - 190, legend_y, right - 160, legend_y), fill=smooth_color, width=4)
    draw.text((right - 152, legend_y - 10), "30日平滑", font=label_font, fill=(75, 85, 99))


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(DATA_PATH, parse_dates=["date"]).sort_values("date")
    df = df[(df["date"].dt.year >= 2016) & (df["date"].dt.year <= 2020)].copy()
    df["flow_roll30"] = df["mean_flow_m3s"].rolling(30, min_periods=1, center=True).mean()
    df["sediment_flux_roll30"] = df["mean_sediment_flux_kg_s"].rolling(30, min_periods=1, center=True).mean()

    width, height = 1600, 960
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(30, bold=True)
    draw_centered(draw, (width / 2, 42), "2016-2020年水流量与沙通量日尺度折线图", title_font, (17, 24, 39))

    draw_panel(
        draw,
        df,
        "mean_flow_m3s",
        "flow_roll30",
        (120, 120, 1540, 440),
        "水流量 Q",
        "单位：m³/s",
        (147, 197, 253),
        (37, 99, 235),
    )
    draw_panel(
        draw,
        df,
        "mean_sediment_flux_kg_s",
        "sediment_flux_roll30",
        (120, 585, 1540, 905),
        "沙通量 F = Q × C",
        "单位：kg/s",
        (252, 165, 165),
        (220, 38, 38),
    )

    output = FIGURES_DIR / "flow-sediment-flux-2016-2020.png"
    image.save(output)
    print(output)


if __name__ == "__main__":
    main()
