#!/usr/bin/env python3
"""Validate a Skill-generated CUMCM final package and optional human approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema


REQUIRED_COMMON = {
    "final/README.md",
    "final/common/assumptions.md",
    "final/common/notation.md",
    "final/common/dependency-map.md",
    "final/common/decision-log.md",
}
SOLUTION_HEADINGS = (
    "## 1 题目要求", "## 2 直接答案", "## 3 与其他问题的关系",
    "## 4 数据与输入", "## 5 假设", "## 6 变量与符号",
    "## 7 模型选择及理由", "## 8 模型建立与公式", "## 9 求解过程",
    "## 10 最终结果", "## 11 图表与论文位置", "## 12 验证",
    "## 13 局限", "## 14 写作禁区",
)
PLACEHOLDER_RE = re.compile(r"\[REQUIRED(?::[^]]*)?\]|\bTODO\b|待填写|待补充", re.I)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def final_tree_sha256(root: Path) -> str:
    """Hash sorted final paths and file bytes, making renames and edits detectable."""
    digest = hashlib.sha256()
    final = root / "final"
    if not final.is_dir():
        return digest.hexdigest()
    for path in sorted((p for p in final.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_file(root: Path, value: str, label: str, errors: list[str]) -> Path | None:
    path = (root / Path(value)).resolve()
    if not path.is_relative_to(root.resolve()):
        errors.append(f"{label} escapes package root: {value}")
        return None
    if not path.is_file():
        errors.append(f"{label} does not exist: {value}")
        return None
    if path.stat().st_size == 0:
        errors.append(f"{label} is empty: {value}")
        return None
    return path


def check_solution(path: Path, question_id: str, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if PLACEHOLDER_RE.search(text):
        errors.append(f"{question_id} solution contains a placeholder: {path.name}")
    positions: list[int] = []
    for heading in SOLUTION_HEADINGS:
        matches = list(re.finditer(rf"(?m)^{re.escape(heading)}\s*$", text))
        if len(matches) != 1:
            errors.append(f"{question_id} solution must contain heading exactly once: {heading}")
            continue
        positions.append(matches[0].start())
    if len(positions) != len(SOLUTION_HEADINGS):
        return
    if positions != sorted(positions):
        errors.append(f"{question_id} solution headings are out of order")
        return
    for index, heading in enumerate(SOLUTION_HEADINGS):
        start = positions[index] + len(heading)
        end = positions[index + 1] if index + 1 < len(positions) else len(text)
        if not text[start:end].strip():
            errors.append(f"{question_id} solution section is empty: {heading}")


def check_provenance(root: Path, entries: list[dict[str, Any]], expected: set[str], label: str, errors: list[str]) -> None:
    mapped: list[str] = []
    for entry in entries:
        mapped.append(entry["final_artifact"])
        for source in entry["process_sources"]:
            resolve_file(root, source, f"{label} provenance source", errors)
    if len(mapped) != len(set(mapped)):
        errors.append(f"{label} provenance contains duplicate final_artifact entries")
    missing = sorted(expected - set(mapped))
    extra = sorted(set(mapped) - expected)
    for value in missing:
        errors.append(f"missing {label} provenance for final artifact: {value}")
    for value in extra:
        errors.append(f"{label} provenance names undeclared final artifact: {value}")


def staging_errors(root: Path) -> list[str]:
    errors: list[str] = []
    staging = root / "process" / "_staging"
    if not staging.is_dir():
        return ["missing required directory: process/_staging/"]
    allowed = {"README.md", "classification-log.md"}
    for name in sorted(allowed):
        if not (staging / name).is_file():
            errors.append(f"missing required staging control file: process/_staging/{name}")
    for path in sorted(candidate for candidate in staging.rglob("*") if candidate.is_file()):
        relative = path.relative_to(staging).as_posix()
        if relative not in allowed:
            errors.append(f"unclassified file remains in process/_staging/: process/_staging/{relative}")
    return errors


def semantic_errors(root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for required in ("README.md", "PROCESS_GUIDE.md", "process/README.md", "process/common/README.md", "human-process.json"):
        resolve_file(root, required, "required package file", errors)
    required_dirs = [
        "source", "source/problem", "source/attachments", "source/external",
        "process", "process/common", "process/common/notes", "process/common/data",
        "process/common/code", "process/common/results", "process/common/figures", "final",
    ]
    for required_dir in required_dirs:
        if not (root / required_dir).is_dir():
            errors.append(f"missing required directory: {required_dir}/")
    errors.extend(staging_errors(root))
    intake_path = root / "human-process.json"
    if intake_path.is_file():
        try:
            intake = load_json(intake_path)
            intake_schema = load_json(Path(__file__).resolve().parents[1] / "schemas" / "human-process.schema.json")
            jsonschema.Draft202012Validator(intake_schema).validate(intake)
            if intake["package_id"] != manifest["package_id"]:
                errors.append("human-process.json package_id does not match generated manifest")
            if intake["questions"] != [question["id"] for question in manifest["questions"]]:
                errors.append("human-process.json questions do not match generated manifest")
            if intake["source_files"] != manifest["source_files"]:
                errors.append("human-process.json source_files do not match generated manifest")
        except (OSError, UnicodeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
            errors.append(f"invalid human-process.json: {exc}")

    if manifest["finalization_status"] == "ready_for_review" and manifest["unresolved_decisions"]:
        errors.append("ready_for_review package must have no unresolved_decisions")
    if manifest["finalization_status"] == "needs_decision" and not manifest["unresolved_decisions"]:
        errors.append("needs_decision package must list unresolved_decisions")

    common = set(manifest["common_files"])
    if not REQUIRED_COMMON.issubset(common):
        errors.append("common_files must include final README, assumptions, notation, dependency map, and decision log")
    referenced_final = set(common)
    for value in common:
        path = resolve_file(root, value, "common file", errors)
        if path and path.suffix.lower() in {".md", ".txt"} and PLACEHOLDER_RE.search(path.read_text(encoding="utf-8-sig")):
            errors.append(f"common file contains a placeholder: {value}")
    check_provenance(root, manifest["common_provenance"], common, "common", errors)
    decision_log_path = root / "final" / "common" / "decision-log.md"
    decision_log_text = decision_log_path.read_text(encoding="utf-8-sig") if decision_log_path.is_file() else ""

    source_files = set(manifest["source_files"])
    if not source_files and not manifest["external_input_note"].strip():
        errors.append("package without source_files must explain external_input_note")
    for value in source_files:
        resolve_file(root, value, "source file", errors)

    seen_questions: set[str] = set()
    any_unresolved_route = False
    for question in manifest["questions"]:
        question_id = question["id"]
        if question_id in seen_questions:
            errors.append(f"duplicate question id: {question_id}")
        seen_questions.add(question_id)
        resolve_file(root, f"process/{question_id}/README.md", f"{question_id} process index", errors)
        for role in ("inbox", "routes", "comparisons", "decisions"):
            process_dir = root / "process" / question_id / role
            if not process_dir.is_dir():
                errors.append(f"missing required process directory: process/{question_id}/{role}/")
        routes_root = root / "process" / question_id / "routes"
        if routes_root.is_dir():
            for route_dir in sorted(routes_root.iterdir()):
                if route_dir.name.startswith("."):
                    continue
                relative_route = route_dir.relative_to(root).as_posix()
                if not route_dir.is_dir():
                    errors.append(f"route entry must be a directory: {relative_route}")
                    continue
                if not re.fullmatch(r"r[0-9]{2}-[a-z0-9]+(?:-[a-z0-9]+)*", route_dir.name):
                    errors.append(f"invalid route directory name: {relative_route}")
                resolve_file(root, f"{relative_route}/route.md", f"{question_id} route description", errors)
                runs_root = route_dir / "runs"
                if runs_root.is_dir():
                    for run_dir in sorted(runs_root.iterdir()):
                        if run_dir.name.startswith("."):
                            continue
                        relative_run = run_dir.relative_to(root).as_posix()
                        if not run_dir.is_dir():
                            errors.append(f"run entry must be a directory: {relative_run}")
                            continue
                        if not re.fullmatch(r"run-[0-9]{8}-[0-9]{4}-[a-z0-9]+(?:-[a-z0-9]+)*", run_dir.name):
                            errors.append(f"invalid run directory name: {relative_run}")
                        resolve_file(root, f"{relative_run}/run.md", f"{question_id} run record", errors)
        expected_solution = f"final/{question_id}/solution.md"
        if question["solution"] != expected_solution:
            errors.append(f"{question_id} solution must be {expected_solution}")
        for source in question["source_inputs"]:
            if source not in source_files and not source.startswith("external:"):
                errors.append(f"{question_id} source input must name source_files or use external:: {source}")
        if bool(question["final_code"]) == bool(question["no_code_reason"].strip()):
            errors.append(f"{question_id} must provide final_code or no_code_reason, but not both")
        if bool(question["final_results"]) == bool(question["no_machine_results_reason"].strip()):
            errors.append(f"{question_id} must provide final_results or no_machine_results_reason, but not both")

        validation = question["validation"]
        status, artifacts, gap = validation["status"], validation["artifacts"], validation["gap_reason"].strip()
        if status == "verified" and (not artifacts or gap):
            errors.append(f"{question_id} verified validation requires artifacts and no gap_reason")
        if status in {"partial", "conflict"} and (not artifacts or not gap):
            errors.append(f"{question_id} {status} validation requires artifacts and gap_reason")
        if status == "unverified" and not gap:
            errors.append(f"{question_id} unverified validation requires gap_reason")

        role_paths = [question["solution"], *question["final_code"], *question["final_results"], *question["final_figures"], *artifacts]
        expected = set(role_paths)
        check_provenance(root, question["provenance"], expected, question_id, errors)
        prefix = f"final/{question_id}/"
        for value in role_paths:
            if not value.startswith(prefix):
                errors.append(f"{question_id} artifact must stay under {prefix}: {value}")
            referenced_final.add(value)
            path = resolve_file(root, value, f"{question_id} final artifact", errors)
            if path and value == question["solution"]:
                check_solution(path, question_id, errors)
        for category, routes in question["route_decisions"].items():
            any_unresolved_route = any_unresolved_route or (category == "unresolved" and bool(routes))
            for route in routes:
                resolve_file(root, route["artifact"], f"{question_id} {category} route", errors)
                if route["artifact"] not in decision_log_text:
                    errors.append(f"{question_id} {category} route is missing from decision-log.md: {route['artifact']}")
                if category in {"rejected", "superseded"}:
                    solution_path = root / question["solution"]
                    solution_text = solution_path.read_text(encoding="utf-8-sig") if solution_path.is_file() else ""
                    ban_heading = "## 14 写作禁区"
                    ban_text = solution_text.split(ban_heading, 1)[1] if ban_heading in solution_text else ""
                    if route["artifact"] not in ban_text:
                        errors.append(f"{question_id} {category} route is missing from solution writing-ban section: {route['artifact']}")
        if not question["route_decisions"]["rejected"] and not question["route_decisions"]["superseded"]:
            # Empty is legal: some clean processes genuinely have one route.
            pass

    if any_unresolved_route and manifest["finalization_status"] != "needs_decision":
        errors.append("unresolved routes require finalization_status=needs_decision")
    actual_final = {p.relative_to(root).as_posix() for p in (root / "final").rglob("*") if p.is_file()} if (root / "final").is_dir() else set()
    for value in sorted(actual_final - referenced_final):
        errors.append(f"unreferenced file in final/: {value}")
    for value in sorted(referenced_final - actual_final):
        errors.append(f"manifest references missing final file: {value}")
    return errors


def approval_errors(root: Path, manifest: dict[str, Any], schema_path: Path) -> list[str]:
    errors: list[str] = []
    approval_path = root / "approval.json"
    if not approval_path.is_file():
        return ["approval.json is required for paper writing"]
    try:
        approval = load_json(approval_path)
        jsonschema.Draft202012Validator(load_json(schema_path), format_checker=jsonschema.FormatChecker()).validate(approval)
    except (OSError, UnicodeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        return [f"invalid approval.json: {exc}"]
    if manifest["finalization_status"] != "ready_for_review":
        errors.append("only ready_for_review packages can be approved for writing")
    if approval["package_id"] != manifest["package_id"]:
        errors.append("approval package_id does not match manifest")
    if approval["status"] != "approved":
        errors.append(f"approval status is not approved: {approval['status']}")
    actual_manifest_hash = sha256_file(root / "human-package.json")
    actual_tree_hash = final_tree_sha256(root)
    if approval["manifest_sha256"] != actual_manifest_hash:
        errors.append("approval is stale: human-package.json hash changed after review")
    if approval["final_tree_sha256"] != actual_tree_hash:
        errors.append("approval is stale: final/ tree changed after review")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--require-approved", action="store_true", help="Require a current human approval for paper writing")
    base = Path(__file__).resolve().parents[1] / "schemas"
    parser.add_argument("--schema", type=Path, default=base / "human-package.schema.json")
    parser.add_argument("--approval-schema", type=Path, default=base / "human-package-approval.schema.json")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {root}")
    manifest_path = root / "human-package.json"
    if not manifest_path.is_file():
        if (root / "human-process.json").is_file():
            errors = staging_errors(root)
            for error in errors:
                print(f"ERROR: {error}")
            if errors:
                print(f"Intake package not ready for finalization: {len(errors)} error(s)")
                return 1
            print("INTAKE: process materials have not been finalized by the Skill")
        else:
            print("LEGACY: missing human-process.json and human-package.json")
        return 2
    try:
        manifest = load_json(manifest_path)
        jsonschema.Draft202012Validator(load_json(args.schema)).validate(manifest)
        errors = semantic_errors(root, manifest)
    except (OSError, UnicodeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.require_approved and not errors:
        errors.extend(approval_errors(root, manifest, args.approval_schema))
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"Human package invalid: {len(errors)} error(s)")
        return 1
    suffix = ", approval=current" if args.require_approved else ", approval=not-required"
    print(f"Human package valid: id={manifest['package_id']}, status={manifest['finalization_status']}, final_files={sum(1 for p in (root / 'final').rglob('*') if p.is_file())}{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
