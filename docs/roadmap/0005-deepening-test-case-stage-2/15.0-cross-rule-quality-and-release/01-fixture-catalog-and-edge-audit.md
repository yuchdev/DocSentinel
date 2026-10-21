# Task 01 — final fixture completeness and all-rule edge audit

- Inventory every `tests/assets/ds104`, `ds105`, `ds106`, `ds108`, `ds109`, `ds110`, `ds112`, `ds113`, `ds114`, `ds115`, `ds116`, `ds117`, `ds118` case directory and reconcile against `fixture-matrix.csv` and JSON. There must be **185 independently loadable scenarios** unless spec updated with justification.
- Assert at least three CLEAN and three FINDING directories for *each* rule, plus ALL named special edge cases and explicit ERROR handling.
- Confirm each directory contains Markdown and meaningful text, not empty placeholders; all companion files and opt-in config variations work.
- Ensure all required outcome tests execute the analyzer rather than passing because the profile skipped it. No `xfail`/`skip` for new fast rules and no generic `assert result is not None` tests.
- Test scanner/caches with the same fixture copied into two roots and edited between runs: results must not leak.
- Record counts, fixtures, tests and assertion locations in `status.md` for each new rule. Detect if matrix text drifts from JSON/CSV and fail audit accordingly.
