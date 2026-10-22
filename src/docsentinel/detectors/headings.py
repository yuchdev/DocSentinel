"""Validate heading hierarchy and section levels (``DS105``).

This fast, standard-library-only analyzer reuses the shared Markdown block
scanner in :mod:`docsentinel.markdown_blocks` rather than re-parsing headings. It
reports two heading-hierarchy problems, both governed by project-local config:

* the **first** heading is deeper than the configured ``first_heading_level``
  (the document opens by skipping one or more levels); and
* a later heading **skips** a level, jumping more than one level deeper than the
  preceding actual heading.

Headings inside fenced code are already excluded by the shared scanner; this
module additionally excludes headings that fall inside multi-line HTML comments
and inside a leading YAML frontmatter block, so heading-looking text there never
affects the hierarchy. Blockquoted (``> ###``) and inline (``C#``) hashes are not
heading tokens in the supported dialect, so they are naturally ignored.

Multiple top-level (H1) headings are permitted by default. When
``multiple_h1_policy = "warn"`` each H1 after the first is reported; this check
is independent of ``heading_level_policy``. When ``heading_level_policy = "off"``
the first-heading and skip checks are suppressed. When
``setext_heading_support = false`` setext headings do not participate in the
hierarchy at all.

The analyzer performs no network, subprocess, or symlink I/O and never executes
embedded code; it only reads the UTF-8 text of Markdown documents it is handed.

``DS105`` is registered in :data:`docsentinel.rules.RULES` and
:data:`docsentinel.rules.ANALYZERS` as an import side effect of this module, so
it runs as an exact ``fast``-profile rule. The Milestone 0005 fixture catalog is
registration gated: registration and engine wiring land together with the
committed ``tests/assets/ds105/*`` fixtures (Task 02), never before them.
"""

from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import Heading, MarkdownBlockIndex, scan_markdown, split_physical_lines

#: Stable metadata for ``DS105``, registered as a ``fast``-profile rule alongside
#: its committed ``tests/assets/ds105/*`` fixtures (Task 02).
DS105 = rules.register_rule(
    rules.Rule(
        code="DS105",
        profile="fast",
        title="Heading hierarchy and section levels",
        description="A heading skips a level or the first heading is deeper than the configured root level.",
        severity="warning",
    )
)

_FRONTMATTER_FENCE = "---"
_FRONTMATTER_CLOSERS = ("---", "...")


def _frontmatter_end_line(text: str) -> int:
    """Return the one-based last line of a leading YAML frontmatter block.

    A frontmatter block exists only when the very first physical line is exactly
    ``---`` and a later line is exactly ``---`` or ``...``. The scanner does not
    model frontmatter, and its closing ``---`` is otherwise mistaken for a setext
    underline, so this boundary lets the detector exclude that region.

    The boundary is derived with the scanner's line splitter
    (:func:`~docsentinel.markdown_blocks.split_physical_lines`) rather than
    :meth:`str.splitlines`; the latter also breaks on ``\\v``, ``\\f``, and other
    Unicode separators the scanner ignores, which would renumber lines and
    misalign the excluded range against the scanned heading spans.

    :param text: The Markdown source text exactly as read.
    :returns: The one-based line number of the closing delimiter, or ``0`` when
        the document has no closed leading frontmatter block.
    """
    lines = split_physical_lines(text)
    if not lines or lines[0].strip() != _FRONTMATTER_FENCE:
        return 0
    for number, content in enumerate(lines[1:], start=2):
        if content.strip() in _FRONTMATTER_CLOSERS:
            return number
    return 0


def _excluded_lines(index: MarkdownBlockIndex, text: str) -> frozenset[int]:
    """Return one-based lines whose headings must be ignored.

    This covers multi-line HTML comments (whose inner heading-looking lines the
    shared scanner still tokenizes) and a leading YAML frontmatter block. Fenced
    code is already masked by the scanner and needs no entry here.

    :param index: A scanned Markdown block index.
    :param text: The Markdown source text exactly as read.
    :returns: The set of one-based line numbers to skip.
    """
    excluded: set[int] = set()
    for comment in index.comments:
        excluded.update(range(comment.span.start_line, comment.span.end_line + 1))
    frontmatter_end = _frontmatter_end_line(text)
    if frontmatter_end:
        excluded.update(range(1, frontmatter_end + 1))
    return frozenset(excluded)


def _active_headings(index: MarkdownBlockIndex, text: str, settings: Config) -> tuple[Heading, ...]:
    """Return headings that participate in hierarchy evaluation, in source order.

    Headings inside excluded regions are dropped, and setext headings are dropped
    when ``setext_heading_support`` is disabled.

    :param index: A scanned Markdown block index.
    :param text: The Markdown source text exactly as read.
    :param settings: Effective settings.
    :returns: The participating headings.
    """
    excluded = _excluded_lines(index, text)
    return tuple(
        heading
        for heading in index.headings
        if heading.span.start_line not in excluded and (settings.setext_heading_support or heading.style != "setext")
    )


def _finding(path: str, line: int, message: str) -> models.Finding:
    """Return a ``DS105`` finding at the offending heading line.

    :param path: POSIX-style relative document path.
    :param line: One-based line of the offending heading.
    :param message: Smallest meaningful diagnostic message.
    :returns: A :class:`~docsentinel.models.Finding`.
    """
    return models.Finding(rule=DS105.code, path=path, message=message, severity=DS105.severity, line=line)


def _heading_findings(headings: tuple[Heading, ...], path: str, settings: Config) -> list[models.Finding]:
    """Return ``DS105`` findings for participating headings in source order.

    The first heading is flagged when it is deeper than ``first_heading_level``;
    a later heading is flagged when it is more than one level deeper than the
    preceding actual heading. Reducing (raising) the level is always allowed.
    Repeated H1 headings are flagged only under ``multiple_h1_policy = "warn"``,
    independently of ``heading_level_policy``.

    :param headings: Participating headings in source order.
    :param path: POSIX-style relative document path.
    :param settings: Effective settings.
    :returns: Findings in source order, at most one per heading.
    """
    findings: list[models.Finding] = []
    check_levels = settings.heading_level_policy == "no-skips"
    warn_multiple_h1 = settings.multiple_h1_policy == "warn"
    previous_level: Optional[int] = None
    seen_h1 = False

    for heading in headings:
        line = heading.span.start_line
        if heading.level == 1:
            if seen_h1 and warn_multiple_h1:
                findings.append(_finding(path, line, "additional top-level (H1) heading is not permitted here"))
            seen_h1 = True
        if check_levels:
            if previous_level is None:
                if heading.level > settings.first_heading_level:
                    findings.append(
                        _finding(
                            path,
                            line,
                            f"first heading is level {heading.level}; "
                            f"document should begin at level {settings.first_heading_level}",
                        )
                    )
            elif heading.level > previous_level + 1:
                findings.append(
                    _finding(
                        path,
                        line,
                        f"heading level {heading.level} skips a level after level {previous_level}",
                    )
                )
            previous_level = heading.level
    return findings


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS105`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline
    source strings; :func:`detect` layers document reading over it.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source order, at most one per offending heading.
    """
    settings = config if config is not None else Config()
    index = scan_markdown(text, path)
    headings = _active_headings(index, text, settings)
    return tuple(_heading_findings(headings, path, settings))


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
    """Return ``DS105`` findings for Markdown documents in their supplied order.

    Each document is evaluated independently; a reported line always belongs to
    the offending heading, never its predecessor.

    :param root: The resolved scan root directory.
    :param documents: Discovered documents to inspect, in scan order.
    :param config: Effective settings; the engine passes this for configured
        policy handling, and direct callers may omit it to use defaults.
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


rules.ANALYZERS[DS105.code] = detect
