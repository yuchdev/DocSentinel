# Task 05 — DS124 detector; DS116 and DS103 integration

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Python Expert  
**Depends on:** Tasks 03 and 04; the Task 02 threat model is a standing input.

## Inputs

- Story README "Resolution (DS124)", "DS124 rule contract", "DS116 and DS103 changes" (with
  amendments A1, A3 and A4 and ruling R1 applied).
- [Threat model](/docs/security/threat-model-0009-at-references-2026-11-14.md) (standing input):
  M1 to M7, M9 to M11, M14 to M17 and M21, and the merge-gate BLOCK conditions in its Verdict.
- `/src/docsentinel/detectors/links.py` (DS101: the pattern for `link_root` handling, containment
  and finding fields), `/src/docsentinel/detectors/path_boundaries.py`,
  `/src/docsentinel/detectors/paths.py`, `/src/docsentinel/link_root.py`,
  `/src/docsentinel/telemetry/classify.py`, the detector imports in the detectors package init.

## Steps

1. New module mentions.py in the detectors package: register DS124 exactly as the story contract
   says; `detect(root, documents, config=None, *, link_root=None)` with the same signature shape as
   DS101; per document read text as DS116 does, call `scan_markdown()`, filter `relative` mentions
   by `at_reference_extensions`, resolve per the two-step algorithm with `contained_path()` before
   every `os.stat()`, report with `S_ISREG`. On step 1, defer to DS116 (and skip step 2) only when
   DS116's own mention classifier reports the mention, through the one shared ownership predicate
   in `/src/docsentinel/detectors/path_boundaries.py`; any other `contained_path()` refusal or any
   `OSError` means "does not resolve at this step" and is never propagated (A4). A step-2 refusal
   produces no finding, only a `DEBUG` record (ruling R1). `message` and `value` both echo `raw`
   cut to 200 characters (A3). Re-validate `at_reference_extensions` for an injected
   `Config` (fail closed with `ConfigError`). Log per document at `DEBUG`: counts of mentions,
   findings and skipped (home, absolute, extension, outside link root); never the mention text.
2. Import the module where the other fast detectors are registered so `RULES` and `ANALYZERS`
   contain DS124 after `import docsentinel`. Results tests (Task 06) must exist before this
   registration is merged (detector registration gate).
3. `/src/docsentinel/link_root.py`: add DS124 to `LINK_ROOT_RULES`.
4. `/src/docsentinel/detectors/path_boundaries.py`: in `check_text()`, add each `relative` mention from
   `index.at_references` as a full-reference candidate (not code-span narrowed); exclude a code
   span from the existing code-span candidates only when the scanner recorded that exact span (by
   `MarkdownSpan` identity) as an `AtReference` with `in_code_span=True`, never by an `@` prefix
   (A1). Expose the mention classifier as the single shared ownership predicate DS124 calls.
5. `/src/docsentinel/detectors/paths.py`: add `@` to the excluded code-span prefixes in `_is_excluded()`.
6. `/src/docsentinel/telemetry/classify.py`: `FAULT_CLASSES["DS124"] = "dangling_reference"`.
7. Add the DS124 rows to `/docs/user/reference/rules.md`, `/docs/specs/fault-classes.md` and
   `/docs/specs/finding-types.md` in the same change (drift tests), and update the fast range in
   the "Profiles at a glance" list.
8. Report a `Docs impact:` line (R, A: new detector module).

## Files

New detector module in `/src/docsentinel/detectors/`; `/src/docsentinel/detectors/path_boundaries.py`,
`/src/docsentinel/detectors/paths.py`, `/src/docsentinel/link_root.py`,
`/src/docsentinel/telemetry/classify.py`, the detectors package registration import,
`/docs/user/reference/rules.md`, `/docs/specs/fault-classes.md`, `/docs/specs/finding-types.md`.

## Verification

- Task 06 tests for DS124, DS116 and DS103 pass with `-q`.
- Existing DS116 and DS103 suites pass unchanged (no regression in their fixtures).
- `uv run docsentinel scan . --format json` exits `0`.

## Acceptance

- [ ] DS124 appears once in `RULES` and `ANALYZERS` with the contract metadata.
- [ ] A mention is classified by exactly one of DS116 (escape) or DS124 (missing), never both;
      a symlink-cycle or hop-overflow mention is one DS124 finding, and only a step-2 refusal
      gives neither (ruling R1).
- [ ] An `@`-prefixed code span that is not a recorded mention keeps its DS116 traversal check.
- [ ] DS103 strict output is identical to today's except `@` spans.
- [ ] All three drift tests (rules table, fault classes, finding types) pass.
