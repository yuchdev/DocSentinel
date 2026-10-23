# Milestone 0005 — Deepening Test Case Stage 2

**Repository:** https://github.com/yuchdev/DocSentinel  
**Milestone path:** `docs/roadmap/0005-deepening-test-case-stage-2/`  
**Audited master SHA:** `48ddf303b6f9b87c901833b29e8d75ffa3543950` (2026-10-14)  
**Status:** specification only; **no new DS104–118 detectors or assets are claimed implemented**  
**Dependencies:** Milestones 0001–0003 complete; Milestone 0004 specification exists on master but its planned detector implementation was not present in this inspected commit.

## Goal

Complete all **13 remaining `fast` DS1xx rules** from the original proposed 19-rule fast catalog, following M4's asset-first test discipline. Focus Stage 2 on **Markdown structure, navigation, asset/path integrity, and documentation governance**, instead of mixing very different NLP and AST tasks. All new runtime analyzers remain **stdlib-only**, deterministic, safe for frequent hooks/CI and compatible with current `docsentinel` CLI/library/pytest/baselines.

When M4's planned DS107, DS111 and DS119 land, this milestone closes the continuous `DS101`–`DS119` fast family. This does **not** imply that M4 has been implemented already.

## Why these rules form one coherent subset

1. **Block-structure cluster (DS104, DS105, DS106, DS109, DS110, DS117):** one shared fence/heading/inline parser supplies consistent source locations; no duplicated fragile regexp logic.
2. **Reference/navigation/path cluster (DS108, DS112, DS113, DS116):** share normalized Markdown link resolution and validated local path handling, keeping DS101/DS103 stable.
3. **Governance cluster (DS114, DS115, DS118):** use explicit metadata/mapping/naming policies rather than guessing human intent; natural boundary with M4 DS111/DS205/DS119.

Out of scope: remaining DS2xx prose/NLP/corpus rules (DS206, DS209–215, DS220–223) and DS3xx advanced semantic rules (DS303–315), which are suitable for subsequent milestones. No LLM calls, execution of document examples, network link checking, mass file renames, or automatic fixers.

## Stories

| Story | Deliverable | Rule | Depends on |
|---|---|---|---|
| [01.0](/docs/roadmap/0005-deepening-test-case-stage-2/01.0-shared-fast-markdown-infrastructure/README.md) | Shared markdown tokens, config and asset catalog | Shared | Existing 0001–0003 + check 0004 landing |
| [02.0](/docs/roadmap/0005-deepening-test-case-stage-2/02.0-anchor-identity-and-collisions/README.md) | Conflicting heading and explicit anchors | DS104 | 01.0; DS107/DS111 shared M4 as relevant |
| [03.0](/docs/roadmap/0005-deepening-test-case-stage-2/03.0-heading-hierarchy-validation/README.md) | Heading hierarchy and section levels | DS105 | 01.0; DS107/DS111 shared M4 as relevant |
| [04.0](/docs/roadmap/0005-deepening-test-case-stage-2/04.0-contentless-section-detection/README.md) | Empty or contentless sections | DS106 | 01.0; DS107/DS111 shared M4 as relevant |
| [05.0](/docs/roadmap/0005-deepening-test-case-stage-2/05.0-reference-definition-integrity/README.md) | Reference-style link definition integrity | DS108 | 01.0; DS107/DS111 shared M4 as relevant |
| [06.0](/docs/roadmap/0005-deepening-test-case-stage-2/06.0-fenced-code-boundary-validation/README.md) | Malformed or unclosed fenced code blocks | DS109 | 01.0; DS107/DS111 shared M4 as relevant |
| [07.0](/docs/roadmap/0005-deepening-test-case-stage-2/07.0-code-fence-language-policy/README.md) | Missing language labels on code fences | DS110 | 01.0; DS107/DS111 shared M4 as relevant |
| [08.0](/docs/roadmap/0005-deepening-test-case-stage-2/08.0-pipe-table-structural-validation/README.md) | Malformed GFM pipe-table structure | DS117 | 01.0; DS107/DS111 shared M4 as relevant |
| [09.0](/docs/roadmap/0005-deepening-test-case-stage-2/09.0-configured-navigation-integrity/README.md) | Declared documentation navigation integrity | DS112 | 01.0; DS107/DS111 shared M4 as relevant |
| [10.0](/docs/roadmap/0005-deepening-test-case-stage-2/10.0-missing-local-media-assets/README.md) | Missing local media and document assets | DS113 | 01.0; DS107/DS111 shared M4 as relevant |
| [11.0](/docs/roadmap/0005-deepening-test-case-stage-2/11.0-repository-root-path-boundaries/README.md) | Path traversal outside documentation root | DS116 | 01.0; DS107/DS111 shared M4 as relevant |
| [12.0](/docs/roadmap/0005-deepening-test-case-stage-2/12.0-document-identity-uniqueness/README.md) | Duplicate stable document identifiers | DS114 | 01.0; DS107/DS111 shared M4 as relevant |
| [13.0](/docs/roadmap/0005-deepening-test-case-stage-2/13.0-deprecated-reference-and-terminology/README.md) | Deprecated names and migrated references | DS115 | 01.0; DS107/DS111 shared M4 as relevant |
| [14.0](/docs/roadmap/0005-deepening-test-case-stage-2/14.0-documentation-path-naming-policy/README.md) | Documentation file and directory naming policy | DS118 | 01.0; DS107/DS111 shared M4 as relevant |
| [15.0](/docs/roadmap/0005-deepening-test-case-stage-2/15.0-cross-rule-quality-and-release/README.md) | Full fast-profile regression and release integration | Shared | All detector stories |

## Mandatory test corpus

- **13 rules**, **15 stories**, **45 detailed story tasks** (3 per story), **185 named scenario directories**.
  Amended 2026-10-23: the matrix now has 191 scenarios (185 specified + 6 DS116 close-gate fixtures; see status.md)
- **At least three independent CLEAN and three FINDING scenarios per rule**; edge/unsupported/security cases additionally specified in `fixture-matrix.md`, `fixture-matrix.csv` and `fixture-matrix.json`.
- Every directory MUST be created as `tests/assets/dsNNN/{two_to_four_word_snake_case_slug}/` and MUST have **at least one real `.md`**. One-file cases use `README.md`; multi-file cases use `a.md`/`b.md` or meaningful relative paths.
- Support files (small local SVG/media, mapping TOML, symlinks generated at runtime) do not substitute for Markdown. Preserve deliberate broken text and exact line/byte boundaries.
- Every specified fixture has a test reference and explicit expected status; no single Markdown file impersonates multiple independently counted cases.
- Error cases in manifest are **validation/security errors**, not negative detector findings; assert appropriate error/unsupported handling.

## Recommended delivery order / PR boundaries

1. **Story 01.0** first: inspect newest M4 implementation; select/reuse one scanner, resolve Analyzer/Config context, define hard fixture catalog gate. Merge independently.
2. **Structure track:** DS109 (fence parser), DS105 (heading levels), DS104 (anchor identity), DS106 (sections), DS110 (languages), DS117 (pipe tables). Dependencies: DS104/105/106 require scanner, DS110 requires DS109; DS117 needs fence/code masking.
3. **Reference track:** DS116 (safe path resolver) first, then DS108 definitions and DS113 assets, followed by DS112 nav (also reuse M4 DS107 graph if available).
4. **Governance track:** DS114 (on M4 DS111 metadata), DS115 (explicit rename mapping and DS205 boundary), DS118 (path naming policy). Can proceed in parallel after Story 01.0.
5. **Story 15.0** last: manifest-to-assets test, all profiles/selection/report/baseline/CI, performance/security and docs. Do not close 0005 if fixture matrix is only documented, not committed and exercised.

## Profile contracts and defaults

Only exact `profile=fast` selects these new codes. `fast` must not eagerly import optional NLP or scikit-learn. Optional policy rules DS110, DS112, DS115, DS118 default **off or not-applicable** until explicit user configuration, instead of unexpected build-breaking warnings. Rule-specific severity/default controls are in each story.

Source-of-truth precedence: current repository implementation after rebase, `implementation-contracts.md` here, M4 shared contracts if merged, then per-rule story spec. If changing a published interface is unavoidable, create an explicit compatibility task and tests rather than silent edits.

## Acceptance criteria

- [ ] 13 new stable rule codes `DS104`, `DS105`, `DS106`, `DS108`, `DS109`, `DS110`, `DS112`, `DS113`, `DS114`, `DS115`, `DS116`, `DS117`, `DS118` registered exactly once, correct severities, correct profile, no regression to DS101–103.
- [ ] All **185 named** scenario directories exist, have Markdown contents, are tested by `asset_case`, assert specified CLEAN/FINDING/ERROR outcomes; >=3 CLEAN and >=3 FINDING in each `dsNNN` tree.
  Amended 2026-10-23: the matrix now has 191 scenarios (185 specified + 6 DS116 close-gate fixtures; see status.md)
- [ ] Shared scanner behavior and exact one-based line/path mapping validated on CRLF, no-newline, fences, escapes and Unicode.
- [ ] Config loads both standalone `doc_sentinel.toml` and `[tool.doc_sentinel]` and preserves strict unknown-key checks; optional rules are honest when disabled.
- [ ] Scan selection/ignore, deterministic order, JSON/text/github output and baselines remain compatible.
- [ ] Real unsafe paths and symlinks never accessed outside scan root; HTML/image refs do not cause network fetches or code execution.
- [ ] CI runs the new rule fixture catalog plus unit/mock/integration/E2E; self-scan excludes intentionally invalid fixtures; standard/deep regressions remain green.
- [ ] Roadmap index, docs/tutorials, sample config and milestone status updated only when completed.

## Reference documents

- [Implementation contracts](/docs/roadmap/0005-deepening-test-case-stage-2/implementation-contracts.md)
- [Scenario manifest](/docs/roadmap/0005-deepening-test-case-stage-2/fixture-matrix.md)
- [Task execution guide](/docs/roadmap/0005-deepening-test-case-stage-2/execution-guide.md)
- [Story/status index](/docs/roadmap/0005-deepening-test-case-stage-2/status.md)
- Existing patterns: `/docs/roadmap/0004-deepening-test-cases/plan.md`, `/tests/assets/README.md`, `/CLAUDE.md`.
