"""Integration tests for DS202 (duplicated text) over text assets in ``tests/assets/ds202``."""

from collections.abc import Callable

import pytest

pytest.importorskip("sklearn")

from docsentinel.detectors.standard import corpus, duplication
from tests.asset_helpers import AssetCase


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear corpus caches before running each duplicate text detector test."""
    corpus.clear_corpus_cache()


def test_identical_paragraphs_in_two_docs_are_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors duplication ds202: verifies identical paragraphs in two docs are flagged.

    Scenario:
        Given test inputs and fixtures for identical paragraphs in two docs are flagged
        When test_identical_paragraphs_in_two_docs_are_flagged executes the target flow
        Then the expected outcome for identical paragraphs in two docs are flagged is confirmed.

    Boundaries:
        - Focus: identical paragraphs in two docs are flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to identical paragraphs in two docs are flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    case = asset_case("ds202", "identical_paragraphs")

    findings = duplication.detect(case.root, case.documents("a.md", "b.md"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS202"
    assert finding.path == "b.md"
    assert finding.severity == "warning"
    assert finding.line == 1
    assert "near-duplicate of a.md#chunk0 (cosine 1.00)" in finding.message


def test_near_duplicate_above_threshold_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors duplication ds202: verifies near duplicate above threshold is flagged.

    Scenario:
        Given test inputs and fixtures for near duplicate above threshold is flagged
        When test_near_duplicate_above_threshold_is_flagged executes the target flow
        Then the expected outcome for near duplicate above threshold is flagged is confirmed.

    Boundaries:
        - Focus: near duplicate above threshold is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to near duplicate above threshold is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    case = asset_case("ds202", "near_duplicate_paragraphs")

    findings = duplication.detect(case.root, case.documents("a.md", "b.md"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS202"
    assert finding.path == "b.md"
    assert "near-duplicate of a.md#chunk0" in finding.message


def test_distinct_paragraphs_below_threshold_are_clean(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors duplication ds202: verifies distinct paragraphs below threshold are clean.

    Scenario:
        Given test inputs and fixtures for distinct paragraphs below threshold are clean
        When test_distinct_paragraphs_below_threshold_are_clean executes the target flow
        Then the expected outcome for distinct paragraphs below threshold are clean is confirmed.

    Boundaries:
        - Focus: distinct paragraphs below threshold are clean
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to distinct paragraphs below threshold are clean
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    case = asset_case("ds202", "distinct_paragraphs")

    assert duplication.detect(case.root, case.documents("a.md", "b.md")) == ()


def test_within_document_duplication_is_flagged(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors duplication ds202: verifies within document duplication is flagged.

    Scenario:
        Given test inputs and fixtures for within document duplication is flagged
        When test_within_document_duplication_is_flagged executes the target flow
        Then the expected outcome for within document duplication is flagged is confirmed.

    Boundaries:
        - Focus: within document duplication is flagged
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to within document duplication is flagged
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    case = asset_case("ds202", "within_document_duplication")

    findings = duplication.detect(case.root, case.documents("single.md"))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS202"
    assert finding.path == "single.md"
    assert finding.line == 7
    assert "near-duplicate of single.md#chunk0" in finding.message


def test_threshold_is_configurable(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors duplication ds202: verifies threshold is configurable.

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
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    case = asset_case("ds202", "near_duplicate_paragraphs")
    documents = case.documents("a.md", "b.md")
    config_file = case.path("doc_sentinel.toml")

    # With high threshold (0.99), near-duplicate is not flagged
    config_file.write_text("duplicate_similarity = 0.99\n", encoding="utf-8")
    findings_strict = duplication.detect(case.root, documents)
    assert findings_strict == ()

    # With lower threshold (0.50), it is flagged
    config_file.write_text("duplicate_similarity = 0.50\n", encoding="utf-8")
    findings_loose = duplication.detect(case.root, documents)
    assert len(findings_loose) == 1


def test_pair_reported_once_not_twice(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] detectors duplication ds202: verifies pair reported once not twice.

    Scenario:
        Given test inputs and fixtures for pair reported once not twice
        When test_pair_reported_once_not_twice executes the target flow
        Then the expected outcome for pair reported once not twice is confirmed.

    Boundaries:
        - Focus: pair reported once not twice
        - Fixtures/params: asset_case
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to pair reported once not twice
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    case = asset_case("ds202", "pair_reported_once")

    findings = duplication.detect(case.root, case.documents("a.md", "b.md", "c.md"))

    # 3 combinations: (a, b), (a, c), (b, c) -> 3 findings, not 6
    assert len(findings) == 3
    assert tuple((f.path, f.message[:25]) for f in findings) == (
        ("b.md", "near-duplicate of a.md#ch"),
        ("c.md", "near-duplicate of a.md#ch"),
        ("c.md", "near-duplicate of b.md#ch"),
    )


def test_empty_and_single_chunk_corpus_produce_no_findings(asset_case: Callable[[str, str], AssetCase]):
    # Empty documents tuple
    """
    [Integration] detectors duplication ds202: verifies empty and single chunk corpus produce no findings.

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
        - Recent changes in code paths exercised by detectors duplication ds202
    """
    single = asset_case("ds202", "single_chunk_corpus")
    assert duplication.detect(single.root, ()) == ()

    # Single document with one chunk
    assert duplication.detect(single.root, single.documents("single.md")) == ()

    # Non-markdown document
    non_markdown = asset_case("ds202", "non_markdown_document")
    assert duplication.detect(non_markdown.root, non_markdown.documents("notes.txt")) == ()
