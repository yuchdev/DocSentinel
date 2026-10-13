"""Tests for DS301 fact-contradiction candidate detector."""

from pathlib import Path

import pytest

from docsentinel import deep_support, models
from docsentinel.detectors._triples import Claim
from docsentinel.detectors.contradictions import DS301, _candidate_findings, _disagree, detect
from docsentinel.rules import RULES


def test_ds301_registered_as_warning_deep() :
    """
    [Unit] detectors contradictions: verifies ds301 registered as warning deep.

    Scenario:
        Given test inputs and fixtures for ds301 registered as warning deep
        When test_ds301_registered_as_warning_deep executes the target flow
        Then the expected outcome for ds301 registered as warning deep is confirmed.

    Boundaries:
        - Focus: ds301 registered as warning deep
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to ds301 registered as warning deep
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
    assert DS301.code == "DS301"
    assert DS301.profile == "deep"
    assert DS301.severity == "warning"
    assert RULES["DS301"].profile == "deep"
    assert RULES["DS301"].severity == "warning"


def test_disagree_on_number_mismatch() :
    """
    [Unit] detectors contradictions: verifies disagree on number mismatch.

    Scenario:
        Given test inputs and fixtures for disagree on number mismatch
        When test_disagree_on_number_mismatch executes the target flow
        Then the expected outcome for disagree on number mismatch is confirmed.

    Boundaries:
        - Focus: disagree on number mismatch
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to disagree on number mismatch
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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


def test_no_disagree_on_shared_number() :
    """
    [Unit] detectors contradictions: verifies no disagree on shared number.

    Scenario:
        Given test inputs and fixtures for no disagree on shared number
        When test_no_disagree_on_shared_number executes the target flow
        Then the expected outcome for no disagree on shared number is confirmed.

    Boundaries:
        - Focus: no disagree on shared number
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to no disagree on shared number
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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


def test_disagree_on_entity_mismatch() :
    """
    [Unit] detectors contradictions: verifies disagree on entity mismatch.

    Scenario:
        Given test inputs and fixtures for disagree on entity mismatch
        When test_disagree_on_entity_mismatch executes the target flow
        Then the expected outcome for disagree on entity mismatch is confirmed.

    Boundaries:
        - Focus: disagree on entity mismatch
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to disagree on entity mismatch
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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


def test_no_disagree_when_one_side_has_no_payload() :
    """
    [Unit] detectors contradictions: verifies no disagree when one side has no payload.

    Scenario:
        Given test inputs and fixtures for no disagree when one side has no payload
        When test_no_disagree_when_one_side_has_no_payload executes the target flow
        Then the expected outcome for no disagree when one side has no payload is confirmed.

    Boundaries:
        - Focus: no disagree when one side has no payload
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to no disagree when one side has no payload
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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


def test_same_document_pair_not_compared() :
    """
    [Unit] detectors contradictions: verifies same document pair not compared.

    Scenario:
        Given test inputs and fixtures for same document pair not compared
        When test_same_document_pair_not_compared executes the target flow
        Then the expected outcome for same document pair not compared is confirmed.

    Boundaries:
        - Focus: same document pair not compared
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to same document pair not compared
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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


def test_single_finding_attached_to_greater_path() :
    """
    [Unit] detectors contradictions: verifies single finding attached to greater path.

    Scenario:
        Given test inputs and fixtures for single finding attached to greater path
        When test_single_finding_attached_to_greater_path executes the target flow
        Then the expected outcome for single finding attached to greater path is confirmed.

    Boundaries:
        - Focus: single finding attached to greater path
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to single finding attached to greater path
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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


def test_findings_are_deduplicated_and_sorted() :
    """
    [Unit] detectors contradictions: verifies findings are deduplicated and sorted.

    Scenario:
        Given test inputs and fixtures for findings are deduplicated and sorted
        When test_findings_are_deduplicated_and_sorted executes the target flow
        Then the expected outcome for findings are deduplicated and sorted is confirmed.

    Boundaries:
        - Focus: findings are deduplicated and sorted
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to findings are deduplicated and sorted
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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
def test_detect_end_to_end_number_contradiction(tmp_path: Path) :
    """
    [Unit] detectors contradictions: verifies detect end to end number contradiction.

    Scenario:
        Given test inputs and fixtures for detect end to end number contradiction
        When test_detect_end_to_end_number_contradiction executes the target flow
        Then the expected outcome for detect end to end number contradiction is confirmed.

    Boundaries:
        - Focus: detect end to end number contradiction
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect end to end number contradiction
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
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
def test_detect_no_finding_when_consistent(tmp_path: Path) :
    """
    [Unit] detectors contradictions: verifies detect no finding when consistent.

    Scenario:
        Given test inputs and fixtures for detect no finding when consistent
        When test_detect_no_finding_when_consistent executes the target flow
        Then the expected outcome for detect no finding when consistent is confirmed.

    Boundaries:
        - Focus: detect no finding when consistent
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect no finding when consistent
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
    (tmp_path / "a.md").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.md").write_text("The cache holds 100 entries.", encoding="utf-8")

    docs = (
        models.Document("a.md", 29),
        models.Document("b.md", 29),
    )
    findings = detect(tmp_path, docs)
    assert findings == ()


@pytest.mark.skipif(not deep_support.deep_ready(), reason="deep dependencies and model not installed")
def test_detect_skips_non_markdown(tmp_path: Path) :
    """
    [Unit] detectors contradictions: verifies detect skips non markdown.

    Scenario:
        Given test inputs and fixtures for detect skips non markdown
        When test_detect_skips_non_markdown executes the target flow
        Then the expected outcome for detect skips non markdown is confirmed.

    Boundaries:
        - Focus: detect skips non markdown
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect skips non markdown
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
    (tmp_path / "a.txt").write_text("The cache holds 100 entries.", encoding="utf-8")
    (tmp_path / "b.txt").write_text("The cache holds 256 entries.", encoding="utf-8")

    docs = (
        models.Document("a.txt", 29),
        models.Document("b.txt", 29),
    )
    findings = detect(tmp_path, docs)
    assert findings == ()
