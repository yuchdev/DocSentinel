# Story 04.0 — Fixtures, tests, docs and release notes

**Touches:** `docs/user/reference/rules.md`, `docs/user/reference/configuration.md`,
`docs/user/tutorial/cli.md`, `docs/specs/finding-types.md`, `docs/specs/fault-classes.md`,
`src/docsentinel/telemetry/classify.py` (`FAULT_CLASSES`), `CLAUDE.md`, `README.md`,
`examples/docsentinel.toml`, `RELEASE_NOTES.json`, `tests/assets/ds302/`.
**Parent:** [Milestone 0010 plan](/docs/roadmap/0010-fact-check/plan.md) (exit gates, item 8).
**Security-sensitive:** no new surface, but this story owns the milestone-wide regression check
that nothing produced across Stories 01.0–04.0 ever carries the embedded Lenz example key or
exercises the real endpoint — see the acceptance criteria below.

## Goal

Close the milestone end to end: full-corpus integration tests of `DS302` against a fake, in-repo
backend; the mapping/rules-table drift tests kept green; every doc trigger in
`docs/dev/documentation_sync.md` that this change set hits; a proposed `RELEASE_NOTES.json` entry;
and the regression check that nothing in this milestone ever touched the real Lenz API or its
example key.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| `01-fixtures-and-fake-backend.md` | `tests/assets/ds302/` asset cases; an in-repo `FakeFactCheckClient` test double registered only inside the test suite (never in `FACT_CHECK_BACKENDS` at import time) | Testing Expert | ⬜ Not written |
| `02-integration-and-mock-tests.md` | End-to-end `scan()` tests for: both gates on with a clean verdict, both gates on with a false/mixed verdict producing a `DS302` finding, each gate individually off, a per-claim `FactCheckError` skip, and the embedded-key regression grep | Testing Expert | ⬜ Not written |
| `03-rules-table-and-fault-class.md` | `rules.md` row, `fault-classes.md` row (`unverified_claim`), `finding-types.md` row (`unverified claim`), `FAULT_CLASSES` entry; `tests/integration/test_rules_table.py` kept green | Python Expert | ⬜ Not written |
| `04-docs-and-release-notes.md` | `configuration.md` (the five `fact_check_*` keys plus the dual-gate explanation), `cli.md` (`--use-external-api`, `DOCSENTINEL_USE_EXTERNAL_API`, `DOCSENTINEL_FACTCHECK_LENZ_API_KEY`, a worked example with placeholder key material), `CLAUDE.md`/`README.md` updates, `examples/docsentinel.toml` annotation, proposed `RELEASE_NOTES.json` entry | Docs Writer | ⬜ Not written |
| `05-diagram-follow-up.md` | `Diagram impact` line for `diagram-creator`: `component-detectors.puml` (new `fact_check.py`/`fact_check_salience.py`/`fact_check_lenz.py` boxes and the `FactCheckClient` Protocol boundary) and `component-overview.puml` (the first outbound-network edge this project draws, labelled gated/opt-in) | Python Expert (reports the line; `app-architect` or the orchestrator invokes `diagram-creator`) | ⬜ Not written |

## Scope

- Fixture assets exercising `DS302` end to end through `scan()`, using a fake `FactCheckClient`
  the test suite injects (never the real `FACT_CHECK_BACKENDS["lenz"]`).
- Every drift-tested doc table (`rules.md`, `fault-classes.md`, `finding-types.md`,
  `FAULT_CLASSES`) gains its `DS302` row in the same change that lands the code, per this
  project's existing rule (Milestone 0009 plan.md "Cross-cutting rules").
- The milestone-wide "never the real key, never the real endpoint" regression check.

## Non-goals

- Any change to `DS301`'s own fixtures or docs rows.
- A second backend's fixtures (none exists yet).
- Running a live scan against `lenz.io` at any point, including in a documentation example's
  copy-pasted command (every example command in the docs this story writes uses a placeholder
  key, e.g. `DOCSENTINEL_FACTCHECK_LENZ_API_KEY=<your key here>`, never a working one).

## Design

### Fixture and fake-backend shape

```python
# tests/mock/_fake_fact_check_backend.py (test-only; never imported by src/)

from docsentinel.detectors.fact_check_protocol import FactCheckResult


class FakeFactCheckClient:
    """A deterministic FactCheckClient test double; never touches the network."""

    name = "fake"
    API_KEY_ENV_VAR = "DOCSENTINEL_FACTCHECK_FAKE_API_KEY"

    def __init__(self, api_key: str, *, verdicts: dict[str, FactCheckResult]):
        self._api_key = api_key
        self._verdicts = verdicts

    def check_claim(self, claim: str) -> FactCheckResult:
        return self._verdicts.get(
            claim, FactCheckResult(verdict="unverifiable", confidence=0.0, backend=self.name)
        )
```

Tests register `FakeFactCheckClient` into a **copy** of `FACT_CHECK_BACKENDS` (or monkeypatch the
registry for the duration of one test) and set `config.fact_check_backend = "fake"` plus
`DOCSENTINEL_FACTCHECK_FAKE_API_KEY` in the test's own environment — the real `"lenz"` entry is
never exercised by any test in this project.

### Asset cases (one folder per case, under `tests/assets/ds302/`)

`gate_off_no_flag`, `gate_off_no_key`, `both_gates_on_clean_verdict`,
`both_gates_on_false_verdict_reports`, `both_gates_on_mixed_verdict_reports`,
`per_claim_network_error_skipped`, `salience_filter_drops_trivial_claim`,
`corpus_dedup_collapses_repeated_claim` (shared with Story 02.0's own unit tests, but exercised
here end to end through `scan()`), `deep_confirm_off_skips_everything_including_ds302`.

Every fixture's claim text is written by hand for this milestone (short, clearly synthetic
sentences with a number or a named entity) — none of it is copied from
`examples/check_fact.py`'s `CLAIMS_DB` or from `examples/docs/lenz_fact-checking.md`.

## Acceptance criteria

- [ ] `tests/integration/test_rules_table.py` passes with `DS302` present in `RULES`,
      `FAULT_CLASSES`, the `Config` field set it checks, and `docsentinel rules`' listing.
- [ ] `docs/user/reference/rules.md` carries one `DS302` row: profile `deep`, severity `warning`,
      "advisory" scope note, fault class `unverified_claim`, config keys listing all five
      `fact_check_*` names plus a note that it also needs `--use-external-api` and a backend API
      key (distinct from an ordinary `opt_in_option` row, consistent with Story 01.0 decision S2).
- [ ] A full-suite run (`uv run pytest -p docsentinel.pytest_plugin`) is green with every new file
      from Stories 01.0–04.0 included, and performs **zero** real network requests (enforced by a
      test-session-scoped guard that fails if `httpx`'s real transport is ever reached, not only by
      careful mocking in each test file).
- [ ] A dedicated regression test (`test_no_lenz_example_key_leaked.py`) greps every file this
      milestone added or touched for the literal API-key prefix embedded in
      `examples/docs/lenz_fact-checking.md` and fails if it finds a match anywhere outside that
      one pre-existing example file.
- [ ] The self-scan (`docsentinel scan . --format json`) still exits `0` with **zero** `DS302`
      findings on this repository, because no CI job or local hook ever sets
      `--use-external-api`/`DOCSENTINEL_USE_EXTERNAL_API` or any `DOCSENTINEL_FACTCHECK_*_API_KEY`.
- [ ] `RELEASE_NOTES.json` gains a proposed entry describing `DS302` as off-by-default,
      advisory-only, and requiring two independent, explicit opt-ins before any network call.
- [ ] `diagram-creator` is invoked (or the `Diagram impact` line handed to whoever can invoke it)
      only after this story's code is merged, per the project rule that `/docs/diagrams/` shows
      the as-built package, never a planned one.

## Test plan

| Layer | File (new) | Covers |
|---|---|---|
| Integration | `test_ds302_full_scan_clean_verdict_ds301.py` | Both gates on, fake backend returns a clean verdict, zero `DS302` findings, `DS301` still runs normally alongside it |
| Integration | `test_ds302_full_scan_false_verdict_reports.py` | Both gates on, fake backend returns `false`/`mixed` above the confidence floor, one `DS302` finding per surviving candidate, fields match the Story 01.0 contract (`value`, `type="unverified claim"`) |
| Integration | `test_ds302_gate_variations_ds301.py` | Each of: no `deep_confirm` (both DS301 and DS302 skipped, existing behaviour unchanged); `deep_confirm` on, gate 2 off (DS301 runs, DS302 skips with the WARNING); both gates on (both run) |
| Mock | `test_ds302_per_claim_network_error_skipped.py` | One candidate's `check_claim()` raises `FactCheckError`; the scan still completes, the other candidates are still checked, and the failure is logged without the claim text |
| Mock/regression | `test_no_lenz_example_key_leaked.py` | The milestone-wide grep guard described above |
| Integration (existing) | `tests/integration/test_rules_table.py` | Updated for the new `DS302` row |

## Docs to update

Triggers R, C and K of `/docs/dev/documentation_sync.md`, all landed in this story once Stories
01.0–03.0's code exists:

- `/docs/user/reference/rules.md` (`DS302` row);
- `/docs/user/reference/configuration.md` (new section "External fact-checking (DS302)" covering
  the five `fact_check_*` keys, the dual consent gate, and the per-backend API-key convention);
- `/docs/user/tutorial/cli.md` (deep profile section: `--use-external-api`, the two environment
  variables, a worked example using placeholder key material, and an explicit warning that this
  sends document-derived text to a third party);
- `/docs/specs/finding-types.md` (`DS302` row, type `unverified claim`),
  `/docs/specs/fault-classes.md` (`DS302` row, fault class `unverified_claim`);
- `/CLAUDE.md` (Architecture section's deep-profile bullet; the "Environment variables read by
  DocSentinel" line gains `DOCSENTINEL_USE_EXTERNAL_API` and
  `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`);
- `/README.md` rule list and configuration example;
- `/examples/docsentinel.toml` (the five `fact_check_*` keys, commented, never the API key);
- a proposed `/RELEASE_NOTES.json` entry (version left to the owner, decision D9).
