# Task 02 — Asset fixture catalog and validation enforcement

## Goal

Convert the milestone-wide asset requirement into a repository-checkable guarantee, not a convention that can be forgotten by an implementation agent.

## Inputs

`fixture-matrix.csv` in this spec archive enumerates every named case. The source-of-truth matrix should be brought into `tests/fixture_catalog.py` or an equivalent checked-in data structure, *without* confusing it with scanned documentation. The new fixture catalog may store metadata outside case directories.

## Implementation

1. Validate all paths under `tests/assets/dsNNN/slug/`: DS code exactly three digits, slug split on `_` gives **2–4 nonempty lowercase English words** (`[a-z][a-z0-9]*` tokens), one or more `.md` files for every case, Markdown files contain UTF-8 or deliberately documented special bytes generated at runtime.
2. Assert at least three `expected=clean` and three `expected=finding` per newly introduced rule, independent cases, and check every enumerated edge.
3. Traverse test parametrizations or a `scenario_registry` to check every asset directory is exercised and every expected case exists. Do not count one multi-doc fixture as three independent passes merely because it contains three files.
4. Extend `tests/assets/README.md` with the two-to-four-word naming rule, suggested `README.md` for one-file cases and a canonical `asset_case` loading example for source companion files.
5. Ensure `tests/assets/*` stays out of `doc_sentinel.toml` exclusions and all format/lint/self-scan lanes; never reformat deliberately malformed source documents.
6. Validate asset file names do not accidentally collide under `load_asset_case`'s `dirs_exist_ok=True` semantics when composing cases into a shared tmp path.

## Acceptance

- [ ] A deliberately missing/one-word-case directory fails the fixture validator with a helpful message.
- [ ] Every DS107–DS316 case directory referenced by the catalog is present; no unused/unasserted cases.
- [ ] All assets loaded by integration tests through existing `asset_case` fixture rather than inline write_text of main inputs.
- [ ] Runtime-only exceptional inputs (symlinks/invalid UTF-8/stress) are separately documented and covered.
