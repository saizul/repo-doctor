"""Continuous integration, issue and pull request templates, dependency updates."""

from __future__ import annotations

from repo_doctor.model import Outcome, Severity, check, failed, passed, warned
from repo_doctor.repo import Repo

CI_FILES = (
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "azure-pipelines.yml",
    "Jenkinsfile",
    ".travis.yml",
    "bitbucket-pipelines.yml",
    ".drone.yml",
    ".woodpecker.yml",
    "appveyor.yml",
)


def workflow_files(repo: Repo) -> list[str]:
    return [p for p in repo.files if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]


@check(
    "RD020",
    "ci",
    "Continuous integration is configured",
    Severity.HIGH,
    "ci",
    "CI runs the tests on every push and pull request, so contributors and maintainers see breakage before merging.",
    "Add a workflow in .github/workflows/ that runs lint and tests on push and pull_request.",
    fixer="ci",
)
def ci_present(repo: Repo) -> Outcome:
    workflows = workflow_files(repo)
    others = [f for f in CI_FILES if repo.find([f])] + [p for p in repo.files if p.startswith(".woodpecker/")][:1]
    if workflows or others:
        found = workflows + others
        details = found[:10]
        if workflows and not any(_runs_on_pull_request(repo, w) for w in workflows):
            return warned("GitHub workflows exist but none runs on pull_request", details)
        return passed(f"{len(found)} CI configuration file(s)", details)
    return failed("No CI configuration (.github/workflows, GitLab CI, CircleCI, ...)")


def _runs_on_pull_request(repo: Repo, rel: str) -> bool:
    text = repo.read_text(rel)
    return "pull_request" in text or "merge_group" in text


@check(
    "RD021",
    "issue-templates",
    "Issue templates",
    Severity.LOW,
    "community",
    "Issue forms ask reporters for versions, steps to reproduce and expected behaviour, which saves maintainers time.",
    "Add issue forms such as .github/ISSUE_TEMPLATE/bug_report.yml and feature_request.yml.",
    fixer="issue-templates",
)
def issue_templates(repo: Repo) -> Outcome:
    templates = [
        p
        for p in repo.files
        if p.lower().startswith((".github/issue_template/", "docs/issue_template/"))
        and p.lower().endswith((".md", ".yml", ".yaml"))
        and not p.lower().endswith("config.yml")
    ]
    single = repo.find([".github/ISSUE_TEMPLATE.md", "ISSUE_TEMPLATE.md", "docs/ISSUE_TEMPLATE.md"])
    if templates:
        return passed(f"{len(templates)} issue template(s)", templates[:10])
    if single:
        return passed(single)
    return failed("No issue templates in .github/ISSUE_TEMPLATE/")


@check(
    "RD022",
    "pr-template",
    "Pull request template",
    Severity.LOW,
    "community",
    "A pull request template reminds contributors to describe the change, link issues and run the tests.",
    "Add .github/pull_request_template.md with a short checklist.",
    fixer="pr-template",
)
def pr_template(repo: Repo) -> Outcome:
    hit = repo.find(
        [
            ".github/pull_request_template.md",
            ".github/PULL_REQUEST_TEMPLATE.md",
            "pull_request_template.md",
            "PULL_REQUEST_TEMPLATE.md",
            "docs/pull_request_template.md",
        ]
    )
    if hit:
        return passed(hit)
    multiple = [p for p in repo.files if p.lower().startswith(".github/pull_request_template/")]
    if multiple:
        return passed(f"{len(multiple)} pull request template(s)")
    return failed("No pull request template")


UPDATE_CONFIGS = (
    ".github/dependabot.yml",
    ".github/dependabot.yaml",
    "renovate.json",
    "renovate.json5",
    ".renovaterc",
    ".renovaterc.json",
    ".renovaterc.json5",
    ".github/renovate.json",
    ".github/renovate.json5",
    ".gitlab/renovate.json",
)


@check(
    "RD023",
    "dependency-updates",
    "Automated dependency updates (Dependabot or Renovate)",
    Severity.MEDIUM,
    "security",
    "Bots that open pull requests for outdated or vulnerable dependencies keep the project secure with little effort.",
    "Add .github/dependabot.yml for your ecosystems, or a renovate.json.",
    fixer="dependabot",
)
def dependency_updates(repo: Repo) -> Outcome:
    hit = repo.find(UPDATE_CONFIGS)
    if hit:
        return passed(hit)
    package = repo.json("package.json") or {}
    if "renovate" in package:
        return passed("renovate config in package.json")
    return failed("No Dependabot or Renovate configuration")
