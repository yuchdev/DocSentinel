"""Unit tests for the secret scanner patterns and the Stop-time sweep hook.

The hook scripts are not a package, so they are loaded from ``.github/hooks/scripts``.
Token fixtures are assembled at run time so this file never contains a literal secret.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / ".github" / "hooks" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import secret_scan
import secret_sweep

LENZ = "lenz" + "_" + "a1B2c3D4" * 4  # 32 alphanumerics after the prefix


def test_bare_lenz_key_in_a_code_fence_is_detected():
    """
    [Unit] secret scanner: a bare Lenz key inside a code fence is found.

    Scenario:
        Given Markdown whose only secret is a bare lenz_ token on its own line
        When scan_text runs
        Then exactly one Lenz API key finding is reported on that line

    Boundaries:
        - Focus: the keyword-less shape the Lenz docs use
        - Fixtures/params: one inline document

    On failure, first check:
        - the Lenz API key pattern in secret_scan.PATTERNS
    """
    hits = secret_scan.scan_text(f"## API key\n\n```\n{LENZ}\n```\n")
    assert [(name, line) for name, line, _ in hits] == [("Lenz API key", 4)]


def test_unknown_vendor_prefixed_token_is_detected_by_the_fallback():
    """
    [Unit] secret scanner: an unlisted vendor token is caught by the fallback.

    Scenario:
        Given a lowercase-prefix token with 32 mixed alphanumerics
        When scan_text runs
        Then a Vendor-prefixed token finding is reported

    Boundaries:
        - Focus: the generic fallback pattern
        - Fixtures/params: one runtime-built token

    On failure, first check:
        - the Vendor-prefixed token pattern
    """
    token = "acme" + "_" + "Zx9Qw8Er" * 4
    assert any(name == "Vendor-prefixed token" for name, _, _ in secret_scan.scan_text(token))


@pytest.mark.parametrize(
    "text",
    [
        "lenz_REDACTED_ROTATE_THIS_KEY",
        "fact_check_max_claims_per_document",
        "a_" + "b" * 40,  # long but no digit: an identifier, not a credential
    ],
)
def test_placeholders_and_long_identifiers_are_not_flagged(text):
    """
    [Unit] secret scanner: placeholders and long identifiers stay quiet.

    Scenario:
        Given the masked key, a long snake_case name and a digit-free long identifier
        When scan_text runs
        Then no finding is reported

    Boundaries:
        - Focus: false-positive control for the new patterns
        - Fixtures/params: three parametrized strings

    On failure, first check:
        - the lookaheads requiring a letter and a digit
    """
    assert secret_scan.scan_text(text) == []


def test_banner_masks_the_value_and_is_clearly_delimited():
    """
    [Unit] sweep banner: it masks the value and is visibly boxed.

    Scenario:
        Given one hit for a Lenz key
        When banner renders
        Then the file and line appear, at most four characters of the key show, and the border repeats

    Boundaries:
        - Focus: no leak of the secret, strong visual delimiting
        - Fixtures/params: one runtime-built key

    On failure, first check:
        - _mask length and BAR usage in banner
    """
    text = f"{LENZ}\n"
    path = Path("x.md")
    masked = secret_sweep._mask(text, "Lenz API key", 1)
    out = secret_sweep.banner([(path.as_posix(), 1, "Lenz API key", masked)])
    assert LENZ not in out and LENZ[:8] not in out
    assert "x.md:1" in out and "lenz***" in out
    assert out.count(secret_sweep.BAR) >= 4 and "ROTATE IT NOW" in out


def _run_hook(tmp_repo: Path, event: dict[str, object]) -> subprocess.CompletedProcess[str]:
    """
    [Unit] helper: run the sweep hook against a throwaway git repo.

    Scenario:
        Given a repo path and an event
        When the hook runs in a subprocess with REPO_ROOT pointed at the repo
        Then the completed process is returned

    Boundaries:
        - Focus: isolation from the real repository
        - Fixtures/params: tmp git repo

    On failure, first check:
        - the REPO_ROOT patching in the inline script
    """
    code = (
        "import sys, pathlib\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "import _common\n"
        f"_common.REPO_ROOT = pathlib.Path({str(tmp_repo)!r})\n"
        f"_common.LOG_DIR = pathlib.Path({str(tmp_repo / '.logs')!r})\n"
        "import secret_sweep\n"
        "secret_sweep.REPO_ROOT = _common.REPO_ROOT\n"
        "secret_sweep.append_log = lambda *a, **k: None\n"
        "secret_sweep.main()\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code], input=json.dumps(event), capture_output=True, text=True, check=False
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """
    [Unit] fixture: an empty throwaway git repository.

    Scenario:
        Given a temporary directory
        When git init runs
        Then the directory is returned as a repository

    Boundaries:
        - Focus: isolation
        - Fixtures/params: tmp_path

    On failure, first check:
        - git is installed
    """
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def test_untracked_file_with_a_key_blocks_the_stop_and_warns_the_user(repo):
    """
    [Unit] sweep hook: a key in an untracked file blocks the Stop and warns the user.

    Scenario:
        Given a throwaway git repo holding an untracked file with a key
        When the hook runs as a Stop event
        Then stdout carries decision block and a SECURITY WARNING systemMessage without the key

    Boundaries:
        - Focus: the end-to-end Stop contract
        - Fixtures/params: tmp git repo, subprocess

    On failure, first check:
        - candidate_files and the payload keys in main
    """
    (repo / "notes.md").write_text(f"```\n{LENZ}\n```\n", encoding="utf-8")
    proc = _run_hook(repo, {})
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["decision"] == "block" and "SECURITY WARNING" in payload["systemMessage"]
    assert LENZ not in proc.stdout


def test_repeat_stop_warns_but_does_not_block_again(repo):
    """
    [Unit] sweep hook: a repeat Stop warns without blocking again.

    Scenario:
        Given the same repo and an event with stop_hook_active true
        When the hook runs
        Then the payload has a systemMessage and no decision

    Boundaries:
        - Focus: loop prevention
        - Fixtures/params: tmp git repo, subprocess

    On failure, first check:
        - the stop_hook_active branch in main
    """
    (repo / "notes.md").write_text(LENZ + "\n", encoding="utf-8")
    payload = json.loads(_run_hook(repo, {"stop_hook_active": True}).stdout)
    assert "decision" not in payload and "SECURITY WARNING" in payload["systemMessage"]


def test_clean_repo_is_silent(repo):
    """
    [Unit] sweep hook: a clean repo produces no output.

    Scenario:
        Given a throwaway git repo with only plain text
        When the hook runs
        Then exit code is 0 and stdout is empty

    Boundaries:
        - Focus: no false alarm
        - Fixtures/params: tmp git repo, subprocess

    On failure, first check:
        - the CLEAN branch in main
    """
    (repo / "notes.md").write_text("plain text\n", encoding="utf-8")
    proc = _run_hook(repo, {})
    assert proc.returncode == 0 and proc.stdout == ""
