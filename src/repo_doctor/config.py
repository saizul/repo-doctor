"""Per-repository configuration from ``.repo-doctor.toml`` or ``[tool.repo-doctor]`` in pyproject.toml.

Example::

    disable = ["RD008", "readme-badges"]
    large_file_mb = 10
    fail_under = 80
    readme_sections = ["install", "usage", "license"]

    [secrets]
    allow_paths = ["tests/fixtures/**"]
    allow_patterns = ["EXAMPLE[A-Z0-9]+"]

    [links]
    ignore = ["docs/generated/**"]
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

CONFIG_FILES = (".repo-doctor.toml", "repo-doctor.toml")
DEFAULT_SECTIONS = ("install", "usage", "license", "contributing")
KNOWN_KEYS = {"disable", "large_file_mb", "fail_under", "readme_sections", "secrets", "links", "remote"}


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    disable: list[str] = field(default_factory=list)
    large_file_mb: float = 5.0
    fail_under: float | None = None
    readme_sections: list[str] = field(default_factory=lambda: list(DEFAULT_SECTIONS))
    secret_allow_paths: list[str] = field(default_factory=list)
    secret_allow_patterns: list[str] = field(default_factory=list)
    link_ignore: list[str] = field(default_factory=list)
    remote: bool = True
    source: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any], source: str = "") -> Config:
        unknown = set(data) - KNOWN_KEYS
        if unknown:
            raise ConfigError(f"{source}: unknown keys {', '.join(sorted(unknown))}")
        cfg = cls(source=source)
        if "disable" in data:
            cfg.disable = _str_list(data["disable"], "disable", source)
        if "large_file_mb" in data:
            value = data["large_file_mb"]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
                raise ConfigError(f"{source}: large_file_mb must be a positive number")
            cfg.large_file_mb = float(value)
        if "fail_under" in data:
            value = data["fail_under"]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 100:
                raise ConfigError(f"{source}: fail_under must be between 0 and 100")
            cfg.fail_under = float(value)
        if "readme_sections" in data:
            sections = _str_list(data["readme_sections"], "readme_sections", source)
            bad = [s for s in sections if s not in DEFAULT_SECTIONS]
            if bad:
                raise ConfigError(f"{source}: unknown readme_sections {bad} (allowed: {', '.join(DEFAULT_SECTIONS)})")
            cfg.readme_sections = sections
        secrets = data.get("secrets", {})
        if not isinstance(secrets, dict):
            raise ConfigError(f"{source}: [secrets] must be a table")
        cfg.secret_allow_paths = _str_list(secrets.get("allow_paths", []), "secrets.allow_paths", source)
        cfg.secret_allow_patterns = _str_list(secrets.get("allow_patterns", []), "secrets.allow_patterns", source)
        links = data.get("links", {})
        if not isinstance(links, dict):
            raise ConfigError(f"{source}: [links] must be a table")
        cfg.link_ignore = _str_list(links.get("ignore", []), "links.ignore", source)
        if "remote" in data:
            if not isinstance(data["remote"], bool):
                raise ConfigError(f"{source}: remote must be true or false")
            cfg.remote = data["remote"]
        return cfg


def _str_list(value: Any, key: str, source: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{source}: {key} must be a list of strings")
    return list(value)


def load_config(root: Path) -> Config:
    for name in CONFIG_FILES:
        path = root / name
        if path.is_file():
            return Config.from_dict(_read(path), name)
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = _read(pyproject)
        except ConfigError:
            return Config()
        section = data.get("tool", {}).get("repo-doctor")
        if isinstance(section, dict):
            return Config.from_dict(section, "pyproject.toml [tool.repo-doctor]")
    return Config()


def _read(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path.name} is not valid TOML: {exc}") from exc
