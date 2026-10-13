---
name: deep-review
description: Periodic (weekly / on-demand) deep-profile review: runs the confirmed deep scan, captures DS301 candidates, drives the docs-reviewer agent to triage them and review doc-vs-code behavioral drift, files a dated report to docs/reviews/. Explicitly not a per-commit hook.
invoke: /loop deep-review [--weekly]
terminates-when: On-demand mode terminates after one report is written; periodic mode self-reschedules weekly (604800s) or stops if deep dependencies are unavailable.
---

# deep-review

Periodic and on-demand review workflow for DocSentinel's `deep` profile and doc-vs-code behavioral drift.

## Cadence and execution policy

- **On-demand by default**: `/loop deep-review` executes a single review cycle and terminates immediately after writing the review report.
- **Weekly periodic mode**: When invoked as `/loop deep-review --weekly`, the loop arms a 7-day reschedule (`delaySeconds: 604800`). The 270-second prompt-cache TTL interval used in convergence loops (`implement-story`, `update-docs`) deliberately does **not** apply to weekly batch reviews where caches are naturally cold.
- **Never per-commit**: Deep scans and semantic reviews are computationally expensive, heuristic, and advisory. This loop must **never** be attached to commit hooks or blocking CI gates.

## Initial rotating review slices

The loop rotates across doc-source pairs across successive weekly cycles:

1. `docs/architecture/README.md` ↔ `src/docsentinel/engine.py`, `src/docsentinel/config.py`
2. `README.md` ↔ `src/docsentinel/cli.py`
3. `docs/dev/python_coding_standard.md` ↔ `ruff.toml`, `pyproject.toml`
4. `CONTRIBUTING.md` ↔ `tests/` test fixtures and scan entry points

## Step algorithm

### 1. Readiness gate
Check whether deep profile dependencies and models are installed:
```bash
python -c "from docsentinel.deep_support import deep_ready; import sys; sys.exit(0 if deep_ready() else 1)"
```
If exit code is non-zero (dependencies or model missing), print setup guidance and **stop immediately without rescheduling**.

### 2. Capture candidates
Run the confirmed deep scan and save JSON output to `.claude/state/deep-review-candidates.json`:
```bash
docsentinel scan --profile deep --i-understand-deep-is-heuristic --format json > .claude/state/deep-review-candidates.json
```

### 3. Select review slice
Read the cursor in `.claude/state/deep-review-candidates.json` to select the current rotating doc/source pair and advance the slice index for the next cycle.

### 4. Drive `docs-reviewer`
Spawn the `docs-reviewer` agent, passing the file paths for the captured candidates JSON and the selected doc/source review slice. Instruct the agent to generate `docs/reviews/YYYY-MM-DD-deep-review.md`.

### 5. Record & reschedule
- **On-demand mode**: Print summary of findings and report location, then terminate.
- **Periodic mode (`--weekly`)**: Self-reschedule via `ScheduleWakeup`:
  - `prompt`: `/loop deep-review --weekly`
  - `delaySeconds`: `604800`
  - `reason`: "weekly deep-review cycle"

## Termination criteria

| Mode | Condition | Action |
|---|---|---|
| Any | Deep dependencies/model not installed | Print install guidance and stop |
| On-demand | Report written to `docs/reviews/` | Print summary and stop |
| Periodic (`--weekly`) | Report written to `docs/reviews/` | Schedule wakeup in 7 days (604800s) |
