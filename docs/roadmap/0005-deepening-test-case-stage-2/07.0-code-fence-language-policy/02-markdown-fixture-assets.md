# Task 02 — committed Markdown scenario assets for DS110

**Parent story:** [Story 07.0](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/README.md)  
**Target directory:** `tests/assets/ds110/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds110/python_fence_label/` | `README.md` | A python-labeled fence containing code is clean. | `require_fence_languages=true` |
| **CLEAN** | `tests/assets/ds110/text_fence_label/` | `README.md` | Plain text deliberately labeled text is clean. | `require_fence_languages=true` |
| **CLEAN** | `tests/assets/ds110/unlabelled_when_disabled/` | `README.md` | A code block without label passes with default policy off. | `default` |
| **FINDING** | `tests/assets/ds110/unlabelled_python_example/` | `README.md` | Nonempty code fence lacking label is flagged under opt-in. | `require_fence_languages=true` |
| **FINDING** | `tests/assets/ds110/blank_info_string_only/` | `README.md` | Only whitespace after opening fence counts as no language. | `require_fence_languages=true` |
| **FINDING** | `tests/assets/ds110/unlabelled_tilde_example/` | `README.md` | Unlabeled tilde fence with meaningful content is flagged. | `require_fence_languages=true` |
| **CLEAN** | `tests/assets/ds110/empty_fence_exemption/` | `README.md` | Empty closed fence is exempt under allow_unlabelled_empty_fences=true. | `require_fence_languages=true` |
| **FINDING** | `tests/assets/ds110/empty_fence_strict_policy/` | `README.md` | Empty closed fence flagged when explicit exemption disabled. | `require_fence_languages=true;allow_unlabelled_empty_fences=false` |
| **CLEAN** | `tests/assets/ds110/custom_language_allowed/` | `README.md` | Language label `mermaid` passes an explicit allowlist. | `require_fence_languages=true;allowed_fence_languages=["mermaid"]` |
| **FINDING** | `tests/assets/ds110/unknown_language_optin/` | `README.md` | Unsupported label flagged when allowlist is configured. | `require_fence_languages=true;allowed_fence_languages=["python"]` |
| **CLEAN** | `tests/assets/ds110/shell_session_label/` | `README.md` | `console` is accepted as ordinary language label. | `require_fence_languages=true` |
| **CLEAN** | `tests/assets/ds110/malformed_fence_not_repeated/` | `README.md` | An unclosed fence only belongs to DS109; DS110 emits zero duplicates. | `require_fence_languages=true` |
| **FINDING** | `tests/assets/ds110/multiple_unlabelled_blocks/` | `README.md` | Two distinct unlabelled fenced blocks yield two findings. | `require_fence_languages=true` |
| **CLEAN** | `tests/assets/ds110/language_with_attributes/` | `README.md` | Language marker with supported trailing attributes is recognized as labeled. | `require_fence_languages=true` |

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
- [ ] Test loader `asset_case("ds110", "scenario")` can copy each directory without modifying fixture text.
