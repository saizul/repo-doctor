"""Audit every Git repository below a folder and print a score table.

python examples/audit_many_repos.py ~/code
"""

from __future__ import annotations

import sys
from pathlib import Path

from repo_doctor import Repo, run_checks


def main(base: str) -> int:
    rows = []
    for git_dir in sorted(Path(base).expanduser().glob("*/.git")):
        repo = Repo(git_dir.parent)
        report = run_checks(repo, remote=False)
        failed = [r.check.id for r in report.results if r.status.value == "fail"]
        rows.append((report.score, report.grade, repo.root.name, ", ".join(failed[:6])))
    for score, grade, name, failed in sorted(rows):
        print(f"{score:>3} {grade}  {name:<30} {failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
