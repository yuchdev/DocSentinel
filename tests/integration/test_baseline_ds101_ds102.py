"""Integration tests for baseline suppression through ``scan`` and the CLI over assets in ``ds101``/``ds102``.

Findings used as baseline material come from DS101 (dangling link, error) and DS102 (stray comment, warning).
"""

from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, Finding, fingerprint, load_baseline, save_baseline, scan
from docsentinel.cli import main
from tests.asset_helpers import AssetCase


def test_scan_with_baseline_suppresses_matching_findings(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies scan with baseline suppresses matching findings.

    Scenario:
        Given test inputs and fixtures for scan with baseline suppresses matching findings
        When test_scan_with_baseline_suppresses_matching_findings executes the target flow
        Then the expected outcome for scan with baseline suppresses matching findings is confirmed.

    Boundaries:
        - Focus: scan with baseline suppresses matching findings
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with baseline suppresses matching findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")

    # Initial scan without baseline surfaces the finding
    raw_result = scan(case.root)
    assert len(raw_result.findings) == 1
    assert raw_result.findings[0].rule == "DS101"

    # Capture baseline
    baseline_file = case.path(".docsentinel-baseline.json")
    save_baseline(baseline_file, raw_result.findings)

    # Scan with baseline configured suppresses the finding
    baselined_result = scan(case.root, config=Config(baseline=".docsentinel-baseline.json"))
    assert len(baselined_result.findings) == 0


def test_scan_with_baseline_still_reports_new_findings(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies scan with baseline still reports new findings.

    Scenario:
        Given test inputs and fixtures for scan with baseline still reports new findings
        When test_scan_with_baseline_still_reports_new_findings executes the target flow
        Then the expected outcome for scan with baseline still reports new findings is confirmed.

    Boundaries:
        - Focus: scan with baseline still reports new findings
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with baseline still reports new findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")

    initial_result = scan(case.root)
    assert len(initial_result.findings) == 1

    baseline_file = case.path(".docsentinel-baseline.json")
    save_baseline(baseline_file, initial_result.findings)

    # Add a second document with a different issue
    asset_case("ds101", "second_dangling_link_file")

    new_result = scan(case.root, config=Config(baseline=".docsentinel-baseline.json"))
    assert len(new_result.findings) == 1
    assert new_result.findings[0].path == "second.md"


def test_scan_with_missing_baseline_file_does_not_fail(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies scan with missing baseline file does not fail.

    Scenario:
        Given test inputs and fixtures for scan with missing baseline file does not fail
        When test_scan_with_missing_baseline_file_does_not_fail executes the target flow
        Then the expected outcome for scan with missing baseline file does not fail is confirmed.

    Boundaries:
        - Focus: scan with missing baseline file does not fail
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with missing baseline file does not fail
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")

    result = scan(case.root, config=Config(baseline="nonexistent-baseline.json"))

    assert len(result.findings) == 1


def test_scan_with_corrupt_baseline_file_raises_config_error(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies scan with corrupt baseline file raises config error.

    Scenario:
        Given test inputs and fixtures for scan with corrupt baseline file raises config error
        When test_scan_with_corrupt_baseline_file_raises_config_error executes the target flow
        Then the expected outcome for scan with corrupt baseline file raises config error is confirmed.

    Boundaries:
        - Focus: scan with corrupt baseline file raises config error
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with corrupt baseline file raises config error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")
    case.path("bad-baseline.json").write_text("{bad", encoding="utf-8")

    with pytest.raises(ConfigError):
        scan(case.root, config=Config(baseline="bad-baseline.json"))


def test_cli_baseline_subcommand_writes_file(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies cli baseline subcommand writes file.

    Scenario:
        Given test inputs and fixtures for cli baseline subcommand writes file
        When test_cli_baseline_subcommand_writes_file executes the target flow
        Then the expected outcome for cli baseline subcommand writes file is confirmed.

    Boundaries:
        - Focus: cli baseline subcommand writes file
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline subcommand writes file
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")

    exit_code = main(["baseline", str(case.root)])
    assert exit_code == 0

    default_baseline = case.path(".docsentinel-baseline.json")
    assert default_baseline.exists()
    suppressed = load_baseline(default_baseline)
    assert len(suppressed) == 1


def test_cli_baseline_subcommand_with_output_flag(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies cli baseline subcommand with output flag.

    Scenario:
        Given test inputs and fixtures for cli baseline subcommand with output flag
        When test_cli_baseline_subcommand_with_output_flag executes the target flow
        Then the expected outcome for cli baseline subcommand with output flag is confirmed.

    Boundaries:
        - Focus: cli baseline subcommand with output flag
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline subcommand with output flag
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")
    custom_output = case.path("custom/base.json")

    exit_code = main(["baseline", str(case.root), "--output", str(custom_output)])

    assert exit_code == 0
    assert custom_output.exists()
    assert len(load_baseline(custom_output)) == 1


def test_cli_baseline_subcommand_honors_config_and_ignores(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies cli baseline subcommand honors config and ignores.

    Scenario:
        Given test inputs and fixtures for cli baseline subcommand honors config and ignores
        When test_cli_baseline_subcommand_honors_config_and_ignores executes the target flow
        Then the expected outcome for cli baseline subcommand honors config and ignores is confirmed.

    Boundaries:
        - Focus: cli baseline subcommand honors config and ignores
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline subcommand honors config and ignores
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")
    asset_case("ds102", "stray_comment_file")
    case.path("doc_sentinel.toml").write_text('ignore = ["DS101"]\nbaseline = "cfg-baseline.json"\n', encoding="utf-8")

    exit_code = main(["baseline", str(case.root)])
    assert exit_code == 0

    cfg_baseline = case.path("cfg-baseline.json")
    assert cfg_baseline.exists()
    suppressed = load_baseline(cfg_baseline)
    # DS101 is ignored by config, so only DS102 stray comment is captured
    assert len(suppressed) == 1
    assert any("DS102" in item for item in suppressed)


def test_cli_baseline_is_idempotent(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies cli baseline is idempotent.

    Scenario:
        Given test inputs and fixtures for cli baseline is idempotent
        When test_cli_baseline_is_idempotent executes the target flow
        Then the expected outcome for cli baseline is idempotent is confirmed.

    Boundaries:
        - Focus: cli baseline is idempotent
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline is idempotent
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")
    asset_case("ds102", "stray_comment_file")

    main(["baseline", str(case.root)])
    baseline_file = case.path(".docsentinel-baseline.json")
    first_run = baseline_file.read_bytes()

    main(["baseline", str(case.root)])
    second_run = baseline_file.read_bytes()

    assert first_run == second_run


def test_cli_scan_exit_code_zero_when_errors_are_baselined(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies cli scan exit code zero when errors are baselined.

    Scenario:
        Given test inputs and fixtures for cli scan exit code zero when errors are baselined
        When test_cli_scan_exit_code_zero_when_errors_are_baselined executes the target flow
        Then the expected outcome for cli scan exit code zero when errors are baselined is confirmed.

    Boundaries:
        - Focus: cli scan exit code zero when errors are baselined
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli scan exit code zero when errors are baselined
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")

    # Without baseline: fails with exit code 1
    assert main(["scan", str(case.root)]) == 1
    assert main(["scan", str(case.root), "--strict"]) == 1

    # Create baseline and config
    case.path("doc_sentinel.toml").write_text('baseline = ".docsentinel-baseline.json"\n', encoding="utf-8")
    main(["baseline", str(case.root)])

    # With baseline: succeeds with exit code 0 even under --strict
    assert main(["scan", str(case.root)]) == 0
    assert main(["scan", str(case.root), "--strict"]) == 0


def test_cli_scan_exit_code_with_new_findings_after_baseline(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] baseline ds101 ds102: verifies cli scan exit code with new findings after baseline.

    Scenario:
        Given test inputs and fixtures for cli scan exit code with new findings after baseline
        When test_cli_scan_exit_code_with_new_findings_after_baseline executes the target flow
        Then the expected outcome for cli scan exit code with new findings after baseline is confirmed.

    Boundaries:
        - Focus: cli scan exit code with new findings after baseline
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli scan exit code with new findings after baseline
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")
    case.path("doc_sentinel.toml").write_text('baseline = ".docsentinel-baseline.json"\n', encoding="utf-8")
    main(["baseline", str(case.root)])

    # Add a new warning (DS102)
    asset_case("ds102", "stray_comment_file")

    # In default mode, warning alone exits 0
    assert main(["scan", str(case.root)]) == 0
    # In strict mode, warning causes exit 1
    assert main(["scan", str(case.root), "--strict"]) == 1

    # Add a new error (DS101)
    asset_case("ds101", "second_dangling_link_file")

    # In default and strict modes, error causes exit 1
    assert main(["scan", str(case.root)]) == 1
    assert main(["scan", str(case.root), "--strict"]) == 1


def test_cli_baseline_failure_exits_two(tmp_path: Path):
    """
    [Integration] baseline ds101 ds102: verifies cli baseline failure exits two.

    Scenario:
        Given test inputs and fixtures for cli baseline failure exits two
        When test_cli_baseline_failure_exits_two executes the target flow
        Then the expected outcome for cli baseline failure exits two is confirmed.

    Boundaries:
        - Focus: cli baseline failure exits two
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline failure exits two
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    (tmp_path / "doc_sentinel.toml").write_text("invalid = toml[\n", encoding="utf-8")

    assert main(["baseline", str(tmp_path)]) == 2


def test_cli_baseline_profile_override_captures_requested_profile_and_preserves_config(
    asset_case: Callable[[str, str], AssetCase],
):
    """
    [Integration] baseline ds101 ds102: verifies cli baseline profile override captures requested profile and preserves config.

    Scenario:
        Given test inputs and fixtures for cli baseline profile override captures requested profile and preserves config
        When test_cli_baseline_profile_override_captures_requested_profile_and_preserves_config executes the target flow
        Then the expected outcome for cli baseline profile override captures requested profile and preserves config is confirmed.

    Boundaries:
        - Focus: cli baseline profile override captures requested profile and preserves config
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline profile override captures requested profile and preserves config
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline ds101 ds102
    """
    case = asset_case("ds101", "dangling_file_link")
    asset_case("ds102", "stray_comment_file")
    asset_case("ds101", "second_dangling_link_file")
    case.path("doc_sentinel.toml").write_text(
        'profile = "standard"\nbaseline = "custom-baseline.json"\nexclude = ["second.md"]\nignore = ["DS102"]\n',
        encoding="utf-8",
    )

    exit_code = main(["baseline", str(case.root), "--profile", "fast"])
    assert exit_code == 0

    custom_baseline = case.path("custom-baseline.json")
    assert custom_baseline.exists()
    suppressed = load_baseline(custom_baseline)
    expected_finding = Finding(
        rule="DS101",
        path="README.md",
        message="dangling link -> missing.md",
        severity="error",
        line=1,
    )
    assert suppressed == frozenset({fingerprint(expected_finding)})
