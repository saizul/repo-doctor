"""Importing this package registers every built-in check."""

from repo_doctor.checks import ci, docs, hygiene, links, metadata, remote, security

__all__ = ["ci", "docs", "hygiene", "links", "metadata", "remote", "security"]
