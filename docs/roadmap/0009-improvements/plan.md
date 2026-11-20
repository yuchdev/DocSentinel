# Milestone 0009 — Improvements: Reference Scope, CLI Selection, Layered Configuration

**Repository:** https://github.com/yuchdev/DocSentinel  
**Milestone path:** `/docs/roadmap/0009-improvements/`  
**Status:** specification only  
**Dependencies:** Milestone 0005 (shared scanner, `resolve_local_reference()`, DS116 containment
gate, opt-in policy rules), the `link_root` work (site-root base for `/` targets), Milestone 0007
(template-driven reports; no report-format change is needed here). Interacts with Milestone 0008
Story 05.0, see [Cross-milestone notes](#cross-milestone-notes).

## Goal

Make the default scan report what a reader can act on, and make DocSentinel easier to point at the
right files with the right settings:

1. **Reference scope.** By default check only real references: Markdown links and agent-style
   `@`-document mentions. Path-looking inline code spans (DS103) move behind an explicit strict
   mode, because most of them are identifiers, examples or paths relative to some other base.
2. **CLI selection.** `--include` and `--exclude` on the command line, accepting globs, files and
   directories.
3. **Layered configuration.** TOML and JSON configuration, with a user-level JSON settings file
   under the user's data directory, layered under the project config.

## Problem inventory (observed, 2026-11-13)

| # | Problem | Effect |
|---|---|---|
| P1 | DS103 reports about 3,900 warnings on this repository's self-scan and hundreds on a 385-document external repository. Examples are dotted identifiers such as TranslationRunner.run, source paths relative to another root, and site-root paths in prose code spans | Real findings drown; the baseline drifts; Milestone 0008 P2 |
| P2 | Agent documents name files as `@`-mentions, for example the coding-standard mention in every agent prompt. Nothing checks them, and DS103 misreads the code-span form as a broken relative path | A renamed file silently breaks every agent prompt that mentions it |
| P3 | `include`/`exclude` exist only in configuration. A directory value such as docs/archive matches nothing, because file patterns match the whole relative path and exclude patterns match single directory names | Users cannot narrow a scan from the command line, and a natural directory value is a silent no-op |
| P4 | Configuration is per project only and TOML only. There is no place for personal defaults | Every repository repeats the same personal preferences; nothing for tools that emit JSON |

## Design principles

1. **One engine.** Every new behaviour lives behind `scan()` in `/src/docsentinel/engine.py` and
   `load_config()` in `/src/docsentinel/config.py`. CLI, library and pytest plugin behave the same.
2. **Never a silent clean result.** A rule switched off by scope is reported as an opt-in rule that
   is not enabled (notice, `rules`, `doctor`), never as evaluated. A selector that matches nothing
   is reported, never ignored.
3. **Trust follows the source.** Repository files (project config) are untrusted. The command line,
   environment and the user's own settings file are invoker input. A user-level file still may not
   set repository-relative paths (contract C6).
4. **No second resolver.** `@`-references reuse `resolve_local_reference()` and the DS116
   containment helpers. Selector normalisation is lexical.
5. **Fail closed on input, cope on content.** A bad flag, settings file or pattern exits `2`. A
   document is never the reason for exit `2`.
6. **Stdlib only.** `json` and `tomllib`; no new runtime dependency.

## Stories

| Story | Deliverable | Depends on |
|---|---|---|
| 01.0 | **Reference scope and `@`-document references:** new key `reference_scope` (`"links"` default, `"strict"`) and flag `--reference-scope`; DS103 becomes an opt-in rule enabled only by `"strict"`; new fast rule **DS124** reports a dangling `@`-document mention; DS116 also checks `@`-mentions for root escapes; baselines regenerated | — |
| 03.0 | **TOML and JSON configuration; user settings:** strict JSON loader with the same validators as TOML; user-level settings at `$HOME/.local/share/docsentinel/settings.json` (XDG-aware, overridable by `DOCSENTINEL_SETTINGS`), layered under the project config; repository-relative keys refused at user level; `init --user`; `doctor` reports config sources | 01.0 (soft: shared edits of the config and CLI modules, and the user-level key policy includes `reference_scope`) |
| 02.0 | **CLI `--include`/`--exclude`:** repeatable flags on `scan` and `baseline` plus `scan(include=, exclude=)` keywords; globs, files and directories; directory-prefix matching for config patterns too; include replaces, exclude appends; fail-closed normalisation | 03.0 (the precedence chain C1 and the `doctor` source lines) |

Story numbers keep the owner's outline order; **execution order is 01.0, then 03.0, then 02.0**.
All three edit `/src/docsentinel/cli.py` and two edit `/src/docsentinel/config.py`, so they run
serially, not in parallel.

```text
01.0 reference scope ──► 03.0 layered config ──► 02.0 CLI include/exclude
```

## Shared contracts (authoritative)

The story READMEs refine these; when a story and this section disagree, this section wins until
the owner rules otherwise.

### C1 — Configuration precedence

From lowest to highest; each layer replaces a key's value as a whole (no list merging), except
the `--exclude` flag, which appends (C5):

1. Built-in defaults (`Config()`).
2. User settings JSON (Story 03.0), only the keys C6 allows.
3. Project config: docsentinel.toml, its alias doc_sentinel.toml, or `[tool.doc_sentinel]` in
   `/pyproject.toml` (discovery unchanged), or an explicit `--config FILE` (TOML, or JSON by the
   `.json` suffix).
4. Command-line flags and `scan()` keywords (`--profile`, `--select`, `--ignore`, `--baseline`,
   `--reference-scope`, `--include`, `--exclude`, `--link-root`, ...).

A `Config` injected through `scan(config=...)` bypasses layers 1 to 3 exactly as today. Layer-4
keywords still apply on top of it.

### C2 — Opt-in enabling values on `Rule`

`Rule` in `/src/docsentinel/rules.py` gains one defaulted field:

```python
@dataclass(frozen=True)
class Rule:
    ...
    opt_in_option: str = ""
    opt_in_values: frozenset[str] = frozenset()  # new: enabling values; empty = legacy truthiness
```

`opt_in_satisfied(rule, config)` returns `getattr(config, option) in rule.opt_in_values` when the
set is non-empty, and keeps today's "truthy and not `"off"`" test otherwise. Rendering (notice,
`rules`, engine warning) shows `option = "value"` for a rule with enabling values, for example
`DS103 (set reference_scope = "strict")`. Text for DS110, DS112, DS115 and DS118 stays
byte-identical. `ScanResult.opt_in_off` keeps its `(code, option)` shape.

### C3 — `@`-document reference grammar and resolution

Defined in full in [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md#at-reference-grammar).
In short: recognised in prose and as a whole single-token inline code span, never in fenced code or
HTML comments; the last path component needs an extension from `at_reference_extensions`; the
target resolves relative to the referring document first, then relative to the link root;
home mentions (`@~` followed by a slash) and absolute mentions (`@` followed by a slash) are
never resolved. The scanner exposes them as `AtReference` records;
DS124 reports missing ones and DS116 reports escapes.

### C4 — Reference-scope matrix

| Rule | `reference_scope = "links"` (default) | `reference_scope = "strict"` |
|---|---|---|
| DS101 links and anchors | on | on |
| DS103 path-like code spans | inert (opt-in not enabled) | on; skips spans that are `@`-mentions |
| DS116 root escapes | on, including code-span traversal and `@`-mentions | same |
| DS124 `@`-mentions | on | on |
| DS108, DS112, DS113, DS115 | unchanged | unchanged |

### C5 — Selector grammar (include/exclude)

Defined in [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md#selector-grammar).
CLI values use the config grammar, relative to the scan root (an absolute path inside the scan root
is accepted and made relative). A value without glob characters selects that file or directory
and everything below it, in config and on the CLI alike. `--include` replaces the configured list;
`--exclude` appends to it; exclude wins over include.

### C6 — User-level key policy

User settings may set any `Config` key **except** the repository-relative ones: `baseline`,
`include`, `exclude`, `docsig_paths`, `navigation_indexes`, `navigation_required`,
`deprecated_references_file`, `report_templates_dir`, `link_root`, `telemetry_domains`. Such a key
at user level is a `ConfigError` (exit `2`), never silently dropped. `telemetry_extensions` stays
builtin-only at every level.

### C7 — Strict JSON configuration parsing

UTF-8 without BOM, at most 1 MiB, one JSON object at top level holding option keys directly,
duplicate keys rejected, `NaN`/`Infinity` rejected, `null` rejected, nesting errors become
`ConfigError`. After parsing, the **same** validators as TOML run, so the error text is the same.

### C8 — Trust tiers

| Input | Tier | May name paths outside the scan root |
|---|---|---|
| Project config (TOML/JSON in the repository) | untrusted | no (existing bounds) |
| User settings file | invoker | no repository-relative keys at all (C6) |
| CLI flags, `scan()` keywords, environment | invoker | `--link-root` only (existing); selectors never |

## Cross-cutting rules

- Follow `/docs/dev/python_coding_standard.md`, ruff, full annotations, and the logging rules in
  `/docs/specs/logging.md`: lazy `%` formatting, untrusted strings through `safe()`, option *names*
  never values, nothing logged per line in the scanner hot path.
- Never echo document content. A finding `value` is the offending token only, bounded and escaped,
  as DS101 and DS103 do today.
- A home-directory path in an `INFO` line is shown with a leading tilde instead of the home
  directory (PII: the account name).
- Every new or changed rule updates `/docs/user/reference/rules.md` in the same change (the drift
  test `/tests/integration/test_rules_table.py`), plus `/docs/specs/fault-classes.md`,
  `/docs/specs/finding-types.md` and `FAULT_CLASSES` in `/src/docsentinel/telemetry/classify.py`.
- Tests follow the layout in `/CLAUDE.md` "Test layout": unit tests use inline strings only;
  integration tests load assets from one folder per rule code and case under the test assets
  directory and carry the rule IDs as a file-name suffix.
- Docs follow `/docs/dev/documentation_sync.md`; each story ends with a Docs Writer task and a
  proposed `/RELEASE_NOTES.json` entry (the owner decides releases).
- Architecture changes (new rule module, a new config layer, discovery semantics) get an ADR under
  `/docs/adr/` from the story's Architect task, and a `Diagram impact` line handed to
  `diagram-creator` **after** the code lands, because the diagrams show the as-built package.
- Do not edit another milestone's specs; record cross-milestone effects in `status.md`.

## Exit gates

1. `uv sync --locked --extra test`, then `uv run --locked pytest -p docsentinel.pytest_plugin` green
   on Python 3.12 and 3.13.
2. `uv run --locked docsentinel scan . --format json` exits `0`; the default lane reports **0
   DS103** (inert) and **0 DS124** findings on this repository, or each DS124 finding is fixed in the
   documents.
3. `/.docsentinel-baseline.json` regenerated under the new default; no stale DS103 fingerprints
   remain. `/.docsentinel-standard-baseline.json` is unchanged (DS2xx only).
4. `uv build` succeeds.
5. `python scripts/check_doc_links.py docs/` reports 0 problems.
6. Security Auditor verdict PASS (or PASS_WITH_FOLLOWUP with follow-ups recorded) for the three
   surfaces: `@`-reference resolution (01.0), invoker selectors (02.0), user settings and JSON
   parsing (03.0).
7. Honesty review: README, `/CLAUDE.md`, `rules`/`doctor` output and `ScanResult.notice` name DS103
   as opt-in and never claim it ran in `"links"` scope.
8. Every open decision below is ratified or overridden by the owner and recorded in `status.md`.

## Out of scope

- Changing what DS103 considers path-like (Milestone 0008 Story 05.0 owns detector tuning).
- A project-level docsentinel.json discovered automatically (decision D11).
- YAML configuration, remote or organisation-wide configuration.
- `python:` extensions from any configuration file (unchanged: command line only).
- Recursive expansion of `@`-mentions (checking the mentioned file's own mentions is free: it is
  checked when it is itself a discovered document).

## Cross-milestone notes

- **0008 Story 05.0** plans to triage the DS103 warnings. With DS103 inert by default, that triage
  shrinks to the strict lane. Story 01.0 records the before and after counts so 0008 can re-plan;
  this milestone does not edit 0008's specs.
- **0006** (fault events, not built) needs a `FAULT_CLASSES` row for DS124; the row is added here.

## Open decisions for owner

Each is decided as stated so work can proceed; the owner confirms or overrides. Record the ruling
in `status.md` under Notes & decisions.

| # | Decision taken | Recommendation and reason |
|---|---|---|
| D1 | Default `reference_scope` is `"links"`, so DS103 is off by default | Confirm. DS103 is about 99% of self-scan findings and rarely names a real file; strict mode keeps it one flag away |
| D2 | A new rule **DS124** reports dangling `@`-mentions, rather than a new finding type in DS101 | Confirm. Separate `select`/`ignore`, separate severity, no change to DS101 baselines. DS119 to DS123 stay reserved by Milestone 0004 |
| D3 | DS124 default severity is `warning` | Confirm. It is new and on by default; `error` would turn passing CI red on upgrade. Revisit after one release |
| D4 | DS116 keeps checking code-span traversal in `"links"` scope | Confirm. It is low-noise, error severity and a safety guard; narrowing it would silently remove a blocking check |
| D5 | `@`-targets resolve document-relative first, then link-root-relative | Confirm. The first matches Claude Code imports in instruction files; the second matches agent prompts that name files from the project root, as this repository does |
| D6 | A whole inline code span that is exactly one `@path` token counts as a mention | Confirm. This repository writes every mention that way; Claude Code itself would not import such a span, so the doc notes the difference |
| D7 | Release as **1.3.0** (minor) with a "behaviour change" note, not 2.0.0 | Confirm. Default findings shrink and the new rule only warns; exit codes are unchanged unless `--strict` is used |
| D8 | CLI selectors are relative to the **scan root** (the config grammar), with absolute paths accepted; not relative to the current directory | Confirm. One grammar for config and CLI. The common case (scan root is the current directory) is identical; a value that matches nothing is reported |
| D9 | `--include` replaces the configured `include`; `--exclude` appends to the configured `exclude` | Confirm. Include narrows a scan; replacing exclude would quietly scan `.venv` and `node_modules` |
| D10 | Directory-prefix matching also applies to `include`/`exclude` in config files | Confirm. Today such a value silently matches nothing, so no working config changes meaning |
| D11 | JSON is accepted for user settings and for an explicit `--config FILE.json`; no automatic discovery of a project-level docsentinel.json | Confirm. A third standalone name adds ambiguity rules for no stated need; reopen on request |
| D12 | User settings apply everywhere `load_config()` discovers config: CLI, library and pytest plugin; `DOCSENTINEL_SETTINGS=off` or `--no-user-settings` turns them off | Confirm. One engine, same results; the test suite and CI set `off` for hermetic runs |
| D13 | User settings refuse the repository-relative keys (C6); `select` and `ignore` are allowed | Confirm. The CLI can already set them; project config still wins |
| D14 | On POSIX a user settings file that is group- or world-writable, or owned by another user, is refused (exit `2`) | Confirm after the Story 03.0 security review. Same model as `ssh`; a symlinked file is checked at its target. Ratified 2026-11-17 by threat-model-0009-user-settings (R1-R7) |
| D15 | `docsentinel init --user` creates the user settings file; no `init --format json` | Confirm. Project JSON is not discovered (D11), so a project JSON scaffold would mislead |
| D16 | The settings location honours `XDG_DATA_HOME` (absolute values only) and falls back to `$HOME/.local/share` | Confirm. Same default as the owner's path, and correct on XDG systems |
