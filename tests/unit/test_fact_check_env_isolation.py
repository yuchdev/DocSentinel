"""Proof that the autouse fixture hides fact-check variables from every test (threat model 0010 M12).

A child ``pytest -p docsentinel.pytest_plugin`` run is started on one inline test with
``DOCSENTINEL_USE_EXTERNAL_API``, ``DOCSENTINEL_FACTCHECK_FAKE_API_KEY`` and the other tool's key
variable set in the parent environment. The child test asserts it sees none of them, which can
only hold when ``tests/conftest.py``'s ``_isolated_fact_check_env`` fixture runs. Only the sentinel
value is ever used; no network is touched.
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

#: The repository root, where the child run picks up ``tests/conftest.py``.
_REPO = Path(__file__).resolve().parents[2]

#: The fake key value (threat model 0010 M12).
_SENTINEL = "sentinel-not-a-real-key-0010"

#: The other tool's key variable, assembled so this file has no standalone literal of it (M8).
_OTHER_TOOL_KEY = "LENZ" + "_API_KEY"

#: The variables the parent sets and the child must not see.
_PARENT_VARIABLES = {
    "DOCSENTINEL_USE_EXTERNAL_API": "1",
    "DOCSENTINEL_FACTCHECK_FAKE_API_KEY": _SENTINEL,
    _OTHER_TOOL_KEY: _SENTINEL,
}

#: The inline child test. It also records that it ran, so a collection failure cannot pass.
_CHILD_TEST = textwrap.dedent(
    '''
    """Child test run by test_fact_check_env_isolation."""

    import os


    def test_child_sees_no_fact_check_variable():
        """
        [Unit] fact-check env isolation child: verifies the fixture removed every variable.

        Scenario:
            Given the parent set the consent flag and two sentinel keys
            When this test reads the environment
            Then none of them is visible.

        Boundaries:
            - Focus: threat model M12
            - Fixtures/params: autouse conftest fixtures only
            - Scope: os.environ

        On failure, first check:
            - _isolated_fact_check_env in tests/conftest.py
        """
        leaked = sorted(
            name
            for name in os.environ
            if name in {"DOCSENTINEL_USE_EXTERNAL_API", "LENZ" + "_API_KEY"} or name.startswith("DOCSENTINEL_FACTCHECK_")
        )
        assert leaked == []
        assert "sentinel-not-a-real-key-0010" not in os.environ.values()
    '''
)


def test_autouse_fixture_hides_fact_check_variables(tmp_path: Path):
    """
    [Unit] fact-check env isolation: verifies a child pytest test sees no consent or key variable.

    Scenario:
        Given DOCSENTINEL_USE_EXTERNAL_API=1 and two sentinel key variables in the parent environment
        When a child pytest run, loading the repository's tests/conftest.py and the plugin, executes one inline test
        Then that test passes, proving the autouse fixture removed all three, and the parent never had them.

    Boundaries:
        - Focus: threat model M12 (the developer's real key never reaches a test)
        - Fixtures/params: tmp_path holds the child test; the repository tree is never written
        - Scope: one subprocess, no network

    On failure, first check:
        - _isolated_fact_check_env in tests/conftest.py and the child output in the assertion message
    """
    child_file = tmp_path / "test_child_env_isolation.py"
    child_file.write_text(_CHILD_TEST, encoding="utf-8")
    env = {**os.environ, **_PARENT_VARIABLES}

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(_REPO / "pyproject.toml"),
            "--rootdir",
            str(_REPO),
            "-p",
            "tests.conftest",
            "-p",
            "docsentinel.pytest_plugin",
            "-p",
            "no:cacheprovider",
            "-q",
            str(child_file),
        ],
        cwd=_REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 0, output
    assert "1 passed" in completed.stdout, output
    assert all(name not in os.environ for name in _PARENT_VARIABLES)
