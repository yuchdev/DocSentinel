"""Unit tests for the shared scanner's CommonMark-correct HTML-comment masking.

These pin the security fix for the comment-masking evasion hole (DS116 threat
model, standing requirement 16): the scanner must mask a ``<!--`` only where a
CommonMark renderer also hides it. A line-start opener (<=3 spaces of indent)
begins an HTML-block comment running to the first ``-->`` or end of file; a
mid-line opener is a comment only when a ``-->`` closes it within the same
paragraph; an opener inside an inline code span is literal and masks nothing.

The functional cases assert exactly which ``<!--``/``-->`` ranges stay masked
(``index.comments``) and the edge forms. The timing cases drive doubling series
through :func:`tests.timing_helpers.assert_scales_linearly` to prove the precompute
+ bisect scan stays linear - a paragraph of many unclosed openers was the exact
quadratic trap behind five earlier regressions.

Documented scanner limitations (not handled here; listed for the security review):
raw HTML blocks (``<div>``/``<pre>``/``<script>``/``<style>``), ``<![CDATA[``,
processing instructions, four-space indented code blocks, and multi-line code
spans. The scanner recognises single-line code spans only, so a ``<!--`` inside a
genuine multi-line code span is still masked; that is a pre-existing, broader
limitation unchanged by this fix.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from docsentinel import markdown_blocks as mb
from tests.timing_helpers import assert_scales_linearly


def _comment_texts(text: str) -> tuple[tuple[str, bool], ...]:
    """Return each scanned comment's ``(raw_text, closed)`` for a document.

    :param text: The Markdown source to scan.
    :returns: The ``(text, closed)`` pair of every comment in source order.
    """
    index = mb.scan_markdown(text, "README.md")
    return tuple((comment.text, comment.closed) for comment in index.comments)


def test_closed_single_line_mid_line_comment_is_masked():
    """
    [Unit] markdown blocks comment masking: verifies a closed mid-line comment is masked.

    Scenario:
        Given a mid-line comment that opens and closes on one line within a paragraph
        When the scanner runs
        Then exactly that ``<!-- c -->`` range is reported as a closed comment.

    Boundaries:
        - Focus: a well-formed inline comment is still masked (no regression)
        - Fixtures/params: none

    On failure, first check:
        - Whether the mid-line paragraph-bound closer search found the same-line closer
    """
    assert _comment_texts("a <!-- c --> b\n") == (("<!-- c -->", True),)


def test_line_start_unclosed_comment_runs_to_end_of_file():
    """
    [Unit] markdown blocks comment masking: verifies a line-start unclosed opener masks to EOF.

    Scenario:
        Given a line-start ``<!--`` with no closer anywhere after it
        When the scanner runs
        Then it reports one unclosed comment running to end of file, the historical HTML-block behaviour.

    Boundaries:
        - Focus: the preserved HTML-block end condition (first closer or EOF)
        - Fixtures/params: none

    On failure, first check:
        - The is_block branch and its unclosed-to-EOF comment
    """
    comments = _comment_texts("intro\n<!-- dangling\ntail\n")
    assert comments == (("<!-- dangling\ntail\n", False),)


def test_mid_line_unclosed_opener_masks_nothing():
    """
    [Unit] markdown blocks comment masking: verifies a mid-line unclosed opener is literal text.

    Scenario:
        Given a mid-line ``<!--`` with no closer in its paragraph
        When the scanner runs
        Then no comment is reported - the literal opener masks nothing, closing the evasion hole where
        it used to run to end of document.

    Boundaries:
        - Focus: the core fix - a mid-line unclosed opener is not a comment
        - Fixtures/params: none

    On failure, first check:
        - The paragraph-bound closer search and the ``continue`` on no closer
    """
    assert _comment_texts("a <!-- dangling\ntail\n") == ()


def test_opener_inside_inline_code_span_masks_nothing():
    """
    [Unit] markdown blocks comment masking: verifies an opener inside an inline code span is literal.

    Scenario:
        Given a ``<!--`` inside an inline code span
        When the scanner runs
        Then no comment is reported, because the code span is blanked before openers are sought.

    Boundaries:
        - Focus: inline-code masking precedes opener detection (CommonMark: a code span is literal)
        - Fixtures/params: none

    On failure, first check:
        - _comment_mask blanking of inline-code columns before the opener scan
    """
    assert _comment_texts("see `<!--` here\n") == ()


def test_code_span_opener_beside_a_real_closed_comment_on_the_same_line():
    """
    [Unit] markdown blocks comment masking: verifies a code-span opener does not shadow a real comment.

    Scenario:
        Given one line carrying a code-span ``<!--`` and, after it, a real closed ``<!-- real -->``
        When the scanner runs
        Then only the real closed comment is masked; the code-span opener masks nothing.

    Boundaries:
        - Focus: masking distinguishes a literal code-span opener from a genuine comment on one line
        - Fixtures/params: none

    On failure, first check:
        - Whether the code-span blanking wrongly consumed the real comment or vice versa
    """
    assert _comment_texts("`<!--` and <!-- real -->\n") == (("<!-- real -->", True),)


def test_mid_line_comment_spanning_lines_within_a_paragraph_is_masked():
    """
    [Unit] markdown blocks comment masking: verifies a paragraph-internal multi-line comment is masked.

    Scenario:
        Given a mid-line ``<!--`` whose ``-->`` appears a line later with no blank line between
        When the scanner runs
        Then the whole ``<!-- open\\nclose -->`` range is reported as one closed comment.

    Boundaries:
        - Focus: a mid-line comment may span lines while it stays inside the paragraph
        - Fixtures/params: none

    On failure, first check:
        - The paragraph boundary (next blank line) used as the closer-search bound
    """
    comments = _comment_texts("a <!-- open\nclose --> b\ntail\n")
    assert comments == (("<!-- open\nclose -->", True),)


def test_mid_line_opener_whose_closer_is_after_a_blank_line_is_not_a_comment():
    """
    [Unit] markdown blocks comment masking: verifies a closer beyond the paragraph does not close a comment.

    Scenario:
        Given a mid-line ``<!--`` whose only ``-->`` sits after a blank line (a new paragraph)
        When the scanner runs
        Then no comment is reported - the closer is out of the opener's paragraph, so the opener is literal.

    Boundaries:
        - Focus: the paragraph bound excludes a closer in a later paragraph
        - Fixtures/params: none

    On failure, first check:
        - The blank-line bisect that bounds the mid-line closer search
    """
    assert _comment_texts("a <!-- open\n\nclose -->\n") == ()


def test_indentation_zero_to_three_spaces_is_a_block_opener_but_four_is_not():
    """
    [Unit] markdown blocks comment masking: verifies the <=3 space indent boundary for block openers.

    Scenario:
        Given a ``<!--`` indented by three spaces and the same opener indented by four spaces, each unclosed
        When the scanner runs over each
        Then the three-space opener is a block comment running to EOF while the four-space opener is treated
        as mid-line and, lacking a paragraph closer, masks nothing.

    Boundaries:
        - Focus: the up-to-three-spaces HTML-block indentation rule
        - Fixtures/params: none

    On failure, first check:
        - The prefix-length check selecting the is_block branch
    """
    assert _comment_texts("   <!-- x\nbody\n") == (("<!-- x\nbody\n", False),)
    assert _comment_texts("    <!-- x\nbody\n") == ()


def test_adjacent_closed_comments_are_each_masked():
    """
    [Unit] markdown blocks comment masking: verifies adjacent comments are reported separately.

    Scenario:
        Given two adjacent closed comments on one line
        When the scanner runs
        Then both are reported, each covering its own range, with no overlap.

    Boundaries:
        - Focus: the consumed-until cursor advances past one comment before the next opener
        - Fixtures/params: none

    On failure, first check:
        - The consumed_until bookkeeping between adjacent comments
    """
    assert _comment_texts("<!-- a --><!-- b -->\n") == (("<!-- a -->", True), ("<!-- b -->", True))


def test_comment_inside_link_text_is_masked():
    """
    [Unit] markdown blocks comment masking: verifies a comment embedded in link text is masked.

    Scenario:
        Given a closed comment inside a link's text span
        When the scanner runs
        Then the comment range is reported as masked.

    Boundaries:
        - Focus: comment detection is independent of surrounding link syntax
        - Fixtures/params: none

    On failure, first check:
        - Whether link scanning interfered with the comment range
    """
    assert _comment_texts("[a <!-- x --> b](u)\n") == (("<!-- x -->", True),)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("<!-->\n", (("<!-->\n", False),)),
        ("<!--->\n", (("<!--->\n", False),)),
        ("a <!-->\n", ()),
        ("a <!--->\n", ()),
    ],
)
def test_empty_comment_edge_forms_follow_the_closer_at_or_after_offset_four(
    source: str, expected: tuple[tuple[str, bool], ...]
):
    """
    [Unit] markdown blocks comment masking: documents the <!--> and <!---> edge forms as implemented.

    Scenario:
        Given the ``<!-->`` and ``<!--->`` empty-comment edge forms at line start and mid-line
        When the scanner runs
        Then the line-start forms are unclosed HTML-block comments to EOF (no ``-->`` lies at or after
        offset four) and the mid-line forms mask nothing - the detector's actual behaviour, pinned so a
        future CommonMark-exact empty-comment change is a deliberate, visible decision.

    Boundaries:
        - Focus: pinning the implemented closer-at-or-after-offset-four behaviour for the edge forms
        - Non-goal: full CommonMark empty-comment conformance (documented, not claimed)
        - Fixtures/params: parametrized over the line-start and mid-line edge forms

    On failure, first check:
        - The ``open_index + 4`` closer lower bound in _scan_comments
    """
    assert _comment_texts(source) == expected


def _single_line_block_flood(opener: str) -> Callable[[int], str]:
    """Return a builder repeating ``opener`` ``n`` times on one line.

    :param opener: The fragment to repeat.
    :returns: A ``size -> source`` builder.
    """

    def build(size: int) -> str:
        """Return the one-line flood for ``size`` repetitions.

        :param size: Repetition count.
        :returns: The Markdown source.
        """
        return opener * size + "\n"

    return build


#: Single-line flood shapes mapped to a builder and the exact comment count the
#: scanner must report. The opener floods collapse to one line-start unclosed
#: HTML-block comment; the closer flood and the code-span floods carry none.
_SINGLE_LINE: dict[str, tuple[Callable[[int], str], int]] = {
    "opener_flood": (_single_line_block_flood("<!--"), 1),
    "opener_space_flood": (_single_line_block_flood("<!-- "), 1),
    "closer_flood": (_single_line_block_flood("-->"), 0),
    "code_span_opener_flood": (_single_line_block_flood("`<!--`"), 0),
    "alternating_code_opener_flood": (_single_line_block_flood("`<!--` "), 0),
    "growing_backtick_runs": (
        lambda n: "".join(f"{'`' * ((i % 5) + 1)}<!--{'`' * ((i % 5) + 1)}" for i in range(n)) + "\n",
        0,
    ),
}

#: Multi-line flood shapes mapped to a builder and the exact comment count. The
#: paragraph of unclosed mid-line openers is the quadratic trap; the many-paragraph
#: and CRLF/CR variants exercise the per-opener paragraph-boundary bisect.
_MULTI_LINE: dict[str, tuple[Callable[[int], str], int]] = {
    "paragraph_of_unclosed_openers": (lambda n: "a <!--\n" * n, 0),
    "paragraphs_with_mid_line_opener": (lambda n: "text <!-- mid\nmore stuff\n\n" * n, 0),
    "crlf_unclosed_openers": (lambda n: "a <!--\r\n" * n, 0),
    "cr_only_unclosed_openers": (lambda n: "a <!--\r" * n, 0),
}

_SINGLE_LINE_SIZES = (2_000, 4_000, 8_000, 16_000)
_MULTI_LINE_SIZES = (2_000, 4_000, 8_000, 16_000)


@pytest.mark.parametrize("name", list(_SINGLE_LINE))
def test_single_line_comment_floods_stay_linear(name: str):
    """
    [Unit] markdown blocks comment masking: verifies single-line opener/closer floods scale near-linearly.

    Scenario:
        Given a pathologically long line of repeated openers, closers, or code-span-wrapped openers
        When the scanner runs over a doubling series of it
        Then the exact comment count holds at every size and the scan stays under the linear bound.

    Boundaries:
        - Focus: precompute + bisect comment scan, no per-opener forward ``-->`` search
        - Fixtures/params: parametrized over every single-line flood shape

    On failure, first check:
        - Whether _scan_comments regained a quadratic closer search from each opener
        - Whether _comment_mask or _all_occurrences became super-linear
    """
    build, expected = _SINGLE_LINE[name]
    assert_scales_linearly(
        build,
        lambda source: mb.scan_markdown(source, "README.md").comments,
        _SINGLE_LINE_SIZES,
        expected_count=expected,
        label=f"comment-{name}",
    )


@pytest.mark.parametrize("name", list(_MULTI_LINE))
def test_multi_line_comment_floods_stay_linear(name: str):
    """
    [Unit] markdown blocks comment masking: verifies multi-line opener floods scale near-linearly.

    Scenario:
        Given one paragraph of many unclosed mid-line openers, many paragraphs each with one mid-line
            opener, and the CRLF/CR-only variants, across a doubling series
        When the scanner runs over each size
        Then the exact comment count holds at every size and the scan stays under the linear bound - the
            one-paragraph flood is the exact quadratic trap the bisect bound defeats.

    Boundaries:
        - Focus: per-opener paragraph-boundary resolution is O(log n), not an O(n) rescan to EOF
        - Fixtures/params: parametrized over every multi-line flood shape

    On failure, first check:
        - Whether the blank-line bisect regressed to a linear paragraph-end scan per opener
        - Whether CRLF/CR line splitting changed the paragraph boundaries
    """
    build, expected = _MULTI_LINE[name]
    assert_scales_linearly(
        build,
        lambda source: mb.scan_markdown(source, "README.md").comments,
        _MULTI_LINE_SIZES,
        expected_count=expected,
        label=f"comment-{name}",
    )


#: Closed-comment floods mapped to a builder and an exact count formula. These pin
#: the second quadratic regression: a single huge line of many *closed* comments
#: used to rebuild the whole masked/sliced text once per comment (O(len) each,
#: quadratic overall). The count formula makes every pass non-vacuous. Sizes are
#: chosen so the smallest already costs tens of milliseconds of CPU, well above the
#: helper's floor, so a re-introduced quadratic cannot hide under timer noise.
_CLOSED_FLOODS: dict[str, tuple[Callable[[int], str], Callable[[int], int], tuple[int, ...]]] = {
    "closed_comment_single_line": (lambda n: "<!-- --> " * n + "\n", lambda n: n, (5_000, 10_000, 20_000, 40_000)),
    "empty_comment_single_line": (lambda n: "<!---->" * n + "\n", lambda n: n, (5_000, 10_000, 20_000, 40_000)),
    "lines_of_closed_comments": (
        lambda n: "<!-- --> <!-- --> <!-- -->\n" * n,
        lambda n: 3 * n,
        (2_000, 4_000, 8_000, 16_000),
    ),
    "multiline_closed_comments": (lambda n: "<!--\nx\n-->\n" * n, lambda n: n, (2_000, 4_000, 8_000, 16_000)),
    "link_adjacent_closed_comments": (
        lambda n: "[a](b) <!-- x --> " * n + "\n",
        lambda n: n,
        (4_000, 8_000, 16_000, 32_000),
    ),
    "code_adjacent_closed_comments": (
        lambda n: "`c` <!-- x --> " * n + "\n",
        lambda n: n,
        (4_000, 8_000, 16_000, 32_000),
    ),
}


@pytest.mark.parametrize("name", list(_CLOSED_FLOODS))
def test_closed_comment_floods_stay_linear(name: str):
    """
    [Unit] markdown blocks comment masking: verifies closed-comment floods scale near-linearly.

    Scenario:
        Given a single huge line of many closed comments, an empty-comment flood, many lines each
            holding several closed comments, many multi-line closed comments, and closed comments
            adjacent to links or code spans, across a doubling series
        When the scanner masks them
        Then the exact comment count holds at every size and the scan stays under the linear bound,
            proving the masked text is built once (segment collect + single join) rather than rebuilt
            once per comment.

    Boundaries:
        - Focus: the O(len)-per-comment rebuild regression; masking must stay O(total size)
        - Fixtures/params: parametrized over every closed-comment flood shape

    On failure, first check:
        - Whether _scan_comments regained a per-comment whole-text slice (for example the opener prefix)
        - Whether a consumer reintroduced a per-match whole-string rebuild
    """
    build, expected, sizes = _CLOSED_FLOODS[name]
    assert_scales_linearly(
        build,
        lambda source: mb.scan_markdown(source, "README.md").comments,
        sizes,
        expected_count=expected,
        label=f"comment-{name}",
    )
