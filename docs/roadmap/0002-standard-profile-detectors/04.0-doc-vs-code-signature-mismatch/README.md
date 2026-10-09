# Story 04.0 - Doc-vs-Code Signature Mismatch Detector (`DS204`)

The one `standard`-tier detector that reads **code, not Markdown**. It checks that a Python
function's docstring documents the same parameters and returns the function's signature actually has
- a documented `param` that does not exist, a real parameter left undocumented, a `:returns:` on a
function that returns nothing. This is deterministic and purely mechanical (no model, no heuristic
judgment about meaning), which is exactly why it belongs in `standard` and not in the
semantic/heuristic `deep` tier (Milestone 0003): there is a single correct answer for "does this
docstring's parameter list match this signature," and `docsig` computes it.

## Library choice: `docsig`, not `darglint`

`darglint` is unmaintained (no release since 2021). The live alternatives are `docsig` and
`pydoclint`. This story uses **`docsig>=0.96`** (actively maintained; 0.96.0 released August 2026):
its stable `SIGxxx` codes and documented, parseable output compose into one `Finding` per violation,
and its programmatic entry point (`docsig(...)`) runs in-process with no subprocess. See
[Task 02](02-signature-mismatch-detector.md) for the honest reality of its API surface (it returns an
int and prints; there is no public structured report object), and how the detector adapts to that.

## The honest discovery problem

Today's `discovery.py` inventories **Markdown** files into `Document(path, bytes)` objects. `DS204`
needs **Python** files. Rather than forcing Python source through the Markdown-shaped `Document`
model and the Markdown `include`/`exclude` config, this story adds a **small, separate code-scanning
discovery path** scoped to a configurable set of source roots (default `src`). The `Analyzer`
signature is unchanged - `DS204`'s `detect` still receives the Markdown `documents` tuple - but it
**ignores** that argument and discovers Python files itself under `root`, which is the one honest
deviation this milestone makes from the "detectors consume `documents`" pattern. Task 01 builds that
discovery path; Task 02 is the detector; Task 03 wires and proves it.

## Tasks

| # | Task | Rule | Output |
|---|------|------|--------|
| 01 | [Python source discovery path](01-code-discovery.md) | - | `src/docsentinel/code_discovery.py`: `discover_python`, `Config.docsig_paths` |
| 02 | [Signature-mismatch detector](02-signature-mismatch-detector.md) | `DS204` | `src/docsentinel/detectors/standard/signatures.py` (docsig integration) |
| 03 | [Package wiring & end-to-end test](03-wiring-and-end-to-end.md) | - | `detectors/standard/__init__.py` import line, end-to-end tests |

01 must precede 02 (the detector consumes the discovery path). 03 wires and proves.
</content>
