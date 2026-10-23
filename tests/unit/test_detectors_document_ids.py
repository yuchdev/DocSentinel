"""Unit tests for DS114 duplicate-stable-document-identifier recognition.

These tests use tiny inline frontmatter strings and call the detector's pure
cores directly: :func:`~docsentinel.detectors.document_ids.extract_frontmatter_field`
(the minimal scalar frontmatter reader),
:func:`~docsentinel.detectors.document_ids.normalize_identity`, and
:func:`~docsentinel.detectors.document_ids.check_documents` (the corpus-level
collision core). Detection over committed Markdown assets is the job of the Story
12.0 Task 03 integration suite, which runs once ``DS114`` is registered with its
``tests/assets/ds114/*`` fixtures in Task 02; this module exercises the pure cores
in isolation and pins the deliberately-unregistered Task 01 state.

Every algorithm bullet, exclusion, and interaction of Story 12.0 Task 01 has a
test here, plus the frontmatter-reader edge cases (quotes, inline comments, BOM,
CRLF, tabs, empty/null values, numbers/booleans, unsupported structures, an
unterminated block, duplicate keys, a NUL byte, Unicode confusables, NFC
equivalence, and whitespace collapse), the config-driven options, the bounded
repr-escaped echo, and single-line and multi-line linear-scaling floods.

It also pins the security-review divergence fixes: multi-line plain/quoted scalar
continuations and double-quoted escapes outside the exactly-YAML subset defer to
UNSUPPORTED (never a truncated or mis-decoded id); YAML null spellings read as
absent; quoted/explicit/merge-key spellings of the field defer rather than read as
absent; and a frozen, PyYAML-verified differential corpus asserts the reader never
returns a concrete id that disagrees with a real parser (no YAML library is imported
in the test).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import document_ids as doc_ids
from tests.timing_helpers import assert_scales_linearly


def _paths(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the offending path of each finding in order.

    :param findings: The findings to describe.
    :returns: The ordered finding paths.
    """
    return [finding.path for finding in findings]


def _messages(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the message of each finding in order.

    :param findings: The findings to describe.
    :returns: The ordered finding messages.
    """
    return [finding.message for finding in findings]


def _doc(identity_body: str) -> str:
    """Return a tiny document whose opening frontmatter contains ``identity_body``.

    :param identity_body: The frontmatter body between the ``---`` fences.
    :returns: A complete document string with a trivial prose body.
    """
    return f"---\n{identity_body}\n---\n\n# Title\n\nBody.\n"


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors document_ids: verifies DS114 metadata and its always-active registration.

    Scenario:
        Given the DS114 rule object built in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact (fast profile, error severity, no opt-in option) and the
            rule is registered in both RULES and ANALYZERS as an always-active, default-on fast
            rule (Story 12.0 Task 02).

    Boundaries:
        - Focus: rule identity and its always-active registration
        - Fixtures/params: none

    On failure, first check:
        - Whether a metadata field (profile, severity, opt_in_option) drifted
        - Whether register_rule or the ANALYZERS wiring was removed or gained an opt_in_option
    """
    assert doc_ids.DS114.code == "DS114"
    assert doc_ids.DS114.profile == "fast"
    assert doc_ids.DS114.severity == "error"
    assert doc_ids.DS114.title == "Duplicate stable document identifiers"
    assert doc_ids.DS114.opt_in_option == ""
    assert rules.RULES["DS114"] is doc_ids.DS114
    assert rules.ANALYZERS["DS114"] is doc_ids.detect


@pytest.mark.parametrize(
    ("body", "expected_value"),
    [
        ("id: alpha", "alpha"),
        ('id: "alpha"', "alpha"),
        ("id: 'alpha'", "alpha"),
        ("id: alpha # trailing comment", "alpha"),
        ("id: a#b", "a#b"),
        ("id: 123", "123"),
        ("id: true", "true"),
        ('id: "  spaced  "', "  spaced  "),
        ("id: 'it''s'", "it's"),
        ('id: "a\\tb"', "a\tb"),
        ("title: T\nid: beta", "beta"),
        ("id : spaced-colon", "spaced-colon"),
    ],
)
def test_reader_extracts_supported_scalars(body: str, expected_value: str):
    """
    [Unit] detectors document_ids: verifies the reader extracts every supported scalar form.

    Scenario:
        Given an opening frontmatter block whose configured field carries a plain, single- or
            double-quoted scalar, an inline-commented plain scalar, a number, a boolean, or a
            quoted value with surrounding whitespace or an escape
        When the minimal frontmatter reader parses it
        Then the raw (un-normalized) scalar text is returned verbatim with a one-based line,
            proving each supported shape is recognised as a literal-text identity.

    Boundaries:
        - Focus: the supported scalar subset of the minimal reader (plain/quoted/comment/escape)
        - Fixtures/params: parametrized over the supported scalar shapes

    On failure, first check:
        - The quote/comment/escape branches of _interpret_value and the quote parsers
        - Whether a number/boolean was wrongly type-coerced instead of kept as text
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._ID
    assert reading.value == expected_value
    assert reading.line is not None


def test_reader_reports_identity_line_is_one_based():
    """
    [Unit] detectors document_ids: verifies the identity line is the one-based line of the field.

    Scenario:
        Given a frontmatter block where the id field is the second line of the block
        When the reader parses it
        Then the reported line is the field's physical one-based line within the document.

    Boundaries:
        - Focus: one-based line attribution of the identity field
        - Fixtures/params: none

    On failure, first check:
        - The ``offset + 2`` line computation in extract_frontmatter_field
    """
    reading = doc_ids.extract_frontmatter_field("---\ntitle: T\nid: gamma\n---\n", "id")
    assert reading.status == doc_ids._ID
    assert reading.line == 3


@pytest.mark.parametrize(
    "body",
    [
        "id:",
        "id:   ",
        "id: # only a comment",
        "title: only-title",
    ],
)
def test_reader_treats_blank_or_absent_field_as_absent(body: str):
    """
    [Unit] detectors document_ids: verifies a blank, null, or absent id reads as absent, not an id.

    Scenario:
        Given a well-formed frontmatter block whose id value is empty, whitespace-only, or a
            comment, or where the id field is simply not present
        When the reader parses it
        Then the result is the ABSENT status with no value, so the document is eligible for the
            document_id_required check but never a collision, and no empty identity is invented.

    Boundaries:
        - Focus: the blank/null/absent -> ABSENT boundary (required-eligible, never a collision)
        - Fixtures/params: parametrized over blank, whitespace, comment, and missing-field bodies

    On failure, first check:
        - The empty/comment branch of _interpret_value returning ABSENT rather than an empty id
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._ABSENT
    assert reading.value is None


@pytest.mark.parametrize(
    "body",
    [
        "id: [a, b]",
        "id: {a: b}",
        "id: &anchor value",
        "id: *alias",
        "id: !tag value",
        "id: |",
        "id: >",
        "id:\n  nested: value",
        'id: "unterminated',
        "id: 'unterminated",
    ],
)
def test_reader_flags_unsupported_value_shapes(body: str):
    """
    [Unit] detectors document_ids: verifies unsupported value shapes are flagged without inventing an id.

    Scenario:
        Given a frontmatter id whose value is a flow collection, an anchor/alias/tag, a block
            scalar, a nested mapping, or an unterminated quoted scalar in a well-formed block
        When the reader parses it
        Then the result is the UNSUPPORTED status with no value but a reported line, so DS114
            emits one explicit finding for the document (it never invents an id and never crashes
            on the unsupported shape) rather than silently dropping it.

    Boundaries:
        - Focus: unsupported-shape -> UNSUPPORTED with a line (never invent an id, never crash)
        - Fixtures/params: parametrized over every unsupported value shape

    On failure, first check:
        - The flow/anchor/tag/block/nested branches of _interpret_value and the quote parsers
        - The UNSUPPORTED line attribution in extract_frontmatter_field
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._UNSUPPORTED
    assert reading.value is None
    assert reading.line is not None


def test_reader_defers_unterminated_block():
    """
    [Unit] detectors document_ids: verifies an unterminated opening block defers to DS111.

    Scenario:
        Given a document that opens with --- and an id line but has no closing delimiter
        When the reader parses it
        Then the result is DEFERRED, so a malformed block is treated as DS111's territory and
            never mined for an identity.

    Boundaries:
        - Focus: the unterminated-block -> DEFERRED delegation
        - Fixtures/params: none

    On failure, first check:
        - The close_index is-None branch of extract_frontmatter_field
    """
    reading = doc_ids.extract_frontmatter_field("---\nid: alpha\nno closer here\n", "id")
    assert reading.status == doc_ids._DEFERRED


def test_reader_defers_duplicate_field_key_as_ambiguous():
    """
    [Unit] detectors document_ids: verifies a duplicated id key defers rather than picking one.

    Scenario:
        Given a single frontmatter block declaring the id key twice with different values
        When the reader parses it
        Then the result is DEFERRED (ambiguous), so DS114 contributes no identity and no
            missing-identity finding for that document, avoiding a dual diagnostic with DS111,
            and it does not silently pick the first or last occurrence.

    Boundaries:
        - Focus: duplicate-key -> DEFERRED (ambiguity, not first/last selection)
        - Fixtures/params: none

    On failure, first check:
        - The ``len(matches) > 1`` branch of extract_frontmatter_field
    """
    reading = doc_ids.extract_frontmatter_field("---\nid: first\nid: second\n---\n", "id")
    assert reading.status == doc_ids._DEFERRED
    assert reading.value is None


@pytest.mark.parametrize(
    "text",
    [
        "# Heading\n\nid: same\n",
        "Some prose mentioning id: same in a sentence.\n",
        "```yaml\nid: same\n```\n",
        "----\nid: same\n----\n",
    ],
)
def test_reader_ignores_ids_outside_opening_frontmatter(text: str):
    """
    [Unit] detectors document_ids: verifies ids in prose, headings, or code fences are not metadata.

    Scenario:
        Given an id-looking line in body prose, a heading, a fenced code example, or under a
            four-dash line that is not a frontmatter opener
        When the reader parses the document
        Then the result is ABSENT because only an opening --- block at byte 0 is frontmatter, so
            none of these are mistaken for a declared identity.

    Boundaries:
        - Focus: the byte-0 opening-fence requirement (exclusion: prose/heading/code-fence ids)
        - Fixtures/params: parametrized over prose, heading, code-fence, and non-opener forms

    On failure, first check:
        - The startswith("---") opener guard and the exact ``---`` opener-line check
    """
    reading = doc_ids.extract_frontmatter_field(text, "id")
    assert reading.status == doc_ids._ABSENT


def test_reader_handles_bom_and_crlf():
    """
    [Unit] detectors document_ids: verifies a UTF-8 BOM and CRLF terminators are handled.

    Scenario:
        Given a document prefixed with a UTF-8 BOM and using CRLF line terminators
        When the reader parses it
        Then the BOM is stripped, the CR is trimmed from each line, and the id is extracted at
            its correct one-based line.

    Boundaries:
        - Focus: BOM stripping and CRLF line handling in _split_lines
        - Fixtures/params: none

    On failure, first check:
        - The BOM strip and the per-line rstrip("\\r") in _split_lines
    """
    reading = doc_ids.extract_frontmatter_field("﻿---\r\nid: alpha\r\n---\r\n", "id")
    assert reading.status == doc_ids._ID
    assert reading.value == "alpha"
    assert reading.line == 2


def test_reader_handles_tab_indented_nested_value():
    """
    [Unit] detectors document_ids: verifies a tab-indented child turns an empty id into unsupported.

    Scenario:
        Given an id field with an empty inline value followed by a tab-indented child line
        When the reader parses it
        Then the result is UNSUPPORTED, because a tab (like a space) marks a nested structure the
            minimal reader does not interpret, which DS114 flags explicitly.

    Boundaries:
        - Focus: tab counts as indentation for nested-structure detection
        - Fixtures/params: none

    On failure, first check:
        - The ``block[offset + 1][0] in " \\t"`` nested check in extract_frontmatter_field
    """
    reading = doc_ids.extract_frontmatter_field("---\nid:\n\tnested: value\n---\n", "id")
    assert reading.status == doc_ids._UNSUPPORTED


def test_reader_accepts_nul_byte_as_literal_scalar_text():
    """
    [Unit] detectors document_ids: verifies an embedded NUL byte is kept as literal scalar text.

    Scenario:
        Given an id whose plain scalar value contains a NUL byte
        When the reader parses it
        Then the NUL is preserved in the raw value (it is treated as ordinary text, not a
            terminator), so downstream normalization and the bounded escaped echo handle it.

    Boundaries:
        - Focus: a control byte in content is data, never a crash or a truncation
        - Fixtures/params: none

    On failure, first check:
        - Whether any reader branch special-cased or choked on \\x00
    """
    reading = doc_ids.extract_frontmatter_field("---\nid: a\x00b\n---\n", "id")
    assert reading.status == doc_ids._ID
    assert reading.value == "a\x00b"


def test_configured_field_name_is_honored():
    """
    [Unit] detectors document_ids: verifies a non-default document_id_field is read.

    Scenario:
        Given two documents keyed by a custom frontmatter field (slug) with the same value and a
            config naming that field
        When the corpus core runs
        Then the later document is reported as a duplicate, proving the configured field name is
            the key the reader looks up rather than a hard-coded ``id``.

    Boundaries:
        - Focus: document_id_field selects the frontmatter key
        - Fixtures/params: none

    On failure, first check:
        - Whether the field name flows from Config into extract_frontmatter_field
    """
    entries = (
        ("a.md", "---\nslug: shared\n---\n"),
        ("b.md", "---\nslug: shared\n---\n"),
    )
    findings = doc_ids.check_documents(entries, Config(document_id_field="slug"))
    assert _paths(findings) == ["b.md"]


def test_distinct_ids_do_not_collide():
    """
    [Unit] detectors document_ids: verifies distinct identities yield no findings.

    Scenario:
        Given two documents declaring different ids
        When the corpus core runs with the default config
        Then no findings are produced.

    Boundaries:
        - Focus: the no-false-positive baseline for distinct ids
        - Fixtures/params: none

    On failure, first check:
        - The bucket key construction in check_documents
    """
    entries = (("a.md", _doc("id: alpha")), ("b.md", _doc("id: beta")))
    assert doc_ids.check_documents(entries) == ()


def test_identical_ids_report_later_sorted_document():
    """
    [Unit] detectors document_ids: verifies a collision is attributed to the later sorted document.

    Scenario:
        Given two documents (supplied out of path order) declaring the same id
        When the corpus core runs
        Then exactly one finding is produced at error severity, attributed to the later sorted
            path, carrying the id line of that later document and naming the original (earlier)
            document in the message.

    Boundaries:
        - Focus: later-document attribution, original reference, severity, and line
        - Fixtures/params: none

    On failure, first check:
        - The sorted() ordering and the originals bookkeeping in check_documents
    """
    entries = (("b.md", "---\nid: alpha\n---\n"), ("a.md", "---\nid: alpha\n---\n"))
    findings = doc_ids.check_documents(entries)
    assert len(findings) == 1
    assert findings[0].path == "b.md"
    assert findings[0].severity == "error"
    assert findings[0].line == 2
    assert findings[0].message == 'duplicate document id "alpha" (already declared in a.md)'


def test_three_duplicates_produce_two_findings_naming_the_original():
    """
    [Unit] detectors document_ids: verifies three identical ids produce exactly two findings.

    Scenario:
        Given three documents a.md, b.md, c.md all declaring the same id
        When the corpus core runs
        Then exactly two findings are produced, one each for b.md and c.md, both naming a.md as
            the original, in sorted-path order (the n-1 contract).

    Boundaries:
        - Focus: the n-1 finding count and that every later duplicate names the first occurrence
        - Fixtures/params: none

    On failure, first check:
        - Whether originals stores the first path and is never overwritten
    """
    entries = (
        ("a.md", "---\nid: x\n---\n"),
        ("b.md", "---\nid: x\n---\n"),
        ("c.md", "---\nid: x\n---\n"),
    )
    findings = doc_ids.check_documents(entries)
    assert _paths(findings) == ["b.md", "c.md"]
    assert all("already declared in a.md" in message for message in _messages(findings))


def test_whitespace_normalized_ids_collide():
    """
    [Unit] detectors document_ids: verifies ids differing only by whitespace collide.

    Scenario:
        Given two documents whose quoted id values differ only in surrounding and internal
            whitespace
        When the corpus core runs
        Then the later document is reported, because whitespace is stripped and collapsed before
            comparison.

    Boundaries:
        - Focus: whitespace normalization (strip + collapse) in the comparison key
        - Fixtures/params: none

    On failure, first check:
        - The ``" ".join(...split())`` collapse in normalize_identity/_display_identity
    """
    entries = (("a.md", '---\nid: "alpha"\n---\n'), ("b.md", '---\nid: "  alpha  "\n---\n'))
    assert _paths(doc_ids.check_documents(entries)) == ["b.md"]


def test_nfc_equivalent_ids_collide():
    """
    [Unit] detectors document_ids: verifies NFC-equivalent Unicode ids collide.

    Scenario:
        Given one document with a precomposed accented id and another with the canonically
            equivalent decomposed form
        When the corpus core runs
        Then the later document is reported, because both normalize to the same NFC string.

    Boundaries:
        - Focus: Unicode NFC normalization of the comparison key
        - Fixtures/params: none

    On failure, first check:
        - The unicodedata.normalize("NFC", ...) call in normalize_identity/_display_identity
    """
    entries = (
        ("a.md", "---\nid: café\n---\n"),
        ("b.md", "---\nid: café\n---\n"),
    )
    assert _paths(doc_ids.check_documents(entries)) == ["b.md"]


def test_unicode_confusables_stay_distinct():
    """
    [Unit] detectors document_ids: verifies Unicode confusables are not conflated.

    Scenario:
        Given one document with a Latin "a" id and another with a Cyrillic "а" id (distinct code
            points that look alike)
        When the corpus core runs
        Then no finding is produced, because NFC does not merge confusables and DS114 adds no
            confusable folding.

    Boundaries:
        - Focus: confusables remain distinct (no homoglyph folding)
        - Fixtures/params: none

    On failure, first check:
        - Whether any normalization step mapped distinct code points together
    """
    entries = (("a.md", "---\nid: a\n---\n"), ("b.md", "---\nid: а\n---\n"))
    assert doc_ids.check_documents(entries) == ()


def test_case_sensitive_default_keeps_case_variants_distinct():
    """
    [Unit] detectors document_ids: verifies the default case-sensitive policy keeps Alpha and alpha distinct.

    Scenario:
        Given two documents declaring ids Alpha and alpha
        When the corpus core runs with the default (case-sensitive) config
        Then no finding is produced.

    Boundaries:
        - Focus: default case sensitivity
        - Fixtures/params: none

    On failure, first check:
        - The case_sensitive branch selecting the comparison key in check_documents
    """
    entries = (("a.md", "---\nid: Alpha\n---\n"), ("b.md", "---\nid: alpha\n---\n"))
    assert doc_ids.check_documents(entries) == ()


def test_case_insensitive_policy_collides_case_variants():
    """
    [Unit] detectors document_ids: verifies case-insensitive policy collides Alpha and alpha.

    Scenario:
        Given two documents declaring ids Alpha and alpha
        When the corpus core runs with document_id_case_sensitive=false
        Then the later document is reported as a duplicate, with the original's displayed id
            preserving its case in the message.

    Boundaries:
        - Focus: case-folded comparison under the opt-in policy
        - Fixtures/params: none

    On failure, first check:
        - The casefold() application to the bucket key when not case_sensitive
    """
    entries = (("a.md", "---\nid: Alpha\n---\n"), ("b.md", "---\nid: alpha\n---\n"))
    findings = doc_ids.check_documents(entries, Config(document_id_case_sensitive=False))
    assert _paths(findings) == ["b.md"]
    assert findings[0].message == 'duplicate document id "alpha" (already declared in a.md)'


def test_directory_scope_isolates_namespaces():
    """
    [Unit] detectors document_ids: verifies directory scope isolates identity namespaces per directory.

    Scenario:
        Given the same id declared once in x/a.md and once in y/b.md, and again twice within x/
        When the corpus core runs with document_id_scope="directory"
        Then the cross-directory pair does not collide while the same-directory pair does, proving
            the namespace is the parent directory.

    Boundaries:
        - Focus: document_id_scope="directory" namespace keying
        - Fixtures/params: none

    On failure, first check:
        - The _scope_key dirname computation and the bucket key
    """
    cross = (("x/a.md", "---\nid: z\n---\n"), ("y/b.md", "---\nid: z\n---\n"))
    assert doc_ids.check_documents(cross, Config(document_id_scope="directory")) == ()
    same = (("x/a.md", "---\nid: z\n---\n"), ("x/b.md", "---\nid: z\n---\n"))
    assert _paths(doc_ids.check_documents(same, Config(document_id_scope="directory"))) == ["x/b.md"]


def test_missing_optional_ids_are_clean_by_default():
    """
    [Unit] detectors document_ids: verifies missing ids are clean when not required.

    Scenario:
        Given two documents that declare no id
        When the corpus core runs with the default config (document_id_required=false)
        Then no findings are produced.

    Boundaries:
        - Focus: optional-id default (missing id is not a finding)
        - Fixtures/params: none

    On failure, first check:
        - The required gate in check_documents
    """
    entries = (("a.md", "# just prose\n"), ("b.md", "# more prose\n"))
    assert doc_ids.check_documents(entries) == ()


def test_required_policy_flags_documents_without_identity():
    """
    [Unit] detectors document_ids: verifies the required policy flags each document lacking an id.

    Scenario:
        Given a document with no id and a document with an id, under document_id_required=true
        When the corpus core runs
        Then exactly one finding is produced for the id-less document (no representable line) and
            none for the document that declares an identity.

    Boundaries:
        - Focus: document_id_required semantics (ABSENT documents only; line is None)
        - Fixtures/params: none

    On failure, first check:
        - The ABSENT + required branch emitting a missing-identity finding
    """
    entries = (("a.md", "# no identity\n"), ("b.md", "---\nid: present\n---\n"))
    findings = doc_ids.check_documents(entries, Config(document_id_required=True))
    assert _paths(findings) == ["a.md"]
    assert findings[0].line is None
    assert findings[0].severity == "error"
    assert findings[0].message == 'document declares no "id" identity'


def test_required_policy_stays_silent_for_deferred_metadata():
    """
    [Unit] detectors document_ids: verifies required mode does not flag malformed metadata.

    Scenario:
        Given document_id_required=true and a document whose only id declaration is a duplicate
            key (DS111 territory)
        When the corpus core runs
        Then no DS114 finding is produced for it, avoiding a contradictory dual diagnostic with
            DS111 even under the required policy.

    Boundaries:
        - Focus: DEFERRED documents never trigger the required finding
        - Fixtures/params: none

    On failure, first check:
        - That the DEFERRED continue precedes the ABSENT+required branch
    """
    entries = (("a.md", "---\nid: one\nid: two\n---\n"),)
    assert doc_ids.check_documents(entries, Config(document_id_required=True)) == ()


def test_unsupported_value_shape_flags_once_and_is_excluded_from_collision():
    """
    [Unit] detectors document_ids: verifies an unsupported id shape yields one finding and no collision.

    Scenario:
        Given one document whose configured id field is a nested mapping (an unsupported value
            shape) and a second document declaring that same value shape, plus a third document
            whose id happens to be the literal text of the first's child line
        When the corpus core runs
        Then each unsupported-shape document produces exactly one finding at its id line naming the
            field but not the value, both are excluded from collision bookkeeping (so they never
            collide with each other or invent an identity), and the plain-scalar third document
            stands alone with no finding.

    Boundaries:
        - Focus: UNSUPPORTED -> one per-document finding, never a collision, never an invented id
        - Fixtures/params: none

    On failure, first check:
        - The UNSUPPORTED branch of check_documents emitting the finding and then continuing
        - That the unsupported document is never added to the originals bucket
    """
    entries = (
        ("a.md", "---\nid:\n  nested: value\n---\n"),
        ("b.md", "---\nid:\n  nested: value\n---\n"),
        ("c.md", "---\nid: nested\n---\n"),
    )
    findings = doc_ids.check_documents(entries)
    assert _paths(findings) == ["a.md", "b.md"]
    for finding in findings:
        assert finding.severity == "error"
        assert finding.line == 2
        assert finding.message == 'document id field "id" has an unsupported value shape (not evaluated for uniqueness)'


def test_unsupported_value_shape_echoes_bounded_escaped_field_name_only():
    """
    [Unit] detectors document_ids: verifies the unsupported-shape message echoes only the field name.

    Scenario:
        Given a document whose configured field has a very long, control-and-non-ASCII name and an
            unsupported flow-collection value
        When the corpus core runs with that field configured
        Then the single finding echoes a bounded, repr-escaped form of the field name (no raw
            control or non-ASCII byte) and never the raw value, mirroring the collision echo.

    Boundaries:
        - Focus: the unsupported-shape message echoes only the bounded, escaped field name
        - Fixtures/params: none

    On failure, first check:
        - The _echo call on the field name in the UNSUPPORTED branch of check_documents
    """
    field = "f" * 200
    entries = (("a.md", f"---\n{field}: [x, y]\n---\n"),)
    findings = doc_ids.check_documents(entries, Config(document_id_field=field))
    assert len(findings) == 1
    message = findings[0].message
    assert message.isascii()
    assert "..." in message
    assert "[x, y]" not in message


def test_echo_is_bounded_and_escaped():
    """
    [Unit] detectors document_ids: verifies the finding message echo is bounded and repr-escaped.

    Scenario:
        Given two documents whose shared id is very long and contains a control byte and a
            non-ASCII character
        When the corpus core runs
        Then the collision message echoes a bounded, unicode_escape-escaped form of the id (no raw
            control byte or non-ASCII byte reaches the message) with a truncation marker.

    Boundaries:
        - Focus: the bounded, repr-escaped echo (no control/non-ASCII leakage, truncation marker)
        - Fixtures/params: none

    On failure, first check:
        - The _MAX_ECHO bound and the unicode_escape encoding in _echo
    """
    identity = "A" * 200 + "\x07é"
    entries = (
        ("a.md", f"---\nid: {identity}\n---\n"),
        ("b.md", f"---\nid: {identity}\n---\n"),
    )
    message = doc_ids.check_documents(entries)[0].message
    assert "\x07" not in message
    assert "é" not in message
    assert "..." in message
    assert message.isascii()


@pytest.mark.parametrize(
    "body",
    [
        "id: alpha\n  continued",
        "id: alpha\n  continued\n  more",
        "id: alpha\n    deeply-indented",
        "id: alpha\n\n  continued-after-blank",
        "id: alpha\n  # indented comment then\n  real-continuation",
        'id: "alpha"\n  continued',
        "id: 'alpha'\n  continued",
    ],
)
def test_multi_line_scalar_continuation_is_unsupported(body: str):
    """
    [Unit] detectors document_ids: verifies a multi-line scalar continuation defers to unsupported.

    Scenario:
        Given a configured field whose non-empty inline plain or quoted scalar is immediately
            followed (blank and comment lines skipped) by a more-indented continuation line
        When the reader parses it
        Then the result is UNSUPPORTED with a reported line and no value, because a real YAML parser
            folds the continuation into the value so the first physical line alone is the wrong
            identity - the reader refuses to read the truncated line (closing the MEDIUM false/hidden
            collision from the security review).

    Boundaries:
        - Focus: plain/quoted multi-line continuation -> UNSUPPORTED (never the truncated first line)
        - Fixtures/params: parametrized over plain, quoted, multi-line, blank- and comment-separated

    On failure, first check:
        - The next_is_indented branch of _interpret_value
        - _next_block_line_is_indented skipping blank/comment lines before the indentation test
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._UNSUPPORTED
    assert reading.value is None
    assert reading.line == 2


@pytest.mark.parametrize(
    "body",
    [
        "id: alpha\nnext: beta",
        "id: alpha\n\nnext: beta",
        "id: shared extra",
    ],
)
def test_scalar_followed_by_sibling_key_is_not_a_continuation(body: str):
    """
    [Unit] detectors document_ids: verifies a sibling top-level key is not a continuation.

    Scenario:
        Given a plain id scalar followed by a top-level sibling key (not indented), with or without a
            blank line between, or a single-line multi-word scalar
        When the reader parses it
        Then the id is read as the ordinary scalar and no continuation is inferred, proving only a
            more-indented following line triggers the unsupported-continuation path.

    Boundaries:
        - Focus: the no-false-positive boundary of the continuation rule (zero-indent sibling is fine)
        - Fixtures/params: parametrized over sibling-key and blank-separated-sibling shapes

    On failure, first check:
        - _next_block_line_is_indented returning False for a zero-indent next real line
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._ID


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('id: "a\\/b"', "a/b"),
        ('id: "a\\0b"', "a\x00b"),
        ('id: "a\\\\b"', "a\\b"),
        ('id: "a\\"b"', 'a"b'),
    ],
)
def test_double_quoted_supported_escapes_decode_as_yaml(body: str, expected: str):
    """
    [Unit] detectors document_ids: verifies the supported double-quote escapes decode exactly as YAML.

    Scenario:
        Given a double-quoted id using one of the exactly-YAML escapes the reader decodes (\\/, \\0,
            \\\\, \\")
        When the reader parses it
        Then the decoded raw value matches PyYAML byte-for-byte, so the reader never invents a value
            that disagrees with a real parser for its supported subset.

    Boundaries:
        - Focus: the supported double-quote escape subset decodes identically to YAML/PyYAML
        - Fixtures/params: parametrized over \\/, \\0, \\\\ and \\"

    On failure, first check:
        - The _DOUBLE_QUOTE_ESCAPES table and _parse_double_quoted decoding
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._ID
    assert reading.value == expected


@pytest.mark.parametrize(
    "body",
    [
        'id: "\\x41"',
        'id: "\\u0041"',
        'id: "\\U00000041"',
        'id: "\\N"',
        'id: "\\_"',
        'id: "\\L"',
        'id: "\\P"',
        'id: "a\\ b"',
    ],
)
def test_double_quoted_unsupported_escape_defers_instead_of_mis_decoding(body: str):
    """
    [Unit] detectors document_ids: verifies an unsupported double-quote escape defers, never mis-decodes.

    Scenario:
        Given a double-quoted id containing an escape outside the reader's exactly-YAML subset (a
            numeric \\x/\\u/\\U, \\N/\\_/\\L/\\P, or \\<space>)
        When the reader parses it
        Then the result is UNSUPPORTED with no value, because the reader refuses to guess at an escape
            it cannot decode exactly as YAML - closing the MEDIUM mis-decode (drop-the-backslash) class
            from the security review by deferring rather than inventing a wrong id.

    Boundaries:
        - Focus: unrecognised double-quote escapes -> UNSUPPORTED (never silently drop the backslash)
        - Fixtures/params: parametrized over \\x, \\u, \\U, \\N, \\_, \\L, \\P and \\<space>

    On failure, first check:
        - The None return for an unrecognised escape in _parse_double_quoted
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._UNSUPPORTED
    assert reading.value is None


@pytest.mark.parametrize(
    "body",
    [
        '"id": value',
        "'id': value",
        "? id\n: value",
        "? id",
        "<<: {other: v}\nname: x",
        "id: plain\n<<: {b: c}",
    ],
)
def test_alternative_key_spellings_defer_rather_than_read_absent(body: str):
    """
    [Unit] detectors document_ids: verifies quoted/explicit/merge key spellings defer, not read absent.

    Scenario:
        Given the configured field present only under a quoted key ("id":), an explicit key (? id), or
            reachable through a << merge key (alone, or alongside a plain id that a merge alias could
            override)
        When the reader parses it
        Then the result is DEFERRED (silent, DS111 territory) rather than ABSENT or a guessed id,
            because a real parser would honour the identity - so DS114 neither invents it, nor (under
            document_id_required) falsely reports "declares no id", closing the MEDIUM hidden-collision
            evasion for these spellings.

    Boundaries:
        - Focus: quoted/explicit/merge-key spellings -> DEFERRED (never ABSENT, never a mined identity)
        - Fixtures/params: parametrized over quoted, single-quoted, explicit, bare-explicit and merge keys

    On failure, first check:
        - The has_shadow_field / has_merge_key branches in extract_frontmatter_field
        - _unquote_key and _explicit_key_names_field recognition of the field spelling
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._DEFERRED
    assert reading.value is None


def test_plain_key_with_quoted_shadow_key_keeps_the_plain_value():
    """
    [Unit] detectors document_ids: verifies a plain id alongside a quoted-key spelling keeps the plain value.

    Scenario:
        Given a block with a plain id and a quoted "id" spelling that resolve to the same value
        When the reader parses it
        Then the plain value is used (the quoted shadow key does not force a defer), matching the
            documented "keep current behaviour when the field is also a plain key" ruling; only a merge
            key forces a defer.

    Boundaries:
        - Focus: a quoted shadow key plus a plain key -> use the plain value (merge key is the exception)
        - Fixtures/params: none

    On failure, first check:
        - That has_shadow_field does not defer when a plain match exists (only has_merge_key does)
    """
    reading = doc_ids.extract_frontmatter_field('---\nid: plain\n"id": plain\n---\n', "id")
    assert reading.status == doc_ids._ID
    assert reading.value == "plain"


@pytest.mark.parametrize("body", ["id: ~", "id: null", "id: Null", "id: NULL"])
def test_yaml_null_spellings_read_as_absent(body: str):
    """
    [Unit] detectors document_ids: verifies ~/null/Null/NULL read as absent (no identity).

    Scenario:
        Given a configured field whose value is a YAML null spelling (~, null, Null, or NULL)
        When the reader parses it
        Then the result is ABSENT with no value - the same outcome as a blank value and matching YAML's
            core-schema null - so two such documents never collide on the literal text and the value is
            eligible for the document_id_required check (ruling 4).

    Boundaries:
        - Focus: YAML null spellings -> ABSENT (never a literal-text identity)
        - Fixtures/params: parametrized over ~, null, Null and NULL

    On failure, first check:
        - The _YAML_NULL_SCALARS membership test in _interpret_value
    """
    reading = doc_ids.extract_frontmatter_field(_doc(body), "id")
    assert reading.status == doc_ids._ABSENT
    assert reading.value is None


def test_non_canonical_null_like_text_stays_a_literal_identity():
    """
    [Unit] detectors document_ids: verifies a non-canonical null-like token stays literal text.

    Scenario:
        Given an id whose value is nUll (not one of the canonical YAML null spellings)
        When the reader parses it
        Then it is read as the literal-text identity nUll, proving only the exact null tokens are
            treated as null and an arbitrary look-alike is an ordinary id (matching PyYAML).

    Boundaries:
        - Focus: only the exact null spellings are null; a look-alike is literal text
        - Fixtures/params: none

    On failure, first check:
        - Whether _YAML_NULL_SCALARS was broadened to case-insensitive matching
    """
    reading = doc_ids.extract_frontmatter_field(_doc("id: nUll"), "id")
    assert reading.status == doc_ids._ID
    assert reading.value == "nUll"


def test_required_policy_stays_silent_for_an_alternative_key_spelling():
    """
    [Unit] detectors document_ids: verifies required mode does not falsely flag a quoted-key id.

    Scenario:
        Given document_id_required=true and a document whose id is declared only under a quoted key
            ("id": present) - a valid identity a real parser honours
        When the corpus core runs
        Then no DS114 "declares no id" finding is produced for it, because the quoted spelling is
            DEFERRED rather than ABSENT, closing the MEDIUM false-block the review raised for the
            required policy.

    Boundaries:
        - Focus: DEFERRED (alt spelling) documents never trigger the required finding
        - Fixtures/params: none

    On failure, first check:
        - That the DEFERRED continue precedes the ABSENT+required branch in check_documents
        - The has_shadow_field defer for a quoted key with no plain key
    """
    entries = (("a.md", '---\n"id": present\n---\n'),)
    assert doc_ids.check_documents(entries, Config(document_id_required=True)) == ()


def test_continuation_document_yields_one_finding_and_never_a_collision():
    """
    [Unit] detectors document_ids: verifies a continuation id flags once and cannot collide.

    Scenario:
        Given two documents whose id uses a multi-line plain continuation, plus a third document whose
            single-line id is the literal text of the first continuation's folded first word
        When the corpus core runs
        Then each continuation document produces exactly one UNSUPPORTED error finding at its id line
            and is excluded from collision bookkeeping, so the two never collide with each other and
            the plain-scalar third document stands alone - turning both a false and a hidden collision
            into an honest unsupported diagnostic.

    Boundaries:
        - Focus: continuation -> one own finding, never a collision, never a truncated-first-line id
        - Fixtures/params: none

    On failure, first check:
        - The UNSUPPORTED branch of check_documents emitting the finding then continuing
        - That the continuation document is never added to the originals bucket
    """
    entries = (
        ("a.md", "---\nid: alpha\n  continued\n---\n"),
        ("b.md", "---\nid: alpha\n  continued\n---\n"),
        ("c.md", "---\nid: alpha\n---\n"),
    )
    findings = doc_ids.check_documents(entries)
    assert _paths(findings) == ["a.md", "b.md"]
    for finding in findings:
        assert finding.severity == "error"
        assert finding.line == 2
        assert "unsupported value shape" in finding.message


#: The YAML differential corpus: ``(frontmatter_body, expected_status, expected_value)`` rows
#: transcribed from a scratch ``uv run --with pyyaml`` differential over PyYAML 6.x. Every row was
#: verified to produce NO case where the reader returns a concrete id different from PyYAML's string
#: value; deferral/unsupported (where the reader is uncertain) and the ruling's literal-text handling
#: of numbers/booleans (which PyYAML parses to non-strings) are the documented, accepted outcomes.
#: No YAML library is imported here or in product code - the verified results are frozen in-table.
_YAML_DIFFERENTIAL_CORPUS: tuple[tuple[str, str, object], ...] = (
    # Plain / quoted / single scalars and inline comments (supported literal text).
    ("id: alpha", doc_ids._ID, "alpha"),
    ('id: "alpha"', doc_ids._ID, "alpha"),
    ("id: 'alpha'", doc_ids._ID, "alpha"),
    ("id: alpha # trailing comment", doc_ids._ID, "alpha"),
    ("id: a#b", doc_ids._ID, "a#b"),
    ('id: "  spaced  "', doc_ids._ID, "  spaced  "),
    ("id: 'it''s'", doc_ids._ID, "it's"),
    ("id: spaced-colon", doc_ids._ID, "spaced-colon"),
    ("title: T\nid: beta", doc_ids._ID, "beta"),
    ("id: shared extra", doc_ids._ID, "shared extra"),
    ("id: alpha\nnext: beta", doc_ids._ID, "alpha"),
    ("id: alpha\n\nnext: beta", doc_ids._ID, "alpha"),
    ('id: plain\n"id": plain', doc_ids._ID, "plain"),
    ("id: alpha\\", doc_ids._ID, "alpha\\"),
    # Numbers / booleans: literal text in the reader (PyYAML parses to non-strings; accepted ruling).
    ("id: 123", doc_ids._ID, "123"),
    ("id: true", doc_ids._ID, "true"),
    ("id: 3.14", doc_ids._ID, "3.14"),
    ("id: yes", doc_ids._ID, "yes"),
    ("id: on", doc_ids._ID, "on"),
    ("id: off", doc_ids._ID, "off"),
    ("id: nUll", doc_ids._ID, "nUll"),
    # Supported double-quote escapes (decoded byte-for-byte as YAML).
    ('id: "a\\tb"', doc_ids._ID, "a\tb"),
    ('id: "a\\nb"', doc_ids._ID, "a\nb"),
    ('id: "a\\rb"', doc_ids._ID, "a\rb"),
    ('id: "a\\\\b"', doc_ids._ID, "a\\b"),
    ('id: "a\\"b"', doc_ids._ID, 'a"b'),
    ('id: "a\\/b"', doc_ids._ID, "a/b"),
    ('id: "a\\0b"', doc_ids._ID, "a\x00b"),
    ('id: "x41"', doc_ids._ID, "x41"),
    ('id: "A"', doc_ids._ID, "A"),
    # Null spellings and absent field -> ABSENT (no identity).
    ("id:", doc_ids._ABSENT, None),
    ("id:   ", doc_ids._ABSENT, None),
    ("id: ~", doc_ids._ABSENT, None),
    ("id: null", doc_ids._ABSENT, None),
    ("id: Null", doc_ids._ABSENT, None),
    ("id: NULL", doc_ids._ABSENT, None),
    ("id: # only a comment", doc_ids._ABSENT, None),
    ("title: only-title", doc_ids._ABSENT, None),
    # Alternative key spellings and duplicate key -> DEFERRED (silent, DS111 territory).
    ('"id": value', doc_ids._DEFERRED, None),
    ("'id': value", doc_ids._DEFERRED, None),
    ("? id\n: value", doc_ids._DEFERRED, None),
    ("? id", doc_ids._DEFERRED, None),
    ("<<: {other: v}\nname: x", doc_ids._DEFERRED, None),
    ("id: plain\n<<: {b: c}", doc_ids._DEFERRED, None),
    ("id: one\nid: two", doc_ids._DEFERRED, None),
    # Unsupported value shapes (continuation, unsupported escapes, flow/anchor/tag/block/nested,
    # unterminated quoted) -> UNSUPPORTED (never a guessed identity).
    ("id: alpha\n  continued", doc_ids._UNSUPPORTED, None),
    ("id: alpha\n  continued\n  more", doc_ids._UNSUPPORTED, None),
    ("id: alpha\n    deeply-indented", doc_ids._UNSUPPORTED, None),
    ("id: alpha\n\n  continued-after-blank", doc_ids._UNSUPPORTED, None),
    ("id: alpha\n  # indented comment then\n  real-continuation", doc_ids._UNSUPPORTED, None),
    ('id: "alpha"\n  continued', doc_ids._UNSUPPORTED, None),
    ("id: 'alpha'\n  continued", doc_ids._UNSUPPORTED, None),
    ('id: "\\x41"', doc_ids._UNSUPPORTED, None),
    ('id: "\\u0041"', doc_ids._UNSUPPORTED, None),
    ('id: "\\U00000041"', doc_ids._UNSUPPORTED, None),
    ('id: "\\N"', doc_ids._UNSUPPORTED, None),
    ('id: "\\_"', doc_ids._UNSUPPORTED, None),
    ('id: "\\L"', doc_ids._UNSUPPORTED, None),
    ('id: "\\P"', doc_ids._UNSUPPORTED, None),
    ('id: "a\\ b"', doc_ids._UNSUPPORTED, None),
    ("id: [a, b]", doc_ids._UNSUPPORTED, None),
    ("id: {a: b}", doc_ids._UNSUPPORTED, None),
    ("id: &anchor value", doc_ids._UNSUPPORTED, None),
    ("id: *alias", doc_ids._UNSUPPORTED, None),
    ("id: !tag value", doc_ids._UNSUPPORTED, None),
    ("id: |\n  block", doc_ids._UNSUPPORTED, None),
    ("id: >\n  folded", doc_ids._UNSUPPORTED, None),
    ("id:\n  nested: value", doc_ids._UNSUPPORTED, None),
    ('id: "unterminated', doc_ids._UNSUPPORTED, None),
    ("id: 'unterminated", doc_ids._UNSUPPORTED, None),
)


@pytest.mark.parametrize(("body", "expected_status", "expected_value"), _YAML_DIFFERENTIAL_CORPUS)
def test_reader_matches_pyyaml_over_the_differential_corpus(body: str, expected_status: str, expected_value: object):
    """
    [Unit] detectors document_ids: verifies the reader matches the PyYAML-verified differential corpus.

    Scenario:
        Given a corpus of 70 crafted frontmatter heads whose expected reader result was transcribed
            from a scratch PyYAML differential (asserted to have ZERO cases where the reader returns a
            concrete id different from PyYAML's string value)
        When the reader parses each head
        Then its status and raw value match the frozen expectation, pinning the reader as a
            narrow-but-faithful YAML subset: it decodes its supported escapes exactly, keeps
            numbers/booleans as literal text, reads null spellings as absent, and defers or marks
            unsupported every shape it cannot be sure of - never inventing a divergent id.

    Boundaries:
        - Focus: parser-parity regression over the full differential corpus (no yaml import in the test)
        - Fixtures/params: parametrized over the 70 transcribed (body, status, value) rows

    On failure, first check:
        - Which category (continuation, escape, null, alt-spelling, unsupported) the failing body is in
        - Whether the product reader drifted from the scratch differential (re-run it to re-verify)
    """
    reading = doc_ids.extract_frontmatter_field("---\n" + body + "\n---\n", "id")
    assert reading.status == expected_status
    if expected_status == doc_ids._ID:
        assert reading.value == expected_value
    else:
        assert reading.value is None


def _run_check(entries: tuple[tuple[str, str], ...]) -> tuple[models.Finding, ...]:
    """Run the corpus core with default settings for the scaling floods.

    :param entries: The ``(path, text)`` document entries to check.
    :returns: The DS114 findings.
    """
    return doc_ids.check_documents(entries)


#: Multi-document floods: n independent documents mapped to the exact DS114 finding
#: count the shape must yield, so the scaling bound can never pass vacuously.
_MULTI_DOC: dict[str, tuple[Callable[[int], tuple[tuple[str, str], ...]], Callable[[int], int]]] = {
    # n documents with pairwise-distinct ids -> zero findings.
    "distinct_ids": (
        lambda n: tuple((f"doc{i:06d}.md", f"---\nid: unique{i}\n---\n") for i in range(n)),
        lambda _n: 0,
    ),
    # n documents sharing one id -> exactly n-1 duplicate findings.
    "identical_ids": (
        lambda n: tuple((f"doc{i:06d}.md", "---\nid: shared\n---\n") for i in range(n)),
        lambda n: n - 1,
    ),
}

#: Single-document floods: one document whose frontmatter grows along one dimension
#: (a giant single value line, or many keys, the latter kept under the reader's line
#: cap so key parsing is genuinely exercised), each yielding zero findings.
_SINGLE_DOC: dict[str, tuple[Callable[[int], tuple[tuple[str, str], ...]], tuple[int, ...]]] = {
    "giant_identity_line": (
        lambda n: (("only.md", "---\nid: " + "a" * n + "\n---\n"),),
        (8_000, 16_000, 32_000, 64_000),
    ),
    "many_frontmatter_keys": (
        lambda n: (("only.md", "---\n" + "".join(f"k{i}: v{i}\n" for i in range(n)) + "id: tail\n---\n"),),
        (200, 400, 800, 1_600),
    ),
}

_MULTI_DOC_SIZES = (500, 1_000, 2_000, 4_000)


@pytest.mark.parametrize("name", list(_MULTI_DOC))
def test_multi_document_floods_stay_linear(name: str):
    """
    [Unit] detectors document_ids: verifies many-document corpora scale near-linearly.

    Scenario:
        Given a doubling series of corpora with either pairwise-distinct ids or one shared id
        When the corpus core runs with no filesystem access
        Then the exact finding count holds at every size (0 for distinct, n-1 for shared) and the
            scaling stays under the linear bound, proving the collision check is one pass over set
            or dict membership rather than a pairwise comparison.

    Boundaries:
        - Focus: O(n) corpus collision detection, never O(n^2) pairwise
        - Fixtures/params: parametrized over the distinct and identical multi-document floods

    On failure, first check:
        - Whether the originals dict lookup degraded into a per-document scan
    """
    builder, expected = _MULTI_DOC[name]
    assert_scales_linearly(builder, _run_check, _MULTI_DOC_SIZES, expected_count=expected, label=name)


@pytest.mark.parametrize("name", list(_SINGLE_DOC))
def test_single_document_frontmatter_floods_stay_linear(name: str):
    """
    [Unit] detectors document_ids: verifies a giant frontmatter value or key count scales near-linearly.

    Scenario:
        Given a doubling series of single documents whose frontmatter has either one very long id
            value line or very many keys
        When the corpus core runs with no filesystem access
        Then zero findings are produced at every size and the scaling stays under the linear bound,
            proving the frontmatter reader makes one bounded pass with no quadratic value or line
            handling.

    Boundaries:
        - Focus: the reader's single linear pass over the head (no tail rescans, no quadratic)
        - Fixtures/params: parametrized over the giant-line and many-keys floods

    On failure, first check:
        - Whether _find_key_colon, the comment strip, or the quote parser rescanned the value
    """
    builder, sizes = _SINGLE_DOC[name]
    assert_scales_linearly(builder, _run_check, sizes, expected_count=lambda _n: 0, label=name)


#: Continuation floods: the continuation path grows along one dimension -- many documents each
#: carrying a short multi-line continuation (n UNSUPPORTED findings), one document whose single
#: continuation line is very long (one finding), or one document with many indented continuation
#: lines kept under the reader's line cap (one finding) -- so the continuation detection is proven to
#: stay linear and never rescans the growing tail.
_CONTINUATION_FLOODS: dict[
    str, tuple[Callable[[int], tuple[tuple[str, str], ...]], tuple[int, ...], Callable[[int], int]]
] = {
    "many_continuation_documents": (
        lambda n: tuple((f"doc{i:06d}.md", "---\nid: head\n  continued\n---\n") for i in range(n)),
        (500, 1_000, 2_000, 4_000),
        lambda n: n,
    ),
    "long_indented_run": (
        lambda n: (("only.md", "---\nid: head\n  " + "a " * n + "\n---\n"),),
        (8_000, 16_000, 32_000, 64_000),
        lambda _n: 1,
    ),
    "many_continuation_lines_under_cap": (
        lambda n: (("only.md", "---\nid: head\n" + "  cont\n" * n + "---\n"),),
        (200, 400, 800, 1_600),
        lambda _n: 1,
    ),
}


@pytest.mark.parametrize("name", sorted(_CONTINUATION_FLOODS))
def test_continuation_floods_stay_linear(name: str):
    """
    [Unit] detectors document_ids: verifies a growing multi-line continuation scales near-linearly.

    Scenario:
        Given a doubling series that grows either the number of continuation documents, the length of
            one indented continuation line, or the number of indented continuation lines (kept under the
            reader's line cap)
        When the corpus core runs with no filesystem access
        Then the exact UNSUPPORTED finding count holds at every size (n for the many-document flood, 1
            for each single-document flood) and the scaling stays under the linear bound, proving the
            continuation detection returns on the first following real line and the block scan makes one
            pass with no quadratic rescanning of the continuation tail.

    Boundaries:
        - Focus: the continuation path is one linear pass (no per-line tail rescans)
        - Fixtures/params: parametrized over the many-document, long-run and many-lines continuation floods

    On failure, first check:
        - Whether _next_block_line_is_indented or the block scan degraded into a quadratic rescan
        - That the exact finding count still holds at every size
    """
    builder, sizes, expected = _CONTINUATION_FLOODS[name]
    assert_scales_linearly(builder, _run_check, sizes, expected_count=expected, label=name)
