"""Detect conflicting heading and explicit anchors (``DS104``).

This fast, standard-library-only analyzer reuses the shared Markdown block
scanner in :mod:`docsentinel.markdown_blocks` rather than re-parsing anchors. It
diagnoses explicit-anchor *identity* collisions, which is a different concern
from DS101: DS101 resolves ``#fragment`` links against the anchor inventory,
while ``DS104`` reports when two anchor definitions fight over the same name.

Two collision shapes are reported, both within a single document:

* a **repeated explicit identifier** -- an ``<a id=...>`` / ``<a name=...>``
  value that a later ``<a>`` tag defines again; and
* an **explicit-vs-generated collision** -- an explicit ``<a>`` identifier whose
  spelling is byte-for-byte the GitHub-style slug the renderer already generated
  for a heading, so a ``#fragment`` link becomes ambiguous.

Ordinary repeated headings are **never** flagged: the shared scanner reproduces
DS101's duplicate-suffix behaviour (``setup``, ``setup-1``, ``setup-2``), so two
identical headings own distinct generated anchors. Explicit identifiers are
compared **case-sensitively** and are never lowercased, matching HTML ``id`` /
``name`` semantics; an explicit ``Setup`` therefore does not collide with the
lowercase generated slug ``setup`` because the renderer cannot prove the two
fragments are the same. Empty headings (``#`` with no text) produce an empty
base slug and are excluded from the generated namespace, so they neither collide
nor seed a bogus anchor.

The rule reads the shared scanner's :class:`~docsentinel.markdown_blocks.HtmlAnchor`
tokens, which are extracted only from text that is not fenced, not inside an HTML
comment, and not inside an inline-code span. Anchor-shaped strings in those three
regions are therefore ignored and never reported. Each token carries its one-based
source line, so every collision finding points at the offending later
occurrence's line; the offending party is always the explicit anchor, not the
heading that legitimately owns the generated slug.

Collisions are scoped to one document: the same identifier appearing in two
different documents is never a collision, because each document is scanned
independently.

The analyzer performs no network, subprocess, or symlink I/O and never executes
embedded code; it only reads the UTF-8 text of Markdown documents it is handed.

``DS104`` is registered in :data:`docsentinel.rules.RULES` and
:data:`docsentinel.rules.ANALYZERS` as an import side effect of this module, so
it runs as an exact ``fast``-profile rule. The Milestone 0005 fixture catalog is
registration gated: registration and engine wiring land together with the
committed ``tests/assets/ds104/*`` fixtures (Story 02.0 Task 02), never before
them.
"""

from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import MarkdownBlockIndex, scan_markdown

#: Stable metadata for ``DS104``, registered as a ``fast``-profile rule alongside
#: its committed ``tests/assets/ds104/*`` fixtures (Story 02.0 Task 02).
DS104 = rules.register_rule(
    rules.Rule(
        code="DS104",
        profile="fast",
        title="Conflicting heading and explicit anchors",
        description="An explicit HTML anchor repeats another explicit anchor or shadows a generated heading anchor.",
        severity="warning",
    )
)


def _generated_anchor_slugs(index: MarkdownBlockIndex) -> frozenset[str]:
    """Return the generated heading-anchor namespace for a document.

    Each heading contributes its duplicate-suffixed slug, matching the anchors
    DS101 resolves links against. Headings with an empty base slug (``#`` with no
    text) are excluded: they neither own a usable fragment nor should their
    suffixed sibling (for example an empty second heading slugged ``-1``) seed a
    bogus anchor that could be mistaken for a collision.

    :param index: A scanned Markdown block index.
    :returns: The generated heading slugs, excluding empty-text headings.
    """
    return frozenset(heading.slug for heading in index.headings if heading.base_slug)


def _finding(path: str, message: str, line: int) -> models.Finding:
    """Return a ``DS104`` finding for an offending explicit anchor.

    The reported line is the offending later occurrence's source line; the
    offending identifier in every collision is the explicit anchor, never the
    heading that owns the generated slug.

    :param path: POSIX-style relative document path.
    :param message: Smallest meaningful diagnostic message.
    :param line: One-based line of the offending explicit anchor.
    :returns: A :class:`~docsentinel.models.Finding`.
    """
    return models.Finding(rule=DS104.code, path=path, message=message, severity=DS104.severity, line=line)


def _anchor_findings(index: MarkdownBlockIndex, path: str) -> list[models.Finding]:
    """Return ``DS104`` findings for explicit anchors in source order.

    Explicit anchors are walked in scanner (source) order. The first occurrence
    of an identifier is its definition; a later identical identifier is a
    repeated-explicit collision, and an identifier whose spelling matches a
    generated heading slug is an explicit-vs-generated collision. Comparisons are
    case-sensitive so ``Setup`` and ``setup`` stay distinct, and every finding
    carries the offending anchor's one-based line.

    :param index: A scanned Markdown block index.
    :param path: POSIX-style relative document path.
    :returns: Findings in source order, one per offending later identifier.
    """
    generated = _generated_anchor_slugs(index)
    findings: list[models.Finding] = []
    seen: set[str] = set()
    for anchor in index.explicit_anchors:
        name = anchor.value
        if not name:
            # The scanner never emits an empty anchor value, but an empty name
            # could never be a meaningful fragment, so it is defensively skipped.
            continue
        if name in seen:
            findings.append(
                _finding(path, f"explicit anchor {name!r} is defined more than once in this document", anchor.line)
            )
        elif name in generated:
            findings.append(
                _finding(path, f"explicit anchor {name!r} collides with the generated anchor of a heading", anchor.line)
            )
        seen.add(name)
    return findings


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS104`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline
    source strings; :func:`detect` layers document reading over it. When
    ``anchor_collision_policy`` is ``"off"`` no findings are produced, and only
    the ``"github"`` ``anchor_renderer`` is supported; any other renderer yields
    no confident diagnostics.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source order, one per offending explicit anchor.
    """
    settings = config if config is not None else Config()
    if settings.anchor_collision_policy == "off":
        return ()
    if settings.anchor_renderer != "github":
        # Only the GitHub slugger is modelled; refuse to emit confident
        # diagnostics for an unrecognized renderer rather than guess.
        return ()
    index = scan_markdown(text, path)
    return tuple(_anchor_findings(index, path))


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
    """Return ``DS104`` findings for Markdown documents in their supplied order.

    Each document is scanned independently, so the same anchor identifier in two
    different documents is never reported as a collision.

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


rules.ANALYZERS[DS104.code] = detect
