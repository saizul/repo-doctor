from __future__ import annotations

import pytest

from conftest import init_git, make_repo, outcome_of, status_of
from repo_doctor.model import Status


def test_gitignore_present_and_languages(tmp_path):
    repo = make_repo(tmp_path / "a", {"package.json": "{}", "a.js": "", ".gitignore": "dist/\n"})
    assert status_of(repo, "RD010") == Status.PASS
    outcome = outcome_of(repo, "RD011")
    assert outcome.status == Status.FAIL
    assert "node_modules/" in outcome.message and ".env" in outcome.message
    good = make_repo(tmp_path / "b", {"package.json": "{}", ".gitignore": "/node_modules\n.env*\n"})
    assert status_of(good, "RD011") == Status.PASS
    assert status_of(make_repo(tmp_path / "c"), "RD010") == Status.FAIL
    assert status_of(make_repo(tmp_path / "d"), "RD011") == Status.FAIL


@pytest.mark.parametrize(
    ("files", "missing"),
    [
        ({"pyproject.toml": "", ".gitignore": ".env\n"}, "__pycache__/"),
        ({"composer.json": "{}", ".gitignore": ".env\n"}, "vendor/"),
        ({"Cargo.toml": "", ".gitignore": ".env\n"}, "target/"),
    ],
)
def test_gitignore_language_specific(tmp_path, files, missing):
    assert missing in outcome_of(make_repo(tmp_path, files), "RD011").message


def test_gitignore_glob_patterns_count(tmp_path):
    repo = make_repo(tmp_path, {"setup.py": "", ".gitignore": "**/__pycache__/\n*venv*\n*.egg\n.env\n"})
    assert status_of(repo, "RD011") == Status.PASS


def test_editorconfig(tmp_path):
    assert status_of(make_repo(tmp_path / "a"), "RD012") == Status.FAIL
    assert status_of(make_repo(tmp_path / "b", {".editorconfig": "root = true"}), "RD012") == Status.PASS


def test_lockfile_node(tmp_path):
    assert status_of(make_repo(tmp_path / "a", {"package.json": "{}"}), "RD013") == Status.FAIL
    assert status_of(make_repo(tmp_path / "b", {"package.json": "{}", "pnpm-lock.yaml": ""}), "RD013") == Status.PASS


def test_lockfile_untracked_in_git(tmp_path):
    root = tmp_path / "g"
    make_repo(root, {"package.json": "{}"})
    init_git(root)
    (root / "package-lock.json").write_text("{}")
    outcome = outcome_of(make_repo(root), "RD013")
    assert outcome.status == Status.FAIL and "not committed" in outcome.message


def test_lockfile_skips_python_library_and_composer_library(tmp_path):
    assert status_of(make_repo(tmp_path / "a", {"pyproject.toml": "[project]\nname='x'\n"}), "RD013") == Status.SKIP
    assert status_of(make_repo(tmp_path / "b", {"composer.json": '{"type": "library"}'}), "RD013") == Status.SKIP


def test_lockfile_python_managers_rust_go(tmp_path):
    poetry = make_repo(tmp_path / "a", {"pyproject.toml": "[tool.poetry]\nname='x'\n"})
    assert status_of(poetry, "RD013") == Status.FAIL
    app = make_repo(tmp_path / "b", {"composer.json": '{"type": "project"}', "composer.lock": "{}"})
    assert status_of(app, "RD013") == Status.PASS
    rust = make_repo(tmp_path / "c", {"Cargo.toml": "[package]\n", "src/main.rs": "fn main(){}"})
    assert status_of(rust, "RD013") == Status.FAIL
    go = make_repo(tmp_path / "d", {"go.mod": "module x\n\nrequire example.com/y v1.0.0\n", "go.sum": ""})
    assert status_of(go, "RD013") == Status.PASS
    go_nodeps = make_repo(tmp_path / "e", {"go.mod": "module x\n"})
    assert status_of(go_nodeps, "RD013") == Status.SKIP


def test_large_files(tmp_path):
    repo = make_repo(
        tmp_path / "a",
        {".repo-doctor.toml": "large_file_mb = 0.001\n", "big.bin": b"x" * 5000, "small.txt": "x"},
    )
    outcome = outcome_of(repo, "RD014")
    assert outcome.status == Status.FAIL
    assert outcome.details[0].startswith("big.bin")
    lfs = make_repo(
        tmp_path / "b",
        {
            ".repo-doctor.toml": "large_file_mb = 0.001\n",
            ".gitattributes": "*.bin filter=lfs diff=lfs merge=lfs -text\n",
            "big.bin": b"x" * 5000,
        },
    )
    assert status_of(lfs, "RD014") == Status.PASS


def test_large_files_only_tracked(tmp_path):
    root = tmp_path / "g"
    make_repo(root, {".repo-doctor.toml": "large_file_mb = 0.001\n", "a.txt": "x"})
    init_git(root)
    (root / "big.bin").write_bytes(b"x" * 5000)  # not added to the index
    assert status_of(make_repo(root), "RD014") == Status.PASS


def test_dockerignore_and_base_pinning(tmp_path):
    repo = make_repo(
        tmp_path / "a",
        {
            "Dockerfile": "FROM python:3.12-slim AS build\nFROM build\nFROM node\nFROM alpine:latest\nFROM scratch\n",
        },
    )
    assert status_of(repo, "RD050") == Status.FAIL
    outcome = outcome_of(repo, "RD051")
    assert outcome.status == Status.WARN
    assert outcome.details == ["Dockerfile:3 FROM node", "Dockerfile:4 FROM alpine:latest"]
    pinned = make_repo(
        tmp_path / "b",
        {
            "Dockerfile": "ARG V=1\nFROM --platform=$BUILDPLATFORM golang:1.25 AS b\nFROM gcr.io/x/y@sha256:abc\n",
            ".dockerignore": ".git",
        },
    )
    assert status_of(pinned, "RD050") == Status.PASS
    assert status_of(pinned, "RD051") == Status.PASS


def test_docker_checks_skip_without_docker(tmp_path):
    repo = make_repo(tmp_path, {"main.go": "package main"})
    assert status_of(repo, "RD050") == Status.SKIP
    assert status_of(repo, "RD051") == Status.SKIP
