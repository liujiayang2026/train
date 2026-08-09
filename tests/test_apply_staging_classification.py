from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT = REPO_ROOT / "scripts" / "init_training_package.py"
APPLY = REPO_ROOT / "scripts" / "apply_staging_classification.py"
VALIDATE = REPO_ROOT / "scripts" / "validate_process_intake.py"


class StagingClassificationMoverTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def scaffold(self, root: Path) -> tuple[Path, Path]:
        package = root / "training-99-classification"
        created = self.run_script(
            INIT,
            str(package),
            "--title",
            "Classification fixture",
            "--questions",
            "q1",
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        staging = package / "process" / "_staging" / "import"
        (staging / "official").mkdir(parents=True)
        (staging / "official" / "problem.md").write_text("problem\n", encoding="utf-8")
        (staging / "q1").mkdir()
        (staging / "q1" / "notes.md").write_text("route uncertain\n", encoding="utf-8")
        plan = package / "process" / "common" / "notes" / "classification-plan.json"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "package_id": "training-99-classification",
                    "organizer": "test-agent",
                    "entries": [
                        {
                            "source": "process/_staging/import/official/problem.md",
                            "destination": "source/problem/problem.md",
                            "reason": "official problem statement",
                        },
                        {
                            "source_prefix": "process/_staging/import/q1",
                            "destination_prefix": "process/q1/inbox/imported",
                            "reason": "question is known but route is unresolved",
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return package, plan

    def test_dry_run_then_apply_updates_log_manifest_and_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, plan = self.scaffold(Path(temporary))
            dry_run = self.run_script(APPLY, str(package), str(plan))
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)
            self.assertTrue((package / "process/_staging/import/official/problem.md").is_file())

            applied = self.run_script(APPLY, str(package), str(plan), "--apply")
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
            self.assertTrue((package / "source/problem/problem.md").is_file())
            self.assertTrue((package / "process/q1/inbox/imported/notes.md").is_file())
            manifest = json.loads((package / "human-process.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_files"], ["source/problem/problem.md"])
            log = (package / "process/_staging/classification-log.md").read_text(encoding="utf-8")
            self.assertEqual(log.count("| test-agent |"), 2)
            strict = self.run_script(VALIDATE, str(package), "--ready-for-finalization")
        self.assertEqual(strict.returncode, 0, strict.stdout + strict.stderr)

    def test_incomplete_plan_is_rejected_without_moving(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, plan = self.scaffold(Path(temporary))
            value = json.loads(plan.read_text(encoding="utf-8"))
            value["entries"].pop()
            plan.write_text(json.dumps(value), encoding="utf-8")
            result = self.run_script(APPLY, str(package), str(plan), "--apply")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not exactly cover", result.stdout)
            self.assertTrue((package / "process/_staging/import/official/problem.md").is_file())
            self.assertTrue((package / "process/_staging/import/q1/notes.md").is_file())

    def test_unsafe_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package, plan = self.scaffold(Path(temporary))
            value = json.loads(plan.read_text(encoding="utf-8"))
            value["entries"][0]["destination"] = "final/problem.md"
            plan.write_text(json.dumps(value), encoding="utf-8")
            result = self.run_script(APPLY, str(package), str(plan), "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("destination is not allowed", result.stdout)


if __name__ == "__main__":
    unittest.main()
