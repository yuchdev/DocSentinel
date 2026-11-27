"""Fact checks in the packaged reports (owner ruling of 2026-11-27).

``text`` prints one ``Fact check:`` line per checked fact and one indented line per rated claim;
``json`` adds a top-level ``fact_checks`` array that is omitted when there are none; ``json-v1``
and ``github`` are unchanged. Every value is built in memory: no scan, no backend.
"""

from __future__ import annotations

import json

import pytest

from docsentinel.config import Config
from docsentinel.models import Document, FactCheck, FactCheckClaim, ScanResult
from docsentinel.reporting import render
from docsentinel.telemetry.model import CONTEXT_SCHEMA, FACT_CHECK_CLAIM_SCHEMA, FACT_CHECK_SCHEMA, ReportModel

#: Untrusted text with an ANSI escape, the GitHub command marker, a bidi override and a zero-width space.
_HOSTILE_FACT = "Bad\x1b[31m ##[x] fact.‮"
_HOSTILE_CLAIM = "c​1"


def _result(*checks: FactCheck) -> ScanResult:
    """Return a deep scan result of one clean document with the given fact checks.

    :param checks: The fact checks.
    :returns: The result.
    """
    return ScanResult(
        profile="deep",
        documents=(Document("a.md", 3),),
        findings=(),
        enabled_rules=("DS302",),
        pending=(),
        fact_checks=checks,
    )


def _checks() -> tuple[FactCheck, ...]:
    """Return one reported fact with a hostile text and two rated claims, and one clean true fact.

    :returns: The fact checks.
    """
    return (
        FactCheck(
            path="a.md",
            fact=_HOSTILE_FACT,
            verdict="False",
            confidence=0.9,
            backend="lenz",
            reported=True,
            claims=(FactCheckClaim(_HOSTILE_CLAIM, "Mostly False", 0.6), FactCheckClaim("Two.", "True", 0.3)),
        ),
        FactCheck(path="b.md", fact="Fine.", verdict="True", confidence=0.75, backend="lenz", reported=False),
    )


def test_context_exposes_fact_checks_and_count():
    """
    [Unit] report context: verifies fact_checks and fact_checks_count are built from the result.

    Scenario:
        Given a result with two fact checks
        When ReportModel.build runs
        Then fact_checks lists both as plain objects in order, with float confidences and claim
        objects, and fact_checks_count is 2; the schema names exactly those members.

    Boundaries:
        - Focus: FACT_CHECK_SCHEMA / FACT_CHECK_CLAIM_SCHEMA and the context builder
        - Fixtures/params: none
        - Scope: telemetry.model.ReportModel

    On failure, first check:
        - The fact_checks entry in ReportModel.build
    """
    context = ReportModel.build(_result(*_checks()), Config())

    assert context["fact_checks_count"] == 2
    assert context["fact_checks"][0] == {
        "path": "a.md",
        "fact": _HOSTILE_FACT,
        "verdict": "False",
        "confidence": 0.9,
        "backend": "lenz",
        "reported": True,
        "claims": [
            {"claim": _HOSTILE_CLAIM, "verdict": "Mostly False", "confidence": 0.6},
            {"claim": "Two.", "verdict": "True", "confidence": 0.3},
        ],
    }
    assert context["fact_checks"][1]["claims"] == []
    assert set(context["fact_checks"][0]) == set(FACT_CHECK_SCHEMA)
    assert set(context["fact_checks"][0]["claims"][0]) == set(FACT_CHECK_CLAIM_SCHEMA)
    assert {"fact_checks", "fact_checks_count"} <= set(CONTEXT_SCHEMA)


def test_text_prints_fact_checks_with_untrusted_text_neutralised():
    """
    [Unit] text report: verifies one Fact check line per fact, one indented line per claim, neutralised.

    Scenario:
        Given a result with a reported fact holding an ANSI escape, '##[', a bidi override and a
        zero-width space in its text and claim, and a second true fact without claims
        When the text template renders it
        Then the report ends with the two Fact check lines, each followed by its claim lines,
        and no raw control, bidi or zero-width code point nor a raw '##[' reaches the output.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (fact checks in the text report), text sink safety
        - Fixtures/params: none
        - Scope: reporting.render with the packaged text template

    On failure, first check:
        - The fact_checks loop and its neutralize filters in telemetry/templates/text.json
    """
    report = render(_result(*_checks()))

    assert report.splitlines()[-4:] == [
        "Fact check: False (confidence 0.9) [a.md]: Bad\\x1b[31m ##\\[x] fact.\\u202e",
        "  Mostly False (confidence 0.6): c\\u200b1",
        "  True (confidence 0.3): Two.",
        "Fact check: True (confidence 0.75) [b.md]: Fine.",
    ]
    for raw in ("\x1b", "‮", "​", "##[x"):
        assert raw not in report


def test_json_adds_a_fact_checks_array():
    """
    [Unit] json report: verifies the top-level fact_checks array mirrors the context.

    Scenario:
        Given a result with two fact checks
        When the json template renders it
        Then the parsed report has a fact_checks array of two objects with every member, the
        claims in order, the untrusted text intact and only ASCII in the raw output.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (fact checks in the json report)
        - Fixtures/params: none
        - Scope: reporting.render with the packaged json template

    On failure, first check:
        - The fact_checks node of telemetry/templates/json.json
    """
    raw = render(_result(*_checks()), format="json")
    payload = json.loads(raw)

    assert raw.isascii()
    assert payload["fact_checks"] == [
        {
            "path": "a.md",
            "fact": _HOSTILE_FACT,
            "verdict": "False",
            "confidence": 0.9,
            "backend": "lenz",
            "reported": True,
            "claims": [
                {"claim": _HOSTILE_CLAIM, "verdict": "Mostly False", "confidence": 0.6},
                {"claim": "Two.", "verdict": "True", "confidence": 0.3},
            ],
        },
        {
            "path": "b.md",
            "fact": "Fine.",
            "verdict": "True",
            "confidence": 0.75,
            "backend": "lenz",
            "reported": False,
            "claims": [],
        },
    ]
    assert list(payload)[-1] == "fact_checks"


@pytest.mark.parametrize("name", ["json", "text", "json-v1", "github"])
def test_reports_without_fact_checks_carry_no_fact_check_output(name: str):
    """
    [Unit] reports: verifies a result without fact checks renders no fact-check key or line.

    Scenario:
        Given a deep result with fact_checks == ()
        When each packaged report template renders it
        Then json has no fact_checks key (it still ends with pending) and no report mentions
        'Fact check' or 'fact_checks'.

    Boundaries:
        - Focus: reports without fact checks stay as before ($omit_if, empty loop)
        - Fixtures/params: name
        - Scope: reporting.render

    On failure, first check:
        - The $omit_if of the fact_checks node in json.json and the loop in text.json
    """
    report = render(_result(), format=name)

    assert "fact_checks" not in report
    assert "Fact check" not in report
    if name == "json":
        assert list(json.loads(report))[-1] == "pending"


@pytest.mark.parametrize("name", ["json-v1", "github"])
def test_json_v1_and_github_ignore_fact_checks(name: str):
    """
    [Unit] reports: verifies json-v1 and github render the same with and without fact checks.

    Scenario:
        Given the same result with and without fact checks
        When json-v1 or github renders both
        Then the two reports are equal.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (json-v1 and github unchanged)
        - Fixtures/params: name
        - Scope: reporting.render

    On failure, first check:
        - Whether a fact_checks node was added to json-v1.json or github.json
    """
    assert render(_result(*_checks()), format=name) == render(_result(), format=name)
