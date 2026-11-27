"""Explicit verdict labels of ``docsentinel.fact_check.protocol`` (owner ruling of 2026-11-27).

Covers ``VERDICT_LABELS`` (severity order), ``VERDICT_DEFAULT_LABELS``, the ``ClaimVerdict`` value
object and the ``label``/``claims`` fields and ``display`` property of ``FactCheckResult``. Pure
value objects: no backend, no network, no environment.
"""

from __future__ import annotations

import pytest

from docsentinel.fact_check.protocol import (
    MAX_RESULT_CLAIM_CHARS,
    MAX_RESULT_CLAIMS,
    VERDICT_DEFAULT_LABELS,
    VERDICT_LABELS,
    VERDICTS,
    ClaimVerdict,
    FactCheckError,
    FactCheckResult,
)


def test_verdict_labels_are_in_severity_order_and_defaults_cover_every_verdict():
    """
    [Unit] verdict labels: verifies the six labels, their order and the default label per verdict.

    Scenario:
        Given the protocol constants
        When VERDICT_LABELS and VERDICT_DEFAULT_LABELS are read
        Then the labels run from False to True in severity order and every verdict has a default
        label taken from VERDICT_LABELS.

    Boundaries:
        - Focus: owner ruling of 2026-11-27 (explicit labels)
        - Fixtures/params: none
        - Scope: module constants only

    On failure, first check:
        - VERDICT_LABELS and VERDICT_DEFAULT_LABELS in fact_check/protocol.py
    """
    assert VERDICT_LABELS == ("False", "Mostly False", "Mixed", "Unverifiable", "Mostly True", "True")
    assert dict(VERDICT_DEFAULT_LABELS) == {
        "true": "True",
        "false": "False",
        "mixed": "Mixed",
        "unverifiable": "Unverifiable",
    }
    assert set(VERDICT_DEFAULT_LABELS) == set(VERDICTS)
    assert set(VERDICT_DEFAULT_LABELS.values()) <= set(VERDICT_LABELS)


@pytest.mark.parametrize("label", VERDICT_LABELS)
def test_claim_verdict_accepts_every_label(label: str):
    """
    [Unit] ClaimVerdict: verifies a valid rated claim constructs with each label and is frozen.

    Scenario:
        Given a claim text, one of the six labels and a confidence in [0, 1]
        When ClaimVerdict is constructed
        Then the fields are kept and assigning one raises.

    Boundaries:
        - Focus: happy path for every label
        - Fixtures/params: label
        - Scope: value object only

    On failure, first check:
        - ClaimVerdict.__post_init__ in fact_check/protocol.py
    """
    part = ClaimVerdict("The sky is blue.", label, 0.9)

    assert (part.claim, part.label, part.confidence) == ("The sky is blue.", label, 0.9)
    with pytest.raises(AttributeError):
        part.label = "True"  # type: ignore[misc]


def test_claim_verdict_bounds_are_inclusive():
    """
    [Unit] ClaimVerdict: verifies the edge values of claim length and confidence are accepted.

    Scenario:
        Given an empty claim, a claim of exactly MAX_RESULT_CLAIM_CHARS characters and the
        confidences 0, 0.0 and 1.0
        When ClaimVerdict is constructed
        Then each construction succeeds.

    Boundaries:
        - Focus: inclusive bounds
        - Fixtures/params: none
        - Scope: value object only

    On failure, first check:
        - The length and range comparisons in ClaimVerdict.__post_init__
    """
    assert ClaimVerdict("", "Mixed", 0).confidence == 0
    assert ClaimVerdict("x" * MAX_RESULT_CLAIM_CHARS, "True", 1.0).claim == "x" * MAX_RESULT_CLAIM_CHARS
    assert ClaimVerdict("a", "False", 0.0).confidence == 0.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"claim": None},
        {"claim": 7},
        {"claim": "x" * (MAX_RESULT_CLAIM_CHARS + 1)},
        {"label": "true"},
        {"label": "Half True"},
        {"label": ""},
        {"label": None},
        {"confidence": True},
        {"confidence": float("nan")},
        {"confidence": float("inf")},
        {"confidence": -0.01},
        {"confidence": 1.01},
        {"confidence": "0.9"},
    ],
    ids=repr,
)
def test_claim_verdict_refuses_invalid_fields(kwargs: dict[str, object]):
    """
    [Unit] ClaimVerdict: verifies every invalid field raises FactCheckError with a fixed message.

    Scenario:
        Given a valid rated claim with one field replaced by an invalid value
        When ClaimVerdict is constructed
        Then FactCheckError is raised and its message echoes no field value.

    Boundaries:
        - Focus: raw labels, bool and non-finite confidence, over-long claim
        - Fixtures/params: one invalid value per case
        - Scope: value object only

    On failure, first check:
        - ClaimVerdict.__post_init__ in fact_check/protocol.py
    """
    fields: dict[str, object] = {"claim": "c", "label": "True", "confidence": 0.5}
    fields.update(kwargs)
    with pytest.raises(FactCheckError) as caught:
        ClaimVerdict(**fields)  # type: ignore[arg-type]
    assert str(caught.value).startswith("fact-check result: a rated claim ")
    assert "x" * 50 not in str(caught.value)


@pytest.mark.parametrize(("verdict", "expected"), sorted(VERDICT_DEFAULT_LABELS.items()))
def test_display_defaults_to_the_verdict_label(verdict: str, expected: str):
    """
    [Unit] FactCheckResult.display: verifies an empty label shows the default label of the verdict.

    Scenario:
        Given a result built with no label (a backend that has no finer rating)
        When display is read
        Then it is the VERDICT_DEFAULT_LABELS entry and claims is empty.

    Boundaries:
        - Focus: backward-compatible default of the new fields
        - Fixtures/params: verdict, expected
        - Scope: value object only

    On failure, first check:
        - FactCheckResult.display in fact_check/protocol.py
    """
    result = FactCheckResult(verdict, 0.5, "lenz")  # type: ignore[arg-type]

    assert result.label == ""
    assert result.claims == ()
    assert result.display == expected


def test_display_prefers_the_explicit_label_and_keeps_claims():
    """
    [Unit] FactCheckResult.display: verifies an explicit label wins and the rated claims are kept.

    Scenario:
        Given a true result labelled Mostly True with two rated claims
        When display and claims are read
        Then display is Mostly True and claims holds both ClaimVerdicts in order.

    Boundaries:
        - Focus: label and claims fields
        - Fixtures/params: none
        - Scope: value object only

    On failure, first check:
        - FactCheckResult fields and display in fact_check/protocol.py
    """
    parts = (ClaimVerdict("A.", "True", 0.9), ClaimVerdict("B.", "Mostly True", 0.6))
    result = FactCheckResult("true", 0.6, "lenz", label="Mostly True", claims=parts)

    assert result.display == "Mostly True"
    assert result.claims == parts


def test_result_accepts_exactly_max_result_claims():
    """
    [Unit] FactCheckResult: verifies MAX_RESULT_CLAIMS rated claims are accepted.

    Scenario:
        Given exactly MAX_RESULT_CLAIMS rated claims
        When FactCheckResult is constructed
        Then construction succeeds.

    Boundaries:
        - Focus: inclusive upper bound of claims
        - Fixtures/params: none
        - Scope: value object only

    On failure, first check:
        - The claims length check in FactCheckResult.__post_init__
    """
    parts = (ClaimVerdict("c", "False", 0.9),) * MAX_RESULT_CLAIMS

    assert len(FactCheckResult("false", 0.9, "lenz", label="False", claims=parts).claims) == MAX_RESULT_CLAIMS


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"label": "false"}, "fact-check result: label is not a known label"),
        ({"label": "Half True"}, "fact-check result: label is not a known label"),
        ({"label": None}, "fact-check result: label is not a known label"),
        ({"claims": [ClaimVerdict("c", "True", 0.5)]}, "fact-check result: claims is not a tuple of rated claims"),
        ({"claims": ("c",)}, "fact-check result: claims is not a tuple of rated claims"),
        (
            {"claims": (ClaimVerdict("c", "True", 0.5),) * (MAX_RESULT_CLAIMS + 1)},
            "fact-check result: too many rated claims",
        ),
    ],
    ids=["raw-false", "half-true", "none", "list", "str-member", "too-many"],
)
def test_result_refuses_invalid_label_and_claims(kwargs: dict[str, object], message: str):
    """
    [Unit] FactCheckResult: verifies an unknown label or malformed claims raise FactCheckError.

    Scenario:
        Given a valid result with an invalid label or claims value
        When FactCheckResult is constructed
        Then FactCheckError is raised with the fixed message of that check.

    Boundaries:
        - Focus: validation of the two new fields
        - Fixtures/params: kwargs, message
        - Scope: value object only

    On failure, first check:
        - The label and claims checks in FactCheckResult.__post_init__
    """
    with pytest.raises(FactCheckError) as caught:
        FactCheckResult("true", 0.5, "lenz", **kwargs)  # type: ignore[arg-type]
    assert str(caught.value) == message
