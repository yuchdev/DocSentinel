# Task 03 - Self-Scan Baseline Capture

**Story:** [04.0 - Pre-commit, CI & Self-Scan Baseline](README.md)
**Depends on:** Task 02 (baseline mechanism must exist)

## Purpose

The last step of Milestone 0001: turn the real fast-profile scan on for **this repository's own
docs**, see what it actually finds, fix what is cheap to fix outright, baseline only what
genuinely needs a later pass, and make CI enforce "the baseline never grows" instead of the
current no-op self-scan. This is a one-time repo chore plus a small CI change - not a reusable
code task, so it has no "Symbols / fields" table.

## Files

| Path | Action |
|------|--------|
| `.docsentinel-baseline.json` | Create (repo root) |
| `doc_sentinel.toml` | Create (repo root) - `baseline = ".docsentinel-baseline.json"`, plus whatever `include`/`exclude` this repo's own scan needs (see Decision) |
| `docs/adr/0001-config-loading-via-layered-settings.md` | Modify - fix, don't baseline, its three already-known dangling links (see Decision) |
| `.github/workflows/ci.yml` | Modify - the self-scan step becomes a real gate |
| `docs/README.md` | Modify - add rows for the two new root files |

## Decision

- **Fix, don't baseline, anything a human can fix in under a few minutes.** The illustrative ADR
  0001's three dangling links (already identified during Story 02.0 Task 01's own real-world
  smoke test against this exact file) are a one-line-each fix: either repoint them at the
  correct still-existing content, or - since that whole file is explicitly marked "delete...
  once this project has written its own first real ADR" - replace the three links with plain
  (non-link) prose referencing the deleted example paths by name, since the ADR is intentionally
  illustrative/historical and does not need live links to content that was deliberately removed.
  Prefer the second option (de-link rather than re-link to a stand-in target) since re-pointing
  them at unrelated real files would be misleading in an ADR whose whole point is to show a
  *hypothetical* example.
- **Everything else the first real scan finds** (stray comments, unresolvable path-like spans
  anywhere else in `docs/`, `.claude/`, or repo-root Markdown) gets captured into the baseline
  rather than fixed in this task - this task's job is to turn the gate on safely, not to do a
  full documentation audit in passing. Note the baseline's entry count in this task's own
  completion note in `status.md` so the backlog size is visible.
- **Scan scope for this repo's own `doc_sentinel.toml`**: default `include`/`exclude` are
  probably already adequate (`*.md`/`**/*.md`, excluding `.git`/`.venv`/`node_modules`) - add
  `dist` to `exclude` (this repo's own `dist/` holds a built wheel/sdist, not docs) if discovery
  would otherwise descend into it. Verify by running the scan once before finalizing the file.
- **CI change**: replace `uv run --locked docsentinel scan . --format json` (which today
  succeeds regardless of findings since `--format` alone doesn't fail the build on its own merit)
  with a step that fails the workflow when `docsentinel scan .` exits non-zero. The existing
  `--format json` can stay as an *additional* step for log visibility, but a separate,
  exit-code-checked invocation (plain `docsentinel scan .`, default text format, default - not
  `--strict` - severity behavior) is what actually gates the build. Do not add `--strict` to CI
  without a separate decision to do so; defaults match the pre-commit hook from Task 01 for
  consistency between local and CI gating.

## Process (not a code spec - a checklist for whoever executes this task)

1. Run `uv run docsentinel scan . --format json` against the repo as it stands after Stories
   02.0-03.0 land, with no config file yet, to see raw findings.
2. Fix the ADR 0001 dangling links per the Decision above.
3. Re-run; confirm the only remaining findings are ones worth baselining rather than fixing now.
4. Create `doc_sentinel.toml` per the Decision's scan-scope note.
5. Run `docsentinel baseline .` (Task 02's subcommand) to produce `.docsentinel-baseline.json`.
6. Re-run `docsentinel scan .` and confirm exit code `0` (everything remaining is baselined).
7. Update `.github/workflows/ci.yml` per the Decision.
8. Update `docs/README.md`'s registry table with the two new root-level files.

## Success criteria

- [ ] `docsentinel scan .` exits `0` on a clean checkout of this repo once this task lands.
- [ ] The illustrative ADR 0001 has zero dangling links after this task (verified both by
      `docsentinel scan` and by `python scripts/check_doc_links.py docs/` - the two tools should
      agree, since `DS101`'s algorithm was ported from the latter in Story 02.0 Task 01).
- [ ] `.github/workflows/ci.yml`'s self-scan step genuinely fails the workflow on a findings-
      producing change - verified by a throwaway local branch with one planted dangling link
      pushed through CI once (not a permanent test fixture; a manual verification step for
      whoever implements this task, noted in their completion summary rather than committed).
- [ ] `status.md`'s Story 04.0 completion note states the baseline's finding count at capture
      time, so the backlog this task deliberately deferred is visible to future contributors.

## Constraints

- This task must not silently widen `exclude` to make inconvenient findings disappear instead of
  baselining them - `exclude` changes are for genuinely out-of-scope content (build artifacts,
  vendored files), baselining is for everything else.
- Keep `doc_sentinel.toml` minimal - only the fields this repo's own scan actually needs
  non-default values for; do not pre-populate `select`/`ignore` speculatively.
