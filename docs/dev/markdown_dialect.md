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

## Declared navigation integrity (DS112)

`DS112` is an **opt-in** policy (`fast` profile, `warning` severity), inert unless
`navigation_indexes` names one or more Markdown index documents. For each configured
index it scopes *navigation* to the local links on list items, reuses the shared
resolver and scanner, and reports — **inside the scan root only** — a navigation
target linked more than once (`navigation_unique_targets`, default on), a navigation
link whose local destination does not exist (`navigation_check_missing`, default on),
a target that escapes the scan root, and (across every configured index) a
`navigation_required` document that no navigation link points at. The README's
"appear exactly once" contract is realised as the **union** of the presence check
(`navigation_required`) and the uniqueness check (`navigation_unique_targets`),
not one coupled rule: a required target listed twice is reported once as a
duplicate, because `navigation_unique_targets` is on by default. Existence is decided
with `os.stat` only (content is **never** opened), so a FIFO/device/socket at a
navigation destination resolves without blocking. Its rulings (threat model R1–R8):

- **R1 — navigation scope.** The shared scanner does not model lists, so `DS112`
  derives navigation-list membership itself, line-by-line **over the scanner's masked
  text** (fenced code, inline code, and HTML comments blanked), with a bounded linear
  marker test (`-`/`*`/`+` or ordered `N.`/`N)` with 0–3 spaces of indentation),
  exactly as `DS108` derives its reference view and `DS117` its table rows. Only
  inline links and full/collapsed reference uses on a navigation list item are
  navigation; prose links outside lists and links inside fenced/inline-code/comment
  regions are not. No regex over unmasked source.
- **R2 — index read discipline.** A configured index is opened only when it is a
  member of the discovered `documents` (an in-root, non-symlink, regular,
  include-matched `.md` file) and only after a defensive re-check (`is_ds116_owned`
  false, resolver containment, `escapes_via_symlink` false, `os.stat` + `S_ISREG`),
  because an injected `Config` bypasses `load_config` validation; the read is bounded.
- **R3 — fail-closed readiness error.** A missing, unreadable, non-regular,
  out-of-root, or non-discovered configured index raises `ConfigError` (readiness
  error), propagating to CLI exit `2` (`Scan failed:`) and a raised exception for the
  Python API / pytest. It is **never** a `Finding` and **never** a silent clean scan;
  no new exit code and no JSON schema v1 change. An index that exists but is excluded
  by `include`/`exclude` is absent from `documents` and so is this readiness error
  (an internally inconsistent configuration), not a silent skip.
- **R4 — escaping navigation target.** A navigation target that escapes lexically
  (`OUTSIDE_ROOT` or `is_ds116_owned`) is a `DS112` finding emitted **with zero
  filesystem access**; `DS116` independently reports it at `error` (documented
  intentional overlap).
- **R5 — target identity / normalization.** Navigation links and
  `navigation_required` entries are compared as canonical **root-anchored,
  fragment-stripped** resolver paths; navigation links resolve relative to the
  **index location**, not the process cwd; duplicate identity ignores the fragment.
  String comparison is exact (case-sensitive); the existence probe's case behaviour
  is the host filesystem's (as for `DS113`).
- **R6 — missing-destination discipline.** The existence probe is `os.stat` only, on a
  `RESOLVED`, in-root, non-`is_ds116_owned`, non-symlink-escaping target, one `stat`
  per distinct resolved path (memoised); fragment-only and external targets are
  skipped. This overlaps `DS101`'s dangling-link check by design, and `DS112` does
  **not** depend on `DS107` (absent from the audited tree) — it does its own
  normalized resolution.
- **R7 — reference-style vs shortcut.** Full `[text][label]` and collapsed `[label][]`
  navigation items are resolved by joining `reference_uses` to `reference_definitions`
  by normalized label.
- **R8 — opt-in accounting.** The opt-in gate is `navigation_indexes` only;
  `navigation_check_missing`/`navigation_unique_targets`/`navigation_required` are
  sub-options, not part of the gate, so `DS112` is genuinely evaluated whenever indexes
  are configured even if the sub-checks are off. Empty `navigation_indexes` makes
  `DS112` not-applicable and it is named (not counted) in the engine notice, mirroring
  `DS110`.

**Known false positive**: an ordered item with a number other than `1` that directly follows a paragraph line (`3. See [g](x.md)`) is treated as navigation, although CommonMark only lets a list starting at `1` interrupt a paragraph; it is a warning only. An index that is not valid UTF-8 or fails mid-read raises the same bounded `ConfigError` readiness error (exit code 2) as a missing index. Both differentials are pinned by `test_list_recognition_differentials_are_pinned`.

`DS112` is a best-effort structural guard, not a complete navigation-integrity
control. **Known false negatives** (a broken nav item silently passes, never a false
block): a **shortcut-reference** navigation item (bare `[label]` with a `[label]:
target` definition) is invisible because the shared scanner does not populate
`reference_uses` for shortcuts (consistent with the `DS108`/`DS113` shortcut gaps,
*Intentional gaps* above); a link on a **lazy continuation line** of a list item (`- intro` followed by an unindented-or-indented continuation holding the link) is not recognised as navigation although a renderer makes it live; a list item indented **beyond three spaces**, or nested
inside a block quote or an indented (4-space) code block, is not recognised as a
navigation list item because the scanner does not model list or block-quote
structure. `DS112` also inherits every shared-scanner destination false negative
(multi-line and nested-parenthesis destinations, multi-line HTML tags, unquoted
attributes). No ad-hoc regex over unmasked source is added to close these gaps.

## Document identity frontmatter (DS114)

`DS114` reports two documents that declare the **same** stable identity in their
opening YAML frontmatter (corpus-wide, or per directory under
`document_id_scope = "directory"`). Because Milestone 0004's `DS111` metadata rule
is not implemented in this tree, `DS114` carries its own **minimal, linear-time,
bounded, standard-library-only** frontmatter reader rather than importing a YAML
library (a fast-profile runtime imports only the standard library). The reader is
explicitly **not** a YAML implementation; it recognises a narrow, enumerated
subset:

- Only the **opening** `---` block at byte `0` is read (an optional UTF-8 BOM is
  stripped first; `LF` and `CRLF` terminators are handled — a lone `CR` is not a
  terminator, a documented limitation). An `id:` line in body prose, a heading, or
  a fenced code example is therefore **never** metadata.
- The block ends at the first line that is exactly `---` or `...`; it is read from
  a bounded head (the first 64 KiB) and bounded to a line cap, so a huge document
  is never read whole.
- Only **plain top-level** `key: scalar` lines are parsed (no indentation, colon
  followed by whitespace or end of line). The supported scalar forms are a plain
  scalar (with a trailing ` #` inline comment stripped), a single-quoted scalar
  (`''` un-escaped), and a double-quoted scalar whose escapes decode **byte-for-byte
  as YAML** — only `\\`, `\"`, `\/`, `\n`, `\t`, `\r`, `\0`. Any **other**
  double-quote escape (a numeric `\x`/`\u`/`\U`, `\N`/`\_`/`\L`/`\P`, `\<space>`, or
  a trailing line-continuation backslash) is **not mis-decoded**: the reader refuses
  to guess and surfaces the value as *unsupported* (see below) rather than silently
  dropping the backslash. A **non-empty** scalar is compared as its **literal text**
  — numbers and booleans are not interpreted as YAML types.
- A **blank or null** value is treated as *no declared identity* (eligible for the
  `document_id_required` check), not as an empty id. Null here means an empty value
  **or** a YAML null spelling `~` / `null` / `Null` / `NULL`.
- A **multi-line continuation** of the field's value — a non-empty plain or quoted
  inline scalar immediately followed by a more-indented line (blank and comment lines
  skipped) — folds into the value in real YAML, so the first physical line alone is
  the wrong identity. The reader does **not** read the truncated first line; it marks
  the value *unsupported* instead.
- Usable values are normalized to **Unicode NFC** (canonical equivalence) with
  whitespace collapsed (surrounding whitespace stripped, internal runs collapsed), so
  NFC-equivalent and whitespace-only-different ids collide. NFC is deliberate and
  matches a real YAML parser: the reader does **not** apply NFKC/compatibility
  folding, so Unicode confusables (Latin vs Cyrillic look-alikes) stay distinct and
  **zero-width / format characters** (`U+200B` ZWSP, `U+202E` RTL override, …) are
  **not** stripped — two ids differing only by an invisible character are distinct,
  exactly as YAML sees them (this is an accepted, YAML-consistent ruling, not a reader
  divergence). `document_id_case_sensitive = false` additionally case-folds the
  comparison key.

**Delegation to `DS111`.** `DS114` owns only corpus-wide *uniqueness*; metadata
*validity* is `DS111`'s. `DS114` therefore stays **completely silent** (no finding,
no contributed identity, no missing-identity finding) for a document whose
frontmatter is malformed in a way `DS111` would diagnose — an unterminated or
over-long opening block, or the configured field declared **more than once** as a
top-level key (treated as *ambiguous*, not first/last). It never invents an identity
from, nor crashes on, either of these, and never raises a contradictory dual
diagnostic with `DS111`. A document that simply does not declare the field is
*absent* (required-eligible), not malformed. A head that is not valid UTF-8 yields
no identity (encoding validity is out of `DS114`'s scope).

**Alternative key spellings (deferred, not absent).** The reader resolves the field
only from a **plain** top-level `field: …` key. When the field is instead present
under a spelling the reader does not resolve — a **quoted key** (`"id":`), an
**explicit key** (`? id`), or a key reachable through a `<<` **merge key** — a real
parser would still read an identity, so reporting *absent* would be wrong (and under
`document_id_required` would raise a false "declares no id"). `DS114` therefore
**defers** (silent, `DS111` territory) for these rather than reporting absent: no
finding, no contributed identity, no missing-identity finding. When a plain key is
**also** present the plain value is used, **except** that a `<<` merge key anywhere
in the block still forces a defer (an alias in the merge could override the plain
value, so the final identity is uncertain). These are documented reader gaps: a
contributor who writes the id only under such a spelling is neither flagged nor
checked for uniqueness until `DS111` lands.

**Unsupported value shape of the configured field (one explicit finding).** When
the configured field *is* present once in a **well-formed** opening block but its
value shape is unsupported — a flow collection `[`/`{`, an anchor/alias/tag
`&`/`*`/`!`, a block scalar `|`/`>`, a nested mapping/sequence, a multi-line
continuation, an unterminated quoted scalar, or a double-quoted scalar with an
escape outside the decoded subset — `DS114` does not silently drop the document
(which would let an unparseable identity pass as clean). It emits **one** finding at
the rule severity,
attributed to that document at the one-based line of the field, whose message names
only the bounded, repr-escaped field name (never the raw value) and states the shape
is unsupported and the document was *not* evaluated for uniqueness; the document is
then excluded from collision detection. This is a finding, not a `ConfigError`: one
odd document flags itself rather than aborting the whole scan with exit code `2`.

## Deprecated names and migrated references (DS115)

`DS115` is an **opt-in** policy (`fast` profile, `warning` severity), inert unless
`deprecated_references_file` names a root-contained TOML **mapping file**. When set it
reports — **inside the scan root only** — each in-scope textual occurrence of a mapped
`old` token in the discovered Markdown, with the suggested `new` replacement and the
mapping provenance. It is purely textual and **never modifies source**; the only
filesystem access it performs during a scan is the single bounded read of the mapping
file plus the already-discovered documents.

**Mapping schema.** The file is parsed with stdlib `tomllib` and validated by DS115's
own schema:

```toml
version = 1

[[replacement]]
old = "oldmod"           # required: nonempty, bounded, no control bytes
new = "newmod"           # required: nonempty, bounded, no control bytes
kind = "prose"           # required: one of prose | link | identifier
scope = ["docs/*", "!archive/*"]   # optional: bounded list of fnmatch globs
```

A required integer `version = 1`; an array-of-tables `[[replacement]]`; each entry's
`old`/`new` nonempty, length-bounded and control-free; `kind` from the closed enum
`prose`/`link`/`identifier`; an optional `scope` list of bounded globs. Unknown
top-level or entry keys, a missing/mistyped key, an unsupported `kind`, an
empty/whitespace-only or over-long string, more than the entry/scope caps, and a
**cross-entry duplicate/conflicting `old`** (two entries sharing the same NFC,
case-folded `old` **and** the same scope set — a semantic duplicate `tomllib` does not
catch) each raise `ConfigError`.

**Scope and exemption syntax.** `scope` globs match the document's relative POSIX path
once per document with `fnmatch.fnmatchcase`. A plain glob is a positive include (the
entry applies only to matching documents); a `!`-prefixed glob is an exclude (the entry
never applies to matching documents). An empty `scope` applies everywhere; a
scope of only excludes applies everywhere except the excluded paths. The
historical/archive exemption is expressed this way (e.g. `scope = ["!archive/*"]`),
**never** by date-guessing.

Its rulings (threat model R1–R10):

- **R1 — mapping read discipline (no `documents` membership gate).** The mapping is
  TOML, not a discovered `.md` document, so DS112's "member of `documents`" check does
  not apply. Containment is enforced, in order, **before any open**: `is_ds116_owned`
  false, resolver `RESOLVED`, `escapes_via_symlink` false, `os.stat` + `S_ISREG`, and
  `st_size` within the byte cap — because an injected `Config` bypasses `load_config`.
  The file is opened `"rb"`, read bounded, decoded once, and parsed with `tomllib`.
- **R2/R3 — fail-closed readiness.** A missing, unreadable, non-regular, out-of-root,
  oversized, non-UTF-8, unparseable, or schema-invalid mapping raises `ConfigError`,
  propagating to CLI exit `2` (`Scan failed:`) and a raised exception for the Python
  API / pytest. It is **never** a `Finding` and **never** a silent clean scan; no new
  exit code, no JSON schema v1 change. `tomllib`/decode/`OSError` failures are
  re-wrapped as a bounded, repr-escaped `ConfigError` that names only the configured
  path and never the raw `tomllib` text.
- **R4 — literal matcher, linear cost, token boundaries.** `old` tokens (and `scope`
  globs) are matched **literally** and **never** compiled as a user regex (no ReDoS).
  Each substrate unit is tokenized once with the fixed, repo-authored word/path
  tokenizer and the `old` token sequences are held in a per-kind **token trie**, so
  each document position is matched by a walk of at most as many dict steps as the
  longest `old` is tokens long — cost is O(document tokens × longest old in tokens),
  bounded by the mapping and **independent of how many entries share a prefix** (a
  first-token-only bucket was O(entries × document tokens) when many multi-word `old`
  values shared one first token). Whole-token comparison makes `APIv1` not match
  inside `APIv10`; a multi-word `old` matches only whitespace-adjacent tokens on one
  physical line. Each discovered document is read in full exactly as every other fast
  detector reads it (no detector size-caps a discovered file); the linear matcher
  keeps that whole-document read bounded in cost.
- **R5 — scope and masking.** `prose` matches run over the scanner's **masked** physical
  lines (fenced code, inline code, and HTML comments blanked); `identifier` matches over
  `index.inline_code` span text; `link` matches over local link and reference-definition
  targets. `deprecated_check_prose` gates prose/identifier, `deprecated_check_links`
  gates links. No regex over unmasked source and no second Markdown parser.
- **R6 — bounded, repr-escaped echo.** Every readiness `ConfigError` and every finding
  message echo only bounded, `unicode_escape`-ed strings: the raw **configured** mapping
  path (never a resolved absolute path), the raw matched `old`, and the raw suggested
  `new`. Provenance is the configured path plus the integer `[[replacement]]` entry
  index.
- **R7 — normalization and case policy.** Matching normalization is **NFC on both
  sides** (no NFKC / confusable folding, so homoglyphs stay distinct). Case sensitivity
  is governed solely by `deprecated_case_sensitive` (both sides casefolded when false).
  DS115 reports literal occurrences and **never** chases or re-applies a replacement, so
  chains (`a->b->c`) and cycles (`a->b, b->a`) are inert.
- **R8 — opt-in accounting.** The opt-in gate is `deprecated_references_file` only;
  `deprecated_check_prose`/`deprecated_check_links`/`deprecated_case_sensitive` are
  sub-options, not part of the gate, so DS115 is genuinely evaluated whenever a mapping
  is configured even if the sub-checks are off. Empty `deprecated_references_file` makes
  DS115 not-applicable and it is named (not counted) in the engine notice, mirroring
  `DS110`/`DS112`; `detect` returns `()` with zero I/O when unset.
- **R9 — zero filesystem probe of targets.** A deprecated **link**/path token is matched
  and flagged **lexically** with **zero** `stat`/`open`/`realpath`/symlink-follow on the
  target: existence is `DS101`'s concern, root escape `DS116`'s (documented overlap). A
  deprecated path is flagged whether or not it still exists. `resolve_local_reference` is
  used only for string identity and only to re-validate the mapping path.
- **R10 — occurrence counting and determinism.** One finding per distinct occurrence,
  ordered by `(line, source offset, entry index)` and stable across repeated scans and
  fresh roots; exact-duplicate `(line, offset, entry)` tuples are collapsed.

`DS115` is a best-effort, explainable deprecated-term guard over a narrow TOML mapping
and the shared-scanner masked view, **not** a complete migration or terminology control.
**Known gaps** (a mapped term silently passes, never a false block): it inherits every
shared-scanner false negative (multi-line or nested-parenthesis link destinations,
multi-line HTML tags, unquoted attributes, shortcut references). The repo-authored
tokenizer is Unicode `\w`-aware and excludes combining marks, so an `old` and a document
both in NFC tokenize and match; but an **NFD-encoded document** (whose accents are
separate combining marks) is a documented best-effort limitation — its accented
identifiers may not tokenize whole and so may be missed. A dotted/slashed `old`
(`pkg.Old.Thing`, `docs/old-guide.md`) must be written exactly as it appears, and a
multi-word `old` matches only tokens separated by whitespace on one physical line.

**Known false *positive* (prose mask).** The prose mask blanks only the shared
scanner's fenced-code, inline-code and HTML-comment spans, because the scanner exposes
no indented-code-block or HTML-block spans. A `kind="prose"` term inside a CommonMark
**4-space indented code block** or an **HTML block** is therefore reported even though a
renderer shows it as code/markup. This is the one false-positive direction (advisory
`warning` only, downgradable via `select`/`ignore`/baseline); move such examples into a
fenced block, or exclude the path with a `scope` glob, to suppress it. Extending the
mask to indented-code / HTML-block spans is deferred until the shared scanner exposes
those spans, so DS115 never runs a second Markdown parser over unmasked source.

## Documentation path naming policy (DS118)

`DS118` is an **opt-in** policy (`fast` profile, `warning` severity), inert unless
`documentation_naming` selects a style. Unlike every other rule in this document it does
**not** parse Markdown at all: it is a pure policy over the *relative POSIX path string*
of each discovered document, so nothing in the "Source model" or "Supported constructs"
sections applies to it. It performs **zero filesystem access** — no `open`/`read`, no
`stat`/`lstat`/`realpath`, no `scandir`/`listdir` — and never reads document content;
every decision comes from `Document.path` as discovery supplies it.

**Policy.** With `documentation_naming = "off"` (the default) DS118 returns nothing. A
project enables it by choosing a style: `kebab` (lowercase ASCII letters/digits joined by
single hyphens) or `snake` (single underscores). Each `/`-separated path component is
checked independently. A component is conformant when it matches
`[a-z0-9]+(sep[a-z0-9]+)*` for the style's separator — a non-empty run of
lowercase-ASCII-alphanumeric words with no leading/trailing or doubled separator, no
uppercase, no space, no dot, and **no non-ASCII character** (the policy is deliberately
portable-ASCII, so `café-guide.md` is reported). The file component is split into a stem
and a trailing extension at its last dot; the stem is checked against the style and the
extension must be a non-empty run of lowercase ASCII letters/digits, so a
multiple-extension name (`a.b.md`) is reported rather than silently accepted. Directory
components are checked only when `documentation_naming_directories` is true (the default).

**Exemptions.** `documentation_naming_allow` (default `["README.md", "index.md"]`) is an
exact, case-sensitive allowlist: a path's *filename* is exempt when it is listed, and the
*whole relative path* is exempt when the full path is listed. `documentation_naming_prefix_patterns`
(default `[]`) are restricted glob-subset patterns for numeric ADR/release prefixes and
similar conventions — a literal character matches itself, `?` matches exactly one
character, `*` matches any (possibly empty) run; there are **no** character classes,
alternations, or anchors, and the text is **never** compiled as a regular expression
(matching is a linear two-pointer walk, so no pattern can cause catastrophic backtracking).
Both the pattern count and each pattern's length are bounded; an injected `Config`
exceeding either bound, or carrying an unrecognised style, fails **closed** with a
`ConfigError`.

**Suggested rename (deterministic).** Each finding carries a suggested conformant name,
never applied to disk. The offending component is NFKD-folded with combining marks
dropped (so `café` transliterates to `cafe`), split into words at camelCase boundaries
and at every non-ASCII-alphanumeric run, lowercased **only** for ASCII letters (a
non-ASCII letter is a word boundary, never silently lowercased), and rejoined with the
style's separator; a component that yields no ASCII word (for example an all-Cyrillic
name) suggests the literal `document`, so the suggestion is always a valid, non-empty,
ASCII, conformant name. The suggestion is ASCII by construction; the **original**
offending name is echoed bounded and `unicode_escape`-ed, so a hostile path name carrying
`ESC`/newline/`::error`/RTL-override/`NUL` bytes can never reach a terminal, CI
annotation, or log unescaped.

**Reporting — once per component, per document.** Findings are produced in document
order; within a document the directory components are reported outermost-first, then the
file component, so `BadDocs/Quick_Start.md` yields exactly two findings (`BadDocs` then
`Quick_Start.md`). A directory name that repeats within one path (`a/a/x.md`) is reported
once for that document. A directory shared by many documents is reported **once per
document** under it, each attributed to that document's own path, so no document under a
badly named directory is silently omitted and the count stays linear. Every finding has
`line = None`, because the policy is over the path string, not the document body.

**Case-insensitive-filesystem caveat.** DS118 compares the path *bytes as committed* and
suggests a rename; it does **not** rename anything. On a case-insensitive filesystem
(macOS APFS/HFS+, Windows NTFS) a user cannot distinguish `Docs/` from `docs/` by a
case-only rename in place — applying a DS118 suggestion there may require a two-step
rename through a temporary name. Equally, DS118 never lowercases a path in place: it only
reports and suggests, leaving the rename (and its filesystem-specific mechanics) to the
author. Fixture names with spaces, uppercase, or non-ASCII characters are committed and
loaded verbatim; the repository relies on git's `core.precomposeunicode` to keep an
accented name in NFC, and the test suite does not depend on case-only differences between
sibling paths.

**No renames, no link rewrites.** DS118 reports pathname *format* only. `DS115` handles
deprecated names already present in prose or links; `DS101` reports any link broken by a
later user rename. DS118 never rewrites a link and never touches a file.
