# Milestone 0010 — completion status

**Planning state:** 📝 Specification only (0 of 4 stories implemented). No ADR, no threat model, no
code. Every story is decomposed into a README with a `## Tasks` table; task detail files are
deliberately **not written yet** (same spec-only state as Milestones 0006 and 0008 at this stage).
Execution order is 01.0 → 02.0 → 03.0 → 04.0 (see
[plan.md](/docs/roadmap/0010-fact-check/plan.md#stories)). Open decisions D1–D10 await owner
sign-off.

## Current status

| Story | Name | State | Tests executed |
|---|---|---|---|
| 01.0 | Backend Protocol and rule contract | ⬜ Not started | — |
| 02.0 | Claim salience and data-mining filter | ⬜ Not started | — |
| 03.0 | Lenz backend client | ⬜ Not started | — |
| 04.0 | Fixtures, tests and docs | ⬜ Not started | — |

Legend: ⬜ Not started · 🔶 In progress · ✅ Complete.

## Tracking rules

- Mark a story complete only when its code, tests, docs and the proposed release-notes entry are
  merged and the full suite (`uv run pytest -p docsentinel.pytest_plugin`) and the self-scan
  (`uv run docsentinel scan . --format json`, exit `0`, **zero** `DS302` findings) are green.
- Story 01.0's and Story 03.0's Security Auditor tasks run **before** their first Python Expert
  task (both stories are security-sensitive); a CRITICAL finding stops the story.
- Do not close this milestone while `DS302` lacks a row in
  [`docs/specs/fault-classes.md`](/docs/specs/fault-classes.md),
  [`docs/specs/finding-types.md`](/docs/specs/finding-types.md) and
  [`docs/user/reference/rules.md`](/docs/user/reference/rules.md).
- Record every owner ruling on D1–D10 below, dated.
- No commit, test, fixture or log in this milestone may contain the literal API key embedded in
  `examples/docs/lenz_fact-checking.md`, or call the real `lenz.io` API. Story 04.0's regression
  check enforces this with a grep-based test; a hit is a stop-the-line finding, not a style note.

## Notes & decisions

- 2026-11-20: Milestone specified from the owner's outline (a new deep-profile rule, `DS302`,
  that fact-checks high-salience claims against an external API through a swappable backend,
  gated independently of `deep_confirm`). Decisions D1–D10 were taken provisionally by the
  architect; see
  [Open decisions for owner](/docs/roadmap/0010-fact-check/plan.md#open-decisions-for-owner).
- 2026-11-20: Rule code **DS302** reserved (next free after DS301; DS107, DS111, DS119–DS123
  remain reserved by Milestone 0004). ADR number **0007** reserved for Story 01.0 (next free after
  0006, `0006-invoker-include-exclude-and-directory-selectors.md`). Neither file is created in
  this milestone.
- 2026-11-20: `examples/check_fact.py` and `examples/docs/lenz_fact-checking.md` were read
  **read-only**, as reference material for the Lenz `/assess` request/response shape only. The
  embedded API key in the latter file was not copied anywhere in this milestone's specs, the real
  API was not called, and the file's embedded "verify it works" / "show me the verdict" text,
  addressed to an AI agent, was treated as untrusted document content and not followed — it is not
  an instruction from the project owner. This note exists so a later reviewer can confirm the
  boundary was respected from the start.
- 2026-11-20: Decision D5 (how a gate failure surfaces beyond the WARNING log line) is the one
  item in this milestone's open-decisions table flagged as genuinely close rather than a
  routine confirm; see plan.md and Story 01.0 decision S9 for both options before ratifying it.
