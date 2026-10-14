# Milestone 0004 — Deepening Test Cases

**GitHub-ready directory name:** `docs/roadmap/0004-deepening-test-cases/`  
**Repository:** [`yuchdev/DocSentinel`](https://github.com/yuchdev/DocSentinel)  
**Observed master:** `04a3eb337f7b75d1783cd4a7f45da2c68528113b` (October 14, 2026).  
**Status:** Specification prepared; **none of the 12 new rules is asserted implemented**.  
**Task structure:** Milestone → Story → Task (per `docs/roadmap/README.md`).

## Goal

Implement **12 new documentation QA detectors** across the established exact `fast`, `standard`, and `deep` profiles, while making substantial real-world test corpora the central acceptance deliverable. Every rule must generate its own repository-committed **Markdown text assets** in the precise shape `tests/assets/dsNNN/{two_to_four_word_slug}/{README|a|b|index|other}.md` and tests that load those assets.

This milestone is intentionally titled **Deepening Test Cases** rather than merely **More Detectors**: rules without rigorous positive/negative/edge fixtures are incomplete. Preserve existing DS101–DS301 behavior, CI, baseline and report contracts.

## Repository audit incorporated into this specification

- M1 fast DS101–103, M2 standard DS201–204 and M3 deep DS301 are present in `src/docsentinel` on current master; `docs/roadmap/0001..0003/status.md` mark all done.
- New test architecture exists: `tests/assets/README.md`, `tests/asset_helpers.py`, `tests/conftest.py`, `tests/integration/test_detectors_*_dsNNN.py`; fixtures are byte-exact and loaded through `asset_case`.
- `python >=3.12`, `doc_sentinel.toml`, `[tool.doc_sentinel]`, `uv sync --extra ...`, strict known config options and exact profiles are the current contracts (earlier standalone naming suggestions must not supersede them).
- `engine.scan` dispatches 2 args for fast/deep, 3 args for standard; M4 must harmonize config forwarding for rules that need it.
- The deep engine currently globally checks NLP readiness; M4 must distinguish DS301 model requirement from DS302/DS316 model-free capabilities while maintaining mandatory explicit deep confirmation.
- The actual `tests/assets/` is excluded from repository self-scan and lint because it deliberately contains invalid documentation. Keep that exclusion.

See [implementation-contracts.md](/docs/roadmap/0004-deepening-test-cases/implementation-contracts.md) for normative cross-cutting requirements and [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) for all specified scenarios.

## Stories

| Story | Goal | Rule(s) | Dependencies |
|---|---|---|---|
| [01.0](/docs/roadmap/0004-deepening-test-cases/01.0-shared-foundations-and-fixtures/README.md) | Analyzer/config contract, Markdown fixture enforcement, deep capability gating | shared | existing 0001–0003 |
| [02.0](/docs/roadmap/0004-deepening-test-cases/02.0-orphan-documentation/README.md) | Orphan documentation | `DS107` | 01.0 |
| [03.0](/docs/roadmap/0004-deepening-test-cases/03.0-required-document-metadata/README.md) | Required document metadata | `DS111` | 01.0 |
| [04.0](/docs/roadmap/0004-deepening-test-cases/04.0-unresolved-migration-markers/README.md) | Unresolved migration markers | `DS119` | 01.0 |
| [05.0](/docs/roadmap/0004-deepening-test-cases/05.0-terminology-consistency/README.md) | Terminology consistency | `DS205` | 01.0 |
| [06.0](/docs/roadmap/0004-deepening-test-cases/06.0-repeated-document-sections/README.md) | Repeated document sections | `DS207` | 01.0 |
| [07.0](/docs/roadmap/0004-deepening-test-cases/07.0-near-duplicate-documents/README.md) | Near duplicate documents | `DS208` | 01.0 |
| [08.0](/docs/roadmap/0004-deepening-test-cases/08.0-stale-source-symbol-references/README.md) | Stale source symbol references | `DS216` | 01.0 + shared source index / graph |
| [09.0](/docs/roadmap/0004-deepening-test-cases/09.0-configuration-key-synchronization/README.md) | Configuration key synchronization | `DS217` | 01.0 + shared source index / graph |
| [10.0](/docs/roadmap/0004-deepening-test-cases/10.0-cli-option-synchronization/README.md) | CLI option synchronization | `DS218` | 01.0 + shared source index / graph |
| [11.0](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/README.md) | Documented code example syntax | `DS219` | 01.0 |
| [12.0](/docs/roadmap/0004-deepening-test-cases/12.0-numeric-contradiction-candidates/README.md) | Numeric contradiction candidates | `DS302` | 01.0 |
| [13.0](/docs/roadmap/0004-deepening-test-cases/13.0-documentation-change-impact/README.md) | Documentation change impact | `DS316` | 01.0 + shared source index / graph |
| [14.0](/docs/roadmap/0004-deepening-test-cases/14.0-cross-profile-validation-and-release/README.md) | Fixture completeness, CI, docs and release gate | all 12 | 01.0–13.0 |

## Profile expansion

| Exact profile | Already implemented | New rules in M4 | Default execution |
|---|---|---|---|
| `fast` | DS101, DS102, DS103 | **DS107, DS111, DS119** | stdlib-only; frequent CI/pre-commit; new config-dependent checks may be dormant when not configured |
| `standard` | DS201–DS204 | **DS205, DS207, DS208, DS216, DS217, DS218, DS219** | `docsentinel[standard]`, CI/on-demand, deterministic and no LLM |
| `deep` | DS301 | **DS302, DS316** | second opt-in confirmation; advisory/candidate-only; DS302/316 need no spaCy |

**Never renumber existing rules.** Gaps DS104–106, DS108–110, DS112–118, DS206, DS209–215, DS220–223, DS303–315 remain unassigned in this milestone. New IDs must remain stable after release.

## Dependency order and pull-request sequence

1. Story 01.0 first: unify analyzer/config context, add per-rule readiness, validate fixture shape; tests prove backward compatibility.
2. Stories 02.0–04.0: stdlib fast detectors in 3 reviewable PRs. DS107 navigation graph should be isolated for DS316 reuse.
3. Stories 05.0–07.0: dictionary + corpus similarity. DS207/208 can be parallel after shared corpus strategy approved.
4. Stories 08.0–10.0: AST source index then DS216, and mapping-based DS217/DS218 (DS217/218 may proceed in parallel once index contract lands).
5. Story 11.0: DS219 fenced syntax validation (independent, can overlap step 3/4).
6. Stories 12.0–13.0: DS302 numeric candidate normalization, DS316 change-impact graph. Require Story 01.0 deep selective readiness; DS316 relies on DS107 and benefits from DS216.
7. Story 14.0: cross-profile fixtures, end-to-end, security, docs, baselines, CI and milestone closeout.

Parallel PRs must not simultaneously edit `rules.py`/`engine.py`/`config.py` in incompatible ways. Shared changes should land in Story 01.0 and be rebased before detector PRs.

## Acceptance criteria

- [ ] All 12 new IDs registered in correct exact profile, with backward compatibility DS101–301.
- [ ] **At least 3 passing and at least 3 failing asset *directories* per rule** — not just assertions — and every listed edge case.
- [ ] Every case directory has the format `tests/assets/dsNNN/{two_to_four_word_slug}/` and includes at least one `.md` file; use `README.md` for simple case, meaningful `a.md`/`b.md` for multi-doc cases. Supporting `.py`, `.toml` permitted.
- [ ] All named fixture scenarios from [fixture-matrix.md](/docs/roadmap/0004-deepening-test-cases/fixture-matrix.md) are committed; no test constructs main document texts inline.
- [ ] Every case is test-referenced using the current `asset_case` fixture and receives a clear assertion for `clean`, `finding`, or `pending`.
- [ ] Unit, mock, integration and CLI/E2E tests cover security, determinism, config injection, selection/ignore, baseline and reports.
- [ ] Profile independence and deep opt-in/advisory semantics hold. DS302 and DS316 work without NLP model when individually selected and confirmed.
- [ ] No source-example execution/import; no remote/LLM work; path traversal and symlink safeguards tested.
- [ ] Repository self-scan excludes intentional bad fixtures; CI/test/build/docs and security audit pass.
- [ ] `status.md` and the repo roadmap index updated as stories merge, without prematurely marking unimplemented rules complete.

## Suggested GitHub labels / issue mapping

Create one milestone titled `0004-deepening-test-cases`. Create **14 story-level issues** (`01.0`–`14.0`), each referencing the story `README.md`; implementation agents should take each **task Markdown file as the task body**. Preferred labels: `milestone:0004`, `documentation-qa`, `tests`, and `profile:fast|standard|deep` as appropriate (create only if existing repository label policy allows). Do not create/modify GitHub issues as part of this archive delivery.

## Implementation notes and source of truth

- The archive is a specification, **not a claimed successful implementation**. Tests/assets inside archive are *planned paths*; implementation must actually create them in GitHub.
- Current source audited: `tests/assets/README.md`, `tests/asset_helpers.py`, `tests/conftest.py`, `src/docsentinel/{engine,config,rules,models,code_discovery}.py`, selected detectors, `docs/roadmap/README.md`, `CLAUDE.md`, `doc_sentinel.toml`, `pyproject.toml`.
- Per-story test matrices are the prescriptive fixture set; additional edge cases found while coding should be added rather than silently substituted for named cases.
