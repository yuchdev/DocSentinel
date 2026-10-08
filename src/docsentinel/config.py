"""Configuration for local, deterministic scans."""

from dataclasses import dataclass
from pathlib import Path
import tomllib


class ConfigError(ValueError):
    """An invalid or unreadable DocSentinel configuration."""


@dataclass(frozen=True)
class Config:
    include: tuple[str, ...] = ("*.md", "**/*.md")
    exclude: tuple[str, ...] = (".git", ".venv", "node_modules")
    profile: str = "fast"


def load_config(root: Path, path: Path | None = None) -> Config:
    """Load docsentinel.toml from root, or an explicitly supplied config file."""
    source = path if path is not None else root / "docsentinel.toml"
    if not source.exists() and path is None:
        return Config()
    try:
        with source.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Cannot read {source}: {exc}") from exc
    if set(data) != {"docsentinel"} or not isinstance(data["docsentinel"], dict):
        raise ConfigError("Config must contain only a [docsentinel] table")
    options = data["docsentinel"]
    unknown = set(options) - {"include", "exclude", "profile"}
    if unknown:
        raise ConfigError(f"Unknown config options: {', '.join(sorted(unknown))}")
    defaults = Config()
    include = options.get("include", list(defaults.include))
    exclude = options.get("exclude", list(defaults.exclude))
    profile = options.get("profile", defaults.profile)
    for name, value in (("include", include), ("exclude", exclude)):
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item for item in value
        ):
            raise ConfigError(f"{name} must be a list of nonempty patterns")
    if profile not in ("fast", "standard", "deep"):
        raise ConfigError("profile must be fast, standard, or deep")
    return Config(tuple(include), tuple(exclude), profile)
