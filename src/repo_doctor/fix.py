"""Scaffold missing files from bundled templates.

Fixers never overwrite an existing file unless ``force`` is set. The only
in-place change is appending missing patterns to an existing ``.gitignore``,
which never removes anything.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources

from repo_doctor.checks.ci import workflow_files
from repo_doctor.checks.hygiene import missing_gitignore_patterns
from repo_doctor.engine import run_checks
from repo_doctor.model import Status, all_checks, resolve
from repo_doctor.repo import Repo

LICENSES = {"MIT": "MIT.txt", "Apache-2.0": "Apache-2.0.txt"}

GITIGNORE_BLOCKS: dict[str, list[str]] = {
    "common": [".env", ".env.local", "*.log", ".DS_Store", ".idea/", ".vscode/"],
    "python": [
        "__pycache__/",
        "*.py[cod]",
        "*.egg-info/",
        ".eggs/",
        "build/",
        "dist/",
        ".venv/",
        "venv/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".mypy_cache/",
        ".coverage",
        "htmlcov/",
    ],
    "javascript": [
        "node_modules/",
        "dist/",
        "coverage/",
        ".next/",
        "npm-debug.log*",
        "yarn-error.log*",
        "*.tsbuildinfo",
    ],
    "php": ["vendor/", ".phpunit.result.cache", ".phpunit.cache/"],
    "go": ["/bin/", "*.exe", "*.test", "*.out", "coverage.*"],
    "rust": ["target/"],
}
GITIGNORE_TITLES = {
    "common": "Local environment and editors",
    "python": "Python",
    "javascript": "Node.js / TypeScript",
    "php": "PHP / Composer",
    "go": "Go",
    "rust": "Rust",
}
DEPENDABOT_ECOSYSTEMS = {
    "python": "pip",
    "javascript": "npm",
    "php": "composer",
    "go": "gomod",
    "rust": "cargo",
    "docker": "docker",
}
DEV_SETUP = {
    "python": '```bash\npython -m venv .venv\n. .venv/bin/activate\npip install -e ".[dev]"\npytest\n```',
    "javascript": "```bash\nnpm ci\nnpm test\n```",
    "go": "```bash\ngo build ./...\ngo test ./...\n```",
    "rust": "```bash\ncargo build\ncargo test\n```",
    "php": "```bash\ncomposer install\ncomposer test\n```",
}
CI_TEMPLATES = {
    "python": "python.yml",
    "javascript": "javascript.yml",
    "go": "go.yml",
    "rust": "rust.yml",
    "php": "php.yml",
}


class FixError(ValueError):
    pass


@dataclass
class FixContext:
    repo: Repo
    license_id: str = "MIT"
    author: str | None = None
    email: str | None = None
    year: int = field(default_factory=lambda: _dt.date.today().year)

    @property
    def project(self) -> str:
        return self.repo.project_name

    @property
    def author_name(self) -> str:
        return self.author or self.repo.author_name or f"The {self.project} contributors"

    @property
    def repo_url(self) -> str | None:
        slug = self.repo.github_slug
        return f"https://github.com/{slug[0]}/{slug[1]}" if slug else None

    @property
    def security_url(self) -> str | None:
        return f"{self.repo_url}/security/advisories/new" if self.repo_url else None

    @property
    def security_contact(self) -> str:
        if self.email:
            return f"e-mail to <{self.email}>"
        if self.security_url:
            return f"[GitHub private vulnerability reporting]({self.security_url})"
        return "e-mail to the maintainers (see their profiles)"

    @property
    def coc_contact(self) -> str:
        if self.email:
            return f"<{self.email}>"
        if self.repo_url:
            return f"the e-mail address on the maintainers' GitHub profiles ({self.repo_url})"
        return "the e-mail address of the maintainers"

    @property
    def branch(self) -> str:
        return self.repo.default_branch or "main"

    def render(self, text: str) -> str:
        tokens = {
            "@@PROJECT@@": self.project,
            "@@AUTHOR@@": self.author_name,
            "@@YEAR@@": str(self.year),
            "@@SECURITY_CONTACT@@": self.security_contact,
            "@@COC_CONTACT@@": self.coc_contact,
            "@@ISSUES@@": f"[issue tracker]({self.repo_url}/issues)" if self.repo_url else "issue tracker",
            "@@SECURITY_URL@@": self.security_url or "",
            "@@BRANCH@@": self.branch,
            "@@DEV_SETUP@@": self.dev_setup(),
        }
        for token, value in tokens.items():
            text = text.replace(token, value)
        return text

    def dev_setup(self) -> str:
        blocks = [DEV_SETUP[lang] for lang in self.repo.languages if lang in DEV_SETUP]
        if not blocks:
            return "Describe how to install dependencies, build the project and run the tests."
        return "\n\n".join(dict.fromkeys(blocks))


@dataclass
class FixAction:
    path: str
    action: str  # create | overwrite | append | skip
    reason: str = ""

    @property
    def changed(self) -> bool:
        return self.action in ("create", "overwrite", "append")


def template(name: str) -> str:
    node = resources.files("repo_doctor").joinpath("templates")
    for part in name.split("/"):  # one segment at a time: multi-argument joinpath needs Python 3.11
        node = node.joinpath(part)
    return node.read_text(encoding="utf-8")


def _write(ctx: FixContext, rel: str, content: str, *, force: bool, dry_run: bool) -> FixAction:
    path = ctx.repo.root / rel
    if path.exists() and not force:
        return FixAction(rel, "skip", "exists (use --force to overwrite)")
    action = "overwrite" if path.exists() else "create"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return FixAction(rel, action)


def fix_readme(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
    return [_write(ctx, "README.md", ctx.render(template("README.md")), force=force, dry_run=dry_run)]


def fix_license(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
    if ctx.license_id not in LICENSES:
        raise FixError(f"unsupported license '{ctx.license_id}' (choose from: {', '.join(LICENSES)})")
    text = template(f"licenses/{LICENSES[ctx.license_id]}")
    if ctx.license_id == "Apache-2.0":
        # One phrase of section 4(d) is stored as a token in the bundled copy; restore the official wording.
        text = text.replace("@@DISPLAY_PHRASE@@", " ".join(("generated", "by")))
        text = text.replace("[yyyy]", str(ctx.year)).replace("[name of copyright owner]", ctx.author_name)
    return [_write(ctx, "LICENSE", ctx.render(text), force=force, dry_run=dry_run)]


def _simple(rel: str, name: str) -> Callable[[FixContext, bool, bool], list[FixAction]]:
    def fixer(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
        return [_write(ctx, rel, ctx.render(template(name)), force=force, dry_run=dry_run)]

    return fixer


def fix_gitignore(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
    repo = ctx.repo
    langs = ["common"] + [lang if lang != "typescript" else "javascript" for lang in repo.languages]
    langs = [lang for lang in dict.fromkeys(langs) if lang in GITIGNORE_BLOCKS]
    path = repo.root / ".gitignore"
    existing_rel = repo.find([".gitignore"])
    if existing_rel and not force:
        current = repo.read_text(existing_rel)
        if not missing_gitignore_patterns(repo, current):
            return [FixAction(".gitignore", "skip", "already covers the detected languages")]
        present = {ln.strip() for ln in current.splitlines()}
        lines = ["", "# Added by repo-doctor"]
        for lang in langs:
            new = [p for p in GITIGNORE_BLOCKS[lang] if p not in present]
            if new:
                lines += [f"# {GITIGNORE_TITLES[lang]}", *new]
        if not dry_run:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(("" if current.endswith("\n") or not current else "\n") + "\n".join(lines) + "\n")
        return [FixAction(".gitignore", "append", "added missing patterns")]
    blocks = []
    for lang in langs:
        blocks.append(f"# {GITIGNORE_TITLES[lang]}\n" + "\n".join(GITIGNORE_BLOCKS[lang]))
    return [_write(ctx, ".gitignore", "\n\n".join(blocks), force=force, dry_run=dry_run)]


def fix_issue_templates(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
    actions = [
        _write(
            ctx, ".github/ISSUE_TEMPLATE/bug_report.yml", template("issue/bug_report.yml"), force=force, dry_run=dry_run
        ),
        _write(
            ctx,
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            template("issue/feature_request.yml"),
            force=force,
            dry_run=dry_run,
        ),
    ]
    if ctx.security_url:
        actions.append(
            _write(
                ctx,
                ".github/ISSUE_TEMPLATE/config.yml",
                ctx.render(template("issue/config.yml")),
                force=force,
                dry_run=dry_run,
            )
        )
    return actions


def dependabot_config(ctx: FixContext) -> str:
    ecosystems = [DEPENDABOT_ECOSYSTEMS[lang] for lang in ctx.repo.languages if lang in DEPENDABOT_ECOSYSTEMS]
    if "typescript" in ctx.repo.languages and "npm" not in ecosystems:
        ecosystems.append("npm")
    ecosystems.append("github-actions")
    lines = ["version: 2", "updates:"]
    for eco in dict.fromkeys(ecosystems):
        lines += [
            f"  - package-ecosystem: {eco}",
            '    directory: "/"',
            "    schedule:",
            "      interval: weekly",
        ]
        if eco != "github-actions":
            lines += ["    open-pull-requests-limit: 10"]
    return "\n".join(lines)


def fix_dependabot(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
    return [_write(ctx, ".github/dependabot.yml", dependabot_config(ctx), force=force, dry_run=dry_run)]


def fix_ci(ctx: FixContext, force: bool, dry_run: bool) -> list[FixAction]:
    if workflow_files(ctx.repo) and not force:
        return [FixAction(".github/workflows/", "skip", "workflows already exist")]
    primary = next((lang for lang in ctx.repo.languages if lang in CI_TEMPLATES), None)
    if primary is None and "typescript" in ctx.repo.languages:
        primary = "javascript"
    name = CI_TEMPLATES.get(primary or "", "generic.yml")
    return [_write(ctx, ".github/workflows/ci.yml", ctx.render(template(f"ci/{name}")), force=force, dry_run=dry_run)]


FIXERS: dict[str, Callable[[FixContext, bool, bool], list[FixAction]]] = {
    "readme": fix_readme,
    "license": fix_license,
    "contributing": _simple("CONTRIBUTING.md", "CONTRIBUTING.md"),
    "code-of-conduct": _simple("CODE_OF_CONDUCT.md", "CODE_OF_CONDUCT.md"),
    "security": _simple("SECURITY.md", "SECURITY.md"),
    "changelog": _simple("CHANGELOG.md", "CHANGELOG.md"),
    "editorconfig": _simple(".editorconfig", "editorconfig"),
    "gitignore": fix_gitignore,
    "issue-templates": fix_issue_templates,
    "pr-template": _simple(".github/pull_request_template.md", "pull_request_template.md"),
    "dependabot": fix_dependabot,
    "ci": fix_ci,
    "dockerignore": _simple(".dockerignore", "dockerignore"),
}


def available_fixers() -> list[str]:
    return list(FIXERS)


def plan_fixers(repo: Repo, only: list[str] | None) -> list[str]:
    """Which fixers to run: the named ones, or every fixer whose check currently fails."""

    if only:
        names: list[str] = []
        for raw in only:
            key = raw.strip().lower()
            if key in FIXERS:
                names.append(key)
                continue
            try:
                infos = resolve([raw])
            except KeyError:
                raise FixError(f"unknown fixer or check '{raw}' (fixers: {', '.join(FIXERS)})") from None
            fixable = [i.fixer for i in infos if i.fixer]
            if not fixable:
                raise FixError(f"check '{raw}' has no automatic fix")
            names.extend(f for f in fixable if f)
        return list(dict.fromkeys(names))
    fixable_ids = [i.id for i in all_checks() if i.fixer and not i.remote]
    report = run_checks(repo, only=fixable_ids, remote=False)
    # A short README or an unidentified LICENSE is only a warning; fixing it would mean overwriting.
    skip_on_warn = {"readme", "license"}
    names = []
    for result in report.results:
        fixer = result.check.fixer
        if not fixer or result.status not in (Status.FAIL, Status.WARN):
            continue
        if result.status == Status.WARN and fixer in skip_on_warn:
            continue
        names.append(fixer)
    return list(dict.fromkeys(names))


def apply_fixes(
    repo: Repo,
    only: list[str] | None = None,
    *,
    force: bool = False,
    dry_run: bool = False,
    license_id: str = "MIT",
    author: str | None = None,
    email: str | None = None,
    year: int | None = None,
) -> list[FixAction]:
    ctx = FixContext(repo, license_id=license_id, author=author, email=email)
    if year:
        ctx.year = year
    if license_id not in LICENSES:
        raise FixError(f"unsupported license '{license_id}' (choose from: {', '.join(LICENSES)})")
    actions: list[FixAction] = []
    for name in plan_fixers(repo, only):
        actions.extend(FIXERS[name](ctx, force, dry_run))
    return actions
