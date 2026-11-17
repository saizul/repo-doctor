from __future__ import annotations

import json

import pytest

from conftest import make_repo, outcome_of, status_of
from repo_doctor.model import Status

FULL_PACKAGE = {
    "name": "x",
    "description": "d",
    "license": "MIT",
    "repository": "github:o/r",
    "keywords": ["a"],
}


def test_pyproject_metadata(tmp_path, healthy):
    assert status_of(healthy, "RD030") == Status.PASS
    repo = make_repo(tmp_path, {"pyproject.toml": '[project]\nname = "x"\n'})
    outcome = outcome_of(repo, "RD030")
    assert outcome.status == Status.FAIL
    assert outcome.details == ["pyproject.toml: missing description, license, urls.Repository, keywords"]


def test_pyproject_license_via_classifier_and_single_missing_warns(tmp_path):
    text = (
        '[project]\nname="x"\ndescription="d"\nkeywords=["k"]\nclassifiers=["License :: OSI Approved :: MIT License"]\n'
    )
    outcome = outcome_of(make_repo(tmp_path, {"pyproject.toml": text}), "RD030")
    assert outcome.status == Status.WARN
    assert "urls.Repository" in outcome.message


def test_poetry_and_build_only_pyproject(tmp_path):
    poetry = '[tool.poetry]\nname="x"\ndescription="d"\nlicense="MIT"\nrepository="https://x"\nkeywords=["a"]\n'
    assert status_of(make_repo(tmp_path / "a", {"pyproject.toml": poetry}), "RD030") == Status.PASS
    build_only = '[build-system]\nrequires=["setuptools"]\n'
    assert "[project] table" in outcome_of(make_repo(tmp_path / "b", {"pyproject.toml": build_only}), "RD030").message


@pytest.mark.parametrize(
    ("data", "status"),
    [
        (FULL_PACKAGE, Status.PASS),
        ({"name": "x", "private": True}, Status.PASS),
        ({"name": "x", "description": "d", "license": "MIT", "keywords": ["k"]}, Status.WARN),
        ({"name": "x"}, Status.FAIL),
    ],
)
def test_package_json(tmp_path, data, status):
    assert status_of(make_repo(tmp_path, {"package.json": json.dumps(data)}), "RD030") == status


def test_composer_and_cargo(tmp_path):
    composer = {"name": "a/b", "description": "d", "license": "MIT", "keywords": ["k"], "support": {"source": "x"}}
    assert status_of(make_repo(tmp_path / "a", {"composer.json": json.dumps(composer)}), "RD030") == Status.PASS
    cargo = '[package]\nname="x"\ndescription="d"\nlicense-file="LICENSE"\nrepository="r"\nkeywords=["k"]\n'
    assert status_of(make_repo(tmp_path / "b", {"Cargo.toml": cargo}), "RD030") == Status.PASS
    workspace = '[workspace]\nmembers=["a"]\n'
    assert status_of(make_repo(tmp_path / "c", {"Cargo.toml": workspace}), "RD030") == Status.PASS


def test_unparseable_manifest(tmp_path):
    outcome = outcome_of(make_repo(tmp_path, {"package.json": "{not json"}), "RD030")
    assert outcome.status == Status.FAIL and "Cannot parse package.json" in outcome.message


def test_no_manifest_skips(tmp_path):
    assert status_of(make_repo(tmp_path), "RD030") == Status.SKIP


def test_ci_detection(tmp_path):
    assert status_of(make_repo(tmp_path / "a"), "RD020") == Status.FAIL
    assert status_of(make_repo(tmp_path / "b", {".gitlab-ci.yml": "test: {}"}), "RD020") == Status.PASS
    push_only = make_repo(tmp_path / "c", {".github/workflows/ci.yaml": "on: push\n"})
    assert status_of(push_only, "RD020") == Status.WARN
    pr = make_repo(tmp_path / "d", {".github/workflows/ci.yml": "on:\n  pull_request:\n"})
    assert status_of(pr, "RD020") == Status.PASS


def test_issue_and_pr_templates(tmp_path):
    assert status_of(make_repo(tmp_path / "a"), "RD021") == Status.FAIL
    only_config = make_repo(tmp_path / "b", {".github/ISSUE_TEMPLATE/config.yml": "x"})
    assert status_of(only_config, "RD021") == Status.FAIL
    legacy = make_repo(tmp_path / "c", {".github/ISSUE_TEMPLATE.md": "x"})
    assert status_of(legacy, "RD021") == Status.PASS
    assert status_of(make_repo(tmp_path / "d"), "RD022") == Status.FAIL
    upper = make_repo(tmp_path / "e", {".github/PULL_REQUEST_TEMPLATE.md": "x"})
    assert status_of(upper, "RD022") == Status.PASS
    multi = make_repo(tmp_path / "f", {".github/PULL_REQUEST_TEMPLATE/feature.md": "x"})
    assert status_of(multi, "RD022") == Status.PASS


def test_dependency_update_configs(tmp_path):
    assert status_of(make_repo(tmp_path / "a"), "RD023") == Status.FAIL
    assert status_of(make_repo(tmp_path / "b", {"renovate.json": "{}"}), "RD023") == Status.PASS
    assert status_of(make_repo(tmp_path / "c", {".github/dependabot.yaml": ""}), "RD023") == Status.PASS
    pkg = make_repo(tmp_path / "d", {"package.json": json.dumps({"renovate": {"extends": ["config:base"]}})})
    assert status_of(pkg, "RD023") == Status.PASS
