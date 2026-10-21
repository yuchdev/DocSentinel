# Task 02 — committed Markdown scenario assets for DS109

**Parent story:** [Story 06.0](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/README.md)  
**Target directory:** `tests/assets/ds109/`  
**Requirement:** 14 *different case directories*, not one parameterized string; at least three CLEAN and three FINDING. Every case directory below must contain a committed Markdown file.

## Exact scenario manifest

| Expected | Case path | Required files | Evidence to construct | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds109/valid_backtick_fence/` | `README.md` | Three backticks open and close a code fence. | `default` |
| **CLEAN** | `tests/assets/ds109/valid_longer_closer/` | `README.md` | Closer with five ticks closes a three-tick opener. | `default` |
| **CLEAN** | `tests/assets/ds109/valid_tilde_fence/` | `README.md` | Paired tilde fences are accepted. | `default` |
| **FINDING** | `tests/assets/ds109/unterminated_fence_eof/` | `README.md` | A backtick opener has no closing delimiter by EOF. | `default` |
| **FINDING** | `tests/assets/ds109/wrong_fence_character/` | `README.md` | Tilde closing run does not terminate a backtick opener. | `default` |
| **FINDING** | `tests/assets/ds109/shorter_closing_run/` | `README.md` | A two-character closer fails to close a four-character opener. | `default` |
| **FINDING** | `tests/assets/ds109/closing_with_extra_text/` | `README.md` | Putative closer with illegal trailing content leaves the fence unclosed. | `default` |
| **CLEAN** | `tests/assets/ds109/indented_literal_ticks/` | `README.md` | Four-space indented backticks are not an opening fenced block. | `default` |
| **CLEAN** | `tests/assets/ds109/fence_with_info_string/` | `README.md` | Known language info string on opener is allowed. | `default` |
| **FINDING** | `tests/assets/ds109/backtick_in_info_string/` | `README.md` | Backtick-containing info string violates backtick fence opener rules. | `default` |
| **FINDING** | `tests/assets/ds109/multiple_unterminated_blocks/` | `README.md` | A long opening fence swallows later pseudo-openers; one original opener finding, no quadratic cascade. | `default` |
| **FINDING** | `tests/assets/ds109/crlf_fence_positions/` | `README.md` | Unclosed CRLF fence reports correct opening line. | `default` |
| **CLEAN** | `tests/assets/ds109/nested_opposite_marker/` | `README.md` | Tildes appear as literal content inside a backtick fenced block. | `default` |
| **CLEAN** | `tests/assets/ds109/fence_trailing_whitespace/` | `README.md` | Trailing spaces after valid closing fence are permitted. | `default` |

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
- [ ] Test loader `asset_case("ds109", "scenario")` can copy each directory without modifying fixture text.
