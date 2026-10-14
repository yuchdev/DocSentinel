# Task 02 — Asset-first test corpus for `DS119`

**Story:** [Story 04.0](/docs/roadmap/0004-deepening-test-cases/04.0-unresolved-migration-markers/README.md) · **Output root:** `tests/assets/ds119/`

## Mandatory directory shape

```text
tests/assets/ds119/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **13 named scenario directories** must be created.

## Required passing cases (no `DS119` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds119/clean_completed_prose/` | `README.md` | A complete section contains no configured markers. |
| **CLEAN** | `tests/assets/ds119/examples_in_code_fence/` | `README.md` | A code sample containing TODO should not be treated as unfinished documentation prose. |
| **CLEAN** | `tests/assets/ds119/literal_inline_marker/` | `README.md` | Inline code `TODO` is descriptive rather than an editorial task. |
| **CLEAN** | `tests/assets/ds119/html_comment_owned_ds102/` | `README.md` | HTML comment containing TODO is not double-reported by DS119. |
| **CLEAN** | `tests/assets/ds119/marker_inside_identifier/` | `README.md` | Method named TODOParser should not trigger word-boundary detection. |
| **CLEAN** | `tests/assets/ds119/marker_in_plain_url/` | `README.md` | URL path containing /TODO/ is not a prose marker. |
| **CLEAN** | `tests/assets/ds119/escaped_marker_literal/` | `README.md` | An escaped literal is excluded by documented escape semantics. |

## Required failing cases (`DS119` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds119/todo_in_paragraph/` | `README.md` | A visible TODO: replace this section marker triggers at exact source line. |
| **FINDING** | `tests/assets/ds119/fixme_section_note/` | `README.md` | Visible FIXME(owner): prose triggers one finding. |
| **FINDING** | `tests/assets/ds119/placeholder_title_text/` | `README.md` | A visible PLACEHOLDER in a heading or paragraph triggers one finding. |
| **FINDING** | `tests/assets/ds119/tbd_punctuation_forms/` | `README.md` | TBD — and TBD: are both recognized as editorial markers. |
| **FINDING** | `tests/assets/ds119/multiple_markers_same_line/` | `README.md` | Two distinct markers on one line yield deterministic independent findings. |
| **FINDING** | `tests/assets/ds119/custom_marker_vocabulary/` | `README.md` | Configured WIP is found and default TODO is ignored when configured replacement is active. |

## Pending, unsupported and safety edge cases

*No separate pending case listed; edge cases are included in the clean/finding tables above.*

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS119` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
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
