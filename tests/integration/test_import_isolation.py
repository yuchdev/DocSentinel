"""Fast-profile optional-dependency import isolation (Story 15.0 Task 02 B).

The 15.0 contract requires that importing :mod:`docsentinel` and running a fast scan
never imports the optional standard (scikit-learn/textstat/docsig) or deep
(spacy/textacy) dependencies. Before this task a plain ``import docsentinel`` pulled in
spaCy eagerly through ``detectors/__init__`` -> ``contradictions`` -> ``_triples``; the
analyzer's ``_triples`` import is now deferred to the first deep scan, while the DS301
rule metadata and analyzer stay registered eagerly. These tests prove the boundary in a
fresh isolated interpreter so no earlier in-process import can mask a leak.
"""

import importlib.util
import subprocess
import sys
import textwrap
from pathlib import Path

from docsentinel.engine import scan

#: The optional heavy dependencies that must never load on the fast path.
_HEAVY_MODULES: tuple[str, ...] = ("spacy", "textacy", "sklearn", "textstat", "docsig")


def _run_probe(code: str) -> str:
    """Run a probe snippet in a fresh isolated interpreter and return its stdout.

    :param code: Python source executed with ``-I`` (isolated: no site customizations,
        env vars or cwd on ``sys.path``), so only installed packages are importable.
    :returns: The probe's stripped stdout.
    """
    completed = subprocess.run(
        [sys.executable, "-I", "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


#: A fast-scan probe: import the package, scan a small real corpus, then report which of
#: the heavy modules leaked into ``sys.modules``.
_FAST_SCAN_PROBE: str = """
    import sys, tempfile, pathlib
    import docsentinel
    from docsentinel.engine import scan

    root = pathlib.Path(tempfile.mkdtemp())
    (root / "doc.md").write_text(
        "# Title\\n\\nSome prose about configuration.\\n\\n"
        "[link](./other.md)\\n\\n"
        "```python\\nx = 1\\n```\\n\\n"
        "| a | b |\\n| - | - |\\n| 1 | 2 |\\n",
        encoding="utf-8",
    )
    scan(root)
    heavy = sorted(m for m in ("spacy", "textacy", "sklearn", "textstat", "docsig") if m in sys.modules)
    print(",".join(heavy))
"""


def test_fast_scan_imports_no_optional_heavy_dependencies():
    """
    [Integration] import isolation: verifies a fast scan loads no optional heavy dependency.

    Scenario:
        Given a fresh isolated interpreter that imports docsentinel and runs a fast scan over a
        small corpus of headings, a link, a fence and a table
        When the loaded modules are inspected afterwards
        Then none of spacy, textacy, sklearn, textstat or docsig is present in sys.modules.

    Boundaries:
        - Focus: the whole fast path, end to end, in a subprocess that cannot be masked by prior imports
        - Fixtures/params: none
        - Scope: one isolated interpreter

    On failure, first check:
        - The printed comma-separated list naming the heavy module that leaked
        - Whether a detector or the engine gained an eager standard/deep import
    """
    assert _run_probe(_FAST_SCAN_PROBE) == ""


#: A probe proving the deep analyzer's spaCy dependency loads only when its module is
#: imported -- not merely by importing docsentinel or running a fast scan.
_DEEP_LAZY_PROBE: str = """
    import sys, importlib, tempfile, pathlib
    import docsentinel
    from docsentinel.engine import scan

    root = pathlib.Path(tempfile.mkdtemp())
    (root / "doc.md").write_text("# Title\\n\\nSome prose.\\n", encoding="utf-8")
    scan(root)
    before = "spacy" in sys.modules
    importlib.import_module("docsentinel.detectors._triples")
    after = "spacy" in sys.modules
    print(f"{before},{after}")
"""


def test_deep_analyzer_code_path_loads_spacy_lazily():
    """
    [Integration] import isolation: verifies spaCy loads only when the deep analyzer module is imported.

    Scenario:
        Given a fresh interpreter that imports docsentinel and runs a fast scan
        When spaCy's presence is checked before and after importing the deep analyzer's _triples module
        Then spaCy is absent after import+fast-scan and present only once _triples is imported, proving
        the lazy boundary is the deep analyzer module, independent of the spaCy model being installed.

    Boundaries:
        - Focus: the lazy-import boundary for the deep path, provable without the en_core_web_sm model
        - Fixtures/params: none
        - Scope: one isolated interpreter

    On failure, first check:
        - Whether the first flag is True (spaCy leaked before any deep work) or the second is False
        - Whether _triples stopped importing spaCy at module load
    """
    assert _run_probe(_DEEP_LAZY_PROBE) == "False,True"


#: A standard-scan probe (only meaningful when the standard extras are installed): run a
#: standard-profile scan and report whether its dependencies loaded.
_STANDARD_SCAN_PROBE: str = """
    import sys, tempfile, pathlib
    import docsentinel
    from docsentinel.config import Config
    from docsentinel.engine import scan

    root = pathlib.Path(tempfile.mkdtemp())
    (root / "a.md").write_text("# A\\n\\n" + ("word " * 80) + "\\n", encoding="utf-8")
    (root / "b.md").write_text("# B\\n\\n" + ("word " * 80) + "\\n", encoding="utf-8")
    scan(root, config=Config(profile="standard"))
    loaded = sorted(m for m in ("sklearn", "textstat") if m in sys.modules)
    print(",".join(loaded))
"""


def test_standard_scan_loads_its_dependencies_when_installed():
    """
    [Integration] import isolation: verifies a standard scan loads its extras (when installed).

    Scenario:
        Given the standard extras installed, a fresh interpreter runs a standard-profile scan
        When the loaded modules are inspected
        Then scikit-learn and textstat are present, confirming the lazy loader pulls the standard
        dependencies in on demand; when the extras are absent this instead asserts the fast path
        still imports none of them (never a skip).

    Boundaries:
        - Focus: the standard lazy loader actually loads its dependencies on a standard scan
        - Fixtures/params: gated on sklearn being importable, without pytest.skip
        - Scope: one isolated interpreter

    On failure, first check:
        - Whether ensure_standard_loaded stopped importing the standard package
        - The printed list of which standard modules did load
    """
    if importlib.util.find_spec("sklearn") is None:
        assert _run_probe(_FAST_SCAN_PROBE) == ""
        return
    assert _run_probe(_STANDARD_SCAN_PROBE) == "sklearn,textstat"


def test_plain_import_docsentinel_does_not_load_spacy():
    """
    [Integration] import isolation: verifies a bare ``import docsentinel`` does not load spaCy.

    Scenario:
        Given a fresh isolated interpreter
        When it imports docsentinel and its detector registry but does nothing else
        Then spaCy is not in sys.modules, proving the eager import regression is gone.

    Boundaries:
        - Focus: the exact regression (import docsentinel -> spacy) the 15.0 contract forbids
        - Fixtures/params: none
        - Scope: one isolated interpreter

    On failure, first check:
        - Whether a module reintroduced an eager ``from docsentinel.detectors._triples import ...``
    """
    probe = """
        import sys
        import docsentinel
        import docsentinel.detectors
        print("spacy" in sys.modules)
    """
    assert _run_probe(probe) == "False"


def test_fast_scan_probe_is_a_real_path(tmp_path: Path):
    """
    [Integration] import isolation: verifies the probe corpus actually exercises fast detectors.

    Scenario:
        Given the same small corpus the subprocess probe writes
        When it is scanned in-process with the fast profile
        Then the scan yields at least one finding (the dangling link), so the isolation probe is not
        vacuously importing heavy modules on an empty, rule-free run.

    Boundaries:
        - Focus: guard that the probe's corpus genuinely runs the fast rules it claims to
        - Fixtures/params: tmp_path
        - Scope: one in-process fast scan

    On failure, first check:
        - Whether the fast rules stopped flagging the dangling ./other.md link
    """

    (tmp_path / "doc.md").write_text(
        "# Title\n\nSome prose about configuration.\n\n[link](./other.md)\n",
        encoding="utf-8",
    )
    result = scan(tmp_path)
    assert any(finding.rule.startswith("DS") for finding in result.findings)
