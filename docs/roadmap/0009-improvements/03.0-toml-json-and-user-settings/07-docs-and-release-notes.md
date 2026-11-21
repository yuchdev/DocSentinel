# Task 07 — Documentation and release-notes proposal for layered configuration

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Docs Writer  
**Depends on:** Tasks 03 to 06 (code final, tests green).

## Inputs

- `Docs impact:` lines from Tasks 03 to 05; story README "Docs to update".
- `/docs/dev/documentation_sync.md` (triggers K, C, P, A).
- The Task 02 threat model,
  [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md):
  R1-R7, U4, U10, U14 and amendment A12.

## Steps

1. `/docs/user/reference/configuration.md` "How to set options": the four layers in order, the JSON
   format with an example, the settings path (XDG rule, `DOCSENTINEL_SETTINGS`, `off`), the refused
   keys and why, the note on `deep_confirm` at user level, and "JSON is not discovered in
   projects; use `--config FILE.json`". Document the permission rule R1-R7 in user terms (file
   and its holding directories owned by you or root, not group- or world-writable, sticky
   directories allowed, a violation exits `2`, skipped on non-POSIX) with the fix
   `chmod go-w` on the file; the WSL drvfs note (files under the Windows mount report mode 0777
   and are refused; keep the file in the Linux home; U14); and that a tool which sets
   `DOCSENTINEL_SETTINGS` for you (direnv, pytest-env, tox, IDE settings) is trusted with your
   settings (U10).
2. `/docs/user/tutorial/cli.md`: `init --user`, `--no-user-settings`, `--config FILE.json`, the
   `doctor` lines; tell CI users to set `DOCSENTINEL_SETTINGS=off` at job level, naming
   self-hosted runners explicitly, because a persistent runner home can carry a settings file
   from one job to the next (U4). Give the same advice in the pre-commit and library docs.
3. `/docs/user/tutorial/library.md`: user settings apply to `scan()` and the pytest fixture; how to
   turn them off (`load_config(..., user_settings=False)`, the environment) and
   `load_config_with_sources()`.
4. `/docs/specs/logging.md`: add the new lines to the examples, only after the concurrent logging
   change has landed (rebase first; do not overwrite it).
5. `/README.md` configuration section; `/CLAUDE.md` config entry, Commands (`init --user`) and the
   environment variables.
6. `/docs/architecture/README.md` configuration layer; hand the Task 01 `Diagram impact:` line to
   `diagram-creator` through the caller.
7. Propose a `/RELEASE_NOTES.json` line.
8. Run `python scripts/check_doc_links.py docs/`.

## Files

The documents named above; no source files.

## Verification

- Link check 0 problems; self-scan adds no finding in the edited documents.

## Acceptance

- [ ] All listed documents current; release-notes line proposed.
