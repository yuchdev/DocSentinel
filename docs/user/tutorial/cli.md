# Using DocSentinel as an Executable (CLI)

The `docsentinel` command-line tool provides fast, deterministic documentation linting and static analysis for local development and CI/CD pipelines.

---

## Command Overview

DocSentinel provides the following CLI subcommands:

| Command                | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `docsentinel scan`     | Analyze Markdown documents and report findings                          |
| `docsentinel baseline` | Capture current findings into a baseline file to suppress legacy issues |
| `docsentinel init`     | Create a starter `docsentinel.toml` (or, with `--user`, your user settings file) |
| `docsentinel rules`    | List all available and active rules per profile                         |
| `docsentinel doctor`   | Diagnose environment readiness and optional dependency installations    |
| `docsentinel extract-facts` | Offline list of the claims `DS302` would send to a fact-check service |

---

## Scanning Documents (`docsentinel scan`)

The `scan` command is the primary entry point for documentation validation.

### Basic Invocations

```bash
# Scan the current repository with default settings
docsentinel scan

# Scan a specific directory
docsentinel scan docs/

# Scan a single Markdown file
docsentinel scan docs/README.md
```

### Analysis Profiles

DocSentinel supports three distinct profiles via `--profile`:

#### 1. Fast Profile (`--profile fast`) - Default

Runs structural and reference rules. All rules use only the Python standard
library. Eighteen rules are registered (`DS100` is emitted by the engine itself and is not counted below); twelve are evaluated by default (five are
opt-in policies that are silent until their option is set):

Every rule, with its severity, activation and options, is listed in the
[rules table](../reference/rules.md).

```bash
docsentinel scan --profile fast
```

**Opt-in rules.** `DS103`, `DS110`, `DS112`, `DS115`, and `DS118` are inert until you set
their enabling option. The scan notice reports exactly which ones are off:

```
12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS103 (set reference_scope = "strict"), DS110 (set require_fence_languages), DS112 (set navigation_indexes), DS115 (set deprecated_references_file), DS118 (set documentation_naming).
```

To enable an opt-in rule, set its option in `docsentinel.toml` (see
[Configuration Reference](../reference/configuration.md)):

```toml
# Enable DS103: also check path-like inline code spans (see below).
reference_scope = "strict"

# Enable DS110: require a language label on every non-empty code fence.
require_fence_languages = true

# Enable DS118: enforce kebab-case file and directory names.
documentation_naming = "kebab"
```

#### 2. Standard Profile (`--profile standard`)
Runs statistical corpus detectors and docstring synchronization:
- `DS201`: Text readability complexity exceeds threshold
- `DS202`: Duplicate text across documents (cosine similarity check)
- `DS203`: Low information content (short/boilerplate files)
- `DS204`: Docstring parameter/return mismatch against Python code signatures

```bash
docsentinel scan --profile standard
```

#### 3. Deep Profile (`--profile deep`)
Runs deep heuristic NLP analysis (`DS301` fact-contradiction candidate detector). Deep checks are heuristic, compute-intensive, and require explicit confirmation:

```bash
docsentinel scan --profile deep --i-understand-deep-is-heuristic
# or via environment variable
DOCSENTINEL_DEEP_CONFIRM=1 docsentinel scan --profile deep
```

##### External fact-checking (`DS302`)

> **Warning: this sends text to a third party.** `DS302` sends claim sentences taken from your
> documents to an external fact-checking service. It is off by default. Its verdicts are advisory,
> heuristic third-party output, not ground truth: a finding is a prompt to review a sentence, and it
> never fails a scan.

`DS302` runs only when you give **two independent opt-ins** on top of the deep confirmation:

1. `--use-external-api` on `scan` or `baseline`, or `DOCSENTINEL_USE_EXTERNAL_API=1` (exactly `1`).
2. The backend's API key in `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`, for the `lenz` backend
   `DOCSENTINEL_FACTCHECK_LENZ_API_KEY`.

Neither is a configuration key: a project or user settings file that names `use_external_api` is
rejected. Preview what would be sent first with
[`extract-facts`](#previewing-what-ds302-would-send-docsentinel-extract-facts).

```bash
# <your key here> is a placeholder: use your own key, from your own shell, for this one command
DOCSENTINEL_FACTCHECK_LENZ_API_KEY=<your key here> \
  docsentinel scan docs --profile deep --i-understand-deep-is-heuristic --use-external-api
```

Tune it with the `fact_check_*` options in the
[configuration reference](../reference/configuration.md#external-fact-checking-ds302). Each finding has
type `unverified claim` and a `value` such as `false (confidence 0.87): <claim>`.

While either opt-in is missing, a confirmed deep scan logs one WARNING, lists the reason under
`Pending:` (and in `pending` in JSON), and does not count `DS302` as evaluated:

```text
Pending: DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set DOCSENTINEL_FACTCHECK_LENZ_API_KEY
```

`docsentinel doctor` shows the same state as `fact-check gate: on (backend: lenz)`,
`fact-check gate: off (<reasons>)` or `fact-check gate: unknown (configuration error)`.

**Safe invocation.** Never put `--use-external-api` in a pre-commit `args:` list or a hook definition,
never use it in a `pull_request_target` workflow, and never export the key variable (or
`DOCSENTINEL_USE_EXTERNAL_API`) for a whole CI job, shell profile, `.envrc` or `.env`: anything that can
change those files or that job could then make a scan send text out. Set them for one command, as above.

---

## Filtering Rules: `--select` and `--ignore`

You can restrict or exclude specific rules using comma-separated rule codes or prefixes:

```bash
# Only run rule DS101 and DS103
docsentinel scan --select DS101,DS103

# Run all DS2xx standard rules
docsentinel scan --profile standard --select DS2

# Exclude comment checks (DS102)
docsentinel scan --ignore DS102
```

---

## Output Formats: `--format`

Every report is rendered from a template. `--format NAME` selects one by name. Five templates ship
with DocSentinel. The [Report Formats](report.md) guide shows each one in full and explains how to
migrate scripts written for the old output.

### 1. Human-Readable Text (`--format text`) - Default

Prints the scan summary, then each document that has problems with its findings indented directly
under it:

```bash
docsentinel scan --format text
```

```text
Documents: 2 (1 with problems)
...
README.md (74 bytes)
  error   DS101 dangling link, line 3, col 15: docs/nope.md
Blocking findings: 1
  error   DS101 dangling link: README.md, line 3, col 15: docs/nope.md
```

Clean documents are hidden. Add `--show-clean-documents` (or set
`report_show_clean_documents = true`) to list them too.

### 2. Structured JSON (`--format json`)

Outputs a JSON object that follows **schema 2**: a summary, the rule status, and one record per
document with its problems inside it. Clean documents are included with an empty `problems` list:

```bash
docsentinel scan --format json
```

Abridged JSON payload:
```json
{
  "schema_version": 2,
  "profile": "fast",
  "run": { "model": null, "notice": "12 fast rule(s) evaluated; ...", "advisory": null },
  "summary": { "documents": 2, "documents_with_problems": 1, "findings": 1,
               "by_severity": { "error": 1 }, "by_rule": { "DS101": 1 } },
  "rules": { "enabled": ["DS101", "DS102", "..."], "evaluated": 12, "opt_in_off": [ { "code": "DS110", "option": "require_fence_languages" } ] },
  "documents": [
    {
      "path": "README.md",
      "bytes": 74,
      "domain": "docs",
      "problems": [
        { "rule": "DS101", "type": "dangling link", "message": "dangling link -> docs/nope.md",
          "value": "docs/nope.md", "severity": "error", "line": 3, "column": 15,
          "fault_class": "dangling_reference", "tier": "deterministic", "outcome": "rejected" }
      ]
    },
    { "path": "docs/setup.md", "bytes": 15, "domain": "docs", "problems": [] }
  ],
  "pending": []
}
```

`rules.enabled` lists every rule selected in the active profile (selection is orthogonal to whether
an opt-in policy fires). `rules.opt_in_off` separately names the opt-in rules that are selected but
currently silent.

### 3. Legacy JSON (`--format json-v1`)

Outputs the schema 1 JSON that `--format json` printed before this release, unchanged: a flat
`findings` list in which each finding carries its own `path`. Use it for consumers that have not
moved to schema 2:

```bash
docsentinel scan --format json-v1
```

### 4. Document records only (`--format json-documents`)

Outputs only the `documents` array of schema 2, as a bare JSON list.

### 5. GitHub Actions Annotations (`--format github`)

Formats findings as GitHub Actions workflow commands (`::error` and `::warning`). Each one carries
`title=` with the rule code, and `col=` when the column is known:

```bash
docsentinel scan --format github
```

```text
::error file=README.md,line=3,col=15,title=DS101::dangling link -> docs/nope.md
```

### Custom templates: `--template` and `report_templates_dir`

- `--template PATH` renders with a template file you supply. It wins over `--format`.
- `report_templates_dir` in the configuration names a directory under the scan root. Each
  `NAME.json` in it can be selected with `--format NAME`. Packaged names always win.

An unknown format name or an invalid template prints `Scan failed: ...` on stderr and exits `2`.
`docsentinel doctor` lists the templates you can select. See
[Report Formats](report.md#custom-templates) and the
[report template format](../../specs/report-template-format.md).

### Reference scope: `--reference-scope`

By default a scan checks what a reader or an agent follows: Markdown links and `@`-document
mentions. `DS103`, which checks path-like inline code spans, is **opt-in** since 1.3.0 and runs
only in the strict scope. `--reference-scope {links,strict}` (also on `baseline`) replaces the
`reference_scope` key for one run; the INFO start line shows the effective value.

```bash
docsentinel scan docs --reference-scope strict
```

**Migration.** To keep the pre-1.3.0 behaviour set `reference_scope = "strict"` in the
configuration or pass `--reference-scope strict`. Baseline entries for `DS103` stop matching under
the default scope; re-record the baseline to drop them. `DS124` is new and reports warnings, which
block only under `--strict`; set `ignore = ["DS124"]` to switch it off. See
[Reference scope options](../reference/configuration.md#reference-scope-options-ds103-ds124).

#### Document mentions (DS124)

`DS124` checks `@`-mentions of documents, the way agent prompts name files: `@docs/README.md` in
prose, or a whole inline code span such as `` `@docs/README.md` ``. A mention is an `@` at the start
of a line or after whitespace, an opening parenthesis or bracket, or a quote, followed by a path of
letters, digits and `._~+-/` whose last component has an extension containing a letter. A
backslash-escaped space is decoded to a space; no other decoding applies. Only extensions
listed in `at_reference_extensions` are checked.

Each mention resolves in two steps and is reported only when both fail:

1. relative to the document that contains it;
2. relative to the link root (the repository root in a git checkout).

A mention whose fallback lands outside the link root (a `..` above it, or a symlink out of it)
produces no finding at all. A mention that leaves the scan root is a `DS116` error, not a `DS124`
warning, and only `DS116` reports it, so ignoring `DS116` or setting `root_escape_policy = "off"`
silences escaping mentions. `@~/...` and `@/...` mentions are recognised but never resolved.
DS124 never opens a target.

Step 2 uses the link root for every relative mention, so under the default `link_root = "auto"`
untrusted content unpacked inside another checkout can learn which files exist in that checkout.
Use `link_root = "."` for such content; see the Trust paragraph in
[`link_root`](../reference/configuration.md#link_root).

Escape hatches: put a backslash before the `@`, or show the mention inside a fenced code block:

```text
\@docs/example.md      not a mention (escaped)
@docs/example.md       a mention, but not checked inside a fence
```

E-mail addresses, handles such as `@octocat` and version strings are not mentions.

### Site-root links: `--link-root`

A link starting with `/` resolves against the link root, by default the
nearest directory holding `.git` (see `link_root` in the configuration
reference). `--link-root PATH` overrides it for one run, for example when the
docs are not in a git repository. PATH is absolute or relative to the current
directory and must be the scan root or one of its ancestors (never the
filesystem root). The flag is trusted invoker input and wins over the
configuration; a bad value exits with code `2`. A `link_root` in a
configuration file is bounded instead (the nearest `.git`, or an ancestor
holding a project marker).

Because the flag is trusted, never put `--link-root` in pre-commit `args:` or in
a `pull_request_target` workflow, where a contributor could choose it.

```bash
docsentinel scan docs --link-root .
```

### Selecting files: --include and --exclude

`--include PATTERN` and `--exclude PATTERN` narrow or widen one scan without editing the
configuration. Both repeat, and both work on `scan` and `baseline`. A value is a glob, a file or a
directory, written relative to the **scan root** (the directory you pass to `scan`, not your
current directory), or as an absolute path inside the scan root.

```bash
# Scan only the user guides (a directory: its Markdown files, at any depth)
docsentinel scan . --include docs/user

# Scan two places
docsentinel scan . --include docs/user --include README.md

# Leave out a directory and every draft, on top of the configured excludes
docsentinel scan . --exclude docs/archive --exclude "**/*.draft.md"

# A value that starts with a hyphen needs the = form
docsentinel scan . --include=-notes.md

# The same selection when recording a baseline
docsentinel baseline . --exclude docs/archive --output .docsentinel-baseline.json
```

How the flags combine with the configuration:

- `--include` **replaces** the configured `include` (default `*.md` and `**/*.md`). `--include .`
  restores that default.
- `--exclude` is **appended** to the configured `exclude` (by default `.git`, `.venv` and
  `node_modules`), so those stay excluded. Duplicates are kept once.
- **Exclude wins** over include for a document matched by both.
- A glob (a value with `*`, `?` or `[`) matches as before. Any other value is a literal: this file,
  or this directory and everything below it. A directory include admits only `.md` files. A file
  name containing `*`, `?` or `[` cannot be a literal; use a glob such as `notes[[]1].md`.
  The full rules are in the [configuration reference](../reference/configuration.md#selection-options-include-and-exclude).
- Matching is case-sensitive and does not normalise Unicode, even on a case-insensitive file
  system. A look-alike slash (U+2215, U+FF0F) is an ordinary character.
- When the scan target is a single file, both flags are ignored with a `WARNING`; their shape is
  still checked.

Values are checked before the scan starts, and a bad one prints `Scan failed:` and exits `2`.
Refused values:

- a `..` step, or an absolute path outside the scan root (the message is the same whether or not
  the path exists);
- a drive, UNC or device form, and on POSIX a backslash;
- control or format characters, and the text `##[`;
- `--exclude .`, because excluding the whole scan root is refused;
- an absolute glob (an absolute value under a root path that itself contains `*`, `?` or `[` is
  read as a glob and refused; use a relative value);
- an include that names nothing (`not found under the scan root`), is not a regular file or
  directory, or goes through a symlinked component;
- an include or exclude that leaves the scan root through a symlink;
- more than 256 values per flag, or a value over 1,024 characters.

An absolute value must be spelled with the real path, or the scan root exactly as you typed it. A
`$PWD` spelling that goes through a symlink is not accepted; use a relative value. An exclude that
has a path component too long for the file system exits `2` with `cannot check it (File name too
long)`.

An invoker selection that admits no document at all exits `2` with `the selection admitted no
document; values are relative to the scan root`, so a typo never produces an empty, clean scan.
`baseline` does the same, through `Baseline generation failed:`.
A selection that comes only from the configuration and is empty still exits `0`. When the scan
root itself does not exist, a literal selector reports `not found under the scan root`.

Each scan logs the effective selection at `INFO`, with counts only, and each pattern at `DEBUG`
(`-v`):

```text
docsentinel: selection: include 1 pattern(s) (invoker), exclude 4 pattern(s) (3 configured, 1 invoker)
```

Two `WARNING` lines flag a likely mistake: `include pattern <p> matched no document` for an
`--include` value that admitted nothing, and `exclude pattern <p> names nothing under the scan
root` for a multi-component literal `--exclude` that does not exist. `docsentinel doctor` prints
`include: <n> pattern(s) (<source>)` and `exclude: ...` lines for the configuration in the current
directory, where the source is the project file name or `default` (never the user settings file).

Notes:

- The new flags make the argparse abbreviations `--i` and `--ex` ambiguous (they also fit
  `--i-understand-deep-is-heuristic` and `--extension`), so argparse rejects them with exit `2`.
  Write the full flag names.
- Corpus-level rules (`DS114`, `DS118`, `DS202`, `DS203`, `DS301`) see only the selected documents,
  and a baseline recorded with one selection looks stale under another; pass the same flags to
  `baseline` as to the scan it serves.
- Links into an excluded document still resolve (`DS101`, `DS113`, `DS116` check the file system).
- The flags select Markdown documents only. `DS204` (standard profile) finds Python sources through
  its own `docsig_paths` and glob-only `exclude` matching, so a literal directory exclude such as
  `--exclude src/legacy` does not remove those Python files from the `DS204` check.
- A file whose name is not valid UTF-8 cannot be selected as a literal; match it with a glob.
- The flags are patterns, not a trust gate like `--link-root`, but they have the same power as the
  `include` and `exclude` keys of the repository's own configuration. Do not feed them from an
  untrusted source, such as a contributor-chosen workflow input.

---

## Strict Mode and Exit Codes

### Exit Code Rules

| Exit Code | Meaning                                                                                |
|-----------|----------------------------------------------------------------------------------------|
| `0`       | Clean run (no error-level findings, or deep advisory findings)                         |
| `1`       | One or more error-level findings detected (or any warnings when `--strict` is enabled) |
| `2`       | Configuration error, invalid CLI flags, or filesystem scan failure                     |

### Strict Mode (`--strict`)

By default, warning-level findings do not fail the build (exit code `0`). Use `--strict` to elevate all findings to build-failing conditions (exit code `1`):

```bash
docsentinel scan --strict
```

*Note: Deep profile findings (`DS301`) are heuristic candidates and advisory-only; they always return exit code `0` to avoid blocking CI pipelines.*

---

## Logging: `-v`, `-q` and the per-run log file

Progress messages go to stderr, never to stdout, so `docsentinel scan --format json | jq` keeps
working. By default you see `INFO` lines: what started, where the report went, and the totals.
`-v`/`--verbose` adds `DEBUG` detail and `-q`/`--quiet` shows only warnings and errors. Both
flags work before or after the command, for example `docsentinel -q scan` and `docsentinel scan -q`.

```text
docsentinel: scan started: root=docs, profile=fast, format=text, output=reports/docs.txt, reference_scope=links
docsentinel: config: user settings loaded (profile, reference_scope), project docsentinel.toml
docsentinel: discovered 301 documents under /repo/docs (0 skipped: symlinks/excluded, 0 unreadable)
docsentinel: profile=fast: 17 rules selected, 12 evaluated; opt-in off: DS103 (reference_scope = "strict"), DS110 (require_fence_languages), DS112 (navigation_indexes), DS115 (deprecated_references_file), DS118 (documentation_naming)
docsentinel: report written to /repo/reports/docs.txt (text, 55 lines)
docsentinel: scan finished in 29.45s: 301 documents, 30 findings (errors 5, warnings 25); by rule DS101=1, DS102=14, DS105=1, DS106=3, DS116=4, DS117=7; blocking 5; exit code 1
docsentinel: details in log file: /home/you/.local/logs/docsentinel/docsentinel-20261116-202253-5802.log
```

Every run also writes a `DEBUG` log file named `docsentinel-<YYYYmmdd-HHMMSS>-<pid>.log` to
`~/.local/logs/docsentinel/`. The directory is created with mode `0o700` and the file with
mode `0o600`. When a run exits `1` or `2`, the last stderr line names its log file. The newest
20 log files are kept and older `docsentinel-*.log` files in that directory are deleted. If the
file cannot be created, the run continues and logs to stderr only.

An existing log directory must be a real directory (not a symlink) owned by you and not writable
by group or others; otherwise no file is written, a `WARNING` says why and the run logs to stderr
only. Do not point `DOCSENTINEL_LOG_DIR` into a checked-out repository or a shared directory. Log
files are created exclusively (an existing file or symlink is never opened) and rotation only
deletes your own regular `docsentinel-*.log` files older than 60 seconds.

The `config:` line names where the settings came from: the state of the user layer (`loaded`,
`missing`, `off` or `no-home`), the names, never the values, of the options the user file set (the
first 20, then `and N more`), and the name of the project file or `none`. The home directory is
never shown in full.

A document that cannot be read or is not valid UTF-8 is reported as a `WARNING` and as a `DS100`
error finding. Stderr names the first 20 such documents and then one `skipped N more unreadable
documents (see log file)` line; the log file lists them all.

| Environment variable | Effect |
|---|---|
| `DOCSENTINEL_LOG_DIR` | Use this directory instead of `~/.local/logs/docsentinel/`. |
| `DOCSENTINEL_LOG_KEEP` | How many log files to keep (default `20`, minimum `1`). |
| `DOCSENTINEL_LOG_LEVEL` | Stderr level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`); overrides `-v`/`-q`. |

The library (`from docsentinel import scan`) never prints log output: it only attaches a
`NullHandler` to the `docsentinel` logger, so your application decides. See
[the logging spec](../../specs/logging.md) for levels and what may be logged.

---

## Baselines: Suppressing Existing Debt (`docsentinel baseline`)

When introducing DocSentinel to an existing project with legacy issues:

### 1. Generate the Baseline

```bash
# Capture fast profile findings
docsentinel baseline --output .docsentinel-baseline.json

# Capture standard profile findings
docsentinel baseline --profile standard --output .docsentinel-standard-baseline.json
```

### 2. Run Scans with Baseline Filtering

```bash
docsentinel scan --baseline .docsentinel-baseline.json
```

All existing issues recorded in `.docsentinel-baseline.json` are suppressed. The scan will only report and fail on new issues introduced in subsequent commits.

---

## Previewing what DS302 would send (`docsentinel extract-facts`)

`extract-facts` lists the verifiable claims that `DS302` would send to a fact-check service. It is
offline: it makes no network call, loads no backend, reads no API key and needs no `--use-external-api`.
It is not an LLM and verifies nothing. Use it as the preview to review before you pass
`--use-external-api`. It needs the deep extras (`docsentinel[deep]`) and the spaCy model, but not
`deep_confirm`.

```bash
docsentinel extract-facts docs
docsentinel extract-facts docs --format facts-json -o /tmp/facts.json
```

| Option | Effect |
|--------|--------|
| `ROOT` | Directory or file to read (default `.`). |
| `--include`, `--exclude` | Document selection, as for `scan`. |
| `--config FILE.json`, `--no-user-settings` | Configuration sources, as for `scan`. |
| `--format NAME` | `facts-text` (default), `facts-json`, or a facts template in `report_templates_dir`. |
| `--template PATH` | Your own facts template; wins over `--format`. |
| `-o`, `--output PATH` | Write the output to a file instead of standard output. |
| `--min-salience FLOAT` | Override `fact_check_min_salience` for this run. |
| `--max-per-document INT` | Override `fact_check_max_claims_per_document` for this run. |
| `--max-total INT` | Override `fact_check_max_claims_total` for this run. |
| `--weights N,E,D` | Exploration only: numeric, entity and distinctiveness weights summing to 1. |
| `--dedup-threshold FLOAT` | Exploration only: near-duplicate threshold in (0, 1]. |
| `--all` | Also list claims that were not selected, with their disposition. |
| `-v`, `-q` | Logging verbosity. |

With no overrides, the default output is the set `DS302` would send for the same root, configuration,
selection and spaCy model. The `matches_ds302` field of `facts-json` (and the `Matches the DS302
selection` line of `facts-text`) says `no` when an override or exploration setting changed it.
`--weights` and `--dedup-threshold` never change `DS302` and are not configuration keys.

`--all` lists every extracted claim, each with a disposition: `selected`, `duplicate`, `below_floor`,
`document_cap` or `total_cap`; `rank` then counts the listed entries.

The output contains text from your documents. Treat a `-o` file like the documents: keep it out of the
scan root and out of version control. Exit codes: `0` on success (even with no facts) and `2` for a
configuration, selection or readiness failure (including missing deep extras); the command never exits
`1`. `docsentinel scan --format facts-text` (or `facts-json`) exits `2` and points here.

Example (`facts-text`, synthetic sentence; the exact numbers depend on your documents):

```text
docs/towers.md
  #1 score 0.81 (numeric 0.90, entity 0.60, distinct 0.80) cluster 1/1 paragraph 0: The Example Tower was completed in 1889 and stands 330 metres tall.
Facts: 1 selected, 1 listed, from 3 claims in 2 document(s) (0 unreadable skipped)
Matches the DS302 selection for this configuration: yes
Heuristic, offline claim extraction; no network call was made and nothing was verified. ...
```

Example (`facts-json`, schema `docsentinel-facts` 1, abridged):

```json
{
  "schema": "docsentinel-facts",
  "schema_version": 1,
  "matches_ds302": true,
  "summary": {"documents": 2, "claims_extracted": 3, "facts_selected": 1, "facts_listed": 1},
  "facts": [
    {
      "rank": 1,
      "path": "docs/towers.md",
      "text": "The Example Tower was completed in 1889 and stands 330 metres tall.",
      "score": 0.81,
      "disposition": "selected"
    }
  ]
}
```

---

## Environment Diagnostics (`docsentinel doctor`)

Verify which profiles, dependencies, and language models are ready on your machine:

```bash
docsentinel doctor
```

Example output:
```text
Inventory: available
standard profile: available
deep profile: not ready
  ✓ deep libraries installed (spacy, textacy)
  ✗ deep model missing (en_core_web_sm): python -m spacy download en_core_web_sm
fast rules: 18 registered (5 opt-in, off unless configured: DS103, DS110, DS112, DS115, DS118)
standard rules: 4 registered
deep rules: 2 registered
fact-check gate: off (pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set DOCSENTINEL_FACTCHECK_LENZ_API_KEY)
fact templates (packaged): facts-json, facts-text
user settings: ~/.local/share/docsentinel/settings.json (loaded, 2 options)
project config: docsentinel.toml (4 options)
reference scope: links (DS103 off)
```

The `user settings` line shows the user settings file in tilde form with its state and option count
(`loaded`, `missing`, `off (DOCSENTINEL_SETTINGS=off)`, `off (--no-user-settings)` or `none (home
directory unknown)`), and the `project config` line the project file name with its option count or
`none`. Counts only, never values. A configuration error in the current directory (a refused user
settings file, say) prints one `config sources: error:` line instead, and `doctor` still exits `0`.
`docsentinel doctor --no-user-settings` leaves the user layer out of these lines.

The `fact-check gate` line shows whether the `DS302` network opt-ins are met (it imports the backend, and
so `httpx`, only when both the flag-or-environment opt-in and the key are set). The `fact templates
(packaged)` line lists the `extract-facts` templates, and a `templates (report_templates_dir)` line lists
your own, with `(context checked at load)`.

The `reference scope` line shows the scope of the configuration in the current directory
(`links` or `strict`) and whether `DS103` is on.

The deep profile requires an additional model download even after
`pip install "docsentinel[deep]"`:

```bash
python -m spacy download en_core_web_sm
```

---

## Listing Rules (`docsentinel rules`)

Inspect all registered detection rules across profiles:

```bash
docsentinel rules
```

---

## Project Configuration (`docsentinel init`)

Generate a starter `docsentinel.toml` configuration:

```bash
docsentinel init
```

Created `docsentinel.toml`:
```toml
profile = "fast"
include = ["*.md", "**/*.md"]
exclude = [".git", ".venv", "node_modules"]
select = []
ignore = []

# Standard profile thresholds (profile = "standard"); defaults shown.
# max_grade_level = 14.0          # DS201: flag prose above this readability grade
# duplicate_similarity = 0.85     # DS202: flag paragraph pairs at/above this cosine similarity
# min_information_score = 0.15    # DS203: flag paragraphs scoring below this information score
# docsig_paths = ["src"]          # DS204: Python source roots checked against docstrings
#
# Statistical size limits (standard profile); defaults shown.
# min_document_words = 50         # DS201: skip documents with fewer prose words
# min_paragraph_words = 5         # DS202/DS203: skip paragraphs with fewer words
# min_paragraph_chars = 30        # DS202/DS203: skip paragraphs shorter than this
```

`docsentinel init` refuses to run in a directory that already contains the
equivalent alias `doc_sentinel.toml`, because keeping both files is ambiguous.

For a comprehensive example of fast-profile policy options (DS104–DS118) with
all defaults documented, see [examples/docsentinel.toml](/examples/docsentinel.toml).

---

## Layered configuration: user settings and JSON

Settings come from four layers, lowest first: the built-in defaults, your **user settings** file,
the project configuration, and command-line flags. A later layer replaces a key of an earlier one
as a whole value. The full rules, the refused keys and the file permission rule are in the
[Configuration Reference](../reference/configuration.md#how-to-set-options).

### Project configuration as JSON: `--config FILE.json`

A project file in JSON is never discovered; name it explicitly. It uses the same keys and
validation as TOML:

```bash
docsentinel scan --config ci/docsentinel.json
docsentinel baseline --config ci/docsentinel.json
```

### User settings: `docsentinel init --user`

```bash
docsentinel init --user        # create ~/.local/share/docsentinel/settings.json
docsentinel init --user --yes  # ... without the confirmation prompt in a terminal
```

The file location follows `XDG_DATA_HOME`, or the absolute path in `DOCSENTINEL_SETTINGS`. The
starter file holds `{"profile": "fast", "reference_scope": "links"}`. Missing directories are
created with mode `0700` and the file with mode `0600`. `init --user` never overwrites an existing
file, and it refuses (exit code `2`) when user settings are off (`DOCSENTINEL_SETTINGS=off`), when
no home directory is known, and with `--project-root`. Before it creates anything it applies the
same permission rule as a load to the nearest existing directory, so a home directory that is
group-writable is refused on a first run, even though an existing file in a private `docsentinel`
directory there would load. Fix the directory (`chmod go-w`) and run it again.

To leave the user layer out of a run, pass `--no-user-settings` (on `scan`, `baseline` and
`doctor`), or set `DOCSENTINEL_SETTINGS=off` to disable it for every run.

```bash
docsentinel scan --no-user-settings
```

### CI and pre-commit: turn user settings off

Set `DOCSENTINEL_SETTINGS=off` at **job level** in every CI job that runs `docsentinel`, so a
settings file in the runner's home never changes a gate. This matters most on **self-hosted
runners**, whose home directory persists between jobs: a job that runs untrusted code (a fork pull
request) could write a settings file that every later job, including the protected branch, would
then read. Job-wide `off` only removes trust, so it is safe at job level, unlike the
`python:` extension gate. It closes only this one way for a job to affect a later one: do not run
untrusted fork pull requests on a self-hosted runner that also runs protected jobs.

```yaml
jobs:
  docs:
    runs-on: self-hosted
    env:
      DOCSENTINEL_SETTINGS: "off"
```

The `docsentinel-fast` pre-commit hook reads your user settings on your own machine, which is
usually what you want locally. Where pre-commit runs in CI (a job that calls `pre-commit run
--all-files`), the job-level variable above covers it too; do not rely on pre-commit `args:` for
this. Commit the options the team needs to the project configuration, so a local run and the CI
gate agree.
