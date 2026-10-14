# Task 03 - JSON Report Schema Versioning

**Story:** [03.0 - CLI & Reporting Completion](README.md)
**Depends on:** none within this story (independent of Tasks 01-02); should land before any
external tooling starts depending on today's unversioned JSON shape.

## Purpose

`reporting.render(result, "json")` today is `json.dumps(asdict(result), indent=2)` - whatever
fields `ScanResult` happens to have, with no marker of shape. Milestone 0001 Story 02.0 already
changed `enabled_rules`' meaning once (full registry → actually-evaluated codes); later
milestones will add more fields. A `schema_version` lets a consumer (CI script, future editor
plugin) detect a shape change instead of guessing from field presence.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/models.py` | Modify - `ScanResult` |
| `src/docsentinel/reporting.py` | Modify - text format gains one line |
| `docs/architecture/README.md` | Modify - document the field and the versioning policy |
| `tests/test_scan.py` / `tests/test_reporting.py` | Modify/add |

## Symbols / fields

`src/docsentinel/models.py`:

| Symbol | Change |
|--------|--------|
| `ScanResult` | Add `schema_version: int = 1` as the **first** field (before `profile`) - field order affects `dataclasses.astuple`/positional construction call sites; grep the codebase for any positional `ScanResult(...)` construction (there is exactly one, in `engine.scan`) and update it to keyword arguments if not already done by Milestone 0001 Story 01.0 Task 03 (which already changed this constructor call - verify, don't assume, since that task may have landed with positional args that this one would silently break). |
| `Finding` | Add `line: Optional[int] = None`, representing a one-based source line when known. Existing callers remain valid; dataclass JSON serialization emits an integer or `null`. |

**Versioning policy** (document this verbatim in `docs/architecture/README.md`, not just in this
task spec): `schema_version` increments by exactly 1 whenever a field is removed, renamed, or has
its *meaning* changed (not just added) in `ScanResult`'s JSON representation. Adding a new
optional field with a sensible default does **not** require a bump - only breaking changes do.
This mirrors semantic-versioning-for-data, not semantic-versioning-for-code.

## Tests

- `test_json_output_includes_schema_version` - `json.loads(render(result, "json"))["schema_version"] == 1`.
- `test_text_output_includes_schema_version_line` - the text format's first line (or an early,
  clearly-labeled line) states the schema version, e.g. `"Schema version: 1"`.
- `test_schema_version_defaults_to_one_for_direct_construction` - `ScanResult(profile="fast",
  documents=(), findings=(), enabled_rules=(), pending=())` (keyword-only, no `schema_version`
  given) defaults to `1`.
- `test_json_output_includes_finding_line` - a finding with a known line serializes that integer;
  an unknown line serializes as `null`.

## Success criteria

- [ ] Every existing JSON-consuming test still passes after adding the field (they should, since
      `json.loads(...)["some_other_key"]`-style assertions are unaffected by one new key, but
      verify no test does an exact dict-equality comparison against the full payload that this
      new field would break - update any that do).
- [ ] The versioning policy is written down in `docs/architecture/README.md`, not only in this
      spec file (specs are read once at implementation time; the policy needs to outlive this
      task for whoever adds the next `ScanResult` field).

## Constraints

- Full type annotations.
- Do not add a `schema_version` *parameter* to `render()` - the version lives on `ScanResult`
  itself (set once, by whoever constructs the result), not chosen per-render-call.
