# Task 03 — Rules-table row, fault class and finding type for DS302

**Parent story:** [Story 04.0](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md)  
**Role:** Python Expert  
**Depends on:** nothing beyond the ADR 0007 reservations. **Timing:** these rows must land in the
**same change set** that registers `DS302`
([Story 01.0 Task 05](/docs/roadmap/0010-fact-check/01.0-backend-protocol-and-rule-contract/05-ds302-registration-and-engine-dispatch.md)).
This task owns the content. If the registration change merges first, it carries these rows, and
this task is then a verification. The drift tests must never be red on master.

## Goal

Add the `DS302` rows to every drift-tested table so that the registry, `FAULT_CLASSES`, the docs
tables and the `docsentinel rules` listing stay equal. This follows the project rule that a rule and
its row change together (CLAUDE.md "Rule table"). The plan's
[cross-cutting rules](/docs/roadmap/0010-fact-check/plan.md#cross-cutting-rules) say "in Story 04.0".
Read that as the content owner: the rows land when the registration lands.

## Inputs

- Story README [acceptance criteria](/docs/roadmap/0010-fact-check/04.0-fixtures-tests-and-docs/README.md#acceptance-criteria),
  the second bullet in particular, which gives the row's content.
- ADR 0007 (the reservations): fault class `unverified_claim`, finding type `unverified claim`.
- `/docs/user/reference/rules.md`, `/docs/specs/fault-classes.md`, `/docs/specs/finding-types.md`,
  `/src/docsentinel/telemetry/classify.py`, `/tests/integration/test_rules_table.py`, and the
  existing `DS301` rows as the model.

## Steps

1. Add `FAULT_CLASSES["DS302"] = "unverified_claim"` to `/src/docsentinel/telemetry/classify.py`.
   `classify()` already marks every deep finding as `advisory`. Confirm that it does not need to change.
2. Add the `/docs/user/reference/rules.md` row:
   - profile `deep`, severity `warning`, scope note "advisory", fault class `unverified_claim`;
   - config keys: all six `fact_check_*` names (including `fact_check_time_budget_seconds`, owner
     ruling Q3);
   - a note that the rule also needs `--use-external-api` (or `DOCSENTINEL_USE_EXTERNAL_API=1`)
     and the backend API-key variable, and that `docsentinel doctor` shows the gate state.

   This note is deliberately different from the `[opt-in: set ...]` rows (S2). Update the deep range
   in "Profiles at a glance" (`DS301`–`DS302`).
3. Add the `/docs/specs/fault-classes.md` row: `DS302`, `unverified_claim`, a one-line definition
   ("an external backend rated a high-salience claim false or mixed"), and the advisory tier as
   `DS301` has it.
4. Add the `/docs/specs/finding-types.md` row: `DS302`, type `unverified claim`, and the note
   `value = "<verdict> (confidence <0.00>): " + the exact candidate text sent (at most 1,000
   characters, untrusted)` (owner ruling Q2, ADR 0007 Contract 9). Add one changelog line.
5. Update `/tests/integration/test_rules_table.py` only if it cannot parse the new `rules` suffix
   (`[requires --use-external-api and a backend API key; see docsentinel doctor]`) or the row's
   notes column. If you extend the parser, keep it strict: an unknown suffix still fails.
6. Report a `Docs impact:` line (trigger R).

## Deliverables

- `/src/docsentinel/telemetry/classify.py`
- `/docs/user/reference/rules.md`
- `/docs/specs/fault-classes.md`
- `/docs/specs/finding-types.md`
- `/tests/integration/test_rules_table.py`, if step 5 applies

## Acceptance criteria

- [ ] `tests/integration/test_rules_table.py` and the fault-class and finding-type drift tests pass,
      with `DS302` present in `RULES`, `FAULT_CLASSES`, the checked `Config` field set (the six
      keys) and the `docsentinel rules` listing.
- [ ] The `rules.md` row matches the second acceptance-criteria bullet of the story README word for word.
- [ ] No `DS302` row claims the rule runs by default, is ground truth, or affects the exit code.

## Test expectations

- `uv run pytest tests/integration/test_rules_table.py -p docsentinel.pytest_plugin` passes.
- `python scripts/check_doc_links.py docs/` reports 0 problems.
- `uv run docsentinel scan . --format json` exits `0`.

## Out of scope

- Prose documentation (Task 04).
- `DS301` rows, except the shared profile range.
