# Task 02 — Asset-first test corpus for `DS208`

**Story:** [Story 07.0](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/README.md) · **Output root:** `tests/assets/ds208/`

## Mandatory directory shape

```text
tests/assets/ds208/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **13 named scenario directories** must be created.

## Required passing cases (no `DS208` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds208/different_topic_documents/` | `a.md`, `b.md` | Two substantial documents describe disjoint architecture topics. |
| **CLEAN** | `tests/assets/ds208/short_identical_documents/` | `a.md`, `b.md` | Two tiny identical pages are below minimum-document length. |
| **CLEAN** | `tests/assets/ds208/shared_template_distinct_body/` | `a.md`, `b.md` | Common frontmatter and navigation with different substantive bodies is allowed. |
| **CLEAN** | `tests/assets/ds208/cross_language_documents/` | `a.md`, `b.md` | Different language translations are excluded by configured language scope rather than blindly compared. |
| **CLEAN** | `tests/assets/ds208/identical_code_only_documents/` | `a.md`, `b.md` | Code-only pages are below prose threshold. |
| **CLEAN** | `tests/assets/ds208/empty_documents_ignored/` | `a.md`, `b.md` | Empty or frontmatter-only pages are ignored by this similarity rule. |
| **CLEAN** | `tests/assets/ds208/code_fences_noise_excluded/` | `a.md`, `b.md` | Matching long code listings with different prose do not imply duplicate documents. |
| **CLEAN** | `tests/assets/ds208/generated_directory_excluded/` | `a.md`, `generated/b.md` | Explicitly excluded generated docs do not participate. |

## Required failing cases (`DS208` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds208/identical_full_documents/` | `a.md`, `b.md` | Two substantive docs have identical normalized prose. |
| **FINDING** | `tests/assets/ds208/minor_reworded_documents/` | `a.md`, `b.md` | A nearly identical guide differs only by small prose edits. |
| **FINDING** | `tests/assets/ds208/repeated_mirror_copy/` | `a.md`, `docs/copy.md` | A copied page inside docs/duplicates is compared and flagged. |
| **FINDING** | `tests/assets/ds208/three_copies_unique_pairs/` | `a.md`, `b.md`, `c.md` | Three near-copies produce once-per-pair deterministic findings. |
| **FINDING** | `tests/assets/ds208/threshold_equal_matches/` | `a.md`, `b.md` | Similarity at configured threshold is included. |

## Pending, unsupported and safety edge cases

*No separate pending case listed; edge cases are included in the clean/finding tables above.*

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS208` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
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
