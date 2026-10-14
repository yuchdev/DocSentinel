# Task 02 - Stray HTML Comment Detector (`DS102`)

**Story:** [02.0 - Fast-Profile Structural Detectors](README.md)
**Depends on:** Milestone 0001 Story 01.0

## Purpose

Leftover `<!-- TODO: rewrite this section -->`-style HTML comments are the single cheapest
"forgot to clean up" signal in a docs corpus. Pure regex, no dependency, single-document - the
canonical `fast`-tier check.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/comments.py` | Create |
| `tests/test_detectors_comments.py` | Create |

## Symbols / fields

| Symbol | Kind | Notes |
|--------|------|-------|
| `DS102` | module-level `Rule` | `Rule(code="DS102", profile="fast", title="Stray HTML comment", description="An HTML comment was left in rendered Markdown.", severity="warning")` - `warning`, not `error`: a stray comment is a cleanliness nit, not a broken contract (this is exactly the severity distinction Milestone 0001 Story 03.0's exit-code work depends on existing somewhere - this is its first real example). |
| `_COMMENT_RE` | module-level compiled regex | `re.compile(r"<!--.*?-->", re.DOTALL)` - matches the shortest span between `<!--` and the first `-->`, across newlines (`DOTALL`), so a multi-line comment is one match, not one per line. |
| `_FENCE_RE` | module-level compiled regex | Same fence-detection pattern as `detectors.links` (`^ {0,3}(\`{3,}|~{3,})`) - a `<!--` sitting inside a fenced code block (someone showing HTML-comment syntax as an *example*) is not a real leftover comment and must not be flagged. Do not share this constant via import from `detectors.links` - each detector module stays self-contained per this project's existing one-concern-per-module style (see `config.py`/`discovery.py`, which do not share helpers despite both touching paths). |
| `_strip_fenced_blocks(text: str) -> str` | function | Returns *text* with every fenced code block's contents blanked out (same byte length preserved via newline-preserving blanking, not deleted - so matches, if any slipped through outside fences, keep correct line numbers) rather than removed outright. |
| `detect(root: Path, documents: tuple[Document, ...]) -> tuple[Finding, ...]` | function, the `Analyzer` | For each `.md` document: read content, strip fenced blocks, run `_COMMENT_RE.finditer`, emit one `Finding(rule="DS102", path=document.path, message=f"stray HTML comment: {comment_text!r}", severity="warning", line=...)` per match, with the one-based line derived from the match offset. Truncate `comment_text` in the message to its first 80 characters (plus `...` if longer) so a huge commented-out block doesn't produce a huge message. |

## Tests (`tests/test_detectors_comments.py`)

- `test_single_line_comment_is_flagged` - `<!-- TODO -->` on its own line.
- `test_multiline_comment_is_flagged_once` - a comment spanning three lines produces exactly one
  finding, not three.
- `test_comment_inside_fenced_code_block_is_ignored` - a ` ```html\n<!-- example -->\n``` ` block
  produces no finding.
- `test_multiple_comments_in_one_document_each_flagged` - two separate comments in one file
  produce two findings.
- `test_long_comment_message_is_truncated` - a >80-character comment's message ends in `...` and
  is capped at a bounded length.
- `test_non_markdown_documents_are_not_scanned` - same boundary as `DS101`'s equivalent test.
- `test_line_numbers_are_preserved_after_fence_stripping` - a document with a fenced block
  *before* a real stray comment: the real comment's reported line number matches its actual
  line, proving the blank-not-delete stripping approach (not a delete-and-shift approach).

## Success criteria

- [ ] A comment inside a fenced block never produces a finding, in any position in the document
      (start, middle, end of file).
- [ ] Reported line numbers are accurate for a document mixing fenced and non-fenced content.

## Constraints

- Full type annotations; no bare `except:`; same file-read error handling stance as `DS101`
  (Task 01) - do not diverge on this between detector modules without a documented reason.
- Keep the whole module free of any dependency beyond the standard library - this is the point
  of a `fast`-tier check.
