"""End-to-end integration tests for deep profile scanning and gating over text assets in ``tests/assets/ds301``."""

import subprocess
import sys
from collections.abc import Callable
from typing import Any

import pytest

from docsentinel import Config, deep_support, scan
from tests.asset_helpers import AssetCase


def test_import_engine_registers_ds301_without_spacy():
    """
    [Integration] deep profile end to end ds301: verifies import engine registers ds301 without spacy.

    Scenario:
        Given test inputs and fixtures for import engine registers ds301 without spacy
        When test_import_engine_registers_ds301_without_spacy executes the target flow
        Then the expected outcome for import engine registers ds301 without spacy is confirmed.

    Boundaries:
        - Focus: import engine registers ds301 without spacy
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to import engine registers ds301 without spacy
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep profile end to end ds301
    """
    code = (
        "import sys\n"
        "for name in ('textacy',):\n"
        "    sys.modules[name] = None\n"
        "from docsentinel.engine import ANALYZERS, RULES\n"
        "assert 'DS301' in ANALYZERS\n"
        "assert 'DS301' in RULES\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_unconfirmed_deep_does_not_load_model(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Integration] deep profile end to end ds301: verifies unconfirmed deep does not load model.

    Scenario:
        Given test inputs and fixtures for unconfirmed deep does not load model
        When test_unconfirmed_deep_does_not_load_model executes the target flow
        Then the expected outcome for unconfirmed deep does not load model is confirmed.

    Boundaries:
        - Focus: unconfirmed deep does not load model
        - Fixtures/params: asset_case, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to unconfirmed deep does not load model
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep profile end to end ds301
    """

    def fake_load_pipeline() -> Any:
        """Fail immediately if model pipeline loading is attempted."""
        raise AssertionError("Model load should not be called when deep is unconfirmed")

    monkeypatch.setattr(deep_support, "load_pipeline", fake_load_pipeline)
    case = asset_case("ds301", "single_claim_document")

    result = scan(case.root, config=Config(profile="deep", deep_confirm=False))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile requires explicit opt-in" in result.pending[0]


def test_confirmed_deep_deps_missing_does_not_load_model(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Integration] deep profile end to end ds301: verifies confirmed deep deps missing does not load model.

    Scenario:
        Given test inputs and fixtures for confirmed deep deps missing does not load model
        When test_confirmed_deep_deps_missing_does_not_load_model executes the target flow
        Then the expected outcome for confirmed deep deps missing does not load model is confirmed.

    Boundaries:
        - Focus: confirmed deep deps missing does not load model
        - Fixtures/params: asset_case, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to confirmed deep deps missing does not load model
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep profile end to end ds301
    """

    def fake_load_pipeline() -> Any:
        """Fail immediately if model pipeline loading is attempted."""
        raise AssertionError("Model load should not be called when deps are missing")

    monkeypatch.setattr(deep_support, "deep_ready", lambda: False)
    monkeypatch.setattr(deep_support, "load_pipeline", fake_load_pipeline)
    case = asset_case("ds301", "single_claim_document")

    result = scan(case.root, config=Config(profile="deep", deep_confirm=True))

    assert result.findings == ()
    assert result.enabled_rules == ()
    assert "deep profile confirmed, but its dependencies are unavailable" in result.pending[0]


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_confirmed_ready_deep_reports_candidates(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] deep profile end to end ds301: verifies confirmed ready deep reports candidates.

    Scenario:
        Given test inputs and fixtures for confirmed ready deep reports candidates
        When test_confirmed_ready_deep_reports_candidates executes the target flow
        Then the expected outcome for confirmed ready deep reports candidates is confirmed.

    Boundaries:
        - Focus: confirmed ready deep reports candidates
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to confirmed ready deep reports candidates
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep profile end to end ds301
    """
    case = asset_case("ds301", "number_contradiction")

    result = scan(case.root, config=Config(profile="deep", deep_confirm=True))

    assert len(result.findings) == 1
    assert result.findings[0].rule == "DS301"
    assert result.enabled_rules == ("DS301",)
    assert "evaluated" in result.notice
    assert "advisory" in result.notice


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_model_loaded_once_for_multi_document_corpus(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    [Integration] deep profile end to end ds301: verifies model loaded once for multi document corpus.

    Scenario:
        Given test inputs and fixtures for model loaded once for multi document corpus
        When test_model_loaded_once_for_multi_document_corpus executes the target flow
        Then the expected outcome for model loaded once for multi document corpus is confirmed.

    Boundaries:
        - Focus: model loaded once for multi document corpus
        - Fixtures/params: asset_case, monkeypatch
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to model loaded once for multi document corpus
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep profile end to end ds301
    """
    load_count = 0
    real_load = deep_support.load_pipeline

    def spy_load() -> Any:
        """Track invocation count while delegating to real load."""
        nonlocal load_count
        load_count += 1
        return real_load()

    monkeypatch.setattr(deep_support, "load_pipeline", spy_load)
    case = asset_case("ds301", "multi_document_corpus")

    result = scan(case.root, config=Config(profile="deep", deep_confirm=True))

    assert len(result.documents) == 3
    assert load_count == 1


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_consistent_corpus_zero_candidates_but_evaluated_notice(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] deep profile end to end ds301: verifies consistent corpus zero candidates but evaluated notice.

    Scenario:
        Given test inputs and fixtures for consistent corpus zero candidates but evaluated notice
        When test_consistent_corpus_zero_candidates_but_evaluated_notice executes the target flow
        Then the expected outcome for consistent corpus zero candidates but evaluated notice is confirmed.

    Boundaries:
        - Focus: consistent corpus zero candidates but evaluated notice
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to consistent corpus zero candidates but evaluated notice
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by deep profile end to end ds301
    """
    case = asset_case("ds301", "consistent_numbers")

    result = scan(case.root, config=Config(profile="deep", deep_confirm=True))

    assert result.findings == ()
    assert result.enabled_rules == ("DS301",)
    assert "evaluated" in result.notice
    assert "not implemented" not in result.notice
