# Task 02 — committed Markdown scenario assets for DS108

**Parent story:** [Story 05.0](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/README.md)  
**Target directory:** `tests/assets/ds108/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds108/resolved_reference_definition/` | `README.md` | Full reference link matches a local definition. | `default` |
| **CLEAN** | `tests/assets/ds108/collapsed_reference_label/` | `README.md` | Collapsed form `[Guide][]` matches normalized Guide declaration. | `default` |
| **CLEAN** | `tests/assets/ds108/case_folded_reference_labels/` | `README.md` | Multiword label with mixed case resolves after CommonMark normalization. | `default` |
| **FINDING** | `tests/assets/ds108/missing_explicit_reference/` | `README.md` | Explicit `[text][missing]` with no definition triggers one finding. | `default` |
| **FINDING** | `tests/assets/ds108/duplicate_reference_labels/` | `README.md` | Two normalized definitions share the same label; flag second declaration. | `default` |
| **FINDING** | `tests/assets/ds108/undefined_image_reference/` | `README.md` | Image syntax `![alt][diagram]` lacks its definition. | `default` |
| **FINDING** | `tests/assets/ds108/unused_definition_enabled/` | `README.md` | Unused definition warned when policy is explicitly enabled. | `unused_reference_definitions=true` |
| **CLEAN** | `tests/assets/ds108/unused_definition_disabled/` | `README.md` | Unused declaration is ignored under default backward-compatible policy. | `default` |
| **CLEAN** | `tests/assets/ds108/reference_inside_fence/` | `README.md` | A broken reference-looking token occurs only inside code fence. | `default` |
| **CLEAN** | `tests/assets/ds108/escaped_bracket_not_reference/` | `README.md` | Escaped reference syntax is rendered literally and ignored. | `default` |
| **CLEAN** | `tests/assets/ds108/footnote_reference_ignored/` | `README.md` | A footnote marker is not checked as an ordinary link ref. | `default` |
| **FINDING** | `tests/assets/ds108/duplicate_whitespace_labels/` | `README.md` | Labels differing solely by collapsed whitespace are duplicates. | `default` |
| **CLEAN** | `tests/assets/ds108/reference_definition_with_url/` | `README.md;guide.md` | Reference definition points at existing local guide; DS108 should report no label problem. | `default` |
| **FINDING** | `tests/assets/ds108/multiple_missing_references/` | `README.md` | Two distinct undefined labels produce two sorted findings. | `default` |

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
- [ ] Test loader `asset_case("ds108", "scenario")` can copy each directory without modifying fixture text.
