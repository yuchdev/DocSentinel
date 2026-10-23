# Security review - DS114 Duplicate stable document identifiers - 2026-10-23

Post-implementation adversarial review of the **shipped, uncommitted** `DS114`
(branch `milestone/0005-deepening-test-case-stage-2`): the detector
`src/docsentinel/detectors/document_ids.py`, its `document_id_*` config
validation in `config.py`, the unit/mock/integration tests, and the
`FINDING_SATISFIES_ERROR` allowlist change in
`tests/integration/test_milestone_0005_fixture_catalog.py`. `DS114` is an
**always-active, `error`-severity, `fast`-profile** rule that carries a brand-new,
hand-written, standard-library-only frontmatter reader (the repo has no YAML
dependency) parsing attacker-controlled document heads.

The DS116/DS113/DS112 standing floor is applied: filesystem containment, no
outside-root I/O or existence oracle, no opening of non-regular/special files, a
bounded repr-escaped echo, no quadratic shapes, a bounded single read, and
tokenizer/evasion parity with a real parser. This review adds the DS114-specific
concern that dominates it: **a hand-rolled YAML-subset reader produces a different
identity than a real YAML 1.2 parser for a well-defined set of inputs**, which at
`error` severity can both falsely block a merge (false collision) and silently
miss a real duplicate (hidden collision). Relevant identifiers: CWE-1286 (improper
validation of syntactic correctness of input / bespoke parser divergence), CWE-20
(improper input validation), CWE-697 (incorrect comparison), CWE-179/CWE-176
(improper Unicode/normalization handling), CWE-117 (log injection), CWE-22/CWE-59
(path traversal / link following), CWE-400 (resource exhaustion), CWE-693
(protection-mechanism failure / evasion), OWASP A01:2021 and A09:2021.

Evidence scripts live only in the session scratchpad; no product code or other
docs were modified. The YAML differential used PyYAML 6.x in a throwaway
`uv run --with pyyaml` environment (scratch only, never a runtime or test
dependency); PyYAML implements YAML 1.1 so each 1.1-vs-1.2 difference is called
out where it matters.

## Assets and trust boundaries

| Asset | Trust level | Why it matters |
|-------|-------------|----------------|
| Untrusted Markdown document heads | Hostile | A PR contributor controls every frontmatter byte: the `id` key, its value shape, quoting, escapes, Unicode, and length. |
| `document_id_field` / `document_id_scope` / `document_id_case_sensitive` / `document_id_required` config | Semi-hostile | In CI/pre-commit the config lives in the contributor-controlled tree; `document_id_field` is a key *name* (not a path), and an injected `Config` bypasses `load_config` validation entirely. |
| Discovery output (`documents`) | Trusted boundary | Discovery has already excluded symlinks, non-regular and out-of-root files; DS114 reads only these, each as `root / document.path`. |
| Scan-root subtree | Trusted boundary | The only region DS114 opens; it reads a bounded head of each discovered `.md` file. |
| Filesystem outside the root | Off-limits | DS114 must never open, `stat`, `realpath`, or symlink-follow it. |
| Report sinks (text/json/github) and CI logs | Semi-public | `finding.message` is rendered verbatim; the author-controlled id and the original document's relative path land here. |
| Pass/fail exit code | Integrity/availability signal | `error` severity makes one collision exit 1 **without** `--strict`; a false collision is a hard merge-gate denial, a hidden collision hides a real duplicate. |

Threat actors: a contributor who submits a crafted frontmatter corpus (and,
secondarily, config) run through CI/pre-commit, to block a good merge, slip a
duplicate id past the gate, inject log bytes, probe host paths, or stall the run.
Repudiation and elevation have no DS114 surface (local/CI CLI, no audit log, no
auth, no automated remediation, no `DOC_SENTINEL_PROD_CONFIRMED`-style action),
consistent with the DS112/DS113/DS116 models. Supply chain is out of scope
(stdlib-only, no network, no execution of document content).

## Verdict on the BLOCK conditions: all PASS (no CRITICAL)

Confirmed empirically with an `os.*`/`builtins.open` recorder, a `sys.addaudithook`
`open` probe, and a 10 s `SIGALRM` guard over a hostile corpus (in-root symlink to
an outside secret, in-root symlink to an in-root file, `/dev/zero` via an in-root
symlink, a runtime `os.mkfifo` named `*.md`, a 5 GiB sparse file, and a
`chmod 000` unreadable file).

- **Filesystem containment / no outside-root I/O - PASS.** Discovery inventoried
  only the two genuine in-root regular files (`a.md`, `sparse.md`); the symlinks
  (incl. the one to `outside/secret.md` and the one to `/dev/zero`) and the FIFO
  were all excluded, so `detect` never saw them. During the scan, `open` was
  called on exactly those two in-root paths and on **no** path resolving outside
  the canonical root. `detect` canonicalises the root once with the single
  permitted `os.path.realpath` (`document_ids.py:614`) and opens each document as
  `canonical / document.path` with no path resolution of its own
  (`:580-592`,`:619`). The mock oracle test pins the same invariant
  (`tests/mock/test_detectors_document_ids_oracle.py:228-234`).
- **Never open/read a special file; never read a whole file - PASS.** The FIFO and
  the device-via-symlink were excluded by discovery, so no `open` ever blocked (the
  alarm never fired; the scan completed promptly). The 5 GiB sparse file's head was
  read and its collision reported, but only `_MAX_HEAD_BYTES` (65 536) were read -
  `_read_head` does a single `stream.read(_MAX_HEAD_BYTES)` (`:590-591`), never the
  body. The mock oracle asserts `bytes_read <= _MAX_HEAD_BYTES` while the on-disk
  size exceeds it (`:236-238`).
- **Echo / log injection / path disclosure - PASS.** `_echo` bounds to
  `_MAX_ECHO = 80` then `unicode_escape` (`:228-241`), so NUL/ESC/C1/CR/LF/RTL and
  non-ASCII render as printable `\xNN`/`\uNNNN`. Because the reader is line-based, a
  double-quoted id value can never span physical lines: an id such as
  `id: "x<CR><LF>::error file=evil::pwned"` is an **unterminated** quoted scalar on
  its physical line, classified `UNSUPPORTED`, and its message names only the
  repr-escaped field (never the value). The rendered github output for a hostile-id
  collision corpus was exactly two well-formed `::error` lines with no injected
  command line (confirmed in scratch; integration pins text/json/github at
  `tests/integration/...ds114.py:794-884`). The relative original path is echoed,
  never the resolved absolute root.
- **Unreadable file fails closed, not clean - PASS.** `_read_head` lets an
  `OSError` on a discovered regular file propagate (`:586-592`): the `chmod 000`
  file raised `PermissionError` out of the scan rather than a false clean, matching
  the other fast detectors (integration `:947-974`).
- **No quadratic shape / linear cost - PASS.** The reader is one bounded pass
  (`split("\n")`, a bounded block scan capped at `_MAX_FRONTMATTER_LINES = 2000`,
  per-line colon/comment/quote scans); the corpus core is one sorted pass with
  dict/set membership (`:505-555`). A doubling series of all-identical ids
  (n = 4k..32k) scaled ~linearly (per-doubling time ratios ~1.8-2.0, not the ~4 of a
  quadratic), with the exact `n-1` finding count; unit floods pin single-line value,
  many-keys, and multi-document shapes with `assert_scales_linearly`
  (`tests/unit/test_detectors_document_ids.py:770-847`).

Because every BLOCK condition passes, there is no CRITICAL and nothing here must be
kept out of `master` on containment grounds. The remaining findings are the
reader-divergence false-positive/false-negative class and lower-severity items.

## Findings

### [MEDIUM] Plain-scalar multi-line continuation is truncated - false AND hidden collisions

- Vector / evidence: a real YAML parser folds a plain scalar's indented
  continuation line into the value; DS114's reader reads only the first physical
  line. `_interpret_value` returns the first line's text whenever the inline value
  is non-empty, and `next_is_nested` is consulted *only* for an empty inline value
  (`document_ids.py:327-354`,`:423-431`). Differential (PyYAML, scratch):
  `id: alpha\n  continued` -> DS114 `alpha`, YAML `alpha continued`.
- Impact (both directions, CWE-1286/CWE-697):
  - **False collision (error, blocks merge):** doc A `id: alpha`, doc B
    `id: alpha\n  continued`. DS114 reads both as `alpha` and emits an `error`
    collision that blocks the merge; a real tool sees distinct ids. A wrapped id
    value is an ordinary authoring shape, so this is a realistic merge-gate DoS.
  - **Hidden collision (false clean, evasion):** doc A `id: shared extra`
    (one line), doc B `id: shared\n  extra`. A real tool reads both as
    `shared extra` and collides; DS114 reads `shared extra` vs `shared` and misses
    the duplicate.
- Mitigation (follow-up, non-blocking): treat a top-level configured-field key
  whose plain inline value is immediately followed by an indented, non-comment
  continuation line as `UNSUPPORTED` (one explicit finding) rather than silently
  reading the truncated first line - matching the reader's existing fail-explicit
  philosophy for other shapes it does not model, and converting both a false and a
  hidden collision into an honest "unsupported value shape" diagnostic. Document the
  limitation in the rule docstring either way. Hand to `python-expert`; regression
  (differential) to `testing-expert`.

### [MEDIUM] Double-quoted `\x` / `\u` / `\U` escapes are mis-decoded, not deferred

- Vector / evidence: `_DOUBLE_QUOTE_ESCAPES` recognises only
  `\\ \" \n \t \r \0` and, for any other `\X`, keeps the following character
  literally and **drops the backslash** (`document_ids.py:200-208`,`:273-277`).
  So YAML's numeric escapes become wrong text, not a deferred/unsupported shape.
  Differential: `"\x41"` -> DS114 `x41` vs YAML `A`; `"A"` -> `u0041` vs `A`;
  `"\U00000041"` -> `U00000041` vs `A`.
- Impact (CWE-1286, both directions):
  - **False collision:** doc A `id: "x41"` (literal), doc B `id: "\x41"` -> DS114
    both `x41` -> `error` collision; real tool `x41` vs `A`, distinct.
  - **Hidden collision:** doc A `id: "A"`, doc B `id: "\x41"` -> real tool both
    `A`, collide; DS114 `A` vs `x41`, missed.
  Numeric escapes in a doc id are uncommon, so the practical likelihood is lower
  than the multi-line case, but the answer to "deferred or wrong id?" is **wrong
  id** - the more dangerous choice because it silently invents a mismatching value.
- Mitigation (follow-up): either support `\xNN`/`\uNNNN`/`\UNNNNNNNN` exactly as
  YAML does, or - preferably, to avoid growing the reader into a YAML engine - treat
  a double-quoted value containing an unrecognised `\X` escape as `UNSUPPORTED`
  (explicit finding), so the id is never silently mis-decoded. Document the escape
  subset in the rule docstring. `python-expert` / `testing-expert`.

### [MEDIUM] Alternative YAML key/value spellings read as absent or unsupported - hidden collisions and false blocks

- Vector / evidence: the reader models only a `key: scalar` line with a plain or
  quoted scalar. The differential shows these well-formed YAML spellings of the id
  diverge:
  - `"id": value` (quoted key) and `? id\n: value` (explicit key): DS114 `ABSENT`,
    YAML `value`. The field comparison is `content[:colon].strip() != field`
    (`:409`), so a quoted or explicit key never matches.
  - `<<: {id: value}` (merge key): DS114 `ABSENT`, YAML `value`.
  - `id: &a value` / `id: *a` (anchor/alias), `id: !!str value` (tag), `id: |`/`id: >`
    (block scalars): DS114 `UNSUPPORTED` (one `error` finding), YAML resolves the
    scalar.
- Impact (CWE-1286/CWE-693):
  - **Hidden collision (evasion, false clean):** a contributor who writes the id as
    `"id": shared` (or `? id`, or via a merge key) declares an identity a real tool
    honours, but DS114 reads it as absent - two such docs never collide, and under
    `document_id_required = true` they are *also* wrongly flagged "declares no id".
    This is the evasion direction: a duplicate id can be smuggled past the gate by
    choosing an un-modelled-but-valid spelling.
  - **False block (error):** `id: !!str 2024` or `id: &ref foo` are valid YAML a doc
    author may legitimately write; DS114 raises a blocking `error` "unsupported value
    shape". This is honest (it flags rather than silently misreading) but still
    blocks on valid frontmatter.
- Mitigation (follow-up): accept the un-modelled spellings as documented reader
  gaps (the quoted/explicit/merge-key *hidden* direction is the one worth
  recording, since it is an evasion), and keep the anchor/alias/tag/block-scalar
  cases as explicit `UNSUPPORTED` findings (already the behaviour, and the safer
  fail direction). Enumerate the recognised-vs-unrecognised key and value shapes in
  the rule docstring and `docs/dev/markdown_dialect.md`. No containment impact.

### [LOW] YAML type coercion divergence: `~`/`null` and boolean/`yes`/`on` ids

- Vector / evidence: DS114 treats every non-empty scalar as literal text and
  explicitly does **not** interpret YAML types (`document_ids.py:33-38`). So
  `id: ~` -> DS114 id `~`, YAML `null` (no identity); `id: null` -> DS114 `null`,
  YAML null; `id: true` -> DS114 `true`, YAML boolean; and under YAML 1.1
  `id: yes`/`id: on` are booleans while DS114 keeps the literal text.
- Impact: minor. Two docs both `id: ~` (or both `id: null`) collide in DS114 on the
  literal text (a false collision at `error`, though both arguably "have no real
  id"); `id: yes` vs `id: true` would collide in a YAML-1.1 tool but stay distinct
  in DS114 (a hidden collision, but only under 1.1 and only for these reserved
  words - YAML 1.2 keeps `yes`/`on` as strings, matching DS114). Using a reserved
  scalar as a stable doc id is poor practice and uncommon.
- Mitigation: accept and document. The "literal text, never YAML types" rule is
  actually the more *deterministic* and predictable choice; only the `~`/`null`
  false-collision edge is mildly surprising. Record in the docstring.

### [LOW] Unicode confusables and zero-width/format characters stay distinct (consistent with YAML; a hidden collision a human might not expect)

- Vector / evidence: normalization is NFC + whitespace-collapse + optional casefold
  (`:439-451`); NFC does not strip zero-width (`U+200B`) or bidi (`U+202E`)
  characters, and Latin vs Cyrillic confusables are distinct code points. The
  differential confirms DS114 and YAML agree: `a<ZWSP>b` and the bidi id are kept
  verbatim, and confusables are not folded.
- Impact: two ids that look identical but differ only by an invisible zero-width or
  a confusable code point are treated as **distinct**, so a collision a human would
  expect is not reported (a hidden collision). But this matches a real YAML parser
  exactly - it is a Unicode policy choice, not a reader divergence - and the echo
  repr-escapes the invisible bytes (`​`, `‮`) so the output is honest.
- Mitigation: this is the documented design (confusables stay distinct; see the
  module docstring and the `test_unicode_confusables_stay_distinct` /
  `test_nfc_equivalent_ids_collide` unit tests). Explicitly **report** the ruling:
  the milestone chose NFC (canonical equivalence) over NFKC/confusable-folding, so
  invisible-character and homoglyph collisions are intentionally not detected.
  Switching to NFKC would fold some confusables but would also diverge from YAML and
  change legitimate ids; keeping NFC is the correct, parser-consistent call. No
  change required; document the choice.

### [LOW] `document.path` is opened without an independent containment re-check (accepted trust boundary)

- Vector / evidence: unlike `DS112` (which re-validates every config-named index
  with `is_ds116_owned` + `escapes_via_symlink` + `S_ISREG` before opening), `detect`
  opens `canonical / document.path` directly with no containment check
  (`document_ids.py:616-619`). A hostile **direct** caller of `detect` that
  fabricates `models.Document("../../etc/passwd")` would have it opened.
- Impact: none under the real trust model. DS114 has no config option that names a
  path (its config is a key *name*, a scope enum, and two bools), so - unlike DS112 -
  there is no attacker-controlled-config path into `detect`. The only source of
  `documents` through the engine is discovery, which already excludes symlinks,
  non-regular, and out-of-root files (confirmed empirically above). A direct `detect`
  caller passing fabricated paths is a trusted library caller, identical to the
  posture of `DS101`/`DS103` reading discovered docs. The docstring states this
  reliance explicitly (`:106-116`).
- Mitigation: none required; recorded so the DS112-vs-DS114 asymmetry is a conscious,
  documented decision rather than an oversight. If `detect` is ever exposed to
  config-named or otherwise untrusted `documents`, it must adopt DS112's defensive
  re-check.

### [LOW] Duplicate-id-key defer is an evasion vector (documented DS111 territory)

- Vector / evidence: a block declaring the configured field twice is `DEFERRED`
  (silent) by design (`:413-415`), leaving metadata validity to the unimplemented
  `DS111`. PyYAML resolves duplicate keys to the **last** value.
- Impact: two docs that each write `id: X\nid: shared` are silently dropped by DS114
  (no collision), while a real tool reads both as `shared` and collides - a hidden
  collision. This is the accepted DS111 boundary (DS114 owns uniqueness, not
  validity) and avoids a contradictory dual diagnostic, but it is an evasion path a
  reviewer should be aware of until DS111 ships.
- Mitigation: accept and document; it is the stated delegation. When `DS111` lands,
  confirm the two rules together leave no "duplicate-key id" silently un-diagnosed.

### [INFO] Per-corpus memory holds every head at once

`detect` builds the full `entries` list of `(path, head)` for every discovered
document before calling `check_documents` (`document_ids.py:615-623`), so peak
memory is `O(n_docs x min(head, 64 KiB))` rather than per-document streaming. It is
bounded (each head <= 64 KiB; `n_docs` is the repo's discovered `.md` count) and is
not a DoS, but it is a larger transient than DS112's sequential per-index read.
Recorded for awareness; streaming the sort key instead of the raw head would remove
it if a very large corpus ever matters.

## Config-injection and allowlist assessment

- **`document_id_field` validation - sound.** `_DOCUMENT_ID_FIELD_PATTERN`
  (`config.py:89`) `fullmatch`es `[A-Za-z_][A-Za-z0-9_-]{0,127}`, rejecting spaces,
  dots, and every regex metacharacter, and caps the length at 128 so a pathological
  field cannot drive an unbounded per-line key comparison. The field is used only in
  plain string comparison (`content[:colon].strip() != field`) and is echoed through
  the bounded `_echo` - it never reaches a regex, so there is no injection surface
  even before the validation. Invalid values from both `doc_sentinel.toml` and
  `[tool.doc_sentinel]` raise `ConfigError` (integration `:623-662`).
- **`document_id_scope` enum incl. injected Config - sound (fails closed).**
  `load_config` enum-validates the scope (`config.py:108`), and `check_documents`
  re-checks `scope not in _VALID_SCOPES` and raises `ConfigError` rather than
  degrading to `corpus` when an **injected** `Config` bypasses `load_config`
  (`document_ids.py:498-501`; integration `:454-478`), mirroring the DS112
  config-injection defence. `document_id_case_sensitive`/`document_id_required` are
  bool-validated at load; an injected non-bool is used in boolean context (trusted
  caller), no security impact.
- **`FINDING_SATISFIES_ERROR` catalog change - does NOT weaken a gate.** The generic
  catalog previously required every `error`-outcome scenario to satisfy
  `result.error is not None or result.pending`. The change adds a narrowly scoped
  `frozenset({("DS114", "invalid_nested_metadata")})` exception allowing that one
  row to be satisfied by `result.own_finding_count >= 1`
  (`test_milestone_0005_fixture_catalog.py:37-40`,`:280-287`). This is sound because:
  (1) `own_finding_count` is **rule-scoped** - the runner scans with
  `select=(scenario.rule,)` and counts only `finding.rule == scenario.rule`
  (`milestone_0005_manifest.py:280-287`), so only a genuine DS114 finding satisfies
  it; (2) the finding is `error` severity, so the merge gate still blocks (exit 1) -
  the scenario cannot pass as clean; (3) a zero-finding clean result still fails the
  assertion (`flagged_by_finding and own_finding_count >= 1` is False at count 0);
  (4) the manifest still counts it in the `error` bucket (totals unchanged,
  `EXPECTED_OUTCOME_COUNTS["error"] == 4`); and (5) the exact line/path/message/
  severity and the "not a ConfigError, never a collision original" contract are
  pinned by the dedicated task-03 test (`...ds114.py:321-354`). It encodes the Story
  12.0 ruling (an unsupported id value shape is one explicit own finding, not a
  whole-scan `ConfigError` exit 2) for exactly one scenario, with the comment
  requiring every other error row to still raise or be pending. No security gate is
  loosened.

## Verdict on `error` default-on

From a confidentiality/integrity standpoint `error` default-on is **acceptable**:
DS114 creates no vulnerability - it reads only bounded heads of the repo's own
in-root regular files, opens nothing outside the root or special, and its echo is
bounded and repr-escaped. All BLOCK conditions pass.

The real residual risk is **merge-gate availability** from the reader-vs-YAML
divergences above - specifically the MEDIUM **false collisions** (multi-line plain
continuation; `\x`/`\u`/`\U` mis-decode; `!!str`/anchor as `UNSUPPORTED`), each of
which can block a good PR at `error` severity. Unlike `DS116` (`root_escape_policy`)
and `DS113` (`missing_asset_policy`), **DS114 ships no off/warn/error severity-
downgrade knob** - the only opt-outs are `select`/`ignore`, baseline, and the typed
options. This is more defensible for DS114 than it was for DS113 because DS114 in
the common case fires only on *genuine* duplicate ids (a real defect worth
blocking) and `document_id_required` is off by default; but the divergence-driven
false positives have no advisory path short of disabling the rule or baselining the
specific finding.

Recommended (non-blocking) follow-ups, in priority order:

1. Close the multi-line-continuation and `\x`/`\u`/`\U` divergences by treating the
   un-modelled shape as an explicit `UNSUPPORTED` finding (fail-explicit) rather than
   reading a truncated/mis-decoded id - this removes both the false and the hidden
   collision in one move and keeps the reader from growing into a YAML engine.
2. Enumerate the recognised-vs-unrecognised key/value/escape subset and the NFC
   (not NFKC) confusable policy honestly in the rule docstring and
   `docs/dev/markdown_dialect.md`, so the reader is documented as a **narrow,
   best-effort frontmatter subset, not a YAML parser**.
3. Consider a `document_id_policy` (off/warn/error, default error) knob mirroring
   `root_escape_policy`/`missing_asset_policy` so an operator can downgrade DS114 to
   advisory without losing it, should the divergence false positives prove
   disruptive in practice.

Fix handoff: the reader-divergence fixes (multi-line continuation, escape handling,
optional severity knob) go to `python-expert`; the YAML-differential, false/hidden-
collision, and hostile-corpus regression tests go to `testing-expert`.

## Review verdict: PASS_WITH_FOLLOWUP

No CRITICAL and no BLOCK condition is met: filesystem containment, the
no-open/no-outside-root and bounded-head guarantees, the fail-closed unreadable
path, the bounded repr-escaped echo (incl. a verified no-github-injection), the
config-injection fail-closed scope check, and linear cost are all verified
empirically. `error` default-on is acceptable. The residual risk is purely
merge-gate availability from the hand-written reader diverging from a real YAML 1.2
parser; the three MEDIUM divergence classes should be closed or documented and a
severity-downgrade knob considered, none of which blocks merging to `master`.

**DS114 must be documented as a best-effort, narrow frontmatter-subset identity
check, not a YAML parser or a complete uniqueness control:** it inherits the
enumerated reader gaps (alternative key spellings, numeric escapes, type coercion,
block scalars, duplicate keys deferred to the unimplemented DS111) and the
NFC-only confusable policy.
