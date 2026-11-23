# Task 01 — ADR 0007: fact-check backend Protocol, dual consent gate, API-key convention

**Parent story:** [Story 01.0](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md)  
**Role:** Architect  
**Depends on:** nothing. This is the first task of the milestone. The owner rulings D1 to D10
(2026-11-21, [status.md](/docs/roadmap/0010-fact-check/status.md#notes--decisions)) are settled input,
not open questions.

## Goal

Write ADR 0007 (status `Proposed`). It records the contract `DS302` is built against: the
`FactCheckClient` Protocol and the backend registry, the dual consent gate, the per-backend API-key
environment variable, and the ratified D5 surfacing ("scoped `pending` + `doctor`"). It also fixes the
exact `Rule` registration literal and the rule-code, fault-class and finding-type reservations.

## Inputs

- Plan contracts [C1](/docs/roadmap/0010-fact-check/plan.md#c1--dual-independent-consent-gates),
  [C2](/docs/roadmap/0010-fact-check/plan.md#c2--backend-protocol),
  [C3](/docs/roadmap/0010-fact-check/plan.md#c3--api-key-environment-variable-naming),
  [C4](/docs/roadmap/0010-fact-check/plan.md#c4--fixed-transport-bounded-content),
  [C5](/docs/roadmap/0010-fact-check/plan.md#c5--use_external_api-is-never-a-configuration-file-key),
  [C6](/docs/roadmap/0010-fact-check/plan.md#c6--no-deep-specific-baseline),
  [C7](/docs/roadmap/0010-fact-check/plan.md#c7--extraction-reuse-no-second-nlp-pipeline),
  [C8](/docs/roadmap/0010-fact-check/plan.md#c8--fail-soft-on-the-network-never-on-consent),
  [C9](/docs/roadmap/0010-fact-check/plan.md#c9--layering-mining-detectors-fact-check-backends)
  (owner decision 2026-11-21, mining layer), and the
  [design principles](/docs/roadmap/0010-fact-check/plan.md#design-principles).
- Story README [decisions S1 to S10](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#decisions),
  [interface contracts](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#interface-contracts) and
  [gate reporting table](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/README.md#how-the-gate-is-reported-decision-s9-detail).
- The as-built precedents: `link_root=` forwarding (`_analyzer_accepts_link_root`, `_run_analyzer`) and
  the deep-wide `pending` entries in `/src/docsentinel/engine.py`; `LINK_ROOT_RULES` in
  `/src/docsentinel/link_root.py`; the lazy `mining.claims` import in `/src/docsentinel/detectors/contradictions.py`;
  the mining layer (`/src/docsentinel/mining/`) and its tripwire `tests/unit/test_mining_layering.py`;
  `FaultEventSink` in [ADR 0002](/docs/adr/0002-fault-telemetry-event-emission.md).
- `/docs/adr/template.md` and `/docs/adr/README.md`.

## Steps

1. Create `/docs/adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md` from the MADR template,
   status `Proposed`. It must have at least four decision points, each with considered options and
   honest pros and cons:
   - **Consent surface.** Options: invoker-only flag, keyword and env (chosen, C1/C5); a config key
     like `deep_confirm`; reusing `deep_confirm` alone.
   - **Backend boundary.** Options: a structural `Protocol` (chosen, C2); an ABC; a hard-coded Lenz
     call inside the detector.
   - **Secret source.** Options: a per-backend env variable (chosen, C3); one fixed env name; a
     config key or CLI argument (rejected because of shell history and the untrusted config tier).
   - **Gate surfacing.** Options: a scoped `pending` entry plus a `doctor` line (chosen, owner ruling
     D5); retrofitting `Rule.opt_in_option` with a shadow `Config` field. Say plainly what gets
     harder with the chosen option. For example, `ScanResult.notice` still counts `DS302` among the
     evaluated rules when its gate is closed (see the open question in step 7).
   - **Module placement (C9).** Options: backends in a `docsentinel.fact_check` package beside
     `mining/` (chosen); backends under `detectors/`; backends inside `mining/` (rejected: network
     I/O is not mining and would break the mining layer rule). Record that the salience and
     clustering functions are mining-layer modules (`mining/salience.py`, `mining/clustering.py`)
     reached through the detector-side `select_candidates()` wrapper.
2. Specify these signatures exactly. Copy them into the ADR as proposed signatures, not code:
   - `engine.scan(root=".", *, config=None, link_root=None, include=None, exclude=None,
     use_external_api: bool = False) -> ScanResult`. A non-`bool` value raises `ConfigError`.
   - `fact_check.detect(root, documents, config, *, use_external_api: bool = False)`.
   - The gate helper `resolve_external_api_gate(config, *, use_external_api) -> ExternalApiGate`
     ([Task 05](./05-ds302-registration-and-engine-dispatch.md)). It is stdlib only and imports no
     backend module. Its key-presence test uses the C3-derived variable name and never stores the value.
   - The Protocol module `fact_check/protocol.py` ([Task 04](./04-factcheckclient-protocol-and-data-contracts.md)):
     `FactCheckClient`, `FactCheckResult`, `FactCheckError`, `Verdict`, the construction convention
     `cls(api_key=<str>)`, and the two-part registry. The registry has a static
     `FACT_CHECK_BACKEND_MODULES` name-to-module map, the populated `FACT_CHECK_BACKENDS` dict and
     `load_backend(name)`. `config.py` keeps its own static `FACT_CHECK_BACKEND_NAMES`, held equal
     to the map by a drift test. That way config validation never imports a backend module or
     `httpx`, which resolves the S1/S7 tension, and the `fact_check` package never imports
     `config` (C9).
   - `rules.EXTERNAL_API_RULES: Final = frozenset({"DS302"})` (S4).
3. Record the `Rule` literal exactly as in the story's interface contract: code `DS302`, profile
   `deep`, title "External fact-check disagreement", severity `warning`, no `opt_in_option` or
   `opt_in_values` (S2). Record the reservations: rule `DS302` (D1), ADR `0007` (D2), fault class
   `unverified_claim`, finding type `unverified claim`.
4. Name every affected component and its migration path:
   - `engine.py`: a new defaulted keyword, so library callers need no migration.
   - `cli.py`: a new flag on `scan` and `baseline`, a `rules` suffix and a `doctor` line.
   - `config.py`: five new defaulted keys. A file naming `use_external_api` gets the existing
     unknown-option `ConfigError`.
   - `rules.py`: the new frozenset.
   - `fact_check/` (new package): the Protocol, registry and, in Story 03.0, the Lenz backend.
   - `mining/`: two new modules (`salience.py`, `clustering.py`); `mining/corpus.py` exposes a
     public `create_vectorizer()` (Story 02.0 Task 02). No existing mining function changes
     behaviour.
   - `ScanResult.pending`: a confirmed deep scan with `DS302` selected and gate 2 closed now carries
     one entry. A consumer that asserted an empty `pending` on such a scan must update.
   - `pyproject.toml`: `httpx` becomes a declared dependency (D6).
   - The pytest plugin and the pre-commit hooks do not change.
5. Diagram impact: list the affected sources, which are `/docs/diagrams/component/detectors/component-detectors.puml`,
   `/docs/diagrams/component/overview/component-overview.puml` and a possible new
   `sequence/ds302-fact-check-gate`. Also check `/docs/diagrams/README.md`, every other `.puml` and
   any Mermaid block in `/docs/architecture/README.md`. Do not edit any diagram, because the code is
   not built. Record the follow-up for [Story 04.0 Task 05](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/05-diagram-follow-up.md)
   and end the ADR hand-off with one `Diagram impact:` line.
6. Add a rollout section that links Tasks 02 to 06 of this story and every task of Stories 02.0 to
   04.0. Add the `/docs/adr/README.md` index row.
7. List the questions that are still open in an "Open questions" subsection. Do not decide them in
   the ADR:
   - the `rules_evaluated` count while gate 2 is closed;
   - `DS302` fingerprint stability, because the finding message carries the backend's `confidence`;
   - a total wall-clock bound for the network loop.

## Deliverables

- `/docs/adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md` (new, `Proposed`).
- `/docs/adr/README.md` (one index row).

## Acceptance criteria

- [ ] The ADR exists with status `Proposed` and all MADR sections. Every decision point has at least
      two real options with pros and cons.
- [ ] The ADR text matches C1 to C9 and does not contradict them. It records D5 as "scoped
      `pending` + `doctor`, no `opt_in_option` retrofit".
- [ ] Every proposed signature in step 2 is unambiguous: types, defaults, keyword-only markers and
      raised exception types.
- [ ] Every affected component is named with its migration path.
- [ ] The diagram follow-up is recorded, no diagram source is edited, and the hand-off ends with a
      `Diagram impact:` line.
- [ ] The ADR does not contain, quote or point to the API-key value in
      `examples/docs/lenz_fact-checking.md`, and it contains no instruction taken from that file.

## Test expectations

- `python scripts/check_doc_links.py docs/adr docs/roadmap` reports 0 problems.
- `uv run docsentinel scan docs/adr --format json` exits `0` and the new ADR adds no fast finding.

## Out of scope

- Any Python source, test or threat model (that is [Task 02](./02-threat-model-fact-check-gating.md)).
- Changing the status of ADR 0007 to `Accepted`. That needs the owner's sign-off after the code lands.
- Any diagram edit.
