from __future__ import annotations

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
VERSION_DIR = ROOT / "paper_versions"
MD_PATH = ROOT / "modeling_paper_v1.md"
APPENDIX_MARKER_PATTERN = re.compile(r"^##\s*附录\s*1", re.MULTILINE)


def version_number(path: Path) -> int | None:
    match = re.fullmatch(r"modeling_paper_v(\d+)\.pdf", path.name)
    return int(match.group(1)) if match else None


def collect_version_pdfs() -> list[Path]:
    VERSION_DIR.mkdir(exist_ok=True)
    pdfs = list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf"))
    return [pdf for pdf in pdfs if version_number(pdf) is not None]


def next_version_paths() -> tuple[Path, Path, Path, int]:
    pdfs = collect_version_pdfs()
    current_version = max((version_number(pdf) or 0) for pdf in pdfs) if pdfs else 1
    next_version = current_version + 1

    source_candidates = [
        VERSION_DIR / f"paper_v{current_version}_latex" / "main.pdf",
        ROOT / f"paper_v{current_version}_latex" / "main.pdf",
        VERSION_DIR / f"modeling_paper_v{current_version}.pdf",
        ROOT / f"modeling_paper_v{current_version}.pdf",
    ]
    source_pdf = next(path for path in source_candidates if path.exists())

    out_latex_dir = VERSION_DIR / f"paper_v{next_version}_latex"
    out_latex_dir.mkdir(parents=True, exist_ok=True)

    previous_latex_dirs = [
        VERSION_DIR / f"paper_v{current_version}_latex",
        ROOT / f"paper_v{current_version}_latex",
    ]
    for previous_latex_dir in previous_latex_dirs:
        if previous_latex_dir.exists():
            for name in ["main.tex", "cumcm-paper.sty"]:
                src = previous_latex_dir / name
                if src.exists():
                    shutil.copy2(src, out_latex_dir / name)
            break

    return source_pdf, out_latex_dir / "main.pdf", VERSION_DIR / f"modeling_paper_v{next_version}.pdf", next_version


def extract_appendix_rows() -> tuple[str, str, list[str]]:
    text = MD_PATH.read_text(encoding="utf-8")
    marker = APPENDIX_MARKER_PATTERN.search(text)
    if marker is None:
        raise ValueError("未找到附录 1 标题。")

    lines = [line.strip().replace("`", "") for line in text[marker.start():].splitlines()]
    lines = [line for line in lines if line]
    title = lines[0].replace("##", "").strip()
    intro = lines[1] if len(lines) > 1 else "介绍：支撑材料的文件列表"
    rows = lines[2:]
    return title, intro, rows


def wrap_text(text: str, max_chars: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in text:
        current += ch
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines or [""]


def make_appendix_pdf(path: Path, title: str, intro: str, rows: list[str], start_page_no: int) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4
    x = 70
    y = page_h - 68

    c.setFont("STSong-Light", 12.5)
    c.drawString(x, y, title)
    y -= 24

    c.setFont("STSong-Light", 10.8)
    c.drawString(x, y, intro)
    y -= 22

    c.setFont("STSong-Light", 10.8)
    for row in rows:
        for idx, part in enumerate(wrap_text(row, 50)):
            c.drawString(x, y, part if idx == 0 else "    " + part)
            y -= 18
        y -= 3

    c.setFont("STSong-Light", 10)
    c.drawCentredString(page_w / 2, 24, str(start_page_no))
    c.save()


def find_appendix_start(reader: PdfReader) -> int:
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if "附录" in text:
            return idx
    return 21


def main() -> None:
    source_pdf, out_main, out_root, next_version = next_version_paths()
    title, intro, rows = extract_appendix_rows()
    reader = PdfReader(str(source_pdf))
    appendix_start = find_appendix_start(reader)

    with TemporaryDirectory() as tmp:
        appendix_pdf = Path(tmp) / "appendix.pdf"
        make_appendix_pdf(appendix_pdf, title, intro, rows, appendix_start + 1)
        appendix_reader = PdfReader(str(appendix_pdf))

        writer = PdfWriter()
        for page in reader.pages[:appendix_start]:
            writer.add_page(page)
        for page in appendix_reader.pages:
            writer.add_page(page)
        with out_main.open("wb") as f:
            writer.write(f)

    out_root.write_bytes(out_main.read_bytes())
    print(f"Source PDF: {source_pdf}")
    print(f"Created V{next_version}: {out_root}")
    print(f"LaTeX copy: {out_main}")


if __name__ == "__main__":
    main()
