"""Unit tests for DS118 documentation file and directory naming policy.

These tests use tiny inline path strings and call the detector's pure cores directly:
:func:`~docsentinel.detectors.naming.check_paths` (the corpus policy core),
:func:`~docsentinel.detectors.naming._glob_matches` (the restricted glob matcher) and
:func:`~docsentinel.detectors.naming._suggest_component` (the deterministic rename
suggester). Detection over committed Markdown assets is the job of the Story 14.0
Task 03 integration suite, which runs once ``DS118`` is registered with its
``tests/assets/ds118/*`` fixtures in Task 02; this module exercises the pure cores in
isolation and pins the deliberately-unregistered Task 01 state.

Every algorithm bullet, exemption, and exclusion of Story 14.0 Task 01 has a test
here, plus the hostile-name echo (``ESC``/newline/``::error``/RTL-override/``NUL``),
the fail-closed defences for an injected :class:`~docsentinel.config.Config` (an invalid
style, out-of-bounds prefix patterns), the opt-in gate, and doubling floods that pin
the linear cost of many documents, very long paths, deep nesting, a shared offending
directory prefix, and a large allowlist crossed with many documents (with a naive
list-membership reference proving the shared workload would be quadratic).

No filesystem test lives here: DS118 performs zero filesystem access, which the mock
recorder in ``tests/mock/test_detectors_documentation_naming_oracle.py`` proves against
a fabricated corpus with every filesystem entry point armed to raise.
"""

from __future__ import annotations

import pytest

from docsentinel import models, rules
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import naming
from tests.timing_helpers import assert_scales_linearly, measure_scaling


def _messages(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the message of each finding in order.

    :param findings: The findings to describe.
    :returns: The ordered finding messages.
    """
    return [finding.message for finding in findings]


def _run(paths: tuple[str, ...], **options: object) -> tuple[models.Finding, ...]:
    """Run the DS118 policy core over ``paths`` with the given config overrides.

    :param paths: The relative document paths under test.
    :param options: Keyword overrides for :class:`~docsentinel.config.Config`.
    :returns: The findings produced by :func:`~docsentinel.detectors.naming.check_paths`.
    """
    return naming.check_paths(paths, Config(**options))


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors naming: verifies DS118 metadata and its Task 02 registration state.

    Scenario:
        Given the Story 14.0 detector module after Task 02 wiring
        When its rule metadata is inspected
        Then DS118 is a fast, warning-severity opt-in rule gated on documentation_naming, and it is
            registered once in the engine's RULES and ANALYZERS registries.

    Boundaries:
        - Focus: exact rule identity plus the registered Task 02 contract the catalog gate relies on
        - Fixtures/params: none

    On failure, first check:
        - Whether the module was wired via register_rule and ANALYZERS exactly once
    """
    assert naming.DS118.code == "DS118"
    assert naming.DS118.profile == "fast"
    assert naming.DS118.severity == "warning"
    assert naming.DS118.opt_in_option == "documentation_naming"
    assert rules.RULES["DS118"] is naming.DS118
    assert rules.ANALYZERS["DS118"] is naming.detect


def test_disabled_style_is_inert():
    """
    [Unit] detectors naming: verifies the default off style produces no findings and no work.

    Scenario:
        Given a path that would violate every enabled style
        When the policy runs with documentation_naming off (the default)
        Then no findings are produced.

    Boundaries:
        - Focus: the opt-in gate; off is inert
        - Fixtures/params: none

    On failure, first check:
        - Whether check_paths short-circuits before building a policy when the style is off
    """
    assert _run(("docs/Getting Started.md",)) == ()
    assert _run(("docs/Getting Started.md",), documentation_naming="off") == ()


def test_kebab_clean_paths_pass():
    """
    [Unit] detectors naming: verifies conformant kebab paths and canonical exemptions pass.

    Scenario:
        Given kebab-case paths plus the canonical README.md and index.md names
        When the kebab policy runs
        Then no findings are produced.

    Boundaries:
        - Focus: algorithm bullet 2 (conformant components) and bullet 3 (README/index exemption)
        - Fixtures/params: none

    On failure, first check:
        - The conformance pattern or the default documentation_naming_allow exemptions
    """
    assert _run(("README.md", "docs/getting-started.md"), documentation_naming="kebab") == ()
    assert _run(("README.md", "docs/index.md"), documentation_naming="kebab") == ()
    assert _run(("docs/user-guides/advanced-setup.md",), documentation_naming="kebab") == ()


def test_uppercase_filename_is_flagged_with_suggestion():
    """
    [Unit] detectors naming: verifies an uppercase/camelCase filename is flagged with a kebab suggestion.

    Scenario:
        Given a PascalCase filename under kebab
        When the policy runs
        Then exactly one warning is produced at line None naming the file and suggesting the kebab rename.

    Boundaries:
        - Focus: character-class violation and the camelCase rename suggestion
        - Fixtures/params: none

    On failure, first check:
        - _suggest_component camelCase word splitting
    """
    findings = _run(("docs/GettingStarted.md",), documentation_naming="kebab")
    assert len(findings) == 1
    assert findings[0].path == "docs/GettingStarted.md"
    assert findings[0].severity == "warning"
    assert findings[0].line is None
    assert "getting-started.md" in findings[0].message
    assert "kebab" in findings[0].message


def test_camelcase_filename_suggests_hyphenated_name():
    """
    [Unit] detectors naming: verifies apiClient.md is rejected with the suggested api-client.md.

    Scenario:
        Given a camelCase filename under kebab
        When the policy runs
        Then one finding suggests api-client.md.

    Boundaries:
        - Focus: the matrix camelcase_path_diagnostic suggestion
        - Fixtures/params: none

    On failure, first check:
        - camelCase boundary insertion in _suggest_component
    """
    findings = _run(("docs/apiClient.md",), documentation_naming="kebab")
    assert _messages(findings) == [
        'file name "apiClient.md" does not match the kebab naming policy; suggested rename "api-client.md"'
    ]


def test_spaces_in_filename_are_flagged():
    """
    [Unit] detectors naming: verifies a space in a filename is a violation with a rename suggestion.

    Scenario:
        Given a filename containing a space under kebab
        When the policy runs
        Then one finding suggests the space-free kebab rename.

    Boundaries:
        - Focus: space is outside the portable character class
        - Fixtures/params: none

    On failure, first check:
        - Whether the conformance pattern admitted the space
    """
    findings = _run(("docs/Quick Start.md",), documentation_naming="kebab")
    assert "quick-start.md" in findings[0].message


def test_wrong_separator_is_flagged_per_style():
    """
    [Unit] detectors naming: verifies each style rejects the other style's separator.

    Scenario:
        Given an underscore name under kebab and a hyphen name under snake
        When each policy runs
        Then each wrong separator is flagged and the suggestion uses the active separator.

    Boundaries:
        - Focus: kebab forbids underscore; snake forbids hyphen
        - Fixtures/params: none

    On failure, first check:
        - The per-separator conformance patterns and suggestion separator
    """
    kebab = _run(("docs/quick_start.md",), documentation_naming="kebab")
    assert "quick-start.md" in kebab[0].message
    snake = _run(("docs/quick-start.md",), documentation_naming="snake")
    assert "quick_start.md" in snake[0].message
    assert "snake" in snake[0].message


def test_uppercase_directory_is_flagged_while_file_is_exempt():
    """
    [Unit] detectors naming: verifies a bad directory is flagged though the file name is exempt.

    Scenario:
        Given Docs/README.md under kebab
        When the policy runs
        Then exactly one finding reports the directory Docs and README.md stays exempt.

    Boundaries:
        - Focus: directory checking plus the file allowlist exemption
        - Fixtures/params: none

    On failure, first check:
        - Whether the allowlist leaked to directory components
    """
    findings = _run(("Docs/README.md",), documentation_naming="kebab")
    assert _messages(findings) == [
        'directory name "Docs" does not match the kebab naming policy; suggested rename "docs"'
    ]


def test_multiple_bad_components_report_directory_then_file():
    """
    [Unit] detectors naming: verifies both a bad directory and a bad file are reported, outermost first.

    Scenario:
        Given BadDocs/Quick_Start.md under kebab
        When the policy runs
        Then two findings are produced in directory-then-file order with deterministic suggestions.

    Boundaries:
        - Focus: per-component reporting and deterministic ordering
        - Fixtures/params: none

    On failure, first check:
        - The component iteration order in _Policy.check_path
    """
    findings = _run(("BadDocs/Quick_Start.md",), documentation_naming="kebab")
    assert _messages(findings) == [
        'directory name "BadDocs" does not match the kebab naming policy; suggested rename "bad-docs"',
        'file name "Quick_Start.md" does not match the kebab naming policy; suggested rename "quick-start.md"',
    ]


def test_unicode_filename_is_flagged_and_echoed_escaped():
    """
    [Unit] detectors naming: verifies a non-ASCII filename is flagged, transliterated and escaped.

    Scenario:
        Given a filename with an accented Latin letter under kebab
        When the policy runs
        Then the non-ASCII name is a violation, the suggestion transliterates the accent to ASCII,
            and the echoed original is unicode_escape-ed (never a raw non-ASCII byte).

    Boundaries:
        - Focus: Unicode is outside portable ASCII; transliteration is deterministic; echo is escaped
        - Fixtures/params: none

    On failure, first check:
        - NFKD combining-mark stripping in _suggest_component and the _echo escaping
    """
    findings = _run(("docs/café-guide.md",), documentation_naming="kebab")
    message = findings[0].message
    assert "cafe-guide.md" in message
    assert "café" not in message
    assert "caf\\xe9-guide.md" in message


def test_default_allowlist_matches_filename_not_full_path():
    """
    [Unit] detectors naming: verifies allowlist entries exempt a filename anywhere in the tree.

    Scenario:
        Given a nested index.md and README.md under kebab
        When the policy runs with the default allowlist
        Then both canonical names are exempt regardless of their directory.

    Boundaries:
        - Focus: allowlist matches the basename
        - Fixtures/params: none

    On failure, first check:
        - Whether the allowlist is matched against the full path only
    """
    assert _run(("a/b/index.md", "c/README.md"), documentation_naming="kebab") == ()


def test_full_path_allowlist_entry_exempts_only_that_path():
    """
    [Unit] detectors naming: verifies a full-path allowlist entry exempts exactly that path.

    Scenario:
        Given an allowlist holding the full path docs/CHANGELOG.md
        When the policy runs over that path and a sibling
        Then only the listed path is exempt; the unlisted sibling is still flagged.

    Boundaries:
        - Focus: allowlist also matches a full relative path
        - Fixtures/params: none

    On failure, first check:
        - The relative_path membership check in _Policy.check_path
    """
    allow = ("README.md", "index.md", "docs/CHANGELOG.md")
    assert _run(("docs/CHANGELOG.md",), documentation_naming="kebab", documentation_naming_allow=allow) == ()
    sibling = _run(("docs/OTHER.md",), documentation_naming="kebab", documentation_naming_allow=allow)
    assert "other.md" in sibling[0].message


def test_prefix_pattern_exempts_matching_component():
    """
    [Unit] detectors naming: verifies a prefix glob pattern exempts a matching component.

    Scenario:
        Given a prefix pattern RFC* and a would-be-bad filename RFC0001.md
        When the kebab policy runs
        Then the matching component is exempt and produces no finding.

    Boundaries:
        - Focus: documentation_naming_prefix_patterns exemption (numeric ADR prefix use-case)
        - Fixtures/params: none

    On failure, first check:
        - _name_is_exempt consulting the prefix patterns
    """
    findings = _run(
        ("docs/RFC0001.md",),
        documentation_naming="kebab",
        documentation_naming_prefix_patterns=("RFC*",),
    )
    assert findings == ()


def test_directory_checking_can_be_disabled():
    """
    [Unit] detectors naming: verifies documentation_naming_directories false skips directory components.

    Scenario:
        Given a bad directory with a clean file under kebab
        When directory checking is disabled
        Then no findings are produced.

    Boundaries:
        - Focus: the documentation_naming_directories scope toggle
        - Fixtures/params: none

    On failure, first check:
        - The check_directories guard in _Policy.check_path
    """
    assert _run(("BadDir/good-name.md",), documentation_naming="kebab", documentation_naming_directories=False) == ()
    assert len(_run(("BadDir/good-name.md",), documentation_naming="kebab")) == 1


def test_repeated_directory_name_reports_once_per_document():
    """
    [Unit] detectors naming: verifies a directory name repeated within one path is reported once.

    Scenario:
        Given A/A/x.md under kebab
        When the policy runs
        Then the directory name A is reported exactly once for that document.

    Boundaries:
        - Focus: within-document de-duplication by component name
        - Fixtures/params: none

    On failure, first check:
        - The seen-set guard over directory names in _Policy.check_path
    """
    findings = _run(("A/A/x.md",), documentation_naming="kebab")
    assert _messages(findings) == ['directory name "A" does not match the kebab naming policy; suggested rename "a"']


def test_shared_offending_directory_reports_once_per_document():
    """
    [Unit] detectors naming: verifies a shared bad directory is reported for each document under it.

    Scenario:
        Given two clean-named files under one badly named directory
        When the policy runs
        Then each document is attributed its own directory finding (one per document).

    Boundaries:
        - Focus: the documented per-document reporting ruling for a shared offending directory
        - Fixtures/params: none

    On failure, first check:
        - Whether cross-document de-duplication dropped a document's finding
    """
    findings = _run(("BadDir/a.md", "BadDir/b.md"), documentation_naming="kebab")
    assert [finding.path for finding in findings] == ["BadDir/a.md", "BadDir/b.md"]
    assert all("BadDir" in finding.message for finding in findings)


@pytest.mark.parametrize(
    ("filename", "fragment"),
    [
        ("a.b.md", "a-b.md"),
        (".hidden.md", "hidden.md"),
        (".md", "document.md"),
        ("foo--bar.md", "foo-bar.md"),
        ("trailing-.md", "trailing.md"),
    ],
)
def test_pathological_filenames_are_flagged_with_safe_suggestions(filename: str, fragment: str):
    """
    [Unit] detectors naming: verifies dots, leading dots, empty stems and doubled separators are flagged.

    Scenario:
        Given a pathological filename (multiple extensions, leading dot, empty stem, doubled or trailing
            separator) under kebab
        When the policy runs
        Then it is flagged with a deterministic, non-empty, conformant suggested rename.

    Boundaries:
        - Focus: the hostile-name algorithm bullets (dots, multiple extensions, empty/leading-dot components)
        - Fixtures/params: parametrized filenames and expected suggestion fragments

    On failure, first check:
        - _split_extension and _suggest_component edge handling
    """
    findings = _run((filename,), documentation_naming="kebab")
    assert len(findings) == 1
    assert fragment in findings[0].message


def test_all_non_ascii_name_suggests_document_placeholder():
    """
    [Unit] detectors naming: verifies a name with no ASCII word yields the document placeholder suggestion.

    Scenario:
        Given an all-Cyrillic filename under kebab
        When the policy runs
        Then it is flagged, the suggestion is document.md (never empty and never a silent lowercasing of
            non-ASCII), and the original is echoed escaped.

    Boundaries:
        - Focus: the empty-suggestion fallback and the no-silent-non-ASCII-lowercasing rule
        - Fixtures/params: none

    On failure, first check:
        - The _EMPTY_SUGGESTION fallback in _suggest_component
    """
    findings = _run(("Привет.md",), documentation_naming="kebab")
    assert "document.md" in findings[0].message
    assert "Привет" not in findings[0].message


def test_hostile_component_bytes_are_bounded_and_escaped():
    """
    [Unit] detectors naming: verifies control, RTL and NUL bytes in a name are echoed escaped and bounded.

    Scenario:
        Given a filename carrying ESC, newline, NUL and an RTL override, plus a very long run
        When the kebab policy runs
        Then the echoed original contains no raw control/non-ASCII byte and is bounded, while the
            suggestion stays clean ASCII.

    Boundaries:
        - Focus: the bounded repr-escaped echo contract for hostile POSIX/injected names
        - Fixtures/params: none

    On failure, first check:
        - The _echo bound and unicode_escape encoding
    """
    hostile = "A\x1b\n\x00‮B" + ("z" * 200) + ".md"
    message = _run((hostile,), documentation_naming="kebab")[0].message
    assert "\x1b" not in message
    assert "\n" not in message
    assert "\x00" not in message
    assert "‮" not in message
    assert "\\x1b" in message
    assert "\\x00" in message
    assert "..." in message


def test_injected_invalid_style_fails_closed():
    """
    [Unit] detectors naming: verifies an injected Config with an invalid style raises ConfigError.

    Scenario:
        Given a hand-built Config whose documentation_naming is an unsupported style
        When the policy runs (bypassing load_config validation)
        Then a ConfigError is raised rather than silently degrading.

    Boundaries:
        - Focus: fail-closed defence against a Config injection
        - Fixtures/params: none

    On failure, first check:
        - The _VALID_STYLES guard in _Policy.__init__
    """
    with pytest.raises(ConfigError):
        _run(("docs/a.md",), documentation_naming="camel")


def test_injected_out_of_bound_prefix_patterns_fail_closed():
    """
    [Unit] detectors naming: verifies oversized prefix pattern count or length raises ConfigError.

    Scenario:
        Given an injected Config with more patterns than the cap, and one with an over-long pattern
        When the kebab policy runs
        Then each fails closed with a ConfigError.

    Boundaries:
        - Focus: bounded pattern count and length defence against a Config injection
        - Fixtures/params: none

    On failure, first check:
        - The _validated_patterns bounds
    """
    too_many = tuple(f"p{index}" for index in range(naming._MAX_PREFIX_PATTERNS + 1))
    with pytest.raises(ConfigError):
        _run(("a.md",), documentation_naming="kebab", documentation_naming_prefix_patterns=too_many)
    too_long = ("x" * (naming._MAX_PATTERN_LENGTH + 1),)
    with pytest.raises(ConfigError):
        _run(("a.md",), documentation_naming="kebab", documentation_naming_prefix_patterns=too_long)


@pytest.mark.parametrize(
    ("pattern", "text", "expected"),
    [
        ("????-*", "0001-fast-path", True),
        ("*-guide", "user-guide", True),
        ("a?c", "abc", True),
        ("a?c", "abdc", False),
        ("*", "anything", True),
        ("", "", True),
        ("", "x", False),
        ("abc", "abc", True),
        ("abc", "abcd", False),
    ],
)
def test_glob_subset_matches_are_linear_and_anchored(pattern: str, text: str, expected: bool):
    """
    [Unit] detectors naming: verifies the restricted glob subset matches literal, ? and * anchored.

    Scenario:
        Given patterns using only literals, ? and *
        When matched against whole components
        Then the two-pointer matcher returns the anchored whole-string result.

    Boundaries:
        - Focus: the no-regex restricted glob subset
        - Fixtures/params: parametrized (pattern, text, expected) triples

    On failure, first check:
        - The star-backtracking in _glob_matches
    """
    assert naming._glob_matches(pattern, text) is expected


def test_repeated_scans_are_stable():
    """
    [Unit] detectors naming: verifies repeated runs over the same corpus produce identical findings.

    Scenario:
        Given a mixed corpus of clean and offending paths
        When the policy runs twice
        Then the two finding tuples are identical (deterministic, memoisation-safe).

    Boundaries:
        - Focus: determinism across repeated scans and the per-component cache
        - Fixtures/params: none

    On failure, first check:
        - Whether the _Policy cache leaked state between documents
    """
    paths = ("README.md", "Docs/Getting Started.md", "docs/getting-started.md", "BadDir/apiClient.md")
    first = _run(paths, documentation_naming="kebab")
    second = _run(paths, documentation_naming="kebab")
    assert _messages(first) == _messages(second)
    assert [finding.path for finding in first] == [finding.path for finding in second]


def _bad_paths(size: int) -> tuple[str, ...]:
    """Build ``size`` distinct offending kebab paths, one bad file component each.

    :param size: The number of documents to build.
    :returns: The relative paths, each with an uppercase (offending) file stem.
    """
    return tuple(f"docs/File{index}.md" for index in range(size))


def test_scales_linearly_with_many_documents():
    """
    [Unit] detectors naming: verifies the policy cost is linear in the number of documents.

    Scenario:
        Given a doubling series of corpora up to 80000 offending documents
        When the kebab policy runs
        Then each document yields one finding and the per-doubling ratio and log-log slope stay linear.

    Boundaries:
        - Focus: linear cost over 10^4-10^5 paths
        - Fixtures/params: assert_scales_linearly over a doubling series

    On failure, first check:
        - Any accidental per-document work that scans all other documents
    """
    assert_scales_linearly(
        _bad_paths,
        lambda paths: naming.check_paths(paths, Config(documentation_naming="kebab")),
        sizes=(10000, 20000, 40000, 80000),
        expected_count=lambda size: size,
        label="ds118-many-documents",
    )


def _long_component_path(size: int) -> tuple[str, ...]:
    """Build one document whose file stem is a single offending component of length ``size``.

    :param size: The length of the offending stem.
    :returns: A one-element tuple holding the path.
    """
    return (f"docs/{'A' * size}.md",)


def test_scales_linearly_with_very_long_components():
    """
    [Unit] detectors naming: verifies cost is linear in the length of a single long component.

    Scenario:
        Given a single document whose stem grows to 160000 characters
        When the kebab policy runs
        Then it yields one finding and conformance plus suggestion cost stays linear in the length.

    Boundaries:
        - Focus: a very long path component
        - Fixtures/params: assert_scales_linearly over a doubling length series

    On failure, first check:
        - Catastrophic backtracking in the conformance pattern or quadratic suggestion building
    """
    assert_scales_linearly(
        _long_component_path,
        lambda paths: naming.check_paths(paths, Config(documentation_naming="kebab")),
        sizes=(20000, 40000, 80000, 160000),
        expected_count=1,
        label="ds118-long-component",
    )


def _deep_nested_path(size: int) -> tuple[str, ...]:
    """Build one document nested under ``size`` distinct offending directory components.

    :param size: The directory depth (number of distinct bad directory names).
    :returns: A one-element tuple holding the deeply nested path.
    """
    directories = "/".join(f"Dir{index}" for index in range(size))
    return (f"{directories}/file.md",)


def test_scales_linearly_with_deep_directory_nesting():
    """
    [Unit] detectors naming: verifies cost is linear in directory depth.

    Scenario:
        Given one document nested under a doubling number of distinct offending directories
        When the kebab policy runs
        Then each distinct directory yields one finding and cost stays linear in the depth.

    Boundaries:
        - Focus: deep directory nesting
        - Fixtures/params: assert_scales_linearly over a doubling depth series

    On failure, first check:
        - Any quadratic rescan of ancestor components per directory
    """
    assert_scales_linearly(
        _deep_nested_path,
        lambda paths: naming.check_paths(paths, Config(documentation_naming="kebab")),
        sizes=(2000, 4000, 8000, 16000),
        expected_count=lambda size: size,
        label="ds118-deep-nesting",
    )


def _shared_prefix_corpus(size: int) -> tuple[str, ...]:
    """Build ``size`` clean-named files under one shared, deeply offending directory prefix.

    The shared prefix is a fixed deep run of offending directory names, so a correct
    implementation memoises each prefix component once and the per-document cost is the
    attribution of the (already-evaluated) prefix finding.

    :param size: The number of documents sharing the prefix.
    :returns: The relative paths, all under the same offending prefix.
    """
    prefix = "/".join(f"Shared{index}" for index in range(8))
    return tuple(f"{prefix}/file-{index}.md" for index in range(size))


def test_scales_linearly_with_shared_offending_prefix():
    """
    [Unit] detectors naming: verifies a shared offending directory prefix stays linear via memoisation.

    Scenario:
        Given a doubling number of clean files all under one fixed, deeply offending directory prefix
        When the kebab policy runs
        Then each document is attributed the prefix's eight directory findings and total cost stays
            linear in the number of documents (the prefix is evaluated once, then served from cache).

    Boundaries:
        - Focus: the shared-prefix workload (the DS115 lesson); per-component memoisation
        - Fixtures/params: assert_scales_linearly over a doubling document series

    On failure, first check:
        - Whether the _Policy cache re-evaluates a shared directory per document
    """
    assert_scales_linearly(
        _shared_prefix_corpus,
        lambda paths: naming.check_paths(paths, Config(documentation_naming="kebab")),
        sizes=(10000, 20000, 40000, 80000),
        expected_count=lambda size: size * 8,
        label="ds118-shared-prefix",
    )


def _allowlist_workload(size: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Build ``size`` clean documents and a ``size``-entry allowlist that never matches them.

    :param size: The number of documents and allowlist entries.
    :returns: A ``(paths, allow_entries)`` pair; every allow entry is distinct from every
        document filename, so membership is always consulted and never short-circuits.
    """
    paths = tuple(f"docs/doc-{index}.md" for index in range(size))
    allow = tuple(f"allowed-{index}.md" for index in range(size))
    return paths, allow


def test_suggested_rename_is_bounded_and_stays_conformant_for_huge_components():
    """
    [Unit] detectors naming: verifies the suggested rename is length-bounded and still conformant.

    Scenario:
        Given an injected 10 000-character offending directory and a 10 000-character extension
        When DS118 computes the suggested rename for kebab style
        Then every suggestion is at most 80 characters (plus separators of the path), ASCII, free of
            path separators and never ends with a separator, so a truncated suggestion is still a valid name.

    Boundaries:
        - Focus: security-review LOW finding (unbounded suggestion text)
        - Fixtures/params: none

    On failure, first check:
        - The slice and rstrip in _suggest_component and the extension cap in _suggest_filename
    """
    huge_word = "Alpha" * 2_000
    suggestion = naming._suggest_component(huge_word + "_" + huge_word, "-")
    filename = naming._suggest_filename(huge_word + "." + "X" * 10_000, "-")

    assert 0 < len(suggestion) <= 80
    assert suggestion.isascii() and "/" not in suggestion and not suggestion.endswith("-")
    assert len(filename) <= 80 + 1 + 80
    assert filename.isascii() and "/" not in filename


def test_large_allowlist_crossed_with_many_documents_is_linear():
    """
    [Unit] detectors naming: verifies a large allowlist crossed with many documents stays linear.

    Scenario:
        Given a doubling series where both the document count and the allowlist size grow together
        When the kebab policy runs (allowlist membership consulted for every file)
        Then cost stays linear because allowlist membership is a frozenset O(1) lookup.

    Boundaries:
        - Focus: many allow entries x many documents must not be O(documents x allow)
        - Fixtures/params: assert_scales_linearly over a doubling series

    On failure, first check:
        - Whether the allowlist is stored as a set (O(1)) rather than a list/tuple (O(n)) membership
    """

    def build(size: int) -> tuple[str, ...]:
        """Build the config-backed payload for a given size.

        :param size: The number of documents and allowlist entries.
        :returns: The document paths for this size.
        """
        paths, allow = _allowlist_workload(size)
        build.allow = allow  # type: ignore[attr-defined]
        return paths

    def run(paths: tuple[str, ...]) -> tuple[models.Finding, ...]:
        """Run the policy with the allowlist captured for this size.

        :param paths: The document paths for this size.
        :returns: The findings (empty: every clean document is conformant).
        """
        config = Config(documentation_naming="kebab", documentation_naming_allow=build.allow)  # type: ignore[attr-defined]
        return naming.check_paths(paths, config)

    assert_scales_linearly(
        build,
        run,
        sizes=(10000, 20000, 40000, 80000),
        expected_count=0,
        label="ds118-allowlist",
    )


def test_naive_list_allowlist_membership_would_be_quadratic():
    """
    [Unit] detectors naming: proves a naive list-membership allowlist is quadratic on the shared workload.

    Scenario:
        Given the same growing (documents, allowlist) workload used for the linear allowlist test
        When a NAIVE reference consults a Python list for membership (O(allow) per document)
        Then its measured log-log slope is clearly super-linear -- documenting the trap the real
            detector avoids by storing the allowlist as a frozenset.

    Boundaries:
        - Focus: demonstrate that the shared workload WOULD fail a naive implementation
        - Fixtures/params: measure_scaling over a doubling series; asserts a super-linear slope

    On failure, first check:
        - Whether the smallest size is large enough to lift the quadratic above the timing floor
    """

    def build(size: int) -> tuple[tuple[str, ...], list[str]]:
        """Build the naive payload: document filenames plus a list allowlist.

        :param size: The number of documents and allowlist entries.
        :returns: A ``(filenames, allow_list)`` pair for the naive reference.
        """
        paths, allow = _allowlist_workload(size)
        return tuple(path.rsplit("/", 1)[-1] for path in paths), list(allow)

    def naive(payload: tuple[tuple[str, ...], list[str]]) -> list[str]:
        """Flag each filename not present in a list allowlist (O(documents x allow)).

        :param payload: The ``(filenames, allow_list)`` pair.
        :returns: The filenames that were not found in the allowlist.
        """
        filenames, allow_list = payload
        return [name for name in filenames if name not in allow_list]

    report = measure_scaling(
        build,
        naive,
        sizes=(2000, 4000, 8000, 16000),
        expected_count=lambda size: size,
    )
    assert report.slope > 1.5, f"naive list-membership was not super-linear: {report.describe()}"


def test_detect_passes_document_paths_through_the_policy():
    """
    [Unit] detectors naming: verifies detect maps Document.path through the policy without touching root.

    Scenario:
        Given fabricated Documents and an arbitrary non-path root object
        When detect runs under the kebab policy
        Then it reports the offending document and never consults the root (the mock oracle proves the
            zero-filesystem contract; this test pins the path mapping and the unused root).

    Boundaries:
        - Focus: the detect wrapper over check_paths; root is accepted but unused
        - Fixtures/params: a sentinel root object

    On failure, first check:
        - Whether detect touched root or dropped Document.path
    """
    documents = (models.Document("docs/Bad Name.md", 0), models.Document("docs/good.md", 0))
    findings = naming.detect(object(), documents, Config(documentation_naming="kebab"))
    assert [finding.path for finding in findings] == ["docs/Bad Name.md"]
