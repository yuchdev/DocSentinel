"""Parity and complexity tests for the shared inline-code (backtick) matcher.

The shared matcher in :mod:`docsentinel.markdown_blocks`
(:func:`~docsentinel.markdown_blocks.find_code_spans` plus the backtick-run index
behind :func:`~docsentinel.markdown_blocks.first_backtick_run_at_or_after`) replaced
two independent quadratic implementations: the scanner's former ``_find_inline_code``
and ``DS117``'s former ``_match_code_span``. Both rescanned the remainder of a line
from every unmatched opener, which is O(n^1.5) on one line of unmatched backtick runs
of strictly increasing length (``x`x``x```x...``) -- the reproduced HIGH-severity
finding.

Two guarantees are pinned here. First, an ORACLE parity check keeps the *old*
quadratic algorithms inside this test module and asserts the new shared matcher is
byte-identical to them over a large seeded random corpus of backtick/pipe/backslash
soup -- identical code-span ranges, identical ``DS117`` cell splits, and identical
``DS117`` findings. Second, a complexity regression drives the strictly-increasing
backtick line at 8/16/32/64 KB through the scanner and every detector that consumes
inline-code ranges (``DS117`` ``check_text``, ``DS106`` sections, ``DS104`` anchors,
``DS110`` fences) and asserts each doubling of input stays well under a quadratic
growth bar using CPU time, with exact result assertions so the pass is never vacuous.
"""

from __future__ import annotations

import random
from collections.abc import Callable

import pytest

from docsentinel import markdown_blocks as mb
from docsentinel.config import Config
from docsentinel.detectors import anchors, fence_languages, sections, tables
from tests.timing_helpers import assert_scales_linearly


def _oracle_code_spans(content: str) -> list[tuple[int, int, int]]:
    """Return inline code spans using the original quadratic rescan algorithm.

    This is the pre-fix ``_find_inline_code`` body (sans inner text): for each opener
    run it rescans the remainder of the line character by character for the first run
    of the same length. Kept here as the parity oracle for :func:`find_code_spans`.

    :param content: One line of text without its terminator.
    :returns: ``(start, end, run_length)`` spans in source order.
    """
    results: list[tuple[int, int, int]] = []
    index = 0
    length = len(content)
    while index < length:
        if content[index] != "`":
            index += 1
            continue
        run_end = index
        while run_end < length and content[run_end] == "`":
            run_end += 1
        run = run_end - index
        cursor = run_end
        closed = False
        while cursor < length:
            if content[cursor] != "`":
                cursor += 1
                continue
            close_end = cursor
            while close_end < length and content[close_end] == "`":
                close_end += 1
            if close_end - cursor == run:
                results.append((index, close_end, run))
                index = close_end
                closed = True
                break
            cursor = close_end
        if not closed:
            index = run_end
    return results


def _oracle_match_code_span(content: str, start: int, run: int, length: int) -> int:
    """Return a code-span end using the original quadratic rescan (pre-fix ``_match_code_span``)."""
    cursor = start
    while cursor < length:
        if content[cursor] != "`":
            cursor += 1
            continue
        close_end = cursor
        while close_end < length and content[close_end] == "`":
            close_end += 1
        if close_end - cursor == run:
            return close_end
        cursor = close_end
    return -1


def _oracle_split(content: str) -> tuple[str, ...]:
    """Split a table row into logical cells using the original quadratic matcher.

    This is the pre-fix ``_split_logical_cells`` body, the parity oracle for the
    current :func:`docsentinel.detectors.tables._split_logical_cells`.

    :param content: One physical table-row line without its terminator.
    :returns: The trimmed cells in column order.
    """
    cells: list[str] = []
    buffer: list[str] = []
    index = 0
    length = len(content)
    while index < length:
        char = content[index]
        if char == "\\" and index + 1 < length:
            buffer.append(content[index : index + 2])
            index += 2
            continue
        if char == "`":
            run_end = index + 1
            while run_end < length and content[run_end] == "`":
                run_end += 1
            run = run_end - index
            close_end = _oracle_match_code_span(content, run_end, run, length)
            end = run_end if close_end == -1 else close_end
            buffer.append(content[index:end])
            index = end
            continue
        if char == "|":
            cells.append("".join(buffer))
            buffer = []
            index += 1
            continue
        buffer.append(char)
        index += 1
    cells.append("".join(buffer))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return tuple(cell.strip() for cell in cells)


def _random_soup_lines(count: int, seed: int = 20240617) -> list[str]:
    """Return ``count`` seeded random lines of backtick/pipe/backslash/text soup.

    The alphabet favours backtick runs of varied length, pipes, backslashes (so
    escaped backticks and escaped pipes appear), spaces, colons, dashes and letters,
    producing unmatched openers, code spans that straddle pipes, and escaped
    delimiters -- exactly the cases the two matchers must agree on.

    :param count: Number of lines to generate.
    :param seed: Deterministic seed so the corpus is reproducible.
    :returns: The generated lines without terminators.
    """
    rng = random.Random(seed)
    fragments = ["`", "``", "```", "````", "`````", "|", "\\", "\\|", "\\`", " ", ":", "-", "a", "b", "x", "`|", "``|"]
    lines: list[str] = []
    for _ in range(count):
        length = rng.randint(0, 24)
        lines.append("".join(rng.choice(fragments) for _ in range(length)))
    return lines


def test_find_code_spans_matches_the_quadratic_oracle():
    """
    [Unit] markdown blocks: verifies the shared matcher equals the quadratic oracle on random soup.

    Scenario:
        Given several thousand seeded random lines of backtick/pipe/backslash soup
        When find_code_spans and the kept quadratic oracle each scan every line
        Then the two produce byte-identical code-span ranges for every line.

    Boundaries:
        - Focus: byte-identical behaviour of the new linear scanner matcher
        - Fixtures/params: none (deterministic seeded corpus)

    On failure, first check:
        - Whether find_code_spans changed its opener/closer pairing or span bounds
        - The specific line printed in the assertion message
    """
    for line in _random_soup_lines(4_000):
        assert mb.find_code_spans(line) == _oracle_code_spans(line), repr(line)


def test_table_cell_split_matches_the_quadratic_oracle():
    """
    [Unit] markdown blocks: verifies DS117 cell splitting equals the quadratic oracle on random soup.

    Scenario:
        Given several thousand seeded random lines of backtick/pipe/backslash soup
        When the current DS117 splitter and the kept quadratic oracle split each line
        Then the two produce identical logical cells for every line, proving the shared
        backtick-run index preserves the escape-aware splitting byte-for-byte.

    Boundaries:
        - Focus: byte-identical DS117 cell splitting after the matcher refactor
        - Fixtures/params: none (deterministic seeded corpus)

    On failure, first check:
        - Whether _split_logical_cells still layers backslash escapes over the shared index
        - The specific line printed in the assertion message
    """
    for line in _random_soup_lines(4_000):
        assert tables._split_logical_cells(line) == _oracle_split(line), repr(line)


def test_ds117_findings_match_the_oracle_splitter(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] markdown blocks: verifies DS117 findings are identical under the oracle splitter.

    Scenario:
        Given a document assembled from seeded random header/delimiter/body rows
        When DS117 recognition runs with the current splitter and then with the quadratic oracle
            splitter monkeypatched in
        Then the two produce identical findings, proving the matcher refactor changed no DS117
            diagnostic on realistic table-shaped soup.

    Boundaries:
        - Focus: end-to-end DS117 finding parity across the splitter swap
        - Fixtures/params: monkeypatch

    On failure, first check:
        - Whether _split_logical_cells diverged from the oracle on some row
        - Whether check_text consumes the splitter by module-global name
    """
    rows = _random_soup_lines(3_000, seed=99)
    # Assemble pseudo-tables: every third line is a delimiter-shaped row so many
    # header/delimiter/body triples form, exercising the finding path heavily.
    assembled = []
    for position, row in enumerate(rows):
        assembled.append("| a | b |" if position % 3 == 1 else row)
    text = "\n".join(assembled) + "\n"

    real = tables.check_text(text, "README.md", Config())
    monkeypatch.setattr(tables, "_split_logical_cells", _oracle_split)
    oracle = tables.check_text(text, "README.md", Config())

    assert real == oracle


def _increasing_backtick_line(target_bytes: int) -> str:
    """Return one line of unmatched backtick runs of strictly increasing length.

    ``x`x``x```x...`` has no two runs of the same length, so none ever closes -- the
    O(n^1.5) trap for a matcher that rescans the tail from every opener.

    :param target_bytes: Approximate target line length in characters.
    :returns: The adversarial line without a terminator.
    """
    parts: list[str] = []
    run_length = 1
    size = 0
    while size < target_bytes:
        parts.append("x")
        parts.append("`" * run_length)
        size += 1 + run_length
        run_length += 1
    return "".join(parts)


#: Inline-code consumers driven by the increasing-backtick regression. Each entry maps a
#: label to a probe that wraps the adversarial line in the smallest document that reaches
#: the consumer and returns its result; every result must be empty at every size (the line
#: holds no closing run, no pipes-in-a-table, no anchors and no fences), which is the exact,
#: non-vacuous assertion guarding against a vacuous pass.
_CONSUMERS: dict[str, Callable[[str], object]] = {
    "scanner_find_code_spans": lambda line: mb.find_code_spans(line),
    "scanner_scan_markdown": lambda line: mb.scan_markdown(line + "\n", "README.md").fences,
    "ds117_tables": lambda line: tables.check_text(line + "\n", "README.md", Config()),
    "ds106_sections": lambda line: sections.check_text(f"# T\n\n## S\n\n{line}\n", "README.md", Config()),
    "ds104_anchors": lambda line: anchors.check_text(f"# T\n\n{line}\n", "README.md", Config()),
    "ds110_fences": lambda line: fence_languages.check_text(
        f"# T\n\n{line}\n", "README.md", Config(require_fence_languages=True)
    ),
}


@pytest.mark.parametrize("consumer", sorted(_CONSUMERS))
def test_increasing_backtick_line_stays_linear(consumer: str):
    """
    [Unit] markdown blocks: verifies the increasing-backtick line stays linear across consumers.

    Scenario:
        Given one line of unmatched backtick runs of strictly increasing length at 8/16/32/64 KB
        When the scanner and each inline-code consumer (DS117, DS106, DS104, DS110) process it
        Then each consumer returns an empty result at every size (no closing run, table, anchor or
            fence exists, so the pass is never vacuous) and the shared timing bound holds, proving
            the shared backtick-run index closed the former O(n^1.5) rescan to linear.

    Boundaries:
        - Focus: the HIGH-severity complexity fix across every inline-code consumer
        - Fixtures/params: parametrized over every consumer; CPU time, best-of-N, floored baseline

    On failure, first check:
        - Whether a consumer reintroduced a tail rescan from every backtick opener
        - Whether the shared first_backtick_run_at_or_after lookup was bypassed
    """
    assert_scales_linearly(
        _increasing_backtick_line,
        _CONSUMERS[consumer],
        (8 * 1024, 16 * 1024, 32 * 1024, 64 * 1024),
        expected_count=0,
        label=consumer,
    )
