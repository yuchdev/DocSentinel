# Task 03 - Unresolvable Path-Like Code Span Detector (`DS103`)

**Story:** [02.0 - Fast-Profile Structural Detectors](README.md)
**Depends on:** Milestone 0001 Story 01.0; disjoint from `DS101`/`DS102` (Tasks 01-02) at the
regex level, but see Scope boundary below for why it must not double-report what `DS101` already
covers.

## Purpose

Covers the "docs mentions an entity that doesn't exist" requirement, scoped to what is
*deterministically* checkable without NLP or project-specific configuration: prose that names a
file-like path in an inline code span - `` `src/foo/bar.py` ``, `` `docs/old-name.md` `` - where
that path does not actually exist. This is deliberately narrower than "any entity mention"
(detecting that generically needs semantic understanding of what counts as an "entity," which is
exactly the kind of check `CLAUDE.md` reserves for `deep`/an agent, not a `fast` regex rule) -
`DS103` only ever fires on a span that is syntactically path-shaped.

## Scope boundary vs. `DS101`

`DS101` (Task 01) already flags dangling **Markdown link** targets (`[text](target)`). `DS103`
flags a different surface: a path-like string inside an **inline code span** that is *not* part
of a Markdown link at all - plain prose like `` See `scripts/old_tool.py` for details. `` with no
`[...]()` around it. A code span that happens to sit inside a link's text part (`` [`foo.py`](foo.py) ``)
is `DS101`'s concern (the link target), not `DS103`'s (the code span is just link label text,
skip it) - **do not** flag code spans that are themselves inside a link's visible text.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/paths.py` | Create |
| `tests/test_detectors_paths.py` | Create |

## Symbols / fields

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS103` | module-level `Rule` | `Rule(code="DS103", profile="fast", title="Unresolvable path-like code span", description="An inline code span looks like a file path but does not resolve.", severity="warning")`. `warning`: a false positive here (a code span that merely *resembles* a path, e.g. a CLI flag) is more likely than for `DS101`/`DS102`, so this must not default to build-breaking `error`. |
| `_CODE_SPAN_RE` | module-level compiled regex | `` re.compile(r"`([^`\n]+)`") `` - single-backtick inline spans only (this task does not need to handle multi-backtick spans containing literal backticks; that is a documented non-goal, see Constraints). |
| `_LINK_RE` | module-level compiled regex | Same shape as `detectors.links._LINK_RE` (duplicated per module, per this project's established no-shared-helpers-across-detectors convention from Task 02) - used only to find spans of text that are a link's visible label, so code spans inside them can be excluded. |
| `_looks_path_like(candidate: str) -> bool` | function | True if `candidate` contains `/` **or** matches `re.search(r"\.[A-Za-z0-9]{1,5}$", candidate)` (a file-extension-shaped suffix) - **and** none of the exclusion rules below apply. |
| `_is_excluded(candidate: str) -> bool` | function | True (skip, not a path) when `candidate`: contains whitespace; starts with `-` or `--` (a CLI flag, e.g. `` `--format` ``); starts with `$` or `>` (a shell prompt/variable, e.g. `` `$HOME/.env` ``'s leading `$HOME` segment - full string starting with `$`); matches `re.fullmatch(r"v?\d+(\.\d+){1,3}", candidate)` (a bare version number like `1.2.3` or `v2.0`); or is a bare file extension with no path segment and no base name longer than 4 characters (`` `.md` `` alone, `` `.py` `` alone) - these read as "the *kind* of file," not a *specific* file. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, the `Analyzer` | For each `.md` document: strip fenced blocks (reuse the same blank-not-delete approach as `DS102`, written locally in this module per the no-shared-helpers convention); find all `_CODE_SPAN_RE` matches whose span does **not** fall inside any `_LINK_RE` match's label portion; for each remaining candidate passing `_looks_path_like` and not `_is_excluded`, resolve it the same way `DS101` resolves link targets (leading `/` → repo-root-relative to `root`; else relative to the document's own directory) and emit a `Finding(rule="DS103", ..., line=...)` with the one-based match line if it does not exist on disk. |

## Tests (`tests/test_detectors_paths.py`)

- `test_unresolvable_relative_path_is_flagged` - `` `src/missing.py` `` with no such file.
- `test_existing_path_produces_no_finding` - `` `src/docsentinel/cli.py` `` (real file) is clean.
- `test_leading_slash_resolves_from_root` - `` `/docs/x.md` `` resolves against `root`.
- `test_cli_flag_like_span_is_excluded` - `` `--format` `` never flagged even though absent.
- `test_version_number_like_span_is_excluded` - `` `1.2.3` `` and `` `v2.0` `` never flagged.
- `test_bare_extension_span_is_excluded` - `` `.md` `` alone never flagged.
- `test_span_with_whitespace_is_excluded` - `` `not a path` `` never flagged (contains a space).
- `test_code_span_inside_link_label_is_not_double_reported` - `` [`missing.py`](missing.py) ``
  produces a `DS101` finding (verified via that module directly, not re-asserted here) and
  **zero** `DS103` findings for the same span.
- `test_code_span_inside_fenced_block_is_ignored` - same fence-skip guarantee as `DS102`.
- `test_non_markdown_documents_are_not_scanned`.
- `test_finding_reports_one_based_source_line` - a missing path-like span after preceding content
  reports the line containing that span through `Finding.line`.

## Success criteria

- [ ] No overlap in reported findings between `DS101` and `DS103` for the same source span - a
      shared fixture document containing one dangling Markdown link and one bare path-like code
      span must produce exactly one `DS101` and one `DS103` finding, not two of either.
- [ ] The exclusion list in `_is_excluded` is driven entirely by the named rules above - no
      project-specific hardcoded exceptions (e.g. no allowlist of specific filenames) sneak in;
      a generic OSS tool cannot special-case anyone's repo.

## Constraints

- Full type annotations; no bare `except:`.
- **Documented non-goal**: multi-backtick spans (`` ``code with ` inside`` ``) are not parsed:
  `_CODE_SPAN_RE` only matches single backticks. Note this explicitly in the module docstring so
  a future contributor doesn't assume full CommonMark code-span support exists.
- Zero dependency beyond the standard library, matching the rest of the `fast` profile.
