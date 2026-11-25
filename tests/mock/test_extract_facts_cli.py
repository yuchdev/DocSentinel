"""``docsentinel extract-facts`` with the spaCy pipeline and claim extraction replaced (Story 05.0 Task 03).

The deep-readiness probes, the pipeline loader and ``mining.claims.extract_statements`` are patched, so no
spaCy model is needed; salience, clustering, the template and the CLI run for real. Covers the
deep-not-ready stop before any read, the E7 type-name-only error, the E10 no-file-on-render-failure
rule, the E13 no-claim-text-in-logs rule (also with ``-v``), the cross-context template messages, the
unreadable-document skip and the empty invoker selection. The full CLI set is Task 04's.
"""

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel import cli, engine
from docsentinel.detectors import fact_check
from docsentinel.engine import EMPTY_SELECTION_MESSAGE
from docsentinel.log import LOG_DIR_ENV
from docsentinel.mining import nlp
from docsentinel.mining.claims import Claim

#: A claim sentence that may reach stdout or the ``-o`` file, never stderr, a log file or a record.
SENTINEL_SENTENCE = "Sentinel-0010 node alpha holds 7 shards in Q3 region nine."


class RecordCollector(logging.Handler):
    """Keep every ``docsentinel`` record."""

    def __init__(self):
        """Start with no records."""
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord):
        """Store the record.

        :param record: The record.
        """
        self.records.append(record)

    def text(self) -> str:
        """Return every record's message, arguments and exception text.

        :returns: The joined text.
        """
        return "\n".join(f"{r.getMessage()} {r.args!r} {r.exc_text or ''}" for r in self.records)


@pytest.fixture
def records() -> Iterator[RecordCollector]:
    """Attach a DEBUG collector to the ``docsentinel`` logger.

    :returns: The collector.
    """
    collector = RecordCollector()
    package = logging.getLogger("docsentinel")
    previous = package.level
    package.addHandler(collector)
    package.setLevel(logging.DEBUG)
    yield collector
    package.removeHandler(collector)
    package.setLevel(previous)


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the per-run log file at a test directory.

    :param tmp_path: Pytest temporary directory.
    :param monkeypatch: Pytest monkeypatch.
    :returns: The log directory.
    """
    directory = tmp_path / "logs"
    monkeypatch.setenv(LOG_DIR_ENV, str(directory))
    return directory


def _log_text(directory: Path) -> str:
    """Return the text of every per-run log file in ``directory``.

    :param directory: The log directory.
    :returns: The joined file contents.
    """
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(directory.glob("docsentinel-*.log")))


def _claims_for(text: str, path: str) -> tuple[Claim, ...]:
    """Return one salient claim per non-blank line of ``text``.

    :param text: The document text.
    :param path: The document path.
    :returns: The claim literals.
    """
    return tuple(
        Claim(
            subject_key="node",
            predicate_key="hold",
            raw_subject="Node",
            raw_object=f"{index} shards Q{index}",
            raw_sentence=line,
            object_numbers=(str(index),),
            object_entities=(f"DATE:Q{index}",),
            path=path,
            paragraph_index=index,
        )
        for index, line in enumerate(line for line in text.splitlines() if line.strip())
    )


@pytest.fixture
def ready(monkeypatch: pytest.MonkeyPatch):
    """Report the deep extras as ready and replace the pipeline and claim extraction.

    :param monkeypatch: Pytest monkeypatch.
    """
    monkeypatch.setattr(nlp, "deep_ready", lambda: True)
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: "pipeline")
    monkeypatch.setattr(
        "docsentinel.mining.claims.extract_statements", lambda pipeline, text, path: _claims_for(text, path)
    )


def _corpus(root: Path) -> Path:
    """Write one document holding the sentinel sentence and one ordinary document.

    :param root: The directory to write into.
    :returns: The scan root.
    """
    docs = root / "docs"
    docs.mkdir()
    (docs / "a.md").write_text(SENTINEL_SENTENCE + "\n", encoding="utf-8")
    (docs / "b.md").write_text("Cluster bravo runs 4 replicas in zone 2 rack 8.\n", encoding="utf-8")
    return docs


@pytest.mark.parametrize("flags", [(), ("-v",)], ids=["info", "debug"])
def test_claim_text_reaches_stdout_only(
    tmp_path: Path, ready, records: RecordCollector, log_dir: Path, capsys: pytest.CaptureFixture[str], flags
):
    """
    [Unit] extract-facts CLI: verifies claim text reaches stdout but never stderr, the log file or a record (E13).

    Scenario:
        Given a corpus whose claim is a sentinel sentence and patched extraction
        When extract-facts runs, at INFO and with -v
        Then the exit code is 0, stdout holds the sentence, and stderr, the log file and every record do not.

    Boundaries:
        - Focus: threat model 0010-extract-facts E13
        - Fixtures/params: patched pipeline; -v on/off
        - Scope: cli.main end to end

    On failure, first check:
        - The extract-facts started/finished lines and the engine's DEBUG stage counts
    """
    root = _corpus(tmp_path)

    code = cli.main(["extract-facts", str(root), *flags])

    captured = capsys.readouterr()
    assert code == 0
    assert SENTINEL_SENTENCE in captured.out
    assert "docsentinel: extract-facts started:" in captured.err
    assert "docsentinel: config: user settings off, project none" in captured.err
    assert SENTINEL_SENTENCE not in captured.err
    assert SENTINEL_SENTENCE not in _log_text(log_dir)
    assert SENTINEL_SENTENCE not in records.text()


def test_extraction_error_prints_type_name_only(
    tmp_path: Path, ready, records: RecordCollector, log_dir: Path, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] extract-facts CLI: verifies a third-party extraction error prints the fixed type-name text (E7).

    Scenario:
        Given extract_statements raising ValueError carrying a claim sentence
        When extract-facts runs with -v
        Then the exit code is 2, stderr holds the fixed message, and no output, log or record holds the sentence.

    Boundaries:
        - Focus: threat model 0010-extract-facts E7, E13
        - Fixtures/params: extract_statements patched to raise
        - Scope: cli.main end to end

    On failure, first check:
        - engine._traced and the RuntimeError branch of cli._cmd_extract_facts
    """

    def _boom(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Raise an error whose text is document-derived."""
        raise ValueError(SENTINEL_SENTENCE)

    monkeypatch.setattr("docsentinel.mining.claims.extract_statements", _boom)
    root = _corpus(tmp_path)

    code = cli.main(["extract-facts", str(root), "-v"])

    captured = capsys.readouterr()
    assert code == 2
    assert "Extraction failed: extract-facts: claim extraction failed (ValueError)\n" in captured.err
    for text in (captured.out, captured.err, _log_text(log_dir), records.text()):
        assert SENTINEL_SENTENCE not in text


def test_deep_not_ready_stops_before_any_read(tmp_path: Path, monkeypatch, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] extract-facts CLI: verifies missing deep extras exit 2 with the doctor-style message, reading nothing.

    Scenario:
        Given deep_ready patched to False and extract_facts patched to fail if called
        When extract-facts runs
        Then the exit code is 2 and stderr names the deep extras hint.

    Boundaries:
        - Focus: story decision X11
        - Fixtures/params: deep_ready False
        - Scope: cli._cmd_extract_facts

    On failure, first check:
        - The order of the readiness check in cli._cmd_extract_facts
    """

    def _never(*args: object, **kwargs: object):
        """Fail: no document may be read."""
        raise AssertionError("extract_facts must not run")

    monkeypatch.setattr(nlp, "deep_ready", lambda: False)
    monkeypatch.setattr(cli, "extract_facts", _never)
    root = _corpus(tmp_path)

    code = cli.main(["extract-facts", str(root)])

    err = capsys.readouterr().err
    assert code == 2
    expected = f"Extraction failed: extract-facts needs the deep extras and the spaCy model - {nlp.DEEP_EXTRA_HINT}"
    assert expected in err


def test_output_file_is_valid_json_and_render_failure_leaves_none(
    tmp_path: Path, ready, monkeypatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] extract-facts CLI: verifies -o writes valid facts JSON, and a render failure writes no file (E10).

    Scenario:
        Given a patched corpus
        When extract-facts --format facts-json -o runs, then again with render_facts failing
        Then the first run writes parseable JSON and logs "report written to", the second exits 2 with no file.

    Boundaries:
        - Focus: Task 03 step 2.6 and threat model E10
        - Fixtures/params: render_facts patched to raise on the second run
        - Scope: cli._cmd_extract_facts output handling

    On failure, first check:
        - That the output is rendered before _write_report is called
    """
    root = _corpus(tmp_path)
    out = tmp_path / "out" / "facts.json"

    assert cli.main(["extract-facts", str(root), "--format", "facts-json", "-o", str(out)]) == 0
    err = capsys.readouterr().err
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == "docsentinel-facts"
    assert "report written to " in err and "(facts-json, " in err

    def _fail(*args: object, **kwargs: object) -> str:
        """Simulate a render failure."""
        raise ValueError("render failed")

    monkeypatch.setattr(cli, "render_facts", _fail)
    missing = tmp_path / "out" / "never.json"

    assert cli.main(["extract-facts", str(root), "--format", "facts-json", "-o", str(missing)]) == 2
    assert "Extraction failed: render failed" in capsys.readouterr().err
    assert not missing.exists()


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["extract-facts", "--format", "json"], "Extraction failed: template json is a report template"),
        (["scan", "--format", "facts-json"], "Scan failed: template facts-json renders fact extraction output"),
    ],
    ids=["report-template-to-extract-facts", "facts-template-to-scan"],
)
def test_cross_context_format_names_the_right_command(
    tmp_path: Path, ready, capsys: pytest.CaptureFixture[str], argv: list[str], message: str
):
    """
    [Unit] extract-facts CLI: verifies a template of the other context exits 2 naming the right command.

    Scenario:
        Given a packaged template of the other context
        When scan or extract-facts names it with --format
        Then the exit code is 2 and the message names the command that renders it.

    Boundaries:
        - Focus: story decision X9
        - Fixtures/params: the two directions
        - Scope: cli._command_template

    On failure, first check:
        - require_context and the PACKAGED_TEMPLATE_CONTEXTS fallback in cli._command_template
    """
    root = _corpus(tmp_path)

    code = cli.main([argv[0], str(root), *argv[1:]])

    assert code == 2
    assert message in capsys.readouterr().err


def test_unreadable_document_is_counted_and_exit_is_zero(tmp_path: Path, ready, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] extract-facts CLI: verifies a non-UTF-8 document is skipped with the shared WARNING and exit 0.

    Scenario:
        Given a corpus with one non-UTF-8 document
        When extract-facts --format facts-json runs
        Then the exit code is 0, stderr holds the skip WARNING, and the summary counts one unreadable.

    Boundaries:
        - Focus: story decision X12
        - Fixtures/params: one invalid UTF-8 file
        - Scope: cli.main end to end

    On failure, first check:
        - engine._partition_readable through the shared inventory step
    """
    root = _corpus(tmp_path)
    (root / "bad.md").write_bytes(b"\xff\xfe not utf-8\n")

    code = cli.main(["extract-facts", str(root), "--format", "facts-json"])

    captured = capsys.readouterr()
    assert code == 0
    assert "skipped bad.md: not valid UTF-8" in captured.err
    assert json.loads(captured.out)["summary"]["unreadable"] == 1


def test_empty_invoker_selection_exits_two(tmp_path: Path, ready, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] extract-facts CLI: verifies an invoker include that admits no document exits 2.

    Scenario:
        Given a corpus and an include glob matching nothing
        When extract-facts runs
        Then the exit code is 2 with EMPTY_SELECTION_MESSAGE.

    Boundaries:
        - Focus: story decision X12 (ADR 0006 owner ruling R1)
        - Fixtures/params: --include "zzz*.md"
        - Scope: cli.main end to end

    On failure, first check:
        - engine._inventory with command="extract-facts"
    """
    root = _corpus(tmp_path)

    code = cli.main(["extract-facts", str(root), "--include", "zzz*.md"])

    assert code == 2
    assert f"Extraction failed: {EMPTY_SELECTION_MESSAGE}" in capsys.readouterr().err
