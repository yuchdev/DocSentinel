"""Integration tests for DS203 (low-information content) over text assets in ``tests/assets/ds203``."""

from collections.abc import Callable

import pytest

pytest.importorskip("sklearn")

from docsentinel.detectors.standard import corpus, low_information
from tests.asset_helpers import AssetCase


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear corpus caches prior to running low information detector tests."""
    corpus.clear_corpus_cache()


def test_filler_paragraph_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors low information ds203: verifies filler paragraph is flagged.

    Scenario:
        Given test inputs and fixtures for filler paragraph is flagged
        When test_filler_paragraph_is_flagged executes the target flow
        Then the expected outcome for filler paragraph is flagged is confirmed.

    Boundaries:
        - Focus: filler paragraph is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to filler paragraph is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information ds203
    """
    case = asset_case("ds203", "filler_paragraph")

    findings = low_information.detect(case.root, case.documents("a.md", "b.md", "filler.md"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS203"
    assert finding.path == "filler.md"
    assert finding.severity == "warning"
    assert finding.line == 1
    assert "low-information paragraph (score 0.00 < 0.15)" in finding.message


def test_informative_paragraph_is_clean(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors low information ds203: verifies informative paragraph is clean.

    Scenario:
        Given test inputs and fixtures for informative paragraph is clean
        When test_informative_paragraph_is_clean executes the target flow
        Then the expected outcome for informative paragraph is clean is confirmed.

    Boundaries:
        - Focus: informative paragraph is clean
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to informative paragraph is clean
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information ds203
    """
    case = asset_case("ds203", "informative_paragraphs")

    assert low_information.detect(case.root, case.documents("a.md", "b.md")) == ()


def test_keyword_list_not_flagged_despite_low_ttr(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors low information ds203: verifies keyword list not flagged despite low ttr.

    Scenario:
        Given test inputs and fixtures for keyword list not flagged despite low ttr
        When test_keyword_list_not_flagged_despite_low_ttr executes the target flow
        Then the expected outcome for keyword list not flagged despite low ttr is confirmed.

    Boundaries:
        - Focus: keyword list not flagged despite low ttr
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to keyword list not flagged despite low ttr
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information ds203
    """
    case = asset_case("ds203", "keyword_list")

    assert low_information.detect(case.root, case.documents("a.md", "b.md", "keywords.md")) == ()


def test_threshold_is_configurable(asset_case: Callable[[str, str], AssetCase]):
    # borderline.md: 16 distinct terms repeated 12 times -> TTR = 16/192 = 0.083, max_tfidf = 1/sqrt(16) = 0.25
    # norm_ttr = 0.083/0.5 = 0.167, norm_dist = 0.25/0.3 = 0.833 -> score ~ 0.37
    """
    [Integration] detectors low information ds203: verifies threshold is configurable.

    Scenario:
        Given test inputs and fixtures for threshold is configurable
        When test_threshold_is_configurable executes the target flow
        Then the expected outcome for threshold is configurable is confirmed.

    Boundaries:
        - Focus: threshold is configurable
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to threshold is configurable
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information ds203
    """
    case = asset_case("ds203", "borderline_paragraph")
    documents = case.documents("a.md", "b.md", "borderline.md")
    config_file = case.path("docsentinel.toml")

    # With higher threshold (0.40), borderline paragraph is flagged
    config_file.write_text("min_information_score = 0.40\n", encoding="utf-8")
    findings_strict = low_information.detect(case.root, documents)
    assert len(findings_strict) == 1
    assert findings_strict[0].path == "borderline.md"

    # With very low threshold (0.01), it is not flagged
    config_file.write_text("min_information_score = 0.01\n", encoding="utf-8")
    findings_loose = low_information.detect(case.root, documents)
    assert findings_loose == ()


def test_empty_and_single_chunk_corpus_produce_no_findings(asset_case: Callable[[str, str], AssetCase]):
    # Empty documents tuple
    """
    [Integration] detectors low information ds203: verifies empty and single chunk corpus produce no findings.

    Scenario:
        Given test inputs and fixtures for empty and single chunk corpus produce no findings
        When test_empty_and_single_chunk_corpus_produce_no_findings executes the target flow
        Then the expected outcome for empty and single chunk corpus produce no findings is confirmed.

    Boundaries:
        - Focus: empty and single chunk corpus produce no findings
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to empty and single chunk corpus produce no findings
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors low information ds203
    """
    single = asset_case("ds203", "single_chunk_corpus")
    assert low_information.detect(single.root, ()) == ()

    # Single document with one informative chunk
    assert low_information.detect(single.root, single.documents("single.md")) == ()

    # Non-markdown document
    non_markdown = asset_case("ds203", "non_markdown_document")
    assert low_information.detect(non_markdown.root, non_markdown.documents("notes.txt")) == ()
