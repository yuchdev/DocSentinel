"""Unit tests for the engine's readability check and the DS100 rule (security review H1, L3, L4).

The engine checks every discovered document once, before any analyzer runs: it opens it with
``O_NOFOLLOW|O_NONBLOCK``, requires a regular file and validates UTF-8 with an incremental decoder.
A document that fails stays in the inventory, is withheld from every analyzer and becomes one
DS100 ``error`` finding unless ``select``/``ignore`` drop DS100. Stderr names at most
``MAX_STDERR_SKIP_WARNINGS`` such documents; the rest go to the log file only.
"""

import logging
import os
from pathlib import Path

import pytest

from docsentinel import engine, scan
from docsentinel.config import Config
from docsentinel.detectors.unreadable import FINDING_TYPE, NOT_REGULAR, NOT_UTF8, unreadable_finding
from docsentinel.log import FILE_ONLY
from docsentinel.models import Finding
from docsentinel.rules import ENGINE_RULES, RULES
from docsentinel.telemetry.classify import classify

_FILE_ONLY_ATTR = next(iter(FILE_ONLY))


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the WARNING records DocSentinel logged."""
    return [
        record
        for record in caplog.records
        if record.name.startswith("docsentinel") and record.levelno == logging.WARNING
    ]


def test_unreadable_reason_accepts_valid_utf8_split_across_chunks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] engine readability: verifies multi-byte characters split across read chunks still validate (normal case).

    Scenario:
        Given a document of two- to four-byte UTF-8 characters and a one-byte read chunk
        When ``_unreadable_reason`` checks it
        Then it returns ``None``.

    Boundaries:
        - Focus: the incremental decoder keeps state between chunks
        - Fixtures/params: tmp_path, monkeypatch (``_READ_CHUNK``)
        - Scope: one call

    On failure, first check:
        - ``_validate_document`` in ``engine.py``
    """
    path = tmp_path / "a.md"
    path.write_text("café € \U0001f600\n", encoding="utf-8")
    monkeypatch.setattr(engine, "_READ_CHUNK", 1)

    assert engine._unreadable_reason(path) is None


@pytest.mark.parametrize(
    "content",
    [b"# A\n\xff\n", b"# A\n\xe2\x82", "café".encode("latin-1")],
    ids=["invalid_byte", "truncated_sequence_at_eof", "latin1"],
)
def test_unreadable_reason_reports_invalid_utf8(content: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] engine readability: verifies an invalid, truncated or Latin-1 document is ``not valid UTF-8`` (invalid input).

    Scenario:
        Given a document with an invalid byte, a multi-byte sequence cut at end of file, or Latin-1 text
        When ``_unreadable_reason`` checks it with a two-byte read chunk
        Then it returns ``not valid UTF-8``.

    Boundaries:
        - Focus: the final ``decode(b"", final=True)`` and strict errors
        - Fixtures/params: tmp_path, monkeypatch; parametrized over three encodings
        - Scope: one call

    On failure, first check:
        - ``_validate_document`` in ``engine.py``
    """
    path = tmp_path / "a.md"
    path.write_bytes(content)
    monkeypatch.setattr(engine, "_READ_CHUNK", 2)

    assert engine._unreadable_reason(path) == NOT_UTF8


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are POSIX-only")
def test_unreadable_reason_does_not_block_on_a_fifo(tmp_path: Path):
    """
    [Unit] engine readability: verifies a FIFO swapped in after discovery is ``not a regular file`` without hanging (edge).

    Scenario:
        Given a FIFO with no writer at a document path
        When ``_unreadable_reason`` checks it
        Then it returns ``not a regular file`` at once (``O_NONBLOCK`` open, ``fstat`` check).

    Boundaries:
        - Focus: security review L3 (FIFO guard)
        - Fixtures/params: tmp_path
        - Scope: one call

    On failure, first check:
        - ``_READ_FLAGS`` (``O_NONBLOCK``) and the ``S_ISREG`` check in ``_validate_document``
    """
    fifo = tmp_path / "a.md"
    os.mkfifo(fifo)

    assert engine._unreadable_reason(fifo) == NOT_REGULAR


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks are not available")
def test_unreadable_reason_refuses_a_symlink(tmp_path: Path):
    """
    [Unit] engine readability: verifies a document swapped for a symlink is not followed (edge).

    Scenario:
        Given a symlink at a document path pointing at a valid UTF-8 file
        When ``_unreadable_reason`` checks it
        Then it reports ``cannot read it (...)`` from the ``O_NOFOLLOW`` open.

    Boundaries:
        - Focus: ``O_NOFOLLOW`` in ``_READ_FLAGS``
        - Fixtures/params: tmp_path
        - Scope: one call

    On failure, first check:
        - ``_READ_FLAGS`` in ``engine.py``
    """
    target = tmp_path / "real.md"
    target.write_text("# Real\n", encoding="utf-8")
    link = tmp_path / "a.md"
    link.symlink_to(target)

    reason = engine._unreadable_reason(link)

    assert reason is not None and reason.startswith("cannot read it (")


def test_unreadable_finding_shape_is_deterministic():
    """
    [Unit] DS100 finding: verifies rule, severity, message, value, type and an unlocated position.

    Scenario:
        Given a document path and a hostile reason holding a newline and ``##[``
        When ``unreadable_finding`` builds the finding
        Then it is an unlocated DS100 error whose message and value carry the neutralised reason only.

    Boundaries:
        - Focus: the DS100 finding contract (finding-types.md §4)
        - Fixtures/params: none
        - Scope: pure function

    On failure, first check:
        - ``unreadable_finding`` in ``detectors/unreadable.py``
    """
    plain = unreadable_finding("docs/a.md", NOT_UTF8)
    hostile = unreadable_finding("a.md", "cannot read it (x\n##[y])")

    assert plain == Finding(
        rule="DS100", path="docs/a.md", message="unreadable document: not valid UTF-8", severity="error"
    )
    assert (plain.line, plain.column, plain.value, plain.type) == (None, None, NOT_UTF8, FINDING_TYPE)
    assert hostile.message == "unreadable document: cannot read it (x\\x0a##\\[y])"
    assert hostile.value == "cannot read it (x\\x0a##\\[y])"


def test_ds100_is_a_fast_engine_rule_without_analyzer():
    """
    [Unit] DS100 registration: verifies DS100 is a registered fast error rule the engine emits itself.

    Scenario:
        Given the rule registry
        When DS100 is looked up
        Then it is a fast, error, always-active rule listed in ``ENGINE_RULES`` with no analyzer.

    Boundaries:
        - Focus: registry metadata the rule table and ``docsentinel rules`` repeat
        - Fixtures/params: none
        - Scope: registry lookup

    On failure, first check:
        - the ``register_rule`` call in ``detectors/unreadable.py``
    """
    rule = RULES["DS100"]

    assert (rule.profile, rule.severity, rule.opt_in_option, rule.title) == ("fast", "error", "", "Unreadable document")
    assert "DS100" in ENGINE_RULES
    assert "DS100" not in engine.ANALYZERS


@pytest.mark.parametrize(
    ("profile", "tier", "outcome"),
    [
        ("fast", "deterministic", "rejected"),
        ("standard", "deterministic", "rejected"),
        ("deep", "heuristic", "advisory"),
    ],
)
def test_ds100_classification_follows_the_scan_profile(profile: str, tier: str, outcome: str):
    """
    [Unit] DS100 classification: verifies DS100 blocks in fast/standard scans and is advisory in a deep scan.

    Scenario:
        Given a DS100 finding and a config of each profile
        When it is classified
        Then the tier and outcome follow the scan profile, matching the CLI's deep-is-advisory exit code.

    Boundaries:
        - Focus: the ENGINE_RULES branch of ``classify``
        - Fixtures/params: parametrized over the three profiles
        - Scope: pure function

    On failure, first check:
        - ``classify`` in ``telemetry/classify.py``
    """
    result = classify(unreadable_finding("a.md", NOT_UTF8), Config(profile=profile))

    assert (result.fault_class, result.tier, result.outcome) == ("unreadable_document", tier, outcome)


def test_clean_scan_keeps_enabled_rules_and_notice(tmp_path: Path):
    """
    [Unit] engine DS100: verifies a scan without unreadable documents is unchanged by DS100 (regression).

    Scenario:
        Given one clean document
        When a default fast scan runs
        Then DS100 is neither in ``enabled_rules`` nor counted in the notice, which still counts 12 rules.

    Boundaries:
        - Focus: byte-identical notice and enabled_rules for clean trees
        - Fixtures/params: tmp_path
        - Scope: one scan

    On failure, first check:
        - the ENGINE_RULES exclusion from ``profile_codes`` in ``engine.scan``
    """
    (tmp_path / "a.md").write_text("# A\n\nClean text.\n", encoding="utf-8")

    result = scan(tmp_path, config=Config())

    assert "DS100" not in result.enabled_rules
    assert result.findings == ()
    assert result.notice.startswith("12 fast rule(s) evaluated;")


@pytest.mark.parametrize(
    ("select", "ignore", "reported"),
    [((), (), True), (("DS1",), (), True), (("DS101",), (), False), ((), ("DS100",), False), ((), ("DS1",), False)],
    ids=["default", "prefix_select", "other_rule_selected", "ignored", "prefix_ignored"],
)
def test_ds100_honours_select_and_ignore(
    select: tuple[str, ...], ignore: tuple[str, ...], reported: bool, tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] engine DS100: verifies DS100 follows select/ignore while the document always stays in the inventory.

    Scenario:
        Given one non-UTF-8 document
        When scans run with several select/ignore combinations
        Then DS100 is reported (and listed first in ``enabled_rules``) only when selected and not ignored;
            the document is always listed and the skip WARNING is always logged.

    Boundaries:
        - Focus: DS100 selection (``ignore = ["DS100"]`` restores skip-with-warning only)
        - Fixtures/params: tmp_path, caplog; parametrized over five selections
        - Scope: one scan each

    On failure, first check:
        - the ``effective_rules((DS100.code,), ...)`` guard in ``engine.scan``
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    (tmp_path / "a.md").write_bytes(b"\xff")

    result = scan(tmp_path, config=Config(select=select, ignore=ignore))

    assert [document.path for document in result.documents] == ["a.md"]
    assert [finding.rule for finding in result.findings] == (["DS100"] if reported else [])
    assert ("DS100" in result.enabled_rules) is reported
    assert [record.getMessage() for record in _warnings(caplog)] == ["skipped a.md: not valid UTF-8"]


def test_ds100_is_reported_in_the_standard_profile(tmp_path: Path):
    """
    [Unit] engine DS100: verifies DS100 is emitted in a standard scan although it is registered as fast.

    Scenario:
        Given one non-UTF-8 document
        When a standard-profile scan runs
        Then the result holds exactly the DS100 finding.

    Boundaries:
        - Focus: DS100 is an engine rule emitted in every profile
        - Fixtures/params: tmp_path; skipped without the standard extra
        - Scope: one scan

    On failure, first check:
        - the DS100 emission placement in ``engine.scan``
    """
    pytest.importorskip("sklearn")
    pytest.importorskip("textstat")
    (tmp_path / "a.md").write_bytes(b"\xff")

    result = scan(tmp_path, config=Config(profile="standard"))

    assert [(finding.rule, finding.severity) for finding in result.findings] == [("DS100", "error")]
    assert result.notice.startswith("4 standard rule(s) evaluated")


def test_stderr_skip_warnings_are_capped(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies only the first 20 skipped documents reach stderr, then one summary (security review L4).

    Scenario:
        Given 25 non-UTF-8 documents
        When scan runs
        Then 25 skip WARNINGs are logged but only the first 20 may reach stderr (the other 5 carry
            ``FILE_ONLY``), one stderr summary counts the 5, and every document gets its DS100 finding.

    Boundaries:
        - Focus: ``MAX_STDERR_SKIP_WARNINGS`` and the ``FILE_ONLY`` extra in ``_partition_readable``
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - ``_partition_readable`` in ``engine.py``
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    for index in range(25):
        (tmp_path / f"d{index:02d}.md").write_bytes(b"\xff")

    result = scan(tmp_path, config=Config())

    records = _warnings(caplog)
    stderr = [record.getMessage() for record in records if not getattr(record, _FILE_ONLY_ATTR, False)]
    file_only = [record.getMessage() for record in records if getattr(record, _FILE_ONLY_ATTR, False)]
    assert stderr == [f"skipped d{index:02d}.md: not valid UTF-8" for index in range(20)] + [
        "skipped 5 more unreadable documents (see log file)"
    ]
    assert file_only == [f"skipped d{index:02d}.md: not valid UTF-8" for index in range(20, 25)]
    assert len([finding for finding in result.findings if finding.rule == "DS100"]) == 25


def test_twenty_skipped_documents_need_no_summary(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] engine logging: verifies exactly 20 skipped documents are all on stderr with no summary (edge).

    Scenario:
        Given 20 non-UTF-8 documents
        When scan runs
        Then 20 stderr-visible WARNINGs are logged and no summary line.

    Boundaries:
        - Focus: the boundary of ``MAX_STDERR_SKIP_WARNINGS``
        - Fixtures/params: tmp_path, caplog
        - Scope: one scan

    On failure, first check:
        - the ``>`` comparison in ``_partition_readable``
    """
    caplog.set_level(logging.WARNING, logger="docsentinel")
    for index in range(engine.MAX_STDERR_SKIP_WARNINGS):
        (tmp_path / f"d{index:02d}.md").write_bytes(b"\xff")

    scan(tmp_path, config=Config())

    records = _warnings(caplog)
    assert len(records) == engine.MAX_STDERR_SKIP_WARNINGS
    assert not any(getattr(record, _FILE_ONLY_ATTR, False) for record in records)
