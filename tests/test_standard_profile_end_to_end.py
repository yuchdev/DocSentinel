"""End-to-end tests for the standard profile detectors (DS201-DS204)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("textstat")
pytest.importorskip("sklearn")
pytest.importorskip("docsig")

from docsentinel.cli import main
from docsentinel.config import Config
from docsentinel.detectors.standard import corpus
from docsentinel.engine import scan

_DENSE_TEXT = (
    "The epistemological ramifications of post-structuralist hermeneutics "
    "necessitate a comprehensive re-evaluation of ontologically indeterminate "
    "socio-historical contextualizations within modern institutional paradigms. "
    "Consequently, idiosyncratic methodological approaches deliberately obfuscate "
    "the phenomenological dialectic inherent in multidisciplinary theoretical syntaxes. "
    "Furthermore, the institutionalized hegemony of predetermined conceptual frameworks "
    "systematically perpetuates epistemological disenfranchisement across heterogeneous "
    "linguistic subcultures, thereby precluding equitable academic discourse and "
    "collaborative interdisciplinary synthesis."
)

_CLEAN_TEXT = (
    "The cat sat on the mat. The sun was hot and bright today. "
    "We had fun playing outside in the yard with our friends all day long. "
    "The dog ran after the red ball across the green grass. "
    "We ate lunch and drank cool water under the shade. "
    "It was a good day for everyone in the park. "
    "Tomorrow we will go to the park again."
)


@pytest.fixture
def standard_profile_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    dense_file = tmp_path / "dense.md"
    dense_file.write_text(_DENSE_TEXT, encoding="utf-8")
    clean_file = tmp_path / "clean.md"
    clean_file.write_text(_CLEAN_TEXT, encoding="utf-8")
    return tmp_path, dense_file, clean_file


def test_importing_engine_does_not_register_ds201() -> None:
    code = (
        "import sys\n"
        "import docsentinel.engine\n"
        "from docsentinel.rules import RULES\n"
        "assert 'DS201' not in RULES, 'DS201 registered eagerly on engine import'\n"
        "assert 'DS202' not in RULES, 'DS202 registered eagerly on engine import'\n"
        "assert 'DS203' not in RULES, 'DS203 registered eagerly on engine import'\n"
        "assert 'DS204' not in RULES, 'DS204 registered eagerly on engine import'\n"
        "assert 'DS201' not in docsentinel.engine.ANALYZERS\n"
        "assert 'DS202' not in docsentinel.engine.ANALYZERS\n"
        "assert 'DS203' not in docsentinel.engine.ANALYZERS\n"
        "assert 'DS204' not in docsentinel.engine.ANALYZERS\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_standard_scan_detects_complex_document(
    standard_profile_tree: tuple[Path, Path, Path],
) -> None:
    root, _, _ = standard_profile_tree
    result = scan(root, config=Config(profile="standard"))
    assert tuple((finding.rule, finding.path) for finding in result.findings) == (("DS201", "dense.md"),)
    assert result.enabled_rules == ("DS201", "DS202", "DS203", "DS204")
    assert result.notice == "4 standard rule(s) evaluated."
    assert result.pending == ()


def test_clean_project_standard_scan(tmp_path: Path) -> None:
    clean_file = tmp_path / "clean.md"
    clean_file.write_text(_CLEAN_TEXT, encoding="utf-8")
    result = scan(tmp_path, config=Config(profile="standard"))
    assert result.findings == ()
    assert result.enabled_rules == ("DS201", "DS202", "DS203", "DS204")
    assert result.notice == "4 standard rule(s) evaluated."
    assert "not implemented" not in result.notice
    assert result.pending == ()


def test_ignore_narrows_standard_set(
    standard_profile_tree: tuple[Path, Path, Path],
) -> None:
    root, _, _ = standard_profile_tree
    result = scan(root, config=Config(profile="standard", ignore=("DS2",)))
    assert result.findings == ()
    assert result.enabled_rules == ()
    assert result.pending == ("all standard rules were excluded by select/ignore",)
    assert result.notice == "All standard rules were excluded by select/ignore."


def test_fast_profile_scan_ignores_standard_detectors(
    standard_profile_tree: tuple[Path, Path, Path],
) -> None:
    root, _, _ = standard_profile_tree
    result = scan(root, config=Config(profile="fast"))
    assert result.findings == ()
    assert result.enabled_rules == ("DS101", "DS102", "DS103")
    assert result.notice == "3 fast rule(s) evaluated."
    assert "DS201" not in result.enabled_rules
    assert "DS204" not in result.enabled_rules


def test_standard_scan_exit_code_zero_for_warning_only(
    standard_profile_tree: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, _ = standard_profile_tree
    assert main(["scan", str(root), "--profile", "standard"]) == 0
    captured = capsys.readouterr()
    assert "warning: dense.md: Readability grade level" in captured.out


def test_standard_scan_exit_code_one_under_strict(
    standard_profile_tree: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    root, _, _ = standard_profile_tree
    assert main(["scan", str(root), "--profile", "standard", "--strict"]) == 1
    captured = capsys.readouterr()
    assert "warning: dense.md: Readability grade level" in captured.out


def test_standard_scan_reports_duplicate_and_low_info(tmp_path: Path) -> None:
    text_dup = (
        "We can use this tool to check our notes and find any problems. "
        "It will look through all files in the project to make sure the words are clear "
        "and easy to read for everyone. You can run the test anytime to see the report."
    )
    text_distinct = (
        "There are many birds in the garden that sing songs every morning. "
        "The blue birds fly from tree to tree looking for small seeds to eat. "
        "In the afternoon they rest on the green branches."
    )
    text_filler = (
        "This is because there is and it was as it has been there before. "
        "This is because there is and it was as it has been there before. "
        "This is because there is and it was as it has been there before. "
        "This is because there is and it was as it has been there before."
    )

    (tmp_path / "a.md").write_text(text_dup, encoding="utf-8")
    (tmp_path / "b.md").write_text(text_dup, encoding="utf-8")
    (tmp_path / "c.md").write_text(text_distinct, encoding="utf-8")
    (tmp_path / "filler.md").write_text(text_filler, encoding="utf-8")

    corpus.build_corpus_model.cache_clear()
    result = scan(tmp_path, config=Config(profile="standard"))
    corpus.build_corpus_model.cache_clear()

    findings_summary = tuple((f.rule, f.path) for f in result.findings)
    assert ("DS202", "b.md") in findings_summary
    assert ("DS203", "filler.md") in findings_summary
    assert len(result.findings) == 2
    assert result.enabled_rules == ("DS201", "DS202", "DS203", "DS204")
    assert result.notice == "4 standard rule(s) evaluated."


def test_corpus_model_built_once_per_scan(tmp_path: Path) -> None:
    text_dup = (
        "We can use this tool to check our notes and find any problems. "
        "It will look through all files in the project to make sure the words are clear "
        "and easy to read for everyone. You can run the test anytime to see the report."
    )
    (tmp_path / "a.md").write_text(text_dup, encoding="utf-8")
    (tmp_path / "b.md").write_text(text_dup, encoding="utf-8")

    corpus.build_corpus_model.cache_clear()
    with patch.object(
        corpus.TfidfVectorizer, "fit_transform", autospec=True, side_effect=corpus.TfidfVectorizer.fit_transform
    ) as mock_fit:
        result = scan(tmp_path, config=Config(profile="standard"))
        assert mock_fit.call_count == 1
        assert "DS202" in result.enabled_rules
        assert "DS203" in result.enabled_rules
        assert "DS204" in result.enabled_rules
    corpus.build_corpus_model.cache_clear()


def test_standard_enabled_rules_are_all_four(tmp_path: Path) -> None:
    clean_file = tmp_path / "clean.md"
    clean_file.write_text(_CLEAN_TEXT, encoding="utf-8")
    result = scan(tmp_path, config=Config(profile="standard"))
    assert result.enabled_rules == ("DS201", "DS202", "DS203", "DS204")
    assert result.notice == "4 standard rule(s) evaluated."


def test_select_narrows_to_single_corpus_rule(tmp_path: Path) -> None:
    text_dup = (
        "We can use this tool to check our notes and find any problems. "
        "It will look through all files in the project to make sure the words are clear "
        "and easy to read for everyone. You can run the test anytime to see the report."
    )
    (tmp_path / "a.md").write_text(text_dup, encoding="utf-8")
    (tmp_path / "b.md").write_text(text_dup, encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="standard", select=("DS202",)))
    assert result.enabled_rules == ("DS202",)
    assert result.notice == "1 standard rule(s) evaluated."
    assert "DS201" not in result.enabled_rules
    assert "DS203" not in result.enabled_rules
    assert "DS204" not in result.enabled_rules
    assert len(result.findings) == 1
    assert result.findings[0].rule == "DS202"
    assert result.findings[0].path == "b.md"


def test_standard_scan_reports_signature_finding(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    bad_py = pkg_dir / "bad.py"
    bad_py.write_text(
        "def compute(total: int) -> int:\n"
        '    """Compute result.\n'
        "\n"
        "    :param total: The total.\n"
        "    :param nonexistent: Nonexistent parameter.\n"
        "    :return: The total multiplied by 2.\n"
        '    """\n'
        "    return total * 2\n",
        encoding="utf-8",
    )
    doc = tmp_path / "docs.md"
    doc.write_text(_CLEAN_TEXT, encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="standard"))
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.rule == "DS204"
    assert finding.path == "src/pkg/bad.py"
    assert finding.severity == "error"
    assert "compute: SIG202" in finding.message
    assert result.enabled_rules == ("DS201", "DS202", "DS203", "DS204")
    assert result.notice == "4 standard rule(s) evaluated."


def test_standard_scan_exit_code_one_for_ds204_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pkg_dir = tmp_path / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    bad_py = pkg_dir / "bad.py"
    bad_py.write_text(
        "def compute(total: int) -> int:\n"
        '    """Compute result.\n'
        "\n"
        "    :param total: The total.\n"
        "    :param nonexistent: Nonexistent parameter.\n"
        "    :return: The total multiplied by 2.\n"
        '    """\n'
        "    return total * 2\n",
        encoding="utf-8",
    )
    doc = tmp_path / "docs.md"
    doc.write_text(_CLEAN_TEXT, encoding="utf-8")

    assert main(["scan", str(tmp_path), "--profile", "standard"]) == 1
    captured = capsys.readouterr()
    assert "error: src/pkg/bad.py: compute: SIG202" in captured.out


def test_ds204_coexists_with_corpus_detectors(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    bad_py = pkg_dir / "bad.py"
    bad_py.write_text(
        "def calculate(value: int) -> int:\n"
        '    """Calculate something.\n'
        "\n"
        "    :param value: The value.\n"
        "    :param extra: Extra parameter.\n"
        "    :return: Processed value.\n"
        '    """\n'
        "    return value + 1\n",
        encoding="utf-8",
    )

    text_dup = (
        "We can use this tool to check our notes and find any problems. "
        "It will look through all files in the project to make sure the words are clear "
        "and easy to read for everyone. You can run the test anytime to see the report."
    )
    (tmp_path / "a.md").write_text(text_dup, encoding="utf-8")
    (tmp_path / "b.md").write_text(text_dup, encoding="utf-8")

    corpus.build_corpus_model.cache_clear()
    result = scan(tmp_path, config=Config(profile="standard"))
    corpus.build_corpus_model.cache_clear()

    finding_rules = tuple((f.rule, f.path) for f in result.findings)
    assert ("DS204", "src/pkg/bad.py") in finding_rules
    assert ("DS202", "b.md") in finding_rules
    assert len(result.findings) == 2


def test_select_ds204_only_skips_corpus_build(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "src"
    pkg_dir.mkdir(parents=True)
    bad_py = pkg_dir / "bad.py"
    bad_py.write_text(
        "def calculate(value: int) -> int:\n"
        '    """Calculate something.\n'
        "\n"
        "    :param value: The value.\n"
        "    :param extra: Extra parameter.\n"
        "    :return: Processed value.\n"
        '    """\n'
        "    return value + 1\n",
        encoding="utf-8",
    )

    text_dup = (
        "We can use this tool to check our notes and find any problems. "
        "It will look through all files in the project to make sure the words are clear "
        "and easy to read for everyone. You can run the test anytime to see the report."
    )
    (tmp_path / "a.md").write_text(text_dup, encoding="utf-8")
    (tmp_path / "b.md").write_text(text_dup, encoding="utf-8")

    corpus.build_corpus_model.cache_clear()
    with patch.object(
        corpus.TfidfVectorizer,
        "fit_transform",
        autospec=True,
        side_effect=corpus.TfidfVectorizer.fit_transform,
    ) as mock_fit:
        result = scan(tmp_path, config=Config(profile="standard", select=("DS204",)))
        assert mock_fit.call_count == 0

    corpus.build_corpus_model.cache_clear()
    assert result.enabled_rules == ("DS204",)
    assert result.notice == "1 standard rule(s) evaluated."
    assert "DS202" not in result.enabled_rules
    assert "DS203" not in result.enabled_rules
    assert len(result.findings) == 1
    assert result.findings[0].rule == "DS204"
    assert result.findings[0].path == "src/bad.py"


def test_clean_project_standard_scan_is_zero_findings_evaluated(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    clean_py = src_dir / "math.py"
    clean_py.write_text(
        "def add(a: int, b: int) -> int:\n"
        '    """Add two numbers.\n'
        "\n"
        "    :param a: The first number.\n"
        "    :param b: The second number.\n"
        "    :return: Sum of both numbers.\n"
        '    """\n'
        "    return a + b\n",
        encoding="utf-8",
    )
    clean_md = tmp_path / "clean.md"
    clean_md.write_text(_CLEAN_TEXT, encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="standard"))
    assert result.findings == ()
    assert result.enabled_rules == ("DS201", "DS202", "DS203", "DS204")
    assert result.notice == "4 standard rule(s) evaluated."
    assert result.pending == ()
