# Task 01 — Shared candidate collection (C11) and the `extract_facts()` public API

**Parent story:** [Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md)  
**Role:** Python Expert  
**Depends on:** Story 02.0 Tasks 01–03 (`mining/salience.py`, `select_candidates`) and Story 01.0
Task 05 (`detectors/fact_check.py`, `detect()`). If those have not landed yet, this task's
amendments are made in the same change as them.

## Goal

Make one function, `trace_candidates()`, the only way documents become DS302 candidates, and expose
it offline through `engine.extract_facts()`. That function serves both `DS302` and `extract-facts`
(plan contract
[C11](/docs/roadmap/0010-fact-check/plan.md#c11--one-candidate-source-for-ds302-and-extract-facts)).

## Inputs

- The story's [decisions X1–X4, X6–X8, X10–X12](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#decisions)
  and [data contracts](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#data-contracts).
- Plan contracts [C7](/docs/roadmap/0010-fact-check/plan.md#c7--extraction-reuse-no-second-nlp-pipeline)
  and [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends).
- [Story 02.0 Task 03](/docs/roadmap/0010-fact-check/02.0-claim-salience-and-data-mining/03-candidate-selection-and-caps.md)
  (the selection steps this task re-expresses as a trace) and
  [Story 01.0 Task 05](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/05-ds302-registration-and-engine-dispatch.md)
  (step 4.4–4.5, which this task replaces with one call).
- `/src/docsentinel/engine.py` (`scan()`, `_apply_invoker_selection`, `_log_selection`,
  `_partition_readable`), `/src/docsentinel/models.py`, `/src/docsentinel/__init__.py`,
  `/src/docsentinel/mining/nlp.py` (`deep_ready`, `DEEP_EXTRA_HINT`).

## Steps

1. **`mining/salience.py`: trace, then projection.**
   - Extend `ScoredClaim` with `numeric`, `entity`, `distinctiveness`, `cluster_size` and
     `disposition`, and add `DISPOSITIONS`.
   - Add `trace_salience(...)` with the same parameters and validation as `select_salient`. It runs
     Story 02.0 Task 03 steps 2.1–2.8 unchanged, but it keeps every canonical claim and records
     why each one was dropped instead of discarding it:
     - `duplicate`: a cluster member that is not the representative;
     - `below_floor`: a representative with `score < min_salience`;
     - `document_cap`: cut by `max_per_document`;
     - `total_cap`: cut by `max_total`;
     - `selected`: everything else.
   - `cluster_size` is the number of canonical claims sharing the `cluster_id`.
   - Return every entry sorted by `(-score, path, paragraph_index, raw_sentence, raw_subject,
     raw_object)`, which is total because canonicalisation already fixed the input order.
   - Re-implement `select_salient(...)` as
     `tuple(s for s in trace_salience(...) if s.disposition == "selected")`. Its order is unchanged:
     the T5 key is a prefix of the trace key, and two representatives can never tie on T5 because
     identical sentences share a cluster.
   - The DEBUG stage counts move into `trace_salience`, so they are logged once per call.
2. **`detectors/fact_check.py`: policy, candidate fields, trace.**
   - Add `SelectionPolicy` and `DS302_POLICY` built from the existing `_W_*` and `_DEDUP_THRESHOLD`
     constants. Keep them plain floats, so importing the module still never imports
     `mining.salience`.
   - `select_candidates(claims, config, *, policy=DS302_POLICY)` builds `SalienceWeights` from
     `policy.weights` and passes `policy.dedup_threshold`. It now calls `trace_salience` and returns
     `tuple[tuple[CandidateClaim, str], ...]` through a private helper. The public
     `select_candidates` keeps its Story 02.0 return type, the `selected` candidates only.
     `ConfigError` re-validation of the config values is unchanged. A `SelectionPolicy` with
     invalid numbers raises `ValueError` from `SalienceWeights`/`trace_salience`.
   - Extend `CandidateClaim` with the five signal and cluster fields, copied from `ScoredClaim`.
     `text` keeps its Story 02.0 definition: stripped and cut to `MAX_CANDIDATE_CHARS`.
   - Add `CandidateTrace` and `trace_candidates(root, documents, config, *, policy=DS302_POLICY)`.
     It is the single extraction loop:
     - Import `docsentinel.mining.claims` lazily and call `nlp.load_pipeline()`.
     - For each document whose path ends in `.md`, read it with strict UTF-8 and call
       `extract_claims`.
     - Pool the claims and call the private helper.
     - Fill `documents_read` and `claims_extracted`.
     - It reads no environment, resolves no gate and imports no backend.
     - **Amended 2026-11-24 (threat model, E11; follow-up allowed).** The re-read of
       `root / doc.path` after `_partition_readable` must not follow a symlink a local process
       swapped in between the two reads: open with `O_NOFOLLOW` and check `fstat` with `S_ISREG`,
       or reuse the text the partition step already read. One change covers both DS302 and
       `extract-facts`. It may land in a later change; if it does, record the deferral in
       `status.md`.
   - Add `collect_candidates(root, documents, config)`, which returns
     `trace_candidates(root, documents, config).selected`. It has no `policy` parameter.
   - Replace Story 01.0 Task 05 steps 4.4 and 4.5 in `detect()` with
     `candidates = collect_candidates(root, documents, config)`. Gate, backend loading,
     `_check_candidates`, the finding format and the log lines are unchanged. Remove any other
     `extract_claims` call from the module.
3. **`engine.py`: the shared inventory step.**
   - Move the part of `scan()` from `target = Path(root).resolve()` through the `discovered …`
     INFO line into `_inventory(root, config, include, exclude) -> _Inventory`. `_Inventory` is a
     private frozen dataclass with `directory`, `settings`, `documents`, `readable`, `unreadable`
     and `skipped`.
   - `scan()` calls `_inventory` and continues unchanged. This must be a pure move: no message,
     level or order change. Every existing engine, CLI and logging test passes unmodified.
4. **`engine.py`: `extract_facts(...)`** with the signature in the story data contracts.
   1. Call `check_invoker_selector_shape`, then `_inventory(...)`. This gives the same errors,
      WARNINGs, the `EMPTY_SELECTION_MESSAGE` `ConfigError`, single-file handling and unreadable
      skips as `scan()`.
   2. If `not deep_ready()`, raise
      `RuntimeError(f"extract-facts needs the deep extras and the spaCy model - {DEEP_EXTRA_HINT}")`
      before any extraction.
   3. Apply the overrides that are not `None` with `dataclasses.replace(settings, ...)` on
      `fact_check_min_salience`, `fact_check_max_claims_per_document` and
      `fact_check_max_claims_total`. Build `policy` from `weights`/`dedup_threshold`, falling back
      to `DS302_POLICY` field by field. Validate `weights` as a 3-tuple of finite non-`bool`
      numbers; anything else is a `ValueError`. `include_rejected` must be a `bool`, else
      `ConfigError`, mirroring `use_external_api`.
      **Amended 2026-11-24 (threat model, E6).** All of this validation runs **before** step 4.2,
      so before `deep_ready()` and `load_pipeline()`, and an invalid value never costs an
      extraction run. Validate the three overrides with the same validator `config.py` applies to
      those keys, `weights` by constructing `SalienceWeights`, and `dedup_threshold` with the same
      unit-interval check `trace_salience` applies. NaN and infinity are refused everywhere. Reuse
      those validators rather than writing new ones, so X6's "no second validator" still holds;
      the re-validation in `select_candidates` stays as defence in depth.
   4. Call `trace_candidates(directory, readable, settings, policy=policy)` and map each entry to
      `ExtractedFact`. Keep only `selected` entries unless `include_rejected`. `rank` is the 1-based
      index in the listed order, and `text` is `CandidateClaim.text` verbatim.
      **Amended 2026-11-24 (threat model, E8).** `ExtractedFact.numbers` and `entities` keep at most
      the first 32 items of `Claim.object_numbers`/`object_entities`, each cut to at most 200 code
      points (private engine constants, for example `_MAX_FACT_LIST_ITEMS = 32` and
      `_MAX_FACT_ITEM_CHARS = 200`). These are preview-only fields that DS302 never sends, so C11 is
      unaffected; `text` is never cut further.
   5. `matches_ds302` is `policy == DS302_POLICY` and each of the three effective values equals the
      value in the pre-override settings.
   6. `notice` is built from engine constants only (trusted). For example:
      `"Heuristic, offline claim extraction; no network call was made and nothing was verified. "`
      followed by either
      `"The selected facts are the claims DS302 would send for this configuration."` or
      `"Settings differ from DS302 (<comma-separated setting names>); DS302 would send a different set."`
      The names come from a fixed vocabulary, never from input.
      **Amended 2026-11-24 (threat model, E12).** The matching sentence states the conditions
      under which it holds. Replace it with:
      `"The selected facts are the claims DS302 would send, at most and in this order, if it ran with both gates open on the same configuration and selection, with DS302 among the active rules; fact_check_time_budget_seconds can stop it earlier."`
      Each sentence is a module-level constant, so a test can pin the exact text.
   7. Log at INFO with counts only:
      `extract-facts: <d> documents read, <c> claims, <s> selected, <l> listed (policy <ds302|custom>)`.
      Never log claim text. Paths appear only through the shared step's existing `safe()` lines.
   8. The function never reads `profile`, `select`, `ignore`, `baseline` or `deep_confirm`, and
      never reads `os.environ` itself.
      **Amended 2026-11-24 (threat model, E1).** It never imports a backend module
      (`docsentinel.fact_check.lenz` or any `FACT_CHECK_BACKEND_MODULES` value), constructs no HTTP
      client, and opens no socket. No DocSentinel code on its call graph names `httpx`. spaCy
      imports `httpx` itself during `load_pipeline()`, so `"httpx" in sys.modules` is expected and is
      not a defect.
   9. **Added 2026-11-24 (threat model, E7): extraction-error wrapper.** Inside `extract_facts`, any
      exception from `trace_candidates` other than `ConfigError`, `OSError` or `UnicodeDecodeError`
      is replaced by `RuntimeError(f"extract-facts: claim extraction failed ({type(exc).__name__})")`.
      Raise it **outside** the `except` block, so it has no `__cause__` and no `__context__`, and log
      it without `exc_info`. spaCy, textacy and scikit-learn exceptions can carry document tokens;
      this mirrors gating M5. `scan()` is unchanged.
5. **`models.py`.** Add `ExtractedFact`, `FactSettings` and `FactExtractionResult` as frozen
   dataclasses, stdlib only, with `:ivar` docstrings. `selected` is a property.
6. **`__init__.py`.** Export `extract_facts`, `ExtractedFact`, `FactSettings` and
   `FactExtractionResult`, and update the module docstring. `scan` keeps its identity.
7. Report a `Docs impact:` line (triggers P and A) and a `Diagram impact:` line naming
   `component-detectors.puml` (shared `trace_candidates` used by `DS302` and `engine.extract_facts`)
   and `component-overview.puml`.

## Deliverables

- `/src/docsentinel/mining/salience.py`
- `/src/docsentinel/detectors/fact_check.py`
- `/src/docsentinel/engine.py`
- `/src/docsentinel/models.py`
- `/src/docsentinel/__init__.py`

## Acceptance criteria

- [ ] `select_salient` equals the `selected` projection of `trace_salience` for every Story 02.0 unit
      case and for the 200-claim generated corpus. Every Story 02.0 test passes unmodified except
      for `ScoredClaim` constructor calls that gain the new fields.
- [ ] Each canonical claim appears in the trace exactly once, with one disposition from
      `DISPOSITIONS`, and `cluster_size >= 1`.
- [ ] `detectors/fact_check.py` contains exactly one `extract_claims` call, inside `trace_candidates`.
      `detect()` calls `collect_candidates`, and `collect_candidates` has no `policy` parameter.
- [ ] Importing `docsentinel` and `docsentinel.detectors.fact_check` still imports neither
      `mining.salience`, `mining.clustering`, `sklearn` nor `httpx` (fresh interpreter).
- [ ] `scan()` behaviour and logs are byte-identical to master. The full suite is green with no test
      edited for the refactor.
- [ ] `extract_facts()` raises exactly as documented. With defaults, its `facts` texts equal
      `[c.text for c in collect_candidates(directory, readable, settings)]`.
- [ ] `trace_salience`, `SelectionPolicy` and `extract_facts` are fully typed. ruff is clean, and the
      code follows `/docs/dev/python_coding_standard.md`.

## Test expectations

Written in [Task 04](./04-fixtures-and-tests.md). Run
`uv run pytest tests/unit tests/mock -q -k "mining or fact_check or extract_facts" -p docsentinel.pytest_plugin`
and the full suite.

## Out of scope

- Rendering and templates (Task 02), the CLI (Task 03).
- Line numbers (owner question O2), any change to `Claim` or `extract_claims`.
- A `policy` that `DS302` could receive.
