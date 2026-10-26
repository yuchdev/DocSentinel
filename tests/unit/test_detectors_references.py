"""Unit tests for DS108 reference-style link definition integrity recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition entry point :func:`docsentinel.detectors.references.check_text`
directly. Detection over committed Markdown assets is the job of the Story 05.0
Task 03 integration suite, which runs now that ``DS108`` is registered together
with its ``tests/assets/ds108/*`` fixtures (Task 02); this module also pins that
registration.

The config-validation tests cover the three DS108 options
(``unused_reference_definitions``, ``duplicate_reference_definitions``,
``reference_label_normalization``) through the real loader and the injected
``Config`` so the typed defaults, standalone TOML, ``[tool.doc_sentinel]`` and
invalid-value paths are all exercised.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config, models, rules
from docsentinel.detectors import references
from tests.timing_helpers import assert_scales_linearly


def _codes(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the rule codes of findings, for terse assertions.

    :param findings: The findings to inspect.
    :returns: The ``rule`` field of each finding in order.
    """
    return [finding.rule for finding in findings]


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors references: verifies DS108 metadata and its registration.

    Scenario:
        Given the DS108 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered in both RULES and ANALYZERS.

    Boundaries:
        - Focus: rule metadata and the Story 05.0 Task 02 registration state
        - Fixtures/params: none

    On failure, first check:
        - Whether DS108 was registered and wired into ANALYZERS with its Task 02 fixtures
        - Whether a metadata field (profile, severity, title) drifted
    """
    assert references.DS108.code == "DS108"
    assert references.DS108.profile == "fast"
    assert references.DS108.severity == "warning"
    assert references.DS108.title == "Reference-style link definition integrity"
    assert references.DS108.opt_in_option == ""
    # Registration (and the ANALYZERS wiring) lands with the committed Task 02 fixtures.
    assert rules.RULES["DS108"] is references.DS108
    assert rules.ANALYZERS["DS108"] is references.detect


def test_full_reference_matching_definition_is_clean():
    """
    [Unit] detectors references: verifies a full reference with a matching definition is clean.

    Scenario:
        Given a full reference [text][label] and its [label]: target definition
        When DS108 recognition runs over the text
        Then no finding is produced.

    Boundaries:
        - Focus: the resolved full-reference happy path (algorithm bullet 1)
        - Fixtures/params: none

    On failure, first check:
        - Whether the definition line was recognized by the reference-definition regex
        - Whether normalization altered the label unexpectedly
    """
    text = "See [the docs][guide].\n\n[guide]: guide.md\n"
    assert references.check_text(text, "README.md") == ()


def test_collapsed_reference_matching_definition_is_clean():
    """
    [Unit] detectors references: verifies a collapsed reference resolves after normalization.

    Scenario:
        Given a collapsed reference [Guide][] and a [guide]: target definition
        When DS108 recognition runs over the text
        Then no finding is produced because the labels normalize to the same value.

    Boundaries:
        - Focus: collapsed form plus case-folded normalization (algorithm bullets 1-2)
        - Fixtures/params: none

    On failure, first check:
        - Whether the collapsed form took its label from the first bracket
        - Whether case folding matched 'Guide' to 'guide'
    """
    text = "Read [Guide][] now.\n\n[guide]: guide.md\n"
    assert references.check_text(text, "README.md") == ()


def test_case_and_whitespace_folded_labels_match():
    """
    [Unit] detectors references: verifies multiword mixed-case labels resolve after folding.

    Scenario:
        Given a full reference whose label differs from its definition only by case and whitespace
        When DS108 recognition runs over the text
        Then no finding is produced.

    Boundaries:
        - Focus: CommonMark normalization (NFC, whitespace collapse, case fold)
        - Fixtures/params: none

    On failure, first check:
        - Whether normalize_label collapsed the internal whitespace run
        - Whether the comparison was case-insensitive
    """
    text = "See [here][Getting   Started].\n\n[getting started]: start.md\n"
    assert references.check_text(text, "README.md") == ()


def test_undefined_full_reference_is_flagged_once():
    """
    [Unit] detectors references: verifies an undefined full reference yields one warning.

    Scenario:
        Given a full reference [text][missing] with no definition
        When DS108 recognition runs over the text
        Then exactly one DS108 warning is reported at the use's one-based line.

    Boundaries:
        - Focus: undefined-use detection (algorithm bullet 3)
        - Fixtures/params: none

    On failure, first check:
        - Whether the full form read the label from the second bracket
        - Whether the finding line matches the use line
    """
    findings = references.check_text("Intro.\n\nSee [text][missing] here.\n", "README.md")
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS108"
    assert finding.severity == "warning"
    assert finding.path == "README.md"
    assert finding.line == 3
    assert "missing" in finding.message


def test_undefined_collapsed_reference_is_flagged():
    """
    [Unit] detectors references: verifies an undefined collapsed reference is flagged.

    Scenario:
        Given a collapsed reference [missing][] with no definition
        When DS108 recognition runs over the text
        Then one DS108 finding names the undefined label.

    Boundaries:
        - Focus: collapsed-form undefined detection
        - Fixtures/params: none

    On failure, first check:
        - Whether the collapsed label was taken from the first bracket
        - Whether the undefined check ran for collapsed forms
    """
    findings = references.check_text("Text [missing][] text.\n", "README.md")
    assert len(findings) == 1
    assert "missing" in findings[0].message


def test_undefined_image_reference_is_flagged():
    """
    [Unit] detectors references: verifies an image reference with no definition is flagged.

    Scenario:
        Given an image reference ![alt][diagram] with no definition
        When DS108 recognition runs over the text
        Then one DS108 finding names the undefined label.

    Boundaries:
        - Focus: image references are treated like link references
        - Fixtures/params: none

    On failure, first check:
        - Whether the leading '!' prevented the bracket pair from being recognized
        - Whether the full-form label was read from the second bracket
    """
    findings = references.check_text("![alt][diagram]\n", "README.md")
    assert len(findings) == 1
    assert "diagram" in findings[0].message


def test_undefined_shortcut_is_not_a_finding():
    """
    [Unit] detectors references: verifies an undefined shortcut bracket is prose, not a finding.

    Scenario:
        Given a shortcut [missing] with no definition
        When DS108 recognition runs over the text
        Then no finding is produced, because a shortcut is only a link when defined.

    Boundaries:
        - Focus: shortcut false-positive safeguard (exclusion bullet 1)
        - Fixtures/params: none

    On failure, first check:
        - Whether shortcut uses were wrongly treated as undefined references
        - Whether the single bracket pair was recognized as a shortcut
    """
    assert references.check_text("This mentions [missing] in prose.\n", "README.md") == ()


def test_defined_shortcut_counts_as_a_use():
    """
    [Unit] detectors references: verifies a defined shortcut marks its definition used.

    Scenario:
        Given a shortcut [guide] and a [guide]: target definition, with unused warnings enabled
        When DS108 recognition runs over the text
        Then no finding is produced, proving the shortcut counted as a use.

    Boundaries:
        - Focus: shortcut-only-when-defined use tracking feeds the unused check
        - Fixtures/params: injected Config(unused_reference_definitions=True)

    On failure, first check:
        - Whether the defined shortcut was recorded as a use
        - Whether the unused check skipped the referenced definition
    """
    text = "See [guide] for details.\n\n[guide]: guide.md\n"
    config = Config(unused_reference_definitions=True)
    assert references.check_text(text, "README.md", config) == ()


def test_duplicate_definition_flags_the_second_declaration():
    """
    [Unit] detectors references: verifies a duplicate definition is flagged at the duplicate line.

    Scenario:
        Given two [guide]: definitions on different lines under the default warn policy
        When DS108 recognition runs over the text
        Then one warning is reported at the second (duplicate) declaration's line.

    Boundaries:
        - Focus: duplicate-definition detection at warn severity (algorithm bullet 3)
        - Fixtures/params: none

    On failure, first check:
        - Whether the first declaration was left clean and the second flagged
        - Whether the finding line is the duplicate's line
    """
    text = "[guide]: a.md\n[guide]: b.md\n"
    findings = references.check_text(text, "README.md")
    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].severity == "warning"
    assert "duplicate" in findings[0].message


def test_duplicate_definition_error_policy_raises_severity():
    """
    [Unit] detectors references: verifies the error duplicate policy reports at error severity.

    Scenario:
        Given two definitions for one label and duplicate_reference_definitions='error'
        When DS108 recognition runs over the text
        Then the duplicate finding carries error severity.

    Boundaries:
        - Focus: duplicate_reference_definitions enum wiring ('error' branch)
        - Fixtures/params: injected Config(duplicate_reference_definitions='error')

    On failure, first check:
        - Whether the policy value mapped to the finding severity
        - Whether the rule metadata severity leaked through instead
    """
    config = Config(duplicate_reference_definitions="error")
    findings = references.check_text("[a]: x.md\n[a]: y.md\n", "README.md", config)
    assert len(findings) == 1
    assert findings[0].severity == "error"


def test_duplicate_definition_off_policy_suppresses_the_finding():
    """
    [Unit] detectors references: verifies the off duplicate policy emits nothing.

    Scenario:
        Given two definitions for one label and duplicate_reference_definitions='off'
        When DS108 recognition runs over the text
        Then no duplicate finding is produced.

    Boundaries:
        - Focus: duplicate_reference_definitions 'off' branch
        - Fixtures/params: injected Config(duplicate_reference_definitions='off')

    On failure, first check:
        - Whether the off policy short-circuited duplicate detection
        - Whether another finding type leaked in
    """
    config = Config(duplicate_reference_definitions="off")
    assert references.check_text("[a]: x.md\n[a]: y.md\n", "README.md", config) == ()


def test_duplicate_whitespace_only_labels_are_duplicates():
    """
    [Unit] detectors references: verifies labels differing only by whitespace are duplicates.

    Scenario:
        Given two definitions whose labels differ solely by internal whitespace
        When DS108 recognition runs over the text
        Then the second is flagged as a duplicate after normalization.

    Boundaries:
        - Focus: whitespace-collapsing normalization drives duplicate detection
        - Fixtures/params: none

    On failure, first check:
        - Whether normalize_label collapsed the whitespace before comparison
        - Whether the duplicate landed on the second declaration
    """
    text = "[a  b]: x.md\n[a b]: y.md\n"
    findings = references.check_text(text, "README.md")
    assert len(findings) == 1
    assert findings[0].line == 2
    assert "duplicate" in findings[0].message


def test_unused_definition_only_warns_when_enabled():
    """
    [Unit] detectors references: verifies unused definitions warn only under the opt-in policy.

    Scenario:
        Given a definition that is never referenced
        When DS108 recognition runs with the default policy and then with the policy enabled
        Then the default run is clean and the enabled run reports one unused warning at the definition.

    Boundaries:
        - Focus: unused_reference_definitions default-off and enabled behavior (algorithm bullet 4)
        - Fixtures/params: injected Config(unused_reference_definitions=True)

    On failure, first check:
        - Whether the default run stayed clean (backward compatibility)
        - Whether the enabled run reported at the definition's line
    """
    text = "No one links this.\n\n[orphan]: orphan.md\n"
    assert references.check_text(text, "README.md") == ()
    findings = references.check_text(text, "README.md", Config(unused_reference_definitions=True))
    assert len(findings) == 1
    assert findings[0].line == 3
    assert "unused" in findings[0].message


def test_footnote_markers_are_not_link_references():
    """
    [Unit] detectors references: verifies footnote markers are ignored as link references.

    Scenario:
        Given a footnote use [^1] and its [^1]: definition, with unused warnings enabled
        When DS108 recognition runs over the text
        Then no finding is produced, because footnotes are not ordinary link refs.

    Boundaries:
        - Focus: footnote exclusion in both use and definition positions (algorithm bullet 5)
        - Fixtures/params: injected Config(unused_reference_definitions=True)

    On failure, first check:
        - Whether labels beginning with '^' were skipped
        - Whether the footnote definition was wrongly counted as unused
    """
    text = "A claim.[^1]\n\n[^1]: the footnote body\n"
    config = Config(unused_reference_definitions=True)
    assert references.check_text(text, "README.md", config) == ()


def test_escaped_brackets_are_literal_text():
    """
    [Unit] detectors references: verifies escaped brackets are not references.

    Scenario:
        Given escaped reference syntax \\[text\\]\\[missing\\]
        When DS108 recognition runs over the text
        Then no finding is produced.

    Boundaries:
        - Focus: escaped-bracket exclusion (exclusion bullet 3)
        - Fixtures/params: none

    On failure, first check:
        - Whether the backslash escape skipped the following bracket
        - Whether the escaped pair was wrongly parsed as a full reference
    """
    assert references.check_text("Literal \\[text\\]\\[missing\\] here.\n", "README.md") == ()


def test_escaped_closing_bracket_inside_a_label_matches_its_definition():
    """
    [Unit] detectors references: verifies a definition label containing an escaped bracket matches its use.

    Scenario:
        Given a use [x][a\\]b] and a definition [a\\]b]: http://u, plus an unescaped-bracket definition
        When DS108 recognition runs over the text
        Then no undefined finding is produced, matching the CommonMark renderer.

    Boundaries:
        - Focus: the definition regex honours the same backslash escapes as the use scanner
        - Fixtures/params: none (security review follow-up, Story 05.0)

    On failure, first check:
        - Whether _REF_DEF_RE reverted to a bare [^\\]]+ label class
        - Whether the use scanner and the definition matcher disagree about escapes
    """
    text = "[x][a\\]b]\n\n[a\\]b]: http://u\n"
    assert references.check_text(text, "README.md") == ()


def test_escaped_bracket_definition_flood_stays_linear():
    """
    [Unit] detectors references: verifies a flood of escaped-bracket definition labels stays near-linear.

    Scenario:
        Given one line per definition with increasing labels full of backslash escapes and no closer
        When DS108 recognition runs across a doubling series
        Then the scaling stays under the linear bound (the label alternation is unambiguous).

    Boundaries:
        - Focus: _REF_DEF_RE must not backtrack on unterminated escaped labels
        - Fixtures/params: doubling series of unit counts

    On failure, first check:
        - Whether the label alternation became ambiguous (overlapping classes)
        - Whether the regex is applied to unbounded unmasked text
    """
    assert_scales_linearly(
        build=lambda n: "".join(f"[a{i}" + "\\]" * 3 + "x" * (i % 7) + "\n" for i in range(n)),
        run=lambda payload: references.check_text(payload, "README.md"),
        sizes=_FLOOD_SIZES,
        expected_count=0,
        label="escaped_bracket_definition_flood",
    )


def test_reference_inside_fenced_code_is_ignored():
    """
    [Unit] detectors references: verifies reference-looking tokens inside a fence are ignored.

    Scenario:
        Given a broken reference that occurs only inside a fenced code block
        When DS108 recognition runs over the text
        Then no finding is produced because the fence is masked.

    Boundaries:
        - Focus: fenced-code masking (exclusion bullet 2)
        - Fixtures/params: none

    On failure, first check:
        - Whether the shared scanner's fence span was blanked before scanning
        - Whether a fence delimiter line was mis-scanned
    """
    text = "```\n[text][missing]\n```\n"
    assert references.check_text(text, "README.md") == ()


def test_reference_inside_inline_code_is_ignored():
    """
    [Unit] detectors references: verifies reference-looking tokens inside inline code are ignored.

    Scenario:
        Given a broken reference wrapped in an inline code span
        When DS108 recognition runs over the text
        Then no finding is produced because the span is masked.

    Boundaries:
        - Focus: inline-code masking (exclusion bullet 2)
        - Fixtures/params: none

    On failure, first check:
        - Whether the inline-code span offsets were blanked before scanning
        - Whether the backtick run was recognized by the shared scanner
    """
    assert references.check_text("Use `[text][missing]` literally.\n", "README.md") == ()


def test_reference_inside_html_comment_is_ignored():
    """
    [Unit] detectors references: verifies reference-looking tokens inside a comment are ignored.

    Scenario:
        Given a broken reference wrapped in an HTML comment closed on the same line
        When DS108 recognition runs over the text
        Then no finding is produced because the comment is masked.

    Boundaries:
        - Focus: HTML-comment masking (exclusion bullet 2)
        - Fixtures/params: none

    On failure, first check:
        - Whether the comment span was blanked before scanning
        - Whether the inline comment was recognized as closed in its paragraph
    """
    assert references.check_text("Note <!-- [text][missing] --> done.\n", "README.md") == ()


def test_inline_link_is_not_a_reference():
    """
    [Unit] detectors references: verifies an inline link is not treated as a reference.

    Scenario:
        Given an inline link [text](https://example.com)
        When DS108 recognition runs over the text
        Then no finding is produced because the bracket pair is an inline link, not a reference.

    Boundaries:
        - Focus: inline-link exclusion (exclusion bullet 5)
        - Fixtures/params: none

    On failure, first check:
        - Whether the '(' after ']' caused the bracket pair to be skipped
        - Whether the destination was mis-scanned as a shortcut
    """
    assert references.check_text("Visit [text](https://example.com) now.\n", "README.md") == ()


def test_definition_line_is_not_scanned_as_a_shortcut_use():
    """
    [Unit] detectors references: verifies a definition line does not self-reference.

    Scenario:
        Given a single [solo]: target definition and the unused policy enabled
        When DS108 recognition runs over the text
        Then one unused finding is produced, proving the definition's own [solo] was not a use.

    Boundaries:
        - Focus: definition lines are excluded from use scanning
        - Fixtures/params: injected Config(unused_reference_definitions=True)

    On failure, first check:
        - Whether the definition line was scanned for shortcut uses
        - Whether the label counted itself as used and suppressed the unused finding
    """
    findings = references.check_text("[solo]: solo.md\n", "README.md", Config(unused_reference_definitions=True))
    assert len(findings) == 1
    assert "unused" in findings[0].message


def test_multiple_missing_references_are_sorted():
    """
    [Unit] detectors references: verifies two distinct undefined labels yield two sorted findings.

    Scenario:
        Given two distinct undefined full references on different lines
        When DS108 recognition runs over the text
        Then two findings are produced in ascending line order.

    Boundaries:
        - Focus: one finding per undefined use and stable line ordering
        - Fixtures/params: none

    On failure, first check:
        - Whether both undefined labels were detected
        - Whether the findings were sorted by line
    """
    text = "See [a][alpha].\n\nAlso [b][beta].\n"
    findings = references.check_text(text, "README.md")
    assert len(findings) == 2
    assert [finding.line for finding in findings] == [1, 3]
    assert "alpha" in findings[0].message
    assert "beta" in findings[1].message


def test_crlf_line_numbers_are_one_based_physical():
    """
    [Unit] detectors references: verifies CRLF input keeps one-based physical line numbers.

    Scenario:
        Given CRLF-terminated lines with an undefined reference on the second line
        When DS108 recognition runs over the text
        Then the finding reports physical line 2.

    Boundaries:
        - Focus: CRLF line numbering via the shared physical-line splitter
        - Fixtures/params: none

    On failure, first check:
        - Whether CRLF was treated as a single line terminator
        - Whether the finding line matched the physical line
    """
    findings = references.check_text("Intro line.\r\nSee [t][missing].\r\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 2


def test_non_commonmark_normalization_yields_no_findings():
    """
    [Unit] detectors references: verifies an unmodelled normalization dialect is inert.

    Scenario:
        Given an undefined reference and reference_label_normalization set to an unmodelled value
        When DS108 recognition runs over the text
        Then no finding is produced rather than a guessed diagnostic.

    Boundaries:
        - Focus: reference_label_normalization guard (only 'commonmark' is modelled)
        - Fixtures/params: hand-built Config bypassing load-time enum validation

    On failure, first check:
        - Whether the dialect guard short-circuited before scanning
        - Whether the guard used the configured value
    """
    config = Config(reference_label_normalization="gfm")
    assert references.check_text("[t][missing]\n", "README.md", config) == ()


def test_detect_reads_documents_and_isolates_labels_per_document(tmp_path: Path):
    """
    [Unit] detectors references: verifies detect reads files and scopes labels per document.

    Scenario:
        Given a.md using [x][label] and b.md defining [label] in a separate file
        When detect runs over both documents
        Then a.md still reports the undefined label because labels do not cross documents.

    Boundaries:
        - Focus: detect file reading and per-document label scope
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether detect read each document's UTF-8 text
        - Whether a definition in another file wrongly satisfied the use
    """
    (tmp_path / "a.md").write_text("See [x][label].\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("[label]: target.md\n", encoding="utf-8")
    documents = (models.Document(path="a.md", bytes=16), models.Document(path="b.md", bytes=20))
    findings = references.detect(tmp_path, documents)
    assert _codes(findings) == ["DS108"]
    assert findings[0].path == "a.md"
    assert findings[0].line == 1


def test_repeated_scans_are_stable():
    """
    [Unit] detectors references: verifies repeated recognition over the same text is deterministic.

    Scenario:
        Given a document mixing an undefined reference and a duplicate definition
        When DS108 recognition runs twice over the identical text
        Then both runs return identical findings.

    Boundaries:
        - Focus: deterministic, order-stable output across repeated scans
        - Fixtures/params: none

    On failure, first check:
        - Whether set iteration leaked into the finding order
        - Whether any per-run state persisted between calls
    """
    text = "See [t][missing].\n\n[a]: x.md\n[a]: y.md\n"
    first = references.check_text(text, "README.md")
    second = references.check_text(text, "README.md")
    assert first == second
    assert len(first) == 2


#: A doubling series of unit counts for the multi-line and single-line bracket floods;
#: the detector does O(characters) work, so these separate linear from quadratic cheaply.
_FLOOD_SIZES = (2_000, 4_000, 8_000, 16_000)


def test_single_line_reference_flood_stays_linear():
    """
    [Unit] detectors references: verifies a single-line full-reference flood stays near-linear.

    Scenario:
        Given one very long line of increasing, non-repeating full references [a{i}][b{i}]
        When DS108 recognition runs across a doubling series
        Then the exact undefined-finding count holds and the scaling stays under the linear bound.

    Boundaries:
        - Focus: _scan_uses and _closing_bracket must not rescan the line tail per '['
        - Fixtures/params: doubling series of unit counts

    On failure, first check:
        - Whether the use scanner advanced its cursor past each consumed bracket construct
        - Whether the closing-bracket search became quadratic on a long line
    """
    assert_scales_linearly(
        build=lambda n: "".join(f"[a{i}][b{i}]" for i in range(n)),
        run=lambda payload: references.check_text(payload, "README.md"),
        sizes=_FLOOD_SIZES,
        expected_count=lambda n: n,
        label="single_line_reference_flood",
    )


def test_multi_line_reference_flood_stays_linear():
    """
    [Unit] detectors references: verifies a multi-line full-reference flood stays near-linear.

    Scenario:
        Given many lines each carrying one increasing, non-repeating undefined full reference
        When DS108 recognition runs across a doubling series
        Then the exact undefined-finding count holds and the scaling stays under the linear bound.

    Boundaries:
        - Focus: the per-line loop and use scanner over many lines
        - Fixtures/params: doubling series of line counts

    On failure, first check:
        - Whether per-line work stayed constant per line
        - Whether the mask build scaled with the line count
    """
    assert_scales_linearly(
        build=lambda n: "".join(f"[a{i}][b{i}]\n" for i in range(n)),
        run=lambda payload: references.check_text(payload, "README.md"),
        sizes=_FLOOD_SIZES,
        expected_count=lambda n: n,
        label="multi_line_reference_flood",
    )


def test_definition_and_unused_flood_stays_linear():
    """
    [Unit] detectors references: verifies a definition/unused flood stays near-linear.

    Scenario:
        Given many lines each defining a distinct, never-referenced label, with unused warnings on
        When DS108 recognition runs across a doubling series
        Then the exact unused-finding count holds and the scaling stays under the linear bound.

    Boundaries:
        - Focus: the reference-definition regex, the definition walk, and the unused walk
        - Fixtures/params: doubling series of definition counts, Config(unused_reference_definitions=True)

    On failure, first check:
        - Whether the definition regex stayed anchored and linear
        - Whether the used-label set membership stayed constant-time per definition
    """
    config = Config(unused_reference_definitions=True)
    assert_scales_linearly(
        build=lambda n: "".join(f"[a{i}]: x{i}.md\n" for i in range(n)),
        run=lambda payload: references.check_text(payload, "README.md", config),
        sizes=_FLOOD_SIZES,
        expected_count=lambda n: n,
        label="definition_and_unused_flood",
    )


def test_masked_fence_flood_stays_linear():
    """
    [Unit] detectors references: verifies masking a huge fenced body stays near-linear.

    Scenario:
        Given a single growing fenced code body full of reference-looking tokens plus one
            undefined reference after the fence
        When DS108 recognition runs across a doubling series
        Then exactly one finding holds at every size and the mask build stays under the linear bound.

    Boundaries:
        - Focus: _masked_lines blanks a large fenced region in O(characters)
        - Fixtures/params: doubling series of in-fence unit counts

    On failure, first check:
        - Whether the fence span was blanked in a single linear pass
        - Whether only the post-fence reference was reported
    """

    def builder(n: int) -> str:
        """Return a fenced body of ``n`` reference-looking units plus one undefined reference.

        :param n: The number of in-fence reference-looking units.
        :returns: The Markdown source for this flood size.
        """
        return "```\n" + ("[a][b] " * n) + "\n```\n[x][missing]\n"

    assert_scales_linearly(
        build=builder,
        run=lambda payload: references.check_text(payload, "README.md"),
        sizes=_FLOOD_SIZES,
        expected_count=1,
        label="masked_fence_flood",
    )


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        ("unused_reference_definitions", False),
        ("duplicate_reference_definitions", "warn"),
        ("reference_label_normalization", "commonmark"),
    ],
)
def test_reference_config_defaults(option: str, expected: object):
    """
    [Unit] config: verifies DS108 reference option defaults match the specification.

    Scenario:
        Given a default Config instance
        When each DS108 reference option is read
        Then it equals the backward-compatible default from the story.

    Boundaries:
        - Focus: DS108 config option defaults
        - Fixtures/params: option/expected (parametrized, 3 cases)

    On failure, first check:
        - Whether a Config field default drifted
        - Whether the story's default for the option changed
    """
    assert getattr(Config(), option) == expected


def test_reference_options_load_from_standalone_toml(tmp_path: Path):
    """
    [Unit] config: verifies DS108 reference options load from standalone TOML.

    Scenario:
        Given a docsentinel.toml setting all three DS108 reference options
        When load_config reads the scan root
        Then the typed Config reflects each configured value.

    Boundaries:
        - Focus: standalone TOML loading of DS108 options
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the loader recognized each option name
        - Whether the enum and bool coercions applied
    """
    (tmp_path / "docsentinel.toml").write_text(
        "unused_reference_definitions = true\n"
        'duplicate_reference_definitions = "error"\n'
        'reference_label_normalization = "commonmark"\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.unused_reference_definitions is True
    assert config.duplicate_reference_definitions == "error"
    assert config.reference_label_normalization == "commonmark"


def test_reference_options_load_from_pyproject_table(tmp_path: Path):
    """
    [Unit] config: verifies DS108 reference options load from the pyproject table.

    Scenario:
        Given a [tool.doc_sentinel] table setting the DS108 options
        When load_config reads the scan root
        Then the typed Config reflects each configured value.

    Boundaries:
        - Focus: pyproject table loading of DS108 options
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the pyproject unwrapping recognized the options
        - Whether the off duplicate policy coerced correctly
    """
    (tmp_path / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nunused_reference_definitions = false\nduplicate_reference_definitions = "off"\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config.unused_reference_definitions is False
    assert config.duplicate_reference_definitions == "off"


@pytest.mark.parametrize("value", ['"warning"', '"on"', "true", "1"])
def test_invalid_duplicate_reference_policy_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies an out-of-vocabulary duplicate policy raises.

    Scenario:
        Given a TOML file with an invalid duplicate_reference_definitions value
        When load_config validates the option
        Then a ConfigError naming the accepted vocabulary is raised.

    Boundaries:
        - Focus: duplicate_reference_definitions enum validation
        - Fixtures/params: tmp_path, value (parametrized, 4 cases)

    On failure, first check:
        - Whether the enum allowlist still names off/warn/error
        - Whether the loader validated the option at all
    """
    (tmp_path / "docsentinel.toml").write_text(f"duplicate_reference_definitions = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="duplicate_reference_definitions must be one of:"):
        load_config(tmp_path)


def test_invalid_reference_label_normalization_raises(tmp_path: Path):
    """
    [Unit] config: verifies an unmodelled normalization dialect is rejected by the loader.

    Scenario:
        Given a TOML file setting reference_label_normalization to an unmodelled value
        When load_config validates the option
        Then a ConfigError naming the accepted vocabulary is raised.

    Boundaries:
        - Focus: reference_label_normalization enum validation
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the enum allowlist still fixes 'commonmark'
        - Whether the loader validated the option
    """
    (tmp_path / "docsentinel.toml").write_text('reference_label_normalization = "gfm"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="reference_label_normalization must be one of: commonmark"):
        load_config(tmp_path)


@pytest.mark.parametrize("value", ['"true"', "1", '["x"]'])
def test_invalid_unused_reference_definitions_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies a non-boolean unused_reference_definitions raises.

    Scenario:
        Given a TOML file with a non-boolean unused_reference_definitions value
        When load_config validates the option
        Then a ConfigError about a boolean value is raised.

    Boundaries:
        - Focus: unused_reference_definitions boolean validation
        - Fixtures/params: tmp_path, value (parametrized, 3 cases)

    On failure, first check:
        - Whether the option stayed in the boolean allowlist
        - Whether the loader coerced the value to bool
    """
    (tmp_path / "docsentinel.toml").write_text(f"unused_reference_definitions = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unused_reference_definitions must be true or false"):
        load_config(tmp_path)
