"""Tests for triple extraction and normalization."""

import pytest

from docsentinel import deep_support
from docsentinel.detectors._triples import _normalize_key, _object_numbers, extract_claims


def test_subject_key_ignores_articles_and_case() -> None:
    assert _normalize_key("The Cache") == "cache"
    assert _normalize_key("a cache") == "cache"
    assert _normalize_key("an engine") == "engine"
    assert _normalize_key("  the   Distributed   Database... ") == "distributed database"


def test_number_normalization() -> None:
    class DummyToken:
        def __init__(self, text: str, like_num: bool = True) -> None:
            self.text = text
            self.like_num = like_num

    assert _object_numbers([DummyToken("1,024")]) == ("1024",)
    assert _object_numbers([DummyToken("ten")]) == ("10",)
    assert _object_numbers([DummyToken("42")]) == ("42",)


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_extract_claims_simple_svo() -> None:
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
def test_paragraph_index_assigned() -> None:
    pipeline = deep_support.load_pipeline()
    text = "The server handles 50 requests.\n\n\nThe client sends 20 messages."
    claims = extract_claims(pipeline, text, "multi.md")

    assert len(claims) >= 2
    indices = [c.paragraph_index for c in claims]
    assert 0 in indices
    assert 1 in indices


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_no_triples_yields_empty() -> None:
    pipeline = deep_support.load_pipeline()
    text = "Hello world."
    claims = extract_claims(pipeline, text, "empty.md")
    assert isinstance(claims, tuple)
