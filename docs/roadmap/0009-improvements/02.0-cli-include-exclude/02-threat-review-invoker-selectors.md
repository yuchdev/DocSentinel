# Task 02 — Security review: invoker selector normalisation and containment

**Parent story:** [Story 02.0](/docs/roadmap/0009-improvements/02.0-cli-include-exclude/README.md)  
**Role:** Security Auditor  
**Depends on:** Task 01. Must finish before Task 03.

## Inputs

- Story README "Selector grammar" (normalisation table), "Security notes", "Edge cases".
- `/src/docsentinel/detectors/path_boundaries.py` (`contained_path()`), `/src/docsentinel/cli.py`
  (`_resolve_root()`, `_origin_spellings()`), `/src/docsentinel/link_root.py`
  (`resolve_invoker_link_root()`, the trusted-invoker precedent).

## Steps

1. Model the inputs: a person at a terminal (trusted), a repository's pre-commit configuration
   passing `args:` (repository-controlled), a CI workflow, a library caller.
2. Check each threat and state the mitigation and a test name:
   - escaping the scan root through `..`, absolute paths, symlinked components, Windows drive, UNC
     or rooted-backslash forms, Unicode look-alike separators (U+2215, U+FF0F) and NUL;
   - an existence oracle outside the root through `os.lstat()`;
   - hiding documents: a repository-controlled exclude in pre-commit args has the same power as the
     repository's config file, so it is not a new capability (record as accepted);
   - cost: 256 values times `fnmatchcase()` per path; worst-case glob shapes;
   - log and stderr injection through echoed values.
3. Verdict PASS, PASS_WITH_FOLLOWUP or BLOCK; a CRITICAL finding stops the story.

## Files

- New review under `/docs/security/` named with the topic and date.

## Verification

- Every mitigation maps to a test in Task 05 or an acceptance criterion.

## Acceptance

- [x] Review written with a verdict; Task 03 briefing references it.

## Amendment (ADR 0006, 2026-11-18)

Review Contract 3 of
[ADR 0006](/docs/adr/0006-invoker-include-exclude-and-directory-selectors.md) and rule on these
points, recording each ruling in the review and in the ADR's open-points table:

- **O2:** absolute values are made relative **lexically** against the resolved scan root and the
  root as the caller spelled it, with no `realpath()` or `stat()` of a value before it is known to
  lie inside the root. This replaces Task 03 step 4's "parent resolved with
  `os.path.realpath()`" unless this review rules otherwise.
- **O6:** a literal include reached through an **in-root** symlinked directory component (detected
  when `contained_path()` returns a path that differs from the lexical one) exits `2` ("symlinked
  paths are not inventoried"); a literal exclude reached that way is kept and reported as
  unmatched.
- **U+2215 and U+FF0F:** ADR 0006 treats these look-alike separators as ordinary name characters,
  never separators. Confirm that no step (normalisation, `contained_path()`, `fnmatchcase()`) can
  turn them into a path separator, or require refusing them.
