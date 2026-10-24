# DocSentinel test suite guide

This guide documents how the tests are organised, configured, run and extended. The configuration lives in `pyproject.toml` (`[tool.pytest.ini_options]`, `[tool.coverage.*]`, `[tool.flakeforge]`) and in `doc_sentinel.toml` (the repository's own documentation scan).

## Running the tests

```sh
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin     # full suite, same as CI
uv run pytest tests/unit/                      # one category
uv run ruff check .                            # lint
```

The full suite takes several minutes because the complexity tests measure CPU time on doubling input sizes. Do not run two full suites at once: overlapping runs make those timing tests noisy.

## Configuration

`[tool.pytest.ini_options]` in `pyproject.toml`:

| Setting | Value | Why |
|---|---|---|
| `testpaths` | `tests` | Only the test tree is collected. |
| `pythonpath` | `src` | Tests import the package from the source tree. |
| `addopts` | `--strict-markers --strict-config` | An unknown marker or ini key fails collection instead of being ignored. |
| `norecursedirs` | assets, reference, build folders | Fixture Markdown and frozen oracle sources are never test modules. |
| `markers` | `unit`, `mock`, `integration`, `e2e` | The four test categories below. |

`tests/conftest.py` applies the category marker automatically from the directory, an explicit marker, or the test body, so every test belongs to exactly one category.

## Test categories and layout

| Directory | Category | Rule |
|---|---|---|
| `tests/unit/` | Unit | Tests one function with tiny inline strings. Never loads assets. |
| `tests/mock/` | Mock | Replaces an external resource, for example the filesystem recorder tests. |
| `tests/integration/` | Integration | Runs a detector, a scan or the CLI over text assets in `tests/assets/`. File names carry the rule IDs as a suffix (for example `_ds113`). |
| `tests/flake8_lint/` | Lint gate | Lints `src`, `tests` and `scripts` with the flakeforge X-rules and no baseline. |
| `tests/assets/` | Fixtures | One directory per rule code and case (`dsNNN/case`), loaded with the `asset_case` fixture. See `tests/assets/README.md`. |
| `tests/reference/` | Frozen oracles | Pre-fix copies of DS101 and DS103 used for parity checks. Never refresh them. |

Every test function carries the standard docstring (`[Unit|Mock|Integration] area: verifies ...` followed by Scenario, Boundaries and On failure sections). Check or regenerate with `uv run python scripts/document_tests.py --check tests`.

## Fixture manifest

`docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.{json,csv,md}` is the checked-in catalog of promised scenarios. `tests/milestone_0005_manifest.py` turns it into the enforced source of truth, and `tests/integration/test_milestone_0005_fixture_catalog.py` enforces it per rule:

- A rule that is not registered is pending, and committing assets for it fails the suite.
- A registered rule must have every promised directory, correctly named (two to four snake_case words) and loadable, with the default-setup outcome matching the manifest.
- The three formats and the expected totals are cross-checked, so an inconsistent edit fails loudly.

## Techniques used by the suite

- **Explicit expectation tables.** Integration tests transcribe expected findings from the manifest; they never derive expectations from detector output.
- **Complexity regression (`tests/timing_helpers.py`).** `assert_scales_linearly` measures CPU time over a doubling series with the garbage collector paused, and fails on the log-log slope (limit 1.4). Floods use increasing, non-repeating units on both single-line and multi-line shapes.
- **Filesystem recorder (`tests/mock/`).** Wraps `os.stat`, `lstat`, `readlink`, `scandir`, `open` and friends to prove that path-sensitive rules (DS101, DS103, DS113, DS116) never touch anything outside the scan root and never open asset content.
- **Frozen parity oracles.** The pre-fix DS101 and DS103 sources check that the shared-scanner changes did not alter their behaviour.
- **Mutation checks.** For security-sensitive rules, temporarily breaking a guard must turn a named test red. Results are recorded in the milestone `status.md`.
- **Differential checks.** Scratch scripts compare detector recognition with a CommonMark renderer (`markdown_it`); documented gaps are pinned by tests.

## Coverage

Coverage is opt-in because `pytest-cov` is not a project dependency:

```sh
uv run --with pytest-cov pytest --cov=docsentinel
```

Do not add `-p docsentinel.pytest_plugin` to a coverage run: the plugin imports the package before coverage starts, which makes module-level lines look uncovered. Measured at Milestone 0005 (ten of fifteen stories closed): **96%** of 3,162 statements. The lowest modules are the deep-profile files (`detectors/_triples.py`, `detectors/contradictions.py`, `deep_support.py`) and `code_discovery.py`. `[tool.coverage.report] fail_under = 90` applies when coverage is run; it is not part of the default test command.

## Lint gates

`uv run ruff check .` and `tests/flake8_lint/test_project_lint.py` must stay clean. The flakeforge X-rules enforced here include: no silent `except` that only assigns a sentinel (X004), docstrings on nested functions, no local imports (X006), and annotating returned values while omitting `-> None`.

## Adding a rule's tests

1. Unit tests with tiny inline strings, including single-line and multi-line doubling floods for every new regex or loop.
2. Committed fixture directories in `tests/assets/dsNNN/` matching the manifest, then register the rule so the catalog enforces them.
3. An integration file `tests/integration/test_*_dsNNN.py` with explicit expectation tables, both the pure `detect` path and the shared `scan` path, config-file forms, CLI exit codes, and safety cases.
4. Update every test that hardcodes the registered fast-rule list or counts (search for the neighbouring rule codes), and the rule lists in `CLAUDE.md`, `README.md` and `docs/architecture/README.md`.
5. For security-sensitive rules, add a filesystem-recorder test and at least four mutation checks.
