"""Configuration for local, deterministic scans."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_CONFIG_OPTIONS = {"include", "exclude", "profile", "select", "ignore", "baseline"}
_SELECTOR_PATTERN = re.compile(r"DS\d*")


class ConfigError(ValueError):
    """An invalid or unreadable DocSentinel configuration."""


@dataclass(frozen=True)
class Config:
    """Immutable settings for a DocSentinel scan."""

    include: tuple[str, ...] = ("*.md", "**/*.md")
    exclude: tuple[str, ...] = (".git", ".venv", "node_modules")
    profile: str = "fast"
    select: tuple[str, ...] = ()
    ignore: tuple[str, ...] = ()
    baseline: Optional[str] = None


def _load_toml_table(source: Path, *, wrapped: bool) -> dict[str, object]:
    """Load and validate options from a standalone or pyproject TOML table."""
    try:
        with source.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Cannot read {source}: {exc}") from exc

    options: object = data
    if wrapped:
        tool = data.get("tool")
        if not isinstance(tool, dict) or "doc_sentinel" not in tool:
            return {}
        options = tool["doc_sentinel"]
        if not isinstance(options, dict):
            raise ConfigError("Unknown config options: tool.doc_sentinel must be a table")

    unknown = set(options) - _CONFIG_OPTIONS
    if unknown:
        raise ConfigError(f"Unknown config options: {', '.join(sorted(unknown))}")
    return options


def load_config(root: Path, path: Optional[Path] = None) -> Config:
    """Load an explicit config or discover root-level DocSentinel settings."""
    if path is not None:
        source = path
        wrapped = source.name == "pyproject.toml"
    else:
        standalone = root / "doc_sentinel.toml"
        pyproject = root / "pyproject.toml"
        if standalone.exists():
            source = standalone
            wrapped = False
        elif pyproject.exists():
            source = pyproject
            wrapped = True
        else:
            return Config()

    options = _load_toml_table(source, wrapped=wrapped)
    defaults = Config()
    include = options.get("include", list(defaults.include))
    exclude = options.get("exclude", list(defaults.exclude))
    profile = options.get("profile", defaults.profile)
    select = options.get("select", list(defaults.select))
    ignore = options.get("ignore", list(defaults.ignore))
    baseline = options.get("baseline", defaults.baseline)
    for name, value in (("include", include), ("exclude", exclude)):
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ConfigError(f"{name} must be a list of nonempty patterns")
    for name, value in (("select", select), ("ignore", ignore)):
        if not isinstance(value, list) or not all(
            isinstance(item, str) and _SELECTOR_PATTERN.fullmatch(item) for item in value
        ):
            raise ConfigError(f"{name} must be a list of DS rule codes or prefixes")
    if not isinstance(profile, str) or profile not in ("fast", "standard", "deep"):
        raise ConfigError("profile must be fast, standard, or deep")
    if baseline is not None and (not isinstance(baseline, str) or not baseline):
        raise ConfigError("baseline must be a nonempty string")
    return Config(
        include=tuple(include),
        exclude=tuple(exclude),
        profile=profile,
        select=tuple(select),
        ignore=tuple(ignore),
        baseline=baseline,
    )
