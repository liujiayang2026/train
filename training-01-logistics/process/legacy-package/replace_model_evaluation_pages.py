from __future__ import annotations

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import replace_appendix_from_markdown as appendix_builder


ROOT = Path(__file__).resolve().parent
VERSION_DIR = ROOT / "paper_versions"
MD_PATH = ROOT / "modeling_paper_v1.md"


def version_number(path: Path) -> int | None:
    match = re.fullmatch(r"modeling_paper_v(\d+)\.pdf", path.name)
    return int(match.group(1)) if match else None


def latest_pdf() -> tuple[Path, int]:
    clean_base = VERSION_DIR / "modeling_paper_v3.pdf"
    if clean_base.exists():
        pdfs = list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf"))
        versions = [version_number(path) or 0 for path in pdfs if version_number(path) is not None]
        return clean_base, max(versions) if versions else 3

    pdfs = list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf"))
    numbered = [(version_number(path), path) for path in pdfs]
    numbered = [(num, path) for num, path in numbered if num is not None]
    if not numbered:
        raise FileNotFoundError("未找到 modeling_paper_v*.pdf")
    num, path = max(numbered, key=lambda item: item[0])
    return path, int(num)


def next_paths() -> tuple[Path, Path, Path, int]:
    source_pdf, current_version = latest_pdf()
    next_version = current_version + 1
    out_latex_dir = VERSION_DIR / f"paper_v{next_version}_latex"
    out_latex_dir.mkdir(parents=True, exist_ok=True)

    for previous_latex_dir in [VERSION_DIR / f"paper_v{current_version}_latex", ROOT / f"paper_v{current_version}_latex"]:
        if previous_latex_dir.exists():
            for name in ["main.tex", "cumcm-paper.sty"]:
                src = previous_latex_dir / name
                if src.exists():
                    shutil.copy2(src, out_latex_dir / name)
            break

    return source_pdf, out_latex_dir / "main.pdf", VERSION_DIR / f"modeling_paper_v{next_version}.pdf", next_version


def extract_tail_lines() -> list[str]:
    text = MD_PATH.read_text(encoding="utf-8")
    start = text.index("## 8 模型评价")
    appendix_match = re.search(r"^##\s*附录\s*1", text, flags=re.MULTILINE)
    if appendix_match is None:
        raise ValueError("未找到附录 1")
    tail = text[start:appendix_match.start()].strip()
    tail = tail.replace(r"\(\delta=0,2,5\)", "δ=0,2,5")
    tail = tail.replace(r"\(\delta=2\)", "δ=2")
    tail = tail.replace("`", "")
    return tail.splitlines()


def wrap_text(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return [""]
    lines: list[str] = []
    current = ""
    chunks = re.findall(r"[A-Za-z0-9_]+|[^\x00-\x7F]|.", text)
    for chunk in chunks:
        if current and len(current) + len(chunk) > max_chars:
            lines.append(current)
            current = chunk
        else:
            current += chunk
    if current:
        lines.append(current)
    return lines


def make_tail_pdf(path: Path, start_page_no: int) -> int:
    font_name = "TailChinese"
    font_candidates = [
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simfang.ttf"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
            break
    else:
        font_name = "STSong-Light"
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4
    left, right, top, bottom = 58, 58, 54, 48
    y = page_h - top
    page_no = start_page_no

    def footer() -> None:
        c.setFont(font_name, 10)
        c.drawCentredString(page_w / 2, 24, str(page_no))

    def new_page() -> None:
        nonlocal y, page_no
        footer()
        c.showPage()
        page_no += 1
        y = page_h - top

    def draw_line(text: str, font_size: float, leading: float, indent: float = 0, max_chars: int = 42) -> None:
        nonlocal y
        for idx, part in enumerate(wrap_text(text, max_chars)):
            if y < bottom + leading:
                new_page()
            c.setFont(font_name, font_size)
            x = left + indent + (14 if idx > 0 and indent else 0)
            c.drawString(x, y, part)
            y -= leading

    for raw in extract_tail_lines():
        line = raw.strip()
        if not line:
            y -= 6
            continue
        if line.startswith("## "):
            if y < bottom + 45:
                new_page()
            draw_line(line[3:], 14, 22, 0, 25)
            y -= 3
        elif re.match(r"^\d+\.\s+", line):
            draw_line(line, 10.2, 16.5, 8, 47)
        elif line.startswith("["):
            draw_line(line, 10, 15, 0, 62)
        else:
            draw_line(line, 10.2, 16.5, 0, 47)

    footer()
    c.save()
    return page_no - start_page_no + 1


def find_appendix_start(reader: PdfReader) -> int:
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if "附录" in text:
            return idx
    return len(reader.pages) - 1


def main() -> None:
    source_pdf, out_main, out_root, next_version = next_paths()
    reader = PdfReader(str(source_pdf))
    appendix_start = find_appendix_start(reader)
    replace_start = max(0, appendix_start - 1)

    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tail_pdf = tmp_dir / "tail.pdf"
        tail_pages = make_tail_pdf(tail_pdf, replace_start + 1)

        title, intro, rows = appendix_builder.extract_appendix_rows()
        appendix_pdf = tmp_dir / "appendix.pdf"
        appendix_builder.make_appendix_pdf(appendix_pdf, title, intro, rows, replace_start + tail_pages + 1)

        writer = PdfWriter()
        for page in reader.pages[:replace_start]:
            writer.add_page(page)
        for page in PdfReader(str(tail_pdf)).pages:
            writer.add_page(page)
        for page in PdfReader(str(appendix_pdf)).pages:
            writer.add_page(page)
        with out_main.open("wb") as f:
            writer.write(f)

    out_root.write_bytes(out_main.read_bytes())
    print(f"Source PDF: {source_pdf}")
    print(f"Created V{next_version}: {out_root}")
    print(f"LaTeX copy: {out_main}")


if __name__ == "__main__":
    main()
