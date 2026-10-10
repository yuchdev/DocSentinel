# Milestone 0001 - Generic Implementation - Status

Tracks progress against [plan.md](plan.md). Updated as each story lands.

## Current status

| Story | Name                                | Status         | Progress | Tests |
|-------|-------------------------------------|----------------|----------|-------|
| 01.0  | Rule Registry & Config Conventions  | ✅ Complete    | 4/4      | 50 full |
| 02.0  | Fast-Profile Structural Detectors   | ✅ Complete    | 4/4      | 136 full |
| 03.0  | CLI & Reporting Completion          | ✅ Complete    | 3/3      | 159 full |
| 04.0  | Pre-commit, CI & Self-Scan Baseline | ✅ Complete    | 3/3      | 209 full; remote CI trial passed |

## Task status

| Task | Deliverable | Status | Evidence / disposition |
|------|-------------|--------|------------------------|
| 01.0-01 | Rule registry | ✅ Complete | Frozen `Rule`, deterministic registry lookup, isolated tests; 4 focused tests passed |
| 01.0-02 | Config conventions | ✅ Complete | Standalone/pyproject precedence, selector shape validation, keyword-safe override; 28 focused tests passed |
| 01.0-03 | Selection resolution | ✅ Complete | Deterministic prefix selection, ignore precedence, profile-scoped engine honesty; 28 focused tests passed |
| 01.0-04 | CLI and docs | ✅ Complete | CLI overrides, registry-derived diagnostics, new config example, synchronized docs |
| 02.0-01 | Dangling link/anchor detector (`DS101`) | ✅ Complete | Faithful local link-check port, structured lines, three-finding repository smoke test; 30 focused tests passed |
| 02.0-02 | Stray HTML comment detector (`DS102`) | ✅ Complete | Fence-safe bounded comment findings with preserved one-based lines; 16 focused tests passed |
| 02.0-03 | Unresolvable path detector (`DS103`) | ✅ Complete | Non-overlapping path-span detection, guarded platform paths, one-based lines; 33 focused tests passed |
| 02.0-04 | Detector package wiring | ✅ Complete | Import-time analyzer activation, profile isolation, real CLI pass/fail, architecture/security sync |
| 03.0-01 | Severity-aware exit codes | ✅ Complete | Default errors-only failure, strict any-finding failure, preserved exit 2; 141 full tests passed |
| 03.0-02 | GitHub annotation format | ✅ Complete | Escaped CI annotations, optional structured lines, severity fallback, indexed security review; 155 full tests passed |
| 03.0-03 | JSON schema versioning | ✅ Complete | Schema v1 JSON/text contract, keyword-safe construction, documented compatibility policy |
| 04.0-01 | Pre-commit fast hook wiring | ✅ Complete | Existing manifest verified; clean/warning/error subprocess behavior and bounded execution tested |
| 04.0-02 | Baseline file mechanism | ✅ Complete | Strict `fingerprints` schema, deterministic hash-only saves, pre-exit filtering, CLI capture; 35 focused tests passed |
| 04.0-03 | Self-scan baseline capture | ✅ Complete | ADR links fixed; 711-fingerprint baseline, clean local self-scan, CI gate wired; remote CI trial passed (yuchdev/DocSentinel, branch trial/milestone-0001-github-actions, commit 6b2906cedb5d27803a5e9a06b0c3947ebd7605fa, run 38073201647) across Python 3.11/3.12/3.13 |

## Decisions and gap dispositions

- **Baseline contract:** the authoritative on-disk shape is `{"fingerprints": [...]}`. The
  contradictory fingerprint-to-`true` mapping prose in Task 04.0-02 was reconciled before work.
- **Finding locations:** `Finding.line` is an optional, one-based public field in this milestone.
  Detectors populate it when known, JSON reports include it, and GitHub annotations use it when
  present. The Task 03.0-02 deferral was removed.
- **Exit gates:** the user authorized an explicit milestone-level section in `plan.md`; the six
  named gates are now the completion contract.
- **Decomposition audit:** all four story READMEs and all fourteen task specifications exist, and
  the dependency graph is acyclic. No additional story scope was introduced.

## Story close evidence

- **01.0 Rule Registry & Config Conventions:** delivered the frozen rule registry, new config
  discovery/shape, deterministic selector resolution, engine wiring, CLI overrides and generated
  config, registry-derived diagnostics, and synchronized architecture/example documentation.
  Story-close gates: 50 plugin-loaded tests passed; scoped Ruff check/format passed; eight affected
  Markdown files passed link/anchor validation; legacy config references are absent from `src/`,
  `tests/`, and `examples/`. No deferrals; the temporary unplanned missing-analyzer failure was
  removed to reconcile implementation with Task 01.0-03's explicit algorithm.
- **02.0 Fast-Profile Structural Detectors:** delivered and registered `DS101`, `DS102`, and
  `DS103`, including structured one-based lines, deterministic detector tests, profile isolation,
  and real CLI findings exits. Story-close gates: 86 detector/E2E tests and 136 full plugin-loaded
  tests passed; Ruff check and format passed over `src/` and `tests/`; architecture/security links
  passed. Security review found no Critical/High issue and recorded Medium residuals for unbounded
  resource use, outside-root link/symlink resolution inherited from the specified link algorithm,
  and unescaped attacker-controlled finding text; these remain explicit hardening follow-ups under
  the task's required open-risk disposition.
- **03.0 CLI & Reporting Completion:** delivered severity-aware strict/default exits, escaped
  GitHub annotations with structured optional lines, and schema-versioned JSON/text reports with a
  documented compatibility policy. Story-close gates: 159 plugin-loaded tests passed; Ruff check
  and format passed over `src/` and `tests/`; architecture, security-review, and documentation-index
  links passed; security review found no workflow-command injection blocker.
- **04.0 Pre-commit, CI & Self-Scan Baseline:** implemented all three tasks: verified the existing
  non-strict hook, added the strict `fingerprints` baseline mechanism, removed three stale illustrative
  ADR links, captured 711 deferred findings, and wired an exit-code-checked CI scan. Local self-scan
  exits 0 with zero findings and all three fast rules evaluated. Authorized remote CI trial passed on
  GitHub Actions ([yuchdev/DocSentinel](https://github.com/yuchdev/DocSentinel), branch [trial/milestone-0001-github-actions](https://github.com/yuchdev/DocSentinel/tree/trial/milestone-0001-github-actions), commit
  `6b2906cedb5d27803a5e9a06b0c3947ebd7605fa`, run `38073201647`, URL
  https://github.com/yuchdev/DocSentinel/actions/runs/38073201647, push event, conclusion success)
  across Python 3.11, 3.12, and 3.13 matrix jobs (locked sync, plugin-loaded pytest, JSON and text
  self-scans, and build all passed). Nonblocking platform notices: Node.js 20 and ubuntu-latest runner
  migration annotations noted without failures.

## Milestone exit-gate evidence

- **Locked environment:** locked synchronization completed without a dependency-manifest or lockfile
  change.
- **Tests:** 209 tests passed with the DocSentinel pytest plugin explicitly loaded. Plain pytest's
  opt-in fixture error remains intentional and is not the repository's documented gate.
- **Self-scan and honesty:** scan exits 0 with zero findings, enabled rules DS101-DS103, no pending
  work for the fast profile, and the truthful notice that three fast rules were evaluated. The
  captured baseline contract contains 711 deterministic fingerprints.
- **Build:** source distribution and wheel built successfully from the locked environment.
- **Quality and review:** Ruff check/format passed over product and tests; task verification found
  zero implementation defects; unified feature/security review returned APPROVE with no blocker or
  security severity; repository secret scan found no credential matches.
- **Documentation:** all 75 documentation files passed relative-link and heading-anchor validation.
- **Remote CI trial and milestone completion:** authorized remote GitHub Actions CI trial completed
  successfully (repository [yuchdev/DocSentinel](https://github.com/yuchdev/DocSentinel), branch [trial/milestone-0001-github-actions](https://github.com/yuchdev/DocSentinel/tree/trial/milestone-0001-github-actions), commit
  `6b2906cedb5d27803a5e9a06b0c3947ebd7605fa`, run `38073201647`, URL
  https://github.com/yuchdev/DocSentinel/actions/runs/38073201647, push event, conclusion success).
  Matrix jobs for Python 3.11, 3.12, and 3.13 all passed locked sync, plugin-loaded pytest (209 tests),
  JSON and text self-scans, and build. Nonblocking platform notices: Node.js 20 and ubuntu-latest runner
  migration annotations noted without failures. Milestone 0001 is complete.

**Legend:** ✅ Complete · 🔶 In progress / partial · ⬜ Not started
