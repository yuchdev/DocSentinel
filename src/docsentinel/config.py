"""Configuration for local, deterministic scans."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
    "deep_confirm",
}
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
    max_grade_level: float = 14.0
    duplicate_similarity: float = 0.85
    min_information_score: float = 0.15
    docsig_paths: tuple[str, ...] = ("src",)
    deep_confirm: bool = False


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
    max_grade_level = options.get("max_grade_level", defaults.max_grade_level)
    duplicate_similarity = options.get("duplicate_similarity", defaults.duplicate_similarity)
    min_information_score = options.get("min_information_score", defaults.min_information_score)
    docsig_paths = options.get("docsig_paths", list(defaults.docsig_paths))
    deep_confirm = options.get("deep_confirm", defaults.deep_confirm)
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
    if not isinstance(max_grade_level, (int, float)) or isinstance(max_grade_level, bool) or max_grade_level <= 0:
        raise ConfigError("max_grade_level must be a positive number")
    if (
        not isinstance(duplicate_similarity, (int, float))
        or isinstance(duplicate_similarity, bool)
        or not (0.0 <= float(duplicate_similarity) <= 1.0)
    ):
        raise ConfigError("duplicate_similarity must be a number between 0 and 1")
    if (
        not isinstance(min_information_score, (int, float))
        or isinstance(min_information_score, bool)
        or not (0.0 <= float(min_information_score) <= 1.0)
    ):
        raise ConfigError("min_information_score must be a number between 0 and 1")
    if not isinstance(deep_confirm, bool):
        raise ConfigError("deep_confirm must be true or false")
    return Config(
        include=tuple(include),
        exclude=tuple(exclude),
        profile=profile,
        select=tuple(select),
        ignore=tuple(ignore),
        baseline=baseline,
        max_grade_level=float(max_grade_level),
        duplicate_similarity=float(duplicate_similarity),
        min_information_score=float(min_information_score),
        docsig_paths=tuple(docsig_paths),
        deep_confirm=deep_confirm,
    )
