# Task 02 — Threat model: user settings file and JSON parser

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Security Auditor  
**Depends on:** Task 01. Must finish before Task 03.

## Inputs

- Story README "Settings path and environment", "Strict JSON parsing", "User-level key policy",
  "Security notes", "Edge cases".
- Existing trust precedents: the `python:` extension gate in `/src/docsentinel/cli.py`, the
  `link_root` bounds in `/src/docsentinel/link_root.py`, the log-file directory rules in
  `/docs/specs/logging.md` (mode `0o700`, symlinks not followed for deletion).

## Steps

1. Model the actors: the user (owner of the file), another local user, a malicious repository
   (cannot write the user file but controls project config), a CI runner, a dotfile manager that
   symlinks the file.
2. Threats, each with a mitigation and a test name:
   - a writable-by-others or foreign-owned settings file enabling `deep_confirm` or changing
     thresholds (decide: ownership and mode rule, whether parent directories are checked, whether
     root-owned files are accepted, error versus warning);
   - a project config that tries to influence where user settings are read (it must not: only the
     environment and the flag can);
   - a user-level key that reaches repository paths (C6), or `python:` extensions;
   - parser denial of service (size, nesting, huge numbers such as a 100,000-digit integer, which
     Python's integer-string limit already refuses; confirm the error is mapped to `ConfigError`);
   - duplicate-key smuggling, BOM, non-finite numbers, `null`;
   - echo of file content or of the home path in errors and logs (tilde form, names only);
   - the test suite reading the developer's real file.
3. Verdict PASS, PASS_WITH_FOLLOWUP or BLOCK; a CRITICAL finding stops the story. Record the final
   permission rule so plan decision D14 can be ratified.

## Files

- New threat model under `/docs/security/` named with the topic and date.

## Verification

- Every mitigation maps to a test in Task 06 or an acceptance criterion.

## Acceptance

- [ ] Threat model written with a verdict and the permission-rule ruling; Tasks 03 to 05 reference it.
