# Task 02 — committed Markdown scenario assets for DS113

**Parent story:** [Story 10.0](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/README.md)  
**Target directory:** `tests/assets/ds113/`  
**Requirement:** 15 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds113/relative_image_exists/` | `README.md;images/logo.svg` | Markdown image resolves to existing SVG companion. | `asset-extension-files` |
| **CLEAN** | `tests/assets/ds113/html_image_exists/` | `README.md;images/icon.png` | HTML `<img src>` points to existing local PNG. | `asset-extension-files` |
| **CLEAN** | `tests/assets/ds113/external_image_is_skipped/` | `README.md` | Remote https URL and data URI are not checked locally. | `default` |
| **FINDING** | `tests/assets/ds113/missing_markdown_image/` | `README.md` | Markdown image references absent diagrams/flow.svg. | `default` |
| **FINDING** | `tests/assets/ds113/missing_html_image/` | `README.md` | HTML `<img src="media/missing.png">` references absent file. | `default` |
| **FINDING** | `tests/assets/ds113/missing_srcset_candidate/` | `README.md;images/small.png` | One candidate exists and second high-DPI srcset candidate is absent. | `asset-extension-files` |
| **CLEAN** | `tests/assets/ds113/asset_reference_definition/` | `README.md;images/chart.svg` | Reference-style Markdown image resolves to existing asset. | `asset-extension-files` |
| **CLEAN** | `tests/assets/ds113/alt_text_not_filename/` | `README.md` | Markdown alt text containing path-like string is not an asset path. | `default` |
| **CLEAN** | `tests/assets/ds113/asset_path_from_subdir/` | `docs/README.md;images/plot.svg` | Nested document image path `../images/plot.svg` resolves inside repo. | `asset-extension-files` |
| **CLEAN** | `tests/assets/ds113/template_asset_is_skipped/` | `README.md` | Template `${IMAGE}` or `{asset_path}` is explicitly exempted. | `default` |
| **CLEAN** | `tests/assets/ds113/bad_asset_under_code/` | `README.md` | Missing-image markup inside code fence is ignored. | `default` |
| **FINDING** | `tests/assets/ds113/missing_pdf_attachment/` | `README.md` | A local PDF asset declared in explicitly-supported attachment syntax is absent. | `asset_extensions=["pdf"]` |
| **FINDING** | `tests/assets/ds113/asset_symlink_outside/` | `README.md` | A runtime-created symlink to outside root is rejected, not opened. | `runtime-symlink-companion` |
| **FINDING** | `tests/assets/ds113/percent_encoded_asset_path/` | `README.md` | Percent-encoded relative asset decodes to missing local file with correct path. | `default` |
| **FINDING** | `tests/assets/ds113/multiple_missing_images/` | `README.md` | Two distinct nonexistent local images produce two deterministic diagnostics. | `default` |

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
- [ ] Test loader `asset_case("ds113", "scenario")` can copy each directory without modifying fixture text.
