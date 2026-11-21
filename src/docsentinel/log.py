"""Logging wrapper for DocSentinel (``docs/specs/logging.md``).

The library stays quiet: importing this module only attaches a ``NullHandler`` to
the ``docsentinel`` logger, so an embedding application decides where records go.
Only the CLI calls :func:`configure_cli_logging`, which adds a stderr handler and a
per-run log file, and :func:`shutdown_cli_logging`, which removes and closes them.

Every untrusted string (paths, link targets, config values, exception messages)
reaches a log record only through :func:`safe`, which neutralises control, bidi and
zero-width code points and caps the length, so a crafted file name cannot forge a
log line or carry a terminal escape sequence.
"""

import errno
import logging
import os
import re
import stat
import sys
import time
import traceback
from collections.abc import Mapping
from pathlib import Path
from typing import Final, Optional

from docsentinel.telemetry.filters import neutralize

#: Name of the package logger every module logger descends from.
LOGGER_NAME: Final[str] = "docsentinel"
#: Environment variable overriding the log directory.
LOG_DIR_ENV: Final[str] = "DOCSENTINEL_LOG_DIR"
#: Environment variable naming how many per-run log files rotation keeps.
LOG_KEEP_ENV: Final[str] = "DOCSENTINEL_LOG_KEEP"
#: Environment variable overriding the stderr level with a level name.
LOG_LEVEL_ENV: Final[str] = "DOCSENTINEL_LOG_LEVEL"
#: Number of per-run log files kept when ``DOCSENTINEL_LOG_KEEP`` is unset or invalid.
DEFAULT_KEEP: Final[int] = 20
#: Smallest accepted ``DOCSENTINEL_LOG_KEEP``; the current run's file is always kept.
MIN_KEEP: Final[int] = 1
#: Default character cap of :func:`safe`.
SAFE_LIMIT: Final[int] = 200
#: Marker appended by :func:`safe` when it truncates a value.
TRUNCATION_MARKER: Final[str] = "..."
#: The only file names rotation ever deletes: ``docsentinel-<date>-<time>-<pid>.log``,
#: optionally with the ``-<n>`` suffix a name collision adds.
LOG_FILE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^docsentinel-\d{8}-\d{6}-\d+(?:-\d+)?\.log$")
#: How many ``-<n>`` suffixes :func:`_open_log_file` tries after a name collision.
MAX_NAME_ATTEMPTS: Final[int] = 100
#: Rotation never deletes a log file modified less than this many seconds ago, so
#: two concurrent runs cannot delete each other's live file.
ROTATION_GRACE_SECONDS: Final[int] = 60
#: Format of the per-run log file.
FILE_FORMAT: Final[str] = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
#: Stderr format for ``WARNING`` and above.
STDERR_PROBLEM_FORMAT: Final[str] = "docsentinel: %(levelname)s: %(message)s"
#: Stderr format below ``WARNING``.
STDERR_INFO_FORMAT: Final[str] = "docsentinel: %(message)s"
#: ``extra=`` mapping for a record that belongs in the log file only, such as the
#: one-line record of an error the CLI already printed to stderr in its own words.
FILE_ONLY: Final[Mapping[str, bool]] = {"docsentinel_file_only": True}

#: Accepted ``DOCSENTINEL_LOG_LEVEL`` names.
_LEVEL_NAMES: Final[Mapping[str, int]] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
#: Attribute marking a handler added by :func:`configure_cli_logging`.
_CLI_HANDLER_MARK: Final[str] = "_docsentinel_cli_handler"
#: Attribute on the stderr handler holding the package logger level to restore.
_SAVED_LEVEL_ATTR: Final[str] = "_docsentinel_saved_level"

logger = logging.getLogger(LOGGER_NAME)
logger.addHandler(logging.NullHandler())


def safe(value: object, limit: int = SAFE_LIMIT) -> str:
    """Return ``value`` as text that is safe to place in a log record.

    The text is ``str(value)`` with every control, bidi, zero-width, separator and
    lone-surrogate code point rendered as a visible ASCII escape (the same table as
    ``reporting.neutralize_text``, which also rewrites the GitHub legacy command
    marker ``##[`` as ``##\\[``), then capped at ``limit`` characters with
    ``...`` appended when anything was cut.

    :param value: Any object; untrusted text such as a path or an exception.
    :param limit: Maximum characters kept before the truncation marker (at least 1).
    :returns: The neutralised, length-capped text.
    :raises ValueError: When ``limit`` is below 1.
    """
    if limit < 1:
        raise ValueError(f"safe() limit must be at least 1, got {limit}")
    text = value if isinstance(value, str) else str(value)
    # Neutralising only ever lengthens text, so limit + 1 raw characters are enough
    # to decide truncation without escaping an arbitrarily long value.
    shown = neutralize(text[: limit + 1])
    if len(text) > limit or len(shown) > limit:
        return shown[:limit] + TRUNCATION_MARKER
    return shown


def _neutralize_lines(text: str) -> str:
    """Neutralise every line of trusted multi-line text, keeping its line breaks.

    :param text: Text whose line breaks are structure, such as traceback frames.
    :returns: ``text`` with each line passed through ``neutralize``.
    """
    return "\n".join(neutralize(line) for line in text.split("\n"))


def _exception_only_chunks(root: traceback.TracebackException) -> set[str]:
    """Return the ``Type: message`` chunks of ``root`` and of every chained exception.

    These chunks embed ``str(exception)``, which can carry scanned text; every other
    traceback chunk (frames, chain separators) is produced by the interpreter.

    :param root: The outermost traceback.
    :returns: Every chunk ``format_exception_only`` yields across the chain.
    """
    chunks: set[str] = set()
    seen: set[int] = set()
    pending = [root]
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        chunks.update(current.format_exception_only())
        pending.extend(item for item in (current.__cause__, current.__context__) if item is not None)
        pending.extend(getattr(current, "exceptions", None) or ())
    return chunks


class _FileFormatter(logging.Formatter):
    """Format log-file records, neutralising tracebacks and stack dumps.

    The message is already built from :func:`safe` arguments. A traceback is not:
    ``str(exc)`` can embed scanned text, including newlines that would forge a
    record. Each ``Type: message`` chunk is therefore neutralised as one line (its
    embedded newlines become ``\\x0a``), and every other line keeps its frame
    break and is neutralised on its own.
    """

    def formatException(self, ei) -> str:
        """Return the neutralised traceback of ``ei``.

        :param ei: The ``(type, value, traceback)`` triple of the record.
        :returns: The traceback text, one neutralised line per frame line.
        """
        if ei[1] is None:
            return _neutralize_lines(super().formatException(ei))
        trace = traceback.TracebackException(ei[0], ei[1], ei[2])
        untrusted = _exception_only_chunks(trace)
        pieces: list[str] = []
        for chunk in trace.format():
            body = chunk.removesuffix("\n")
            pieces.append(neutralize(body) if chunk in untrusted else _neutralize_lines(body))
        return "\n".join(pieces)

    def formatStack(self, stack_info: str) -> str:
        """Return ``stack_info`` with every line neutralised.

        :param stack_info: The stack dump of a ``stack_info=True`` record.
        :returns: The neutralised dump.
        """
        return _neutralize_lines(stack_info)


class _StderrFormatter(logging.Formatter):
    """Format stderr records: ``docsentinel: LEVEL: msg`` for problems, ``docsentinel: msg`` below.

    Tracebacks are never printed to stderr; ``logger.exception`` sends them to the
    log file only, whose path the CLI prints on failure.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Return the one-line stderr form of ``record``.

        :param record: The record to format.
        :returns: The formatted line without a traceback.
        """
        message = record.getMessage()
        if record.levelno >= logging.WARNING:
            return f"docsentinel: {record.levelname}: {message}"
        return f"docsentinel: {message}"


def _not_file_only(record: logging.LogRecord) -> bool:
    """Return whether ``record`` may reach stderr (it was not logged with :data:`FILE_ONLY`).

    :param record: The record to test.
    :returns: ``False`` for a file-only record.
    """
    return not getattr(record, "docsentinel_file_only", False)


class _OwnedStreamHandler(logging.StreamHandler):
    """A stream handler that owns, and therefore closes, the per-run log file stream."""

    def close(self):
        """Flush and close the handler and its file stream."""
        self.acquire()
        try:
            stream = self.stream
            if stream is not None and not stream.closed:
                stream.flush()
                stream.close()
        finally:
            self.release()
            super().close()


def _stderr_level(verbosity: int, env: Mapping[str, str], problems: list[str]) -> int:
    """Return the stderr level for ``verbosity``, honouring ``DOCSENTINEL_LOG_LEVEL``.

    :param verbosity: ``-1`` for ``--quiet``, ``0`` by default, ``1`` or more for ``--verbose``.
    :param env: The environment to read.
    :param problems: Collects a warning message for an invalid override.
    :returns: The ``logging`` level number.
    """
    if verbosity < 0:
        level = logging.WARNING
    elif verbosity == 0:
        level = logging.INFO
    else:
        level = logging.DEBUG
    override = env.get(LOG_LEVEL_ENV)
    if override is None or override.strip() == "":
        return level
    named = _LEVEL_NAMES.get(override.strip().upper())
    if named is None:
        problems.append(
            f"ignoring invalid {LOG_LEVEL_ENV}={safe(override, 40)}; expected one of {', '.join(_LEVEL_NAMES)}"
        )
        return level
    return named


def _keep_count(env: Mapping[str, str], problems: list[str]) -> int:
    """Return how many per-run log files rotation keeps.

    :param env: The environment to read.
    :param problems: Collects a warning message for an invalid or too small value.
    :returns: ``DOCSENTINEL_LOG_KEEP`` as an integer of at least :data:`MIN_KEEP`; the
        default for an unset or non-integer value, :data:`MIN_KEEP` for a smaller one.
    """
    raw = env.get(LOG_KEEP_ENV)
    if raw is None or raw.strip() == "":
        return DEFAULT_KEEP
    try:
        keep = int(raw.strip())
    except ValueError:
        problems.append(f"ignoring invalid {LOG_KEEP_ENV}={safe(raw, 40)}; keeping {DEFAULT_KEEP} log files")
        return DEFAULT_KEEP
    if keep < MIN_KEEP:
        problems.append(f"{LOG_KEEP_ENV}={keep} is below {MIN_KEEP}; keeping {MIN_KEEP} log file")
        return MIN_KEEP
    return keep


def _log_directory(env: Mapping[str, str]) -> Path:
    """Return the log directory: ``DOCSENTINEL_LOG_DIR`` or ``~/.local/logs/docsentinel``.

    :param env: The environment to read.
    :returns: The directory path (not yet created).
    :raises RuntimeError: When no override is set and the home directory is unknown.
    """
    override = env.get(LOG_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".local" / "logs" / "docsentinel"


def _check_private_directory(directory: Path):
    """Require ``directory`` to be a real directory only the current user can write.

    ``lstat`` (never following a symlink) must show a directory, and on POSIX one
    owned by the effective user with no group or other write bit, like ``ssh``
    requires of its own directories. Otherwise another local user could plant a
    hard link or swap files under the log's name.

    :param directory: The existing log directory.
    :raises OSError: When it is a symlink, not a directory, owned by someone else,
        or writable by group or others.
    """
    info = os.lstat(directory)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise OSError(f"{safe(directory)} is not a directory (symlinks are refused)")
    if not hasattr(os, "geteuid"):
        return
    if info.st_uid != os.geteuid():
        raise OSError(f"{safe(directory)} is not owned by the current user")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise OSError(f"{safe(directory)} is writable by group or others")


def _ensure_directory(directory: Path):
    """Create ``directory`` (and parents) with mode ``0o700`` when it does not exist.

    An existing directory is never changed, but it must pass
    :func:`_check_private_directory`; so must the directory created here.

    :param directory: The log directory.
    :raises OSError: When the directory cannot be created, or is not a private
        directory of the current user.
    """
    if not os.path.lexists(directory):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        # mkdir applies the umask; make the mode exact for the directory we just created.
        _make_private(directory)
    _check_private_directory(directory)


def _make_private(directory: Path):
    """Set mode ``0o700`` on a directory this run just created, never through a symlink.

    :param directory: The new log directory.
    :raises OSError: When it cannot be opened as a directory or its mode cannot be set.
    """
    if not (hasattr(os, "fchmod") and hasattr(os, "O_DIRECTORY")):
        os.chmod(directory, 0o700)
        return
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fchmod(descriptor, 0o700)
    finally:
        os.close(descriptor)


#: ``os.open`` flags for a new log file: it must not exist yet (``O_EXCL``, so a
#: pre-planted file or hard link is never opened) and must not be a symlink.
_CREATE_FLAGS: Final[int] = (
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
)


def _create_exclusive(directory: Path, stem: str) -> tuple[Path, int]:
    """Create a new file ``<stem>.log`` (or ``<stem>-<n>.log``) in ``directory``.

    :param directory: The log directory.
    :param stem: ``docsentinel-<YYYYmmdd-HHMMSS>-<pid>``.
    :returns: The created path and its open descriptor.
    :raises OSError: When no free name is found or the file cannot be created.
    """
    for attempt in range(MAX_NAME_ATTEMPTS):
        name = f"{stem}.log" if attempt == 0 else f"{stem}-{attempt}.log"
        path = directory / name
        try:
            return path, os.open(path, _CREATE_FLAGS, 0o600)
        except FileExistsError:
            # Never open an existing entry: it may be a planted file or hard link.
            logger.debug("log file name %s is taken; trying the next suffix", safe(name))
    raise OSError(errno.EEXIST, f"no free log file name for {stem} after {MAX_NAME_ATTEMPTS} attempts")


def _open_log_file(directory: Path) -> tuple[Path, logging.Handler]:
    """Create this run's log file and return it with its file handler.

    The file is ``docsentinel-<YYYYmmdd-HHMMSS>-<pid>.log`` (local time), created
    with ``O_CREAT|O_EXCL|O_NOFOLLOW`` and mode ``0o600``, so an existing file, hard
    link or symlink under that name is never opened. When the name is taken (a
    second CLI call in the same process and second), ``-1``, ``-2`` ... is appended.
    The new file must be a regular file owned by us with exactly one link.

    :param directory: The existing log directory.
    :returns: The file path and a DEBUG-level UTF-8 handler writing to it.
    :raises OSError: When the file cannot be created or fails those checks.
    """
    stem = f"docsentinel-{time.strftime('%Y%m%d-%H%M%S', time.localtime())}-{os.getpid()}"
    path, descriptor = _create_exclusive(directory, stem)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or (hasattr(os, "geteuid") and info.st_uid != os.geteuid()):
            raise OSError(f"{path.name} is not a regular file owned by the current user")
        if info.st_nlink != 1:
            raise OSError(f"{path.name} has {info.st_nlink} hard links; expected 1")
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        stream = open(descriptor, "a", encoding="utf-8", errors="backslashreplace", closefd=True)
    except OSError:
        os.close(descriptor)
        raise
    handler = _OwnedStreamHandler(stream)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(_FileFormatter(FILE_FORMAT))
    return path, handler


def _rotation_candidates(directory: Path, current: Path, now_ns: int) -> list[tuple[int, str, str]]:
    """Return ``(mtime_ns, name, path)`` of the log files rotation may count and delete.

    A candidate's name matches :data:`LOG_FILE_PATTERN` exactly, it is a regular
    file (symlinks are never followed), it is owned by the effective user, it is not
    ``current``, and its modification time is not in the future. A future time
    would otherwise let a planted file outrank, and so evict, the real logs.

    :param directory: The log directory.
    :param current: This run's log file.
    :param now_ns: The current time in nanoseconds since the epoch.
    :returns: The candidates in no particular order.
    :raises OSError: When the directory cannot be listed.
    """
    owner = os.geteuid() if hasattr(os, "geteuid") else None
    candidates: list[tuple[int, str, str]] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if LOG_FILE_PATTERN.match(entry.name) is None or entry.name == current.name:
                continue
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                continue
            info = entry.stat(follow_symlinks=False)
            if (owner is not None and info.st_uid != owner) or info.st_mtime_ns > now_ns:
                continue
            candidates.append((info.st_mtime_ns, entry.name, entry.path))
    return candidates


def _rotate(directory: Path, current: Path, keep: int):
    """Delete all but the newest ``keep`` per-run log files in ``directory``.

    Only :func:`_rotation_candidates` are counted or deleted, and ``current`` is
    never deleted. Newest means the latest modification time, then the greater
    name. A file modified less than :data:`ROTATION_GRACE_SECONDS` ago is counted
    but kept, so a concurrent run's live file survives.

    :param directory: The log directory.
    :param current: This run's log file.
    :param keep: How many files to keep, ``current`` included.
    """
    now_ns = time.time_ns()
    try:
        candidates = _rotation_candidates(directory, current, now_ns)
    except OSError as exc:
        logger.error("could not list the log directory for rotation: %s", safe(exc.strerror or exc))
        return
    candidates.sort(reverse=True)
    grace_start = now_ns - ROTATION_GRACE_SECONDS * 1_000_000_000
    for modified, name, entry_path in candidates[max(keep - 1, 0) :]:
        if modified > grace_start:
            logger.debug("kept recent log file %s", safe(name))
            continue
        try:
            os.unlink(entry_path)
        except OSError as exc:
            logger.error("could not delete old log file %s: %s", safe(name), safe(exc.strerror or exc))
        else:
            logger.debug("deleted old log file %s", safe(name))


def shutdown_cli_logging() -> "None":
    """Remove and close every handler :func:`configure_cli_logging` added.

    Restores the ``docsentinel`` logger level it changed. Safe to call when logging
    was never configured, and more than once.
    """
    package_logger = logging.getLogger(LOGGER_NAME)
    for handler in list(package_logger.handlers):
        if not getattr(handler, _CLI_HANDLER_MARK, False):
            continue
        package_logger.removeHandler(handler)
        if hasattr(handler, _SAVED_LEVEL_ATTR):
            package_logger.setLevel(getattr(handler, _SAVED_LEVEL_ATTR))
        # The stderr stream may already be closed (a replaced sys.stderr torn down first).
        if not getattr(getattr(handler, "stream", None), "closed", False):
            handler.flush()
        handler.close()


def configure_cli_logging(*, verbosity: int = 0, env: Optional[Mapping[str, str]] = None) -> Optional[Path]:
    """Attach the CLI's stderr handler and per-run log file to the ``docsentinel`` logger.

    Idempotent: handlers from an earlier call are removed and closed first, so
    repeated ``cli.main`` calls in one process never stack handlers. Never raises
    for a logging problem: when the log directory or file cannot be created, the
    run continues with stderr only and one ``WARNING`` names the reason.

    :param verbosity: ``-1`` (``--quiet``, stderr ``WARNING``), ``0`` (``INFO``) or
        ``1`` and more (``--verbose``, ``DEBUG``); ``DOCSENTINEL_LOG_LEVEL`` overrides it.
    :param env: The environment to read; ``os.environ`` when omitted.
    :returns: The per-run log file path, or ``None`` when it could not be created.
    """
    environment = os.environ if env is None else env
    shutdown_cli_logging()
    package_logger = logging.getLogger(LOGGER_NAME)
    problems: list[str] = []

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(_stderr_level(verbosity, environment, problems))
    stderr_handler.setFormatter(_StderrFormatter())
    stderr_handler.addFilter(_not_file_only)
    setattr(stderr_handler, _CLI_HANDLER_MARK, True)
    setattr(stderr_handler, _SAVED_LEVEL_ATTR, package_logger.level)
    package_logger.addHandler(stderr_handler)
    package_logger.setLevel(logging.DEBUG)

    keep = _keep_count(environment, problems)
    log_path: Optional[Path] = None
    try:
        directory = _log_directory(environment)
        _ensure_directory(directory)
        log_path, file_handler = _open_log_file(directory)
    except (OSError, RuntimeError) as exc:
        problems.append(f"log file disabled, logging to stderr only: {safe(exc)}")
    else:
        setattr(file_handler, _CLI_HANDLER_MARK, True)
        package_logger.addHandler(file_handler)

    for problem in problems:
        logger.warning("%s", problem)
    if log_path is not None:
        _rotate(log_path.parent, log_path, keep)
        logger.debug("log file: %s", safe(log_path))
    return log_path
