"""Unit tests for :mod:`docsentinel.log`, the logging wrapper of ``docs/specs/logging.md``.

Each test configures CLI logging against an explicit ``env`` mapping that points the
log directory at ``tmp_path``, logs a record or two, and checks stderr (``capsys``),
the per-run file and the rotation result. The autouse ``_isolated_cli_logging``
fixture in ``tests/conftest.py`` closes the handlers after every test.
"""

import logging
import os
import re
import stat
from pathlib import Path

import pytest

from docsentinel import log
from docsentinel.log import FILE_ONLY, configure_cli_logging, quote_start, safe, shutdown_cli_logging
from tests.log_helpers import TIMESTAMP_PATTERN, without_timestamps

ESC = chr(0x1B)
RLO = chr(0x202E)
_LOG_NAME = re.compile(r"^docsentinel-\d{8}-\d{6}-\d+\.log$")
_PACKAGE = logging.getLogger("docsentinel")


def _env(tmp_path: Path, **extra: str) -> dict[str, str]:
    """Return an environment whose log directory is ``tmp_path/logs`` plus ``extra``."""
    return {"DOCSENTINEL_LOG_DIR": str(tmp_path / "logs"), **extra}


def _cli_handlers() -> list[logging.Handler]:
    """Return the handlers ``configure_cli_logging`` attached to the package logger."""
    return [handler for handler in _PACKAGE.handlers if getattr(handler, "_docsentinel_cli_handler", False)]


def test_safe_neutralizes_control_and_bidi_characters():
    """
    [Unit] log safe: verifies ESC, CR, LF and a bidi override become visible escapes.

    Scenario:
        Given a value carrying an ANSI escape, CR, LF and U+202E
        When ``safe`` renders it
        Then none of those raw code points survive and each appears as a backslash escape.

    Boundaries:
        - Focus: the neutralize table reused from ``telemetry.filters``
        - Fixtures/params: none
        - Scope: one call

    On failure, first check:
        - ``log.safe`` still calls ``telemetry.filters.neutralize``
    """
    shown = safe(f"a{ESC}[31m\r\nforged line{RLO}b")

    for raw in (ESC, "\r", "\n", RLO):
        assert raw not in shown
    assert "\\x1b" in shown and "\\x0d" in shown and "\\x0a" in shown and "\\u202e" in shown


def test_safe_caps_length_with_a_marker():
    """
    [Unit] log safe: verifies a long value is cut at the limit and marked, a short one is not.

    Scenario:
        Given values of 500, exactly 200 and 199 characters, and 100 ESC characters
        When ``safe`` renders them with the default limit of 200
        Then the long one is 200 characters plus ``...``, the 200/199 ones are unchanged, and the
            escaped ESC run (400 characters once escaped) is capped too.

    Boundaries:
        - Focus: the cap applies to the neutralised output, so escaping cannot exceed it
        - Fixtures/params: none
        - Scope: four calls

    On failure, first check:
        - The truncation condition in ``log.safe``
    """
    assert safe("x" * 500) == "x" * 200 + "..."
    assert safe("y" * 200) == "y" * 200
    assert safe("z" * 199) == "z" * 199
    capped = safe(ESC * 100)
    assert len(capped) == 203 and capped.endswith("...") and ESC not in capped


def test_safe_accepts_any_object_and_a_custom_limit():
    """
    [Unit] log safe: verifies non-string values are rendered with ``str`` and ``limit`` is honoured.

    Scenario:
        Given a Path, an exception whose message ends in a newline, an int, and a custom limit
        When ``safe`` renders them
        Then each is its ``str`` form, neutralised, and the custom limit cuts at 3 characters.

    Boundaries:
        - Focus: the ``object`` parameter type
        - Fixtures/params: none
        - Scope: four calls

    On failure, first check:
        - The ``str(value)`` conversion in ``log.safe``
    """
    assert safe(Path("docs/a.md")) == "docs/a.md"
    assert safe(ValueError("boom\n")) == "boom\\x0a"
    assert safe(42) == "42"
    assert safe("abcdef", limit=3) == "abc..."


def test_safe_rejects_a_limit_below_one():
    """
    [Unit] log safe: verifies a limit of 0 is refused instead of returning only the marker.

    Scenario:
        Given ``limit=0``
        When ``safe`` is called
        Then it raises ``ValueError``.

    Boundaries:
        - Focus: invalid input
        - Fixtures/params: none
        - Scope: one call

    On failure, first check:
        - The limit guard at the top of ``log.safe``
    """
    with pytest.raises(ValueError, match="at least 1"):
        safe("value", limit=0)


@pytest.mark.parametrize(
    ("text", "words", "expected"),
    [
        (
            "one two three four five six seven eight nine ten eleven",
            10,
            '"one two three four five six seven eight nine ten ..."',
        ),
        ("one two three four five six seven eight nine ten", 10, '"one two three four five six seven eight nine ten"'),
        ("  spaced\tout\n words  ", 10, '"spaced out words"'),
        ("alpha beta gamma", 2, '"alpha beta ..."'),
        ("", 10, '""'),
    ],
)
def test_quote_start_keeps_the_first_words(text: str, words: int, expected: str):
    """
    [Unit] log quote_start: verifies the first words are quoted and ``...`` marks a cut.

    Scenario:
        Given texts longer, exactly as long and shorter than the word limit, odd whitespace and empty text
        When quote_start quotes them
        Then the first ``words`` words are joined by one space in double quotes, with `` ...`` only
            when words were left out.

    Boundaries:
        - Focus: the DS302 and lenz claim trace (owner ruling 2026-11-27)
        - Fixtures/params: text, words, expected
        - Scope: one call each

    On failure, first check:
        - The split and join in ``quote_start``

    :param text: The text to quote.
    :param words: The word limit.
    :param expected: The quoted result.
    """
    assert quote_start(text, words) == expected


def test_quote_start_neutralizes_and_rejects_a_bad_limit():
    """
    [Unit] log quote_start: verifies controls and ``##[`` are neutralised and a limit below 1 is refused.

    Scenario:
        Given a word holding an ESC sequence and the GitHub command marker, and a limit of 0
        When quote_start quotes them
        Then the quote shows visible escapes, never ESC or ``##[``, and the bad limit raises ValueError.

    Boundaries:
        - Focus: untrusted claim text reaching a log record
        - Fixtures/params: none
        - Scope: two calls

    On failure, first check:
        - The ``safe`` call and the ``words < 1`` guard in ``quote_start``
    """
    quoted = quote_start("bad" + ESC + "[31m ##[error]x")

    assert quoted == '"bad\\x1b[31m ##\\[error]x"'
    with pytest.raises(ValueError, match="at least 1"):
        quote_start("value", words=0)


def test_configure_creates_private_per_run_file_in_private_directory(tmp_path: Path):
    """
    [Unit] log configure: verifies the per-run file is 0o600, its new directory 0o700, and it gets DEBUG records.

    Scenario:
        Given a log directory that does not exist yet
        When CLI logging is configured and a DEBUG record is logged and the handlers are shut down
        Then the returned path is ``docsentinel-<YYYYmmdd-HHMMSS>-<pid>.log`` in a 0o700 directory, mode 0o600,
            and holds the DEBUG record in the spec's file format.

    Boundaries:
        - Focus: spec §2 directory, file name, file mode and file level
        - Fixtures/params: tmp_path
        - Scope: one configure call

    On failure, first check:
        - ``_ensure_directory`` and ``_open_log_file`` in ``docsentinel.log``
    """
    path = configure_cli_logging(env=_env(tmp_path))
    logging.getLogger("docsentinel.unit").debug("checking %s", safe("a.md"))
    shutdown_cli_logging()

    assert path is not None and path.parent == tmp_path / "logs"
    assert _LOG_NAME.match(path.name)
    assert str(os.getpid()) in path.name
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^" + TIMESTAMP_PATTERN + r"\[DEBUG\]: checking a\.md$", text, re.MULTILINE)


def _old_log(directory: Path, name: str, age: int) -> Path:
    """Create ``directory/name`` with a modification time ``age`` hours in the past."""
    path = directory / name
    path.write_text("old\n", encoding="utf-8")
    moment = path.stat().st_mtime - age * 3600
    os.utime(path, (moment, moment))
    return path


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks are not available")
def test_rotation_keeps_newest_and_touches_nothing_else(tmp_path: Path):
    """
    [Unit] log rotation: verifies only the newest matching regular files are kept and nothing else is deleted.

    Scenario:
        Given five old ``docsentinel-*.log`` files, a non-matching ``other.log``, a ``docsentinel-x.txt``,
            a directory named ``docsentinel-dir.log`` and a symlink ``docsentinel-link.log`` to an outside file
        When CLI logging is configured with ``DOCSENTINEL_LOG_KEEP=3``
        Then the current file and the two newest old files remain, the three oldest are deleted, and every
            non-matching entry, the directory, the symlink and its target are untouched.

    Boundaries:
        - Focus: spec §2 rotation (pattern only, no symlink following)
        - Fixtures/params: tmp_path
        - Scope: one configure call

    On failure, first check:
        - ``_rotate`` in ``docsentinel.log``: the pattern, the symlink skip and the keep arithmetic
    """
    logs = tmp_path / "logs"
    logs.mkdir()
    old = [_old_log(logs, f"docsentinel-2020010{index}-000000-1.log", age=10 - index) for index in range(5)]
    other = _old_log(logs, "other.log", age=50)
    text = _old_log(logs, "docsentinel-x.txt", age=50)
    (logs / "docsentinel-dir.log").mkdir()
    outside = tmp_path / "outside.log"
    outside.write_text("keep me\n", encoding="utf-8")
    os.symlink(outside, logs / "docsentinel-link.log")

    current = configure_cli_logging(env=_env(tmp_path, DOCSENTINEL_LOG_KEEP="3"))

    assert current is not None and current.exists()
    assert [path.exists() for path in old] == [False, False, False, True, True]
    assert other.exists() and text.exists() and (logs / "docsentinel-dir.log").is_dir()
    assert (logs / "docsentinel-link.log").is_symlink() and outside.read_text(encoding="utf-8") == "keep me\n"


@pytest.mark.parametrize(
    ("value", "kept", "warning"),
    [
        ("abc", 20, "ignoring invalid DOCSENTINEL_LOG_KEEP=abc; keeping 20 log files"),
        ("0", 1, "DOCSENTINEL_LOG_KEEP=0 is below 1; keeping 1 log file"),
        ("-4", 1, "DOCSENTINEL_LOG_KEEP=-4 is below 1; keeping 1 log file"),
    ],
)
def test_invalid_or_too_small_keep_warns_and_falls_back(
    value: str, kept: int, warning: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] log rotation: verifies an invalid KEEP uses the default and a too small one the minimum, with a WARNING.

    Scenario:
        Given 25 old per-run log files and ``DOCSENTINEL_LOG_KEEP`` set to ``abc``, ``0`` or ``-4``
        When CLI logging is configured
        Then one WARNING line names the fallback and exactly 20 (default) or 1 (minimum) files remain.

    Boundaries:
        - Focus: ``_keep_count`` fallbacks
        - Fixtures/params: three values
        - Scope: one configure call per value

    On failure, first check:
        - ``_keep_count`` in ``docsentinel.log``
    """
    logs = tmp_path / "logs"
    logs.mkdir()
    for index in range(25):
        _old_log(logs, f"docsentinel-20200101-0000{index:02d}-1.log", age=100 - index)

    configure_cli_logging(env=_env(tmp_path, DOCSENTINEL_LOG_KEEP=value))

    assert len(list(logs.glob("docsentinel-*.log"))) == kept
    assert without_timestamps(capsys.readouterr().err) == f"[WARNING]: {warning}\n"


@pytest.mark.parametrize(
    ("verbosity", "shown"),
    [(-1, ["WARNING"]), (0, ["INFO", "WARNING"]), (1, ["DEBUG", "INFO", "WARNING"]), (3, ["DEBUG", "INFO", "WARNING"])],
)
def test_verbosity_selects_stderr_level_and_format(
    verbosity: int, shown: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] log stderr: verifies -q/default/-v levels and the one stderr format.

    Scenario:
        Given verbosity -1 (quiet), 0, 1 and 3
        When a DEBUG, an INFO and a WARNING record are logged
        Then stderr shows only the records at or above WARNING/INFO/DEBUG, each as
            ``[YYYY-mm-dd HH:MM:SS][LEVEL]: msg``.

    Boundaries:
        - Focus: ``_stderr_level`` and ``_StderrFormatter``
        - Fixtures/params: four verbosities
        - Scope: one configure call each

    On failure, first check:
        - ``_stderr_level`` and ``_StderrFormatter.format`` in ``docsentinel.log``
    """
    configure_cli_logging(verbosity=verbosity, env=_env(tmp_path))
    capsys.readouterr()
    unit = logging.getLogger("docsentinel.unit")
    unit.debug("a debug record")
    unit.info("an info record")
    unit.warning("a warning record")

    expected = {
        "DEBUG": "[DEBUG]: a debug record",
        "INFO": "[INFO]: an info record",
        "WARNING": "[WARNING]: a warning record",
    }
    err = capsys.readouterr().err
    assert all(re.match(TIMESTAMP_PATTERN + r"\[", line) for line in err.splitlines())
    assert without_timestamps(err).splitlines() == [expected[level] for level in shown]


@pytest.mark.parametrize(("value", "verbosity"), [("debug", -1), ("ERROR", 1), (" warning ", 0)])
def test_log_level_env_overrides_verbosity(
    value: str, verbosity: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] log stderr: verifies DOCSENTINEL_LOG_LEVEL wins over -q/-v, case- and whitespace-insensitively.

    Scenario:
        Given ``DOCSENTINEL_LOG_LEVEL`` of ``debug`` with -q, ``ERROR`` with -v, `` warning `` by default
        When CLI logging is configured
        Then the stderr handler level is that named level.

    Boundaries:
        - Focus: the override in ``_stderr_level``
        - Fixtures/params: three combinations
        - Scope: one configure call each

    On failure, first check:
        - ``_stderr_level`` in ``docsentinel.log``
    """
    configure_cli_logging(verbosity=verbosity, env=_env(tmp_path, DOCSENTINEL_LOG_LEVEL=value))

    stderr_handlers = [handler for handler in _cli_handlers() if not isinstance(handler, log._OwnedStreamHandler)]
    assert [handler.level for handler in stderr_handlers] == [logging.getLevelName(value.strip().upper())]
    assert "WARNING" not in capsys.readouterr().err


def test_invalid_log_level_env_is_ignored_with_a_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] log stderr: verifies an unknown DOCSENTINEL_LOG_LEVEL is ignored with one WARNING.

    Scenario:
        Given ``DOCSENTINEL_LOG_LEVEL=LOUD\\x1b`` (with an ESC)
        When CLI logging is configured and an INFO record is logged
        Then one WARNING names the neutralised value and the default INFO level still applies.

    Boundaries:
        - Focus: invalid input to the override
        - Fixtures/params: tmp_path
        - Scope: one configure call

    On failure, first check:
        - ``_stderr_level`` in ``docsentinel.log``
    """
    configure_cli_logging(env=_env(tmp_path, DOCSENTINEL_LOG_LEVEL=f"LOUD{ESC}"))
    logging.getLogger("docsentinel.unit").info("still info")

    lines = without_timestamps(capsys.readouterr().err).splitlines()
    assert lines[0].startswith("[WARNING]: ignoring invalid DOCSENTINEL_LOG_LEVEL=LOUD\\x1b;")
    assert lines[1:] == ["[INFO]: still info"]


def test_configure_twice_does_not_stack_handlers(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] log configure: verifies a second configure replaces, not duplicates, the handlers.

    Scenario:
        Given CLI logging configured twice in one process (as repeated ``cli.main`` calls do)
        When one INFO record is logged
        Then stderr holds it once, exactly two CLI handlers are attached, and the first file handler is closed.

    Boundaries:
        - Focus: idempotency
        - Fixtures/params: tmp_path
        - Scope: two configure calls

    On failure, first check:
        - ``shutdown_cli_logging`` being called first in ``configure_cli_logging``
    """
    configure_cli_logging(env=_env(tmp_path))
    first_file = next(handler for handler in _cli_handlers() if isinstance(handler, log._OwnedStreamHandler))
    configure_cli_logging(env=_env(tmp_path))
    logging.getLogger("docsentinel.unit").info("once")

    assert without_timestamps(capsys.readouterr().err) == "[INFO]: once\n"
    assert len(_cli_handlers()) == 2
    assert first_file.stream.closed


def test_shutdown_closes_file_and_restores_the_logger(tmp_path: Path):
    """
    [Unit] log shutdown: verifies shutdown removes the CLI handlers, closes the file and restores the level.

    Scenario:
        Given the package logger at its import-time level and CLI logging configured
        When ``shutdown_cli_logging`` runs (twice)
        Then no CLI handler remains, the NullHandler is still attached, the file stream is closed and
            the logger level is back to what it was.

    Boundaries:
        - Focus: no leaked file descriptors across repeated CLI runs
        - Fixtures/params: tmp_path
        - Scope: one configure, two shutdowns

    On failure, first check:
        - ``shutdown_cli_logging`` and ``_OwnedStreamHandler.close``
    """
    level = _PACKAGE.level
    configure_cli_logging(env=_env(tmp_path))
    file_handler = next(handler for handler in _cli_handlers() if isinstance(handler, log._OwnedStreamHandler))

    shutdown_cli_logging()
    shutdown_cli_logging()

    assert _cli_handlers() == []
    assert any(isinstance(handler, logging.NullHandler) for handler in _PACKAGE.handlers)
    assert file_handler.stream.closed
    assert _PACKAGE.level == level


def test_unwritable_log_directory_falls_back_to_stderr_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] log configure: verifies a log directory that cannot be created disables the file, not the run.

    Scenario:
        Given ``DOCSENTINEL_LOG_DIR`` naming a regular file
        When CLI logging is configured and an INFO record is logged
        Then it returns ``None`` without raising, one WARNING says the log file is disabled, and stderr
            logging still works.

    Boundaries:
        - Focus: spec §2 failure behaviour
        - Fixtures/params: tmp_path
        - Scope: one configure call

    On failure, first check:
        - The ``except (OSError, RuntimeError)`` around the file creation in ``configure_cli_logging``
    """
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")

    path = configure_cli_logging(env={"DOCSENTINEL_LOG_DIR": str(blocker)})
    logging.getLogger("docsentinel.unit").info("still running")

    assert path is None
    lines = without_timestamps(capsys.readouterr().err).splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("[WARNING]: log file disabled, logging to stderr only: ")
    assert lines[1] == "[INFO]: still running"


def test_file_only_record_skips_stderr(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] log stderr: verifies a record logged with ``FILE_ONLY`` reaches the file but not stderr.

    Scenario:
        Given CLI logging configured
        When a WARNING is logged with ``extra=FILE_ONLY``
        Then stderr is empty and the log file holds the WARNING.

    Boundaries:
        - Focus: the CLI's "already printed in its own words" records
        - Fixtures/params: tmp_path
        - Scope: one record

    On failure, first check:
        - ``_not_file_only`` on the stderr handler
    """
    path = configure_cli_logging(env=_env(tmp_path))
    logging.getLogger("docsentinel.unit").warning("scan failed: %s", "bad config", extra=FILE_ONLY)
    shutdown_cli_logging()

    assert capsys.readouterr().err == ""
    assert path is not None
    assert "[WARNING]: scan failed: bad config\n" in without_timestamps(path.read_text(encoding="utf-8"))


def test_default_log_directory_is_local_logs_under_home():
    """
    [Unit] log directory: verifies the default is ``~/.local/logs/docsentinel`` and the override wins.

    Scenario:
        Given an environment without and with ``DOCSENTINEL_LOG_DIR``
        When the log directory is resolved
        Then it is ``<home>/.local/logs/docsentinel`` (plural ``logs``), or the override.

    Boundaries:
        - Focus: spec §2 log directory
        - Fixtures/params: none (nothing is created)
        - Scope: two calls

    On failure, first check:
        - ``_log_directory`` in ``docsentinel.log``
    """
    assert log._log_directory({}) == Path.home() / ".local" / "logs" / "docsentinel"
    assert log._log_directory({"DOCSENTINEL_LOG_DIR": "/x/y"}) == Path("/x/y")


def test_safe_rewrites_the_github_legacy_command_marker():
    """
    [Unit] log safe: verifies ``##[`` never survives ``safe`` (security review M2).

    Scenario:
        Given values holding ``##[``, ``###[`` and a marker split by a zero-width space
        When each passes through ``safe``
        Then every ``##[`` becomes ``##\\[`` and no output contains ``##[``.

    Boundaries:
        - Focus: the shared ``neutralize`` table that feeds ``safe``
        - Fixtures/params: none
        - Scope: pure function

    On failure, first check:
        - ``_neutralize_controls`` in ``docsentinel.telemetry.filters``
    """
    assert safe("##[error]x") == "##\\[error]x"
    assert safe("###[[##[") == "###\\[[##\\["
    assert safe("#​#[") == "#\\u200b#["
    assert all("##[" not in safe(value) for value in ("##[", "a##[b##[c", "##[" * 80))


def _fixed_stem(monkeypatch: pytest.MonkeyPatch) -> str:
    """Pin the log file time stamp and return the stem ``_open_log_file`` will use."""
    monkeypatch.setattr(log.time, "strftime", lambda _format, _moment=None: "20260101-000000")
    return f"docsentinel-20260101-000000-{os.getpid()}"


@pytest.mark.skipif(not hasattr(os, "link"), reason="hard links are not available")
def test_pre_planted_hard_link_is_never_opened(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] log file: verifies a hard link planted under the next log name is left alone (security review M1).

    Scenario:
        Given a private log directory holding a hard link, named like the next log file, to a victim file
        When CLI logging is configured and a record is logged
        Then the run writes to ``<stem>-1.log`` instead, and the victim keeps its content and mode.

    Boundaries:
        - Focus: ``O_EXCL`` creation and the collision suffix
        - Fixtures/params: tmp_path, monkeypatch (fixed time stamp)
        - Scope: one configure call

    On failure, first check:
        - ``_CREATE_FLAGS`` and ``_create_exclusive`` in ``docsentinel.log``
    """
    stem = _fixed_stem(monkeypatch)
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)
    victim = tmp_path / "victim.txt"
    victim.write_text("precious\n", encoding="utf-8")
    victim.chmod(0o644)
    os.link(victim, logs / f"{stem}.log")

    path = configure_cli_logging(env=_env(tmp_path))
    logging.getLogger("docsentinel.unit").warning("hello")
    shutdown_cli_logging()

    assert path == logs / f"{stem}-1.log"
    assert victim.read_text(encoding="utf-8") == "precious\n"
    assert stat.S_IMODE(victim.stat().st_mode) == 0o644
    assert "hello" in path.read_text(encoding="utf-8")


def test_second_configure_in_the_same_second_gets_a_suffix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] log file: verifies two runs in one process and second create two files, never appending (edge).

    Scenario:
        Given a fixed time stamp
        When CLI logging is configured three times
        Then the files are ``<stem>.log``, ``<stem>-1.log`` and ``<stem>-2.log``, all matching the rotation pattern.

    Boundaries:
        - Focus: the collision suffix replacing the old same-file append
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: three configure calls

    On failure, first check:
        - ``_create_exclusive`` and ``LOG_FILE_PATTERN``
    """
    stem = _fixed_stem(monkeypatch)

    names = [configure_cli_logging(env=_env(tmp_path)).name for _ in range(3)]

    assert names == [f"{stem}.log", f"{stem}-1.log", f"{stem}-2.log"]
    assert all(log.LOG_FILE_PATTERN.match(name) for name in names)


def test_log_file_with_more_than_one_link_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] log file: verifies a created file reporting ``st_nlink != 1`` disables the file, not the run.

    Scenario:
        Given ``os.fstat`` reporting two links for the new log file
        When CLI logging is configured
        Then it returns ``None`` and one WARNING names the link count.

    Boundaries:
        - Focus: the ``st_nlink`` check before any write or ``fchmod``
        - Fixtures/params: tmp_path, monkeypatch (fstat), capsys
        - Scope: one configure call

    On failure, first check:
        - the ``st_nlink`` check in ``_open_log_file``
    """
    real_fstat = os.fstat

    def linked(descriptor: int) -> os.stat_result:
        """Return the real stat result with ``st_nlink`` forced to 2."""
        values = list(real_fstat(descriptor))
        values[stat.ST_NLINK] = 2
        return os.stat_result(values)

    monkeypatch.setattr(log.os, "fstat", linked)

    path = configure_cli_logging(env=_env(tmp_path))

    assert path is None
    err = without_timestamps(capsys.readouterr().err)
    assert "[WARNING]: log file disabled, logging to stderr only: " in err
    assert "has 2 hard links; expected 1" in err


@pytest.mark.skipif(not hasattr(os, "geteuid"), reason="POSIX ownership and mode bits")
@pytest.mark.parametrize("kind", ["symlink", "group_writable", "other_writable", "foreign_owner"])
def test_unsafe_existing_log_directory_disables_the_file(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Unit] log directory: verifies an existing directory that is not private disables the file (invalid input).

    Scenario:
        Given ``DOCSENTINEL_LOG_DIR`` naming a symlink to a directory, a group- or other-writable directory,
            or a directory owned by another user (simulated through ``geteuid``)
        When CLI logging is configured
        Then it returns ``None`` without raising, writes nothing there, and one WARNING says why.

    Boundaries:
        - Focus: ``_check_private_directory`` (lstat, owner, no group/other write bit)
        - Fixtures/params: tmp_path, monkeypatch, capsys; parametrized over four unsafe directories
        - Scope: one configure call

    On failure, first check:
        - ``_check_private_directory`` in ``docsentinel.log``
    """
    real = tmp_path / "real"
    real.mkdir(mode=0o700)
    target = real
    if kind == "symlink":
        target = tmp_path / "logs"
        target.symlink_to(real, target_is_directory=True)
        reason = "is not a directory (symlinks are refused)"
    elif kind == "group_writable":
        real.chmod(0o770)
        reason = "is writable by group or others"
    elif kind == "other_writable":
        real.chmod(0o703)
        reason = "is writable by group or others"
    else:
        monkeypatch.setattr(log.os, "geteuid", lambda: os.getuid() + 1)
        reason = "is not owned by the current user"

    path = configure_cli_logging(env={"DOCSENTINEL_LOG_DIR": str(target)})

    assert path is None
    assert list(real.iterdir()) == []
    lines = without_timestamps(capsys.readouterr().err).splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("[WARNING]: log file disabled, logging to stderr only: ")
    assert lines[0].endswith(reason)


def test_existing_private_log_directory_is_accepted_unchanged(tmp_path: Path):
    """
    [Unit] log directory: verifies an existing 0o700 directory of ours is used as is (normal case).

    Scenario:
        Given an existing private log directory
        When CLI logging is configured
        Then the log file is created inside it and its mode stays 0o700.

    Boundaries:
        - Focus: the accepting branch of ``_check_private_directory``
        - Fixtures/params: tmp_path
        - Scope: one configure call

    On failure, first check:
        - ``_ensure_directory`` and ``_check_private_directory``
    """
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)

    path = configure_cli_logging(env=_env(tmp_path))

    assert path is not None and path.parent == logs
    assert stat.S_IMODE(logs.stat().st_mode) == 0o700


def test_rotation_skips_loose_names_future_and_recent_files(tmp_path: Path):
    """
    [Unit] log rotation: verifies the exact pattern, the future-mtime skip and the 60 s grace (security review L1).

    Scenario:
        Given ``docsentinel-important.log``, a matching file with a future mtime, a matching file modified
            just now, and three old matching files, with ``DOCSENTINEL_LOG_KEEP=2``
        When CLI logging is configured
        Then all three old files are deleted (the recent file takes the one free keep slot, the future
            file takes none), while the loose name, the future file and the recent file survive.

    Boundaries:
        - Focus: ``LOG_FILE_PATTERN`` and ``_rotation_candidates``/``_rotate`` timing rules
        - Fixtures/params: tmp_path
        - Scope: one configure call

    On failure, first check:
        - ``_rotation_candidates`` and ``ROTATION_GRACE_SECONDS`` in ``docsentinel.log``
    """
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)
    loose = _old_log(logs, "docsentinel-important.log", age=100)
    future = _old_log(logs, "docsentinel-20990101-000000-1.log", age=-1000)
    recent = logs / "docsentinel-20260101-000000-2.log"
    recent.write_text("live\n", encoding="utf-8")
    old = [_old_log(logs, f"docsentinel-2020010{index}-000000-1.log", age=10 - index) for index in range(3)]

    current = configure_cli_logging(env=_env(tmp_path, DOCSENTINEL_LOG_KEEP="2"))

    assert current is not None and current.exists()
    assert loose.exists() and future.exists() and recent.exists()
    assert [path.exists() for path in old] == [False, False, False]


@pytest.mark.skipif(not hasattr(os, "geteuid"), reason="POSIX ownership")
def test_rotation_never_deletes_files_of_another_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] log rotation: verifies files not owned by the effective user are neither counted nor deleted.

    Scenario:
        Given three old matching log files and ``geteuid`` reporting another user during rotation
        When rotation runs with ``keep=1``
        Then every file survives.

    Boundaries:
        - Focus: the ``st_uid`` filter in ``_rotation_candidates``
        - Fixtures/params: tmp_path, monkeypatch
        - Scope: one direct ``_rotate`` call

    On failure, first check:
        - the owner check in ``_rotation_candidates``
    """
    logs = tmp_path / "logs"
    logs.mkdir(mode=0o700)
    old = [_old_log(logs, f"docsentinel-2020010{index}-000000-1.log", age=10 - index) for index in range(3)]
    current = logs / "docsentinel-20260101-000000-9.log"
    current.write_text("", encoding="utf-8")
    monkeypatch.setattr(log.os, "geteuid", lambda: os.getuid() + 1)

    log._rotate(logs, current, 1)

    assert all(path.exists() for path in old)


def test_file_traceback_cannot_forge_a_record(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] log file: verifies a multi-line exception message stays on one neutralised line (security review L2).

    Scenario:
        Given CLI logging configured
        When ``logger.exception`` records a chained exception whose message holds a newline, a fake record,
            an ESC sequence and ``##[``
        Then the file holds the message on one line with ``\\x0a``, no ESC and no ``##[``, the frame lines
            keep their breaks, and stderr shows no traceback.

    Boundaries:
        - Focus: ``_FileFormatter.formatException``
        - Fixtures/params: tmp_path, capsys
        - Scope: one record

    On failure, first check:
        - ``_FileFormatter`` and ``_exception_only_chunks`` in ``docsentinel.log``
    """
    path = configure_cli_logging(env=_env(tmp_path))
    hostile = "bad\n[2026-01-01 00:00:00][ERROR]: owned " + ESC + "[31m ##[x]"
    try:
        try:
            raise KeyError("inner\nline")
        except KeyError as inner:
            raise ValueError(hostile) from inner
    except ValueError:
        logging.getLogger("docsentinel.unit").exception("analyzer failed")
    shutdown_cli_logging()

    text = path.read_text(encoding="utf-8")
    assert "ValueError: bad\\x0a[2026-01-01 00:00:00][ERROR]: owned \\x1b[31m ##\\[x]" in text
    assert "KeyError: 'inner\\nline'" in text
    assert not any(line.startswith("[2026-01-01 00:00:00]") for line in text.splitlines())
    assert ESC not in text and "##[" not in text
    assert "Traceback (most recent call last):" in text and '  File "' in text
    assert "Traceback" not in capsys.readouterr().err
