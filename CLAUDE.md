# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

DocSentinel is a deterministic-first documentation QA tool, currently at **M0: an inventory scaffold only**. It discovers Markdown files but runs no detectors. An empty findings list does **not** mean docs are validated; never describe it as a successful content audit. The `standard` and `deep` profiles are placeholders that only report a "pending" message. No network or model calls.

## Commands

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). Runtime dependencies are pinned `release-saga==1.2.0` and `flakeforge==1.1.0` (neither is imported by the package yet); `pytest` is the `test` extra. Use `uv run --extra test pytest ...` so the test extra is installed.

```sh
uv sync --extra test
uv run pytest -p docsentinel.pytest_plugin          # full suite (same as CI)
uv run pytest tests/test_scan.py::test_name -p docsentinel.pytest_plugin   # single test
uv run docsentinel scan PATH --format json             # CLI (also: init, rules, doctor)
uv build                                            # hatchling wheel/sdist
```

CI (`.github/workflows/ci.yml`) runs with `--locked`: sync, pytest with the plugin, a self-scan of the repo, then `uv build`. There is no linter/formatter configured.

## Architecture

All consumers go through one engine, so behavior stays identical across surfaces:

- `config.py` — loads/validates `docsentinel.toml` (`[docsentinel]` table: `profile`, `include`, `exclude`).
- `discovery.py` — inventories Markdown files; output order and paths are stable. Patterns match relative paths; exclude patterns also match directory names; symlinked files are skipped.
- `engine.py` — `scan()` is the single entry point used by the CLI, the Python API (`from docsentinel import scan`), and the pytest plugin. It runs discovery, then every analyzer in the `ANALYZERS` registry, and returns a `ScanResult` (`models.py`). The registry is empty in M0; new detectors register there.
- `reporting.py` — renders `ScanResult` as text/JSON for the CLI.
- `cli.py` — thin argparse-style front end over the engine.
- `pytest_plugin.py` — opt-in plugin (must be enabled with `-p docsentinel.pytest_plugin`) exposing a `docsentinel_scan` fixture; it returns a `ScanResult` and asserts nothing.
- `.pre-commit-hooks.yaml` exposes the `fast` profile as a pre-commit hook.

CLI exit codes: `0` = inventory succeeded (not that detectors passed), `1` = reserved for findings, `2` = config or scan failure.

## Conventions

- New detectors must be explicit and deterministic, with tests for their results added **before** enabling them in the `ANALYZERS` registry.
- Profiles: `fast` (future structural/reference checks), `standard` (corpus/mechanical), `deep` (explicitly enabled semantic integrations). None of these checks exist yet; docs must not imply otherwise.
- See `docs/architecture/README.md` for milestone boundaries.
