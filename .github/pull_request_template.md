## What does this pull request do?

<!-- One or two sentences. Link the issue: "Closes #123". -->

## Type

- [ ] New check
- [ ] New or improved fixer / template
- [ ] Bug fix or false positive fix
- [ ] Documentation

## Checklist

- [ ] Tests added or updated (`pytest` passes; tests use `tmp_path` repos and no network)
- [ ] `ruff check . && ruff format --check .` passes
- [ ] New checks have an ID, slug, severity, explanation and fix hint, and `docs/checks.md` is regenerated
      (`repo-doctor checks -f markdown > docs/checks.md`)
- [ ] Fixers never overwrite existing files without `--force`
- [ ] No real secrets in tests (build fake tokens from string pieces at runtime)
- [ ] CHANGELOG.md updated under "Unreleased"
