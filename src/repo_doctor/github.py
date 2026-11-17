"""Tiny GitHub REST client for the optional remote checks (standard library only)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from repo_doctor._version import __version__

DEFAULT_API = "https://api.github.com"


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


def token_from_env() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None


class GitHubClient:
    def __init__(self, token: str, api_url: str | None = None, timeout: float = 15.0) -> None:
        self.token = token
        self.api_url = (api_url or os.environ.get("GITHUB_API_URL") or DEFAULT_API).rstrip("/")
        self.timeout = timeout

    def get(self, path: str) -> Any:
        request = urllib.request.Request(
            f"{self.api_url}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": f"repo-doctor/{__version__}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8") or "null")
        except urllib.error.HTTPError as exc:
            try:
                message = json.loads(exc.read().decode("utf-8")).get("message", exc.reason)
            except (ValueError, AttributeError):
                message = str(exc.reason)
            raise GitHubError(exc.code, message) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GitHubError(0, str(exc)) from None

    def repository(self, owner: str, name: str) -> dict[str, Any]:
        return self.get(f"/repos/{_q(owner)}/{_q(name)}")

    def branch_protection(self, owner: str, name: str, branch: str) -> dict[str, Any] | None:
        """Classic branch protection, or ``None`` when the branch is not protected."""

        try:
            return self.get(f"/repos/{_q(owner)}/{_q(name)}/branches/{_q(branch)}/protection")
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise

    def branch_rules(self, owner: str, name: str, branch: str) -> list[dict[str, Any]]:
        """Active repository ruleset rules for ``branch`` (readable with read access)."""

        data = self.get(f"/repos/{_q(owner)}/{_q(name)}/rules/branches/{_q(branch)}")
        return data if isinstance(data, list) else []


def _q(part: str) -> str:
    return urllib.parse.quote(part, safe="")
