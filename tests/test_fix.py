from __future__ import annotations

import re

import pytest

from conftest import REPO_ROOT, init_git, make_repo
from repo_doctor.engine import run_checks
from repo_doctor.fix import FIXERS, FixContext, FixError, apply_fixes, dependabot_config, plan_fixers
from repo_doctor.model import Status
from repo_doctor.repo import Repo

TEMPLATES = REPO_ROOT / "src" / "repo_doctor" / "templates"


def test_fix_everything_on_empty_python_repo(tmp_path):
    repo = make_repo(tmp_path, {"pyproject.toml": '[project]\nname = "demo"\n', "a.py": "", "b.py": "", "c.py": ""})
    before = run_checks(repo, remote=False).score
    actions = apply_fixes(repo, author="Jane Doe", email="security@example.org", year=2030)
    created = {a.path for a in actions if a.action == "create"}
    assert {
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SECURITY.md",
        "CHANGELOG.md",
        ".gitignore",
        ".editorconfig",
        ".github/workflows/ci.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/pull_request_template.md",
        ".github/dependabot.yml",
    } <= created
    assert "Copyright (c) 2030 Jane Doe" in (tmp_path / "LICENSE").read_text()
    assert "security@example.org" in (tmp_path / "SECURITY.md").read_text()
    assert "pip install -e" in (tmp_path / "CONTRIBUTING.md").read_text()
    assert "python-version" in (tmp_path / ".github/workflows/ci.yml").read_text()
    after = run_checks(Repo(tmp_path), remote=False)
    assert after.score > before + 40
    fixable_failures = [r for r in after.results if r.check.fixer and r.status == Status.FAIL]
    assert fixable_failures == []


def test_no_placeholders_left(tmp_path):
    repo = make_repo(tmp_path, {"package.json": "{}"})
    apply_fixes(repo)
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "@@" not in path.read_text(), path


def test_existing_files_are_not_overwritten(tmp_path):
    repo = make_repo(tmp_path, {"SECURITY.md": "my policy\n"})
    actions = apply_fixes(repo, ["security"])
    assert actions[0].action == "skip"
    assert (tmp_path / "SECURITY.md").read_text() == "my policy\n"
    actions = apply_fixes(repo, ["security"], force=True)
    assert actions[0].action == "overwrite"
    assert "Security Policy" in (tmp_path / "SECURITY.md").read_text()


def test_dry_run_writes_nothing(tmp_path):
    repo = make_repo(tmp_path)
    actions = apply_fixes(repo, dry_run=True)
    assert actions and all(a.action == "create" for a in actions)
    assert list(tmp_path.iterdir()) == []


def test_apache_license(tmp_path):
    repo = make_repo(tmp_path)
    apply_fixes(repo, ["license"], license_id="Apache-2.0", author="ACME Ltd", year=2027)
    text = (tmp_path / "LICENSE").read_text()
    assert "Apache License" in text and "Copyright 2027 ACME Ltd" in text and "[yyyy]" not in text
    assert run_checks(Repo(tmp_path), only=["RD004"]).results[0].outcome.message == "LICENSE: Apache-2.0"


def test_apache_text_matches_official_copy(tmp_path):
    """With the appendix placeholders restored, the text is byte-identical to apache.org/licenses/LICENSE-2.0.txt."""

    import hashlib

    repo = make_repo(tmp_path)
    apply_fixes(repo, ["license"], license_id="Apache-2.0", author="[name of copyright owner]", year=2027)
    text = (tmp_path / "LICENSE").read_text().replace("Copyright 2027 [name", "Copyright [yyyy] [name")
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert digest == "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def test_unknown_license_and_fixer(tmp_path):
    repo = make_repo(tmp_path)
    with pytest.raises(FixError):
        apply_fixes(repo, ["license"], license_id="WTFPL")
    with pytest.raises(FixError, match="unknown fixer"):
        apply_fixes(repo, ["nope"])
    with pytest.raises(FixError, match="no automatic fix"):
        apply_fixes(repo, ["RD015"])


def test_only_accepts_check_ids_and_slugs(tmp_path):
    repo = make_repo(tmp_path)
    assert plan_fixers(repo, ["RD006", "security-policy", "editorconfig"]) == [
        "code-of-conduct",
        "security",
        "editorconfig",
    ]


def test_default_plan_skips_passing_and_warned_readme(tmp_path, healthy):
    assert plan_fixers(healthy, None) == []
    repo = make_repo(tmp_path / "short", {"README.md": "# short\n"})
    assert "readme" not in plan_fixers(repo, None)


def test_gitignore_append_keeps_content(tmp_path):
    repo = make_repo(tmp_path, {".gitignore": "secret-notes.txt", "package.json": "{}"})
    actions = apply_fixes(repo, ["gitignore"])
    assert actions[0].action == "append"
    text = (tmp_path / ".gitignore").read_text()
    assert text.startswith("secret-notes.txt\n")
    assert "node_modules/" in text and "# Added by repo-doctor" in text
    assert apply_fixes(Repo(tmp_path), ["gitignore"])[0].action == "skip"


def test_gitignore_force_rewrites(tmp_path):
    repo = make_repo(tmp_path, {".gitignore": "old\n", "Cargo.toml": ""})
    assert apply_fixes(repo, ["gitignore"], force=True)[0].action == "overwrite"
    text = (tmp_path / ".gitignore").read_text()
    assert "old" not in text and "target/" in text


def test_ci_template_per_language(tmp_path):
    for files, marker in (
        ({"go.mod": "module x"}, "setup-go"),
        ({"Cargo.toml": ""}, "cargo test"),
        ({"composer.json": "{}"}, "setup-php"),
        ({"package.json": "{}"}, "setup-node"),
        ({"tsconfig.json": "{}", "a.ts": "", "b.ts": "", "c.ts": ""}, "setup-node"),
        ({}, "Replace this step"),
    ):
        root = tmp_path / marker.replace(" ", "-") / str(len(files))
        repo = make_repo(root, files)
        apply_fixes(repo, ["ci"])
        assert marker in (root / ".github/workflows/ci.yml").read_text()


def test_ci_not_written_when_workflows_exist(tmp_path):
    repo = make_repo(tmp_path, {".github/workflows/lint.yml": "on: pull_request"})
    assert apply_fixes(repo, ["ci"])[0].action == "skip"


def test_dependabot_ecosystems(tmp_path):
    repo = make_repo(tmp_path, {"package.json": "{}", "go.mod": "module x", "Dockerfile": "FROM a:1"})
    text = dependabot_config(FixContext(repo))
    for eco in ("npm", "gomod", "docker", "github-actions"):
        assert f"package-ecosystem: {eco}" in text


def test_contacts_use_github_when_known(tmp_path):
    root = tmp_path / "g"
    make_repo(root)
    init_git(root, remote="git@github.com:octo/demo.git")
    repo = Repo(root)
    apply_fixes(repo, ["security", "issue-templates", "code-of-conduct"])
    assert "https://github.com/octo/demo/security/advisories/new" in (root / "SECURITY.md").read_text()
    assert "advisories/new" in (root / ".github/ISSUE_TEMPLATE/config.yml").read_text()
    assert "Test User" in FixContext(repo).author_name


def test_issue_config_skipped_without_github(tmp_path):
    repo = make_repo(tmp_path)
    paths = [a.path for a in apply_fixes(repo, ["issue-templates"])]
    assert ".github/ISSUE_TEMPLATE/config.yml" not in paths


def test_every_template_is_used_and_valid_yaml_like():
    used = set()
    source = (REPO_ROOT / "src/repo_doctor/fix.py").read_text()
    for path in TEMPLATES.rglob("*"):
        if path.is_file():
            rel = path.relative_to(TEMPLATES).as_posix()
            used.add(rel)
            stem = rel.split("/")[-1]
            assert stem in source or rel in source, f"template {rel} is not referenced"
    assert len(used) >= 15
    assert set(FIXERS) >= {"license", "readme", "ci", "dependabot", "gitignore"}


def test_templates_contain_no_unknown_tokens():
    known = {
        "PROJECT",
        "AUTHOR",
        "YEAR",
        "SECURITY_CONTACT",
        "COC_CONTACT",
        "ISSUES",
        "SECURITY_URL",
        "BRANCH",
        "DEV_SETUP",
        "DISPLAY_PHRASE",
    }
    for path in TEMPLATES.rglob("*"):
        if path.is_file():
            tokens = set(re.findall(r"@@([A-Z_]+)@@", path.read_text()))
            assert tokens <= known, (path, tokens - known)
