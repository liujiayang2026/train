"""Question 2 complete pricing script.

This is the single entry point for Question 2. It runs the complete pipeline:
1. fit the monotone Logistic completion model;
2. output baseline and improved pricing tables;
3. run budget/price-change scenarios;
4. solve greedy, exact MILP, and practical MILP pricing models.

The implementation reuses the maintained Question 2 helper modules so all
variables and output paths stay consistent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

QUESTION_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = QUESTION_DIR.parent
SHARED_PACKAGES = PROJECT_DIR / "shared" / "python-packages"
if SHARED_PACKAGES.exists():
    sys.path.insert(0, str(SHARED_PACKAGES))

CODE_DIR = QUESTION_DIR / "code"
DOCS_DIR = QUESTION_DIR / "docs"
FIGURES_DIR = QUESTION_DIR / "figures"
RESULTS_DIR = QUESTION_DIR / "results"


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    for directory in (DOCS_DIR, FIGURES_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    baseline = load_module("question2_baseline_pricing", CODE_DIR / "baseline-pricing.py")
    scenario = load_module("question2_scenario_analysis", CODE_DIR / "scenario-analysis.py")
    milp = load_module("question2_milp_pricing", CODE_DIR / "milp-pricing.py")

    print("Running Question 2 baseline and improved pricing...")
    baseline.main()
    print("Running Question 2 scenario analysis...")
    scenario.main()
    print("Running Question 2 exact/practical MILP pricing...")
    milp.main()
    print("Question 2 complete.")
    print(f"Outputs: {RESULTS_DIR}, {FIGURES_DIR}, {DOCS_DIR}")


if __name__ == "__main__":
    main()
