# Task 02 — Facts template context, packaged `facts-text`/`facts-json`, `render_facts()`

**Parent story:** [Story 05.0](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md)  
**Role:** Python Expert. The Security Auditor reviews the loader delta (step 6) before merge.  
**Depends on:** [Task 01](./01-shared-candidate-collection-and-public-api.md) (`FactExtractionResult`).

## Goal

Render fact-extraction output through the existing template engine, with no format branch, layout
literal or `json.dumps` in Python. This keeps the CLAUDE.md "No hardcoded output format" convention
and the loader's untrusted-text sink rules, so claim text is neutralised.

## Inputs

- Story [decision X9](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#decisions) and
  [facts template context](/docs/roadmap/0010-fact-check/05.0-extract-facts-cli/README.md#facts-template-context-facts_context_schema-task-02).
- `/docs/specs/report-template-format.md`, `/src/docsentinel/telemetry/loader.py`
  (`Template`, the `template()` validator, `CONTEXT_SCHEMA` use, `packaged_template_names()`),
  `/src/docsentinel/telemetry/model.py` (`ReportModel`, `CONTEXT_SCHEMA`, trust tags),
  `/src/docsentinel/telemetry/engine.py`, `/src/docsentinel/reporting.py`.
- `/docs/security/threat-model-0007-template-engine-2026-10-31.md` (mitigations M1–M14).
- `tests/unit/test_reporting_has_no_format_literals.py` (the AST tripwire).

## Steps

1. **Loader `context` key.**
   - Add an optional top-level key `"context"`, valid for both `text` and `json` templates, with
     the values `"report"` (default) and `"facts"`. Any other value raises `TemplateError`
     (`context must be "report" or "facts"`).
   - `Template` gains `context: str = "report"`.
   - The validator checks variables against `CONTEXT_SCHEMA` for `report` and
     `FACTS_CONTEXT_SCHEMA` for `facts`. A variable from the other schema is an unknown variable.
   - A `facts` template with a non-empty `requires_extensions` raises `TemplateError`.
   - Every other rule is unchanged and applies to both contexts: M1–M14, the sinks, the literal
     hygiene and the file gate.
   - **Amended 2026-11-24 (threat model, E4).** One function, `schema_for(context: str)`, returns
     the schema for a context. Both root scopes (the text placement scope and the json scope), the
     alias checks (`_alias`) and the `ext` resolution all call it; none names `CONTEXT_SCHEMA`
     directly. `FACTS_CONTEXT_SCHEMA` has no `ext` entry, and in a `facts` template both
     `requires_extensions` and every `ext.*` filter or variable are refused with `TemplateError`.
     A `facts` template with `output.sink: github` obeys the 0007 T2-R1 rules unchanged.
2. **`telemetry/facts_model.py` (new).**
   - `FACTS_CONTEXT_SCHEMA` follows the same `Variable`/trust-tag shape as `CONTEXT_SCHEMA`, with
     exactly the paths and trust tags in the story table.
   - `FactsModel.build(result: FactExtractionResult) -> dict` returns the JSON-shaped context:
     - `facts` in the listed order;
     - `documents` sorted by path, each with its facts in rank order;
     - weights as an object `{numeric, entity, distinctiveness}`;
     - floats as JSON numbers, not formatted strings.
   - The module imports only `docsentinel.models` and telemetry siblings. It reads no file,
     environment or clock.
   - **Amended 2026-11-24 (threat model, E4, E5, E3).**
     - `FactsModel.build` raises `ValueError` for any fact whose disposition is not in
       `DISPOSITIONS`, because the disposition is tagged trusted. `run.notice` is taken only from
       the engine constants (Task 01 step 4.6), never composed from input.
     - Every untrusted list element (`numbers[]`, `entities[]`, `facts[]` string fields) is tagged
       untrusted (0007 M1/M2).
     - Each fact gains the trusted bool `hidden_characters`: true when `text` holds any code point
       of category Cf, Co or Cn, or of the 0007 R4 list (U+00AD, U+180E, U+2060-U+2064, the Hangul
       fillers, variation selectors, U+E0000-U+E007F), that `neutralize` keeps.
     - For `facts`-context JSON output, the template engine serialises the `[` of every `##[` as
       `[` after `ensure_ascii` encoding. This is lossless (`json.loads` gives the same string),
       so C11 equality holds at the value level. `report`-context JSON is unchanged; extending the
       escape to it is an owner question.
3. **Packaged templates** in `telemetry/templates/`, shipped as package data like the existing five:
   - `facts-text.json`: `"type": "text"`, `"context": "facts"`, `output.sink` `terminal`.
     - Each document path appears once, through `neutralize`.
     - Beneath it, one line per fact, built with `"append": true` line nodes:
       `  #<rank> score <score> (numeric <n>, entity <e>, distinct <d>) cluster <id>/<size> paragraph <p>[ <disposition>]: <text|neutralize>`.
     - Then `Facts: <selected> selected, <listed> listed, from <claims> claims in <documents> document(s) (<unreadable> unreadable skipped)`.
     - Then `Matches the DS302 selection for this configuration: yes|no`.
     - Then the notice.
     - The disposition is shown only when `include_rejected` is true. Use the template language's
       existing conditional construct, or print it always if there is none; record which one in
       the PR.
   - `facts-json.json`: `"type": "json"`, `"context": "facts"`, `schema_version` `1`. Its body has
     the shape in the story README.
   - Each packaged template carries a `description` that says it is for `extract-facts`.
   - **Amended 2026-11-24 (threat model, E5).** On a fact line whose `hidden_characters` is true,
     `facts-text` prints a fixed literal marker (proposed: `[hidden characters] `) immediately
     before the neutralised text. The marker is a template literal, not data.
4. **`packaged_template_names(context="report")`.** Add a keyword so that `scan`'s `--format` help and
   validation list only `report` templates and `extract-facts` lists only `facts` templates. The
   function's default behaviour stays the same for existing callers.
   **Amended 2026-11-24 (threat model, E2).** The packaged partition comes from the trusted
   packaged set only: either a static name-to-context table pinned by a test against the loaded
   packaged templates, or the packaged templates validated once and cached. The
   `report_templates_dir` listing (`available_templates`) stays **name-only** and opens no file;
   it is not split by context. A context mismatch on a directory template is detected only when
   that selected template is loaded, with the step 5 errors. A malformed directory file therefore
   breaks only its own selection.
5. **`reporting.render_facts(result, format="facts-text", *, template=None, root=None,
   templates_dir=None) -> str`.**
   - It is a thin shim like `render()`. It resolves the template the same way: a `template`
     object or an invoker path, else `format` as a name.
   - It raises `TemplateError` (surfaced as a chained `ValueError`, as `render()` does) when
     `template.context != "facts"`, with the message
     `template <name> is a report template; use it with docsentinel scan`.
   - `render()` raises the mirror error for a `facts` template:
     `template <name> renders fact extraction output; use docsentinel extract-facts`.
   - The function holds no format literal. Extend the AST tripwire to cover
     `telemetry/facts_model.py`.
   - **Amended 2026-11-24 (threat model, E4): engine-level check.** `telemetry.engine.render_template`
     gains an additive keyword naming the model kind (proposed `context: str = "report"`), which
     both shims pass. It raises `TemplateError` when `template.context` and that kind disagree, so
     a library caller of `render_template` cannot bypass the shim checks. Existing callers are
     unchanged because the default is `report`.
6. **Security Auditor review.** Before merge, the Security Auditor reads the loader diff and
   `FACTS_CONTEXT_SCHEMA`. The verdict and any follow-up go into a short dated delta note appended to
   `/docs/security/threat-model-0007-template-engine-2026-10-31.md` (a "Delta 2026-11-xx: template
   context kind" section), or into a new
   `/docs/security/threat-model-0010-extract-facts-<date>.md` if the auditor prefers. A CRITICAL
   finding stops the task. Review points:
   - Can a `facts` template reach a report variable, or the reverse?
   - Is every untrusted facts path tagged untrusted, including list elements (M1/M2)?
   - Does the default `report` context keep every existing template byte-identical?
7. Report a `Docs impact:` line (triggers O, A) and a `Diagram impact:` line naming
   `component-reporting.puml` (facts context model, facts templates, loader context kind).

## Deliverables

- `/src/docsentinel/telemetry/loader.py`, `/src/docsentinel/telemetry/facts_model.py` (new)
- `/src/docsentinel/telemetry/templates/facts-text.json`, `facts-json.json` (new, package data)
- `/src/docsentinel/reporting.py`
- The security delta note from step 6

## Acceptance criteria

- [ ] Each of the five existing packaged templates, and every template in the test assets, loads
      with `context == "report"` and renders byte-identically to master.
- [ ] A `facts` template that names `findings`, or a `report` template that names `facts`, fails
      to load with the unknown-variable error.
- [ ] A `facts` text template that places `text` or `path` without a terminal sink filter fails to
      load (the existing M4 rule).
- [ ] `facts-json` output parses as JSON, is ASCII-only, and has exactly the documented top-level
      keys. A claim holding bidi controls or `##[` reaches `facts-text` neutralised.
- [ ] `render()` with a facts template and `render_facts()` with a report template both raise the
      documented errors.
- [ ] The AST tripwire covers `reporting.py`, `telemetry/engine.py` and `telemetry/facts_model.py`
      and is green.
- [ ] The Security Auditor verdict is PASS or PASS_WITH_FOLLOWUP, and it is recorded (done:
      [threat-model-0010-extract-facts-2026-11-24](/docs/security/threat-model-0010-extract-facts-2026-11-24.md)).
- [ ] **Amended 2026-11-24 (threat model, E3).** A claim `##[error]x` gives no `##[` anywhere in
      `facts-json` output, and `json.loads` of the output round-trips to the same string.
- [ ] **Amended 2026-11-24 (threat model, E4).** A cross-context variable is refused at the text
      root, the json root and alias scope; an `ext.*` filter in a `facts` template is refused;
      `render_template` with a mismatched model kind raises `TemplateError`; `FactsModel.build`
      with a disposition outside `DISPOSITIONS` raises `ValueError`; a `facts` text template placing
      a facts value without `neutralize` is refused; a github-sink `facts` template obeys T2-R1.
- [ ] **Amended 2026-11-24 (threat model, E5).** Claims holding U+E0041 or U+2060 have
      `hidden_characters == true` and carry the marker in `facts-text`; a plain claim has neither.
- [ ] **Amended 2026-11-24 (threat model, E2).** Listing templates opens no `report_templates_dir`
      file (open/parse spy), and a malformed directory file fails only when it is selected.

## Test expectations

Written in [Task 04](./04-fixtures-and-tests.md) (`tests/unit/test_facts_template_context.py` plus
the template cases of the CLI integration test).

## Out of scope

- The CLI (Task 03).
- Report extensions for facts.
- Schema-2 or any change to the `report` context.
