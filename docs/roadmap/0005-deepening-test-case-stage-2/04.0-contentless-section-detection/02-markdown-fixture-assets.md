# Task 02 — committed Markdown scenario assets for DS106

**Parent story:** [Story 04.0](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/README.md)  
**Target directory:** `tests/assets/ds106/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds106/leaf_section_with_prose/` | `README.md` | Every leaf section has at least one explanatory paragraph. | `default` |
| **CLEAN** | `tests/assets/ds106/parent_with_child_section/` | `README.md` | H2 parent is empty but H3 child has content; parent is structural. | `default` |
| **CLEAN** | `tests/assets/ds106/image_only_leaf_section/` | `README.md` | Section body contains a meaningful image and alt text. | `default` |
| **FINDING** | `tests/assets/ds106/empty_terminal_heading/` | `README.md` | Trailing H2 has no body before EOF. | `default` |
| **FINDING** | `tests/assets/ds106/comment_only_section/` | `README.md` | Only `<!-- forthcoming -->` is present between headings. | `default` |
| **FINDING** | `tests/assets/ds106/whitespace_separator_only/` | `README.md` | Spaces and thematic rules do not count as content. | `default` |
| **CLEAN** | `tests/assets/ds106/nonempty_fenced_example/` | `README.md` | Code example with actual lines counts as content. | `default` |
| **FINDING** | `tests/assets/ds106/blank_fence_content/` | `README.md` | A code fence containing only empty lines is not content. | `default` |
| **FINDING** | `tests/assets/ds106/nested_empty_child/` | `README.md` | H3 child under H2 parent is empty; report leaf H3 only. | `default` |
| **CLEAN** | `tests/assets/ds106/inline_link_body_text/` | `README.md` | A link with text is sufficient visible content. | `default` |
| **CLEAN** | `tests/assets/ds106/table_only_section/` | `README.md` | A well-formed table supplies content. | `default` |
| **FINDING** | `tests/assets/ds106/html_tag_only_section/` | `README.md` | A non-rendering empty span or anchor tag is not content. | `default` |
| **CLEAN** | `tests/assets/ds106/horizontal_rule_then_text/` | `README.md` | A thematic separator precedes actual prose. | `default` |
| **FINDING** | `tests/assets/ds106/multiple_empty_leaf_sections/` | `README.md` | Two terminal leaves lacking content yield two sorted findings. | `default` |

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
- [ ] Test loader `asset_case("ds106", "scenario")` can copy each directory without modifying fixture text.
