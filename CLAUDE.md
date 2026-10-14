# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

DocSentinel is a deterministic-first documentation QA framework and Python library with three completed milestones:

- **Milestone 0001 (Generic implementation & Fast profile):** Rule registry, layered config discovery, baseline tracking, CLI/Python/pytest orchestration engine, and fast structural detectors (`DS101` dangling links/anchors, `DS102` stray HTML comments, `DS103` unresolvable paths).
- **Milestone 0002 (Standard profile):** Corpus-level detectors (`DS201` text complexity, `DS202` duplicate text, `DS203` low-information content, `DS204` docstring-to-code signature mismatch), lazy loading boundary, and separate baseline/CI lanes.
- **Milestone 0003 (Deep profile & Periodic review):** Semantic contradiction candidate detection (`DS301`), explicit opt-in confirmation gate (`deep_confirm` / `--i-understand-deep-is-heuristic` / `DOCSENTINEL_DEEP_CONFIRM=1`), advisory-only exit codes, and periodic review workflows.

## Commands

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/). Optional dependency extras are `test` (`pytest`), `standard` (`scikit-learn`, `textstat`, `docsig`), and `deep` (`spacy`, `textacy`).

```sh
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin          # full suite (same as CI)
uv run pytest tests/integration/test_scan.py::test_name -p docsentinel.pytest_plugin   # single test
uv run pytest tests/unit/                              # unit test suite
uv run pytest tests/mock/                              # mock test suite
uv run pytest tests/integration/                       # integration test suite
uv run docsentinel scan PATH --format json             # CLI scan (also: text, github)
uv run docsentinel scan --profile standard             # standard profile scan
uv run docsentinel scan --profile deep --i-understand-deep-is-heuristic   # deep profile scan
uv run docsentinel baseline PATH --output PATH        # baseline recording
uv run docsentinel init                                # scaffold doc_sentinel.toml
uv run docsentinel rules                               # list available/active rules
uv run docsentinel doctor                              # environment and dependency readiness
uv build                                               # hatchling wheel/sdist
```

CI (`.github/workflows/ci.yml`) runs with `--locked`: sync with extras, pytest with the plugin, self-scans of the repo, and `uv build`.

## Architecture

All consumers go through one engine, so behavior stays identical across CLI, Python library, and pytest plugin:

- `config.py` — loads/validates `doc_sentinel.toml` (standalone) or `pyproject.toml` (`[tool.doc_sentinel]` table: `profile`, `include`, `exclude`, `select`, `ignore`, `baseline`, `max_grade_level`, `duplicate_similarity`, `min_information_score`, `docsig_paths`, `deep_confirm`).
- `discovery.py` — inventories Markdown files; output order and paths are stable. Patterns match relative paths; exclude patterns also match directory names; symlinked files are skipped.
- `engine.py` — `scan()` is the single entry point used by the CLI, the Python API (`from docsentinel import scan`), and the pytest plugin. It runs discovery, resolves active rules for the requested profile, executes registered analyzers from the `ANALYZERS` registry, and applies baseline filters.
- `detectors/` — modular rule analyzers:
  - `fast` (DS1xx): `links.py` (`DS101`), `comments.py` (`DS102`), `paths.py` (`DS103`). Standard library only.
  - `standard` (DS2xx): lazy-loaded via `loader.py`: `complexity.py` (`DS201`), `duplication.py` (`DS202`), `low_information.py` (`DS203`), `signatures.py` (`DS204`).
  - `deep` (DS301): heuristic semantic checks in `contradictions.py` (`DS301`), `_triples.py`, and `deep_support.py`. Opt-in gated, advisory-only.
- `code_discovery.py` — Python source discovery for `DS204` docstring verification against live AST signatures.
- `baseline.py` — computes SHA-256 finding fingerprints, loads/saves baseline JSON files, and filters known findings.
- `reporting.py` — renders `ScanResult` as human-readable text, structured JSON (Schema v1), or GitHub Actions workflow commands (`::warning`, `::error`).
- `cli.py` — command-line interface (`scan`, `baseline`, `init`, `rules`, `doctor`).
- `pytest_plugin.py` — opt-in pytest plugin (`-p docsentinel.pytest_plugin`) exposing the `docsentinel_scan` fixture.
- `.pre-commit-hooks.yaml` — `docsentinel-fast` (default pre-commit) and `docsentinel-standard` (manual stage).

CLI exit codes: `0` = scan succeeded with no blocking findings (or advisory-only deep findings), `1` = blocking findings (errors, or warnings with `--strict`), `2` = config or scan failure.

## Conventions

- Deterministic-first: fast and standard detectors are strictly deterministic. Deep profile is heuristic, requiring explicit opt-in confirmation (`deep_confirm = true`, `--i-understand-deep-is-heuristic`, or `DOCSENTINEL_DEEP_CONFIRM=1`), and is advisory-only (exit code 0).
- Profiles: `fast` (structural/reference checks, zero extra dependencies), `standard` (corpus/signatures, `docsentinel[standard]`), `deep` (semantic contradictions, `docsentinel[deep]`). Profiles are exact rather than cumulative.
- Rule selection: exact codes or prefixes via `select` / `ignore` (e.g. `select = ["DS1"]`).
- Test layout: `tests/unit/` tests one function with tiny inline strings and never loads assets; `tests/mock/` replaces an external resource; `tests/integration/` runs a detector, scan, or CLI over text assets kept in `tests/assets/` as one directory per rule code and case (dsNNN/case), loaded with the `asset_case` fixture. Integration files that load assets carry the rule IDs as a suffix (for example `_ds101`, or `_ds101_ds102_ds103` when composing rules). See `tests/assets/README.md`.
- See `docs/architecture/README.md` and `docs/roadmap/README.md` for architectural design and milestone details.
