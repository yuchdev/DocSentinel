"""Tests for pre-commit hook manifest validation and hook execution behavior."""

import importlib
import importlib.util
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from tests.asset_helpers import AssetCase

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / ".pre-commit-hooks.yaml"


def _parse_hooks_manifest(path: Path) -> list[dict[str, object]]:
    """Parse a pre-commit hooks YAML manifest file."""
    text = path.read_text(encoding="utf-8")
    if importlib.util.find_spec("yaml") is not None:
        yaml = importlib.import_module("yaml")
        data = yaml.safe_load(text)
        if isinstance(data, list):
            return data

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
            elif val.startswith("[") and val.endswith("]"):
                val_obj = [item.strip().strip("'\"") for item in val[1:-1].split(",") if item.strip()]
            else:
                val_obj = val
            current[key] = val_obj
    if current:
        hooks.append(current)
    return hooks


def _run_entry_command(entry_cmd: str, cwd: Path, *, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    """Execute a CLI entry point command within a specific working directory."""
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


def test_hook_manifest_is_valid_yaml_with_expected_fields():
    """
    [Integration] pre commit hook manifest: verifies hook manifest is valid yaml with expected fields.

    Scenario:
        Given the .pre-commit-hooks.yaml manifest exists
        When test_hook_manifest_is_valid_yaml_with_expected_fields parses the manifest
        Then docsentinel-fast is configured with python language and always_run enabled.

    Boundaries:
        - Focus: hook manifest is valid yaml with expected fields
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Content and syntax of .pre-commit-hooks.yaml
        - Required keys for docsentinel-fast hook entry
        - Recent changes in code paths exercised by pre commit hook manifest
    """
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


def test_hook_entry_command_runs_clean_on_a_clean_tree(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] pre commit hook manifest: verifies hook entry command runs clean on a clean tree.

    Scenario:
        Given a clean directory tree with valid Markdown (asset ds101/clean_document)
        When the hook entry command is executed
        Then it exits with code 0.

    Boundaries:
        - Focus: hook entry command runs clean on a clean tree
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Returncode and output of the hook entry command
        - The asset case materialized from tests/assets/ds101/clean_document
        - Recent changes in code paths exercised by pre commit hook manifest
    """
    case = asset_case("ds101", "clean_document")

    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next(h for h in hooks if h.get("id") == "docsentinel-fast")
    entry_cmd = str(fast_hook["entry"])

    proc = _run_entry_command(entry_cmd, cwd=case.root)
    assert proc.returncode == 0


def test_hook_entry_command_fails_on_planted_dangling_link(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] pre commit hook manifest: verifies hook entry command fails on planted dangling link.

    Scenario:
        Given a tree with a planted dangling Markdown link (DS101, asset ds101/dangling_file_link)
        When the hook entry command is executed
        Then it exits with code 1.

    Boundaries:
        - Focus: hook entry command fails on planted dangling link
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Returncode and output of the hook entry command
        - The asset case materialized from tests/assets/ds101/dangling_file_link
        - Recent changes in code paths exercised by pre commit hook manifest
    """
    case = asset_case("ds101", "dangling_file_link")

    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next(h for h in hooks if h.get("id") == "docsentinel-fast")
    entry_cmd = str(fast_hook["entry"])

    proc = _run_entry_command(entry_cmd, cwd=case.root)
    assert proc.returncode == 1


def test_hook_entry_command_exits_zero_on_planted_stray_comment(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] pre commit hook manifest: verifies hook entry command exits zero on planted stray comment.

    Scenario:
        Given a tree with only a stray HTML comment warning (DS102, asset ds102/stray_comment_before_heading)
        When the hook entry command is executed
        Then it exits with code 0 because warnings do not fail the fast profile.

    Boundaries:
        - Focus: hook entry command exits zero on planted stray comment
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Returncode and output of the hook entry command
        - The asset case materialized from tests/assets/ds102/stray_comment_before_heading
        - Recent changes in code paths exercised by pre commit hook manifest
    """
    case = asset_case("ds102", "stray_comment_before_heading")

    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next(h for h in hooks if h.get("id") == "docsentinel-fast")
    entry_cmd = str(fast_hook["entry"])

    proc = _run_entry_command(entry_cmd, cwd=case.root)
    assert proc.returncode == 0


def test_standard_hook_present_and_opt_in():
    """
    [Integration] pre commit hook manifest: verifies standard hook present and opt in.

    Scenario:
        Given the .pre-commit-hooks.yaml manifest exists
        When test_standard_hook_present_and_opt_in inspects the manifest
        Then docsentinel-standard is present and configured for manual stage only.

    Boundaries:
        - Focus: standard hook present and opt in
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Configuration of docsentinel-standard in .pre-commit-hooks.yaml
        - Stages configuration in manifest
        - Recent changes in code paths exercised by pre commit hook manifest
    """
    assert MANIFEST_PATH.is_file(), f"{MANIFEST_PATH} does not exist"
    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    standard_hook = next((h for h in hooks if h.get("id") == "docsentinel-standard"), None)
    assert standard_hook is not None, "docsentinel-standard hook not found in manifest"

    assert standard_hook["id"] == "docsentinel-standard"
    assert standard_hook["entry"] == "docsentinel scan --profile standard --baseline .docsentinel-standard-baseline.json"
    assert standard_hook["language"] == "python"
    assert standard_hook["pass_filenames"] is False
    assert standard_hook["always_run"] is True
    assert standard_hook.get("stages") == ["manual"]
    deps = standard_hook.get("additional_dependencies")
    assert isinstance(deps, list)
    assert any("docsentinel[standard]" in dep for dep in deps)


def test_fast_hook_is_still_default_and_unchanged():
    """
    [Integration] pre commit hook manifest: verifies fast hook is still default and unchanged.

    Scenario:
        Given the .pre-commit-hooks.yaml manifest exists
        When test_fast_hook_is_still_default_and_unchanged inspects docsentinel-fast
        Then it has no stages restriction and remains the default hook.

    Boundaries:
        - Focus: fast hook is still default and unchanged
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - docsentinel-fast entry in .pre-commit-hooks.yaml
        - Entry command and options
        - Recent changes in code paths exercised by pre commit hook manifest
    """
    assert MANIFEST_PATH.is_file(), f"{MANIFEST_PATH} does not exist"
    hooks = _parse_hooks_manifest(MANIFEST_PATH)
    fast_hook = next((h for h in hooks if h.get("id") == "docsentinel-fast"), None)
    assert fast_hook is not None, "docsentinel-fast hook not found in manifest"

    assert "stages" not in fast_hook
    assert fast_hook["always_run"] is True
    assert fast_hook["pass_filenames"] is False
    assert fast_hook["entry"] == "docsentinel scan --profile fast"


def test_standard_and_fast_use_separate_baseline_files():
    """
    [Integration] pre commit hook manifest: verifies standard and fast use separate baseline files.

    Scenario:
        Given fast and standard baseline files in the repository
        When test_standard_and_fast_use_separate_baseline_files checks their existence and CI references
        Then each profile has its distinct baseline file and standard lane references its baseline.

    Boundaries:
        - Focus: standard and fast use separate baseline files
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Existence of .docsentinel-baseline.json and .docsentinel-standard-baseline.json
        - References in .github/workflows/ci.yml
        - Recent changes in code paths exercised by pre commit hook manifest
    """
    ci_workflow_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_workflow_path.is_file(), f"{ci_workflow_path} does not exist"
    ci_content = ci_workflow_path.read_text(encoding="utf-8")

    fast_baseline_path = REPO_ROOT / ".docsentinel-baseline.json"
    standard_baseline_path = REPO_ROOT / ".docsentinel-standard-baseline.json"

    assert fast_baseline_path.name != standard_baseline_path.name
    assert standard_baseline_path.is_file(), f"{standard_baseline_path} does not exist"
    assert fast_baseline_path.is_file(), f"{fast_baseline_path} does not exist"

    # CI standard lane must explicitly reference the standard baseline file
    assert ".docsentinel-standard-baseline.json" in ci_content
    assert "--profile standard" in ci_content
