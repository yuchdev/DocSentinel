# DocSentinel Milestone 0004 — Master fixture matrix

This is a **specification manifest**, not a claim that the files already exist in the repository. The implementation PR must add each named case under `tests/assets/` and a named integration assertion loading it via `asset_case`.

## Totals by rule

| Rule | Profile | Story | Clean | Finding | Pending | Total |
|---|---|---|---:|---:|---:|---:|
| `DS107` | fast | [02.0](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/README.md) | 5 | 8 | 1 | 14 |
| `DS111` | fast | [03.0](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/README.md) | 6 | 6 | 1 | 13 |
| `DS119` | fast | [04.0](/docs/roadmap/0004-deepening-test-cases/04.0-unresolved-migration-markers/README.md) | 7 | 6 | 0 | 13 |
| `DS205` | standard | [05.0](/docs/roadmap/0004-deepening-test-cases/05.0-terminology-consistency/README.md) | 6 | 5 | 2 | 13 |
| `DS207` | standard | [06.0](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/README.md) | 8 | 5 | 0 | 13 |
| `DS208` | standard | [07.0](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/README.md) | 8 | 5 | 0 | 13 |
| `DS216` | standard | [08.0](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/README.md) | 9 | 3 | 1 | 13 |
| `DS217` | standard | [09.0](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/README.md) | 6 | 5 | 2 | 13 |
| `DS218` | standard | [10.0](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/README.md) | 8 | 3 | 2 | 13 |
| `DS219` | standard | [11.0](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/README.md) | 8 | 4 | 2 | 14 |
| `DS302` | deep | [12.0](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/README.md) | 10 | 5 | 1 | 16 |
| `DS316` | deep | [13.0](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/README.md) | 5 | 8 | 2 | 15 |

**Total cases:** 163. Cases with `clean` are positive/pass, `finding` negative/fail; `pending` tests that unsupported inputs are reported honestly. Every case is a distinct directory and contains one or more real Markdown text assets.

## Exact expected asset paths and behaviors

### DS107 — Orphan documentation

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds107/reachable_from_index/` | `README.md`, `docs/index.md`, `docs/guide.md` | README links to docs/index.md, which links to docs/guide.md; all three reachable. |
| **CLEAN** | `tests/assets/ds107/reachable_through_chain/` | `README.md`, `a.md`, `b.md`, `c.md` | A nested chain of three linked Markdown pages traverses from root; transitive reachability. |
| **CLEAN** | `tests/assets/ds107/excluded_archive_document/` | `README.md`, `archive/old.md` | Unlinked archived page is explicitly excluded from the scanned document inventory. |
| **FINDING** | `tests/assets/ds107/unlinked_guide_document/` | `README.md`, `docs/guide.md` | README exists but docs/guide.md has no inbound reachable links: one finding at docs/guide.md. |
| **FINDING** | `tests/assets/ds107/unreachable_document_cycle/` | `README.md`, `a.md`, `b.md` | Two orphan pages link to each other but cannot be reached from README. |
| **FINDING** | `tests/assets/ds107/unlinked_nested_reference/` | `README.md`, `docs/reference/api.md` | Nested docs/reference/api.md is present and not reached from any configured index. |
| **PENDING** | `tests/assets/ds107/missing_entrypoint_graceful/` | `README.md`, `docs/guide.md` | Configured entrypoint does not exist; cannot prove reachability; report not evaluated, not all orphan. |
| **FINDING** | `tests/assets/ds107/self_link_not_reachable/` | `README.md`, `self.md` | An orphan file linking to itself remains orphaned. |
| **FINDING** | `tests/assets/ds107/external_link_not_navigation/` | `README.md`, `guide.md` | Only an external URL mentions guide.md; guide is not locally reachable. |
| **CLEAN** | `tests/assets/ds107/reference_style_navigation/` | `README.md`, `guide.md` | Navigation uses a valid Markdown reference-style link definition. |
| **FINDING** | `tests/assets/ds107/fragment_only_navigation/` | `README.md`, `guide.md` | An in-page #anchor cannot make a separate page reachable. |
| **CLEAN** | `tests/assets/ds107/multiple_configured_roots/` | `README.md`, `docs/index.md`, `docs/guide.md` | Two independent configured entrypoints each own a reachable subtree. |
| **FINDING** | `tests/assets/ds107/code_fence_fake_links/` | `README.md`, `guide.md` | Link-shaped content inside fenced code must not count as a navigation edge. |
| **FINDING** | `tests/assets/ds107/repeated_scan_stable_order/` | `README.md`, `a.md`, `z.md` | Two orphans are reported once each in stable sorted path order. |

### DS111 — Required document metadata

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds111/valid_required_fields/` | `README.md` | Required title and status are present in opening frontmatter. |
| **CLEAN** | `tests/assets/ds111/valid_quoted_values/` | `README.md` | Simple quoted scalar metadata values satisfy the rule. |
| **CLEAN** | `tests/assets/ds111/outside_selected_paths/` | `README.md` | An unmarked ordinary README outside configured patterns is exempt. |
| **FINDING** | `tests/assets/ds111/missing_title_field/` | `README.md` | Selected document frontmatter lacks required title. |
| **FINDING** | `tests/assets/ds111/empty_status_field/` | `README.md` | Selected document has status: with no scalar value. |
| **FINDING** | `tests/assets/ds111/duplicate_metadata_key/` | `README.md` | Opening frontmatter declares title twice, with conflicting values. |
| **FINDING** | `tests/assets/ds111/no_frontmatter_block/` | `README.md` | Selected document begins with prose and never declares frontmatter. |
| **CLEAN** | `tests/assets/ds111/false_zero_values/` | `README.md` | Fields with literal false and 0 are defined, not missing. |
| **FINDING** | `tests/assets/ds111/unterminated_frontmatter/` | `README.md` | Opening --- has no closing delimiter; report malformed metadata without consuming whole file. |
| **FINDING** | `tests/assets/ds111/mid_document_hr_only/` | `README.md` | A later thematic separator is not frontmatter on a selected doc. |
| **CLEAN** | `tests/assets/ds111/unselected_document_no_findings/` | `README.md`, `docs/guide.md` | Same missing keys do not trigger where path pattern does not match. |
| **PENDING** | `tests/assets/ds111/unsupported_nested_yaml/` | `README.md` | Nested YAML constructs outside the supported scalar subset are not falsely validated. |
| **CLEAN** | `tests/assets/ds111/windows_newline_frontmatter/` | `README.md` | CRLF scalar delimiters are recognized without line offset drift. |

### DS119 — Unresolved migration markers

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds119/clean_completed_prose/` | `README.md` | A complete section contains no configured markers. |
| **CLEAN** | `tests/assets/ds119/examples_in_code_fence/` | `README.md` | A code sample containing TODO should not be treated as unfinished documentation prose. |
| **CLEAN** | `tests/assets/ds119/literal_inline_marker/` | `README.md` | Inline code `TODO` is descriptive rather than an editorial task. |
| **FINDING** | `tests/assets/ds119/todo_in_paragraph/` | `README.md` | A visible TODO: replace this section marker triggers at exact source line. |
| **FINDING** | `tests/assets/ds119/fixme_section_note/` | `README.md` | Visible FIXME(owner): prose triggers one finding. |
| **FINDING** | `tests/assets/ds119/placeholder_title_text/` | `README.md` | A visible PLACEHOLDER in a heading or paragraph triggers one finding. |
| **CLEAN** | `tests/assets/ds119/html_comment_owned_ds102/` | `README.md` | HTML comment containing TODO is not double-reported by DS119. |
| **CLEAN** | `tests/assets/ds119/marker_inside_identifier/` | `README.md` | Method named TODOParser should not trigger word-boundary detection. |
| **CLEAN** | `tests/assets/ds119/marker_in_plain_url/` | `README.md` | URL path containing /TODO/ is not a prose marker. |
| **FINDING** | `tests/assets/ds119/tbd_punctuation_forms/` | `README.md` | TBD — and TBD: are both recognized as editorial markers. |
| **FINDING** | `tests/assets/ds119/multiple_markers_same_line/` | `README.md` | Two distinct markers on one line yield deterministic independent findings. |
| **CLEAN** | `tests/assets/ds119/escaped_marker_literal/` | `README.md` | An escaped literal is excluded by documented escape semantics. |
| **FINDING** | `tests/assets/ds119/custom_marker_vocabulary/` | `README.md` | Configured WIP is found and default TODO is ignored when configured replacement is active. |

### DS205 — Terminology consistency

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds205/canonical_terms_only/` | `README.md`, `terminology.toml` | Docs use CanonixEngine and translation pipeline exclusively. |
| **CLEAN** | `tests/assets/ds205/alias_in_code_example/` | `README.md`, `terminology.toml` | Disallowed alias occurs only inside a code fence and is not evaluated as prose. |
| **CLEAN** | `tests/assets/ds205/alias_in_link_target/` | `README.md`, `terminology.toml` | Alias appears in a URL destination, not visible link label. |
| **FINDING** | `tests/assets/ds205/deprecated_term_in_prose/` | `README.md`, `terminology.toml` | Configured alias translation chain occurs as visible prose and maps to translation pipeline. |
| **FINDING** | `tests/assets/ds205/wrong_product_spelling/` | `README.md`, `terminology.toml` | Alias Canonix Engine is found in a heading and corrected to CanonixEngine. |
| **FINDING** | `tests/assets/ds205/alias_inside_link_label/` | `README.md`, `terminology.toml` | Visible Markdown link label contains deprecated term. |
| **CLEAN** | `tests/assets/ds205/case_sensitive_alias/` | `README.md`, `terminology.toml` | Capitalization is valid under configured exact-case policy. |
| **FINDING** | `tests/assets/ds205/unicode_word_boundary/` | `README.md`, `terminology.toml` | Configured non-ASCII alias is matched on Unicode word boundaries. |
| **CLEAN** | `tests/assets/ds205/substring_not_full_term/` | `README.md`, `terminology.toml` | Alias `arc` must not match `architecture` or `arcade`. |
| **PENDING** | `tests/assets/ds205/conflicting_alias_definitions/` | `README.md`, `terminology.toml` | Ambiguous alias mapped to two canonical forms fails configuration validation, not prose lint. |
| **CLEAN** | `tests/assets/ds205/quoted_legacy_term/` | `README.md`, `terminology.toml` | Explicit quotation opt-out syntax marks historic terminology with a documented exemption. |
| **FINDING** | `tests/assets/ds205/repeated_alias_locations/` | `README.md`, `terminology.toml` | Two occurrences on different lines are each located; ordering is stable. |
| **PENDING** | `tests/assets/ds205/dictionary_missing_file/` | `README.md` | Configured dictionary path missing: report configuration failure, not a clean corpus. |

### DS207 — Repeated document sections

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds207/distinct_section_explanations/` | `a.md`, `b.md` | Two same-title sections contain clearly different substantive material. |
| **CLEAN** | `tests/assets/ds207/short_section_exception/` | `a.md`, `b.md` | A repeated small boilerplate section below minimum word threshold is ignored. |
| **CLEAN** | `tests/assets/ds207/code_only_section_bodies/` | `a.md`, `b.md` | Sections containing only code examples are excluded from prose similarity. |
| **FINDING** | `tests/assets/ds207/identical_multisection_text/` | `a.md`, `b.md` | Two substantial sections share the same multi-paragraph text; report second one. |
| **FINDING** | `tests/assets/ds207/near_duplicate_section_text/` | `a.md`, `b.md` | Two substantial sections paraphrase a few phrases while retaining high similarity. |
| **FINDING** | `tests/assets/ds207/duplicate_nested_sections/` | `a.md`, `b.md` | Nested H3 sections are identical under separate parent H2 headings. |
| **CLEAN** | `tests/assets/ds207/identical_heading_only/` | `a.md`, `b.md` | Only headings match, body differs; no finding. |
| **CLEAN** | `tests/assets/ds207/section_body_single_paragraph/` | `a.md`, `b.md` | Single paragraph is DS202 territory and not eligible for DS207. |
| **CLEAN** | `tests/assets/ds207/within_document_repetition/` | `README.md` | Default cross-document scope ignores two similar sections inside one file. |
| **FINDING** | `tests/assets/ds207/pair_reported_only_once/` | `a.md`, `b.md`, `c.md` | Three similar sections yield stable unique pairs without mirrored duplicates. |
| **FINDING** | `tests/assets/ds207/threshold_boundary_similarity/` | `a.md`, `b.md` | At exactly configured similarity threshold a result is reported. |
| **CLEAN** | `tests/assets/ds207/heading_in_fenced_block/` | `a.md`, `b.md` | Fake headings inside a fenced block never become section boundaries. |
| **CLEAN** | `tests/assets/ds207/table_dominated_section/` | `a.md`, `b.md` | Table-only sections are excluded from the prose-driven threshold. |

### DS208 — Near duplicate documents

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds208/different_topic_documents/` | `a.md`, `b.md` | Two substantial documents describe disjoint architecture topics. |
| **CLEAN** | `tests/assets/ds208/short_identical_documents/` | `a.md`, `b.md` | Two tiny identical pages are below minimum-document length. |
| **CLEAN** | `tests/assets/ds208/shared_template_distinct_body/` | `a.md`, `b.md` | Common frontmatter and navigation with different substantive bodies is allowed. |
| **FINDING** | `tests/assets/ds208/identical_full_documents/` | `a.md`, `b.md` | Two substantive docs have identical normalized prose. |
| **FINDING** | `tests/assets/ds208/minor_reworded_documents/` | `a.md`, `b.md` | A nearly identical guide differs only by small prose edits. |
| **FINDING** | `tests/assets/ds208/repeated_mirror_copy/` | `a.md`, `docs/copy.md` | A copied page inside docs/duplicates is compared and flagged. |
| **CLEAN** | `tests/assets/ds208/cross_language_documents/` | `a.md`, `b.md` | Different language translations are excluded by configured language scope rather than blindly compared. |
| **CLEAN** | `tests/assets/ds208/identical_code_only_documents/` | `a.md`, `b.md` | Code-only pages are below prose threshold. |
| **CLEAN** | `tests/assets/ds208/empty_documents_ignored/` | `a.md`, `b.md` | Empty or frontmatter-only pages are ignored by this similarity rule. |
| **FINDING** | `tests/assets/ds208/three_copies_unique_pairs/` | `a.md`, `b.md`, `c.md` | Three near-copies produce once-per-pair deterministic findings. |
| **FINDING** | `tests/assets/ds208/threshold_equal_matches/` | `a.md`, `b.md` | Similarity at configured threshold is included. |
| **CLEAN** | `tests/assets/ds208/code_fences_noise_excluded/` | `a.md`, `b.md` | Matching long code listings with different prose do not imply duplicate documents. |
| **CLEAN** | `tests/assets/ds208/generated_directory_excluded/` | `a.md`, `generated/b.md` | Explicitly excluded generated docs do not participate. |

### DS216 — Stale source symbol references

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds216/existing_public_function/` | `README.md`, `src/pkg/module.py`, `src/pkg/__init__.py` | README refers to local package.module.process(), which exists. |
| **CLEAN** | `tests/assets/ds216/external_library_reference/` | `README.md`, `src/pkg/module.py` | Reference to stdlib/pathlib.Path is not claimed to be an in-repo symbol. |
| **CLEAN** | `tests/assets/ds216/valid_class_method_symbol/` | `README.md`, `src/pkg/module.py` | README refers to local module.Worker.run that exists. |
| **FINDING** | `tests/assets/ds216/removed_function_reference/` | `README.md`, `src/pkg/module.py`, `src/pkg/__init__.py` | README refers to qualified local pkg.module.old_api(), absent from the symbol index. |
| **FINDING** | `tests/assets/ds216/misspelled_class_method/` | `README.md`, `src/pkg/module.py` | README refers to local Worker.execut(), while only execute() exists. |
| **FINDING** | `tests/assets/ds216/removed_module_reference/` | `README.md`, `src/pkg/__init__.py`, `src/pkg/module.py` | README links qualified pkg.legacy.helper() but no local module or mapped symbol exists. |
| **CLEAN** | `tests/assets/ds216/backtick_ambiguous_name/` | `README.md`, `src/pkg/module.py` | Plain `run()` without module context is not automatically assumed to be local. |
| **CLEAN** | `tests/assets/ds216/decorator_alias_function/` | `README.md`, `src/pkg/module.py` | Statically declared alias resolves to an existing function. |
| **CLEAN** | `tests/assets/ds216/nested_class_definition/` | `README.md`, `src/pkg/module.py` | Nested class symbol is indexed with complete qualified path. |
| **CLEAN** | `tests/assets/ds216/dynamic_getattr_reference/` | `README.md`, `src/pkg/module.py` | Documented dynamic attribute is exempt unless explicit static mapping proves otherwise. |
| **CLEAN** | `tests/assets/ds216/symbol_inside_code_fence/` | `README.md`, `src/pkg/module.py` | Standalone example code does not create a symbol-reference claim by default. |
| **PENDING** | `tests/assets/ds216/python_source_syntax_error/` | `README.md`, `src/pkg/module.py` | Broken source AST must yield an actionable scan error/pending state, never a clean symbol audit. |
| **CLEAN** | `tests/assets/ds216/symlink_outside_code_root/` | `README.md`, `src/pkg/module.py` | Never follow symlink escapes when indexing source paths. |

### DS217 — Configuration key synchronization

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds217/documented_defaults_match/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Configured doc table key retry_count=3 matches supported dataclass literal default 3. |
| **CLEAN** | `tests/assets/ds217/optional_source_key_omitted/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Configured optional key is intentionally not required to appear in docs. |
| **CLEAN** | `tests/assets/ds217/matching_toml_configuration/` | `README.md`, `config/defaults.toml`, `mapping.toml` | Documented TOML snippet matches mapped TOML reference schema values. |
| **FINDING** | `tests/assets/ds217/documented_default_mismatch/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Documentation declares retry_count=5 while mapped literal source default is 3. |
| **FINDING** | `tests/assets/ds217/documented_key_not_defined/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | README describes removed key fallback_workers absent from explicitly mapped schema. |
| **FINDING** | `tests/assets/ds217/required_key_not_documented/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Source schema marks a required public key that is absent from selected documentation. |
| **PENDING** | `tests/assets/ds217/factory_default_unknown/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Source default_factory or computed function is not statically resolved; emit unverifiable status, not mismatch. |
| **CLEAN** | `tests/assets/ds217/boolean_false_matches/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | false is a real typed default and compares correctly to False. |
| **FINDING** | `tests/assets/ds217/numeric_type_mismatch/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | String "3" in documentation is not equal to integer 3 for a typed source field. |
| **CLEAN** | `tests/assets/ds217/unmapped_prose_number/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Unmapped numbers mentioned in background prose are ignored. |
| **CLEAN** | `tests/assets/ds217/schema_version_scopes/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Version-scoped config examples with distinct defaults are not compared cross-version. |
| **PENDING** | `tests/assets/ds217/schema_source_path_escape/` | `README.md`, `mapping.toml` | Mapping pointing outside scan root fails validation; no external filesystem reads. |
| **FINDING** | `tests/assets/ds217/duplicate_config_key_row/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Two rows for same canonical key with different documented values are flagged deterministically. |

### DS218 — CLI option synchronization

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds218/matching_argument_flags/` | `README.md`, `src/tool.py`, `mapping.toml` | Mapped docs list --timeout and --max-retries that exist with matching defaults. |
| **CLEAN** | `tests/assets/ds218/valid_short_alias_flag/` | `README.md`, `src/tool.py`, `mapping.toml` | Mapped docs use -t alias for --timeout, both declared by argparse. |
| **CLEAN** | `tests/assets/ds218/internal_flag_not_required/` | `README.md`, `src/tool.py`, `mapping.toml` | An internal/private flag omitted from docs does not trigger completeness unless explicitly required. |
| **FINDING** | `tests/assets/ds218/removed_option_in_docs/` | `README.md`, `src/tool.py`, `mapping.toml` | README documents --obsolete but argparse no longer defines it. |
| **FINDING** | `tests/assets/ds218/wrong_argument_default/` | `README.md`, `src/tool.py`, `mapping.toml` | README default 60 contrasts with parser literal default 30. |
| **FINDING** | `tests/assets/ds218/missing_required_public_flag/` | `README.md`, `src/tool.py`, `mapping.toml` | Completeness enabled; public --max-retries omitted from reference table. |
| **CLEAN** | `tests/assets/ds218/unrelated_shell_snippet_flag/` | `README.md`, `src/tool.py`, `mapping.toml` | A shell example unrelated to mapped CLI reference contains --temporary; ignore it. |
| **CLEAN** | `tests/assets/ds218/argparse_boolean_actions/` | `README.md`, `src/tool.py`, `mapping.toml` | Documented `--verbose` store_true default agrees with argparse behavior. |
| **CLEAN** | `tests/assets/ds218/subcommand_scoped_options/` | `README.md`, `src/tool.py`, `mapping.toml` | Different subcommands own flags of same name without false conflicts. |
| **PENDING** | `tests/assets/ds218/computed_arg_default_unknown/` | `README.md`, `src/tool.py`, `mapping.toml` | Env-derived default cannot be safely resolved; report as unknown rather than mismatch. |
| **CLEAN** | `tests/assets/ds218/parser_aliases_same_action/` | `README.md`, `src/tool.py`, `mapping.toml` | Flag aliases map to one argparse action and do not inflate required count. |
| **PENDING** | `tests/assets/ds218/dynamic_flag_registration/` | `README.md`, `src/tool.py`, `mapping.toml` | Custom parser builder cannot be statically analyzed; mark unsupported. |
| **CLEAN** | `tests/assets/ds218/argument_inside_code_fence/` | `README.md`, `src/tool.py`, `mapping.toml` | Ordinary fenced shell example is not the official option reference. |

### DS219 — Documented code example syntax

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds219/valid_python_example/` | `README.md` | Complete ```python check=syntax fenced code parses with ast.parse. |
| **CLEAN** | `tests/assets/ds219/valid_json_example/` | `README.md` | Explicit JSON fence with object validates using json.loads. |
| **CLEAN** | `tests/assets/ds219/valid_toml_example/` | `README.md` | Explicit TOML fence parses with tomllib.loads. |
| **FINDING** | `tests/assets/ds219/invalid_python_indentation/` | `README.md` | Explicit Python example contains indentation SyntaxError; flag precise line. |
| **FINDING** | `tests/assets/ds219/invalid_json_trailing_comma/` | `README.md` | Explicit JSON example has a trailing comma not allowed in JSON. |
| **FINDING** | `tests/assets/ds219/invalid_toml_assignment/` | `README.md` | Explicit TOML code block contains invalid assignment syntax. |
| **CLEAN** | `tests/assets/ds219/partial_python_snippet_unmarked/` | `README.md` | Illustrative fragment without check=syntax is not automatically validated. |
| **CLEAN** | `tests/assets/ds219/python_repl_transcript/` | `README.md` | A ```pycon transcript is unsupported/skipped, never executed. |
| **PENDING** | `tests/assets/ds219/fence_language_not_supported/` | `README.md` | Explicit check=syntax for unsupported bash block yields clear unsupported warning/pending. |
| **FINDING** | `tests/assets/ds219/two_fences_distinct_lines/` | `README.md` | One valid and one invalid marked fence yield exactly one finding at invalid source line. |
| **CLEAN** | `tests/assets/ds219/nested_backtick_fence/` | `README.md` | Fence with nontrivial delimiter run parses closing marker correctly. |
| **CLEAN** | `tests/assets/ds219/html_comment_in_code/` | `README.md` | Text resembling HTML comment inside a Python string is still Python syntax. |
| **PENDING** | `tests/assets/ds219/giant_code_block_limit/` | `README.md` | Configured size limit prevents pathological parse time without giving false clean. |
| **CLEAN** | `tests/assets/ds219/never_execute_side_effect/` | `README.md` | Python example `raise RuntimeError` is parseable; verification must never run it. |

### DS302 — Numeric contradiction candidates

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds302/consistent_worker_limits/` | `a.md`, `b.md` | Two docs assert maximum workers=8 for same version/context. |
| **CLEAN** | `tests/assets/ds302/distinct_limit_qualifiers/` | `a.md`, `b.md` | One doc says default workers=8 and another max workers=16: not contradictory. |
| **CLEAN** | `tests/assets/ds302/equivalent_memory_units/` | `a.md`, `b.md` | 1 GiB and 1024 MiB are equal when unit and binary scaling match. |
| **FINDING** | `tests/assets/ds302/conflicting_worker_maxima/` | `a.md`, `b.md` | Two docs assert max concurrent workers=8 versus 16 for identical scope. |
| **FINDING** | `tests/assets/ds302/conflicting_retry_defaults/` | `a.md`, `b.md` | Two docs assert default retries=3 versus 5 with same identity. |
| **FINDING** | `tests/assets/ds302/disjoint_numeric_ranges/` | `a.md`, `b.md` | Accepted port range 8000-8100 conflicts with 8200-8300 under same scope. |
| **CLEAN** | `tests/assets/ds302/different_product_versions/` | `a.md`, `b.md` | Version 1 and version 2 legitimately use different limits. |
| **CLEAN** | `tests/assets/ds302/different_unit_dimensions/` | `a.md`, `b.md` | 5 seconds versus 5 requests are incomparable, not contradictions. |
| **CLEAN** | `tests/assets/ds302/spelled_numbers_match_digits/` | `a.md`, `b.md` | Eight and 8 normalize to same magnitude when clearly attached to same property. |
| **CLEAN** | `tests/assets/ds302/comparison_operator_overlap/` | `a.md`, `b.md` | “At least 8” and “at most 16” constraints have nonempty intersection. |
| **FINDING** | `tests/assets/ds302/opposing_exclusive_bounds/` | `a.md`, `b.md` | “Greater than 10” and “less than 10” under same scope have no intersection. |
| **CLEAN** | `tests/assets/ds302/claim_inside_code_block/` | `a.md`, `b.md` | Numbers inside fenced code are not free-prose facts. |
| **CLEAN** | `tests/assets/ds302/unqualified_number_prose/` | `a.md`, `b.md` | Two unrelated numeric mentions have no safely matching subject/property. |
| **CLEAN** | `tests/assets/ds302/decimal_precision_tolerance/` | `a.md`, `b.md` | 5.0 and 5 are equivalent where numeric precision carries no separate semantics. |
| **PENDING** | `tests/assets/ds302/invalid_numeric_expression/` | `a.md`, `b.md` | Malformed quantitative phrase is skipped with candidate-extraction coverage notice. |
| **FINDING** | `tests/assets/ds302/deduplicate_claim_pairs/` | `a.md`, `b.md`, `c.md` | Three docs with conflicting values yield deterministically deduplicated candidate pair findings. |

### DS316 — Documentation change impact

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds316/unrelated_source_change/` | `README.md`, `docs/guide.md`, `src/unrelated.py` | Changed unrelated module has no mapped documentation references. |
| **CLEAN** | `tests/assets/ds316/unchanged_referenced_source/` | `README.md`, `docs/guide.md`, `src/tool.py` | A documented module exists but is absent from explicit changed set. |
| **CLEAN** | `tests/assets/ds316/excluded_document_ignored/` | `README.md`, `docs/ignored.md`, `src/tool.py` | Documentation excluded from inventory never receives impact finding. |
| **FINDING** | `tests/assets/ds316/changed_linked_source_file/` | `README.md`, `src/tool.py` | README links to src/tool.py and it is in changed set: one advisory finding. |
| **FINDING** | `tests/assets/ds316/changed_documented_symbol/` | `README.md`, `src/pkg/worker.py`, `src/pkg/__init__.py` | Docs explicitly reference pkg.worker.run; changed pkg/worker.py is linked via symbol index. |
| **FINDING** | `tests/assets/ds316/changed_config_schema_source/` | `README.md`, `src/config.py`, `mapping.toml` | Docs map config schema to src/config.py; changed schema source prompts review. |
| **PENDING** | `tests/assets/ds316/changed_files_missing/` | `README.md`, `src/tool.py` | No --changed-file and no API changed_paths; explicitly not evaluated. |
| **FINDING** | `tests/assets/ds316/duplicate_changed_paths/` | `README.md`, `src/tool.py` | Repeated path from list and normalized `./` variant yield one finding. |
| **PENDING** | `tests/assets/ds316/outside_root_change_path/` | `README.md`, `src/tool.py` | ../secret.py path rejected; do not traverse outside scan root. |
| **FINDING** | `tests/assets/ds316/bounded_transitive_mapping/` | `README.md`, `docs/architecture.md`, `src/tool.py`, `mapping.toml` | Curated docs dependency mapping routes source change to one additional docs page. |
| **FINDING** | `tests/assets/ds316/dependency_cycle_no_repeat/` | `README.md`, `docs/a.md`, `docs/b.md`, `src/tool.py`, `mapping.toml` | A dependency cycle terminates and each affected doc appears at most once. |
| **CLEAN** | `tests/assets/ds316/code_fence_path_reference/` | `README.md`, `src/tool.py` | A source-looking string in code fence is not evidence of a doc-to-source dependency. |
| **FINDING** | `tests/assets/ds316/deleted_source_change_path/` | `README.md` | Deleted source path still matches a recorded documentation reference without requiring the file to exist. |
| **FINDING** | `tests/assets/ds316/relative_paths_normalized/` | `README.md`, `src/tool.py` | src/./tool.py normalizes to src/tool.py, preserving evidence and stable paths. |
| **CLEAN** | `tests/assets/ds316/unmapped_dynamic_reference/` | `README.md`, `src/tool.py` | A speculative NLP similarity without explicit link/mapping does not produce impact. |


## Fixture implementation gate

See [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md). All slug names are exactly 2–4 words. Paths are generated from the matrix, not guessed from fixture tests. These cases are **mandatory**, not illustrative; additional corner cases found during implementation should be added with a new 2–4-word slug and test.
