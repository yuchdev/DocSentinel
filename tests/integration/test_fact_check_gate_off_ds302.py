"""DS302 with the consent gate closed, over a real two-document corpus (Milestone 0010 Story 01.0).

Loads ``tests/assets/ds302/gate_off_no_flag/`` (two short documents, each with one sentence holding
a number and a named entity) and checks that a confirmed deep scan without both prerequisites of
gate 2 sends nothing, reports zero ``DS302`` findings, logs one WARNING and adds one ``pending``
entry whose text names only what is missing. It also pins the ``rules`` and ``doctor`` lines
(threat model 0010 M6), including the configuration-error form of the ``doctor`` gate line.

No backend is registered, no network is reached and the only key value is the M12 sentinel. The
scan cases need the real deep pipeline (DS301 runs too), so they are skipped when
``mining.nlp.deep_ready()`` is false, like the DS301 integration tests (Python 3.13 has no textacy).
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli, scan
from docsentinel.config import Config
from docsentinel.mining import nlp
from tests.asset_helpers import AssetCase

#: The fake key value (threat model 0010 M12).
SENTINEL = "sentinel-not-a-real-key-0010"

#: The default backend's key variable (plan contract C3).
LENZ_KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"

#: The gate reason when egress was not requested.
REQUEST_REASON = "pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1)"

#: Exact WARNING / pending text and ``doctor`` line per gate state (threat model M6).
GATE_STATES = {
    "neither": (
        f"DS302 skipped: {REQUEST_REASON}; set {LENZ_KEY_ENV} or LENZ_API_KEY",
        f"fact-check gate: off ({REQUEST_REASON}; set {LENZ_KEY_ENV} or LENZ_API_KEY)",
    ),
    "key_only": (f"DS302 skipped: {REQUEST_REASON}", f"fact-check gate: off ({REQUEST_REASON})"),
    "flag_only": (f"DS302 skipped: set {LENZ_KEY_ENV} or LENZ_API_KEY", f"fact-check gate: off (set {LENZ_KEY_ENV} or LENZ_API_KEY)"),
}

#: The ``rules`` listing line of DS302 (Task 03).
RULES_LINE = (
    "  DS302: External fact-check disagreement "
    "[requires --use-external-api and a backend API key; see docsentinel doctor]"
)

#: Skip marker for the scan cases that run the real deep pipeline.
needs_deep = pytest.mark.skipif(
    not nlp.deep_ready(), reason="deep dependencies and model not installed (DS301 runs in a confirmed deep scan)"
)


def _set_state(monkeypatch: pytest.MonkeyPatch, state: str) -> bool:
    """Set the key for ``key_only`` and return the flag for ``flag_only``.

    :param monkeypatch: Pytest monkeypatch.
    :param state: ``neither``, ``key_only`` or ``flag_only``.
    :returns: The ``use_external_api`` value to pass.
    """
    if state == "key_only":
        monkeypatch.setenv(LENZ_KEY_ENV, SENTINEL)
    return state == "flag_only"


def _gate_lines(output: str) -> list[str]:
    """Return the ``fact-check gate:`` lines of ``doctor`` output.

    :param output: Captured stdout.
    :returns: The matching lines.
    """
    return [line for line in output.splitlines() if line.startswith("fact-check gate:")]


@needs_deep
@pytest.mark.parametrize("state", sorted(GATE_STATES))
def test_closed_gate_scan_reports_nothing_and_names_what_is_missing(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    state: str,
):
    """
    [Integration] DS302 gate off: verifies a closed gate gives no finding, one WARNING and one pending entry.

    Scenario:
        Given the gate_off_no_flag corpus and a confirmed deep configuration
        When scan() runs with neither prerequisite, with only the key, or with only the flag
        Then there is no DS302 finding, exactly one DS302 WARNING and one pending entry, both equal to the
        state's exact text, DS302 is not counted, and the sentinel key appears nowhere.

    Boundaries:
        - Focus: ADR 0007 Contracts 3 and 6, threat model M6
        - Fixtures/params: asset ds302/gate_off_no_flag; three gate states
        - Scope: engine.scan with the real deep pipeline

    On failure, first check:
        - ExternalApiGate.reasons and the pending computation in engine.scan
    """
    case = asset_case("ds302", "gate_off_no_flag")
    flag = _set_state(monkeypatch, state)
    expected_warning, _ = GATE_STATES[state]
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = scan(case.root, config=Config(profile="deep"), use_external_api=flag)

    assert [d.path for d in result.documents] == ["harbor.md", "library.md"]
    assert [f for f in result.findings if f.rule == "DS302"] == []
    assert result.pending == (expected_warning,)
    assert result.rules_evaluated == 1
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and "DS302" in r.getMessage()]
    assert warnings == [expected_warning]
    assert not [r for r in caplog.records if r.getMessage().startswith("DS302: sent")]
    assert SENTINEL not in "\n".join(r.getMessage() for r in caplog.records)
    assert SENTINEL not in repr(result)


@needs_deep
def test_cli_deep_scan_without_consent_exits_zero(
    asset_case: Callable[[str, str], AssetCase], capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] DS302 gate off: verifies the confirmed deep CLI scan exits 0 without consent.

    Scenario:
        Given the gate_off_no_flag corpus
        When "docsentinel scan ROOT --profile deep --format json" runs
        Then the exit code is 0 and the report holds no DS302 problem.

    Boundaries:
        - Focus: advisory-only deep exit codes with DS302 skipped
        - Fixtures/params: asset ds302/gate_off_no_flag
        - Scope: cli.main end to end

    On failure, first check:
        - Whether a closed gate raises instead of returning ()
    """
    case = asset_case("ds302", "gate_off_no_flag")

    code = cli.main(
        ["scan", str(case.root), "--profile", "deep", "--format", "json"]
    )

    report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert [p for doc in report["documents"] for p in doc["problems"] if p["rule"] == "DS302"] == []
    assert len(report["documents"]) == 2


def test_rules_lists_ds302_with_the_consent_suffix(capsys: pytest.CaptureFixture[str]):
    """
    [Integration] DS302 rules listing: verifies the exact rules line.

    Scenario:
        Given the registered rules
        When "docsentinel rules" runs
        Then DS302 is listed once under deep with the Task 03 consent suffix.

    Boundaries:
        - Focus: Task 03 rules text
        - Fixtures/params: none
        - Scope: cli.main rules

    On failure, first check:
        - EXTERNAL_API_SUFFIX in cli.py
    """
    assert cli.main(["rules"]) == 0

    lines = [line for line in capsys.readouterr().out.splitlines() if "DS302" in line]
    assert lines == [RULES_LINE]


@pytest.mark.parametrize("state", sorted(GATE_STATES))
def test_doctor_gate_line_names_only_what_is_missing(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    state: str,
):
    """
    [Integration] DS302 doctor: verifies the exact gate line for neither, key only and flag only.

    Scenario:
        Given the gate_off_no_flag corpus as the current directory
        When "docsentinel doctor" runs with neither prerequisite, only the key, or DOCSENTINEL_USE_EXTERNAL_API=1 only
        Then exactly one gate line is printed and it equals the state's text, without the key value.

    Boundaries:
        - Focus: threat model M6; doctor has no --use-external-api flag, so the env form stands in for it
        - Fixtures/params: asset ds302/gate_off_no_flag; three gate states
        - Scope: cli.main doctor

    On failure, first check:
        - _doctor_fact_check_gate_line in cli.py
    """
    case = asset_case("ds302", "gate_off_no_flag")
    monkeypatch.chdir(case.root)
    if _set_state(monkeypatch, state):
        monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")
    _, expected_line = GATE_STATES[state]

    assert cli.main(["doctor"]) == 0

    out = capsys.readouterr().out
    assert _gate_lines(out) == [expected_line]
    assert SENTINEL not in out


@pytest.mark.parametrize(
    ("body", "offending"),
    [
        ('fact_check_backend = "openai"\n', "fact_check_backend"),
        ("use_external_api = true\n", "use_external_api"),
        ("fact_check_time_budget_seconds = 0\n", "fact_check_time_budget_seconds"),
    ],
)
def test_doctor_gate_line_in_the_config_error_state(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    body: str,
    offending: str,
):
    """
    [Integration] DS302 doctor: verifies a broken configuration gives the fixed unknown gate line.

    Scenario:
        Given the gate_off_no_flag corpus with a docsentinel.toml holding an invalid or unknown key
        When "docsentinel doctor" runs with the key and the env consent set
        Then the gate line is exactly "fact-check gate: unknown (configuration error)" and no gate line
        echoes the offending key name or the key value.

    Boundaries:
        - Focus: threat model M6 (FC-6)
        - Fixtures/params: three broken configurations written inline
        - Scope: cli.main doctor

    On failure, first check:
        - FACT_CHECK_GATE_UNKNOWN and the doctor config-load error path
    """
    case = asset_case("ds302", "gate_off_no_flag")
    (case.root / "docsentinel.toml").write_text(body, encoding="utf-8")
    monkeypatch.chdir(case.root)
    monkeypatch.setenv(LENZ_KEY_ENV, SENTINEL)
    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")

    cli.main(["doctor"])

    captured = capsys.readouterr()
    lines = _gate_lines(captured.out)
    assert lines == ["fact-check gate: unknown (configuration error)"]
    assert all(offending not in line for line in lines)
    assert SENTINEL not in captured.out + captured.err


def test_asset_documents_carry_a_number_and_a_named_entity(asset_case: Callable[[str, str], AssetCase]):
    """
    [Integration] DS302 asset: verifies the gate_off_no_flag case is claim-shaped input.

    Scenario:
        Given the gate_off_no_flag corpus
        When each document is read
        Then each holds one sentence with a digit and a capitalised proper name, so a closed gate is what
        stops DS302, not an empty corpus.

    Boundaries:
        - Focus: the asset contract of Task 06 step 3
        - Fixtures/params: asset ds302/gate_off_no_flag
        - Scope: file reads only

    On failure, first check:
        - Whether the asset was edited
    """
    case = asset_case("ds302", "gate_off_no_flag")

    assert [d.path for d in case.documents()] == ["harbor.md", "library.md"]
    for name, entity in (("harbor.md", "Rotterdam"), ("library.md", "Tampere")):
        text = case.read_text(name)
        assert entity in text
        assert any(ch.isdigit() for ch in text)
        assert isinstance(case.path(name), Path)
