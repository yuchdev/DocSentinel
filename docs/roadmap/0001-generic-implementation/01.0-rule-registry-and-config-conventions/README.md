# Story 01.0 - Rule Registry & Config Conventions

Gives DocSentinel the same configuration shape every Pythonic static analyzer has, before any
detector exists to configure: a stable rule-code registry, a `pyproject.toml`/standalone-file
config convention, and `select`/`ignore` resolution with the defaults `CLAUDE.md` specifies -
include everything, select everything, exclude nothing, ignore nothing. This story produces no
new findings by itself (`RULES` stays empty until [Story 02.0](/docs/roadmap/0001-generic-implementation/plan.md#stories)
registers real detectors) - it is pure plumbing that Story 02.0 plugs into.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Rule registry](01-rule-registry.md) | `docsentinel/rules.py`: `Rule`, `RULES`, `register_rule` |
| 02 | [Config conventions](02-config-conventions.md) | `pyproject.toml` `[tool.doc_sentinel]` / standalone `doc_sentinel.toml`, `select`/`ignore` fields |
| 03 | [Selection resolution](03-selection-resolution.md) | `effective_rules()`; `engine.scan()` filters `ANALYZERS` by it; `ANALYZERS` keyed by rule code |
| 04 | [CLI & docs](04-cli-and-docs.md) | `--select`/`--ignore` flags, real `rules`/`init`/`doctor` output, docs refresh |

Sequential - each task's code depends on the previous one existing (02 imports 01's `RULES` for
validation; 03 consumes 02's `Config.select`/`Config.ignore`; 04 exposes 03's resolver on the CLI).
