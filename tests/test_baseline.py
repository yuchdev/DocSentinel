"""Tests for baseline fingerprinting, file persistence, and scan suppression."""

import hashlib
import json
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, Finding, filter_baselined, fingerprint, load_baseline, save_baseline, scan
from docsentinel.cli import main


def test_fingerprint_is_stable_for_identical_finding() -> None:
    finding1 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="error", line=5)
    finding2 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="error", line=5)
    assert fingerprint(finding1) == fingerprint(finding2)


def test_fingerprint_differs_by_rule_path_or_message() -> None:
    base = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'")
    diff_rule = Finding(rule="DS102", path="docs/intro.md", message="Dangling link 'foo.md'")
    diff_path = Finding(rule="DS101", path="docs/other.md", message="Dangling link 'foo.md'")
    diff_msg = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'bar.md'")

    assert fingerprint(base) != fingerprint(diff_rule)
    assert fingerprint(base) != fingerprint(diff_path)
    assert fingerprint(base) != fingerprint(diff_msg)


def test_fingerprint_ignores_line_and_severity() -> None:
    f1 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="error", line=10)
    f2 = Finding(rule="DS101", path="docs/intro.md", message="Dangling link 'foo.md'", severity="warning", line=99)
    assert fingerprint(f1) == fingerprint(f2)


def test_fingerprint_format_exact() -> None:
    finding = Finding(rule="DS101", path="docs/guide.md", message="Link target missing")
    expected_hash = hashlib.sha256(b"Link target missing").hexdigest()[:12]
    assert fingerprint(finding) == f"DS101:docs/guide.md:{expected_hash}"


def test_load_baseline_missing_file_is_empty_set(tmp_path: Path) -> None:
    assert load_baseline(tmp_path / "nonexistent.json") == frozenset()


def test_load_baseline_malformed_json_raises_config_error(tmp_path: Path) -> None:
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
def test_load_baseline_invalid_shapes_raise_config_error(tmp_path: Path, content: str, match_str: str) -> None:
    baseline_file = tmp_path / "invalid.json"
    baseline_file.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError, match=match_str):
        load_baseline(baseline_file)


def test_load_baseline_directory_path_raises_config_error(tmp_path: Path) -> None:
    dir_path = tmp_path / "somedir"
    dir_path.mkdir()
    with pytest.raises(ConfigError, match="Cannot read"):
        load_baseline(dir_path)


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    findings = (
        Finding(rule="DS101", path="a.md", message="Broken link"),
        Finding(rule="DS102", path="b.md", message="Stray comment"),
    )
    baseline_file = tmp_path / "baseline.json"
    save_baseline(baseline_file, findings)

    loaded = load_baseline(baseline_file)
    expected = frozenset(fingerprint(f) for f in findings)
    assert loaded == expected


def test_save_baseline_creates_parent_directories(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "path" / "baseline.json"
    findings = (Finding(rule="DS101", path="a.md", message="Broken link"),)
    save_baseline(nested, findings)
    assert nested.exists()
    assert load_baseline(nested) == frozenset({fingerprint(findings[0])})


def test_save_baseline_is_deterministic_and_sorted(tmp_path: Path) -> None:
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


def test_filter_baselined_drops_known_findings_only() -> None:
    f1 = Finding(rule="DS101", path="a.md", message="Link 1")
    f2 = Finding(rule="DS101", path="b.md", message="Link 2")
    f3 = Finding(rule="DS102", path="c.md", message="Comment 1")

    known = frozenset({fingerprint(f1), fingerprint(f3)})
    filtered = filter_baselined((f1, f2, f3), known)
    assert filtered == (f2,)


def test_scan_with_baseline_suppresses_matching_findings(tmp_path: Path) -> None:
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


def test_scan_with_baseline_still_reports_new_findings(tmp_path: Path) -> None:
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


def test_scan_with_missing_baseline_file_does_not_fail(tmp_path: Path) -> None:
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(baseline="nonexistent-baseline.json"))
    assert len(result.findings) == 1


def test_scan_with_corrupt_baseline_file_raises_config_error(tmp_path: Path) -> None:
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")
    bad_baseline = tmp_path / "bad-baseline.json"
    bad_baseline.write_text("{bad", encoding="utf-8")

    with pytest.raises(ConfigError):
        scan(tmp_path, config=Config(baseline="bad-baseline.json"))


def test_cli_baseline_subcommand_writes_file(tmp_path: Path) -> None:
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")

    exit_code = main(["baseline", str(tmp_path)])
    assert exit_code == 0

    default_baseline = tmp_path / ".docsentinel-baseline.json"
    assert default_baseline.exists()
    suppressed = load_baseline(default_baseline)
    assert len(suppressed) == 1


def test_cli_baseline_subcommand_with_output_flag(tmp_path: Path) -> None:
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n", encoding="utf-8")
    custom_output = tmp_path / "custom" / "base.json"

    exit_code = main(["baseline", str(tmp_path), "--output", str(custom_output)])
    assert exit_code == 0
    assert custom_output.exists()
    assert len(load_baseline(custom_output)) == 1


def test_cli_baseline_subcommand_honors_config_and_ignores(tmp_path: Path) -> None:
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


def test_cli_baseline_is_idempotent(tmp_path: Path) -> None:
    doc = tmp_path / "test.md"
    doc.write_text("[dangling](missing.md)\n<!-- stray -->\n", encoding="utf-8")

    main(["baseline", str(tmp_path)])
    baseline_file = tmp_path / ".docsentinel-baseline.json"
    first_run = baseline_file.read_bytes()

    main(["baseline", str(tmp_path)])
    second_run = baseline_file.read_bytes()

    assert first_run == second_run


def test_cli_scan_exit_code_zero_when_errors_are_baselined(tmp_path: Path) -> None:
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


def test_cli_scan_exit_code_with_new_findings_after_baseline(tmp_path: Path) -> None:
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


def test_cli_baseline_failure_exits_two(tmp_path: Path) -> None:
    (tmp_path / "doc_sentinel.toml").write_text("invalid = toml[\n", encoding="utf-8")
    assert main(["baseline", str(tmp_path)]) == 2


def test_cli_baseline_profile_override_captures_requested_profile_and_preserves_config(tmp_path: Path) -> None:
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
