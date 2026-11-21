"""Unit tests for the log lines of the report template core (``docs/specs/logging.md``).

``telemetry/loader.py`` logs at ``DEBUG`` which template was resolved, from where and its
size, and how many templates a listing found; ``telemetry/engine.py`` logs one ``DEBUG``
line per render with the output size and the steps used; ``telemetry/model.py`` logs one
``DEBUG`` line per context build with document and problem counts. A ``TemplateError`` is
a user fault the CLI logs once, so it is never logged where it is raised.
``telemetry/filters.py`` is the bottom layer and never logs.
"""

import logging
from pathlib import Path

import pytest

from docsentinel.config import Config
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.telemetry import loader
from docsentinel.telemetry.engine import render_template
from docsentinel.telemetry.filters import TemplateError
from docsentinel.telemetry.loader import (
    PACKAGED_TEMPLATES_DIR,
    available_templates,
    load_named_template,
    load_template,
    validate_template,
)
from docsentinel.telemetry.model import ReportModel

ESC = chr(0x1B)
_MINI = '{"template_version": 1, "name": "mini", "type": "text", "lines": []}'
_LOADER = "docsentinel.telemetry.loader"
_ENGINE = "docsentinel.telemetry.engine"
_MODEL = "docsentinel.telemetry.model"


def _messages(caplog: pytest.LogCaptureFixture, name: str) -> list[str]:
    """Return the messages ``name`` logged, in order."""
    return [record.getMessage() for record in caplog.records if record.name == name]


def _result() -> ScanResult:
    """Build a tiny scan result: two documents, one finding on b.md, one outside the inventory."""
    return ScanResult(
        profile="fast",
        documents=(Document("a.md", 1), Document("b.md", 2)),
        findings=(
            Finding(rule="DS101", path="b.md", message="dangling link -> x.md", severity="error", line=2),
            Finding(rule="DS102", path="gone.md", message="stray HTML comment", severity="warning", line=1),
        ),
        enabled_rules=("DS101", "DS102"),
        pending=(),
    )


def test_packaged_template_load_logs_origin_and_size(caplog: pytest.LogCaptureFixture):
    """
    [Unit] loader logging: verifies a packaged template load logs its name, type, origin and byte size.

    Scenario:
        Given the packaged ``text`` template
        When it is loaded by name twice (the second time from the cache)
        Then each load logs one DEBUG line naming ``packaged`` and the file's byte size.

    Boundaries:
        - Focus: the ``_log_loaded`` call in ``_load_by_name`` (outside the lru_cache)
        - Fixtures/params: caplog
        - Scope: packaged template resolution

    On failure, first check:
        - Whether the log call moved inside ``_load_packaged_cached`` (it would vanish on a cache hit)
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    size = (PACKAGED_TEMPLATES_DIR / "text.json").stat().st_size

    load_named_template("text")
    load_named_template("text")

    expected = f"template text (text) resolved from packaged text: {size} bytes"
    assert _messages(caplog, _LOADER) == [expected, expected]
    assert all(record.levelno == logging.DEBUG for record in caplog.records if record.name == _LOADER)


def test_directory_template_load_logs_report_templates_dir(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] loader logging: verifies a ``report_templates_dir`` template logs that origin and its UTF-8 size.

    Scenario:
        Given a scan root with ``templates/mini.json``
        When ``mini`` is loaded by name with ``templates_dir="templates"``
        Then one DEBUG line names ``report_templates_dir``, the configured relative path and its byte size.

    Boundaries:
        - Focus: the directory branch of ``_load_by_name``
        - Fixtures/params: tmp_path, caplog
        - Scope: one temp template file

    On failure, first check:
        - ``_utf8_size`` and the ``configured`` label passed to ``_log_loaded``
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "mini.json").write_text(_MINI, encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    load_named_template("mini", root=tmp_path, templates_dir="templates")

    assert _messages(caplog, _LOADER) == [
        f"template mini (text) resolved from report_templates_dir templates/mini.json: {len(_MINI)} bytes"
    ]


def test_path_mapping_and_configured_loads_log_their_origin(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] loader logging: verifies invoker paths, configured paths and mappings each log their origin.

    Scenario:
        Given a template file inside a scan root and the same template as a mapping
        When it is loaded as a command-line path, as a configured path and as a mapping
        Then three DEBUG lines name ``path``, ``configured path`` and ``mapping`` respectively.

    Boundaries:
        - Focus: the three non-name branches of ``load_template``
        - Fixtures/params: tmp_path, caplog
        - Scope: one temp template file

    On failure, first check:
        - Which ``load_template`` branch returns before calling ``_log_loaded``
    """
    file = tmp_path / "mini.json"
    file.write_text(_MINI, encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    load_template(str(file))
    load_template("mini.json", root=tmp_path, from_config=True)
    load_template({"template_version": 1, "name": "mini", "type": "text", "lines": []})

    assert _messages(caplog, _LOADER) == [
        f"template mini (text) resolved from path {file}: {len(_MINI)} bytes",
        f"template mini (text) resolved from configured path mini.json: {len(_MINI)} bytes",
        "template mini (text) resolved from mapping <mapping>: 0 bytes",
    ]


def test_hostile_template_path_is_neutralized_in_the_log(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] loader logging: verifies an untrusted template path cannot carry a terminal escape into a log line.

    Scenario:
        Given a template file whose name holds an ESC control character
        When it is loaded as a path
        Then the DEBUG line holds no raw ESC and still names the file.

    Boundaries:
        - Focus: ``safe()`` on the location in ``_log_loaded``
        - Fixtures/params: tmp_path, caplog
        - Scope: one temp template file

    On failure, first check:
        - Whether ``_log_loaded`` still routes ``location`` through ``safe``
    """
    file = tmp_path / f"evil{ESC}[31m.json"
    file.write_text(_MINI, encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    load_template(str(file))

    (message,) = _messages(caplog, _LOADER)
    assert ESC not in message
    assert "evil" in message and "[31m.json" in message


def test_template_errors_are_not_logged_where_raised(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] loader logging: verifies a refused or invalid template raises without any log record.

    Scenario:
        Given an unknown name, a configured path escaping the root, and a template file with invalid JSON
        When each is loaded
        Then each raises ``TemplateError`` and the loader logs nothing (the CLI logs the error once).

    Boundaries:
        - Focus: logging.md §3 "a user mistake that aborts the run is logged once by the CLI"
        - Fixtures/params: tmp_path, caplog
        - Scope: three failing loads

    On failure, first check:
        - Whether a log call was added before a ``raise TemplateError`` in the loader
    """
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(TemplateError, match="unknown template"):
        load_named_template("no-such-template")
    with pytest.raises(TemplateError, match="escapes the scan root"):
        load_template("../outside.json", root=tmp_path, from_config=True)
    with pytest.raises(TemplateError, match="invalid JSON"):
        load_template(str(bad))

    assert caplog.records == []


def test_available_templates_logs_counts(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] loader logging: verifies template listing logs packaged, directory and skipped counts.

    Scenario:
        Given a templates directory holding ``mini.json`` and one non-template file
        When the templates are listed without and with that directory
        Then the first DEBUG line counts the packaged templates only and the second adds 1 found and 1 skipped.

    Boundaries:
        - Focus: both return paths of ``available_templates``
        - Fixtures/params: tmp_path, caplog
        - Scope: a temp directory listing

    On failure, first check:
        - The ``skipped`` counter in the listing loop
    """
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "mini.json").write_text(_MINI, encoding="utf-8")
    (templates / "notes.txt").write_text("x", encoding="utf-8")
    packaged = len(loader.packaged_template_names())
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    available_templates()
    available_templates(tmp_path, "templates")

    assert _messages(caplog, _LOADER) == [
        f"available templates: {packaged} packaged",
        f"available templates: {packaged} packaged, 1 in report_templates_dir templates (1 other entries skipped)",
    ]


def test_render_logs_once_with_size_and_steps(caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a render logs exactly one DEBUG line with output size and steps used.

    Scenario:
        Given a text template with a block loop over three items
        When it is rendered
        Then exactly one DEBUG line names the template, its output character count and a positive step count.

    Boundaries:
        - Focus: ``_rendered`` in ``render_template``; nothing logged per node or loop item
        - Fixtures/params: caplog
        - Scope: an in-memory render

    On failure, first check:
        - Whether a log call was added inside ``_nodes``/``_loop``/``_interpolate``
    """
    template = validate_template(
        {
            "template_version": 1,
            "name": "t",
            "type": "text",
            "lines": [
                {
                    "type": "loop",
                    "over": "pending",
                    "as": "code",
                    "body": [{"type": "line", "text": "{code|neutralize}", "variables_used": ["code"]}],
                }
            ],
        }
    )
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    output = render_template(template, {"pending": ["a", "b", "c"]})

    (record,) = [record for record in caplog.records if record.name == _ENGINE]
    assert record.levelno == logging.DEBUG
    prefix = f"rendered template t (text, origin mapping): {len(output)} characters, "
    message = record.getMessage()
    assert message.startswith(prefix)
    steps = int(message.removeprefix(prefix).removesuffix(" steps"))
    assert steps > 0


def test_render_failure_is_not_logged(caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a render error raises without a log record.

    Scenario:
        Given a json template reading a variable the context lacks
        When it is rendered
        Then ``TemplateError`` is raised and the engine logs nothing (reporting/CLI handle it).

    Boundaries:
        - Focus: no log on the raise path of ``render_template``
        - Fixtures/params: caplog
        - Scope: an in-memory render

    On failure, first check:
        - Whether ``_rendered`` was moved before the renderer returns
    """
    template = validate_template(
        {"template_version": 1, "name": "t", "type": "json", "schema_version": 1, "body": {"$var": "profile"}}
    )
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(TemplateError, match="not present"):
        render_template(template, {})

    assert caplog.records == []


def test_model_build_logs_counts_once(caplog: pytest.LogCaptureFixture):
    """
    [Unit] model logging: verifies a context build logs one DEBUG line with document and problem counts.

    Scenario:
        Given two inventory documents, one error finding on b.md and one warning on a path outside the inventory
        When the report model is built
        Then one DEBUG line counts 3 documents (2 with problems, 1 outside the inventory), 2 problems, 1 blocking.

    Boundaries:
        - Focus: the summary log at the end of ``ReportModel.build``
        - Fixtures/params: caplog
        - Scope: in-memory model building

    On failure, first check:
        - The outside-inventory arithmetic in the log call
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    ReportModel.build(_result(), Config())

    assert _messages(caplog, _MODEL) == [
        "report model built: 3 documents (2 with problems, 1 outside the inventory), 2 problems, 1 blocking"
    ]


def test_model_build_of_an_empty_result_logs_zero_counts(caplog: pytest.LogCaptureFixture):
    """
    [Unit] model logging: verifies an empty scan result still logs its (zero) counts.

    Scenario:
        Given a scan result with no documents and no findings
        When the report model is built
        Then the DEBUG line counts zero everywhere.

    Boundaries:
        - Focus: the empty edge case of the build summary
        - Fixtures/params: caplog
        - Scope: in-memory model building

    On failure, first check:
        - Whether the log call assumes a non-empty inventory
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    ReportModel.build(ScanResult(profile="fast", documents=(), findings=(), enabled_rules=(), pending=()), Config())

    assert _messages(caplog, _MODEL) == [
        "report model built: 0 documents (0 with problems, 0 outside the inventory), 0 problems, 0 blocking"
    ]


@pytest.mark.parametrize("name", ["text", "json", "github"])
def test_normal_render_emits_no_warning_or_error(name: str, caplog: pytest.LogCaptureFixture):
    """
    [Unit] telemetry core logging: verifies a normal load, build and render logs nothing at WARNING or above.

    Scenario:
        Given a packaged template and a tiny scan result
        When the template is loaded, the context built and the report rendered
        Then every record from the telemetry core is DEBUG.

    Boundaries:
        - Focus: level discipline of the loader, model and engine on the happy path
        - Fixtures/params: parametrized over three packaged templates; caplog
        - Scope: in-memory pipeline

    On failure, first check:
        - Which logger emitted the WARNING/ERROR record and whether its event is really a user fault
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    template = load_named_template(name)
    render_template(template, ReportModel.build(_result(), Config()))

    assert [record for record in caplog.records if record.levelno >= logging.WARNING] == []
    assert {record.name for record in caplog.records} >= {_LOADER, _MODEL, _ENGINE}
