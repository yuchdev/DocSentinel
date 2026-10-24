"""Adversarial complexity regression tests for the shared Markdown scanner.

Each test feeds a doubling series of single very long lines (or multi-line
documents) through both :func:`scan_markdown` and the DS1xx recognizer built on
it, and asserts near-linear scaling through the shared
:func:`tests.timing_helpers.assert_scales_linearly` (CPU time, best-of-N, floored
baseline, per-doubling ratio plus a log-log slope bound). The former per-start
quadratic rescans would blow the slope well past the linear bar; the shared helper
distinguishes that from timer noise. The result is asserted at every size so a dead
scanner cannot pass vacuously. These lines contain no fenced code; in-fence
adversarial input is covered by the DS109 integration suite.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from docsentinel.detectors import anchors, fences
from docsentinel.markdown_blocks import scan_markdown
from tests.timing_helpers import assert_scales_linearly

#: Adversarial repeat units, one per per-line pattern the scanner must keep
#: linear: bare brackets, link/image openers, reference-definition openers,
#: HTML anchor/image openers, and inline-code openers.
ADVERSARIAL_UNITS: dict[str, str] = {
    "open_bracket": "[",
    "link_prefix": "[a](",
    "close_bracket_paren": "](",
    "image_prefix": "![",
    "html_anchor_open": "<a ",
    "html_anchor_id_open": "<a id=",
    "html_img_open": "<img ",
    "inline_code_open": "`a",
    "reference_definition": "[x]: ",
}

#: A doubling series of characters per single line. The scanner is cheap per
#: character, so these sizes keep the measurement above the floor while staying fast.
_LINE_SIZES = (8_000, 16_000, 32_000, 64_000)

#: A doubling series of physical line counts for multi-line documents.
_MULTILINE_SIZES = (500, 1_000, 2_000, 4_000)


def _line(unit: str, approx_chars: int) -> str:
    """Build a single line of ``unit`` repeated to about ``approx_chars`` chars."""
    return unit * (approx_chars // len(unit))


def _reference_tokens(line: str) -> tuple[object, ...]:
    """Return the link/image/reference tokens scan_markdown finds in ``line``.

    Inline-code spans are deliberately excluded: every adversarial unit here holds no
    closable link, image or reference, so this is empty for all of them (the headline
    non-vacuous correctness claim), while the scanner still does its inline-code work
    under the timer.

    :param line: One non-fenced line of a repeated adversarial unit.
    :returns: A tuple of the reference-shaped tokens (empty for these floods).
    """
    index = scan_markdown(line, "README.md")
    return (*index.local_references, *index.images, *index.reference_uses)


@pytest.mark.parametrize("unit", ADVERSARIAL_UNITS.values(), ids=list(ADVERSARIAL_UNITS))
@pytest.mark.parametrize(
    ("label", "run"),
    (
        ("scan_markdown", _reference_tokens),
        ("check_text", lambda line: fences.check_text(line, "README.md")),
    ),
    ids=("scan_markdown", "check_text"),
)
def test_non_fenced_adversarial_line_stays_linear(label: str, run: Callable[[str], object], unit: str):
    """
    [Unit] markdown blocks: adversarial single lines tokenize in near-linear time.

    Scenario:
        Given a single non-fenced line of a repeated adversarial unit across a
            10k/20k/40k/80k doubling series
        When the shared scanner (and the DS109 recognizer built on it) tokenizes each
        Then every size yields zero reference/image/finding tokens (so the pass is never vacuous)
            and the scaling stays under the shared linear bound, ruling out the former per-start
            quadratic rescans.

    Boundaries:
        - Focus: complexity bound of the per-line tokenizer scanners
        - Fixtures/params: parametrized over every adversarial unit and both entry points

    On failure, first check:
        - Whether a per-line regex regained a greedy ``[^..]*`` that rescans per start
        - Whether the new hand-rolled scanners advance past a failed start in one step
    """
    assert_scales_linearly(
        lambda size: _line(unit, size),
        run,
        _LINE_SIZES,
        expected_count=0,
        label=f"{label}/{unit}",
    )


def test_open_bracket_flood_yields_no_tokens():
    """
    [Unit] markdown blocks: a flood of ``[`` produces no link, image, or reference tokens.

    Scenario:
        Given a single line of tens of thousands of ``[`` characters
        When scan_markdown tokenizes it
        Then no inline link, image, reference use, or inline-code token is emitted.

    Boundaries:
        - Focus: correctness of the linear scanners on the headline adversarial input
        - Fixtures/params: none

    On failure, first check:
        - The ``]``-absent break in _find_inline_links and _find_reference_uses
        - That no spurious token is produced from unmatched brackets
    """
    index = scan_markdown("[" * 40_000, "README.md")

    assert index.local_references == ()
    assert index.images == ()
    assert index.reference_uses == ()
    assert index.inline_code == ()


def test_unclosed_anchor_tag_with_many_attrs_stays_linear_and_empty():
    """
    [Unit] markdown blocks: one ``<a`` opener with a flood of attributes yields no anchors.

    Scenario:
        Given a single non-fenced line of ``<a `` followed by tens of thousands of
            ``x=y `` pseudo-attributes and no closing ``>``
        When scan_markdown extracts explicit anchors
        Then no HtmlAnchor or html_anchors string is produced and extraction returns
            fast, because no ``id``/``name`` attribute matches.

    Boundaries:
        - Focus: the no-matching-attribute early exit in _find_html_anchor_attributes
        - Fixtures/params: none

    On failure, first check:
        - That extraction early-returns when no id/name attribute exists
        - That a lone opener never rescans the remainder per pseudo-attribute
    """
    index = scan_markdown("<a " + "x=y " * 40_000, "README.md")

    assert index.explicit_anchors == ()
    assert index.html_anchors == ()


#: Anchor-tag flood units whose per-opener ``find('>')`` was O(n) before the fix:
#: an unterminated or far-closing tag made a single line O(openers * len). Each maps
#: its opener shape to the integer divisor ``k`` in the exact anchor-count formula
#: ``(size // len(unit)) // k`` (``k == 0`` means the shape yields no anchor at all),
#: so the timing bound is pinned to an exact, size-scaling count rather than asserted
#: vacuously. Each is exercised with no closing ``>`` and with one trailing ``>``.
_ANCHOR_FLOOD_UNITS: dict[str, tuple[str, int]] = {
    "id_dquote_unterminated": ('<a id="', 2),
    "id_dquote_no_close": ('<a id="x', 2),
    "id_squote_unterminated": ("<a id='", 2),
    "id_unquoted": ("<a id=x ", 0),
    "name_valid_spaced": ('<a name="a" ', 1),
    "attr_then_space": ('<a id="a" ', 1),
}


@pytest.mark.parametrize("suffix", ("", ">"), ids=("no_close", "trailing_gt"))
@pytest.mark.parametrize("unit", _ANCHOR_FLOOD_UNITS.values(), ids=list(_ANCHOR_FLOOD_UNITS))
def test_anchor_tag_flood_stays_linear(unit: tuple[str, int], suffix: str):
    """
    [Unit] markdown blocks: unterminated/far-closing ``<a>`` floods tokenize linearly.

    Scenario:
        Given a single non-fenced line of a repeated ``<a>`` opener shape, with no
            closing ``>`` and with one trailing ``>``, across a doubling series
        When scan_markdown tokenizes each size
        Then the exact (size-scaling) explicit-anchor count holds at every size (so the pass is
            never vacuous) and the scaling stays under the shared linear bound, ruling out the
            former per-opener ``find('>')`` that rescanned to end of line from every opener.

    Boundaries:
        - Focus: the forward-only ``>`` cursor in _find_tagged_attributes and
          _find_html_anchor_attributes
        - Fixtures/params: every anchor flood shape, with and without a trailing ``>``

    On failure, first check:
        - Whether a closer search regained a per-opener ``find('>')`` to end of line
        - That the ``>`` cursor only advances forward across openers
    """
    opener, divisor = unit
    assert_scales_linearly(
        lambda size: _line(opener, size) + suffix,
        lambda line: scan_markdown(line, "README.md").explicit_anchors,
        _LINE_SIZES,
        expected_count=lambda size: 0 if divisor == 0 else (size // len(opener)) // divisor,
        label=f"{opener!r}/{suffix!r}",
    )


def test_anchor_flood_shapes_produce_consistent_tokens():
    """
    [Unit] markdown blocks: anchor flood shapes extract the expected (bounded) tokens.

    Scenario:
        Given an unquoted-attribute flood and a valid spaced-attribute flood
        When scan_markdown tokenizes each
        Then the unquoted flood yields no anchors and the valid flood yields one
            anchor per opener, confirming the linearity fix did not change behavior.

    Boundaries:
        - Focus: correctness parity of the forward-only cursor on valid and junk input
        - Fixtures/params: none

    On failure, first check:
        - That the ``>`` cursor still bounds attribute selection to within the tag
        - That unquoted attributes still match no anchor
    """
    assert scan_markdown("<a id=x " * 2_000, "README.md").explicit_anchors == ()
    valid = scan_markdown('<a name="a"> ' * 2_000, "README.md")
    assert [a.value for a in valid.explicit_anchors] == ["a"] * 2_000
    assert valid.html_anchors == ("a",) * 2_000


#: Multi-line document builders keyed by name, each producing roughly ``n`` physical
#: lines. These exercise per-line helpers against document-global collections
#: (comment ranges, fence mask, headings, references, table rows) that the earlier
#: single-line adversarial tests never stressed. A comment-per-line flood in
#: particular was quadratic before the _mask_line moving-cursor fix.
_MULTILINE_BUILDERS: dict[str, Callable[[int], str]] = {
    "comment_per_line": lambda n: "<!-- c -->\n" * n,
    "multiline_comments": lambda n: "<!--\nbody\n-->\n" * (n // 3),
    "comment_anchor_backtick": lambda n: '<a name="a"></a> <!-- c --> `code`\n' * n,
    "many_short_fences": lambda n: "```\nx\n```\n" * (n // 3),
    "many_headings": lambda n: "# Heading\n" * n,
    "many_reference_defs": lambda n: "[label]: target\n" * n,
    "many_reference_uses": lambda n: "[text][label]\n" * n,
    "many_table_rows": lambda n: "| a | b |\n| - | - |\n" + "| c | d |\n" * n,
    "many_blank_lines": lambda n: "\n" * n,
    "cr_only_flood": lambda n: "x\r" * n,
    "crlf_flood": lambda n: "x\r\n" * n,
}


def _zero_expected(_size: int) -> int:
    """Return the zero expected count for a builder/entry-point pair that emits no token."""
    return 0


#: Per-builder exact expected counts under each entry point, pinning the timing bound to a
#: non-vacuous result. ``scan_markdown`` is probed through its heading list (only the heading
#: flood is non-zero) and ``check_text`` through DS104 (only the repeated named anchor is
#: non-zero, at one duplicate finding per occurrence after the first).
_SCAN_HEADING_EXPECTED: dict[str, Callable[[int], int]] = {"many_headings": lambda n: n}
_DS104_EXPECTED: dict[str, Callable[[int], int]] = {"comment_anchor_backtick": lambda n: n - 1}

#: The two entry points driven over every multi-line builder: a label, the timed run, and
#: the per-builder expected-count lookup for that entry point.
_MULTILINE_ENTRYPOINTS: tuple[tuple[str, Callable[[str], object], dict[str, Callable[[int], int]]], ...] = (
    ("scan_markdown", lambda text: scan_markdown(text, "README.md").headings, _SCAN_HEADING_EXPECTED),
    ("check_text", lambda text: anchors.check_text(text, "README.md"), _DS104_EXPECTED),
)


@pytest.mark.parametrize("entrypoint", _MULTILINE_ENTRYPOINTS, ids=[entry[0] for entry in _MULTILINE_ENTRYPOINTS])
@pytest.mark.parametrize("name", list(_MULTILINE_BUILDERS))
def test_multiline_document_floods_stay_linear(
    name: str, entrypoint: tuple[str, Callable[[str], object], dict[str, Callable[[int], int]]]
):
    """
    [Unit] markdown blocks: multi-line document floods tokenize in near-linear time.

    Scenario:
        Given multi-line documents (comment-per-line, multi-line comments, comment+anchor+
            backtick per line, many short fences, many headings, reference defs/uses, table
            rows, blank lines, CR-only and CRLF floods) across a doubling series of line counts
        When the shared scanner and the DS104 recognizer built on it tokenize each size
        Then the exact per-builder result count holds at every size (so the pass is never vacuous)
            and the scaling stays under the shared linear bound, ruling out any per-line iteration
            over a document-global collection (the former quadratic comment mask grew super-linearly).

    Boundaries:
        - Focus: O(lines + overlap) behavior of the main-loop helpers on multi-line input
        - Fixtures/params: parametrized over every builder and both entry points

    On failure, first check:
        - Whether _mask_line regained a per-line loop over all comment ranges
        - Whether another per-line helper began scanning a document-global list
    """
    builder = _MULTILINE_BUILDERS[name]
    label, run, expected_map = entrypoint
    assert_scales_linearly(
        builder,
        run,
        _MULTILINE_SIZES,
        expected_count=expected_map.get(name, _zero_expected),
        label=f"{label}/{name}",
    )
