# Task 02 — committed Markdown scenario assets for DS114

**Parent story:** [Story 12.0](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/README.md)  
**Target directory:** `tests/assets/ds114/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds114/distinct_frontmatter_ids/` | `a.md;b.md` | Two Markdown files carry different explicit frontmatter ids. | `default` |
| **CLEAN** | `tests/assets/ds114/missing_optional_ids/` | `a.md;b.md` | Neither doc has an id and the field is optional. | `default` |
| **CLEAN** | `tests/assets/ds114/same_h1_distinct_ids/` | `a.md;b.md` | Identical visible titles but distinct frontmatter ids are allowed. | `default` |
| **FINDING** | `tests/assets/ds114/identical_ids_two_docs/` | `a.md;b.md` | Two Markdown frontmatter records declare id: alpha. | `default` |
| **FINDING** | `tests/assets/ds114/unicode_normalized_ids/` | `a.md;b.md` | NFC-equivalent Unicode IDs collide deterministically. | `default` |
| **FINDING** | `tests/assets/ds114/whitespace_normalized_ids/` | `a.md;b.md` | Scalar id values differing only surrounding whitespace collide. | `default` |
| **FINDING** | `tests/assets/ds114/three_duplicate_document_ids/` | `a.md;b.md;c.md` | Three same IDs produce exactly two findings ordered by path. | `default` |
| **CLEAN** | `tests/assets/ds114/case_distinct_ids_default/` | `a.md;b.md` | IDs Alpha and alpha remain distinct under case-sensitive policy. | `default` |
| **FINDING** | `tests/assets/ds114/casefold_ids_optin/` | `a.md;b.md` | IDs Alpha and alpha collide with case-insensitive policy. | `document_id_case_sensitive=false` |
| **CLEAN** | `tests/assets/ds114/frontmatter_like_prose/` | `a.md;b.md` | An `id: same` line in ordinary body prose is not frontmatter. | `default` |
| **CLEAN** | `tests/assets/ds114/id_in_code_fence/` | `a.md;b.md` | Code example showing id syntax is not metadata. | `default` |
| **FINDING** | `tests/assets/ds114/missing_ids_required/` | `a.md;b.md` | When document_id_required=true, missing id yields explicit metadata-identity finding. | `document_id_required=true` |
| **CLEAN** | `tests/assets/ds114/duplicate_key_one_document/` | `README.md` | Duplicate id keys in same opening frontmatter belong to DS111, not cross-document DS114. | `default` |
| **ERROR** | `tests/assets/ds114/invalid_nested_metadata/` | `README.md` | Unsupported nested YAML must be declared invalid/unsupported, never invent an ID. | `default` |

## Authoring rules

1. Every case slug is exact, 2–4 descriptive English words in snake_case. Create the specified `.md` files with small but realistic content, plus companions (valid image asset, mapping config) when the scenario needs them. For cases requiring runtime symlinks or permission failures, commit the main Markdown and create the unsafe filesystem object **only** inside `tmp_path`.
2. Preserve intent. CLEAN cases must not accidentally contain another own-rule violation; FINDING cases should isolate the intended defect; ERROR cases must exercise explicit safe validation failure.
3. Use real `README.md` for simplest one-file scenarios, `a.md`/`b.md` for comparisons, nested `docs/README.md` / `docs/index.md` when path relative context matters. Do not create a gratuitous extra README that changes graph/source findings.
4. If `setup` is not `default`, write a compact explicit config companion or apply an injected Config override in tests. The text under test must remain committed `.md` input.
5. Keep raw CRLF/no-final-newline where required and create pathological binary bytes or symlink objects only at runtime. No screenshots or inline-only Python fixture texts replace required Markdown assets.
6. Keep assets excluded from production self-scan, style formatters and documentation update hooks. Intentionally bad Markdown is required and **must not be fixed**.
7. New edge cases discovered by the implementation agent must be added as *additional* named case directories with manifest rows and tests, not used as substitutes for these required cases.

## Completion gate

- [ ] All exact directories above exist in the working tree and each has at least one meaningful Markdown file.
- [ ] Every case is listed in the JSON/CSV/Markdown manifest with the same slug, expected outcome and setup.
- [ ] 3+ CLEAN and 3+ FINDING distinct cases, plus edge and ERROR rows.
- [ ] Test loader `asset_case("ds114", "scenario")` can copy each directory without modifying fixture text.
