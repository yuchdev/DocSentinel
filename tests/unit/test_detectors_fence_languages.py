"""Unit tests for DS110 fence-language-policy recognition.

These tests use tiny inline Markdown strings and call the detector's pure
recognition helpers directly with ``check_text(text, path, config)``. Detection
over committed Markdown assets is the job of the Story 07.0 Task 03 integration
suite, which runs once ``DS110`` is registered together with its
``tests/assets/ds110/*`` fixtures (Task 02). ``DS110`` is intentionally *not*
registered yet, so this module exercises the detector in isolation.
"""

from pathlib import Path

import pytest

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.detectors import fence_languages

_ENABLED = Config(require_fence_languages=True)


def _codes(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the rule code of each finding in order."""
    return [finding.rule for finding in findings]


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors fence_languages: verifies DS110 metadata and its registration.

    Scenario:
        Given the DS110 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact and the rule is registered with its analyzer wired.

    Boundaries:
        - Focus: rule metadata and the fixture-gated registration
        - Fixtures/params: none

    On failure, first check:
        - Whether a metadata field (profile, severity, title) drifted
        - Whether the register_rule / ANALYZERS wiring was removed
    """
    assert fence_languages.DS110.code == "DS110"
    assert fence_languages.DS110.profile == "fast"
    assert fence_languages.DS110.severity == "warning"
    assert fence_languages.DS110.title == "Missing language labels on code fences"
    # Registration (and the ANALYZERS wiring) land with the committed Task 02 fixtures.
    assert rules.RULES["DS110"] is fence_languages.DS110
    assert rules.ANALYZERS["DS110"] is fence_languages.detect


def test_policy_off_by_default_is_not_applicable():
    """
    [Unit] detectors fence_languages: verifies the policy is off without opt-in.

    Scenario:
        Given a nonempty unlabelled fence and the default configuration
        When DS110 recognition runs with require_fence_languages false
        Then no finding is produced because the optional policy is not applicable.

    Boundaries:
        - Focus: disabled optional policy never masquerades as an evaluated clean result
        - Fixtures/params: default Config (require_fence_languages=False)

    On failure, first check:
        - The require_fence_languages gate at the top of check_text
        - That the same text does flag once the policy is enabled
    """
    assert fence_languages.check_text("```\ncode\n```\n", "README.md") == ()
    assert len(fence_languages.check_text("```\ncode\n```\n", "README.md", _ENABLED)) == 1


def test_labelled_fence_is_clean():
    """
    [Unit] detectors fence_languages: verifies a language-labelled fence is clean.

    Scenario:
        Given backtick and tilde fences labelled python, text and console
        When DS110 recognition runs under the enabled policy with no allowlist
        Then none of them is flagged.

    Boundaries:
        - Focus: the normal labelled-fence case across markers and ordinary labels
        - Fixtures/params: inline strings, enabled Config

    On failure, first check:
        - The first-token language extraction in _fence_language
        - That text/console are treated as ordinary labels without an allowlist
    """
    assert fence_languages.check_text("```python\ncode\n```\n", "README.md", _ENABLED) == ()
    assert fence_languages.check_text("```text\nhi\n```\n", "README.md", _ENABLED) == ()
    assert fence_languages.check_text("~~~console\n$ ls\n~~~\n", "README.md", _ENABLED) == ()


def test_nonempty_unlabelled_fence_is_flagged_at_opener_line():
    """
    [Unit] detectors fence_languages: verifies a meaningful unlabelled fence is flagged.

    Scenario:
        Given an unlabelled backtick fence with code opening on line 2
        When DS110 recognition runs under the enabled policy
        Then one warning finding is produced at the opener line with the right path.

    Boundaries:
        - Focus: the primary finding case and line/path/severity fidelity
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - The empty-language branch in _fence_finding
        - The opener line carried onto the finding
    """
    findings = fence_languages.check_text("intro\n```\ncode\n```\n", "README.md", _ENABLED)
    assert len(findings) == 1
    assert findings[0].rule == "DS110"
    assert findings[0].severity == "warning"
    assert findings[0].line == 2
    assert findings[0].path == "README.md"
    assert "language label" in findings[0].message


def test_whitespace_only_info_string_counts_as_absent():
    """
    [Unit] detectors fence_languages: verifies a whitespace-only info string is no language.

    Scenario:
        Given a fence whose opener is followed only by trailing spaces
        When DS110 recognition runs under the enabled policy
        Then the fence is treated as unlabelled and flagged once.

    Boundaries:
        - Focus: whitespace-only info string normalization (treated as absent)
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - That the shared scanner trims the info string
        - The empty-token result of _fence_language on blank input
    """
    findings = fence_languages.check_text("```   \ncode\n```\n", "README.md", _ENABLED)
    assert len(findings) == 1
    assert findings[0].line == 1


def test_unlabelled_tilde_fence_is_flagged():
    """
    [Unit] detectors fence_languages: verifies an unlabelled tilde fence is flagged.

    Scenario:
        Given an unlabelled tilde fence with meaningful content
        When DS110 recognition runs under the enabled policy
        Then one finding is produced.

    Boundaries:
        - Focus: marker independence (tilde fences are checked like backticks)
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - That the detector does not special-case the backtick marker
        - The body_nonempty predicate on the tilde fence
    """
    findings = fence_languages.check_text("~~~\ncode\n~~~\n", "README.md", _ENABLED)
    assert _codes(findings) == ["DS110"]


def test_empty_fence_is_exempt_by_default_but_flagged_when_strict():
    """
    [Unit] detectors fence_languages: verifies the empty-fence exemption toggles.

    Scenario:
        Given an empty, closed, unlabelled fence
        When DS110 recognition runs with allow_unlabelled_empty_fences true then false
        Then it is clean under the default exemption and flagged once the exemption is off.

    Boundaries:
        - Focus: the allow_unlabelled_empty_fences exemption for demonstration fences
        - Fixtures/params: inline string, two enabled Configs

    On failure, first check:
        - The body_nonempty guard in the empty-language branch
        - That the strict policy still points at the opener line
    """
    text = "```\n```\n"
    assert fence_languages.check_text(text, "README.md", _ENABLED) == ()
    strict = Config(require_fence_languages=True, allow_unlabelled_empty_fences=False)
    findings = fence_languages.check_text(text, "README.md", strict)
    assert len(findings) == 1
    assert findings[0].line == 1


def test_language_with_trailing_attributes_is_recognized_as_labelled():
    """
    [Unit] detectors fence_languages: verifies a language with trailing attributes is labelled.

    Scenario:
        Given fences whose info string is a language followed by attributes
        When DS110 recognition runs under the enabled policy with no allowlist
        Then they are treated as labelled and not flagged.

    Boundaries:
        - Focus: first-token language extraction ignoring trailing attributes
        - Fixtures/params: inline strings, enabled Config

    On failure, first check:
        - The maxsplit=1 split in _fence_language
        - That attribute text after the first token does not become the language
    """
    assert fence_languages.check_text('```python title="example"\ncode\n```\n', "README.md", _ENABLED) == ()
    assert fence_languages.check_text("~~~python {.line-numbers}\ncode\n~~~\n", "README.md", _ENABLED) == ()


def test_attribute_block_without_whitespace_is_part_of_the_language_token():
    """
    [Unit] detectors fence_languages: pins the no-whitespace attribute-block limitation.

    Scenario:
        Given a fence ``` ```python{.x} ``` whose attribute block is NOT separated from the language
        by whitespace
        When DS110 recognition runs with no allowlist and then with an allowlist of ["python"]
        Then the first whitespace-delimited token is the whole ``python{.x}`` string: with no
        allowlist it still counts as labelled (no finding), but under ``["python"]`` the token
        ``python{.x}`` does not equal ``python`` and is flagged, its message echoing ``python{.x}``.

    Boundaries:
        - Focus: a deliberate gfm-subset limitation - the info string is split only on whitespace, so
          an attribute block glued to the language (no space) is part of the language token. Separating
          the attributes with a space (covered above) is the supported form.
        - Fixtures/params: inline strings, enabled Config with and without an allowlist

    On failure, first check:
        - The whitespace-only split in _fence_language (it does not parse ``{...}`` attribute blocks)
        - Whether the allowlist comparison began stripping an attached attribute block
    """
    # No allowlist: any non-empty first token counts as a label, so the glued attribute block is fine.
    assert fence_languages.check_text("```python{.x}\ncode\n```\n", "README.md", _ENABLED) == ()

    # With an allowlist, the token is literally "python{.x}", which is not the allow-listed "python".
    config = Config(require_fence_languages=True, allowed_fence_languages=("python",))
    flagged = fence_languages.check_text("```python{.x}\ncode\n```\n", "README.md", config)
    assert len(flagged) == 1
    assert "python{.x}" in flagged[0].message
    assert "allowlist" in flagged[0].message


def test_allowlist_rejects_unknown_language_and_accepts_known():
    """
    [Unit] detectors fence_languages: verifies a non-empty allowlist gates languages.

    Scenario:
        Given an allowlist of ["python"] and fences labelled mermaid and python
        When DS110 recognition runs under the enabled policy
        Then the mermaid fence is flagged for its language and the python fence is clean.

    Boundaries:
        - Focus: allowlist membership (unknown language finding; known language clean)
        - Fixtures/params: inline strings, enabled Config with an allowlist

    On failure, first check:
        - The non-empty-allowlist branch in _fence_finding
        - That the unknown-language message echoes the offending language
    """
    config = Config(require_fence_languages=True, allowed_fence_languages=("python",))
    unknown = fence_languages.check_text("```mermaid\ngraph TD\n```\n", "README.md", config)
    assert len(unknown) == 1
    assert "mermaid" in unknown[0].message
    assert "allowlist" in unknown[0].message
    assert fence_languages.check_text("```python\ncode\n```\n", "README.md", config) == ()


def test_unclosed_fence_is_owned_by_ds109_not_double_reported():
    """
    [Unit] detectors fence_languages: verifies an unclosed fence yields no DS110 finding.

    Scenario:
        Given an unlabelled fence that is never closed before end of file
        When DS110 recognition runs under the enabled policy
        Then no finding is produced because DS109 owns the delimiter problem.

    Boundaries:
        - Focus: cross-rule ownership (no cascade from one malformed fence)
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - The not-closed guard in _is_ds109_owned
        - That a closed sibling fence would still be evaluated
    """
    assert fence_languages.check_text("```\ncode\nmore\n", "README.md", _ENABLED) == ()


def test_malformed_backtick_info_is_owned_by_ds109():
    """
    [Unit] detectors fence_languages: verifies a backtick-in-info fence is left to DS109.

    Scenario:
        Given a closed backtick fence whose info string contains a backtick
        When DS110 recognition runs under the enabled policy
        Then no finding is produced because DS109 reports that malformed opener.

    Boundaries:
        - Focus: cross-rule ownership for a closed-but-malformed backtick opener
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - The backtick-in-info branch of _is_ds109_owned
        - That a tilde fence with tildes in its info is still evaluated normally
    """
    assert fence_languages.check_text("```py`thon\ncode\n```\n", "README.md", _ENABLED) == ()


def test_multiple_unlabelled_blocks_yield_one_finding_each():
    """
    [Unit] detectors fence_languages: verifies distinct unlabelled blocks each flag once.

    Scenario:
        Given two separate unlabelled fenced blocks in one document
        When DS110 recognition runs under the enabled policy
        Then exactly two findings are produced, one per block, in source order.

    Boundaries:
        - Focus: per-fence finding count and source ordering
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - That the detector iterates every fence token independently
        - The opener lines of the two reported fences
    """
    findings = fence_languages.check_text("```\none\n```\n\n```\ntwo\n```\n", "README.md", _ENABLED)
    assert _codes(findings) == ["DS110", "DS110"]
    assert [finding.line for finding in findings] == [1, 5]


def test_unsupported_dialect_emits_no_confident_diagnostics():
    """
    [Unit] detectors fence_languages: verifies an unsupported dialect yields no findings.

    Scenario:
        Given an enabled policy whose fence_dialect is not the supported gfm-subset
        When DS110 recognition runs over text that would otherwise flag
        Then no finding is produced rather than a confident false diagnostic.

    Boundaries:
        - Focus: dialect gating (DS110 reuses DS109's fence tokens)
        - Fixtures/params: Config constructed directly to bypass TOML validation

    On failure, first check:
        - The fence_dialect guard in check_text
        - That the default gfm-subset path still flags the same input
    """
    unsupported = Config(require_fence_languages=True, fence_dialect="other-dialect")
    assert fence_languages.check_text("```\ncode\n```\n", "README.md", unsupported) == ()
    assert len(fence_languages.check_text("```\ncode\n```\n", "README.md", _ENABLED)) == 1


def test_long_language_echo_is_truncated_and_repr_safe():
    """
    [Unit] detectors fence_languages: verifies a long language echo is bounded.

    Scenario:
        Given an allowlist that omits a pathologically long language token
        When DS110 recognition runs under the enabled policy
        Then the unknown-language message truncates the echoed token and keeps repr escaping.

    Boundaries:
        - Focus: message size bound and repr-safe echo of untrusted info-string text
        - Fixtures/params: inline string with a 500-character language, enabled Config

    On failure, first check:
        - The _MAX_LANGUAGE_ECHO truncation in _echo
        - That the !r conversion is retained on the echoed language
    """
    language = "x" * 500
    config = Config(require_fence_languages=True, allowed_fence_languages=("python",))
    findings = fence_languages.check_text(f"```{language}\ncode\n```\n", "README.md", config)
    assert len(findings) == 1
    assert len(findings[0].message) < len(language)
    assert "..." in findings[0].message


def test_detect_reads_documents_and_skips_non_markdown(tmp_path: Path):
    """
    [Unit] detectors fence_languages: verifies detect reads .md files and ignores others.

    Scenario:
        Given a Markdown file with an unlabelled fence and a non-Markdown sibling
        When detect runs over both documents under the enabled policy
        Then only the Markdown file contributes a single DS110 finding.

    Boundaries:
        - Focus: document reading, .md filtering, and path propagation in detect
        - Fixtures/params: tmp_path with two committed files, enabled Config

    On failure, first check:
        - The .md suffix filter in detect
        - That the finding path matches the Markdown document path
    """
    (tmp_path / "README.md").write_text("```\ncode\n```\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("```\ncode\n```\n", encoding="utf-8")
    documents = (models.Document("README.md", 1), models.Document("notes.txt", 1))
    findings = fence_languages.detect(tmp_path, documents, _ENABLED)
    assert len(findings) == 1
    assert findings[0].path == "README.md"


def test_detect_surfaces_invalid_utf8_rather_than_false_clean(tmp_path: Path):
    """
    [Unit] detectors fence_languages: verifies invalid UTF-8 raises instead of passing silently.

    Scenario:
        Given a Markdown document containing invalid UTF-8 bytes
        When detect attempts to read it under the enabled policy
        Then a UnicodeDecodeError propagates rather than a false clean result.

    Boundaries:
        - Focus: explicit handling of unreadable input (no silent clean signal)
        - Fixtures/params: tmp_path file with invalid bytes, enabled Config

    On failure, first check:
        - The UTF-8 read in _read_text
        - That unreadable input is never reported as zero findings
    """
    (tmp_path / "README.md").write_bytes(b"```\n\xff\xfe\n```\n")
    with pytest.raises(UnicodeDecodeError):
        fence_languages.detect(tmp_path, (models.Document("README.md", 1),), _ENABLED)


def test_repeated_recognition_is_deterministic():
    """
    [Unit] detectors fence_languages: verifies repeated scans produce identical findings.

    Scenario:
        Given the same Markdown text scanned twice under the enabled policy
        When DS110 recognition runs on each pass
        Then the two finding tuples are equal.

    Boundaries:
        - Focus: determinism and absence of shared mutable state
        - Fixtures/params: inline string, enabled Config

    On failure, first check:
        - Any module-level mutable caches
        - Ordering stability of the shared scanner's fence list
    """
    text = "```\none\n```\n```python\ntwo\n```\n```\nthree\n```\n"
    first = fence_languages.check_text(text, "README.md", _ENABLED)
    assert first == fence_languages.check_text(text, "README.md", _ENABLED)
    assert _codes(first) == ["DS110", "DS110"]
