"""Tests for pre-commit hook manifest validation and hook execution behavior."""

import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / ".pre-commit-hooks.yaml"


def _parse_hooks_manifest(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml

        data = yaml.safe_load(text)
        if isinstance(data, list):
            return data
    except ImportError:
        pass

    hooks: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                hooks.append(current)
            current = {}
            line = line[2:].strip()
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            val_obj: object
            if val.lower() == "true":
                val_obj = True
            elif val.lower() == "false":
                val_obj = False
            elif val.isdigit():
                val_obj = int(val)
            else:
                val_obj = val
            current[key] = val_obj
    if current:
        hooks.append(current)
    return hooks


def _run_entry_command(entry_cmd: str, cwd: Path, *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    venv_bin = str(Path(sys.executable).parent)
    if venv_bin not in env.get("PATH", "").split(os.pathsep):
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    return subprocess.run(
        shlex.split(entry_cmd),
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        check=False,
    )


def test_hook_manifest_is_valid_yaml_with_expected_fields() -> None:
    """Validate that .pre-commit-hooks.yaml defines the expected docsentinel-fast entry."""
    assert MANIFEST_PATH.is_file(), f"{MANIFEST_PATH} does not exist"
    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    assert len(hooks) >= 1

    fast_hook = next((h for h in hooks if h.get("id") == "docsentinel-fast"), None)
    assert fast_hook is not None, "docsentinel-fast hook not found in manifest"

    assert fast_hook["id"] == "docsentinel-fast"
    assert fast_hook["entry"] == "docsentinel scan --profile fast"
    assert fast_hook["language"] == "python"
    assert fast_hook["pass_filenames"] is False
    assert fast_hook["always_run"] is True


def test_hook_entry_command_runs_clean_on_a_clean_tree(tmp_path: Path) -> None:
    """Verify that running the hook entry command on a clean tree exits with code 0."""
    clean_file = tmp_path / "clean.md"
    clean_file.write_text("# Clean document\n\nNo issues found.\n", encoding="utf-8")

    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next(h for h in hooks if h.get("id") == "docsentinel-fast")
    entry_cmd = str(fast_hook["entry"])

    proc = _run_entry_command(entry_cmd, cwd=tmp_path)
    assert proc.returncode == 0


def test_hook_entry_command_fails_on_planted_dangling_link(tmp_path: Path) -> None:
    """Verify that running the hook on a tree with a planted DS101 error exits non-zero."""
    broken_file = tmp_path / "broken.md"
    broken_file.write_text("[missing](missing.md)\n", encoding="utf-8")

    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next(h for h in hooks if h.get("id") == "docsentinel-fast")
    entry_cmd = str(fast_hook["entry"])

    proc = _run_entry_command(entry_cmd, cwd=tmp_path)
    assert proc.returncode == 1


def test_hook_entry_command_exits_zero_on_planted_stray_comment(tmp_path: Path) -> None:
    """Verify that running the hook on a tree with only a DS102 warning exits with code 0."""
    comment_file = tmp_path / "comment.md"
    comment_file.write_text("<!-- stray comment -->\n# Clean\n", encoding="utf-8")

    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next(h for h in hooks if h.get("id") == "docsentinel-fast")
    entry_cmd = str(fast_hook["entry"])

    proc = _run_entry_command(entry_cmd, cwd=tmp_path)
    assert proc.returncode == 0
