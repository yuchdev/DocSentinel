# Story 02.0 — CLI `--include` and `--exclude` (directories allowed)

**Category:** discovery and invoker surface · **Touched sources:** `/src/docsentinel/discovery.py`,
`/src/docsentinel/engine.py`, `/src/docsentinel/cli.py`, `/src/docsentinel/__init__.py` (docstring
only, no new export)  
**Parent:** [Milestone 0009 plan](/docs/roadmap/0009-improvements/plan.md) (contracts C1, C5, C8).  
**Depends on:** [Story 03.0](/docs/roadmap/0009-improvements/03.0-toml-json-and-user-settings/README.md)
(precedence chain and the `doctor` config-source lines).  
**Security-sensitive:** yes (invoker path normalisation and containment); Task 02 runs before code.

## Goal

Let the invoker narrow or widen a scan from the command line, with globs, files or directories,
and make a directory value work everywhere, including in config files, where today it silently
matches nothing.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| [01](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/01-adr-selection-semantics.md) | ADR for selector grammar, directory semantics and merge rules | Architect | ✅ Complete |
| [02](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/02-threat-review-invoker-selectors.md) | Security review of selector normalisation and containment | Security Auditor | ✅ Complete |
| [03](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/03-selector-normalisation-and-matching.md) | Normaliser for invoker selectors; directory-aware matching in discovery; per-pattern hit counts | Python Expert | ✅ Complete |
| [04](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/04-cli-and-library-surface.md) | `--include`/`--exclude` on `scan` and `baseline`; `scan(include=, exclude=)`; logging; `doctor` lines | Python Expert | ✅ Complete |
| [05](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/05-tests.md) | Unit, mock and integration tests | Testing Expert | ✅ Complete |
| [06](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/06-docs-and-release-notes.md) | CLI tutorial, configuration reference, library guide, README, release-notes proposal | Docs Writer | ✅ Complete |

## Scope

- Repeatable `--include` and `--exclude` on `scan` and `baseline`.
- Keywords `include` and `exclude` on `docsentinel.scan()` (the CLI passes through them, so there
  is one implementation).
- Directory-prefix matching for literal patterns, in configuration and on the command line.
- Logging and `doctor` output of the effective selection.

## Non-goals

- A flag that removes configured excludes (for example `--no-default-excludes`).
- Regex patterns, negated patterns, or gitignore syntax.
- Following symlinked directories (discovery keeps pruning them).
- Selection for `docsig_paths` (DS204 sources).

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| S1 | Flags `--include PATTERN` and `--exclude PATTERN`, each repeatable (`action="append"`) | Matches `--extension`; a comma list would break on file names with commas |
| S2 | Values are relative to the **scan root**, in the config grammar; an absolute path inside the scan root is accepted and made relative (plan D8) | One grammar: a value copied between CLI and config means the same thing |
| S3 | `--include` replaces the configured list; `--exclude` appends to it (plan D9) | Include narrows a scan; replacing exclude would scan `.venv` and `node_modules` |
| S4 | Exclude wins over include | Already true in discovery; stated as contract |
| S5 | A literal pattern (no glob character) means "this file, or this directory and everything below it", in config and CLI (plan D10) | Today such a value matches nothing, so no working config changes meaning |
| S6 | A directory include admits only Markdown files below it (names ending in `.md`) | Every detector inspects `.md` documents only; including a directory must not inventory images or sources |
| S7 | Invoker values are validated lexically and contained with `contained_path()`; problems exit `2` | Fail closed on input (plan principle 5) |
| S8 | A literal include that names nothing exits `2`; a literal exclude that names nothing logs a `WARNING` and continues | A missing include would produce an empty, falsely clean scan; a missing exclude is harmless (logging spec lists it as a warning). Amended: an empty overall inventory under invoker selectors exits `2` (R1, ADR 0006) |
| S9 | A single-file scan target ignores both flags with one `WARNING` | Existing rule: an explicitly selected file bypasses include and exclude |

### CLI reference

| Command | Flag | Repeatable | Value | Merge |
|---|---|---|---|---|
| `scan` | `--include` | yes | glob, file or directory, relative to the scan root, or absolute inside it | replaces `include` |
| `scan` | `--exclude` | yes | same | appends to `exclude` |
| `baseline` | `--include` | yes | same | replaces `include` |
| `baseline` | `--exclude` | yes | same | appends to `exclude` |

Library:

```python
def scan(
    root: Union[Path, str] = ".",
    *,
    config: Optional[Config] = None,
    link_root: Optional[Union[Path, str]] = None,
    include: Optional[Sequence[str]] = None,   # new: replaces config.include
    exclude: Optional[Sequence[str]] = None,   # new: appended to config.exclude
) -> ScanResult: ...
```

`None` means "not given". An empty sequence is a `ConfigError` ("include needs at least one
value"), so a caller bug never turns into an empty scan. The keywords apply on top of an injected
`Config` too. The pytest fixture does not change.

### Selector grammar

A **glob** is a value containing `*`, `?` or `[`; anything else is a **literal**. Matching is over
the scan-root-relative POSIX path, case-sensitive, with `fnmatchcase()` as today.

| Pattern kind | Include matches path R when | Exclude removes path R when |
|---|---|---|
| glob G | `fnmatchcase(R, G)` (unchanged) | `fnmatchcase(R, G)`, or a directory name on R's path matches G (both unchanged; no relative-path prune) |
| literal L | R equals L, or R lies under L and ends in `.md` (new) | R equals L or lies under L (new: prunes the walk), or a directory name on R's path equals L (unchanged name rule) |

Exclude pruning during `os.walk(topdown=True)` keeps the existing name test for every pattern and
adds the relative-path test for **literal** excludes only, so a literal directory exclude is never
walked. Glob excludes stay byte-identical to today (owner ruling, 2026-11-18; ADR 0006 O1). The
authoritative table is Contract 2 of
[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md).

Invoker values (CLI and keywords) are normalised before they are merged; config values keep
today's validation and only gain the literal semantics above.

```text
Input (scan root /repo)        Normalised       Notes
docs/user                      docs/user        literal: file or directory
docs/user/                     docs/user        trailing slash dropped
./docs//user                   docs/user        leading ./ and repeated / dropped
/repo/docs/user                docs/user        absolute inside the root
docs\user   (Windows)          docs/user        backslash is a separator only on Windows
docs\user   (POSIX)            exit 2           a backslash is refused on POSIX
**/*.draft.md                  (unchanged)      glob, relative to the root
.          (--include)         *.md, **/*.md    the default include
.          (--exclude)         exit 2           excluding everything is refused
../other, docs/../x, /etc      exit 2           outside the scan root or a parent step
/repo/docs/x*  (absolute glob) exit 2           globs must be relative
(empty), control characters    exit 2
```

Bounds: at most 256 values per flag, each at most 1,024 characters. Symlinks: a literal include
whose final component is a symlink exits `2` ("symlinked paths are not inventoried", consistent
with the engine's single-file rule); a literal whose path leaves the scan root through a symlinked
component exits `2` (checked with `contained_path()`, never by following it). Existence is checked
with `os.lstat()` on the contained path only.

### Precedence

Layers per plan C1. For `include`: CLI or keyword value if given, else the project config, else
the default (user settings may not set it, C6). For `exclude`: project config value (or default),
then plus the CLI or keyword values. Exclude then wins over include.

### Showing the effective selection

| Where | Level | Text |
|---|---|---|
| engine, once per scan | `INFO` | `selection: include 1 pattern(s) (invoker), exclude 15 pattern(s) (12 configured, 3 invoker)` |
| engine, per pattern | `DEBUG` | each normalised pattern through `safe()` |
| engine, per invoker include pattern with no document | `WARNING` | `include pattern <p> matched no document` |
| engine, single-file target with flags | `WARNING` | `--include/--exclude ignored for a single-file scan target` |
| engine, invoker selectors given and the inventory is empty | error | `ConfigError`, exit `2` (owner ruling R1, 2026-11-19; [ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md)). Config-only selection keeps exit `0` |
| `doctor` | stdout | `include: 2 pattern(s) (default)` and `exclude: 12 pattern(s) (docsentinel.toml)` for the configuration of the current directory |

### Interactions with rules and options

- DS112: an index document excluded from the inventory keeps today's fail-closed `ConfigError`
  (exit `2`); the error text names the option, so the user sees why.
- DS101, DS103, DS113: links into excluded documents still resolve, because they check the
  filesystem, not the inventory.
- DS114, DS118, DS202, DS203, DS301: corpus results depend on the selection; this is expected and
  documented.
- Baselines: fingerprints are unchanged; findings in excluded documents disappear and would look
  stale to the Milestone 0008 drift check, so `baseline` should be run with the same selection as
  the scan lane it serves.
- pre-commit: flags in a hook's `args:` are fine (they are patterns only, not a trust gate,
  unlike `--link-root`).

## Edge cases

- The same path both included and excluded: excluded.
- Duplicate values: kept once, first occurrence order.
- A directory include under an excluded directory: excluded (exclude prunes the walk).
- An include of a non-Markdown file named explicitly (literal file): included, exactly as a config
  include of that file is today; detectors skip non-`.md` documents.
- Case-insensitive filesystems: matching stays case-sensitive (documented), as today.
- Values that look like options (a leading hyphen) need the `--include=VALUE` form (argparse).

## Security notes

- Invoker input is trusted but may come from a repository's own pre-commit config, so it never
  reads or stats anything outside the scan root, and values are echoed only through `safe()` and
  `neutralize_text()`.
- No pattern compiles to a regex beyond what `fnmatchcase()` does today; bounds cap the cost.
- Task 02 confirms the normaliser cannot be steered outside the root by `..`, absolute paths,
  symlinked components, Windows drive or UNC forms, or Unicode separators.

## Acceptance criteria

- [ ] `docsentinel scan . --exclude docs/archive` removes every document under that directory, and
      the same value in config does the same.
- [ ] `docsentinel scan . --include docs/user` inventories only Markdown files below it.
- [ ] `--include` replaces and `--exclude` appends, through the CLI and through `scan()` keywords,
      including on top of an injected `Config`.
- [ ] Every row of the normalisation table behaves as shown; refused values exit `2` with
      `Scan failed:` and a neutralised message.
- [ ] Logging and `doctor` lines appear as specified; the walk never enters an excluded directory.
- [ ] Existing config-based selection results are unchanged for glob patterns.

## Test plan

| Layer | File (new) | Covers |
|---|---|---|
| Unit | test_invoker_selectors.py in the unit tests folder | Normalisation table, bounds, glob versus literal, Windows separator through an injected flag, empty sequence |
| Unit | test_selector_matching.py | Literal and glob matching for include and exclude, Markdown-only directory include |
| Mock | test_invoker_selectors_containment.py in the mock tests folder | `os.lstat()` only on contained paths; symlinked component refused without following |
| Integration | test_discovery_selectors.py | Trees built in the test body: pruning (walk never enters), precedence, duplicates, single-file warning |
| Integration | test_cli_include_exclude_ds101.py | CLI end to end over ds101 asset cases: a dangling link in an excluded directory disappears; `baseline` honours the flags; exit codes; `doctor` lines |

Asset cases under the ds101 asset folder: selection_excluded_directory and
selection_included_directory (each a tree with a dangling link inside and outside the selected
directory).

## Docs to update

Triggers C, K and P of `/docs/dev/documentation_sync.md`:

- `/docs/user/tutorial/cli.md`: new section "Selecting files: --include and --exclude";
- `/docs/user/reference/configuration.md`: a section for `include` and `exclude` (there is none
  today) with the literal semantics;
- `/docs/user/tutorial/library.md`: the two keywords;
- `/README.md` CLI usage; `/CLAUDE.md` discovery and engine entries;
- `/docs/architecture/README.md` discovery paragraph; diagram follow-up via the Task 01 line;
- a proposed `/RELEASE_NOTES.json` line.
