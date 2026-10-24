"""End-to-end tests for the fast profile (DS101-DS103) over composed text assets from ``tests/assets``."""

from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.config import Config
from docsentinel.engine import ANALYZERS, scan
from docsentinel.rules import rules_for_profile
from tests.asset_helpers import AssetCase


@pytest.fixture
def fast_profile_tree(asset_case: Callable[[str, str], AssetCase]) -> tuple[Path, Path]:
    """Compose a markdown corpus from per-rule assets that triggers each fast-profile rule once."""
    dangling = asset_case("ds101", "dangling_link_file")
    asset_case("ds102", "stray_comment_file")
    asset_case("ds103", "unresolvable_path_file")
    clean = asset_case("ds101", "clean_document")
    return dangling.root, clean.path("clean.md")


def test_importing_engine_registers_all_fast_analyzers():
    """
    [Integration] fast profile end to end ds101 ds102 ds103: verifies importing engine registers all fast analyzers.

    Scenario:
        Given test inputs and fixtures for importing engine registers all fast analyzers
        When test_importing_engine_registers_all_fast_analyzers executes the target flow
        Then the expected outcome for importing engine registers all fast analyzers is confirmed.

    Boundaries:
        - Focus: importing engine registers all fast analyzers
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to importing engine registers all fast analyzers
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by fast profile end to end ds101 ds102 ds103
    """
    assert tuple(code for code in sorted(ANALYZERS) if code.startswith("DS1")) == (
        "DS101",
        "DS102",
        "DS103",
        "DS104",
        "DS105",
        "DS106",
        "DS108",
        "DS109",
        "DS110",
        "DS112",
        "DS113",
        "DS114",
        "DS115",
        "DS116",
        "DS117",
        "DS118",
    )
    assert tuple(rule.code for rule in rules_for_profile("fast")) == (
        "DS101",
        "DS102",
        "DS103",
        "DS104",
        "DS105",
        "DS106",
        "DS108",
        "DS109",
        "DS110",
        "DS112",
        "DS113",
        "DS114",
        "DS115",
        "DS116",
        "DS117",
        "DS118",
    )


def test_default_fast_scan_reports_all_three_rule_findings(
    fast_profile_tree: tuple[Path, Path],
):
    """
    [Integration] fast profile end to end ds101 ds102 ds103: verifies default fast scan reports all three rule findings.

    Scenario:
        Given test inputs and fixtures for default fast scan reports all three rule findings
        When test_default_fast_scan_reports_all_three_rule_findings executes the target flow
        Then the expected outcome for default fast scan reports all three rule findings is confirmed.

    Boundaries:
        - Focus: default fast scan reports all three rule findings
        - Fixtures/params: fast_profile_tree
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to default fast scan reports all three rule findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by fast profile end to end ds101 ds102 ds103
    """
    root, _ = fast_profile_tree

    result = scan(root)

    assert tuple((finding.rule, finding.path) for finding in result.findings) == (
        ("DS101", "dangling.md"),
        ("DS102", "comment.md"),
        ("DS103", "path.md"),
    )


def test_clean_tree_reports_zero_findings_with_evaluated_notice(
    fast_profile_tree: tuple[Path, Path],
):
    """
    [Integration] fast profile end to end ds101 ds102 ds103: verifies clean tree reports zero findings with evaluated notice.

    Scenario:
        Given test inputs and fixtures for clean tree reports zero findings with evaluated notice
        When test_clean_tree_reports_zero_findings_with_evaluated_notice executes the target flow
        Then the expected outcome for clean tree reports zero findings with evaluated notice is confirmed.

    Boundaries:
        - Focus: clean tree reports zero findings with evaluated notice
        - Fixtures/params: fast_profile_tree
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to clean tree reports zero findings with evaluated notice
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by fast profile end to end ds101 ds102 ds103
    """
    _, clean_file = fast_profile_tree

    result = scan(clean_file)

    assert result.findings == ()
    assert (
        result.notice
        == "12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS110 (set require_fence_languages), DS112 (set navigation_indexes), DS115 (set deprecated_references_file), DS118 (set documentation_naming)."
    )
    assert "not implemented" not in result.notice
    assert result.enabled_rules == (
        "DS101",
        "DS102",
        "DS103",
        "DS104",
        "DS105",
        "DS106",
        "DS108",
        "DS109",
        "DS110",
        "DS112",
        "DS113",
        "DS114",
        "DS115",
        "DS116",
        "DS117",
        "DS118",
    )


def test_ignore_narrows_the_active_set(fast_profile_tree: tuple[Path, Path]):
    """
    [Integration] fast profile end to end ds101 ds102 ds103: verifies ignore narrows the active set.

    Scenario:
        Given test inputs and fixtures for ignore narrows the active set
        When test_ignore_narrows_the_active_set executes the target flow
        Then the expected outcome for ignore narrows the active set is confirmed.

    Boundaries:
        - Focus: ignore narrows the active set
        - Fixtures/params: fast_profile_tree
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ignore narrows the active set
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by fast profile end to end ds101 ds102 ds103
    """
    root, _ = fast_profile_tree

    result = scan(root, config=Config(ignore=("DS102",)))

    assert tuple((finding.rule, finding.path) for finding in result.findings) == (
        ("DS101", "dangling.md"),
        ("DS103", "path.md"),
    )
    assert result.enabled_rules == (
        "DS101",
        "DS103",
        "DS104",
        "DS105",
        "DS106",
        "DS108",
        "DS109",
        "DS110",
        "DS112",
        "DS113",
        "DS114",
        "DS115",
        "DS116",
        "DS117",
        "DS118",
    )


def test_deep_profile_still_reports_pending(
    fast_profile_tree: tuple[Path, Path],
):
    """
    [Integration] fast profile end to end ds101 ds102 ds103: verifies deep profile still reports pending.

    Scenario:
        Given test inputs and fixtures for deep profile still reports pending
        When test_deep_profile_still_reports_pending executes the target flow
        Then the expected outcome for deep profile still reports pending is confirmed.

    Boundaries:
        - Focus: deep profile still reports pending
        - Fixtures/params: fast_profile_tree
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to deep profile still reports pending
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by fast profile end to end ds101 ds102 ds103
    """
    root, _ = fast_profile_tree

    result = scan(root, config=Config(profile="deep"))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile requires explicit opt-in" in result.pending[0]
    assert "explicit opt-in" in result.notice


def test_cli_scan_exit_code_reflects_real_findings(
    fast_profile_tree: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] fast profile end to end ds101 ds102 ds103: verifies cli scan exit code reflects real findings.

    Scenario:
        Given test inputs and fixtures for cli scan exit code reflects real findings
        When test_cli_scan_exit_code_reflects_real_findings executes the target flow
        Then the expected outcome for cli scan exit code reflects real findings is confirmed.

    Boundaries:
        - Focus: cli scan exit code reflects real findings
        - Fixtures/params: fast_profile_tree, capsys
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli scan exit code reflects real findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by fast profile end to end ds101 ds102 ds103
    """
    root, clean_file = fast_profile_tree

    assert cli.main(["scan", str(root)]) == 1
    capsys.readouterr()
    assert cli.main(["scan", str(clean_file)]) == 0
