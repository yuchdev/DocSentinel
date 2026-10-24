"""Detect documentation file and directory naming-policy violations (``DS118``).

This fast, standard-library-only analyzer is a **pure path-string policy** over the
relative POSIX paths of the discovered Markdown documents. It performs **zero**
filesystem access of any kind -- no ``open``/``read``, no ``stat``/``lstat``, no
``scandir``/``listdir``, not even an ``os.path.realpath`` of the scan root -- and
never reads document *content*. Every decision is derived from ``Document.path`` as
the engine supplies it (a discovery-produced, in-root, forward-slash relative path).
The detector therefore never renames, rewrites, or touches any file; it only reports
a path component that does not match the configured portable-ASCII naming policy and
offers a deterministic suggested rename.

Opt-in policy (off by default)
------------------------------
``DS118`` is an opt-in policy rule (``opt_in_option="documentation_naming"``, ``fast``
profile, default severity ``warning``). With ``documentation_naming = "off"`` (the
default) the rule is inert and :func:`detect` returns ``()`` immediately. A project
enables it by selecting a style: ``kebab`` (lowercase ASCII letters/digits joined by
single hyphens) or ``snake`` (lowercase ASCII letters/digits joined by single
underscores). The style is validated against :data:`_VALID_STYLES`; an injected
:class:`~docsentinel.config.Config` carrying any other value fails **closed** with a
:class:`~docsentinel.config.ConfigError` (it bypasses ``load_config``'s enum gate),
mirroring ``DS114``'s ``document_id_scope`` defence.

Algorithm (per discovered path)
-------------------------------
The relative path is split into its ``/``-separated components: zero or more
*directory* components and one *file* component.

* **Directory components** are validated only when ``documentation_naming_directories``
  is true (the default). Each distinct directory *name* in the path is checked once.
* The **file component** is split into a *stem* and a trailing *extension* at its last
  ``.`` (``getting-started.md`` -> stem ``getting-started``, extension ``md``). The stem
  is validated against the style; the extension must be a nonempty run of lowercase
  ASCII letters/digits. A filename with no dot has an empty extension and only its stem
  is checked. A filename with several dots keeps every dot before the final one inside
  the stem, so a dot there makes the stem non-conformant (a *multiple-extension* name is
  reported, not silently accepted).

A **component is conformant** when it matches ``[a-z0-9]+(sep[a-z0-9]+)*`` for the
style's separator -- a nonempty sequence of lowercase-ASCII-alphanumeric words joined
by single separators, with no leading/trailing separator, no doubled separator, no
uppercase, no space, no dot, and no non-ASCII character. This single predicate rejects
every matrix violation: uppercase (``GettingStarted``), spaces (``Quick Start``), the
wrong separator (``quick_start`` under ``kebab``; ``quick-start`` under ``snake``),
camelCase (``apiClient``), a non-ASCII letter (``café-guide``), and an uppercase
directory (``Docs``).

Exemptions (false-positive safeguards)
--------------------------------------
Two explicit exemptions keep conventional names clean:

* ``documentation_naming_allow`` (default ``["README.md", "index.md"]``) is an explicit
  allowlist matched **exactly** (case-sensitively). A path's *filename* is exempt when
  it is in the allowlist, and the *whole relative path* is exempt when the full path is
  in the allowlist. Allowlist membership is a :class:`frozenset` lookup, so a large
  allowlist costs O(1) per component -- it never degrades to an O(documents x allow)
  scan (the ``DS115`` shared-workload lesson).
* ``documentation_naming_prefix_patterns`` (default ``[]``) are validated glob-subset
  patterns for numeric ADR/release prefixes and similar conventions. A component (a
  directory name or a filename) matching any pattern is exempt. The glob subset is
  **restricted and documented**: a literal character matches itself, ``?`` matches
  exactly one character, and ``*`` matches any (possibly empty) run of characters.
  There are **no** character classes, alternations, or anchors, and user text is
  **never** compiled as a regular expression -- matching is a linear two-pointer walk
  (:func:`_glob_matches`), so no pattern can trigger catastrophic backtracking (ReDoS).
  The pattern **count** and each pattern's **length** are bounded
  (:data:`_MAX_PREFIX_PATTERNS`, :data:`_MAX_PATTERN_LENGTH`); an injected ``Config``
  exceeding either bound fails **closed** with a :class:`~docsentinel.config.ConfigError`.

Suggested rename (deterministic, safe)
--------------------------------------
Each finding carries a deterministic suggested rename computed by
:func:`_suggest_component` and never applied to disk. The raw component is NFKD-folded
with combining marks dropped (so an accented Latin letter transliterates: ``café`` ->
``cafe``), split into words at camelCase boundaries and at every non-ASCII-alphanumeric
run, lowercased **only for ASCII letters** (a non-ASCII letter is never silently
lowercased; it is a word boundary), and rejoined with the style's separator. A
component that yields no ASCII word (for example an all-Cyrillic or all-CJK name)
suggests the literal ``document`` so the suggestion is always a valid, non-empty,
ASCII, policy-conformant name. The suggestion is ASCII by construction and therefore
safe to embed in a report; the **original** offending component is always echoed
through :func:`_echo` (bounded, ``unicode_escape``-ed) so a hostile path name carrying
``ESC``/newline/``::error``/RTL-override/``NUL`` bytes -- all possible on a POSIX
filesystem and via an injected :class:`~docsentinel.models.Document` -- can never reach
a terminal, a CI annotation, or a log unescaped.

Reporting and determinism
--------------------------
Findings are produced in document order, and within a document the directory components
are reported outermost-first, then the file component -- so ``BadDocs/Quick_Start.md``
yields exactly two findings (``BadDocs`` then ``Quick_Start.md``). A directory *name*
that repeats within one path (``a/a/x.md``) is reported once for that document. The
ruling for a directory shared by many documents is **one finding per document** under
it, each attributed to that document's own path: the ``Finding.path`` is always a real
document path, the count is linear in the corpus, and no document that lives under a
badly named directory is silently omitted. Every finding has ``line=None`` because the
policy is over the path string, not the document body. Per-component conformance and
suggestion depend only on the component name and the scan-constant policy, so each
distinct component is evaluated once and memoised (:class:`_Policy`), keeping a
shared-prefix corpus linear.

Relationship to other rules
----------------------------
``DS115`` handles deprecated names already present in prose or links; ``DS118`` is
pathname *format* only. ``DS101`` reports links broken by a later rename; ``DS118``
never rewrites a link. Excluded directories are removed by ``discovery.py`` before the
engine calls this detector, so an excluded vendor tree is never seen here.

Registration
------------
Story 14.0 Task 01 shipped the detector and its pure cores unregistered; Task 02 wires
it in: the :class:`~docsentinel.rules.Rule` below is registered through
``register_rule``, :func:`detect` is wired into :data:`~docsentinel.rules.ANALYZERS`,
and this module is imported by ``docsentinel.detectors``, alongside the committed
``tests/assets/ds118/*`` fixtures the Milestone 0005 catalog is registration-gated on,
exactly as ``DS108``/``DS112``/``DS115`` were sequenced.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config, ConfigError

#: Stable metadata for ``DS118``, registered (Story 14.0 Task 02) as a ``fast``-profile
#: opt-in policy rule alongside its committed ``tests/assets/ds118/*`` fixtures.
#: ``opt_in_option`` names the config string that switches the policy on, exactly as
#: ``DS110`` uses ``require_fence_languages`` and ``DS115`` uses
#: ``deprecated_references_file``.
DS118 = rules.register_rule(
    rules.Rule(
        code="DS118",
        profile="fast",
        title="Documentation file and directory naming policy",
        description=(
            "A documentation file or directory name does not match the configured portable "
            "naming policy (documentation_naming)."
        ),
        severity="warning",
        opt_in_option="documentation_naming",
    )
)

#: The disabled sentinel and the two supported naming styles. An injected
#: :class:`~docsentinel.config.Config` carrying anything else fails closed with a
#: :class:`~docsentinel.config.ConfigError` rather than silently degrading.
_STYLE_OFF = "off"
_STYLE_KEBAB = "kebab"
_STYLE_SNAKE = "snake"
_VALID_STYLES = frozenset({_STYLE_OFF, _STYLE_KEBAB, _STYLE_SNAKE})

#: The word separator each enabled style joins lowercase-alnum words with.
_STYLE_SEPARATORS = {_STYLE_KEBAB: "-", _STYLE_SNAKE: "_"}

#: Compiled conformance pattern per separator (repo-authored, never user input, so a
#: fixed regex here carries no ReDoS risk). A conformant component is a nonempty run of
#: ``[a-z0-9]`` words joined by single separators, with no leading/trailing/doubled
#: separator; the structure ``W(?:sepW)*`` consumes each character once.
_CONFORMANT = {
    "-": re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*"),
    "_": re.compile(r"[a-z0-9]+(?:_[a-z0-9]+)*"),
}

#: A portable file extension: a nonempty run of lowercase ASCII letters/digits.
_PORTABLE_EXTENSION = re.compile(r"[a-z0-9]+")

#: Maximum characters of an author-influenced string echoed into a finding message.
_MAX_ECHO = 80

#: Upper bound on ``documentation_naming_prefix_patterns`` entries, so a flood of
#: patterns can never drive an unbounded per-component compare (R: bounded pattern set).
_MAX_PREFIX_PATTERNS = 256

#: Upper bound on the length of one prefix pattern, so a single pattern can never drive
#: an unbounded per-component glob walk.
_MAX_PATTERN_LENGTH = 256

#: The suggested-rename fallback when a component yields no ASCII word (for example an
#: all-non-Latin name), so a suggestion is always a valid, non-empty, conformant name.
_EMPTY_SUGGESTION = "document"

#: Sentinel distinguishing "not cached" from a cached ``None`` (acceptable) result, so a
#: conformant component is never re-evaluated. Using ``object()`` keeps ``None`` a valid
#: cached value without a second lookup.
_UNSET = object()


def _echo(raw_value: str) -> str:
    """Return a bounded, repr-escaped echo of an author-influenced string.

    The value is bounded to :data:`_MAX_ECHO` characters, then escaped with
    ``unicode_escape`` so control bytes, ``ESC`` sequences, and non-ASCII bytes render
    as printable ``\\xNN``/``\\uNNNN`` forms before the string reaches any report sink,
    mirroring the bounded echo used by ``DS114``/``DS115``. A hostile path component
    (``NUL``, newline, ``::error``, RTL override) can therefore never reach a terminal,
    a CI annotation, or a log unescaped.

    :param raw_value: The offending component or filename exactly as supplied.
    :returns: The bounded, escaped echo with a trailing ``...`` when truncated.
    """
    bounded = raw_value[:_MAX_ECHO]
    escaped = bounded.encode("unicode_escape").decode("ascii")
    return f"{escaped}..." if len(raw_value) > _MAX_ECHO else escaped


def _glob_matches(pattern: str, text: str) -> bool:
    """Return whether ``text`` matches a restricted glob ``pattern`` (no regex).

    The supported subset is deliberately small and documented: a literal character
    matches itself, ``?`` matches exactly one character, and ``*`` matches any (possibly
    empty) run of characters. There are no character classes, alternations, or anchors,
    and the user pattern is **never** compiled as a regular expression. Matching is a
    linear two-pointer walk with single-star backtracking, so its cost is bounded by the
    (capped) pattern and text lengths and no pattern can trigger catastrophic
    backtracking.

    :param pattern: The restricted glob pattern (already length-bounded).
    :param text: The path component to test.
    :returns: ``True`` when the whole component matches the whole pattern.
    """
    pattern_length = len(pattern)
    text_length = len(text)
    pattern_index = 0
    text_index = 0
    star_index = -1
    star_text = 0
    while text_index < text_length:
        if pattern_index < pattern_length and pattern[pattern_index] in ("?", text[text_index]):
            pattern_index += 1
            text_index += 1
        elif pattern_index < pattern_length and pattern[pattern_index] == "*":
            star_index = pattern_index
            star_text = text_index
            pattern_index += 1
        elif star_index != -1:
            pattern_index = star_index + 1
            star_text += 1
            text_index = star_text
        else:
            return False
    while pattern_index < pattern_length and pattern[pattern_index] == "*":
        pattern_index += 1
    return pattern_index == pattern_length


def _validated_patterns(raw_patterns: tuple[str, ...]) -> tuple[str, ...]:
    """Return the prefix patterns after enforcing the count and length bounds.

    The bounds are re-checked here because an injected :class:`~docsentinel.config.Config`
    bypasses ``load_config``; exceeding either bound fails closed with a
    :class:`~docsentinel.config.ConfigError` rather than allowing an unbounded compare.

    :param raw_patterns: The configured ``documentation_naming_prefix_patterns``.
    :raises ConfigError: When there are more than :data:`_MAX_PREFIX_PATTERNS` patterns
        or any pattern is longer than :data:`_MAX_PATTERN_LENGTH` characters.
    :returns: The validated patterns unchanged.
    """
    if len(raw_patterns) > _MAX_PREFIX_PATTERNS:
        raise ConfigError(f"documentation_naming_prefix_patterns exceeds {_MAX_PREFIX_PATTERNS} patterns")
    for pattern in raw_patterns:
        if len(pattern) > _MAX_PATTERN_LENGTH:
            raise ConfigError(
                f"documentation_naming_prefix_patterns entries must be at most {_MAX_PATTERN_LENGTH} characters"
            )
    return raw_patterns


def _split_extension(filename: str) -> tuple[str, str]:
    """Split a filename into its stem and trailing extension at the last dot.

    A filename with no dot has an empty extension and the whole name as its stem. A dot
    before the final extension stays in the stem (so ``a.b.md`` has stem ``a.b``), which
    is how a *multiple-extension* name is reported rather than silently accepted.

    :param filename: The file component of a path.
    :returns: A ``(stem, extension)`` pair; ``extension`` excludes the dot and is empty
        when the filename has no dot.
    """
    stem, dot, extension = filename.rpartition(".")
    if not dot:
        return filename, ""
    return stem, extension


def _component_is_conformant(component: str, pattern: re.Pattern[str]) -> bool:
    """Return whether a single path component satisfies the style's conformance pattern.

    :param component: The directory name or file stem to test.
    :param pattern: The compiled conformance pattern for the active separator.
    :returns: ``True`` when the component fully matches the pattern.
    """
    return pattern.fullmatch(component) is not None


def _suggest_component(raw_component: str, separator: str) -> str:
    """Return a deterministic, policy-conformant suggested rename for a component.

    The component is NFKD-folded with combining marks dropped (transliterating accented
    Latin letters, so ``café`` becomes ``cafe``), split into words at camelCase
    boundaries and at every run that is not an ASCII letter or digit, lowercased **only**
    for ASCII letters (a non-ASCII letter is treated as a word boundary, never silently
    lowercased), then rejoined with ``separator``. A component that yields no ASCII word
    suggests :data:`_EMPTY_SUGGESTION`, so the result is always a valid, non-empty,
    ASCII, conformant name.

    :param raw_component: The offending component (a directory name or file stem).
    :param separator: The active style's word separator (``-`` or ``_``).
    :returns: The suggested conformant component name.
    """
    decomposed = unicodedata.normalize("NFKD", raw_component)
    words: list[str] = []
    current: list[str] = []
    previous = ""
    for character in decomposed:
        if unicodedata.combining(character):
            continue
        is_upper = "A" <= character <= "Z"
        is_lower = "a" <= character <= "z"
        is_digit = "0" <= character <= "9"
        if is_upper and current and ("a" <= previous <= "z" or "0" <= previous <= "9"):
            words.append("".join(current))
            current = []
        if is_upper or is_lower or is_digit:
            current.append(character.lower() if is_upper else character)
        elif current:
            words.append("".join(current))
            current = []
        previous = character
    if current:
        words.append("".join(current))
    suggestion = separator.join(word for word in words if word)
    # Bound the generated text like the echoed original (an injected component can be arbitrarily long);
    # trimming a trailing separator keeps the truncated suggestion policy-conformant.
    suggestion = suggestion[:_MAX_ECHO].rstrip(separator)
    return suggestion or _EMPTY_SUGGESTION


def _suggest_filename(filename: str, separator: str) -> str:
    """Return a suggested rename for a whole filename, preserving a portable extension.

    The stem is suggested by :func:`_suggest_component`; the extension is ASCII-lowercased
    (extensions are ASCII for Markdown companions, so this never silently lowercases a
    non-ASCII letter) and re-appended. A filename with no extension yields just the
    suggested stem.

    :param filename: The offending file component.
    :param separator: The active style's word separator.
    :returns: The suggested conformant filename.
    """
    stem, extension = _split_extension(filename)
    suggested_stem = _suggest_component(stem, separator)
    if not extension:
        return suggested_stem
    return f"{suggested_stem}.{extension[:_MAX_ECHO].lower()}"


class _Policy:
    """The scan-constant naming policy plus a per-component memoisation cache.

    A single instance is built once per scan from the effective configuration and reused
    for every document, so each distinct directory name and filename is evaluated at most
    once regardless of how many documents share it. This keeps a shared-prefix corpus
    linear: a deep directory shared by thousands of documents is conformance-checked and
    (if offending) suggestion-computed exactly once, then served from the cache.

    :ivar style: The active style name (``kebab`` or ``snake``).
    :ivar separator: The style's word separator.
    :ivar pattern: The compiled conformance pattern for the separator.
    :ivar allow: The exact-match allowlist as a :class:`frozenset` (O(1) membership).
    :ivar prefix_patterns: The validated, bounded glob-subset exemption patterns.
    :ivar check_directories: Whether directory components are validated.
    """

    def __init__(self, settings: Config):
        """Build the policy from effective settings, failing closed on an invalid style.

        :param settings: The effective :class:`~docsentinel.config.Config`.
        :raises ConfigError: When ``documentation_naming`` is not a recognised style, or
            the prefix patterns exceed their count/length bounds (an injected ``Config``
            that bypassed ``load_config``).
        """
        style = settings.documentation_naming
        if style not in _VALID_STYLES:
            allowed = ", ".join(sorted(_VALID_STYLES))
            raise ConfigError(f"documentation_naming must be one of: {allowed}")
        self.style = style
        self.separator = _STYLE_SEPARATORS[style]
        self.pattern = _CONFORMANT[self.separator]
        self.allow = frozenset(settings.documentation_naming_allow)
        self.prefix_patterns = _validated_patterns(settings.documentation_naming_prefix_patterns)
        self.check_directories = settings.documentation_naming_directories
        self._directory_cache: dict[str, Optional[str]] = {}
        self._file_cache: dict[str, Optional[str]] = {}

    def _name_is_exempt(self, name: str) -> bool:
        """Return whether a component name is exempt via the allowlist or a prefix pattern.

        :param name: The directory name or filename to test.
        :returns: ``True`` when the name is explicitly allowed or matches a prefix pattern.
        """
        if name in self.allow:
            return True
        return any(_glob_matches(pattern, name) for pattern in self.prefix_patterns)

    def evaluate_directory(self, name: str) -> Optional[str]:
        """Return a suggested rename for a directory name, or ``None`` when acceptable.

        :param name: The directory component.
        :returns: The suggested conformant name when the component violates the policy,
            else ``None`` (exempt or already conformant). Memoised per distinct name.
        """
        cached = self._directory_cache.get(name, _UNSET)
        if cached is not _UNSET:
            return cached
        if self._name_is_exempt(name) or _component_is_conformant(name, self.pattern):
            result: Optional[str] = None
        else:
            result = _suggest_component(name, self.separator)
        self._directory_cache[name] = result
        return result

    def evaluate_filename(self, filename: str) -> Optional[str]:
        """Return a suggested rename for a filename, or ``None`` when acceptable.

        The filename is exempt when the allowlist or a prefix pattern matches it; the
        whole-path allowlist match is handled by the caller. Otherwise the stem must be
        conformant and the extension must be portable.

        :param filename: The file component.
        :returns: The suggested conformant filename when it violates the policy, else
            ``None``. Memoised per distinct filename.
        """
        cached = self._file_cache.get(filename, _UNSET)
        if cached is not _UNSET:
            return cached
        if self._name_is_exempt(filename):
            result: Optional[str] = None
        else:
            stem, extension = _split_extension(filename)
            stem_ok = _component_is_conformant(stem, self.pattern)
            extension_ok = extension == "" or _PORTABLE_EXTENSION.fullmatch(extension) is not None
            result = None if stem_ok and extension_ok else _suggest_filename(filename, self.separator)
        self._file_cache[filename] = result
        return result

    def check_path(self, relative_path: str) -> list[models.Finding]:
        """Return the naming findings for one relative document path.

        Directory components are checked (outermost first) only when
        ``documentation_naming_directories`` is true and are de-duplicated by name within
        the path; the file component is then checked unless the whole relative path is
        explicitly allowed. Every finding has ``line=None`` and echoes the original
        offending component through :func:`_echo`.

        :param relative_path: The document's forward-slash relative path.
        :returns: The findings for this path in deterministic order.
        """
        findings: list[models.Finding] = []
        parts = relative_path.split("/")
        directories = parts[:-1]
        filename = parts[-1]
        if self.check_directories:
            seen: set[str] = set()
            for name in directories:
                if name in seen:
                    continue
                seen.add(name)
                suggestion = self.evaluate_directory(name)
                if suggestion is not None:
                    findings.append(self._finding(relative_path, "directory", name, suggestion))
        if relative_path not in self.allow:
            suggestion = self.evaluate_filename(filename)
            if suggestion is not None:
                findings.append(self._finding(relative_path, "file", filename, suggestion))
        return findings

    def _finding(self, relative_path: str, kind: str, offending: str, suggestion: str) -> models.Finding:
        """Return one ``DS118`` finding for an offending component.

        :param relative_path: The document path recorded on the finding.
        :param kind: ``"directory"`` or ``"file"`` -- the component kind named in the
            message.
        :param offending: The offending component exactly as supplied (echoed escaped).
        :param suggestion: The deterministic, ASCII, conformant suggested rename.
        :returns: A :class:`~docsentinel.models.Finding` at ``DS118`` severity with
            ``line=None``.
        """
        message = (
            f'{kind} name "{_echo(offending)}" does not match the {self.style} naming policy; '
            f'suggested rename "{suggestion}"'
        )
        return models.Finding(rule=DS118.code, path=relative_path, message=message, severity=DS118.severity, line=None)


def check_paths(paths: tuple[str, ...], config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return the ``DS118`` findings for a sequence of relative document paths.

    This is the pure core used by unit tests with tiny inline path strings; :func:`detect`
    layers the document iteration over it. It performs **zero** filesystem access. When
    ``documentation_naming`` is ``off`` it returns ``()`` with no work; an invalid style
    or out-of-bounds prefix patterns fail closed with a :class:`~docsentinel.config.ConfigError`.

    :param paths: The forward-slash relative document paths, in the desired report order.
    :param config: Effective settings, or ``None`` for defaults.
    :raises ConfigError: On an unrecognised ``documentation_naming`` style or prefix
        patterns exceeding their bounds (an injected ``Config``).
    :returns: The findings in path order; within a path, directories (outermost first)
        then the file component.
    """
    settings = config if config is not None else Config()
    if settings.documentation_naming == _STYLE_OFF:
        return ()
    policy = _Policy(settings)
    findings: list[models.Finding] = []
    for path in paths:
        findings.extend(policy.check_path(path))
    return tuple(findings)


def detect(
    root: object,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS118`` findings across the discovered Markdown documents.

    The policy is a pure function of each document's relative path, so this detector
    touches the filesystem **not at all**: ``root`` is accepted for engine-signature
    parity and is never resolved, stat-ed, or opened, and document *content* is never
    read. With ``documentation_naming`` off the policy is inert and ``()`` is returned.

    :param root: The scan root, accepted for signature parity and never used (the policy
        needs no filesystem access).
    :param documents: Discovered documents, in scan order, supplying their relative paths.
    :param config: Effective settings; the engine passes this, and direct callers may
        omit it to use defaults.
    :raises ConfigError: On an unrecognised style or out-of-bounds prefix patterns.
    :returns: Findings in document order.
    """
    return check_paths(tuple(document.path for document in documents), config)


rules.ANALYZERS[DS118.code] = detect
