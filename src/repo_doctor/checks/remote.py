"""Optional checks against the GitHub API (only when GITHUB_TOKEN or GH_TOKEN is set)."""

from __future__ import annotations

from typing import Any

from repo_doctor.github import GitHubClient, GitHubError, token_from_env
from repo_doctor.model import Outcome, Severity, check, failed, passed, skipped, warned
from repo_doctor.repo import Repo

_SENTINEL = object()


def _context(repo: Repo) -> tuple[GitHubClient, str, str, dict[str, Any]] | Outcome:
    """Shared, cached API context; returns an Outcome (skip) when remote checks cannot run."""

    cached = repo._cache.get("github", _SENTINEL)
    if cached is not _SENTINEL:
        return cached
    result: Any
    token = token_from_env()
    if not repo.config.remote:
        result = skipped("Remote checks disabled")
    elif not token:
        result = skipped("Set GITHUB_TOKEN to enable GitHub checks")
    elif not repo.github_slug:
        result = skipped("origin is not a GitHub repository")
    else:
        client = repo._cache.get("github_client") or GitHubClient(token)
        owner, name = repo.github_slug
        try:
            data = client.repository(owner, name)
            result = (client, owner, name, data)
        except GitHubError as exc:
            result = skipped(f"GitHub API unavailable ({exc})")
    repo._cache["github"] = result
    return result


@check(
    "RD040",
    "github-description",
    "GitHub repository has a description",
    Severity.MEDIUM,
    "metadata",
    "The description is shown in search results, on profile pages and in link previews.",
    "Set it under the repository's About settings or with: gh repo edit --description '...'",
    remote=True,
)
def github_description(repo: Repo) -> Outcome:
    ctx = _context(repo)
    if isinstance(ctx, Outcome):
        return ctx
    description = (ctx[3].get("description") or "").strip()
    if not description:
        return failed("No repository description")
    if len(description) < 20:
        return warned(f"Description is very short: {description!r}")
    return passed(description)


@check(
    "RD041",
    "github-topics",
    "GitHub repository has topics",
    Severity.LOW,
    "metadata",
    "Topics make the project discoverable on github.com/topics and in GitHub search.",
    "Add 5-10 topics: gh repo edit --add-topic python --add-topic cli",
    remote=True,
)
def github_topics(repo: Repo) -> Outcome:
    ctx = _context(repo)
    if isinstance(ctx, Outcome):
        return ctx
    topics = ctx[3].get("topics") or []
    if not topics:
        return failed("No topics")
    if len(topics) < 3:
        return warned(f"Only {len(topics)} topic(s): {', '.join(topics)}")
    return passed(", ".join(topics))


@check(
    "RD042",
    "github-homepage",
    "GitHub repository has a homepage URL",
    Severity.LOW,
    "metadata",
    "A homepage link (docs site, package page) gives visitors a next step right from the About box.",
    "Set it with: gh repo edit --homepage https://...",
    remote=True,
)
def github_homepage(repo: Repo) -> Outcome:
    ctx = _context(repo)
    if isinstance(ctx, Outcome):
        return ctx
    homepage = (ctx[3].get("homepage") or "").strip()
    return passed(homepage) if homepage else failed("No homepage URL")


@check(
    "RD043",
    "branch-protection",
    "Default branch is protected",
    Severity.MEDIUM,
    "security",
    "Protection (or a ruleset) stops force-pushes and direct pushes and can require reviews and passing CI.",
    "Add a branch ruleset for the default branch: require pull requests and status checks, block force pushes.",
    remote=True,
)
def branch_protection(repo: Repo) -> Outcome:
    ctx = _context(repo)
    if isinstance(ctx, Outcome):
        return ctx
    client, owner, name, data = ctx
    branch = data.get("default_branch") or repo.default_branch or "main"
    try:
        rules = client.branch_rules(owner, name, branch)
    except GitHubError:
        rules = []
    if rules:
        types = sorted({r.get("type", "?") for r in rules})
        return passed(f"{branch} is covered by rulesets: {', '.join(types)}")
    try:
        protection = client.branch_protection(owner, name, branch)
    except GitHubError as exc:
        if exc.status in (401, 403):
            return skipped(f"Token cannot read branch protection for {branch} (needs admin access)")
        return skipped(f"Could not read branch protection ({exc})")
    if protection is None:
        return failed(f"{branch} has no branch protection or ruleset")
    return passed(f"{branch} is protected")
