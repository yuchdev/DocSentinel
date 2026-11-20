# Task 02 — Threat model: `@`-reference recognition and resolution

**Parent story:** [Story 01.0](/docs/roadmap/0009-improvements/01.0-reference-scope-and-at-references/README.md)  
**Role:** Security Auditor  
**Depends on:** Task 01 (ADR). Must finish before Task 03.

## Inputs

- Story README: "At-reference grammar", "Resolution (DS124)", "DS116 and DS103 changes",
  "Security notes".
- Existing models: `/docs/security/threat-model-ds116-path-boundaries-2026-10-22.md` and the
  helpers `contained_path()`, `escapes_via_symlink()`, `is_ds116_owned()` in
  `/src/docsentinel/detectors/path_boundaries.py`; the link-root bounds in
  `/src/docsentinel/link_root.py`.

## Steps

1. Enumerate assets and attackers: a contributor who controls document text in a scanned
   repository (untrusted), the invoker (trusted), CI runners.
2. Threats to cover, each with a mitigation that becomes an acceptance criterion:
   - existence oracle outside the scan root on step 1, or outside the link root on step 2;
   - symlink-out on step 2 (a link-root path whose component is a symlink leaving the link root);
   - home and absolute mentions probing the invoker's home directory;
   - recognition cost (pathological lines, very long tokens, many `@` characters);
   - backslash-space decoding producing separators or control characters;
   - finding value and log injection (control, bidi and zero-width characters in the token);
   - TOCTOU between DS116's lexical gate and DS124's `os.stat()` (parity with DS101);
   - a mention that resolves through the fallback to a sensitive in-repository file (information
     disclosure is nil: only existence is used, nothing is read).
3. Rate each threat, give the mitigation and a test name for the Testing Expert.
4. Give a verdict for the design: PASS, PASS_WITH_FOLLOWUP or BLOCK. A CRITICAL finding stops the
   story until the owner signs off.

## Files

- New threat model under `/docs/security/` named with the topic and date (for example
  threat-model-0009-at-references-YYYY-MM-DD.md).

## Verification

- Every mitigation maps to an acceptance criterion or a test in Task 06.
- `python scripts/check_doc_links.py docs/security docs/roadmap` reports 0 problems.

## Acceptance

- [ ] Threat model written; mitigations numbered; verdict given.
- [ ] Task 03 and Task 05 briefings reference it as a standing input.
