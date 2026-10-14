# Task 03 — Per-rule readiness, unsupported evidence and deep gating

## Current blocker

In current master, `engine.scan` checks `deep_ready()` (spaCy+textacy+model) *before* selecting rules. This would make model-free DS302 and DS316 unusable without NLP dependencies, contradicting their deterministic/static design.

## Implement

- Resolve profile+select+ignore first, still requiring deep confirmation before running *any* deep rule.
- Add per-rule capabilities: `DS301` = spaCy/textacy+en_core_web_sm; `DS302` = pure numeric extractor; `DS316` = explicit changed_paths plus static references. Never auto-download model.
- If a confirmed mixed run selects DS301/DS302/DS316 but model is missing, execute DS302/DS316 and report DS301 skipped with a cause. If no changed paths were supplied, mark DS316 'not evaluated' independently, leaving other deep findings intact.
- Keep deep candidates `warning` and always advisory; `--strict` does not make deep findings exit 1. Malformed config and unsafe paths still return exit 2.
- Expose execution statuses in Python API/JSON in a backward-compatible way; update text and GitHub output and `doctor` rule-readiness details. Existing `pending` field may be reused if semantics are unambiguous, but do not state all selected rules were evaluated if they were not.
- Ensure no eager spaCy/model imports from `docsentinel`, CLI, or fast/standard detectors.

## Tests

- `deep` without confirmation: selected DS302 does no work; actionable pending.
- Confirmed DS302-only: works without spaCy installed/model; produces candidate when fixture contradicts.
- Confirmed DS316-only: works without spaCy; missing changed paths is explicit pending.
- Confirmed mixed DS301+DS302 lacking model: DS302 evaluated, DS301 pending.
- Model present: DS301 existing tests continue to pass; advisory exit under strict.
- Invalid path/config: exit 2; unsupported cases never counted as successful audits.
