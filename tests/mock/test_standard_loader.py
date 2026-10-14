import builtins
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from docsentinel.detectors import loader
from docsentinel.detectors.loader import ensure_standard_loaded
from docsentinel.errors import ExtraNotInstalledError


@pytest.fixture(autouse=True)
def reset_standard_loader_state() -> Iterator[None]:
    """Reset the standard loader state between test runs."""
    original_loaded = loader._standard_loaded
    try:
        loader._standard_loaded = False
        yield
    finally:
        loader._standard_loaded = original_loaded


def test_loader_module_imports_without_heavy_deps():
    """
    [Unit] standard loader: verifies loader module imports without heavy deps.

    Scenario:
        Given test inputs and fixtures for loader module imports without heavy deps
        When test_loader_module_imports_without_heavy_deps executes the target flow
        Then the expected outcome for loader module imports without heavy deps is confirmed.

    Boundaries:
        - Focus: loader module imports without heavy deps
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to loader module imports without heavy deps
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    code = (
        "import sys\n"
        "import docsentinel.detectors.loader\n"
        "heavy = {'sklearn', 'textstat', 'docsig'}\n"
        "imported_heavy = heavy.intersection(sys.modules.keys())\n"
        "assert not imported_heavy, f'Heavy modules imported: {imported_heavy}'\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("missing_pkg", ["sklearn", "textstat", "docsig"])
def test_ensure_standard_loaded_raises_actionable_error_when_extra_missing(
    monkeypatch: pytest.MonkeyPatch, missing_pkg: str
):
    """
    [Unit] standard loader: verifies ensure standard loaded raises actionable error when extra missing.

    Scenario:
        Given test inputs and fixtures for ensure standard loaded raises actionable error when extra missing
        When test_ensure_standard_loaded_raises_actionable_error_when_extra_missing executes the target flow
        Then the expected outcome for ensure standard loaded raises actionable error when extra missing is confirmed.

    Boundaries:
        - Focus: ensure standard loaded raises actionable error when extra missing
        - Fixtures/params: monkeypatch, missing_pkg (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ensure standard loaded raises actionable error when extra missing
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        """Simulate missing optional package error."""
        if name == "docsentinel.detectors.standard":
            raise ModuleNotFoundError(f"No module named '{missing_pkg}'", name=missing_pkg)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ExtraNotInstalledError) as exc_info:
        ensure_standard_loaded()

    assert exc_info.value.extra == "standard"
    assert "docsentinel[standard]" in str(exc_info.value)
    assert f"No module named '{missing_pkg}'" in str(exc_info.value)


def test_ensure_standard_loaded_reraises_unrelated_import_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Unit] standard loader: verifies ensure standard loaded reraises unrelated import error.

    Scenario:
        Given test inputs and fixtures for ensure standard loaded reraises unrelated import error
        When test_ensure_standard_loaded_reraises_unrelated_import_error executes the target flow
        Then the expected outcome for ensure standard loaded reraises unrelated import error is confirmed.

    Boundaries:
        - Focus: ensure standard loaded reraises unrelated import error
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ensure standard loaded reraises unrelated import error
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        """Simulate unrelated submodule import error."""
        if name == "docsentinel.detectors.standard":
            raise ModuleNotFoundError(
                "No module named 'docsentinel.detectors.standard.typo'",
                name="docsentinel.detectors.standard.typo",
            )
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        ensure_standard_loaded()

    assert not isinstance(exc_info.value, ExtraNotInstalledError)
    assert exc_info.value.name == "docsentinel.detectors.standard.typo"


def test_ensure_standard_loaded_reraises_import_error_with_none_name(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Unit] standard loader: verifies ensure standard loaded reraises import error with none name.

    Scenario:
        Given test inputs and fixtures for ensure standard loaded reraises import error with none name
        When test_ensure_standard_loaded_reraises_import_error_with_none_name executes the target flow
        Then the expected outcome for ensure standard loaded reraises import error with none name is confirmed.

    Boundaries:
        - Focus: ensure standard loaded reraises import error with none name
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ensure standard loaded reraises import error with none name
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        """Simulate ImportError with None name."""
        if name == "docsentinel.detectors.standard":
            raise ImportError("cannot import name 'unrelated'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ImportError) as exc_info:
        ensure_standard_loaded()

    assert not isinstance(exc_info.value, ExtraNotInstalledError)


def test_ensure_standard_loaded_is_idempotent_on_success(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Unit] standard loader: verifies ensure standard loaded is idempotent on success.

    Scenario:
        Given test inputs and fixtures for ensure standard loaded is idempotent on success
        When test_ensure_standard_loaded_is_idempotent_on_success executes the target flow
        Then the expected outcome for ensure standard loaded is idempotent on success is confirmed.

    Boundaries:
        - Focus: ensure standard loaded is idempotent on success
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ensure standard loaded is idempotent on success
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    import_calls: list[str] = []
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        """Track import calls."""
        if name == "docsentinel.detectors.standard":
            import_calls.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    ensure_standard_loaded()
    assert len(import_calls) == 1
    assert loader._standard_loaded is True

    ensure_standard_loaded()
    assert len(import_calls) == 1


def test_failed_load_is_not_cached(
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Unit] standard loader: verifies failed load is not cached.

    Scenario:
        Given test inputs and fixtures for failed load is not cached
        When test_failed_load_is_not_cached executes the target flow
        Then the expected outcome for failed load is not cached is confirmed.

    Boundaries:
        - Focus: failed load is not cached
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to failed load is not cached
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    should_fail = True
    original_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        """Conditionally fail imports."""
        if name == "docsentinel.detectors.standard" and should_fail:
            raise ModuleNotFoundError("No module named 'sklearn'", name="sklearn")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ExtraNotInstalledError):
        ensure_standard_loaded()

    assert loader._standard_loaded is False

    should_fail = False
    ensure_standard_loaded()
    assert loader._standard_loaded is True


def test_engine_import_and_fast_scan_succeeds_with_heavy_modules_blocked(tmp_path: Path):
    """
    [Unit] standard loader: verifies engine import and fast scan succeeds with heavy modules blocked.

    Scenario:
        Given test inputs and fixtures for engine import and fast scan succeeds with heavy modules blocked
        When test_engine_import_and_fast_scan_succeeds_with_heavy_modules_blocked executes the target flow
        Then the expected outcome for engine import and fast scan succeeds with heavy modules blocked is confirmed.

    Boundaries:
        - Focus: engine import and fast scan succeeds with heavy modules blocked
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to engine import and fast scan succeeds with heavy modules blocked
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by standard loader
    """
    code = (
        "import sys\n"
        "for name in ('sklearn', 'textstat', 'docsig'):\n"
        "    sys.modules[name] = None\n"
        "from docsentinel import scan, Config\n"
        f"result = scan(r'{tmp_path}', config=Config(profile='fast'))\n"
        "assert result.profile == 'fast'\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
