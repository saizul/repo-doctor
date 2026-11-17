# Checks

Every check has a stable ID. Use IDs or slugs with `--only`, `--skip` and `disable` in the config.
Severity weights for the score: high 10, medium 5, low 2. A warning earns half the weight.

| ID | Slug | Severity | Category | Auto-fix | Title |
| --- | --- | --- | --- | --- | --- |
| [RD001](#rd001) | `readme` | high | docs | `readme` | README is present |
| [RD002](#rd002) | `readme-sections` | medium | docs |  | README covers install, usage, license and contributing |
| [RD003](#rd003) | `readme-badges` | low | docs |  | README shows status badges |
| [RD004](#rd004) | `license` | high | docs | `license` | LICENSE file with a recognised open-source license |
| [RD005](#rd005) | `contributing` | medium | community | `contributing` | CONTRIBUTING guide |
| [RD006](#rd006) | `code-of-conduct` | medium | community | `code-of-conduct` | Code of conduct |
| [RD007](#rd007) | `security-policy` | medium | community | `security` | Security policy |
| [RD008](#rd008) | `changelog` | low | docs | `changelog` | Changelog |
| [RD010](#rd010) | `gitignore` | medium | hygiene | `gitignore` | .gitignore is present |
| [RD011](#rd011) | `gitignore-languages` | low | hygiene | `gitignore` | .gitignore covers the detected languages |
| [RD012](#rd012) | `editorconfig` | low | hygiene | `editorconfig` | .editorconfig is present |
| [RD013](#rd013) | `lockfile` | medium | hygiene |  | Dependency lockfile is committed |
| [RD014](#rd014) | `large-files` | medium | hygiene |  | No large files committed |
| [RD015](#rd015) | `secrets` | high | security |  | No secrets in tracked files |
| [RD016](#rd016) | `markdown-links` | medium | docs |  | No broken relative links in Markdown |
| [RD020](#rd020) | `ci` | high | ci | `ci` | Continuous integration is configured |
| [RD021](#rd021) | `issue-templates` | low | community | `issue-templates` | Issue templates |
| [RD022](#rd022) | `pr-template` | low | community | `pr-template` | Pull request template |
| [RD023](#rd023) | `dependency-updates` | medium | security | `dependabot` | Automated dependency updates (Dependabot or Renovate) |
| [RD030](#rd030) | `package-metadata` | medium | metadata |  | Package metadata is complete |
| [RD040](#rd040) | `github-description` | medium | metadata |  | GitHub repository has a description |
| [RD041](#rd041) | `github-topics` | low | metadata |  | GitHub repository has topics |
| [RD042](#rd042) | `github-homepage` | low | metadata |  | GitHub repository has a homepage URL |
| [RD043](#rd043) | `branch-protection` | medium | security |  | Default branch is protected |
| [RD050](#rd050) | `dockerignore` | low | docker | `dockerignore` | .dockerignore next to the Dockerfile |
| [RD051](#rd051) | `docker-base-pinned` | low | docker |  | Dockerfile base images are pinned |

<a id="rd001"></a>

## RD001 README is present

**Slug:** `readme` · **Severity:** high · **Category:** docs

The README is the front page of the project: what it does, how to install it and how to use it.

**How to fix:** Add a README.md with a one-line description, installation, usage, contributing and license sections.

Auto-fix: `repo-doctor fix --only readme`

<a id="rd002"></a>

## RD002 README covers install, usage, license and contributing

**Slug:** `readme-sections` · **Severity:** medium · **Category:** docs

Visitors decide in seconds whether they can use a project. Clear sections answer the first questions.

**How to fix:** Add headings such as '## Installation', '## Usage', '## Contributing' and '## License' to the README.

<a id="rd003"></a>

## RD003 README shows status badges

**Slug:** `readme-badges` · **Severity:** low · **Category:** docs

Badges for CI, version and license show at a glance that the project is alive and tested.

**How to fix:** Add a CI badge at the top of the README; GitHub shows its URL under Actions > workflow > Create status badge.

<a id="rd004"></a>

## RD004 LICENSE file with a recognised open-source license

**Slug:** `license` · **Severity:** high · **Category:** docs

Without a license nobody may legally use, copy or modify the code. An OSI-approved license makes reuse safe.

**How to fix:** Add a LICENSE file; MIT and Apache-2.0 are common permissive choices (see https://choosealicense.com).

Auto-fix: `repo-doctor fix --only license`

<a id="rd005"></a>

## RD005 CONTRIBUTING guide

**Slug:** `contributing` · **Severity:** medium · **Category:** community

A contributing guide tells newcomers how to set up the project, run tests and send a good pull request.

**How to fix:** Add CONTRIBUTING.md with development setup, tests, style and pull request steps.

Auto-fix: `repo-doctor fix --only contributing`

<a id="rd006"></a>

## RD006 Code of conduct

**Slug:** `code-of-conduct` · **Severity:** medium · **Category:** community

A code of conduct sets expectations for behaviour and explains how problems are reported and handled.

**How to fix:** Adopt the Contributor Covenant 2.1 in CODE_OF_CONDUCT.md and name a contact for reports.

Auto-fix: `repo-doctor fix --only code-of-conduct`

<a id="rd007"></a>

## RD007 Security policy

**Slug:** `security-policy` · **Severity:** medium · **Category:** community

A security policy tells researchers how to report vulnerabilities privately instead of in a public issue.

**How to fix:** Add SECURITY.md with supported versions and a private reporting channel (e.g. GitHub advisories).

Auto-fix: `repo-doctor fix --only security`

<a id="rd008"></a>

## RD008 Changelog

**Slug:** `changelog` · **Severity:** low · **Category:** docs

A changelog lets users see what changed between versions and whether an upgrade is safe.

**How to fix:** Add CHANGELOG.md following https://keepachangelog.com and update it with every release.

Auto-fix: `repo-doctor fix --only changelog`

<a id="rd010"></a>

## RD010 .gitignore is present

**Slug:** `gitignore` · **Severity:** medium · **Category:** hygiene

Without .gitignore, build output, dependencies and local secrets end up in commits.

**How to fix:** Add a .gitignore with the patterns for your languages and local files such as .env.

Auto-fix: `repo-doctor fix --only gitignore`

<a id="rd011"></a>

## RD011 .gitignore covers the detected languages

**Slug:** `gitignore-languages` · **Severity:** low · **Category:** hygiene

Every ecosystem has folders that must never be committed (node_modules, __pycache__, vendor, target), and .env files hold local secrets.

**How to fix:** Add the missing patterns to .gitignore.

Auto-fix: `repo-doctor fix --only gitignore`

<a id="rd012"></a>

## RD012 .editorconfig is present

**Slug:** `editorconfig` · **Severity:** low · **Category:** hygiene

.editorconfig keeps indentation, line endings and final newlines consistent across editors and contributors.

**How to fix:** Add an .editorconfig with charset, line endings, indentation and final newline rules.

Auto-fix: `repo-doctor fix --only editorconfig`

<a id="rd013"></a>

## RD013 Dependency lockfile is committed

**Slug:** `lockfile` · **Severity:** medium · **Category:** hygiene

Lockfiles make installs reproducible and let dependency bots and audits see the exact versions in use.

**How to fix:** Commit the lockfile your package manager writes (package-lock.json, poetry.lock, uv.lock, Cargo.lock, go.sum, ...).

<a id="rd014"></a>

## RD014 No large files committed

**Slug:** `large-files` · **Severity:** medium · **Category:** hygiene

Large binaries bloat every clone forever, even after deletion. Use Git LFS or release assets instead.

**How to fix:** Remove the files from history (git filter-repo) or track them with Git LFS; raise large_file_mb if intended.

<a id="rd015"></a>

## RD015 No secrets in tracked files

**Slug:** `secrets` · **Severity:** high · **Category:** security

Tokens, keys and passwords in Git history are found by bots within minutes and stay in history after deletion.

**How to fix:** Revoke the credential, remove it from history (git filter-repo) and load it from the environment instead. Mark false positives with 'repo-doctor:ignore' or [secrets] allow_paths.

<a id="rd016"></a>

## RD016 No broken relative links in Markdown

**Slug:** `markdown-links` · **Severity:** medium · **Category:** docs

Links to files or headings that no longer exist frustrate readers and look unmaintained.

**How to fix:** Fix or remove the listed links; exclude generated docs with [links] ignore in the config.

<a id="rd020"></a>

## RD020 Continuous integration is configured

**Slug:** `ci` · **Severity:** high · **Category:** ci

CI runs the tests on every push and pull request, so contributors and maintainers see breakage before merging.

**How to fix:** Add a workflow in .github/workflows/ that runs lint and tests on push and pull_request.

Auto-fix: `repo-doctor fix --only ci`

<a id="rd021"></a>

## RD021 Issue templates

**Slug:** `issue-templates` · **Severity:** low · **Category:** community

Issue forms ask reporters for versions, steps to reproduce and expected behaviour, which saves maintainers time.

**How to fix:** Add issue forms such as .github/ISSUE_TEMPLATE/bug_report.yml and feature_request.yml.

Auto-fix: `repo-doctor fix --only issue-templates`

<a id="rd022"></a>

## RD022 Pull request template

**Slug:** `pr-template` · **Severity:** low · **Category:** community

A pull request template reminds contributors to describe the change, link issues and run the tests.

**How to fix:** Add .github/pull_request_template.md with a short checklist.

Auto-fix: `repo-doctor fix --only pr-template`

<a id="rd023"></a>

## RD023 Automated dependency updates (Dependabot or Renovate)

**Slug:** `dependency-updates` · **Severity:** medium · **Category:** security

Bots that open pull requests for outdated or vulnerable dependencies keep the project secure with little effort.

**How to fix:** Add .github/dependabot.yml for your ecosystems, or a renovate.json.

Auto-fix: `repo-doctor fix --only dependabot`

<a id="rd030"></a>

## RD030 Package metadata is complete

**Slug:** `package-metadata` · **Severity:** medium · **Category:** metadata

Registries (PyPI, npm, Packagist, crates.io) show description, license, repository link and keywords; they drive search ranking and trust.

**How to fix:** Fill in description, license, repository URL and keywords in each package manifest.

<a id="rd040"></a>

## RD040 GitHub repository has a description

**Slug:** `github-description` · **Severity:** medium · **Category:** metadata · **Needs:** `GITHUB_TOKEN`

The description is shown in search results, on profile pages and in link previews.

**How to fix:** Set it under the repository's About settings or with: gh repo edit --description '...'

<a id="rd041"></a>

## RD041 GitHub repository has topics

**Slug:** `github-topics` · **Severity:** low · **Category:** metadata · **Needs:** `GITHUB_TOKEN`

Topics make the project discoverable on github.com/topics and in GitHub search.

**How to fix:** Add 5-10 topics: gh repo edit --add-topic python --add-topic cli

<a id="rd042"></a>

## RD042 GitHub repository has a homepage URL

**Slug:** `github-homepage` · **Severity:** low · **Category:** metadata · **Needs:** `GITHUB_TOKEN`

A homepage link (docs site, package page) gives visitors a next step right from the About box.

**How to fix:** Set it with: gh repo edit --homepage https://...

<a id="rd043"></a>

## RD043 Default branch is protected

**Slug:** `branch-protection` · **Severity:** medium · **Category:** security · **Needs:** `GITHUB_TOKEN`

Protection (or a ruleset) stops force-pushes and direct pushes and can require reviews and passing CI.

**How to fix:** Add a branch ruleset for the default branch: require pull requests and status checks, block force pushes.

<a id="rd050"></a>

## RD050 .dockerignore next to the Dockerfile

**Slug:** `dockerignore` · **Severity:** low · **Category:** docker · **Applies to:** Docker

Without .dockerignore the whole folder, including .git and local secrets, is sent to the build context.

**How to fix:** Add a .dockerignore that excludes .git, dependencies, build output and .env files.

Auto-fix: `repo-doctor fix --only dockerignore`

<a id="rd051"></a>

## RD051 Dockerfile base images are pinned

**Slug:** `docker-base-pinned` · **Severity:** low · **Category:** docker · **Applies to:** Docker

FROM image:latest (or no tag) changes under your feet and makes builds unreproducible.

**How to fix:** Use a specific tag such as python:3.12-slim, or pin a digest (image@sha256:...).
