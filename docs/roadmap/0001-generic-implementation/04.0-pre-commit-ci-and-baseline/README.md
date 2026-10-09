# Story 04.0 - Pre-commit, CI & Self-Scan Baseline

Closes Milestone 0001: the fast detectors (Story 02.0) and the reporting polish (Story 03.0)
only become a "first limited run" once they're actually wired into the hooks CI already has a
place for, and once this repo's own docs - including the known-broken illustrative ADR 0001 -
stop being a surprise the moment the hook goes live.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Pre-commit fast hook wiring](01-pre-commit-fast-hook-wiring.md) | `.pre-commit-hooks.yaml`'s `docsentinel-fast` hook actually gates on findings |
| 02 | [Baseline file mechanism](02-baseline-file-mechanism.md) | `Config.baseline`, `docsentinel baseline` subcommand, suppression logic in `engine.scan()` |
| 03 | [Self-scan baseline capture](03-self-scan-baseline-capture.md) | `.docsentinel-baseline.json` for this repo; CI step enforces it; cheap pre-existing issues fixed outright |

Sequential: 02 must exist before 03 can use it; 01 can land independently but is most useful
once 02/03 mean a pre-commit run won't immediately fail on this repo's own existing docs.
