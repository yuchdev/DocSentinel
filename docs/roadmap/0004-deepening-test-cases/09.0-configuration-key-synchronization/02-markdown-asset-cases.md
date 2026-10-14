# Task 02 — Asset-first test corpus for `DS217`

**Story:** [Story 09.0](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/README.md) · **Output root:** `tests/assets/ds217/`

## Mandatory directory shape

```text
tests/assets/ds217/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **13 named scenario directories** must be created.

## Required passing cases (no `DS217` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds217/documented_defaults_match/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Configured doc table key retry_count=3 matches supported dataclass literal default 3. |
| **CLEAN** | `tests/assets/ds217/optional_source_key_omitted/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Configured optional key is intentionally not required to appear in docs. |
| **CLEAN** | `tests/assets/ds217/matching_toml_configuration/` | `README.md`, `config/defaults.toml`, `mapping.toml` | Documented TOML snippet matches mapped TOML reference schema values. |
| **CLEAN** | `tests/assets/ds217/boolean_false_matches/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | false is a real typed default and compares correctly to False. |
| **CLEAN** | `tests/assets/ds217/unmapped_prose_number/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Unmapped numbers mentioned in background prose are ignored. |
| **CLEAN** | `tests/assets/ds217/schema_version_scopes/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Version-scoped config examples with distinct defaults are not compared cross-version. |

## Required failing cases (`DS217` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds217/documented_default_mismatch/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Documentation declares retry_count=5 while mapped literal source default is 3. |
| **FINDING** | `tests/assets/ds217/documented_key_not_defined/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | README describes removed key fallback_workers absent from explicitly mapped schema. |
| **FINDING** | `tests/assets/ds217/required_key_not_documented/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Source schema marks a required public key that is absent from selected documentation. |
| **FINDING** | `tests/assets/ds217/numeric_type_mismatch/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | String "3" in documentation is not equal to integer 3 for a typed source field. |
| **FINDING** | `tests/assets/ds217/duplicate_config_key_row/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Two rows for same canonical key with different documented values are flagged deterministically. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds217/factory_default_unknown/` | `README.md`, `src/pkg/settings.py`, `mapping.toml` | Source default_factory or computed function is not statically resolved; emit unverifiable status, not mismatch. |
| **PENDING** | `tests/assets/ds217/schema_source_path_escape/` | `README.md`, `mapping.toml` | Mapping pointing outside scan root fails validation; no external filesystem reads. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS217` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
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
