"""Detect empty or contentless Markdown sections (``DS106``).

This fast, standard-library-only analyzer reuses the shared Markdown block
scanner in :mod:`docsentinel.markdown_blocks` rather than re-parsing the
document. It reports headings whose section -- the span of lines between the
heading and the next heading (or end of file) -- carries no visible, publishable
content.

A section counts as having content when any of the following lies between the
heading and the next heading:

* visible non-whitespace prose with at least
  ``empty_section_min_text_chars`` + 1 characters (0 by default, so any visible
  text is enough);
* a non-empty fenced code block;
* a GFM pipe table; or
* an image, when ``image_content_counts`` is enabled (the default).

Blank lines, thematic breaks (``---``/``***``/``___``), empty fenced code
blocks, and -- under the default ``placeholder_content_policy = "ignore"`` --
HTML comments are *not* content. Setting ``placeholder_content_policy = "count"``
lets comments count as content. A lone HTML tag such as ``<a id="x"></a>`` or an
empty ``<span></span>`` renders nothing and is never content. Visible prose is
always content regardless of the policy: a word such as ``TODO`` is text a reader
sees, so DS106 never strips it; detecting such markers is DS119's territory, not
DS106's.

Section membership follows the configured ``empty_section_policy``. Under the
default ``"leaf"`` only sections with no child section are inspected, so a
structural parent that holds only nested subsections is never flagged; ``"all"``
inspects every section's direct body, and ``"off"`` disables the rule and emits
no findings. A trailing heading with no body before end of file is a finding, a
document with no headings is never a finding (an empty document is another
rule's concern), and a leading YAML frontmatter record is excluded so its
closing ``---`` is never mistaken for a setext heading that owns an empty body.

Heading-looking lines inside fenced code are already masked by the shared
scanner; this module additionally excludes heading tokens that fall inside a
multi-line HTML comment or the leading frontmatter block, matching DS105. Each
section's extent is computed in a single forward pass over the physical lines, and
every per-line construct (HTML comments, images, HTML tags) is stripped with a
forward-only cursor rather than a backtracking regex, so the whole analysis runs in
``O(headings + characters)``, never rescanning the token list per heading nor the
tail of a line per candidate opener.

The analyzer performs no network, subprocess, or symlink I/O and never executes
embedded code; it only reads the UTF-8 text of Markdown documents it is handed.

``DS106`` is registered in :data:`docsentinel.rules.RULES` and
:data:`docsentinel.rules.ANALYZERS` as an import side effect of this module, so
it runs as an exact ``fast``-profile rule. The Milestone 0005 fixture catalog is
registration gated: registration and engine wiring land together with the
committed ``tests/assets/ds106/*`` fixtures (Story 04.0 Task 02), never before
them.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import Heading, MarkdownBlockIndex, scan_markdown, split_physical_lines

#: Stable metadata for ``DS106``, registered as a ``fast``-profile rule alongside
#: its committed ``tests/assets/ds106/*`` fixtures (Story 04.0 Task 02).
DS106 = rules.register_rule(
    rules.Rule(
        code="DS106",
        profile="fast",
        title="Empty or contentless sections",
        description="A heading introduces a section with no visible, publishable content.",
        severity="warning",
    )
)

_FRONTMATTER_FENCE = "---"
_FRONTMATTER_CLOSERS = ("---", "...")

#: A thematic break line (``---``/``***``/``___`` with optional spaces), which the
#: shared scanner does not tokenize and which never counts as section content. The
#: pattern is anchored and its repeated group matches a dedicated delimiter char, so
#: it cannot backtrack catastrophically on a long run of ``-``/``*``/``_`` or spaces.
_THEMATIC_RE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
#: Maximum number of characters of a heading's text echoed into a finding message, so
#: a pathologically long heading cannot produce a pathologically long diagnostic.
_MAX_HEADING_ECHO = 80


def _is_ascii_letter(character: str) -> bool:
    """Return whether ``character`` is a single ASCII letter (``[A-Za-z]``).

    :param character: The one-character string to classify.
    :returns: ``True`` when the character is ``a``-``z`` or ``A``-``Z``.
    """
    return character.isascii() and character.isalpha()


def _strip_leading_comment_open(text: str) -> str:
    """Blank a ``<!--`` and everything after it on a comment-opening line.

    Linear replacement for ``re.sub(r"<!--.*$", " ", text)``: a single
    :meth:`str.find` locates the opener and the tail is dropped in one slice, so the
    work is proportional to the line length rather than quadratic in it.

    :param text: The physical line content without its terminator.
    :returns: The line with the opened comment tail replaced by one space.
    """
    index = text.find("<!--")
    if index == -1:
        return text
    return text[:index] + " "


def _strip_trailing_comment_close(text: str) -> str:
    """Blank the line head up to and including the first ``-->`` on a closing line.

    Linear replacement for ``re.sub(r"^.*?-->", " ", text)``.

    :param text: The physical line content without its terminator.
    :returns: The line with the closed comment head replaced by one space.
    """
    index = text.find("-->")
    if index == -1:
        return text
    return " " + text[index + 3 :]


def _strip_single_line_comments(text: str) -> str:
    """Blank each ``<!-- ... -->`` comment on a line with a single space.

    Linear replacement for ``re.sub(r"<!--.*?-->", " ", text)``. A forward cursor
    advances past each matched comment and, once a ``-->`` closer is absent for the
    current opener, abandons the line (no later opener can close either), so a flood
    of unterminated ``<!--`` costs ``O(characters)`` rather than ``O(characters^2)``.

    :param text: The physical line content without its terminator.
    :returns: The line with every closed single-line comment replaced by one space.
    """
    open_index = text.find("<!--")
    if open_index == -1:
        return text
    pieces: list[str] = []
    cursor = 0
    while open_index != -1:
        close_index = text.find("-->", open_index + 4)
        if close_index == -1:
            break
        pieces.append(text[cursor:open_index])
        pieces.append(" ")
        cursor = close_index + 3
        open_index = text.find("<!--", cursor)
    pieces.append(text[cursor:])
    return "".join(pieces)


def _strip_images(text: str) -> str:
    """Blank each ``![alt](target)`` image on a line with a single space.

    Linear replacement for ``re.sub(r"!\\[[^\\]]*\\]\\([^)]*\\)", " ", text)``. Closer
    searches for ``]`` and ``)`` use forward :meth:`str.find` scans and the pass
    abandons the line as soon as a required closer is missing, so a flood of ``![``
    with no closing bracket is ``O(characters)`` rather than ``O(characters^2)``.

    :param text: The physical line content without its terminator.
    :returns: The line with every complete image construct replaced by one space.
    """
    open_index = text.find("![")
    if open_index == -1:
        return text
    length = len(text)
    pieces: list[str] = []
    cursor = 0
    while open_index != -1:
        bracket = text.find("]", open_index + 2)
        if bracket == -1:
            break
        if bracket + 1 < length and text[bracket + 1] == "(":
            paren = text.find(")", bracket + 2)
            if paren == -1:
                break
            pieces.append(text[cursor:open_index])
            pieces.append(" ")
            cursor = paren + 1
            open_index = text.find("![", cursor)
        else:
            open_index = text.find("![", open_index + 1)
    pieces.append(text[cursor:])
    return "".join(pieces)


def _strip_html_tags(text: str) -> str:
    """Blank each ``<tag ...>`` HTML tag on a line with a single space.

    Linear replacement for ``re.sub(r"</?[A-Za-z][^>]*>", " ", text)``. The closing
    ``>`` is located with a forward :meth:`str.find`, and the pass stops once no
    ``>`` remains after a valid tag opener, so a flood of ``<`` or ``<a`` with no
    closing ``>`` is ``O(characters)`` rather than ``O(characters^2)``. HTML comments
    (``<!-- -->``) are deliberately not matched here.

    :param text: The physical line content without its terminator.
    :returns: The line with every complete HTML tag replaced by one space.
    """
    open_index = text.find("<")
    if open_index == -1:
        return text
    length = len(text)
    pieces: list[str] = []
    cursor = 0
    while open_index != -1:
        name_index = open_index + 1
        if name_index < length and text[name_index] == "/":
            name_index += 1
        if name_index < length and _is_ascii_letter(text[name_index]):
            close = text.find(">", name_index + 1)
            if close == -1:
                break
            pieces.append(text[cursor:open_index])
            pieces.append(" ")
            cursor = close + 1
            open_index = text.find("<", cursor)
        else:
            open_index = text.find("<", open_index + 1)
    pieces.append(text[cursor:])
    return "".join(pieces)


def _frontmatter_end_line(text: str) -> int:
    """Return the one-based last line of a leading YAML frontmatter block.

    A frontmatter block exists only when the very first physical line is exactly
    ``---`` and a later line is exactly ``---`` or ``...``. This mirrors DS105's
    boundary detection and, like it, splits on the scanner's line terminators
    (:func:`~docsentinel.markdown_blocks.split_physical_lines`) so the excluded
    range lines up with the scanned heading spans.

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


def _span_lines(start_line: int, end_line: int) -> range:
    """Return the inclusive one-based line range of a token span.

    :param start_line: One-based first line of the span.
    :param end_line: One-based last line of the span.
    :returns: The ``range`` of line numbers the span covers.
    """
    return range(start_line, end_line + 1)


@dataclass
class _LineMasks:
    """Per-line classification of a document, built in one linear pass per token kind.

    Every attribute is a set of one-based line numbers. The sets are populated by
    walking each token list once; because scanner spans of a given kind do not
    overlap, the total work is ``O(lines + tokens)`` rather than quadratic.

    :ivar heading_lines: Lines occupied by a kept (section) heading.
    :ivar fenced_lines: Lines inside any fenced code block, including delimiters.
    :ivar fence_content_lines: Lines inside a non-empty fenced code block.
    :ivar comment_open_lines: Start lines of multi-line comments.
    :ivar comment_close_lines: End lines of multi-line comments.
    :ivar comment_interior_lines: Lines wholly inside a multi-line comment body.
    :ivar table_lines: Lines belonging to a GFM pipe table.
    :ivar image_lines: Lines carrying an image (only populated when images count).
    """

    heading_lines: set[int] = field(default_factory=set)
    fenced_lines: set[int] = field(default_factory=set)
    fence_content_lines: set[int] = field(default_factory=set)
    comment_open_lines: set[int] = field(default_factory=set)
    comment_close_lines: set[int] = field(default_factory=set)
    comment_interior_lines: set[int] = field(default_factory=set)
    table_lines: set[int] = field(default_factory=set)
    image_lines: set[int] = field(default_factory=set)


def _build_masks(index: MarkdownBlockIndex, headings: tuple[Heading, ...], image_content_counts: bool) -> _LineMasks:
    """Return per-line masks for a document from its scanned tokens.

    :param index: The scanned Markdown block index.
    :param headings: The kept section headings (frontmatter/comment headings removed).
    :param image_content_counts: Whether images should be recorded as content.
    :returns: The populated :class:`_LineMasks`.
    """
    masks = _LineMasks()
    for heading in headings:
        masks.heading_lines.update(_span_lines(heading.span.start_line, heading.span.end_line))
    for fence in index.fences:
        span_lines = _span_lines(fence.span.start_line, fence.span.end_line)
        masks.fenced_lines.update(span_lines)
        if fence.body_nonempty:
            masks.fence_content_lines.update(span_lines)
    for comment in index.comments:
        start, end = comment.span.start_line, comment.span.end_line
        if end > start:
            masks.comment_open_lines.add(start)
            masks.comment_close_lines.add(end)
            masks.comment_interior_lines.update(range(start + 1, end))
    for row in index.table_rows:
        masks.table_lines.add(row.span.start_line)
    if image_content_counts:
        for image in index.images:
            masks.image_lines.add(image.span.start_line)
    return masks


def _active_headings(index: MarkdownBlockIndex, text: str) -> tuple[Heading, ...]:
    """Return heading tokens that bound real sections, in source order.

    Headings whose start line lies inside a multi-line HTML comment or the
    leading YAML frontmatter block are dropped: the shared scanner still emits
    such heading-looking lines (it masks fenced code but not comments), and a
    frontmatter record's closing ``---`` can otherwise be read as a setext
    heading that owns a spurious empty body.

    :param index: The scanned Markdown block index.
    :param text: The Markdown source text exactly as read.
    :returns: The section headings in source order.
    """
    excluded: set[int] = set()
    for comment in index.comments:
        excluded.update(_span_lines(comment.span.start_line, comment.span.end_line))
    frontmatter_end = _frontmatter_end_line(text)
    if frontmatter_end:
        excluded.update(range(1, frontmatter_end + 1))
    return tuple(heading for heading in index.headings if heading.span.start_line not in excluded)


def _checked_indices(headings: tuple[Heading, ...], policy: str) -> tuple[int, ...]:
    """Return the indices of headings whose sections are inspected, in source order.

    Under ``"leaf"`` only sections with no child section are inspected: a heading
    is a leaf when the next heading in source order is not deeper than it, or when
    it is the last heading. Under ``"all"`` every section is inspected.

    :param headings: The section headings in source order.
    :param policy: The ``empty_section_policy`` value (``"leaf"`` or ``"all"``).
    :returns: The inspected heading indices in ascending order.
    """
    if policy == "all":
        return tuple(range(len(headings)))
    last = len(headings) - 1
    return tuple(
        index for index in range(len(headings)) if index == last or headings[index + 1].level <= headings[index].level
    )


def _visible_text(line: str, line_number: int, masks: _LineMasks, count_placeholders: bool) -> str:
    """Return the publishable text of a line with non-content constructs removed.

    Images and basic HTML tags are always stripped so an image-only or bare-tag
    line contributes no prose. Under the ``ignore`` placeholder policy, HTML
    comments are stripped too; under ``count`` they are kept so their text
    registers as content. Visible prose is never stripped: a word such as
    ``TODO`` is text a reader sees and always counts as content (marker detection
    is DS119's territory, not DS106's).

    :param line: The physical line content without its terminator.
    :param line_number: The one-based line number, used for comment-span lookups.
    :param masks: The per-line masks for the document.
    :param count_placeholders: Whether HTML comments count as content.
    :returns: The line reduced to its publishable text.
    """
    text = line
    if not count_placeholders:
        if line_number in masks.comment_interior_lines:
            return ""
        if line_number in masks.comment_open_lines:
            text = _strip_leading_comment_open(text)
        if line_number in masks.comment_close_lines:
            text = _strip_trailing_comment_close(text)
        text = _strip_single_line_comments(text)
    text = _strip_images(text)
    text = _strip_html_tags(text)
    return text


def _section_content(
    lines: list[str],
    headings: tuple[Heading, ...],
    masks: _LineMasks,
    settings: Config,
) -> tuple[list[bool], list[int]]:
    """Return per-section block-content flags and visible text-character counts.

    This is the single forward pass promised by the algorithm: it walks the
    physical lines once, advancing a heading pointer so each line is attributed to
    its owning section without rescanning tokens or re-slicing text per heading.
    Lines before the first heading (preamble/frontmatter) belong to no section and
    are ignored.

    :param lines: The physical line contents in order (index ``i`` is line ``i+1``).
    :param headings: The section headings in source order.
    :param masks: The per-line masks for the document.
    :param settings: Effective settings.
    :returns: A ``(has_block, text_chars)`` pair, each indexed by heading.
    """
    count = len(headings)
    has_block = [False] * count
    text_chars = [0] * count
    count_placeholders = settings.placeholder_content_policy == "count"
    pointer = 0
    current = -1

    for line_number in range(1, len(lines) + 1):
        if pointer < count and headings[pointer].span.start_line == line_number:
            current = pointer
            pointer += 1
        if line_number in masks.heading_lines or current < 0:
            continue
        if line_number in masks.fence_content_lines:
            has_block[current] = True
            continue
        if line_number in masks.fenced_lines:
            continue
        if line_number in masks.table_lines or line_number in masks.image_lines:
            has_block[current] = True
            continue
        content = lines[line_number - 1]
        if not content.strip() or _THEMATIC_RE.match(content):
            continue
        visible = _visible_text(content, line_number, masks, count_placeholders)
        text_chars[current] += sum(1 for character in visible if not character.isspace())

    return has_block, text_chars


def _finding(path: str, heading: Heading) -> models.Finding:
    """Return a ``DS106`` finding for an empty section at its heading line.

    The heading text echoed into the message is bounded to :data:`_MAX_HEADING_ECHO`
    characters (plus an ellipsis marker) so a pathologically long heading cannot
    produce a pathologically long, unbounded diagnostic. The ``!r`` conversion is
    retained so control characters in the heading render as safe escapes.

    :param path: POSIX-style relative document path.
    :param heading: The heading that introduces the empty section.
    :returns: A :class:`~docsentinel.models.Finding`.
    """
    echoed = heading.text
    if len(echoed) > _MAX_HEADING_ECHO:
        echoed = echoed[:_MAX_HEADING_ECHO] + "..."
    message = f"empty section: {echoed!r} has no visible content"
    return models.Finding(
        rule=DS106.code,
        path=path,
        message=message,
        severity=DS106.severity,
        line=heading.span.start_line,
    )


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS106`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline source
    strings; :func:`detect` layers document reading over it. When
    ``empty_section_policy`` is ``"off"`` no findings are produced, and a document
    with no section headings never yields a finding.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source (ascending line) order, one per empty section.
    """
    settings = config if config is not None else Config()
    if settings.empty_section_policy == "off":
        return ()
    index = scan_markdown(text, path)
    headings = _active_headings(index, text)
    if not headings:
        return ()
    lines = split_physical_lines(text)
    masks = _build_masks(index, headings, settings.image_content_counts)
    has_block, text_chars = _section_content(lines, headings, masks, settings)
    minimum = settings.empty_section_min_text_chars
    findings = [
        _finding(path, headings[index_])
        for index_ in _checked_indices(headings, settings.empty_section_policy)
        if not has_block[index_] and text_chars[index_] <= minimum
    ]
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
    """Return ``DS106`` findings for Markdown documents in their supplied order.

    Each document is evaluated independently and a reported line always belongs to
    the empty section's own heading.

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


rules.ANALYZERS[DS106.code] = detect
