"""Detect ``@``-document mentions that do not resolve to a file (``DS124``).

An ``@``-mention (``@docs/dev/guide.md`` in prose, or a whole code span such as
`` `@AGENTS.md` ``) is how agent prompts and harnesses import another document.
The shared scanner records every mention
(:class:`~docsentinel.markdown_blocks.AtReference`); this fast, standard-library-only
analyzer checks that each ``relative`` mention whose extension is listed in
``at_reference_extensions`` names an existing regular file. It is an always-active
rule at ``warning`` severity (Milestone 0009 Story 01.0, ADR 0004 Contract 3).

Resolution, per mention, in this fixed order (threat model M1, M2, M5, M6):

1. **Document-relative.** :func:`~docsentinel.detectors.path_boundaries.mention_ds116_reason`
   (the one ownership predicate DS116 itself uses) is asked first; a root escape or
   a symlink out of the scan root belongs to ``DS116``, so DS124 stops and never
   runs step 2. Otherwise the target is resolved lexically with
   :func:`~docsentinel.markdown_blocks.resolve_local_reference`, contained with
   :func:`~docsentinel.detectors.path_boundaries.contained_path` inside the scan
   root, and only the path ``contained_path`` returned is stat-ed (one
   ``os.stat(..., follow_symlinks=False)`` plus ``S_ISREG``). Any other refusal (a
   symlink cycle, more than 64 hops) or any :class:`OSError` means "does not resolve
   at this step" and is never propagated (M10).
2. **Link-root-relative fallback.** ``"/" + target`` is resolved against the
   engine-validated link root and contained inside it the same way. A refusal (a
   climb above the link root, or a symlink out of it) gives **no finding**, only a
   ``DEBUG`` record: the file is outside the link root, so "missing" is the wrong
   word (owner ruling R1, the single documented exception to "every relative
   mention resolves, gets a DS116 finding or gets a DS124 finding"). An
   :class:`OSError`, a cycle or a hop overflow means "does not resolve".
3. Otherwise one ``DS124`` finding is reported.

Security contract (``docs/security/threat-model-0009-at-references-2026-11-14.md``):

* ``home`` and ``absolute`` mentions are skipped on their ``kind`` before any
  resolver or filesystem call; nothing is ever expanded (M7).
* Every filesystem call stays inside the scan root on step 1 and inside the link
  root on step 2: ``os.lstat``/``os.readlink`` happen only inside
  ``contained_path`` and the shared predicate, on in-boundary objects, and the
  single stat is on the contained path (M1-M4). Called without ``link_root=``,
  the fallback is the lexical :func:`~docsentinel.link_root.link_root_for`, so step
  2 never leaves the scan root (M21).
* A target is never opened, read, listed or ``realpath``-ed (M16). The residual
  time-of-check/time-of-use window between ``contained_path`` and the stat is the
  same one ``DS101`` and ``DS113`` accept: a concurrent writer swapping an in-root
  directory for a symlink could learn one existence bit, never content. Stating
  with ``follow_symlinks=False`` narrows it to intermediate components.
* Resolution is memoised per ``(document directory, target)`` and each contained
  path is stat-ed at most once per run, so repeated mentions cost one probe (M9).
* A finding echoes only the author's ``raw`` mention, cut to 200 characters, in
  both ``message`` and ``value`` (M15). It never reveals the resolved path, the step,
  or the file type: a missing file, a directory and a FIFO read the same (M17).
* Logging is ``DEBUG`` only, with the document path through ``safe()``, line
  numbers, counts and fixed reasons; the mention text is never logged (M14).
"""

from __future__ import annotations

import logging
import os
import re
import stat
from bisect import bisect_right
from pathlib import Path
from typing import Final, Optional

from docsentinel import models, rules
from docsentinel.config import Config, validate_at_reference_extensions
from docsentinel.detectors.path_boundaries import (
    canonical_root,
    contained_path,
    escapes_via_symlink,
    mention_ds116_reason,
)
from docsentinel.link_root import link_root_for
from docsentinel.log import safe
from docsentinel.markdown_blocks import AtReference, ReferenceStatus, resolve_local_reference, scan_markdown

logger = logging.getLogger(__name__)

DS124 = rules.register_rule(
    rules.Rule(
        code="DS124",
        profile="fast",
        title="Dangling @-document reference",
        description="An @-document mention does not resolve to an existing file.",
        severity="warning",
    )
)

#: Most characters of the raw mention echoed into ``message`` and ``value`` (M15).
MAX_ECHO_CHARS: Final = 200

#: Finding ``type`` label (``docs/specs/finding-types.md``).
FINDING_TYPE: Final = "dangling document mention"

_LINE_BREAK_RE = re.compile(r"\r\n|\r|\n")

# Resolution outcomes, memoised per (document directory, target).
_RESOLVED: Final = "resolved"
_DS116: Final = "ds116"
_OUTSIDE_LINK_ROOT: Final = "outside_link_root"
_MISSING: Final = "missing"


def _extension(target: str) -> str:
    """Return the lowercased extension of a mention target's last component.

    The scanner records a mention only when its last component has an extension
    holding a letter, and the target is ASCII, so ``str.lower`` is ASCII lowercasing.

    :param target: The decoded mention target.
    :returns: The extension without the dot, lowercased (``""`` when absent).
    """
    last = target.rpartition("/")[2]
    dot = last.rfind(".")
    return last[dot + 1 :].lower() if dot > 0 else ""


class _Resolver:
    """Resolve mention targets for one DS124 run, memoising every probe (M9).

    :ivar root: The scan root, the step-1 boundary.
    :ivar link_root: The validated link root, the step-2 boundary.
    """

    def __init__(self, root: Path, link_root: Path):
        """Create a resolver for one run.

        :param root: The scan root, as the engine passes it.
        :param link_root: The engine-validated link root, or the lexical fallback.
        """
        self.root = root
        self.link_root = link_root
        self._outcomes: dict[tuple[str, str], str] = {}
        self._regular: dict[Path, bool] = {}

    def outcome(self, document_path: str, target: str) -> str:
        """Return the memoised resolution outcome of one ``relative`` mention target.

        :param document_path: POSIX-style relative path of the referring document.
        :param target: The decoded mention target.
        :returns: One of the module's outcome constants.
        """
        directory = document_path.rpartition("/")[0]
        key = (directory, target)
        cached = self._outcomes.get(key)
        if cached is None:
            cached = self._resolve(document_path, target)
            self._outcomes[key] = cached
        return cached

    def _is_regular(self, path: Path) -> bool:
        """Return whether a *contained* path is a regular file, stat-ing it at most once.

        :param path: A path :func:`contained_path` returned (symlinks already expanded).
        :returns: ``True`` for a regular file; ``False`` when missing, of another type,
            or when the stat fails with any :class:`OSError`.
        """
        cached = self._regular.get(path)
        if cached is None:
            try:
                cached = stat.S_ISREG(os.stat(path, follow_symlinks=False).st_mode)
            except OSError:
                cached = False
            self._regular[path] = cached
        return cached

    def _contained(self, boundary: Path, candidate: Path, document_path: str, step: int) -> tuple[Optional[Path], bool]:
        """Return the contained path; an :class:`OSError` means "does not resolve" (M10).

        The error is logged at ``DEBUG`` with a fixed reason and never propagated, so
        one hostile mention (``ENAMETOOLONG``, ``EACCES``, ``ELOOP``) cannot abort the scan.

        :param boundary: The step's containment boundary.
        :param candidate: The lexically resolved candidate inside it.
        :param document_path: The referring document, for the log record only.
        :param step: ``1`` or ``2``, for the log record only.
        :returns: ``(path, failed)``: the contained path or ``None``, and whether an
            :class:`OSError` was raised while proving containment.
        """
        try:
            return contained_path(boundary, candidate), False
        except OSError:
            logger.debug("DS124 %s: containment error on step %d", safe(document_path), step)
            return None, True

    def _resolve(self, document_path: str, target: str) -> str:
        """Run the two-step resolution of one mention target.

        :param document_path: POSIX-style relative path of the referring document.
        :param target: The decoded mention target.
        :returns: One of the module's outcome constants.
        """
        # Step 1: document-relative. DS116's own predicate decides ownership.
        try:
            owned = mention_ds116_reason(self.root, document_path, target) is not None
        except OSError:
            # Treated as "not proven DS116's": containment below decides, and step 2
            # stays bounded by the link root, so nothing leaves either boundary.
            logger.debug("DS124 %s: containment error on step 1", safe(document_path))
            owned = False
        if owned:
            return _DS116
        first = resolve_local_reference(self.root, document_path, target)
        if first.status is ReferenceStatus.RESOLVED and first.path is not None:
            contained, _ = self._contained(self.root, first.path, document_path, 1)
            if contained is not None and self._is_regular(contained):
                return _RESOLVED

        # Step 2: link-root-relative fallback, bounded by the link root.
        second = resolve_local_reference(self.root, document_path, "/" + target, link_root=self.link_root)
        if second.status is not ReferenceStatus.RESOLVED or second.path is None:
            return _OUTSIDE_LINK_ROOT
        contained, failed = self._contained(self.link_root, second.path, document_path, 2)
        if failed:
            return _MISSING
        if contained is None:
            # Refused: a symlink out of the link root is R1's "outside"; a cycle or a
            # hop overflow stays inside it and simply does not resolve.
            try:
                outside = escapes_via_symlink(self.link_root, second.path)
            except OSError:
                outside = False
            return _OUTSIDE_LINK_ROOT if outside else _MISSING
        return _RESOLVED if self._is_regular(contained) else _MISSING


def _line_starts(text: str) -> list[int]:
    """Return the start offset of every line of ``text``, in one linear pass.

    :param text: The document text.
    :returns: Ascending line-start offsets, beginning with ``0``.
    """
    return [0, *(match.end() for match in _LINE_BREAK_RE.finditer(text))]


def _column(text: str, line_starts: list[int], mention: AtReference) -> int:
    """Return the 1-based code-point column of a mention's ``@``.

    :param text: The document text.
    :param line_starts: The result of :func:`_line_starts` for ``text``.
    :param mention: The mention; a code-span mention's span starts at the backticks.
    :returns: The column of the ``@`` within its line.
    """
    offset = mention.span.start_offset
    if mention.in_code_span:
        found = text.find("@", offset, mention.span.end_offset)
        offset = found if found != -1 else offset
    line_start = line_starts[bisect_right(line_starts, offset) - 1]
    return offset - line_start + 1


def _check_text(
    text: str,
    document_path: str,
    resolver: _Resolver,
    extensions: frozenset[str],
) -> tuple[models.Finding, ...]:
    """Return ``DS124`` findings for one document's Markdown ``text``.

    :param text: The Markdown source exactly as read.
    :param document_path: POSIX-style relative path recorded on each finding.
    :param resolver: The run's memoising resolver.
    :param extensions: Validated, lowercased ``at_reference_extensions``.
    :returns: Findings in source order, one per mention occurrence; the same mention
        twice on one line is reported once.
    """
    index = scan_markdown(text, document_path)
    findings: list[models.Finding] = []
    seen: set[tuple[int, str]] = set()
    skipped = {"home": 0, "absolute": 0, "extension": 0, "outside_link_root": 0, "ds116": 0}
    line_starts: Optional[list[int]] = None
    for mention in index.at_references:
        # Branch on kind before any resolver or filesystem call (M7).
        if mention.kind != "relative":
            if mention.kind in skipped:
                skipped[mention.kind] += 1
            continue
        if _extension(mention.target) not in extensions:
            skipped["extension"] += 1
            continue
        outcome = resolver.outcome(document_path, mention.target)
        if outcome == _RESOLVED:
            continue
        if outcome == _DS116:
            skipped["ds116"] += 1
            continue
        if outcome == _OUTSIDE_LINK_ROOT:
            skipped["outside_link_root"] += 1
            logger.debug(
                "DS124 %s:%d: no finding, step-2 boundary refusal", safe(document_path), mention.span.start_line
            )
            continue
        bounded = mention.raw[:MAX_ECHO_CHARS]
        key = (mention.span.start_line, bounded)
        if key in seen:
            continue
        seen.add(key)
        if line_starts is None:
            line_starts = _line_starts(text)
        findings.append(
            models.Finding(
                rule=DS124.code,
                path=document_path,
                message=f"dangling @-reference -> {bounded}",
                severity=DS124.severity,
                line=mention.span.start_line,
                column=_column(text, line_starts, mention),
                value=bounded,
                type=FINDING_TYPE,
            )
        )
    logger.debug(
        "DS124 checked %s: %d mention(s), %d finding(s); skipped %d home, %d absolute, %d extension, "
        "%d outside link root, %d left to DS116",
        safe(document_path),
        len(index.at_references),
        len(findings),
        skipped["home"],
        skipped["absolute"],
        skipped["extension"],
        skipped["outside_link_root"],
        skipped["ds116"],
    )
    return tuple(findings)


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a document path.

    :param path: Absolute path of the Markdown document.
    :returns: The decoded document text.
    :raises OSError: When the document cannot be opened or read.
    :raises UnicodeDecodeError: When the document is not valid UTF-8.
    """
    with path.open(encoding="utf-8") as stream:
        return stream.read()


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
    *,
    link_root: Optional[Path] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS124`` findings for Markdown documents in their supplied order.

    :param root: The scan root directory (trusted); canonicalised once with
        :func:`~docsentinel.detectors.path_boundaries.canonical_root`, as DS116 does.
    :param documents: Documents to inspect, in scan order.
    :param config: Effective settings supplying ``at_reference_extensions`` and
        ``link_root``; ``None`` uses defaults. The extensions of an injected
        ``Config`` are re-validated here (threat model M20).
    :param link_root: The engine-validated step-2 boundary; ``None`` falls back to
        :func:`~docsentinel.link_root.link_root_for`, which accepts only values
        meaning the scan root, so step 2 then stays inside the scan root.
    :returns: Findings across all documents in document then source order.
    :raises ConfigError: When ``at_reference_extensions`` is invalid, or when
        ``link_root`` must be resolved here and is invalid.
    """
    settings = config if config is not None else Config()
    extensions = frozenset(validate_at_reference_extensions(settings.at_reference_extensions))
    scan_root = canonical_root(root)
    base = link_root if link_root is not None else link_root_for(scan_root, settings)
    logger.debug("DS124 checking %d document(s): link_root=%s", len(documents), safe(base))
    resolver = _Resolver(scan_root, Path(base))
    findings: list[models.Finding] = []
    for document in documents:
        if not document.path.endswith(".md"):
            continue
        try:
            text = _read_text(scan_root / document.path)
        except (OSError, UnicodeDecodeError):
            # The engine withheld unreadable documents already; this covers a file
            # that changed after that check. Log the path only, never content.
            logger.debug("DS124 %s: skipped, document no longer readable", safe(document.path))
            continue
        findings.extend(_check_text(text, document.path, resolver, extensions))
    return tuple(findings)


rules.ANALYZERS[DS124.code] = detect
