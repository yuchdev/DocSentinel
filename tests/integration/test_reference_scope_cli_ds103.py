"""CLI ``--reference-scope`` over the DS103 ``unresolvable_path_file`` asset (Milestone 0009 Story 01.0).

The default scope ``"links"`` leaves DS103 inert and names it in the notice; ``strict``
from the config or the command line enables it, and the command line beats the config.
"""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.baseline import load_baseline
from docsentinel.config import load_config
from tests.asset_helpers import AssetCase
from tests.log_helpers import problem_output

_DS103_HINT = 'DS103 (set reference_scope = "strict")'


def _ds103_findings(report: str) -> list[dict]:
    """Return the DS103 problems of a schema-2 JSON report."""
    document = json.loads(report)
    return [problem for doc in document["documents"] for problem in doc["problems"] if problem["rule"] == "DS103"]


def test_default_scope_keeps_ds103_inert_and_names_it(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds103: verifies the default scope reports no DS103 finding and names DS103 in the notice.

    Scenario:
        Given a document with one unresolvable path-like code span and no config
        When ``docsentinel scan --format text`` runs
        Then the report has no DS103 line and the notice lists DS103 with the reference_scope hint,
            ahead of the byte-identical legacy entries.

    Boundaries:
        - Focus: Story 01.0 acceptance "Default scope is links; DS103 is inert and named"
        - Fixtures/params: ds103/unresolvable_path_file
        - Scope: one in-process CLI call

    On failure, first check:
        - DS103's opt-in registration and the self-gate in detectors/paths.py
    """
    root = asset_case("ds103", "unresolvable_path_file").root

    code = cli.main(["scan", str(root)])
    out = capsys.readouterr().out

    assert code == 0
    assert "DS103 unresolvable path" not in out
    assert (
        "12 fast rule(s) evaluated; opt-in rule(s) not enabled: "
        f"{_DS103_HINT}, DS110 (set require_fence_languages), DS112 (set navigation_indexes), "
        "DS115 (set deprecated_references_file), DS118 (set documentation_naming)."
    ) in out


@pytest.mark.parametrize(
    ("config_scope", "flag", "expected"),
    [
        (None, "strict", 1),  # flag alone enables DS103
        ("strict", None, 1),  # config alone enables DS103
        ("links", "strict", 1),  # CLI beats config (enable)
        ("strict", "links", 0),  # CLI beats config (disable)
    ],
)
def test_scan_reference_scope_flag_beats_config(
    asset_case: Callable[[str, str], AssetCase],
    capsys: pytest.CaptureFixture[str],
    config_scope: str,
    flag: str,
    expected: int,
):
    """
    [Integration] cli ds103: verifies ``scan --reference-scope`` enables DS103 and wins over the config.

    Scenario:
        Given the DS103 asset, optionally with reference_scope in docsentinel.toml
        When ``docsentinel scan --format json`` runs with or without ``--reference-scope``
        Then DS103 reports the span exactly when the effective scope is strict.

    Boundaries:
        - Focus: C1 layer 4 precedence for --reference-scope
        - Fixtures/params: ds103/unresolvable_path_file; four config/flag pairs
        - Scope: one in-process CLI call per case

    On failure, first check:
        - The reference_scope change in cli._run_scan
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    if config_scope is not None:
        (root / "docsentinel.toml").write_text(f'reference_scope = "{config_scope}"\n', encoding="utf-8")
    argv = ["scan", str(root), "--format", "json"] + ([] if flag is None else ["--reference-scope", flag])

    assert cli.main(argv) == 0
    findings = _ds103_findings(capsys.readouterr().out)

    assert len(findings) == expected
    if expected:
        assert findings[0]["value"] == "nonexistent/path.py"


def test_baseline_reference_scope_strict_records_ds103(
    asset_case: Callable[[str, str], AssetCase], tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds103: verifies ``baseline --reference-scope strict`` records the DS103 finding.

    Scenario:
        Given the DS103 asset and no config
        When ``docsentinel baseline`` runs with and without ``--reference-scope strict``
        Then the strict baseline holds one fingerprint and the default one holds none,
            and the start log line names the effective scope.

    Boundaries:
        - Focus: a strict lane can record its own baseline
        - Fixtures/params: ds103/unresolvable_path_file
        - Scope: two in-process CLI calls

    On failure, first check:
        - The reference_scope replace in cli._run_baseline
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    strict_out = tmp_path / "strict.json"
    default_out = tmp_path / "default.json"

    assert cli.main(["baseline", str(root), "--output", str(strict_out), "--reference-scope", "strict"]) == 0
    strict_err = capsys.readouterr().err
    assert cli.main(["baseline", str(root), "--output", str(default_out)]) == 0
    default_err = capsys.readouterr().err

    assert len(load_baseline(strict_out)) == 1
    assert len(load_baseline(default_out)) == 0
    assert f"output={strict_out}, reference_scope=strict" in strict_err.splitlines()[0]
    assert f"output={default_out}, reference_scope=links" in default_err.splitlines()[0]


@pytest.mark.parametrize("command", ["scan", "baseline"])
def test_invalid_reference_scope_flag_exits_2(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str], command: str
):
    """
    [Integration] cli ds103: verifies an out-of-vocabulary ``--reference-scope`` is a usage error.

    Scenario:
        Given ``--reference-scope STRICT`` (wrong case) on scan or baseline
        When the CLI parses it
        Then argparse exits with code 2 and names the valid choices.

    Boundaries:
        - Focus: invalid-input handling of the new flag
        - Fixtures/params: ds103/unresolvable_path_file; scan and baseline
        - Scope: one in-process CLI call

    On failure, first check:
        - The choices of --reference-scope in cli._build_parser
    """
    root = asset_case("ds103", "unresolvable_path_file").root

    with pytest.raises(SystemExit) as caught:
        cli.main([command, str(root), "--reference-scope", "STRICT"])

    assert caught.value.code == 2
    assert "argument --reference-scope: invalid choice: 'STRICT'" in capsys.readouterr().err


def test_invalid_reference_scope_config_exits_2(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli ds103: verifies an invalid configured reference_scope fails the scan with exit 2.

    Scenario:
        Given docsentinel.toml with reference_scope = "everything"
        When ``docsentinel scan`` runs
        Then it exits 2 with the validator message on a ``Scan failed:`` line.

    Boundaries:
        - Focus: Story acceptance "Invalid values exit 2 with the validator message"
        - Fixtures/params: ds103/unresolvable_path_file
        - Scope: one in-process CLI call

    On failure, first check:
        - The reference_scope entry of config._ENUM_OPTIONS
    """
    root = asset_case("ds103", "unresolvable_path_file").root
    (root / "docsentinel.toml").write_text('reference_scope = "everything"\n', encoding="utf-8")

    assert cli.main(["scan", str(root)]) == 2
    err = problem_output(capsys.readouterr().err)

    assert "Scan failed: reference_scope must be one of: links, strict" in err


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("", "reference scope: links (DS103 off)"),
        ('reference_scope = "strict"\n', "reference scope: strict (DS103 on)"),
        ('reference_scope = "bad"\n', "reference scope: error: reference_scope must be one of: links, strict"),
    ],
)
def test_doctor_reports_reference_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contents: str,
    expected: str,
):
    """
    [Integration] cli ds103: verifies ``doctor`` prints the effective reference scope and DS103 state.

    Scenario:
        Given a current directory whose config sets no, a strict, or an invalid reference_scope
        When ``docsentinel doctor`` runs
        Then it prints one reference-scope line (an error line for a bad config) and counts DS103 opt-in.

    Boundaries:
        - Focus: the doctor surface of "How the mode is reported"
        - Fixtures/params: tmp_path as the current directory; three config contents
        - Scope: one in-process CLI call

    On failure, first check:
        - cli._doctor_reference_scope_line
    """
    if contents:
        (tmp_path / "docsentinel.toml").write_text(contents, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert cli.main(["doctor"]) == 0
    lines = capsys.readouterr().out.splitlines()

    assert expected in lines
    fast = next(line for line in lines if line.startswith("fast rules:"))
    assert "opt-in, off unless configured: DS103, DS110, DS112, DS115, DS118)" in fast


def test_init_template_documents_both_keys(tmp_path: Path):
    """
    [Integration] cli: verifies the ``init`` template carries both new keys, commented, defaults shown.

    Scenario:
        Given the init TEMPLATE
        When it is written by ``docsentinel init`` and loaded back
        Then both keys appear commented with their defaults and the file loads to the defaults.

    Boundaries:
        - Focus: Task 03 step 6
        - Fixtures/params: tmp_path
        - Scope: one in-process CLI call plus load_config

    On failure, first check:
        - cli.TEMPLATE
    """
    assert '# reference_scope = "links"\n' in cli.TEMPLATE
    assert (
        '# at_reference_extensions = ["md", "markdown", "mdx", "txt", "rst", "toml", "json", "yaml", "yml", "py"]\n'
        in (cli.TEMPLATE)
    )
    assert cli.main(["init", str(tmp_path), "--yes"]) == 0
    settings = load_config(tmp_path)
    assert settings.reference_scope == "links"
