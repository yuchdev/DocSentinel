# 0004 - Reference Scope and @-Document References

> **Status:** Accepted (2026-11-20, owner)
>
> **Date:** 2026-11-14
>
> **Supersedes:** _(none)_
>
> **Superseded by:** _(none)_

## Context and Problem Statement

DocSentinel's fast profile checks references in two different ways. Markdown links, images and
reference definitions are checked by DS101, DS108, DS113 and DS116, and these are references a
reader actually follows. DS103 also treats every path-like inline code span as a reference. On
this repository's self-scan DS103 reports about 3,900 warnings, and it reports hundreds on a
385-document external repository. Nearly all of them are dotted identifiers, source paths relative
to some other base, or site-root paths written as examples. The real findings get lost, and the
fast baseline keeps drifting
([Milestone 0009 plan, P1](/docs/roadmap/0009-improvements/plan.md#problem-inventory-observed-2026-11-13)).

Meanwhile, the references that agents follow are not checked. Agent prompts and instruction
files name documents as `@`-mentions, such as the coding-standard mention in every agent prompt.
A renamed file silently breaks every prompt that mentions it. DS103 even misreads the code-span
form of a mention as a missing path relative to the document (P2).

The question is how DocSentinel should decide, by default, which references it checks. A further
constraint is that a scan which did not run a rule must never look like a clean result.

## Decision Drivers

- **Signal over volume.** By default, report only what a reader or an agent will follow.
- **Never a silent clean result** (plan principle 2). A rule switched off by a mode must appear as
  "opt-in, not enabled" in `ScanResult.notice`, `docsentinel rules`, `docsentinel doctor` and
  the engine warning.
- **One scanner, no second resolver** (principle 4). Mentions must reuse `scan_markdown()`,
  `resolve_local_reference()` and the DS116 containment helpers.
- **Stable selection and baselines.** Existing `select`/`ignore` lists, DS101 baselines and DS101
  severity must not change meaning.
- **Byte-identity.** The notice, `rules` and engine-warning text for DS110, DS112, DS115 and DS118
  stays byte-identical.
- **No report schema change.** `ScanResult` gains no field, and JSON schemas 1 and 2 are unchanged.
- **Security.** Mention targets are attacker-controlled text. Every filesystem probe goes through
  containment first, and nothing outside the scan root or link root is ever opened or stat-ed.
- **Stdlib only.** `import docsentinel` and fast scans import nothing new.
- **Room to grow.** A later scope (for example one that also checks bare prose paths) must not
  need a new key.

## Considered Options

1. **(a) A `reference_scope` mode that makes DS103 opt-in, plus a new rule DS124 for
   `@`-mentions.** `reference_scope = "links"` (the default) or `"strict"`. DS103 is enabled
   only by `"strict"`, through a generalised opt-in mechanism (`Rule.opt_in_values`). A new
   always-active fast rule, DS124, reports dangling mentions, and DS116 also checks mentions for
   root escapes.
2. **(b) Keep DS103 on by default and tune its heuristics.** Skip dotted identifiers, and add a
   project-root fallback and allow-lists.
3. **(c) A boolean `check_code_span_paths` option** that gates DS103 through the existing
   truthiness-based opt-in. Mentions are handled separately.
4. **(d) Fold mentions into DS101** as a new finding type, `dangling mention`, under the
   existing link rule.

## Decision Outcome

Chosen option: **(a)**. It is the only option that removes the noise by default and still reports
the disabled rule honestly. It also checks agent mentions under their own code, reuses the existing
opt-in reporting instead of adding a new mechanism, and leaves DS101 untouched.

### Decisions recorded

Story decisions (from the
[Story 01.0 README](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md#decisions)):

| # | Decision |
|---|---|
| S1 | Key `reference_scope`, values `"links"` (default) and `"strict"`. A named mode, not a DS103 toggle. |
| S2 | CLI flag `--reference-scope {links,strict}` on `scan` and `baseline`. The flag is not named `--strict`, because `--strict` already means "warnings block". |
| S3 | DS103 registers with `opt_in_option="reference_scope"` and `opt_in_values=frozenset({"strict"})`. |
| S4 | New rule DS124, `warning`, always active, independent of the scope. |
| S5 | DS116 keeps its code-span traversal check in both scopes and also checks mentions. |
| S6 | DS115 does not depend on the scope. |
| S7 | DS103 skips every inline code span whose text starts with `@`, so each mention has one owner. |
| S8 | Recognition lives in the shared scanner, which stays config-free. DS124 and DS116 filter by config. |

Milestone decisions. The [plan's open decisions](/docs/roadmap/0009-improvements/plan.md#open-decisions-for-owner)
D1 to D16 were adopted as recommended on 2026-11-14 (see
[status.md](/docs/roadmap/0009-improvements/status.md)). This ADR rests on D1 to D7. D8 to D16
belong to Stories 02.0 and 03.0 and are listed so the record is complete.

| # | Decision (adopted) | Scope |
|---|---|---|
| D1 | Default `reference_scope` is `"links"`, so DS103 is off by default | this ADR |
| D2 | A new rule DS124 reports dangling mentions, rather than a new DS101 finding type | this ADR |
| D3 | DS124 default severity is `warning`; revisit after one release | this ADR |
| D4 | DS116 keeps checking code-span traversal in `"links"` scope | this ADR |
| D5 | Mention targets resolve relative to the document first, then relative to the link root | this ADR |
| D6 | An inline code span that is exactly one `@path` token counts as a mention | this ADR |
| D7 | Release as 1.3.0 with a behaviour-change note | this ADR (release) |
| D8 | CLI selectors are relative to the scan root; absolute paths inside it are accepted | Story 02.0 |
| D9 | `--include` replaces the configured list; `--exclude` appends to it | Story 02.0 |
| D10 | Directory-prefix matching also applies to `include`/`exclude` in config files | Story 02.0 |
| D11 | JSON is accepted for user settings and `--config FILE.json`; no automatic discovery of a project-level JSON file | Story 03.0 |
| D12 | User settings apply to the CLI, the library and the pytest plugin; `DOCSENTINEL_SETTINGS=off` or `--no-user-settings` turns them off | Story 03.0 |
| D13 | User settings refuse repository-relative keys; `select`/`ignore` are allowed | Story 03.0 |
| D14 | On POSIX, a group- or world-writable or foreign-owned settings file is refused | Story 03.0 |
| D15 | `init --user` creates the settings file; there is no `init --format json` | Story 03.0 |
| D16 | The settings location honours an absolute `XDG_DATA_HOME`, otherwise `$HOME/.local/share` | Story 03.0 |

### Contract 1: `Rule.opt_in_values` (plan C2)

This contract applies to `Rule` in `/src/docsentinel/rules.py`, which gains one field after
`opt_in_option`. It has a default, so positional and keyword construction of every existing rule
is unchanged:

```python
@dataclass(frozen=True)
class Rule:
    code: str
    profile: str
    title: str
    description: str
    severity: str = "warning"
    opt_in_option: str = ""
    opt_in_values: frozenset[str] = frozenset()  # enabling values; empty = legacy truthiness
```

**Registration invariants.** `register_rule()` enforces them and raises `ValueError`, like its
existing duplicate-code check:

- A non-empty `opt_in_values` requires a non-empty `opt_in_option`.
- Every enabling value is a `str` that matches `^[a-z0-9][a-z0-9_-]{0,31}$`. The values are
  literals defined in code, not user data. The pattern guarantees that the double-quoted rendering
  below never needs escaping and can never carry a control or bidi character.

**`opt_in_satisfied(rule, config) -> bool`.** The semantics are exact:

1. If `rule.opt_in_option` is empty, return `True`. This is unchanged.
2. Read `value = getattr(config, rule.opt_in_option, None)`. A missing attribute reads as `None`.
3. If `rule.opt_in_values` is non-empty, return `isinstance(value, str) and value in
   rule.opt_in_values`. The match is exact and case-sensitive, with no stripping or folding. The
   `isinstance` guard is required: an unhashable value, such as a list on a hand-built `Config`,
   must return `False` and must not raise `TypeError`.
4. Otherwise keep today's test: `bool(value) and value != "off"`.

Consequently, an injected `Config` with an unknown scope (for example `"STRICT"`) leaves DS103
inert. The notice still names DS103, so the result is never silently clean. `load_config()`
rejects such a value with `ConfigError("reference_scope must be one of: links, strict")`.

**`opt_in_hint(rule) -> str`.** This new helper in `/src/docsentinel/rules.py` is the single source of the hint
text:

| Rule shape | Returns | Example |
|---|---|---|
| `opt_in_option == ""` | `""` | ordinary rule |
| `opt_in_values` empty | `opt_in_option`, verbatim | `require_fence_languages` |
| one enabling value | `<option> = "<value>"` | `reference_scope = "strict"` |
| several enabling values | `<option> = ` followed by each value double-quoted, in `sorted()` order, joined with `" or "` | `x = "a" or "b"` |

**Where the hint is rendered.** Every one of these surfaces uses `opt_in_hint()`:

| Surface | Text (`<hint>` from `opt_in_hint`) |
|---|---|
| `ScanResult.notice` via `engine.evaluated_notice()` | `<code> (set <hint>)` in the `opt-in rule(s) not enabled:` list |
| `docsentinel rules` suffix (`cli._opt_in_suffix`) | ` [opt-in: set <hint>]` |
| Engine `WARNING` for an exact-code selection of an inert rule | `<code> is selected but evaluates nothing until <hint> is set` |
| Engine `INFO` rule-plan line | `<code> (<hint>)` in the `opt-in off:` list |
| `docsentinel doctor` summary | codes only; the format is unchanged |

`evaluated_notice(profile, rules_evaluated, opt_in_off)` keeps its signature. It looks up the
hint with `RULES.get(code)`. For a code that is not registered (a caller-built tuple), it falls
back to the option string verbatim, so it never raises.

**Byte-identity requirement.** DS110, DS112, DS115 and DS118 have empty `opt_in_values`, so their
hint is their option name. Their notice, `rules`, warning and plan text must not change by one
byte. A golden unit test pins the four legacy fragments, for example `DS110 (set
require_fence_languages)` and `[opt-in: set documentation_naming]`.

**Unchanged structured fields.** `ScanResult.opt_in_off` keeps its `(code, option)` shape. The
second element is the option name (`reference_scope`), never the hint. `rules_evaluated` keeps its
meaning. JSON schema 2 exposes `opt_in_off` as `[{"code": ..., "option": ...}]` with no new key.
DS100 stays in `rules.ENGINE_RULES` and is outside this mechanism.

### Contract 2: `AtReference` and `MarkdownBlockIndex.at_references` (plan C3)

The shared scanner `/src/docsentinel/markdown_blocks.py` gains one record and one field. Both are
additive and have defaults:

```python
@dataclass(frozen=True)
class AtReference:
    target: str            # token without "@", escaped spaces decoded, trailing punctuation stripped
    raw: str               # "@" plus the token exactly as written (finding value; untrusted)
    kind: str              # "relative" | "home" ("~/" start) | "absolute" ("/" start); plain str, not a Literal
    in_code_span: bool     # True for the whole-code-span form (D6)
    span: MarkdownSpan     # prose form: from the "@"; code-span form: the InlineCode span itself

@dataclass(frozen=True)
class MarkdownBlockIndex:
    ...                                         # existing fields unchanged, in order
    at_references: tuple[AtReference, ...] = ()  # new, last field, source order
```

- The grammar, bounds and exclusions are those of
  [Story 01.0, At-reference grammar](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md#at-reference-grammar),
  which this ADR adopts verbatim, including threat model amendment A2. In particular: the token is
  capped at 1,024 raw characters as written, a backslash not followed by a space ends the token, a
  token may not start or end with an escaped space, a `#` or
  `%` ends the token, no percent-decoding applies, the last component needs an extension with a
  letter, and nothing is recognised in fences, HTML comments, raw HTML tags, link text,
  destinations or labels, or after a backslash, letter, digit or `@`.
- `scan_markdown(text, path)` keeps its signature and stays config-free. It records every
  syntactic mention, whatever its extension. Filtering by `at_reference_extensions` is the
  consumer's job.
- `AtReference` is internal to the scanner module. It is not added to the public
  `docsentinel.__init__` API.

**Consumers:**

| Component | Use |
|---|---|
| DS124, in a new module, `mentions.py`, in the detectors package | Reads `relative` mentions whose lowercased extension is in `at_reference_extensions` and resolves them in two steps: relative to the document, then relative to the link root. Both steps go through `resolve_local_reference()` and `contained_path()` before a single `os.stat()` + `S_ISREG`. It never opens a target. `home` and `absolute` mentions are never probed. DS124 defers a mention to DS116, and skips step 2, only when DS116's mention classifier reports it: one shared ownership predicate in `/src/docsentinel/detectors/path_boundaries.py`, the same one DS116 uses. Any other `contained_path()` refusal (symlink cycle, hop overflow) or `OSError` means "does not resolve at this step" and is never propagated (threat model A4, M5, M10). A step-2 refusal gives no finding, only a `DEBUG` record (ruling R1). |
| DS116, `/src/docsentinel/detectors/path_boundaries.py` | Adds every `relative` mention, whatever its extension, to its candidates at full-reference strictness, resolved relative to the document. It drops a code span from its own code-span candidates only when the scanner recorded that exact span (by `MarkdownSpan` identity) as an `AtReference` with `in_code_span=True`, never by an `@` prefix, so each mention is classified once and a non-mention `@` span keeps its traversal check (threat model A1, M11). |
| DS103, `/src/docsentinel/detectors/paths.py` | Does not read the record. It adds `@` to its excluded span prefixes (today `-`, `$`, `>`). Apart from that, strict scope keeps it byte-for-byte. |

### Contract 3: DS124 rule, link root and fault class

- **Rule-code reservation:** DS124. DS107, DS111 and DS119 to DS123 stay reserved by
  Milestone 0004, and DS124 is the next free fast code. Registration (Task 05): `code="DS124"`,
  `profile="fast"`, `title="Dangling @-document reference"`, `severity="warning"`, with no
  `opt_in_option`.
- **Analyzer signature:** `detect(root, documents, config=None, *, link_root=None)`, the same as
  DS101. When `config` is `None`, defaults apply. On an injected `Config`, the analyzer
  re-validates `at_reference_extensions` and fails closed with `ConfigError`, like DS118.
- **Link root:** DS124 joins `LINK_ROOT_RULES` in `/src/docsentinel/link_root.py`, so the engine
  validates the link root once per scan and passes `link_root=`. If DS124 is called directly
  without it, it falls back to the lexical `link_root_for()`.
- **Finding:** `Finding(rule="DS124", path=<document>, message="dangling @-reference ->
  <bounded_raw>", severity="warning", line=<line of @>, column=<1-based code point of @ within the
  line>, value=<bounded_raw>, type="dangling document mention")`, where `bounded_raw` is `raw` cut
  to its first 200 characters with no truncation marker inside the token. `message` and `value`
  use the same bounded `raw`, so finding identity and baseline fingerprints stay bounded (threat
  model A3, M15). There is one finding
  per occurrence, in source order, and a mention repeated on the same line is reported once. In
  the text report it prints as
  `warning DS124 dangling document mention, line N, col M: <raw>`.
- **Fault class:** `dangling_reference`, the existing class shared with DS101. It counts toward the
  fabricated-reference aggregate in `/docs/specs/fault-classes.md` and needs a matching
  `FAULT_CLASSES` row in `/src/docsentinel/telemetry/classify.py`. The outcome is `advisory`, or
  `rejected` under `--strict`, like every warning.
- **Logging:** DS124 logs at `DEBUG` only, following `/docs/specs/logging.md`. A step-2
  containment refusal logs the document path through `safe()`, the line number and a fixed reason,
  never the mention text.

### Reference-scope matrix (plan C4)

| Rule | `"links"` (default) | `"strict"` |
|---|---|---|
| DS101 | on | on |
| DS103 | inert, named as opt-in not enabled | on; skips `@` spans |
| DS116 | on, including code-span traversal and mentions | same |
| DS124 | on | on |
| DS108, DS112, DS113, DS115 | unchanged | unchanged |

### Counts (corrected for DS100)

DS100 (an engine rule in `rules.ENGINE_RULES`) landed before this milestone. It is registered in
the fast profile, but it is not an analyzer and is not counted in the evaluated number. After this
story:

- `docsentinel doctor`: `fast rules: 18 registered (5 opt-in, off unless configured: DS103, DS110,
  DS112, DS115, DS118)`. Today it reports 17 registered and 4 opt-in.
- Default notice: `12 fast rule(s) evaluated; opt-in rule(s) not enabled: DS103 (set
  reference_scope = "strict"), DS110 (set require_fence_languages), DS112 (set
  navigation_indexes), DS115 (set deprecated_references_file), DS118 (set documentation_naming).`
  There are 17 analyzer rules, 5 of them off. Under `"strict"` the count is 13.

### Affected components and migration path

| Component | Change | Migration for callers |
|---|---|---|
| `/src/docsentinel/config.py` | Adds keys `reference_scope` and `at_reference_extensions` | None. The defaults apply when the keys are absent. |
| `/src/docsentinel/rules.py` | `Rule.opt_in_values`, the `opt_in_satisfied()` branch, `opt_in_hint()`, registration invariants | None. The field has a default and legacy rules behave the same. |
| `/src/docsentinel/engine.py` | The notice, plan line and warning use `opt_in_hint()` | None. Text is byte-identical for the four legacy rules. |
| `/src/docsentinel/cli.py` | `--reference-scope` on `scan` and `baseline`; the `rules` suffix; a `doctor` scope line; `reference_scope=` on the start `INFO` lines | Scripts that parse `doctor` see a new line and new counts. |
| `/src/docsentinel/markdown_blocks.py` | `AtReference`, `at_references` | None. The new field is last and has a default. |
| `/src/docsentinel/detectors/paths.py` | Opt-in registration; `@` prefix skip | Set `reference_scope = "strict"` or pass `--reference-scope strict` to keep DS103. |
| `/src/docsentinel/detectors/path_boundaries.py` | Mentions become DS116 candidates | New DS116 errors appear only for mentions that escape the root. |
| `mentions.py` in the detectors package (new), and the detectors package `__init__` import | DS124 | `ignore = ["DS124"]` silences it. |
| `/src/docsentinel/link_root.py` | DS124 joins `LINK_ROOT_RULES` | None. |
| `/src/docsentinel/telemetry/classify.py` | `FAULT_CLASSES` row for DS124 | None. |
| Baselines | DS103 fingerprints stop matching in the default scope; they are not an error | [Task 07](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/07-self-scan-and-baseline-migration.md) regenerates `/.docsentinel-baseline.json`. The standard baseline is untouched. |
| Pytest plugin, pre-commit hooks, report templates, JSON schemas | No code change. They inherit the new default through `scan()`. | Strict users add the key to their config. The hook `args:` are unchanged. |
| Library callers | No new `scan()` keyword | Use `dataclasses.replace(config, reference_scope="strict")`. |

### Consequences

- Good: the default self-scan drops from about 3,900 warnings to the findings people act on, and
  the fast baseline stops drifting.
- Good: agent mentions are checked, with their own code, severity and `select`/`ignore` handle.
  DS101 baselines and semantics do not move.
- Good: the opt-in mechanism now supports enum-valued options, which a future scope can reuse
  without a new key or reporting path.
- Good: each mention has one owner. DS116 reports escapes, DS124 reports missing files and DS103
  never sees `@` spans.
- Bad: this is a behaviour change on upgrade. Default scans stop reporting DS103. Teams that relied
  on it must opt in. It is mitigated by the notice, `doctor` and the release note (D7).
- Bad: `evaluated_notice()` now reads the `RULES` registry, so it is no longer a pure function of
  its arguments. An unregistered code falls back to the option name.
- Bad: JSON `opt_in_off[].option` carries `reference_scope` without the enabling value. A JSON
  consumer that wants `"strict"` must read the notice or `docsentinel rules`. This is deliberate,
  because a schema change is a non-goal.
- Bad: the scanner gains a second recognition pass over prose, which adds hot-path cost and attack
  surface. It is bounded (linear, a 1,024-character cap, no regex built from input) and goes
  through the threat model in Task 02.
- Bad: the D6 code-span form differs from Claude Code, which does not import such spans. The docs
  must state this difference.
- Neutral: DS124 is a `warning`, so it blocks only under `--strict`. D3 is to be revisited after
  one release.

## Pros and Cons of the Options

### (a) `reference_scope` mode, DS103 opt-in, new DS124 (chosen)

- Good: it removes the noise by default and stays honest, because the existing opt-in surfaces
  name DS103.
- Good: a named mode, not a toggle, so it can be extended (S1).
- Good: a separate rule code keeps DS101 baselines and selection stable (D2).
- Bad: it needs a small generalisation of the opt-in contract (`opt_in_values`) and a new rule
  module.
- Bad: default output changes on upgrade.

### (b) Keep DS103 on and tune its heuristics

- Good: no new key, no default change, and no new rule.
- Bad: identifiers, foreign-base paths and example paths cannot be told apart syntactically, so
  every heuristic trades false positives for false negatives. Milestone 0008 Story 05.0 already
  owns that triage.
- Bad: mentions remain unchecked, or are wrongly checked as relative paths.
- Bad: the baseline keeps drifting while the tuning is iterated.

### (c) Boolean `check_code_span_paths`

- Good: it fits today's truthiness-based opt-in with no `Rule` change.
- Bad: a boolean names a detector detail, not a policy. A future scope would need another key, and
  then the interactions between keys would need rules of their own.
- Bad: it does nothing about mentions.

### (d) Fold mentions into DS101

- Good: no new rule code and it reuses DS101's resolver path.
- Bad: mentions inherit DS101's severity and baselines. Selecting or ignoring DS101 would also
  switch mentions, so existing `ignore = ["DS101"]` configs would silently drop them.
- Bad: DS101's anchor and fragment semantics do not apply to mentions (no fragment checking is a
  non-goal), so the rule would carry two resolution models.
- Bad: new DS101 findings on upgrade would change the meaning of existing DS101 baselines and
  dashboards.

## Validation / Rollout

- `python scripts/check_doc_links.py docs` reports 0 problems.
- The acceptance criteria of
  [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md#acceptance-criteria),
  including a self-scan with 0 DS103 and 0 DS124 findings in the default lane, byte-identical
  legacy notice text, and no filesystem call for `home`/`absolute` mentions.
- The ADR moves to `Accepted` once the owner signs off and the Security Auditor's Task 02 verdict
  is PASS or PASS_WITH_FOLLOWUP.

Follow-up tasks:

| Task | Owner | Deliverable |
|---|---|---|
| [02](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/02-threat-model-at-references.md) | Security Auditor | Threat model for mention recognition and resolution; runs before any code |
| [03](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/03-reference-scope-config-and-opt-in-values.md) | Python Expert | Config keys, `--reference-scope`, Contract 1 (`opt_in_values`, `opt_in_satisfied`, `opt_in_hint`, registration invariants), DS103 opt-in, notice, `rules`, `doctor` |
| [04](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/04-at-reference-scanner.md) | Python Expert | Contract 2 in the shared scanner |
| [05](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/05-ds124-detector-and-ds103-ds116-integration.md) | Python Expert | Contract 3: DS124 detector, DS116 and DS103 integration, `LINK_ROOT_RULES`, `FAULT_CLASSES`, the rules table row |
| [06](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/06-fixtures-and-tests.md) | Testing Expert | Assets and unit, mock and integration tests, including the golden test for the four legacy opt-in texts, the `opt_in_satisfied` `isinstance` guard, the registration invariants and the `opt_in_hint` multi-value ordering |
| [07](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/07-self-scan-and-baseline-migration.md) | Python Expert | Before and after self-scan counts; fast baseline regenerated |
| [08](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/08-docs-and-release-notes.md) | Docs Writer | User docs, specs, README, CLAUDE.md, release-notes proposal for 1.3.0 |

**Diagram follow-up for `diagram-creator`.** Run it after Task 05 lands, because
`/docs/diagrams/` shows the as-built package:

- `/docs/diagrams/component/detectors/component-detectors.puml`:
  - Add a `mentions.py DS124` box in the fast group, with edges to `/src/docsentinel/markdown_blocks.py`
    (`at_references`, `resolve_local_reference`) and to `/src/docsentinel/detectors/path_boundaries.py` (`contained_path`,
    `is_ds116_owned`), plus the `link_root` input.
  - Relabel DS103 as `opt-in: reference_scope = "strict"`.
  - Add `AtReference` to the `/src/docsentinel/markdown_blocks.py` label.
  - Note that DS116 now also takes mentions.
- `/docs/diagrams/component/overview/component-overview.puml`: check the fast-group note on
  registered rules. No structural change is expected.
- `/docs/diagrams/component/reporting/component-reporting.puml`: no change.
- `/docs/architecture/README.md` has no Mermaid diagram, so its prose is updated by Task 08.
- Optional new diagram: `sequence/ds124-at-reference-resolution`, showing the two-step resolution
  with containment gates.

## Links

- **Roadmap story/task:**
  [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md),
  [Task 01](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/01-adr-and-rule-contract.md),
  [Milestone 0009 plan, shared contracts](/docs/roadmap/0009-improvements/plan.md#shared-contracts-authoritative)
- **Supporting specs:** [rules table](/docs/user/reference/rules.md),
  [fault classes](/docs/specs/fault-classes.md), [finding types](/docs/specs/finding-types.md),
  [logging](/docs/specs/logging.md), [architecture](/docs/architecture/README.md)
- **Threat model:** [Story 01.0 threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md)
  (amendments A1 to A4 and ruling R1 are applied in Contracts 2 and 3)
- **Related ADRs:** [0003 - Template-Driven Reporting](/docs/adr/0003-template-driven-reporting-on-telemetry.md)
  (no report schema change here)
- **Diagrams:** [component diagrams](/docs/diagrams/README.md); the follow-up is above
