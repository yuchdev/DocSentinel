# Task 03 - `doctor` Deep-Readiness Reporting & Model-Setup Docs

**Story:** [01.0 - Deep Profile Opt-In Gating & Dependency Plumbing](README.md)
**Depends on:** [01 - Deep opt-in confirmation gate](01-deep-opt-in-confirmation-gate.md),
[02 - Optional dependency group & lazy-import boundary](02-optional-dependency-group-and-lazy-import.md)
(reads `deep_support`'s probe and `Config.deep_confirm`)

## Purpose

A user who selects `deep` and gets a "nothing ran" `pending` message needs one place that tells them
*why* and *exactly what to do*. The `doctor` subcommand already exists to "show capabilities"; this
task makes it report the three independent conditions a deep run needs - confirmation, libraries,
and the model - so the fix is never a guessing game. It also lands the short, one-time model-setup
documentation (README + architecture note), mirroring how other deterministic-first tools document
a single out-of-band setup step without building a bespoke installer.

## Decision this task implements

1. **`doctor` gains a deep-readiness section**, printed for every invocation (not only when `deep`
   is selected - `doctor` is the "what can this install do?" command). It reports, each as its own
   line with a clear ✓ / ✗ and a remedy when ✗:
   - deep libraries installed (`deep_support.libraries_available()`),
   - spaCy model `en_core_web_sm` present (`deep_support.model_available()`),
   - overall `deep_ready()` verdict.
   `doctor` does **not** read `deep_confirm` from config (confirmation is a per-run gesture, not an
   install capability) - it reports *installability*, and names the confirmation step in prose so
   the user knows readiness alone is not enough to run deep.
2. **`doctor` never loads the model** - it uses the non-loading probes from Task 02 only, so running
   `doctor` stays fast even when the model is installed.
3. **`doctor` exit code is unchanged** (`0`) - reporting that deep is not installed is informational,
   not a failure. A machine that will only ever run `fast` is a perfectly healthy machine.
4. **One-time model setup is documented, not automated.** A short README section and an architecture
   note state the two commands (`pip install docsentinel[deep]` + `python -m spacy download
   en_core_web_sm`) and that they are run once per environment. No download-on-first-run,
   no auto-installer - explicit and inspectable, consistent with the project's deterministic-first,
   no-surprise-network posture.

## Files

| Path | Action |
|------|--------|
| `src/docsentinel/cli.py` | Modify - `doctor` output gains the deep-readiness section |
| `README.md` | Modify - add a "Deep profile (optional)" setup section |
| `docs/architecture/README.md` | Modify - one-line pointer to the optional deep setup (not the full reliability story - that is Story 04.0 Task 02) |
| `tests/test_scan.py` | Modify - `doctor` output tests |

## Symbols / fields

| Symbol | Change |
|--------|--------|
| `doctor` handler in `cli.main` | Append lines built from `deep_support.libraries_available()`, `deep_support.model_available()`, `deep_support.deep_ready()`; include `deep_support.DEEP_EXTRA_HINT` on any ✗ line. Factor the formatting into a pure helper `_deep_doctor_lines() -> list[str]` so it is unit-testable without argparse. |
| `_deep_doctor_lines() -> list[str]` | New pure function in `cli.py`: returns the deep-readiness report lines given the current probe results. No I/O beyond the probe calls; no printing (returns the lines for the caller to print). |

## Tests

`tests/test_scan.py` additions (stub the probes with `monkeypatch` so the test matrix does not need
spaCy installed):
- `test_doctor_reports_deep_not_installed` - probes stubbed to `False` → `doctor` output contains a
  ✗ for libraries and the install hint; exit code `0`.
- `test_doctor_reports_deep_ready` - probes stubbed to `True` → output shows deep ready, no install
  hint line; exit code `0`.
- `test_doctor_reports_libs_present_model_missing` - `libraries_available()` True,
  `model_available()` False → the libraries line is ✓, the model line is ✗ with the
  `spacy download` remedy, overall verdict not-ready.
- `test_doctor_does_not_load_model` - assert `deep_support.load_pipeline` is **not** called during
  `doctor` (e.g. monkeypatch it to raise and confirm `doctor` still exits `0`).
- `test_deep_doctor_lines_pure` - `_deep_doctor_lines()` returns a `list[str]` and prints nothing
  (capture stdout, assert empty) with probes stubbed.

## Success criteria

- [ ] `docsentinel doctor` on a machine without the `deep` extra prints an actionable ✗ line with
      the exact `pip install docsentinel[deep]` + `python -m spacy download en_core_web_sm` remedy,
      and still exits `0`.
- [ ] `doctor` never loads the spaCy model (fast even when installed) - guarded by a test.
- [ ] `_deep_doctor_lines` is a pure function over the probe results, unit-testable without
      invoking the CLI or argparse.
- [ ] The README "Deep profile (optional)" section states the setup is one-time and out-of-band, and
      links to this milestone's plan for the full gating/advisory story - it does not overclaim what
      `deep` detects (that is Story 04.0 Task 02's scoped sentence).

## Constraints

- Full type annotations; no bare `except:`.
- Reuse `deep_support.DEEP_EXTRA_HINT` and `deep_support.MODEL_NAME` verbatim - `doctor` must not
  hardcode a second copy of the install command or the model name.
- Keep the README addition short (a few lines) - this is a setup note, not a tutorial; the
  authoritative behavior lives in the roadmap/architecture docs.
