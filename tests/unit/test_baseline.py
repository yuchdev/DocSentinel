"""Tests for baseline fingerprinting, file persistence, and scan suppression."""

import hashlib
import json
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, Finding, filter_baselined, fingerprint, load_baseline, save_baseline, scan
from docsentinel.cli import main


def test_fingerprint_is_stable_for_identical_finding() :
    """
    [Unit] baseline: verifies fingerprint is stable for identical finding.

    Scenario:
        Given test inputs and fixtures for fingerprint is stable for identical finding
        When test_fingerprint_is_stable_for_identical_finding executes the target flow
        Then the expected outcome for fingerprint is stable for identical finding is confirmed.

    Boundaries:
        - Focus: fingerprint is stable for identical finding
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to fingerprint is stable for identical finding
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    finding1 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="error", line=5)
    finding2 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="error", line=5)
    assert fingerprint(finding1) == fingerprint(finding2)


def test_fingerprint_differs_by_rule_path_or_message() :
    """
    [Unit] baseline: verifies fingerprint differs by rule path or message.

    Scenario:
        Given test inputs and fixtures for fingerprint differs by rule path or message
        When test_fingerprint_differs_by_rule_path_or_message executes the target flow
        Then the expected outcome for fingerprint differs by rule path or message is confirmed.

    Boundaries:
        - Focus: fingerprint differs by rule path or message
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to fingerprint differs by rule path or message
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    base = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'")
    diff_rule = Finding(rule="DS102", path="docs/intro.md", message="Dangling link 'foo.md'")
    diff_path = Finding(rule="DS101", path="docs/other.md", message="Dangling link 'foo.md'")
    diff_msg = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'bar.md'")

    assert fingerprint(base) != fingerprint(diff_rule)
    assert fingerprint(base) != fingerprint(diff_path)
    assert fingerprint(base) != fingerprint(diff_msg)


def test_fingerprint_ignores_line_and_severity() :
    """
    [Unit] baseline: verifies fingerprint ignores line and severity.

    Scenario:
        Given test inputs and fixtures for fingerprint ignores line and severity
        When test_fingerprint_ignores_line_and_severity executes the target flow
        Then the expected outcome for fingerprint ignores line and severity is confirmed.

    Boundaries:
        - Focus: fingerprint ignores line and severity
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to fingerprint ignores line and severity
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    f1 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="error", line=10)
    f2 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="warning", line=99)
    assert fingerprint(f1) == fingerprint(f2)


def test_fingerprint_format_exact() :
    """
    [Unit] baseline: verifies fingerprint format exact.

    Scenario:
        Given test inputs and fixtures for fingerprint format exact
        When test_fingerprint_format_exact executes the target flow
        Then the expected outcome for fingerprint format exact is confirmed.

    Boundaries:
        - Focus: fingerprint format exact
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to fingerprint format exact
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    finding = Finding(rule="DS101", path="docs/guide.md", message="Link target missing")
    expected_hash = hashlib.sha256(b"Link target missing").hexdigest()[:12]
    assert fingerprint(finding) == f"DS101:docs/guide.md:{expected_hash}"


def test_load_baseline_missing_file_is_empty_set(tmp_path: Path) :
    """
    [Unit] baseline: verifies load baseline missing file is empty set.

    Scenario:
        Given test inputs and fixtures for load baseline missing file is empty set
        When test_load_baseline_missing_file_is_empty_set executes the target flow
        Then the expected outcome for load baseline missing file is empty set is confirmed.

    Boundaries:
        - Focus: load baseline missing file is empty set
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load baseline missing file is empty set
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    assert load_baseline(tmp_path / "nonexistent.json") == frozenset()


def test_load_baseline_malformed_json_raises_config_error(tmp_path: Path) :
    """
    [Unit] baseline: verifies load baseline malformed json raises config error.

    Scenario:
        Given test inputs and fixtures for load baseline malformed json raises config error
        When test_load_baseline_malformed_json_raises_config_error executes the target flow
        Then the expected outcome for load baseline malformed json raises config error is confirmed.

    Boundaries:
        - Focus: load baseline malformed json raises config error
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load baseline malformed json raises config error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ConfigError, match="Cannot read"):
        load_baseline(bad_json)


@pytest.mark.parametrize(
    "content,match_str",
    [
        ("[]", "expected a JSON object"),
        ('"string"', "expected a JSON object"),
        ("123", "expected a JSON object"),
        ("true", "expected a JSON object"),
        ("{}", "expected exactly 'fingerprints' key"),
        ('{"suppressed_findings": []}', "expected exactly 'fingerprints' key"),
        ('{"fingerprints": [], "extra": 1}', "expected exactly 'fingerprints' key"),
        (
            '{"fingerprints": {"DS101:a.md:1234567890ab": true}}',
            "'fingerprints' must be a list of strings",
        ),
        ('{"fingerprints": "not-a-list"}', "'fingerprints' must be a list of strings"),
        ('{"fingerprints": [123]}', "'fingerprints' must be a list of strings"),
        ('{"fingerprints": [null]}', "'fingerprints' must be a list of strings"),
        ('{"fingerprints": [true]}', "'fingerprints' must be a list of strings"),
        ('{"fingerprints": [{}]}', "'fingerprints' must be a list of strings"),
    ],
)
def test_load_baseline_invalid_shapes_raise_config_error(tmp_path: Path, content: str, match_str: str) :
    """
    [Unit] baseline: verifies load baseline invalid shapes raise config error.

    Scenario:
        Given test inputs and fixtures for load baseline invalid shapes raise config error
        When test_load_baseline_invalid_shapes_raise_config_error executes the target flow
        Then the expected outcome for load baseline invalid shapes raise config error is confirmed.

    Boundaries:
        - Focus: load baseline invalid shapes raise config error
        - Fixtures/params: tmp_path, content, match_str (parametrized, 13 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load baseline invalid shapes raise config error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    baseline_file = tmp_path / "invalid.json"
    baseline_file.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=match_str):
        load_baseline(baseline_file)


def test_load_baseline_directory_path_raises_config_error(tmp_path: Path) :
    """
    [Unit] baseline: verifies load baseline directory path raises config error.

    Scenario:
        Given test inputs and fixtures for load baseline directory path raises config error
        When test_load_baseline_directory_path_raises_config_error executes the target flow
        Then the expected outcome for load baseline directory path raises config error is confirmed.

    Boundaries:
        - Focus: load baseline directory path raises config error
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load baseline directory path raises config error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    dir_path = tmp_path / "somedir"
    dir_path.mkdir()
    with pytest.raises(ConfigError, match="Cannot read"):
        load_baseline(dir_path)


def test_save_then_load_round_trips(tmp_path: Path) :
    """
    [Unit] baseline: verifies save then load round trips.

    Scenario:
        Given test inputs and fixtures for save then load round trips
        When test_save_then_load_round_trips executes the target flow
        Then the expected outcome for save then load round trips is confirmed.

    Boundaries:
        - Focus: save then load round trips
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to save then load round trips
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    findings = (
        Finding(rule="DS101", path="a.md", message="Broken link"),
        Finding(rule="DS102", path="b.md", message="Stray comment"),
    )
    baseline_file = tmp_path / "baseline.json"
    save_baseline(baseline_file, findings)

    loaded = load_baseline(baseline_file)
    expected = frozenset(fingerprint(f) for f in findings)
    assert loaded == expected


def test_save_baseline_creates_parent_directories(tmp_path: Path) :
    """
    [Unit] baseline: verifies save baseline creates parent directories.

    Scenario:
        Given test inputs and fixtures for save baseline creates parent directories
        When test_save_baseline_creates_parent_directories executes the target flow
        Then the expected outcome for save baseline creates parent directories is confirmed.

    Boundaries:
        - Focus: save baseline creates parent directories
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to save baseline creates parent directories
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    nested = tmp_path / "deep" / "nested" / "path" / "baseline.json"
    findings = (Finding(rule="DS101", path="a.md", message="Broken link"),)
    save_baseline(nested, findings)
    assert nested.exists()
    assert load_baseline(nested) == frozenset({fingerprint(findings[0])})


def test_save_baseline_is_deterministic_and_sorted(tmp_path: Path) :
    """
    [Unit] baseline: verifies save baseline is deterministic and sorted.

    Scenario:
        Given test inputs and fixtures for save baseline is deterministic and sorted
        When test_save_baseline_is_deterministic_and_sorted executes the target flow
        Then the expected outcome for save baseline is deterministic and sorted is confirmed.

    Boundaries:
        - Focus: save baseline is deterministic and sorted
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to save baseline is deterministic and sorted
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    f1 = Finding(rule="DS102", path="z.md", message="Stray comment")
    f2 = Finding(rule="DS101", path="a.md", message="Broken link")
    f3 = Finding(rule="DS101", path="m.md", message="Broken link")

    baseline_file1 = tmp_path / "baseline1.json"
    baseline_file2 = tmp_path / "baseline2.json"

    # Save with different initial orders and duplicates
    save_baseline(baseline_file1, (f1, f2, f3, f1))
    save_baseline(baseline_file2, (f3, f1, f2))

    content1 = baseline_file1.read_text(encoding="utf-8")
    content2 = baseline_file2.read_text(encoding="utf-8")

    assert content1 == content2

    parsed = json.loads(content1)
    assert parsed["fingerprints"] == sorted(parsed["fingerprints"])


def test_filter_baselined_drops_known_findings_only() :
    """
    [Unit] baseline: verifies filter baselined drops known findings only.

    Scenario:
        Given test inputs and fixtures for filter baselined drops known findings only
        When test_filter_baselined_drops_known_findings_only executes the target flow
        Then the expected outcome for filter baselined drops known findings only is confirmed.

    Boundaries:
        - Focus: filter baselined drops known findings only
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to filter baselined drops known findings only
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    f1 = Finding(rule="DS101", path="a.md", message="Link 1")
    f2 = Finding(rule="DS101", path="b.md", message="Link 2")
    f3 = Finding(rule="DS102", path="c.md", message="Comment 1")

    known = frozenset({fingerprint(f1), fingerprint(f3)})
    filtered = filter_baselined((f1, f2, f3), known)
    assert filtered == (f2,)


def test_scan_with_baseline_suppresses_matching_findings(tmp_path: Path) :
    """
    [Unit] baseline: verifies scan with baseline suppresses matching findings.

    Scenario:
        Given test inputs and fixtures for scan with baseline suppresses matching findings
        When test_scan_with_baseline_suppresses_matching_findings executes the target flow
        Then the expected outcome for scan with baseline suppresses matching findings is confirmed.

    Boundaries:
        - Focus: scan with baseline suppresses matching findings
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with baseline suppresses matching findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")

    # Initial scan without baseline surfaces the finding
    raw_result = scan(tmp_path)
    assert len(raw_result.findings) == 1
    assert raw_result.findings[0].rule == "DS101"

    # Capture baseline
    baseline_file = tmp_path / ".docsentinel-baseline.json"
    save_baseline(baseline_file, raw_result.findings)

    # Scan with baseline configured suppresses the finding
    baselined_result = scan(tmp_path, config=Config(baseline=".docsentinel-baseline.json"))
    assert len(baselined_result.findings) == 0


def test_scan_with_baseline_still_reports_new_findings(tmp_path: Path) :
    """
    [Unit] baseline: verifies scan with baseline still reports new findings.

    Scenario:
        Given test inputs and fixtures for scan with baseline still reports new findings
        When test_scan_with_baseline_still_reports_new_findings executes the target flow
        Then the expected outcome for scan with baseline still reports new findings is confirmed.

    Boundaries:
        - Focus: scan with baseline still reports new findings
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with baseline still reports new findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc1 = tmp_path / "first.md"
    doc1.write_text("[dangling](missing1.md)\n", encoding="utf-8")

    initial_result = scan(tmp_path)
    assert len(initial_result.findings) == 1

    baseline_file = tmp_path / ".docsentinel-baseline.json"
    save_baseline(baseline_file, initial_result.findings)

    # Add a second document with a different issue
    doc2 = tmp_path / "second.md"
    doc2.write_text("[dangling](missing2.md)\n", encoding="utf-8")

    new_result = scan(tmp_path, config=Config(baseline=".docsentinel-baseline.json"))
    assert len(new_result.findings) == 1
    assert new_result.findings[0].path == "second.md"


def test_scan_with_missing_baseline_file_does_not_fail(tmp_path: Path) :
    """
    [Unit] baseline: verifies scan with missing baseline file does not fail.

    Scenario:
        Given test inputs and fixtures for scan with missing baseline file does not fail
        When test_scan_with_missing_baseline_file_does_not_fail executes the target flow
        Then the expected outcome for scan with missing baseline file does not fail is confirmed.

    Boundaries:
        - Focus: scan with missing baseline file does not fail
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with missing baseline file does not fail
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(baseline="nonexistent-baseline.json"))
    assert len(result.findings) == 1


def test_scan_with_corrupt_baseline_file_raises_config_error(tmp_path: Path) :
    """
    [Unit] baseline: verifies scan with corrupt baseline file raises config error.

    Scenario:
        Given test inputs and fixtures for scan with corrupt baseline file raises config error
        When test_scan_with_corrupt_baseline_file_raises_config_error executes the target flow
        Then the expected outcome for scan with corrupt baseline file raises config error is confirmed.

    Boundaries:
        - Focus: scan with corrupt baseline file raises config error
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to scan with corrupt baseline file raises config error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")
    bad_baseline = tmp_path / "bad-baseline.json"
    bad_baseline.write_text("{bad", encoding="utf-8")

    with pytest.raises(ConfigError):
        scan(tmp_path, config=Config(baseline="bad-baseline.json"))


def test_cli_baseline_subcommand_writes_file(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli baseline subcommand writes file.

    Scenario:
        Given test inputs and fixtures for cli baseline subcommand writes file
        When test_cli_baseline_subcommand_writes_file executes the target flow
        Then the expected outcome for cli baseline subcommand writes file is confirmed.

    Boundaries:
        - Focus: cli baseline subcommand writes file
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline subcommand writes file
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")

    exit_code = main(["baseline", str(tmp_path)])
    assert exit_code == 0

    default_baseline = tmp_path / ".docsentinel-baseline.json"
    assert default_baseline.exists()
    suppressed = load_baseline(default_baseline)
    assert len(suppressed) == 1


def test_cli_baseline_subcommand_with_output_flag(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli baseline subcommand with output flag.

    Scenario:
        Given test inputs and fixtures for cli baseline subcommand with output flag
        When test_cli_baseline_subcommand_with_output_flag executes the target flow
        Then the expected outcome for cli baseline subcommand with output flag is confirmed.

    Boundaries:
        - Focus: cli baseline subcommand with output flag
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline subcommand with output flag
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")
    custom_output = tmp_path / "custom" / "base.json"

    exit_code = main(["baseline", str(tmp_path), "--output", str(custom_output)])
    assert exit_code == 0
    assert custom_output.exists()
    assert len(load_baseline(custom_output)) == 1


def test_cli_baseline_subcommand_honors_config_and_ignores(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli baseline subcommand honors config and ignores.

    Scenario:
        Given test inputs and fixtures for cli baseline subcommand honors config and ignores
        When test_cli_baseline_subcommand_honors_config_and_ignores executes the target flow
        Then the expected outcome for cli baseline subcommand honors config and ignores is confirmed.

    Boundaries:
        - Focus: cli baseline subcommand honors config and ignores
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline subcommand honors config and ignores
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        'ignore = ["DS101"]\nbaseline = "cfg-baseline.json"\n', encoding="utf-8"
    )
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n<!-- stray -->\n", encoding="utf-8")

    exit_code = main(["baseline", str(tmp_path)])
    assert exit_code == 0

    cfg_baseline = tmp_path / "cfg-baseline.json"
    assert cfg_baseline.exists()
    suppressed = load_baseline(cfg_baseline)
    # DS101 is ignored by config, so only DS102 stray comment is captured
    assert len(suppressed) == 1
    assert any("DS102" in item for item in suppressed)


def test_cli_baseline_is_idempotent(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli baseline is idempotent.

    Scenario:
        Given test inputs and fixtures for cli baseline is idempotent
        When test_cli_baseline_is_idempotent executes the target flow
        Then the expected outcome for cli baseline is idempotent is confirmed.

    Boundaries:
        - Focus: cli baseline is idempotent
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline is idempotent
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n<!-- stray -->\n", encoding="utf-8")

    main(["baseline", str(tmp_path)])
    baseline_file = tmp_path / ".docsentinel-baseline.json"
    first_run = baseline_file.read_bytes()

    main(["baseline", str(tmp_path)])
    second_run = baseline_file.read_bytes()

    assert first_run == second_run


def test_cli_scan_exit_code_zero_when_errors_are_baselined(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli scan exit code zero when errors are baselined.

    Scenario:
        Given test inputs and fixtures for cli scan exit code zero when errors are baselined
        When test_cli_scan_exit_code_zero_when_errors_are_baselined executes the target flow
        Then the expected outcome for cli scan exit code zero when errors are baselined is confirmed.

    Boundaries:
        - Focus: cli scan exit code zero when errors are baselined
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli scan exit code zero when errors are baselined
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")

    # Without baseline: fails with exit code 1
    assert main(["scan", str(tmp_path)]) == 1
    assert main(["scan", str(tmp_path), "--strict"]) == 1

    # Create baseline and config
    (tmp_path / "doc_sentinel.toml").write_text('baseline = ".docsentinel-baseline.json"\n', encoding="utf-8")
    main(["baseline", str(tmp_path)])

    # With baseline: succeeds with exit code 0 even under --strict
    assert main(["scan", str(tmp_path)]) == 0
    assert main(["scan", str(tmp_path), "--strict"]) == 0


def test_cli_scan_exit_code_with_new_findings_after_baseline(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli scan exit code with new findings after baseline.

    Scenario:
        Given test inputs and fixtures for cli scan exit code with new findings after baseline
        When test_cli_scan_exit_code_with_new_findings_after_baseline executes the target flow
        Then the expected outcome for cli scan exit code with new findings after baseline is confirmed.

    Boundaries:
        - Focus: cli scan exit code with new findings after baseline
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli scan exit code with new findings after baseline
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    (tmp_path / "doc_sentinel.toml").write_text('baseline = ".docsentinel-baseline.json"\n', encoding="utf-8")
    doc1 = tmp_path / "first.md"
    doc1.write_text("[dangling](missing1.md)\n", encoding="utf-8")
    main(["baseline", str(tmp_path)])

    # Add a new warning (DS102)
    doc2 = tmp_path / "second.md"
    doc2.write_text("<!-- stray comment -->\n", encoding="utf-8")

    # In default mode, warning alone exits 0
    assert main(["scan", str(tmp_path)]) == 0
    # In strict mode, warning causes exit 1
    assert main(["scan", str(tmp_path), "--strict"]) == 1

    # Add a new error (DS101)
    doc3 = tmp_path / "third.md"
    doc3.write_text("[another](missing2.md)\n", encoding="utf-8")

    # In default and strict modes, error causes exit 1
    assert main(["scan", str(tmp_path)]) == 1
    assert main(["scan", str(tmp_path), "--strict"]) == 1


def test_cli_baseline_failure_exits_two(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli baseline failure exits two.

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
        - Recent changes in code paths exercised by baseline
    """
    (tmp_path / "doc_sentinel.toml").write_text("invalid = toml[\n", encoding="utf-8")
    assert main(["baseline", str(tmp_path)]) == 2


def test_cli_baseline_profile_override_captures_requested_profile_and_preserves_config(tmp_path: Path) :
    """
    [Unit] baseline: verifies cli baseline profile override captures requested profile and preserves config.

    Scenario:
        Given test inputs and fixtures for cli baseline profile override captures requested profile and preserves config
        When test_cli_baseline_profile_override_captures_requested_profile_and_preserves_config executes the target flow
        Then the expected outcome for cli baseline profile override captures requested profile and preserves config is confirmed.

    Boundaries:
        - Focus: cli baseline profile override captures requested profile and preserves config
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to cli baseline profile override captures requested profile and preserves config
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by baseline
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        'profile = "standard"\nbaseline = "custom-baseline.json"\nexclude = ["skip.md"]\nignore = ["DS102"]\n',
        encoding="utf-8",
    )
    doc = tmp_path / "test.md"
    doc.write_text("[missing](missing.md)\n<!-- stray -->\n", encoding="utf-8")
    skip_doc = tmp_path / "skip.md"
    skip_doc.write_text("[missing](missing.md)\n", encoding="utf-8")

    exit_code = main(["baseline", str(tmp_path), "--profile", "fast"])
    assert exit_code == 0

    custom_baseline = tmp_path / "custom-baseline.json"
    assert custom_baseline.exists()
    suppressed = load_baseline(custom_baseline)
    expected_finding = Finding(
        rule="DS101",
        path="test.md",
        message="dangling link -> missing.md",
        severity="error",
        line=1,
    )
    assert suppressed == frozenset({fingerprint(expected_finding)})
