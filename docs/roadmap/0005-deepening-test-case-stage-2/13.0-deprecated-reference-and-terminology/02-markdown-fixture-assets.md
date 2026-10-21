# Task 02 — committed Markdown scenario assets for DS115

**Parent story:** [Story 13.0](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/README.md)  
**Target directory:** `tests/assets/ds115/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds115/only_current_module_name/` | `README.md` | Prose names only current module symbol, not mapped legacy name. | `deprecated-mapping` |
| **CLEAN** | `tests/assets/ds115/historical_archive_exempt/` | `archive/README.md` | Historical archive path is configured exempt even though it quotes old terminology. | `deprecated-mapping;archive-exempt` |
| **CLEAN** | `tests/assets/ds115/substring_of_longer_name/` | `README.md` | Old name `APIv1` is not spuriously matched inside `APIv10`. | `deprecated-mapping` |
| **FINDING** | `tests/assets/ds115/deprecated_module_in_prose/` | `README.md` | Old module path mentioned in prose is flagged with new name. | `deprecated-mapping` |
| **FINDING** | `tests/assets/ds115/deprecated_local_link_path/` | `README.md` | A Markdown local link uses explicitly deprecated path even if it still exists. | `deprecated-mapping` |
| **FINDING** | `tests/assets/ds115/deprecated_identifier_code_span/` | `README.md` | Inline code contains obsolete class name in configured mapping. | `deprecated-mapping` |
| **CLEAN** | `tests/assets/ds115/deprecated_case_sensitive/` | `README.md` | Different casing does not match under case-sensitive policy. | `deprecated-mapping` |
| **FINDING** | `tests/assets/ds115/deprecated_casefolded_optin/` | `README.md` | Case-folded match when explicitly enabled. | `deprecated-mapping;deprecated_case_sensitive=false` |
| **CLEAN** | `tests/assets/ds115/deprecated_in_fenced_example/` | `README.md` | Fenced migration sample is exempt by documented policy. | `deprecated-mapping` |
| **FINDING** | `tests/assets/ds115/multiple_occurrences_same_line/` | `README.md` | Two distinct obsolete occurrences should produce deterministic one-per-occurrence or one-per-line as defined. | `deprecated-mapping` |
| **FINDING** | `tests/assets/ds115/obsolete_name_with_punctuation/` | `README.md` | Deprecated identifier surrounded by punctuation is matched correctly. | `deprecated-mapping` |
| **CLEAN** | `tests/assets/ds115/unconfigured_mapping_is_inert/` | `README.md` | Without mapping, an old-looking token must not be flagged. | `default` |
| **ERROR** | `tests/assets/ds115/invalid_mapping_duplicate_key/` | `README.md` | Companion TOML has duplicate/conflicting replacement sources and must raise ConfigError. | `invalid-deprecated-mapping` |
| **ERROR** | `tests/assets/ds115/mapping_path_outside_root/` | `README.md` | Configured mapping path attempts to escape root; reject before reading. | `unsafe-mapping-path` |

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
- [ ] Test loader `asset_case("ds115", "scenario")` can copy each directory without modifying fixture text.
