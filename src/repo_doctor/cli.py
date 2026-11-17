"""Command line interface: ``repo-doctor check | fix | checks``."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from repo_doctor._version import __version__
from repo_doctor.config import ConfigError
from repo_doctor.engine import Report, run_checks
from repo_doctor.fix import LICENSES, FixError, apply_fixes, available_fixers
from repo_doctor.model import Severity, all_checks
from repo_doctor.output import FORMATS, render, render_json, render_markdown, render_sarif, use_color
from repo_doctor.repo import LANGUAGE_LABELS, Repo

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


def _csv(values: list[str] | None) -> list[str]:
    out: list[str] = []
    for value in values or []:
        out.extend(v.strip() for v in value.split(",") if v.strip())
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-doctor",
        description="Check a repository for open-source best practices and scaffold what is missing.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("check", help="run the checks and print a report with a 0-100 score")
    p.add_argument("path", nargs="?", default=".", help="repository folder (default: current directory)")
    p.add_argument("-f", "--format", choices=sorted(FORMATS), default="text")
    p.add_argument("-o", "--output", metavar="FILE", help="write the report to FILE instead of stdout")
    p.add_argument("--fail-under", type=float, metavar="SCORE", help="exit 1 when the score is below SCORE")
    p.add_argument(
        "--fail-on",
        choices=[s.value for s in Severity],
        help="exit 1 when a check of this severity (or higher) fails",
    )
    p.add_argument(
        "--only", action="append", metavar="IDS", help="run only these checks (IDs or slugs, comma-separated)"
    )
    p.add_argument("--skip", action="append", metavar="IDS", help="skip these checks (IDs or slugs, comma-separated)")
    p.add_argument("--offline", action="store_true", help="never call the GitHub API")
    p.add_argument("--json-file", metavar="FILE", help="also write a JSON report")
    p.add_argument("--sarif-file", metavar="FILE", help="also write a SARIF 2.1.0 report (GitHub code scanning)")
    p.add_argument("--markdown-file", metavar="FILE", help="also write a Markdown report")
    p.add_argument("--github-summary", action="store_true", help="append a Markdown report to $GITHUB_STEP_SUMMARY")
    p.add_argument("--no-color", action="store_true", help="disable colours")
    p.add_argument("-v", "--verbose", action="store_true", help="show skipped checks and all details")

    p = sub.add_parser("fix", help="create missing community files from templates")
    p.add_argument("path", nargs="?", default=".", help="repository folder (default: current directory)")
    p.add_argument(
        "--only",
        action="append",
        metavar="NAMES",
        help=f"fixers, check IDs or slugs (comma-separated). Fixers: {', '.join(available_fixers())}",
    )
    p.add_argument("--force", action="store_true", help="overwrite existing files")
    p.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    p.add_argument("--license", dest="license_id", choices=sorted(LICENSES), default="MIT", help="license to create")
    p.add_argument("--author", help="copyright holder (default: git user.name or package metadata)")
    p.add_argument("--email", help="contact address for SECURITY.md and CODE_OF_CONDUCT.md")
    p.add_argument("--year", type=int, help="copyright year (default: current year)")

    p = sub.add_parser("checks", help="list all checks")
    p.add_argument("-f", "--format", choices=["table", "json", "markdown"], default="table")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return EXIT_USAGE
    try:
        if args.command == "check":
            return cmd_check(args)
        if args.command == "fix":
            return cmd_fix(args)
        return cmd_checks(args)
    except (ConfigError, FixError, NotADirectoryError) as exc:
        print(f"repo-doctor: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except KeyError as exc:
        print(f"repo-doctor: error: unknown check {exc}. Run 'repo-doctor checks' for the list.", file=sys.stderr)
        return EXIT_USAGE


def _write_file(path: str, content: str) -> None:
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")


def cmd_check(args: argparse.Namespace) -> int:
    repo = Repo(args.path)
    report = run_checks(repo, only=_csv(args.only), skip=_csv(args.skip), remote=not args.offline)
    text = render(
        report, args.format, color=use_color() and not args.no_color and not args.output, verbose=args.verbose
    )
    if args.output:
        _write_file(args.output, text)
    else:
        print(text)
    if args.json_file:
        _write_file(args.json_file, render_json(report))
    if args.sarif_file:
        _write_file(args.sarif_file, render_sarif(report))
    if args.markdown_file:
        _write_file(args.markdown_file, render_markdown(report))
    if args.github_summary and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(render_markdown(report) + "\n")
    if os.environ.get("GITHUB_OUTPUT") and args.github_summary:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"score={report.score}\ngrade={report.grade}\n")
    return _exit_code(report, args, repo)


def _exit_code(report: Report, args: argparse.Namespace, repo: Repo) -> int:
    threshold = args.fail_under if args.fail_under is not None else repo.config.fail_under
    reasons = []
    if threshold is not None and report.score < threshold:
        reasons.append(f"score {report.score} is below {threshold:g}")
    if args.fail_on:
        failing = report.failing_at_or_above(Severity(args.fail_on))
        if failing:
            reasons.append(f"{len(failing)} failed check(s) at severity {args.fail_on} or higher")
    if reasons:
        print(f"repo-doctor: {'; '.join(reasons)}", file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


def cmd_fix(args: argparse.Namespace) -> int:
    repo = Repo(args.path)
    actions = apply_fixes(
        repo,
        _csv(args.only) or None,
        force=args.force,
        dry_run=args.dry_run,
        license_id=args.license_id,
        author=args.author,
        email=args.email,
        year=args.year,
    )
    prefix = "[dry-run] " if args.dry_run else ""
    if not actions:
        print("Nothing to fix: every check with an automatic fix already passes.")
        return EXIT_OK
    langs = ", ".join(LANGUAGE_LABELS[lang] for lang in repo.languages) or "none detected"
    print(f"{prefix}repo-doctor fix in {repo.root} (languages: {langs})")
    for action in actions:
        reason = f"  ({action.reason})" if action.reason else ""
        print(f"{prefix}{action.action:<9} {action.path}{reason}")
    changed = [a for a in actions if a.changed]
    if changed and not args.dry_run:
        after = run_checks(Repo(args.path), remote=False)
        print(f"\nScore after fixing: {after.score}/100 (grade {after.grade}). Review the new files before committing.")
    return EXIT_OK


def cmd_checks(args: argparse.Namespace) -> int:
    infos = all_checks()
    if args.format == "json":
        print(json.dumps([i.to_dict() for i in infos], indent=2))
    elif args.format == "markdown":
        print(checks_markdown())
    else:
        width = max(len(i.slug) for i in infos)
        for info in infos:
            fix = "fix" if info.fixer else "   "
            scope = "remote" if info.remote else ("/".join(info.languages) if info.languages else "")
            print(f"{info.id}  {info.slug:<{width}}  {info.severity.value:<6}  {fix}  {info.title} {scope}".rstrip())
    return EXIT_OK


def checks_markdown() -> str:
    infos = all_checks()
    lines = [
        "# Checks",
        "",
        "Every check has a stable ID. Use IDs or slugs with `--only`, `--skip` and `disable` in the config.",
        "Severity weights for the score: high 10, medium 5, low 2. A warning earns half the weight.",
        "",
        "| ID | Slug | Severity | Category | Auto-fix | Title |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for i in infos:
        fixer = f"`{i.fixer}`" if i.fixer else ""
        lines.append(
            f"| [{i.id}](#{i.id.lower()}) | `{i.slug}` | {i.severity.value} | {i.category} | {fixer} | {i.title} |"
        )
    for i in infos:
        lines += ["", f'<a id="{i.id.lower()}"></a>', "", f"## {i.id} {i.title}", ""]
        meta = f"**Slug:** `{i.slug}` · **Severity:** {i.severity.value} · **Category:** {i.category}"
        if i.languages:
            meta += f" · **Applies to:** {', '.join(LANGUAGE_LABELS[lang] for lang in i.languages)}"
        if i.remote:
            meta += " · **Needs:** `GITHUB_TOKEN`"
        lines += [meta, "", i.explanation, "", f"**How to fix:** {i.fix_hint}"]
        if i.fixer:
            lines += ["", f"Auto-fix: `repo-doctor fix --only {i.fixer}`"]
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
