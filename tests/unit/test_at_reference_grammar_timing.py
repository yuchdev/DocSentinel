"""Complexity regression tests for the shared scanner's ``@``-mention recognition.

Threat model T4 / M8 (Milestone 0009 Story 01.0): recognition must be one
left-to-right pass per line that examines each character a bounded number of
times, skips an over-long run as a whole and resumes after it, and never builds a
pattern from input. Each test feeds a doubling series of adversarial lines (or
documents) through :func:`scan_markdown` and asserts near-linear scaling with the
shared :func:`tests.timing_helpers.assert_scales_linearly` (CPU time, best-of-N,
floored baseline, per-doubling ratio and log-log slope), with a fixed expected
mention count at every size so a dead recogniser cannot pass vacuously.
"""

from __future__ import annotations

from docsentinel.markdown_blocks import AT_TOKEN_MAX_CHARS, AtReference, scan_markdown
from tests.timing_helpers import assert_scales_linearly

#: A doubling series of characters per single line, as in the other scanner timing tests.
_LINE_SIZES = (8_000, 16_000, 32_000, 64_000)

#: The 1 MB series the task spec names for a line of repeated ``@a``.
_MEGABYTE_SIZES = (131_072, 262_144, 524_288, 1_048_576)

#: A doubling series of physical line counts for multi-line documents.
_MULTILINE_SIZES = (500, 1_000, 2_000, 4_000)


def _mentions(text: str) -> tuple[AtReference, ...]:
    """Return the ``@``-mentions recorded for ``text`` (the timed call).

    :param text: Markdown source.
    :returns: The scanner's ``at_references``.
    """
    return scan_markdown(text, "README.md").at_references


def _repeat(unit: str, approx_chars: int) -> str:
    """Return ``unit`` repeated to about ``approx_chars`` characters.

    :param unit: The repeat unit.
    :param approx_chars: Target length.
    :returns: The built line.
    """
    return unit * (approx_chars // len(unit))


def test_many_at_signs_linear():
    """
    [Unit] at-reference timing: a 1 MB line of repeated ``@a`` stays linear and records nothing.

    Scenario:
        Given single lines of ``@a`` repeated up to 1 MB
        When scan_markdown runs
        Then no mention is recorded (only the first ``@`` has a boundary and ``a`` has no extension)
            and the scaling stays under the linear bound.

    Boundaries:
        - Focus: M8, every rejected ``@`` costs O(1)
        - Fixtures/params: 128 KiB to 1 MiB doubling series

    On failure, first check:
        - _find_prose_at_references must jump with str.find and never rescan a run
    """
    assert_scales_linearly(
        lambda size: _repeat("@a", size),
        _mentions,
        _MEGABYTE_SIZES,
        expected_count=0,
        label="@a",
    )


def test_bare_at_sign_flood_linear():
    """
    [Unit] at-reference timing: a line made only of ``@`` characters stays linear.

    Scenario:
        Given single lines of ``@`` repeated
        When scan_markdown runs
        Then no mention is recorded and the scaling stays linear.

    Boundaries:
        - Focus: M8, a million-``@`` line
        - Fixtures/params: the shared line-size series

    On failure, first check:
        - The ``@``-after-``@`` rejection is O(1)
    """
    assert_scales_linearly(lambda size: "@" * size, _mentions, _LINE_SIZES, expected_count=0, label="@")


def test_dense_mentions_linear():
    """
    [Unit] at-reference timing: a line packed with short valid mentions stays linear.

    Scenario:
        Given single lines of `` @a.md`` repeated
        When scan_markdown runs
        Then one mention per unit is recorded and the scaling stays linear.

    Boundaries:
        - Focus: M8, recording cost per mention is constant
        - Fixtures/params: the shared line-size series

    On failure, first check:
        - Per-mention work in _at_token and the merge in scan_markdown
    """
    unit = " @a.md"
    assert_scales_linearly(
        lambda size: _repeat(unit, size),
        _mentions,
        _LINE_SIZES,
        expected_count=lambda size: size // len(unit),
        label="dense",
    )


def test_overlong_token_linear():
    """
    [Unit] at-reference timing: one ``@`` followed by a huge token run is skipped in linear time.

    Scenario:
        Given ``@`` plus tens of thousands of token characters (all above the 1,024 cap) plus ``.md``
        When scan_markdown runs
        Then no mention is recorded and the scaling stays linear.

    Boundaries:
        - Focus: M8, the over-long run is skipped whole and scanning resumes after it
        - Fixtures/params: the shared line-size series

    On failure, first check:
        - _find_prose_at_references resume offset after a rejected run
    """
    assert _LINE_SIZES[0] > AT_TOKEN_MAX_CHARS
    assert_scales_linearly(
        lambda size: "@" + "a/" * (size // 2) + ".md",
        _mentions,
        _LINE_SIZES,
        expected_count=0,
        label="overlong",
    )


def test_escaped_space_flood_linear():
    """
    [Unit] at-reference timing: floods of escaped spaces stay linear, both over-long and dense.

    Scenario:
        Given one ``@`` followed by a huge run of ``a\\ `` pairs, and separately a line of short
            mentions each holding an escaped space
        When scan_markdown runs
        Then the over-long run records nothing, the dense line records one per unit, and both scale linearly.

    Boundaries:
        - Focus: M8 with the two-character escape
        - Fixtures/params: the shared line-size series

    On failure, first check:
        - The escaped-space branch of _consume_at_token
    """
    assert_scales_linearly(
        lambda size: "@" + "a\\ " * (size // 3) + "b.md",
        _mentions,
        _LINE_SIZES,
        expected_count=0,
        label="escaped-overlong",
    )
    unit = " @a\\ b.md"
    assert_scales_linearly(
        lambda size: _repeat(unit, size),
        _mentions,
        _LINE_SIZES,
        expected_count=lambda size: size // len(unit),
        label="escaped-dense",
    )


def test_open_punctuation_flood_linear():
    """
    [Unit] at-reference timing: floods of the four opening characters (with and without ``@``) stay linear.

    Scenario:
        Given lines of ``("[\'`` repeated and lines of ``(@`` repeated
        When scan_markdown runs
        Then no mention is recorded and both scale linearly.

    Boundaries:
        - Focus: M8, boundary checks are O(1); ``[`` floods also exercise the link exclusions
        - Fixtures/params: the shared line-size series

    On failure, first check:
        - _merge_ranges and the exclusion pointer
    """
    for unit in ("(\"['", "(@", "[@"):
        assert_scales_linearly(
            lambda size, unit=unit: _repeat(unit, size),
            _mentions,
            _LINE_SIZES,
            expected_count=0,
            label=f"open:{unit}",
        )


def test_code_span_form_flood_linear():
    """
    [Unit] at-reference timing: a line packed with code-span mentions stays linear.

    Scenario:
        Given single lines of ```@a.md` `` repeated
        When scan_markdown runs
        Then one in-code-span mention per unit is recorded and the scaling stays linear.

    Boundaries:
        - Focus: M8 on the code-span form
        - Fixtures/params: the shared line-size series

    On failure, first check:
        - _code_span_at_reference is O(span length)
    """
    unit = "`@a.md` "
    assert_scales_linearly(
        lambda size: _repeat(unit, size),
        _mentions,
        _LINE_SIZES,
        expected_count=lambda size: size // len(unit),
        label="code-span",
    )


def test_multi_line_mention_flood_linear():
    """
    [Unit] at-reference timing: a document with one mention per line, mixed forms, stays linear.

    Scenario:
        Given documents of thousands of lines, each with a prose mention, a link and a code-span mention
        When scan_markdown runs
        Then two mentions per line are recorded and the scaling stays linear in the line count.

    Boundaries:
        - Focus: M8 across lines (no per-document rescans)
        - Fixtures/params: the shared multi-line size series

    On failure, first check:
        - Per-line state in scan_markdown (exclusions, line_mentions) is reset per line
    """
    line = "see @docs/a.md and [x](y.md) and `@b.md` here\n"
    assert_scales_linearly(
        lambda size: line * size,
        _mentions,
        _MULTILINE_SIZES,
        expected_count=lambda size: 2 * size,
        label="multi-line",
    )
