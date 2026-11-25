"""Unit tests for the log lines of the engine and core modules (``docs/specs/logging.md``).

The engine logs the stage lines at ``INFO``: the discovery total with the skipped count,
the rule plan (selected, evaluated, opt-in rules that are off) and, when a baseline is
used, the fingerprint and suppression counts. Per-analyzer timings, config loading,
link-root resolution, per-file discovery skips and the standard/deep corpus sizes are
``DEBUG``. ``WARNING`` is reserved for user input DocSentinel coped with: a missing
baseline file, an unconfirmed deep profile or one whose dependencies are missing, an
unreadable or non-UTF-8 document (skipped by the analyzers, reported as DS100), an opt-in rule selected by its exact code
while its option is unset, and a symlinked or non-``.py`` ``docsig_paths`` entry. A
failing spaCy import or model load is a ``DEBUG`` record only: the ``RuntimeError`` it
raises is logged once by the CLI. No log record carries document content or a raw
control character.
"""

import json
import logging
import os
import types
from pathlib import Path

import pytest

from docsentinel import engine, scan
from docsentinel.baseline import fingerprint, load_baseline
from docsentinel.code_discovery import discover_python
from docsentinel.config import Config, load_config
from docsentinel.link_root import resolve_invoker_link_root, resolve_link_root
from docsentinel.mining import nlp
from docsentinel.mining.nlp import load_pipeline
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.reporting import render

ESC = chr(0x1B)
#: A word placed in document content; no log record may ever contain it.
_MARKER = "PRIVATECONTENTMARKER"


def _records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the records logged under the ``docsentinel`` logger, in order."""
    return [record for record in caplog.records if record.name.startswith("docsentinel")]


def _messages(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    """Return the messages DocSentinel logged at exactly ``level``."""
    return [record.getMessage() for record in _records(caplog) if record.levelno == level]


def _problems(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the WARNING-or-above messages DocSentinel logged."""
    return [record.getMessage() for record in _records(caplog) if record.levelno >= logging.WARNING]


def test_scan_logs_discovery_total_with_skipped_symlink_and_excluded_directory(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] engine logging: verifies the INFO discovery line counts a symlink and an excluded directory.

    Scenario:
        Given a scan root with one Markdown file, a symlink to it and an excluded .venv directory
        When scan runs
        Then one INFO line reports 1 document and 2 skipped entries, and DEBUG names each skip reason.

    Boundaries:
        - Focus: discovery_with_skips counting and the engine discovery INFO line
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Whether discover_with_skips still counts symlinks and excluded directories
        - Whether the engine still logs the discovery line after discovery
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "b.md").symlink_to(tmp_path / "a.md")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "c.md").write_text("# C\n", encoding="utf-8")

    result = scan(tmp_path, config=Config())

    assert [document.path for document in result.documents] == ["a.md"]
    info = [message for message in _messages(caplog, logging.INFO) if message.startswith("discovered ")]
    assert info == [f"discovered 1 documents under {tmp_path.resolve()} (2 skipped: symlinks/excluded, 0 unreadable)"]
    debug = _messages(caplog, logging.DEBUG)
    assert "skipped b.md: symlinked file" in debug
    assert "skipped .venv: excluded directory" in debug


def test_scan_logs_rule_plan_with_opt_in_rules_off(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies the INFO rule plan names selected, evaluated and opt-in-off rules.

    Scenario:
        Given a default fast configuration where the opt-in policies are unset
        When scan runs
        Then one INFO line gives the selected and evaluated counts and lists DS110 with its option.

    Boundaries:
        - Focus: engine._log_rule_plan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Whether opt_in_off is still computed from opt_in_satisfied before the analyzers run
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")

    result = scan(tmp_path, config=Config())

    plan = [message for message in _messages(caplog, logging.INFO) if message.startswith("profile=")]
    assert len(plan) == 1
    assert plan[0].startswith(
        f"profile=fast: {len(result.enabled_rules)} rules selected, {result.rules_evaluated} evaluated; opt-in off: "
    )
    assert "DS110 (require_fence_languages)" in plan[0]


def test_rule_plan_with_no_opt_in_rule_active_says_none(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies the rule plan prints "none" when no opt-in rule is off.

    Scenario:
        Given a configuration selecting only DS101
        When scan runs
        Then the rule plan reads "1 rules selected, 1 evaluated; opt-in off: none".

    Boundaries:
        - Focus: the empty opt_in_off edge of engine._log_rule_plan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - The "none" fallback of the joined opt-in list
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")

    scan(tmp_path, config=Config(select=("DS101",)))

    assert "profile=fast: 1 rules selected, 1 evaluated; opt-in off: none" in _messages(caplog, logging.INFO)


def test_exactly_selected_opt_in_rule_without_option_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies an opt-in rule selected by exact code with its option unset warns.

    Scenario:
        Given select = ["DS110"] and require_fence_languages left unset
        When scan runs
        Then exactly one WARNING says DS110 evaluates nothing until require_fence_languages is set.

    Boundaries:
        - Focus: the WARNING branch of engine._log_rule_plan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan; findings are unchanged (none)

    On failure, first check:
        - Whether the warning still requires the exact code in Config.select
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    (tmp_path / "a.md").write_text("```\ncode\n```\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(select=("DS110",)))

    assert result.findings == ()
    assert _problems(caplog) == ["DS110 is selected but evaluates nothing until require_fence_languages is set"]


def test_prefix_selected_opt_in_rule_does_not_warn(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a prefix selection covering an opt-in rule does not warn.

    Scenario:
        Given select = ["DS1"], which covers DS110 without naming it
        When scan runs
        Then no WARNING is logged.

    Boundaries:
        - Focus: the exact-code edge of engine._log_rule_plan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Whether the warning matches prefixes instead of exact codes
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")

    scan(tmp_path, config=Config(select=("DS1",)))

    assert _problems(caplog) == []


def test_scan_logs_per_analyzer_debug_timing(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies one DEBUG line per analyzer with its finding count.

    Scenario:
        Given a document with one dangling link and select = ["DS101"]
        When scan runs
        Then a DEBUG line "DS101: 1 findings in <s>s" is logged.

    Boundaries:
        - Focus: the per-analyzer loop of engine.scan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Whether the analyzer loop still materialises and times each analyzer
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text("[x](missing.md)\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(select=("DS101",)))

    assert len(result.findings) == 1
    timing = [message for message in _messages(caplog, logging.DEBUG) if message.startswith("DS101: ")]
    assert len(timing) == 1
    assert timing[0].startswith("DS101: 1 findings in ")
    assert timing[0].endswith("s")


def test_scan_logs_baseline_suppression_totals(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies the INFO baseline line reports fingerprints and suppressed findings.

    Scenario:
        Given a baseline holding the fingerprint of the one dangling-link finding plus one stale entry
        When scan runs with that baseline
        Then one INFO line reports 2 fingerprints and 1 finding suppressed.

    Boundaries:
        - Focus: the baseline branch of engine.scan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Whether the suppressed count is taken before and after filter_baselined
    """
    caplog.set_level(logging.INFO, logger="docsentinel")
    (tmp_path / "a.md").write_text("[x](missing.md)\n", encoding="utf-8")
    finding = scan(tmp_path, config=Config(select=("DS101",))).findings[0]
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"fingerprints": [fingerprint(finding), "DS101:old.md:000000000000"]}))
    caplog.clear()

    result = scan(tmp_path, config=Config(select=("DS101",), baseline="baseline.json"))

    assert result.findings == ()
    assert f"baseline {baseline}: 2 fingerprints, 1 findings suppressed" in _messages(caplog, logging.INFO)


def test_missing_baseline_file_warns_and_suppresses_nothing(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] baseline logging: verifies a configured baseline that does not exist logs one WARNING.

    Scenario:
        Given a baseline path that does not exist
        When load_baseline reads it
        Then it still returns an empty set and logs one WARNING naming the path.

    Boundaries:
        - Focus: the missing-file branch of baseline.load_baseline
        - Fixtures/params: tmp_path, caplog
        - Scope: one call

    On failure, first check:
        - Whether the missing-file branch still returns frozenset() before the warning text changed
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    missing = tmp_path / "nope.json"

    assert load_baseline(missing) == frozenset()
    assert _problems(caplog) == [f"baseline {missing} does not exist; no findings are suppressed"]


def test_deep_profile_without_dependencies_logs_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch):
    """
    [Unit] engine logging: verifies a confirmed deep profile without its dependencies logs one WARNING.

    Scenario:
        Given a confirmed deep profile and deep_ready() reporting False
        When scan runs
        Then it logs "deep profile skipped: dependencies unavailable" once at WARNING and nothing else at WARNING+.

    Boundaries:
        - Focus: the deep readiness branch of engine.scan (owner decision: WARNING)
        - Fixtures/params: tmp_path, caplog, monkeypatch
        - Scope: one scan

    On failure, first check:
        - Whether engine still calls deep_ready through its module attribute
    """
    monkeypatch.setattr(engine, "deep_ready", lambda: False)
    caplog.set_level(logging.INFO, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")

    scan(tmp_path, config=Config(profile="deep"))

    assert _problems(caplog) == [f"deep profile skipped: dependencies unavailable - {nlp.DEEP_EXTRA_HINT}"]
    assert _messages(caplog, logging.WARNING) == _problems(caplog)


def test_normal_scan_logs_no_problem_and_no_content(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a normal scan logs no WARNING/ERROR and never document content.

    Scenario:
        Given documents whose text holds a marker word, with findings, under default config
        When scan runs with DEBUG capture
        Then no record is WARNING or above and no record contains the marker.

    Boundaries:
        - Focus: every log call reached by a default fast scan
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Which logger name produced the offending record
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text(f"# A\n\n{_MARKER} see [b](b.md).\n", encoding="utf-8")
    (tmp_path / "b.md").write_text(f"# B\n\n{_MARKER} [gone](missing.md)\n", encoding="utf-8")

    result = scan(tmp_path, config=Config())

    assert result.findings
    assert _problems(caplog) == []
    assert all(_MARKER not in record.getMessage() for record in _records(caplog))


def test_hostile_skipped_file_name_is_neutralised(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] discovery logging: verifies a skipped file name with an escape character never reaches a record raw.

    Scenario:
        Given a symlinked file whose name embeds ESC
        When scan runs with DEBUG capture
        Then no record contains a raw ESC.

    Boundaries:
        - Focus: safe() on the per-skip DEBUG line of discovery
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Whether the discovery skip line still routes the path through safe()
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / f"x{ESC}[31m.md").symlink_to(tmp_path / "a.md")

    scan(tmp_path, config=Config())

    assert any("skipped x" in message for message in _messages(caplog, logging.DEBUG))
    assert all(ESC not in record.getMessage() for record in _records(caplog))


def test_load_config_logs_source_and_option_names(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] config logging: verifies load_config logs the file it loads and option names, not values.

    Scenario:
        Given a docsentinel.toml setting select, and an empty directory
        When load_config runs on each
        Then DEBUG names the file and "select", omits the value, and the empty one reports defaults.

    Boundaries:
        - Focus: config.load_config DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: two calls

    On failure, first check:
        - Whether the option-name line still logs names only
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    configured = tmp_path / "configured"
    configured.mkdir()
    (configured / "docsentinel.toml").write_text('select = ["DS1"]\n', encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()

    load_config(configured)
    load_config(empty)

    debug = _messages(caplog, logging.DEBUG)
    assert f"loading config {configured / 'docsentinel.toml'}" in debug
    assert "config options set: select" in debug
    assert f"no config file in {empty}; using defaults" in debug
    assert all("DS1" not in message for message in debug)
    assert _problems(caplog) == []


def test_link_root_resolution_logs_how_it_was_chosen(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] link_root logging: verifies DEBUG names the resolved link root and the method.

    Scenario:
        Given a repository holding .git with a docs subdirectory
        When resolve_link_root runs with "auto" and resolve_invoker_link_root with the repository
        Then DEBUG reports the .git ancestor for auto and the invoker override.

    Boundaries:
        - Focus: link_root.resolve_link_root and resolve_invoker_link_root DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: two calls

    On failure, first check:
        - Whether tmp_path lies under the home directory (the dotfiles guard)
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    repository = tmp_path / "repo"
    (repository / ".git").mkdir(parents=True)
    docs = repository / "docs"
    docs.mkdir()

    resolved = resolve_link_root(docs, Config())
    resolve_invoker_link_root(docs, repository)

    debug = _messages(caplog, logging.DEBUG)
    if resolved == repository:
        assert f"link root {repository} (auto: nearest .git ancestor)" in debug
    else:
        assert f"link root {docs} (auto: no trusted .git ancestor, scan root)" in debug
    assert f"link root {os.path.realpath(repository)} (invoker override)" in debug


def test_docsig_symlink_and_non_python_paths_warn_and_missing_path_does_not(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] code_discovery logging: verifies dropped user-named docsig paths warn and a missing one is DEBUG.

    Scenario:
        Given docsig_paths naming a symlink, a non-.py file, a missing path and a real .py file
        When discover_python runs
        Then only the .py file is returned, two WARNINGs name the symlink and the non-.py file,
        and the missing path is logged at DEBUG only.

    Boundaries:
        - Focus: the configured-entry skip branches of code_discovery.discover_python
        - Fixtures/params: tmp_path, caplog
        - Scope: one call

    On failure, first check:
        - Whether the default docsig path "src" being absent would now warn on every standard scan
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "real.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "link.py").symlink_to(tmp_path / "real.py")
    (tmp_path / "notes.txt").write_text("n\n", encoding="utf-8")
    config = Config(docsig_paths=("link.py", "notes.txt", "missing", "real.py"))

    found = discover_python(tmp_path, config)

    assert found == ((tmp_path / "real.py").resolve(),)
    assert _problems(caplog) == [
        "docsig path link.py is a symlink and is not checked",
        "docsig path notes.txt is not a .py file and is not checked",
    ]
    assert "docsig path missing does not exist; skipped" in _messages(caplog, logging.DEBUG)


def test_load_pipeline_logs_debug_when_spacy_import_fails(caplog: pytest.LogCaptureFixture, monkeypatch):
    """
    [Unit] nlp logging: verifies a failing spaCy import at run time logs DEBUG only (logged once upstream).

    Scenario:
        Given importlib.import_module raising ImportError for spacy
        When load_pipeline runs
        Then it still raises RuntimeError, logs one DEBUG naming the module and nothing at WARNING+.

    Boundaries:
        - Focus: the import except branch of nlp.load_pipeline
        - Fixtures/params: caplog, monkeypatch
        - Scope: one call

    On failure, first check:
        - Whether load_pipeline still imports spacy via nlp.importlib
    """
    def refuse(name: str):
        """Raise the ImportError a missing spacy install produces."""
        raise ImportError(f"no module named {name}", name=name)

    monkeypatch.setattr(nlp.importlib, "import_module", refuse)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(RuntimeError):
        load_pipeline()

    assert _problems(caplog) == []
    assert _messages(caplog, logging.DEBUG) == ["deep profile: spacy failed to import at run time: spacy"]


def test_load_pipeline_logs_debug_when_model_load_fails(caplog: pytest.LogCaptureFixture, monkeypatch):
    """
    [Unit] nlp logging: verifies a failing spaCy model load logs DEBUG only (logged once upstream).

    Scenario:
        Given a spacy stand-in whose load raises OSError
        When load_pipeline runs
        Then it still raises RuntimeError, logs a DEBUG naming the model and nothing at WARNING+.

    Boundaries:
        - Focus: the model-load except branch of nlp.load_pipeline
        - Fixtures/params: caplog, monkeypatch
        - Scope: one call

    On failure, first check:
        - Whether the except tuple still covers OSError
    """
    def broken_load(name: str):
        """Raise the OSError an unreadable model produces."""
        raise OSError("model data unreadable")

    stand_in = types.SimpleNamespace(load=broken_load)
    monkeypatch.setattr(nlp.importlib, "import_module", lambda name: stand_in)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(RuntimeError):
        load_pipeline()

    assert _problems(caplog) == []
    assert f"deep profile: spaCy model {nlp.MODEL_NAME} failed to load: OSError" in _messages(
        caplog, logging.DEBUG
    )


def test_corpus_model_logs_sizes_at_debug(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] standard corpus logging: verifies build_corpus_model logs corpus sizes at DEBUG only.

    Scenario:
        Given one document with two qualifying paragraphs
        When build_corpus_model runs
        Then DEBUG reports 1 document and 2 paragraphs and no record is INFO or above.

    Boundaries:
        - Focus: mining.corpus DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: one uncached call

    On failure, first check:
        - Whether the lru_cache returned a cached model (clear_corpus_cache first)
    """
    corpus = pytest.importorskip("docsentinel.mining.corpus")
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    text = "Alpha beta gamma delta epsilon zeta eta.\n\nTheta iota kappa lambda mu nu xi omicron.\n"
    (tmp_path / "a.md").write_text(text, encoding="utf-8")
    corpus.clear_corpus_cache()

    corpus.build_corpus_model(tmp_path, (Document("a.md", len(text)),))
    corpus.clear_corpus_cache()

    debug = _messages(caplog, logging.DEBUG)
    assert any(message.startswith("corpus model built: 1 documents, 2 paragraphs") for message in debug)
    assert all(record.levelno == logging.DEBUG for record in _records(caplog))


def test_render_logs_template_choice_at_debug(caplog: pytest.LogCaptureFixture):
    """
    [Unit] reporting logging: verifies render logs the chosen template at DEBUG and nothing louder.

    Scenario:
        Given a scan result with one finding
        When render runs with the packaged text template
        Then a DEBUG line names the template, its origin and the finding count.

    Boundaries:
        - Focus: reporting.render DEBUG lines
        - Fixtures/params: caplog
        - Scope: one call

    On failure, first check:
        - Whether the packaged text template still reports origin "packaged"
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    result = ScanResult(
        profile="fast",
        documents=(Document("a.md", 1),),
        findings=(Finding(rule="DS101", path="a.md", message="m", severity="error"),),
        enabled_rules=("DS101",),
        pending=(),
    )

    render(result, "text")

    assert "render: template text (packaged, text), 1 findings, strict=False" in _messages(caplog, logging.DEBUG)
    assert _problems(caplog) == []


def test_non_utf8_document_is_skipped_with_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a non-UTF-8 document is skipped with one WARNING and the scan continues.

    Scenario:
        Given a clean UTF-8 document and a document holding an invalid UTF-8 byte
        When scan runs
        Then the bad document stays in the inventory with exactly one DS100 error finding, one WARNING
            names it, and the INFO line counts it as unreadable.

    Boundaries:
        - Focus: the readability check of engine.scan (owner decision: skip + blocking DS100 finding)
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - ``_partition_readable`` in ``engine.py`` and the discovery INFO line format
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n\nClean text.\n", encoding="utf-8")
    (tmp_path / "b.md").write_bytes(b"# B\n\n" + _MARKER.encode("ascii") + b" \xff\n")

    result = scan(tmp_path, config=Config())

    assert [document.path for document in result.documents] == ["a.md", "b.md"]
    assert [(f.rule, f.path, f.severity, f.message) for f in result.findings if f.path == "b.md"] == [
        ("DS100", "b.md", "error", "unreadable document: not valid UTF-8")
    ]
    assert result.enabled_rules[0] == "DS100"
    assert _problems(caplog) == ["skipped b.md: not valid UTF-8"]
    info = [message for message in _messages(caplog, logging.INFO) if message.startswith("discovered ")]
    assert info == [f"discovered 2 documents under {tmp_path.resolve()} (0 skipped: symlinks/excluded, 1 unreadable)"]
    assert all(_MARKER not in record.getMessage() for record in _records(caplog))
    assert all(_MARKER not in finding.message for finding in result.findings)


def test_only_document_non_utf8_is_reported_as_ds100(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a scan whose only document is not UTF-8 reports it as DS100 (edge).

    Scenario:
        Given a single document encoded as Latin-1 with a non-ASCII character
        When scan runs on the directory and on the file itself
        Then both scans keep the document and report exactly one DS100 error, and log the skip WARNING.

    Boundaries:
        - Focus: the readability filter for directory and explicitly selected file scans
        - Fixtures/params: tmp_path, caplog
        - Scope: two scans

    On failure, first check:
        - that the filter runs after both the selected-file and the discovery branch
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    (tmp_path / "only.md").write_bytes("# Caf\u00e9\n".encode("latin-1"))

    for target in (tmp_path, tmp_path / "only.md"):
        result = scan(target, config=Config())
        assert [document.path for document in result.documents] == ["only.md"]
        assert [(finding.rule, finding.path, finding.severity) for finding in result.findings] == [
            ("DS100", "only.md", "error")
        ]

    assert _problems(caplog) == ["skipped only.md: not valid UTF-8", "skipped only.md: not valid UTF-8"]


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs POSIX non-root")
def test_unreadable_document_is_skipped_with_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies an unreadable (mode 000) document is skipped with one WARNING.

    Scenario:
        Given a readable document and a document whose permissions are removed
        When scan runs
        Then the unreadable document stays listed with a DS100 finding and the WARNING names the OS reason.

    Boundaries:
        - Focus: the OSError branch of the readability filter
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan; POSIX non-root only

    On failure, first check:
        - the OSError branch of ``_partition_readable`` (strerror or type name)
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    locked = tmp_path / "locked.md"
    locked.write_text("# Locked\n", encoding="utf-8")
    locked.chmod(0)
    try:
        result = scan(tmp_path, config=Config())
    finally:
        locked.chmod(0o600)

    assert [document.path for document in result.documents] == ["a.md", "locked.md"]
    assert [(finding.rule, finding.message, finding.value) for finding in result.findings if finding.rule == "DS100"] == [
        ("DS100", "unreadable document: cannot read it (Permission denied)", "cannot read it (Permission denied)")
    ]
    assert all(finding.path == "a.md" for finding in result.findings if finding.rule != "DS100")
    assert _problems(caplog) == ["skipped locked.md: cannot read it (Permission denied)"]


def test_unreadable_document_warning_falls_back_to_exception_type(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """
    [Unit] engine logging: verifies an OSError without strerror is named by its type in the skip WARNING.

    Scenario:
        Given a document whose read raises a bare OSError subclass
        When scan runs
        Then the WARNING names the exception type and the document is skipped.

    Boundaries:
        - Focus: the ``strerror or type name`` fallback
        - Fixtures/params: tmp_path, caplog, monkeypatch
        - Scope: one scan

    On failure, first check:
        - ``_validate_document`` is still the single read the check calls
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")

    def refuse(path: Path):
        """Raise an OSError subclass that carries no strerror."""
        raise BlockingIOError()

    monkeypatch.setattr(engine, "_validate_document", refuse)

    result = scan(tmp_path, config=Config())

    assert [document.path for document in result.documents] == ["a.md"]
    assert [finding.message for finding in result.findings] == ["unreadable document: cannot read it (BlockingIOError)"]
    assert _problems(caplog) == ["skipped a.md: cannot read it (BlockingIOError)"]


@pytest.mark.skipif(os.name == "nt", reason="control characters are not valid in Windows file names")
def test_skip_warning_neutralizes_hostile_filename(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies a hostile file name reaches the skip WARNING neutralized (invalid input).

    Scenario:
        Given a non-UTF-8 document whose name holds an ESC sequence and a newline
        When scan runs
        Then exactly one WARNING is logged and it holds neither raw character.

    Boundaries:
        - Focus: ``safe()`` on the skipped document path
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - the ``safe(document.path)`` call in ``_partition_readable``
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    (tmp_path / ("evil" + ESC + "[31m\nINFO forged.md")).write_bytes(b"\xfe\xff")

    result = scan(tmp_path, config=Config())

    assert len(result.documents) == 1
    assert [finding.rule for finding in result.findings] == ["DS100"]
    problems = _problems(caplog)
    assert len(problems) == 1
    assert problems[0].startswith("skipped evil") and problems[0].endswith(": not valid UTF-8")
    assert ESC not in problems[0] and "\n" not in problems[0]


def test_standard_profile_corpus_never_sees_skipped_document(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies the standard corpus detectors get the filtered list (no crash on bad bytes).

    Scenario:
        Given two readable prose documents and one non-UTF-8 document
        When a standard-profile scan runs
        Then it completes, the inventory holds all three documents, the only finding on the skipped one is
            DS100, and the only WARNING is the skip.

    Boundaries:
        - Focus: the filtered documents reach DS201-DS204 (corpus readers) as well as fast rules
        - Fixtures/params: tmp_path, caplog; skipped without the standard extra
        - Scope: one scan

    On failure, first check:
        - that engine.scan passes the filtered ``documents`` to every analyzer
    """
    pytest.importorskip("sklearn")
    pytest.importorskip("textstat")
    caplog.set_level(logging.WARNING, logger="docsentinel")
    prose = "This guide explains how the tool scans a folder of notes and reports problems it finds.\n"
    (tmp_path / "a.md").write_text("# A\n\n" + prose, encoding="utf-8")
    (tmp_path / "c.md").write_text("# C\n\n" + prose.replace("guide", "page"), encoding="utf-8")
    (tmp_path / "b.md").write_bytes(b"# B\n\n" + prose.encode("ascii") + b"\xff\n")

    result = scan(tmp_path, config=Config(profile="standard"))

    assert [document.path for document in result.documents] == ["a.md", "b.md", "c.md"]
    assert [finding.rule for finding in result.findings if finding.path == "b.md"] == ["DS100"]
    assert _problems(caplog) == ["skipped b.md: not valid UTF-8"]
