"""Expand local LaTeX input files for deterministic content auditing."""

from __future__ import annotations

import re
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "source"
OUTPUT = Path(__file__).resolve().parents[2] / "qa" / "audit-main-expanded.tex"


def expand(text: str, base: Path) -> str:
    pattern = re.compile(r"\\input\{([^}]+)\}")

    def replace(match: re.Match[str]) -> str:
        candidate = base / match.group(1)
        if candidate.suffix == "":
            candidate = candidate.with_suffix(".tex")
        if not candidate.is_file():
            return match.group(0)
        return expand(candidate.read_text(encoding="utf-8"), candidate.parent)

    return pattern.sub(replace, text)


def main() -> None:
    main_source = SOURCE / "main.tex"
    OUTPUT.write_text(
        expand(main_source.read_text(encoding="utf-8"), SOURCE), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
