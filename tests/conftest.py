from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from repo_doctor.engine import run_checks
from repo_doctor.model import Status
from repo_doctor.repo import Repo

REPO_ROOT = Path(__file__).resolve().parent.parent

HEALTHY_README = """\
# demo

[![CI](https://github.com/octo/demo/actions/workflows/ci.yml/badge.svg)](https://github.com/octo/demo/actions)

A small demo project that is used by the repo-doctor test-suite to represent a
well maintained repository with every recommended file in place.

## Installation

pip install demo

## Usage

demo --help

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
"""

MIT_TEXT = (REPO_ROOT / "src" / "repo_doctor" / "templates" / "licenses" / "MIT.txt").read_text(encoding="utf-8")


def write_files(root: Path, files: dict[str, str | bytes]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


def healthy_files() -> dict[str, str]:
    long_text = "This document explains the process in enough detail to be useful for contributors.\n"
    return {
        "README.md": HEALTHY_README,
        "LICENSE": MIT_TEXT.replace("@@YEAR@@", "2026").replace("@@AUTHOR@@", "Jane Doe"),
        "CONTRIBUTING.md": "# Contributing\n\n" + long_text,
        "CODE_OF_CONDUCT.md": "# Code of Conduct\n\n" + long_text,
        "SECURITY.md": "# Security\n\n" + long_text,
        "CHANGELOG.md": "# Changelog\n\n## 0.1.0\n",
        ".gitignore": "__pycache__/\n.venv/\n*.egg-info/\n.env\n",
        ".editorconfig": "root = true\n",
        ".github/workflows/ci.yml": "on: [push, pull_request]\njobs: {}\n",
        ".github/ISSUE_TEMPLATE/bug_report.yml": "name: Bug\n",
        ".github/pull_request_template.md": "## What\n",
        ".github/dependabot.yml": "version: 2\n",
        "pyproject.toml": (
            '[project]\nname = "demo"\ndescription = "Demo"\nlicense = { text = "MIT" }\n'
            'keywords = ["demo"]\n[project.urls]\nRepository = "https://github.com/octo/demo"\n'
        ),
        "src/demo/__init__.py": "",
        "src/demo/core.py": "VALUE = 1\n",
        "src/demo/cli.py": "def main():\n    return 0\n",
    }


def make_repo(root: Path, files: dict[str, str | bytes] | None = None) -> Repo:
    root.mkdir(parents=True, exist_ok=True)
    write_files(root, files or {})
    return Repo(root)


def init_git(root: Path, add: bool = True, remote: str | None = None) -> None:
    git = shutil.which("git")
    if not git:
        pytest.skip("git is not installed")
    subprocess.run([git, "init", "-q", str(root)], check=True)
    subprocess.run([git, "-C", str(root), "config", "user.name", "Test User"], check=True)
    subprocess.run([git, "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    if remote:
        subprocess.run([git, "-C", str(root), "remote", "add", "origin", remote], check=True)
    if add:
        subprocess.run([git, "-C", str(root), "add", "-A"], check=True)


def status_of(repo: Repo, check_id: str) -> Status:
    return run_checks(repo, only=[check_id], remote=False).results[0].status


def outcome_of(repo: Repo, check_id: str):
    return run_checks(repo, only=[check_id], remote=False).results[0].outcome


@pytest.fixture(autouse=True)
def _no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")


@pytest.fixture
def healthy(tmp_path: Path) -> Repo:
    return make_repo(tmp_path / "healthy", healthy_files())
