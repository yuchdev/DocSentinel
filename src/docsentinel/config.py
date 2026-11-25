"""Configuration for local, deterministic scans."""

import json
import logging
import math
import os
import re
import stat
import tomllib
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional, Union

from docsentinel.log import safe
from docsentinel.telemetry.filters import neutralize

logger = logging.getLogger(__name__)

_CONFIG_OPTIONS = {
    "include",
    "exclude",
    "profile",
    "select",
    "ignore",
    "baseline",
    "max_grade_level",
    "duplicate_similarity",
    "min_information_score",
    "docsig_paths",
    # Standard-profile statistical size limits (DS201, DS202, DS203).
    "min_document_words",
    "min_paragraph_words",
    "min_paragraph_chars",
    # Story 02 — anchor identity and collisions (DS104).
    "anchor_collision_policy",
    "anchor_renderer",
    # Story 03 — heading hierarchy validation (DS105).
    "heading_level_policy",
    "first_heading_level",
    "multiple_h1_policy",
    "setext_heading_support",
    # Story 04 — contentless section detection (DS106).
    "empty_section_policy",
    "placeholder_content_policy",
    "image_content_counts",
    "empty_section_min_text_chars",
    # Story 05 — reference definition integrity (DS108).
    "unused_reference_definitions",
    "duplicate_reference_definitions",
    "reference_label_normalization",
    # Story 06 — fenced code boundary validation (DS109).
    "fence_dialect",
    "report_stray_closing_fence",
    # Story 07 — code fence language policy (DS110).
    "require_fence_languages",
    "allow_unlabelled_empty_fences",
    "allowed_fence_languages",
    # Story 08 — pipe table structural validation (DS117).
    "table_dialect",
    "table_strict_cells",
    "table_enable",
    # Story 09 — configured navigation integrity (DS112).
    "navigation_indexes",
    "navigation_required",
    "navigation_unique_targets",
    "navigation_check_missing",
    # Story 10 — missing local media assets (DS113).
    "asset_extensions",
    "check_html_asset_tags",
    "check_markdown_images",
    "check_srcset",
    "missing_asset_policy",
    # Story 11 — repository root path boundaries (DS116).
    "root_escape_policy",
    "decode_percent_paths",
    "windows_path_policy",
    # Story 12 — document identity uniqueness (DS114).
    "document_id_field",
    "document_id_scope",
    "document_id_case_sensitive",
    "document_id_required",
    # Story 13 — deprecated reference and terminology (DS115).
    "deprecated_references_file",
    "deprecated_check_prose",
    "deprecated_check_links",
    "deprecated_case_sensitive",
    # Story 14 — documentation path naming policy (DS118).
    "documentation_naming",
    "documentation_naming_allow",
    "documentation_naming_directories",
    "documentation_naming_prefix_patterns",
    # Milestone 0007 Story 03.0 — template-driven reporting.
    "report_templates_dir",
    "report_show_clean_documents",
    "report_include_run_meta",
    # Milestone 0007 Story 04.0 — report extensions (builtin-only in config).
    "telemetry_extensions",
    # Milestone 0007 Story 04.0 Task 02 — path -> domain table of ``builtin:domain``.
    "telemetry_domains",
    # Site-root-absolute link base (``/``-targets; DS101, DS103, DS112, DS113, DS116).
    "link_root",
    # Milestone 0009 Story 01.0 — reference scope (DS103 opt-in) and @-document references (DS124).
    "reference_scope",
    "at_reference_extensions",
    # Milestone 0010 Story 01.0 — DS302 fact-check tuning (ADR 0007). The invoker-only
    # consent ``use_external_api`` is deliberately absent (plan contract C5).
    "fact_check_backend",
    "fact_check_min_salience",
    "fact_check_min_confidence",
    "fact_check_max_claims_per_document",
    "fact_check_max_claims_total",
    "fact_check_time_budget_seconds",
    "fact_check_combination",
}
# Standalone config file names accepted at the scan root: the preferred name first, then the alias.
STANDALONE_CONFIG_NAMES = ("docsentinel.toml", "doc_sentinel.toml")
_SELECTOR_PATTERN = re.compile(r"DS\d*")

#: Accepted ``fact_check_backend`` names (ADR 0007, Contract 4). A static set, so
#: ``config.py`` never imports ``docsentinel.detectors``, ``docsentinel.fact_check`` or
#: ``httpx`` (plan contract C9); a drift test keeps it equal to the backend module map.
FACT_CHECK_BACKEND_NAMES: Final[frozenset[str]] = frozenset({"lenz"})

#: ``fact_check_*`` integer options with their inclusive ``(minimum, maximum)`` bounds.
_FACT_CHECK_INT_BOUNDS: Final[dict[str, tuple[int, int]]] = {
    "fact_check_max_claims_per_document": (1, 50),
    "fact_check_max_claims_total": (1, 500),
    "fact_check_time_budget_seconds": (1, 3600),
}

#: The ``fact_check_combination`` keywords: every claim alone (default), or all claims as one fact.
FACT_COMBINATION_EACH: Final = "each"
FACT_COMBINATION_ALL: Final = "all"

#: Longest accepted ``fact_check_combination`` value, in characters.
MAX_FACT_COMBINATION_CHARS: Final = 2048

#: One ``fact_check_combination`` range: ``N`` or ``N-M`` with no sign, space or leading zero.
_FACT_RANGE_RE: Final = re.compile(r"([1-9][0-9]{0,2})(?:-([1-9][0-9]{0,2}))?")

#: ``fact_check_*`` options holding a finite number in the closed range ``[0, 1]``.
_FACT_CHECK_UNIT_OPTIONS: Final = ("fact_check_min_salience", "fact_check_min_confidence")

#: Largest JSON configuration file read, in bytes (plan C7; threat model 0009-user-settings
#: M11). One byte more is read so an over-long file is detected without reading it all.
MAX_JSON_CONFIG_BYTES: Final = 1_048_576

#: Longest duplicate JSON key echoed in a message, in characters (threat model U9).
_JSON_DUPLICATE_KEY_ECHO_LIMIT: Final = 80

#: A UTF-16 surrogate code point, which is never valid on its own in decoded text.
_LONE_SURROGATE_PATTERN: Final = re.compile("[\ud800-\udfff]")

#: Flags of the single open of a JSON config file (threat model R7): never blocks on a
#: FIFO that replaced the file after the pre-check, never acquires a controlling terminal.
_JSON_OPEN_FLAGS: Final = (
    os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOCTTY", 0) | getattr(os, "O_BINARY", 0)
)

#: Environment variable naming the user settings file, or ``off`` (ADR 0005 S4). Read
#: only by :func:`user_settings_path`.
USER_SETTINGS_ENV: Final = "DOCSENTINEL_SETTINGS"

#: The exact :data:`USER_SETTINGS_ENV` value that disables the user settings layer.
USER_SETTINGS_OFF: Final = "off"

#: Repository-relative options a user settings file may not set (plan C6, ADR 0005
#: Contract 4). A new repository-relative option is added here in the same change.
USER_SETTINGS_REFUSED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "baseline",
        "include",
        "exclude",
        "docsig_paths",
        "navigation_indexes",
        "navigation_required",
        "deprecated_references_file",
        "report_templates_dir",
        "link_root",
        "telemetry_domains",
    }
)

#: Environment variable of the XDG data directory (ADR 0005 S3).
_XDG_DATA_HOME_ENV: Final = "XDG_DATA_HOME"

#: The user settings file below the data directory (ADR 0005 S3).
_USER_SETTINGS_RELATIVE: Final = Path("docsentinel") / "settings.json"

#: The data directory below the home directory when ``XDG_DATA_HOME`` is not usable.
_HOME_DATA_RELATIVE: Final = Path(".local") / "share"

#: Unicode categories refused in a settings path from the environment: controls,
#: format (bidi, zero-width), separators and surrogates.
_PATH_REFUSED_CATEGORIES: Final = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})

#: Fixed messages of the user settings permission gate (threat model R6).
_GATE_FILE_OWNER: Final = "owned by another user"
_GATE_FILE_MODE: Final = "writable by group or others (run chmod go-w on it)"
_GATE_DIRECTORY: Final = "its directory is owned by another user or writable by others"
_GATE_TOO_MANY_LINKS: Final = "too many symbolic links"

#: Most symbolic links followed while checking the user settings directories (T04-1).
_MAX_SYMLINK_HOPS: Final = 40

#: A ``telemetry_extensions`` entry: ``builtin:`` plus an extension name matching
#: ``docsentinel.telemetry.extensions.EXTENSION_NAME_PATTERN`` (a test pins parity).
#: Configuration may name only builtin extensions (threat model 0007-extensions M1).
_BUILTIN_EXTENSION_SPEC_PATTERN = re.compile(r"builtin:[a-z][a-z0-9_]{0,63}")

#: Most ``telemetry_extensions`` entries accepted.
MAX_TELEMETRY_EXTENSIONS = 32

#: Most ``at_reference_extensions`` entries accepted (threat model 0009 M20).
MAX_AT_REFERENCE_EXTENSIONS = 64

#: One ``at_reference_extensions`` entry (used with ``fullmatch``): 1 to 16 ASCII
#: letters or digits, no dot. The entries themselves are only ever compared by set
#: membership, never compiled into a pattern or a glob (M20).
_AT_REFERENCE_EXTENSION_PATTERN = re.compile(r"[A-Za-z0-9]{1,16}")

#: Bounds of the ``telemetry_domains`` table (threat model 0007-extensions M22).
MAX_TELEMETRY_DOMAINS = 256
MAX_DOMAIN_GLOB_CHARS = 256
MAX_DOMAIN_GLOB_SEGMENTS = 32
#: Total characters of all ``telemetry_domains`` globs together (closure threat model
#: 2026-11-04 follow-up (a)). The matcher's work per path is bounded by this total
#: times the path length, so it caps the per-document cost of a hostile table
#: (without it: 256 x 256 characters).
MAX_DOMAIN_GLOBS_TOTAL_CHARS = 4096

#: A domain label (owner decision D-D, the Milestone 0006 vocabulary). ASCII only:
#: ``[a-z]`` in a ``str`` pattern never matches a non-ASCII letter.
DOMAIN_LABEL_PATTERN = re.compile(r"[a-z][a-z0-9_-]{0,63}")

#: Characters a ``telemetry_domains`` glob may never hold (M20): no character
#: classes, no alternation, no escapes.
_DOMAIN_GLOB_REFUSED = frozenset("[]{}\\")

#: The two keys of one ``[[telemetry_domains]]`` table.
_DOMAIN_ENTRY_KEYS = frozenset({"glob", "domain"})

# A ``document_id_field`` (the frontmatter key DS114 reads) must be a simple,
# identifier-like key name, bounded in length so a pathological config value can
# never drive an unbounded key comparison in the detector.
_DOCUMENT_ID_FIELD_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,127}")

# Enum-valued options and their accepted vocabularies. Where a milestone
# specification fixes a single value (for example ``anchor_renderer`` or the
# dialect options), only that value is accepted until a story widens it.
_ENUM_OPTIONS: dict[str, frozenset[str]] = {
    "anchor_collision_policy": frozenset({"off", "explicit"}),
    "anchor_renderer": frozenset({"github"}),
    "heading_level_policy": frozenset({"off", "no-skips"}),
    "multiple_h1_policy": frozenset({"allow", "warn"}),
    "empty_section_policy": frozenset({"off", "leaf", "all"}),
    "placeholder_content_policy": frozenset({"ignore", "count"}),
    "duplicate_reference_definitions": frozenset({"off", "warn", "error"}),
    "reference_label_normalization": frozenset({"commonmark"}),
    "fence_dialect": frozenset({"gfm-subset"}),
    "table_dialect": frozenset({"gfm-subset"}),
    "missing_asset_policy": frozenset({"off", "warn", "error"}),
    "root_escape_policy": frozenset({"off", "warn", "error"}),
    "windows_path_policy": frozenset({"off", "portable"}),
    "document_id_scope": frozenset({"corpus", "directory"}),
    "documentation_naming": frozenset({"off", "kebab", "snake"}),
    "reference_scope": frozenset({"links", "strict"}),
    "fact_check_backend": FACT_CHECK_BACKEND_NAMES,
}

# Boolean-valued options, paired with the ``Config`` attribute defaults.
_BOOL_OPTIONS = (
    "setext_heading_support",
    "image_content_counts",
    "unused_reference_definitions",
    "report_stray_closing_fence",
    "require_fence_languages",
    "allow_unlabelled_empty_fences",
    "table_strict_cells",
    "table_enable",
    "navigation_unique_targets",
    "navigation_check_missing",
    "check_html_asset_tags",
    "check_markdown_images",
    "check_srcset",
    "decode_percent_paths",
    "document_id_case_sensitive",
    "document_id_required",
    "deprecated_check_prose",
    "deprecated_check_links",
    "deprecated_case_sensitive",
    "documentation_naming_directories",
    "report_show_clean_documents",
    "report_include_run_meta",
)

# Options holding a list of nonempty, non-path strings.
_STR_LIST_OPTIONS = (
    "allowed_fence_languages",
    "asset_extensions",
    "documentation_naming_allow",
    "documentation_naming_prefix_patterns",
)

# Options holding a list of nonempty relative paths that must stay under root.
_ROOT_PATH_LIST_OPTIONS = (
    "navigation_indexes",
    "navigation_required",
)


class ConfigError(ValueError):
    """An invalid or unreadable DocSentinel configuration."""


@dataclass(frozen=True)
class Config:
    """Immutable settings for a DocSentinel scan.

    .. note::

       :func:`load_config` validates every option (enum vocabularies, ranges,
       path containment) before constructing this dataclass. Constructing
       ``Config(...)`` directly, as a library caller may, bypasses that
       load-time validation: the field values are trusted as given, so callers
       that build a ``Config`` by hand are responsible for passing valid values.

    :ivar include: Glob patterns of Markdown documents to inventory.
    :ivar exclude: Glob/directory patterns removed from the inventory.
    :ivar profile: Active profile, one of ``fast``, ``standard``, ``deep``.
    :ivar select: Rule codes or prefixes to activate; empty selects all.
    :ivar ignore: Rule codes or prefixes to suppress; wins over ``select``.
    :ivar baseline: Path to a baseline JSON file, or ``None``.
    :ivar max_grade_level: Maximum acceptable readability grade for ``DS201``.
    :ivar duplicate_similarity: Cosine-similarity threshold for ``DS202``.
    :ivar min_information_score: Minimum information score for ``DS203``.
    :ivar docsig_paths: Python source roots scanned by ``DS204``.
    :ivar min_document_words: Minimum prose-word count before ``DS201`` scores a
        document. Documents with fewer prose words (after Markdown stripping) are
        skipped, so short notes are never penalised for readability. Integer
        ``>= 1``; the default ``50`` reproduces the historical built-in floor.
    :ivar min_paragraph_words: Minimum prose-word count for a paragraph to enter
        the ``DS202``/``DS203`` corpus. Paragraphs with fewer words are not
        analysed. Integer ``>= 1``; the default ``5`` reproduces the historical
        built-in floor.
    :ivar min_paragraph_chars: Minimum visible-character count for a paragraph to
        enter the ``DS202``/``DS203`` corpus. Paragraphs shorter than this are not
        analysed. A paragraph must clear **both** this and ``min_paragraph_words``.
        Integer ``>= 0``; the default ``30`` reproduces the historical built-in
        floor.
    :ivar anchor_collision_policy: ``DS104`` collision policy.
    :ivar anchor_renderer: Renderer whose slugging ``DS104`` emulates.
    :ivar heading_level_policy: ``DS105`` heading-level policy.
    :ivar first_heading_level: Expected first heading level (1..6) for ``DS105``.
    :ivar multiple_h1_policy: Policy for repeated H1 headings.
    :ivar setext_heading_support: Whether setext headings participate in ``DS105``.
    :ivar empty_section_policy: ``DS106`` contentless-section policy.
    :ivar placeholder_content_policy: Whether HTML comments count as ``DS106`` content.
    :ivar image_content_counts: Whether an image counts as section content.
    :ivar empty_section_min_text_chars: ``DS106`` visible-text threshold. A section is
        flagged when its visible non-whitespace character count is ``<=`` this value,
        so a section must carry **strictly more** than ``empty_section_min_text_chars``
        visible characters to count as non-empty; the default ``0`` means any visible
        text at all is enough. Positive values are deferred to the ``DS203`` quality
        policy, so a caller who sets ``5`` should expect sections with exactly five
        visible characters to be flagged.
    :ivar unused_reference_definitions: Whether unused definitions warn (``DS108``).
    :ivar duplicate_reference_definitions: ``DS108`` duplicate-definition policy.
    :ivar reference_label_normalization: Reference-label normalization dialect.
    :ivar fence_dialect: Fenced-code dialect recognized by ``DS109``.
    :ivar report_stray_closing_fence: Whether unattached closers are reported.
    :ivar require_fence_languages: Whether ``DS110`` requires a fence language.
    :ivar allow_unlabelled_empty_fences: Whether empty fences may be unlabelled.
    :ivar allowed_fence_languages: Allowlist of fence languages; empty allows all.
    :ivar table_dialect: Pipe-table dialect recognized by ``DS117``.
    :ivar table_strict_cells: Whether ``DS117`` enforces consistent cell counts.
    :ivar table_enable: Whether the ``DS117`` table check runs.
    :ivar navigation_indexes: Navigation index documents inspected by ``DS112``.
    :ivar navigation_required: Documents required to appear in navigation.
    :ivar navigation_unique_targets: Whether navigation targets must be unique.
    :ivar navigation_check_missing: Whether missing navigation targets warn.
    :ivar asset_extensions: Media extensions ``DS113`` treats as local assets.
    :ivar check_html_asset_tags: Whether ``DS113`` inspects HTML media tags.
    :ivar check_markdown_images: Whether ``DS113`` inspects Markdown images.
    :ivar check_srcset: Whether ``DS113`` inspects ``srcset`` candidates.
    :ivar missing_asset_policy: ``DS113`` severity policy for a missing or
        non-regular local asset (``"off"``/``"warn"``/``"error"``), mirroring
        ``root_escape_policy``: ``"off"`` suppresses the rule with no filesystem
        access, ``"warn"`` downgrades each finding to ``warning`` severity, and
        ``"error"`` (the default, blocking) keeps the rule's ``error`` severity.
        The :class:`~docsentinel.rules.Rule` metadata severity stays ``error``
        regardless of this policy.
    :ivar root_escape_policy: ``DS116`` root-escape policy.
    :ivar decode_percent_paths: Whether percent-encoded paths are decoded once.
    :ivar windows_path_policy: ``DS116`` Windows path portability policy.
    :ivar document_id_field: Front-matter key carrying the document identity.
    :ivar document_id_scope: Scope within which identities must be unique.
    :ivar document_id_case_sensitive: Whether identity comparison is case-sensitive.
    :ivar document_id_required: Whether every document must declare an identity.
    :ivar deprecated_references_file: Mapping file of deprecated names, or empty.
    :ivar deprecated_check_prose: Whether ``DS115`` scans prose for deprecated names.
    :ivar deprecated_check_links: Whether ``DS115`` scans link targets.
    :ivar deprecated_case_sensitive: Whether deprecated matching is case-sensitive.
    :ivar documentation_naming: ``DS118`` naming policy (``off``/``kebab``/``snake``).
    :ivar documentation_naming_allow: Exempt file names for ``DS118``.
    :ivar documentation_naming_directories: Whether ``DS118`` checks directories.
    :ivar documentation_naming_prefix_patterns: Validated prefix exceptions.
    :ivar report_templates_dir: Directory, relative to the scan root, holding extra
        report templates selectable by name with ``--format``, or ``None``. Validated
        lexically here; the template loader re-applies the full containment gate
        (no symlink out of the root) before listing or opening anything in it.
    :ivar report_show_clean_documents: Whether the text report also lists documents
        without problems (``--show-clean-documents``).
    :ivar report_include_run_meta: Whether the report context carries the per-run
        ``run.generated_at``/``run.id`` values; off keeps reports deterministic.
    :ivar telemetry_extensions: Report extension specs, ``builtin:<name>`` only
        (threat model 0007-extensions M1): a ``python:`` spec is accepted only from
        the command line, never from configuration. The extension resolver
        re-checks an injected ``Config`` with :func:`validate_telemetry_extensions`.
    :ivar telemetry_domains: The ``builtin:domain`` table, ``(glob, domain)`` pairs
        in configured array order (first match wins; threat model 0007-extensions
        M20-M23). Validated by :func:`validate_telemetry_domains` here and again by
        :func:`docsentinel.telemetry.builtin.domain.domain_for` for an injected
        ``Config``. Ignored unless ``builtin:domain`` is loaded.
    :ivar link_root: Base directory for site-root-absolute targets (a leading
        ``/``). ``"auto"`` (the default) uses the nearest ancestor of the scan root,
        the scan root included, that holds a ``.git`` entry (a directory or a file),
        falling back to the scan root; any other value is a path relative to the
        scan root that must name the scan root itself or an ancestor no higher than
        the nearest ``.git`` ancestor (for example ``"."`` for an MkDocs-style site
        or ``".."``). Validated lexically by :func:`validate_link_root` here; the
        ancestor, repository-ceiling and directory checks need the scan root and run
        in :func:`docsentinel.link_root.resolve_link_root`,
        which also re-validates an injected ``Config``. Relative targets are never
        affected.
    :ivar reference_scope: Which path-like references are checked (Milestone 0009
        Story 01.0). ``"links"`` (the default) checks links, images and
        ``@``-mentions and leaves ``DS103`` inert; ``"strict"`` also enables
        ``DS103`` for path-like inline code spans. ``--reference-scope`` overrides
        it for one run. An injected ``Config`` holding any other value keeps
        ``DS103`` inert (:func:`docsentinel.rules.opt_in_satisfied`).
    :ivar at_reference_extensions: File extensions (lowercase, without the dot) a
        relative ``@``-mention must end in to be checked by ``DS124``. 1 to 64
        entries of 1 to 16 ASCII letters or digits, compared case-insensitively;
        validated by :func:`validate_at_reference_extensions`, which stores them
        lowercased. An empty list is refused: use ``ignore = ["DS124"]`` instead.
    :ivar fact_check_backend: Registered fact-check backend ``DS302`` sends claims
        to (Milestone 0010, ADR 0007). Default ``"lenz"``; one of
        :data:`FACT_CHECK_BACKEND_NAMES`. Choosing a backend never grants network
        consent: that needs ``--use-external-api`` (or ``scan(use_external_api=True)``)
        and the backend's API-key environment variable, neither of which is a
        configuration key.
    :ivar fact_check_min_salience: Smallest salience score, ``0.0`` to ``1.0``
        inclusive (default ``0.5``), a candidate claim needs before ``DS302`` may send
        it.
    :ivar fact_check_min_confidence: Smallest backend confidence, ``0.0`` to ``1.0``
        inclusive (default ``0.6``), for a ``DS302`` verdict to become a finding.
    :ivar fact_check_max_claims_per_document: Most claims ``DS302`` sends per
        document; an integer from 1 to 50 (default ``3``).
    :ivar fact_check_max_claims_total: Most claims ``DS302`` sends per scan; an
        integer from 1 to 500 (default ``25``).
    :ivar fact_check_time_budget_seconds: Wall-clock budget, in whole seconds, of
        the ``DS302`` network stage of one scan; an integer from 1 to 3600 (default
        ``300``; ADR 0007 Contract 7).
    :ivar fact_check_combination: How ``DS302`` groups the selected claims into the facts it
        sends (default ``"each"``: one request per claim; ``"all"``: one request for all of
        them; or ranges such as ``"1-6,7-8"``). See :func:`parse_fact_combination`.
    """

    include: tuple[str, ...] = ("*.md", "**/*.md")
    exclude: tuple[str, ...] = (".git", ".venv", "node_modules")
    profile: str = "fast"
    select: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    baseline: Optional[str] = None
    max_grade_level: float = 14.0
    duplicate_similarity: float = 0.85
    min_information_score: float = 0.15
    docsig_paths: tuple[str, ...] = ("src",)
    min_document_words: int = 50
    min_paragraph_words: int = 5
    min_paragraph_chars: int = 30
    anchor_collision_policy: str = "explicit"
    anchor_renderer: str = "github"
    heading_level_policy: str = "no-skips"
    first_heading_level: int = 1
    multiple_h1_policy: str = "allow"
    setext_heading_support: bool = True
    empty_section_policy: str = "leaf"
    placeholder_content_policy: str = "ignore"
    image_content_counts: bool = True
    empty_section_min_text_chars: int = 0
    unused_reference_definitions: bool = False
    duplicate_reference_definitions: str = "warn"
    reference_label_normalization: str = "commonmark"
    fence_dialect: str = "gfm-subset"
    report_stray_closing_fence: bool = False
    require_fence_languages: bool = False
    allow_unlabelled_empty_fences: bool = True
    allowed_fence_languages: tuple[str, ...] = ()
    table_dialect: str = "gfm-subset"
    table_strict_cells: bool = True
    table_enable: bool = True
    navigation_indexes: tuple[str, ...] = ()
    navigation_required: tuple[str, ...] = ()
    navigation_unique_targets: bool = True
    navigation_check_missing: bool = True
    asset_extensions: tuple[str, ...] = ("png", "jpg", "jpeg", "svg", "webp", "gif", "pdf")
    check_html_asset_tags: bool = True
    check_markdown_images: bool = True
    check_srcset: bool = True
    missing_asset_policy: str = "error"
    root_escape_policy: str = "error"
    decode_percent_paths: bool = True
    windows_path_policy: str = "portable"
    document_id_field: str = "id"
    document_id_scope: str = "corpus"
    document_id_case_sensitive: bool = True
    document_id_required: bool = False
    deprecated_references_file: str = ""
    deprecated_check_prose: bool = True
    deprecated_check_links: bool = True
    deprecated_case_sensitive: bool = True
    documentation_naming: str = "off"
    documentation_naming_allow: tuple[str, ...] = ("README.md", "index.md")
    documentation_naming_directories: bool = True
    documentation_naming_prefix_patterns: tuple[str, ...] = ()
    report_templates_dir: Optional[str] = None
    report_show_clean_documents: bool = False
    report_include_run_meta: bool = False
    telemetry_extensions: tuple[str, ...] = ()
    telemetry_domains: tuple[tuple[str, str], ...] = ()
    link_root: str = "auto"
    reference_scope: str = "links"
    at_reference_extensions: tuple[str, ...] = (
        "md",
        "markdown",
        "mdx",
        "txt",
        "rst",
        "toml",
        "json",
        "yaml",
        "yml",
        "py",
    )
    fact_check_backend: str = "lenz"
    fact_check_min_salience: float = 0.5
    fact_check_min_confidence: float = 0.6
    fact_check_max_claims_per_document: int = 3
    fact_check_max_claims_total: int = 25
    fact_check_time_budget_seconds: int = 300
    fact_check_combination: str = "each"


def domain_glob_segments(glob: object, where: str) -> tuple[str, ...]:
    """Validate one ``telemetry_domains`` glob and return its segments (M20, M22).

    Grammar: the glob is split on ``/``; ``**`` is allowed only as a whole segment;
    ``*`` and ``?`` are wildcards inside one segment; everything else is a literal.
    Refused: ``[``, ``]``, ``{``, ``}``, ``\\``, ``!`` at the start of a segment, an
    empty segment (so a leading, trailing or doubled ``/``), a ``.`` or ``..``
    segment, ``**`` inside a longer segment, and any code point the ``neutralize``
    filter escapes (controls, bidi and zero-width characters, line separators, lone
    surrogates). The glob is repository-controlled, so it is never echoed.

    :param glob: The configured glob.
    :param where: The entry position for the message, e.g. ``telemetry_domains[3]``.
    :returns: The segments, in order.
    :raises ConfigError: For a non-string, empty, over-long or over-segmented glob, or
        any refused grammar element.
    """
    if type(glob) is not str or not glob:
        raise ConfigError(f"{where}.glob must be a nonempty string")
    if len(glob) > MAX_DOMAIN_GLOB_CHARS:
        raise ConfigError(f"{where}.glob is longer than {MAX_DOMAIN_GLOB_CHARS} characters")
    if neutralize(glob) != glob:
        raise ConfigError(f"{where}.glob holds a control, format or separator character")
    if any(character in _DOMAIN_GLOB_REFUSED for character in glob):
        raise ConfigError(f"{where}.glob uses [, ], {{, }} or a backslash, which are not supported")
    segments = tuple(glob.split("/"))
    if len(segments) > MAX_DOMAIN_GLOB_SEGMENTS:
        raise ConfigError(f"{where}.glob has more than {MAX_DOMAIN_GLOB_SEGMENTS} segments")
    for segment in segments:
        if not segment:
            raise ConfigError(f"{where}.glob has an empty segment (a leading, trailing or doubled /)")
        if segment in (".", ".."):
            raise ConfigError(f"{where}.glob has a . or .. segment")
        if segment.startswith("!"):
            raise ConfigError(f"{where}.glob has a segment starting with !, which is not supported")
        if "**" in segment and segment != "**":
            raise ConfigError(f"{where}.glob uses ** inside a segment; ** must be a whole segment")
    return segments


def _domain_entry(entry: object, where: str) -> tuple[str, str]:
    """Return one validated ``(glob, domain)`` pair.

    :param entry: A TOML table (``dict`` with exactly ``glob`` and ``domain``) or, in
        an injected :class:`Config`, a ``(glob, domain)`` tuple.
    :param where: The entry position for the message.
    :returns: The pair.
    :raises ConfigError: For any other shape, a bad glob or a domain outside
        :data:`DOMAIN_LABEL_PATTERN`.
    """
    if type(entry) is dict:
        if set(entry) != _DOMAIN_ENTRY_KEYS:
            raise ConfigError(f"{where} must be a table with exactly the keys glob and domain")
        glob, domain = entry["glob"], entry["domain"]
    elif type(entry) is tuple and len(entry) == 2:
        glob, domain = entry
    else:
        raise ConfigError(f"{where} must be a table with exactly the keys glob and domain")
    domain_glob_segments(glob, where)
    if type(domain) is not str or DOMAIN_LABEL_PATTERN.fullmatch(domain) is None:
        raise ConfigError(f"{where}.domain must match ^[a-z][a-z0-9_-]{{0,63}}$")
    return glob, domain


def validate_telemetry_domains(value: object) -> tuple[tuple[str, str], ...]:
    """Return the validated ``telemetry_domains`` table as ordered pairs (M20, M22, M23).

    The table is an array of tables (``[[telemetry_domains]]``), so a key-sorting
    TOML formatter cannot reorder it; the array order is kept as a tuple and the
    first matching entry wins. The size bound is checked before any entry is
    inspected, so an injected ``Config`` with a huge table fails fast.

    :param value: The configured array (a ``list`` from TOML) or the tuple of an
        injected :class:`Config`.
    :returns: ``(glob, domain)`` pairs, in configured order.
    :raises ConfigError: For a non-array, more than :data:`MAX_TELEMETRY_DOMAINS`
        entries, any invalid entry, or globs longer than
        :data:`MAX_DOMAIN_GLOBS_TOTAL_CHARS` characters in total.
    """
    if type(value) is not list and type(value) is not tuple:
        raise ConfigError("telemetry_domains must be an array of tables with glob and domain")
    if len(value) > MAX_TELEMETRY_DOMAINS:  # type: ignore[arg-type]
        raise ConfigError(f"telemetry_domains holds more than {MAX_TELEMETRY_DOMAINS} entries")
    pairs = tuple(
        _domain_entry(entry, f"telemetry_domains[{position}]")
        for position, entry in enumerate(value)  # type: ignore[arg-type]
    )
    if sum(len(glob) for glob, _ in pairs) > MAX_DOMAIN_GLOBS_TOTAL_CHARS:
        raise ConfigError(f"telemetry_domains globs hold more than {MAX_DOMAIN_GLOBS_TOTAL_CHARS} characters in total")
    return pairs


def validate_telemetry_extensions(value: object) -> tuple[str, ...]:
    """Return the validated ``telemetry_extensions`` entries, builtin specs only (M1).

    Every entry must be ``builtin:<name>``; any other entry, every ``python:`` spec
    included, is refused whatever the trust gate says, so a scanned repository's
    configuration can never choose code to execute. The rejected value is never
    echoed: it is repository-controlled.

    :param value: The configured list (a ``list`` from TOML, or the ``tuple`` of an
        injected :class:`Config`).
    :returns: The entries as a tuple, in configured order.
    :raises ConfigError: For a non-list, more than :data:`MAX_TELEMETRY_EXTENSIONS`
        entries, a non-``builtin:`` or malformed entry, or a duplicate entry.
    """
    if not isinstance(value, (list, tuple)):
        raise ConfigError("telemetry_extensions must be a list of builtin:<name> extension specs")
    if len(value) > MAX_TELEMETRY_EXTENSIONS:
        raise ConfigError(f"telemetry_extensions holds more than {MAX_TELEMETRY_EXTENSIONS} entries")
    seen: set[str] = set()
    for position, item in enumerate(value):
        if type(item) is not str or _BUILTIN_EXTENSION_SPEC_PATTERN.fullmatch(item) is None:
            raise ConfigError(
                f"telemetry_extensions[{position}] is not a builtin:<name> spec; configuration may name only "
                "builtin extensions"
            )
        if item in seen:
            raise ConfigError(f"telemetry_extensions[{position}] repeats an earlier entry")
        seen.add(item)
    return tuple(value)


def validate_at_reference_extensions(value: object) -> tuple[str, ...]:
    """Return the validated ``at_reference_extensions``, lowercased, in configured order (M20).

    Each entry must be a ``str`` of 1 to 16 ASCII letters or digits (no dot, no
    whitespace); entries are compared case-insensitively, so two entries equal
    after ASCII lowercasing are a duplicate. The list must hold 1 to
    :data:`MAX_AT_REFERENCE_EXTENSIONS` entries. The rejected value is never
    echoed: it is repository-controlled.

    :param value: The configured list (a ``list`` from TOML, or the ``tuple`` of an
        injected :class:`Config`).
    :returns: The lowercased entries as a tuple.
    :raises ConfigError: For a non-list, an empty list, more than
        :data:`MAX_AT_REFERENCE_EXTENSIONS` entries, a malformed entry, or a duplicate.
    """
    if not isinstance(value, (list, tuple)):
        raise ConfigError("at_reference_extensions must be a list of file extensions")
    if not value:
        raise ConfigError(
            'at_reference_extensions must not be empty; to turn off @-reference checks use ignore = ["DS124"]'
        )
    if len(value) > MAX_AT_REFERENCE_EXTENSIONS:
        raise ConfigError(f"at_reference_extensions holds more than {MAX_AT_REFERENCE_EXTENSIONS} entries")
    lowered: list[str] = []
    for position, item in enumerate(value):
        if type(item) is not str or _AT_REFERENCE_EXTENSION_PATTERN.fullmatch(item) is None:
            raise ConfigError(
                f"at_reference_extensions[{position}] must be 1 to 16 ASCII letters or digits, without a dot"
            )
        # The entry is ASCII, so str.lower() is exactly ASCII lowercasing here.
        extension = item.lower()
        if extension in lowered:
            raise ConfigError(f"at_reference_extensions[{position}] repeats an earlier entry (case-insensitive)")
        lowered.append(extension)
    return tuple(lowered)


#: The ``link_root`` value selecting the ``.git`` ancestor walk.
LINK_ROOT_AUTO = "auto"


def validate_link_root(value: object) -> str:
    """Return a lexically valid ``link_root`` value, else raise ``ConfigError``.

    The check is lexical and performs no filesystem access. ``"auto"`` is accepted
    as is; any other value must be a nonempty relative ``/``-separated path without
    control, format or separator code points, backslashes, a leading ``/`` or a
    Windows drive. Whether it names the scan root or an ancestor of it needs the
    scan root, so :func:`docsentinel.link_root.resolve_link_root` decides that. The
    value is repository-controlled, so it is never echoed.

    :param value: The configured value (from TOML or an injected :class:`Config`).
    :returns: The validated string.
    :raises ConfigError: For a non-string, empty or lexically unsafe value.
    """
    if type(value) is not str or not value:
        raise ConfigError('link_root must be "auto" or a nonempty path relative to the scan root')
    if value == LINK_ROOT_AUTO:
        return value
    if neutralize(value) != value or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise ConfigError("link_root holds a control, format or separator character")
    if value.startswith("/") or "\\" in value or re.match(r"^[A-Za-z]:", value):
        raise ConfigError("link_root must be a relative path with / separators (the scan root or an ancestor)")
    return value


def validate_fact_check_option(name: str, value: object) -> float:
    """Validate one numeric ``fact_check_*`` option and return its value (ADR 0007).

    The loader uses it for every configuration layer, and ``DS302`` uses it again for an
    injected ``Config`` (fail closed), so both give the same messages.

    :param name: A key of the integer bounds or one of the ``[0, 1]`` number options.
    :param value: The candidate value.
    :returns: The validated integer, or the number as a finite ``float``.
    :raises ConfigError: When the value is out of bounds or of the wrong type.
    :raises KeyError: When ``name`` is not a numeric ``fact_check_*`` option.
    """
    bounds = _FACT_CHECK_INT_BOUNDS.get(name)
    if bounds is not None:
        return _require_bounded_int(name, value, bounds[0], maximum=bounds[1])
    if name not in _FACT_CHECK_UNIT_OPTIONS:
        raise KeyError(name)
    number = _finite_number(value)
    if number is None or not (0.0 <= number <= 1.0):
        raise ConfigError(f"{name} must be a number between 0 and 1")
    return number


def parse_fact_combination(value: object) -> Union[str, tuple[tuple[int, int], ...]]:
    """Validate a ``fact_check_combination`` value and return its parsed form.

    ``each`` checks every selected claim on its own (the default), ``all`` joins every selected
    claim into one fact, and a comma-separated list of 1-based ranges (``1-6,7-8,9-16``) joins the
    claims of each range, numbered in send order (the ``extract-facts`` order). A range is ``N`` or
    ``N-M`` with ``1 <= N <= M <= fact_check_max_claims_total``'s upper bound (500); ranges may not
    overlap; a claim no range names is still checked on its own. The loader, the CLI flag and
    ``DS302`` (for an injected ``Config``) all use this function, so they give the same messages.

    :param value: The candidate value.
    :returns: ``"each"``, ``"all"`` or the ranges as ``(start, end)`` pairs in ascending order.
    :raises ConfigError: When the value is not one of those forms.
    """
    message = (
        "fact_check_combination must be 'each', 'all' or comma-separated claim ranges such as "
        "'1-6,7-8,9-16' (1-based, ascending, not overlapping, at most 500)"
    )
    if not isinstance(value, str) or not value or len(value) > MAX_FACT_COMBINATION_CHARS:
        raise ConfigError(message)
    if value in (FACT_COMBINATION_EACH, FACT_COMBINATION_ALL):
        return value
    limit = _FACT_CHECK_INT_BOUNDS["fact_check_max_claims_total"][1]
    ranges: list[tuple[int, int]] = []
    for part in value.split(","):
        match = _FACT_RANGE_RE.fullmatch(part)
        if match is None:
            raise ConfigError(message)
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) is not None else start
        if start > end or end > limit or (ranges and start <= ranges[-1][1]):
            raise ConfigError(message)
        ranges.append((start, end))
    return tuple(ranges)


def _require_bool(name: str, value: object) -> bool:
    """Return ``value`` when it is a real boolean, else raise ``ConfigError``.

    :param name: Option name used in the error message.
    :param value: Candidate value from the TOML table.
    :returns: The validated boolean.
    """
    if not isinstance(value, bool):
        raise ConfigError(f"{name} must be true or false")
    return value


def _require_bounded_int(name: str, value: object, minimum: int, *, maximum: Optional[int] = None) -> int:
    """Return ``value`` when it is an ``int`` within the bounds, else raise ``ConfigError``.

    Real booleans and floats (even integral ones such as ``5.0``) are rejected,
    matching the strictness of the other numeric options. With ``maximum`` the
    message names both bounds (``<name> must be an integer from 1 to 50``).

    :param name: Option name used in the error message.
    :param value: Candidate value from the TOML table.
    :param minimum: The smallest accepted integer value.
    :param maximum: The largest accepted integer value, or ``None`` for no upper bound.
    :returns: The validated integer.
    """
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        if maximum is not None:
            requirement = f"an integer from {minimum} to {maximum}"
        elif minimum == 0:
            requirement = "a non-negative integer"
        else:
            requirement = f"an integer >= {minimum}"
        raise ConfigError(f"{name} must be {requirement}")
    return value


def _require_enum(name: str, value: object, allowed: frozenset[str]) -> str:
    """Return ``value`` when it is one of ``allowed``, else raise ``ConfigError``.

    :param name: Option name used in the error message.
    :param value: Candidate value from the TOML table.
    :param allowed: The accepted vocabulary for this option.
    :returns: The validated string.
    """
    if not isinstance(value, str) or value not in allowed:
        joined = ", ".join(sorted(allowed))
        raise ConfigError(f"{name} must be one of: {joined}")
    return value


def _require_str_list(name: str, value: object) -> tuple[str, ...]:
    """Return a tuple of nonempty strings, else raise ``ConfigError``.

    :param name: Option name used in the error message.
    :param value: Candidate value from the TOML table.
    :returns: The validated strings as a tuple.
    """
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ConfigError(f"{name} must be a list of nonempty strings")
    return tuple(value)


def _require_fence_language_list(name: str, value: object) -> tuple[str, ...]:
    """Return a tuple of single-token fence languages, else raise ``ConfigError``.

    A fence language is the first whitespace-delimited token of a fence info
    string, so an allowlist entry that itself contains whitespace (``"python
    bash"``, a leading space, or an embedded tab) could never match any single
    fence language and almost certainly signals a malformed config. Such entries
    are rejected; ordinary tokens with punctuation such as ``"c++"`` or
    ``"objective-c"`` remain valid.

    :param name: Option name used in the error message.
    :param value: Candidate value from the TOML table.
    :returns: The validated single-token languages as a tuple.
    """
    languages = _require_str_list(name, value)
    for language in languages:
        if any(character.isspace() for character in language):
            raise ConfigError(f"{name} entries must be single tokens without whitespace: {language!r}")
    return languages


def _is_within_root(path_part: str) -> bool:
    """Return whether a relative path stays lexically within the scan root.

    The check is lexical and performs no filesystem access: absolute paths,
    Windows drive/UNC paths, backslash separators, and ``..`` escapes above the
    root are rejected.

    :param path_part: A candidate ``/``-separated relative path.
    :returns: ``True`` when the path is root-relative and does not escape.
    """
    if path_part.startswith("/") or "\\" in path_part:
        return False
    if re.match(r"^[A-Za-z]:", path_part):
        return False
    depth = 0
    for part in path_part.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if depth == 0:
                return False
            depth -= 1
        else:
            depth += 1
    return True


def _require_root_path_list(name: str, value: object) -> tuple[str, ...]:
    """Return a tuple of root-relative paths, else raise ``ConfigError``.

    :param name: Option name used in the error message.
    :param value: Candidate value from the TOML table.
    :returns: The validated paths as a tuple.
    """
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ConfigError(f"{name} must be a list of nonempty paths under the scan root")
    for item in value:
        if not _is_within_root(item):
            raise ConfigError(f"{name} entries must stay within the scan root: {item}")
    return tuple(value)


def _require_known_options(options: dict[str, object]):
    """Raise ``ConfigError`` when ``options`` holds a key outside the configuration schema.

    Shared by the TOML and JSON readers so both give the same message.

    :param options: The raw options mapping.
    :raises ConfigError: Naming every unknown key, sorted and comma-joined.
    """
    unknown = set(options) - _CONFIG_OPTIONS
    if unknown:
        raise ConfigError(f"Unknown config options: {', '.join(sorted(unknown))}")


def _load_toml_table(source: Path, *, wrapped: bool) -> dict[str, object]:
    """Load the raw options of a standalone or pyproject TOML table.

    A number beyond Python's integer-string conversion limit is a ``ConfigError``
    (``number out of range``) instead of a stray ``ValueError`` (threat model
    0009-user-settings F1), so ``doctor`` survives a repository's TOML.

    :param source: The TOML file to read.
    :param wrapped: Whether to unwrap a ``[tool.doc_sentinel]`` table.
    :returns: The raw options mapping.
    :raises ConfigError: For an unreadable or malformed file or an unknown option.
    """
    try:
        with source.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Cannot read {source}: {exc}") from exc
    except ValueError as exc:
        # tomllib lets the integer-string digit limit escape as a plain ValueError.
        raise ConfigError(f"Cannot read {source}: number out of range") from exc

    options: object = data
    if wrapped:
        tool = data.get("tool")
        if not isinstance(tool, dict) or "doc_sentinel" not in tool:
            logger.debug("%s has no [tool.doc_sentinel] table; using defaults", safe(source))
            return {}
        options = tool["doc_sentinel"]
        if not isinstance(options, dict):
            raise ConfigError("Unknown config options: tool.doc_sentinel must be a table")

    _require_known_options(options)
    return options


def _json_config_error(reason: str) -> ConfigError:
    """Return the path-free ``ConfigError`` of a JSON config failure (ADR 0005 Contract 5).

    :param reason: One of the fixed reason phrases; never file content.
    :returns: ``Cannot read JSON config: <reason>``.
    """
    return ConfigError(f"Cannot read JSON config: {reason}")


def _read_config_once(
    source: Path,
    *,
    check_descriptor: Optional[Callable[[os.stat_result], None]] = None,
) -> bytes:
    """Open ``source`` once and return at most ``MAX_JSON_CONFIG_BYTES + 1`` bytes from it.

    The order is fixed (threat model 0009-user-settings R7, amendment A1): an
    ``os.stat()`` pre-check refuses a non-regular file before any open, so a FIFO or
    device is never opened; one ``os.open()`` with ``O_NONBLOCK | O_NOCTTY``; then
    ``os.fstat()`` of that descriptor, which is authoritative, refuses a non-regular
    file again and runs ``check_descriptor`` (the user settings layer passes its
    ownership and mode gate here); then a bounded read from the same descriptor,
    closed in ``finally``. The file is never reopened.

    :param source: The file to read.
    :param check_descriptor: Optional extra check on the descriptor's
        ``os.fstat()`` result. It must raise only ``ConfigError`` to refuse the file:
        an ``OSError`` it raises is rewritten as ``not readable``. Checks of the
        holding directories (threat model R3) belong before this call.
    :returns: The bytes read; a result longer than ``MAX_JSON_CONFIG_BYTES`` means
        the file is too large.
    :raises ConfigError: ``not a regular file``, ``not readable`` for any
        ``OSError``, or whatever ``check_descriptor`` raises (unchanged).
    """
    try:
        if not stat.S_ISREG(os.stat(source).st_mode):
            raise _json_config_error("not a regular file")
        descriptor = os.open(source, _JSON_OPEN_FLAGS)
    except OSError:
        raise _json_config_error("not readable") from None
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode):
            raise _json_config_error("not a regular file")
        if check_descriptor is not None:
            check_descriptor(status)
        chunks: list[bytes] = []
        remaining = MAX_JSON_CONFIG_BYTES + 1
        while remaining > 0:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    except OSError:
        raise _json_config_error("not readable") from None
    finally:
        os.close(descriptor)


def _json_object_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """``object_pairs_hook`` refusing a duplicate key at any depth (threat model U9).

    :param pairs: The decoded key/value pairs of one JSON object, in file order.
    :returns: The object as a ``dict``.
    :raises ConfigError: Naming the duplicate key, bounded to 80 characters and
        neutralised.
    """
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _json_config_error(f"duplicate key {safe(key, _JSON_DUPLICATE_KEY_ECHO_LIMIT)}")
        result[key] = value
    return result


def _json_refuse_constant(_name: str) -> object:
    """``parse_constant`` refusing ``NaN``, ``Infinity`` and ``-Infinity``.

    :param _name: The constant's spelling (not echoed).
    :raises ConfigError: Always.
    """
    raise _json_config_error("NaN and Infinity are not allowed")


def _json_finite_float(text: str) -> float:
    """``parse_float`` refusing a literal that overflows to infinity (``1e400``).

    :param text: The numeric literal (not echoed).
    :returns: The finite float.
    :raises ConfigError: ``number out of range`` for a non-finite result.
    """
    number = float(text)
    if not math.isfinite(number):
        raise _json_config_error("number out of range")
    return number


def _json_check_values(value: object):
    """Refuse ``null`` and lone surrogates anywhere in a parsed JSON value.

    JSON can spell a lone surrogate (``"\\ud800"``) that TOML cannot; in a path option it
    would surface later as a ``UnicodeEncodeError`` rather than a ``ConfigError``
    (threat model 0009-user-settings T03-1), so every ``str`` key and value is
    checked. The walk is iterative (an explicit stack), so a value nested as deeply
    as the C scanner accepts can never raise ``RecursionError`` here (threat model
    M13). Neither the offending key nor the value is echoed.

    :param value: The parsed value.
    :raises ConfigError: ``null is not allowed; omit the key`` or
        ``lone surrogate is not allowed``.
    """
    stack: list[object] = [value]
    while stack:
        item = stack.pop()
        if item is None:
            raise _json_config_error("null is not allowed; omit the key")
        if type(item) is str:
            if _LONE_SURROGATE_PATTERN.search(item) is not None:
                raise _json_config_error("lone surrogate is not allowed")
        elif type(item) is dict:
            stack.extend(item.keys())
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)


def _parse_json_options(data: bytes) -> dict[str, object]:
    """Parse the bytes of one JSON config file strictly into a raw options mapping.

    Steps 2 to 6 of ADR 0005 Contract 2's ``load_json_options()``: size cap, strict
    UTF-8 without a byte-order mark (only the decoded ``str`` reaches
    ``json.loads()``), duplicate keys, non-finite numbers, nesting, the integer-string
    limit, the top-level shape, ``null`` or a lone surrogate anywhere and unknown keys. No message echoes
    file content.

    :param data: The bytes read by :func:`_read_config_once`.
    :returns: The raw options mapping.
    :raises ConfigError: With a fixed, path-free reason phrase.
    """
    if len(data) > MAX_JSON_CONFIG_BYTES:
        raise _json_config_error("larger than 1 MiB")
    if data.startswith(b"\xef\xbb\xbf"):
        raise _json_config_error("starts with a byte-order mark")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _json_config_error("not valid UTF-8") from exc
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_json_object_pairs,
            parse_constant=_json_refuse_constant,
            parse_float=_json_finite_float,
        )
    except ConfigError:
        raise
    except RecursionError as exc:
        raise _json_config_error("nested too deeply") from exc
    except json.JSONDecodeError as exc:
        raise _json_config_error(f"invalid JSON at line {exc.lineno}, column {exc.colno}") from exc
    except ValueError as exc:
        # The integer-string digit limit (a plain ValueError from int()).
        raise _json_config_error("number out of range") from exc
    if type(parsed) is not dict:
        raise _json_config_error("the top level must be an object")
    _json_check_values(parsed)
    _require_known_options(parsed)
    return parsed


def load_json_options(source: Path) -> dict[str, object]:
    """Read one JSON config object strictly; raise ``ConfigError`` on any deviation.

    Follows ADR 0005 Contract 2: one open through the open-once reader (no ownership
    or mode check here), at most ``MAX_JSON_CONFIG_BYTES`` bytes, strict UTF-8
    without a byte-order mark, no duplicate key at any depth, no ``NaN``,
    ``Infinity`` or overflowing number, no ``null``, an object at the top level and
    only known option names. ``5`` stays an ``int`` and ``5.0`` a ``float``, as in
    TOML, so the shared validators behave the same. Messages carry no path and no
    file content. The file is read once and nothing is cached.

    :param source: The JSON file to read.
    :returns: The raw options mapping, to be validated by the shared builder.
    :raises ConfigError: ``Cannot read JSON config: <reason>`` or the shared
        ``Unknown config options: ...`` message.
    """
    return _parse_json_options(_read_config_once(source))


def _finite_number(value: object) -> Optional[float]:
    """Return ``value`` as a finite ``float``, or ``None`` when it is not one.

    Booleans, non-numbers, ``nan``, infinities and integers too large for a float
    all give ``None``, so each caller raises its option's existing message (threat
    model 0009-user-settings U8, amendment A6).

    :param value: The configured value.
    :returns: The finite float, or ``None``.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except OverflowError:
        # An integer too large for a float is out of range like an infinity.
        number = math.inf
    return number if math.isfinite(number) else None


def _read_project_options(root: Path, path: Optional[Path]) -> tuple[Optional[dict[str, object]], Optional[Path], str]:
    """Read the raw options of the explicit or discovered project configuration.

    An explicit ``path`` named ``pyproject.toml`` is read as a wrapped table, one
    whose suffix is ``.json`` (case-insensitive) as strict JSON, anything else as
    standalone TOML. Discovery is unchanged: a standalone ``docsentinel.toml`` (or
    its alias ``doc_sentinel.toml``), else ``pyproject.toml``.

    :param root: The scan root directory used for discovery.
    :param path: An explicit config file, or ``None`` to discover one.
    :returns: The raw options mapping (``None`` when no configuration file exists),
        the file read (or ``None``) and its kind: ``toml``, ``pyproject``, ``json``
        or ``none`` (ADR 0005 Contract 2, ``ConfigSources.project_kind``).
    :raises ConfigError: For both standalone names in one root, or any read error.
    """
    if path is not None:
        source = path
        wrapped = source.name == "pyproject.toml"
        if not wrapped and source.suffix.lower() == ".json":
            logger.debug("loading config %s (json)", safe(source))
            return load_json_options(source), source, "json"
    else:
        standalones = [root / name for name in STANDALONE_CONFIG_NAMES if (root / name).exists()]
        pyproject = root / "pyproject.toml"
        if len(standalones) > 1:
            names = " and ".join(path.name for path in standalones)
            raise ConfigError(f"found both {names} in {root}; keep only one")
        if standalones:
            source = standalones[0]
            wrapped = False
        elif pyproject.exists():
            source = pyproject
            wrapped = True
        else:
            logger.debug("no config file in %s; using defaults", safe(root))
            return None, None, "none"

    logger.debug("loading config %s%s", safe(source), " ([tool.doc_sentinel])" if wrapped else "")
    return _load_toml_table(source, wrapped=wrapped), source, "pyproject" if wrapped else "toml"


@dataclass(frozen=True)
class ConfigSources:
    """Where the layers of an effective :class:`Config` came from (ADR 0005 Contract 2).

    It holds option *names* only, never values. It is never logged as an object and
    never enters a report context, because its paths are absolute (threat model
    0009-user-settings U11, A7); render a path through the tilde form instead.

    :ivar user: The loaded user settings file as resolved from the environment (not
        symlink-resolved), or ``None``.
    :ivar user_state: ``loaded``, ``missing``, ``off`` or ``no-home``.
    :ivar project: The loaded project configuration file, or ``None``.
    :ivar project_kind: ``toml``, ``pyproject``, ``json`` or ``none``.
    :ivar user_options: Option names set by the user file, sorted.
    :ivar project_options: Option names set by the project file, sorted.
    """

    user: Optional[Path]
    user_state: str
    project: Optional[Path]
    project_kind: str
    user_options: tuple[str, ...] = ()
    project_options: tuple[str, ...] = ()


def _home_directory() -> Optional[Path]:
    """Return the absolute home directory, or ``None`` when it is unknown or unsafe.

    ``Path.home()`` failing, a relative home (``HOME=.``), the filesystem root (an
    empty ``HOME``) or one holding a control, format or separator character all give
    ``None``, so a home can never turn the user settings path into a
    current-directory path (threat model 0009-user-settings U3, A4). No filesystem
    call is made.

    :returns: The home directory, or ``None``.
    """
    try:
        home = Path.home()
    except (RuntimeError, KeyError, OSError, ValueError) as exc:
        # Only the exception type: its text may hold a user name.
        logger.debug("user settings: home directory unknown (%s)", type(exc).__name__)
        return None
    if not home.is_absolute() or home == Path(home.anchor) or not _is_plain_path_text(str(home)):
        # A filesystem-root home (``Path.home()`` maps an empty ``HOME`` to ``/``) is
        # no real home either.
        return None
    return home


def _is_plain_path_text(text: str) -> bool:
    """Return whether ``text`` holds no control, format, separator or surrogate character.

    :param text: A path string from the environment.
    :returns: ``True`` when every character is printable path text.
    """
    return not any(unicodedata.category(char) in _PATH_REFUSED_CATEGORIES for char in text)


def user_settings_path() -> tuple[Optional[Path], str]:
    """Resolve the user settings file from the environment, without touching the filesystem.

    The only reader of ``DOCSENTINEL_SETTINGS``, ``XDG_DATA_HOME`` and (through
    ``Path.home()``) ``HOME`` (ADR 0005 Contract 1; threat model U13). The states are:

    * ``off``: ``DOCSENTINEL_SETTINGS`` is exactly ``off``; the path is ``None``.
    * ``env``: ``DOCSENTINEL_SETTINGS`` names an absolute path; it must exist.
    * ``default``: the file under ``XDG_DATA_HOME`` when it is set, absolute and
      plain, else under ``$HOME/.local/share``; a missing file is skipped.
    * ``no-home``: no override and the home directory is unknown or relative; the
      path is ``None``.

    An empty ``DOCSENTINEL_SETTINGS`` counts as unset. Every returned path is absolute.

    :returns: The settings path (or ``None``) and its state.
    :raises ConfigError: When ``DOCSENTINEL_SETTINGS`` is relative or holds a control
        character. The value is never echoed.
    """
    override = os.environ.get(USER_SETTINGS_ENV, "")
    if override == USER_SETTINGS_OFF:
        return None, "off"
    if override:
        if not _is_plain_path_text(override) or not os.path.isabs(override):
            raise ConfigError(f'{USER_SETTINGS_ENV} must be an absolute path or "{USER_SETTINGS_OFF}"')
        return Path(override), "env"
    data_home = os.environ.get(_XDG_DATA_HOME_ENV, "")
    if data_home and os.path.isabs(data_home) and _is_plain_path_text(data_home):
        return Path(data_home) / _USER_SETTINGS_RELATIVE, "default"
    home = _home_directory()
    if home is None:
        return None, "no-home"
    candidate = home / _HOME_DATA_RELATIVE / _USER_SETTINGS_RELATIVE
    if not candidate.is_absolute():
        # Defensive: the home was checked, but never stat a relative path (threat model A4).
        return None, "no-home"
    return candidate, "default"


def _tilde_path(path: Path) -> str:
    """Return ``path`` for a message or log line, with the home directory shown as ``~``.

    The home matches lexically or through its real path (threat model U11, M15);
    the symlink target of ``path`` itself is never shown. The result passes through
    :func:`~docsentinel.log.safe`, so it is neutralised and bounded.

    :param path: The user settings path.
    :returns: The display form.
    """
    text = str(path)
    home = _home_directory()
    if home is not None:
        for base in dict.fromkeys((str(home), os.path.realpath(home))):
            base = base.rstrip(os.sep)
            if not base:
                continue  # A home of "/" would make every path "~".
            if text == base:
                text = "~"
                break
            if text.startswith(base + os.sep):
                text = "~" + text[len(base) :]
                break
    return safe(text)


def _user_settings_exist(path: Path, *, required: bool) -> bool:
    """Return whether the user settings file exists (ADR 0005 Contract 3 step 1).

    The file is absent only when ``os.stat()`` raises ``FileNotFoundError`` or
    ``NotADirectoryError`` and ``os.path.lexists()`` is false, so a dangling symlink
    or any other ``OSError`` fails closed (threat model U7, A5).

    :param path: The absolute settings path.
    :param required: Whether the invoker named the file (``DOCSENTINEL_SETTINGS``);
        then an absent file is an error too.
    :returns: ``False`` for an absent default-location file, else ``True``.
    :raises ConfigError: ``Cannot read JSON config: not readable``.
    """
    try:
        os.stat(path)
    except (FileNotFoundError, NotADirectoryError):
        if required or os.path.lexists(path):
            raise _json_config_error("not readable") from None
        return False
    except (OSError, ValueError):
        raise _json_config_error("not readable") from None
    return True


def _owner_trusted(uid: int) -> bool:
    """Return whether ``uid`` may own a user settings object (threat model R2-R4).

    The effective user or root; when running as root only root.

    :param uid: The ``st_uid`` of the file or directory.
    :returns: ``True`` when the owner is trusted.
    """
    return uid in (os.geteuid(), 0)


def _user_settings_link_directories(path: Path, *, final_is_directory: bool = False) -> dict[str, list[int]]:
    """Return the physical directories R3 applies to, walking every symbolic link.

    The path is resolved one component at a time, as the kernel does, with
    ``os.lstat()`` and ``os.readlink()`` only (nothing is opened). The directory
    holding each symbolic link met on the way, a file link or a directory link at any
    depth of the chain, is collected, then the directory holding the final target.
    Without a symlink that is just the directory holding the file. Ancestors that
    hold no link are not collected (residual U1). A relative link target resolves
    against the directory holding the link, and ``..`` against the physical directory
    reached so far (threat model 0009-user-settings T04-1). The ``lstat()`` owner of
    each link is kept beside its directory, so a link planted by another user in a
    shared sticky directory can be refused (T04-4).

    :param path: The absolute settings path, known to exist.
    :param final_is_directory: Collect the final target itself instead of the
        directory holding it; ``init --user`` passes the deepest existing directory
        it is about to create entries in (threat model U15).
    :returns: The directories, physical and absolute, in walk order without repeats,
        each mapped to the owners of the links met in it (empty for the directory
        holding only the final target).
    :raises ConfigError: ``too many symbolic links`` after
        :data:`_MAX_SYMLINK_HOPS` links, or ``Cannot read JSON config: not
        readable`` for any ``OSError``.
    """
    text = str(path)
    current = os.sep
    pending = [part for part in text.split(os.sep) if part]
    directories: dict[str, list[int]] = {}
    hops = 0
    while pending:
        name = pending.pop(0)
        if name == ".":
            continue
        if name == "..":
            current = os.path.dirname(current)
            continue
        candidate = os.path.join(current, name)
        try:
            link_status = os.lstat(candidate)
            is_link = stat.S_ISLNK(link_status.st_mode)
            target = os.readlink(candidate) if is_link else ""
        except (OSError, ValueError):
            # ``from None``: the OSError text would carry the absolute path (T04-2).
            raise _json_config_error("not readable") from None
        if not is_link:
            current = candidate
            continue
        hops += 1
        if hops > _MAX_SYMLINK_HOPS:
            raise ConfigError(_GATE_TOO_MANY_LINKS)
        directories.setdefault(current, []).append(link_status.st_uid)
        if os.path.isabs(target):
            current = os.sep
        pending[:0] = [part for part in target.split(os.sep) if part]
    directories.setdefault(current if final_is_directory else os.path.dirname(current), [])
    return directories


def _check_user_settings_directories(path: Path, *, final_is_directory: bool = False):
    """Apply threat model R3 to every directory holding a link or the user settings file.

    The directory holding the configured path, the directory holding each symbolic
    link of the chain (file and directory links alike) and the directory holding
    the final target must each be owned by the effective user or root and have no
    group/other write bit unless the sticky bit is set (T04-1). In such a shared
    sticky directory every link must also be owned by the effective user or root,
    the ``protected_symlinks`` rule that macOS and BSD lack (T04-4). Ancestors
    holding no link are not checked (residual U1).

    :param path: The absolute settings path, known to exist.
    :param final_is_directory: ``path`` is an existing directory that is checked
        itself, with every link on the way to it (``init --user`` before it creates
        anything, threat model U15).
    :raises ConfigError: ``its directory is owned by another user or writable by
        others``, ``too many symbolic links`` or ``Cannot read JSON config: not
        readable``.
    """
    for directory, link_owners in _user_settings_link_directories(path, final_is_directory=final_is_directory).items():
        try:
            status = os.stat(directory)
        except (OSError, ValueError):
            raise _json_config_error("not readable") from None
        writable = status.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        if not _owner_trusted(status.st_uid) or (writable and not status.st_mode & stat.S_ISVTX):
            raise ConfigError(_GATE_DIRECTORY)
        if writable and not all(_owner_trusted(uid) for uid in link_owners):
            # A sticky shared directory: a link another user planted there is refused.
            raise ConfigError(_GATE_DIRECTORY)


def _check_user_settings_descriptor(status: os.stat_result):
    """Apply threat model R2 to ``os.fstat()`` of the descriptor the file is read from.

    Passed to :func:`_read_config_once` as ``check_descriptor``, so the decision is
    made on the opened object, not on a path that may have been swapped (U2). It
    raises only :class:`ConfigError` (threat model T03-3).

    :param status: ``os.fstat()`` of the opened descriptor (a regular file).
    :raises ConfigError: ``owned by another user`` or ``writable by group or others
        (run chmod go-w on it)``.
    """
    if not _owner_trusted(status.st_uid):
        raise ConfigError(_GATE_FILE_OWNER)
    if status.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ConfigError(_GATE_FILE_MODE)


def _read_user_options(path: Path) -> dict[str, object]:
    """Gate, read, parse and C6-check one user settings file (ADR 0005 Contract 3 steps 2-5).

    The order is threat model R7: R3 directory checks, then the open-once reader with
    the R2 check on the descriptor's ``fstat()``, then a bounded read from the same
    descriptor. Ownership and mode are skipped on non-POSIX with one ``DEBUG`` line
    (R1). Refused C6 keys are rejected before any value validation, then the mapping
    is validated alone so a bad value is attributed to this file.

    :param path: The absolute settings path, known to exist.
    :returns: The raw user options.
    :raises ConfigError: Unprefixed; the caller adds the ``user settings`` prefix.
    """
    check_descriptor: Optional[Callable[[os.stat_result], None]] = None
    if os.name == "posix":
        _check_user_settings_directories(path)
        check_descriptor = _check_user_settings_descriptor
    else:
        logger.debug("user settings: permission check skipped (non-POSIX)")
    options = _parse_json_options(_read_config_once(path, check_descriptor=check_descriptor))
    refused = sorted(set(options) & USER_SETTINGS_REFUSED_KEYS)
    if refused:
        raise ConfigError(f"repository-relative options cannot be set in user settings: {', '.join(refused)}")
    _build_config(options)
    return options


def _load_user_layer(user_settings: bool) -> tuple[dict[str, object], Optional[Path], str]:
    """Locate and load the user settings layer (ADR 0005 Contract 3 steps 1-5).

    :param user_settings: ``False`` turns the layer off without reading the
        environment (threat model U13).
    :returns: The user options (empty unless loaded), the loaded path (or ``None``)
        and the ``ConfigSources.user_state``.
    :raises ConfigError: For a bad ``DOCSENTINEL_SETTINGS`` value (unprefixed) or any
        failure of an existing or invoker-named file, prefixed
        ``user settings <tilde path>: ``.
    """
    if not user_settings:
        logger.debug("user settings: disabled")
        return {}, None, "off"
    path, state = user_settings_path()
    if state == "off":
        logger.debug("user settings: disabled")
        return {}, None, "off"
    if path is None:
        logger.debug("user settings: no home directory")
        return {}, None, "no-home"
    try:
        if not _user_settings_exist(path, required=state == "env"):
            logger.debug("user settings: missing")
            return {}, None, "missing"
        options = _read_user_options(path)
    except ConfigError as exc:
        raise ConfigError(f"user settings {_tilde_path(path)}: {exc}") from None
    # Only option names (already checked against the known set), never their values.
    logger.debug("user settings %s: loaded, options set: %s", _tilde_path(path), ", ".join(sorted(options)) or "none")
    return options, path, "loaded"


def load_config_with_sources(
    root: Path, path: Optional[Path] = None, *, user_settings: bool = True
) -> tuple[Config, ConfigSources]:
    """Resolve configuration layers 1 to 3 and report where each came from.

    Layers, lowest first (plan C1, ADR 0005 Contract 1): the :class:`Config`
    defaults, the user settings JSON file (unless off; never the C6 keys), then the
    project configuration, explicit ``path`` or discovered exactly as by
    :func:`load_config`. A key's value is replaced as a whole, never merged. Command
    line flags (layer 4) are applied by the caller. The user file is read once per
    call; nothing is cached.

    :param root: The scan root directory used for discovery.
    :param path: An explicit project config file, or ``None`` to discover one. It
        replaces discovery only, never the user layer.
    :param user_settings: ``False`` skips the user layer and never reads the
        environment.
    :returns: The effective :class:`Config` and its :class:`ConfigSources`.
    :raises ConfigError: For an unreadable, malformed, refused or invalid
        configuration. A user-file failure is prefixed ``user settings <tilde
        path>: ``; project messages are unchanged.
    """
    user_options, user_path, user_state = _load_user_layer(user_settings)
    project_options, project_path, project_kind = _read_project_options(root, path)
    if project_options is not None:
        # Only option names (already checked against the known set), never their values.
        logger.debug("config options set: %s", ", ".join(sorted(project_options)) or "none")
    sources = ConfigSources(
        user=user_path,
        user_state=user_state,
        project=project_path,
        project_kind=project_kind,
        user_options=tuple(sorted(user_options)),
        project_options=tuple(sorted(project_options or {})),
    )
    if not user_options and project_options is None:
        return Config(), sources
    # Every validator is per key and the user mapping was validated alone, so a
    # failure here comes from a project value and keeps its unprefixed message.
    return _build_config({**user_options, **(project_options or {})}), sources


def load_config(root: Path, path: Optional[Path] = None, *, user_settings: bool = True) -> Config:
    """Load the user settings layer and an explicit or discovered project config.

    A standalone ``docsentinel.toml`` (or its alias ``doc_sentinel.toml``) wins
    over ``[tool.doc_sentinel]`` in ``pyproject.toml``; when none exists,
    defaults are returned. Both standalone names in one root is ambiguous and
    raises :class:`ConfigError`. An explicit ``path`` bypasses discovery; one whose
    suffix is ``.json`` (case-insensitive) is read by :func:`load_json_options`. TOML
    and JSON options are validated by the same builder, so they give the same
    messages. The user settings file (``DOCSENTINEL_SETTINGS``, else under
    ``XDG_DATA_HOME`` or ``~/.local/share``) is layered beneath the project
    configuration; see :func:`load_config_with_sources`. A :class:`Config` injected
    directly by a library caller is used verbatim by the engine and never consults
    files or the environment.

    :param root: The scan root directory used for discovery.
    :param path: An explicit config file, or ``None`` to discover one.
    :param user_settings: ``False`` skips the user settings layer.
    :returns: The validated :class:`Config`.
    :raises ConfigError: For an unreadable, malformed or invalid configuration.
    """
    return load_config_with_sources(root, path, user_settings=user_settings)[0]


def _build_config(options: dict[str, object]) -> Config:
    """Validate a raw options mapping and build the :class:`Config` from it.

    The single validation path for every configuration source (ADR 0005 Contract 2):
    TOML, the pyproject table and JSON all reach :class:`Config` only through here.
    Every validator is per key. Float-valued options must be finite and
    float-convertible (threat model 0009-user-settings A6).

    :param options: The raw options mapping; keys are already known option names.
    :returns: The validated :class:`Config`.
    :raises ConfigError: For the first invalid option.
    """
    defaults = Config()
    include = options.get("include", list(defaults.include))
    exclude = options.get("exclude", list(defaults.exclude))
    profile = options.get("profile", defaults.profile)
    select = options.get("select", list(defaults.select))
    ignore = options.get("ignore", list(defaults.ignore))
    baseline = options.get("baseline", defaults.baseline)
    max_grade_level = _finite_number(options.get("max_grade_level", defaults.max_grade_level))
    duplicate_similarity = _finite_number(options.get("duplicate_similarity", defaults.duplicate_similarity))
    min_information_score = _finite_number(options.get("min_information_score", defaults.min_information_score))
    docsig_paths = options.get("docsig_paths", list(defaults.docsig_paths))
    for name, value in (("include", include), ("exclude", exclude)):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ConfigError(f"{name} must be a list of nonempty patterns")
    if not isinstance(docsig_paths, list) or not all(isinstance(item, str) and item for item in docsig_paths):
        raise ConfigError("docsig_paths must be a list of nonempty paths")
    for name, value in (("select", select), ("ignore", ignore)):
        if not isinstance(value, list) or not all(
            isinstance(item, str) and _SELECTOR_PATTERN.fullmatch(item) for item in value
        ):
            raise ConfigError(f"{name} must be a list of DS rule codes or prefixes")
    if not isinstance(profile, str) or profile not in ("fast", "standard", "deep"):
        raise ConfigError("profile must be fast, standard, or deep")
    if baseline is not None and (not isinstance(baseline, str) or not baseline):
        raise ConfigError("baseline must be a nonempty string")
    if max_grade_level is None or max_grade_level <= 0:
        raise ConfigError("max_grade_level must be a positive number")
    if duplicate_similarity is None or not (0.0 <= duplicate_similarity <= 1.0):
        raise ConfigError("duplicate_similarity must be a number between 0 and 1")
    if min_information_score is None or not (0.0 <= min_information_score <= 1.0):
        raise ConfigError("min_information_score must be a number between 0 and 1")

    extra = _load_extra_options(options, defaults)

    return Config(
        include=tuple(include),
        exclude=tuple(exclude),
        profile=profile,
        select=tuple(select),
        ignore=tuple(ignore),
        baseline=baseline,
        max_grade_level=max_grade_level,
        duplicate_similarity=duplicate_similarity,
        min_information_score=min_information_score,
        docsig_paths=tuple(docsig_paths),
        **extra,
    )


def _load_extra_options(options: dict[str, object], defaults: Config) -> dict[str, object]:
    """Validate the Story 02–14 and Milestone 0007 typed options into ``Config`` keyword arguments.

    :param options: The raw options mapping (from TOML or JSON).
    :param defaults: A default :class:`Config` used to source field defaults.
    :returns: A mapping of validated keyword arguments for :class:`Config`.
    """
    extra: dict[str, object] = {}
    for name in _BOOL_OPTIONS:
        extra[name] = _require_bool(name, options.get(name, getattr(defaults, name)))
    for name, allowed in _ENUM_OPTIONS.items():
        extra[name] = _require_enum(name, options.get(name, getattr(defaults, name)), allowed)
    for name in _STR_LIST_OPTIONS:
        if name in options:
            validate = _require_fence_language_list if name == "allowed_fence_languages" else _require_str_list
            extra[name] = validate(name, options[name])
        else:
            extra[name] = getattr(defaults, name)
    for name in _ROOT_PATH_LIST_OPTIONS:
        if name in options:
            extra[name] = _require_root_path_list(name, options[name])
        else:
            extra[name] = getattr(defaults, name)

    first_heading_level = options.get("first_heading_level", defaults.first_heading_level)
    if (
        not isinstance(first_heading_level, int)
        or isinstance(first_heading_level, bool)
        or not (1 <= first_heading_level <= 6)
    ):
        raise ConfigError("first_heading_level must be an integer between 1 and 6")
    extra["first_heading_level"] = first_heading_level

    min_text_chars = options.get("empty_section_min_text_chars", defaults.empty_section_min_text_chars)
    if not isinstance(min_text_chars, int) or isinstance(min_text_chars, bool) or min_text_chars < 0:
        raise ConfigError("empty_section_min_text_chars must be a non-negative integer")
    extra["empty_section_min_text_chars"] = min_text_chars

    for name, minimum in (("min_document_words", 1), ("min_paragraph_words", 1), ("min_paragraph_chars", 0)):
        extra[name] = _require_bounded_int(name, options.get(name, getattr(defaults, name)), minimum)

    for name in (*_FACT_CHECK_INT_BOUNDS, *_FACT_CHECK_UNIT_OPTIONS):
        extra[name] = validate_fact_check_option(name, options.get(name, getattr(defaults, name)))
    combination = options.get("fact_check_combination", defaults.fact_check_combination)
    parse_fact_combination(combination)
    extra["fact_check_combination"] = combination

    document_id_field = options.get("document_id_field", defaults.document_id_field)
    if not isinstance(document_id_field, str) or not document_id_field:
        raise ConfigError("document_id_field must be a nonempty string")
    if not _DOCUMENT_ID_FIELD_PATTERN.fullmatch(document_id_field):
        raise ConfigError(
            "document_id_field must be a simple key name: a letter or underscore "
            "followed by letters, digits, underscores or hyphens, at most 128 characters"
        )
    extra["document_id_field"] = document_id_field

    deprecated_file = options.get("deprecated_references_file", defaults.deprecated_references_file)
    if not isinstance(deprecated_file, str):
        raise ConfigError("deprecated_references_file must be a path string under the scan root")
    if deprecated_file and not _is_within_root(deprecated_file):
        raise ConfigError("deprecated_references_file must stay within the scan root")
    extra["deprecated_references_file"] = deprecated_file

    templates_dir = options.get("report_templates_dir", defaults.report_templates_dir)
    if templates_dir is not None:
        if not isinstance(templates_dir, str) or not templates_dir:
            raise ConfigError("report_templates_dir must be a nonempty directory path under the scan root")
        if not _is_within_root(templates_dir):
            raise ConfigError("report_templates_dir must stay within the scan root")
    extra["report_templates_dir"] = templates_dir

    extra["telemetry_extensions"] = validate_telemetry_extensions(
        options.get("telemetry_extensions", list(defaults.telemetry_extensions))
    )
    extra["telemetry_domains"] = validate_telemetry_domains(
        options.get("telemetry_domains", list(defaults.telemetry_domains))
    )
    extra["link_root"] = validate_link_root(options.get("link_root", defaults.link_root))
    extra["at_reference_extensions"] = validate_at_reference_extensions(
        options.get("at_reference_extensions", list(defaults.at_reference_extensions))
    )

    return extra
