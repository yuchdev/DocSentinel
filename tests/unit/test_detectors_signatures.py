"""Tests for DS204 docstring/signature mismatch detector."""

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("docsig")

import docsentinel.detectors.standard as std_pkg
from docsentinel import engine, models, rules
from docsentinel.detectors.standard import signatures

if "signatures" not in getattr(std_pkg, "__all__", []):
    rules.RULES.pop("DS204", None)
    rules.ANALYZERS.pop("DS204", None)


@pytest.fixture(autouse=True)
def _ensure_ds204_registered() -> Iterator[None]:
    """Ensure DS204 rule and analyzer are registered for signature test duration."""
    rules.RULES["DS204"] = signatures.DS204
    rules.ANALYZERS["DS204"] = signatures.detect
    yield
    if "signatures" not in getattr(std_pkg, "__all__", []):
        rules.RULES.pop("DS204", None)
        rules.ANALYZERS.pop("DS204", None)


def test_rule_metadata():
    """
    [Unit] detectors signatures: verifies rule metadata.

    Scenario:
        Given test inputs and fixtures for rule metadata
        When test_rule_metadata executes the target flow
        Then the expected outcome for rule metadata is confirmed.

    Boundaries:
        - Focus: rule metadata
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to rule metadata
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    assert signatures.DS204.code == "DS204"
    assert signatures.DS204.profile == "standard"
    assert signatures.DS204.title == "Docstring/signature mismatch"
    assert signatures.DS204.severity == "error"
    assert (
        signatures.DS204.description
        == "A function docstring's documented parameters or returns do not match its signature."
    )
    assert engine.ANALYZERS["DS204"] == signatures.detect


def test_parse_docsig_output_single_violation():
    """
    [Unit] detectors signatures: verifies parse docsig output single violation.

    Scenario:
        Given test inputs and fixtures for parse docsig output single violation
        When test_parse_docsig_output_single_violation executes the target flow
        Then the expected outcome for parse docsig output single violation is confirmed.

    Boundaries:
        - Focus: parse docsig output single violation
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parse docsig output single violation
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    canned_output = (
        "src/calc.py:10 in calculate\n    SIG202: includes parameters that do not exist (params-do-not-exist)\n"
    )
    violations = signatures._parse_docsig_output(canned_output, file="src/calc.py")
    assert len(violations) == 1
    v = violations[0]
    assert v.file == "src/calc.py"
    assert v.lineno == 10
    assert v.function == "calculate"
    assert v.sig_code == "SIG202"
    assert v.sig_message == "includes parameters that do not exist (params-do-not-exist)"


def test_parse_docsig_output_multiple_violations_one_function():
    """
    [Unit] detectors signatures: verifies parse docsig output multiple violations one function.

    Scenario:
        Given test inputs and fixtures for parse docsig output multiple violations one function
        When test_parse_docsig_output_multiple_violations_one_function executes the target flow
        Then the expected outcome for parse docsig output multiple violations one function is confirmed.

    Boundaries:
        - Focus: parse docsig output multiple violations one function
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parse docsig output multiple violations one function
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    canned_output = (
        "src/calc.py:10 in calculate\n"
        "    SIG202: includes parameters that do not exist (params-do-not-exist)\n"
        "    SIG305: description does not begin with a capital letter (description-not-capitalized)\n"
    )
    violations = signatures._parse_docsig_output(canned_output, file="src/calc.py")
    assert len(violations) == 2
    assert violations[0].lineno == 10
    assert violations[0].function == "calculate"
    assert violations[0].sig_code == "SIG202"
    assert violations[1].lineno == 10
    assert violations[1].function == "calculate"
    assert violations[1].sig_code == "SIG305"


def test_parse_docsig_output_unknown_sig_code_raises():
    """
    [Unit] detectors signatures: verifies parse docsig output unknown sig code raises.

    Scenario:
        Given test inputs and fixtures for parse docsig output unknown sig code raises
        When test_parse_docsig_output_unknown_sig_code_raises executes the target flow
        Then the expected outcome for parse docsig output unknown sig code raises is confirmed.

    Boundaries:
        - Focus: parse docsig output unknown sig code raises
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parse docsig output unknown sig code raises
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    canned_output = "src/calc.py:10 in calculate\n    SIG999: some brand new future violation format (unknown-code)\n"
    with pytest.raises(ValueError, match="Unrecognized docsig code: SIG999"):
        signatures._parse_docsig_output(canned_output, file="src/calc.py")


def test_parse_docsig_output_clean_is_empty():
    """
    [Unit] detectors signatures: verifies parse docsig output clean is empty.

    Scenario:
        Given test inputs and fixtures for parse docsig output clean is empty
        When test_parse_docsig_output_clean_is_empty executes the target flow
        Then the expected outcome for parse docsig output clean is empty is confirmed.

    Boundaries:
        - Focus: parse docsig output clean is empty
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to parse docsig output clean is empty
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    assert signatures._parse_docsig_output("", file="src/calc.py") == ()
    assert signatures._parse_docsig_output("   \n\n  ", file="src/calc.py") == ()


def test_check_file_flags_param_that_does_not_exist(tmp_path: Path):
    """
    [Unit] detectors signatures: verifies check file flags param that does not exist.

    Scenario:
        Given test inputs and fixtures for check file flags param that does not exist
        When test_check_file_flags_param_that_does_not_exist executes the target flow
        Then the expected outcome for check file flags param that does not exist is confirmed.

    Boundaries:
        - Focus: check file flags param that does not exist
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check file flags param that does not exist
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    py_content = (
        "def calculate(total: int) -> int:\n"
        '    """Calculate something.\n'
        "\n"
        "    :param total: The total value.\n"
        "    :param nonexistent: An extra parameter that does not exist.\n"
        "    :return: Calculated value.\n"
        '    """\n'
        "    return total * 2\n"
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    file_path = src_dir / "calc.py"
    file_path.write_text(py_content, encoding="utf-8")

    findings = signatures.check_file(tmp_path, file_path)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS204"
    assert finding.path == "src/calc.py"
    assert finding.line == 1
    assert finding.severity == "error"
    assert "calculate: SIG202 includes parameters that do not exist" in finding.message


def test_check_file_flags_undocumented_param(tmp_path: Path):
    """
    [Unit] detectors signatures: verifies check file flags undocumented param.

    Scenario:
        Given test inputs and fixtures for check file flags undocumented param
        When test_check_file_flags_undocumented_param executes the target flow
        Then the expected outcome for check file flags undocumented param is confirmed.

    Boundaries:
        - Focus: check file flags undocumented param
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to check file flags undocumented param
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    py_content = (
        "def process(a: int, b: int) -> int:\n"
        '    """Process values.\n'
        "\n"
        "    :param a: The first value.\n"
        "    :return: The result.\n"
        '    """\n'
        "    return a + b\n"
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    file_path = src_dir / "process.py"
    file_path.write_text(py_content, encoding="utf-8")

    findings = signatures.check_file(tmp_path, file_path)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule == "DS204"
    assert finding.path == "src/process.py"
    assert finding.line == 1
    assert finding.severity == "error"
    assert "process: SIG203" in finding.message


def test_well_documented_function_is_clean(tmp_path: Path):
    """
    [Unit] detectors signatures: verifies well documented function is clean.

    Scenario:
        Given test inputs and fixtures for well documented function is clean
        When test_well_documented_function_is_clean executes the target flow
        Then the expected outcome for well documented function is clean is confirmed.

    Boundaries:
        - Focus: well documented function is clean
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to well documented function is clean
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    py_content = (
        "def add(a: int, b: int) -> int:\n"
        '    """Add two numbers.\n'
        "\n"
        "    :param a: The first number.\n"
        "    :param b: The second number.\n"
        "    :return: Sum of the numbers.\n"
        '    """\n'
        "    return a + b\n"
    )
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    file_path = src_dir / "add.py"
    file_path.write_text(py_content, encoding="utf-8")

    findings = signatures.check_file(tmp_path, file_path)
    assert findings == ()


def test_detect_ignores_markdown_documents(tmp_path: Path):
    """
    [Unit] detectors signatures: verifies detect ignores markdown documents.

    Scenario:
        Given test inputs and fixtures for detect ignores markdown documents
        When test_detect_ignores_markdown_documents executes the target flow
        Then the expected outcome for detect ignores markdown documents is confirmed.

    Boundaries:
        - Focus: detect ignores markdown documents
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect ignores markdown documents
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    bad_py = src_dir / "bad.py"
    bad_py.write_text(
        "def bad(x: int) -> int:\n"
        '    """Bad doc.\n'
        "\n"
        "    :param x: The x.\n"
        "    :param y: Missing y.\n"
        "    :return: Val.\n"
        '    """\n'
        "    return x\n",
        encoding="utf-8",
    )

    unrelated_docs = (models.Document(path="unrelated.md", bytes=100),)
    findings = signatures.detect(tmp_path, unrelated_docs)
    assert len(findings) == 1
    assert findings[0].rule == "DS204"
    assert findings[0].path == "src/bad.py"


def test_detect_respects_docsig_paths(tmp_path: Path):
    """
    [Unit] detectors signatures: verifies detect respects docsig paths.

    Scenario:
        Given test inputs and fixtures for detect respects docsig paths
        When test_detect_respects_docsig_paths executes the target flow
        Then the expected outcome for detect respects docsig paths is confirmed.

    Boundaries:
        - Focus: detect respects docsig paths
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to detect respects docsig paths
        - Fixture or parameter values used by this test
        - Recent changes in code paths exercised by detectors signatures
    """
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir(parents=True)
    bad_lib = lib_dir / "bad.py"
    bad_lib.write_text(
        "def lib_bad(x: int) -> int:\n"
        '    """Lib bad doc.\n'
        "\n"
        "    :param x: The x.\n"
        "    :param extra: Extra param.\n"
        "    :return: Val.\n"
        '    """\n'
        "    return x\n",
        encoding="utf-8",
    )

    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    bad_src = src_dir / "bad_src.py"
    bad_src.write_text(
        "def src_bad(y: int) -> int:\n"
        '    """Src bad doc.\n'
        "\n"
        "    :param y: The y.\n"
        "    :param extra: Extra param.\n"
        "    :return: Val.\n"
        '    """\n'
        "    return y\n",
        encoding="utf-8",
    )

    (tmp_path / "doc_sentinel.toml").write_text(
        'docsig_paths = ["lib"]\n',
        encoding="utf-8",
    )

    findings = signatures.detect(tmp_path, ())
    assert len(findings) == 1
    assert findings[0].path == "lib/bad.py"
