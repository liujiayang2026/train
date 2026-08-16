from __future__ import annotations

import math
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
ATTACHMENT = ROOT / "source" / "attachments" / "附件.xlsx"
FIGURE_DIR = ROOT / "process" / "common" / "figures"


COLORS = {
    "bg": (250, 250, 247),
    "ink": (38, 43, 51),
    "muted": (94, 102, 115),
    "grid": (212, 216, 222),
    "green": (63, 132, 94),
    "green_soft": (224, 240, 230),
    "red": (189, 74, 67),
    "red_soft": (246, 226, 224),
    "blue": (57, 112, 173),
    "blue_soft": (220, 233, 248),
    "orange": (205, 123, 51),
    "orange_soft": (248, 232, 214),
    "purple": (118, 89, 178),
    "yellow": (229, 174, 57),
    "panel": (255, 255, 255),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


F = {
    "title": font(38, True),
    "h2": font(26, True),
    "label": font(22),
    "small": font(18),
    "tiny": font(15),
}


def canvas(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (1600, 1050), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    draw.text((70, 48), title, fill=COLORS["ink"], font=F["title"])
    return img, draw


def centered_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fill: tuple[int, int, int] = COLORS["ink"],
    font_obj: ImageFont.FreeTypeFont = F["label"],
) -> None:
    box = draw.textbbox((0, 0), text, font=font_obj)
    draw.text((xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2), text, fill=fill, font=font_obj)


def centered_multiline(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    fill: tuple[int, int, int] = COLORS["ink"],
    font_obj: ImageFont.FreeTypeFont = F["label"],
    spacing: int = 6,
) -> None:
    box = draw.multiline_textbbox((0, 0), text, font=font_obj, spacing=spacing, align="center")
    draw.multiline_text(
        (xy[0] - (box[2] - box[0]) / 2, xy[1] - (box[3] - box[1]) / 2),
        text,
        fill=fill,
        font=font_obj,
        spacing=spacing,
        align="center",
    )


def line_arrow(
    draw: ImageDraw.ImageDraw,
    p1: tuple[float, float],
    p2: tuple[float, float],
    fill: tuple[int, int, int],
    width: int = 5,
    head: int = 18,
) -> None:
    draw.line([p1, p2], fill=fill, width=width)
    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    left = (p2[0] - head * math.cos(angle - math.pi / 7), p2[1] - head * math.sin(angle - math.pi / 7))
    right = (p2[0] - head * math.cos(angle + math.pi / 7), p2[1] - head * math.sin(angle + math.pi / 7))
    draw.polygon([p2, left, right], fill=fill)


def unit(v: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(v[0], v[1])
    return (v[0] / length, v[1] / length)


def add(v1: tuple[float, float], v2: tuple[float, float]) -> tuple[float, float]:
    return (v1[0] + v2[0], v1[1] + v2[1])


def sub(v1: tuple[float, float], v2: tuple[float, float]) -> tuple[float, float]:
    return (v1[0] - v2[0], v1[1] - v2[1])


def mul(v: tuple[float, float], scalar: float) -> tuple[float, float]:
    return (v[0] * scalar, v[1] * scalar)


def dashed_line(
    draw: ImageDraw.ImageDraw,
    p1: tuple[float, float],
    p2: tuple[float, float],
    fill: tuple[int, int, int],
    width: int = 3,
    dash: int = 16,
    gap: int = 10,
) -> None:
    total = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    direction = ((p2[0] - p1[0]) / total, (p2[1] - p1[1]) / total)
    distance = 0.0
    while distance < total:
        start = (p1[0] + direction[0] * distance, p1[1] + direction[1] * distance)
        end_distance = min(distance + dash, total)
        end = (p1[0] + direction[0] * end_distance, p1[1] + direction[1] * end_distance)
        draw.line((start, end), fill=fill, width=width)
        distance += dash + gap


def rounded_box(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int],
    outline: tuple[int, int, int] = COLORS["grid"],
    radius: int = 18,
    width: int = 3,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def save(img: Image.Image, filename: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    img.save(FIGURE_DIR / filename, "PNG", optimize=True)


def load_heliostat_points() -> list[tuple[float, float]]:
    workbook = openpyxl.load_workbook(ATTACHMENT, read_only=True, data_only=True)
    sheet = workbook.active
    points: list[tuple[float, float]] = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[0] is None or row[1] is None:
            continue
        points.append((float(row[0]), float(row[1])))
    return points


def draw_field_layout() -> None:
    img, draw = canvas("定日镜场坐标系与题干几何")
    cx, cy, scale = 760, 560, 1.08
    field_r = 350 * scale
    exclusion_r = 100 * scale

    draw.ellipse((cx - field_r, cy - field_r, cx + field_r, cy + field_r), fill=COLORS["green_soft"], outline=COLORS["green"], width=5)
    draw.ellipse((cx - exclusion_r, cy - exclusion_r, cx + exclusion_r, cy + exclusion_r), fill=COLORS["red_soft"], outline=COLORS["red"], width=4)

    for r in [100, 200, 300]:
        rr = r * scale
        draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=COLORS["grid"], width=2)

    line_arrow(draw, (cx - field_r - 80, cy), (cx + field_r + 85, cy), COLORS["ink"], width=3, head=16)
    line_arrow(draw, (cx, cy + field_r + 75), (cx, cy - field_r - 85), COLORS["ink"], width=3, head=16)
    draw.text((cx + field_r + 94, cy - 16), "x 正向：东", fill=COLORS["ink"], font=F["label"])
    draw.text((cx + 16, cy - field_r - 112), "y 正向：北", fill=COLORS["ink"], font=F["label"])

    points = load_heliostat_points()
    for x, y in points:
        px, py = cx + x * scale, cy - y * scale
        draw.ellipse((px - 2.1, py - 2.1, px + 2.1, py + 2.1), fill=COLORS["blue"])

    draw.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), fill=COLORS["orange"], outline=COLORS["ink"], width=2)
    centered_text(draw, (cx, cy + 38), "场心 / q1 吸收塔", COLORS["ink"], F["small"])

    draw.text((74, 140), "关键数据", fill=COLORS["ink"], font=F["h2"])
    facts = [
        "圆形区域半径：350 m",
        "塔周禁建半径：100 m",
        "坐标原点：圆形区域中心",
        "场址：东经 98.5°，北纬 39.4°",
        "海拔：3000 m",
        f"附件镜位：{len(points)} 面",
    ]
    y0 = 192
    for item in facts:
        draw.text((88, y0), item, fill=COLORS["muted"], font=F["label"])
        y0 += 44

    draw.text((1160, 852), "外圈：可建圆形镜场", fill=COLORS["green"], font=F["label"])
    draw.text((1160, 896), "内圈：100 m 禁建区", fill=COLORS["red"], font=F["label"])
    draw.text((1160, 940), "蓝点：附件给定定日镜中心", fill=COLORS["blue"], font=F["label"])
    save(img, "fig01-field-coordinate-layout.png")


def draw_side_geometry() -> None:
    img, draw = canvas("定日镜入射锥束、反射锥束与集热器截断")
    ground_y = 850
    draw.line((100, ground_y, 1500, ground_y), fill=COLORS["grid"], width=4)

    tower_x = 1180
    tower_top = 292
    tower_bottom = ground_y
    draw.rectangle((tower_x - 32, tower_top, tower_x + 32, tower_bottom), fill=COLORS["orange_soft"], outline=COLORS["orange"], width=5)
    receiver = (tower_x - 70, tower_top - 78, tower_x + 70, tower_top + 16)
    receiver_center = (tower_x, tower_top - 31)
    draw.rounded_rectangle(receiver, radius=16, fill=COLORS["red_soft"], outline=COLORS["red"], width=5)
    centered_multiline(draw, (tower_x + 230, tower_top - 38), "圆柱形外表受光集热器\n高 8 m，直径 7 m", COLORS["ink"], F["label"])
    draw.line((tower_x + 80, tower_top, tower_x + 80, ground_y), fill=COLORS["orange"], width=4)
    line_arrow(draw, (tower_x + 125, ground_y), (tower_x + 125, tower_top), COLORS["orange"], width=3, head=16)
    draw.text((tower_x + 145, 535), "吸收塔高度 80 m", fill=COLORS["orange"], font=F["label"])

    mirror_center = (520, ground_y - 82)
    sun_center = (220, 190)
    incoming = unit(sub(mirror_center, sun_center))
    outgoing = unit(sub(receiver_center, mirror_center))
    normal = unit(add(mul(incoming, -1), outgoing))
    tangent = (-normal[1], normal[0])
    mirror_len = 270
    mirror_thick = 18
    mirror_left = add(mirror_center, mul(tangent, -mirror_len / 2))
    mirror_right = add(mirror_center, mul(tangent, mirror_len / 2))
    mirror_pts = [
        add(mirror_left, mul(normal, -mirror_thick / 2)),
        add(mirror_right, mul(normal, -mirror_thick / 2)),
        add(mirror_right, mul(normal, mirror_thick / 2)),
        add(mirror_left, mul(normal, mirror_thick / 2)),
    ]

    source_perp = (-incoming[1], incoming[0])
    sun_a = add(sun_center, mul(source_perp, -36))
    sun_b = add(sun_center, mul(source_perp, 36))
    incident_poly = [sun_a, sun_b, add(mirror_right, mul(normal, -18)), add(mirror_left, mul(normal, -18))]
    reflected_poly = [
        add(mirror_left, mul(normal, 14)),
        add(mirror_right, mul(normal, 14)),
        (receiver_center[0] + 80, receiver_center[1] + 78),
        (receiver_center[0] - 80, receiver_center[1] - 78),
    ]
    draw.polygon(incident_poly, fill=(248, 236, 178), outline=COLORS["yellow"])
    draw.polygon(reflected_poly, fill=(218, 232, 248), outline=COLORS["blue"])

    line_arrow(draw, sun_center, mirror_center, COLORS["yellow"], width=6, head=22)
    line_arrow(draw, mirror_center, receiver_center, COLORS["blue"], width=6, head=22)
    draw.line((sun_a, add(mirror_left, mul(normal, -18))), fill=COLORS["yellow"], width=3)
    draw.line((sun_b, add(mirror_right, mul(normal, -18))), fill=COLORS["yellow"], width=3)
    draw.line((add(mirror_left, mul(normal, 14)), (receiver_center[0] - 80, receiver_center[1] - 78)), fill=COLORS["blue"], width=3)
    draw.line((add(mirror_right, mul(normal, 14)), (receiver_center[0] + 80, receiver_center[1] + 78)), fill=COLORS["blue"], width=3)

    draw.polygon(mirror_pts, fill=COLORS["blue_soft"], outline=COLORS["blue"])
    draw.line((mirror_center[0], ground_y, mirror_center[0], mirror_center[1]), fill=COLORS["grid"], width=4)
    draw.ellipse((mirror_center[0] - 8, mirror_center[1] - 8, mirror_center[0] + 8, mirror_center[1] + 8), fill=COLORS["blue"])
    draw.ellipse((sun_center[0] - 42, sun_center[1] - 42, sun_center[0] + 42, sun_center[1] + 42), fill=COLORS["yellow"], outline=COLORS["ink"], width=3)

    normal_end = add(mirror_center, mul(normal, 190))
    dashed_line(draw, mirror_center, normal_end, COLORS["purple"], width=5)
    line_arrow(draw, (normal_end[0] - normal[0] * 12, normal_end[1] - normal[1] * 12), normal_end, COLORS["purple"], width=3, head=18)

    draw.arc((mirror_center[0] - 88, mirror_center[1] - 88, mirror_center[0] + 88, mirror_center[1] + 88), 220, 282, fill=COLORS["purple"], width=3)
    draw.arc((mirror_center[0] - 116, mirror_center[1] - 116, mirror_center[0] + 116, mirror_center[1] + 116), 292, 340, fill=COLORS["purple"], width=3)

    centered_text(draw, (sun_center[0], sun_center[1] + 72), "太阳圆盘", COLORS["ink"], F["small"])
    draw.text((114, 328), "入射不是单根平行线：\n题干把太阳光视为具有锥形角的光束", fill=COLORS["ink"], font=F["label"])
    draw.text((308, 548), "中心入射光", fill=COLORS["yellow"], font=F["small"])
    draw.text((782, 500), "中心反射光指向\n集热器中心", fill=COLORS["blue"], font=F["small"])
    draw.text((430, 570), "法向 = 入射中心反向\n与反射中心方向的角平分线", fill=COLORS["purple"], font=F["small"])
    draw.text((250, 822), "安装高度：镜面中心离地高度", fill=COLORS["muted"], font=F["label"])
    draw.text((980, 160), "反射锥束与圆柱集热器相交\n相交比例对应截断效率 ηtrunc", fill=COLORS["red"], font=F["small"])
    draw.text((620, 918), "dHR：镜面中心到集热器中心距离，影响大气透射率 ηat", fill=COLORS["muted"], font=F["label"])

    rounded_box(draw, (76, 680, 378, 768), COLORS["panel"])
    centered_text(draw, (227, 710), "定日镜：矩形平面镜", COLORS["ink"], F["small"])
    centered_text(draw, (227, 744), "q1 尺寸 6 m × 6 m，高度 4 m", COLORS["muted"], F["small"])
    save(img, "fig02-side-ray-geometry.png")


def draw_efficiency_structure() -> None:
    img, draw = canvas("输出热功率与光学效率结构")

    boxes = [
        ((80, 170, 360, 300), "太阳位置", "每月21日\n9:00、10:30、12:00\n13:30、15:00"),
        ((510, 170, 790, 275), "DNI", "由太阳高度角和海拔 H=3 km 计算"),
        ((940, 170, 1260, 275), "场输出热功率", "Efield = DNI · Σ Ai ηi"),
    ]
    for box, title, subtitle in boxes:
        rounded_box(draw, box, COLORS["panel"])
        centered_text(draw, ((box[0] + box[2]) / 2, box[1] + 36), title, COLORS["ink"], F["h2"])
        centered_multiline(draw, ((box[0] + box[2]) / 2, box[1] + 84), subtitle, COLORS["muted"], F["small"])
    line_arrow(draw, (360, 222), (510, 222), COLORS["ink"], width=3, head=16)
    line_arrow(draw, (790, 222), (940, 222), COLORS["ink"], width=3, head=16)

    draw.text((100, 390), "单镜光学效率", fill=COLORS["ink"], font=F["h2"])
    draw.text((100, 442), "η = ηsb × ηcos × ηat × ηtrunc × ηref", fill=COLORS["ink"], font=font(34, True))

    factors = [
        ("ηsb", "阴影遮挡效率", "前后镜之间遮阴与挡光"),
        ("ηcos", "余弦效率", "镜面法向与入射/反射夹角"),
        ("ηat", "大气透射率", "由 dHR 距离决定"),
        ("ηtrunc", "截断效率", "反射锥光能否落到集热器"),
        ("ηref", "镜面反射率", "题干可取常数 0.92"),
    ]
    x0 = 100
    for i, (symbol, name, note) in enumerate(factors):
        left = x0 + i * 292
        rounded_box(draw, (left, 545, left + 245, 715), COLORS["blue_soft"] if i in [1, 2] else COLORS["orange_soft"])
        centered_text(draw, (left + 122, 588), symbol, COLORS["ink"], font(32, True))
        centered_text(draw, (left + 122, 636), name, COLORS["ink"], F["label"])
        wrapped = note if len(note) <= 14 else note[:14] + "\n" + note[14:]
        centered_text(draw, (left + 122, 682), wrapped, COLORS["muted"], F["small"])
        if i < len(factors) - 1:
            centered_text(draw, (left + 266, 630), "×", COLORS["ink"], font(34, True))

    draw.line((120, 815, 1480, 815), fill=COLORS["grid"], width=4)
    draw.text((120, 850), "建模提示：ηsb 和 ηtrunc 是几何建模难点，需要遮挡/光线锥/接收器截断计算；其余项可先按公式直接计算。", fill=COLORS["muted"], font=F["label"])
    save(img, "fig03-efficiency-power-structure.png")


def draw_questions_constraints() -> None:
    img, draw = canvas("三问任务、变量与约束关系")

    stages = [
        ((80, 160, 450, 335), "问题 1", "固定布局评价", "塔在场心；镜面 6 m × 6 m；安装高度 4 m；附件给定镜位"),
        ((615, 160, 985, 335), "问题 2", "同尺寸同高度优化", "优化塔坐标、统一镜面尺寸、统一安装高度、镜数和镜位"),
        ((1150, 160, 1520, 335), "问题 3", "逐镜变尺寸变高度优化", "在 q2 基础上放开每面镜的宽、高、安装高度"),
    ]
    for box, q, title, note in stages:
        rounded_box(draw, box, COLORS["panel"])
        centered_text(draw, ((box[0] + box[2]) / 2, box[1] + 38), q, COLORS["ink"], F["h2"])
        centered_text(draw, ((box[0] + box[2]) / 2, box[1] + 82), title, COLORS["blue"], F["label"])
        lines = [note[:21], note[21:42], note[42:]]
        for j, line in enumerate([line for line in lines if line]):
            centered_text(draw, ((box[0] + box[2]) / 2, box[1] + 122 + j * 30), line, COLORS["muted"], F["small"])
    line_arrow(draw, (450, 248), (615, 248), COLORS["ink"], width=3, head=16)
    line_arrow(draw, (985, 248), (1150, 248), COLORS["ink"], width=3, head=16)

    draw.text((90, 430), "共同物理/几何约束", fill=COLORS["ink"], font=F["h2"])
    constraints = [
        ("场地边界", "镜场位于半径 350 m 圆形区域内"),
        ("禁建区", "吸收塔周围 100 m 范围内不安装定日镜"),
        ("镜面尺寸", "边长 2–8 m，且镜面宽度不小于高度"),
        ("安装高度", "2–6 m，并保证绕水平转轴旋转时不触地"),
        ("相邻间距", "底座中心距离至少比镜面宽度多 5 m"),
        ("额定功率", "q2/q3 年平均输出热功率达到 60 MW"),
    ]
    for i, (head, note) in enumerate(constraints):
        row, col = divmod(i, 2)
        left, top = 90 + col * 725, 500 + row * 115
        fill = COLORS["green_soft"] if i in [0, 1] else COLORS["orange_soft"] if i in [2, 3, 4] else COLORS["red_soft"]
        rounded_box(draw, (left, top, left + 610, top + 78), fill)
        draw.text((left + 24, top + 18), head, fill=COLORS["ink"], font=F["label"])
        draw.text((left + 150, top + 20), note, fill=COLORS["muted"], font=F["small"])

    draw.text((90, 900), "推荐路线：先做 q1 评价器，再把同一套评价器作为 q2/q3 的目标函数与约束检查器。", fill=COLORS["blue"], font=F["label"])
    save(img, "fig04-question-variables-constraints.png")


def main() -> None:
    draw_field_layout()
    draw_side_geometry()
    draw_efficiency_structure()
    draw_questions_constraints()


if __name__ == "__main__":
    main()
