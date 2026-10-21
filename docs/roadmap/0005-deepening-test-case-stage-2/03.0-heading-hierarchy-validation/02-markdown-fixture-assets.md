# Task 02 — committed Markdown scenario assets for DS105

**Parent story:** [Story 03.0](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/README.md)  
**Target directory:** `tests/assets/ds105/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds105/sequential_heading_levels/` | `README.md` | H1 > H2 > H3, then H2 is a valid hierarchy. | `default` |
| **CLEAN** | `tests/assets/ds105/single_root_heading/` | `README.md` | One top-level title with no subsections. | `default` |
| **CLEAN** | `tests/assets/ds105/setext_then_atx/` | `README.md` | Setext level-one title followed by ATX level-two heading. | `default` |
| **FINDING** | `tests/assets/ds105/first_heading_level_three/` | `README.md` | Document begins with level-three heading under default root-level-one policy. | `default` |
| **FINDING** | `tests/assets/ds105/skipped_intermediate_level/` | `README.md` | H2 followed directly by H4 flags H4 line. | `default` |
| **FINDING** | `tests/assets/ds105/multiple_levels_skipped/` | `README.md` | H1 followed by H5 flags exactly one bad heading, not four. | `default` |
| **CLEAN** | `tests/assets/ds105/heading_inside_code_fence/` | `README.md` | A code block with `###` text does not affect hierarchy. | `default` |
| **CLEAN** | `tests/assets/ds105/heading_inside_html_comment/` | `README.md` | HTML comment containing heading syntax is ignored. | `default` |
| **CLEAN** | `tests/assets/ds105/heading_after_frontmatter/` | `README.md` | YAML frontmatter is skipped before first H1. | `default` |
| **FINDING** | `tests/assets/ds105/optional_multiple_h1_warning/` | `README.md` | Two H1s trigger only when multiple_h1_policy=warn. | `multiple_h1_policy=warn` |
| **CLEAN** | `tests/assets/ds105/optional_nonroot_start/` | `README.md` | First H2 is accepted when first_heading_level=2. | `first_heading_level=2` |
| **CLEAN** | `tests/assets/ds105/blockquote_heading_ignored/` | `README.md` | A quoted example beginning with `> ###` is not a top-level document heading. | `default` |
| **FINDING** | `tests/assets/ds105/crlf_line_accuracy/` | `README.md` | CRLF source lines do not move an H2-to-H4 jump diagnostic. | `default` |
| **CLEAN** | `tests/assets/ds105/heading_symbols_in_prose/` | `README.md` | Inline literal hashes within paragraphs do not count as headings. | `default` |

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
- [ ] Test loader `asset_case("ds105", "scenario")` can copy each directory without modifying fixture text.
