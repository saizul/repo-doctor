# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-17

### Added

- `repo-doctor check` with 26 checks (`RD001`-`RD051`): README presence, sections
  and badges; LICENSE with SPDX detection; CONTRIBUTING, CODE_OF_CONDUCT,
  SECURITY and CHANGELOG; `.gitignore` per language; `.editorconfig`; lockfiles;
  large files (Git LFS aware); secrets in tracked files; broken relative Markdown
  links and anchors; CI; issue and pull request templates; Dependabot/Renovate;
  package metadata for pyproject.toml, package.json, composer.json and Cargo.toml;
  `.dockerignore` and pinned Docker base images.
- Optional GitHub API checks (description, topics, homepage, branch protection
  or rulesets) when `GITHUB_TOKEN` or `GH_TOKEN` is set.
- Language detection for Python, JavaScript/TypeScript, PHP, Go, Rust and Docker.
- Score (0-100) and grade (A-F), `--fail-under` and `--fail-on` gates.
- Text, JSON, Markdown and SARIF 2.1.0 output; GitHub job summary and outputs.
- `repo-doctor fix` with 13 fixers and bundled templates (MIT and Apache-2.0
  licenses, Contributor Covenant 2.1 by reference, security policy, issue forms,
  pull request template, Dependabot, CI starters for five ecosystems).
- Configuration through `.repo-doctor.toml` or `[tool.repo-doctor]`.
- Composite GitHub Action, pre-commit hooks and a container image on
  `ghcr.io/saizul/repo-doctor`.

[Unreleased]: https://github.com/saizul/repo-doctor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/saizul/repo-doctor/releases/tag/v0.1.0
