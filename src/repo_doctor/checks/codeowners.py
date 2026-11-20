"""CODEOWNERS: syntax GitHub accepts, valid owners and patterns that match files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from repo_doctor.model import Location, Outcome, Severity, check, failed, passed, skipped, warned
from repo_doctor.repo import Repo

# GitHub reads the first of these and ignores the others.
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")

OWNER_RE = re.compile(
    r"^(?:@[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?"
    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$"
)


@dataclass(frozen=True)
class Rule:
    line: int
    pattern: str
    owners: tuple[str, ...]


@dataclass
class ParsedCodeowners:
    rules: list[Rule] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)


def _split(line: str) -> list[str]:
    """Split a CODEOWNERS line into tokens, honouring ``\\ `` and ``\\#`` escapes and ``#`` comments."""

    tokens: list[str] = []
    current: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] in " #":
            current.append(line[i + 1])
            i += 2
            continue
        if ch == "#":
            break
        if ch in " \t":
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
        i += 1
    if current:
        tokens.append("".join(current))
    return tokens


def parse_codeowners(text: str) -> ParsedCodeowners:
    parsed = ParsedCodeowners()
    for number, raw in enumerate(text.splitlines(), start=1):
        tokens = _split(raw)
        if not tokens:
            continue
        pattern, owners = tokens[0], tuple(tokens[1:])
        if pattern.startswith("!"):
            parsed.errors.append((number, f"negated pattern {pattern!r} is not supported by CODEOWNERS"))
            continue
        if "[" in pattern or "]" in pattern:
            parsed.errors.append((number, f"character ranges in {pattern!r} are not supported by CODEOWNERS"))
            continue
        bad = [o for o in owners if not OWNER_RE.match(o)]
        if bad:
            parsed.errors.append((number, f"invalid owner(s) {', '.join(bad)} (use @user, @org/team or an email)"))
            continue
        parsed.rules.append(Rule(number, pattern, owners))
    return parsed


def pattern_regex(pattern: str) -> re.Pattern[str]:
    """Translate a CODEOWNERS (gitignore-style) pattern into a regex over POSIX paths."""

    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    directory = pattern.endswith("/")
    body = pattern.strip("/")
    out: list[str] = []
    i = 0
    while i < len(body):
        if body.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif body.startswith("**", i):
            out.append(".*")
            i += 2
        elif body[i] == "*":
            out.append("[^/]*")
            i += 1
        elif body[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(body[i]))
            i += 1
    prefix = "^" if anchored else "^(?:.*/)?"
    if directory:
        suffix = "/.*$"
    elif body.endswith("*") and not body.endswith("**") and "/" in body:
        suffix = "$"  # GitHub: "docs/*" owns docs/a.md but not docs/sub/b.md
    else:
        suffix = "(?:/.*)?$"  # a file, or a directory and everything below it
    return re.compile(prefix + "".join(out) + suffix)


def matches(pattern: str, path: str) -> bool:
    if pattern in ("*", "**", "/**"):
        return True
    return bool(pattern_regex(pattern).match(path))


@check(
    "RD024",
    "codeowners",
    "CODEOWNERS is valid",
    Severity.LOW,
    "community",
    "GitHub silently ignores CODEOWNERS lines it cannot parse, so review requests and required code-owner reviews "
    "stop working without any warning. Patterns that match no file usually point at renamed or deleted paths.",
    "Fix the reported lines: owners must be @user, @org/team or an email; CODEOWNERS does not support '!' or "
    "'[...]'. Keep a single CODEOWNERS file (.github/ takes precedence) and update stale paths.",
)
def codeowners(repo: Repo) -> Outcome:
    found = [p for p in (repo.find([c]) for c in CODEOWNERS_PATHS) if p]
    if not found:
        return skipped("No CODEOWNERS file (optional)")
    path = found[0]
    text = repo.read_text(path)
    parsed = parse_codeowners(text)
    details = [f"{path}:{line} {message}" for line, message in parsed.errors]
    locations = [Location(path, line) for line, _ in parsed.errors]
    if parsed.errors:
        return failed(f"{len(parsed.errors)} invalid line(s) in {path}", details[:50], locations[:50])

    problems: list[str] = []
    warn_locations: list[Location] = []
    if len(found) > 1:
        problems.append(f"GitHub only reads {path}; {', '.join(found[1:])} is ignored")
        warn_locations.extend(Location(p) for p in found[1:])
    files = repo.files
    for rule in parsed.rules:
        if not any(matches(rule.pattern, f) for f in files):
            problems.append(f"{path}:{rule.line} pattern {rule.pattern!r} matches no file")
            warn_locations.append(Location(path, rule.line))
    if not parsed.rules:
        return warned(f"{path} has no rules", [], [Location(path)])
    if problems:
        return warned(f"{len(problems)} problem(s) in {path}", problems[:50], warn_locations[:50])
    return passed(f"{len(parsed.rules)} rule(s) in {path}")
