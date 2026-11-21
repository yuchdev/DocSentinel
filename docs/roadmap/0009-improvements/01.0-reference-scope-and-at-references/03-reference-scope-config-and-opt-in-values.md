# Task 03 — `reference_scope`, `at_reference_extensions`, `--reference-scope`, opt-in values

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Python Expert  
**Depends on:** Tasks 01 and 02.

## Inputs

- Story README "Config reference", "CLI reference", "How the mode is reported"; plan C2.
- [Threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md) (standing input):
  M20 (config bounds for `at_reference_extensions`, fail-closed re-validation of an injected
  `Config`, an unknown injected `reference_scope` keeps DS103 inert).
- `/src/docsentinel/config.py`, `/src/docsentinel/rules.py`, `/src/docsentinel/engine.py`,
  `/src/docsentinel/cli.py`, `/src/docsentinel/detectors/paths.py`.

## Steps

1. `/src/docsentinel/config.py`: add `reference_scope` (enum `links`, `strict`, default `"links"`) to the known
   options and the enum table; add `at_reference_extensions` with a dedicated validator (1 to 64
   entries, each matching ASCII letters or digits, 1 to 16 characters, duplicates after lowercasing
   refused, empty list refused with the message pointing to `ignore = ["DS124"]`). Store the
   extensions lowercased as a tuple. Document both in the `Config` docstring.
2. `/src/docsentinel/rules.py`: add `opt_in_values: frozenset[str] = frozenset()` to `Rule`; extend
   `opt_in_satisfied()` per plan C2. Add a helper `opt_in_hint(rule) -> str` returning
   `option` or `option = "value"` so the engine and CLI render the same text.
3. `/src/docsentinel/detectors/paths.py`: register DS103 with `opt_in_option="reference_scope"` and
   `opt_in_values=frozenset({"strict"})`. Title, description and severity unchanged.
4. `/src/docsentinel/engine.py`: build the notice and the rule-plan warning with `opt_in_hint()`. Keep
   `ScanResult.opt_in_off` as `(code, option)` pairs. Byte-identical text for DS110, DS112, DS115,
   DS118. Coordinate with any concurrent logging change in this file; do not reformat unrelated
   lines.
5. `/src/docsentinel/cli.py`: add `--reference-scope {links,strict}` to `scan` and `baseline` (default `None`,
   applied with `dataclasses.replace()` after `load_config()`); use `opt_in_hint()` in the `rules`
   suffix; in `doctor`, print `reference scope: <value> (DS103 on|off)` for the configuration of
   the current directory (a `ConfigError` prints one neutralised error line, as the extension line
   does). Add `reference_scope=<value>` to the `scan started` and `baseline started` `INFO` lines.
6. Update `/examples/docsentinel.toml` and the `init` template comment block with both keys
   (commented, defaults shown).
7. Update `/docs/user/reference/rules.md` DS103 activation cell and config-keys column in the same
   change (the drift test requires it). DS124 is added in Task 05.
8. Report a `Docs impact:` line (R, C, K).

## Files

`/src/docsentinel/config.py`, `/src/docsentinel/rules.py`, `/src/docsentinel/engine.py`,
`/src/docsentinel/cli.py`, `/src/docsentinel/detectors/paths.py`, `/examples/docsentinel.toml`,
`/docs/user/reference/rules.md`, and the test-side drift expectations in
`/tests/integration/test_rules_table.py` if the activation parser needs the `option = "value"`
form.

## Verification

- Unit: test_reference_scope_config.py and test_rule_opt_in_values.py (written with Task 06 or
  here, whichever comes first) pass with `-q`.
- `python .github/hooks/scripts/style_fixes.py --check` on each changed file; ruff clean.
- `uv run docsentinel rules` shows the DS103 suffix; `uv run docsentinel doctor` shows 5 opt-in
  rules (4 plus DS103) and `17 registered` (18 once DS124 lands in Task 05; DS100 is counted).
- `opt_in_values`, `opt_in_satisfied()`, `opt_in_hint()` and the `register_rule()` invariants
  follow [ADR 0004](/docs/adr/0004-reference-scope-and-at-document-references.md) Contract 1
  exactly (including the `isinstance(value, str)` guard).

## Acceptance

- [ ] Default scope is `"links"`; DS103 is inert and named in the notice with the hint.
- [ ] `--reference-scope strict` on `scan` and `baseline` enables DS103; CLI beats config.
- [ ] Existing opt-in notice text unchanged byte for byte (golden test).
- [ ] Invalid values exit `2` with the validator message.
