"""Run checks against a repository and compute the score."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repo_doctor._version import __version__
from repo_doctor.model import REGISTRY, CheckInfo, Outcome, Result, Severity, Status, all_checks, resolve
from repo_doctor.repo import LANGUAGE_LABELS, Repo

GRADES = ((90, "A"), (80, "B"), (70, "C"), (60, "D"), (0, "F"))


@dataclass
class Report:
    repo: Repo
    results: list[Result] = field(default_factory=list)

    @property
    def scored(self) -> list[Result]:
        return [r for r in self.results if r.status not in (Status.SKIP, Status.ERROR)]

    @property
    def score(self) -> int:
        total = sum(r.check.severity.weight for r in self.scored)
        if total == 0:
            return 100
        earned = 0.0
        for r in self.scored:
            if r.status == Status.PASS:
                earned += r.check.severity.weight
            elif r.status == Status.WARN:
                earned += r.check.severity.weight / 2
        return round(100 * earned / total)

    @property
    def grade(self) -> str:
        return grade_for(self.score)

    def by_status(self, *statuses: Status) -> list[Result]:
        return [r for r in self.results if r.status in statuses]

    def failing_at_or_above(self, severity: Severity) -> list[Result]:
        return [r for r in self.by_status(Status.FAIL) if r.check.severity.rank >= severity.rank]

    def summary(self) -> dict[str, int]:
        return {status.value: len(self.by_status(status)) for status in Status}

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": "repo-doctor",
            "version": __version__,
            "path": str(self.repo.root),
            "project": self.repo.project_name,
            "languages": [LANGUAGE_LABELS[lang] for lang in self.repo.languages],
            "score": self.score,
            "grade": self.grade,
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.results],
        }


def grade_for(score: int) -> str:
    for threshold, letter in GRADES:
        if score >= threshold:
            return letter
    return "F"  # pragma: no cover


def select_checks(repo: Repo, only: list[str] | None = None, skip: list[str] | None = None) -> list[CheckInfo]:
    infos = resolve(only) if only else all_checks()
    excluded = set()
    for name in [*repo.config.disable, *(skip or [])]:
        try:
            excluded.update(i.id for i in resolve([name]))
        except KeyError:
            continue
    return [i for i in infos if i.id not in excluded]


def run_checks(
    repo: Repo,
    only: list[str] | None = None,
    skip: list[str] | None = None,
    *,
    remote: bool = True,
) -> Report:
    report = Report(repo)
    for info in select_checks(repo, only, skip):
        func = REGISTRY[info.id][1]
        if info.remote and not remote:
            outcome = Outcome(Status.SKIP, "Remote checks disabled (--offline)")
        elif info.languages and not repo.has_language(*info.languages):
            labels = "/".join(LANGUAGE_LABELS[lang] for lang in info.languages)
            outcome = Outcome(Status.SKIP, f"Not a {labels} project")
        else:
            try:
                outcome = func(repo)
            except Exception as exc:  # a broken check must not break the whole run
                outcome = Outcome(Status.ERROR, f"Check crashed: {type(exc).__name__}: {exc}")
        report.results.append(Result(info, outcome))
    return report
