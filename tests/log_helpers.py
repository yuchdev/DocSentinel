"""Helpers for tests that assert on CLI stderr now that the CLI logs progress there.

``cli.main`` writes INFO lines such as ``docsentinel: scan started: ...`` to stderr
(``docs/specs/logging.md`` §2). Tests that used to assert ``stderr == ""`` meant
"nothing went wrong"; :func:`problem_output` keeps that meaning by dropping only the
INFO/DEBUG progress lines, so a user message (``Scan failed: ...``) or a logged
``WARNING``/``ERROR``/``CRITICAL`` still fails the assertion.
"""

import re

#: A CLI progress line: the ``docsentinel: `` prefix without a problem level after it.
_PROGRESS_LINE = re.compile(r"^docsentinel: (?!(?:WARNING|ERROR|CRITICAL): )")


def problem_output(stderr: str) -> str:
    """Return ``stderr`` without the CLI's INFO/DEBUG progress lines.

    :param stderr: Captured standard error of one or more CLI runs.
    :returns: The remaining lines, each with its newline, in their original order.
    """
    return "".join(line for line in stderr.splitlines(keepends=True) if not _PROGRESS_LINE.match(line))
