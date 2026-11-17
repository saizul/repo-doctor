"""Repository access: file index, Git metadata and language detection."""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import Any

from repo_doctor.config import Config, load_config

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".tox",
    ".nox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "vendor",
    "target",
    "dist",
    "build",
    ".next",
    ".cache",
    ".idea",
    ".vscode",
}

LANGUAGES = ("python", "javascript", "typescript", "php", "go", "rust", "docker")

_MARKERS: dict[str, tuple[str, ...]] = {
    "python": ("pyproject.toml", "setup.py", "setup.cfg", "Pipfile", "requirements.txt"),
    "javascript": ("package.json",),
    "typescript": ("tsconfig.json",),
    "php": ("composer.json",),
    "go": ("go.mod",),
    "rust": ("Cargo.toml",),
    "docker": ("Dockerfile", "compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"),
}
_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "javascript": (".js", ".mjs", ".cjs", ".jsx"),
    "typescript": (".ts", ".tsx", ".mts", ".cts"),
    "php": (".php",),
    "go": (".go",),
    "rust": (".rs",),
}
LANGUAGE_LABELS = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "php": "PHP",
    "go": "Go",
    "rust": "Rust",
    "docker": "Docker",
}


class Repo:
    """A checked-out repository (Git or a plain folder)."""

    def __init__(self, root: str | os.PathLike[str], config: Config | None = None) -> None:
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise NotADirectoryError(f"{self.root} is not a directory")
        self.config = config if config is not None else load_config(self.root)
        self._cache: dict[str, Any] = {}

    # ----------------------------------------------------------------- git
    @cached_property
    def git(self) -> str | None:
        return shutil.which("git")

    def _git(self, *args: str) -> str | None:
        if not self.git:
            return None
        try:
            proc = subprocess.run(
                [self.git, "-C", str(self.root), *args],
                capture_output=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0:
            return None
        return proc.stdout.decode("utf-8", errors="replace")

    @cached_property
    def is_git(self) -> bool:
        if not (self.root / ".git").exists():
            return False
        out = self._git("rev-parse", "--show-toplevel")
        return out is not None and Path(out.strip()).resolve() == self.root

    @cached_property
    def tracked(self) -> set[str] | None:
        """Files in the Git index, or ``None`` when this is not a Git repository."""

        if not self.is_git:
            return None
        out = self._git("ls-files", "-z", "--cached")
        if out is None:
            return None
        return {p for p in out.split("\0") if p}

    @cached_property
    def files(self) -> list[str]:
        """Repository files as POSIX paths: tracked plus untracked-but-not-ignored, or a filtered walk."""

        if self.is_git:
            out = self._git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
            if out is not None:
                return sorted({p for p in out.split("\0") if p and (self.root / p).is_file()})
        found: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            rel_dir = Path(dirpath).relative_to(self.root)
            for name in sorted(filenames):
                found.append((rel_dir / name).as_posix() if str(rel_dir) != "." else name)
        return found

    @cached_property
    def _lower_index(self) -> dict[str, str]:
        return {p.lower(): p for p in self.files}

    def is_tracked(self, rel: str) -> bool:
        if self.tracked is None:
            return (self.root / rel).is_file()
        return rel in self.tracked

    @cached_property
    def remote_url(self) -> str | None:
        out = self._git("config", "--get", "remote.origin.url")
        return out.strip() if out else None

    @cached_property
    def github_slug(self) -> tuple[str, str] | None:
        return parse_github_slug(self.remote_url or "")

    @cached_property
    def default_branch(self) -> str | None:
        out = self._git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        if out and "/" in out:
            return out.strip().split("/", 1)[1]
        return None

    # --------------------------------------------------------------- files
    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def find(self, candidates: tuple[str, ...] | list[str]) -> str | None:
        """Return the first existing candidate path, matched case-insensitively."""

        for cand in candidates:
            hit = self._lower_index.get(cand.lower())
            if hit:
                return hit
            if (self.root / cand).is_file():
                return cand
        return None

    def find_doc(self, stems: tuple[str, ...], dirs: tuple[str, ...] = ("", ".github", "docs")) -> str | None:
        exts = ("", ".md", ".markdown", ".rst", ".txt", ".adoc")
        candidates = [f"{d}/{s}{e}" if d else f"{s}{e}" for d in dirs for s in stems for e in exts]
        return self.find(candidates)

    def glob(self, pattern: str) -> list[str]:
        return [p for p in self.files if fnmatch.fnmatch(p, pattern)]

    def read_text(self, rel: str, limit: int = 2_000_000) -> str:
        path = self.root / rel
        try:
            if path.stat().st_size > limit:
                return ""
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def size(self, rel: str) -> int:
        try:
            return (self.root / rel).stat().st_size
        except OSError:
            return 0

    # ------------------------------------------------------------ manifests
    def toml(self, rel: str) -> dict[str, Any] | None:
        key = f"toml:{rel}"
        if key not in self._cache:
            try:
                with (self.root / rel).open("rb") as fh:
                    self._cache[key] = tomllib.load(fh)
            except (OSError, tomllib.TOMLDecodeError):
                self._cache[key] = None
        return self._cache[key]

    def json(self, rel: str) -> dict[str, Any] | None:
        key = f"json:{rel}"
        if key not in self._cache:
            try:
                data = json.loads((self.root / rel).read_text(encoding="utf-8"))
                self._cache[key] = data if isinstance(data, dict) else None
            except (OSError, ValueError):
                self._cache[key] = None
        return self._cache[key]

    # ------------------------------------------------------------ languages
    @cached_property
    def language_stats(self) -> dict[str, int]:
        """Evidence per language: marker files count 50, each source file counts 1."""

        stats: Counter[str] = Counter()
        for rel in self.files:
            name = PurePosixPath(rel).name
            depth = rel.count("/")
            for lang, markers in _MARKERS.items():
                if depth <= 1 and (name in markers or (lang == "python" and re.match(r"requirements.*\.txt$", name))):
                    stats[lang] += 50
                if lang == "docker" and depth <= 2 and (name.startswith("Dockerfile") or name.endswith(".dockerfile")):
                    stats[lang] += 50
            suffix = PurePosixPath(rel).suffix.lower()
            for lang, exts in _EXTENSIONS.items():
                if suffix in exts:
                    stats[lang] += 1
        return dict(stats.most_common())

    @cached_property
    def languages(self) -> list[str]:
        """Detected languages, strongest first. TypeScript implies the JavaScript tooling checks."""

        langs = [lang for lang, score in self.language_stats.items() if score >= 3]
        if "typescript" in langs and "javascript" not in langs and self.find(["package.json"]):
            langs.append("javascript")
        return langs

    def has_language(self, *names: str) -> bool:
        return any(n in self.languages for n in names)

    # ------------------------------------------------------------- metadata
    @cached_property
    def project_name(self) -> str:
        py = self.toml("pyproject.toml") or {}
        name = py.get("project", {}).get("name") or py.get("tool", {}).get("poetry", {}).get("name")
        if not name:
            name = (self.json("package.json") or {}).get("name")
        if not name:
            name = (self.json("composer.json") or {}).get("name")
        if not name:
            name = (self.toml("Cargo.toml") or {}).get("package", {}).get("name")
        if not name and self.github_slug:
            name = self.github_slug[1]
        return str(name or self.root.name)

    @cached_property
    def author_name(self) -> str | None:
        out = self._git("config", "--get", "user.name")
        if out and out.strip():
            return out.strip()
        py = self.toml("pyproject.toml") or {}
        authors = py.get("project", {}).get("authors") or []
        if authors and isinstance(authors[0], dict) and authors[0].get("name"):
            return str(authors[0]["name"])
        author = (self.json("package.json") or {}).get("author")
        if isinstance(author, dict):
            author = author.get("name")
        if isinstance(author, str) and author.strip():
            return re.sub(r"\s*[<(].*$", "", author).strip() or None
        return None


_GITHUB_RE = re.compile(r"github\.com[:/](?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def parse_github_slug(url: str) -> tuple[str, str] | None:
    match = _GITHUB_RE.search(url.strip())
    if not match:
        return None
    return match.group("owner"), match.group("name")


def matches_any(path: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False
