# Task 02 — committed Markdown scenario assets for DS116

**Parent story:** [Story 11.0](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/README.md)  
**Target directory:** `tests/assets/ds116/`  
**Requirement:** 15 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds116/nested_parent_within_root/` | `docs/README.md;guide.md` | Relative `../guide.md` stays inside root and resolves. | `default` |
| **CLEAN** | `tests/assets/ds116/root_relative_local_link/` | `README.md;docs/guide.md` | Link to `/docs/guide.md` stays inside scan root. | `default` |
| **CLEAN** | `tests/assets/ds116/external_https_url/` | `README.md` | Absolute https:// URL is external, not filesystem path. | `default` |
| **FINDING** | `tests/assets/ds116/parent_escape_from_root/` | `README.md` | `../../secrets.md` attempts traversal above scan root. | `default` |
| **FINDING** | `tests/assets/ds116/percent_encoded_parent_escape/` | `README.md` | `%2e%2e/%2e%2e/file.md` must decode and be rejected. | `default` |
| **FINDING** | `tests/assets/ds116/windows_absolute_drive_path/` | `README.md` | `C:\Windows\win.ini` interpreted as unsafe local path, not relative Markdown target. | `default` |
| **FINDING** | `tests/assets/ds116/windows_unc_network_path/` | `README.md` | UNC path `\\server\share` does not resolve within root. | `default` |
| **FINDING** | `tests/assets/ds116/symlink_escape_is_rejected/` | `README.md` | Runtime symlink from docs to parent outside root must not be traversed. | `runtime-symlink-companion` |
| **FINDING** | `tests/assets/ds116/encoded_separator_escape/` | `README.md` | Encoded slash/backslash must not conceal parent traversal. | `default` |
| **CLEAN** | `tests/assets/ds116/safe_parent_link_subdir/` | `docs/deep/README.md;docs/guide.md` | `../guide.md` stays in docs subtree. | `default` |
| **FINDING** | `tests/assets/ds116/unsafe_image_target/` | `README.md` | Markdown image source attempts ../../ filesystem escape. | `default` |
| **FINDING** | `tests/assets/ds116/unsafe_code_span_target/` | `README.md` | Explicit path-like code span attempts to name outside-root file. | `default` |
| **FINDING** | `tests/assets/ds116/encoded_double_decode_attack/` | `README.md` | Double-encoded traversal cannot trick detector into dereference; conservative reject or explicit unsupported state. | `default` |
| **FINDING** | `tests/assets/ds116/absolute_rooted_backslash/` | `README.md` | Windows-rooted `\Windows\...` is not silently considered local. | `default` |
| **CLEAN** | `tests/assets/ds116/template_link_literal_skipped/` | `README.md` | Templated path containing `{...}` is ignored by existing DS101 conventions. | `default` |

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
- [ ] Test loader `asset_case("ds116", "scenario")` can copy each directory without modifying fixture text.
