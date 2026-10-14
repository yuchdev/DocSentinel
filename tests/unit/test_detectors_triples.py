"""Unit tests for triple key and number normalization (no NLP model required).

Claim extraction over documents is covered by ``tests/integration/test_triples_ds301.py``.
"""

from docsentinel.detectors._triples import _normalize_key, _object_numbers


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
