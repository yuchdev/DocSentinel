"""DS302 per-claim failures and the time budget, end to end (Milestone 0010 Story 04.0 Task 02 step 5).

Loads ``tests/assets/ds302/per_claim_network_error_skipped/`` (three one-sentence documents, each
yielding one claim) and runs a confirmed, gate-open deep scan selecting ``DS302``. The case's
``verdicts.json`` rates two claims ``false`` and lists the ``alpha.md`` claim under ``fail_on``.
Covers the scripted ``FactCheckError`` skip, a backend raising ``FactCheckError`` for an answer it
cannot map (the Lenz client itself rates any unlisted label ``unverifiable`` since the owner ruling of
2026-11-27, which replaces ruling Q4), the time budget with a patched clock (owner ruling Q3, no real sleep) and one
network failure through the real ``LenzFactCheckClient`` over an ``httpx.MockTransport`` (plan
contract C8).

The task names this file ``tests/mock/test_fact_check_per_claim_error_skipped.py``; it lives under
``tests/integration/`` with the ``_ds302`` suffix because it loads assets (CLAUDE.md test layout).
Claim text reaches the log only in the DS302 and Lenz trace lines of the owner ruling of 2026-11-27
(each claim's first ten words; every case claim is shorter, so it is quoted whole); the tests pin
those lines exactly. No network is reached: the session guard refuses a real transport, the Lenz client only ever sees a
``MockTransport`` and the key is the threat model 0010 M12 sentinel. Skipped when
``mining.nlp.deep_ready()`` is false.
"""

import functools
import json
import logging
from collections.abc import Callable
from types import ModuleType

import httpx
import pytest

from docsentinel import cli, scan
from docsentinel.detectors import fact_check
from docsentinel.fact_check.protocol import FactCheckError
from docsentinel.mining import nlp
from tests.asset_helpers import AssetCase
from tests.fact_check_fakes import (
    FAKE_KEY_ENV,
    FAKE_NAME,
    SENTINEL,
    fact_check_env,
    fake_deep_config,
    make_case_backend,
    register_fake_backend,
)

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The case's claims, in send order.
SEND_ORDER = [
    "The Thornbury depot produced 2,150 spare rails in 2021.",
    "The Corvane weather station logged 73 storms during 2025.",
    "The Iskra relay station logged 9 outages during March 2022.",
]

#: The claim ``verdicts.json`` lists under ``fail_on``.
FAILING = SEND_ORDER[1]

#: The asset case name.
CASE = "per_claim_network_error_skipped"


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return DocSentinel WARNING messages.

    :param caplog: Pytest log capture.
    :returns: The messages, in order.
    """
    return [r.getMessage() for r in caplog.records if r.name.startswith("docsentinel") and r.levelno == logging.WARNING]


def _claim_records(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return every captured message that contains a case claim, in order.

    :param caplog: Pytest log capture.
    :returns: The messages.
    """
    return [r.getMessage() for r in caplog.records if any(claim in r.getMessage() for claim in SEND_ORDER)]


#: The DS302 trace line of each selected claim, in send order (owner ruling 2026-11-27).
CLAIM_TRACE = [
    f'DS302: claim 1/3 "{SEND_ORDER[0]}" in gamma.md',
    f'DS302: claim 2/3 "{SEND_ORDER[1]}" in alpha.md',
    f'DS302: claim 3/3 "{SEND_ORDER[2]}" in beta.md',
]


def _fact_trace(number: int, path: str) -> str:
    """Return the DS302 trace line of a checked fact rated false at 0.87 and reported.

    :param number: The 1-based position of the fact in send order.
    :param path: The document of the fact.
    :returns: The expected message.
    """
    return (
        f'DS302: fact {number}/3 ({number}) "{SEND_ORDER[number - 1]}" in {path}: '
        "verdict False, confidence 0.87, reported"
    )


def _log_text(caplog: pytest.LogCaptureFixture) -> str:
    """Return every captured record, formatted, joined.

    :param caplog: Pytest log capture.
    :returns: The text.
    """
    return "\n".join(r.getMessage() for r in caplog.records)


def test_one_failing_claim_is_skipped_and_the_others_are_still_checked(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] DS302 per-claim failure: verifies a FactCheckError skips one claim and the scan completes.

    Scenario:
        Given the per_claim_network_error_skipped corpus and a fake that raises FactCheckError for the alpha.md claim
        When the gate-open scan runs
        Then all three claims were sent in order, the two others give findings, exactly one WARNING names
            alpha.md and the exception type only, the INFO counts line reports one failure, and claim text
            appears only in the exact DS302 claim and fact trace lines

    Boundaries:
        - Focus: Task 02 step 5; plan contract C8; threat model M5 as amended by the owner ruling of 2026-11-27
        - Fixtures/params: asset ds302/per_claim_network_error_skipped with its verdicts.json
        - Scope: engine.scan and _check_candidates

    On failure, first check:
        - The FactCheckError handler in _check_candidates
    """
    case = asset_case("ds302", CASE)
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    fact_check_env(monkeypatch, flag=False, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(case.root, config=fake_deep_config(select=("DS302",)), use_external_api=True)

    assert backend.calls == SEND_ORDER
    assert [(f.path, f.value) for f in result.findings] == [
        ("beta.md", f"False (confidence 0.87): {SEND_ORDER[2]}"),
        ("gamma.md", f"False (confidence 0.87): {SEND_ORDER[0]}"),
    ]
    assert _warnings(caplog) == ["DS302: fact-check failed for a claim in alpha.md (FactCheckError)"]
    assert (
        "DS302: sent 3 claim(s) from 3 document(s) to backend fake; 1 failed, 2 reported, 0 not sent (time budget)"
        in _log_text(caplog)
    )
    assert _claim_records(caplog) == [*CLAIM_TRACE, _fact_trace(1, "gamma.md"), _fact_trace(3, "beta.md")]
    assert (backend.constructed, backend.closed) == (1, 1)


def test_cli_with_a_failing_claim_exits_zero(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] DS302 per-claim failure via the CLI: verifies the advisory exit code 0 and two problems.

    Scenario:
        Given the per_claim_network_error_skipped corpus and the case fake registered as lenz
        When "docsentinel scan ROOT --profile deep --use-external-api
            --select DS302 --format json" runs with the sentinel lenz key
        Then the exit code is 0 and the report has DS302 problems on beta.md and gamma.md only

    Boundaries:
        - Focus: Task 02 step 5 exit code
        - Fixtures/params: asset ds302/per_claim_network_error_skipped
        - Scope: cli.main scan

    On failure, first check:
        - Whether a per-claim failure escapes into cli.main as exit 2
    """
    case = asset_case("ds302", CASE)
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root, name="lenz"))
    fact_check_env(monkeypatch, flag=False, key=True, key_env=backend.API_KEY_ENV_VAR)

    code = cli.main(
        [
            "scan",
            str(case.root),
            "--profile",
            "deep",
            "--use-external-api",
            "--select",
            "DS302",
            "--format",
            "json",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [(d["path"], p["rule"]) for d in report["documents"] for p in d["problems"]] == [
        ("beta.md", "DS302"),
        ("gamma.md", "DS302"),
    ]
    assert backend.calls == SEND_ORDER


def test_unrecognised_verdict_is_a_skip_never_a_mixed_finding(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] DS302 backend error: verifies a backend's unrecognised-verdict error skips that claim only.

    Scenario:
        Given the per_claim corpus with no fail_on and a fake that raises FactCheckError("... unrecognised
            verdict") for the gamma.md claim, as a backend does for a verdict outside the vocabulary
        When the gate-open scan runs
        Then gamma.md has no finding (and no finding anywhere is mixed), the other two claims give false
            findings and one WARNING names gamma.md

    Boundaries:
        - Focus: a backend-raised FactCheckError end to end (the Lenz client no longer raises for an
          unlisted label; owner ruling 2026-11-27)
        - Fixtures/params: asset ds302/per_claim_network_error_skipped; verdicts overridden in the test
        - Scope: engine.scan and _check_candidates

    On failure, first check:
        - Whether an unknown verdict is mapped to mixed anywhere
    """
    case = asset_case("ds302", CASE)
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    backend.fail_on = frozenset()
    backend.verdicts[FAILING] = ("false", 0.87)
    backend.verdicts[SEND_ORDER[0]] = FactCheckError("fake /assess returned an unrecognised verdict")
    fact_check_env(monkeypatch, flag=False, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(case.root, config=fake_deep_config(select=("DS302",)), use_external_api=True)

    assert backend.calls == SEND_ORDER
    assert [f.path for f in result.findings] == ["alpha.md", "beta.md"]
    assert not any(f.value.startswith("mixed") for f in result.findings)
    assert _warnings(caplog) == ["DS302: fact-check failed for a claim in gamma.md (FactCheckError)"]
    assert "unrecognised verdict" not in _log_text(caplog)


def test_time_budget_stops_after_the_first_claim(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] DS302 time budget: verifies a passed deadline stops sending with one counts-only WARNING.

    Scenario:
        Given the per_claim corpus, fact_check_time_budget_seconds = 1 and a patched clock that reads 0
            for the deadline and the first check, then 10
        When the gate-open scan runs
        Then exactly the first claim is in calls, the one budget WARNING is
            "DS302: time budget of 1 s exhausted; 2 of 3 claim(s) not checked" with no path or claim text,
            the first claim's finding is kept, the client is still closed, and claim text appears only in
            the three claim trace lines and the first fact's trace line

    Boundaries:
        - Focus: owner ruling Q3 end to end; no real sleep
        - Fixtures/params: asset ds302/per_claim_network_error_skipped; clock seam of _check_candidates
        - Scope: engine.scan and _check_candidates

    On failure, first check:
        - Where the deadline is taken and checked in _check_candidates
    """
    case = asset_case("ds302", CASE)
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    fact_check_env(monkeypatch, flag=False, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    readings = iter([0.0, 0.0])
    monkeypatch.setattr(
        fact_check,
        "_check_candidates",
        functools.partial(fact_check._check_candidates, clock=lambda: next(readings, 10.0)),
    )

    result = scan(
        case.root,
        config=fake_deep_config(select=("DS302",), fact_check_time_budget_seconds=1),
        use_external_api=True,
    )

    assert backend.calls == SEND_ORDER[:1]
    assert _warnings(caplog) == ["DS302: time budget of 1 s exhausted; 2 of 3 claim(s) not checked"]
    assert [(f.path, f.value) for f in result.findings] == [("gamma.md", f"False (confidence 0.87): {SEND_ORDER[0]}")]
    assert (backend.constructed, backend.closed) == (1, 1)
    assert _claim_records(caplog) == [*CLAIM_TRACE, _fact_trace(1, "gamma.md")]


def test_real_lenz_client_network_failure_skips_one_claim(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    lenz_module: ModuleType,
):
    """
    [Integration] DS302 network failure: verifies a transport error in the real Lenz client skips only that claim.

    Scenario:
        Given the per_claim corpus and a LenzFactCheckClient subclass named fake whose transport is an
            httpx.MockTransport answering "False" at 0.87, but raising httpx.ConnectError for the alpha.md claim
        When the gate-open scan runs
        Then three requests reached the mock transport with exactly the three claims, two false findings are
            reported, one WARNING names alpha.md, the key is never logged, and claim text appears only in
            the exact DS302 trace lines and one Lenz verdict line per answered claim

    Boundaries:
        - Focus: plan contract C8 through the real client's error mapping; never a real socket
        - Fixtures/params: asset ds302/per_claim_network_error_skipped; lenz_module; MockTransport
        - Scope: engine.scan, DS302 detect and LenzFactCheckClient.check_claim

    On failure, first check:
        - The httpx.HTTPError mapping to FactCheckError in fact_check/lenz.py
    """
    case = asset_case("ds302", CASE)
    sent: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        """Record the claim and answer it, or fail the connection for the alpha.md claim.

        :param request: The request the client sent.
        :returns: A streamed one-claim success response.
        :raises httpx.ConnectError: For the failing claim.
        """
        claim = json.loads(request.content)["claim"]
        sent.append(claim)
        if claim == FAILING:
            raise httpx.ConnectError("connection refused", request=request)
        body = {"claims": [{"claim": claim, "verdict": "False", "confidence": 0.87}], "error": None}
        return httpx.Response(200, stream=httpx.ByteStream(json.dumps(body).encode("utf-8")))

    class MockedLenz(lenz_module.LenzFactCheckClient):
        """The real Lenz client under the fake backend name, wired to a mock transport."""

        name = FAKE_NAME
        API_KEY_ENV_VAR = FAKE_KEY_ENV

        def __init__(self, api_key: str):
            """Build the real client with the mock transport.

            :param api_key: The key DS302 read from the environment.
            """
            super().__init__(api_key, transport=httpx.MockTransport(answer))

    register_fake_backend(monkeypatch, MockedLenz)
    fact_check_env(monkeypatch, flag=False, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(case.root, config=fake_deep_config(select=("DS302",)), use_external_api=True)

    assert sent == SEND_ORDER
    assert [(f.path, f.value) for f in result.findings] == [
        ("beta.md", f"False (confidence 0.87): {SEND_ORDER[2]}"),
        ("gamma.md", f"False (confidence 0.87): {SEND_ORDER[0]}"),
    ]
    assert all(f.message.endswith("rated false by fake - review to confirm") for f in result.findings)
    assert _warnings(caplog) == ["DS302: fact-check failed for a claim in alpha.md (FactCheckError)"]
    text = _log_text(caplog)
    assert SENTINEL not in text
    assert _claim_records(caplog) == [
        *CLAIM_TRACE,
        f'lenz /assess: claim 1/1 "{SEND_ORDER[0]}": verdict False, confidence 0.87',
        _fact_trace(1, "gamma.md"),
        f'lenz /assess: claim 1/1 "{SEND_ORDER[2]}": verdict False, confidence 0.87',
        _fact_trace(3, "beta.md"),
    ]
