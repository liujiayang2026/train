from __future__ import annotations

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parent
VERSION_DIR = ROOT / "paper_versions"


def next_version_paths() -> tuple[Path, Path, Path, int]:
    VERSION_DIR.mkdir(exist_ok=True)
    versions: list[int] = []
    for pdf in list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf")):
        match = re.fullmatch(r"modeling_paper_v(\d+)\.pdf", pdf.name)
        if match:
            versions.append(int(match.group(1)))

    current_version = max(versions) if versions else 1
    source_candidates = [
        VERSION_DIR / f"paper_v{current_version}_latex" / "main.pdf",
        ROOT / f"paper_v{current_version}_latex" / "main.pdf",
        VERSION_DIR / f"modeling_paper_v{current_version}.pdf",
        ROOT / f"modeling_paper_v{current_version}.pdf",
    ]
    source_pdf = next(path for path in source_candidates if path.exists())

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


def draw_fit_image(c: canvas.Canvas, image_path: Path, x: float, y_top: float, max_w: float, max_h: float) -> float:
    with Image.open(image_path) as img:
        width, height = img.size
    scale = min(max_w / width, max_h / height)
    draw_w = width * scale
    draw_h = height * scale
    c.drawImage(ImageReader(str(image_path)), x + (max_w - draw_w) / 2, y_top - draw_h, draw_w, draw_h)
    return draw_h


def make_q1_page(path: Path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4
    margin = 42

    y = page_h - 48
    img_w = page_w - 2 * margin
    img_h = 255
    draw_fit_image(c, ROOT / "q1_revised" / "figures" / "daily_total_before_after.png", margin, y, img_w, img_h)
    c.setFont("STSong-Light", 10.5)
    c.drawCentredString(page_w / 2, y - img_h - 12, "（a）全网每日预测总量修正前后对比")

    y2 = y - img_h - 48
    draw_fit_image(c, ROOT / "q1_revised" / "figures" / "key_sites_before_after.png", margin, y2, img_w, img_h)
    c.drawCentredString(page_w / 2, y2 - img_h - 12, "（b）关键场地预测货量修正前后对比")
    c.setFont("STSong-Light", 12)
    c.drawCentredString(page_w / 2, y2 - img_h - 38, "图 1  问题一预测修正前后可视化")
    c.save()


def make_q4_page(path: Path) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4
    margin = 38
    draw_fit_image(
        c,
        ROOT / "q4_analysis" / "figures" / "problem4_new_site_robustness_comparison.png",
        margin,
        page_h - 82,
        page_w - 2 * margin,
        470,
    )
    c.setFont("STSong-Light", 12)
    c.drawCentredString(page_w / 2, page_h - 580, "图 2  问题四新增场地方案鲁棒性改善对比")
    c.setFont("STSong-Light", 10.5)
    c.drawCentredString(page_w / 2, page_h - 604, "新增 DC_NEW 前后在超载记录、超载总量和负荷率标准差上的对比")
    c.save()


def insert_pages(base_pdf: Path, q1_pdf: Path, q4_pdf: Path, output_pdf: Path) -> None:
    reader = PdfReader(str(base_pdf))
    writer = PdfWriter()
    q1_page = PdfReader(str(q1_pdf)).pages[0]
    q4_page = PdfReader(str(q4_pdf)).pages[0]

    for page_index, page in enumerate(reader.pages, start=1):
        writer.add_page(page)
        if page_index == 5:
            writer.add_page(q1_page)
        if page_index == 15:
            writer.add_page(q4_page)

    with output_pdf.open("wb") as f:
        writer.write(f)


def main() -> None:
    source_pdf, out_paper_pdf, out_root_pdf, next_version = next_version_paths()
    with TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        q1_pdf = tmp_dir / "q1_visuals.pdf"
        q4_pdf = tmp_dir / "q4_visuals.pdf"
        make_q1_page(q1_pdf)
        make_q4_page(q4_pdf)
        insert_pages(source_pdf, q1_pdf, q4_pdf, out_paper_pdf)
    out_root_pdf.write_bytes(out_paper_pdf.read_bytes())
    print(f"Source PDF: {source_pdf}")
    print(f"Created V{next_version}: {out_root_pdf}")
    print(f"LaTeX copy: {out_paper_pdf}")


if __name__ == "__main__":
    main()
