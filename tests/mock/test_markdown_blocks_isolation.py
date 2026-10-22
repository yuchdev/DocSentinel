"""Isolation tests proving the shared scanner stays standard-library only.

A subprocess must import ``docsentinel`` and the shared scanner, and run a
fast-profile scan, without eagerly pulling in any lazily-loaded optional
dependency (the ``standard`` extras ``sklearn``/``textstat``/``docsig`` and
``textacy``). ``spacy`` is intentionally excluded from these assertions: the
pre-existing deep detector (``docsentinel.detectors._triples``) imports it at
module load time, which is outside the scope of this shared scanner and is
unchanged by it.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

# Optional dependencies whose import the shared scanner and fast profile must
# never eagerly trigger. ``spacy`` is deliberately omitted (see module docstring).
_LAZY_HEAVY = {"textacy", "sklearn", "textstat", "docsig"}


def _run(code: str) -> subprocess.CompletedProcess[str]:
    """Run ``code`` in an isolated subprocess interpreter.

    :param code: Python source to execute.
    :returns: The completed subprocess result.
    """
    return subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)


def test_import_scanner_loads_no_lazy_heavy_modules():
    """
    [Unit] markdown blocks isolation: importing the scanner loads no lazy heavy deps.

    Scenario:
        Given a fresh subprocess interpreter
        When docsentinel and the shared scanner are imported
        Then no lazily-loaded optional dependency is present in sys.modules.

    Boundaries:
        - Focus: stdlib-only scanner import surface
        - Fixtures/params: none
        - Scope: this test case only

    On failure, first check:
        - The subprocess stderr for the failing import or assertion
        - Any new import added to markdown_blocks
    """
    code = textwrap.dedent(
        f"""
        import sys
        import docsentinel
        from docsentinel.markdown_blocks import scan_markdown

        index = scan_markdown("# Title\\n", "README.md")
        assert index.headings[0].slug == "title"

        leaked = {_LAZY_HEAVY!r}.intersection(sys.modules)
        assert not leaked, f"lazy heavy modules imported: {{leaked}}"
        """
    )
    result = _run(code)

    assert result.returncode == 0, result.stderr


def test_fast_scan_runs_without_lazy_heavy_modules(tmp_path: Path):
    """
    [Unit] markdown blocks isolation: a fast scan runs without lazy heavy deps.

    Scenario:
        Given a temporary document and a fresh subprocess interpreter
        When a default fast scan runs
        Then it succeeds and loads no lazily-loaded optional dependency.

    Boundaries:
        - Focus: fast-profile scan import surface
        - Fixtures/params: tmp_path
        - Scope: this test case only

    On failure, first check:
        - The subprocess stderr for the failing import or assertion
        - The fast profile analyzer import boundary
    """
    (tmp_path / "README.md").write_text("# Title\n\nSome prose.\n", encoding="utf-8")

    code = textwrap.dedent(
        f"""
        import sys
        from docsentinel import scan

        result = scan({str(tmp_path)!r})
        assert result.profile == "fast"
        assert any(doc.path == "README.md" for doc in result.documents)

        leaked = {_LAZY_HEAVY!r}.intersection(sys.modules)
        assert not leaked, f"lazy heavy modules imported: {{leaked}}"
        """
    )
    result = _run(code)

    assert result.returncode == 0, result.stderr
