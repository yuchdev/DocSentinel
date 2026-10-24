"""Detect deprecated names and migrated references (``DS115``).

This fast, standard-library-only analyzer reports in-scope textual occurrences of
explicitly **mapped** deprecated names inside discovered Markdown documents, with
the suggested replacement and the mapping provenance. It is driven by a
user-configured, root-contained TOML **mapping file** of ``[[replacement]]``
entries (``old``, ``new``, ``kind``, optional ``scope``) named by the
``deprecated_references_file`` config option. With no mapping configured the rule
is inert and performs **zero** filesystem access (the opt-in gate, R8).

``DS115`` is an opt-in policy rule (``opt_in_option="deprecated_references_file"``,
``fast`` profile, default severity ``warning``). A missing, unreadable,
out-of-root, non-regular, oversized, or schema-invalid mapping file is a
**config/readiness error** (:class:`~docsentinel.config.ConfigError` -> CLI exit
``2``), never a silent clean result and never a :class:`~docsentinel.models.Finding`
(R2/R3).

Security contract (see
``docs/security/threat-model-ds115-deprecated-references-2026-10-23.md`` and the
DS112/DS113/DS114/DS116 precedents). Like DS112, ``DS115`` is driven by
**attacker-controlled configuration** as well as content: in CI/pre-commit a PR
author chooses which file ``deprecated_references_file`` opens and every byte of
the mapping's ``old``/``new``/``kind``/``scope`` strings. Unlike DS112's index (a
discovered ``.md`` document whose membership in ``documents`` is a usable gate),
the DS115 mapping is **TOML, not Markdown** -- it is never inventoried by
``discovery.py``, so containment is enforced by the lexical + ``stat`` path alone
(R1). The DS116/DS113/DS112/DS114 floor applies unchanged; the following
DS115-specific controls are added:

Rulings recorded (threat model R1-R10):

* **R1 -- mapping read discipline (no ``documents`` membership gate).** Because an
  injected :class:`~docsentinel.config.Config` bypasses ``load_config``'s lexical
  validation, the configured mapping path is re-validated defensively **before any
  open**, in order: :func:`~docsentinel.detectors.path_boundaries.is_ds116_owned`
  false, :func:`~docsentinel.markdown_blocks.resolve_local_reference` ``RESOLVED``,
  :func:`~docsentinel.detectors.path_boundaries.escapes_via_symlink` false,
  ``os.stat`` + :func:`stat.S_ISREG`, and ``st_size <= _MAX_MAPPING_BYTES``. The
  file is opened ``"rb"``, a bounded byte count is read (never an unbounded
  ``tomllib.load`` on a stream), decoded once, and parsed with
  :func:`tomllib.loads`. A FIFO/device/socket/directory/symlink-out/oversized
  mapping is never opened.
* **R2 -- schema contract.** The mapping has a required integer ``version`` (``1``)
  and an array-of-tables ``[[replacement]]`` with required ``old`` (nonempty,
  bounded, no control bytes), required ``new`` (nonempty, bounded, no control
  bytes), required ``kind`` from the closed enum ``prose``/``link``/``identifier``,
  and an optional ``scope`` (a bounded list of bounded, control-free glob strings).
  Unknown keys, missing/mistyped keys, an unsupported ``kind``, empty/oversized
  strings, over ``_MAX_ENTRIES`` entries, and a duplicate/conflicting ``old`` (two
  entries sharing the same normalized ``old`` **and** the same scope set -- a
  *semantic* cross-entry duplicate ``tomllib`` does not catch) each raise
  :class:`~docsentinel.config.ConfigError`.
* **R3 -- readiness error surface.** Every readiness/schema failure raises
  :class:`~docsentinel.config.ConfigError`, which the engine propagates to CLI exit
  ``2`` and to a raised exception for the Python API / pytest. ``tomllib``,
  ``UnicodeDecodeError`` and ``OSError`` failures are re-wrapped as a bounded,
  repr-escaped ``ConfigError`` naming only the configured path (never the raw
  ``tomllib`` text, which may echo content and gives line/col). No new exit code,
  no JSON schema v1 change.
* **R4 -- literal matcher, linear cost, token boundaries.** ``old`` tokens and
  ``scope`` globs are matched **literally** and are **never** compiled as a user
  regex (no ReDoS). Each substrate unit is tokenized exactly once with the fixed,
  repo-authored :data:`_TOKEN_RE` (never user input); the ``old`` token sequences are
  held in a per-kind **token trie** (:class:`_MatchIndex`), so each document position
  is matched by a walk of at most as many dict steps as the longest ``old`` is tokens
  long -- O(document tokens x longest old in tokens), bounded by the mapping and
  **independent of how many entries share a prefix** (a first-token-only bucket was
  O(entries x document tokens) when thousands of multi-word ``old`` values shared one
  first token). Whole-token comparison makes ``APIv1`` not match inside ``APIv10``,
  and a multi-word ``old`` matches only whitespace-adjacent tokens on one physical
  line. ``scope`` globs match the document's relative POSIX path **once per document**
  with :func:`fnmatch.fnmatchcase` on a bounded pattern count, never per token. Entry
  count and per-string length are bounded at schema load. Each discovered document is
  read in full exactly as every other fast detector reads it (discovery governs what
  is a document; no detector size-caps a discovered file), and the linear matcher
  keeps that whole-document read bounded in cost.
* **R5 -- scope and masking.** ``kind="prose"`` matches run over the scanner's
  **masked** physical lines (fenced code, inline code, and HTML comments blanked);
  ``kind="identifier"`` matches run over ``index.inline_code`` span text;
  ``kind="link"`` matches run over local link / reference-definition targets. The
  ``deprecated_check_prose`` toggle gates ``prose`` and ``identifier`` (document
  content); ``deprecated_check_links`` gates ``link``. The historical/archive
  exemption is an explicit per-entry ``scope`` glob (including ``!``-prefixed
  excludes), never date-guessing. No regex over unmasked source and no second
  Markdown parser (requirement 16).
* **R6 -- bounded, repr-escaped echo.** Every readiness ``ConfigError`` and every
  finding message echo only bounded, ``unicode_escape``-ed strings via
  :func:`_echo`: the raw **configured** mapping path (never a resolved absolute
  path), the raw matched ``old`` token, and the raw suggested ``new``. Provenance is
  the configured path plus the integer ``[[replacement]]`` entry index.
* **R7 -- normalization and case policy.** Matching normalization is **NFC on both
  sides** (mirroring DS114; no NFKC / confusable folding, so homoglyphs stay
  distinct). Case sensitivity is governed solely by ``deprecated_case_sensitive``
  (both sides are casefolded when it is false). ``DS115`` reports literal
  occurrences and never chases or re-applies a replacement, so chains (``a->b->c``)
  and cycles (``a->b, b->a``) are inert -- each literal ``old`` occurrence is
  reported independently and the matcher never follows ``new``.
* **R8 -- opt-in accounting.** The opt-in gate is ``deprecated_references_file``
  only; ``deprecated_check_prose``/``deprecated_check_links``/
  ``deprecated_case_sensitive`` are sub-options, not part of the gate. ``DS115`` is
  genuinely evaluated whenever a mapping is configured even if the sub-checks are
  off; an empty ``deprecated_references_file`` makes it not-applicable (named, not
  counted, in the engine notice) and :func:`detect` returns ``()`` with zero I/O.
* **R9 -- zero filesystem probe of targets.** The only filesystem access ``DS115``
  performs during a scan is the single bounded mapping read plus the already
  discovered documents. A deprecated link/path token is matched and flagged
  **lexically** with **zero** ``stat``/``open``/``realpath``/symlink-follow on the
  target: existence is DS101's concern, root escape DS116's (documented overlap,
  contract E). :func:`resolve_local_reference` is used only for string identity, and
  only to re-validate the mapping path -- never to prove a target exists.
* **R10 -- occurrence counting and determinism.** One finding per distinct
  occurrence, ordered by ``(line, source offset, entry index)`` and stable across
  repeated scans and fresh roots; exact-duplicate ``(line, offset, entry)`` tuples
  are collapsed.

**DS115 is a best-effort, explainable deprecated-term guard over a narrow TOML
mapping and the shared-scanner masked view -- not a complete migration or
terminology control.** It inherits every shared-scanner false negative (multi-line
or nested-parenthesis link destinations, multi-line HTML tags, unquoted attributes,
shortcut references) plus the NFC normalization policy, the literal-match
token-boundary rule (dotted/slashed ``old`` values must be written exactly, and a
multi-word ``old`` matches only tokens separated by whitespace on one physical
line), and it deliberately performs no existence or target validation. One known
false-*positive* direction: the prose mask (:func:`_masked_text`) blanks only the
shared scanner's fenced code, inline code, and HTML comment spans, because the
scanner exposes no indented-code-block or HTML-block spans. A ``kind="prose"`` term
inside a CommonMark **4-space indented code block** or an **HTML block** is therefore
reported though a renderer shows it as code/markup; move such examples into a fenced
block (or exclude the path with a ``scope`` glob) to suppress it. This is advisory
only (``warning`` severity, downgradable via ``select``/``ignore``/baseline).

Story 13.0 Task 02 registers this :class:`~docsentinel.rules.Rule` in ``RULES``
and wires :func:`detect` into ``ANALYZERS`` (through
``docsentinel.detectors.__init__``), exactly as ``DS112`` is wired, so the
committed ``tests/assets/ds115/*`` fixtures are enforced by the Milestone 0005
catalog.
"""

from __future__ import annotations

import os
import re
import stat
import tomllib
import unicodedata
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config, ConfigError
from docsentinel.detectors.path_boundaries import escapes_via_symlink, is_ds116_owned
from docsentinel.markdown_blocks import (
    InlineCode,
    LocalReference,
    MarkdownBlockIndex,
    ReferenceStatus,
    resolve_local_reference,
    scan_markdown,
    split_physical_lines,
)

#: Stable metadata for ``DS115``, registered as a ``fast``-profile opt-in policy
#: rule alongside its committed ``tests/assets/ds115/*`` fixtures (Story 13.0
#: Task 02). The ``opt_in_option`` names the config string that switches the policy
#: on, exactly as ``DS110`` uses ``require_fence_languages`` and ``DS112`` uses
#: ``navigation_indexes``; with ``deprecated_references_file`` empty the rule is
#: inert, the engine notice names it, and it is not counted among the evaluated
#: rules.
DS115 = rules.register_rule(
    rules.Rule(
        code="DS115",
        profile="fast",
        title="Deprecated names and migrated references",
        description=(
            "A document uses a name or reference explicitly mapped as deprecated in the "
            "configured deprecated-references mapping file."
        ),
        severity="warning",
        opt_in_option="deprecated_references_file",
    )
)

#: Maximum characters of an author-controlled string echoed into a finding or a
#: readiness-error message.
_MAX_ECHO = 80

#: Maximum number of attacker-controlled TOML key names listed in a schema
#: ``ConfigError`` before a bounded ``... N more`` tail, so a flood of keys can
#: neither grow the message without bound nor inject terminal/log bytes (R6).
_MAX_LISTED_KEYS = 5

#: Hard cap on bytes read from the configured mapping file. Enforced by ``os.stat``
#: *before* any open and again by the bounded ``read`` so a huge in-root file can
#: neither exhaust memory nor reach an unbounded ``tomllib.load``.
_MAX_MAPPING_BYTES = 1_000_000

#: Upper bound on ``[[replacement]]`` entries, so no mapping can drive an unbounded
#: per-document compare.
_MAX_ENTRIES = 5000

#: Upper bound on the length of an ``old``/``new``/``scope`` string, so no single
#: field can drive an unbounded compare or a catastrophic glob.
_MAX_STRING = 500

#: Upper bound on ``scope`` globs per entry.
_MAX_SCOPE_PATTERNS = 64

#: The closed ``kind`` enum.
_PROSE = "prose"
_LINK = "link"
_IDENTIFIER = "identifier"
_KINDS = frozenset({_PROSE, _LINK, _IDENTIFIER})

#: The required and optional ``[[replacement]]`` keys.
_REQUIRED_ENTRY_KEYS = frozenset({"old", "new", "kind"})
_ALLOWED_ENTRY_KEYS = _REQUIRED_ENTRY_KEYS | {"scope"}
_ALLOWED_TOP_KEYS = frozenset({"version", "replacement"})

#: The one supported mapping schema version.
_SCHEMA_VERSION = 1

#: Repo-authored tokenizer (never user input, R4): an identifier/path run of
#: Unicode word (``\w``) segments joined by single ``.``/``-``/``/`` separators. A
#: trailing sentence period or comma is excluded (it is not followed by a word
#: character), while internal dots/hyphens/slashes in ``pkg.Old.Thing`` or
#: ``docs/old-guide.md`` are kept. ``\w`` is Unicode-aware so accented identifiers
#: tokenize whole (matching is NFC on both sides, R7); it excludes combining marks,
#: so an NFD-encoded *document* is a documented best-effort limitation. The
#: structure ``A(?:sepA)*`` consumes each character once with no ambiguous
#: backtracking, so it is linear and carries no catastrophic pattern.
_TOKEN_RE = re.compile(r"\w+(?:[./\-]\w+)*")


def _echo(raw_value: str) -> str:
    """Return a bounded, repr-escaped echo of an author-controlled string.

    The value is bounded to :data:`_MAX_ECHO` characters, then escaped with
    ``unicode_escape`` so control bytes, ``ESC`` sequences, and non-ASCII bytes
    render as printable ``\\xNN``/``\\uNNNN`` forms before the string reaches any
    report sink or the ``Scan failed:`` line, mirroring the bounded echo used by
    ``DS112``/``DS113``/``DS116``. A resolved absolute path is never echoed.

    :param raw_value: The configured path, matched token, or suggested replacement
        exactly as written.
    :returns: The bounded, escaped echo with a trailing ``...`` when truncated.
    """
    bounded = raw_value[:_MAX_ECHO]
    escaped = bounded.encode("unicode_escape").decode("ascii")
    return f"{escaped}..." if len(raw_value) > _MAX_ECHO else escaped


def _echo_keys(keys: set[str]) -> str:
    """Return a bounded, repr-escaped, comma-joined echo of offending TOML keys (R6).

    TOML quoted keys accept ``\\u`` escapes, so an attacker-controlled mapping key
    can carry raw ``ESC``/``BEL``/``CR``/``LF``/``NUL`` bytes and be arbitrarily
    long. Each key is therefore echoed through :func:`_echo` (bounded,
    ``unicode_escape``-ed) before it reaches a ``ConfigError`` message, and at most
    :data:`_MAX_LISTED_KEYS` keys are listed (sorted) before a bounded ``... N more``
    tail, so neither a long key nor a flood of keys can grow the message without
    bound or inject terminal/log bytes.

    :param keys: The offending TOML key names exactly as parsed.
    :returns: The bounded, escaped, comma-joined key list.
    """
    ordered = sorted(keys)
    listed = ", ".join(_echo(key) for key in ordered[:_MAX_LISTED_KEYS])
    remaining = len(ordered) - _MAX_LISTED_KEYS
    return f"{listed}, ... {remaining} more" if remaining > 0 else listed


@dataclass(frozen=True)
class Replacement:
    """One validated ``[[replacement]]`` entry from the mapping file.

    :ivar old: The deprecated name exactly as written in the mapping.
    :ivar new: The suggested replacement exactly as written.
    :ivar kind: The closed-enum substrate selector (``prose``/``link``/
        ``identifier``).
    :ivar scope: The raw ``scope`` glob patterns; an empty tuple means the entry
        applies to every document.
    :ivar index: The zero-based ``[[replacement]]`` position, used as finding
        provenance.
    """

    old: str
    new: str
    kind: str
    scope: tuple[str, ...]
    index: int


@dataclass(frozen=True)
class DeprecatedMapping:
    """A validated deprecated-references mapping.

    :ivar configured_path: The mapping path exactly as configured (echoed as
        provenance; never the resolved absolute path).
    :ivar replacements: The validated entries in ``[[replacement]]`` order.
    """

    configured_path: str
    replacements: tuple[Replacement, ...]


def _normalize(value: str, *, case_sensitive: bool) -> str:
    """Return the matching-normal form of a string (R7).

    Normalization is NFC on both sides (no NFKC / confusable folding); the value is
    casefolded only when ``case_sensitive`` is false.

    :param value: The raw string to normalize.
    :param case_sensitive: Whether matching is case-sensitive.
    :returns: The normalized string used for literal comparison.
    """
    normalized = unicodedata.normalize("NFC", value)
    return normalized if case_sensitive else normalized.casefold()


def _old_tokens(old: str, *, case_sensitive: bool) -> tuple[str, ...]:
    """Return the normalized token sequence of an ``old`` value.

    The ``old`` string is NFC-normalized *before* tokenizing so an NFD-encoded
    accent folds into its base letter's composed form and tokenizes whole, matching
    the NFC document side (R7); each resulting token is then casefolded when the
    policy is case-insensitive.

    :param old: The deprecated name exactly as written.
    :param case_sensitive: Whether matching is case-sensitive.
    :returns: The normalized tokens; empty when ``old`` holds no token character.
    """
    composed = unicodedata.normalize("NFC", old)
    return tuple(_normalize(token, case_sensitive=case_sensitive) for token in _TOKEN_RE.findall(composed))


class _TrieNode:
    """One node of a literal token trie built from the mapping entries.

    :ivar children: Child nodes keyed by the next normalized ``old`` token.
    :ivar terminals: Entries whose full ``old`` token sequence ends at this node, in
        mapping order.
    """

    __slots__ = ("children", "terminals")

    def __init__(self):
        """Initialise an empty trie node with no children and no terminal entries."""
        self.children: dict[str, _TrieNode] = {}
        self.terminals: list[Replacement] = []


class _MatchIndex:
    """A linear literal matcher built once per scan from in-scope entries.

    Entries are grouped by substrate ``kind`` into a per-kind **token trie** keyed on
    the normalized ``old`` token sequence, so a document position is matched by a walk
    of at most as many dict steps as the longest ``old`` is tokens long -- bounded by
    the mapping and **independent of how many entries share a prefix** (R4). A naive
    first-token bucket let thousands of multi-word ``old`` values sharing one first
    token fan a single document token out to one tail compare per entry (quadratic);
    the trie's second step keys on the *second* token, so that same workload stops
    after two dict lookups per position. The index is built once per
    :func:`check_text` call and never compiles a user string as a regex.
    """

    def __init__(self, mapping: DeprecatedMapping, settings: Config):
        """Build the per-kind token trie from the mapping entries.

        An entry whose ``old`` yields no token (only possible if validation were
        bypassed) is skipped so it can never match everywhere.

        :param mapping: The validated mapping.
        :param settings: Effective configuration supplying the case policy.
        """
        self.case_sensitive = settings.deprecated_case_sensitive
        self._roots: dict[str, _TrieNode] = {_PROSE: _TrieNode(), _LINK: _TrieNode(), _IDENTIFIER: _TrieNode()}
        for replacement in mapping.replacements:
            tokens = _old_tokens(replacement.old, case_sensitive=self.case_sensitive)
            if not tokens:
                continue
            node = self._roots[replacement.kind]
            for token in tokens:
                node = node.children.setdefault(token, _TrieNode())
            node.terminals.append(replacement)

    def root(self, kind: str) -> _TrieNode:
        """Return the token-trie root for a substrate kind.

        :param kind: The substrate kind to look up.
        :returns: The root :class:`_TrieNode` for that kind.
        """
        return self._roots[kind]

    def has_kind(self, kind: str) -> bool:
        """Return whether any entry targets the given substrate kind.

        :param kind: The substrate kind.
        :returns: ``True`` when at least one entry has that kind.
        """
        return bool(self._roots[kind].children)


def _document_in_scope(replacement: Replacement, document_path: str) -> bool:
    """Return whether an entry applies to a document given its ``scope`` globs (R5).

    ``scope`` is a list of :func:`fnmatch.fnmatchcase` globs against the document's
    relative POSIX path, matched once per document. A ``!``-prefixed pattern is an
    exclude: the entry does not apply when any exclude matches. When positive
    patterns exist at least one must match; a scope of only excludes applies
    everywhere except the excluded paths; an empty scope applies everywhere.

    :param replacement: The entry whose scope is evaluated.
    :param document_path: The document's POSIX-style relative path.
    :returns: ``True`` when the entry applies to the document.
    """
    if not replacement.scope:
        return True
    positives: list[str] = []
    for pattern in replacement.scope:
        if pattern.startswith("!"):
            if fnmatchcase(document_path, pattern[1:]):
                return False
        else:
            positives.append(pattern)
    if not positives:
        return True
    return any(fnmatchcase(document_path, pattern) for pattern in positives)


@dataclass(frozen=True)
class _Occurrence:
    """One matched deprecated occurrence before it becomes a finding.

    :ivar line: One-based source line of the occurrence.
    :ivar offset: Absolute source character offset (the deterministic column key).
    :ivar replacement: The matched entry.
    """

    line: int
    offset: int
    replacement: Replacement


def _match_unit(
    unit: str,
    base_offset: int,
    line: int,
    kind: str,
    index: _MatchIndex,
    in_scope: frozenset[int],
) -> list[_Occurrence]:
    """Return the deprecated occurrences in one tokenized substrate unit.

    The unit is tokenized once with :data:`_TOKEN_RE`. From every token position a
    bounded walk descends the per-kind token trie: each step consumes the next
    whitespace-adjacent token, and every terminal node reached contributes one
    occurrence per in-scope entry whose ``old`` ends there. The walk stops as soon as
    a token is absent from the trie or a non-whitespace gap breaks adjacency, so each
    position costs at most O(longest old in tokens) dict steps regardless of how many
    entries share a prefix (R4). A single-token ``old`` matches on its token alone; a
    multi-word ``old`` matches only tokens separated by whitespace on this unit, so
    ``old module`` matches ``old module`` but neither ``old, module`` nor a phrase
    split across a line. Only in-scope entries contribute an occurrence.

    :param unit: The substrate text (a masked physical line, an inline-code span's
        text, or a link target).
    :param base_offset: The absolute source offset of ``unit[0]``.
    :param line: The one-based source line the unit begins on.
    :param kind: The substrate kind being matched.
    :param index: The prebuilt literal match index.
    :param in_scope: Entry indices applicable to the current document.
    :returns: The occurrences in this unit (unsorted).
    """
    if not index.has_kind(kind):
        return []
    root = index.root(kind)
    spans = [(match.start(), match.end()) for match in _TOKEN_RE.finditer(unit)]
    normals = [_normalize(unit[start:end], case_sensitive=index.case_sensitive) for start, end in spans]
    count = len(spans)
    occurrences: list[_Occurrence] = []
    for position in range(count):
        node = root
        for step in range(position, count):
            if step > position:
                gap = unit[spans[step - 1][1] : spans[step][0]]
                if gap and not gap.isspace():
                    break
            node = node.children.get(normals[step])
            if node is None:
                break
            if node.terminals:
                offset = base_offset + spans[position][0]
                for replacement in node.terminals:
                    if replacement.index in in_scope:
                        occurrences.append(_Occurrence(line, offset, replacement))
    return occurrences


def _line_start_offsets(text: str) -> list[int]:
    """Return the absolute source offset at which each physical line begins.

    :param text: The document text exactly as read.
    :returns: A list whose entry ``n - 1`` is the start offset of one-based line
        ``n``, aligned with :func:`~docsentinel.markdown_blocks.split_physical_lines`.
    """
    offsets = [0]
    for match in re.finditer(r"\r\n|\r|\n", text):
        offsets.append(match.end())
    return offsets


def _masked_text(text: str, index: MarkdownBlockIndex) -> str:
    """Return the source with fenced code, inline code, and HTML comments blanked.

    Every character inside a fenced block, an inline-code span, or an HTML comment
    is replaced with a space while line terminators and all offsets are preserved,
    so prose matching never sees a construct a CommonMark renderer hides (R5), yet
    every offset and line number still maps back to the original source. Each span
    is visited once, so the mask is built in time proportional to the source length.

    :param text: The Markdown source text exactly as read.
    :param index: The scanned block index supplying the hidden spans.
    :returns: The masked copy, equal in length and offsets to ``text``.
    """
    masked = list(text)
    total = len(masked)
    for spans in (index.fences, index.comments, index.inline_code):
        for token in spans:
            for position in range(token.span.start_offset, min(token.span.end_offset, total)):
                character = masked[position]
                if character != "\n" and character != "\r":
                    masked[position] = " "
    return "".join(masked)


def _prose_occurrences(
    text: str, index: MarkdownBlockIndex, matcher: _MatchIndex, in_scope: frozenset[int]
) -> list[_Occurrence]:
    """Return ``kind="prose"`` occurrences over the masked physical lines.

    :param text: The document text exactly as read.
    :param index: The scanned block index.
    :param matcher: The prebuilt literal match index.
    :param in_scope: Entry indices applicable to this document.
    :returns: The prose occurrences (unsorted).
    """
    if not matcher.has_kind(_PROSE):
        return []
    masked = _masked_text(text, index)
    starts = _line_start_offsets(text)
    occurrences: list[_Occurrence] = []
    for number, content in enumerate(split_physical_lines(masked), start=1):
        base = starts[number - 1] if number - 1 < len(starts) else 0
        occurrences.extend(_match_unit(content, base, number, _PROSE, matcher, in_scope))
    return occurrences


def _identifier_occurrences(
    index: MarkdownBlockIndex, matcher: _MatchIndex, in_scope: frozenset[int]
) -> list[_Occurrence]:
    """Return ``kind="identifier"`` occurrences over inline-code span text.

    :param index: The scanned block index.
    :param matcher: The prebuilt literal match index.
    :param in_scope: Entry indices applicable to this document.
    :returns: The identifier occurrences (unsorted).
    """
    if not matcher.has_kind(_IDENTIFIER):
        return []
    occurrences: list[_Occurrence] = []
    for code in index.inline_code:
        occurrences.extend(
            _match_unit(code.text, _code_offset(code), code.span.start_line, _IDENTIFIER, matcher, in_scope)
        )
    return occurrences


def _code_offset(code: InlineCode) -> int:
    """Return the absolute source offset of an inline-code span's inner text.

    The inner text begins after the opening backtick run, so the span start is
    advanced by the backtick count; this keeps every occurrence's column key inside
    the span and distinct from neighbouring spans.

    :param code: The inline-code span.
    :returns: The absolute offset of the first inner character.
    """
    return code.span.start_offset + code.backticks


def _link_occurrences(index: MarkdownBlockIndex, matcher: _MatchIndex, in_scope: frozenset[int]) -> list[_Occurrence]:
    """Return ``kind="link"`` occurrences over local link targets (R9).

    Link targets are matched **lexically**: the fragment-stripped target of every
    inline/HTML local reference and every reference definition is tokenized and run
    through the matcher with **zero** filesystem access on the target. Existence is
    not probed; a deprecated path is flagged whether or not it still exists.

    :param index: The scanned block index.
    :param matcher: The prebuilt literal match index.
    :param in_scope: Entry indices applicable to this document.
    :returns: The link occurrences (unsorted).
    """
    if not matcher.has_kind(_LINK):
        return []
    occurrences: list[_Occurrence] = []
    for reference in index.local_references:
        occurrences.extend(
            _match_unit(
                _link_target(reference),
                reference.span.start_offset,
                reference.span.start_line,
                _LINK,
                matcher,
                in_scope,
            )
        )
    for definition in index.reference_definitions:
        target = definition.target.partition("#")[0].strip()
        occurrences.extend(
            _match_unit(target, definition.span.start_offset, definition.span.start_line, _LINK, matcher, in_scope)
        )
    return occurrences


def _link_target(reference: LocalReference) -> str:
    """Return the fragment-stripped, whitespace-trimmed target of a local reference.

    :param reference: The inline or HTML local reference.
    :returns: The link's path component without any ``#fragment``.
    """
    return reference.path_component.strip()


def check_text(
    text: str,
    document_path: str,
    root: Path,
    mapping: DeprecatedMapping,
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return the ``DS115`` findings for one document's ``text`` against a mapping.

    This is the pure recognition entry point used by unit tests with inline source
    strings; :func:`detect` layers the mapping load, the readiness error, and the
    per-document iteration over it. It scopes matches per ``kind`` over the shared
    scanner's masked views (R5), matches ``old`` tokens literally with token
    boundaries (R4), honours ``deprecated_check_prose``/``deprecated_check_links``,
    and emits one finding per distinct occurrence in ``(line, offset, entry)`` order
    with exact-duplicate tuples collapsed (R10).

    :param text: The document's Markdown text exactly as read.
    :param document_path: POSIX-style relative path recorded on each finding and
        used for scope-glob matching.
    :param root: The canonical scan root, accepted for parity with the detector
        family. Link targets are matched purely lexically, so it is never used for a
        filesystem probe of any target (R9).
    :param mapping: The validated deprecated-references mapping.
    :param config: Effective settings, or ``None`` for defaults.
    :returns: Findings in deterministic source order.
    """
    settings = config if config is not None else Config()
    matcher = _MatchIndex(mapping, settings)
    in_scope = frozenset(
        replacement.index for replacement in mapping.replacements if _document_in_scope(replacement, document_path)
    )
    if not in_scope:
        return ()

    index = scan_markdown(text, document_path)
    occurrences: list[_Occurrence] = []
    if settings.deprecated_check_prose:
        occurrences.extend(_prose_occurrences(text, index, matcher, in_scope))
        occurrences.extend(_identifier_occurrences(index, matcher, in_scope))
    if settings.deprecated_check_links:
        occurrences.extend(_link_occurrences(index, matcher, in_scope))

    findings: list[models.Finding] = []
    seen: set[tuple[int, int, int]] = set()
    for occurrence in sorted(occurrences, key=lambda item: (item.line, item.offset, item.replacement.index)):
        key = (occurrence.line, occurrence.offset, occurrence.replacement.index)
        if key in seen:
            continue
        seen.add(key)
        findings.append(_finding(document_path, occurrence.line, occurrence.replacement, mapping.configured_path))
    return tuple(findings)


def _finding(path: str, line: int, replacement: Replacement, configured_path: str) -> models.Finding:
    """Return a ``DS115`` finding for one deprecated occurrence (R6).

    :param path: POSIX-style relative path of the document.
    :param line: One-based source line of the occurrence.
    :param replacement: The matched entry supplying the old, new, and index.
    :param configured_path: The mapping path exactly as configured.
    :returns: A :class:`~docsentinel.models.Finding` at ``DS115`` severity whose
        message echoes only bounded, repr-escaped author strings.
    """
    message = (
        f"deprecated {replacement.kind} '{_echo(replacement.old)}' should be replaced "
        f"with '{_echo(replacement.new)}' (mapping {_echo(configured_path)} entry {replacement.index})"
    )
    return models.Finding(rule=DS115.code, path=path, message=message, severity=DS115.severity, line=line)


def _require_string(value: object, field: str, index: int) -> str:
    """Return a validated bounded, control-free, nonempty mapping string (R2).

    :param value: The raw value from the parsed TOML.
    :param field: The field name for the error message.
    :param index: The zero-based entry index for the error message.
    :raises ConfigError: When the value is not a string, is empty/whitespace-only,
        exceeds :data:`_MAX_STRING`, or contains a control byte.
    :returns: The validated raw string.
    """
    if not isinstance(value, str):
        raise ConfigError(f"deprecated mapping entry {index} field {field!r} must be a string")
    if not value.strip():
        raise ConfigError(f"deprecated mapping entry {index} field {field!r} must not be empty")
    if len(value) > _MAX_STRING:
        raise ConfigError(f"deprecated mapping entry {index} field {field!r} exceeds {_MAX_STRING} characters")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ConfigError(f"deprecated mapping entry {index} field {field!r} contains control characters")
    return value


def _require_scope(value: object, index: int) -> tuple[str, ...]:
    """Return a validated ``scope`` glob list (R2/R4).

    :param value: The raw ``scope`` value from the parsed TOML.
    :param index: The zero-based entry index for the error message.
    :raises ConfigError: When the scope is not a list of bounded, control-free,
        nonempty strings or exceeds :data:`_MAX_SCOPE_PATTERNS`.
    :returns: The validated glob patterns.
    """
    if not isinstance(value, list):
        raise ConfigError(f"deprecated mapping entry {index} field 'scope' must be a list of glob strings")
    if len(value) > _MAX_SCOPE_PATTERNS:
        raise ConfigError(f"deprecated mapping entry {index} field 'scope' exceeds {_MAX_SCOPE_PATTERNS} patterns")
    return tuple(_require_string(pattern, "scope", index) for pattern in value)


def parse_mapping(raw_text: str, configured_path: str) -> DeprecatedMapping:
    """Parse and validate a deprecated-references mapping from already-read text.

    This is the pure schema validator (R2): it never touches the filesystem, so unit
    tests can exercise every hostile mapping shape from an inline string. It wraps a
    :class:`tomllib.TOMLDecodeError` as a bounded :class:`~docsentinel.config.ConfigError`
    (R3/R6) that names only the configured path and never the raw ``tomllib`` text.

    :param raw_text: The decoded TOML mapping text.
    :param configured_path: The mapping path exactly as configured (echoed as
        provenance, never a resolved absolute path).
    :raises ConfigError: On any TOML or schema violation.
    :returns: The validated mapping.
    """
    try:
        data = tomllib.loads(raw_text)
    except (tomllib.TOMLDecodeError, ValueError, RecursionError) as exc:
        # ``tomllib`` raises ``TOMLDecodeError`` (a ``ValueError``) on a malformed
        # document, but deeply nested array/table values drive its recursive-descent
        # parser into a ``RecursionError`` (a ``RuntimeError``) even for input under
        # the byte cap. Both are bounded parser failures, so both become the same
        # repr-escaped readiness ``ConfigError`` (R3); the raw ``tomllib`` text, which
        # may echo offending content, is dropped. ``Exception`` is never caught.
        raise ConfigError(f"deprecated references mapping could not be parsed: {_echo(configured_path)}") from exc

    unknown = set(data) - _ALLOWED_TOP_KEYS
    if unknown:
        raise ConfigError(f"deprecated references mapping has unknown top-level keys: {_echo_keys(unknown)}")
    version = data.get("version")
    if version != _SCHEMA_VERSION:
        raise ConfigError(f"deprecated references mapping version must be {_SCHEMA_VERSION}")
    raw_entries = data.get("replacement", [])
    if not isinstance(raw_entries, list):
        raise ConfigError("deprecated references mapping 'replacement' must be an array of tables")
    if len(raw_entries) > _MAX_ENTRIES:
        raise ConfigError(f"deprecated references mapping exceeds {_MAX_ENTRIES} entries")

    replacements: list[Replacement] = []
    seen_keys: set[tuple[str, frozenset[str]]] = set()
    for index, entry in enumerate(raw_entries):
        replacements.append(_build_replacement(entry, index, seen_keys))
    return DeprecatedMapping(configured_path=configured_path, replacements=tuple(replacements))


def _build_replacement(entry: object, index: int, seen_keys: set[tuple[str, frozenset[str]]]) -> Replacement:
    """Return one validated :class:`Replacement`, rejecting conflicts (R2).

    A conflict is two entries sharing the same case-folded, NFC-normalized ``old``
    **and** the same scope set -- a semantic cross-entry duplicate ``tomllib`` does
    not catch. The conflict key is case-insensitive so a duplicate cannot hide
    behind a casing difference.

    :param entry: One raw ``[[replacement]]`` table.
    :param index: The zero-based entry index.
    :param seen_keys: The accumulating set of ``(normalized old, scope set)`` keys.
    :raises ConfigError: On a missing/unknown/mistyped key, an unsupported ``kind``,
        or a duplicate/conflicting ``old``.
    :returns: The validated entry.
    """
    if not isinstance(entry, dict):
        raise ConfigError(f"deprecated mapping entry {index} must be a table")
    keys = set(entry)
    missing = _REQUIRED_ENTRY_KEYS - keys
    if missing:
        raise ConfigError(f"deprecated mapping entry {index} is missing keys: {', '.join(sorted(missing))}")
    unknown = keys - _ALLOWED_ENTRY_KEYS
    if unknown:
        raise ConfigError(f"deprecated mapping entry {index} has unknown keys: {_echo_keys(unknown)}")
    old = _require_string(entry["old"], "old", index)
    new = _require_string(entry["new"], "new", index)
    kind = _require_string(entry["kind"], "kind", index)
    if kind not in _KINDS:
        raise ConfigError(f"deprecated mapping entry {index} field 'kind' must be one of {sorted(_KINDS)}")
    scope = _require_scope(entry["scope"], index) if "scope" in entry else ()
    conflict_key = (unicodedata.normalize("NFC", old).casefold(), frozenset(scope))
    if conflict_key in seen_keys:
        raise ConfigError(f"deprecated mapping entry {index} conflicts with an earlier entry for the same name")
    seen_keys.add(conflict_key)
    return Replacement(old=old, new=new, kind=kind, scope=scope, index=index)


def load_mapping(root: Path, configured_path: str) -> DeprecatedMapping:
    """Validate, read, and parse the configured mapping file (R1/R3).

    The configured path is re-validated defensively before any open because an
    injected :class:`~docsentinel.config.Config` bypasses ``load_config``: it must
    not be DS116-owned, must resolve ``RESOLVED`` in-root, must not escape via a
    symlink, must be a regular file, and must be at most :data:`_MAX_MAPPING_BYTES`
    bytes -- all before the bounded ``"rb"`` read. ``tomllib``/decode/``OSError``
    failures are re-wrapped as a bounded :class:`~docsentinel.config.ConfigError`.

    :param root: The canonical scan root.
    :param configured_path: The mapping path exactly as configured.
    :raises ConfigError: When the mapping is out-of-root, non-regular, oversized,
        unreadable, non-UTF-8, unparseable, or schema-invalid.
    :returns: The validated mapping.
    """
    if is_ds116_owned(root, ".", configured_path):
        raise ConfigError(f"deprecated references mapping escapes the documentation root: {_echo(configured_path)}")
    reference = resolve_local_reference(root, ".", configured_path)
    if reference.status is not ReferenceStatus.RESOLVED or reference.path is None:
        raise ConfigError(f"deprecated references mapping escapes the documentation root: {_echo(configured_path)}")
    candidate = root / configured_path
    if escapes_via_symlink(root, candidate):
        raise ConfigError(f"deprecated references mapping escapes the documentation root: {_echo(configured_path)}")
    try:
        info = os.stat(candidate)
    except OSError as exc:
        raise ConfigError(f"deprecated references mapping could not be read: {_echo(configured_path)}") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ConfigError(f"deprecated references mapping is not a regular file: {_echo(configured_path)}")
    if info.st_size > _MAX_MAPPING_BYTES:
        raise ConfigError(f"deprecated references mapping is larger than {_MAX_MAPPING_BYTES} bytes")
    try:
        with candidate.open("rb") as stream:
            raw = stream.read(_MAX_MAPPING_BYTES)
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"deprecated references mapping could not be read: {_echo(configured_path)}") from exc
    return parse_mapping(text, configured_path)


def _read_document(path: Path) -> str:
    """Read UTF-8 text from a discovered in-root document.

    :param path: Absolute path to the Markdown document (a discovered, in-root,
        regular file guaranteed by discovery).
    :returns: The decoded document text.
    """
    with path.open(encoding="utf-8") as stream:
        return stream.read()


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS115`` findings across every discovered Markdown document.

    The opt-in gate is ``deprecated_references_file`` only (R8): with it empty the
    policy is not applicable and no findings are produced with zero filesystem
    access. Otherwise the trusted scan root is canonicalised exactly once here with
    the single permitted :func:`os.path.realpath`; the configured mapping is
    validated, read, and parsed defensively (R1/R2/R3); then each discovered ``.md``
    document is read and matched (R4/R5/R9). The only filesystem access is the one
    bounded mapping read plus the already discovered documents; no deprecated target
    is ever ``stat``-ed or opened (R9).

    :param root: The scan root directory (trusted).
    :param documents: Discovered documents, in scan order.
    :param config: Effective settings; the engine passes this, and direct callers
        may omit it to use defaults.
    :returns: Findings across all documents in document then source order.
    :raises ConfigError: When the configured mapping is missing, unreadable,
        non-regular, out-of-root, oversized, unparseable, or schema-invalid.
    """
    settings = config if config is not None else Config()
    if not settings.deprecated_references_file:
        return ()
    canonical = Path(os.path.realpath(root))
    mapping = load_mapping(canonical, settings.deprecated_references_file)
    findings: list[models.Finding] = []
    for document in documents:
        if not document.path.endswith(".md"):
            continue
        text = _read_document(canonical / document.path)
        findings.extend(check_text(text, document.path, canonical, mapping, settings))
    return tuple(findings)


rules.ANALYZERS[DS115.code] = detect
