# Security

Threat models, security review outputs, and posture documentation for DocSentinel.

The `security-auditor` agent owns this directory. Every change touching auth,
secrets, external integrations, or untrusted-input ingestion triggers a security
review whose output is stored here.

## Naming convention

`threat-model-<scope>.md` for threat models, `review-<scope>-<YYYY-MM-DD>.md`
for point-in-time reviews.

## What a threat model must contain

1. **Scope** - which components and trust boundaries are in scope.
2. **Assets** - what secrets, PII, and data are handled.
3. **Threat actors** - attacker profiles considered.
4. **STRIDE analysis** - Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation.
5. **Mitigations** - existing controls and open gaps.
6. **Verdict** - CRITICAL (merge blocked) / HIGH / MEDIUM / LOW / INFO.

## Security rules (non-negotiable)

- Never log secrets; rely on this project's log-redaction mechanism (if any)
  and verify it covers new sinks.
- Never hard-code credentials. Read from settings/env.
- Treat all untrusted external input as sensitive - no unredacted raw input
  in logs, exceptions, stored reports, or API error bodies.
- Untrusted input must never reach a shell, SQL string, `eval`, or an AI
  prompt without sanitisation/parameterisation.

> **SME REVIEW NEEDED (AI-drafted - verify before relying on this):**
> **Initial threat model: DocSentinel M0 inventory scan**
>
> **Scope**
> - Components: `config.py` (`load_config`), `discovery.py` (`discover`), `engine.py` (`scan`, `ANALYZERS`), `reporting.py` (`render`), `cli.py` (`main`), `pytest_plugin.py`, and the `docsentinel-fast` pre-commit hook.
> - Trust boundaries:
>   - The scanned repository tree, including its `docsentinel.toml`. It is untrusted because DocSentinel runs in CI and pre-commit on contributor-controlled checkouts.
>   - The CLI arguments.
>   - The report output, which goes to CI logs.
> - M0 makes no network or model calls, and the package does no logging.
>
> **Assets**
> - Document paths and sizes. These are emitted in full in text and JSON reports.
> - Markdown contents. M0 does not read them; future analyzers will.
> - Config contents.
> - The integrity of the pass/fail signal (exit codes `0`/`1`/`2`) that CI and pre-commit rely on.
>
> **Threat actors**
> - A contributor who submits a malicious or malformed tree or config in a PR.
> - A dependency supply-chain compromise. `flakeforge` and `release-saga` are pinned but unused, and the build backend is `hatchling`.
>
> **STRIDE**
> - *Spoofing*: N/A. There is no authentication surface.
> - *Tampering*: A contributor can edit `docsentinel.toml` `exclude`/`include` patterns, or pick a different `--config` path, to hide documents from the scan. Today's impact is low because no detectors run; it becomes high once detectors exist.
>   - Symlinked files and directories are not followed (`discovery.py`), and a symlinked single-file target raises `ValueError` (`engine.py`).
>   - `init` opens with mode `"x"`, so it cannot overwrite an existing file.
> - *Repudiation*: N/A for a local CLI.
> - *Information disclosure*:
>   - JSON and text reports list every matched relative path.
>   - `ConfigError` and `Scan failed:` messages echo filesystem paths and `tomllib` parse errors to stderr and CI logs.
>   - Future `deep` integrations would send document contents to external services and must stay opt-in.
> - *Denial of service*:
>   - `discover()` walks the entire tree and buffers the full inventory in memory before sorting. Very large trees or many patterns slow every pre-commit run.
>   - There is no size or file-count limit.
> - *Elevation of privilege*:
>   - No shell, `eval` or subprocess use exists in `src/docsentinel/`.
>   - `tomllib` is a data-only parser.
>   - The pytest plugin is opt-in (`-p docsentinel.pytest_plugin`).
>
> **Mitigations and open gaps**
> - Existing controls:
>   - Strict config schema: only the `[docsentinel]` table, known keys, non-empty string patterns, and an enumerated `profile`.
>   - Symlink refusal.
>   - Walk errors propagate instead of being swallowed.
>   - CI uses `--locked` dependency sync and `contents: read` workflow permissions.
> - Open gaps:
>   - No limit on tree size or file size.
>   - No check that excludes do not hide in-scope docs.
>   - The unused pinned runtime dependencies widen the supply-chain surface without benefit.
>   - Future content-reading analyzers need their own review of parsing and memory limits.
>
> **Verdict**: LOW for M0, since it only inventories files and makes no network calls. Re-assess when the first `ANALYZERS` entry or any `deep` integration lands.
