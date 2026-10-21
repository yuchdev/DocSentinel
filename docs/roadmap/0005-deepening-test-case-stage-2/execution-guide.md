# Stage 2 — Agentic execution guide

This milestone is designed for independent GitHub Copilot / Claude Code agent stories while avoiding concurrent edits to shared scan code.

## Branch and issue strategy

- Open one milestone named `0005-deepening-test-case-stage-2`; track Story 01.0 through 15.0 as 15 independent issues.
- For each rule, the story README is the issue narrative. Its three numbered task Markdown files are independently executable instructions: **01 detector**, **02 asset fixtures**, **03 tests+verification**.
- Story 01.0 merges first; its internal `markdown_blocks` contract and config layer are a prerequisite for every rule story. Do not create ad-hoc overlapping scanner implementations.
- Rules modifying `config.py`, `rules.py`, and `detectors/__init__.py` may collide: assign one integration owner, rebase before merging, and run the full suite after each merge.

## Sequential dependency graph

```text
M4 shared contracts (if implemented)
       |
    Story 01.0 -- shared Markdown tokens, resolver, fixture audit
       |                          |
       +-- DS109 -- DS110         +-- DS116 -- DS113 -- DS112
       |                               |          \_ DS108
       +-- DS105 -- DS104         +-- DS114 -- DS115 -- DS118
       |         \_ DS106         |
       +-- DS117 -----------------+
                                  |
                             Story 15.0
```

`DS114` depends on DS111 compatible frontmatter parsing; `DS112` may consume DS107 reachable-document graph when available. This is a conceptual dependency map, not a promise that M4 code has landed.

## Story command checklist

Run the repository's actual commands, adjusting only when the current master documents a changed invocation:

```sh
uv sync --extra test --extra standard --extra deep
uv run pytest -p docsentinel.pytest_plugin tests/unit/
uv run pytest -p docsentinel.pytest_plugin tests/integration/
uv run pytest -p docsentinel.pytest_plugin
uv run docsentinel rules
uv run docsentinel scan . --profile fast --format json
uv run docsentinel scan . --profile standard --format json
uv build
```

For the optional deep scan, preserve the explicit confirmation and advisory-only semantics from Milestone 0003. Model-dependent DS301 tests may be skipped when assets are legitimately unavailable, but no new fast rule may depend on deep assets.

## Fixture authoring loop (repeat for each scenario)

1. Read one matrix row; create literal asset files in the specified directory. Respect the input's intended outcome and byte/line shape.
2. For `setup=...`, declare explicit config fixtures or companion sources and assert config propagation. Symlinks, permissions and invalid-encoding bytes are generated at runtime, keeping committed `.md` inputs readable.
3. Load via `case = asset_case("dsNNN", "slug")`. Collect case Markdown documents via `case.documents(*paths)` **excluding non-Markdown attachments** unless testing discovery behavior.
4. Invoke the selected detector and `scan()` separately; isolate own-rule findings from unrelated detectors in full profile scans.
5. Assert path, one-based line, severity, stable ordering, and message evidence. For error scenarios expect `ConfigError`/safe scan failure, not zero findings.
6. Record explicit expectation in `tests/integration/test_milestone_0005_fixture_catalog.py` or named parametrized test. Verify matrix coverage equals actual directory set.
7. Run rule-specific tests, full tests and fast self-scan. Do not autoformat intentionally malformed fixture Markdown.

## Definition of done for each task PR

- Source exists and is registered once; stable text/json/github output.
- At least three clean and three finding fixture directories; every named edge row committed.
- Every fixture is independently exercised and cannot pass from a missing rule or skipped analyzer.
- No new third-party dependency for the fast import graph; no network or document code execution.
- No stale documentation links, baseline masking, unsupported config keys or silent no-op rules.
- Security and ownership boundaries explicitly verified.
