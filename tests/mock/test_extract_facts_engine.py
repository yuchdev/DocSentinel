"""``engine.extract_facts`` with the spaCy pipeline and claim extraction replaced (Story 05.0 Task 01).

The pipeline loader and ``mining.claims.extract_claims`` are patched to return hand-built ``Claim``
literals, so no spaCy model is needed; salience and clustering run for real. Covers plan contract
C11 (same texts as ``collect_candidates``), the overrides and ``matches_ds302``, and threat model
0010 extract-facts mitigations E6 (validate before extraction), E7 (type-name-only error), E8
(per-fact list caps) and E12 (notice wording). The Story 05.0 Task 04 cases stub
``trace_candidates`` itself (``engine.trace_candidates``) where only the inventory, the validation
order or the error containment is under test.
"""

import dataclasses
import logging
import math
from pathlib import Path

import pytest

from docsentinel import engine, extract_facts
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import fact_check
from docsentinel.mining.claims import Claim
from docsentinel.models import Document

#: A sentence that must never appear in a log record or an exception message.
SENTINEL_SENTENCE = "Sentinel-0010 claim text must never be logged"


def _claims_for(text: str, path: str) -> tuple[Claim, ...]:
    """Return one salient claim per non-blank line of ``text``.

    :param text: The document text.
    :param path: The document path.
    :returns: The claim literals.
    """
    claims = []
    for index, line in enumerate(line for line in text.splitlines() if line.strip()):
        claims.append(
            Claim(
                subject_key="node",
                predicate_key="hold",
                raw_subject="Node",
                raw_object=f"{index} shards Q{index}",
                raw_sentence=line,
                object_numbers=(str(index),),
                object_entities=(f"DATE:Q{index}",),
                path=path,
                paragraph_index=index,
            )
        )
    return tuple(claims)


@pytest.fixture
def patched_extraction(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch deep readiness, the pipeline and claim extraction; record each loader call.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The list ``load_pipeline`` and ``extract_claims`` append to.
    """
    calls: list[str] = []
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: calls.append("pipeline") or "pipeline")

    def _extract(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Record the call and return claim literals."""
        calls.append(path)
        return _claims_for(text, path)

    monkeypatch.setattr("docsentinel.mining.claims.extract_claims", _extract)
    return calls


def _corpus(tmp_path: Path) -> Path:
    """Write two documents of distinct claim sentences.

    :param tmp_path: Pytest temporary directory.
    :returns: The scan root.
    """
    (tmp_path / "a.md").write_text(
        "\n".join(f"Node alpha{k} holds {k} shards in Q{k} region{k}." for k in range(6)) + "\n", encoding="utf-8"
    )
    (tmp_path / "b.md").write_text(
        "\n".join(f"Cluster bravo{k} runs {k} replicas in zone{k} rack{k}." for k in range(4)) + "\n",
        encoding="utf-8",
    )
    return tmp_path


def test_default_facts_equal_ds302_candidates(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies the default facts are exactly the DS302 candidate texts (C11).

    Scenario:
        Given two documents and patched extraction
        When extract_facts runs with defaults and collect_candidates runs on the same inventory
        Then the texts match in order, matches_ds302 is true, ranks are 1-based and the notice is E12's

    Boundaries:
        - Focus: plan contract C11, Task 01 steps 4.4-4.6
        - Fixtures/params: patched pipeline and extract_claims
        - Scope: extract_facts and collect_candidates

    On failure, first check:
        - Whether extract_facts still calls trace_candidates with DS302_POLICY
    """
    root = _corpus(tmp_path)
    config = Config()
    result = extract_facts(root, config=config)
    expected = fact_check.collect_candidates(root.resolve(), result.documents, config)
    assert [f.text for f in result.facts] == [c.text for c in expected]
    assert [f.rank for f in result.facts] == list(range(1, len(result.facts) + 1))
    assert result.matches_ds302 is True
    assert result.selected == result.facts
    assert all(f.disposition == "selected" for f in result.facts)
    assert result.claims_extracted == 10
    assert result.settings.weights == fact_check.DS302_POLICY.weights
    assert result.notice == (
        "Heuristic, offline claim extraction; no network call was made and nothing was verified. "
        "The selected facts are the claims DS302 would send, at most and in this order, "
        "if it ran with both gates open on the same configuration and selection, "
        "with DS302 among the active rules; fact_check_time_budget_seconds can stop it earlier."
    )


def test_overrides_and_exploration_name_the_settings(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies differing overrides and exploration settings clear matches_ds302.

    Scenario:
        Given the default config
        When extract_facts runs with max_total=2, weights (0.2, 0.2, 0.6) and the default threshold
        Then matches_ds302 is false, the notice names max_total and weights only, and at most 2 are selected

    Boundaries:
        - Focus: decisions X5 and X6
        - Fixtures/params: patched pipeline and extract_claims
        - Scope: extract_facts

    On failure, first check:
        - The differs tuple and the fixed setting-name vocabulary
    """
    result = extract_facts(
        _corpus(tmp_path), config=Config(), max_total=2, weights=(0.2, 0.2, 0.6), dedup_threshold=0.92
    )
    assert result.matches_ds302 is False
    assert result.notice.endswith("Settings differ from DS302 (max_total, weights); DS302 would send a different set.")
    assert len(result.selected) <= 2
    assert result.settings.max_total == 2
    assert fact_check.DS302_POLICY.weights == (0.3, 0.3, 0.4)


def test_override_equal_to_config_still_matches(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies an override equal to the effective config keeps matches_ds302.

    Scenario:
        Given a config with fact_check_max_claims_total = 7
        When extract_facts runs with max_total=7 and the DS302 weights spelled out
        Then matches_ds302 stays true

    Boundaries:
        - Focus: Task 01 step 4.5 (compare against pre-override values)
        - Fixtures/params: patched extraction
        - Scope: extract_facts

    On failure, first check:
        - Whether the comparison uses the pre-override settings
    """
    config = dataclasses.replace(Config(), fact_check_max_claims_total=7)
    result = extract_facts(_corpus(tmp_path), config=config, max_total=7, weights=(0.3, 0.3, 0.4))
    assert result.matches_ds302 is True


def test_include_rejected_lists_every_canonical_claim(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies include_rejected lists every claim with a disposition, selected unchanged.

    Scenario:
        Given ten claims over two documents and the default per-document cap of 3
        When extract_facts runs with and without include_rejected
        Then all ten are listed, some as document_cap, and the selected subsets are equal

    Boundaries:
        - Focus: decision X7
        - Fixtures/params: patched extraction
        - Scope: extract_facts

    On failure, first check:
        - The listed filter on trace.entries
    """
    root = _corpus(tmp_path)
    everything = extract_facts(root, config=Config(), include_rejected=True)
    assert len(everything.facts) == 10
    assert {f.disposition for f in everything.facts} <= {"selected", "document_cap", "total_cap", "below_floor"}
    assert "document_cap" in {f.disposition for f in everything.facts}
    assert [f.text for f in everything.selected] == [f.text for f in extract_facts(root, config=Config()).facts]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_salience": math.nan},
        {"min_salience": math.inf},
        {"max_total": 0},
        {"max_per_document": True},
        {"weights": (math.nan, 0.5, 0.5)},
        {"weights": (0.5, 0.5, 0.5)},
        {"weights": (True, 0.0, 0.0)},
        {"weights": (0.5, 0.5)},
        {"dedup_threshold": 0},
        {"dedup_threshold": math.inf},
        {"dedup_threshold": False},
        {"include_rejected": 1},
    ],
)
def test_invalid_settings_fail_before_extraction(
    tmp_path: Path, patched_extraction: list[str], kwargs: dict[str, object]
):
    """
    [Unit] extract_facts: verifies every invalid override or exploration value fails before the pipeline loads.

    Scenario:
        Given one invalid value (NaN, infinity, out of range, bool, wrong arity, bad weight sum)
        When extract_facts runs
        Then ConfigError or ValueError is raised and load_pipeline/extract_claims were never called

    Boundaries:
        - Focus: threat model E6
        - Fixtures/params: one invalid value per case
        - Scope: extract_facts validation order

    On failure, first check:
        - Whether validation moved after deep_ready() or trace_candidates
    """
    with pytest.raises((ConfigError, ValueError)):
        extract_facts(_corpus(tmp_path), config=Config(), **kwargs)  # type: ignore[arg-type]
    assert patched_extraction == []


def test_deep_not_ready_raises_runtime_error_before_reading(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] extract_facts: verifies missing deep extras raise RuntimeError with the hint and read nothing.

    Scenario:
        Given deep_ready() false and a spy on load_pipeline
        When extract_facts runs
        Then RuntimeError names the deep extras and the spy was not called

    Boundaries:
        - Focus: decision X11
        - Fixtures/params: patched deep_ready
        - Scope: extract_facts

    On failure, first check:
        - The deep_ready check position
    """
    calls: list[str] = []
    monkeypatch.setattr(engine, "deep_ready", lambda: False)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: calls.append("pipeline"))
    with pytest.raises(RuntimeError, match="extract-facts needs the deep extras and the spaCy model - "):
        extract_facts(_corpus(tmp_path), config=Config())
    assert calls == []


def test_extraction_failure_is_type_name_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """
    [Unit] extract_facts: verifies an extraction exception becomes a chainless, type-name-only RuntimeError.

    Scenario:
        Given extract_claims raising ValueError carrying a sentinel sentence
        When extract_facts runs
        Then RuntimeError names ValueError only, has no cause or context, and no record holds the sentence

    Boundaries:
        - Focus: threat model E7
        - Fixtures/params: patched extract_claims
        - Scope: extract_facts error path

    On failure, first check:
        - The except/raise split in engine._traced
    """
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: "pipeline")

    def _boom(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Raise with document text in the message."""
        raise ValueError(SENTINEL_SENTENCE)

    monkeypatch.setattr("docsentinel.mining.claims.extract_claims", _boom)
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    with pytest.raises(RuntimeError) as info:
        extract_facts(_corpus(tmp_path), config=Config())
    assert str(info.value) == "extract-facts: claim extraction failed (ValueError)"
    assert info.value.__cause__ is None
    assert info.value.__context__ is None
    assert all(SENTINEL_SENTENCE not in record.getMessage() and not record.exc_info for record in caplog.records)


def test_no_claim_text_is_logged(tmp_path: Path, patched_extraction: list[str], caplog: pytest.LogCaptureFixture):
    """
    [Unit] extract_facts: verifies no log record at any level carries claim text, and one INFO counts line exists.

    Scenario:
        Given a document whose only claim is the sentinel sentence
        When extract_facts runs with DEBUG logging captured
        Then the sentence is in the result but in no record, and the INFO line has counts only

    Boundaries:
        - Focus: Task 01 step 4.7, threat model E13 (library part)
        - Fixtures/params: patched extraction
        - Scope: extract_facts logging

    On failure, first check:
        - Any new log call formatting a claim or candidate
    """
    (tmp_path / "s.md").write_text(SENTINEL_SENTENCE + " 42 Q4.\n", encoding="utf-8")
    caplog.set_level(logging.DEBUG, logger="docsentinel")
    result = extract_facts(tmp_path, config=dataclasses.replace(Config(), fact_check_min_salience=0.0))
    assert result.facts and SENTINEL_SENTENCE in result.facts[0].text
    assert all(SENTINEL_SENTENCE not in record.getMessage() for record in caplog.records)
    assert "extract-facts: 1 documents read, 1 claims, 1 selected, 1 listed (policy ds302)" in [
        r.getMessage() for r in caplog.records
    ]


def test_numbers_and_entities_are_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] extract_facts: verifies per-fact numbers/entities are capped at 32 items of 200 code points.

    Scenario:
        Given one claim with 10,000 entities of 500 characters each
        When extract_facts runs with a floor of 0
        Then the fact lists 32 entities of 200 characters, while the text is unchanged

    Boundaries:
        - Focus: threat model E8
        - Fixtures/params: patched extraction
        - Scope: engine._bounded

    On failure, first check:
        - MAX_FACT_LIST_ITEMS / MAX_FACT_ITEM_CHARS
    """
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: "pipeline")
    big = tuple(f"ORG:{k}" + "x" * 500 for k in range(10_000))

    def _extract(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Return one claim with a huge entity list."""
        claim = _claims_for(text, path)[0]
        return (dataclasses.replace(claim, object_entities=big),)

    monkeypatch.setattr("docsentinel.mining.claims.extract_claims", _extract)
    (tmp_path / "a.md").write_text("Node one holds 3 shards in Q1.\n", encoding="utf-8")
    result = extract_facts(tmp_path, config=dataclasses.replace(Config(), fact_check_min_salience=0.0))
    (fact,) = result.facts
    assert len(fact.entities) == engine.MAX_FACT_LIST_ITEMS == 32
    assert all(len(entity) == engine.MAX_FACT_ITEM_CHARS == 200 for entity in fact.entities)
    assert fact.text == "Node one holds 3 shards in Q1."


def test_inventory_errors_match_scan(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies the shared inventory step: empty invoker selection, unreadable skip, single file.

    Scenario:
        Given a root with one good and one non-UTF-8 document
        When extract_facts runs with an include matching nothing, then over the root, then over one file
        Then the first raises the scan() ConfigError, the second counts one unreadable document,
        and the third reads only the selected file

    Boundaries:
        - Focus: decisions X3, X4, X12
        - Fixtures/params: patched extraction
        - Scope: extract_facts through engine._inventory

    On failure, first check:
        - Whether extract_facts still calls engine._inventory
    """
    (tmp_path / "good.md").write_text("Node one holds 3 shards in Q1.\n", encoding="utf-8")
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe not utf-8\n")
    (tmp_path / "sub").mkdir()
    with pytest.raises(ConfigError, match=engine.EMPTY_SELECTION_MESSAGE):
        extract_facts(tmp_path, config=Config(), include=["sub"])
    result = extract_facts(tmp_path, config=Config())
    assert result.documents_unreadable == 1
    assert [d.path for d in result.documents] == ["bad.md", "good.md"]
    patched_extraction.clear()
    single = extract_facts(tmp_path / "good.md", config=Config())
    assert [d.path for d in single.documents] == ["good.md"]
    assert patched_extraction == ["pipeline", "good.md"]


#: The exact E12 notice text when every setting equals the DS302 selection.
MATCHING_NOTICE = (
    "Heuristic, offline claim extraction; no network call was made and nothing was verified. "
    "The selected facts are the claims DS302 would send, at most and in this order, "
    "if it ran with both gates open on the same configuration and selection, "
    "with DS302 among the active rules; fact_check_time_budget_seconds can stop it earlier."
)


def _differing_notice(names: str) -> str:
    """Return the exact E12 notice text when the named settings differ.

    :param names: The comma-separated setting names, in display order.
    :returns: The notice.
    """
    return (
        "Heuristic, offline claim extraction; no network call was made and nothing was verified. "
        f"Settings differ from DS302 ({names}); DS302 would send a different set."
    )


@pytest.fixture
def stub_trace(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Report deep readiness and replace ``engine.trace_candidates`` with a recorder.

    The stub returns one selected candidate per readable document it receives.

    :param monkeypatch: Pytest monkeypatch.
    :returns: The document paths of each call, one tuple per call.
    """
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(engine, "deep_ready", lambda: True)

    def _stub(
        root: Path,
        documents: tuple[Document, ...],
        config: Config,
        *,
        policy: fact_check.SelectionPolicy = fact_check.DS302_POLICY,
    ) -> fact_check.CandidateTrace:
        """Record the documents and return one candidate per document.

        :param root: The scan root.
        :param documents: The readable documents.
        :param config: The effective configuration.
        :param policy: The selection policy.
        :returns: The trace.
        """
        calls.append(tuple(doc.path for doc in documents))
        entries = tuple(
            (fact_check.CandidateClaim(claim=claim, text=claim.raw_sentence, score=0.9), "selected")
            for claim in (_claims_for(f"Node {doc.path} holds 3 shards.", doc.path)[0] for doc in documents)
        )
        return fact_check.CandidateTrace(entries=entries, documents_read=len(documents), claims_extracted=len(entries))

    monkeypatch.setattr(engine, "trace_candidates", _stub)
    return calls


@pytest.mark.parametrize(
    ("kwargs", "names", "field", "value"),
    [
        ({"min_salience": 0.25}, "min_salience", "min_salience", 0.25),
        ({"max_per_document": 1}, "max_per_document", "max_per_document", 1),
        ({"max_total": 2}, "max_total", "max_total", 2),
        ({"weights": (0.2, 0.2, 0.6)}, "weights", "weights", (0.2, 0.2, 0.6)),
        ({"dedup_threshold": 0.8}, "dedup_threshold", "dedup_threshold", 0.8),
        (
            {"dedup_threshold": 0.8, "min_salience": 0.25, "weights": (0.2, 0.2, 0.6)},
            "min_salience, weights, dedup_threshold",
            "dedup_threshold",
            0.8,
        ),
    ],
    ids=["min_salience", "max_per_document", "max_total", "weights", "dedup_threshold", "three-in-display-order"],
)
def test_each_differing_setting_is_applied_and_named_in_the_exact_notice(
    tmp_path: Path,
    patched_extraction: list[str],
    kwargs: dict[str, object],
    names: str,
    field: str,
    value: object,
):
    """
    [Unit] extract_facts: verifies each override is applied, clears matches_ds302 and is named in the exact notice.

    Scenario:
        Given the default config and one (or three) differing settings
        When extract_facts runs
        Then the settings field holds the value, matches_ds302 is false and the notice is exactly the E12
            differing text with the names in the fixed display order

    Boundaries:
        - Focus: decisions X5/X6, threat model E12
        - Fixtures/params: patched extraction; one setting per case
        - Scope: extract_facts

    On failure, first check:
        - _FACT_SETTING_NAMES and the differs tuple
    """
    result = extract_facts(_corpus(tmp_path), config=Config(), **kwargs)  # type: ignore[arg-type]

    assert getattr(result.settings, field) == value
    assert result.matches_ds302 is False
    assert result.notice == _differing_notice(names)
    assert result.notice == engine._FACTS_NOTICE_BASE + engine._FACTS_NOTICE_DIFFERS.format(names=names)


def test_matching_notice_is_the_exact_engine_constant(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies the matching notice is exactly the E12 constants and plain text.

    Scenario:
        Given the default config
        When extract_facts runs with no override
        Then the notice equals _FACTS_NOTICE_BASE + _FACTS_NOTICE_MATCHES and the literal E12 text

    Boundaries:
        - Focus: threat model E12
        - Fixtures/params: patched extraction
        - Scope: extract_facts

    On failure, first check:
        - The notice constants in engine.py
    """
    result = extract_facts(_corpus(tmp_path), config=Config())

    assert result.notice == engine._FACTS_NOTICE_BASE + engine._FACTS_NOTICE_MATCHES == MATCHING_NOTICE


@pytest.mark.parametrize("value", ["yes", 1, None, "true"])
def test_include_rejected_must_be_a_real_bool(tmp_path: Path, stub_trace: list[tuple[str, ...]], value: object):
    """
    [Unit] extract_facts: verifies a non-bool include_rejected raises the fixed ConfigError before any read.

    Scenario:
        Given include_rejected set to a string, an int or None
        When extract_facts runs
        Then ConfigError(INCLUDE_REJECTED_TYPE_MESSAGE) is raised and trace_candidates is never called

    Boundaries:
        - Focus: decision X7, threat model E6
        - Fixtures/params: one value per case
        - Scope: extract_facts validation

    On failure, first check:
        - The isinstance(include_rejected, bool) check at the top of extract_facts
    """
    with pytest.raises(ConfigError, match=f"^{engine.INCLUDE_REJECTED_TYPE_MESSAGE}$"):
        extract_facts(_corpus(tmp_path), config=Config(), include_rejected=value)  # type: ignore[arg-type]
    assert stub_trace == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"weights": (math.inf, 0.0, 0.0)},
        {"weights": (0.3, 0.3, math.nan)},
        {"dedup_threshold": math.nan},
        {"dedup_threshold": -math.inf},
        {"max_total": 0},
        {"max_total": 501},
        {"min_salience": 1.5},
    ],
    ids=["inf-weight", "nan-weight", "nan-threshold", "neg-inf-threshold", "max-total-0", "max-total-501", "floor-1.5"],
)
def test_invalid_values_fail_before_deep_readiness_and_the_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, object]
):
    """
    [Unit] extract_facts: verifies NaN, infinity and out-of-range values raise before deep_ready or load_pipeline (E6).

    Scenario:
        Given spies on engine.deep_ready and the pipeline loader
        When extract_facts runs with one invalid exploration or override value
        Then ConfigError or ValueError is raised and neither spy recorded a call

    Boundaries:
        - Focus: threat model E6 (validate before the expensive stage)
        - Fixtures/params: one invalid value per case
        - Scope: extract_facts validation order

    On failure, first check:
        - Whether the validation moved below the deep_ready() check
    """
    calls: list[str] = []
    monkeypatch.setattr(engine, "deep_ready", lambda: calls.append("deep_ready") or True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: calls.append("pipeline"))

    with pytest.raises((ConfigError, ValueError)):
        extract_facts(_corpus(tmp_path), config=Config(), **kwargs)  # type: ignore[arg-type]
    assert calls == []


def test_single_file_target_ignores_selectors_with_one_warning(
    tmp_path: Path, stub_trace: list[tuple[str, ...]], caplog: pytest.LogCaptureFixture
):
    """
    [Unit] extract_facts: verifies a single-file target reads only that file and ignores selectors with one WARNING.

    Scenario:
        Given two documents and include/exclude selectors that would exclude the target
        When extract_facts runs on b.md alone with those selectors
        Then only b.md is passed to trace_candidates, its fact is listed and exactly one WARNING names the ignore

    Boundaries:
        - Focus: decision X4 (shared inventory step), ADR 0006 Contract 5
        - Fixtures/params: stubbed trace_candidates
        - Scope: extract_facts through engine._inventory

    On failure, first check:
        - The selected_file branch of engine._inventory
    """
    root = _corpus(tmp_path)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    result = extract_facts(root / "b.md", config=Config(), include=["a.md"], exclude=["b.md"])

    assert stub_trace == [("b.md",)]
    assert [fact.path for fact in result.facts] == ["b.md"]
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == ["--include/--exclude ignored for a single-file scan target"]


def test_symlinked_single_file_target_raises_value_error(tmp_path: Path, stub_trace: list[tuple[str, ...]]):
    """
    [Unit] extract_facts: verifies a symlinked single-file target raises ValueError and is never read.

    Scenario:
        Given link.md, a symlink to a.md
        When extract_facts runs on link.md
        Then ValueError names the symlink refusal and trace_candidates is never called

    Boundaries:
        - Focus: decision X4 (same refusal as scan)
        - Fixtures/params: a relative symlink
        - Scope: engine._inventory

    On failure, first check:
        - The is_symlink check in engine._inventory
    """
    root = _corpus(tmp_path)
    (root / "link.md").symlink_to("a.md")

    with pytest.raises(ValueError, match="Symlinked files are not inventoried"):
        extract_facts(root / "link.md", config=Config())
    assert stub_trace == []


def test_unreadable_document_is_counted_and_never_passed_on(tmp_path: Path, stub_trace: list[tuple[str, ...]]):
    """
    [Unit] extract_facts: verifies a non-UTF-8 document is counted in documents_unreadable and withheld from extraction.

    Scenario:
        Given two good documents and one non-UTF-8 document
        When extract_facts runs over the root
        Then documents_unreadable is 1, the document stays in documents, and trace_candidates receives
            only the two good documents

    Boundaries:
        - Focus: decision X12, engine._partition_readable
        - Fixtures/params: stubbed trace_candidates, invalid UTF-8 bytes
        - Scope: extract_facts

    On failure, first check:
        - Whether _traced passes inventory.documents instead of inventory.readable
    """
    root = _corpus(tmp_path)
    (root / "bad.md").write_bytes(b"\xff\xfe not utf-8\n")

    result = extract_facts(root, config=Config())

    assert result.documents_unreadable == 1
    assert [doc.path for doc in result.documents] == ["a.md", "b.md", "bad.md"]
    assert stub_trace == [("a.md", "b.md")]
    assert "bad.md" not in {fact.path for fact in result.facts}


def test_scan_only_settings_do_not_change_the_result(tmp_path: Path, patched_extraction: list[str]):
    """
    [Unit] extract_facts: verifies profile and select in the config do not change the facts.

    Scenario:
        Given the default config and one with profile "deep" and select ["DS1"]
        When extract_facts runs with each
        Then the facts, settings, matches_ds302 and notice are equal

    Boundaries:
        - Focus: decision X3 (profile/select/ignore are not read)
        - Fixtures/params: patched extraction
        - Scope: extract_facts

    On failure, first check:
        - Whether extract_facts started gating on the profile or the rule selection
    """
    root = _corpus(tmp_path)
    scan_only = dataclasses.replace(Config(), profile="deep", select=("DS1",), ignore=("DS302",))

    plain = extract_facts(root, config=Config())
    other = extract_facts(root, config=scan_only)

    assert plain.facts
    assert other.facts == plain.facts
    assert (other.settings, other.matches_ds302, other.notice) == (plain.settings, plain.matches_ds302, plain.notice)


@pytest.mark.parametrize(
    "error",
    [
        ConfigError("fact_check_max_claims_total must be an integer from 1 to 500"),
        OSError(5, "Input/output error"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
    ids=["ConfigError", "OSError", "UnicodeDecodeError"],
)
def test_config_os_and_decode_errors_pass_through_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
):
    """
    [Unit] extract_facts: verifies ConfigError, OSError and UnicodeDecodeError from extraction pass through as-is (E7).

    Scenario:
        Given trace_candidates raising one of the three pass-through types
        When extract_facts runs
        Then the very same exception object propagates (not the type-name RuntimeError)

    Boundaries:
        - Focus: threat model E7 (only other exception types are contained)
        - Fixtures/params: one exception per case
        - Scope: engine._traced

    On failure, first check:
        - The pass-through except clause in engine._traced
    """
    monkeypatch.setattr(engine, "deep_ready", lambda: True)

    def _raise(*args: object, **kwargs: object) -> fact_check.CandidateTrace:
        """Raise the scripted error.

        :param args: Ignored.
        :param kwargs: Ignored.
        :raises Exception: The scripted error.
        """
        raise error

    monkeypatch.setattr(engine, "trace_candidates", _raise)

    with pytest.raises(type(error)) as caught:
        extract_facts(_corpus(tmp_path), config=Config())
    assert caught.value is error


def test_one_huge_entity_and_many_numbers_are_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] extract_facts: verifies a 5,000-code-point entity and 10,000 numbers are capped, the text unchanged (E8).

    Scenario:
        Given one claim with a single 5,000-code-point entity and 10,000 numbers
        When extract_facts runs with a floor of 0
        Then entities holds one item of 200 code points (its prefix), numbers holds the first 32, and the
            text equals the sentence

    Boundaries:
        - Focus: threat model E8
        - Fixtures/params: patched extraction
        - Scope: engine._bounded

    On failure, first check:
        - MAX_FACT_LIST_ITEMS / MAX_FACT_ITEM_CHARS
    """
    monkeypatch.setattr(engine, "deep_ready", lambda: True)
    monkeypatch.setattr(fact_check.nlp, "load_pipeline", lambda: "pipeline")
    entity = "ORG:" + "é" * 4996
    numbers = tuple(str(k) for k in range(10_000))

    def _extract(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Return one claim with the oversized lists.

        :param pipeline: Ignored.
        :param text: The document text.
        :param path: The document path.
        :returns: One claim.
        """
        claim = _claims_for(text, path)[0]
        return (dataclasses.replace(claim, object_entities=(entity,), object_numbers=numbers),)

    monkeypatch.setattr("docsentinel.mining.claims.extract_claims", _extract)
    (tmp_path / "a.md").write_text("Node one holds 3 shards in Q1.\n", encoding="utf-8")

    (fact,) = extract_facts(tmp_path, config=dataclasses.replace(Config(), fact_check_min_salience=0.0)).facts

    assert len(entity) == 5000
    assert fact.entities == (entity[:200],)
    assert fact.numbers == numbers[:32]
    assert fact.text == "Node one holds 3 shards in Q1."
