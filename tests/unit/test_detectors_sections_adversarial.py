"""Adversarial complexity regression tests for DS106 section-content computation.

Section-content detection is a classic quadratic trap: a naive implementation
scans forward to the next heading for each heading, re-slices the text per
section, or re-scans the whole token list per heading, any of which is
``O(headings x lines)``. :func:`docsentinel.detectors.sections.check_text`
instead computes every section's extent in a single forward pass over the
physical lines with a heading pointer, so it stays ``O(headings + lines)``.

Each test drives the detector over a doubling series through the shared
:func:`tests.timing_helpers.assert_scales_linearly` (CPU time, best-of-N, floored
baseline, per-doubling ratio plus a log-log slope bound). The exact finding count
is asserted at every size so the pass is never vacuous. The inputs are multi-line
and non-fenced (in-fence adversarial input is the DS109 suite's concern) and
exercise the shapes the performance contract names: consecutive empty headings, one
short paragraph per heading, a single huge body, deeply alternating heading levels,
comment/placeholder floods between headings, CRLF and CR-only variants, and a
family of single pathologically long body lines.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from docsentinel.detectors import sections
from tests.timing_helpers import assert_scales_linearly

#: Multi-line document builders keyed by name, each mapped to a builder producing
#: roughly ``n`` physical lines of a non-fenced adversarial shape and the exact
#: DS106 finding-count formula that shape must yield at scale ``n``.
_BUILDERS: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    "consecutive_empty_headings": (lambda n: "## Empty\n" * n, lambda n: n),
    "heading_then_short_paragraph": (lambda n: "## S\n\ntext\n\n" * (n // 4), lambda _n: 0),
    "huge_blank_body": (lambda n: "# One\n" + "\n" * n, lambda _n: 1),
    "huge_comment_body": (lambda n: "# One\n" + "<!-- c -->\n" * n, lambda _n: 1),
    "huge_table_body": (lambda n: "# One\n| a | b |\n| - | - |\n" + "| c | d |\n" * n, lambda _n: 0),
    "huge_image_body": (lambda n: "# One\n" + "![a](i.png)\n" * n, lambda _n: 0),
    "alternating_heading_levels": (lambda n: "# A\n## B\n" * (n // 2), lambda n: n // 2),
    "placeholder_between_headings": (lambda n: "## S\nTODO\n" * (n // 2), lambda _n: 0),
    "comment_between_headings": (lambda n: "## S\n<!-- x -->\n" * (n // 2), lambda n: n // 2),
    "crlf_empty_headings": (lambda n: "## Empty\r\n" * n, lambda n: n),
    "cr_only_empty_headings": (lambda n: "## Empty\r" * n, lambda n: n),
}

#: A doubling series of line counts for the multi-line builders (the detector does
#: O(lines) work per document, so these stay fast while separating linear from quadratic).
_SIZES = (500, 1_000, 2_000, 4_000)

#: A larger doubling series for the single-line floods, where one very long body line
#: must rise above the floor so a per-opener tail rescan would show as super-linear.
_SINGLE_LINE_SIZES = (4_000, 8_000, 16_000, 32_000)


@pytest.mark.parametrize("name", list(_BUILDERS))
def test_section_content_stays_linear_across_doublings(name: str):
    """
    [Unit] detectors sections: verifies section-content computation stays near-linear.

    Scenario:
        Given multi-line non-fenced documents (consecutive empty headings, one short
            paragraph per heading, one heading over a huge blank/comment/table/image
            body, deeply alternating heading levels, placeholder/comment floods between
            headings, and CRLF and CR-only variants) across a doubling series
        When DS106 recognition runs over each size through check_text(text, path)
        Then the exact finding count holds at every size (so the pass is never vacuous) and the
            scaling stays under the shared linear bound, ruling out a per-heading forward scan,
            per-section text re-slicing, or a per-heading token re-scan.

    Boundaries:
        - Focus: O(headings + lines) single-pass extent computation
        - Fixtures/params: parametrized over every adversarial builder

    On failure, first check:
        - Whether _section_content regained a per-heading loop over lines or tokens
        - Whether a mask build began rescanning a document-global list per heading
    """
    builder, expected = _BUILDERS[name]
    assert_scales_linearly(
        builder,
        lambda text: sections.check_text(text, "README.md"),
        _SIZES,
        expected_count=expected,
        label=name,
    )


#: Single-line flood shapes: one pathologically long section-body line built by
#: repeating a fragment ``n`` times, keyed to the exact DS106 finding count that the
#: one flooded section must produce. These guard the per-line strippers and the
#: thematic/whitespace classifiers against a quadratic rescan of one long line (the
#: old ``re.sub`` strippers rescanned the tail from every candidate opener). A flood
#: that stays visible text counts as content (0 findings); a flood that reduces to
#: whitespace/thematic/empty-fence is contentless (1 finding).
_SINGLE_LINE_FLOODS: dict[str, tuple[str, int]] = {
    "angle_open": ("<", 0),
    "angle_open_letter": ("<a", 0),
    "image_open": ("![", 0),
    "comment_open": ("<!--", 0),
    "comment_close": ("-->", 0),
    "left_bracket": ("[", 0),
    "pipe": ("|", 0),
    "backtick": ("`", 1),
    "dash": ("-", 1),
    "space": (" ", 1),
    "hash": ("#", 0),
}


def _flood_document(fragment: str, repeats: int) -> str:
    """Return a one-section document whose only body line repeats ``fragment``."""
    return "# Title\n\n## Section\n\n" + fragment * repeats + "\n"


@pytest.mark.parametrize("flood", _SINGLE_LINE_FLOODS.values(), ids=list(_SINGLE_LINE_FLOODS))
def test_single_long_line_flood_stays_linear(flood: tuple[str, int]):
    """
    [Unit] detectors sections: verifies ONE long flooded line stays near-linear.

    Scenario:
        Given a single section whose only body is one very long line built by repeating an
            adversarial fragment ('<', '<a', '![', '<!--', '-->', '[', '|', '`', '-', ' ', '#')
            across a doubling series
        When DS106 recognition runs over each size through check_text(text, path)
        Then the flooded section yields the exact expected finding count at every size (so the pass
            is never vacuous) and the scaling stays under the shared linear bound, ruling out the
            old per-opener tail rescan that made one long line quadratic.

    Boundaries:
        - Focus: per-line comment/image/tag strippers and thematic/whitespace classifiers on ONE
          long line (distinct from the multi-line builders above)
        - Fixtures/params: parametrized over every single-line flood fragment

    On failure, first check:
        - Whether a stripper regained a backtracking .sub over the line tail
        - Whether the thematic/whitespace/fence classification of this fragment changed
    """
    fragment, expected_count = flood
    assert_scales_linearly(
        lambda size: _flood_document(fragment, size),
        lambda text: sections.check_text(text, "README.md"),
        _SINGLE_LINE_SIZES,
        expected_count=expected_count,
        label=repr(fragment),
    )
