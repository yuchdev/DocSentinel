"""Tests for deep_support lazy loaders, probes, and readiness checks."""

import builtins
import importlib
import sys
from typing import Any

import pytest

from docsentinel import deep_support
from docsentinel.cli import _deep_doctor_lines, main


def test_deep_extra_hint_constant():
    """
    [Unit] deep support: verifies deep extra hint constant.

    Scenario:
        Given test inputs and fixtures for deep extra hint constant
        When test_deep_extra_hint_constant executes the target flow
        Then the expected outcome for deep extra hint constant is confirmed.

    Boundaries:
        - Focus: deep extra hint constant
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to deep extra hint constant
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    assert "pip install docsentinel[deep]" in deep_support.DEEP_EXTRA_HINT
    assert "python -m spacy download en_core_web_sm" in deep_support.DEEP_EXTRA_HINT


def test_model_name_constant():
    """
    [Unit] deep support: verifies model name constant.

    Scenario:
        Given test inputs and fixtures for model name constant
        When test_model_name_constant executes the target flow
        Then the expected outcome for model name constant is confirmed.

    Boundaries:
        - Focus: model name constant
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to model name constant
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    assert deep_support.MODEL_NAME == "en_core_web_sm"


def test_libraries_available_true_when_importable(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies libraries available true when importable.

    Scenario:
        Given test inputs and fixtures for libraries available true when importable
        When test_libraries_available_true_when_importable executes the target flow
        Then the expected outcome for libraries available true when importable is confirmed.

    Boundaries:
        - Focus: libraries available true when importable
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to libraries available true when importable
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    fake_spacy = object()
    fake_textacy = object()
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)
    monkeypatch.setitem(sys.modules, "textacy", fake_textacy)

    assert deep_support.libraries_available() is True


def test_libraries_available_false_when_missing(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies libraries available false when missing.

    Scenario:
        Given test inputs and fixtures for libraries available false when missing
        When test_libraries_available_false_when_missing executes the target flow
        Then the expected outcome for libraries available false when missing is confirmed.

    Boundaries:
        - Focus: libraries available false when missing
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to libraries available false when missing
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    orig_import_module = importlib.import_module

    def fake_import_module(name: str, *args: Any, **kwargs: Any) -> Any:
        """Simulate missing libraries by failing on target imports.

        ``libraries_available`` probes with ``importlib.import_module``, which does not go through
        ``builtins.__import__``; patching that hook would only work while the libraries are uninstalled.
        """
        if name in ("spacy", "textacy"):
            raise ImportError(f"No module named '{name}'")
        return orig_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    assert deep_support.libraries_available() is False


def test_model_available_false_without_spacy(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies model available false without spacy.

    Scenario:
        Given test inputs and fixtures for model available false without spacy
        When test_model_available_false_without_spacy executes the target flow
        Then the expected outcome for model available false without spacy is confirmed.

    Boundaries:
        - Focus: model available false without spacy
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to model available false without spacy
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    orig_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        """Simulate missing spaCy by failing on spacy imports."""
        if name.startswith("spacy"):
            raise ImportError("No module named 'spacy'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert deep_support.model_available() is False


def test_model_available_checks_spacy_util(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies model available checks spacy util.

    Scenario:
        Given test inputs and fixtures for model available checks spacy util
        When test_model_available_checks_spacy_util executes the target flow
        Then the expected outcome for model available checks spacy util is confirmed.

    Boundaries:
        - Focus: model available checks spacy util
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to model available checks spacy util
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """

    class FakeSpacyUtil:
        """Mock spacy.util module."""

        @staticmethod
        def is_package(name: str) -> bool:
            """Check if given model package name is installed."""
            return name == "en_core_web_sm"

    class FakeSpacy:
        """Mock spacy module."""

        util = FakeSpacyUtil

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy)
    monkeypatch.setitem(sys.modules, "spacy.util", FakeSpacyUtil)

    assert deep_support.model_available() is True


def test_deep_ready_requires_both(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies deep ready requires both.

    Scenario:
        Given test inputs and fixtures for deep ready requires both
        When test_deep_ready_requires_both executes the target flow
        Then the expected outcome for deep ready requires both is confirmed.

    Boundaries:
        - Focus: deep ready requires both
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to deep ready requires both
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)
    assert deep_support.deep_ready() is False

    monkeypatch.setattr(deep_support, "libraries_available", lambda: False)
    monkeypatch.setattr(deep_support, "model_available", lambda: True)
    assert deep_support.deep_ready() is False

    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: True)
    assert deep_support.deep_ready() is True


def test_load_pipeline_raises_actionable_when_missing(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies load pipeline raises actionable when missing.

    Scenario:
        Given test inputs and fixtures for load pipeline raises actionable when missing
        When test_load_pipeline_raises_actionable_when_missing executes the target flow
        Then the expected outcome for load pipeline raises actionable when missing is confirmed.

    Boundaries:
        - Focus: load pipeline raises actionable when missing
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load pipeline raises actionable when missing
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    orig_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        """Simulate missing spaCy during pipeline load."""
        if name.startswith("spacy"):
            raise ImportError("No module named 'spacy'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError) as exc_info:
        deep_support.load_pipeline()

    assert deep_support.DEEP_EXTRA_HINT in str(exc_info.value)
    assert "en_core_web_sm" in str(exc_info.value)


def test_load_pipeline_raises_when_model_load_fails(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies load pipeline raises when model load fails.

    Scenario:
        Given test inputs and fixtures for load pipeline raises when model load fails
        When test_load_pipeline_raises_when_model_load_fails executes the target flow
        Then the expected outcome for load pipeline raises when model load fails is confirmed.

    Boundaries:
        - Focus: load pipeline raises when model load fails
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to load pipeline raises when model load fails
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """

    class FakeSpacy:
        """Mock spacy module that fails to load model."""

        @staticmethod
        def load(name: str) -> Any:
            """Simulate model load failure."""
            raise OSError(f"Can't find model '{name}'")

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy)
    with pytest.raises(RuntimeError) as exc_info:
        deep_support.load_pipeline()

    assert deep_support.DEEP_EXTRA_HINT in str(exc_info.value)


def test_doctor_reports_deep_not_installed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] deep support: verifies doctor reports deep not installed.

    Scenario:
        Given test inputs and fixtures for doctor reports deep not installed
        When test_doctor_reports_deep_not_installed executes the target flow
        Then the expected outcome for doctor reports deep not installed is confirmed.

    Boundaries:
        - Focus: doctor reports deep not installed
        - Fixtures/params: monkeypatch, capsys
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to doctor reports deep not installed
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    monkeypatch.setattr(deep_support, "libraries_available", lambda: False)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)

    code = main(["doctor"])
    assert code == 0
    out = capsys.readouterr().out
    assert "deep profile: not ready" in out
    assert "✗ deep libraries missing" in out
    assert deep_support.DEEP_EXTRA_HINT in out


def test_doctor_reports_deep_ready(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] deep support: verifies doctor reports deep ready.

    Scenario:
        Given test inputs and fixtures for doctor reports deep ready
        When test_doctor_reports_deep_ready executes the target flow
        Then the expected outcome for doctor reports deep ready is confirmed.

    Boundaries:
        - Focus: doctor reports deep ready
        - Fixtures/params: monkeypatch, capsys
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to doctor reports deep ready
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: True)

    code = main(["doctor"])
    assert code == 0
    out = capsys.readouterr().out
    assert "deep profile: ready" in out
    assert "✓ deep libraries installed" in out
    assert "✓ deep model installed" in out
    assert "✗" not in out


def test_doctor_reports_libs_present_model_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    """
    [Unit] deep support: verifies doctor reports libs present model missing.

    Scenario:
        Given test inputs and fixtures for doctor reports libs present model missing
        When test_doctor_reports_libs_present_model_missing executes the target flow
        Then the expected outcome for doctor reports libs present model missing is confirmed.

    Boundaries:
        - Focus: doctor reports libs present model missing
        - Fixtures/params: monkeypatch, capsys
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to doctor reports libs present model missing
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)

    code = main(["doctor"])
    assert code == 0
    out = capsys.readouterr().out
    assert "deep profile: not ready" in out
    assert "✓ deep libraries installed" in out
    assert "✗ deep model missing" in out
    assert "python -m spacy download en_core_web_sm" in out


def test_doctor_does_not_load_model(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies doctor does not load model.

    Scenario:
        Given test inputs and fixtures for doctor does not load model
        When test_doctor_does_not_load_model executes the target flow
        Then the expected outcome for doctor does not load model is confirmed.

    Boundaries:
        - Focus: doctor does not load model
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to doctor does not load model
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """

    def fake_load_pipeline() -> Any:
        """Fail if load_pipeline is invoked."""
        raise AssertionError("load_pipeline should not be called by doctor")

    monkeypatch.setattr(deep_support, "load_pipeline", fake_load_pipeline)
    code = main(["doctor"])
    assert code == 0


def test_deep_doctor_lines_pure(monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] deep support: verifies deep doctor lines pure.

    Scenario:
        Given test inputs and fixtures for deep doctor lines pure
        When test_deep_doctor_lines_pure executes the target flow
        Then the expected outcome for deep doctor lines pure is confirmed.

    Boundaries:
        - Focus: deep doctor lines pure
        - Fixtures/params: monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to deep doctor lines pure
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep support
    """
    monkeypatch.setattr(deep_support, "libraries_available", lambda: False)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)

    lines = _deep_doctor_lines()
    assert isinstance(lines, list)
    assert any("not ready" in line for line in lines)
