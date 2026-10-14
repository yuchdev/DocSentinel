"""Unit tests for DS301 claim-comparison logic using hand-built ``Claim`` values (no NLP model, no files).

Detection over documents is covered by ``tests/integration/test_detectors_contradictions_ds301.py``.
"""

from docsentinel.detectors._triples import Claim
from docsentinel.detectors.contradictions import DS301, _candidate_findings, _disagree
from docsentinel.rules import RULES


def _claim(
    path: str,
    raw_object: str,
    object_numbers: tuple[str, ...] = (),
    object_entities: tuple[str, ...] = (),
    *,
    subject_key: str = "cache",
    predicate_key: str = "holds",
    raw_subject: str = "The cache",
    paragraph_index: int = 0,
) -> Claim:
    """Build a claim whose sentence is derived from its subject, predicate, and object."""
    return Claim(
        subject_key=subject_key,
        predicate_key=predicate_key,
        raw_subject=raw_subject,
        raw_object=raw_object,
        raw_sentence=f"{raw_subject} {predicate_key} {raw_object}.",
        object_numbers=object_numbers,
        object_entities=object_entities,
        path=path,
        paragraph_index=paragraph_index,
    )


def test_ds301_registered_as_warning_deep():
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


def test_disagree_on_number_mismatch():
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
    a = _claim("doc_a.md", "100 entries", ("100",))
    b = _claim("doc_b.md", "256 entries", ("256",))

    assert _disagree(a, b) is True


def test_no_disagree_on_shared_number():
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
    a = _claim("doc_a.md", "100 to 200 entries", ("100", "200"))
    b = _claim("doc_b.md", "100 entries", ("100",))

    assert _disagree(a, b) is False


def test_disagree_on_entity_mismatch():
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
    a = _claim(
        "doc_a.md",
        "Acme Corp",
        object_entities=("ORG:acme corp",),
        subject_key="service",
        predicate_key="uses",
        raw_subject="The service",
    )
    b = _claim(
        "doc_b.md",
        "Globex",
        object_entities=("ORG:globex",),
        subject_key="service",
        predicate_key="uses",
        raw_subject="The service",
    )

    assert _disagree(a, b) is True


def test_no_disagree_when_one_side_has_no_payload():
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
    a = _claim("doc_a.md", "100 entries", ("100",))
    b = _claim("doc_b.md", "items in memory")

    assert _disagree(a, b) is False


def test_same_document_pair_not_compared():
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
    a = _claim("doc_a.md", "100 entries", ("100",), paragraph_index=0)
    b = _claim("doc_a.md", "256 entries", ("256",), paragraph_index=1)

    assert _disagree(a, b) is False
    assert _candidate_findings((a, b)) == ()


def test_single_finding_attached_to_greater_path():
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
    a = _claim("alpha.md", "100 entries", ("100",))
    b = _claim("beta.md", "256 entries", ("256",))

    findings = _candidate_findings((a, b))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.path == "beta.md"
    assert "candidate" in finding.message
    assert "alpha.md" in finding.message
    assert "beta.md" in finding.message


def test_findings_are_deduplicated_and_sorted():
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
    a1 = _claim("alpha.md", "100 entries", ("100",), paragraph_index=0)
    a2 = _claim("alpha.md", "100 entries", ("100",), paragraph_index=1)
    b = _claim("beta.md", "256 entries", ("256",))

    assert len(_candidate_findings((a1, a2, b))) == 1


def test_claims_without_subject_or_predicate_are_not_grouped():
    """
    [Unit] detectors contradictions: verifies claims without subject or predicate are not grouped.

    Scenario:
        Given test inputs and fixtures for claims without subject or predicate are not grouped
        When test_claims_without_subject_or_predicate_are_not_grouped executes the target flow
        Then the expected outcome for claims without subject or predicate are not grouped is confirmed.

    Boundaries:
        - Focus: claims without subject or predicate are not grouped
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to claims without subject or predicate are not grouped
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors contradictions
    """
    a = _claim("alpha.md", "100 entries", ("100",), subject_key="")
    b = _claim("beta.md", "256 entries", ("256",), subject_key="")

    assert _candidate_findings((a, b)) == ()
