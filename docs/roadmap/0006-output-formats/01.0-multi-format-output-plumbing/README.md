# Story 01.0 - Multi-Format Output Plumbing

`docsentinel scan` renders one format to stdout. This story lets one scan write several report
files and gives the formats a small registry, so Story 02.0 can add renderers without touching the
CLI again. It changes no detection and no exit code.

## Tasks

| # | Task | Output |
|---|------|--------|
| 01 | [Renderer registry](01-renderer-registry.md) | `reporting.py` exposes a `FORMATS` registry mapping a format name to a renderer; `text`, `json` and `github` register through it with byte-identical output |
| 02 | [`--output` and repeatable `--format`](02-output-flag-and-repeatable-format.md) | `scan --format json --format text --output-dir DIR` (and `--output PATH` for a single format) writes each report from one scan |

01 is a pure refactor and must land first; 02 builds on the registry.
