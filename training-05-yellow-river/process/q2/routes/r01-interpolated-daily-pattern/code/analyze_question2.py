from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


PROJECT_DIR = Path(__file__).resolve().parents[2]
Q1_DIR = PROJECT_DIR / "question-1"
PROCESSED_DATA_DIR = PROJECT_DIR / "question-2" / "data" / "processed"
RESULTS_DIR = PROJECT_DIR / "question-2" / "results"
DOCS_DIR = PROJECT_DIR / "question-2" / "docs"
FIGURES_DIR = PROJECT_DIR / "question-2" / "figures"
QA_DIR = PROJECT_DIR / "question-2" / "qa"
SECONDS_PER_DAY = 24 * 3600


def load_question1_series() -> pd.DataFrame:
    candidates = [
        Q1_DIR / "data" / "processed" / "cleaned_hydro_timeseries.csv",
        Q1_DIR / "results" / "cleaned_hydro_timeseries.csv",
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if path is None:
        expected = "\n".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"Missing required question 1 cleaned series. Tried:\n{expected}")
    df = pd.read_csv(path, parse_dates=["datetime"])
    needed = ["datetime", "flow_m3s", "sediment_used_kgm3", "sediment_flux_kg_s"]
    missing = [col for col in needed if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in question 1 output: {missing}")
    df = df[needed].sort_values("datetime").drop_duplicates("datetime")
    df = df[(df["datetime"] >= pd.Timestamp("2016-01-01")) & (df["datetime"] < pd.Timestamp("2022-01-01"))]
    return df


def build_daily_series(df: pd.DataFrame) -> pd.DataFrame:
    indexed = df.set_index("datetime").sort_index()
    full_hours = pd.date_range("2016-01-01 00:00:00", "2022-01-01 00:00:00", freq="1h")
    expanded = indexed.reindex(indexed.index.union(full_hours)).sort_index()
    expanded[["flow_m3s", "sediment_used_kgm3", "sediment_flux_kg_s"]] = expanded[
        ["flow_m3s", "sediment_used_kgm3", "sediment_flux_kg_s"]
    ].interpolate(method="time", limit_direction="both")
    expanded = expanded.loc[full_hours]
    hourly = expanded.iloc[:-1]

    daily = hourly.resample("D").mean()
    daily.index.name = "date"
    daily = daily.rename(
        columns={
            "flow_m3s": "mean_flow_m3s",
            "sediment_used_kgm3": "mean_sediment_kgm3",
            "sediment_flux_kg_s": "mean_sediment_flux_kg_s",
        }
    )
    daily["water_volume_m3"] = daily["mean_flow_m3s"] * SECONDS_PER_DAY
    daily["sediment_mass_kg"] = daily["mean_sediment_flux_kg_s"] * SECONDS_PER_DAY
    daily["water_volume_1e8_m3"] = daily["water_volume_m3"] / 1e8
    daily["sediment_mass_1e4_t"] = daily["sediment_mass_kg"] / 1e7
    daily["year"] = daily.index.year
    daily["month"] = daily.index.month
    daily["day_of_year"] = daily.index.dayofyear
    return daily.reset_index()


def seasonal_summary(daily: pd.DataFrame) -> pd.DataFrame:
    total_water = daily["water_volume_m3"].sum()
    total_sediment = daily["sediment_mass_kg"].sum()
    monthly = (
        daily.groupby("month", as_index=False)
        .agg(
            days=("date", "size"),
            mean_flow_m3s=("mean_flow_m3s", "mean"),
            mean_sediment_kgm3=("mean_sediment_kgm3", "mean"),
            mean_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "mean"),
            water_volume_1e8_m3=("water_volume_1e8_m3", "sum"),
            sediment_mass_1e4_t=("sediment_mass_1e4_t", "sum"),
        )
    )
    monthly["water_share"] = monthly["water_volume_1e8_m3"] * 1e8 / total_water
    monthly["sediment_share"] = monthly["sediment_mass_1e4_t"] * 1e7 / total_sediment
    monthly["sediment_to_water_share_ratio"] = monthly["sediment_share"] / monthly["water_share"]
    return monthly


def annual_summary(daily: pd.DataFrame) -> pd.DataFrame:
    annual = (
        daily.groupby("year", as_index=False)
        .agg(
            days=("date", "size"),
            water_volume_1e8_m3=("water_volume_1e8_m3", "sum"),
            sediment_mass_1e4_t=("sediment_mass_1e4_t", "sum"),
            mean_flow_m3s=("mean_flow_m3s", "mean"),
            mean_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "mean"),
            max_daily_flow_m3s=("mean_flow_m3s", "max"),
            max_daily_sediment_flux_kg_s=("mean_sediment_flux_kg_s", "max"),
        )
    )
    annual["water_yoy_change"] = annual["water_volume_1e8_m3"].pct_change()
    annual["sediment_yoy_change"] = annual["sediment_mass_1e4_t"].pct_change()
    return annual


def select_events(events: pd.DataFrame, score_col: str, min_gap_days: int = 20, top_n: int = 15) -> pd.DataFrame:
    selected = []
    used_dates: list[pd.Timestamp] = []
    for _, row in events.sort_values(score_col, ascending=False).iterrows():
        date = pd.Timestamp(row["date"])
        if all(abs((date - used_date).days) >= min_gap_days for used_date in used_dates):
            selected.append(row)
            used_dates.append(date)
        if len(selected) >= top_n:
            break
    if not selected:
        return events.head(0)
    return pd.DataFrame(selected).sort_values("date").reset_index(drop=True)


def abrupt_change_events(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.sort_values("date").copy()
    data["log_flow"] = np.log1p(data["mean_flow_m3s"])
    data["log_sediment_flux"] = np.log1p(data["mean_sediment_flux_kg_s"])
    window = 7
    for source, prefix in [("log_flow", "flow"), ("log_sediment_flux", "sediment")]:
        before = data[source].shift(1).rolling(window).mean()
        after = data[source].rolling(window).mean().shift(-window + 1)
        contrast = after - before
        scale = contrast.std(skipna=True)
        if not np.isfinite(scale) or scale == 0:
            scale = 1.0
        data[f"{prefix}_contrast"] = contrast
        data[f"{prefix}_contrast_z"] = contrast / scale
        data[f"{prefix}_daily_log_diff"] = data[source].diff()
    data["abrupt_score"] = np.maximum(data["flow_contrast_z"].abs(), data["sediment_contrast_z"].abs())
    data["main_direction"] = np.where(
        data["sediment_contrast_z"].abs() >= data["flow_contrast_z"].abs(),
        np.where(data["sediment_contrast_z"] >= 0, "sediment_rise", "sediment_fall"),
        np.where(data["flow_contrast_z"] >= 0, "flow_rise", "flow_fall"),
    )
    events = data.dropna(subset=["abrupt_score"]).copy()
    events = events[
        [
            "date",
            "year",
            "month",
            "mean_flow_m3s",
            "mean_sediment_kgm3",
            "mean_sediment_flux_kg_s",
            "flow_contrast_z",
            "sediment_contrast_z",
            "abrupt_score",
            "main_direction",
        ]
    ]
    return select_events(events, "abrupt_score")


def periodogram(series: pd.Series, name: str) -> pd.DataFrame:
    y = np.log1p(series.to_numpy(dtype=float))
    mask = np.isfinite(y)
    y = pd.Series(y).interpolate(limit_direction="both").to_numpy()
    x = np.arange(len(y), dtype=float)
    coef = np.polyfit(x[mask], y[mask], deg=1)
    detrended = y - np.polyval(coef, x)
    detrended = detrended - detrended.mean()
    window = np.hanning(len(detrended))
    spectrum = np.fft.rfft(detrended * window)
    freq = np.fft.rfftfreq(len(detrended), d=1.0)
    power = np.abs(spectrum) ** 2
    valid = freq > 0
    periods = 1 / freq[valid]
    power = power[valid]
    band = (periods >= 20) & (periods <= 800)
    periods = periods[band]
    power = power[band]
    order = np.argsort(power)[::-1]
    rows = []
    total_power = power.sum()
    for idx in order[:10]:
        rows.append(
            {
                "series": name,
                "period_days": float(periods[idx]),
                "period_months": float(periods[idx] / 30.4375),
                "relative_power": float(power[idx] / total_power) if total_power else np.nan,
            }
        )
    return pd.DataFrame(rows)


def autocorrelation_lags(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    lags = [7, 15, 30, 60, 90, 120, 180, 365]
    for col, name in [
        ("mean_flow_m3s", "water_flux"),
        ("mean_sediment_flux_kg_s", "sediment_flux"),
    ]:
        y = np.log1p(daily[col].to_numpy(dtype=float))
        y = y - np.nanmean(y)
        for lag in lags:
            if lag >= len(y):
                continue
            a = y[:-lag]
            b = y[lag:]
            corr = np.corrcoef(a, b)[0, 1]
            rows.append({"series": name, "lag_days": lag, "autocorrelation": float(corr)})
    return pd.DataFrame(rows)


def high_flux_concentration(daily: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month_set, label in [([6, 7], "jun_jul"), ([6, 7, 8, 9, 10], "jun_oct"), ([7], "jul")]:
        part = daily[daily["month"].isin(month_set)]
        rows.append(
            {
                "period": label,
                "days": int(len(part)),
                "water_share": float(part["water_volume_m3"].sum() / daily["water_volume_m3"].sum()),
                "sediment_share": float(part["sediment_mass_kg"].sum() / daily["sediment_mass_kg"].sum()),
                "mean_flow_m3s": float(part["mean_flow_m3s"].mean()),
                "mean_sediment_flux_kg_s": float(part["mean_sediment_flux_kg_s"].mean()),
            }
        )
    return pd.DataFrame(rows)


def dataframe_to_markdown(df: pd.DataFrame, floatfmt: str = ".4g") -> str:
    headers = list(df.columns)
    body = []
    for _, row in df.iterrows():
        values = []
        for value in row:
            if isinstance(value, pd.Timestamp):
                values.append(value.strftime("%Y-%m-%d"))
            elif isinstance(value, (float, np.floating)):
                values.append(format(float(value), floatfmt))
            else:
                values.append(str(value))
        body.append(values)
    widths = [
        max(len(str(header)), *(len(row[index]) for row in body)) if body else len(str(header))
        for index, header in enumerate(headers)
    ]
    lines = [
        "| " + " | ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers)) + " |",
        "| " + " | ".join("-" * widths[index] for index in range(len(headers))) + " |",
    ]
    lines.extend(
        "| " + " | ".join(value.ljust(widths[index]) for index, value in enumerate(row)) + " |"
        for row in body
    )
    return "\n".join(lines)


def write_svg(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def draw_centered_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, fill) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = xy[0] - (bbox[2] - bbox[0]) / 2
    y = xy[1] - (bbox[3] - bbox[1]) / 2
    draw.text((x, y), text, font=font, fill=fill)


def save_bar_chart_png(
    path: Path,
    labels: list[str],
    series: list[tuple[str, list[float], tuple[int, int, int]]],
    title: str,
    ylabel: str,
    width: int = 1200,
    height: int = 720,
) -> None:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(28, bold=True)
    axis_font = get_font(16)
    tick_font = get_font(14)
    legend_font = get_font(16)
    left, right, top, bottom = 105, 45, 82, 105
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_value = max(max(values) for _, values, _ in series)
    y_max = max_value * 1.15 if max_value else 1.0
    draw_centered_text(draw, (width / 2, 36), title, title_font, (31, 41, 55))
    draw.text((left, top - 30), ylabel, font=axis_font, fill=(55, 65, 81))
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_h - value / y_max * plot_h
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 12 - 8 * len(f"{value:.0f}"), y - 8), f"{value:.0f}", font=tick_font, fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_h), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill=(55, 65, 81), width=2)
    group_w = plot_w / len(labels)
    bar_gap = 7
    bar_w = min(34, (group_w - 22) / len(series) - bar_gap)
    for i, label in enumerate(labels):
        group_x = left + i * group_w
        center = group_x + group_w / 2
        draw_centered_text(draw, (center, top + plot_h + 28), label, tick_font, (55, 65, 81))
        start_x = center - (len(series) * bar_w + (len(series) - 1) * bar_gap) / 2
        for j, (_, values, color) in enumerate(series):
            value = values[i]
            bar_h = value / y_max * plot_h
            x = start_x + j * (bar_w + bar_gap)
            y = top + plot_h - bar_h
            draw.rounded_rectangle((x, y, x + bar_w, top + plot_h), radius=3, fill=color)
    legend_x = left
    legend_y = height - 45
    for name, _, color in series:
        draw.rounded_rectangle((legend_x, legend_y - 12, legend_x + 18, legend_y + 6), radius=3, fill=color)
        draw.text((legend_x + 27, legend_y - 14), name, font=legend_font, fill=(55, 65, 81))
        legend_x += 250
    image.save(path)


def save_line_chart_png(
    path: Path,
    labels: list[str],
    series: list[tuple[str, list[float], tuple[int, int, int]]],
    title: str,
    ylabel: str,
    width: int = 1200,
    height: int = 720,
) -> None:
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font = get_font(28, bold=True)
    axis_font = get_font(16)
    tick_font = get_font(14)
    legend_font = get_font(16)
    left, right, top, bottom = 105, 45, 82, 105
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_value = max(max(values) for _, values, _ in series)
    y_max = max_value * 1.15 if max_value else 1.0
    draw_centered_text(draw, (width / 2, 36), title, title_font, (31, 41, 55))
    draw.text((left, top - 30), ylabel, font=axis_font, fill=(55, 65, 81))
    for tick in range(6):
        value = y_max * tick / 5
        y = top + plot_h - value / y_max * plot_h
        draw.line((left, y, width - right, y), fill=(229, 231, 235), width=1)
        draw.text((left - 12 - 8 * len(f"{value:.0f}"), y - 8), f"{value:.0f}", font=tick_font, fill=(107, 114, 128))
    draw.line((left, top, left, top + plot_h), fill=(55, 65, 81), width=2)
    draw.line((left, top + plot_h, width - right, top + plot_h), fill=(55, 65, 81), width=2)
    step = plot_w / (len(labels) - 1)
    for i, label in enumerate(labels):
        x = left + i * step
        draw_centered_text(draw, (x, top + plot_h + 28), label, tick_font, (55, 65, 81))
    for name, values, color in series:
        points = []
        for i, value in enumerate(values):
            x = left + i * step
            y = top + plot_h - value / y_max * plot_h
            points.append((x, y))
        draw.line(points, fill=color, width=4, joint="curve")
        for x, y in points:
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=color)
    legend_x = left
    legend_y = height - 45
    for name, _, color in series:
        draw.line((legend_x, legend_y - 4, legend_x + 32, legend_y - 4), fill=color, width=4)
        draw.text((legend_x + 42, legend_y - 14), name, font=legend_font, fill=(55, 65, 81))
        legend_x += 300
    image.save(path)


def bar_chart_svg(
    labels: list[str],
    series: list[tuple[str, list[float], str]],
    title: str,
    ylabel: str,
    width: int = 980,
    height: int = 520,
) -> str:
    margin_left, margin_right, margin_top, margin_bottom = 86, 36, 62, 82
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    max_value = max(max(values) for _, values, _ in series)
    y_max = max_value * 1.15 if max_value else 1.0
    group_w = plot_w / len(labels)
    bar_gap = 5
    bar_w = min(26, (group_w - 18) / len(series) - bar_gap)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-family="Arial, sans-serif" fill="#1f2937">{title}</text>',
        f'<text x="22" y="{height/2}" transform="rotate(-90 22 {height/2})" text-anchor="middle" font-size="14" font-family="Arial, sans-serif" fill="#374151">{ylabel}</text>',
    ]
    for tick in range(6):
        value = y_max * tick / 5
        y = margin_top + plot_h - value / y_max * plot_h
        parts.append(f'<line x1="{margin_left}" y1="{y:.2f}" x2="{width-margin_right}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{margin_left-10}" y="{y+4:.2f}" text-anchor="end" font-size="12" font-family="Arial, sans-serif" fill="#6b7280">{value:.0f}</text>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#374151" stroke-width="1.2"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{width-margin_right}" y2="{margin_top+plot_h}" stroke="#374151" stroke-width="1.2"/>')
    for i, label in enumerate(labels):
        group_x = margin_left + i * group_w
        center = group_x + group_w / 2
        parts.append(f'<text x="{center:.2f}" y="{margin_top+plot_h+28}" text-anchor="middle" font-size="12" font-family="Arial, sans-serif" fill="#374151">{label}</text>')
        start_x = center - (len(series) * bar_w + (len(series) - 1) * bar_gap) / 2
        for j, (_, values, color) in enumerate(series):
            value = values[i]
            bar_h = value / y_max * plot_h
            x = start_x + j * (bar_w + bar_gap)
            y = margin_top + plot_h - bar_h
            parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_w:.2f}" height="{bar_h:.2f}" fill="{color}" rx="2"/>')
    legend_x = margin_left
    legend_y = height - 28
    for name, _, color in series:
        parts.append(f'<rect x="{legend_x}" y="{legend_y-12}" width="14" height="14" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{legend_x+20}" y="{legend_y}" font-size="13" font-family="Arial, sans-serif" fill="#374151">{name}</text>')
        legend_x += 150
    parts.append("</svg>")
    return "\n".join(parts)


def line_chart_svg(
    labels: list[str],
    series: list[tuple[str, list[float], str]],
    title: str,
    ylabel: str,
    width: int = 980,
    height: int = 520,
) -> str:
    margin_left, margin_right, margin_top, margin_bottom = 86, 36, 62, 82
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    max_value = max(max(values) for _, values, _ in series)
    y_max = max_value * 1.15 if max_value else 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{width/2}" y="30" text-anchor="middle" font-size="22" font-family="Arial, sans-serif" fill="#1f2937">{title}</text>',
        f'<text x="22" y="{height/2}" transform="rotate(-90 22 {height/2})" text-anchor="middle" font-size="14" font-family="Arial, sans-serif" fill="#374151">{ylabel}</text>',
    ]
    for tick in range(6):
        value = y_max * tick / 5
        y = margin_top + plot_h - value / y_max * plot_h
        parts.append(f'<line x1="{margin_left}" y1="{y:.2f}" x2="{width-margin_right}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{margin_left-10}" y="{y+4:.2f}" text-anchor="end" font-size="12" font-family="Arial, sans-serif" fill="#6b7280">{value:.0f}</text>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top+plot_h}" stroke="#374151" stroke-width="1.2"/>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top+plot_h}" x2="{width-margin_right}" y2="{margin_top+plot_h}" stroke="#374151" stroke-width="1.2"/>')
    step = plot_w / (len(labels) - 1)
    for i, label in enumerate(labels):
        x = margin_left + i * step
        parts.append(f'<text x="{x:.2f}" y="{margin_top+plot_h+28}" text-anchor="middle" font-size="12" font-family="Arial, sans-serif" fill="#374151">{label}</text>')
    for name, values, color in series:
        points = []
        for i, value in enumerate(values):
            x = margin_left + i * step
            y = margin_top + plot_h - value / y_max * plot_h
            points.append(f"{x:.2f},{y:.2f}")
        parts.append(f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="3"/>')
        for point in points:
            x, y = point.split(",")
            parts.append(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')
    legend_x = margin_left
    legend_y = height - 28
    for name, _, color in series:
        parts.append(f'<line x1="{legend_x}" y1="{legend_y-6}" x2="{legend_x+22}" y2="{legend_y-6}" stroke="{color}" stroke-width="3"/>')
        parts.append(f'<text x="{legend_x+30}" y="{legend_y}" font-size="13" font-family="Arial, sans-serif" fill="#374151">{name}</text>')
        legend_x += 190
    parts.append("</svg>")
    return "\n".join(parts)


def write_seasonal_figures(monthly: pd.DataFrame) -> dict[str, Path]:
    labels = [f"{int(month)}" for month in monthly["month"]]
    water_share_pct = (monthly["water_share"] * 100).tolist()
    sediment_share_pct = (monthly["sediment_share"] * 100).tolist()
    mean_flow = monthly["mean_flow_m3s"].tolist()
    mean_sediment_flux = monthly["mean_sediment_flux_kg_s"].tolist()
    mean_flow_norm = (monthly["mean_flow_m3s"] / monthly["mean_flow_m3s"].max() * 100).tolist()
    mean_sediment_norm = (
        monthly["mean_sediment_flux_kg_s"] / monthly["mean_sediment_flux_kg_s"].max() * 100
    ).tolist()
    paths = {
        "monthly_share": FIGURES_DIR / "monthly-water-sediment-share.png",
        "monthly_flux_norm": FIGURES_DIR / "monthly-normalized-flux.png",
        "monthly_absolute_flux": FIGURES_DIR / "monthly-absolute-flux.png",
    }
    save_bar_chart_png(
        paths["monthly_share"],
        labels,
        [
            ("water share (%)", water_share_pct, (37, 99, 235)),
            ("sediment share (%)", sediment_share_pct, (220, 38, 38)),
        ],
        "Monthly Water and Sediment Contribution",
        "share (%)",
    )
    save_line_chart_png(
        paths["monthly_flux_norm"],
        labels,
        [
            ("mean flow index", mean_flow_norm, (37, 99, 235)),
            ("mean sediment flux index", mean_sediment_norm, (220, 38, 38)),
        ],
        "Monthly Normalized Water-Sediment Flux",
        "index (max=100)",
    )
    save_bar_chart_png(
        paths["monthly_absolute_flux"],
        labels,
        [
            ("mean flow (m3/s)", mean_flow, (37, 99, 235)),
            ("mean sediment flux (kg/s)", mean_sediment_flux, (220, 38, 38)),
        ],
        "Monthly Mean Flow and Sediment Flux",
        "monthly mean",
    )
    return paths


def write_report(
    daily: pd.DataFrame,
    annual: pd.DataFrame,
    monthly: pd.DataFrame,
    concentration: pd.DataFrame,
    events: pd.DataFrame,
    periods: pd.DataFrame,
    acf: pd.DataFrame,
    figure_paths: dict[str, Path],
) -> None:
    top_periods = periods.groupby("series").head(5).reset_index(drop=True)
    key_acf = acf[acf["lag_days"].isin([30, 90, 180, 365])]
    top_events = events.sort_values("abrupt_score", ascending=False).head(8).sort_values("date")
    lines = [
        "# 问题二初步分析",
        "",
        "本分析沿用问题一补全后的含沙量序列，定义水通量为流量 `Q(t)`，沙通量为 `Q(t)C(t)`。",
        "为减少原始不等间隔采样的影响，先插值到小时尺度，再聚合为日尺度序列进行突变性、季节性和周期性分析。",
        "",
        "## 年际变化",
        "",
        dataframe_to_markdown(
            annual[
                [
                    "year",
                    "water_volume_1e8_m3",
                    "sediment_mass_1e4_t",
                    "mean_flow_m3s",
                    "mean_sediment_flux_kg_s",
                    "water_yoy_change",
                    "sediment_yoy_change",
                ]
            ],
            floatfmt=".5g",
        ),
        "",
        "## 季节性",
        "",
        "按月份累计看，水沙通量高度集中在汛期，尤其是 6-10 月。沙通量的季节集中程度强于水通量。",
        "",
        f"![monthly share](../figures/{figure_paths['monthly_share'].name})",
        "",
        f"![monthly normalized flux](../figures/{figure_paths['monthly_flux_norm'].name})",
        "",
        "12 个月完整季节性统计如下：",
        "",
        dataframe_to_markdown(
            monthly[
                [
                    "month",
                    "mean_flow_m3s",
                    "mean_sediment_flux_kg_s",
                    "water_share",
                    "sediment_share",
                    "sediment_to_water_share_ratio",
                ]
            ],
            floatfmt=".5g",
        ),
        "",
        "从全年月份对比可见，1-5 月水沙通量整体较低，6 月开始明显抬升，7 月达到最集中输沙阶段，8-10 月仍保持较高水平，11-12 月逐步回落。与水量相比，排沙量在 7-9 月的占比更高，说明泥沙输移对汛期洪峰更敏感。",
        "",
        "汛期集中度：",
        "",
        dataframe_to_markdown(concentration, floatfmt=".5g"),
        "",
        "## 突变性",
        "",
        "采用 7 日前后滑动均值差构造突变得分。高得分日期通常对应汛期涨水、落水或调水调沙过程前后的快速变化。",
        "",
        dataframe_to_markdown(
            top_events[
                [
                    "date",
                    "main_direction",
                    "mean_flow_m3s",
                    "mean_sediment_flux_kg_s",
                    "flow_contrast_z",
                    "sediment_contrast_z",
                    "abrupt_score",
                ]
            ],
            floatfmt=".5g",
        ),
        "",
        "## 周期性",
        "",
        "对日尺度 `log(1+x)` 序列去趋势后进行频谱分析，并补充典型滞后自相关。结果显示水通量和沙通量都存在明显年周期；其他较强峰值多分布在 8-24 个月附近，反映汛期时点差异和年际调制。30 日、90 日自相关为正，说明洪峰过程还具有季节内持续性。",
        "",
        dataframe_to_markdown(top_periods, floatfmt=".5g"),
        "",
        "典型滞后自相关：",
        "",
        dataframe_to_markdown(key_acf, floatfmt=".5g"),
        "",
        "## 初步结论",
        "",
        "1. 2018 年以后水通量和沙通量较 2016-2017 年显著增大，2020 年沙通量达到高值。",
        "2. 水沙通量具有强季节性，6-10 月贡献了主要水量和绝大部分排沙量，7 月最为突出。",
        "3. 突变事件主要集中在汛期和调水调沙相关时段，表现为短时间内流量和沙通量同步跃升或回落。",
        "4. 周期性上，年周期最稳定；沙通量与水通量的主周期接近，但沙通量在汛期突变中放大更明显，说明泥沙输移对洪峰过程更敏感。",
        "",
    ]
    (DOCS_DIR / "question2-analysis.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    QA_DIR.mkdir(parents=True, exist_ok=True)

    source = load_question1_series()
    daily = build_daily_series(source)
    monthly = seasonal_summary(daily)
    annual = annual_summary(daily)
    events = abrupt_change_events(daily)
    periods = pd.concat(
        [
            periodogram(daily["mean_flow_m3s"], "water_flux"),
            periodogram(daily["mean_sediment_flux_kg_s"], "sediment_flux"),
        ],
        ignore_index=True,
    )
    acf = autocorrelation_lags(daily)
    concentration = high_flux_concentration(daily)
    figure_paths = write_seasonal_figures(monthly)

    daily.to_csv(PROCESSED_DATA_DIR / "daily_flux_series.csv", index=False, encoding="utf-8-sig")
    annual.to_csv(RESULTS_DIR / "annual_flux_pattern.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(RESULTS_DIR / "monthly_flux_summary.csv", index=False, encoding="utf-8-sig")
    events.to_csv(QA_DIR / "abrupt_change_events.csv", index=False, encoding="utf-8-sig")
    periods.to_csv(QA_DIR / "periodicity_summary.csv", index=False, encoding="utf-8-sig")
    acf.to_csv(QA_DIR / "autocorrelation_lags.csv", index=False, encoding="utf-8-sig")
    concentration.to_csv(RESULTS_DIR / "flood_season_concentration.csv", index=False, encoding="utf-8-sig")
    write_report(daily, annual, monthly, concentration, events, periods, acf, figure_paths)

    print("Daily rows:", len(daily))
    print("Annual pattern:")
    print(
        annual[
            [
                "year",
                "water_volume_1e8_m3",
                "sediment_mass_1e4_t",
                "water_yoy_change",
                "sediment_yoy_change",
            ]
        ].to_string(index=False)
    )
    print("\nTop sediment months:")
    print(
        monthly.sort_values("sediment_mass_1e4_t", ascending=False)
        .head(5)[["month", "water_share", "sediment_share", "mean_sediment_flux_kg_s"]]
        .to_string(index=False)
    )
    print("\nTop abrupt events:")
    print(
        events.sort_values("abrupt_score", ascending=False)
        .head(8)[["date", "main_direction", "abrupt_score", "mean_flow_m3s", "mean_sediment_flux_kg_s"]]
        .to_string(index=False)
    )
    print("\nTop periods:")
    print(periods.groupby("series").head(5).to_string(index=False))


if __name__ == "__main__":
    main()
