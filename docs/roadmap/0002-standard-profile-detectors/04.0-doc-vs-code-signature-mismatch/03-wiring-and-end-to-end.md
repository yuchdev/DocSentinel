# Task 03 - Package Wiring & End-to-End Test (`DS204`)

**Story:** [04.0 - Doc-vs-Code Signature Mismatch Detector](README.md)
**Depends on:** [01 - Code discovery](01-code-discovery.md),
[02 - Signature-mismatch detector](02-signature-mismatch-detector.md)

## Purpose

Register `DS204` into the lazily-loaded `standard` subpackage and prove the full chain: a `standard`
scan discovers Python source, runs `docsig`, and returns `error`-severity findings that fail the
build by default - unlike the three `warning`-severity statistical detectors. This is also the proof
that a code-reading detector coexists cleanly with the Markdown-corpus detectors under one engine.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/detectors/standard/__init__.py` | Modify - add the `signatures` import |
| `tests/test_standard_profile_end_to_end.py` | Modify - add DS204 cases |
| `docs/architecture/README.md` | Modify - record DS204 and the code-reading note |
| `docs/security/README.md` | Modify - threat-model note (DS204 reads source code) |

## Symbols / fields

`src/docsentinel/detectors/standard/__init__.py` - final state after this milestone:

```python
from docsentinel.detectors.standard import complexity        # DS201 (Story 02.0)
from docsentinel.detectors.standard import duplication        # DS202 (Story 03.0)
from docsentinel.detectors.standard import low_information     # DS203 (Story 03.0)
from docsentinel.detectors.standard import signatures          # DS204 (Story 04.0)

__all__ = ["complexity", "duplication", "low_information", "signatures"]
```

## Behavior change

- A default `standard` scan (extra installed) now evaluates `DS201`, `DS202`, `DS203`, `DS204`;
  `enabled_rules == ("DS201", "DS202", "DS203", "DS204")`, `notice` reads "4 standard rule(s)
  evaluated".
- Because `DS204` is `error` severity, a `standard` scan of a repo with a real docstring/signature
  mismatch now exits `1` **by default** (not only under `--strict`), unlike the three `warning`
  detectors - the first `standard` rule that fails a default build.

## Tests (`tests/test_standard_profile_end_to_end.py`)

Guard with `importorskip("docsig")` (and `sklearn`/`textstat` as the shared module requires).

- `test_standard_scan_reports_signature_finding` - a `tmp_path` project with `src/pkg/bad.py`
  (docstring documents a nonexistent param) and some Markdown → exactly one `DS204` finding among any
  others, attributed to the `.py` path with its SIG sub-code in the message.
- `test_standard_scan_exit_code_one_for_ds204_error` - `main(["scan", str(tmp_path), "--profile",
  "standard"])` on that project returns `1` by default (DS204 is `error`), even though DS201-DS203 are
  only warnings - distinguishes the error detector from the warning ones.
- `test_ds204_coexists_with_corpus_detectors` - a project with both a bad `.py` *and* a duplicated
  Markdown paragraph yields one `DS204` **and** one `DS202` finding in a single scan, proving the
  code-reading and corpus-reading detectors run together under one engine without interfering.
- `test_select_ds204_only_skips_corpus_build` - `Config(profile="standard", select=("DS204",))` runs
  only `DS204`; assert no `DS202`/`DS203` findings and (bonus) that the corpus model is not built when
  no corpus detector is active (spy on `TfidfVectorizer.fit_transform`, expect zero calls) - a small
  efficiency guarantee that selecting the code detector alone does not pay the TF-IDF cost.
- `test_clean_project_standard_scan_is_zero_findings_evaluated` - a project with well-documented code
  and no duplicate/filler/complex prose: zero findings, `notice` says "4 ... evaluated",
  `enabled_rules` is all four codes.

## Docs updates

`docs/architecture/README.md`: add `DS204` (docstring/signature mismatch, `docsig`, `error`) to the
`standard`-profile rule list, with a one-line note that it is the sole `standard` detector that reads
**Python source** (via `code_discovery.discover_python` / `Config.docsig_paths`), not the Markdown
corpus. The `standard` profile is now fully specified for this milestone (DS201-DS204).

`docs/security/README.md`: append a dated note (do not rewrite prior blocks) - `DS204` reads
**source code** file contents in addition to the Markdown contents that DS201-DS203 (and Milestone
0001's detectors) already read. The scanned-surface for a crafted-input DoS now includes Python files
under `docsig_paths`, and `docsig` runs third-party parsing over them in-process; flag for
`security-auditor` to assess (a) the added read surface and (b) that `docsig`, like any analyzer,
executes no scanned code but does parse it. This task **files** the item; it does not resolve it.

## Success criteria

- [ ] A single `scan(..., profile="standard")` (extra installed) evaluates all four `DS2xx` codes;
      `DS204` fails the default build (exit `1`) on a real mismatch while the three warning detectors
      alone do not.
- [ ] The code-reading detector and the corpus-reading detectors run together in one scan without
      interference, proven by a mixed-finding test.
- [ ] Selecting `DS204` alone does not build the TF-IDF corpus model (no wasted work).
- [ ] `security-auditor` has the new source-code read surface filed before Story 04.0 is marked
      complete in `status.md`.

## Constraints

- Full type annotations; no bare `except:`.
- One import line per detector in `detectors/standard/__init__.py` - no plugin discovery (consistent
  with Story 01.0 and Milestone 0001).
- Keep the `importorskip` guards so the default (no-extra) lane stays green; the extra lane (Story
  05.0) is where these execute.
</content>
