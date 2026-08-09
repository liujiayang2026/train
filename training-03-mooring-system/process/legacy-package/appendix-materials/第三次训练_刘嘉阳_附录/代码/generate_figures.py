"""Generate vector PDF figures for the Project 3 paper using ReportLab."""

from __future__ import annotations

import csv
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, black, grey
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "support" / "data"
FIGURES = ROOT / "figures"
FIGURES.mkdir(exist_ok=True)
FONT_PATH = Path(r"C:\Windows\Fonts\simhei.ttf")
if FONT_PATH.exists():
    pdfmetrics.registerFont(TTFont("Chinese", str(FONT_PATH)))
    FONT = "Chinese"
else:
    FONT = "Helvetica"


def axes(c, x0, y0, width, height, xlabel, ylabel, xmax, ymax, xticks=5, yticks=5, xmin=0):
    c.setStrokeColor(black); c.setLineWidth(0.8)
    c.line(x0, y0, x0 + width, y0); c.line(x0, y0, x0, y0 + height)
    c.setFont(FONT, 8)
    for i in range(xticks + 1):
        x = x0 + width * i / xticks
        c.line(x, y0 - 3, x, y0 + 3)
        c.drawCentredString(x, y0 - 14, f"{xmin+(xmax-xmin)*i/xticks:.1f}")
    for i in range(yticks + 1):
        y = y0 + height * i / yticks
        c.line(x0 - 3, y, x0 + 3, y)
        c.drawRightString(x0 - 6, y - 3, f"{ymax*i/yticks:.1f}")
    c.drawCentredString(x0 + width / 2, y0 - 28, xlabel)
    c.saveState(); c.translate(x0 - 38, y0 + height / 2); c.rotate(90)
    c.drawCentredString(0, 0, ylabel); c.restoreState()


def panel_axes(c, x0, y0, width, height, xlabel, ylabel, xmin, xmax, ymin, ymax, xticks, yticks=4):
    c.setStrokeColor(black); c.setLineWidth(0.7)
    c.line(x0, y0, x0 + width, y0); c.line(x0, y0, x0, y0 + height)
    c.setFont(FONT, 7)
    for value in xticks:
        x = x0 + width * (value - xmin) / (xmax - xmin)
        c.line(x, y0 - 2.5, x, y0 + 2.5)
        c.drawCentredString(x, y0 - 12, f"{value:g}")
    for i in range(yticks + 1):
        value = ymin + (ymax - ymin) * i / yticks
        y = y0 + height * i / yticks
        c.line(x0 - 2.5, y, x0 + 2.5, y)
        c.drawRightString(x0 - 5, y - 2.5, f"{value:.2f}" if ymax < 10 else f"{value:.0f}")
    c.drawCentredString(x0 + width / 2, y0 - 25, xlabel)
    c.saveState(); c.translate(x0 - 34, y0 + height / 2); c.rotate(90)
    c.drawCentredString(0, 0, ylabel); c.restoreState()


def panel_series(c, x0, y0, width, height, xs, ys, xmin, xmax, ymin, ymax, color, dash=None):
    c.setStrokeColor(color); c.setFillColor(color); c.setLineWidth(1.5)
    if dash:
        c.setDash(*dash)
    p = c.beginPath()
    for index, (xv, yv) in enumerate(zip(xs, ys)):
        x = x0 + width * (xv - xmin) / (xmax - xmin)
        y = y0 + height * (yv - ymin) / (ymax - ymin)
        p.moveTo(x, y) if index == 0 else p.lineTo(x, y)
        c.circle(x, y, 2.2, stroke=1, fill=1)
    c.drawPath(p); c.setDash()


def chain_profiles():
    rows = list(csv.DictReader((DATA / "chain-profiles.csv").open(encoding="utf-8-sig")))
    groups = {}
    for row in rows:
        groups.setdefault(row["wind_speed_m_s"], []).append(
            (float(row["x_from_anchor_m"]), float(row["height_above_seabed_m"]))
        )
    path = FIGURES / "question-1-chain-profiles.pdf"
    c = canvas.Canvas(str(path), pagesize=(500, 320))
    axes(c, 70, 55, 390, 225, "水平距离 / m", "离海床高度 / m", 18, 13, 6, 5)
    colors = [HexColor("#1f4e79"), HexColor("#c0504d")]
    for (speed, points), color in zip(sorted(groups.items()), colors):
        c.setStrokeColor(color); c.setLineWidth(1.7)
        p = c.beginPath()
        for index, (x, y) in enumerate(points):
            px = 70 + 390 * x / 18; py = 55 + 225 * y / 13
            p.moveTo(px, py) if index == 0 else p.lineTo(px, py)
        c.drawPath(p)
    c.setFont(FONT, 9); c.setFillColor(colors[0]); c.drawString(305, 286, "12 m/s")
    c.setFillColor(colors[1]); c.drawString(375, 286, "24 m/s")
    c.save()


def ballast_sensitivity():
    rows = list(csv.DictReader((DATA / "ballast-mass-sensitivity.csv").open(encoding="utf-8-sig")))
    masses = [float(r["ballast_mass_kg"]) for r in rows]
    barrel = [float(r["barrel_angle_deg"]) for r in rows]
    anchor = [float(r["anchor_angle_deg"]) for r in rows]
    path = FIGURES / "question-2-ballast-sensitivity.pdf"
    c = canvas.Canvas(str(path), pagesize=(500, 320))
    axes(c, 70, 55, 390, 225, "重物球质量 / kg", "角度 / (°)", 2200, 20, 5, 5, 1200)
    # Relabel x axis with absolute masses.
    c.setFillColor(black); c.setFont(FONT, 8)
    c.setFillColor(HexColor("#1f4e79"));
    for values, color in ((barrel, HexColor("#1f4e79")), (anchor, HexColor("#c0504d"))):
        c.setStrokeColor(color); c.setLineWidth(1.7); p = c.beginPath()
        for i, (mass, value) in enumerate(zip(masses, values)):
            x = 70 + 390 * (mass - 1200) / 1000; y = 55 + 225 * value / 20
            p.moveTo(x, y) if i == 0 else p.lineTo(x, y)
        c.drawPath(p)
    c.setStrokeColor(grey); c.setDash(4, 3)
    for value in (5, 16):
        y = 55 + 225 * value / 20; c.line(70, y, 460, y)
    c.setDash(); c.setFillColor(HexColor("#1f4e79")); c.drawString(285, 286, "钢桶倾角")
    c.setFillColor(HexColor("#c0504d")); c.drawString(365, 286, "锚点夹角")
    c.save()


def depth_response():
    rows = list(csv.DictReader((DATA / "selected-design-scenarios.csv").open(encoding="utf-8-sig")))
    rows = [r for r in rows if r["wind_speed_m_s"] == "36.0" and r["current_speed_m_s"] == "1.5" and r["wind_current_angle_deg"] == "0.0"]
    depths = [float(r["depth_m"]) for r in rows]
    barrel = [float(r["barrel_angle_deg"]) for r in rows]
    anchor = [float(r["anchor_angle_deg"]) for r in rows]
    path = FIGURES / "question-3-depth-angles.pdf"
    c = canvas.Canvas(str(path), pagesize=(500, 320))
    axes(c, 70, 55, 390, 225, "水深 / m", "角度 / (°)", 20, 16, 4, 4, 16)
    for values, color in ((barrel, HexColor("#1f4e79")), (anchor, HexColor("#c0504d"))):
        c.setStrokeColor(color); c.setLineWidth(1.7); p = c.beginPath()
        for i, (depth, value) in enumerate(zip(depths, values)):
            x = 70 + 390 * (depth - 16) / 4; y = 55 + 225 * value / 16
            p.moveTo(x, y) if i == 0 else p.lineTo(x, y)
            c.circle(x, y, 2.5, stroke=1, fill=0)
        c.drawPath(p)
    c.setFillColor(HexColor("#1f4e79")); c.drawString(285, 286, "钢桶倾角")
    c.setFillColor(HexColor("#c0504d")); c.drawString(365, 286, "锚点夹角")
    c.save()


def ballast_state_comparison():
    rows = list(csv.DictReader((DATA / "question-2-summary.csv").open(encoding="utf-8-sig")))
    masses = [float(r["ballast_mass_kg"]) for r in rows]
    drafts = [float(r["draft_m"]) for r in rows]
    horizontal = [float(r["horizontal_tension_n"]) for r in rows]
    vertical = [float(r["chain_top_vertical_n"]) for r in rows]
    path = FIGURES / "question-2-state-comparison.pdf"
    c = canvas.Canvas(str(path), pagesize=(500, 300))
    panel_axes(c, 55, 55, 175, 185, "重物球质量 / kg", "吃水 / m", 1200, 1800, 0.74, 0.98, [1200, 1500, 1800])
    panel_series(c, 55, 55, 175, 185, masses, drafts, 1200, 1800, 0.74, 0.98, HexColor("#1f4e79"))
    c.setFillColor(black); c.setFont(FONT, 8); c.drawCentredString(142, 260, "(a) 配重与浮标吃水")
    panel_axes(c, 295, 55, 175, 185, "重物球质量 / kg", "张力 / N", 1200, 1800, 1600, 2200, [1200, 1500, 1800])
    panel_series(c, 295, 55, 175, 185, masses, horizontal, 1200, 1800, 1600, 2200, HexColor("#1f4e79"))
    panel_series(c, 295, 55, 175, 185, masses, vertical, 1200, 1800, 1600, 2200, HexColor("#c0504d"), (4, 2))
    c.setFillColor(black); c.drawCentredString(382, 260, "(b) 锚链顶端张力")
    c.setFillColor(HexColor("#1f4e79")); c.drawString(325, 278, "水平张力")
    c.setFillColor(HexColor("#c0504d")); c.drawString(405, 278, "竖直张力")
    c.save()


def environmental_response():
    rows = list(csv.DictReader((DATA / "selected-design-scenarios.csv").open(encoding="utf-8-sig")))
    specs = [
        ("wind_speed_m_s", lambda r: r["depth_m"] == "18.0" and r["current_speed_m_s"] == "1.5" and r["wind_current_angle_deg"] == "0.0", [12, 24, 36], "风速 / (m/s)", "(a) 风速响应"),
        ("current_speed_m_s", lambda r: r["depth_m"] == "18.0" and r["wind_speed_m_s"] == "36.0" and r["wind_current_angle_deg"] == "0.0", [0, 0.5, 1.0, 1.5], "流速 / (m/s)", "(b) 流速响应"),
        ("wind_current_angle_deg", lambda r: r["depth_m"] == "18.0" and r["wind_speed_m_s"] == "36.0" and r["current_speed_m_s"] == "1.5", [0, 45, 90, 135, 180], "风流夹角 / (°)", "(c) 方向响应"),
    ]
    path = FIGURES / "question-3-environmental-response.pdf"
    c = canvas.Canvas(str(path), pagesize=(500, 290))
    for index, (key, predicate, ticks, xlabel, title) in enumerate(specs):
        selected = sorted((r for r in rows if predicate(r)), key=lambda r: float(r[key]))
        xs = [float(r[key]) for r in selected]
        barrel = [float(r["barrel_angle_deg"]) for r in selected]
        anchor = [float(r["anchor_angle_deg"]) for r in selected]
        x0 = 45 + index * 160
        panel_axes(c, x0, 52, 125, 175, xlabel, "角度 / (°)", min(ticks), max(ticks), 0, 6.5, ticks, 5)
        panel_series(c, x0, 52, 125, 175, xs, barrel, min(ticks), max(ticks), 0, 6.5, HexColor("#1f4e79"))
        panel_series(c, x0, 52, 125, 175, xs, anchor, min(ticks), max(ticks), 0, 6.5, HexColor("#c0504d"), (4, 2))
        c.setFillColor(black); c.setFont(FONT, 8); c.drawCentredString(x0 + 62.5, 246, title)
    c.setFillColor(HexColor("#1f4e79")); c.drawString(340, 270, "钢桶倾角")
    c.setFillColor(HexColor("#c0504d")); c.drawString(415, 270, "锚点夹角")
    c.save()


if __name__ == "__main__":
    chain_profiles(); ballast_sensitivity(); depth_response()
    ballast_state_comparison(); environmental_response()
