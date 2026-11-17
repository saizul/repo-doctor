"""Possible secrets in tracked files."""

from __future__ import annotations

import re

from repo_doctor.model import Location, Outcome, Severity, check, failed, passed
from repo_doctor.repo import Repo, matches_any
from repo_doctor.scanner import scan_text, should_scan


@check(
    "RD015",
    "secrets",
    "No secrets in tracked files",
    Severity.HIGH,
    "security",
    "Tokens, keys and passwords in Git history are found by bots within minutes and stay in history after deletion.",
    "Revoke the credential, remove it from history (git filter-repo) and load it from the environment instead. "
    "Mark false positives with 'repo-doctor:ignore' or [secrets] allow_paths.",
)
def secrets(repo: Repo) -> Outcome:
    allow = [re.compile(p) for p in repo.config.secret_allow_patterns]
    files = sorted(repo.tracked) if repo.tracked is not None else repo.files
    findings = []
    for rel in files:
        if not should_scan(rel) or matches_any(rel, repo.config.secret_allow_paths):
            continue
        text = repo.read_text(rel, limit=1_000_000)
        if text:
            findings.extend(scan_text(rel, text, allow))
    if not findings:
        return passed(f"No secret patterns in {len(files)} file(s)")
    details = [f"{f.path}:{f.line} {f.rule.title} ({f.masked})" for f in findings[:50]]
    if len(findings) > 50:
        details.append(f"... and {len(findings) - 50} more")
    return failed(
        f"{len(findings)} possible secret(s) in {len({f.path for f in findings})} file(s)",
        details,
        [Location(f.path, f.line) for f in findings[:50]],
    )
