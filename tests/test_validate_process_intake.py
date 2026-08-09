from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_process_intake.py"
SPEC = importlib.util.spec_from_file_location("validate_process_intake", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VALIDATOR
SPEC.loader.exec_module(VALIDATOR)


class StagingValidationTests(unittest.TestCase):
    def make_package(self, root: Path) -> Path:
        package = root / "training-example"
        staging = package / "process" / "_staging"
        staging.mkdir(parents=True)
        (staging / "README.md").write_text("# Staging\n", encoding="utf-8")
        (staging / "classification-log.md").write_text(
            "# Log\n\n| Date | Original | Destination | Reason | Organizer |\n",
            encoding="utf-8",
        )
        return package

    def test_clean_staging_passes_both_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.make_package(Path(temporary))
            for strict in (False, True):
                report = VALIDATOR.Report()
                VALIDATOR.validate_staging(package, report, strict)
                self.assertEqual(report.errors, [])
                self.assertEqual(report.warnings, [])

    def test_live_mode_warns_for_unclassified_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.make_package(Path(temporary))
            loose = package / "process" / "_staging" / "chat-export.md"
            loose.write_text("uncertain notes\n", encoding="utf-8")
            report = VALIDATOR.Report()
            VALIDATOR.validate_staging(package, report, False)
            self.assertEqual(report.errors, [])
            self.assertEqual(len(report.warnings), 1)
            self.assertIn("unclassified file remains", report.warnings[0])

    def test_finalization_mode_rejects_unclassified_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = self.make_package(Path(temporary))
            loose = package / "process" / "_staging" / "unknown" / "result.csv"
            loose.parent.mkdir()
            loose.write_text("value\n1\n", encoding="utf-8")
            report = VALIDATOR.Report()
            VALIDATOR.validate_staging(package, report, True)
            self.assertEqual(report.warnings, [])
            self.assertEqual(len(report.errors), 1)
            self.assertIn("unclassified file remains", report.errors[0])

    def test_staging_control_files_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "training-example"
            (package / "process" / "_staging").mkdir(parents=True)
            report = VALIDATOR.Report()
            VALIDATOR.validate_staging(package, report, False)
            self.assertEqual(len(report.errors), 2)


class ProcessGuideValidationTests(unittest.TestCase):
    def test_package_guide_must_match_canonical_template(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "training-example"
            package.mkdir()
            (package / "PROCESS_GUIDE.md").write_text("outdated guide\n", encoding="utf-8")
            report = VALIDATOR.Report()
            VALIDATOR.validate_process_guide(package, report)
            self.assertEqual(len(report.errors), 1)
            self.assertIn("does not match", report.errors[0])


if __name__ == "__main__":
    unittest.main()
