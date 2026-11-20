"""Unit tests for the log lines of the config-driven fast detectors (``docs/specs/logging.md``).

``DS112`` (navigation), ``DS113`` (assets), ``DS114`` (document ids), ``DS115``
(deprecated references), ``DS116`` (path boundaries) and ``DS118`` (naming) log at
``DEBUG`` only: one entry line per ``detect`` with the options that matter, one line
per document (or index) with its finding count, the deliberate deferrals (DS113 to
DS116, DS116 code spans to DS103, DS114 malformed frontmatter to DS111) and the loaded
mapping/index sizes. The single ``WARNING`` is a DS114 document whose head is not
valid UTF-8 and is therefore skipped. A ``ConfigError`` is a user fault the CLI logs
once, so it is never logged where it is raised. No frontmatter id value and no
mapping ``old``/``new`` token ever reaches a log record.
"""

import logging
import os
from pathlib import Path

import pytest

from docsentinel import engine
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import assets, deprecated_refs, document_ids, naming, navigation, path_boundaries
from docsentinel.models import Document

_MODULES = (
    "docsentinel.detectors.assets",
    "docsentinel.detectors.deprecated_refs",
    "docsentinel.detectors.document_ids",
    "docsentinel.detectors.navigation",
    "docsentinel.detectors.path_boundaries",
    "docsentinel.detectors.naming",
)


def _messages(caplog: pytest.LogCaptureFixture, name: str) -> list[str]:
    """Return the messages logger ``name`` recorded, in order."""
    return [record.getMessage() for record in caplog.records if record.name == name]


def _problems(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Return the WARNING-and-above records any of this group's detectors logged."""
    return [record for record in caplog.records if record.name in _MODULES and record.levelno >= logging.WARNING]


def _write(root: Path, relative: str, content: str) -> Document:
    """Write ``content`` under ``root`` and return its discovered ``Document``."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Document(relative, path.stat().st_size)


def test_ds114_non_utf8_head_logs_one_warning_naming_only_the_path(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS114 logging: verifies a non-UTF-8 document head is skipped with one WARNING.

    Scenario:
        Given a discovered document whose first bytes are not valid UTF-8
        When DS114 detects over it
        Then it returns no findings (unchanged) and logs exactly one WARNING naming the path.

    Boundaries:
        - Focus: the ``head is None`` skip in ``document_ids.detect``
        - Fixtures/params: tmp_path, caplog
        - Scope: one document

    On failure, first check:
        - Whether the skip was reclassified (spec section 3 lists a skipped non-UTF-8 document as WARNING)
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))
    (root / "bad.md").write_bytes(b"---\nid: \xff\xfe\n---\n")

    findings = document_ids.detect(root, (Document("bad.md", 13),), Config())

    assert findings == ()
    problems = _problems(caplog)
    assert [(record.levelno, record.getMessage()) for record in problems] == [
        (logging.WARNING, "DS114 skipped bad.md: the document head is not valid UTF-8")
    ]


def test_ds114_logs_statuses_and_counts_but_never_the_id_value(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS114 logging: verifies per-document status lines and the summary carry no id value.

    Scenario:
        Given two documents sharing the id ``secret-id-q7``, one without frontmatter and one
            with an unterminated block
        When DS114 detects over them
        Then each document gets one DEBUG status line, the deferral to DS111 is DEBUG, the
            summary counts every outcome, and no record at any level contains the id.

    Boundaries:
        - Focus: ``check_documents`` and ``detect`` DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: four documents, corpus scope

    On failure, first check:
        - Whether a log call formats ``reading.value`` or ``display`` (frontmatter content)
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))
    documents = (
        _write(root, "a.md", "---\nid: secret-id-q7\n---\n"),
        _write(root, "b.md", "---\nid: secret-id-q7\n---\n"),
        _write(root, "c.md", "# no frontmatter\n"),
        _write(root, "d.md", "---\nid: other\n"),
    )

    findings = document_ids.detect(root, documents, Config())

    assert [finding.path for finding in findings] == ["b.md"]
    messages = _messages(caplog, "docsentinel.detectors.document_ids")
    assert messages[0].startswith("DS114 detect: 4 documents, document_id_field=id, document_id_scope=corpus")
    assert "DS114 read a.md: id declared" in messages
    assert "DS114 read c.md: no id declared" in messages
    assert "DS114 read d.md: malformed or ambiguous frontmatter left to DS111, not evaluated" in messages
    assert messages[-1] == (
        "DS114 checked 4 documents: 2 with an id, 1 without, 1 deferred to DS111, 0 unsupported shape; 1 findings"
    )
    assert all("secret-id-q7" not in record.getMessage() for record in caplog.records)
    assert all(record.levelno == logging.DEBUG for record in caplog.records if record.name in _MODULES)


def test_ds114_unsupported_shape_is_debug_not_warning(caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS114 logging: verifies an unsupported id value shape is logged at DEBUG only.

    Scenario:
        Given one document whose id is a flow sequence
        When ``check_documents`` runs
        Then the finding is emitted (unchanged) and the log line is DEBUG, not WARNING.

    Boundaries:
        - Focus: the ``_UNSUPPORTED`` branch; the finding is the result
        - Fixtures/params: caplog
        - Scope: one inline entry

    On failure, first check:
        - Whether the unsupported branch gained a WARNING (the finding already reports it)
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    findings = document_ids.check_documents((("x.md", "---\nid: [a, b]\n---\n"),), Config())

    assert len(findings) == 1
    assert "DS114 read x.md: id field has an unsupported value shape, not evaluated for uniqueness" in _messages(
        caplog, "docsentinel.detectors.document_ids"
    )
    assert _problems(caplog) == []


def test_ds115_logs_mapping_size_and_per_document_counts_without_tokens(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] DS115 logging: verifies the mapping-load line counts entries by kind and never names tokens.

    Scenario:
        Given a mapping with one prose and one identifier entry and a document using both
        When DS115 detects
        Then one DEBUG line reports 2 entries split by kind, one DEBUG line per document
            reports its finding count, and neither ``old`` nor ``new`` appears in any record.

    Boundaries:
        - Focus: ``deprecated_refs.detect`` and ``check_text`` DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: one mapping, one document

    On failure, first check:
        - Whether a log call formats ``Replacement.old``/``new``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))
    (root / "map.toml").write_text(
        'version = 1\n[[replacement]]\nold = "Quuxold"\nnew = "Quuxnew"\nkind = "prose"\n'
        '[[replacement]]\nold = "frobold"\nnew = "frobnew"\nkind = "identifier"\n',
        encoding="utf-8",
    )
    document = _write(root, "guide.md", "Use Quuxold and `frobold` here.\n")

    findings = deprecated_refs.detect(root, (document,), Config(deprecated_references_file="map.toml"))

    assert len(findings) == 2
    messages = _messages(caplog, "docsentinel.detectors.deprecated_refs")
    assert messages[0].startswith(
        "DS115 mapping map.toml loaded: 2 replacement entries (prose 1, link 0, identifier 1); "
    )
    assert messages[-1] == "DS115 checked guide.md: 2 findings (2 of 2 mapping entries in scope)"
    for token in ("Quuxold", "Quuxnew", "frobold", "frobnew"):
        assert all(token not in record.getMessage() for record in caplog.records)
    assert _problems(caplog) == []


def test_ds115_config_error_is_not_logged_where_raised(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS115 logging: verifies a missing mapping raises ConfigError without a WARNING/ERROR record.

    Scenario:
        Given ``deprecated_references_file`` naming a file that does not exist
        When DS115 detects
        Then ``ConfigError`` propagates (unchanged) and the detector logged no problem record.

    Boundaries:
        - Focus: fail-closed readiness path; the CLI logs it once
        - Fixtures/params: tmp_path, caplog
        - Scope: invalid input

    On failure, first check:
        - Whether ``load_mapping`` gained a log call before ``raise ConfigError``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    with pytest.raises(ConfigError):
        deprecated_refs.detect(tmp_path, (), Config(deprecated_references_file="missing.toml"))

    assert _problems(caplog) == []


def test_ds112_logs_index_and_required_sizes(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS112 logging: verifies the run line, per-index line and required summary.

    Scenario:
        Given one index listing one existing document and two required targets
        When DS112 detects
        Then DEBUG lines report 1 index and 2 required targets, the index's target and
            finding counts, and 1 of 2 required targets not listed.

    Boundaries:
        - Focus: ``navigation.detect`` and ``_analyze_index`` DEBUG lines
        - Fixtures/params: tmp_path, caplog
        - Scope: one index

    On failure, first check:
        - Whether the per-index line moved outside ``_analyze_index``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))
    documents = (_write(root, "README.md", "- [Guide](guide.md)\n"), _write(root, "guide.md", "# Guide\n"))
    config = Config(navigation_indexes=("README.md",), navigation_required=("guide.md", "other.md"))

    findings = navigation.detect(root, documents, config)

    assert len(findings) == 1
    messages = _messages(caplog, "docsentinel.detectors.navigation")
    assert messages[0].startswith("DS112 detect: 1 index(es), 2 required target(s), ")
    assert "DS112 checked index README.md: 1 navigation target(s), 0 findings" in messages
    assert messages[-1] == "DS112 required targets: 1 of 2 not listed across 1 index(es)"
    assert _problems(caplog) == []


def test_ds113_logs_targets_deferred_to_ds116(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS113 logging: verifies a root-escaping image is a DEBUG deferral, not a WARNING.

    Scenario:
        Given a document with a missing in-root image and an image escaping the root
        When DS113 checks it
        Then it reports the missing image only (unchanged) and logs one DEBUG line with
            1 finding and 1 target deferred to DS116.

    Boundaries:
        - Focus: the ``is_ds116_owned`` deferral counter in ``assets.check_text``
        - Fixtures/params: tmp_path, caplog
        - Scope: one document

    On failure, first check:
        - Whether the deferral counter is incremented on both DS116 branches
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))

    findings = assets.check_text("![a](missing.png)\n![b](../../out.png)\n", "doc.md", root, Config())

    assert len(findings) == 1
    assert _messages(caplog, "docsentinel.detectors.assets") == [
        "DS113 checked doc.md: 1 findings, 1 target(s) deferred to DS116"
    ]
    assert _problems(caplog) == []


def test_ds116_logs_code_spans_left_to_ds103(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS116 logging: verifies the code-span narrowing is counted at DEBUG.

    Scenario:
        Given a document with a Windows drive path in a code span and an escaping link
        When DS116 checks it
        Then the link is reported (unchanged) and one DEBUG line counts 1 finding and
            1 code span left to DS103.

    Boundaries:
        - Focus: the ``_CODE_SPAN_EXEMPT_REASONS`` skip in ``path_boundaries.check_text``
        - Fixtures/params: tmp_path, caplog
        - Scope: one document

    On failure, first check:
        - Whether ``_looks_path_like`` still treats ``C:\\x\\win.ini`` as path-like
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))

    findings = path_boundaries.check_text("See `C:\\x\\win.ini` and [up](../../x.md).\n", "doc.md", root, Config())

    assert len(findings) == 1
    assert _messages(caplog, "docsentinel.detectors.path_boundaries") == [
        "DS116 checked doc.md: 1 findings, 1 code span(s) left to DS103"
    ]
    assert _problems(caplog) == []


def test_ds118_logs_policy_and_per_path_counts_with_neutralized_names(caplog: pytest.LogCaptureFixture):
    """
    [Unit] DS118 logging: verifies the policy line and a per-path line with a neutralized path.

    Scenario:
        Given the kebab policy and one conformant path and one path with an ESC character
        When ``check_paths`` runs
        Then DEBUG lines report the policy, each path's finding count, and no raw ESC.

    Boundaries:
        - Focus: ``naming.check_paths`` DEBUG lines and ``safe`` on the path
        - Fixtures/params: caplog
        - Scope: two inline paths

    On failure, first check:
        - Whether the per-path log call still wraps the path in ``safe``
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    hostile = "Bad\x1bName.md"

    findings = naming.check_paths(("good-name.md", hostile), Config(documentation_naming="kebab"))

    assert len(findings) == 1
    messages = _messages(caplog, "docsentinel.detectors.naming")
    assert messages[0].startswith("DS118 checking 2 path(s): documentation_naming=kebab, ")
    assert messages[1] == "DS118 checked good-name.md: 0 findings"
    assert messages[2] == "DS118 checked Bad\\x1bName.md: 1 findings"
    assert all("\x1b" not in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize(
    ("call", "logger_name", "expected"),
    [
        (
            lambda: navigation.detect(Path("."), (), Config()),
            "navigation",
            "DS112 inactive: navigation_indexes is not set",
        ),
        (
            lambda: assets.detect(Path("."), (), Config(missing_asset_policy="off")),
            "assets",
            "DS113 inactive: missing_asset_policy is off",
        ),
        (
            lambda: deprecated_refs.detect(Path("."), (), Config()),
            "deprecated_refs",
            "DS115 inactive: deprecated_references_file is not set",
        ),
        (
            lambda: path_boundaries.detect(Path("."), (), Config(root_escape_policy="off")),
            "path_boundaries",
            "DS116 inactive: root_escape_policy is off",
        ),
        (lambda: naming.check_paths(("A.md",), Config()), "naming", "DS118 inactive: documentation_naming is off"),
    ],
)
def test_inactive_policy_logs_one_debug_line(call, logger_name: str, expected: str, caplog: pytest.LogCaptureFixture):
    """
    [Unit] detector logging: verifies an off policy logs one DEBUG line naming its option.

    Scenario:
        Given a detector whose gating option is off
        When it is called
        Then it returns no findings and logs exactly one DEBUG line naming the option.

    Boundaries:
        - Focus: the early-return branches of each detector
        - Fixtures/params: caplog; one case per detector
        - Scope: no filesystem access

    On failure, first check:
        - Whether the early return still precedes the entry DEBUG line
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    assert call() == ()

    records = [record for record in caplog.records if record.name == f"docsentinel.detectors.{logger_name}"]
    assert [(record.levelno, record.getMessage()) for record in records] == [(logging.DEBUG, expected)]


def test_normal_scan_with_every_group_rule_active_emits_no_warning_or_error(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] detector logging: verifies a normal scan with all six rules on logs nothing above DEBUG.

    Scenario:
        Given a small clean tree with every opt-in of DS112/DS115/DS118 enabled and
            DS113/DS114/DS116 at their defaults
        When ``engine.scan`` runs
        Then none of this group's detectors logs at INFO or above.

    Boundaries:
        - Focus: level discipline (detectors never log INFO; WARNING only on coped input faults)
        - Fixtures/params: tmp_path, caplog
        - Scope: one fast scan, three documents

    On failure, first check:
        - Whether a new log call in one of the six modules used INFO or WARNING for a normal path
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    root = Path(os.path.realpath(tmp_path))
    _write(root, "README.md", "---\nid: home\n---\n# Home\n\n- [Guide](guide.md)\n")
    _write(root, "guide.md", "---\nid: guide\n---\n# Guide\n\nUse the new name.\n")
    (root / "map.toml").write_text(
        'version = 1\n[[replacement]]\nold = "oldname"\nnew = "newname"\nkind = "prose"\n', encoding="utf-8"
    )
    config = Config(
        select=("DS112", "DS113", "DS114", "DS115", "DS116", "DS118"),
        navigation_indexes=("README.md",),
        navigation_required=("guide.md",),
        deprecated_references_file="map.toml",
        documentation_naming="kebab",
        link_root=".",
    )

    result = engine.scan(root, config=config)

    assert result.findings == ()
    assert [record for record in caplog.records if record.name in _MODULES and record.levelno >= logging.INFO] == []
    assert any(record.name in _MODULES for record in caplog.records)
