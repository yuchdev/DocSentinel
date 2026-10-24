"""Unit tests for DS117 malformed pipe-table recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition entry point directly with ``check_text(text, path, config)``.
Detection over committed Markdown assets is the job of the Story 08.0 Task 03
integration suite, which runs ``DS117`` registered together with its
``tests/assets/ds117/*`` fixtures (Task 02). This module exercises the detector in
isolation and confirms it is registered and wired as an always-active fast rule.
"""

from pathlib import Path

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import tables


def _lines(findings: tuple[models.Finding, ...]) -> list[int]:
    """Return the one-based line of each finding in order."""
    return [finding.line for finding in findings]


def _codes(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the rule code of each finding in order."""
    return [finding.rule for finding in findings]


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors tables: verifies DS117 metadata and its registration.

    Scenario:
        Given the DS117 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered and wired as an
            always-active (no opt-in option) fast rule.

    Boundaries:
        - Focus: rule metadata and the registered, always-active state
        - Fixtures/params: none

    On failure, first check:
        - Whether a metadata field (profile, severity, title) drifted
        - Whether the register_rule / ANALYZERS wiring was removed
    """
    assert tables.DS117.code == "DS117"
    assert tables.DS117.profile == "fast"
    assert tables.DS117.severity == "warning"
    assert tables.DS117.title == "Malformed GFM pipe-table structure"
    assert tables.DS117.opt_in_option == ""
    assert rules.RULES["DS117"] is tables.DS117
    assert rules.ANALYZERS["DS117"] is tables.detect


def test_valid_two_column_table_is_clean():
    """
    [Unit] detectors tables: verifies a consistent two-column table yields nothing.

    Scenario:
        Given a header, delimiter, and body row that each carry two cells
        When DS117 recognition runs over the table
        Then no finding is produced.

    Boundaries:
        - Focus: a well-formed table recognized without false positives
        - Fixtures/params: default Config

    On failure, first check:
        - The header-count-as-authority comparison in check_text
        - Whether the delimiter row was misread as malformed
    """
    text = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    assert tables.check_text(text, "README.md") == ()


def test_aligned_three_column_table_is_clean():
    """
    [Unit] detectors tables: verifies left/center/right alignment markers are valid.

    Scenario:
        Given a three-column table whose delimiter uses ``:--``/``:-:``/``--:``
        When DS117 recognition runs over the table
        Then no finding is produced because every marker is in the supported subset.

    Boundaries:
        - Focus: valid alignment markers (left, center, right)
        - Fixtures/params: default Config

    On failure, first check:
        - The _VALID_MARKER_RE pattern for colon placement
        - Whether a consistent three-cell count tripped a count check
    """
    text = "| L | C | R |\n| :-- | :-: | --: |\n| 1 | 2 | 3 |\n"
    assert tables.check_text(text, "README.md") == ()


def test_escaped_pipe_stays_inside_cell():
    """
    [Unit] detectors tables: verifies a backslash-escaped pipe does not split a cell.

    Scenario:
        Given a header cell containing ``\\|`` and a matching two-cell delimiter
        When DS117 recognition runs over the table
        Then no finding is produced because the escaped pipe is cell text, not a separator.

    Boundaries:
        - Focus: backslash escape handling in _split_logical_cells
        - Fixtures/params: default Config

    On failure, first check:
        - The ``char == "\\\\"`` branch that consumes the escaped character
        - Whether the escaped pipe inflated the header cell count to three
    """
    text = "a \\| b | c\n--- | ---\n"
    assert tables.check_text(text, "README.md") == ()


def test_pipe_inside_code_span_does_not_split_cell():
    """
    [Unit] detectors tables: verifies a pipe inside a backtick code span is protected.

    Scenario:
        Given a header cell ``\\`a|b\\``` whose code span contains a pipe
        When DS117 recognition runs over a two-column table
        Then no finding is produced because the code-span pipe does not split a column.

    Boundaries:
        - Focus: backtick code-span masking in _split_logical_cells
        - Fixtures/params: default Config

    On failure, first check:
        - first_backtick_run_at_or_after closing-run detection via the shared index
        - Whether the code-span pipe was counted as a separator
    """
    text = "| `a|b` | c |\n| --- | --- |\n"
    assert tables.check_text(text, "README.md") == ()


def test_optional_outer_pipes_are_valid():
    """
    [Unit] detectors tables: verifies a table without outer border pipes is valid.

    Scenario:
        Given a table whose rows omit the leading and trailing pipes
        When DS117 recognition runs over the table
        Then no finding is produced because outer pipes are optional.

    Boundaries:
        - Focus: border-cell trimming in _split_logical_cells
        - Fixtures/params: default Config

    On failure, first check:
        - The leading/trailing empty-cell drop in _split_logical_cells
        - Whether a missing outer pipe changed the cell count
    """
    text = "A | B\n--- | ---\n1 | 2\n"
    assert tables.check_text(text, "README.md") == ()


def test_explicit_empty_cell_counts_as_a_cell():
    """
    [Unit] detectors tables: verifies an explicit empty cell between separators counts.

    Scenario:
        Given a body row ``| 1 |  |`` with an intentional empty second cell
        When DS117 recognition runs over a two-column table
        Then no finding is produced because the empty cell still counts toward the total.

    Boundaries:
        - Focus: empty-cell preservation versus outer-border trimming
        - Fixtures/params: default Config

    On failure, first check:
        - That only ONE leading and ONE trailing empty border cell is dropped
        - Whether the interior empty cell was collapsed away
    """
    text = "| A | B |\n| --- | --- |\n| 1 |  |\n"
    assert tables.check_text(text, "README.md") == ()


def test_prose_with_pipes_and_no_delimiter_is_not_a_table():
    """
    [Unit] detectors tables: verifies pipe-laden prose without a delimiter is ignored.

    Scenario:
        Given two prose lines that contain pipes but no delimiter row
        When DS117 recognition runs over the text
        Then no finding is produced because no table exists.

    Boundaries:
        - Focus: the exclusion that a header needs an immediate delimiter row
        - Fixtures/params: default Config

    On failure, first check:
        - The _is_delimiter_candidate guard on the second line
        - Whether a non-delimiter line was accepted as a delimiter
    """
    text = "This | has | pipes\nBut no delimiter row here.\n"
    assert tables.check_text(text, "README.md") == ()


def test_blank_line_breaks_header_delimiter_adjacency():
    """
    [Unit] detectors tables: verifies a header is only a table when immediately delimited.

    Scenario:
        Given a header row, a blank line, then a delimiter row
        When DS117 recognition runs over the text
        Then no finding is produced because the delimiter does not immediately follow the header.

    Boundaries:
        - Focus: strict header/delimiter adjacency
        - Fixtures/params: default Config

    On failure, first check:
        - The ``delimiter_index = line_index + 1`` adjacency requirement
        - Whether a blank intervening line was skipped over
    """
    text = "| A | B |\n\n| --- | --- |\n"
    assert tables.check_text(text, "README.md") == ()


def test_table_inside_code_fence_is_ignored():
    """
    [Unit] detectors tables: verifies a table-looking block inside a fence is ignored.

    Scenario:
        Given an inconsistent table wholly inside a fenced code block
        When DS117 recognition runs over the text
        Then no finding is produced because fenced lines are masked.

    Boundaries:
        - Focus: the fence mask derived from the shared scanner
        - Fixtures/params: default Config

    On failure, first check:
        - _fenced_lines span coverage
        - Whether an unclosed fence failed to mask its swallowed body
    """
    text = "```\n| A | B |\n| --- |\n```\n"
    assert tables.check_text(text, "README.md") == ()


def test_extra_body_cell_is_flagged_at_body_line():
    """
    [Unit] detectors tables: verifies a body row with too many cells is flagged.

    Scenario:
        Given a two-column table whose third row carries three cells
        When DS117 recognition runs under the strict cell policy
        Then exactly one finding is produced at the offending body row's line.

    Boundaries:
        - Focus: body cell-count mismatch at the body line
        - Fixtures/params: default Config (strict cells on)

    On failure, first check:
        - The body-row loop and its line-number reporting
        - Whether the header count was taken as the authority
    """
    text = "| A | B |\n| --- | --- |\n| 1 | 2 | 3 |\n"
    findings = tables.check_text(text, "README.md")
    assert _codes(findings) == ["DS117"]
    assert _lines(findings) == [3]
    assert "body" in findings[0].message


def test_missing_delimiter_cell_is_flagged_at_delimiter_line():
    """
    [Unit] detectors tables: verifies a short delimiter row is flagged at its line.

    Scenario:
        Given a two-column header followed by a one-cell delimiter row
        When DS117 recognition runs under the strict cell policy
        Then exactly one finding is produced at the delimiter row's line.

    Boundaries:
        - Focus: delimiter cell-count mismatch at the delimiter line
        - Fixtures/params: default Config

    On failure, first check:
        - The delimiter-row count comparison against the header count
        - Whether the finding line pointed at the header instead
    """
    text = "| A | B |\n| --- |\n"
    findings = tables.check_text(text, "README.md")
    assert _codes(findings) == ["DS117"]
    assert _lines(findings) == [2]
    assert "delimiter" in findings[0].message


def test_missing_body_cell_is_flagged_under_strict_policy():
    """
    [Unit] detectors tables: verifies a short body row is flagged under strict cells.

    Scenario:
        Given a two-column table whose third row carries one cell
        When DS117 recognition runs under the strict cell policy
        Then exactly one finding is produced at the offending body row's line.

    Boundaries:
        - Focus: a body row shorter than the header under strict policy
        - Fixtures/params: default Config

    On failure, first check:
        - The strict-policy gate on body count checks
        - The body-row line reporting
    """
    text = "| A | B |\n| --- | --- |\n| 1 |\n"
    findings = tables.check_text(text, "README.md")
    assert _codes(findings) == ["DS117"]
    assert _lines(findings) == [3]


def test_invalid_alignment_marker_is_flagged_at_delimiter_line():
    """
    [Unit] detectors tables: verifies a malformed alignment marker is reported.

    Scenario:
        Given a two-column table whose delimiter cell ``--:-`` is malformed
        When DS117 recognition runs over the table
        Then exactly one finding at the delimiter line names the malformed marker.

    Boundaries:
        - Focus: malformed alignment marker detection under the supported subset
        - Fixtures/params: default Config

    On failure, first check:
        - _has_malformed_marker versus _is_delimiter_candidate
        - Whether a malformed delimiter stopped the block from being a table at all
    """
    text = "| A | B |\n| :-- | --:- |\n"
    findings = tables.check_text(text, "README.md")
    assert _codes(findings) == ["DS117"]
    assert _lines(findings) == [2]
    assert "malformed" in findings[0].message


def test_malformed_marker_wins_over_count_mismatch_for_one_finding():
    """
    [Unit] detectors tables: verifies one finding per offending delimiter row.

    Scenario:
        Given a two-column header and a three-cell delimiter row with a malformed marker
        When DS117 recognition runs under the strict cell policy
        Then exactly one finding is produced and it reports the malformed marker.

    Boundaries:
        - Focus: single finding per row with malformed precedence over count
        - Fixtures/params: default Config

    On failure, first check:
        - The precedence order in _row_finding (marker before count)
        - Whether the row produced two findings
    """
    text = "| A | B |\n| :-: | --:- | :-: |\n"
    findings = tables.check_text(text, "README.md")
    assert len(findings) == 1
    assert "malformed" in findings[0].message


def test_multiple_broken_tables_report_in_source_order():
    """
    [Unit] detectors tables: verifies independent broken tables report in order.

    Scenario:
        Given two separate broken tables divided by a blank line
        When DS117 recognition runs over the document
        Then one finding per table is produced in ascending source-line order.

    Boundaries:
        - Focus: multiple tables, stable source ordering, no duplicates
        - Fixtures/params: default Config

    On failure, first check:
        - That the body loop stops at the blank line between tables
        - Whether the second table's header was consumed as the first table's body
    """
    text = "| A | B |\n| --- | --- |\n| 1 | 2 | 3 |\n\n| C | D |\n| --- |\n"
    findings = tables.check_text(text, "README.md")
    assert _lines(findings) == [3, 6]


def test_crlf_table_reports_correct_line():
    """
    [Unit] detectors tables: verifies CRLF input keeps one-based line positions.

    Scenario:
        Given a broken table whose lines are terminated by CRLF
        When DS117 recognition runs over the document
        Then the finding points at the offending body row's physical line.

    Boundaries:
        - Focus: CRLF line numbering via split_physical_lines
        - Fixtures/params: default Config

    On failure, first check:
        - Whether CR/LF handling drifted from the shared scanner's numbering
        - The body-row line computation
    """
    text = "| A | B |\r\n| --- | --- |\r\n| 1 |\r\n"
    findings = tables.check_text(text, "README.md")
    assert _lines(findings) == [3]


def test_cr_only_terminator_reports_correct_line():
    """
    [Unit] detectors tables: verifies lone-CR input keeps one-based line positions.

    Scenario:
        Given a broken table whose lines are terminated by lone carriage returns
        When DS117 recognition runs over the document
        Then the finding points at the offending body row's physical line.

    Boundaries:
        - Focus: lone-CR line numbering via split_physical_lines
        - Fixtures/params: default Config

    On failure, first check:
        - Whether lone-CR terminators were treated as line breaks
        - The body-row line computation
    """
    text = "| A | B |\r| --- | --- |\r| 1 |\r"
    findings = tables.check_text(text, "README.md")
    assert _lines(findings) == [3]


def test_unmatched_backtick_is_literal_and_does_not_crash():
    """
    [Unit] detectors tables: verifies an unmatched backtick is treated as literal text.

    Scenario:
        Given a header with a single unmatched backtick before two pipe-split cells
        When DS117 recognition runs over a consistent two-column table
        Then no finding is produced and no error is raised.

    Boundaries:
        - Focus: adversarial unmatched backtick run handling
        - Fixtures/params: default Config

    On failure, first check:
        - The ``close_end == -1`` literal-backtick fallback in _split_logical_cells
        - Whether the unmatched backtick swallowed the following pipe
    """
    text = "| `unclosed | b |\n| --- | --- |\n"
    assert tables.check_text(text, "README.md") == ()


def test_table_enable_false_produces_nothing():
    """
    [Unit] detectors tables: verifies a disabled policy never evaluates.

    Scenario:
        Given a broken table and ``table_enable`` set to false
        When DS117 recognition runs
        Then no finding is produced because the check is disabled.

    Boundaries:
        - Focus: the table_enable gate at the top of check_text
        - Fixtures/params: Config(table_enable=False)

    On failure, first check:
        - The ``not settings.table_enable`` guard
        - That the same text does flag under the default config
    """
    broken = "| A | B |\n| --- |\n"
    assert tables.check_text(broken, "README.md", Config(table_enable=False)) == ()
    assert tables.check_text(broken, "README.md") != ()


def test_unsupported_dialect_produces_nothing():
    """
    [Unit] detectors tables: verifies an unsupported dialect yields no diagnostics.

    Scenario:
        Given a broken table and a ``table_dialect`` the scanner cannot validate
        When DS117 recognition runs
        Then no finding is produced because the dialect is not the supported subset.

    Boundaries:
        - Focus: the table_dialect guard (mirrors DS109/DS110)
        - Fixtures/params: a hand-built Config with an unsupported dialect

    On failure, first check:
        - The ``settings.table_dialect != _SUPPORTED_DIALECT`` guard
        - Whether an unsupported dialect still parsed the table
    """
    broken = "| A | B |\n| --- |\n"
    assert tables.check_text(broken, "README.md", Config(table_dialect="commonmark")) == ()


def test_strict_cells_off_ignores_count_but_keeps_markers():
    """
    [Unit] detectors tables: verifies non-strict policy drops count checks only.

    Scenario:
        Given ``table_strict_cells`` disabled
        When DS117 recognition runs over a cell-count mismatch and over a malformed marker
        Then the count mismatch is ignored while the malformed alignment marker is still reported.

    Boundaries:
        - Focus: strict gate covers cell counts; malformed markers stay structural
        - Fixtures/params: Config(table_strict_cells=False)

    On failure, first check:
        - That only the count branch is gated by ``strict`` in _row_finding
        - Whether the marker check was gated by the strict policy by mistake
    """
    lenient = Config(table_strict_cells=False)
    count_mismatch = "| A | B |\n| --- | --- |\n| 1 | 2 | 3 |\n"
    assert tables.check_text(count_mismatch, "README.md", lenient) == ()
    malformed = "| A | B |\n| :-- | --:- |\n"
    findings = tables.check_text(malformed, "README.md", lenient)
    assert _lines(findings) == [2]
    assert "malformed" in findings[0].message


def test_message_snippet_is_bounded():
    """
    [Unit] detectors tables: verifies an echoed delimiter snippet stays bounded.

    Scenario:
        Given a malformed delimiter row with a very long run of markers
        When DS117 recognition runs over the table
        Then the echoed snippet in the message stays within the bounded echo budget.

    Boundaries:
        - Focus: bounded, repr-safe message echo
        - Fixtures/params: default Config

    On failure, first check:
        - _snippet truncation to _MAX_SNIPPET_ECHO
        - Whether the whole (possibly huge) row was echoed verbatim
    """
    long_cell = ":" + "-" * 500 + ":" + "-"  # trailing dash makes it malformed
    text = f"| A |\n| {long_cell} |\n"
    findings = tables.check_text(text, "README.md")
    assert len(findings) == 1
    # The snippet is bounded; the message prefix plus a <=83-char echo stays small.
    assert len(findings[0].message) < 160


def test_repeated_recognition_is_stable():
    """
    [Unit] detectors tables: verifies recognition is deterministic across repeats.

    Scenario:
        Given one broken table
        When DS117 recognition runs twice over identical input
        Then both runs return identical findings.

    Boundaries:
        - Focus: no hidden state or caching between runs
        - Fixtures/params: default Config

    On failure, first check:
        - Any mutable module-level state in the detector
        - Whether scan_markdown shared mutable tokens
    """
    text = "| A | B |\n| --- | --- |\n| 1 | 2 | 3 |\n"
    first = tables.check_text(text, "README.md")
    second = tables.check_text(text, "README.md")
    assert first == second
    assert _lines(first) == [3]


def test_detect_reads_documents_and_normalizes_path(tmp_path: Path):
    """
    [Unit] detectors tables: verifies detect reads a document and records its path.

    Scenario:
        Given a committed Markdown file with a broken table on disk
        When detect runs over the discovered document
        Then one finding is produced carrying the document's relative POSIX path.

    Boundaries:
        - Focus: the detect file-reading layer over check_text
        - Fixtures/params: tmp_path with one README.md

    On failure, first check:
        - The ``.md`` suffix filter and UTF-8 read in detect
        - Whether the recorded path matched the supplied document path
    """
    (tmp_path / "README.md").write_text("| A | B |\n| --- |\n", encoding="utf-8")
    documents = (models.Document(path="README.md", bytes=0),)
    findings = detect_findings = tables.detect(tmp_path, documents)
    assert [finding.path for finding in detect_findings] == ["README.md"]
    assert _lines(findings) == [2]


def test_leading_tab_counts_as_indentation_so_the_table_is_not_parsed():
    """
    [Unit] detectors tables: verifies a leading tab makes a table-shaped line a non-table.

    Scenario:
        Given a table-shaped block whose lines start with a tab, with two spaces plus a tab,
            with one space plus a tab, and (as the control) with three spaces
        When check_text runs over each
        Then the tab-indented variants (column four or more) produce no finding, matching
            CommonMark's tab-stop rule for indented code, while the three-space control still
            reports its broken body row.

    Boundaries:
        - Focus: _is_block_prefixed tab handling
        - Fixtures/params: parametrized inline strings
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Whether a tab advances the indentation column to the next multiple of four
        - Whether only literal spaces are counted again
    """
    for prefix, expected in (("\t", []), ("  \t", []), (" \t", []), ("   ", [3])):
        text = f"{prefix}| A | B |\n{prefix}| --- | --- |\n{prefix}| 1 | 2 | 3 |\n"
        assert _lines(tables.check_text(text, "README.md")) == expected, repr(prefix)
