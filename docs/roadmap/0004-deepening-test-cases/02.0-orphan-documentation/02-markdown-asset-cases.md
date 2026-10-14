# Task 02 — Asset-first test corpus for `DS107`

**Story:** [Story 02.0](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/README.md) · **Output root:** `tests/assets/ds107/`

## Mandatory directory shape

```text
tests/assets/ds107/
  {two_to_four_word_case_slug}/
    README.md             # simplest case OR local fixture entrypoint
    a.md                  # when the case compares multiple docs
    b.md                  # when the case compares multiple docs
    src/...py             # only when source evidence is required
    mapping.toml          # only for explicit mappings when required
```

Every case slug is **2–4 clear words** separated by underscores, and **at least one `.md` is mandatory**. Do not place source-only fixtures under a DS216/217/218/316 case. Companion `.py`/`.toml` files are realistic but are not counted as a Markdown test asset. The following exact **14 named scenario directories** must be created.

## Required passing cases (no `DS107` findings)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **CLEAN** | `tests/assets/ds107/reachable_from_index/` | `README.md`, `docs/index.md`, `docs/guide.md` | README links to docs/index.md, which links to docs/guide.md; all three reachable. |
| **CLEAN** | `tests/assets/ds107/reachable_through_chain/` | `README.md`, `a.md`, `b.md`, `c.md` | A nested chain of three linked Markdown pages traverses from root; transitive reachability. |
| **CLEAN** | `tests/assets/ds107/excluded_archive_document/` | `README.md`, `archive/old.md` | Unlinked archived page is explicitly excluded from the scanned document inventory. |
| **CLEAN** | `tests/assets/ds107/reference_style_navigation/` | `README.md`, `guide.md` | Navigation uses a valid Markdown reference-style link definition. |
| **CLEAN** | `tests/assets/ds107/multiple_configured_roots/` | `README.md`, `docs/index.md`, `docs/guide.md` | Two independent configured entrypoints each own a reachable subtree. |

## Required failing cases (`DS107` finding expected)

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **FINDING** | `tests/assets/ds107/unlinked_guide_document/` | `README.md`, `docs/guide.md` | README exists but docs/guide.md has no inbound reachable links: one finding at docs/guide.md. |
| **FINDING** | `tests/assets/ds107/unreachable_document_cycle/` | `README.md`, `a.md`, `b.md` | Two orphan pages link to each other but cannot be reached from README. |
| **FINDING** | `tests/assets/ds107/unlinked_nested_reference/` | `README.md`, `docs/reference/api.md` | Nested docs/reference/api.md is present and not reached from any configured index. |
| **FINDING** | `tests/assets/ds107/self_link_not_reachable/` | `README.md`, `self.md` | An orphan file linking to itself remains orphaned. |
| **FINDING** | `tests/assets/ds107/external_link_not_navigation/` | `README.md`, `guide.md` | Only an external URL mentions guide.md; guide is not locally reachable. |
| **FINDING** | `tests/assets/ds107/fragment_only_navigation/` | `README.md`, `guide.md` | An in-page #anchor cannot make a separate page reachable. |
| **FINDING** | `tests/assets/ds107/code_fence_fake_links/` | `README.md`, `guide.md` | Link-shaped content inside fenced code must not count as a navigation edge. |
| **FINDING** | `tests/assets/ds107/repeated_scan_stable_order/` | `README.md`, `a.md`, `z.md` | Two orphans are reported once each in stable sorted path order. |

## Pending, unsupported and safety edge cases

| Outcome | Case directory | Markdown assets (and companions) | Required behavior |
|---|---|---|---|
| **PENDING** | `tests/assets/ds107/missing_entrypoint_graceful/` | `README.md`, `docs/guide.md` | Configured entrypoint does not exist; cannot prove reachability; report not evaluated, not all orphan. |

## Authoring instructions

- Convert each row into a *miniature realistic repository*. Put meaningful source prose into every Markdown asset, not a generic placeholder that triggers an unrelated rule instead. For a two-document case, a.md/b.md must deliberately share or disagree about the same identifiable concept, as described.
- Where source path examples are listed (e.g. `src/pkg/module.py`) the companion should be minimally syntactically valid and should contain an actual declaration with attributes matching the scenario. Where `mapping.toml` is listed, write a complete sample in the mapping syntax from Task 01.
- For a case whose file inventory lists `README.md` *and* `docs/...md`, README provides index/navigation or the exact documented claim. For cases listing only `a.md`/`b.md`, multi-document comparison operates directly on those files; **create an optional README.md only if the extra document is intentionally part of the scan**. Additional README content must not generate accidental findings.
- The `tests/assets/README.md` convention says copy fixtures byte-for-byte into `tmp_path` via `asset_case`. Preserve deliberate broken Markdown and no-trailing-newline cases.
- Assert `expected=clean` as exactly zero `DS107` findings, *not* necessarily zero findings from other profiles/rules when the integration test composes detectors.
- For `expected=finding`, assert the exact rule code, severity, target file, one-based line when specified, and evidence phrase. Choose a stable report attribution policy for cross-file candidates.
- For `expected=pending`, assert the precise invalid/unverifiable/not-run signal as agreed in Story 01.0, never an empty result with a misleading 'evaluated' notice.

## Runtime-generated additional edge tests

In addition to the committed Markdown assets, create **runtime-generated** tests if this rule reads files/paths: `UnicodeDecodeError`, permission denied, symlink-to-outside-root, nested `../` root escape, Unicode normalization, CRLF offsets, very long lines, empty/binary input and repeated scans with different roots. Use `tmp_path` and mark resource-heavy cases explicitly rather than checking megabytes of arbitrary data into Git. If a case is inapplicable (e.g., no source traversal in DS119), document why in the story test file.

## Acceptance

- [ ] All 14 directories exist in repository and match these names exactly.
- [ ] Every directory includes one or more `.md` and any required supporting source/config files.
- [ ] At least 3 clean and 3 finding cases are present, independent rather than trivial variations.
- [ ] **All** named edge/negative assertions are implemented and not left as xfail/TODO.
- [ ] No intentionally failing input is 'fixed' or autoformatted by linter scripts.
- [ ] Asset matrix paths and actual committed files are reconciled in a machine-checked inventory test.
