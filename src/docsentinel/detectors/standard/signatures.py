"""Detect docstring and signature mismatches in Python source files.

Rule DS204 runs `docsig` over Python files discovered via `discover_python` and
converts docstring-vs-signature violations into error-severity findings.

Fragility and version notes:
- docsig does not expose a public structured report object. Its `docsig(...)` API
  runs checks and prints formatted text to stdout. We invoke `docsig` in-process
  with `no_ansi=True` and capture stdout using `contextlib.redirect_stdout`.
- If a future version of `docsig` introduces a public structured API, the stdout
  parser in `_parse_docsig_output` should be replaced by structured inspection,
  preserving the `Finding` mapping logic.
- We do not invoke docsig via a subprocess to avoid execution overhead and CLI argv
  coupling.
- Sub-code filtering (`SIGxxx`) and docstring style selection (Sphinx, NumPy, Google)
  are reserved for future configuration enhancements; `select` and `ignore` operate
  at the `DS204` rule level.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.code_discovery import discover_python
from docsentinel.config import load_config

DS204 = rules.register_rule(
    rules.Rule(
        code="DS204",
        profile="standard",
        title="Docstring/signature mismatch",
        description="A function docstring's documented parameters or returns do not match its signature.",
        severity="error",
    )
)

_HEADER_RE = re.compile(r"^(?:(?P<file>.+):)?(?P<lineno>\d+)\s+in\s+(?P<func>.+)$")
_VIOLATION_RE = re.compile(r"^\s*(?P<code>SIG\d+):\s*(?P<msg>.+)$")


@dataclass(frozen=True)
class _Violation:
    """Record representing a docsig signature violation."""

    file: str
    lineno: int
    function: str
    sig_code: str
    sig_message: str


def _get_known_sig_codes() -> frozenset[str]:
    """Return all known SIG error codes from docsig.messages schema."""
    docsig_messages = importlib.import_module("docsig.messages")

    codes: set[str] = set()
    if hasattr(docsig_messages, "E"):
        for msg in docsig_messages.E.values():
            if hasattr(msg, "ref"):
                codes.add(msg.ref)
    return frozenset(codes)


def _run_docsig(path: Path) -> str:
    """Run docsig on a Python file path in-process and return captured stdout."""
    docsig = importlib.import_module("docsig")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        docsig.docsig(str(path), no_ansi=True)
    return buf.getvalue()


def _parse_docsig_output(output: str, *, file: str) -> tuple[_Violation, ...]:
    """Parse docsig report text into _Violation records and validate SIG codes.

    Raises:
        ValueError: If an unrecognized SIG code is encountered in the report.
    """
    if not output.strip():
        return ()

    known_codes = _get_known_sig_codes()
    violations: list[_Violation] = []
    current_file = file
    current_lineno: Optional[int] = None
    current_func: Optional[str] = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue

        header_match = _HEADER_RE.match(line.strip())
        if header_match and not _VIOLATION_RE.match(line):
            hdr_file = header_match.group("file")
            current_file = file or (hdr_file or "")
            current_lineno = int(header_match.group("lineno"))
            current_func = header_match.group("func").strip()
            continue

        violation_match = _VIOLATION_RE.match(line)
        if violation_match:
            sig_code = violation_match.group("code")
            sig_msg = violation_match.group("msg").strip()

            if sig_code not in known_codes:
                raise ValueError(f"Unrecognized docsig code: {sig_code}")

            lineno = current_lineno if current_lineno is not None else 1
            func_name = current_func if current_func is not None else ""

            violations.append(
                _Violation(
                    file=current_file,
                    lineno=lineno,
                    function=func_name,
                    sig_code=sig_code,
                    sig_message=sig_msg,
                )
            )

    return tuple(violations)


def check_file(root: Path, path: Path) -> tuple[models.Finding, ...]:
    """Check a single Python source file for docstring/signature mismatches."""
    try:
        rel_path = path.relative_to(root).as_posix()
    except ValueError:
        rel_path = path.as_posix()

    output = _run_docsig(path)
    violations = _parse_docsig_output(output, file=rel_path)
    findings: list[models.Finding] = []
    for v in violations:
        findings.append(
            models.Finding(
                rule=DS204.code,
                path=rel_path,
                line=v.lineno,
                message=f"{v.function}: {v.sig_code} {v.sig_message}",
                severity=DS204.severity,
            )
        )
    return tuple(findings)


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
) -> tuple[models.Finding, ...]:
    """Return DS204 findings for Python source files discovered under root.

    Note: The `documents` parameter (Markdown document inventory) is intentionally
    unused. DS204 scans Python source files discovered via `discover_python(root, config)`
    rather than Markdown documentation.
    """
    config = load_config(root)
    python_files = discover_python(root, config)
    findings: list[models.Finding] = []
    for py_file in python_files:
        findings.extend(check_file(root, py_file))
    return tuple(findings)


rules.ANALYZERS[DS204.code] = detect
