"""Command-line access to the shared scan engine."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional

from docsentinel import deep_support
from docsentinel.baseline import save_baseline
from docsentinel.config import ConfigError, load_config
from docsentinel.detectors.loader import ensure_standard_loaded
from docsentinel.engine import scan
from docsentinel.errors import ExtraNotInstalledError
from docsentinel.models import ScanResult
from docsentinel.reporting import render
from docsentinel.rules import rules_for_profile

TEMPLATE = (
    'profile = "fast"\n'
    'include = ["*.md", "**/*.md"]\n'
    'exclude = [".git", ".venv", "node_modules"]\n'
    "select = []\n"
    "ignore = []\n"
)


def _standard_rule_lines() -> list[str]:
    """Return formatted rule lines for the standard profile, or install guidance if missing."""
    try:
        ensure_standard_loaded()
    except ExtraNotInstalledError:
        missing_msg = ["standard profile: install docsentinel[standard] to enable (DS2xx)"]
        return missing_msg
    registered = rules_for_profile("standard")
    if registered:
        return [f"  {rule.code}: {rule.title}" for rule in registered]
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


def main(argv: Optional[list[str]] = None) -> int:
    """Run the DocSentinel command line interface."""
    parser = argparse.ArgumentParser(prog="docsentinel")
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan", help="Inventory Markdown documents")
    scan_parser.add_argument("root", nargs="?", default=".", help="Directory or file to check")
    scan_parser.add_argument("--config", type=Path)
    scan_parser.add_argument("--profile", choices=("fast", "standard", "deep"))
    scan_parser.add_argument("--select", type=str, default=None)
    scan_parser.add_argument("--ignore", type=str, default=None)
    scan_parser.add_argument("--baseline", type=Path, default=None)
    scan_parser.add_argument("--format", choices=("text", "json", "github"), default="text")
    scan_parser.add_argument("--strict", action="store_true")
    scan_parser.add_argument(
        "--i-understand-deep-is-heuristic",
        action="store_true",
        dest="deep_confirm",
        help="Explicitly confirm execution of heuristic deep profile detectors",
    )
    baseline_parser = commands.add_parser("baseline", help="Record current findings into a baseline file")
    baseline_parser.add_argument("root", nargs="?", default=".", help="Directory or file to check")
    baseline_parser.add_argument("--config", type=Path)
    baseline_parser.add_argument("--output", type=Path)
    baseline_parser.add_argument("--profile", choices=("fast", "standard", "deep"))
    init_parser = commands.add_parser("init", help="Create a starter config")
    init_parser.add_argument("root", nargs="?", default=".")
    commands.add_parser("rules", help="List active detection rules")
    commands.add_parser("doctor", help="Show M0 capabilities")
    args = parser.parse_args(argv)
    if args.command == "init":
        target = Path(args.root) / "doc_sentinel.toml"
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(TEMPLATE)
        except OSError as exc:
            print(f"Cannot create {target}: {exc}", file=sys.stderr)
            return 2
        print(f"Created {target}")
        return 0
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
                        print(f"  {rule.code}: {rule.title}")
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
            print(f"{profile} rules: {len(rules_for_profile(profile))} registered")
        return 0
    if args.command == "baseline":
        try:
            target = Path(args.root).resolve()
            directory = target.parent if target.is_file() else target
            settings = load_config(directory, args.config)
            if args.profile is not None:
                settings = replace(settings, profile=args.profile)
            if args.output is not None:
                output_path = Path(args.output) if Path(args.output).is_absolute() else Path.cwd() / args.output
            elif settings.baseline is not None:
                output_path = (
                    Path(settings.baseline) if Path(settings.baseline).is_absolute() else directory / settings.baseline
                )
            else:
                output_path = directory / ".docsentinel-baseline.json"

            unbaselined_config = replace(settings, baseline=None)
            result = scan(args.root, config=unbaselined_config)
            save_baseline(output_path, result.findings)
        except (ConfigError, ValueError, OSError) as exc:
            print(f"Baseline generation failed: {exc}", file=sys.stderr)
            return 2
        print(f"Saved baseline: {output_path}")
        return 0
    try:
        target = Path(args.root).resolve()
        settings = load_config(target.parent if target.is_file() else target, args.config)
        changes = {}
        if args.profile is not None:
            changes["profile"] = args.profile
        if args.select is not None:
            changes["select"] = tuple(item.strip() for item in args.select.split(",") if item.strip())
        if args.ignore is not None:
            changes["ignore"] = tuple(item.strip() for item in args.ignore.split(",") if item.strip())
        if args.baseline is not None:
            changes["baseline"] = str(args.baseline)
        if getattr(args, "deep_confirm", False):
            changes["deep_confirm"] = True
        if changes:
            settings = replace(settings, **changes)
        result = scan(args.root, config=settings)
    except (ConfigError, ValueError, OSError) as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 2
    print(render(result, args.format))
    return _exit_code(result, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
