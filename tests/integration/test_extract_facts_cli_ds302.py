"""``docsentinel extract-facts`` end to end over a real corpus (Milestone 0010 Story 05.0 Task 04, step 8).

Loads ``tests/assets/ds302/extract_facts_basic/`` (two synthetic documents: numeric and
named-entity claims, a near-duplicate pair across the files and one trivial sentence) and runs the
command through ``cli.main`` with the real spaCy pipeline, salience, clustering and packaged
templates. Covers every Task 03 acceptance criterion and the threat model 0010-extract-facts
mitigations E1 (a fresh-interpreter socket guard and backend-module absence), E2 (the ``doctor``
template lines), E7 (type-name-only extraction error), E8 (``--all`` over a generated corpus and the
render cap), E10 (no file after a render failure; selector refusals as for ``scan``) and E13 (no
claim text in stderr, the log file or a record, also with ``-v``).

No network is reached, no backend is registered or imported, and the only key value is the threat
model 0010 M12 sentinel. Skipped when ``mining.nlp.deep_ready()`` is false, like the DS301
integration tests.
"""

import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli, extract_facts
from docsentinel.engine import EMPTY_SELECTION_MESSAGE
from docsentinel.log import LOG_DIR_ENV
from docsentinel.mining import nlp
from docsentinel.mining.claims import Claim
from docsentinel.reporting import render_facts
from docsentinel.telemetry import engine as template_engine
from tests.asset_helpers import AssetCase
from tests.log_helpers import problem_output

pytestmark = pytest.mark.skipif(not nlp.deep_ready(), reason="deep dependencies and model not installed")

#: The fake key value (threat model 0010 M12); it resembles no real provider key.
SENTINEL_KEY = "sentinel-not-a-real-key-0010"

#: A claim sentence of the asset case that DS302 would send; it may reach stdout or ``-o`` only.
SENTINEL_SENTENCE = "The northern dome houses 3 telescopes and 18 spectrographs."

#: The near-duplicate pair of the asset case.
NEAR_DUPLICATES = (
    "The Quillan Space Agency granted 7 million credits to the eastern wing in 2029.",
    "The Quillan Space Agency granted 7 million credits to the eastern wing in 2029 overall.",
)

#: The trivial sentence of the asset case.
TRIVIAL = "The staff likes the view."

#: The top-level keys of a ``facts-json`` document, in template order.
FACTS_JSON_KEYS = [
    "schema",
    "schema_version",
    "notice",
    "matches_ds302",
    "include_rejected",
    "settings",
    "summary",
    "facts",
]

#: The ``facts-text`` DS302 match lines.
MATCH_YES = "Matches the DS302 selection for this configuration: yes"
MATCH_NO = "Matches the DS302 selection for this configuration: no"

#: Runs ``cli.main(["extract-facts", <root>, ...])`` in a fresh interpreter behind a socket guard.
_SOCKET_GUARD_PROBE = """
import json
import socket
import sys

calls = []


def _guard(name):
    def blocked(*args, **kwargs):
        calls.append(name)
        raise OSError("network blocked by the extract-facts socket guard: " + name)
    return blocked


socket.socket.connect = _guard("socket.socket.connect")
socket.create_connection = _guard("socket.create_connection")
socket.getaddrinfo = _guard("socket.getaddrinfo")

from docsentinel import cli

code = cli.main(["extract-facts", sys.argv[1], "--format", "facts-json", "-o", sys.argv[2]])

from docsentinel.fact_check.protocol import FACT_CHECK_BACKEND_MODULES

modules = sorted({"docsentinel.fact_check.lenz", *FACT_CHECK_BACKEND_MODULES.values()})
print(json.dumps({"code": code, "calls": calls, "loaded": {name: name in sys.modules for name in modules}}))
"""


@pytest.fixture
def root(asset_case: Callable[[str, str], AssetCase]) -> Path:
    """Materialize the extract_facts_basic case.

    :param asset_case: The asset loader fixture.
    :returns: The scan root.
    """
    return asset_case("ds302", "extract_facts_basic").root


@pytest.fixture
def log_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the per-run log file at a directory outside the scan root.

    :param tmp_path_factory: Pytest temporary directory factory.
    :param monkeypatch: Pytest monkeypatch.
    :returns: The log directory.
    """
    directory = tmp_path_factory.mktemp("extract-facts-logs")
    monkeypatch.setenv(LOG_DIR_ENV, str(directory))
    return directory


def _log_text(directory: Path) -> str:
    """Return the text of every per-run log file in ``directory``.

    :param directory: The log directory.
    :returns: The joined contents.
    """
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(directory.glob("docsentinel-*.log")))


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    """Run ``cli.main`` and capture its output.

    :param capsys: Pytest capture fixture.
    :param argv: The command line.
    :returns: ``(exit code, stdout, stderr)``.
    """
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_default_text_output_exits_zero_and_equals_the_library_rendering(
    root: Path, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] extract-facts CLI: verifies the default facts-text output, exit 0 and a clean stdout.

    Scenario:
        Given the extract_facts_basic corpus
        When docsentinel extract-facts runs with no option
        Then it exits 0, stdout is exactly render_facts(extract_facts(root)) plus a newline, both documents
            are listed with the summary, match and notice lines, and stderr holds no problem line

    Boundaries:
        - Focus: Task 03 acceptance 1 (default facts-text, clean stdout)
        - Fixtures/params: real spaCy pipeline
        - Scope: cli.main extract-facts

    On failure, first check:
        - DEFAULT_FACTS_TEMPLATE and the print of the rendered output
    """
    code, out, err = _run(capsys, "extract-facts", str(root))

    assert code == 0
    assert out == render_facts(extract_facts(root)) + "\n"
    lines = out.splitlines()
    assert [line for line in lines if not line.startswith(" ")][:2] == ["archive.md", "observatory.md"]
    assert "Facts: 4 selected, 4 listed, from 6 claims in 2 document(s) (0 unreadable skipped)" in lines
    assert lines[-2] == MATCH_YES
    assert lines[-1].startswith("Heuristic, offline claim extraction; no network call was made")
    assert TRIVIAL not in out
    assert problem_output(err) == ""


def test_zero_facts_still_exit_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies a corpus with no salient claim exits 0 with zero facts.

    Scenario:
        Given one document holding only a trivial sentence
        When extract-facts runs with facts-text and with facts-json
        Then both exit 0, the text summary says 0 selected and the JSON facts list is empty

    Boundaries:
        - Focus: Task 03 acceptance 1, decision X12 (zero facts is success, never exit 1)
        - Fixtures/params: inline document generated in the test
        - Scope: cli.main extract-facts

    On failure, first check:
        - Whether an empty selection is treated as an error
    """
    (tmp_path / "plain.md").write_text("# Plain\n\n" + TRIVIAL + "\n", encoding="utf-8")

    text_code, text_out, _ = _run(capsys, "extract-facts", str(tmp_path))
    json_code, json_out, _ = _run(capsys, "extract-facts", str(tmp_path), "--format", "facts-json")

    assert (text_code, json_code) == (0, 0)
    assert "Facts: 0 selected, 0 listed, from 1 claims in 1 document(s) (0 unreadable skipped)" in text_out
    assert json.loads(json_out)["facts"] == []


def test_facts_json_output_file_shape_ascii_and_near_duplicate_cluster(
    root: Path, tmp_path_factory: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] extract-facts CLI: verifies -o facts-json is valid ASCII JSON with the documented keys and one near-duplicate fact.

    Scenario:
        Given the extract_facts_basic corpus
        When extract-facts --format facts-json -o out.json runs
        Then it exits 0 with nothing on stdout, logs "report written to", and the file parses with the
            top-level keys in order, is pure ASCII, has matches_ds302 true, and lists exactly one member
            of the near-duplicate pair with cluster.size 2

    Boundaries:
        - Focus: Task 03 acceptance 2, Task 04 step 8 (facts-json checks)
        - Fixtures/params: real spaCy pipeline; output outside the scan root
        - Scope: cli.main extract-facts, facts-json template

    On failure, first check:
        - _write_report and the facts-json template body
    """
    out_file = tmp_path_factory.mktemp("facts-out") / "nested" / "out.json"

    code, out, err = _run(capsys, "extract-facts", str(root), "--format", "facts-json", "-o", str(out_file))

    raw = out_file.read_bytes()
    document = json.loads(raw)
    assert code == 0
    assert out == ""
    assert f"report written to {out_file} (facts-json, " in err
    assert list(document) == FACTS_JSON_KEYS
    assert all(byte < 0x80 for byte in raw)
    assert document["schema"] == "docsentinel-facts"
    assert document["matches_ds302"] is True
    assert document["summary"] == {
        "documents": 2,
        "unreadable": 0,
        "claims_extracted": 6,
        "facts_selected": 4,
        "facts_listed": 4,
    }
    pair = [fact for fact in document["facts"] if fact["text"] in NEAR_DUPLICATES]
    assert len(pair) == 1
    assert pair[0]["cluster"]["size"] == 2
    assert [fact["rank"] for fact in document["facts"]] == [1, 2, 3, 4]
    assert {fact["disposition"] for fact in document["facts"]} == {"selected"}


def test_all_lists_the_trivial_sentence_as_below_floor(root: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies --all lists every claim, the trivial one as below_floor and the pair member as duplicate.

    Scenario:
        Given the extract_facts_basic corpus
        When extract-facts --all --format facts-json runs
        Then all six claims are listed, the trivial sentence is below_floor, the other pair member is
            duplicate, the selected set is unchanged and matches_ds302 stays true

    Boundaries:
        - Focus: decision X7, Task 04 step 8 (--all)
        - Fixtures/params: real spaCy pipeline
        - Scope: cli.main extract-facts

    On failure, first check:
        - The --all flag wiring to include_rejected
    """
    code, out, _ = _run(capsys, "extract-facts", str(root), "--all", "--format", "facts-json")

    document = json.loads(out)
    dispositions = {fact["text"]: fact["disposition"] for fact in document["facts"]}
    assert code == 0
    assert document["include_rejected"] is True
    assert document["matches_ds302"] is True
    assert len(document["facts"]) == document["summary"]["facts_listed"] == 6
    assert dispositions[TRIVIAL] == "below_floor"
    assert sorted(dispositions[text] for text in NEAR_DUPLICATES) == ["duplicate", "selected"]
    assert list(dispositions.values()).count("selected") == document["summary"]["facts_selected"] == 4


def test_overrides_change_the_settings_and_clear_the_match(root: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies each override changes run.settings and the notice names it.

    Scenario:
        Given the extract_facts_basic corpus
        When extract-facts --min-salience 0.6 --max-per-document 1 --max-total 2 --format facts-json runs
        Then the settings hold those values, at most 2 facts with one per document are listed,
            matches_ds302 is false and the notice names the three settings

    Boundaries:
        - Focus: Task 03 acceptance 4, decision X6
        - Fixtures/params: real spaCy pipeline
        - Scope: cli.main extract-facts

    On failure, first check:
        - cli._fact_overrides
    """
    code, out, _ = _run(
        capsys,
        "extract-facts",
        str(root),
        "--min-salience",
        "0.6",
        "--max-per-document",
        "1",
        "--max-total",
        "2",
        "--format",
        "facts-json",
    )

    document = json.loads(out)
    assert code == 0
    assert (
        document["settings"]["min_salience"],
        document["settings"]["max_per_document"],
        document["settings"]["max_total"],
    ) == (0.6, 1, 2)
    assert len(document["facts"]) == 2
    assert len({fact["path"] for fact in document["facts"]}) == 2
    assert document["matches_ds302"] is False
    assert document["notice"].endswith(
        "Settings differ from DS302 (min_salience, max_per_document, max_total); DS302 would send a different set."
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--max-total", "0"), "fact_check_max_claims_total must be an integer from 1 to 500"),
        (("--max-total", "501"), "fact_check_max_claims_total must be an integer from 1 to 500"),
        (("--max-per-document", "0"), "fact_check_max_claims_per_document must be an integer from 1 to 50"),
        (("--min-salience", "1.5"), "fact_check_min_salience must be a number between 0 and 1"),
        (("--min-salience", "nan"), "fact_check_min_salience must be a number between 0 and 1"),
        (("--weights", "0.5,0.5,0.5"), "salience weights must sum to 1.0"),
        (("--dedup-threshold", "0"), "dedup_threshold must be a finite number in (0, 1]"),
        (("--dedup-threshold", "inf"), "dedup_threshold must be a finite number in (0, 1]"),
        (("--format", "json"), "template json is a report template"),
        (("--include", "zzz*.md"), EMPTY_SELECTION_MESSAGE),
    ],
    ids=[
        "max-total-0",
        "max-total-501",
        "max-per-document-0",
        "min-salience-1.5",
        "min-salience-nan",
        "weights-sum",
        "threshold-0",
        "threshold-inf",
        "report-template",
        "empty-selection",
    ],
)
def test_invalid_values_exit_two_with_the_validator_message(
    root: Path, capsys: pytest.CaptureFixture[str], args: tuple[str, ...], message: str
):
    """
    [Integration] extract-facts CLI: verifies every invalid value exits 2 with the exact validator message.

    Scenario:
        Given one out-of-range override, exploration value, report template or empty selection
        When extract-facts runs
        Then it exits 2 (never 1), stdout is empty and stderr holds "Extraction failed: <message>"

    Boundaries:
        - Focus: Task 03 acceptance 3-5 and 7, decision X12
        - Fixtures/params: one invalid input per case
        - Scope: cli.main extract-facts

    On failure, first check:
        - The except clause of cli._cmd_extract_facts and the shared validators
    """
    code, out, err = _run(capsys, "extract-facts", str(root), *args)

    assert code == 2
    assert out == ""
    assert f"Extraction failed: {message}" in err


def test_exploration_weights_exit_zero_and_say_they_do_not_match(root: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies --weights 0.2,0.2,0.6 exits 0 and the output says it does not match DS302.

    Scenario:
        Given the extract_facts_basic corpus
        When extract-facts --weights 0.2,0.2,0.6 runs (text, then JSON)
        Then both exit 0, the text has the "no" match line and the JSON settings hold the weights

    Boundaries:
        - Focus: Task 03 acceptance 5, decision X5
        - Fixtures/params: real spaCy pipeline
        - Scope: cli.main extract-facts

    On failure, first check:
        - _weights_argument and the matches_ds302 computation
    """
    text_code, text_out, _ = _run(capsys, "extract-facts", str(root), "--weights", "0.2,0.2,0.6")
    json_code, json_out, _ = _run(
        capsys, "extract-facts", str(root), "--weights", "0.2,0.2,0.6", "--format", "facts-json"
    )

    document = json.loads(json_out)
    assert (text_code, json_code) == (0, 0)
    assert MATCH_NO in text_out.splitlines()
    assert MATCH_YES not in text_out
    assert document["settings"]["weights"] == {"numeric": 0.2, "entity": 0.2, "distinctiveness": 0.6}
    assert document["notice"].endswith("Settings differ from DS302 (weights); DS302 would send a different set.")


@pytest.mark.parametrize(
    "flag",
    [
        ("--use-external-api",),
        ("--profile", "deep"),
        ("--select", "DS302"),
        ("--extension", "builtin:domain"),
        ("--weights", "1,2"),
    ],
    ids=["use-external-api", "profile", "select", "extension", "weights-shape"],
)
def test_scan_only_flags_are_argparse_errors(root: Path, capsys: pytest.CaptureFixture[str], flag: tuple[str, ...]):
    """
    [Integration] extract-facts CLI: verifies scan-only flags and a malformed --weights are argparse errors (exit 2).

    Scenario:
        Given a flag extract-facts deliberately does not define, or three numbers missing from --weights
        When cli.main parses the command line
        Then SystemExit carries code 2 and stdout is empty

    Boundaries:
        - Focus: Task 03 acceptance 6, story acceptance (--use-external-api is an argparse error)
        - Fixtures/params: one flag per case
        - Scope: cli argument parsing

    On failure, first check:
        - _add_extract_facts_parser
    """
    with pytest.raises(SystemExit) as caught:
        cli.main(["extract-facts", str(root), *flag])

    captured = capsys.readouterr()
    assert caught.value.code == 2
    assert captured.out == ""
    assert "error:" in captured.err


def test_unreadable_document_is_skipped_counted_and_exit_zero(root: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies a non-UTF-8 document is skipped with the shared WARNING and counted.

    Scenario:
        Given the corpus plus one document of invalid UTF-8 bytes
        When extract-facts --format facts-json runs
        Then it exits 0, stderr holds the skip WARNING once, and the summary counts 3 documents, 1 unreadable

    Boundaries:
        - Focus: Task 03 acceptance 7, decision X12
        - Fixtures/params: invalid bytes generated in the test
        - Scope: cli.main extract-facts

    On failure, first check:
        - engine._partition_readable through engine._inventory
    """
    (root / "broken.md").write_bytes(b"# Broken\n\n\xff\xfe not utf-8\n")

    code, out, err = _run(capsys, "extract-facts", str(root), "--format", "facts-json")

    summary = json.loads(out)["summary"]
    assert code == 0
    assert err.count("skipped broken.md: not valid UTF-8") == 1
    assert (summary["documents"], summary["unreadable"], summary["facts_selected"]) == (3, 1, 4)


def test_single_file_target_reads_only_that_file(root: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies a single-file target lists only its facts and ignores selectors with a WARNING.

    Scenario:
        Given observatory.md as the target and an --exclude naming it
        When extract-facts --format facts-json runs
        Then it exits 0, every fact comes from observatory.md, one document is counted and stderr holds the
            selector WARNING

    Boundaries:
        - Focus: decision X4 (shared inventory, single-file target)
        - Fixtures/params: real spaCy pipeline
        - Scope: cli.main extract-facts

    On failure, first check:
        - The selected_file branch of engine._inventory
    """
    code, out, err = _run(
        capsys, "extract-facts", str(root / "observatory.md"), "--exclude", "observatory.md", "--format", "facts-json"
    )

    document = json.loads(out)
    assert code == 0
    assert document["summary"]["documents"] == 1
    assert document["facts"]
    assert {fact["path"] for fact in document["facts"]} == {"observatory.md"}
    assert "--include/--exclude ignored for a single-file scan target" in err


@pytest.mark.parametrize("flags", [(), ("-v",)], ids=["info", "debug"])
def test_claim_text_reaches_stdout_only(
    root: Path,
    log_dir: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    flags: tuple[str, ...],
):
    """
    [Integration] extract-facts CLI: verifies a claim sentence reaches stdout but never stderr, the log file or a record (E13).

    Scenario:
        Given the corpus, whose selected claims include a sentinel sentence
        When extract-facts runs at INFO and with -v (DEBUG, including the trace_salience stage counts)
        Then it exits 0, stdout holds the sentence, the config: INFO line is present, the DEBUG salience
            counts appear with -v, and the sentence is in neither stderr, the per-run log file nor any record

    Boundaries:
        - Focus: threat model 0010-extract-facts E13, Task 03 acceptance 9
        - Fixtures/params: real spaCy pipeline; -v on/off
        - Scope: cli.main extract-facts logging

    On failure, first check:
        - Any new log call formatting a claim, a candidate or a sentence
    """
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    code, out, err = _run(capsys, *flags, "extract-facts", str(root))

    log_text = _log_text(log_dir)
    assert code == 0
    assert SENTINEL_SENTENCE in out
    assert "docsentinel: config: user settings off, project none" in err
    assert "extract-facts finished in " in log_text
    assert ("salience: " in err) is bool(flags)
    assert "salience: 6 claim(s) in, 5 cluster(s)" in log_text
    for text in (err, log_text, "\n".join(record.getMessage() for record in caplog.records)):
        assert SENTINEL_SENTENCE not in text
        assert NEAR_DUPLICATES[0] not in text


def test_extraction_error_prints_the_type_name_only(
    root: Path,
    log_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
):
    """
    [Integration] extract-facts CLI: verifies an extraction exception carrying claim text exits 2 with the fixed text (E7).

    Scenario:
        Given the real pipeline and extract_statements patched to raise ValueError(<sentinel sentence>)
        When extract-facts -v runs
        Then it exits 2, stderr holds the fixed type-name message, and no stream, log file or record holds
            the sentence or a traceback

    Boundaries:
        - Focus: threat model E7, E13
        - Fixtures/params: patched extract_statements only
        - Scope: cli.main extract-facts error path

    On failure, first check:
        - engine._traced and the RuntimeError branch of cli._cmd_extract_facts
    """

    def _boom(pipeline: object, text: str, path: str) -> tuple[Claim, ...]:
        """Raise an error whose message is document text.

        :param pipeline: Ignored.
        :param text: Ignored.
        :param path: Ignored.
        :raises ValueError: Always.
        """
        raise ValueError(SENTINEL_SENTENCE)

    monkeypatch.setattr("docsentinel.mining.claims.extract_statements", _boom)
    caplog.set_level(logging.DEBUG, logger="docsentinel")

    code, out, err = _run(capsys, "-v", "extract-facts", str(root))

    log_text = _log_text(log_dir)
    assert code == 2
    assert "Extraction failed: extract-facts: claim extraction failed (ValueError)\n" in err
    for text in (out, err, log_text, "\n".join(record.getMessage() for record in caplog.records)):
        assert SENTINEL_SENTENCE not in text
        assert "Traceback" not in text
    assert all(record.exc_info is None for record in caplog.records)


def test_all_over_a_generated_corpus_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """
    [Integration] extract-facts CLI: verifies --all over a generated corpus lists more than the total cap and exits 0 (E8).

    Scenario:
        Given 20 generated documents of five numeric claim sentences each
        When extract-facts --all --format facts-json runs
        Then it exits 0, lists every extracted claim (more than the 25-claim total cap), selects at most 25,
            and every listed numbers/entities list is within the 32-item, 200-code-point caps

    Boundaries:
        - Focus: threat model E8 (volume), decision X7
        - Fixtures/params: corpus generated in the test, real spaCy pipeline
        - Scope: cli.main extract-facts

    On failure, first check:
        - The render caps and engine._bounded
    """
    for doc in range(20):
        sentences = [f"Station S{doc}x{k} logged {100 * doc + k} readings in sector {k + 1}." for k in range(5)]
        (tmp_path / f"station{doc:02d}.md").write_text(
            f"# Station {doc}\n\n" + "\n\n".join(sentences) + "\n", encoding="utf-8"
        )

    code, out, _ = _run(capsys, "extract-facts", str(tmp_path), "--all", "--format", "facts-json")

    document = json.loads(out)
    assert code == 0
    assert document["summary"]["facts_listed"] == len(document["facts"]) > 25
    assert document["summary"]["facts_selected"] <= 25
    for fact in document["facts"]:
        for values in (fact["numbers"], fact["entities"]):
            assert len(values) <= 32
            assert all(len(value) <= 200 for value in values)


@pytest.mark.parametrize("output_format", ["facts-text", "facts-json"])
def test_render_cap_overflow_with_output_leaves_no_file(
    root: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
):
    """
    [Integration] extract-facts CLI: verifies a render-cap overflow with -o exits 2 and writes no file (E8, E10).

    Scenario:
        Given MAX_OUTPUT_CHARS lowered to 200 characters
        When extract-facts --all -o out runs with either packaged facts template
        Then it exits 2 with the rendering-stopped message and the output file does not exist

    Boundaries:
        - Focus: threat model E8/E10 (render first, then write; never truncate)
        - Fixtures/params: patched render cap; both packaged templates
        - Scope: cli.main extract-facts, telemetry.engine caps

    On failure, first check:
        - That _write_report runs only after render_facts returned
    """
    monkeypatch.setattr(template_engine, "MAX_OUTPUT_CHARS", 200)
    target = tmp_path_factory.mktemp("cap-out") / "out.txt"

    code, out, err = _run(capsys, "extract-facts", str(root), "--all", "--format", output_format, "-o", str(target))

    assert code == 2
    assert out == ""
    assert "Extraction failed: rendering stopped: output larger than 200 characters" in err
    assert not target.exists()


@pytest.mark.parametrize(
    "selector",
    [("--include", "../x"), ("--include", "##[x"), ("--exclude", ".")],
    ids=["parent-step", "workflow-marker", "exclude-root"],
)
def test_selector_refusals_match_scan(root: Path, capsys: pytest.CaptureFixture[str], selector: tuple[str, str]):
    """
    [Integration] extract-facts CLI: verifies refused selector values exit 2 with the same message as scan (E10).

    Scenario:
        Given a parent-step include, a "##[" include and "--exclude ."
        When extract-facts and then scan run with that value
        Then both exit 2 and the text after "Extraction failed: " equals the text after "Scan failed: ",
            with "##[" neutralized

    Boundaries:
        - Focus: threat model E10, ADR 0006 selector shape checks
        - Fixtures/params: one refused value per case
        - Scope: cli.main extract-facts and scan

    On failure, first check:
        - cli._validate_selectors and check_invoker_selector_shape
    """
    facts_code, _, facts_err = _run(capsys, "extract-facts", str(root), *selector)
    scan_code, _, scan_err = _run(capsys, "scan", str(root), *selector)

    facts_line = next(line for line in facts_err.splitlines() if line.startswith("Extraction failed: "))
    scan_line = next(line for line in scan_err.splitlines() if line.startswith("Scan failed: "))
    assert (facts_code, scan_code) == (2, 2)
    assert facts_line.removeprefix("Extraction failed: ") == scan_line.removeprefix("Scan failed: ")
    assert "##[" not in facts_err


def test_doctor_lists_the_template_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] doctor: verifies the packaged report/facts lines and one name-only report_templates_dir line (E2).

    Scenario:
        Given a project whose report_templates_dir holds a valid facts template and a malformed file
        When docsentinel doctor runs in that directory
        Then the packaged lines list both contexts, and exactly one templates (report_templates_dir): line
            lists both names without opening them

    Boundaries:
        - Focus: threat model E2, Task 03 acceptance 10
        - Fixtures/params: inline project and templates
        - Scope: cli.main doctor

    On failure, first check:
        - cli._doctor_template_lines
    """
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "broken.json").write_text("{not json", encoding="utf-8")
    (templates / "mine.json").write_text("{}", encoding="utf-8")
    (tmp_path / "docsentinel.toml").write_text('report_templates_dir = "templates"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code, out, _ = _run(capsys, "doctor")

    lines = out.splitlines()
    assert code == 0
    assert "report templates (packaged): github, json, json-documents, json-v1, text" in lines
    assert "fact templates (packaged): facts-json, facts-text" in lines
    assert [line for line in lines if line.startswith("templates (report_templates_dir):")] == [
        "templates (report_templates_dir): broken, mine (context checked at load)"
    ]


def test_gate_environment_changes_nothing_and_never_leaks(
    root: Path, log_dir: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    """
    [Integration] extract-facts CLI: verifies DOCSENTINEL_USE_EXTERNAL_API=1 and a sentinel key give byte-identical output.

    Scenario:
        Given one run with a clean environment
        When extract-facts --format facts-json runs again with DOCSENTINEL_USE_EXTERNAL_API=1 and a sentinel
            DOCSENTINEL_FACTCHECK_LENZ_API_KEY
        Then both exit 0, stdout is byte-identical and the sentinel key is in no stream or log file

    Boundaries:
        - Focus: story decision X10, gating M8 (no consent or key read on this path)
        - Fixtures/params: real spaCy pipeline; sentinel key only
        - Scope: cli.main extract-facts

    On failure, first check:
        - Any environment read added to the extract-facts path
    """
    plain_code, plain_out, _ = _run(capsys, "extract-facts", str(root), "--format", "facts-json")
    monkeypatch.setenv("DOCSENTINEL_USE_EXTERNAL_API", "1")
    monkeypatch.setenv("DOCSENTINEL_FACTCHECK_LENZ_API_KEY", SENTINEL_KEY)

    gated_code, gated_out, gated_err = _run(capsys, "extract-facts", str(root), "--format", "facts-json")

    assert (plain_code, gated_code) == (0, 0)
    assert gated_out == plain_out
    for text in (gated_out, gated_err, _log_text(log_dir)):
        assert SENTINEL_KEY not in text
    assert "docsentinel.fact_check.lenz" not in sys.modules


def test_fresh_interpreter_opens_no_socket_and_imports_no_backend(root: Path, tmp_path_factory: pytest.TempPathFactory):
    """
    [Integration] extract-facts CLI: verifies, behind a socket guard in a fresh interpreter, no socket call and no backend import (E1).

    Scenario:
        Given a python -I subprocess that patches socket.socket.connect, socket.create_connection and
            socket.getaddrinfo to record and raise, with the consent variable and a sentinel key set
        When it calls cli.main(["extract-facts", <asset>, "--format", "facts-json", "-o", <file>])
        Then the exit code is 0, no socket call was recorded, docsentinel.fact_check.lenz and every
            FACT_CHECK_BACKEND_MODULES value are absent from sys.modules, and the file holds the facts

    Boundaries:
        - Focus: threat model 0010-extract-facts E1 (replaces the impossible httpx-absence assertion)
        - Fixtures/params: subprocess with a minimal explicit environment; no sys.modules manipulation
        - Scope: the whole extract-facts command

    On failure, first check:
        - A new network call (for example a spaCy model download) or a backend import on the path
    """
    work = tmp_path_factory.mktemp("socket-guard")
    (work / "home").mkdir()
    (work / "logs").mkdir()
    out_file = work / "facts.json"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(work / "home"),
        "DOCSENTINEL_SETTINGS": "off",
        LOG_DIR_ENV: str(work / "logs"),
        "DOCSENTINEL_USE_EXTERNAL_API": "1",
        "DOCSENTINEL_FACTCHECK_LENZ_API_KEY": SENTINEL_KEY,
    }

    completed = subprocess.run(
        [sys.executable, "-I", "-c", _SOCKET_GUARD_PROBE, str(root), str(out_file)],
        capture_output=True,
        text=True,
        env=env,
        cwd=work,
        timeout=600,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr[-2000:]
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report["code"] == 0
    assert report["calls"] == []
    assert "docsentinel.fact_check.lenz" in report["loaded"]
    assert not any(report["loaded"].values()), report["loaded"]
    facts = json.loads(out_file.read_text(encoding="utf-8"))["facts"]
    assert len(facts) == 4
    assert SENTINEL_KEY not in completed.stderr
