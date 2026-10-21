# Task 02 — committed Markdown scenario assets for DS118

**Parent story:** [Story 14.0](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/README.md)  
**Target directory:** `tests/assets/ds118/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds118/lower_kebab_docs_paths/` | `README.md;docs/getting-started.md` | Kebab-case doc paths pass when style=kebab. | `documentation_naming=kebab` |
| **CLEAN** | `tests/assets/ds118/readme_index_exemptions/` | `README.md;docs/index.md` | Canonical special filenames remain exempt. | `documentation_naming=kebab` |
| **CLEAN** | `tests/assets/ds118/allowed_numeric_adr_prefix/` | `docs/adr/0001-fast-path.md` | Numeric prefix accepted under explicit ADR pattern. | `documentation_naming=kebab;adr-prefix-allow` |
| **FINDING** | `tests/assets/ds118/uppercase_filename_violation/` | `docs/GettingStarted.md` | Uppercase filename violates selected kebab case. | `documentation_naming=kebab` |
| **FINDING** | `tests/assets/ds118/spaces_in_filename_violation/` | `docs/Quick Start.md` | Spaces in filename require a rename suggestion. | `documentation_naming=kebab` |
| **FINDING** | `tests/assets/ds118/underscore_kebab_violation/` | `docs/quick_start.md` | Underscore violates selected kebab naming. | `documentation_naming=kebab` |
| **FINDING** | `tests/assets/ds118/hyphen_snake_violation/` | `docs/quick-start.md` | Hyphen violates selected snake naming. | `documentation_naming=snake` |
| **FINDING** | `tests/assets/ds118/uppercase_directory_violation/` | `Docs/README.md` | Directory component casing violates configured policy. | `documentation_naming=kebab` |
| **CLEAN** | `tests/assets/ds118/naming_disabled_is_inert/` | `docs/Getting Started.md` | Style=off permits arbitrary but valid repo file names. | `default` |
| **CLEAN** | `tests/assets/ds118/deep_nested_clean_paths/` | `docs/user-guides/advanced-setup.md` | Multiple kebab components pass. | `documentation_naming=kebab` |
| **FINDING** | `tests/assets/ds118/unicode_filename_policy/` | `docs/café-guide.md` | Unicode filename outside portable ASCII naming policy is reported under strict style. | `documentation_naming=kebab` |
| **CLEAN** | `tests/assets/ds118/excluded_vendor_directory/` | `vendor/SomeDoc.md` | Excluded imported docs must not be checked. | `documentation_naming=kebab;exclude=["vendor"]` |
| **FINDING** | `tests/assets/ds118/multiple_bad_components/` | `BadDocs/Quick_Start.md` | Both directory and file naming violations are reported deterministically. | `documentation_naming=kebab` |
| **FINDING** | `tests/assets/ds118/camelcase_path_diagnostic/` | `docs/apiClient.md` | Camelcase filename is rejected with suggested api-client.md. | `documentation_naming=kebab` |

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
- [ ] Test loader `asset_case("ds118", "scenario")` can copy each directory without modifying fixture text.
