# Task 02 - SARIF 2.1.0 Renderer

**Story:** [02.0 - New Report Renderers](README.md)
**Depends on:** [Story 01.0 Task 01](/docs/roadmap/0006-output-formats/01.0-multi-format-output-plumbing/01-renderer-registry.md)

## Purpose

SARIF is the interchange format code-scanning tools ingest. Emitting it lets DocSentinel findings
appear next to other analyzers' without a custom adapter.

## Mapping

| SARIF | From |
|-------|------|
| `version` / `$schema` | `2.1.0` and the official 2.1.0 schema URI |
| `runs[0].tool.driver` | `name: docsentinel`, `version` from package metadata, `rules` from the registry |
| `rules[].id` / `shortDescription` | `Rule.code` / `Rule.title`; `defaultConfiguration.level` from `Rule.severity` |
| `results[].ruleId` | finding rule |
| `results[].level` | `error` -> `error`, `warning` -> `warning` |
| `results[].message.text` | neutralized finding message |
| `results[].locations[0].physicalLocation` | `artifactLocation.uri` = relative POSIX path (no absolute paths); `region.startLine` only when the finding has a line |
| `runs[0].properties` | `profile`, `documents`, `notice`, `pending`, and `advisory: true` for deep runs |

## Decisions

- Relative URIs with `uriBaseId: "%SRCROOT%"`; the report never embeds the scanning machine's
  absolute paths.
- Every rule enabled for the run is listed in `tool.driver.rules` even with zero results, so a
  consumer can tell "evaluated, none found" from "not evaluated".
- Deep findings are emitted at `warning` and marked advisory in `properties`; SARIF has no
  advisory level and this task does not invent one.
- Standard library `json` only; output is key-sorted and indented for stable diffs.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/reporting.py` | Modify - `render_sarif`; register `sarif` (extension `sarif`) |
| `tests/test_reporting.py` | Modify/add |
| `tests/assets/sarif/` | New - minimal fixture and expected log |

## Tests

- `test_sarif_is_valid_2_1_0_shape` - required properties present, `version == "2.1.0"`.
- `test_sarif_rules_list_includes_rules_with_no_results`.
- `test_sarif_levels_map_from_severity`.
- `test_sarif_uris_are_relative_and_have_no_absolute_paths`.
- `test_sarif_region_present_only_when_line_known`.
- `test_sarif_deep_run_marked_advisory`.
- `test_sarif_output_is_deterministic`.
