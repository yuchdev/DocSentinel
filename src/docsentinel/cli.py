"""Command-line access to the shared scan engine."""

import argparse
from pathlib import Path
import sys

from docsentinel.config import Config, ConfigError, load_config
from docsentinel.engine import scan
from docsentinel.reporting import render

TEMPLATE = '[docsentinel]\nprofile = "fast"\ninclude = ["*.md", "**/*.md"]\nexclude = [".git", ".venv", "node_modules"]\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docsentinel")
    commands = parser.add_subparsers(dest="command", required=True)
    scan_parser = commands.add_parser("scan", help="Inventory Markdown documents")
    scan_parser.add_argument("root", nargs="?", default=".", help="Directory or file to check")
    scan_parser.add_argument("--config", type=Path)
    scan_parser.add_argument("--profile", choices=("fast", "standard", "deep"))
    scan_parser.add_argument("--format", choices=("text", "json"), default="text")
    init_parser = commands.add_parser("init", help="Create a starter config")
    init_parser.add_argument("root", nargs="?", default=".")
    commands.add_parser("rules", help="List active detection rules")
    commands.add_parser("doctor", help="Show M0 capabilities")
    args = parser.parse_args(argv)
    if args.command == "init":
        target = Path(args.root) / "docsentinel.toml"
        try:
            with target.open("x", encoding="utf-8") as stream:
                stream.write(TEMPLATE)
        except OSError as exc:
            print(f"Cannot create {target}: {exc}", file=sys.stderr)
            return 2
        print(f"Created {target}")
        return 0
    if args.command == "rules":
        print("Enabled rules: []\nDetection rules are not implemented in M0.")
        return 0
    if args.command == "doctor":
        print("Inventory: available\nDetection rules: not implemented (future)")
        return 0
    try:
        target = Path(args.root).resolve()
        settings = load_config(target.parent if target.is_file() else target, args.config)
        if args.profile:
            settings = Config(settings.include, settings.exclude, args.profile)
        result = scan(args.root, config=settings)
    except (ConfigError, ValueError, OSError) as exc:
        print(f"Scan failed: {exc}", file=sys.stderr)
        return 2
    print(render(result, args.format))
    return 1 if result.findings else 0


if __name__ == "__main__":
    sys.exit(main())
