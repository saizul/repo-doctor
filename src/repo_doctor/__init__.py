"""repo-doctor: check a repository for open-source best practices and fix what is missing."""

from repo_doctor._version import __version__
from repo_doctor.engine import Report, run_checks
from repo_doctor.fix import apply_fixes
from repo_doctor.repo import Repo

__all__ = ["Report", "Repo", "__version__", "apply_fixes", "run_checks"]
