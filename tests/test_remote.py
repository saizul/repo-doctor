from __future__ import annotations

import io
import json
import urllib.error

import pytest

from conftest import init_git, make_repo
from repo_doctor import github as gh
from repo_doctor.engine import run_checks
from repo_doctor.github import GitHubClient, GitHubError
from repo_doctor.model import Status
from repo_doctor.repo import parse_github_slug

REMOTE_IDS = ["RD040", "RD041", "RD042", "RD043"]


class FakeClient:
    def __init__(self, repo=None, protection=None, rules=None, error=None, protection_error=None):
        self.repo = repo or {}
        self.protection = protection
        self.rules = rules or []
        self.error = error
        self.protection_error = protection_error
        self.calls = []

    def repository(self, owner, name):
        self.calls.append(("repo", owner, name))
        if self.error:
            raise self.error
        return self.repo

    def branch_rules(self, owner, name, branch):
        self.calls.append(("rules", branch))
        return self.rules

    def branch_protection(self, owner, name, branch):
        self.calls.append(("protection", branch))
        if self.protection_error:
            raise self.protection_error
        return self.protection


@pytest.fixture
def github_repo(tmp_path, monkeypatch):
    root = tmp_path / "r"
    make_repo(root, {"README.md": "x"})
    init_git(root, remote="https://github.com/octo/demo.git")
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-value")
    return root


def run_remote(root, client):
    repo = make_repo(root)
    repo._cache["github_client"] = client
    return {r.check.id: r for r in run_checks(repo, only=REMOTE_IDS).results}


def test_remote_checks_pass(github_repo):
    client = FakeClient(
        repo={
            "description": "A demo repository with a proper description",
            "topics": ["a", "b", "c"],
            "homepage": "https://demo.example",
            "default_branch": "main",
        },
        rules=[{"type": "pull_request"}, {"type": "non_fast_forward"}],
    )
    results = run_remote(github_repo, client)
    assert {k: r.status for k, r in results.items()} == dict.fromkeys(REMOTE_IDS, Status.PASS)
    assert sum(1 for c in client.calls if c[0] == "repo") == 1  # cached across checks
    assert "pull_request" in results["RD043"].outcome.message


def test_remote_checks_fail_and_warn(github_repo):
    client = FakeClient(repo={"description": "short", "topics": ["x"], "homepage": "", "default_branch": "dev"})
    results = run_remote(github_repo, client)
    assert results["RD040"].status == Status.WARN
    assert results["RD041"].status == Status.WARN
    assert results["RD042"].status == Status.FAIL
    assert results["RD043"].status == Status.FAIL
    assert ("protection", "dev") in client.calls


def test_remote_missing_values(github_repo):
    results = run_remote(github_repo, FakeClient(repo={"description": None, "topics": []}, protection={"url": "x"}))
    assert results["RD040"].status == Status.FAIL
    assert results["RD041"].status == Status.FAIL
    assert results["RD043"].status == Status.PASS


def test_branch_protection_without_admin_is_skipped(github_repo):
    client = FakeClient(repo={"description": "d" * 30}, protection_error=GitHubError(403, "Resource not accessible"))
    assert run_remote(github_repo, client)["RD043"].status == Status.SKIP


def test_api_error_skips_everything(github_repo):
    results = run_remote(github_repo, FakeClient(error=GitHubError(401, "Bad credentials")))
    assert all(r.status == Status.SKIP for r in results.values())
    assert "Bad credentials" in results["RD040"].outcome.message


def test_skipped_without_token(tmp_path):
    repo = make_repo(tmp_path)
    results = run_checks(repo, only=REMOTE_IDS)
    assert all(r.status == Status.SKIP and "GITHUB_TOKEN" in r.outcome.message for r in results.results)


def test_skipped_for_non_github_remote(tmp_path, monkeypatch):
    root = tmp_path / "r"
    make_repo(root)
    init_git(root, remote="https://gitlab.com/o/r.git")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    result = run_checks(make_repo(root), only=["RD040"]).results[0]
    assert result.status == Status.SKIP and "not a GitHub" in result.outcome.message


def test_offline_flag_and_config(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    assert run_checks(make_repo(tmp_path / "a"), only=["RD041"], remote=False).results[0].status == Status.SKIP
    repo = make_repo(tmp_path / "b", {".repo-doctor.toml": "remote = false\n"})
    assert "disabled" in run_checks(repo, only=["RD041"]).results[0].outcome.message


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://github.com/octo/demo.git", ("octo", "demo")),
        ("git@github.com:octo/demo.git", ("octo", "demo")),
        ("ssh://git@github.com/octo/demo", ("octo", "demo")),
        ("https://github.com/octo/demo.js/", ("octo", "demo.js")),
        ("https://gitlab.com/octo/demo.git", None),
        ("", None),
    ],
)
def test_parse_github_slug(url, slug):
    assert parse_github_slug(url) == slug


def test_client_sends_headers_and_parses(monkeypatch):
    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["auth"] = request.get_header("Authorization")
        return Response(json.dumps({"description": "x"}).encode())

    monkeypatch.setattr(gh.urllib.request, "urlopen", fake_urlopen)
    client = GitHubClient("tkn", api_url="https://ghe.example/api/v3/")
    assert client.repository("o", "r b") == {"description": "x"}
    assert seen["url"] == "https://ghe.example/api/v3/repos/o/r%20b"
    assert seen["auth"] == "Bearer tkn"


def test_client_errors(monkeypatch):
    def not_found(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 404, "Not Found", {}, io.BytesIO(b'{"message": "Branch not protected"}')
        )

    monkeypatch.setattr(gh.urllib.request, "urlopen", not_found)
    client = GitHubClient("t")
    assert client.branch_protection("o", "r", "main") is None
    with pytest.raises(GitHubError) as exc:
        client.repository("o", "r")
    assert exc.value.status == 404 and "Branch not protected" in str(exc.value)

    def offline(request, timeout):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(gh.urllib.request, "urlopen", offline)
    with pytest.raises(GitHubError) as exc:
        client.branch_rules("o", "r", "main")
    assert exc.value.status == 0


def test_token_from_env(monkeypatch):
    assert gh.token_from_env() is None
    monkeypatch.setenv("GH_TOKEN", "b")
    assert gh.token_from_env() == "b"
    monkeypatch.setenv("GITHUB_TOKEN", "a")
    assert gh.token_from_env() == "a"
