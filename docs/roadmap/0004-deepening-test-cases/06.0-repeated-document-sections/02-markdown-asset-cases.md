# Task 02 — Asset-first test corpus for `DS207`

**Story:** [Story 06.0](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/README.md) · **Output root:** `tests/assets/ds207/`

## Mandatory directory shape

```text
tests/assets/ds207/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **13 named scenario directories** must be created.

## Required passing cases (no `DS207` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds207/distinct_section_explanations/` | `a.md`, `b.md` | Two same-title sections contain clearly different substantive material. |
| **CLEAN** | `tests/assets/ds207/short_section_exception/` | `a.md`, `b.md` | A repeated small boilerplate section below minimum word threshold is ignored. |
| **CLEAN** | `tests/assets/ds207/code_only_section_bodies/` | `a.md`, `b.md` | Sections containing only code examples are excluded from prose similarity. |
| **CLEAN** | `tests/assets/ds207/identical_heading_only/` | `a.md`, `b.md` | Only headings match, body differs; no finding. |
| **CLEAN** | `tests/assets/ds207/section_body_single_paragraph/` | `a.md`, `b.md` | Single paragraph is DS202 territory and not eligible for DS207. |
| **CLEAN** | `tests/assets/ds207/within_document_repetition/` | `README.md` | Default cross-document scope ignores two similar sections inside one file. |
| **CLEAN** | `tests/assets/ds207/heading_in_fenced_block/` | `a.md`, `b.md` | Fake headings inside a fenced block never become section boundaries. |
| **CLEAN** | `tests/assets/ds207/table_dominated_section/` | `a.md`, `b.md` | Table-only sections are excluded from the prose-driven threshold. |

## Required failing cases (`DS207` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds207/identical_multisection_text/` | `a.md`, `b.md` | Two substantial sections share the same multi-paragraph text; report second one. |
| **FINDING** | `tests/assets/ds207/near_duplicate_section_text/` | `a.md`, `b.md` | Two substantial sections paraphrase a few phrases while retaining high similarity. |
| **FINDING** | `tests/assets/ds207/duplicate_nested_sections/` | `a.md`, `b.md` | Nested H3 sections are identical under separate parent H2 headings. |
| **FINDING** | `tests/assets/ds207/pair_reported_only_once/` | `a.md`, `b.md`, `c.md` | Three similar sections yield stable unique pairs without mirrored duplicates. |
| **FINDING** | `tests/assets/ds207/threshold_boundary_similarity/` | `a.md`, `b.md` | At exactly configured similarity threshold a result is reported. |

## Pending, unsupported and safety edge cases

*No separate pending case listed; edge cases are included in the clean/finding tables above.*

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS207` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
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
