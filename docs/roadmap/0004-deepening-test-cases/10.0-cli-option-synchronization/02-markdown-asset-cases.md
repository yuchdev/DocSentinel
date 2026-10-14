# Task 02 — Asset-first test corpus for `DS218`

**Story:** [Story 10.0](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/README.md) · **Output root:** `tests/assets/ds218/`

## Mandatory directory shape

```text
tests/assets/ds218/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **13 named scenario directories** must be created.

## Required passing cases (no `DS218` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds218/matching_argument_flags/` | `README.md`, `src/tool.py`, `mapping.toml` | Mapped docs list --timeout and --max-retries that exist with matching defaults. |
| **CLEAN** | `tests/assets/ds218/valid_short_alias_flag/` | `README.md`, `src/tool.py`, `mapping.toml` | Mapped docs use -t alias for --timeout, both declared by argparse. |
| **CLEAN** | `tests/assets/ds218/internal_flag_not_required/` | `README.md`, `src/tool.py`, `mapping.toml` | An internal/private flag omitted from docs does not trigger completeness unless explicitly required. |
| **CLEAN** | `tests/assets/ds218/unrelated_shell_snippet_flag/` | `README.md`, `src/tool.py`, `mapping.toml` | A shell example unrelated to mapped CLI reference contains --temporary; ignore it. |
| **CLEAN** | `tests/assets/ds218/argparse_boolean_actions/` | `README.md`, `src/tool.py`, `mapping.toml` | Documented `--verbose` store_true default agrees with argparse behavior. |
| **CLEAN** | `tests/assets/ds218/subcommand_scoped_options/` | `README.md`, `src/tool.py`, `mapping.toml` | Different subcommands own flags of same name without false conflicts. |
| **CLEAN** | `tests/assets/ds218/parser_aliases_same_action/` | `README.md`, `src/tool.py`, `mapping.toml` | Flag aliases map to one argparse action and do not inflate required count. |
| **CLEAN** | `tests/assets/ds218/argument_inside_code_fence/` | `README.md`, `src/tool.py`, `mapping.toml` | Ordinary fenced shell example is not the official option reference. |

## Required failing cases (`DS218` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds218/removed_option_in_docs/` | `README.md`, `src/tool.py`, `mapping.toml` | README documents --obsolete but argparse no longer defines it. |
| **FINDING** | `tests/assets/ds218/wrong_argument_default/` | `README.md`, `src/tool.py`, `mapping.toml` | README default 60 contrasts with parser literal default 30. |
| **FINDING** | `tests/assets/ds218/missing_required_public_flag/` | `README.md`, `src/tool.py`, `mapping.toml` | Completeness enabled; public --max-retries omitted from reference table. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds218/computed_arg_default_unknown/` | `README.md`, `src/tool.py`, `mapping.toml` | Env-derived default cannot be safely resolved; report as unknown rather than mismatch. |
| **PENDING** | `tests/assets/ds218/dynamic_flag_registration/` | `README.md`, `src/tool.py`, `mapping.toml` | Custom parser builder cannot be statically analyzed; mark unsupported. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS218` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
- For `expected=finding`, assert the exact rule code, severity, target file, one-based line when specified, and evidence phrase. Choose a stable report attribution policy for cross-file candidates.
- For `expected=pending`, assert the precise invalid/unverifiable/not-run signal as agreed in Story 01.0, never an empty result with a misleading 'evaluated' notice.

## Runtime-generated additional edge tests

In addition to the committed Markdown assets, create **runtime-generated** tests if this rule reads files/paths: `UnicodeDecodeError`, permission denied, symlink-to-outside-root, nested `../` root escape, Unicode normalization, CRLF offsets, very long lines, empty/binary input and repeated scans with different roots. Use `tmp_path` and mark resource-heavy cases explicitly rather than checking megabytes of arbitrary data into Git. If a case is inapplicable (e.g., no source traversal in DS119), document why in the story test file.

## Acceptance

- [ ] All 13 directories exist in repository and match these names exactly.
- [ ] Every directory includes one or more `.md` and any required supporting source/config files.
- [ ] At least 3 clean and 3 finding cases are present, independent rather than trivial variations.
- [ ] **All** named edge/negative assertions are implemented and not left as xfail/TODO.
- [ ] No intentionally failing input is 'fixed' or autoformatted by linter scripts.
- [ ] Asset matrix paths and actual committed files are reconciled in a machine-checked inventory test.
