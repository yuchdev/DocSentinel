from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.config import Config
from docsentinel.engine import ANALYZERS, scan
from docsentinel.rules import rules_for_profile


@pytest.fixture
def fast_profile_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Create a small markdown corpus that triggers each fast-profile rule once."""
    (tmp_path / "dangling.md").write_text("[missing](missing.md)\n", encoding="utf-8")
    (tmp_path / "comment.md").write_text("<!-- stray -->\n", encoding="utf-8")
    (tmp_path / "path.md").write_text("See `nonexistent/path.py`.\n", encoding="utf-8")
    clean_file = tmp_path / "clean.md"
    clean_file.write_text("# Clean\n\nNo structural issues.\n", encoding="utf-8")
    return tmp_path, clean_file


def test_importing_engine_registers_all_fast_analyzers():
    """
    [Integration] fast profile end to end: verifies importing engine registers all fast analyzers.

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
        - Recent changes in code paths exercised by fast profile end to end
    """
    assert tuple(code for code in sorted(ANALYZERS) if code.startswith("DS1")) == ("DS101", "DS102", "DS103")
    assert tuple(rule.code for rule in rules_for_profile("fast")) == ("DS101", "DS102", "DS103")


def test_default_fast_scan_reports_all_three_rule_findings(
    fast_profile_tree: tuple[Path, Path],
):
    """
    [Integration] fast profile end to end: verifies default fast scan reports all three rule findings.

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
        - Recent changes in code paths exercised by fast profile end to end
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
    [Integration] fast profile end to end: verifies clean tree reports zero findings with evaluated notice.

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
        - Recent changes in code paths exercised by fast profile end to end
    """
    _, clean_file = fast_profile_tree

    result = scan(clean_file)

    assert result.findings == ()
    assert result.notice == "3 fast rule(s) evaluated."
    assert "not implemented" not in result.notice
    assert result.enabled_rules == ("DS101", "DS102", "DS103")


def test_ignore_narrows_the_active_set(fast_profile_tree: tuple[Path, Path]):
    """
    [Integration] fast profile end to end: verifies ignore narrows the active set.

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
        - Recent changes in code paths exercised by fast profile end to end
    """
    root, _ = fast_profile_tree

    result = scan(root, config=Config(ignore=("DS102",)))

    assert tuple((finding.rule, finding.path) for finding in result.findings) == (
        ("DS101", "dangling.md"),
        ("DS103", "path.md"),
    )
    assert result.enabled_rules == ("DS101", "DS103")


def test_deep_profile_still_reports_pending(
    fast_profile_tree: tuple[Path, Path],
):
    """
    [Integration] fast profile end to end: verifies deep profile still reports pending.

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
        - Recent changes in code paths exercised by fast profile end to end
    """
    root, _ = fast_profile_tree

    result = scan(root, config=Config(profile="deep"))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile requires explicit opt-in" in result.pending[0]
    assert "not implemented" in result.notice


def test_cli_scan_exit_code_reflects_real_findings(
    fast_profile_tree: tuple[Path, Path],
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] fast profile end to end: verifies cli scan exit code reflects real findings.

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
        - Recent changes in code paths exercised by fast profile end to end
    """
    root, clean_file = fast_profile_tree

    assert cli.main(["scan", str(root)]) == 1
    capsys.readouterr()
    assert cli.main(["scan", str(clean_file)]) == 0
