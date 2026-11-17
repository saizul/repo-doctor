# repo-doctor

[![CI](https://github.com/saizul/repo-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/saizul/repo-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**A health check for open-source repositories.** repo-doctor looks at any Git
repository, scores it from 0 to 100 against 26 best-practice checks (README,
LICENSE, CI, security policy, secrets, broken links, package metadata, ...)
and creates the missing files for you.

```text
$ pipx install git+https://github.com/saizul/repo-doctor
$ repo-doctor check
FAIL  RD004 LICENSE file with a recognised open-source license [high]
      No LICENSE, LICENCE or COPYING file in the repository root
      fix: Add a LICENSE file; MIT and Apache-2.0 are common permissive choices (see https://choosealicense.com).
      auto-fix: repo-doctor fix --only license
FAIL  RD015 No secrets in tracked files [high]
      1 possible secret(s) in 1 file(s)
        - config/settings.py:12 AWS access key ID (AKIA…QA)
...
Score: 41/100  Grade: F   (9 passed, 2 warnings, 10 failed, 5 skipped)

$ repo-doctor fix --author "Jane Doe"
create    LICENSE
create    CONTRIBUTING.md
create    CODE_OF_CONDUCT.md
create    SECURITY.md
create    .github/ISSUE_TEMPLATE/bug_report.yml
...
Score after fixing: 83/100 (grade B). Review the new files before committing.
```

No dependencies besides the Python standard library (plus `tomli` on Python 3.10).
Works offline; GitHub API checks are optional.

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Usage](#usage)
- [Checks](#checks)
- [Configuration](#configuration)
- [GitHub Action](#github-action)
- [Docker image](#docker-image)
- [Examples](#examples)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [Testing](#testing)
- [Security notes](#security-notes)
- [Limitations](#limitations)
- [License](#license)

## Features

- **26 checks** with stable IDs, a severity, an explanation and a fix hint each ([full list](docs/checks.md))
- **Score and grade** (0-100, A-F) weighted by severity, so you can track progress and gate CI with `--fail-under`
- **Language aware**: detects Python, JavaScript/TypeScript, PHP, Go, Rust and Docker and tailors
  `.gitignore`, lockfile, metadata, Dependabot and CI checks
- **`fix` command** scaffolds LICENSE (MIT or Apache-2.0 with your name and year), CONTRIBUTING,
  CODE_OF_CONDUCT (Contributor Covenant 2.1 by reference), SECURITY.md, CHANGELOG, issue forms,
  a pull request template, `dependabot.yml`, `.editorconfig`, `.gitignore`, `.dockerignore` and a starter CI workflow.
  It **never overwrites** existing files unless you pass `--force`
- **Secret scanner** for tracked files (AWS, GitHub, GitLab, Slack, Stripe, Google, npm, PyPI, private keys,
  passwords in URLs, hardcoded passwords) with masking, placeholder filtering and an allowlist
- **Broken relative links** in all Markdown files, including `#heading` anchors
- **Package metadata** for `pyproject.toml`, `package.json`, `composer.json` and `Cargo.toml`
- **Remote checks** (description, topics, homepage, branch protection or rulesets) when `GITHUB_TOKEN` is set
- **Outputs**: coloured text, JSON, Markdown (job summaries) and **SARIF 2.1.0** for GitHub code scanning
- **Reusable GitHub Action** with a job summary, outputs and SARIF, plus pre-commit hooks and a Docker image

## Quick start

```bash
pipx install git+https://github.com/saizul/repo-doctor   # or: pip install git+https://...
cd your-project
repo-doctor check                 # see the score and what is missing
repo-doctor fix --dry-run         # preview the files that would be created
repo-doctor fix --author "Your Name" --email security@example.com
git add -A && git diff --cached   # review, then commit
```

## Usage

### `repo-doctor check [PATH]`

| Option | Description |
| --- | --- |
| `-f, --format text\|json\|markdown\|sarif` | Output format (default: `text`) |
| `-o, --output FILE` | Write the report to a file |
| `--fail-under SCORE` | Exit 1 when the score is below `SCORE` |
| `--fail-on high\|medium\|low` | Exit 1 when a check of that severity or higher fails |
| `--only IDS` / `--skip IDS` | Comma-separated IDs or slugs (`RD015`, `secrets`) |
| `--offline` | Never call the GitHub API |
| `--json-file`, `--sarif-file`, `--markdown-file` | Write extra reports in the same run |
| `--github-summary` | Append Markdown to `$GITHUB_STEP_SUMMARY` and write `score`/`grade` to `$GITHUB_OUTPUT` |
| `-v, --verbose` | Show skipped checks and all details |

Exit codes: `0` success, `1` the `--fail-under` / `--fail-on` gate failed, `2` usage or configuration error.

### `repo-doctor fix [PATH]`

| Option | Description |
| --- | --- |
| `--only NAMES` | Fixers, check IDs or slugs, e.g. `--only license,security,RD021` |
| `--license MIT\|Apache-2.0` | License to create (default: MIT) |
| `--author NAME` | Copyright holder (default: `git config user.name`, then package metadata) |
| `--email ADDRESS` | Contact for SECURITY.md and CODE_OF_CONDUCT.md (default: GitHub private reporting link) |
| `--year YEAR` | Copyright year (default: this year) |
| `--dry-run` | Show what would be written |
| `--force` | Overwrite existing files |

Without `--only`, `fix` runs every fixer whose check currently fails. Fixers:
`readme`, `license`, `contributing`, `code-of-conduct`, `security`, `changelog`,
`editorconfig`, `gitignore` (creates the file or **appends** missing patterns),
`issue-templates`, `pr-template`, `dependabot`, `ci`, `dockerignore`.

### `repo-doctor checks`

Lists every check (`-f json` and `-f markdown` are available too).

## Checks

| ID | Check | Severity | Auto-fix |
| --- | --- | --- | --- |
| RD001 | README is present | high | yes |
| RD002 | README covers install, usage, license and contributing | medium | |
| RD003 | README shows status badges | low | |
| RD004 | LICENSE with a recognised open-source license (SPDX detection) | high | yes |
| RD005 | CONTRIBUTING guide | medium | yes |
| RD006 | Code of conduct | medium | yes |
| RD007 | Security policy | medium | yes |
| RD008 | Changelog | low | yes |
| RD010 | .gitignore is present | medium | yes |
| RD011 | .gitignore covers the detected languages | low | yes |
| RD012 | .editorconfig is present | low | yes |
| RD013 | Dependency lockfile is committed | medium | |
| RD014 | No large files committed (default > 5 MB, Git LFS aware) | medium | |
| RD015 | No secrets in tracked files | high | |
| RD016 | No broken relative links in Markdown | medium | |
| RD020 | Continuous integration is configured | high | yes |
| RD021 | Issue templates | low | yes |
| RD022 | Pull request template | low | yes |
| RD023 | Dependabot or Renovate | medium | yes |
| RD030 | Package metadata is complete | medium | |
| RD040 | GitHub description (needs `GITHUB_TOKEN`) | medium | |
| RD041 | GitHub topics (needs `GITHUB_TOKEN`) | low | |
| RD042 | GitHub homepage URL (needs `GITHUB_TOKEN`) | low | |
| RD043 | Default branch protected or covered by a ruleset (needs `GITHUB_TOKEN`) | medium | |
| RD050 | .dockerignore next to the Dockerfile | low | yes |
| RD051 | Dockerfile base images are pinned | low | |

Explanations and fix hints for every check: [docs/checks.md](docs/checks.md).

**Scoring.** Weights are high = 10, medium = 5, low = 2. A pass earns the full
weight, a warning half of it, a failure nothing; skipped checks (not applicable,
for example Docker checks in a repository without a Dockerfile) do not count.
Grades: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F below.

**Language detection.** A marker file (`pyproject.toml`, `package.json`,
`composer.json`, `go.mod`, `Cargo.toml`, `Dockerfile`, ...) or at least three
source files of a language switch on its rules.

## Configuration

Put a `.repo-doctor.toml` in the repository root, or the same keys under
`[tool.repo-doctor]` in `pyproject.toml`:

```toml
disable = ["RD008", "readme-badges"]     # IDs or slugs
large_file_mb = 10                       # RD014 threshold
fail_under = 80                          # default for --fail-under
readme_sections = ["install", "usage", "license"]
remote = true                            # set false to never call the GitHub API

[secrets]
allow_paths = ["tests/fixtures/**"]
allow_patterns = ["EXAMPLE[A-Z0-9]+"]

[links]
ignore = ["docs/api/**"]
```

Suppress a single secret finding with a comment on the same line:
`# repo-doctor:ignore` (also accepted: `pragma: allowlist secret`, `gitleaks:allow`).

| Environment variable | Meaning |
| --- | --- |
| `GITHUB_TOKEN` / `GH_TOKEN` | Enables the remote checks RD040-RD043 |
| `GITHUB_API_URL` | GitHub Enterprise Server API base URL |
| `NO_COLOR` / `FORCE_COLOR` | Turn colours off or on |

## GitHub Action

```yaml
# .github/workflows/repo-doctor.yml
name: repo-doctor
on: [pull_request]
permissions:
  contents: read
jobs:
  doctor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: saizul/repo-doctor@v0.1.0
        with:
          fail-under: "80"
```

The action writes a Markdown report to the job summary and sets the outputs
`score` and `grade`.

| Input | Default | Description |
| --- | --- | --- |
| `path` | `.` | Folder to check |
| `fail-under` | | Fail below this score |
| `fail-on` | | Fail when a check of this severity or higher fails |
| `only` / `skip` | | Comma-separated IDs or slugs |
| `sarif-file` | | Write SARIF for `github/codeql-action/upload-sarif` |
| `json-file` | | Write a JSON report |
| `remote` | `true` | Run the GitHub API checks with `token` |
| `token` | `${{ github.token }}` | Token for the API checks (branch protection needs admin rights; otherwise it is skipped) |
| `python-version` | `3.12` | Python used to run the tool (installed in its own virtual environment) |

Upload findings to code scanning: see [examples/github-workflow.yml](examples/github-workflow.yml).
Use the tag of a published release (for example `@v0.1.0`) or a commit SHA.

### pre-commit

```yaml
repos:
  - repo: https://github.com/saizul/repo-doctor
    rev: v0.1.0
    hooks:
      - id: repo-doctor-secrets
```

## Docker image

Published to the GitHub Container Registry for `linux/amd64` and `linux/arm64`
on every push to `main` and on releases: `ghcr.io/saizul/repo-doctor`.

```bash
docker run --rm -v "$PWD:/repo:ro" ghcr.io/saizul/repo-doctor                 # check the current folder
docker run --rm -v "$PWD:/repo:ro" ghcr.io/saizul/repo-doctor check . -f json
docker run --rm -v "$PWD:/repo" --user "$(id -u):$(id -g)" ghcr.io/saizul/repo-doctor fix . --dry-run
docker run --rm -e GITHUB_TOKEN -v "$PWD:/repo:ro" ghcr.io/saizul/repo-doctor check . --fail-under 80
```

Tags: `latest` (default branch), the short commit SHA and release versions
(`0.1.0`). The image includes Git, runs as UID 10001 and defaults to
`check .` in `/repo`. Build it locally with `docker build -t repo-doctor .`.

## Examples

- [examples/repo-doctor.toml](examples/repo-doctor.toml): every configuration option
- [examples/github-workflow.yml](examples/github-workflow.yml): action plus code scanning upload
- [examples/pre-commit-config.yaml](examples/pre-commit-config.yaml): pre-commit hooks
- [examples/audit_many_repos.py](examples/audit_many_repos.py): score every repository in a folder with the Python API

```python
from repo_doctor import Repo, run_checks

report = run_checks(Repo("."), remote=False)
print(report.score, report.grade)
for result in report.results:
    if result.status.value == "fail":
        print(result.check.id, result.outcome.message)
```

## Contributing

New checks, better templates and false-positive fixes are very welcome. Every
check is one small function in `src/repo_doctor/checks/`, so adding one is a
good first contribution. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the
step-by-step "Add a new check" guide.

```bash
git clone https://github.com/saizul/repo-doctor && cd repo-doctor
python -m venv .venv && . .venv/bin/activate && pip install -e .[dev]
pytest
```

Look for issues labelled `good first issue`, `false positive` or `new check`.
Please follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## Roadmap

- More languages: Java/Kotlin (Maven, Gradle), Ruby, .NET, Swift
- Checks for `CITATION.cff`, `CODEOWNERS`, `FUNDING.yml`, OpenSSF Scorecard basics, signed releases
- `fix` for README sections and package metadata (with a preview diff)
- Remote checks for GitLab and Gitea
- Scanning Git history for secrets, not only the working tree
- A `--baseline` file to accept known findings

## Testing

```bash
pip install -e .[dev]
pytest                    # 190+ tests on tmp_path fixture repositories, no network needed
ruff check . && ruff format --check .
repo-doctor check . --offline --fail-under 95   # the project checks itself
```

CI runs the test-suite on Python 3.10-3.13, runs the action against this
repository, verifies `docs/checks.md` is current and builds the Docker image.

## Security notes

- repo-doctor only reads files, except `fix`, which creates new files (and
  appends to `.gitignore`). Use `--dry-run` first.
- Secret findings are masked in all outputs (`AKIA…QA`). The scanner never sends
  data anywhere. Remote checks only call the GitHub REST API with your token.
- A secret scanner with a small rule set will miss things. Use a dedicated tool
  such as gitleaks or GitHub secret scanning for full coverage, and **revoke**
  any credential that was ever committed.
- Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Limitations

- Checks are heuristics. A README with unusual headings or a heavily modified
  license text may be reported incorrectly; disable the check or open a
  false-positive issue.
- License detection uses phrase fingerprints for common licenses and
  `SPDX-License-Identifier` headers, not a full text comparison.
- Secret scanning covers the current tracked files, not Git history.
- Branch protection needs a token with admin access; with the default Actions
  token the check is skipped unless rulesets are in use.
- The generated code of conduct adopts the Contributor Covenant by reference
  (link plus summary) instead of copying its full text.

## License

[MIT](LICENSE) © 2026 Saizul Amin
