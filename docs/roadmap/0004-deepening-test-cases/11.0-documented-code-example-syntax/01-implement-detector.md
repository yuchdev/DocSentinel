# Task 01 — Implement `DS219`: Documented code example syntax

**Story:** [Story 11.0](/docs/roadmap/0004-deepening-test-cases/11.0-documented-code-example-syntax/README.md) · **Rule:** `DS219` · **Profile:** `standard`

## Deliverable and location

Implement `src/docsentinel/detectors/standard/examples.py` (new module unless a preexisting equivalent is found during implementation). Register `Rule(code="DS219", profile="standard", severity="error", ...)` through the existing rule registry, and bind exactly one detector under `ANALYZERS["DS219"]`. Preserve lazy imports and existing rule identities.

## Inputs and well-defined outputs

**Input source:** Markdown fenced code blocks and optional check=syntax info attribute.

**Success:** a deterministic tuple of `Finding` objects with `rule="DS219"`, normalized repo-relative paths, correct 1-based lines (where known), evidence-focused messages and severity `error`.

**Not evaluated:** Missing mandatory config, unsupported source construct, or missing scan context must not silently turn into an assertion that the documentation was checked and found clean. Emit a clear pending/readiness or validation outcome using the milestone's shared per-rule execution status mechanism. **Do not** abuse `Finding(severity="error")` to mean 'could not analyze'.

## Algorithm contract

Algorithm: scan Markdown fence delimiters and info strings, preserving exact start line; validate only `check=syntax` explicitly marked complete blocks in v1 (unless separately configured full opt-in). Route Python through ast.parse, JSON through json.loads and TOML through tomllib.loads. Translate parser-local (line,column) positions to Markdown absolute lines. Unmarked snippets and unsupported languages are not evaluated; no execution, subprocess, shell or import of example contents.

## Detailed implementation obligations

1. Extract fenced blocks with original source-line offsets and info string tokens; allow backticks and tildes.
2. Implement safe parser adapters for Python, JSON and TOML; opt-in completeness via fence attribute.
3. Handle unsupported languages, partial snippets and size budgets as explicit not-evaluated conditions.
4. Prohibit dynamic execution and external interpreters; ensure no fence content is evaluated.

## Settings and parsing

**Proposed configuration fields:** example_languages: tuple[str,...] (default python,json,toml); example_check_mode: str (default explicit).

Config work includes updating `Config`, `_CONFIG_OPTIONS`, both TOML loading paths, documented defaults, bad-config tests, and the existing example config. A rule that requires explicit mappings/dictionaries must be idle with an honest pending/readiness explanation until configured; it cannot implicitly reinterpret every README as an API contract. Existing configs continue loading untouched.

## Work with the current implementation

- `engine.scan` currently calls fast/deep analyzers with two arguments and standard ones with three. Follow Story 01.0's uniform optional-context contract before introducing a rule whose behavior depends on programmatic `Config` overrides.
- Use the already-implemented code paths where appropriate: `discovery.py`, `rules.py`, `code_discovery.py`, `detectors/standard/corpus.py`, `deep_support.py`, and `baseline.py`; do not silently duplicate a heavyweight index.
- No new runtime libraries in `fast`; standard only loads on demand; deep remains explicitly opt-in/advisory. Non-LLM by default in every rule.
- Favor explainable measurements and evidence. Any approximation is documented as a **candidate** rather than an authoritative contradiction.

## Security, negative scope and boundary checks

No `exec`, `eval`, subprocess or shell invocation; this rule cannot prove runtime correctness.

- Parse Markdown and Python source without executing it. Sanitize/normalize paths and reject scan-root escapes before I/O.
- Avoid reading generated fixture assets from the repository self-scan; fixture directories belong only to tests.
- No background agent, git invocation, secret file harvesting or remote request from a detector.

## Example Markdown test evidence


### Required fixture path examples

- Positive: `tests/assets/ds219/valid_python_example/README.md` — Complete ```python check=syntax fenced code parses with ast.parse.
- Negative: `tests/assets/ds219/invalid_python_indentation/README.md` — Explicit Python example contains indentation SyntaxError; flag precise line.

The asset files are **required PR deliverables**. A rule implementation without those files and tests loading each case does not satisfy this story.


## Definition of done

- [ ] Rule registered exactly once, and selected/ignored predictably.
- [ ] Config options validated; default settings are conservative and backward compatible.
- [ ] Source line/provenance is preserved; reports are deterministic and privacy-conscious.
- [ ] Direct analyzer unit tests cover parser boundaries and specific error scenarios.
- [ ] Task 02 fixture tests prove no false positive on 3+ clean scenarios and detection on 3+ failing scenarios.
- [ ] README/architecture/rules output explains behavior and limitations.
