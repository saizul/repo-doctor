"""A small, readable secret scanner.

It is deliberately conservative: a short list of high-signal token formats plus
one generic ``password = "..."`` rule with placeholder filtering. It is meant to
catch the common accident, not to replace a dedicated scanner such as gitleaks.

Suppress a finding with an inline ``repo-doctor:ignore`` (or ``pragma: allowlist secret``)
comment on the same line, or with ``[secrets] allow_paths`` / ``allow_patterns`` in the config.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePosixPath

INLINE_ALLOW = ("repo-doctor:ignore", "pragma: allowlist secret", "gitleaks:allow", "nosec")


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    pattern: re.Pattern[str]
    group: int = 0


RULES: list[Rule] = [
    Rule(
        "private-key",
        "Private key",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----"),
    ),
    Rule("aws-access-key-id", "AWS access key ID", re.compile(r"\b((?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16})\b"), 1),
    Rule(
        "aws-secret-access-key",
        "AWS secret access key",
        re.compile(r"(?i)aws_?secret_?access_?key\s*[:=]\s*[\"']?([A-Za-z0-9/+=]{40})\b"),
        1,
    ),
    Rule("github-token", "GitHub token", re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255})\b"), 1),
    Rule(
        "github-fine-grained-token",
        "GitHub fine-grained token",
        re.compile(r"\b(github_pat_[A-Za-z0-9_]{22,255})\b"),
        1,
    ),
    Rule("gitlab-token", "GitLab token", re.compile(r"\b(glpat-[A-Za-z0-9_-]{20,})\b"), 1),
    Rule("slack-token", "Slack token", re.compile(r"\b(xox[abposr]-[A-Za-z0-9-]{10,})\b"), 1),
    Rule(
        "slack-webhook",
        "Slack webhook URL",
        re.compile(r"(https://hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+)"),
        1,
    ),
    Rule("stripe-live-key", "Stripe live key", re.compile(r"\b((?:sk|rk)_live_[0-9a-zA-Z]{20,})\b"), 1),
    Rule("google-api-key", "Google API key", re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b"), 1),
    Rule("npm-token", "npm access token", re.compile(r"\b(npm_[A-Za-z0-9]{36})\b"), 1),
    Rule("pypi-token", "PyPI API token", re.compile(r"\b(pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,})\b"), 1),
    Rule("sendgrid-key", "SendGrid API key", re.compile(r"\b(SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43})\b"), 1),
    Rule(
        "url-credentials",
        "Password in a URL",
        re.compile(r"\b[a-z][a-z0-9+.-]{1,20}://[^\s:/@\"'<>{}$]{1,64}:([^\s:@/\"'<>{}$]{3,128})@[A-Za-z0-9.-]+"),
        1,
    ),
    Rule(
        "generic-secret",
        "Hardcoded password or secret",
        re.compile(
            r"(?i)\b(?:password|passwd|pwd|secret|secret_key|api_key|apikey|access_token|auth_token|client_secret)"
            r"[\"']?\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"
        ),
        1,
    ),
]

PLACEHOLDER_RE = re.compile(
    r"(?i)^(?:x+|\*+|\.+|-+|_+|0+)$|change.?me|example|sample|placeholder|dummy|your[_-]|<[^>]*>|\$\{|\{\{|%\(|"
    r"^(?:password|secret|token|test|testing|fake|foo|bar|baz|null|none|undefined|redacted|hidden)\w*$|"
    r"^env\(|^os\.environ|^process\.env|xxxx"
)
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg", ".pdf", ".zip", ".gz", ".tgz", ".bz2", ".xz",
    ".7z", ".jar", ".class", ".so", ".dll", ".dylib", ".exe", ".bin", ".woff", ".woff2", ".ttf", ".otf",
    ".eot", ".mp3", ".mp4", ".mov", ".avi", ".lock", ".min.js", ".map", ".sum",
}  # fmt: skip
SKIP_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "Cargo.lock",
    "poetry.lock",
    "uv.lock",
}
MAX_BYTES = 1_000_000


@dataclass(frozen=True)
class SecretFinding:
    path: str
    line: int
    rule: Rule
    masked: str


def mask(value: str) -> str:
    if len(value) <= 8:
        return value[:2] + "…"
    return value[:4] + "…" + value[-2:]


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {ch: value.count(ch) for ch in set(value)}
    return -sum(c / len(value) * math.log2(c / len(value)) for c in counts.values())


def should_scan(path: str) -> bool:
    pure = PurePosixPath(path)
    if pure.name in SKIP_NAMES:
        return False
    lower = pure.name.lower()
    return not any(lower.endswith(suffix) for suffix in SKIP_SUFFIXES)


def scan_text(path: str, text: str, allow_patterns: Iterable[re.Pattern[str]] = ()) -> list[SecretFinding]:
    allow = list(allow_patterns)
    findings: list[SecretFinding] = []
    if "\0" in text[:4096]:
        return findings
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(line) > 2000 or any(marker in line for marker in INLINE_ALLOW):
            continue
        for rule in RULES:
            for match in rule.pattern.finditer(line):
                value = match.group(rule.group)
                if any(a.search(value) or a.search(line) for a in allow):
                    continue
                fuzzy = rule.id in ("generic-secret", "url-credentials")
                if fuzzy and (PLACEHOLDER_RE.search(value) or shannon_entropy(value) < 2.5):
                    continue
                findings.append(SecretFinding(path, lineno, rule, mask(value)))
    return findings
