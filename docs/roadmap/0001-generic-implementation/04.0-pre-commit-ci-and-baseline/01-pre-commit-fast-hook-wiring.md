# Task 01 - Pre-commit Fast Hook Wiring

**Story:** [04.0 - Pre-commit, CI & Self-Scan Baseline](README.md)
**Depends on:** Milestone 0001 Story 02.0 (real findings), Story 03.0 Task 01 (severity-aware
exit codes - a pre-commit hook that fails on every `DS102` warning would be unusable)

## Purpose

`.pre-commit-hooks.yaml`'s `docsentinel-fast` entry already exists (`entry: docsentinel scan
--profile fast`, `always_run: true`, `pass_filenames: false`) but has done nothing until now
because `fast` had no detectors. This task confirms/adjusts it for the newly-real behavior and
adds the test coverage a pre-commit hook definition can't get from `pytest` alone.

## Files

| Path | Action |
|------|--------|
| `.pre-commit-hooks.yaml` | Modify |
| `tests/test_pre_commit_hook_manifest.py` | Create |

## Decision

- Keep `pass_filenames: false` and `always_run: true` - DocSentinel's own discovery already walks
  the whole tree per its `include`/`exclude` config; per-file invocation would fight that, not
  complement it (a dangling-anchor check for file A can depend on file B's headings, so scoping
  the hook to only changed files would silently miss cross-file breakage - exactly the scenario
  `doc_link_check.py`'s own design in the agent-fleet precedent this project drew from runs a
  full-corpus `Stop`-time sweep for).
- Default severity behavior (no `--strict`) applies - a hook that fails every commit touching a
  file with a pre-existing `warning` would get disabled by the first contributor it annoys.
  `error`-only failure (`DS101`, dangling links) is the right bar for something that blocks
  every commit.
- Add `language_version: python3` is **not** needed (`language: python` with no pinned version is
  already correct for a hook whose `entry` is the installed console script) - do not add
  speculative pre-commit config keys without a concrete reason.

## Symbols / fields

`.pre-commit-hooks.yaml`: no structural change is required if the Decision above already matches
today's file (verify by reading it at implementation time - this task may turn out to be
verification-only). If it does not match (e.g. if a future change added `--strict` or
per-file args), restore it to: `entry: docsentinel scan --profile fast`, nothing else changed.

## Tests (`tests/test_pre_commit_hook_manifest.py`)

Pre-commit hook manifests are YAML, not Python, so this is a thin structural test rather than a
behavioral one:
- `test_hook_manifest_is_valid_yaml_with_expected_fields` - parse `.pre-commit-hooks.yaml`,
  assert the `docsentinel-fast` entry's `id`, `entry`, `language`, `pass_filenames`, `always_run`
  values match the Decision exactly.
- `test_hook_entry_command_runs_clean_on_a_clean_tree` - an integration-style test: write a
  minimal clean Markdown tree to `tmp_path`, run the exact string in `entry` as a subprocess
  (`shlex.split` it) with `cwd=tmp_path`, assert exit code `0`. This is the only test in this
  milestone allowed to shell out to the installed console script rather than calling `cli.main`
  directly - it is specifically testing the *installed command name* pre-commit will invoke.

## Success criteria

- [ ] The hook, run against a tree with one planted `DS101` dangling link, exits non-zero.
- [ ] The hook, run against a tree with only a planted `DS102` stray comment, exits `0` (warning,
      not error, per Story 03.0 Task 01's default behavior) - this is the test that actually
      justifies this task's existence; get it wrong and every contributor's first stray comment
      blocks their commit.

## Constraints

- No new dependency; `PyYAML` (or `tomllib`-adjacent) parsing for the manifest test should use
  whatever YAML library is already available via `pre-commit`'s own dependency chain if the repo
  has it, or the stdlib-adjacent minimal approach of reading the file as text and asserting on
  the `entry:` line's exact string if pulling in a YAML parser just for one test is not already
  justified elsewhere in the dependency tree - check `uv.lock` first before adding `pyyaml`.
