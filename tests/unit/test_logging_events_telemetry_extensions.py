"""Unit tests for the log lines of report extensions and classification (``docs/specs/logging.md``).

``telemetry/extensions.py`` logs the admitted extensions once per resolution at ``INFO``
(``report extensions: <specs> (python gate on|off)``), the hook call counts once per render
at ``DEBUG``, and one ``WARNING`` when the fault-event guard disables a failing extension.
``telemetry/classify.py`` logs one ``DEBUG`` record per finding of an unmapped rule code.
``telemetry/builtin/domain.py`` and ``document_stats.py`` log at ``DEBUG`` only. A refusal
(``ExtensionError``) is a user fault the CLI logs once, so it is never logged where raised.
Extension output values never reach a record; only specs and names do.
"""

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import docsentinel
from docsentinel.config import Config
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.reporting import render
from docsentinel.telemetry.builtin.domain import domain_table
from docsentinel.telemetry.classify import UNMAPPED_FAULT_CLASS, classify
from docsentinel.telemetry.extensions import (
    EventHookGuard,
    ExtensionError,
    admit_extensions,
    resolve_extensions,
)
from docsentinel.telemetry.model import ReportModel

ESC = chr(0x1B)
_EXTENSIONS = "docsentinel.telemetry.extensions"
_CLASSIFY = "docsentinel.telemetry.classify"
_DOMAIN = "docsentinel.telemetry.builtin.domain"
_STATS = "docsentinel.telemetry.builtin.document_stats"
#: A value only extension output carries; it must never reach a log record.
_MARKER = "extension-output-value-7f3a"


def _records(caplog: pytest.LogCaptureFixture, name: str, level: int) -> list[str]:
    """Return the messages ``name`` logged at exactly ``level``, in order."""
    return [record.getMessage() for record in caplog.records if record.name == name and record.levelno == level]


def _problems(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return every ``WARNING`` or higher record from a ``docsentinel`` logger."""
    return [r for r in caplog.records if r.name.startswith("docsentinel") and r.levelno >= logging.WARNING]


def _result() -> ScanResult:
    """Build a tiny scan result: two documents, one finding on b.md."""
    return ScanResult(
        profile="fast",
        documents=(Document("a.md", 1), Document("b.md", 2048)),
        findings=(Finding(rule="DS101", path="b.md", message="dangling link -> x.md", severity="error", line=2),),
        enabled_rules=("DS101",),
        pending=(),
    )


def test_resolve_builtin_extensions_logs_one_info_line(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    """
    [Unit] extensions logging: verifies admitted builtin extensions are logged once at INFO with the gate state.

    Scenario:
        Given builtin:domain from the config and builtin:document_stats from the invoker
        When the extensions are resolved with the python gate closed
        Then exactly one INFO line lists both specs in order with ``python gate off``.

    Boundaries:
        - Focus: the operation-start INFO line of ``resolve_extensions``
        - Fixtures/params: caplog, tmp_path (origin-check anchor only)
        - Scope: resolve_extensions

    On failure, first check:
        - ``_log_admitted`` in ``telemetry/extensions.py``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    resolve_extensions(
        ("builtin:document_stats",),
        config=Config(telemetry_extensions=("builtin:domain",)),
        allow_python=False,
        root=tmp_path,
        cwd=tmp_path,
    )

    assert _records(caplog, _EXTENSIONS, logging.INFO) == [
        "report extensions: builtin:domain, builtin:document_stats (python gate off)"
    ]
    assert "resolving report extensions: 1 from config, 1 from the invoker" in _records(
        caplog, _EXTENSIONS, logging.DEBUG
    )


def test_resolve_with_gate_open_reports_gate_on(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    """
    [Unit] extensions logging: verifies the INFO line says ``python gate on`` when the invoker opened the gate.

    Scenario:
        Given one builtin spec and ``allow_python=True``
        When the extensions are resolved
        Then the INFO line ends with ``(python gate on)``.

    Boundaries:
        - Focus: gate state in the INFO line
        - Fixtures/params: caplog, tmp_path
        - Scope: resolve_extensions (no python: spec, so nothing is imported)

    On failure, first check:
        - the ``allow_python`` argument passed to ``_log_admitted``
    """
    caplog.set_level(logging.INFO, logger="docsentinel")

    resolve_extensions(("builtin:domain",), config=Config(), allow_python=True, root=tmp_path, cwd=tmp_path)

    assert _records(caplog, _EXTENSIONS, logging.INFO) == ["report extensions: builtin:domain (python gate on)"]


def test_no_extensions_logs_no_info_line(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    """
    [Unit] extensions logging: verifies an empty resolution logs at DEBUG only (edge case).

    Scenario:
        Given no configured and no invoker specs
        When the extensions are resolved
        Then no INFO line is logged and DEBUG says ``report extensions: none``.

    Boundaries:
        - Focus: a plain run stays quiet at INFO
        - Fixtures/params: caplog, tmp_path
        - Scope: resolve_extensions

    On failure, first check:
        - the empty-registry branch of ``_log_admitted``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    resolve_extensions((), config=Config(), allow_python=False, root=tmp_path, cwd=tmp_path)

    assert _records(caplog, _EXTENSIONS, logging.INFO) == []
    assert "report extensions: none" in _records(caplog, _EXTENSIONS, logging.DEBUG)


def test_refused_spec_is_not_logged_where_raised(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    """
    [Unit] extensions logging: verifies a refused spec raises without any record (the CLI logs it once).

    Scenario:
        Given an unknown builtin spec carrying an escape character
        When the extensions are resolved
        Then ExtensionError is raised and no INFO, WARNING or ERROR record is written.

    Boundaries:
        - Focus: user faults that abort are not logged at the raise site (spec §3)
        - Fixtures/params: caplog, tmp_path
        - Scope: resolve_extensions

    On failure, first check:
        - whether a log call was added on a raise path of ``resolve_extensions``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(ExtensionError):
        resolve_extensions(("builtin:nope" + ESC,), config=Config(), allow_python=False, root=tmp_path, cwd=tmp_path)

    assert [r for r in caplog.records if r.name == _EXTENSIONS and r.levelno >= logging.INFO] == []


def test_hook_calls_logged_once_with_counts_and_no_values(caplog: pytest.LogCaptureFixture):
    """
    [Unit] extensions logging: verifies hook calls are counted per hook in one DEBUG line without output values.

    Scenario:
        Given an extension with run, document and problem hooks returning a marker value
        When a report context with two documents and one problem is built
        Then one DEBUG line reports run=1, document=2, problem=1 and no record holds the marker.

    Boundaries:
        - Focus: no per-call records; counts at the end; names only
        - Fixtures/params: caplog
        - Scope: ReportModel.build -> apply_report_hooks

    On failure, first check:
        - the ``calls`` counter in ``apply_report_hooks``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    hooks: dict[str, Any] = {
        "provide_run": lambda model: {"v": _MARKER},
        "provide_document": lambda doc, model: {"v": _MARKER},
        "provide_problem": lambda problem, doc, model: {"v": _MARKER},
    }
    loaded = admit_extensions([SimpleNamespace(name="calc", **hooks)])

    ReportModel.build(_result(), Config(), extensions=loaded)

    lines = [m for m in _records(caplog, _EXTENSIONS, logging.DEBUG) if m.startswith("report extension hooks")]
    assert lines == [
        "report extension hooks over 2 document(s): calc.provide_run=1, calc.provide_document=2, calc.provide_problem=1"
    ]
    assert "admitted 1 extension object(s): calc" in _records(caplog, _EXTENSIONS, logging.DEBUG)
    assert all(_MARKER not in record.getMessage() for record in caplog.records)


def test_event_guard_warns_once_with_name_only(caplog: pytest.LogCaptureFixture):
    """
    [Unit] extensions logging: verifies a failing event-path hook logs one WARNING naming only the extension.

    Scenario:
        Given a problem hook that raises with a message holding a marker value
        When the event guard runs it three times
        Then exactly one WARNING names the extension and the hook, and no record holds the marker.

    Boundaries:
        - Focus: caught-and-continued extension failure is WARNING (spec §3), once per extension
        - Fixtures/params: caplog
        - Scope: EventHookGuard.problem_ext

    On failure, first check:
        - the ``except ExtensionError`` branch of ``EventHookGuard.problem_ext``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    def broken(problem: Any, doc: Any, model: Any):
        """Fail with a message carrying extension data."""
        raise RuntimeError(_MARKER)

    guard = EventHookGuard(admit_extensions([SimpleNamespace(name="bad", provide_problem=broken)]), warn=lambda m: None)
    for _ in range(3):
        guard.problem_ext({"rule": "DS101"}, {"path": "a.md"}, {})

    assert _records(caplog, _EXTENSIONS, logging.WARNING) == [
        "extension bad disabled for fault events after its provide_problem hook failed"
    ]
    assert all(_MARKER not in record.getMessage() for record in caplog.records)


def test_unmapped_rule_logs_debug_per_finding(caplog: pytest.LogCaptureFixture):
    """
    [Unit] classify logging: verifies an unmapped rule code logs one WARNING per code and still classifies.

    Scenario:
        Given three findings of rule DS999 and one of DS998, none with a fault-class row
        When each is classified
        Then each is ``unmapped``, one DEBUG is logged per finding and nothing at WARNING+.

    Boundaries:
        - Focus: DEBUG for a coped-with missing table row (owner decision: not a WARNING)
        - Fixtures/params: caplog
        - Scope: classify

    On failure, first check:
        - ``_fault_class`` in ``telemetry/classify.py``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    codes = ("DS999", "DS999", "DS999", "DS998")
    labels = [classify(Finding(rule=code, path="a.md", message="m"), Config()) for code in codes]

    assert {label.fault_class for label in labels} == {UNMAPPED_FAULT_CLASS}
    assert _records(caplog, _CLASSIFY, logging.WARNING) == []
    assert _records(caplog, _CLASSIFY, logging.DEBUG) == [
        "rule DS999 has no fault class; it is classified as unmapped",
        "rule DS999 has no fault class; it is classified as unmapped",
        "rule DS999 has no fault class; it is classified as unmapped",
        "rule DS998 has no fault class; it is classified as unmapped",
    ]


def test_unmapped_rule_code_is_neutralized(caplog: pytest.LogCaptureFixture):
    """
    [Unit] classify logging: verifies a hostile rule code reaches the DEBUG record neutralized (invalid input).

    Scenario:
        Given a finding whose rule code holds an escape character
        When it is classified
        Then the DEBUG record holds no raw escape character.

    Boundaries:
        - Focus: ``safe()`` on the untrusted rule code
        - Fixtures/params: caplog
        - Scope: classify

    On failure, first check:
        - the ``safe(code, 40)`` call in ``_fault_class``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    classify(Finding(rule="X" + ESC + "[31m", path="a.md", message="m"), Config())

    messages = _records(caplog, _CLASSIFY, logging.DEBUG)
    assert len(messages) == 1 and ESC not in messages[0]


def test_mapped_rule_logs_nothing(caplog: pytest.LogCaptureFixture):
    """
    [Unit] classify logging: verifies a shipped rule code is classified without any record.

    Scenario:
        Given a DS101 finding
        When it is classified
        Then no classify record is logged.

    Boundaries:
        - Focus: classify stays silent per finding on the normal path
        - Fixtures/params: caplog
        - Scope: classify

    On failure, first check:
        - whether a per-finding log call was added to ``classify``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    classify(Finding(rule="DS101", path="a.md", message="m"), Config())

    assert [r for r in caplog.records if r.name == _CLASSIFY] == []


def test_domain_table_build_logged_at_debug(caplog: pytest.LogCaptureFixture):
    """
    [Unit] domain logging: verifies building a domain table logs its entry count and enabled state at DEBUG.

    Scenario:
        Given a fresh Config with builtin:domain and two telemetry_domains entries
        When its table is built and two paths are looked up
        Then exactly one DEBUG line reports 2 entries and ``builtin:domain on``.

    Boundaries:
        - Focus: once-per-Config DEBUG line, no per-path records
        - Fixtures/params: caplog
        - Scope: domain_table

    On failure, first check:
        - ``_build`` in ``telemetry/builtin/domain.py``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    config = Config(
        telemetry_extensions=("builtin:domain",),
        telemetry_domains=(("agent/**", "agent"), ("**", "docs")),
    )

    table = domain_table(config)
    table.domain("agent/a.md")
    table.domain("b.md")

    assert _records(caplog, _DOMAIN, logging.DEBUG) == ["domain table built: 2 entries, builtin:domain on"]


def test_document_stats_logs_selection_count(caplog: pytest.LogCaptureFixture, tmp_path: Path):
    """
    [Unit] document_stats logging: verifies the run hook logs how many worst documents it selected.

    Scenario:
        Given builtin:document_stats and a result with one document holding a problem
        When the report context is built
        Then one DEBUG line reports 1 selected document.

    Boundaries:
        - Focus: one DEBUG per render, never per document
        - Fixtures/params: caplog, tmp_path
        - Scope: DocumentStatsExtension.provide_run

    On failure, first check:
        - ``provide_run`` in ``telemetry/builtin/document_stats.py``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    loaded = resolve_extensions(
        ("builtin:document_stats",), config=Config(), allow_python=False, root=tmp_path, cwd=tmp_path
    )

    ReportModel.build(_result(), Config(), extensions=loaded)

    assert _records(caplog, _STATS, logging.DEBUG) == ["document_stats: 1 worst document(s) selected"]


def test_normal_scan_and_render_with_extensions_has_no_problem_records(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
):
    """
    [Unit] telemetry logging: verifies a normal scan and render with both builtins logs no WARNING or ERROR.

    Scenario:
        Given a tiny inline document with one dangling link
        When it is scanned and rendered as json with builtin:domain and builtin:document_stats
        Then no docsentinel record is at WARNING or above.

    Boundaries:
        - Focus: the normal path stays free of problem records
        - Fixtures/params: caplog, tmp_path (one inline file)
        - Scope: docsentinel.scan + reporting.render

    On failure, first check:
        - any WARNING/ERROR call added in the telemetry modules
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n\nSee [x](missing.md).\n", encoding="utf-8")

    result = docsentinel.scan(tmp_path)
    render(result, "json", config=Config(), root=tmp_path, extensions=("builtin:domain", "builtin:document_stats"))

    assert result.findings
    assert _problems(caplog) == []
