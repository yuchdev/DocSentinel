"""Claim-selection options shared by ``scan``, ``baseline`` and ``extract-facts`` (owner rulings of 2026-11-27).

``scan``/``baseline`` take ``--min-salience``, ``--max-per-document``, ``--max-total`` (replace the
``fact_check_*`` values for the run), ``--weights``/``--dedup-threshold`` (forwarded to ``scan()``)
and ``--include-facts FILE``; ``extract-facts`` takes ``--fact-combination``. ``scan()`` and
``extract_facts()`` are replaced by recorders here, except where a real fast scan checks the
facts-file refusal; no backend, model or network is used.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from docsentinel import cli
from docsentinel.config import Config
from docsentinel.models import FactExtractionResult, ScanResult
from tests.log_helpers import problem_output

#: The five selection options and a valid value of each.
_SELECTION_ARGS = (
    "--min-salience",
    "0.7",
    "--max-per-document",
    "4",
    "--max-total",
    "9",
    "--weights",
    "0.5,0.5,0",
    "--dedup-threshold",
    "0.8",
)


def _empty_result() -> ScanResult:
    """Return an empty fast scan result.

    :returns: The result.
    """
    return ScanResult(profile="fast", documents=(), findings=(), enabled_rules=(), pending=())


def _record_scan(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Config, dict[str, Any]]]:
    """Replace ``cli.scan`` with a recorder of its config and keywords.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The ``(config, keywords)`` list the recorder appends to.
    """
    seen: list[tuple[Config, dict[str, Any]]] = []

    def recording(root: Any, *, config: Config, **kwargs: Any) -> ScanResult:
        """Record the config and keywords and return an empty result."""
        seen.append((config, kwargs))
        return _empty_result()

    monkeypatch.setattr(cli, "scan", recording)
    return seen


def _argv(command: str, root: Path, *extra: str) -> list[str]:
    """Return the argument vector of ``command`` over ``root``.

    :param command: ``scan`` or ``baseline``.
    :param root: The scan root.
    :param extra: Further arguments.
    :returns: The argument vector.
    """
    argv = [command, str(root), *extra]
    if command == "baseline":
        argv += ["--output", str(root / "baseline.json")]
    return argv


@pytest.mark.parametrize("command", ["scan", "baseline"])
def test_scan_and_baseline_parse_the_selection_options(command: str):
    """
    [Unit] CLI selection options: verifies scan and baseline parse the five options and --include-facts.

    Scenario:
        Given the scan or baseline parser
        When the five selection options and --include-facts are given, and then none
        Then each is parsed to its typed value, and every one defaults to None.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (same options on all three commands)
        - Fixtures/params: command
        - Scope: cli._build_parser

    On failure, first check:
        - _add_fact_selection_options and the --include-facts arguments in cli.py
    """
    parser = cli._build_parser()

    args = parser.parse_args([command, *_SELECTION_ARGS, "--include-facts", "f.json"])
    default = parser.parse_args([command])

    assert (args.min_salience, args.max_per_document, args.max_total) == (0.7, 4, 9)
    assert (args.weights, args.dedup_threshold, args.include_facts) == ((0.5, 0.5, 0.0), 0.8, Path("f.json"))
    for name in ("min_salience", "max_per_document", "max_total", "weights", "dedup_threshold", "include_facts"):
        assert getattr(default, name) is None


@pytest.mark.parametrize("command", ["scan", "baseline"])
@pytest.mark.parametrize("bad", [["--weights", "0.5,0.5"], ["--weights", "a,b,c"], ["--max-total", "x"]])
def test_malformed_selection_values_are_argparse_errors(command: str, bad: list[str]):
    """
    [Unit] CLI selection options: verifies a malformed weights or integer value exits 2 at parse time.

    Scenario:
        Given the scan or baseline parser
        When --weights has two parts or non-numbers, or --max-total is not an integer
        Then argparse exits with code 2.

    Boundaries:
        - Focus: _weights_argument shared with extract-facts
        - Fixtures/params: command, bad
        - Scope: cli._build_parser

    On failure, first check:
        - _weights_argument in cli.py
    """
    with pytest.raises(SystemExit) as raised:
        cli._build_parser().parse_args([command, *bad])
    assert raised.value.code == 2


@pytest.mark.parametrize("command", ["scan", "baseline"])
def test_selection_options_reach_config_and_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str):
    """
    [Unit] CLI selection options: verifies the three config overrides and the two policy keywords reach scan().

    Scenario:
        Given scan() replaced by a recorder
        When "docsentinel <command> ROOT" runs with the five selection options
        Then the config passed to scan() carries fact_check_min_salience 0.7,
        fact_check_max_claims_per_document 4 and fact_check_max_claims_total 9, and scan()
        receives fact_weights (0.5, 0.5, 0.0) and fact_dedup_threshold 0.8.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (_fact_config_changes, _scan_overrides)
        - Fixtures/params: command
        - Scope: cli.main with scan() replaced

    On failure, first check:
        - _fact_config_changes and _scan_overrides in cli.py
    """
    seen = _record_scan(monkeypatch)

    assert cli.main(_argv(command, tmp_path, *_SELECTION_ARGS)) == 0

    ((config, kwargs),) = seen
    assert (
        config.fact_check_min_salience,
        config.fact_check_max_claims_per_document,
        config.fact_check_max_claims_total,
    ) == (0.7, 4, 9)
    assert (kwargs["fact_weights"], kwargs["fact_dedup_threshold"]) == ((0.5, 0.5, 0.0), 0.8)
    assert "facts_file" not in kwargs


@pytest.mark.parametrize("command", ["scan", "baseline"])
def test_without_selection_options_scan_gets_the_configured_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
):
    """
    [Unit] CLI selection options: verifies no option leaves the config and scan() keywords as before.

    Scenario:
        Given scan() replaced by a recorder
        When "docsentinel <command> ROOT" runs with no selection option
        Then the config keeps the Config defaults and no fact_* keyword is passed.

    Boundaries:
        - Focus: unchanged behaviour without the new options
        - Fixtures/params: command
        - Scope: cli.main with scan() replaced

    On failure, first check:
        - The None guards in _fact_config_changes and _scan_overrides
    """
    seen = _record_scan(monkeypatch)

    assert cli.main(_argv(command, tmp_path)) == 0

    ((config, kwargs),) = seen
    defaults = Config()
    assert config.fact_check_max_claims_total == defaults.fact_check_max_claims_total
    assert config.fact_check_min_salience == defaults.fact_check_min_salience
    assert not {"fact_weights", "fact_dedup_threshold", "facts_file"} & set(kwargs)


@pytest.mark.parametrize("command", ["scan", "baseline"])
def test_include_facts_warns_about_the_ignored_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, command: str
):
    """
    [Unit] CLI --include-facts: verifies one WARNING names exactly the ignored options that were passed.

    Scenario:
        Given scan() replaced by a recorder
        When "docsentinel <command> ROOT --include-facts F --fact-combination all --max-total 3 --weights ..."
        runs
        Then scan() receives facts_file=F and no fact_weights, and one WARNING reads
        '--include-facts given: ignoring --fact-combination, --max-total, --weights'.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (_warn_ignored_fact_options)
        - Fixtures/params: command, caplog
        - Scope: cli.main with scan() replaced

    On failure, first check:
        - _FACTS_FILE_IGNORED and _warn_ignored_fact_options in cli.py
    """
    seen = _record_scan(monkeypatch)
    facts = tmp_path / "facts.json"
    caplog.set_level(logging.WARNING, logger="docsentinel")

    code = cli.main(
        _argv(
            command,
            tmp_path,
            "--include-facts",
            str(facts),
            "--fact-combination",
            "all",
            "--max-total",
            "3",
            "--weights",
            "0.5,0.5,0",
        )
    )

    assert code == 0
    ((_, kwargs),) = seen
    assert kwargs["facts_file"] == facts
    assert "fact_weights" not in kwargs
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["--include-facts given: ignoring --fact-combination, --max-total, --weights"]


def test_include_facts_alone_logs_no_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] CLI --include-facts: verifies no WARNING when no ignored option was passed.

    Scenario:
        Given scan() replaced by a recorder
        When "docsentinel scan ROOT --include-facts F" runs
        Then no WARNING is logged.

    Boundaries:
        - Focus: the warning appears only when something is ignored
        - Fixtures/params: caplog
        - Scope: cli.main with scan() replaced

    On failure, first check:
        - The if ignored guard of _warn_ignored_fact_options
    """
    _record_scan(monkeypatch)
    caplog.set_level(logging.WARNING, logger="docsentinel")

    assert cli.main(["scan", str(tmp_path), "--include-facts", str(tmp_path / "f.json")]) == 0
    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


@pytest.mark.parametrize("command", ["scan", "baseline"])
@pytest.mark.parametrize(
    ("content", "message"),
    [
        (None, "cannot read it (FileNotFoundError)"),
        ("[]", "not a facts-json file"),
        (json.dumps({"schema": "docsentinel-facts", "schema_version": 1, "facts": [{"path": "a.md"}]}), "fact 1"),
    ],
    ids=["missing", "wrong-schema", "no-text"],
)
def test_bad_facts_file_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], command: str, content: str, message: str
):
    """
    [Unit] CLI --include-facts: verifies an unusable facts file exits 2 with 'Scan failed: facts file ...'.

    Scenario:
        Given a scan root with one document and a facts file that is missing, not facts-json or
        has an entry without text
        When "docsentinel <command> ROOT --include-facts F" runs (fast profile, gate closed)
        Then the exit code is 2 and stderr names the file and the reason after the command's
        failure prefix.

    Boundaries:
        - Focus: fail closed on a bad invoker file
        - Fixtures/params: command, content, message
        - Scope: cli.main with the real engine

    On failure, first check:
        - The load_facts_file call in engine.scan and the ConfigError handling of _run_scan/_run_baseline
    """
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.md").write_text("# A\n", encoding="utf-8")
    facts = tmp_path / "facts.json"
    if content is not None:
        facts.write_text(content, encoding="utf-8")
    argv = [command, str(root), "--include-facts", str(facts)]
    if command == "baseline":
        argv += ["--output", str(tmp_path / "baseline.json")]

    assert cli.main(argv) == 2

    err = problem_output(capsys.readouterr().err)
    prefix = "Scan failed" if command == "scan" else "Baseline generation failed"
    assert f"{prefix}: facts file {facts}: " in err
    assert message in err


def test_extract_facts_forwards_fact_combination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] CLI extract-facts --fact-combination: verifies the value is validated and forwarded.

    Scenario:
        Given extract_facts() replaced by a recorder
        When "docsentinel extract-facts ROOT --fact-combination all" runs, and then with '1-3,2-4'
        Then extract_facts() receives fact_combination='all', and the overlapping ranges are an
        argparse error (exit 2) before any extraction.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (--fact-combination on extract-facts)
        - Fixtures/params: extract_facts replaced
        - Scope: cli.main and cli._build_parser

    On failure, first check:
        - _fact_overrides and the --fact-combination argument of _add_extract_facts_parser
    """
    seen: list[dict[str, Any]] = []

    def recording(root: Any, **kwargs: Any) -> FactExtractionResult:
        """Record the keywords, then stop the command."""
        seen.append(kwargs)
        raise RuntimeError("stop after recording")

    monkeypatch.setattr(cli, "extract_facts", recording)
    monkeypatch.setattr(cli.nlp, "deep_ready", lambda: True)

    cli.main(["extract-facts", str(tmp_path), "--fact-combination", "all"])

    assert seen and seen[0]["fact_combination"] == "all"
    with pytest.raises(SystemExit) as raised:
        cli._build_parser().parse_args(["extract-facts", "--fact-combination", "1-3,2-4"])
    assert raised.value.code == 2
