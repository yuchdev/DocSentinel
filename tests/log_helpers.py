"""Helpers for tests that assert on CLI stderr now that the CLI logs progress there.

``cli.main`` writes INFO lines such as ``[<timestamp>][INFO]: scan started: ...`` to stderr
(``docs/specs/logging.md`` §2). Tests that used to assert ``stderr == ""`` meant
"nothing went wrong"; :func:`problem_output` keeps that meaning by dropping only the
INFO/DEBUG progress lines, so a user message (``Scan failed: ...``) or a logged
``WARNING``/``ERROR``/``CRITICAL`` still fails the assertion.
"""

import re

#: The ``[YYYY-mm-dd HH:MM:SS]`` timestamp that opens every log line (``log.LOG_DATE_FORMAT``).
TIMESTAMP_PATTERN = r"\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\]"
#: A CLI progress line: ``[timestamp][INFO]: `` or ``[timestamp][DEBUG]: ``.
_PROGRESS_LINE = re.compile(r"^" + TIMESTAMP_PATTERN + r"\[(?:INFO|DEBUG)\]: ")
#: The timestamp at the start of a line, removed by :func:`without_timestamps`.
_LINE_TIMESTAMP = re.compile(r"^" + TIMESTAMP_PATTERN, re.MULTILINE)


def problem_output(stderr: str) -> str:
    """Return ``stderr`` without the CLI's INFO/DEBUG progress lines.

    :param stderr: Captured standard error of one or more CLI runs.
    :returns: The remaining lines, each with its newline, in their original order.
    """
    return "".join(line for line in stderr.splitlines(keepends=True) if not _PROGRESS_LINE.match(line))


def without_timestamps(text: str) -> str:
    """Return ``text`` with the leading ``[YYYY-mm-dd HH:MM:SS]`` of every line removed.

    A record ``[2026-11-27 14:51:50][WARNING]: msg`` becomes ``[WARNING]: msg``, so a test can
    compare log lines exactly without depending on the clock. Only a timestamp at the very start
    of a line is removed; anything else is kept as is.

    :param text: Captured stderr or log-file text.
    :returns: The text without line-leading timestamps, line breaks unchanged.
    """
    return _LINE_TIMESTAMP.sub("", text)
