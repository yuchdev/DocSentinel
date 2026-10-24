"""Unit tests for DS105 heading-hierarchy recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition helpers directly. Detection over committed Markdown assets is the
job of the Story 03.0 Task 03 integration suite, which runs once ``DS105`` is
registered together with its ``tests/assets/ds105/*`` fixtures (Task 02).
"""

from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import headings


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors headings: verifies DS105 metadata and its fast-profile registration.

    Scenario:
        Given the DS105 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered with its analyzer.

    Boundaries:
        - Focus: rule metadata and registration state only
        - Fixtures/params: none

    On failure, first check:
        - Whether DS105 was registered as a fast-profile rule with its analyzer
        - Whether a metadata field (profile, severity, title) drifted
    """
    assert headings.DS105.code == "DS105"
    assert headings.DS105.profile == "fast"
    assert headings.DS105.severity == "warning"
    assert headings.DS105.title == "Heading hierarchy and section levels"
    # Registration lands with the committed Task 02 fixtures.
    assert rules.RULES["DS105"] is headings.DS105
    assert rules.ANALYZERS["DS105"] is headings.detect


def test_sequential_heading_levels_are_clean():
    """
    [Unit] detectors headings: verifies a well-formed descending hierarchy is clean.

    Scenario:
        Given H1 > H2 > H3 followed by a return to H2
        When DS105 recognition runs
        Then no finding is produced.

    Boundaries:
        - Focus: normal case; descending and ascending steps are both valid
        - Fixtures/params: inline string

    On failure, first check:
        - The one-level step tolerance in the skip check
        - That reducing the level (H3 back to H2) is permitted
    """
    assert headings.check_text("# A\n## B\n### C\n## D\n", "README.md") == ()


def test_single_root_heading_is_clean():
    """
    [Unit] detectors headings: verifies a lone top-level heading is clean.

    Scenario:
        Given a document with one H1 and no subsections
        When DS105 recognition runs
        Then no finding is produced.

    Boundaries:
        - Focus: first-heading check with no successor headings
        - Fixtures/params: inline string

    On failure, first check:
        - The first-heading level comparison against first_heading_level
    """
    assert headings.check_text("# Title\n\nBody text.\n", "README.md") == ()


def test_setext_then_atx_is_clean():
    """
    [Unit] detectors headings: verifies a setext H1 followed by an ATX H2 is clean.

    Scenario:
        Given a setext level-one title followed by an ATX level-two heading
        When DS105 recognition runs
        Then setext and ATX headings share one hierarchy and no finding appears.

    Boundaries:
        - Focus: setext participation in the hierarchy (support enabled by default)
        - Fixtures/params: inline string

    On failure, first check:
        - That the shared scanner emits the setext heading as level one
        - The one-level step from the setext H1 to the ATX H2
    """
    assert headings.check_text("Title\n=====\n\n## Section\n", "README.md") == ()


def test_first_heading_level_three_flags_opening_line():
    """
    [Unit] detectors headings: verifies a document opening at H3 is flagged.

    Scenario:
        Given a document whose first heading is level three under the default root policy
        When DS105 recognition runs
        Then one warning is produced at the opening heading line.

    Boundaries:
        - Focus: the first-heading-level check (algorithm bullet 2)
        - Fixtures/params: inline string

    On failure, first check:
        - The first-heading branch comparing level to first_heading_level
        - That the reported line is the offending heading line
    """
    findings = headings.check_text("### Deep start\n", "README.md")
    assert len(findings) == 1
    assert findings[0].rule == "DS105"
    assert findings[0].severity == "warning"
    assert findings[0].line == 1
    assert findings[0].path == "README.md"
    assert "level 3" in findings[0].message


def test_skipped_intermediate_level_flags_offending_heading():
    """
    [Unit] detectors headings: verifies an H2-to-H4 jump flags the H4 line only.

    Scenario:
        Given H1, then H2, then a direct jump to H4
        When DS105 recognition runs
        Then one warning is produced at the H4 line, not the predecessor line.

    Boundaries:
        - Focus: the level-skip check and offending-line fidelity (bullets 2 and 4)
        - Fixtures/params: inline string

    On failure, first check:
        - The ``level > previous_level + 1`` comparison
        - That the line points at the deeper heading, not its predecessor
    """
    findings = headings.check_text("# A\n## B\n#### D\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 3
    assert "skips" in findings[0].message


def test_multiple_levels_skipped_flags_exactly_once():
    """
    [Unit] detectors headings: verifies a single big jump yields one finding, not many.

    Scenario:
        Given H1 followed directly by H5
        When DS105 recognition runs
        Then exactly one warning is produced at the H5 line.

    Boundaries:
        - Focus: one finding per offending heading, no per-skipped-level cascade
        - Fixtures/params: inline string

    On failure, first check:
        - That the skip check emits a single finding for one heading
        - That previous_level advances to the offending level afterwards
    """
    findings = headings.check_text("# A\n##### E\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 2


def test_heading_inside_code_fence_is_ignored():
    """
    [Unit] detectors headings: verifies fenced heading syntax does not affect hierarchy.

    Scenario:
        Given an H1 and a fenced code block containing a '###' line
        When DS105 recognition runs
        Then the fenced line is not a heading and no finding is produced.

    Boundaries:
        - Focus: fenced-code masking from the shared scanner (bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - That the shared scanner masks fenced lines from heading tokenization
    """
    assert headings.check_text("# Title\n\n```\n### not a heading\n```\n", "README.md") == ()


def test_heading_inside_html_comment_is_ignored():
    """
    [Unit] detectors headings: verifies heading syntax in a multi-line comment is ignored.

    Scenario:
        Given an H1 and a multi-line HTML comment whose body contains '##' lines
        When DS105 recognition runs
        Then the commented heading-looking lines are excluded and no finding appears.

    Boundaries:
        - Focus: comment-region exclusion the scanner does not apply to headings (bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - The comment-span exclusion in _excluded_lines
        - That the commented '##' and '####' lines are not evaluated as a skip
    """
    text = "# Title\n\n<!--\n## Hidden\n#### Deeper hidden\n-->\n\n## Section\n"
    assert headings.check_text(text, "README.md") == ()


def test_yaml_frontmatter_is_skipped_before_first_heading():
    """
    [Unit] detectors headings: verifies leading YAML frontmatter does not become a heading.

    Scenario:
        Given a YAML frontmatter block followed by an H1 and an H2
        When DS105 recognition runs
        Then the frontmatter (including its closing '---') is excluded and no finding appears.

    Boundaries:
        - Focus: frontmatter exclusion that prevents a spurious setext heading (bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - The _frontmatter_end_line boundary detection
        - That the closing '---' is not mistaken for a setext underline heading
    """
    text = "---\ntitle: Doc\nauthor: Me\n---\n\n# Title\n\n## Section\n"
    assert headings.check_text(text, "README.md") == ()


def test_frontmatter_with_vertical_whitespace_uses_scanner_line_numbering():
    """
    [Unit] detectors headings: verifies frontmatter boundary uses the scanner's line numbering.

    Scenario:
        Given a leading YAML frontmatter block whose body line carries a vertical tab
            and a form feed, followed by an H1 and a level-skipping H3
        When DS105 recognition runs
        Then the closing '---' is located at physical line 3 (not renumbered by the
            Unicode line breaks str.splitlines would honor), the H1 on line 5 survives
            exclusion, and the only finding is the H3 level skip at line 7.

    Boundaries:
        - Focus: _frontmatter_end_line aligning with the scanner's \\r\\n/\\r/\\n splitter
        - Fixtures/params: inline string with \\x0b and \\x0c in the frontmatter body

    On failure, first check:
        - That _frontmatter_end_line splits on scanner terminators, not str.splitlines
        - That the exclusion range does not swallow the first real heading
    """
    text = "---\nsummary: a\x0bb\x0cc\n---\n\n# Title\n\n### Deep\n"
    assert headings._frontmatter_end_line(text) == 3
    findings = headings.check_text(text, "README.md")
    assert len(findings) == 1
    assert findings[0].line == 7
    assert "skips a level" in findings[0].message


def test_multiple_h1_policy_warns_only_when_enabled():
    """
    [Unit] detectors headings: verifies repeated H1 warns only under the warn policy.

    Scenario:
        Given two H1 headings scanned under the default allow policy and the warn policy
        When DS105 recognition runs under each
        Then allow yields no finding while warn flags the second H1 line.

    Boundaries:
        - Focus: multiple_h1_policy independence from the level checks (bullet 5)
        - Fixtures/params: Config toggled on multiple_h1_policy

    On failure, first check:
        - The seen_h1 gate and the warn branch
        - That a reduced level (H2 back to H1) is not also reported as a skip
    """
    text = "# First\n\n## Section\n\n# Second\n"
    assert headings.check_text(text, "README.md") == ()
    warned = headings.check_text(text, "README.md", Config(multiple_h1_policy="warn"))
    assert len(warned) == 1
    assert warned[0].line == 5
    assert "top-level" in warned[0].message


def test_first_heading_level_two_accepts_h2_start():
    """
    [Unit] detectors headings: verifies a configured non-root start level is honored.

    Scenario:
        Given a document opening at H2 and first_heading_level set to two
        When DS105 recognition runs
        Then the H2 start is accepted and no finding is produced.

    Boundaries:
        - Focus: first_heading_level configurability (1..6)
        - Fixtures/params: Config(first_heading_level=2)

    On failure, first check:
        - The first-heading comparison using the configured level
    """
    assert headings.check_text("## Section\n\n### Sub\n", "README.md", Config(first_heading_level=2)) == ()


def test_setext_support_disabled_excludes_setext_headings():
    """
    [Unit] detectors headings: verifies disabling setext support drops setext headings.

    Scenario:
        Given a setext H2 title under default and setext-disabled settings
        When DS105 recognition runs under each
        Then the default flags the deep first heading while the disabled run has no headings.

    Boundaries:
        - Focus: setext_heading_support toggle (invalid-for-dialect style opt-out)
        - Fixtures/params: Config(setext_heading_support=False)

    On failure, first check:
        - The style filter in _active_headings
        - That an excluded setext heading leaves nothing to evaluate
    """
    text = "Section\n-------\n\nBody.\n"
    assert len(headings.check_text(text, "README.md")) == 1
    assert headings.check_text(text, "README.md", Config(setext_heading_support=False)) == ()


def test_heading_level_policy_off_suppresses_level_checks():
    """
    [Unit] detectors headings: verifies the off policy disables first and skip checks.

    Scenario:
        Given a document opening at H3 scanned with heading_level_policy off
        When DS105 recognition runs
        Then no level finding is produced.

    Boundaries:
        - Focus: heading_level_policy gate so a disabled policy never masquerades as evaluated
        - Fixtures/params: Config(heading_level_policy="off")

    On failure, first check:
        - The check_levels gate in _heading_findings
    """
    assert headings.check_text("### Deep start\n", "README.md", Config(heading_level_policy="off")) == ()


def test_blockquote_and_inline_hashes_are_not_headings():
    """
    [Unit] detectors headings: verifies quoted and inline hashes are not headings.

    Scenario:
        Given an H1, a blockquoted '> ###' line, and inline literal hashes in prose
        When DS105 recognition runs
        Then none of the hash runs count as headings and no finding appears.

    Boundaries:
        - Focus: false-positive safeguards for blockquote and inline '#' (exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That the ATX regex requires a line-initial marker, excluding '> ###'
        - That inline hashes inside prose never match a heading opener
    """
    text = "# Title\n\n> ### Quoted example\n\nUse C# and the `#` sigil inline.\n"
    assert headings.check_text(text, "README.md") == ()


def test_crlf_input_preserves_offending_line():
    """
    [Unit] detectors headings: verifies CRLF input keeps the offending heading line.

    Scenario:
        Given CRLF-terminated Markdown with an H2-to-H4 jump on line 3
        When DS105 recognition runs
        Then the single finding reports physical line 3.

    Boundaries:
        - Focus: CRLF line numbering for the skip diagnostic
        - Fixtures/params: inline string

    On failure, first check:
        - The scanner's CRLF terminator handling
        - The one-based offending line on the emitted finding
    """
    findings = headings.check_text("# A\r\n## B\r\n#### D\r\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 3


def test_detect_reads_documents_and_skips_non_markdown(tmp_path: Path):
    """
    [Unit] detectors headings: verifies detect reads .md files and ignores others.

    Scenario:
        Given a Markdown file opening at H3 and a non-Markdown sibling
        When detect runs over both documents
        Then only the Markdown file contributes a single DS105 finding.

    Boundaries:
        - Focus: document reading, .md filtering, and path propagation in detect
        - Fixtures/params: tmp_path with two committed files

    On failure, first check:
        - The .md suffix filter in detect
        - That the finding path matches the Markdown document path
    """
    (tmp_path / "README.md").write_text("### Deep start\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("### Deep start\n", encoding="utf-8")
    documents = (models.Document("README.md", 1), models.Document("notes.txt", 1))
    findings = headings.detect(tmp_path, documents)
    assert len(findings) == 1
    assert findings[0].path == "README.md"


def test_detect_surfaces_invalid_utf8_rather_than_false_clean(tmp_path: Path):
    """
    [Unit] detectors headings: verifies invalid UTF-8 raises instead of passing silently.

    Scenario:
        Given a Markdown document containing invalid UTF-8 bytes
        When detect attempts to read it
        Then a UnicodeDecodeError propagates rather than a false clean result.

    Boundaries:
        - Focus: explicit handling of unreadable input (no silent clean signal)
        - Fixtures/params: tmp_path file with invalid bytes

    On failure, first check:
        - The UTF-8 read in _read_text
        - That unreadable input is never reported as zero findings
    """
    (tmp_path / "README.md").write_bytes(b"# Title\n\xff\xfe\n")
    with pytest.raises(UnicodeDecodeError):
        headings.detect(tmp_path, (models.Document("README.md", 1),))


def test_repeated_recognition_is_deterministic():
    """
    [Unit] detectors headings: verifies repeated scans produce identical findings.

    Scenario:
        Given the same Markdown text scanned twice
        When DS105 recognition runs on each pass
        Then the two finding tuples are equal.

    Boundaries:
        - Focus: determinism and absence of shared mutable state
        - Fixtures/params: inline string

    On failure, first check:
        - Any module-level mutable caches
        - Ordering stability of the shared scanner's heading list
    """
    text = "# A\n#### D\n## B\n#### E\n"
    first = headings.check_text(text, "README.md")
    assert first == headings.check_text(text, "README.md")
    # Pin the expected findings so the equality above cannot pass on a shared
    # empty result: the H1->H4 and H2->H4 jumps each skip a level.
    assert [finding.line for finding in first] == [2, 4]
    assert all(finding.rule == "DS105" and "skips a level" in finding.message for finding in first)


def test_many_prose_headings_stay_linear_and_bounded():
    """
    [Unit] detectors headings: verifies large non-fenced heading input stays bounded.

    Scenario:
        Given one H1 followed by thousands of valid H2 prose headings, and separately
            thousands of deep H6 headings
        When DS105 recognition runs over each
        Then the valid run yields zero findings and the deep run yields exactly one.

    Boundaries:
        - Focus: linear handling and a ratio-based bound on adversarial non-fenced prose
        - Fixtures/params: generated inline strings (not fenced, so the scanner cannot skip them)

    On failure, first check:
        - That valid one-level steps never accumulate findings
        - That only the first deep heading trips the first-heading check, not each H6
    """
    valid = "# Title\n" + ("## Section\n\ntext\n\n" * 3000)
    assert headings.check_text(valid, "README.md") == ()
    deep = "###### Deep\n" * 3000
    deep_findings = headings.check_text(deep, "README.md")
    assert len(deep_findings) == 1
    assert deep_findings[0].line == 1
