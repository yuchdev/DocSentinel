# Task 01 - Renderer Registry

**Story:** [01.0 - Multi-Format Output Plumbing](README.md)
**Depends on:** Milestone 0001 Story 03.0 (the existing `text`, `json` and `github` renderers)

## Purpose

`cli.py` currently picks a renderer with an `if/elif` over the three format names. A registry makes
the set of formats data, not control flow, so adding one is a registration and `--format`'s
`choices` come from the registry.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/reporting.py` | Modify - add the registry; register the three existing renderers |
| `src/docsentinel/cli.py` | Modify - `--format` choices and dispatch read the registry |
| `tests/test_reporting.py` | Modify/add registry tests |

## Symbols / fields

| Symbol | Change |
|--------|--------|
| `Renderer = Callable[[ScanResult], str]` | New type alias. |
| `FORMATS: dict[str, Renderer]` | New. Insertion-ordered; initial keys `text`, `json`, `github`. |
| `register_format(name: str, renderer: Renderer) -> None` | New. Raises `ValueError` on a duplicate name or a name that is not lowercase ASCII `[a-z0-9-]+`. |
| `render(result: ScanResult, format: str = "text") -> str` | Exists today with the `if/elif` dispatch; becomes a registry lookup. An unknown name raises `ValueError` listing the known formats (keep today's behavior if it already raises, and extend the message). |

## Acceptance criteria

1. For every existing fixture, the bytes produced for `text`, `json` and `github` are identical to
   the pre-refactor output (golden comparison).
2. `docsentinel scan --help` lists the formats from `FORMATS`, in registration order.
3. Registering a duplicate or invalid name fails loudly; no silent override.

## Tests

- `test_registry_contains_builtin_formats` - keys are `text`, `json`, `github`, in that order.
- `test_register_format_rejects_duplicate_and_invalid_name`.
- `test_render_unknown_format_lists_known_formats`.
- `test_builtin_renderers_output_unchanged` - golden comparison against stored fixtures.
