"""Unit tests for the shared standard-library Markdown block scanner.

These tests use tiny inline source strings only; detector-level behavior over
committed assets is out of scope for this module.
"""

from pathlib import Path

import pytest

from docsentinel import markdown_blocks as mb


def test_crlf_line_numbers_and_offsets():
    """
    [Unit] markdown blocks: CRLF terminators keep one-based lines and char offsets.

    Scenario:
        Given Markdown separated by CRLF terminators
        When the scanner tokenizes it
        Then heading lines and character offsets stay correct.

    Boundaries:
        - Focus: CRLF line numbering and offsets
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The line splitter's handling of CRLF
        - Reported span offsets against the source text
    """
    text = "# One\r\n\r\n## Two\r\n"
    index = mb.scan_markdown(text, "README.md")

    assert [h.span.start_line for h in index.headings] == [1, 3]
    first = index.headings[0]
    assert text[first.span.start_offset : first.span.end_offset] == "# One"


def test_missing_final_newline_has_no_phantom_line():
    """
    [Unit] markdown blocks: a missing final newline does not add a trailing line.

    Scenario:
        Given text whose last line has no terminator
        When the scanner splits lines
        Then no phantom empty line is created.

    Boundaries:
        - Focus: final-newline-absent line counting
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The _iter_lines final-chunk emission
        - Line numbers near end of file
    """
    index = mb.scan_markdown("line one\nline two", "README.md")

    assert index.headings == ()
    assert mb._iter_lines("a\nb")[-1][0] == 2


def test_empty_input_yields_empty_index():
    """
    [Unit] markdown blocks: empty input produces an empty index with the path.

    Scenario:
        Given an empty document body
        When the scanner runs
        Then the index is empty but retains the path.

    Boundaries:
        - Focus: empty-input handling
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The empty-text branch of _iter_lines
        - Default empty token tuples on the index
    """
    index = mb.scan_markdown("", "docs/empty.md")

    assert index.path == "docs/empty.md"
    assert index.headings == ()
    assert index.fences == ()


def test_repeated_headings_get_duplicate_suffix():
    """
    [Unit] markdown blocks: duplicate headings gain DS101-style numeric suffixes.

    Scenario:
        Given three identical headings
        When the scanner slugs them
        Then the later slugs gain -1 and -2 suffixes.

    Boundaries:
        - Focus: duplicate-anchor suffix behavior
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The _slug_with_suffix counter logic
        - base_slug versus slug fields
    """
    index = mb.scan_markdown("# Setup\n# Setup\n# Setup\n", "README.md")

    assert [h.slug for h in index.headings] == ["setup", "setup-1", "setup-2"]
    assert [h.base_slug for h in index.headings] == ["setup", "setup", "setup"]


def test_empty_atx_heading_yields_empty_base_slug():
    """
    [Unit] markdown blocks: an empty ATX heading produces an empty base slug.

    Scenario:
        Given two ATX headings with a marker but no heading text ('# ' and '## ')
        When the scanner slugs them
        Then both carry an empty base slug, so the empty text owns no real anchor.

    Boundaries:
        - Focus: empty-heading slugging (Story 01.0 review follow-up)
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - That slugify("") stays empty rather than inventing a name
        - base_slug versus the duplicate-suffixed slug for empty-text headings

    This locks the scanner side of the Story 01.0 review item: an empty heading
    must not seed a usable anchor. DS104 relies on the empty base_slug to exclude
    such headings from the generated anchor namespace (see the DS104 unit suite),
    so neither the empty slug nor its suffixed sibling becomes a bogus anchor.
    """
    index = mb.scan_markdown("# \n## \n", "README.md")

    assert [h.text for h in index.headings] == ["", ""]
    assert [h.base_slug for h in index.headings] == ["", ""]
    # The second empty heading still receives the duplicate suffix, but because
    # its base slug is empty it carries no meaningful anchor identity.
    assert [h.slug for h in index.headings] == ["", "-1"]


def test_setext_headings_detected_with_levels():
    """
    [Unit] markdown blocks: setext underlines promote the preceding paragraph line.

    Scenario:
        Given paragraph lines underlined by = and -
        When the scanner runs
        Then level 1 and level 2 setext headings are emitted.

    Boundaries:
        - Focus: setext heading detection and levels
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The previous-paragraph tracking in scan_markdown
        - Level assignment for = versus -
    """
    index = mb.scan_markdown("Title\n=====\n\nSub\n---\n", "README.md")

    assert [(h.text, h.level, h.style) for h in index.headings] == [
        ("Title", 1, "setext"),
        ("Sub", 2, "setext"),
    ]


def test_lone_dash_rule_is_not_a_setext_heading():
    """
    [Unit] markdown blocks: a dash rule with no preceding paragraph is not a heading.

    Scenario:
        Given a dash rule after a blank line
        When the scanner runs
        Then no heading is produced.

    Boundaries:
        - Focus: setext false-positive guard
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The blank-line reset of previous_paragraph
        - The setext branch guard
    """
    index = mb.scan_markdown("\n---\n", "README.md")

    assert index.headings == ()


def test_mixed_backtick_and_tilde_fences_close_independently():
    """
    [Unit] markdown blocks: tilde and backtick fences only close on their own marker.

    Scenario:
        Given adjacent backtick and tilde fenced blocks
        When the scanner runs
        Then each fence closes only on its own marker character.

    Boundaries:
        - Focus: mixed fence marker handling
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The marker and length comparison in _scan_fences
        - Info-string capture on the opener
    """
    text = "```py\n~~~ not a closer\n```\n\n~~~\nbody\n~~~\n"
    index = mb.scan_markdown(text, "README.md")

    assert [(f.marker, f.closed) for f in index.fences] == [("`", True), ("~", True)]
    assert index.fences[0].info_string == "py"


def test_unclosed_fence_is_conservative_and_swallows_body():
    """
    [Unit] markdown blocks: an unclosed fence is malformed and masks headings below it.

    Scenario:
        Given a fence opener with no closer
        When the scanner runs
        Then the fence is malformed and inner headings are not emitted.

    Boundaries:
        - Focus: conservative malformed fence handling
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The end-of-file unclosed branch in _scan_fences
        - The fenced-line masking of heading detection
    """
    text = "```\n# not a heading\nmore\n"
    index = mb.scan_markdown(text, "README.md")

    assert index.headings == ()
    (fence,) = index.fences
    assert fence.closed is False
    assert fence.closer_line is None
    assert "unclosed fence" in fence.reason


def test_closing_candidate_with_info_string_is_not_a_closer():
    """
    [Unit] markdown blocks: a closing fence carrying an info string is rejected.

    Scenario:
        Given a candidate closer that has trailing text
        When the scanner runs
        Then the fence is treated as unclosed.

    Boundaries:
        - Focus: info-string versus delimiter distinction
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The closer info-string emptiness check
        - closed flag on the resulting fence
    """
    text = "```\ncode\n``` trailing\n"
    index = mb.scan_markdown(text, "README.md")

    (fence,) = index.fences
    assert fence.closed is False


def test_long_unmatched_backtick_run_is_ignored():
    """
    [Unit] markdown blocks: a long unterminated backtick run yields no inline code.

    Scenario:
        Given a very long run of backticks with no closer
        When the scanner scans inline code
        Then no inline code span is produced and it stays linear.

    Boundaries:
        - Focus: adversarial unmatched inline backticks
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The _find_inline_code unmatched-run advance
        - Absence of catastrophic backtracking
    """
    index = mb.scan_markdown("`" * 5000 + "no close\n", "README.md")

    assert index.inline_code == ()


def test_inline_code_matches_equal_length_runs():
    """
    [Unit] markdown blocks: inline code closes on a run equal to its opener.

    Scenario:
        Given single and double backtick spans with nested backticks
        When the scanner runs
        Then each span closes on an equal-length run.

    Boundaries:
        - Focus: variable-length inline code runs
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The run-length matching in _find_inline_code
        - Captured inner text
    """
    index = mb.scan_markdown("a `one` and ``two `nested` two`` end\n", "README.md")

    spans = [(c.text, c.backticks) for c in index.inline_code]
    assert ("one", 1) in spans
    assert ("two `nested` two", 2) in spans


def test_fenced_code_masks_comments_and_inline():
    """
    [Unit] markdown blocks: fenced content is not scanned for comments or inline code.

    Scenario:
        Given a comment and inline code inside a fence
        When the scanner runs
        Then only the comment outside the fence is reported.

    Boundaries:
        - Focus: fence masking of comments and inline code
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The fenced-line blanking in _scan_comments
        - The fenced-line skip in the main scan loop
    """
    text = "```\n<!-- hidden -->\n`code`\n```\n\n<!-- real -->\n"
    index = mb.scan_markdown(text, "README.md")

    assert index.inline_code == ()
    assert [(c.text, c.closed) for c in index.comments] == [("<!-- real -->", True)]


def test_multiline_comment_span_covers_both_lines():
    """
    [Unit] markdown blocks: a multi-line HTML comment spans start to end line.

    Scenario:
        Given an HTML comment across two lines
        When the scanner runs
        Then the span covers both lines.

    Boundaries:
        - Focus: multi-line comment spans
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The offset-to-line mapping in _scan_comments
        - The comment open/close offsets
    """
    index = mb.scan_markdown("intro\n<!-- a\nb -->\ntail\n", "README.md")

    (comment,) = index.comments
    assert comment.closed is True
    assert comment.span.start_line == 2
    assert comment.span.end_line == 3


def test_unclosed_comment_runs_to_end_of_file():
    """
    [Unit] markdown blocks: an HTML comment with no closer is reported as unclosed.

    Scenario:
        Given a comment opener with no closer
        When the scanner runs
        Then an unclosed comment spanning to end of file is reported.

    Boundaries:
        - Focus: unclosed comment handling
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The no-closer branch in _scan_comments
        - The closed flag on the comment
    """
    index = mb.scan_markdown("text\n<!-- dangling\n", "README.md")

    (comment,) = index.comments
    assert comment.closed is False
    assert comment.span.start_line == 2


def test_escaped_pipe_does_not_split_table_cell():
    """
    [Unit] markdown blocks: an escaped pipe stays inside a single table cell.

    Scenario:
        Given a table body cell with an escaped pipe
        When the scanner splits cells
        Then the escaped pipe is not a column separator.

    Boundaries:
        - Focus: escaped delimiter handling in tables
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The backslash handling in _split_table_cells
        - Cell boundaries of the body row
    """
    text = "| a | b |\n| --- | --- |\n| x \\| y | z |\n"
    index = mb.scan_markdown(text, "README.md")

    body = [row for row in index.table_rows if not row.is_delimiter][-1]
    assert body.cells == ("x \\| y", "z")


def test_table_header_delimiter_and_body_rows_detected():
    """
    [Unit] markdown blocks: a header, delimiter, and body rows are all emitted.

    Scenario:
        Given a pipe table with a header and two body rows
        When the scanner runs
        Then header, delimiter, and body rows are all produced.

    Boundaries:
        - Focus: table row enumeration
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The header-plus-delimiter detection in _scan_tables
        - The body-row continuation loop
    """
    text = "| h1 | h2 |\n|----|----|\n| 1 | 2 |\n| 3 | 4 |\n"
    index = mb.scan_markdown(text, "README.md")

    kinds = [(row.is_delimiter, row.cells) for row in index.table_rows]
    assert kinds == [
        (False, ("h1", "h2")),
        (True, ("----", "----")),
        (False, ("1", "2")),
        (False, ("3", "4")),
    ]


def test_markdown_and_html_images_captured():
    """
    [Unit] markdown blocks: Markdown images and HTML img/source tags are captured.

    Scenario:
        Given a Markdown image and HTML img and source tags
        When the scanner runs
        Then each image source is captured with its origin flag.

    Boundaries:
        - Focus: image token extraction
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The _HTML_IMG_RE and _LINK_RE handling
        - The html flag on image tokens
    """
    text = '![alt](pic.png)\n<img src="a.svg">\n<source src="b.webm">\n'
    index = mb.scan_markdown(text, "README.md")

    targets = {(img.raw_target, img.html) for img in index.images}
    assert ("pic.png", False) in targets
    assert ("a.svg", True) in targets
    assert ("b.webm", True) in targets


def test_reference_definitions_and_uses_normalize_labels():
    """
    [Unit] markdown blocks: reference labels are normalized for definitions and uses.

    Scenario:
        Given a reference definition and two uses with varied casing and spacing
        When the scanner runs
        Then all labels normalize to the same form.

    Boundaries:
        - Focus: reference label normalization
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - normalize_label whitespace and case folding
        - Collapsed versus full reference-use parsing
    """
    text = "[My  Ref]: target.md\n\nsee [text][my ref] and [My  Ref][]\n"
    index = mb.scan_markdown(text, "README.md")

    (definition,) = index.reference_definitions
    assert definition.label == "my ref"
    assert definition.target == "target.md"
    assert {use.label for use in index.reference_uses} == {"my ref"}


def test_unicode_normalization_matches_equivalent_labels():
    """
    [Unit] markdown blocks: NFC and NFD label forms normalize to the same label.

    Scenario:
        Given the same label in precomposed and decomposed Unicode forms
        When normalize_label runs
        Then both yield an identical normalized label.

    Boundaries:
        - Focus: Unicode normalization of labels
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The NFC normalization in normalize_label
        - Case folding of the result
    """
    nfc = "Café"
    nfd = "Cafe\u0301"

    assert nfc != nfd
    assert mb.normalize_label(nfc) == mb.normalize_label(nfd)


def test_html_anchor_names_join_heading_slugs():
    """
    [Unit] markdown blocks: anchor_names merges heading slugs and HTML anchors.

    Scenario:
        Given a heading plus explicit HTML id and name anchors
        When anchor_names is called
        Then the set contains the slug and both HTML anchors.

    Boundaries:
        - Focus: resolvable anchor set
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The _HTML_ANCHOR_RE extraction
        - The anchor_names union logic
    """
    text = '# Title\n\n<a id="manual-anchor"></a>\n<a name="other"></a>\n'
    index = mb.scan_markdown(text, "README.md")

    assert index.anchor_names() == frozenset({"title", "manual-anchor", "other"})


def test_explicit_anchor_tokens_record_kind_value_and_line():
    """
    [Unit] markdown blocks: explicit_anchors carry attribute kind, spelling, and line.

    Scenario:
        Given an id anchor, a name anchor in single quotes, and a CRLF-separated name
        When the scanner tokenizes the document
        Then each HtmlAnchor records its attribute kind, raw value, one-based line,
            and a span whose source slice contains the opener and attribute.

    Boundaries:
        - Focus: HtmlAnchor token shape across quote styles and CRLF
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - _find_html_anchor_attributes kind/value capture and offsets
        - The one-based line recorded on each HtmlAnchor
    """
    text = '# Title\n\n<a id="First"></a>\n<a name=\'second\'></a>\r\n  <a name="Third"></a>\n'
    index = mb.scan_markdown(text, "README.md")

    anchors = index.explicit_anchors
    assert [(a.attribute, a.value, a.line) for a in anchors] == [
        ("id", "First", 3),
        ("name", "second", 4),
        ("name", "Third", 5),
    ]
    first = anchors[0]
    assert text[first.span.start_offset : first.span.end_offset].startswith("<a ")
    assert "First" in text[first.span.start_offset : first.span.end_offset]


def test_explicit_anchors_exclude_masked_regions_but_html_anchors_do_not():
    """
    [Unit] markdown blocks: explicit_anchors mask code/comment regions; html_anchors do not.

    Scenario:
        Given anchor-shaped text in a code fence, inline code, and an HTML comment,
            plus one genuine anchor
        When the scanner tokenizes the document
        Then explicit_anchors holds only the genuine anchor while html_anchors keeps
            the inline-code and comment anchors for DS101 backward compatibility.

    Boundaries:
        - Focus: comment/inline-code masking for the new token versus legacy strings
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - _mask_line blanking of inline-code and comment columns
        - That html_anchors extraction still runs on raw non-fenced content
    """
    text = (
        '<a name="real"></a>\n'
        "```html\n"
        '<a name="fenced"></a>\n'
        "```\n"
        'Inline `<a name="incode">` text.\n'
        '<!-- <a name="comment"> -->\n'
    )
    index = mb.scan_markdown(text, "README.md")

    assert [a.value for a in index.explicit_anchors] == ["real"]
    # The fenced anchor is masked for both; inline-code and comment anchors remain
    # in the legacy html_anchors list so DS101's resolvable set is unchanged.
    assert index.html_anchors == ("real", "incode", "comment")


def test_entity_encoded_anchor_id_is_stored_verbatim():
    """
    [Unit] markdown blocks: an entity-encoded id is stored byte-for-byte, not decoded.

    Scenario:
        Given an explicit anchor id written as ``sec&amp;tion``
        When the scanner tokenizes it
        Then both the explicit-anchor token and the legacy html_anchors string keep the
            literal ``sec&amp;tion`` spelling without HTML-entity decoding.

    Boundaries:
        - Focus: verbatim anchor spelling (no entity normalization)
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - That the anchor extractor never unescapes HTML entities
        - That explicit_anchors and html_anchors agree on the raw value
    """
    index = mb.scan_markdown('<a id="sec&amp;tion"></a>\n', "README.md")

    assert [a.value for a in index.explicit_anchors] == ["sec&amp;tion"]
    assert index.html_anchors == ("sec&amp;tion",)


def test_anchor_id_containing_gt_is_captured_consistently():
    """
    [Unit] markdown blocks: an id value containing ``>`` is captured like html_anchors.

    Scenario:
        Given an explicit anchor id whose quoted value begins with ``>`` (``<a id=">foo">``)
        When the scanner tokenizes it
        Then the ``>`` inside the quotes is part of the value and the explicit-anchor token
            matches the legacy html_anchors string exactly.

    Boundaries:
        - Focus: the ``>`` boundary cursor does not truncate a quoted value containing ``>``
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - That the attribute match (not the first ``>``) determines the captured value
        - That explicit_anchors and html_anchors stay consistent on this shape
    """
    index = mb.scan_markdown('<a id=">foo"></a>\n', "README.md")

    assert [a.value for a in index.explicit_anchors] == [">foo"]
    assert index.html_anchors == (">foo",)


def test_local_reference_splits_fragment():
    """
    [Unit] markdown blocks: a link target splits into path component and fragment.

    Scenario:
        Given a link with a path and a fragment
        When the scanner runs
        Then path component and fragment are separated.

    Boundaries:
        - Focus: local reference fragment splitting
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The partition on '#' in the scan loop
        - The category assignment for links
    """
    index = mb.scan_markdown("see [x](guide.md#section)\n", "README.md")

    (reference,) = index.local_references
    assert reference.path_component == "guide.md"
    assert reference.fragment == "section"
    assert reference.category == "ordinary"


def test_tokens_are_immutable():
    """
    [Unit] markdown blocks: emitted tokens are frozen dataclasses.

    Scenario:
        Given a scanned heading token
        When an attribute assignment is attempted
        Then a FrozenInstanceError (AttributeError) is raised.

    Boundaries:
        - Focus: token immutability
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The frozen=True dataclass declarations
        - That no token exposes mutable state
    """
    index = mb.scan_markdown("# Title\n", "README.md")

    with pytest.raises(AttributeError):
        index.headings[0].level = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("raw_target", "status"),
    (
        ("guide.md", mb.ReferenceStatus.RESOLVED),
        ("missing.md", mb.ReferenceStatus.RESOLVED),
        ("#anchor", mb.ReferenceStatus.RESOLVED),
        ("http://example.invalid/x", mb.ReferenceStatus.EXTERNAL),
        ("//cdn.example/x", mb.ReferenceStatus.EXTERNAL),
        ("mailto:nobody@example.invalid", mb.ReferenceStatus.EXTERNAL),
        ("../../escape.md", mb.ReferenceStatus.OUTSIDE_ROOT),
        ("{NN}-{slug}.md", mb.ReferenceStatus.UNSUPPORTED),
        ("docs/*.md", mb.ReferenceStatus.UNSUPPORTED),
        ("C:\\win.md", mb.ReferenceStatus.UNSUPPORTED),
        ("\\\\server\\share\\x.md", mb.ReferenceStatus.UNSUPPORTED),
    ),
)
def test_resolve_local_reference_status(raw_target: str, status: mb.ReferenceStatus):
    """
    [Unit] markdown blocks: reference resolution tags each target class correctly.

    Scenario:
        Given a variety of link targets
        When resolve_local_reference runs lexically
        Then each target is tagged with the expected status.

    Boundaries:
        - Focus: reference resolution status classification
        - Fixtures/params: raw_target, status (parametrized, 11 cases)
        - Scope: this test case only

    On failure, first check:
        - The ordering of scheme, Windows, glob, and escape checks
        - The lexical normalization of relative paths
    """
    result = mb.resolve_local_reference(Path("/root"), "docs/guide.md", raw_target)

    assert result.status is status


def test_resolve_readme_subdirectory_uses_document_directory():
    """
    [Unit] markdown blocks: a link in a subdirectory README resolves against its folder.

    Scenario:
        Given a README under docs linking to ../top.md
        When resolve_local_reference runs
        Then the path resolves to top.md at the root.

    Boundaries:
        - Focus: README subdirectory resolution
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The document-directory join in the resolver
        - The _normalize_relative dot-dot handling
    """
    result = mb.resolve_local_reference(Path("/root"), "docs/README.md", "../top.md")

    assert result.status is mb.ReferenceStatus.RESOLVED
    assert result.path == Path("/root/top.md")


def test_resolve_leading_slash_uses_root():
    """
    [Unit] markdown blocks: a root-relative link resolves against the scan root.

    Scenario:
        Given a leading-slash link target
        When resolve_local_reference runs
        Then the path resolves relative to the root.

    Boundaries:
        - Focus: root-relative resolution
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The leading-slash branch in the resolver
        - The joined root path
    """
    result = mb.resolve_local_reference(Path("/root"), "docs/README.md", "/guide/x.md")

    assert result.status is mb.ReferenceStatus.RESOLVED
    assert result.path == Path("/root/guide/x.md")


@pytest.mark.parametrize(
    ("raw_target", "status"),
    (
        ("C%3A%5Cwin.md", mb.ReferenceStatus.UNSUPPORTED),
        ("%5c%5cserver%5cshare%5cx.md", mb.ReferenceStatus.UNSUPPORTED),
        ("%2f%2fcdn.example/x", mb.ReferenceStatus.EXTERNAL),
        ("bad%00name.md", mb.ReferenceStatus.UNSUPPORTED),
        ("..%2f..%2fescape.md", mb.ReferenceStatus.OUTSIDE_ROOT),
        ("%2e%2e/%2e%2e/escape.md", mb.ReferenceStatus.OUTSIDE_ROOT),
        ("%252e%252e/x.md", mb.ReferenceStatus.RESOLVED),
    ),
)
def test_resolve_local_reference_decoded_classification(raw_target: str, status: mb.ReferenceStatus):
    """
    [Unit] markdown blocks: encoded targets classify identically to their literal forms.

    Scenario:
        Given percent-encoded Windows, UNC, protocol-relative, control-char,
            traversal, and double-encoded targets
        When resolve_local_reference runs lexically
        Then each decodes exactly once before every guard and is tagged as the
            matching literal form would be.

    Boundaries:
        - Focus: single up-front decode feeding all classification guards
        - Fixtures/params: raw_target, status (parametrized, 7 cases)
        - Scope: this test case only

    On failure, first check:
        - The single unquote and guard ordering in the resolver
        - That double-encoded %25 sequences are not decoded twice
    """
    result = mb.resolve_local_reference(Path("/root"), "docs/guide.md", raw_target)

    assert result.status is status


def test_resolve_percent_encoded_path_is_decoded():
    """
    [Unit] markdown blocks: percent-encoded path segments decode before resolution.

    Scenario:
        Given a link target with a percent-encoded space
        When resolve_local_reference runs
        Then the decoded path is resolved.

    Boundaries:
        - Focus: percent-encoding decode
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The unquote call in the resolver
        - The resulting path segments
    """
    result = mb.resolve_local_reference(Path("/root"), "README.md", "my%20doc.md")

    assert result.status is mb.ReferenceStatus.RESOLVED
    assert result.path == Path("/root/my doc.md")


def _reference_masked_lines(text: str) -> list[str]:
    """Mask every non-fenced line the pre-fix O(lines x comments) way.

    This replays the old :func:`_mask_line` behavior (iterate *all* comment
    ranges per line with per-char min/max blanking) so the optimized moving-cursor
    implementation can be pinned byte-for-byte against it.
    """
    lines = mb._iter_lines(text)
    _fences, fenced = mb._scan_fences("p.md", lines)
    comments = mb._scan_comments("p.md", text, lines, fenced)
    comment_ranges = [(c.span.start_offset, c.span.end_offset) for c in comments]
    out: list[str] = []
    for index, (_ln, content, start, _end) in enumerate(lines):
        if fenced[index]:
            continue
        chars = list(content)
        for span_start, span_end, _bt, _inner in mb._find_inline_code(content):
            for pos in range(span_start, span_end):
                chars[pos] = " "
        length = len(content)
        for range_start, range_end in comment_ranges:
            low = max(range_start, start) - start
            high = min(range_end, start + length) - start
            for pos in range(low, high):
                chars[pos] = " "
        out.append("".join(chars))
    return out


def _new_masked_lines(text: str) -> list[str]:
    """Mask every non-fenced line via the shipped moving-cursor :func:`_mask_line`."""
    lines = mb._iter_lines(text)
    _fences, fenced = mb._scan_fences("p.md", lines)
    comments = mb._scan_comments("p.md", text, lines, fenced)
    comment_ranges = [(c.span.start_offset, c.span.end_offset) for c in comments]
    out: list[str] = []
    cursor = 0
    for index, (_ln, content, start, _end) in enumerate(lines):
        if fenced[index]:
            continue
        masked, cursor = mb._mask_line(content, start, mb._find_inline_code(content), comment_ranges, cursor)
        out.append(masked)
    return out


@pytest.mark.parametrize(
    "text",
    (
        "no comments or code here\nplain second line\n",
        "<!--\nspanning\nmany\nlines\n-->\nafter\n",
        "text before <!-- opens here\nand closes --> after on line two\n",
        "<!-- never closed to end of file\nmore swallowed text\nand more\n",
        "`<!-- comment in inline code -->` and `<a name=x>` here\n",
        'before <a name="a"></a> <!-- c --> <a id="b"></a> after\n',
        'line one\r\n<!-- crlf\r\ncomment -->\r\n<a id="x"></a>\r\n',
        "```\n<!-- fenced comment, never scanned -->\n```\nvisible <!-- c --> tail\n",
        "<!-- a --><!-- b --> both adjacent on one line <!-- c -->\n",
    ),
    ids=(
        "no_masking",
        "multiline_comment",
        "comment_opens_midline",
        "unterminated_to_eof",
        "comment_in_inline_code",
        "comment_adjacent_to_anchors",
        "crlf_multiline_comment",
        "fenced_comment_then_visible",
        "many_single_line_comments",
    ),
)
def test_mask_line_is_byte_identical_to_the_reference(text: str):
    """
    [Unit] markdown blocks: the moving-cursor mask matches the old per-line reference.

    Scenario:
        Given varied inputs (multi-line comments, a comment opening mid-line and
            closing later, an unterminated comment to EOF, comments inside inline
            code, comments adjacent to anchors, CRLF, fenced comments, many adjacent
            comments)
        When each non-fenced line is masked by the shipped cursor implementation and
            by the pre-fix reference that rescans every comment per line
        Then the two produce byte-identical masked lines.

    Boundaries:
        - Focus: parity of the O(lines + overlap) masker against the O(lines x comments) one
        - Fixtures/params: parametrized over masking-relevant shapes
        - Scope: this test case only

    On failure, first check:
        - The moving-cursor advance condition (``end <= line_start``) in _mask_line
        - The overlap clamping (``low``/``high``) and slice-assignment blanking
    """
    assert _new_masked_lines(text) == _reference_masked_lines(text)
