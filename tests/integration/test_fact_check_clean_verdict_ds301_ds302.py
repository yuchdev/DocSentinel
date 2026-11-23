"""DS302 with both gates open and a clean verdict, next to DS301 (Milestone 0010 Story 04.0 Task 02 step 2).

Loads ``tests/assets/ds302/both_gates_on_clean_verdict/`` (three one-sentence documents; two of them
state different crossing counts for one subject, so DS301 has a contradiction to report) and runs a
confirmed deep scan with gate 2 open against a fake backend scripted by the case's
``verdicts.json`` to rate every sent claim ``true``. DS302 must report nothing and must not disturb
DS301, whose findings equal a ``select = ["DS301"]`` scan exactly.

No network is reached: the fake is registered in ``FACT_CHECK_BACKENDS`` for one test only and the
key is the threat model 0010 M12 sentinel. Skipped when ``mining.nlp.deep_ready()`` is false.
"""

import dataclasses
import json
from collections.abc import Callable

import pytest

from docsentinel import cli, extract_facts, scan
from docsentinel.mining import nlp
from tests.asset_helpers import AssetCase
from tests.fact_check_fakes import (
    SENTINEL,
    fact_check_env,
    fake_deep_config,
    make_case_backend,
    register_fake_backend,
)

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The three claims of the case, in send order.
CLEAN_CLAIMS = [
    "The Brackwell mill produced 4,800 sacks of barley in 2024.",
    "The Dunmere ferry company logged 260 crossings during 2027.",
    "The Dunmere ferry company logged 310 crossings during 2027.",
]


def test_clean_verdict_gives_no_ds302_finding_and_leaves_ds301_unchanged(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch
):
    """
    [Integration] DS302 clean verdict: verifies true verdicts give no DS302 finding and DS301 runs as alone.

    Scenario:
        Given the both_gates_on_clean_verdict corpus, the fake backend rating every claim true and the
            sentinel key
        When a confirmed deep scan runs with use_external_api=True, and again with select = ["DS301"]
        Then every selected claim was sent once, in extract_facts order; no finding is DS302; the DS301
            findings equal the DS301-only scan; pending is empty; both rules are counted; the client was
            constructed and closed once and the key appears nowhere in the result

    Boundaries:
        - Focus: Task 02 step 2; ADR 0007 Contract 9 (only false/mixed report)
        - Fixtures/params: asset ds302/both_gates_on_clean_verdict; real spaCy pipeline
        - Scope: engine.scan with DS301 and DS302 active

    On failure, first check:
        - REPORTABLE_VERDICTS in detectors/fact_check.py
    """
    case = asset_case("ds302", "both_gates_on_clean_verdict")
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    fact_check_env(monkeypatch, flag=False, key=True)
    config = fake_deep_config()

    both = scan(case.root, config=config, use_external_api=True)
    ds301_only = scan(case.root, config=dataclasses.replace(config, select=("DS301",)))

    assert backend.calls == CLEAN_CLAIMS
    assert backend.calls == [fact.text for fact in extract_facts(case.root, config=config).facts]
    assert both.enabled_rules == ("DS301", "DS302")
    assert [f for f in both.findings if f.rule == "DS302"] == []
    assert [f.rule for f in ds301_only.findings] == ["DS301"]
    assert both.findings == ds301_only.findings
    assert [f.path for f in both.findings] == ["ledger.md"]
    assert both.pending == ()
    assert both.rules_evaluated == 2
    assert (backend.constructed, backend.closed) == (1, 1)
    assert SENTINEL not in repr(both)


def test_cli_clean_verdict_exits_zero_with_only_the_ds301_problem(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] DS302 clean verdict via the CLI: verifies exit 0 and a report holding DS301 only.

    Scenario:
        Given the both_gates_on_clean_verdict corpus and the case fake registered as the default lenz backend
        When "docsentinel scan ROOT --profile deep --i-understand-deep-is-heuristic --use-external-api
            --format json" runs with the sentinel lenz key
        Then the exit code is 0, the report has exactly one problem (DS301 on ledger.md) and the fake
            received the three claims

    Boundaries:
        - Focus: Task 02 steps 2 and 4 (CLI form); the CLI config accepts only shipped backend names
        - Fixtures/params: asset ds302/both_gates_on_clean_verdict; fake named lenz
        - Scope: cli.main scan

    On failure, first check:
        - The --use-external-api forwarding in cli.py
    """
    case = asset_case("ds302", "both_gates_on_clean_verdict")
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root, name="lenz"))
    fact_check_env(monkeypatch, flag=False, key=True, key_env=backend.API_KEY_ENV_VAR)

    code = cli.main(
        [
            "scan",
            str(case.root),
            "--profile",
            "deep",
            "--i-understand-deep-is-heuristic",
            "--use-external-api",
            "--format",
            "json",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    problems = [(doc["path"], p["rule"]) for doc in report["documents"] for p in doc["problems"]]
    assert code == 0
    assert problems == [("ledger.md", "DS301")]
    assert backend.calls == CLEAN_CLAIMS
