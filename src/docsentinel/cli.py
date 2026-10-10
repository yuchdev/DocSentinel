"""Command-line access to the shared scan engine."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from docsentinel.baseline import save_baseline
from docsentinel.config import Config, ConfigError, load_config
from docsentinel.engine import scan
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


def _exit_code(result: ScanResult, *, strict: bool = False) -> int:
    """Return the exit code for a scan result.

    Returns 1 if strict mode is enabled and there are any findings, or if any finding has
    severity == "error". Otherwise, returns 0. Any other severity (such as "warning")
    does not cause a failure by default.
    """
    if strict:
        return 1 if result.findings else 0
    return 1 if any(finding.severity == "error" for finding in result.findings) else 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="docsentinel")
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan", help="Inventory Markdown documents")
    scan_parser.add_argument("root", nargs="?", default=".", help="Directory or file to check")
    scan_parser.add_argument("--config", type=Path)
    scan_parser.add_argument("--profile", choices=("fast", "standard", "deep"))
    scan_parser.add_argument("--select", type=str, default=None)
    scan_parser.add_argument("--ignore", type=str, default=None)
    scan_parser.add_argument("--format", choices=("text", "json", "github"), default="text")
    scan_parser.add_argument("--strict", action="store_true")
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
            registered = rules_for_profile(profile)
            if registered:
                for rule in registered:
                    print(f"  {rule.code}: {rule.title}")
            else:
                print("  (none registered)")
        return 0
    if args.command == "doctor":
        print("Inventory: available")
        for profile in ("fast", "standard", "deep"):
            print(f"{profile} rules: {len(rules_for_profile(profile))} registered")
        return 0
    if args.command == "baseline":
        try:
            target = Path(args.root).resolve()
            directory = target.parent if target.is_file() else target
            settings = load_config(directory, args.config)
            if args.profile is not None:
                settings = Config(
                    include=settings.include,
                    exclude=settings.exclude,
                    profile=args.profile,
                    select=settings.select,
                    ignore=settings.ignore,
                    baseline=settings.baseline,
                )
            if args.output is not None:
                output_path = Path(args.output) if Path(args.output).is_absolute() else Path.cwd() / args.output
            elif settings.baseline is not None:
                output_path = (
                    Path(settings.baseline) if Path(settings.baseline).is_absolute() else directory / settings.baseline
                )
            else:
                output_path = directory / ".docsentinel-baseline.json"

            unbaselined_config = Config(
                include=settings.include,
                exclude=settings.exclude,
                profile=settings.profile,
                select=settings.select,
                ignore=settings.ignore,
                baseline=None,
            )
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
        if args.profile is not None or args.select is not None or args.ignore is not None:
            settings = Config(
                include=settings.include,
                exclude=settings.exclude,
                profile=args.profile if args.profile is not None else settings.profile,
                select=(
                    tuple(item.strip() for item in args.select.split(",") if item.strip())
                    if args.select is not None
                    else settings.select
                ),
                ignore=(
                    tuple(item.strip() for item in args.ignore.split(",") if item.strip())
                    if args.ignore is not None
                    else settings.ignore
                ),
                baseline=settings.baseline,
            )
        result = scan(args.root, config=settings)
    except (ConfigError, ValueError, OSError) as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 2
    print(render(result, args.format))
    return _exit_code(result, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
