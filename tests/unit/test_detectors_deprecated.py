"""Unit tests for DS115 deprecated-names recognition and mapping-load discipline.

These tests use tiny inline Markdown and TOML strings (plus a few small files
written into ``tmp_path`` when the mapping-load readiness error genuinely needs the
filesystem) and call the detector's pure core through
``parse_mapping(raw_text, configured_path)``, ``load_mapping(root, configured_path)``
and ``check_text(text, document_path, root, mapping, config)``. Detection over
committed Markdown assets is the job of the Story 13.0 Task 03 integration suite,
which runs over ``DS115``'s committed ``tests/assets/ds115/*`` fixtures now that
Task 02 has registered the rule.

Each algorithm bullet, exclusion, and ruling (R1-R10) of the DS115 threat model has
a test here, plus every R-listed hostile mapping shape, the config validation, the
opt-in gate, the bounded repr-escaped echo, and single-line and multi-line
linear-scaling floods.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config, models, rules
from docsentinel.detectors import deprecated_refs as dep
from tests.timing_helpers import assert_scales_linearly

_ROOT = Path(os.sep) / "scanroot"


def _mapping(raw_text: str, configured_path: str = "deprecated.toml") -> dep.DeprecatedMapping:
    """Return a validated mapping parsed from inline TOML text.

    :param raw_text: The TOML mapping body.
    :param configured_path: The configured mapping path echoed as provenance.
    :returns: The validated :class:`~docsentinel.detectors.deprecated_refs.DeprecatedMapping`.
    """
    return dep.parse_mapping(raw_text, configured_path)


def _messages(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the message of each finding in order.

    :param findings: The findings to describe.
    :returns: The ordered finding messages.
    """
    return [finding.message for finding in findings]


def _check(text: str, raw_mapping: str, config: Config, path: str = "README.md") -> tuple[models.Finding, ...]:
    """Return the DS115 findings for one inline document against an inline mapping.

    :param text: The document Markdown text.
    :param raw_mapping: The TOML mapping body.
    :param config: The effective configuration.
    :param path: The document's relative path.
    :returns: The findings in deterministic order.
    """
    return dep.check_text(text, path, _ROOT, _mapping(raw_mapping), config)


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors deprecated_refs: verifies DS115 metadata is exact and registered.

    Scenario:
        Given the DS115 rule metadata built in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact with the deprecated_references_file opt-in option, and the
            rule is registered in both RULES and ANALYZERS as Task 02 wires it.

    Boundaries:
        - Focus: rule identity and the Task 02 registration
        - Fixtures/params: none

    On failure, first check:
        - Whether a metadata field (profile, severity, opt_in_option) drifted
        - Whether register_rule / the ANALYZERS wiring was removed
    """
    assert dep.DS115.code == "DS115"
    assert dep.DS115.profile == "fast"
    assert dep.DS115.severity == "warning"
    assert dep.DS115.title == "Deprecated names and migrated references"
    assert dep.DS115.opt_in_option == "deprecated_references_file"
    assert rules.RULES["DS115"] is dep.DS115
    assert rules.ANALYZERS["DS115"] is dep.detect


def test_prose_match_emits_bounded_provenance_message():
    """
    [Unit] detectors deprecated_refs: verifies a prose match carries old, new and provenance (R6/R10).

    Scenario:
        Given a mapping with one prose entry and a document naming the deprecated term in prose
        When check_text runs with default config
        Then exactly one warning finding is emitted at the correct line naming the old token, the
            suggested new, and the configured mapping path plus the integer entry index.

    Boundaries:
        - Focus: the prose substrate, the message contract (R6), and one-per-occurrence (R10)
        - Fixtures/params: none

    On failure, first check:
        - Whether the entry index or configured path is missing from the message
        - Whether the line number tracks the occurrence
    """
    mapping = 'version = 1\n[[replacement]]\nold = "oldmod"\nnew = "newmod"\nkind = "prose"\n'
    findings = _check("# Title\n\nThe oldmod helper is gone.\n", mapping, Config())
    assert len(findings) == 1
    assert findings[0].rule == "DS115"
    assert findings[0].severity == "warning"
    assert findings[0].line == 3
    assert findings[0].path == "README.md"
    assert findings[0].message == (
        "deprecated prose 'oldmod' should be replaced with 'newmod' (mapping deprecated.toml entry 0)"
    )


@pytest.mark.parametrize(
    ("kind", "document", "expected_lines"),
    [
        ("prose", "the Widget name here\n", [1]),
        ("prose", "use `Widget` only\n", []),
        ("identifier", "use `Widget` here\n", [1]),
        ("identifier", "the Widget name here\n", []),
        ("link", "see [x](Widget)\n", [1]),
        ("link", "the Widget name here\n", []),
    ],
)
def test_kind_scoping_restricts_substrate(kind: str, document: str, expected_lines: list[int]):
    """
    [Unit] detectors deprecated_refs: verifies each kind matches only its substrate (R5).

    Scenario:
        Given a mapping whose single entry has a given kind and a document that places the old
            token in prose, inline code, or a link target
        When check_text runs with default config
        Then the occurrence is flagged only when it sits in the substrate the kind selects, so
            prose entries never fire on code spans or links and vice versa.

    Boundaries:
        - Focus: per-kind substrate scoping (prose/identifier/link) of R5
        - Fixtures/params: kind, document, expected_lines

    On failure, first check:
        - Whether the masked-prose, inline-code, or link-target path leaked into another kind
    """
    mapping = f'version = 1\n[[replacement]]\nold = "Widget"\nnew = "Gadget"\nkind = "{kind}"\n'
    findings = _check(document, mapping, Config())
    assert [finding.line for finding in findings] == expected_lines


@pytest.mark.parametrize(
    ("old", "document", "expected"),
    [
        ("APIv1", "We use APIv10 and APIv1 here.\n", 1),
        ("APIv1", "Only APIv10 appears.\n", 0),
        ("OldClass", "Call (OldClass), please.\n", 1),
        ("OldClass", "A sentence ends with OldClass.\n", 1),
        ("OldClass", "But OldClassExtra is distinct.\n", 0),
        ("pkg.Old", "Import pkg.Old now.\n", 1),
        ("pkg.Old", "Import pkg.OldThing now.\n", 0),
    ],
)
def test_token_boundaries_and_punctuation(old: str, document: str, expected: int):
    """
    [Unit] detectors deprecated_refs: verifies literal token boundaries around punctuation (R4).

    Scenario:
        Given a prose entry whose old is an identifier or dotted name and a document placing it
            adjacent to punctuation, inside a longer token, or standalone
        When check_text runs with default config
        Then a whole-token match fires (APIv1 is found beside punctuation) while a longer token
            such as APIv10 or OldClassExtra never matches a shorter old.

    Boundaries:
        - Focus: the whole-token comparison that makes APIv1 not match inside APIv10 (R4)
        - Fixtures/params: old, document, expected

    On failure, first check:
        - Whether the tokenizer included trailing sentence punctuation in the token
        - Whether substring matching crept back in
    """
    mapping = f'version = 1\n[[replacement]]\nold = "{old}"\nnew = "REPL"\nkind = "prose"\n'
    assert len(_check(document, mapping, Config())) == expected


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ("the old module is retired\n", 1),
        ("the old, module split by comma\n", 0),
        ("old\nmodule across lines\n", 0),
        ("brand old module here\n", 1),
    ],
)
def test_multi_word_prose_requires_whitespace_adjacency(document: str, expected: int):
    """
    [Unit] detectors deprecated_refs: verifies multi-word old needs whitespace-adjacent tokens (R4).

    Scenario:
        Given a prose entry whose old is the two-word phrase "old module" and documents that place
            the two tokens whitespace-adjacent, comma-separated, or split across lines
        When check_text runs with default config
        Then only the whitespace-adjacent occurrence on a single physical line is flagged.

    Boundaries:
        - Focus: the bounded whitespace-adjacent tail compare for multi-word olds (R4)
        - Fixtures/params: document, expected

    On failure, first check:
        - Whether the gap check accepted non-whitespace between tokens
        - Whether a multi-line term was folded across physical lines
    """
    mapping = 'version = 1\n[[replacement]]\nold = "old module"\nnew = "new module"\nkind = "prose"\n'
    assert len(_check(document, mapping, Config())) == expected


@pytest.mark.parametrize(
    "document",
    [
        "```\nWidget\n```\n",
        "text `Widget` inline\n",
        "text <!-- Widget --> here\n",
    ],
)
def test_masked_regions_are_exempt_for_prose(document: str):
    """
    [Unit] detectors deprecated_refs: verifies fenced/inline-code/comment regions are exempt (R5).

    Scenario:
        Given a prose entry and a document that places the old token only inside a fenced block,
            an inline-code span, or an HTML comment
        When check_text runs with default config
        Then the prose matcher never fires because it runs over the scanner's masked text.

    Boundaries:
        - Focus: scanner-mask parity for prose matching (R5)
        - Fixtures/params: document

    On failure, first check:
        - Whether _masked_text blanked every hidden span before tokenizing the prose line
    """
    mapping = 'version = 1\n[[replacement]]\nold = "Widget"\nnew = "Gadget"\nkind = "prose"\n'
    assert _check(document, mapping, Config()) == ()


@pytest.mark.parametrize(
    ("case_sensitive", "expected"),
    [(True, 0), (False, 1)],
)
def test_case_policy_is_governed_by_option(case_sensitive: bool, expected: int):
    """
    [Unit] detectors deprecated_refs: verifies case sensitivity follows deprecated_case_sensitive (R7).

    Scenario:
        Given a prose entry whose old is "OldName" and a document that writes "oldname" in a
            different case
        When check_text runs once case-sensitive and once case-insensitive
        Then the differently cased token matches only when deprecated_case_sensitive is false.

    Boundaries:
        - Focus: the single case policy knob (R7)
        - Fixtures/params: case_sensitive, expected

    On failure, first check:
        - Whether both sides are casefolded only when the option is false
    """
    mapping = 'version = 1\n[[replacement]]\nold = "OldName"\nnew = "NewName"\nkind = "prose"\n'
    config = Config(deprecated_case_sensitive=case_sensitive)
    assert len(_check("We still ship oldname today.\n", mapping, config)) == expected


def test_nfc_normalization_matches_and_confusables_stay_distinct():
    """
    [Unit] detectors deprecated_refs: verifies NFC matching and distinct confusables (R7).

    Scenario:
        Given a prose entry whose old is an accented name written NFD and a document that writes
            the same name NFC, plus a separate Cyrillic look-alike of an ASCII old
        When check_text runs with default config
        Then the NFC-equivalent occurrence matches while the Cyrillic confusable of a Latin old
            never matches, because normalization is NFC only (no confusable folding).

    Boundaries:
        - Focus: the NFC (not NFKC) normalization ruling (R7)
        - Fixtures/params: none

    On failure, first check:
        - Whether normalization folded confusables or skipped NFC on one side
    """
    old_nfd = unicodedata.normalize("NFD", "Café")
    doc_nfc = unicodedata.normalize("NFC", "the Café bar\n")
    mapping = f'version = 1\n[[replacement]]\nold = "{old_nfd}"\nnew = "Bistro"\nkind = "prose"\n'
    assert len(_check(doc_nfc, mapping, Config())) == 1

    confusable = "Siсtem"  # the third letter is Cyrillic 'es', not Latin 'c'
    mapping_c = 'version = 1\n[[replacement]]\nold = "Sistem"\nnew = "System"\nkind = "prose"\n'
    assert _check(f"the {confusable} word\n", mapping_c, Config()) == ()


def test_chain_and_cycle_are_inert():
    """
    [Unit] detectors deprecated_refs: verifies chains and cycles are reported literally, not chased (R7).

    Scenario:
        Given a mapping with a cycle a->b and b->a and a document containing both a and b once
        When check_text runs with default config
        Then each literal occurrence is reported exactly once and the matcher terminates, never
            following new back into another match.

    Boundaries:
        - Focus: literal-occurrence reporting with inert chains/cycles (R7)
        - Fixtures/params: none

    On failure, first check:
        - Whether the matcher re-applied a replacement by following new
    """
    mapping = (
        "version = 1\n"
        '[[replacement]]\nold = "alpha"\nnew = "beta"\nkind = "prose"\n'
        '[[replacement]]\nold = "beta"\nnew = "alpha"\nkind = "prose"\n'
    )
    findings = _check("first alpha then beta end\n", mapping, Config())
    assert sorted(finding.message.split("'")[1] for finding in findings) == ["alpha", "beta"]


@pytest.mark.parametrize(
    ("scope", "path", "expected"),
    [
        ('scope = ["docs/*"]', "docs/guide.md", 1),
        ('scope = ["docs/*"]', "README.md", 0),
        ('scope = ["!archive/*"]', "archive/README.md", 0),
        ('scope = ["!archive/*"]', "docs/guide.md", 1),
    ],
)
def test_scope_globs_include_and_exclude(scope: str, path: str, expected: int):
    """
    [Unit] detectors deprecated_refs: verifies scope globs gate documents, including exclusion (R5).

    Scenario:
        Given a prose entry carrying a positive or a bang-excluded scope glob and documents at
            various relative paths
        When check_text runs with default config
        Then a positive scope limits the entry to matching paths while a bang-excluded scope
            exempts the archive path (the historical-archive exemption).

    Boundaries:
        - Focus: per-document scope-glob gating and the archive exemption (R5)
        - Fixtures/params: scope, path, expected

    On failure, first check:
        - Whether _document_in_scope evaluated positives and excludes in the right order
    """
    mapping = f'version = 1\n[[replacement]]\nold = "Legacy"\nnew = "Modern"\nkind = "prose"\n{scope}\n'
    assert len(_check("the Legacy thing\n", mapping, Config(), path=path)) == expected


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (Config(deprecated_check_prose=False), 1),
        (Config(deprecated_check_links=False), 1),
        (Config(deprecated_check_prose=False, deprecated_check_links=False), 0),
    ],
)
def test_sub_option_toggles_select_substrates(config: Config, expected: int):
    """
    [Unit] detectors deprecated_refs: verifies the prose and link toggles select substrates (R5/R8).

    Scenario:
        Given a mapping with one prose entry and one link entry and a document that triggers both
        When check_text runs with each sub-check toggled off
        Then disabling prose suppresses only the prose/identifier match, disabling links suppresses
            only the link match, and disabling both yields zero findings.

    Boundaries:
        - Focus: the deprecated_check_prose / deprecated_check_links substrate toggles (R5)
        - Fixtures/params: config, expected

    On failure, first check:
        - Whether the toggle gated the wrong substrate
    """
    mapping = (
        "version = 1\n"
        '[[replacement]]\nold = "Legacy"\nnew = "Modern"\nkind = "prose"\n'
        '[[replacement]]\nold = "old.md"\nnew = "new.md"\nkind = "link"\n'
    )
    findings = _check("the Legacy term\n\n[x](old.md)\n", mapping, config)
    assert len(findings) == expected


def test_multiple_occurrences_same_line_are_deterministic_and_deduped():
    """
    [Unit] detectors deprecated_refs: verifies one-per-occurrence counting and dedup (R10).

    Scenario:
        Given a prose entry and a document with two distinct occurrences of the old on one line
        When check_text runs with default config
        Then two findings are produced in ascending source-offset order, and an exact-duplicate
            occurrence tuple would collapse to one.

    Boundaries:
        - Focus: deterministic one-per-occurrence ordering and duplicate collapse (R10)
        - Fixtures/params: none

    On failure, first check:
        - Whether occurrences were sorted by (line, offset, entry) and deduped
    """
    mapping = 'version = 1\n[[replacement]]\nold = "obso"\nnew = "fresh"\nkind = "prose"\n'
    findings = _check("obso here and obso again\n", mapping, Config())
    assert len(findings) == 2
    assert all(finding.line == 1 for finding in findings)


def test_repeated_scans_are_stable():
    """
    [Unit] detectors deprecated_refs: verifies identical findings across repeated scans (R10).

    Scenario:
        Given a fixed mapping and document
        When check_text runs twice
        Then both runs produce byte-identical ordered messages and line numbers.

    Boundaries:
        - Focus: run-to-run determinism (R10)
        - Fixtures/params: none

    On failure, first check:
        - Whether a set/dict iteration order leaked into the output ordering
    """
    mapping = 'version = 1\n[[replacement]]\nold = "Legacy"\nnew = "Modern"\nkind = "prose"\n'
    text = "Legacy one\nLegacy two\n"
    first = _check(text, mapping, Config())
    second = _check(text, mapping, Config())
    assert _messages(first) == _messages(second)
    assert [f.line for f in first] == [f.line for f in second]


def test_opt_in_gate_unset_returns_nothing_with_zero_filesystem_access(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors deprecated_refs: verifies an empty mapping option performs zero I/O (R8).

    Scenario:
        Given the default config where deprecated_references_file is empty and any os.stat or
            open would raise, scanned over a document tuple
        When detect runs
        Then it returns no findings without performing a single filesystem call, so an unconfigured
            repo is inert.

    Boundaries:
        - Focus: the opt-in gate and its zero-I/O guarantee (R8)
        - Fixtures/params: monkeypatch

    On failure, first check:
        - Whether detect short-circuited before canonicalising the root or reading any file
    """

    def _boom(*_args: object, **_kwargs: object) -> object:
        """Fail if any filesystem access is attempted while the gate is off."""
        raise AssertionError("DS115 performed filesystem access with no mapping configured")

    monkeypatch.setattr(os, "stat", _boom)
    monkeypatch.setattr(os.path, "realpath", _boom)
    document = models.Document("README.md", 10)
    assert dep.detect(_ROOT, (document,), Config()) == ()


def test_regex_metacharacter_old_is_matched_literally():
    """
    [Unit] detectors deprecated_refs: verifies a regex-metacharacter old never compiles as a pattern (R4).

    Scenario:
        Given a prose entry whose old is the catastrophic-looking literal "(a+)+" and a document
            containing that literal once plus benign text a regex would backtrack on
        When check_text runs with default config
        Then the literal occurrence is matched exactly once with no stall and no spurious match on
            the plain "aaaa" run.

    Boundaries:
        - Focus: literal matching of regex metacharacters, no ReDoS (R4)
        - Fixtures/params: none

    On failure, first check:
        - Whether the old was ever handed to re.compile
    """
    mapping = 'version = 1\n[[replacement]]\nold = "(a+)+"\nnew = "SAFE"\nkind = "prose"\n'
    findings = _check("aaaa and the literal (a+)+ token\n", mapping, Config())
    assert len(findings) == 1


def test_echo_neutralizes_control_bytes_in_configured_path():
    """
    [Unit] detectors deprecated_refs: verifies a control-laden configured path is repr-escaped (R6).

    Scenario:
        Given a valid mapping whose configured path carries NUL/ESC/CR/LF bytes (the path is not
            schema-validated, unlike old/new which reject control bytes at load) and whose old
            matches a prose token
        When check_text builds the finding message
        Then the message contains no raw control byte and renders a single line, so a report sink
            cannot be driven to inject a second command.

    Boundaries:
        - Focus: the bounded repr-escaped echo of the provenance path (R6)
        - Fixtures/params: none

    On failure, first check:
        - Whether _echo was applied to the configured path in the message
    """
    raw_mapping = 'version = 1\n[[replacement]]\nold = "Legacy"\nnew = "Modern"\nkind = "prose"\n'
    mapping = dep.parse_mapping(raw_mapping, "dir/\x1b]0;x\x07map\r\n.toml")
    findings = dep.check_text("the Legacy term\n", "README.md", _ROOT, mapping, Config())
    assert len(findings) == 1
    message = findings[0].message
    assert "\n" not in message.rstrip("\n")
    assert "\x1b" not in message and "\x00" not in message
    assert all(ord(character) >= 0x20 and ord(character) != 0x7F for character in message)


# --- mapping loader readiness discipline (R1/R3) -------------------------------


def test_load_mapping_outside_root_raises():
    """
    [Unit] detectors deprecated_refs: verifies an out-of-root mapping path fails closed (R1/R3).

    Scenario:
        Given a configured mapping path that lexically escapes the scan root via ../
        When load_mapping runs
        Then it raises ConfigError before any open and the message echoes only the configured path.

    Boundaries:
        - Focus: defensive containment of an injected out-of-root mapping path (R1)
        - Fixtures/params: none

    On failure, first check:
        - Whether is_ds116_owned / resolver containment ran before any stat or open
    """
    with pytest.raises(ConfigError, match="escapes the documentation root"):
        dep.load_mapping(_ROOT, "../secrets.toml")


def test_load_mapping_nonexistent_raises(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies a missing mapping file fails closed (R3).

    Scenario:
        Given a configured mapping path that does not exist inside the root
        When load_mapping runs
        Then it raises ConfigError (the unreadable readiness error), never a silent clean result.

    Boundaries:
        - Focus: fail-closed readiness on a missing mapping (R3)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the os.stat OSError branch re-wrapped as ConfigError
    """
    root = Path(os.path.realpath(tmp_path))
    with pytest.raises(ConfigError, match="could not be read"):
        dep.load_mapping(root, "missing.toml")


def test_load_mapping_directory_raises(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies a directory mapping path fails closed (R1/R3).

    Scenario:
        Given a configured mapping path that names an in-root directory
        When load_mapping runs
        Then it raises ConfigError because the path is not a regular file.

    Boundaries:
        - Focus: the stat + S_ISREG gate before any open (R1)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether S_ISREG rejected the directory before open
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "mapdir.toml").mkdir()
    with pytest.raises(ConfigError, match="not a regular file"):
        dep.load_mapping(root, "mapdir.toml")


def test_load_mapping_oversized_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors deprecated_refs: verifies an oversized mapping fails closed before read (R1).

    Scenario:
        Given a regular in-root mapping whose size exceeds the (test-lowered) byte cap
        When load_mapping runs
        Then it raises ConfigError on the size check before reading or parsing the file.

    Boundaries:
        - Focus: the st_size cap enforced before the bounded read (R1)
        - Fixtures/params: tmp_path, monkeypatch

    On failure, first check:
        - Whether the size cap was checked before open
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "big.toml").write_text("version = 1\n" + "# pad\n" * 50, encoding="utf-8")
    monkeypatch.setattr(dep, "_MAX_MAPPING_BYTES", 8)
    with pytest.raises(ConfigError, match="larger than"):
        dep.load_mapping(root, "big.toml")


def test_load_mapping_non_utf8_raises(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies a non-UTF-8 mapping fails closed (R3).

    Scenario:
        Given a regular in-root mapping whose bytes are not valid UTF-8
        When load_mapping runs
        Then it raises ConfigError (unreadable), never leaking the raw decode error text.

    Boundaries:
        - Focus: the decode-failure re-wrap as a bounded ConfigError (R3)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether UnicodeDecodeError was re-wrapped rather than propagated raw
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "bad.toml").write_bytes(b"\xff\xfe version = 1")
    with pytest.raises(ConfigError, match="could not be read"):
        dep.load_mapping(root, "bad.toml")


def test_load_mapping_fifo_raises_without_opening(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies a FIFO mapping is never opened (R1).

    Scenario:
        Given a runtime FIFO committed where the configured mapping path points
        When load_mapping runs
        Then it raises ConfigError on the non-regular-file check and never blocks opening the FIFO.

    Boundaries:
        - Focus: the S_ISREG gate preventing a hang on a special file (R1)
        - Fixtures/params: tmp_path; skipped with a reason when os.mkfifo is unavailable

    On failure, first check:
        - Whether S_ISREG ran before any open of the FIFO
    """
    if not hasattr(os, "mkfifo"):
        pytest.skip("os.mkfifo unavailable on this platform")
    root = Path(os.path.realpath(tmp_path))
    os.mkfifo(root / "pipe.toml")
    with pytest.raises(ConfigError, match="not a regular file"):
        dep.load_mapping(root, "pipe.toml")


def test_load_mapping_symlink_out_raises(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies an in-root symlink to an outside file fails closed (R1).

    Scenario:
        Given an in-root mapping path that is a symlink pointing to a file outside the scan root
        When load_mapping runs
        Then it raises ConfigError via the escapes_via_symlink gate, never reading the outside file.

    Boundaries:
        - Focus: the symlink-escape gate before any open (R1)
        - Fixtures/params: tmp_path; skipped with a reason when symlinks are unavailable

    On failure, first check:
        - Whether escapes_via_symlink ran before stat/open
    """
    root = Path(os.path.realpath(tmp_path / "root"))
    root.mkdir()
    outside = tmp_path / "outside.toml"
    outside.write_text("version = 1\n", encoding="utf-8")
    try:
        (root / "link.toml").symlink_to(outside)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symlinks unavailable: {error}")
    with pytest.raises(ConfigError, match="escapes the documentation root"):
        dep.load_mapping(root, "link.toml")


def test_load_mapping_valid_reads_entries(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies a valid in-root mapping parses its entries (R1).

    Scenario:
        Given a valid regular in-root TOML mapping with one entry
        When load_mapping runs
        Then it returns a DeprecatedMapping carrying the configured path and the parsed entry.

    Boundaries:
        - Focus: the happy path of the bounded read and parse (R1)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the bounded read decoded and parsed the committed file
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "map.toml").write_text(
        'version = 1\n[[replacement]]\nold = "X"\nnew = "Y"\nkind = "prose"\n', encoding="utf-8"
    )
    mapping = dep.load_mapping(root, "map.toml")
    assert mapping.configured_path == "map.toml"
    assert len(mapping.replacements) == 1
    assert mapping.replacements[0].old == "X"


# --- schema validation (R2) ----------------------------------------------------


@pytest.mark.parametrize(
    "raw_text",
    [
        "bogus = 1\nversion = 1\n",
        "version = 2\n",
        '[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\n',
        'version = 1\nreplacement = "nope"\n',
        'version = 1\n[[replacement]]\nnew = "b"\nkind = "prose"\n',
        'version = 1\n[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\nextra = 1\n',
        'version = 1\n[[replacement]]\nold = ""\nnew = "b"\nkind = "prose"\n',
        'version = 1\n[[replacement]]\nold = "   "\nnew = "b"\nkind = "prose"\n',
        'version = 1\n[[replacement]]\nold = "a\\u0000"\nnew = "b"\nkind = "prose"\n',
        'version = 1\n[[replacement]]\nold = "a"\nnew = "b"\nkind = "unknown"\n',
        'version = 1\n[[replacement]]\nold = 7\nnew = "b"\nkind = "prose"\n',
        'version = 1\n[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\nscope = "x"\n',
        'version = 1\n[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\nscope = ["a\\u0000"]\n',
        'version = 1\n[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\n[[replacement]]\nold = "a"\nnew = "c"\nkind = "prose"\n',
        'version = 1\n[[replacement]]\nold = "a"\nold = "b"\nnew = "c"\nkind = "prose"\n',
        "this is not = valid = toml ===\n",
    ],
)
def test_parse_mapping_rejects_hostile_schema(raw_text: str):
    """
    [Unit] detectors deprecated_refs: verifies every hostile mapping shape raises ConfigError (R2/R3).

    Scenario:
        Given a mapping with an unknown top key, wrong/missing version, non-list replacement,
            missing/unknown/mistyped entry key, empty/control/invalid old or kind, a bad scope, a
            cross-entry duplicate old, a literal duplicate key, or unparseable TOML
        When parse_mapping runs
        Then each case raises ConfigError rather than parsing into a usable mapping.

    Boundaries:
        - Focus: the full schema contract and fail-closed parsing (R2/R3)
        - Fixtures/params: raw_text

    On failure, first check:
        - Which schema branch failed to reject its hostile input
    """
    with pytest.raises(ConfigError):
        dep.parse_mapping(raw_text, "deprecated.toml")


def test_parse_mapping_accepts_same_old_in_distinct_scopes():
    """
    [Unit] detectors deprecated_refs: verifies the same old under distinct scopes is not a conflict (R2).

    Scenario:
        Given two entries with the same old but different scope sets
        When parse_mapping runs
        Then both entries are accepted because the conflict key is (old, scope-set), so scoped
            overrides remain valid.

    Boundaries:
        - Focus: the duplicate/conflict definition (same old AND same scope) (R2)
        - Fixtures/params: none

    On failure, first check:
        - Whether the conflict key ignored scope and over-rejected
    """
    mapping = dep.parse_mapping(
        "version = 1\n"
        '[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\nscope = ["docs/*"]\n'
        '[[replacement]]\nold = "a"\nnew = "c"\nkind = "prose"\nscope = ["api/*"]\n',
        "deprecated.toml",
    )
    assert len(mapping.replacements) == 2


def test_parse_mapping_drops_raw_tomllib_text(tmp_path: Path):
    """
    [Unit] detectors deprecated_refs: verifies a parse error never echoes raw tomllib text (R6).

    Scenario:
        Given an unparseable TOML mapping whose offending token is a recognizable secret string
        When parse_mapping raises
        Then the ConfigError message names only the configured path and the fixed phrase, never the
            offending content or the raw tomllib line/column text.

    Boundaries:
        - Focus: dropping the raw tomllib exception text from the message (R6)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the tomllib exception was formatted into the message
    """
    with pytest.raises(ConfigError) as info:
        dep.parse_mapping("version = 1\nSECRETTOKEN broken ===\n", "deprecated.toml")
    assert "SECRETTOKEN" not in str(info.value)
    assert "could not be parsed" in str(info.value)


# --- config validation ---------------------------------------------------------


def test_config_standalone_and_pyproject_load_deprecated_options(tmp_path: Path):
    """
    [Unit] config: verifies the deprecated_* options load from standalone and pyproject TOML.

    Scenario:
        Given a standalone doc_sentinel.toml and, separately, a pyproject [tool.doc_sentinel] table
            that set the mapping path and the three sub-option bools
        When load_config reads each
        Then the typed Config carries the configured path and bool values from both sources.

    Boundaries:
        - Focus: typed validation of the DS115 options from both config surfaces
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the option names are present in _CONFIG_OPTIONS and the bool/str validators
    """
    standalone = tmp_path / "a"
    standalone.mkdir()
    (standalone / "doc_sentinel.toml").write_text(
        'deprecated_references_file = "docs/dep.toml"\n'
        "deprecated_check_prose = false\n"
        "deprecated_check_links = false\n"
        "deprecated_case_sensitive = false\n",
        encoding="utf-8",
    )
    config = load_config(standalone)
    assert config.deprecated_references_file == "docs/dep.toml"
    assert config.deprecated_check_prose is False
    assert config.deprecated_check_links is False
    assert config.deprecated_case_sensitive is False

    project = tmp_path / "b"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\ndeprecated_references_file = "dep.toml"\ndeprecated_check_prose = false\n',
        encoding="utf-8",
    )
    wrapped = load_config(project)
    assert wrapped.deprecated_references_file == "dep.toml"
    assert wrapped.deprecated_check_prose is False


def test_config_rejects_non_bool_sub_option(tmp_path: Path):
    """
    [Unit] config: verifies a non-boolean deprecated sub-option raises ConfigError.

    Scenario:
        Given a standalone doc_sentinel.toml that sets deprecated_check_prose to a string
        When load_config reads it
        Then it raises ConfigError because the sub-option is boolean-typed.

    Boundaries:
        - Focus: bool typing of the DS115 sub-options
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether deprecated_check_prose is in the _BOOL_OPTIONS validator list
    """
    (tmp_path / "doc_sentinel.toml").write_text('deprecated_check_prose = "yes"\n', encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_config_injected_values_reach_the_detector():
    """
    [Unit] detectors deprecated_refs: verifies an injected Config drives check_text behaviour.

    Scenario:
        Given a hand-built Config that disables the link sub-check
        When check_text runs over a document with a link occurrence
        Then the injected toggle is honoured and the link match is suppressed, proving the detector
            reads the effective Config a library caller injects.

    Boundaries:
        - Focus: injected-Config propagation to the detector (config independence)
        - Fixtures/params: none

    On failure, first check:
        - Whether settings fell back to defaults instead of the injected Config
    """
    mapping = 'version = 1\n[[replacement]]\nold = "old.md"\nnew = "new.md"\nkind = "link"\n'
    assert _check("[x](old.md)\n", mapping, Config(deprecated_check_links=False)) == ()


# --- linear-cost floods (R4) ----------------------------------------------------


def test_matching_scales_linearly_with_entry_count():
    """
    [Unit] detectors deprecated_refs: verifies cost stays linear as entry count grows (R4).

    Scenario:
        Given mappings with a doubling number of distinct prose entries and a fixed document that
            triggers exactly five of them
        When check_text runs across the series
        Then CPU time scales near-linearly with entry count, proving dict-keyed lookup rather than
            O(entries x document bytes).

    Boundaries:
        - Focus: linear entry-count scaling with a fixed finding count (R4)
        - Fixtures/params: internal doubling series

    On failure, first check:
        - Whether matching iterated every entry per document token
    """
    document = "term0 term1 term2 term3 term4 and some filler words here\n"

    def build(size: int) -> dep.DeprecatedMapping:
        """Build a mapping with ``size`` distinct prose entries."""
        body = "version = 1\n" + "".join(
            f'[[replacement]]\nold = "term{i}"\nnew = "fresh{i}"\nkind = "prose"\n' for i in range(size)
        )
        return dep.parse_mapping(body, "deprecated.toml")

    def run(mapping: dep.DeprecatedMapping) -> tuple[models.Finding, ...]:
        """Run check_text over the fixed document."""
        return dep.check_text(document, "README.md", _ROOT, mapping, Config())

    assert_scales_linearly(build, run, [500, 1000, 2000, 4000], expected_count=5, label="entries")


def test_matching_scales_linearly_on_one_long_line():
    """
    [Unit] detectors deprecated_refs: verifies a single very long line scales linearly (R4).

    Scenario:
        Given a fixed small mapping and a single physical line of a doubling number of distinct,
            non-repeating non-matching tokens plus one matching token
        When check_text runs across the series
        Then CPU time scales near-linearly with line length and the finding count stays one.

    Boundaries:
        - Focus: linear single-line tokenization cost (R4)
        - Fixtures/params: internal doubling series

    On failure, first check:
        - Whether tokenization or matching rescanned the line tail
    """
    mapping = dep.parse_mapping(
        'version = 1\n[[replacement]]\nold = "needle"\nnew = "pin"\nkind = "prose"\n', "deprecated.toml"
    )

    def build(size: int) -> str:
        """Build a one-line document with ``size`` distinct filler tokens and one match."""
        return "needle " + " ".join(f"w{i}" for i in range(size)) + "\n"

    def run(document: str) -> tuple[models.Finding, ...]:
        """Run check_text over the long single line."""
        return dep.check_text(document, "README.md", _ROOT, mapping, Config())

    assert_scales_linearly(build, run, [2000, 4000, 8000, 16000], expected_count=1, label="long-line")


def test_matching_scales_linearly_with_occurrence_count():
    """
    [Unit] detectors deprecated_refs: verifies many occurrences across lines scale linearly (R4/R10).

    Scenario:
        Given a fixed mapping and a document of a doubling number of lines each holding one distinct
            occurrence of the old
        When check_text runs across the series
        Then CPU time scales near-linearly and the finding count equals the line count (one per
            distinct occurrence).

    Boundaries:
        - Focus: linear multi-line occurrence cost and one-per-occurrence counting (R4/R10)
        - Fixtures/params: internal doubling series

    On failure, first check:
        - Whether sorting or dedup introduced a super-linear step
    """
    mapping = dep.parse_mapping(
        'version = 1\n[[replacement]]\nold = "obso"\nnew = "fresh"\nkind = "prose"\n', "deprecated.toml"
    )

    def build(size: int) -> str:
        """Build a document of ``size`` lines each with one distinct occurrence."""
        return "".join(f"line {i} has obso here\n" for i in range(size))

    def run(document: str) -> tuple[models.Finding, ...]:
        """Run check_text over the multi-line document."""
        return dep.check_text(document, "README.md", _ROOT, mapping, Config())

    assert_scales_linearly(build, run, [1000, 2000, 4000, 8000], expected_count=lambda size: size, label="occurrences")


def test_scope_matching_scales_linearly_with_pattern_count(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors deprecated_refs: verifies a huge scope list scales linearly per document (R4).

    Scenario:
        Given an entry carrying a doubling number of non-matching exclude globs (the cap lifted for
            the test) and a fixed matching document
        When check_text runs across the series
        Then CPU time scales near-linearly with the pattern count, proving scope is matched once per
            document on a bounded pattern list rather than per token.

    Boundaries:
        - Focus: linear once-per-document scope-glob cost (R4)
        - Fixtures/params: monkeypatch; internal doubling series

    On failure, first check:
        - Whether scope globs were evaluated per token instead of once per document
    """
    monkeypatch.setattr(dep, "_MAX_SCOPE_PATTERNS", 1 << 20)
    document = "the Legacy term appears here\n"

    def build(size: int) -> dep.DeprecatedMapping:
        """Build a mapping whose single entry carries ``size`` exclude globs."""
        globs = ", ".join(f'"!nomatch{i}/*"' for i in range(size))
        body = f'version = 1\n[[replacement]]\nold = "Legacy"\nnew = "Modern"\nkind = "prose"\nscope = [{globs}]\n'
        return dep.parse_mapping(body, "deprecated.toml")

    def run(mapping: dep.DeprecatedMapping) -> tuple[models.Finding, ...]:
        """Run check_text over the fixed matching document."""
        return dep.check_text(document, "README.md", _ROOT, mapping, Config())

    assert_scales_linearly(build, run, [1000, 2000, 4000, 8000], expected_count=1, label="scope")


def _shared_first_token_mapping_body(size: int) -> str:
    """Return a mapping of ``size`` multi-word olds that all share the first token.

    Every ``old`` is ``aaaa z{i}``, so all ``size`` entries collapse into the one
    ``aaaa`` first-token bucket -- the shared-prefix shape a first-token-only index
    fans a single document ``aaaa`` token out across, one tail compare per entry.

    :param size: Number of entries sharing the first token.
    :returns: The TOML mapping body.
    """
    return "version = 1\n" + "".join(
        f'[[replacement]]\nold = "aaaa z{index}"\nnew = "r{index}"\nkind = "prose"\n' for index in range(size)
    )


def test_matching_scales_linearly_with_shared_first_token_on_one_line():
    """
    [Unit] detectors deprecated_refs: verifies a shared-first-token bucket stays linear on one line (R4).

    Scenario:
        Given a mapping whose ``size`` multi-word olds all share the first token ``aaaa`` and a single
            physical line of ``size`` ``aaaa`` tokens followed by one real ``aaaa z0`` occurrence
        When check_text runs across a doubling series
        Then exactly one finding is produced at every size and CPU time scales near-linearly, proving the
            token trie keys its second step on the second token rather than fanning the shared ``aaaa``
            bucket out to one tail compare per entry (the O(entries x document tokens) HIGH DoS).

    Boundaries:
        - Focus: the shared-first-token fan-out the first-token-bucket matcher was quadratic on (R4)
        - Fixtures/params: internal doubling series over both entry count and document tokens

    On failure, first check:
        - Whether the matcher reverted to a first-token-only bucket with a per-entry tail compare
    """

    def build(size: int) -> tuple[dep.DeprecatedMapping, str]:
        """Build the shared-first-token mapping and a one-line document of ``size`` ``aaaa`` tokens."""
        mapping = dep.parse_mapping(_shared_first_token_mapping_body(size), "deprecated.toml")
        return (mapping, ("aaaa " * size) + "aaaa z0\n")

    def run(payload: tuple[dep.DeprecatedMapping, str]) -> tuple[models.Finding, ...]:
        """Run check_text over the one-line shared-first-token document."""
        mapping, document = payload
        return dep.check_text(document, "README.md", _ROOT, mapping, Config())

    assert_scales_linearly(build, run, [500, 1000, 2000, 4000], expected_count=1, label="shared-first-token-line")


def test_matching_scales_linearly_with_shared_first_token_across_lines():
    """
    [Unit] detectors deprecated_refs: verifies a shared-first-token bucket stays linear across lines (R4).

    Scenario:
        Given a mapping whose ``size`` multi-word olds all share the first token ``aaaa`` and a document of
            ``size`` single-token ``aaaa`` lines followed by one real ``aaaa z0`` line
        When check_text runs across a doubling series
        Then exactly one finding is produced at every size and CPU time scales near-linearly, proving the
            per-line match cost is bounded by the trie depth and not by the shared bucket size.

    Boundaries:
        - Focus: the multi-line form of the shared-first-token fan-out (R4)
        - Fixtures/params: internal doubling series over both entry count and line count

    On failure, first check:
        - Whether each lone ``aaaa`` line iterated every entry in the shared bucket
    """

    def build(size: int) -> tuple[dep.DeprecatedMapping, str]:
        """Build the shared-first-token mapping and a ``size``-line document of lone ``aaaa`` tokens."""
        mapping = dep.parse_mapping(_shared_first_token_mapping_body(size), "deprecated.toml")
        return (mapping, "".join("aaaa\n" for _ in range(size)) + "aaaa z0\n")

    def run(payload: tuple[dep.DeprecatedMapping, str]) -> tuple[models.Finding, ...]:
        """Run check_text over the multi-line shared-first-token document."""
        mapping, document = payload
        return dep.check_text(document, "README.md", _ROOT, mapping, Config())

    assert_scales_linearly(build, run, [500, 1000, 2000, 4000], expected_count=1, label="shared-first-token-lines")


# --- bounded repr-escaped echo of attacker TOML keys and parser crashes (R3/R6) ---


@pytest.mark.parametrize(
    "raw_text",
    [
        'version = 1\n"\\u001b]0;PWNED\\u0007 injected ' + "A" * 10_000 + '" = true\n',
        'version = 1\n[[replacement]]\nold = "a"\nnew = "b"\nkind = "prose"\n'
        '"\\u001b[31mEVIL\\u0007\\r\\n\\u0000 ' + "B" * 10_000 + '" = 1\n',
    ],
)
def test_unknown_key_configerror_is_bounded_and_repr_escaped(raw_text: str):
    """
    [Unit] detectors deprecated_refs: verifies attacker TOML key names are bounded and escaped (R6).

    Scenario:
        Given a mapping carrying an unknown top-level key and, separately, an unknown entry key, each a
            TOML quoted key whose unicode escapes decode to raw ESC/BEL/CR/LF/NUL bytes and 10,000 characters
        When parse_mapping rejects the unknown key
        Then the ConfigError names "unknown" keys but contains no raw control byte, stays well under the
            unbounded length (the per-key echo bound plus a bounded "... N more" tail), so a report sink
            cannot be driven to inject a terminal escape, forge a second log line, or flood the log.

    Boundaries:
        - Focus: routing every attacker-controlled TOML key through the bounded _echo (R6, BLOCK #5)
        - Fixtures/params: an unknown top-level key and an unknown entry key, both hostile

    On failure, first check:
        - Whether the unknown-key message still used ", ".join(sorted(unknown)) instead of _echo_keys
    """
    with pytest.raises(ConfigError) as info:
        dep.parse_mapping(raw_text, "deprecated.toml")
    message = str(info.value)
    assert "unknown" in message
    assert all(ord(character) >= 0x20 and ord(character) != 0x7F for character in message)
    assert "\x1b" not in message and "\x07" not in message and "\x00" not in message
    assert "\r" not in message and "\n" not in message
    assert len(message) < 300


def test_many_unknown_keys_are_capped_with_remainder_count():
    """
    [Unit] detectors deprecated_refs: verifies a flood of unknown keys is capped with a remainder (R6).

    Scenario:
        Given a mapping with many unknown top-level keys
        When parse_mapping rejects them
        Then the ConfigError lists at most _MAX_LISTED_KEYS keys and appends a bounded "... N more" tail, so a
            flood of keys cannot grow the message without bound.

    Boundaries:
        - Focus: the listed-key cap and remainder tail of _echo_keys (R6)
        - Fixtures/params: none

    On failure, first check:
        - Whether _echo_keys sorted, capped at _MAX_LISTED_KEYS and emitted the remainder count
    """
    keys = "\n".join(f'"zz{index}" = true' for index in range(dep._MAX_LISTED_KEYS + 7))
    with pytest.raises(ConfigError) as info:
        dep.parse_mapping(f"version = 1\n{keys}\n", "deprecated.toml")
    message = str(info.value)
    assert "... 7 more" in message
    assert message.count(",") == dep._MAX_LISTED_KEYS


def test_deeply_nested_toml_raises_bounded_configerror_not_recursionerror():
    """
    [Unit] detectors deprecated_refs: verifies deeply nested TOML fails closed as ConfigError (R3).

    Scenario:
        Given a mapping well under the byte cap whose single value is a deeply nested array that drives
            tomllib's recursive-descent parser into a RecursionError
        When parse_mapping runs
        Then it raises the bounded readiness ConfigError (naming only the configured path, the fixed
            "could not be parsed" phrase), never letting the raw RecursionError escape to a traceback.

    Boundaries:
        - Focus: catching RecursionError/ValueError parser failures and re-wrapping them (R3)
        - Fixtures/params: none

    On failure, first check:
        - Whether parse_mapping's except clause still caught only tomllib.TOMLDecodeError
    """
    depth = 50_000
    raw_text = "version = 1\nx = " + "[" * depth + "]" * depth + "\n"
    with pytest.raises(ConfigError, match="could not be parsed"):
        dep.parse_mapping(raw_text, "deprecated.toml")


def test_prose_in_indented_code_block_is_a_documented_false_positive():
    """
    [Unit] detectors deprecated_refs: pins the indented-code / HTML-block prose-mask false positive (R5).

    Scenario:
        Given a prose mapping and a document that places the old token in a 4-space indented code block, in an
            HTML block, and (as a control) in a fenced block
        When check_text runs with default config
        Then the fenced occurrence is exempt (the scanner masks it) but the indented-code and HTML-block
            occurrences are reported -- the one documented false-positive direction, pinned here so a future
            mask extension is a deliberate, tested change rather than a silent behaviour drift.

    Boundaries:
        - Focus: the documented indented-code / HTML-block prose-mask gap (R5, markdown_dialect.md)
        - Fixtures/params: none

    On failure, first check:
        - Whether the shared scanner began exposing indented-code / HTML-block spans (then extend _masked_text)
    """
    mapping = 'version = 1\n[[replacement]]\nold = "oldname"\nnew = "newname"\nkind = "prose"\n'
    assert _check("# T\n\n```\noldname fenced\n```\n", mapping, Config()) == ()
    assert len(_check("# T\n\ntext\n\n    oldname indented\n", mapping, Config())) == 1
    assert len(_check("# T\n\n<div>\noldname in html\n</div>\n", mapping, Config())) == 1
