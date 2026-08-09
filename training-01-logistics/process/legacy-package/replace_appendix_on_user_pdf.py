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
BASE_PDF = ROOT / "paper_v1_latex" / "main_before_appendix_fix_user_modified.pdf"


def next_version_paths() -> tuple[Path, Path, int]:
    VERSION_DIR.mkdir(exist_ok=True)
    versions: list[int] = []
    for pdf in list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf")):
        match = re.fullmatch(r"modeling_paper_v(\d+)\.pdf", pdf.name)
        if match:
            versions.append(int(match.group(1)))

    next_version = max(versions) + 1 if versions else 1
    out_latex_dir = VERSION_DIR / f"paper_v{next_version}_latex"
    out_latex_dir.mkdir(parents=True, exist_ok=True)

    previous_version = next_version - 1
    for previous_latex_dir in [VERSION_DIR / f"paper_v{previous_version}_latex", ROOT / f"paper_v{previous_version}_latex"]:
        if previous_latex_dir.exists():
            for name in ["main.tex", "cumcm-paper.sty"]:
                src = previous_latex_dir / name
                if src.exists():
                    shutil.copy2(src, out_latex_dir / name)
            break

    return out_latex_dir / "main.pdf", VERSION_DIR / f"modeling_paper_v{next_version}.pdf", next_version


APPENDIX_GROUPS = [
    (
        "公共数据与说明",
        [
            ("数据", "paper_skill_materials/raw_data/history_volume_data.xlsx", "原始历史线路日货量数据"),
            ("说明", "目录说明.txt", "项目文件夹结构说明"),
        ],
    ),
    (
        "问题一：预测模型",
        [
            ("代码", "q1_revised/code/problem1_anomaly_corrected_forecast.py", "异常修正、LightGBM 预测与校准主程序"),
            ("结果", "q1_revised/results/revised_forecast_all_edges.csv", "2023 年 1 月全网各线路日预测货量"),
            ("结果", "q1_revised/results/revised_forecast_target_edges.csv", "三条指定线路预测结果"),
            ("结果", "q1_revised/results/problem1_before_after_validation_metrics.csv", "修正前后回测误差指标"),
            ("图表", "q1_revised/figures/daily_total_before_after.png", "全网日预测总量修正前后对比图"),
            ("图表", "q1_revised/figures/key_sites_before_after.png", "关键场地预测货量修正前后对比图"),
        ],
    ),
    (
        "问题二：DC5 关停分流",
        [
            ("代码", "q2_revised/code/problem2_dc5_revised_q1_milp.py", "DC5 关停已有线路分流 MILP 主程序"),
            ("结果", "q2_revised/results/problem2_revised_summary.csv", "DC5 关停分流汇总结果"),
            ("结果", "q2_revised/results/problem2_revised_daily_metrics.csv", "每日分流与变化线路指标"),
            ("结果", "q2_revised/results/problem2_revised_allocation_detail.csv", "分流明细长表"),
            ("结果", "q2_revised/results/problem2_revised_three_scheme_comparison.csv", "三种变化线路放宽方案对比"),
        ],
    ),
    (
        "问题三：DC9 动态线路调整",
        [
            ("代码", "q3_revised/code/problem3_dc9_dynamic_milp.py", "方案 A 最少变化 MILP 主程序"),
            ("代码", "q3_revised/code/problem3_dc9_flow_heuristic.py", "流启发式均衡方案程序"),
            ("代码", "q3_revised/code/problem3_dc9_pareto_milp.py", "新开与旧线路平衡对比程序"),
            ("结果", "q3_revised/results/problem3_balance_metric_comparison.csv", "三类方案统一指标对比"),
            ("结果", "q3_revised/results/problem3_dc9_dynamic_summary.csv", "方案 A 汇总结果"),
            ("结果", "q3_revised/results/problem3_dc9_dynamic_allocation_detail.csv", "方案 A 分流明细长表"),
            ("图表", "q3_revised/figures/problem3_balance_metric_comparison.png", "三类方案指标对比图"),
        ],
    ),
    (
        "问题四：重要性评价与新增场地",
        [
            ("代码", "q4_analysis/code/problem4_core_importance.py", "场地和线路重要性评价程序"),
            ("代码", "q4_analysis/code/problem4_new_site_design.py", "新增 DC_NEW 线路设计与鲁棒性检验程序"),
            ("结果", "q4_analysis/results/problem4_site_core_importance.csv", "场地重要性完整排序"),
            ("结果", "q4_analysis/results/problem4_edge_core_importance.csv", "线路重要性完整排序"),
            ("结果", "q4_analysis/results/problem4_new_site_lines.csv", "新增线路及能力结果"),
            ("结果", "q4_analysis/results/problem4_new_site_robustness_summary.csv", "新增场地鲁棒性检验汇总"),
            ("图表", "q4_analysis/figures/problem4_new_site_robustness_comparison.png", "鲁棒性改善对比图"),
        ],
    ),
]


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
    return lines


def draw_wrapped(c: canvas.Canvas, text: str, x: float, y: float, max_chars: int, leading: float = 13) -> float:
    for line in wrap_text(text, max_chars):
        c.drawString(x, y, line)
        y -= leading
    return y


def make_appendix_pdf(path: Path, start_page_no: int) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(str(path), pagesize=A4)
    page_w, page_h = A4
    left, right, top, bottom = 50, 50, 48, 46
    y = page_h - top
    page_no = start_page_no

    def new_page() -> None:
        nonlocal y, page_no
        c.setFont("STSong-Light", 10)
        c.drawCentredString(page_w / 2, 24, str(page_no))
        c.showPage()
        page_no += 1
        y = page_h - top

    c.setFont("STSong-Light", 18)
    c.drawString(left, y, "附录一  支撑材料与代码说明")
    y -= 32
    c.setFont("STSong-Light", 10.5)
    intro = (
        "本文正文已列出主要模型、关键指标和结论，未另设必须展示的大型结果表格。"
        "因此附录一统一列出各问题支撑材料、可运行代码、结果文件和图表文件，"
        "完整明细表以支撑材料中的 CSV/XLSX 文件形式提供。"
    )
    y = draw_wrapped(c, intro, left, y, 46, 15)
    y -= 8

    for group_title, rows in APPENDIX_GROUPS:
        if y < bottom + 95:
            new_page()
        c.setFont("STSong-Light", 12)
        c.drawString(left, y, group_title)
        y -= 18
        c.setFont("STSong-Light", 9.4)
        for file_type, filename, purpose in rows:
            item_lines = wrap_text(f"{file_type}：{filename}；{purpose}。", 62)
            need = len(item_lines) * 12 + 2
            if y - need < bottom:
                new_page()
                c.setFont("STSong-Light", 9.4)
            for idx, line in enumerate(item_lines):
                prefix = "• " if idx == 0 else "  "
                c.drawString(left + 10, y, prefix + line)
                y -= 12
            y -= 2
        y -= 8

    if y < bottom + 55:
        new_page()
    c.setFont("STSong-Light", 12)
    c.drawString(left, y, "运行与提交说明")
    y -= 18
    c.setFont("STSong-Light", 9.4)
    notes = [
        "各问题代码均按本项目相对路径读取输入文件，运行前保持原文件夹结构不变。",
        "结果文件和图表文件用于支撑正文中的预测、分流、方案比较和鲁棒性结论。",
        "提交支撑材料时，将上述数据、代码、结果和图表文件统一压缩为 ZIP 或 RAR 文件。",
        "支撑材料中不应出现参赛者身份、学校、赛区或个人系统路径等信息。",
    ]
    for note in notes:
        y = draw_wrapped(c, "• " + note, left + 10, y, 62, 12)
        y -= 2

    c.setFont("STSong-Light", 10)
    c.drawCentredString(page_w / 2, 24, str(page_no))
    c.save()


def replace_last_page(base_pdf: Path, appendix_pdf: Path, out_pdf: Path) -> None:
    reader = PdfReader(str(base_pdf))
    appendix_reader = PdfReader(str(appendix_pdf))
    writer = PdfWriter()
    for page in reader.pages[:-1]:
        writer.add_page(page)
    for page in appendix_reader.pages:
        writer.add_page(page)
    with out_pdf.open("wb") as f:
        writer.write(f)


def main() -> None:
    out_main, out_root, next_version = next_version_paths()
    reader = PdfReader(str(BASE_PDF))
    with TemporaryDirectory() as tmp:
        appendix_pdf = Path(tmp) / "appendix.pdf"
        make_appendix_pdf(appendix_pdf, len(reader.pages))
        replace_last_page(BASE_PDF, appendix_pdf, out_main)
    out_root.write_bytes(out_main.read_bytes())
    print(f"Created V{next_version}: {out_root}")
    print(f"LaTeX copy: {out_main}")


if __name__ == "__main__":
    main()
