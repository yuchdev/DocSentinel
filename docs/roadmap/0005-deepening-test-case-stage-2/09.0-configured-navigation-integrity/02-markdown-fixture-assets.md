# Task 02 — committed Markdown scenario assets for DS112

**Parent story:** [Story 09.0](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/README.md)  
**Target directory:** `tests/assets/ds112/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds112/required_pages_all_listed/` | `README.md;docs/guide.md;docs/api.md` | Configured navigation README links to both required Markdown targets. | `navigation_indexes=["README.md"];navigation_required=["docs/guide.md","docs/api.md"]` |
| **CLEAN** | `tests/assets/ds112/valid_nested_navigation/` | `README.md;docs/index.md;docs/setup.md` | Nested index references local files in documented navigation structure. | `navigation_indexes=["README.md","docs/index.md"]` |
| **CLEAN** | `tests/assets/ds112/external_navigation_links/` | `README.md` | External product link is not treated as a missing local target. | `navigation_indexes=["README.md"]` |
| **FINDING** | `tests/assets/ds112/missing_required_nav_item/` | `README.md;docs/guide.md` | Required docs/guide.md exists but is absent from index links. | `navigation_indexes=["README.md"];navigation_required=["docs/guide.md"]` |
| **FINDING** | `tests/assets/ds112/duplicate_navigation_target/` | `README.md;docs/guide.md` | Configured index contains two links to same target; second one flagged. | `navigation_indexes=["README.md"]` |
| **FINDING** | `tests/assets/ds112/missing_navigation_destination/` | `README.md` | Configured nav contains local link to nonexistent doc. | `navigation_indexes=["README.md"]` |
| **CLEAN** | `tests/assets/ds112/prose_link_outside_list/` | `README.md` | Broken-looking ordinary prose link is not part of configured navigation. | `navigation_indexes=["README.md"]` |
| **CLEAN** | `tests/assets/ds112/fragment_navigation_is_local/` | `README.md` | Fragment link within same nav document is not an extra document target. | `navigation_indexes=["README.md"]` |
| **CLEAN** | `tests/assets/ds112/reference_style_navigation_item/` | `README.md;docs/guide.md` | Configured nav item uses reference-style link definition. | `navigation_indexes=["README.md"]` |
| **FINDING** | `tests/assets/ds112/duplicate_with_fragments/` | `README.md;docs/guide.md` | Same nav document linked twice with different fragments counts as duplicate target. | `navigation_indexes=["README.md"]` |
| **ERROR** | `tests/assets/ds112/missing_index_is_error/` | `README.md` | Configured index missing must raise/record an explicit config/readiness problem. | `navigation_indexes=["docs/missing.md"]` |
| **CLEAN** | `tests/assets/ds112/nested_relative_nav_path/` | `docs/index.md;docs/guide.md` | Nav path resolves relative to index location, not current process cwd. | `navigation_indexes=["docs/index.md"]` |
| **CLEAN** | `tests/assets/ds112/fake_nav_in_fence/` | `README.md` | An invalid nav link inside a fenced example does not count. | `navigation_indexes=["README.md"]` |
| **FINDING** | `tests/assets/ds112/unsafe_parent_navigation/` | `docs/index.md` | Nav path traverses outside configured scan root, refusing escape. | `navigation_indexes=["docs/index.md"]` |

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
- [ ] Test loader `asset_case("ds112", "scenario")` can copy each directory without modifying fixture text.
