#!/usr/bin/env python3
"""Create a hash-bound pending, approved, or rejected human review record."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

from validate_human_package import final_tree_sha256, load_json, semantic_errors, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--pending", action="store_true", help="Skill records that generated final awaits human review")
    action.add_argument("--approve", action="store_true", help="Human accepts the generated final for paper writing")
    action.add_argument("--reject", action="store_true", help="Human rejects the generated final")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--note", default="")
    base = Path(__file__).resolve().parents[1] / "schemas"
    parser.add_argument("--schema", type=Path, default=base / "human-package.schema.json")
    args = parser.parse_args()

    root = args.root.resolve()
    manifest_path = root / "human-package.json"
    if not manifest_path.is_file():
        parser.error(f"missing generated manifest: {manifest_path}")
    try:
        manifest = load_json(manifest_path)
        jsonschema.Draft202012Validator(load_json(args.schema)).validate(manifest)
        errors = semantic_errors(root, manifest)
    except (OSError, UnicodeError, json.JSONDecodeError, jsonschema.ValidationError) as exc:
        print(f"ERROR: generated final is invalid: {exc}")
        return 1
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("Refusing to record review for an invalid generated final")
        return 1

    status = "approved" if args.approve else "rejected" if args.reject else "pending"
    if status == "approved" and manifest["finalization_status"] != "ready_for_review":
        print("ERROR: unresolved decisions block approval")
        return 1
    if status in {"approved", "rejected"} and not args.reviewer.strip():
        print("ERROR: --reviewer is required for a human review decision")
        return 1
    if status == "rejected" and not args.note.strip():
        print("ERROR: --note is required when rejecting a package")
        return 1

    record = {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "status": status,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": args.reviewer.strip(),
        "review_note": args.note.strip(),
        "manifest_sha256": sha256_file(manifest_path),
        "final_tree_sha256": final_tree_sha256(root),
    }
    (root / "approval.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Recorded {status} review state for {manifest['package_id']}")
    if status == "pending":
        print("A human must review and explicitly approve before paper writing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
