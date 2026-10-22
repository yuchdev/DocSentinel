# Supported Markdown dialect (shared fast scanner)

`src/docsentinel/markdown_blocks.py` is the shared, standard-library-only
block scanner used by DocSentinel's fast detectors. It recognizes a **narrow,
explicitly enumerated subset** of GitHub Flavored Markdown. It is **not** a
CommonMark or full-GFM implementation, and it does not claim conformance with
either specification; there is no conformance suite behind it.

The scanner performs no file, network, or subprocess I/O, imports only the
Python standard library, and runs in time proportional to the source length
for ordinary input.

## Source model

- **Offsets** are character offsets (Python `str` indices) into the input text
  exactly as supplied, reported as half-open ranges `[start_offset, end_offset)`.
- **Line numbers** are one-based physical line numbers. The scanner treats
  `LF`, `CRLF`, and lone `CR` as line terminators and does not invent a phantom
  trailing line when the final newline is absent.
- Fenced code spans are masked for comment, heading, inline-code, link, and
  table scanning, so constructs inside a code block are never tokenized.

## Supported constructs

| Construct | Notes |
|-----------|-------|
| ATX headings | `#` through `######`, requiring whitespace after the marker; trailing `#` runs are stripped. |
| Setext headings | A paragraph line underlined by a `=` run (level 1) or `-` run (level 2). |
| Heading slugs | GitHub-style; duplicate base slugs gain a `-N` suffix, matching DS101. |
| Fenced code | Backtick and tilde fences with 1-3 leading spaces; info strings are captured. |
| HTML comments | `<!-- ... -->`, including multi-line comments, outside fenced code. |
| Inline code | Single-line backtick runs; the closing run must match the opening run length. |
| Reference definitions | Line-initial `[label]: target`; labels are NFC-normalized and case-folded. |
| Reference uses | Full `[text][label]` and collapsed `[label][]` forms. |
| Links and images | `[text](target)` and `![alt](target)`; targets split into path and fragment. |
| HTML images | Basic `<img>` and `<source>` tags, read only for their `src` attribute. |
| HTML anchors | `<a>` tags, read only for `id`/`name` attributes as explicit anchors. |
| Pipe tables | A header row followed by a delimiter row, then consecutive pipe rows; escaped `\|` does not split cells. |

## Malformed fences

An opening fence with no matching closing delimiter is reported as a single
malformed `Fence` (with `closed=False` and a `reason`) that runs to end of file.
Everything between the opener and end of file is treated as swallowed code, so
unrelated rules do not parse it as active Markdown. A closing candidate that
carries an info string, or that uses a shorter or different marker, is not
accepted as a closer; this distinguishes delimiter problems from info-string
problems.

## Intentional gaps

The scanner deliberately does **not** handle these; detectors must avoid
confident diagnostics about them:

- Inline HTML beyond the `<a>`, `<img>`, and `<source>` attributes listed above.
  Arbitrary rendered or untrusted HTML is never scanned with broad regular
  expressions.
- Multi-line inline code spans, nested or escaped emphasis, and backslash
  escapes outside table cells.
- Shortcut reference links (`[label]` with no second bracket pair).
- Indented (four-space) code blocks, block quotes, and list structure.
- Full CommonMark link-destination grammar. A `<...>` angle-bracket destination
  *is* unwrapped (for inline links and reference definitions), and HTML entity and
  numeric character references in a destination are decoded by the resolver, but
  nested balanced parentheses and titles are not parsed: a destination ends at the
  first `)`, so `x(y)z.md` is truncated to `x(y`. A link or reference definition
  whose destination is split across physical lines is not joined (the scanner is
  line-based), so it escapes detection. These are known false negatives for the
  path-boundary check `DS116`, which is a best-effort structural guard rather than a
  complete containment control.
- Unquoted HTML attribute values. Only quoted `id`/`name` attributes
  (`<a id="x">` or `<a name='x'>`) are recognised as explicit anchors; an
  unquoted form such as `<a id=value>` is not, so a detector will not treat it
  as an anchor identity.
- `<a>` tags that span multiple physical lines. Anchor attributes are scanned
  one line at a time, so an `<a>` opener whose `id`/`name` attribute sits on a
  later line than the `<a` is not recognised as an explicit anchor.
- A pipe inside an inline code span does **not** split a table cell in `DS117`,
  which diverges from GitHub. GitHub's own table parser splits a row on
  unescaped pipes *before* inline (code-span) parsing, so GitHub treats
  `` | `a | b` | note | `` as three cells and reports the code span as broken.
  `DS117` instead protects pipes inside code spans, counting two cells there, so
  it will not flag that row. A literal pipe that must split a cell should be
  written outside a code span or escaped as `\|`.
- Pipe tables inside other block constructs are **not** parsed as tables by
  `DS117`. A table-shaped line whose header opens a block quote (`>`), a bullet
  (`-`/`*`/`+`) or ordered (`1.`/`1)`) list item, or a four-space-indented code
  block is treated as a non-table and yields no finding, rather than being parsed
  with the marker as a leading cell. Shallow (zero-to-three-space) indentation is
  still a table; a leading tab counts as indentation to the next multiple-of-four
  column, as in CommonMark, so a tab-indented table-shaped line is also a non-table.
  This follows the rule that unsupported block constructs are left as non-tables
  rather than guessed at.

## Pipe-table findings (DS117)

`DS117` emits **one finding per offending row** (a delimiter or body row whose
logical cell count disagrees with the header under the strict cell policy, or a
delimiter row with a malformed alignment marker), at that row's one-based line.
There is **no** corpus-wide or per-document cap on the number of findings; a
corpus-level cap is planned for Story 15.0. Even pathologically long lines and
documents are processed in time proportional to their length: backtick code-span
closers are resolved through a shared backtick-run index rather than by rescanning
the remainder of a line from every opener.

## Reference-definition integrity (DS108)

`DS108` is a reference *identity* check: it reasons about reference labels and
definitions and never about whether a resolved target exists on disk (that is
`DS101`/`DS113`'s concern). It derives its own escape-aware view of reference
syntax over the scanner's masked text (fenced code, inline code, and HTML
comments are blanked first), so reference-looking material inside those regions
is never recognized.

- A **definition** is a line-initial `[label]: target` (up to three spaces of
  indentation and leading block-quote markers), with a non-empty destination.
  Labels are normalized under the `commonmark` `reference_label_normalization`
  dialect (NFC, whitespace-collapsed, Unicode case-folded), so `[Getting
  Started]` and `[getting   started]` are the same label; any other dialect
  value yields no confident diagnostics.
- A **use** is a *full* `[text][label]` (label is the second bracket), a
  *collapsed* `[label][]` (label is the first bracket), or a *shortcut*
  `[label]` (a lone bracket pair). Image forms (`![text][label]` etc.) are
  treated exactly like their link forms.
- An **undefined reference** finding is emitted for each full or collapsed use
  whose normalized label has no definition. A **shortcut** use with no
  definition is ordinary prose and is **never** flagged; it only counts as a use
  of its label when a definition exists. A **duplicate definition** finding is
  emitted for each definition after the first for a normalized label (gated by
  `duplicate_reference_definitions`: `off` suppresses, `warn`/`error` set
  severity). An **unused definition** finding is emitted only when
  `unused_reference_definitions` is enabled.
- An **escape** is a backslash before a bracket (`\[` / `\]`): escaped reference
  syntax is literal text and is skipped. An inline link `[text](target)` is not
  a reference, so its bracket pair is skipped. Footnotes (`[^note]` and
  `[^note]: ...`) are not ordinary link references in either position. A
  definition line is not also scanned for shortcut uses, so a definition never
  references itself.

Unlike the shared scanner (which does not recognize shortcut reference links,
see *Intentional gaps* above), `DS108` recognizes shortcuts itself over the
masked text, but only to count a shortcut as a *use* of an existing definition;
a shortcut is never a finding on its own.

Known gaps: `DS108` is line-based, so a reference use or definition split across
physical lines is not joined and escapes recognition; only the `commonmark`
normalization dialect is modelled; and link-reference *titles* and the full
CommonMark link-label grammar are not parsed.

## Path resolution

`resolve_local_reference(root, document_path, raw_target)` classifies a target
as `RESOLVED`, `EXTERNAL`, `OUTSIDE_ROOT`, or `UNSUPPORTED`. It is purely
lexical: it never opens a target, follows a symlink, or touches the filesystem,
so it is safe on untrusted content and during tokenization. A missing path is
still `RESOLVED` (existence is DS101/DS113's concern); only a lexical `..`
escape is `OUTSIDE_ROOT`. Symlink-based escapes require filesystem checks and
are out of scope for this resolver.

Before classifying, the resolver unwraps a `<...>` angle-bracket destination,
then decodes HTML entities and numeric character references once
(`html.unescape`), then percent-encoding once (`unquote`), matching what a
renderer resolves. So `&amp;` stays an in-root literal while `&#46;&#46;/` and
`..%2f..%2f` classify as escapes; `%252e%252e` stays literal (no double-decode).
It also extracts HTML `<a href>` and `<img>`/`<source>` `srcset` candidates as
references, and balances nested brackets so the outer destination of
`[![alt](inner)](dest)` is checked. A `srcset` value is split per the WHATWG
algorithm: each candidate URL is a maximal run of **non-whitespace** characters, so
the comma that separates two candidates is the descriptor-delimiting comma *after*
the URL run, never a comma inside the URL. A `data:` URI's internal comma
(`data:image/png;base64,AAAA`) therefore stays part of a single candidate and never
manufactures a spurious in-root path (the HIGH `srcset`/data-URI split guarded by
the `DS113` threat model and regression-tested for `DS116`).

## Missing local assets (DS113)

`DS113` resolves Markdown images (`![alt](target)`), HTML `<img src>`/`<source src>`
tags and `srcset` candidates, HTML `<a href>` link targets, and used reference-style
definitions to local paths and reports a target that does not exist, is not a
regular file, or cannot be used as an asset — **inside the scan root only**. It
reuses the shared resolver and scanner, performs existence and file-type checks with
`os.stat` + `stat.S_ISREG` only, and **never opens or reads asset content**, so a
committed FIFO, device, socket, or directory at an asset path is reported as a
non-regular-file finding without being opened or blocking the scan. Its rulings:

- **R1** — a reference *definition*'s target is checked only when its decoded
  extension is in `asset_extensions` **and** the label is actually used, so `DS113`
  neither steps on `DS101`'s link territory nor flags an unused definition
  (`DS108`'s concern).
- **R2** — a target that `DS116` owns (lexical root escape, `drive`/`unc`/`backslash`/
  `control`, or an in-root symlink whose target escapes the root) is never resolved,
  `stat`-ed, or reported by `DS113`; the escape is solely `DS116`'s finding.
- **R3** — an in-root symlink to an in-root regular file is a valid asset; an
  existing non-regular in-root path is a finding reported without opening it.
- **R4** — the scanner does not model backslash escapes outside table cells, so
  `\![alt](x.png)` is still seen as an image (a possible over-detection, never a
  hidden escape); this is accepted rather than diverging from the shared scanner.
- **R5** — Markdown `![]()` and HTML `<img>`/`<source>` images are checked
  regardless of extension (an image is an asset by syntax); `asset_extensions`
  (matched case-insensitively) gates only link-shaped references (HTML `<a href>`
  and reference definitions). Ordinary Markdown `[text](target)` links are
  `DS101`'s territory, not `DS113`'s.

`DS113` masks inline code spans and HTML comments (constructs a CommonMark renderer
also hides) before considering image and reference tokens, so a missing image inside
`` `...` ``, `<!-- ... -->`, or a fenced block is never reported. It is a best-effort
structural guard, not a complete asset-integrity control: it inherits every
shared-scanner false negative above (multi-line and nested-parenthesis destinations,
multi-line HTML tags, unquoted attributes), and existence is decided by the host
filesystem's **case policy**, so a case-mismatched reference such as `Logo.PNG` to a
committed `logo.png` is platform-dependent (present on case-insensitive macOS or
Windows, missing on a case-sensitive Linux runner). `DS113` adds no per-directory
case check. The `missing_asset_policy` option (`off`/`warn`/`error`, default `error`)
mirrors `root_escape_policy`: `off` suppresses the rule with no filesystem access and
`warn` downgrades each finding to `warning` severity.

Known accuracy gaps of `DS113` (security review, Story 10.0; pinned by tests so they
cannot change silently). **False positives** (an `error` for something a renderer does
not load): an image inside a CommonMark *indented* (4-space) code block is reported,
because the shared scanner does not model indented code; and a destination truncated by
the scanner (`x(y)z.png` read as `x(y`, `<ang le.png>` read as `ang`) is probed under
the truncated name. **False negative**: shortcut reference images (`![ref]` with a
`[ref]: file.png` definition) are not checked, while collapsed (`![ref][]`) and full
(`![alt][ref]`) forms are. Teams hit by these can set `missing_asset_policy = "warn"` or
move the example into a fenced block.
