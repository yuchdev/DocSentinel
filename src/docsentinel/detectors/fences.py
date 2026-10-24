"""Detect malformed or unclosed fenced code blocks (``DS109``).

This fast, standard-library-only analyzer reuses the shared Markdown block
scanner in :mod:`docsentinel.markdown_blocks` rather than re-parsing fences. It
reports two unambiguous delimiter problems:

* an opening fence (backtick or tilde, opener length >= 3, indent <= 3) that has
  no accepted closing delimiter before end of file; and
* a backtick opener whose info string contains a backtick, which GitHub Flavored
  Markdown forbids on a backtick fence opener.

A closing candidate that carries an info string, or that uses a shorter or a
different marker, is treated by the shared scanner as *not* a closer, so those
cases surface here as unclosed fences with their original opener line preserved.

.. note::

   ``report_stray_closing_fence`` is accepted by :class:`Config` but has no
   additional effect in the ``gfm-subset`` dialect: a lone closing fence is
   lexically indistinguishable from an opener, so the shared scanner models it
   as an unclosed opener that this rule already reports. The option is reserved
   for a future dialect that can tell the two apart; it is read here so that its
   configured value is honored deterministically rather than silently ignored.

The analyzer performs no network, subprocess, or symlink I/O and never executes
embedded code; it only reads the UTF-8 text of Markdown documents it is handed.

``DS109`` is registered in :data:`docsentinel.rules.RULES` and
:data:`docsentinel.rules.ANALYZERS` as an import side effect of this module, so
it runs as an exact ``fast``-profile rule. The Milestone 0005 fixture catalog is
registration gated: registration and engine wiring land together with the
committed ``tests/assets/ds109/*`` fixtures (Task 02), never before them.
"""

from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import Fence, MarkdownBlockIndex, scan_markdown

#: Stable metadata for ``DS109``, registered as a ``fast``-profile rule alongside
#: its committed ``tests/assets/ds109/*`` fixtures (Task 02).
DS109 = rules.register_rule(
    rules.Rule(
        code="DS109",
        profile="fast",
        title="Malformed or unclosed fenced code blocks",
        description="A fenced code block has no valid closing delimiter or a malformed opener.",
        severity="error",
    )
)

_MARKER_NAMES = {"`": "backtick", "~": "tilde"}


def _marker_name(marker: str) -> str:
    """Return a human-readable name for a fence marker character.

    :param marker: The fence marker, ``"`"`` or ``"~"``.
    :returns: ``"backtick"``, ``"tilde"``, or the marker itself when unknown.
    """
    return _MARKER_NAMES.get(marker, marker)


def _fence_finding(fence: Fence) -> Optional[models.Finding]:
    """Return a ``DS109`` finding for one fence, or ``None`` when it is well formed.

    An unclosed fence is reported at its opening line; a closed backtick fence
    whose info string carries a backtick is reported as a malformed opener. A
    shorter or differently marked closing candidate never completes a fence, so
    it is reflected here as the original opener remaining unclosed.

    :param fence: A fence token from the shared scanner.
    :returns: A :class:`~docsentinel.models.Finding` or ``None``.
    """
    if not fence.closed:
        reason = fence.reason or "no matching closing delimiter"
        message = (
            f"unclosed {_marker_name(fence.marker)} fenced code block opened at line {fence.opener_line}: {reason}"
        )
        return models.Finding(
            rule=DS109.code,
            path=fence.span.path,
            message=message,
            severity=DS109.severity,
            line=fence.opener_line,
        )
    if fence.marker == "`" and "`" in fence.info_string:
        return models.Finding(
            rule=DS109.code,
            path=fence.span.path,
            message="malformed opener: a backtick fence info string may not contain a backtick",
            severity=DS109.severity,
            line=fence.opener_line,
        )
    return None


def fenced_line_numbers(index: MarkdownBlockIndex) -> frozenset[int]:
    """Return the one-based line numbers covered by any fenced code block.

    This is offered as a shared fence mask so that other ``DS1xx`` analyzers can
    skip fenced regions using the same tokenization DS109 relies on, instead of
    re-deriving an incompatible fence mask. The span of each fence runs from its
    opener line through its closer line, or through end of file when unclosed.

    :param index: A scanned Markdown block index.
    :returns: The set of one-based line numbers inside fenced code, inclusive of
        the delimiter lines.
    """
    covered: set[int] = set()
    for fence in index.fences:
        covered.update(range(fence.span.start_line, fence.span.end_line + 1))
    return frozenset(covered)


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS109`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline
    source strings; :func:`detect` layers document reading over it.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source order, one per malformed or unclosed fence.
    """
    settings = config if config is not None else Config()
    if settings.fence_dialect != "gfm-subset":
        # Only the gfm-subset dialect is supported; refuse to emit confident
        # diagnostics for an unrecognized dialect rather than guess.
        return ()
    index = scan_markdown(text, path)
    findings = [finding for fence in index.fences if (finding := _fence_finding(fence)) is not None]
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
    """Return ``DS109`` findings for Markdown documents in their supplied order.

    :param root: The resolved scan root directory.
    :param documents: Discovered documents to inspect, in scan order.
    :param config: Effective settings; the engine passes this for configured
        dialect handling, and direct callers may omit it to use defaults.
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


rules.ANALYZERS[DS109.code] = detect
