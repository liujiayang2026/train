from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent
VERSION_DIR = ROOT / "paper_versions"
INPUT = ROOT / "modeling_paper_v1.md"


def next_version_pdf() -> Path:
    VERSION_DIR.mkdir(exist_ok=True)
    versions: list[int] = []
    for pdf in list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf")):
        match = re.fullmatch(r"modeling_paper_v(\d+)\.pdf", pdf.name)
        if match:
            versions.append(int(match.group(1)))
    next_version = max(versions) + 1 if versions else 1
    return VERSION_DIR / f"modeling_paper_v{next_version}.pdf"


OUTPUT = next_version_pdf()


def register_font() -> tuple[str, str]:
    candidates = [
        (r"C:\Windows\Fonts\simsun.ttc", "PaperChinese"),
        (r"C:\Windows\Fonts\msyh.ttc", "PaperChinese"),
        (r"C:\Windows\Fonts\simfang.ttf", "PaperChinese"),
        (r"C:\Windows\Fonts\simkai.ttf", "PaperChinese"),
    ]
    bold_candidates = [
        (r"C:\Windows\Fonts\simhei.ttf", "PaperChineseBold"),
        (r"C:\Windows\Fonts\msyhbd.ttc", "PaperChineseBold"),
        (r"C:\Windows\Fonts\simsunb.ttf", "PaperChineseBold"),
    ]

    normal_name = "Helvetica"
    bold_name = "Helvetica-Bold"
    for font_path, font_name in candidates:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                normal_name = font_name
                break
            except Exception:
                continue

    for font_path, font_name in bold_candidates:
        if Path(font_path).exists():
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                bold_name = font_name
                break
            except Exception:
                continue

    return normal_name, bold_name


NORMAL_FONT, BOLD_FONT = register_font()


def make_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "PaperTitle",
            parent=base["Title"],
            fontName=BOLD_FONT,
            fontSize=18,
            leading=26,
            alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "PaperHeading1",
            parent=base["Heading1"],
            fontName=BOLD_FONT,
            fontSize=15,
            leading=22,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "PaperHeading2",
            parent=base["Heading2"],
            fontName=BOLD_FONT,
            fontSize=12.5,
            leading=18,
            spaceBefore=9,
            spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "PaperHeading3",
            parent=base["Heading3"],
            fontName=BOLD_FONT,
            fontSize=11.5,
            leading=17,
            spaceBefore=7,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "PaperBody",
            parent=base["BodyText"],
            fontName=NORMAL_FONT,
            fontSize=10.5,
            leading=17,
            firstLineIndent=21,
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "body_no_indent": ParagraphStyle(
            "PaperBodyNoIndent",
            parent=base["BodyText"],
            fontName=NORMAL_FONT,
            fontSize=10.5,
            leading=17,
            firstLineIndent=0,
            alignment=TA_LEFT,
            spaceAfter=5,
        ),
        "list": ParagraphStyle(
            "PaperList",
            parent=base["BodyText"],
            fontName=NORMAL_FONT,
            fontSize=10.2,
            leading=16,
            leftIndent=18,
            firstLineIndent=-12,
            spaceAfter=3,
        ),
        "formula": ParagraphStyle(
            "PaperFormula",
            parent=base["BodyText"],
            fontName=NORMAL_FONT,
            fontSize=10,
            leading=15,
            alignment=TA_CENTER,
            spaceBefore=3,
            spaceAfter=5,
        ),
        "table": ParagraphStyle(
            "PaperTable",
            parent=base["BodyText"],
            fontName=NORMAL_FONT,
            fontSize=8.2,
            leading=11,
            alignment=TA_CENTER,
        ),
        "table_left": ParagraphStyle(
            "PaperTableLeft",
            parent=base["BodyText"],
            fontName=NORMAL_FONT,
            fontSize=8.2,
            leading=11,
            alignment=TA_LEFT,
        ),
    }
    return styles


STYLES = make_styles()


def inline(text: str) -> str:
    parts = re.split(r"(\*\*.*?\*\*|`.*?`)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            out.append(f"<b>{html.escape(part[2:-2])}</b>")
        elif part.startswith("`") and part.endswith("`"):
            out.append(f"<font name='{NORMAL_FONT}'>{html.escape(part[1:-1])}</font>")
        else:
            out.append(html.escape(part))
    return "".join(out)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = split_table_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def build_table(lines: list[str], usable_width: float) -> Table:
    rows = [split_table_row(line) for line in lines if not is_table_separator(line)]
    if not rows:
        return Table([[""]])

    col_count = max(len(row) for row in rows)
    rows = [row + [""] * (col_count - len(row)) for row in rows]

    if col_count == 2:
        widths = [usable_width * 0.36, usable_width * 0.64]
    elif col_count == 3:
        widths = [usable_width * 0.28, usable_width * 0.36, usable_width * 0.36]
    elif col_count == 4:
        widths = [usable_width * 0.34] + [usable_width * 0.22] * 3
    else:
        widths = [usable_width / col_count] * col_count

    data = []
    for r_idx, row in enumerate(rows):
        style = STYLES["table_left"] if col_count <= 2 else STYLES["table"]
        data.append([Paragraph(inline(cell), style) for cell in row])

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), NORMAL_FONT),
                ("FONTNAME", (0, 0), (-1, 0), BOLD_FONT),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def parse_markdown(markdown: str, usable_width: float):
    story = []
    lines = markdown.splitlines()
    i = 0
    in_formula = False
    formula_buffer: list[str] = []

    while i < len(lines):
        line = lines[i].rstrip()

        if not line:
            if formula_buffer:
                story.append(Paragraph(inline(" ".join(formula_buffer)), STYLES["formula"]))
                formula_buffer.clear()
            story.append(Spacer(1, 4))
            i += 1
            continue

        if line.strip() == "\\[":
            in_formula = True
            formula_buffer = []
            i += 1
            continue
        if line.strip() == "\\]":
            in_formula = False
            story.append(Paragraph(inline(" ".join(formula_buffer)), STYLES["formula"]))
            formula_buffer.clear()
            i += 1
            continue
        if in_formula:
            formula_buffer.append(line.strip())
            i += 1
            continue

        if line.startswith("|") and "|" in line[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].rstrip())
                i += 1
            story.append(build_table(table_lines, usable_width))
            story.append(Spacer(1, 8))
            continue

        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:].strip()), STYLES["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:].strip()), STYLES["h1"]))
        elif line.startswith("### "):
            story.append(Paragraph(inline(line[4:].strip()), STYLES["h2"]))
        elif line.startswith("#### "):
            story.append(Paragraph(inline(line[5:].strip()), STYLES["h3"]))
        elif re.match(r"^\d+\.\s+", line):
            story.append(Paragraph(inline(line), STYLES["list"]))
        elif line.startswith("- "):
            story.append(Paragraph(inline("• " + line[2:].strip()), STYLES["list"]))
        elif line.startswith("[") and re.match(r"^\[\d+\]", line):
            story.append(Paragraph(inline(line), STYLES["body_no_indent"]))
        else:
            style = STYLES["body_no_indent"] if line.startswith("**关键词") else STYLES["body"]
            story.append(Paragraph(inline(line), style))
        i += 1

    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(NORMAL_FONT, 9)
    canvas.drawCentredString(A4[0] / 2, 1.05 * cm, str(doc.page))
    canvas.restoreState()


def main() -> None:
    markdown = INPUT.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=2.1 * cm,
        leftMargin=2.1 * cm,
        topMargin=2.2 * cm,
        bottomMargin=1.8 * cm,
        title="电商物流网络货量预测、关停分流与网络优化模型",
        author="",
    )
    usable_width = A4[0] - doc.leftMargin - doc.rightMargin
    story = parse_markdown(markdown, usable_width)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
