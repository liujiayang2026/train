#!/usr/bin/env python3
"""Create a new process-only mathematical-modeling training package."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


PACKAGE_RE = re.compile(r"training-[0-9]{2,}-[a-z0-9]+(?:-[a-z0-9]+)*$")
QUESTION_RE = re.compile(r"q[1-9][0-9]*$")
COMMON_ROLES = ("notes", "data", "code", "results", "figures")
QUESTION_ROLES = ("inbox", "routes", "comparisons", "decisions")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--package-id", help="defaults to the destination directory name")
    parser.add_argument("--title", required=True)
    parser.add_argument("--questions", nargs="+", required=True)
    parser.add_argument(
        "--external-input-note",
        default="[REQUIRED: describe official inputs stored outside this package]",
    )
    args = parser.parse_args()

    args.package_id = args.package_id or args.destination.name
    if not PACKAGE_RE.fullmatch(args.package_id):
        parser.error("package id must look like training-06-short-name")
    if args.destination.name != args.package_id:
        parser.error("destination directory name must equal --package-id")
    if len(set(args.questions)) != len(args.questions) or any(
        not QUESTION_RE.fullmatch(question) for question in args.questions
    ):
        parser.error("--questions must be unique identifiers such as q1 q2")
    if not args.title.strip():
        parser.error("--title must not be empty")
    return args


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    args = parse_args()
    destination = args.destination.resolve()
    if destination.exists():
        raise SystemExit(f"refusing to overwrite existing path: {destination}")

    repo_root = Path(__file__).resolve().parents[1]
    guide = repo_root / "templates" / "PROCESS_GUIDE.md"
    if not guide.is_file():
        raise SystemExit(f"missing canonical process guide template: {guide}")

    destination.mkdir(parents=True)
    shutil.copyfile(guide, destination / "PROCESS_GUIDE.md")

    for role in ("problem", "attachments", "external"):
        (destination / "source" / role).mkdir(parents=True)
    for role in COMMON_ROLES:
        (destination / "process" / "common" / role).mkdir(parents=True)

    staging = destination / "process" / "_staging"
    staging.mkdir(parents=True)
    write_text(
        staging / "README.md",
        "# Process staging area\n\n"
        "Put loose files here only when their question, route, or source role is not yet known. "
        "If the question is known, use that question's `inbox/` instead.\n\n"
        "Before finalization, an intake-organizer Agent must inspect each file's contents, "
        "move it without editing into its proper location, and append the original path, "
        "destination, reason, date, and organizer to `classification-log.md`.\n\n"
        "Only this README and `classification-log.md` may remain at handoff.\n",
    )
    write_text(
        staging / "classification-log.md",
        "# Staging classification log\n\n"
        "Append one row for every classified move. Never rewrite an earlier row; "
        "record corrections as new moves.\n\n"
        "| Date | Original path | Destination path | Classification reason | Organizer |\n"
        "|---|---|---|---|---|\n",
    )

    for question_id in args.questions:
        question_root = destination / "process" / question_id
        for role in QUESTION_ROLES:
            (question_root / role).mkdir(parents=True)
        write_text(
            question_root / "README.md",
            f"# {question_id.upper()} process index\n\n"
            "- Question requirement:\n"
            "- Current candidate routes:\n"
            "- Known conflicts:\n"
            "- Explicit human decisions:\n\n"
            "Create one `routes/rNN-short-name/` directory per materially different route. "
            "Keep each route's model, code, runs, results, figures, validation, and logs together.\n",
        )

    write_text(
        destination / "README.md",
        "# Human modeling intake\n\n"
        "This package is created and maintained by the `train` repository. During modeling, "
        "Agents maintain only `source/` and `process/`; an independent train Finalizer creates "
        "`final/` and `human-package.json` after strict readiness.\n\n"
        "Read `PROCESS_GUIDE.md` before adding materials. Before handoff, classify every file "
        "in `process/_staging/` and run the readiness validator from the train repository.\n",
    )
    write_text(
        destination / "process" / "README.md",
        "# Process index\n\n"
        "This directory is noncanonical. Record the global timeline, question dependencies, "
        "competing routes, failed attempts, and unresolved conflicts here.\n\n"
        "- `_staging/`: loose materials whose question or source role is not yet known; an "
        "intake-organizer Agent must classify and log them before handoff.\n"
        "- `common/`: materials reused by two or more questions.\n"
        "- `qN/inbox/`: question-known imports whose route is not yet known.\n"
        "- `qN/routes/`: one self-contained directory per materially different solution route.\n"
        "- `qN/comparisons/`: explicit cross-route comparisons.\n"
        "- `qN/decisions/`: human decisions and reasons; never infer decisions from filenames.\n\n"
        "Nothing here may be used directly by the paper-writing Agent.\n",
    )
    write_text(
        destination / "process" / "common" / "README.md",
        "# Common process materials\n\n"
        "Place an artifact here only when it is genuinely shared by at least two questions. "
        "Question-specific materials belong inside that question's route directory.\n",
    )

    intake = {
        "schema_version": 3,
        "package_id": args.package_id,
        "title": args.title.strip(),
        "intake_status": "intake",
        "human_supplies": ["source", "process"],
        "questions": args.questions,
        "source_files": [],
        "external_input_note": args.external_input_note,
    }
    write_text(
        destination / "human-process.json",
        json.dumps(intake, ensure_ascii=False, indent=2) + "\n",
    )

    print(f"Created training package skeleton: {destination}")
    print("Next: add official source files and list them in human-process.json.")
    print(
        "Before handoff: python scripts/validate_process_intake.py "
        f"{args.package_id} --ready-for-finalization"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
