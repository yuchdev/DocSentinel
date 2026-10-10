# Task 01 - Dangling Link / Anchor Detector (`DS101`)

**Story:** [02.0 - Fast-Profile Structural Detectors](README.md)
**Depends on:** Milestone 0001 Story 01.0 (rule registry, `ANALYZERS` keyed by code)

## Purpose

The single highest-value fast check any docs tool can ship: a Markdown link or `#anchor` that
does not resolve. This project's own `scripts/check_doc_links.py` (used by this repo's `.claude`
tooling to lint *this repo's own* docs) already implements exactly this algorithm - port its
logic into the `docsentinel` package itself as `DS101`, rather than inventing a second
implementation. Read that script first; this task is a structured port, not a fresh design.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/models.py` | Modify - add the authorized optional, one-based `Finding.line` field |
| `src/docsentinel/detectors/__init__.py` | Create (empty for now - Task 04 populates it) |
| `src/docsentinel/detectors/links.py` | Create |
| `tests/test_detectors_links.py` | Create |

## Symbols / fields

`src/docsentinel/detectors/links.py`:

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS101` | module-level `Rule`, via `register_rule(Rule(code="DS101", profile="fast", title="Dangling link or anchor", description="A Markdown link or #anchor target does not resolve.", severity="error"))` | `error` severity - a dangling link is unambiguously wrong, not a style nit. |
| `slugify(heading_text: str) -> str` | function | Port of `check_doc_links.slugify` unchanged (GitHub-slugger behavior: lowercase, strip non-word/space/hyphen chars, spaces to hyphens). |
| `heading_anchors(path: Path) -> set[str]` | function | Port of `check_doc_links.heading_anchors` unchanged, including the duplicate-slug `-1`/`-2` suffixing and `<a id=/name=>` HTML-anchor handling. |
| `check_document(root: Path, document: Document) -> tuple[Finding, ...]` | function | New - adapts `check_doc_links.check_file` to this package's `Document`/`Finding` models instead of printing strings. One `Finding(rule="DS101", path=document.path, message=..., severity="error", line=...)` per dangling link/anchor, with the one-based source line from the matched Markdown link. Message format is `"dangling link -> {target}"` / `"missing anchor '#{anchor}' in {file_part}"` (reuse the source script's exact wording so a user who has seen `check_doc_links.py` output recognizes it). |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, the `Analyzer` | Filters `documents` to `path.endswith(".md")`, calls `check_document` on each, concatenates results. This is the function registered into `ANALYZERS["DS101"]` (Task 04 wires the registration call). |

## Behavior ported unchanged from `scripts/check_doc_links.py`

- Fenced code blocks (`` ``` `` / `~~~`) are skipped entirely - both for link scanning and for
  heading detection inside `heading_anchors`.
- Inline code spans (`` `...` ``) are stripped from a line before link matching, so link-shaped
  text inside code is never treated as a real link. **Known inherited limitation**: the stripping
  regex (`` `+[^`]*`+ ``) matches by backtick *runs*, not CommonMark's actual rule (opening and
  closing delimiters must have the *same* backtick count) - a span delimited by two backticks but
  containing a literal single backtick (e.g. a double-backtick span used specifically to show a
  single backtick character, `` `` `x` `` ``) can be stripped asymmetrically, leaving a link-shaped
  remainder exposed. This is a pre-existing property of `scripts/check_doc_links.py` being ported
  as-is (see Task scope: a faithful port, not a redesign) - do not silently fix it as a drive-by
  improvement; if it proves to matter in practice, it is a follow-up task for a proper CommonMark
  tokenizer, not a regex patch.
- Link resolution: a target starting with `/` resolves repo-root-relative (relative to the
  **scan root**, i.e. `root` in `detect`'s signature - not the current working directory);
  anything else resolves relative to the *linking document's own directory*.
- Skippable targets (never resolved as files): empty, external schemes (`http:`, `mailto:`,
  etc. via the same `_SCHEME_RE`), template paths containing `{`/`}`, and glob patterns
  containing `*`/`?`.
- In-page anchors (`[text](#foo)`) are checked against the *same* document's own headings.
- A target with both a file part and an anchor (`other.md#foo`) is checked in two steps: file
  existence first, then (only if the file exists and is `.md`) anchor existence in that file.

## Tests (`tests/test_detectors_links.py`)

- `test_dangling_file_link_is_flagged` - a link to a nonexistent `.md` file produces one `DS101`
  finding with the dangling-link message shape.
- `test_valid_link_produces_no_finding` - a link to an existing file, with or without a valid
  anchor, is clean.
- `test_missing_anchor_in_same_file_is_flagged` - `[x](#nope)` with no matching heading.
- `test_missing_anchor_in_other_file_is_flagged` - `[x](other.md#nope)` where `other.md` exists
  but lacks that heading.
- `test_duplicate_headings_get_suffixed_anchors` - two `## Foo` headings in one file; a link to
  `#foo-1` (the second one) is valid.
- `test_html_anchor_tag_is_recognized` - `<a id="custom">` satisfies a link to `#custom`.
- `test_links_inside_fenced_code_are_ignored` - a link-shaped string inside a ` ```...``` ` block
  produces no finding even if it would otherwise be dangling.
- `test_links_inside_inline_code_span_are_ignored` - same, for a link-shaped string wrapped in a
  single-backtick inline code span (e.g. `x` with a literal `[x](bad.md)` as its content).
- `test_external_and_template_and_glob_targets_are_skipped` - `http://...`, `{NN}-{slug}.md`,
  and `*.md` targets never resolve to a finding either way.
- `test_leading_slash_resolves_from_scan_root_not_cwd` - run `detect()` with `root` set to a
  `tmp_path` fixture while the test process's actual cwd differs; a `/docs/x.md`-style target
  must resolve against `root`, not `Path.cwd()`.
- `test_non_markdown_documents_are_not_scanned` - a `Document` for a `.txt` file (reachable only
  via a custom `include` pattern) produces no findings even if its content contains a
  link-looking string - `DS101` only reads `.md`.
- `test_finding_reports_one_based_source_line` - a dangling link after preceding content reports
  the line containing that link through the structured `Finding.line` field.

## Success criteria

- [ ] Every behavior in "Behavior ported unchanged" above has at least one covering test.
- [ ] Running `detect()` against this repo's own `docs/adr/0001-config-loading-via-layered-settings.md`
      (an existing file with three already-known dangling links to a deleted task spec) produces
      exactly three `DS101` findings - a real-world smoke check that the port is faithful, not
      just unit-test-green.

## Constraints

- Full type annotations; no bare `except:`. Reading file content for link/heading extraction
  needs `OSError`/`UnicodeDecodeError` handling consistent with how `config.py` already handles
  file reads - propagate, do not swallow (a document that cannot be read is itself worth
  surfacing, not silently skipping; raising is acceptable for this task - Task 04's end-to-end
  test should confirm `scan()` doesn't crash the whole run on one bad file, and if it does,
  flag that as a gap for Task 04 to resolve, not something to silently work around here).
- Do not import from or shell out to `scripts/check_doc_links.py` - this task ports the
  *algorithm*, the shipped package must have zero runtime dependency on the repo's own
  `scripts/` directory (those scripts lint *this repo's* docs with the kit tooling; they are not
  part of the `docsentinel` distribution).
