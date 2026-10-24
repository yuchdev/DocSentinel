# Technical Handoff: Future DS2xx Lexical/Editorial Checks and DS3xx Semantic Checks

This document captures what was built in Milestone 0005, what shared
infrastructure exists, what is missing, and the hazards found during
implementation. It is a handoff note for the engineers who will implement
further DS2xx and DS3xx rules; it does not implement any new rule.

---

## What Milestone 0005 delivered

Thirteen new fast-profile rules registered and fully tested:

| Rule | Profile | Severity | Opt-in | Subject |
|------|---------|----------|--------|---------|
| DS104 | fast | warning | no | Anchor identity and collisions |
| DS105 | fast | warning | no | Heading hierarchy |
| DS106 | fast | warning | no | Contentless sections |
| DS108 | fast | warning | no | Reference definition integrity |
| DS109 | fast | error | no | Malformed fenced code blocks |
| DS110 | fast | warning | `require_fence_languages` | Missing fence language labels |
| DS112 | fast | warning | `navigation_indexes` | Navigation integrity |
| DS113 | fast | error | no | Missing local assets |
| DS114 | fast | error | no | Duplicate document identifiers |
| DS115 | fast | warning | `deprecated_references_file` | Deprecated references |
| DS116 | fast | error | no | Path traversal outside root |
| DS117 | fast | warning | no | Malformed pipe tables |
| DS118 | fast | warning | `documentation_naming` | File/directory naming policy |

A shared `markdown_blocks.py` scanner backs DS104–DS118 (DS114 carries its
own bounded frontmatter reader because DS111 is absent). DS101–DS103 have not
been refactored onto the shared scanner.

The existing standard-profile rules (DS201–DS204) and the deep-profile rule
(DS301) are unchanged by Milestone 0005.

---

## Shared infrastructure for future rules

### `markdown_blocks.py` scanner

Available to any future rule at zero extra cost:

- All token types in `MarkdownBlockIndex` (see
  [docs/dev/markdown_scanner.md](../../dev/markdown_scanner.md)).
- `resolve_local_reference` — purely lexical path resolver.
- `is_ds116_owned` / `escapes_via_symlink` — filesystem containment helpers.
- `fenced_line_numbers()` mask.
- `split_physical_lines()` for line-aligned iteration.
- `backtick_runs`, `find_code_spans` — backtick-run indexing shared by DS117
  and the scanner; O(n) on a single line.

### Config options available for future rules

DS112 (`navigation_indexes`), DS115 (`deprecated_references_file`), and DS118
(`documentation_naming`) are registered as opt-in rules with their options
already validated by `load_config`. When a future rule needs a similar opt-in
pattern, use the same `opt_in_option` field in `rules.Rule`.

All 44 typed policy options from Milestone 0005 are fully defined and validated
in `config.py`. Options consumed by DS112, DS115, and DS118 may overlap with
future editorial rules.

### Test infrastructure

- `tests/timing_helpers.py` — `assert_scales_linearly` helper (CPU time,
  best-of-3, per-doubling slope ≤ 1.4, max ratio guard 6.0). All flood tests
  in the existing suite use this; new rules must too.
- `tests/milestone_0005_manifest.py` — registration-gated fixture catalog.
  New rules must register their scenarios here; a rule registered without its
  fixture directories fails the catalog test, and committed directories for an
  unregistered rule also fail.
- `tests/reference/*.py.txt` — frozen oracle copies of pre-Story-11 DS101 and
  DS103 behaviour used for parity tests. Do not refresh; they are the regression
  guards.

---

## What is missing (constraints for DS2xx/DS3xx authors)

### DS101 and DS103 are not on the shared scanner

DS101 and DS103 were not refactored onto `markdown_blocks.py` during Milestone
0005. Their fence-closing semantics differ from the shared scanner (DS101 closes
on the first same-marker line; the scanner requires a closer run length ≥ opener
with an empty info string). Reconcile this before attempting to share scanner
tokens between old and new rules.

### DS111 (metadata validation) is absent

DS114 carries a minimal, standard-library-only frontmatter reader because DS111
(the metadata-validation rule from Milestone 0004) is not implemented. DS114's
reader is deliberately conservative: it defers ambiguous cases silently rather
than guessing. If DS111 lands, DS114's reader can be simplified to delegate
malformed-metadata cases to DS111.

### No per-document or corpus-level findings cap

All fast-profile rules (including DS102, DS104, DS116, DS117) can emit one
finding per occurrence with no upper bound. A hostile 2 MB file can produce
hundreds of thousands of findings and a JSON report of hundreds of megabytes.
An engine-level per-rule per-document findings cap was noted in Milestone 0005
stories 02.0 and 08.0 but was not implemented. This is a correctness issue for
adversarial inputs; implement it before any rule that is expected to run on
untrusted repositories.

### No per-file or corpus-level size cap

The engine reads every discovered file in full. A 100 MB Markdown file is read
entirely into memory before any detector touches it. Noted in stories 03.0 and
06.0; a document-size cap before `.read()` reduces ~140× memory amplification
to a bounded constant. Implement before a deep or standard-profile rule that
processes every document.

### spaCy eager import (resolved in Story 15.0)

Resolved: `contradictions.py` now imports its spaCy-dependent `_triples` module
lazily via `importlib.import_module` on the first deep scan call (see the `detect()`
docstring). `import docsentinel` no longer imports spaCy at module load; fast and
standard scans never pull in spaCy or textacy.

**Remaining open item:** `pyproject.toml` still lists `spacy>=3.8.16` as a core
runtime dependency, so every `pip install docsentinel` still installs spaCy. Removing
spaCy from the core dependencies is a product decision deferred to the next release;
it does not affect scan correctness.

### Two table parsers

DS117 contains its own self-contained table parser because the shared scanner's
`TableRow` tokens split cells on pipes inside backtick code spans. DS106's
section-extent computation still uses the scanner's `TableRow` tokens. These two
parsers are a maintenance hazard; unify them (fix the scanner tokens or reuse
DS117's parser) before adding a third table-aware rule.

---

## Hazards found in Milestone 0005

These are non-obvious pitfalls discovered during implementation. Future rule
authors should read them carefully.

### Comment-masking evasion (scanner level)

An unclosed HTML comment opener inside an inline code span was silently treated
as a multi-line HTML comment running to end-of-file, making every reference
after it invisible to DS116, DS101, and DS104. Fixed in Story 11.0 close. The invariant
now enforced: a mid-line HTML comment opener is a comment only if a closer
`-->` follows it within the same paragraph; otherwise it masks nothing. Any scanner construct
that could silence a later region must be tested with inline-code masking.

### Shared-prefix quadratic matchers

DS115 (deprecated references) hit a per-entry × per-document-token quadratic
when many `old` tokens shared a first token (first-token buckets). Fixed by
replacing the bucket approach with a per-kind token trie. Any detector that
iterates a list of patterns per document position must use trie/suffix-array
indexing, not a linear scan over the pattern list.

### Backtick-run quadratic (global)

The shared scanner's `_find_inline_code` and DS117's cell-splitter both hit
O(n^1.5) CPU on one line of strictly increasing backtick-run lengths. Fixed in
Story 08.0 with the shared `backtick_runs`/`first_backtick_run_at_or_after`
index. Any new rule that processes backtick spans must reuse this index, never
re-scan the line for matching runs.

### HTML comment-per-line masking (O(lines × comments))

DS104's `_mask_line` iterated every comment range per line: 20 000
single-line comments timed out. Fixed with a forward-only cursor. The pattern
to follow: any masking step that walks a document-global collection per line
must use a cursor or merge-interval approach, never a per-line search.

### Timing guard self-test in a large process

The `assert_scales_linearly` helper discriminates quadratic from linear code
using CPU-time measurements. When run inside the full-suite process (which keeps
spaCy/scikit-learn loaded: ~3 M tracked objects), GC pauses add a roughly-linear
term proportional to the heap that can flatten the fitted slope. Fix: GC is
disabled for each timed run and re-enabled after. Any new adversarial test must
run in the same conditions as the full suite; validate the guard **inside a full-
suite-sized process**, not only in isolation.

---

## Suggested order for future rules

### DS2xx lexical/editorial checks

These rules read Markdown content (not statistical models) and would sit in the
`fast` or `standard` profile depending on whether they require heavy
dependencies.

Recommended prerequisites:
- Implement the engine-level per-document findings cap.
- Implement the document-size cap.
- spaCy eager import: resolved in Story 15.0 — DS301 imports its spaCy-dependent `_triples` module lazily; remaining open item: `spacy` is still a core `pyproject.toml` dependency (product decision for next release).

Candidate rules (from the Milestone 0004 specification in
`docs/roadmap/0004-deepening-test-cases/plan.md`):

| Rule | Subject | Shared infra available |
|------|---------|------------------------|
| DS111 | YAML frontmatter metadata validation | DS114's reader is a start; defer to a real YAML parser |
| DS107 | Orphan documentation (unreachable from navigation) | DS112's navigation graph; requires index traversal |
| DS119 | Unresolved migration markers (TODO/FIXME/WIP in content) | `markdown_blocks.py` masked text; word tokenizer from DS115 |
| DS120 | Terminology consistency (variants of the same term) | DS115's trie matcher; needs a configurable synonym mapping |
| DS121 | Repeated document sections (duplicate heading+body pairs) | DS106's section extents; cross-document comparison |

### DS3xx semantic checks

These rules use NLP models and belong in the `deep` profile.

- **DS301** (fact-contradiction candidates) is already registered and gated
  by `deep_confirm`. It uses `spacy` and `textacy` for SVO extraction. It is
  advisory-only (exit code 0 always).
- Future DS3xx rules should follow the same deep-profile pattern: explicit
  opt-in, lazy model loading via `ensure_deep_loaded()`, advisory-only exit
  codes, and a clear user-facing warning that findings are heuristic candidates
  for human review.

Key constraint: resolved in Story 15.0 — `contradictions.py` now imports `_triples`
(and thus spaCy) lazily on the first deep scan call; `import docsentinel` and fast
and standard scans no longer pull in spaCy. Remaining open item: `spacy` is still
listed as a core dependency in `pyproject.toml`, a product decision for the next
release.

---

## Open questions for the next milestone

1. **Policy-off rules in `ScanResult.notice`**: Rules silenced by a policy
   option (`root_escape_policy = "off"`, `table_enable = false`, etc.) are
   still counted as evaluated. Should they be reported like opt-in rules? The
   distinction matters for audit trails.

2. **Findings and document-size cap**: What is the right cap? The engine needs
   a per-rule per-document cap (to bound JSON output size), a per-scan total
   cap (to bound memory), and a document-size cap before `.read()` (to bound
   memory amplification). These three caps interact with baseline
   fingerprinting.

3. **DS103 glob/template noise**: DS103 currently reports path-like code spans
   that look like glob patterns or template strings. Dropping this noise was
   noted as potentially desirable in Story 11.0 but was not done; any change
   must be deliberate and tested against the frozen oracle in
   `tests/reference/`.

4. **Baseline staleness**: The committed fast and standard baselines predate the
   Milestone 0005 roadmap docs (they contain thousands of DS103/DS202 findings
   on them). These should be regenerated or the roadmap docs excluded before a
   public release.

> **SME REVIEW NEEDED:** Confirm the ordering suggestion for DS2xx rules above
> matches current architectural priorities.
