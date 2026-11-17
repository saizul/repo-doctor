"""Package manifest metadata: description, license, repository URL and keywords."""

from __future__ import annotations

from typing import Any

from repo_doctor.model import Location, Outcome, Severity, check, failed, passed, skipped, warned
from repo_doctor.repo import Repo


def _pyproject(data: dict[str, Any]) -> list[str]:
    project = data.get("project")
    if isinstance(project, dict):
        missing = []
        if not project.get("description"):
            missing.append("description")
        if not project.get("license") and not any("License ::" in c for c in project.get("classifiers", [])):
            missing.append("license")
        urls = {k.lower(): v for k, v in (project.get("urls") or {}).items()}
        if not any(k in urls for k in ("repository", "source", "source code", "homepage", "code")):
            missing.append("urls.Repository")
        if not project.get("keywords"):
            missing.append("keywords")
        return missing
    poetry = data.get("tool", {}).get("poetry")
    if isinstance(poetry, dict):
        return [
            key
            for key, ok in (
                ("description", poetry.get("description")),
                ("license", poetry.get("license")),
                ("repository", poetry.get("repository") or poetry.get("homepage")),
                ("keywords", poetry.get("keywords")),
            )
            if not ok
        ]
    return ["[project] table"]


def _package_json(data: dict[str, Any]) -> list[str]:
    if data.get("private") is True:
        return []
    missing = [k for k in ("description", "license", "keywords") if not data.get(k)]
    if not data.get("repository"):
        missing.insert(2, "repository")
    return missing


def _composer_json(data: dict[str, Any]) -> list[str]:
    missing = [k for k in ("description", "license", "keywords") if not data.get(k)]
    support = data.get("support") or {}
    if not (data.get("homepage") or (isinstance(support, dict) and support.get("source"))):
        missing.insert(2, "homepage or support.source")
    return missing


def _cargo_toml(data: dict[str, Any]) -> list[str]:
    package = data.get("package")
    if not isinstance(package, dict):
        return []  # workspace root
    if package.get("publish") is False:
        return []
    missing = [k for k in ("description", "repository", "keywords") if not package.get(k)]
    if not package.get("license") and not package.get("license-file"):
        missing.insert(1, "license")
    return missing


MANIFESTS = (
    ("pyproject.toml", "toml", _pyproject),
    ("package.json", "json", _package_json),
    ("composer.json", "json", _composer_json),
    ("Cargo.toml", "toml", _cargo_toml),
)


@check(
    "RD030",
    "package-metadata",
    "Package metadata is complete",
    Severity.MEDIUM,
    "metadata",
    "Registries (PyPI, npm, Packagist, crates.io) show description, license, repository link and keywords; "
    "they drive search ranking and trust.",
    "Fill in description, license, repository URL and keywords in each package manifest.",
)
def package_metadata(repo: Repo) -> Outcome:
    present = [(name, kind, func) for name, kind, func in MANIFESTS if repo.find([name])]
    if not present:
        return skipped("No pyproject.toml, package.json, composer.json or Cargo.toml in the root")
    problems: list[str] = []
    unreadable: list[str] = []
    checked: list[str] = []
    for name, kind, func in present:
        data = repo.toml(name) if kind == "toml" else repo.json(name)
        if data is None:
            unreadable.append(name)
            continue
        checked.append(name)
        missing = func(data)
        if missing:
            problems.append(f"{name}: missing {', '.join(missing)}")
    if unreadable:
        return failed(f"Cannot parse {', '.join(unreadable)}", problems, [Location(n) for n in unreadable])
    if not problems:
        return passed(f"{', '.join(checked)} complete")
    locations = [Location(p.split(":", 1)[0]) for p in problems]
    total_missing = sum(p.count(",") + 1 for p in problems)
    if total_missing == 1:
        return warned(problems[0], problems, locations)
    return failed(f"Incomplete metadata in {len(problems)} manifest(s)", problems, locations)
