"""Unit tests for DS116 path-boundary recognition (``path_boundaries.py``).

These exercise the detector with tiny inline Markdown strings and ``tmp_path``
roots, never loading ``tests/assets`` (Story 11.0 Task 02 commits the fixtures).
They cover every algorithm bullet and false-positive safeguard from the task
briefing and the standing threat model: lexical escapes, decode-once and the
residual-encoding ruling (G1), Windows drive/UNC/backslash and control targets,
the three config options, the bounded repr-escaped message, source ordering and
de-duplication, and the safe non-following symlink containment check (G4).

``DS116`` is registered as an always-active fast rule (Story 11.0 Task 02); these
tests still call ``check_text``/``detect`` directly rather than going through the
engine so they can exercise each config and algorithm bullet in isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import path_boundaries as pb


def _messages(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the message strings of findings in order."""
    return [finding.message for finding in findings]


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors path_boundaries: verifies DS116 metadata and active registration.

    Scenario:
        Given the module-level DS116 rule object
        When its fields and the global registry are inspected
        Then it is a fast, error-severity, non-opt-in rule registered in RULES and ANALYZERS.

    Boundaries:
        - Focus: rule identity and the Task 02 always-active registration
        - Fixtures/params: none

    On failure, first check:
        - Whether register_rule and the ANALYZERS wiring are present in path_boundaries
        - Whether the Rule fields drifted from the story contract
    """
    assert pb.DS116.code == "DS116"
    assert pb.DS116.profile == "fast"
    assert pb.DS116.severity == "error"
    assert pb.DS116.opt_in_option == ""
    assert rules.RULES["DS116"] is pb.DS116
    assert rules.ANALYZERS["DS116"] is pb.detect


def test_lexical_parent_escape_is_flagged(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies a lexical parent escape is flagged.

    Scenario:
        Given a link whose ``../`` chain leaves the scan root
        When check_text runs with the default error policy
        Then exactly one DS116 error finding names the raw target at its line.

    Boundaries:
        - Focus: algorithm bullet 1 (lexical normalization then reject escape)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether resolve_local_reference still returns OUTSIDE_ROOT for ``..`` escapes
        - Whether the message echoes the raw target
    """
    findings = pb.check_text("[x](../../secrets.md)\n", "docs/README.md", tmp_path)

    assert findings == (
        models.Finding(
            rule="DS116",
            path="docs/README.md",
            message="reference escapes the documentation root: ../../secrets.md",
            severity="error",
            line=1,
        ),
    )


@pytest.mark.parametrize(
    "target",
    ("%2e%2e/%2e%2e/file.md", "..%2f..%2fx.md"),
)
def test_percent_encoded_escape_is_flagged_after_one_decode(tmp_path: Path, target: str):
    """
    [Unit] detectors path_boundaries: verifies a single decode exposes an encoded escape.

    Scenario:
        Given a percent-encoded parent escape (encoded dots or encoded separators)
        When check_text decodes exactly once and normalizes
        Then the target is reported as a root escape.

    Boundaries:
        - Focus: algorithm bullet 2 (decode once, then validate)
        - Fixtures/params: tmp_path, target (parametrized, 2 cases)

    On failure, first check:
        - Whether the shared resolver still decodes exactly once
        - Whether the encoded separator decodes to a real ``/``
    """
    findings = pb.check_text(f"[x]({target})\n", "docs/README.md", tmp_path)

    assert len(findings) == 1
    assert findings[0].message.startswith("reference escapes the documentation root: ")


def test_double_encoded_attack_is_flagged_as_residual_without_double_decoding(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies the ruling G1 residual-encoding signal.

    Scenario:
        Given the double-encoded ``%252e%252e/x.md`` target
        When check_text decodes once (yielding literal ``%2e%2e/x.md``) and inspects the residue
        Then a residual-encoding finding is produced without ever decoding twice.

    Boundaries:
        - Focus: ruling G1 (conservative residual-encoding reject, never double-decode)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _RESIDUAL_ENCODING_RE still matches a residual ``%2e`` octet
        - Whether the resolver was wrongly changed to double-decode
    """
    findings = pb.check_text("[x](%252e%252e/x.md)\n", "docs/README.md", tmp_path)

    assert len(findings) == 1
    assert "percent-encoded path separators" in findings[0].message


@pytest.mark.parametrize("target", ("100%25.md", "a%41b.md"))
def test_benign_residual_percent_stays_clean(tmp_path: Path, target: str):
    """
    [Unit] detectors path_boundaries: verifies a lone or non-separator residual percent stays clean.

    Scenario:
        Given targets whose single decode leaves a ``%25`` or a non-separator ``%xx`` residue
        When check_text applies the residual-encoding check
        Then no finding is produced (only residual dot/slash/backslash octets trip G1).

    Boundaries:
        - Focus: ruling G1 negative side (``%25`` and other residues are clean)
        - Fixtures/params: tmp_path, target (parametrized, 2 cases)

    On failure, first check:
        - Whether _RESIDUAL_ENCODING_RE over-matches beyond ``%2e``/``%2f``/``%5c``
    """
    assert pb.check_text(f"[x]({target})\n", "README.md", tmp_path) == ()


@pytest.mark.parametrize(
    ("target", "fragment"),
    (
        (r"C:\Windows\win.ini", "Windows drive-letter"),
        ("c:/x", "Windows drive-letter"),
        ("C%3A/x", "Windows drive-letter"),
        (r"\\server\share", "UNC network"),
        (r"\Windows\system32", "backslash path separators"),
        (r"..%5c..%5cx", "backslash path separators"),
    ),
)
def test_windows_and_separator_targets_are_flagged_under_portable_policy(tmp_path: Path, target: str, fragment: str):
    """
    [Unit] detectors path_boundaries: verifies Windows/UNC/backslash targets are flagged by default.

    Scenario:
        Given drive-letter, UNC, rooted-backslash, embedded-backslash, and encoded-backslash targets
        When check_text runs with the default ``windows_path_policy = "portable"``
        Then each is a DS116 finding with the matching diagnostic fragment.

    Boundaries:
        - Focus: algorithm bullet 3 and ruling G2 (typed UNSUPPORTED reasons)
        - Fixtures/params: tmp_path, target, fragment (parametrized, 6 cases)

    On failure, first check:
        - Whether the resolver still tags drive/unc/backslash reasons distinctly
        - Whether an encoded backslash decodes before the backslash guard runs
    """
    findings = pb.check_text(f"[x]({target})\n", "README.md", tmp_path)

    assert len(findings) == 1
    assert fragment in findings[0].message


def test_windows_policy_off_suppresses_windows_targets(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies windows_path_policy off suppresses drive/UNC/backslash.

    Scenario:
        Given drive, UNC, and backslash targets
        When check_text runs with ``windows_path_policy = "off"``
        Then none are reported (lexical escapes and control bytes remain the other rules' concern).

    Boundaries:
        - Focus: windows_path_policy gating only the Windows subcategories
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _classify still honors windows_path_policy == "off" for the Windows reasons
    """
    settings = Config(windows_path_policy="off")
    text = "[a](C:/x)\n[b](\\\\server\\share)\n[c](d\\e)\n"

    assert pb.check_text(text, "README.md", tmp_path, settings) == ()


def test_control_byte_target_is_flagged_and_escaped_in_message(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies a control byte is flagged and repr-escaped.

    Scenario:
        Given a link target carrying a NUL and an ESC byte
        When check_text classifies and builds the message
        Then a control-character finding is produced whose message contains no raw control byte.

    Boundaries:
        - Focus: control-byte detection plus the log-injection escaping safeguard
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _echo still unicode-escapes control bytes before the message is built
    """
    findings = pb.check_text("[x](a\x00b\x1bc.md)\n", "README.md", tmp_path)

    assert len(findings) == 1
    message = findings[0].message
    assert "control characters" in message
    assert "\x00" not in message and "\x1b" not in message
    assert "\\x00" in message and "\\x1b" in message


@pytest.mark.parametrize(
    "target",
    (
        "https://example.com/page",
        "mailto:nobody@example.invalid",
        "//host/share",
        "file:///etc/passwd",
        "{placeholder}.md",
        "docs/*.md",
        "query.md?a=../../b",
        "/etc/passwd",
        "/docs/guide.md",
        "~/secret.md",
        "$HOME/x.md",
        "\uff0e\uff0e/x.md",
        "a/../b.md",
        "../guide.md#intro",
    ),
)
def test_safe_targets_are_not_flagged(tmp_path: Path, target: str):
    """
    [Unit] detectors path_boundaries: verifies safe and in-root targets produce no finding.

    Scenario:
        Given external URLs, protocol-relative and file-scheme URLs, templates, globs, a query
            string hiding ``..``, absolute POSIX and root-relative paths (ruling G3), tilde and
            env-var literals, fullwidth-dot confusables, an oscillation that collapses in-root, and
            a fragment-bearing in-root parent link
        When check_text classifies each
        Then none is reported, matching the documented false-positive safeguards.

    Boundaries:
        - Focus: exclusions and rulings G3 (absolute POSIX reinterpreted root-relative is clean)
        - Fixtures/params: tmp_path, target (parametrized, 14 cases)

    On failure, first check:
        - Whether the resolver classification for the target drifted
        - Whether a confusable was wrongly folded into the ASCII parent token
    """
    assert pb.check_text(f"[x]({target})\n", "docs/README.md", tmp_path) == ()


def test_image_html_tag_and_reference_definition_targets_are_validated(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies image, HTML img, and reference-definition targets.

    Scenario:
        Given a Markdown image, an HTML ``<img>`` tag, and a reference definition all escaping root
        When check_text scans the document
        Then each contributes exactly one DS116 finding at its own line.

    Boundaries:
        - Focus: algorithm bullet 5 (validate images and reference definitions via the resolver)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the detector still gathers images, html images, and reference_definitions
        - Whether reference-definition targets drop a trailing title via _first_token
    """
    text = '![alt](../../a.png)\n<img src="../../b.png">\n[ref]: ../../c.md "title"\n'

    findings = pb.check_text(text, "docs/README.md", tmp_path)

    assert _messages(findings) == [
        "reference escapes the documentation root: ../../a.png",
        "reference escapes the documentation root: ../../b.png",
        "reference escapes the documentation root: ../../c.md",
    ]
    assert [finding.line for finding in findings] == [1, 2, 3]


def test_path_like_code_span_is_validated(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies an explicit path-like code span is validated.

    Scenario:
        Given a path-like inline code span that escapes root and a non-path code span
        When check_text scans the document
        Then only the path-like escaping span is reported.

    Boundaries:
        - Focus: algorithm bullet 5 (path-like code spans) and _looks_path_like shape rules
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _looks_path_like still requires a separator or extension and excludes versions
    """
    findings = pb.check_text("See `../../etc/passwd` and `plainword`.\n", "docs/README.md", tmp_path)

    assert _messages(findings) == ["reference escapes the documentation root: ../../etc/passwd"]


#: Documentation-only inline spans: Windows-path literals and regex/escape snippets that must never
#: be DS116 findings when written as code spans (Story 11.0 code-span ruling).
_DOC_CODE_SPANS = (
    r"C:\Windows\win.ini",
    r"\\server\share",
    r"\Windows\x",
    r"\n",
    r"\|",
    r"\b\w+\b",
    r"DS\d{3}",
    r"^DS\d*$",
)


@pytest.mark.parametrize("span", _DOC_CODE_SPANS)
def test_documentation_code_spans_are_not_flagged(tmp_path: Path, span: str):
    """
    [Unit] detectors path_boundaries: verifies drive/UNC/backslash/regex code spans are not findings.

    Scenario:
        Given a Windows drive/UNC/backslash literal or a regex/escape snippet inside an inline code span
        When check_text classifies it
        Then DS116 emits nothing: a code span reports only genuine traversal, never these documented
            literals (regex/escape spans are not path-like at all, and Windows categories are exempt).

    Boundaries:
        - Focus: Story 11.0 code-span ruling (narrowed code-span scope)
        - Fixtures/params: tmp_path, span (parametrized, 8 cases)

    On failure, first check:
        - Whether _looks_path_like started treating a backslash as a path signal again
        - Whether _CODE_SPAN_EXEMPT_REASONS stopped suppressing drive/unc/backslash/control spans
    """
    assert pb.check_text(f"See `{span}` here.\n", "docs/README.md", tmp_path) == ()


@pytest.mark.parametrize(
    ("target", "fragment"),
    (
        (r"C:\Windows\win.ini", "Windows drive-letter"),
        (r"\\server\share", "UNC network"),
        (r"\Windows\x", "backslash path separators"),
    ),
)
def test_same_windows_strings_as_links_images_and_definitions_are_flagged(tmp_path: Path, target: str, fragment: str):
    """
    [Unit] detectors path_boundaries: verifies the same Windows strings ARE findings as references.

    Scenario:
        Given a Windows drive/UNC/backslash target written as a link, an HTML image, and a reference
            definition (the categories DS116 checks at full strictness)
        When check_text scans each
        Then every one is a DS116 finding, proving the exemption is scoped to inline code spans only.

    Boundaries:
        - Focus: full-strictness reference categories versus the exempt code-span category
        - Fixtures/params: tmp_path, target, fragment (parametrized, 3 cases)

    On failure, first check:
        - Whether the code-span exemption leaked into the link/image/reference-definition path
    """
    link = pb.check_text(f"[x]({target})\n", "docs/README.md", tmp_path)
    image = pb.check_text(f'<img src="{target}">\n', "docs/README.md", tmp_path)
    definition = pb.check_text(f"[r]: {target}\n", "docs/README.md", tmp_path)

    assert len(link) == 1 and fragment in link[0].message
    assert len(image) == 1 and fragment in image[0].message
    assert len(definition) == 1 and fragment in definition[0].message


def test_in_root_symlink_out_code_span_is_flagged(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies a code span through an in-root symlink-out IS a finding.

    Scenario:
        Given an in-root symlink whose target is above the root, referenced by a path-like code span
        When check_text classifies the span
        Then DS116 reports it: symlink-out is one of the two genuine-traversal categories a code span
            still covers, alongside lexical root escape.

    Boundaries:
        - Focus: the code-span scope keeps symlink-out (ruling G4) while dropping Windows categories
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether escapes_via_symlink is still consulted for a lexically in-root code-span target
    """
    root = tmp_path / "root"
    (root / "docs").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.md").write_text("secret\n", encoding="utf-8")
    try:
        (root / "docs" / "escape.md").symlink_to("../../outside/secret.md")
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"symlinks unavailable: {error}")

    findings = pb.check_text("See `escape.md` for details.\n", "docs/README.md", root)

    assert len(findings) == 1
    assert "symlink that escapes the documentation root" in findings[0].message


def test_targets_inside_fences_and_comments_are_skipped(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies fenced and commented references are treated as examples.

    Scenario:
        Given escaping links inside a fenced code block and inside an HTML comment, plus one live link
        When check_text scans the document
        Then only the live link is reported.

    Boundaries:
        - Focus: skipping example content in fences and comments
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the shared scanner still masks fenced content
        - Whether _comment_filter still drops tokens whose offset falls inside a comment
    """
    text = "```\n[fenced](../../a.md)\n```\n<!-- [commented](../../b.md) -->\n[live](../../c.md)\n"

    findings = pb.check_text(text, "docs/README.md", tmp_path)

    assert _messages(findings) == ["reference escapes the documentation root: ../../c.md"]
    assert findings[0].line == 5


def test_findings_are_ordered_by_source_and_deduplicated(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies stable source ordering and duplicate collapsing.

    Scenario:
        Given two identical escaping links on one line and a distinct escaping link on the next
        When check_text scans the document
        Then the identical pair collapses to one finding and the two findings are in source order.

    Boundaries:
        - Focus: one finding per offending reference, stable order, no duplicate (line, message)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the (line, message) de-duplication set is still applied
        - Whether candidates are still sorted by source offset
    """
    text = "[a](../../x.md) and [b](../../x.md)\n[c](../../y.md)\n"

    findings = pb.check_text(text, "docs/README.md", tmp_path)

    assert _messages(findings) == [
        "reference escapes the documentation root: ../../x.md",
        "reference escapes the documentation root: ../../y.md",
    ]
    assert [finding.line for finding in findings] == [1, 2]


def test_message_echo_is_bounded_and_escaped(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies the echoed raw target is length-bounded.

    Scenario:
        Given an escaping link whose target is far longer than the echo bound
        When check_text builds the message
        Then the echoed raw target is truncated with an ellipsis and never the resolved path.

    Boundaries:
        - Focus: bounded, repr-escaped echo (information-disclosure safeguard)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _echo still truncates at _MAX_ECHO characters and appends an ellipsis
    """
    target = "../../" + "a" * 10_000 + ".md"
    findings = pb.check_text(f"[x]({target})\n", "docs/README.md", tmp_path)

    assert len(findings) == 1
    message = findings[0].message
    assert message.endswith("...")
    assert len(message) < 200
    assert str(tmp_path) not in message


def test_root_escape_policy_off_and_warn(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies root_escape_policy off is silent and warn lowers severity.

    Scenario:
        Given an escaping link
        When check_text runs with ``root_escape_policy`` off and then warn
        Then off yields nothing and warn yields a warning-severity finding (the rule default stays error).

    Boundaries:
        - Focus: the root_escape_policy option (off/warn/error)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether check_text short-circuits on off and maps warn to severity "warning"
    """
    text = "[x](../a.md)\n"

    assert pb.check_text(text, "README.md", tmp_path, Config(root_escape_policy="off")) == ()

    warned = pb.check_text(text, "README.md", tmp_path, Config(root_escape_policy="warn"))
    assert len(warned) == 1
    assert warned[0].severity == "warning"
    assert pb.DS116.severity == "error"


def test_decode_percent_paths_false_keeps_encoded_literal_but_catches_raw(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies decode_percent_paths=false disables decoding only.

    Scenario:
        Given an encoded escape and a raw ``../`` escape
        When check_text runs with ``decode_percent_paths = false``
        Then the encoded form is treated as a literal in-root filename (clean) while the raw escape
            is still reported.

    Boundaries:
        - Focus: the decode_percent_paths option
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether the ``%``-neutralising probe still suppresses the resolver's single decode
    """
    settings = Config(decode_percent_paths=False)

    assert pb.check_text("[x](%2e%2e/%2e%2e/a.md)\n", "docs/README.md", tmp_path, settings) == ()

    raw = pb.check_text("[x](../../a.md)\n", "docs/README.md", tmp_path, settings)
    assert len(raw) == 1


def test_subdirectory_root_is_the_boundary_not_the_repository(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies the scan root (not the repo) is the containment boundary.

    Scenario:
        Given a document under a subdirectory scan root whose link climbs above that subdir
            but would still be inside an enclosing repository
        When check_text runs against the subdirectory root
        Then the climb above the scan root is a finding.

    Boundaries:
        - Focus: subdir-root containment (threat model MEDIUM scan-root subtlety)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether containment is compared against the configured scan root only
    """
    sub_root = tmp_path / "scan-root"
    sub_root.mkdir()

    findings = pb.check_text("[x](../outside.md)\n", "README.md", sub_root)

    assert len(findings) == 1


def test_detect_skips_non_markdown_and_canonicalizes_root_once(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies detect reads only Markdown and uses a canonical root.

    Scenario:
        Given a Markdown document with an escaping link and a non-Markdown companion
        When detect scans the supplied documents
        Then only the Markdown document is read and its escape is reported once.

    Boundaries:
        - Focus: detect document selection and single root canonicalization
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether detect still filters on the .md suffix and realpaths the root once
    """
    (tmp_path / "README.md").write_text("[x](../a.md)\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("[x](../a.md)\n", encoding="utf-8")
    documents = (models.Document("README.md", 0), models.Document("notes.txt", 0))

    findings = pb.detect(tmp_path, documents)

    assert len(findings) == 1
    assert findings[0].path == "README.md"


def test_detect_propagates_unreadable_document(tmp_path: Path):
    """
    [Unit] detectors path_boundaries: verifies an invalid-UTF-8 document surfaces its read error.

    Scenario:
        Given a Markdown document whose bytes are not valid UTF-8
        When detect reads it
        Then the decode error propagates rather than being silently treated as clean.

    Boundaries:
        - Focus: explicit handling of unreadable input (no false clean signal)
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _read_text still opens documents as strict UTF-8
    """
    (tmp_path / "README.md").write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        pb.detect(tmp_path, (models.Document("README.md", 1),))
