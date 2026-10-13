"""Pytest lint gate for Flakeforge X-rules."""

from __future__ import annotations

from pathlib import Path

from flakeforge.config import load_config
from flakeforge.testing import assert_lint_clean

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_project_lint_reports_x_rule_violations_without_baseline():
    """
    [Integration] flakeforge lint: verifies project lint gate reports X-rule violations without baseline.

    Scenario:
        Given the project contains flakeforge X-rule checks
        When pytest executes this lint gate
        Then violations are reported directly instead of being hidden by baseline suppression.

    Boundaries:
        - Focus: enforce project-wide X-rule visibility during pytest runs
        - Fixtures/params: none
        - Scope: lints src/tests/scripts using configured rules, with baseline disabled

    On failure, first check:
        - The reported X-rule locations and messages
        - Whether violations are pre-existing debt that still needs cleanup
        - pyproject.toml [tool.flakeforge] configuration
    """
    config = load_config(cwd=REPO_ROOT).merge(baseline="")
    assert_lint_clean(
        REPO_ROOT / "src",
        REPO_ROOT / "tests",
        REPO_ROOT / "scripts",
        config=config,
    )
