"""End-to-end integration tests for deep profile scanning and gating."""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from docsentinel import Config, deep_support, scan


def test_import_engine_registers_ds301_without_spacy() -> None:
    code = (
        "import sys\n"
        "for name in ('spacy', 'textacy'):\n"
        "    sys.modules[name] = None\n"
        "from docsentinel.engine import ANALYZERS, RULES\n"
        "assert 'DS301' in ANALYZERS\n"
        "assert 'DS301' in RULES\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_unconfirmed_deep_does_not_load_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_pipeline() -> Any:
        raise AssertionError("Model load should not be called when deep is unconfirmed")

    monkeypatch.setattr(deep_support, "load_pipeline", fake_load_pipeline)

    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=False))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile requires explicit opt-in" in result.pending[0]


def test_confirmed_deep_deps_missing_does_not_load_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_load_pipeline() -> Any:
        raise AssertionError("Model load should not be called when deps are missing")

    monkeypatch.setattr(deep_support, "deep_ready", lambda: False)
    monkeypatch.setattr(deep_support, "load_pipeline", fake_load_pipeline)

    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile confirmed, but its dependencies are unavailable" in result.pending[0]


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_confirmed_ready_deep_reports_candidates(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.md").write_text("The cache holds 256 entries.", encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))
    assert len(result.findings) == 1
    assert result.findings[0].rule == "DS301"
    assert result.enabled_rules == ("DS301",)
    assert "evaluated" in result.notice
    assert "advisory" in result.notice


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_model_loaded_once_for_multi_document_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    load_count = 0
    real_load = deep_support.load_pipeline

    def spy_load() -> Any:
        nonlocal load_count
        load_count += 1
        return real_load()

    monkeypatch.setattr(deep_support, "load_pipeline", spy_load)

    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.md").write_text("The database holds 50 tables.", encoding="utf-8")
    (tmp_path / "c.md").write_text("The server handles 10 requests.", encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))
    assert len(result.documents) == 3
    assert load_count == 1


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_consistent_corpus_zero_candidates_but_evaluated_notice(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.md").write_text("The cache holds 100 entries.", encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="deep", deep_confirm=True))
    assert result.findings == ()
    assert result.enabled_rules == ("DS301",)
    assert "evaluated" in result.notice
    assert "not implemented" not in result.notice
