# Task 07 — Self-scan counts and baseline migration

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Python Expert  
**Depends on:** Task 05.

## Inputs

- Story README "Baselines and self-scan".
- `/docsentinel.toml`, `/.docsentinel-baseline.json`, `/.docsentinel-standard-baseline.json`,
  `/.github/workflows/ci.yml`, `/.pre-commit-hooks.yaml`.
- CI log rule in `/CLAUDE.md`: never print a full report to a log; write it with `-o`.

## Steps

1. Before the scope change is merged (on the parent commit), record per-rule counts of the default
   self-scan: `uv run docsentinel scan . --format json -o` into a file under the scratch reports
   folder, then count by rule. Record DS103 and the total.
2. After the change, record the same counts for the default scope and for
   `--reference-scope strict`.
3. Fix any DS124 finding in this repository's documents (a renamed file mentioned by an agent
   prompt is a real bug) rather than baselining it.
4. Regenerate the fast baseline: `uv run docsentinel baseline . --output .docsentinel-baseline.json`.
   Confirm it holds no DS103 fingerprints and record the old and new entry counts.
5. Confirm the standard baseline is byte-identical (profiles are exact).
6. Confirm the CI self-scan steps and the pre-commit hooks need no change (default scope). Do not
   add a strict lane.
7. Write the counts into the Story 01.0 close note in `/docs/roadmap/0009-improvements/status.md`
   (the implement-story close step), and add one line for Milestone 0008 Story 05.0 under Notes &
   decisions.

## Files

`/.docsentinel-baseline.json`; documents with broken mentions, if any;
`/docs/roadmap/0009-improvements/status.md` (counts only).

## Verification

- `uv run docsentinel scan . --format json -o` (to a scratch file) exits `0` with 0 DS103 and 0
  DS124 findings.
- The baseline-drift comparison (new versus stale fingerprints) is empty.

## Acceptance

- [ ] Before and after counts recorded.
- [ ] Fast baseline regenerated without DS103 entries; standard baseline unchanged.
- [ ] No report printed to a CI log.
