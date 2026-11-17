"""Report formatters: text, JSON, Markdown (job summaries) and SARIF 2.1.0."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from repo_doctor._version import __version__
from repo_doctor.engine import Report
from repo_doctor.model import Result, Severity, Status, all_checks

ICONS = {
    Status.PASS: ("PASS", "\033[32m"),
    Status.WARN: ("WARN", "\033[33m"),
    Status.FAIL: ("FAIL", "\033[31m"),
    Status.SKIP: ("SKIP", "\033[90m"),
    Status.ERROR: ("ERR ", "\033[35m"),
}
MD_ICONS = {Status.PASS: "✅", Status.WARN: "⚠️", Status.FAIL: "❌", Status.SKIP: "⏭️", Status.ERROR: "💥"}
RESET = "\033[0m"
HOMEPAGE = "https://github.com/saizul/repo-doctor"


def use_color(stream: Any = None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


def _sorted(results: list[Result]) -> list[Result]:
    order = {Status.FAIL: 0, Status.ERROR: 1, Status.WARN: 2, Status.PASS: 3, Status.SKIP: 4}
    return sorted(results, key=lambda r: (order[r.status], -r.check.severity.rank, r.check.id))


def render_text(report: Report, *, color: bool = False, verbose: bool = False) -> str:
    repo = report.repo
    langs = ", ".join(report.to_dict()["languages"]) or "none detected"
    lines = [f"repo-doctor {__version__}: {repo.project_name} ({repo.root})", f"Languages: {langs}", ""]
    for result in _sorted(report.results):
        if result.status == Status.SKIP and not verbose:
            continue
        label, ansi = ICONS[result.status]
        tag = f"{ansi}{label}{RESET}" if color else label
        sev = result.check.severity.value
        lines.append(f"{tag}  {result.check.id} {result.check.title} [{sev}]")
        lines.append(f"      {result.outcome.message}")
        if result.status in (Status.FAIL, Status.WARN, Status.ERROR) or verbose:
            for detail in result.outcome.details[: (50 if verbose else 5)]:
                lines.append(f"        - {detail}")
            if len(result.outcome.details) > 5 and not verbose:
                lines.append(f"        - ... {len(result.outcome.details) - 5} more (use -v)")
        if result.status in (Status.FAIL, Status.WARN):
            lines.append(f"      fix: {result.check.fix_hint}")
            if result.check.fixer:
                lines.append(f"      auto-fix: repo-doctor fix --only {result.check.fixer}")
    summary = report.summary()
    lines.append("")
    lines.append(
        f"Score: {report.score}/100  Grade: {report.grade}   "
        f"({summary['pass']} passed, {summary['warn']} warnings, {summary['fail']} failed, {summary['skip']} skipped)"
    )
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2)


def render_markdown(report: Report, *, title: str = "Repository health") -> str:
    summary = report.summary()
    out = [
        f"## {title}: {report.score}/100 (grade {report.grade})",
        "",
        f"**{report.repo.project_name}** - {summary['pass']} passed, {summary['warn']} warnings, "
        f"{summary['fail']} failed, {summary['skip']} skipped.",
        "",
        "| | Check | Severity | Result |",
        "| --- | --- | --- | --- |",
    ]
    for result in _sorted(report.results):
        if result.status == Status.SKIP:
            continue
        message = result.outcome.message.replace("|", "\\|")
        out.append(
            f"| {MD_ICONS[result.status]} | `{result.check.id}` {result.check.title} | "
            f"{result.check.severity.value} | {message} |"
        )
    problems = [r for r in _sorted(report.results) if r.status in (Status.FAIL, Status.WARN)]
    if problems:
        out += ["", "### How to fix", ""]
        for result in problems:
            auto = f" Auto-fix: `repo-doctor fix --only {result.check.fixer}`." if result.check.fixer else ""
            out.append(f"- **{result.check.id} {result.check.title}**: {result.check.fix_hint}{auto}")
            for detail in result.outcome.details[:5]:
                out.append(f"  - `{detail}`")
    skipped = report.by_status(Status.SKIP)
    if skipped:
        out += ["", "<details><summary>Skipped checks</summary>", ""]
        out += [f"- `{r.check.id}` {r.check.title}: {r.outcome.message}" for r in skipped]
        out += ["", "</details>"]
    out += ["", f"<sub>[repo-doctor]({HOMEPAGE}) {__version__}</sub>", ""]
    return "\n".join(out)


SARIF_LEVEL = {Severity.HIGH: "error", Severity.MEDIUM: "warning", Severity.LOW: "note"}


def render_sarif(report: Report) -> str:
    rules = []
    index: dict[str, int] = {}
    for i, info in enumerate(all_checks()):
        index[info.id] = i
        rules.append(
            {
                "id": info.id,
                "name": info.slug,
                "shortDescription": {"text": info.title},
                "fullDescription": {"text": info.explanation},
                "help": {"text": info.fix_hint, "markdown": info.fix_hint},
                "helpUri": f"{HOMEPAGE}/blob/main/docs/checks.md#{info.id.lower()}",
                "defaultConfiguration": {"level": SARIF_LEVEL[info.severity]},
                "properties": {"tags": [info.category], "security-severity": _security_severity(info.severity)}
                if info.category == "security"
                else {"tags": [info.category]},
            }
        )
    results = []
    for result in report.results:
        if result.status not in (Status.FAIL, Status.WARN):
            continue
        level = SARIF_LEVEL[result.check.severity] if result.status == Status.FAIL else "note"
        message = result.outcome.message
        if result.outcome.details:
            message += "\n" + "\n".join(f"- {d}" for d in result.outcome.details[:20])
        locations = result.outcome.locations or []
        sarif_locations = []
        for loc in locations[:20]:
            physical: dict[str, Any] = {"artifactLocation": {"uri": loc.path, "uriBaseId": "%SRCROOT%"}}
            if loc.line:
                physical["region"] = {"startLine": loc.line}
            sarif_locations.append({"physicalLocation": physical})
        if not sarif_locations:
            sarif_locations.append({"physicalLocation": {"artifactLocation": {"uri": ".", "uriBaseId": "%SRCROOT%"}}})
        results.append(
            {
                "ruleId": result.check.id,
                "ruleIndex": index.get(result.check.id, 0),
                "level": level,
                "message": {"text": message},
                "locations": sarif_locations,
                "partialFingerprints": {"repoDoctor/v1": f"{result.check.id}:{result.outcome.message}"},
            }
        )
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "repo-doctor",
                        "version": __version__,
                        "informationUri": HOMEPAGE,
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {"score": report.score, "grade": report.grade},
            }
        ],
    }
    return json.dumps(sarif, indent=2)


def _security_severity(severity: Severity) -> str:
    return {"high": "8.0", "medium": "5.0", "low": "2.0"}[severity.value]


FORMATS = {"text", "json", "markdown", "sarif"}


def render(report: Report, fmt: str, *, color: bool = False, verbose: bool = False) -> str:
    if fmt == "json":
        return render_json(report)
    if fmt == "markdown":
        return render_markdown(report)
    if fmt == "sarif":
        return render_sarif(report)
    return render_text(report, color=color, verbose=verbose)
