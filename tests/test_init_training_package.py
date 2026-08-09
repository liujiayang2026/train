from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INIT = REPO_ROOT / "scripts" / "init_training_package.py"
VALIDATE = REPO_ROOT / "scripts" / "validate_process_intake.py"
GUIDE = REPO_ROOT / "templates" / "PROCESS_GUIDE.md"


class TrainingPackageInitializerTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def create_package(self, root: Path) -> Path:
        package = root / "training-99-example"
        result = self.run_script(
            INIT,
            str(package),
            "--title",
            "Example problem",
            "--questions",
            "q1",
            "q2",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return package

    def test_initializer_creates_train_owned_staging_skeleton(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.create_package(Path(temporary))
            required_dirs = (
                "source/problem",
                "source/attachments",
                "source/external",
                "process/_staging",
                "process/common/notes",
                "process/common/data",
                "process/common/code",
                "process/common/results",
                "process/common/figures",
                "process/q1/inbox",
                "process/q1/routes",
                "process/q1/comparisons",
                "process/q1/decisions",
                "process/q2/inbox",
                "process/q2/routes",
                "process/q2/comparisons",
                "process/q2/decisions",
            )
            for relative in required_dirs:
                self.assertTrue((package / relative).is_dir(), relative)
            self.assertTrue((package / "process/_staging/README.md").is_file())
            self.assertTrue((package / "process/_staging/classification-log.md").is_file())
            self.assertFalse((package / "final").exists())
            self.assertEqual(
                (package / "PROCESS_GUIDE.md").read_bytes(),
                GUIDE.read_bytes(),
            )
            manifest = json.loads((package / "human-process.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["package_id"], "training-99-example")
        self.assertEqual(manifest["questions"], ["q1", "q2"])
        self.assertEqual(manifest["source_files"], [])

    def test_generated_package_passes_strict_validation_after_source_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.create_package(Path(temporary))
            problem = package / "source" / "problem" / "problem.md"
            problem.write_text("# Problem\n", encoding="utf-8")
            manifest_path = package / "human-process.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_files"] = ["source/problem/problem.md"]
            manifest["external_input_note"] = "All required official input is in source/."
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result = self.run_script(
                VALIDATE,
                str(package),
                "--ready-for-finalization",
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 error(s), 0 warning(s)", result.stdout)

    def test_initializer_refuses_duplicate_questions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "training-99-example"
            result = self.run_script(
                INIT,
                str(package),
                "--title",
                "Example problem",
                "--questions",
                "q1",
                "q1",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unique identifiers", result.stderr)

    def test_initializer_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = self.create_package(root)
            result = self.run_script(
                INIT,
                str(package),
                "--title",
                "Replacement",
                "--questions",
                "q1",
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to overwrite", result.stderr)


if __name__ == "__main__":
    unittest.main()
