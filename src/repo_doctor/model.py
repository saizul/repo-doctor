"""Core data model: check metadata, results and the check registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from repo_doctor.repo import Repo


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def weight(self) -> int:
        return {"high": 10, "medium": 5, "low": 2}[self.value]

    @property
    def rank(self) -> int:
        return {"high": 3, "medium": 2, "low": 1}[self.value]


class Status(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass(frozen=True)
class Location:
    path: str
    line: int | None = None

    def __str__(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path


@dataclass(frozen=True)
class CheckInfo:
    id: str
    slug: str
    title: str
    severity: Severity
    category: str
    explanation: str
    fix_hint: str
    languages: tuple[str, ...] = ()
    fixer: str | None = None
    remote: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "severity": self.severity.value,
            "category": self.category,
            "explanation": self.explanation,
            "fix_hint": self.fix_hint,
            "languages": list(self.languages),
            "fixer": self.fixer,
            "remote": self.remote,
        }


@dataclass
class Outcome:
    """What a check function returns."""

    status: Status
    message: str
    details: list[str] = field(default_factory=list)
    locations: list[Location] = field(default_factory=list)


def passed(message: str, details: list[str] | None = None) -> Outcome:
    return Outcome(Status.PASS, message, details or [])


def failed(message: str, details: list[str] | None = None, locations: list[Location] | None = None) -> Outcome:
    return Outcome(Status.FAIL, message, details or [], locations or [])


def warned(message: str, details: list[str] | None = None, locations: list[Location] | None = None) -> Outcome:
    return Outcome(Status.WARN, message, details or [], locations or [])


def skipped(message: str) -> Outcome:
    return Outcome(Status.SKIP, message)


@dataclass
class Result:
    check: CheckInfo
    outcome: Outcome

    @property
    def status(self) -> Status:
        return self.outcome.status

    @property
    def counts_against(self) -> bool:
        return self.status in (Status.FAIL, Status.WARN)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check.id,
            "slug": self.check.slug,
            "title": self.check.title,
            "severity": self.check.severity.value,
            "category": self.check.category,
            "status": self.status.value,
            "message": self.outcome.message,
            "details": self.outcome.details,
            "locations": [{"path": loc.path, "line": loc.line} for loc in self.outcome.locations],
            "fix_hint": self.check.fix_hint,
            "fixable": self.check.fixer is not None,
        }


CheckFunc = Callable[["Repo"], Outcome]
REGISTRY: dict[str, tuple[CheckInfo, CheckFunc]] = {}


def check(
    id: str,
    slug: str,
    title: str,
    severity: Severity,
    category: str,
    explanation: str,
    fix_hint: str,
    *,
    languages: tuple[str, ...] = (),
    fixer: str | None = None,
    remote: bool = False,
) -> Callable[[CheckFunc], CheckFunc]:
    """Register a check function under a stable ID."""

    info = CheckInfo(id, slug, title, severity, category, explanation, fix_hint, languages, fixer, remote)

    def decorator(func: CheckFunc) -> CheckFunc:
        if id in REGISTRY:
            raise ValueError(f"duplicate check id {id}")
        if any(existing.slug == slug for existing, _ in REGISTRY.values()):
            raise ValueError(f"duplicate check slug {slug}")
        REGISTRY[id] = (info, func)
        return func

    return decorator


def all_checks() -> list[CheckInfo]:
    from repo_doctor import checks  # noqa: F401 - importing registers every check

    return [info for info, _ in sorted(REGISTRY.values(), key=lambda item: item[0].id)]


def resolve(names: list[str]) -> list[CheckInfo]:
    """Resolve IDs, slugs or fixer names (case-insensitive) to checks."""

    infos = all_checks()
    out: list[CheckInfo] = []
    for raw in names:
        key = raw.strip().lower()
        matches = [i for i in infos if key in (i.id.lower(), i.slug, (i.fixer or "").lower())]
        if not matches:
            raise KeyError(raw)
        for match in matches:
            if match not in out:
                out.append(match)
    return out
