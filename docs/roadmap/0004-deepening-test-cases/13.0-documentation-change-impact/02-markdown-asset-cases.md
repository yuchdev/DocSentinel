# Task 02 — Asset-first test corpus for `DS316`

**Story:** [Story 13.0](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/README.md) · **Output root:** `tests/assets/ds316/`

## Mandatory directory shape

```text
tests/assets/ds316/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **15 named scenario directories** must be created.

## Required passing cases (no `DS316` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds316/unrelated_source_change/` | `README.md`, `docs/guide.md`, `src/unrelated.py` | Changed unrelated module has no mapped documentation references. |
| **CLEAN** | `tests/assets/ds316/unchanged_referenced_source/` | `README.md`, `docs/guide.md`, `src/tool.py` | A documented module exists but is absent from explicit changed set. |
| **CLEAN** | `tests/assets/ds316/excluded_document_ignored/` | `README.md`, `docs/ignored.md`, `src/tool.py` | Documentation excluded from inventory never receives impact finding. |
| **CLEAN** | `tests/assets/ds316/code_fence_path_reference/` | `README.md`, `src/tool.py` | A source-looking string in code fence is not evidence of a doc-to-source dependency. |
| **CLEAN** | `tests/assets/ds316/unmapped_dynamic_reference/` | `README.md`, `src/tool.py` | A speculative NLP similarity without explicit link/mapping does not produce impact. |

## Required failing cases (`DS316` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds316/changed_linked_source_file/` | `README.md`, `src/tool.py` | README links to src/tool.py and it is in changed set: one advisory finding. |
| **FINDING** | `tests/assets/ds316/changed_documented_symbol/` | `README.md`, `src/pkg/worker.py`, `src/pkg/__init__.py` | Docs explicitly reference pkg.worker.run; changed pkg/worker.py is linked via symbol index. |
| **FINDING** | `tests/assets/ds316/changed_config_schema_source/` | `README.md`, `src/config.py`, `mapping.toml` | Docs map config schema to src/config.py; changed schema source prompts review. |
| **FINDING** | `tests/assets/ds316/duplicate_changed_paths/` | `README.md`, `src/tool.py` | Repeated path from list and normalized `./` variant yield one finding. |
| **FINDING** | `tests/assets/ds316/bounded_transitive_mapping/` | `README.md`, `docs/architecture.md`, `src/tool.py`, `mapping.toml` | Curated docs dependency mapping routes source change to one additional docs page. |
| **FINDING** | `tests/assets/ds316/dependency_cycle_no_repeat/` | `README.md`, `docs/a.md`, `docs/b.md`, `src/tool.py`, `mapping.toml` | A dependency cycle terminates and each affected doc appears at most once. |
| **FINDING** | `tests/assets/ds316/deleted_source_change_path/` | `README.md` | Deleted source path still matches a recorded documentation reference without requiring the file to exist. |
| **FINDING** | `tests/assets/ds316/relative_paths_normalized/` | `README.md`, `src/tool.py` | src/./tool.py normalizes to src/tool.py, preserving evidence and stable paths. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds316/changed_files_missing/` | `README.md`, `src/tool.py` | No --changed-file and no API changed_paths; explicitly not evaluated. |
| **PENDING** | `tests/assets/ds316/outside_root_change_path/` | `README.md`, `src/tool.py` | ../secret.py path rejected; do not traverse outside scan root. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS316` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
- For `expected=finding`, assert the exact rule code, severity, target file, one-based line when specified, and evidence phrase. Choose a stable report attribution policy for cross-file candidates.
- For `expected=pending`, assert the precise invalid/unverifiable/not-run signal as agreed in Story 01.0, never an empty result with a misleading 'evaluated' notice.

## Runtime-generated additional edge tests

In addition to the committed Markdown assets, create **runtime-generated** tests if this rule reads files/paths: `UnicodeDecodeError`, permission denied, symlink-to-outside-root, nested `../` root escape, Unicode normalization, CRLF offsets, very long lines, empty/binary input and repeated scans with different roots. Use `tmp_path` and mark resource-heavy cases explicitly rather than checking megabytes of arbitrary data into Git. If a case is inapplicable (e.g., no source traversal in DS119), document why in the story test file.

## Acceptance

- [ ] All 15 directories exist in repository and match these names exactly.
- [ ] Every directory includes one or more `.md` and any required supporting source/config files.
- [ ] At least 3 clean and 3 finding cases are present, independent rather than trivial variations.
- [ ] **All** named edge/negative assertions are implemented and not left as xfail/TODO.
- [ ] No intentionally failing input is 'fixed' or autoformatted by linter scripts.
- [ ] Asset matrix paths and actual committed files are reconciled in a machine-checked inventory test.
