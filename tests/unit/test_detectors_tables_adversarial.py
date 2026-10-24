"""Adversarial complexity regression tests for DS117 pipe-table recognition.

DS117 scans a document once, splits it into physical lines once, and then walks
the lines a single time, splitting each line into logical cells at most twice (as
a possible header and as the following line's delimiter probe). Every one of those
steps is a quadratic trap if written naively: a per-cell rescan of the rest of a
line, a code-span matcher that rescans from every unmatched backtick run, a
delimiter-marker regex that backtracks on a long dash run, or a per-table rescan of
the whole line list. These tests drive the detector over doubling series of both
single-line floods (one pathologically long line) and multi-line floods (many
tables, rows, or near-tables) through the shared
:func:`tests.timing_helpers.assert_scales_linearly` (CPU time, best-of-N, floored
baseline, per-doubling ratio plus a log-log slope bound), asserting the exact DS117
finding count at every size so the pass is never vacuous.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from docsentinel.config import Config
from docsentinel.detectors import tables
from tests.timing_helpers import assert_scales_linearly

#: Default configuration; table checks are enabled and strict by default.
_DEFAULT = Config()

#: A doubling series of line counts for the multi-line floods (the detector does
#: O(lines) work with a high constant, so these stay fast while still separating
#: linear from quadratic under the shared criterion).
_MULTI_SIZES = (250, 500, 1_000, 2_000)

#: A larger doubling series for the single-line / single-table floods, where one very
#: long line is cheap to build yet must rise above the floor for the slope to bite.
_LINE_SIZES = (2_000, 4_000, 8_000, 16_000)


def _run(config: Config) -> Callable[[str], object]:
    """Return a timed run that recognizes DS117 findings in a document under ``config``.

    :param config: Effective settings for the DS117 recognition pass.
    :returns: A ``text -> findings`` callable for :func:`assert_scales_linearly`.
    """
    return lambda text: tables.check_text(text, "README.md", config)


def _increasing_backtick_run(n: int) -> str:
    """Return one line of unmatched backtick runs of strictly INCREASING length.

    ``x`x``x```x...`` packs runs of length 1, 2, 3, ... separated by ``x`` so no two
    runs share a length and none ever closes. A code-span matcher that rescans the
    remainder of the line from every opener is O(n^1.5) here (the HIGH-severity bug);
    the shared backtick-run index closes it to linear. ``n`` bounds the line length.

    :param n: Approximate target line length in characters.
    :returns: The adversarial line with a trailing newline.
    """
    parts: list[str] = []
    run_length = 1
    size = 0
    while size < n:
        parts.append("x")
        parts.append("`" * run_length)
        size += 1 + run_length
        run_length += 1
    parts.append("\n")
    return "".join(parts)


#: Single-line floods: each builds ONE pathologically long line that cannot form a
#: table on its own (there is no second line to delimit it), so the expected finding
#: count is exactly 0. They exercise the cell splitter, the code-span matcher, the
#: escape handling, and the delimiter-candidate classifier on one huge line.
_SINGLE_LINE_FLOODS: dict[str, Callable[[int], str]] = {
    "pipe_run": lambda n: "|" * n + "\n",
    "escaped_pipe_run": lambda n: "\\|" * n + "\n",
    "backtick_pipe_run": lambda n: "`|" * n + "\n",
    "double_backtick_pipe_run": lambda n: "``|" * n + "\n",
    "increasing_backtick_run": _increasing_backtick_run,
    "align_cell_run": lambda n: ":-:|" * n + "\n",
}


@pytest.mark.parametrize("builder", _SINGLE_LINE_FLOODS.values(), ids=list(_SINGLE_LINE_FLOODS))
def test_single_line_flood_stays_linear(builder: Callable[[int], str]):
    """
    [Unit] detectors tables: verifies ONE long flooded line stays near-linear.

    Scenario:
        Given a single pathologically long line built by repeating an adversarial fragment
            ('|', '\\|', '`|', '``|', strictly increasing backtick runs, ':-:|')
            across a doubling series
        When DS117 recognition runs over each size through check_text(text, path, config)
        Then no finding is produced at any size (a lone line cannot form a table) and the scaling
            stays under the shared linear bound, ruling out a per-cell line rescan or a code-span
            matcher that rescans from every unmatched backtick run.

    Boundaries:
        - Focus: _split_logical_cells, the shared backtick-run index, and _is_delimiter_candidate
          on one line
        - Fixtures/params: parametrized over every single-line flood builder

    On failure, first check:
        - Whether the backtick code-span lookup began rescanning the tail from every run
        - Whether the escape or pipe branch started scanning the whole line per cell
    """
    assert_scales_linearly(builder, _run(_DEFAULT), _LINE_SIZES, expected_count=0, label="single-line")


#: Multi-line floods: each builds ``n`` repeat units and a finding count as a function
#: of ``n``. These guard the single forward pass over the physical lines against a
#: per-table rescan and verify body/delimiter checks stay linear when every row is a
#: finding, plus CRLF/CR, list, and blockquote shapes.
_MULTI_LINE_FLOODS: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    "many_broken_tables": (lambda n: "| a | b |\n| - |\n\n" * n, lambda n: n),
    "one_table_many_body_rows": (
        lambda n: "| a | b |\n| - | - |\n" + "| 1 | 2 | 3 |\n" * n,
        lambda n: n,
    ),
    "crlf_broken_tables": (lambda n: "| a | b |\r\n| - |\r\n\r\n" * n, lambda n: n),
    "cr_broken_tables": (lambda n: "| a | b |\r| - |\r\r" * n, lambda n: n),
    # List-item table-shaped lines are documented non-tables (DS117 treats unsupported
    # block constructs as non-tables), so this contributes no finding at any scale; the
    # liveness guard below proves a plain broken table still fires under the same config.
    "tables_in_list_items": (lambda n: "- | a | b |\n  | - |\n\n" * n, lambda n: 0),
}


@pytest.mark.parametrize("flood", _MULTI_LINE_FLOODS.values(), ids=list(_MULTI_LINE_FLOODS))
def test_multi_line_flood_stays_linear(flood: tuple[Callable[[int], str], Callable[[int], int]]):
    """
    [Unit] detectors tables: verifies many tables and rows stay near-linear.

    Scenario:
        Given many repeat units of one shape (broken tables, one table with many body rows,
            CRLF and CR broken tables, and list-item non-tables) across a doubling series
        When DS117 recognition runs over each size through check_text(text, path, config)
        Then the exact expected finding count holds at every size (so the pass is never vacuous)
            and the scaling stays under the shared linear bound, ruling out a per-table rescan.

    Boundaries:
        - Focus: the single forward pass over lines and its finding-producing branches
        - Fixtures/params: parametrized over every multi-line flood builder

    On failure, first check:
        - Whether the body loop regained a scan over the whole line list
        - Whether a shape misclassified header/delimiter adjacency
    """
    builder, count_of = flood
    # Liveness guard so a zero-count shape can never pass vacuously: under the SAME
    # config a plain broken table must still produce exactly one finding, so a zero
    # below reflects the shape, not a dead detector.
    assert len(tables.check_text("| a | b |\n| - |\n", "README.md", _DEFAULT)) == 1
    assert_scales_linearly(builder, _run(_DEFAULT), _MULTI_SIZES, expected_count=count_of, label="multi-line")


def _wide_row(cell: str, columns: int) -> str:
    """Return a one-line pipe row of ``columns`` cells each holding ``cell``.

    :param cell: The repeated cell body.
    :param columns: Number of logical cells.
    :returns: A bordered pipe row line with a trailing newline.
    """
    return "|" + "".join(f"{cell}|" for _ in range(columns)) + "\n"


def test_wide_matching_table_stays_linear():
    """
    [Unit] detectors tables: verifies a very wide, consistent table stays near-linear.

    Scenario:
        Given a header row and delimiter row that each carry N columns and agree
        When DS117 recognition runs across a doubling series of column counts
        Then no finding is produced (counts agree) and the scaling stays under the shared linear
            bound, proving both huge rows split in time linear in their width.

    Boundaries:
        - Focus: splitting two very wide rows and comparing counts once
        - Fixtures/params: default Config

    On failure, first check:
        - Whether header/delimiter splitting became quadratic in the column count
        - The header-count comparison path
    """
    assert_scales_linearly(
        lambda n: _wide_row("a", n) + _wide_row("-", n),
        _run(_DEFAULT),
        _LINE_SIZES,
        expected_count=0,
        label="wide-matching",
    )


def test_wide_body_mismatch_stays_linear():
    """
    [Unit] detectors tables: verifies one very wide mismatched body row stays near-linear.

    Scenario:
        Given a two-column table and one body row of N columns
        When DS117 recognition runs across a doubling series of body widths
        Then exactly one finding is produced (the mismatched body row) at every size and the
            scaling stays under the shared linear bound.

    Boundaries:
        - Focus: splitting one huge body row and a single count check
        - Fixtures/params: default Config

    On failure, first check:
        - Whether the body-row split became quadratic in the column count
        - The strict body-count branch
    """
    assert_scales_linearly(
        lambda n: "| a | b |\n| - | - |\n" + _wide_row("x", n),
        _run(_DEFAULT),
        _LINE_SIZES,
        expected_count=1,
        label="wide-body",
    )


def test_long_dash_delimiter_stays_linear():
    """
    [Unit] detectors tables: verifies a huge dash run in a delimiter cell stays near-linear.

    Scenario:
        Given a two-column header and a delimiter whose second cell is a malformed marker built
            from a very long dash run followed by an interior colon and trailing dash
        When DS117 recognition runs across a doubling series of dash-run lengths
        Then exactly one malformed-marker finding is produced at every size and the scaling stays
            under the shared linear bound, proving the marker regex does not backtrack on a long run.

    Boundaries:
        - Focus: the _VALID_MARKER_RE match on a pathologically long cell
        - Fixtures/params: default Config

    On failure, first check:
        - Whether _VALID_MARKER_RE lost its single greedy dash-run character class
        - Whether _is_delimiter_candidate rescanned the cell per character superlinearly
    """
    assert_scales_linearly(
        lambda n: f"| a | b |\n| --- | {'-' * n + ':-'} |\n",  # interior colon makes the marker malformed
        _run(_DEFAULT),
        _LINE_SIZES,
        expected_count=1,
        label="long-dash",
    )
