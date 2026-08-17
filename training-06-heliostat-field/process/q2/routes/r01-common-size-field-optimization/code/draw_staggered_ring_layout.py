from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs" / "run-20260817-1312-staggered-ring-layout-final"
OUTPUT = RUN / "figures" / "fig01-staggered-ring-layout-parameters.png"

COLORS = {
    "bg": (249, 250, 247),
    "ink": (34, 40, 49),
    "muted": (91, 101, 113),
    "grid": (206, 213, 218),
    "blue": (45, 105, 170),
    "blue_soft": (220, 233, 247),
    "green": (45, 126, 87),
    "green_soft": (220, 239, 229),
    "red": (185, 66, 59),
    "red_soft": (246, 225, 222),
    "orange": (202, 119, 42),
    "purple": (116, 80, 165),
    "white": (255, 255, 255),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsunb.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


F = {
    "title": font(46, True),
    "subtitle": font(24),
    "panel": font(28, True),
    "label": font(23),
    "label_bold": font(23, True),
    "small": font(19),
    "tiny": font(16),
    "formula": font(25),
}


def centered(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font_obj, fill) -> None:
    box = draw.textbbox((0, 0), text, font=font_obj)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, font=font_obj, fill=fill)


def arrow_head(draw: ImageDraw.ImageDraw, tip, angle, fill, size=14) -> None:
    points = [
        tip,
        (tip[0] - size * math.cos(angle - math.pi / 6), tip[1] - size * math.sin(angle - math.pi / 6)),
        (tip[0] - size * math.cos(angle + math.pi / 6), tip[1] - size * math.sin(angle + math.pi / 6)),
    ]
    draw.polygon(points, fill=fill)


def arrow(draw: ImageDraw.ImageDraw, start, end, fill, width=4, both=False, size=14) -> None:
    draw.line([start, end], fill=fill, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    arrow_head(draw, end, angle, fill, size)
    if both:
        arrow_head(draw, start, angle + math.pi, fill, size)


def dashed_line(draw: ImageDraw.ImageDraw, start, end, fill, width=2, dash=12, gap=8) -> None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    ux, uy = dx / length, dy / length
    pos = 0.0
    while pos < length:
        stop = min(pos + dash, length)
        draw.line(
            [(start[0] + ux * pos, start[1] + uy * pos), (start[0] + ux * stop, start[1] + uy * stop)],
            fill=fill,
            width=width,
        )
        pos += dash + gap


def dashed_ellipse(draw: ImageDraw.ImageDraw, box, fill, width=2, segments=72) -> None:
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
    for i in range(0, segments, 2):
        a0 = 2 * math.pi * i / segments
        a1 = 2 * math.pi * (i + 1) / segments
        draw.line(
            [(cx + rx * math.cos(a0), cy + ry * math.sin(a0)), (cx + rx * math.cos(a1), cy + ry * math.sin(a1))],
            fill=fill,
            width=width,
        )


def mirror_polygon(center, angle, width=18, height=9):
    tx, ty = math.cos(angle), math.sin(angle)
    nx, ny = -ty, tx
    return [
        (center[0] - width / 2 * tx - height / 2 * nx, center[1] - width / 2 * ty - height / 2 * ny),
        (center[0] + width / 2 * tx - height / 2 * nx, center[1] + width / 2 * ty - height / 2 * ny),
        (center[0] + width / 2 * tx + height / 2 * nx, center[1] + width / 2 * ty + height / 2 * ny),
        (center[0] - width / 2 * tx + height / 2 * nx, center[1] - width / 2 * ty + height / 2 * ny),
    ]


def panel_title(draw, x, y, letter, title):
    draw.ellipse((x, y, x + 38, y + 38), fill=COLORS["ink"])
    centered(draw, (x + 19, y + 19), letter, F["small"], COLORS["white"])
    draw.text((x + 52, y + 2), title, font=F["panel"], fill=COLORS["ink"])


def overall_view(draw: ImageDraw.ImageDraw) -> None:
    panel_title(draw, 70, 165, "A", "场地与吸收塔位置")
    center = (500, 720)
    radius = 410
    scale = radius / 350.0
    tower = (center[0] + 58 * scale, center[1] - 36 * scale)

    draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), fill=COLORS["white"], outline=COLORS["ink"], width=4)
    draw.line((center[0] - radius + 25, center[1], center[0] + radius - 25, center[1]), fill=COLORS["grid"], width=2)
    draw.line((center[0], center[1] + radius - 25, center[0], center[1] - radius + 25), fill=COLORS["grid"], width=2)
    arrow(draw, (center[0] + radius - 80, center[1]), (center[0] + radius - 25, center[1]), COLORS["muted"], width=3, size=11)
    arrow(draw, (center[0], center[1] - radius + 80), (center[0], center[1] - radius + 25), COLORS["muted"], width=3, size=11)
    draw.text((center[0] + radius - 20, center[1] + 8), "x（东）", font=F["tiny"], fill=COLORS["muted"])
    draw.text((center[0] + 10, center[1] - radius - 4), "y（北）", font=F["tiny"], fill=COLORS["muted"])

    exclusion = 100 * scale
    draw.ellipse((tower[0] - exclusion, tower[1] - exclusion, tower[0] + exclusion, tower[1] + exclusion), fill=COLORS["red_soft"], outline=COLORS["red"], width=3)
    draw.text((tower[0] - exclusion - 125, tower[1] - exclusion + 5), "禁建区半径 100 m", font=F["small"], fill=COLORS["red"])

    ring_radii_m = [122, 164, 206, 248]
    counts = [14, 19, 24, 29]
    theta0 = math.radians(13)
    for k, (r_m, count) in enumerate(zip(ring_radii_m, counts)):
        r = r_m * scale
        dashed_ellipse(draw, (tower[0] - r, tower[1] - r, tower[0] + r, tower[1] + r), COLORS["blue"], width=2)
        offset = theta0 + (math.pi / count if k % 2 else 0.0)
        for j in range(count):
            angle = offset + 2 * math.pi * j / count
            point = (tower[0] + r * math.cos(angle), tower[1] - r * math.sin(angle))
            if math.hypot(point[0] - center[0], point[1] - center[1]) < radius - 12:
                draw.polygon(mirror_polygon(point, -angle + math.pi / 2), fill=COLORS["green"], outline=COLORS["white"])

    draw.ellipse((center[0] - 7, center[1] - 7, center[0] + 7, center[1] + 7), fill=COLORS["ink"])
    draw.text((center[0] - 32, center[1] + 15), "O(0,0)", font=F["small"], fill=COLORS["ink"])
    draw.ellipse((tower[0] - 14, tower[1] - 14, tower[0] + 14, tower[1] + 14), fill=COLORS["orange"], outline=COLORS["white"], width=3)
    centered(draw, (tower[0] + 72, tower[1] + 72), "T(x_T, y_T)", F["small"], COLORS["orange"])

    dashed_line(draw, center, (tower[0], center[1]), COLORS["purple"], width=3)
    dashed_line(draw, (tower[0], center[1]), tower, COLORS["purple"], width=3)
    arrow(draw, (center[0], center[1] + 35), (tower[0], center[1] + 35), COLORS["purple"], width=3, both=True, size=11)
    centered(draw, ((center[0] + tower[0]) / 2, center[1] + 62), "x_T", F["label_bold"], COLORS["purple"])
    arrow(draw, (tower[0] + 35, center[1]), (tower[0] + 35, tower[1]), COLORS["purple"], width=3, both=True, size=11)
    draw.text((tower[0] + 46, (center[1] + tower[1]) / 2 - 12), "y_T", font=F["label_bold"], fill=COLORS["purple"])

    angle = math.radians(-58)
    outer = ring_radii_m[-1] * scale
    end = (tower[0] + outer * math.cos(angle), tower[1] + outer * math.sin(angle))
    arrow(draw, tower, end, COLORS["blue"], width=4, both=True)
    centered(draw, (tower[0] + 0.66 * (end[0] - tower[0]) + 34, tower[1] + 0.66 * (end[1] - tower[1]) - 8), "r_max", F["label_bold"], COLORS["blue"])

    boundary_point = (center[0] - radius * 0.72, center[1] + radius * 0.69)
    arrow(draw, center, boundary_point, COLORS["ink"], width=3, both=True, size=11)
    centered(draw, ((center[0] + boundary_point[0]) / 2 - 28, (center[1] + boundary_point[1]) / 2 + 8), "R_site = 350 m", F["small"], COLORS["ink"])


def ring_zoom(draw: ImageDraw.ImageDraw) -> None:
    panel_title(draw, 1010, 165, "B", "交错环带局部放大")
    tower = (1055, 930)
    r1, r2 = 305, 420
    start_deg, end_deg = 270, 350
    draw.arc((tower[0] - r1, tower[1] - r1, tower[0] + r1, tower[1] + r1), start=start_deg, end=end_deg, fill=COLORS["blue"], width=4)
    draw.arc((tower[0] - r2, tower[1] - r2, tower[0] + r2, tower[1] + r2), start=start_deg, end=end_deg, fill=COLORS["blue"], width=4)
    draw.ellipse((tower[0] - 10, tower[1] - 10, tower[0] + 10, tower[1] + 10), fill=COLORS["orange"])
    draw.text((tower[0] + 12, tower[1] - 8), "T", font=F["small"], fill=COLORS["orange"])

    inner_angles = [math.radians(a) for a in [278, 298, 318, 338]]
    outer_angles = [math.radians(a) for a in [288, 308, 328, 348]]
    inner_points = []
    outer_points = []
    for angle in inner_angles:
        point = (tower[0] + r1 * math.cos(angle), tower[1] + r1 * math.sin(angle))
        inner_points.append(point)
        draw.polygon(mirror_polygon(point, angle + math.pi / 2, 30, 14), fill=COLORS["green"], outline=COLORS["white"])
    for angle in outer_angles:
        point = (tower[0] + r2 * math.cos(angle), tower[1] + r2 * math.sin(angle))
        outer_points.append(point)
        draw.polygon(mirror_polygon(point, angle + math.pi / 2, 30, 14), fill=COLORS["green"], outline=COLORS["white"])

    radial_angle = math.radians(320)
    p1 = (tower[0] + r1 * math.cos(radial_angle), tower[1] + r1 * math.sin(radial_angle))
    p2 = (tower[0] + r2 * math.cos(radial_angle), tower[1] + r2 * math.sin(radial_angle))
    arrow(draw, p1, p2, COLORS["purple"], width=4, both=True)
    centered(draw, ((p1[0] + p2[0]) / 2 + 45, (p1[1] + p2[1]) / 2), "Δr", F["label_bold"], COLORS["purple"])

    chord_a, chord_b = outer_points[1], outer_points[2]
    arrow(draw, chord_a, chord_b, COLORS["orange"], width=4, both=True)
    centered(draw, ((chord_a[0] + chord_b[0]) / 2 - 10, (chord_a[1] + chord_b[1]) / 2 - 30), "d_t", F["label_bold"], COLORS["orange"])
    draw.text((1175, 335), "相邻中心距离 ≥ W + 5 m", font=F["small"], fill=COLORS["orange"])
    dashed_line(draw, (1380, 365), ((chord_a[0] + chord_b[0]) / 2, (chord_a[1] + chord_b[1]) / 2), COLORS["orange"], width=2, dash=9, gap=6)

    theta = inner_angles[0]
    axis_end = (tower[0], tower[1] - 155)
    draw.line([tower, axis_end], fill=COLORS["grid"], width=2)
    ray_end = (tower[0] + 170 * math.cos(theta), tower[1] + 170 * math.sin(theta))
    draw.line([tower, ray_end], fill=COLORS["purple"], width=3)
    draw.arc((tower[0] - 115, tower[1] - 115, tower[0] + 115, tower[1] + 115), start=270, end=278, fill=COLORS["purple"], width=4)
    draw.text((tower[0] + 22, tower[1] - 132), "θ_0", font=F["label_bold"], fill=COLORS["purple"])

    r0_end = inner_points[0]
    arrow(draw, tower, r0_end, COLORS["blue"], width=3, both=True, size=12)
    centered(draw, ((tower[0] + r0_end[0]) / 2 - 24, (tower[1] + r0_end[1]) / 2 - 20), "r_0", F["label_bold"], COLORS["blue"])

    draw.text((1035, 1000), "r_k = r_0 + (k - 1)Δr", font=F["formula"], fill=COLORS["ink"])
    draw.text((1035, 1045), "n_k = floor(2πr_k / d_t)", font=F["formula"], fill=COLORS["ink"])
    draw.text((1035, 1090), "奇、偶环相差半个角步长 π/n_k", font=F["small"], fill=COLORS["muted"])


def mirror_geometry(draw: ImageDraw.ImageDraw) -> None:
    panel_title(draw, 1760, 165, "C", "统一镜面尺寸与安装高度")
    x0, y0, x1, y1 = 1905, 310, 2225, 555
    draw.rectangle((x0, y0, x1, y1), fill=COLORS["green_soft"], outline=COLORS["green"], width=5)
    draw.line((x0, (y0 + y1) / 2, x1, (y0 + y1) / 2), fill=COLORS["green"], width=3)
    centered(draw, ((x0 + x1) / 2, (y0 + y1) / 2), "定日镜", F["label_bold"], COLORS["green"])
    arrow(draw, (x0, y0 - 38), (x1, y0 - 38), COLORS["blue"], width=4, both=True)
    centered(draw, ((x0 + x1) / 2, y0 - 66), "镜面宽度 W", F["label_bold"], COLORS["blue"])
    arrow(draw, (x1 + 45, y0), (x1 + 45, y1), COLORS["purple"], width=4, both=True)
    draw.text((x1 + 62, (y0 + y1) / 2 - 14), "H", font=F["label_bold"], fill=COLORS["purple"])
    draw.text((1885, 600), "2 m ≤ H ≤ W ≤ 8 m", font=F["formula"], fill=COLORS["ink"])

    ground_y = 1080
    center = (2070, 835)
    draw.line((1815, ground_y, 2325, ground_y), fill=COLORS["ink"], width=5)
    draw.text((1815, ground_y + 12), "地面", font=F["small"], fill=COLORS["muted"])
    draw.line((center[0], ground_y, center[0], center[1]), fill=COLORS["grid"], width=2)
    angle = math.radians(-28)
    half = 160
    p_top = (center[0] - half * math.cos(angle), center[1] - half * math.sin(angle))
    p_bottom = (center[0] + half * math.cos(angle), center[1] + half * math.sin(angle))
    draw.line([p_top, p_bottom], fill=COLORS["green"], width=15)
    draw.ellipse((center[0] - 13, center[1] - 13, center[0] + 13, center[1] + 13), fill=COLORS["orange"], outline=COLORS["white"], width=3)
    draw.text((center[0] + 20, center[1] - 20), "水平转轴中心", font=F["small"], fill=COLORS["orange"])
    arrow(draw, (1850, ground_y), (1850, center[1]), COLORS["blue"], width=4, both=True)
    draw.text((1870, (ground_y + center[1]) / 2 - 14), "z_H", font=F["label_bold"], fill=COLORS["blue"])
    arrow(draw, center, p_bottom, COLORS["purple"], width=4, both=True)
    draw.text((2145, 920), "H/2", font=F["label_bold"], fill=COLORS["purple"])
    draw.text((1845, 1150), "2 m ≤ z_H ≤ 6 m，且 z_H ≥ H/2", font=F["formula"], fill=COLORS["ink"])


def footer(draw: ImageDraw.ImageDraw) -> None:
    y = 1300
    draw.line((70, y, 2330, y), fill=COLORS["grid"], width=3)
    text = "优化参数向量  x = (x_T, y_T, W, H, z_H, r_0, Δr, d_t, r_max, theta_0)"
    centered(draw, (1200, y + 58), text, F["formula"], COLORS["ink"])
    text2 = "镜面总数由各环自动生成：N = Σ n_k；布局生成阶段直接剔除越界、禁建区和间距不合格镜面"
    centered(draw, (1200, y + 103), text2, F["small"], COLORS["muted"])


def main() -> None:
    image = Image.new("RGB", (2400, 1450), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw.text((70, 48), "交错环形定日镜场参数化布局", font=F["title"], fill=COLORS["ink"])
    draw.text((72, 108), "场地总览、交错环带与单镜几何参数的统一定义", font=F["subtitle"], fill=COLORS["muted"])
    draw.line((70, 148, 2330, 148), fill=COLORS["grid"], width=3)
    draw.line((970, 175, 970, 1245), fill=COLORS["grid"], width=2)
    draw.line((1730, 175, 1730, 1245), fill=COLORS["grid"], width=2)
    overall_view(draw)
    ring_zoom(draw)
    mirror_geometry(draw)
    footer(draw)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT, format="PNG", optimize=True)
    print(OUTPUT)


if __name__ == "__main__":
    main()
