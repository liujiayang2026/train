#!/usr/bin/env python3
"""Validate process-only CUMCM human modeling intake packages.

The validator intentionally uses only the Python standard library so every
teammate and GitHub Actions can run it without installing project dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


ROUTE_RE = re.compile(r"r\d{2}-[a-z0-9][a-z0-9-]*$")
RUN_RE = re.compile(r"run-\d{8}-\d{4}-[a-z0-9][a-z0-9-]*$")
DECISION_RE = re.compile(r"d\d{2}-[a-z0-9][a-z0-9-]*\.md$")
COMPARISON_RE = re.compile(r"compare-[a-z0-9][a-z0-9-]*\.md$")
QUESTION_RE = re.compile(r"q\d+$")

ROUTE_FIELDS = (
    "对应问题",
    "过程状态",
    "要回答的内容",
    "输入与数据口径",
    "核心模型/算法",
    "代码入口",
    "关联运行",
    "与其他问题/路线的关系",
    "当前优点",
    "已知缺陷或冲突",
    "放弃时的原因",
)

RUN_FIELDS = (
    "日期时间",
    "执行目录",
    "执行命令",
    "代码入口/版本",
    "输入文件",
    "关键参数",
    "随机种子",
    "环境/依赖",
    "结果文件",
    "图表文件",
    "验证文件",
    "是否成功完成",
    "异常与备注",
)

PLACEHOLDER_VALUES = {"", "todo", "tbd", "待定", "待填写", "未填写", "placeholder"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    packages: int = 0
    routes: int = 0
    runs: int = 0

    def error(self, path: Path | str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def warn(self, path: Path | str, message: str) -> None:
        self.warnings.append(f"{path}: {message}")


def read_text(path: Path, report: Report) -> str | None:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        report.error(path, f"cannot read UTF-8 text: {exc}")
        return None


def read_json(path: Path, report: Report) -> dict | None:
    text = read_text(path, report)
    if text is None:
        return None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        report.error(path, f"invalid JSON: {exc}")
        return None
    if not isinstance(value, dict):
        report.error(path, "top-level JSON value must be an object")
        return None
    return value


def normalized_relative(value: str) -> PurePosixPath | None:
    candidate = PurePosixPath(value.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate


def parse_template_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        body = stripped[1:].strip()
        match = re.match(r"([^：:]+)[：:]\s*(.*)$", body)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def require_filled_fields(path: Path, fields: tuple[str, ...], report: Report) -> dict[str, str]:
    text = read_text(path, report)
    if text is None:
        return {}
    parsed = parse_template_fields(text)
    for name in fields:
        if name not in parsed:
            report.error(path, f"missing template field: {name}")
            continue
        if parsed[name].strip().lower() in PLACEHOLDER_VALUES:
            report.error(path, f"template field is not filled: {name}")
    return parsed


def validate_run(run: Path, report: Report) -> None:
    report.runs += 1
    if not RUN_RE.fullmatch(run.name):
        report.error(run, "run directory must match run-YYYYMMDD-HHMM-label")
    run_md = run / "run.md"
    if not run_md.is_file():
        report.error(run, "missing run.md")
        return
    fields = require_filled_fields(run_md, RUN_FIELDS, report)
    status = fields.get("是否成功完成", "").lower()
    if status and status not in {"yes", "no", "partial"}:
        report.error(run_md, "是否成功完成 must be yes, no, or partial")

    allowed = {"run.md", "results", "figures", "validation", "logs"}
    for child in run.iterdir():
        if child.name not in allowed:
            report.error(child, "unexpected item in run directory")
    artifact_dirs = [run / name for name in ("results", "figures", "validation", "logs")]
    if not any(
        path.is_dir() and any(candidate.is_file() for candidate in path.rglob("*"))
        for path in artifact_dirs
    ):
        report.warn(run, "run has no recorded result, figure, validation, or log artifact")


def validate_route(route: Path, question: str, report: Report) -> None:
    report.routes += 1
    if not ROUTE_RE.fullmatch(route.name):
        report.error(route, "route directory must match rNN-short-name")
    route_md = route / "route.md"
    if not route_md.is_file():
        report.error(route, "missing route.md")
    else:
        fields = require_filled_fields(route_md, ROUTE_FIELDS, report)
        status = fields.get("过程状态", "").lower()
        if status and status not in {"candidate", "abandoned", "uncertain"}:
            report.error(route_md, "过程状态 must be candidate, abandoned, or uncertain")
        declared_question = fields.get("对应问题", "").lower()
        if declared_question and declared_question != question.lower():
            report.error(route_md, f"对应问题 must be {question}")

    allowed = {"route.md", "notes", "inputs", "model", "code", "runs"}
    for child in route.iterdir():
        if child.name not in allowed:
            report.error(child, "unexpected item in route directory")
    runs = route / "runs"
    if runs.is_dir():
        for child in sorted(runs.iterdir()):
            if child.is_dir():
                validate_run(child, report)
            elif child.name != ".gitkeep":
                report.error(child, "runs/ may contain only run directories")


def validate_question(question_dir: Path, report: Report) -> None:
    if not (question_dir / "README.md").is_file():
        report.error(question_dir, "missing README.md")
    allowed = {"README.md", "inbox", "routes", "comparisons", "decisions"}
    for child in question_dir.iterdir():
        if child.name not in allowed:
            report.error(child, "unexpected item in question directory")

    routes = question_dir / "routes"
    if routes.is_dir():
        for child in sorted(routes.iterdir()):
            if child.is_dir():
                validate_route(child, question_dir.name, report)
            elif child.name != ".gitkeep":
                report.error(child, "routes/ may contain only route directories")

    comparisons = question_dir / "comparisons"
    if comparisons.is_dir():
        for child in comparisons.iterdir():
            if child.is_dir():
                report.error(child, "comparisons/ may contain only Markdown comparison files")
            elif child.name != ".gitkeep" and not COMPARISON_RE.fullmatch(child.name):
                report.error(child, "comparison file must match compare-short-title.md")

    decisions = question_dir / "decisions"
    if decisions.is_dir():
        for child in decisions.iterdir():
            if child.is_dir():
                report.error(child, "decisions/ may contain only Markdown decision files")
            elif child.name != ".gitkeep" and not DECISION_RE.fullmatch(child.name):
                report.error(child, "decision file must match dNN-short-title.md")


def validate_package(package: Path, report: Report) -> None:
    report.packages += 1
    required_files = ("README.md", "PROCESS_GUIDE.md", "human-process.json", "process/README.md", "process/common/README.md")
    for value in required_files:
        if not (package / value).is_file():
            report.error(package / value, "required package file is missing")

    if (package / "final").exists():
        report.error(package / "final", "final/ is forbidden in a process-only intake")
    if (package / "human-package.json").exists():
        report.error(package / "human-package.json", "generated finalization manifest is forbidden in intake")

    intake = read_json(package / "human-process.json", report)
    if intake is None:
        return
    if intake.get("schema_version") != 3:
        report.error(package / "human-process.json", "schema_version must be 3")
    if intake.get("intake_status") != "intake":
        report.error(package / "human-process.json", "intake_status must be intake")
    if intake.get("human_supplies") != ["source", "process"]:
        report.error(package / "human-process.json", 'human_supplies must equal ["source", "process"]')
    for key in ("package_id", "title", "external_input_note"):
        value = intake.get(key)
        if not isinstance(value, str) or not value.strip():
            report.error(package / "human-process.json", f"{key} must be a non-empty string")

    source_files = intake.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        report.error(package / "human-process.json", "source_files must be a non-empty list")
    else:
        if len(source_files) != len({value for value in source_files if isinstance(value, str)}):
            report.error(package / "human-process.json", "source_files contains duplicate entries")
        for value in source_files:
            if not isinstance(value, str):
                report.error(package / "human-process.json", "source_files entries must be strings")
                continue
            relative = normalized_relative(value)
            if relative is None or not relative.parts or relative.parts[0] != "source":
                report.error(package / "human-process.json", f"unsafe or non-source path: {value}")
            elif not (package / Path(*relative.parts)).is_file():
                report.error(package / Path(*relative.parts), "declared source file is missing")

    questions = intake.get("questions")
    if not isinstance(questions, list) or not questions:
        report.error(package / "human-process.json", "questions must be a non-empty list")
        return
    for question in questions:
        if not isinstance(question, str) or not QUESTION_RE.fullmatch(question):
            report.error(package / "human-process.json", f"invalid question id: {question!r}")
            continue
        question_dir = package / "process" / question
        if not question_dir.is_dir():
            report.error(question_dir, "declared question directory is missing")
        else:
            validate_question(question_dir, report)
    declared = {value for value in questions if isinstance(value, str)}
    process_dir = package / "process"
    if process_dir.is_dir():
        for child in process_dir.iterdir():
            if child.is_dir() and QUESTION_RE.fullmatch(child.name) and child.name not in declared:
                report.error(child, "question directory is not declared in human-process.json")


def git_changed_entries(repo: Path, base: str, report: Report) -> list[tuple[str, list[str]]]:
    if not base or set(base) == {"0"}:
        report.warn(repo, "git base is empty/all-zero; immutable-area diff check skipped")
        return []
    command = ["git", "-C", str(repo), "diff", "--name-status", "--find-renames", f"{base}...HEAD"]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        report.error(repo, f"cannot compare with git base {base}: {completed.stderr.strip()}")
        return []
    entries: list[tuple[str, list[str]]] = []
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            entries.append((parts[0], [value.replace("\\", "/") for value in parts[1:]]))
    return entries


def validate_git_immutability(repo: Path, base: str, report: Report) -> None:
    for status, paths in git_changed_entries(repo, base, report):
        status_code = status[0]
        for value in paths:
            parts = PurePosixPath(value).parts
            if len(parts) < 2 or not parts[0].startswith("training-"):
                continue
            joined = "/".join(parts)
            if "/final/" in f"/{joined}/" or value.endswith("/human-package.json"):
                report.error(value, "finalized artifacts are forbidden in this intake repository")
            if status_code in {"M", "D", "R", "C"} and "/source/" in f"/{joined}/":
                report.error(value, "existing official source material is immutable")
            if status_code in {"M", "D", "R", "C"} and "/process/legacy-package/" in f"/{joined}/":
                report.error(value, "legacy-package is an immutable snapshot")
            if status_code in {"M", "D", "R", "C"} and re.search(r"/runs/run-[^/]+/", f"/{joined}/"):
                report.error(value, "existing run records and artifacts are append-only")
            if status_code in {"M", "D", "R", "C"} and re.search(r"/process/q\d+/decisions/", f"/{joined}/"):
                report.error(value, "existing decision records are append-only; add a superseding decision")


def discover_packages(repo: Path, values: list[str], report: Report) -> list[Path]:
    if values:
        packages = []
        for value in values:
            path = Path(value)
            if not path.is_absolute():
                path = repo / path
            path = path.resolve()
            if not path.is_dir():
                report.error(path, "package directory does not exist")
            else:
                packages.append(path)
        return packages
    return sorted(path for path in repo.glob("training-*") if (path / "human-process.json").is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packages", nargs="*", help="package directories; default: every training-* package")
    parser.add_argument("--git-base", help="also enforce append-only/protected paths against this Git revision")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    report = Report()
    packages = discover_packages(repo, args.packages, report)
    if not packages and not report.errors:
        report.error(repo, "no process intake packages found")
    for package in packages:
        validate_package(package, report)
    if args.git_base:
        validate_git_immutability(repo, args.git_base, report)

    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")
    print(
        f"Checked {report.packages} package(s), {report.routes} route(s), "
        f"and {report.runs} run(s): {len(report.errors)} error(s), "
        f"{len(report.warnings)} warning(s)."
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
