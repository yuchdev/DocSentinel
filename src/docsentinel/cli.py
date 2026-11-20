"""Command-line access to the shared scan engine."""

import argparse
import errno
import logging
import os
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Optional

from docsentinel import deep_support
from docsentinel.baseline import save_baseline
from docsentinel.config import (
    USER_SETTINGS_ENV,
    USER_SETTINGS_OFF,
    Config,
    ConfigError,
    ConfigSources,
    _check_user_settings_directories,
    _tilde_path,
    load_config_with_sources,
    user_settings_path,
)
from docsentinel.detectors.loader import ensure_standard_loaded
from docsentinel.discovery import check_invoker_selector_shape, normalize_invoker_selectors, selector_root_spellings
from docsentinel.engine import scan
from docsentinel.errors import ExtraNotInstalledError
from docsentinel.log import FILE_ONLY, configure_cli_logging, safe, shutdown_cli_logging
from docsentinel.models import ScanResult
from docsentinel.reporting import neutralize_text, render
from docsentinel.rules import RULES, Rule, opt_in_hint, opt_in_satisfied, rules_for_profile
from docsentinel.telemetry.extensions import ExtensionError, LoadedExtensions, check_template, resolve_extensions
from docsentinel.telemetry.filters import TemplateError
from docsentinel.telemetry.loader import (
    DEFAULT_TEMPLATE,
    Template,
    available_templates,
    load_named_template,
    load_template,
    packaged_template_names,
)

# Named explicitly: under "python -m docsentinel.cli" __name__ is "__main__", which is
# outside the "docsentinel" logger hierarchy the CLI handlers are attached to.
logger = logging.getLogger("docsentinel.cli")

TEMPLATE = (
    'profile = "fast"\n'
    'include = ["*.md", "**/*.md"]\n'
    'exclude = [".git", ".venv", "node_modules"]\n'
    "select = []\n"
    "ignore = []\n"
    "\n"
    '# Standard profile thresholds (profile = "standard"); defaults shown.\n'
    "# max_grade_level = 14.0          # DS201: flag prose above this readability grade\n"
    "# duplicate_similarity = 0.85     # DS202: flag paragraph pairs at/above this cosine similarity\n"
    "# min_information_score = 0.15    # DS203: flag paragraphs scoring below this information score\n"
    '# docsig_paths = ["src"]          # DS204: Python source roots checked against docstrings\n'
    "#\n"
    "# Statistical size limits (standard profile); defaults shown.\n"
    "# min_document_words = 50         # DS201: skip documents with fewer prose words\n"
    "# min_paragraph_words = 5         # DS202/DS203: skip paragraphs with fewer words\n"
    "# min_paragraph_chars = 30        # DS202/DS203: skip paragraphs shorter than this\n"
    "\n"
    '# Base for site-root-absolute links (/docs/x.md): "auto" = nearest .git ancestor, "." = scan root.\n'
    '# link_root = "auto"\n'
    "\n"
    '# Reference scope: "links" checks links and @-mentions; "strict" also checks path-like\n'
    "# inline code spans (DS103). --reference-scope overrides it for one run.\n"
    '# reference_scope = "links"\n'
    "# File extensions an @-mention must end in to be checked (DS124); defaults shown.\n"
    '# at_reference_extensions = ["md", "markdown", "mdx", "txt", "rst", "toml", "json", "yaml", "yml", "py"]\n'
)

#: The starter object ``init --user`` writes (story 03.0 decision S10).
USER_SETTINGS_TEMPLATE = '{\n  "profile": "fast",\n  "reference_scope": "links"\n}\n'

#: The default user settings location as shown in help texts (tilde form, never a real home).
USER_SETTINGS_HELP_PATH = "~/.local/share/docsentinel/settings.json"

#: At most this many user-layer option names are listed in the INFO ``config:`` line
#: (threat model 0009-user-settings A10, U16).
MAX_LOGGED_OPTION_NAMES = 20

#: The ``--no-user-settings`` help text shared by ``scan``, ``baseline`` and ``doctor``.
NO_USER_SETTINGS_HELP = (
    f"Ignore the user settings file ({USER_SETTINGS_HELP_PATH}, under $XDG_DATA_HOME when set, or the "
    f"absolute path in {USER_SETTINGS_ENV}) for this run; {USER_SETTINGS_ENV}={USER_SETTINGS_OFF} "
    "disables it for every run"
)


def _opt_in_suffix(rule: Rule) -> str:
    """Return the ``rules`` listing suffix marking an opt-in policy rule, else empty.

    :param rule: A registered rule.
    :returns: ``" [opt-in: set <hint>]"`` for an opt-in policy rule, with the hint
        from :func:`~docsentinel.rules.opt_in_hint` (for example
        ``reference_scope = "strict"``), or ``""`` for an ordinary always-active rule.
    """
    return f" [opt-in: set {opt_in_hint(rule)}]" if rule.opt_in_option else ""


def _standard_rule_lines() -> list[str]:
    """Return formatted rule lines for the standard profile, or install guidance if missing."""
    try:
        ensure_standard_loaded()
    except ExtraNotInstalledError:
        missing_msg = ["standard profile: install docsentinel[standard] to enable (DS2xx)"]
        return missing_msg
    registered = rules_for_profile("standard")
    if registered:
        return [f"  {rule.code}: {rule.title}{_opt_in_suffix(rule)}" for rule in registered]
    return ["  (none registered)"]


def _deep_doctor_lines() -> list[str]:
    """Return formatted lines for doctor describing deep profile readiness."""
    libs = deep_support.libraries_available()
    model = deep_support.model_available()
    ready = deep_support.deep_ready()

    lines = []
    if ready:
        lines.append("deep profile: ready")
        lines.append("  ✓ deep libraries installed (spacy, textacy)")
        lines.append(f"  ✓ deep model installed ({deep_support.MODEL_NAME})")
    else:
        lines.append("deep profile: not ready")
        if libs:
            lines.append("  ✓ deep libraries installed (spacy, textacy)")
        else:
            lines.append(f"  ✗ deep libraries missing: {deep_support.DEEP_EXTRA_HINT}")
        if model:
            lines.append(f"  ✓ deep model installed ({deep_support.MODEL_NAME})")
        else:
            lines.append(
                f"  ✗ deep model missing ({deep_support.MODEL_NAME}): python -m spacy download {deep_support.MODEL_NAME}"
            )
    return lines


def _exit_code(result: ScanResult, *, strict: bool = False) -> int:
    """Return the exit code for a scan result.

    Deep profile findings are heuristic candidates and advisory-only: they never fail
    the exit code (returning 0), even when strict is True. This profile-keyed exemption
    ensures candidate contradictions inform review without breaking builds.
    A future --fail-on-deep flag / deep_fail setting is deferred.

    For fast and standard profiles, returns 1 if strict mode is enabled and there are any
    findings, or if any finding has severity == "error". Otherwise, returns 0.
    """
    if result.profile == "deep":
        return 0
    if strict:
        return 1 if result.findings else 0
    return 1 if any(finding.severity == "error" for finding in result.findings) else 0


def _report_template(format_name: str, template_path: Optional[Path], settings: Config, root: Path) -> Template:
    """Resolve the report template for ``scan`` before the scan runs.

    ``--template PATH`` wins and is trusted invoker input, read through the loader's
    regular-file/size/encoding gate. Otherwise ``--format`` must name one of the
    discovered templates (packaged, then ``report_templates_dir``).

    :param format_name: The ``--format`` value.
    :param template_path: The ``--template`` value, or ``None``.
    :param settings: The effective configuration.
    :param root: The scan root directory ``report_templates_dir`` is relative to.
    :returns: The validated template.
    :raises TemplateError: When the template is unknown, unreadable or invalid.
    """
    if template_path is not None:
        return load_template(template_path)
    names = available_templates(root, settings.report_templates_dir)
    if format_name not in names:
        raise TemplateError(f"unknown --format {format_name[:80]!r}; choose from: {', '.join(names)}")
    return load_named_template(format_name, root=root, templates_dir=settings.report_templates_dir)


def _doctor_template_lines(settings: Optional[Config], error: Optional[Exception]) -> list[str]:
    """Return the ``doctor`` lines listing the selectable report templates.

    The packaged templates are always listed. When the configuration discovered in
    the current directory sets ``report_templates_dir``, its templates are listed
    too; a configuration or directory problem is reported on one neutralized line
    instead of failing ``doctor``.

    :param settings: The configuration of the current directory, or ``None`` when
        loading it failed.
    :param error: The configuration error, or ``None``.
    :returns: The formatted lines.
    """
    lines = [f"report templates (packaged): {', '.join(packaged_template_names())}"]
    if settings is None:
        lines.append(f"report templates (report_templates_dir): unavailable: {neutralize_text(str(error))}")
        return lines
    try:
        if settings.report_templates_dir:
            packaged = set(packaged_template_names())
            extra = [
                name for name in available_templates(Path.cwd(), settings.report_templates_dir) if name not in packaged
            ]
            lines.append(f"report templates (report_templates_dir): {', '.join(extra) or '(none)'}")
    except (ConfigError, TemplateError, OSError) as exc:
        lines.append(f"report templates (report_templates_dir): unavailable: {neutralize_text(str(exc))}")
    return lines


#: The environment form of ``--allow-python-extensions``; only the exact value ``"1"``
#: opens the gate (threat model 0007-extensions M2). Only this module reads it.
ALLOW_PYTHON_EXTENSIONS_ENV = "DOCSENTINEL_ALLOW_PYTHON_EXTENSIONS"


def _python_extensions_allowed(flag: bool) -> bool:
    """Return the ``python:`` extension gate decision (M2).

    :param flag: Whether ``--allow-python-extensions`` was given.
    :returns: ``True`` for the flag, or the environment variable set to exactly ``"1"``
        (``true``, ``yes``, ``" 1"``, ``"1 "`` and an empty value are refused).
    """
    return flag is True or os.environ.get(ALLOW_PYTHON_EXTENSIONS_ENV) == "1"


def _report_extensions(
    specs: list[str], settings: Config, root: Path, *, allow_python: bool, origin_roots: tuple[Path, ...]
) -> LoadedExtensions:
    """Resolve the report extensions before the template and the scan (M30).

    Config entries come first (builtin only), then the ``--extension`` specs in
    order. Nothing is imported for a ``builtin:`` spec; a ``python:`` spec passes the
    gate and the origin check of the shared importlib helper.

    :param specs: The ``--extension`` values.
    :param settings: The effective configuration.
    :param root: The resolved scan root directory (refused as a module origin, M6).
    :param allow_python: The gate decision.
    :param origin_roots: The scan root as given on the command line, absolute but
        unresolved, plus its logical spellings (see :func:`_origin_spellings`);
        anchored too, so a root that is a symlink out of the checkout cannot drop
        the checkout from the M6 boundary (amended 2026-11-03, F1, N5).
    :returns: The validated registry.
    :raises ConfigError: For a non-builtin ``telemetry_extensions`` entry.
    :raises ExtensionError: For a refused, unknown, duplicate or failing extension.
    """
    return resolve_extensions(
        tuple(specs),
        config=settings,
        allow_python=allow_python,
        root=root,
        cwd=Path.cwd(),
        origin_roots=origin_roots,
    )


#: Characters of the root argument echoed in a resolution error.
_MAX_ROOT_ECHO = 200


def _resolve_root(spelled: str) -> Path:
    """Return the canonical scan root, turning a symlink loop into a ``ConfigError``.

    Strict resolution detects loops on both Python 3.12 and 3.13. Missing or
    non-directory components retain non-strict resolution so root validation stays
    with the scan engine. The root argument is invoker input; it is bounded here
    and neutralized when the error is printed.

    :param spelled: The root argument as the invoker typed it.
    :returns: The resolved path.
    :raises ConfigError: When the path cannot be resolved (a symlink loop, or an
        ``OSError`` while resolving).
    """
    try:
        path = Path(spelled)
        try:
            resolved = path.resolve(strict=True)
        except (FileNotFoundError, NotADirectoryError):
            # Preserve scan-engine validation of missing or non-directory components.
            resolved = path.resolve()
        return resolved
    except (RuntimeError, OSError) as exc:
        shown = spelled[:_MAX_ROOT_ECHO] + ("..." if len(spelled) > _MAX_ROOT_ECHO else "")
        loop = isinstance(exc, RuntimeError) or isinstance(exc, OSError) and exc.errno == errno.ELOOP
        reason = "symlink loop" if loop else type(exc).__name__
        raise ConfigError(f"cannot resolve the scan root {shown!r}: {reason}") from None


def _origin_spellings(spelled: str, *, is_file: bool) -> tuple[Path, ...]:
    """Return the scan-root spellings the M6 boundary anchors besides the resolved root.

    ``os.path.abspath`` joins a relative root onto the *physical* current directory,
    so after ``cd <checkout>/docs`` with ``docs`` a symlink out of the checkout the
    unresolved spelling is already outside and the checkout would drop out of the
    boundary; the logical directory survives only in ``$PWD`` (amended 2026-11-03,
    N5). ``$PWD`` is therefore used too, but only when it is absolute and names the
    current directory (``os.path.samefile``): then ``$PWD`` itself and the root
    joined onto it are added. Extra anchors can only widen the boundary, so a
    spoofed ``$PWD`` cannot admit anything; an unusable one is ignored, never raised.
    For a file root the containing directory and the file itself are both given (the
    file so that a symlinked root file's link chain is walked, L1).

    :param spelled: The root argument as the invoker typed it.
    :param is_file: Whether the root is a file.
    :returns: The spellings, deduplicated, physical spelling first.
    """
    given = os.path.abspath(spelled)
    found = [os.path.dirname(given) if is_file else given, given]
    pwd = os.environ.get("PWD")
    if pwd and os.path.isabs(pwd):
        try:
            same = os.path.samefile(pwd, os.curdir)
        except (OSError, ValueError):
            # Fail closed: an unusable $PWD only means fewer extra anchors, never an error.
            same = False
        if same:
            logical = os.path.normpath(os.path.join(pwd, spelled))
            found.extend((pwd, os.path.dirname(logical) if is_file else logical, logical))
    return tuple(Path(entry) for entry in dict.fromkeys(found))


def _doctor_extension_lines(settings: Optional[Config], error: Optional[Exception]) -> list[str]:
    """Return the ``doctor`` lines describing report extensions, without importing any (M32).

    Lists the ``telemetry_extensions`` of the configuration discovered in the
    current directory (neutralized) and the ``python:`` gate state. A configuration
    error -- such as a ``python:`` entry, which configuration may never hold -- is
    reported on one neutralized line.

    :param settings: The configuration of the current directory, or ``None`` when
        loading it failed.
    :param error: The configuration error, or ``None``.
    :returns: The formatted lines.
    """
    gate = "on" if _python_extensions_allowed(False) else "off"
    lines = [f"python extensions gate: {gate} (--allow-python-extensions or {ALLOW_PYTHON_EXTENSIONS_ENV}=1)"]
    if settings is None:
        lines.append(f"report extensions (telemetry_extensions): error: {neutralize_text(str(error))}")
        return lines
    listed = ", ".join(neutralize_text(spec[:80]) for spec in settings.telemetry_extensions)
    lines.append(f"report extensions (telemetry_extensions): {listed or '(none)'}")
    return lines


def _doctor_reference_scope_line(settings: Optional[Config], error: Optional[Exception]) -> str:
    """Return the ``doctor`` line naming the effective reference scope of the current directory.

    The scope comes from the configuration discovered in the current directory. A
    configuration error is reported on the same line, neutralized, instead of
    failing ``doctor``.

    :param settings: The configuration of the current directory, or ``None`` when
        loading it failed.
    :param error: The configuration error, or ``None``.
    :returns: ``reference scope: <value> (DS103 on|off)``, or an error line.
    """
    if settings is None:
        return f"reference scope: error: {neutralize_text(str(error))}"
    state = "on" if opt_in_satisfied(RULES["DS103"], settings) else "off"
    return f"reference scope: {settings.reference_scope} (DS103 {state})"


def _option_count(count: int) -> str:
    """Return ``count`` options as text.

    :param count: The number of option names.
    :returns: ``"1 option"`` or ``"<count> options"``.
    """
    return f"{count} option" if count == 1 else f"{count} options"


def _doctor_config_source_lines(
    sources: Optional[ConfigSources], error: Optional[Exception], *, no_user_settings: bool
) -> list[str]:
    """Return the ``doctor`` lines naming the configuration sources of the current directory.

    The user settings file is shown in tilde form and the project file by its name
    only, so the absolute home path never appears (threat model 0009-user-settings
    U11); only option counts are shown, never values. A configuration error gives
    one neutralized line instead, and ``doctor`` still exits ``0``.

    :param sources: The sources from :func:`~docsentinel.config.load_config_with_sources`,
        or ``None`` when loading failed.
    :param error: The configuration error, or ``None``.
    :param no_user_settings: Whether ``--no-user-settings`` was given.
    :returns: ``user settings: ...`` and ``project config: ...``, or one error line.
    """
    if sources is None:
        return [f"config sources: error: {neutralize_text(str(error))}"]
    if sources.user_state == "loaded" and sources.user is not None:
        user = f"{_tilde_path(sources.user)} (loaded, {_option_count(len(sources.user_options))})"
    elif sources.user_state == "missing":
        try:
            path, _ = user_settings_path()
        except ConfigError:
            path = None
        user = "missing" if path is None else f"{_tilde_path(path)} (missing)"
    elif sources.user_state == "off":
        user = "off (--no-user-settings)" if no_user_settings else f"off ({USER_SETTINGS_ENV}={USER_SETTINGS_OFF})"
    else:
        user = "none (home directory unknown)"
    if sources.project is None:
        project = "none"
    else:
        project = f"{safe(sources.project.name)} ({_option_count(len(sources.project_options))})"
    return [f"user settings: {user}", f"project config: {project}"]


def _doctor_selection_lines(
    settings: Optional[Config], sources: Optional[ConfigSources], error: Optional[Exception]
) -> list[str]:
    """Return the ``doctor`` lines counting the ``include`` and ``exclude`` patterns.

    The source is the project file name when that file sets the key, else
    ``default``; never the user settings file, which may not set either key
    (ADR 0005 C6). Only counts are shown, never a pattern.

    :param settings: The configuration of the current directory, or ``None`` when
        loading it failed.
    :param sources: Its sources, or ``None`` when loading failed.
    :param error: The configuration error, or ``None``.
    :returns: ``include: <n> pattern(s) (<source>)`` and the same for ``exclude``,
        or one error line.
    """
    if settings is None or sources is None:
        return [f"selection: error: {neutralize_text(str(error))}"]
    lines = []
    for key, patterns in (("include", settings.include), ("exclude", settings.exclude)):
        project_set = sources.project is not None and key in sources.project_options
        source = safe(sources.project.name) if project_set else "default"
        lines.append(f"{key}: {len(patterns)} pattern(s) ({source})")
    return lines


def _config_sources_text(sources: ConfigSources) -> str:
    """Return the text of the ``INFO`` ``config:`` line of ``scan`` and ``baseline``.

    Names the user-layer state, the user-layer option names (sorted, at most
    :data:`MAX_LOGGED_OPTION_NAMES`, then ``and N more``) and the project file name.
    Option values and the absolute home path never appear (threat model
    0009-user-settings A10, U11, U16).

    :param sources: The sources of the effective configuration.
    :returns: For example ``user settings loaded (ignore, reference_scope), project
        docsentinel.toml``.
    """
    text = f"user settings {sources.user_state}"
    names = tuple(sorted(sources.user_options))
    if names:
        listed = ", ".join(names[:MAX_LOGGED_OPTION_NAMES])
        if len(names) > MAX_LOGGED_OPTION_NAMES:
            listed += f" and {len(names) - MAX_LOGGED_OPTION_NAMES} more"
        text += f" ({listed})"
    project = "none" if sources.project is None else safe(sources.project.name)
    return f"{text}, project {project}"


PROJECT_ROOT_MARKERS = ("uv.lock", "pyproject.toml")


def find_project_root(start: Path) -> Optional[Path]:
    """Find the nearest directory at or above ``start`` that marks a project root.

    Parameters
    ----------
    start : Path
        Directory to begin the upward search from.

    Returns
    -------
    Optional[Path]
        The first directory holding ``uv.lock`` or ``pyproject.toml``, or ``None`` when
        the search reaches the filesystem root without finding either.
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        if any((candidate / marker).is_file() for marker in PROJECT_ROOT_MARKERS):
            return candidate
    return None


def _run_init(root: Path, *, project_root: bool, assume_yes: bool) -> int:
    """Create a starter ``docsentinel.toml``.

    Parameters
    ----------
    root : Path
        Directory to create the file in, or to start the project-root search from.
    project_root : bool
        When true, use the nearest ancestor of ``root`` holding ``uv.lock`` or ``pyproject.toml``.
    assume_yes : bool
        When true, never ask for confirmation. Without it, confirmation is requested only
        when standard input is an interactive terminal, so scripts and CI never block.

    Returns
    -------
    int
        0 when the file was created or the user declined, 2 on failure.
    """
    directory = root
    if project_root:
        found = find_project_root(root)
        if found is None:
            names = " or ".join(PROJECT_ROOT_MARKERS)
            print(f"No {names} found at or above {root.resolve()}", file=sys.stderr)
            logger.warning("init failed: no %s at or above %s", names, safe(root.resolve()), extra=FILE_ONLY)
            return 2
        directory = found
    target = directory / "docsentinel.toml"
    legacy = directory / "doc_sentinel.toml"
    if legacy.exists():
        print(f"{legacy} already configures DocSentinel; not creating a second config file", file=sys.stderr)
        logger.warning("init failed: %s already exists", safe(legacy), extra=FILE_ONLY)
        return 2
    if target.exists():
        print(f"{target} already exists; not overwriting it", file=sys.stderr)
        logger.warning("init failed: %s already exists", safe(target), extra=FILE_ONLY)
        return 2
    if not assume_yes and sys.stdin.isatty():
        try:
            answer = input(f"Create {target}? [Y/n] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("", "y", "yes"):
            print("Aborted: no file created")
            return 0
    try:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(TEMPLATE)
    except OSError as exc:
        print(f"Cannot create {target}: {neutralize_text(str(exc))}", file=sys.stderr)
        logger.exception("init failed: cannot create %s", safe(target), extra=FILE_ONLY)
        return 2
    print(f"Created {target}")
    logger.debug("created %s", safe(target))
    return 0


def _init_user_refused(message: str) -> int:
    """Print an ``init --user`` refusal and log it to the log file only.

    :param message: The neutralized message; paths in it are in tilde form.
    :returns: ``2``.
    """
    print(message, file=sys.stderr)
    logger.warning("init failed: %s", safe(message), extra=FILE_ONLY)
    return 2


def _missing_directories(directory: Path) -> tuple[Path, list[Path]]:
    """Split ``directory`` into its deepest existing ancestor and the directories to create.

    Only ``os.path.lexists()`` is used, so a dangling symlink counts as existing and
    is then refused by the R3 walk rather than created through.

    :param directory: The absolute directory that must hold the settings file.
    :returns: The deepest existing ancestor (``directory`` itself when it exists) and
        the missing directories, outermost first.
    """
    missing: list[Path] = []
    existing = directory
    while not os.path.lexists(existing) and existing.parent != existing:
        missing.append(existing)
        existing = existing.parent
    missing.reverse()
    return existing, missing


def _run_init_user(*, assume_yes: bool) -> int:
    """Create the starter user settings file (``init --user``, story 03.0 decision S10).

    The location is :func:`~docsentinel.config.user_settings_path` (so
    ``DOCSENTINEL_SETTINGS`` is honoured). Before anything is created, the deepest
    existing directory and every symbolic link on the way to it pass the same R3
    check the loader applies (POSIX only); then each missing directory is created
    with mode ``0o700`` and the file with ``O_EXCL``/``O_NOFOLLOW`` and mode
    ``0o600``, re-applied with ``fchmod`` so the umask cannot change it (threat
    model 0009-user-settings U15, A8). An existing file or symlink is never
    overwritten or followed. Every message shows the path in tilde form.

    :param assume_yes: When true, never ask for confirmation; otherwise ask only on
        an interactive terminal, as ``init`` does.
    :returns: ``0`` when the file was created or the user declined, ``2`` on refusal
        or failure.
    """
    try:
        path, state = user_settings_path()
    except ConfigError as exc:
        # The message never echoes the refused environment value (ADR 0005 Contract 5).
        refusal = f"Cannot create the user settings file: {neutralize_text(str(exc))}"
        return _init_user_refused(refusal)
    if state == "off":
        return _init_user_refused(
            f"Cannot create the user settings file: user settings are off ({USER_SETTINGS_ENV}={USER_SETTINGS_OFF})"
        )
    if path is None:
        return _init_user_refused(
            "Cannot create the user settings file: the home directory is unknown; "
            f"set {USER_SETTINGS_ENV} to an absolute path"
        )
    shown = _tilde_path(path)
    if os.path.lexists(path):
        return _init_user_refused(f"{shown} already exists; not overwriting it")
    existing, missing = _missing_directories(path.parent)
    if os.name == "posix":
        try:
            _check_user_settings_directories(existing, final_is_directory=True)
        except ConfigError as exc:
            # The same fixed R3 phrase the loader's gate uses, so nothing is created.
            refusal = f"Cannot create user settings {shown}: {neutralize_text(str(exc))}"
            return _init_user_refused(refusal)
    if not assume_yes and sys.stdin.isatty():
        try:
            answer = input(f"Create {shown}? [Y/n] ").strip().lower()
        except EOFError:
            answer = "n"
        if answer not in ("", "y", "yes"):
            print("Aborted: no file created")
            return 0
    created = False
    try:
        for directory in missing:
            os.mkdir(directory, 0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path, flags, 0o600)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            if hasattr(os, "fchmod"):
                os.fchmod(stream.fileno(), 0o600)
            stream.write(USER_SETTINGS_TEMPLATE)
    except OSError as exc:
        if created:
            # Never leave a half-written file that the next load would refuse.
            try:
                os.unlink(path)
            except OSError as cleanup:
                logger.debug("cannot remove the partial user settings file %s (%s)", shown, type(cleanup).__name__)
        if isinstance(exc, FileExistsError) and not created:
            return _init_user_refused(f"{shown} already exists; not overwriting it")
        # The reason only: the exception text would carry the absolute path (U11).
        reason = neutralize_text(exc.strerror or type(exc).__name__)
        return _init_user_refused(f"Cannot create user settings {shown}: {reason}")
    print(f"Created {shown}")
    logger.debug("created user settings %s", shown)
    return 0


def _add_verbosity_options(parser: argparse.ArgumentParser, *, suppress: bool):
    """Add ``-v/--verbose`` and ``-q/--quiet`` to ``parser``.

    :param parser: The top-level parser or the shared subcommand parent parser.
    :param suppress: ``True`` for the subcommand copy, whose absent flags must not
        overwrite the values parsed before the subcommand name.
    """
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=argparse.SUPPRESS if suppress else 0,
        help="Show debug messages on stderr (DOCSENTINEL_LOG_LEVEL overrides)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=argparse.SUPPRESS if suppress else False,
        help="Show only warnings and errors on stderr (DOCSENTINEL_LOG_LEVEL overrides)",
    )


#: The values of ``--reference-scope`` (the ``reference_scope`` vocabulary).
REFERENCE_SCOPES = ("links", "strict")


def _add_selector_options(parser: argparse.ArgumentParser):
    """Add the repeatable ``--include`` and ``--exclude`` flags (ADR 0006 Contract 6).

    :param parser: The ``scan`` or ``baseline`` subparser.
    """
    parser.add_argument(
        "--include",
        action="append",
        default=None,
        metavar="PATTERN",
        help=(
            "Select documents: a glob, file or directory relative to the scan root (or absolute inside it); "
            "repeatable; replaces include in the config. Use --include=VALUE for a value starting with -"
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        metavar="PATTERN",
        help=(
            "Leave out documents: a glob, file or directory relative to the scan root (or absolute inside it); "
            "repeatable; appended to exclude in the config, and wins over --include"
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    """Return the ``docsentinel`` argument parser.

    :returns: The parser with every subcommand.
    """
    parser = argparse.ArgumentParser(prog="docsentinel")
    _add_verbosity_options(parser, suppress=False)
    # Subcommands repeat -v/-q with suppressed defaults, so both "docsentinel -v scan"
    # and "docsentinel scan -v" work and an absent subcommand flag keeps the global one.
    verbosity = argparse.ArgumentParser(add_help=False)
    _add_verbosity_options(verbosity, suppress=True)
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan", help="Inventory Markdown documents", parents=[verbosity])
    scan_parser.add_argument("root", nargs="?", default=".", help="Directory or file to check")
    scan_parser.add_argument("--config", type=Path)
    scan_parser.add_argument("--profile", choices=("fast", "standard", "deep"))
    scan_parser.add_argument("--select", type=str, default=None)
    scan_parser.add_argument("--ignore", type=str, default=None)
    scan_parser.add_argument("--baseline", type=Path, default=None)
    scan_parser.add_argument(
        "--link-root",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Directory that site-root-absolute links (/docs/x.md) resolve against: an absolute path or one "
            "relative to the current directory; must be the scan root or an ancestor (not /). Trusted; "
            "overrides link_root in the config."
        ),
    )
    scan_parser.add_argument(
        "--reference-scope",
        choices=REFERENCE_SCOPES,
        default=None,
        help=(
            'Which references are checked: "links" (links and @-mentions) or "strict" (also path-like '
            "inline code spans, DS103); overrides reference_scope in the config"
        ),
    )
    scan_parser.add_argument(
        "--format",
        default=DEFAULT_TEMPLATE,
        metavar="NAME",
        help=(
            f"Report template name: one of {', '.join(packaged_template_names())}, "
            "or a template in report_templates_dir (default: %(default)s)"
        ),
    )
    scan_parser.add_argument(
        "--template",
        type=Path,
        default=None,
        metavar="PATH",
        help="Render with this template file (wins over --format)",
    )
    scan_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Write the report to this file (UTF-8, overwritten; parent directories are created) "
            "instead of standard output; relative paths resolve against the current directory"
        ),
    )
    scan_parser.add_argument(
        "--show-clean-documents",
        action="store_true",
        help="List documents without problems in the text report as well",
    )
    scan_parser.add_argument(
        "--extension",
        action="append",
        default=[],
        dest="extensions",
        metavar="SPEC",
        help="Report extension: builtin:<name>, or python:<module>:<callable> (needs --allow-python-extensions)",
    )
    scan_parser.add_argument(
        "--allow-python-extensions",
        action="store_true",
        help=(
            "Allow python: extensions given with --extension to run (they execute arbitrary code); "
            f"also {ALLOW_PYTHON_EXTENSIONS_ENV}=1"
        ),
    )
    _add_selector_options(scan_parser)
    scan_parser.add_argument("--no-user-settings", action="store_true", help=NO_USER_SETTINGS_HELP)
    scan_parser.add_argument("--strict", action="store_true")
    scan_parser.add_argument(
        "--i-understand-deep-is-heuristic",
        action="store_true",
        dest="deep_confirm",
        help="Explicitly confirm execution of heuristic deep profile detectors",
    )
    baseline_parser = commands.add_parser(
        "baseline", help="Record current findings into a baseline file", parents=[verbosity]
    )
    baseline_parser.add_argument("root", nargs="?", default=".", help="Directory or file to check")
    baseline_parser.add_argument("--config", type=Path)
    baseline_parser.add_argument("--output", type=Path)
    baseline_parser.add_argument("--profile", choices=("fast", "standard", "deep"))
    baseline_parser.add_argument(
        "--link-root",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Directory that site-root-absolute links (/docs/x.md) resolve against: an absolute path or one "
            "relative to the current directory; must be the scan root or an ancestor (not /). Trusted; "
            "overrides link_root in the config."
        ),
    )
    baseline_parser.add_argument(
        "--reference-scope",
        choices=REFERENCE_SCOPES,
        default=None,
        help=(
            'Which references are checked: "links" (links and @-mentions) or "strict" (also path-like '
            "inline code spans, DS103); overrides reference_scope in the config"
        ),
    )
    _add_selector_options(baseline_parser)
    baseline_parser.add_argument("--no-user-settings", action="store_true", help=NO_USER_SETTINGS_HELP)
    init_parser = commands.add_parser("init", help="Create a starter config", parents=[verbosity])
    init_parser.add_argument(
        "root", nargs="?", default=".", help="Directory for docsentinel.toml (default: current directory)"
    )
    init_target = init_parser.add_mutually_exclusive_group()
    init_target.add_argument(
        "--project-root",
        action="store_true",
        help="Create the file at the nearest ancestor of ROOT that holds uv.lock or pyproject.toml",
    )
    init_target.add_argument(
        "--user",
        action="store_true",
        help=(
            f"Create the user settings file instead ({USER_SETTINGS_HELP_PATH}, under $XDG_DATA_HOME when set, "
            f"or the absolute path in {USER_SETTINGS_ENV}); never overwrites it; refused when "
            f"{USER_SETTINGS_ENV}={USER_SETTINGS_OFF}"
        ),
    )
    init_parser.add_argument(
        "--yes", "-y", action="store_true", help="Do not ask for confirmation when running in a terminal"
    )
    commands.add_parser("rules", help="List active detection rules", parents=[verbosity])
    doctor_parser = commands.add_parser("doctor", help="Show M0 capabilities", parents=[verbosity])
    doctor_parser.add_argument("--no-user-settings", action="store_true", help=NO_USER_SETTINGS_HELP)
    return parser


class _UnexpectedErrorLog:
    """Context manager that logs an unexpected exception at ``ERROR`` and lets it propagate.

    The traceback reaches the log file only; stderr gets one line plus the log file
    path, then Python's own traceback as before. The exit code is unchanged.
    """

    def __init__(self, log_path: Optional[Path]):
        """Remember the per-run log file to name on failure.

        :param log_path: The per-run log file, or ``None`` when there is none.
        """
        self._log_path = log_path

    def __enter__(self) -> "_UnexpectedErrorLog":
        """Enter the guarded block.

        :returns: This guard.
        """
        return self

    def __exit__(self, exc_type: Optional[type], exc: Optional[BaseException], traceback: object) -> bool:
        """Log an escaping ``Exception`` (never ``KeyboardInterrupt``/``SystemExit``).

        :param exc_type: The exception type, or ``None``.
        :param exc: The exception, or ``None``.
        :param traceback: The traceback, or ``None``.
        :returns: ``False``, so the exception always propagates.
        """
        if exc_type is not None and issubclass(exc_type, Exception):
            logger.error("unexpected error: %s: %s", exc_type.__name__, safe(exc), exc_info=(exc_type, exc, traceback))
            if self._log_path is not None:
                logger.info("details in log file: %s", safe(self._log_path))
        return False


def main(argv: Optional[list[str]] = None) -> int:
    """Run the DocSentinel command line interface.

    Logging is configured after argument parsing (``-v``/``-q``) and always shut
    down again; it writes to stderr and the per-run log file only, never to
    stdout, and never changes the exit code.

    Parameters
    ----------
    argv : Optional[list[str]]
        Command-line arguments; defaults to ``sys.argv[1:]`` when omitted.

    Returns
    -------
    int
        Process exit code: 0 on success, 1 for blocking findings, 2 on failure.
    """
    args = _build_parser().parse_args(argv)
    log_path = configure_cli_logging(verbosity=-1 if args.quiet else args.verbose)
    try:
        with _UnexpectedErrorLog(log_path):
            code = _dispatch(args)
        if code != 0 and log_path is not None:
            logger.info("details in log file: %s", safe(log_path))
        return code
    finally:
        shutdown_cli_logging()


def _dispatch(args: argparse.Namespace) -> int:
    """Run the parsed subcommand.

    :param args: The parsed command line.
    :returns: The process exit code.
    """
    logger.debug("command: %s", args.command)
    if args.command == "init":
        if args.user:
            return _run_init_user(assume_yes=args.yes)
        return _run_init(Path(args.root), project_root=args.project_root, assume_yes=args.yes)
    if args.command == "rules":
        for profile in ("fast", "standard", "deep"):
            print(f"{profile}:")
            if profile == "standard":
                for line in _standard_rule_lines():
                    print(line)
            else:
                registered = rules_for_profile(profile)
                if registered:
                    for rule in registered:
                        print(f"  {rule.code}: {rule.title}{_opt_in_suffix(rule)}")
                else:
                    print("  (none registered)")
        return 0
    if args.command == "doctor":
        print("Inventory: available")
        standard_lines = _standard_rule_lines()
        if standard_lines == ["standard profile: install docsentinel[standard] to enable (DS2xx)"]:
            print("standard profile: not installed (pip install docsentinel[standard])")
        else:
            print("standard profile: available")
        for line in _deep_doctor_lines():
            print(line)
        for profile in ("fast", "standard", "deep"):
            registered = rules_for_profile(profile)
            opt_in = tuple(rule for rule in registered if rule.opt_in_option)
            summary = f"{profile} rules: {len(registered)} registered"
            if opt_in:
                codes = ", ".join(rule.code for rule in opt_in)
                summary += f" ({len(opt_in)} opt-in, off unless configured: {codes})"
            print(summary)
        # One load shared by every config-dependent line (ADR 0005 affected components).
        settings: Optional[Config] = None
        sources: Optional[ConfigSources] = None
        error: Optional[Exception] = None
        try:
            settings, sources = load_config_with_sources(Path.cwd(), user_settings=not args.no_user_settings)
        except (ConfigError, OSError) as exc:
            error = exc
        for line in _doctor_template_lines(settings, error):
            print(line)
        for line in _doctor_extension_lines(settings, error):
            print(line)
        for line in _doctor_config_source_lines(sources, error, no_user_settings=args.no_user_settings):
            print(line)
        for line in _doctor_selection_lines(settings, sources, error):
            print(line)
        print(_doctor_reference_scope_line(settings, error))
        return 0
    if args.command == "baseline":
        return _run_baseline(args)
    return _run_scan(args)


def _finding_totals(result: ScanResult) -> tuple[int, int, str]:
    """Return the error count, warning count and per-rule counts of ``result``.

    :param result: The scan result.
    :returns: ``(errors, warnings, "DS101=2, DS103=1")``; the last is ``"none"`` without findings.
    """
    errors = sum(1 for finding in result.findings if finding.severity == "error")
    warnings = sum(1 for finding in result.findings if finding.severity == "warning")
    by_rule = Counter(finding.rule for finding in result.findings)
    text = ", ".join(f"{code}={count}" for code, count in sorted(by_rule.items()))
    return errors, warnings, text or "none"


def _blocking_count(result: ScanResult, *, strict: bool) -> int:
    """Return how many findings block the run, matching :func:`_exit_code`.

    :param result: The scan result.
    :param strict: Whether ``--strict`` was given.
    :returns: ``0`` for the advisory deep profile, every finding under ``strict``,
        otherwise the error findings.
    """
    if result.profile == "deep":
        return 0
    if strict:
        return len(result.findings)
    return sum(1 for finding in result.findings if finding.severity == "error")


def _validate_selectors(args: argparse.Namespace, target: Path):
    """Validate ``--include``/``--exclude`` before ``scan started`` is logged (ADR 0006 Contract 6).

    Mirrors the engine exactly: the shape checks run for every target, and a
    directory target is normalised with the same canonical root (``target`` from
    :func:`_resolve_root`) and the same root spellings
    (:func:`~docsentinel.discovery.selector_root_spellings` of the root as typed).
    The result is discarded and nothing is logged; :func:`~docsentinel.engine.scan`
    normalises the raw lists again and logs the warnings once.

    :param args: The parsed ``scan`` or ``baseline`` command line.
    :param target: The canonical scan root (a directory or a single file).
    :raises ConfigError: For a refused selector value.
    """
    if args.include is None and args.exclude is None:
        return
    check_invoker_selector_shape(args.include, args.exclude)
    if not target.is_file():
        normalize_invoker_selectors(
            target,
            args.include,
            args.exclude,
            root_spellings=selector_root_spellings(target, args.root),
        )


def _scan_overrides(args: argparse.Namespace) -> dict[str, object]:
    """Return the ``scan()`` keywords the invoker gave, so unset ones are not passed.

    :param args: The parsed ``scan`` or ``baseline`` command line.
    :returns: ``link_root``, ``include`` and ``exclude`` when given.
    """
    overrides: dict[str, object] = {}
    if args.link_root is not None:
        overrides["link_root"] = args.link_root
    if args.include is not None:
        overrides["include"] = tuple(args.include)
    if args.exclude is not None:
        overrides["exclude"] = tuple(args.exclude)
    return overrides


def _run_baseline(args: argparse.Namespace) -> int:
    """Run ``docsentinel baseline``.

    :param args: The parsed command line.
    :returns: ``0`` when the baseline was saved, ``2`` on failure.
    """
    started = time.perf_counter()
    try:
        target = _resolve_root(args.root)
        directory = target.parent if target.is_file() else target
        settings, sources = load_config_with_sources(directory, args.config, user_settings=not args.no_user_settings)
        if args.profile is not None:
            settings = replace(settings, profile=args.profile)
        if args.reference_scope is not None:
            settings = replace(settings, reference_scope=args.reference_scope)
        if args.output is not None:
            output_path = Path(args.output) if Path(args.output).is_absolute() else Path.cwd() / args.output
        elif settings.baseline is not None:
            output_path = (
                Path(settings.baseline) if Path(settings.baseline).is_absolute() else directory / settings.baseline
            )
        else:
            output_path = directory / ".docsentinel-baseline.json"
        _validate_selectors(args, target)

        logger.info(
            "baseline started: root=%s, profile=%s, output=%s, reference_scope=%s",
            safe(args.root),
            settings.profile,
            safe(output_path),
            safe(settings.reference_scope),
        )
        logger.info("config: %s", _config_sources_text(sources))
        unbaselined_config = replace(settings, baseline=None)
        result = scan(args.root, config=unbaselined_config, **_scan_overrides(args))
        save_baseline(output_path, result.findings)
    except (ConfigError, ValueError) as exc:
        print(f"Baseline generation failed: {neutralize_text(str(exc))}", file=sys.stderr)
        logger.warning("baseline failed: %s", safe(exc), extra=FILE_ONLY)
        return 2
    except OSError as exc:
        print(f"Baseline generation failed: {neutralize_text(str(exc))}", file=sys.stderr)
        logger.exception("baseline failed: %s", safe(exc), extra=FILE_ONLY)
        return 2
    print(f"Saved baseline: {output_path}")
    errors, warnings, by_rule = _finding_totals(result)
    logger.info(
        "baseline finished in %.2fs: %d documents, %d findings recorded (errors %d, warnings %d); by rule %s; "
        "written to %s; exit code 0",
        time.perf_counter() - started,
        len(result.documents),
        len(result.findings),
        errors,
        warnings,
        by_rule,
        safe(output_path),
    )
    return 0


def _run_scan(args: argparse.Namespace) -> int:
    """Run ``docsentinel scan``.

    :param args: The parsed command line.
    :returns: The exit code of :func:`_exit_code`, or ``2`` on failure.
    """
    started = time.perf_counter()
    report_format = str(args.template) if args.template is not None else args.format
    try:
        target = _resolve_root(args.root)
        directory = target.parent if target.is_file() else target
        # M6 (F1, N5, L1): the unresolved and the logical ($PWD) spellings keep the
        # checkout in the extension boundary when the root, a root file or the cwd is
        # a symlink pointing out of it.
        origins = _origin_spellings(args.root, is_file=target.is_file())
        settings, sources = load_config_with_sources(directory, args.config, user_settings=not args.no_user_settings)
        changes = {}
        if args.profile is not None:
            changes["profile"] = args.profile
        if args.select is not None:
            changes["select"] = tuple(item.strip() for item in args.select.split(",") if item.strip())
        if args.ignore is not None:
            changes["ignore"] = tuple(item.strip() for item in args.ignore.split(",") if item.strip())
        if args.baseline is not None:
            changes["baseline"] = str(args.baseline)
        if args.reference_scope is not None:
            changes["reference_scope"] = args.reference_scope
        if getattr(args, "deep_confirm", False):
            changes["deep_confirm"] = True
        if args.show_clean_documents:
            changes["report_show_clean_documents"] = True
        if changes:
            settings = replace(settings, **changes)
        # M30 order: gate and resolve extensions -> template -> requires check -> scan.
        allow_python = _python_extensions_allowed(args.allow_python_extensions)
        loaded = _report_extensions(
            args.extensions, settings, directory, allow_python=allow_python, origin_roots=origins
        )
        if loaded.builtin_specs != settings.telemetry_extensions:
            settings = replace(settings, telemetry_extensions=loaded.builtin_specs)
        template = _report_template(args.format, args.template, settings, directory)
        check_template(template, loaded)
        _validate_selectors(args, target)
        # Logged once every user input is validated, so a config, extension or template
        # error leaves "Scan failed:" as the first stderr line.
        logger.info(
            "scan started: root=%s, profile=%s, format=%s, output=%s, reference_scope=%s",
            safe(args.root),
            settings.profile,
            safe(report_format),
            "stdout" if args.output is None else safe(args.output),
            safe(settings.reference_scope),
        )
        logger.info("config: %s", _config_sources_text(sources))
        # Pass link_root, include and exclude only when given, so callers wrapping
        # scan() keep working.
        result = scan(args.root, config=settings, **_scan_overrides(args))
        report = render(
            result, config=settings, template=template, root=directory, strict=args.strict, extensions=loaded
        )
        if args.output is not None:
            written = _write_report(args.output, report)
            logger.info(
                "report written to %s (%s, %d lines)", safe(written), safe(report_format), report.count("\n") + 1
            )
    except (ConfigError, ExtensionError, ValueError, TemplateError, NotImplementedError) as exc:
        print(f"Scan failed: {neutralize_text(str(exc))}", file=sys.stderr)
        logger.warning("scan failed: %s", safe(exc), extra=FILE_ONLY)
        return 2
    except OSError as exc:
        print(f"Scan failed: {neutralize_text(str(exc))}", file=sys.stderr)
        logger.exception("scan failed: %s", safe(exc), extra=FILE_ONLY)
        return 2
    if args.output is None:
        print(report)
    exit_code = _exit_code(result, strict=args.strict)
    errors, warnings, by_rule = _finding_totals(result)
    logger.info(
        "scan finished in %.2fs: %d documents, %d findings (errors %d, warnings %d); by rule %s; blocking %d; "
        "exit code %d",
        time.perf_counter() - started,
        len(result.documents),
        len(result.findings),
        errors,
        warnings,
        by_rule,
        _blocking_count(result, strict=args.strict),
        exit_code,
    )
    return exit_code


def _write_report(output: Path, report: str) -> Path:
    """Write a rendered report to ``output`` exactly as ``print`` would emit it.

    The file holds the report plus one trailing newline, encoded as UTF-8 with ``\\n`` line endings
    on every platform, so a file report is byte-identical to redirected standard output on POSIX.
    The report is rendered completely before this runs, so a template or scan failure never leaves
    a truncated file behind.

    :param output: The report path; a relative path resolves against the current directory.
    :param report: The rendered report text.
    :returns: The absolute path written.
    :raises OSError: When the parent directory cannot be created or the file cannot be written.
    """
    path = output if output.is_absolute() else Path.cwd() / output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report + "\n", encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    sys.exit(main())
