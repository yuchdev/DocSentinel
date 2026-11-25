"""DS302 salience end to end and the C11 send set per asset case (Milestone 0010 Story 04.0 Task 02 steps 6 and 10).

Step 6: ``salience_filter_drops_trivial_claim`` (one salient and one trivial sentence) and
``corpus_dedup_collapses_repeated_claim`` (one sentence repeated in three documents plus one other
claim) run through a gate-open ``scan()``; the fake's ``calls`` show what reached the backend, and
the total cap is lowered to one.

Step 10: for every ``tests/assets/ds302/`` case where DS302 sends at least one claim, the default
``extract_facts()`` texts and the ``extract-facts --format facts-json`` ``facts[].text`` values equal
the fake's ``calls`` in order, also with a lowered ``fact_check_max_claims_total`` in the project
configuration. Exploration flags passed only to ``extract-facts`` clear ``matches_ds302`` and never
change what DS302 sends, and ``extract-facts`` with both gate-2 prerequisites set sends nothing.
``extract_facts_basic`` is covered by ``test_fact_check_extract_facts_equivalence_ds302.py``.

No network is reached: a recording fake is registered as the default ``lenz`` backend for one test
(so the CLI configuration, which accepts only shipped names, reaches it) and the key is the threat
model 0010 M12 sentinel. Skipped when ``mining.nlp.deep_ready()`` is false.
"""

import dataclasses
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import pytest

from docsentinel import cli, extract_facts, scan
from docsentinel.config import load_config
from docsentinel.mining import nlp
from docsentinel.models import ScanResult
from tests.asset_helpers import AssetCase
from tests.fact_check_fakes import (
    FakeBackendBase,
    fact_check_env,
    make_case_backend,
    register_fake_backend,
)

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The default backend's key variable (plan contract C3).
LENZ_KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"

#: The trivial sentence of the salience case.
TRIVIAL = "The visitors enjoy the path."

#: The salient sentence of the salience case.
SALIENT = "The Wexley botanical garden grows 1,240 species of fern from Borneo."

#: The sentence repeated in three documents of the dedup case.
REPEATED = "The Halcrest museum displays 340 bronze coins from Varos."

#: The other claim of the dedup case.
PELHAM = "The Pelham reading room recorded 58 visiting scholars during 2020."

#: Every asset case (other than extract_facts_basic) with how many claims DS302 sends by default.
SENDING_CASES = {
    "both_gates_on_clean_verdict": 3,
    "both_gates_on_false_verdict_reports": 3,
    "both_gates_on_mixed_verdict_reports": 1,
    "corpus_dedup_collapses_repeated_claim": 2,
    "deep_confirm_off_skips_everything_including_ds302": 1,
    # Both sentences carry a number or date: "in 2019" counts since statements are scored whole.
    "gate_off_no_flag": 2,
    "gate_off_no_key": 1,
    "per_claim_network_error_skipped": 3,
    "salience_filter_drops_trivial_claim": 1,
}


@pytest.fixture
def lenz_fake(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], type[FakeBackendBase]]:
    """Return a function registering the case fake as ``lenz`` and setting the sentinel key.

    :param monkeypatch: Pytest monkeypatch; restores the registry and the environment.
    :returns: The registering function; it takes the case root and returns the fake class.
    """

    def register(root: Path) -> type[FakeBackendBase]:
        """Register a fresh fake scripted by the case under ``root``.

        :param root: The case root.
        :returns: The fake class.
        """
        fact_check_env(monkeypatch, flag=False, key=True, key_env=LENZ_KEY_ENV)
        return register_fake_backend(monkeypatch, make_case_backend(root, name="lenz"))

    return register


def _ds302_scan(root: Path, config_overrides: Optional[dict[str, object]] = None) -> ScanResult:
    """Run a confirmed, gate-open deep scan selecting DS302 over the loaded project config.

    :param root: The scan root.
    :param config_overrides: Extra ``Config`` fields.
    :returns: The result.
    """
    config = dataclasses.replace(
        load_config(root), profile="deep", select=("DS302",), **(config_overrides or {})
    )
    return scan(root, config=config, use_external_api=True)


def _cli_facts(capsys: pytest.CaptureFixture[str], root: Path, *extra: str) -> dict[str, object]:
    """Run ``extract-facts --format facts-json`` and return the parsed report.

    :param capsys: Pytest capture.
    :param root: The root.
    :param extra: Extra arguments.
    :returns: The JSON report.
    """
    capsys.readouterr()
    assert cli.main(["extract-facts", str(root), "--format", "facts-json", *extra]) == 0
    return json.loads(capsys.readouterr().out)


def test_trivial_claim_never_reaches_the_backend(
    asset_case: Callable[[str, str], AssetCase], lenz_fake: Callable[[Path], type[FakeBackendBase]]
):
    """
    [Integration] DS302 salience: verifies the trivial sentence is filtered by the floor, not by extraction.

    Scenario:
        Given the salience_filter_drops_trivial_claim corpus
        When the gate-open scan runs with the default floor, and again with fact_check_min_salience = 0.0
        Then the default run sends only the salient claim; the zero-floor run sends the trivial one too

    Boundaries:
        - Focus: Task 02 step 6, salience case
        - Fixtures/params: asset ds302/salience_filter_drops_trivial_claim
        - Scope: engine.scan and the salience floor

    On failure, first check:
        - fact_check_min_salience handling in trace_candidates
    """
    case = asset_case("ds302", "salience_filter_drops_trivial_claim")
    default_backend = lenz_fake(case.root)
    _ds302_scan(case.root)
    zero_backend = lenz_fake(case.root)
    _ds302_scan(case.root, {"fact_check_min_salience": 0.0})

    assert default_backend.calls == [SALIENT]
    assert TRIVIAL not in default_backend.calls
    assert sorted(zero_backend.calls) == sorted([SALIENT, TRIVIAL])


def test_repeated_sentence_is_sent_once_and_the_total_cap_holds(
    asset_case: Callable[[str, str], AssetCase], lenz_fake: Callable[[Path], type[FakeBackendBase]]
):
    """
    [Integration] DS302 dedup: verifies a sentence in three documents is sent once and max_claims_total = 1 sends one.

    Scenario:
        Given the corpus_dedup_collapses_repeated_claim corpus
        When the gate-open scan runs with defaults, and again with fact_check_max_claims_total = 1
        Then the default run sends the repeated sentence exactly once plus the Pelham claim; the capped run
            sends exactly one claim, the first of the default order

    Boundaries:
        - Focus: Task 02 step 6, dedup and cap cases
        - Fixtures/params: asset ds302/corpus_dedup_collapses_repeated_claim
        - Scope: engine.scan, clustering and the total cap

    On failure, first check:
        - The cluster representative choice in mining/salience.py
    """
    case = asset_case("ds302", "corpus_dedup_collapses_repeated_claim")
    default_backend = lenz_fake(case.root)
    _ds302_scan(case.root)
    capped_backend = lenz_fake(case.root)
    _ds302_scan(case.root, {"fact_check_max_claims_total": 1})

    assert default_backend.calls.count(REPEATED) == 1
    assert sorted(default_backend.calls) == sorted([REPEATED, PELHAM])
    assert capped_backend.calls == default_backend.calls[:1]


@pytest.mark.parametrize("name", sorted(SENDING_CASES))
def test_extract_facts_equals_the_ds302_send_set_of_every_case(
    asset_case: Callable[[str, str], AssetCase],
    lenz_fake: Callable[[Path], type[FakeBackendBase]],
    capsys: pytest.CaptureFixture[str],
    name: str,
):
    """
    [Integration] C11 per case: verifies extract_facts and extract-facts list exactly what DS302 sends, in order.

    Scenario:
        Given an asset case where DS302 sends at least one claim
        When the gate-open DS302 scan runs, then extract_facts() and "extract-facts --format facts-json"
        Then all three lists are equal in order, have the case's count, and matches_ds302 is true on both

    Boundaries:
        - Focus: plan contract C11; Task 02 step 10
        - Fixtures/params: every sending asset case under tests/assets/ds302/
        - Scope: engine.scan, engine.extract_facts and cli.main extract-facts

    On failure, first check:
        - Whether DS302 and extract_facts still share trace_candidates
    """
    case = asset_case("ds302", name)
    backend = lenz_fake(case.root)

    _ds302_scan(case.root)
    library = extract_facts(case.root)
    report = _cli_facts(capsys, case.root)

    assert len(backend.calls) == SENDING_CASES[name]
    assert [fact.text for fact in library.facts] == backend.calls
    assert [fact["text"] for fact in report["facts"]] == backend.calls
    assert library.matches_ds302 is True
    assert report["matches_ds302"] is True


def test_lowered_total_cap_in_the_project_config_shrinks_both_sides(
    asset_case: Callable[[str, str], AssetCase],
    lenz_fake: Callable[[Path], type[FakeBackendBase]],
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] C11 with a project cap: verifies fact_check_max_claims_total in docsentinel.toml shrinks both lists.

    Scenario:
        Given the false-verdict corpus (three claims by default) and docsentinel.toml with
            fact_check_max_claims_total = 2
        When the gate-open DS302 scan, extract_facts() and the CLI extract-facts run
        Then each yields the same two texts, a prefix of the default order, and matches_ds302 stays true

    Boundaries:
        - Focus: plan contract C11, lowered cap bullet
        - Fixtures/params: asset ds302/both_gates_on_false_verdict_reports; config written inline
        - Scope: config.load_config, engine.scan, engine.extract_facts, cli.main extract-facts

    On failure, first check:
        - Whether both paths read fact_check_max_claims_total from the same Config
    """
    case = asset_case("ds302", "both_gates_on_false_verdict_reports")
    default_order = [fact.text for fact in extract_facts(case.root).facts]
    (case.root / "docsentinel.toml").write_text("fact_check_max_claims_total = 2\n", encoding="utf-8")
    backend = lenz_fake(case.root)

    _ds302_scan(case.root)
    library = extract_facts(case.root)
    report = _cli_facts(capsys, case.root)

    assert backend.calls == default_order[:2]
    assert [fact.text for fact in library.facts] == backend.calls
    assert [fact["text"] for fact in report["facts"]] == backend.calls
    assert library.matches_ds302 is True
    assert report["matches_ds302"] is True


@pytest.mark.parametrize(
    ("flags", "prefix_only"),
    [(("--max-total", "1"), True), (("--weights", "0.2,0.2,0.6"), False)],
    ids=["max_total", "weights"],
)
def test_exploration_flags_clear_the_match_and_never_change_ds302(
    asset_case: Callable[[str, str], AssetCase],
    lenz_fake: Callable[[Path], type[FakeBackendBase]],
    capsys: pytest.CaptureFixture[str],
    flags: tuple[str, str],
    prefix_only: bool,
):
    """
    [Integration] C11 exploration: verifies --max-total and --weights only change extract-facts.

    Scenario:
        Given the false-verdict corpus
        When the gate-open DS302 scan runs, then extract-facts runs with --max-total 1 or --weights 0.2,0.2,0.6,
            then the DS302 scan runs again
        Then matches_ds302 is false; --max-total 1 lists exactly the first sent text; and the second scan
            sends exactly what the first one sent

    Boundaries:
        - Focus: plan contract C11 exploration bullets (decision X3)
        - Fixtures/params: asset ds302/both_gates_on_false_verdict_reports; two flag sets
        - Scope: cli.main extract-facts and engine.scan

    On failure, first check:
        - Whether an extract-facts override leaks into Config or DS302_POLICY
    """
    case = asset_case("ds302", "both_gates_on_false_verdict_reports")
    before = lenz_fake(case.root)
    _ds302_scan(case.root)

    report = _cli_facts(capsys, case.root, *flags)
    after = lenz_fake(case.root)
    _ds302_scan(case.root)

    texts = [fact["text"] for fact in report["facts"]]
    assert report["matches_ds302"] is False
    assert after.calls == before.calls
    if prefix_only:
        assert texts == before.calls[:1]
    else:
        assert texts


def test_extract_facts_with_both_gate_prerequisites_sends_nothing(
    asset_case: Callable[[str, str], AssetCase],
    lenz_fake: Callable[[Path], type[FakeBackendBase]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] C11 offline: verifies extract-facts with DOCSENTINEL_USE_EXTERNAL_API=1 and a key calls no backend.

    Scenario:
        Given the false-verdict corpus and a recording fake registered as lenz with the sentinel key
        When extract-facts --format facts-json runs without, then with DOCSENTINEL_USE_EXTERNAL_API=1
        Then the fake was never constructed or called, the two outputs are identical and no backend module
            was imported

    Boundaries:
        - Focus: plan contract C11 last bullet; Story 05.0 offline guarantee
        - Fixtures/params: asset ds302/both_gates_on_false_verdict_reports
        - Scope: cli.main extract-facts

    On failure, first check:
        - Any gate or backend call added to engine.extract_facts
    """
    case = asset_case("ds302", "both_gates_on_false_verdict_reports")
    backend = lenz_fake(case.root)
    plain = _cli_facts(capsys, case.root)
    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")

    gated = _cli_facts(capsys, case.root)

    assert gated == plain
    assert (backend.calls, backend.constructed) == ([], 0)
    assert "docsentinel.fact_check.lenz" not in sys.modules
