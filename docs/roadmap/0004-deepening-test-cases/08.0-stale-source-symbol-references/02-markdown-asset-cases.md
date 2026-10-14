# Task 02 — Asset-first test corpus for `DS216`

**Story:** [Story 08.0](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/README.md) · **Output root:** `tests/assets/ds216/`

## Mandatory directory shape

```text
tests/assets/ds216/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **13 named scenario directories** must be created.

## Required passing cases (no `DS216` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds216/existing_public_function/` | `README.md`, `src/pkg/module.py`, `src/pkg/__init__.py` | README refers to local package.module.process(), which exists. |
| **CLEAN** | `tests/assets/ds216/external_library_reference/` | `README.md`, `src/pkg/module.py` | Reference to stdlib/pathlib.Path is not claimed to be an in-repo symbol. |
| **CLEAN** | `tests/assets/ds216/valid_class_method_symbol/` | `README.md`, `src/pkg/module.py` | README refers to local module.Worker.run that exists. |
| **CLEAN** | `tests/assets/ds216/backtick_ambiguous_name/` | `README.md`, `src/pkg/module.py` | Plain `run()` without module context is not automatically assumed to be local. |
| **CLEAN** | `tests/assets/ds216/decorator_alias_function/` | `README.md`, `src/pkg/module.py` | Statically declared alias resolves to an existing function. |
| **CLEAN** | `tests/assets/ds216/nested_class_definition/` | `README.md`, `src/pkg/module.py` | Nested class symbol is indexed with complete qualified path. |
| **CLEAN** | `tests/assets/ds216/dynamic_getattr_reference/` | `README.md`, `src/pkg/module.py` | Documented dynamic attribute is exempt unless explicit static mapping proves otherwise. |
| **CLEAN** | `tests/assets/ds216/symbol_inside_code_fence/` | `README.md`, `src/pkg/module.py` | Standalone example code does not create a symbol-reference claim by default. |
| **CLEAN** | `tests/assets/ds216/symlink_outside_code_root/` | `README.md`, `src/pkg/module.py` | Never follow symlink escapes when indexing source paths. |

## Required failing cases (`DS216` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds216/removed_function_reference/` | `README.md`, `src/pkg/module.py`, `src/pkg/__init__.py` | README refers to qualified local pkg.module.old_api(), absent from the symbol index. |
| **FINDING** | `tests/assets/ds216/misspelled_class_method/` | `README.md`, `src/pkg/module.py` | README refers to local Worker.execut(), while only execute() exists. |
| **FINDING** | `tests/assets/ds216/removed_module_reference/` | `README.md`, `src/pkg/__init__.py`, `src/pkg/module.py` | README links qualified pkg.legacy.helper() but no local module or mapped symbol exists. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds216/python_source_syntax_error/` | `README.md`, `src/pkg/module.py` | Broken source AST must yield an actionable scan error/pending state, never a clean symbol audit. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS216` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
- For `expected=finding`, assert the exact rule code, severity, target file, one-based line when specified, and evidence phrase. Choose a stable report attribution policy for cross-file candidates.
- For `expected=pending`, assert the precise invalid/unverifiable/not-run signal as agreed in Story 01.0, never an empty result with a misleading 'evaluated' notice.

## Runtime-generated additional edge tests

In addition to the committed Markdown assets, create **runtime-generated** tests if this rule reads files/paths: `UnicodeDecodeError`, permission denied, symlink-to-outside-root, nested `../` root escape, Unicode normalization, CRLF offsets, very long lines, empty/binary input and repeated scans with different roots. Use `tmp_path` and mark resource-heavy cases explicitly rather than checking megabytes of arbitrary data into Git. If a case is inapplicable (e.g., no source traversal in DS119), document why in the story test file.

## Acceptance

- [ ] All 13 directories exist in repository and match these names exactly.
- [ ] Every directory includes one or more `.md` and any required supporting source/config files.
- [ ] At least 3 clean and 3 finding cases are present, independent rather than trivial variations.
- [ ] **All** named edge/negative assertions are implemented and not left as xfail/TODO.
- [ ] No intentionally failing input is 'fixed' or autoformatted by linter scripts.
- [ ] Asset matrix paths and actual committed files are reconciled in a machine-checked inventory test.
