"""Convert the verified Markdown question notes to LaTeX body fragments."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT.parents[1]
SOURCE = ROOT / "source"


def inline(text: str) -> str:
    text = re.sub(r"(?<!\\)%", r"\\%", text).replace("#", r"\#")
    text = re.sub(r"\*\*(.+?)\*\*", r"\textbf{\1}", text)
    text = re.sub(r"`([^`]+)`", lambda m: r"\texttt{" + m.group(1).replace("_", r"\_") + "}", text)
    return text


def convert(markdown: Path, output: Path, section_title: str, label_prefix: str) -> None:
    lines = markdown.read_text(encoding="utf-8").splitlines()
    out = [rf"\section{{{section_title}}}"]
    in_math = False
    in_list = False
    pending_caption = None
    table_count = 0
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        stripped = raw.strip()
        if stripped.startswith("# "):
            i += 1; continue
        if stripped.startswith("## "):
            if in_list: out.append(r"\end{itemize}"); in_list = False
            title = re.sub(r"^\d+\.\s*", "", stripped[3:])
            out.append(rf"\subsection{{{inline(title)}}}"); i += 1; continue
        if stripped.startswith("### "):
            if in_list: out.append(r"\end{itemize}"); in_list = False
            title = re.sub(r"^\d+(\.\d+)*\s*", "", stripped[4:])
            out.append(rf"\subsubsection{{{inline(title)}}}"); i += 1; continue
        if stripped == r"\[":
            if in_list: out.append(r"\end{itemize}"); in_list = False
            out.append(r"\["); in_math = True; i += 1; continue
        if stripped == r"\]":
            out.append(r"\]"); in_math = False; i += 1; continue
        if in_math:
            out.append(raw); i += 1; continue
        if stripped.startswith("**表") and stripped.endswith("**"):
            pending_caption = stripped[2:-2]; i += 1; continue
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            rows = []
            header = [cell.strip() for cell in stripped.strip("|").split("|")]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([cell.strip() for cell in lines[i].strip().strip("|").split("|")]); i += 1
            cols = len(header)
            table_count += 1
            out.append(r"\begin{table}[H]\centering\small")
            if pending_caption:
                out.append(rf"\caption{{{inline(pending_caption)}}}"); pending_caption = None
            else:
                out.append(rf"\caption{{{section_title}变量与计算符号说明}}")
            out.append(rf"\label{{tab:{label_prefix}-{table_count}}}")
            if cols >= 4:
                out.append(r"\resizebox{\textwidth}{!}{%")
            out.append(r"\begin{tabular}{" + "c" * cols + "}")
            out.append(r"\toprule")
            out.append(" & ".join(inline(c) for c in header) + r" \\")
            out.append(r"\midrule")
            for row in rows:
                row += [""] * (cols - len(row))
                out.append(" & ".join(inline(c) for c in row[:cols]) + r" \\")
            out.extend([r"\bottomrule", r"\end{tabular}"])
            if cols >= 4:
                out.append("}")
            out.append(r"\end{table}")
            continue
        if re.match(r"^\d+\.\s+", stripped) or stripped.startswith("- "):
            if not in_list: out.append(r"\begin{itemize}"); in_list = True
            content = re.sub(r"^(\d+\.|-)\s+", "", stripped)
            out.append(r"\item " + inline(content)); i += 1; continue
        if in_list:
            out.append(r"\end{itemize}"); in_list = False
        if stripped:
            out.append(inline(stripped) + "\n")
        i += 1
    if in_list: out.append(r"\end{itemize}")
    output.write_text("\n".join(out), encoding="utf-8")


def main() -> None:
    convert(PROJECT / "question-1" / "docs" / "question-1-paper-draft.md", SOURCE / "question-1.tex", "问题一：静水风载下的系统响应", "q1")
    convert(PROJECT / "question-2" / "docs" / "question-2-complete-solution.md", SOURCE / "question-2.tex", "问题二：极端风速下的最小配重", "q2")
    convert(PROJECT / "question-3" / "docs" / "question-3-complete-solution.md", SOURCE / "question-3.tex", "问题三：风流耦合下的鲁棒设计", "q3")


if __name__ == "__main__":
    main()
