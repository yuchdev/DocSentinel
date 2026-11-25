"""The ``extract-facts`` selection equals what a gate-open DS302 scan sends (plan contract C11).

Loads ``tests/assets/ds302/extract_facts_basic/`` (two synthetic documents with numeric and
named-entity claims, one near-duplicate pair across the files and one trivial sentence) and runs
the real spaCy pipeline twice: once through a confirmed deep scan selecting only ``DS302`` with both
consent gates open and a recording fake backend registered under the default backend name, once
through ``extract_facts`` / ``docsentinel extract-facts`` with default settings. The texts the fake
backend received must equal the listed facts exactly, in order. Both sides read the same root and
the same on-disk configuration; the deep scan only adds the profile, the confirmation and the rule
selection, which ``extract-facts`` does not read (decision X3).

No network is reached and no real backend is imported: the fake is registered in
``FACT_CHECK_BACKENDS`` for one test (so ``load_backend`` returns it without an import) and the key
is the threat model 0010 M12 sentinel. Skipped when ``mining.nlp.deep_ready()`` is false, like the
DS301 integration tests.
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
from docsentinel.fact_check.protocol import FACT_CHECK_BACKEND_MODULES
from docsentinel.mining import nlp
from tests.asset_helpers import AssetCase
from tests.fact_check_fakes import SENTINEL, FakeBackendBase, make_fake_backend, register_fake_backend

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The default backend's key variable (plan contract C3).
LENZ_KEY_ENV = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"

#: The near-duplicate pair of the asset case; at most one of them may be sent.
NEAR_DUPLICATES = (
    "The Quillan Space Agency granted 7 million credits to the eastern wing in 2029.",
    "The Quillan Space Agency granted 7 million credits to the eastern wing in 2029 overall.",
)

#: The trivial sentence of the asset case; it never clears the default floor.
TRIVIAL = "The staff likes the view."

#: Project configurations written as ``docsentinel.toml``; ``None`` writes none (all defaults).
CONFIGS: dict[str, Optional[str]] = {
    "defaults": None,
    "tight-caps": "fact_check_max_claims_per_document = 1\nfact_check_max_claims_total = 2\n",
    "zero-floor": "fact_check_min_salience = 0.0\n",
}


#: How many claims DS302 sends for each configuration (the config must reach both sides).
EXPECTED_COUNTS: dict[str, int] = {"defaults": 4, "tight-caps": 2, "zero-floor": 5}


@pytest.fixture
def recording_backend(monkeypatch: pytest.MonkeyPatch) -> type[FakeBackendBase]:
    """Register a recording fake as the default ``lenz`` backend and set the sentinel key.

    :param monkeypatch: Pytest monkeypatch; restores the registry and the environment.
    :returns: The fake class; its ``calls`` lists every text DS302 sent.
    """
    monkeypatch.setenv(LENZ_KEY_ENV, SENTINEL)
    return register_fake_backend(monkeypatch, make_fake_backend(name="lenz"))


def _case_root(asset_case: Callable[[str, str], AssetCase], config: Optional[str]) -> Path:
    """Materialize the asset case and write its project configuration.

    :param asset_case: The asset loader fixture.
    :param config: The ``docsentinel.toml`` body, or ``None``.
    :returns: The scan root.
    """
    root = asset_case("ds302", "extract_facts_basic").root
    if config is not None:
        (root / "docsentinel.toml").write_text(config, encoding="utf-8")
    return root


@pytest.mark.parametrize("name", sorted(CONFIGS))
def test_extract_facts_equals_what_a_gate_open_ds302_scan_sends(
    asset_case: Callable[[str, str], AssetCase], recording_backend: type[FakeBackendBase], name: str
):
    """
    [Integration] C11 equality: verifies the default extract_facts texts equal the claims DS302 sends, in order.

    Scenario:
        Given the extract_facts_basic corpus and a project configuration
        When a confirmed deep scan selecting DS302 runs with use_external_api=True and the recording
            fake backend, and extract_facts runs on the same root with no override
        Then the backend received exactly the facts' texts in the same order, matches_ds302 is true, the
            near-duplicate pair contributes at most one claim, and the count and the trivial sentence
            follow the configuration (only the zero floor admits it)

    Boundaries:
        - Focus: plan contract C11, Story 05.0 acceptance criterion 2
        - Fixtures/params: real spaCy pipeline; recording fake backend; three configurations
        - Scope: engine.scan (DS302 detect) and engine.extract_facts

    On failure, first check:
        - Whether DS302 detect() and extract_facts() still read trace_candidates with DS302_POLICY
    """
    root = _case_root(asset_case, CONFIGS[name])
    scan_config = dataclasses.replace(load_config(root), profile="deep", select=("DS302",))

    scanned = scan(root, config=scan_config, use_external_api=True)
    facts = extract_facts(root)

    sent = list(recording_backend.calls)
    assert sent, "the fixture corpus must yield at least one candidate"
    assert sent == [fact.text for fact in facts.facts]
    assert facts.matches_ds302 is True
    assert scanned.enabled_rules == ("DS302",)
    assert scanned.pending == ()
    assert scanned.findings == ()
    assert recording_backend.constructed == recording_backend.closed == 1
    assert sum(text in NEAR_DUPLICATES for text in sent) <= 1
    assert (TRIVIAL in sent) is (name == "zero-floor")
    assert len(sent) == EXPECTED_COUNTS[name]
    assert "docsentinel.fact_check.lenz" not in sys.modules


def test_default_selection_collapses_the_near_duplicate_pair(
    asset_case: Callable[[str, str], AssetCase], recording_backend: type[FakeBackendBase]
):
    """
    [Integration] C11 equality: verifies the default DS302 selection of the fixture, sentence by sentence.

    Scenario:
        Given the extract_facts_basic corpus with no configuration file
        When the gate-open DS302 scan runs
        Then exactly one member of the near-duplicate pair is sent, the trivial sentence is not, and four
            claims are sent, each a sentence of the corpus

    Boundaries:
        - Focus: fixture contract (Task 04 step 7) on which the equality test relies
        - Fixtures/params: real spaCy pipeline; recording fake backend
        - Scope: engine.scan

    On failure, first check:
        - A spaCy model upgrade changing the extracted claims (Story README RR4)
    """
    root = _case_root(asset_case, None)
    corpus = (root / "observatory.md").read_text(encoding="utf-8") + (root / "archive.md").read_text(encoding="utf-8")

    scan(
        root,
        config=dataclasses.replace(load_config(root), profile="deep", select=("DS302",)),
        use_external_api=True,
    )

    sent = recording_backend.calls
    assert len(sent) == 4
    assert sum(text in NEAR_DUPLICATES for text in sent) == 1
    assert TRIVIAL not in sent
    assert all(text in corpus for text in sent)


def test_cli_extract_facts_json_equals_what_cli_scan_sends(
    asset_case: Callable[[str, str], AssetCase],
    recording_backend: type[FakeBackendBase],
    capsys: pytest.CaptureFixture[str],
):
    """
    [Integration] C11 equality via the CLI: verifies extract-facts --format facts-json lists what scan --use-external-api sends.

    Scenario:
        Given the extract_facts_basic corpus
        When docsentinel scan --profile deep --use-external-api --select DS302
            runs, then docsentinel extract-facts --format facts-json
        Then both exit 0 and the facts' texts equal the backend's recorded calls, in order, with
            matches_ds302 true; no backend module was imported

    Boundaries:
        - Focus: plan contract C11 through both command lines
        - Fixtures/params: real spaCy pipeline; recording fake backend registered as lenz
        - Scope: cli.main scan and extract-facts

    On failure, first check:
        - Whether the CLI handlers pass the same configuration and selection to the engine
    """
    root = _case_root(asset_case, None)

    scan_code = cli.main(
        [
            "scan",
            str(root),
            "--profile",
            "deep",
            "--use-external-api",
            "--select",
            "DS302",
            "--format",
            "json",
        ]
    )
    capsys.readouterr()
    facts_code = cli.main(["extract-facts", str(root), "--format", "facts-json"])
    output = json.loads(capsys.readouterr().out)

    assert scan_code == 0
    assert facts_code == 0
    assert output["matches_ds302"] is True
    assert [fact["text"] for fact in output["facts"]] == recording_backend.calls
    assert len(recording_backend.calls) == 4
    assert not {"docsentinel.fact_check.lenz", *FACT_CHECK_BACKEND_MODULES.values()} & set(sys.modules)
