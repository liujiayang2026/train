from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VERSION_DIR = ROOT / "paper_versions"
MD_PATH = ROOT / "modeling_paper_v1.md"


def next_latex_dir() -> Path:
    VERSION_DIR.mkdir(exist_ok=True)
    versions: list[int] = []
    for pdf in list(ROOT.glob("modeling_paper_v*.pdf")) + list(VERSION_DIR.glob("modeling_paper_v*.pdf")):
        match = re.fullmatch(r"modeling_paper_v(\d+)\.pdf", pdf.name)
        if match:
            versions.append(int(match.group(1)))
    next_version = max(versions) + 1 if versions else 1
    return VERSION_DIR / f"paper_v{next_version}_latex"


OUT_DIR = next_latex_dir()
TEX_PATH = OUT_DIR / "main.tex"
STYLE_SOURCE = ROOT / "paper_skill_materials" / "latex_source" / "cumcm-paper.sty"


SPECIALS = {
    "&": r"\&",
    "%": r"\%",
    "#": r"\#",
}


TABLE_CAPTIONS = {
    1: "主要符号说明",
    2: "问题一总量校准指标",
    3: "问题一预测模型回测误差",
    4: "三条指定线路月预测货量",
    5: "问题二 MILP 决策变量",
    6: "问题二变化线路放宽方案对比",
    7: "问题二 DC5 关停分流结果",
    8: "问题二未正常流转日期与货量",
    9: "问题三三类方案建模思路对比",
    10: "问题三三类方案统一指标对比",
    11: "问题三方案 A MILP 决策变量",
    12: "问题三方案 A 分流结果",
    13: "问题四场地重要性前十五名",
    14: "问题四线路重要性前二十名",
    15: "问题四新增 DC_NEW 有向线路及能力",
    16: "问题四新增场地鲁棒性改善结果",
    17: "附录支撑材料文件索引",
}


def normalize_math(text: str) -> str:
    if text.startswith(r"\(") and text.endswith(r"\)"):
        text = "$" + text[2:-2] + "$"
    return text.replace(r"\_", "_")


def escape_text(text: str) -> str:
    segments = re.split(r"(\$.*?\$|\\\(.*?\\\)|`.*?`|\*\*.*?\*\*)", text)
    out: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if (seg.startswith("$") and seg.endswith("$")) or (seg.startswith(r"\(") and seg.endswith(r"\)")):
            out.append(normalize_math(seg))
        elif seg.startswith("`") and seg.endswith("`"):
            inner = seg[1:-1]
            inner = inner.replace("{", r"\{").replace("}", r"\}")
            out.append(r"\path{" + inner + "}")
        elif seg.startswith("**") and seg.endswith("**"):
            inner = escape_text(seg[2:-2])
            out.append(r"\textbf{" + inner + "}")
        else:
            s = seg
            for old, new in SPECIALS.items():
                s = s.replace(old, new)
            s = s.replace("_", r"\_")
            out.append(s)
    return "".join(out)


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def table_to_tex(lines: list[str], counter: int) -> str:
    rows = [split_row(line) for line in lines if not is_separator(line)]
    if not rows:
        return ""
    ncol = max(len(row) for row in rows)
    rows = [row + [""] * (ncol - len(row)) for row in rows]
    if ncol == 2:
        align = r"@{}L{0.50\textwidth}@{\extracolsep{\fill}}L{0.42\textwidth}@{}"
    elif ncol == 3:
        align = r"L{0.28\textwidth}L{0.28\textwidth}L{0.34\textwidth}"
    elif ncol == 4:
        align = "lrrr"
    else:
        align = "l" * ncol
    body = []
    for idx, row in enumerate(rows):
        escaped = [escape_text(cell) for cell in row]
        body.append(" & ".join(escaped) + r" \\")
        if idx == 0:
            body.append(r"\midrule")
    tabular = "\n".join(body)
    caption = TABLE_CAPTIONS.get(counter, f"结果汇总 {counter}")
    if ncol >= 4:
        content = rf"""
\begin{{table}}[H]
  \centering
  \caption{{{escape_text(caption)}}}
  \label{{tab:auto-{counter}}}
  \resizebox{{\textwidth}}{{!}}{{%
  \begin{{tabular}}{{{align}}}
    \toprule
{tabular}
    \bottomrule
  \end{{tabular}}}}
\end{{table}}
"""
    elif ncol == 2:
        content = rf"""
\begin{{table}}[H]
  \centering
  \caption{{{escape_text(caption)}}}
  \label{{tab:auto-{counter}}}
  \begin{{tabular*}}{{\textwidth}}{{{align}}}
    \toprule
{tabular}
    \bottomrule
  \end{{tabular*}}
\end{{table}}
"""
    else:
        content = rf"""
\begin{{table}}[H]
  \centering
  \caption{{{escape_text(caption)}}}
  \label{{tab:auto-{counter}}}
  \begin{{tabular}}{{{align}}}
    \toprule
{tabular}
    \bottomrule
  \end{{tabular}}
\end{{table}}
"""
    return content


def image_to_tex(line: str) -> str:
    match = re.match(r"^!\[(.*?)\]\((.*?)\)$", line.strip())
    if not match:
        return ""
    caption = match.group(1).strip()
    image_path = match.group(2).strip().replace("\\", "/")
    if not re.match(r"^[A-Za-z]:/", image_path) and not image_path.startswith("../"):
        prefix = "../../" if OUT_DIR.parent.name == "paper_versions" else "../"
        image_path = prefix + image_path
    return rf"""
\begin{{figure}}[H]
  \centering
  \includegraphics[width=0.95\textwidth]{{\detokenize{{{image_path}}}}}
  \caption{{{escape_text(caption)}}}
\end{{figure}}
"""


def parse_body(lines: list[str]) -> str:
    chunks: list[str] = []
    i = 0
    table_counter = 1
    in_display = False
    display_lines: list[str] = []
    list_env: str | None = None

    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()

        if line == r"\[":
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            in_display = True
            display_lines = []
            i += 1
            continue
        if line == r"\]":
            formula = "\n".join(display_lines).strip()
            formula = formula.replace(
                r"\sum_{e\in \delta(k)}新增分流量",
                r"\sum_{e\in \delta(k)} a^{new}_{e,k,t}",
            )
            chunks.append(r"\begin{equation}" + "\n" + formula + "\n" + r"\end{equation}")
            in_display = False
            display_lines = []
            i += 1
            continue
        if in_display:
            if line:
                display_lines.append(raw)
            i += 1
            continue

        if not line:
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            chunks.append("")
            i += 1
            continue

        if line.startswith("|") and "|" in line[1:]:
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].rstrip())
                i += 1
            chunks.append(table_to_tex(table_lines, table_counter))
            table_counter += 1
            continue

        if re.match(r"^!\[.*?\]\(.*?\)$", line):
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            chunks.append(image_to_tex(line))
            i += 1
            continue

        if re.match(r"^\d+\.\s+", line):
            if list_env != "enumerate":
                if list_env:
                    chunks.append(rf"\end{{{list_env}}}")
                chunks.append(r"\begin{enumerate}")
                list_env = "enumerate"
            item = re.sub(r"^\d+\.\s+", "", line)
            chunks.append(r"\item " + escape_text(item))
            i += 1
            continue

        if line.startswith("# "):
            i += 1
            continue
        if line.startswith("## "):
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            title = re.sub(r"^\d+\s+", "", line[3:].strip())
            chunks.append(r"\section{" + escape_text(title) + "}")
        elif line.startswith("### "):
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            title = re.sub(r"^\d+(?:\.\d+)*\s+", "", line[4:].strip())
            chunks.append(r"\subsection{" + escape_text(title) + "}")
        elif line.startswith("#### "):
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            title = re.sub(r"^\d+(?:\.\d+)*\s+", "", line[5:].strip())
            chunks.append(r"\subsubsection{" + escape_text(title) + "}")
        elif line.startswith("- "):
            if list_env != "itemize":
                if list_env:
                    chunks.append(rf"\end{{{list_env}}}")
                chunks.append(r"\begin{itemize}")
                list_env = "itemize"
            chunks.append(r"\item " + escape_text(line[2:]))
        else:
            if list_env:
                chunks.append(rf"\end{{{list_env}}}")
                list_env = None
            chunks.append(escape_text(line))
        i += 1

    if list_env:
        chunks.append(rf"\end{{{list_env}}}")
    return "\n\n".join(chunks)


def split_markdown(md: str) -> tuple[str, str, str, str]:
    title = "电商物流网络货量预测、关停分流与网络优化模型"
    match = re.search(r"^#\s+(.+)$", md, re.M)
    if match:
        title = match.group(1).strip()

    abstract_match = re.search(r"## 摘要\s+(.*?)\n\*\*关键词：\*\*(.*?)\n## 1 ", md, re.S)
    if not abstract_match:
        raise RuntimeError("Cannot find abstract and keywords in markdown.")
    abstract = abstract_match.group(1).strip()
    keywords = abstract_match.group(2).strip()
    body_start = md.index("## 1 ")
    body = md[body_start:]
    return title, abstract, keywords, body


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    shutil.copy2(STYLE_SOURCE, OUT_DIR / "cumcm-paper.sty")

    md = MD_PATH.read_text(encoding="utf-8")
    title, abstract, keywords, body = split_markdown(md)
    abstract_paragraphs = [escape_text(p.strip()) for p in abstract.split("\n\n") if p.strip()]
    if abstract_paragraphs:
        abstract_paragraphs[0] = r"\hspace{2em}" + abstract_paragraphs[0]
    abstract_tex = "\n\n".join(abstract_paragraphs)
    body_tex = parse_body(body.splitlines())
    keywords_tex = escape_text(keywords)

    tex = rf"""\documentclass[UTF8,zihao=-4,a4paper,fontset=fandol]{{ctexart}}
\usepackage{{cumcm-paper}}
\usepackage{{makecell}}
\usepackage{{multirow}}

\title{{{escape_text(title)}}}
\author{{}}
\date{{}}

\begin{{document}}

\maketitle

\begin{{cumcmabstract}}
{abstract_tex}
\end{{cumcmabstract}}

\keywords{{{keywords_tex}}}

\CumcmBodyStart

{body_tex}

\CumcmMainMatterEnd

\end{{document}}
"""
    TEX_PATH.write_text(tex, encoding="utf-8")
    print(TEX_PATH)


if __name__ == "__main__":
    main()
