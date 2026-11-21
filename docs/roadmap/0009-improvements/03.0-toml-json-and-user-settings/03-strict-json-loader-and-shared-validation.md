# Task 03 — Strict JSON loader and one validation path

**Parent story:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)  
**Role:** Python Expert  
**Depends on:** Tasks 01 and 02.

## Inputs

- Story README "Strict JSON parsing", "Shared validation and layering" (steps 2 and 3 only),
  decisions S2 and S7; ADR 0005 Contracts 2, 3 and 5.
- The Task 02 threat model,
  [threat-model-0009-user-settings-2026-11-17.md](/docs/security/threat-model-0009-user-settings-2026-11-17.md):
  R7, U2, U6, U8, U9, U11, follow-up F1 and amendments A1 and A6 (link it in the briefing).
- `/src/docsentinel/config.py`: `_load_toml_table()`, `load_config()`, `_load_extra_options()`.

## Steps

1. Refactor `load_config()` so reading (TOML, pyproject table, JSON) produces a raw options
   mapping and one function builds the `Config` from a mapping. Behaviour and every existing error
   message stay identical (existing config tests must pass unchanged), with one allowed exception
   (threat model A6, U8): float-valued options require a finite, float-convertible value and map
   `OverflowError` to the option's existing message (for example
   `max_grade_level must be a positive number`), in TOML and JSON alike. This fixes today's TOML
   `nan`/`inf` gap and the overflow crash (traceback, exit `1`). `_load_toml_table()` maps the
   integer-string-limit `ValueError` to `ConfigError` `Cannot read <path>: number out of range`
   (F1), so `doctor` no longer crashes on a repository's TOML.
2. Add `MAX_JSON_CONFIG_BYTES` and `load_json_options()` exactly per the story's numbered rules
   and ADR 0005 Contract 2. Open once (A1, R7): `os.stat()` regular-file pre-check (a FIFO or
   device is never opened), `os.open(O_RDONLY | O_NONBLOCK | O_NOCTTY)`, `os.fstat()` on the
   descriptor (authoritative regular-file check), then a bounded read of the cap plus one byte from
   that same descriptor, closed in `finally`. Build this as a private open-once helper that Task 04
   reuses with its ownership and mode check; `load_json_options(source)` keeps its signature and
   calls the helper without the ownership check. Any `OSError` maps to `not readable`. Then (A6):
   decode with strict UTF-8 and pass only `str` to `json.loads`; the duplicate-key hook; the
   constant hook; a `parse_float` that refuses a non-finite result; an iterative (explicit-stack)
   `null` walk; `except` order `ConfigError` (re-raise unchanged), `RecursionError`
   (`nested too deeply`), `ValueError` (the integer digit limit as `number out of range`,
   `JSONDecodeError` with line and column only).
3. Route an explicit `path` with a `.json` suffix (case-insensitive) to the JSON reader; keep
   pyproject.toml wrapped; everything else TOML.
4. `DEBUG` log `loading config <path> (json)` beside the existing TOML line; names of set options
   only.
5. Report a `Docs impact:` line (K, C).

## Files

`/src/docsentinel/config.py`.

## Verification

- test_json_config_loader.py and test_config_message_parity.py (Task 06) green with `-q`.
- All existing config tests green without modification, except where they pin the TOML `nan`,
  `inf` or overflow behaviour that A6 deliberately changes.

## Acceptance

- [ ] A JSON file with the same options as a TOML file yields an equal `Config`.
- [ ] Every malformed-JSON case exits `2` with a message that does not echo content.
- [ ] Message parity holds for every validator.
- [ ] A 100,000-digit integer, `1e400` and a 5,001-digit TOML integer each give a `ConfigError`
      (exit `2`), never a traceback; `doctor` survives the TOML case (F1).
