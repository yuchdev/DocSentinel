"""Render a scan through a report template (Milestone 0007 Story 03.0 Task 02).

Every report -- the human-readable listing, GitHub workflow annotations, the
schema-2 and schema-1 JSON documents, and any user template -- is produced by the
template engine of ``docs/specs/report-template-format.md``: :func:`render` resolves
a template, builds the :class:`~docsentinel.telemetry.model.ReportModel` context and
hands both to :func:`~docsentinel.telemetry.engine.render_template`. This module
holds no output format of its own: no format name, line layout or serializer lives
here, and a unit test parses it to keep it that way (the hardcode-ban tripwire).

A finding's ``path`` and ``message`` -- and a document's ``path`` -- originate in
scanned repository content and are untrusted. The templates route them through the
sink filters of :mod:`docsentinel.telemetry.filters`, and the loader refuses a text
template that would emit one unfiltered. Baseline fingerprints hash the raw
:class:`~docsentinel.models.Finding` fields, never rendered output.

Extensions (spec §9) are resolved here only from explicit arguments: ``render``
never reads the environment, and a ``python:`` spec runs only when the caller passes
``allow_python_extensions=True`` (threat model 0007-extensions M2).

:func:`render_facts` (Milestone 0010 Story 05.0 Task 02) is the same thin shim for a
:class:`~docsentinel.models.FactExtractionResult`: it resolves a ``facts`` template,
builds the :class:`~docsentinel.telemetry.facts_model.FactsModel` context and renders it.
A template of the other context is refused by both shims and by the renderer itself.
Claim text, paths, numbers and entities are untrusted; the facts templates route them
through the same sink filters. ``render_facts`` takes no extensions.
"""

import logging
import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Optional, Union

from docsentinel.config import Config
from docsentinel.log import safe
from docsentinel.models import FactExtractionResult, ScanResult
from docsentinel.telemetry.engine import render_template
from docsentinel.telemetry.extensions import (
    PYTHON_PREFIX,
    ExtensionError,
    LoadedExtensions,
    check_template,
    resolve_extensions,
)
from docsentinel.telemetry.facts_model import FactsModel
from docsentinel.telemetry.filters import TemplateError
from docsentinel.telemetry.filters import neutralize as _neutralize
from docsentinel.telemetry.loader import (
    CONTEXT_FACTS,
    CONTEXT_REPORT,
    DEFAULT_FACTS_TEMPLATE,
    DEFAULT_TEMPLATE,
    Template,
    load_named_template,
    load_template,
    require_context,
)
from docsentinel.telemetry.model import REPORT_SCHEMA_VERSION, ReportModel

logger = logging.getLogger(__name__)


def neutralize_text(value: str) -> str:
    """Return ``value`` with unsafe control, format and surrogate code points escaped.

    Public entry point for output paths outside the report templates (for example
    the command-line error lines), so untrusted text such as a scanned path inside
    an exception message never reaches a terminal or log with raw control bytes.
    Delegates to :func:`docsentinel.telemetry.filters.neutralize`, the table the
    ``neutralize`` template filter applies.

    :param value: Text that may embed untrusted path or content characters.
    :returns: The text with every unsafe code point rendered as a visible escape.
    """
    return _neutralize(value)


def _has_python_spec(extensions: object) -> bool:
    """Return whether an ``extensions=`` sequence holds a ``python:`` spec string.

    :param extensions: The ``extensions`` argument of :func:`render`.
    :returns: The decision; malformed values are left to ``resolve_extensions``.
    """
    if isinstance(extensions, (str, bytes)) or not isinstance(extensions, Sequence):
        return False
    return any(isinstance(spec, str) and spec.startswith(PYTHON_PREFIX) for spec in extensions)


def _resolve(
    format: str,
    template: Union[Template, str, os.PathLike[str], None],
    templates_dir: Optional[str],
    root: Optional[Path],
) -> Template:
    """Return the template to render: ``template`` when given, else ``format`` by name.

    :param format: A template name (packaged, then ``templates_dir``).
    :param template: A loaded template, or an invoker-supplied template file path.
    :param templates_dir: The configured ``report_templates_dir``, or ``None``.
    :param root: The scan root ``report_templates_dir`` is relative to.
    :returns: The validated template.
    :raises TemplateError: On any resolution, read or validation failure.
    """
    if isinstance(template, Template):
        return template
    if template is not None:
        return load_template(Path(os.fspath(template)))
    return load_named_template(format, root=root, templates_dir=templates_dir)


def render(
    result: ScanResult,
    format: str = DEFAULT_TEMPLATE,
    *,
    config: Optional[Config] = None,
    template: Union[Template, str, os.PathLike[str], None] = None,
    root: Optional[Path] = None,
    strict: bool = False,
    extensions: Union[Sequence[str], LoadedExtensions] = (),
    allow_python_extensions: bool = False,
) -> str:
    """Render a scan result through a report template.

    The template is ``template`` when given (a loaded
    ``Template``, or a file path the invoker
    trusts, which still passes the loader's regular-file/size/encoding gate);
    otherwise ``format`` is looked up as a template *name* -- never as a path --
    among the packaged templates and then ``config.report_templates_dir``.

    :param result: Completed scan to render.
    :param format: Template name, e.g. a packaged name listed by ``docsentinel doctor``.
    :param config: The effective configuration; ``Config()`` when omitted. Supplies
        ``report_templates_dir``, ``report_show_clean_documents`` and
        ``report_include_run_meta``, and drives the per-problem classification. Its
        ``telemetry_extensions`` is replaced by the loaded builtin specs, so
        ``doc.domain`` follows ``builtin:domain`` whether it was selected in config,
        in ``extensions`` or in a resolved registry.
    :param template: A template or template file path; wins over ``format``.
    :param root: The scan root ``report_templates_dir`` is resolved against, and the
        anchor of the ``python:`` origin check; required when ``extensions`` holds a
        ``python:`` spec. Pass it as the user spelled it, never pre-resolved, and
        absolute against the logical current directory when the caller knows one: a
        relative ``root`` is made absolute against the physical ``os.getcwd()`` (this
        function never reads ``$PWD``), which can hide a checkout entered through an
        outward symlink (M6, amended 2026-11-03, N5/I2).
    :param strict: Whether warnings are blocking (``--strict``); feeds ``outcome``.
    :param extensions: Extension specs equivalent to ``--extension`` (``builtin:<name>``
        or ``python:<module>:<callable>``), resolved after ``config.telemetry_extensions``;
        or a registry already resolved by
        ``resolve_extensions`` (as the CLI does
        before the scan), used as-is.
    :param allow_python_extensions: The explicit trust gate for ``python:`` specs;
        never taken from the environment.
    :returns: The rendered report.
    :raises ValueError: If the template is unknown, unreadable, invalid, a ``facts``
        template (``template <name> renders fact extraction output; use docsentinel
        extract-facts``), needs an extension that is not loaded, or fails to render;
        the message is bounded and neutralized, and the ``TemplateError``
        is chained as the cause.
    :raises docsentinel.telemetry.extensions.ExtensionError: If an extension is
        refused (including a ``python:`` spec without ``root``), cannot be loaded, or
        fails, or a ``python:`` extension imported a module from the checkout during
        the render (a ``ValueError``; bounded message).
    :raises docsentinel.config.ConfigError: If ``config.telemetry_extensions`` holds a
        non-``builtin:`` entry.
    """
    settings = config if config is not None else Config()
    if isinstance(extensions, LoadedExtensions):
        loaded = extensions
    else:
        if root is None and allow_python_extensions is True and _has_python_spec(extensions):
            raise ExtensionError(
                "a python: extension needs root= (the scan root) so its origin can be checked against the checkout"
            )
        # root/cwd only feed the M6 origin check of a python: spec, so a plain render
        # never reads the process cwd (it may no longer exist).
        needs_origin = _has_python_spec(extensions)
        loaded = resolve_extensions(
            extensions,
            config=settings,
            allow_python=allow_python_extensions,
            root=Path(root) if root is not None else (Path.cwd() if needs_origin else Path(".")),
            cwd=Path.cwd() if needs_origin else Path("."),
        )
    if loaded.builtin_specs != settings.telemetry_extensions:
        # The effective Config names exactly the loaded builtins (argv specs merged),
        # so domain_for -- hence doc.domain -- sees builtin:domain only when it runs (M24).
        settings = replace(settings, telemetry_extensions=loaded.builtin_specs)
    try:
        chosen = _resolve(format, template, settings.report_templates_dir, root)
        require_context(chosen, CONTEXT_REPORT)
        logger.debug(
            "render: template %s (%s, %s), %d findings, strict=%s",
            safe(chosen.name),
            chosen.origin,
            chosen.type,
            len(result.findings),
            strict,
        )
        check_template(chosen, loaded)
        context = ReportModel.build(
            result,
            settings,
            extensions=loaded,
            strict=strict,
            report_include_run_meta=settings.report_include_run_meta,
            report_schema_version=chosen.schema_version or REPORT_SCHEMA_VERSION,
            show_clean_documents=settings.report_show_clean_documents,
        )
        report = render_template(chosen, context, extensions=loaded, model_kind=CONTEXT_REPORT)
    except TemplateError as exc:
        raise ValueError(str(exc)) from exc
    loaded.check_modules()
    logger.debug("render: %d characters", len(report))
    return report


def render_facts(
    result: FactExtractionResult,
    format: str = DEFAULT_FACTS_TEMPLATE,
    *,
    template: Union[Template, str, os.PathLike[str], None] = None,
    root: Optional[Path] = None,
    templates_dir: Optional[str] = None,
) -> str:
    """Render a fact-extraction result through a ``facts`` template.

    Resolution matches :func:`render`: ``template`` when given (a loaded ``Template``,
    or a trusted invoker file path through the loader's file gate), otherwise
    ``format`` as a template *name* -- never a path -- among the packaged templates and
    then ``templates_dir``. No extension is loaded or accepted.

    :param result: The completed ``extract_facts`` run.
    :param format: Template name, e.g. a packaged ``facts`` template name.
    :param template: A template or template file path; wins over ``format``.
    :param root: The scan root ``templates_dir`` is resolved against.
    :param templates_dir: The configured ``report_templates_dir``, or ``None``.
    :returns: The rendered output.
    :raises ValueError: If the template is unknown, unreadable, invalid, a ``report``
        template (``template <name> is a report template; use it with docsentinel
        scan``), or fails to render; or if the result holds a disposition outside the
        closed set. A ``TemplateError`` is chained as the cause.
    """
    try:
        chosen = _resolve(format, template, templates_dir, root)
        require_context(chosen, CONTEXT_FACTS)
        logger.debug(
            "render facts: template %s (%s, %s), %d facts",
            safe(chosen.name),
            chosen.origin,
            chosen.type,
            len(result.facts),
        )
        context = FactsModel.build(result)
        output = render_template(chosen, context, model_kind=CONTEXT_FACTS)
    except TemplateError as exc:
        raise ValueError(str(exc)) from exc
    logger.debug("render facts: %d characters", len(output))
    return output
