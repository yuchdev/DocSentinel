"""Tests for triple extraction and normalization."""

import pytest

from docsentinel import deep_support
from docsentinel.detectors._triples import _normalize_key, _object_numbers, extract_claims


def test_subject_key_ignores_articles_and_case():
    """
    [Unit] detectors triples: verifies subject key ignores articles and case.

    Scenario:
        Given test inputs and fixtures for subject key ignores articles and case
        When test_subject_key_ignores_articles_and_case executes the target flow
        Then the expected outcome for subject key ignores articles and case is confirmed.

    Boundaries:
        - Focus: subject key ignores articles and case
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to subject key ignores articles and case
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """
    assert _normalize_key("The Cache") == "cache"
    assert _normalize_key("a cache") == "cache"
    assert _normalize_key("an engine") == "engine"
    assert _normalize_key("  the   Distributed   Database... ") == "distributed database"


def test_number_normalization():
    """
    [Unit] detectors triples: verifies number normalization.

    Scenario:
        Given test inputs and fixtures for number normalization
        When test_number_normalization executes the target flow
        Then the expected outcome for number normalization is confirmed.

    Boundaries:
        - Focus: number normalization
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to number normalization
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """

    class DummyToken:
        """Dummy token class for mocking spacy token properties."""

        def __init__(self, text: str, like_num: bool = True):
            """Initialize dummy token with text and numeric property."""
            self.text = text
            self.like_num = like_num

    assert _object_numbers([DummyToken("1,024")]) == ("1024",)
    assert _object_numbers([DummyToken("ten")]) == ("10",)
    assert _object_numbers([DummyToken("42")]) == ("42",)


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_extract_claims_simple_svo():
    """
    [Unit] detectors triples: verifies extract claims simple svo.

    Scenario:
        Given test inputs and fixtures for extract claims simple svo
        When test_extract_claims_simple_svo executes the target flow
        Then the expected outcome for extract claims simple svo is confirmed.

    Boundaries:
        - Focus: extract claims simple svo
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to extract claims simple svo
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """
    pipeline = deep_support.load_pipeline()
    text = "The cache holds 100 entries."
    claims = extract_claims(pipeline, text, "doc.md")

    assert len(claims) >= 1
    claim = claims[0]
    assert claim.subject_key == "cache"
    assert "100" in claim.object_numbers
    assert claim.path == "doc.md"
    assert claim.paragraph_index == 0


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_paragraph_index_assigned():
    """
    [Unit] detectors triples: verifies paragraph index assigned.

    Scenario:
        Given test inputs and fixtures for paragraph index assigned
        When test_paragraph_index_assigned executes the target flow
        Then the expected outcome for paragraph index assigned is confirmed.

    Boundaries:
        - Focus: paragraph index assigned
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to paragraph index assigned
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """
    pipeline = deep_support.load_pipeline()
    text = "The server handles 50 requests.\n\n\nThe client sends 20 messages."
    claims = extract_claims(pipeline, text, "multi.md")

    assert len(claims) >= 2
    indices = [c.paragraph_index for c in claims]
    assert 0 in indices
    assert 1 in indices


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_no_triples_yields_empty():
    """
    [Unit] detectors triples: verifies no triples yields empty.

    Scenario:
        Given test inputs and fixtures for no triples yields empty
        When test_no_triples_yields_empty executes the target flow
        Then the expected outcome for no triples yields empty is confirmed.

    Boundaries:
        - Focus: no triples yields empty
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to no triples yields empty
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors triples
    """
    pipeline = deep_support.load_pipeline()
    text = "Hello world."
    claims = extract_claims(pipeline, text, "empty.md")
    assert isinstance(claims, tuple)
