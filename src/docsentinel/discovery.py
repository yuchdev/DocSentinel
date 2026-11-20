"""Discover Markdown files without following directory symlinks.

Selection follows ADR 0006 (Contracts 2 and 3). A pattern holding ``*``, ``?`` or
``[`` is a **glob** and is matched with :func:`fnmatchcase` exactly as before; any
other pattern is a **literal** that means "this file, or this directory and
everything below it" (a literal include admits only ``.md`` files below a
directory). Only a literal exclude prunes a directory by its relative path; a glob
exclude keeps the directory-name test, so every glob configuration gives the same
inventory and skip count as before.

Invoker selectors (``--include``/``--exclude`` and the ``scan()`` keywords) go
through :func:`normalize_invoker_selectors` first. It is lexical up to the point
where a literal is known to lie inside the canonical scan root; only then does it
walk the joined path with :func:`~docsentinel.detectors.path_boundaries.contained_path`
and ``os.lstat`` it once. Globs never reach the filesystem. Configured values never
pass through it and never trigger filesystem access.
"""

import logging
import ntpath
import os
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Final, Optional, Union

from docsentinel.config import Config, ConfigError
from docsentinel.detectors.path_boundaries import _within, contained_path
from docsentinel.log import safe
from docsentinel.models import Document
from docsentinel.telemetry.filters import neutralize

logger = logging.getLogger(__name__)

#: Characters that make a pattern a glob (Contract 2).
GLOB_CHARACTERS: Final = frozenset("*?[")

#: Most values one invoker key accepts (threat model A8).
MAX_SELECTOR_VALUES: Final = 256

#: Longest single invoker value, checked before any character check or echo (A8).
MAX_SELECTOR_LENGTH: Final = 1024

#: Characters of an invoker value echoed in an error message (A7).
_ECHO_LIMIT: Final = 200

#: Suffix of every normaliser error (A7).
_RELATIVE_HINT: Final = "values are relative to the scan root"

_CHARACTER_REASON: Final = "contains a control, format or unsupported character sequence"
_DRIVE_REASON: Final = "drive, UNC and device paths are not allowed"
_ROOTED_REASON: Final = "a rooted path needs a drive letter"
_WINDOWS_NAME_REASON: Final = "alternate data streams and names ending in a dot or space are not allowed"
_BACKSLASH_REASON: Final = "a backslash is not a path separator on this platform"
_PARENT_REASON: Final = "parent steps (..) are not allowed"
_ABSOLUTE_GLOB_REASON: Final = "globs must be relative"
_OUTSIDE_REASON: Final = "is outside the scan root"
_EMPTY_REASON: Final = "names no path"
_EXCLUDE_ROOT_REASON: Final = "excluding the scan root is not allowed"
_SYMLINK_ESCAPE_REASON: Final = "leaves the scan root through a symlink"
_MISSING_REASON: Final = "not found under the scan root"
_SYMLINKED_REASON: Final = "symlinked paths are not inventoried"
_NOT_REGULAR_REASON: Final = "not a regular file or directory"

_SEPARATORS: Final = ("/", "\\")


def is_glob(pattern: str) -> bool:
    """Return whether a selector pattern is a glob.

    :param pattern: A configured or normalised invoker pattern.
    :returns: ``True`` when the pattern contains ``*``, ``?`` or ``[``.
    """
    return any(character in GLOB_CHARACTERS for character in pattern)


def _under(relative: str, literal: str) -> bool:
    """Return whether ``relative`` lies strictly below the literal directory path.

    :param relative: A scan-root-relative POSIX path.
    :param literal: A literal pattern.
    :returns: ``True`` when ``relative`` starts with ``literal + "/"``.
    """
    return relative.startswith(literal + "/")


def _exclude_reason(relative: str, pattern: str) -> Optional[str]:
    """Return why an exclude pattern removes a file, or ``None`` when it does not.

    :param relative: The file's scan-root-relative POSIX path.
    :param pattern: One exclude pattern.
    :returns: ``"excluded"`` for a path match (or a path below a literal),
        ``"excluded parent directory"`` for a directory-name match, else ``None``.
    """
    if fnmatchcase(relative, pattern) or (not is_glob(pattern) and _under(relative, pattern)):
        return "excluded"
    if any(fnmatchcase(part, pattern) for part in relative.split("/")[:-1]):
        return "excluded parent directory"
    return None


def selector_matches(relative: str, pattern: str, *, include: bool) -> bool:
    """Apply one row of the ADR 0006 Contract 2 matching table to a file path.

    For a glob ``G``: an include admits ``R`` when ``fnmatchcase(R, G)``; an exclude
    removes it when ``fnmatchcase(R, G)`` or ``G`` matches a directory name on its
    path (both unchanged). For a literal ``L``: an include admits ``R == L``, or ``R``
    below ``L`` when ``R`` ends in ``.md``; an exclude removes ``R == L``, ``R`` below
    ``L``, or a directory name on its path equal to ``L``. Matching is case-sensitive
    string comparison or :func:`fnmatchcase`, never a filesystem call.

    :param relative: The file's scan-root-relative POSIX path.
    :param pattern: One include or exclude pattern.
    :param include: ``True`` to apply the include column, ``False`` for exclude.
    :returns: Whether the pattern admits (include) or removes (exclude) the file.
    """
    if not include:
        return _exclude_reason(relative, pattern) is not None
    if is_glob(pattern):
        return fnmatchcase(relative, pattern)
    return relative == pattern or (_under(relative, pattern) and relative.endswith(".md"))


def prunes_directory(relative: str, pattern: str) -> bool:
    """Return whether an exclude pattern removes the directory at this relative path.

    A glob prunes by the directory's name only (unchanged, owner ruling O1); a
    literal prunes by its name or by its whole relative path (new).

    :param relative: The directory's scan-root-relative POSIX path.
    :param pattern: One exclude pattern.
    :returns: ``True`` when the walk must not enter the directory.
    """
    name = relative.rsplit("/", 1)[-1]
    if is_glob(pattern):
        return fnmatchcase(name, pattern)
    return name == pattern or relative == pattern


@dataclass(frozen=True)
class Discovery:
    """The result of one discovery walk.

    :ivar documents: The admitted documents, sorted by path.
    :ivar skipped: Symlinked, non-regular and excluded entries (an excluded
        directory counts once; its contents are never walked).
    :ivar include_hits: Per ``config.include`` entry, in the same order, the
        number of admitted documents it matches (a document counts toward every
        pattern it matches).
    """

    documents: tuple[Document, ...]
    skipped: int
    include_hits: tuple[int, ...]


def discover(root: Path, config: Config) -> tuple[Document, ...]:
    """Return a reproducible inventory of matching regular files.

    :param root: The scan root directory.
    :param config: Effective settings supplying ``include`` and ``exclude``.
    :returns: The sorted documents.
    :raises ValueError: When ``root`` is not a directory.
    """
    return discover_with_stats(root, config).documents


def discover_with_skips(root: Path, config: Config) -> tuple[tuple[Document, ...], int]:
    """Return the :func:`discover` inventory together with the number of skipped entries.

    :param root: The scan root directory.
    :param config: Effective settings supplying ``include`` and ``exclude``.
    :returns: The sorted documents and the skipped-entry count.
    :raises ValueError: When ``root`` is not a directory.
    """
    found = discover_with_stats(root, config)
    return found.documents, found.skipped


def discover_with_stats(root: Path, config: Config) -> Discovery:
    """Walk the scan root and return the inventory, skip count and include hit counts.

    An entry is *skipped* when it is a symlink (file or directory), not a regular
    file, or removed by an ``exclude`` pattern (an excluded directory counts once,
    its contents are never walked). A file that simply does not match ``include``
    is not counted. Each skip is logged at ``DEBUG`` with its reason. Matching
    follows :func:`selector_matches` and :func:`prunes_directory`.

    :param root: The scan root directory.
    :param config: Effective settings supplying ``include`` and ``exclude``.
    :returns: The :class:`Discovery` for this walk.
    :raises ValueError: When ``root`` is not a directory.
    """
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    logger.debug("discovering documents under %s", safe(root))
    documents: list[Document] = []
    hits = [0] * len(config.include)
    skipped = 0

    def raise_walk_error(error: OSError):
        """Re-raise directory walk errors encountered during os.walk."""
        raise error

    for current, directories, filenames in os.walk(root, topdown=True, onerror=raise_walk_error):
        current_path = Path(current)
        kept: list[str] = []
        for name in directories:
            relative_dir = (current_path / name).relative_to(root).as_posix()
            if (current_path / name).is_symlink():
                reason = "symlinked directory"
            elif any(prunes_directory(relative_dir, pattern) for pattern in config.exclude):
                reason = "excluded directory"
            else:
                kept.append(name)
                continue
            skipped += 1
            logger.debug("skipped %s: %s", safe(relative_dir), reason)
        directories[:] = kept
        for filename in filenames:
            path = current_path / filename
            if not path.is_file() or path.is_symlink():
                skipped += 1
                reason = "symlinked file" if path.is_symlink() else "not a regular file"
                logger.debug("skipped %s: %s", safe(path.relative_to(root).as_posix()), reason)
                continue
            relative = path.relative_to(root).as_posix()
            reason = _first_exclude_reason(relative, config.exclude)
            if reason is not None:
                skipped += 1
                logger.debug("skipped %s: %s", safe(relative), reason)
                continue
            matched = [selector_matches(relative, pattern, include=True) for pattern in config.include]
            if not any(matched):
                continue
            for index, hit in enumerate(matched):
                hits[index] += hit
            documents.append(Document(relative, path.stat().st_size))
    return Discovery(tuple(sorted(documents, key=lambda item: item.path)), skipped, tuple(hits))


def _first_exclude_reason(relative: str, patterns: Sequence[str]) -> Optional[str]:
    """Return the skip reason of the first exclude rule that removes a file.

    Path matches are tried for every pattern before directory-name matches, as the
    walk always did, so the logged reason is unchanged.

    :param relative: The file's scan-root-relative POSIX path.
    :param patterns: The effective exclude patterns.
    :returns: The skip reason, or ``None`` when no pattern removes the file.
    """
    reasons = [_exclude_reason(relative, pattern) for pattern in patterns]
    if "excluded" in reasons:
        return "excluded"
    if "excluded parent directory" in reasons:
        return "excluded parent directory"
    return None


@dataclass(frozen=True)
class InvokerSelection:
    """Normalised invoker selectors (ADR 0006 Contract 3).

    :ivar include: The normalised include replacement, or ``None`` when not given.
    :ivar exclude: The normalised exclude additions, ``()`` when not given.
    :ivar unmatched_exclude: Multi-component literal excludes that name nothing
        under the scan root (missing, or reached through a symlink); the engine
        logs one ``WARNING`` for each.
    """

    include: Optional[tuple[str, ...]]
    exclude: tuple[str, ...]
    unmatched_exclude: tuple[str, ...]


def selector_root_spellings(canonical_root: Path, spelled_root: Union[Path, str]) -> tuple[Path, ...]:
    """Return the scan-root spellings an absolute selector may be written under.

    The canonical root always; plus ``os.path.abspath(spelled_root)`` only when
    :func:`os.path.samefile` holds between it and the canonical root. The only
    filesystem calls are on the invoker's own root spelling, never on a selector
    value, and ``$PWD`` is never read (threat model A4).

    :param canonical_root: The resolved scan root.
    :param spelled_root: The scan root as the invoker wrote it.
    :returns: The canonical root, then the spelled root when it differs and is the
        same directory.
    """
    spellings = [canonical_root]
    spelled = Path(os.path.abspath(spelled_root))
    if os.fspath(spelled) != os.fspath(canonical_root):
        try:
            same = os.path.samefile(spelled, canonical_root)
        except OSError:
            same = False
        if same:
            spellings.append(spelled)
    return tuple(spellings)


def _refuse(key: str, value: str, reason: str) -> ConfigError:
    """Build a normaliser error that echoes one bounded, neutralised value.

    :param key: ``include`` or ``exclude``.
    :param value: The value to echo (raw or relative); passed through ``safe``.
    :param reason: One of the fixed reason phrases.
    :returns: The error, ready to raise.
    """
    joiner = " " if reason == _OUTSIDE_REASON else ": "
    return ConfigError(f"{key} value {safe(value, _ECHO_LIMIT)}{joiner}{reason}; {_RELATIVE_HINT}")


def _shape_error(message: str) -> ConfigError:
    """Build a shape error; it carries counts and limits only, never a value.

    :param message: The fixed shape message.
    :returns: The error, ready to raise.
    """
    return ConfigError(f"{message}; {_RELATIVE_HINT}")


def _check_shape(key: str, values: object) -> tuple[str, ...]:
    """Validate the container and items of one invoker key in the A8 order.

    Container type, emptiness, ``len() <= 256`` before iterating, then per item
    its type and ``len() <= 1024`` before any other processing.

    :param key: ``include`` or ``exclude``.
    :param values: The raw keyword or flag value (not ``None``).
    :returns: A snapshot tuple of plain ``str`` copies, so a mutable or
        ``str``-subclass input cannot change between the check and later use.
    :raises ConfigError: On the first shape violation (no value echoed).
    """
    if isinstance(values, (str, bytes, bytearray)):
        raise _shape_error(f"{key} must be a sequence of patterns, not a single string")
    if not isinstance(values, Sequence):
        raise _shape_error(f"{key} must be a sequence of patterns")
    if len(values) == 0:
        raise _shape_error(f"{key} needs at least one value")
    if len(values) > MAX_SELECTOR_VALUES:
        raise _shape_error(f"{key} accepts at most {MAX_SELECTOR_VALUES} values")
    for item in values:
        if not isinstance(item, str) or not item:
            raise _shape_error(f"{key} values must be nonempty strings")
        if len(item) > MAX_SELECTOR_LENGTH:
            raise _shape_error(f"{key} value is longer than {MAX_SELECTOR_LENGTH} characters")
    return tuple(str.__str__(item) for item in values)


def check_invoker_selector_shape(include: Optional[Sequence[str]], exclude: Optional[Sequence[str]]):
    """Run only the shape checks of ADR 0006 Contract 3 step 1 on invoker selectors.

    The engine calls this for every scan target, including a single-file one,
    before it decides to ignore the selectors (Contract 5 step 2), so a caller bug
    never passes silently. It makes no filesystem call and echoes no value; the
    checks are the same, in the same order, as :func:`normalize_invoker_selectors`.

    :param include: The invoker include values, or ``None`` when not given.
    :param exclude: The invoker exclude values, or ``None`` when not given.
    :raises ConfigError: On the first shape violation (no value echoed).
    """
    for key, values in (("include", include), ("exclude", exclude)):
        if values is not None:
            _check_shape(key, values)


def _check_windows_forms(key: str, value: str, backslash_is_separator: bool) -> bool:
    """Refuse drive, UNC and device forms lexically, on every platform (A3).

    :param key: ``include`` or ``exclude``.
    :param value: The raw value (characters already checked).
    :param backslash_is_separator: Whether ``\\`` is a path separator.
    :returns: Whether the value is an absolute ``X:\\...`` or ``X:/...`` path that
        the backslash-separator platform accepts as absolute.
    :raises ConfigError: For a refused form.
    """
    drive = ntpath.splitdrive(value)[0]
    leading_double = len(value) >= 2 and value[0] in _SEPARATORS and value[1] in _SEPARATORS
    letter_drive = len(drive) == 2 and drive[1] == ":" and drive[0].isascii() and drive[0].isalpha()
    drive_absolute = backslash_is_separator and letter_drive and value[2:3] in _SEPARATORS
    if leading_double or (drive and not drive_absolute):
        raise _refuse(key, value, _DRIVE_REASON)
    if not backslash_is_separator:
        return False
    rest = value[len(drive) :]
    if not drive and rest[:1] in _SEPARATORS:
        raise _refuse(key, value, _ROOTED_REASON)
    if ":" in rest:
        raise _refuse(key, value, _WINDOWS_NAME_REASON)
    for part in rest.replace("\\", "/").split("/"):
        if part not in ("", ".", "..") and part[-1] in ". ":
            raise _refuse(key, value, _WINDOWS_NAME_REASON)
    return drive_absolute


def _relative_to_spellings(key: str, value: str, absolute: str, spellings: tuple[str, ...]) -> str:
    """Make an absolute literal relative to the longest matching root spelling (A1).

    Purely lexical: ``os.path.normpath`` (parent steps are already refused, so it can
    only drop ``.``, repeated and trailing separators) and the separator-aware
    ``_within`` test of ``path_boundaries``. No filesystem call is made.

    :param key: ``include`` or ``exclude``.
    :param value: The value as given, echoed in the error.
    :param absolute: The absolute value after the backslash rule, ``/``-separated.
    :param spellings: The normalised root spellings, longest first.
    :returns: The ``/``-separated relative path, or ``"."`` for the root itself.
    :raises ConfigError: When the value is outside every spelling; the message
        does not depend on whether the outside path exists.
    """
    candidate = os.path.normpath(absolute)
    for spelling in spellings:
        if not _within(candidate, spelling):
            continue
        if candidate == spelling:
            return "."
        prefix = spelling if spelling.endswith(os.sep) else spelling + os.sep
        return candidate[len(prefix) :].replace(os.sep, "/")
    raise _refuse(key, value, _OUTSIDE_REASON)


def _lexical_normalize(
    key: str, value: str, spellings: tuple[str, ...], backslash_is_separator: bool
) -> tuple[str, ...]:
    """Run Contract 3 steps 2 to 8 on one value, with no filesystem call.

    :param key: ``include`` or ``exclude``.
    :param value: One shape-checked value.
    :param spellings: The normalised root spellings, longest first.
    :param backslash_is_separator: Whether ``\\`` is a path separator.
    :returns: The normalised pattern (two patterns for an include of ``.``).
    :raises ConfigError: For a refused value.
    """
    if neutralize(value) != value:
        raise _refuse(key, value, _CHARACTER_REASON)
    drive_absolute = _check_windows_forms(key, value, backslash_is_separator)
    if "\\" in value:
        if not backslash_is_separator:
            raise _refuse(key, value, _BACKSLASH_REASON)
        text = value.replace("\\", "/")
    else:
        text = value
    if ".." in text.split("/"):
        raise _refuse(key, value, _PARENT_REASON)
    if text.startswith("/") or drive_absolute:
        if is_glob(text):
            raise _refuse(key, value, _ABSOLUTE_GLOB_REASON)
        text = _relative_to_spellings(key, value, text, spellings)
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if not parts:
        if "." not in text.split("/"):
            raise _refuse(key, value, _EMPTY_REASON)
        if key == "exclude":
            raise _refuse(key, value, _EXCLUDE_ROOT_REASON)
        return Config().include
    return ("/".join(parts),)


def _check_literal(scan_root: Path, key: str, literal: str) -> bool:
    """Run Contract 3 steps 9 and 10 on one in-root literal.

    The only filesystem calls are the :func:`contained_path` walk of the lexical
    join (which never leaves ``scan_root``) and one ``os.lstat`` of its result.

    :param scan_root: The canonical scan root.
    :param key: ``include`` or ``exclude``.
    :param literal: The normalised relative literal.
    :returns: ``True`` when the literal names an existing, non-symlinked object;
        ``False`` for an exclude that is missing or reached through a symlink.
    :raises ConfigError: For an escape, an include that is missing, symlinked or
        not a regular file or directory, or an ``OSError`` while checking.
    """
    lexical = scan_root.joinpath(*literal.split("/"))
    try:
        contained = contained_path(scan_root, lexical)
        if contained is None:
            raise _refuse(key, literal, _SYMLINK_ESCAPE_REASON)
        symlinked = os.fspath(contained) != os.fspath(lexical)
        try:
            info: Optional[os.stat_result] = os.lstat(contained)
        except (FileNotFoundError, NotADirectoryError):
            info = None
    except OSError as error:
        reason = safe(error.strerror or type(error).__name__, _ECHO_LIMIT)
        raise _refuse(key, literal, f"cannot check it ({reason})") from None
    symlinked = symlinked or (info is not None and stat.S_ISLNK(info.st_mode))
    if key == "exclude":
        return info is not None and not symlinked
    if symlinked:
        raise _refuse(key, literal, _SYMLINKED_REASON)
    if info is None:
        raise _refuse(key, literal, _MISSING_REASON)
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise _refuse(key, literal, _NOT_REGULAR_REASON)
    return True


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    """Return ``values`` once each, in first-occurrence order.

    :param values: Normalised patterns.
    :returns: The deduplicated tuple.
    """
    return tuple(dict.fromkeys(values))


def normalize_invoker_selectors(
    scan_root: Path,
    include: Optional[Sequence[str]],
    exclude: Optional[Sequence[str]],
    *,
    root_spellings: tuple[Path, ...] = (),
    backslash_is_separator: Optional[bool] = None,
) -> InvokerSelection:
    """Validate and normalise invoker selectors (ADR 0006 Contract 3).

    The shape of both keys is checked first, then every value of both keys runs
    the lexical steps (characters, drive/UNC/device forms, backslash, parent steps,
    absolute values against the root spellings, clean-up, ``.``) and is
    deduplicated, all with no filesystem call. Only then is each literal walked
    with :func:`contained_path` and ``os.lstat``-ed once inside the root. Globs never
    reach the filesystem. No Unicode normalisation or case folding is applied, and
    nothing is logged: the caller logs the unmatched-exclude ``WARNING``.

    :param scan_root: The canonical (resolved) scan root.
    :param include: The invoker include values, or ``None`` when not given.
    :param exclude: The invoker exclude values, or ``None`` when not given.
    :param root_spellings: Extra spellings an absolute value may be written under,
        from :func:`selector_root_spellings`; the canonical root always counts.
    :param backslash_is_separator: Whether ``\\`` is a path separator; ``None``
        means ``os.sep == "\\\\"``.
    :returns: The normalised selection.
    :raises ConfigError: For any refused value, before discovery; the message
        echoes a value only through ``safe(value, 200)``.
    """
    windows = os.sep == "\\" if backslash_is_separator is None else backslash_is_separator
    given = {
        key: _check_shape(key, values)
        for key, values in (("include", include), ("exclude", exclude))
        if values is not None
    }
    spelling_set = {os.path.normpath(os.fspath(path)) for path in (scan_root, *root_spellings)}
    spellings = tuple(sorted(spelling_set, key=lambda text: (-len(text), text)))
    normalised = {
        key: _unique([pattern for value in values for pattern in _lexical_normalize(key, value, spellings, windows)])
        for key, values in given.items()
    }
    unmatched: list[str] = []
    for key, patterns in normalised.items():
        for pattern in patterns:
            if is_glob(pattern):
                continue
            if not _check_literal(scan_root, key, pattern) and "/" in pattern:
                unmatched.append(pattern)
    return InvokerSelection(
        include=normalised.get("include"),
        exclude=normalised.get("exclude", ()),
        unmatched_exclude=tuple(unmatched),
    )
