# Task 02 — Asset-first test corpus for `DS302`

**Story:** [Story 12.0](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/README.md) · **Output root:** `tests/assets/ds302/`

## Mandatory directory shape

```text
tests/assets/ds302/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **16 named scenario directories** must be created.

## Required passing cases (no `DS302` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds302/consistent_worker_limits/` | `a.md`, `b.md` | Two docs assert maximum workers=8 for same version/context. |
| **CLEAN** | `tests/assets/ds302/distinct_limit_qualifiers/` | `a.md`, `b.md` | One doc says default workers=8 and another max workers=16: not contradictory. |
| **CLEAN** | `tests/assets/ds302/equivalent_memory_units/` | `a.md`, `b.md` | 1 GiB and 1024 MiB are equal when unit and binary scaling match. |
| **CLEAN** | `tests/assets/ds302/different_product_versions/` | `a.md`, `b.md` | Version 1 and version 2 legitimately use different limits. |
| **CLEAN** | `tests/assets/ds302/different_unit_dimensions/` | `a.md`, `b.md` | 5 seconds versus 5 requests are incomparable, not contradictions. |
| **CLEAN** | `tests/assets/ds302/spelled_numbers_match_digits/` | `a.md`, `b.md` | Eight and 8 normalize to same magnitude when clearly attached to same property. |
| **CLEAN** | `tests/assets/ds302/comparison_operator_overlap/` | `a.md`, `b.md` | “At least 8” and “at most 16” constraints have nonempty intersection. |
| **CLEAN** | `tests/assets/ds302/claim_inside_code_block/` | `a.md`, `b.md` | Numbers inside fenced code are not free-prose facts. |
| **CLEAN** | `tests/assets/ds302/unqualified_number_prose/` | `a.md`, `b.md` | Two unrelated numeric mentions have no safely matching subject/property. |
| **CLEAN** | `tests/assets/ds302/decimal_precision_tolerance/` | `a.md`, `b.md` | 5.0 and 5 are equivalent where numeric precision carries no separate semantics. |

## Required failing cases (`DS302` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds302/conflicting_worker_maxima/` | `a.md`, `b.md` | Two docs assert max concurrent workers=8 versus 16 for identical scope. |
| **FINDING** | `tests/assets/ds302/conflicting_retry_defaults/` | `a.md`, `b.md` | Two docs assert default retries=3 versus 5 with same identity. |
| **FINDING** | `tests/assets/ds302/disjoint_numeric_ranges/` | `a.md`, `b.md` | Accepted port range 8000-8100 conflicts with 8200-8300 under same scope. |
| **FINDING** | `tests/assets/ds302/opposing_exclusive_bounds/` | `a.md`, `b.md` | “Greater than 10” and “less than 10” under same scope have no intersection. |
| **FINDING** | `tests/assets/ds302/deduplicate_claim_pairs/` | `a.md`, `b.md`, `c.md` | Three docs with conflicting values yield deterministically deduplicated candidate pair findings. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds302/invalid_numeric_expression/` | `a.md`, `b.md` | Malformed quantitative phrase is skipped with candidate-extraction coverage notice. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS302` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
- For `expected=finding`, assert the exact rule code, severity, target file, one-based line when specified, and evidence phrase. Choose a stable report attribution policy for cross-file candidates.
- For `expected=pending`, assert the precise invalid/unverifiable/not-run signal as agreed in Story 01.0, never an empty result with a misleading 'evaluated' notice.

## Runtime-generated additional edge tests

In addition to the committed Markdown assets, create **runtime-generated** tests if this rule reads files/paths: `UnicodeDecodeError`, permission denied, symlink-to-outside-root, nested `../` root escape, Unicode normalization, CRLF offsets, very long lines, empty/binary input and repeated scans with different roots. Use `tmp_path` and mark resource-heavy cases explicitly rather than checking megabytes of arbitrary data into Git. If a case is inapplicable (e.g., no source traversal in DS119), document why in the story test file.

## Acceptance

- [ ] All 16 directories exist in repository and match these names exactly.
- [ ] Every directory includes one or more `.md` and any required supporting source/config files.
- [ ] At least 3 clean and 3 finding cases are present, independent rather than trivial variations.
- [ ] **All** named edge/negative assertions are implemented and not left as xfail/TODO.
- [ ] No intentionally failing input is 'fixed' or autoformatted by linter scripts.
- [ ] Asset matrix paths and actual committed files are reconciled in a machine-checked inventory test.
