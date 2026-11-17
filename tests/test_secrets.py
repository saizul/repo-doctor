"""Fake credentials are assembled at runtime so that this file never contains a real-looking token."""

from __future__ import annotations

import re

import pytest

from conftest import init_git, make_repo, outcome_of, status_of
from repo_doctor.model import Status
from repo_doctor.scanner import mask, scan_text, shannon_entropy, should_scan

AWS_ID = "AKIA" + "IOSFODNN7" + "ABCDEFG"
GH_TOKEN = "ghp" + "_" + "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5"
GH_PAT = "github" + "_pat_" + "11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz"
SLACK = "xox" + "b-" + "123456789012-abcdefghijkl"
STRIPE = "sk" + "_live_" + "4eC39HqLyjWDarjtT1zdp7dc"
GOOGLE = "AI" + "za" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q"
PRIVATE_KEY = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"
NPM = "npm" + "_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


@pytest.mark.parametrize(
    ("line", "rule"),
    [
        (f"aws_access_key_id = {AWS_ID}", "aws-access-key-id"),
        (f"token: {GH_TOKEN}", "github-token"),
        (f"export GH={GH_PAT}", "github-fine-grained-token"),
        (f"slack = '{SLACK}'", "slack-token"),
        (f"STRIPE={STRIPE}", "stripe-live-key"),
        (f"key = {GOOGLE}", "google-api-key"),
        (PRIVATE_KEY, "private-key"),
        (f"//registry.npmjs.org/:_authToken={NPM}", "npm-token"),
        ('password = "Zx9!kLm2#Qr7"', "generic-secret"),  # repo-doctor:ignore
        ("DATABASE_URL=postgres://app:" + "S3cr3tPassw0rd" + "@db.internal/app", "url-credentials"),
    ],
)
def test_rules_detect(line, rule):
    findings = scan_text("f.txt", line)
    assert [f.rule.id for f in findings] == [rule]
    assert findings[0].line == 1


@pytest.mark.parametrize(
    "line",
    [
        'password = "changeme"',
        'password = "<your password>"',
        'password = "${DB_PASSWORD}"',
        'secret: "xxxxxxxxxxxx"',
        'api_key = "your_api_key_here"',
        'password = "aaaaaaaaaaaa"',
        "postgres://user:${PASSWORD}@db/app",
        "https://user:" + "password" + "@example.com",
        f"key = {AWS_ID}  # repo-doctor:ignore",
        f"key = {AWS_ID}  # pragma: allowlist secret",
    ],
)
def test_placeholders_and_inline_allow(line):
    assert scan_text("f.txt", line) == []


def test_allow_patterns():
    assert scan_text("f", f"k={AWS_ID}", [re.compile("IOSFODNN7")]) == []


def test_binary_and_skip_files():
    assert scan_text("f", "\0\0" + AWS_ID) == []
    assert not should_scan("logo.png") and not should_scan("package-lock.json") and should_scan("app.py")


def test_mask_and_entropy():
    assert mask("abcdefghijkl") == "abcd…kl"
    assert mask("abc") == "ab…"
    assert shannon_entropy("") == 0
    assert shannon_entropy("aaaa") == 0
    assert shannon_entropy("abcd") == 2


def test_check_reports_masked_values(tmp_path):
    repo = make_repo(tmp_path, {"config.py": f"KEY = '{AWS_ID}'\n", "ok.py": "x = 1\n"})
    outcome = outcome_of(repo, "RD015")
    assert outcome.status == Status.FAIL
    assert outcome.details == ["config.py:1 AWS access key ID (AKIA…FG)"]
    assert AWS_ID not in " ".join(outcome.details)
    assert outcome.locations[0].line == 1


def test_allow_paths_from_config(tmp_path):
    repo = make_repo(
        tmp_path,
        {
            ".repo-doctor.toml": '[secrets]\nallow_paths = ["tests/fixtures/**"]\n',
            "tests/fixtures/sample.env": f"KEY={AWS_ID}\n",
        },
    )
    assert status_of(repo, "RD015") == Status.PASS


def test_only_tracked_files_are_scanned_in_git(tmp_path):
    root = tmp_path / "g"
    make_repo(root, {"a.py": "x = 1\n"})
    init_git(root)
    (root / "local.env").write_text(f"KEY={AWS_ID}\n")
    assert status_of(make_repo(root), "RD015") == Status.PASS


def test_many_findings_are_truncated(tmp_path):
    repo = make_repo(tmp_path, {"keys.txt": "\n".join(f"k{i}={AWS_ID}" for i in range(60))})
    outcome = outcome_of(repo, "RD015")
    assert len(outcome.details) == 51 and outcome.details[-1].startswith("... and 10 more")
