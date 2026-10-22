"""Detect malformed GFM pipe-table structure (``DS117``).

This fast, standard-library-only analyzer recognizes GitHub-style pipe tables and
reports the ones whose structure is inconsistent. A table exists only when a
header row is **immediately** followed by a valid GFM delimiter row (cells made of
optional colons around a dash run); a run of prose with pipes but no delimiter row
underneath is never treated as a table, and neither is a table-looking block inside
a fenced code region. A table-shaped line that opens a block construct this subset
does not parse -- a four-space-indented code block, a block quote (``>``), or a
bullet (``-``/``*``/``+``) or ordered (``1.``/``1)``) list item -- is likewise left
as a non-table rather than guessed at, so no finding is emitted for it.

Once a table is recognized the analyzer reports, under the strict cell policy
(``table_strict_cells``, the default), rows whose logical cell count differs from
the header's -- a short or long delimiter row at the delimiter line, a short or long
body row at that body line -- plus malformed alignment markers in the delimiter row
regardless of the strict policy. Exactly one finding is emitted per offending row,
at that row's one-based source line, and multiple tables in one document are
reported in stable source order. There is no corpus-wide or per-document cap on the
number of findings (a corpus-level cap is planned for Story 15.0); every offending
row in every table is reported.

Cell boundaries are found with a single hand-rolled linear pass that honors the
narrow GFM subset the shared scanner documents: a backslash escapes the next
character so ``\\|`` stays inside a cell, a backtick code span (any run length, and
an unmatched run that never closes) protects the pipes inside it, leading and
trailing border pipes are optional, an explicit empty cell between separators still
counts, and trailing whitespace and ``CRLF``/``CR`` terminators are tolerated. The
analysis runs in time proportional to the source length even for pathologically long
lines: the document is scanned and split once, each physical line is split into cells
at most twice (once as a possible header, once as the following line's delimiter
probe), and no per-table rescan of the token list or re-split of lines ever occurs.

The analyzer reuses the shared block scanner in
:mod:`docsentinel.markdown_blocks` for its fence mask (so table-looking lines inside
a code fence are ignored) and for the shared backtick-run index
(:func:`~docsentinel.markdown_blocks.backtick_runs_by_length` and
:func:`~docsentinel.markdown_blocks.first_backtick_run_at_or_after`), which closes a
code span in logarithmic time rather than rescanning the rest of the line from every
opener -- the same amortised-linear matcher the scanner's own inline-code finder
uses, so a line of unmatched backtick runs of strictly increasing length cannot
cause quadratic blow-up. It still derives cell boundaries itself (layering backslash
escapes over that shared index) because the scanner's own ``TableRow`` tokens neither
protect pipes inside code spans nor retain a delimiter row whose alignment markers
are malformed, both of which ``DS117`` must reason about. Extending the shared
scanner for those two needs would change its ``table_rows`` output and could perturb
``DS106``'s content model, so the shared token behavior is left byte-identical.

The analyzer performs no network, subprocess, or symlink I/O and never executes
embedded code; it only reads the UTF-8 text of Markdown documents it is handed. It
emits nothing when ``table_enable`` is false or when ``table_dialect`` names an
unsupported dialect, so a disabled or inapplicable policy never masquerades as an
evaluated clean result.

``DS117`` is an always-active ``fast``-profile rule: it registers its
:class:`~docsentinel.rules.Rule` and ``ANALYZERS`` entry as an import side effect of
this module, alongside its committed ``tests/assets/ds117/*`` fixtures (Story 08.0
Task 02). It carries no ``opt_in_option``, so it is evaluated by default.
"""

import re
from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import (
    MarkdownBlockIndex,
    backtick_runs_by_length,
    first_backtick_run_at_or_after,
    scan_markdown,
    split_physical_lines,
)

#: Stable metadata for ``DS117``, registered as an always-active ``fast``-profile
#: rule alongside its committed ``tests/assets/ds117/*`` fixtures (Story 08.0 Task 02).
DS117 = rules.register_rule(
    rules.Rule(
        code="DS117",
        profile="fast",
        title="Malformed GFM pipe-table structure",
        description="A pipe table has inconsistent cell counts or malformed alignment markers.",
        severity="warning",
    )
)

#: The only pipe-table dialect this detector can validate; any other value yields no
#: confident diagnostics, mirroring ``DS109``/``DS110``'s dialect guard.
_SUPPORTED_DIALECT = "gfm-subset"
#: Maximum characters of a delimiter-row snippet echoed into a message, so a
#: pathologically long row cannot produce a pathologically long diagnostic.
_MAX_SNIPPET_ECHO = 80
#: A valid GFM alignment marker: optional leading colon, a dash run, optional
#: trailing colon. The dash run is a single greedy character class, so it cannot
#: backtrack catastrophically on a long run of dashes.
_VALID_MARKER_RE = re.compile(r"^:?-+:?$")


def _split_logical_cells(content: str) -> tuple[str, ...]:
    """Split a table row into trimmed logical cells in one linear pass.

    A backslash escapes the next character (so ``\\|`` does not split a cell), a
    backtick code span of any run length protects the pipes inside it (an unmatched
    run is treated as literal backticks), and leading and trailing empty border cells
    from optional outer pipes are dropped. An explicit empty cell between two
    separators is preserved so it still counts toward the cell total.

    Code-span closers are located through the shared backtick-run index in
    :mod:`docsentinel.markdown_blocks` (a logarithmic lookup per opener) rather than
    by rescanning the rest of the line from every opener, so a line of unmatched
    backtick runs of strictly increasing length cannot cause quadratic blow-up.

    :param content: One physical table-row line without its terminator.
    :returns: The trimmed cells in column order.
    """
    by_length = backtick_runs_by_length(content)
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
            close_start = first_backtick_run_at_or_after(by_length, run, run_end)
            end = run_end if close_start == -1 else close_start + run
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


#: An ordered-list marker (``1.`` or ``1)``) at the start of a line's content, up to
#: nine digits per the GFM subset, followed by a space.
_ORDERED_LIST_RE = re.compile(r"\d{1,9}[.)] ")


def _is_block_prefixed(line: str) -> bool:
    """Return whether a line belongs to a block construct this detector does not parse.

    A line indented four or more spaces (an indented code block), or whose first
    non-space content opens a block quote (``>``) or a bullet (``-``/``*``/``+``) or
    ordered (``1.``/``1)``) list item, is not treated as a pipe-table row. Per the
    spec these unsupported constructs are left as non-tables rather than guessed at,
    so a table-shaped line inside a list item or block quote yields no finding.

    :param line: One physical line without its terminator.
    :returns: ``True`` when the line opens such a block construct.
    """
    column = 0
    for char in line:
        if char == " ":
            column += 1
        elif char == "\t":
            # A tab advances to the next multiple-of-four column, as in CommonMark.
            column += 4 - column % 4
        else:
            break
        if column >= 4:
            return True
    stripped = line.lstrip(" \t")
    if stripped.startswith(">"):
        return True
    if stripped[:2] in ("- ", "* ", "+ "):
        return True
    return bool(_ORDERED_LIST_RE.match(stripped))


def _is_delimiter_candidate(cells: tuple[str, ...]) -> bool:
    """Return whether a row's cells look like an attempted GFM delimiter row.

    A delimiter candidate has at least one cell, every cell is non-empty and composed
    solely of ``:`` and ``-`` characters, and at least one cell carries a dash. This
    recognizes both well-formed delimiter rows and ones with malformed alignment
    markers (for example ``:-:-``), so the detector can diagnose the malformed form
    rather than silently refusing to treat the block as a table.

    :param cells: The trimmed logical cells of a candidate delimiter row.
    :returns: ``True`` when the row is a delimiter attempt.
    """
    if not cells:
        return False
    saw_dash = False
    for cell in cells:
        if not cell:
            return False
        for character in cell:
            if character not in "-:":
                return False
        if "-" in cell:
            saw_dash = True
    return saw_dash


def _has_malformed_marker(cells: tuple[str, ...]) -> bool:
    """Return whether any delimiter-candidate cell is not a valid alignment marker.

    :param cells: The trimmed cells of a recognized delimiter row.
    :returns: ``True`` when at least one cell fails the supported marker subset.
    """
    return any(not _VALID_MARKER_RE.match(cell) for cell in cells)


def _fenced_lines(index: MarkdownBlockIndex, line_count: int) -> list[bool]:
    """Return a per-line flag of whether each physical line lies inside a fence.

    Fence spans do not overlap, so the total work is proportional to the document
    length even when a single unclosed fence swallows the tail of the file.

    :param index: The scanned Markdown block index.
    :param line_count: Number of physical lines in the document.
    :returns: A list indexed by zero-based line, ``True`` when fenced.
    """
    flags = [False] * line_count
    for fence in index.fences:
        for line in range(fence.span.start_line, fence.span.end_line + 1):
            if 1 <= line <= line_count:
                flags[line - 1] = True
    return flags


def _snippet(cells: tuple[str, ...]) -> str:
    """Return a bounded, repr-safe echo of a delimiter row for a message.

    :param cells: The trimmed cells of the offending delimiter row.
    :returns: The joined cells truncated to :data:`_MAX_SNIPPET_ECHO` characters,
        with a trailing marker when truncated.
    """
    joined = " | ".join(cells)
    if len(joined) > _MAX_SNIPPET_ECHO:
        joined = joined[:_MAX_SNIPPET_ECHO] + "..."
    return joined


def _finding(path: str, line: int, message: str) -> models.Finding:
    """Return a ``DS117`` finding at an offending row's one-based line.

    :param path: POSIX-style relative document path.
    :param line: One-based source line of the offending row.
    :param message: Smallest meaningful diagnostic message.
    :returns: A :class:`~docsentinel.models.Finding`.
    """
    return models.Finding(rule=DS117.code, path=path, message=message, severity=DS117.severity, line=line)


def _row_finding(
    path: str,
    line: int,
    cells: tuple[str, ...],
    expected: int,
    kind: str,
    strict: bool,
    check_markers: bool,
) -> Optional[models.Finding]:
    """Return the single ``DS117`` finding a row warrants, or ``None`` when clean.

    A malformed alignment marker takes precedence over a cell-count mismatch so a
    delimiter row never produces two findings; cell-count mismatches are gated by the
    strict policy while a malformed marker is always structural.

    :param path: POSIX-style relative document path.
    :param line: One-based source line of the row.
    :param cells: The trimmed logical cells of the row.
    :param expected: The header's authoritative cell count.
    :param kind: ``"delimiter"`` or ``"body"``, named in the message.
    :param strict: Whether cell-count consistency is enforced.
    :param check_markers: Whether malformed alignment markers are checked (delimiter row).
    :returns: A :class:`~docsentinel.models.Finding` or ``None``.
    """
    if check_markers and _has_malformed_marker(cells):
        return _finding(path, line, f"table delimiter row has a malformed alignment marker: {_snippet(cells)!r}")
    if strict and len(cells) != expected:
        return _finding(
            path,
            line,
            f"table {kind} row has {_count_cells(len(cells))}; the header declares {expected}",
        )
    return None


def _count_cells(count: int) -> str:
    """Return a grammatical ``"N cell"``/``"N cells"`` phrase for a cell count.

    :param count: A logical cell count.
    :returns: ``"1 cell"`` for one, otherwise ``"N cells"``.
    """
    return "1 cell" if count == 1 else f"{count} cells"


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS117`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline source
    strings; :func:`detect` layers document reading over it. No findings are produced
    when ``table_enable`` is false or when ``table_dialect`` is not the supported
    ``gfm-subset``, so a disabled or inapplicable policy never implies an evaluated
    clean result.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source (ascending line) order, one per offending row.
    """
    settings = config if config is not None else Config()
    if not settings.table_enable or settings.table_dialect != _SUPPORTED_DIALECT:
        return ()
    index = scan_markdown(text, path)
    lines = split_physical_lines(text)
    count = len(lines)
    fenced = _fenced_lines(index, count)
    strict = settings.table_strict_cells
    findings: list[models.Finding] = []

    line_index = 0
    while line_index < count:
        if fenced[line_index] or "|" not in lines[line_index] or _is_block_prefixed(lines[line_index]):
            line_index += 1
            continue
        header_cells = _split_logical_cells(lines[line_index])
        delimiter_index = line_index + 1
        if (
            _is_delimiter_candidate(header_cells)
            or delimiter_index >= count
            or fenced[delimiter_index]
            or "|" not in lines[delimiter_index]
            or _is_block_prefixed(lines[delimiter_index])
        ):
            line_index += 1
            continue
        delimiter_cells = _split_logical_cells(lines[delimiter_index])
        if not _is_delimiter_candidate(delimiter_cells):
            line_index += 1
            continue

        expected = len(header_cells)
        delimiter_finding = _row_finding(
            path, delimiter_index + 1, delimiter_cells, expected, "delimiter", strict, check_markers=True
        )
        if delimiter_finding is not None:
            findings.append(delimiter_finding)

        body_index = delimiter_index + 1
        while (
            body_index < count
            and not fenced[body_index]
            and lines[body_index].strip()
            and "|" in lines[body_index]
            and not _is_block_prefixed(lines[body_index])
        ):
            body_finding = _row_finding(
                path,
                body_index + 1,
                _split_logical_cells(lines[body_index]),
                expected,
                "body",
                strict,
                check_markers=False,
            )
            if body_finding is not None:
                findings.append(body_finding)
            body_index += 1
        line_index = body_index

    return tuple(findings)


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a path.

    :param path: Absolute path to the Markdown document.
    :returns: The decoded document text.
    """
    with path.open(encoding="utf-8") as stream:
        return stream.read()


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS117`` findings for Markdown documents in their supplied order.

    Each document is evaluated independently and a reported line always belongs to the
    offending row's own source line. The engine wiring that calls this lands with the
    committed fixtures in Story 08.0 Task 02; it is defined here so that task can wire
    it without reshaping the detector.

    :param root: The resolved scan root directory.
    :param documents: Discovered documents to inspect, in scan order.
    :param config: Effective settings; the engine passes this for configured policy
        handling, and direct callers may omit it to use defaults.
    :returns: Findings across all documents in document then source order.
    """
    settings = config if config is not None else Config()
    findings: list[models.Finding] = []
    for document in documents:
        if not document.path.endswith(".md"):
            continue
        text = _read_text(root / document.path)
        findings.extend(check_text(text, document.path, settings))
    return tuple(findings)


rules.ANALYZERS[DS117.code] = detect
