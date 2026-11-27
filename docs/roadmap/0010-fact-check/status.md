# Milestone 0010 — completion status

**Planning state:** ✅ Complete (5 of 5 stories, 2026-11-24). ADR 0007 is still `Proposed`
pending owner sign-off. Execution order was 01.0 → 02.0 → 05.0 → 03.0 → 04.0 (see
[plan.md](/docs/roadmap/0010-fact-check/plan.md#stories)).

**Reopened 2026-11-25 (owner request):** one additional story, 06.0 (optional AI-assisted
statement rewrite), added. Specification only, no code yet. The five original stories above remain
complete and unchanged; see the dated entry below.

## Current status

| Story | Name | State | Tests executed |
|---|---|---|---|
| 01.0 | Backend Protocol and rule contract | ✅ Complete (2026-11-24) | suite 5392 passed; review LGTM |
| 02.0 | Claim salience and data-mining filter | ✅ Complete (2026-11-24) | suite 5525 passed + 2 env fixes; review LGTM |
| 03.0 | Lenz backend client | ✅ Complete (2026-11-24) | suite 5939 passed; review LGTM |
| 04.0 | Fixtures, tests and docs | ✅ Complete (2026-11-24) | full suite green; docs sync done |
| 05.0 | `extract-facts` CLI command | ✅ Complete (2026-11-24) | suite 5714 passed; review LGTM |
| 06.0 | Optional AI-assisted statement rewrite (added 2026-11-25) | ⬜ Not started | — |

Legend: ⬜ Not started · 🔶 In progress · ✅ Complete.

**Exit gates (2026-11-24):** `uv lock --check` ✅; full suite under `uv run --locked` ✅ (after
one lint fix, rerun below); fast self-scan exit 0 with zero DS302 findings ✅; standard
self-scan with `.docsentinel-standard-baseline.json` exit 0 ✅; `uv build` ✅ (wheel ships
`fact_check/lenz.py` and both facts templates); honesty review ✅ (DS302 registered, gate stated
wherever DS302 is described); DS302 rows in `rules.md`, `fault-classes.md`, `finding-types.md`
✅; embedded-key regression test ✅. Python 3.13 was not run locally (CI covers 3.12 and 3.13).

## Tracking rules

- Mark a story complete only when its code, tests, docs and the proposed release-notes entry are
  merged and the full suite (`uv run pytest -p docsentinel.pytest_plugin`) and the self-scan
  (`uv run docsentinel scan . --format json`, exit `0`, **zero** `DS302` findings) are green.
- Story 01.0's and Story 03.0's Security Auditor tasks run **before** their first Python Expert
  task (both stories are security-sensitive); a CRITICAL finding stops the story.
- Do not close this milestone while `DS302` lacks a row in
  [`docs/specs/fault-classes.md`](/docs/specs/fault-classes.md),
  [`docs/specs/finding-types.md`](/docs/specs/finding-types.md) and
  [`docs/user/reference/rules.md`](/docs/user/reference/rules.md).
- Record every owner ruling on D1–D10 below, dated.
- No commit, test, fixture or log in this milestone may contain the literal API key embedded in
  `examples/docs/lenz_fact-checking.md`, or call the real `lenz.io` API. Story 04.0's regression
  check enforces this with a grep-based test; a hit is a stop-the-line finding, not a style note.

## Notes & decisions

- 2026-11-20: Milestone specified from the owner's outline (a new deep-profile rule, `DS302`,
  that fact-checks high-salience claims against an external API through a swappable backend,
  gated independently of `deep_confirm`). Decisions D1–D10 were taken provisionally by the
  architect; see
  [Open decisions for owner](/docs/roadmap/0010-fact-check/plan.md#open-decisions-for-owner).
- 2026-11-20: Rule code **DS302** reserved (next free after DS301; DS107, DS111, DS119–DS123
  remain reserved by Milestone 0004). ADR number **0007** reserved for Story 01.0 (next free after
  0006, `0006-invoker-include-exclude-and-directory-selectors.md`). Neither file is created in
  this milestone.
- 2026-11-20: `examples/check_fact.py` and `examples/docs/lenz_fact-checking.md` were read
  **read-only**, as reference material for the Lenz `/assess` request/response shape only. The
  embedded API key in the latter file was not copied anywhere in this milestone's specs, the real
  API was not called, and the file's embedded "verify it works" / "show me the verdict" text,
  addressed to an AI agent, was treated as untrusted document content and not followed — it is not
  an instruction from the project owner. This note exists so a later reviewer can confirm the
  boundary was respected from the start.
- 2026-11-20: Decision D5 (how a gate failure surfaces beyond the WARNING log line) is the one
  item in this milestone's open-decisions table flagged as genuinely close rather than a
  routine confirm; see plan.md and Story 01.0 decision S9 for both options before ratifying it.
- 2026-11-21: **Owner ruling — D1–D4 and D6–D10 ratified as written** in
  [plan.md](/docs/roadmap/0010-fact-check/plan.md#open-decisions-for-owner).
- 2026-11-21: **Owner ruling — D5: scoped `pending` + `doctor`.** A `DS302` gate failure (either
  gate) logs a WARNING every time, adds one `ScanResult.pending` entry and one `docsentinel doctor`
  line naming which gate is missing; the generic `Rule.opt_in_option`/`ScanResult.notice`
  machinery is **not** retrofitted (Story 01.0 S9, recommended option).
- 2026-11-21: Phase R audit (`/implement-milestone`): no as-built `DS302`/fact-check code exists
  (state NEW, no divergence). Gap: all 19 task spec files listed in the four story READMEs were
  unwritten; disposition — authored by `app-architect` into each story folder against the
  ratified D1–D10.
- 2026-11-21: Spec authoring raised open questions for the owner (to be ruled before Story 01.0
  task 01, the ADR): Q1 whether `DS302` counts as "evaluated" in `ScanResult.notice` while a gate is
  closed; Q2 the finding message embeds backend confidence, making the baseline fingerprint
  run-unstable; Q3 no global time budget (worst case 500 claims × 30 s); Q4 whether an unrecognised
  Lenz verdict yields a `mixed` finding; Q5 `examples/docs/lenz_fact-checking.md` carries a
  committed API key — rotation/removal is out of this milestone's scope. Provisional values in the
  specs (salience weights 0.3/0.3/0.4, unknown-verdict confidence band 0.35–0.65, `trust_env`
  deferred to the 03.0 egress review) are proposals, not decisions.
- 2026-11-21: **Owner decision — mining layer (`src/docsentinel/mining/`), applied as plan contract C9.** Salience scoring and clustering become pure, `Config`-free mining modules `mining/salience.py` and `mining/clustering.py` (two modules: clustering is text-generic, salience is `Claim`-aware); `select_candidates(claims, config)` is a thin wrapper in `detectors/fact_check.py` that re-validates the `Config`, holds the fixed policy constants (weights, `0.92`) and the 1,000-character bound, and never reorders, so the `(-score, path, paragraph_index, raw_sentence)` order and tie-breaks stay in `mining.salience.select_salient`; clustering reuses the `mining/corpus.py` vectorizer factory (promoted to public `create_vectorizer()`), not the cached `build_corpus_model()`; the Protocol and Lenz client move to a new `docsentinel.fact_check` package (`fact_check/protocol.py`, `fact_check/lenz.py`; network I/O is not mining, a backend is not a rule analyzer) with its own tripwire `tests/unit/test_fact_check_layering.py`; references to `_triples`/`deep_support`/`detectors/standard/corpus` now name `mining/claims.py`/`mining/nlp.py`/`mining/corpus.py`. Dispositions: plan.md amended; status.md amended; 01.0 README amended, 01 amended, 02 unchanged, 03 amended, 04 amended, 05 amended, 06 amended; 02.0 README amended, 01 amended, 02 amended, 03 amended, 04 amended; 03.0 README amended, 01 unchanged, 02 amended, 03 amended, 04 amended; 04.0 README amended, 01 unchanged, 02 amended, 03 unchanged, 04 amended, 05 amended. Open question Q6: `tests/unit/test_mining_layering.py` must allow intra-layer `docsentinel.mining.*` imports (`salience` -> `clustering` -> `corpus`, `salience` -> `claims`), and should also deny `httpx` and `docsentinel.fact_check` explicitly.
- 2026-11-21: **Owner ruling — Q1–Q4 (recommended options).** Q1: while either gate is closed,
  `DS302` is **not** counted as evaluated in `ScanResult.notice`. Q2: backend confidence is carried
  in report-only `Finding` fields (`compare=False`), never in `message`, so baseline fingerprints
  are run-stable. Q3: a per-scan overall time budget is added; claims remaining when it is
  exhausted are skipped with one WARNING. Q4: an unrecognised backend verdict is skipped with a
  WARNING, never mapped to `mixed`. Q5 (committed key in `examples/`) stays out of scope; owner
  advised to rotate and remove it.
- 2026-11-21: Story 01.0 Task 01 done: [ADR 0007](/docs/adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md)
  written (`Proposed`), index row added. Q1–Q4 realised as ADR Contracts 6–9 and plan contract C10
  (Q3 key `fact_check_time_budget_seconds`, int, default 300, 1–3600, monotonic). Specs amended:
  plan.md (status line, C4, new C10); 01.0 README, 02, 03, 05, 06; 02.0 README, 03; 03.0 README,
  01, 02, 04; 04.0 README, 02, 03, 04, 05. New owner points O1 (verdict in `message` makes a
  verdict flip change the fingerprint) and O2 (composite `value` vs a dedicated
  `Finding.confidence` field) are in the ADR's Open questions.
- 2026-11-23: **Owner request — Story 05.0 `extract-facts` added.** The owner asked for "CLI command
  `extract-facts` that accept documents and settings for the algorithm … reduce document to a group
  of verifiable facts using non-LLM data mining algorithms … the one that used in `DS302`".
  - Authored [Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md) with four
    tasks: shared collection and public API, facts template context, the CLI command, and tests.
  - New plan contract **C11**: `trace_candidates()`/`collect_candidates()` in
    `detectors/fact_check.py` is the single candidate source for `DS302` and `extract-facts`;
    `select_salient()` becomes the projection of a new `trace_salience()`.
  - Dependencies: 05.0 depends on 01.0 and 02.0 (not 03.0). 04.0 now depends on 05.0. The order is
    01.0 → 02.0 → 05.0 → 03.0 → 04.0, and 05.0 and 03.0 may run in parallel.
  - New exit gate 9. The plan Out-of-scope item on "inspecting what was sent" is narrowed to past
    sends.
  - Dispositions:
    - plan.md amended (Stories, order, C11, Diagrams, exit gates 1 and 9, Out of scope, status
      line);
    - 01.0 Task 05 amended (steps 4.4–4.5 become `collect_candidates`);
    - 02.0 README and Task 03 amended (`trace_salience`, signal fields, `SelectionPolicy`);
    - 04.0 README, Task 02 (step 10, the C11 equality test), Task 04 (`cli.md`,
      `report-template-format.md`, `custom-reports.md`, CLAUDE.md, release notes) and Task 05
      (diagram items) amended;
    - [ADR 0007](/docs/adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md) gains an
      "Amendment 2026-11-23" section (still `Proposed`).
  - Provisional decisions X1–X12 are in the story README. Open owner questions:
    - **O1**: CLI-only exploration flags `--weights`/`--dedup-threshold`. Recommended: keep them,
      marked non-DS302.
    - **O2**: line numbers need an additive `Claim.line`, a change to the extraction that is out of
      scope. Recommended: defer to a follow-up and ship with `paragraph_index`.
    - **O3**: confirm the narrowed Out-of-scope item.
    - **O4**: the additive template `context` key also amends the Milestone 0007 format contract and
      ADR 0003 (still `Proposed`). Recommended: accept, since it is additive and defaults to
      `report`.
- 2026-11-23: **Owner ruling on Story 05.0 O1–O4: all recommended options.** O1 keep the CLI-only
  `--weights`/`--dedup-threshold` exploration flags (never a config key, never read by DS302;
  output marked `matches_ds302: false`). O2 defer line numbers; facts carry the paragraph index.
  O3 the Out-of-scope "no inspection surface" item covers only claims already sent. O4 accept the
  additive template `context` key as an amendment to the Milestone 0007 format contract and
  ADR 0003 (recorded in Story 05.0 Task 02, applied when that task lands).
- 2026-11-23: **Story 01.0 Task 02 complete — threat model**
  [threat-model-0010-fact-check-gating-2026-11-23](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md),
  verdict PASS_WITH_FOLLOWUP (no CRITICAL). HIGH FC-5: key disclosure through an uncaught
  backend/transport exception (httpx/h11 header errors carry the `Bearer` value) -> M5, re-raise
  with the type name only and no chain. MEDIUM FC-3, FC-4, FC-10. Mitigations M1–M12 each map to a
  test; the spec amendments they require in Tasks 03–06 are applied by app-architect (2026-11-23).
- 2026-11-23: **Story 01.0 Task 03 complete** (task-verifier PASS). Six `fact_check_*` keys,
  `FACT_CHECK_BACKEND_NAMES`, `--use-external-api` on `scan`/`baseline`, `rules.EXTERNAL_API_RULES`,
  the `rules` suffix path and a no-op `scan(use_external_api=False)` keyword (wired in Task 05).
  Suite 5111 passed / 17 skipped; self-scan exit 0. Dispositions (owner standing instruction:
  take the recommended option): the `doctor` `fact-check gate:` line moves to Task 05 (it needs
  `resolve_external_api_gate`); the criterion "`doctor` does not import `httpx`" is reworded to
  "`import docsentinel`, `rules` and `doctor` never import a `docsentinel.fact_check` backend
  module; `import docsentinel` and `rules` do not import `httpx`", because spaCy itself imports
  `httpx` in the pre-existing deep-readiness probe.
- 2026-11-23: **Story 01.0 Task 04 complete** (task-verifier PASS). New `docsentinel.fact_check`
  package (`__init__.py` docstring only, stdlib-only `protocol.py`: `FactCheckClient`,
  `FactCheckResult`, `FactCheckError`, `VERDICTS`, `FACT_CHECK_BACKEND_MODULES`,
  `FACT_CHECK_BACKENDS`, `load_backend`). `load_backend` imports through a fixed per-backend
  literal importer (importlib tripwire allowlist entry); `load_backend("lenz")` raises
  `ImportError` until Story 03.0. Drift test vs `config.FACT_CHECK_BACKEND_NAMES` landed early.
  Suite 5181 passed / 17 skipped. Rulings (recommended option): no `-> None` annotations (project
  lint rule wins over the spec's "fully typed"); M8's ban is on a standalone `LENZ_API_KEY`
  (Task 06 spec amended), since the C3 name contains it.
- 2026-11-23: **Story 01.0 Task 05 complete** (task-verifier PASS; security-auditor post-code
  review PASS_WITH_FOLLOWUP). `detectors/fact_check.py` (gate helper, `ExternalApiGate`,
  `detect()`, `collect_candidates` seam returning `()` until Story 02.0, `_check_candidates`),
  DS302 registered (deep, advisory), engine `use_external_api` validation/forwarding/`pending`,
  `doctor` `fact-check gate:` line (deferred from Task 03), DS302 rows in `rules.md`,
  `fault-classes.md`, `finding-types.md`. Suite 5221 passed / 17 skipped; self-scan exit 0, no
  DS302 finding. Rulings (recommended option): an open gate whose backend cannot load counts as
  closed (honesty; ADR 0007 amendment); the auditor's MEDIUM (a `FactCheckError` message logged
  via `safe(str(exc))` could echo a `Bearer` value) fixed in the main session: type name only,
  plus regression test `test_factcheckerror_message_never_reaches_the_log`. LOW items accepted:
  `doctor` imports the backend (and `httpx`) only when the flag env and a key are both set; a
  malformed runtime-registered backend name raises `ValueError` (trusted code only).
- 2026-11-24: **Story 01.0 Task 06 complete.** M1–M12 each have a test (new unit
  `test_fact_check_{layering,env_reads,repo_hygiene,env_isolation}.py`, mock
  `test_fact_check_{no_key_logged,import_isolation}.py`, integration
  `test_fact_check_gate_off_ds302.py`, assets `tests/assets/ds302/gate_off_no_flag/`, shared fake
  `tests/fact_check_fakes.py`). With `en_core_web_sm` now installed, 8 earlier deep tests that had
  been skipping failed against the ratified DS302 behaviour; their expectations were updated (DS301
  tests select only DS301; whole-profile tests expect DS302 and its gate WARNING). Three more
  exposed a **pre-existing DS301 bug**: textacy 0.13 trims an SVO object to its head noun, so
  `object_numbers` lost "100" in "holds 100 entries"; fixed in `mining/claims.py` by reading
  numbers/entities from the object's dependency subtree (`raw_object` unchanged).
- 2026-11-24: **Story 05.0 threat model**
  [threat-model-0010-extract-facts-2026-11-24](/docs/security/threat-model-0010-extract-facts-2026-11-24.md),
  verdict PASS_WITH_FOLLOWUP (no CRITICAL). HIGH F1: spaCy itself imports `httpx`, so the specified
  "`httpx` absent from `sys.modules`" proof can never pass; the offline invariant becomes no backend
  module, no `httpx` reference in DocSentinel code on the path, and no outbound socket (E1).
  MEDIUM F2-F4 (name-only directory template listing, `##[` JSON escape, one `schema_for` plus an
  engine-level context check) must land in Task 02 before merge; E5-E10, E12, E13 land with their
  tasks; E11 (no-follow re-read) may follow later. Spec amendments applied by app-architect,
  marked "Amended 2026-11-24 (threat model)": 05.0 README (X10, data contracts, facts context
  table, security notes, acceptance criterion 7, test plan), Task 01 (steps 2, 4.3, 4.4, 4.6,
  4.8, new 4.9 for E7), Task 02 (steps 1-5, acceptance), Task 03 (steps 2.6, 3, 5, acceptance),
  Task 04 (steps 3-6, step 8 assertion replaced); one-line corrections in plan.md C11 and the
  ADR 0007 2026-11-23 offline-extraction amendment. The `doctor` directory-template line is
  renamed to `templates (report_templates_dir): …` per E2, an intended exception to the
  byte-identical `doctor` criterion.

### Story 01.0 - Backend Protocol and rule contract (✅ 2026-11-24)

**Delivered**
- ADR 0007 (Proposed, amended 2026-11-23 twice) and threat model
  `threat-model-0010-fact-check-gating-2026-11-23.md` (PASS_WITH_FOLLOWUP, M1–M12).
- Six `fact_check_*` keys; `--use-external-api` on `scan`/`baseline`; `scan(use_external_api=)`.
- `docsentinel.fact_check.protocol` (`FactCheckClient`, `FactCheckResult`, `FactCheckError`,
  static backend registry, `load_backend`).
- `detectors/fact_check.py`: gate helper (`ExternalApiGate`, backend availability closes the
  gate), `detect()`, `collect_candidates` seam (empty until Story 02.0), send loop with time
  budget, type-name-only containment; DS302 registered (deep, advisory); `pending`, evaluated-count
  exclusion, `rules` suffix, `doctor` `fact-check gate:` line; DS302 rows in `rules.md`,
  `fault-classes.md`, `finding-types.md`.

**Tests / gate**
- Full suite 5392 passed / 2 skipped; ruff clean; self-scan exit 0 with no DS302 finding.
- task-verifier PASS on Tasks 03, 04, 05; security-auditor post-code PASS_WITH_FOLLOWUP (MEDIUM
  fixed); feature-reviewer LGTM. Review follow-ups: `isinstance(exc, KeyboardInterrupt)` applied;
  per-request timeout already in Story 03.0 Task 02 (`REQUEST_TIMEOUT_SECONDS = 30.0`); the
  notice names DS302 only through `pending` (accepted); `doctor` importing the backend when both
  gates are set is noted for Story 04.0 docs; the docs-updater pass runs once at Story 04.0.

**Reconciliation note**
- Task 03 step 5 (`doctor` line): consumed by Task 05. Task 03 "`doctor` imports no `httpx`":
  superseded by the reworded criterion (spaCy imports `httpx`). Task 06's "fully typed"
  `-> None`: superseded by the project lint rule. ADR 0007 Contract 6: superseded by the
  backend-availability ruling.
- 2026-11-24: **Story 02.0 Tasks 01–02 complete** (task-verifier PASS, run in parallel).
  `mining/salience.py` (signals, `SalienceWeights`, `combined_score`, clamped to [0, 1]),
  `mining/clustering.py` (`cluster_near_duplicates`, `TextCluster`, additive `cluster_sizes()`
  for Story 05.0; similarities rounded to 12 places so the strict `>` is chunk-independent),
  `_W_*` constants in `detectors/fact_check.py`. Task 03 (`select_salient`, `select_candidates`)
  implemented; it re-validates three numeric keys (the spec's "four" lists three; Q3 excludes the
  time budget). `trace_salience`/`trace_candidates` stay with Story 05.0 Task 01.

### Story 02.0 - Claim salience and data-mining filter (✅ 2026-11-24)

**Delivered**
- `mining/salience.py`: `token_count`, `numeric_density`, `entity_density`, `SalienceWeights`,
  `combined_score`, `ScoredClaim`, `select_salient` (private steps `_canonical`,
  `_score_canonical`, `_representatives`, floor, caps, ready to back Story 05.0's
  `trace_salience`).
- `mining/clustering.py`: `TextCluster`, `cluster_near_duplicates` (TF-IDF via
  `mining.corpus.create_vectorizer()`, chunked sparse cosine, union-find, distinctiveness),
  `cluster_sizes()`.
- `detectors/fact_check.py`: `_W_*` weights, `_DEDUP_THRESHOLD = 0.92`, `CandidateClaim`,
  `select_candidates`, and `collect_candidates` now feeds DS302 real candidates.

**Tests / gate**
- task-verifier PASS on Tasks 01, 02, 03; Task 04 added the missing criteria tests (exact
  scores, AST layering, cross-hash-seed determinism, factory-only vectorizer, real-wrapper floor,
  dedup and cap order). feature-reviewer LGTM.
- Full suite 5525 passed / 2 failed / 2 skipped, both failures resolved: the timing test passes on
  rerun (load flake); the oracle-parity test scanned a stray Claude worktree, so
  `.claude/worktrees/*` joins the `docsentinel.toml` exclude list. Lazy imports moved to
  allowlisted `importlib.import_module` literals (tripwire + lint X006).
- Review MEDIUMs applied: a similarity block is capped at 4,000,000 cells
  (`_MAX_BLOCK_CELLS`), and pairs are masked to the upper triangle before the Python union loop
  (3,500 claims incl. 500 duplicates cluster in 0.67 s). LOW items accepted: a stop-word-only
  sentence scores distinctiveness 1.0 and is not clustered with its copies (its numeric and
  entity densities are 0, so it rarely clears the floor); the re-read `UnicodeDecodeError`
  matches DS301.

**Reconciliation note**
- Task 03's "four numeric values" lists three; three are re-validated (Q3 keeps the time budget
  out). `trace_salience`/`trace_candidates` and the extra fields moved to Story 05.0 Task 01.
- 2026-11-24: **Story 05.0 Task 01 implemented** (verification running): `trace_salience` (with
  `select_salient` as its `selected` filter, identical on 432 scratch cases), `trace_candidates` as
  the one candidate source for DS302 and `extract_facts()`, `engine._inventory` shared with
  `scan()`, public `extract_facts`, `ExtractedFact`, `FactSettings`, `FactExtractionResult`.
  Threat-model mitigations E1, E6–E9, E12 applied. Ruling (recommended option): the E2 `doctor`
  rename `templates (report_templates_dir): …` is an accepted exception to byte-identical `doctor`.
- 2026-11-24: **Story 05.0 Task 01 complete** (task-verifier PARTIAL -> fixed in the main session:
  the E12 notice tail now ends "..., with DS302 among the active rules;
  fact_check_time_budget_seconds can stop it earlier.", pinned by the exact-string test).
- 2026-11-24: **Story 05.0 Task 02 complete** (task-verifier PASS; security-auditor post-code
  PASS_WITH_FOLLOWUP). Template `context` key (`report` default, `facts`), `telemetry/facts_model.py`,
  packaged `facts-text`/`facts-json`, `render_facts()`, `render_template(model_kind=)` (named so
  because `context` is already that function's data parameter), §6a in
  `docs/specs/report-template-format.md` (O4). The auditor's MEDIUM (CWE-116: the `json` filter
  let `##[` through to a text sink, in both contexts) fixed in the main session: `_filter_json`
  writes `##[` as `##\u005b` (lossless, JSON has no `#` token), with regression test
  `test_json_filter_escapes_legacy_marker_losslessly`. LOW accepted: U+2060 and U+E0041 reach
  `facts-text` flagged and marked (E5), RR3 stays open. Task 03 implemented (`extract-facts`;
  manual run over `examples/docs` exit 0, 7 facts selected from 83 claims in 5 documents).
  Ruling (recommended option): the `doctor` fact-templates line stays sorted
  (`facts-json, facts-text`); Task 03 spec amended.
- 2026-11-24: **Story 05.0 Task 03 complete** (task-verifier PASS; E7/E10/E13 CLI behaviour is pinned by Task 04 tests).
- 2026-11-24: **Story 05.0 Task 04 complete.** ~114 tests: E1 socket guard in a fresh `python -I`
  interpreter (consent env and a sentinel key set; non-vacuous), AST offline check, C11 equality
  `tests/integration/test_fact_check_extract_facts_equivalence_ds302.py` (a gate-open DS302 scan's
  recording fake backend receives exactly the default `extract-facts` texts, same order, three
  configs, library and CLI), assets `tests/assets/ds302/extract_facts_basic/`. Full suite 5714
  passed / 2 skipped; ruff clean; self-scan exit 0. E11 (no-follow re-read) stays a recorded
  follow-up.

### Story 05.0 - `extract-facts` CLI command (✅ 2026-11-24)

**Delivered**
- `mining.salience.trace_salience` (every claim with its disposition and signals;
  `select_salient` is its `selected` filter), `detectors.fact_check.trace_candidates` (the one
  candidate source of DS302 and `extract-facts`, C11), `DS302_POLICY`.
- `engine.extract_facts()` sharing `_inventory` with `scan()`; public `ExtractedFact`,
  `FactSettings`, `FactExtractionResult`; notices for "matches DS302" and "settings differ".
- Template `context` key (`report`/`facts`), `telemetry/facts_model.py`, packaged
  `facts-text`/`facts-json`, `reporting.render_facts()`, report-template-format §6a (O4).
- `docsentinel extract-facts` (`--min-salience`, `--max-per-document`, `--max-total`, CLI-only
  `--weights`/`--dedup-threshold`, `--all`, `--format`, `-o`, include/exclude, `--config`,
  `--no-user-settings`; exit 0 or 2); `scan --format facts-*` points at `extract-facts`;
  `doctor` `fact templates (packaged):` line.

**Tests / gate**
- Threat model `threat-model-0010-extract-facts-2026-11-24.md` PASS_WITH_FOLLOWUP (E1–E13).
- task-verifier: Task 01 PARTIAL -> fixed (E12 notice), Tasks 02, 03 PASS; security-auditor
  post-code review of the template change PASS_WITH_FOLLOWUP (MEDIUM `json`-filter `##[` fixed
  for both contexts); feature-reviewer LGTM.
- Full suite 5714 passed / 2 skipped; ruff clean; self-scan exit 0; `uv build` ships both facts
  templates.
- Review suggestions: the `OSError` branch keeps the CLAUDE.md convention (ERROR with traceback to
  the log file only, as `scan` does); the library `extract_facts()` checks the selection before
  deep readiness (the CLI checks readiness first) and `rank` under `--all` counts listed entries,
  both carried to Story 04.0 docs.

**Reconciliation note**
- Task 03 `doctor` order: superseded by the sorted listing. E11 (no-follow re-read): open
  follow-up. "Offline = no `httpx`": superseded by "no backend module, no socket" (F1).

- 2026-11-24: **Story 03.0 Task 01 complete — egress threat model**
  [threat-model-0010-fact-check-egress-2026-11-24](/docs/security/threat-model-0010-fact-check-egress-2026-11-24.md),
  PASS_WITH_FOLLOWUP. HIGH EG-4 (a per-request deadline does not bound a hung call -> hard
  deadline on a daemon thread), EG-5 (decompression bomb through `iter_bytes()` -> identity
  encoding, raw-byte cap via `iter_raw`), EG-7 (key header injection, exception text, chains and
  `httpcore` traces). Mitigations E1–E13 (egress numbering); spec amendments to Tasks 02–04 applied
  by app-architect.
- 2026-11-24: **Story 03.0 Tasks 02–03 complete.** `fact_check/lenz.py` `LenzFactCheckClient`
  (fixed `ASSESS_URL`, no redirects, `trust_env=False`, daemon-thread hard deadline, identity
  encoding and raw-byte cap via `iter_raw`, strict JSON, fixed-message chainless
  `FactCheckError`s, idempotent `close()`); task-verifier PASS; security-auditor post-code review
  PASS_WITH_FOLLOWUP (probes: hung handler fails at 0.20 s, `gzip`/`br` refused, NaN/`1e999`/
  5000-digit/30k-deep JSON refused, a 302 is not followed, no key in any log level). The LOW
  duplicate-JSON-key item fixed in the main session (`object_pairs_hook`); LOWs accepted: other
  worker exceptions keep their text (DS302 logs only the type name), confidence 7 clamps to 1.0
  per spec, a cookie-clear race with an abandoned worker (cookies only go to lenz.io). Task 03:
  `httpx>=0.28,<1` declared (lock: httpx 0.28.1, h11 0.16.0, httpcore 1.0.9; no h2, brotli,
  zstandard or socksio), the registration line `FACT_CHECK_BACKENDS["lenz"]` added in the main
  session at the end of `lenz.py`, `doctor` with both gates prints `on (backend: lenz)`, a
  gate-closed deep scan leaves `lenz` unloaded (socket guard counts connects, lookups and sends).
  Self-scan DS116 hits on two dot-dot path code spans in this session's docs reworded. Note: `uv sync
  --locked` removes the `en_core_web_sm` wheel, which was reinstalled.
- 2026-11-24: **Story 03.0 Task 04 complete** (220 cases across `test_lenz_client_transport.py`,
  `test_lenz_client_no_secret_leak.py`, `test_lenz_verdict_normalization.py`,
  `test_lenz_client_static.py`, `test_lenz_import_isolation.py`; session-wide network guard and
  `lenz_module` fixture in `tests/conftest.py`; five deliberate `lenz.py` mutations each caught).
  Story 03.0 feature-reviewer LGTM. Review MEDIUMs accepted with rationale (recommended option):
  abandoned timed-out workers are bounded by the 30 s request deadline inside the
  `fact_check_time_budget_seconds` scan budget (default 300 s, so about ten at most); `close()`
  runs only after DS302's send loop, so a "client has been closed" error can surface only in an
  already abandoned worker whose result nobody reads.

### Story 03.0 - Lenz backend client (✅ 2026-11-24)

**Delivered**
- Egress threat model `threat-model-0010-fact-check-egress-2026-11-24.md` (PASS_WITH_FOLLOWUP,
  E1–E13; HIGH EG-4, EG-5, EG-7 mitigated in code).
- `fact_check/lenz.py` `LenzFactCheckClient`, self-registered as backend `lenz`; `httpx>=0.28,<1`.
- 220 Lenz test cases plus a session-wide network guard.

**Tests / gate**
- task-verifier PASS (Task 02); security-auditor post-code PASS_WITH_FOLLOWUP; feature-reviewer
  LGTM.
- The standard self-scan (with `.docsentinel-standard-baseline.json`, as CI runs it) had 17
  blocking DS204 findings: baseline entries of the moved `mining/` modules no longer matched
  their new paths, plus new Milestone 0010 docstrings. Fixed in the docstrings (baseline
  unchanged); `ruff.toml` UP037 ignore extended to `mining/corpus.py` and `telemetry/loader.py`
  for the repo's `-> "None"` convention.
- Full suite 5939 passed / 2 skipped; ruff clean; fast and standard self-scans exit 0.

**Reconciliation note**
- The registration line belongs to Task 03 in the spec but was added at the end of `lenz.py`
  (self-registration on import), consumed.
- 2026-11-24: **Story 04.0 Task 03 complete** (task-verifier PASS; the DS302 rows landed early in Story 01.0 Task 05). The `rules.md` opt-in column says "always" for DS302, consistent with D5 (no `opt_in_option`; the gate note names `--use-external-api`, the env gate, the key variable and `doctor`).
- 2026-11-24: **Story 04.0 Tasks 01, 02 and 05 complete.** Eight new `tests/assets/ds302/` cases
  with `verdicts.json` scripts, helpers in `tests/fact_check_fakes.py`, six integration files
  (clean verdict, reportable verdict incl. fingerprint stability and baseline filtering (C6),
  gate variations, per-claim error / unknown verdict / time budget / real Lenz client over a mock
  transport (C8), salience and send set with C11 for all nine cases, repo-wide embedded-key search
  proven to fail on a planted prefix). Deviations accepted: the per-claim file sits in
  `tests/integration/` because it loads assets; the key search skips nested checkouts.
  Diagrams: `component-overview`, `component-detectors`, `component-reporting` and
  `scan-selection` updated; new `sequence/ds302-fact-check-gate/` and `sequence/extract-facts/`.
- 2026-11-24: **Story 04.0 Task 04 complete — docs sync** (docs-updater, once): `configuration.md`
  (six keys, dual gate), `docs/user/tutorial/cli.md` (DS302, `extract-facts`), report-template
  docs, README, CLAUDE.md (Milestone 0010 status, env variables, `httpx`), architecture README,
  `examples/docsentinel.toml`, `RELEASE_NOTES.json` proposal appended to the unreleased 1.3.0 entry
  (`pyproject.toml` stays 1.2.0; owner to decide). Exit-gate full suite had one failure (X004 in
  the new key-hygiene test, which swallowed `OSError`); fixed to fail closed.

### Story 04.0 - Fixtures, tests and docs (✅ 2026-11-24)

**Delivered**
- `tests/assets/ds302/` (nine cases), integration tests for every gate, verdict, failure and
  send-set path, the repo-wide embedded-key test; DS302 table rows; six diagrams; the docs sync.

**Tests / gate**
- task-verifier PASS (Task 03); targeted 798 passed; milestone exit gates above.

### Milestone close (2026-11-24)

- Stories delivered: 01.0, 02.0, 05.0 (added by owner request 2026-11-23), 03.0, 04.0.
- Open follow-ups: E11 of the extract-facts threat model (no-follow document re-read); RR3 (U+2060
  and tag characters reach `facts-text` flagged, not removed); ADR 0007 and ADR 0003 sign-off; the
  release version for the 1.3.0 notes; Q5 (rotate and remove the API key embedded in
  `examples/docs/lenz_fact-checking.md`, outside this milestone).

- 2026-11-25: **Owner request — Story 06.0 "optional AI-assisted statement rewrite" added.** The
  owner asked: "optional AI-assisted step after `docsentinel fact-check`. If the resulted set of
  facts may seem disconnected and either of them can't be checked independently, process the
  result with AI, on the first step using Anthropic API and `ANTHROPIC_API_KEY` with simplest
  model and clear instructions - rephrase statements borrowing content from previous statements,
  to make them processed as independent self-contained, atomic statements."
  - There is no literal `docsentinel fact-check` subcommand; the request is resolved against the
    two real pipelines that already share one candidate source (plan contract
    [C11](/docs/roadmap/0010-fact-check/plan.md#c11--one-candidate-source-for-ds302-and-extract-facts)):
    `docsentinel extract-facts` / `engine.extract_facts()` and `DS302`'s `detect()`.
  - Authored [Story 06.0](/docs/roadmap/0010-fact-check/06.0-ai-statement-rewrite/README.md),
    specification only: a new `docsentinel.rewrite` package (`protocol.py`,
    `anthropic_backend.py`), a new `StatementRewriter` Protocol (distinct from `FactCheckClient`:
    it rewrites text, it does not return a verdict), a new dual consent gate mirroring plan
    contract C1's shape (`--ai-rewrite` / `DOCSENTINEL_USE_AI_REWRITE=1`, plus the presence of
    `ANTHROPIC_API_KEY`), a pure mining-layer signal reusing `mining/claims.py`'s existing
    anaphora/back-reference heuristic to flag which statements are offered for rewrite, and a
    fail-soft original-preserved-alongside-rewritten data contract.
  - New plan contract **C12** (the AI-rewrite gate shape and its relationship to C1/C5/C11); new
    plan rows D11-D13; a new exit gate 10; ADR number **0008** reserved for this story (not
    written yet, per this task's instruction).
  - Dispositions: plan.md amended (status line, reserved-ADR line, Stories table, dependency
    diagram, new C12, Open decisions D11-D13, Diagrams note, exit gate 10); status.md amended
    (this entry, Planning-state reopened note, Current status row).
  - No code, ADR or threat model is written in this task. This story is purely a specification
    pass, exactly like the original Story 01.0 specification pass before ADR 0007 was written.
  - Open owner questions (continuing the O-series from Story 05.0):
    - **O5**: where the rewrite stage sits — after `extract-facts` selection only, after `DS302`
      selection only, or in one shared place feeding both (recommended, most consistent with
      C11's "one candidate source" spirit, but it changes `DS302`'s risk surface with a second
      third-party destination and changes `extract-facts`'s long-standing offline/no-gate
      guarantee, so it needs explicit confirmation rather than silent adoption).
    - **O6**: the opt-in flag/env names, recommended `--ai-rewrite` /
      `DOCSENTINEL_USE_AI_REWRITE=1`, mirroring C1 gate 2's CLI-flag-or-env shape.
    - **O7**: the API-key environment variable is the plain `ANTHROPIC_API_KEY`, a deliberate
      divergence from plan contract C3's per-backend `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`
      naming, because the owner specified the name every other Anthropic tool already reads;
      recommended accept, with the explicit opt-in gate (O6) as the independent safeguard so the
      key's mere presence (set for an unrelated tool) never silently enables egress.
    - **O8**: a new ADR 0008 versus an amendment to ADR 0007; recommended a new ADR, because the
      consent-gate shape, the secret, the backend Protocol's I/O shape and the risk class
      (generated text re-entering the pipeline, not just a verdict) all differ materially, even
      though the dual-gate pattern of ADR 0007 is the precedent.
    - **O9**: the pinned model id `claude-haiku-4-5-20251001` (Anthropic's current
      cheapest/fastest model for a narrow, bounded rewrite task, pinned exactly rather than by
      alias, to match this project's exact-version dependency-pinning discipline); recommended
      confirm.
    - **O10**: if O5 selects "`DS302` only" or "shared", `DS302` gains a second third-party
      network destination (Anthropic, beside Lenz) inside one rule's `detect()`, which touches
      ADR 0007 Contract 4 and Decision Driver 9 and needs its own egress threat-model pass beside
      the Lenz one; recommended named but not written in this story, exactly like the Lenz egress
      threat model preceded Story 03.0's code.

- 2026-11-26: **Note on Story 06.0 (no change to the story or its open decisions).** A
  deterministic, rule-based anaphora resolution landed in `mining.claims.extract_statements`, the
  one candidate source shared by `DS302` and `extract-facts` (plan contract C11). A statement is now
  one sentence (or one clause of a coordinated sentence), never a join of up to three sentences;
  a third-person pronoun, a possessive or a bare definite noun phrase is replaced by its
  antecedent ("Their findings ..." becomes "The findings of the team led by Nandita Saha ..."), a
  sentence opening with a consequence connective ("As a result") is dropped, and a statement whose
  pronoun stays unresolved is dropped. It uses no learned coreference and no LLM and can resolve
  wrongly. On the MRI sample the preview went from 16 joined statements to 22 single-sentence ones.
  Story 06.0's premise ("disconnected statements") therefore changes: the AI stage would start from
  already-resolved statements, and the `MAX_STATEMENT_SENTENCES` joining its Goal cites no longer
  exists. The owner should re-evaluate the story's scope and need (decisions O5-O10 are unchanged
  and still open).

### Owner rulings after the first live run (2026-11-26 / 2026-11-27)

- 2026-11-26: **Key fallback (K).** `DS302` reads `DOCSENTINEL_FACTCHECK_<NAME>_API_KEY` and, when
  it is unset or empty, `<NAME>_API_KEY` (`LENZ_API_KEY` for `lenz`), in
  `detectors/fact_check.py::_read_api_key`. This reverses the earlier position (threat model 0010
  M8 and FC-8 and FC-14: the other tool's key is never read). Residual risk: a key exported for
  another Lenz tool can open the key half of the gate; the `--use-external-api` half is unchanged.
- 2026-11-26: **Log format (O).** stderr and the per-run log file use
  `[{timestamp}][{severity}]: {message}` (`log.LOG_FORMAT`).
- 2026-11-27: **Lenz response parsing (R) replaces ruling Q4** (ADR 0007 Contract 8, plan C10,
  Story 03.0 decision U7). Every verdict is kept and printed; labels map through `VERDICT_LABELS`
  and any other label is `unverifiable` (never a finding); confidence words map to 0.9/0.6/0.3;
  every item of `claims` is read and the most severe verdict wins. The real API returned words and
  labels such as `Mostly True`, which the old client rejected.
- 2026-11-27: **Tracing (O).** At INFO, `DS302` and the lenz client log the first ten words of each
  claim and its verdict: an explicit owner exception to "document content is never logged"
  (`log.quote_start`).
- 2026-11-27: **Explicit verdict labels (R, O).** Every verdict is shown as `True`, `Mostly True`, `False`,
  `Mostly False`, `Mixed` or `Unverifiable` (`protocol.VERDICT_LABELS`, `lenz.DISPLAY_LABELS`); the lenz INFO
  line is `verdict <Label>, confidence 0.90`; the finding `value` is `<Label> (confidence 0.90): <text>` and
  its `message` is unchanged (baseline fingerprints unchanged).
- 2026-11-27: **Fact checks in the report (O, P).** `ScanResult.fact_checks` (`FactCheck`, `FactCheckClaim`);
  context variables `fact_checks` and `fact_checks_count`; `Fact check:` lines in the `text` template and a
  top-level `fact_checks` array in `json` (omitted when empty); `json-v1` and `github` unchanged.
- 2026-11-27: **`all` combination (K, R).** `all` joins every claim above the salience floor, ignores the
  caps and splits into facts within 1000 characters.
- 2026-11-27: **Shared selection options (C); reverses the O1 ruling's "never read by DS302".** `scan` and
  `baseline` take `--min-salience`, `--max-per-document`, `--max-total`, `--weights`, `--dedup-threshold`;
  `extract-facts` takes `--fact-combination`. Known gap: its preview does not show the request grouping.
- 2026-11-27: **Facts file (C, R).** `scan`/`baseline --include-facts FILE` sends the facts of a `facts-json`
  file (1 MiB, 500 facts); the selection and combination options are ignored with one WARNING; the dual gate
  and the time budget still apply. Threat model addenda dated 2026-11-27 record the verbatim-egress risk.
- Docs synced 2026-11-27 (second pass the same day for the rulings above). The version bump and the
  `RELEASE_NOTES.json` entry remain the owner's.
