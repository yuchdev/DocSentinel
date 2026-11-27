"""Verdict normalisation of the Lenz client (Story 03.0 Task 04 step 3, egress E9, owner ruling 2026-11-27).

The owner ruling of 2026-11-27 replaces ruling Q4: ``_normalize_verdict`` never returns ``None``.
``VERDICT_LABELS`` maps true/mostly true to ``true``, false/mostly false to ``false``, mixed/half
true to ``mixed`` and unverifiable to ``unverifiable`` (stripped, case-insensitive); every other
raw string, including the empty string, maps to ``unverifiable`` and is never an error. The raw
verdict strings are typed by hand here; nothing is imported from ``examples/``. The
``check_claim`` cases answer through an in-memory ``httpx.MockTransport``; no network is reached.
"""

from __future__ import annotations

import importlib
import json
import logging
from types import ModuleType

import httpx
import pytest

from tests.fact_check_fakes import SENTINEL

pytestmark = pytest.mark.usefixtures("lenz_module")


def _lenz() -> ModuleType:
    """Return the client module imported by the ``lenz_module`` fixture.

    :return: The module.
    """
    return importlib.import_module("docsentinel.fact_check.lenz")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("True", "true"),
        ("False", "false"),
        (" true ", "true"),
        ("FALSE", "false"),
        ("true", "true"),
        ("\tFalse\n", "false"),
        ("tRuE", "true"),
        ("Mostly True", "true"),
        (" mostly true ", "true"),
        ("Mostly False", "false"),
        ("MOSTLY FALSE", "false"),
        ("Mixed", "mixed"),
        ("mixed", "mixed"),
        ("Half True", "mixed"),
        ("Unverifiable", "unverifiable"),
        ("", "unverifiable"),
        ("   ", "unverifiable"),
        ("truthy", "unverifiable"),
        ("t", "unverifiable"),
        ("yes", "unverifiable"),
        ("1", "unverifiable"),
        ("True.", "unverifiable"),
        ("mostly  true", "unverifiable"),  # two spaces: not a listed label
        ("Truе", "unverifiable"),  # Cyrillic small ie, a confusable
        ("Ｔrue", "unverifiable"),  # full-width T
    ],
)
def test_normalize_verdict_known_and_unknown(raw: str, expected: str):
    """
    [Unit] lenz verdicts: verifies the VERDICT_LABELS mapping and the unverifiable fallback.

    Scenario:
        Given raw verdict strings typed by hand
        When _normalize_verdict maps them
        Then each listed label in any case and surrounding whitespace maps to its verdict; the
        empty string, unknown words and confusables map to unverifiable (never None).

    Boundaries:
        - Focus: E9, owner ruling 2026-11-27 (replaces Q4; no confidence band, no None)
        - Fixtures/params: raw, expected
        - Scope: lenz._normalize_verdict

    On failure, first check:
        - VERDICT_LABELS and the strip and casefold in _normalize_verdict

    :param raw: The raw verdict.
    :param expected: The mapped verdict.
    """
    assert _lenz()._normalize_verdict(raw) == expected


@pytest.mark.parametrize("raw", ["", "Bogus", "UNKNOWN-VERDICT-MARKER-0010"])
@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_unknown_verdict_is_unverifiable_through_check_claim(raw: str, confidence: float):
    """
    [Unit] lenz verdicts: verifies an unlisted verdict is unverifiable at every confidence, never an error.

    Scenario:
        Given an in-memory transport answering a one-claim body with an unlisted verdict
        When check_claim runs at confidence 0.0, 0.5 and 1.0
        Then the result is unverifiable with the sent confidence; no FactCheckError is raised.

    Boundaries:
        - Focus: E9, owner ruling 2026-11-27 (replaces Q4)
        - Fixtures/params: raw, confidence
        - Scope: LenzFactCheckClient.check_claim with httpx.MockTransport

    On failure, first check:
        - The unverifiable default of _normalize_verdict

    :param raw: The unlisted verdict.
    :param confidence: The confidence sent with it.
    """
    body = (
        b'{"claims": [{"claim": "x", "verdict": "'
        + raw.encode("ascii")
        + b'", "confidence": '
        + str(confidence).encode("ascii")
        + b"}]}"
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=httpx.ByteStream(body)))
    client = _lenz().LenzFactCheckClient(SENTINEL, transport=transport)
    result = client.check_claim("A claim.")
    client.close()
    assert (result.verdict, result.confidence) == ("unverifiable", confidence)


@pytest.mark.parametrize(
    ("raw", "expected"), [("True", "true"), ("False", "false"), (" true ", "true"), ("FALSE", "false")]
)
def test_known_verdict_through_check_claim(raw: str, expected: str):
    """
    [Unit] lenz verdicts: verifies a known verdict reaches the result through check_claim.

    Scenario:
        Given an in-memory transport answering a one-claim body with a known verdict
        When check_claim runs
        Then the result verdict is the normalised value.

    Boundaries:
        - Focus: E9 positive path
        - Fixtures/params: raw, expected
        - Scope: LenzFactCheckClient.check_claim with httpx.MockTransport

    On failure, first check:
        - _parse_assess's use of _normalize_verdict

    :param raw: The raw verdict.
    :param expected: The normalised verdict.
    """
    body = b'{"claims": [{"claim": "x", "verdict": "' + raw.encode("ascii") + b'", "confidence": 0.87}]}'
    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=httpx.ByteStream(body)))
    client = _lenz().LenzFactCheckClient(SENTINEL, transport=transport)
    result = client.check_claim("A claim.")
    client.close()
    assert (result.verdict, result.confidence) == (expected, 0.87)


@pytest.mark.parametrize(
    ("claims", "expected"),
    [
        ([{"verdict": "True", "confidence": "high"}], ("true", 0.9)),
        ([{"verdict": "False", "confidence": " Medium "}], ("false", 0.6)),
        (
            [
                {"verdict": "True", "confidence": "high"},
                {"verdict": "Mostly True", "confidence": "medium"},
                {"verdict": "True", "confidence": "low"},
            ],
            ("true", 0.3),
        ),
        (
            [
                {"verdict": "True", "confidence": "high"},
                {"verdict": "False", "confidence": "low"},
                {"verdict": "False", "confidence": 0.8},
            ],
            ("false", 0.8),
        ),
        (
            [
                {"verdict": "True", "confidence": "high"},
                {"verdict": "Half True", "confidence": "low"},
                {"verdict": "Bogus", "confidence": "high"},
            ],
            ("mixed", 0.3),
        ),
        (
            [{"verdict": "True", "confidence": "low"}, {"verdict": "Bogus", "confidence": "medium"}],
            ("unverifiable", 0.6),
        ),
        ([{"verdict": "Mostly True", "confidence": "high"}], ("true", 0.9)),
    ],
)
def test_parse_assess_reads_word_confidence_and_every_claim(claims: list, expected: tuple):
    """
    [Unit] lenz response: verifies word confidences and multi-claim answers give one result.

    Scenario:
        Given an /assess body with one or more claims rated with confidence words
        When _parse_assess reads it
        Then the result is the most severe verdict (false, mixed, unverifiable, true); an unlisted
        label counts as unverifiable; confidence is the minimum for true, the maximum otherwise.

    Boundaries:
        - Focus: the real Lenz response shape (confidence words, a combined fact split into claims)
        - Fixtures/params: claim lists
        - Scope: lenz._parse_assess

    On failure, first check:
        - CONFIDENCE_WORDS and the claim loop in _parse_assess
    """
    result = _lenz()._parse_assess(json.dumps({"claims": claims}).encode(), "lenz")

    assert (result.verdict, result.confidence) == expected


def test_parse_assess_refuses_unknown_confidence_word():
    """
    [Unit] lenz response: verifies an unknown confidence word fails, also behind a valid claim.

    Scenario:
        Given a claim with an unknown confidence word, alone or after a well-formed claim
        When _parse_assess reads it
        Then it raises FactCheckError.

    Boundaries:
        - Focus: fail-closed parsing
        - Fixtures/params: none
        - Scope: lenz._parse_assess

    On failure, first check:
        - _confidence and CONFIDENCE_WORDS
    """
    lenz = _lenz()
    for claims in (
        [{"verdict": "True", "confidence": "certain"}],
        [{"verdict": "True", "confidence": "high"}, {"verdict": "False", "confidence": "very"}],
    ):
        with pytest.raises(lenz.FactCheckError):
            lenz._parse_assess(json.dumps({"claims": claims}).encode(), "lenz")


def test_parse_assess_logs_one_info_line_per_claim(caplog: pytest.LogCaptureFixture):
    """
    [Unit] lenz response: verifies one INFO line per claim with its first words and explicit label.

    Scenario:
        Given an /assess body with three claims: one longer than ten words, one Mostly True and
        one with an unlisted verdict
        When _parse_assess reads it
        Then three INFO records name claim i/n, the quoted first ten words, the explicit label
        (False, Mostly True, Unverifiable; never the raw label nor a "(mapped)" suffix) and the
        confidence with two decimals.

    Boundaries:
        - Focus: owner rulings 2026-11-27 (every verdict printed, explicit labels)
        - Fixtures/params: caplog
        - Scope: lenz._parse_assess

    On failure, first check:
        - The logger.info call in the claim loop of _parse_assess, DISPLAY_LABELS and log.quote_start
    """
    claims = [
        {"claim": "one two three four five six seven eight nine ten eleven", "verdict": "False", "confidence": "high"},
        {"claim": "Mostly right.", "verdict": "mostly true", "confidence": "medium"},
        {"claim": "Short claim.", "verdict": "Bogus", "confidence": 0.5},
    ]
    with caplog.at_level(logging.INFO, logger="docsentinel.fact_check.lenz"):
        _lenz()._parse_assess(json.dumps({"claims": claims}).encode(), "lenz")

    assert [record.getMessage() for record in caplog.records if record.levelno == logging.INFO] == [
        'lenz /assess: claim 1/3 "one two three four five six seven eight nine ten ...": '
        "verdict False, confidence 0.90",
        'lenz /assess: claim 2/3 "Mostly right.": verdict Mostly True, confidence 0.60',
        'lenz /assess: claim 3/3 "Short claim.": verdict Unverifiable, confidence 0.50',
    ]


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("True", "True"),
        (" mostly true ", "Mostly True"),
        ("FALSE", "False"),
        ("Mostly False", "Mostly False"),
        ("mixed", "Mixed"),
        ("Half True", "Mixed"),
        ("Unverifiable", "Unverifiable"),
        ("Bogus", "Unverifiable"),
        ("", "Unverifiable"),
    ],
)
def test_parse_assess_labels_each_claim(raw: str, label: str):
    """
    [Unit] lenz response: verifies the explicit label of a one-claim answer, unknown -> Unverifiable.

    Scenario:
        Given an /assess body with one claim and a raw verdict label
        When _parse_assess reads it
        Then the result's label and display are the DISPLAY_LABELS entry and claims holds one
        ClaimVerdict with the echoed claim, that label and the confidence.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (explicit labels)
        - Fixtures/params: raw, label
        - Scope: lenz._parse_assess

    On failure, first check:
        - DISPLAY_LABELS and the ClaimVerdict construction in _parse_assess
    """
    lenz = _lenz()
    body = json.dumps({"claims": [{"claim": "It is so.", "verdict": raw, "confidence": 0.7}]}).encode()

    result = lenz._parse_assess(body, "lenz")

    assert (result.label, result.display) == (label, label)
    assert result.claims == (lenz.ClaimVerdict("It is so.", label, 0.7),)


@pytest.mark.parametrize(
    ("verdicts", "label", "verdict"),
    [
        (["True", "Mostly True"], "Mostly True", "true"),
        (["Mostly True", "Mostly False", "True"], "Mostly False", "false"),
        (["Mostly False", "False"], "False", "false"),
        (["True", "Half True", "Bogus"], "Mixed", "mixed"),
        (["True", "Bogus"], "Unverifiable", "unverifiable"),
    ],
)
def test_parse_assess_takes_the_most_severe_label(verdicts: list[str], label: str, verdict: str):
    """
    [Unit] lenz response: verifies a split fact's label is the most severe label of its claims.

    Scenario:
        Given an /assess body with several claims rated with different labels
        When _parse_assess reads it
        Then label is the first of VERDICT_LABELS order among them, consistent with the verdict,
        and claims keeps every row in response order with its own label.

    Boundaries:
        - Focus: owner ruling 2026-11-27 (most severe label of a combined fact)
        - Fixtures/params: verdicts, label, verdict
        - Scope: lenz._parse_assess

    On failure, first check:
        - worst_label in _parse_assess and protocol.VERDICT_LABELS order
    """
    rows = [{"claim": f"Claim {i}.", "verdict": raw, "confidence": 0.8} for i, raw in enumerate(verdicts)]

    result = _lenz()._parse_assess(json.dumps({"claims": rows}).encode(), "lenz")

    assert (result.label, result.verdict) == (label, verdict)
    assert [(part.claim, part.label) for part in result.claims] == [
        (f"Claim {i}.", _lenz().DISPLAY_LABELS.get(raw.strip().casefold(), "Unverifiable"))
        for i, raw in enumerate(verdicts)
    ]


def test_parse_assess_caps_kept_claims_but_labels_from_every_row():
    """
    [Unit] lenz response: verifies claims keeps MAX_RESULT_CLAIMS rows and the label still sees every row.

    Scenario:
        Given an /assess body with MAX_RESULT_CLAIMS true rows, then one False row, and a claim
        echo longer than MAX_RESULT_CLAIM_CHARS in the first row
        When _parse_assess reads it
        Then claims holds the first MAX_RESULT_CLAIMS rows (the long echo cut to the bound) and the
        label and verdict are False, taken from the dropped last row.

    Boundaries:
        - Focus: regression: the label was computed over the kept rows only and could disagree
          with the verdict
        - Fixtures/params: none
        - Scope: lenz._parse_assess

    On failure, first check:
        - The labels list and the MAX_RESULT_CLAIMS cap in _parse_assess
    """
    lenz = _lenz()
    cap = lenz.MAX_RESULT_CLAIMS
    rows = [{"claim": "y" * (lenz.MAX_RESULT_CLAIM_CHARS + 5), "verdict": "True", "confidence": 0.9}]
    rows += [{"claim": "ok", "verdict": "True", "confidence": 0.9}] * (cap - 1)
    rows.append({"claim": "bad", "verdict": "False", "confidence": 0.9})

    result = lenz._parse_assess(json.dumps({"claims": rows}).encode(), "lenz")

    assert len(result.claims) == cap
    assert result.claims[0].claim == "y" * lenz.MAX_RESULT_CLAIM_CHARS
    assert all(part.label == "True" for part in result.claims)
    assert (result.verdict, result.label) == ("false", "False")


def test_parse_assess_claim_without_echo_keeps_an_empty_claim():
    """
    [Unit] lenz response: verifies a row without a string claim echo is kept with an empty claim.

    Scenario:
        Given an /assess body whose row has no claim key and a second row whose claim is a number
        When _parse_assess reads it
        Then both rows are kept in claims with claim "" and their labels.

    Boundaries:
        - Focus: tolerant echo handling (the echo is optional)
        - Fixtures/params: none
        - Scope: lenz._parse_assess

    On failure, first check:
        - The isinstance(claim_text, str) fallback in _parse_assess
    """
    rows = [{"verdict": "True", "confidence": 0.9}, {"claim": 5, "verdict": "Mixed", "confidence": 0.4}]

    result = _lenz()._parse_assess(json.dumps({"claims": rows}).encode(), "lenz")

    assert [(part.claim, part.label) for part in result.claims] == [("", "True"), ("", "Mixed")]
    assert result.label == "Mixed"
