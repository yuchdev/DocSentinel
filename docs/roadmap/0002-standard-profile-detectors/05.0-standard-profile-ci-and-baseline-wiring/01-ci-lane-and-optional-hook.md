# Task 01 - Standard CI Lane & Optional Pre-commit Hook

**Story:** [05.0 - Standard-Profile CI & Baseline Wiring](README.md)
**Depends on:** Milestone 0002 Stories 01.0-04.0 (the detectors + the extra); Milestone 0001 Story
04.0 (the `docsentinel-fast` pre-commit hook precedent and the baseline mechanism)

## Purpose

Decide and wire where the `standard` profile runs automatically, without making it an all-or-nothing
blocker on a corpus that has pre-existing findings and without forcing the heavy optional extra onto
every contributor's pre-commit environment.

## Decision this task implements

1. **`standard` is CI-and-on-demand, not a default pre-commit hook.** The Milestone 0001
   `docsentinel-fast` hook stays `always_run: true` (fast, stdlib-only). `standard` does **not** get
   an `always_run` hook - it is too slow (corpus-wide O(n²) + `docsig` over source) and requires the
   `docsentinel[standard]` extra, which not every contributor will have installed. Blocking every
   commit on it would get it disabled by the first person it annoys (the same reasoning Milestone
   0001 used to keep warnings non-blocking).
2. **A separate, opt-in pre-commit hook id `docsentinel-standard` is provided but not default.** Add
   it to `.pre-commit-hooks.yaml` with `always_run: true`, `pass_filenames: false`, and
   `stages: [manual]` (or `[pre-push]`) so it runs only when a team explicitly opts in (e.g.
   `pre-commit run docsentinel-standard --hook-stage manual`, or a `pre-push` stage), never on every
   `pre-commit`. Its `entry` installs/assumes the extra; document in the hook `name`/comment that it
   requires `docsentinel[standard]`. This gives teams a sanctioned way to run it locally without
   imposing it on everyone.
3. **CI gets a dedicated `standard` lane** that installs the extra (`uv sync --extra standard`) and
   runs `docsentinel scan --profile standard` against this repo, gated by a **`standard` baseline
   file** (`.docsentinel-standard-baseline.json`, via `Config.baseline` from Milestone 0001 Story
   04.0 Task 02). Keep it a **separate baseline file** from the `fast` baseline - the two profiles'
   findings are disjoint, their fingerprints live in different files, and a project can adopt one
   profile's baseline without the other. The lane is non-blocking on `warning`-only drift by default
   (DS201-DS203 are warnings) and blocks on `DS204` (`error`) and on any finding under `--strict` if
   the team chooses that lane.
4. **`deep` is explicitly out of scope** - no hook, no lane; Milestone 0003 owns it.

## Files

| Path | Action |
|------|--------|
| `.pre-commit-hooks.yaml` | Modify - add the opt-in `docsentinel-standard` hook |
| CI workflow file (e.g. `.github/workflows/*.yml`, whichever runs the existing test/lint lanes) | Modify - add the `standard`-extra scan lane |
| `.docsentinel-standard-baseline.json` | Create - captured via `docsentinel baseline --profile standard` (see below) |
| `tests/test_pre_commit_hook_manifest.py` | Modify - assert the new hook's fields |
| `docs/architecture/README.md` | Modify - record the CI/hook policy for `standard` |

> Verify the actual CI workflow path at implementation time (read `.github/workflows/` first). If
> this repo has no CI workflow yet, this task adds the lane to whatever CI entry exists or documents
> the exact command for a human to wire into CI - do not invent a workflow structure that does not
> match the repo's conventions.

## Symbols / fields

`.pre-commit-hooks.yaml` - append (alongside the existing `docsentinel-fast` entry):

```yaml
- id: docsentinel-standard
  name: DocSentinel standard profile (requires docsentinel[standard])
  entry: docsentinel scan --profile standard
  language: python
  additional_dependencies: ["docsentinel[standard]"]
  pass_filenames: false
  always_run: true
  stages: [manual]
```

- `additional_dependencies: ["docsentinel[standard]"]` makes pre-commit install the extra into the
  hook's isolated env, so the hook works even for a contributor whose main env lacks it - but
  `stages: [manual]` means it never runs on a plain `pre-commit`/`git commit`; it is opt-in.
- Confirm the exact `additional_dependencies` spelling pre-commit accepts for an extra at
  implementation time.

Baseline capture: run `docsentinel baseline --profile standard --output
.docsentinel-standard-baseline.json` (the `baseline` subcommand + `--profile` from Milestone 0001
Story 04.0 Task 02 - confirm that subcommand honors `--profile`; if it does not yet, that is a small
cross-reference fix to file against that task, noted here, not silently worked around). Commit the
resulting file so the CI lane gates only *new* standard findings.

## Decision rationale recorded (why not an always-on hook)

A corpus-wide, extra-dependent, source-reading scan has three properties that make it wrong for an
every-commit hook and right for CI/on-demand: it is **slow** (seconds, not milliseconds), it needs a
**heavy optional install** many contributors will not have, and its **warning**-heavy output (3 of 4
rules) is advisory, not blocking. CI (where the extra is installed once and runtime is amortized) and
an explicit on-demand hook are the correct homes. This mirrors how linters ship their heavy,
whole-project analyses (type-checking, security scanning) as CI lanes rather than per-commit hooks.

## Tests (`tests/test_pre_commit_hook_manifest.py` additions)

- `test_standard_hook_present_and_opt_in` - parse `.pre-commit-hooks.yaml`; assert a
  `docsentinel-standard` entry exists with `always_run: true`, `pass_filenames: false`,
  `stages: [manual]` (not default), and `additional_dependencies` naming the extra.
- `test_fast_hook_is_still_default_and_unchanged` - the `docsentinel-fast` entry still has no
  `stages:` restriction (runs on every commit) - a regression guard that adding `standard` did not
  accidentally restage `fast`.
- `test_standard_and_fast_use_separate_baseline_files` - a documentation/consistency assertion: the
  CI lane config (or a small constant) references `.docsentinel-standard-baseline.json`, distinct
  from the `fast` baseline path - guards Decision §3.

## Success criteria

- [ ] `docsentinel-standard` exists as an opt-in (`stages: [manual]`) hook that installs the extra;
      `docsentinel-fast` remains the only default-staged hook.
- [ ] CI has a `standard` lane that installs `docsentinel[standard]` and runs the standard scan gated
      by a committed, separate `.docsentinel-standard-baseline.json`.
- [ ] The policy ("`standard` is CI/on-demand, not every-commit") is written down in
      `docs/architecture/README.md`, so a future contributor does not "helpfully" promote it to an
      always-run hook.

## Constraints

- No new runtime dependency on the base package - the extra is installed only in CI and the opt-in
  hook's isolated env, never promoted to a core dependency.
- Do not block CI on `warning`-only standard findings by default (DS201-DS203); let `DS204` (`error`)
  and `--strict` be the blocking signals, consistent with Milestone 0001 Story 03.0 Task 01's
  severity semantics.
- Reuse the existing `Config.baseline` / `docsentinel baseline` mechanism unchanged - this task adds
  no new baseline machinery, only a second baseline *file* and the CI/hook wiring around it.
</content>
