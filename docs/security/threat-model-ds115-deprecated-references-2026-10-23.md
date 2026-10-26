# Threat Model - DS115 Deprecated names and migrated references - 2026-10-23

This is the standing, **pre-implementation** threat model for Story 13.0
(`DS115`, `fast` profile, default severity `warning`, **opt-in** via the
`deprecated_references_file` config option). It is normative input for every
Task 01/02/03 briefing and every reviewer of Story 13.0 and must be linked from
each. No `DS115` detector code exists yet (the proposed module is
`src/docsentinel/detectors/deprecated_refs.py`); the behaviour attributed below
to `config.py` (the committed `deprecated_*` options), `rules.py`
(`opt_in_satisfied`), `engine.py` (the opt-in notice), `cli.py`
(`Scan failed:`), `markdown_blocks.py` (the shared scanner and
`resolve_local_reference`), `detectors/path_boundaries.py`
(`is_ds116_owned`/`escapes_via_symlink`/`_echo`), and `detectors/navigation.py`
(the configured-file read discipline) was confirmed against the committed /
uncommitted-on-branch code, not assumed.

`DS115` loads a **user-configured TOML mapping file** of deprecated-name
`[[replacement]]` entries (old, new, kind, optional scope), then reports, inside
the scan root only, each in-scope textual occurrence of a mapped `old` token in
discovered Markdown, with the suggested `new` replacement and the mapping
provenance. A missing, unreadable, out-of-root, non-regular, or schema-invalid
mapping file is a **config/readiness error** (`ConfigError` -> exit 2), never a
silent clean result. DS115 is purely textual: beyond reading the one mapping
file and the already-discovered documents it performs **zero** filesystem access
- it never `stat`s, `open`s, resolves, or symlink-follows a deprecated link's
target (a deprecated path is flagged lexically whether or not it still exists -
Task 02 `deprecated_local_link_path`).

Two trust boundaries dominate this model. First, like DS112, DS115 is driven by
**attacker-controlled configuration**: in CI and pre-commit DocSentinel runs on a
contributor-controlled checkout, so `docsentinel.toml` /
`[tool.doc_sentinel]` (and therefore `deprecated_references_file`) and the mapping
file it names are untrusted - a PR author chooses *which file DS115 opens* and
*every byte of the mapping's `old`/`new`/`kind`/`scope` strings*. Second, unlike
DS112's index (which is a discovered `.md` document, so membership in `documents`
is a usable gate), the DS115 mapping is **TOML, not Markdown** - it is never
inventoried by `discovery.py`, so DS112's "member of the discovered `documents`"
check **cannot apply** and containment must be enforced another way (ruling R1).

Relevant identifiers: CWE-22/CWE-23/CWE-36 (path traversal), CWE-59 (link
following), CWE-400 with CWE-1333 (resource / regex DoS - FIFO, huge file,
quadratic match, ReDoS from compiling a user string as a pattern), CWE-20
(improper validation of config / mapping schema), CWE-1286 (improper validation
of syntactic correctness - bespoke/partial parsing), CWE-203 (observable
discrepancy / existence oracle), CWE-117 (log injection into `Scan failed:` and
report sinks), CWE-176/CWE-179 (improper Unicode/normalization handling),
CWE-178 (case handling), CWE-693 (protection-mechanism failure / scanner-mask
evasion), CWE-697 (incorrect comparison), and OWASP A01:2021 (Broken Access
Control), A05:2021 (Security Misconfiguration), A09:2021 (Security Logging).

The DS116 / DS113 / DS112 / DS114 standing floor applies unchanged and is relaxed
nowhere: filesystem containment, no existence oracle outside root, no opening of
non-regular / special files, decode-once, bounded repr-escaped echo
(`_MAX_ECHO = 80` + `unicode_escape`), no quadratic shapes, a bounded single
read, tokenizer/evasion parity with CommonMark masking (shared-scanner
requirement 16), fail-closed readiness errors, honest opt-in accounting, and the
injected-`Config`-bypasses-`load_config` defensive re-validation rule.

## Scope and method

In scope: the proposed analyzer `src/docsentinel/detectors/deprecated_refs.py`;
its read of the configured mapping file via `tomllib`; its use of the shared
scanner `scan_markdown` and the masked views it exposes
(`index.local_references`, `index.reference_definitions`, `index.reference_uses`,
`index.inline_code`, `index.comments`, and the `masked` text that blanks fenced
code / inline code / comments, `markdown_blocks.py:305-323`); the containment
helpers `is_ds116_owned` / `escapes_via_symlink` / `resolve_local_reference`
(`path_boundaries.py:206-354`, `markdown_blocks.py:1374-1442`); the committed
`deprecated_*` config options and their validation (`config.py:73-77,129-132,
301-304,597-602`, `_is_within_root:387-411`); the opt-in registration machinery
(`rules.opt_in_satisfied:50-80`, which already names `deprecated_references_file`)
and the engine notice (`engine.py:197-212`); the report sinks (`reporting.py`)
and the CLI `Scan failed:` path (`cli.py:229-231`). Method is STRIDE-lite over
three trust boundaries: untrusted **config** -> which file is opened; untrusted
**mapping-file content** -> schema, matcher, and echoed provenance; untrusted
**document content** -> what is matched and echoed.

Out of scope and recorded: repudiation and elevation have no DS115 surface
(local/CI CLI, no audit log, no auth, no automated remediation, no
`DOC_SENTINEL_PROD_CONFIRMED`-style action), consistent with the DS112/DS113/
DS114/DS116 models; supply chain is out of scope (stdlib-only `tomllib`, no
network, no execution of document or mapping content).

## Assets and trust boundaries

| Asset | Trust level | Why it matters |
|-------|-------------|----------------|
| `deprecated_references_file` config value | Hostile | In CI/pre-commit the config lives in the contributor-controlled tree; a PR author picks which file DS115 opens. `load_config` validates it only lexically (`_is_within_root`, `config.py:600`); an injected `Config` (library caller) bypasses that entirely. |
| Mapping-file content (`[[replacement]]` old/new/kind/scope, version) | Hostile | A contributor controls every byte: key names, value types, duplicate/conflicting/chained `old`s, empty/enormous strings, control/NUL bytes, regex metacharacters, Unicode confusables, entry count, glob patterns in `scope`. |
| `deprecated_check_prose` / `deprecated_check_links` / `deprecated_case_sensitive` sub-options | Semi-hostile | In-tree config toggles; not part of the opt-in gate; an injected `Config` can set non-bool values that bypass `load_config`. |
| Untrusted Markdown document content | Hostile | Authors control every token, link target, code span, and the structure the matcher scopes over. |
| Scan-root subtree | Trusted boundary | The only region DS115 may read: the one mapping file plus the already-discovered documents. Existence disclosure here is of the repo's own files and is not sensitive. |
| Filesystem outside the root | Off-limits | Must never be `open`-ed, `stat`-ed, `realpath`-ed, or symlink-followed by DS115 (the DS116 boundary). In particular DS115 must **not** probe deprecated link/path targets. |
| Special files inside the root (FIFO, device, socket, directory, huge file) | Hostile-adjacent | A mapping path pointing at a FIFO/device/directory must never be `open`-ed (hang / unbounded read); a huge regular mapping file must be size-capped before `tomllib.load` reads it whole. |
| Report sinks (text/json/github), CI logs, `Scan failed:` stderr | Semi-public | `finding.message` (old token + new + provenance) and the readiness `ConfigError` are rendered verbatim into CI logs and PR annotations; all three carry attacker-controlled strings (document token, mapping `old`/`new`, mapping path). |
| Pass/fail exit code (`0`/`1`/`2`) | Integrity/availability signal | `warning` severity blocks only under `--strict`; a readiness `ConfigError` is exit `2`. A false clean hides a prohibited term; a spurious `ConfigError` or quadratic match wedges the gate. |

Threat actors: a contributor who submits a crafted tree **and config/mapping**
that runs through CI or pre-commit (to open an out-of-root or special file, stall
the run with a huge file / quadratic matcher / ReDoS, inject log bytes, or wedge
the gate with a spurious error), and a reader of public CI logs harvesting any
host-path disclosure.

## Empirical grounding (confirmed against committed code)

- **The mapping file is not a discovered document.** `discovery.py` inventories
  `.md` files only; a `.toml` mapping never appears in `documents`. So the DS112
  membership gate (`_resolved_identity(...) in document_identities`,
  `navigation.py:558`) is inapplicable; DS115 must enforce containment by the
  lexical + stat path alone (R1).
- **Config validation of the path is lexical only and injected-`Config`-skippable.**
  `config.py:597-602` type-checks `deprecated_references_file` is a `str` and runs
  `_is_within_root` (`config.py:387-411`) which rejects leading `/`, backslashes,
  `A:` drive, and `..`-above-root **purely lexically with no filesystem access** -
  so a symlink pointing outside, a FIFO/device/directory, a non-TOML file, and a
  nonexistent path all pass load-time validation, and an **injected `Config`**
  skips even that. Same posture as DS112's `navigation_indexes` (its HIGH finding).
- **`opt_in_satisfied` already treats the string option as the gate.**
  `rules.py:50-80`: a non-empty `deprecated_references_file` reads as *on*, an empty
  string as *off*; the docstring names `deprecated_references_file` explicitly. So
  DS115 registers with `opt_in_option="deprecated_references_file"` exactly as DS110
  uses `require_fence_languages` and DS112 uses `navigation_indexes`.
- **The engine notice already handles it.** `engine.py:197-212` excludes an off
  opt-in rule from the evaluated count and names it; for DS115 it will read
  `DS115 (set deprecated_references_file)`. The engine does **not** catch analyzer
  exceptions, so a `ConfigError` raised by DS115 propagates out of `scan()`.
- **CLI maps the readiness error to exit 2 already.** `cli.py:229-231` wraps
  `scan()` in `except (ConfigError, ValueError, OSError)` -> `Scan failed: {exc}`
  -> returns **2**. (`tomllib.TOMLDecodeError` is a `ValueError` subclass and
  `UnicodeDecodeError` is a `ValueError` subclass, so both already route to exit 2 -
  but see R3 on re-wrapping them so the Python API honours the `ConfigError`
  contract and the raw message is bounded/escaped.)
- **The main-config loader already echoes a path + tomllib text into a message.**
  `config.py:436-440` builds `ConfigError(f"Cannot read {source}: {exc}")` - note
  it embeds both the absolute `source` path and the raw `tomllib` exception text.
  DS115 must **not** copy this pattern for the mapping file: `{source}` leaks the
  absolute host path and `{exc}` can echo offending content (R6).
- **The scanner exposes the masked views DS115 needs.** `inline_code`, `comments`,
  `local_references`, `reference_definitions`, `reference_uses`, and a `masked`
  text that blanks fenced code / inline code / HTML comments
  (`markdown_blocks.py:305-323`), the same substrate DS108/DS117/DS112 scope over.
- **The bounded echo helper exists.** `path_boundaries._echo`
  (`path_boundaries.py:341-354`) and the identical `navigation._echo` /
  `document_ids._echo`: bound to `_MAX_ECHO = 80` then `unicode_escape`. DS115
  reuses this discipline for every echoed string.
- **`resolve_local_reference` is lexical and never touches the FS**
  (`markdown_blocks.py:1374-1442`): a missing path is still `RESOLVED`; only a
  lexical `..` escape is `OUTSIDE_ROOT`. DS115 uses it only to normalize link
  targets for the `kind="link"` match and to re-validate the mapping path - never
  to prove existence.

## Threats (STRIDE findings)

Each lists vector, impact, and required control. "Matrix" marks a case covered by
the 14 Task 02 fixtures (6 CLEAN, 6 FINDING, 2 ERROR); "extra" marks a test the
implementer must add beyond the matrix.

### [HIGH] Config-injection: opening an out-of-root, special, or oversized mapping file

- Vector / evidence: `deprecated_references_file` is attacker-controlled in CI.
  Lexical config validation (`_is_within_root`, `config.py:600`) rejects
  `..`/absolute/drive/backslash but **not** a symlink that points outside, a
  FIFO/device/socket, a directory, a non-TOML file, or a path an injected `Config`
  never validated. A naive DS115 that does `tomllib.load(open(root / mapping, "rb"))`
  on the configured path would: open a FIFO and **hang the whole scan forever**
  (CWE-400); `tomllib.load` a multi-gigabyte in-root file (tomllib reads the whole
  stream - there is no built-in size limit) and exhaust memory (CWE-400); follow an
  in-root symlink to an out-of-root file and read it (CWE-22/CWE-59/CWE-203); or
  open a directory. The mapping is **not** in `documents`, so there is no discovery
  gate to lean on.
- Impact: one crafted PR config wedges every pre-commit/CI run, reads an
  out-of-root file, or exhausts memory - all before a single document is scanned.
- Mitigation (required, R1): before any open, re-validate the configured mapping
  path defensively because an injected `Config` bypassed `load_config`: confirm
  `is_ds116_owned(root, ".", mapping)` is false, `resolve_local_reference(root,
  ".", mapping).status is RESOLVED`, `escapes_via_symlink(root, root / mapping)` is
  false, then `os.stat` + `stat.S_ISREG` (never open a FIFO/device/socket/
  directory) **and** reject `st_size > _MAX_MAPPING_BYTES` *before* reading. Read a
  bounded byte count and parse with `tomllib.load` on that validated regular file
  (open in `"rb"`). Any failure is the readiness error of R3 - never a silent skip
  and never an open of an unvalidated path.
- Test case (matrix `mapping_path_outside_root` ERROR + extra syscall recorder):
  a configured mapping that is a runtime `os.mkfifo`, a runtime in-root symlink to
  an outside file, a directory, an oversized regular file, and a nonexistent path
  each complete promptly, perform **zero** `open()` on the special/outside/oversized
  path, and raise the readiness `ConfigError` (R3). Assert via a patched
  `os.open`/`builtins.open` counter and a `SIGALRM` guard.

### [HIGH] Readiness / schema error must fail closed, not fall through to clean

- Vector / evidence: Task 02 has two ERROR rows: `mapping_path_outside_root`
  (path escapes root) and `invalid_mapping_duplicate_key` (duplicate/conflicting
  `old`s). If DS115 treats a missing / unreadable / out-of-root mapping, a
  `tomllib` parse failure, or a schema violation as "no mapping -> no findings",
  the scan returns **zero findings** and the engine notice counts DS115 as
  "evaluated" - a false clean that hides both a broken policy and a
  misconfiguration (CWE-20, OWASP A05/A09). Task 03 point 5 and the story README
  forbid treating a dropped detector as a clean scan. Note `invalid_mapping_
  duplicate_key` is a **semantic** conflict: `[[replacement]]` is a TOML
  array-of-tables, so two entries with the same `old` are valid TOML - `tomllib`
  will *not* raise; DS115's own schema validator must (a literal duplicate key
  *within one* `[[replacement]]` table, e.g. two `old =`, is the only duplicate
  `tomllib` itself rejects).
- Impact: a typo, a deliberately broken mapping, or a conflicting entry silently
  disables the entire deprecated-term check while appearing green.
- Mitigation (required, R2/R3): a missing / unreadable / non-regular / out-of-root
  / oversized mapping path, a `tomllib` parse failure, a wrong top-level shape, an
  unknown/missing/mistyped key, an unsupported `kind`, an empty/oversized `old` or
  `new`, a duplicate-or-conflicting `old` (same old, or same old+scope, mapping to
  a different new), or more than `_MAX_ENTRIES` entries each raise `ConfigError`
  (a readiness error). The engine propagates it; the CLI maps it to exit **2** with
  `Scan failed: ...`; the Python API raises; the pytest test asserts the exception
  (not zero findings). No new exit code, no JSON schema v1 change. The whole scan
  fails closed - correct for an operator misconfiguration.
- Test case (matrix `invalid_mapping_duplicate_key`, `mapping_path_outside_root`):
  assert `ConfigError` (or the scan `pending`/failure state) from `scan`, CLI exit
  `2`, and that no clean empty-findings `ScanResult` is produced. Extra: a
  `tomllib`-unparseable mapping, a mapping with an unknown key, a wrong-typed `old`,
  an unsupported `kind`, and an over-`_MAX_ENTRIES` mapping each raise.

### [HIGH] Matcher DoS - ReDoS from user patterns, quadratic entries x tokens, catastrophic glob

- Vector / evidence: three distinct DoS surfaces. (a) **ReDoS (CWE-1333):** if
  DS115 ever compiles an `old` (or a `scope` glob) as a regular expression, a
  contributor supplies a catastrophic-backtracking pattern and stalls CI. (b)
  **Quadratic match (CWE-400):** a naive "for each of N entries, scan the whole
  document for the old" is O(entries x document bytes); with thousands of entries
  and large docs this blows up. (c) **Glob pathology:** `scope` globs translated
  through `fnmatch`/`translate` can embed many `*`/`?` producing slow matches, and
  per-token globbing multiplies it.
- Impact: a crafted mapping + corpus stalls every pre-commit/CI run; at
  super-linear cost a modest repo wedges the gate.
- Mitigation (required, R4): **`old` tokens are matched literally, NEVER compiled
  as a user regex.** For identifier/prose kinds, tokenize each masked line once
  with a fixed, repo-authored word regex (e.g. a bounded `[\w.\-/]+`-class pattern
  the project owns, not user input) and look each token up in a dict keyed on the
  normalized `old` (and, for multi-word/path-like olds, a dict keyed on the first
  token with a bounded literal tail compare) - O(document tokens + entries), never
  O(entries x tokens). Token boundaries must make `APIv1` not match inside `APIv10`
  (matrix `substring_of_longer_name`): compare whole tokens / use a boundary test,
  never `str.find`/substring. `scope` globs are matched against the document's
  relative POSIX path **once per document** with `fnmatch` on a **bounded** number
  of patterns (`_MAX_SCOPE_PATTERNS`), never per token; cache the compiled matcher.
  Bound entry count (`_MAX_ENTRIES`) and per-string length at schema load so no
  single field can drive an unbounded compare.
- Test case (extra timing, `tests/timing_helpers.assert_scales_linearly`): doubling
  series over (a) many mapping entries, (b) many document tokens / one very long
  line, and (c) many `old` occurrences, in CPU time, with fixed expected finding
  counts so the bound cannot pass vacuously. Extra: a mapping whose `old` is a
  regex-metacharacter string (e.g. `(a+)+$`, `.*`, `a{1,99999}`) is matched
  literally (zero spurious matches, no stall).

### [MEDIUM] Log injection / path disclosure through readiness error and finding messages

- Vector / evidence: the readiness `ConfigError` embeds the attacker-controlled
  mapping path, and every finding message embeds the matched old token, the
  suggested new, and the provenance (mapping path + entry index) - all
  attacker-influenced. `cli.py:230` prints the error verbatim to stderr/CI logs;
  `reporting.py` renders finding messages verbatim and its github `_escape_data`
  neutralises only `%`/CR/LF, not NUL/ESC or other C0/C1 bytes (CWE-117). A mapping
  path or an `old`/`new` carrying `\x1b]0;pwned\x07`, CR/LF, or NUL corrupts or
  spoofs a log line or injects a second `::error`/`::warning` command; echoing a
  resolved absolute path leaks host layout (CWE-203). The committed main-config
  loader's own `f"Cannot read {source}: {exc}"` (`config.py:439`) is exactly the
  anti-pattern to avoid: `{source}` is absolute and `{exc}` can echo offending
  content.
- Impact: control/ESC bytes corrupt or spoof CI log lines or inject annotations; a
  resolved absolute path or `tomllib` echo discloses host layout / mapping content.
- Mitigation (required, R6): both the readiness `ConfigError` and every finding
  message echo **only** bounded, repr-escaped strings via the shared `_echo`
  (bound `_MAX_ECHO`, then `unicode_escape`): the raw mapping path as configured
  (never the resolved absolute path), the raw matched token, and the raw suggested
  new. Provenance is the **configured** mapping path (echoed) plus the integer entry
  index (`[[replacement]]` position) - never an absolute path and never the raw
  `tomllib` exception text. Do not weaken the github newline/percent escaping. A
  `tomllib.TOMLDecodeError` is caught and re-raised as a DS115 `ConfigError` whose
  message names only the echoed configured path and a fixed "could not be parsed"
  phrase - the original `tomllib` message (which may echo content and gives
  line/col) is dropped or, at most, reduced to the line number.
- Test case (extra): a mapping path, an `old`, and a `new` each carrying
  NUL/ESC/CR/LF and 10,000-char length render under the bound with no raw control
  byte and no second github command line; assert the canonical root string and the
  raw `tomllib` message never appear in any message or `ConfigError`.

### [MEDIUM] Scanner-mask evasion - matching over unmasked source hides or over-flags

- Vector / evidence: DS115 must scope matches per `kind` - prose terms, Markdown
  link targets, path-like code spans - while **exempting** fenced code and the
  quoted historical/migration examples (matrix `deprecated_in_fenced_example`
  CLEAN, `historical_archive_exempt` CLEAN). If DS115 runs its own regex over
  **unmasked** source, a deprecated term inside a fence is wrongly flagged (false
  positive) or, conversely, a mask applied too broadly hides a live occurrence
  (false clean) (CWE-693). The fenced-example exemption must come from the
  scanner's mask, and the archive exemption from an explicit `scope`/path-exclude
  policy - **not** from date-guessing (story README task bullet 4).
- Impact: a false positive on a documented migration example (advisory noise) or a
  false clean on a live deprecated term; both erode the gate.
- Mitigation (required, R5): derive prose matches over the scanner's `masked` text
  (fenced code, inline code, HTML comments already blanked); derive code-span
  matches from `index.inline_code`; derive link matches from
  `index.local_references`/`reference_uses`/`reference_definitions`. The
  `deprecated_check_prose`/`deprecated_check_links` toggles select which of these
  substrates are scanned; inline-code matching is the `kind="identifier"`/code-span
  path. The historical-archive exemption is a `scope` glob / path exclude applied to
  the document's relative path, documented as policy, never a heuristic. Any
  construct DS115 treats as masked must be masked only where CommonMark hides it
  (requirement 16). No regex over unmasked source; no second Markdown parser.
- Test case (matrix `deprecated_in_fenced_example`, `historical_archive_exempt`,
  `deprecated_identifier_code_span` + extra markdown-it differential): a deprecated
  term in a fence is never flagged; the same term in an exempt archive path is never
  flagged; a mapped identifier in a real inline-code span is flagged.

### [MEDIUM] Mapping-schema bespoke-parsing divergence (false and hidden findings)

- Vector / evidence: DS115 hand-validates the `[[replacement]]` schema on top of
  `tomllib`. Divergences produce false or hidden findings (CWE-1286/CWE-20/CWE-697):
  **control characters / NUL / embedded newlines** in `old`/`new` (TOML basic
  strings can contain `\u0000`, `\n`) match against masked text in surprising ways;
  **Unicode normalization / confusables** - an `old` written NFD vs a document in
  NFC, or a Cyrillic look-alike, matches or misses depending on an undocumented
  normalization choice (CWE-176/CWE-179); **case sensitivity** - the gate is
  `deprecated_case_sensitive` (matrix `deprecated_case_sensitive` CLEAN,
  `deprecated_casefolded_optin` FINDING), and the comparison must pick exactly one
  policy; **chains / cycles** - `a->b, b->a` or `a->b->c` must not loop or
  re-apply (DS115 reports occurrences, it does not rewrite, so it reports `a` and
  `b` independently and never follows the chain); **empty / whitespace-only** `old`
  must be rejected at schema load (an empty old would match everywhere).
- Impact: a false `warning` on an unintended match, or a hidden miss of a genuine
  deprecated term; advisory severity bounds the blast radius but the gate still
  drifts.
- Mitigation (required, R2/R7): the schema validator rejects empty/whitespace-only
  `old`, over-length `old`/`new`, control/NUL characters in `old`/`new` (or defines
  and documents exactly how they are handled), unknown keys, missing required keys,
  wrong types, unsupported `kind`, and duplicate/conflicting `old`s, each as a
  `ConfigError`. Define **one** normalization policy for matching (recommended: NFC
  on both sides, matching the DS114 ruling; **no** NFKC/confusable folding) and
  document it. Case comparison is governed solely by `deprecated_case_sensitive`
  (casefold both sides when false). DS115 reports literal occurrences and **never**
  chases a chain or re-applies a replacement, so cycles are inert - document this.
- Test case (matrix `deprecated_case_sensitive`, `deprecated_casefolded_optin` +
  extra): a mapping with a cycle (`a->b,b->a`) reports each literal occurrence once
  and terminates; an empty `old` is a `ConfigError`; an NFC/NFD and a
  confusable-`old` differential pins the documented normalization policy.

### [MEDIUM] Opt-in honesty - gate is `deprecated_references_file` only

- Vector / evidence: `opt_in_satisfied` keys only on `deprecated_references_file`.
  If an operator sets the mapping file but turns `deprecated_check_prose` and
  `deprecated_check_links` both off, DS115 is counted "evaluated" in the engine
  notice although it can emit nothing. Conversely DS115 in `enabled_rules` with an
  empty `deprecated_references_file` must be named `DS115 (set
  deprecated_references_file)` and excluded from the evaluated count - it must not
  masquerade as an audited rule (contract D; matrix `unconfigured_mapping_is_inert`
  CLEAN). An unconfigured repo must flag an old-looking token **never** (the mapping
  is required - DS115 is not a universal obsolete-term heuristic).
- Impact: a mildly misleading "evaluated" count; the real risk is a disabled policy
  presented as audited.
- Mitigation (required, R8): the opt-in gate is `deprecated_references_file` only;
  `deprecated_check_prose`/`deprecated_check_links`/`deprecated_case_sensitive` are
  sub-options, not part of the gate, so DS115 is genuinely "evaluated" whenever a
  mapping is configured even if sub-checks are off. Empty `deprecated_references_file`
  makes DS115 not-applicable and it is named (not counted) in the notice, mirroring
  DS110/DS112. With no mapping, `detect` returns `()` and performs zero I/O.
- Test case (matrix `unconfigured_mapping_is_inert`): with no mapping, assert DS115
  registered, zero findings, zero file opens, and named not-applicable in the
  notice; with a mapping set, assert it is counted evaluated.

### [LOW] No filesystem probe of deprecated targets (confirm zero-FS discipline)

- Vector / evidence: a deprecated **link** path (matrix `deprecated_local_link_path`
  "even if it still exists") tempts DS115 into a `stat`/`exists` probe to decide
  whether to flag. Any such probe re-creates the DS101/DS103/DS116 existence oracle
  (CWE-203/CWE-22/CWE-59) and duplicates DS101's dangling-link job.
- Impact: an out-of-root existence oracle and double-reporting with DS101/DS103/
  DS113/DS116/DS108.
- Mitigation (required, R9): DS115 is **purely textual**. It matches the deprecated
  path token lexically (optionally normalized through `resolve_local_reference`
  purely for string identity, which does no FS access) and flags it **without any**
  `stat`/`open`/`realpath`/symlink-follow on the target. Existence is explicitly not
  DS115's concern (story README responsibility boundary: "DS101 checks existence; a
  legacy path can exist yet still be prohibited"). The only filesystem access DS115
  performs in the entire scan is the single bounded read of the validated mapping
  file. No double reporting: DS115 owns "explicitly mapped deprecated name", DS101
  owns existence, DS116 owns root escape (contract E) - collapse DS115's own
  duplicate `(line, message)` pairs.
- Test case (extra syscall recorder): over a hostile corpus (deprecated link to an
  in-root symlink-out, to `/etc/passwd`, to a nonexistent path), DS115 performs
  **zero** `stat`/`open`/`readlink` on any link target and still emits the lexical
  finding; the only `open` recorded is the mapping file.

### [LOW] Occurrence/line ordering determinism and multi-occurrence counting

- Vector / evidence: matrix `multiple_occurrences_same_line` and
  `obsolete_name_with_punctuation` require a defined, deterministic one-per-
  occurrence or one-per-line policy and correct boundary handling around
  punctuation. An undefined policy yields nondeterministic counts across runs
  (CWE-697 lite) and flaky `--strict` gates.
- Impact: nondeterministic finding counts; flaky tests / gate.
- Mitigation (required, R10): define and document one counting policy (recommended:
  one finding per distinct occurrence, ordered by `(path, line, column)`,
  deterministic across repeated scans and fresh roots) and collapse exact duplicate
  `(path, line, column, old)` tuples. Punctuation adjacency is governed by the token
  boundary of R4.
- Test case (matrix `multiple_occurrences_same_line`, `obsolete_name_with_punctuation`
  + extra repeated-scan stability): identical counts and ordering across two scans
  into two fresh roots.

### [INFO] Repudiation / Elevation - out of scope, recorded

DocSentinel is a local/CI CLI with no audit log, no authentication surface, and no
automated remediation; DS115 only reads and reports and modifies no source
(story README: "without modifying source automatically"). There is no production
action and therefore no `DOC_SENTINEL_PROD_CONFIRMED`-style guard to respect.
Consistent with the DS112/DS113/DS114/DS116 models, repudiation and elevation have
no DS115 surface.

## Required rulings (resolve before the 14 Task 02 fixtures freeze)

Record each in the DS115 rule docstring and `docs/dev/markdown_dialect.md` before
Task 02 freezes.

- **R1 - Mapping read discipline (no `documents` membership gate).** The mapping is
  TOML, not a discovered `.md` document, so DS112's "member of `documents`" check
  does not apply. Containment is enforced by, in order: `is_ds116_owned(root, ".",
  mapping)` false, `resolve_local_reference` `RESOLVED`, `escapes_via_symlink(root,
  root / mapping)` false, `os.stat` + `stat.S_ISREG`, and `st_size <=
  _MAX_MAPPING_BYTES` - all **before** a single `open`. The file is opened `"rb"`
  and parsed with `tomllib.load` on the validated regular file. Confirm this is the
  read path (vs any attempt to treat the mapping as a discovered document).

- **R2 - Schema contract.** Define the versioned schema: a top-level version field,
  an array-of-tables `[[replacement]]` with required `old` (nonempty, bounded
  length, no control/NUL or documented handling), required `new` (bounded), required
  `kind` from a closed enum (e.g. `prose`/`link`/`identifier`), optional `scope`
  (bounded list of globs). Reject unknown keys, missing required keys, wrong types,
  unsupported `kind`, empty/whitespace `old`, over-length strings, and
  duplicate/conflicting `old`s (the `invalid_mapping_duplicate_key` ERROR is a
  **semantic** cross-entry duplicate `tomllib` does not catch), and > `_MAX_ENTRIES`
  entries - each a `ConfigError`. Confirm the exact enum, the version-mismatch
  behaviour, and the duplicate/conflict definition (same `old`, or same
  `old`+`scope`).

- **R3 - Readiness-error surface and exit behaviour.** A missing / unreadable /
  non-regular / out-of-root / oversized mapping path, a `tomllib` parse failure, a
  non-UTF-8 read, or any R2 schema violation raises `ConfigError` (fail-closed),
  propagating through `engine.scan()` to CLI exit **2** (`Scan failed:`) and to a
  raised exception for the Python API / pytest. It is **not** a `Finding` and
  **not** a silent skip. Catch `tomllib.TOMLDecodeError`/`UnicodeDecodeError`/`OSError`
  and re-raise as a DS115 `ConfigError` so the Python API honours the contract and
  the message is bounded/escaped (R6) - do not let the raw `tomllib`/decode
  exception escape (it would still exit 2 via `cli.py` but diverges from the
  documented `ConfigError` surface and may echo content). No new exit code, no JSON
  schema v1 change. Confirm `ConfigError` is the surface.

- **R4 - Literal matcher, linear cost, token boundaries.** `old` tokens (and
  `scope` globs) are matched **literally** and are **never** compiled as a user
  regex (no ReDoS). Matching is O(document tokens + entries) via dict lookup keyed
  on the normalized `old` (first-token dict + bounded literal tail for multi-word /
  path-like olds), never O(entries x document bytes). Token boundaries make `APIv1`
  not match inside `APIv10`. `scope` globs match the document's relative POSIX path
  once per document on a bounded pattern count with `fnmatch`, never per token.
  Entry count and per-string length are bounded at schema load. Confirm the
  tokenization regex is repo-authored (never user input) and the exact boundary
  rule.

- **R5 - Scope and masking.** Prose matches run over the scanner's `masked` text;
  code-span matches over `index.inline_code`; link matches over
  `index.local_references`/`reference_uses`/`reference_definitions`. Fenced code,
  inline code, and HTML comments are exempt via the scanner mask; the historical/
  archive exemption is an explicit `scope` glob / path exclude, never date-guessing.
  `deprecated_check_prose`/`deprecated_check_links` select substrates. No regex over
  unmasked source; no second Markdown parser (requirement 16). Confirm the substrate
  per `kind` and that `deprecated_in_fenced_example` and `historical_archive_exempt`
  stay CLEAN.

- **R6 - Bounded repr-escaped echo, no path/content disclosure.** The readiness
  `ConfigError` and every finding message echo only bounded, `unicode_escape`-ed
  strings via the shared `_echo`: the raw **configured** mapping path (never
  resolved absolute), the raw matched token, and the raw suggested new. Provenance
  is the configured path plus the integer entry index; the raw `tomllib` exception
  text is dropped (at most a line number). Do not weaken the github newline/percent
  escaping. Confirm no absolute path, no neighbour existence, no file type, no raw
  `tomllib` text reaches any sink.

- **R7 - Normalization and case policy.** Define **one** matching normalization
  (recommended NFC on both sides, mirroring DS114; no NFKC / confusable folding) and
  document it. Case sensitivity is governed solely by `deprecated_case_sensitive`
  (casefold both sides when false). DS115 reports literal occurrences and never
  chases a replacement chain or re-applies a replacement, so cycles are inert.
  Confirm the normalization choice and the chain/cycle non-behaviour.

- **R8 - Opt-in accounting.** The gate is `deprecated_references_file` only;
  `deprecated_check_prose`/`deprecated_check_links`/`deprecated_case_sensitive` are
  sub-options, not part of the gate. DS115 is "evaluated" whenever a mapping is
  configured even if sub-checks are off; empty `deprecated_references_file` makes
  DS115 not-applicable and it is named `DS115 (set deprecated_references_file)` (not
  counted) in the engine notice, mirroring DS110/DS112; `detect` returns `()` with
  zero I/O when unset. Confirm.

- **R9 - Zero filesystem probe of targets.** DS115's only filesystem access in the
  whole scan is the single bounded read of the validated mapping file. Deprecated
  link/path tokens are matched and flagged lexically with **zero** `stat`/`open`/
  `realpath`/symlink-follow on the target; existence is DS101's concern, root escape
  DS116's (documented overlap, contract E). Confirm the zero-FS-probe discipline and
  that `resolve_local_reference` is used only for string identity (no FS access).

- **R10 - Occurrence counting and determinism.** Define one counting policy
  (recommended: one finding per distinct occurrence, ordered by `(path, line,
  column)`, stable across repeated scans and fresh roots) and collapse exact
  duplicate tuples. Confirm the per-occurrence-vs-per-line choice named in
  `multiple_occurrences_same_line`.

## Merge-gate BLOCK conditions (any one ships => BLOCK, keep out of `master`)

- DS115 `open`s / `stat`s / `realpath`s / `resolve`s / symlink-follows any path that
  resolves **outside** the canonical root (via the configured mapping path or a
  deprecated target), or probes the existence of any deprecated link/path target
  (re-introducing the DS101/DS103/DS116 oracle).
- DS115 `open`s a configured mapping that is **not** a validated in-root regular file
  - in particular a FIFO/device/socket (hang/unbounded read), a directory, or an
  oversized file read whole into memory (no `_MAX_MAPPING_BYTES` cap before
  `tomllib.load`).
- A missing / unreadable / out-of-root / unparseable / schema-invalid mapping yields
  a **clean** scan with empty findings (false clean) instead of the R3 readiness
  `ConfigError`; or the `invalid_mapping_duplicate_key` conflict is silently
  accepted.
- DS115 compiles any `old` or `scope` value as a regular expression (ReDoS), or is
  super-linear (O(entries x document bytes), per-token globbing, or an unbounded
  entry/line flood).
- DS115 echoes a resolved absolute path, a neighbouring path's existence, a file
  type, or the raw `tomllib` exception text into any report sink or the `Scan
  failed:` line, or leaves control/ESC bytes un-escaped in a message or `ConfigError`.
- DS115 adds a second path resolver, a third-party Markdown or TOML parser (beyond
  stdlib `tomllib`), a regex over **unmasked** source, a network call, any execution
  of document or mapping content, or modifies source files.

## Standing requirements checklist (apply to every Story 13.0 task and review)

1. **Opt-in registration.** Register `DS115` exactly once in `RULES` and
   `ANALYZERS`, `fast` profile, severity `warning`, with
   `opt_in_option="deprecated_references_file"`; selectable via `select`/`ignore`,
   honouring baseline; CLI `rules` tags it `[opt-in: set deprecated_references_file]`,
   `doctor` counts it among opt-in rules, and the engine notice names it when unset.
   Stdlib-only import graph (incl. `tomllib`); passes the fast-only import isolation
   test (no spacy/textacy/sklearn/docsig/network on the fast path).
   **Test obligation:** registry/CLI `rules`/`doctor`/select/ignore/baseline tests;
   fast-import-isolation test.
2. **Config-injection containment (R1).** Re-validate the configured mapping path
   defensively (`is_ds116_owned` false, resolver `RESOLVED`, `escapes_via_symlink`
   false, `os.stat` + `S_ISREG`, `st_size <= _MAX_MAPPING_BYTES`) before any open,
   because an injected `Config` bypasses `load_config`. Open `"rb"`, bounded.
   **Test obligation:** syscall recorder + `SIGALRM` guard proving zero `open()` on a
   runtime FIFO / symlink-out / directory / oversized / nonexistent configured
   mapping, each raising the readiness error.
3. **Fail-closed readiness / schema error (R2/R3).** Missing / unreadable /
   non-regular / out-of-root / oversized / unparseable / schema-invalid mapping
   raises `ConfigError` -> engine propagation -> CLI exit 2 / API exception; never a
   clean empty-findings scan; no JSON schema or exit-code change; `tomllib`/decode
   exceptions re-wrapped as bounded/escaped `ConfigError`.
   **Test obligation:** `invalid_mapping_duplicate_key` and `mapping_path_outside_root`
   assert the exception / exit 2; extra tests for parse failure, unknown key, wrong
   type, bad `kind`, over-`_MAX_ENTRIES`, and non-UTF-8.
4. **Literal matcher, linear cost, token boundaries (R4).** `old`/`scope` matched
   literally (never compiled as a user regex); O(document tokens + entries) via dict
   lookup; `APIv1` not inside `APIv10`; globs matched per document on a bounded
   pattern count; entry count and string length bounded at load.
   **Test obligation:** `assert_scales_linearly` doubling series (many entries, long
   line, many occurrences) with fixed finding counts; a regex-metacharacter `old`
   matched literally with no stall; `substring_of_longer_name` CLEAN.
5. **Scope and masking (R5).** Prose over `masked` text; code spans over
   `inline_code`; links over `local_references`/reference views; fence/inline-code/
   comment exemption from the scanner mask; archive exemption via explicit `scope`/
   path exclude; no regex over unmasked source; no second Markdown parser.
   **Test obligation:** `deprecated_in_fenced_example` / `historical_archive_exempt`
   CLEAN, `deprecated_identifier_code_span` FINDING, plus a markdown-it scratch
   differential over fence/inline/prose/link cases.
6. **Bounded, repr-escaped echo (R6).** Readiness error and finding messages echo
   only bounded `unicode_escape`-ed configured path / token / new; provenance =
   configured path + entry index; no absolute path, neighbour existence, file type,
   or raw `tomllib` text; github newline/percent escaping preserved.
   **Test obligation:** NUL/ESC/CR/LF and 10,000-char mapping path, `old`, and `new`
   render under the bound with no raw control byte and no injected github command;
   canonical root string and raw `tomllib` text never appear.
7. **Zero filesystem probe of targets (R9).** The only scan-time filesystem access
   is the one bounded mapping read; deprecated targets are matched lexically with no
   `stat`/`open`/`realpath`/symlink-follow; no double reporting with DS101/DS103/
   DS113/DS116/DS108 (duplicate `(path,line,message)` collapsed).
   **Test obligation:** syscall recorder over a hostile corpus proving zero target
   `stat`/`open` while still emitting the lexical link/path finding
   (`deprecated_local_link_path`).
8. **Normalization, case, chains (R7).** One documented normalization (NFC, no
   NFKC/confusable folding); case governed solely by `deprecated_case_sensitive`;
   literal-occurrence reporting that never chases or re-applies a chain (cycles
   inert).
   **Test obligation:** `deprecated_case_sensitive` CLEAN,
   `deprecated_casefolded_optin` FINDING, plus an NFC/NFD / confusable differential
   and an `a->b,b->a` cycle test (terminates, one finding per literal occurrence).
9. **Opt-in honesty (R8).** Gate is `deprecated_references_file` only; sub-options
   are not part of the gate; DS115 named-not-counted when unset; zero I/O when unset;
   never a universal obsolete-term heuristic without a mapping.
   **Test obligation:** `unconfigured_mapping_is_inert` CLEAN with zero opens and the
   named-not-applicable notice; evaluated-count check with a mapping set.
10. **Occurrence determinism (R10).** Defined one-per-occurrence (or one-per-line)
    policy, `(path, line, column)` ordering, stable across repeated scans / fresh
    roots, exact-duplicate tuples collapsed.
    **Test obligation:** `multiple_occurrences_same_line`,
    `obsolete_name_with_punctuation`, plus a repeated-scan / two-fresh-roots
    stability assertion.
11. **No regressions.** DS101-DS103 and the shipped M5 fast rules (DS104-DS110,
    DS112-DS114, DS116, DS117) stay green - especially source line offsets, escape
    handling, root resolution, and scanner masking; no baseline edit to make
    self-scan green; `tests/assets/ds115` excluded from self-scan and formatters;
    intentionally broken fixtures kept byte-for-byte.
    **Test obligation:** full fast-suite regression; self-scan clean without a
    baseline change; catalog manifest lists all 14 rows (6 CLEAN / 6 FINDING /
    2 ERROR) with matching slugs.
12. **No network, no execution, no content transmission, no source mutation.** Never
    execute/import/fetch document or mapping content; stdlib `tomllib` only; DS115
    modifies no source file.
    **Test obligation:** fast-import-isolation / no-network assertion in Task 03.

## Verdict on default severity `warning` + opt-in design

**The `warning` + opt-in posture is correct and should stand** - it is the DS112
posture, strictly safer than DS113/DS114/DS116 `error` default-on:

- Opt-in (empty `deprecated_references_file` by default) gives DS115 **zero**
  default-on attack surface: on an unconfigured repo it opens nothing, matches
  nothing, and is honestly reported as not-applicable. The config-injection surface
  (the HIGH finding) exists only once an operator opts in - except in CI, where the
  config and mapping are still attacker-controlled, which is exactly why R1's
  defensive re-validation and R3's fail-closed readiness error are mandatory even
  under opt-in.
- `warning` severity means an in-scope finding blocks the merge only under
  `--strict`, so a false positive (e.g. a punctuation / normalization edge) is an
  advisory, not a hard merge-gate DoS. `select`/`ignore` + baseline give the
  operator the downgrade path. **No** off/warn/error severity knob is required for
  DS115 (unlike DS113/DS116), and - unlike DS114 - DS115 fires only on explicitly
  mapped terms, so its false-positive blast radius is operator-scoped by the mapping
  itself.
- The one non-advisory outcome - the readiness `ConfigError` (exit 2) - is correct
  and intended: a misconfigured or conflicting deprecated-term policy must fail
  closed, not pass green.

## Verdict: PASS_WITH_FOLLOWUP

No CRITICAL exists because no `DS115` detector code is written yet; this is the
pre-code standing model. The spec is sufficient to begin **provided** the standing
requirements above are met and rulings **R1-R10** are recorded before the Task 02
fixtures freeze. The `warning` + opt-in design is endorsed and must not be
escalated to `error` default-on.

**DS115 must be documented as a best-effort, explainable deprecated-term guard over
a narrow TOML mapping and the shared-scanner masked view - not a complete migration
or terminology control:** it inherits every shared-scanner false negative
(multi-line / nested-paren link destinations, multi-line HTML tags, unquoted
attributes, shortcut references) plus the documented normalization/case policy and
the literal-match token-boundary rule, and it deliberately performs no existence or
target validation (that is DS101's / DS116's job).

Fix handoff: the `deprecated_refs.py` analyzer, the bounded/validated `tomllib`
read, the literal linear matcher, and the masked-text scoping go to
`python-expert`; the syscall-recorder / runtime-FIFO-symlink / oversized-file /
markdown-it differential / normalization / ReDoS-literal / flood-slope /
readiness-error regression tests go to `testing-expert`.

## Security review findings - Story 13.0 DS115 - 2026-10-23

Post-implementation adversarial review of the uncommitted
`src/docsentinel/detectors/deprecated_refs.py` (branch
`milestone/0005-deepening-test-case-stage-2`) against the standing floor, R1-R10,
and the merge-gate BLOCK conditions above. Attack scripts and PoC output are in the
session scratchpad. Most of the floor holds and is confirmed below; three
implementation defects break it, two of them tripping stated BLOCK conditions.

### What holds (confirmed against the code)

- **R1 config-injection containment.** `load_mapping` (`deprecated_refs.py:781-819`)
  re-validates the configured path *before any open*: `is_ds116_owned` (rejects
  OUTSIDE_ROOT + drive/unc/backslash/control), then `resolve_local_reference`
  RESOLVED (rejects EXTERNAL `//`/scheme and UNSUPPORTED glob/template/empty), then
  `escapes_via_symlink` (in-root symlink-out), then `os.stat` + `stat.S_ISREG`
  (FIFO/device/socket/directory never opened), then `st_size <= _MAX_MAPPING_BYTES`,
  then an `"rb"` open with a bounded `read(_MAX_MAPPING_BYTES)`. The percent/HTML-entity
  decode in the resolver only *adds* `..`/scheme classification, so no raw-vs-decoded
  divergence lets an out-of-root or special file reach `os.stat`/`open`. The mock
  oracle suite (`tests/mock/test_detectors_deprecated_oracle.py`) proves zero
  out-of-root access, open-set == {mapping, document}, and a FIFO mapping never
  opened. **No finding.**
- **R9 zero target probe.** `_link_occurrences` matches link targets lexically with
  no `stat`/`open`/`realpath`/`readlink`; the only scan-time FS access is the one
  mapping read plus the discovered documents. **No finding.**
- **R4 ReDoS / literal matcher.** `old`/`scope` are never compiled as a user regex;
  the sole regex is the repo-authored `_TOKEN_RE`. A metacharacter `old` such as
  `(a+)+$` is matched literally with no stall (verified). **No finding on ReDoS.**
- **R2/R3 schema fail-closed, R5 masking, R6 echo of old/new/path, R7 NFC+case,
  R8 opt-in gate, R10 determinism** are implemented as specified and are not the
  subject of a finding except where noted below. The two ERROR fixtures
  (`mapping_path_outside_root`, `invalid_mapping_duplicate_key`) raise `ConfigError`;
  the cross-entry semantic-conflict check (`_build_replacement:774-777`) is present.

### [HIGH] Unescaped, unbounded attacker TOML key names in schema `ConfigError` (BLOCK)

- Vector / evidence: `parse_mapping` (`deprecated_refs.py:725-727`) and
  `_build_replacement` (`deprecated_refs.py:765-767`) build their "unknown
  top-level keys" / "unknown keys" `ConfigError` messages with
  `', '.join(sorted(unknown))`, where `unknown` is a set of **attacker-controlled
  TOML key names** - and these two messages bypass `_echo` entirely (every other
  message in the module routes author strings through the bounded, `unicode_escape`
  helper). TOML quoted keys accept `\u` escapes, so a mapping key like
  `"\u001b]0;PWNED\u0007 ..."` or `"real\ndeprecated mapping entry 0 is fine"`
  injects raw `ESC`/`BEL`/`CR`/`LF`/`NUL` bytes, unbounded in length. PoC output:
  a 300+-char key produced a 378-char `ConfigError` containing raw `0x1b` and `0x07`;
  a newline key produced a forged second log line.
- Impact: this `ConfigError` propagates through `engine.scan()` to
  `cli.py` `Scan failed: {exc}`, printed verbatim to stderr / CI logs / PR
  annotations - ANSI terminal-escape injection, CI-log-line spoofing, and an
  unbounded log flood (CWE-117), from a file a PR author fully controls in CI.
- This trips **BLOCK condition #5** ("leaves control/ESC bytes un-escaped in a
  message or `ConfigError`") and violates **R6**.
- Mitigation (python-expert): echo each offending key through the existing `_echo`
  (bound `_MAX_ECHO`, `unicode_escape`) and cap the joined count, e.g.
  `', '.join(_echo(key) for key in sorted(unknown)[:N])`; do the same for any future
  message that embeds a TOML key or value. Regression test (testing-expert): a
  mapping with an unknown top-level key *and* an unknown entry key each carrying
  NUL/ESC/CR/LF and 10,000-char length raises a `ConfigError` whose text contains no
  raw control byte and stays under the echo bound.

### [HIGH] Matcher is O(entries x document tokens) via shared first-token bucket (BLOCK)

- Vector / evidence: `_MatchIndex.__init__` (`deprecated_refs.py:324-329`) buckets
  every entry solely by its **normalized first token** (`tokens[0]`); `_match_unit`
  (`deprecated_refs.py:419-425`) then iterates *all* candidates in that bucket for
  every document token that equals the bucket key. For multi-word `old` values
  (whitespace-separated - path-like dotted/slashed olds collapse to one token and do
  not amplify) a contributor can fill one bucket: 5000 entries (`_MAX_ENTRIES`) of
  `old = "aaaa z{i}"` all land under first-token `aaaa`. A document that is just a
  long run of the token `aaaa` then costs `document_tokens x 5000` tail compares,
  and documents are **not** size-capped (discovery reads the whole file). Measured
  (PoC `poc_dos2.py`): with 5000 same-first-token entries, a prose document of
  1000/2000/4000/8000 `aaaa` tokens took 2.6 / 5.7 / 11.3 / 22.7 s with **zero**
  findings - clean linear scaling in document tokens multiplied by the 5000x bucket
  constant. A ~350 KB document (approx 100k tokens, entirely normal) extrapolates to
  approx 280 s, wedging every pre-commit / CI run.
- Impact: a crafted 5000-entry mapping plus one modest document stalls CI for
  minutes with no finding to show for it (CWE-400) - exactly the quadratic shape R4
  forbids.
- This trips **BLOCK condition #4** ("super-linear ... O(entries x document bytes)")
  and violates **R4**'s required "O(document tokens + entries), never O(entries x
  tokens)".
- Mitigation (python-expert): key the multi-token index on more than the first
  token (e.g. a `(first_token, second_token)` or `(first_token, token_count)`
  secondary dict), or cap per-bucket candidates, so a single document token cannot
  fan out to `_MAX_ENTRIES` tail compares. Keep single-token olds as the existing
  O(1) dict lookup.
- Test-gate integrity (see below): the committed R4 scaling tests do **not** catch
  this.

### [MEDIUM] Uncaught `RecursionError` from deeply nested TOML (R3 fail-closed-cleanly)

- Vector / evidence: `parse_mapping` (`deprecated_refs.py:720-723`) catches only
  `tomllib.TOMLDecodeError`. A deeply nested TOML array value (`x = [[[...]]]`)
  drives tomllib's recursive-descent parser into a `RecursionError`, which is a
  `RuntimeError` - not a `TOMLDecodeError`, `ValueError`, or `OSError`. PoC
  (`poc_recur.py`): a ~100 KB mapping (50,000 nested brackets, well under the 1 MB
  `_MAX_MAPPING_BYTES` cap, so the size guard never fires) raises an uncaught
  `RecursionError` that escapes `parse_mapping` -> `detect` -> `scan()`. `cli.py`
  catches only `(ConfigError, ValueError, OSError)`, so the CLI terminates with a raw
  traceback instead of the documented bounded `ConfigError` -> exit 2, and the
  traceback discloses internal module paths / stack (minor CWE-209 info leak).
- Impact: a crafted in-cap mapping yields an uncaught crash + traceback rather than
  the R3 fail-closed readiness error; violates R3's "do not let the raw exception
  escape ... re-raise as a DS115 `ConfigError`".
- Mitigation (python-expert): broaden the `parse_mapping` guard to also catch
  `RecursionError` (and, defensively, `ValueError`) and re-raise the same bounded
  `ConfigError` naming only the echoed configured path. Test (testing-expert): a
  deeply nested TOML mapping under the size cap raises `ConfigError`, not
  `RecursionError`, and routes to CLI exit 2.

### [LOW] Prose mask omits indented code blocks and HTML blocks (R5 parity, false positive)

- Vector / evidence: `_masked_text` (`deprecated_refs.py:490`) blanks only
  `index.fences`, `index.comments`, and `index.inline_code`. A 4-space **indented
  code block** and an **HTML block** are not masked, so a `kind="prose"` term inside
  them is reported though a CommonMark renderer shows it as code/markup, not live
  prose. PoC (`poc_mask.py`): `oldname` in an indented code block and in an HTML
  block each produced one finding; the fenced-code control correctly produced zero.
- Impact: advisory-severity false positives on documented code/markup; bounded by
  `warning` + `select`/`ignore`/baseline, and adjacent to the module's own
  "inherited shared-scanner" disclosure - but that docstring lists only false
  *negatives*, not this false *positive*.
- Mitigation: either extend the mask to the scanner's indented-code / HTML-block
  spans if available, or document the indented-code / HTML-block false positive
  explicitly in the rule docstring and `docs/dev/markdown_dialect.md`. Not a BLOCK.

### [INFO] Test-gate integrity - R4 scaling tests pass vacuously against the HIGH matcher DoS

- The R4 linear-scaling gate does not exercise the shared-first-token vector.
  `tests/integration/...ds115.py:_single_line_flood`/`_multi_line_flood`
  (lines 1597/1606) and the three unit scaling tests
  (`tests/unit/test_detectors_deprecated.py:898/932/964`) all use strictly
  **distinct** tokens (`obso{i}`, `term{i}`, `w{i}`) or a single mapped token, so
  every first-token bucket holds exactly one entry and the tests run the genuine
  O(tokens + entries) path while never materialising the many-entries-sharing-one-
  first-token amplification. The gate therefore passes green against the HIGH DoS
  above. Remediation must add a scaling test whose mapping places `scale` multi-word
  entries under one shared first token with a document saturated with that token, so
  the slope assertion actually bounds the bucket fan-out. No test weakens an ERROR
  or masking gate; the 14-row catalog (6 CLEAN / 6 FINDING / 2 ERROR) and the oracle
  suite are intact.

### Verdict on `warning` + opt-in: ENDORSED, unchanged

The `warning` + opt-in posture remains correct and must stand - it is the strictly
safer DS112 posture and gives DS115 zero default-on attack surface on an
unconfigured repo. The two HIGH findings are **implementation defects, not a flaw in
the severity design**: they do not become less severe by lowering severity (they are
a `ConfigError`/exit-2 log-injection and a pre-finding CPU stall, both independent of
whether a resulting finding would block), and they do not justify escalating to
`error` default-on. Do **not** change the severity contract to address them; fix the
code.

### Review verdict: BLOCK

Two findings trip stated merge-gate BLOCK conditions (#5 unescaped control/ESC bytes
in a `ConfigError`; #4 super-linear O(entries x document bytes) matcher). **Keep DS115
out of `master`** until both HIGH findings are fixed and regression-tested; the
MEDIUM `RecursionError` R3 gap and the LOW mask-parity gap should ride the same fix.
Hand the matcher-index and echo/guard fixes to `python-expert`; hand the
control-byte-echo, shared-first-token-scaling, nested-TOML, and indented-code
regression tests to `testing-expert`.

### Re-audit after fixes - Story 13.0 DS115 - 2026-10-23

Independent re-verification of the uncommitted fixes in
`src/docsentinel/detectors/deprecated_refs.py` (`_echo_keys`, `_MAX_LISTED_KEYS`,
the `_TrieNode`/`_MatchIndex`/`_match_unit` token trie, and the
`parse_mapping` guard widened to `RecursionError`/`ValueError`). All PoCs were
re-written from scratch for this pass (not the implementer's); scripts and raw
output are in the session scratchpad (`poc_echo.py`, `poc_matcher.py`,
`poc_mem2.py`, `poc_sem.py`, `poc_gate.py`, `poc_nested.py`). The full suite was
not run (out of scope for this pass). No product code or other docs were edited.

**(1) Echo / bounding of every attacker-influenced message string - PASS.** I
grepped every `raise ConfigError`/`Finding` message in the module and exercised each
with hostile input: unknown top-level keys, unknown entry keys, and hostile `[table]`
names (all -> `_echo_keys`); hostile `kind`/`version`/`scope`/`old`/`new` values; a
`tomllib` parse error with a hostile configured path; and a `Finding` message built
over a hostile `new` + configured path. Each offending key/value carried decoded
`ESC`/`BEL`/`CR`/`LF`/`NUL`/`NEL`(U+0085)/C1(U+009B)/`RTL`(U+202E)/`DEL`(0x7F) bytes and
a 100,000-char padding. Result: 12/12 messages contained **zero** raw control bytes
(all rendered as printable `\xNN`/`\uNNNN` via `unicode_escape`, including `DEL` ->
`\x7f`) and every message stayed bounded (longest 250 chars; the 5000-key flood
collapsed to `k0, k1, k10, k100, k1000, ... 4995 more`). The two schema messages the
prior review flagged (`parse_mapping` unknown top-level keys, `_build_replacement`
unknown entry keys) now route through `_echo_keys` (bounded `_echo` per key + a
capped `... N more` tail). The `missing keys` join (line 809) is safe because its
values are the repo-owned `_REQUIRED_ENTRY_KEYS`, never attacker input; the
`kind must be one of ...` join lists the repo-owned enum, not the attacker's value.
CLI/JSON/github sinks cannot be injected: finding messages embed only
schema-validated (control-free, <=500-char) `old`/`new` plus the `_echo`-ed configured
path, so no raw `CR`/`LF`/`%` ever reaches `reporting._escape_data`, and that github
escaping is preserved. **BLOCK condition #5 resolved.**

**(2) Matcher - PASS.** The sole regex is the repo-authored `_TOKEN_RE`; no `old`/
`scope` is ever compiled as a user pattern (ReDoS surface closed). Adversarial trie
shapes all stayed linear and finding-count-exact: (a) the original 5000-entry
shared-first-token bucket + a 100,000-`aaaa` document completed in 0.47 s with 0
findings (vs the prior review's ~22 s at 8k and ~280 s extrapolation); (b) 5000 olds
sharing a 49-token prefix and differing only at token 50 scaled linearly in document
length (0.56 s -> 1.00 s on a 2x doubling), i.e. cost is O(document tokens x longest
old in tokens) and **independent of entry count**; (c) 100 nested-prefix olds
(`w0`, `w0 w1`, ...) over a 297,000-token line produced 297,000 findings in 3.8 s -
output-bound, not entry-bound; (d) single-token `aaaa` over 400,000 tokens stayed
linear; (f) 404-char single-token olds and (g) 10,000 entries (cap raised) stayed
linear. Equivalence with the documented semantics was re-pinned: `APIv1` does not
match inside `APIv10`; `old module` matches `old module` but not `old, module` nor a
line-split phrase; casefold honours `deprecated_case_sensitive`; NFC matches, NFD-doc
is the documented best-effort miss; punctuation adjacency, multi-occurrence counting,
`link`/`identifier` substrate scoping and fenced-exempt all behaved as specified.
**BLOCK condition #4 resolved.**

Memory of the trie is bounded and the two caps that bound it were verified. The
absolute pathological shape (5000 x 83 distinct 5-char tokens) peaks ~142 MB / 415k
nodes - but expressing it needs a ~2.6 MB mapping file, which `load_mapping`'s
`_MAX_MAPPING_BYTES = 1_000_000` rejects *before* parse. The true node-maximising
mapping that fits under the 1 MB file cap builds a ~42 MB / 121k-node trie (3,039
entries) - comparable to loading a 1 MB file into Python objects, bounded, not a DoS.
This is a new (modest) memory cost the first-token bucket did not have; it is
acceptable and is noted as informational, not blocking.

**(3) Nested / pathological TOML - PASS.** 50,000-deep nested arrays, 20,000-deep
nested inline tables, 5,000 dotted keys, a ~1 MB flat int array, a near-1-MB nesting,
and nesting inside a `[[replacement]]` value each raised the bounded readiness
`ConfigError` (`could not be parsed` / `unknown top-level keys`) - **no** uncaught
`RecursionError`, `ValueError`, or `MemoryError` escaped. End to end through the CLI,
a 50,000-deep-array mapping produced `Scan failed: deprecated references mapping could
not be parsed: map.toml` and **exit 2** with no traceback. The widened
`except (TOMLDecodeError, ValueError, RecursionError)` closes the prior
`RecursionError` gap. (TOML has no reference/expansion grammar, so no small-input
`MemoryError` amplification exists.) **MEDIUM resolved.**

**(4) LOW indented-code / HTML-block prose-mask false positive - ACCEPTED.** The
direction is documented in the rule docstring (`deprecated_refs.py:124-130`) and in
`docs/dev/markdown_dialect.md` (the DS115 section, "one false-positive direction"),
and pinned by `test_prose_in_indented_code_block_is_a_documented_false_positive`. At
`warning` severity + opt-in, downgradable via `select`/`ignore`/baseline, a
false positive on a documented code/markup example is advisory, not a merge-gate DoS.
Acceptable as documented; no change required.

**(5) Test-gate integrity - PASS.** The new `test_matching_scales_linearly_with_
shared_first_token_on_one_line` / `..._across_lines` build `size` multi-word olds
sharing one first token with a document saturated by that token - exactly the HIGH #4
vector - and assert `expected_count=1` so the pass is non-vacuous. I confirmed the
gate bites: the current trie runs that shape at log-log slope **0.16** (well under the
1.4 `DEFAULT_SLOPE_LIMIT`), while a scratch reimplementation of the pre-fix
first-token bucket (per-entry tail compare) on the identical shape fails the same
helper at slope **2.09** (per-doubling ~4x: 0.07/0.30/1.38/5.36 s). No ERROR or
masking gate was weakened; the 14-row catalog (6 CLEAN / 6 FINDING / 2 ERROR) and the
oracle suite remain intact.

**(6) Earlier BLOCK-condition re-run:**

- #1 (open/stat/realpath/symlink-follow outside root, or existence oracle): PASS -
  unchanged by these fixes; `load_mapping` re-validates before any open and
  `_link_occurrences` is lexical (confirmed in the prior pass, not regressed here).
- #2 (open a non-regular / FIFO / directory / oversized mapping): PASS - the
  `is_ds116_owned` -> resolver -> `escapes_via_symlink` -> `S_ISREG` -> `st_size`
  gate is intact and precedes every open.
- #3 (false-clean instead of readiness `ConfigError`): PASS - every parse/schema
  failure, including the nested-TOML shapes, raises `ConfigError` -> CLI exit 2.
- #4 (ReDoS / super-linear matcher): PASS - trie is O(document tokens x longest old)
  and entry-count-independent; literal matching only.
- #5 (absolute path / raw `tomllib` text / unescaped control bytes in a sink): PASS -
  every attacker string is `_echo`/`_echo_keys` bounded + escaped; only the configured
  (never resolved) path and the entry index are echoed as provenance.
- #6 (second parser / network / execution / source mutation): PASS - stdlib `tomllib`
  only, shared scanner reused, no network/subprocess, no source write.

### Re-audit verdict: PASS

All four defects from the BLOCK review are resolved and independently re-verified; the
two HIGH findings that tripped BLOCK conditions #5 and #4 no longer do, the MEDIUM
`RecursionError` gap is closed, and the LOW mask false positive is accepted as
documented. No CRITICAL or HIGH remains. The one informational note (a bounded ~42 MB
worst-case trie under the 1 MB mapping cap) needs no action. The `warning` + opt-in
severity posture stands unchanged. **DS115 is clear to merge** with respect to this
threat model.
