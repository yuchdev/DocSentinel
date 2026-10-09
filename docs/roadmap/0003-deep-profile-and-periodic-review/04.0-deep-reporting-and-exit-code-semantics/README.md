# Story 04.0 - Deep-Profile Reporting & Exit-Code Semantics

`DS301` findings are explicitly *candidates* (Story 02.0), produced by a heuristic that is expected
to be wrong sometimes. That property forces a deliberate decision this story records and implements:
**`deep` findings never fail a build - not by default, and not even under `--strict`** - a conscious
asymmetry versus `fast`/`standard`, whose `warning`s do fail under `--strict` per
[Milestone 0001 Story 03.0 Task 01](/docs/roadmap/0001-generic-implementation/03.0-cli-and-reporting-completion/01-severity-aware-exit-codes.md).
A future, separate opt-in could change that, but it is explicitly out of scope here. This story also
makes the reporting wording honest for every `deep` outcome and lands the narrow architecture-doc
update that gives `deep` defined (if small) content without overclaiming reliability.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Advisory-only exit-code semantics for deep](01-advisory-only-exit-codes-for-deep.md) | `_exit_code` treats `deep` findings as non-failing even under `--strict`; `--fail-on-deep` documented as deferred |
| 02 | [Deep reporting wording & architecture refresh](02-deep-reporting-wording-and-architecture-refresh.md) | honest `notice`/pending + advisory banner for deep runs; `docs/architecture/README.md` narrow `deep` paragraph |

01 owns the exit-code boundary; 02 owns what the report *says*. Both depend on Story 01.0 (the
`pending`/`notice` branches) and Story 02.0 (`DS301`, the findings being reported). 01 extends the
`_exit_code` helper introduced in Milestone 0001 Story 03.0 Task 01.
