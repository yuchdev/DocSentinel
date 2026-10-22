"""Unit tests for DS109 fenced-code boundary recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition helpers directly. Detection over committed Markdown assets is the
job of the Story 06.0 Task 03 integration suite, which runs once ``DS109`` is
registered together with its ``tests/assets/ds109/*`` fixtures (Task 02).
"""

from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import fences
from docsentinel.markdown_blocks import scan_markdown


def _codes(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the rule code of each finding in order."""
    return [finding.rule for finding in findings]


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors fences: verifies DS109 metadata and its fast-profile registration.

    Scenario:
        Given the DS109 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered with its analyzer.

    Boundaries:
        - Focus: rule metadata and registration state only
        - Fixtures/params: none

    On failure, first check:
        - Whether DS109 was registered as a fast-profile rule with its analyzer
        - Whether a metadata field (profile, severity, title) drifted
    """
    assert fences.DS109.code == "DS109"
    assert fences.DS109.profile == "fast"
    assert fences.DS109.severity == "error"
    assert fences.DS109.title == "Malformed or unclosed fenced code blocks"
    # Registration lands with the committed Task 02 fixtures.
    assert rules.RULES["DS109"] is fences.DS109
    assert rules.ANALYZERS["DS109"] is fences.detect


def test_valid_backtick_fence_is_clean():
    """
    [Unit] detectors fences: verifies a paired backtick fence yields no finding.

    Scenario:
        Given three backticks that open and close a code fence
        When DS109 recognition runs over the text
        Then no finding is produced.

    Boundaries:
        - Focus: normal, well-formed backtick fence
        - Fixtures/params: inline string

    On failure, first check:
        - The shared scanner's closed-fence detection
        - The detector's clean-case short circuit
    """
    assert fences.check_text("```\ncode\n```\n", "README.md") == ()


def test_valid_tilde_fence_and_longer_closer_are_clean():
    """
    [Unit] detectors fences: verifies tilde fences and over-length closers are clean.

    Scenario:
        Given a paired tilde fence and a backtick fence closed by a longer run
        When DS109 recognition runs over each text
        Then neither produces a finding.

    Boundaries:
        - Focus: tilde marker support and longer-closer acceptance
        - Fixtures/params: inline strings

    On failure, first check:
        - Closer-length comparison (closer >= opener is valid)
        - Tilde marker handling in the shared scanner
    """
    assert fences.check_text("~~~\ncode\n~~~\n", "README.md") == ()
    assert fences.check_text("```\ncode\n`````\n", "README.md") == ()


def test_unterminated_fence_reports_opener_line_once():
    """
    [Unit] detectors fences: verifies an EOF-unterminated fence reports its opener line.

    Scenario:
        Given a backtick opener on line 2 with no closing delimiter by EOF
        When DS109 recognition runs
        Then exactly one error finding is produced at the opener line.

    Boundaries:
        - Focus: unclosed-fence EOF handling and line fidelity
        - Fixtures/params: inline string

    On failure, first check:
        - The reported line against the opener position
        - That only one finding is emitted for the single opener
    """
    findings = fences.check_text("intro\n```py\ncode\nmore\n", "README.md")
    assert len(findings) == 1
    assert findings[0].rule == "DS109"
    assert findings[0].severity == "error"
    assert findings[0].line == 2
    assert findings[0].path == "README.md"
    assert "unclosed" in findings[0].message


def test_wrong_marker_shorter_run_and_trailing_text_do_not_close():
    """
    [Unit] detectors fences: verifies invalid closers leave a fence unclosed.

    Scenario:
        Given a tilde run, a shorter run, and a run with trailing text as closers
        When DS109 recognition runs over each backtick-opened fence
        Then each is reported as a single unclosed-fence finding.

    Boundaries:
        - Focus: closer character, closer length, and closer trailing-content rules
        - Fixtures/params: inline strings

    On failure, first check:
        - The shared scanner's is-closer predicate
        - That a rejected closer does not silently complete the fence
    """
    wrong_char = fences.check_text("```py\ncode\n~~~\n", "README.md")
    shorter = fences.check_text("````\ncode\n``\n", "README.md")
    trailing = fences.check_text("```\ncode\n``` done\n", "README.md")
    for findings in (wrong_char, shorter, trailing):
        assert len(findings) == 1
        assert findings[0].line == 1
        assert "unclosed" in findings[0].message


def test_backtick_in_info_string_is_malformed_opener():
    """
    [Unit] detectors fences: verifies a backtick in a backtick-fence info string is flagged.

    Scenario:
        Given a closed backtick fence whose info string contains a backtick
        When DS109 recognition runs
        Then one malformed-opener finding is produced at the opener line.

    Boundaries:
        - Focus: backtick-opener info-string rule, distinct from delimiter problems
        - Fixtures/params: inline string

    On failure, first check:
        - The info-string backtick check against the closed-fence branch
        - That a tilde fence with tildes in its info is not similarly flagged
    """
    findings = fences.check_text("```py`thon\ncode\n```\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 1
    assert "info string" in findings[0].message
    # A tilde fence may legally carry tildes in its info string.
    assert fences.check_text("~~~foo~bar\ncode\n~~~\n", "README.md") == ()


def test_indented_four_space_ticks_are_not_a_fence():
    """
    [Unit] detectors fences: verifies four-space indented backticks are not an opener.

    Scenario:
        Given backticks indented by four spaces (an indented code block)
        When DS109 recognition runs
        Then no fence is recognized and no finding is produced.

    Boundaries:
        - Focus: the <= 3 space indent exclusion for fence openers
        - Fixtures/params: inline string

    On failure, first check:
        - The indent bound in the shared scanner's fence regex
        - That indented literal backticks are treated as content
    """
    assert fences.check_text("    ```\n    code\n", "README.md") == ()


def test_opposite_marker_inside_fence_is_literal_content():
    """
    [Unit] detectors fences: verifies tildes inside a backtick fence are content.

    Scenario:
        Given a backtick fence whose body contains tilde runs
        When DS109 recognition runs
        Then the tildes are treated as literal content and no finding is produced.

    Boundaries:
        - Focus: cross-marker interaction inside a fenced body
        - Fixtures/params: inline string

    On failure, first check:
        - That only the opening marker can close its own fence
        - The masking of fenced content in the shared scanner
    """
    assert fences.check_text("```\n~~~\ncode\n~~~\n```\n", "README.md") == ()


def test_trailing_whitespace_after_closer_is_permitted():
    """
    [Unit] detectors fences: verifies trailing spaces after a closer still close the fence.

    Scenario:
        Given a valid closing fence followed by trailing spaces
        When DS109 recognition runs
        Then the fence is considered closed and no finding is produced.

    Boundaries:
        - Focus: permitted trailing whitespace on a closing delimiter
        - Fixtures/params: inline string

    On failure, first check:
        - The closer's trailing-whitespace tolerance
        - That trailing non-whitespace would instead reject the closer
    """
    assert fences.check_text("```\ncode\n```   \n", "README.md") == ()


def test_crlf_unclosed_fence_reports_physical_opener_line():
    """
    [Unit] detectors fences: verifies CRLF input preserves the opener line number.

    Scenario:
        Given CRLF-terminated Markdown with an unclosed fence opening on line 3
        When DS109 recognition runs
        Then the single finding reports physical line 3.

    Boundaries:
        - Focus: CRLF line numbering for unclosed fences
        - Fixtures/params: inline string

    On failure, first check:
        - The scanner's CRLF terminator handling
        - The one-based opener line on the emitted finding
    """
    findings = fences.check_text("a\r\nb\r\n```\ncode\n", "README.md")
    assert len(findings) == 1
    assert findings[0].line == 3


def test_many_pseudo_openers_collapse_to_one_finding():
    """
    [Unit] detectors fences: verifies adversarial pseudo-openers do not cascade.

    Scenario:
        Given one long opening fence followed by hundreds of shorter pseudo-openers
        When DS109 recognition runs
        Then exactly one unclosed-fence finding is produced, with no cascade.

    Boundaries:
        - Focus: single-finding behavior and linear handling on adversarial input
        - Fixtures/params: generated inline string

    On failure, first check:
        - That the first opener swallows the rest as body
        - That no per-pseudo-opener finding is emitted
    """
    text = "`````\n" + "```\n" * 500
    findings = fences.check_text(text, "README.md")
    assert len(findings) == 1
    assert findings[0].line == 1


def test_unsupported_dialect_emits_no_confident_diagnostics():
    """
    [Unit] detectors fences: verifies an unsupported dialect yields no findings.

    Scenario:
        Given a Config whose fence_dialect is not the supported gfm-subset
        When DS109 recognition runs over text that would otherwise flag
        Then no finding is produced rather than a confident false diagnostic.

    Boundaries:
        - Focus: dialect gating on malformed input (invalid-config guard)
        - Fixtures/params: Config constructed directly to bypass TOML validation

    On failure, first check:
        - The fence_dialect guard in check_text
        - That the default gfm-subset path still flags the same input
    """
    unsupported = Config(fence_dialect="other-dialect")
    assert fences.check_text("```\ncode\n", "README.md", unsupported) == ()
    # The same text flags under the supported default dialect.
    assert len(fences.check_text("```\ncode\n", "README.md")) == 1


def test_report_stray_closing_fence_flag_does_not_change_results():
    """
    [Unit] detectors fences: verifies the reserved stray-closer flag has no extra effect.

    Scenario:
        Given a lone trailing closing fence scanned with the flag off and on
        When DS109 recognition runs under both settings
        Then both report the same single unclosed-fence finding.

    Boundaries:
        - Focus: documented no-op of report_stray_closing_fence in gfm-subset
        - Fixtures/params: Config toggled on the flag

    On failure, first check:
        - The module docstring's reserved-option note
        - That a lone closer is modeled as an unclosed opener
    """
    text = "```\ncode\n```\ntail\n```\n"
    off = fences.check_text(text, "README.md", Config(report_stray_closing_fence=False))
    on = fences.check_text(text, "README.md", Config(report_stray_closing_fence=True))
    assert _codes(off) == _codes(on) == ["DS109"]


def test_fenced_line_numbers_masks_fence_span():
    """
    [Unit] detectors fences: verifies the shared fence mask covers delimiter and body lines.

    Scenario:
        Given a document with one fenced block on lines 2 through 4
        When fenced_line_numbers builds the shared mask
        Then it contains the delimiter and body lines but not surrounding prose.

    Boundaries:
        - Focus: the shared fence-mask helper offered to other DS1xx analyzers
        - Fixtures/params: inline string

    On failure, first check:
        - The inclusive start/end line range used to build the mask
        - That unclosed fences extend the mask to end of file
    """

    index = scan_markdown("intro\n```\ncode\n```\nafter\n", "README.md")
    assert fences.fenced_line_numbers(index) == frozenset({2, 3, 4})


def test_detect_reads_documents_and_skips_non_markdown(tmp_path: Path):
    """
    [Unit] detectors fences: verifies detect reads .md files and ignores others.

    Scenario:
        Given a Markdown file with an unclosed fence and a non-Markdown sibling
        When detect runs over both documents
        Then only the Markdown file contributes a single DS109 finding.

    Boundaries:
        - Focus: document reading, .md filtering, and path propagation in detect
        - Fixtures/params: tmp_path with two committed files

    On failure, first check:
        - The .md suffix filter in detect
        - That the finding path matches the Markdown document path
    """
    (tmp_path / "README.md").write_text("```\ncode\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("```\ncode\n", encoding="utf-8")
    documents = (models.Document("README.md", 1), models.Document("notes.txt", 1))
    findings = fences.detect(tmp_path, documents)
    assert len(findings) == 1
    assert findings[0].path == "README.md"


def test_detect_surfaces_invalid_utf8_rather_than_false_clean(tmp_path: Path):
    """
    [Unit] detectors fences: verifies invalid UTF-8 raises instead of passing silently.

    Scenario:
        Given a Markdown document containing invalid UTF-8 bytes
        When detect attempts to read it
        Then a UnicodeDecodeError propagates rather than a false clean result.

    Boundaries:
        - Focus: explicit handling of unreadable input (no silent clean signal)
        - Fixtures/params: tmp_path file with invalid bytes

    On failure, first check:
        - The UTF-8 read in _read_text
        - That unreadable input is never reported as zero findings
    """
    (tmp_path / "README.md").write_bytes(b"```\n\xff\xfe\n")
    with pytest.raises(UnicodeDecodeError):
        fences.detect(tmp_path, (models.Document("README.md", 1),))


def test_repeated_recognition_is_deterministic():
    """
    [Unit] detectors fences: verifies repeated scans produce identical findings.

    Scenario:
        Given the same Markdown text scanned twice
        When DS109 recognition runs on each pass
        Then the two finding tuples are equal.

    Boundaries:
        - Focus: determinism and absence of shared mutable state
        - Fixtures/params: inline string

    On failure, first check:
        - Any module-level mutable caches
        - Ordering stability of the shared scanner's fence list
    """
    text = "```\none\n```\n```py`thon\ntwo\n```\n"
    assert fences.check_text(text, "README.md") == fences.check_text(text, "README.md")
