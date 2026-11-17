"""Repository hygiene: ignore files, editor config, lockfiles, large files, Docker basics."""

from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath

from repo_doctor.model import Location, Outcome, Severity, check, failed, passed, skipped, warned
from repo_doctor.repo import LANGUAGE_LABELS, Repo

# Patterns a .gitignore should contain per language. Each entry is (label, alternatives);
# any alternative that appears in .gitignore satisfies the entry.
GITIGNORE_EXPECTATIONS: dict[str, list[tuple[str, tuple[str, ...]]]] = {
    "python": [
        ("__pycache__/", ("__pycache__", "*.py[cod]", "*.pyc")),
        (".venv/", (".venv", "venv", "*venv*", ".env*/")),
        ("*.egg-info/", ("*.egg-info", ".eggs", "*.egg")),
    ],
    "javascript": [("node_modules/", ("node_modules",))],
    "typescript": [("node_modules/", ("node_modules",))],
    "php": [("vendor/", ("vendor", "/vendor"))],
    "rust": [("target/", ("target", "/target"))],
    "go": [],
    "docker": [],
}
COMMON_EXPECTATIONS: list[tuple[str, tuple[str, ...]]] = [(".env", (".env", ".env*", "*.env", ".env.local"))]


def gitignore_entries(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def missing_gitignore_patterns(repo: Repo, text: str) -> list[str]:
    entries = [e.strip("/") for e in gitignore_entries(text)]
    missing: list[str] = []
    expectations = list(COMMON_EXPECTATIONS)
    for lang in repo.languages:
        for item in GITIGNORE_EXPECTATIONS.get(lang, []):
            if item not in expectations:
                expectations.append(item)
    for label, alternatives in expectations:
        if not any(_covers(entry, alt.strip("/")) for entry in entries for alt in alternatives):
            missing.append(label)
    return missing


def _covers(entry: str, alternative: str) -> bool:
    entry = entry.lstrip("!").strip("/")
    if entry.startswith("**/"):
        entry = entry[3:]
    return entry == alternative or fnmatch.fnmatch(alternative, entry) or fnmatch.fnmatch(entry, alternative)


@check(
    "RD010",
    "gitignore",
    ".gitignore is present",
    Severity.MEDIUM,
    "hygiene",
    "Without .gitignore, build output, dependencies and local secrets end up in commits.",
    "Add a .gitignore with the patterns for your languages and local files such as .env.",
    fixer="gitignore",
)
def gitignore_present(repo: Repo) -> Outcome:
    if repo.find([".gitignore"]):
        return passed(".gitignore")
    return failed("No .gitignore in the repository root")


@check(
    "RD011",
    "gitignore-languages",
    ".gitignore covers the detected languages",
    Severity.LOW,
    "hygiene",
    "Every ecosystem has folders that must never be committed (node_modules, __pycache__, vendor, target), "
    "and .env files hold local secrets.",
    "Add the missing patterns to .gitignore.",
    fixer="gitignore",
)
def gitignore_languages(repo: Repo) -> Outcome:
    path = repo.find([".gitignore"])
    if not path:
        return failed("No .gitignore to inspect")
    missing = missing_gitignore_patterns(repo, repo.read_text(path))
    langs = ", ".join(LANGUAGE_LABELS[lang] for lang in repo.languages) or "no specific language"
    if missing:
        return failed(f".gitignore is missing: {', '.join(missing)}", [f"Detected: {langs}"], [Location(path)])
    return passed(f".gitignore covers {langs}")


@check(
    "RD012",
    "editorconfig",
    ".editorconfig is present",
    Severity.LOW,
    "hygiene",
    ".editorconfig keeps indentation, line endings and final newlines consistent across editors and contributors.",
    "Add an .editorconfig with charset, line endings, indentation and final newline rules.",
    fixer="editorconfig",
)
def editorconfig(repo: Repo) -> Outcome:
    if repo.find([".editorconfig"]):
        return passed(".editorconfig")
    return failed("No .editorconfig")


LOCKFILES: dict[str, tuple[str, ...]] = {
    "javascript": ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock", "npm-shrinkwrap.json"),
    "php": ("composer.lock",),
    "python": ("poetry.lock", "uv.lock", "Pipfile.lock", "pdm.lock", "pixi.lock", "requirements.lock"),
    "rust": ("Cargo.lock",),
    "go": ("go.sum",),
}


def _expects_lockfile(repo: Repo, lang: str) -> bool:
    if lang == "javascript":
        return bool(repo.find(["package.json"]))
    if lang == "php":
        data = repo.json("composer.json") or {}
        return bool(repo.find(["composer.json"])) and data.get("type", "library") == "project"
    if lang == "python":
        py = repo.toml("pyproject.toml") or {}
        tool = py.get("tool", {})
        uses_manager = any(k in tool for k in ("poetry", "uv", "pdm", "pixi")) or bool(repo.find(["Pipfile"]))
        return uses_manager
    if lang == "rust":
        return bool(repo.find(["Cargo.toml"])) and bool(repo.glob("src/main.rs") or repo.glob("src/bin/*.rs"))
    if lang == "go":
        text = repo.read_text("go.mod") if repo.find(["go.mod"]) else ""
        return bool(re.search(r"^\s*require\b", text, re.MULTILINE))
    return False


@check(
    "RD013",
    "lockfile",
    "Dependency lockfile is committed",
    Severity.MEDIUM,
    "hygiene",
    "Lockfiles make installs reproducible and let dependency bots and audits see the exact versions in use.",
    "Commit the lockfile your package manager writes "
    "(package-lock.json, poetry.lock, uv.lock, Cargo.lock, go.sum, ...).",
)
def lockfile(repo: Repo) -> Outcome:
    relevant = [lang for lang in LOCKFILES if lang in repo.languages and _expects_lockfile(repo, lang)]
    if not relevant:
        return skipped("No application manifest that needs a lockfile")
    missing: list[str] = []
    untracked: list[str] = []
    found: list[str] = []
    for lang in relevant:
        hit = repo.find(LOCKFILES[lang])
        if not hit:
            missing.append(f"{LANGUAGE_LABELS[lang]} ({' / '.join(LOCKFILES[lang][:3])})")
        elif not repo.is_tracked(hit):
            untracked.append(hit)
        else:
            found.append(hit)
    if missing:
        return failed(f"No lockfile for {', '.join(missing)}")
    if untracked:
        return failed(f"Lockfile exists but is not committed: {', '.join(untracked)}")
    return passed(", ".join(found))


@check(
    "RD014",
    "large-files",
    "No large files committed",
    Severity.MEDIUM,
    "hygiene",
    "Large binaries bloat every clone forever, even after deletion. Use Git LFS or release assets instead.",
    "Remove the files from history (git filter-repo) or track them with Git LFS; raise large_file_mb if intended.",
)
def large_files(repo: Repo) -> Outcome:
    limit = int(repo.config.large_file_mb * 1024 * 1024)
    lfs_patterns = _lfs_patterns(repo)
    candidates = sorted(repo.tracked) if repo.tracked is not None else repo.files
    offenders: list[tuple[str, int]] = []
    for rel in candidates:
        size = repo.size(rel)
        if size > limit and not any(
            fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(PurePosixPath(rel).name, p) for p in lfs_patterns
        ):
            offenders.append((rel, size))
    if not offenders:
        return passed(f"No file above {repo.config.large_file_mb:g} MB")
    offenders.sort(key=lambda item: -item[1])
    details = [f"{rel} ({size / 1024 / 1024:.1f} MB)" for rel, size in offenders[:20]]
    return failed(
        f"{len(offenders)} file(s) above {repo.config.large_file_mb:g} MB",
        details,
        [Location(rel) for rel, _ in offenders[:20]],
    )


def _lfs_patterns(repo: Repo) -> list[str]:
    text = repo.read_text(".gitattributes") if repo.find([".gitattributes"]) else ""
    return [line.split()[0] for line in text.splitlines() if "filter=lfs" in line and line.split()]


@check(
    "RD050",
    "dockerignore",
    ".dockerignore next to the Dockerfile",
    Severity.LOW,
    "docker",
    "Without .dockerignore the whole folder, including .git and local secrets, is sent to the build context.",
    "Add a .dockerignore that excludes .git, dependencies, build output and .env files.",
    languages=("docker",),
    fixer="dockerignore",
)
def dockerignore(repo: Repo) -> Outcome:
    dockerfiles = [p for p in repo.files if PurePosixPath(p).name.startswith("Dockerfile")]
    if not dockerfiles:
        return skipped("No Dockerfile")
    if repo.find([".dockerignore"]):
        return passed(".dockerignore")
    return failed("Dockerfile without .dockerignore", locations=[Location(dockerfiles[0])])


_FROM_RE = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(?P<image>\S+)", re.IGNORECASE | re.MULTILINE)


@check(
    "RD051",
    "docker-base-pinned",
    "Dockerfile base images are pinned",
    Severity.LOW,
    "docker",
    "FROM image:latest (or no tag) changes under your feet and makes builds unreproducible.",
    "Use a specific tag such as python:3.12-slim, or pin a digest (image@sha256:...).",
    languages=("docker",),
)
def docker_base_pinned(repo: Repo) -> Outcome:
    dockerfiles = [p for p in repo.files if PurePosixPath(p).name.startswith("Dockerfile")]
    if not dockerfiles:
        return skipped("No Dockerfile")
    problems: list[str] = []
    locations: list[Location] = []
    for rel in dockerfiles:
        text = repo.read_text(rel)
        stages = {m.group(1).lower() for m in re.finditer(r"\bAS\s+(\S+)", text, re.IGNORECASE)}
        for match in _FROM_RE.finditer(text):
            image = match.group("image")
            if image.lower() in stages or image.lower() == "scratch" or "$" in image:
                continue
            name = image.split("@", 1)[0]
            tag = name.rsplit(":", 1)[1] if ":" in name.rsplit("/", 1)[-1] else ""
            if "@" not in image and (not tag or tag == "latest"):
                line = text[: match.start()].count("\n") + 1
                problems.append(f"{rel}:{line} FROM {image}")
                locations.append(Location(rel, line))
    if problems:
        return warned(f"{len(problems)} unpinned base image(s)", problems, locations)
    return passed(f"{len(dockerfiles)} Dockerfile(s) use pinned base images")
