"""Milestone-wide regression check: the Lenz example key never leaves its file (Story 04.0 Task 02 steps 7 and 8).

``examples/docs/lenz_fact-checking.md`` embeds an API key under its ``## API key`` heading. This
module reads that key at test time, keeps it only in memory and fails when the key or a 12-character
prefix of it occurs in any other repository file (plan exit gate 8, threat model 0010 M12). It also
pins where the backend host name may appear under ``src/`` and ``tests/``, proves the session-wide
network guard of ``tests/conftest.py`` is installed, and checks that a fresh interpreter's backend
registry never holds a test fake.

This file never contains the key, a prefix of it or the host string as one literal. It loads no
asset. Failure messages name only paths and line numbers, never the token.
"""

import os
import re
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS
from tests.conftest import NETWORK_GUARD_MESSAGE

#: The repository root.
REPO = Path(__file__).resolve().parents[2]

#: The one file allowed to hold the example key.
EXAMPLE = REPO / "examples" / "docs" / "lenz_fact-checking.md"

#: Top-level directories that are not repository content.
SKIPPED_TOP_LEVEL = frozenset({".git", ".venv", "dist", "build", "reports", ".idea"})

#: Prefix length searched for: long enough to be specific, short enough to catch a truncated copy.
PREFIX_CHARS = 12

#: The backend host, assembled so this file never holds it as one literal.
HOST = "lenz" + "." + "io"

#: Files allowed to name the host: the client and the Story 03.0 tests that pin its URL.
HOST_ALLOWED = frozenset(
    {
        "src/docsentinel/fact_check/lenz.py",
        "tests/mock/test_lenz_client_transport.py",
        "tests/unit/test_lenz_client_static.py",
    }
)

#: A key-shaped token: printable, no whitespace, at least 16 characters.
KEY_SHAPE = re.compile(r"^[!-~]{16,}$")


def _example_key() -> str:
    """Return the key from the example document's ``## API key`` fenced block.

    :returns: The key.
    """
    if not EXAMPLE.is_file():
        pytest.skip("examples/docs/lenz_fact-checking.md is absent; there is no key to guard")
    text = EXAMPLE.read_text(encoding="utf-8")
    match = re.search(r"^## API key\s*\n+```[^\n]*\n([^\n`]+)\n```", text, re.MULTILINE)
    if match is None or not KEY_SHAPE.match(match.group(1).strip()):
        pytest.fail("the example document exists but no key-shaped token was found under '## API key'")
    return match.group(1).strip()


def _is_nested_checkout(directory: Path) -> bool:
    """Return whether ``directory`` is another checkout (a git worktree or submodule) below the root.

    :param directory: A directory under the repository root.
    :returns: ``True`` when it holds its own ``.git`` entry.
    """
    return directory != REPO and os.path.lexists(directory / ".git")


def _repository_files() -> Iterator[Path]:
    """Yield every regular repository file except the skipped directories and the example itself.

    Nested checkouts (for example ``.claude/worktrees/<name>``) are separate working trees with their
    own copy of the example, not files of this tree, and are not descended into. Symlinks are not
    followed.

    :returns: An iterator over the files, in sorted walk order.
    """
    for current, dirs, files in os.walk(REPO):
        here = Path(current)
        dirs[:] = sorted(
            name
            for name in dirs
            if not (here == REPO and name in SKIPPED_TOP_LEVEL)
            and name != "__pycache__"
            and not (here / name).is_symlink()
            and not _is_nested_checkout(here / name)
        )
        for name in sorted(files):
            path = here / name
            if path != EXAMPLE and path.is_file() and not path.is_symlink():
                yield path


def _matching_lines(path: Path, needle: bytes) -> list[int]:
    """Return the 1-based line numbers of ``path`` that contain ``needle``.

    :param path: The file.
    :param needle: The bytes searched for.
    :returns: The line numbers; empty when absent. An unreadable file raises ``OSError``, so the
        search fails closed instead of skipping a file it could not check.
    """
    data = path.read_bytes()
    if needle not in data:
        return []
    return [number for number, line in enumerate(data.split(b"\n"), start=1) if needle in line]


def test_example_key_appears_in_no_other_repository_file():
    """
    [Integration] key hygiene: verifies no repository file but the example holds the key or its 12-character prefix.

    Scenario:
        Given the key read at test time from the example document's API key block
        When every repository file outside .git, .venv, dist, build, reports, .idea, nested checkouts and
            the example itself is searched as bytes
        Then no file contains the first 12 characters of the key, and a failure names path:line only

    Boundaries:
        - Focus: plan exit gate 8; Task 02 step 7; threat model 0010 M12
        - Fixtures/params: none; skips only when the example file is absent, fails when it has no key
        - Scope: the working tree

    On failure, first check:
        - The named file; replace the value with tests.fact_check_fakes.SENTINEL or a placeholder
    """
    needle = _example_key()[:PREFIX_CHARS].encode("utf-8")
    assert needle in EXAMPLE.read_bytes()

    offenders = [
        f"{path.relative_to(REPO).as_posix()}:{line}"
        for path in _repository_files()
        for line in _matching_lines(path, needle)
    ]

    assert offenders == [], "the example API key (or its prefix) appears in: " + ", ".join(offenders)


def test_walk_reaches_src_tests_docs_and_this_file():
    """
    [Integration] key hygiene: verifies the repository walk is not vacuous.

    Scenario:
        Given the repository walk used by the key check
        When its files are collected
        Then it includes this file, the DS302 detector, a documentation file and the shared fakes, and
            excludes the example and anything under .git

    Boundaries:
        - Focus: Task 02 step 7 (a missing walk must not pass vacuously)
        - Fixtures/params: none
        - Scope: _repository_files

    On failure, first check:
        - The pruning in _repository_files
    """
    files = {path.relative_to(REPO).as_posix() for path in _repository_files()}

    assert {
        "tests/integration/test_no_lenz_example_key_leaked.py",
        "src/docsentinel/detectors/fact_check.py",
        "tests/fact_check_fakes.py",
        "CLAUDE.md",
    } <= files
    assert "examples/docs/lenz_fact-checking.md" not in files
    assert not any(name.startswith(".git/") for name in files)


def test_host_name_appears_only_in_the_client_and_its_transport_tests():
    """
    [Integration] endpoint hygiene: verifies no src/ or tests/ file names the backend host outside the allow list.

    Scenario:
        Given every file under src/ and tests/
        When each is searched for the backend host string
        Then only fact_check/lenz.py and the Story 03.0 transport and static tests contain it

    Boundaries:
        - Focus: Task 02 step 7 last bullet; no test reaches the real endpoint
        - Fixtures/params: none
        - Scope: src/ and tests/

    On failure, first check:
        - Whether a new test builds a request to the real host
    """
    needle = HOST.encode("ascii")
    holders = {
        path.relative_to(REPO).as_posix()
        for path in _repository_files()
        if path.relative_to(REPO).parts[0] in {"src", "tests"} and _matching_lines(path, needle)
    }

    assert holders <= HOST_ALLOWED
    assert "src/docsentinel/fact_check/lenz.py" in holders


def test_session_network_guard_is_installed():
    """
    [Integration] network guard: verifies the session fixture replaced both real httpx transports.

    Scenario:
        Given the test session
        When httpx's real sync and async transport entry points are inspected and the sync one is called
        Then both come from tests/conftest.py and a real request fails with the guard message

    Boundaries:
        - Focus: Task 02 step 8 (removing the guard fails this test)
        - Fixtures/params: the session-scoped _no_real_network_transport fixture
        - Scope: httpx.HTTPTransport and httpx.AsyncHTTPTransport

    On failure, first check:
        - _no_real_network_transport in tests/conftest.py
    """
    assert httpx.HTTPTransport.handle_request.__module__ == "tests.conftest"
    assert httpx.AsyncHTTPTransport.handle_async_request.__module__ == "tests.conftest"
    request = httpx.Request("GET", "http://192.0.2.1:9/")
    with pytest.raises(AssertionError, match=f"^{NETWORK_GUARD_MESSAGE}$"):
        httpx.HTTPTransport().handle_request(request)


def test_backend_registry_never_holds_a_fake():
    """
    [Integration] registry hygiene: verifies a fresh interpreter's registry is empty, then lenz only.

    Scenario:
        Given a fresh "python -I" interpreter with this repository's src on sys.path
        When it imports docsentinel and the fact_check protocol, then calls load_backend("lenz")
        Then the registry is {} after import and {"lenz"} after loading; in this process no "fake" entry
            exists outside a test's monkeypatch scope

    Boundaries:
        - Focus: Story 04.0 Task 01 acceptance criterion 2
        - Fixtures/params: subprocess; no socket is opened (load_backend only imports)
        - Scope: import docsentinel and protocol.load_backend

    On failure, first check:
        - An import-time registration in src/ or a leaked monkeypatch
    """
    probe = textwrap.dedent(
        """
        import json
        import docsentinel
        from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS, load_backend
        before = sorted(FACT_CHECK_BACKENDS)
        load_backend("lenz")
        print(json.dumps([before, sorted(FACT_CHECK_BACKENDS)]))
        """
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DOCSENTINEL_", "PYTHON"))}
    completed = subprocess.run(
        [sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(REPO / 'src')!r})\n{probe}"],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr[-2000:]
    assert completed.stdout.strip() == '[[], ["lenz"]]'
    assert "fake" not in FACT_CHECK_BACKENDS
