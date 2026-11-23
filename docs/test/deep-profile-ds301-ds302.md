# Manual test checklist: deep-profile contradiction and fact-check rules (DS301, DS302)

This checklist exercises the two deep-profile rules by hand: `DS301` (fact-contradiction
candidate), which is fully implemented, and `DS302` (external fact-check disagreement), which is
mid-implementation under Milestone 0010 (see the status callout in [Use case 2](#use-case-2--ds302-external-fact-check-disagreement)
before running those steps). Both rules are advisory-only: they never fail a scan, regardless of
`--strict` (deep findings always exit `0`).

Every command below runs with `DOCSENTINEL_SETTINGS=off` so a real `~/.local/share/docsentinel/settings.json`
on the machine running the checklist cannot change rule selection or the active profile out from
under you. Never run these steps with your real settings file, and never set
`DOCSENTINEL_USE_EXTERNAL_API=1` or a `DOCSENTINEL_FACTCHECK_*` variable outside the scoped shell
session described below.

## Setup

```sh
uv sync --extra test --extra deep
uv run python -m spacy download en_core_web_sm
```

The deep profile needs `docsentinel[deep]` (spaCy + textacy) and the pinned `en_core_web_sm`
model; `uv run docsentinel doctor` reports `deep profile: not ready` with install guidance until
both are present.

## Use case 1 — DS301: fact-contradiction candidate (coverage discrepancy)

### Fixtures

[`examples/docs/ds301-demo-coverage-report-v1.md`](/examples/docs/ds301-demo-coverage-report-v1.md) and
[`examples/docs/ds301-demo-coverage-report-v2.md`](/examples/docs/ds301-demo-coverage-report-v2.md) each
make one checkable claim about the same subject with a different number:

```md
# Coverage report — Q1 2026

DocSentinel scored 85 on the test coverage benchmark this quarter.
```

```md
# Coverage report — Q2 2026

DocSentinel scored 90 on the test coverage benchmark this quarter.
```

`DS301` works by extracting a subject-verb-object (SVO) triple per paragraph (`mining/claims.py`,
via textacy over the pinned spaCy model) and normalizing the subject and predicate to a
`(subject_key, predicate_key)` grouping key — here `("docsentinel", "scored")` for both documents.
Two claims in the same group "disagree" when their extracted object numbers are both non-empty
and disjoint (`{85}` vs. `{90}`); the same rule applies to named entities when numbers are absent.
This is why the wording matters: a copula sentence like "DocSentinel's test coverage is 85
percent" does **not** reliably produce a usable claim here — textacy's SVO extractor only
populates `object_numbers` when the number is the head of the object span, not when it modifies a
following noun phrase (`"85 percent test coverage"` parses with the object span starting after the
`85`). The two fixtures above were verified against the live extractor before being committed.

### Checklist

| # | Step | Expected |
|---|------|----------|
| 1 | `DOCSENTINEL_SETTINGS=off uv run docsentinel scan examples/docs --include ds301-demo-coverage-report-v1.md --include ds301-demo-coverage-report-v2.md --profile deep --i-understand-deep-is-heuristic` | Exit `0`; one `DS301 fact-contradiction candidate` finding on `ds301-demo-coverage-report-v2.md`: `candidate contradiction: subject 'DocSentinel' claimed as '85' in ds301-demo-coverage-report-v1.md but '90' in ds301-demo-coverage-report-v2.md - review to confirm` |
| 2 | Same command, but scan only `--include ds301-demo-coverage-report-v1.md` | Exit `0`; `0 findings`: a lone claim has nothing to disagree with |
| 3 | Run step 1 without `--i-understand-deep-is-heuristic` and without `DOCSENTINEL_DEEP_CONFIRM=1` | Exit `0` (not `2` — the gate is a graceful skip, not a failure): `WARNING: deep profile skipped: not confirmed (...)`, `Enabled rules: []`, `0 findings`, and a `Pending:` line naming the three ways to confirm |
| 4 | Run step 1 with `-v` | stderr DEBUG line `DS301: 2 claims compared, 1 candidates` (from `contradictions.py`) |
| 5 | Record a baseline: `DOCSENTINEL_SETTINGS=off DOCSENTINEL_DEEP_CONFIRM=1 uv run docsentinel baseline <scratch copy of the two files> --profile deep --output baseline.json`, then re-scan with `--baseline baseline.json` | The baseline file holds one `DS301:...` fingerprint; the re-scan reports `0 findings` and logs `1 fingerprints, 1 findings suppressed` — the standard "reviewed, now a non-issue" workflow |
| 6 | Add `ignore = ["DS301"]` to a `[tool.doc_sentinel]` config at the scan root, re-run step 1 | `Enabled rules` drops `DS301`; `profile=deep: 1 rules selected, 0 evaluated`; `0 findings` |
| 7 | `uv run docsentinel scan --format json examples/docs --include ds301-demo-coverage-report-v1.md --include ds301-demo-coverage-report-v2.md --profile deep --i-understand-deep-is-heuristic` | Schema-2 JSON (`"schema_version": 2`); the finding appears under `documents[1]` (`path: "ds301-demo-coverage-report-v2.md"`) with `"severity": "warning"`, `"fault_class": "contradiction_candidate"`, `"tier": "heuristic"`, `"outcome": "advisory"`; `documents[0]` (`v1.md`) has an empty `problems` array |

### Adjusting DS301's weights and parameters

`DS301` is the odd one out in `docsentinel.toml`: unlike `DS201`–`DS204`, it exposes **no**
`Config` field at all — `detect(root, documents)` does not even take a `config` argument (confirm
with `grep -n "contradiction\|DS301" src/docsentinel/config.py`, which matches nothing). There is
no numeric "contradiction threshold" to raise or lower from the command line or
`docsentinel.toml`. The real levers are:

- **Rule selection**, not rule tuning: `select = ["DS3"]` to run only deep rules, or
  `ignore = ["DS301"]` to turn it off entirely (checklist step 6). This changes *whether* it runs,
  not *how sensitively* it matches.
- **The consent gate**: `deep_confirm = true` / `--i-understand-deep-is-heuristic` /
  `DOCSENTINEL_DEEP_CONFIRM=1`. This gates the whole deep profile, not DS301 specifically.
- **Scope**: `--include`/`--exclude` (or the config equivalents) change which documents' claims
  are compared, which indirectly changes the candidate pairs DS301 can find — the only
  "sensitivity" knob that exists today without touching code.
- **The matching logic itself, in code, not config** (`detectors/contradictions.py::_disagree`):
  it is a binary, deterministic test — disjoint non-empty number sets, or disjoint non-empty
  entity sets — with no weight or score to tune. Loosening or tightening it (for example, treating
  `85%` and `85.0` as equal, or adding a numeric tolerance band for rounding) is a code change to
  `_disagree`, reviewed like any other detector change, not a configuration edit.
  `_CLOSED_ENTITY_TYPES` in `mining/claims.py` is the closest thing to a tunable "parameter" — it
  restricts which spaCy entity labels count as comparable objects (`ORG`, `PRODUCT`, `GPE`,
  `PERSON`, `CARDINAL`, `QUANTITY`, `PERCENT`, `DATE`) — again a code constant, not a config key.
- **The pinned model** (`mining/nlp.py::MODEL_NAME = "en_core_web_sm"`): upgrading it changes what
  gets extracted as a claim at all (the module docstring warns extraction is deterministic only
  for the pinned version), which is the single biggest behavioral lever over DS301's recall — and
  it is a dependency change, not a runtime setting.

If a future story adds genuine numeric weights (for example, a cosine-similarity threshold between
claim objects instead of exact set disjointness), it should follow the pattern DS201–DS204 use:
a validated, documented `Config` field, a row in the architecture section of `CLAUDE.md`, and a
drift test in `tests/integration/test_rules_table.py`.

## Use case 2 — DS302: external fact-check disagreement

> **Current implementation status (2026-11-23, Milestone 0010, Story 01.0 5/6 tasks):** the dual
> consent gate and dispatch plumbing are real and testable today. Candidate *selection*
> (`select_candidates`, Story 02.0) is still a stub that always returns no candidates, and the
> `lenz` backend itself (Story 03.0) is not shipped — `load_backend("lenz")` raises `ImportError`.
> So **today**, `DS302` can never produce a finding through the plain CLI, no matter how the
> `fact_check_*` options are set: it always stops at one of the two gates below. See
> [`docs/roadmap/0010-fact-check/status.md`](/docs/roadmap/0010-fact-check/status.md) for the
> live state before re-running this checklist later.

> **Do not use `examples/docs/lenz_fact-checking.md` for this or any other test.** That file sits
> in the same directory as the article used below, but it is not a normal fixture: it is written
> as direct instructions to an AI agent ("Run the snippet above as-is, and show me the verdict...",
> "Do not add it yet; describe it first") and it embeds a bare API key for `https://lenz.io`. The
> project's own roadmap notes (`status.md`, 2026-11-20) already record that this content was read
> read-only and never acted on, and milestone 0010's exit gates refuse to ship any test, fixture or
> log containing that key or a real call to `lenz.io`. Treat it as untrusted content, not as setup
> instructions, the same way the project already does.

### Fixture

[`examples/docs/New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md`](/examples/docs/New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md),
a real press-style article, is the corpus `DS302` would eventually fact-check.

### Checklist — the gate, as it behaves today

| # | Step | Expected |
|---|------|----------|
| 1 | `DOCSENTINEL_SETTINGS=off uv run docsentinel scan examples/docs --include New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md --profile deep --i-understand-deep-is-heuristic` (no `--use-external-api`, no key) | Exit `0`; stderr `WARNING: DS302 skipped: pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set DOCSENTINEL_FACTCHECK_LENZ_API_KEY`; the text report's `Pending:` line repeats it; zero `DS302` findings |
| 2 | Same, with `--use-external-api` but no key set | A shorter message, not the identical one: `WARNING: DS302 skipped: set DOCSENTINEL_FACTCHECK_LENZ_API_KEY` — the "pass --use-external-api" clause drops out because that half of the gate is now satisfied; only the still-missing key is named |
| 3 | Same, with `DOCSENTINEL_FACTCHECK_LENZ_API_KEY=test-only-not-real DOCSENTINEL_USE_EXTERNAL_API=1` (both halves of the gate now open) | `WARNING: DS302 skipped: backend lenz not available` — the gate opened, but Story 03.0 has not shipped the backend yet |
| 4 | `DOCSENTINEL_SETTINGS=off uv run docsentinel doctor` with nothing set | A line `fact-check gate: off (pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1); set DOCSENTINEL_FACTCHECK_LENZ_API_KEY)` |
| 5 | `doctor` with only `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` set | `fact-check gate: off (pass --use-external-api (or set DOCSENTINEL_USE_EXTERNAL_API=1))` — `doctor` always resolves as if the flag were absent, per its own docstring |
| 6 | `doctor` with both the key and `DOCSENTINEL_USE_EXTERNAL_API=1` set | `fact-check gate: off (backend lenz not available)` |
| 7 | Confirm no network call is attempted in any of the above: run step 1 under a sandbox with outbound network disabled | Identical output; `DS302` returns before importing a backend module or reading any document for fact-checking (`fact_check.py` docstring: "a closed gate logs one WARNING and returns before any document is read") |

Never point `DOCSENTINEL_FACTCHECK_LENZ_API_KEY` at a real Lenz key for this checklist — steps
1–7 above never reach the backend constructor, so a real key would sit in your shell environment
for no reason. `test-only-not-real` (a string that is obviously not a credential) is enough to
exercise "key present."

### Advanced: a full round-trip with a local fake backend (no network, real claims from the article)

Because Stories 02.0 and 03.0 are not built, the only way to see `DS302` actually turn a claim
into a finding today is the same technique the project's own test suite uses
(`tests/fact_check_fakes.py`, `tests/mock/test_fact_check_no_key_logged.py`): register a throwaway
backend class under the name `lenz` and monkeypatch `collect_candidates` to skip the not-yet-built
selection stub. This never contacts `lenz.io` and never reads the leaked key from
`lenz_fact-checking.md` — it scripts its own fake verdicts locally. Save this as a scratch script
(do not commit it under `src/` or `tests/`) and run it with `uv run python`:

```python
import os
from pathlib import Path

from docsentinel import scan
from docsentinel.config import Config
from docsentinel.detectors import fact_check
from docsentinel.fact_check.protocol import FACT_CHECK_BACKENDS, FactCheckResult
from docsentinel.mining import claims, nlp

ROOT = Path("examples/docs")
ARTICLE = "New_MRI_breakthrough_reveals_the_brain_and_eye_like_never_before.md"


class LocalFakeLenz:
    name = "lenz"
    API_KEY_ENV_VAR = "DOCSENTINEL_FACTCHECK_LENZ_API_KEY"

    def __init__(self, *, api_key: str):
        self._api_key = api_key  # never logged, never returned

    def check_claim(self, claim: str) -> FactCheckResult:
        if "7.0 Tesla" in claim:
            return FactCheckResult(verdict="mixed", confidence=0.72, backend="lenz", citations=())
        return FactCheckResult(verdict="true", confidence=0.95, backend="lenz", citations=())

    def close(self):
        pass


def main() -> None:
    pipeline = nlp.load_pipeline()
    text = (ROOT / ARTICLE).read_text(encoding="utf-8")
    extracted = claims.extract_claims(pipeline, text, ARTICLE)
    picked = [
        c for c in extracted
        if "7.0 Tesla" in c.raw_sentence or "has developed a new MRI antenna" in c.raw_sentence
    ]
    candidates = tuple(
        fact_check.CandidateClaim(claim=c, text=c.raw_sentence.strip()[:1000], score=0.9) for c in picked
    )

    FACT_CHECK_BACKENDS["lenz"] = LocalFakeLenz
    os.environ["DOCSENTINEL_FACTCHECK_LENZ_API_KEY"] = "local-fake-key-not-real"
    original = fact_check.collect_candidates
    fact_check.collect_candidates = lambda root, documents, config: candidates
    try:
        config = Config(profile="deep", deep_confirm=True, fact_check_backend="lenz")
        result = scan(ROOT, config=config, use_external_api=True)
    finally:
        fact_check.collect_candidates = original
        del FACT_CHECK_BACKENDS["lenz"]
        os.environ.pop("DOCSENTINEL_FACTCHECK_LENZ_API_KEY", None)

    for finding in result.findings:
        print(finding.rule, finding.path, "|", finding.message)


if __name__ == "__main__":
    main()
```

| # | Step | Expected |
|---|------|----------|
| 8 | Run the script as written | One `DS302 external fact-check disagreement` finding on the article: `external fact-check: '...7.0 Tesla MRI scanner.' rated mixed by lenz - review to confirm`. The "team ... has developed a new MRI antenna" claim is rated `true` at confidence `0.95` and produces **no** finding: `true` is not in `REPORTABLE_VERDICTS` (`{"false", "mixed"}`) |
| 9 | Add `fact_check_min_confidence=0.72` to the `Config(...)` call (exactly the scripted confidence), re-run | Still one finding: the comparison in `_check_candidates` is `result.confidence >= min_confidence`, inclusive |
| 10 | Change it to `0.73` (one hundredth above the scripted confidence), re-run | Zero findings: the floor is now strictly above `0.72` |
| 11 | Set `fact_check_min_salience=0.99` (the least permissive value the field allows) and, separately, `fact_check_max_claims_per_document=1`, re-run each | **Identical** one-finding result both times — in this interim build `collect_candidates` is monkeypatched directly, so `select_candidates` (the only place that reads these two fields) is never called at all. A verified no-op, not a guess: confirmed by also calling `validate_fact_check_option("fact_check_min_salience", 1.5)` directly, which still raises `ConfigError: fact_check_min_salience must be a number between 0 and 1` — the validator works, nothing in this interim path calls it with the live value |
| 12 | Give the fake backend a 0.6s delay per call, set `fact_check_time_budget_seconds=1`, and send 3 candidates ordered so the one scripted `mixed` verdict is **third** | Zero `DS302` findings, and `result.pending` stays `()` — the skip is **not** surfaced there. Attach a logger instead: it shows `DS302: time budget of 1 s exhausted; 1 of 3 claim(s) not checked` and `... 2 sent ... 1 not sent (time budget)`. A QA pass that only reads the rendered report's `Pending:` line, rather than the log, will not notice a time-budget cutoff happened |
| 13 | Register a second fake backend (a well-formed name — `BACKEND_NAME_PATTERN` is `^[a-z][a-z0-9]{0,31}$`, no hyphen or underscore) that rates everything `false` at confidence `0.99`, set `fact_check_backend` to its name, re-run | Both candidates become findings: the "true" antenna claim now also reports, because the *backend*, not DS302's own logic, produced the verdict. Confirms `fact_check_backend` genuinely switches which service's opinion is trusted |
| 14 | Set `fact_check_backend` to a well-formed but unregistered name, e.g. `"unknownbackend"` | `ConfigError: fact_check_backend must be one of: lenz` — a typo in the backend name fails closed before any candidate is touched, exactly like an unknown value for any other enum-validated option |

### Adjusting DS302's weights and parameters

Unlike `DS301`, `DS302` has real, validated `Config` fields (`config.py`, `validate_fact_check_option`).
All of them are re-validated at every layer that reads them (even an injected `Config` cannot
bypass validation), and none of them is accepted from the user settings file —
`fact_check_backend` is not in `USER_SETTINGS_REFUSED_KEYS`, but `link_root`, `baseline`, etc. are,
for comparison; check `docsentinel doctor`'s `project config:` count to confirm where a value came
from:

| Option | Default | Effect | Where it is read |
|---|---|---|---|
| `fact_check_backend` | `"lenz"` | Which registered backend receives claims; must be in `FACT_CHECK_BACKEND_NAMES` (or a test-registered fake) | `_validated_backend`, gate resolution |
| `fact_check_min_salience` | `0.5` | Smallest salience score (`[0, 1]`) a claim needs *before* it may be selected to send | `select_candidates` (currently a no-op: it validates this but selects nothing until Story 02.0) |
| `fact_check_min_confidence` | `0.6` | Smallest backend confidence (`[0, 1]`) for a `false`/`mixed` verdict to become a finding | `_check_candidates`; verified live in checklist steps 8–10 above |
| `fact_check_max_claims_per_document` | `3` | Cap on claims sent per document | `select_candidates` (not yet enforced; validated only) |
| `fact_check_max_claims_total` | `25` | Cap on claims sent per scan | `select_candidates` (not yet enforced; validated only) |
| `fact_check_time_budget_seconds` | `300` | Wall-clock budget (`1`–`3600`) for the whole `DS302` network stage; claims left over when it expires are skipped with one WARNING, never sent | `_check_candidates`'s deadline loop |

Practical tuning guidance, once Stories 02.0/03.0 land and the options start doing their full job:

- **False positives from borderline backend verdicts**: raise `fact_check_min_confidence` first
  (verified above: `0.73` suppressed a `0.72`-confidence `mixed` verdict with no code change, and
  `0.72` itself still reported — the floor is an inclusive `>=`, so set it to the smallest
  confidence you want to *keep*, not the largest you want to drop). This is the cheapest lever
  because it is applied locally, after the network round trip, so tuning it never changes what was
  sent or logged.
- **Too many/too few claims examined**: once Story 02.0 lands, `fact_check_min_salience` will be
  the recall/precision knob on *selection* (fewer, higher-salience claims vs. broader coverage);
  until then, changing it has no observable effect — confirmed above by setting it to its most
  restrictive value and seeing the same finding anyway, and separately confirming its validator
  still rejects an out-of-range value on its own. Do not conclude "it doesn't work" from a QA run
  before Story 02.0 closes; re-check `status.md`'s story table first.
- **Cost/latency**: `fact_check_max_claims_per_document`, `fact_check_max_claims_total` and
  `fact_check_time_budget_seconds` bound how much a scan can send and how long it can take;
  raising the budget trades latency for completeness, lowering it trades completeness for a
  predictable scan time. All three are integer-bounded ranges enforced by
  `validate_fact_check_option` — an out-of-range value is a `ConfigError`, not a clamp. Of the
  three, only `fact_check_time_budget_seconds` is live today (checklist step 12): a claim dropped
  by the budget is logged at WARNING but is **not** added to `ScanResult.pending` or the report's
  `Pending:` line, so a time-budget cutoff is invisible to anyone reading only the rendered report
  — check the log (or `-v`) when a scan feels like it checked fewer claims than expected.
- **Switching backend**: `fact_check_backend` is the only field that changes *which* service's
  verdicts and confidence calibration apply (checklist step 13 flips every verdict from mixed/true
  to false by switching backend alone, with no other option touched); it has no effect on `DS301`,
  which never calls out to any backend. An unrecognised name fails closed with `ConfigError`
  before any candidate is touched (checklist step 14) — the same fail-closed shape as any other
  enum-validated `Config` field, not a silent fallback to `lenz`.

None of these six options unlock `DS302` on their own while either consent gate is closed — that
is deliberate (ADR 0007 Contracts 3–4; threat model
[`0010-fact-check-gating`](/docs/security/threat-model-0010-fact-check-gating-2026-11-23.md)):
configuration is for *tuning* an already-consented scan, not for *granting* network egress. A test
run that changes a `fact_check_*` value and sees no behavior change should first check `doctor`'s
`fact-check gate:` line before suspecting the option itself.

## See also

- [Configuration reference: how to set options](../user/reference/configuration.md#how-to-set-options)
- [Rules reference: DS301, DS302](../user/reference/rules.md)
- [ADR 0007: fact-check backend protocol and dual consent gate](../adr/0007-fact-check-backend-protocol-and-dual-consent-gate.md)
- [Threat model: 0010 fact-check gating](../security/threat-model-0010-fact-check-gating-2026-11-23.md)
- [Milestone 0010 plan and status](../roadmap/0010-fact-check/plan.md)
- [The test suite guide](README.md)
