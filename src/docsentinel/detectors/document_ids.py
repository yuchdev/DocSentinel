"""Detect duplicate stable document identifiers across a corpus (``DS114``).

This fast, standard-library-only analyzer reports two documents (or, with
``document_id_scope = "directory"``, two documents in the same directory) that
declare the **same** stable identity in their opening YAML frontmatter. It reads
only the configured scalar frontmatter field (``document_id_field``, default
``id``), normalizes each value, and flags a collision at the *later* sorted
document, naming the document that declared the identity first.

Minimal frontmatter reader (why there is no YAML dependency)
------------------------------------------------------------
Milestone 0004's ``DS111`` metadata rule -- which would own a shared frontmatter
parser -- is **not** implemented in this tree (the project is a self-contained
0005). ``DS114`` therefore carries its own deliberately minimal, linear-time,
bounded, standard-library-only frontmatter reader rather than importing a YAML
library (a fast-profile runtime may import the standard library only). The reader
recognises a **narrow, enumerated subset** of YAML and is explicitly *not* a YAML
implementation:

* Only the **opening** ``---`` block at byte ``0`` of the document is read (an
  optional UTF-8 BOM is stripped first). A document whose first line is not an
  opening ``---`` fence has no frontmatter, so an ``id:`` line appearing in body
  prose, a heading, or a fenced code example is **never** treated as metadata.
* The block ends at the first line that is exactly ``---`` or ``...``. A block
  with no closing delimiter within :data:`_MAX_FRONTMATTER_LINES` is treated as
  **unterminated / malformed** and yields no identity (see *delegation* below).
* Only **plain top-level** ``key: scalar`` lines are parsed (zero leading
  indentation, the colon followed by whitespace or end of line). Indented and
  nested lines are skipped, never crashed on. Alternative YAML spellings of the
  configured key -- a **quoted key** (``"id":``), an **explicit key** (``? id``),
  or a key brought in by a ``<<`` **merge key** -- are recognised only well enough
  to *defer* (see *alternative key spellings* below), never to mine an identity.
* Supported scalar forms for the configured field: a **plain** scalar (with a
  trailing `` #`` inline comment stripped), a **single-quoted** scalar (``''``
  un-escaped), and a **double-quoted** scalar whose escapes decode **byte-for-byte
  as YAML** -- only ``\\\\``, ``\\"``, ``\\/``, ``\\n``, ``\\t``, ``\\r`` and
  ``\\0``. Any other double-quote escape (a numeric ``\\x``/``\\u``/``\\U``,
  ``\\N``/``\\_``/``\\L``/``\\P``, ``\\<space>``, or a trailing line-continuation
  backslash) is **never mis-decoded**: the value is surfaced as *unsupported*
  instead. A **non-empty** scalar is compared as its literal text -- numbers and
  booleans are **not** interpreted as YAML types, only as text.
* A **blank or null** value is treated as *no declared identity* (eligible for the
  ``document_id_required`` check), not as literal text. Null here means an empty
  value (``id:`` with nothing, only whitespace, or only an inline comment) **or**
  a YAML null spelling ``~`` / ``null`` / ``Null`` / ``NULL``.
* A **multi-line continuation** of the field's value -- a non-empty plain or quoted
  inline scalar immediately followed by a more-indented (blank/comment lines
  skipped) line -- folds into the value in real YAML, so the first physical line
  alone is the wrong identity. The reader does **not** read the truncated first
  line; it surfaces the shape as *unsupported* instead.
* An **unsupported** value shape for the field -- a flow collection (``[`` /
  ``{``), an anchor/alias/tag (``&`` / ``*`` / ``!``), a block scalar (``|`` /
  ``>``), a nested mapping/sequence under the key, a multi-line continuation, an
  unterminated quoted scalar, or a double-quoted scalar with an escape outside the
  decoded subset -- is **never** turned into an identity and never crashes the
  reader; it is surfaced as one explicit finding instead (see *unsupported value
  shape* below).

Delegation to ``DS111`` (malformed / duplicate-key metadata)
------------------------------------------------------------
``DS111`` (not present in this tree) owns metadata *validity*; ``DS114`` owns only
corpus-wide *uniqueness*. ``DS114`` therefore stays **completely silent** for a
document whose frontmatter is malformed in a way ``DS111`` would diagnose -- it
emits no finding and also contributes no identity and no missing-identity finding
for it, so the two rules can never raise contradictory dual diagnostics:

* an unterminated or over-long opening block;
* the configured field appearing **more than once** as a top-level key in one
  block (``DS114`` treats the identity as *ambiguous* and defers entirely; it does
  **not** pick the first or last occurrence); and
* an unsupported value shape of **any other** key, or a blank/null value of the
  configured field (that is *absent*, not malformed).

A document that simply does not declare the field (no frontmatter, or a
well-formed block without the key, or a blank/null value) is *absent*, not
malformed: it is eligible for the ``document_id_required`` finding but is never a
collision.

Alternative key spellings (deferred, not absent)
------------------------------------------------
The reader resolves the field only from a **plain** top-level ``field: ...`` key.
When the field is instead present under a spelling the reader does not resolve --
a **quoted key** (``"id": v``), an **explicit key** (``? id``), or a ``<<`` **merge
key** that could supply it via an alias -- a real parser would still read an
identity, so reporting *absent* would be wrong (and under ``document_id_required``
would raise a false "declares no id"). ``DS114`` therefore returns ``DEFERRED``
(silent, ``DS111`` territory) for these rather than ``ABSENT``: it emits no finding,
contributes no identity, and never claims the field is missing. When a plain key is
**also** present the plain value is used as before, **except** that a ``<<`` merge
key anywhere in the block still forces ``DEFERRED`` (an alias in the merge could
override the plain value, so the final identity is uncertain).

Unsupported value shape of the configured field (one explicit finding)
----------------------------------------------------------------------
When the **configured** field *is* present once in a **well-formed** opening block
but its value shape is unsupported (flow, anchor/alias/tag, block scalar, nested
mapping/sequence, or an unterminated quoted scalar), ``DS114`` does not silently
drop the document: that would let a document with an unparseable identity pass as a
clean scan. Instead it emits **one** explicit finding at the configured rule
severity, attributed to that document at the one-based line of the field, whose
message names only the bounded, repr-escaped field name (never the raw value) and
states the value shape is unsupported and the document was *not* evaluated for
uniqueness. The document is then **excluded** from collision detection -- an
identity is never invented from an unsupported shape. This is a finding rather than
a ``ConfigError`` on purpose: one odd document must flag itself, not abort the whole
scan with exit code ``2``. (The *unterminated/over-long block* and *duplicate id
key* cases remain silent ``DS111`` territory, as above.)

Normalization and scope
-----------------------
A usable scalar is normalized to Unicode **NFC** (canonical equivalence) and its
whitespace collapsed (surrounding whitespace stripped, internal runs collapsed to a
single space), so ``"  alpha  "`` and ``alpha`` collide and an NFC-equivalent pair
collides. NFC is deliberate and matches a real YAML parser: the reader does **not**
apply NFKC/compatibility folding, so Unicode confusables (Latin vs Cyrillic
look-alikes, distinct code points) stay distinct, and **zero-width / format
characters** (``U+200B`` ZWSP, ``U+202E`` RTL override, and the like) are **not**
stripped -- two ids differing only by an invisible character are distinct, exactly
as YAML sees them. (These invisible bytes are repr-escaped by :func:`_echo` before
any report sink.) When ``document_id_case_sensitive`` is false the comparison key is
additionally case-folded. Uniqueness is enforced within the ``document_id_scope``:
``corpus`` (one namespace for every document) or ``directory`` (one namespace per
parent directory).

Reporting
---------
Documents are processed in sorted relative-path order. The first document to
declare an identity is the *original*; every later document declaring the same
identity produces one ``DS114`` finding at ``error`` severity, attributed to that
later document's path, at the one-based line of its identity field, whose message
echoes the colliding identity and the original document's relative path. Both
echoes are bounded to :data:`_MAX_ECHO` characters and ``unicode_escape``-escaped
so no control byte, ``ESC`` sequence, or non-ASCII byte reaches the report sinks;
an absolute path is never echoed. Three documents sharing an identity therefore
produce exactly two findings (``n - 1``), each naming the original.

Security contract (DS113/DS116/DS112 precedents)
------------------------------------------------
* **No filesystem access outside the root.** The trusted root is canonicalised
  once with :func:`os.path.realpath`; each document is opened as ``root /
  document.path`` where ``document.path`` is a discovery-produced in-root relative
  path (discovery already excludes symlinks and non-regular files). The reader
  performs no path resolution of its own and never follows a reference.
* **Bounded head read, never the whole file.** Frontmatter lives at the top, so
  only the first :data:`_MAX_HEAD_BYTES` bytes of each document are read; a
  multi-gigabyte document can neither exhaust memory nor cost more than a bounded
  read. A head that is not valid UTF-8 yields no identity (encoding validity is
  out of ``DS114``'s scope), without crashing the scan.
* **Linear cost, no quadratic shapes.** The reader makes a single bounded pass
  over the head; the corpus check is one pass with set/dict membership after a
  sort, so ``n`` documents (all distinct or all identical) cost ``O(total
  bytes)`` plus the sort.

Registration
------------
``DS114`` is an always-active ``fast``-profile rule at ``error`` severity: Story
12.0 Task 02 wires it in, passing its :class:`~docsentinel.rules.Rule` through
``register_rule`` and registering :func:`detect` in
:data:`~docsentinel.rules.ANALYZERS` as an import side effect, together with its
committed ``tests/assets/ds114/*`` fixtures the Milestone 0005 catalog is
registration gated on, exactly as ``DS108``/``DS112``/``DS113`` were sequenced. It
registers **without** an ``opt_in_option`` -- unlike the opt-in ``DS110``/``DS112``
it is on by default.
"""

from __future__ import annotations

import codecs
import os
import posixpath
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config, ConfigError

#: Stable metadata for ``DS114``, registered here as an import side effect (Story
#: 12.0 Task 02) so importing :mod:`docsentinel.detectors` activates it; the
#: ``ANALYZERS`` wiring is added at the foot of this module.
DS114 = rules.register_rule(
    rules.Rule(
        code="DS114",
        profile="fast",
        title="Duplicate stable document identifiers",
        description="Two documents declare the same stable frontmatter identity within the configured scope.",
        severity="error",
    )
)

#: Maximum characters of the colliding identity or the original path echoed into a
#: finding message.
_MAX_ECHO = 80

#: Upper bound on bytes read from the top of each document. Frontmatter is at byte
#: ``0``, so this head is always enough to find the opening block and its closer;
#: a larger document is never read in full.
_MAX_HEAD_BYTES = 65_536

#: Upper bound on physical lines scanned for the opening block's closing
#: delimiter. A block that is not closed within this many lines is treated as
#: unterminated (malformed, ``DS111`` territory) rather than scanned unbounded.
_MAX_FRONTMATTER_LINES = 2_000

#: Reader outcome: the field is declared once with a usable scalar identity.
_ID = "id"

#: Reader outcome: the field is not declared, or is declared blank/null. The
#: document has no identity but is well-formed, so it is eligible for the
#: ``document_id_required`` finding and never a collision.
_ABSENT = "absent"

#: Reader outcome: the frontmatter is malformed in a way ``DS111`` owns (an
#: unterminated/over-long opening block, or the configured field appearing as a
#: duplicate top-level key). ``DS114`` stays completely silent for such a document.
_DEFERRED = "deferred"

#: Reader outcome: the configured field is present once in a well-formed block but
#: its value shape is unsupported (flow collection, anchor/alias/tag, block scalar,
#: nested mapping/sequence, or an unterminated quoted scalar). ``DS114`` emits one
#: explicit finding for such a document and excludes it from collision detection,
#: rather than inventing an identity or silently dropping it.
_UNSUPPORTED = "unsupported"

#: The accepted ``document_id_scope`` vocabulary. An injected :class:`Config` (the
#: library-caller trust boundary that bypasses ``load_config``'s enum validation)
#: carrying anything else fails closed with a :class:`ConfigError` rather than
#: silently degrading to ``corpus``, mirroring ``DS112``'s config-injection defence.
_VALID_SCOPES = frozenset({"corpus", "directory"})

#: Double-quoted-scalar escape subset decoded by the minimal reader. Every entry
#: decodes **byte-for-byte identically** to YAML 1.2 and PyYAML, so the reader can
#: never invent a value that disagrees with a real parser. Any escape *not* listed
#: here (``\x``/``\u``/``\U`` numerics, ``\a``/``\b``/``\v``/``\f``/``\e``, ``\N``/
#: ``\_``/``\L``/``\P``, ``\<space>`` and the line-continuation ``\``) is **not**
#: guessed at: :func:`_parse_double_quoted` returns ``None`` so the value is deferred
#: to :data:`_UNSUPPORTED` rather than mis-decoded.
_DOUBLE_QUOTE_ESCAPES = {
    "\\": "\\",
    '"': '"',
    "/": "/",
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
}

#: Plain-scalar spellings of a YAML null the reader treats as *no declared identity*
#: (the same outcome as a blank value), matching YAML's core-schema null tokens.
#: Every other plain scalar -- including booleans and numbers -- is kept as literal
#: text, never coerced to a YAML type.
_YAML_NULL_SCALARS = frozenset({"~", "null", "Null", "NULL"})


@dataclass(frozen=True)
class _FieldReading:
    """The result of reading the configured field from one document's frontmatter.

    :ivar status: One of :data:`_ID`, :data:`_ABSENT`, :data:`_DEFERRED`, or
        :data:`_UNSUPPORTED`.
    :ivar value: The raw (un-normalized) scalar text when ``status`` is
        :data:`_ID`, else ``None``.
    :ivar line: The one-based physical line of the field, when ``status`` is
        :data:`_ID` or :data:`_UNSUPPORTED`, else ``None``.
    """

    status: str
    value: Optional[str]
    line: Optional[int]


def _echo(raw_value: str) -> str:
    """Return a bounded, repr-escaped echo of an author-influenced string.

    The value is bounded to :data:`_MAX_ECHO` characters, then escaped with
    ``unicode_escape`` so control bytes, ``ESC`` sequences, and non-ASCII bytes
    render as printable ``\\xNN``/``\\uNNNN`` forms before the string reaches any
    report sink, mirroring the bounded echo used by ``DS113``/``DS116``.

    :param raw_value: The identity or relative path exactly as it would be shown.
    :returns: The bounded, escaped echo with a trailing ``...`` when truncated.
    """
    bounded = raw_value[:_MAX_ECHO]
    escaped = bounded.encode("unicode_escape").decode("ascii")
    return f"{escaped}..." if len(raw_value) > _MAX_ECHO else escaped


def _find_key_colon(content: str) -> Optional[int]:
    """Return the index of the mapping colon in a top-level key line, or ``None``.

    The mapping colon is the first ``:`` followed by whitespace or end of line, so
    a ``:`` embedded in a URL-like value (``http://x``) does not end the key.

    :param content: The physical line's text, with no trailing line terminator.
    :returns: The colon index, or ``None`` when the line is not a mapping key.
    """
    for index, character in enumerate(content):
        if character == ":" and (index + 1 == len(content) or content[index + 1] in " \t"):
            return index
    return None


def _parse_double_quoted(value: str) -> Optional[str]:
    """Return the content of a double-quoted scalar, or ``None`` when uncertain.

    Only the escapes in :data:`_DOUBLE_QUOTE_ESCAPES` are decoded (each exactly as
    YAML/PyYAML does). The reader refuses to guess at any other escape: an
    unrecognised ``\\X`` sequence (a numeric ``\\x``/``\\u``/``\\U``, ``\\N``/``\\_``/
    ``\\L``/``\\P``, ``\\<space>``, or the trailing line-continuation backslash) makes
    the whole value ``None`` so :func:`_interpret_value` surfaces it as an unsupported
    shape rather than silently dropping the backslash. ``None`` is likewise returned
    when no closing quote is found. Text after the closing quote (a trailing comment
    or whitespace) is ignored.

    :param value: The stripped value beginning with a double quote.
    :returns: The decoded scalar text, or ``None`` when the value is unterminated or
        contains an escape the reader does not decode exactly as YAML.
    """
    out: list[str] = []
    index = 1
    length = len(value)
    while index < length:
        character = value[index]
        if character == "\\":
            if index + 1 >= length:
                # A trailing backslash is a line-continuation the line-based reader
                # cannot resolve: defer rather than guess.
                return None
            decoded = _DOUBLE_QUOTE_ESCAPES.get(value[index + 1])
            if decoded is None:
                # An escape outside the exactly-YAML subset: do not mis-decode it.
                return None
            out.append(decoded)
            index += 2
            continue
        if character == '"':
            return "".join(out)
        out.append(character)
        index += 1
    return None


def _parse_single_quoted(value: str) -> Optional[str]:
    """Return the content of a single-quoted scalar, or ``None`` when unterminated.

    A doubled single quote (``''``) is the YAML single-quote escape for a literal
    ``'``; no other escaping applies. Text after the closing quote is ignored.

    :param value: The stripped value beginning with a single quote.
    :returns: The decoded scalar text, or ``None`` when no closing quote is found.
    """
    out: list[str] = []
    index = 1
    length = len(value)
    while index < length:
        character = value[index]
        if character == "'":
            if index + 1 < length and value[index + 1] == "'":
                out.append("'")
                index += 2
                continue
            return "".join(out)
        out.append(character)
        index += 1
    return None


def _strip_plain_comment(value: str) -> str:
    """Return a plain scalar with any trailing `` #`` inline comment removed.

    A ``#`` starts a comment only when preceded by whitespace (YAML's rule), so a
    ``#`` that is part of the scalar (``a#b``) is preserved. The value is assumed
    to have no leading whitespace, so index ``0`` is never a comment start.

    :param value: The stripped plain-scalar text.
    :returns: The scalar text up to an inline comment, if any.
    """
    for index in range(1, len(value)):
        if value[index] == "#" and value[index - 1] in " \t":
            return value[:index]
    return value


def _interpret_value(after_colon: str, next_is_indented: bool) -> _FieldReading:
    """Classify the text after a field's colon into an identity reading.

    :param after_colon: The line text following the mapping colon.
    :param next_is_indented: Whether the next non-blank, non-comment line of the
        block is more indented than the (top-level) key line. For an empty inline
        value this is a nested mapping/sequence; for a non-empty inline scalar it is
        a multi-line continuation that folds into the value. Either way the reader
        cannot be sure of the final string, so the shape is reported unsupported.
    :returns: A reading with no ``line`` populated (the caller fills it in).
    """
    stripped = after_colon.strip()
    if stripped == "" or stripped.startswith("#"):
        # A blank or comment-only inline value is a null scalar (no identity) unless
        # an indented child follows, which is an unsupported nested structure.
        return _FieldReading(_UNSUPPORTED if next_is_indented else _ABSENT, None, None)
    first = stripped[0]
    if first in "[{" or first in "&*!" or first in "|>":
        # Flow collection, anchor/alias/tag, or block scalar: unsupported shapes
        # that are never coerced into an identity.
        return _FieldReading(_UNSUPPORTED, None, None)
    if next_is_indented:
        # A non-empty inline scalar (plain or quoted) immediately followed by a
        # more-indented line is a YAML multi-line continuation: a real parser folds
        # the continuation into the value, so the first physical line alone is the
        # wrong identity. Defer to an explicit unsupported finding rather than read
        # the truncated first line.
        return _FieldReading(_UNSUPPORTED, None, None)
    if first == '"':
        parsed = _parse_double_quoted(stripped)
        return _FieldReading(_UNSUPPORTED if parsed is None else _ID, parsed, None)
    if first == "'":
        parsed = _parse_single_quoted(stripped)
        return _FieldReading(_UNSUPPORTED if parsed is None else _ID, parsed, None)
    plain = _strip_plain_comment(stripped).rstrip()
    if plain == "" or plain in _YAML_NULL_SCALARS:
        # An empty plain value, or a YAML null spelling (``~``/``null``/``Null``/
        # ``NULL``), is *no declared identity* -- the same outcome as a blank value.
        return _FieldReading(_ABSENT, None, None)
    return _FieldReading(_ID, plain, None)


def _split_lines(text: str) -> list[str]:
    """Return physical lines with a leading BOM and any ``\\r`` terminators removed.

    Lines are split on ``\\n`` so one-based indices match an editor's line numbers
    for ``LF`` and ``CRLF`` input (a lone ``CR`` is not treated as a terminator,
    a documented reader limitation).

    :param text: The decoded head text exactly as read.
    :returns: The physical lines, line ``n`` at index ``n - 1``.
    """
    if text.startswith("﻿"):
        text = text[1:]
    return [line.rstrip("\r") for line in text.split("\n")]


def _unquote_key(key_text: str) -> str:
    """Return a mapping key with a single pair of surrounding quotes removed.

    This recognises only the plain ``"field"`` / ``'field'`` quoted-key spelling (no
    escape decoding); it exists so a quoted spelling of the configured field can be
    told apart from an unrelated key, not to parse arbitrary quoted keys.

    :param key_text: The stripped key text before the mapping colon.
    :returns: The key with one matching surrounding quote pair stripped, else the
        key unchanged.
    """
    if len(key_text) >= 2 and key_text[0] in "\"'" and key_text[-1] == key_text[0]:
        return key_text[1:-1]
    return key_text


def _explicit_key_names_field(content: str, field: str) -> bool:
    """Return whether a ``? key`` explicit-key line names the configured field.

    :param content: A top-level block line beginning with the ``?`` explicit-key
        indicator (``?`` followed by whitespace or end of line).
    :param field: The configured identity field name.
    :returns: ``True`` when the explicit key resolves (plain or quoted) to ``field``.
    """
    rest = content[1:].strip()
    colon = _find_key_colon(rest)
    key = rest[:colon].strip() if colon is not None else rest
    return _unquote_key(key) == field


def _next_block_line_is_indented(block: list[str], offset: int) -> bool:
    """Return whether the first following real block line is more indented.

    Blank and comment lines are skipped; the key line is always top-level (zero
    indentation), so any leading space or tab on the next real line marks a YAML
    continuation or nested child. The scan stops at the first non-blank, non-comment
    line, so a long run of continuation or blank lines stays linear.

    :param block: The frontmatter block lines (between the opening and closing
        delimiters).
    :param offset: The zero-based index of the key line within ``block``.
    :returns: ``True`` when the next real line after ``offset`` is indented.
    """
    for probe in range(offset + 1, len(block)):
        line = block[probe]
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        return line[0] in " \t"
    return False


def extract_frontmatter_field(text: str, field: str) -> _FieldReading:
    """Return the configured field's identity reading from a document's frontmatter.

    See the module docstring for the recognised subset and the delegation rules.
    The scan is a single bounded pass and never raises on malformed input.

    :param text: The document's head text (a leading BOM is handled here).
    :param field: The frontmatter key naming the identity (``document_id_field``).
    :returns: An :data:`_ID`, :data:`_ABSENT`, :data:`_DEFERRED`, or
        :data:`_UNSUPPORTED` reading.
    """
    if not text.startswith(("---", "﻿---")):
        return _FieldReading(_ABSENT, None, None)
    lines = _split_lines(text)
    if not lines or lines[0].rstrip() != "---":
        return _FieldReading(_ABSENT, None, None)

    close_index: Optional[int] = None
    limit = min(len(lines), 1 + _MAX_FRONTMATTER_LINES)
    for index in range(1, limit):
        if lines[index].rstrip() in ("---", "..."):
            close_index = index
            break
    if close_index is None:
        # Unterminated (or over-long) opening block: malformed, DS111's territory.
        return _FieldReading(_DEFERRED, None, None)

    block = lines[1:close_index]
    matches: list[int] = []
    has_shadow_field = False
    has_merge_key = False
    for offset, content in enumerate(block):
        if not content.strip() or content.lstrip().startswith("#"):
            continue
        if content[0] in " \t":
            continue
        if content[0] == "?" and (len(content) == 1 or content[1] in " \t"):
            # Explicit-key spelling ``? field``: a valid id declaration the reader
            # does not model. Record it so a bare ``? id`` defers rather than looking
            # absent, but never mine an identity from it.
            if _explicit_key_names_field(content, field):
                has_shadow_field = True
            continue
        colon = _find_key_colon(content)
        if colon is None:
            continue
        key_text = content[:colon].strip()
        if key_text == "<<":
            # A merge key can bring the field in via an alias; the reader cannot
            # resolve the alias, so its presence makes the identity uncertain.
            has_merge_key = True
            continue
        if _unquote_key(key_text) == field and key_text != field:
            # A quoted spelling (``"field":``) of the configured field: another valid
            # declaration the plain-key reader does not resolve.
            has_shadow_field = True
            continue
        if colon > len(field) + 1:
            continue
        if key_text != field:
            continue
        matches.append(offset)

    if len(matches) > 1:
        # Duplicate top-level field key: ambiguous identity, deferred to DS111.
        return _FieldReading(_DEFERRED, None, None)
    if not matches:
        if has_shadow_field or has_merge_key:
            # The field is present only under an alternative YAML spelling the reader
            # does not resolve (quoted/explicit key, or a merge key that could supply
            # it): defer silently rather than report a false "declares no id".
            return _FieldReading(_DEFERRED, None, None)
        return _FieldReading(_ABSENT, None, None)
    if has_merge_key:
        # A plain id plus a merge key: an alias in the merge could override the plain
        # value, so the final identity is uncertain -- defer rather than guess.
        return _FieldReading(_DEFERRED, None, None)

    offset = matches[0]
    content = block[offset]
    colon = _find_key_colon(content)
    after = content[colon + 1 :] if colon is not None else ""
    next_is_indented = _next_block_line_is_indented(block, offset)
    reading = _interpret_value(after, next_is_indented)
    if reading.status == _ID:
        return _FieldReading(_ID, reading.value, offset + 2)
    if reading.status == _UNSUPPORTED:
        # The configured field has an unsupported value shape in a well-formed
        # block; report it at the field's one-based line (never invent an id).
        return _FieldReading(_UNSUPPORTED, None, offset + 2)
    return reading


def normalize_identity(value: str, *, case_sensitive: bool) -> str:
    """Return the comparison key for a raw identity value.

    The value is normalized to Unicode NFC and its whitespace collapsed
    (surrounding whitespace stripped, internal runs collapsed to a single space),
    then case-folded when ``case_sensitive`` is false.

    :param value: The raw scalar text read from the frontmatter.
    :param case_sensitive: Whether comparison keeps case (``True``) or folds it.
    :returns: The normalized comparison key.
    """
    collapsed = " ".join(unicodedata.normalize("NFC", value).split())
    return collapsed if case_sensitive else collapsed.casefold()


def _display_identity(value: str) -> str:
    """Return the human-facing (NFC, whitespace-collapsed, case-preserving) identity.

    :param value: The raw scalar text read from the frontmatter.
    :returns: The normalized identity shown in a finding message.
    """
    return " ".join(unicodedata.normalize("NFC", value).split())


def _scope_key(document_path: str, scope: str) -> str:
    """Return the uniqueness namespace for a document under the configured scope.

    :param document_path: The document's POSIX-style relative path.
    :param scope: ``"corpus"`` (one namespace) or ``"directory"`` (per directory).
    :returns: The namespace key (``""`` for ``corpus``; the parent directory for
        ``directory``).
    """
    if scope == "directory":
        return posixpath.dirname(document_path)
    return ""


def check_documents(
    entries: tuple[tuple[str, str], ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS114`` findings for ``(path, head_text)`` document entries.

    This is the pure corpus core used by unit tests with inline strings;
    :func:`detect` layers the bounded head read over it. Entries are processed in
    sorted relative-path order so the *original* of each identity is deterministic
    and every later duplicate is attributed to its own path.

    :param entries: ``(relative_path, head_text)`` pairs for the documents.
    :param config: Effective settings, or ``None`` for defaults.
    :returns: Findings in sorted-path order; one per duplicate, one per document
        whose configured field has an unsupported value shape, and, when
        ``document_id_required`` is set, one per document lacking an identity.
    """
    settings = config if config is not None else Config()
    field = settings.document_id_field
    case_sensitive = settings.document_id_case_sensitive
    scope = settings.document_id_scope
    required = settings.document_id_required
    if scope not in _VALID_SCOPES:
        # Fail closed on an injected Config that bypassed load_config's enum gate;
        # an unknown scope must not silently fall back to the corpus namespace.
        raise ConfigError(f"document_id_scope must be one of: {', '.join(sorted(_VALID_SCOPES))}")

    findings: list[models.Finding] = []
    originals: dict[tuple[str, str], str] = {}
    for path, text in sorted(entries, key=lambda entry: entry[0]):
        reading = extract_frontmatter_field(text, field)
        if reading.status == _DEFERRED:
            # Malformed/ambiguous metadata is DS111's; DS114 stays silent for it.
            continue
        if reading.status == _UNSUPPORTED:
            # The configured field has an unsupported value shape in a well-formed
            # block: flag it explicitly and exclude it from collision detection,
            # never inventing an identity. A finding, not a ConfigError, so one odd
            # document flags itself rather than aborting the whole scan.
            findings.append(
                models.Finding(
                    rule=DS114.code,
                    path=path,
                    message=(
                        f'document id field "{_echo(field)}" has an unsupported value shape '
                        "(not evaluated for uniqueness)"
                    ),
                    severity=DS114.severity,
                    line=reading.line,
                )
            )
            continue
        if reading.status == _ABSENT:
            if required:
                findings.append(
                    models.Finding(
                        rule=DS114.code,
                        path=path,
                        message=f'document declares no "{_echo(field)}" identity',
                        severity=DS114.severity,
                        line=None,
                    )
                )
            continue
        display = _display_identity(reading.value or "")
        bucket = (_scope_key(path, scope), display.casefold() if not case_sensitive else display)
        original = originals.get(bucket)
        if original is None:
            originals[bucket] = path
            continue
        findings.append(
            models.Finding(
                rule=DS114.code,
                path=path,
                message=f'duplicate document id "{_echo(display)}" (already declared in {_echo(original)})',
                severity=DS114.severity,
                line=reading.line,
            )
        )
    return tuple(findings)


def _decode_head(raw: bytes) -> Optional[str]:
    """Return the decoded head text, or ``None`` when it is not valid UTF-8.

    A trailing incomplete multibyte sequence (a byte-boundary split of the bounded
    head read) is buffered rather than errored by the incremental decoder, so only
    genuinely invalid bytes map to ``None``.

    :param raw: The raw head bytes (a leading UTF-8 BOM is removed here).
    :returns: The decoded text, or ``None`` when the bytes are not valid UTF-8.
    """
    if raw.startswith(codecs.BOM_UTF8):
        raw = raw[len(codecs.BOM_UTF8) :]
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        text: Optional[str] = decoder.decode(raw, final=False)
    except UnicodeDecodeError:
        # A head that is not valid UTF-8 has no extractable identity; encoding
        # validity is out of DS114's scope, so record the absence rather than crash.
        text = None
    return text


def _read_head(path: Path) -> Optional[str]:
    """Return the bounded, UTF-8-decoded head of a document, or ``None``.

    Only the first :data:`_MAX_HEAD_BYTES` bytes are read, so a very large document
    is never materialised in full. An :class:`OSError` on a discovered regular file
    is a genuine environment failure and is allowed to propagate (it is not masked).

    :param path: Absolute path to the in-root document.
    :returns: The decoded head, or ``None`` when the head is not valid UTF-8.
    """
    with path.open("rb") as stream:
        raw = stream.read(_MAX_HEAD_BYTES)
    return _decode_head(raw)


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS114`` findings across the discovered Markdown documents.

    The trusted scan root is canonicalised exactly once with the single permitted
    :func:`os.path.realpath`; each document is read as ``root / document.path`` from
    its discovery-produced in-root relative path, bounded to the head. A document
    whose head is not valid UTF-8 contributes no identity.

    :param root: The scan root directory (trusted).
    :param documents: Discovered documents, in scan order.
    :param config: Effective settings; the engine passes this, and direct callers
        may omit it to use defaults.
    :returns: Findings in sorted-path order.
    """
    settings = config if config is not None else Config()
    canonical = Path(os.path.realpath(root))
    entries: list[tuple[str, str]] = []
    for document in documents:
        if not document.path.endswith(".md"):
            continue
        head = _read_head(canonical / document.path)
        if head is None:
            continue
        entries.append((document.path, head))
    return check_documents(tuple(entries), settings)


rules.ANALYZERS[DS114.code] = detect
