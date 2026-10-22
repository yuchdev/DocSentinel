"""Detect reference-style link definition integrity problems (``DS108``).

This fast, standard-library-only analyzer reuses the shared Markdown block
scanner in :mod:`docsentinel.markdown_blocks` for its fence, HTML-comment, and
inline-code masks, then derives its own escape-aware view of reference-style
links and definitions over the masked text. It is a deterministic *identity*
check: it reasons about reference labels and definitions, never about whether a
resolved target exists on disk (that is DS101's and DS113's concern).

Three use shapes are recognized, matching the supported Markdown subset:

* a **full** reference ``[text][label]`` (the label is the second bracket);
* a **collapsed** reference ``[label][]`` (the label is the first bracket); and
* a **shortcut** reference ``[label]`` -- a single bracket pair that is **only**
  a link when ``label`` is defined. A shortcut whose label has no definition is
  ordinary prose, so it is never reported as a broken reference; it merely counts
  as a use of its definition when one exists.

Image references (``![text][label]`` and friends) are treated exactly like their
link counterparts. The three findings this rule emits are:

* an **undefined reference** -- one finding per *full* or *collapsed* use whose
  normalized label has no definition, at the use's one-based line;
* a **duplicate definition** -- each definition after the first for a normalized
  label, at the duplicate's line, gated by ``duplicate_reference_definitions``
  (``"off"`` suppresses it, ``"warn"`` reports at ``warning``, ``"error"`` at
  ``error``); and
* an **unused definition** -- a defined label that is never referenced, at its
  first definition's line, emitted only when ``unused_reference_definitions`` is
  enabled (off by default for backward compatibility).

Labels are normalized with the shared
:func:`~docsentinel.markdown_blocks.normalize_label` (CommonMark: NFC, whitespace
collapsed, Unicode case-folded), so references that differ only by case or
whitespace resolve to the same definition. Only the ``"commonmark"``
``reference_label_normalization`` dialect is modelled; any other value yields no
confident diagnostics.

False-positive safeguards, all honoured by scanning the masked text:

* reference-looking material inside fenced code, inline code, or HTML comments is
  blanked before scanning, so it is never recognized;
* escaped brackets (``\\[`` / ``\\]``) are skipped, so escaped reference syntax is
  literal text;
* footnotes (``[^note]`` and ``[^note]: ...``) are not ordinary link references;
* a reference-definition line is not also scanned for uses, so its own
  ``[label]`` is never mistaken for a shortcut use of itself; and
* an inline link ``[text](target)`` is not a reference, so its bracket pair is
  skipped.

Responsibility boundary: DS101 resolves inline-link *targets* after reference
expansion; DS108 owns reference *identifiers* and *definitions*. DS101 never
reports a merely undefined label (its matcher only sees inline ``[text](target)``
links), so the two rules do not double-report.

Every per-line scan is a single forward pass that advances a cursor past each
construct it consumes, so the whole analysis runs in time proportional to the
source length even on adversarial bracket floods; it never rescans a line tail
from each ``[``. The analyzer performs no network, subprocess, or symlink I/O and
never executes embedded code; it only reads the UTF-8 text of Markdown documents
it is handed.

``DS108`` is registered in :data:`docsentinel.rules.RULES` and
:data:`docsentinel.rules.ANALYZERS` as an import side effect of this module, so it
runs as an exact ``fast``-profile rule. The Milestone 0005 fixture catalog is
registration gated: registration and engine wiring land together with the
committed ``tests/assets/ds108/*`` fixtures (Story 05.0 Task 02), never before
them.
"""

import re
from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import MarkdownBlockIndex, normalize_label, scan_markdown, split_physical_lines

#: Stable metadata for ``DS108``, registered as a ``fast``-profile rule alongside
#: its committed ``tests/assets/ds108/*`` fixtures (Story 05.0 Task 02).
DS108 = rules.register_rule(
    rules.Rule(
        code="DS108",
        profile="fast",
        title="Reference-style link definition integrity",
        description="A reference-style link uses an undefined label or a label is defined more than once.",
        severity="warning",
    )
)

#: Line-initial reference definition (``[label]: target``), allowing up to three
#: spaces of indentation and leading block-quote markers, matching the shared
#: scanner's own definition recognition. The label is group 1.
_REF_DEF_RE = re.compile(r"^ {0,3}(?:>\s?)*\[((?:\\.|[^\]\\])+)\]:\s*\S")

#: Maximum characters of the author's raw label echoed into a finding message, so a
#: pathologically long label cannot produce a pathologically long diagnostic.
_MAX_ECHO = 80

#: Use-shape tags produced by :func:`_scan_uses`.
_FULL = "full"
_COLLAPSED = "collapsed"
_SHORTCUT = "shortcut"


def _echo(raw_label: str) -> str:
    """Return a bounded, escaped echo of the author's raw reference label.

    The label is bounded to :data:`_MAX_ECHO` characters, then escaped with
    ``unicode_escape`` so control bytes, ``ESC`` sequences, and non-ASCII bytes
    render as printable ``\\xNN``/``\\uNNNN`` forms before the string reaches any
    report sink, mirroring the bounded echo used by ``DS116``.

    :param raw_label: The reference label exactly as written.
    :returns: The bounded, escaped echo with a trailing ``...`` when truncated.
    """
    bounded = raw_label[:_MAX_ECHO]
    escaped = bounded.encode("unicode_escape").decode("ascii")
    return f"{escaped}..." if len(raw_label) > _MAX_ECHO else escaped


def _is_footnote(raw_label: str) -> bool:
    """Return whether a label is a footnote marker rather than a link reference.

    A footnote label (``[^note]``) is not an ordinary reference-style link, so
    DS108 ignores it in both use and definition positions.

    :param raw_label: The reference label exactly as written.
    :returns: ``True`` when the stripped label begins with ``^``.
    """
    return raw_label.lstrip().startswith("^")


def _masked_lines(text: str, index: MarkdownBlockIndex) -> list[str]:
    """Return physical lines with fenced, comment, and inline-code spans blanked.

    Every character inside a fenced code block, an HTML comment, or an inline-code
    span is replaced with a space while line terminators are preserved, so the
    returned lines keep their original one-based numbering and offsets yet no
    reference-looking material survives in a masked region. Each span is visited
    once, so the mask is built in time proportional to the source length.

    :param text: The Markdown source text exactly as read.
    :param index: The scanned block index supplying fence, comment, and inline-code
        spans.
    :returns: The masked physical lines, where line ``n`` is index ``n - 1``.
    """
    masked = list(text)
    total = len(masked)

    def blank(start: int, end: int):
        """Blank a half-open offset range to spaces, keeping line terminators.

        :param start: Inclusive start offset.
        :param end: Exclusive end offset.
        """
        for position in range(start, min(end, total)):
            character = masked[position]
            if character != "\n" and character != "\r":
                masked[position] = " "

    for fence in index.fences:
        blank(fence.span.start_offset, fence.span.end_offset)
    for comment in index.comments:
        blank(comment.span.start_offset, comment.span.end_offset)
    for code in index.inline_code:
        blank(code.span.start_offset, code.span.end_offset)
    return split_physical_lines("".join(masked))


def _closing_bracket(content: str, start: int) -> int:
    """Return the offset of the next unescaped ``]`` at or after ``start``.

    A backslash escapes the following character, so ``\\]`` is not a closer. The
    scan advances monotonically and is only ever entered on a region the caller
    then skips past, keeping the whole use scan linear.

    :param content: One physical line of text without its terminator.
    :param start: The offset to begin scanning from.
    :returns: The offset of the closing ``]``, or ``-1`` when none remains.
    """
    index = start
    length = len(content)
    while index < length:
        character = content[index]
        if character == "\\":
            index += 2
            continue
        if character == "]":
            return index
        index += 1
    return -1


def _scan_uses(content: str) -> list[tuple[int, str, str]]:
    """Return reference-style link uses on one line in a single linear pass.

    The pass maintains a forward cursor that always advances past each bracket
    construct it consumes, so a bracket flood such as ``"[" * n`` or
    ``"[a][b]" * n`` stays linear rather than rescanning the line tail from every
    ``[``. Escaped brackets are skipped, an inline link ``[text](target)`` is
    recognized and skipped (its bracket pair is not a reference), and ``][``
    adjacency distinguishes a full or collapsed reference from a shortcut.

    :param content: One masked physical line of text without its terminator.
    :returns: ``(column, kind, raw_label)`` tuples in source order, where ``kind``
        is :data:`_FULL`, :data:`_COLLAPSED`, or :data:`_SHORTCUT` and
        ``raw_label`` is the governing label exactly as written.
    """
    uses: list[tuple[int, str, str]] = []
    index = 0
    length = len(content)
    while index < length:
        character = content[index]
        if character == "\\":
            index += 2
            continue
        if character != "[":
            index += 1
            continue
        first_close = _closing_bracket(content, index + 1)
        if first_close == -1:
            break
        label_one = content[index + 1 : first_close]
        after = first_close + 1
        if after < length and content[after] == "[":
            second_close = _closing_bracket(content, after + 1)
            if second_close == -1:
                # No closer for the second bracket: treat the first pair as a
                # shortcut and reprocess from the dangling ``[`` without rescanning.
                uses.append((index, _SHORTCUT, label_one))
                index = after
                continue
            label_two = content[after + 1 : second_close]
            if label_two.strip() == "":
                uses.append((index, _COLLAPSED, label_one))
            else:
                uses.append((index, _FULL, label_two))
            index = second_close + 1
            continue
        if after < length and content[after] == "(":
            # Inline link text, not a reference; skip the bracket pair and let the
            # destination be scanned as ordinary text on the next iterations.
            index = after
            continue
        uses.append((index, _SHORTCUT, label_one))
        index = first_close + 1
    return uses


def _finding(path: str, message: str, line: int, severity: str) -> models.Finding:
    """Return a ``DS108`` finding.

    :param path: POSIX-style relative document path.
    :param message: Smallest meaningful diagnostic message.
    :param line: One-based line of the offending construct.
    :param severity: Finding severity (``warning`` or, for duplicates under the
        ``error`` policy, ``error``).
    :returns: A :class:`~docsentinel.models.Finding`.
    """
    return models.Finding(rule=DS108.code, path=path, message=message, severity=severity, line=line)


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS108`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline source
    strings; :func:`detect` layers document reading over it. Only the
    ``"commonmark"`` ``reference_label_normalization`` dialect is modelled; any
    other value yields no confident diagnostics.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source order (ascending line then column), with any
        duplicate ``(line, column, message)`` collapsed.
    """
    settings = config if config is not None else Config()
    if settings.reference_label_normalization != "commonmark":
        return ()

    index = scan_markdown(text, path)
    lines = _masked_lines(text, index)

    definitions: list[tuple[str, str, int, int]] = []
    uses: list[tuple[int, int, str, str, str]] = []
    for line_number, content in enumerate(lines, start=1):
        definition = _REF_DEF_RE.match(content)
        if definition:
            raw_label = definition.group(1)
            if not _is_footnote(raw_label):
                column = definition.start(1) - 1
                definitions.append((normalize_label(raw_label), raw_label, line_number, column))
            continue
        for column, kind, raw_label in _scan_uses(content):
            if not raw_label.strip() or _is_footnote(raw_label):
                continue
            uses.append((line_number, column, kind, normalize_label(raw_label), raw_label))

    defined_labels = {label for label, _raw, _line, _column in definitions}

    used_labels: set[str] = set()
    for _line, _column, kind, label, _raw in uses:
        if kind in (_FULL, _COLLAPSED) or label in defined_labels:
            used_labels.add(label)

    findings: list[tuple[int, int, models.Finding]] = []

    for line, column, kind, label, raw_label in uses:
        if kind in (_FULL, _COLLAPSED) and label not in defined_labels:
            message = f"undefined reference label: {_echo(raw_label)}"
            findings.append((line, column, _finding(path, message, line, DS108.severity)))

    duplicate_policy = settings.duplicate_reference_definitions
    if duplicate_policy != "off":
        severity = "error" if duplicate_policy == "error" else DS108.severity
        seen: set[str] = set()
        for label, raw_label, line, column in definitions:
            if label in seen:
                message = f"duplicate reference definition: {_echo(raw_label)}"
                findings.append((line, column, _finding(path, message, line, severity)))
            else:
                seen.add(label)

    if settings.unused_reference_definitions:
        reported: set[str] = set()
        for label, raw_label, line, column in definitions:
            if label not in used_labels and label not in reported:
                reported.add(label)
                message = f"unused reference definition: {_echo(raw_label)}"
                findings.append((line, column, _finding(path, message, line, DS108.severity)))

    ordered: list[models.Finding] = []
    seen_keys: set[tuple[int, int, str]] = set()
    for line, column, finding in sorted(findings, key=lambda item: (item[0], item[1])):
        key = (line, column, finding.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ordered.append(finding)
    return tuple(ordered)


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
    """Return ``DS108`` findings for Markdown documents in their supplied order.

    Each document is scanned independently, so reference labels never cross
    document boundaries: an undefined label in one document is not satisfied by a
    definition in another.

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


rules.ANALYZERS[DS108.code] = detect
