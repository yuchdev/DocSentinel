"""Tests for DS301 fact-contradiction candidate detector."""

from pathlib import Path

import pytest

from docsentinel import deep_support, models
from docsentinel.detectors._triples import Claim
from docsentinel.detectors.contradictions import DS301, _candidate_findings, _disagree, detect
from docsentinel.rules import RULES


def test_ds301_registered_as_warning_deep() -> None:
    assert DS301.code == "DS301"
    assert DS301.profile == "deep"
    assert DS301.severity == "warning"
    assert RULES["DS301"].profile == "deep"
    assert RULES["DS301"].severity == "warning"


def test_disagree_on_number_mismatch() -> None:
    a = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="doc_a.md",
        paragraph_index=0,
    )
    b = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="256 entries",
        raw_sentence="The cache holds 256 entries.",
        object_numbers=("256",),
        object_entities=(),
        path="doc_b.md",
        paragraph_index=0,
    )
    assert _disagree(a, b) is True


def test_no_disagree_on_shared_number() -> None:
    a = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 to 200 entries",
        raw_sentence="The cache holds 100 to 200 entries.",
        object_numbers=("100", "200"),
        object_entities=(),
        path="doc_a.md",
        paragraph_index=0,
    )
    b = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="doc_b.md",
        paragraph_index=0,
    )
    assert _disagree(a, b) is False


def test_disagree_on_entity_mismatch() -> None:
    a = Claim(
        subject_key="service",
        predicate_key="uses",
        raw_subject="The service",
        raw_object="Acme Corp",
        raw_sentence="The service uses Acme Corp.",
        object_numbers=(),
        object_entities=("ORG:acme corp",),
        path="doc_a.md",
        paragraph_index=0,
    )
    b = Claim(
        subject_key="service",
        predicate_key="uses",
        raw_subject="The service",
        raw_object="Globex",
        raw_sentence="The service uses Globex.",
        object_numbers=(),
        object_entities=("ORG:globex",),
        path="doc_b.md",
        paragraph_index=0,
    )
    assert _disagree(a, b) is True


def test_no_disagree_when_one_side_has_no_payload() -> None:
    a = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="doc_a.md",
        paragraph_index=0,
    )
    b = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="items in memory",
        raw_sentence="The cache holds items in memory.",
        object_numbers=(),
        object_entities=(),
        path="doc_b.md",
        paragraph_index=0,
    )
    assert _disagree(a, b) is False


def test_same_document_pair_not_compared() -> None:
    a = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="doc_a.md",
        paragraph_index=0,
    )
    b = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="256 entries",
        raw_sentence="The cache holds 256 entries.",
        object_numbers=("256",),
        object_entities=(),
        path="doc_a.md",
        paragraph_index=1,
    )
    assert _disagree(a, b) is False
    findings = _candidate_findings((a, b))
    assert findings == ()


def test_single_finding_attached_to_greater_path() -> None:
    a = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="alpha.md",
        paragraph_index=0,
    )
    b = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="256 entries",
        raw_sentence="The cache holds 256 entries.",
        object_numbers=("256",),
        object_entities=(),
        path="beta.md",
        paragraph_index=0,
    )
    findings = _candidate_findings((a, b))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.path == "beta.md"
    assert "candidate" in finding.message
    assert "alpha.md" in finding.message
    assert "beta.md" in finding.message


def test_findings_are_deduplicated_and_sorted() -> None:
    a1 = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="alpha.md",
        paragraph_index=0,
    )
    a2 = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="100 entries",
        raw_sentence="The cache holds 100 entries.",
        object_numbers=("100",),
        object_entities=(),
        path="alpha.md",
        paragraph_index=1,
    )
    b = Claim(
        subject_key="cache",
        predicate_key="holds",
        raw_subject="The cache",
        raw_object="256 entries",
        raw_sentence="The cache holds 256 entries.",
        object_numbers=("256",),
        object_entities=(),
        path="beta.md",
        paragraph_index=0,
    )
    findings = _candidate_findings((a1, a2, b))
    assert len(findings) == 1


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_detect_end_to_end_number_contradiction(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.md").write_text("The cache holds 256 entries.", encoding="utf-8")

    docs = (
        models.Document("a.md", 29),
        models.Document("b.md", 29),
    )
    findings = detect(tmp_path, docs)
    assert len(findings) == 1
    assert findings[0].rule == "DS301"
    assert findings[0].path == "b.md"


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_detect_no_finding_when_consistent(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.md").write_text("The cache holds 100 entries.", encoding="utf-8")

    docs = (
        models.Document("a.md", 29),
        models.Document("b.md", 29),
    )
    findings = detect(tmp_path, docs)
    assert findings == ()


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_detect_skips_non_markdown(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("The cache holds 256 entries.", encoding="utf-8")

    docs = (
        models.Document("a.txt", 29),
        models.Document("b.txt", 29),
    )
    findings = detect(tmp_path, docs)
    assert findings == ()
