# Milestone 0004 — Cross-cutting implementation contracts

## Grounded baseline (master at planning time)

- Repository: `yuchdev/DocSentinel`; master merge SHA: `04a3eb337f7b75d1783cd4a7f45da2c68528113b` (2026-10-14).
- Python **3.12+**, `uv`, Hatchling. Config file is **`doc_sentinel.toml`**, pyproject namespace **`[tool.doc_sentinel]`**, import and CLI name **`docsentinel`**.
- Rules already shipped: fast `DS101`, `DS102`, `DS103`; standard `DS201`–`DS204`; deep `DS301`. Milestones 0001–0003 marked complete.
- Profiles are **exact, not cumulative**. `scan(profile=standard)` does not execute fast rules. Rule `select` / `ignore` uses existing prefix-or-exact resolution.
- `Rule`, `RULES`, `ANALYZERS`, `Finding`, `ScanResult` are the shared contracts; status is not the same as zero findings. `Finding` currently includes `rule`, `path`, `message`, `severity`, `line`.
- Analyzer calls are currently inconsistent: standard analyzers receive `(root, documents, settings)` and fast/deep receive `(root, documents)` in `engine.scan`. This requires intentional compatibility work before more configurable rules are added.
- A deep scan requires a second confirmation gesture and is advisory-only even under `--strict`. The current global `deep_ready()` check requires spaCy+textacy+model, which is unnecessarily broad for the deterministic DS302 and DS316 proposed here.
- Tests are organized `tests/unit`, `tests/mock`, `tests/integration`, `tests/e2e`, with asset cases copied by `tests/asset_helpers.py` and the `asset_case` fixture in `tests/conftest.py`.
- Current self-scan config excludes `tests/assets/*`; deliberately broken fixtures MUST remain excluded from repository documentation QA, Ruff and Flakeforge.

## A. Non-negotiable asset-first test rule

Every DS107/111/119/205/207/208/216/217/218/219/302/316 integration scenario must be checked in as a real UTF-8 Markdown asset, using:

```text
tests/assets/dsNNN/{two_to_four_word_snake_case_slug}/{README|a|b|index|guide|other}.md
```

- A **case** is a directory, *not* one paragraph inside a parametric test. Each case must contain at least one `.md`; the simplest case uses `README.md`. Multi-document comparisons should use `a.md` and `b.md`, but also include a `README.md` if the case needs a clear scan entry point.
- Non-Markdown companions (`src/*.py`, `mapping.toml`, `terminology.toml`, `config/defaults.toml`) are permitted **in addition** to Markdown, never as a substitute. Configuration written by the test body is acceptable only when it varies between tests; canonical text fixtures still belong under assets.
- The case slug is **2–4 clear English words**, lowercase `snake_case`, e.g. `unlinked_nested_reference` (3), `documented_default_mismatch` (3), `changed_linked_source_file` (4). Filename can be `README.md` for single-document tests, `a.md`/`b.md` for paired documents, or descriptive one-word names for additional documents.
- File bytes are immutable test inputs: do not prettify or autoformat deliberate errors, whitespace, line endings or missing EOF newlines.
- Tests load through `asset_case("dsNNN", "case_slug")` and `case.documents("README.md",...)`; `AssetCase.documents()` enumerates **all files**, including `.py`/`.toml`, so use explicit paths for Markdown-only analyzers when companion sources are present.
- **Minimum per rule:** 3 distinct passing cases + 3 distinct failing cases + *every listed edge case*. Failing cases must assert at least one finding for that exact rule code; clean cases must assert no findings for that code; pending/unverifiable cases must assert explicit readiness/validation signaling, not pretend clean.
- **Not sufficient:** a single parametric Python function with in-memory text, tests that merely assert `len(findings)>0`, or fixtures whose only content is headings. Each fixture must contain the substantive text needed to exercise the described check.
- Unit/mocks may inline a few tokens; all rule integration and CLI demonstrations must load file assets. Symlinks, invalid UTF-8, chmod/permission errors, mass fuzzing and dynamic 1000-file stress corpora may be generated at runtime (as current `tests/assets/README.md` allows) and must have corresponding documented tests.
- Fixture authors must not write test-only keywords into production rules. Implement general semantics first; fixtures may not rely on improbable magic tokens except documented opt-in syntax or mappings.

## B. Expected result contract

For each asset scenario keep a test assertion (or code-side parametrization) listing:

```text
case_slug; expected_state (clean|finding|pending); rule_id; expected_location;
source files; config overrides; diagnostic substring; notes
```

Store expectations in Python test parametrization or a `tests/fixture_expectations.py` dictionary; the generated `fixture-matrix.csv` and `fixture-matrix.md` are the specification checklist. Do **not** add `.json` files within a fixture case that the detector mistakes for documentation. A new case is incomplete unless a named test loads it and asserts its stated outcome.

- `Finding.line` is 1-based where an offending Markdown span can be identified; the source path uses normalized POSIX separators relative to scan root. Cross-corpus findings are attributed consistently to the latter document or documented output-target policy.
- For warnings, assert rule ID, severity, path, meaningful message, line where supported, and deterministic order; avoid asserting floating-point similarity scores that vary slightly across dependency versions.
- For failures, assert explicit scan/CLI exit code and validation error messages; Python API exceptions are distinct from findings.
- A candidate can be *expected* in a test without asserting the claim is logically proven. For DS302/DS316, message must say 'candidate' or 'review recommended'.

## C. Analyzer API migration without regressions

Decide one internal calling contract in Story 01.0 before writing detectors. Preferred minimal path:

1. Make all shipped analyzers accept an **optional** `config: Config | None = None` third argument while keeping their existing public two-argument invocation valid, including DS301.
2. Update `engine.scan` to supply the effective `Config` to all selected analyzers, instead of treating standard specially. Keep `ANALYZERS` mapping as the registered dispatch table.
3. For DS316, add **optional** context representing explicit changed paths via `scan(..., changed_paths=...)` and inject a validated immutable scan context into only context-aware rule(s), or provide a typed engine-level `ScanContext` adapter. Do not push `changed_paths` into every unrelated analyzer or make them read process-global state.
4. Maintain monkeypatchability of `ANALYZERS`, direct detector tests, library scan, CLI and pytest plugin, and the exact existing DS101–DS301 behavior. Avoid inspect.signature probing in each scan.

**Alternate safe implementation** is an `AnalyzerContext` dispatch wrapper registered alongside each rule with a compatible legacy adapter. Its acceptance test must prove all old detectors work unchanged. Whichever choice is used, document it and make it stable before rule story merges.

## D. Config conventions

- Add new flat validated config options to the existing `Config` dataclass and `_CONFIG_OPTIONS` allowlist; update `_load_toml_table`, standalone root config and `[tool.doc_sentinel]` parsing, README, and `examples/doc_sentinel.toml`.
- Reject unknown options (existing contract). Do not silently swallow syntax errors.
- New optional checks that require a dictionary, explicit mapping or entrypoint must expose an honest *not evaluated* status when such prerequisites are absent; do not force a new setup burden on all existing users.
- Use repo-relative paths resolved under scan root; prohibit `..` escapes, absolute external targets and symlink traversal for source/config mapping. Project code should be parsed, never imported or executed for analysis.
- New optional extras should be added only for a justified capability, using already installed standard dependencies first. `fast` must not import spaCy, scikit-learn, textstat or third-party Markdown/YAML parsers.

## E. Deep profile capability gating

The shipped engine currently checks `deep_ready()` *before* resolving selected rules. This is appropriate for DS301 but incorrect for new model-free DS302 and DS316.

**Required M4 change:** select active deep rule codes first, check `deep_confirm` before ANY deep execution, then evaluate capability readiness **per selected rule**. `DS301` needs spaCy+textacy+model; `DS302` and `DS316` need no NLP model. A mixed confirmed scan runs eligible rules and explicitly lists skipped rules plus reason. An unconfirmed deep scan runs none. Advisory-only exit code remains 0 even with findings (except configuration/scan failures, which are exit 2). CLI `doctor` must describe individual rule readiness.

Do not silently change deep semantics to build-blocking, download a model, or execute the docs-reviewer agent during CLI scans.

## F. Scanner security and reproducibility

- No external network or LLM calls during detector execution. No import/execution of user project source or Markdown snippets, even when attempting CLI/config/doc synchronization.
- Single scan caches indexes per scan, clears them between scans, supports stable sorted output, and has no cross-root leaks.
- Treat Markdown as untrusted: limit regex backtracking, guard huge files/claims and bound graph traversals. If resource budgets are exceeded, report a clear skipped/incomplete state.
- Keep existing baseline fingerprints and JSON Schema v1 intact; additive fields are permissible only with backward compatibility and validated serializers. Because baseline keys hash message text, message shape changes require baseline review rather than automatic baseline regeneration.
- Deep findings must not contain whole unredacted documents. Cite concise normalized evidence with file:line.

## G. Testing and CI evidence

For every rule's story acceptance:

1. At least 3 clean, 3 finding, and every edge fixture case are present as Markdown assets and loaded by integration tests; see per-story matrices.
2. A direct detector test, a `scan(root, config=...)` integration test, and CLI JSON/text/GitHub results are covered (shared report tests may be combined in the final story).
3. Rule registration and profile selection (exact, noncumulative) are verified, including `select`/`ignore` and baseline handling.
4. A default fast scan on a fresh temp repo does not import any standard/deep package. Standard when extra missing still exits 2 with instructions. Deep unconfirmed still skips all analyzers.
5. `uv run pytest -p docsentinel.pytest_plugin`, `uv build`, Ruff, Flakeforge, and CI self-scan lanes pass; the implementation does not alter intentionally broken assets.
6. Test docs use existing test taxonomy and descriptive docstrings without autogenerated filler. Fixtures with false positives/false negatives are calibrated before the rule ships; no baseline is used to mask a failing fixture test.
