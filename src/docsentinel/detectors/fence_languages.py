"""Detect fenced code blocks that lack a required language label (``DS110``).

This fast, standard-library-only analyzer reuses the shared Markdown block
scanner in :mod:`docsentinel.markdown_blocks` rather than re-parsing fences. It
reports an opt-in documentation policy: when ``require_fence_languages`` is
enabled, a meaningful fenced code block must name its language in the info
string (``python``, ``bash``, ``text``, ``console``, ``diff``, ...). The first
whitespace-delimited token of the info string is the language; anything that
follows it (for example ``python title="example"`` or ``python {.line-numbers}``)
is treated as trailing attributes, so such a fence still counts as labelled.

The policy is **off by default**: with ``require_fence_languages = false`` the
rule is not applicable and emits nothing, so a disabled optional policy never
masquerades as an evaluated clean result. When enabled:

* a nonempty fence with no language token is flagged;
* an empty fence with no language token is exempt while
  ``allow_unlabelled_empty_fences`` is true (the default) and flagged once that
  exemption is turned off;
* a labelled fence is clean unless ``allowed_fence_languages`` is a non-empty
  allowlist that does not contain its language, in which case the unknown
  language is flagged. ``text`` and ``plaintext`` are ordinary labels and are
  only special when an allowlist omits them.

``DS110`` owns only fence *metadata*. Delimiter problems belong to ``DS109``: a
fence that was never successfully closed, or a backtick opener whose info string
carries a backtick (which ``DS109`` reports as a malformed opener), is skipped
here so one malformed fence never cascades into two findings.

The analyzer performs no network, subprocess, or symlink I/O and never executes
embedded code; it only reads the UTF-8 text of Markdown documents it is handed.

``DS110`` is registered in :data:`docsentinel.rules.RULES` and
:data:`docsentinel.rules.ANALYZERS` as an import side effect of this module, so
it runs as an exact ``fast``-profile rule. It is an *optional* policy that is off
by default: with ``require_fence_languages`` unset the rule is enabled but
applicable to nothing, so it never emits a finding until a project opts in. The
Milestone 0005 fixture catalog is registration gated: registration and engine
wiring land together with the committed ``tests/assets/ds110/*`` fixtures (Story
07.0 Task 02), never before them.
"""

from pathlib import Path
from typing import Optional

from docsentinel import models, rules
from docsentinel.config import Config
from docsentinel.markdown_blocks import Fence, scan_markdown

#: Stable metadata for ``DS110``, registered as a ``fast``-profile rule alongside
#: its committed ``tests/assets/ds110/*`` fixtures (Story 07.0 Task 02).
DS110 = rules.register_rule(
    rules.Rule(
        code="DS110",
        profile="fast",
        title="Missing language labels on code fences",
        description="A meaningful fenced code block omits the language label required by policy.",
        severity="warning",
        opt_in_option="require_fence_languages",
    )
)

#: Maximum number of characters of a fence language echoed into a finding message,
#: so a pathologically long info string cannot produce an unbounded diagnostic.
_MAX_LANGUAGE_ECHO = 80


def _fence_language(info_string: str) -> str:
    """Return the language token of a fence info string, or ``""`` when absent.

    The scanner already trims the info string, so the language is its first
    whitespace-delimited token; anything after the first whitespace run is
    trailing attributes and is ignored. A ``maxsplit`` of one keeps this
    proportional to the language length rather than to the whole info string.

    :param info_string: The trimmed info string captured by the shared scanner.
    :returns: The first token, or the empty string for a blank info string.
    """
    if not info_string:
        return ""
    return info_string.split(None, 1)[0]


def _is_ds109_owned(fence: Fence) -> bool:
    """Return whether ``DS109`` already owns this fence as a delimiter problem.

    A fence that never closed, or a backtick opener whose info string carries a
    backtick (a malformed opener ``DS109`` reports), is skipped here so one
    malformed fence never produces a second ``DS110`` finding.

    :param fence: A fence token from the shared scanner.
    :returns: ``True`` when ``DS109`` owns the fence and ``DS110`` must defer.
    """
    if not fence.closed:
        return True
    return fence.marker == "`" and "`" in fence.info_string


def _echo(language: str) -> str:
    """Return a bounded, repr-safe echo of a fence language for a message.

    :param language: The language token to echo.
    :returns: The language truncated to :data:`_MAX_LANGUAGE_ECHO` characters,
        with a trailing marker when truncated.
    """
    if len(language) > _MAX_LANGUAGE_ECHO:
        return language[:_MAX_LANGUAGE_ECHO] + "..."
    return language


def _finding(path: str, message: str, line: int) -> models.Finding:
    """Return a ``DS110`` finding at a fence's opener line.

    :param path: POSIX-style relative document path.
    :param message: Smallest meaningful diagnostic message.
    :param line: One-based opener line of the offending fence.
    :returns: A :class:`~docsentinel.models.Finding`.
    """
    return models.Finding(rule=DS110.code, path=path, message=message, severity=DS110.severity, line=line)


def _fence_finding(
    fence: Fence,
    path: str,
    allowed: frozenset[str],
    allow_unlabelled_empty_fences: bool,
) -> Optional[models.Finding]:
    """Return a ``DS110`` finding for one fence, or ``None`` when it is clean.

    :param fence: A fence token from the shared scanner.
    :param path: POSIX-style relative document path.
    :param allowed: The configured language allowlist (empty allows any language).
    :param allow_unlabelled_empty_fences: Whether an empty fence may omit a label.
    :returns: A :class:`~docsentinel.models.Finding` or ``None``.
    """
    if _is_ds109_owned(fence):
        return None
    language = _fence_language(fence.info_string)
    if not language:
        if not fence.body_nonempty and allow_unlabelled_empty_fences:
            return None
        return _finding(path, "fenced code block has no language label", fence.opener_line)
    if allowed and language not in allowed:
        return _finding(
            path, f"fence language {_echo(language)!r} is not in the configured allowlist", fence.opener_line
        )
    return None


def check_text(text: str, path: str, config: Optional[Config] = None) -> tuple[models.Finding, ...]:
    """Return ``DS110`` findings for Markdown ``text`` without touching the filesystem.

    This is the pure recognition entry point used by unit tests with inline
    source strings; :func:`detect` layers document reading over it. When
    ``require_fence_languages`` is false the policy is not applicable and no
    findings are produced, so a disabled policy never implies an evaluated clean
    result. Only the ``gfm-subset`` ``fence_dialect`` is supported; any other
    dialect yields no confident diagnostics.

    :param text: The Markdown source text exactly as read.
    :param path: POSIX-style relative path recorded on each finding.
    :param config: Effective settings, or ``None`` to use defaults.
    :returns: Findings in source order, one per offending fence.
    """
    settings = config if config is not None else Config()
    if not settings.require_fence_languages:
        return ()
    if settings.fence_dialect != "gfm-subset":
        # DS110 reuses DS109's fence tokens; refuse to emit confident diagnostics
        # for a dialect whose fences the shared scanner does not validate.
        return ()
    index = scan_markdown(text, path)
    allowed = frozenset(settings.allowed_fence_languages)
    allow_empty = settings.allow_unlabelled_empty_fences
    findings = [
        finding for fence in index.fences if (finding := _fence_finding(fence, path, allowed, allow_empty)) is not None
    ]
    return tuple(findings)


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a path.

    :param path: Absolute path to the Markdown document.
    :returns: The decoded document text.
    """
    with path.open(encoding="utf-8") as stream:
        return stream.read()


def detect(
    root: Path,
    documents: tuple[models.Document, ...],
    config: Optional[Config] = None,
) -> tuple[models.Finding, ...]:
    """Return ``DS110`` findings for Markdown documents in their supplied order.

    :param root: The resolved scan root directory.
    :param documents: Discovered documents to inspect, in scan order.
    :param config: Effective settings; the engine passes this for configured
        policy handling, and direct callers may omit it to use defaults.
    :returns: Findings across all documents in document then source order.
    """
    settings = config if config is not None else Config()
    findings: list[models.Finding] = []
    for document in documents:
        if not document.path.endswith(".md"):
            continue
        text = _read_text(root / document.path)
        findings.extend(check_text(text, document.path, settings))
    return tuple(findings)


rules.ANALYZERS[DS110.code] = detect
