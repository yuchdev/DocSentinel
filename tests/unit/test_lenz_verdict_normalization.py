"""Verdict normalisation of the Lenz client (Story 03.0 Task 04 step 3, egress E9, owner ruling Q4).

Only ``true`` and ``false`` (stripped, case-insensitive) are recognised verdicts; every other raw
string, including the empty string and ``Mixed``, maps to ``None`` and, through ``check_claim``,
raises a fixed ``FactCheckError`` at any confidence (there is no confidence band). The raw verdict
strings are typed by hand here; nothing is imported from ``examples/``. The ``check_claim`` cases
answer through an in-memory ``httpx.MockTransport``; no network is reached.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Optional

import httpx
import pytest

from docsentinel.fact_check.protocol import FactCheckError
from tests.fact_check_fakes import SENTINEL

pytestmark = pytest.mark.usefixtures("lenz_module")

#: The fixed unrecognised-verdict message, pinned.
VERDICT_MESSAGE = "lenz /assess returned an unrecognised verdict"


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
        ("", None),
        ("   ", None),
        ("Mixed", None),
        ("mixed", None),
        ("Unverifiable", None),
        ("Mostly True", None),
        ("truthy", None),
        ("t", None),
        ("yes", None),
        ("1", None),
        ("True.", None),
        ("Truе", None),  # Cyrillic small ie, a confusable
        ("Ｔrue", None),  # full-width T
    ],
)
def test_normalize_verdict_known_and_unknown(raw: str, expected: Optional[str]):
    """
    [Unit] lenz verdicts: verifies only true and false map, everything else is None.

    Scenario:
        Given raw verdict strings typed by hand
        When _normalize_verdict maps them
        Then True/False in any case and surrounding whitespace map to true/false; the empty
        string, Mixed, unknown words and confusables return None.

    Boundaries:
        - Focus: E9, decision U7, owner ruling Q4 (no confidence band, no guessed verdict)
        - Fixtures/params: raw, expected
        - Scope: lenz._normalize_verdict

    On failure, first check:
        - The strip and casefold in _normalize_verdict

    :param raw: The raw verdict.
    :param expected: The mapped verdict or None.
    """
    assert _lenz()._normalize_verdict(raw) == expected


@pytest.mark.parametrize("raw", ["", "Mixed", "UNKNOWN-VERDICT-MARKER-0010"])
@pytest.mark.parametrize("confidence", [0.0, 0.5, 1.0])
def test_unknown_verdict_raises_through_check_claim(raw: str, confidence: float):
    """
    [Unit] lenz verdicts: verifies an unknown verdict raises a fixed error at every confidence.

    Scenario:
        Given an in-memory transport answering a one-claim body with an unknown verdict
        When check_claim runs at confidence 0.0, 0.5 and 1.0
        Then FactCheckError carries the fixed message, which never contains the raw value.

    Boundaries:
        - Focus: E9, owner ruling Q4
        - Fixtures/params: raw, confidence
        - Scope: LenzFactCheckClient.check_claim with httpx.MockTransport

    On failure, first check:
        - The verdict-is-None branch of _parse_assess

    :param raw: The unknown verdict.
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
    with pytest.raises(FactCheckError) as info:
        client.check_claim("A claim.")
    client.close()
    assert str(info.value) == VERDICT_MESSAGE
    if raw:
        assert raw not in str(info.value).replace("unrecognised verdict", "")
    assert info.value.__context__ is None


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
