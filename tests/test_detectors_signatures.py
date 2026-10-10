"""Tests for DS204 docstring/signature mismatch detector."""

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("docsig")

import docsentinel.detectors.standard as std_pkg
from docsentinel import engine, models
from docsentinel.detectors.standard import signatures

if "signatures" not in getattr(std_pkg, "__all__", []):
    from docsentinel.rules import RULES

    RULES.pop("DS204", None)
    engine.ANALYZERS.pop("DS204", None)


@pytest.fixture(autouse=True)
def _ensure_ds204_registered() -> Iterator[None]:
    from docsentinel.rules import RULES

    RULES["DS204"] = signatures.DS204
    engine.ANALYZERS["DS204"] = signatures.detect
    yield
    if "signatures" not in getattr(std_pkg, "__all__", []):
        RULES.pop("DS204", None)
        engine.ANALYZERS.pop("DS204", None)


def test_rule_metadata() -> None:
    assert signatures.DS204.code == "DS204"
    assert signatures.DS204.profile == "standard"
    assert signatures.DS204.title == "Docstring/signature mismatch"
    assert signatures.DS204.severity == "error"
    assert (
        signatures.DS204.description
        == "A function docstring's documented parameters or returns do not match its signature."
    )
    assert engine.ANALYZERS["DS204"] == signatures.detect


def test_parse_docsig_output_single_violation() -> None:
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


def test_parse_docsig_output_multiple_violations_one_function() -> None:
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


def test_parse_docsig_output_unknown_sig_code_raises() -> None:
    canned_output = "src/calc.py:10 in calculate\n    SIG999: some brand new future violation format (unknown-code)\n"
    with pytest.raises(ValueError, match="Unrecognized docsig code: SIG999"):
        signatures._parse_docsig_output(canned_output, file="src/calc.py")


def test_parse_docsig_output_clean_is_empty() -> None:
    assert signatures._parse_docsig_output("", file="src/calc.py") == ()
    assert signatures._parse_docsig_output("   \n\n  ", file="src/calc.py") == ()


def test_check_file_flags_param_that_does_not_exist(tmp_path: Path) -> None:
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


def test_check_file_flags_undocumented_param(tmp_path: Path) -> None:
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


def test_well_documented_function_is_clean(tmp_path: Path) -> None:
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


def test_detect_ignores_markdown_documents(tmp_path: Path) -> None:
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


def test_detect_respects_docsig_paths(tmp_path: Path) -> None:
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
