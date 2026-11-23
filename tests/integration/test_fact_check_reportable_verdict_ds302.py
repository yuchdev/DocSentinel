"""DS302 with both gates open and a reportable verdict (Milestone 0010 Story 04.0 Task 02 step 3).

Loads ``tests/assets/ds302/both_gates_on_false_verdict_reports/`` (three documents; one sentence is
longer than the 200-code-point message snippet) and ``both_gates_on_mixed_verdict_reports/`` (one
document) and runs a confirmed deep scan selecting ``DS302`` with gate 2 open against a fake backend
scripted by each case's ``verdicts.json`` (``false`` or ``mixed`` at confidence 0.87). It pins every
finding field of ADR 0007 Contract 9, the confidence floor boundary, fingerprint stability across
confidences (owner ruling Q2), generic baseline filtering (plan contract C6) and the advisory CLI
exit code with both the ``json`` and the ``text`` report.

No network is reached: the fake is registered for one test only and the key is the threat model
0010 M12 sentinel. Skipped when ``mining.nlp.deep_ready()`` is false.
"""

import dataclasses
import json
from collections.abc import Callable

import pytest

from docsentinel import cli, scan
from docsentinel.baseline import fingerprint, save_baseline
from docsentinel.config import Config, load_config
from docsentinel.mining import nlp
from docsentinel.models import ScanResult
from tests.asset_helpers import AssetCase
from tests.fact_check_fakes import (
    FakeBackendBase,
    fact_check_env,
    fake_deep_config,
    make_case_backend,
    register_fake_backend,
)

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The long claim of the false case; its message snippet is cut at 200 code points.
LONG_CLAIM = (
    "The Wendmoor basin authority recorded 4,410 barge passages during 2022 across the twelve western "
    "locks, the six eastern basins, the long Arlow cutting, the Pellmouth tidal gate, the narrow Quenby "
    "feeder channel and the old Tolvar brickworks wharf beside the river."
)

#: The claims of the false case keyed by document, as the scripted verdicts name them.
FALSE_CLAIMS = {
    "basin.md": LONG_CLAIM,
    "canal.md": "The Fenwick canal links 12 locks between Arlow and Pellmouth.",
    "tower.md": "The Ostrava signal tower recorded 87 lightning strikes during 2023.",
}

#: The one claim of the mixed case.
MIXED_CLAIM = "The Marlow orchard in Edzell produced 5,300 crates of pears in 2026."

#: Case name, verdict and the expected ``{path: claim}`` of each reportable case.
REPORTABLE_CASES = {
    "false": ("both_gates_on_false_verdict_reports", "false", FALSE_CLAIMS),
    "mixed": ("both_gates_on_mixed_verdict_reports", "mixed", {"orchard.md": MIXED_CLAIM}),
}


def _ds302_config(**overrides: object) -> Config:
    """Return a confirmed deep configuration selecting only DS302 with the fake backend.

    :param overrides: Extra ``Config`` fields.
    :returns: The configuration.
    """
    return fake_deep_config(select=("DS302",), **overrides)


def _open_scan(
    case: AssetCase, monkeypatch: pytest.MonkeyPatch, config: Config
) -> tuple[ScanResult, type[FakeBackendBase]]:
    """Register the case fake, set the sentinel key and run a gate-open scan.

    :param case: The materialized asset case.
    :param monkeypatch: Pytest monkeypatch.
    :param config: The configuration to scan with.
    :returns: The result and the fake class.
    """
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    fact_check_env(monkeypatch, flag=False, key=True)
    return scan(case.root, config=config, use_external_api=True), backend


@pytest.mark.parametrize("kind", sorted(REPORTABLE_CASES))
def test_reportable_verdict_gives_one_exact_finding_per_candidate(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, kind: str
):
    """
    [Integration] DS302 reportable verdict: verifies one finding per sent claim with every Contract 9 field.

    Scenario:
        Given the false or mixed corpus and a fake rating each claim with that verdict at confidence 0.87
        When a confirmed deep scan selecting DS302 runs with use_external_api=True
        Then there is one finding per sent claim, sorted by (path, message); each has rule DS302, the
            claim's document path, severity warning, type "unverified claim", no line, value
            "<verdict> (confidence 0.87): <the exact text sent>" and the message
            "external fact-check: '<first 200 code points>' rated <verdict> by fake - review to confirm"
            with no confidence in it

    Boundaries:
        - Focus: ADR 0007 Contract 9, owner ruling Q2, Task 02 step 3
        - Fixtures/params: assets ds302/both_gates_on_false_verdict_reports and _mixed_; real spaCy
        - Scope: engine.scan, DS302 detect and _finding

    On failure, first check:
        - _finding and the sort in _check_candidates
    """
    case_name, verdict, claims = REPORTABLE_CASES[kind]
    case = asset_case("ds302", case_name)

    result, backend = _open_scan(case, monkeypatch, _ds302_config())

    assert sorted(backend.calls) == sorted(claims.values())
    assert len(result.findings) == len(backend.calls)
    assert list(result.findings) == sorted(result.findings, key=lambda f: (f.path, f.message))
    for finding in result.findings:
        sent = claims[finding.path]
        assert (finding.rule, finding.severity, finding.type, finding.line) == (
            "DS302",
            "warning",
            "unverified claim",
            None,
        )
        assert finding.value == f"{verdict} (confidence 0.87): {sent}"
        assert finding.value.split(": ", 1)[1] in backend.calls
        assert finding.message == f"external fact-check: '{sent[:200]}' rated {verdict} by fake - review to confirm"
        assert "confidence" not in finding.message
    assert result.pending == ()
    assert result.rules_evaluated == 1


def test_long_claim_message_snippet_is_cut_at_200_code_points(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch
):
    """
    [Integration] DS302 finding: verifies the message carries a 200-code-point snippet but value the whole claim.

    Scenario:
        Given the false corpus, whose basin.md claim is longer than 200 code points
        When the gate-open scan runs
        Then the basin.md message quotes exactly the first 200 code points and the value ends with the full
            sent text

    Boundaries:
        - Focus: ADR 0007 Contract 9 snippet bound
        - Fixtures/params: asset ds302/both_gates_on_false_verdict_reports
        - Scope: _finding

    On failure, first check:
        - _SNIPPET_CHARS in detectors/fact_check.py
    """
    case = asset_case("ds302", "both_gates_on_false_verdict_reports")
    assert len(LONG_CLAIM) > 200

    result, _ = _open_scan(case, monkeypatch, _ds302_config())

    (basin,) = [f for f in result.findings if f.path == "basin.md"]
    quoted = basin.message.split("'")[1]
    assert quoted == LONG_CLAIM[:200]
    assert len(quoted) == 200
    assert basin.value == f"false (confidence 0.87): {LONG_CLAIM}"


@pytest.mark.parametrize(
    ("confidence", "reported"),
    [(0.86, False), (0.87, True), (0.95, True)],
    ids=["just_below_floor", "equal_to_floor", "above_floor"],
)
def test_confidence_floor_boundary(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch, confidence: float, reported: bool
):
    """
    [Integration] DS302 confidence floor: verifies the floor is inclusive and a lower confidence is silent.

    Scenario:
        Given the mixed corpus, fact_check_min_confidence = 0.87 and a fake rating the claim false
        When the gate-open scan runs with confidence 0.86, 0.87 or 0.95
        Then the claim is always sent, and a finding exists only at or above the floor

    Boundaries:
        - Focus: Task 02 step 3 floor cases
        - Fixtures/params: asset ds302/both_gates_on_mixed_verdict_reports; three confidences
        - Scope: _check_candidates

    On failure, first check:
        - The ">=" comparison against min_confidence in _check_candidates
    """
    case = asset_case("ds302", "both_gates_on_mixed_verdict_reports")
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    backend.verdicts[MIXED_CLAIM] = ("false", confidence)
    fact_check_env(monkeypatch, flag=False, key=True)

    result = scan(case.root, config=_ds302_config(fact_check_min_confidence=0.87), use_external_api=True)

    assert backend.calls == [MIXED_CLAIM]
    assert [f.value for f in result.findings] == (
        [f"false (confidence {confidence:.2f}): {MIXED_CLAIM}"] if reported else []
    )


def test_other_confidence_keeps_the_baseline_fingerprints(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch
):
    """
    [Integration] DS302 fingerprint: verifies a changed confidence with the same verdict keeps every fingerprint.

    Scenario:
        Given the false corpus scanned once at confidence 0.87
        When a second scan rates the same claims false at 0.61
        Then the values differ, but the fingerprints are the same set

    Boundaries:
        - Focus: owner ruling Q2 end to end
        - Fixtures/params: asset ds302/both_gates_on_false_verdict_reports
        - Scope: engine.scan and baseline.fingerprint

    On failure, first check:
        - Whether the message gained the confidence
    """
    case = asset_case("ds302", "both_gates_on_false_verdict_reports")
    first, _ = _open_scan(case, monkeypatch, _ds302_config())
    second_backend = register_fake_backend(monkeypatch, make_case_backend(case.root))
    for text in FALSE_CLAIMS.values():
        second_backend.verdicts[text] = ("false", 0.61)

    second = scan(case.root, config=_ds302_config(), use_external_api=True)

    assert len(first.findings) == len(second.findings) == 3
    assert {f.value for f in first.findings}.isdisjoint({f.value for f in second.findings})
    assert [fingerprint(f) for f in first.findings] == [fingerprint(f) for f in second.findings]


def test_generic_baseline_filters_ds302_findings(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
):
    """
    [Integration] DS302 baseline: verifies the generic baseline file suppresses recorded DS302 findings.

    Scenario:
        Given the false corpus and a baseline file recording two of its three DS302 findings
        When the gate-open scan runs with baseline set to that file
        Then only the unrecorded finding remains, and every claim was still sent

    Boundaries:
        - Focus: plan contract C6 (no deep-specific baseline; DS302 is filtered like any finding)
        - Fixtures/params: asset ds302/both_gates_on_false_verdict_reports; baseline outside the scan root
        - Scope: engine.scan baseline filter

    On failure, first check:
        - The baseline step of engine.scan
    """
    case = asset_case("ds302", "both_gates_on_false_verdict_reports")
    unfiltered, _ = _open_scan(case, monkeypatch, _ds302_config())
    baseline_path = tmp_path_factory.mktemp("baseline") / "deep-baseline.json"
    save_baseline(baseline_path, unfiltered.findings[:2])
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root))

    filtered = scan(case.root, config=_ds302_config(baseline=str(baseline_path)), use_external_api=True)

    assert len(backend.calls) == 3
    assert filtered.findings == unfiltered.findings[2:]


@pytest.mark.parametrize("report_format", ["json", "text"])
def test_cli_reports_the_finding_and_exits_zero(
    asset_case: Callable[[str, str], AssetCase],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    report_format: str,
):
    """
    [Integration] DS302 via the CLI: verifies a reportable verdict renders in json and text and exits 0.

    Scenario:
        Given the mixed corpus and the case fake registered as the default lenz backend
        When "docsentinel scan ROOT --profile deep --i-understand-deep-is-heuristic --use-external-api
            --select DS302 --format <json|text>" runs with the sentinel lenz key
        Then the exit code is 0 (advisory); json holds one DS302 problem on orchard.md with type
            "unverified claim", the value and outcome advisory; text names the document and a
            "warning DS302 unverified claim" line ending with the value

    Boundaries:
        - Focus: Task 02 step 3 (CLI exit and both renderings)
        - Fixtures/params: asset ds302/both_gates_on_mixed_verdict_reports; fake named lenz
        - Scope: cli.main scan and the json/text templates

    On failure, first check:
        - The deep advisory exit-code path in cli.py
    """
    case = asset_case("ds302", "both_gates_on_mixed_verdict_reports")
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root, name="lenz"))
    fact_check_env(monkeypatch, flag=False, key=True, key_env=backend.API_KEY_ENV_VAR)
    value = f"mixed (confidence 0.87): {MIXED_CLAIM}"

    code = cli.main(
        [
            "scan",
            str(case.root),
            "--profile",
            "deep",
            "--i-understand-deep-is-heuristic",
            "--use-external-api",
            "--select",
            "DS302",
            "--format",
            report_format,
        ]
    )

    out = capsys.readouterr().out
    assert code == 0
    assert backend.calls == [MIXED_CLAIM]
    if report_format == "json":
        report = json.loads(out)
        problems = [(doc["path"], p) for doc in report["documents"] for p in doc["problems"]]
        assert len(problems) == 1
        path, problem = problems[0]
        assert path == "orchard.md"
        assert (problem["rule"], problem["type"], problem["severity"], problem["value"], problem["outcome"]) == (
            "DS302",
            "unverified claim",
            "warning",
            value,
            "advisory",
        )
    else:
        lines = out.splitlines()
        assert [line for line in lines if line.startswith("orchard.md")] == [
            f"orchard.md ({case.path('orchard.md').stat().st_size} bytes)"
        ]
        assert [line.strip() for line in lines if line.startswith("  warning DS302")] == [
            f"warning DS302 unverified claim: {value}"
        ]


def test_project_config_confidence_floor_reaches_ds302(
    asset_case: Callable[[str, str], AssetCase], monkeypatch: pytest.MonkeyPatch
):
    """
    [Integration] DS302 config: verifies fact_check_min_confidence from docsentinel.toml reaches DS302.

    Scenario:
        Given the mixed corpus with docsentinel.toml setting fact_check_min_confidence = 0.9
        When the gate-open scan runs with the loaded configuration made deep and confirmed
        Then the 0.87 verdict is below the configured floor and gives no finding, though the claim was sent

    Boundaries:
        - Focus: project-config path of the confidence floor
        - Fixtures/params: asset ds302/both_gates_on_mixed_verdict_reports; config written inline
        - Scope: config.load_config and engine.scan

    On failure, first check:
        - Whether fact_check_min_confidence is read from the project file
    """
    case = asset_case("ds302", "both_gates_on_mixed_verdict_reports")
    (case.root / "docsentinel.toml").write_text(
        'fact_check_backend = "lenz"\nfact_check_min_confidence = 0.9\n', encoding="utf-8"
    )
    backend = register_fake_backend(monkeypatch, make_case_backend(case.root, name="lenz"))
    fact_check_env(monkeypatch, flag=False, key=True, key_env=backend.API_KEY_ENV_VAR)

    loaded = load_config(case.root)
    assert loaded.fact_check_min_confidence == 0.9

    result = scan(
        case.root,
        config=dataclasses.replace(loaded, profile="deep", deep_confirm=True, select=("DS302",)),
        use_external_api=True,
    )

    assert backend.calls == [MIXED_CLAIM]
    assert result.findings == ()
