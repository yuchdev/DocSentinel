# Configuration Reference — Fast-Profile Policy Options

This page is the reference for every configuration option introduced in
Milestone 0005 for the fast-profile rules DS104–DS118 and, since Milestone 0009, the
reference-scope options of DS103 and DS124, and since Milestone 0010 the `fact_check_*` options of DS302. All defaults and
valid values on this page were verified against
`src/docsentinel/config.py` before publication.

For the standard-profile statistical keys (`max_grade_level`,
`duplicate_similarity`, `min_information_score`, `docsig_paths`,
`min_document_words`, `min_paragraph_words`, `min_paragraph_chars`),
see [Statistical Checks](statistical-checks.md).

For the report options (`report_templates_dir`, `report_show_clean_documents`,
`report_include_run_meta`), see
[Report Formats](../tutorial/report.md#report-options).

## How to set options

An effective configuration is built from four layers. A later layer replaces an earlier one
**per key**, as a whole value: a list is never merged with the list of a lower layer.

1. **Built-in defaults** (the `Config` dataclass).
2. **User settings**: one personal JSON file, described in
   [User settings](#user-settings-json) below.
3. **Project configuration**: one file for the scan, as described next.
4. **Command-line flags**, for example `--reference-scope`, `--profile` or `--strict`, for one run.

A `Config` object passed directly to `scan()` in the Python API bypasses all of this: it is used
as given, with no file read, no user settings and no validation (the caller is responsible for
valid values).

The project configuration is, in order, the first that applies:

1. An explicit file given with `--config FILE` (or `load_config(root, path)`). A `.json`
   suffix, in any letter case, selects the JSON reader; any other suffix is read as TOML.
2. `docsentinel.toml` at the scan root (keys at the top level, no table header).
   `doc_sentinel.toml` is accepted as an equivalent alias.
3. `[tool.doc_sentinel]` in `pyproject.toml` at the scan root.

When a standalone file (`docsentinel.toml` or `doc_sentinel.toml`) and
`pyproject.toml` both exist, the standalone file wins and `pyproject.toml` is
ignored. Having both `docsentinel.toml` and `doc_sentinel.toml` in the same
root is ambiguous: the load fails with exit code 2 and names both files, so
keep only one. New projects should use `docsentinel.toml`, which is what
`docsentinel init` creates (it refuses to run next to an existing
`doc_sentinel.toml`). All options are validated on every
config load regardless of the active profile; an invalid value makes even a
fast scan fail with exit code 2.

**JSON is not discovered in projects.** A project JSON file is read only when you name it with
`--config FILE.json`; no `docsentinel.json` is looked for at the scan root. The keys and the
validation are the same as in TOML, so an invalid value gives the same message.

```json
{
  "profile": "fast",
  "ignore": ["DS102"],
  "reference_scope": "strict"
}
```

JSON is read strictly, and each of these is a configuration error (exit code 2): a file larger than
1 MiB (1,048,576 bytes), a byte-order mark, invalid UTF-8, a duplicate key, `NaN` or `Infinity`, a
`null` anywhere (leave the key out to get its default), a lone surrogate escape, or a top-level
value that is not an object.

### User settings (JSON)

User settings hold your personal defaults, for example `profile` or `reference_scope`, for every
repository you scan on this machine. The file is a JSON object in the format above.

| Where | Location |
|-------|----------|
| Default | `~/.local/share/docsentinel/settings.json` |
| `XDG_DATA_HOME` set (absolute) | `$XDG_DATA_HOME/docsentinel/settings.json` |
| `DOCSENTINEL_SETTINGS=/abs/path.json` | That file, which must exist (a missing file is an error) |
| `DOCSENTINEL_SETTINGS=off` | No user settings at all, for every run |

A missing file at the default location is simply skipped. An empty `DOCSENTINEL_SETTINGS` counts
as unset; a relative path in it is an error. When no home directory is known and no override is
set, the layer is skipped. Create the starter file with
[`docsentinel init --user`](../tutorial/cli.md#user-settings-docsentinel-init---user), or switch
the layer off for one run with `docsentinel scan --no-user-settings` (also on `baseline` and
`doctor`) or in Python with `load_config(root, user_settings=False)`.

**Refused keys.** An option that names a repository file or changes which documents a repository
scans belongs to that repository, not to you, so these ten keys in a user file are a
configuration error that lists every refused key: `baseline`, `include`, `exclude`,
`docsig_paths`, `navigation_indexes`, `navigation_required`, `deprecated_references_file`,
`report_templates_dir`, `link_root` and `telemetry_domains`. The same file may not enable a
`python:` extension either. Set them in the project configuration or on the command line.

**`deep_confirm` at user level.** `deep_confirm` is allowed in user settings, so one setting there
confirms the heuristic deep profile on every repository you scan. The deep profile stays
advisory-only (it never changes the exit code), but if you want each project to opt in on its own,
leave `deep_confirm` out of the user file and use the flag or the project configuration.

**Permission rule.** A user settings file that someone else could have changed would let that
person weaken every scan of yours, so on POSIX systems (Linux, macOS, BSD, WSL) the file is checked
before it is read:

- The file (after following symbolic links) must be a regular file owned by you or by root, and
  must not be writable by group or others.
- The directory that holds the path, each directory that holds a symbolic link on the way to the
  file, and the directory that holds the final file must be owned by you or by root, and must not be
  writable by group or others. A directory that is group- or world-writable is accepted only when
  it has the sticky bit set (like `/tmp`), and then a symbolic link in it must be owned by you or
  root too. At most 40 links are followed.
- When you run as root, only root-owned files and directories pass, so `sudo` with your `HOME`
  kept does not read your file as root.

A violation is a configuration error with exit code `2` and one of the fixed messages `owned by
another user`, `writable by group or others (run chmod go-w on it)` or `its directory is owned by
another user or writable by others`. There is no warning mode and no override flag. The directory
message names no directory: check the directory holding the file, every directory holding a
symbolic link on the way to it, and the directory holding the final file. Fix a mode problem with
`chmod go-w` on the file or on that directory. An ownership problem, or a link owned by another
user in a shared sticky directory, cannot be fixed with `chmod`: move the file (or the link) to a
directory you own. Or skip the layer with `--no-user-settings` or `DOCSENTINEL_SETTINGS=off`. Read permission is not checked; keep no secrets in the file. On
non-POSIX systems the ownership and mode checks are skipped (the regular-file, size and parse
checks still apply); protect the profile directory with its own access rights. ACLs are not
inspected.

**WSL.** With the default drvfs mount options, files under the Windows mount (`/mnt/c/...`)
report mode `0777`, so the permission rule refuses them. Keep the settings file in the Linux home directory.

**Tools that set `DOCSENTINEL_SETTINGS`.** The path in that variable is trusted. A tool that sets
it for you (direnv, pytest-env, tox `setenv`, an IDE run configuration) is therefore trusted with
your settings: it can point DocSentinel at a file it chose. The file still cannot set the refused
keys, so it cannot change which documents a repository scans, but it can, for example, ignore
rules. Review such hooks as you would any script that runs in your shell.

**CI.** Set `DOCSENTINEL_SETTINGS=off` at job level in every CI job that runs `docsentinel`. On a
self-hosted runner the home directory persists, so a settings file written by one job (a fork pull
request, say) would otherwise apply to every later job, including the protected branch. Job-wide
`off` only removes trust, so it is the safe direction. This repository's own workflow does so.
Quote the value in YAML (`DOCSENTINEL_SETTINGS: "off"`): unquoted, a YAML 1.1 parser reads `off` as
the boolean false. `off` closes only this one way for a job to affect a later one. Do not run
untrusted fork pull requests on a self-hosted runner that also runs protected jobs.

For a working annotated example of every option in this page, see
[examples/docsentinel.toml](/examples/docsentinel.toml).

---

## Selection options: `include` and `exclude`

These two options choose which Markdown documents a scan inventories. Patterns are matched against
each path relative to the scan root, written with `/`, and the match is case-sensitive.

| Option | Type | Default | Merge with the command line |
|--------|------|---------|-----------------------------|
| `include` | list of strings | `["*.md", "**/*.md"]` | `--include` replaces it |
| `exclude` | list of strings | `[".git", ".venv", "node_modules"]` | `--exclude` is appended to it |

A user settings file may not set either key (see [Refused keys](#user-settings-json)).

A value that contains `*`, `?` or `[` is a **glob**; any other value is a **literal**.

| Kind | `include` admits a document when | `exclude` removes a document when |
|------|----------------------------------|-----------------------------------|
| glob | its path matches the glob | its path matches, or a directory name on its path matches |
| literal | the path equals the value, or lies below it and ends in `.md` | the path equals the value or lies below it, or a directory name on its path equals the value |

- A literal names **this file, or this directory and everything below it**. A directory `include`
  admits only `.md` files, so images and sources below it are not inventoried. A literal `exclude`
  prunes the walk: the directory is never entered.
- **Exclude wins.** A document that is both included and excluded is left out.
- Symlinked files and directories are skipped; a literal does not follow them.
- Glob values behave as they always have. Literal values changed: a value such as `docs/archive`
  used to match nothing, and now it matches that directory and everything below it, in a
  configuration file and on the command line alike.
- A file name that contains `*`, `?` or `[` cannot be selected as a literal. Use a glob that
  matches it, writing the bracket as `[[]`: `notes[[]1].md` selects `notes[1].md`.
- Matching is case- and Unicode-normalisation-sensitive: `Docs` does not match `docs`, even on a
  case-insensitive file system, and a look-alike slash such as U+2215 or U+FF0F is an ordinary
  character, not a separator.

```toml
include = ["docs", "README.md"]
exclude = [".git", ".venv", "node_modules", "docs/archive", "**/*.draft.md"]
```

The same options exist on the command line and in Python; see
[Selecting files](../tutorial/cli.md#selecting-files---include-and---exclude) and
[`scan(include=, exclude=)`](../tutorial/library.md#selecting-documents-include-and-exclude).
A configuration value is checked only to be a list of non-empty strings; unlike a command-line
value it is never refused for being absolute, for containing `..` or for naming a missing path.

Corpus-level results depend on the selection (`DS114`, `DS118`, `DS202`, `DS203`, `DS301`), and a
baseline recorded with one selection looks stale under another, so record it with the selection
of the scan it serves. Links into an excluded document still resolve, because `DS101`, `DS113` and
`DS116` read the file system, not the inventory.

---

## Anchor options (DS104)

`DS104` reports conflicts between heading-derived slugs and explicit HTML
anchors. It is always active in the fast profile.

### `anchor_collision_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"explicit"` |
| Valid values | `"off"`, `"explicit"` |
| Consumed by | DS104 |

Controls which kind of anchor collision DS104 reports.

- `"explicit"` (default): report every explicit `<a id="...">` or
  `<a name="...">` anchor whose id duplicates another anchor (generated or
  explicit) in the same document.
- `"off"`: DS104 emits nothing regardless of configuration. The rule still
  appears in `enabled_rules`; selection is orthogonal.

```toml
anchor_collision_policy = "explicit"
```

### `anchor_renderer`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"github"` |
| Valid values | `"github"` |
| Consumed by | DS104 |

Heading-slug algorithm DS104 uses when checking whether a generated heading
anchor collides with an explicit anchor. Currently only GitHub-style slugging
(`"github"`) is supported; the enum may be extended in a future milestone.

```toml
anchor_renderer = "github"
```

---

## Heading options (DS105)

`DS105` reports heading-level skips and violations of the configured first
heading level. It is always active in the fast profile.

### `heading_level_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"no-skips"` |
| Valid values | `"off"`, `"no-skips"` |
| Consumed by | DS105 |

- `"no-skips"` (default): report any heading that jumps more than one level
  down from the previous heading (for example `## H2` directly followed by
  `#### H4`). A level-1 heading is the expected first heading by default
  (controlled by `first_heading_level`).
- `"off"`: DS105 emits nothing.

```toml
heading_level_policy = "no-skips"
```

### `first_heading_level`

| Field | Value |
|-------|-------|
| Type | integer |
| Default | `1` |
| Valid values | integer 1–6 |
| Consumed by | DS105 |

The heading level expected to appear first in a document. When a document's
first heading is at a different level DS105 reports it. The default `1`
means every document should open with an `# H1`.

```toml
first_heading_level = 1
```

**Validation error** — not an integer, or outside 1–6:
```
first_heading_level must be an integer >= 1
```

### `multiple_h1_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"allow"` |
| Valid values | `"allow"`, `"warn"` |
| Consumed by | DS105 |

- `"allow"` (default): more than one level-1 heading in a document is
  accepted.
- `"warn"`: DS105 reports each H1 after the first.

```toml
multiple_h1_policy = "warn"
```

### `setext_heading_support`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS105 |

Whether setext-style headings (a line underlined with `===` or `---`) count
as headings for DS105's hierarchy check.

```toml
setext_heading_support = true
```

---

## Section options (DS106)

`DS106` reports empty or contentless leaf sections. It is always active in
the fast profile.

### `empty_section_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"leaf"` |
| Valid values | `"off"`, `"leaf"`, `"all"` |
| Consumed by | DS106 |

- `"leaf"` (default): report only leaf sections (a heading whose body
  contains no sub-heading) with no visible content.
- `"all"`: report all sections, including non-leaf ones, whose body has no
  visible content before the first sub-heading.
- `"off"`: DS106 emits nothing.

```toml
empty_section_policy = "leaf"
```

### `placeholder_content_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"ignore"` |
| Valid values | `"ignore"`, `"count"` |
| Consumed by | DS106 |

Whether HTML comments (such as a comment containing a placeholder note) count
as section content. Example of a comment-only section body:

```markdown
## In Progress

<!-- This section will be filled in once the API stabilises. -->
```

- `"ignore"` (default): HTML comments are stripped before DS106 tests for
  emptiness, so a section with only a comment is considered empty.
- `"count"`: HTML comments count as visible content; a section is not empty
  if it contains one.

Note: visible marker words like `TODO` or `FIXME` in prose are **always**
treated as content by DS106. DS119 (not yet implemented) is the rule for
detecting leftover TODO markers.

```toml
placeholder_content_policy = "ignore"
```

### `image_content_counts`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS106 |

Whether an image (`![alt](src)`) counts as section content. When `true` (the
default), a section that contains only an image is not reported as empty.

```toml
image_content_counts = true
```

### `empty_section_min_text_chars`

| Field | Value |
|-------|-------|
| Type | integer |
| Default | `0` |
| Valid values | integer >= 0 |
| Consumed by | DS106 |

Visible-character threshold. A section is reported when its visible
non-whitespace character count is **less than or equal to** this value, so
a section must carry **strictly more** than `empty_section_min_text_chars`
characters to be non-empty. The default `0` means any visible text at all
is enough to pass.

Setting a positive value (e.g. `5`) flags sections with very short bodies.
This overlaps with DS203 quality scoring; prefer DS203's `min_information_score`
for quality filtering.

```toml
empty_section_min_text_chars = 0
```

**Validation error** — negative integer:
```
empty_section_min_text_chars must be a non-negative integer
```

---

## Reference definition options (DS108)

`DS108` reports reference-style link definition integrity problems. It is
always active in the fast profile.

### `unused_reference_definitions`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `false` |
| Valid values | `true`, `false` |
| Consumed by | DS108 |

Whether DS108 flags reference definitions that are never used in the same
document. Off by default because many repositories intentionally define
shared or reusable references.

```toml
unused_reference_definitions = false
```

### `duplicate_reference_definitions`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"warn"` |
| Valid values | `"off"`, `"warn"`, `"error"` |
| Consumed by | DS108 |

Severity for a reference label defined more than once in the same document.

- `"off"`: duplicates are not reported.
- `"warn"` (default): duplicates produce a warning finding.
- `"error"`: duplicates produce an error finding (blocking by default, or
  under `--strict`).

```toml
duplicate_reference_definitions = "warn"
```

### `reference_label_normalization`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"commonmark"` |
| Valid values | `"commonmark"` |
| Consumed by | DS108 |

The normalization dialect used to compare reference labels. `"commonmark"`
applies Unicode NFC normalization, whitespace collapse, and Unicode case
folding, so `[Getting Started]` and `[getting   started]` are the same
label. Only `"commonmark"` is currently supported; any other value is
rejected on load.

```toml
reference_label_normalization = "commonmark"
```

---

## Fence options (DS109)

`DS109` reports malformed or unclosed fenced code blocks. It is always
active in the fast profile at error severity.

### `fence_dialect`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"gfm-subset"` |
| Valid values | `"gfm-subset"` |
| Consumed by | DS109, DS110 |

The fenced-code dialect recognized. `"gfm-subset"` (the only supported
value) accepts backtick and tilde fences with 1–3 leading spaces; a closing
fence must use the same marker character and equal or longer run, with an
empty info string. Indented (4-space) code blocks are not recognized.

```toml
fence_dialect = "gfm-subset"
```

### `report_stray_closing_fence`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `false` |
| Valid values | `true`, `false` |
| Consumed by | DS109 |

Reserved. In the `gfm-subset` dialect a stray closing fence (a closing
marker with no preceding opening fence) is silently ignored. This option is
accepted but currently has no effect; it is a placeholder for a future
dialect that may report orphan closers.

```toml
report_stray_closing_fence = false
```

---

## Fence language options (DS110) — opt-in

`DS110` is an **opt-in** rule: it is silent until `require_fence_languages`
is set to `true`. It is always in `enabled_rules` and named in the scan
notice when off.

### `require_fence_languages`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `false` |
| Valid values | `true`, `false` |
| Consumed by | DS110 (opt-in gate) |

The opt-in switch for DS110. When `true`, every non-empty fenced code block
must carry a language label. Empty fences are controlled by
`allow_unlabelled_empty_fences`.

```toml
require_fence_languages = true
```

### `allow_unlabelled_empty_fences`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS110 |

When `true` (the default), empty fences (fences with no content lines) are
exempt from the language-label requirement even when
`require_fence_languages` is enabled.

```toml
allow_unlabelled_empty_fences = true
```

### `allowed_fence_languages`

| Field | Value |
|-------|-------|
| Type | list of strings |
| Default | `[]` (all languages allowed) |
| Valid values | list of non-empty single-token strings |
| Consumed by | DS110 |

Allowlist of accepted language labels. When empty (the default), any label
satisfies the requirement. When non-empty, only the listed labels are
accepted; a fence with a different label is reported.

Labels are matched case-sensitively. An entry containing whitespace is
rejected with a `ConfigError` because it can never match a single-token
language.

```toml
allowed_fence_languages = ["python", "bash", "yaml", "toml", "json"]
```

**Validation error** — whitespace in an entry:
```
allowed_fence_languages entries must be single tokens (no whitespace)
```

---

## Table options (DS117)

`DS117` reports malformed GFM pipe-table structure. It is always active in
the fast profile.

### `table_dialect`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"gfm-subset"` |
| Valid values | `"gfm-subset"` |
| Consumed by | DS117 |

The pipe-table dialect DS117 validates. `"gfm-subset"` is the only supported
value. Pipe tables inside block quotes, list items, or 4-space indented code
are not recognized. When `table_dialect` names an unsupported value DS117
emits nothing.

```toml
table_dialect = "gfm-subset"
```

**Known limitation:** GitHub splits table cells on every unescaped pipe,
even inside backtick code spans. DS117 instead protects pipes inside code
spans (they do not split a cell). DS117 can therefore under-report relative
to what GitHub renders. A literal pipe that must split a cell should be
written outside a code span or escaped as `\|`.

### `table_strict_cells`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS117 |

When `true` (the default), DS117 reports a body row whose logical cell count
differs from the header row. When `false`, cell-count mismatches are not
reported; only malformed alignment markers are.

```toml
table_strict_cells = true
```

### `table_enable`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS117 |

When `false`, DS117 performs no table scanning and emits nothing. Use this
to silence all table findings without removing DS117 from `enabled_rules`.

```toml
table_enable = true
```

---

## Navigation options (DS112) — opt-in

`DS112` is an **opt-in** rule: it is silent until `navigation_indexes` names
at least one index document. A missing or unreadable configured index is a
fail-closed readiness error (exit code 2), not a finding.

### `navigation_indexes`

| Field | Value |
|-------|-------|
| Type | list of relative paths |
| Default | `[]` |
| Valid values | non-empty list of relative paths inside the scan root |
| Consumed by | DS112 (opt-in gate) |

Paths to Markdown index documents whose navigation lists are inspected. Each
path must be inside the scan root; paths that escape the root are rejected
on load with a `ConfigError`. Each configured index must be present in the
discovered document set (an in-root, non-symlinked, regular `.md` file
matching `include`/`exclude`); if it is not, DS112 raises a readiness
`ConfigError` (CLI exit 2).

```toml
navigation_indexes = ["docs/README.md"]
```

**Polyrepo note.** Navigation links are checked inside the scan root only;
cross-root links trigger DS116. In a polyrepo where docs reference sibling
repositories, consider setting `root_escape_policy = "warn"` or `"off"` to
avoid DS116 blocking the build.

### `navigation_required`

| Field | Value |
|-------|-------|
| Type | list of relative paths |
| Default | `[]` |
| Valid values | list of relative paths inside the scan root |
| Consumed by | DS112 |

Documents that must appear in at least one navigation link across all
configured indexes. DS112 reports a `warning` for each required document
with no inbound navigation link.

```toml
navigation_required = ["docs/architecture/README.md", "docs/user/tutorial/README.md"]
```

### `navigation_unique_targets`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS112 |

When `true` (the default), DS112 reports a navigation link target that
appears more than once within the same index document.

```toml
navigation_unique_targets = true
```

### `navigation_check_missing`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS112 |

When `true` (the default), DS112 reports a navigation link whose local
destination does not exist on disk.

```toml
navigation_check_missing = true
```

---

## Asset options (DS113)

`DS113` reports local media and document assets that do not exist as a
regular file inside the scan root. It is always active in the fast profile
at error severity (blocking by default, downgraded by `missing_asset_policy`).

### `asset_extensions`

| Field | Value |
|-------|-------|
| Type | list of strings |
| Default | `["png", "jpg", "jpeg", "svg", "webp", "gif", "pdf"]` |
| Valid values | list of non-empty extension strings (without leading `.`) |
| Consumed by | DS113 |

File extensions that DS113 treats as local media assets when encountered as
HTML `<a href>` link targets or reference-definition targets. The comparison
is case-insensitive. Markdown images (`![alt](src)`) and HTML `<img>`/`<source>`
tags are always checked regardless of extension; this option gates only
link-shaped references.

```toml
asset_extensions = ["png", "jpg", "jpeg", "svg", "webp", "gif", "pdf"]
```

### `check_html_asset_tags`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS113 |

When `true` (the default), DS113 inspects HTML `<img src>`, `<source src>`,
and `<a href>` tags for missing local assets.

```toml
check_html_asset_tags = true
```

### `check_markdown_images`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS113 |

When `true` (the default), DS113 inspects Markdown image syntax
`![alt](src)` for missing local assets.

```toml
check_markdown_images = true
```

### `check_srcset`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS113 |

When `true` (the default), DS113 inspects `srcset` attribute candidates
(from `<img srcset="...">` and `<source srcset="...">`) for missing local
assets. `srcset` values are split per the WHATWG algorithm.

```toml
check_srcset = true
```

### `missing_asset_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"error"` |
| Valid values | `"off"`, `"warn"`, `"error"` |
| Consumed by | DS113 |

Severity policy for a missing or non-regular local asset, mirroring
`root_escape_policy`.

- `"off"`: DS113 emits nothing and performs no filesystem access.
- `"warn"`: each finding is downgraded to `warning` severity.
- `"error"` (default): each finding is `error` severity (blocking).

Teams whose documentation references generated or LFS-stored assets that are
not present at lint time should set this to `"warn"` to avoid blocking the build.

```toml
missing_asset_policy = "error"
```

---

## Path-boundary options (DS116)

`DS116` reports references that escape the documentation root. It is always
active in the fast profile at error severity.

### `root_escape_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"error"` |
| Valid values | `"off"`, `"warn"`, `"error"` |
| Consumed by | DS116 |

Severity policy for a reference that escapes the scan root.

- `"off"`: DS116 emits nothing.
- `"warn"`: each finding is `warning` severity.
- `"error"` (default): each finding is `error` severity (blocking).

**Polyrepo docs.** In a polyrepo where Markdown documents legitimately
reference sibling repositories with relative `../sibling/README.md` paths,
every such link escapes the single-repository scan root and would be flagged
at error severity. Set `root_escape_policy = "warn"` or `"off"` for repos
that intentionally cross root boundaries, or scope the scan to a subdirectory
that keeps all cross-links inside the root.

```toml
root_escape_policy = "error"
```

### `decode_percent_paths`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS116 |

When `true` (the default), DS116 percent-decodes link targets once before
checking for root escape, so `..%2f..%2fpasswd` is treated as a traversal.
Double-encoded paths (`%252e%252e`) are not decoded.

```toml
decode_percent_paths = true
```

### `windows_path_policy`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"portable"` |
| Valid values | `"off"`, `"portable"` |
| Consumed by | DS116 |

How DS116 treats Windows-style drive letters (`C:\`), UNC paths
(`\\server\share`), and rooted backslash paths.

- `"portable"` (default): drive letters, UNC prefixes, and backslash
  separators in links, images, reference definitions, and HTML
  `href`/`src`/`srcset` are reported as unsafe. In inline code spans they
  are treated as documentation and not reported (DS103 retains its legacy
  behaviour for those).
- `"off"`: Windows path forms are not reported. Use only when all consumers
  are Windows and portability is not a concern.

```toml
windows_path_policy = "portable"
```

### `link_root`

| Field | Value |
|-------|-------|
| Type | string |
| Default | `"auto"` |
| Valid values | `"auto"`, or a path relative to the scan root naming the scan root or a permitted ancestor (`"."`, `".."`, ...) |
| Consumed by | DS101, DS103, DS112, DS113, DS116, DS124 |

The directory that site-root-absolute targets (a link starting with `/`, such as
one to the ADR index under the repository's docs directory) resolve against.
GitHub resolves `/` against the repository root, so scanning only the docs
directory must not join such a link onto that directory a second time.

- `"auto"` (default): the nearest ancestor of the scan root, the scan root
  included, that holds a `.git` directory or file (worktrees and submodules use
  a `.git` file). Without one, the scan root is used, as before.
- A relative path: `"."` keeps the scan root (MkDocs-style sites where `/`
  means the docs directory); `".."` uses its parent. A configuration file is
  supplied by the scanned repository, so its value is bounded: inside a git
  repository it may not go above the nearest directory holding `.git`; outside
  one, an ancestor is accepted only if that exact directory directly contains
  a pyproject.toml, docsentinel.toml or doc_sentinel.toml file (checked for
  existence only, never read). The filesystem root is always refused. Anything
  else, or a missing directory, is a configuration error (exit code 2).
- A git repository rooted at your home directory or above (a "dotfiles"
  checkout) is not trusted as a link root: `"auto"` then uses the scan root, and
  a configured ancestor is a configuration error.

**Command line.** `docsentinel scan --link-root PATH` (also on `baseline`, and
`docsentinel.scan(..., link_root=PATH)` in Python) sets the link root for one
run and wins over the configuration. It is trusted invoker input, like
`--template`: PATH is absolute or relative to the current directory, is
resolved through symlinks, and must be an existing directory that is the scan
root or one of its ancestors. No `.git` or project marker is needed; only the
filesystem root is refused. Use it for docs that are not in a
git repository, or to go further up than a configuration file may.

Only `/` targets of links, and the fallback step of `DS124` `@`-mentions, are
affected; relative link targets still resolve against the referring document.
`DS124` tries every relative mention against the link root when it is not found
next to the document, so a bare file name is looked up at the link root too. A `/` target inside the link root is a valid repository
reference, even outside the scan root (a link to a source file while scanning
only the docs directory), so DS116 does not report it; a `/` target whose `..`
climbs above the link root is still an escape.

**Trust.** `"auto"` trusts the enclosing git repository: DocSentinel checks
whether `/` targets exist anywhere in it and reads the headings of linked
Markdown files there. `DS124` also checks every relative `@`-mention against it.
If you scan untrusted content that was extracted inside another repository (for
example a downloaded archive unpacked into your checkout), its `/` links and its
`DS124` mentions can reach files of that repository: each mention shows, as a
finding or none, whether one file exists there, and CI output exposes that
result. Set `link_root = "."` for such scans so `/` links and mention fallbacks
stay within the scanned directory.

```toml
link_root = "auto"
```

---

## Document identity options (DS114)

`DS114` reports duplicate stable document identifiers across the corpus.
It is always active in the fast profile at error severity.

### `document_id_field`

| Field | Value |
|-------|-------|
| Type | string |
| Default | `"id"` |
| Valid values | alphanumeric/underscore/hyphen identifier, 1–128 characters |
| Consumed by | DS114 |

The YAML frontmatter key whose value DS114 uses as the document's stable
identity. The default `"id"` means DS114 looks for `id:` in the opening
`---` block.

```toml
document_id_field = "id"
```

**Validation error** — wrong characters or empty:
```
document_id_field must match [A-Za-z_][A-Za-z0-9_-]{0,127}
```

### `document_id_scope`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"corpus"` |
| Valid values | `"corpus"`, `"directory"` |
| Consumed by | DS114 |

Scope within which document identities must be unique.

- `"corpus"` (default): ids must be unique across all discovered documents.
- `"directory"`: ids must be unique within each directory (the parent
  directory of each document).

```toml
document_id_scope = "corpus"
```

### `document_id_case_sensitive`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS114 |

When `true` (the default), identity comparison is case-sensitive: `Guide`
and `guide` are distinct identities. When `false`, identities are
case-folded before comparison.

```toml
document_id_case_sensitive = true
```

### `document_id_required`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `false` |
| Valid values | `true`, `false` |
| Consumed by | DS114 |

When `true`, every discovered document must declare an identity in its
frontmatter (the configured `document_id_field` must be present with a
non-null value). Documents that do not are reported as findings.

```toml
document_id_required = false
```

---

## Deprecated reference options (DS115) — opt-in

`DS115` is an **opt-in** rule: it is silent until
`deprecated_references_file` names a TOML mapping file. A missing,
unreadable, or schema-invalid mapping is a fail-closed readiness error
(exit code 2), not a finding.

### `deprecated_references_file`

| Field | Value |
|-------|-------|
| Type | string (relative path) |
| Default | `""` (empty, rule is off) |
| Valid values | relative path inside the scan root |
| Consumed by | DS115 (opt-in gate) |

Path to a TOML file mapping deprecated names to their replacements. The
file must be inside the scan root. Example mapping file:

```toml
version = 1

[[replacement]]
old = "oldmod"
new = "newmod"
kind = "prose"           # prose | link | identifier

[[replacement]]
old = "docs/old-guide.md"
new = "docs/new-guide.md"
kind = "link"
scope = ["!archive/*"]   # exempt paths matching archive/*
```

```toml
deprecated_references_file = ".deprecated-names.toml"
```

### `deprecated_check_prose`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS115 |

When `true` (the default), DS115 checks `kind = "prose"` and
`kind = "identifier"` entries against prose text and inline code spans
respectively.

```toml
deprecated_check_prose = true
```

### `deprecated_check_links`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS115 |

When `true` (the default), DS115 checks `kind = "link"` entries against
local link targets and reference-definition targets (lexically only —
existence is DS101's concern).

```toml
deprecated_check_links = true
```

### `deprecated_case_sensitive`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS115 |

When `true` (the default), deprecated term matching is case-sensitive. When
`false`, both the `old` token and the document text are NFC case-folded
before comparison.

```toml
deprecated_case_sensitive = true
```

---

## Documentation naming options (DS118) — opt-in

`DS118` is an **opt-in** rule: it is silent until `documentation_naming`
selects a style. It reads no document content and touches no filesystem; it
decides entirely from each discovered document's relative path string.

### `documentation_naming`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"off"` |
| Valid values | `"off"`, `"kebab"`, `"snake"` |
| Consumed by | DS118 (opt-in gate) |

The naming style enforced on every discovered document path component.

- `"off"` (default): DS118 emits nothing.
- `"kebab"`: each path component must be lowercase ASCII
  alphanumeric words joined by single hyphens (`lowercase-words.md`).
- `"snake"`: each path component must be lowercase ASCII
  alphanumeric words joined by single underscores (`lowercase_words.md`).

Non-ASCII characters are not allowed under either style (the policy is
deliberately portable-ASCII). DS118 suggests a deterministic conformant
rename for each violation.

```toml
documentation_naming = "kebab"
```

### `documentation_naming_allow`

| Field | Value |
|-------|-------|
| Type | list of strings |
| Default | `["README.md", "index.md"]` |
| Valid values | list of non-empty strings |
| Consumed by | DS118 |

Exact filename exemptions. A path's filename (the final component) is exempt
when it matches exactly. A full relative path is exempt when the whole path
matches. Comparison is case-sensitive.

```toml
documentation_naming_allow = ["README.md", "index.md", "CHANGELOG.md"]
```

### `documentation_naming_directories`

| Field | Value |
|-------|-------|
| Type | boolean |
| Default | `true` |
| Valid values | `true`, `false` |
| Consumed by | DS118 |

When `true` (the default), DS118 checks directory components of each
discovered document path in addition to the file component. When `false`,
only the file component is checked.

```toml
documentation_naming_directories = true
```

### `documentation_naming_prefix_patterns`

| Field | Value |
|-------|-------|
| Type | list of strings |
| Default | `[]` |
| Valid values | list of restricted glob-subset strings |
| Consumed by | DS118 |

Glob-subset patterns for conventional numeric prefixes such as ADR numbers
(`0001-`) or version tags (`v1-`). A literal character matches itself; `?`
matches exactly one character; `*` matches any (possibly empty) run. No
character classes, alternations, or anchors; the text is never compiled as a
regular expression.

A path component is exempt from the style check only for the prefix portion
matching the pattern; the remainder still must conform.

```toml
documentation_naming_prefix_patterns = ["[0-9][0-9][0-9][0-9]-", "v*-"]
```

**Validation error** — too many patterns or a pattern that is too long:
```
documentation_naming_prefix_patterns: too many patterns (max 256)
documentation_naming_prefix_patterns: pattern too long (max 256 chars)
```

---

## Reference scope options (DS103, DS124)

`reference_scope` decides whether `DS103` (path-like inline code spans) runs at all. `DS124`
checks `@`-document mentions in both scopes and is tuned by `at_reference_extensions`. The scan
notice names `DS103 (set reference_scope = "strict")` while the scope is `"links"`, so a default
scan never reads as if it had checked code-span paths. For the grammar of a mention and the two
resolution steps, see [document mentions](../tutorial/cli.md#document-mentions-ds124).

### `reference_scope`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"links"` |
| Valid values | `"links"`, `"strict"` |
| Consumed by | DS103 (opt-in gate) |

Which path-like references a scan checks.

- `"links"` (default): Markdown links and `@`-document mentions only. `DS103` is inert: it emits
  nothing and is listed as opt-in and not enabled.
- `"strict"`: `DS103` also checks path-like inline code spans, as it did before 1.3.0, except
  spans starting with `@` (those belong to `DS124` and `DS116`).

`docsentinel scan --reference-scope {links,strict}` (also on `baseline`) overrides the key for one
run. Any other value is a `ConfigError` (exit code 2). An injected `Config` with an unknown value
keeps `DS103` inert.

```toml
reference_scope = "strict"
```

### `at_reference_extensions`

| Field | Value |
|-------|-------|
| Type | list of strings |
| Default | `["md", "markdown", "mdx", "txt", "rst", "toml", "json", "yaml", "yml", "py"]` |
| Valid values | 1 to 64 entries, each 1 to 16 ASCII letters or digits, no dot |
| Consumed by | DS124 |

The file extensions a `relative` `@`-mention must end in to be checked by `DS124`. Entries are
compared case-insensitively and stored lowercase; a duplicate after lowercasing is a
`ConfigError`. An empty list is a `ConfigError` too: to switch the `@`-reference check off use
`ignore = ["DS124"]`. `DS116` still checks every `relative` mention for a root escape, whatever
its extension.

```toml
at_reference_extensions = ["md", "txt", "py"]
```

---

## External fact-checking (DS302)

`DS302` is a deep-profile rule (advisory, warning severity) that sends a few high-salience claim
sentences from your documents to a third-party fact-checking service and reports the ones the service
rates false or mixed. **It is off until both of its independent opt-ins are met, and what it reports is
third-party heuristic output, not ground truth.** Treat a finding as a prompt to review the sentence.

**Sending text to a third party.** When the rule runs, the text of each selected claim sentence (at most
1,000 characters each) leaves your machine for the backend. Preview exactly what would be sent with
`docsentinel extract-facts` first; see
[the CLI guide](../tutorial/cli.md#previewing-what-ds302-would-send-docsentinel-extract-facts).

**The dual gate.** Nothing is sent unless all of these hold:

1. the deep profile is confirmed (`--i-understand-deep-is-heuristic`, `deep_confirm` or
   `DOCSENTINEL_DEEP_CONFIRM=1`);
2. the invoker passes `--use-external-api` (on `scan` and `baseline`), or sets
   `DOCSENTINEL_USE_EXTERNAL_API=1` (exactly `1`), or calls `scan(..., use_external_api=True)`;
3. the backend's API-key variable is set and not empty: `DOCSENTINEL_FACTCHECK_<BACKEND>_API_KEY`, for
   the `lenz` backend `DOCSENTINEL_FACTCHECK_LENZ_API_KEY`;
4. the backend loads.

While the gate is closed the scan logs one WARNING (`DS302 skipped: ...` with what is missing), adds the
same text to `ScanResult.pending`, and does not count `DS302` as evaluated in the scan notice.
`docsentinel doctor` prints `fact-check gate: on (backend: lenz)`, `off (<reasons>)` or
`unknown (configuration error)`.

**Never a configuration key.** `use_external_api` and the API key are not configuration options, in the
project file, the JSON file or the user settings file. A file that names one is rejected as an unknown
option (`Unknown config options: use_external_api`, exit code 2). A repository you scan must never be able to switch on network egress or carry a key, so consent
comes only from the invoker's command line and environment. Never put `--use-external-api` in a
pre-commit `args:` list or a `pull_request_target` workflow, and never export the key variable for a
whole CI job.

**Fixed transport.** The service URL, the 30-second request deadline, the response size cap and the
rules on redirects and proxies are fixed in the backend and are not configurable.

**What a finding says.** Its `type` is `unverified claim` and its `value` is
`<verdict> (confidence 0.87): <claim>`, so the backend confidence is visible. A verdict the backend
returns that DocSentinel does not recognise is skipped with a WARNING and never reported.

The six keys below are allowed in the user settings file as well as the project file.

### `fact_check_backend`

| Field | Value |
|-------|-------|
| Type | string enum |
| Default | `"lenz"` |
| Valid values | `"lenz"` |
| Consumed by | DS302 |

Chooses which backend receives the claims. Choosing one grants no consent; the gate above still applies.

```toml
fact_check_backend = "lenz"
```

### `fact_check_min_salience`

| Field | Value |
|-------|-------|
| Type | number |
| Default | `0.5` |
| Valid values | `0.0` to `1.0` inclusive |
| Consumed by | DS302 |

The salience score a claim needs before it may be sent. Raise it to send fewer, more number- and
entity-heavy claims.

```toml
fact_check_min_salience = 0.7
```

### `fact_check_min_confidence`

| Field | Value |
|-------|-------|
| Type | number |
| Default | `0.6` |
| Valid values | `0.0` to `1.0` inclusive |
| Consumed by | DS302 |

The backend confidence a false or mixed verdict needs to become a finding.

```toml
fact_check_min_confidence = 0.8
```

### `fact_check_max_claims_per_document`

| Field | Value |
|-------|-------|
| Type | integer |
| Default | `3` |
| Valid values | `1` to `50` |
| Consumed by | DS302 |

Most claims sent per document.

```toml
fact_check_max_claims_per_document = 5
```

### `fact_check_max_claims_total`

| Field | Value |
|-------|-------|
| Type | integer |
| Default | `25` |
| Valid values | `1` to `500` |
| Consumed by | DS302 |

Most claims sent per scan, over every document.

```toml
fact_check_max_claims_total = 50
```

### `fact_check_time_budget_seconds`

| Field | Value |
|-------|-------|
| Type | integer |
| Default | `300` |
| Valid values | `1` to `3600` |
| Consumed by | DS302 |

Budget, in whole seconds, for the network stage of one scan. It is measured with a monotonic clock.
Claims not yet sent when it runs out are skipped with one WARNING. A request already in flight can
overrun the budget by up to one backend timeout.

```toml
fact_check_time_budget_seconds = 120
```

---

## Summary table

The following table lists every option on this page with its default and
the rule that consumes it. All defaults were verified against
`src/docsentinel/config.py`.

| Option | Default | Rule |
|--------|---------|------|
| `anchor_collision_policy` | `"explicit"` | DS104 |
| `anchor_renderer` | `"github"` | DS104 |
| `heading_level_policy` | `"no-skips"` | DS105 |
| `first_heading_level` | `1` | DS105 |
| `multiple_h1_policy` | `"allow"` | DS105 |
| `setext_heading_support` | `true` | DS105 |
| `empty_section_policy` | `"leaf"` | DS106 |
| `placeholder_content_policy` | `"ignore"` | DS106 |
| `image_content_counts` | `true` | DS106 |
| `empty_section_min_text_chars` | `0` | DS106 |
| `unused_reference_definitions` | `false` | DS108 |
| `duplicate_reference_definitions` | `"warn"` | DS108 |
| `reference_label_normalization` | `"commonmark"` | DS108 |
| `fence_dialect` | `"gfm-subset"` | DS109, DS110 |
| `report_stray_closing_fence` | `false` | DS109 |
| `require_fence_languages` | `false` | DS110 (opt-in) |
| `allow_unlabelled_empty_fences` | `true` | DS110 |
| `allowed_fence_languages` | `[]` | DS110 |
| `table_dialect` | `"gfm-subset"` | DS117 |
| `table_strict_cells` | `true` | DS117 |
| `table_enable` | `true` | DS117 |
| `navigation_indexes` | `[]` | DS112 (opt-in) |
| `navigation_required` | `[]` | DS112 |
| `navigation_unique_targets` | `true` | DS112 |
| `navigation_check_missing` | `true` | DS112 |
| `asset_extensions` | `["png","jpg","jpeg","svg","webp","gif","pdf"]` | DS113 |
| `check_html_asset_tags` | `true` | DS113 |
| `check_markdown_images` | `true` | DS113 |
| `check_srcset` | `true` | DS113 |
| `missing_asset_policy` | `"error"` | DS113 |
| `root_escape_policy` | `"error"` | DS116 |
| `decode_percent_paths` | `true` | DS116 |
| `windows_path_policy` | `"portable"` | DS116 |
| `link_root` | `"auto"` | DS101, DS103, DS112, DS113, DS116, DS124 |
| `reference_scope` | `"links"` | DS103 (opt-in, on with `"strict"`) |
| `at_reference_extensions` | `["md","markdown","mdx","txt","rst","toml","json","yaml","yml","py"]` | DS124 |
| `fact_check_backend` | `"lenz"` | DS302 (needs `--use-external-api` and an API key) |
| `fact_check_min_salience` | `0.5` | DS302 |
| `fact_check_min_confidence` | `0.6` | DS302 |
| `fact_check_max_claims_per_document` | `3` | DS302 |
| `fact_check_max_claims_total` | `25` | DS302 |
| `fact_check_time_budget_seconds` | `300` | DS302 |
| `document_id_field` | `"id"` | DS114 |
| `document_id_scope` | `"corpus"` | DS114 |
| `document_id_case_sensitive` | `true` | DS114 |
| `document_id_required` | `false` | DS114 |
| `deprecated_references_file` | `""` | DS115 (opt-in) |
| `deprecated_check_prose` | `true` | DS115 |
| `deprecated_check_links` | `true` | DS115 |
| `deprecated_case_sensitive` | `true` | DS115 |
| `documentation_naming` | `"off"` | DS118 (opt-in) |
| `documentation_naming_allow` | `["README.md","index.md"]` | DS118 |
| `documentation_naming_directories` | `true` | DS118 |
| `documentation_naming_prefix_patterns` | `[]` | DS118 |
