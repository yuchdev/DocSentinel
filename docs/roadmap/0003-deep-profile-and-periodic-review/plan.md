# Milestone 0003 - Deep Profile & Periodic Review

**Package:** `docsentinel` | **Module root:** `src/docsentinel/` | **Config namespace:** `doc_sentinel`

> Naming note: the distributed package, CLI, and import path are all `docsentinel` (one word,
> no underscore). The **configuration namespace** - the `pyproject.toml` table and the standalone
> config filename - is deliberately `doc_sentinel` (underscored) per `CLAUDE.md`'s explicit
> convention. These are two different names for two different things; do not "fix" one to match
> the other. See
> [Milestone 0001's naming note](/docs/roadmap/0001-generic-implementation/plan.md) for the full
> statement.

## Goal

Give the **`deep` profile** - the third and last profile named in
[`docs/architecture/README.md`](/docs/architecture/README.md) - its first real, narrow content:
one explicitly-opt-in, heuristic, semantic detector (fact-contradiction *candidates*), plus the
one requirement that cannot be a pure code detector at all - a periodic `docs-reviewer` agent that
triages those candidates and reads doc-vs-code *behavioral* drift. This milestone deliberately
realizes the future that `docs/security/README.md`'s own M0 threat model already flagged: `deep`
is the point at which an analyzer loads a model and reads full document contents, so it must be
**more** gated than merely selecting `profile = "deep"`.

Everything here is **heuristic and advisory by design.** Unlike `fast` (Milestone 0001) and
`standard` (Milestone 0002), a `deep` detector is a *candidate generator*: false positives are
expected and acceptable, because the output's consumer is a human-in-the-loop (or the
`docs-reviewer` agent), not a build gate. This single property shapes every story below - the
opt-in gate (Story 01.0), the "candidate" framing of every finding (Story 02.0), the agent/loop
that triages rather than trusts (Story 03.0), and the deliberate exit-code asymmetry that keeps
`deep` findings out of the build-failing path even under `--strict` (Story 04.0).

Scope is narrow on purpose. This milestone ships exactly one detector (`DS301`), one agent, and
one periodic loop. It does **not** attempt the full "semantic QA" space; it establishes the
gating, dependency, reporting, and review-loop machinery that any future `deep` detector plugs
into, and proves the shape end-to-end with a single honest check.

## Stories

| Story | Name                                           | Category | Output                                                                                                   |
|-------|------------------------------------------------|----------|---------------------------------------------------------------------------------------------------------|
| 01.0  | Deep Profile Opt-In Gating & Dependency Plumbing | feature  | `Config.deep_confirm` + `--i-understand-deep-is-heuristic` flag / `DOCSENTINEL_DEEP_CONFIRM` env, `[project.optional-dependencies] deep`, lazy-import boundary, `doctor` readiness |
| 02.0  | Fact-Contradiction Candidate Detector          | feature  | `DS301`: spaCy + textacy SVO triples compared cross-corpus; `warning`-only "candidate contradiction" findings |
| 03.0  | `docs-reviewer` Agent & Periodic Review Loop    | chore    | `.claude/agents/docs-reviewer.md` (triage + behavioral-drift review), `.claude/loops/deep-review.md` (weekly / on-demand) |
| 04.0  | Deep-Profile Reporting & Exit-Code Semantics    | feature  | `deep` findings are advisory-only (never fail a build, even under `--strict`); honest notice/pending wording; architecture doc refresh |

## Cross-cutting guidelines (every story)

- **Heuristic, not deterministic - and say so.** Every `fast`/`standard` guideline said
  "explainable from inputs alone, no model calls." `deep` is the milestone that deliberately
  relaxes that one dimension: it loads a pinned spaCy model. Output is therefore stable only for a
  **fixed model version**; a model upgrade can change findings. This is a real departure from the
  "deterministic-first" premise and must be documented wherever it surfaces - never papered over.
- **Opt-in is a real mechanism, not prose.** `profile = "deep"` alone must never trigger model
  loading, network, or heavy work. A second, explicit confirmation gesture is required (Story
  01.0). Selecting `deep` without confirming is a no-op-with-explanation, not an error and not a
  silent heavy run.
- **Candidate, never verdict.** No `deep` finding may assert a contradiction as fact or ship at
  `severity = "error"`. The word "candidate" (or equivalent hedge) appears in every `DS3xx`
  message, and `deep` findings never fail a build (Story 04.0).
- **No eager heavy imports.** `docsentinel.engine` and `docsentinel.detectors` must import
  cheaply even when the `deep` extra is not installed. spaCy/textacy load lazily, inside the
  analyzer call, never at module import time (Story 01.0 Task 02).
- **Honesty about `notice`/`pending`.** Per `CLAUDE.md`, an empty findings list is never a
  validated audit. A `deep` run that did not actually evaluate rules (not confirmed, or deps
  missing) must say so via a distinct `pending` message - not the "N rule(s) evaluated" wording
  and not "not implemented."
- **No secrets or raw sensitive content persisted.** The `docs-reviewer` agent and the periodic
  loop write reports to `docs/reviews/`; they cite findings by location, never by pasting
  unredacted document contents, per `docs/security/README.md`'s non-negotiable rules.
- **Full type annotations, no bare `except:`** - see
  [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md).

## Rule code namespace

`DS3xx` is the `deep` range reserved by
[Milestone 0001's rule-code namespace table](/docs/roadmap/0001-generic-implementation/plan.md).
This milestone assigns the first code in that range:

| Prefix  | Profile | Category                                                | Codes this milestone                                     |
|---------|---------|---------------------------------------------------------|----------------------------------------------------------|
| `DS3xx` | `deep`  | Semantic (explicitly enabled, heuristic, may feed an agent) | `DS301` fact-contradiction candidate (Story 02.0)        |

- `DS302`-`DS399` stay **reserved** for future `deep` detectors (doc-vs-code behavioral drift, if
  ever reduced to a code-emittable form; semantic duplication; entailment checks). They are not
  assigned here - an unused gap is cheaper than a reused number.
- A rule's code is permanent once shipped. `DS301` registers at import time like every other rule
  (per [Milestone 0001 Story 01.0 Task 01](/docs/roadmap/0001-generic-implementation/01.0-rule-registry-and-config-conventions/01-rule-registry.md)),
  with `Rule.profile == "deep"` and `Rule.severity == "warning"`.

## Relationship to the other milestones

- **Milestone 0001 (`fast`)** established the rule registry, `select`/`ignore` resolution, the
  `ANALYZERS`-keyed-by-code contract, severity-aware exit codes, and the baseline mechanism this
  milestone's findings flow through unchanged. This milestone depends on all of it.
- **Milestone 0002 (`standard`, specced in parallel)** is corpus-wide but still non-LLM. It
  almost certainly introduces its own optional-dependency group and lazy-import boundary for its
  heavier (but still deterministic) dependencies. **If** 0002 lands a generic lazy-import /
  optional-extra helper, Story 01.0 Task 02 here should be rebased onto it rather than keeping a
  second copy - this milestone cannot confirm 0002's design from disk at authoring time, so it
  designs its own boundary and flags the de-duplication as an explicit follow-up for whoever lands
  both. The `docs-reviewer` agent (Story 03.0) is also deliberately scoped to be *distinct* from
  0002's `docsig` *signature*-only doc-vs-code check: this milestone's review is *behavioral*.

## Beyond this milestone

- A future, **separate** opt-in (e.g. `--fail-on-deep` / `deep_fail = true`) could let a project
  that has tuned `DS301` promote its candidates to build-failing. Story 04.0 documents this as a
  deliberate deferral, not a gap - the default and `--strict` both keep `deep` advisory-only.
- `DS302`+ semantic detectors.
- A security re-assessment of the content-leaving-the-process surface is an **action item handed
  to `security-auditor`** in Story 01.0's success criteria - the threat model itself is written by
  `security-auditor`, not here.

## Links

- **Architecture boundaries:** [`docs/architecture/README.md`](/docs/architecture/README.md)
- **Security threat model (M0, flags the `deep` future risk):** [`docs/security/README.md`](/docs/security/README.md)
- **Sibling milestone (fast profile, format reference):** [`docs/roadmap/0001-generic-implementation/plan.md`](/docs/roadmap/0001-generic-implementation/plan.md)
- **Coding standard:** [`docs/dev/python_coding_standard.md`](/docs/dev/python_coding_standard.md)
- **Status tracker:** [status.md](status.md)
