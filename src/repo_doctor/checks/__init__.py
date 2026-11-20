"""Importing this package registers every built-in check."""

from repo_doctor.checks import ci, codeowners, docs, hygiene, links, metadata, remote, security

__all__ = ["ci", "codeowners", "docs", "hygiene", "links", "metadata", "remote", "security"]
