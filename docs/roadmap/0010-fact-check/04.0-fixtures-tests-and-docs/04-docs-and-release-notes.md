# Task 04 — User and developer documentation; proposed release-notes entry

**Parent story:** [Story 04.0](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md)  
**Role:** Docs Writer  
**Depends on:** Stories 01.0 to 03.0 and 05.0 merged. Tasks 01 to 03 of this story are green. The `Docs impact:`
lines from every Python Expert task in this milestone are collected.

## Goal

Document `DS302` truthfully and completely. Cover what it does, the fact that it sends
document-derived text to a third party, the two independent opt-ins it needs, the per-backend key
variable, and that its verdicts are advisory third-party heuristics. Then propose a
`RELEASE_NOTES.json` entry.

## Inputs

- Story README [docs to update](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md#docs-to-update)
  (normative list).
- Plan [exit gate 6](/docs/roadmap/0010-fact-check/plan.md#exit-gates) (honesty review) and contracts
  [C1](/docs/roadmap/0010-fact-check/plan.md#c1--dual-independent-consent-gates),
  [C3](/docs/roadmap/0010-fact-check/plan.md#c3--api-key-environment-variable-naming),
  [C5](/docs/roadmap/0010-fact-check/plan.md#c5--use_external_api-is-never-a-configuration-file-key).
- Both threat models: `/docs/security/threat-model-0010-fact-check-gating-<date>.md` and
  `/docs/security/threat-model-0010-fact-check-egress-<date>.md`. Their guidance on safe invocation
  (`pre-commit args:`, `pull_request_target`) is normative for the CLI page.
- `/docs/dev/documentation_sync.md` (triggers R, C, K, A, D, P), and ADR 0007.

## Steps

1. `/docs/user/reference/configuration.md`: add a new section, "External fact-checking (DS302)".
   - Document the six `fact_check_*` keys in the page's per-option format: type, default, bounds,
     effect and example. Add their rows to the summary table. For
     `fact_check_time_budget_seconds`, say that it is measured with a monotonic clock, that claims
     not yet sent when it runs out are skipped with one WARNING, and that an in-flight request can
     overrun it by one backend timeout.
   - State that `DS302` is not counted as evaluated in the notice while either gate is closed, that
     the finding `value` carries the backend confidence, and that an unrecognised verdict is
     skipped with a WARNING (owner rulings Q1, Q2, Q4).
   - Explain the dual gate.
   - State that `use_external_api` and the API key are never configuration keys, and that a file
     naming either one is rejected or ignored.
   - State that the transport (URL, timeout, size cap) is fixed.
   - Note that the keys are allowed in user settings.
2. `/docs/user/tutorial/cli.md`, deep profile section:
   - Document `--use-external-api` on `scan` and `baseline`, `DOCSENTINEL_USE_EXTERNAL_API=1` (exact
     value), and `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` with its `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`
     pattern.
   - Give one worked example that uses only placeholder key material, written literally as
     `DOCSENTINEL_FACTCHECK_LENZ_API_KEY=<your key here>`.
   - Add a prominent warning that this sends claim sentences to a third-party service.
   - Add the threat-model guidance: never put the flag in pre-commit `args:` or in a
     `pull_request_target` workflow, and never export the key for a whole CI job.
   - Show the `doctor` line and the `pending` entry.
2a. **`extract-facts` (Story 05.0).** In `/docs/user/tutorial/cli.md`, add an `extract-facts` section
   next to `scan`. There is no `/docs/user/reference/cli.md`; the CLI page is this tutorial.
   - Purpose: an offline, non-LLM list of the verifiable facts that `DS302` would send. Present it
     as the preview to review before passing `--use-external-api`.
   - Every option, from Story 05.0 Task 03.
   - The default output equals the DS302 set for the same root, configuration, selection and spaCy
     model. `matches_ds302` and the notice say when it does not.
   - `--weights`/`--dedup-threshold` are exploration only: they never change DS302 and are not
     configuration keys.
   - `--all` and the dispositions.
   - The output contains document text, so treat a `-o` file like the documents.
   - Exit codes `0`/`2`, and that the command never exits `1`.
   - It needs the deep extras and no `deep_confirm`.
   - Two examples, `facts-text` and `facts-json`, using synthetic sentences.

   In `/docs/specs/report-template-format.md`, document the top-level `context` key and the facts
   context schema (paths and trust tags from the Story 05.0 README) and the `facts-json` schema 1.
   In `/docs/user/tutorial/custom-reports.md`, add one paragraph on writing a `facts` template.
3. `/CLAUDE.md`:
   - Architecture: add the `DS302` modules (`detectors/fact_check.py`; the mining-layer
     `mining/salience.py` and `mining/clustering.py`; the `fact_check/` backend package with
     `fact_check/protocol.py` and `fact_check/lenz.py`), the C9 layering rule and its two tripwire
     tests, the gate, the `pending` surfacing and `EXTERNAL_API_RULES`.
   - Milestone status: add one line.
   - Commands: add `uv run docsentinel extract-facts PATH --format facts-json`. Architecture: in
     `engine.py`, name `extract_facts()` and the shared inventory step. In `detectors/`, name
     `trace_candidates`/`collect_candidates` as the one candidate source (C11). In `telemetry/`,
     name `facts_model.py`, the `context` key and the two facts templates. In `models.py`, name
     `FactExtractionResult`.
   - Add `DOCSENTINEL_USE_EXTERNAL_API` and `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY` to "Environment
     variables read by DocSentinel".
   - Add `httpx` to the profiles convention: a declared dependency, imported only on the open-gate
     deep path.
4. `/README.md`: add the rule-list entry and a configuration example with no key.
   `/examples/docsentinel.toml`: add the six keys, commented out, with no key and no consent setting.
5. `/docs/architecture/README.md`:
   - Profile boundaries: the deep profile now has one opt-in outbound network edge.
   - Name the new modules and the Protocol boundary.
   - Diagram changes go through Task 05. Do not edit diagram sources.
6. Verify the `DS302` rows written by Task 03 in `/docs/user/reference/rules.md`,
   `/docs/specs/finding-types.md` and `/docs/specs/fault-classes.md`. Do not fork them.
7. `/RELEASE_NOTES.json`: propose an entry without bumping the version (owner ruling D9).
   - `DS302` is new: off by default, advisory only, and it needs two explicit, independent opt-ins
     before any network call.
   - Six new keys, one new flag, two new environment variables, and `httpx` as a declared
     dependency.
   - New offline `extract-facts` command and `docsentinel.extract_facts()`, two new packaged
     templates, and the additive template `context` key. Existing templates are unchanged.
   - Existing users see no behaviour change, except that a confirmed deep scan now carries one
     `pending` entry while the fact-check gate is closed.
8. Run `python scripts/check_doc_links.py docs/` and fix what it reports.

Per CLAUDE.md "Docs sync", the orchestrator runs this task through the `docs-updater` agent once,
after tests are green and review is LGTM, and before the push.

## Deliverables

The documents named in steps 1 to 7. No source files.

## Acceptance criteria

- [ ] Every document in the story's "Docs to update" list is current.
- [ ] Every page that mentions `DS302` states that it is off until both gates are met, that it is
      advisory, and that the Lenz verdict is third-party heuristic output and not ground truth (exit
      gate 6).
- [ ] No document contains a real or real-looking API key. The only key text is the literal
      placeholder `<your key here>`. No document repeats instructions from
      `examples/docs/lenz_fact-checking.md`.
- [ ] The release-notes entry is proposed, and the version is left to the owner.
- [ ] The link check reports 0 problems. `uv run docsentinel scan . --format json` exits `0`, and
      the edited pages add no finding.

## Test expectations

- `tests/integration/test_rules_table.py` still passes.
- Task 02's embedded-key regression test passes over the edited documents.

## Out of scope

- Diagram edits (Task 05).
- Changing ADR 0007 to `Accepted`, which needs the owner.
- Bumping the version.
