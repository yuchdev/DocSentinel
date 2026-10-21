# Task 02 — committed Markdown scenario assets for DS117

**Parent story:** [Story 08.0](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/README.md)  
**Target directory:** `tests/assets/ds117/`  
**Requirement:** 15 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds117/valid_two_column_table/` | `README.md` | Header, delimiter, and rows each have two cells. | `default` |
| **CLEAN** | `tests/assets/ds117/aligned_three_column_table/` | `README.md` | Left/center/right delimiter alignment with consistent counts. | `default` |
| **CLEAN** | `tests/assets/ds117/escaped_pipe_cell_text/` | `README.md` | An escaped pipe belongs inside a cell. | `default` |
| **FINDING** | `tests/assets/ds117/extra_body_cell/` | `README.md` | Body row has three cells but header has two. | `default` |
| **FINDING** | `tests/assets/ds117/missing_delimiter_cell/` | `README.md` | Delimiter row has fewer cells than header. | `default` |
| **FINDING** | `tests/assets/ds117/invalid_alignment_marker/` | `README.md` | Delimiter row has malformed `:--:` alignment syntax under supported subset. | `default` |
| **FINDING** | `tests/assets/ds117/missing_body_cell/` | `README.md` | One body row has fewer cells than header under strict policy. | `default` |
| **CLEAN** | `tests/assets/ds117/optional_outer_pipes/` | `README.md` | Table remains valid with leading and trailing pipes omitted. | `default` |
| **CLEAN** | `tests/assets/ds117/empty_cell_is_valid/` | `README.md` | Explicit empty cell between separators counts as a cell. | `default` |
| **CLEAN** | `tests/assets/ds117/code_span_contains_pipe/` | `README.md` | Pipe within inline code span does not split column. | `default` |
| **CLEAN** | `tests/assets/ds117/pipes_in_regular_paragraph/` | `README.md` | Pipes in prose without a delimiter row do not form a table. | `default` |
| **CLEAN** | `tests/assets/ds117/table_inside_code_fence/` | `README.md` | Invalid-looking table in a code fence is ignored. | `default` |
| **FINDING** | `tests/assets/ds117/multiple_broken_tables/` | `README.md` | Two independent broken tables produce separate findings in source order. | `default` |
| **FINDING** | `tests/assets/ds117/crlf_table_line_positions/` | `README.md` | Broken CRLF table identifies offending row line. | `default` |
| **CLEAN** | `tests/assets/ds117/html_table_not_parsed/` | `README.md` | HTML `<table>` is outside this GFM subset and is ignored. | `default` |

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
- [ ] Test loader `asset_case("ds117", "scenario")` can copy each directory without modifying fixture text.
