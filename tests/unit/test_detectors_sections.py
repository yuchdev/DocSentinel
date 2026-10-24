"""Unit tests for DS106 empty/contentless-section recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition helpers directly. Detection over committed Markdown assets is the
job of the Story 04.0 Task 03 integration suite, which runs once ``DS106`` is
registered together with its ``tests/assets/ds106/*`` fixtures (Task 02).
"""

import random
import re
from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import sections

#: The pre-refactor regex implementation of the per-line visible-text strippers,
#: kept verbatim as a parity oracle. The shipped detector replaced these backtracking
#: ``re.sub`` passes with forward-only linear scanners; the oracle lets a generated
#: corpus prove the replacement is byte-identical on legitimate input.
_ORACLE_SINGLE_LINE_COMMENT = re.compile(r"<!--.*?-->")
_ORACLE_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_ORACLE_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_ORACLE_COMMENT_OPEN = re.compile(r"<!--.*$")
_ORACLE_COMMENT_CLOSE = re.compile(r"^.*?-->")


def _oracle_visible_text(line: str, line_number: int, masks: object, count_placeholders: bool) -> str:
    """Return the old regex-based visible text of a line (parity oracle for _visible_text)."""
    text = line
    if not count_placeholders:
        if line_number in masks.comment_interior_lines:  # type: ignore[attr-defined]
            return ""
        if line_number in masks.comment_open_lines:  # type: ignore[attr-defined]
            text = _ORACLE_COMMENT_OPEN.sub(" ", text)
        if line_number in masks.comment_close_lines:  # type: ignore[attr-defined]
            text = _ORACLE_COMMENT_CLOSE.sub(" ", text)
        text = _ORACLE_SINGLE_LINE_COMMENT.sub(" ", text)
    text = _ORACLE_IMAGE.sub(" ", text)
    text = _ORACLE_HTML_TAG.sub(" ", text)
    return text


#: Token alphabet for the parity corpus: images (complete and broken), bracket/paren
#: soup, HTML comments (single-line, unclosed, multiple), real and malformed HTML
#: tags, entities, control-ish punctuation and plain words.
_CORPUS_TOKENS: tuple[str, ...] = (
    "![",
    "![alt]",
    "![alt](img.png)",
    "![](x)",
    "]",
    "[",
    "(",
    ")",
    "link",
    "<!--",
    "-->",
    "<!-- note -->",
    "<!---->",
    "<!-->",
    '<a href="x">',
    "</a>",
    "<br/>",
    "<span>",
    "</span>",
    "<",
    ">",
    "<1",
    "< ",
    "&amp;",
    "word",
    "text",
    " ",
    "TODO",
    "42",
)


def _corpus_lines(count: int, seed: int = 20251022, max_tokens: int = 12) -> list[str]:
    """Return ``count`` seeded-random single lines mixing the parity token alphabet."""
    generator = random.Random(seed)
    lines: list[str] = []
    for _ in range(count):
        length = generator.randint(0, max_tokens)
        lines.append("".join(generator.choice(_CORPUS_TOKENS) for _ in range(length)))
    return lines


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors sections: verifies DS106 metadata and its fast-profile registration.

    Scenario:
        Given the DS106 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered with its analyzer.

    Boundaries:
        - Focus: rule metadata and registration state only
        - Fixtures/params: none

    On failure, first check:
        - Whether DS106 was registered as a fast-profile rule with its analyzer
        - Whether a metadata field (profile, severity, title) drifted
    """
    assert sections.DS106.code == "DS106"
    assert sections.DS106.profile == "fast"
    assert sections.DS106.severity == "warning"
    assert sections.DS106.title == "Empty or contentless sections"
    # Registration lands with the committed Task 02 fixtures.
    assert rules.RULES["DS106"] is sections.DS106
    assert rules.ANALYZERS["DS106"] is sections.detect


def test_leaf_section_with_prose_is_clean():
    """
    [Unit] detectors sections: verifies a leaf section with a paragraph is clean.

    Scenario:
        Given a single heading followed by an explanatory paragraph
        When DS106 recognition runs
        Then no finding is produced.

    Boundaries:
        - Focus: normal case; visible prose counts as content (bullet 1)
        - Fixtures/params: inline string

    On failure, first check:
        - The prose text-character accumulation in _section_content
    """
    assert sections.check_text("# Title\n\nAn explanatory paragraph.\n", "README.md") == ()


def test_parent_with_child_section_is_not_flagged():
    """
    [Unit] detectors sections: verifies a structural parent holding only a child is clean.

    Scenario:
        Given an H2 parent with no direct body and an H3 child that has prose
        When DS106 recognition runs under the default leaf policy
        Then the parent is treated as structural and no finding is produced.

    Boundaries:
        - Focus: leaf-only inspection; parents with children are not empty (bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - The is-leaf test in _checked_indices
        - That the H3 child's prose is attributed to the H3 section
    """
    text = "## Parent\n\n### Child\n\nChild body text.\n"
    assert sections.check_text(text, "README.md") == ()


def test_image_only_leaf_section_is_clean_by_default():
    """
    [Unit] detectors sections: verifies an image-only section counts as content by default.

    Scenario:
        Given a leaf section whose only body is a Markdown image
        When DS106 recognition runs with image_content_counts enabled (default)
        Then the image supplies content and no finding is produced.

    Boundaries:
        - Focus: image_content_counts true path (bullet 1 / exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That the image token line is recorded in image_lines
        - That image syntax is stripped from the prose check so it does not double count
    """
    text = "# Diagram\n\n![architecture](diagram.png)\n"
    assert sections.check_text(text, "README.md") == ()


def test_image_only_section_flagged_when_images_do_not_count():
    """
    [Unit] detectors sections: verifies disabling image counting flags an image-only section.

    Scenario:
        Given an image-only leaf section and image_content_counts disabled
        When DS106 recognition runs
        Then the image no longer counts and one finding is produced.

    Boundaries:
        - Focus: image_content_counts false path; image syntax is not prose
        - Fixtures/params: Config(image_content_counts=False)

    On failure, first check:
        - That image_lines is empty when counting is disabled
        - That _IMAGE_RE strips the image so its alt/target text is not prose
    """
    text = "# Diagram\n\n![architecture](diagram.png)\n"
    findings = sections.check_text(text, "README.md", Config(image_content_counts=False))
    assert len(findings) == 1
    assert findings[0].line == 1


def test_empty_terminal_heading_is_flagged():
    """
    [Unit] detectors sections: verifies a trailing heading with no body is flagged.

    Scenario:
        Given a section with prose followed by a trailing empty heading at EOF
        When DS106 recognition runs
        Then only the trailing empty section is flagged, at its heading line.

    Boundaries:
        - Focus: last-section-at-EOF handling (bullet 4)
        - Fixtures/params: inline string

    On failure, first check:
        - That the final heading's section extends to end of file
        - That the reported line is the trailing heading line
    """
    findings = sections.check_text("# Intro\n\nBody.\n\n## Empty\n", "README.md")
    assert len(findings) == 1
    assert findings[0].rule == "DS106"
    assert findings[0].severity == "warning"
    assert findings[0].path == "README.md"
    assert findings[0].line == 5
    assert "Empty" in findings[0].message


def test_comment_only_section_is_flagged_by_default():
    """
    [Unit] detectors sections: verifies a section holding only a comment is flagged.

    Scenario:
        Given a leaf section whose only body is an HTML comment
        When DS106 recognition runs under the default ignore placeholder policy
        Then the comment does not count and one finding is produced.

    Boundaries:
        - Focus: placeholder_content_policy ignore for comments (bullet 2 / exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That the single-line comment is stripped in _visible_text
        - That the comment is not recorded as block content
    """
    findings = sections.check_text("# Section\n\n<!-- forthcoming -->\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 1


def test_comment_only_section_counts_under_count_policy():
    """
    [Unit] detectors sections: verifies the count policy lets a comment supply content.

    Scenario:
        Given a comment-only leaf section and placeholder_content_policy set to count
        When DS106 recognition runs
        Then the comment text counts as content and no finding is produced.

    Boundaries:
        - Focus: placeholder_content_policy count path
        - Fixtures/params: Config(placeholder_content_policy="count")

    On failure, first check:
        - That _visible_text keeps comment text when counting placeholders
        - That the HTML-tag strip does not also remove comment text
    """
    text = "# Section\n\n<!-- forthcoming -->\n"
    assert sections.check_text(text, "README.md", Config(placeholder_content_policy="count")) == ()


def test_bare_marker_word_is_visible_content_not_flagged():
    """
    [Unit] detectors sections: verifies a visible marker word counts as content.

    Scenario:
        Given a leaf section whose only body is the visible word "TODO"
        When DS106 recognition runs under the default ignore placeholder policy
        Then the word is text a reader sees, so it counts as content and no finding is produced.

    Boundaries:
        - Focus: visible prose is never stripped; marker detection is DS119's territory, not DS106's
        - Fixtures/params: inline string

    On failure, first check:
        - That _visible_text no longer strips TODO/TBD/FIXME/WIP markers
    """
    assert sections.check_text("# Section\n\nTODO\n", "README.md") == ()


def test_whitespace_and_thematic_break_only_section_is_flagged():
    """
    [Unit] detectors sections: verifies spaces and thematic rules are not content.

    Scenario:
        Given a leaf section whose body is only spaces and a thematic break
        When DS106 recognition runs
        Then neither counts as content and one finding is produced.

    Boundaries:
        - Focus: blank and thematic-break skipping (bullet 2)
        - Fixtures/params: inline string

    On failure, first check:
        - The blank-line skip and _THEMATIC_RE match in _section_content
    """
    findings = sections.check_text("# Section\n\n   \n\n---\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 1


def test_horizontal_rule_then_prose_is_clean():
    """
    [Unit] detectors sections: verifies a separator followed by prose is clean.

    Scenario:
        Given a leaf section with a thematic break and then an actual paragraph
        When DS106 recognition runs
        Then the prose supplies content and no finding is produced.

    Boundaries:
        - Focus: thematic break is skipped but following prose still counts
        - Fixtures/params: inline string

    On failure, first check:
        - That the thematic break line contributes zero characters
        - That the following prose line is counted
    """
    assert sections.check_text("# Section\n\n---\n\nReal prose here.\n", "README.md") == ()


def test_nonempty_fence_counts_but_blank_fence_does_not():
    """
    [Unit] detectors sections: verifies fenced content counts only when non-empty.

    Scenario:
        Given one section with a code fence containing a line and another whose fence
            holds only blank lines
        When DS106 recognition runs
        Then the non-empty fence is content (clean) and the blank fence is flagged.

    Boundaries:
        - Focus: fence body_nonempty predicate (bullet 2)
        - Fixtures/params: inline strings

    On failure, first check:
        - That fence_content_lines is built only for body_nonempty fences
        - That all fenced lines are otherwise skipped from prose
    """
    assert sections.check_text("# Code\n\n```\nprint(1)\n```\n", "README.md") == ()
    findings = sections.check_text("# Code\n\n```\n\n\n```\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 1


def test_table_only_section_is_clean():
    """
    [Unit] detectors sections: verifies a well-formed table supplies content.

    Scenario:
        Given a leaf section whose only body is a GFM pipe table
        When DS106 recognition runs
        Then the table counts as content and no finding is produced.

    Boundaries:
        - Focus: table_rows contributing content (bullet 2)
        - Fixtures/params: inline string

    On failure, first check:
        - That table row lines are recorded in table_lines
    """
    text = "# Data\n\n| a | b |\n| - | - |\n| 1 | 2 |\n"
    assert sections.check_text(text, "README.md") == ()


def test_inline_link_body_text_is_clean():
    """
    [Unit] detectors sections: verifies a link with text is sufficient content.

    Scenario:
        Given a leaf section whose only body is a Markdown link with visible text
        When DS106 recognition runs
        Then the link text counts as content and no finding is produced.

    Boundaries:
        - Focus: link text surviving the prose strip
        - Fixtures/params: inline string

    On failure, first check:
        - That the image/HTML strips do not remove ordinary link text
    """
    assert sections.check_text("# Links\n\n[the guide](guide.md)\n", "README.md") == ()


def test_html_tag_only_section_is_flagged():
    """
    [Unit] detectors sections: verifies a bare HTML tag renders no content.

    Scenario:
        Given a leaf section whose only body is an empty anchor/span tag
        When DS106 recognition runs
        Then the non-rendering tag is not content and one finding is produced.

    Boundaries:
        - Focus: HTML tag stripping so a bare tag is not prose (exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - The _HTML_TAG_RE substitution in _visible_text
    """
    findings = sections.check_text('# Anchor\n\n<a id="x"></a><span></span>\n', "README.md")
    assert len(findings) == 1
    assert findings[0].line == 1


def test_nested_empty_child_reports_leaf_only():
    """
    [Unit] detectors sections: verifies an empty nested child flags the leaf, not the parent.

    Scenario:
        Given an H2 parent whose only descendant is an empty H3 child
        When DS106 recognition runs under the default leaf policy
        Then only the H3 leaf is flagged.

    Boundaries:
        - Focus: leaf attribution when parents are skipped (bullets 3 and 4)
        - Fixtures/params: inline string

    On failure, first check:
        - That the H2 parent is excluded by the is-leaf test
        - That the H3 child's line is the one reported
    """
    findings = sections.check_text("## Parent\n\n### Child\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 3
    assert "Child" in findings[0].message


def test_multiple_empty_leaf_sections_are_sorted():
    """
    [Unit] detectors sections: verifies two empty leaves yield two findings in line order.

    Scenario:
        Given two consecutive terminal headings that both lack a body
        When DS106 recognition runs
        Then two findings are produced in ascending line order.

    Boundaries:
        - Focus: multiple findings and stable ordering (bullet 4)
        - Fixtures/params: inline string

    On failure, first check:
        - That _checked_indices yields ascending indices
        - That each sibling leaf is inspected independently
    """
    findings = sections.check_text("# First\n\n## Alpha\n\n## Beta\n", "README.md")
    assert [finding.line for finding in findings] == [3, 5]


def test_all_policy_flags_empty_parent_and_child():
    """
    [Unit] detectors sections: verifies the all policy inspects parents too.

    Scenario:
        Given an empty H2 parent whose only descendant is an empty H3 child
        When DS106 recognition runs with empty_section_policy set to all
        Then both the parent and the child are flagged.

    Boundaries:
        - Focus: empty_section_policy all branch in _checked_indices
        - Fixtures/params: Config(empty_section_policy="all")

    On failure, first check:
        - That the all branch returns every heading index
        - That the parent's direct body (between it and the child) is empty
    """
    findings = sections.check_text("## Parent\n\n### Child\n", "README.md", Config(empty_section_policy="all"))
    assert [finding.line for finding in findings] == [1, 3]


def test_off_policy_suppresses_all_findings():
    """
    [Unit] detectors sections: verifies the off policy disables the rule.

    Scenario:
        Given a document with an obviously empty terminal heading
        When DS106 recognition runs with empty_section_policy set to off
        Then no finding is produced.

    Boundaries:
        - Focus: the off gate so a disabled policy never masquerades as evaluated
        - Fixtures/params: Config(empty_section_policy="off")

    On failure, first check:
        - The early return for the off policy in check_text
    """
    assert sections.check_text("# Empty\n", "README.md", Config(empty_section_policy="off")) == ()


def test_document_without_headings_is_never_a_finding():
    """
    [Unit] detectors sections: verifies a heading-free document is not flagged.

    Scenario:
        Given prose and a blank document, neither containing a heading
        When DS106 recognition runs
        Then no finding is produced for either.

    Boundaries:
        - Focus: a document without headings has no empty section (bullet 5 / exclusions)
        - Fixtures/params: inline strings

    On failure, first check:
        - The no-headings early return in check_text
    """
    assert sections.check_text("Just a paragraph with no heading.\n", "README.md") == ()
    assert sections.check_text("", "README.md") == ()


def test_frontmatter_record_is_not_an_empty_section():
    """
    [Unit] detectors sections: verifies leading frontmatter is excluded from sections.

    Scenario:
        Given a YAML frontmatter record whose last key line precedes the closing '---'
            and then a real heading with a body
        When DS106 recognition runs
        Then the closing '---' is not read as a setext heading owning an empty body
            and no finding is produced.

    Boundaries:
        - Focus: frontmatter exclusion that prevents a spurious empty section (bullet 5)
        - Fixtures/params: inline string

    On failure, first check:
        - The _frontmatter_end_line boundary and the _active_headings exclusion
    """
    text = "---\ntitle: Doc\n---\n\n# Real\n\nBody text.\n"
    assert sections.check_text(text, "README.md") == ()


def test_heading_inside_comment_is_not_a_section():
    """
    [Unit] detectors sections: verifies a commented-out heading forms no section.

    Scenario:
        Given a real section with prose and a multi-line HTML comment containing a
            heading-looking '## Hidden' line
        When DS106 recognition runs
        Then the commented heading is excluded and no finding is produced.

    Boundaries:
        - Focus: comment-region heading exclusion matching DS105 (bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - That _active_headings drops headings whose start line is inside a comment
    """
    text = "# Real\n\nBody.\n\n<!--\n## Hidden\n-->\n"
    assert sections.check_text(text, "README.md") == ()


def test_setext_heading_section_is_evaluated_at_its_text_line():
    """
    [Unit] detectors sections: verifies setext heading spans are handled correctly.

    Scenario:
        Given an ATX section with a body followed by a trailing empty setext H1 at EOF
        When DS106 recognition runs
        Then the empty setext section is flagged at its text line, not its underline.

    Boundaries:
        - Focus: setext heading two-line spans at EOF (bullet 1 / semantics)
        - Fixtures/params: inline string

    On failure, first check:
        - That the setext heading span covers both the text and underline lines
        - That the finding line is the text line, and content would begin after the underline
    """
    findings = sections.check_text("# Intro\n\nBody text.\n\nAppendix\n========\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 5


def test_min_text_chars_threshold_flags_thin_sections():
    """
    [Unit] detectors sections: verifies a positive min-text-chars threshold is honored.

    Scenario:
        Given a leaf section whose body is a very short word under a threshold of ten
        When DS106 recognition runs with empty_section_min_text_chars set to ten
        Then the thin section is flagged, while the same text under the default is clean.

    Boundaries:
        - Focus: empty_section_min_text_chars accounting
        - Fixtures/params: Config(empty_section_min_text_chars=10)

    On failure, first check:
        - The text_chars comparison against the configured minimum in check_text
    """
    text = "# Section\n\nHi.\n"
    assert sections.check_text(text, "README.md") == ()
    findings = sections.check_text(text, "README.md", Config(empty_section_min_text_chars=10))
    assert len(findings) == 1


def test_crlf_and_cr_inputs_preserve_offending_line():
    """
    [Unit] detectors sections: verifies CRLF and lone-CR inputs keep the heading line.

    Scenario:
        Given the same empty-terminal-section document terminated with CRLF and with CR
        When DS106 recognition runs on each
        Then each reports the trailing heading at physical line 5.

    Boundaries:
        - Focus: CRLF and CR line numbering fidelity (semantics)
        - Fixtures/params: inline strings with \\r\\n and \\r terminators

    On failure, first check:
        - That split_physical_lines numbers CRLF and CR the same as the scanner
    """
    for terminator in ("\r\n", "\r"):
        text = f"# Intro{terminator}{terminator}Body.{terminator}{terminator}## Empty{terminator}"
        findings = sections.check_text(text, "README.md")
        assert len(findings) == 1
        assert findings[0].line == 5


def test_repeated_recognition_is_deterministic():
    """
    [Unit] detectors sections: verifies repeated scans produce identical findings.

    Scenario:
        Given the same Markdown text scanned twice
        When DS106 recognition runs on each pass
        Then the two finding tuples are equal and pinned to the expected lines.

    Boundaries:
        - Focus: determinism and absence of shared mutable state
        - Fixtures/params: inline string

    On failure, first check:
        - Any module-level mutable caches
        - Ordering stability of the section walk
    """
    text = "# A\n\n## Empty one\n\n## Empty two\n"
    first = sections.check_text(text, "README.md")
    assert first == sections.check_text(text, "README.md")
    assert [finding.line for finding in first] == [3, 5]


def test_detect_reads_documents_and_skips_non_markdown(tmp_path: Path):
    """
    [Unit] detectors sections: verifies detect reads .md files and ignores others.

    Scenario:
        Given a Markdown file with an empty terminal heading and a non-Markdown sibling
        When detect runs over both documents
        Then only the Markdown file contributes a single DS106 finding.

    Boundaries:
        - Focus: document reading, .md filtering, and path propagation in detect
        - Fixtures/params: tmp_path with two committed files

    On failure, first check:
        - The .md suffix filter in detect
        - That the finding path matches the Markdown document path
    """
    (tmp_path / "README.md").write_text("# Empty\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("# Empty\n", encoding="utf-8")
    documents = (models.Document("README.md", 1), models.Document("notes.txt", 1))
    findings = sections.detect(tmp_path, documents)
    assert len(findings) == 1
    assert findings[0].path == "README.md"


def test_detect_surfaces_invalid_utf8_rather_than_false_clean(tmp_path: Path):
    """
    [Unit] detectors sections: verifies invalid UTF-8 raises instead of passing silently.

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
        sections.detect(tmp_path, (models.Document("README.md", 1),))


def test_link_reference_definition_only_section_is_visible_content():
    """
    [Unit] detectors sections: pins the link-reference-definition-only section as content.

    Scenario:
        Given a leaf section whose only body is a link-reference definition
        When DS106 recognition runs
        Then the definition is treated as visible text and the section is NOT flagged.

    Boundaries:
        - Focus: current behaviour of a reference-definition-only body (no own-rule violation)
        - Fixtures/params: inline string

    On failure, first check:
        - Whether _visible_text began stripping reference-definition syntax
        - That the scanner does not mask a reference definition out of the body
    """
    # A reference definition renders invisibly in rendered Markdown, so flagging such a
    # section as contentless is a plausible future policy; DS106 deliberately does NOT
    # do that today and this test pins the current "counts as content" behaviour.
    findings = sections.check_text("# Title\n\n## References\n\n[link]: https://example.com\n", "README.md")
    assert findings == ()


def test_overlong_heading_text_is_bounded_in_message():
    """
    [Unit] detectors sections: verifies a pathologically long heading yields a bounded message.

    Scenario:
        Given an empty section whose heading text is 500k characters long
        When DS106 produces its finding
        Then the heading echo in the message is truncated to _MAX_HEADING_ECHO characters plus an
        ellipsis marker, so the diagnostic cannot grow unbounded with the input.

    Boundaries:
        - Focus: the finding-message echo is length-bounded while keeping the !r escaping
        - Fixtures/params: inline string

    On failure, first check:
        - The _MAX_HEADING_ECHO truncation in _finding
        - That short headings are still echoed in full (asserted elsewhere)
    """
    heading_text = "A" * 500_000
    # A single trailing heading with a 500k-character title and no body is the flagged section,
    # so the overlong text is exactly what the message would otherwise echo in full.
    findings = sections.check_text(f"## {heading_text}\n", "README.md")
    assert len(findings) == 1
    message = findings[0].message
    assert len(message) < 200
    assert "..." in message
    assert message.count("A") == sections._MAX_HEADING_ECHO
    assert message.startswith("empty section: 'AAA")
    assert message.endswith("has no visible content")


def test_linear_strippers_match_regex_oracle_per_line():
    """
    [Unit] detectors sections: verifies the linear strippers equal the old regex oracle per line.

    Scenario:
        Given a seeded-random corpus of a few thousand single lines mixing images, bracket/paren
        soup, single-line/unclosed/multiple HTML comments, real and malformed tags, entities and text
        When _visible_text runs over each line under both the ignore and count placeholder policies
        Then its output is byte-identical to the pre-refactor regex oracle, and the leading/trailing
        comment strippers also match their regex oracles.

    Boundaries:
        - Focus: byte-for-byte parity of the linear strippers with the original regex semantics
        - Fixtures/params: generated corpus; no filesystem

    On failure, first check:
        - A stripper boundary case (unclosed opener, closer before opener, overlap) that diverges
        - Whether the stripping order in _visible_text changed
    """
    empty_masks = sections._LineMasks()
    lines = _corpus_lines(4_000)
    assert len(lines) == 4_000

    for line in lines:
        for count_placeholders in (False, True):
            assert sections._visible_text(line, 1, empty_masks, count_placeholders) == _oracle_visible_text(
                line, 1, empty_masks, count_placeholders
            )
        assert sections._strip_leading_comment_open(line) == _ORACLE_COMMENT_OPEN.sub(" ", line)
        assert sections._strip_trailing_comment_close(line) == _ORACLE_COMMENT_CLOSE.sub(" ", line)


def test_linear_strippers_match_regex_oracle_for_ds106_findings(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors sections: verifies DS106 findings are identical to the regex-oracle detector.

    Scenario:
        Given a document whose section bodies are the seeded-random parity corpus
        When DS106 scans it once with the shipped linear strippers and once with _visible_text
            monkeypatched to the regex oracle
        Then the two finding tuples are identical, proving the refactor changed no observable outcome.

    Boundaries:
        - Focus: end-to-end finding parity isolated to _visible_text (scanner/masks are shared)
        - Fixtures/params: generated corpus; monkeypatch

    On failure, first check:
        - A stripper divergence surfaced only through the full section-content pass
        - Whether the oracle and shipped code see the same masks (they must)
    """
    lines = _corpus_lines(2_000, seed=777, max_tokens=8)
    body = "".join(f"## S{index}\n\n{line}\n\n" for index, line in enumerate(lines))
    document = "# Root\n\n" + body

    shipped = sections.check_text(document, "README.md", Config(profile="fast"))
    monkeypatch.setattr(sections, "_visible_text", _oracle_visible_text)
    oracle = sections.check_text(document, "README.md", Config(profile="fast"))

    assert shipped == oracle
    assert len(shipped) > 0  # the corpus must actually produce some empty sections
