# Contributing to repo-doctor

Thank you for helping make open-source repositories healthier! New checks,
better templates, false-positive fixes and documentation are all welcome.

- [Ways to contribute](#ways-to-contribute)
- [Development setup](#development-setup)
- [Project layout](#project-layout)
- [Add a new check](#add-a-new-check)
- [Add or change a fixer](#add-or-change-a-fixer)
- [Add a secret rule](#add-a-secret-rule)
- [Guidelines](#guidelines)
- [Pull request process](#pull-request-process)

## Ways to contribute

| Size | Idea |
| --- | --- |
| 10 minutes | Report a false positive with a minimal example (issue template "False positive") |
| 30 minutes | Add a synonym for README sections, a lockfile name or a CI provider |
| 1 hour | Add a new check from the issues labelled `new check` |
| 1-2 hours | Support a new language (detection, `.gitignore` patterns, Dependabot ecosystem, CI template) |

Issues labelled `good first issue` are a good start. Comment on the issue so
that nobody else picks the same one.

## Development setup

```bash
git clone https://github.com/saizul/repo-doctor
cd repo-doctor
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .[dev]
pytest
ruff check . && ruff format --check .
```

Python 3.10+ and Git are needed. Tests must not use the network.

## Project layout

| Path | Responsibility |
| --- | --- |
| `src/repo_doctor/model.py` | `@check` decorator, `CheckInfo`, `Outcome`, statuses and severities |
| `src/repo_doctor/repo.py` | File index (Git-aware), case-insensitive lookup, language detection, manifests |
| `src/repo_doctor/checks/` | The checks, grouped by topic (`docs`, `hygiene`, `ci`, `security`, `links`, `metadata`, `remote`) |
| `src/repo_doctor/engine.py` | Runs checks, scoring and grades |
| `src/repo_doctor/output.py` | Text, JSON, Markdown and SARIF output |
| `src/repo_doctor/fix.py` | Fixers and template rendering |
| `src/repo_doctor/templates/` | Files created by `fix` (tokens like `@@PROJECT@@`) |
| `src/repo_doctor/scanner.py` | Secret rules |
| `src/repo_doctor/licenses.py` | SPDX fingerprints |
| `action.yml` | The composite GitHub Action |
| `docs/checks.md` | Check reference, rebuilt from the registry |

## Add a new check

1. **Pick an ID.** IDs are grouped: `RD00x` docs and community, `RD01x` hygiene,
   `RD02x` CI and community automation, `RD03x` metadata, `RD04x` remote,
   `RD05x` Docker. Use the next free number in the group. IDs never change once released.

2. **Write the function** in the matching module under `src/repo_doctor/checks/`:

   ```python
   from repo_doctor.model import Location, Outcome, Severity, check, failed, passed, skipped
   from repo_doctor.repo import Repo


   @check(
       "RD009",
       "citation",                      # slug: lowercase, used with --only/--skip
       "CITATION.cff for academic use",  # title shown in reports
       Severity.LOW,                     # high = 10, medium = 5, low = 2 points
       "docs",                           # category
       "A CITATION.cff tells researchers how to cite the software.",       # why it matters
       "Add CITATION.cff (https://citation-file-format.github.io/).",      # how to fix
       # languages=("python",),        # only run when one of these languages is detected
       # fixer="citation",             # name of a fixer in fix.py, if it can be created
   )
   def citation(repo: Repo) -> Outcome:
       if repo.find(["CITATION.cff"]):
           return passed("CITATION.cff")
       return failed("No CITATION.cff", locations=[Location("CITATION.cff")])
   ```

   Return `passed`, `warned` (half the points), `failed` or `skipped` (not applicable).
   Use `repo.files`, `repo.find(...)`, `repo.read_text(...)`, `repo.toml(...)`, `repo.json(...)`
   and `repo.languages` instead of touching the file system directly.
   Read `repo.config` for user settings.

3. **Write tests** in `tests/` with `make_repo(tmp_path, {...files...})` from
   `conftest.py`. Cover pass, fail and the tricky cases:

   ```python
   def test_citation(tmp_path):
       assert status_of(make_repo(tmp_path / "a"), "RD009") == Status.FAIL
       assert status_of(make_repo(tmp_path / "b", {"CITATION.cff": "cff-version: 1.2.0"}), "RD009") == Status.PASS
   ```

4. **Make sure repo-doctor still passes its own checks**, and that the healthy
   fixture in `conftest.py` still scores 100 (add the file there if the check
   should pass for a healthy project).

5. **Regenerate the reference** and update the README table:

   ```bash
   repo-doctor checks -f markdown > docs/checks.md
   ```

## Add or change a fixer

Fixers live in `src/repo_doctor/fix.py` and are registered in `FIXERS`.

- Put template files in `src/repo_doctor/templates/` (no leading dots in file
  names, so they are packaged). Available tokens: `@@PROJECT@@`, `@@AUTHOR@@`,
  `@@YEAR@@`, `@@SECURITY_CONTACT@@`, `@@COC_CONTACT@@`, `@@ISSUES@@`,
  `@@SECURITY_URL@@`, `@@BRANCH@@`, `@@DEV_SETUP@@`.
- Always write through `_write(...)`, which refuses to overwrite without `--force`
  and respects `--dry-run`.
- Test that `fix` creates the file, skips an existing one and that the related
  check passes afterwards.
- Templates must be your own text or text whose license allows redistribution.

## Add a secret rule

Rules are in `RULES` in `src/repo_doctor/scanner.py`. A rule needs a stable `id`,
a title and a regular expression with one capture group for the secret value.
Prefer token formats with a fixed prefix (low false-positive rate).

In tests, **never write a real-looking token as one string literal**: build it
from pieces (`"ghp" + "_" + "..."`) so that push protection and other scanners
do not flag this repository.

## Guidelines

- Checks must be fast, deterministic and work offline (remote checks go in `checks/remote.py`).
- Messages are short and specific: say what is missing and where.
- No new runtime dependencies without discussion; the tool should stay standard-library only.
- Type hints everywhere, `ruff check` and `ruff format` clean.

## Pull request process

1. Fork and create a branch (`check/citation`, `fix/readme-sections-false-positive`).
2. Keep pull requests focused; fill in the checklist in the template.
3. Add an entry to `CHANGELOG.md` under "Unreleased".
4. A maintainer reviews within a few days.

By contributing you agree that your work is released under the MIT License and
that you follow the [Code of Conduct](CODE_OF_CONDUCT.md).
