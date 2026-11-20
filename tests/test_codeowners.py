from __future__ import annotations

import pytest

from conftest import healthy_files, make_repo, outcome_of, status_of
from repo_doctor.checks.codeowners import matches, parse_codeowners
from repo_doctor.model import Status


@pytest.mark.parametrize(
    ("pattern", "path", "expected"),
    [
        ("*", "src/demo/core.py", True),
        ("*.py", "src/demo/core.py", True),
        ("*.js", "src/demo/core.py", False),
        ("/src/", "src/demo/core.py", True),
        ("/src/", "lib/src/x.py", False),
        ("src/", "lib/src/x.py", True),
        ("/README.md", "README.md", True),
        ("/README.md", "docs/README.md", False),
        ("README.md", "docs/README.md", True),
        ("src/demo", "src/demo/core.py", True),
        ("src/demo", "lib/src/demo/core.py", False),
        ("docs/*", "docs/a.md", True),
        ("docs/*", "docs/sub/b.md", False),
        ("docs/**", "docs/sub/b.md", True),
        ("**/core.py", "src/demo/core.py", True),
        ("src/**/cli.py", "src/demo/cli.py", True),
        ("src/**/cli.py", "src/cli.py", True),
        ("/.github/workflows/", ".github/workflows/ci.yml", True),
        ("c?re.py", "src/demo/core.py", True),
    ],
)
def test_pattern_matching(pattern, path, expected):
    assert matches(pattern, path) is expected


def test_parse_comments_escapes_and_errors():
    parsed = parse_codeowners(
        "# owners\n"
        "\n"
        "*            @octo/maintainers   # default\n"
        "docs/        docs@example.com\n"
        "\\#notes.md  @jane\n"
        "!vendor/     @octo\n"
        "*.[ch]       @octo\n"
        "/build/      octo\n"
        "/generated/\n"
    )
    assert [(r.line, r.pattern, r.owners) for r in parsed.rules] == [
        (3, "*", ("@octo/maintainers",)),
        (4, "docs/", ("docs@example.com",)),
        (5, "#notes.md", ("@jane",)),
        (9, "/generated/", ()),
    ]
    assert [line for line, _ in parsed.errors] == [6, 7, 8]
    assert "negated" in parsed.errors[0][1]
    assert "character ranges" in parsed.errors[1][1]
    assert "invalid owner(s) octo" in parsed.errors[2][1]


def test_missing_codeowners_is_skipped(healthy):
    assert status_of(healthy, "RD024") == Status.SKIP


def test_valid_codeowners_passes(tmp_path):
    files = healthy_files()
    files[".github/CODEOWNERS"] = "* @octo/core\n/src/demo/ @jane\n*.toml @octo\n"
    outcome = outcome_of(make_repo(tmp_path / "r", files), "codeowners")
    assert outcome.status == Status.PASS
    assert outcome.message == "3 rule(s) in .github/CODEOWNERS"


def test_invalid_lines_fail_with_locations(tmp_path):
    files = healthy_files()
    files["CODEOWNERS"] = "* @octo\n!docs/ @octo\nsrc/ jane\n"
    outcome = outcome_of(make_repo(tmp_path / "r", files), "RD024")
    assert outcome.status == Status.FAIL
    assert [str(loc) for loc in outcome.locations] == ["CODEOWNERS:2", "CODEOWNERS:3"]


def test_stale_patterns_warn(tmp_path):
    files = healthy_files()
    files[".github/CODEOWNERS"] = "* @octo\n/old-module/ @jane\n*.go @octo\n"
    outcome = outcome_of(make_repo(tmp_path / "r", files), "RD024")
    assert outcome.status == Status.WARN
    assert outcome.details == [
        ".github/CODEOWNERS:2 pattern '/old-module/' matches no file",
        ".github/CODEOWNERS:3 pattern '*.go' matches no file",
    ]


def test_shadowed_codeowners_file_warns(tmp_path):
    files = healthy_files()
    files[".github/CODEOWNERS"] = "* @octo\n"
    files["docs/CODEOWNERS"] = "* @someone-else\n"
    outcome = outcome_of(make_repo(tmp_path / "r", files), "RD024")
    assert outcome.status == Status.WARN
    assert "docs/CODEOWNERS is ignored" in outcome.details[0]


def test_empty_codeowners_warns(tmp_path):
    files = healthy_files()
    files[".github/CODEOWNERS"] = "# nothing yet\n"
    assert status_of(make_repo(tmp_path / "r", files), "RD024") == Status.WARN
