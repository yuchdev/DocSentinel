"""Unit tests for the log lines of the scanner and the first fast detectors (``docs/specs/logging.md``).

``DS101``-``DS110`` and ``DS117`` log one ``DEBUG`` line per ``detect()`` call with the
options that matter and one ``DEBUG`` line per document with its finding count. ``DS101``
logs a ``WARNING`` when it skips the anchor check of a linked file outside the scan root
(too large, not UTF-8 or unreadable). ``DS104``/``DS108``/``DS109``/``DS110``/``DS117`` log
one ``WARNING`` per call when an injected ``Config`` names a renderer or dialect they do
not model, because the rule then silently checks nothing. The Markdown scanner
(``markdown_blocks``) is a hot path and never logs. No log line carries document content.
"""

import logging
import types
from pathlib import Path

import pytest

from docsentinel import scan
from docsentinel.config import Config
from docsentinel.detectors import (
    anchors,
    comments,
    fence_languages,
    fences,
    headings,
    links,
    paths,
    references,
    sections,
    tables,
)
from docsentinel.markdown_blocks import resolve_local_reference, scan_markdown
from docsentinel.models import Document

#: DS103 is opt-in (Milestone 0009 Story 01.0): it evaluates only under reference_scope = "strict".
STRICT_SCOPE = Config(reference_scope="strict")

ESC = chr(0x1B)
#: A word placed in document content; no log record may ever contain it.
_MARKER = "PRIVATECONTENTMARKER"


def _records(caplog: pytest.LogCaptureFixture, prefix: str = "docsentinel") -> list[logging.LogRecord]:
    """Return the records logged under ``prefix``, in order."""
    return [record for record in caplog.records if record.name.startswith(prefix)]


def _problems(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the WARNING-or-above messages DocSentinel logged."""
    return [record.getMessage() for record in _records(caplog) if record.levelno >= logging.WARNING]


def _write(root: Path, name: str, text: str) -> Document:
    """Write ``text`` to ``root/name`` and return its document."""
    path = root / name
    path.write_text(text, encoding="utf-8")
    return Document(name, path.stat().st_size)


def _rule_code(module: types.ModuleType) -> str:
    """Return the rule code a detector module registers (its ``DSnnn`` attribute)."""
    return next(name for name in vars(module) if name.startswith("DS") and name[2:].isdigit())


def test_linked_anchors_warns_for_non_utf8_linked_file(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS101 logging: verifies a non-UTF-8 linked file logs one WARNING naming it and the reason.

    Scenario:
        Given a linked Markdown file holding invalid UTF-8 bytes
        When _linked_anchors reads it
        Then it still returns None and logs exactly one WARNING with the path and "not valid UTF-8".

    Boundaries:
        - Focus: the UnicodeDecodeError branch of links._linked_anchors
        - Fixtures/params: tmp_path, caplog
        - Scope: one call

    On failure, first check:
        - Whether the except branch still distinguishes UnicodeDecodeError from OSError
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    binary = tmp_path / "notes.md"
    binary.write_bytes(b"# Notes\n\xff\xfe\n")

    assert links._linked_anchors(binary) is None

    assert _problems(caplog) == [f"DS101 skipped the anchor check for linked file {binary}: not valid UTF-8"]
    assert [record.levelname for record in _records(caplog)] == ["WARNING"]


def test_linked_anchors_warns_for_oversized_linked_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
):
    """
    [Unit] DS101 logging: verifies a linked file over the read cap logs one WARNING with the cap.

    Scenario:
        Given the anchor read cap lowered to 20 characters and a 60-character linked file
        When _linked_anchors reads it
        Then it returns None and logs a WARNING naming the file and "larger than 20 characters".

    Boundaries:
        - Focus: the oversize branch of links._linked_anchors
        - Fixtures/params: tmp_path, caplog, monkeypatch (lowers _MAX_ANCHOR_SOURCE_CHARS)
        - Scope: one call

    On failure, first check:
        - Whether the oversize check still runs after a successful read
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    monkeypatch.setattr(links, "_MAX_ANCHOR_SOURCE_CHARS", 20)
    big = tmp_path / "big.md"
    big.write_text("# Title\n" + "x" * 52, encoding="utf-8")

    assert links._linked_anchors(big) is None

    assert _problems(caplog) == [f"DS101 skipped the anchor check for linked file {big}: larger than 20 characters"]


def test_linked_anchors_warns_for_unreadable_linked_file(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS101 logging: verifies an unreadable linked path logs one WARNING with the OS reason.

    Scenario:
        Given a directory named like a Markdown file (opening it raises an OSError)
        When _linked_anchors reads it
        Then it returns None and logs a WARNING "...: cannot read it (<strerror>)".

    Boundaries:
        - Focus: the OSError branch of links._linked_anchors
        - Fixtures/params: tmp_path, caplog
        - Scope: one call

    On failure, first check:
        - Whether the OSError branch still uses exc.strerror
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    folder = tmp_path / "folder.md"
    folder.mkdir()

    assert links._linked_anchors(folder) is None

    (message,) = _problems(caplog)
    assert message.startswith(f"DS101 skipped the anchor check for linked file {folder}: cannot read it (")
    assert message.endswith(")")


def test_linked_anchors_warning_neutralizes_a_crafted_file_name(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS101 logging: verifies a control character in the linked file name never reaches the record raw.

    Scenario:
        Given a non-UTF-8 linked file whose name carries an ESC character
        When _linked_anchors logs its WARNING
        Then the message holds the escaped form and no raw ESC.

    Boundaries:
        - Focus: safe() applied to the linked path
        - Fixtures/params: tmp_path, caplog
        - Scope: one call

    On failure, first check:
        - Whether the path argument is still wrapped in safe()
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    crafted = tmp_path / f"a{ESC}[31m.md"
    crafted.write_bytes(b"\xff")

    links._linked_anchors(crafted)

    (message,) = _problems(caplog)
    assert ESC not in message
    assert "\\x1b" in message


def test_linked_anchors_logs_nothing_for_a_readable_file(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS101 logging: verifies a small UTF-8 linked file is read without any log record.

    Scenario:
        Given a small UTF-8 linked file with one heading
        When _linked_anchors reads it
        Then the anchors are returned and nothing is logged.

    Boundaries:
        - Focus: the success path of links._linked_anchors
        - Fixtures/params: tmp_path, caplog
        - Scope: one call

    On failure, first check:
        - Whether a log call was added outside the skip branches
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    small = tmp_path / "small.md"
    small.write_text("# Title\n", encoding="utf-8")

    assert links._linked_anchors(small) == {"title"}
    assert _records(caplog) == []


def test_ds101_logs_entry_per_document_count_and_ds116_handoff(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS101 logging: verifies the entry line, the DS116 hand-off line and the per-document count.

    Scenario:
        Given one document with a dangling link and a link escaping the scan root
        When DS101 runs
        Then it logs DEBUG "checking 1 document(s)", the hand-off of ../out.md and "1 finding(s)", nothing higher.

    Boundaries:
        - Focus: links.detect and links.check_document DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: one detect call

    On failure, first check:
        - The order of the DEBUG calls in check_document
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    document = _write(tmp_path, "a.md", "[gone](missing.md) and [out](../out.md)\n")

    findings = links.detect(tmp_path, (document,))

    messages = [record.getMessage() for record in _records(caplog, "docsentinel.detectors.links")]
    assert len(findings) == 1
    assert messages[0].startswith("DS101 checking 1 document(s): link_root=")
    assert messages[1:] == ["DS101 a.md:1: target ../out.md left to DS116", "DS101 checked a.md: 1 finding(s)"]
    assert _problems(caplog) == []


def test_ds102_logs_counts_but_never_comment_text(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS102 logging: verifies per-document counts are logged and the comment text is not.

    Scenario:
        Given a document with a stray comment holding a marker word, one without any comment, and a .txt file
        When DS102 runs
        Then each document gets one DEBUG line with its count, the .txt skip is logged, and no record holds the marker.

    Boundaries:
        - Focus: comments.detect DEBUG lines, including the early exit without a comment closer
        - Fixtures/params: tmp_path, caplog
        - Scope: one detect call

    On failure, first check:
        - Whether a log call formats the finding message or value
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    with_comment = _write(tmp_path, "a.md", f"# A\n\n<!-- {_MARKER} -->\n")
    clean = _write(tmp_path, "b.md", "# B\n")
    other = _write(tmp_path, "c.txt", "<!-- x -->\n")

    comments.detect(tmp_path, (with_comment, clean, other))

    assert [record.getMessage() for record in _records(caplog)] == [
        "DS102 checking 3 document(s)",
        "DS102 checked a.md: 1 finding(s)",
        "DS102 checked b.md: 0 finding(s)",
        "DS102 skipped c.txt: not a Markdown document",
    ]
    assert all(record.levelno == logging.DEBUG for record in _records(caplog))


def test_ds103_logs_root_escape_handoff_and_count(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS103 logging: verifies a code span escaping the root is logged as left to DS116.

    Scenario:
        Given a document with a code span ``../outside.md`` and a missing in-root ``docs/x.md``
        When DS103 runs
        Then it logs the hand-off of ../outside.md at DEBUG and "1 finding(s)" for the document.

    Boundaries:
        - Focus: paths.detect DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: one detect call

    On failure, first check:
        - Whether the escape is still skipped via contained_path returning None
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    document = _write(tmp_path, "a.md", "see `../outside.md` and `docs/x.md`\n")

    findings = paths.detect(tmp_path, (document,), STRICT_SCOPE)

    messages = [record.getMessage() for record in _records(caplog, "docsentinel.detectors.paths")]
    assert [finding.value for finding in findings] == ["docs/x.md"]
    assert messages[1:] == [
        "DS103 a.md:1: code span ../outside.md resolves outside its boundary; left to DS116",
        "DS103 checked a.md: 1 finding(s)",
    ]


@pytest.mark.parametrize(
    ("module", "config", "expected"),
    [
        (
            anchors,
            Config(anchor_renderer="mkdocs"),
            "DS104 is not checked: anchor_renderer=mkdocs is not supported (only 'github')",
        ),
        (
            references,
            Config(reference_label_normalization="pandoc"),
            "DS108 is not checked: reference_label_normalization=pandoc is not supported (only 'commonmark')",
        ),
        (
            fences,
            Config(fence_dialect="pandoc"),
            "DS109 is not checked: fence_dialect=pandoc is not supported (only 'gfm-subset')",
        ),
        (
            fence_languages,
            Config(require_fence_languages=True, fence_dialect="pandoc"),
            "DS110 is not checked: fence_dialect=pandoc is not supported (only 'gfm-subset')",
        ),
        (
            tables,
            Config(table_dialect="pandoc"),
            "DS117 is not checked: table_dialect=pandoc is not supported (only 'gfm-subset')",
        ),
    ],
)
def test_unsupported_injected_dialect_warns_once_per_call(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, module: types.ModuleType, config: Config, expected: str
):
    """
    [Unit] fast detector logging: verifies an unsupported injected dialect logs one WARNING per detect call.

    Scenario:
        Given two documents and an injected Config naming a renderer/dialect the config loader would reject
        When the detector runs
        Then it still returns no findings and logs exactly one WARNING naming the option and value.

    Boundaries:
        - Focus: the dialect gates added to detect() of DS104, DS108, DS109, DS110, DS117
        - Fixtures/params: tmp_path, caplog, parametrized module/config
        - Scope: one detect call

    On failure, first check:
        - Whether the gate moved into check_text (it would warn once per document)
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    documents = (_write(tmp_path, "a.md", "# A\n"), _write(tmp_path, "b.md", "# B\n"))

    assert module.detect(tmp_path, documents, config) == ()
    assert _problems(caplog) == [expected]


@pytest.mark.parametrize(
    ("module", "config", "expected"),
    [
        (anchors, Config(anchor_collision_policy="off"), "DS104 is off: anchor_collision_policy=off"),
        (sections, Config(empty_section_policy="off"), "DS106 is off: empty_section_policy=off"),
        (fence_languages, Config(), "DS110 is off: require_fence_languages is not set"),
        (tables, Config(table_enable=False), "DS117 is off: table_enable=false"),
    ],
)
def test_policy_off_is_debug_only(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, module: types.ModuleType, config: Config, expected: str
):
    """
    [Unit] fast detector logging: verifies a rule switched off by its policy logs at DEBUG, never higher.

    Scenario:
        Given one document and a Config that switches the rule's policy off
        When the detector runs
        Then the "is off" line is logged at DEBUG and no WARNING/ERROR is logged.

    Boundaries:
        - Focus: the policy-off DEBUG lines in detect()
        - Fixtures/params: tmp_path, caplog, parametrized module/config
        - Scope: one detect call

    On failure, first check:
        - Whether a deliberate off switch was mistaken for a user problem
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    document = _write(tmp_path, "a.md", "# A\n")

    module.detect(tmp_path, (document,), config)

    debug = [record.getMessage() for record in _records(caplog) if record.levelno == logging.DEBUG]
    assert expected in debug
    assert _problems(caplog) == []


@pytest.mark.parametrize("module", [anchors, headings, sections, references, fences, fence_languages, tables])
def test_scanner_detectors_log_entry_and_per_document_count(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, module: types.ModuleType
):
    """
    [Unit] fast detector logging: verifies the entry line and one count line per document, without content.

    Scenario:
        Given a Markdown document whose headings, table cell and fence carry a marker word, and a .txt file
        When each scanner-based detector runs with defaults
        Then it logs "<code> checking 2 document(s): ...", the .txt skip and "<code> checked a.md: N finding(s)",
          and no record contains the marker word.

    Boundaries:
        - Focus: detect() of DS104, DS105, DS106, DS108, DS109, DS110, DS117
        - Fixtures/params: tmp_path, caplog, parametrized module
        - Scope: one detect call per module

    On failure, first check:
        - The shared detect() loop of the module and its rule code in the messages
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    text = f"# {_MARKER}\n\n| {_MARKER} | b |\n|---|---|\n| 1 |\n\n```\n{_MARKER}\n```\n\n### {_MARKER}\n"
    document = _write(tmp_path, "a.md", text)
    other = _write(tmp_path, "b.txt", "x\n")
    code = _rule_code(module)

    findings = module.detect(tmp_path, (document, other))

    messages = [record.getMessage() for record in _records(caplog, module.__name__)]
    assert messages[0].startswith(f"{code} checking 2 document(s): ")
    assert messages[-2:] == [
        f"{code} checked a.md: {len(findings)} finding(s)",
        f"{code} skipped b.txt: not a Markdown document",
    ]
    assert not any(_MARKER in record.getMessage() for record in caplog.records)


def test_markdown_scanner_never_logs(caplog: pytest.LogCaptureFixture):
    """
    [Unit] markdown_blocks logging: verifies the scanner and the resolver emit no record.

    Scenario:
        Given a small document with every token kind and an escaping reference
        When scan_markdown and resolve_local_reference run
        Then nothing is logged (the scanner is a hot path; detectors log per document).

    Boundaries:
        - Focus: markdown_blocks has a logger but no log calls
        - Fixtures/params: caplog
        - Scope: one scan and one resolve

    On failure, first check:
        - Whether a log call was added inside the scanner or resolver
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    text = "# H\n\n<!-- c -->\n\n```py\nx\n```\n\n[a][b]\n\n[b]: ../out.md\n\n| a |\n|---|\n"

    scan_markdown(text, "a.md")
    resolve_local_reference(Path("/r"), "a.md", "../../x.md")

    assert _records(caplog) == []


def test_clean_scan_logs_no_warning_or_error(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] fast detector logging: verifies a clean fast scan of a small inline document logs no problem.

    Scenario:
        Given one well-formed document linking to an existing sibling with a valid anchor
        When the engine runs the fast profile
        Then there are no findings and no WARNING/ERROR record from any docsentinel logger.

    Boundaries:
        - Focus: no false WARNING/ERROR on the normal path
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - Any WARNING added on a non-exceptional branch
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    (tmp_path / "a.md").write_text(
        "# Alpha\n\nSee [beta](b.md#beta) and `b.md`.\n\n| x | y |\n|---|---|\n| 1 | 2 |\n\n```text\nok\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "b.md").write_text("# Beta\n\nBody text.\n", encoding="utf-8")

    result = scan(tmp_path)

    assert result.findings == ()
    assert _problems(caplog) == []
