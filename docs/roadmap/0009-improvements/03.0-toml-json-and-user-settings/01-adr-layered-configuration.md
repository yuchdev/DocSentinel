# Task 01 — ADR for layered configuration and JSON support

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Architect  
**Depends on:** Story 01.0 complete.

## Inputs

- Story README "Decisions", "Shared validation and layering", "User-level key policy"; plan C1,
  C6, C7, C8 and decisions D11 to D16.
- `/src/docsentinel/config.py` (`load_config()`, `_load_toml_table()`), `/src/docsentinel/engine.py`
  (`scan()` loads config when none is injected), `/src/docsentinel/pytest_plugin.py`,
  `/src/docsentinel/cli.py`.
- `/docs/adr/0001-config-loading-via-layered-settings.md` is an illustrative example only; do not
  cite it as prior art or chain to it.

## Steps

1. Take the next free ADR number (expected 0005) and write a MADR record "Layered configuration:
   user settings JSON under project TOML", status `Proposed`. Considered options at least:
   (a) user JSON layered under project config, restricted keys (chosen); (b) user file with all keys;
   (c) no user layer, environment variables per key; (d) project JSON discovery as well. Pros and
   cons for each, including what gets harder (reproducibility across machines, mitigated by
   `DOCSENTINEL_SETTINGS=off` in CI and tests).
2. Specify `load_config()`, `load_config_with_sources()`, `ConfigSources` and
   `load_json_options()` signatures, the precedence chain, the refused-key set and the error-prefix
   rule. Name the affected components (config loader, engine, CLI, pytest plugin, library callers,
   the test suite's conftest) and the migration path (none for existing projects; a user file is
   opt-in by existing).
3. List affected diagrams (configuration loading in `/docs/diagrams/` and
   `/docs/architecture/README.md`), add a sequence diagram follow-up for the layered load, record
   it for `diagram-creator` after the code lands, and end with one `Diagram impact:` line.

## Files

- New ADR under `/docs/adr/`; `/docs/adr/README.md` index row.

## Verification

- `python scripts/check_doc_links.py docs/adr docs/roadmap` reports 0 problems.

## Acceptance

- [ ] ADR `Proposed`, options and consequences complete, contracts unambiguous.
- [ ] Diagram follow-up recorded, no diagram source edited.
