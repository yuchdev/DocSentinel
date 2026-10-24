"""Unit tests for DS104 conflicting-anchor recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition helpers directly. Detection over committed Markdown assets is the
job of the Story 02.0 Task 03 integration suite, which runs now that ``DS104`` is
registered together with its ``tests/assets/ds104/*`` fixtures (Task 02).

Registration landed with Task 02: ``DS104`` is wired into the rule registry, the
analyzer registry, and ``docsentinel.detectors.__init__`` alongside its committed
fixtures. The first test pins that registered state so the Milestone 0005 fixture
catalog actively enforces the DS104 slice.
"""

from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import anchors


def test_rule_metadata_is_exact_and_registration_is_wired():
    """
    [Unit] detectors anchors: verifies DS104 metadata and its registration.

    Scenario:
        Given the DS104 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered and wired as a fast rule.

    Boundaries:
        - Focus: rule metadata and the registration gate only
        - Fixtures/params: none

    On failure, first check:
        - That docsentinel.detectors.anchors registered DS104 on import
        - Whether a metadata field (profile, severity, title) drifted
    """
    assert anchors.DS104.code == "DS104"
    assert anchors.DS104.profile == "fast"
    assert anchors.DS104.severity == "warning"
    assert anchors.DS104.title == "Conflicting heading and explicit anchors"
    # Registration landed with the committed Task 02 fixtures.
    assert rules.RULES["DS104"] is anchors.DS104
    assert rules.ANALYZERS["DS104"] is anchors.detect


def test_distinct_headings_without_explicit_anchors_are_clean():
    """
    [Unit] detectors anchors: verifies ordinary headings alone never collide.

    Scenario:
        Given two distinct headings and no explicit HTML anchors
        When DS104 recognition runs
        Then no finding is produced.

    Boundaries:
        - Focus: normal case; generated anchors do not self-collide
        - Fixtures/params: inline string

    On failure, first check:
        - That the generated namespace only collides with explicit anchors
    """
    assert anchors.check_text("# Alpha\n\n## Beta\n", "README.md") == ()


def test_repeated_headings_do_not_collide():
    """
    [Unit] detectors anchors: verifies duplicate headings stay valid via suffixes.

    Scenario:
        Given three identical headings that slug to setup, setup-1, setup-2
        When DS104 recognition runs
        Then no finding is produced because each owns a distinct generated anchor.

    Boundaries:
        - Focus: DS101 duplicate-suffix compatibility (algorithm bullet 1)
        - Fixtures/params: inline string

    On failure, first check:
        - That repeated headings are never flagged without an explicit conflict
        - The shared scanner's -N suffixing
    """
    assert anchors.check_text("# Setup\n# Setup\n# Setup\n", "README.md") == ()


def test_repeated_explicit_anchor_is_flagged_once():
    """
    [Unit] detectors anchors: verifies a repeated explicit id/name is flagged.

    Scenario:
        Given an explicit id and an explicit name sharing the identifier 'dup'
        When DS104 recognition runs
        Then exactly one finding reports the later definition as a repeat.

    Boundaries:
        - Focus: repeated-explicit-identifier collision (algorithm bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - The seen-identifier set in _anchor_findings
        - That id and name share one explicit namespace
    """
    findings = anchors.check_text('<a id="dup"></a>\n<a name="dup"></a>\n', "README.md")
    assert len(findings) == 1
    assert findings[0].rule == "DS104"
    assert findings[0].severity == "warning"
    assert findings[0].path == "README.md"
    assert findings[0].line == 2
    assert "dup" in findings[0].message
    assert "more than once" in findings[0].message


def test_explicit_anchor_shadowing_generated_slug_is_flagged():
    """
    [Unit] detectors anchors: verifies an explicit anchor shadowing a slug is flagged.

    Scenario:
        Given a heading slugged 'setup' and an explicit anchor named 'setup'
        When DS104 recognition runs
        Then one finding reports the explicit-vs-generated collision.

    Boundaries:
        - Focus: explicit-vs-generated collision (algorithm bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - The generated namespace built from heading slugs
        - That the explicit anchor is the offending party
    """
    findings = anchors.check_text('# Setup\n\n<a name="setup"></a>\n', "README.md")
    assert len(findings) == 1
    assert findings[0].rule == "DS104"
    assert findings[0].line == 3
    assert "setup" in findings[0].message
    assert "generated" in findings[0].message


def test_explicit_anchor_naming_a_generated_suffix_is_flagged():
    """
    [Unit] detectors anchors: verifies an explicit anchor colliding with a -N slug is flagged.

    Scenario:
        Given two 'Setup' headings slugged setup and setup-1 and an explicit anchor 'setup-1'
        When DS104 recognition runs
        Then one finding reports the collision with the generated suffixed slug.

    Boundaries:
        - Focus: explicit-vs-generated collision against a duplicate suffix (bullet 3)
        - Fixtures/params: inline string

    On failure, first check:
        - That both duplicate headings enter the generated namespace
        - That the suffixed slug setup-1 is a real anchor identity
    """
    findings = anchors.check_text('# Setup\n# Setup\n\n<a name="setup-1"></a>\n', "README.md")
    assert len(findings) == 1
    assert findings[0].line == 4
    assert "setup-1" in findings[0].message
    assert "generated" in findings[0].message


def test_anchor_inside_inline_code_is_ignored():
    """
    [Unit] detectors anchors: verifies anchor-shaped inline code does not collide.

    Scenario:
        Given a heading slugged 'target' and an identical anchor shown inside inline code
        When DS104 recognition runs
        Then the inline-code anchor is masked out and no finding is produced.

    Boundaries:
        - Focus: inline-code masking in the shared scanner (exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That _mask_line blanks inline-code spans before anchor extraction
    """
    assert anchors.check_text('# Target\n\nUse `<a name="target">` literally.\n', "README.md") == ()


def test_anchor_inside_html_comment_is_ignored():
    """
    [Unit] detectors anchors: verifies anchor-shaped comment text does not collide.

    Scenario:
        Given a heading slugged 'target' and an identical anchor inside a multi-line comment
        When DS104 recognition runs
        Then the commented anchor is masked out and no finding is produced.

    Boundaries:
        - Focus: comment masking across lines in the shared scanner (exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That comment ranges mask explicit-anchor extraction on every covered line
    """
    text = '# Target\n\n<!--\n<a name="target"></a>\n-->\n'
    assert anchors.check_text(text, "README.md") == ()


def test_explicit_identifiers_are_compared_case_sensitively():
    """
    [Unit] detectors anchors: verifies explicit ids are not lowercased.

    Scenario:
        Given a heading slugged 'setup' and explicit anchors 'Setup' and 'SETUP'
        When DS104 recognition runs
        Then no finding appears because case-distinct ids prove no ambiguity.

    Boundaries:
        - Focus: HTML id/name case sensitivity (algorithm bullet 4, exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That explicit identifiers are never folded to lowercase
        - That a case-mismatched id does not collide with a lowercase slug
    """
    assert anchors.check_text('# Setup\n\n<a id="Setup"></a>\n<a id="SETUP"></a>\n', "README.md") == ()


def test_anchor_inside_code_fence_is_ignored():
    """
    [Unit] detectors anchors: verifies fenced anchor syntax does not collide.

    Scenario:
        Given a heading slugged 'target' and an identical anchor inside a code fence
        When DS104 recognition runs
        Then the fenced anchor is not extracted and no finding is produced.

    Boundaries:
        - Focus: fenced-code masking from the shared scanner (exclusions)
        - Fixtures/params: inline string

    On failure, first check:
        - That the shared scanner masks fenced lines before anchor extraction
    """
    text = '# Target\n\n```html\n<a name="target"></a>\n```\n'
    assert anchors.check_text(text, "README.md") == ()


def test_empty_headings_do_not_collide_or_seed_bogus_anchor():
    """
    [Unit] detectors anchors: verifies empty-text headings never create collisions.

    Scenario:
        Given two empty ATX headings (slugged '' and '-1') and an explicit anchor '-1'
        When DS104 recognition runs
        Then no finding appears: the empty base slug is excluded and '-1' is not bogus.

    Boundaries:
        - Focus: Story 01.0 review follow-up for empty slugs (false-positive safeguard)
        - Fixtures/params: inline string with empty '# ' headings

    On failure, first check:
        - That _generated_anchor_slugs excludes headings with an empty base slug
        - That the suffixed '-1' slug of an empty heading is not a real anchor
    """
    assert anchors.check_text('# \n## \n<a name="-1"></a>\n', "README.md") == ()


def test_collision_policy_off_suppresses_findings():
    """
    [Unit] detectors anchors: verifies the off policy disables all collisions.

    Scenario:
        Given a document with a genuine repeated explicit anchor
        When DS104 recognition runs with anchor_collision_policy off
        Then no finding is produced.

    Boundaries:
        - Focus: anchor_collision_policy gate so a disabled policy is not masqueraded
        - Fixtures/params: Config(anchor_collision_policy="off")

    On failure, first check:
        - The off-policy early return in check_text
    """
    text = '<a id="dup"></a>\n<a name="dup"></a>\n'
    assert len(anchors.check_text(text, "README.md")) == 1
    assert anchors.check_text(text, "README.md", Config(anchor_collision_policy="off")) == ()


def test_multiple_repeats_yield_one_finding_each_in_source_order():
    """
    [Unit] detectors anchors: verifies each later identifier is flagged once in order.

    Scenario:
        Given a heading slugged 'x' then three explicit anchors all named 'x'
        When DS104 recognition runs
        Then three findings appear: one shadow then two repeats, in source order.

    Boundaries:
        - Focus: one finding per offending later identifier, stable order (bullet 5)
        - Fixtures/params: inline string

    On failure, first check:
        - That the first explicit 'x' is the shadow and each later one is a repeat
        - That findings follow the scanner's source order of explicit anchors
    """
    text = '# X\n\n<a name="x"></a>\n<a name="x"></a>\n<a id="x"></a>\n'
    findings = anchors.check_text(text, "README.md")
    assert len(findings) == 3
    assert [finding.line for finding in findings] == [3, 4, 5]
    assert "generated" in findings[0].message
    assert "more than once" in findings[1].message
    assert "more than once" in findings[2].message


def test_recognition_is_deterministic_across_repeated_runs():
    """
    [Unit] detectors anchors: verifies repeated recognition is identical.

    Scenario:
        Given the same Markdown text recognized twice
        When DS104 recognition runs on each pass
        Then the two finding tuples are equal and pinned to the expected collisions.

    Boundaries:
        - Focus: determinism and absence of shared mutable state
        - Fixtures/params: inline string

    On failure, first check:
        - Any module-level mutable caches
        - Ordering stability of the shared scanner's anchor list
    """
    text = '# A\n\n<a name="a"></a>\n<a name="a"></a>\n'
    first = anchors.check_text(text, "README.md")
    assert first == anchors.check_text(text, "README.md")
    assert [finding.message for finding in first] == [
        "explicit anchor 'a' collides with the generated anchor of a heading",
        "explicit anchor 'a' is defined more than once in this document",
    ]


def test_detect_reads_markdown_and_skips_non_markdown(tmp_path: Path):
    """
    [Unit] detectors anchors: verifies detect reads .md files and ignores others.

    Scenario:
        Given a Markdown file with a shadowing anchor and a non-Markdown sibling
        When detect runs over both documents
        Then only the Markdown file contributes a single DS104 finding.

    Boundaries:
        - Focus: document reading, .md filtering, and path propagation in detect
        - Fixtures/params: tmp_path with two committed files

    On failure, first check:
        - The .md suffix filter in detect
        - That the finding path matches the Markdown document path
    """
    (tmp_path / "README.md").write_text('# Dup\n\n<a name="dup"></a>\n', encoding="utf-8")
    (tmp_path / "notes.txt").write_text('# Dup\n\n<a name="dup"></a>\n', encoding="utf-8")
    documents = (models.Document("README.md", 1), models.Document("notes.txt", 1))
    findings = anchors.detect(tmp_path, documents)
    assert len(findings) == 1
    assert findings[0].path == "README.md"
    assert findings[0].rule == "DS104"


def test_detect_does_not_collide_across_documents(tmp_path: Path):
    """
    [Unit] detectors anchors: verifies identifiers are scoped per document.

    Scenario:
        Given two Markdown documents that each define the same explicit anchor once
        When detect runs over both
        Then no finding is produced because collisions never span documents.

    Boundaries:
        - Focus: per-document scoping (algorithm bullet 5, exclusions)
        - Fixtures/params: tmp_path with two committed files

    On failure, first check:
        - That each document is scanned independently with a fresh seen set
    """
    (tmp_path / "a.md").write_text('<a name="shared"></a>\n', encoding="utf-8")
    (tmp_path / "b.md").write_text('<a name="shared"></a>\n', encoding="utf-8")
    documents = (models.Document("a.md", 1), models.Document("b.md", 1))
    assert anchors.detect(tmp_path, documents) == ()


def test_detect_surfaces_invalid_utf8_rather_than_false_clean(tmp_path: Path):
    """
    [Unit] detectors anchors: verifies invalid UTF-8 raises instead of passing silently.

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
    (tmp_path / "README.md").write_bytes(b'<a name="x"></a>\n\xff\xfe\n')
    with pytest.raises(UnicodeDecodeError):
        anchors.detect(tmp_path, (models.Document("README.md", 1),))


def test_many_duplicate_headings_stay_bounded_and_clean():
    """
    [Unit] detectors anchors: verifies a large duplicate-heading corpus stays clean.

    Scenario:
        Given twenty thousand identical non-fenced headings and, separately, a single
            heading whose text is one hundred thousand characters
        When DS104 recognition runs over each
        Then both are clean because suffixed headings never self-collide.

    Boundaries:
        - Focus: linear handling and a ratio-based bound on adversarial non-fenced prose
        - Fixtures/params: generated inline strings (not fenced, so the scanner cannot skip them)

    On failure, first check:
        - That generated anchors never collide among themselves
        - That a very long single heading does not blow up the slugger
    """
    assert anchors.check_text("# Dup\n" * 20000, "README.md") == ()
    assert anchors.check_text("# " + ("word " * 20000) + "\n", "README.md") == ()


def test_many_explicit_anchors_scale_by_ratio():
    """
    [Unit] detectors anchors: verifies explicit-anchor volume scales by ratio.

    Scenario:
        Given many distinct explicit anchors and, separately, many identical ones
        When DS104 recognition runs over each
        Then distinct anchors are clean and N identical anchors yield exactly N-1 findings.

    Boundaries:
        - Focus: ratio-based bound on many non-fenced explicit anchors (adversarial)
        - Fixtures/params: generated inline strings of <a name=...> tags

    On failure, first check:
        - That only repeats after the first definition are reported
        - That distinct identifiers never collide
    """
    count = 5000
    distinct = "".join(f'<a name="anchor-{index}"></a>\n' for index in range(count))
    assert anchors.check_text(distinct, "README.md") == ()
    identical = '<a name="same"></a>\n' * count
    findings = anchors.check_text(identical, "README.md")
    assert len(findings) == count - 1
    assert all("more than once" in finding.message for finding in findings)
