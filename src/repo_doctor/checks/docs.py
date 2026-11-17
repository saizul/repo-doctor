"""Documentation and community health files."""

from __future__ import annotations

import re

from repo_doctor.licenses import OSI_APPROVED, copyright_line, detect_spdx
from repo_doctor.markdown import headings
from repo_doctor.model import Location, Outcome, Severity, check, failed, passed, warned
from repo_doctor.repo import Repo

README_STEMS = ("README", "readme")
SECTION_SYNONYMS: dict[str, tuple[str, ...]] = {
    "install": ("install", "installation", "installing", "getting started", "quick start", "quickstart", "setup"),
    "usage": ("usage", "how to use", "examples", "example", "getting started", "quick start", "quickstart", "using"),
    "license": ("license", "licence", "licensing", "copyright"),
    "contributing": ("contributing", "contribute", "contribution", "contributions", "development", "hacking"),
}
BADGE_RE = re.compile(
    r"!\[[^\]]*\]\((?:https?://)?[^)]*(?:shields\.io|badge|/badges?/|badgen\.net|codecov\.io|coveralls\.io)[^)]*\)",
    re.IGNORECASE,
)


def find_readme(repo: Repo) -> str | None:
    return repo.find_doc(README_STEMS, dirs=("", ".github", "docs"))


@check(
    "RD001",
    "readme",
    "README is present",
    Severity.HIGH,
    "docs",
    "The README is the front page of the project: what it does, how to install it and how to use it.",
    "Add a README.md with a one-line description, installation, usage, contributing and license sections.",
    fixer="readme",
)
def readme_present(repo: Repo) -> Outcome:
    path = find_readme(repo)
    if not path:
        return failed("No README found in the root, .github/ or docs/")
    text = repo.read_text(path)
    words = len(re.findall(r"\w+", text))
    if words < 30:
        return warned(f"{path} is very short ({words} words)", locations=[Location(path)])
    return passed(f"{path} ({words} words)")


@check(
    "RD002",
    "readme-sections",
    "README covers install, usage, license and contributing",
    Severity.MEDIUM,
    "docs",
    "Visitors decide in seconds whether they can use a project. Clear sections answer the first questions.",
    "Add headings such as '## Installation', '## Usage', '## Contributing' and '## License' to the README.",
)
def readme_sections(repo: Repo) -> Outcome:
    path = find_readme(repo)
    if not path:
        return failed("No README to inspect")
    found = {h.lower().strip(" :") for h in headings(repo.read_text(path))}
    missing = []
    for section in repo.config.readme_sections:
        synonyms = SECTION_SYNONYMS[section]
        if not any(any(re.search(rf"\b{re.escape(s)}\b", h) for s in synonyms) for h in found):
            missing.append(section)
    if not missing:
        return passed(f"{path} has all {len(repo.config.readme_sections)} sections")
    msg = f"{path} is missing: {', '.join(missing)}"
    if len(missing) == 1:
        return warned(msg, locations=[Location(path)])
    return failed(msg, locations=[Location(path)])


@check(
    "RD003",
    "readme-badges",
    "README shows status badges",
    Severity.LOW,
    "docs",
    "Badges for CI, version and license show at a glance that the project is alive and tested.",
    "Add a CI badge at the top of the README; GitHub shows its URL under Actions > workflow > Create status badge.",
)
def readme_badges(repo: Repo) -> Outcome:
    path = find_readme(repo)
    if not path:
        return failed("No README to inspect")
    text = repo.read_text(path)
    badges = BADGE_RE.findall(text) + re.findall(r"<img[^>]+(?:shields\.io|badge)[^>]*>", text, re.IGNORECASE)
    if badges:
        return passed(f"{len(badges)} badge(s) in {path}")
    return failed(f"No badges in {path}", locations=[Location(path)])


LICENSE_STEMS = ("LICENSE", "LICENCE", "COPYING", "LICENSE-MIT", "LICENSE-APACHE", "UNLICENSE")


def find_license(repo: Repo) -> str | None:
    return repo.find_doc(LICENSE_STEMS, dirs=("",))


@check(
    "RD004",
    "license",
    "LICENSE file with a recognised open-source license",
    Severity.HIGH,
    "docs",
    "Without a license nobody may legally use, copy or modify the code. An OSI-approved license makes reuse safe.",
    "Add a LICENSE file; MIT and Apache-2.0 are common permissive choices (see https://choosealicense.com).",
    fixer="license",
)
def license_file(repo: Repo) -> Outcome:
    path = find_license(repo)
    if not path:
        return failed("No LICENSE, LICENCE or COPYING file in the repository root")
    text = repo.read_text(path)
    spdx = detect_spdx(text)
    details = []
    line = copyright_line(text)
    if line:
        details.append(line)
    if spdx is None:
        return warned(f"{path} found, but the license could not be identified", details, [Location(path)])
    if spdx not in OSI_APPROVED and " OR " not in spdx and " AND " not in spdx:
        return warned(f"{path}: {spdx} is not an OSI-approved license", details, [Location(path)])
    if spdx in ("MIT", "BSD-2-Clause", "BSD-3-Clause", "ISC") and line and re.search(r"<|\[|\{", line):
        return warned(f"{path}: {spdx}, but the copyright line still has a placeholder", details, [Location(path)])
    return passed(f"{path}: {spdx}", details)


def _doc_check(repo: Repo, stems: tuple[str, ...], label: str) -> Outcome:
    path = repo.find_doc(stems)
    if not path:
        return failed(f"No {label} found in the root, .github/ or docs/")
    if len(repo.read_text(path).strip()) < 40:
        return warned(f"{path} is nearly empty", locations=[Location(path)])
    return passed(path)


@check(
    "RD005",
    "contributing",
    "CONTRIBUTING guide",
    Severity.MEDIUM,
    "community",
    "A contributing guide tells newcomers how to set up the project, run tests and send a good pull request.",
    "Add CONTRIBUTING.md with development setup, tests, style and pull request steps.",
    fixer="contributing",
)
def contributing(repo: Repo) -> Outcome:
    return _doc_check(repo, ("CONTRIBUTING",), "CONTRIBUTING guide")


@check(
    "RD006",
    "code-of-conduct",
    "Code of conduct",
    Severity.MEDIUM,
    "community",
    "A code of conduct sets expectations for behaviour and explains how problems are reported and handled.",
    "Adopt the Contributor Covenant 2.1 in CODE_OF_CONDUCT.md and name a contact for reports.",
    fixer="code-of-conduct",
)
def code_of_conduct(repo: Repo) -> Outcome:
    return _doc_check(repo, ("CODE_OF_CONDUCT", "CODE-OF-CONDUCT", "CONDUCT"), "code of conduct")


@check(
    "RD007",
    "security-policy",
    "Security policy",
    Severity.MEDIUM,
    "community",
    "A security policy tells researchers how to report vulnerabilities privately instead of in a public issue.",
    "Add SECURITY.md with supported versions and a private reporting channel (e.g. GitHub advisories).",
    fixer="security",
)
def security_policy(repo: Repo) -> Outcome:
    return _doc_check(repo, ("SECURITY",), "SECURITY policy")


@check(
    "RD008",
    "changelog",
    "Changelog",
    Severity.LOW,
    "docs",
    "A changelog lets users see what changed between versions and whether an upgrade is safe.",
    "Add CHANGELOG.md following https://keepachangelog.com and update it with every release.",
    fixer="changelog",
)
def changelog(repo: Repo) -> Outcome:
    path = repo.find_doc(("CHANGELOG", "CHANGES", "HISTORY", "NEWS", "RELEASES"), dirs=("", "docs"))
    if not path:
        return failed("No CHANGELOG, CHANGES, HISTORY or NEWS file")
    return passed(path)
