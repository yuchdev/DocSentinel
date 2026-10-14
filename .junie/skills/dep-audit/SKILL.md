---
name: dep-audit
description: Audit Python dependency manifests for known vulnerabilities, outdated security-sensitive pins, and license compatibility after manifest changes, on a cadence, or on request.
---

# Dependency audit

Run after `pyproject.toml`, `uv.lock`, or requirements files change, during periodic maintenance, or
when explicitly requested.

1. Run `uv run pip-audit --progress-spinner off`, falling back to an available `pip-audit`.
2. Inspect `uv tree --outdated` and flag security-relevant major-version lag.
3. Enumerate direct dependencies and determine each license from installed metadata or authoritative
   package sources. Classify permissive licenses as Allow; LGPL and unusual/modified weak-copyleft
   terms as Flag; GPL, AGPL, SSPL, source-available restrictions, no license, and unknown licenses as
   Block unless the repository's distribution policy explicitly says otherwise.
4. Ask `background-reviewer` to write `docs/reviews/YYYY-MM-DD-dep-audit.md` with evidence,
   severities, and recommended upgrades or replacements.

Report package, installed version, advisory ID, severity, fixed version, license, and ruling. Never
silently omit unknown data. A critical/high vulnerability requires an immediate remediation proposal
and regression run; a blocking license requires replacement or explicit human/legal disposition.