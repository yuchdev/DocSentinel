"""Single entry point for all scan consumers."""

import codecs
import inspect
import logging
import os
import stat
import time
from collections.abc import Sequence
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Callable, Final, Optional, Union

from docsentinel.baseline import filter_baselined, load_baseline
from docsentinel.config import Config, ConfigError, load_config
from docsentinel.deep_support import DEEP_EXTRA_HINT, deep_ready
from docsentinel.detectors.loader import clear_standard_caches, ensure_standard_loaded
from docsentinel.detectors.unreadable import DS100, NOT_REGULAR, NOT_UTF8, cannot_read, unreadable_finding
from docsentinel.discovery import (
    check_invoker_selector_shape,
    discover_with_stats,
    normalize_invoker_selectors,
    selector_root_spellings,
)
from docsentinel.link_root import LINK_ROOT_RULES, resolve_invoker_link_root, resolve_link_root
from docsentinel.log import FILE_ONLY, safe
from docsentinel.models import Document, Finding, ScanResult
from docsentinel.rules import ANALYZERS, ENGINE_RULES, RULES, effective_rules, opt_in_hint, opt_in_satisfied

Analyzer = Callable[..., tuple[Finding, ...]]

logger = logging.getLogger(__name__)


#: Dispatch mode for an analyzer: it takes no config (legacy two-argument form),
#: config as a keyword (``config=settings``), or config as a third positional
#: argument (``settings`` after ``root`` and ``documents``).
_CONFIG_NONE = "none"
_CONFIG_KEYWORD = "keyword"
_CONFIG_POSITIONAL = "positional"


@lru_cache(maxsize=256)
def _analyzer_config_mode(analyzer: Analyzer) -> str:
    """Return how the engine must forward effective config to an analyzer.

    The preferred analyzer contract is ``detect(root, documents, config=None)``,
    while the legacy ``detect(root, documents)`` two-argument form stays
    supported. Inspecting the signature lets the engine always forward effective
    config to analyzers that accept it without breaking two-argument detectors,
    and -- critically -- choose *how* to pass it so the call never raises
    ``TypeError`` from a missing positional slot:

    * A parameter literally named ``config`` that is keyword-acceptable
      (positional-or-keyword or keyword-only) is filled as ``config=settings``,
      which works for both ``detect(..., config=None)`` and a keyword-only
      ``detect(..., *, config=None)``.
    * A ``*args`` (``VAR_POSITIONAL``) analyzer, or one declaring three or more
      ordinary positional parameters with no ``config`` name, receives config as
      a third positional argument.
    * Everything else -- including a ``**kwargs``-only callable, which has **no**
      third positional slot and so would raise if called positionally -- is the
      legacy two-argument form. ``VAR_KEYWORD`` alone therefore does *not* mark
      an analyzer as config-aware.

    Registered analyzers are ordinarily module-level functions whose signatures
    introspect cleanly, but some callables (for example C builtins or objects
    whose ``__signature__`` raises) cannot be inspected; those raise
    ``ValueError`` or ``TypeError`` from :func:`inspect.signature` and are
    treated as the legacy two-argument form rather than crashing the scan. The
    cache has a fixed ``maxsize``; once it is full the least-recently-used entry
    is evicted, so an evicted analyzer is simply re-introspected on its next use
    (a bounded, repeatable cost) rather than the cache growing without bound.

    :param analyzer: A registered analyzer callable.
    :returns: One of :data:`_CONFIG_NONE`, :data:`_CONFIG_KEYWORD`, or
        :data:`_CONFIG_POSITIONAL`.
    """
    try:
        signature = inspect.signature(analyzer)
    except (ValueError, TypeError):
        # A callable whose signature cannot be introspected (for example a C
        # builtin, or an object whose __signature__ raises) cannot declare a
        # config parameter; record that absence and dispatch it below via the
        # legacy two-argument form rather than swallowing the condition here.
        signature = None
    if signature is None:
        logger.debug("analyzer %s has no introspectable signature; called without config", safe(analyzer))
        return _CONFIG_NONE
    parameters = list(signature.parameters.values())
    config_param = signature.parameters.get("config")
    if config_param is not None and config_param.kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        return _CONFIG_KEYWORD
    if any(parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters):
        return _CONFIG_POSITIONAL
    positional = [
        parameter
        for parameter in parameters
        if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= 3:
        return _CONFIG_POSITIONAL
    return _CONFIG_NONE


@lru_cache(maxsize=256)
def _analyzer_accepts_link_root(analyzer: Analyzer) -> bool:
    """Return True when an analyzer declares a keyword-acceptable ``link_root`` parameter.

    Analyzers that resolve site-root-absolute (``/``) targets accept the engine's
    validated link root as ``link_root=``; every other analyzer is called exactly as
    before. Signatures that cannot be introspected are treated as not accepting it.

    :param analyzer: A registered analyzer callable.
    :returns: True when ``link_root`` is forwarded by keyword.
    """
    try:
        parameter = inspect.signature(analyzer).parameters.get("link_root")
    except (ValueError, TypeError):
        # Not introspectable: it cannot declare link_root; call it the legacy way.
        parameter = None
    return parameter is not None and parameter.kind in (
        inspect.Parameter.KEYWORD_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def _analyzer_accepts_config(analyzer: Analyzer) -> bool:
    """Return True when the engine forwards effective config to an analyzer.

    This is a thin predicate over :func:`_analyzer_config_mode`; the mode also
    records *how* config is forwarded so the call cannot raise ``TypeError``.

    :param analyzer: A registered analyzer callable.
    :returns: True when config is forwarded (by keyword or position), else False.
    """
    return _analyzer_config_mode(analyzer) != _CONFIG_NONE


def _run_analyzer(
    analyzer: Analyzer,
    directory: Path,
    documents: tuple[Document, ...],
    settings: Config,
    link_root: Optional[Path] = None,
) -> tuple[Finding, ...]:
    """Invoke an analyzer, forwarding effective config when its signature accepts it.

    :param analyzer: The analyzer callable to run.
    :param directory: The resolved scan root directory.
    :param documents: Discovered documents to inspect, in scan order.
    :param settings: Effective settings for this scan.
    :param link_root: The engine-validated link root, forwarded as ``link_root=``
        to analyzers that declare it; ``None`` forwards nothing.
    :returns: The analyzer's findings.
    """
    extra: dict[str, Path] = {}
    if link_root is not None and _analyzer_accepts_link_root(analyzer):
        extra["link_root"] = link_root
    mode = _analyzer_config_mode(analyzer)
    if mode == _CONFIG_KEYWORD:
        return analyzer(directory, documents, config=settings, **extra)
    if mode == _CONFIG_POSITIONAL:
        return analyzer(directory, documents, settings, **extra)
    return analyzer(directory, documents, **extra)


def _env_confirms() -> bool:
    """Return True if DOCSENTINEL_DEEP_CONFIRM is set to a truthy value."""
    return os.environ.get("DOCSENTINEL_DEEP_CONFIRM", "").lower() in {"1", "true", "yes"}


def _resolve_deep_confirm(settings: Config) -> bool:
    """Return True if deep profile execution is confirmed via settings or env."""
    return settings.deep_confirm or _env_confirms()


def _hint_for(code: str, option: str) -> str:
    """Return the opt-in hint of ``code``, or ``option`` verbatim for an unregistered code.

    :param code: A rule code from an ``opt_in_off`` pair.
    :param option: The option name from the same pair.
    :returns: :func:`~docsentinel.rules.opt_in_hint` of the registered rule, else ``option``.
    """
    rule = RULES.get(code)
    return opt_in_hint(rule) if rule is not None else option


def evaluated_notice(profile: str, rules_evaluated: int, opt_in_off: tuple[tuple[str, str], ...]) -> str:
    """Build the legacy ``ScanResult.notice`` for a scan that ran at least one active rule.

    This is the single source of the notice text: :func:`scan` stores
    ``rules_evaluated`` and ``opt_in_off`` on the result and derives the notice from
    them here, so the structured fields and the string can never disagree.

    :param profile: The scan profile (``fast``/``standard``/``deep``).
    :param rules_evaluated: Active rules that genuinely evaluated.
    :param opt_in_off: ``(code, option)`` pairs for active opt-in rules whose policy is off.
    :returns: The byte-identical legacy notice string.
    """
    if profile == "deep":
        # The deep notice has always counted every active rule.
        return f"{rules_evaluated + len(opt_in_off)} deep rule(s) evaluated (heuristic, advisory-only)."
    notice = f"{rules_evaluated} {profile} rule(s) evaluated"
    if opt_in_off:
        disabled = ", ".join(f"{code} (set {_hint_for(code, option)})" for code, option in opt_in_off)
        return f"{notice}; opt-in rule(s) not enabled: {disabled}."
    return f"{notice}."


#: ``os.open`` flags for the per-document readability check: read-only, binary on
#: Windows, never following a final-component symlink (discovery already skips
#: symlinked files; this keeps a file swapped for a symlink afterwards unread), and
#: non-blocking so a path swapped for a FIFO cannot hang the scan on ``open``.
_READ_FLAGS: Final[int] = (
    os.O_RDONLY
    | getattr(os, "O_BINARY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
#: Bytes read per chunk while validating UTF-8; the text is never held whole.
_READ_CHUNK: Final[int] = 1 << 20
#: Unreadable documents named individually on stderr; the rest go to the log file only.
MAX_STDERR_SKIP_WARNINGS: Final[int] = 20


class _NotRegularFileError(OSError):
    """The discovered path is no longer a regular file when the engine opens it."""


def _validate_document(path: Path):
    """Check that one discovered document is a readable regular file of valid UTF-8.

    The file is opened with ``O_NOFOLLOW|O_NONBLOCK``, must be a regular file by
    ``fstat``, and is decoded with a strict incremental UTF-8 decoder in
    :data:`_READ_CHUNK` pieces, so neither the bytes nor the text are kept.

    :param path: Absolute path of the document.
    :raises _NotRegularFileError: When the opened file is not a regular file.
    :raises UnicodeDecodeError: When the content is not valid UTF-8.
    :raises OSError: When the file cannot be opened or read.
    """
    descriptor = os.open(path, _READ_FLAGS)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise _NotRegularFileError(NOT_REGULAR)
        decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
        while chunk := os.read(descriptor, _READ_CHUNK):
            decoder.decode(chunk)
        decoder.decode(b"", final=True)
    finally:
        os.close(descriptor)


def _unreadable_reason(path: Path) -> Optional[str]:
    """Return why a document cannot be scanned, or ``None`` when it can.

    :param path: Absolute path of the document.
    :returns: A DS100 reason (``not valid UTF-8``, ``not a regular file`` or
        ``cannot read it (<OS error>)``), or ``None`` for a readable document.
    """
    reason: Optional[str] = None
    try:
        _validate_document(path)
    except UnicodeDecodeError:
        reason = NOT_UTF8
    except _NotRegularFileError:
        reason = NOT_REGULAR
    except OSError as exc:
        reason = cannot_read(exc.strerror or type(exc).__name__)
    return reason


def _partition_readable(
    directory: Path, documents: tuple[Document, ...]
) -> tuple[tuple[Document, ...], tuple[tuple[Document, str], ...]]:
    """Split the inventory into documents the analyzers can read and those they cannot.

    Each document is checked once by :func:`_unreadable_reason`, with the strict
    UTF-8 decoding every detector uses, so analyzers never see a file that would
    make them raise. The unreadable ones stay in the inventory and become DS100
    findings. Each is logged at ``WARNING`` (path through :func:`safe`, never
    content); after :data:`MAX_STDERR_SKIP_WARNINGS` of them the rest go to the log
    file only and one summary ``WARNING`` counts them, so a flood of bad files
    cannot flood a CI log.

    :param directory: The scan root the document paths are relative to.
    :param documents: The discovered inventory.
    :returns: The readable documents in their original order, and
        ``(document, reason)`` for each unreadable one in the same order.
    """
    readable: list[Document] = []
    unreadable: list[tuple[Document, str]] = []
    for document in documents:
        reason = _unreadable_reason(directory / document.path)
        if reason is None:
            readable.append(document)
            continue
        unreadable.append((document, reason))
        extra = FILE_ONLY if len(unreadable) > MAX_STDERR_SKIP_WARNINGS else None
        logger.warning("skipped %s: %s", safe(document.path), safe(reason), extra=extra)
    hidden = len(unreadable) - MAX_STDERR_SKIP_WARNINGS
    if hidden > 0:
        logger.warning("skipped %d more unreadable documents (see log file)", hidden)
    return tuple(readable), tuple(unreadable)


def _log_rule_plan(settings: Config, active_codes: tuple[str, ...], opt_in_off: tuple[tuple[str, str], ...]):
    """Log the rule plan of a scan at ``INFO`` and warn for an explicitly selected, inert opt-in rule.

    An opt-in policy rule whose option is unset evaluates nothing. When the user
    named that rule by its exact code in ``select``, they asked for it, so the scan
    coping by evaluating nothing earns a ``WARNING``; a prefix selection or the
    default selection keeps it at the plan line only.

    :param settings: Effective settings for this scan.
    :param active_codes: Selected rule codes for the profile, in rule-code order.
    :param opt_in_off: ``(code, option)`` pairs of active opt-in rules whose policy is off.
    """
    disabled = ", ".join(f"{code} ({_hint_for(code, option)})" for code, option in opt_in_off) or "none"
    logger.info(
        "profile=%s: %d rules selected, %d evaluated; opt-in off: %s",
        settings.profile,
        len(active_codes),
        len(active_codes) - len(opt_in_off),
        disabled,
    )
    for code, option in opt_in_off:
        if code in settings.select:
            logger.warning("%s is selected but evaluates nothing until %s is set", code, _hint_for(code, option))


#: Characters of one selector pattern echoed in a log record (threat model M22).
_PATTERN_ECHO_LIMIT: Final[int] = 200

#: ``ConfigError`` text for an empty inventory under invoker selection (owner ruling R1).
EMPTY_SELECTION_MESSAGE: Final[str] = "the selection admitted no document; values are relative to the scan root"


def _apply_invoker_selection(
    directory: Path,
    root: Union[Path, str],
    settings: Config,
    include: Optional[Sequence[str]],
    exclude: Optional[Sequence[str]],
) -> tuple[Config, bool]:
    """Normalise the invoker selectors and merge them into the settings (ADR 0006 Contracts 3 and 4).

    The include replaces the effective include; the exclude is appended to the
    effective exclude, duplicates removed in first-occurrence order (configured
    entries first). The settings object is never mutated. Each unmatched literal
    exclude is logged once at ``WARNING``, echoed through :func:`safe`.

    :param directory: The canonical (resolved) scan root.
    :param root: The scan root as the caller spelled it, for the root spellings (A4).
    :param settings: The effective settings (loaded or injected).
    :param include: The invoker include values, or ``None`` when not given.
    :param exclude: The invoker exclude values, or ``None`` when not given.
    :returns: The merged settings and whether the include came from the invoker.
    :raises ConfigError: For a refused selector value.
    """
    if include is None and exclude is None:
        return settings, False
    selection = normalize_invoker_selectors(
        directory, include, exclude, root_spellings=selector_root_spellings(directory, root)
    )
    changes: dict[str, tuple[str, ...]] = {}
    if selection.include is not None:
        changes["include"] = selection.include
    if selection.exclude:
        changes["exclude"] = tuple(dict.fromkeys((*settings.exclude, *selection.exclude)))
    for pattern in selection.unmatched_exclude:
        logger.warning("exclude pattern %s names nothing under the scan root", safe(pattern, _PATTERN_ECHO_LIMIT))
    merged = replace(settings, **changes) if changes else settings
    return merged, selection.include is not None


def _log_selection(settings: Config, configured_exclude: tuple[str, ...], invoker_include: bool):
    """Log the effective selection: one ``INFO`` line of counts, one ``DEBUG`` line per pattern.

    The ``INFO`` line carries counts only (threat model M22); a pattern appears
    only in a ``DEBUG`` record, through ``safe(pattern, 200)``.

    :param settings: The merged settings.
    :param configured_exclude: The exclude list before the invoker additions.
    :param invoker_include: Whether the include came from the invoker.
    """
    configured = frozenset(configured_exclude)
    effective = tuple(dict.fromkeys(settings.exclude))
    added = sum(1 for pattern in effective if pattern not in configured)
    include_source = "invoker" if invoker_include else "configured"
    logger.info(
        "selection: include %d pattern(s) (%s), exclude %d pattern(s) (%d configured, %d invoker)",
        len(settings.include),
        include_source,
        len(effective),
        len(effective) - added,
        added,
    )
    for pattern in settings.include:
        logger.debug("selection: include %s (%s)", safe(pattern, _PATTERN_ECHO_LIMIT), include_source)
    for pattern in effective:
        source = "configured" if pattern in configured else "invoker"
        logger.debug("selection: exclude %s (%s)", safe(pattern, _PATTERN_ECHO_LIMIT), source)


def scan(
    root: Union[Path, str] = ".",
    *,
    config: Optional[Config] = None,
    link_root: Optional[Union[Path, str]] = None,
    include: Optional[Sequence[str]] = None,
    exclude: Optional[Sequence[str]] = None,
) -> ScanResult:
    """Inventory documents and run registered analyzers, without implicit deep checks.

    A discovered document that cannot be read, is not a regular file or is not
    valid UTF-8 stays in the inventory but is withheld from every analyzer; unless
    ``select``/``ignore`` drop ``DS100``, it gets one ``DS100`` error finding, in
    every profile (an unconfirmed or dependency-less deep scan runs no rule and
    reports none).

    :param root: The directory or single file to scan.
    :param config: Settings to use verbatim, or ``None`` to load them from ``root``.
    :param link_root: Trusted invoker override for the base of site-root-absolute
        (``/``) targets (``scan --link-root``): an absolute path or one relative to the
        current directory that must resolve to an existing scan root or ancestor (not
        the filesystem root). It wins over ``config.link_root``; ``None`` uses the
        configured, bounded value.
    :param include: Invoker include patterns (``scan --include``), relative to the
        scan root in the configuration grammar; they **replace** the effective
        ``include`` (also of an injected ``config``, which is never mutated).
        ``None`` (the default) means not given. A bare ``str``, an empty sequence,
        more than 256 values or a value over 1,024 characters is a ``ConfigError``,
        for every target; a single-file target then ignores the selectors with one
        ``WARNING``.
    :param exclude: Invoker exclude patterns (``scan --exclude``), same grammar and
        bounds; they are **appended** to the effective ``exclude`` (duplicates
        removed, configured entries first). Exclude wins over include.
    :returns: The scan result.
    :raises ConfigError: When the configured or invoker link root is invalid, when an
        invoker selector is refused, or when ``include`` or ``exclude`` was given and
        the selection admitted no document (a config-only empty inventory is not an
        error).
    """
    target = Path(root).resolve()
    selected_file = target.is_file()
    directory = target.parent if selected_file else target
    logger.debug(
        "scan: root=%s, config=%s, link_root override=%s",
        safe(target),
        "injected" if config is not None else "discovered",
        "none" if link_root is None else safe(link_root),
    )
    settings = config if config is not None else load_config(directory)
    invoker_selection = include is not None or exclude is not None
    # Shape checks run for every target, so a caller bug never passes silently
    # because the target happened to be a file (ADR 0006 Contract 5 step 2).
    check_invoker_selector_shape(include, exclude)
    if selected_file:
        # An explicitly selected file bypasses include/exclude patterns.
        if invoker_selection:
            logger.warning("--include/--exclude ignored for a single-file scan target")
        if Path(root).is_symlink():
            raise ValueError(f"Symlinked files are not inventoried: {root}")
        documents = (Document(target.name, target.stat().st_size),)
        skipped = 0
    else:
        configured_exclude = settings.exclude
        settings, invoker_include = _apply_invoker_selection(directory, root, settings, include, exclude)
        _log_selection(settings, configured_exclude, invoker_include)
        found = discover_with_stats(directory, settings)
        if invoker_include:
            for pattern, hits in zip(settings.include, found.include_hits, strict=True):
                if hits == 0:
                    logger.warning("include pattern %s matched no document", safe(pattern, _PATTERN_ECHO_LIMIT))
        if invoker_selection and not found.documents:
            raise ConfigError(EMPTY_SELECTION_MESSAGE)
        documents, skipped = found.documents, found.skipped
    readable, unreadable = _partition_readable(directory, documents)
    logger.info(
        "discovered %d documents under %s (%d skipped: symlinks/excluded, %d unreadable)",
        len(documents),
        safe(directory),
        skipped,
        len(unreadable),
    )

    if settings.profile == "deep":
        if not _resolve_deep_confirm(settings):
            logger.warning(
                "deep profile skipped: not confirmed (set deep_confirm = true, pass "
                "--i-understand-deep-is-heuristic, or set DOCSENTINEL_DEEP_CONFIRM=1)"
            )
            pending = (
                "deep profile requires explicit opt-in: set deep_confirm = true, "
                "pass --i-understand-deep-is-heuristic, or set DOCSENTINEL_DEEP_CONFIRM=1 "
                "(deep checks are heuristic and may report false positives)",
            )
            return ScanResult(
                profile=settings.profile,
                documents=documents,
                findings=(),
                enabled_rules=(),
                pending=pending,
                notice="Deep profile detection skipped until explicit opt-in is provided.",
            )
        if not deep_ready():
            logger.warning("deep profile skipped: dependencies unavailable - %s", DEEP_EXTRA_HINT)
            pending = (f"deep profile confirmed, but its dependencies are unavailable - {DEEP_EXTRA_HINT}",)
            return ScanResult(
                profile=settings.profile,
                documents=documents,
                findings=(),
                enabled_rules=(),
                pending=pending,
                notice="Deep profile detection skipped because dependencies are unavailable.",
            )

    if settings.profile == "standard":
        ensure_standard_loaded()
        clear_standard_caches()

    # Engine rules (DS100) are not part of any profile's analyzer plan; the engine
    # emits them itself below, in every profile, when select/ignore keep them.
    profile_codes = tuple(
        code for code, rule in RULES.items() if rule.profile == settings.profile and code not in ENGINE_RULES
    )
    active_codes = effective_rules(profile_codes, settings.select, settings.ignore)
    # Opt-in policy rules that are active but whose policy is off evaluate
    # nothing, so the notice must not count them among the evaluated rules;
    # it names them instead so a disabled policy never masquerades as audited.
    opt_in_off: tuple[tuple[str, str], ...] = tuple(
        (code, RULES[code].opt_in_option) for code in active_codes if not opt_in_satisfied(RULES[code], settings)
    )
    _log_rule_plan(settings, active_codes, opt_in_off)
    # Resolve ``link_root`` once per scan (the ``.git`` walk runs a single time, and
    # only when a rule that resolves ``/`` targets is active) and hand the validated
    # directory to the analyzers that declare ``link_root``; an invalid or unbounded
    # value fails closed with ConfigError before any analyzer runs.
    # An invoker override is validated unconditionally (trusted input, fail closed).
    if link_root is not None:
        resolved_link_root: Optional[Path] = resolve_invoker_link_root(directory, link_root)
    elif LINK_ROOT_RULES.intersection(active_codes):
        resolved_link_root = resolve_link_root(directory, settings)
    else:
        resolved_link_root = None
    collected: list[Finding] = []
    unreadable_reported = bool(unreadable) and bool(effective_rules((DS100.code,), settings.select, settings.ignore))
    if unreadable_reported:
        collected.extend(unreadable_finding(document.path, reason) for document, reason in unreadable)
        logger.debug("%s: %d findings", DS100.code, len(unreadable))
    for code in active_codes:
        if code not in ANALYZERS:
            continue
        started = time.perf_counter()
        produced = tuple(_run_analyzer(ANALYZERS[code], directory, readable, settings, resolved_link_root))
        logger.debug("%s: %d findings in %.2fs", code, len(produced), time.perf_counter() - started)
        collected.extend(produced)
    findings = tuple(collected)
    if settings.baseline is not None:
        baseline_path = (
            Path(settings.baseline)
            if Path(settings.baseline).is_absolute()
            else (directory / settings.baseline).resolve()
        )
        known = load_baseline(baseline_path)
        unfiltered = len(findings)
        findings = filter_baselined(findings, known)
        logger.info(
            "baseline %s: %d fingerprints, %d findings suppressed",
            safe(baseline_path),
            len(known),
            unfiltered - len(findings),
        )
    rules_evaluated = 0
    if active_codes:
        pending = ()
        rules_evaluated = len(active_codes) - len(opt_in_off)
        notice = evaluated_notice(settings.profile, rules_evaluated, opt_in_off)
    elif not profile_codes:
        if settings.profile == "deep":
            pending = ("deep profile confirmed, but no deep rules are registered",)
        else:
            pending = ("standard detectors are not implemented in M0",) if settings.profile == "standard" else ()
        notice = "Detection rules are not implemented in M0; this is an inventory only."
    else:
        pending = (f"all {settings.profile} rules were excluded by select/ignore",)
        notice = f"All {settings.profile} rules were excluded by select/ignore."
    return ScanResult(
        profile=settings.profile,
        documents=documents,
        findings=findings,
        # DS100 is listed only when it reported a document, so a clean scan's
        # enabled_rules (and every report pinned to it) stays unchanged.
        enabled_rules=((DS100.code,) if unreadable_reported else ()) + active_codes,
        pending=pending,
        notice=notice,
        rules_evaluated=rules_evaluated,
        opt_in_off=opt_in_off,
    )
