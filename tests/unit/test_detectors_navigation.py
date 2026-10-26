"""Unit tests for DS112 declared-navigation-integrity recognition.

These tests use tiny inline Markdown strings (or a few small files written into
``tmp_path`` when the readiness error, the missing-destination probe, or the
cross-index ``navigation_required`` aggregation genuinely needs the filesystem) and
call the detector's pure core through ``check_text(text, index_path, root, config)``
and ``detect(root, documents, config)``. Detection over committed Markdown assets is
the job of the Story 09.0 Task 03 integration suite, which runs now that ``DS112``
is registered together with its ``tests/assets/ds112/*`` fixtures (Task 02). This
module exercises the detector's pure core in isolation and confirms that
registration.

Each algorithm bullet, exclusion, and ruling (R1-R8) of the DS112 threat model has a
test here, plus the readiness errors, the config opt-in honesty, the bounded
repr-escaped echo, and single-line and multi-line linear-scaling floods.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from docsentinel import cli, models, rules
from docsentinel.config import Config, ConfigError
from docsentinel.detectors import navigation as nav
from docsentinel.engine import scan
from tests.timing_helpers import assert_scales_linearly

_ROOT = Path(os.sep) / "scanroot"


def _messages(findings: tuple[models.Finding, ...]) -> list[str]:
    """Return the message of each finding in order.

    :param findings: The findings to describe.
    :returns: The ordered finding messages.
    """
    return [finding.message for finding in findings]


def _write(root: Path, relative: str, text: str):
    """Write ``text`` to ``root / relative``, creating parent directories.

    :param root: The scan-root directory.
    :param relative: POSIX-style relative path under the root.
    :param text: The file content.
    """
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_rule_metadata_is_exact_and_registered():
    """
    [Unit] detectors navigation: verifies DS112 metadata and its Task 02 registration.

    Scenario:
        Given the DS112 rule metadata defined in the detector module
        When its fields and the live rule registry are inspected
        Then the metadata is exact, the opt-in option names navigation_indexes, and the
            rule is registered in both RULES and ANALYZERS (Task 02 wiring).

    Boundaries:
        - Focus: rule identity and the registration that activates the fixture catalog slice
        - Fixtures/params: none

    On failure, first check:
        - Whether a metadata field (profile, severity, opt_in_option) drifted
        - Whether register_rule / ANALYZERS wiring was removed or the import dropped
    """
    assert nav.DS112.code == "DS112"
    assert nav.DS112.profile == "fast"
    assert nav.DS112.severity == "warning"
    assert nav.DS112.title == "Declared documentation navigation integrity"
    assert nav.DS112.opt_in_option == "navigation_indexes"
    assert rules.RULES["DS112"] is nav.DS112
    assert rules.ANALYZERS["DS112"] is nav.detect


def test_opt_in_gate_is_navigation_indexes_only():
    """
    [Unit] detectors navigation: verifies the opt-in gate keys only on navigation_indexes (R8).

    Scenario:
        Given the default config and a config with navigation_indexes set
        When opt_in_satisfied and detect are consulted
        Then the policy is off (no findings) with empty indexes and on once indexes are
            configured, independent of the navigation_* sub-toggles.

    Boundaries:
        - Focus: R8 opt-in accounting; disabled policy never masquerades as evaluated
        - Fixtures/params: default and configured Config

    On failure, first check:
        - The navigation_indexes guard at the top of detect
        - opt_in_satisfied's truthiness/off handling for a tuple option
    """
    assert rules.opt_in_satisfied(nav.DS112, Config()) is False
    assert rules.opt_in_satisfied(nav.DS112, Config(navigation_indexes=("README.md",))) is True
    # Sub-toggles off but indexes set: still genuinely evaluated (the gate is indexes only).
    assert (
        rules.opt_in_satisfied(
            nav.DS112,
            Config(navigation_indexes=("README.md",), navigation_check_missing=False, navigation_unique_targets=False),
        )
        is True
    )
    assert nav.detect(_ROOT, (), Config()) == ()


def test_list_links_are_navigation_prose_links_are_not():
    """
    [Unit] detectors navigation: verifies only list-item links are navigation (R1).

    Scenario:
        Given an index whose list items link to in-root docs and whose body also carries
            a prose link to a nonexistent doc, with missing-destination checking on
        When check_text analyzes it against a root where neither target exists
        Then the list links are missing-destination findings and the prose link is not,
            because navigation is scoped to list items derived over masked text.

    Boundaries:
        - Focus: R1 navigation scope (list membership over masked text), prose exclusion
        - Fixtures/params: inline string, default-ish Config

    On failure, first check:
        - The _LIST_MARKER_RE / _navigation_list_lines membership derivation
        - That prose-line tokens are excluded from _navigation_links
    """
    text = "# Nav\n\n- [Guide](guide.md)\n- [API](api.md)\n\nSee [broken](prose_only.md) in prose.\n"
    findings = nav.check_text(text, "README.md", _ROOT, Config(navigation_indexes=("README.md",)))
    messages = _messages(findings)
    assert "navigation target does not exist: guide.md" in messages
    assert "navigation target does not exist: api.md" in messages
    assert all("prose_only.md" not in message for message in messages)


def test_links_in_fence_inline_code_and_comment_are_not_navigation():
    """
    [Unit] detectors navigation: verifies masked-region links are never navigation (R1).

    Scenario:
        Given an index with nav-looking list links inside a fenced block, an inline-code
            span, and an HTML comment
        When check_text analyzes it
        Then none of those links is treated as navigation, so no finding is produced.

    Boundaries:
        - Focus: R1 scanner-evasion parity; mask only what CommonMark hides
        - Fixtures/params: inline string

    On failure, first check:
        - That _masked_lines blanks fence/inline-code/comment spans before the marker test
        - That the shared scanner does not emit tokens for masked regions
    """
    text = "```\n- [x](nope_fence.md)\n```\n\n- `[y](nope_code.md)`\n\n<!-- - [z](nope_comment.md) -->\n"
    assert nav.check_text(text, "README.md", _ROOT, Config(navigation_indexes=("README.md",))) == ()


def test_external_and_fragment_links_are_permitted():
    """
    [Unit] detectors navigation: verifies external URLs and fragment-only links are allowed.

    Scenario:
        Given list items linking to an external URL and to a same-document fragment
        When check_text analyzes the index
        Then neither is a missing-destination finding nor a required/duplicate target.

    Boundaries:
        - Focus: external-link exclusion and fragment-only locality
        - Fixtures/params: inline string

    On failure, first check:
        - The EXTERNAL short-circuit after resolve_local_reference
        - The ``target.startswith('#')`` fragment-only skip
    """
    text = "- [Product](https://example.com/product)\n- [Section](#nav)\n"
    assert nav.check_text(text, "README.md", _ROOT, Config(navigation_indexes=("README.md",))) == ()


def test_duplicate_target_reported_once_at_the_later_link():
    """
    [Unit] detectors navigation: verifies a duplicate target is flagged at the later link.

    Scenario:
        Given two list links to the same in-root target
        When check_text runs with navigation_unique_targets on and missing checks off
        Then exactly one duplicate finding is produced, anchored at the second link's line.

    Boundaries:
        - Focus: navigation_unique_targets "reported once each at later link"
        - Fixtures/params: inline string

    On failure, first check:
        - The seen_identity first-occurrence bookkeeping in _analyze_index
        - That the finding line is the later link's one-based line
    """
    text = "- [a](docs/guide.md)\n- [b](docs/guide.md)\n"
    config = Config(navigation_indexes=("README.md",), navigation_check_missing=False)
    findings = nav.check_text(text, "README.md", _ROOT, config)
    assert len(findings) == 1
    assert findings[0].message == "navigation target is linked more than once: docs/guide.md"
    assert findings[0].line == 2
    assert findings[0].severity == "warning"


def test_duplicate_identity_ignores_the_fragment():
    """
    [Unit] detectors navigation: verifies duplicate identity strips the fragment (R5).

    Scenario:
        Given two list links to the same document with different #fragments
        When check_text runs with unique targets on and missing checks off
        Then they count as one duplicate target, so one duplicate finding is produced.

    Boundaries:
        - Focus: R5 fragment-stripped duplicate identity
        - Fixtures/params: inline string

    On failure, first check:
        - That _resolved_identity uses the fragment-stripped resolved path
    """
    text = "- [a](docs/guide.md#intro)\n- [b](docs/guide.md#setup)\n"
    config = Config(navigation_indexes=("README.md",), navigation_check_missing=False)
    findings = nav.check_text(text, "README.md", _ROOT, config)
    assert _messages(findings) == ["navigation target is linked more than once: docs/guide.md#setup"]


def test_unique_targets_off_suppresses_duplicate_finding():
    """
    [Unit] detectors navigation: verifies navigation_unique_targets=false suppresses duplicates.

    Scenario:
        Given two list links to the same target and navigation_unique_targets disabled
        When check_text runs with missing checks also off
        Then no finding is produced.

    Boundaries:
        - Focus: the navigation_unique_targets sub-toggle
        - Fixtures/params: inline string

    On failure, first check:
        - The ``settings.navigation_unique_targets`` guard before the duplicate record
    """
    text = "- [a](docs/guide.md)\n- [b](docs/guide.md)\n"
    config = Config(navigation_indexes=("README.md",), navigation_unique_targets=False, navigation_check_missing=False)
    assert nav.check_text(text, "README.md", _ROOT, config) == ()


def test_missing_destination_reported_and_present_destination_is_clean(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies the missing-destination probe (R6).

    Scenario:
        Given an index with one list link to a committed in-root doc and one to an absent
            doc, under a real scan root
        When check_text runs with navigation_check_missing on
        Then only the absent destination is reported, proving a single os.stat decides it.

    Boundaries:
        - Focus: navigation_check_missing / R6 existence probe on a RESOLVED in-root target
        - Fixtures/params: tmp_path (real files)

    On failure, first check:
        - The os.stat-only _destination_missing probe and its memoisation
        - That an existing destination yields no finding
    """
    root = Path(os.path.realpath(tmp_path))
    _write(root, "docs/guide.md", "# guide\n")
    text = "- [Guide](docs/guide.md)\n- [Gone](docs/gone.md)\n"
    findings = nav.check_text(text, "README.md", root, Config(navigation_indexes=("README.md",)))
    assert _messages(findings) == ["navigation target does not exist: docs/gone.md"]
    assert findings[0].line == 2


def test_check_missing_off_suppresses_missing_finding(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies navigation_check_missing=false suppresses missing findings.

    Scenario:
        Given a list link to an absent in-root doc and navigation_check_missing disabled
        When check_text runs
        Then no finding is produced.

    Boundaries:
        - Focus: the navigation_check_missing sub-toggle
        - Fixtures/params: tmp_path

    On failure, first check:
        - The ``settings.navigation_check_missing`` guard before the os.stat probe
    """
    root = Path(os.path.realpath(tmp_path))
    text = "- [Gone](docs/gone.md)\n"
    config = Config(navigation_indexes=("README.md",), navigation_check_missing=False)
    assert nav.check_text(text, "README.md", root, config) == ()


def test_escaping_navigation_target_is_reported_lexically(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies an escaping nav target is a lexical escape finding (R4).

    Scenario:
        Given a list link whose target traverses above the scan root, scanned under a root
            with no matching file on disk
        When check_text runs with the default (missing-checking) config
        Then a single "escapes the documentation root" finding is produced, not a
            missing-destination finding, with no filesystem probe of the escaped target.

    Boundaries:
        - Focus: R4 lexical escape finding; the DS116 overlap by design
        - Fixtures/params: tmp_path

    On failure, first check:
        - The is_ds116_owned / OUTSIDE_ROOT short-circuit emitting the escape finding
        - That the escape path ``continue``s before any resolve/stat
    """
    root = Path(os.path.realpath(tmp_path))
    text = "- [Up](../../secret.md)\n"
    findings = nav.check_text(text, "docs/index.md", root, Config(navigation_indexes=("docs/index.md",)))
    assert _messages(findings) == ["navigation target escapes the documentation root: ../../secret.md"]


def test_reference_style_navigation_item_is_resolved(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies a full reference-style nav item resolves (R7).

    Scenario:
        Given a list item using [text][label] with a matching [label]: target definition,
            where the target exists on disk
        When check_text runs with missing checking on
        Then no finding is produced because the reference use is joined to its definition
            and the destination exists.

    Boundaries:
        - Focus: R7 full/collapsed reference-use join to definitions
        - Fixtures/params: tmp_path

    On failure, first check:
        - The reference_uses -> reference_definitions label join in _navigation_links
    """
    root = Path(os.path.realpath(tmp_path))
    _write(root, "docs/guide.md", "# guide\n")
    text = "- [Guide][g]\n\n[g]: docs/guide.md\n"
    assert nav.check_text(text, "README.md", root, Config(navigation_indexes=("README.md",))) == ()


def test_shortcut_reference_navigation_item_is_a_false_negative(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies shortcut references are an accepted false negative (R7).

    Scenario:
        Given a list item written as a bare shortcut reference [label] with a definition to
            an absent destination
        When check_text runs with missing checking on
        Then DS112 produces no finding, pinning the documented shortcut false negative
            (the shared scanner does not populate reference_uses for shortcuts).

    Boundaries:
        - Focus: R7 shortcut-reference documented gap; no ad-hoc regex over unmasked source
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether a shortcut recognizer was added (it must not be) -- this would change scope
    """
    root = Path(os.path.realpath(tmp_path))
    text = "- [g]\n\n[g]: docs/gone.md\n"
    assert nav.check_text(text, "README.md", root, Config(navigation_indexes=("README.md",))) == ()


def test_list_recognition_differentials_are_pinned(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies the two documented list-recognition differentials stay explicit.

    Scenario:
        Given a paragraph followed by an ordered item starting at 3, and a bullet item with a lazy
            continuation line holding a link to an absent destination
        When check_text runs with missing checking on
        Then the ordered "3." item is treated as navigation (known false positive: CommonMark only
            lets an ordered list starting at 1 interrupt a paragraph) and the lazy-continuation link
            is not (known false negative), exactly as docs/dev/markdown_dialect.md states.

    Boundaries:
        - Focus: security-review differentials are pinned so a scanner change cannot flip them silently
        - Fixtures/params: tmp_path

    On failure, first check:
        - Whether _LIST_MARKER_RE or the list-line derivation changed
        - Whether docs/dev/markdown_dialect.md and the threat model were updated to match
    """
    root = Path(os.path.realpath(tmp_path))
    config = Config(navigation_indexes=("README.md",))
    ordered = nav.check_text("Intro paragraph\n3. See [g](gone.md)\n", "README.md", root, config)
    lazy = nav.check_text("- intro\n  [c](gone.md)\n", "README.md", root, config)

    assert [finding.line for finding in ordered] == [2]
    assert lazy == ()


def test_nested_relative_nav_resolves_relative_to_index_location(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies nav links resolve relative to the index, not cwd (R5).

    Scenario:
        Given a nested index docs/index.md linking to the sibling file guide.md, where
            docs/guide.md exists on disk
        When detect runs with docs/index.md as the configured index
        Then the link resolves to docs/guide.md (relative to the index) and no finding is
            produced, proving resolution ignores the process cwd.

    Boundaries:
        - Focus: R5 index-relative resolution and canonical identity
        - Fixtures/params: tmp_path

    On failure, first check:
        - That resolve_local_reference is called with the index path as the document base
    """
    root = Path(os.path.realpath(tmp_path))
    _write(root, "docs/index.md", "- [Guide](guide.md)\n")
    _write(root, "docs/guide.md", "# guide\n")
    documents = (models.Document("docs/index.md", 0), models.Document("docs/guide.md", 0))
    assert nav.detect(root, documents, Config(navigation_indexes=("docs/index.md",))) == ()


def test_navigation_required_union_and_missing_entry(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies navigation_required membership over the index union.

    Scenario:
        Given two indexes whose list links cover docs/guide.md and docs/api.md, and a
            navigation_required set that also demands an unlinked docs/extra.md
        When detect runs
        Then the listed required targets are satisfied and only docs/extra.md yields a single
            "required navigation target is not listed" finding anchored at the first index.

    Boundaries:
        - Focus: navigation_required satisfied by the union of indexes; set-based membership
        - Fixtures/params: tmp_path

    On failure, first check:
        - The union aggregation of identities across indexes before the required loop
        - That the required finding uses the primary (first) configured index path
    """
    root = Path(os.path.realpath(tmp_path))
    _write(root, "README.md", "- [Guide](docs/guide.md)\n")
    _write(root, "docs/index.md", "- [API](api.md)\n")
    _write(root, "docs/guide.md", "# g\n")
    _write(root, "docs/api.md", "# a\n")
    documents = tuple(
        models.Document(path, 0) for path in ("README.md", "docs/index.md", "docs/guide.md", "docs/api.md")
    )
    config = Config(
        navigation_indexes=("README.md", "docs/index.md"),
        navigation_required=("docs/guide.md", "docs/api.md", "docs/extra.md"),
    )
    findings = nav.detect(root, documents, config)
    assert _messages(findings) == [
        "required navigation target is not listed in the configured navigation: docs/extra.md"
    ]
    assert findings[0].path == "README.md"
    assert findings[0].line is None


def test_missing_configured_index_raises_config_error(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies a missing configured index fails closed (R3).

    Scenario:
        Given a configured navigation index that is not a discovered document
        When detect runs
        Then a ConfigError is raised (never a clean empty-findings scan), echoing only the
            bounded configured path.

    Boundaries:
        - Focus: R3 readiness error; no silent clean, no Finding
        - Fixtures/params: tmp_path

    On failure, first check:
        - The document-membership gate in _require_readable_index
        - That the message carries no resolved absolute path
    """
    root = Path(os.path.realpath(tmp_path))
    _write(root, "README.md", "- [x](README.md)\n")
    documents = (models.Document("README.md", 0),)
    with pytest.raises(ConfigError, match="docs/missing.md"):
        nav.detect(root, documents, Config(navigation_indexes=("docs/missing.md",)))


def test_non_utf8_configured_index_raises_config_error(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies a non-UTF-8 index fails closed with the readiness error (R3).

    Scenario:
        Given a discovered index document whose bytes are not valid UTF-8
        When detect runs
        Then a ConfigError (not a raw UnicodeDecodeError) is raised, echoing only the bounded
            configured path and no absolute path.

    Boundaries:
        - Focus: the Python API raises the documented readiness error for undecodable indexes
        - Fixtures/params: tmp_path

    On failure, first check:
        - The try/except around _read_index in detect
        - That the message carries no resolved absolute path
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "README.md").write_bytes(b"- [x](a.md) \xff\xfe\n")
    documents = (models.Document("README.md", 0),)
    with pytest.raises(ConfigError, match="could not be read") as raised:
        nav.detect(root, documents, Config(navigation_indexes=("README.md",)))
    assert str(root) not in str(raised.value)


def test_non_regular_configured_index_raises_config_error(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies a directory configured as an index fails closed (R2/R3).

    Scenario:
        Given a directory committed where a configured index path should be a file, listed in
            the discovered documents by identity
        When detect runs
        Then a ConfigError is raised rather than opening the directory.

    Boundaries:
        - Focus: R2 os.stat + S_ISREG defensive check; never open a non-regular path
        - Fixtures/params: tmp_path

    On failure, first check:
        - The stat.S_ISREG branch of _require_readable_index
    """
    root = Path(os.path.realpath(tmp_path))
    (root / "docs").mkdir()
    documents = (models.Document("docs", 0),)
    with pytest.raises(ConfigError, match="docs"):
        nav.detect(root, documents, Config(navigation_indexes=("docs",)))


def test_injected_config_out_of_root_index_raises_config_error(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies an injected out-of-root index is rejected (R2/R3).

    Scenario:
        Given an injected Config (bypassing load_config validation) whose navigation_indexes
            entry escapes the scan root
        When detect runs
        Then the defensive is_ds116_owned / resolver gate raises a ConfigError with no
            filesystem access to the escaped path.

    Boundaries:
        - Focus: R2 injected-Config defence; the lexical containment re-check
        - Fixtures/params: tmp_path

    On failure, first check:
        - The is_ds116_owned / OUTSIDE_ROOT guard at the top of _require_readable_index
    """
    root = Path(os.path.realpath(tmp_path))
    documents = (models.Document("README.md", 0),)
    config = Config.__new__(Config)
    object.__setattr__(config, "navigation_indexes", ("../../etc/passwd.md",))
    object.__setattr__(config, "navigation_required", ())
    object.__setattr__(config, "navigation_unique_targets", True)
    object.__setattr__(config, "navigation_check_missing", True)
    with pytest.raises(ConfigError, match="escapes the documentation root"):
        nav.detect(root, documents, config)


def test_message_echo_is_bounded_escaped_and_hides_absolute_path(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies bounded repr-escaped echo with no path disclosure.

    Scenario:
        Given _echo applied to a 10,000-char value carrying NUL/ESC/CR/LF, and a list link
            whose 10,000-char target carries NUL/ESC control bytes (a line-based scanner cannot
            carry CR/LF inside a single-line link target), scanned under a real root
        When _echo runs and check_text analyzes the index
        Then every echoed message stays bounded, contains no raw control byte or raw CR/LF, and
            never contains the resolved absolute root path.

    Boundaries:
        - Focus: bounded, unicode_escape echo (log-injection / path-disclosure control)
        - Fixtures/params: tmp_path

    On failure, first check:
        - The _echo bound (_MAX_ECHO) and unicode_escape call
        - That the resolved absolute path is never interpolated into a message
    """
    echoed = nav._echo("x\x00\x1b\r\n" + ("a" * 10_000))
    # The raw value is bounded to _MAX_ECHO characters before escaping; escaping can
    # expand each control byte to a few printable characters, so the escaped result
    # stays within a small constant multiple of the bound, never the 10,000-char input.
    assert len(echoed) <= nav._MAX_ECHO * 4 + 3
    assert not any(ord(character) < 0x20 or ord(character) == 0x7F for character in echoed)
    assert "\r" not in echoed and "\n" not in echoed
    assert echoed.endswith("...")

    root = Path(os.path.realpath(tmp_path))
    hostile = "docs/\x00\x1b" + ("a" * 10_000) + ".md"
    text = f"- [x]({hostile})\n"
    findings = nav.check_text(text, "README.md", root, Config(navigation_indexes=("README.md",)))
    assert len(findings) == 1
    message = findings[0].message
    assert len(message) < 200
    assert not any(ord(character) < 0x20 or ord(character) == 0x7F for character in message)
    assert str(root) not in message
    assert message.endswith("...")


def test_engine_propagates_readiness_config_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    [Unit] detectors navigation: verifies the engine propagates the readiness ConfigError (R3).

    Scenario:
        Given DS112 temporarily registered and wired into ANALYZERS, and a scan config whose
            configured index is missing
        When engine.scan runs over a real root
        Then the ConfigError propagates out of scan (the engine does not catch analyzer
            exceptions), so the CLI's exit-2 path is reached and no clean ScanResult is built.

    Boundaries:
        - Focus: R3 propagation through the engine; existing exit codes/JSON schema untouched
        - Fixtures/params: tmp_path, monkeypatch (temporary registration, auto-restored)

    On failure, first check:
        - That engine._run_analyzer does not wrap analyzers in try/except
        - That the config reaches the analyzer (keyword dispatch)
    """
    monkeypatch.setitem(rules.RULES, "DS112", nav.DS112)
    monkeypatch.setitem(rules.ANALYZERS, "DS112", nav.detect)
    _write(tmp_path, "README.md", "# docs\n")
    config = Config(profile="fast", select=("DS112",), navigation_indexes=("docs/missing.md",))
    with pytest.raises(ConfigError):
        scan(tmp_path, config=config)


def test_cli_scan_maps_readiness_error_to_exit_two(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    """
    [Unit] detectors navigation: verifies the CLI maps the readiness error to exit 2 (R3).

    Scenario:
        Given DS112 temporarily registered and a standalone docsentinel.toml configuring a
            missing navigation index
        When the scan CLI command runs with JSON output
        Then it returns exit code 2 and prints a "Scan failed" line, with no resolved absolute
            path leaked into the message.

    Boundaries:
        - Focus: R3 end-to-end readiness mapping to the existing config/scan-failure exit code
        - Fixtures/params: tmp_path, monkeypatch, capsys

    On failure, first check:
        - The CLI's ``except (ConfigError, ValueError, OSError)`` -> return 2 path
        - That the echoed message hides the absolute root
    """

    monkeypatch.setitem(rules.RULES, "DS112", nav.DS112)
    monkeypatch.setitem(rules.ANALYZERS, "DS112", nav.detect)
    _write(tmp_path, "README.md", "# docs\n")
    _write(tmp_path, "docsentinel.toml", 'profile = "fast"\nnavigation_indexes = ["docs/missing.md"]\n')
    code = cli.main(["scan", str(tmp_path), "--format", "json"])
    captured = capsys.readouterr()
    assert code == 2
    assert "Scan failed" in captured.err
    assert str(Path(os.path.realpath(tmp_path))) not in captured.err


# --- Linear-scaling floods (threat-model requirement 6) ---------------------------

_PURE_SETTINGS = Config(
    navigation_indexes=("README.md",),
    navigation_check_missing=False,
    navigation_unique_targets=True,
)


def _run_pure(text: str) -> tuple[models.Finding, ...]:
    """Run DS112 recognition over one in-memory index without any filesystem probe.

    :param text: The index Markdown text.
    :returns: The DS112 findings.
    """
    return nav.check_text(text, "README.md", _ROOT, _PURE_SETTINGS)


#: Single-line floods: one list item carrying many links on a single physical line,
#: mapped to the exact DS112 finding count that shape must yield. Each builder uses a
#: non-repeating unit so the shape is a genuine doubling, not a shared substring.
_SINGLE_LINE: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    # n distinct targets each linked twice on one list line -> n duplicate findings
    # (distinct messages, so the (line, message) de-dup never collapses them).
    "distinct_target_duplicate_flood": (
        lambda n: "- " + "".join(f"[a{i}](t{i}.md)[b{i}](t{i}.md)" for i in range(n)) + "\n",
        lambda n: n,
    ),
    # n distinct escaping targets on one list line -> n lexical escape findings.
    "escape_target_flood": (
        lambda n: "- " + "".join(f"[a{i}](../../out{i}.md)" for i in range(n)) + "\n",
        lambda n: n,
    ),
    # A single very long target on one list line -> one escape finding, no tail rescan.
    "long_single_target": (
        lambda n: "- [a](" + "../" * n + "y.md)\n",
        lambda _n: 1,
    ),
}

#: Multi-line floods: n independent list items, each a distinct escaping link so no
#: de-duplication collapses the count.
_MULTI_LINE: dict[str, tuple[Callable[[int], str], Callable[[int], int]]] = {
    "many_distinct_escape_items": (
        lambda n: "".join(f"- [a{i}](../../out{i}.md)\n" for i in range(n)),
        lambda n: n,
    ),
    "many_reference_style_items": (
        lambda n: (
            "".join(f"- [t{i}][r{i}]\n" for i in range(n))
            + "\n"
            + "".join(f"[r{i}]: ../../out{i}.md\n" for i in range(n))
        ),
        lambda n: n,
    ),
}

_SINGLE_LINE_SIZES = (1_000, 2_000, 4_000, 8_000)
_MULTI_LINE_SIZES = (400, 800, 1_600, 3_200)


@pytest.mark.parametrize("name", list(_SINGLE_LINE))
def test_single_line_floods_stay_linear(name: str):
    """
    [Unit] detectors navigation: verifies single-line navigation floods scale near-linearly.

    Scenario:
        Given one list line carrying a same-target duplicate flood, a distinct-escape flood,
            or a single very long traversal target, across a doubling series
        When DS112 recognition runs with no filesystem probe
        Then the exact finding count holds at every size and the scaling stays under the
            linear bound, proving the masked-text list scan and per-link classification are linear.

    Boundaries:
        - Focus: one bounded linear marker pass and O(links) classification, no catastrophic regex
        - Fixtures/params: parametrized over every single-line flood shape

    On failure, first check:
        - Whether _navigation_links or the duplicate bookkeeping became super-linear
        - Whether resolve_local_reference began rescanning a long target
    """
    builder, expected = _SINGLE_LINE[name]
    assert_scales_linearly(builder, _run_pure, _SINGLE_LINE_SIZES, expected_count=expected, label=name)


@pytest.mark.parametrize("name", list(_MULTI_LINE))
def test_multi_line_floods_stay_linear(name: str):
    """
    [Unit] detectors navigation: verifies multi-line navigation floods scale near-linearly.

    Scenario:
        Given n independent list items (distinct escaping links, and reference-style items
            joined to definitions) across a doubling series
        When DS112 recognition runs with no filesystem probe
        Then exactly n findings are produced at every size and the scaling stays under the
            linear bound.

    Boundaries:
        - Focus: per-item O(1) classification and the reference-use/definition join at scale
        - Fixtures/params: parametrized over every multi-line flood shape

    On failure, first check:
        - Whether list-line membership or the definition join became super-linear
    """
    builder, expected = _MULTI_LINE[name]
    assert_scales_linearly(builder, _run_pure, _MULTI_LINE_SIZES, expected_count=expected, label=name)


def test_navigation_required_is_not_quadratic(tmp_path: Path):
    """
    [Unit] detectors navigation: verifies required-vs-links membership is linear, not quadratic.

    Scenario:
        Given an index listing n links to the even-numbered docs and a navigation_required set
            demanding all n docs, with missing checking off, across a doubling series where a
            fresh index file is written per size
        When detect runs
        Then exactly n/2 unlisted-required findings are produced at every size and the scaling
            stays under the linear bound, proving the required check is O(links + required) set
            membership rather than O(required x links).

    Boundaries:
        - Focus: no quadratic required x links; set-based membership over the union
        - Fixtures/params: tmp_path (a new scan root and index per size)

    On failure, first check:
        - Whether the required loop does a linear scan of the identities per entry
        - Whether identities is a set, not a list
    """

    def build(size: int) -> tuple[Path, tuple[models.Document, ...], Config]:
        """Create a per-size scan root with an index listing the even docs.

        :param size: Number of navigation_required entries (even).
        :returns: ``(root, documents, config)`` for one detect run.
        """
        root = Path(os.path.realpath(tmp_path)) / f"root{size}"
        root.mkdir()
        listed = "".join(f"- [d{i}](docs/d{i}.md)\n" for i in range(0, size, 2))
        (root / "index.md").write_text(listed, encoding="utf-8")
        documents = (models.Document("index.md", 0),)
        config = Config(
            navigation_indexes=("index.md",),
            navigation_required=tuple(f"docs/d{i}.md" for i in range(size)),
            navigation_check_missing=False,
        )
        return root, documents, config

    def run(payload: tuple[Path, tuple[models.Document, ...], Config]) -> tuple[models.Finding, ...]:
        """Run detect for one pre-built payload.

        :param payload: The ``(root, documents, config)`` triple from ``build``.
        :returns: The DS112 findings.
        """
        root, documents, config = payload
        return nav.detect(root, documents, config)

    assert_scales_linearly(
        build,
        run,
        (200, 400, 800, 1_600),
        expected_count=lambda n: n // 2,
        label="required_not_quadratic",
    )
