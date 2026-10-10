"""Tests for deep_support lazy loaders, probes, and readiness checks."""

import builtins
import sys
from typing import Any

import pytest

from docsentinel import deep_support
from docsentinel.cli import _deep_doctor_lines, main


def test_deep_extra_hint_constant() -> None:
    assert "pip install docsentinel[deep]" in deep_support.DEEP_EXTRA_HINT
    assert "python -m spacy download en_core_web_sm" in deep_support.DEEP_EXTRA_HINT


def test_model_name_constant() -> None:
    assert deep_support.MODEL_NAME == "en_core_web_sm"


def test_libraries_available_true_when_importable(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_spacy = object()
    fake_textacy = object()
    monkeypatch.setitem(sys.modules, "spacy", fake_spacy)
    monkeypatch.setitem(sys.modules, "textacy", fake_textacy)

    assert deep_support.libraries_available() is True


def test_libraries_available_false_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    orig_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name in ("spacy", "textacy"):
            raise ImportError(f"No module named '{name}'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert deep_support.libraries_available() is False


def test_model_available_false_without_spacy(monkeypatch: pytest.MonkeyPatch) -> None:
    orig_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("spacy"):
            raise ImportError("No module named 'spacy'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert deep_support.model_available() is False


def test_model_available_checks_spacy_util(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSpacyUtil:
        @staticmethod
        def is_package(name: str) -> bool:
            return name == "en_core_web_sm"

    class FakeSpacy:
        util = FakeSpacyUtil

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy)
    monkeypatch.setitem(sys.modules, "spacy.util", FakeSpacyUtil)

    assert deep_support.model_available() is True


def test_deep_ready_requires_both(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)
    assert deep_support.deep_ready() is False

    monkeypatch.setattr(deep_support, "libraries_available", lambda: False)
    monkeypatch.setattr(deep_support, "model_available", lambda: True)
    assert deep_support.deep_ready() is False

    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: True)
    assert deep_support.deep_ready() is True


def test_load_pipeline_raises_actionable_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    orig_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("spacy"):
            raise ImportError("No module named 'spacy'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError) as exc_info:
        deep_support.load_pipeline()

    assert deep_support.DEEP_EXTRA_HINT in str(exc_info.value)
    assert "en_core_web_sm" in str(exc_info.value)


def test_load_pipeline_raises_when_model_load_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSpacy:
        @staticmethod
        def load(name: str) -> Any:
            raise OSError(f"Can't find model '{name}'")

    monkeypatch.setitem(sys.modules, "spacy", FakeSpacy)
    with pytest.raises(RuntimeError) as exc_info:
        deep_support.load_pipeline()

    assert deep_support.DEEP_EXTRA_HINT in str(exc_info.value)


def test_doctor_reports_deep_not_installed(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(deep_support, "libraries_available", lambda: False)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)

    code = main(["doctor"])
    assert code == 0
    out = capsys.readouterr().out
    assert "deep profile: not ready" in out
    assert "✗ deep libraries missing" in out
    assert deep_support.DEEP_EXTRA_HINT in out


def test_doctor_reports_deep_ready(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: True)

    code = main(["doctor"])
    assert code == 0
    out = capsys.readouterr().out
    assert "deep profile: ready" in out
    assert "✓ deep libraries installed" in out
    assert "✓ deep model installed" in out
    assert "✗" not in out


def test_doctor_reports_libs_present_model_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(deep_support, "libraries_available", lambda: True)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)

    code = main(["doctor"])
    assert code == 0
    out = capsys.readouterr().out
    assert "deep profile: not ready" in out
    assert "✓ deep libraries installed" in out
    assert "✗ deep model missing" in out
    assert "python -m spacy download en_core_web_sm" in out


def test_doctor_does_not_load_model(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_pipeline() -> Any:
        raise AssertionError("load_pipeline should not be called by doctor")

    monkeypatch.setattr(deep_support, "load_pipeline", fake_load_pipeline)
    code = main(["doctor"])
    assert code == 0


def test_deep_doctor_lines_pure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deep_support, "libraries_available", lambda: False)
    monkeypatch.setattr(deep_support, "model_available", lambda: False)

    lines = _deep_doctor_lines()
    assert isinstance(lines, list)
    assert any("not ready" in line for line in lines)
