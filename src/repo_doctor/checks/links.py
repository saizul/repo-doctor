"""Broken relative links in Markdown files."""

from __future__ import annotations

import posixpath
from urllib.parse import unquote

from repo_doctor.markdown import anchors, links
from repo_doctor.model import Location, Outcome, Severity, check, failed, passed, skipped
from repo_doctor.repo import Repo, matches_any

EXTERNAL_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "ftp://",
    "//",
    "data:",
    "javascript:",
    "irc://",
    "xmpp:",
)


def resolve_link(source: str, target: str) -> tuple[str, str]:
    """Return ``(repo_relative_path, fragment)`` for a relative link inside ``source``."""

    target, _, fragment = target.partition("#")
    target = target.split("?", 1)[0]
    target = unquote(target)
    if not target:
        return source, fragment
    if target.startswith("/"):
        path = posixpath.normpath(target.lstrip("/"))
    else:
        path = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    return path, fragment


@check(
    "RD016",
    "markdown-links",
    "No broken relative links in Markdown",
    Severity.MEDIUM,
    "docs",
    "Links to files or headings that no longer exist frustrate readers and look unmaintained.",
    "Fix or remove the listed links; exclude generated docs with [links] ignore in the config.",
)
def markdown_links(repo: Repo) -> Outcome:
    md_files = [
        p
        for p in repo.files
        if p.lower().endswith((".md", ".markdown")) and not matches_any(p, repo.config.link_ignore)
    ]
    if not md_files:
        return skipped("No Markdown files")
    all_files = set(repo.files)
    dirs = {posixpath.dirname(p) for p in all_files}
    expanded_dirs = set()
    for d in dirs:
        while d:
            expanded_dirs.add(d)
            d = posixpath.dirname(d)
    anchor_cache: dict[str, set[str]] = {}
    broken: list[tuple[str, int, str]] = []
    checked = 0
    for source in md_files:
        for link in links(repo.read_text(source)):
            target = link.target.strip()
            if not target or target.lower().startswith(EXTERNAL_PREFIXES) or "{{" in target or "$" in target:
                continue
            checked += 1
            path, fragment = resolve_link(source, target)
            if path.startswith(".."):
                continue  # points outside the repository (e.g. a monorepo parent); cannot verify
            exists = path in all_files or path in expanded_dirs or path in ("", ".") or repo.exists(path)
            if not exists:
                broken.append((source, link.line, target))
                continue
            if fragment and path.lower().endswith((".md", ".markdown")) and path in all_files:
                if path not in anchor_cache:
                    anchor_cache[path] = anchors(repo.read_text(path))
                if fragment.lower() not in {a.lower() for a in anchor_cache[path]} and not fragment.startswith("L"):
                    broken.append((source, link.line, target))
    if not broken:
        return passed(f"{checked} relative link(s) in {len(md_files)} Markdown file(s) resolve")
    details = [f"{src}:{line} -> {target}" for src, line, target in broken[:50]]
    return failed(
        f"{len(broken)} broken relative link(s)",
        details,
        [Location(src, line) for src, line, _ in broken[:50]],
    )
