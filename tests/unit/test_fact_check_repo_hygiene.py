"""Repository hygiene for the DS302 consent surface (Milestone 0010 threat model M4, M12).

Consent to send document text to a third-party service is an invoker decision. A repository
must never grant it ambiently: the published pre-commit hooks never pass ``--use-external-api``,
and no GitHub workflow passes the flag, sets ``DOCSENTINEL_USE_EXTERNAL_API`` or names a
``DOCSENTINEL_FACTCHECK_*`` variable (which would carry an API key into CI). Only repository
configuration files are read; no asset is loaded.
"""

from pathlib import Path

import pytest

#: The repository root (``tests/unit/`` is two levels below it).
_REPO = Path(__file__).resolve().parents[2]

#: The published pre-commit hook definitions.
_HOOKS = _REPO / ".pre-commit-hooks.yaml"

#: The GitHub Actions workflow directory.
_WORKFLOWS = _REPO / ".github" / "workflows"

#: Text no workflow may contain.
_WORKFLOW_FORBIDDEN = ("--use-external-api", "DOCSENTINEL_USE_EXTERNAL_API", "DOCSENTINEL_FACTCHECK_")


def _workflow_files() -> list[Path]:
    """Return every workflow file, sorted."""
    return sorted(path for path in _WORKFLOWS.iterdir() if path.suffix in {".yml", ".yaml"})


def test_pre_commit_hooks_never_pass_the_consent_flag():
    """
    [Unit] fact-check hygiene: verifies .pre-commit-hooks.yaml never passes --use-external-api.

    Scenario:
        Given the published pre-commit hook definitions
        When their text is searched
        Then --use-external-api does not occur, while the docsentinel-fast hook still exists.

    Boundaries:
        - Focus: threat model M4 (FC-4, ambient consent through a repository)
        - Fixtures/params: none
        - Scope: one repository file

    On failure, first check:
        - The entry/args of the hook that gained the flag
    """
    text = _HOOKS.read_text(encoding="utf-8")

    assert "id: docsentinel-fast" in text
    assert "--use-external-api" not in text


def test_workflow_directory_is_not_empty():
    """
    [Unit] fact-check hygiene: verifies the workflow scan has files to check.

    Scenario:
        Given .github/workflows/
        When the workflow files are listed
        Then ci.yml is among them.

    Boundaries:
        - Focus: guard against the hygiene check scanning nothing
        - Fixtures/params: none
        - Scope: directory listing

    On failure, first check:
        - Whether the workflows were moved or renamed
    """
    assert "ci.yml" in {path.name for path in _workflow_files()}


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda path: path.name)
def test_workflows_never_grant_consent_or_carry_a_key(path: Path):
    """
    [Unit] fact-check hygiene: verifies no workflow passes the flag, sets the env consent or names a key variable.

    Scenario:
        Given one GitHub workflow file
        When its text is searched
        Then none of --use-external-api, DOCSENTINEL_USE_EXTERNAL_API or DOCSENTINEL_FACTCHECK_ occurs.

    Boundaries:
        - Focus: threat model M4 and M12
        - Fixtures/params: every workflow file
        - Scope: one repository file

    On failure, first check:
        - The step that gained the flag or variable; DS302 is never a CI gate
    """
    text = path.read_text(encoding="utf-8")

    assert [token for token in _WORKFLOW_FORBIDDEN if token in text] == []
