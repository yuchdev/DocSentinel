# Security Review & Threat Model: GitHub Actions Workflow Command Annotations

**Date:** 2026-10-10
**Feature:** GitHub Actions Workflow Command Annotation Formatting (`--format github`)
**Target Files:**
- `src/docsentinel/reporting.py`
- `src/docsentinel/cli.py`
- `tests/test_reporting.py`
**Reviewer:** Security Auditor (DocSentinel Team)
**Verdict:** `PASS_WITH_FOLLOWUP`

---

## 1. Executive Summary & Context

DocSentinel provides automated documentation quality assurance. To integrate seamlessly with GitHub Actions CI/CD workflows, DocSentinel implements a dedicated output formatter (`--format github`) emitting GitHub Actions workflow command annotations (`::error ...` and `::warning ...`).

Because GitHub Actions workflow commands are interpreted directly by the CI runner from standard output, untrusted input contained within scanned documentation (such as file paths, link targets, heading anchors, or comment snippets) could theoretically attempt CI workflow command injection or delimiter corruption if not neutralized.

This assessment conducted an exhaustive STRIDE threat model and implementation verification covering command injection, delimiter escaping, severity parsing, data exposure, determinism, and test coverage.

---

## 2. External Inputs, Assets, and Trust Boundaries

### 2.1 Trust Boundaries
- **Untrusted Source Artifacts:** Scanned Markdown files, directory names, file paths, heading text, link targets, and raw code spans located within the scanned repository. These may be attacker-controlled in open-source pull requests or multi-tenant repository scans.
- **DocSentinel Internal Pipeline:** Scanner, rule detectors (`DS101`, `DS102`, `DS103`), and immutable data contracts (`Finding`, `ScanResult`).
- **CI / Runner Trust Boundary:** The stdout stream consumed by the GitHub Actions runner environment and parsed by the runner's workflow command processor.

### 2.2 Key Assets
- **CI Runner Integrity & Pipeline Control:** Prevention of unauthorized workflow command execution (e.g. runner control manipulation, environment modification, or arbitrary step outputs).
- **Log & Annotation Integrity:** Accurate, uncorrupted diagnostic rendering without syntax breakage or swallowed findings.
- **Repository Confidentiality:** Prevention of sensitive document content leakage or secret exposure in CI output streams.

---

## 3. STRIDE Threat Model & Security Scope Evaluation

### 3.1 CI Workflow-Command Injection (Spoofing / Tampering / Elevation of Privilege)
*Applicable Standards: CWE-74, CWE-93, CWE-116, OWASP Top 10 A03:2021 (Injection), OWASP CI/CD Risk CICD-SEC-08*

- **Threat:** An attacker crafts a Markdown document with newlines (`\r`, `\n`) or percent-encoded sequences (`%0A`) in a link, comment, or path to break out of the annotation line and inject arbitrary runner commands (e.g. `::set-output`, `::add-mask`, `::stop-commands`).
- **Implementation Analysis (`src/docsentinel/reporting.py:14-16, 26-35`):**
  - Data escaping function `_escape_data(value: str)` executes:
    `value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")`
  - Escaping order is strictly correct: `%` is substituted first with `%25`. This prevents percent-encoding bypasses (e.g., `%0A` becomes `%250A`, which the runner decodes safely as literal text `%0A` rather than a newline).
  - Carriage returns (`\r` → `%0D`) and line feeds (`\n` → `%0A`) are fully replaced.
  - Every finding emits a strictly single-line annotation without unescaped newlines.
- **Finding:** Verified secure against workflow command injection.

### 3.2 Property Delimiter Escaping (Tampering / Message Distortion)
*Applicable Standards: CWE-116 (Improper Encoding or Escaping of Output)*

- **Threat:** File paths containing commas (`,`), colons (`:`), percent signs (`%`), or newlines could disrupt GitHub Actions key-value property parsing (`file=...,line=...`), causing property confusion, truncated file paths, or injected command parameters.
- **Implementation Analysis (`src/docsentinel/reporting.py:9-12, 31-34`):**
  - Property escaping function `_escape_property(value: str)` executes:
    `value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")`
  - Escapes `%`, `\r`, `\n`, `:`, and `,` in strict conformity with the official GitHub Actions runner / `@actions/core` specification.
  - Colons (`:`) are encoded to `%3A` to prevent premature termination of the property block (`::level properties::message`).
  - Commas (`,`) are encoded to `%2C` to preserve multi-parameter structures.
- **Finding:** Verified secure against property delimiter injection and structure corruption.

### 3.3 Severity Mapping & Unknown Inputs (Denial of Service / Integrity)
*Applicable Standards: CWE-20 (Improper Input Validation), CWE-754 (Improper Check for Unusual or Exceptional Conditions)*

- **Threat:** Unexpected, custom, or malformed severity strings cause unhandled exceptions (crashing CI scans) or allow command level tampering.
- **Implementation Analysis (`src/docsentinel/reporting.py:19-23, 30`):**
  - `_gha_level(severity: str)` strictly checks `if severity == "error": return "error"` and falls back to `"warning"` for all other inputs.
  - It is resilient against empty strings, custom severities, or malicious strings (e.g., `"error\n::malicious"` returns `"warning"` because it does not equal `"error"`).
  - CLI exit code calculation (`src/docsentinel/cli.py:23-33`) cleanly separates `error` (returns exit code 1) from non-error findings (returns 0 unless `--strict` is set).
- **Finding:** Verified robust and resilient against unexpected inputs.

### 3.4 Data Exposure & Information Disclosure (Information Disclosure)
*Applicable Standards: CWE-200 (Exposure of Sensitive Information)*

- **Threat:** Emitting entire document payloads, environment variables, or sensitive file system metadata into CI annotations.
- **Implementation Analysis (`src/docsentinel/reporting.py:26-35`, `src/docsentinel/discovery.py:32`):**
  - Annotations only expose workspace-relative posix paths, 1-based line numbers, and concise diagnostic messages.
  - Detector implementations (e.g. `DS102` in `comments.py`) truncate matched comment content to 80 characters using safe `repr()` formatting.
  - No complete document body, environment variable, or absolute host path is emitted. Findings may
    contain only the concise source excerpt needed by the detector contract; `DS102` bounds that
    excerpt to 80 characters.
- **Finding:** Verified compliant with project privacy and security invariants.

### 3.5 Determinism & Integrity (Tampering / Invariant Violation)
*Applicable Standards: CWE-664 (Improper Control of a Resource Through its Lifetime)*

- **Threat:** Mutable contracts or non-deterministic ordering causing flakiness or inconsistent CI results.
- **Implementation Analysis (`src/docsentinel/models.py:7-30`, `src/docsentinel/reporting.py:26-35`):**
  - `Document`, `Finding`, and `ScanResult` are immutable (`frozen=True`).
  - Discovery performs deterministic sorting by file path.
  - Clean scans emit an empty string `""` without extraneous preamble, avoiding false CI annotation noise.
- **Finding:** Verified deterministic and state-immutable.

---

## 4. Security Findings & Recommendations Table

| ID | Title / Target | Severity | CWE / Standards | Impact | Recommendation & Specialist Routing |
|---|---|---|---|---|---|
| **SEC-01** | Workflow Command Injection Defense | **INFORMATIONAL (PASS)** | CWE-74, CWE-93, CWE-116 | None (Properly mitigated) | Maintained in `src/docsentinel/reporting.py`. Escapes `%`, `\r`, `\n` in exact order. |
| **SEC-02** | Delimiter Escaping in Annotation Properties | **INFORMATIONAL (PASS)** | CWE-116 | None (Properly mitigated) | Maintained in `src/docsentinel/reporting.py`. Escapes `%`, `\r`, `\n`, `:`, `,`. |
| **SEC-03** | Unknown Severity Fail-Safe Mapping | **INFORMATIONAL (PASS)** | CWE-20 | None (Properly mitigated) | Hardened default mapping to `"warning"`. |
| **REC-01** | Defense-in-Depth: Explicit Line Integer Type Validation | **LOW (Follow-up)** | CWE-20 | If external plugins fabricate non-integer/string `Finding.line`, unescaped characters could bypass property escaping. | Validate `isinstance(finding.line, int) and finding.line > 0` before formatting `line={finding.line}`. Route to `python-expert` and `testing-expert`. |
| **REC-02** | Extended Regression Tests: Unicode & Non-ASCII Path / Message Escaping | **LOW (Follow-up)** | CWE-116 | High-plane Unicode or non-ASCII characters in Markdown paths could behave unpredictably on diverse CI runners. | Add targeted unit tests verifying Unicode handling in `tests/test_reporting.py`. Route to `testing-expert`. |
| **REC-03** | Annotation Title Metadata Enhancement | **INFO (Enhancement)** | N/A | Feature enhancement to display rule codes (e.g. `DS101`) in GitHub PR annotation headers. | Consider adding `title={finding.rule}` to the workflow command property list in future milestones. Route to `python-expert`. |

---

## 5. Specialist Routing & Follow-up Actions

- **`python-expert`**:
  - Implement defense-in-depth line validation in `src/docsentinel/reporting.py` ensuring `finding.line` is an integer $> 0$ before emitting `line=N`.
- **`testing-expert`**:
  - Add Unicode and boundary tests in `tests/test_reporting.py` (e.g. non-ASCII paths, multibyte characters, and malformed line value handling).

---

## 6. Audit Verdict

**Final Verdict:** `PASS_WITH_FOLLOWUP`

The implementation satisfies all security criteria and project invariants. It robustly mitigates workflow command injection and property delimiter corruption, properly handles unknown severities without crashing, preserves data confidentiality, and ensures deterministic CI output. No blocking or critical vulnerabilities were identified.
