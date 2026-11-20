"""CLI logging over a live DS101 scan (``docs/specs/logging.md``).

``cli.main`` configures logging after parsing ``-v``/``-q``: INFO lines on stderr say what
started, what finished and where the report went, a per-run file under
``DOCSENTINEL_LOG_DIR`` (pointed at a temporary directory by ``tests/conftest.py``) keeps
DEBUG detail, and stdout carries only the report. The scan root is the
``ds101/dangling_file_link`` case (one dangling link, exit code ``1``) or ``ds101/clean_document``.
"""

import json
import os
import re
import subprocess
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli
from docsentinel.engine import scan
from docsentinel.reporting import render
from tests.asset_helpers import AssetCase

#: The engine's stage lines, logged inside ``scan()`` between the CLI's start and report lines.
_DISCOVERED = re.compile(r"^docsentinel: discovered \d+ documents under .+ \(\d+ skipped: symlinks/excluded, \d+ unreadable\)$")
_SELECTION = (
    "docsentinel: selection: include 2 pattern(s) (configured), exclude 3 pattern(s) (3 configured, 0 invoker)"
)
_RULE_PLAN = re.compile(r"^docsentinel: profile=fast: \d+ rules selected, \d+ evaluated; opt-in off: .+$")

_FINISHED = re.compile(
    r"^docsentinel: scan finished in \d+\.\d\ds: (\d+) documents, 1 findings \(errors 1, warnings 0\); "
    r"by rule DS101=1; blocking 1; exit code 1$"
)


def _log_dir() -> Path:
    """Return the per-test log directory the conftest fixture set."""
    return Path(os.environ["DOCSENTINEL_LOG_DIR"])


def test_scan_output_logs_start_report_written_and_finish(
    asset_case: Callable[[str, str], AssetCase], tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging ds101: verifies ``scan -o FILE`` is not silent on stderr.

    Scenario:
        Given a root with one dangling link and ``--output`` naming a file
        When ``docsentinel scan`` runs with default verbosity
        Then stdout is empty and stderr holds, in order, the start line, the engine's selection,
            discovery and rule-plan lines, the report-written line with the format and line count, the finish line with
            totals, and the log file line for the failing exit.

    Boundaries:
        - Focus: spec §1 "a CLI run is never silent" and the §3 INFO events
        - Fixtures/params: ds101/dangling_file_link
        - Scope: one in-process CLI call

    On failure, first check:
        - The ``logger.info`` calls in ``cli._run_scan`` and ``cli.main``
    """
    root = asset_case("ds101", "dangling_file_link").root
    target = tmp_path / "out" / "report.txt"

    code = cli.main(["scan", str(root), "-o", str(target)])
    captured = capsys.readouterr()

    assert code == 1 and captured.out == ""
    lines = captured.err.splitlines()
    assert lines[0] == f"docsentinel: scan started: root={root}, profile=fast, format=text, output={target}, reference_scope=links"
    assert lines[1] == "docsentinel: config: user settings off, project none"
    assert lines[2] == _SELECTION
    assert _DISCOVERED.match(lines[3]), lines[3]
    assert _RULE_PLAN.match(lines[4]), lines[4]
    report_lines = len(target.read_text(encoding="utf-8").splitlines())
    assert lines[5] == f"docsentinel: report written to {target} (text, {report_lines} lines)"
    assert _FINISHED.match(lines[6]), lines[6]
    assert lines[7].startswith(f"docsentinel: details in log file: {_log_dir()}{os.sep}docsentinel-")
    assert len(lines) == 8


def test_json_stdout_is_byte_identical_whatever_the_verbosity(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging ds101: verifies logging never writes to stdout.

    Scenario:
        Given a root with one dangling link
        When ``scan --format json`` runs quiet, by default, and with ``-v -v``
        Then stdout is the same bytes each time, equal to the library render plus one newline, and parses
            as JSON, while only the default and verbose runs write INFO lines to stderr.

    Boundaries:
        - Focus: spec §1 "logging never writes to stdout"
        - Fixtures/params: ds101/dangling_file_link
        - Scope: three in-process CLI calls

    On failure, first check:
        - A handler bound to ``sys.stdout``, or a ``print`` added for diagnostics
    """
    root = asset_case("ds101", "dangling_file_link").root
    expected = render(scan(root), "json", root=root) + "\n"
    outputs = []
    errors = []
    for flags in (["-q"], [], ["-v", "-v"]):
        assert cli.main(["scan", str(root), "--format", "json", *flags]) == 1
        captured = capsys.readouterr()
        outputs.append(captured.out)
        errors.append(captured.err)

    assert outputs == [expected] * 3
    json.loads(outputs[0])
    assert errors[0] == ""
    assert "docsentinel: scan started:" in errors[1] and "docsentinel: command: scan" not in errors[1]
    assert "docsentinel: command: scan" in errors[2]


@pytest.mark.parametrize(
    "argv",
    [["-v", "scan", "{root}"], ["scan", "-v", "{root}"], ["-q", "scan", "{root}"], ["scan", "{root}", "--quiet"]],
)
def test_verbosity_flags_work_before_and_after_the_subcommand(
    argv: list[str], asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging ds101: verifies ``-v``/``-q`` are accepted on both sides of the subcommand.

    Scenario:
        Given a clean root
        When the CLI runs with ``-v`` or ``-q`` before or after ``scan``
        Then the exit code is 0, ``-v`` shows the DEBUG ``command: scan`` line and ``-q`` shows nothing.

    Boundaries:
        - Focus: the suppressed-default parent parser in ``cli._build_parser``
        - Fixtures/params: four placements
        - Scope: one in-process CLI call each

    On failure, first check:
        - ``_add_verbosity_options`` and the ``parents=`` of each subparser
    """
    root = asset_case("ds101", "clean_document").root

    code = cli.main([part.format(root=root) for part in argv])
    err = capsys.readouterr().err

    assert code == 0
    if "-v" in argv:
        assert "docsentinel: command: scan" in err
    else:
        assert err == ""


def test_config_error_is_logged_once_at_warning_in_the_file_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli logging: verifies an exit-2 user error keeps its stderr message and is logged once at WARNING.

    Scenario:
        Given a root whose docsentinel.toml sets an unknown key
        When ``docsentinel scan`` runs
        Then it exits 2, stderr starts with the unchanged ``Scan failed:`` line followed only by the log file
            line, and the log file holds exactly one ``WARNING`` ``scan failed:`` record and no ``ERROR``.

    Boundaries:
        - Focus: spec §3 last paragraph (a user mistake is WARNING, not ERROR, and is not printed twice)
        - Fixtures/params: tmp_path (inline config; no detector runs)
        - Scope: one in-process CLI call

    On failure, first check:
        - The ``except`` branches of ``cli._run_scan`` and ``log.FILE_ONLY``
    """
    (tmp_path / "docsentinel.toml").write_text("no_such_option = 1\n", encoding="utf-8")

    code = cli.main(["scan", str(tmp_path)])
    lines = capsys.readouterr().err.splitlines()

    assert code == 2
    assert lines[0].startswith("Scan failed: ")
    assert len(lines) == 2 and lines[1].startswith("docsentinel: details in log file: ")
    (log_file,) = _log_dir().glob("docsentinel-*.log")
    text = log_file.read_text(encoding="utf-8")
    assert text.count("WARNING docsentinel.cli: scan failed: ") == 1
    assert " ERROR " not in text


def test_unwritable_log_directory_keeps_exit_code_and_stdout(
    asset_case: Callable[[str, str], AssetCase], tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging ds101: verifies a log directory that cannot be created changes nothing but stderr.

    Scenario:
        Given ``DOCSENTINEL_LOG_DIR`` naming a regular file, and a root with one dangling link
        When ``scan --format json`` runs
        Then the exit code (1) and stdout equal those of a run with a working log directory, and stderr
            starts with one WARNING that the log file is disabled and names no log file.

    Boundaries:
        - Focus: spec §2 "logging must never change an exit code"
        - Fixtures/params: ds101/dangling_file_link
        - Scope: two in-process CLI calls

    On failure, first check:
        - The fallback in ``log.configure_cli_logging``
    """
    root = asset_case("ds101", "dangling_file_link").root
    assert cli.main(["scan", str(root), "--format", "json"]) == 1
    expected = capsys.readouterr().out
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    os.environ["DOCSENTINEL_LOG_DIR"] = str(blocker)

    code = cli.main(["scan", str(root), "--format", "json"])
    captured = capsys.readouterr()

    assert code == 1 and captured.out == expected
    lines = captured.err.splitlines()
    assert lines[0].startswith("docsentinel: WARNING: log file disabled, logging to stderr only: ")
    assert not any("details in log file" in line for line in lines)


def test_baseline_logs_start_and_finish(
    asset_case: Callable[[str, str], AssetCase], tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging ds101: verifies ``docsentinel baseline`` logs its start and recorded totals.

    Scenario:
        Given a root with one dangling link
        When ``docsentinel baseline --output FILE`` runs
        Then stdout keeps ``Saved baseline:`` and stderr holds the start line, the engine's selection,
            discovery and rule-plan lines, and a finish line recording one DS101 finding and the output path.

    Boundaries:
        - Focus: spec §3 INFO events for the baseline command
        - Fixtures/params: ds101/dangling_file_link
        - Scope: one in-process CLI call

    On failure, first check:
        - The ``logger.info`` calls in ``cli._run_baseline``
    """
    root = asset_case("ds101", "dangling_file_link").root
    output = tmp_path / "baseline.json"

    assert cli.main(["baseline", str(root), "--output", str(output)]) == 0
    captured = capsys.readouterr()

    assert captured.out == f"Saved baseline: {output}\n"
    lines = captured.err.splitlines()
    assert lines[0] == f"docsentinel: baseline started: root={root}, profile=fast, output={output}, reference_scope=links"
    assert lines[1] == "docsentinel: config: user settings off, project none"
    assert lines[2] == _SELECTION
    assert _DISCOVERED.match(lines[3]), lines[3]
    assert _RULE_PLAN.match(lines[4]), lines[4]
    assert re.match(
        r"^docsentinel: baseline finished in \d+\.\d\ds: \d+ documents, 1 findings recorded "
        r"\(errors 1, warnings 0\); by rule DS101=1; written to .+; exit code 0$",
        lines[5],
    )
    assert len(lines) == 6


_IMPORT_PROBE = textwrap.dedent(
    """
    import logging, sys, tempfile, pathlib
    import docsentinel
    root = pathlib.Path(tempfile.mkdtemp())
    (root / "doc.md").write_text("# T\\n\\n[x](./missing.md)\\n", encoding="utf-8")
    docsentinel.scan(root)
    package = logging.getLogger("docsentinel")
    print(",".join(type(handler).__name__ for handler in package.handlers))
    print(len(logging.getLogger().handlers), package.propagate, package.level)
    """
)


def test_import_docsentinel_adds_only_a_null_handler(tmp_path: Path):
    """
    [Integration] cli logging: verifies the library configures no output of its own.

    Scenario:
        Given a fresh interpreter that imports docsentinel and runs a scan with a finding
        When its logging setup is inspected
        Then the package logger holds only a NullHandler, propagates, has no level of its own, the root
            logger has no handler, stderr is empty, and no log directory was created.

    Boundaries:
        - Focus: spec §1 "the library stays quiet"
        - Fixtures/params: tmp_path as the log directory that must stay absent
        - Scope: one isolated interpreter

    On failure, first check:
        - A handler or ``basicConfig`` added at import time outside ``docsentinel.log``
    """
    log_dir = tmp_path / "never-created"
    env = {**os.environ, "DOCSENTINEL_LOG_DIR": str(log_dir)}

    completed = subprocess.run(
        [sys.executable, "-I", "-c", _IMPORT_PROBE], capture_output=True, text=True, env=env, check=True
    )

    assert completed.stdout.splitlines() == ["NullHandler", "0 True 0"]
    assert completed.stderr == ""
    assert not log_dir.exists()


@pytest.mark.parametrize(
    ("dangling", "expected_rules"),
    [(False, ["DS100"]), (True, ["DS100", "DS101"])],
    ids=["clean_rest", "finding_in_rest"],
)
def test_non_utf8_document_is_reported_as_ds100_and_blocks(
    dangling: bool, expected_rules: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging: verifies a non-UTF-8 document gets one WARNING and a blocking DS100 finding.

    Scenario:
        Given a readable document (clean, or with one dangling link) and a non-UTF-8 document
        When ``docsentinel scan --format json`` runs
        Then stderr holds exactly one problem line naming the skipped document, the JSON report lists
            both documents with a DS100 error on the bad one, and the exit code is 1 (never 0, never 2).

    Boundaries:
        - Focus: owner decision "bad document -> skip + blocking DS100 finding" through the CLI
          (security review H1: one invalid byte must not turn the gate green)
        - Fixtures/params: tmp_path (inline documents), capsys; parametrized clean / one finding
        - Scope: one in-process CLI call

    On failure, first check:
        - engine._partition_readable, the DS100 emission in engine.scan and cli._exit_code
    """
    body = "# A\n\n[x](missing.md)\n" if dangling else "# A\n\nClean text.\n"
    (tmp_path / "a.md").write_text(body, encoding="utf-8")
    (tmp_path / "b.md").write_bytes(b"# B\n\n\xff\xfe\n")

    code = cli.main(["scan", str(tmp_path), "--format", "json"])
    captured = capsys.readouterr()

    assert code == 1
    assert [line for line in captured.err.splitlines() if line.startswith("docsentinel: WARNING")] == [
        "docsentinel: WARNING: skipped b.md: not valid UTF-8"
    ]
    assert "Scan failed" not in captured.err and "ERROR" not in captured.err
    assert any(
        line.startswith("docsentinel: discovered 2 documents under ") and line.endswith(", 1 unreadable)")
        for line in captured.err.splitlines()
    )
    payload = json.loads(captured.out)
    assert payload["summary"]["documents"] == 2
    problems = [problem for document in payload["documents"] for problem in document["problems"]]
    assert sorted(problem["rule"] for problem in problems) == expected_rules
    unreadable = next(problem for problem in problems if problem["rule"] == "DS100")
    assert unreadable["message"] == "unreadable document: not valid UTF-8"


def test_ignoring_ds100_restores_skip_with_warning_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli logging: verifies ``ignore = ["DS100"]`` turns an unreadable document back into a warning only.

    Scenario:
        Given a clean document, a non-UTF-8 document and a config that ignores DS100
        When ``docsentinel scan`` runs
        Then it exits 0 with the skip WARNING on stderr and no DS100 finding.

    Boundaries:
        - Focus: DS100 honours select/ignore like any rule
        - Fixtures/params: tmp_path, capsys
        - Scope: one in-process CLI call

    On failure, first check:
        - the effective_rules check guarding DS100 in engine.scan
    """
    (tmp_path / "docsentinel.toml").write_text('ignore = ["DS100"]\n', encoding="utf-8")
    (tmp_path / "a.md").write_text("# A\n\nClean text.\n", encoding="utf-8")
    (tmp_path / "b.md").write_bytes(b"# B\n\n\xff\xfe\n")

    code = cli.main(["scan", str(tmp_path), "--format", "json"])
    captured = capsys.readouterr()

    assert code == 0
    assert "docsentinel: WARNING: skipped b.md: not valid UTF-8" in captured.err.splitlines()
    assert "DS100" not in captured.out


def test_non_utf8_document_with_root_escape_never_exits_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli logging: verifies a DS116 root escape hidden behind an invalid byte still fails the gate.

    Scenario:
        Given the only document holds a root-escaping link, a dangling link and one 0xFF byte
        When ``docsentinel scan`` runs with the default text format
        Then it exits 1 and the report names the document with a DS100 error.

    Boundaries:
        - Focus: regression for security review H1 (fail-open gate)
        - Fixtures/params: tmp_path, capsys
        - Scope: one in-process CLI call

    On failure, first check:
        - whether DS100 is still emitted for an undecodable document
    """
    (tmp_path / "evil.md").write_bytes(b"# E\n\n[x](../../../../etc/passwd)\n[y](gone.md)\n\xff\n")

    code = cli.main(["scan", str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    assert "DS100" in out and "evil.md" in out
    assert "Blocking findings: 1" in out


@pytest.mark.skipif(os.name == "nt", reason="'[' and ']' file names are POSIX-only in this test")
def test_legacy_workflow_command_in_file_name_never_reaches_stderr_or_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] cli logging: verifies a file name holding ``##[`` reaches neither stderr nor the report verbatim.

    Scenario:
        Given a non-UTF-8 document named ``##[set-output name=x]pwn.md``
        When ``docsentinel scan -q`` runs with the text format and with the github format
        Then neither stderr nor stdout contains ``##[``; both show the rewritten ``##\\[``.

    Boundaries:
        - Focus: security review M2 (GitHub legacy command injection) for log lines and report sinks
        - Fixtures/params: tmp_path, capsys
        - Scope: two in-process CLI calls

    On failure, first check:
        - the ``##[`` rewrite in telemetry.filters._neutralize_controls
    """
    (tmp_path / "##[set-output name=x]pwn.md").write_bytes(b"\xff")

    for report_format in ("text", "github"):
        code = cli.main(["scan", str(tmp_path), "-q", "--format", report_format])
        captured = capsys.readouterr()

        assert code == 1
        assert "##[" not in captured.err and "##[" not in captured.out
        assert "skipped ##\\[set-output name=x]pwn.md: not valid UTF-8" in captured.err
        assert "##\\[set-output" in captured.out


def test_baseline_records_ds100_for_non_utf8_document(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] cli logging: verifies ``docsentinel baseline`` records the DS100 finding of a non-UTF-8 document.

    Scenario:
        Given a document with one dangling link and a non-UTF-8 document
        When ``docsentinel baseline --output`` runs
        Then it exits 0, warns once about the skipped document and records both the DS100 and DS101
            fingerprints, and a later scan with that baseline exits 0.

    Boundaries:
        - Focus: the baseline command goes through engine.scan; DS100's fixed message keeps its fingerprint stable
        - Fixtures/params: tmp_path (inline documents), capsys
        - Scope: one in-process CLI call

    On failure, first check:
        - Whether cli._run_baseline still calls engine.scan
    """
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.md").write_text("# A\n\n[x](missing.md)\n", encoding="utf-8")
    (root / "b.md").write_bytes(b"# B\n\n\xff\xfe\n")
    output = tmp_path / "baseline.json"

    code = cli.main(["baseline", str(root), "--output", str(output)])
    err = capsys.readouterr().err

    assert code == 0
    assert [line for line in err.splitlines() if line.startswith("docsentinel: WARNING")] == [
        "docsentinel: WARNING: skipped b.md: not valid UTF-8"
    ]
    fingerprints = sorted(json.loads(output.read_text(encoding="utf-8"))["fingerprints"])
    assert [entry.split(":", 2)[:2] for entry in fingerprints] == [["DS100", "b.md"], ["DS101", "a.md"]]

    (root / "docsentinel.toml").write_text('baseline = "../baseline.json"\n', encoding="utf-8")
    scan_code = cli.main(["scan", str(root), "--format", "json"])
    capsys.readouterr()
    assert scan_code == 0  # the recorded DS100 fingerprint suppresses the finding on the next scan
