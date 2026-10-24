# Stage 2 — complete fixture matrix

**Specification only.** The listed folders do not yet exist as committed test assets. The agent must write the Markdown and companion inputs, not merely reference these paths from unit tests.

**Totals:** 191 named case directories across 13 rule IDs: **96 CLEAN**, **91 FINDING**, **4 ERROR**. Every rule has at least three CLEAN and at least three FINDING cases. ERROR means validation/readiness/security error, never a passing detector with no findings.

**Required path shape:** `tests/assets/dsNNN/{two_to_four_word_slug}/{README|a|b|index|guide}.md`; nested Markdown paths are allowed for realistic graphs and paths. Slugs are snake_case, 2–4 words.

## DS104 — Conflicting heading and explicit anchors

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS105 — Heading hierarchy and section levels

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS106 — Empty or contentless sections

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds106/leaf_section_with_prose/` | `README.md` | Every leaf section has at least one explanatory paragraph. | `default` |
| **CLEAN** | `tests/assets/ds106/parent_with_child_section/` | `README.md` | H2 parent is empty but H3 child has content; parent is structural. | `default` |
| **CLEAN** | `tests/assets/ds106/image_only_leaf_section/` | `README.md` | Section body contains a meaningful image and alt text. | `default` |
| **FINDING** | `tests/assets/ds106/empty_terminal_heading/` | `README.md` | Trailing H2 has no body before EOF. | `default` |
| **FINDING** | `tests/assets/ds106/comment_only_section/` | `README.md` | Only `<!-- forthcoming -->` is present between headings. | `default` |
| **FINDING** | `tests/assets/ds106/whitespace_separator_only/` | `README.md` | Spaces and thematic rules do not count as content. | `default` |
| **CLEAN** | `tests/assets/ds106/nonempty_fenced_example/` | `README.md` | Code example with actual lines counts as content. | `default` |
| **FINDING** | `tests/assets/ds106/blank_fence_content/` | `README.md` | A code fence containing only empty lines is not content. | `default` |
| **FINDING** | `tests/assets/ds106/nested_empty_child/` | `README.md` | H3 child under H2 parent is empty; report leaf H3 only. | `default` |
| **CLEAN** | `tests/assets/ds106/inline_link_body_text/` | `README.md` | A link with text is sufficient visible content. | `default` |
| **CLEAN** | `tests/assets/ds106/table_only_section/` | `README.md` | A well-formed table supplies content. | `default` |
| **FINDING** | `tests/assets/ds106/html_tag_only_section/` | `README.md` | A non-rendering empty span or anchor tag is not content. | `default` |
| **CLEAN** | `tests/assets/ds106/horizontal_rule_then_text/` | `README.md` | A thematic separator precedes actual prose. | `default` |
| **FINDING** | `tests/assets/ds106/multiple_empty_leaf_sections/` | `README.md` | Two terminal leaves lacking content yield two sorted findings. | `default` |

## DS108 — Reference-style link definition integrity

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS109 — Malformed or unclosed fenced code blocks

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS110 — Missing language labels on code fences

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS117 — Malformed GFM pipe-table structure

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds117/valid_two_column_table/` | `README.md` | Header, delimiter, and rows each have two cells. | `default` |
| **CLEAN** | `tests/assets/ds117/aligned_three_column_table/` | `README.md` | Left/center/right delimiter alignment with consistent counts. | `default` |
| **CLEAN** | `tests/assets/ds117/escaped_pipe_cell_text/` | `README.md` | An escaped pipe belongs inside a cell. | `default` |
| **FINDING** | `tests/assets/ds117/extra_body_cell/` | `README.md` | Body row has three cells but header has two. | `default` |
| **FINDING** | `tests/assets/ds117/missing_delimiter_cell/` | `README.md` | Delimiter row has fewer cells than header. | `default` |
| **FINDING** | `tests/assets/ds117/invalid_alignment_marker/` | `README.md` | Delimiter row has malformed `:--:` alignment syntax under supported subset. | `default` |
| **FINDING** | `tests/assets/ds117/missing_body_cell/` | `README.md` | One body row has fewer cells than header under strict policy. | `default` |
| **CLEAN** | `tests/assets/ds117/optional_outer_pipes/` | `README.md` | Table remains valid with leading and trailing pipes omitted. | `default` |
| **CLEAN** | `tests/assets/ds117/empty_cell_is_valid/` | `README.md` | Explicit empty cell between separators counts as a cell. | `default` |
| **CLEAN** | `tests/assets/ds117/code_span_contains_pipe/` | `README.md` | Pipe within inline code span does not split column. | `default` |
| **CLEAN** | `tests/assets/ds117/pipes_in_regular_paragraph/` | `README.md` | Pipes in prose without a delimiter row do not form a table. | `default` |
| **CLEAN** | `tests/assets/ds117/table_inside_code_fence/` | `README.md` | Invalid-looking table in a code fence is ignored. | `default` |
| **FINDING** | `tests/assets/ds117/multiple_broken_tables/` | `README.md` | Two independent broken tables produce separate findings in source order. | `default` |
| **FINDING** | `tests/assets/ds117/crlf_table_line_positions/` | `README.md` | Broken CRLF table identifies offending row line. | `default` |
| **CLEAN** | `tests/assets/ds117/html_table_not_parsed/` | `README.md` | HTML `<table>` is outside this GFM subset and is ignored. | `default` |

## DS112 — Declared documentation navigation integrity

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS113 — Missing local media and document assets

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS116 — Path traversal outside documentation root

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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
| **FINDING** | `tests/assets/ds116/html_anchor_href_escape/` | `README.md` | HTML `<a href>` with ../ traversal is extracted and reported (close-gate fix). | `default` |
| **FINDING** | `tests/assets/ds116/html_img_srcset_escape/` | `README.md` | HTML `srcset` candidate escaping the root is reported (close-gate fix). | `default` |
| **FINDING** | `tests/assets/ds116/angle_bracket_destination_escape/` | `README.md` | `[a](<../../x>)` and `[r]: <../../x>` destinations are unwrapped, then reported (close-gate fix). | `default` |
| **FINDING** | `tests/assets/ds116/entity_encoded_destination_escape/` | `README.md` | Entity-encoded `&#46;&#46;/` destination is decoded before resolving, then reported (close-gate fix). | `default` |
| **FINDING** | `tests/assets/ds116/nested_image_link_escape/` | `README.md` | `[![alt](inner.png)](../../x)` reports the outer destination (close-gate fix). | `default` |
| **FINDING** | `tests/assets/ds116/quoted_refdef_escape/` | `README.md` | Reference definition inside a block quote with an escaping target is reported (close-gate fix). | `default` |

## DS114 — Duplicate stable document identifiers

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
|---|---|---|---|---|
| **CLEAN** | `tests/assets/ds114/distinct_frontmatter_ids/` | `a.md;b.md` | Two Markdown files carry different explicit frontmatter ids. | `default` |
| **CLEAN** | `tests/assets/ds114/missing_optional_ids/` | `a.md;b.md` | Neither doc has an id and the field is optional. | `default` |
| **CLEAN** | `tests/assets/ds114/same_h1_distinct_ids/` | `a.md;b.md` | Identical visible titles but distinct frontmatter ids are allowed. | `default` |
| **FINDING** | `tests/assets/ds114/identical_ids_two_docs/` | `a.md;b.md` | Two Markdown frontmatter records declare id: alpha. | `default` |
| **FINDING** | `tests/assets/ds114/unicode_normalized_ids/` | `a.md;b.md` | NFC-equivalent Unicode IDs collide deterministically. | `default` |
| **FINDING** | `tests/assets/ds114/whitespace_normalized_ids/` | `a.md;b.md` | Scalar id values differing only surrounding whitespace collide. | `default` |
| **FINDING** | `tests/assets/ds114/three_duplicate_document_ids/` | `a.md;b.md;c.md` | Three same IDs produce exactly two findings ordered by path. | `default` |
| **CLEAN** | `tests/assets/ds114/case_distinct_ids_default/` | `a.md;b.md` | IDs Alpha and alpha remain distinct under case-sensitive policy. | `default` |
| **FINDING** | `tests/assets/ds114/casefold_ids_optin/` | `a.md;b.md` | IDs Alpha and alpha collide with case-insensitive policy. | `document_id_case_sensitive=false` |
| **CLEAN** | `tests/assets/ds114/frontmatter_like_prose/` | `a.md;b.md` | An `id: same` line in ordinary body prose is not frontmatter. | `default` |
| **CLEAN** | `tests/assets/ds114/id_in_code_fence/` | `a.md;b.md` | Code example showing id syntax is not metadata. | `default` |
| **FINDING** | `tests/assets/ds114/missing_ids_required/` | `a.md;b.md` | When document_id_required=true, missing id yields explicit metadata-identity finding. | `document_id_required=true` |
| **CLEAN** | `tests/assets/ds114/duplicate_key_one_document/` | `README.md` | Duplicate id keys in same opening frontmatter belong to DS111, not cross-document DS114. | `default` |
| **ERROR** | `tests/assets/ds114/invalid_nested_metadata/` | `README.md` | Unsupported nested YAML must be declared invalid/unsupported, never invent an ID. | `default` |

## DS115 — Deprecated names and migrated references

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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

## DS118 — Documentation file and directory naming policy

| Outcome | Scenario directory | Markdown/companion files | Required assertion | Setup |
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
