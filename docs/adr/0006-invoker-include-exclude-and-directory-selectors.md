# 0006 - Invoker Include/Exclude and Directory Selectors

> **Status:** Accepted (2026-11-20, owner)
>
> **Date:** 2026-11-18
>
> **Supersedes:** _(none)_
>
> **Superseded by:** _(none)_

## Context and Problem Statement

Which documents a scan sees is decided only by the `include` and `exclude` lists of the project
configuration. Both default to `("*.md", "**/*.md")` and `(".git", ".venv", "node_modules")`.
`discover_with_skips()` in `/src/docsentinel/discovery.py` walks the scan root with
`os.walk(topdown=True)`, prunes symlinked directories and directories whose *name* matches an
exclude pattern, skips symlinked and non-regular files, and matches each file's scan-root-relative
POSIX path with `fnmatchcase()`. There are two gaps
([Milestone 0009 plan, Story 02.0](/docs/roadmap/0009-improvements/plan.md)):

- **No invoker selection.** A person, a CI lane or a library caller cannot narrow or widen one run
  without editing the repository's configuration. `scan()` has keywords for `config` and
  `link_root` only, and the CLI has no selection flag.
- **Directory values silently match nothing.** `exclude = ["docs/archive"]` removes nothing below
  that directory, because `fnmatchcase("docs/archive/a.md", "docs/archive")` is false and the
  directory-name test compares one name, never a relative path. `include = ["docs/user"]` admits
  nothing. Neither is reported, so a scan can look narrower or wider than the user intended.

The question is how invoker values are written, which base they are relative to, how they combine
with the configured lists, and what a value without glob characters means, without changing any
working configuration and without giving an invoker value a way to reach outside the scan root.

## Decision Drivers

- **One grammar** (plan C5). A value copied between the command line and a configuration file
  must mean the same thing.
- **One engine** (plan principle 1). The CLI, the library and the pytest plugin select documents
  through `engine.scan()`; the CLI passes through `scan()` keywords, so there is one
  implementation.
- **Never a silent clean result** (principle 2). A selector that names nothing must not turn into
  an empty, clean-looking scan.
- **Fail closed on input** (principle 5). An invoker value that is malformed, unbounded or leaves
  the scan root exits `2` before discovery.
- **Trust tiers** (plan C8). Selectors are invoker input but may arrive through a repository's own
  pre-commit `args:`, so they never name, read or stat a path outside the scan root.
- **No silent behaviour change for working configurations.** Glob results stay as they are; only
  values that match nothing today gain meaning.
- **Precedence as ADR 0005 fixed it.** Defaults, user settings, project config, then CLI flags and
  keywords; `include` and `exclude` are C6-refused at user level.
- **Stdlib only** (principle 6), no regex beyond what `fnmatchcase()` does today.

## Considered Options

Value base (which directory a relative selector is relative to):

1. **(A1) The scan root** (chosen). An absolute path inside the scan root is accepted and made
   relative.
2. **(A2) The current working directory**, like most shell tools.
3. **(A3) Mixed**: literal paths relative to the current directory, globs relative to the scan
   root.

Merge with the configured lists:

4. **(B1) Replace both** lists.
5. **(B2) Append both** lists.
6. **(B3) `--include` replaces, `--exclude` appends** (chosen).

Meaning of a value without glob characters:

7. **(C1) "This file, or this directory and everything below it"**, in config and on the command
   line alike (chosen, plan D10).
8. **(C2) Unchanged exact-path match**; users write `docs/archive/**` for a directory.
9. **(C3) Directory semantics for invoker values only**; config keeps exact-path match.

## Decision Outcome

Chosen: **A1, B3 and C1**. A1 is the only base that gives one grammar for config and CLI (C5).
B3 lets `--include` narrow a scan while the configured excludes (`.venv`, `node_modules`) keep
protecting it. C1 gives directory values a meaning where today they silently match nothing, so no
working configuration changes, and it keeps config and CLI identical.

### Decisions recorded

Story decisions S1 to S9, from the
[Story 02.0 README](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md#decisions),
adopted verbatim:

| # | Decision |
|---|---|
| S1 | Flags `--include PATTERN` and `--exclude PATTERN`, each repeatable (`action="append"`), on `scan` and `baseline`. |
| S2 | Values are relative to the **scan root**, in the config grammar; an absolute path inside the scan root is accepted and made relative (D8). |
| S3 | `--include` replaces the configured list; `--exclude` appends to it (D9). |
| S4 | Exclude wins over include. |
| S5 | A literal pattern (no glob character) means "this file, or this directory and everything below it", in config and CLI (D10). |
| S6 | A directory include admits only Markdown files below it (names ending in `.md`). |
| S7 | Invoker values are validated lexically and contained with `contained_path()`; problems exit `2`. |
| S8 | A literal include that names nothing exits `2`; a literal exclude that names nothing logs a `WARNING` and continues. |
| S9 | A single-file scan target ignores both flags with one `WARNING`. |

Milestone decisions D8 to D10 from the
[plan's open decisions](/docs/roadmap/0009-improvements/plan.md#open-decisions-for-owner) were
adopted as recommended on 2026-11-14, pending owner override (see
[status.md](/docs/roadmap/0009-improvements/status.md)).

This ADR adds the clarifications marked **(ADR)** below. They are contract-level choices the story
leaves open; each is listed under [Open points for the owner](#open-points-for-the-owner).

### Contract 1: `scan()` keywords (`/src/docsentinel/engine.py`)

Described, not implemented. Follows `/docs/dev/python_coding_standard.md` (`Optional[T]`, full
annotations, reStructuredText docstrings); `Sequence` comes from `collections.abc`.

```python
def scan(
    root: Union[Path, str] = ".",
    *,
    config: Optional[Config] = None,
    link_root: Optional[Union[Path, str]] = None,
    include: Optional[Sequence[str]] = None,   # new: replaces the effective include
    exclude: Optional[Sequence[str]] = None,   # new: appended to the effective exclude
) -> ScanResult: ...
```

| Keyword value | Meaning |
|---|---|
| `None` (default) | Not given. The layer does not apply; the effective list is the configured one. |
| Non-empty sequence of non-empty `str` | Normalised (Contract 3), then merged (Contract 4). |
| A bare `str` or `bytes` **(ADR)** | `ConfigError`: `include must be a sequence of patterns, not a single string`. A `str` is a `Sequence[str]`, so without this rule `"docs"` would be read as four one-character patterns. |
| Not a `collections.abc.Sequence` (a generator, a set, an iterator) | `ConfigError`: `include must be a sequence of patterns` (threat model A8). |
| Empty sequence (`()`, `[]`) | `ConfigError`: `include needs at least one value` (or `exclude ...`). A caller bug never becomes an empty scan. |
| More than 256 items | `ConfigError`: `include accepts at most 256 values`, checked with `len()` **before** any item is read. |
| An item that is not a `str`, or an empty `str` | `ConfigError`: `include values must be nonempty strings`. |
| An item over 1,024 characters | `ConfigError`: `include value is longer than 1024 characters`, checked before any character check, neutralisation or echo. |

**Shape order (threat model A8).** The checks run exactly in the table's order from the bare
`str` row down: type of the container, emptiness, `len() <= 256`, then per item its type and
`len() <= 1024`. A multi-megabyte library value is therefore never scanned, neutralised or echoed.
**Shape errors echo no value** (A7): their messages carry only the key name, counts and limits.

- **Injected `Config`.** The keywords apply on top of an injected `Config` exactly as on a loaded
  one (C1 layer 4). The injected object is frozen and never mutated: the engine uses
  `dataclasses.replace(settings, include=..., exclude=...)`. The CLI always injects its `Config`,
  so the CLI and the library take the same path and give identical results.
- **Config values are not re-validated.** The configured `include` and `exclude` (from a file or an
  injected `Config`) keep today's validation (`<name> must be a list of nonempty patterns`) and
  gain only the literal semantics of Contract 2. They are matched as strings and never trigger
  filesystem access; the existence and containment checks of Contract 3 apply to invoker values
  only.
- **The merged `Config` is what analyzers see.** Every analyzer receives the merged settings, so a
  DS112 navigation index removed by `--exclude` keeps today's fail-closed `ConfigError` (exit `2`).
- **No new export.** `docsentinel.__init__` gains no name; its docstring mentions the keywords.
  `Config`, `ScanResult`, JSON schemas, report templates and baseline fingerprints are unchanged.
  The selection is not recorded in `ScanResult` or a report.
- **Pytest plugin.** The `docsentinel_scan` fixture does not change and passes no selector.

### Contract 2: matching table (authoritative)

A **glob** is a value containing `*`, `?` or `[`; any other value is a **literal**. Matching uses
the scan-root-relative POSIX path, is case-sensitive, and uses `fnmatchcase()` only (in which `*`
also matches `/`, as today). Notation: R is a regular file's relative path, D is a directory's
relative path during the walk and N its last name; "R under L" means `R.startswith(L + "/")`.

| Pattern | Include admits file R when | Exclude removes file R when | Exclude prunes directory D when |
|---|---|---|---|
| glob G | `fnmatchcase(R, G)` (unchanged) | `fnmatchcase(R, G)`, or `fnmatchcase(P, G)` for a directory name P on R's path (both unchanged) | `fnmatchcase(N, G)` only (unchanged; never by relative path) |
| literal L | `R == L` (unchanged), or R under L and `R.endswith(".md")` (**new**) | `R == L` (unchanged), or R under L (**new**, by pruning), or a directory name on R's path equals L (unchanged) | `N == L` (unchanged), or `D == L` (**new**) |

**Globs are byte-identical** (owner ruling on O1, 2026-11-18). Only a literal exclude prunes a
directory by its relative path. A glob exclude keeps today's directory-name pruning and today's
file matching exactly, so every existing glob configuration gives the same inventory and skip
count as before. A glob such as `docs/v?` or `**/archive` therefore still does not remove
`docs/v1/a.md` or `docs/archive/a.md`; writing the literal `docs/archive` (or the glob
`docs/archive/*`) does.

Rules that complete the table:

1. **Exclude wins.** A file removed by any exclude pattern is never admitted, whatever include says.
   A pruned directory is never walked, so its files are never examined.
2. **Include never prunes.** The walk still visits every non-excluded, non-symlinked directory;
   `--include docs/user` narrows the inventory, not the walk.
3. **Markdown-only directory include.** Below a literal directory include only names ending in
   `.md` (case-sensitive) are admitted. A literal include equal to a file's path admits that file
   whatever its suffix, as a config include of that file does today; detectors skip non-`.md`
   documents.
4. **Unchanged skips.** Symlinked directories are pruned and symlinked or non-regular files are
   skipped, before any pattern is tested. An excluded directory counts once in the skip count, by
   either rule.
5. **No escape syntax.** A file whose name contains `*`, `?` or `[` can only be selected by a glob
   that matches it (for example `notes[[]1].md`), as with `fnmatchcase()` today.
6. **Hit counts.** Discovery counts, per include pattern in effective-list order, the admitted
   documents it matches; a document counts toward every pattern it matches. These counts feed the
   zero-hit `WARNING` (Contract 5).

Proposed discovery signatures (`/src/docsentinel/discovery.py`):

```python
def is_glob(pattern: str) -> bool:
    """Return True when the pattern contains *, ? or [."""

def selector_matches(relative: str, pattern: str, *, include: bool) -> bool:
    """Apply one row of the matching table to a file path (directory-name rule included)."""

def prunes_directory(relative: str, pattern: str) -> bool:
    """Return True when an exclude pattern removes the directory at this relative path."""

@dataclass(frozen=True)
class Discovery:
    documents: tuple[Document, ...]   # sorted by path, as today
    skipped: int                      # as discover_with_skips() counts today
    include_hits: tuple[int, ...]     # one count per config.include entry, same order

def discover_with_stats(root: Path, config: Config) -> Discovery: ...
```

`discover()` and `discover_with_skips()` keep their signatures and results and delegate to
`discover_with_stats()`.

### Contract 3: invoker normalisation

```python
@dataclass(frozen=True)
class InvokerSelection:
    include: Optional[tuple[str, ...]]  # normalised replacement, or None when not given
    exclude: tuple[str, ...]            # normalised additions, () when not given
    unmatched_exclude: tuple[str, ...]  # literal excludes that name nothing (for the WARNING)

def selector_root_spellings(canonical_root: Path, spelled_root: Union[Path, str]) -> tuple[Path, ...]:
    """Return the scan-root spellings an absolute selector may be written under.

    The canonical root always; plus ``os.path.abspath(spelled_root)`` only when
    ``os.path.samefile()`` holds between it and the canonical root. Never ``$PWD``.
    """

def normalize_invoker_selectors(
    scan_root: Path,
    include: Optional[Sequence[str]],
    exclude: Optional[Sequence[str]],
    *,
    root_spellings: tuple[Path, ...] = (),
    backslash_is_separator: Optional[bool] = None,
) -> InvokerSelection: ...
```

- **(ADR)** The function returns the unmatched excludes instead of logging them. The CLI can then
  call it for early validation (Contract 6), and the engine logs the `WARNING` once.
- `scan_root` is the **canonical** scan root: `Path(root).resolve()` in the engine, the directory
  from `_resolve_root()` in the CLI, never the spelled root (threat model M3).
- `backslash_is_separator=None` means `os.sep == "\\"`. Passing `True` lets the Windows rules be
  tested on POSIX.
- **Root spellings (threat model A4, M8, M9).** `root_spellings` is the result of
  `selector_root_spellings()`, one helper in `/src/docsentinel/discovery.py`. Both the CLI early
  call and the engine use it, with the same canonical root and the same spelled root, so they
  always accept and refuse the same values. `()` means the canonical root alone. The helper's
  `samefile` check stats only the invoker's own root spelling, never a selector value. It does
  **not** reuse `_origin_spellings()` in `cli.py` and never reads `$PWD`. That helper serves a
  refusal boundary, where extra anchors are safe; here the spellings are an acceptance boundary.

**Pipeline (threat model A1, A2, A3, A5).** Steps run per value, in this order. Every failure is a
`ConfigError` raised before discovery. Steps 1 to 8 make **no filesystem call**.

1. **Shape** (Contract 1, in the A8 order). The message carries no value.
2. **Characters (A2, M13, M14).** A value is refused when it holds any C0/C1 control, DEL or NUL,
   or any character or sequence that `neutralize()` rewrites. That covers bidi, zero-width,
   U+2028/U+2029 and lone surrogates (non-UTF-8 argv bytes). It also covers the GitHub command
   marker `##[`, so a name holding `##[` can be selected only by a glob such as `#[#][[]...`. The
   reason is always `contains a control, format or unsupported character sequence`.
   - No Unicode normalisation of any form (NFC, NFD, NFKC, NFKD) and no case folding (`casefold`,
     `lower`) is applied to a selector anywhere. On Windows a selector is never converted to a
     bytes path.
   - Look-alike separators (U+2215, U+FF0F, U+2044, U+29F8, U+FF3C, U+FE68) are ordinary name
     characters (ruling U1).
3. **Drive, UNC and device forms (A3, M10, M11).** These are detected lexically **on every
   platform**, before the backslash rule.
   - The value is refused when `ntpath.splitdrive(value)[0]` is non-empty, or when it starts with
     two separators in any mix of `/` and `\`. This covers `C:/x`, `C:x`, UNC paths, and the
     verbatim and device namespaces. It also refuses a POSIX name such as `a:b.md`, which a glob
     like `a[:]b.md` still selects.
   - One exception: with `backslash_is_separator`, a drive followed by a separator (`X:\...` or
     `X:/...`) goes on to step 6 as an absolute value.
   - With `backslash_is_separator`, the value is also refused when it is rooted without a drive
     (`\docs` or `/docs`), when it holds a `:` after the drive (an alternate data stream), or when
     any component ends in `.` or a space.
4. **Backslash.** With `backslash_is_separator`, `\` becomes `/`. Otherwise a value holding `\` is
   refused.
5. **Parent steps (A1, M1).** A `..` component in the value is refused, for relative, absolute and
   glob values alike. The check runs on the step-4 result, **before** any `normpath()`, so
   `/repo/docs/../x` is refused just as `docs/../x` is.
6. **Absolute values (A1, M2, M4, M6), purely lexical.**
   - An absolute glob is refused (`globs must be relative`).
   - An absolute literal goes through `os.path.normpath()`. With step 5 done, that can only drop
     `.`, repeated separators and a trailing separator. It is then compared with every spelling
     through the separator-aware `_within()` semantics of `/src/docsentinel/detectors/path_boundaries.py`,
     never a bare `startswith`, so `/repo-other/x` is outside root `/repo`.
   - When several spellings match, the **longest** wins. Its prefix is removed, and a value equal
     to the root becomes `.`.
   - A value outside every spelling is refused with one message that does not depend on whether
     the outside path exists: `<key> value <v> is outside the scan root`.
   - No `realpath()`, `abspath()`, `resolve()`, `stat()`, `lstat()`, `expanduser()`,
     `expandvars()` or `glob.glob()` is ever applied to a selector value. `~/x` and `$HOME/x` are
     plain relative literals.
7. **Lexical clean-up.** A leading `./`, repeated `/` and a trailing `/` are removed. An empty
   result is refused.
8. **`.`** As an include, `.` becomes the built-in default include `("*.md", "**/*.md")`
   (`Config().include`, not the configured include). As an exclude, it is refused (`excluding the
   scan root is not allowed`).
9. **Containment (literals only, M3, M7).** Let `lexical = scan_root.joinpath(*L.split("/"))`.
   `contained_path(scan_root, lexical)` must return a path.
   - `None` means an escape through a symlinked component or the 64-hop limit. It is refused for
     include **and** exclude (`leaves the scan root through a symlink`).
10. **Existence and type (literals only, A5, M15, M16).** One `os.lstat()` of the contained path,
    which is always inside the root. The **symlink signal** is
    `os.fspath(contained) != os.fspath(lexical)` (an in-root symlinked component was expanded), or
    `S_ISLNK` from the `lstat` (a final-component symlink).
    - Include: refused when missing (`not found under the scan root`) or when the symlink signal
      holds (`symlinked paths are not inventoried`). Otherwise it must be `S_ISREG` or `S_ISDIR`;
      anything else (FIFO, socket, device) is refused (`not a regular file or directory`).
    - Exclude: missing, or the symlink signal, keeps the value and lists it in
      `unmatched_exclude`. **(ADR, O3)** A single-component literal (no `/`) is never listed,
      because the directory-name rule makes it meaningful anywhere in the tree (`--exclude build`).
11. **Duplicates.** Values are kept once, in first-occurrence order, after normalisation.

**`OSError` (A5, M17).** An `OSError` from the step-9 walk or the step-10 `lstat` becomes a
`ConfigError`: `<key> value <v>: cannot check it (<strerror>)`. A missing component
(`FileNotFoundError`, `NotADirectoryError`) is not an error; it counts as "missing" in step 10. The
message echoes the bounded relative value and the `strerror` only, never an absolute path, so no
home path reaches CI logs. This replaces the earlier "an `OSError` propagates". NUL cannot reach
`lstat`, because step 2 refuses it there.

**Failure text (A7, M21).**
- Every message that echoes a value shows it only as `safe(value, 200)`: neutralised and capped
  at 200 characters. The text is therefore already safe for library callers, and the CLI's
  `neutralize_text()` is a second, idempotent pass.
- Each message has the form `<key> value <v>: <reason>; values are relative to the scan root`,
  where `<key>` is `include` or `exclude`.
- `<reason>` is one of the fixed phrases above. Shape errors echo no value.

Globs get steps 1 to 8 and 11 only, with no filesystem access (M5). Configured `include` and
`exclude` values never reach this pipeline and never trigger filesystem access (threat model T9).

### Contract 4: precedence and merge (extends ADR 0005 Contract 1)

| Key | Layer 1 defaults | Layer 2 user settings | Layer 3 project config | Layer 4 CLI flag or `scan()` keyword |
|---|---|---|---|---|
| `include` | `("*.md", "**/*.md")` | **refused** (C6, `ConfigError`, exit `2`) | replaces the default as a whole | **replaces** the effective value |
| `exclude` | `(".git", ".venv", "node_modules")` | **refused** (C6, `ConfigError`, exit `2`) | replaces the default as a whole (unchanged: a project `exclude` drops the default entries unless it repeats them) | **appended** to the effective value |

- Effective include: the normalised invoker include if given, else the layer-3 value, else the
  default. Effective exclude: the layer-3 value (or the default) followed by the normalised invoker
  additions, duplicates removed in first-occurrence order (configured entries first). Exclude then
  wins over include (Contract 2, rule 1).
- An injected `Config` stands in for layers 1 to 3 (ADR 0005); layer 4 applies on top of it.
- `--exclude` is the single list-merging exception to ADR 0005's whole-value replacement, as C1
  and ADR 0005 Contract 1 already state.

### Contract 5: engine pipeline and observability

Inside `scan()`, in order:

1. Resolve the target and settings (unchanged).
2. Shape-check `include` and `exclude` (Contract 3 step 1) **for every target (ADR)**, so a caller
   bug never passes silently because the target happened to be a file.
3. Single-file target with either keyword given: one `WARNING`
   `--include/--exclude ignored for a single-file scan target` (no value echoed); the keywords are
   ignored (S9).
4. Otherwise `normalize_invoker_selectors(directory, include, exclude,
   root_spellings=selector_root_spellings(directory, root))`, where `directory` is the canonical
   scan root and `root` the argument as given (A4). Then `dataclasses.replace()` per Contract 4.
5. `INFO` once per scan, **counts only** (A7, M22):
   `selection: include <n> pattern(s) (<invoker|configured>), exclude <m> pattern(s) (<c> configured, <i> invoker)`,
   where `<i>` counts invoker additions not already configured. `DEBUG` per normalised pattern
   as `safe(pattern, 200)`. `WARNING` per `unmatched_exclude` value:
   `exclude pattern <safe(p, 200)> names nothing under the scan root`.
6. `discover_with_stats()`. Then:
   - a `WARNING` `include pattern <safe(p, 200)> matched no document` for each **invoker** include
     pattern with zero hits. Configured patterns with zero hits stay silent, as today.
   - **Empty inventory under invoker selection (owner ruling R1, 2026-11-19; threat model A6,
     M18).** If `include` or `exclude` was given (not `None`) and the final inventory is empty,
     `scan()` raises `ConfigError`:
     `the selection admitted no document; values are relative to the scan root`. No value is
     echoed. The CLI exits `2` through its `Scan failed:` / `Baseline generation failed:` path. This
     covers `--exclude '*'`, `--exclude docs` on a docs-only repository, and an existing directory
     include with no Markdown file when it is the only include. The per-pattern zero-hit `WARNING`s
     are logged first.
   - **Config-only selection keeps today's behaviour.** With both keywords `None`, an empty
     inventory is still exit `0`, with no new message. A single-file target never reaches this
     step.
7. Everything after discovery is unchanged and receives the merged settings.

`doctor` prints, for the configuration of the current directory, `include: <n> pattern(s)
(<source>)` and `exclude: <n> pattern(s) (<source>)`, where `<source>` is the project file name when the key is in
`ConfigSources.project_options`, else `default` (never a user-settings source, by C6). Patterns are
logged only as `safe(pattern, 200)`; error text is already bounded by Contract 3 and is printed
through `neutralize_text()` (A7).

### Contract 6: CLI surface (`/src/docsentinel/cli.py`)

- `scan` and `baseline` gain `--include PATTERN` and `--exclude PATTERN` (`action="append"`, help
  text "relative to the scan root"). Values that start with `-` need the `--include=VALUE` form.
- Each list is passed to `scan()` only when given, as `--link-root` is today.
- **(ADR)** To keep the existing rule that a user error leaves `Scan failed:` as the first stderr
  line, the CLI calls `normalize_invoker_selectors()` once before it logs `scan started` (or
  `baseline started`), discards the result, and passes the raw lists to `scan()`. The second
  normalisation in the engine is idempotent and logs the warnings once.
- **Same inputs for both calls (A4, M3, M8).** The early call passes the canonical directory from
  `_resolve_root()` and `root_spellings=selector_root_spellings(directory, args.root)`. These are
  the same values the engine computes from the same `root`, so a value the early call accepts is
  never refused after `scan started`, apart from the accepted TOCTOU residual (threat model T13).
- The R1 empty-inventory `ConfigError` can only be raised after discovery, so it follows the
  `scan started` line. That is expected: it is a result of the walk, not a malformed value.
- A `ConfigError`, `ValueError` or `OSError` keeps the existing `Scan failed:` / `Baseline
  generation failed:` paths and exit `2`.
- Selectors in a pre-commit hook's `args:` are fine: they are patterns, not a trust gate (unlike
  `--link-root`), and a repository-controlled exclude has no power the repository's config file
  lacks.

### Affected components and migration path

| Component | Change | Migration |
|---|---|---|
| Discovery, `/src/docsentinel/discovery.py` | Contract 2 matcher, relative-path pruning for literal excludes only, `Discovery` and `discover_with_stats()`, `normalize_invoker_selectors()`, `InvokerSelection` and `selector_root_spellings()` | `discover()` and `discover_with_skips()` keep their signatures |
| Engine, `/src/docsentinel/engine.py` | `include`/`exclude` keywords, Contract 5 pipeline, selection logging, the R1 empty-inventory `ConfigError` | None: keyword-only, default `None`; R1 applies only when a keyword is given |
| CLI, `/src/docsentinel/cli.py` | Flags on `scan` and `baseline`, early validation through the shared spellings helper, two `doctor` lines | Scripts that parse `doctor` see two new lines. Adding the flags makes the argparse abbreviations `--i` and `--ex` ambiguous (exit `2`); write the full option names |
| Config, `/src/docsentinel/config.py` | None. `include`/`exclude` stay in `USER_SETTINGS_REFUSED_KEYS`; no new field | None |
| Library users (`docsentinel.scan`) | Two new keywords; docstring only in `/src/docsentinel/__init__.py` | None |
| Pytest plugin, `/src/docsentinel/pytest_plugin.py` | None | None |
| Pre-commit users, `/.pre-commit-hooks.yaml` | Hook entries unchanged; `args:` may add selectors | None |
| Projects whose config holds **glob** patterns | Byte-identical results and skip counts (O1 ruled: only literals prune by relative path) | None |
| Projects whose config holds **literal** patterns | They gain meaning: `exclude = ["docs/archive"]` now removes that tree; `include = ["docs"]` now admits `docs/**/*.md` | Behaviour change, release-noted; findings in newly excluded documents disappear, findings in newly included ones appear |
| Baselines | Fingerprints unchanged | Record a baseline with the same selection as the scan lane it serves |
| `ScanResult`, reports, JSON schemas, templates | Unchanged | None |

### Consequences

- Good: one grammar and one implementation for config, CLI and library; the CLI passes through
  `scan()` keywords.
- Good: directory values work everywhere. A missing include, or an invoker selection that leaves
  the inventory empty (R1), fails closed instead of producing a clean-looking empty scan.
- Good: the security review (verdict PASS_WITH_FOLLOWUP) traced zero filesystem calls outside the
  root for every symlink shape. Absolute values are handled purely lexically.
- Bad: R1 makes the invoker and config paths differ. `--exclude '*'` exits `2`, while
  `exclude = ["*"]` in config still gives an empty exit-`0` scan, as today.
- Bad: some legitimate names cannot be written as a literal selector: names holding `:`, `##[`,
  `*`, `?` or `[`, and non-UTF-8 names. They need a glob or cannot be selected (non-UTF-8).
  Matching stays case-sensitive with no Unicode normalisation, so on a case-insensitive or
  normalising file system a literal can pass the existence check yet admit nothing. The user then
  gets the zero-hit `WARNING`, or exit `2` under R1.
- Good: a literal directory exclude prunes the walk by relative path, so the walk never enters it;
  glob excludes stay byte-identical (O1).
- Good: the configured excludes stay in force under `--include`, so `.venv` and `node_modules` are
  never scanned by accident.
- Bad: a value typed relative to a subdirectory (`cd docs && docsentinel scan .. --include user`)
  does not match; it is reported (exit `2` for a literal include, `WARNING` for an exclude or a
  zero-hit glob) rather than guessed.
- Bad: there is no way to remove a configured exclude from the command line (non-goal); a user
  must edit the config.
- Bad: the selection is not recorded in `ScanResult` or the report, so a reader cannot tell a
  narrowed run from a full one; the `INFO` selection line is the only trace. Corpus rules (DS114,
  DS118, DS202, DS203, DS301) and DS112 depend on the selection.
- Bad: literal config values change meaning (release-noted). A literal include of a directory
  admits only `.md` files, which differs from a glob include.
- Bad: the normaliser and the containment walk add an attack surface. Task 02
  ([threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md)) reviewed it
  before code and set merge-gate conditions.
- Neutral: include narrows the inventory but not the walk, so `--include` does not make the walk
  faster.

## Pros and Cons of the Options

### (A1) Scan-root base (chosen)

- Good: one grammar; config and CLI values are interchangeable; matches C5 and D8.
- Good: when the scan root is the current directory (the common case and the pre-commit case) it
  is the same as A2.
- Bad: from a subdirectory a CWD-relative value does not match; it is reported, not guessed.

### (A2) Current-directory base

- Good: familiar from shell tools and tab completion.
- Bad: the same value means different things in config and on the CLI; copying between them
  breaks.
- Bad: values could name paths outside the scan root, which then need a second refusal path.

### (A3) Mixed base

- Good: tab completion works for paths while globs stay root-relative.
- Bad: two bases in one flag, decided by whether the value has a glob character; `docs/x.md` and
  `docs/x*.md` would have different bases. Hard to explain and to test.

### (B1) Replace both

- Good: simplest and consistent with ADR 0005's whole-value rule.
- Bad: any `--exclude` silently drops `.git`, `.venv` and `node_modules`, so a narrowing flag
  widens the scan into dependencies.

### (B2) Append both

- Good: no configured value is ever lost.
- Bad: `--include docs/user` cannot narrow a scan, because the default `**/*.md` still admits
  every document.

### (B3) Include replaces, exclude appends (chosen)

- Good: both flags do what the user means: include narrows, exclude removes more.
- Bad: the two flags merge differently, which must be documented; it is the one exception to the
  whole-value rule.

### (C1) Literal means file or directory, everywhere (chosen)

- Good: today such values match nothing, so no working configuration changes meaning.
- Good: one meaning in config and on the CLI.
- Bad: a literal config value that matched nothing now matters, which is a (release-noted)
  behaviour change.

### (C2) Exact-path match only

- Good: no behaviour change at all.
- Bad: the silent no-match stays; users must know to write `docs/archive/**`.

### (C3) Directory semantics for invoker values only

- Good: config files keep exact behaviour.
- Bad: two grammars, which breaks the main driver; the silent no-match in config stays.

## Open points for the owner

State:
- O1 and R1 are ruled by the owner.
- O2, O6 and U1 are ruled by the Task 02 Security Auditor.
- O8 is superseded by R1.
- O3 to O5 and O7 are provisional decisions. Task 02 endorsed or did not challenge them, and they
  stand unless the owner rules otherwise.

Amendments A1 to A8 of the
[threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md#required-spec-amendments-before-task-03-starts-unless-noted)
are folded in: A1 to A3, A5 and A8 into Contracts 1 and 3, A4 into Contracts 3, 5 and 6, A6 into
Contract 5 (as R1), and A7 into Contracts 1, 3 and 5.

| # | Point | Decided here | State |
|---|---|---|---|
| O1 | Should a glob exclude also prune a directory by its relative path (`fnmatchcase(D, G)`)? For globs such as `docs/v?` or `**/archive` that would remove documents scanned today. | **Ruled by the owner, 2026-11-18: literals only.** Only a literal exclude prunes by relative path; glob excludes keep today's behaviour exactly (Contract 2), so the story acceptance "unchanged for glob patterns" and Task 03 "glob behaviour byte-identical" stand. No glob behaviour-change release note. | Ruled |
| O2 | Absolute values are made relative lexically against the root spellings, never by `realpath()` of the value's parent | Lexical only (Contract 3 steps 5 and 6) | **Ruled by Task 02, 2026-11-18: lexical only, confirmed** ([threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md) A1, A4). Task 03 step 4's `realpath()` step is struck: an absolute value is never `realpath`-ed, `stat`-ed, `abspath`-ed or resolved before it is lexically inside the root. A `..` component is refused on the raw value before `normpath()`; containment is separator-aware; the longest matching spelling wins; spellings are the canonical root plus `abspath(spelled root)` only when `samefile` with it, from one helper shared by the CLI and the engine, never `$PWD` |
| O3 | A single-component literal exclude that names nothing at the root gives no `WARNING` | No warning (Contract 3 step 10) | **Confirmed by the owner, 2026-11-20.** Was provisional: S8 says every missing literal exclude warns; that would warn for `--exclude build`, which still prunes every `build` directory by name |
| O4 | Shape checks run even for a single-file target | Yes (Contract 5 step 2) | **Confirmed by the owner, 2026-11-20.** Was provisional: S9 says the flags are ignored; Task 04 originally skipped normalisation entirely for a file target |
| O5 | A bare `str` keyword is a `ConfigError` | Yes (Contract 1) | **Confirmed by the owner, 2026-11-20.** Was provisional: Not in the story; without it `scan(include="docs")` silently means four patterns |
| O6 | A literal include through an in-root symlinked component exits `2` | Yes (Contract 3 steps 9 and 10) | **Ruled by Task 02, 2026-11-18: confirmed** ([threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md) A5). Signal: the `contained_path()` result differs from the lexical join (sound once `..` is refused); a final-component symlink counts too. A literal exclude reached that way is kept and listed in `unmatched_exclude` (O3 exception stands); a `None` walk (escape or hop limit) exits `2` for include and exclude. A literal include must also be a regular file or directory |
| O7 | `--include .` means the built-in default include, not the configured include | As the story table says | **Confirmed by the owner, 2026-11-20.** Was provisional: A user may expect "everything the config includes" |
| O8 | An existing directory with no Markdown file is a zero-hit `WARNING`, not exit `2`, even when it leaves the inventory empty | Per-pattern zero-hit `WARNING` kept; the empty-inventory case is now R1 | **Superseded by R1** (challenged by Task 02, threat model T8) |
| R1 | When invoker selectors are given and the final inventory is empty, is that exit `2` or only a `WARNING`? | `ConfigError`, exit `2` (Contract 5 step 6). Config-only selection keeps today's exit `0` | **Ruled by the owner, 2026-11-19: exit `2`** ([threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md) T8, A6) |
| U1 | Are the look-alike separators U+2215 and U+FF0F (and U+2044, U+29F8, U+FF3C, U+FE68) separators? | Ordinary name characters (Contract 3 step 2) | **Ruled by Task 02, 2026-11-18: ordinary name characters, no refusal** ([threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md) A2), provided no Unicode normalisation (NFKC/NFKD would map U+FF0F to `/`), case folding or bytes-path conversion is applied to a selector anywhere |

## Validation / Rollout

- `python scripts/check_doc_links.py docs/adr docs/roadmap` reports 0 problems.
- The acceptance criteria of
  [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md#acceptance-criteria).
- The Task 02 verdict is PASS_WITH_FOLLOWUP (2026-11-18), O2, O6 and U1 are ruled, A1 to A8 are
  folded in, and the owner ruled O1 and R1. The ADR moves to `Accepted` once the owner confirms
  O3 to O5 and O7.
- Merge gate: the threat model's BLOCK conditions apply to every Story 02.0 change. Among them:
  any filesystem call on a selector value before it is lexically inside the canonical root; a glob
  reaching the filesystem; Unicode normalisation or case folding of a selector; an accepted parent
  step; a literal include accepted through a symlink; an unbounded echo; config values touching the
  filesystem.
- Product backlog, not this story: F1 (a total-character budget across selector values) and F2
  (selection counts in the report's optional run metadata).

Follow-up tasks:

| Task | Owner | Deliverable |
|---|---|---|
| [02](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/02-threat-review-invoker-selectors.md) | Security Auditor | Done 2026-11-18: [threat model](/docs/security/threat-model-0009-invoker-selectors-2026-11-18.md), PASS_WITH_FOLLOWUP |
| [03](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/03-selector-normalisation-and-matching.md) | Python Expert | Contract 2 and Contract 3 in discovery, `InvokerSelection` return shape |
| [04](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/04-cli-and-library-surface.md) | Python Expert | Contracts 1, 4, 5 and 6 |
| [05](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/05-tests.md) | Testing Expert | Story test plan plus one test per row of Contract 1, Contract 2 and Contract 3, and per open point as ruled |
| [06](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/06-docs-and-release-notes.md) | Docs Writer | Story "Docs to update", including the literal behaviour change (globs unchanged, O1) and the `[` escaping note |

**Diagram follow-up for `diagram-creator`.** Run it after Tasks 03 and 04 land, because
`/docs/diagrams/` shows the as-built package. No discovery or engine pipeline diagram exists yet,
and `/docs/architecture/README.md` has no Mermaid diagram (Task 06 updates its discovery prose):

- `/docs/diagrams/component/overview/component-overview.puml`: extend the `discovery.py` label with
  `discover_with_stats, normalize_invoker_selectors`; label the engine-to-discovery edge
  `normalise invoker selectors, discover (literal exclude prunes by path)`; mention `--include/--exclude` on the
  CLI. Re-render the `.svg` and `.png`.
- `/docs/diagrams/sequence/config-layered-load/config-layered-load.puml`: in the "Layer 4: CLI
  flags" section, show `scan(root, config=settings, link_root=..., include=..., exclude=...)` and a
  note that the engine replaces `include` and appends `exclude` on top of the (possibly injected)
  `Config`.
- New: `sequence/scan-selection`. Participants: CLI or library, `engine.scan`,
  `selector_root_spellings`, `normalize_invoker_selectors`, `contained_path`, `discover_with_stats`.
  It shows the CLI early call and the engine call sharing one spellings result, the shape check,
  the single-file branch, normalisation (characters, drive/UNC, parent steps, lexical absolute
  handling, containment, one `lstat`), the merge, the walk with name pruning and literal
  relative-path pruning, the zero-hit and unmatched-exclude warnings, and the R1 empty-inventory
  `ConfigError` branch. Add it to
  `/docs/diagrams/README.md`.
- `/docs/diagrams/component/detectors/component-detectors.puml` and
  `/docs/diagrams/component/reporting/component-reporting.puml`: no change.

Diagram impact: component-overview (discovery label, engine-to-discovery edge), config-layered-load
(layer 4 shows `include=`/`exclude=`), new `sequence/scan-selection` (including the R1 branch); detectors and reporting
unchanged; run `diagram-creator` after Tasks 03 and 04 land.

## Links

- **Roadmap story/task:**
  [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md),
  [Task 01](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/01-adr-selection-semantics.md),
  [Milestone 0009 plan, shared contracts](/docs/roadmap/0009-improvements/plan.md#shared-contracts-authoritative)
- **Supporting specs:** [configuration reference](/docs/user/reference/configuration.md),
  [logging](/docs/specs/logging.md), [architecture](/docs/architecture/README.md),
  [coding standard](/docs/dev/python_coding_standard.md)
- **Related ADRs:**
  [0005 - Layered Configuration: User Settings JSON under Project TOML](/docs/adr/0005-layered-configuration-user-settings-json.md)
  (precedence chain and the C6 refused keys this ADR builds on)
- **Diagrams:** [diagram index](/docs/diagrams/README.md); the follow-up is above
