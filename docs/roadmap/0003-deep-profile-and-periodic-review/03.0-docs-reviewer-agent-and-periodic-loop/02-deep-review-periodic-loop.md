# Task 02 - `deep-review` Periodic Loop

**Story:** [03.0 - `docs-reviewer` Agent & Periodic Review Loop](README.md)
**Depends on:** [01 - `docs-reviewer` agent definition](01-docs-reviewer-agent-definition.md),
Milestone 0003 Story 01.0 (the confirmed-deep invocation), Story 02.0 (`DS301`, the candidate
source). Mirrors the file conventions of the existing loops
[`implement-story.md`](/.claude/loops/implement-story.md) and
[`update-docs.md`](/.claude/loops/update-docs.md) (frontmatter, Step algorithm, state cursor,
Termination table, `ScheduleWakeup` self-reschedule).

## Purpose

`deep` is slow, heuristic, and advisory - running it per-commit would be both wasteful and noisy.
It belongs on a **cadence**: a weekly (or on-demand) batch that runs the confirmed deep scan,
captures the `DS301` candidates, hands them plus a rotating slice of doc/source pairs to the
`docs-reviewer` agent, and files a dated review report. This task writes that loop. No existing loop
in `.claude/loops/` is periodic - both current loops are convergence loops that self-terminate once
clean - so this task designs the periodic cadence from scratch using the project's `ScheduleWakeup`
self-rescheduling idiom, while matching the existing loop files' structure as closely as possible.

## Files

| Path | Action |
|------|--------|
| `.claude/loops/deep-review.md` | Create |

> Pure loop-definition task - no Python, no tests. "Symbols / fields" is replaced by the Step
> algorithm and cadence decision below.

## Frontmatter (match the existing loops' shape)

| Field | Value |
|-------|-------|
| `name` | `deep-review` |
| `description` | Periodic (weekly / on-demand) deep-profile review: runs the confirmed `deep` scan, captures `DS301` candidates, drives the `docs-reviewer` agent to triage them and review doc-vs-code behavioral drift, files a dated report to `docs/reviews/`. Explicitly **not** a per-commit hook. |
| `invoke` | `/loop deep-review` |
| `terminates-when` | On-demand single-shot: terminates after one report is written. Periodic mode: self-reschedules weekly; a human stops it by not re-arming, or it stops itself when the `deep` extra/model is unavailable. |

## Cadence decision (the core difference from existing loops)

1. **Weekly, not 270-second.** `implement-story`/`update-docs` reschedule at `delaySeconds: 270` to
   stay inside the 300 s prompt-cache TTL, because they re-fire rapidly into one growing
   conversation. This loop is the opposite: a weekly batch where the cache is cold anyway, so the
   270 s rationale **does not apply** - state this explicitly in the loop file so a future editor
   doesn't "fix" the cadence to 270 s. Periodic mode reschedules at `delaySeconds: 604800` (7 days).
2. **On-demand is the default invocation.** `/loop deep-review` runs **once** and stops (writes one
   report, no reschedule). Periodic mode is opt-in via an argument (e.g. `/loop deep-review --weekly`)
   that arms the self-reschedule - so a human can get a one-off review without accidentally starting
   a recurring job.
3. **Never per-commit.** The loop file states plainly that it is not wired into any pre-commit hook
   or CI step - `deep` is advisory and slow; coupling it to commits is explicitly rejected (consistent
   with Story 04.0's advisory-only exit codes and the plan's "deferred/periodic" framing).

## Step algorithm (adapt the existing loops' Step structure)

1. **Readiness gate.** Run `docsentinel doctor` (or call `deep_support.deep_ready` via a one-line
   `python -c`). If the `deep` extra/model is unavailable, print the setup hint (`doctor`'s remedy
   line) and **stop** - do not reschedule into a permanently-failing state. A periodic run that can
   never succeed must disarm itself, not spin.
2. **Capture candidates.** Run
   `docsentinel scan --profile deep --i-understand-deep-is-heuristic --format json` and persist the
   result (findings + enabled_rules + notice) to a state file
   `.claude/state/deep-review-candidates.json` (mirror `update-docs`'s `.claude/state/*.json` cursor
   convention). If there are zero `DS301` candidates **and** no doc/source pair is due for drift
   review this cycle, write a short "clean this cycle" report and proceed to Step 5.
3. **Pick a doc/source review slice.** Behavioral-drift review across the whole corpus every week is
   too much; maintain a small rotating cursor of doc-section ↔ source-module pairs (e.g. architecture
   README ↔ `engine.py`/`config.py`, user manual ↔ `cli.py`) in the state file and advance it each
   run so coverage rotates over successive weeks. Document the initial pair list in the loop file.
4. **Drive `docs-reviewer`.** Spawn the `docs-reviewer` agent (Task 01) with: the candidates state
   file path, the doc/source pair(s) for this cycle, and the instruction to write
   `docs/reviews/YYYY-MM-DD-deep-review.md`. Pass **paths, not pasted contents** (the agent reads
   them itself), consistent with the existing loops' token-economy discipline and the security rule
   against moving raw content around unnecessarily.
5. **Record & reschedule.** Record the report path and advance the review-slice cursor in the state
   file. Then:
   - **On-demand mode:** print a one-line summary (candidates triaged, drift pairs reviewed, report
     path) and **stop** - do not call `ScheduleWakeup`.
   - **Periodic (`--weekly`) mode:** call `ScheduleWakeup` with `prompt: /loop deep-review --weekly`,
     `delaySeconds: 604800`, `reason: "weekly deep-review cycle"`. Then stop this iteration.

## Decision

- **State file is a derived cursor, not the source of truth** - the review reports in `docs/reviews/`
  and the live scan are authoritative, exactly as `implement-story`'s cursor relates to its
  `status.md`. The state file just carries the rotating review slice and the last candidate capture.
- **No secrets/raw content in the state file** - it holds finding *fingerprints*/locations and the
  rotation cursor, not document bodies, per `docs/security/README.md`.
- **Idempotent on a clean cycle** - a week with no new candidates and nothing due for drift review
  still writes a short dated "clean" report (an empty findings list is never silently treated as a
  validated audit - `CLAUDE.md`'s honesty rule applies to the loop's output too).

## Success criteria

- [ ] `.claude/loops/deep-review.md` exists with frontmatter (`name`/`description`/`invoke`/
      `terminates-when`) matching the existing loops' shape and a Step algorithm + Termination table
      in the same style.
- [ ] The cadence decision is explicit: weekly (`604800 s`) in periodic mode, single-shot on demand,
      and a stated reason the 270 s cache-TTL cadence of the other loops deliberately does **not**
      apply here.
- [ ] The loop file states plainly it is **not** per-commit and not wired into any hook/CI.
- [ ] The readiness gate disarms (stops without rescheduling) when the `deep` extra/model is absent -
      no permanently-failing reschedule.
- [ ] The loop drives the `docs-reviewer` agent with paths (not pasted content) and the review-slice
      rotation is described, with an initial doc/source pair list.

## Constraints

- `.claude/` markdown only - no Python, no tests.
- After adding this loop, the Copilot fleet importer must be re-run so `.github/copilot/loops/`
  mirrors it (per `CLAUDE.md`) - note as a follow-up; not run by this doc-only spec.
- Do not reuse the 270 s `delaySeconds` from the other loops - that value is for cache-warm rapid
  loops and is wrong for a weekly batch; the loop file must call this out so it is not "corrected"
  back later.
