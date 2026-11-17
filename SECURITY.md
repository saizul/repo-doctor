# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | yes |

## What counts as a vulnerability

- `fix` writing outside the target repository or overwriting files without `--force`
- A secret value that appears unmasked in any output format
- The GitHub token being sent anywhere other than the configured GitHub API
- Code execution through crafted repository content (file names, manifests, Markdown)
- A problem in `action.yml` that allows script injection through inputs

Missed or wrongly detected secrets are usually not vulnerabilities; please use
the "False positive or false negative" issue form (without the real secret).

## Reporting

Please **do not** open a public issue. Use
[GitHub private vulnerability reporting](https://github.com/saizul/repo-doctor/security/advisories/new)
with the version, the impact and steps to reproduce.

You will get an answer within 5 working days. Fixes are released as soon as
possible and credited in the changelog unless you prefer otherwise.
