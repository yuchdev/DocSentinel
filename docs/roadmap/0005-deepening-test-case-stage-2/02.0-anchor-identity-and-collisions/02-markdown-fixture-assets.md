# Task 02 — committed Markdown scenario assets for DS104

**Parent story:** [Story 02.0](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/README.md)  
**Target directory:** `tests/assets/ds104/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds104/duplicate_headings_suffixed/` | `README.md` | Two `## Usage` headings receive distinct usage and usage-1 generated anchors; cross-references work. | `default` |
| **CLEAN** | `tests/assets/ds104/distinct_explicit_anchors/` | `README.md` | Two explicit id attributes identify separate sections. | `default` |
| **CLEAN** | `tests/assets/ds104/same_anchor_other_files/` | `a.md;b.md` | Both documents may independently declare id="details". | `default` |
| **FINDING** | `tests/assets/ds104/duplicate_explicit_ids/` | `README.md` | Two separate `<a id="setup">` tags in one document must report second definition. | `default` |
| **FINDING** | `tests/assets/ds104/duplicate_named_anchors/` | `README.md` | Two `<a name="intro">` tags in one file collide. | `default` |
| **FINDING** | `tests/assets/ds104/explicit_shadow_heading/` | `README.md` | Explicit `<a id="usage">` shadows generated anchor for `## Usage` under configured renderer policy. | `default` |
| **CLEAN** | `tests/assets/ds104/explicit_different_cases/` | `README.md` | Case-distinct HTML IDs `API` and `api` remain distinct. | `default` |
| **CLEAN** | `tests/assets/ds104/anchor_inside_code_fence/` | `README.md` | Repeated HTML anchor markup in a code sample is ignored. | `default` |
| **CLEAN** | `tests/assets/ds104/anchor_inside_html_comment/` | `README.md` | Duplicate-looking anchor in HTML comment is ignored. | `default` |
| **FINDING** | `tests/assets/ds104/three_anchor_occurrences/` | `README.md` | Three explicit identical ids produce exactly two findings; no pairwise explosion. | `default` |
| **FINDING** | `tests/assets/ds104/indented_html_anchor/` | `README.md` | An explicit anchor indented as markup but not an indented code block collides. | `default` |
| **FINDING** | `tests/assets/ds104/generated_suffix_collision/` | `README.md` | An explicit anchor names the generated `usage-1` suffix for a repeated heading. | `default` |
| **CLEAN** | `tests/assets/ds104/inline_literal_anchor_text/` | `README.md` | Inline code showing `<a id="setup">` is not a declaration. | `default` |
| **CLEAN** | `tests/assets/ds104/unicode_heading_normalization/` | `README.md` | Accented heading slug obeys DS101 slugger; no false collision from normalized prose. | `default` |

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
- [ ] Test loader `asset_case("ds104", "scenario")` can copy each directory without modifying fixture text.
