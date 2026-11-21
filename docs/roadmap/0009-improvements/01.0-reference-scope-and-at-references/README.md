# Story 01.0 — Reference scope and `@`-document references (DS103 opt-in, new DS124)

**Profile:** `fast` · **New rule:** `DS124` (warning, always active) · **Changed rule:** `DS103`
(becomes opt-in, enabled by `reference_scope = "strict"`) · **Touched sources:**
`/src/docsentinel/config.py`, `/src/docsentinel/rules.py`, `/src/docsentinel/engine.py`,
`/src/docsentinel/cli.py`, `/src/docsentinel/markdown_blocks.py`,
`/src/docsentinel/detectors/paths.py`, `/src/docsentinel/detectors/path_boundaries.py`,
`/src/docsentinel/link_root.py`, `/src/docsentinel/telemetry/classify.py`, and a new detector
module named mentions.py in the detectors package.  
**Parent:** [Milestone 0009 plan](/docs/roadmap/0009-improvements/plan.md) (contracts C2, C3, C4).  
**Security-sensitive:** yes. It resolves paths taken from untrusted document text; Task 02 runs
before any code.

## Goal

By default, check only what a reader or an agent will actually follow: Markdown links (already
DS101, DS108, DS113, DS116) and `@`-document mentions (new DS124). Path-looking inline code spans
(DS103) stay available, but only in a strict mode the project asks for. A scan in the default mode
must say that DS103 did not run.

## Tasks

| Task | Deliverable | Role | Status |
|---|---|---|---|
| [01](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/01-adr-and-rule-contract.md) | ADR for reference scope and DS124; `Rule.opt_in_values` contract; rule code reservation | Architect | ✅ Complete |
| [02](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/02-threat-model-at-references.md) | Threat model for `@`-reference recognition and resolution | Security Auditor | ✅ Complete |
| [03](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/03-reference-scope-config-and-opt-in-values.md) | `reference_scope` and `at_reference_extensions` keys, `--reference-scope`, `Rule.opt_in_values`, DS103 opt-in, notice, `rules` and `doctor` | Python Expert | ✅ Complete |
| [04](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/04-at-reference-scanner.md) | `AtReference` recognition in the shared scanner | Python Expert | ✅ Complete |
| [05](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/05-ds124-detector-and-ds103-ds116-integration.md) | DS124 detector; DS116 checks mentions; DS103 skips mentions; link-root and fault-class wiring | Python Expert | ✅ Complete |
| [06](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/06-fixtures-and-tests.md) | Assets for DS124 and DS103 scope cases; unit, mock and integration tests | Testing Expert | ✅ Complete |
| [07](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/07-self-scan-and-baseline-migration.md) | Self-scan counts before and after; regenerate the fast baseline; CI check | Python Expert | ✅ Complete |
| [08](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/08-docs-and-release-notes.md) | Rules table, configuration, CLI, finding types, fault classes, scanner docs, README, release-notes proposal | Docs Writer | ✅ Complete |

## Scope

- New config keys `reference_scope` and `at_reference_extensions`; new flag `--reference-scope` on
  `scan` and `baseline`.
- The opt-in machinery learns enabling values (C2), so DS103 is inert unless the scope is
  `"strict"`.
- A new shared-scanner record for `@`-mentions, a new rule DS124, and DS116 coverage of mentions.

## Non-goals

- Changing which code spans DS103 considers path-like (Milestone 0008 Story 05.0).
- Following mentions recursively, checking a fragment after a mention, or resolving home and
  absolute mentions.
- Changing DS101, DS108, DS113 or DS112 behaviour.
- Any report schema change. `ScanResult` gains no field.

## Design

### Decisions

| # | Decision | Rationale |
|---|---|---|
| S1 | Key `reference_scope`, values `"links"` (default) and `"strict"` | A named mode reads better than a DS103 toggle and leaves room for a future scope without a new key |
| S2 | CLI flag `--reference-scope {links,strict}` | `--strict` already means "warnings block"; a second meaning of "strict" on the same command would be a trap |
| S3 | DS103 registers with `opt_in_option="reference_scope"` and `opt_in_values=frozenset({"strict"})` | Reuses the existing opt-in reporting (notice, `rules`, `doctor`, engine warning) instead of a new mechanism |
| S4 | New rule DS124, `warning`, always active, not tied to the scope | Mentions are real references in both modes; a separate code keeps DS101 baselines and `select`/`ignore` untouched (plan D2, D3) |
| S5 | DS116 keeps its code-span traversal check in both scopes and adds mentions | Error-severity safety guard with low noise (plan D4) |
| S6 | DS115 is unchanged by the scope | It matches mapped deprecated tokens, it does not check existence |
| S7 | DS103 skips every code span starting with `@` | One owner per mention; today DS103 misreads the coding-standard mention as a missing relative path |
| S8 | Recognition lives in the shared scanner; DS124 and DS116 filter by config | The scanner stays config-free (`scan_markdown(text, path)`), as for every other record |

### Config reference

| Key | Type | Default | Validation | Allowed in user settings (Story 03.0) |
|---|---|---|---|---|
| `reference_scope` | string | `"links"` | enum `links`, `strict`; anything else raises `ConfigError("reference_scope must be one of: links, strict")` through the existing enum validator | yes |
| `at_reference_extensions` | list of strings | md, markdown, mdx, txt, rst, toml, json, yaml, yml, py | 1 to 64 entries; each 1 to 16 ASCII letters or digits, no dot, no whitespace; compared case-insensitively; duplicates after lowercasing are a `ConfigError`; an empty list is a `ConfigError` whose message says to use `ignore = ["DS124"]` instead | yes |

Both keys are added to the known-option set, to `Config` with the defaults above, and to the
annotated example `/examples/docsentinel.toml`. The standalone TOML file, `[tool.doc_sentinel]`
and an injected `Config` behave the same. An injected `Config` with an unknown scope makes
`opt_in_satisfied()` return false (DS103 inert), and DS124 re-validates `at_reference_extensions`
and fails closed with `ConfigError`, as DS118 does for its options.

### CLI reference

| Command | Flag | Values | Effect |
|---|---|---|---|
| `scan` | `--reference-scope` | `links`, `strict` | Replaces `reference_scope` for this run (layer 4 in C1) |
| `baseline` | `--reference-scope` | `links`, `strict` | Same, so a strict lane can record its own baseline |
| `rules` | — | — | DS103 line ends with `[opt-in: set reference_scope = "strict"]`; DS124 is listed as an ordinary rule |
| `doctor` | — | — | Counts DS103 among opt-in rules and prints one line with the effective scope of the configuration in the current directory |

There is no new `scan()` keyword; library callers set the key on `Config` (for example with
`dataclasses.replace()`).

### At-reference grammar

An `@`-mention is recognised by the shared scanner, in two forms.

1. **Prose form.** An `@` at the start of a line or after whitespace or one of the four characters
   open-parenthesis, open-bracket, double quote, single quote, followed by a path token.
2. **Code-span form.** An inline code span whose trimmed text is exactly one `@` plus a path token
   (no whitespace other than an escaped space). Plan D6: Claude Code does not import such a span,
   but this repository writes every agent mention this way.

The path token is a run of ASCII letters, digits and the characters dot, underscore, tilde, plus,
hyphen and slash, plus a backslash-escaped space (the Claude Code convention for paths with
spaces). After recognition, each two-character backslash-space sequence is replaced by one space,
once, as a literal string operation; no other decoding applies. A backslash followed by any other
character ends the token and is never decoded. The token ends at any other character. It is at
most 1,024 raw characters as written, each escaped space counting as two; a longer run is not
recognised, and scanning resumes after the end of that run. Trailing dots, commas, semicolons,
colons, exclamation and question marks are stripped. A token that starts or ends with an escaped
space (checked after that stripping) is not recognised, so the resolver's whitespace strip can
never change the name. A fragment (`#`) or percent sign ends the token, so no percent or fragment
decoding ever applies. Amendment A2 of the
[threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md#required-spec-amendments-before-the-named-task-starts)
(M8, M12, M13).

A token is recorded only when its last path component has an extension that contains at least one
letter (so version strings are not mentions). It is classified by its start:

- `relative` — everything else; checked by DS124 and DS116;
- `home` — starts with a tilde and a slash; recorded, never resolved;
- `absolute` — starts with a slash; recorded, never resolved.

Never recognised: inside fenced code blocks, HTML comments, raw HTML tags, the text or destination
of an inline link or image, or a reference-style link label; after a backslash (the author's
escape hatch); after a letter, digit or another `@` (e-mail addresses, handles).

```text
Recognised (relative):     @docs/dev/python_coding_standard.md    (@AGENTS.md)    "@Design\ Docs/x.md"
Code-span form:            `@docs/dev/python_coding_standard.md`
Recognised, never resolved: @~/notes/me.md    @/etc/hosts.txt
Not recognised:            user@example.org   @octocat   @types/node   @1.2.3   \@docs/x.md
Filtered by extension list: @example.com      (com is not in at_reference_extensions)
```

The scanner record (additive, defaulted, so existing consumers are unchanged):

```python
@dataclass(frozen=True)
class AtReference:
    target: str          # path token without "@", escaped spaces decoded, punctuation stripped
    raw: str             # "@" plus the token exactly as written, for the finding value
    kind: str            # "relative" | "home" | "absolute"
    in_code_span: bool
    span: MarkdownSpan   # prose form: from the "@"; code-span form: the InlineCode span object itself

# MarkdownBlockIndex gains:  at_references: tuple[AtReference, ...] = ()
```

### Resolution (DS124)

For each `relative` mention whose extension (lowercased) is in `at_reference_extensions`:

1. **Document-relative.** `resolve_local_reference(root, document, target)`. If DS116's mention
   classifier reports it (the single shared ownership predicate in
   `/src/docsentinel/detectors/path_boundaries.py` that DS116 itself uses: a root escape, or a
   symlink out of the scan root), DS124 stops: DS116 owns it, and step 2 never runs. Any other
   `contained_path()` refusal (a symlink cycle, more than 64 hops) or any `OSError` means "does not
   resolve at this step", is never propagated, and DS124 goes on to step 2. If the contained path
   is a regular file (`os.stat()` plus `S_ISREG` on the path `contained_path()` returned, never
   opened), the mention resolves. Amendment A4 of the
   [threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md#required-spec-amendments-before-the-named-task-starts)
   (M5, M10).
2. **Link-root-relative fallback.** Otherwise resolve `"/" + target` with `link_root=` the engine's
   validated link root. If `contained_path(link_root, ...)` returns a regular file, the mention
   resolves. If it is refused (a symlink out of the link root, or a climb above it), DS124 logs it
   at `DEBUG` (the document path through `safe()`, the line number and a fixed reason, never the
   mention text) and reports nothing: the file is outside the link root, so it is not "missing".
   This is the single documented exception to "every relative mention resolves, gets a DS116
   finding or gets a DS124 finding" (owner ruling R1, adopted as recommended; threat model M6).
   An `OSError` on this step means "does not resolve" and falls through to step 3.
3. Otherwise DS124 reports one finding.

DS124 joins `LINK_ROOT_RULES` in `/src/docsentinel/link_root.py`, so the engine validates the
link root once and passes `link_root=`. Called directly without it, DS124 uses the lexical
`link_root_for()`, like DS101.

### DS124 rule contract

```python
DS124 = rules.register_rule(
    rules.Rule(
        code="DS124",
        profile="fast",
        title="Dangling @-document reference",
        description="An @-document mention does not resolve to an existing file.",
        severity="warning",
    )
)
# bounded_raw = raw cut to its first 200 characters, no truncation marker inside the token
# Finding(rule="DS124", path=<document>, message="dangling @-reference -> <bounded_raw>",
#         severity="warning", line=<line of @>, column=<1-based code point of @>,
#         value=<bounded_raw>, type="dangling document mention")
```

`message` and `value` echo the same bounded `raw` (amendment A3 of the
[threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md#required-spec-amendments-before-the-named-task-starts),
M15), so the finding identity and the baseline fingerprint stay bounded.

Fault class: `dangling_reference` (it feeds the fabricated-reference aggregate). One finding per
mention occurrence, in source order; the same mention twice on one line is reported once.

### DS116 and DS103 changes

- DS116 adds every `relative` mention (any extension, not only the configured list) to its
  candidates at full-reference strictness, classified with document-relative semantics, exactly
  like a relative Markdown link. A mention that escapes the scan root, directly or through an
  in-root symlink, is a DS116 finding with the existing messages. Its own code-span candidate list
  drops a span only when the scanner recorded that exact span (by `MarkdownSpan` identity) as an
  `AtReference` with `in_code_span=True`, never by an `@` prefix, so a mention is classified once,
  with the right base, and an `@`-prefixed code span that is not a mention (for example one with
  no letter-bearing extension) stays a DS116 code-span candidate. Amendment A1 of the
  [threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md#required-spec-amendments-before-the-named-task-starts)
  (M11).
- DS103 adds `@` to its excluded span prefixes (today: hyphen, dollar, greater-than). Strict scope
  otherwise keeps DS103 byte-for-byte.

### How the mode is reported

| Surface | Default scope | Strict scope |
|---|---|---|
| `ScanResult.notice` | `... opt-in rule(s) not enabled: DS103 (set reference_scope = "strict"), DS110 (set require_fence_languages), ...` | DS103 counted as evaluated |
| `ScanResult.enabled_rules` | contains DS103 (selection stays orthogonal) | same |
| `docsentinel rules` | `DS103: Unresolvable path-like code span [opt-in: set reference_scope = "strict"]` | same (static listing) |
| `docsentinel doctor` | `fast rules: 18 registered (5 opt-in, off unless configured: DS103, DS110, DS112, DS115, DS118)` and `reference scope: links (DS103 off)` | `reference scope: strict (DS103 on)` |
| CLI `INFO` start line | adds `reference_scope=links` | adds `reference_scope=strict` |
| Engine `WARNING` when DS103 is selected explicitly | `DS103 is selected but evaluates nothing until reference_scope = "strict" is set` | none |

The notice text for DS110, DS112, DS115 and DS118 stays byte-identical (contract C2).

Counts (corrected per [ADR 0004](/docs/adr/0004-reference-scope-and-at-document-references.md)):
DS100 is an engine rule registered in the fast profile, so `doctor` goes from 17 to 18 registered
with DS124; the default notice stays at `12 fast rule(s) evaluated` (17 analyzer rules, 5 opt-in
off), and strict scope evaluates 13.

### Baselines and self-scan

- Baseline fingerprints are per finding, so DS103 entries in an existing baseline simply stop
  matching under the default scope; they are not an error. Task 07 regenerates
  `/.docsentinel-baseline.json` so no stale DS103 fingerprints remain, and records the counts.
- `/.docsentinel-standard-baseline.json` holds DS2xx findings only and is not touched (profiles are
  exact).
- CI keeps one default-scope self-scan lane (`/.github/workflows/ci.yml` is unchanged). A strict
  lane is not added: it would only reintroduce the noise. The repository's own mentions (the agent
  prompts) must resolve, so DS124 reports 0 on the self-scan.

### Migration and release

- Behaviour change: default scans stop reporting DS103. To keep the old behaviour set
  `reference_scope = "strict"` or pass `--reference-scope strict`.
- New warnings may appear from DS124. They block only under `--strict`. To silence it set
  `ignore = ["DS124"]`.
- Proposed version 1.3.0 (plan D7) with a release-notes entry written by Task 08.

## Edge cases

- `reference_scope = "strict"` with `ignore = ["DS103"]`: DS103 is not active, so it is neither
  evaluated nor listed as opt-in-off (existing selection semantics).
- Single-file scan target: mentions resolve the same way; the scan root is the file's directory.
- A mention to a directory (for example a folder with a dotted name) is reported as missing:
  mentions name files.
- Unreadable or non-UTF-8 documents keep today's engine behaviour: withheld from every analyzer
  (so no DS124 or DS103 finding) and reported by the engine rule DS100.
- A mention inside a Markdown table cell is recognised (a space precedes it); the table rule is not
  affected.
- The same mention in two documents is two findings, one per document.
- An extension in the list but with different case (`.MD`) matches, because the comparison is
  case-insensitive; the file lookup itself is case-sensitive as on the filesystem.

## Security notes

- Mentions are attacker-controlled text. Recognition is linear and bounded (1,024-character token
  cap, one pass per line, no backtracking regex built from input).
- No filesystem access for `home` and `absolute` mentions, ever; a test with `os.stat()` and
  `os.lstat()` patched proves it.
- No access outside the scan root on step 1 or outside the link root on step 2: both go through
  `contained_path()` before any `os.stat()`. DS124 never opens a target.
- The finding value is the raw mention, bounded to 200 characters; report sinks neutralise it as
  for DS101 and DS103 values.
- Task 02 (Security Auditor) writes the threat model under `/docs/security/` and must cover:
  fallback containment, symlink-out on step 2, TOCTOU parity with DS101, the backslash-space
  decoding, and log content (paths through `safe()`, never document text).

## Acceptance criteria

- [ ] With no configuration, a scan never runs DS103 and the notice names
      `DS103 (set reference_scope = "strict")`; with `reference_scope = "strict"` (config, user
      settings once Story 03.0 lands, or `--reference-scope strict`) DS103 reports exactly what it
      reports today, except spans starting with `@`.
- [ ] Notice text for DS110, DS112, DS115 and DS118 is byte-identical to the current text.
- [ ] DS124 is registered once in `RULES` and `ANALYZERS`, fast profile, warning, with a row in
      `/docs/user/reference/rules.md`, `/docs/specs/fault-classes.md`,
      `/docs/specs/finding-types.md` and `FAULT_CLASSES`; all drift tests pass.
- [ ] Every grammar example above behaves as stated (unit tests).
- [ ] The repository self-scan reports 0 DS103 and 0 DS124 findings and exits `0`; the before and
      after counts are recorded in `/docs/roadmap/0009-improvements/status.md`.
- [ ] Home and absolute mentions cause no filesystem call; escaping mentions are DS116 findings and
      never DS124 findings.
- [ ] `import docsentinel` and fast scans still import nothing outside the standard library.

## Test plan

| Layer | File (new unless noted) | Covers |
|---|---|---|
| Unit | test_at_reference_grammar.py in the unit tests folder | Every recognised and rejected form, both forms, kinds, punctuation stripping, escaped space, 1,024-character cap, link-label and HTML-tag skips, offsets and columns |
| Unit | test_reference_scope_config.py | Defaults, both TOML forms, invalid scope, `at_reference_extensions` bounds, duplicates, empty list message |
| Unit | test_rule_opt_in_values.py | `opt_in_satisfied()` with and without enabling values, legacy rules unchanged, notice rendering byte-identical for the four legacy rules, DS103 hint text |
| Mock | test_at_reference_no_probe.py in the mock tests folder | `os.stat()`/`os.lstat()` patched: no call for home or absolute mentions, none outside the scan root on step 1 or outside the link root on step 2 |
| Integration | test_at_references_ds124.py | DS124 asset cases end to end through `scan()` |
| Integration | test_at_references_ds116_ds124.py | Escaping and symlink-out mentions are DS116 only (symlinks built in the test body) |
| Integration | test_reference_scope_ds103.py | DS103 inert by default, reports in strict, skips `@` spans |
| Integration | test_reference_scope_cli_ds103_ds124.py | `--reference-scope` precedence over config, `rules` and `doctor` lines, notice, `baseline --reference-scope strict` |
| Integration (existing) | `/tests/integration/test_rules_table.py` | Updated for DS124 and the DS103 activation cell |

Asset cases (one folder per case, snake_case, under the ds124 and ds103 asset folders):
prose_mention_resolves, prose_mention_missing, code_span_mention_missing,
project_root_fallback_resolves, fenced_and_comment_ignored, emails_and_handles_ignored,
escaped_space_path, unknown_extension_ignored, home_and_absolute_skipped,
link_label_mention_ignored, trailing_punctuation_stripped, mention_escapes_root (ds124 folder,
asserts DS116 only); links_scope_inert, strict_scope_reports, strict_scope_skips_mentions (ds103
folder).

## Docs to update

Triggers R, C and K of `/docs/dev/documentation_sync.md`:

- `/docs/user/reference/rules.md` (DS124 row; DS103 activation `opt-in` with
  `reference_scope = "strict"`; config-keys column) — updated by the Python Expert with the code,
  verified by the Docs Writer;
- `/docs/user/reference/configuration.md` (new section "Reference scope options (DS103, DS124)");
- `/docs/user/tutorial/cli.md` (fast profile section, the new flag, migration note);
- `/docs/specs/finding-types.md` (DS124 row), `/docs/specs/fault-classes.md` (DS124 row);
- `/docs/dev/markdown_scanner.md` (the `AtReference` record and resolver ownership);
- `/README.md` rule list and configuration example; `/CLAUDE.md` Architecture and Conventions
  entries (rules, detectors, opt-in policy rules);
- `/examples/docsentinel.toml`; a proposed `/RELEASE_NOTES.json` entry for 1.3.0.
