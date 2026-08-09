#!/usr/bin/env python3
"""Validate and apply an Agent-authored staging classification plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


CONTROL_FILES = {"README.md", "classification-log.md"}


def safe_relative(value: str, label: str) -> PurePosixPath:
    if not value or "\\" in value:
        raise ValueError(f"{label} must be a non-empty POSIX path: {value!r}")
    path = PurePosixPath(value)
    if not path.parts or path.is_absolute() or ".." in path.parts or "\x00" in value:
        raise ValueError(f"unsafe {label}: {value!r}")
    return path


def resolve_inside(root: Path, value: PurePosixPath) -> Path:
    path = root.joinpath(*value.parts)
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"path escapes package: {value.as_posix()}")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--apply", action="store_true", help="move files after a successful preflight")
    return parser.parse_args()


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def build_mapping(package: Path, plan: dict, questions: set[str]) -> list[dict[str, str]]:
    if plan.get("schema_version") != 1:
        raise ValueError("classification plan schema_version must be 1")
    organizer = plan.get("organizer")
    if not isinstance(organizer, str) or not organizer.strip():
        raise ValueError("classification plan organizer must be a non-empty string")
    entries = plan.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("classification plan entries must be a non-empty list")

    staging = package / "process" / "_staging"
    mapping: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"entries[{index}] must be an object")
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"entries[{index}].reason must be a non-empty string")
        has_file = "source" in entry or "destination" in entry
        has_prefix = "source_prefix" in entry or "destination_prefix" in entry
        if has_file == has_prefix:
            raise ValueError(
                f"entries[{index}] must define either source/destination or source_prefix/destination_prefix"
            )
        if has_file:
            if set(entry) != {"source", "destination", "reason"}:
                raise ValueError(f"entries[{index}] file mapping has unexpected or missing keys")
            source_rel = safe_relative(entry["source"], f"entries[{index}].source")
            destination_rel = safe_relative(entry["destination"], f"entries[{index}].destination")
            mapping.append({
                "source": source_rel.as_posix(),
                "destination": destination_rel.as_posix(),
                "reason": reason.strip(),
            })
        else:
            if set(entry) != {"source_prefix", "destination_prefix", "reason"}:
                raise ValueError(f"entries[{index}] prefix mapping has unexpected or missing keys")
            source_prefix = safe_relative(entry["source_prefix"], f"entries[{index}].source_prefix")
            destination_prefix = safe_relative(
                entry["destination_prefix"], f"entries[{index}].destination_prefix"
            )
            source_root = resolve_inside(package, source_prefix)
            if not source_root.is_dir() or not source_root.resolve().is_relative_to(staging):
                raise ValueError(f"source prefix is not a staging directory: {source_prefix.as_posix()}")
            files = sorted(path for path in source_root.rglob("*") if path.is_file())
            if not files:
                raise ValueError(f"source prefix contains no files: {source_prefix.as_posix()}")
            for source_path in files:
                relative_tail = source_path.relative_to(source_root)
                mapping.append({
                    "source": source_path.relative_to(package).as_posix(),
                    "destination": (destination_prefix / PurePosixPath(relative_tail.as_posix())).as_posix(),
                    "reason": reason.strip(),
                })

    actual = {
        path.relative_to(package).as_posix()
        for path in staging.rglob("*")
        if path.is_file() and path.relative_to(staging).as_posix() not in CONTROL_FILES
    }
    planned_sources = [item["source"] for item in mapping]
    if len(planned_sources) != len(set(planned_sources)):
        raise ValueError("classification plan maps at least one staging file more than once")
    missing = sorted(actual - set(planned_sources))
    extra = sorted(set(planned_sources) - actual)
    if missing or extra:
        details = []
        if missing:
            details.append("unplanned: " + ", ".join(missing[:10]))
        if extra:
            details.append("not in staging: " + ", ".join(extra[:10]))
        raise ValueError("classification plan does not exactly cover staging files (" + "; ".join(details) + ")")

    destinations = [item["destination"] for item in mapping]
    if len(destinations) != len(set(destinations)):
        raise ValueError("classification plan has duplicate destination paths")
    for item in mapping:
        source_rel = safe_relative(item["source"], "source")
        if source_rel.parts[:2] != ("process", "_staging"):
            raise ValueError(f"classification source is outside staging: {item['source']}")
        destination_rel = safe_relative(item["destination"], "destination")
        allowed = destination_rel.parts[0] == "source"
        if destination_rel.parts[0] == "process" and len(destination_rel.parts) >= 3:
            allowed = destination_rel.parts[1] == "common" or destination_rel.parts[1] in questions
        if not allowed or "_staging" in destination_rel.parts or "legacy-package" in destination_rel.parts:
            raise ValueError(f"classification destination is not allowed: {item['destination']}")
        source_path = resolve_inside(package, source_rel)
        destination_path = resolve_inside(package, destination_rel)
        if not source_path.is_file() or source_path.is_symlink():
            raise ValueError(f"classification source is not a regular file: {item['source']}")
        if destination_path.exists():
            raise ValueError(f"classification destination already exists: {item['destination']}")
    return mapping


def apply_mapping(package: Path, plan: dict, mapping: list[dict[str, str]]) -> None:
    manifest_path = package / "human-process.json"
    manifest = load_object(manifest_path)
    original_manifest = manifest_path.read_bytes()
    log_path = package / "process" / "_staging" / "classification-log.md"
    original_log = log_path.read_bytes()
    hashes = {
        item["source"]: sha256(resolve_inside(package, safe_relative(item["source"], "source")))
        for item in mapping
    }
    moved: list[tuple[Path, Path]] = []
    try:
        for item in mapping:
            source = resolve_inside(package, safe_relative(item["source"], "source"))
            destination = resolve_inside(package, safe_relative(item["destination"], "destination"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append((source, destination))
            if sha256(destination) != hashes[item["source"]]:
                raise RuntimeError(f"content hash changed while moving: {item['source']}")

        source_files = manifest.get("source_files")
        if not isinstance(source_files, list):
            raise ValueError("human-process.json source_files must be a list")
        additions = [item["destination"] for item in mapping if item["destination"].startswith("source/")]
        manifest["source_files"] = sorted(set(source_files).union(additions))
        temporary_manifest = manifest_path.with_suffix(".json.tmp")
        temporary_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary_manifest, manifest_path)

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = "".join(
            "| " + " | ".join(
                markdown_cell(value)
                for value in (
                    timestamp,
                    item["source"],
                    item["destination"],
                    item["reason"],
                    str(plan["organizer"]),
                )
            ) + " |\n"
            for item in mapping
        )
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(rows)

        staging = package / "process" / "_staging"
        for directory in sorted(
            (path for path in staging.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            if not any(directory.iterdir()):
                directory.rmdir()
    except Exception:
        manifest_path.write_bytes(original_manifest)
        log_path.write_bytes(original_log)
        for source, destination in reversed(moved):
            if destination.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(destination), str(source))
        raise


def main() -> int:
    args = parse_args()
    package = args.package.resolve()
    plan_path = args.plan.resolve()
    if not package.is_dir():
        raise SystemExit(f"package directory does not exist: {package}")
    try:
        manifest = load_object(package / "human-process.json")
        plan = load_object(plan_path)
        if plan.get("package_id") != manifest.get("package_id"):
            raise ValueError("classification plan package_id does not match human-process.json")
        questions = manifest.get("questions")
        if not isinstance(questions, list) or not all(isinstance(value, str) for value in questions):
            raise ValueError("human-process.json questions must be a string list")
        mapping = build_mapping(package, plan, set(questions))
        print(f"Classification plan valid: {len(mapping)} file(s), organizer={plan['organizer']}")
        if args.apply:
            apply_mapping(package, plan, mapping)
            print(f"Classification applied: {len(mapping)} file(s)")
        else:
            print("Dry run only; pass --apply to move files.")
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
