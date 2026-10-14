# Task 02 — Asset-first test corpus for `DS219`

**Story:** [Story 11.0](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/README.md) · **Output root:** `tests/assets/ds219/`

## Mandatory directory shape

```text
tests/assets/ds219/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **14 named scenario directories** must be created.

## Required passing cases (no `DS219` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds219/valid_python_example/` | `README.md` | Complete ```python check=syntax fenced code parses with ast.parse. |
| **CLEAN** | `tests/assets/ds219/valid_json_example/` | `README.md` | Explicit JSON fence with object validates using json.loads. |
| **CLEAN** | `tests/assets/ds219/valid_toml_example/` | `README.md` | Explicit TOML fence parses with tomllib.loads. |
| **CLEAN** | `tests/assets/ds219/partial_python_snippet_unmarked/` | `README.md` | Illustrative fragment without check=syntax is not automatically validated. |
| **CLEAN** | `tests/assets/ds219/python_repl_transcript/` | `README.md` | A ```pycon transcript is unsupported/skipped, never executed. |
| **CLEAN** | `tests/assets/ds219/nested_backtick_fence/` | `README.md` | Fence with nontrivial delimiter run parses closing marker correctly. |
| **CLEAN** | `tests/assets/ds219/html_comment_in_code/` | `README.md` | Text resembling HTML comment inside a Python string is still Python syntax. |
| **CLEAN** | `tests/assets/ds219/never_execute_side_effect/` | `README.md` | Python example `raise RuntimeError` is parseable; verification must never run it. |

## Required failing cases (`DS219` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds219/invalid_python_indentation/` | `README.md` | Explicit Python example contains indentation SyntaxError; flag precise line. |
| **FINDING** | `tests/assets/ds219/invalid_json_trailing_comma/` | `README.md` | Explicit JSON example has a trailing comma not allowed in JSON. |
| **FINDING** | `tests/assets/ds219/invalid_toml_assignment/` | `README.md` | Explicit TOML code block contains invalid assignment syntax. |
| **FINDING** | `tests/assets/ds219/two_fences_distinct_lines/` | `README.md` | One valid and one invalid marked fence yield exactly one finding at invalid source line. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds219/fence_language_not_supported/` | `README.md` | Explicit check=syntax for unsupported bash block yields clear unsupported warning/pending. |
| **PENDING** | `tests/assets/ds219/giant_code_block_limit/` | `README.md` | Configured size limit prevents pathological parse time without giving false clean. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS219` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
- For `expected=finding`, assert the exact rule code, severity, target file, one-based line when specified, and evidence phrase. Choose a stable report attribution policy for cross-file candidates.
- For `expected=pending`, assert the precise invalid/unverifiable/not-run signal as agreed in Story 01.0, never an empty result with a misleading 'evaluated' notice.

## Runtime-generated additional edge tests

In addition to the committed Markdown assets, create **runtime-generated** tests if this rule reads files/paths: `UnicodeDecodeError`, permission denied, symlink-to-outside-root, nested `../` root escape, Unicode normalization, CRLF offsets, very long lines, empty/binary input and repeated scans with different roots. Use `tmp_path` and mark resource-heavy cases explicitly rather than checking megabytes of arbitrary data into Git. If a case is inapplicable (e.g., no source traversal in DS119), document why in the story test file.

## Acceptance

- [ ] All 14 directories exist in repository and match these names exactly.
- [ ] Every directory includes one or more `.md` and any required supporting source/config files.
- [ ] At least 3 clean and 3 finding cases are present, independent rather than trivial variations.
- [ ] **All** named edge/negative assertions are implemented and not left as xfail/TODO.
- [ ] No intentionally failing input is 'fixed' or autoformatted by linter scripts.
- [ ] Asset matrix paths and actual committed files are reconciled in a machine-checked inventory test.
