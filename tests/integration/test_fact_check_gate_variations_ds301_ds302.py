"""DS302 gate combinations next to DS301, through scan() and the CLI (Milestone 0010 Story 04.0 Task 02 step 4).

Loads three asset cases: ``deep_confirm_off_skips_everything_including_ds302`` (gate 1 closed),
``gate_off_no_flag`` (gate 1 open, no egress request) and ``gate_off_no_key`` (egress requested,
no key). For every combination a recording fake backend is registered, so a closed gate is proven
by an empty ``calls`` list and zero constructions, not only by an absent finding. The deep-wide
``pending`` text of an unconfirmed deep scan is pinned literally as it is on master.

No network is reached and the only key value is the threat model 0010 M12 sentinel. Skipped when
``mining.nlp.deep_ready()`` is false.
"""

import dataclasses
import json
import logging
from collections.abc import Callable

import pytest

from docsentinel import cli, extract_facts, scan
from docsentinel.mining import nlp
from tests.asset_helpers import AssetCase
from tests.fact_check_fakes import (
    FAKE_KEY_ENV,
    FakeBackendBase,
    fact_check_env,
    fake_deep_config,
    make_case_backend,
    register_fake_backend,
)

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The deep-wide pending entry of an unconfirmed deep scan, byte-identical to master.
DEEP_CONFIRM_PENDING = (
    "deep profile requires explicit opt-in: set deep_confirm = true, pass --i-understand-deep-is-heuristic, "
    "or set DOCSENTINEL_DEEP_CONFIRM=1 (deep checks are heuristic and may report false positives)"
)

#: The notice of an unconfirmed deep scan, byte-identical to master.
DEEP_CONFIRM_NOTICE = "Deep profile detection skipped until explicit opt-in is provided."

#: The gate reason when egress was not requested.
REQUEST_REASON = "pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)"

#: The default backend's key variable (plan contract C3).
LENZ_KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"

#: The notice when only DS301 evaluated.
DS301_ONLY_NOTICE = "1 deep rule(s) evaluated (heuristic, advisory-only)."


def _ds302_warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the WARNING messages that mention DS302.

    :param caplog: Pytest log capture.
    :returns: The messages, in order.
    """
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and "DS302" in r.getMessage()]


def _register(case: AssetCase, monkeypatch: pytest.MonkeyPatch, name: str = "fake") -> type[FakeBackendBase]:
    """Register the case fake for one test.

    :param case: The materialized asset case.
    :param monkeypatch: Pytest monkeypatch.
    :param name: The backend name.
    :returns: The fake class.
    """
    return register_fake_backend(monkeypatch, make_case_backend(case.root, name=name))


def _cli_scan(root: str, *extra: str) -> list[str]:
    """Build a deep CLI scan command line with a JSON report.

    :param root: The scan root.
    :param extra: Additional arguments.
    :returns: The argument list.
    """
    return ["scan", root, "--profile", "deep", "--format", "json", *extra]


def test_unconfirmed_deep_scan_skips_ds301_and_ds302_with_the_master_pending(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] gate 1 closed: verifies DS301 and DS302 are both skipped and pending is unchanged from master.

    Scenario:
        Given the deep_confirm_off corpus, both gate-2 prerequisites present and a recording fake
        When scan() runs with profile deep, deep_confirm false and use_external_api=True
        Then there are no findings, the fake was never constructed or called, pending is exactly the
            master deep opt-in entry (no DS302 entry), the notice is the master text, no DS302 WARNING is
            logged and the result equals the same scan with DS302 ignored

    Boundaries:
        - Focus: Task 02 step 4 first bullet; plan contract C1 gate 1 precedes gate 2
        - Fixtures/params: asset ds302/deep_confirm_off_skips_everything_including_ds302
        - Scope: engine.scan

    On failure, first check:
        - Whether the engine resolves gate 2 before checking deep_confirm
    """
    case = asset_case("ds302", "deep_confirm_off_skips_everything_including_ds302")
    backend = _register(case, monkeypatch)
    fact_check_env(monkeypatch, flag=True, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    config = fake_deep_config(deep_confirm=False)

    result = scan(case.root, config=config, use_external_api=True)
    ignored = scan(case.root, config=dataclasses.replace(config, ignore=("DS302",)), use_external_api=True)

    assert [d.path for d in result.documents] == ["quarry.md"]
    assert result.findings == ()
    assert result.pending == (DEEP_CONFIRM_PENDING,)
    assert result.notice == DEEP_CONFIRM_NOTICE
    assert result.rules_evaluated == 0
    assert (backend.calls, backend.constructed) == ([], 0)
    assert _ds302_warnings(caplog) == []
    assert dataclasses.replace(result, enabled_rules=()) == dataclasses.replace(ignored, enabled_rules=())


def test_cli_unconfirmed_deep_scan_exits_zero_and_sends_nothing(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] gate 1 closed via the CLI: verifies --use-external-api alone never opens DS302.

    Scenario:
        Given the deep_confirm_off corpus, the sentinel lenz key and a fake registered as lenz
        When "docsentinel scan ROOT --profile deep --use-external-api --format json" runs without the
            deep confirmation
        Then the exit code is 0, the report has no problem, pending is exactly the master entry and the
            fake was never constructed

    Boundaries:
        - Focus: Task 02 step 4 CLI form of the first bullet
        - Fixtures/params: asset ds302/deep_confirm_off_skips_everything_including_ds302
        - Scope: cli.main scan

    On failure, first check:
        - The deep_confirm resolution in cli.py
    """
    case = asset_case("ds302", "deep_confirm_off_skips_everything_including_ds302")
    backend = _register(case, monkeypatch, name="lenz")
    fact_check_env(monkeypatch, flag=False, key=True, key_env=LENZ_KEY_ENV)

    code = cli.main(_cli_scan(str(case.root), "--use-external-api"))

    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [p for doc in report["documents"] for p in doc["problems"]] == []
    assert report["pending"] == [DEEP_CONFIRM_PENDING]
    assert backend.constructed == 0


def test_confirmed_without_request_runs_ds301_and_skips_ds302(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] gate 2 not requested: verifies DS301 runs as alone, DS302 skips once and is not counted.

    Scenario:
        Given the gate_off_no_flag corpus, the sentinel key set but no egress request
        When a confirmed deep scan runs with use_external_api=False, and again with select = ["DS301"]
        Then the findings equal the DS301-only scan, pending holds exactly the one request reason, one
            DS302 WARNING is logged, the notice equals the DS301-only notice (owner ruling Q1) and the fake
            was never constructed

    Boundaries:
        - Focus: Task 02 step 4 second bullet; owner ruling Q1
        - Fixtures/params: asset ds302/gate_off_no_flag
        - Scope: engine.scan

    On failure, first check:
        - The closed-gate subtraction from rules_evaluated in engine.scan
    """
    case = asset_case("ds302", "gate_off_no_flag")
    backend = _register(case, monkeypatch)
    fact_check_env(monkeypatch, flag=False, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    config = fake_deep_config()

    result = scan(case.root, config=config)
    ds301_only = scan(case.root, config=dataclasses.replace(config, select=("DS301",)))

    assert result.enabled_rules == ("DS301", "DS302")
    assert result.findings == ds301_only.findings
    assert result.pending == (f"DS302 skipped: {REQUEST_REASON}",)
    assert _ds302_warnings(caplog) == [f"DS302 skipped: {REQUEST_REASON}"]
    assert result.notice == ds301_only.notice == DS301_ONLY_NOTICE
    assert result.rules_evaluated == 1
    assert (backend.calls, backend.constructed) == ([], 0)


def test_requested_without_key_skips_ds302_naming_only_the_key(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] gate 2 without key: verifies the skip reason lists only the missing key variable.

    Scenario:
        Given the gate_off_no_key corpus, no key variable and a recording fake
        When a confirmed deep scan runs with use_external_api=True
        Then pending and the one DS302 WARNING are exactly "DS302 skipped: set DOCSENTINEL_FACTCHECK_FAKE_API_KEY",
            no DS302 finding exists, DS302 is not counted and the fake was never constructed

    Boundaries:
        - Focus: Task 02 step 4 third bullet
        - Fixtures/params: asset ds302/gate_off_no_key
        - Scope: engine.scan

    On failure, first check:
        - ExternalApiGate.reasons
    """
    case = asset_case("ds302", "gate_off_no_key")
    backend = _register(case, monkeypatch)
    fact_check_env(monkeypatch, flag=False, key=False)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(case.root, config=fake_deep_config(), use_external_api=True)

    expected = f"DS302 skipped: set {FAKE_KEY_ENV}"
    assert [d.path for d in result.documents] == ["bridge.md"]
    assert [f for f in result.findings if f.rule == "DS302"] == []
    assert result.pending == (expected,)
    assert _ds302_warnings(caplog) == [expected]
    assert result.rules_evaluated == 1
    assert (backend.calls, backend.constructed) == ([], 0)


def test_cli_requested_without_key_reports_the_key_reason(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] gate 2 without key via the CLI: verifies --use-external-api with no key exits 0 and names the key.

    Scenario:
        Given the gate_off_no_key corpus, no lenz key and a fake registered as lenz
        When "docsentinel scan ROOT --profile deep --i-understand-deep-is-heuristic --use-external-api" runs
        Then the exit code is 0, pending holds exactly "DS302 skipped: set DOCSENTINEL_FACTCHECK_LENZ_API_KEY"
            and no DS302 problem is reported

    Boundaries:
        - Focus: Task 02 step 4 CLI form of the third bullet
        - Fixtures/params: asset ds302/gate_off_no_key
        - Scope: cli.main scan

    On failure, first check:
        - The pending computation in engine.scan
    """
    case = asset_case("ds302", "gate_off_no_key")
    backend = _register(case, monkeypatch, name="lenz")
    fact_check_env(monkeypatch, flag=False, key=False, key_env=LENZ_KEY_ENV)

    code = cli.main(_cli_scan(str(case.root), "--i-understand-deep-is-heuristic", "--use-external-api"))

    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert report["pending"] == [f"DS302 skipped: set {LENZ_KEY_ENV}"]
    assert [p for doc in report["documents"] for p in doc["problems"] if p["rule"] == "DS302"] == []
    assert backend.constructed == 0


def test_env_consent_and_key_open_the_gate_through_scan(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch
):
    """
    [Integration] gate 2 via the environment: verifies DOCSENTINEL_USE_EXTERNAL_API=1 plus a key runs DS302.

    Scenario:
        Given the gate_off_no_key corpus, DOCSENTINEL_USE_EXTERNAL_API=1 and the sentinel key
        When a confirmed deep scan runs with use_external_api=False
        Then pending is empty, both rules are counted and the fake received exactly the extract_facts texts

    Boundaries:
        - Focus: Task 02 step 4 fourth bullet (env form)
        - Fixtures/params: asset ds302/gate_off_no_key
        - Scope: engine.scan

    On failure, first check:
        - external_api_requested in detectors/fact_check.py
    """
    case = asset_case("ds302", "gate_off_no_key")
    backend = _register(case, monkeypatch)
    fact_check_env(monkeypatch, flag=True, key=True)
    config = fake_deep_config()

    result = scan(case.root, config=config)

    assert result.pending == ()
    assert result.rules_evaluated == 2
    assert backend.calls == ["The Orvella bridge carries 31 tram lines across the Kesmar river."]
    assert backend.calls == [fact.text for fact in extract_facts(case.root, config=config).facts]
    assert (backend.constructed, backend.closed) == (1, 1)


@pytest.mark.parametrize("env_value", ["1", "true", "yes", " 1"])
def test_cli_env_consent_opens_only_for_exactly_one(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    env_value: str,
):
    """
    [Integration] gate 2 via the environment and the CLI: verifies only the exact value "1" grants consent.

    Scenario:
        Given the gate_off_no_key corpus, the sentinel lenz key and a fake registered as lenz
        When "docsentinel scan ROOT --profile deep --i-understand-deep-is-heuristic" runs with
            DOCSENTINEL_USE_EXTERNAL_API set to "1", "true", "yes" or " 1"
        Then "1" sends the claim with an empty pending; every other value sends nothing and pending holds
            the request reason; the exit code is 0 either way

    Boundaries:
        - Focus: Task 02 step 4 fourth bullet (CLI env form); plan contract C1 exact value
        - Fixtures/params: asset ds302/gate_off_no_key; four env values
        - Scope: cli.main scan

    On failure, first check:
        - external_api_requested comparing to exactly "1"
    """
    case = asset_case("ds302", "gate_off_no_key")
    backend = _register(case, monkeypatch, name="lenz")
    fact_check_env(monkeypatch, flag=False, key=True, key_env=LENZ_KEY_ENV)
    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", env_value)

    code = cli.main(_cli_scan(str(case.root), "--i-understand-deep-is-heuristic"))

    report = json.loads(capsys.readouterr().out)
    assert code == 0
    if env_value == "1":
        assert report["pending"] == []
        assert len(backend.calls) == 1
    else:
        assert report["pending"] == [f"DS302 skipped: {REQUEST_REASON}"]
        assert backend.calls == []


def test_ignored_ds302_logs_no_warning_and_adds_no_pending(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Integration] DS302 ignored: verifies ignore = ["DS302"] removes the gate warning, the pending entry and the send.

    Scenario:
        Given the gate_off_no_flag corpus, both gate-2 prerequisites present and a recording fake
        When a confirmed deep scan runs with ignore = ["DS302"], once with consent and once without
        Then neither run logs a DS302 WARNING, both have an empty pending, DS302 is not enabled and the
            fake was never constructed

    Boundaries:
        - Focus: Task 02 step 4 last bullet
        - Fixtures/params: asset ds302/gate_off_no_flag
        - Scope: engine.scan

    On failure, first check:
        - Whether the engine intersects EXTERNAL_API_RULES with the active codes
    """
    case = asset_case("ds302", "gate_off_no_flag")
    backend = _register(case, monkeypatch)
    fact_check_env(monkeypatch, flag=False, key=True)
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    config = fake_deep_config(ignore=("DS302",))

    with_consent = scan(case.root, config=config, use_external_api=True)
    without_consent = scan(case.root, config=config)

    for result in (with_consent, without_consent):
        assert result.enabled_rules == ("DS301",)
        assert result.pending == ()
        assert result.rules_evaluated == 1
    assert _ds302_warnings(caplog) == []
    assert (backend.calls, backend.constructed) == ([], 0)
