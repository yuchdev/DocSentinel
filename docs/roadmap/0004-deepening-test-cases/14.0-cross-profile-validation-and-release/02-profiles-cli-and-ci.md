# Task 02 — Full-profile API/CLI/CI verification

## Exact profile rules after M4

- `fast`: DS101, DS102, DS103, **DS107, DS111, DS119**.
- `standard`: DS201, DS202, DS203, DS204, **DS205, DS207, DS208, DS216, DS217, DS218, DS219**.
- `deep`: DS301, **DS302, DS316**.

`scan --profile standard` MUST NOT implicitly execute fast. `scan --profile deep` MUST NOT automatically execute other profiles. CLI rule listings must reflect actual registration and readiness without eager imports.

## Test matrix

| Run | Expected |
|---|---|
| fast, stdlib-only install, no spaCy/sklearn | All fast rules load, none of the heavy modules imported |
| standard without `docsentinel[standard]` | Exit 2, install hint; not a fake clean report |
| standard with extra, no explicit code mapping | Corpus rules work, mapping-dependent rules explain not evaluated |
| deep, no confirmation | No deep analyzers executed, explanatory pending |
| deep, confirm, select DS302 only, no model | DS302 runs advisory |
| deep, confirm, select DS316 only, changed-file provided | DS316 runs advisory |
| deep, confirm, select DS301 only, no model | DS301 pending, no auto install |
| deep, confirm, select DS301+DS302 and model absent | DS302 runs, DS301 pending |
| strict + deep candidate findings | Exit 0; explicit candidate messages |
| malformed config, invalid source mapping, root escape | Exit 2; actionable error |
| baseline containing earlier finding | Suppress earlier; new findings remain visible |
| repeated scans / different roots | stable ordering, no cache bleed |

## CLI and report formats

`docsentinel scan --profile ... --format text|json|github`, `docsentinel rules`, `doctor`, and baseline creation must reflect new IDs. New `--changed-file` help describes explicit change list and path scope. `docsentinel scan` must not execute user code, model downloads, network calls, or tests. Preserve JSON schema version semantics.

## Commands

```sh
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin
uv run pytest tests/integration/test_milestone_0004_fixture_catalog.py -p docsentinel.pytest_plugin
uv run docsentinel rules
uv run docsentinel doctor
uv build
```

Run Ruff and Flakeforge with the repository's configured commands, plus self-scans in the existing `.github/workflows/ci.yml`. Optional NLP model-dependent tests must not be mislabeled as passing when skipped.
